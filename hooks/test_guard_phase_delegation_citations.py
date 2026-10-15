"""PRD 00307: a phase name inside a longer quoted or wrapped run is a citation.

Also pins the `_ordered_to_follow` negation floor (a negation in the clause
before the follow verb must not excuse it) and the enumerated agoge roster
(only the real personas are exempt, not anything spelled `agoge:*`).
"""

from __future__ import annotations

import importlib
import inspect
import sys
from pathlib import Path

import pytest

HOOKS = Path(__file__).resolve().parent
GP = "general-purpose"


def _guard_module():
    sys.path.insert(0, str(HOOKS))
    return importlib.import_module("guard_phase_delegation")


def _find(prompt: str, subagent_type: str | None = GP) -> str | None:
    tool_input = {"prompt": prompt}
    if subagent_type is not None:
        tool_input["subagent_type"] = subagent_type
    return _guard_module().find_phase_delegation(tool_input)


def test_backtick_run_opening_before_the_name_is_a_citation() -> None:
    assert _find("The report line reads `run plan-tasks for PRD 00300` verbatim.") is None


def test_double_quote_run_is_a_citation() -> None:
    assert _find('The log line reads "run plan-tasks for PRD 00300" verbatim.') is None


def test_paren_aside_is_a_citation() -> None:
    assert _find("The fallback (run plan-tasks for PRD 00300) sits in the old docs.") is None


@pytest.mark.parametrize(
    "prompt",
    [
        "Run `plan-tasks` for PRD 00300.",
        'Run "plan-tasks" for PRD 00300.',
        "Run (plan-tasks) for PRD 00300.",
        "Run `/autopilot:work` for PRD 00300.",
    ],
    ids=["backtick", "double-quote", "paren", "backtick-slash-skill"],
)
def test_wrapper_closing_right_after_the_name_still_counts(prompt: str) -> None:
    # A name wrapped on its own (open right before, close right after) is a
    # label, not a citation: it still anchors as a delegation, as today.
    assert _find(prompt) is not None


def test_already_closed_aside_before_the_name_is_not_a_citation() -> None:
    # The "(an aside)" closes before plan-tasks; the later, unrelated ")" must
    # not make plan-tasks read as wrapped.
    assert _find("Note (an aside) then also run plan-tasks for PRD 00300 cleanup)") is not None


_CORPUS = [
    (
        "re-invokes `/autopilot:work, which then",
        None,
        "The orchestrator automatically re-invokes `/autopilot:work, which then proceeds to the next task`.",
    ),
    (
        "d reports `design-solution: <p",
        GP,
        "The subagent then prints and reports `design-solution: <prd-stem>` followed by the doc path.",
    ),
    (
        '.assertIn("design-solution: <p',
        GP,
        'Write a test that checks self.assertIn("design-solution: <prd-stem>", report) for the exit line.',
    ),
    (
        "ine reads `design-solution: <p",
        GP,
        "The first line reads `design-solution: <prd-stem>` exactly.",
    ),
    (
        "parse and plan-tasks) looks fo",
        GP,
        "The dispatcher (which handles catchup, design, parse and plan-tasks) looks for the next phase.",
    ),
    (
        "`Run the work phase for PRD 0",
        "autopilot:worker-opus",
        "The fixture prompt text is `Run the work phase for PRD 00300, every task` verbatim.",
    ),
]


@pytest.mark.parametrize(
    ("span", "subagent_type", "prompt"),
    _CORPUS,
    ids=["re-invokes-work", "reports-design", "assert-in-design", "line-reads-design", "paren-plan-tasks", "fixture-work-phase"],
)
def test_six_corpus_dispatches_are_allowed(span: str, subagent_type: str | None, prompt: str) -> None:
    assert span in prompt
    assert _find(prompt, subagent_type) is None


def test_negation_in_previous_clause_does_not_excuse_follow() -> None:
    assert _find("Read skills/work/SKILL.md, do not stop, then follow it for every task.") is not None


def test_negation_inside_the_verb_clause_still_excuses() -> None:
    assert _find("Read skills/work/SKILL.md and do not follow it for every task.") is None


def test_ordered_to_follow_uses_bisect() -> None:
    source = inspect.getsource(_guard_module()._ordered_to_follow)
    assert "bisect_left" in source
    assert "_negated(text, end, match.start())" not in source


_AGOGE_PROMPT = "Run /autopilot:work for PRD 00300, every task."


@pytest.mark.parametrize(
    "subagent_type",
    [
        "agoge:olivia", "agoge:walter", "agoge:heidi", "agoge:judy",
        "agoge:wendy", "agoge:peggy", "agoge:trudy",
    ],
)
def test_each_agoge_persona_is_exempt(subagent_type: str) -> None:
    # Control: the same prompt is a delegation for a non-exempt agent.
    assert _find(_AGOGE_PROMPT, GP) is not None
    assert _find(_AGOGE_PROMPT, subagent_type) is None


@pytest.mark.parametrize("subagent_type", ["agoge:", "agoge:not-a-real-agent"], ids=["bare-prefix", "unknown-name"])
def test_unknown_agoge_prefix_is_not_exempt(subagent_type: str) -> None:
    assert _find(_AGOGE_PROMPT, subagent_type) is not None
