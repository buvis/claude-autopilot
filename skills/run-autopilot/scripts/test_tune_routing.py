"""Tests for tune_routing.py (PRD 00170).

Binds: S1 mechanical-row escalation rate against the MIN_ROWS/
S1_ESCALATION_RATE floors, and that a PROPOSE emits a `git apply`-able patch;
S2 repair-budget completion rate; S3 codex-rung failure rate (either the
no-edit share or the next-attempt escalation share); that contract/
algorithmic_risk/floor rows never move S1-S3 (opus and operator floors are
out of tuning scope) yet still count in the report table; ledger dedupe on
`(batch_id, prd, task_id, attempt.attempt)`; per-field UNPARSED reasons for a
malformed row, with the rest of the ledger still counted; an UNPARSED
classifier literal when the constant line is absent; run-to-run determinism
of the proposal and patch files; and the Phase 1 acceptance exits (an
unreadable ledger, and an all-UNPARSED ledger) writing nothing.

Stdlib unittest (pytest collects it). Fixture rows are built with `_row`, one
full ledger row per the shape documented in state-schema.md § Attempt
ledger. Fixture-driven end-to-end cases drive the CLI via subprocess; cases
where a unit assertion is clearer call `signals`/`render`/`parse_rows`/
`load_rows` directly on a module loaded via `importlib.util` (same pattern as
`test_codex_review_run.py`).
"""

import importlib.util
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).parent / "tune_routing.py"

_spec = importlib.util.spec_from_file_location("tune_routing", SCRIPT)
tr = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(tr)

CLASSIFIER_FIXTURE = (
    "#!/usr/bin/env python3\n"
    "_MECHANICAL_MAX_FILES = 2\n"
    "_MECHANICAL_MAX_LINES = 50\n"
    "PHRASES = ()\n"
)

CLASSIFIER_NO_LITERAL = (
    "#!/usr/bin/env python3\n"
    "_MECHANICAL_MAX_FILES = 2\n"
    "PHRASES = ()\n"
)


def _row(prd: str, task_id: str, attempt_no: int, outcome: str,
         tier_reason: str | None = None, **attempt_fields) -> dict:
    """One full ledger row, per state-schema.md § Attempt ledger."""
    attempt = {"attempt": attempt_no, "model": "sonnet", "outcome": outcome}
    attempt.update(attempt_fields)
    return {
        "batch_id": "202609040001",
        "prd": prd,
        "task_id": task_id,
        "task_name": task_id,
        "task_model": "sonnet",
        "qwen_eligible": True,
        "task_tier_reason": tier_reason,
        "task_qwen_excluded_reason": None,
        "recorded_at": "2026-09-04T10:00:00Z",
        "attempt": attempt,
    }


def _write_ledger(path: Path, rows: list) -> None:
    path.write_text(
        "\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8"
    )


def _write_classifier(tmp_path: Path, text: str = CLASSIFIER_FIXTURE) -> Path:
    classifier_dir = tmp_path / "skills" / "plan-tasks" / "scripts"
    classifier_dir.mkdir(parents=True, exist_ok=True)
    classifier = classifier_dir / "classify_tier.py"
    classifier.write_text(text, encoding="utf-8")
    return classifier


def _sources_stub(rows: list) -> dict:
    return {
        "ledger": "test-ledger.jsonl",
        "rows": len(rows),
        "deduped_rows": len(rows),
        "prds": sorted({r["prd"] for r in rows}),
        "recorded_at_min": None,
        "recorded_at_max": None,
        "unparsed": 0,
        "audit_qwen": None,
    }


def _run_cli(ledger: Path, out_dir: Path, date: str,
             classifier: Path | None = None) -> subprocess.CompletedProcess:
    args = ["python3", str(SCRIPT), "--ledger", str(ledger),
            "--out-dir", str(out_dir), "--date", date]
    if classifier is not None:
        args += ["--classifier", str(classifier)]
    return subprocess.run(args, capture_output=True, text=True)


class TuneRoutingTest(unittest.TestCase):
    def test_s1_escalation_at_floor_proposes_and_patch_applies(self) -> None:
        """S1: n=12 mechanical first attempts, rate=7/12 >= 0.5 -> PROPOSE,
        with a `.patch` that `git apply --check` accepts and whose only
        changed lines halve _MECHANICAL_MAX_LINES."""
        prd = "00001-example.md"
        rows = [
            _row(prd, f"task-{i}", 1, "escalated" if i < 7 else "completed",
                 tier_reason="mechanical")
            for i in range(12)
        ]
        rows += [
            _row(prd, f"task-{i}", 2, "completed", tier_reason="mechanical",
                 escalated_from="haiku")
            for i in range(7)
        ]
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            ledger = tmp_path / "attempts.jsonl"
            _write_ledger(ledger, rows)
            classifier = _write_classifier(tmp_path)
            out_dir = tmp_path / "out"
            result = _run_cli(ledger, out_dir, "2026-01-01", classifier)
            self.assertEqual(result.returncode, 0, result.stderr)

            md = (out_dir / "routing-proposal-2026-01-01.md").read_text()
            self.assertIn("## S1 mechanical row", md)
            self.assertIn("- PROPOSE: n=12", md)
            patch_path = out_dir / "routing-proposal-2026-01-01.patch"
            self.assertTrue(patch_path.exists())

            check = subprocess.run(
                ["git", "apply", "--check", str(patch_path)],
                cwd=tmp_path, capture_output=True, text=True,
            )
            self.assertEqual(check.returncode, 0, check.stderr)

            changed = [
                line for line in patch_path.read_text().splitlines()
                if line.startswith(("+", "-"))
                and not line.startswith(("+++", "---"))
            ]
            self.assertEqual(
                changed,
                ["-_MECHANICAL_MAX_LINES = 50", "+_MECHANICAL_MAX_LINES = 25"],
            )

    def test_s1_below_floor_holds_with_needed_count(self) -> None:
        """S1: n=11 < MIN_ROWS -> HOLD naming `needed: 1 more rows`, no patch."""
        prd = "00001-example.md"
        rows = [
            _row(prd, f"task-{i}", 1, "escalated" if i < 6 else "completed",
                 tier_reason="mechanical")
            for i in range(11)
        ]
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            ledger = tmp_path / "attempts.jsonl"
            _write_ledger(ledger, rows)
            classifier = _write_classifier(tmp_path)
            out_dir = tmp_path / "out"
            result = _run_cli(ledger, out_dir, "2026-01-01", classifier)
            self.assertEqual(result.returncode, 0, result.stderr)

            md = (out_dir / "routing-proposal-2026-01-01.md").read_text()
            self.assertIn("## S1 mechanical row", md)
            self.assertIn("- HOLD: n=11", md)
            self.assertIn("needed: 1 more rows", md)
            self.assertFalse(
                (out_dir / "routing-proposal-2026-01-01.patch").exists()
            )

    def test_s1_at_floor_with_low_rate_holds_on_rate_not_on_count(self) -> None:
        """S1: n=12 but rate=5/12 < 0.5 -> HOLD that names the rate floor,
        never `needed: 0 more rows`."""
        prd = "00001-example.md"
        rows = [
            _row(prd, f"task-{i}", 1, "escalated" if i < 5 else "completed",
                 tier_reason="mechanical")
            for i in range(12)
        ]
        sig = tr.signals(rows)
        md, patch = tr.render(sig, _sources_stub(rows), "2026-01-01",
                              CLASSIFIER_FIXTURE)
        self.assertEqual(sig["S1"]["verdict"], "HOLD")
        self.assertIn("- HOLD: n=12 rate=0.42", md)
        self.assertIn("rate below S1_ESCALATION_RATE", md)
        self.assertNotIn("needed:", md.split("## S2")[0])
        self.assertIsNone(patch)

    def test_s2_completion_rate_below_floor_proposes(self) -> None:
        """S2: n=12 repair_used rows, rate=5/12 < 0.5 -> PROPOSE."""
        prd = "00001-example.md"
        rows = [
            _row(prd, f"task-{i}", 1, "completed" if i < 5 else "aborted",
                 tier_reason="default", repair_used=True)
            for i in range(12)
        ]
        sig = tr.signals(rows)
        self.assertEqual(sig["S2"]["verdict"], "PROPOSE")
        self.assertEqual(sig["S2"]["n"], 12)

    def test_s3_no_edit_rate_at_floor_proposes_codex_off(self) -> None:
        """S3: n=12 codex rows, no_edit_rate=6/12 >= 0.5 -> PROPOSE naming
        `_WORK_CODEX_RUNG=off`; no patch is produced for S3."""
        prd = "00001-example.md"
        rows = []
        for i in range(12):
            fields = {"implementor": "codex"}
            if i < 6:
                fields["cause"] = "codex_no_edit"
            rows.append(_row(prd, f"task-{i}", 1, "completed",
                              tier_reason="default", **fields))
        sig = tr.signals(rows)
        self.assertEqual(sig["S3"]["verdict"], "PROPOSE")
        md, patch = tr.render(sig, _sources_stub(rows), "2026-01-01", None)
        self.assertIn("_WORK_CODEX_RUNG=off", md)
        self.assertIsNone(patch)

    def test_s3_next_attempt_escalated_from_codex_at_floor_proposes(self) -> None:
        """S3: n=12 codex rows, no no-edit rows, but 6 whose next attempt
        carries `escalated_from: "codex"` -> escalated_rate=0.5 -> PROPOSE.
        The Claude follow-up rows are not codex rows and never inflate n."""
        prd = "00001-example.md"
        rows = [
            _row(prd, f"task-{i}", 1, "escalated" if i < 6 else "completed",
                 tier_reason="default", implementor="codex")
            for i in range(12)
        ]
        rows += [
            _row(prd, f"task-{i}", 2, "completed", tier_reason="default",
                 implementor="claude", escalated_from="codex")
            for i in range(6)
        ]
        sig = tr.signals(rows)
        self.assertEqual(sig["S3"]["n"], 12)
        self.assertEqual(sig["S3"]["no_edit_rate"], 0.0)
        self.assertEqual(sig["S3"]["escalated_rate"], 0.5)
        self.assertEqual(sig["S3"]["verdict"], "PROPOSE")

    def test_missing_attempt_number_is_unparsed_not_silently_deduped(self) -> None:
        """A row without an int `attempt.attempt` has no dedupe key and no
        rung index -> `UNPARSED: attempt.attempt`, never a silent collapse of
        every such row into one."""
        row = _row("00001-example.md", "task-1", 1, "completed")
        del row["attempt"]["attempt"]
        rows, reasons = tr.parse_rows(json.dumps(row) + "\n")
        self.assertEqual(rows, [])
        self.assertEqual(reasons, ["line 1: UNPARSED: attempt.attempt"])

    def test_out_of_scope_tier_reasons_never_move_a_signal(self) -> None:
        """contract/algorithmic_risk/floor rows never feed S1-S3 even when
        they would otherwise trip every floor; they still count in the
        report table (opus and operator floors are out of tuning scope)."""
        prd = "00001-example.md"
        rows = []
        for reason in ("contract", "algorithmic_risk", "floor"):
            for i in range(12):
                rows.append(_row(
                    prd, f"{reason}-{i}", 1, "escalated", tier_reason=reason,
                    repair_used=True, implementor="codex",
                    cause="codex_no_edit",
                ))
        sig = tr.signals(rows)
        self.assertEqual(sig["S1"]["n"], 0)
        self.assertEqual(sig["S1"]["verdict"], "HOLD")
        self.assertEqual(sig["S2"]["n"], 0)
        self.assertEqual(sig["S2"]["verdict"], "HOLD")
        self.assertEqual(sig["S3"]["n"], 0)
        self.assertEqual(sig["S3"]["verdict"], "HOLD")
        counts = sig["report"]["escalations_by_reason"]
        self.assertEqual(counts["contract"], 12)
        self.assertEqual(counts["algorithmic_risk"], 12)
        self.assertEqual(counts["floor"], 12)

    def test_unknown_tier_reason_still_appears_in_the_report_table(self) -> None:
        """A reason value the classifier does not emit today is rendered
        after the fixed eight rows, never dropped from the table."""
        rows = [_row("00001-example.md", "task-1", 1, "escalated",
                     tier_reason="widened")]
        md, _patch = tr.render(tr.signals(rows), _sources_stub(rows),
                               "2026-01-01", CLASSIFIER_FIXTURE)
        table = md.split("## Escalations by tier reason")[1]
        self.assertIn("| unattributed | 0 |\n| widened | 1 |", table)

    def test_duplicate_attempt_row_counts_once(self) -> None:
        """A row repeated verbatim (same batch_id/prd/task_id/attempt.attempt)
        is deduped: deduped rows is one less than raw parsed rows."""
        prd = "00001-example.md"
        rows = [
            _row(prd, f"task-{i}", 1, "completed", tier_reason="default")
            for i in range(3)
        ]
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            ledger = tmp_path / "attempts.jsonl"
            lines = [json.dumps(r) for r in rows] + [json.dumps(rows[0])]
            ledger.write_text("\n".join(lines) + "\n", encoding="utf-8")

            raw, _reasons = tr.parse_rows(ledger.read_text(encoding="utf-8"))
            deduped, _reasons2 = tr.load_rows(ledger)
            self.assertEqual(len(raw), 4)
            self.assertEqual(len(deduped), 3)

            classifier = _write_classifier(tmp_path)
            out_dir = tmp_path / "out"
            result = _run_cli(ledger, out_dir, "2026-01-01", classifier)
            self.assertEqual(result.returncode, 0, result.stderr)
            md = (out_dir / "routing-proposal-2026-01-01.md").read_text()
            self.assertIn("- rows: 4", md)
            self.assertIn("- deduped rows: 3", md)

    def test_missing_attempt_outcome_is_unparsed_but_others_count(self) -> None:
        """A row missing `attempt.outcome` -> `UNPARSED: attempt.outcome`;
        the other rows still count and the proposal shows `unparsed: 1`."""
        prd = "00001-example.md"
        good = [
            _row(prd, f"task-{i}", 1, "completed", tier_reason="default")
            for i in range(3)
        ]
        bad_row = _row(prd, "task-bad", 1, "completed", tier_reason="default")
        del bad_row["attempt"]["outcome"]

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            ledger = tmp_path / "attempts.jsonl"
            lines = [json.dumps(r) for r in good] + [json.dumps(bad_row)]
            ledger.write_text("\n".join(lines) + "\n", encoding="utf-8")

            raw, reasons = tr.parse_rows(ledger.read_text(encoding="utf-8"))
            self.assertEqual(len(raw), 3)
            self.assertTrue(
                any("UNPARSED: attempt.outcome" in r for r in reasons)
            )

            classifier = _write_classifier(tmp_path)
            out_dir = tmp_path / "out"
            result = _run_cli(ledger, out_dir, "2026-01-01", classifier)
            self.assertEqual(result.returncode, 0, result.stderr)
            md = (out_dir / "routing-proposal-2026-01-01.md").read_text()
            self.assertIn("- unparsed: 1", md)
            self.assertIn("- rows: 3", md)

    def test_classifier_without_literal_is_unparsed_with_no_patch(self) -> None:
        """A classifier missing the `_MECHANICAL_MAX_LINES` literal reports
        `UNPARSED: _MECHANICAL_MAX_LINES` and writes no `.patch`, even on an
        S1 PROPOSE ledger."""
        prd = "00001-example.md"
        rows = [
            _row(prd, f"task-{i}", 1, "escalated" if i < 7 else "completed",
                 tier_reason="mechanical")
            for i in range(12)
        ]
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            ledger = tmp_path / "attempts.jsonl"
            _write_ledger(ledger, rows)
            classifier = _write_classifier(tmp_path, CLASSIFIER_NO_LITERAL)
            out_dir = tmp_path / "out"
            result = _run_cli(ledger, out_dir, "2026-01-01", classifier)
            self.assertEqual(result.returncode, 0, result.stderr)

            md = (out_dir / "routing-proposal-2026-01-01.md").read_text()
            self.assertIn("UNPARSED: _MECHANICAL_MAX_LINES", md)
            self.assertFalse(
                (out_dir / "routing-proposal-2026-01-01.patch").exists()
            )

    def test_two_runs_same_inputs_are_byte_identical(self) -> None:
        """Same ledger and `--date` on two runs -> byte-identical `.md` and
        `.patch` files (no timestamps beyond the given date, sorted lists)."""
        prd = "00001-example.md"
        rows = [
            _row(prd, f"task-{i}", 1, "escalated" if i < 7 else "completed",
                 tier_reason="mechanical")
            for i in range(12)
        ]
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            ledger = tmp_path / "attempts.jsonl"
            _write_ledger(ledger, rows)
            classifier = _write_classifier(tmp_path)
            out_dir = tmp_path / "out"

            result1 = _run_cli(ledger, out_dir, "2026-01-01", classifier)
            self.assertEqual(result1.returncode, 0, result1.stderr)
            md1 = (out_dir / "routing-proposal-2026-01-01.md").read_bytes()
            patch1 = (out_dir / "routing-proposal-2026-01-01.patch").read_bytes()

            result2 = _run_cli(ledger, out_dir, "2026-01-01", classifier)
            self.assertEqual(result2.returncode, 0, result2.stderr)
            md2 = (out_dir / "routing-proposal-2026-01-01.md").read_bytes()
            patch2 = (out_dir / "routing-proposal-2026-01-01.patch").read_bytes()

            self.assertEqual(md1, md2)
            self.assertEqual(patch1, patch2)

    def test_unreadable_ledger_exits_1_and_writes_nothing(self) -> None:
        """Phase 1 acceptance: a nonexistent ledger exits 1 and the out-dir
        is never created."""
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp) / "out"
            result = _run_cli(Path("/nonexistent"), out_dir, "2026-01-01")
            self.assertEqual(result.returncode, 1)
            self.assertFalse(out_dir.exists())

    def test_all_rows_unparsed_exits_1_and_writes_nothing(self) -> None:
        """A ledger whose only line is not JSON parses zero rows -> the
        whole run is UNPARSED, exit 1, nothing written."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            ledger = tmp_path / "attempts.jsonl"
            ledger.write_text("not json\n", encoding="utf-8")
            out_dir = tmp_path / "out"
            result = _run_cli(ledger, out_dir, "2026-01-01")
            self.assertEqual(result.returncode, 1)
            self.assertIn("UNPARSED", result.stderr)
            self.assertFalse(out_dir.exists())


if __name__ == "__main__":
    unittest.main()
