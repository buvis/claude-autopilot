"""Pins the rework-tier floor prose: Phase 6 "Dispatch rework"'s "Compute the
tier" bullet must apply `final_tier = max(tier, default_model)` only when the
task's findings carry a CRITICAL, and plan-tasks/SKILL.md must point authors
at that rule so a `[D]` task's tier isn't silently floored on every rework.
"""

from __future__ import annotations

from pathlib import Path

_PHASE_REVIEW = (
    Path(__file__).resolve().parent.parent / "references" / "phase-review.md"
)
_PLAN_TASKS = Path(__file__).resolve().parent.parent.parent / "plan-tasks" / "SKILL.md"

_COMPUTE_TIER = "Compute the tier"
_NEXT_BULLET = "`task-add <task-json-file>` with a payload"


def _compute_tier_bullet(text: str) -> str:
    assert _COMPUTE_TIER in text, (
        f"{_PHASE_REVIEW}: the 'Compute the tier' bullet is gone"
    )
    start = text.index(_COMPUTE_TIER)
    return text[start : text.index(_NEXT_BULLET, start)]


def test_floor_applies_only_to_critical_rework() -> None:
    bullet = _compute_tier_bullet(_PHASE_REVIEW.read_text())
    for needle in (
        "only when the task's findings include at least one \U0001f534 CRITICAL line",
        "`final_tier = max(tier, default_model)`",
    ):
        assert needle in bullet, (
            f"{_PHASE_REVIEW}: the 'Compute the tier' bullet lacks {needle!r}"
        )


def test_non_critical_rework_keeps_the_classifier_tier() -> None:
    bullet = _compute_tier_bullet(_PHASE_REVIEW.read_text())
    assert "keeps the classifier tier" in bullet, (
        f"{_PHASE_REVIEW}: the 'Compute the tier' bullet lacks 'keeps the classifier tier'"
    )


def test_plan_tasks_points_at_the_rework_rule() -> None:
    text = _PLAN_TASKS.read_text()
    needle = "Review-rework `[D]` tasks take this floor only when they carry a \U0001f534 finding"
    start = text.index("This guarantees:")
    end = text.index("**`qwen_eligible` computation**", start)
    floor_list = text[start:end]
    assert needle in floor_list, (
        f"{_PLAN_TASKS}: missing {needle!r} from the step 4.7 floor list"
    )
