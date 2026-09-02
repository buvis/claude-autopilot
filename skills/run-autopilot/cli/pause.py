"""cli/pause.py - the operator pause marker (PRD 00106).

Ports the wrapper's pause branch (PRD 00014): `touch
<ap_dir>/pause-requested` is the sanctioned "let me in" signal, honored
at the next session boundary. The marker is consumed so a later loop
run starts normally; the loop then prints the resume runbook, notifies
once, and exits 0 (stall-not-pause policy, PRD 00017 - the loop stops
spawning without wedging).
"""

from __future__ import annotations

import json
from pathlib import Path

MARKER = "pause-requested"
STAMP = "paused-by-operator"


def stand_down_reason(autopilot_dir: Path, since: float) -> str | None:
    """The reason in a marker written at or after `since` (the session's
    start); None when no such marker exists. A marker the session itself
    wrote is a stand-down (PRD 00172): it found another session owning
    its PRD and touched nothing else. Empty or non-JSON content is a
    stand-down with no reason - an operator `touch` mid-session lands
    here too."""
    path = autopilot_dir / MARKER
    try:
        if int(path.stat().st_mtime) < int(since):
            return None
        text = path.read_text(encoding="utf-8")
    except OSError:
        return None
    try:
        data = json.loads(text)
    except ValueError:
        return "no reason given"
    reason = data.get("reason") if isinstance(data, dict) else None
    if isinstance(reason, str) and reason.strip():
        return reason.strip()
    return "no reason given"


def consume_pause(autopilot_dir: Path) -> bool:
    """True when the pause marker existed; it is removed either way."""
    try:
        (autopilot_dir / MARKER).unlink()
        return True
    except FileNotFoundError:
        return False
    except OSError:
        return False


def stamp_paused(autopilot_dir: Path) -> None:
    """Leave the trace tracon renders as "paused".

    The pause exit happens BEFORE a session runs, so it appends no metrics
    row - and without this stamp the overview reads the loop as work left
    behind with nothing to relaunch it and paints it "orphaned", which is
    what a dropped batch looks like, not a deliberate stop."""
    try:
        (autopilot_dir / STAMP).touch()
    except OSError:
        pass


def clear_paused(autopilot_dir: Path) -> None:
    """Drop the stamp: this loop is about to run a session."""
    try:
        (autopilot_dir / STAMP).unlink(missing_ok=True)
    except OSError:
        pass
