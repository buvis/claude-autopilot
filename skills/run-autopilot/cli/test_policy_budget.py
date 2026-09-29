#!/usr/bin/env python3
"""Tests for cli/policy.py's per-model wall-clock task budget.

Split out of test_policy.py to keep that file under the 800-line limit.
"""

from __future__ import annotations

import unittest

from cli import policy


class TaskOverBudgetTests(unittest.TestCase):
    """Per-model wall-clock budget: strictly-greater-than fires, missing or
    malformed stamps never do."""

    def test_opus_task_over_forty_five_minutes_is_over_budget(self) -> None:
        task = {"started_at": 0, "done_at": 2701, "model": "opus"}
        self.assertTrue(policy.task_over_budget(task))

    def test_sonnet_task_under_twenty_minutes_is_within_budget(self) -> None:
        task = {"started_at": 0, "done_at": 1199, "model": "sonnet"}
        self.assertFalse(policy.task_over_budget(task))

    def test_missing_stamp_is_never_over_budget(self) -> None:
        self.assertFalse(
            policy.task_over_budget({"done_at": 10_000, "model": "opus"})
        )
        self.assertFalse(
            policy.task_over_budget({"started_at": 0, "model": "opus"})
        )
        self.assertFalse(
            policy.task_over_budget(
                {"started_at": "0", "done_at": 10_000, "model": "opus"}
            )
        )
        self.assertFalse(
            policy.task_over_budget(
                {"started_at": 0, "done_at": "10000", "model": "opus"}
            )
        )

    def test_unknown_model_is_never_over_budget(self) -> None:
        self.assertFalse(
            policy.task_over_budget(
                {"started_at": 0, "done_at": 999_999, "model": "gpt-5"}
            )
        )
        self.assertFalse(
            policy.task_over_budget({"started_at": 0, "done_at": 999_999})
        )


if __name__ == "__main__":
    unittest.main()
