#!/usr/bin/env python3
"""Low-severity review-verb corrections (#12, #13, #14, #17, #20, #24).

Six approved corrections to the review verbs: the tail sweep's open-deferral
refusal and the six keys a deferred entry carries, the coverage refusal naming
every uncovered ref, the sweep reporting no lenses closed, a persona absent
from `agents:` closing its dispatch row as lost, a refused batch leaving the
state backup alone, and a dash-led dispatch row id never reaching an argv.

They live here because test_review_close.py and test_gate_findings_table.py are
both within a few lines of the 800-line limit; fixtures are shared from
test_review_close.py.
"""

from __future__ import annotations

import os
from pathlib import Path
from uuid import uuid4

import pytest

from cli import review_close
from cli.test_review_close import (
    CARRY_CONSOLIDATED,
    HIGH,
    LOW,
    MED,
    RUNTIME_ISSUE,
    TAIL_MED,
    _carry_batch,
    _finding,
    _load,
    _review,
    _state,
    _swept,
)

# An open deferral sharing TAIL_MED's (severity, file) pair but not its issue:
# the pair is what settles a finding, not the wording of it.
OPEN_DEFERRAL = {
    "issue": "deferred last cycle",
    "severity": MED,
    "file": "src/c.py:20",
    "reason": "needs a design call",
}

# A second open deferral no swept row collides with: the bystander.
OTHER_DEFERRAL = dict(OPEN_DEFERRAL, file="src/other.py:7")

# Refs minted per run (the gate reads a ref cell as `R<digits>`), so no
# implementation can name an uncovered ref without reading the table below.
_REF_SEED = uuid4().int % 10**9
REF_COVERED = f"R{_REF_SEED}"
REF_LOOSE_HIGH = f"R{_REF_SEED + 1}"
REF_LOOSE_MED = f"R{_REF_SEED + 2}"

# Dispatch row ids no implementation can have seen before this run: two for
# the personas absent from `agents:`, one for the disabled persona, and one
# leading with a dash.
LOST_ROWS = (f"d-{uuid4().hex}", f"d-{uuid4().hex}")
DISABLED_ROW = f"d-{uuid4().hex}"
DASH_ID = f"-{uuid4().hex}"

# A consolidated table with three Ref'd rows, so a findings JSON naming one of
# them leaves TWO uncovered - the case a refusal naming only the first hides.
THREE_ROWS = (
    "## Consolidated Findings\n\n"
    "| Ref | Consensus | Severity | Issue | File | Task | Found By |\n"
    "|-----|-----------|----------|-------|------|------|----------|\n"
    f"| {REF_COVERED} | [2/2] | {HIGH} | wrong default | src/b.py:10 | 3 | alice, bob |\n"
    f"| {REF_LOOSE_HIGH} | [2/2] | {HIGH} | {RUNTIME_ISSUE} | src/d.py:4 | 3 | alice, bob |\n"
    f"| {REF_LOOSE_MED} | [1/2] | {MED} | unclear name | src/c.py:20 | 3 | bob |\n"
)

CARRY_HINT = "(re-queued [C] rows use classification carry)"


def _dispatch_argv(monkeypatch: pytest.MonkeyPatch) -> list[list[str]]:
    """Capture the argv of every dispatch-row subprocess close() builds."""
    commands: list[list[str]] = []
    monkeypatch.setattr(
        review_close.subprocess,
        "run",
        lambda cmd, **_kwargs: commands.append(cmd),
    )
    return commands


def _ended(commands: list[list[str]]) -> dict[str, str]:
    """{row id: closing --outcome} for every captured dispatch argv."""
    return {
        cmd[cmd.index("end") + 1]: cmd[cmd.index("--outcome") + 1] for cmd in commands
    }


def _deferral_entry(cycle: int) -> dict:
    """The `deferred_decisions` entry the orchestrator contract requires."""
    return {
        "cycle": cycle,
        "issue": "later",
        "severity": MED,
        "file": "src/d.py:4",
        "action": "deferred",
        "reason": "deferred by review-close",
    }


def _gate_lenses(tmp_path: Path, agents: str, name: str) -> dict:
    """`lenses_closed` of one decision-gate batch over an `agents:` block."""
    home = tmp_path / name
    home.mkdir()
    review = _review(home, agents=agents)
    result = review_close.close(review, _state(home), "decision-gate", [])
    assert result["applied"] is True
    return result["lenses_closed"]


def _prelock_refusals(tmp_path: Path, state_path: Path, bare_state: Path) -> list[dict]:
    """The three refusals close() reaches before any state mutation starts: a
    review file failing the shape gate, an uncovered consolidated row, and a
    carry row no re-queued task backs."""
    return [
        review_close.close(
            _review(tmp_path, verdict="", name="gate-01.md"),
            state_path,
            "decision-gate",
            [_finding(HIGH, "src/b.py:10", "wrong default")],
        ),
        review_close.close(
            _review(tmp_path, consolidated=THREE_ROWS, name="uncovered-01.md"),
            state_path,
            "decision-gate",
            [dict(_finding(HIGH, "src/b.py:10", "wrong default"), ref=REF_COVERED)],
        ),
        review_close.close(
            _review(tmp_path, consolidated=CARRY_CONSOLIDATED, name="carry-01.md"),
            bare_state,
            "decision-gate",
            _carry_batch(),
        ),
    ]


def test_tail_sweep_refuses_an_open_deferral(tmp_path: Path) -> None:
    """A swept row the operator already deferred would re-open settled work, so
    the sweep is refused instead of applying the row a second time. The match is
    the (severity, file) pair, not the issue text: this row's issue differs from
    the deferral's and it is still refused. Two deferrals are open and only one
    collides, so the reason has to name that one and leave the bystander out, or
    the operator goes looking at the wrong deferral. The batch's first row
    duplicates nothing, so a check reading only row one would wave it through.
    Severity is half the key: a Low row at the same file as a Medium deferral
    settles nothing and still sweeps."""
    review = _review(tmp_path)
    state_path = _swept(
        tmp_path,
        review,
        deferred_decisions=[OTHER_DEFERRAL, OPEN_DEFERRAL],
    )
    before = state_path.read_bytes()
    rows = [dict(_finding(LOW, "src/a.py:3", "stale comment"), ref="R1"), TAIL_MED]

    result = review_close.close(review, state_path, "tail-sweep", rows)

    assert result["applied"] is False
    assert result["refused"] == "tail_sweep_duplicates_deferral"
    assert MED in result["reason"]
    assert "src/c.py:20" in result["reason"]
    assert OTHER_DEFERRAL["file"] not in result["reason"]
    assert state_path.read_bytes() == before
    assert not Path(f"{state_path}.lock").exists()

    quiet = tmp_path / "quiet"
    quiet.mkdir()
    other_severity = review_close.close(
        review,
        _swept(quiet, review, deferred_decisions=[OPEN_DEFERRAL]),
        "tail-sweep",
        [dict(_finding(LOW, "src/c.py:20", "stale name"), ref="R3")],
    )

    assert other_severity["applied"] is True


def test_deferred_entries_carry_cycle_and_action(tmp_path: Path) -> None:
    """The orchestrator reads `deferred_decisions` to report which cycle parked
    a finding and what was done with it, so every entry review-close appends
    carries six keys, not four. The cycle is whichever cycle the state is in,
    so two closes against states in cycle 5 and cycle 7 file their deferral
    under 5 and 7: a constant stamp would park one of them in the wrong
    cycle, and the operator would hunt a deferral that cycle never made."""
    review = _review(tmp_path)
    filed: dict[int, list] = {}

    for cycle in (5, 7):
        home = tmp_path / f"cycle-{cycle}"
        home.mkdir()
        state_path = _state(home, cycle=cycle)

        result = review_close.close(
            review,
            state_path,
            "decision-gate",
            [_finding(MED, "src/d.py:4", "later", "defer")],
        )

        assert result["applied"] is True
        filed[cycle] = _load(state_path)["deferred_decisions"]

    assert filed[5] == [_deferral_entry(5)]
    assert filed[7] == [_deferral_entry(7)]


def test_coverage_refusal_lists_every_uncovered_ref(tmp_path: Path) -> None:
    """Two consolidated rows have no disposition. Naming only the first costs
    the operator a whole re-run per missing row, so one message names them all -
    and ends with the hint that a re-queued row is covered by a `carry` row,
    which is the disposition people miss. The covered ref stays out of it. The
    refs are minted per run, so the message has to be read off this table."""
    review = _review(tmp_path, consolidated=THREE_ROWS)
    state_path = _state(tmp_path)
    before = state_path.read_bytes()
    findings = [dict(_finding(HIGH, "src/b.py:10", "wrong default"), ref=REF_COVERED)]

    result = review_close.close(review, state_path, "decision-gate", findings)

    assert result["applied"] is False
    assert result["refused"] == "findings_uncovered"
    assert REF_LOOSE_HIGH in result["reason"]
    assert REF_LOOSE_MED in result["reason"]
    assert REF_COVERED not in result["reason"]
    assert result["reason"].endswith(CARRY_HINT)
    assert state_path.read_bytes() == before


def test_tail_sweep_reports_no_lenses_closed(tmp_path: Path) -> None:
    """A tail sweep closes no lens: it runs after the lenses are already done,
    and it deliberately leaves `review_lenses` alone, in the report and in
    state.json alike. Reporting the review file's lens map anyway tells the
    orchestrator this batch closed five lenses it never touched. The
    decision-gate batch over the same file still reports its real map and
    stores exactly that map, and a persona reporting an unknown status is a
    failed lens, not a lost one - so an empty or canned map is wrong."""
    review = _review(tmp_path)
    state_path = _state(tmp_path)

    gate_result = review_close.close(review, state_path, "decision-gate", [])
    stored = _load(state_path)["review_lenses"]
    sweep_result = review_close.close(review, state_path, "tail-sweep", [TAIL_MED])

    assert gate_result["applied"] is True
    assert gate_result["lenses_closed"] == {
        "consensus": "done",
        "doubt": "done",
        "blind": "lost",
        "ui": "lost",
        "fable": "lost",
    }
    assert stored == gate_result["lenses_closed"]
    assert sweep_result["applied"] is True
    assert sweep_result["lenses_closed"] == {}
    assert _load(state_path)["review_lenses"] == stored

    flaky = _gate_lenses(
        tmp_path,
        "  alice: available\n  bob: unavailable\n",
        "flaky",
    )

    assert flaky["doubt"] == "failed"


def test_absent_persona_closes_dispatch_as_lost(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """bob and blake each have an open dispatch row and no line at all under
    `agents:`: nothing ever reported back for those dispatches, so their lenses
    and their rows close as lost rather than as successes the ledger would then
    average into its timings (bob's lens is `doubt`, blake's is `blind`). Two
    absent personas with row ids minted for this run, so no id branch covers
    them. carl is a different fact - taken off the roster on purpose - so
    carl's lens is skipped and carl's row keeps today's dispatch outcome, `ok`,
    which is what the dispatch vocabulary has for a row nobody failed."""
    review = _review(
        tmp_path,
        agents="  alice: available\n  carl: disabled\n",
        extra_frontmatter=(
            "dispatch_rows:\n"
            f"  bob: {LOST_ROWS[0]}\n"
            f"  blake: {LOST_ROWS[1]}\n"
            f"  carl: {DISABLED_ROW}\n"
        ),
    )
    state_path = _state(tmp_path)
    commands = _dispatch_argv(monkeypatch)

    result = review_close.close(review, state_path, "decision-gate", [])

    assert result["applied"] is True
    ended = _ended(commands)
    assert ended[LOST_ROWS[0]] == "lost"
    assert ended[LOST_ROWS[1]] == "lost"
    assert ended[DISABLED_ROW] == "ok"
    assert result["lenses_closed"]["doubt"] == "lost"
    assert result["lenses_closed"]["blind"] == "lost"
    assert result["lenses_closed"]["ui"] == "skipped"


def test_refused_repeat_leaves_backup_untouched(tmp_path: Path) -> None:
    """Every pre-lock refusal happens before any state mutation begins, so a
    repeat call that is refused must not open the backup: an operator re-running
    a refused batch would otherwise overwrite the one copy of state.json they
    could recover from. An existing backup keeps its bytes and its mtime, and
    where none exists none is created. The applied call at the end is the
    control: it does write the backup, holding the bytes state.json had before
    that call, so "never touched" cannot be bought by never backing up."""
    state_path = _state(tmp_path)
    backup = Path(f"{state_path}.bak")
    backup.write_bytes(b'{"cycle": 1, "tasks": [], "recoverable": true}')
    os.utime(backup, (1_000_000, 1_000_000))
    before, mtime = backup.read_bytes(), backup.stat().st_mtime_ns
    bare = tmp_path / "bare"
    bare.mkdir()
    bare_state = _state(bare)
    bare_before = bare_state.read_bytes()

    results = _prelock_refusals(tmp_path, state_path, bare_state)

    assert [r["applied"] for r in results] == [False, False, False]
    assert [r.get("refused") for r in results] == [
        None,
        "findings_uncovered",
        "carry_unmatched",
    ]
    assert backup.read_bytes() == before
    assert backup.stat().st_mtime_ns == mtime
    assert not Path(f"{bare_state}.bak").exists()

    applied = review_close.close(
        _review(bare, name="applied-01.md"),
        bare_state,
        "decision-gate",
        [],
    )

    assert applied["applied"] is True
    assert Path(f"{bare_state}.bak").read_bytes() == bare_before


def test_dispatch_id_with_leading_dash_is_refused(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A row id is written into a child process's argv, so an id starting with a
    dash would be read there as a flag: `--outcome` as an id silently rewrites
    the outcome of whatever row follows. Such an id is refused before any argv
    is built - including one minted for this run, which no blocklist of known
    ids can hold - while the ordinary ids in the same block are still closed: a
    filter that dropped every row would lose the real dispatch records."""
    review = _review(
        tmp_path,
        extra_frontmatter=(
            "dispatch_rows:\n"
            "  alice: 3a6d1d4e\n"
            "  bob: -x\n"
            "  carl: --outcome\n"
            f"  dave: {DASH_ID}\n"
            "  eve: a.b_c-1\n"
        ),
    )
    state_path = _state(tmp_path)
    commands = _dispatch_argv(monkeypatch)

    result = review_close.close(review, state_path, "decision-gate", [])

    assert result["applied"] is True
    assert sorted(_ended(commands)) == ["3a6d1d4e", "a.b_c-1"]
    assert DASH_ID not in [arg for cmd in commands for arg in cmd]
