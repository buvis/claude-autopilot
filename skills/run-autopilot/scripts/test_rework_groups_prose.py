"""Pins the group-rework wiring prose in `references/phase-review.md`: Phase 6's
"Dispatch rework" list must gain a "Group first." bullet ahead of the existing
CRITICAL-D-task bullet, and the Tail sweep section's split rule must route
through `autopilot group-rework` instead of the old hand-split threshold.

Same pattern as the sibling prose suites: read the file once, locate the two
landmarks by their literal text, and assert on short reword-resistant
fragments with a message naming what drifted.
"""

from __future__ import annotations

from pathlib import Path

_PHASE_REVIEW = Path(__file__).resolve().parent.parent / "references" / "phase-review.md"

_GROUP_FIRST = "Group first."
_CRITICAL_D_TASKS = "CRITICAL D-tasks carry the rework design"
_TAIL_SWEEP = "### Tail sweep"
_HAND_OFF = "### Hand off to the finalize session"
_SPLIT_RULE = "**Split rule:**"


def test_phase_6_groups_before_creating_d_tasks() -> None:
    text = _PHASE_REVIEW.read_text()
    assert _GROUP_FIRST in text, f"{_PHASE_REVIEW}: the 'Group first.' bullet is gone"
    assert _CRITICAL_D_TASKS in text, (
        f"{_PHASE_REVIEW}: the 'CRITICAL D-tasks carry the rework design' bullet is gone"
    )
    group_start = text.index(_GROUP_FIRST)
    critical_start = text.index(_CRITICAL_D_TASKS)
    assert group_start < critical_start, (
        f"{_PHASE_REVIEW}: 'Group first.' must come before the CRITICAL D-tasks "
        "bullet so grouping happens before task creation"
    )
    bullet = text[group_start:critical_start]
    for needle in ("autopilot group-rework", "Never split or merge groups by hand"):
        assert needle in bullet, (
            f"{_PHASE_REVIEW}: the 'Group first.' bullet lacks {needle!r}"
        )


def test_tail_sweep_split_rule_uses_the_command() -> None:
    text = _PHASE_REVIEW.read_text()
    assert _TAIL_SWEEP in text, f"{_PHASE_REVIEW}: the 'Tail sweep' section is gone"
    assert _HAND_OFF in text, (
        f"{_PHASE_REVIEW}: the 'Hand off to the finalize session' section is gone"
    )
    section = text[text.index(_TAIL_SWEEP) : text.index(_HAND_OFF)]
    assert _SPLIT_RULE in section, (
        f"{_PHASE_REVIEW}: the Tail sweep section lost its 'Split rule:' sentence"
    )
    start = section.index(_SPLIT_RULE)
    assert "\n\n" in section[start:], (
        f"{_PHASE_REVIEW}: the 'Split rule:' sentence has no paragraph end to bound it"
    )
    end = section.index("\n\n", start)
    sentence = section[start:end]
    for needle in ("autopilot group-rework", "caps at 4"):
        assert needle in sentence, (
            f"{_PHASE_REVIEW}: the Tail sweep 'Split rule:' sentence lacks {needle!r}"
        )
