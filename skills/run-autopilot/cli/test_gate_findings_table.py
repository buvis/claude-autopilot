#!/usr/bin/env python3
"""The pipe-table and Ref-column half of the `gate --findings` cross-check.

Split out of test_gate.py to keep every file under the 800-line limit
(rules/coding-style.md). The bullet-shape half, the CLI wiring and the shared
`_review` / `_findings` / `_gate` helpers stay there.
"""

from __future__ import annotations

import json
import subprocess
import sys
import unittest
from itertools import groupby
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
# The TestCase class is reached through the module: binding its name here would
# make pytest collect that whole suite a second time under this file.
from cli import test_gate as gate_tests
from cli.test_gate import CLI_DIR, CRIT, GOOD_FILE, HIGH, MED, _row

# Real artifacts of review cycle 1 of PRD 00256: a saved review file whose
# consolidated-findings section is a populated 22-row 6-column pipe table, and
# the 18-row chosen-findings JSON an orchestrator derived from it after
# re-wording every issue.
FIXTURES = CLI_DIR / "fixtures"
REAL_REVIEW = FIXTURES / "00256-review-1.md"
REAL_FINDINGS = FIXTURES / "00256-rework-1-findings.json"

# Which review-table row (1-based, table order) each row of that chosen-findings
# JSON applies, in the JSON's own order: rows 1, 17, 21 and 22 were not chosen.
REAL_CHOSEN_REVIEW_ROWS = [*range(2, 17), 18, 19, 20]

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


def _table_section(header: str, *rows: str) -> str:
    """A consolidated-findings section whose findings live in a pipe table."""
    return "## Consolidated Findings\n\n" + header + "".join(f"{r}\n" for r in rows)


def _table_row(sev: str, issue: str, file: str) -> str:
    return f"| [2/4] | {sev} | {issue} | {file} | 3 | ALICE, BOB |"


def _ref_row(ref: str, sev: str, issue: str, file: str) -> str:
    return f"| {ref} | [2/4] | {sev} | {issue} | {file} | 3 | ALICE, BOB |"


def _with_ref_column(text: str) -> str:
    """The same review text with a leading `Ref` column of R1, R2, ... ."""
    out: list[str] = []
    seen = 0
    for line in text.splitlines(keepends=True):
        if line.startswith("| Consensus |"):
            out.append(f"| Ref {line}")
        elif line.startswith("|---"):
            out.append(f"|-----{line}")
        elif line.startswith("| ["):
            seen += 1
            out.append(f"| R{seen} {line}")
        else:
            out.append(line)
    return "".join(out)


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
            TABLE_HEADER_6,
            _table_row(CRIT, "crash on empty input", "src/a.py:3"),
            _table_row(HIGH, "wrong default", "src/b.py:10"),
        )
        rows = [
            _row(CRIT, "src/a.py:3", "crash on empty input"),
            _row(HIGH, "src/b.py:10", "wrong default"),
        ]
        self.assertEqual(_check(text, rows), ("ok", None))

    def _assert_rows_are_the_real_fixture(self, rows: list) -> None:
        """Pins the fixture's own 22 rows: a hardcoded row list cannot pass."""
        sevs = [r.severity for r in rows]
        # The fixture's real severity sequence, in table order: one red row,
        # then five, then eleven, then five, and four distinct severities.
        self.assertEqual([len(list(g)) for _s, g in groupby(sevs)], [1, 5, 11, 5])
        self.assertEqual(len(set(sevs)), 4)
        # The red row keys as a red cell keys anywhere else.
        red, _err = _keys(_table_section(TABLE_HEADER_6, _table_row(CRIT, "x", "y")))
        self.assertEqual(sevs[0], red[0].severity)
        cli = "skills/run-autopilot/cli"
        mid = {
            6: ("fail-first replay", f"{cli}/test_verification.py:235"),
            10: (
                "Rename and copy handling is under-tested",
                f"{cli}/test_verification.py:146",
            ),
            15: ("[MECH] 2 touched test(s)", f"{cli}/test_review_stage.py"),
        }
        for index, (issue, file) in mid.items():
            with self.subTest(row=index + 1):
                self.assertIn(issue, rows[index].issue)
                self.assertEqual(rows[index].file, file)

    def test_cross_check_reads_a_real_saved_review_file(self) -> None:
        rows, err = _keys(REAL_REVIEW.read_text(encoding="utf-8"))
        self.assertIsNone(err)
        self.assertEqual(len(rows), 22)
        # The documented field order: anyone unpacking a Row positionally gets
        # (ref, severity, file, issue), not some other arrangement.
        self.assertEqual(type(rows[0])._fields, ("ref", "severity", "file", "issue"))
        # This real table has no Ref column, so every row's ref is empty.
        self.assertEqual({r.ref for r in rows}, {""})
        # File is column 4 of 6 and has to be found by header name. Row 1's
        # issue cell itself carries escaped pipes, so a naive split would put
        # the wrong cell here.
        self.assertEqual(rows[0].file, "skills/run-autopilot/cli/gate.py:102")
        self.assertIn("only parses the bullet shape", rows[0].issue)
        self.assertEqual(rows[1].file, "dev/bin/release-checks:37")
        self.assertEqual(
            rows[21].file,
            "docs/dev/project-management/prds/done/"
            "00255-triage-resolve-base-is-a-second-diff-base-resol-v1.md",
        )
        self._assert_rows_are_the_real_fixture(rows)

    def test_table_columns_are_located_by_header_name_not_position(self) -> None:
        # File and Issue swapped against the shape this repo emits. A reader
        # that guesses the layout from the column count, or from a fixed
        # position, hands back the Issue cell as the file.
        text = (
            "## Consolidated Findings\n\n"
            "| Consensus | Severity | File | Issue | Task | Found By |\n"
            "|-----------|----------|------|-------|------|----------|\n"
            f"| [2/4] | {HIGH} | src/b.py:10 | wrong default | 3 | ALICE, BOB |\n"
        )
        rows, err = _keys(text)
        self.assertIsNone(err)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].file, "src/b.py:10")
        self.assertEqual(rows[0].issue, "wrong default")
        self.assertEqual(
            _check(text, [_row(HIGH, "src/b.py:10", "wrong default")]),
            ("ok", None),
        )

    def test_cross_check_refuses_the_real_paraphrased_findings_json_without_refs(
        self,
    ) -> None:
        # BY DESIGN. The orchestrator re-worded the issue text and carried no
        # refs, so text matching cannot back these rows - and must not be
        # loosened until they carry refs.
        rows = json.loads(REAL_FINDINGS.read_text(encoding="utf-8"))
        self.assertTrue(all("ref" not in row for row in rows))
        review = REAL_REVIEW.read_text(encoding="utf-8")
        # The refusal has to come from text that genuinely differs, not from a
        # table nothing could read.
        parsed, err = _keys(review)
        self.assertEqual((len(parsed), err), (22, None))
        tag, detail = _check(review, rows)
        self.assertEqual(tag, "mismatch")
        self.assertTrue(detail)

    def test_cross_check_backs_the_same_real_pair_once_refs_are_carried(self) -> None:
        rows = json.loads(REAL_FINDINGS.read_text(encoding="utf-8"))
        self.assertEqual(len(rows), len(REAL_CHOSEN_REVIEW_ROWS))
        chosen = [
            dict(row, ref=f"R{n}")
            for row, n in zip(rows, REAL_CHOSEN_REVIEW_ROWS, strict=True)
        ]
        text = _with_ref_column(REAL_REVIEW.read_text(encoding="utf-8"))
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
        text = _table_section(TABLE_HEADER_6, _table_row(HIGH, reviewed, "src/v.py:1"))
        cases = {
            "unrelated wording": "the gate reuses a record it never measured",
            "a prefix of the reviewed row": "the drain never closes",
            "the reviewed row plus a sentence": f"{reviewed}. Apply the deadline.",
        }
        for label, issue in cases.items():
            with self.subTest(label):
                chosen = [
                    _row(HIGH, "src/v.py:1", reviewed),
                    _row(HIGH, "src/v.py:1", issue),
                ]
                tag, detail = _check(text, chosen)
                self.assertEqual(tag, "mismatch")
                self.assertIn(issue, detail or "")

    def test_cross_check_refuses_an_empty_issue_with_no_ref(self) -> None:
        # An empty issue would otherwise key as a substring of everything.
        text = _table_section(
            TABLE_HEADER_6,
            _table_row(HIGH, "wrong default", "src/b.py:10"),
        )
        for label, issue in {"empty": "", "whitespace only": "   "}.items():
            with self.subTest(label):
                tag, detail = _check(text, [_row(HIGH, "src/b.py:10", issue)])
                self.assertEqual(tag, "mismatch")
                self.assertTrue(detail)
        # Control: the same table does back the row it really holds.
        self.assertEqual(
            _check(text, [_row(HIGH, "src/b.py:10", "wrong default")]),
            ("ok", None),
        )

    def test_a_ref_less_chosen_row_still_matches_exactly_as_before(self) -> None:
        text = _table_section(
            TABLE_HEADER_6,
            _table_row(MED, "unclear name", "src/c.py:20"),
        )
        self.assertEqual(
            _check(text, [_row(MED, "src/c.py:20", "unclear name")]),
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
        # Malformed is exit 1, never the exit 2 of a refusal.
        proc = self._gate(self._review(section=broken_rows), self._findings(chosen))
        self.assertEqual(proc.returncode, 1, proc.stdout)
        self.assertNotIn("unrecognized arguments", proc.stderr)
        # Control, so exit 1 above is not a hardcoded exit code: an unbacked
        # row against a table the gate CAN read is the exit 2 refusal.
        readable = _table_section(
            TABLE_HEADER_6,
            _table_row(HIGH, "wrong default", "src/b.py:10"),
        )
        unbacked = [_row(HIGH, "src/b.py:10", "a finding nobody raised")]
        proc = self._gate(self._review(section=readable), self._findings(unbacked))
        self.assertEqual(proc.returncode, 2, proc.stdout)

    def test_table_row_issue_containing_a_pipe_keys_correctly(self) -> None:
        # Real review rows quote tables, so the issue cell carries bare pipes.
        issue = "the header `| Consensus | Severity |` is read by name"
        text = _table_section(TABLE_HEADER_6, _table_row(HIGH, issue, "src/b.py:10"))
        rows, err = _keys(text)
        self.assertIsNone(err)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].file, "src/b.py:10")
        self.assertEqual(_check(text, [_row(HIGH, "src/b.py:10", issue)]), ("ok", None))

    def test_cross_check_reads_the_five_column_documented_table(self) -> None:
        text = _table_section(
            TABLE_HEADER_5,
            f"| [3/3] | {CRIT} Critical | XSS in input handler | src/input.ts "
            "| Alice, Bob |",
        )
        rows, err = _keys(text)
        self.assertIsNone(err)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].file, "src/input.ts")
        chosen = [_row("critical", "src/input.ts", "XSS in input handler")]
        self.assertEqual(_check(text, chosen), ("ok", None))
        # A Severity cell spelled as the bare English word, no emoji at all:
        # reading only the cell's first character would key it as nothing and
        # refuse the row.
        worded = _table_section(
            TABLE_HEADER_5,
            "| [3/3] | High | wrong default | src/b.py:10 | Alice, Bob |",
        )
        by_word, word_err = _keys(worded)
        self.assertIsNone(word_err)
        self.assertEqual(len(by_word), 1)
        self.assertEqual(by_word[0].severity, "high")
        emoji_text = _table_section(
            TABLE_HEADER_6,
            _table_row(HIGH, "wrong default", "src/b.py:10"),
        )
        by_emoji, _emoji_err = _keys(emoji_text)
        self.assertEqual(by_word[0].severity, by_emoji[0].severity)
        self.assertEqual(
            _check(worded, [_row(HIGH, "src/b.py:10", "wrong default")]),
            ("ok", None),
        )

    def test_table_and_bullet_rows_key_identically(self) -> None:
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
        chosen = [_row(HIGH, "src/b.py:10", "wrong default")]
        self.assertEqual(_check(bullet, chosen), ("ok", None))
        self.assertEqual(_check(table, chosen), ("ok", None))
        # So a chosen row naming R1 is not backed by either review: nothing in
        # them holds that ref, however well the text lines up.
        for label, text in {"bullet": bullet, "table": table}.items():
            with self.subTest(label):
                tag, detail = _check(text, [dict(chosen[0], ref="R1")])
                self.assertEqual(tag, "mismatch")
                self.assertIn("R1", detail or "")

    def test_escaped_pipe_in_a_table_cell_keys_like_an_unescaped_one(self) -> None:
        # Normalization applies to BOTH sides, so a verbatim-copied escaped row
        # and a hand-unescaped one key the same.
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
                    TABLE_HEADER_6,
                    _table_row(HIGH, cell, "src/b.py:10"),
                )
                chosen = [_row(HIGH, "src/b.py:10", value)]
                self.assertEqual(_check(text, chosen), ("ok", None))

    def test_table_row_absent_from_the_findings_json_is_still_not_a_mismatch(
        self,
    ) -> None:
        text = _table_section(
            TABLE_HEADER_6,
            _table_row(CRIT, "crash on empty input", "src/a.py:3"),
            _table_row(HIGH, "wrong default", "src/b.py:10"),
            _table_row(MED, "unclear name", "src/c.py:20"),
        )
        chosen = [_row(HIGH, "src/b.py:10", "wrong default")]
        self.assertEqual(_check(text, chosen), ("ok", None))


if __name__ == "__main__":
    unittest.main()
