#!/usr/bin/env python3
"""lane_check.py - the solo lane's code-decided escalation (PRD 00205).

`autopilot lane-check` runs this at the end of a solo build, before any
review: the decision that a finished build may take the single review pass
is made here, over the live git range, never by the session's reading of its
own work.

    diff_signal(work_start_sha, repo_root, git_dir) -> str | None
    escalate(state_path, signal)                    -> the committed state

Two checks, in order, over `work_start_sha..HEAD` read through
`custody.git_argv`: `unnamed_path` when any changed path is a hook or a
production path (a solo PRD named none, so any is unnamed); `security_diff`
when `lane.security_triggered` fires. A git command that fails escalates with
`check_failed` rather than passing: the check fails toward the expensive
lane. The session's own signals (`critical_finding`, `high_unresolved`,
`suite_red`) arrive through `--signal` and take the same write.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from . import custody, lane, schema, state

SESSION_SIGNALS = ("critical_finding", "high_unresolved", "suite_red", "review_failed")
CHECK_FAILED = "check_failed"
# Rename detection would list only a rename's destination and show no
# changed lines, so a production file renamed into a doc path would pass
# both checks. Both diffs read every path as an add plus a delete instead.
_NO_RENAMES = "--no-renames"


def _git_output(argv: list[str]) -> str | None:
    """stdout of a git command, or None when it failed to run or exited
    non-zero (the caller reads None as `check_failed`)."""
    try:
        result = subprocess.run(argv, capture_output=True, text=True)
    except OSError:
        return None
    return result.stdout if result.returncode == 0 else None


def diff_signal(work_start_sha: str, repo_root: str, git_dir: str | None) -> str | None:
    """The first escalation signal the range `work_start_sha..HEAD` earns,
    or None when the diff stays inside the solo lane's contract."""
    argv = custody.git_argv(repo_root, git_dir)
    span = f"{work_start_sha}..HEAD"
    names = _git_output([*argv, "diff", _NO_RENAMES, "--name-only", span])
    if names is None:
        return CHECK_FAILED
    changed = [line.strip() for line in names.splitlines() if line.strip()]
    if any(lane.is_hook_path(p) or lane.is_production_path(p) for p in changed):
        return "unnamed_path"
    diff = _git_output([*argv, "diff", _NO_RENAMES, span])
    if diff is None:
        return CHECK_FAILED
    if lane.security_triggered(diff, changed):
        return "security_diff"
    return None


def escalate(state_path: Path, signal: str) -> dict:
    """One transaction: `lane_effective: "full"` and
    `lane_escalated: {"from": <state.lane>, "signal": <signal>}`."""

    def record(current: dict) -> dict:
        return {
            **current,
            "lane_effective": "full",
            "lane_escalated": {"from": current.get("lane"), "signal": signal},
        }

    return state.transaction(
        state_path,
        record,
        validator=lambda new: schema.validate({"lane_effective": new["lane_effective"]}),
    )
