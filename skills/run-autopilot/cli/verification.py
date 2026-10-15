#!/usr/bin/env python3
"""Run the project's test gate once and decide when its record can be reused.

`run_gate` is the only writer of
`docs/dev/project-management/autopilot/last-verification.json` (shape defined
in skills/work/references/final-verification.md § Recorded verification
result). `reuse_verdict` decides whether a prior record still certifies HEAD.
Both fail toward re-running the gate, never toward skipping it.

Unrelated to `cli/gate.py`'s `run_gate` (a review-file shape check).
"""

from __future__ import annotations

import fcntl
import json
import os
import posixpath
import re
import selectors
import signal
import subprocess
import time
from pathlib import Path

# Dirty paths under these roots never refuse a record: the store, plus the
# agents' scratch dir, which a repo need not gitignore.
from cli.store_tree import STORE_PREFIXES

GATE_TIMEOUT_S = 1800
GATE_OUTPUT_CAP = 2_000_000  # bytes of combined stdout+stderr kept
_LOCK_POLL_S = 0.05  # LOCK_NB poll interval while waiting for the gate lock

STORE_PREFIX = "docs/dev/project-management/"
RECORD_REL = Path(STORE_PREFIX) / "autopilot" / "last-verification.json"
GATE_LOCK_REL = Path("docs/dev/tmp") / "gate.lock"
SUMMARY_RE = re.compile(r"PASS (\d+) FAIL (\d+) SKIP (\d+) EXIT (\d+)")
_FULL_SHA_RE = re.compile(r"[0-9a-f]{40}")
_STALE: tuple[str, dict] = ("stale", {})


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


def _record_shape_ok(record: dict, gate_command: str) -> bool:
    """True iff the record has a full sha, all counts, and a green run of
    exactly `gate_command`, stamped by `_write_record` (`writer: run_gate`)."""
    if record.get("writer") != "run_gate":
        return False
    sha = record.get("sha")
    if not isinstance(sha, str) or not _FULL_SHA_RE.fullmatch(sha):
        return False
    if any(record.get(key) is None for key in ("passed", "failed", "skipped")):
        return False
    commands = record.get("commands")
    if not isinstance(commands, list) or not commands:
        return False
    if record["failed"] != 0 or not all(
        isinstance(c, dict) and c.get("exit") == 0 for c in commands
    ):
        return False
    gate = normalize_command(gate_command)
    return all(
        isinstance(c.get("command"), str) and normalize_command(c["command"]) == gate
        for c in commands
    )


def normalize_command(command: object) -> str:
    """Collapses whitespace only (str.split semantics). A non-str maps to ""."""
    if not isinstance(command, str):
        return ""
    return " ".join(command.split())


def reuse_verdict(
    record: dict | None,
    repo_root: Path,
    head_sha: str,
    gate_command: str,
) -> tuple[str, dict]:
    """
    record: the parsed contents of last-verification.json, or None if the
        file is missing/unreadable/unparseable.
    gate_command: every recorded command must equal it after both sides
        pass through `normalize_command`.
    Returns ("reused", record) only when ALL hold:
      - record["sha"] is a full lowercase hex object id (never a symbolic
        ref or abbreviation), and passed/failed/skipped are all present and
        not None
      - the run was green: failed is 0 and record["commands"] is a non-empty
        list whose every entry is a dict that exited 0
      - `git merge-base --is-ancestor <record["sha"]> <head_sha>` exits 0,
        rejecting a sibling or descendant surviving a reset/rebase
      - every path in `git diff --name-only --no-renames -z <record["sha"]>
        <head_sha>` (cwd=repo_root) starts with
        "docs/dev/project-management/" (an empty diff also counts,
        vacuously)
      - `git status --porcelain=1 -z --untracked-files=all` (cwd=repo_root)
        reports no dirty path outside the store tree, since
        gather-context.sh's diff is against the working tree, not just HEAD
      - a dirty or untracked docs/dev/project-management/ path is tolerated
      - a rename or copy is judged by both of its endpoint paths, so a move
        out of the store tree counts as dirty
      - no tracked symlink outside the store resolves to a store path the
        diff or the dirty scan touched, committed or uncommitted -- a
        directory-level alias (even one normalizing to ".", the repo root)
        counts too, since it covers every store path beneath it
    Returns ("stale", {}) otherwise, including when any git call itself
    fails (missing sha, unknown ref, non-git repo, non-zero exit on the
    ancestor check): fail toward re-running the gate, never toward
    skipping it. The symlink-alias check above actually runs inside
    `_ancestor_and_clean`, which this function calls, not in this function
    itself.
    """
    if not isinstance(record, dict) or not _record_shape_ok(record, gate_command):
        return _STALE
    try:
        if not _ancestor_and_clean(repo_root, record["sha"], head_sha):
            return _STALE
    except OSError:
        return _STALE
    return ("reused", record)


def _write_record(
    cwd: Path,
    command: str,
    sha: str,
    cycle: int | None,
    result: dict,
) -> None:
    path = cwd / RECORD_REL
    path.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "sha": sha,
        "cycle": cycle,
        "writer": "run_gate",
        "commands": [{"command": normalize_command(command), "exit": result["exit"]}],
        "passed": result["passed"],
        "failed": result["failed"],
        "skipped": result["skipped"],
    }
    path.write_text(json.dumps(record, indent=2) + "\n")


def _drain_bounded(
    proc: subprocess.Popen,
    cap: int,
    deadline: float,
    sink=None,
) -> tuple[bytes, bool]:
    """Drains stdout and stderr against `deadline`, keeping only the last
    `cap` bytes of stdout (dropping from the front, never the back) and
    discarding stderr after reading it (so its pipe can never fill and
    block the child). When `sink` is given, every chunk read from either
    pipe is written to it immediately, in read order, in addition to the
    bounded in-memory retention above (memory stays bounded exactly as
    before; only the parse tail is kept in memory). Returns
    (stdout_tail, done) where `done` is True iff the child exited and both
    pipes reached EOF before the deadline."""
    sel = selectors.DefaultSelector()
    sel.register(proc.stdout, selectors.EVENT_READ)
    sel.register(proc.stderr, selectors.EVENT_READ)
    open_fds = {proc.stdout, proc.stderr}
    stdout_buf = b""
    while open_fds and time.monotonic() < deadline:
        for key, _ in sel.select(timeout=min(deadline - time.monotonic(), 1.0)):
            fobj = key.fileobj
            chunk = os.read(fobj.fileno(), 65536)
            if not chunk:
                sel.unregister(fobj)
                open_fds.discard(fobj)
                continue
            if sink is not None:
                sink.write(chunk)
            if fobj is proc.stdout:
                stdout_buf = (stdout_buf + chunk)[-cap:]
    sel.close()
    return stdout_buf, not open_fds


def _timed_out_result() -> dict:
    """The all-None result of a gate killed at its deadline."""
    return {
        "passed": None,
        "failed": None,
        "skipped": None,
        "exit": None,
        "raw_line": None,
        "timed_out": True,
        "recorded": False,
        "dirty": False,
        "dirty_paths": [],
        "lock_timeout": False,
        "head_moved": False,
    }


def _lock_timeout_result() -> dict:
    """The flock was never acquired by the deadline. No gate spawned, so
    `timed_out` stays False (it means a gate killed at its deadline);
    `lock_timeout` names this cause."""
    return {
        "passed": None,
        "failed": None,
        "skipped": None,
        "exit": None,
        "raw_line": None,
        "timed_out": False,
        "recorded": False,
        "dirty": False,
        "dirty_paths": [],
        "lock_timeout": True,
        "head_moved": False,
    }


def _head_moved_result() -> dict:
    """HEAD no longer equals `sha` once the lock is held. Not a `dirty`
    result: the tree can be clean while HEAD itself moved."""
    return {
        "passed": None,
        "failed": None,
        "skipped": None,
        "exit": None,
        "raw_line": None,
        "timed_out": False,
        "recorded": False,
        "dirty": False,
        "dirty_paths": [],
        "lock_timeout": False,
        "head_moved": True,
    }


def _dirty_result(dirty_paths: list[str]) -> dict:
    """The refusal shape for a dirty-tree check, pre-spawn or post-reap.
    `timed_out` is explicitly False here, never inherited from
    `_timed_out_result()`, because `run_gate_line` branches on `timed_out`
    first to build its human-readable Tests line and a dirty tree is not a
    timeout."""
    return {
        "passed": None,
        "failed": None,
        "skipped": None,
        "exit": None,
        "raw_line": None,
        "timed_out": False,
        "recorded": False,
        "dirty": True,
        "dirty_paths": dirty_paths,
        "lock_timeout": False,
        "head_moved": False,
    }


def _reap(proc: subprocess.Popen, deadline: float, drained: bool) -> bool:
    """Bounds the child's EXIT, not only its output: waits for `proc` until
    `deadline` when both pipes reached EOF, else kills its process group (a
    grandchild can outlive the shell while holding the pipes open) and
    reaps it. Closes both pipes either way. Returns True iff the child
    exited on its own, before the deadline, with its output fully drained."""
    exited = False
    if drained:
        try:
            proc.wait(timeout=max(0.0, deadline - time.monotonic()))
            exited = True
        except subprocess.TimeoutExpired:
            pass
    if not exited:
        os.killpg(proc.pid, signal.SIGKILL)
        proc.wait()
    proc.stdout.close()
    proc.stderr.close()
    return exited


def _parse_summary(stdout_buf: bytes) -> tuple[str | None, re.Match | None]:
    """The LAST SUMMARY_RE match in `stdout_buf` -- a command that prints the
    pattern twice (a retry) is read as its final, superseding line."""
    raw_line, found = None, None
    for line in stdout_buf.decode("utf-8", errors="ignore").splitlines():
        hit = SUMMARY_RE.search(line)
        if hit:
            raw_line, found = line, hit
    return raw_line, found


def _record_gate(
    command: str,
    cwd: Path,
    sha: str,
    cycle: int | None,
    returncode: int,
    stdout_buf: bytes,
    extra_excluded: tuple[str, ...],
) -> dict:
    """The post-reap half of `run_gate`: parse the summary, re-check the tree,
    and write the record only when a summary parsed and the tree is clean."""
    raw_line, found = _parse_summary(stdout_buf)
    dirty, dirty_paths = _dirty_check(cwd, extra_excluded)
    result = {
        "passed": int(found.group(1)) if found else None,
        "failed": int(found.group(2)) if found else None,
        "skipped": int(found.group(3)) if found else None,
        "exit": returncode,
        "raw_line": raw_line,
        "timed_out": False,
        "recorded": False,
        "dirty": dirty,
        "dirty_paths": dirty_paths,
        "lock_timeout": False,
        "head_moved": False,
    }
    if found and not dirty:
        _write_record(cwd, command, sha, cycle, result)
        result["recorded"] = True
    return result


def _acquire_lock(lock_fd: int, deadline: float) -> bool:
    """Polls a non-blocking exclusive flock on `lock_fd` until it succeeds
    or `deadline` passes. Returns False on expiry, with the lock NOT held
    (nothing to release)."""
    while True:
        try:
            fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            return True
        except OSError:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return False
            time.sleep(min(_LOCK_POLL_S, remaining))


_HEAD_MOVED = object()


def _lock_and_check(
    cwd: Path, sha: str, log_path: Path | None
) -> tuple[tuple[str, ...], dict | object | None]:
    """The preamble of `run_gate`, called with the flock already held:
    refuse when the tree is dirty or HEAD no longer equals `sha`. Returns
    the log exclusion and the `_dirty_result` refusal, the `_HEAD_MOVED`
    sentinel, or None to proceed."""
    extra_excluded = _untracked_log_exclusion(cwd, log_path)
    dirty, dirty_paths = _dirty_check(cwd, extra_excluded)
    if dirty:
        return extra_excluded, _dirty_result(dirty_paths)
    head = _git(cwd, "rev-parse", "HEAD")
    if head.returncode != 0 or head.stdout.strip() != sha:
        return extra_excluded, _HEAD_MOVED
    return extra_excluded, None


def _run_locked_gate(
    command: str,
    cwd: Path,
    sha: str,
    cycle: int | None,
    deadline: float,
    log_path: Path | None,
    extra_excluded: tuple[str, ...],
    lock_fd: int,
) -> dict:
    """The spawn half of `run_gate`, called with the flock held: open the log,
    delete any record, spawn, drain, reap and record against the same
    `deadline` the lock wait was bounded by. Closes the log in its own
    `finally`, before `run_gate`'s `finally` releases the lock.

    The gate inherits `lock_fd` (`pass_fds`), so the flock stays held by
    the gate's own process group if this process dies: a SIGKILLed verify
    cannot be handled, and this inheritance alone keeps the next verify
    waiting until the orphaned gate exits. Do not add a SIGKILL "handler".
    SIGTERM, or any other exception during drain/reap, kills the gate's
    process group and re-raises."""
    log_file = None
    try:
        if log_path is not None:
            log_path.parent.mkdir(parents=True, exist_ok=True)
            log_file = open(log_path, "wb", buffering=0)
        (cwd / RECORD_REL).unlink(missing_ok=True)

        def _raise_on_sigterm(signum, frame):
            raise RuntimeError("verify: SIGTERM during gate")

        old_handler = signal.getsignal(signal.SIGTERM)
        signal.signal(signal.SIGTERM, _raise_on_sigterm)
        try:
            proc = subprocess.Popen(
                command,
                shell=True,
                cwd=cwd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                start_new_session=True,
                pass_fds=(lock_fd,),
            )
            try:
                stdout_buf, done = _drain_bounded(
                    proc, GATE_OUTPUT_CAP, deadline, log_file
                )
                exited = _reap(proc, deadline, done)
            except BaseException:
                # A log-sink write error, SIGTERM, or an interrupt: kill and
                # reap the gate, then re-raise. The group may already be
                # gone, which raises ProcessLookupError and must not mask
                # the error this block exists to propagate.
                try:
                    os.killpg(proc.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                proc.wait()
                proc.stdout.close()
                proc.stderr.close()
                raise
        finally:
            signal.signal(signal.SIGTERM, old_handler)
        if not exited:
            return _timed_out_result()
        return _record_gate(
            command, cwd, sha, cycle, proc.returncode, stdout_buf, extra_excluded
        )
    finally:
        if log_file is not None:
            log_file.close()


def run_gate(
    command: str,
    cwd: Path,
    sha: str,
    cycle: int | None,
    timeout: float = GATE_TIMEOUT_S,
    log_path: Path | None = None,
) -> dict:
    """
    Runs `command` via Popen(shell=True), draining stdout/stderr in bounded
    chunks against a wall-clock deadline that bounds the child's exit too.
    On expiry: kill the process group, return `_timed_out_result()` and
    write NOTHING. `run_gate` is the only writer of last-verification.json
    (shape: `_write_record`); it checks `_dirty_outside_store(cwd)` before
    spawning the child AND again after `_reap` returns, and writes the
    record only when both checks are clean AND a summary line parsed. A
    dirty-tree refusal (`_dirty_result()`) is never recorded. When
    `log_path` is given, every byte of stdout and stderr is streamed to it,
    in read order, in addition to the bounded in-memory parse tail.

    `deadline = time.monotonic() + timeout` is computed once, before the
    lock is even requested, and governs BOTH the wait for the exclusive
    flock on `cwd / GATE_LOCK_REL` (polled with `LOCK_NB`, never a blocking
    `LOCK_EX`) and, once acquired, the spawn/drain/reap below -- so a
    caller's `timeout` is the whole wall-clock budget, not the budget for
    each half separately. Expiry while still waiting for the lock returns
    `_lock_timeout_result()` with the lock never taken, released in the
    closing `finally` as a no-op. Once the lock is held: the pre-spawn
    dirty check; then a re-check that `git rev-parse HEAD` still equals
    `sha` (a mismatch or git failure returns `_head_moved_result()`, the
    gate never runs); then `run_gate` opens `log_path` itself (creating parent
    directories first) and deletes any existing record before spawning the
    child, so a run that fails, times out or dirties the tree leaves no
    older record behind. A failure to open the log or delete the record
    raises the bare OSError rather than being caught here. Neither refusal
    opens the log or deletes the record.
    """
    lock_path = cwd / GATE_LOCK_REL
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    lock_fd = os.open(lock_path, os.O_RDWR | os.O_CREAT)
    deadline = time.monotonic() + timeout
    try:
        if not _acquire_lock(lock_fd, deadline):
            return _lock_timeout_result()
        extra_excluded, refusal = _lock_and_check(cwd, sha, log_path)
        if refusal is _HEAD_MOVED:
            return _head_moved_result()
        if refusal is not None:
            return refusal
        return _run_locked_gate(
            command, cwd, sha, cycle, deadline, log_path, extra_excluded, lock_fd
        )
    finally:
        fcntl.flock(lock_fd, fcntl.LOCK_UN)
        os.close(lock_fd)
