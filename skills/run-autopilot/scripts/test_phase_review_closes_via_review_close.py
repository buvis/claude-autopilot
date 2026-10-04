"""Pins PRD 00249 task 7: the decision gate's "Dispatch rework" and the
converged "Tail sweep" create their tasks through one `autopilot
review-close` call each, not a hand-run `group-rework` + `task-add` loop.

Same pattern as the sibling prose suites: slice each section by its heading
and assert on short literal fragments with a message naming what drifted.
"""

from __future__ import annotations

from pathlib import Path

_PHASE_REVIEW = Path(__file__).resolve().parent.parent / "references" / "phase-review.md"


def _section(text: str, start: str, end: str) -> str:
    assert start in text, f"{_PHASE_REVIEW}: heading {start!r} is gone"
    begin = text.index(start)
    assert end in text[begin:], f"{_PHASE_REVIEW}: heading {end!r} is gone"
    return text[begin : text.index(end, begin)]


def test_phase_review_closes_via_review_close() -> None:
    text = _PHASE_REVIEW.read_text()
    sections = {
        "Dispatch rework": _section(
            text, "### Dispatch rework", "### After /autopilot:work returns"
        ),
        "Tail sweep": _section(text, "### Tail sweep", "### Hand off to the finalize session"),
    }
    for name, body in sections.items():
        assert "autopilot review-close" in body, (
            f"{_PHASE_REVIEW}: the {name} section does not create its tasks "
            "through `autopilot review-close`."
        )
        assert "autopilot group-rework" not in body, (
            f"{_PHASE_REVIEW}: the {name} section still hand-runs "
            "`autopilot group-rework`; review-close groups the findings itself."
        )
    assert "--batch-id decision-gate" in sections["Dispatch rework"]
    assert "--batch-id tail-sweep" in sections["Tail sweep"]
