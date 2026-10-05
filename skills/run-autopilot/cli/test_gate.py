#!/usr/bin/env python3
"""Tests for `autopilot gate` (PRD 00107 Phase 0).

Binds the CLI wiring and the two entry points, not the full check matrix —
that stays in review-work-completion/scripts/test_check_review_file.py,
which now exercises the same code through the re-export shim and must keep
passing unmodified (the parity proof for the move).
"""

from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path
from uuid import uuid4

CLI_DIR = Path(__file__).resolve().parent
CLI_MAIN = CLI_DIR / "__main__.py"
GATE_SCRIPT = CLI_DIR / "gate.py"
SHIM = (
    CLI_DIR.parents[1] / "review-work-completion" / "scripts" / "check_review_file.py"
)

GOOD_FILE = """---
reviewers: alice,blake,bob
---

codex_rung_guard: not fired

## Alice

- finding one

## Blake

No spec drift found.

## Bob

D1: pass

Verdict: converged
Tests: 12 passed, 0 failed
"""

DOCS_ONLY_FILE = """---
reviewers: alice
---

## Alice

docs read clean

Verdict: converged
Tests: none (docs-only)
"""

CONSTRAINT_UNMET_FILE = """---
reviewers: alice
---

codex_rung_guard: fired (2 codex-implemented task(s)); constraint UNMET

## Alice

- ok

Verdict: converged
Tests: 3 passed, 0 failed
"""

CRIT = "\U0001f534"
HIGH = "\U0001f7e0"
MED = "\U0001f7e1"

# The SAVED review artifact: the Review Summary Format's bullet list, which is
# what `gate --review-file` reads.
FINDINGS_SECTION = f"""## Consolidated Findings

### Full Consensus (3/3)

- [3/3] {CRIT} crash on empty input | src/a.py:3 | Found by: alice, blake, bob

### Majority Consensus (>50%)

- [2/3] {HIGH} wrong default | src/b.py:10 | Found by: alice, bob

### Minority (<=50%)

- [1/3] {MED} unclear name | src/c.py:20 | Found by: bob
"""

EMPTY_FINDINGS_SECTION = """## Consolidated Findings

### Full Consensus (3/3)

### Majority Consensus (>50%)

### Minority (<=50%)
"""


def _run(entry: list[str], args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, *entry, *args],
        capture_output=True,
        text=True,
    )


def _row(sev: str, file: str, issue: str, cls: str = "fix") -> dict:
    return {"classification": cls, "severity": sev, "file": file, "issue": issue}


def _one_row_section(sev: str, issue: str, file: str) -> str:
    """A consolidated-findings section holding exactly one finding line."""
    return (
        "## Consolidated Findings\n\n"
        "### Full Consensus (2/2)\n\n"
        f"- [2/2] {sev} {issue} | {file} | Found by: alice, bob\n"
    )


class GateSubcommandTests(unittest.TestCase):
    """`autopilot gate` via cli/__main__.py."""

    def _write(self, tmp_name: str, text: str) -> Path:
        import tempfile

        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        path = Path(tmp.name) / tmp_name
        path.write_text(text, encoding="utf-8")
        return path

    def test_well_formed_file_passes(self) -> None:
        path = self._write("prd-review-1.md", GOOD_FILE)
        proc = _run([str(CLI_MAIN)], ["gate", "--review-file", str(path)])
        self.assertEqual(proc.returncode, 0, proc.stderr)

    def test_docs_only_sentinel_passes(self) -> None:
        path = self._write("prd-review-1.md", DOCS_ONLY_FILE)
        proc = _run([str(CLI_MAIN)], ["gate", "--review-file", str(path)])
        self.assertEqual(proc.returncode, 0, proc.stderr)

    def test_tests_line_admits_the_provenance_suffix(self) -> None:
        # PRD 00164: step 6 names which path produced the counts, as a suffix
        # on the Tests: line. The gate is what that suffix has to survive - a
        # reused count that fails the gate would push the review straight back
        # to re-running the suite it just avoided.
        text = GOOD_FILE.replace(
            "Tests: 12 passed, 0 failed",
            "Tests: 12 passed, 0 failed, 0 skipped "
            "(reused from last-verification.json at 292418f)",
        )
        path = self._write("prd-review-1.md", text)
        proc = _run([str(CLI_MAIN)], ["gate", "--review-file", str(path)])
        self.assertEqual(proc.returncode, 0, proc.stderr)

    def test_docs_only_sentinel_takes_no_suffix(self) -> None:
        # The other half of the same rule, and the reason step 6 states it: the
        # counts branch of TESTS_RE ends in `.*`, the docs-only branch does not.
        # Suffixing the sentinel silently fails the gate.
        text = DOCS_ONLY_FILE.replace(
            "Tests: none (docs-only)",
            "Tests: none (docs-only) (suite run this cycle)",
        )
        path = self._write("prd-review-1.md", text)
        proc = _run([str(CLI_MAIN)], ["gate", "--review-file", str(path)])
        self.assertEqual(proc.returncode, 1)
        self.assertIn("tests line", proc.stderr.lower())

    def test_shape_gap_blocks_with_reason(self) -> None:
        path = self._write("prd-review-1.md", "## Alice\n\nhm\n")
        proc = _run(
            [str(CLI_MAIN)],
            ["gate", "--review-file", str(path), "--reviewers", "alice"],
        )
        self.assertEqual(proc.returncode, 1)
        self.assertIn("verdict", proc.stderr.lower())

    def test_missing_reviewer_section_names_the_reviewer(self) -> None:
        path = self._write("prd-review-1.md", GOOD_FILE)
        proc = _run(
            [str(CLI_MAIN)],
            ["gate", "--review-file", str(path), "--reviewers", "alice,carl"],
        )
        self.assertEqual(proc.returncode, 1)
        self.assertIn("carl", proc.stderr)

    def test_missing_file_exits_1(self) -> None:
        proc = _run(
            [str(CLI_MAIN)],
            ["gate", "--review-file", "/nonexistent/rev.md"],
        )
        self.assertEqual(proc.returncode, 1)
        self.assertIn("missing review file", proc.stderr)

    def test_constraint_unmet_exits_2_only_under_the_flag(self) -> None:
        path = self._write("prd-review-1.md", CONSTRAINT_UNMET_FILE)
        without = _run(
            [str(CLI_MAIN)],
            ["gate", "--review-file", str(path), "--require-codex-guard"],
        )
        self.assertEqual(without.returncode, 0, without.stderr)
        with_flag = _run(
            [str(CLI_MAIN)],
            [
                "gate",
                "--review-file",
                str(path),
                "--require-codex-guard",
                "--assert-constraint-met",
            ],
        )
        self.assertEqual(with_flag.returncode, 2)
        self.assertIn("constraint UNMET", with_flag.stderr)

    def test_plain_fired_without_eve_section_blocks(self) -> None:
        text = CONSTRAINT_UNMET_FILE.replace("; constraint UNMET", "")
        path = self._write("prd-review-1.md", text)
        proc = _run(
            [str(CLI_MAIN)],
            ["gate", "--review-file", str(path), "--require-codex-guard"],
        )
        self.assertEqual(proc.returncode, 1)
        self.assertIn("eve", proc.stderr.lower())


class DirectScriptTests(unittest.TestCase):
    """cli/gate.py must stay standalone-runnable: review_coverage_hook.py
    shells to it by path, outside the `autopilot` dispatcher."""

    def test_direct_invocation_matches_subcommand(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "prd-review-1.md"
            path.write_text(GOOD_FILE, encoding="utf-8")
            direct = _run([str(GATE_SCRIPT)], ["--review-file", str(path)])
            self.assertEqual(direct.returncode, 0, direct.stderr)

    def test_direct_invocation_cross_checks_findings(self) -> None:
        """The by-path entry point must honour --findings too: accepting the
        flag and discarding it would leave review_coverage_hook.py blind."""
        import tempfile

        bogus = f"issue nobody raised {uuid4().hex}"
        with tempfile.TemporaryDirectory() as tmp:
            review = Path(tmp) / "prd-review-1.md"
            review.write_text(
                GOOD_FILE.replace(
                    "Verdict: converged",
                    f"{FINDINGS_SECTION}\nVerdict: converged",
                ),
                encoding="utf-8",
            )
            matching = Path(tmp) / "good.json"
            matching.write_text(
                json.dumps([_row(HIGH, "src/b.py:10", "wrong default")]),
                encoding="utf-8",
            )
            mismatching = Path(tmp) / "bad.json"
            mismatching.write_text(
                json.dumps([_row(HIGH, "src/b.py:10", bogus)]),
                encoding="utf-8",
            )
            ok = _run(
                [str(GATE_SCRIPT)],
                ["--review-file", str(review), "--findings", str(matching)],
            )
            self.assertEqual(ok.returncode, 0, ok.stderr)
            bad = _run(
                [str(GATE_SCRIPT)],
                ["--review-file", str(review), "--findings", str(mismatching)],
            )
            self.assertEqual(bad.returncode, 2, bad.stdout)
            self.assertIn(bogus, bad.stderr)


class ShimParityTests(unittest.TestCase):
    def test_shim_objects_are_the_cli_gate_objects(self) -> None:
        """The shim re-exports, never copies: its `check` must BE cli.gate's."""
        import importlib.util

        sys.path.insert(0, str(CLI_DIR.parent))
        try:
            from cli import gate as cli_gate

            spec = importlib.util.spec_from_file_location("check_review_file", SHIM)
            assert spec is not None and spec.loader is not None
            shim = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(shim)
        finally:
            sys.path.remove(str(CLI_DIR.parent))
        self.assertIs(shim.check, cli_gate.check)
        self.assertIs(shim.run_gate, cli_gate.run_gate)
        self.assertIs(shim.FRONTMATTER_REVIEWERS_RE, cli_gate.FRONTMATTER_REVIEWERS_RE)


class FindingsCrossCheckTests(unittest.TestCase):
    """`gate --findings` cross-checks a chosen-findings JSON array against the
    review file's consolidated-findings bullet list.

    One direction only: every findings row must match a review row; the review
    may carry rows the batch is not applying.
    """

    def setUp(self) -> None:
        import tempfile

        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(tmp.name)

    def _review(self, section: str = FINDINGS_SECTION) -> Path:
        body = GOOD_FILE
        if section:
            body = body.replace("Verdict: converged", f"{section}\nVerdict: converged")
        path = self.tmp / "prd-review-1.md"
        path.write_text(body, encoding="utf-8")
        return path

    def _raw_review(self, body: str) -> Path:
        path = self.tmp / "prd-review-1.md"
        path.write_text(body, encoding="utf-8")
        return path

    def _findings(self, rows: list[dict]) -> Path:
        path = self.tmp / "findings.json"
        path.write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")
        return path

    def _gate(self, review: Path, findings: Path) -> subprocess.CompletedProcess:
        return _run(
            [str(CLI_MAIN)],
            ["gate", "--review-file", str(review), "--findings", str(findings)],
        )

    def test_gate_accepts_matching_findings_json(self) -> None:
        # Severity spelled as emoji on two rows and as the English word on the
        # third; issue text and file carry stray whitespace. All normalize.
        findings = self._findings(
            [
                {
                    "classification": "fix",
                    "severity": CRIT,
                    "file": "src/a.py:3",
                    "issue": "crash on empty input",
                },
                {
                    "classification": "fix",
                    "severity": "high",
                    "file": "src/b.py:10",
                    "issue": "wrong   default",
                },
                {
                    "classification": "defer",
                    "severity": MED,
                    "file": " src/c.py:20 ",
                    "issue": "unclear name",
                },
            ],
        )
        proc = self._gate(self._review(), findings)
        self.assertEqual(proc.returncode, 0, proc.stderr)

    def test_gate_refuses_findings_json_mismatch(self) -> None:
        findings = self._findings(
            [
                {
                    "classification": "fix",
                    "severity": CRIT,
                    "file": "src/a.py:3",
                    "issue": "crash on empty input",
                },
                # Same file as a real review row, invented issue text: an
                # implementation comparing file paths alone would pass this.
                {
                    "classification": "fix",
                    "severity": HIGH,
                    "file": "src/b.py:10",
                    "issue": "issue nobody reviewed",
                },
                {
                    "classification": "fix",
                    "severity": MED,
                    "file": "src/z.py:1",
                    "issue": "second invented issue",
                },
            ],
        )
        proc = self._gate(self._review(), findings)
        self.assertEqual(proc.returncode, 2, proc.stdout)
        self.assertIn("issue nobody reviewed", proc.stderr)
        # Only the FIRST mismatched row is named.
        self.assertNotIn("second invented issue", proc.stderr)

    def test_gate_refuses_severity_only_mismatch(self) -> None:
        # File and issue match a real review row; the severity does not. The
        # comparison tuple includes severity, so this is a mismatch.
        findings = self._findings(
            [
                {
                    "classification": "fix",
                    "severity": "critical",
                    "file": "src/b.py:10",
                    "issue": "wrong default",
                },
            ],
        )
        proc = self._gate(self._review(), findings)
        self.assertEqual(proc.returncode, 2, proc.stdout)
        self.assertIn("wrong default", proc.stderr)

    def test_gate_refuses_file_only_mismatch(self) -> None:
        # Severity and issue match a real review row; the file does not. The
        # comparison tuple includes the file, so this is a mismatch.
        findings = self._findings([_row(HIGH, "src/elsewhere.py:10", "wrong default")])
        proc = self._gate(self._review(), findings)
        self.assertEqual(proc.returncode, 2, proc.stdout)
        self.assertIn("src/elsewhere.py:10", proc.stderr)

    def test_gate_refuses_a_deferred_row_the_review_never_recorded(self) -> None:
        # A `defer` row is applied to state as a deferred decision, so it has
        # to cross-check like any other: the classification is not a bypass.
        bogus = f"deferred issue nobody raised {uuid4().hex}"
        findings = self._findings([_row(MED, "src/c.py:20", bogus, "defer")])
        proc = self._gate(self._review(), findings)
        self.assertEqual(proc.returncode, 2, proc.stdout)
        self.assertIn(bogus, proc.stderr)

    def test_gate_accepts_a_review_row_invented_at_runtime(self) -> None:
        # The issue text exists nowhere but this run, so the only way to match
        # it is to parse the review file.
        issue = f"freshly minted finding {uuid4().hex}"
        findings = self._findings([_row(HIGH, "src/new.py:7", issue)])
        proc = self._gate(
            self._review(section=_one_row_section(HIGH, issue, "src/new.py:7")),
            findings,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)

    def test_gate_refuses_a_runtime_row_absent_from_the_review(self) -> None:
        # The inverse of the test above: same findings row, a review that
        # records a different finding at the same file.
        issue = f"freshly minted finding {uuid4().hex}"
        findings = self._findings([_row(HIGH, "src/new.py:7", issue)])
        other = _one_row_section(HIGH, "something else entirely", "src/new.py:7")
        proc = self._gate(self._review(section=other), findings)
        self.assertEqual(proc.returncode, 2, proc.stdout)
        self.assertIn(issue, proc.stderr)

    def test_partial_batch_is_not_a_mismatch(self) -> None:
        # A real subset of the review's rows. The two rows findings never
        # mentions must not count against it.
        findings = self._findings(
            [
                {
                    "classification": "fix",
                    "severity": HIGH,
                    "file": "src/b.py:10",
                    "issue": "wrong default",
                },
            ],
        )
        proc = self._gate(self._review(), findings)
        self.assertEqual(proc.returncode, 0, proc.stderr)

    def test_malformed_findings_section_exits_1_not_2(self) -> None:
        # GOOD_FILE has no `## Consolidated Findings` heading at all.
        findings = self._findings(
            [
                {
                    "classification": "fix",
                    "severity": HIGH,
                    "file": "src/b.py:10",
                    "issue": "wrong default",
                },
            ],
        )
        proc = self._gate(self._review(section=""), findings)
        self.assertEqual(proc.returncode, 1, proc.stdout)
        # The 1 must come from check()'s gap path, not from argparse rejecting
        # an unknown flag - which also exits 1 here.
        self.assertNotIn("unrecognized arguments", proc.stderr)

    def test_shape_gap_outranks_a_findings_mismatch(self) -> None:
        # A review that is both shape-broken (no Verdict: line) and carrying a
        # mismatching batch exits 1 for the shape gap, not 2: the operator has
        # to fix the file before the findings question means anything.
        body = GOOD_FILE.replace("Verdict: converged\n", f"{FINDINGS_SECTION}\n")
        findings = self._findings([_row(HIGH, "src/b.py:10", "unreviewed issue")])
        proc = self._gate(self._raw_review(body), findings)
        self.assertEqual(proc.returncode, 1, proc.stdout)
        self.assertIn("verdict", proc.stderr.lower())

    def test_empty_findings_against_a_missing_section_is_malformed(self) -> None:
        # An empty batch is not a licence to skip the section check: a review
        # with no consolidated findings at all stays malformed.
        from cli import gate

        tag, detail = gate._cross_check_findings(GOOD_FILE, [])
        self.assertEqual(tag, "malformed")
        self.assertTrue(detail)

    def test_bad_findings_file_fails_cleanly_without_a_traceback(self) -> None:
        review = self._review()
        cases = {
            "missing file": None,
            "not json at all": "{not json",
            "a json object, not an array": '{"severity": "high"}',
        }
        for label, body in cases.items():
            with self.subTest(label):
                path = self.tmp / "bad-findings.json"
                if body is None:
                    path.unlink(missing_ok=True)
                else:
                    path.write_text(body, encoding="utf-8")
                proc = self._gate(review, path)
                self.assertNotEqual(proc.returncode, 0, proc.stdout)
                self.assertNotIn("Traceback", proc.stderr)
                self.assertTrue(proc.stderr.strip(), proc.stdout)
                # Against an older CLI that doesn't understand --findings at
                # all, argparse would reject the flag itself and trivially
                # satisfy the three assertions above without the findings-
                # file diagnostic ever running. Rule that false-pass out.
                self.assertNotIn("unrecognized arguments", proc.stderr)
                self.assertIn("findings file", proc.stderr)

    def test_empty_findings_is_not_malformed(self) -> None:
        proc = self._gate(
            self._review(section=EMPTY_FINDINGS_SECTION),
            self._findings([]),
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)

    def test_cross_check_normalizes_combined_severity_cell(self) -> None:
        """A review row written `🟠 High` equals a findings row written `high`."""
        from cli import gate

        text = (
            "## Consolidated Findings\n\n"
            "### Majority Consensus (>50%)\n\n"
            f"- [2/3] {HIGH} High wrong default | src/b.py:10 | "
            "Found by: alice, bob\n"
        )
        row = {
            "classification": "fix",
            "severity": "high",
            "file": "src/b.py:10",
            "issue": "wrong default",
        }
        self.assertEqual(gate._cross_check_findings(text, [row]), ("ok", None))

    def test_cross_check_matches_an_issue_starting_with_a_severity_word(self) -> None:
        """`High coupling ...` is ordinary issue text, not a severity cell: both
        sides must treat that leading word the same or a valid batch is refused."""
        from cli import gate

        issue = "High coupling between the gate and the closer"
        text = _one_row_section(HIGH, issue, "src/b.py:10")
        row = _row(HIGH, "src/b.py:10", issue)
        self.assertEqual(gate._cross_check_findings(text, [row]), ("ok", None))

    def test_gate_refuses_an_unbacked_row_carrying_no_classification(self) -> None:
        # Only `verify` and `discard` are exempt. A row with no classification
        # key at all is not exempt - the by-path gate has no other validator,
        # so skipping it would let a fabricated row through.
        bogus = f"unclassified issue nobody raised {uuid4().hex}"
        findings = self._findings(
            [{"severity": HIGH, "file": "src/b.py:10", "issue": bogus}],
        )
        proc = self._gate(self._review(), findings)
        self.assertEqual(proc.returncode, 2, proc.stdout)
        self.assertIn(bogus, proc.stderr)

    def test_cross_check_reports_the_missing_section_as_malformed(self) -> None:
        from cli import gate

        tag, detail = gate._cross_check_findings(
            GOOD_FILE,
            [
                {
                    "classification": "fix",
                    "severity": HIGH,
                    "file": "src/b.py:10",
                    "issue": "wrong default",
                },
            ],
        )
        self.assertEqual(tag, "malformed")
        self.assertTrue(detail)


if __name__ == "__main__":
    unittest.main()
