"""Contract test: the pack's hooks are wired in its OWN hooks/hooks.json.

History. PRD 00071 moved the per-handler registrations out of settings.json into
`~/.claude/hooks/dispatch.py`'s ROUTES table, and this test followed them there.
PRD 00144 extracted the pack into a plugin, at which point reading `~/.claude`
from here became a plugin inspecting a personal config file it does not own —
and the test broke outright, because its `parents[3]` now resolves to the pack
root rather than `~/.claude`. All four hooks are registered in the plugin's own
`hooks/hooks.json` now, so that manifest is what this binds.

The coverage Stop hook is a backstop — if it is wired nowhere, a session ending
at a review handoff with incomplete coverage would not be blocked. The stop and
yield-clear hooks were deleted with the headless-loop conversion (PRD 00014); a
resurrected registration would point at a nonexistent script on every Stop. This
test fails loud if either invariant breaks, or if hooks.json is malformed.

Stdlib-only unittest.
"""

from __future__ import annotations

import json
import unittest
from pathlib import Path

# scripts -> run-autopilot -> skills -> pack root.
_PACK_ROOT = Path(__file__).resolve().parents[3]
_HOOKS_JSON = _PACK_ROOT / "hooks" / "hooks.json"

_COVERAGE_HOOK_NAME = "review_coverage_hook.py"
_RETIRED_HOOKS = ("autopilot_stop_hook.py", "autopilot_yield_clear_hook.py")

# Every handler the plugin owns, and the event each must be registered on.
# dispatch.py carries a PLUGIN_OWNED set that must stay the complement of this;
# routing one of these in both places fires it twice for the same tool call.
_EXPECTED_REGISTRATIONS = {
    "enforce_prd_location.py": "PreToolUse",
    "autopilot_context_cap_hook.py": "PostToolUse",
    "validate_state_json_hook.py": "PostToolUse",
    _COVERAGE_HOOK_NAME: "Stop",
}


def _commands_by_event() -> dict[str, list[str]]:
    data = json.loads(_HOOKS_JSON.read_text(encoding="utf-8"))
    out: dict[str, list[str]] = {}
    for event, blocks in data.get("hooks", {}).items():
        for block in blocks:
            for hook in block.get("hooks", []):
                command = hook.get("command")
                if command is not None:
                    out.setdefault(event, []).append(command)
    return out


class ReviewCoverageHookRegistrationTests(unittest.TestCase):
    def test_hooks_json_is_valid(self) -> None:
        # Must parse — a malformed manifest silently unregisters every hook.
        json.loads(_HOOKS_JSON.read_text(encoding="utf-8"))

    def test_coverage_hook_registered_on_stop(self) -> None:
        stop = " ".join(_commands_by_event().get("Stop", []))
        self.assertIn(
            _COVERAGE_HOOK_NAME,
            stop,
            "review_coverage_hook.py must be registered on Stop in "
            "hooks/hooks.json; the coverage Stop hook is a backstop - if it is "
            "wired nowhere, a session ending at a review handoff with "
            "incomplete coverage would not be blocked",
        )

    def test_every_plugin_owned_handler_is_registered_on_its_event(self) -> None:
        commands = _commands_by_event()
        for script, event in _EXPECTED_REGISTRATIONS.items():
            self.assertIn(
                script,
                " ".join(commands.get(event, [])),
                f"{script} must be registered on {event} in hooks/hooks.json; "
                f"~/.claude/hooks/dispatch.py no longer routes it, so an "
                f"absent entry here means it never runs",
            )

    def test_registered_commands_point_at_files_that_exist(self) -> None:
        # A registration naming a moved or deleted script fails on every hook
        # firing, and the harness surfaces that as a hook error, not as ours.
        for event, commands in _commands_by_event().items():
            for command in commands:
                target = command.split()[-1]
                self.assertTrue(
                    target.startswith("${CLAUDE_PLUGIN_ROOT}/"),
                    f"{event} command is not pack-relative: {command!r}",
                )
                resolved = _PACK_ROOT / target.removeprefix("${CLAUDE_PLUGIN_ROOT}/")
                self.assertTrue(
                    resolved.is_file(),
                    f"{event} registration points at a missing file: {resolved}",
                )

    def test_retired_orchestration_hooks_not_registered(self) -> None:
        # PRD 00014 deleted these scripts; a registration would fail every Stop.
        every_command = " ".join(
            command
            for commands in _commands_by_event().values()
            for command in commands
        )
        for retired in _RETIRED_HOOKS:
            self.assertNotIn(
                retired,
                every_command,
                f"{retired} was retired by PRD 00014 and must not be "
                "registered in hooks/hooks.json",
            )


if __name__ == "__main__":
    unittest.main()
