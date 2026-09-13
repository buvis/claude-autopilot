#!/usr/bin/env python3
"""Per-item metrics for /fast-track: one JSONL row per finished item, appended
to ``dev/local/autopilot/loop-metrics.jsonl`` and its GC-exempt ``ledger/``
mirror, so an attended item renders beside the rows the autopilot loop writes.

    record_item.py --item ID --card PATH --model NAME --started EPOCH
        --outcome committed|branched|stopped --rework 0|1 --findings JSON
        --confirmed N [--cost USD]

The append is borrowed from ``record_dispatch.py``, whose writer names that
module's own ``FILENAME`` global, so the call is wrapped in a redirect that is
undone whether the write lands or blows up. ``--findings`` is stored in the
shape the review roster produced it; ``--cost`` absent means unmeasured, which
is not the same fact as free. Every write is best-effort and exits 0: nothing
on the item's path waits on these rows.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
import time
from pathlib import Path

FILENAME = "loop-metrics.jsonl"
OUTCOMES = ("committed", "branched", "stopped")
PHASE = "fast-track"

_RECORD_DISPATCH = (
    Path(__file__).resolve().parents[2] / "work" / "scripts" / "record_dispatch.py"
)
_spec = importlib.util.spec_from_file_location("record_dispatch", _RECORD_DISPATCH)
assert _spec is not None and _spec.loader is not None
_record_dispatch = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_record_dispatch)


def append_item_row(autopilot_dir: Path, row: dict[str, object]) -> None:
    """Append ``row`` through the shared writer, pointed at the loop ledger.

    ``record_dispatch.FILENAME`` is process-wide state /work appends its own
    dispatch rows through, so the redirect is undone in a ``finally``: a write
    that raises must not leave later dispatch rows landing in this ledger.
    """
    original = _record_dispatch.FILENAME
    _record_dispatch.FILENAME = FILENAME
    try:
        _record_dispatch.append_row(autopilot_dir, row)
    finally:
        _record_dispatch.FILENAME = original


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Append one fast-track item row.")
    parser.add_argument("--item", required=True, help="the item, for the caller")
    parser.add_argument("--card", required=True, help="card path; its name is prd")
    parser.add_argument("--model", required=True)
    parser.add_argument("--started", required=True, type=int)
    parser.add_argument("--outcome", required=True, choices=OUTCOMES)
    parser.add_argument("--rework", required=True, type=int, choices=(0, 1))
    parser.add_argument("--findings", required=True, type=json.loads)
    parser.add_argument("--confirmed", required=True, type=int)
    parser.add_argument("--cost", type=float, help="measured USD; absent is unknown")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    autopilot_dir = _record_dispatch.find_autopilot_dir(Path.cwd())
    if autopilot_dir is None:
        return 0
    ts_end = int(time.time())
    append_item_row(
        autopilot_dir,
        {
            "ts_start": args.started,
            "ts_end": ts_end,
            "wall_secs": ts_end - args.started,
            "prd": Path(args.card).name,
            "batch": PHASE,
            "phase_launched": PHASE,
            "phase_end": PHASE,
            "signal": args.outcome,
            "model": args.model,
            "cost_usd": args.cost,
            "findings": args.findings,
            "confirmed": args.confirmed,
            "rework": args.rework,
            "outcome": args.outcome,
        },
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
