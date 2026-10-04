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
import signal
import subprocess
from pathlib import Path

GATE_TIMEOUT_S = 1800
GATE_OUTPUT_CAP = 2_000_000  # bytes of combined stdout+stderr kept

STORE_PREFIX = "docs/dev/project-management/"
RECORD_REL = Path(STORE_PREFIX) / "autopilot" / "last-verification.json"
SUMMARY_RE = re.compile(r"PASS (\d+) FAIL (\d+) SKIP (\d+) EXIT (\d+)")
_STALE: tuple[str, dict] = ("stale", {})


def _git(repo_root: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args], cwd=repo_root, capture_output=True, text=True, check=False
    )


def reuse_verdict(record: dict | None, repo_root: Path, head_sha: str) -> tuple[str, dict]:
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
        if _git(repo_root, "merge-base", "--is-ancestor", sha, head_sha).returncode != 0:
            return _STALE
        log = _git(repo_root, "log", f"{sha}..{head_sha}", "--name-only", "--format=")
        if log.returncode != 0:
            return _STALE
        paths = [line for line in log.stdout.splitlines() if line.strip()]
        if not all(path.startswith(STORE_PREFIX) for path in paths):
            return _STALE
        status = _git(repo_root, "status", "--porcelain")
        if status.returncode != 0 or status.stdout.strip():
            return _STALE
    except OSError:
        return _STALE
    return ("reused", record)


def _cap(text: str) -> str:
    return text.encode("utf-8")[:GATE_OUTPUT_CAP].decode("utf-8", errors="ignore")


def _write_record(cwd: Path, command: str, sha: str, cycle: int | None, result: dict) -> None:
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


def run_gate(
    command: str,
    cwd: Path,
    sha: str,
    cycle: int | None,
    timeout: float = GATE_TIMEOUT_S,
) -> dict:
    """
    Runs `command` (the project's test-gate command, e.g.
    `dev/bin/release-checks` — resolved by the caller, never hardcoded here)
    via subprocess.run(command, shell=True, cwd=cwd, capture_output=True,
    text=True, timeout=GATE_TIMEOUT_S), with stdout/stderr each truncated to
    GATE_OUTPUT_CAP bytes before any parsing or storage.
    On subprocess.TimeoutExpired: kill the process group, return
    {"passed": None, "failed": None, "skipped": None, "exit": None,
     "raw_line": None, "timed_out": True} and write NOTHING to
     last-verification.json (a timed-out run proves nothing).
    On a clean exit, parse the command's own final summary line via the
    fixed pattern `PASS (\\d+) FAIL (\\d+) SKIP (\\d+) EXIT (\\d+)`
    (case-sensitive, matched against the LAST matching line in the captured
    stdout). Return {"passed": int, "failed": int, "skipped": int,
    "exit": int, "raw_line": str, "timed_out": False}.
    If no line matches, return the same shape with passed/failed/skipped
    = None.
    On a successful parse (passed/failed/skipped all not None), WRITE
    <cwd>/docs/dev/project-management/autopilot/last-verification.json:
    {"sha": sha, "cycle": cycle, "commands":
    [{"command": command, "exit": result["exit"]}], "passed", "failed",
    "skipped"} — this is the shape skills/work/references/final-verification.md
    already defines for this file.

    `timeout` defaults to GATE_TIMEOUT_S; it exists so tests need not sleep
    for 30 minutes. `exit` is the process's own return code. stderr is
    captured (so it never floods the caller) but not parsed or stored.
    """
    # Popen in its own session so a timeout can kill the shell's children too;
    # a bare kill() of the shell would leave them holding the pipes open.
    proc = subprocess.Popen(
        command,
        shell=True,
        cwd=cwd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        start_new_session=True,
    )
    try:
        stdout, _stderr = proc.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        os.killpg(proc.pid, signal.SIGKILL)
        proc.communicate()
        return {
            "passed": None,
            "failed": None,
            "skipped": None,
            "exit": None,
            "raw_line": None,
            "timed_out": True,
        }
    raw_line, found = None, None
    for line in _cap(stdout).splitlines():
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
