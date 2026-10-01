#!/usr/bin/env python3
"""store_tree.py - the dirty-tree predicate and the scoped store recorder.

`foreign_dirty` lists the dirty paths outside the autopilot store roots;
`record_store` stages and commits the store alone, leaving any other staged
path untouched.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

STORE_PREFIXES = ("docs/dev/project-management/", "docs/dev/tmp/")
STORE_PATHSPEC = ":(top)docs/dev/project-management"
GIT_TIMEOUT_SECS = 30


def run_git(args: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=True,
        timeout=GIT_TIMEOUT_SECS,
    )


def foreign_dirty(repo: Path, run_git=run_git) -> list[str]:
    """Dirty paths (either side of a rename or copy) outside STORE_PREFIXES."""
    out = run_git(["status", "--porcelain", "-z", "--untracked-files=all"], cwd=repo)
    fields = iter(out.stdout.split("\0"))
    paths = []
    for field in fields:
        if not field:
            continue
        code, path = field[:2], field[3:]
        paths.append(path)
        if "R" in code or "C" in code:
            paths.append(next(fields))
    return [p for p in paths if not p.startswith(STORE_PREFIXES)]


def record_store(repo: Path, site: str, prd: str, run_git=run_git) -> str | None:
    """Commit the store pathspec only; the new HEAD sha, or None when nothing
    changed or git failed (the reason on one stderr line)."""
    message = f"chore(autopilot): record {site} state" + (f" for {prd}" if prd else "")
    try:
        run_git(["add", "--", STORE_PATHSPEC], cwd=repo)
        staged = run_git(
            ["diff", "--cached", "--name-only", "--", STORE_PATHSPEC], cwd=repo
        )
        if not staged.stdout.strip():
            return None
        run_git(["commit", "-m", message, "--", STORE_PATHSPEC], cwd=repo)
        return run_git(["rev-parse", "HEAD"], cwd=repo).stdout.strip()
    except (OSError, RuntimeError, subprocess.SubprocessError) as err:
        reason = getattr(err, "stderr", None) or str(err)
        print(
            f"autopilot: store record failed: {' '.join(reason.split())}",
            file=sys.stderr,
        )
        return None
