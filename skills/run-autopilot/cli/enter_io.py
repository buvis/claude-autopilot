#!/usr/bin/env python3
"""enter_io.py - enter()'s git, telemetry and review-log reads.

Split out of `enter.py` to keep that module under its line ceiling (PRD
00244 / 00234). Pure side-effect helpers: a git HEAD read, a best-effort
handoff-row dispatch, and the design-gate's review-log predicate.

    git_head_sha(repo_root) -> str | None
    record_resume_row(prd, site, autopilot_dir) -> None
    review_log_has_dispatch_line(text) -> bool
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
