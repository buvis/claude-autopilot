#!/usr/bin/env python3
"""`gate --findings` validates every row's `classification` BEFORE it
cross-checks the batch against the review table.

A sibling of test_gate_findings_table.py, which sits at the 800-line limit
(rules/coding-style.md): the table-shape half, the fixtures reused below and
the shared `_review` / `_findings` / `_gate` helpers all live there and in
test_gate.py.
"""

from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path
from uuid import uuid4

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
# Reached through the module so pytest does not collect the borrowed TestCase
# suite a second time under this file's name.
from cli import test_gate as gate_tests
from cli.test_gate import HIGH, MED, _row
from cli.test_gate_findings_table import (
    KNOWN_CLASSIFICATIONS,
    TABLE_HEADER_REF_6,
    _r1_finding,
    _ref_row,
    _table_section,
)

EXPECTED_LIST = "|".join(KNOWN_CLASSIFICATIONS)

# Four review rows a findings batch can match cell for cell, so every refusal
# below is the classification check alone, never a cross-check verdict in
# disguise.
_ROWS = (
    ("R1", HIGH, "wrong default", "src/b.py:10"),
    ("R2", MED, "unclear name", "src/c.py:20"),
    ("R3", MED, "stale comment", "src/d.py:30"),
    ("R4", HIGH, "missing guard", "src/e.py:40"),
)
ONE_ROW_TABLE = _table_section(TABLE_HEADER_REF_6, _ref_row(*_ROWS[0]))
TWO_ROW_TABLE = _table_section(TABLE_HEADER_REF_6, *(_ref_row(*r) for r in _ROWS[:2]))
FOUR_ROW_TABLE = _table_section(TABLE_HEADER_REF_6, *(_ref_row(*r) for r in _ROWS))


def _finding(spec: tuple, cls: object) -> dict:
    """A findings-JSON row matching one `_ROWS` entry cell for cell."""
    ref, sev, issue, file = spec
    return dict(_row(sev, file, issue, cls), ref=ref)


def _batch4(last: object) -> list[dict]:
    """Four backed, covered rows for FOUR_ROW_TABLE. Only the LAST row's
    classification varies, so a reader that stops after row one or two, or that
    reads the batch backwards, cannot answer these cases correctly."""
    rows = [_finding(_ROWS[i], cls) for i, cls in enumerate(("fix", "carry", "defer"))]
    rows.append(_finding(_ROWS[3], last))
    return rows


def _line(ref: str, value: object, expected: str = EXPECTED_LIST) -> str:
    """The one stderr line the gate owes for an unknown classification."""
    return f"row {ref}: unknown classification {value!r} (expected {expected})"


def _said(stderr: str) -> list[str]:
    return [line for line in stderr.splitlines() if line.strip()]


def _exit(text: str, rows: list[dict], tmp_path: Path) -> int:
    from cli import gate

    path = tmp_path / "findings.json"
    path.write_text(json.dumps(rows), encoding="utf-8")
    return gate._findings_exit(text, path)


class GateClassificationRefusalTests(unittest.TestCase):
    """The real CLI, so the exit code and the stderr line are both real."""

    setUp = gate_tests.FindingsCrossCheckTests.setUp
    _review = gate_tests.FindingsCrossCheckTests._review
    _findings = gate_tests.FindingsCrossCheckTests._findings
    _gate = gate_tests.FindingsCrossCheckTests._gate

    def _run_gate(
        self,
        rows: list[dict],
        section: str = ONE_ROW_TABLE,
    ) -> subprocess.CompletedProcess:
        return self._gate(self._review(section=section), self._findings(rows))

    def test_gate_names_the_row_with_an_unknown_classification(self) -> None:
        # `Carry` is the real slip: the right disposition, the wrong case. The
        # row matches R1 in every other cell, so nothing else can refuse it.
        proc = self._run_gate([_r1_finding("Carry")])
        self.assertEqual(proc.returncode, 2, proc.stdout)
        self.assertIn(_line("R1", "Carry"), proc.stderr)
        self.assertNotIn("Traceback", proc.stderr)
        # The five dispositions are spelled out, so the operator fixes the row
        # from this line alone, and the refusal is the gate's whole answer.
        self.assertIn(EXPECTED_LIST, proc.stderr)
        self.assertEqual(len(_said(proc.stderr)), 1, proc.stderr)
        # Control, so this is not a refuse-everything: the same row carrying the
        # lower-case spelling is a known disposition and passes.
        ok = self._run_gate([_r1_finding("carry")])
        self.assertEqual(ok.returncode, 0, ok.stderr)

    def test_gate_refuses_a_row_with_no_classification_key(self) -> None:
        # Absent is not "unclassified, carry on": the value reprs as None and
        # the row is refused exactly like a misspelled one.
        row = _r1_finding("carry")
        del row["classification"]
        proc = self._run_gate([row])
        self.assertEqual(proc.returncode, 2, proc.stdout)
        self.assertIn(_line("R1", None), proc.stderr)
        self.assertEqual(len(_said(proc.stderr)), 1, proc.stderr)

    def test_gate_names_a_ref_less_row_with_a_question_mark(self) -> None:
        # No ref key to quote, so the line still has to point somewhere.
        proc = self._run_gate([_row(HIGH, "src/b.py:10", "wrong default", "carried")])
        self.assertEqual(proc.returncode, 2, proc.stdout)
        self.assertIn(_line("?", "carried"), proc.stderr)
        self.assertNotIn("Traceback", proc.stderr)

    def test_gate_names_the_offending_row_not_the_first_one(self) -> None:
        # R1 is dispositioned correctly and R2 is the slip, so a line that
        # quotes the batch's first ref sends the operator to the wrong row.
        proc = self._run_gate(
            [_r1_finding("fix"), _finding(_ROWS[1], "Carry")],
            section=TWO_ROW_TABLE,
        )
        self.assertEqual(proc.returncode, 2, proc.stdout)
        self.assertEqual(_said(proc.stderr), [_line("R2", "Carry")])
        self.assertNotIn("R1", proc.stderr)

    def test_gate_names_the_first_unknown_row_when_two_rows_are_unknown(self) -> None:
        # Both rows are bad. The operator is handed the first one, in batch
        # order: hiding it behind the last one costs a second round trip.
        proc = self._run_gate(
            [_r1_finding("Carry"), _finding(_ROWS[1], "carried")],
            section=TWO_ROW_TABLE,
        )
        self.assertEqual(proc.returncode, 2, proc.stdout)
        self.assertEqual(_said(proc.stderr), [_line("R1", "Carry")])
        self.assertNotIn("carried", proc.stderr)
        self.assertNotIn("R2", proc.stderr)

    def test_unknown_classification_outranks_the_cross_check_verdict(self) -> None:
        # Both problems at once. The classification is what the operator has to
        # fix first, so it is what the gate reports: the cross-check never runs.
        bogus = f"issue nobody raised {uuid4().hex}"
        cases = {
            "also a mismatch": [
                _r1_finding("Carry"),
                dict(_row(MED, "src/c.py:20", bogus), ref="R2"),
            ],
            "also uncovered": [_r1_finding("Carry")],
        }
        for label, rows in cases.items():
            with self.subTest(label):
                proc = self._run_gate(rows, section=TWO_ROW_TABLE)
                self.assertEqual(proc.returncode, 2, proc.stdout)
                self.assertIn(_line("R1", "Carry"), proc.stderr)
                said = proc.stderr + proc.stdout
                self.assertNotIn(bogus, said)
                self.assertNotIn("R2", said)
        # Control: with every classification known, the same partial batch gets
        # the cross-check verdict it always got, naming the uncovered R2.
        verdict = self._run_gate([_r1_finding("fix")], section=TWO_ROW_TABLE)
        self.assertEqual(verdict.returncode, 2, verdict.stdout)
        self.assertIn("R2", verdict.stderr + verdict.stdout)

    def test_a_batch_of_known_classifications_still_exits_0(self) -> None:
        # Both refs dispositioned with known values, one of them the `carry`
        # whose wrong-case twin is refused above: a clean batch is untouched.
        rows = [_r1_finding("fix"), _finding(_ROWS[1], "carry")]
        proc = self._run_gate(rows, section=TWO_ROW_TABLE)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(proc.stderr.strip(), "")


@pytest.mark.parametrize("value", KNOWN_CLASSIFICATIONS)
def test_findings_exit_accepts_every_known_classification(
    value: str,
    tmp_path: Path,
) -> None:
    # Also the control for the refusal cases below: this very batch, with only
    # the last row's classification swapped, is backed, covered and clean.
    assert _exit(FOUR_ROW_TABLE, _batch4(value), tmp_path) == 0


_UNKNOWN_VALUES = {
    "wrong case": "Carry",
    "a near miss": "carried",
    "an upper-case known word": "FIX",
    "trailing space": "fix ",
    "empty string": "",
    "not a string": 1,
    "null": None,
    # Not drawn from any list a deny-list could carry, so the gate has to decide
    # by membership in the five, not by spotting known-bad spellings.
    "an arbitrary word": uuid4().hex,
}
# A prefix of a known disposition is not that disposition: `fi` is nobody's
# verdict, and a gate that matches on prefixes accepts all five of these.
_UNKNOWN_VALUES.update({f"a truncated {k}": k[:-1] for k in KNOWN_CLASSIFICATIONS})


@pytest.mark.parametrize(
    "value",
    list(_UNKNOWN_VALUES.values()),
    ids=list(_UNKNOWN_VALUES),
)
def test_findings_exit_refuses_an_unknown_classification(
    value: object,
    tmp_path: Path,
) -> None:
    # 2, not 1: an unknown disposition is a refusal the operator has to answer,
    # not the gate tripping over a shape it could not read. All four review rows
    # are backed and covered, so the cross-check has nothing to say here and
    # only the LAST row's classification can produce the refusal.
    assert _exit(FOUR_ROW_TABLE, _batch4(value), tmp_path) == 2


def test_the_refusal_line_lists_whatever_the_gate_tuple_holds(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture,
    tmp_path: Path,
) -> None:
    """The expected list is read off `KNOWN_CLASSIFICATIONS`, not spelled out a
    second time: a sixth disposition has to show up in the line, and in the
    gate's verdict, the day it joins the tuple."""
    from cli import gate

    grown = gate.KNOWN_CLASSIFICATIONS + ("park",)
    monkeypatch.setattr(gate, "KNOWN_CLASSIFICATIONS", grown)
    assert _exit(FOUR_ROW_TABLE, _batch4("park"), tmp_path) == 0
    capsys.readouterr()
    assert _exit(FOUR_ROW_TABLE, _batch4("parked"), tmp_path) == 2
    out = capsys.readouterr()
    assert _line("R4", "parked", "|".join(grown)) in out.err + out.out


def test_findings_verdict_keeps_a_row_it_cannot_classify(tmp_path: Path) -> None:
    """`review-close` reads the public verdict, so a row the gate cannot
    classify must not quietly vanish from the batch it judges: dropping it hands
    `review-close` an `ok` for findings that were never checked."""
    from cli import gate

    # R9 is in no table, so an honest verdict refuses this batch whatever it
    # makes of `Carry`. Only an implementation that drops the row it could not
    # classify gets to call the rest of the batch clean.
    ghost = dict(_row(HIGH, "src/z.py:90", "ghost row"), ref="R9")
    assert gate.findings_verdict(
        ONE_ROW_TABLE,
        [_r1_finding("fix"), dict(ghost, classification="Carry")],
    ) != ("ok", None)
    # Control: with a known disposition the same ghost is reported, by ref, as
    # the mismatch it is - so the refusal above is not a refuse-everything.
    tag, detail = gate.findings_verdict(
        ONE_ROW_TABLE,
        [_r1_finding("fix"), dict(ghost, classification="carry")],
    )
    assert tag != "ok"
    assert "R9" in (detail or "")


def test_main_module_shares_the_gate_classification_tuple(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Two copies of the five dispositions is how the gate and `review-close`
    drift apart, so __main__.py references the gate's tuple instead of carrying
    its own literal."""
    from cli import __main__ as cli_main
    from cli import gate

    assert cli_main._KNOWN_CLASSIFICATIONS is gate.KNOWN_CLASSIFICATIONS
    squeezed = "".join(Path(cli_main.__file__).read_text(encoding="utf-8").split())
    for quote in ('"', "'"):
        body = ",".join(f"{quote}{v}{quote}" for v in KNOWN_CLASSIFICATIONS)
        for open_, close in (("(", ")"), ("{", "}"), ("[", "]")):
            assert open_ + body + close not in squeezed
    # `_is_chosen_finding` keeps the behaviour it had: a complete fix row is
    # still chosen, and the unknown value is still the only thing refused.
    good = dict(_r1_finding("fix"), found_by=["bob"])
    assert cli_main._is_chosen_finding(good) is True
    assert cli_main._is_chosen_finding(dict(good, classification="Carry")) is False
    # And it reads the shared tuple when it runs, so a sixth disposition reaches
    # `review-close` too instead of being refused by a stale inline copy.
    grown = gate.KNOWN_CLASSIFICATIONS + ("park",)
    monkeypatch.setattr(gate, "KNOWN_CLASSIFICATIONS", grown)
    monkeypatch.setattr(cli_main, "_KNOWN_CLASSIFICATIONS", grown)
    assert cli_main._is_chosen_finding(dict(good, classification="park")) is True
    assert cli_main._is_chosen_finding(dict(good, classification="parked")) is False


if __name__ == "__main__":
    unittest.main()
