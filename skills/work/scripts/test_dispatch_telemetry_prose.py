"""Prose pins for the dispatch timing ledger (PRD 00168).

Same pattern as test_dispatch_prose.py and test_command_budget_prose.py: read
each file once, assert on short, reword-resistant substrings, each with a
failure message naming what drifted. A separate file because
test_dispatch_prose.py sits at 710 lines and the pack's own step-5.65 style
gate flags an 800-line crossing (test_command_budget_prose.py split for the
same reason).

Nothing executes a call site but a reader: the render flags, the `end` call
and the handoff rows are Bash lines the orchestrator copies from these files,
so a dropped flag leaves every script test green while the ledger silently
stops filling — which is the failure the ledger exists to end.
"""

from __future__ import annotations

from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parent
_WORK = _SCRIPTS.parent
_REFS = _WORK / "references"
_SKILL_MD = _WORK / "SKILL.md"
_RUN_REFS = _WORK.parent / "run-autopilot" / "references"
_RUN_SKILL_MD = _WORK.parent / "run-autopilot" / "SKILL.md"
_CHANGELOG = _WORK.parents[1] / "CHANGELOG.md"

_RENDER = "render_prompt.py ${CLAUDE_PLUGIN_ROOT}"
_FLAG = "--dispatch-kind"
_END_CALL = "record_dispatch.py end"
_START_CALL = "record_dispatch.py start"
_HANDOFF_CALL = "record_dispatch.py handoff"


def _section(text: str, start: str, end: str) -> str:
    # The end marker is searched past the start marker: `## ` is a substring
    # of `### Retention`, so searching from `begin` yields a one-byte section.
    begin = text.index(start)
    return text[begin : text.index(end, begin + len(start))]


def test_every_render_block_in_the_body_carries_both_flags_for_its_persona() -> None:
    # Three render blocks, three personas. Pinning the kind per block, not
    # just the flag's presence, is what catches a copy-pasted `tess` on the
    # Ivan render — a ledger whose kinds are wrong is worse than none.
    text = _SKILL_MD.read_text()

    for start, end, kind in (
        ("### 2.7.", "### 2.8.", "tess"),
        ("### 3.", "### 4.", "ivan"),
        ("### 5.7.", "### 6.", "pat"),
    ):
        step = _section(text, start, end)
        assert _RENDER in step, (
            f"{_SKILL_MD}: step {start} no longer renders through "
            "render_prompt.py, so the start row it used to open is gone."
        )
        assert f"--dispatch-kind {kind} --dispatch-task" in step, (
            f"{_SKILL_MD}: the step {start} render block does not pass "
            f"`--dispatch-kind {kind} --dispatch-task`. Without both flags the "
            "render is byte-identical to before and writes no start row."
        )

    assert _END_CALL in text, (
        f"{_SKILL_MD}: nothing names `record_dispatch.py end`, so every start "
        "row stays open and no dispatch ever gets an elapsed time."
    )


def test_the_hand_built_dispatches_open_their_rows_with_start() -> None:
    # Devon (2.85) and the self-deslop pass (5.6) fill their templates by
    # hand — the PRD's premise that every dispatch renders was false for both
    # — so without this call those two lanes are holes in every task's timeline.
    text = _SKILL_MD.read_text()

    devon = _section(text, "### 2.85.", "### 2.9.")
    assert f"{_START_CALL} --kind devon" in devon, (
        f"{_SKILL_MD}: step 2.85 never opens Devon's row with "
        "`record_dispatch.py start --kind devon`; no render does it for him."
    )
    deslop = _section(text, "### 5.6.", "### 5.65.")
    assert f"{_START_CALL} --kind deslop" in deslop, (
        f"{_SKILL_MD}: step 5.6 never opens the deslop pass's row with "
        "`record_dispatch.py start --kind deslop`; no render does it for it."
    )


def test_step_6_5_writes_the_leave_row_before_the_stop() -> None:
    # The gap this row opens is closed by the next session's `resume` row;
    # written after STOP it would never be written at all.
    text = _SKILL_MD.read_text()
    step = _section(text, "### 6.5.", "### 7.")
    assert "handoff row" in step, (
        f"{_SKILL_MD}: step 6.5 does not name the handoff row among the "
        "procedure's steps, so a reader following the body skips it."
    )

    handoff = (_REFS / "task-boundary-handoff.md").read_text()
    command = f"{_HANDOFF_CALL} --site build --edge leave"
    assert command in handoff, (
        "references/task-boundary-handoff.md never writes the `leave` row for "
        "the task-boundary handoff."
    )
    assert handoff.index(command) < handoff.index("then STOP"), (
        "references/task-boundary-handoff.md writes the `leave` row after the "
        "STOP; a session that has ended writes nothing."
    )


def test_every_reference_render_carries_the_flags_for_its_persona() -> None:
    # One expectation per file, by count: a reference that grows a second
    # render block without the flags fails here instead of quietly opening
    # no row for the retry, the style fix or the delta re-run.
    for name, kind, renders in (
        ("gate-failure.md", "ivan", 2),
        ("test-author-prompt.md", "tess", 1),
        ("per-task-review.md", "pat", 1),
    ):
        text = (_REFS / name).read_text()
        assert text.count(_RENDER) == renders, (
            f"references/{name} has {text.count(_RENDER)} render blocks, not "
            f"{renders}; retarget this pin and add the flags to the new one."
        )
        assert text.count(f"--dispatch-kind {kind} --dispatch-task") == renders, (
            f"references/{name}: not every render block passes "
            f"`--dispatch-kind {kind} --dispatch-task`, so that dispatch opens "
            "no start row."
        )


def test_the_reference_defines_the_rows_the_outcomes_and_the_never_blocks_rule() -> (
    None
):
    dispatch = (_REFS / "subagent-dispatch.md").read_text()
    assert "## Dispatch telemetry" in dispatch, (
        "references/subagent-dispatch.md has no `## Dispatch telemetry` "
        "section; every call site cites it by name."
    )
    section = dispatch[dispatch.index("## Dispatch telemetry") :]

    for needle in (
        "dispatch-metrics.jsonl",
        "ledger/dispatch-metrics.jsonl",
        "queued_at",
        "prompt_bytes",
        "elapsed_s",
        _START_CALL,
        _END_CALL,
        _HANDOFF_CALL,
    ):
        assert needle in section, (
            f"references/subagent-dispatch.md § Dispatch telemetry never names "
            f"{needle!r}; the row catalogue is the only place a reader learns "
            "the shape."
        )
    for outcome in ("`ok`", "`timeout`", "`killed`", "`error`", "`lost`"):
        assert outcome in section, (
            f"references/subagent-dispatch.md § Dispatch telemetry does not map "
            f"{outcome} to a dispatch result; an unmapped outcome is stamped by "
            "guess."
        )
    assert "never a dispatch failure" in section, (
        "references/subagent-dispatch.md § Dispatch telemetry dropped the rule "
        "that a telemetry failure is never a dispatch failure — the one "
        "sentence that keeps a broken ledger from stalling a batch."
    )

    watchdog = _section(
        dispatch, "## Subagent Watchdog", "## Foreground command budgets"
    )
    assert watchdog.count("Dispatch telemetry") >= 2, (
        "references/subagent-dispatch.md § Subagent Watchdog no longer points "
        "at § Dispatch telemetry from both return points (the Agent completion "
        "and the helper-script `TaskOutput` wait), so one lane's rows stay open."
    )


def test_attempt_logging_points_at_the_ledger_and_keeps_timing_out_of_the_record() -> (
    None
):
    attempt_logging = (_REFS / "attempt-logging.md").read_text()
    assert "dispatch-metrics" in attempt_logging, (
        "references/attempt-logging.md never points at the dispatch ledger, so "
        "a reader looking for a task's runtime in the attempt record finds "
        "nothing and no pointer."
    )
    assert "not an attempt field" in attempt_logging, (
        "references/attempt-logging.md no longer says timing is deliberately "
        "not an attempt field; the next PRD adds a `duration_s` stamp that "
        "cannot say which of the task's dispatches took the hour."
    )


def test_every_handoff_site_writes_its_edge() -> None:
    # A `leave` with no matching `resume` (or the reverse) measures nothing.
    # Counts per file: build and done each hand off once and resume once;
    # review resumes once and hands off twice (review → review, review → done).
    expectations = {
        "phase-build.md": {
            "--site build --edge resume": 1,
            "--site build --edge leave": 1,
        },
        "phase-review.md": {
            "--site review --edge resume": 1,
            "--site review --edge leave": 2,
        },
        "phase-done.md": {
            "--site done --edge resume": 1,
            "--site done --edge leave": 1,
        },
    }
    for name, counts in expectations.items():
        text = (_RUN_REFS / name).read_text()
        for needle, count in counts.items():
            assert text.count(f"{_HANDOFF_CALL} {needle}") == count, (
                f"run-autopilot/references/{name} writes "
                f"`{_HANDOFF_CALL} {needle}` {text.count(f'{_HANDOFF_CALL} {needle}')} "
                f"times, not {count}; the gap that edge measures is unrecorded."
            )


def test_the_review_leave_rows_follow_their_phase_done_calls() -> None:
    # `phase` on a leave row is state.phase at write time, which is only the
    # next session's phase once phase-done has committed the transition.
    review = (_RUN_REFS / "phase-review.md").read_text()

    finalize = _section(review, "### Hand off to the finalize session", "## Phase 6")
    assert finalize.index("--outcome converged") < finalize.index(
        "--site review --edge leave --phase done",
    ), (
        "run-autopilot/references/phase-review.md writes the review → done "
        "`leave` row before `phase-done --outcome converged`, so its `phase` "
        "names the phase being left rather than the one handed to."
    )
    rework = _section(review, "### After /autopilot:work returns", "## De-slop")
    assert rework.index("--outcome rework") < rework.index(
        "--site review --edge leave --phase review",
    ), (
        "run-autopilot/references/phase-review.md writes the review → review "
        "`leave` row before `phase-done --outcome rework`, so a crash between "
        "them records a handoff that never committed."
    )


def test_retention_lists_the_ledger_mirror_as_durable() -> None:
    skill = _RUN_SKILL_MD.read_text()
    retention = _section(skill, "### Retention", "\n#")
    assert "ledger/dispatch-metrics.jsonl" in retention, (
        "run-autopilot/SKILL.md § Retention does not list "
        "`ledger/dispatch-metrics.jsonl` as durable; a cleanup that reads the "
        "contract literally may trash the one copy that survives GC."
    )


def test_the_changelog_names_the_ledger_under_unreleased() -> None:
    changelog = _CHANGELOG.read_text()
    unreleased = changelog[changelog.index("## [Unreleased]") :]
    next_release = unreleased.find("\n## [", 1)
    if next_release != -1:
        unreleased = unreleased[:next_release]
    assert "dispatch-metrics.jsonl" in unreleased, (
        "CHANGELOG.md has no [Unreleased] entry naming "
        "dev/local/autopilot/dispatch-metrics.jsonl; the ledger is user-visible "
        "and the changelog rule is blocking."
    )
