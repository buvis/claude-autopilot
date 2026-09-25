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
    # Exact python3 command in the matcher-less Stop block, after the coverage hook.
    blocks = [b for b in _blocks("Stop") if b.get("matcher") is None]
    assert len(blocks) == 1, blocks
    hooks = blocks[0].get("hooks", [])
    commands = [hook["command"] for hook in hooks]
    guard = [i for i, c in enumerate(commands) if "guard_stop_on_live_lanes.py" in c]
    coverage = [i for i, c in enumerate(commands) if "review_coverage_hook.py" in c]
    assert len(guard) == 1 and len(coverage) == 1, commands
    entry = hooks[guard[0]]
    assert entry["command"] == (
        "python3 ${CLAUDE_PLUGIN_ROOT}/hooks/guard_stop_on_live_lanes.py"
    ), entry
    assert entry["type"] == "command", entry
    assert coverage[0] < guard[0], commands


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
        timeout = hooks[0].get("timeout")
        assert isinstance(timeout, int) and not isinstance(timeout, bool), hooks[0]
        assert 0 < timeout <= 5, hooks[0]
