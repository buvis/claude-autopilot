"""Pins PRD 00200's marker placement: `/work` reads `.handoff-requested` in
exactly one place, step 6.5, after step 6's task-done write, and the build
gate applies the same headroom rule at the design->plan and plan->work edges
where no task is in progress.

Same pattern as the other prose suites: read each markdown file once, slice
the step by its heading, assert on short reword-resistant fragments with a
failure message naming what drifted.
"""

from __future__ import annotations

from pathlib import Path

_SKILLS = Path(__file__).resolve().parent.parent.parent
_WORK_SKILL = _SKILLS / "work" / "SKILL.md"
_PHASE_BUILD = _SKILLS / "run-autopilot" / "references" / "phase-build.md"
_HANDOFF = _SKILLS / "work" / "references" / "task-boundary-handoff.md"

_PLACEMENT_SENTENCE = (
    "A marker seen before this step is carried to this step; between the "
    "commit of step 5 and the task-done write of step 6 the marker is never "
    "acted on."
)


def _section(text: str, start: str, end: str) -> str:
    i = text.index(start)
    return text[i : text.index(end, i)]


def test_marker_is_read_only_at_step_6_5() -> None:
    step_6_5 = _section(_WORK_SKILL.read_text(), "### 6.5.", "### 7.")
    assert _PLACEMENT_SENTENCE in step_6_5, (
        f"{_WORK_SKILL}: step 6.5 lacks the placement sentence "
        f"{_PLACEMENT_SENTENCE!r} - a session that reads the marker between "
        "the commit and the task-done write hands off with the task still "
        "in_progress (PRD 00182's batch)."
    )
    for needle in ("read only here", "`task-done` write has landed"):
        assert needle in step_6_5, f"{_WORK_SKILL}: step 6.5 lacks {needle!r}"


def test_build_gate_hands_off_at_design_and_plan_edges() -> None:
    # The hook writes no marker with no task in progress, so the build gate
    # applies the rule itself at both pre-task edges, naming both estimates.
    text = _PHASE_BUILD.read_text()
    design_exit = _section(text, "After design completes", "## Phase 2: Planning")
    plan_exit = _section(
        text, "After completion, `state.tasks` is already current", "## Phase 3: Work"
    )
    for where, edge in (("Phase 1.5 exit", design_exit), ("Phase 2 exit", plan_exit)):
        for needle in (
            "TURN_TRIPWIRE - count < FIRST_TASK_CALLS_ESTIMATE",
            "USAGE_CAP - total < FIRST_TASK_USAGE_ESTIMATE",
            "fresh build session",
        ):
            assert needle in edge, f"{_PHASE_BUILD}: the {where} lacks {needle!r}"
    for needle in (
        ".turn-counts.json",
        "`last.count`",
        "`last.usage`",
        "450 - count < 200",
        "always describes the running session",
        "the calls comparison stays in force",
    ):
        assert needle in design_exit, (
            f"{_PHASE_BUILD}: the gate-edge check lacks {needle!r}"
        )
    # After a rotation the fresh session clears the dead session's marker at
    # Phase 0, so the hook is not blind during its prologue.
    abort = _section(text, "### Handle Work-phase abort", "### Handle pending custody")
    assert "_walk_up.py --clear-cap" in abort, (
        f"{_PHASE_BUILD}: the cap-rotation handler never clears `.cap-fired`"
    )


def test_handoff_reference_names_the_headroom_rule_not_a_soft_cap() -> None:
    # PRD 00200 replaced the flat soft cap with the headroom rule; the
    # reference and its banner must not describe the old trigger.
    text = _HANDOFF.read_text()
    for needle in ("headroom rule fires (PRD 00200)", "headroom rule fired"):
        assert needle in text, f"{_HANDOFF}: lacks {needle!r}"
    for stale in ("SOFT_CAP", "_soft_limit", "soft threshold", "context near soft cap"):
        assert stale not in text, f"{_HANDOFF}: still says {stale!r}"


def test_leave_row_is_the_last_write_before_the_stop() -> None:
    # PRD 00199: the next session compares state.json's mtime against the
    # leave row's timestamp, so next_phase must be set BEFORE the row.
    text = _HANDOFF.read_text()
    step_h = text[text.index("h. **Write the contract card**") :]
    assert step_h.index("set `state.next_phase`") < step_h.index(
        "record_dispatch.py handoff"
    ), f"{_HANDOFF}: step h writes the leave row before state.next_phase"
    assert "last write before the stop" in step_h, (
        f"{_HANDOFF}: step h no longer says the leave row is the last write"
    )
