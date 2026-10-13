#!/usr/bin/env python3
"""Tests for cli/verification.py split out of test_verification.py: how
run_gate guards its log file. A log-sink write error kills and reaps the
gate's process group and still releases the gate lock; a tracked log
destination is refused before anything is opened. Split because
test_verification.py sits at the 800-line style cap.

The checks run against real temporary git repos and real child processes.
"""

from __future__ import annotations

import errno
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

import pytest

from cli import verification

STORE = "docs/dev/project-management"
RECORD_REL = Path(STORE) / "autopilot" / "last-verification.json"
GATE_LOCK_REL = Path("docs/dev/tmp") / "gate.lock"
SUMMARY = "echo 'PASS 1 FAIL 0 SKIP 0 EXIT 0'"


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        [
            "git",
            "-c",
            "user.name=t",
            "-c",
            "user.email=t@example.com",
            "-c",
            "commit.gpgsign=false",
            *args,
        ],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _commit(repo: Path, rel: str, body: str = "x\n") -> str:
    path = repo / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body)
    _git(repo, "add", "--", rel)
    _git(repo, "commit", "--no-verify", "-q", "-m", f"touch {rel}")
    return _git(repo, "rev-parse", "HEAD")


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    _git(tmp_path, "init", "-q")
    _commit(tmp_path, "src/app.py", "print(1)\n")
    return tmp_path


class _FullDiskSink:
    """A log sink whose every write fails the way a full disk does."""

    def write(self, chunk: bytes) -> int:
        raise OSError(errno.ENOSPC, "No space left on device")


def _fail_the_log_sink(monkeypatch: pytest.MonkeyPatch) -> None:
    """Runs the real drain, but hands it a sink that cannot be written."""
    real = verification._drain_bounded

    def _wrapper(proc, cap, deadline, sink=None):
        return real(proc, cap, deadline, _FullDiskSink())

    monkeypatch.setattr(verification, "_drain_bounded", _wrapper)


def _process_exists(pid: int) -> bool:
    # A zombie still answers signal 0: True here means "not yet reaped".
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    return True


def _group_exists(pgid: int) -> bool:
    try:
        os.killpg(pgid, 0)
    except ProcessLookupError:
        return False
    return True


def _kill_group_quietly(pgid: int) -> None:
    try:
        os.killpg(pgid, signal.SIGKILL)
    except ProcessLookupError:
        pass


def _run_gate_into_a_failing_sink(
    repo: Path, scratch: Path, monkeypatch: pytest.MonkeyPatch
) -> tuple[pytest.ExceptionInfo, int]:
    """Starts a gate whose shell (also its process group leader) writes its
    pid, prints a line, then sleeps 30s in a child; the first log write
    fails. Returns the raised error and the shell's pid."""
    pid_file = scratch / "pid.txt"
    command = f"echo $$ > '{pid_file}'; echo started; sleep 30; echo done"
    _fail_the_log_sink(monkeypatch)
    head = _git(repo, "rev-parse", "HEAD")
    with pytest.raises(OSError) as raised:
        verification.run_gate(command, repo, head, 1, log_path=scratch / "gate.log")
    return raised, int(pid_file.read_text().strip())


def test_log_write_error_kills_and_reaps_the_gate(
    repo: Path, tmp_path_factory, monkeypatch: pytest.MonkeyPatch
) -> None:
    scratch = tmp_path_factory.mktemp("sink")
    start = time.monotonic()
    raised, pid = _run_gate_into_a_failing_sink(repo, scratch, monkeypatch)
    try:
        # The sink's own error leaves run_gate, unchanged and promptly (not
        # after the child's 30s sleep).
        assert raised.value.errno == errno.ENOSPC
        assert time.monotonic() - start < 10
        # The shell was killed AND reaped (not left a zombie) before the
        # error left run_gate: checked at once, with no waiting.
        assert not _process_exists(pid)
        # Its sleeping child, same process group, was killed with it.
        deadline = time.monotonic() + 5
        while _group_exists(pid) and time.monotonic() < deadline:
            time.sleep(0.05)
        assert not _group_exists(pid)
        # A failed run writes no record.
        assert not (repo / RECORD_REL).exists()
    finally:
        _kill_group_quietly(pid)


def test_log_write_error_releases_the_gate_lock(
    repo: Path, tmp_path_factory, monkeypatch: pytest.MonkeyPatch
) -> None:
    scratch = tmp_path_factory.mktemp("sink")
    _, pid = _run_gate_into_a_failing_sink(repo, scratch, monkeypatch)
    try:
        # A separate process opens the lock file and takes it at once
        # (LOCK_NB): only a released flock lets it, a renamed or removed
        # path would not prove that.
        probe = (
            "import fcntl, os, sys\n"
            "fd = os.open(sys.argv[1], os.O_RDWR)\n"
            "fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)\n"
        )
        taken = subprocess.run(
            [sys.executable, "-c", probe, str(repo / GATE_LOCK_REL)],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert taken.returncode == 0, taken.stderr
    finally:
        _kill_group_quietly(pid)


@pytest.mark.parametrize("cwd_rel", [".", "src"])
def test_run_gate_refuses_a_tracked_log_path_and_leaves_it_unchanged(
    repo: Path, tmp_path_factory, cwd_rel: str
) -> None:
    # The log destination is a committed file and the tree is clean. The
    # refusal names it toplevel-relative, also when cwd is a subdirectory.
    head = _commit(repo, "logs/gate.log", "committed log body\n")
    cwd = repo / cwd_rel
    record = cwd / RECORD_REL
    assert verification.run_gate(SUMMARY, cwd, head, 1)["recorded"] is True
    green = record.read_bytes()
    ran = tmp_path_factory.mktemp("ran") / "ran.txt"

    result = verification.run_gate(
        f"echo ran > '{ran}'; {SUMMARY}", cwd, head, 2, log_path=repo / "logs" / "gate.log"
    )

    assert result == {
        "passed": None,
        "failed": None,
        "skipped": None,
        "exit": None,
        "raw_line": None,
        "timed_out": False,
        "recorded": False,
        "dirty": True,
        "dirty_paths": ["logs/gate.log"],
    }
    # The log was never opened for writing, the gate never ran, the older
    # record was not touched, and the lock was released on the way out.
    assert (repo / "logs" / "gate.log").read_bytes() == b"committed log body\n"
    assert not ran.exists()
    assert record.read_bytes() == green
    assert verification.run_gate(SUMMARY, cwd, head, 3)["recorded"] is True
