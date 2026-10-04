"""Pins the review-close wiring prose in `references/phase-review.md` (PRD 00249):
Phase 6's "Dispatch rework" decision-gate bullet and the Tail sweep section's
split rule must both route task creation through `autopilot review-close`,
never through hand-run `task-add`/`group-rework` calls.

Same pattern as the sibling prose suites: read the file once, locate the
landmarks by their literal text, and assert on short reword-resistant
fragments with a message naming what drifted.
"""

from __future__ import annotations

from pathlib import Path

_PHASE_REVIEW = Path(__file__).resolve().parent.parent / "references" / "phase-review.md"

_DECISION_GATE_START = "2. **Decision gate"
_CRITICAL_D_TASKS = "CRITICAL D-tasks carry the rework design"
_TAIL_SWEEP = "### Tail sweep"
_HAND_OFF = "### Hand off to the finalize session"


def test_phase_6_decision_gate_calls_review_close_before_creating_d_tasks() -> None:
    text = _PHASE_REVIEW.read_text()
    assert _DECISION_GATE_START in text, (
        f"{_PHASE_REVIEW}: the decision-gate '[D{{cycle}}]' bullet is gone"
    )
    assert _CRITICAL_D_TASKS in text, (
        f"{_PHASE_REVIEW}: the 'CRITICAL D-tasks carry the rework design' bullet is gone"
    )
    gate_start = text.index(_DECISION_GATE_START)
    critical_start = text.index(_CRITICAL_D_TASKS)
    assert gate_start < critical_start, (
        f"{_PHASE_REVIEW}: the decision-gate bullet must come before the CRITICAL "
        "D-tasks bullet so review-close's task creation happens before the "
        "CRITICAL-specific contract body is attached"
    )
    bullet = text[gate_start:critical_start]
    for needle in ("autopilot review-close", "--batch-id decision-gate", "--findings"):
        assert needle in bullet, (
            f"{_PHASE_REVIEW}: the decision-gate bullet lacks {needle!r}"
        )
    assert "statectl.py" not in bullet and "task-add <task-json-file>" not in bullet, (
        f"{_PHASE_REVIEW}: the decision-gate bullet still invokes a hand-run "
        "'task-add' call instead of routing through review-close"
    )


def test_tail_sweep_split_rule_uses_review_close() -> None:
    text = _PHASE_REVIEW.read_text()
    assert _TAIL_SWEEP in text, f"{_PHASE_REVIEW}: the 'Tail sweep' section is gone"
    assert _HAND_OFF in text, (
        f"{_PHASE_REVIEW}: the 'Hand off to the finalize session' section is gone"
    )
    section = text[text.index(_TAIL_SWEEP) : text.index(_HAND_OFF)]
    for needle in ("autopilot review-close", "--batch-id tail-sweep", "--findings"):
        assert needle in section, (
            f"{_PHASE_REVIEW}: the Tail sweep section lacks {needle!r}"
        )
    assert "autopilot group-rework" not in section, (
        f"{_PHASE_REVIEW}: the Tail sweep section still names 'autopilot "
        "group-rework' instead of routing through review-close"
    )


def test_tail_sweep_split_rule_states_findings_path_naming_and_floor() -> None:
    text = _PHASE_REVIEW.read_text()
    assert _TAIL_SWEEP in text, f"{_PHASE_REVIEW}: the 'Tail sweep' section is gone"
    assert _HAND_OFF in text, (
        f"{_PHASE_REVIEW}: the 'Hand off to the finalize session' section is gone"
    )
    section = text[text.index(_TAIL_SWEEP) : text.index(_HAND_OFF)]
    assert "--findings" in section, (
        f"{_PHASE_REVIEW}: the Tail sweep section doesn't name a '--findings' "
        "path for how the findings file is produced"
    )
    assert "[D{cycle}] Tail sweep:" in section, (
        f"{_PHASE_REVIEW}: the Tail sweep section doesn't state the "
        "'[D{cycle}] Tail sweep:' task naming prefix"
    )
    assert "at most 4" in section or "caps at 4" in section, (
        f"{_PHASE_REVIEW}: the Tail sweep section doesn't state the grouping "
        "upper cap (at most 4 tasks)"
    )
    assert "never zero" in section, (
        f"{_PHASE_REVIEW}: the Tail sweep section doesn't state the grouping "
        "nonzero floor (never zero tasks)"
    )
