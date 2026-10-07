#!/usr/bin/env python3
"""Tail-sweep refusals for cli/review_close.py: the carry row, the duplicated
deferral, the accepting path and the CLI's exit code.

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

# An open deferral sharing TAIL_MED's (severity, file) pair but not its issue.
OPEN_DEFERRAL = {
    "issue": "deferred last cycle",
    "severity": MED,
    "file": "src/c.py:20",
    "reason": "needs a design call",
}


@pytest.mark.parametrize("decision_gate_applied", [True, False])
def test_tail_sweep_refuses_a_carry_row_ahead_of_its_other_checks(
    tmp_path: Path,
    decision_gate_applied: bool,
) -> None:
    """A carry row is a decision-gate disposition: a sweep that carried one
    would move a row forward with no gate record of it. It is reported even
    when the sweep ALSO runs before the decision-gate batch was applied, which
    pins which of the two refusals the operator is told about first."""
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
        [TAIL_MED, CARRY_ROW],
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
    issue differs from the deferral's and it is still refused, and the reason
    names the pair so the operator can tell which deferral collided."""
    review = _review(tmp_path)
    state_path = _swept(tmp_path, review, deferred_decisions=[OPEN_DEFERRAL])
    before = state_path.read_bytes()
    # The first row duplicates nothing: a check that only read row one would
    # wave this batch through.
    rows = [dict(_finding(MED, "src/a.py:3", "stale comment"), ref="R1"), TAIL_MED]

    result = review_close.close(review, state_path, "tail-sweep", rows)

    assert result["applied"] is False
    assert result["refused"] == "tail_sweep_duplicates_deferral"
    assert MED in result["reason"]
    assert "src/c.py:20" in result["reason"]
    assert state_path.read_bytes() == before
    assert not Path(f"{state_path}.lock").exists()


def test_a_clean_tail_sweep_still_applies(tmp_path: Path) -> None:
    """The accepting side: decision-gate applied, Medium and Low rows only, no
    carry row, and the one open deferral shares a file with a swept row but not
    its severity - so the pair does not match and the batch is recorded."""
    review = _review(tmp_path)
    state_path = _swept(
        tmp_path,
        review,
        deferred_decisions=[dict(OPEN_DEFERRAL, severity=LOW)],
    )

    result = review_close.close(
        review,
        state_path,
        "tail-sweep",
        [TAIL_MED, _finding(LOW, "src/a.py:3", "stale comment")],
    )

    assert result["applied"] is True
    assert "refused" not in result
    batches = _load(state_path)["applied_review_batches"]
    assert f"{review.resolve()}::tail-sweep" in batches


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
