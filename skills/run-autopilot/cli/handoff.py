#!/usr/bin/env python3
"""handoff.py - clearing the session markers a lifecycle commit leaves behind.

Exposes:
    clear_markers(autopilot_dir) -> None
        Remove `.handoff-requested` and `.cap-fired` from the directory
        holding state.json. Absent is not an error, and a marker that cannot
        be removed is skipped rather than raised: this always runs AFTER the
        commit it follows, so it must never turn a landed transition into a
        failure. Each marker is removed in its OWN try block, so a failure on
        one cannot skip the other.

Call it only after a commit that ends the current PRD or phase (phase-done's
tasks_done/converged/more_prds/drained, reset-prd, a successful stall or
park). A commit that leaves the session on the same phase and PRD (review +
rework) keeps its markers: that session continues, so a pending handoff or
cap request is still pending.
"""

from __future__ import annotations

from pathlib import Path

MARKERS = (".handoff-requested", ".cap-fired")


def clear_markers(autopilot_dir: Path) -> None:
    """Remove both markers from `autopilot_dir`, silently and independently."""
    for name in MARKERS:
        try:
            (autopilot_dir / name).unlink()
        except OSError:
            pass
