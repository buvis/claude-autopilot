"""Pins the cap_regression prose: the loop-mode cap-out deferral bullet in
phase-review.md must run `autopilot cap-check` before deferring and route a
regression (exit 1) to a `cap_regression` stall, and the `cap_regression` slug
must appear beside `cap_critical` in both recovery.md and state-schema.md
(PRD 00310).
"""

from __future__ import annotations

from pathlib import Path

_REFERENCES = Path(__file__).resolve().parent.parent / "references"
_PHASE_REVIEW = _REFERENCES / "phase-review.md"
_RECOVERY = _REFERENCES / "recovery.md"
_STATE_SCHEMA = _REFERENCES / "state-schema.md"

_CAP_OUT_BULLET_START = 'Otherwise (all unresolved findings ≤ high)'
_CAP_OVERFLOW_DEFER_SENTENCE = (
    'Append each to `deferred_decisions` as `{"type": "cap-overflow"'
)


def _cap_out_bullet() -> str:
    text = _PHASE_REVIEW.read_text()
    assert _CAP_OUT_BULLET_START in text, (
        f"{_PHASE_REVIEW}: the cap-out deferral bullet is gone"
    )
    start = text.index(_CAP_OUT_BULLET_START)
    assert _CAP_OVERFLOW_DEFER_SENTENCE in text[start:], (
        f"{_PHASE_REVIEW}: the cap-overflow deferral sentence is gone"
    )
    end = text.index(_CAP_OVERFLOW_DEFER_SENTENCE, start)
    return text[start:end]


def test_cap_out_runs_cap_check_before_deferring() -> None:
    bullet = _cap_out_bullet()
    assert "autopilot cap-check" in bullet, (
        f"{_PHASE_REVIEW}: the cap-out bullet never mentions `autopilot cap-check`"
        " ahead of the cap-overflow deferral"
    )


def test_exit_1_routes_to_cap_regression_stall() -> None:
    bullet = _cap_out_bullet()
    assert "autopilot stall" in bullet and "cap_regression" in bullet, (
        f"{_PHASE_REVIEW}: the cap-out bullet never routes a cap-check regression"
        " to `autopilot stall ... site cap_regression`"
    )


def test_recovery_lists_cap_regression_slug() -> None:
    for path in (_RECOVERY, _STATE_SCHEMA):
        text = path.read_text()
        assert "cap_critical" in text and "cap_regression" in text, (
            f"{path}: `cap_regression` must appear beside `cap_critical`"
        )
