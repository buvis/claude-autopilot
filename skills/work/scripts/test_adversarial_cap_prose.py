"""Tests binding the live text of the adversarial Tess/Devon round cap — the
one-round-cap prose that PRD's task 1 added to
${CLAUDE_PLUGIN_ROOT}/skills/work/references/adversarial-test-prompt.md and
${CLAUDE_PLUGIN_ROOT}/skills/work/SKILL.md.

Mirrors test_dispatch_prose.py's pattern for pinning a skill file's prose:
resolve each target file's path relative to this file, read it once, and
assert on short, reword-resistant substrings, each with a failure message
naming what drifted.
"""

from __future__ import annotations

from pathlib import Path

_SKILL_MD = Path(__file__).resolve().parent.parent / "SKILL.md"
_SKILL_TEXT = _SKILL_MD.read_text()

_ADVERSARIAL_TEST_PROMPT = (
    Path(__file__).resolve().parent.parent
    / "references"
    / "adversarial-test-prompt.md"
)
_ADVERSARIAL_TEXT = _ADVERSARIAL_TEST_PROMPT.read_text()


def test_outcome_table_caps_the_loop_at_one_round() -> None:
    for needle in (
        "Max 1 Tess/Devon round",
        "2 Devon dispatches, 1 strengthen-side Tess dispatch",
    ):
        assert needle in _ADVERSARIAL_TEXT, (
            f"{_ADVERSARIAL_TEST_PROMPT}: expected the outcome table to say "
            f"{needle!r} — not found. The one-round cap appears to have "
            "drifted or been removed."
        )

    for needle in ("Max 2 Tess/Devon rounds", "2 A/C rounds exhausted"):
        assert needle not in _ADVERSARIAL_TEXT, (
            f"{_ADVERSARIAL_TEST_PROMPT}: found {needle!r} — the outcome "
            "table has regressed to the old two-round cap."
        )


def test_total_tess_budget_is_four() -> None:
    for needle in ("max 4 dispatches", "1 adversarial strengthen"):
        assert needle in _SKILL_TEXT, (
            f"{_SKILL_MD}: expected {needle!r} — not found. The total Tess "
            "dispatch budget appears to have drifted or been removed."
        )

    assert "max 5 dispatches" not in _SKILL_TEXT, (
        f"{_SKILL_MD}: found 'max 5 dispatches' — the Tess dispatch budget "
        "has regressed to the old five-dispatch total."
    )


def test_step_2_85_states_devons_per_task_maximum() -> None:
    needle = "Devon runs at most twice per task"

    assert needle in _SKILL_TEXT, (
        f"{_SKILL_MD}: expected step 2.85 to state {needle!r} — not found. "
        "The per-task Devon maximum appears to have drifted or been removed."
    )
