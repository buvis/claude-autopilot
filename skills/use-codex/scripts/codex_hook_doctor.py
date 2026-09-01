#!/usr/bin/env python3
"""Doctor for a codex hooks.json — verdicts every referenced hook target.

Usage:
    codex_hook_doctor.py check --config PATH --aegis-root PATH --autopilot-root PATH
"""

from __future__ import annotations

import argparse
import json
import py_compile
import shlex
import sys
from pathlib import Path

KNOWN_HOOKS: dict[str, str] = {
    "validate_commit_msg.py": "hooks/validate_commit_msg.py",
    "_common.py": "hooks/_common.py",
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
    path_token = next(token for token in tokens if token.endswith(".py"))
    path = Path(path_token)
    return path if path.is_absolute() else config_dir / path


def _verdict_for(target: Path, aegis_root: Path) -> tuple[str, str]:
    if not target.exists():
        return "missing", ""
    if target.stat().st_size == 0:
        return "empty", ""

    canonical_rel = KNOWN_HOOKS.get(target.name)
    if canonical_rel is not None:
        canonical = aegis_root / canonical_rel
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
        verdict, detail = _verdict_for(target, aegis_root)
        results.append((verdict, str(target), detail))
    return results


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="subcommand", required=True)
    check_parser = subparsers.add_parser("check")
    check_parser.add_argument("--config", type=Path, required=True)
    check_parser.add_argument("--aegis-root", type=Path, required=True)
    check_parser.add_argument("--autopilot-root", type=Path, required=True)
    args = parser.parse_args(argv)

    try:
        results = check(
            config=args.config,
            aegis_root=args.aegis_root,
            autopilot_root=args.autopilot_root,
        )
    except (OSError, json.JSONDecodeError, KeyError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    ok = sum(1 for verdict, _, _ in results if verdict == "ok")
    stale = sum(1 for verdict, _, _ in results if verdict == "stale")
    broken = len(results) - ok - stale

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
