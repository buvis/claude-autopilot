#!/usr/bin/env python3
"""PostToolUse hook (Bash): note which loop session wrote its `leave` row.

PRD 00211. Every hand-off site ends with `record_dispatch.py handoff ...
--edge leave` as the session's last write before the banner and END TURN.
When that command succeeds under `_AUTOPILOT_LOOP`, this hook writes
`dev/local/autopilot/.session-left` with the session id, and
`guard_skill_after_leave.py` then denies any `autopilot:*` skill call from
the same session: the hand-off ended it, the loop relaunches the next phase.

Observation only: every failure is a silent exit 0, so the hook can never
block the hand-off it records.
"""

from __future__ import annotations

import datetime as _dt
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(
    0,
    str(Path(__file__).resolve().parents[1] / "skills" / "run-autopilot" / "scripts"),
)

from _common import allow, read_input
from _walk_up import find_autopilot_dir

MARKER = ".session-left"
_LEAVE_TOKENS = ("record_dispatch.py handoff", "--edge leave")


def is_leave_row(command: object) -> bool:
    return isinstance(command, str) and all(token in command for token in _LEAVE_TOKENS)


def tool_failed(response: object) -> bool:
    """True when the Bash tool reports the command failed or was cut short.

    No exit code is read: a non-zero exit fires `PostToolUseFailure`, never
    this PostToolUse hook, so `is_error` and `interrupted` are all that remain.
    """
    if not isinstance(response, dict):
        return False
    return bool(response.get("is_error")) or bool(response.get("interrupted"))


def main() -> None:
    if not os.environ.get("_AUTOPILOT_LOOP"):
        allow()
    payload = read_input()
    if payload.get("tool_name") != "Bash":
        allow()
    tool_input = payload.get("tool_input")
    command = tool_input.get("command") if isinstance(tool_input, dict) else None
    if not is_leave_row(command) or tool_failed(payload.get("tool_response")):
        allow()
    session = payload.get("session_id")
    if not isinstance(session, str) or not session:
        allow()
    autopilot_dir = find_autopilot_dir(Path(str(payload.get("cwd") or os.getcwd())))
    if autopilot_dir is None:
        allow()
    record = {
        "session": session,
        "at": _dt.datetime.now(tz=_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    try:
        (autopilot_dir / MARKER).write_text(json.dumps(record) + "\n", encoding="utf-8")
    except OSError:
        pass
    allow()


if __name__ == "__main__":
    main()
