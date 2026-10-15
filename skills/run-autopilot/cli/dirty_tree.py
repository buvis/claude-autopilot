#!/usr/bin/env python3
"""Working-tree dirt checks shared by `verification.py`: everything that
decides whether a repo's state outside the project-management store counts
as dirty, for both the pre-spawn/post-reap gate checks and `reuse_verdict`'s
ancestor-and-clean check.

Split out of `verification.py` to keep that file under the project's
800-line limit (PRD 00311 review R3); the split is purely mechanical, no
behavior changed. `verification.py` imports every public name here directly,
so `verification._dirty_path_is_in_store` and friends keep working for
existing callers and tests.
"""

from __future__ import annotations

import posixpath
import subprocess
from pathlib import Path

# Dirty paths under these roots never refuse a record: the store, plus the
# agents' scratch dir, which a repo need not gitignore.
from cli.store_tree import STORE_PREFIXES

STORE_PREFIX = "docs/dev/project-management/"


def _git(repo_root: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )


def _dirty_path_is_in_store(
    new_path: str,
    old_path: str | None,
    store: str | tuple[str, ...],
) -> bool:
    """A porcelain -z status record's store check: the path field
    (and the second, source path field when the record is a rename/copy)
    must both be under `store`, or the record counts as dirty outside
    the store. A rename or copy is judged by both its destination and
    source path -- crossing the store boundary in either direction, on
    either path, is dirty."""
    paths = (new_path, old_path) if old_path else (new_path,)
    return all(p.startswith(store) for p in paths)


def _iter_porcelain_z_records(raw: str) -> list[tuple[str, str | None]]:
    """Splits `git status --porcelain=1 -z` output into (path, source_path)
    pairs. XY is always two status-code bytes (either may be blank); a
    rename/copy record (R or C in EITHER column) carries a second,
    NUL-terminated source-path field."""
    fields = raw.split("\0")
    records = []
    i = 0
    while i < len(fields) and fields[i]:
        field = fields[i]
        code, path = field[:2], field[3:]
        if code[0] in "RC" or code[1] in "RC":
            i += 1
            records.append((path, fields[i]))
        else:
            records.append((path, None))
        i += 1
    return records


def _ancestor_and_clean(repo_root: Path, sha: str, head_sha: str) -> bool:
    """Unchanged ancestor check and status check. The change list source
    is `git diff --name-only --no-renames -z <sha> <head_sha>` split on NUL
    (replacing the `git log` call, which is silent for a merge commit's own
    resolution edits - `git diff` between the two endpoints is not). The
    status/store-filter part is shared with `_dirty_outside_store`."""
    if _git(repo_root, "merge-base", "--is-ancestor", sha, head_sha).returncode != 0:
        return False
    # Git paths are toplevel-relative; repo_root may sit below the toplevel.
    prefix = _git(repo_root, "rev-parse", "--show-prefix")
    if prefix.returncode != 0:
        return False
    store = prefix.stdout.strip() + STORE_PREFIX
    diff = _git(repo_root, "diff", "--name-only", "--no-renames", "-z", sha, head_sha)
    if diff.returncode != 0:
        return False
    paths = [p for p in diff.stdout.split("\0") if p]
    if not all(path.startswith(store) for path in paths):
        return False
    if _store_symlink_targets_changed(repo_root, paths):
        return False
    if _store_symlink_targets_changed(repo_root, _dirty_store_paths(repo_root)):
        return False
    return not _dirty_outside_store(repo_root)


class _GitProbeFailed(OSError):
    """A git call in the dirt probe exited non-zero (non-git cwd and the
    like); an OSError so `_dirty_outside_store` counts it as dirty."""


def _store_roots(repo_root: Path) -> tuple[str, ...]:
    """Toplevel-relative store roots: `git rev-parse --show-prefix` joined
    with each of STORE_PREFIXES. Raises `_GitProbeFailed` on a git failure."""
    prefix = _git(repo_root, "rev-parse", "--show-prefix")
    if prefix.returncode != 0:
        raise _GitProbeFailed("git rev-parse --show-prefix failed")
    return tuple(prefix.stdout.strip() + root for root in STORE_PREFIXES)


def _dirty_store_paths(repo_root: Path) -> list[str]:
    """Toplevel-relative paths of every porcelain status record path that
    lies under the store roots (the inverse of `_dirty_outside_store_paths`);
    a rename/copy contributes each of its paths that is in the store.
    Raises `_GitProbeFailed` on a git failure."""
    store = _store_roots(repo_root)
    status = _git(repo_root, "status", "--porcelain=1", "-z", "--untracked-files=all")
    if status.returncode != 0:
        raise _GitProbeFailed("git status failed")
    return [
        p
        for new, old in _iter_porcelain_z_records(status.stdout)
        for p in (new, old)
        if p and _dirty_path_is_in_store(p, None, store)
    ]


def _store_symlink_targets_changed(repo_root: Path, store_paths: list[str]) -> bool:
    """True iff a tracked symlink outside the store, its blob target resolved
    against the link's own directory, names one of `store_paths` (all
    toplevel-relative) or a directory above one. Absolute targets and
    symlink chains are taken at face value. Raises `_GitProbeFailed` on a
    git failure."""
    if not store_paths:
        return False
    store = _store_roots(repo_root)
    listing = _git(repo_root, "ls-files", "-s", "-z", "--full-name")
    if listing.returncode != 0:
        raise _GitProbeFailed("git ls-files failed")
    for entry in listing.stdout.split("\0"):
        if not entry:
            continue
        meta, link = entry.split("\t", 1)
        mode, blob, _stage = meta.split()
        if mode != "120000" or link.startswith(store):
            continue
        raw = _git(repo_root, "cat-file", "-p", blob)
        if raw.returncode != 0:
            raise _GitProbeFailed("git cat-file failed")
        target = posixpath.normpath(posixpath.join(posixpath.dirname(link), raw.stdout))
        # "." is the repo root: every repo-relative store path is beneath it,
        # but none of them literally starts with "./", so it needs its own
        # branch rather than falling through to the startswith check below.
        if target == "." or any(
            p == target or p.startswith(target + "/") for p in store_paths
        ):
            return True
    return False


def _dirty_outside_store_paths(
    repo_root: Path,
    extra_excluded: tuple[str, ...] = (),
) -> list[str]:
    """Sorted, deduplicated paths of every porcelain status record outside
    the store roots, [] when clean. Store roots come from `_store_roots`
    (`prefix + p for p in STORE_PREFIXES`, `prefix` from `git rev-parse
    --show-prefix`); `extra_excluded` holds TOPLEVEL-relative POSIX file
    paths, used as given (not re-joined with prefix) and matched exactly,
    never as prefixes. Runs `git status --porcelain=1 -z
    --untracked-files=all` and reuses `_iter_porcelain_z_records` and
    `_dirty_path_is_in_store`; a rename/copy record contributes both of its
    paths. Catches nothing: a failing git call raises `_GitProbeFailed`
    (an OSError), never `[]`."""
    store = _store_roots(repo_root)
    status = _git(repo_root, "status", "--porcelain=1", "-z", "--untracked-files=all")
    if status.returncode != 0:
        raise _GitProbeFailed("git status failed")
    offending = set()
    for new, old in _iter_porcelain_z_records(status.stdout):
        # extra_excluded holds exact file paths: match by equality, never
        # by prefix, so "my-own.log.bak" is not excused by "my-own.log".
        excused = all(p in extra_excluded for p in (new, old) if p)
        if not excused and not _dirty_path_is_in_store(new, old, store):
            offending.update(p for p in (new, old) if p)
    offending.update(_hidden_flag_edits(repo_root, store))
    return sorted(offending)


def _hidden_flag_edits(repo_root: Path, store: tuple[str, ...]) -> list[str]:
    """Toplevel-relative paths outside `store` whose index entry carries the
    skip-worktree or assume-unchanged flag. Either flag alone is dirt: both
    hide the path from `git status`, so its on-disk content can never be
    trusted to still match the index blob -- there is no safe way to tell
    an unedited flagged file from an edited one without the gate itself
    reading stale bytes. Raises `_GitProbeFailed` when a git call fails."""
    top = _git(repo_root, "rev-parse", "--show-toplevel")
    if top.returncode != 0:
        raise _GitProbeFailed("git rev-parse --show-toplevel failed")
    toplevel = Path(top.stdout.strip())
    listing = _git(toplevel, "ls-files", "-v", "-s", "-z")
    if listing.returncode != 0:
        raise _GitProbeFailed("git ls-files failed")
    flagged = []
    for entry in listing.stdout.split("\0"):
        if not entry:
            continue
        meta, path = entry.split("\t", 1)
        tag, _mode, _blob, _stage = meta.split()
        # "S" is skip-worktree; a lowercase tag is assume-unchanged.
        if (tag == "S" or tag.islower()) and not path.startswith(store):
            flagged.append(path)
    return flagged


def _dirty_outside_store(
    repo_root: Path,
    extra_excluded: tuple[str, ...] = (),
) -> bool:
    """True iff the working tree has any change outside the store roots
    (see `_dirty_outside_store_paths`), or the git calls themselves fail
    (non-git cwd, any OSError/non-zero exit counts as dirty - fail toward
    refusing the record)."""
    try:
        return bool(_dirty_outside_store_paths(repo_root, extra_excluded))
    except OSError:
        return True


def _dirty_check(cwd: Path, extra_excluded: tuple[str, ...]) -> tuple[bool, list[str]]:
    """(dirty, dirty_paths) for `run_gate`'s result. A failing git probe is
    dirty with no path to list."""
    try:
        paths = _dirty_outside_store_paths(cwd, extra_excluded)
    except OSError:
        return True, []
    return bool(paths), paths


def _log_rel_and_tracked(cwd: Path, log_path: Path | None) -> tuple[str, bool] | None:
    """(toplevel-relative POSIX path of `log_path`, whether it is tracked
    there), when `log_path` resolves inside cwd's git toplevel; None when
    there is no log, it resolves outside the toplevel, or any git call
    fails. The single probe both `_untracked_log_exclusion` callers used to
    run separately."""
    if log_path is None:
        return None
    try:
        top = _git(cwd, "rev-parse", "--show-toplevel")
        if top.returncode != 0:
            return None
        toplevel = Path(top.stdout.strip())
        rel = log_path.resolve().relative_to(toplevel.resolve()).as_posix()
        tracked = _git(toplevel, "ls-files", "--error-unmatch", "--", rel)
    except (OSError, ValueError):
        return None
    return rel, tracked.returncode == 0


def _untracked_log_exclusion(cwd: Path, log_path: Path | None) -> tuple[str, ...]:
    """`(toplevel-relative POSIX path of log_path,)` when the log resolves
    inside cwd's git toplevel and is NOT tracked there; `()` otherwise
    (no log, log outside the toplevel, log tracked, or any git failure).
    A tracked log is never excused: its edits stay dirt."""
    resolved = _log_rel_and_tracked(cwd, log_path)
    if resolved is None:
        return ()
    rel, tracked = resolved
    return () if tracked else (rel,)
