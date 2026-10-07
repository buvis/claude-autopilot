#!/usr/bin/env python3
"""The pipe-table and Ref-column half of the `gate --findings` cross-check.

Split out of test_gate.py to keep every file under the 800-line limit
(rules/coding-style.md). The bullet-shape half, the CLI wiring and the shared
`_review` / `_findings` / `_gate` helpers stay there; the tests fed the real
saved review artifacts live in test_gate_findings_real_fixtures.py, which
imports the table helpers below.
"""

from __future__ import annotations

import subprocess
import sys
import unittest
from itertools import combinations
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
# The TestCase class is reached through the module: binding its name here would
# make pytest collect that whole suite a second time under this file.
from cli import test_gate as gate_tests
from cli.test_gate import CLI_DIR, CRIT, GOOD_FILE, HIGH, MED, _row

# The shape this repo emits: Task sits between File and Found By.
TABLE_HEADER_6 = (
    "| Consensus | Severity | Issue | File | Task | Found By |\n"
    "|-----------|----------|-------|------|------|----------|\n"
)
# The shape references/output-formats.md documents.
TABLE_HEADER_5 = (
    "| Consensus | Severity | Issue | File | Found By |\n"
    "|-----------|----------|-------|------|----------|\n"
)
TABLE_HEADER_REF_6 = (
    "| Ref | Consensus | Severity | Issue | File | Task | Found By |\n"
    "|-----|-----------|----------|-------|------|------|----------|\n"
)
# The documented shape, with the Ref column a coverable section needs.
TABLE_HEADER_REF_5 = (
    "| Ref | Consensus | Severity | Issue | File | Found By |\n"
    "|-----|-----------|----------|-------|------|----------|\n"
)

# The five dispositions a findings row may carry. Asserted against
# gate.KNOWN_CLASSIFICATIONS below, so a drift in either is a failure.
KNOWN_CLASSIFICATIONS = ("verify", "discard", "fix", "defer", "carry")


def _table_section(header: str, *rows: str) -> str:
    """A consolidated-findings section whose findings live in a pipe table."""
    return "## Consolidated Findings\n\n" + header + "".join(f"{r}\n" for r in rows)


def _table_row(sev: str, issue: str, file: str) -> str:
    return f"| [2/4] | {sev} | {issue} | {file} | 3 | ALICE, BOB |"


def _ref_row(ref: str, sev: str, issue: str, file: str) -> str:
    return f"| {ref} | [2/4] | {sev} | {issue} | {file} | 3 | ALICE, BOB |"


def _ref_cell_row(ref: str, consensus: str) -> str:
    """A TABLE_HEADER_REF_6 data row whose Ref and Consensus cells are spelled
    verbatim, so a test can hand either one an off-shape value."""
    return f"| {ref} | {consensus} | {HIGH} | wrong default | src/b.py:10 | 3 | A, B |"


def _r1_finding(cls: str) -> dict:
    """A findings-JSON row naming the R1 row `_ref_cell_row` writes."""
    return dict(_row(HIGH, "src/b.py:10", "wrong default", cls), ref="R1")


def _check(text: str, rows: list[dict]) -> tuple[str, str | None]:
    from cli import gate

    return gate._cross_check_findings(text, rows)


def _keys(text: str) -> tuple[list, str | None]:
    from cli import gate

    return gate._reviewed_keys(text)


class FindingsTableCrossCheckTests(unittest.TestCase):
    """The same one-direction cross-check, fed the pipe-table review shape.

    Borrows the fixture helpers rather than subclassing FindingsCrossCheckTests,
    which would re-run that whole subprocess-heavy suite under a second name.
    """

    setUp = gate_tests.FindingsCrossCheckTests.setUp
    _review = gate_tests.FindingsCrossCheckTests._review
    _findings = gate_tests.FindingsCrossCheckTests._findings
    _gate = gate_tests.FindingsCrossCheckTests._gate

    def test_cross_check_reads_a_pipe_table_review_file(self) -> None:
        # The shape every saved review file actually uses. The chosen rows are
        # copied out of it verbatim, so the batch is honest and must pass.
        text = _table_section(
            TABLE_HEADER_REF_6,
            _ref_row("R1", CRIT, "crash on empty input", "src/a.py:3"),
            _ref_row("R2", HIGH, "wrong default", "src/b.py:10"),
        )
        rows = [
            dict(_row(CRIT, "src/a.py:3", "crash on empty input"), ref="R1"),
            dict(_row(HIGH, "src/b.py:10", "wrong default"), ref="R2"),
        ]
        self.assertEqual(_check(text, rows), ("ok", None))

    def test_table_columns_are_located_by_header_name_not_position(self) -> None:
        # File and Issue swapped against the shape this repo emits. A reader
        # that guesses the layout from the column count, or from a fixed
        # position, hands back the Issue cell as the file.
        text = (
            "## Consolidated Findings\n\n"
            "| Ref | Consensus | Severity | File | Issue | Task | Found By |\n"
            "|-----|-----------|----------|------|-------|------|----------|\n"
            f"| R1 | [2/4] | {HIGH} | src/b.py:10 | wrong default | 3 | ALICE, BOB |\n"
        )
        rows, err = _keys(text)
        self.assertIsNone(err)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].file, "src/b.py:10")
        self.assertEqual(rows[0].issue, "wrong default")
        chosen = [dict(_row(HIGH, "src/b.py:10", "wrong default"), ref="R1")]
        self.assertEqual(_check(text, chosen), ("ok", None))

    def test_cross_check_matches_by_ref_regardless_of_issue_wording(self) -> None:
        text = _table_section(
            TABLE_HEADER_REF_6,
            _ref_row("R1", HIGH, "`run_gate` is 60 lines", "src/v.py:181"),
        )
        chosen = [
            {
                "classification": "fix",
                "ref": "R1",
                "severity": "high",
                "file": "src/v.py:181",
                "issue": "FIX: run_gate is 60 lines. Trim the docstring.",
            },
        ]
        self.assertEqual(_check(text, chosen), ("ok", None))

    def test_cross_check_refuses_a_ref_the_review_file_does_not_contain(self) -> None:
        # The issue text, severity and file all match the R1 row: a row that
        # names a ref is backed by that ref or not at all.
        text = _table_section(
            TABLE_HEADER_REF_6,
            _ref_row("R1", HIGH, "wrong default", "src/b.py:10"),
        )
        chosen = [dict(_row(HIGH, "src/b.py:10", "wrong default"), ref="R9")]
        tag, detail = _check(text, chosen)
        self.assertEqual(tag, "mismatch")
        self.assertIn("R9", detail or "")
        # R2 is a prefix of the only ref this review holds: a ref is matched
        # whole, never as a substring.
        prefixed = _table_section(
            TABLE_HEADER_REF_6,
            _ref_row("R20", HIGH, "wrong default", "src/b.py:10"),
        )
        row = _row(HIGH, "src/b.py:10", "wrong default")
        tag, detail = _check(prefixed, [dict(row, ref="R2")])
        self.assertEqual(tag, "mismatch")
        self.assertIn("R2", detail or "")
        # Control: the whole ref is backed, so this is not a refuse-everything.
        self.assertEqual(_check(prefixed, [dict(row, ref="R20")]), ("ok", None))

    def test_cross_check_refuses_a_ref_whose_severity_or_file_disagrees(self) -> None:
        text = _table_section(
            TABLE_HEADER_REF_6,
            _ref_row("R1", HIGH, "wrong default", "src/b.py:10"),
        )
        cases = {
            "severity disagrees": _row(CRIT, "src/b.py:10", "wrong default"),
            "file disagrees": _row(HIGH, "src/elsewhere.py:10", "wrong default"),
        }
        for label, chosen in cases.items():
            with self.subTest(label):
                tag, detail = _check(text, [dict(chosen, ref="R1")])
                self.assertEqual(tag, "mismatch")
                self.assertTrue(detail)
        # Control, so a refuse-everything implementation cannot pass: the same
        # ref with an agreeing severity and file is backed.
        agreeing = dict(_row(HIGH, "src/b.py:10", "wrong default"), ref="R1")
        self.assertEqual(_check(text, [agreeing]), ("ok", None))

    def test_cross_check_still_refuses_a_different_finding_about_the_same_file(
        self,
    ) -> None:
        # No containment, no prefix threshold, no similarity score: without a
        # ref, a second issue at the same severity and file is backed only by
        # its own review row.
        reviewed = "the drain never closes both pipes before waiting"
        text = _table_section(
            TABLE_HEADER_REF_6,
            _ref_row("R1", HIGH, reviewed, "src/v.py:1"),
        )
        cases = {
            "unrelated wording": "the gate reuses a record it never measured",
            "a prefix of the reviewed row": "the drain never closes",
            "the reviewed row plus a sentence": f"{reviewed}. Apply the deadline.",
        }
        for label, issue in cases.items():
            with self.subTest(label):
                # The first row names R1, so coverage is satisfied and the
                # second row's unbacked text is the only thing left to refuse.
                chosen = [
                    dict(_row(HIGH, "src/v.py:1", reviewed), ref="R1"),
                    _row(HIGH, "src/v.py:1", issue),
                ]
                tag, detail = _check(text, chosen)
                self.assertEqual(tag, "mismatch")
                self.assertIn(issue, detail or "")

    def test_cross_check_refuses_an_empty_issue_with_no_ref(self) -> None:
        # An empty issue would otherwise key as a substring of everything.
        text = _table_section(
            TABLE_HEADER_REF_6,
            _ref_row("R1", HIGH, "wrong default", "src/b.py:10"),
        )
        for label, issue in {"empty": "", "whitespace only": "   "}.items():
            with self.subTest(label):
                tag, detail = _check(text, [_row(HIGH, "src/b.py:10", issue)])
                self.assertEqual(tag, "mismatch")
                self.assertTrue(detail)
        # Control: the same table does back the row it really holds.
        self.assertEqual(
            _check(text, [dict(_row(HIGH, "src/b.py:10", "wrong default"), ref="R1")]),
            ("ok", None),
        )

    def test_a_ref_less_chosen_row_still_matches_exactly_as_before(self) -> None:
        from cli import gate

        text = _table_section(
            TABLE_HEADER_REF_6,
            _ref_row("R1", MED, "unclear name", "src/c.py:20"),
        )
        # A row carrying no ref covers no review row, so coverage is off here:
        # text keying is what this test is about.
        self.assertEqual(
            gate._cross_check_findings(
                text,
                [_row(MED, "src/c.py:20", "unclear name")],
                require_coverage=False,
            ),
            ("ok", None),
        )
        # The key is the whole (severity, file, issue) triple: changing any one
        # of the three on its own leaves the row unbacked.
        cases = {
            "only the issue text differs": _row(MED, "src/c.py:20", "unclear naming"),
            "only the severity differs": _row(HIGH, "src/c.py:20", "unclear name"),
            "only the file differs": _row(MED, "src/d.py:20", "unclear name"),
        }
        for label, chosen in cases.items():
            with self.subTest(label):
                tag, detail = _check(text, [chosen])
                self.assertEqual(tag, "mismatch")
                self.assertTrue(detail)

    def test_gate_imports_cleanly_as_the_first_package_import(self) -> None:
        # cli/convergence.py imports from cli/gate.py, never the reverse: in a
        # fresh interpreter `import cli.gate` must stand on its own, and carry
        # the table-row detector convergence consumes.
        proc = subprocess.run(
            [sys.executable, "-c", "import cli.gate; cli.gate.TABLE_DATA_ROW_RE"],
            cwd=str(CLI_DIR.parent),
            capture_output=True,
            text=True,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        from cli import gate

        # That detector has to find real data rows and only those: convergence
        # counts severities with it, so a regex matching nothing counts none,
        # and one matching the header or the |---| rule counts phantoms.
        data_row = _table_row(HIGH, "wrong default", "src/b.py:10")
        self.assertTrue(gate.TABLE_DATA_ROW_RE.match(data_row))
        # The old exact single-space spelling must keep counting.
        old_spelling = f"| [2/4] | {HIGH} | x | src/b.py:10 | 3 | B |"
        self.assertTrue(gate.TABLE_DATA_ROW_RE.match(old_spelling))
        not_data = {
            "header": "| Consensus | Severity | Issue | File | Task | Found By |",
            "separator": "|-----------|----------|-------|------|------|----------|",
        }
        for label, line in not_data.items():
            with self.subTest(label):
                self.assertIsNone(gate.TABLE_DATA_ROW_RE.search(line))

    def test_a_findings_table_whose_rows_do_not_match_is_malformed(self) -> None:
        no_required_columns = _table_section(
            "| Consensus | Who | Note |\n|-----------|-----|------|\n",
            "| [2/4] | ALICE | something happened |",
        )
        broken_rows = _table_section(TABLE_HEADER_6, "| [2/4]", "| |")
        chosen = [_row(HIGH, "src/b.py:10", "wrong default")]
        no_section_detail = _check(GOOD_FILE, chosen)[1]
        cases = {
            "header names no severity, issue or file": no_required_columns,
            "data rows do not match the row shape": broken_rows,
        }
        for label, text in cases.items():
            with self.subTest(label):
                self.assertEqual(_keys(text), ([], "unreadable-table"))
                tag, detail = _check(text, chosen)
                self.assertEqual(tag, "malformed")
                reason = (detail or "").lower()
                self.assertIn("row", reason)
                # The reason has to name what failed, not just say "row": the
                # operator fixes the table or its header from this text alone.
                self.assertTrue(
                    "table" in reason or "header" in reason,
                    f"table-specific reason expected, got {detail!r}",
                )
                # Not the missing-section reason: the operator has to know the
                # section is there and the table is what failed.
                self.assertNotEqual(detail, no_section_detail)
        # A table the gate cannot read is a refusal, exit 2: it cannot tell
        # whether the batch covers rows it was unable to parse.
        proc = self._gate(self._review(section=broken_rows), self._findings(chosen))
        self.assertEqual(proc.returncode, 2, proc.stdout)
        self.assertNotIn("unrecognized arguments", proc.stderr)
        # Control, so exit 2 above is not a hardcoded exit code: the OTHER
        # malformed reason, a review file carrying no findings section at all,
        # is the operator's own shape gap and stays exit 1.
        proc = self._gate(self._review(section=""), self._findings(chosen))
        self.assertEqual(proc.returncode, 1, proc.stdout)

    def test_a_truncated_data_row_is_malformed_not_a_crash(self) -> None:
        # `| [2/4] |` matches the data-row shape yet splits to ONE cell, so the
        # Severity column the header names (index 1, and index 2 once a Ref
        # column leads) is out of range. Reading it by index raises IndexError
        # and kills the review verb; the gate owes the operator `malformed`.
        chosen = [_row(HIGH, "src/b.py:10", "wrong default")]
        cases = {
            "one cell under the 6-column header": _table_section(
                TABLE_HEADER_6,
                "| [2/4] |",
            ),
            "two cells under the 7-column Ref header": _table_section(
                TABLE_HEADER_REF_6,
                "| R1 | [2/4] |",
            ),
        }
        for label, text in cases.items():
            with self.subTest(label):
                self.assertEqual(_keys(text), ([], "unreadable-table"))
                tag, detail = _check(text, chosen)
                self.assertEqual(tag, "malformed")
                self.assertTrue(detail)
                proc = self._gate(self._review(section=text), self._findings(chosen))
                # An unreadable table is the exit-2 refusal, and an uncaught
                # exception would exit 1, so this also rules the crash out.
                self.assertEqual(proc.returncode, 2, proc.stdout)
                self.assertNotIn("Traceback", proc.stderr)

    def test_table_row_issue_containing_a_pipe_keys_correctly(self) -> None:
        # Real review rows quote tables, so the issue cell carries bare pipes.
        from cli import gate

        issue = "the header `| Consensus | Severity |` is read by name"
        text = _table_section(
            TABLE_HEADER_REF_6,
            _ref_row("R1", HIGH, issue, "src/b.py:10"),
        )
        rows, err = _keys(text)
        self.assertIsNone(err)
        self.assertEqual(len(rows), 1)
        # The extra pipes must not shift the Ref cell off R1 either.
        self.assertEqual(rows[0].ref, "R1")
        self.assertEqual(rows[0].file, "src/b.py:10")
        # Keyed by text, not by R1: a ref match would skip the issue cell.
        chosen = [_row(HIGH, "src/b.py:10", issue)]
        self.assertEqual(
            gate._cross_check_findings(text, chosen, require_coverage=False),
            ("ok", None),
        )

    def test_cross_check_reads_the_five_column_documented_table(self) -> None:
        text = _table_section(
            TABLE_HEADER_REF_5,
            f"| R1 | [3/3] | {CRIT} Critical | XSS in input handler | src/input.ts "
            "| Alice, Bob |",
        )
        rows, err = _keys(text)
        self.assertIsNone(err)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].file, "src/input.ts")
        chosen = [
            dict(_row("critical", "src/input.ts", "XSS in input handler"), ref="R1"),
        ]
        self.assertEqual(_check(text, chosen), ("ok", None))
        # A Severity cell spelled as the bare English word, no emoji at all:
        # reading only the cell's first character would key it as nothing and
        # refuse the row.
        worded = _table_section(
            TABLE_HEADER_REF_5,
            "| R1 | [3/3] | High | wrong default | src/b.py:10 | Alice, Bob |",
        )
        by_word, word_err = _keys(worded)
        self.assertIsNone(word_err)
        self.assertEqual(len(by_word), 1)
        self.assertEqual(by_word[0].severity, "high")
        emoji_text = _table_section(
            TABLE_HEADER_REF_6,
            _ref_row("R1", HIGH, "wrong default", "src/b.py:10"),
        )
        by_emoji, _emoji_err = _keys(emoji_text)
        self.assertEqual(by_word[0].severity, by_emoji[0].severity)
        worded_chosen = [dict(_row(HIGH, "src/b.py:10", "wrong default"), ref="R1")]
        self.assertEqual(_check(worded, worded_chosen), ("ok", None))

    def test_table_and_bullet_rows_key_identically(self) -> None:
        from cli import gate

        bullet = (
            "## Consolidated Findings\n\n"
            f"- [2/3] {HIGH} wrong default | src/b.py:10 | Found by: alice, bob\n"
        )
        table = _table_section(
            TABLE_HEADER_6,
            _table_row(HIGH, "wrong default", "src/b.py:10"),
        )
        from_bullet, _bullet_err = _keys(bullet)
        from_table, _table_err = _keys(table)
        self.assertEqual(len(from_bullet), 1)
        self.assertEqual(len(from_table), 1)
        self.assertEqual(
            (from_bullet[0].severity, from_bullet[0].file, from_bullet[0].issue),
            (from_table[0].severity, from_table[0].file, from_table[0].issue),
        )
        # Neither shape invents a ref: a bullet carries none and this table has
        # no Ref column.
        self.assertEqual(from_bullet[0].ref, "")
        self.assertEqual(from_table[0].ref, "")
        # Neither shape can be covered, so both are asked the keying question
        # alone: with coverage required they are refused outright (see
        # test_bullet_rows_without_ref_need_coverage_and_are_refused).
        chosen = [_row(HIGH, "src/b.py:10", "wrong default")]
        for label, text in {"bullet": bullet, "table": table}.items():
            with self.subTest(label):
                self.assertEqual(
                    gate._cross_check_findings(text, chosen, require_coverage=False),
                    ("ok", None),
                )
                # So a chosen row naming R1 is not backed by either review:
                # nothing in them holds that ref, however well the text lines up.
                tag, detail = gate._cross_check_findings(
                    text,
                    [dict(chosen[0], ref="R1")],
                    require_coverage=False,
                )
                self.assertEqual(tag, "mismatch")
                self.assertIn("R1", detail or "")

    def test_escaped_pipe_in_a_table_cell_keys_like_an_unescaped_one(self) -> None:
        # Normalization applies to BOTH sides, so a verbatim-copied escaped row
        # and a hand-unescaped one key the same.
        from cli import gate

        plain = "the shape | Consensus | Severity | is a table"
        escaped = plain.replace("|", "\\|")
        cases = {
            "escaped review cell, plain chosen value": (escaped, plain),
            "escaped on both sides (a verbatim copy)": (escaped, escaped),
            "plain review cell, escaped chosen value": (plain, escaped),
        }
        for label, (cell, value) in cases.items():
            with self.subTest(label):
                text = _table_section(
                    TABLE_HEADER_REF_6,
                    _ref_row("R1", HIGH, cell, "src/b.py:10"),
                )
                # The chosen row names no ref on purpose: matching on R1 would
                # skip the issue cell, which is the cell under test.
                chosen = [_row(HIGH, "src/b.py:10", value)]
                self.assertEqual(
                    gate._cross_check_findings(text, chosen, require_coverage=False),
                    ("ok", None),
                )

    def test_table_row_absent_from_the_findings_json_is_still_not_a_mismatch(
        self,
    ) -> None:
        from cli import gate

        text = _table_section(
            TABLE_HEADER_REF_6,
            _ref_row("R1", CRIT, "crash on empty input", "src/a.py:3"),
            _ref_row("R2", HIGH, "wrong default", "src/b.py:10"),
            _ref_row("R3", MED, "unclear name", "src/c.py:20"),
        )
        chosen = [_row(HIGH, "src/b.py:10", "wrong default")]
        # Not a mismatch is the claim here; the two unmentioned rows are a
        # coverage question, which `test_dropped_table_row_is_uncovered` owns.
        self.assertEqual(
            gate._cross_check_findings(text, chosen, require_coverage=False),
            ("ok", None),
        )

    def test_dropped_table_row_is_uncovered(self) -> None:
        # Hold stub 00260 / PRD 00264: the cross-check used to look only one
        # way (a chosen row the review never recorded is refused). A review
        # row the findings JSON drops entirely passed silently - this is the
        # other direction, now also refused, named by its Ref.
        text = _table_section(
            TABLE_HEADER_REF_6,
            _ref_row("R1", HIGH, "wrong default", "src/b.py:10"),
            _ref_row("R2", MED, "unclear name", "src/c.py:20"),
        )
        chosen = [dict(_row(HIGH, "src/b.py:10", "wrong default"), ref="R1")]
        tag, detail = _check(text, chosen)
        self.assertEqual(tag, "uncovered")
        self.assertIn("R2", detail or "")
        self.assertIn("classification", (detail or "").lower())
        # Control: naming both refs leaves nothing uncovered.
        covered = chosen + [
            dict(_row(MED, "src/c.py:20", "unclear name"), ref="R2"),
        ]
        self.assertEqual(_check(text, covered), ("ok", None))

    def test_discarded_row_counts_as_covered(self) -> None:
        # A `discard` row is never applied to state, but it is still the
        # operator's explicit disposition for that review row - it must count
        # as coverage, not leave the row looking dropped.
        text = _table_section(
            TABLE_HEADER_REF_6,
            _ref_row("R1", HIGH, "wrong default", "src/b.py:10"),
            _ref_row("R2", MED, "unclear name", "src/c.py:20"),
        )
        chosen = [
            dict(_row(HIGH, "src/b.py:10", "wrong default"), ref="R1"),
            dict(_row(MED, "src/c.py:20", "unclear name", "discard"), ref="R2"),
        ]
        self.assertEqual(_check(text, chosen), ("ok", None))

    def test_carry_row_counts_as_covered(self) -> None:
        # A re-queued `[C{cycle}]` row is classified `carry` - like `discard`,
        # it is never applied to state, but it is still the operator's
        # explicit disposition for that review row, so it counts as coverage.
        text = _table_section(
            TABLE_HEADER_REF_6,
            _ref_row("R1", HIGH, "wrong default", "src/b.py:10"),
            _ref_row("R2", MED, "unclear name", "src/c.py:20"),
        )
        chosen = [
            dict(_row(HIGH, "src/b.py:10", "wrong default"), ref="R1"),
            dict(_row(MED, "src/c.py:20", "unclear name", "carry"), ref="R2"),
        ]
        self.assertEqual(_check(text, chosen), ("ok", None))

    def test_tail_sweep_subset_of_a_ref_table_is_not_uncovered(self) -> None:
        # The tail-sweep step's findings JSON is a deliberate, documented
        # subset of the consolidated table (actionable Medium/Low rows only),
        # so the reverse coverage check must not apply to it.
        from cli import gate

        text = _table_section(
            TABLE_HEADER_REF_6,
            _ref_row("R1", HIGH, "wrong default", "src/b.py:10"),
            _ref_row("R2", MED, "unclear name", "src/c.py:20"),
        )
        chosen = [dict(_row(MED, "src/c.py:20", "unclear name"), ref="R2")]
        self.assertEqual(
            gate._cross_check_findings(text, chosen, require_coverage=False),
            ("ok", None),
        )
        # Control: the same partial JSON under full coverage still refuses.
        tag, detail = gate._cross_check_findings(text, chosen)
        self.assertEqual(tag, "uncovered")
        self.assertIn("R1", detail or "")

    def test_bullet_rows_without_ref_need_coverage_and_are_refused(self) -> None:
        # Bullet-shape rows, and table rows with no Ref column, key with an
        # empty ref. Exempting them from coverage is what let a severe finding
        # leave the gate uncovered, so a section holding one is refused: there
        # is no ref a findings row could name, and the gate says so.
        from cli import gate

        bullet = (
            "## Consolidated Findings\n\n"
            f"- [2/3] {HIGH} wrong default | src/b.py:10 | Found by: alice, bob\n"
        )
        table_no_ref = _table_section(
            TABLE_HEADER_6,
            _table_row(HIGH, "wrong default", "src/b.py:10"),
        )
        for label, text in {"bullet": bullet, "table_no_ref": table_no_ref}.items():
            with self.subTest(label):
                tag, detail = _check(text, [])
                self.assertEqual(tag, "ref-required")
                self.assertTrue(detail)
                proc = self._gate(self._review(section=text), self._findings([]))
                self.assertEqual(proc.returncode, 2, proc.stdout)
                self.assertNotIn("Traceback", proc.stderr)
        # Two controls, so this is not a refuse-everything: a findings section
        # with no rows at all has nothing to cover and passes, and a caller that
        # does not require coverage never sees `ref-required`.
        self.assertEqual(
            _check(gate_tests.EMPTY_FINDINGS_SECTION, []),
            ("ok", None),
        )
        self.assertEqual(
            gate._cross_check_findings(table_no_ref, [], require_coverage=False),
            ("ok", None),
        )


# The parser fails closed: one off-shape cell makes the whole table unreadable
# rather than quietly dropping the row (and the finding) it could not read.
_REF_CELL_CASES = {
    # The one accepted spelling that is not already `R1`: a ref is read
    # case-insensitively and normalized to upper case.
    "lowercase r1 is read as R1": ("r1", "[2/4]", "R1"),
    "trailing dot": ("R1.", "[2/4]", None),
    "trailing letter": ("R1a", "[2/4]", None),
    "two refs in one cell": ("R1 | R3", "[2/4]", None),
    "empty ref cell": ("", "[2/4]", None),
    "unbracketed consensus cell": ("R1", "2/2", None),
}


@pytest.mark.parametrize(
    ("ref_cell", "consensus_cell", "expected_ref"),
    list(_REF_CELL_CASES.values()),
    ids=list(_REF_CELL_CASES),
)
def test_rejects_review_row_with_offshape_ref_instead_of_skipping_it(
    ref_cell: str,
    consensus_cell: str,
    expected_ref: str | None,
) -> None:
    # The second row is well-formed, so skipping the first one would leave a
    # readable one-row table: that is the silent skip this test rules out, and
    # an off-shape-row-plus-empty-table reading cannot pass here.
    text = _table_section(
        TABLE_HEADER_REF_6,
        _ref_cell_row(ref_cell, consensus_cell),
        _ref_row("R2", MED, "unclear name", "src/c.py:20"),
    )
    chosen = [_r1_finding("fix"), {"ref": "R2", "classification": "discard"}]
    rows, err = _keys(text)
    if expected_ref is None:
        # One off-shape row makes the WHOLE table unreadable, R2 included: a
        # row the gate cannot read may be the severe finding it owes coverage.
        assert (rows, err) == ([], "unreadable-table")
        tag, detail = _check(text, chosen)
        assert tag == "malformed"
        assert detail
        return
    assert err is None
    assert [r.ref for r in rows] == [expected_ref, "R2"]
    assert _check(text, chosen) == ("ok", None)


def test_refless_table_with_findings_is_unreadable() -> None:
    """A findings table with no Ref column cannot be covered: no findings row
    can name a ref the table never handed out. The gate returns `ref-required`
    instead of passing the section as if it had been checked."""
    from cli import gate

    text = _table_section(
        TABLE_HEADER_6,
        _table_row(HIGH, "wrong default", "src/b.py:10"),
    )
    chosen = [_row(HIGH, "src/b.py:10", "wrong default")]
    tag, detail = _check(text, chosen)
    assert tag == "ref-required"
    assert detail
    # Two controls: a section with no rows has nothing to cover, and the same
    # Ref-less table passes when the caller does not require coverage.
    assert _check(gate_tests.EMPTY_FINDINGS_SECTION, []) == ("ok", None)
    assert gate._cross_check_findings(text, chosen, require_coverage=False) == (
        "ok",
        None,
    )


def test_duplicate_table_ref_is_refused() -> None:
    """Two rows sharing a ref make every findings row naming it ambiguous, so
    the table is unreadable rather than silently keyed to the first row."""
    text = _table_section(
        TABLE_HEADER_REF_6,
        _ref_row("R1", HIGH, "wrong default", "src/b.py:10"),
        _ref_row("R1", MED, "unclear name", "src/c.py:20"),
    )
    assert _keys(text) == ([], "unreadable-table")
    tag, detail = _check(text, [_r1_finding("fix")])
    assert tag == "malformed"
    assert detail
    # Refs are normalized before they are compared, so `r1` IS `R1` here.
    mixed_case = _table_section(
        TABLE_HEADER_REF_6,
        _ref_row("R1", HIGH, "wrong default", "src/b.py:10"),
        _ref_row("r1", MED, "unclear name", "src/c.py:20"),
    )
    assert _keys(mixed_case) == ([], "unreadable-table")
    # Control: the same two rows under distinct refs read fine, so it is the
    # duplicate that is refused, not the pair of rows.
    distinct = _table_section(
        TABLE_HEADER_REF_6,
        _ref_row("R1", HIGH, "wrong default", "src/b.py:10"),
        _ref_row("R2", MED, "unclear name", "src/c.py:20"),
    )
    rows, err = _keys(distinct)
    assert err is None
    assert [r.ref for r in rows] == ["R1", "R2"]


@pytest.mark.parametrize(
    ("first", "second"),
    list(combinations(KNOWN_CLASSIFICATIONS, 2)),
)
def test_ref_with_two_classifications_is_refused(first: str, second: str) -> None:
    """One review row cannot hold two dispositions. Two findings rows naming R1
    with different classifications is a refusal for every pair of them."""
    text = _table_section(
        TABLE_HEADER_REF_6,
        _ref_row("R1", HIGH, "wrong default", "src/b.py:10"),
    )
    tag, detail = _check(text, [_r1_finding(first), _r1_finding(second)])
    assert tag == "mismatch"
    assert "R1" in (detail or "")
    # The same ref twice with the SAME classification says nothing
    # contradictory, so it is not an error.
    assert _check(text, [_r1_finding(first), _r1_finding(first)]) == ("ok", None)


def test_ghost_carry_row_is_refused_like_any_other() -> None:
    """A `carry` row used to skip the cross-check. One naming a ref the review
    table never handed out is a fabricated disposition, so it is refused."""
    text = _table_section(
        TABLE_HEADER_REF_6,
        _ref_row("R1", HIGH, "wrong default", "src/b.py:10"),
    )
    ghost = dict(_row(HIGH, "src/b.py:10", "wrong default", "carry"), ref="R9")
    tag, detail = _check(text, [_r1_finding("fix"), ghost])
    assert tag == "mismatch"
    assert "R9" in (detail or "")
    # Control: the same carry row, naming the ref the table does hold, is backed.
    assert _check(text, [_r1_finding("carry")]) == ("ok", None)


def test_findings_verdict_is_the_cross_check_alias() -> None:
    """Callers outside the gate read the public name, so it has to hand back the
    same tuple, including the coverage-on default."""
    from cli import gate

    text = _table_section(
        TABLE_HEADER_REF_6,
        _ref_row("R1", HIGH, "wrong default", "src/b.py:10"),
        _ref_row("R2", MED, "unclear name", "src/c.py:20"),
    )
    chosen = [dict(_row(HIGH, "src/b.py:10", "wrong default"), ref="R1")]
    # The two settings give different verdicts here, so an alias that ignored
    # require_coverage, or defaulted it to False, cannot pass.
    assert gate.findings_verdict(text, chosen)[0] == "uncovered"
    for require in (True, False):
        assert gate.findings_verdict(
            text,
            chosen,
            require_coverage=require,
        ) == gate._cross_check_findings(text, chosen, require)
    assert gate.findings_verdict(text, chosen) == gate._cross_check_findings(
        text,
        chosen,
    )


def test_known_classifications_are_the_five_review_dispositions() -> None:
    from cli import gate

    assert gate.KNOWN_CLASSIFICATIONS == KNOWN_CLASSIFICATIONS
    for value in KNOWN_CLASSIFICATIONS:
        assert gate.known_classification(value) is True
    for value in ("fxi", "FIX", "fix ", "", None, 1, True, ["fix"]):
        assert gate.known_classification(value) is False


if __name__ == "__main__":
    unittest.main()
