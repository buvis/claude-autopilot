#!/usr/bin/env python3
"""handoff.py - clearing the session markers a lifecycle commit leaves behind.

Exposes:
    clear_markers(autopilot_dir) -> None
        Remove `.handoff-requested` and `.cap-fired` from the directory
        holding state.json. Absent is not an error, and a marker that cannot
        be removed is reported on stderr and skipped rather than raised: this
        always runs AFTER the commit it follows, so it must never turn a
        landed transition into a failure. Each marker is removed in its OWN
        try block, so a failure on one cannot skip the other.

Call it only after a commit that ends the current PRD or phase (phase-done's
tasks_done/converged/more_prds/drained, reset-prd, a successful stall or
park). A commit that leaves the session on the same phase and PRD (review +
rework) keeps its markers: that session continues, so a pending handoff or
cap request is still pending.
"""

from __future__ import annotations

import sys
from pathlib import Path

MARKERS = (".handoff-requested", ".cap-fired")


def clear_markers(autopilot_dir: Path) -> None:
    """Remove both markers from `autopilot_dir`, independently.

    Absent markers are silent; any other OSError is reported on stderr and
    skipped, so the caller's landed commit is never turned into a failure.
    """
    for name in MARKERS:
        marker = autopilot_dir / name
        try:
            marker.unlink()
        except FileNotFoundError:
            pass
        except OSError as err:
            print(f"autopilot: could not remove {marker}: {err}", file=sys.stderr)
