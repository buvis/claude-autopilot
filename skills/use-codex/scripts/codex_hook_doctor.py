#!/usr/bin/env python3
"""Doctor for a codex hooks.json — verdicts every referenced hook target.

Usage:
    codex_hook_doctor.py check --config PATH --aegis-root PATH --autopilot-root PATH
"""

from __future__ import annotations

import argparse
import ast
import json
import os
import shlex
import sys
from pathlib import Path

# basename -> (root the canonical source resolves against, relative path
# under that root)
KNOWN_HOOKS: dict[str, tuple[str, str]] = {
    "validate_commit_msg.py": ("aegis", "hooks/validate_commit_msg.py"),
    "_common.py": ("aegis", "hooks/_common.py"),
    "protect_config.py": ("aegis", "hooks/protect_config.py"),
    "block_devlocal_redirects.py": ("aegis", "hooks/block_devlocal_redirects.py"),
    "block-suppression-markers.py": ("aegis", "hooks/block_suppression_markers.py"),
    "gateguard-fact-force.py": ("aegis", "hooks/gateguard_fact_force.py"),
    "enforce_prd_location.py": ("autopilot", "hooks/enforce_prd_location.py"),
}


def _iter_commands(hooks: dict) -> list[str]:
    commands: list[str] = []
    for entries in hooks.values():
        for entry in entries:
            for hook in entry.get("hooks", []):
                if hook.get("type") == "command":
                    commands.append(hook["command"])
    return commands


def _resolve_target(command: str, config_dir: Path) -> Path:
    tokens = shlex.split(command)
    path = Path(tokens[-1])
    if not path.is_absolute():
        path = config_dir / path
    return Path(os.path.normpath(path))


def _verdict_for(
    target: Path,
    aegis_root: Path,
    autopilot_root: Path,
) -> tuple[str, str]:
    if not target.exists():
        return "missing", ""
    if target.stat().st_size == 0:
        return "empty", ""

    # Syntax outranks staleness: a hook that cannot compile fails on every
    # tool call, and `stale` exits 3 (rung stays on) while `syntax_error`
    # exits 1 (rung gates off). Checking drift first would report the
    # harmless verdict for the harmful state. `compile()` is used rather
    # than py_compile so the check writes no bytecode -- `check` is
    # contractually read-only, and a batch runs it against the real ~/.codex.
    try:
        compile(target.read_text(encoding="utf-8"), str(target), "exec")
    except (SyntaxError, UnicodeDecodeError) as exc:
        return "syntax_error", str(exc)

    known = KNOWN_HOOKS.get(target.name)
    if known is not None:
        root_name, canonical_rel = known
        root = aegis_root if root_name == "aegis" else autopilot_root
        canonical = root / canonical_rel
        if not canonical.exists():
            return "no_canonical", ""
        if canonical.read_bytes() != target.read_bytes():
            return "stale", ""

    return "ok", ""


def check(
    *,
    config: Path,
    aegis_root: Path,
    autopilot_root: Path,
) -> list[tuple[str, str, str]]:
    hooks = json.loads(config.read_text(encoding="utf-8"))["hooks"]
    if not isinstance(hooks, dict):
        raise TypeError("hooks must be an object")
    config_dir = config.parent

    targets: list[Path] = []
    seen: set[Path] = set()
    for command in _iter_commands(hooks):
        target = _resolve_target(command, config_dir)
        if target not in seen:
            seen.add(target)
            targets.append(target)

    hooks_dir = config_dir / "hooks"
    if hooks_dir.is_dir():
        for path in sorted(hooks_dir.glob("*.py")):
            if path not in seen:
                seen.add(path)
                targets.append(path)

    results: list[tuple[str, str, str]] = []
    for target in targets:
        verdict, detail = _verdict_for(target, aegis_root, autopilot_root)
        results.append((verdict, str(target), detail))
    return results


def _missing_common_import_names(hooks_dir: Path, canonical: Path) -> list[str]:
    imported: set[str] = set()
    unparseable: list[str] = []
    for py_file in sorted(hooks_dir.glob("*.py")):
        if py_file.name == "_common.py":
            continue
        try:
            tree = ast.parse(py_file.read_text(encoding="utf-8"))
        except SyntaxError:
            unparseable.append(
                f"{py_file.name}: SyntaxError (cannot verify _common imports)"
            )
            continue
        except (UnicodeDecodeError, OSError):
            unparseable.append(
                f"{py_file.name}: unreadable (cannot verify _common imports)"
            )
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module == "_common":
                imported.update(alias.name for alias in node.names)

    try:
        canonical_tree = ast.parse(canonical.read_text(encoding="utf-8"))
    except SyntaxError:
        unparseable.append(
            f"{canonical.name}: SyntaxError (cannot verify _common imports)"
        )
        return sorted(imported) + unparseable

    defined = {
        node.name for node in canonical_tree.body if isinstance(node, ast.FunctionDef)
    }
    return sorted(imported - defined) + unparseable


def _repair_unknown(
    verdict: str, target_str: str, detail: str
) -> tuple[str, str, str] | None:
    if verdict in ("missing", "empty", "syntax_error"):
        why = detail or f"no canonical source for unknown hook ({verdict})"
        return ("unrepairable", target_str, why)
    return None


def _repair_known(
    verdict: str,
    target_str: str,
    known: tuple[str, str],
    *,
    hooks_dir: Path,
    aegis_root: Path,
    autopilot_root: Path,
    dry_run: bool,
) -> tuple[str, str, str] | None:
    if verdict not in ("missing", "empty", "stale", "no_canonical"):
        return None

    target = Path(target_str)
    if target.is_symlink():
        return ("skipped", target_str, "symlink")

    root_name, canonical_rel = known
    root = aegis_root if root_name == "aegis" else autopilot_root
    canonical = root / canonical_rel
    if not canonical.exists():
        return ("unrepairable", target_str, f"no canonical source ({canonical})")

    if target.name == "_common.py":
        missing = _missing_common_import_names(hooks_dir, canonical)
        if missing:
            why = (
                "sibling imports names not defined in canonical _common.py: "
                + ", ".join(missing)
            )
            return ("unrepairable", target_str, why)

    if dry_run:
        return ("would-repair", target_str, str(canonical))

    tmp_path = target.with_name(target.name + ".tmp")
    tmp_path.write_bytes(canonical.read_bytes())
    os.replace(tmp_path, target)
    return ("repaired", target_str, str(canonical))


def _repair_target(
    verdict: str,
    target_str: str,
    detail: str,
    *,
    tests_dir: Path,
    registered: set[Path],
    hooks_dir: Path,
    aegis_root: Path,
    autopilot_root: Path,
    dry_run: bool,
) -> tuple[str, str, str] | None:
    target = Path(target_str)
    try:
        target.relative_to(tests_dir)
        return None
    except ValueError:
        pass

    known = KNOWN_HOOKS.get(target.name)
    # _common.py is never named by a command, so it is always "unregistered".
    # Excluding it here keeps its repair path; the placeholder scan exempts it
    # too, so without this it would be neither repaired nor removed.
    if (
        verdict == "empty"
        and target not in registered
        and target.name != "_common.py"
    ):
        return None  # zero-byte + unregistered -> handled by the placeholder scan below

    if known is None:
        return _repair_unknown(verdict, target_str, detail)

    return _repair_known(
        verdict,
        target_str,
        known,
        hooks_dir=hooks_dir,
        aegis_root=aegis_root,
        autopilot_root=autopilot_root,
        dry_run=dry_run,
    )


def _remove_orphaned_empty(
    hooks_dir: Path, registered: set[Path], dry_run: bool
) -> list[tuple[str, str, str]]:
    out: list[tuple[str, str, str]] = []
    if not hooks_dir.is_dir():
        return out
    for path in sorted(hooks_dir.glob("*.py")):
        if (
            path.stat().st_size == 0
            and path not in registered
            and path.name != "_common.py"
        ):
            if dry_run:
                out.append(("would-remove", str(path), ""))
            else:
                path.unlink()
                out.append(("removed", str(path), ""))
    return out


def repair(
    *,
    config: Path,
    aegis_root: Path,
    autopilot_root: Path,
    dry_run: bool = False,
) -> list[tuple[str, str, str]]:
    results = check(config=config, aegis_root=aegis_root, autopilot_root=autopilot_root)
    config_dir = config.parent
    hooks_dir = config_dir / "hooks"
    tests_dir = hooks_dir / "tests"

    hooks = json.loads(config.read_text(encoding="utf-8"))["hooks"]
    registered = {_resolve_target(c, config_dir) for c in _iter_commands(hooks)}

    out: list[tuple[str, str, str]] = []
    for verdict, target_str, detail in results:
        result = _repair_target(
            verdict,
            target_str,
            detail,
            tests_dir=tests_dir,
            registered=registered,
            hooks_dir=hooks_dir,
            aegis_root=aegis_root,
            autopilot_root=autopilot_root,
            dry_run=dry_run,
        )
        if result is not None:
            out.append(result)

    cleanup_hooks = json.loads(config.read_text(encoding="utf-8"))["hooks"]
    cleanup_registered = {
        _resolve_target(c, config_dir) for c in _iter_commands(cleanup_hooks)
    }
    out.extend(_remove_orphaned_empty(hooks_dir, cleanup_registered, dry_run))
    return out


def _default_config() -> Path:
    codex_home = os.environ.get("CODEX_HOME")
    if codex_home:
        return Path(codex_home) / "hooks.json"
    return Path.home() / ".codex" / "hooks.json"


def _default_aegis_root() -> Path:
    manifest = Path.home() / ".claude" / "plugins" / "installed_plugins.json"
    data = json.loads(manifest.read_text(encoding="utf-8"))
    return Path(data["plugins"]["aegis@buvis-plugins"][0]["installPath"])


def _default_autopilot_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="subcommand", required=True)
    check_parser = subparsers.add_parser("check")
    check_parser.add_argument("--config", type=Path)
    check_parser.add_argument("--aegis-root", type=Path)
    check_parser.add_argument("--autopilot-root", type=Path)
    repair_parser = subparsers.add_parser("repair")
    repair_parser.add_argument("--config", type=Path)
    repair_parser.add_argument("--aegis-root", type=Path)
    repair_parser.add_argument("--autopilot-root", type=Path)
    repair_parser.add_argument("--dry-run", action="store_true")
    return parser


def _resolve_roots(args: argparse.Namespace) -> tuple[Path, Path, Path]:
    config = args.config if args.config is not None else _default_config()
    if not config.exists():
        raise OSError(f"config not found: {config}")
    aegis_root = (
        args.aegis_root if args.aegis_root is not None else _default_aegis_root()
    )
    autopilot_root = (
        args.autopilot_root
        if args.autopilot_root is not None
        else _default_autopilot_root()
    )
    return config, aegis_root, autopilot_root


def _run_subcommand(
    args: argparse.Namespace,
    config: Path,
    aegis_root: Path,
    autopilot_root: Path,
) -> tuple[list[tuple[str, str, str]], list[tuple[str, str, str]]]:
    if args.subcommand == "repair":
        results = repair(
            config=config,
            aegis_root=aegis_root,
            autopilot_root=autopilot_root,
            dry_run=args.dry_run,
        )
        # Exit code reflects the post-repair state (identical to the
        # pre-repair state when --dry-run is set).
        verdicts = check(config=config, aegis_root=aegis_root, autopilot_root=autopilot_root)
        return results, verdicts
    results = check(config=config, aegis_root=aegis_root, autopilot_root=autopilot_root)
    return results, results


def _report(
    results: list[tuple[str, str, str]], verdicts: list[tuple[str, str, str]]
) -> int:
    ok = sum(1 for verdict, _, _ in verdicts if verdict == "ok")
    stale = sum(1 for verdict, _, _ in verdicts if verdict in ("stale", "no_canonical"))
    broken = sum(
        1
        for verdict, _, _ in verdicts
        if verdict in ("missing", "empty", "syntax_error")
    )

    for verdict, target, detail in results:
        print(f"{verdict}\t{target}\t{detail}")
    print(f"summary\t{ok} ok, {stale} stale, {broken} broken")

    if broken:
        return 1
    if stale:
        return 3
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    try:
        config, aegis_root, autopilot_root = _resolve_roots(args)
        results, verdicts = _run_subcommand(args, config, aegis_root, autopilot_root)
    except (
        OSError,
        json.JSONDecodeError,
        KeyError,
        TypeError,
        IndexError,
        ValueError,
        AttributeError,
    ) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    return _report(results, verdicts)


if __name__ == "__main__":
    sys.exit(main())
