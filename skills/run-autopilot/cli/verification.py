#!/usr/bin/env python3
"""Run the project's test gate once and decide when its record can be reused.

`run_gate` is the code-side writer of
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

GATE_TIMEOUT_S = 1800
GATE_OUTPUT_CAP = 2_000_000  # bytes of combined stdout+stderr kept

STORE_PREFIX = "docs/dev/project-management/"
RECORD_REL = Path(STORE_PREFIX) / "autopilot" / "last-verification.json"
SUMMARY_RE = re.compile(r"PASS (\d+) FAIL (\d+) SKIP (\d+) EXIT (\d+)")
_FULL_SHA_RE = re.compile(r"(?:[0-9a-f]{40}|[0-9a-f]{64})")
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
    store: str = STORE_PREFIX,
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
    """True iff `sha` is an ancestor of `head_sha`, every path changed since
    then stays under STORE_PREFIX, and the dirty paths outside the store are
    none. May raise OSError, same as the `_git` calls it wraps."""
    if _git(repo_root, "merge-base", "--is-ancestor", sha, head_sha).returncode != 0:
        return False
    # Git paths are toplevel-relative; repo_root may sit below the toplevel.
    prefix = _git(repo_root, "rev-parse", "--show-prefix")
    if prefix.returncode != 0:
        return False
    store = prefix.stdout.strip() + STORE_PREFIX
    log = _git(
        repo_root,
        "log",
        f"{sha}..{head_sha}",
        "--no-renames",
        "--name-only",
        "--format=",
    )
    if log.returncode != 0:
        return False
    paths = [line for line in log.stdout.splitlines() if line.strip()]
    if not all(path.startswith(store) for path in paths):
        return False
    status = _git(repo_root, "status", "--porcelain=1", "-z")
    if status.returncode != 0:
        return False
    records = _iter_porcelain_z_records(status.stdout)
    return all(_dirty_path_is_in_store(new, old, store) for new, old in records)


def reuse_verdict(
    record: dict | None,
    repo_root: Path,
    head_sha: str,
    gate_command: str | None = None,
) -> tuple[str, dict]:
    """
    record: the parsed contents of last-verification.json, or None if the
        file is missing/unreadable/unparseable.
    gate_command: when given, every recorded command must equal it.
    Returns ("reused", record) only when ALL hold:
      - record["sha"] is a full lowercase hex object id (never a symbolic
        ref or abbreviation), and passed/failed/skipped are all present and
        not None
      - the run was green: failed is 0 and record["commands"] is a non-empty
        list whose every entry is a dict that exited 0
      - `git merge-base --is-ancestor <record["sha"]> <head_sha>` exits 0,
        rejecting a sibling or descendant surviving a reset/rebase
      - every path in `git log <record["sha"]>..<head_sha> --name-only`
        (cwd=repo_root) starts with "docs/dev/project-management/" (an
        empty diff also counts, vacuously)
      - `git status --porcelain=1 -z` (cwd=repo_root) reports no dirty path
        outside the store tree, since gather-context.sh's diff is against
        the working tree, not just HEAD
      - a dirty or untracked docs/dev/project-management/ path is tolerated
      - a rename or copy is judged by both of its endpoint paths, so a move
        out of the store tree counts as dirty
    Returns ("stale", {}) otherwise, including when any git call itself
    fails (missing sha, unknown ref, non-git repo, non-zero exit on the
    ancestor check): fail toward re-running the gate, never toward
    skipping it.
    """
    if not isinstance(record, dict):
        return _STALE
    sha = record.get("sha")
    if not isinstance(sha, str) or not _FULL_SHA_RE.fullmatch(sha):
        return _STALE
    if any(record.get(key) is None for key in ("passed", "failed", "skipped")):
        return _STALE
    commands = record.get("commands")
    if not isinstance(commands, list) or not commands:
        return _STALE
    if record["failed"] != 0 or not all(
        isinstance(c, dict) and c.get("exit") == 0 for c in commands
    ):
        return _STALE
    if gate_command is not None and any(c.get("command") != gate_command for c in commands):
        return _STALE
    try:
        if not _ancestor_and_clean(repo_root, sha, head_sha):
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
        "commands": [{"command": command, "exit": result["exit"]}],
        "passed": result["passed"],
        "failed": result["failed"],
        "skipped": result["skipped"],
    }
    path.write_text(json.dumps(record, indent=2) + "\n")


def _drain_bounded(
    proc: subprocess.Popen,
    cap: int,
    deadline: float,
) -> tuple[bytes, bool]:
    """Drains stdout and stderr against `deadline`, keeping only the last
    `cap` bytes of stdout (dropping from the front, never the back) and
    discarding stderr after reading it (so its pipe can never fill and
    block the child). Returns (stdout_tail, done) where `done` is True iff
    the child exited and both pipes reached EOF before the deadline."""
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


def run_gate(
    command: str,
    cwd: Path,
    sha: str,
    cycle: int | None,
    timeout: float = GATE_TIMEOUT_S,
) -> dict:
    """
    Runs `command` (the gate command, e.g. `dev/bin/release-checks` --
    resolved by the caller, never hardcoded here) via Popen(shell=True),
    draining stdout/stderr in bounded chunks (never buffering the full
    output) against a wall-clock deadline that bounds the child's exit too,
    not only its output. On expiry: kill the process group, return
    `_timed_out_result()` and write NOTHING. On a clean exit, parse the
    LAST SUMMARY_RE match in the (bounded) stdout tail -- a command that
    prints the pattern twice (a retry) is read as its final, superseding
    line. No match: passed/failed/skipped are None and nothing is written;
    a parse writes last-verification.json (shape: `_write_record`).
    """
    proc = subprocess.Popen(
        command,
        shell=True,
        cwd=cwd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        start_new_session=True,
    )
    deadline = time.monotonic() + timeout
    stdout_buf, done = _drain_bounded(proc, GATE_OUTPUT_CAP, deadline)
    if not _reap(proc, deadline, done):
        return _timed_out_result()
    raw_line, found = None, None
    for line in stdout_buf.decode("utf-8", errors="ignore").splitlines():
        hit = SUMMARY_RE.search(line)
        if hit:
            raw_line, found = line, hit
    result = {
        "passed": int(found.group(1)) if found else None,
        "failed": int(found.group(2)) if found else None,
        "skipped": int(found.group(3)) if found else None,
        "exit": proc.returncode,
        "raw_line": raw_line,
        "timed_out": False,
    }
    if found:
        _write_record(cwd, command, sha, cycle, result)
    return result
