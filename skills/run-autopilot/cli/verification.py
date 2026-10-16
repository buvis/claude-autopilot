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
import re
import selectors
import signal
import subprocess
import threading
import time
from contextlib import contextmanager
from pathlib import Path

from cli import log_sink_refusal

# The dirty-tree and git-probe helpers live in `dirty_tree.py` (PRD 00311
# review R3, split to keep this file under the 800-line limit); importing
# them here keeps `verification._dirty_path_is_in_store` and friends working
# for existing callers and tests.
from cli.dirty_tree import (
    STORE_PREFIX,
    _ancestor_and_clean,
    _dirty_check,
    _dirty_outside_store,
    _dirty_path_is_in_store,
    _dirty_store_paths,
    _dirty_outside_store_paths,
    _git,
    _GitProbeFailed,
    _hidden_flag_edits,
    _iter_porcelain_z_records,
    _log_rel_and_tracked,
    _store_roots,
    _store_symlink_targets_changed,
    _untracked_log_exclusion,
)

GATE_TIMEOUT_S = 1800
GATE_LOCK_TIMEOUT_S = 600  # the lock wait's own budget, separate from the gate's
GATE_OUTPUT_CAP = 2_000_000  # bytes of combined stdout+stderr kept
_LOCK_POLL_S = 0.05  # LOCK_NB poll interval while waiting for the gate lock

RECORD_REL = Path(STORE_PREFIX) / "autopilot" / "last-verification.json"
GATE_LOCK_REL = Path("docs/dev/tmp") / "gate.lock"
SUMMARY_RE = re.compile(r"PASS (\d+) FAIL (\d+) SKIP (\d+) EXIT (\d+)")
_FULL_SHA_RE = re.compile(r"[0-9a-f]{40}")
_STALE: tuple[str, dict] = ("stale", {})


def _record_shape_ok(record: dict, gate_command: str) -> bool:
    """True iff the record has a full sha, all counts, and a green run of
    exactly `gate_command`, stamped by `_write_record` (`writer: run_gate`).
    `record["failed"]` alone carries the summary line's own EXIT token too:
    `_write_record` folds a non-zero EXIT token into `failed` before writing,
    so a summary of `FAIL 0 ... EXIT 1` is stored as failed, and this check
    needs nothing beyond the existing `failed != 0` test to refuse it, even
    though the gate process itself exited 0 and the true parsed failure
    count (returned to the caller for the Tests line) stayed 0."""
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
    summary_exit: int | None,
) -> None:
    """Writes the record with the usual shape (no extra key): a non-zero
    `summary_exit` (the summary line's own EXIT token, never returned to
    `run_gate`'s caller) is folded into the persisted `failed` count here,
    forcing it non-zero so `_record_shape_ok` refuses the record on reuse
    exactly as it already does for a parsed failure -- without changing the
    true parsed `failed` the caller gets back in `result`."""
    path = cwd / RECORD_REL
    path.parent.mkdir(parents=True, exist_ok=True)
    persisted_failed = result["failed"]
    if summary_exit not in (0, None):
        persisted_failed = max(persisted_failed or 0, 1)
    record = {
        "sha": sha,
        "cycle": cycle,
        "writer": "run_gate",
        "commands": [{"command": normalize_command(command), "exit": result["exit"]}],
        "passed": result["passed"],
        "failed": persisted_failed,
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


def _timed_out_result(waited_s: float) -> dict:
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
        "waited_s": waited_s,
    }


def _lock_timeout_result(waited_s: float) -> dict:
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
        "waited_s": waited_s,
    }


def _head_moved_result(waited_s: float) -> dict:
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
        "waited_s": waited_s,
    }


def _dirty_result(dirty_paths: list[str], waited_s: float) -> dict:
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
        "waited_s": waited_s,
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
    # The summary line's own EXIT token: never surfaced to the caller (only
    # the real process `returncode` is, as `exit`), used solely to fold a
    # dropped failure into the persisted record below.
    summary_exit = int(found.group(4)) if found else None
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
        _write_record(cwd, command, sha, cycle, result, summary_exit)
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


def _refuse_verify_log_path(cwd: Path, log_path: Path | None) -> str | None:
    """The `_lock_and_check`-side mirror of `__main__._refuse_verify_log`,
    for the library entry point (`run_gate` called directly, bypassing the
    CLI). None when there is no log or it is safe; else the refusal reason.
    `cwd` IS the repo root by `run_gate`'s existing contract."""
    if log_path is None:
        return None
    return log_sink_refusal.refuse(log_path, cwd)


def _lock_and_check(
    cwd: Path,
    sha: str,
    log_path: Path | None,
    waited_s: float,
) -> tuple[tuple[str, ...], dict | object | None]:
    """The preamble of `run_gate`, called with the flock already held:
    refuse when the log sink is unsafe (`_refuse_verify_log_path`, checked
    first so no gate is ever spawned toward it), when the tree is dirty, or
    when HEAD no longer equals `sha`. Returns the log exclusion and the
    `_dirty_result` refusal, the `_HEAD_MOVED` sentinel, or None to
    proceed."""
    extra_excluded = _untracked_log_exclusion(cwd, log_path)
    if _refuse_verify_log_path(cwd, log_path) is not None:
        resolved = _log_rel_and_tracked(cwd, log_path)
        rel = resolved[0] if resolved is not None else str(log_path)
        return extra_excluded, _dirty_result([rel], waited_s)
    dirty, dirty_paths = _dirty_check(cwd, extra_excluded)
    if dirty:
        return extra_excluded, _dirty_result(dirty_paths, waited_s)
    head = _git(cwd, "rev-parse", "HEAD")
    if head.returncode != 0 or head.stdout.strip() != sha:
        return extra_excluded, _HEAD_MOVED
    return extra_excluded, None


def _pinned_parent_fd(parent: Path, root: Path) -> int:
    """A descriptor for `parent`, opened without following a symlink at any
    level below `root`.

    The descent starts at `root` and takes every component beneath it one
    at a time with `O_DIRECTORY | O_NOFOLLOW`, so a symlink standing in
    for any of them fails that level's open with ELOOP/ENOTDIR instead of
    being followed. Anchoring at the deepest ancestor that lstats as a
    directory would not do: `O_NOFOLLOW` guards only the final component
    of the path it is given, leaving every level above the anchor followed
    silently, and the lstat-then-open pair is itself the
    time-of-check/time-of-use gap this chain exists to close.

    `root` is where the strictness starts, not where it ends: the repo's
    OWN path is trusted (a checkout reached through a symlinked ancestor,
    e.g. a repo under macOS `/tmp`, is normal and must not be refused),
    while everything the caller could be tricked about lives below it."""
    try:
        names = parent.relative_to(root).parts
    except ValueError as exc:
        # A lexical mismatch, not a filesystem fault: the caller spelled the
        # sink through a different root than it passed (`/tmp/x` vs
        # `/private/tmp/x`). Raised as OSError so the caller's handling of a
        # refused sink covers it, and before `root` is opened so no fd leaks.
        raise OSError(f"{parent} is not under {root}") from exc
    parent_fd = os.open(root, os.O_DIRECTORY)
    for name in names:
        try:
            parent_fd = _descend(parent_fd, name)
        except OSError:
            os.close(parent_fd)
            raise
    return parent_fd


def _descend(parent_fd: int, name: str) -> int:
    """`name`'s directory descriptor, opened relative to `parent_fd` and
    created there first when it is missing (an existing component is not
    an error; a symlinked one fails the reopen, which is the refusal).
    Closes `parent_fd` once the new descriptor replaces it, and leaves it
    open for the caller to close when either step raises."""
    try:
        os.mkdir(name, dir_fd=parent_fd)
    except FileExistsError:
        pass
    next_fd = os.open(name, os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent_fd)
    os.close(parent_fd)
    return next_fd


def _open_log_sink(log_path: Path, root: Path):
    """Opens `log_path` for a fresh write without following a symlink at
    any level below `root` (`log_path`'s own parent chain included).

    The leaf is unlinked (safe: the refusal check already proved an
    existing leaf untracked, non-symlink, single-link, regular and
    non-executable) and recreated with `O_EXCL | O_NOFOLLOW` relative to a
    descriptor pinned by `_pinned_parent_fd`, so a later symlink swap of
    the PATHNAME cannot redirect the open either. `root` is the repo
    root; every caller has one and must pass it."""
    parent_fd = _pinned_parent_fd(log_path.parent, root)
    try:
        try:
            os.unlink(log_path.name, dir_fd=parent_fd)
        except FileNotFoundError:
            pass
        # 0o666 is what builtin `open` passes; os.open's own default is
        # 0o777, which would leave the sink executable and make the NEXT
        # run refuse its own log.
        sink_fd = os.open(
            log_path.name,
            os.O_CREAT | os.O_WRONLY | os.O_EXCL | os.O_NOFOLLOW,
            0o666,
            dir_fd=parent_fd,
        )
    finally:
        os.close(parent_fd)
    return os.fdopen(sink_fd, "wb", buffering=0)


def _run_locked_gate(
    command: str,
    cwd: Path,
    sha: str,
    cycle: int | None,
    deadline: float,
    log_path: Path | None,
    extra_excluded: tuple[str, ...],
    lock_fd: int,
    waited_s: float,
) -> dict:
    """The spawn half of `run_gate`, called with the flock held: open the log,
    delete any record, spawn, drain, reap and record against the gate's own
    `deadline`, computed once the lock was acquired. Closes the log in its
    own `finally`, before `run_gate`'s `finally` releases the lock."""
    log_file = None
    try:
        if log_path is not None:
            log_file = _open_log_sink(log_path, cwd)
        (cwd / RECORD_REL).unlink(missing_ok=True)
        returncode, stdout_buf, exited = _spawn_gate(
            command,
            cwd,
            deadline,
            log_file,
            lock_fd,
        )
        if not exited:
            return _timed_out_result(waited_s)
        recorded = _record_gate(
            command,
            cwd,
            sha,
            cycle,
            returncode,
            stdout_buf,
            extra_excluded,
        )
        return {**recorded, "waited_s": waited_s}
    finally:
        if log_file is not None:
            log_file.close()


def _signal_error(signum: int) -> RuntimeError:
    """The error a guarded signal turns into, named after the signal."""
    return RuntimeError(f"verify: {signal.Signals(signum).name} during gate")


class _SignalGuard:
    """Tracks whether the gate has started, the first signal that arrived
    while raising was unsafe, and whether cleanup has begun. `handle` is
    the installed signal handler: before the gate starts, or once cleanup
    has begun, it only records `pending_signum`; otherwise it marks
    cleanup as begun and raises directly (a signal during drain/reap).
    `raise_if_pending` turns a signal deferred during spawn into the same
    error, called right after the gate starts."""

    def __init__(self) -> None:
        self.gate_started: bool = False
        self.pending_signum: int | None = None
        self.cleaning: bool = False

    def handle(self, signum: int, frame) -> None:
        if not self.gate_started or self.cleaning:
            if self.pending_signum is None:
                self.pending_signum = signum
            return
        self.cleaning = True
        raise _signal_error(signum)

    def raise_if_pending(self) -> None:
        if self.pending_signum is not None and not self.cleaning:
            self.cleaning = True
            raise _signal_error(self.pending_signum)


@contextmanager
def _deferred_signals(signums: tuple[int, ...]):
    """Installs `_SignalGuard.handle` as the handler for every signal in
    `signums` for the caller's protected region, restoring each previous
    handler on exit. The signals are not blocked around `Popen`: the gate
    would inherit the blocked mask. A no-op off the main thread, where
    `signal.signal` cannot install a handler at all."""
    guard = _SignalGuard()
    old_handlers = {}
    if threading.current_thread() is threading.main_thread():
        for signum in signums:
            old_handlers[signum] = signal.signal(signum, guard.handle)
    try:
        yield guard
    finally:
        for signum, handler in old_handlers.items():
            signal.signal(signum, handler)


def _spawn_gate(
    command: str,
    cwd: Path,
    deadline: float,
    log_file,
    lock_fd: int,
) -> tuple[int | None, bytes, bool]:
    """Spawns the gate, drains and reaps it against `deadline`. Returns
    (returncode, stdout_tail, exited) as `_reap` left them.

    The gate inherits `lock_fd` (`pass_fds`), so the flock stays held by
    the gate's own process group if this process dies: a SIGKILLed verify
    cannot be handled, and this inheritance alone keeps the next verify
    waiting until the orphaned gate exits. Do not add a SIGKILL "handler".
    `Popen` itself is inside the guarded region, so SIGTERM, SIGINT and
    SIGHUP landing during spawn are deferred until `Popen` returns and then
    get the same cleanup as one landing during drain/reap: kill the gate's
    process group and re-raise. `proc` is therefore always a real `Popen`
    or None in the cleanup branch."""
    proc = None
    with _deferred_signals((signal.SIGTERM, signal.SIGINT, signal.SIGHUP)) as guard:
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
            guard.gate_started = True
            guard.raise_if_pending()
            stdout_buf, done = _drain_bounded(proc, GATE_OUTPUT_CAP, deadline, log_file)
            exited = _reap(proc, deadline, done)
        except BaseException as exc:
            # A log-sink write error or a guarded signal: kill and reap the
            # gate, then re-raise. A signal landing during the cleanup is
            # recorded (guard.cleaning is True, so guard.handle defers it)
            # and must still win once cleanup finishes, with the original
            # exception kept as its cause rather than dropped.
            guard.cleaning = True
            _kill_gate(proc)
            if guard.pending_signum is not None:
                raise _signal_error(guard.pending_signum) from exc
            raise
    return proc.returncode, stdout_buf, exited


def _kill_gate(proc: subprocess.Popen | None) -> None:
    """Kills and reaps the gate's process group and closes its pipes.
    `proc` is None when the gate never actually forked, which is a no-op.
    The group may already be gone, which raises ProcessLookupError and must
    not mask the error the caller is propagating."""
    if proc is None:
        return
    try:
        os.killpg(proc.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    proc.wait()
    proc.stdout.close()
    proc.stderr.close()


def run_gate(
    command: str,
    cwd: Path,
    sha: str,
    cycle: int | None,
    timeout: float = GATE_TIMEOUT_S,
    log_path: Path | None = None,
    lock_timeout: float = GATE_LOCK_TIMEOUT_S,
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

    The wait for the exclusive flock on `cwd / GATE_LOCK_REL` (polled with
    `LOCK_NB`, never a blocking `LOCK_EX`) is bounded by `lock_timeout`
    alone. Once the lock is held, the gate's own deadline is computed fresh
    as `time.monotonic() + timeout`, so a late waiter still gets the full
    `timeout` for its gate. Expiry while still waiting for the lock returns
    `_lock_timeout_result()` with the lock never taken, released in the
    closing `finally` as a no-op. Every result carries `waited_s`, the
    seconds spent waiting for the lock. What runs once the lock is held:
    `_gate_under_lock`.
    """
    lock_path = cwd / GATE_LOCK_REL
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    lock_fd = os.open(lock_path, os.O_RDWR | os.O_CREAT)
    wait_start = time.monotonic()
    try:
        return _gate_under_lock(
            command,
            cwd,
            sha,
            cycle,
            timeout,
            log_path,
            lock_fd,
            wait_start + lock_timeout,
            wait_start,
        )
    finally:
        fcntl.flock(lock_fd, fcntl.LOCK_UN)
        os.close(lock_fd)


def _gate_under_lock(
    command: str,
    cwd: Path,
    sha: str,
    cycle: int | None,
    timeout: float,
    log_path: Path | None,
    lock_fd: int,
    lock_deadline: float,
    wait_start: float,
) -> dict:
    """The locked half of `run_gate`: wait for the flock until
    `lock_deadline` (`_lock_timeout_result()` on expiry). `waited_s`, the
    time since `wait_start`, is measured once the wait ends and goes on
    every result. Once the lock is held, the gate gets its own deadline
    `timeout` seconds from now. Then: the
    pre-spawn dirty check; then a re-check that `git rev-parse HEAD` still
    equals `sha` (a mismatch or git failure returns `_head_moved_result()`,
    the gate never runs); then `_run_locked_gate` opens `log_path` itself
    (creating parent directories first) and deletes any existing record
    before spawning the child, so a run that fails, times out or dirties
    the tree leaves no older record behind. A failure to open the log or
    delete the record raises the bare OSError rather than being caught
    here. Neither refusal opens the log or deletes the record."""
    acquired = _acquire_lock(lock_fd, lock_deadline)
    waited_s = time.monotonic() - wait_start
    if not acquired:
        return _lock_timeout_result(waited_s)
    gate_deadline = time.monotonic() + timeout
    extra_excluded, refusal = _lock_and_check(cwd, sha, log_path, waited_s)
    if refusal is _HEAD_MOVED:
        return _head_moved_result(waited_s)
    if refusal is not None:
        return refusal
    return _run_locked_gate(
        command,
        cwd,
        sha,
        cycle,
        gate_deadline,
        log_path,
        extra_excluded,
        lock_fd,
        waited_s,
    )
