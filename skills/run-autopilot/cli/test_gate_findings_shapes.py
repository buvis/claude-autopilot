#!/usr/bin/env python3
"""The negative-space half of the `gate --findings` cross-check.

A sibling of test_gate_findings_table.py (786 lines, at the 800-line limit in
rules/coding-style.md), whose fixtures and happy-path table tests are imported
here rather than re-spelled. Every test below pins a verdict that a reader
sniffing the review text, or validating only the first row or the first pair,
would get wrong: an off-shape cell BEHIND a well-formed row, a duplicate ref
that is not adjacent, a classification conflict past the second findings row, a
ghost ref under each applied classification, and the exit code of each verdict
tag taken from the tag itself.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
# The TestCase class is reached through the module: binding its name here would
# make pytest collect that whole suite a second time under this file.
from cli import test_gate as gate_tests
from cli.test_gate import GOOD_FILE, HIGH, MED, _row
from cli.test_gate_findings_table import (
    _REF_CELL_CASES,
    KNOWN_CLASSIFICATIONS,
    TABLE_HEADER_6,
    TABLE_HEADER_REF_6,
    _check,
    _keys,
    _r1_finding,
    _ref_cell_row,
    _ref_row,
    _table_row,
    _table_section,
)

# The two well-formed rows every batch below is judged against.
_R1_ROW = _ref_row("R1", HIGH, "wrong default", "src/b.py:10")
_R2_ROW = _ref_row("R2", MED, "unclear name", "src/c.py:20")


def _r2_finding(cls: str) -> dict:
    """A findings-JSON row naming `_R2_ROW`, the way `_r1_finding` names R1."""
    return dict(_row(MED, "src/c.py:20", "unclear name", cls), ref="R2")


# Strings outside the five dispositions, and values that are not strings at all.
_UNLISTED = ("fxi", "totally-made-up", "carryover", "fix2", "0", "", "FIX", "fix ")
_NOT_A_STRING = (None, 1, True, 3.5, (), (3.5,), ["fix"], {"fix"})


def test_known_classification_answers_membership_and_nothing_wider() -> None:
    """The answer is `value in KNOWN_CLASSIFICATIONS` for every probe, so a
    reader that refuses a fixed list of bad values and accepts everything else
    fails here on the first made-up word."""
    from cli import gate

    assert gate.KNOWN_CLASSIFICATIONS == KNOWN_CLASSIFICATIONS
    for value in (*KNOWN_CLASSIFICATIONS, *_UNLISTED, *_NOT_A_STRING):
        expected = isinstance(value, str) and value in KNOWN_CLASSIFICATIONS
        assert gate.known_classification(value) is expected, repr(value)


def test_refless_table_is_refused_even_when_a_cell_quotes_the_ref_header() -> None:
    """The verdict reads the parsed rows, not the review text: this table has no
    Ref column, and spelling the Ref header inside an Issue cell hands its rows
    no ref, so the section still cannot be covered."""
    issue = "the header `| Ref |` is read by name"
    text = _table_section(TABLE_HEADER_6, _table_row(HIGH, issue, "src/b.py:10"))
    rows, err = _keys(text)
    assert err is None
    assert [r.ref for r in rows] == [""]
    tag, detail = _check(text, [_row(HIGH, "src/b.py:10", issue)])
    assert tag == "ref-required"
    assert detail


def test_a_refless_row_beside_a_ref_table_row_is_refused() -> None:
    """A mixed section: one Ref-bearing table row plus a bullet-shaped row that
    carries no ref. The Ref-ful rows do not buy the ref-less one coverage - no
    findings row can name a ref it was never given."""
    text = _table_section(TABLE_HEADER_REF_6, _R1_ROW) + (
        f"- [2/3] {MED} unclear name | src/c.py:20 | Found by: alice, bob\n"
    )
    rows, err = _keys(text)
    assert err is None
    assert sorted(r.ref for r in rows) == ["", "R1"]
    tag, detail = _check(text, [_r1_finding("fix")])
    assert tag == "ref-required"
    assert detail


# The off-shape cells of test_rejects_review_row_with_offshape_ref_instead_of_
# skipping_it, reused here in the one position that test does not cover: behind
# a well-formed row.
_OFFSHAPE_CELLS = {
    label: (ref_cell, consensus_cell)
    for label, (ref_cell, consensus_cell, expected_ref) in _REF_CELL_CASES.items()
    if expected_ref is None
}


@pytest.mark.parametrize(
    ("ref_cell", "consensus_cell"),
    list(_OFFSHAPE_CELLS.values()),
    ids=list(_OFFSHAPE_CELLS),
)
def test_offshape_ref_row_is_refused_behind_a_well_formed_row(
    ref_cell: str,
    consensus_cell: str,
) -> None:
    text = _table_section(
        TABLE_HEADER_REF_6,
        _ref_row("R5", HIGH, "wrong default", "src/b.py:10"),
        _ref_cell_row(ref_cell, consensus_cell),
    )
    # Reading the first row and trusting the rest drops the second row - and
    # the finding it carried - while reporting a readable one-row table.
    assert _keys(text) == ([], "unreadable-table")
    chosen = [dict(_row(HIGH, "src/b.py:10", "wrong default"), ref="R5")]
    tag, detail = _check(text, chosen)
    assert tag == "malformed"
    assert detail
    # Control: the same leading row followed by a well-formed second row reads
    # fine, so it is the off-shape cell that is refused, not the second row.
    readable = _table_section(
        TABLE_HEADER_REF_6,
        _ref_row("R5", HIGH, "wrong default", "src/b.py:10"),
        _ref_row("R6", MED, "unclear name", "src/c.py:20"),
    )
    rows, err = _keys(readable)
    assert err is None
    assert [r.ref for r in rows] == ["R5", "R6"]


_DUPLICATE_REF_ROWS = {
    "the duplicate refs are not adjacent": ("R1", "R2", "R1"),
    "the duplicate pair is not the first pair": ("R1", "R2", "r2"),
    "the same ref three times": ("R1", "R1", "R1"),
}


@pytest.mark.parametrize(
    "refs",
    list(_DUPLICATE_REF_ROWS.values()),
    ids=list(_DUPLICATE_REF_ROWS),
)
def test_duplicate_table_ref_is_refused_wherever_the_pair_sits(
    refs: tuple[str, ...],
) -> None:
    """Two rows sharing a ref make every findings row naming it ambiguous. The
    pair is found by looking at every row, not only at neighbours."""
    rows = [
        _ref_row(ref, HIGH, f"issue {i}", f"src/{i}.py:1")
        for i, ref in enumerate(refs)
    ]
    text = _table_section(TABLE_HEADER_REF_6, *rows)
    assert _keys(text) == ([], "unreadable-table")
    tag, detail = _check(text, [_r1_finding("fix")])
    assert tag == "malformed"
    assert detail
    # Control: the same rows under distinct refs read fine, so it is the
    # duplicate that is refused and not the row count.
    distinct = [
        _ref_row(f"R{i + 1}", HIGH, f"issue {i}", f"src/{i}.py:1")
        for i in range(len(refs))
    ]
    parsed, err = _keys(_table_section(TABLE_HEADER_REF_6, *distinct))
    assert err is None
    assert len(parsed) == len(refs)


def test_ref_with_two_classifications_is_refused_past_the_second_row() -> None:
    """One review row cannot hold two dispositions, however long the findings
    JSON is and wherever in it the contradicting pair sits."""
    text = _table_section(TABLE_HEADER_REF_6, _R1_ROW, _R2_ROW)
    three_rows = [_r1_finding("fix"), _r2_finding("discard"), _r1_finding("carry")]
    tag, detail = _check(text, three_rows)
    assert tag == "mismatch"
    assert "R1" in (detail or "")
    # Four rows, and the contradicting pair is neither the first pair nor an
    # adjacent one: rows 2 and 4 both name R2.
    four_rows = [
        _r1_finding("fix"),
        _r2_finding("fix"),
        _r1_finding("fix"),
        _r2_finding("defer"),
    ]
    tag, detail = _check(text, four_rows)
    assert tag == "mismatch"
    assert "R2" in (detail or "")
    # Control: the same four rows with one disposition per ref are backed, so
    # this is not a refusal of repeated refs or of long batches.
    agreeing = [_r1_finding("fix"), _r2_finding("fix")] * 2
    assert _check(text, agreeing) == ("ok", None)


# `verify` and `discard` stay exempt from the cross-check (test_gate.py's
# test_gate_refuses_an_unbacked_row_carrying_no_classification states that
# rule); the three dispositions below are applied to state, so each one has to
# be backed by a ref the review table really handed out.
@pytest.mark.parametrize("classification", ["fix", "defer", "carry"])
def test_ghost_ref_row_is_refused_for_every_applied_classification(
    classification: str,
) -> None:
    text = _table_section(TABLE_HEADER_REF_6, _R1_ROW)
    ghost = dict(_row(HIGH, "src/b.py:10", "wrong default", classification), ref="R9")
    tag, detail = _check(text, [_r1_finding("fix"), ghost])
    assert tag == "mismatch"
    assert "R9" in (detail or "")
    # Control: the same row naming the ref the table does hold is backed, so no
    # classification is refused on its own name.
    assert _check(text, [_r1_finding(classification)]) == ("ok", None)


def test_a_row_carrying_only_a_ref_and_a_classification_is_backed_by_that_ref() -> None:
    """Saved findings JSONs write a bare `{ref, classification}` row for a review
    row nobody is fixing, so severity and file are checked only when the row
    carries them - and the ref still has to exist."""
    text = _table_section(TABLE_HEADER_REF_6, _R1_ROW, _R2_ROW)
    bare = [_r1_finding("fix"), {"ref": "R2", "classification": "discard"}]
    assert _check(text, bare) == ("ok", None)
    bare_ghost = [
        _r1_finding("fix"),
        _r2_finding("fix"),
        {"ref": "R9", "classification": "fix"},
    ]
    tag, detail = _check(text, bare_ghost)
    assert tag == "mismatch"
    assert "R9" in (detail or "")


# An unbacked row's issue text is copied into the mismatch detail, so this
# wording puts the word "section" inside a detail that is NOT the
# missing-section one.
_SECTIONY_ISSUE = "the consolidated findings section lost a row"


class FindingsExitCodeTests(unittest.TestCase):
    """One case per verdict tag, each asserting the tag and the exit code of the
    same pair, so the mapping is pinned per tag instead of inferred from two
    runs. Borrows the fixture helpers rather than subclassing, which would re-run
    that subprocess-heavy suite under a second name."""

    setUp = gate_tests.FindingsCrossCheckTests.setUp
    _review = gate_tests.FindingsCrossCheckTests._review
    _findings = gate_tests.FindingsCrossCheckTests._findings
    _gate = gate_tests.FindingsCrossCheckTests._gate

    def test_each_findings_verdict_exits_by_its_own_tag(self) -> None:
        ref_table = _table_section(TABLE_HEADER_REF_6, _R1_ROW, _R2_ROW)
        refless = _table_section(
            TABLE_HEADER_6,
            _table_row(HIGH, "wrong default", "src/b.py:10"),
        )
        covered = [_r1_finding("fix"), _r2_finding("fix")]
        # No ref, so it is keyed by its text - which this table does not hold.
        unbacked = _row(HIGH, "src/b.py:10", _SECTIONY_ISSUE)
        cases = {
            # The only exit-1 reason: the review file carries no findings
            # section at all, which is the operator's own shape gap.
            "malformed, no section at all": ("", covered, "malformed", 1),
            "malformed, unreadable table": (
                _table_section(TABLE_HEADER_REF_6, "| R1 | [2/4] |"),
                covered,
                "malformed",
                2,
            ),
            # Its detail quotes the word "section" on purpose: a code picked by
            # sniffing the reason prose reads this as the exit-1 shape gap.
            "mismatch whose detail names a section": (
                ref_table,
                [*covered, unbacked],
                "mismatch",
                2,
            ),
            "uncovered": (ref_table, [_r1_finding("fix")], "uncovered", 2),
            "ref-required": (refless, [], "ref-required", 2),
        }
        for label, (section, rows, tag, code) in cases.items():
            with self.subTest(label):
                # An empty section means the review file carries none at all,
                # which is GOOD_FILE as `_review` writes it.
                text = section or GOOD_FILE
                verdict_tag, detail = _check(text, rows)
                self.assertEqual(verdict_tag, tag)
                proc = self._gate(self._review(section=section), self._findings(rows))
                self.assertEqual(proc.returncode, code, proc.stdout)
                self.assertNotIn("Traceback", proc.stderr)
                if label.endswith("names a section"):
                    self.assertIn("section", detail or "")


if __name__ == "__main__":
    unittest.main()
