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

    def test_empty_task_list_prints_none_stamped(self) -> None:
        # No tasks at all: none can carry both stamps, so the block
        # renders only the fallback line.
        state = {"tasks": []}
        text = render_report.prd_section(state, [], NOW)
        self.assertIn("Task wall-clock:\n- none stamped", text)
        self.assertNotIn("not stamped", text)

    def test_missing_tasks_key_prints_none_stamped(self) -> None:
        # No "tasks" key at all behaves the same as an empty list.
        state = {}
        text = render_report.prd_section(state, [], NOW)
        self.assertIn("Task wall-clock:\n- none stamped", text)
        self.assertNotIn("not stamped", text)

    def test_all_unstamped_tasks_print_none_stamped(self) -> None:
        # Every task is missing one of its two stamps: none carries both,
        # so the block renders only the fallback line, never a per-task
        # "not stamped" line.
        state = {
            "tasks": [
                {"id": "a", "model": "haiku", "started_at": 0},
                {"id": "b", "model": "opus", "done_at": 60},
            ]
        }
        text = render_report.prd_section(state, [], NOW)
        self.assertIn("Task wall-clock:\n- none stamped", text)
        self.assertNotIn("not stamped", text)

    def test_string_stamp_alongside_valid_task_renders_not_stamped(self) -> None:
        # A non-int started_at must not raise TypeError, and is treated
        # exactly like a missing stamp: the well-stamped task still gets
        # its line, the string-stamped one gets "not stamped" rather than
        # aborting the whole render.
        state = {
            "tasks": [
                {"id": "s1", "model": "opus", "started_at": 0, "done_at": 60},
                {
                    "id": "bad",
                    "model": "sonnet",
                    "started_at": "oops",
                    "done_at": 600,
                },
            ]
        }
        text = render_report.prd_section(state, [], NOW)
        self.assertIn(
            "Task wall-clock:\n- s1 (opus): 1 min\n- bad (sonnet): not stamped", text
        )

    def test_all_string_stamped_tasks_print_none_stamped(self) -> None:
        # Stamps that are present but not ints must not count toward
        # any_stamped: with no task carrying two real int stamps, the
        # block falls back to "none stamped" instead of raising or
        # printing a per-task line.
        state = {
            "tasks": [
                {"id": "bad", "model": "sonnet", "started_at": "0", "done_at": "600"},
            ]
        }
        text = render_report.prd_section(state, [], NOW)
        self.assertIn("Task wall-clock:\n- none stamped", text)
        self.assertNotIn("not stamped", text)

    def test_negative_span_prints_not_stamped(self) -> None:
        # done_at before started_at must never render a negative minute
        # count; it is treated as not stamped instead.
        state = {
            "tasks": [
                {"id": "t1", "model": "sonnet", "started_at": 100, "done_at": 0},
            ]
        }
        text = render_report.prd_section(state, [], NOW)
        self.assertIn("Task wall-clock:\n- t1 (sonnet): not stamped", text)

    def test_task_with_missing_model_does_not_print_none(self) -> None:
        # No "model" key: the line must not leak the literal "None".
        state = {
            "tasks": [
                {"id": "t1", "started_at": 0, "done_at": 60},
            ]
        }
        text = render_report.prd_section(state, [], NOW)
        self.assertIn("- t1 (", text)
        self.assertIn("): 1 min", text)
        self.assertNotIn("None", text)


if __name__ == "__main__":
    unittest.main()
