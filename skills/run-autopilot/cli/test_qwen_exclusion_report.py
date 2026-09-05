"""Runtime Qwen file exclusions must survive into the operator's report."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from cli import render_report


def test_stale_eligible_task_reports_files_once_across_multiple_attempts() -> None:
    task = {
        "qwen_eligible": True,
        "attempts": [
            {"qwen_excluded_reason": "files"},
            {"qwen_excluded_reason": "files"},
        ],
    }
    assert render_report._exclusion_line([task]) == (
        "Excluded from qwen: none (plan-time); dispatch-time reroutes: files 1"
    )


def test_plan_and_runtime_exclusions_remain_separate_populations() -> None:
    tasks = [
        {"qwen_eligible": False, "qwen_excluded_reason": "files"},
        {"qwen_eligible": True, "attempts": [{"qwen_excluded_reason": "files"}]},
        {
            "qwen_eligible": True,
            "attempts": [{"qwen_excluded_reason": "memory_pressure"}],
        },
    ]
    assert render_report._exclusion_line(tasks) == (
        "Excluded from qwen: files 1 (plan-time); dispatch-time reroutes: "
        "files 1, memory_pressure 1"
    )
