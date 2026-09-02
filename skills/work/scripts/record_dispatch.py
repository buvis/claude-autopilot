#!/usr/bin/env python3
"""Dispatch timing ledger for ``/work`` (PRD 00168).

Nothing in the pack said when anything happened: the attempt record carries
no timestamp and ``loop-metrics.jsonl`` is one row per session, so a 6-hour
gap between two commits could not be split into model work, quota waits,
handoff latency or a hung tool. This appends one JSONL row per dispatch start,
one per dispatch end and one per session-handoff edge to
``dev/local/autopilot/dispatch-metrics.jsonl``, mirrored into the GC-exempt
``ledger/`` copy the way the loop mirrors its own rows.

    record_dispatch.py start --kind KIND --task ID [--prompt-bytes N]
    record_dispatch.py end ID --outcome ok|timeout|killed|error|lost [--detail TEXT]
    record_dispatch.py handoff --site build|review|done --edge leave|resume --phase P --prd PRD

Every write is best-effort: an unresolvable autopilot dir, an unwritable file
or an id with no start row all exit 0. Telemetry never blocks a dispatch or a
phase transition, and no gate reads these rows. ``render_prompt.py`` imports
``start_row`` so a render opens the row for free.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import secrets
import sys
import time
from pathlib import Path

FILENAME = "dispatch-metrics.jsonl"
OUTCOMES = ("ok", "timeout", "killed", "error", "lost")
SITES = ("build", "review", "done")
EDGES = ("leave", "resume")

_WALK_UP = (
    Path(__file__).resolve().parents[2] / "run-autopilot" / "scripts" / "_walk_up.py"
)
_spec = importlib.util.spec_from_file_location("_walk_up", _WALK_UP)
assert _spec is not None and _spec.loader is not None
_walk_up = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_walk_up)

find_autopilot_dir = _walk_up.find_autopilot_dir


def append_row(autopilot_dir: Path, row: dict[str, object]) -> None:
    """Append ``row`` as one line to the working file and its ``ledger/`` mirror.

    A failed write prints one stderr line and returns: the caller is a
    dispatch or a phase transition, and neither waits on telemetry.
    """
    # ponytail: one O_APPEND write per row and no lock; add fcntl.flock if a
    # row ever grows past PIPE_BUF and concurrent lines start interleaving.
    line = json.dumps(row, separators=(",", ":")) + "\n"
    try:
        with open(autopilot_dir / FILENAME, "a", encoding="utf-8") as fh:
            fh.write(line)
        ledger = autopilot_dir / "ledger"
        ledger.mkdir(parents=True, exist_ok=True)
        with open(ledger / FILENAME, "a", encoding="utf-8") as fh:
            fh.write(line)
    except OSError as err:
        print(f"record_dispatch: append failed, row dropped: {err}", file=sys.stderr)


def start_row(
    autopilot_dir: Path | None,
    kind: str,
    task: str,
    prompt_bytes: int | None,
) -> str:
    """Open a dispatch row and return its id; no dir means no write, same id."""
    dispatch_id = secrets.token_hex(4)
    if autopilot_dir is not None:
        append_row(
            autopilot_dir,
            {
                "id": dispatch_id,
                "kind": kind,
                "task": task,
                "queued_at": int(time.time()),
                "prompt_bytes": prompt_bytes,
            },
        )
    return dispatch_id


def _queued_at(autopilot_dir: Path, dispatch_id: str) -> int | None:
    """The start row's ``queued_at`` for ``dispatch_id``, or None without one."""
    try:
        lines = (autopilot_dir / FILENAME).read_text(encoding="utf-8").splitlines()
    except OSError:
        return None
    for line in lines:
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if isinstance(row, dict) and row.get("id") == dispatch_id:
            queued_at = row.get("queued_at")
            if isinstance(queued_at, int):
                return queued_at
    return None


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Append dispatch timing rows.")
    verbs = parser.add_subparsers(dest="verb", required=True)

    start = verbs.add_parser("start", help="open a row for a hand-built dispatch")
    start.add_argument("--kind", required=True)
    start.add_argument("--task", required=True)
    start.add_argument("--prompt-bytes", type=int)

    end = verbs.add_parser("end", help="close a dispatch row")
    end.add_argument("id")
    end.add_argument("--outcome", required=True, choices=OUTCOMES)
    end.add_argument("--detail")

    handoff = verbs.add_parser("handoff", help="stamp one edge of a session handoff")
    handoff.add_argument("--site", required=True, choices=SITES)
    handoff.add_argument("--edge", required=True, choices=EDGES)
    handoff.add_argument("--phase", required=True)
    handoff.add_argument("--prd", required=True)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    autopilot_dir = find_autopilot_dir(Path.cwd())
    if args.verb == "start":
        print(start_row(autopilot_dir, args.kind, args.task, args.prompt_bytes))
    elif autopilot_dir is None:
        return 0
    elif args.verb == "end":
        ended_at = int(time.time())
        queued_at = _queued_at(autopilot_dir, args.id)
        append_row(
            autopilot_dir,
            {
                "id": args.id,
                "ended_at": ended_at,
                "elapsed_s": None if queued_at is None else ended_at - queued_at,
                "outcome": args.outcome,
                "detail": args.detail,
            },
        )
    else:
        append_row(
            autopilot_dir,
            {
                "kind": "handoff",
                "site": args.site,
                "edge": args.edge,
                "at": int(time.time()),
                "phase": args.phase,
                "prd": args.prd,
            },
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
