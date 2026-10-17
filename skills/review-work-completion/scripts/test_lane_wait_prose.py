"""Prose pins for the reviewer-lane wait: one long foreground call, not polls.

Background: `await_reviewer_outputs.py --budget 100` capped one call at
100 s to stay under the old Bash tool timeout. With the Bash tool's
`timeout` parameter now able to hold a foreground call up to 600000 ms,
one call can cover the whole wait instead of many short polls. These
tests pin the Watcher prompts (review-work-completion and fast-track
SKILL.md) and the design-solution review wait to the new budget and
call shape, and guard against a stray `--budget 100` surviving in any
skill's prose.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
REVIEW_SKILL = REPO_ROOT / "skills" / "review-work-completion" / "SKILL.md"
FAST_TRACK_SKILL = REPO_ROOT / "skills" / "fast-track" / "SKILL.md"
DESIGN_SKILL = REPO_ROOT / "skills" / "design-solution" / "SKILL.md"


def test_watcher_prompts_wait_in_long_calls() -> None:
    review_text = REVIEW_SKILL.read_text()
    fast_track_text = FAST_TRACK_SKILL.read_text()
    for text in (review_text, fast_track_text):
        assert "--budget 570" in text
        assert "timeout parameter set to 600000" in text
        assert "up to 6 times total" in text
    assert "after 6 runs (~57 min)" in review_text


def test_design_review_waits_once_and_never_polls() -> None:
    text = DESIGN_SKILL.read_text()
    assert "await_reviewer_outputs.py --budget 570" in text
    assert "On WAITING run it once more" in text
    assert "pgrep" in text
    assert "Monitor" in text
    assert "ScheduleWakeup" in text


def test_no_prose_keeps_the_hundred_second_budget() -> None:
    result = subprocess.run(
        ["rg", "-l", "-F", "--glob", "*.md", "--", "--budget 100", "skills"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    assert result.stdout.strip() == ""
