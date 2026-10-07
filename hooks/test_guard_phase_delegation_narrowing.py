"""Narrowing of the phase-delegation guard: contraction double negation,
bounded gap words, and a prohibition inside the SKILL.md-read pattern.

Sibling of test_guard_phase_delegation.py (kept apart for the file size limit).
Each case is one input string and one assertion on `is_phase_delegation`.
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

import pytest

HOOKS = Path(__file__).resolve().parent


def _guard_module():
    sys.path.insert(0, str(HOOKS))
    return importlib.import_module("guard_phase_delegation")


@pytest.mark.parametrize(
    "prompt",
    [
        "Don't hesitate to run the work phase",
        "Doesn't hesitate to run the work phase",
        "Won't hesitate to run the work phase",
        "Don't fail to run the work phase",
        "Doesn't fail to run the work phase",
        "Won't fail to run the work phase",
        "Don't only run the work phase",
        "Doesn't only run the work phase",
        "Won't only run the work phase",
        "Do not hesitate to run the work phase",
        "never fail to execute /autopilot:work",
    ],
)
def test_contraction_before_hesitate_fail_or_only_is_a_double_negation_and_is_denied(prompt: str) -> None:
    assert _guard_module().is_phase_delegation({"prompt": prompt}) is True


def test_contraction_without_hesitate_fail_or_only_stays_a_plain_negation() -> None:
    assert _guard_module().is_phase_delegation({"prompt": "Don't run the work phase"}) is False


@pytest.mark.parametrize(
    "prompt",
    [
        "Tell me what we do in the work phase",
        "Decide what to do about the work phase",
        "Tasks complete in the work phase",
        "Start with the work phase fixtures",
        "Review diff; complete the work phase checklist",
        "Fix the bug. Do tests for the design phase",
        "Do review the work phase diff",
        "Call the work phase reviewer",
        "Start with the work phase review",
        "Start reviewing the design phase",
    ],
)
def test_ordinary_prose_with_a_widened_verb_near_phase_jargon_is_allowed(prompt: str) -> None:
    assert _guard_module().is_phase_delegation({"prompt": prompt}) is False


@pytest.mark.parametrize(
    "prompt",
    [
        "Run the work phase",
        "Run the entire work phase",
        "Start the work phase",
        "Do the work phase",
        "Perform the work phase",
        "Complete the work phase",
        "Launch /autopilot:work",
        "Call /autopilot:plan-tasks",
    ],
)
def test_delegating_phrasing_with_a_widened_verb_stays_denied(prompt: str) -> None:
    assert _guard_module().is_phase_delegation({"prompt": prompt}) is True


def test_prohibition_inside_the_skill_md_read_pattern_is_allowed() -> None:
    prompt = "Read skills/work/SKILL.md and do not perform all tasks"
    assert _guard_module().is_phase_delegation({"prompt": prompt}) is False


def test_skill_md_read_without_a_prohibition_stays_denied() -> None:
    prompt = "Read skills/work/SKILL.md and do all tasks"
    assert _guard_module().is_phase_delegation({"prompt": prompt}) is True
