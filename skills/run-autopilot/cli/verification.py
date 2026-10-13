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

import json
import os
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

STORE_PREFIX = "docs/dev/project-management/"
RECORD_REL = Path(STORE_PREFIX) / "autopilot" / "last-verification.json"
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
    return not _dirty_outside_store(repo_root)


class _GitProbeFailed(OSError):
    """A git call in the dirt probe exited non-zero (non-git cwd and the
    like); an OSError so `_dirty_outside_store` counts it as dirty."""


def _dirty_outside_store_paths(
    repo_root: Path,
    extra_excluded: tuple[str, ...] = (),
) -> list[str]:
    """Sorted, deduplicated paths of every porcelain status record outside
    the store roots, [] when clean. Store roots are
    `{prefix + p for p in STORE_PREFIXES}` (prefix match), where
    `prefix` is `git rev-parse --show-prefix`; `extra_excluded` holds
    TOPLEVEL-relative POSIX file paths, used as given (not re-joined with
    prefix) and matched exactly, never as prefixes. Runs
    `git status --porcelain=1 -z --untracked-files=all` and reuses `_iter_porcelain_z_records` and `_dirty_path_is_in_store`; a
    rename/copy record contributes both of its paths. Catches nothing: a
    failing git call raises `_GitProbeFailed` (an OSError), never `[]`."""
    prefix = _git(repo_root, "rev-parse", "--show-prefix")
    if prefix.returncode != 0:
        raise _GitProbeFailed("git rev-parse --show-prefix failed")
    store = tuple(prefix.stdout.strip() + root for root in STORE_PREFIXES)
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
    return sorted(offending)


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


def _untracked_log_exclusion(cwd: Path, log_path: Path | None) -> tuple[str, ...]:
    """`(toplevel-relative POSIX path of log_path,)` when the log resolves
    inside cwd's git toplevel and is NOT tracked there; `()` otherwise
    (no log, log outside the toplevel, log tracked, or any git failure).
    A tracked log is never excused: its edits stay dirt."""
    if log_path is None:
        return ()
    try:
        top = _git(cwd, "rev-parse", "--show-toplevel")
        if top.returncode != 0:
            return ()
        toplevel = Path(top.stdout.strip())
        rel = log_path.resolve().relative_to(toplevel.resolve()).as_posix()
        tracked = _git(toplevel, "ls-files", "--error-unmatch", "--", rel)
    except (OSError, ValueError):
        return ()
    return () if tracked.returncode == 0 else (rel,)


def _record_shape_ok(record: dict, gate_command: str) -> bool:
    """True iff the record has a full sha, all counts, and a green run of
    exactly `gate_command`."""
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
    """Collapses whitespace, then strips one leading `bash `/`sh ` and one
    leading `./`. A non-str maps to ""."""
    if not isinstance(command, str):
        return ""
    text = " ".join(command.split())
    for shell in ("bash ", "sh "):
        if text.startswith(shell):
            text = text[len(shell) :]
            break
    return text.removeprefix("./")


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
    Returns ("stale", {}) otherwise, including when any git call itself
    fails (missing sha, unknown ref, non-git repo, non-zero exit on the
    ancestor check): fail toward re-running the gate, never toward
    skipping it.
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
    }


def _dirty_result() -> dict:
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
    dirty = _dirty_outside_store(cwd, extra_excluded)
    result = {
        "passed": int(found.group(1)) if found else None,
        "failed": int(found.group(2)) if found else None,
        "skipped": int(found.group(3)) if found else None,
        "exit": returncode,
        "raw_line": raw_line,
        "timed_out": False,
        "recorded": False,
        "dirty": dirty,
    }
    if found and not dirty:
        _write_record(cwd, command, sha, cycle, result)
        result["recorded"] = True
    return result


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
    in read order, in addition to the bounded in-memory parse tail;
    `run_gate` opens `log_path` itself (creating parent directories first)
    before its pre-spawn dirty check, and a failure to open it raises the
    bare OSError rather than being caught here.
    """
    log_file = None
    if log_path is not None:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_file = open(log_path, "wb", buffering=0)
    try:
        extra_excluded = _untracked_log_exclusion(cwd, log_path)
        if _dirty_outside_store(cwd, extra_excluded):
            return _dirty_result()
        proc = subprocess.Popen(
            command,
            shell=True,
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            start_new_session=True,
        )
        deadline = time.monotonic() + timeout
        stdout_buf, done = _drain_bounded(proc, GATE_OUTPUT_CAP, deadline, log_file)
        if not _reap(proc, deadline, done):
            return _timed_out_result()
        return _record_gate(
            command, cwd, sha, cycle, proc.returncode, stdout_buf, extra_excluded
        )
    finally:
        if log_file is not None:
            log_file.close()
