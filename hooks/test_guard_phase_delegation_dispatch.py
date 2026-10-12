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
import time
from pathlib import Path

import pytest

from guard_phase_delegation import is_phase_delegation

HOOKS = Path(__file__).resolve().parent
GUARD = HOOKS / "guard_phase_delegation.py"

MB = 1048576
# Seconds per megabyte the predicate may cost. The harness kills a hook at 5 s,
# so this bound keeps the timeout out of reach until roughly 16 MB of prompt.
BUDGET_S_PER_MB = 0.3

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


def _best_seconds_per_mb(prompt: str) -> float:
    # Best of three, not a mean: the figure being bounded is the predicate's
    # own cost, and a scheduler hiccup on one run is not that cost.
    best = min(_time_predicate(prompt) for _ in range(3))
    return best / (len(prompt) / MB)


def _time_predicate(prompt: str) -> float:
    start = time.perf_counter()
    is_phase_delegation({"prompt": prompt})
    return time.perf_counter() - start


def test_guard_time_per_mb_stays_under_the_baseline() -> None:
    # Called in-process, unlike the dispatch tests above: a subprocess's
    # interpreter start-up would swamp the measurement.
    crafted = "Read work/SKILL.md " + "not " * 262144
    prose = "run the the the " * 65536

    crafted_rate = _best_seconds_per_mb(crafted)
    prose_rate = _best_seconds_per_mb(prose)

    # Printed before the assertions so `pytest -s` shows the real numbers even
    # when one of them fails the budget.
    print(f"guard s/MB crafted={crafted_rate:.4f} prose={prose_rate:.4f}")

    assert crafted_rate < BUDGET_S_PER_MB
    assert prose_rate < BUDGET_S_PER_MB
