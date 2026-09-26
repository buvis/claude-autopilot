#!/usr/bin/env python3
"""cli/handoff_request.py - the wrapper's cap warning (2026-09-26).

The context-cap hook hands a session off at a task boundary when its usage
or call budget runs low, but the wrapper's wall-clock cap was invisible to
the session: at 7200s it SIGTERM'd a build session mid-task, with task 3's
code committed and its attempt record never written. The watchdog now calls
`request_wrapper_handoff` when the session enters its warning window. It
resolves what the hook gets on stdin (the phase, the in-flight task, the
session id) from state.json and the session log, then writes the marker
through the hook's own writer (`scripts/_cap_handoff_marker.py`), so there
is exactly one marker format for `/work` step 6.5 to read.

Best effort by construction: an unreadable state.json or log yields the
string "unknown", and a marker that did not land is one stderr line, never
an exception into the watchdog.
"""

from __future__ import annotations

import importlib.util
import json
import re
import sys
from pathlib import Path

_SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
_WRITER = _SCRIPTS_DIR / "_cap_handoff_marker.py"
MARKER = ".handoff-requested"
_SESSION_RE = re.compile(r'"session_id":"([0-9a-f-]{36})"')


def _marker_writer():
    spec = importlib.util.spec_from_file_location("_cap_handoff_marker", _WRITER)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module.request_handoff


def _phase_and_task(autopilot_dir: Path) -> tuple[str, str]:
    """(phase, in-flight task id) from state.json; "build" / "unknown" when
    absent or unreadable. Every value is a string, the marker's contract."""
    try:
        state = json.loads((autopilot_dir / "state.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return "build", "unknown"
    if not isinstance(state, dict):
        return "build", "unknown"
    phase = state.get("phase")
    phase = phase if isinstance(phase, str) and phase else "build"
    tasks = state.get("tasks")
    for task in tasks if isinstance(tasks, list) else []:
        if isinstance(task, dict) and task.get("status") == "in_progress":
            task_id = task.get("id")
            if isinstance(task_id, (str, int)) and str(task_id):
                return phase, str(task_id)
    return phase, "unknown"


def _session_id(log_path: Path) -> str:
    """The session id from the log's init event, "unknown" until it is there."""
    try:
        with open(log_path, encoding="utf-8", errors="replace") as log:
            for line in log:
                match = _SESSION_RE.search(line)
                if match:
                    return match.group(1)
    except OSError:
        pass
    return "unknown"


def request_wrapper_handoff(autopilot_dir: Path) -> dict | None:
    """Resolve the marker's inputs from disk and write it through the hook's
    writer; return the resolved fields, or None when no marker is on disk."""
    phase, task_id = _phase_and_task(autopilot_dir)
    session = _session_id(autopilot_dir / "last-session.log")
    try:
        _marker_writer()(autopilot_dir, task_id, session, phase)
    except Exception as err:  # the watchdog must keep its cap either way
        print(f"autoclaude: handoff marker writer failed: {err}", file=sys.stderr)
        return None
    if not (autopilot_dir / MARKER).is_file():
        print(
            f"autoclaude: could not write the handoff marker in {autopilot_dir}",
            file=sys.stderr,
        )
        return None
    return {"phase": phase, "session": session, "task_id": task_id}
