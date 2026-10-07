#!/usr/bin/env python3
"""Tail-sweep refusals for cli/review_close.py: the carry row, the duplicated
deferral, the review gate, the order two refusals are reported in, the
accepting path and the CLI's exit code.

The three acceptance-named refusal tests live in test_review_close.py; these
would push that module past the file-size limit, so they live here and share
its fixtures.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from cli import review_close
from cli.test_review_close import (
    CRIT,
    LOW,
    MED,
    TAIL_MED,
    _carry_task,
    _finding,
    _findings_file,
    _load,
    _review,
    _review_close_cli,
    _state,
    _swept,
)

ORIGINAL_TASK = {"id": "1", "name": "original", "status": "completed"}

# A carry row pointing at the re-queued [C2] task _carry_task() builds, and the
# state that holds it: the carry/task match cannot be what refuses a batch
# carrying this pair, so only the tail-sweep ban can.
CARRY_ROW = dict(_finding(MED, "src/b.py:10", "carry me", "carry"), ref="R1")
MATCHED_CARRY_STATE = {
    "tasks": [ORIGINAL_TASK, _carry_task()],
    "tasks_total": 2,
    "rework_task_ids": ["4"],
}

# A second carry row sharing nothing with CARRY_ROW but its classification:
# different issue text, different file, different severity. It points at the
# same re-queued [C2] task, so only `classification == "carry"` can refuse a
# batch holding it.
ALT_CARRY_ROW = dict(_finding(LOW, "src/zz.py:1", "stale docstring", "carry"), ref="R1")

# An open deferral sharing TAIL_MED's (severity, file) pair but not its issue.
OPEN_DEFERRAL = {
    "issue": "deferred last cycle",
    "severity": MED,
    "file": "src/c.py:20",
    "reason": "needs a design call",
}

# A second open deferral no swept row collides with: whatever the reason says,
# it must not send the operator to this one.
OTHER_DEFERRAL = {
    "issue": "also deferred last cycle",
    "severity": MED,
    "file": "src/other.py:7",
    "reason": "needs a design call",
}


@pytest.mark.parametrize(
    ("carry_row", "decision_gate_applied"),
    [
        (CARRY_ROW, True),
        (CARRY_ROW, False),
        (ALT_CARRY_ROW, True),
    ],
    ids=["swept", "before-gate", "unrelated-carry-row"],
)
def test_tail_sweep_refuses_a_carry_row_ahead_of_its_other_checks(
    tmp_path: Path,
    carry_row: dict,
    decision_gate_applied: bool,
) -> None:
    """A carry row is a decision-gate disposition: a sweep that carried one
    would move a row forward with no gate record of it. What refuses it is the
    `carry` classification, not any one row's text, so a carry row with a
    different issue, file and severity is refused too. It is reported even when
    the sweep ALSO runs before the decision-gate batch was applied, which pins
    which of the two refusals the operator is told about first."""
    review = _review(tmp_path)
    state_path = (
        _swept(tmp_path, review, **MATCHED_CARRY_STATE)
        if decision_gate_applied
        else _state(tmp_path, **MATCHED_CARRY_STATE)
    )
    before = state_path.read_bytes()

    result = review_close.close(
        review,
        state_path,
        "tail-sweep",
        [TAIL_MED, carry_row],
    )

    assert result["applied"] is False
    assert result["refused"] == "carry_in_tail_sweep"
    assert result["reason"] == "a tail-sweep batch never carries a carry row"
    assert state_path.read_bytes() == before
    assert not Path(f"{state_path}.lock").exists()


def test_tail_sweep_refuses_a_row_duplicating_an_open_deferral(
    tmp_path: Path,
) -> None:
    """A sweep row the operator already deferred would re-open settled work.
    The match is the (severity, file) pair, not the issue text: this row's
    issue differs from the deferral's and it is still refused. Two deferrals
    are open and only one collides, so the reason has to name that one and not
    the bystander - otherwise the operator reads a constant string and goes
    looking at the wrong deferral."""
    review = _review(tmp_path)
    state_path = _swept(
        tmp_path,
        review,
        deferred_decisions=[OTHER_DEFERRAL, OPEN_DEFERRAL],
    )
    before = state_path.read_bytes()
    # The first row duplicates nothing: a check that only read row one would
    # wave this batch through.
    rows = [dict(_finding(MED, "src/a.py:3", "stale comment"), ref="R1"), TAIL_MED]

    result = review_close.close(review, state_path, "tail-sweep", rows)

    assert result["applied"] is False
    assert result["refused"] == "tail_sweep_duplicates_deferral"
    assert MED in result["reason"]
    assert "src/c.py:20" in result["reason"]
    assert OTHER_DEFERRAL["file"] not in result["reason"]
    assert state_path.read_bytes() == before
    assert not Path(f"{state_path}.lock").exists()


# The row a clean sweep defers: an accepted sweep has to record it as an open
# decision, not drop it.
DEFER_ROW = _finding(MED, "src/d.py:4", "later", "defer")


@pytest.mark.parametrize(
    "deferral",
    [
        dict(OPEN_DEFERRAL, severity=LOW),
        dict(OPEN_DEFERRAL, file="src/zz.py:99"),
    ],
    ids=["same-file-other-severity", "same-severity-other-file"],
)
def test_a_clean_tail_sweep_still_applies(tmp_path: Path, deferral: dict) -> None:
    """The accepting side: decision-gate applied, Medium and Low rows only, no
    carry row, and the one open deferral matches a swept row on exactly one
    axis - same file, other severity, or same severity on a file no swept row
    touches - so the pair does not match either way. Applying means the swept
    rows land: the `fix` rows become rework tasks and the `defer` row becomes
    an open decision. A sweep that only stamped the batch would have thrown
    every swept finding away."""
    review = _review(tmp_path)
    state_path = _swept(tmp_path, review, deferred_decisions=[deferral])

    result = review_close.close(
        review,
        state_path,
        "tail-sweep",
        [TAIL_MED, _finding(LOW, "src/a.py:3", "stale comment"), DEFER_ROW],
    )

    assert result["applied"] is True
    assert "refused" not in result
    data = _load(state_path)
    assert f"{review.resolve()}::tail-sweep" in data["applied_review_batches"]
    created = result["tasks_created"]
    assert created, "the swept fix rows must reach state.json as rework tasks"
    swept_tasks = [t for t in data["tasks"] if t["id"] in created]
    assert any("src/c.py" in t["name"] for t in swept_tasks)
    assert all(task_id in data["rework_task_ids"] for task_id in created)
    open_decisions = data["deferred_decisions"]
    assert [d["issue"] for d in open_decisions].count(DEFER_ROW["issue"]) == 1
    assert len(open_decisions) == 2


def test_a_tail_sweep_over_a_gate_failing_review_is_refused_by_the_gate(
    tmp_path: Path,
) -> None:
    """A tail sweep relaxes the findings coverage check, not the review gate: a
    review artifact with no Verdict: line is refused on the gate's own terms,
    so a sweep cannot close a cycle whose review file was never readable.
    Every tail-sweep condition holds here, so no tail-sweep refusal can be what
    stops it, and close() has to have read the file to refuse at all."""
    review = _review(tmp_path, verdict="")
    state_path = _swept(tmp_path, review)
    before = state_path.read_bytes()

    result = review_close.close(review, state_path, "tail-sweep", [TAIL_MED])

    assert result["applied"] is False
    assert "no verdict line" in result["reason"]
    assert not result.get("refused", "").startswith("tail_sweep")
    assert result.get("refused") != "carry_in_tail_sweep"
    assert state_path.read_bytes() == before
    assert not Path(f"{state_path}.lock").exists()


# A red row, and an open deferral duplicating its (severity, file) pair: a
# batch holding both trips the above-medium and the duplicate-deferral refusal.
CRIT_ROW = dict(_finding(CRIT, "src/a.py:3", "crash on empty input"), ref="R1")
CRIT_DEFERRAL = dict(OPEN_DEFERRAL, severity=CRIT, file="src/a.py:3")
CRIT_DUP_STATE = {"deferred_decisions": [CRIT_DEFERRAL]}
CARRY_DUP_STATE = dict(MATCHED_CARRY_STATE, deferred_decisions=[CRIT_DEFERRAL])


@pytest.mark.parametrize(
    ("rows", "decision_gate_applied", "extra", "expected"),
    [
        ([], False, {}, "tail_sweep_before_decision_gate"),
        ([CRIT_ROW], False, CRIT_DUP_STATE, "tail_sweep_before_decision_gate"),
        ([CRIT_ROW], True, CRIT_DUP_STATE, "tail_sweep_above_medium"),
        ([CARRY_ROW, CRIT_ROW], True, CARRY_DUP_STATE, "carry_in_tail_sweep"),
    ],
    ids=[
        "empty-and-before-gate",
        "above-medium-and-before-gate",
        "above-medium-and-duplicate-deferral",
        "carry-and-above-medium",
    ],
)
def test_a_tail_sweep_tripping_two_refusals_reports_the_earlier_kind(
    tmp_path: Path,
    rows: list[dict],
    decision_gate_applied: bool,
    extra: dict,
    expected: str,
) -> None:
    """The five refusals are ordered, and the operator hears about the earliest
    one that fires: a carry row outranks an above-Medium row, a missing
    decision-gate batch outranks both an empty batch and an above-Medium row,
    and an above-Medium row outranks a duplicated deferral. Naming a later kind
    would send the operator to fix the wrong thing and re-run into the first
    refusal anyway."""
    review = _review(tmp_path)
    state_path = (
        _swept(tmp_path, review, **extra)
        if decision_gate_applied
        else _state(tmp_path, **extra)
    )
    before = state_path.read_bytes()

    result = review_close.close(review, state_path, "tail-sweep", rows)

    assert result["applied"] is False
    assert result["refused"] == expected
    assert state_path.read_bytes() == before
    assert not Path(f"{state_path}.lock").exists()


@pytest.mark.parametrize(
    ("kind", "rows", "decision_gate_applied", "extra"),
    [
        ("carry_in_tail_sweep", [TAIL_MED, CARRY_ROW], True, MATCHED_CARRY_STATE),
        ("tail_sweep_before_decision_gate", [TAIL_MED], False, {}),
        ("tail_sweep_empty", [], True, {}),
        (
            "tail_sweep_above_medium",
            [dict(_finding(CRIT, "src/a.py:3", "crash on empty input"), ref="R1")],
            True,
            {},
        ),
        (
            "tail_sweep_duplicates_deferral",
            [TAIL_MED],
            True,
            {"deferred_decisions": [OPEN_DEFERRAL]},
        ),
    ],
)
def test_cli_exits_2_on_every_tail_sweep_refusal(
    tmp_path: Path,
    kind: str,
    rows: list[dict],
    decision_gate_applied: bool,
    extra: dict,
) -> None:
    """Each refusal has to reach the caller as exit 2 and name its kind: exit 1
    reads as a plain not-applied (an already-applied re-run), so an
    orchestrator would retry instead of stopping. State stays byte-identical."""
    review = _review(tmp_path)
    state_path = (
        _swept(tmp_path, review, **extra)
        if decision_gate_applied
        else _state(tmp_path, **extra)
    )
    before = state_path.read_bytes()
    findings = _findings_file(tmp_path, rows)

    proc = _review_close_cli(review, state_path, findings, batch_id="tail-sweep")

    output = proc.stdout + proc.stderr
    assert proc.returncode == 2, output
    assert kind in output
    assert state_path.read_bytes() == before
