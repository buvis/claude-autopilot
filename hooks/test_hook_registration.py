"""PRD 00211 and PRD 00213: the leave-row guard pair (00211) and the live-lane
Stop guard (00213) are registered in the plugin's own hooks/hooks.json on the
events their scripts handle.

The pack-wide registration table lives in
skills/run-autopilot/scripts/test_review_coverage_hook_registration.py; this
file is the PRDs' named pin for the three hooks they add, runnable on its own:

    uv run --no-project --with pytest python -m pytest -q \\
      hooks/test_guard_skill_after_leave.py \\
      hooks/test_guard_stop_on_live_lanes.py hooks/test_hook_registration.py
"""

from __future__ import annotations

import json
from pathlib import Path

HOOKS_JSON = Path(__file__).resolve().parent / "hooks.json"


def _blocks(event: str) -> list[dict]:
    data = json.loads(HOOKS_JSON.read_text(encoding="utf-8"))
    return data["hooks"].get(event, [])


def _commands(event: str, matcher: str | None) -> list[str]:
    return [
        hook["command"]
        for block in _blocks(event)
        if block.get("matcher") == matcher
        for hook in block.get("hooks", [])
    ]


def test_note_session_leave_runs_after_every_bash_call() -> None:
    commands = _commands("PostToolUse", "Bash")
    assert any(c.endswith("/hooks/note_session_leave.py") for c in commands), commands


def test_guard_skill_after_leave_runs_before_every_skill_call() -> None:
    commands = _commands("PreToolUse", "Skill")
    assert any(c.endswith("/hooks/guard_skill_after_leave.py") for c in commands), commands


def test_guard_stop_on_live_lanes_runs_on_stop() -> None:
    commands = _commands("Stop", None)
    assert any(c.endswith("/hooks/guard_stop_on_live_lanes.py") for c in commands), commands


def test_both_registrations_point_at_pack_relative_files_that_exist() -> None:
    pack = HOOKS_JSON.parent.parent
    names = (
        "/hooks/note_session_leave.py",
        "/hooks/guard_skill_after_leave.py",
        "/hooks/guard_stop_on_live_lanes.py",
    )
    commands = [
        c
        for c in _commands("PostToolUse", "Bash")
        + _commands("PreToolUse", "Skill")
        + _commands("Stop", None)
        if c.endswith(names)
    ]
    assert len(commands) == 3, commands  # all three new hooks, never vacuously green
    for command in commands:
        target = command.split()[-1]
        assert target.startswith("${CLAUDE_PLUGIN_ROOT}/"), command
        assert (pack / target.removeprefix("${CLAUDE_PLUGIN_ROOT}/")).is_file(), command


def test_each_guard_hook_has_a_short_timeout() -> None:
    for event, matcher, name in (
        ("PostToolUse", "Bash", "note_session_leave.py"),
        ("PreToolUse", "Skill", "guard_skill_after_leave.py"),
        ("Stop", None, "guard_stop_on_live_lanes.py"),
    ):
        hooks = [
            hook
            for block in _blocks(event)
            if block.get("matcher") == matcher
            for hook in block.get("hooks", [])
            if hook["command"].endswith(name)
        ]
        assert len(hooks) == 1, (event, matcher, name)
        assert "timeout" in hooks[0] and hooks[0]["timeout"] <= 5, hooks[0]
