"""Tests binding the live text of the adversarial Tess/Devon round cap — the
one-round-cap prose that PRD's task 1 added to
${CLAUDE_PLUGIN_ROOT}/skills/work/references/adversarial-test-prompt.md and
${CLAUDE_PLUGIN_ROOT}/skills/work/SKILL.md.

Mirrors test_dispatch_prose.py's pattern for pinning a skill file's prose:
resolve each target file's path relative to this file, read it once, and
assert on short, reword-resistant substrings, each with a failure message
naming what drifted. Presence assertions are scoped to the section that is
supposed to carry them, via `_section` below, so the pin still catches text
that has moved out of its section rather than only text that has vanished
outright.
"""

from __future__ import annotations

from pathlib import Path

_WORK_DIR = Path(__file__).resolve().parent.parent
_SKILL_MD = _WORK_DIR / "SKILL.md"
_SKILL_TEXT = _SKILL_MD.read_text()

_ADVERSARIAL_TEST_PROMPT = _WORK_DIR / "references" / "adversarial-test-prompt.md"
_ADVERSARIAL_TEXT = _ADVERSARIAL_TEST_PROMPT.read_text()


def _section(text: str, path: Path, start_anchor: str, end_anchor: str) -> str:
    """Slice `text` from `start_anchor` up to `end_anchor`.

    Asserts both anchors are present first, naming `path` and the missing
    anchor, so a drifted heading fails loudly instead of raising a bare
    `ValueError: substring not found`.
    """
    assert start_anchor in text, (
        f"{path}: expected section anchor {start_anchor!r} — not found."
    )
    start = text.index(start_anchor)
    assert end_anchor in text[start:], (
        f"{path}: expected section anchor {end_anchor!r} after "
        f"{start_anchor!r} — not found."
    )
    end = text.index(end_anchor, start)
    return text[start:end]


def test_outcome_table_caps_the_loop_at_one_round() -> None:
    outcomes = _section(
        _ADVERSARIAL_TEXT,
        _ADVERSARIAL_TEST_PROMPT,
        "**Outcomes:**",
        "## Prompt Template",
    )
    for needle in (
        "Max 1 Tess/Devon round",
        "2 Devon dispatches, 1 strengthen-side Tess dispatch",
    ):
        assert needle in outcomes, (
            f"{_ADVERSARIAL_TEST_PROMPT}: expected the outcome table to say "
            f"{needle!r} — not found. The one-round cap appears to have "
            "drifted or been removed."
        )

    # Absence checks stay whole-file, unlike the presence checks above:
    # whole-file matching is strictly stronger for an absence assertion,
    # since scoping it to a section would let the old wording reappear
    # anywhere else in the file and still pass. Do not scope these.
    for needle in ("Max 2 Tess/Devon rounds", "2 A/C rounds exhausted"):
        assert needle not in _ADVERSARIAL_TEXT, (
            f"{_ADVERSARIAL_TEST_PROMPT}: found {needle!r} — the outcome "
            "table has regressed to the old two-round cap."
        )


def test_total_tess_budget_is_four() -> None:
    step_2_8 = _section(_SKILL_TEXT, _SKILL_MD, "### 2.8.", "### 2.85.")
    for needle in ("max 4 dispatches", "1 adversarial strengthen"):
        assert needle in step_2_8, (
            f"{_SKILL_MD}: expected {needle!r} — not found. The total Tess "
            "dispatch budget appears to have drifted or been removed."
        )

    # Whole-file on purpose: an absence assertion scoped to step 2.8 would
    # let "max 5 dispatches" reappear anywhere else in the file and still
    # pass. Whole-file is strictly stronger here, so do not scope it.
    assert "max 5 dispatches" not in _SKILL_TEXT, (
        f"{_SKILL_MD}: found 'max 5 dispatches' — the Tess dispatch budget "
        "has regressed to the old five-dispatch total."
    )


def test_step_2_85_states_devons_per_task_maximum() -> None:
    step_2_85 = _section(_SKILL_TEXT, _SKILL_MD, "### 2.85.", "### 2.9.")
    needle = "Devon runs at most twice per task"

    assert needle in step_2_85, (
        f"{_SKILL_MD}: expected step 2.85 to state {needle!r} — not found. "
        "The per-task Devon maximum appears to have drifted or been removed."
    )
