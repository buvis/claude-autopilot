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

import json
import sys
import unittest
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
# The TestCase class is reached through the module: binding its name here would
# make pytest collect that whole suite a second time under this file.
from cli import test_gate as gate_tests
from cli.test_gate import CRIT, GOOD_FILE, HIGH, MED, _row
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
        _ref_row(ref, HIGH, f"issue {i}", f"src/{i}.py:1") for i, ref in enumerate(refs)
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
            # section, no [m/n] token and an empty findings JSON - the
            # operator's own shape gap.
            "malformed, no section at all": ("", [], "malformed", 1),
            # The same missing section under a batch that names rows: the
            # heading is missing or misspelled, which is a refusal.
            "malformed, no section but findings rows": ("", covered, "malformed", 2),
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


def test_an_indented_data_row_under_a_valid_header_is_still_read() -> None:
    """`_CANDIDATE_ROW_RE` used to be anchored at column zero (`^\\|`), so a
    data row some editor or renderer indented with leading spaces matched
    neither the candidate-row check nor the separator check and was silently
    dropped — along with the CRITICAL finding it carried, which then reached
    no disposition at all. The header itself stays unindented in this fixture:
    only the data row is indented, which is the exact shape the escape used."""
    text = _table_section(
        TABLE_HEADER_REF_6,
        "  "
        + _ref_row(
            "R1",
            CRIT,
            "crash on empty input",
            "src/a.py:3",
        ),
    )
    rows, err = _keys(text)
    assert err is None
    assert [r.ref for r in rows] == ["R1"]
    chosen = [dict(_row(CRIT, "src/a.py:3", "crash on empty input"), ref="R1")]
    assert _check(text, chosen) == ("ok", None)


def test_a_data_row_missing_its_closing_pipe_is_refused() -> None:
    """A row shaped `| [2/4] | high | wrong default | src/b.py:10 | 3 | B` with
    no trailing `|` still has every cell a well-formed row would have, so a
    check that only counts cells accepts it. The row's termination has to be
    checked too, or a truncated row silently parses as complete."""
    unterminated = (
        TABLE_HEADER_6
        + _table_row(HIGH, "wrong default", "src/b.py:10")
        .rstrip(
            "|",
        )
        .rstrip()
    )
    text = "## Consolidated Findings\n\n" + unterminated
    assert _keys(text) == ([], "unreadable-table")
    chosen = [_row(HIGH, "src/b.py:10", "wrong default")]
    tag, detail = _check(text, chosen)
    assert tag == "malformed"
    assert detail
    # Control: the same row with its closing pipe reads fine.
    whole = _table_section(
        TABLE_HEADER_6,
        _table_row(HIGH, "wrong default", "src/b.py:10"),
    )
    rows, err = _keys(whole)
    assert err is None
    assert len(rows) == 1


def test_unreadable_table_message_names_the_ref_required_shape() -> None:
    """The `unreadable-table` operator message used to describe only the old
    row shape and never mentioned that a Ref-less table is refused under the
    distinct `ref-required` tag, leaving the exit-2 operator no way to tell
    which gap they are looking at from the message alone."""
    from cli import gate

    message = gate._FINDINGS_PROBLEMS["unreadable-table"]
    assert "ref" in message.lower()
    assert "ref-required" in message


def test_ref_required_message_names_the_0_9_0_version_skew() -> None:
    """The `ref-required` operator message never explained WHY a review file
    can be Ref-less in the first place: it predates the Ref column. Without
    naming the version skew, an operator mid-batch has no way to tell a
    genuine gap from a review file simply written by an older autopilot."""
    from cli import gate

    message = gate._FINDINGS_PROBLEMS["ref-required"]
    assert "0.9.0" in message
    assert "finish or restart the batch on one version" in message


# PRD 00269: every [m/n] token and every pipe row in the review file is either
# read by the findings parser or refused. A fenced block quotes its lines, so a
# worked example is not a finding; nothing else hides a row.
_COVERED = [_r1_finding("fix"), _r2_finding("fix")]
_REF_TABLE = _table_section(TABLE_HEADER_REF_6, _R1_ROW, _R2_ROW)
_UNREAD = "a [m/n] token or table row the findings parser did not read: "

# Consensus tokens beyond the fixtures' own [1/3] [2/4] [3/3] [2/3]: any
# `[m/n]` is a token, so a sweep that knows only the fixture values fails here.
_CONSENSUS_TOKENS = ("[1/3]", "[4/5]", "[10/12]")


def _alice_row(consensus: str = "[1/3]") -> str:
    return f"- {consensus} {CRIT} crash on empty input | src/a.py:3 | Found by: alice"


_ALICE_ROW = _alice_row()


def _review_text(section: str = _REF_TABLE, alice: str = "- finding one") -> str:
    """GOOD_FILE with `section` above its verdict line, the way the gate tests'
    `_review` writes it, and `alice` as the body of the Alice section."""
    body = GOOD_FILE.replace("- finding one", alice)
    if section:
        body = body.replace("Verdict: converged", f"{section}\nVerdict: converged")
    return body


def _verdict_and_exit(
    text: str,
    findings: list[dict],
    tmp_path: Path,
) -> tuple[str, str | None, int]:
    """The verdict on one pair, and the gate's exit code for that same pair."""
    from cli import gate

    path = tmp_path / "findings.json"
    path.write_text(json.dumps(findings, ensure_ascii=False), encoding="utf-8")
    tag, detail = gate.findings_verdict(text, findings)
    return tag, detail, gate._findings_exit(text, path)


def _unread_detail(text: str, line: str) -> str:
    """The refusal naming `line` as the first token line nothing consumed."""
    n = text.splitlines().index(line) + 1
    return f"line {n}: {_UNREAD}{line.strip()[:120]}"


@pytest.mark.parametrize(
    "heading",
    [
        "## Consolidated findings",
        "### Consolidated Findings",
        "## Consolidated Findings (cycle 2)",
        "",
    ],
    ids=["lower-case f", "h3", "suffixed", "no heading"],
)
def test_heading_typo_with_a_ref_table_is_unreadable(
    heading: str,
    tmp_path: Path,
) -> None:
    """A table under a misspelled heading is not a missing section: its rows are
    findings nobody read, so the batch is refused (exit 2), never let through
    as the exit-1 shape gap."""
    from cli import gate

    table = TABLE_HEADER_REF_6 + f"{_R1_ROW}\n{_R2_ROW}\n"
    text = _review_text(f"{heading}\n\n{table}" if heading else table)
    tag, detail, code = _verdict_and_exit(text, _COVERED, tmp_path)
    assert tag == "malformed"
    assert detail != gate._FINDINGS_PROBLEMS["no-section"]
    assert detail == _unread_detail(text, TABLE_HEADER_REF_6.splitlines()[0])
    assert code == 2
    # Control: the same table under the exact heading is read and covered.
    assert gate.findings_verdict(_review_text(), _COVERED) == ("ok", None)


@pytest.mark.parametrize("consensus", _CONSENSUS_TOKENS)
@pytest.mark.parametrize(
    "section",
    ["", "## Consolidated Findings\n\nNo findings.\n"],
    ids=["no findings section", "an empty findings section"],
)
def test_a_critical_row_only_under_a_reviewer_heading_is_unreadable(
    section: str,
    consensus: str,
    tmp_path: Path,
) -> None:
    """A red row left under `## Alice` never reached the consolidated section,
    so an empty batch cannot pass it - with or without a section to look in,
    whatever numbers its `[m/n]` token carries."""
    row = _alice_row(consensus)
    text = _review_text(section, alice=row)
    verdict = _verdict_and_exit(text, [], tmp_path)
    assert verdict == ("malformed", _unread_detail(text, row), 2)


@pytest.mark.parametrize("extra", [1, 2], ids=["two headings", "three headings"])
def test_a_second_findings_heading_is_unreadable(extra: int, tmp_path: Path) -> None:
    """Two or more live findings headings leave no single section to read. The
    readable one comes first, so taking the first match passes this file."""
    from cli import gate

    second = "## Consolidated Findings\n\nNo findings.\n" * extra
    text = _review_text(f"{_REF_TABLE}\n{second}")
    tag, detail, code = _verdict_and_exit(text, _COVERED, tmp_path)
    assert tag == "malformed"
    assert detail
    assert detail != gate._FINDINGS_PROBLEMS["no-section"]
    assert code == 2
    # Control: one heading over the same table reads fine.
    assert gate.findings_verdict(_review_text(), _COVERED) == ("ok", None)


def test_a_fenced_h2_line_does_not_end_the_findings_section(tmp_path: Path) -> None:
    """A quoted `## example` above the table is not the next section: the rows
    below it are still the section's rows."""
    fenced = "```markdown\n## example\n```\n\n"
    rows = f"{_R1_ROW}\n{_R2_ROW}\n"
    text = _review_text(
        f"## Consolidated Findings\n\n{fenced}{TABLE_HEADER_REF_6}{rows}",
    )
    assert _verdict_and_exit(text, _COVERED, tmp_path) == ("ok", None, 0)


def test_a_live_h2_after_the_section_ends_it(tmp_path: Path) -> None:
    """The section stops at the next live `## ` line: a ref row under a later
    `## Notes` is no consolidated finding, so no batch backs or covers it."""
    late = f"| R3 | [1/3] | {MED} | late row | src/d.py:1 | 3 | ALICE, BOB |"
    text = _review_text(f"{_REF_TABLE}\n## Notes\n\n{late}\n")
    verdict = _verdict_and_exit(text, _COVERED, tmp_path)
    assert verdict == ("malformed", _unread_detail(text, late), 2)
    # A batch naming R3 cannot make the late row a backed, covered finding.
    r3 = dict(_row(MED, "src/d.py:1", "late row"), ref="R3")
    tag, _, code = _verdict_and_exit(text, [*_COVERED, r3], tmp_path)
    assert tag != "ok"
    assert code == 2


def test_a_fenced_example_row_and_heading_are_not_findings(tmp_path: Path) -> None:
    """A worked example inside a fence - a findings heading, a table, a bullet
    row - is quoted, under a reviewer heading and inside the section alike."""
    example = (
        "```\n## Consolidated Findings\n\n"
        f"{TABLE_HEADER_REF_6}{_ref_row('R9', CRIT, 'example only', 'src/x.py:1')}\n"
        "```"
    )
    # A fence closes only on a run of its own character at least as long as
    # the opener, so the shorter ~~~ line inside it keeps quoting.
    in_section = (
        "~~~~\n"
        f"- [1/3] {MED} example bullet | src/y.py:2 | Found by: bob\n"
        "~~~\n"
        f"{_ref_row('R8', MED, 'example row', 'src/y.py:3')}\n"
        "~~~~~\n"
    )
    text = _review_text(f"{_REF_TABLE}\n{in_section}", alice=example)
    assert _verdict_and_exit(text, _COVERED, tmp_path) == ("ok", None, 0)


def test_an_unclosed_fence_quotes_nothing(tmp_path: Path) -> None:
    """A fence that never closes cannot hide a row: the row after its opener is
    live, and so is the findings heading further down."""
    from cli import gate

    text = _review_text(alice=f"```\n{_ALICE_ROW}")
    verdict = _verdict_and_exit(text, _COVERED, tmp_path)
    assert verdict == ("malformed", _unread_detail(text, _ALICE_ROW), 2)
    # Control: the same fence, closed, quotes the row.
    closed = _review_text(alice=f"```\n{_ALICE_ROW}\n```")
    assert gate.findings_verdict(closed, _COVERED) == ("ok", None)


def test_an_unclosed_opener_does_not_let_a_later_pair_hide_a_row(
    tmp_path: Path,
) -> None:
    """A four-backtick opener that never finds its own four-or-more-backtick
    closer must not resume scanning as if nothing happened: a three-backtick
    pair further down used to be read as its OWN fence and blanked, hiding
    whatever row it wrapped. Once an opener is unclosed, the rest of the text
    stays live/scanned - no later run of the fence character may start a new
    fence instead."""
    alice = f"````\nnever closes\n```\n{_ALICE_ROW}\n```\nafter\n"
    text = _review_text(alice=alice)
    verdict = _verdict_and_exit(text, _COVERED, tmp_path)
    assert verdict == ("malformed", _unread_detail(text, _ALICE_ROW), 2)


def test_an_indented_fence_still_quotes_its_rows(tmp_path: Path) -> None:
    """The fence rule reads the stripped line, so a fence indented under a
    list item still opens and closes, quoting the row between."""

    indented = f"  ```\n  {_ALICE_ROW}\n  ```"
    text = _review_text(alice=indented)
    assert _verdict_and_exit(text, _COVERED, tmp_path) == ("ok", None, 0)


def test_a_closer_with_trailing_text_still_closes_the_fence(tmp_path: Path) -> None:
    """A closer line only needs to START with a run of the fence character at
    least as long as the opener - trailing text after it still closes."""

    text = _review_text(alice=f"```\n{_ALICE_ROW}\n``` trailing text")
    assert _verdict_and_exit(text, _COVERED, tmp_path) == ("ok", None, 0)


# (opener, closer) lines whose fence marker sits at column 4 or more, so
# CommonMark reads them as an indented code block, not a fence.
_DEEP_FENCES = [
    pytest.param("\t```", "\t```", id="tab"),
    pytest.param("    ```", "    ```", id="4 spaces"),
    pytest.param("     ```", "     ```", id="5 spaces"),
    pytest.param("        ```", "        ```", id="8 spaces"),
    pytest.param("\t\t```", "\t\t```", id="two tabs"),
    pytest.param("    ```python", "    ```", id="info string"),
    pytest.param("\t~~~", "\t~~~", id="tab tilde"),
    pytest.param("    ~~~", "    ~~~", id="4 spaces tilde"),
    pytest.param("    ````", "    ````", id="4 spaces 4 backticks"),
    pytest.param("\t~~~~", "\t~~~~", id="tab 4 tildes"),
    pytest.param("  \t```", "  \t```", id="2 spaces then tab"),
    pytest.param(" \t```", " \t```", id="1 space then tab"),
    # The opener counts, the closer does not: the fence never closes.
    pytest.param("```", "    ```", id="unindented opener 4-space closer"),
]

# Bodies whose row must stay live: the fence's indent decides, not the row.
_DEEP_FENCE_BODIES = [
    pytest.param(_ALICE_ROW, id="alice bullet"),
    pytest.param(
        f"- [2/3] {MED} stale cache | src/f.py:8 | Found by: bob",
        id="bob bullet",
    ),
    pytest.param(_ref_row("R9", CRIT, "quoted table row", "src/g.py:4"), id="ref row"),
]


@pytest.mark.parametrize("body", _DEEP_FENCE_BODIES)
@pytest.mark.parametrize(("opener", "closer"), _DEEP_FENCES)
def test_indented_fence_does_not_blank_rows(
    opener: str,
    closer: str,
    body: str,
    tmp_path: Path,
) -> None:
    """CommonMark reads a fence marker at column 4 or more (a tab, 4+ spaces,
    or spaces then a tab reaching the tab stop) as a code block, not a fence:
    such a line neither opens nor closes, so the row between is live and
    refused like a row never fenced at all."""
    from cli import gate

    text = _review_text(alice=f"{opener}\n{body}\n{closer}")
    verdict = _verdict_and_exit(text, _COVERED, tmp_path)
    assert verdict == ("malformed", _unread_detail(text, body), 2)
    # Control at the boundary: the same fence lines indented 3 spaces are a
    # real fence, and quote the same row.
    shallow = _review_text(alice=f"   {opener.lstrip()}\n{body}\n   {closer.lstrip()}")
    assert gate.findings_verdict(shallow, _COVERED) == ("ok", None)


def test_a_row_above_the_table_header_is_unreadable(tmp_path: Path) -> None:
    stray = _ref_row("R3", MED, "stray row", "src/d.py:1")
    rows = f"{_R1_ROW}\n{_R2_ROW}\n"
    text = _review_text(
        f"## Consolidated Findings\n\n{stray}\n\n{TABLE_HEADER_REF_6}{rows}",
    )
    verdict = _verdict_and_exit(text, _COVERED, tmp_path)
    assert verdict == ("malformed", _unread_detail(text, stray), 2)


@pytest.mark.parametrize("consensus", _CONSENSUS_TOKENS)
@pytest.mark.parametrize("bullet", ["*", "+"])
def test_a_star_or_plus_bullet_row_is_unreadable(
    bullet: str,
    consensus: str,
    tmp_path: Path,
) -> None:
    from cli import gate

    row = f"{bullet} {consensus} {MED} unclear name | src/e.py:5 | Found by: bob"
    text = _review_text(f"{_REF_TABLE}\n{row}\n")
    verdict = _verdict_and_exit(text, _COVERED, tmp_path)
    assert verdict == ("malformed", _unread_detail(text, row), 2)
    # Control: the `-` bullet is read, as a ref-less row no batch can cover.
    dash = _review_text(f"{_REF_TABLE}\n-{row[1:]}\n")
    assert gate.findings_verdict(dash, _COVERED)[0] == "ref-required"


def test_a_one_line_html_comment_row_is_unreadable(tmp_path: Path) -> None:
    """A comment hides nothing: the row inside it is a live token line."""
    row = f"<!-- {_ref_row('R3', MED, 'hidden row', 'src/d.py:1')} -->"
    text = _review_text(f"{_REF_TABLE}\n{row}\n")
    verdict = _verdict_and_exit(text, _COVERED, tmp_path)
    assert verdict == ("malformed", _unread_detail(text, row), 2)


# Shapes some markdown renderer would hide, none of which quotes a row here:
# only a closed fence does.
_R3_ROW = _ref_row("R3", MED, "hidden row", "src/d.py:1")
_HIDDEN_ROWS = {
    "multi-line html comment": ("<!--", _R3_ROW, "-->"),
    "multi-line html comment, bullet": ("<!--", _alice_row("[4/5]"), "-->"),
    "blockquoted bullet": ("", f"> {_alice_row()}", ""),
    "blockquoted ref row": ("", f"> {_R3_ROW}", ""),
    "4-space indented bullet": ("", f"    {_alice_row()}", ""),
    "8-space indented bullet": ("", f"        {_alice_row('[10/12]')}", ""),
    "tab-indented bullet": ("", f"\t{_alice_row()}", ""),
    "4-space indented ref row": ("", f"    {_R3_ROW}", ""),
}


@pytest.mark.parametrize(
    ("before", "row", "after"),
    list(_HIDDEN_ROWS.values()),
    ids=list(_HIDDEN_ROWS),
)
def test_a_row_a_renderer_would_hide_is_unreadable(
    before: str,
    row: str,
    after: str,
    tmp_path: Path,
) -> None:
    """Under `## Alice`, beside a covered table: the row is the first line
    nothing read, named by its own line, exit 2."""
    alice = "\n".join(line for line in (before, row, after) if line)
    text = _review_text(alice=alice)
    verdict = _verdict_and_exit(text, _COVERED, tmp_path)
    assert verdict == ("malformed", _unread_detail(text, row), 2)


def test_a_tokenless_pipe_row_outside_the_table_is_unreadable(tmp_path: Path) -> None:
    """A pipe row with no `[m/n]` and no `|---|` below it is still a row: one
    under `## Alice` is refused, the exact ref table in place notwithstanding."""
    row = f"| R5 | {CRIT} | crash | src/a.py:3 |"
    text = _review_text(alice=row)
    verdict = _verdict_and_exit(text, _COVERED, tmp_path)
    assert verdict == ("malformed", _unread_detail(text, row), 2)


@pytest.mark.parametrize(
    ("section", "findings"),
    [("", []), (_REF_TABLE, _COVERED)],
    ids=["no findings section, empty batch", "covered ref table"],
)
def test_an_unread_row_quoting_the_no_section_text_still_exits_2(
    section: str,
    findings: list[dict],
    tmp_path: Path,
) -> None:
    """The exit code follows the detail being the no-section one, never words
    found inside it: this row quotes that text and is still a refusal."""
    from cli import gate

    no_section = gate._FINDINGS_PROBLEMS["no-section"]
    row = f"- [1/3] {CRIT} {no_section} | src/a.py:3 | Found by: alice"
    text = _review_text(section, alice=row)
    tag, detail, code = _verdict_and_exit(text, findings, tmp_path)
    assert no_section in (detail or "")
    assert (tag, detail, code) == ("malformed", _unread_detail(text, row), 2)


# A findings table whose header names none of Severity, Issue and File, and
# whose first cell is no R<n> ref: no row of it reads as a findings row.
_UNRECOGNISED_TABLE = (
    "| ID | Consensus | Sev | Description | Location |\n"
    "|----|-----------|-----|-------------|----------|\n"
    f"| F1 | [3/3] | {CRIT} | crash on empty input | src/a.py:3 |\n"
    f"| F2 | [2/3] | {HIGH} | wrong default | src/b.py:10 |\n"
)


def test_a_second_table_like_block_is_not_swallowed_as_data(tmp_path: Path) -> None:
    """A findings table whose header carries neither Ref nor Consensus skips
    `_row_from_table`'s cell checks for both, so a later table-looking block
    used to be silently parsed as one more data row under the FIRST header's
    column positions instead of being refused - `in_table` never reset, so
    `_unread_token` also treated it as already read. A blank line between
    the two blocks must end the first table's run, so the second one is
    re-evaluated as its own header and refused when it is not a real one."""
    from cli import gate

    first_table = (
        "| Severity | Issue | File | Found By |\n"
        "|----------|-------|------|----------|\n"
        f"| {HIGH} | wrong default | src/b.py:10 | alice, bob |\n"
    )
    text = _review_text(
        f"## Consolidated Findings\n\n{first_table}\n{_UNRECOGNISED_TABLE}",
    )
    tag, detail = gate.findings_verdict(text, [], require_coverage=False)
    assert tag == "malformed"
    assert detail == _unread_detail(text, _UNRECOGNISED_TABLE.splitlines()[0])


def test_a_row_under_an_unrecognised_header_is_unreadable(tmp_path: Path) -> None:
    """The 00268 shape: an empty batch against a table the parser does not
    recognise passed as covering nothing, red row and all."""
    text = _review_text(f"## Consolidated Findings\n\n{_UNRECOGNISED_TABLE}")
    header = _UNRECOGNISED_TABLE.splitlines()[0]
    verdict = _verdict_and_exit(text, [], tmp_path)
    assert verdict == ("malformed", _unread_detail(text, header), 2)


def test_unreadable_detail_names_the_line_number_and_text() -> None:
    """The FIRST unconsumed line, 1-indexed, its text stripped and cut to 120
    characters - so the operator can find it without opening the parser."""
    from cli import gate

    long_row = f"   - [1/3] {CRIT} {'x' * 200} | src/a.py:3 | Found by: alice"
    later = f"- [1/3] {MED} second stray | src/f.py:9 | Found by: bob"
    text = _review_text(alice=long_row).replace("D1: pass", f"D1: pass\n{later}")
    assert text.splitlines()[8] == long_row
    stripped = long_row.strip()
    assert len(stripped) > 120
    tag, detail = gate.findings_verdict(text, _COVERED)
    assert tag == "malformed"
    assert detail == (
        "line 9: a [m/n] token or table row the findings parser did not read: "
        f"{stripped[:120]}"
    )


def test_no_section_no_tokens_and_no_findings_keeps_the_exit_1_shape_gap(
    tmp_path: Path,
) -> None:
    """Only a file with no section, no token and an empty batch is the exit-1
    shape gap; the same file under a batch naming rows is refused."""
    from cli import gate

    no_section = gate._FINDINGS_PROBLEMS["no-section"]
    assert _verdict_and_exit(GOOD_FILE, [], tmp_path) == ("malformed", no_section, 1)
    named = (
        "no '## Consolidated Findings' section, yet the findings JSON names "
        "2 rows: the findings heading is missing or misspelled"
    )
    assert _verdict_and_exit(GOOD_FILE, _COVERED, tmp_path) == ("malformed", named, 2)
    # k counts every row, whatever its classification: verify and discard rows
    # are rows the batch names too.
    mixed = [_r1_finding("fix"), _r2_finding("discard")]
    assert _verdict_and_exit(GOOD_FILE, mixed, tmp_path) == ("malformed", named, 2)
    one = named.replace("names 2 rows", "names 1 rows")
    verify = [_r1_finding("verify")]
    assert _verdict_and_exit(GOOD_FILE, verify, tmp_path) == ("malformed", one, 2)


# PRD 00277: a severity row needs no `[m/n]` token and no leading pipe to be a
# row. Each shape pairs a severity marker with a consensus-style marker or a
# column layout, in a shape the bullet and pipe-row readers never read.
def _unparsed_rows(mn: str, sev: str, word: str, issue: str, file: str) -> dict:
    """The seven unparsed shapes, built from one row's facts; `file` may be
    empty, the way a reviewer leaves the cell blank."""
    m, n = mn.split("/")
    tail = f"{issue} | {file}" if file else issue
    return {
        "emoji bullet, no token": f"- {sev} {word}: {tail} | Found by: alice",
        "spaced brackets": f"- [{m} / {n}] {sev} {tail}",
        "fullwidth brackets": f"- ［{mn}］ {sev} {tail}",
        "parentheses": f"- ({mn}) {sev} {tail}",
        "blockquoted table row": f"> | {word} | {file} | {issue} |",
        "pipe-less table": f"{mn}    {sev} {word}    {issue}    {file}    alice",
        "html table": (
            f"<table><tr><td>{sev} {word}</td><td>{file}</td>"
            f"<td>{issue}</td></tr></table>"
        ),
    }


# One row per consensus token, each with its own severity, issue text and file
# (a non-src path, a non-Python file, no file at all): no shared fixture text,
# path shape or severity stands in for the shape itself.
_ROW_FACTS = (
    (CRIT, "CRITICAL", "stale cache survives restart", "skills/x.py:3"),
    (HIGH, "HIGH", "retry loop never backs off", "lib/a.ts:9"),
    (MED, "MEDIUM", "token leaks into the log", ""),
)
_ROW_VARIANTS = [
    (token.strip("[]"), *facts) for token, facts in zip(_CONSENSUS_TOKENS, _ROW_FACTS)
]
_SHAPE_NAMES = tuple(_unparsed_rows(*_ROW_VARIANTS[0]))
_REVIEWER_BODIES = {
    "Alice": "- finding one",
    "Blake": "No spec drift found.",
    "Bob": "D1: pass",
}
_FINDINGS_SECTION = "Consolidated Findings"


def _placed(row: str, where: str) -> str:
    """The review with `row` as the body of `## {where}`; in the findings
    section it sits below the covered ref table, after a blank line."""
    if where == _FINDINGS_SECTION:
        return _review_text(f"{_REF_TABLE}\n{row}\n")
    return _review_text().replace(_REVIEWER_BODIES[where], row)


@pytest.mark.parametrize("where", [*_REVIEWER_BODIES, _FINDINGS_SECTION])
@pytest.mark.parametrize(
    "variant",
    _ROW_VARIANTS,
    ids=[f"{v[0]} {v[2]}" for v in _ROW_VARIANTS],
)
@pytest.mark.parametrize("shape", _SHAPE_NAMES)
def test_critical_row_in_unparsed_shape_is_malformed(
    shape: str,
    variant: tuple,
    where: str,
    tmp_path: Path,
) -> None:
    """Under any reviewer heading or inside the findings section beside the
    covered ref table: a severity row no reader parses is refused, named by its
    own line, exit 2 - with an empty batch and with the batch that covers every
    row the parser did read."""
    row = _unparsed_rows(*variant)[shape]
    text = _placed(row, where)
    assert row in text.splitlines()
    for findings in ([], _COVERED):
        verdict = _verdict_and_exit(text, findings, tmp_path)
        assert verdict == ("malformed", _unread_detail(text, row), 2)


def _near_variants() -> dict:
    """Each shape indented 1-3 spaces and tab-separated, plus spellings that
    no fixture prefix matches."""
    base = _unparsed_rows(*_ROW_VARIANTS[0])
    rows = {
        f"{name}, {k}-space indent": " " * k + row
        for name, row in base.items()
        for k in (1, 2, 3)
    }
    for name, row in base.items():
        tabbed = row.replace("    ", "\t").replace(" | ", "\t|\t")
        rows[f"{name}, tab-separated"] = tabbed.replace("><", ">\t<")
    return rows | {
        "asymmetric spaced brackets": f"- [2/ 2] {CRIT} stale cache | skills/x.py:3",
        "lenticular brackets": f"- 【2/2】 {HIGH} retry loop stalls | lib/a.ts:9",
        "upper-case html tags": f"<TABLE><TR><TD>{HIGH} HIGH</TD><TD>lib/a.ts:9</TD>",
        "nested blockquote": "> > | CRITICAL | lib/a.ts:9 | retry loop never backs off |",
        "dash after the severity": f"- {CRIT} CRITICAL - token leaks | lib/a.ts:9",
        "low severity emoji": "- ⚪ LOW: typo in the help text | docs/x.md:2",
    }


_NEAR_VARIANTS = _near_variants()


@pytest.mark.parametrize("row", list(_NEAR_VARIANTS.values()), ids=list(_NEAR_VARIANTS))
def test_a_near_variant_of_an_unparsed_shape_is_malformed(
    row: str,
    tmp_path: Path,
) -> None:
    """Spacing, indent, tabs, bracket pair and tag case do not hide a row."""
    text = _review_text(alice=row)
    verdict = _verdict_and_exit(text, _COVERED, tmp_path)
    assert verdict == ("malformed", _unread_detail(text, row), 2)


@pytest.mark.parametrize("word", ["Critical", "critical", "High", "medium", "LOW"])
@pytest.mark.parametrize(
    "template",
    ["> | {} | lib/a.ts:9 | retry loop never backs off |", "Row 3: | {} | lib/a.ts:9 |"],
    ids=["blockquoted", "text before the pipes"],
)
def test_a_pipe_bounded_severity_word_in_any_case_is_malformed(
    template: str,
    word: str,
    tmp_path: Path,
) -> None:
    """A severity word between pipes, with no emoji, is a row whatever its case:
    the table reader itself reads `Critical` and `critical` as one severity."""
    row = template.format(word)
    text = _review_text(alice=row)
    verdict = _verdict_and_exit(text, _COVERED, tmp_path)
    assert verdict == ("malformed", _unread_detail(text, row), 2)


@pytest.mark.parametrize(
    "row",
    [
        "- [2 / 2] stale cache survives restart | skills/x.py:3",
        "- ［2/2］ stale cache survives restart | skills/x.py:3",
        "- (2/2) stale cache survives restart | skills/x.py:3",
    ],
    ids=["spaced brackets", "fullwidth brackets", "parentheses"],
)
def test_a_consensus_marker_variant_without_a_severity_is_malformed(
    row: str,
    tmp_path: Path,
) -> None:
    """The marker variant is a consensus token on its own: no severity needed."""
    text = _review_text(alice=row)
    verdict = _verdict_and_exit(text, _COVERED, tmp_path)
    assert verdict == ("malformed", _unread_detail(text, row), 2)


_NOT_FINDINGS = {
    "heading and prose": "### Critical path\n\nTwo critical issues were found and fixed.",
    "prose bullet naming a file": "- Two CRITICAL issues fixed in src/a.py:3",
    "prose bullet, lower case": "- fixed the high-severity crash in lib/a.ts:9",
    "severity-free bullet": "- stale cache survives restart | skills/x.py:3 | alice",
    "severity-free blockquote": "> | note | skills/x.py:3 | stale cache survives |",
    "severity-free pipe-less": "2/2    note    stale cache    skills/x.py:3    alice",
    "severity-free html": "<table><tr><td>note</td><td>skills/x.py:3</td></tr></table>",
}


@pytest.mark.parametrize("prose", list(_NOT_FINDINGS.values()), ids=list(_NOT_FINDINGS))
def test_a_line_with_no_severity_signal_is_not_a_row(prose: str) -> None:
    """Prose naming a severity word or a file, and a row shape carrying no
    severity and no marker variant, are not findings: the covered batch passes."""
    from cli import gate

    assert gate.findings_verdict(_review_text(alice=prose), _COVERED) == ("ok", None)


@pytest.mark.parametrize("shape", _SHAPE_NAMES)
def test_an_unparsed_row_above_a_stray_token_is_the_line_named(shape: str) -> None:
    """The refusal names the FIRST unread line: an unparsed severity row above
    a stray `- [1/3]` bullet, not the bullet a token-only pass would hit."""
    from cli import gate

    row = _unparsed_rows(*_ROW_VARIANTS[1])[shape]
    stray = f"- [1/3] {MED} second stray | src/f.py:9 | Found by: bob"
    text = _review_text(alice=row).replace("D1: pass", f"D1: pass\n{stray}")
    lines = text.splitlines()
    assert lines.index(row) < lines.index(stray)
    verdict = gate.findings_verdict(text, _COVERED)
    assert verdict == ("malformed", _unread_detail(text, row))


if __name__ == "__main__":
    unittest.main()
