#!/usr/bin/env python3
"""Tests for the `- Run conditions:` line of the batch report's completed-PRD
section (render_report.run_conditions_line) and the `- Tasks:` fallback it
feeds inside render_report.prd_section, called in process.

Split out of test_render.py, which keeps the golden renders (the golden
event row is pinned there through expected/report-section.md). The rows
here are hand-built so that no two segments share a value and each field
the loop can leave odd is odd.
"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

CLI_DIR = Path(__file__).resolve().parent
GOLDEN = CLI_DIR / "golden"

sys.path.insert(0, str(CLI_DIR.parent))

from cli import render_metrics, render_report

NOW = "2026-08-09T12:00:00Z"


def _state() -> dict:
    return json.loads((GOLDEN / "state-render.json").read_text(encoding="utf-8"))


def _rows() -> list[dict]:
    return render_metrics.load_rows(GOLDEN / "metrics-render.jsonl")


# One review_converged row exactly as the loop appends it to loop-metrics.jsonl.
CAP_DEFERRED_ROW = {
    "event": "review_converged",
    "prd": "x",
    "batch": "b",
    "cycles_to_converge": 2,
    "outcome": "cap_deferred",
    "ts": 1,
    "rework_cap": 2,
    "build_models": ["claude-sonnet-5[1m]"],
    "attempt_tiers": ["sonnet"],
    "tasks_planned": 21,
    "tasks_completed": 4,
    "tasks_in_prd": 4,
    "cycles": [
        {
            "cycle": 1,
            "reviewers": ["alice", "blake", "bob"],
            "verdict": 8,
            "findings": {"critical": 1, "high": 4, "medium": 3, "low": 0},
        },
        {
            "cycle": 2,
            "reviewers": ["alice", "blake", "bob"],
            "verdict": 11,
            "findings": {"critical": 0, "high": 1, "medium": 8, "low": 2},
        },
    ],
}

# A row where every segment has to come from its own field: a cap of 3, a
# cycle count (3) above the length of the cycle list (2), an outcome that
# contradicts the last cycle's verdict, two-name and one-name rosters, a gap
# in the cycle numbers (1, 3), two build models, and three task counts that
# all differ.
SKEWED_ROW = {
    "event": "review_converged",
    "prd": "x",
    "batch": "b",
    "cycles_to_converge": 3,
    "outcome": "cap_deferred",
    "ts": 1,
    "rework_cap": 3,
    "build_models": ["claude-sonnet-5", "claude-opus-5"],
    "attempt_tiers": ["opus"],
    "tasks_planned": 5,
    "tasks_completed": 2,
    "tasks_in_prd": 7,
    "cycles": [
        {
            "cycle": 1,
            "reviewers": ["alice", "carl"],
            "verdict": 1,
            "findings": {"critical": 0, "high": 0, "medium": 1, "low": 0},
        },
        {
            "cycle": 3,
            "reviewers": ["blake"],
            "verdict": "converged",
            "findings": {"critical": 0, "high": 0, "medium": 0, "low": 0},
        },
    ],
}


class RunConditionsTests(unittest.TestCase):
    """The `- Run conditions:` line and the `- Tasks:` fallback it feeds."""

    def test_run_conditions_line_renders_from_the_event_row(self) -> None:
        self.assertEqual(
            render_report.run_conditions_line(CAP_DEFERRED_ROW),
            "cap 2 · 2 cycles, cap_deferred · c1 alice,blake,bob 1/4/3/0 · "
            "c2 alice,blake,bob 0/1/8/2 (crit/high/med/low) · "
            "build claude-sonnet-5[1m] · tiers sonnet · tasks 21 planned, 4 in PRD",
        )

    def test_every_segment_reads_its_own_field(self) -> None:
        # No constant, count, roster or index shortcut survives this row:
        # cap 3 (not 2), 3 cycles (not len(cycles) == 2), cap_deferred (not
        # the last verdict), alice,carl and blake (not the golden trio), c3
        # (not c2 from the list index), two build models, and 5/7 for
        # planned/in PRD with tasks_completed 2 rendered nowhere.
        self.assertEqual(
            render_report.run_conditions_line(SKEWED_ROW),
            "cap 3 · 3 cycles, cap_deferred · c1 alice,carl 0/0/1/0 · "
            "c3 blake 0/0/0/0 (crit/high/med/low) · "
            "build claude-sonnet-5,claude-opus-5 · tiers opus · "
            "tasks 5 planned, 7 in PRD",
        )

    def test_outcome_comes_from_the_row_not_the_last_verdict(self) -> None:
        # A converged run whose last review file was unreadable (null
        # verdict) still reads converged. SKEWED_ROW carries the mirror
        # case: a cap_deferred row whose last verdict says converged.
        last = {"cycle": 2, "reviewers": None, "verdict": None, "findings": None}
        row = {
            **SKEWED_ROW,
            "outcome": "converged",
            "cycles": [SKEWED_ROW["cycles"][0], last],
        }
        self.assertIn(
            "cap 3 · 3 cycles, converged · c1 alice,carl 0/0/1/0 · "
            "c2 ? ?/?/?/? (crit/high/med/low) · build",
            render_report.run_conditions_line(row),
        )

    def test_run_conditions_line_marks_nulls_with_question_marks(self) -> None:
        # Null cap, a single cycle whose review file was unreadable (null
        # reviewers and findings), no build models, no tiers, null counts.
        row = {
            "rework_cap": None,
            "cycles_to_converge": 1,
            "outcome": "cap_deferred",
            "build_models": [],
            "attempt_tiers": [],
            "tasks_planned": None,
            "tasks_completed": 4,
            "tasks_in_prd": None,
            "cycles": [
                {"cycle": 1, "reviewers": None, "verdict": None, "findings": None}
            ],
        }
        self.assertEqual(
            render_report.run_conditions_line(row),
            "cap ? · 1 cycle, cap_deferred · c1 ? ?/?/?/? (crit/high/med/low) · "
            "build ? · tiers ? · tasks ? planned, ? in PRD",
        )
        # No cycles at all: the cycle segments and the legend both go away.
        bare = {**row, "cycles_to_converge": None, "cycles": []}
        self.assertEqual(
            render_report.run_conditions_line(bare),
            "cap ? · ? cycles, cap_deferred · build ? · tiers ? · "
            "tasks ? planned, ? in PRD",
        )

    def test_zero_cycles_renders_zero_not_a_question_mark(self) -> None:
        # A cycle count of 0 is a measurement (the loop never reviewed);
        # only null stands for an unknown count.
        row = {**SKEWED_ROW, "cycles_to_converge": 0, "cycles": []}
        self.assertEqual(
            render_report.run_conditions_line(row),
            "cap 3 · 0 cycles, cap_deferred · build claude-sonnet-5,claude-opus-5 · "
            "tiers opus · tasks 5 planned, 7 in PRD",
        )

    def test_missing_event_row_renders_loud(self) -> None:
        text = render_report.prd_section(_state(), _rows(), NOW)
        self.assertIn("3/3\n- Run conditions: no review_converged row\n\n", text)

    def test_legacy_five_positional_call_still_renders_the_section(self) -> None:
        text = render_report.prd_section(_state(), _rows(), NOW, [], None)
        self.assertIn("- Run conditions: no review_converged row\n", text)

    def test_convergence_is_keyword_only(self) -> None:
        text = render_report.prd_section(
            _state(), _rows(), NOW, [], None, convergence=CAP_DEFERRED_ROW
        )
        self.assertIn("- Run conditions: cap 2 ·", text)
        with self.assertRaises(TypeError):
            render_report.prd_section(
                _state(), _rows(), NOW, [], None, CAP_DEFERRED_ROW
            )

    def test_tasks_line_falls_back_to_the_event_row_when_record_reads_zero(
        self,
    ) -> None:
        # The live task list reads 3/3 and the row's tasks_in_prd is bumped
        # to 9 so it differs from tasks_completed (4): a render that prefers
        # the task list, a real record (5/6) or the wrong row field shows.
        # Without a row 0/0 stays.
        row = {**CAP_DEFERRED_ROW, "tasks_in_prd": 9}
        zero = {"filename": _state()["prd"], "tasks_completed": 0, "tasks_total": 0}
        real = {**zero, "tasks_completed": 5, "tasks_total": 6}
        for records, expected in (([zero], "4/21"), ([], "4/21"), ([real], "5/6")):
            with self.subTest(records=records):
                state = _state()
                state["batch"]["completed_prds"] = records
                text = render_report.prd_section(state, [], NOW, convergence=row)
                self.assertIn(f"- Tasks: {expected}\n- Run conditions: cap 2 ·", text)
                self.assertNotIn("- Tasks: 3/3", text)
        state = _state()
        state["batch"]["completed_prds"] = [zero]
        self.assertIn("- Tasks: 0/0\n", render_report.prd_section(state, [], NOW))


if __name__ == "__main__":
    unittest.main()
