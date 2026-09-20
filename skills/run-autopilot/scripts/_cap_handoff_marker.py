"""The `.handoff-requested` marker the context-cap hook writes when the
headroom rule fires (PRD 00200), and the reader that tells a marker naming
the current task from one naming an earlier one.

Split out of `autopilot_context_cap_hook.py` to keep that file under the
800-line limit; imported as a sibling module, like `_walk_up`. Stdlib only.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path


def marker_task_id(text: str) -> str:
    """Return the task id a `.handoff-requested` marker names, or "".

    Reads both the JSON object this hook writes and the legacy bare task id
    earlier versions wrote. Task ids are integer strings, so a bare number is
    a legacy task id even though it parses as JSON. Anything else — empty,
    whitespace, a JSON list or null — names no task, so the marker gets
    replaced.
    """
    text = text.strip()
    if not text:
        return ""
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return text
    if isinstance(payload, dict):
        task_id = payload.get("task_id")
        return task_id if isinstance(task_id, str) else ""
    return text if isinstance(payload, int) else ""


def request_handoff(
    autopilot_dir: Path, task_id: str, session_id: str, phase: str
) -> None:
    """Write the `.handoff-requested` marker (one-shot per task).

    Unlike the hard-cap rotation, this is non-destructive: state.json is left
    untouched and no envelope is emitted. `/work` checks the marker at a task
    boundary (after a task commits) and hands off cleanly to a fresh session,
    which resumes the phase with the remaining pending tasks.

    The marker is a JSON object with exactly four fields: the phase the hook
    fired in (step 6.5 honours a marker only in its own phase, PRD 00196), the
    requesting session's id, a UTC stamp, and the task id. A marker (JSON or
    legacy bare id) already naming the task is left byte-identical (redundant
    fire); one naming an earlier task is overwritten. Best-effort: an
    unwritable autopilot dir is swallowed, as on the rotation path.
    """
    marker = autopilot_dir / ".handoff-requested"
    if marker.exists():
        try:
            existing = marker.read_text()
        except OSError:
            return
        if marker_task_id(existing) == task_id:
            return
    payload = {
        "phase": phase,
        "session": session_id,
        "at": datetime.now(timezone.utc).isoformat(),
        "task_id": task_id,
    }
    try:
        marker.write_text(json.dumps(payload))
    except OSError:
        pass
