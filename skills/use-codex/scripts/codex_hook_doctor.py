#!/usr/bin/env python3
"""Doctor for a codex hooks.json — verdicts every referenced hook target.

Usage:
    codex_hook_doctor.py check --config PATH --aegis-root PATH --autopilot-root PATH
"""

from __future__ import annotations

import argparse
import json
import os
import py_compile
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
    return path if path.is_absolute() else config_dir / path


def _verdict_for(
    target: Path, aegis_root: Path, autopilot_root: Path
) -> tuple[str, str]:
    if not target.exists():
        return "missing", ""
    if target.stat().st_size == 0:
        return "empty", ""

    known = KNOWN_HOOKS.get(target.name)
    if known is not None:
        root_name, canonical_rel = known
        root = aegis_root if root_name == "aegis" else autopilot_root
        canonical = root / canonical_rel
        if not canonical.exists():
            return "no_canonical", ""
        if canonical.read_bytes() != target.read_bytes():
            return "stale", ""

    try:
        py_compile.compile(str(target), doraise=True)
    except py_compile.PyCompileError as exc:
        return "syntax_error", str(exc)

    return "ok", ""


def check(
    *, config: Path, aegis_root: Path, autopilot_root: Path
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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="subcommand", required=True)
    check_parser = subparsers.add_parser("check")
    check_parser.add_argument("--config", type=Path)
    check_parser.add_argument("--aegis-root", type=Path)
    check_parser.add_argument("--autopilot-root", type=Path)
    args = parser.parse_args(argv)

    try:
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
        results = check(
            config=config,
            aegis_root=aegis_root,
            autopilot_root=autopilot_root,
        )
    except (OSError, json.JSONDecodeError, KeyError, TypeError, IndexError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    ok = sum(1 for verdict, _, _ in results if verdict == "ok")
    stale = sum(1 for verdict, _, _ in results if verdict in ("stale", "no_canonical"))
    broken = sum(
        1 for verdict, _, _ in results if verdict in ("missing", "empty", "syntax_error")
    )

    for verdict, target, detail in results:
        print(f"{verdict}\t{target}\t{detail}")
    print(f"summary\t{ok} ok, {stale} stale, {broken} broken")

    if broken:
        return 1
    if stale:
        return 3
    return 0


if __name__ == "__main__":
    sys.exit(main())
