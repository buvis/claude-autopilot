#!/usr/bin/env python3
"""PreToolUse hook (Skill): deny an autopilot skill call from a session that
already handed off.

PRD 00211. Measured 2026-09-20: a build session wrote its card, brief and
`leave` row, printed the hand-off banner and, in the same assistant message,
called `Skill autopilot:run-autopilot` again - the whole review cycle then ran
inside the build session (503K context, cap hook unguarded, no Watcher). The
prose ("print the banner and end the turn") did not hold; this guard does.

Denies (exit 2, reason on stderr) iff `_AUTOPILOT_LOOP` is set, the tool is
`Skill`, the requested skill is `autopilot:*` or `git-ferry:catchup`, and
`dev/local/autopilot/.session-left` names THIS session (written by
`note_session_leave.py`). A marker from another session never denies; a
malformed marker passes (the guard is a backstop, the prose still says STOP).
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(
    0,
    str(Path(__file__).resolve().parents[1] / "skills" / "run-autopilot" / "scripts"),
)

from _common import allow, block, read_input
from _walk_up import find_autopilot_dir

MARKER = ".session-left"
_GUARDED_PREFIX = "autopilot:"
_GUARDED_EXACT = ("git-ferry:catchup",)


def guarded_skill(skill: object) -> bool:
    return isinstance(skill, str) and (
        skill.startswith(_GUARDED_PREFIX) or skill in _GUARDED_EXACT
    )


def left_at(autopilot_dir: Path, session: str) -> str | None:
    """The marker's `at` when it names `session`, else None."""
    try:
        record = json.loads((autopilot_dir / MARKER).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(record, dict) or record.get("session") != session:
        return None
    at = record.get("at")
    return at if isinstance(at, str) else "an earlier call"


def main() -> None:
    if not os.environ.get("_AUTOPILOT_LOOP"):
        allow()
    payload = read_input()
    if payload.get("tool_name") != "Skill":
        allow()
    tool_input = payload.get("tool_input")
    skill = tool_input.get("skill") if isinstance(tool_input, dict) else None
    if not guarded_skill(skill):
        allow()
    session = payload.get("session_id")
    if not isinstance(session, str) or not session:
        allow()
    autopilot_dir = find_autopilot_dir(Path(str(payload.get("cwd") or os.getcwd())))
    if autopilot_dir is None:
        allow()
    at = left_at(autopilot_dir, session)
    if at is None:
        allow()
    block(
        f"autopilot: this session wrote its leave row at {at}; the hand-off "
        f"ended it. End the turn now - do not invoke {skill}. The loop "
        "relaunches the next phase from state.json."
    )


if __name__ == "__main__":
    main()
