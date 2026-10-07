#!/usr/bin/env python3
"""Carry-row tests for cli/review_close.py (PRD 00265 task 2).

A `carry` row claims "this finding leaves the decision gate unfixed because a
re-queued task already carries it". These tests pin the proof close() demands
for that claim. Fixtures and helpers are shared with test_review_close.py,
which keeps the four acceptance-named tests; this file holds the rest so
neither module runs further past the file-size limit.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from cli import review_close
from cli.test_review_close import (
    CARRY_CONSOLIDATED,
    CRIT,
    MED,
    _carry_batch,
    _carry_reason,
    _carry_state,
    _carry_task,
    _finding,
    _load,
    _review,
    _state,
)


def _carry_row(ref: object = "R1") -> dict:
    row = _finding(CRIT, "src/b.py:10", "crash on empty input", "carry")
    if ref is not None:
        row["ref"] = ref
    return row


@pytest.mark.parametrize("ref", [None, "", "   "], ids=["absent", "empty", "blank"])
def test_a_carry_row_with_no_usable_ref_is_refused_naming_none(
    tmp_path: Path,
    ref: object,
) -> None:
    """A carry row with no ref cannot be matched to any re-queued task, so it
    is unmatched by definition - and the refusal has to say which row it is
    talking about, which for a ref-less row is the literal `(none)`."""
    review = _review(tmp_path)
    state_path = _carry_state(tmp_path, [_carry_task()], ["4"])
    before = state_path.read_bytes()

    result = review_close.close(
        review,
        state_path,
        "decision-gate",
        [_carry_row(ref)],
    )

    assert result["applied"] is False
    assert result["refused"] == "carry_unmatched"
    assert result["reason"] == _carry_reason("(none)")
    assert state_path.read_bytes() == before


def test_two_carry_refs_backed_by_one_task_are_accepted(tmp_path: Path) -> None:
    """One re-queued task may carry several refs: a cycle carrying R1 and R2
    forward on a single task is backed, so the batch applies. An
    implementation matching one ref per task would refuse this."""
    review = _review(tmp_path, consolidated=CARRY_CONSOLIDATED)
    state_path = _carry_state(tmp_path, [_carry_task(refs=("R1", "R2"))], ["4"])

    result = review_close.close(
        review,
        state_path,
        "decision-gate",
        _carry_batch(("R1", "R2")),
    )

    assert result["applied"] is True
    assert "refused" not in result
    assert _load(state_path)["applied_review_batches"]


def test_a_stale_earlier_cycle_carry_task_does_not_back_this_cycles_carry(
    tmp_path: Path,
) -> None:
    """The task looks right - re-queued, pending, [C]-named, carrying R1 - but
    it was re-queued for cycle 1 while state is on cycle 2. Accepting it would
    let one old task launder the same Critical forward cycle after cycle."""
    review = _review(tmp_path, consolidated=CARRY_CONSOLIDATED)
    stale = _carry_task(carry_cycle=1, name="[C1] carry: src/b.py")
    state_path = _carry_state(tmp_path, [stale], ["4"])
    before = state_path.read_bytes()

    result = review_close.close(review, state_path, "decision-gate", _carry_batch())

    assert result["applied"] is False
    assert result["refused"] == "carry_unmatched"
    assert result["reason"] == _carry_reason("R1")
    assert state_path.read_bytes() == before


def test_a_tail_sweep_batch_skips_the_carry_match(tmp_path: Path) -> None:
    """The carry match is scoped to the decision gate, which is where tasks
    get re-queued. A tail-sweep batch must not be refused for an unmatched
    carry - whatever else it may be refused for."""
    review = _review(tmp_path)
    state_path = _state(tmp_path)

    result = review_close.close(
        review,
        state_path,
        "tail-sweep",
        [_finding(MED, "src/carry.py", "carry me", "carry")],
    )

    assert result.get("refused") != "carry_unmatched"
    assert "carry_refs including" not in str(result.get("reason", ""))


@pytest.mark.parametrize(
    ("task", "rework_ids", "unmatched"),
    [
        (_carry_task(), ["4"], False),
        (_carry_task(refs=(" r1  ",)), ["4"], False),
        (_carry_task(task_id=4), ["4"], False),
        (_carry_task(escalation_reason="fable_rescue"), ["4"], False),
        (_carry_task(status="failed"), ["4"], False),
        (_carry_task(refs=("R9",)), ["4"], True),
        (_carry_task(refs=("R10",)), ["4"], True),
        (_carry_task(refs=()), ["4"], True),
        (_carry_task(carry_cycle=1, name="[C1] carry: src/b.py"), ["4"], True),
        (_carry_task(), [], True),
        (_carry_task(task_id="4"), ["9"], True),
        (_carry_task(name="[D2] src/b.py"), ["4"], True),
        (_carry_task(status="completed"), ["4"], True),
        (_carry_task(escalation_reason="model_floor"), ["4"], True),
        (_carry_task(escalation_reason=None), ["4"], True),
    ],
    ids=[
        "matching-task",
        "ref-compared-stripped-and-case-folded",
        "int-task-id-matches-string-rework-id",
        "fable-rescue-requeue-also-backs-a-carry",
        "a-failed-task-is-still-live-enough-to-back-a-carry",
        "task-carries-another-ref",
        "task-carries-a-ref-this-one-is-only-a-prefix-of",
        "task-carries-no-refs",
        "stale-earlier-cycle",
        "not-in-rework-task-ids",
        "another-task-id-was-requeued",
        "D-named-task-is-not-a-carry-requeue",
        "task-already-completed",
        "unrelated-escalation-reason",
        "no-escalation-reason",
    ],
)
def test_carry_unmatched_matches_only_a_live_this_cycle_requeued_task(
    task: dict,
    rework_ids: list[str],
    unmatched: bool,
) -> None:
    row = _carry_row(" r1 ")

    assert review_close._carry_unmatched(row, 2, [task], rework_ids) is unmatched


@pytest.mark.parametrize(
    ("carry_cycle", "unmatched"),
    [(3, False), (2, True)],
    ids=["requeued-for-the-given-cycle", "requeued-for-the-cycle-before"],
)
def test_carry_unmatched_judges_against_the_cycle_it_is_given(
    carry_cycle: int,
    unmatched: bool,
) -> None:
    """The cycle to match is the one the caller passes (the state's current
    `cycle`), not a fixed number: asked about cycle 3, a task re-queued for
    cycle 3 backs the row and the cycle-2 task that backed it last cycle no
    longer does."""
    task = _carry_task(
        carry_cycle=carry_cycle,
        name=f"[C{carry_cycle}] carry: src/b.py",
    )

    assert review_close._carry_unmatched(_carry_row(), 3, [task], ["4"]) is unmatched


def test_a_carry_is_refused_when_no_single_task_satisfies_every_condition(
    tmp_path: Path,
) -> None:
    """Every word a reader skimming state.json for reassurance would find is
    there: a `[C2]`-named task, a carry_refs list, carry_cycle 2, a non-empty
    rework_task_ids, and the ref R1 spelled out in a task description. No ONE
    task carries R1 for this cycle, so the Critical is still unbacked and the
    batch is refused."""
    review = _review(tmp_path, consolidated=CARRY_CONSOLIDATED)
    decoy = {
        "id": "1",
        "name": "original",
        "status": "completed",
        "description": "carry_refs: see R1 in the cycle-2 review",
    }
    state_path = _state(
        tmp_path,
        tasks=[decoy, _carry_task(task_id="5", refs=("R2",))],
        tasks_total=2,
        rework_task_ids=["5"],
    )
    before = state_path.read_bytes()

    result = review_close.close(review, state_path, "decision-gate", _carry_batch())

    assert result["applied"] is False
    assert result["refused"] == "carry_unmatched"
    assert result["reason"] == _carry_reason("R1")
    assert state_path.read_bytes() == before


def test_the_refusal_names_the_first_unmatched_carry_row(tmp_path: Path) -> None:
    """Two rows are carried, R1 then R3, and nothing was re-queued at all: the
    operator is sent to the first unmatched row of their findings file, not the
    last, so the row they will meet first is the one named."""
    review = _review(tmp_path, consolidated=CARRY_CONSOLIDATED)
    state_path = _state(tmp_path)

    result = review_close.close(
        review,
        state_path,
        "decision-gate",
        _carry_batch(("R1", "R3")),
    )

    assert result["applied"] is False
    assert result["refused"] == "carry_unmatched"
    assert result["reason"] == _carry_reason("R1")


def test_carry_unmatched_ignores_task_entries_that_are_not_dicts() -> None:
    """A task list holding junk (a bare string, a null) must not raise: the
    entry is skipped and the surrounding tasks still decide the verdict."""
    junk: list[object] = ["not-a-task", None, 7]

    assert review_close._carry_unmatched(_carry_row(), 2, junk, ["4"]) is True
    assert (
        review_close._carry_unmatched(_carry_row(), 2, [*junk, _carry_task()], ["4"])
        is False
    )
