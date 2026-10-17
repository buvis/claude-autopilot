#!/usr/bin/env python3
"""statectl.py - re-export shim over cli/statectl.py (PRD 00089).

The implementation moved to the `cli/` package so `state.json` has ONE
validated writer. This path stays because ~100 call sites name it: the skill
prose, the gate files, `scripts/fablectl.py`, and two test suites that must
keep passing unmodified.

Everything below is the same object as its `cli.statectl` counterpart, not a
copy - `StateError` raised inside the package is the `StateError` an importer
of this module catches.

CLI and exit codes are unchanged:
    python3 statectl.py <state-path> get|set|append|del <json-path> [value]
    python3 statectl.py <state-path> get <json-path> --default <json-value>
    python3 statectl.py <state-path> decide --issue I --severity S --cycle C --action A --reason R [--type T]
    python3 statectl.py <state-path> task-start <task-id>
    python3 statectl.py <state-path> task-done <task-id> <attempt-json-file>
    python3 statectl.py <state-path> append-attempt <task-id> <attempt-json-file>
    python3 statectl.py <state-path> set-contract-card <file>
    python3 statectl.py <state-path> task-add <task-json-file>
    python3 statectl.py <state-path> task-set-body <task-id> <body-file>
    python3 statectl.py <state-path> task-set-meta <task-id> <meta-json-file>
    python3 statectl.py <state-path> task-set-status <task-id> pending|in_progress|completed
    python3 statectl.py <state-path> tasks-clear
    python3 statectl.py <state-path> complete-prd <prd-filename>
    python3 statectl.py <state-path> write-brief <out-md>

    0  ok
    1  bad argument, unsupported json-path, or a value the schema rejects
    2  state file missing or corrupt

See `cli/statectl.py`'s docstring for the two behaviors the move changed.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# FRONT of sys.path, unconditionally, mirroring cli/__main__.py's bootstrap: a
# decoy top-level `cli/` package elsewhere on sys.path (e.g. the invoking
# process's cwd) must never shadow the real one this script belongs to. The
# import below has to follow it, exactly as it does in __main__.py.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from cli import schema
from cli.statectl import (
    USAGE,
    StateError,
    Token,
    UsageError,
    atomic_write,
    do_append,
    do_append_attempt,
    do_complete_prd,
    do_del,
    do_set,
    do_set_contract_card,
    do_task_add,
    do_task_done,
    do_task_set_body,
    do_task_set_meta,
    do_task_set_status,
    do_task_start,
    do_tasks_clear,
    get_value,
    main,
    mutate,
    parse_path,
    read_and_parse,
    write_brief,
)


def _run_decide(state_path: Path, decide_argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="statectl.py decide", add_help=False)
    parser.add_argument("--issue", required=True)
    parser.add_argument("--severity", required=True)
    parser.add_argument("--cycle", required=True, type=int)
    parser.add_argument("--action", required=True)
    parser.add_argument("--reason", required=True)
    parser.add_argument("--type")
    try:
        args = parser.parse_args(decide_argv)
    except SystemExit:
        return 1

    entry: dict[str, object] = {
        "issue": args.issue,
        "severity": args.severity,
        "cycle": args.cycle,
        "action": args.action,
        "reason": args.reason,
    }
    if args.type is not None:
        entry["type"] = args.type

    def apply(data):
        data.setdefault("autonomous_decisions", []).append(entry)

    try:
        mutate(state_path, apply)
    except schema.SchemaError as err:
        print(f"statectl: decide: {err}", file=sys.stderr)
        return 1
    except (StateError, OSError) as err:
        print(f"statectl: decide: {err}", file=sys.stderr)
        return 2
    return 0


def _run_get_with_default(state_path: Path, json_path: str, default_raw: str) -> int:
    try:
        default = json.loads(default_raw)
    except ValueError as err:
        print(f"statectl: get: invalid --default JSON: {err}", file=sys.stderr)
        return 1
    try:
        tokens = parse_path(json_path)
    except UsageError as err:
        print(f"{USAGE}\nstatectl: get: {err}", file=sys.stderr)
        return 1
    try:
        _, data = read_and_parse(state_path)
    except StateError as err:
        print(f"statectl: get: {err}", file=sys.stderr)
        return 2
    try:
        value = get_value(data, tokens)
    except UsageError:
        value = default
    print(json.dumps(value))
    return 0


class _RejectRepeatedDefault(argparse.Action):
    """Reject a second `--default`, instead of argparse's default last-wins."""

    def __call__(self, parser, namespace, values, option_string=None):
        if getattr(namespace, self.dest) is not None:
            parser.error(f"{option_string} specified multiple times")
        setattr(namespace, self.dest, values)


def _parse_get_args(get_argv: list[str]) -> tuple[str, str] | None:
    """Parse `get` argv (path and `--default` in either order).

    Returns (path, default_raw), or None when the path is missing, an extra
    positional argument is present, `--default` is repeated, or a trailing
    `--default` carries no value - each is a usage error.
    """
    parser = argparse.ArgumentParser(
        prog="statectl.py get", add_help=False, exit_on_error=True
    )
    parser.add_argument("path")
    parser.add_argument("--default", action=_RejectRepeatedDefault)
    try:
        args = parser.parse_args(get_argv)
    except SystemExit:
        return None
    if args.default is None:
        return None
    return args.path, args.default


def _dispatch(argv: list[str]) -> int:
    """Entry-point-only dispatch: intercepts `decide` and `get --default`
    before falling through to the re-exported `main` unchanged, so `main`
    itself stays the same object `cli.statectl.main` is (test_shims.py)."""
    if len(argv) >= 2 and argv[1] == "decide":
        return _run_decide(Path(argv[0]), argv[2:])
    if len(argv) >= 3 and argv[1] == "get" and "--default" in argv[2:]:
        parsed = _parse_get_args(argv[2:])
        if parsed is None:
            print(USAGE, file=sys.stderr)
            return 1
        path, default_raw = parsed
        return _run_get_with_default(Path(argv[0]), path, default_raw)
    return main(argv)

__all__ = [
    "USAGE",
    "StateError",
    "Token",
    "UsageError",
    "atomic_write",
    "do_append",
    "do_append_attempt",
    "do_complete_prd",
    "do_del",
    "do_set",
    "do_set_contract_card",
    "do_task_add",
    "do_task_done",
    "do_task_set_body",
    "do_task_set_meta",
    "do_task_set_status",
    "do_task_start",
    "do_tasks_clear",
    "get_value",
    "main",
    "mutate",
    "parse_path",
    "read_and_parse",
    "write_brief",
]


if __name__ == "__main__":
    sys.exit(_dispatch(sys.argv[1:]))
