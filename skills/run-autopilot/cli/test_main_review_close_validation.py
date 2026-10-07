#!/usr/bin/env python3
"""Tests for cli/__main__.py's review-close finding validation (PRD 00249,
finding F6 at __main__.py:1017).

_is_chosen_finding is the gate `_run_review_close` runs over every row of
the findings JSON before review_close.close() is ever called, so a row it
rejects can never reach a mutation.

The second half (PRD 00265 task 2) pins `_run_review_close`'s exit-code
mapping: every refusal close() can return is a validation refusal worth exit
2, distinct from the exit 1 a plain "not applied" carries.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from cli import __main__ as cli_main
from cli import gate, review_close
from cli.test_review_close import (
    CARRY_CONSOLIDATED,
    CONSOLIDATED,
    HIGH,
    UNREADABLE_TABLE,
    _carry_batch,
    _finding,
    _findings_file,
    _review,
    _review_close_cli,
    _state,
)

# Every refusal kind `_run_review_close` has to report as exit 2.
REFUSAL_KINDS = (
    "findings_mismatch",
    "findings_uncovered",
    "findings_ref_required",
    "findings_malformed",
    "carry_unmatched",
    "carry_in_tail_sweep",
    "tail_sweep_before_decision_gate",
    "tail_sweep_empty",
    "tail_sweep_above_medium",
    "tail_sweep_duplicates_deferral",
    "already_applied_duplicate",
)

# A readable findings table with no Ref column at all: under coverage (every
# batch but tail-sweep) the gate calls this the ref-required problem.
NO_REF_COLUMN = (
    "## Consolidated Findings\n\n"
    "| Consensus | Severity | Issue | File | Found By |\n"
    "|-----------|----------|-------|------|----------|\n"
    f"| [2/2] | {HIGH} | wrong default | src/b.py:10 | alice, bob |\n\n"
)


def _row(classification: str, **overrides: object) -> dict:
    base = {
        "classification": classification,
        "severity": "\U0001f7e0",
        "file": "src/x.py",
        "issue": "something",
        "found_by": ["bob"],
    }
    base.update(overrides)
    return base


def test_rejects_an_unknown_classification_value() -> None:
    assert cli_main._is_chosen_finding(_row("fxi")) is False


def test_accepts_the_known_non_actionable_classifications() -> None:
    assert cli_main._is_chosen_finding(_row("verify")) is True
    assert cli_main._is_chosen_finding(_row("discard")) is True


def test_accepts_fix_and_defer_with_complete_string_fields() -> None:
    assert cli_main._is_chosen_finding(_row("fix")) is True
    assert cli_main._is_chosen_finding(_row("defer")) is True


def test_rejects_found_by_that_is_not_a_list() -> None:
    assert cli_main._is_chosen_finding(_row("fix", found_by="bob")) is False


def test_rejects_found_by_containing_a_non_string_element() -> None:
    assert cli_main._is_chosen_finding(_row("fix", found_by=["bob", 2])) is False


def test_accepts_found_by_as_a_list_of_strings() -> None:
    assert cli_main._is_chosen_finding(_row("fix", found_by=["bob", "carl"])) is True


def test_rejects_plain_word_severity() -> None:
    assert cli_main._is_chosen_finding(_row("fix", severity="CRITICAL")) is False


def test_rejects_an_actionable_row_missing_the_file_or_issue_close_reads() -> None:
    """close() reads `file` and `issue` off every fix/defer row to name the
    task and quote the finding, so a row without them must never reach it."""
    assert cli_main._is_chosen_finding(_row("fix", file=None)) is False
    assert cli_main._is_chosen_finding(_row("defer", issue=None)) is False


def test_rejects_a_findings_entry_that_is_not_a_row() -> None:
    """A JSON array of bare strings is not a findings file: each entry has to
    be an object before any field of it can be read."""
    assert cli_main._is_chosen_finding("fix") is False
    assert cli_main._is_chosen_finding(["fix"]) is False


def _cli_refusal(tmp_path: Path, consolidated: str, findings: list[dict]) -> tuple:
    """Run the real CLI over a review file the cross-check or the carry match
    must refuse, and prove the run left state.json alone."""
    review = _review(tmp_path, consolidated=consolidated)
    state_path = _state(tmp_path)
    before = state_path.read_bytes()

    proc = _review_close_cli(review, state_path, _findings_file(tmp_path, findings))

    assert state_path.read_bytes() == before, "a refused batch must write nothing"
    return proc.returncode, proc.stdout + proc.stderr


def test_cli_exits_2_when_a_findings_row_mismatches(tmp_path: Path) -> None:
    code, out = _cli_refusal(
        tmp_path,
        CONSOLIDATED,
        [_finding(HIGH, "src/b.py:10", "an issue no reviewer raised")],
    )

    assert code == 2, out
    assert "findings_mismatch" in out


def test_cli_exits_2_when_a_review_row_has_no_disposition(tmp_path: Path) -> None:
    """R1 is the only ref the findings JSON names; R2 and R3 are dropped."""
    code, out = _cli_refusal(
        tmp_path,
        CONSOLIDATED,
        [dict(_finding(HIGH, "src/b.py:10", "wrong default"), ref="R1")],
    )

    assert code == 2, out
    assert "findings_uncovered" in out


def test_cli_exits_2_when_the_table_has_no_ref_column(tmp_path: Path) -> None:
    code, out = _cli_refusal(
        tmp_path,
        NO_REF_COLUMN,
        [_finding(HIGH, "src/b.py:10", "wrong default")],
    )

    assert code == 2, out
    assert "findings_ref_required" in out
    # Naming the kind is not enough: the operator has to be told what to fix,
    # which is the cross-check's own diagnostic for the missing Ref column.
    assert gate._FINDINGS_PROBLEMS["ref-required"] in out


def test_cli_exits_2_when_the_findings_table_cannot_be_read(tmp_path: Path) -> None:
    code, out = _cli_refusal(
        tmp_path,
        UNREADABLE_TABLE,
        [dict(_finding(HIGH, "src/b.py:10", "wrong default"), ref="R1")],
    )

    assert code == 2, out
    assert "findings_malformed" in out


def test_cli_exits_2_when_a_carry_row_has_no_requeued_task(tmp_path: Path) -> None:
    code, out = _cli_refusal(tmp_path, CARRY_CONSOLIDATED, _carry_batch())

    assert code == 2, out
    assert "carry_unmatched" in out
    assert "R1" in out


def _argv(review: Path, state_path: Path, findings: Path) -> list[str]:
    return [
        "review-close",
        "--review-file",
        str(review),
        "--state",
        str(state_path),
        "--batch-id",
        "decision-gate",
        "--findings",
        str(findings),
    ]


def _run_main(tmp_path: Path) -> int:
    review = _review(tmp_path)
    state_path = _state(tmp_path)
    findings = _findings_file(
        tmp_path,
        [_finding(HIGH, "src/b.py:10", "wrong default")],
    )
    return cli_main.main(_argv(review, state_path, findings))


@pytest.mark.parametrize("kind", REFUSAL_KINDS)
def test_every_refusal_kind_exits_2_and_names_itself(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture,
    kind: str,
) -> None:
    """Exit 1 is the generic "not applied"; a refusal is a validation failure
    the caller must be able to tell apart, so every kind maps to 2 and the
    operator is told which one fired. The tail-sweep carve-outs and the
    duplicate stamp have preconditions this task does not specify, so the
    mapping is driven at the seam close() returns through."""
    monkeypatch.setattr(
        review_close,
        "close",
        lambda *_a, **_k: {
            "applied": False,
            "refused": kind,
            "reason": f"{kind} happened",
        },
    )

    code = _run_main(tmp_path)

    captured = capsys.readouterr()
    assert code == 2
    assert kind in captured.out + captured.err


def test_a_refusal_kind_outside_todays_list_also_exits_2(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture,
) -> None:
    """A `refused` key is what makes a result a refusal, so the next kind
    close() learns to return is exit 2 the day it is added - a mapping that
    enumerates only today's kinds would quietly call it a plain "not
    applied"."""
    monkeypatch.setattr(
        review_close,
        "close",
        lambda *_a, **_k: {
            "applied": False,
            "refused": "future_kind",
            "reason": "future_kind happened",
        },
    )

    code = _run_main(tmp_path)

    captured = capsys.readouterr()
    assert code == 2
    assert "future_kind" in captured.out + captured.err


def test_a_not_applied_result_with_no_refused_key_still_exits_1(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The already-applied no-op is not a refusal: it keeps exit 1, so a
    caller treating 2 as "the batch was rejected" is not misled by a replay."""
    monkeypatch.setattr(
        review_close,
        "close",
        lambda *_a, **_k: {"applied": False, "reason": "already applied"},
    )

    assert _run_main(tmp_path) == 1


def test_an_applied_batch_exits_0_after_reporting_what_it_created(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture,
) -> None:
    """Exit 0 alone tells the caller nothing: the applied result is the only
    place the new task ids and the closed lenses are reported, so it has to be
    printed before the exit."""
    applied = {
        "applied": True,
        "tasks_created": ["2"],
        "rework_task_ids": ["2"],
        "lenses_closed": {"consensus": "done"},
    }
    monkeypatch.setattr(review_close, "close", lambda *_a, **_k: applied)

    code = _run_main(tmp_path)

    assert code == 0
    assert json.loads(capsys.readouterr().out) == applied
