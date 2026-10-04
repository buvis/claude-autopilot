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
_STALE: tuple[str, dict] = ("stale", {})


def _git(repo_root: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )


def _dirty_path_is_in_store(new_path: str, old_path: str | None) -> bool:
    """A porcelain -z status record's STORE_PREFIX check: the path field
    (and the second, source path field when the record is a rename/copy)
    must both be under STORE_PREFIX, or the record counts as dirty outside
    the store. A rename or copy is judged by both its destination and
    source path -- crossing the store boundary in either direction, on
    either path, is dirty."""
    paths = (new_path, old_path) if old_path else (new_path,)
    return all(p.startswith(STORE_PREFIX) for p in paths)


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
    log = _git(repo_root, "log", f"{sha}..{head_sha}", "--name-only", "--format=")
    if log.returncode != 0:
        return False
    paths = [line for line in log.stdout.splitlines() if line.strip()]
    if not all(path.startswith(STORE_PREFIX) for path in paths):
        return False
    status = _git(repo_root, "status", "--porcelain=1", "-z")
    if status.returncode != 0:
        return False
    records = _iter_porcelain_z_records(status.stdout)
    return all(_dirty_path_is_in_store(new, old) for new, old in records)


def reuse_verdict(
    record: dict | None,
    repo_root: Path,
    head_sha: str,
) -> tuple[str, dict]:
    """
    record: the parsed contents of last-verification.json, or None if the
        file is missing/unreadable/unparseable.
    Returns ("reused", record) only when ALL hold:
      - record is not None, record["sha"] is a non-empty str
      - record["passed"], record["failed"], record["skipped"] are all
        present and not None
      - `git merge-base --is-ancestor <record["sha"]> <head_sha>` exits 0
        (record["sha"] is a real ancestor of head_sha — rejects a record
        from a sibling or descendant commit surviving a reset/rebase)
      - every path in `git log <record["sha"]>..<head_sha> --name-only`
        (cwd=repo_root) starts with "docs/dev/project-management/" (an empty
        diff also counts — vacuously true)
      - `git status --porcelain` (cwd=repo_root) is empty — reuse never
        certifies a dirty working tree, since gather-context.sh's diff is
        against the working tree, not just HEAD
    Returns ("stale", {}) otherwise, including when any git call itself
    fails (missing sha, unknown ref, non-git repo, non-zero exit on the
    ancestor check) — fail toward re-running the gate, never toward
    skipping it.
    """
    if not isinstance(record, dict):
        return _STALE
    sha = record.get("sha")
    if not isinstance(sha, str) or not sha:
        return _STALE
    if any(record.get(key) is None for key in ("passed", "failed", "skipped")):
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
    proc: subprocess.Popen, cap: int, deadline: float
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


def run_gate(
    command: str,
    cwd: Path,
    sha: str,
    cycle: int | None,
    timeout: float = GATE_TIMEOUT_S,
) -> dict:
    """
    Runs `command` (the project's test-gate command, e.g.
    `dev/bin/release-checks` -- resolved by the caller, never hardcoded
    here) via subprocess.Popen(shell=True), draining stdout/stderr in
    bounded chunks (never buffering the full output) against a wall-clock
    deadline. On deadline expiry with the child not yet reaped: kill the
    process group, return {"passed": None, "failed": None, "skipped": None,
    "exit": None, "raw_line": None, "timed_out": True} and write NOTHING to
    last-verification.json. On a clean exit, parse the command's own final
    summary line via SUMMARY_RE, keeping the LAST match in the (bounded)
    stdout tail -- a command that prints the pattern more than once (a
    retry) is read as its final, superseding line. If no line matches,
    passed/failed/skipped are None and nothing is written. On a successful
    parse, writes last-verification.json per
    skills/work/references/final-verification.md.
    """
    proc = subprocess.Popen(
        command,
        shell=True,
        cwd=cwd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        start_new_session=True,
    )
    stdout_buf, done = _drain_bounded(proc, GATE_OUTPUT_CAP, time.monotonic() + timeout)
    if not done:
        os.killpg(proc.pid, signal.SIGKILL)
        proc.wait()
        return {
            "passed": None,
            "failed": None,
            "skipped": None,
            "exit": None,
            "raw_line": None,
            "timed_out": True,
        }
    proc.wait()
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
