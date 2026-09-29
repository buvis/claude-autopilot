#!/usr/bin/env python3
"""Tests for the `Task wall-clock:` block that render_report.prd_section
appends after its existing per-PRD lines, driven by state["tasks"]'s
started_at/done_at stamps and cli.policy.task_over_budget.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

CLI_DIR = Path(__file__).resolve().parent

sys.path.insert(0, str(CLI_DIR.parent))

from cli import render_report

NOW = "2026-08-09T12:00:00Z"


class TaskWallClockBlockTests(unittest.TestCase):
    """The `Task wall-clock:` block appended to prd_section's output."""

    def test_report_prints_one_wall_line_per_task(self) -> None:
        state = {
            "tasks": [
                {"id": "t1", "model": "sonnet", "started_at": 0, "done_at": 600},
                {"id": "t2", "model": "haiku", "started_at": 0, "done_at": 300},
            ]
        }
        text = render_report.prd_section(state, [], NOW)
        self.assertIn(
            "Task wall-clock:\n- t1 (sonnet): 10 min\n- t2 (haiku): 5 min", text
        )

    def test_over_budget_task_is_flagged(self) -> None:
        # sonnet's budget is 1200s; 1300s (21 min) trips it, 600s (10 min)
        # does not, so only the first line carries the suffix.
        state = {
            "tasks": [
                {"id": "over", "model": "sonnet", "started_at": 0, "done_at": 1300},
                {"id": "under", "model": "sonnet", "started_at": 0, "done_at": 600},
            ]
        }
        text = render_report.prd_section(state, [], NOW)
        self.assertIn("- over (sonnet): 21 min [over budget]", text)
        self.assertIn("- under (sonnet): 10 min", text)
        self.assertNotIn("- under (sonnet): 10 min [over budget]", text)

    def test_unstamped_task_prints_not_stamped(self) -> None:
        # One fully stamped task alongside one missing done_at: since at
        # least one task carries both stamps, the unstamped one still gets
        # its own "not stamped" line rather than the all-unstamped fallback.
        state = {
            "tasks": [
                {"id": "s1", "model": "opus", "started_at": 0, "done_at": 60},
                {"id": "u1", "model": "sonnet", "started_at": 0},
            ]
        }
        text = render_report.prd_section(state, [], NOW)
        self.assertIn(
            "Task wall-clock:\n- s1 (opus): 1 min\n- u1 (sonnet): not stamped", text
        )

    def test_prd_without_stamps_prints_none_stamped(self) -> None:
        # Empty task list and an all-unstamped task list both count as "no
        # task carries both stamps": the block renders only "- none
        # stamped" and never a per-task "not stamped" line.
        empty = {"tasks": []}
        no_key = {}
        all_unstamped = {
            "tasks": [
                {"id": "a", "model": "haiku", "started_at": 0},
                {"id": "b", "model": "opus", "done_at": 60},
            ]
        }
        for state in (empty, no_key, all_unstamped):
            with self.subTest(state=state):
                text = render_report.prd_section(state, [], NOW)
                self.assertIn("Task wall-clock:\n- none stamped", text)
                self.assertNotIn("not stamped", text)


if __name__ == "__main__":
    unittest.main()
