#!/usr/bin/env python3
"""Tests for cli/review_close.py (PRD 00249 task 4).

Every test runs close() against a real state.json in tmp_path through the
real statectl/state boundary; only the seams a test is about are spied on.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from uuid import uuid4

import pytest

from cli import gate, review_close

CLI_MAIN = Path(__file__).resolve().parent / "__main__.py"
RUN_AUTOPILOT = CLI_MAIN.parent.parent

CRIT = "\U0001f534"
HIGH = "\U0001f7e0"
MED = "\U0001f7e1"

D_LINES = "D1: pass\nD2: fail\nD3: pass\nD4: pass\nD5: pass\n"

# Minted per run, so no implementation can match it without reading the
# review file this test writes.
RUNTIME_ISSUE = f"finding minted at runtime {uuid4().hex}"

# The saved review artifact's consolidated-findings table, carrying three rows.
# Batches applied against it are subsets of these. Every row names a Ref: a
# findings section whose rows key with an empty ref is refused outright now.
CONSOLIDATED = (
    "## Consolidated Findings\n\n"
    "| Ref | Consensus | Severity | Issue | File | Found By |\n"
    "|-----|-----------|----------|-------|------|----------|\n"
    f"| R1 | [2/2] | {HIGH} | wrong default | src/b.py:10 | alice, bob |\n"
    f"| R2 | [2/2] | {HIGH} | {RUNTIME_ISSUE} | src/d.py:4 | alice, bob |\n"
    f"| R3 | [1/2] | {MED} | unclear name | src/c.py:20 | bob |\n\n"
)


def _review(
    tmp_path: Path,
    *,
    d_lines: str = D_LINES,
    verdict: str = "Verdict: 3 findings\n",
    agents: str = "  alice: available\n  bob: available\n",
    extra_frontmatter: str = "",
    consolidated: str = "",
    name: str = "00249-x-review-01.md",
) -> Path:
    text = (
        "---\n"
        "reviewers: alice,bob\n"
        "agents:\n"
        f"{agents}"
        f"{extra_frontmatter}"
        "---\n\n"
        "# Review\n\n"
        "## Alice\n\nOne finding.\n\n"
        "## Bob\n\n"
        f"{d_lines}\n"
        "Some doubts.\n\n"
        f"{consolidated}"
        f"{verdict}"
        "Tests: 12 passed, 0 failed\n"
    )
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return path


def _state(tmp_path: Path, **extra: object) -> Path:
    data = {
        "cycle": 2,
        "tasks": [{"id": "1", "name": "original", "status": "completed"}],
        "tasks_total": 1,
        "rework_task_ids": [],
        "deferred_decisions": [],
        **extra,
    }
    path = tmp_path / "state.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _finding(sev: str, file: str, issue: str, cls: str = "fix") -> dict:
    return {
        "severity": sev,
        "file": file,
        "issue": issue,
        "classification": cls,
        "found_by": ["bob"],
    }


# A findings section that HAS its header but whose only data row is not shaped
# `| [m/n] | ... |`: the gate reads this as its "unreadable-table" problem.
UNREADABLE_TABLE = (
    "## Consolidated Findings\n\n"
    "| Ref | Consensus | Severity | Issue | File | Found By |\n"
    "|-----|-----------|----------|-------|------|----------|\n"
    f"| R1 | 2 of 2 | {HIGH} | wrong default | src/b.py:10 | alice, bob |\n\n"
)

# A review artifact whose top row is a Critical the operator carries forward
# instead of fixing in this cycle.
CARRY_CONSOLIDATED = (
    "## Consolidated Findings\n\n"
    "| Ref | Consensus | Severity | Issue | File | Found By |\n"
    "|-----|-----------|----------|-------|------|----------|\n"
    f"| R1 | [2/2] | {CRIT} | crash on empty input | src/b.py:10 | alice, bob |\n"
    f"| R2 | [2/2] | {HIGH} | wrong default | src/d.py:4 | alice, bob |\n"
    f"| R3 | [1/2] | {MED} | unclear name | src/c.py:20 | bob |\n\n"
)

CARRY_ROWS = (
    (CRIT, "src/b.py:10", "crash on empty input", "R1"),
    (HIGH, "src/d.py:4", "wrong default", "R2"),
    (MED, "src/c.py:20", "unclear name", "R3"),
)


def _carry_batch(carried: tuple[str, ...] = ("R1",)) -> list[dict]:
    """A findings JSON covering every CARRY_CONSOLIDATED ref: the refs named in
    `carried` classified `carry`, the rest discarded, so the findings
    cross-check passes and only the carry match can refuse the batch."""
    return [
        dict(
            _finding(sev, file, issue, "carry" if ref in carried else "discard"),
            ref=ref,
        )
        for sev, file, issue, ref in CARRY_ROWS
    ]


def _carry_task(
    task_id: object = "4",
    *,
    refs: tuple[str, ...] = ("R1",),
    carry_cycle: int = 2,
    name: str = "[C2] carry: src/b.py",
    status: str = "pending",
    escalation_reason: str = "review_flag",
) -> dict:
    """One re-queued carry-forward task: what a `carry` row has to point at."""
    return {
        "id": task_id,
        "name": name,
        "status": status,
        "escalation_reason": escalation_reason,
        "carry_refs": list(refs),
        "carry_cycle": carry_cycle,
    }


def _carry_state(tmp_path: Path, tasks: list[dict], rework_ids: list[str]) -> Path:
    return _state(
        tmp_path,
        tasks=[{"id": "1", "name": "original", "status": "completed"}, *tasks],
        tasks_total=1 + len(tasks),
        rework_task_ids=rework_ids,
    )


def _carry_reason(ref: str, cycle: int = 2) -> str:
    return (
        f"carry row ref {ref} has no cycle-{cycle} [C]-prefixed task in "
        f"rework_task_ids carrying carry_refs including {ref}"
    )


def _findings_file(tmp_path: Path, rows: list[dict]) -> Path:
    path = tmp_path / "findings.json"
    path.write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")
    return path


# The two severities a tail sweep is allowed to carry.
LOW = "⚪"

# One actionable Medium row: the shape every legitimate tail-sweep row has.
TAIL_MED = dict(_finding(MED, "src/c.py:20", "unclear name"), ref="R3")


def _gate_entry(review: Path) -> str:
    """The applied_review_batches entry that unlocks a tail sweep."""
    return f"{review.resolve()}::decision-gate"


def _swept(tmp_path: Path, review: Path, **extra: object) -> Path:
    """State whose decision-gate batch for `review` is already applied, so a
    tail sweep against it is past the before-decision-gate refusal."""
    return _state(tmp_path, applied_review_batches=[_gate_entry(review)], **extra)


def _review_close_cli(
    review: Path,
    state_path: Path,
    findings: Path,
    batch_id: str = "decision-gate",
) -> subprocess.CompletedProcess:
    return subprocess.run(
        [
            sys.executable,
            str(CLI_MAIN),
            "review-close",
            "--review-file",
            str(review),
            "--state",
            str(state_path),
            "--batch-id",
            batch_id,
            "--findings",
            str(findings),
        ],
        capture_output=True,
        text=True,
        cwd=str(RUN_AUTOPILOT),
    )


@pytest.mark.parametrize(
    ("batch_id", "classification"),
    [
        ("decision-gate", "fix"),
        ("tail-sweep", "fix"),
        ("decision-gate", "defer"),
    ],
)
def test_review_close_refuses_on_findings_mismatch(
    tmp_path: Path,
    batch_id: str,
    classification: str,
) -> None:
    """The cross-check is mandatory in close(): a chosen finding the review
    file never recorded is refused, whatever the batch or the classification,
    state stays byte-identical, and the refusal names the offending row."""
    review = _review(tmp_path, consolidated=CONSOLIDATED)
    state_path = _state(tmp_path)
    before = state_path.read_bytes()
    bogus = "an issue no reviewer raised"
    # The file matches a real review row; the issue text does not.
    findings = [_finding(HIGH, "src/b.py:10", bogus, classification)]

    result = review_close.close(review, state_path, batch_id, findings)

    assert result["applied"] is False
    assert result["refused"] == "findings_mismatch"
    assert bogus in result["reason"]
    assert state_path.read_bytes() == before
    assert not Path(f"{state_path}.lock").exists()


def test_close_refuses_an_uncovered_review_row(tmp_path: Path) -> None:
    """Hold stub 00260 / PRD 00264: a review row the findings JSON drops
    entirely is refused exactly like a mismatch - nothing written, named by
    its Ref. Needs a Ref column, so the row's ref is non-empty: bullet rows
    (CONSOLIDATED's shape) always key with an empty ref and are exempt."""
    consolidated = (
        "## Consolidated Findings\n\n"
        "| Ref | Consensus | Severity | Issue | File | Task | Found By |\n"
        "|-----|-----------|----------|-------|------|------|----------|\n"
        f"| R1 | [2/2] | {HIGH} | wrong default | src/b.py:10 | 3 | alice, bob |\n"
        f"| R2 | [2/2] | {HIGH} | {RUNTIME_ISSUE} | src/d.py:4 | 3 | alice, bob |\n"
    )
    review = _review(tmp_path, consolidated=consolidated)
    state_path = _state(tmp_path)
    before = state_path.read_bytes()
    # Only R1 carries a findings-JSON row; R2 is dropped entirely.
    findings = [dict(_finding(HIGH, "src/b.py:10", "wrong default"), ref="R1")]

    result = review_close.close(review, state_path, "decision-gate", findings)

    assert result["applied"] is False
    assert "R2" in result["reason"]
    assert state_path.read_bytes() == before
    assert not Path(f"{state_path}.lock").exists()


def test_tail_sweep_applies_cleanly_against_a_partial_ref_table(tmp_path: Path) -> None:
    """The tail-sweep step's findings JSON deliberately names only a subset of
    the consolidated table's refs (actionable Medium/Low rows); close() must
    not refuse it as uncovered the way a decision-gate batch would."""
    consolidated = (
        "## Consolidated Findings\n\n"
        "| Ref | Consensus | Severity | Issue | File | Task | Found By |\n"
        "|-----|-----------|----------|-------|------|------|----------|\n"
        f"| R1 | [2/2] | {HIGH} | wrong default | src/b.py:10 | 3 | alice, bob |\n"
        f"| R2 | [1/2] | {MED} | unclear name | src/c.py:20 | 3 | bob |\n"
    )
    review = _review(tmp_path, consolidated=consolidated)
    # A tail sweep only applies once this cycle's decision-gate batch has.
    state_path = _state(tmp_path, applied_review_batches=[_gate_entry(review)])
    # Only R2 (the actionable Medium row) carries a findings-JSON entry.
    findings = [dict(_finding(MED, "src/c.py:20", "unclear name"), ref="R2")]

    result = review_close.close(review, state_path, "tail-sweep", findings)

    assert result["applied"] is True
    assert "refused" not in result
    # Applying means recording: a result that only claims it applied, over a
    # state.json this batch never reached, is not an applied batch.
    batches = _load(state_path)["applied_review_batches"]
    assert f"{review.resolve()}::tail-sweep" in batches


def test_close_applies_a_findings_subset_of_the_review(tmp_path: Path) -> None:
    """The counterpart: the cross-check must not block a legitimate batch that
    applies only some of the review's rows. The one row applied carries an
    issue text minted this run, so the review file has to be read.
    Passes against the pre-change code too: applying a legitimate findings
    subset is pre-existing close() behavior the new cross-check must not
    break, not a case the cross-check itself needs to refuse."""
    review = _review(tmp_path, consolidated=CONSOLIDATED)
    state_path = _state(tmp_path)
    # R2 is the one row being fixed; R1 and R3 carry the operator's `discard`
    # disposition, which is coverage without a task or a decision.
    findings = [
        dict(_finding(HIGH, "src/d.py:4", RUNTIME_ISSUE), ref="R2"),
        dict(_finding(HIGH, "src/b.py:10", "wrong default", "discard"), ref="R1"),
        dict(_finding(MED, "src/c.py:20", "unclear name", "discard"), ref="R3"),
    ]

    result = review_close.close(review, state_path, "decision-gate", findings)

    assert result["applied"] is True
    assert "refused" not in result
    assert [t["name"] for t in _load(state_path)["tasks"][1:]] == ["[D2] src/d.py"]


def test_cli_exit_2_on_findings_mismatch(tmp_path: Path) -> None:
    review = _review(tmp_path, consolidated=CONSOLIDATED)
    state_path = _state(tmp_path)
    before = state_path.read_bytes()
    bogus = "an issue no reviewer raised"
    findings = _findings_file(tmp_path, [_finding(HIGH, "src/b.py:10", bogus)])

    proc = _review_close_cli(review, state_path, findings)

    output = proc.stdout + proc.stderr
    assert proc.returncode == 2, output
    assert "findings_mismatch" in output
    # The operator has to learn which row was bogus, not just that one was.
    assert bogus in output
    assert state_path.read_bytes() == before


def test_cli_exit_2_on_findings_uncovered(tmp_path: Path) -> None:
    """The uncovered refusal is mapped to exit 2 the same way the mismatch
    refusal is: a review row no findings-JSON row names is just as much a
    refusal to apply as a row whose findings don't match."""
    consolidated = (
        "## Consolidated Findings\n\n"
        "| Ref | Consensus | Severity | Issue | File | Task | Found By |\n"
        "|-----|-----------|----------|-------|------|------|----------|\n"
        f"| R1 | [2/2] | {HIGH} | wrong default | src/b.py:10 | 3 | alice, bob |\n"
        f"| R2 | [2/2] | {HIGH} | {RUNTIME_ISSUE} | src/d.py:4 | 3 | alice, bob |\n"
    )
    review = _review(tmp_path, consolidated=consolidated)
    state_path = _state(tmp_path)
    before = state_path.read_bytes()
    # Only R1 carries a findings-JSON row; R2 is dropped entirely.
    findings = _findings_file(
        tmp_path,
        [dict(_finding(HIGH, "src/b.py:10", "wrong default"), ref="R1")],
    )

    proc = _review_close_cli(review, state_path, findings)

    output = proc.stdout + proc.stderr
    assert proc.returncode == 2, output
    assert "findings_uncovered" in output
    assert "R2" in output
    assert state_path.read_bytes() == before


def test_cli_accepts_a_carry_classification(tmp_path: Path) -> None:
    """`carry` must be accepted by the CLI's own classification gate
    (_is_chosen_finding/_KNOWN_CLASSIFICATIONS in __main__.py), the layer in
    front of review_close.close() - a findings file holding a `carry` row for
    a re-queued [C{cycle}] row must not be rejected before close() runs. The
    state carries that re-queued task, so close() accepts the carry too."""
    review = _review(tmp_path)
    state_path = _carry_state(tmp_path, [_carry_task()], ["4"])
    findings = _findings_file(
        tmp_path,
        [
            _finding(HIGH, "src/fix.py", "fix me", "fix"),
            dict(_finding(MED, "src/carry.py", "carry me", "carry"), ref="R1"),
        ],
    )

    proc = _review_close_cli(review, state_path, findings)

    assert proc.returncode == 0, proc.stdout + proc.stderr
    # The caller reads what was created out of this JSON line; exiting 0
    # without printing it leaves the orchestrator blind to the new task ids.
    assert "tasks_created" in proc.stdout
    assert "rework_task_ids" in proc.stdout
    assert "lenses_closed" in proc.stdout
    new_tasks = [t for t in _load(state_path)["tasks"] if t["id"] not in {"1", "4"}]
    assert [t["name"] for t in new_tasks] == ["[D2] src/fix.py"]


def test_cli_exits_1_when_the_review_itself_fails_the_gate(tmp_path: Path) -> None:
    """Exit 2 belongs to the findings cross-check (mismatch or uncovered): a
    review file the gate rejects keeps exit 1, even though its findings would
    also mismatch.
    Passes against the pre-change code too: the gate-failure exit path is
    pre-existing, unchanged behavior, not the new exit-2 mismatch path."""
    review = _review(tmp_path, verdict="", consolidated=CONSOLIDATED)
    state_path = _state(tmp_path)
    before = state_path.read_bytes()
    findings = _findings_file(
        tmp_path,
        [_finding(HIGH, "src/b.py:10", "an issue no reviewer raised")],
    )

    proc = _review_close_cli(review, state_path, findings)

    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert state_path.read_bytes() == before


def test_cli_still_exits_1_on_other_not_applied_reasons(tmp_path: Path) -> None:
    """Exit 2 is reserved for the mismatch: the already-applied refusal, whose
    findings do cross-check, keeps the old exit 1.
    Passes against the pre-change code too: the already-applied exit path
    is pre-existing, unchanged behavior, not the new exit-2 mismatch path."""
    review = _review(tmp_path, consolidated=CONSOLIDATED)
    state_path = _state(tmp_path)
    findings = _findings_file(
        tmp_path,
        [
            dict(_finding(HIGH, "src/b.py:10", "wrong default"), ref="R1"),
            dict(_finding(HIGH, "src/d.py:4", RUNTIME_ISSUE, "discard"), ref="R2"),
            dict(_finding(MED, "src/c.py:20", "unclear name", "discard"), ref="R3"),
        ],
    )

    first = _review_close_cli(review, state_path, findings)
    second = _review_close_cli(review, state_path, findings)

    assert first.returncode == 0, first.stdout + first.stderr
    assert second.returncode == 1, second.stdout + second.stderr
    assert "findings_mismatch" not in second.stdout + second.stderr


# Passes against the pre-change code too: this pins pre-existing,
# unchanged lens-bookkeeping behavior, not the new findings-mismatch
# cross-check this diff adds (flagged touched only by its proximity to the
# new tests above, not by any edit to its own body).
def test_close_leaves_no_lens_running(tmp_path: Path) -> None:
    review = _review(
        tmp_path,
        agents=(
            "  alice: available\n"
            "  blake: available\n"
            "  bob: available\n"
            "  carl: disabled\n"
            "  eve: available\n"
        ),
    )
    state_path = _state(tmp_path)

    result = review_close.close(review, state_path, "decision-gate", [])

    assert result["applied"] is True
    lenses = _load(state_path)["review_lenses"]
    assert "running" not in lenses.values()
    assert lenses == {
        "consensus": "done",
        "blind": "done",
        "doubt": "done",
        "ui": "skipped",
        "fable": "done",
    }


# A persona with no line at all under agents: (not even "unavailable") must
# still close its mapped lens as "failed", not leave it absent. Fails against
# the current _lens_states, which only emits a key for personas present in
# the agents: block, so "blind" never gets written here.
def test_close_fails_a_lens_whose_persona_is_absent_from_agents_block(
    tmp_path: Path,
) -> None:
    review = _review(
        tmp_path,
        # blake has no line here at all: not "available", not "unavailable".
        agents="  alice: available\n  bob: available\n",
    )
    state_path = _state(tmp_path)

    result = review_close.close(review, state_path, "decision-gate", [])

    assert result["applied"] is True
    lenses = _load(state_path)["review_lenses"]
    assert "blind" in lenses
    assert lenses["blind"] == "failed"


def test_refuses_unreadable_table_instead_of_applying(tmp_path: Path) -> None:
    """A review file that HAS a '## Consolidated Findings' section but whose
    table cannot be read is refused: there is nothing to cross-check the
    operator's findings JSON against, so applying it would be a blind write
    of whatever the JSON happens to say."""
    review = _review(tmp_path, consolidated=UNREADABLE_TABLE)
    state_path = _state(tmp_path)
    before = state_path.read_bytes()
    findings = [dict(_finding(HIGH, "src/b.py:10", "wrong default"), ref="R1")]

    result = review_close.close(review, state_path, "decision-gate", findings)

    assert result["applied"] is False
    assert result["refused"] == "findings_malformed"
    assert result["reason"] == gate._FINDINGS_PROBLEMS["unreadable-table"]
    assert state_path.read_bytes() == before
    assert not Path(f"{state_path}.lock").exists()
    assert not Path(f"{state_path}.bak").exists()


def test_a_missing_findings_section_still_applies_as_legacy_malformed(
    tmp_path: Path,
) -> None:
    """The other half of the malformed split: a review file with no findings
    section at all keeps its legacy pass-through - it applies and only reports
    the cross-check. Refusing every malformed verdict would strand every
    review artifact written before the table existed."""
    review = _review(tmp_path)
    state_path = _state(tmp_path)
    findings = [_finding(HIGH, "src/b.py:10", "wrong default")]

    result = review_close.close(review, state_path, "decision-gate", findings)

    assert result["applied"] is True
    assert "refused" not in result
    assert result["findings_cross_check"] == "malformed"
    assert [t["name"] for t in _load(state_path)["tasks"][1:]] == ["[D2] src/b.py"]


def _pin_verdict(
    monkeypatch: pytest.MonkeyPatch,
    tag: str,
    detail: str,
) -> None:
    """Fix the cross-check's answer at the seam close() consults it through,
    so the review file's own text cannot carry the signal instead."""
    monkeypatch.setattr(
        review_close.gate,
        "findings_verdict",
        lambda *_a, **_k: (tag, detail),
    )


def test_an_unreadable_table_verdict_is_refused_whatever_the_file_looks_like(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Which malformed verdict refuses is the cross-check's call, not the
    review text's: a file with no table at all is refused once the cross-check
    reports the unreadable-table problem, and the operator gets that problem's
    own wording back as the reason."""
    review = _review(tmp_path)
    state_path = _state(tmp_path)
    before = state_path.read_bytes()
    _pin_verdict(monkeypatch, "malformed", gate._FINDINGS_PROBLEMS["unreadable-table"])

    result = review_close.close(
        review,
        state_path,
        "decision-gate",
        [_finding(HIGH, "src/b.py:10", "wrong default")],
    )

    assert result["applied"] is False
    assert result["refused"] == "findings_malformed"
    assert result["reason"] == gate._FINDINGS_PROBLEMS["unreadable-table"]
    assert state_path.read_bytes() == before
    assert not Path(f"{state_path}.lock").exists()


def test_a_no_section_verdict_applies_however_long_its_wording_is(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The legacy pass-through follows the no-section problem itself, not the
    shape of its message: given an unreadable table in the file but a
    no-section verdict at the seam - here worded longer than the
    unreadable-table problem - the batch still applies and reports the
    cross-check."""
    review = _review(tmp_path, consolidated=UNREADABLE_TABLE)
    state_path = _state(tmp_path)
    monkeypatch.setitem(
        gate._FINDINGS_PROBLEMS,
        "no-section",
        "no '## Consolidated Findings' section in the review file " + "(x)" * 60,
    )
    _pin_verdict(monkeypatch, "malformed", gate._FINDINGS_PROBLEMS["no-section"])

    result = review_close.close(
        review,
        state_path,
        "decision-gate",
        [_finding(HIGH, "src/b.py:10", "wrong default")],
    )

    assert result["applied"] is True
    assert "refused" not in result
    assert result["findings_cross_check"] == "malformed"
    assert [t["name"] for t in _load(state_path)["tasks"][1:]] == ["[D2] src/b.py"]


def test_matched_carry_is_accepted(tmp_path: Path) -> None:
    """The carry check's accepting side: R1 is classified `carry` and state
    holds this cycle's re-queued [C2] task carrying ref R1, so the batch
    applies - and the carry row still writes no task of its own."""
    review = _review(tmp_path, consolidated=CARRY_CONSOLIDATED)
    state_path = _carry_state(tmp_path, [_carry_task()], ["4"])

    result = review_close.close(review, state_path, "decision-gate", _carry_batch())

    assert result["applied"] is True
    assert "refused" not in result
    # This batch's table reads cleanly, so there is no cross-check problem to
    # report: a result stamped "malformed" here would be a false alarm.
    assert "findings_cross_check" not in result
    data = _load(state_path)
    assert [t["id"] for t in data["tasks"]] == ["1", "4"]
    assert data["applied_review_batches"] == [f"{review.resolve()}::decision-gate"]


def test_carry_on_critical_without_requeued_task_is_refused(tmp_path: Path) -> None:
    """The escape this closes: the operator classifies a Critical as `carry`
    but nothing was re-queued for it, so the Critical would leave the run
    while the review batch is stamped applied. Refused before the lock, so
    state.json is byte-unchanged."""
    review = _review(tmp_path, consolidated=CARRY_CONSOLIDATED)
    state_path = _state(tmp_path)
    before = state_path.read_bytes()

    result = review_close.close(review, state_path, "decision-gate", _carry_batch())

    assert result["applied"] is False
    assert result["refused"] == "carry_unmatched"
    assert result["reason"] == _carry_reason("R1")
    assert state_path.read_bytes() == before
    assert not Path(f"{state_path}.lock").exists()
    assert not Path(f"{state_path}.bak").exists()


def test_ghost_carry_ref_is_refused(tmp_path: Path) -> None:
    """Two rows are carried, R1 and R3, and the only re-queued task carries
    R1 alone: R3 is a ghost. Every other condition on that task holds, so
    only the ref comparison can refuse the batch, and a check that stopped at
    the first matching carry row would wave R3 through."""
    review = _review(tmp_path, consolidated=CARRY_CONSOLIDATED)
    state_path = _carry_state(tmp_path, [_carry_task(refs=("R1",))], ["4"])
    before = state_path.read_bytes()

    result = review_close.close(
        review,
        state_path,
        "decision-gate",
        _carry_batch(("R1", "R3")),
    )

    assert result["applied"] is False
    assert result["refused"] == "carry_unmatched"
    assert result["reason"] == _carry_reason("R3")
    assert state_path.read_bytes() == before
    assert not Path(f"{state_path}.lock").exists()


def test_tail_sweep_refused_before_decision_gate_applied(tmp_path: Path) -> None:
    """A tail sweep is a cycle's second batch: run before this cycle's
    decision-gate batch is applied, it would stamp a cycle whose Critical and
    High dispositions were never recorded. Two other artifacts' decision-gate
    entries are seeded, so neither a non-empty applied_review_batches nor a
    same-file-name entry from another directory can satisfy it."""
    review = _review(tmp_path)
    other = (tmp_path / "other-02.md").resolve()
    namesake = (tmp_path / "sub" / review.name).resolve()
    state_path = _state(
        tmp_path,
        applied_review_batches=[
            f"{other}::decision-gate",
            f"{namesake}::decision-gate",
        ],
    )
    before = state_path.read_bytes()

    result = review_close.close(review, state_path, "tail-sweep", [TAIL_MED])

    assert result["applied"] is False
    assert result["refused"] == "tail_sweep_before_decision_gate"
    assert "decision-gate" in result["reason"]
    assert state_path.read_bytes() == before
    assert not Path(f"{state_path}.lock").exists()


@pytest.mark.parametrize(
    ("rows", "named", "unnamed"),
    [
        (
            [
                TAIL_MED,
                dict(_finding(HIGH, "src/b.py:10", "wrong default"), ref="R1"),
                dict(_finding(CRIT, "src/a.py:3", "crash on empty input"), ref="R2"),
            ],
            "R1",
            "R2",
        ),
        ([_finding(CRIT, "src/a.py:3", "crash on empty input")], "src/a.py:3", "R1"),
    ],
)
def test_tail_sweep_refuses_rows_above_medium(
    tmp_path: Path,
    rows: list[dict],
    named: str,
    unnamed: str,
) -> None:
    """A tail sweep closes Medium and Low rows only: a red or orange row is the
    decision gate's business, and letting one through here would close it
    without a dispatch. The reason names the FIRST offending row, by Ref when
    it has one and by file when it does not, so the operator can move it."""
    review = _review(tmp_path)
    state_path = _swept(tmp_path, review)
    before = state_path.read_bytes()

    result = review_close.close(review, state_path, "tail-sweep", rows)

    assert result["applied"] is False
    assert result["refused"] == "tail_sweep_above_medium"
    assert named in result["reason"]
    assert unnamed not in result["reason"]
    assert state_path.read_bytes() == before
    assert not Path(f"{state_path}.lock").exists()


def test_empty_tail_sweep_is_refused_and_records_nothing(tmp_path: Path) -> None:
    """An empty tail sweep is a sweep that never ran: applying it would stamp
    the cycle swept. Refused even though every other condition holds, and
    state.json is byte-identical, so the batch is not recorded either."""
    review = _review(tmp_path)
    state_path = _swept(tmp_path, review)
    before = state_path.read_bytes()

    result = review_close.close(review, state_path, "tail-sweep", [])

    assert result["applied"] is False
    assert result["refused"] == "tail_sweep_empty"
    assert result["reason"] == "tail sweep findings must not be empty"
    assert state_path.read_bytes() == before
    assert not Path(f"{state_path}.lock").exists()
