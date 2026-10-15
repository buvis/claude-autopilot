#!/usr/bin/env python3
"""markers.py - check/clear for the autopilot handoff marker files.

Mirrors cli.handoff.MARKERS' own two names (`handoff-requested`, `cap-fired`)
mapped to `.handoff-requested` and `.cap-fired` beside state.json.
"""

from __future__ import annotations

from pathlib import Path

MARKERS = {
    "handoff-requested": ".handoff-requested",
    "cap-fired": ".cap-fired",
}


def check(autopilot_dir: Path, names: list[str]) -> dict[str, bool]:
    return {name: (autopilot_dir / MARKERS[name]).exists() for name in names}


def clear(autopilot_dir: Path, names: list[str]) -> None:
    for name in names:
        (autopilot_dir / MARKERS[name]).unlink(missing_ok=True)
