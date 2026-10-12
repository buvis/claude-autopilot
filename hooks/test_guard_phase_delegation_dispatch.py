"""Pin the per-`subagent_type` dispatch of `guard_phase_delegation.py`: the
`agoge:` persona exemption (and that lookalike types stay checked), plus the
two deny messages - the per-task personas' "rephrase that sentence" wording and
everyone else's "Skill tool in THIS session" wording.

One shared PROMPT is reused across all four tests on purpose: holding the
prompt constant makes `subagent_type` the only variable, so a verdict or a
message that changes can only come from the dispatch rule under test.

The guard runs as a subprocess with a stdin payload, exactly as the harness
invokes it - the same shape as `test_guard_phase_delegation_replay.py`.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

HOOKS = Path(__file__).resolve().parent
GUARD = HOOKS / "guard_phase_delegation.py"

PROMPT = "Run the work phase for PRD 00300."
# The span the guard quotes back for PROMPT, read from its stderr - a literal,
# never recomputed here, so a change to the quoting window fails this module.
SPAN = "Run the work phase for PRD 0"
REASON = "hooks/guard_phase_delegation.py denied this Agent call."


def _run(stdin: str) -> subprocess.CompletedProcess[str]:
    env = {"PATH": "/usr/bin:/bin", "HOME": str(Path.home()), "_AUTOPILOT_LOOP": "4242"}
    return subprocess.run(
        [sys.executable, str(GUARD)],
        input=stdin,
        capture_output=True,
        text=True,
        env=env,
    )


def _agent_payload(tool_input: dict) -> str:
    return json.dumps(
        {
            "session_id": "11111111-2222-3333-4444-555555555555",
            "tool_name": "Agent",
            "tool_input": tool_input,
        },
    )


def _dispatch(subagent_type: str | None) -> subprocess.CompletedProcess[str]:
    tool_input = {"prompt": PROMPT}
    if subagent_type is not None:
        tool_input["subagent_type"] = subagent_type
    return _run(_agent_payload(tool_input))


@pytest.mark.parametrize(
    "subagent_type",
    [
        "agoge:walter",
        "agoge:wendy",
        "agoge:trudy",
        "agoge:heidi",
        "agoge:peggy",
        "agoge:olivia",
        "agoge:judy",
    ],
)
def test_agoge_personas_are_exempt(subagent_type: str) -> None:
    result = _dispatch(subagent_type)
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize(
    "subagent_type",
    ["agoge", "walter", "agoge-walter", "xagoge:walter"],
)
def test_agoge_lookalike_types_are_still_checked(subagent_type: str) -> None:
    result = _dispatch(subagent_type)
    assert result.returncode == 2, result.stderr


@pytest.mark.parametrize(
    "subagent_type",
    [
        "autopilot:ivan",
        "autopilot:tess",
        "autopilot:devon",
        "autopilot:worker-sonnet",
        "autopilot:worker-opus",
    ],
)
def test_per_task_persona_refusal_says_rephrase_and_quotes_the_match(
    subagent_type: str,
) -> None:
    result = _dispatch(subagent_type)
    assert result.returncode == 2, result.stderr
    assert "rephrase that sentence" in result.stderr
    assert f'"{SPAN}"' in result.stderr
    assert REASON in result.stderr
    assert "Matched" not in result.stderr


@pytest.mark.parametrize("subagent_type", ["general-purpose", "Explore", None])
def test_other_refusals_keep_the_skill_tool_text_and_quote_the_match(
    subagent_type: str | None,
) -> None:
    result = _dispatch(subagent_type)
    assert result.returncode == 2, result.stderr
    assert "with the Skill tool in THIS session" in result.stderr
    assert f'Matched: "{SPAN}"' in result.stderr
    assert REASON in result.stderr
