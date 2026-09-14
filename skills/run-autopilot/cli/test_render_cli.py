#!/usr/bin/env python3
"""The subprocess half of the PRD 00107 render tests: `autopilot render`
and `autopilot status` driven as real processes against a constructed
<repo>/dev/local/autopilot tree, plus the report header's Started: line.

Split out of test_render.py, which keeps the in-process render tests and
the goldens.
"""

from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

CLI_DIR = Path(__file__).resolve().parent
CLI_MAIN = CLI_DIR / "__main__.py"
GOLDEN = CLI_DIR / "golden"

NOW = "2026-08-09T12:00:00Z"
STARTED = "2026-08-09T10:00:00Z"


def _state() -> dict:
    return json.loads((GOLDEN / "state-render.json").read_text(encoding="utf-8"))


def _batch_state() -> dict:
    """A reconstruction of real batch 202608162223 with hand-written dict
    counts (not the archived record) standing in for the batch that exposed
    all five original render_report.py defects."""
    return json.loads(
        (GOLDEN / "state-batch-202608162223-reconstructed.json").read_text(
            encoding="utf-8",
        ),
    )


class CliWiringTests(unittest.TestCase):
    """`autopilot render`/`autopilot status` as real subprocesses against a
    constructed <repo>/dev/local/autopilot tree."""

    def setUp(self) -> None:
        import tempfile

        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.repo = Path(tmp.name)
        self.ap_dir = self.repo / "dev" / "local" / "autopilot"
        self.ap_dir.mkdir(parents=True)
        self.state_path = self.ap_dir / "state.json"
        self.state_path.write_text(
            (GOLDEN / "state-render.json").read_text(encoding="utf-8"),
            encoding="utf-8",
        )
        (self.ap_dir / "loop-metrics.jsonl").write_text(
            (GOLDEN / "metrics-render.jsonl").read_text(encoding="utf-8"),
            encoding="utf-8",
        )

    def _run(self, args: list[str]) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, str(CLI_MAIN), *args, "--state", str(self.state_path)],
            capture_output=True,
            text=True,
        )

    def test_render_audit_writes_the_reviews_file(self) -> None:
        proc = self._run(["render", "audit", "--now", NOW])
        self.assertEqual(proc.returncode, 0, proc.stderr)
        out = self.repo / "dev" / "local" / "reviews" / "00040-feature-x-v1-audit.md"
        self.assertTrue(out.exists())
        text = out.read_text(encoding="utf-8")
        self.assertIn("# Decision Audit Log: 00040-feature-x-v1", text)
        # First render: Started == Completed == --now.
        self.assertIn(f"Started: {NOW}", text)

    def test_render_audit_preserves_started_on_rerender(self) -> None:
        self._run(["render", "audit", "--now", STARTED])
        proc = self._run(["render", "audit", "--now", NOW])
        self.assertEqual(proc.returncode, 0, proc.stderr)
        out = self.repo / "dev" / "local" / "reviews" / "00040-feature-x-v1-audit.md"
        text = out.read_text(encoding="utf-8")
        self.assertIn(f"Started: {STARTED}", text)
        self.assertIn(f"Completed: {NOW}", text)

    def test_render_report_creates_header_once_then_appends(self) -> None:
        first = self._run(["render", "report", "--now", NOW])
        self.assertEqual(first.returncode, 0, first.stderr)
        second = self._run(["render", "report", "--summary", "--now", NOW])
        self.assertEqual(second.returncode, 0, second.stderr)
        report = self.ap_dir / "reports" / "202607202320-report.md"
        text = report.read_text(encoding="utf-8")
        self.assertEqual(text.count("# Autopilot Batch Report 202607202320"), 1)
        self.assertIn("## 00040-feature-x-v1.md", text)
        self.assertIn("## Batch Summary", text)

    def test_render_report_reads_the_batch_attempt_ledger(self) -> None:
        # complete-prd drains state.tasks[].attempts into
        # <autopilot_dir>/ledger/attempts.jsonl before the section renders, so
        # the Implementor table exists only if the CLI hands prd_section that
        # path. Dropping the argument leaves `no implementor data` here while
        # every in-process ledger test stays green.
        state = _state()
        state["tasks"] = []
        self.state_path.write_text(json.dumps(state), encoding="utf-8")
        (self.ap_dir / "ledger").mkdir()
        (self.ap_dir / "ledger" / "attempts.jsonl").write_text(
            "".join(
                json.dumps(
                    {
                        "batch_id": state["batch"]["id"],
                        "prd": state["prd"],
                        "task_id": task_id,
                        "recorded_at": "2026-09-07T05:48:00Z",
                        "attempt": {"attempt": attempt, "implementor": implementor},
                    },
                )
                + "\n"
                for task_id, attempt, implementor in (
                    ("1", 1, "claude"),
                    ("1", 2, "claude"),
                    ("2", 1, "qwen"),
                )
            ),
            encoding="utf-8",
        )
        proc = self._run(["render", "report", "--now", NOW])
        self.assertEqual(proc.returncode, 0, proc.stderr)
        text = (self.ap_dir / "reports" / "202607202320-report.md").read_text(
            encoding="utf-8",
        )
        self.assertNotIn("no implementor data", text)
        self.assertIn("| claude | 2 |", text)
        self.assertIn("| qwen | 1 |", text)

    def test_report_keeps_ledger_only_attempts_with_convergence(self) -> None:
        # Tasks drained and the batch record wiped to 0/0: the Implementor
        # table can only come from the ledger, and the task counts and the
        # Run conditions line only from the review_converged row the golden
        # loop-metrics.jsonl carries for this PRD and batch.
        state = _state()
        state["tasks"] = []
        state["batch"]["completed_prds"] = [
            {
                "filename": state["prd"],
                "cycles": 2,
                "tasks_completed": 0,
                "tasks_total": 0,
            },
        ]
        self.state_path.write_text(json.dumps(state), encoding="utf-8")
        (self.ap_dir / "ledger").mkdir()
        (self.ap_dir / "ledger" / "attempts.jsonl").write_text(
            json.dumps(
                {
                    "batch_id": state["batch"]["id"],
                    "prd": state["prd"],
                    "task_id": "1",
                    "recorded_at": "2026-09-07T05:48:00Z",
                    "attempt": {"attempt": 1, "implementor": "qwen"},
                },
            )
            + "\n",
            encoding="utf-8",
        )
        proc = self._run(["render", "report", "--now", NOW])
        self.assertEqual(proc.returncode, 0, proc.stderr)
        text = (self.ap_dir / "reports" / "202607202320-report.md").read_text(
            encoding="utf-8",
        )
        self.assertIn("| qwen | 1 |", text)
        self.assertIn("- Run conditions: cap 2 ·", text)
        self.assertIn("- Tasks: 3/3", text)
        self.assertNotIn("- Tasks: 0/0", text)

    def test_report_reads_loud_when_no_event_row_matches_the_batch(self) -> None:
        # The golden event row retagged to another batch: the report must say
        # so rather than borrow a foreign batch's run conditions.
        metrics = self.ap_dir / "loop-metrics.jsonl"
        rows = [
            json.loads(line)
            for line in metrics.read_text(encoding="utf-8").splitlines()
        ]
        for row in rows:
            if row.get("event") == "review_converged":
                row["batch"] = "202601010000"
        metrics.write_text(
            "".join(json.dumps(row) + "\n" for row in rows),
            encoding="utf-8",
        )
        proc = self._run(["render", "report", "--now", NOW])
        self.assertEqual(proc.returncode, 0, proc.stderr)
        text = (self.ap_dir / "reports" / "202607202320-report.md").read_text(
            encoding="utf-8",
        )
        self.assertIn("- Run conditions: no review_converged row", text)
        self.assertNotIn("- Run conditions: cap 2", text)

    def test_report_reads_loud_when_the_event_row_belongs_to_another_prd(
        self,
    ) -> None:
        # Same batch, another PRD: a multi-PRD batch holds one event row per
        # PRD, and a match on batch alone would print PRD B's run conditions
        # under PRD A's heading.
        metrics = self.ap_dir / "loop-metrics.jsonl"
        rows = [
            json.loads(line)
            for line in metrics.read_text(encoding="utf-8").splitlines()
        ]
        for row in rows:
            if row.get("event") == "review_converged":
                self.assertEqual(row["batch"], _state()["batch"]["id"])
                row["prd"] = "00002-object-entry-v1.md"
        metrics.write_text(
            "".join(json.dumps(row) + "\n" for row in rows),
            encoding="utf-8",
        )
        proc = self._run(["render", "report", "--now", NOW])
        self.assertEqual(proc.returncode, 0, proc.stderr)
        text = (self.ap_dir / "reports" / "202607202320-report.md").read_text(
            encoding="utf-8",
        )
        self.assertIn("- Run conditions: no review_converged row", text)
        self.assertNotIn("- Run conditions: cap 2", text)

    def test_report_reads_the_event_row_from_the_metrics_flag(self) -> None:
        # `--metrics` names the file for session rows and event rows alike:
        # the event row lives only in a side file and is stripped from the
        # default loop-metrics.jsonl, so only a CLI that loads events from
        # the flagged path can still render the run conditions.
        default = self.ap_dir / "loop-metrics.jsonl"
        lines = default.read_text(encoding="utf-8").splitlines(keepends=True)
        sessions = [line for line in lines if '"event"' not in line]
        self.assertEqual(len(sessions), len(lines) - 1)
        default.write_text("".join(sessions), encoding="utf-8")
        side = self.repo / "side-metrics.jsonl"
        side.write_text("".join(lines), encoding="utf-8")
        proc = self._run(["render", "report", "--metrics", str(side), "--now", NOW])
        self.assertEqual(proc.returncode, 0, proc.stderr)
        text = (self.ap_dir / "reports" / "202607202320-report.md").read_text(
            encoding="utf-8",
        )
        self.assertIn("- Run conditions: cap 2 ·", text)
        self.assertNotIn("no review_converged row", text)

    def test_render_report_stalled_appends_the_short_form(self) -> None:
        proc = self._run(
            [
                "render",
                "report",
                "--stalled",
                "--site",
                "oversized_plan",
                "--detail",
                "34 tasks",
                "--now",
                NOW,
            ],
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        report = self.ap_dir / "reports" / "202607202320-report.md"
        self.assertIn("STALLED (oversized_plan)", report.read_text(encoding="utf-8"))

    def test_render_metrics_prints_the_summary(self) -> None:
        proc = self._run(["render", "metrics"])
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("| 00040-feature-x-v1.md | 5 | 1069 | 28.16 |", proc.stdout)

    def test_render_stdout_writes_nothing(self) -> None:
        proc = self._run(["render", "report", "--stdout", "--now", NOW])
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("## 00040-feature-x-v1.md", proc.stdout)
        self.assertFalse((self.ap_dir / "reports").exists())

    def test_status_prints_the_plain_view(self) -> None:
        proc = self._run(["status"])
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("PRD:    00040-feature-x-v1.md", proc.stdout)
        self.assertIn("Phase:  done -> next: done", proc.stdout)

    def test_status_on_missing_state_exits_2(self) -> None:
        self.state_path.unlink()
        proc = self._run(["status"])
        self.assertEqual(proc.returncode, 2)

    def test_render_audit_outside_a_dev_local_autopilot_tree_refuses(self) -> None:
        """A --state outside dev/local/autopilot must exit 2, never derive a
        repo root from an arbitrary ancestor and plant dev/local/reviews
        there (the committed first version did exactly that)."""
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            stray = Path(tmp) / "state.json"
            stray.write_text(
                (GOLDEN / "state-render.json").read_text(encoding="utf-8"),
                encoding="utf-8",
            )
            proc = subprocess.run(
                [
                    sys.executable,
                    str(CLI_MAIN),
                    "render",
                    "audit",
                    "--now",
                    NOW,
                    "--state",
                    str(stray),
                ],
                capture_output=True,
                text=True,
            )
            planted = list(Path(tmp).parents[2].glob("dev/local/reviews/*"))
        self.assertEqual(proc.returncode, 2)
        self.assertIn("not a dev/local/autopilot dir", proc.stderr)
        self.assertNotIn("Traceback", proc.stderr)
        self.assertEqual(planted, [])


class HeaderStartedTests(unittest.TestCase):
    """The report header's Started: line is the batch's real start -
    the first metrics row's ts_start for this batch, or batch.id's
    yyyymmddHHMM stamp when no metrics rows exist yet - never the
    file-write --now (R4)."""

    def setUp(self) -> None:
        import tempfile

        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.repo = Path(tmp.name)
        self.ap_dir = self.repo / "dev" / "local" / "autopilot"
        self.ap_dir.mkdir(parents=True)
        self.state_path = self.ap_dir / "state.json"

    def _run(self, args: list[str]) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, str(CLI_MAIN), *args, "--state", str(self.state_path)],
            capture_output=True,
            text=True,
        )

    def test_started_derives_from_the_first_metrics_row_for_this_batch(self) -> None:
        state = _state()
        state["batch"]["id"] = "202311142213"
        self.state_path.write_text(json.dumps(state), encoding="utf-8")
        (self.ap_dir / "loop-metrics.jsonl").write_text(
            json.dumps(
                {
                    "ts_start": 1700000000,
                    "ts_end": 1700000900,
                    "wall_secs": 900,
                    "prd": state["prd"],
                    "batch": "202311142213",
                    "phase_launched": "",
                    "phase_end": "review",
                    "signal": "continue",
                    "model": "claude-opus-5[1m]",
                    "cost_usd": 1.0,
                    "tokens_out": 100,
                },
            )
            + "\n",
            encoding="utf-8",
        )
        proc = self._run(["render", "report", "--now", NOW])
        self.assertEqual(proc.returncode, 0, proc.stderr)
        report = self.ap_dir / "reports" / "202311142213-report.md"
        text = report.read_text(encoding="utf-8")
        self.assertIn("Started: 2023-11-14T22:13:20Z", text)
        self.assertNotIn(f"Started: {NOW}", text)

    def test_started_falls_back_to_batch_id_when_no_metrics_rows_exist(self) -> None:
        state = _state()
        state["batch"]["id"] = "202301020304"
        self.state_path.write_text(json.dumps(state), encoding="utf-8")
        (self.ap_dir / "loop-metrics.jsonl").write_text("", encoding="utf-8")
        proc = self._run(["render", "report", "--now", NOW])
        self.assertEqual(proc.returncode, 0, proc.stderr)
        report = self.ap_dir / "reports" / "202301020304-report.md"
        text = report.read_text(encoding="utf-8")
        self.assertIn("Started: 2023-01-02T03:04:00Z", text)
        self.assertNotIn(f"Started: {NOW}", text)

    def test_started_derives_from_the_real_202608162223_batch_metrics_row(
        self,
    ) -> None:
        # PRD 00107 item 4 (R4), proven against the one batch this task
        # exists to reconstruct: earliest ts_start row tagged with
        # "batch": "202608162223" is epoch 1786911719.
        state = _batch_state()
        self.state_path.write_text(json.dumps(state), encoding="utf-8")
        (self.ap_dir / "loop-metrics.jsonl").write_text(
            json.dumps(
                {
                    "ts_start": 1786911719,
                    "ts_end": 1786919356,
                    "wall_secs": 7637,
                    "prd": state["prd"],
                    "batch": "202608162223",
                    "phase_launched": "",
                    "phase_end": "review",
                    "signal": "continue",
                    "model": "claude-opus-5[1m]",
                    "cost_usd": 1.0,
                    "tokens_out": 100,
                },
            )
            + "\n",
            encoding="utf-8",
        )
        proc = self._run(["render", "report", "--now", NOW])
        self.assertEqual(proc.returncode, 0, proc.stderr)
        report = self.ap_dir / "reports" / "202608162223-report.md"
        text = report.read_text(encoding="utf-8")
        self.assertIn("Started: 2026-08-16T20:21:59Z", text)
        self.assertNotIn(f"Started: {NOW}", text)


if __name__ == "__main__":
    unittest.main()
