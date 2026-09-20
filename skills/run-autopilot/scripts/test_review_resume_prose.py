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


def test_resume_drops_completed_ids_and_keeps_a_sweep_on_its_finalize_path() -> None:
    # Review 1 of PRD 00196: rework mode re-runs every listed id whatever its
    # status, and a rotated Tail sweep must not re-enter a rework cycle.
    text = _PHASE_REVIEW.read_text()
    window = text[text.index(_CYCLE_SKIP) : text.index(_INVOKE)]
    for needle in (
        "drop every id whose task is already `completed` from `state.rework_task_ids`",
        "must not be implemented twice",
        "[D{cycle}] Tail sweep",
        "resume at Tail sweep step 3",
        "reopen a converged cycle",
    ):
        assert needle in window, f"{_PHASE_REVIEW}: the third skip lacks {needle!r}"
    sweep = text[text.index("### Tail sweep") : text.index("**3. Dispatch.**")]
    assert "[D{cycle}] Tail sweep: <theme>" in sweep, (
        f"{_PHASE_REVIEW}: Tail sweep step 2 no longer names its task with the "
        "`Tail sweep` prefix the resume rule reads."
    )


def test_escalation_resets_the_status_before_appending_the_rework_id() -> None:
    # Review 2 of PRD 00196: the resume rule drops listed ids whose task is
    # still `completed`, so the status reset must land before the append.
    text = _PHASE_REVIEW.read_text()
    steps = text[text.index("4. Otherwise (chain not exhausted)") : text.index('The "no prior attempt" case')]
    reset = steps.index("task-set-status <task-id> pending")
    append = steps.index("5. Append the task ID to `state.rework_task_ids`")
    assert reset < append, (
        f"{_PHASE_REVIEW}: Phase 6 escalation appends the rework id before "
        "resetting the task to pending; a rotation between the writes would "
        "drop the task on resume."
    )
    assert "**after** the status reset, never before" in steps
