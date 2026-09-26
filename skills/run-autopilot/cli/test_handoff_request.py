"""cli/handoff_request.py: the wrapper's cap warning writes the same
`.handoff-requested` marker the context-cap hook writes, so /work hands off
at the next task boundary instead of dying at the wall-clock cap (2026-09-26:
a two-hour opus session was SIGTERM'd mid-task, its attempt record unwritten).
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from cli.handoff_request import request_wrapper_handoff

SESSION = "0123abcd-0000-4000-8000-000000000001"
INIT = f'{{"type":"system","subtype":"init","session_id":"{SESSION}","model":"m"}}\n'


def _autopilot_dir(tmp_path: Path, state: dict | None, log: str | None) -> Path:
    ap = tmp_path / "dev/local/autopilot"
    ap.mkdir(parents=True)
    if state is not None:
        (ap / "state.json").write_text(json.dumps(state))
    if log is not None:
        (ap / "last-session.log").write_text(log)
    return ap


def _marker(ap: Path) -> dict:
    return json.loads((ap / ".handoff-requested").read_text())


def test_marker_carries_phase_session_time_and_in_flight_task(tmp_path):
    state = {
        "phase": "build",
        "tasks": [{"id": "1", "status": "completed"}, {"id": "3", "status": "in_progress"}],
    }
    ap = _autopilot_dir(tmp_path, state, INIT)
    resolved = request_wrapper_handoff(ap)
    assert resolved == {"phase": "build", "session": SESSION, "task_id": "3"}
    marker = _marker(ap)
    assert {k: marker[k] for k in ("phase", "session", "task_id")} == resolved
    assert datetime.fromisoformat(marker["at"]).tzinfo is not None
    assert all(isinstance(value, str) for value in marker.values())


def test_missing_state_and_log_fall_back_to_unknowns(tmp_path):
    ap = _autopilot_dir(tmp_path, None, None)
    resolved = request_wrapper_handoff(ap)
    assert resolved == {"phase": "build", "session": "unknown", "task_id": "unknown"}
    assert _marker(ap)["task_id"] == "unknown"


def test_review_phase_without_a_task_still_writes_a_string_task_id(tmp_path):
    state = {"phase": "review", "tasks": [{"id": "1", "status": "completed"}]}
    ap = _autopilot_dir(tmp_path, state, INIT)
    resolved = request_wrapper_handoff(ap)
    assert resolved["phase"] == "review"
    assert resolved["task_id"] == "unknown"
    assert _marker(ap)["phase"] == "review"


def test_a_marker_the_hook_wrote_for_the_same_task_is_left_byte_identical(tmp_path):
    state = {"phase": "build", "tasks": [{"id": "2", "status": "in_progress"}]}
    ap = _autopilot_dir(tmp_path, state, INIT)
    earlier = '{"phase":"build","session":"hook","at":"earlier","task_id":"2"}'
    (ap / ".handoff-requested").write_text(earlier)
    request_wrapper_handoff(ap)
    assert (ap / ".handoff-requested").read_text() == earlier


def test_a_failure_never_raises(tmp_path, capsys):
    missing = tmp_path / "no-such-dir"
    assert request_wrapper_handoff(missing) is None
    assert "handoff marker" in capsys.readouterr().err
