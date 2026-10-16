#!/usr/bin/env python3
"""The one place that decides whether `verify`'s log sink may be opened.

Shared by `__main__._refuse_verify_log` (the CLI pre-flight, which prints)
and `verification._refuse_verify_log_path` (the library path, which folds the
reason into a dirty result). Pure: git and filesystem reads only, no printing.
"""

from __future__ import annotations

import os
import stat
from pathlib import Path

from cli.dirty_tree import STORE_PREFIX, _git, _log_rel_and_tracked

_OUTSIDE = "resolves outside the repository"


def refuse(log_path: Path, repo_root: Path) -> str | None:
    """The refusal reason for `log_path` as a log sink, or None when it may
    be opened. `log_path` must be the UNRESOLVED candidate: resolving it
    before this call follows any symlink in its ancestry and makes the
    symlink case unreachable. Every probe is scoped to `repo_root`, never to
    cwd. First match wins. A path that does not exist yet is eligible."""
    toplevel = _toplevel(repo_root)
    if toplevel is None:
        return _OUTSIDE  # a failing git probe fails closed
    resolved = log_path.resolve()
    identity = _identity_hit(resolved, repo_root, toplevel)
    if identity is not None:
        return identity
    # Containment comes before the symlink-component walk: a path that never
    # touches the repository at all (reached through a symlinked ancestor
    # outside it, or otherwise) must be reported as outside, not misreported
    # by whatever the component walk trips over first while climbing past
    # filesystem ancestors that have nothing to do with the repo.
    if not resolved.is_relative_to(toplevel):
        return _OUTSIDE
    probe = _log_rel_and_tracked(repo_root, log_path)
    if probe is None:
        return _OUTSIDE  # a failing tracked-probe fails closed
    if probe[1]:
        return "is tracked"
    if _symlinked_component(log_path, repo_root, toplevel):
        return "is a symlink"
    if _in_nested_repo(resolved, toplevel):
        return _OUTSIDE
    try:
        st = os.lstat(resolved)
    except OSError:
        return None  # nothing on disk to inspect yet
    if not stat.S_ISREG(st.st_mode):
        return "is not a regular file"
    if st.st_mode & 0o111:
        return "is executable"
    if st.st_nlink > 1:
        return "has more than one hard link"
    return None


def _toplevel(repo_root: Path) -> Path | None:
    """`repo_root`'s git toplevel, resolved; None when the probe fails."""
    top = _git(repo_root, "rev-parse", "--show-toplevel")
    if top.returncode != 0:
        return None
    return Path(top.stdout.strip()).resolve()


def _identity_targets(repo_root: Path) -> list[tuple[Path, str]]:
    """The directories the sink may not resolve inside, by inode identity:
    the store, and both spellings of the git directory (a worktree's own
    `--absolute-git-dir` and the shared `--git-common-dir`)."""
    targets = [(repo_root / STORE_PREFIX, "resolves inside the store")]
    for flag in ("--absolute-git-dir", "--git-common-dir"):
        probe = _git(repo_root, "rev-parse", flag)
        if probe.returncode == 0:
            # A relative answer ("--git-common-dir" gives ".git") joins onto
            # repo_root; an absolute one replaces it.
            targets.append(
                (
                    repo_root / probe.stdout.strip(),
                    "resolves inside the git directory",
                ),
            )
    return targets


def _identity_hit(resolved: Path, repo_root: Path, toplevel: Path) -> str | None:
    """The reason when ANY existing ancestor of `resolved` is one of
    `_identity_targets`. Every ancestor is checked, not just the nearest
    existing one: for `.git/hooks/pre-push.sample` the nearest is
    `.git/hooks` while the identity target is `.git` itself above it. The
    walk stops at `toplevel` (or at the filesystem root for a path that
    resolves outside it). The literal store-prefix check comes first: it
    still refuses a store path whose directory does not exist yet, which
    has no inode for the identity walk to compare against."""
    if resolved.is_relative_to((repo_root / STORE_PREFIX).resolve()):
        return "resolves inside the store"
    targets = _identity_targets(repo_root)
    pointer = _worktree_gitdir_pointer(resolved)
    if pointer is not None:
        for target, reason in targets:
            try:
                if os.path.samefile(pointer, target):
                    return reason
            except OSError:
                continue  # one of the two does not exist
    current = resolved.parent
    while True:
        for target, reason in targets:
            try:
                if os.path.samefile(current, target):
                    return reason
            except OSError:
                continue  # one of the two does not exist
        if current == toplevel or current.parent == current:
            return None
        current = current.parent


def _worktree_gitdir_pointer(resolved: Path) -> Path | None:
    """The target of a linked worktree's `.git` FILE (`gitdir: <path>`), or
    None when `resolved` is not such a file. A linked worktree's `.git` is a
    regular file, not a directory, so it never shows up as an ancestor's
    identity match for anything resolved below it -- and the file IS itself
    the candidate sink, so it must be checked directly against the identity
    targets by what it points at, not by its own (unrelated) inode."""
    try:
        if not stat.S_ISREG(os.lstat(resolved).st_mode):
            return None
        text = resolved.read_text()
    except (OSError, UnicodeDecodeError):
        return None
    if not text.startswith("gitdir:"):
        return None
    return Path(text.split(":", 1)[1].strip())


def _symlinked_component(log_path: Path, repo_root: Path, toplevel: Path) -> bool:
    """True iff any component of the UNRESOLVED `log_path` BELOW the
    repository is a symlink (the final component included). The walk stops
    at the unresolved `repo_root` as well as at the resolved `toplevel`:
    the repository's own path may carry a symlink in its ancestry (on
    macOS a repo under `/tmp` does), and that symlink is not the sink's --
    climbing past the repo root would refuse every run, the default sink
    included. Only components at or below the repo root are inspected."""
    current = log_path
    while current not in (repo_root, toplevel) and current.parent != current:
        if os.path.islink(current):
            return True
        current = current.parent
    return False


def _in_nested_repo(resolved: Path, toplevel: Path) -> bool:
    """True iff `resolved` lives in a second repository nested inside
    `toplevel`'s working tree (an ignored directory carrying its own `.git`
    and its own committed store). The probe is scoped to where the target
    actually lives, not to `repo_root`. A parent directory that does not
    exist yet cannot hold a nested repo, so its failure is not a refusal.
    Git also fails this same probe with "fatal: this operation must be run
    in a work tree" (rc 128) when invoked from inside a `.git` administrative
    directory itself -- which is exactly where `resolved.parent` lands for
    `<nested-repo>/.git/<rel>`. By the time this runs, `toplevel`'s own
    `.git` has already been ruled out by the identity check above, so that
    specific failure can only mean a DIFFERENT repo's git internals, and
    must be treated as nested rather than as "no repo here"."""
    try:
        probe = _git(resolved.parent, "rev-parse", "--show-toplevel")
    except OSError:
        return False
    if probe.returncode != 0:
        return "work tree" in probe.stderr
    return Path(probe.stdout.strip()).resolve() != toplevel
