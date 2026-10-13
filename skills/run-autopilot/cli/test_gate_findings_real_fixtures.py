#!/usr/bin/env python3
"""The real-saved-artifact half of the `gate --findings` cross-check.

Split out of test_gate_findings_table.py to keep every file under the 800-line
limit (rules/coding-style.md). The synthetic pipe-table fixtures, the Ref-cell
shape tests and the shared `_table_section` / `_keys` helpers stay there; this
file holds the tests fed the saved review file and findings JSON of PRD 00256
review cycle 1, plus the prose checks on the skill text documenting that rule.
"""

from __future__ import annotations

import json
import sys
import unittest
from itertools import groupby
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from cli.test_gate import CLI_DIR, CRIT

# Imported, never re-spelled: both halves of the split have to read a review
# file through the same helpers and the same parser entry point.
from cli.test_gate_findings_table import (
    TABLE_HEADER_6,
    _check,
    _keys,
    _table_row,
    _table_section,
)

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


class RealSavedReviewFixtureTests(unittest.TestCase):
    """The cross-check fed the artifacts a real review cycle left behind."""

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

    def test_cross_check_refuses_the_real_paraphrased_findings_json_without_refs(
        self,
    ) -> None:
        # BY DESIGN. The orchestrator re-worded the issue text and carried no
        # refs, so text matching cannot back these rows - and must not be
        # loosened until they carry refs.
        rows = json.loads(REAL_FINDINGS.read_text(encoding="utf-8"))
        self.assertTrue(all("ref" not in row for row in rows))
        # The saved table carries no Ref column, which is its own refusal now
        # (`ref-required`), so the Ref-ful copy is what isolates the paraphrase.
        review = _with_ref_column(REAL_REVIEW.read_text(encoding="utf-8"))
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
        # Rows 1, 17, 21 and 22 are deliberately not chosen for a fix; every
        # review row still needs a disposition, so each gets a discard row.
        not_chosen = set(range(1, 23)) - set(REAL_CHOSEN_REVIEW_ROWS)
        chosen += [{"ref": f"R{n}", "classification": "discard"} for n in not_chosen]
        text = _with_ref_column(REAL_REVIEW.read_text(encoding="utf-8"))
        self.assertEqual(_check(text, chosen), ("ok", None))


# PRD 00264's third checkbox: the decision-gate prose in phase-review.md and
# the findings-JSON step of review-work-completion's SKILL.md both have to
# tell a human operator the same rule test_gate_findings_table.py pins
# mechanically - every consolidated row needs one findings-JSON row naming its
# `ref` and a `classification`, `discard` included.
_SKILLS_DIR = CLI_DIR.parents[1]
_PHASE_REVIEW = _SKILLS_DIR / "run-autopilot" / "references" / "phase-review.md"
_REVIEW_SKILL = _SKILLS_DIR / "review-work-completion" / "SKILL.md"
_COVERAGE_SENTENCE = (
    "every consolidated row gets one JSON row with its `ref` and a "
    "`classification`, `discard` included"
)


_CARRY_PHRASE = (
    "so give it a `chosen_findings` entry too, with `classification` set to `carry`"
)
_TAIL_SWEEP_EXEMPT_PHRASE = (
    "The tail-sweep step's findings JSON is exempt from this coverage check"
)


# PRD 00277: every saved review file carrying a findings section, replayed
# through the gate with a findings JSON that classifies each of its rows `fix`.
# The baseline holds the verdict tag each one got before the gate widened what
# it refuses; a file whose tag flips is named here, never fixed by editing it.
_REPO_ROOT = CLI_DIR.parents[2]
_BASELINE_PATH = FIXTURES / "gate_replay_baseline.json"
# PRD 00282 task D1 (#11): `_is_unread_line` widened to flag a bullet- or
# ordinal-led line carrying a bare severity emoji anywhere on it (a reviewer's
# free-text finding note or discard rationale, with no pipe, word or token to
# back it). Every one of these real review files carries such a line outside
# the one structured findings table - a follow-up task list, a discard note,
# an availability summary mentioning a count - and now correctly refuses.
_ACCEPTED_FLIPS: dict[str, str] = {
    "docs/dev/project-management/reviews/00171-route-sonnet-prompt-through-stdin-v1-review-1.md": "malformed",
    "docs/dev/project-management/reviews/00187-keep-cap-out-criticals-off-master-and-home-deferred-highs-v1-review-2.md": "malformed",
    "docs/dev/project-management/reviews/00188-record-convergence-cap-and-roster-per-prd-v1-review-2.md": "malformed",
    "docs/dev/project-management/reviews/00189-stall-to-split-on-plan-expansion-v1-review-2.md": "malformed",
    "docs/dev/project-management/reviews/00192-split-loop-py-and-its-tests-under-the-cap-v1-review-1.md": "malformed",
    "docs/dev/project-management/reviews/00207-route-rework-resume-sessions-on-task-tier-v1-review-01.md": "malformed",
    "docs/dev/project-management/reviews/00208-hand-off-between-the-rework-design-and-the-first-fix-v1-review-01.md": "malformed",
    "docs/dev/project-management/reviews/00218-leave-sessions-at-task-boundaries-and-run-one-devon-round-v1-review-2.md": "malformed",
    "docs/dev/project-management/reviews/00223-enter-the-build-gate-in-one-cli-call-v1-review-2.md": "malformed",
    "docs/dev/project-management/reviews/00232-keep-subagent-test-runs-narrow-v1-review-1.md": "malformed",
    "docs/dev/project-management/reviews/00244-tidy-the-enter-verb-and-the-review-diff-plumbing-v1-review-1.md": "malformed",
    "docs/dev/project-management/reviews/00256-finish-the-review-verbs-before-release-v1-review-1.md": "malformed",
    "docs/dev/project-management/reviews/00256-finish-the-review-verbs-before-release-v1-review-2.md": "malformed",
    "docs/dev/project-management/reviews/00265-close-the-critical-row-escapes-v1-review-2.md": "malformed",
    "docs/dev/project-management/reviews/00267-widen-the-phase-delegation-guard-v1-review-1.md": "malformed",
    "docs/dev/project-management/reviews/00271-guard-v2-structural-delegation-check-v1-review-2.md": "malformed",
    "docs/dev/project-management/reviews/00276-make-the-gate-record-trustworthy-v1-review-2.md": "malformed",
}


def _replay_verdict(path: Path) -> dict:
    """The gate's tag for `path` under one `fix` row per consolidated row it
    reads: a ref-bearing row is named by its ref, a ref-less one by its text,
    and coverage is required only when some row carries a ref."""
    from cli import gate

    text = path.read_text(encoding="utf-8")
    rows, _problem = _keys(gate._unfenced(text))
    findings = []
    for row in rows:
        finding = {
            "classification": "fix",
            "severity": row.severity,
            "file": row.file,
            "issue": row.issue,
        }
        findings.append({"ref": row.ref, **finding} if row.ref else finding)
    coverage = any(row.ref for row in rows)
    tag, _detail = gate.findings_verdict(text, findings, require_coverage=coverage)
    return {"tag": tag, "coverage": coverage}


class ReplayBaselineTests(unittest.TestCase):
    def test_real_review_files_keep_their_baseline_verdict(self) -> None:
        baseline = json.loads(_BASELINE_PATH.read_text(encoding="utf-8"))
        self.assertTrue(baseline)
        for relpath, recorded in baseline.items():
            with self.subTest(relpath):
                current = _replay_verdict(_REPO_ROOT / relpath)
                self.assertEqual(current["coverage"], recorded["coverage"])
                expected = _ACCEPTED_FLIPS.get(relpath, recorded["tag"])
                self.assertEqual(current["tag"], expected)


class FindingsJsonCoverageProseTests(unittest.TestCase):
    def test_findings_json_covers_every_row_prose(self) -> None:
        for path in (_PHASE_REVIEW, _REVIEW_SKILL):
            with self.subTest(path.name):
                text = path.read_text(encoding="utf-8")
                self.assertIn(
                    _COVERAGE_SENTENCE,
                    text,
                    f"{path}: expected the sentence {_COVERAGE_SENTENCE!r} - not found.",
                )

    def test_requeued_rows_are_classified_carry_prose(self) -> None:
        text = _PHASE_REVIEW.read_text(encoding="utf-8")
        self.assertIn(_CARRY_PHRASE, text)

    def test_tail_sweep_is_exempt_from_coverage_prose(self) -> None:
        text = _PHASE_REVIEW.read_text(encoding="utf-8")
        self.assertIn(_TAIL_SWEEP_EXEMPT_PHRASE, text)


if __name__ == "__main__":
    unittest.main()
