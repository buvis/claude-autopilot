#!/usr/bin/env python3
"""enter_io.py - enter()'s git, telemetry and review-log reads.

Split out of `enter.py` to keep that module under its line ceiling (PRD
00244 / 00234). Pure side-effect helpers: a git HEAD read, a best-effort
handoff-row dispatch, and the design-gate's review-log predicate.

    git_head_sha(repo_root) -> str | None
    inside_work_tree(root) -> bool
    record_resume_row(prd, site, autopilot_dir) -> None
    review_log_has_dispatch_line(text) -> bool
    loop_committer(batch_id) -> str
    commits_all_loop(repo_root, base, committer) -> bool
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

_RECORD_DISPATCH = (
    Path(__file__).resolve().parents[2]
    / "work" / "scripts" / "record_dispatch.py"
)

_DISPATCH_RE = re.compile(
    r"dispatch \d+ \((claude|codex|claude-fallback)\): "
    r"cardinal-sin \d+, blocker \d+, non-blocker \d+, question \d+"
)


def git_head_sha(repo_root: Path) -> str | None:
    try:
        proc = subprocess.run(
            ["git", "-C", str(repo_root), "rev-parse", "HEAD"],
            capture_output=True, text=True, timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return proc.stdout.strip() if proc.returncode == 0 else None


def inside_work_tree(root: Path) -> bool:
    """True when git finds a work tree from `root`, even one whose HEAD is
    unborn. A bare-repo-backed root (no `.git` of its own, as `~/.claude`
    under a `--git-dir` repo) reads False, as does any git failure."""
    try:
        proc = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "--is-inside-work-tree"],
            capture_output=True, text=True, timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return proc.returncode == 0 and proc.stdout.strip() == "true"


def record_resume_row(prd: str, site: str, autopilot_dir: Path) -> None:
    """Best-effort handoff row via the work pack's record_dispatch.py; any
    failure goes to stderr, never past the caller. Runs in `autopilot_dir`:
    record_dispatch.py resolves the ledger from its own cwd, and this
    process's cwd need not be inside the project at all."""
    try:
        proc = subprocess.run(
            ["python3", str(_RECORD_DISPATCH), "handoff", "--site", site,
             "--edge", "resume", "--phase", "build", "--prd", prd],
            capture_output=True, text=True, timeout=10, cwd=str(autopilot_dir),
        )
    except (OSError, subprocess.SubprocessError) as err:
        print(f"autopilot: enter: resume row failed: {err}", file=sys.stderr)
        return
    if proc.returncode != 0:
        print(
            f"autopilot: enter: resume row exited {proc.returncode}: {proc.stderr.strip()}",
            file=sys.stderr,
        )


def loop_committer(batch_id: str | None) -> str:
    """The GIT_COMMITTER_NAME stamped on loop-driven commits: the batch
    id, or 'no-batch' when the loop has none."""
    return f"autopilot-loop/{batch_id or 'no-batch'}"


def commits_all_loop(repo_root: Path, base: str, committer: str) -> bool:
    """True when every commit in `base..HEAD` (merges and side commits too)
    has exactly `committer` as its committer name; an empty range is True.
    Any git failure or a name that is not valid UTF-8 is False. `base` must
    be an ancestor of HEAD -- a reset or rebase that leaves it a sibling or
    descendant makes `base..HEAD` empty (vacuously "all loop"), which would
    wrongly reuse a capsule describing commits no longer in history."""
    try:
        ancestor = subprocess.run(
            ["git", "-C", str(repo_root), "merge-base", "--is-ancestor", base, "HEAD"],
            capture_output=True, timeout=10,
        )
        if ancestor.returncode != 0:
            return False
        proc = subprocess.run(
            ["git", "-C", str(repo_root), "log", "--format=%cn", f"{base}..HEAD"],
            capture_output=True, timeout=10,
        )
        if proc.returncode != 0:
            return False
        names = proc.stdout.decode("utf-8").splitlines()
    except (OSError, subprocess.SubprocessError, UnicodeDecodeError):
        return False
    return all(name == committer for name in names)


def review_log_has_dispatch_line(text: str) -> bool:
    in_section = False
    for line in text.splitlines():
        if line.startswith("## Review log"):
            in_section = True
            continue
        if line.startswith("## "):
            in_section = False
        if in_section and _DISPATCH_RE.search(line):
            return True
    return False
