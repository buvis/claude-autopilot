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

STORE_GITIGNORE = "".join(
    f"{pattern}\n"
    for pattern in (
        "autopilot/state.json",
        "autopilot/state.json.bak",
        "autopilot/*.lock",
        "autopilot/.turn-counts.json",
        "autopilot/.handoff-requested",
        "autopilot/.cap-fired",
        "autopilot/.session-left",
        "autopilot/.review-gate-blocks",
        "autopilot/.review-gate-failed",
        "autopilot/.lane-guard-blocks",
        "autopilot/lanes/",
        "autopilot/wave-slots/",
        "autopilot/wave.json",
        "autopilot/review-paths",
        "autopilot/last-session.log",
        "autopilot/wrapper.log",
        "autopilot/pause-requested",
        "autopilot/paused-by-operator",
        "autopilot/park-requested",
        "autopilot/session-brief.md",
        "autopilot/contract-card.md",
        "autopilot/replan-context.md",
        "autopilot/last-verification.json",
    )
)


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


def ensure_store_gitignore(store_dir: Path) -> bool:
    """Write STORE_GITIGNORE into store_dir unless the file already holds it;
    True when it was written. A body that cannot be read counts as differing."""
    path = store_dir / ".gitignore"
    try:
        if path.read_text(encoding="utf-8") == STORE_GITIGNORE:
            return False
    except (OSError, UnicodeDecodeError):
        pass
    store_dir.mkdir(parents=True, exist_ok=True)
    path.write_text(STORE_GITIGNORE, encoding="utf-8")
    return True


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
        stderr = getattr(err, "stderr", None)
        reason = (stderr if isinstance(stderr, str) else None) or str(err)
        print(
            f"autopilot: store record failed: {' '.join(reason.split())}",
            file=sys.stderr,
        )
        return None
