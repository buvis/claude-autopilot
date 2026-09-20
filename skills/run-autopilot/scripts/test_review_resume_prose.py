"""Pins PRD 00196's review-gate resume rule: a rotated review-phase rework
session re-enters `references/phase-review.md` and must resume at Phase 6
"Dispatch rework" (this cycle's review file exists and `rework_task_ids`
names an unfinished task) instead of re-reviewing.

Same pattern as the sibling prose suites: read the file once, slice the
window between the cycle skip and the review-skill invocation, assert on
short reword-resistant fragments with a message naming what drifted.
"""

from __future__ import annotations

from pathlib import Path

_PHASE_REVIEW = Path(__file__).resolve().parent.parent / "references" / "phase-review.md"

_CYCLE_SKIP = "**Skip this cycle's review if:**"
_INVOKE = "Invoke `/autopilot:review-work-completion` skill."
_THIRD_SKIP = (
    "**Skip Phases 4 and 5 and resume at Phase 6 \"Dispatch rework\"** when this "
    "cycle's review file exists and `state.rework_task_ids` names a task whose "
    "status is not `completed`"
)


def test_review_gate_resumes_rework_from_the_review_file() -> None:
    text = _PHASE_REVIEW.read_text()
    assert _CYCLE_SKIP in text, f"{_PHASE_REVIEW}: the cycle skip is gone"
    start = text.index(_CYCLE_SKIP)
    assert _INVOKE in text[start:], f"{_PHASE_REVIEW}: the review invocation is gone"
    window = text[start : text.index(_INVOKE, start)]
    assert _THIRD_SKIP in window, (
        f"{_PHASE_REVIEW}: Phase 4 has no third skip {_THIRD_SKIP!r} between the "
        "cycle skip and the review invocation - a rotated rework session would "
        "re-enter Phase 4 and re-review unfinished rework."
    )
    for needle in ("PRD 00196", "every listed task is `completed`", "does not fire"):
        assert needle in window, f"{_PHASE_REVIEW}: the third skip lacks {needle!r}"
