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
    """A carry row with no ref cannot be matched to any re-queued task - but
    with no `## Consolidated Findings` section to check it against either,
    the findings cross-check now refuses first, matching `gate --findings`'s
    own exit 2 on this exact input, before close() ever reaches the carry
    match. The "(none)" naming this row would otherwise earn is pinned
    directly against `_carry_reason` in
    `test_carry_refusal_names_no_usable_ref_for_a_ref_less_row`."""
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
    assert result["refused"] == "findings_malformed"
    assert "yet the findings JSON names 1 rows" in result["reason"]
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
    assert result["reason"] == _carry_reason("R1", tasks=[stale], rework_ids=["4"])
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
        (_carry_task(name="[D2] src/b.py"), ["4"], False),
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
        "D-named-requeued-task-backs-a-carry",
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


def test_a_requeued_d_task_with_correct_stamps_backs_a_carry(tmp_path: Path) -> None:
    """Dropping the `[D` exclusion means a D-named task (heidi's own naming,
    not just `[C{cycle}]`) backs a carry row when every other condition
    holds."""
    review = _review(tmp_path, consolidated=CARRY_CONSOLIDATED)
    task = _carry_task(
        refs=("R2",),
        name="[D1] src/d.py",
        escalation_reason="fable_rescue",
    )
    state_path = _carry_state(tmp_path, [task], ["4"])

    result = review_close.close(
        review, state_path, "decision-gate", _carry_batch(("R2",))
    )

    assert result["applied"] is True
    assert "refused" not in result


def test_a_fresh_d_task_with_no_escalation_reason_is_refused(tmp_path: Path) -> None:
    """A D-named task is eligible now, but still has to be a genuine
    escalation requeue - one carrying no `escalation_reason` at all is not,
    and the refusal names that exact failing field."""
    review = _review(tmp_path, consolidated=CARRY_CONSOLIDATED)
    task = _carry_task(name="[D1] src/d.py", escalation_reason=None)
    state_path = _carry_state(tmp_path, [task], ["4"])
    before = state_path.read_bytes()

    result = review_close.close(review, state_path, "decision-gate", _carry_batch())

    assert result["applied"] is False
    assert result["refused"] == "carry_unmatched"
    assert (
        "escalation_reason: None is not review_flag or fable_rescue" in result["reason"]
    )
    assert state_path.read_bytes() == before


def test_a_completed_carry_task_is_still_refused(tmp_path: Path) -> None:
    """A re-queued task that has already completed can no longer carry
    anything forward - its work is done, so it cannot still be "carrying" a
    Critical the operator deferred."""
    review = _review(tmp_path, consolidated=CARRY_CONSOLIDATED)
    task = _carry_task(status="completed")
    state_path = _carry_state(tmp_path, [task], ["4"])
    before = state_path.read_bytes()

    result = review_close.close(review, state_path, "decision-gate", _carry_batch())

    assert result["applied"] is False
    assert result["refused"] == "carry_unmatched"
    assert "status: completed" in result["reason"]
    assert state_path.read_bytes() == before


@pytest.mark.parametrize(
    ("task", "rework_ids", "expected_fragment"),
    [
        (
            dict(_carry_task(), escalation_reason=None),
            ["4"],
            'closest task 4 "[C2] carry: src/b.py" fails escalation_reason: '
            "None is not review_flag or fable_rescue",
        ),
        (
            dict(_carry_task(), carry_cycle=1),
            ["4"],
            'closest task 4 "[C2] carry: src/b.py" fails carry_cycle: 1 is not 2',
        ),
        (
            dict(_carry_task(), id="9"),
            ["4"],
            'closest task 9 "[C2] carry: src/b.py" fails rework_task_ids: 9 is not listed',
        ),
        (
            dict(_carry_task(), status="completed"),
            ["4"],
            'closest task 4 "[C2] carry: src/b.py" fails status: completed',
        ),
    ],
    ids=[
        "no-escalation-reason",
        "stale-carry-cycle",
        "id-not-in-rework-task-ids",
        "completed",
    ],
)
def test_carry_refusal_names_the_closest_task_and_its_first_failing_condition(
    task: dict,
    rework_ids: list[str],
    expected_fragment: str,
) -> None:
    """Among the candidates whose `carry_refs` list the ref, the reason names
    the one passing the longest run of conditions in order, and its exact
    first failing field - not a generic "no task backs this" message."""
    reason = review_close._carry_reason(_carry_row(), 2, [task], rework_ids)

    assert expected_fragment in reason


def test_carry_refusal_names_no_task_lists_the_ref_when_no_candidate_exists() -> None:
    """A ref no task's `carry_refs` mentions at all gets the narrower
    "no task lists" message, never a closest-task guess among tasks that
    were never candidates in the first place."""
    reason = review_close._carry_reason(
        _carry_row(), 2, [_carry_task(refs=("R9",))], ["4"]
    )

    assert reason == "carry row ref R1: no task lists R1 in carry_refs"


def test_carry_refusal_names_no_usable_ref_for_a_ref_less_row() -> None:
    """A carry row with no ref at all is refused before any task is even
    considered: "(none)" is the row's own problem, not a task mismatch."""
    reason = review_close._carry_reason(_carry_row(None), 2, [_carry_task()], ["4"])

    assert (
        reason
        == "carry row ref (none): a carry row needs a ref to match a re-queued task"
    )


def test_carry_unmatched_ignores_task_entries_that_are_not_dicts() -> None:
    """A task list holding junk (a bare string, a null) must not raise: the
    entry is skipped and the surrounding tasks still decide the verdict."""
    junk: list[object] = ["not-a-task", None, 7]

    assert review_close._carry_unmatched(_carry_row(), 2, junk, ["4"]) is True
    assert (
        review_close._carry_unmatched(_carry_row(), 2, [*junk, _carry_task()], ["4"])
        is False
    )
