#!/usr/bin/env python3
"""store_tree.py - the dirty-tree predicate and the scoped store recorder.

`foreign_dirty` lists the dirty paths outside the autopilot store roots;
`record_store` stages and commits the store alone, leaving any other staged
path untouched.

The store is `<project root>/docs/dev/project-management`, and a bare-backed
project puts the project root below git's work-tree root (`$HOME/.claude` under
`$HOME`), so the roots `git status` prints carry a prefix git cannot report.
"""

from __future__ import annotations

import os
import subprocess
import sys
from collections.abc import Mapping
from pathlib import Path

STORE_SUBDIR = "docs/dev/project-management"
STORE_PREFIXES = (f"{STORE_SUBDIR}/", "docs/dev/tmp/")
STORE_PATHSPEC = f":(top){STORE_SUBDIR}"
# One exclude pathspec per store root, derived so a new root needs no edit here.
STORE_EXCLUDE_PATHSPECS = tuple(
    ":(exclude)" + prefix.removesuffix("/") for prefix in STORE_PREFIXES
)
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


class StoreGitError(RuntimeError):
    """A `git status` probe behind `foreign_dirty` failed."""


def run_git(args: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=True,
        timeout=GIT_TIMEOUT_SECS,
    )


def in_wave_lane(env: Mapping[str, str] | None = None) -> bool:
    """True inside a wave lane worktree, where `_AUTOPILOT_REVIEW_SLOTS_DIR`
    carries the lane's (opaque) slots directory. A mapping that was passed
    answers for itself; only `None` falls back to os.environ, read now."""
    if env is None:
        env = os.environ
    return bool(env.get("_AUTOPILOT_REVIEW_SLOTS_DIR"))


def _store_prefix(repo: Path, store_dir: Path | None) -> str:
    """The slash-terminated path from git's work-tree root down to the store's
    parent, or "" when `store_dir` is absent or is not `<x>/STORE_SUBDIR` inside
    `repo`. git resolves symlinks in `--show-toplevel`, so both sides must too."""
    if store_dir is None:
        return ""
    try:
        rel = store_dir.resolve().relative_to(repo.resolve()).as_posix()
    except (OSError, ValueError):
        return ""
    if not rel.endswith(f"/{STORE_SUBDIR}"):
        return ""
    return rel[: -len(STORE_SUBDIR)]


def _status(args: list[str], repo: Path, run_git) -> list[tuple[str, str]]:
    """(code, path) per porcelain entry, both sides of a rename or copy;
    StoreGitError when the probe itself failed."""
    try:
        out = run_git(args, cwd=repo)
    except (OSError, subprocess.SubprocessError) as err:
        stderr = getattr(err, "stderr", None)
        detail = f"{err} {stderr if isinstance(stderr, str) else ''}"
        raise StoreGitError(f"git status failed: {' '.join(detail.split())}") from err
    fields = iter(out.stdout.split("\0"))
    entries = []
    for field in fields:
        if not field:
            continue
        code, path = field[:2], field[3:]
        entries.append((code, path))
        if "R" in code or "C" in code:
            entries.append((code, next(fields)))
    return entries


def foreign_dirty(
    repo: Path, store_dir: Path | None = None, run_git=run_git
) -> list[str]:
    """Dirty paths (either side of a rename or copy) outside the store roots as
    they read from `repo`, git's work-tree root. The repository's own
    `status.showUntrackedFiles` decides which untracked paths reach us, so a
    wholly untracked store can arrive collapsed into one ancestor directory;
    such an entry is re-listed in full instead of being reported as foreign."""
    roots = tuple(_store_prefix(repo, store_dir) + root for root in STORE_PREFIXES)
    paths = []
    for code, path in _status(["status", "--porcelain", "-z"], repo, run_git):
        if path.startswith(roots):
            continue
        untracked_dir = code == "??" and path.endswith("/")
        if untracked_dir and any(root.startswith(path) for root in roots):
            probe = ["status", "--porcelain", "-z", "--untracked-files=all"]
            paths.extend(
                leaf
                for _code, leaf in _status([*probe, "--", path], repo, run_git)
                if not leaf.startswith(roots)
            )
        else:
            paths.append(path)
    return paths


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


def record_store(
    repo: Path, site: str, prd: str, store_dir: Path | None = None, run_git=run_git
) -> str | None:
    """Commit the store pathspec only; the new HEAD sha, or None when nothing
    changed or git failed (the reason on one stderr line)."""
    pathspec = f":(top){_store_prefix(repo, store_dir)}{STORE_SUBDIR}"
    message = f"chore(autopilot): record {site} state" + (f" for {prd}" if prd else "")
    try:
        run_git(["add", "--", pathspec], cwd=repo)
        staged = run_git(["diff", "--cached", "--name-only", "--", pathspec], cwd=repo)
        if not staged.stdout.strip():
            return None
        run_git(["commit", "-m", message, "--", pathspec], cwd=repo)
        return run_git(["rev-parse", "HEAD"], cwd=repo).stdout.strip()
    except (OSError, RuntimeError, subprocess.SubprocessError) as err:
        stderr = getattr(err, "stderr", None)
        reason = (stderr if isinstance(stderr, str) else None) or str(err)
        print(
            f"autopilot: store record failed: {' '.join(reason.split())}",
            file=sys.stderr,
        )
        return None
