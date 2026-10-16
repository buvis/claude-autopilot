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


class _FailingSink:
    """A log sink whose every write fails with `code` (a full disk, an I/O
    error, a file grown past its limit)."""

    def __init__(self, code: int) -> None:
        self.code = code

    def write(self, chunk: bytes) -> int:
        raise OSError(self.code, os.strerror(self.code))


def _fail_the_log_sink(monkeypatch: pytest.MonkeyPatch, code: int) -> dict:
    """Runs the real drain, but hands it a sink that cannot be written.
    Returns a dict that gets the gate's `proc` and the real log file
    run_gate opened, so the test can check both are closed afterwards."""
    real = verification._drain_bounded
    seen: dict = {}

    def _wrapper(proc, cap, deadline, sink=None):
        seen["proc"], seen["log"] = proc, sink
        return real(proc, cap, deadline, _FailingSink(code))

    monkeypatch.setattr(verification, "_drain_bounded", _wrapper)
    return seen


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


def _assert_gate_killed_and_reaped(pid: int) -> None:
    # The shell was killed AND reaped (not left a zombie) before the error
    # left run_gate: checked at once, with no waiting.
    assert not _process_exists(pid)
    # Its sleeping child, same process group, was killed with it.
    deadline = time.monotonic() + 5
    while _group_exists(pid) and time.monotonic() < deadline:
        time.sleep(0.05)
    assert not _group_exists(pid)


def _run_gate_into_a_failing_sink(
    repo: Path, scratch: Path, monkeypatch: pytest.MonkeyPatch, code: int
) -> tuple[pytest.ExceptionInfo, int, dict]:
    """Starts a gate whose shell (also its process group leader) writes its
    pid, prints a line, then sleeps 30s in a child; the first log write
    fails with `code`. Returns the raised error, the shell's pid, and the
    proc and log file run_gate handed to the drain."""
    pid_file = scratch / "pid.txt"
    command = f"echo $$ > '{pid_file}'; echo started; sleep 30; echo done"
    seen = _fail_the_log_sink(monkeypatch, code)
    head = _git(repo, "rev-parse", "HEAD")
    with pytest.raises(OSError) as raised:
        verification.run_gate(
            command, repo, head, 1, log_path=repo / "docs" / "dev" / "tmp" / "gate.log"
        )
    return raised, int(pid_file.read_text().strip()), seen


@pytest.mark.parametrize(
    "code", [errno.ENOSPC, errno.EIO, errno.EFBIG], ids=["ENOSPC", "EIO", "EFBIG"]
)
def test_log_write_error_kills_and_reaps_the_gate(
    repo: Path, tmp_path_factory, monkeypatch: pytest.MonkeyPatch, code: int
) -> None:
    scratch = tmp_path_factory.mktemp("sink")
    start = time.monotonic()
    raised, pid, seen = _run_gate_into_a_failing_sink(repo, scratch, monkeypatch, code)
    try:
        # The sink's own error, whatever its errno, leaves run_gate unchanged
        # and promptly (not after the child's 30s sleep).
        assert raised.value.errno == code
        assert time.monotonic() - start < 10
        _assert_gate_killed_and_reaped(pid)
        # Nothing leaks: the log file and both of the child's pipes are shut.
        assert seen["log"].closed
        assert seen["proc"].stdout.closed
        assert seen["proc"].stderr.closed
        # A failed run writes no record.
        assert not (repo / RECORD_REL).exists()
    finally:
        _kill_group_quietly(pid)


def test_log_write_error_releases_the_gate_lock(
    repo: Path, tmp_path_factory, monkeypatch: pytest.MonkeyPatch
) -> None:
    scratch = tmp_path_factory.mktemp("sink")
    _, pid, _ = _run_gate_into_a_failing_sink(repo, scratch, monkeypatch, errno.EIO)
    try:
        # The lock is free again AND the gate it guarded is gone: a free lock
        # over a still-running gate would let a second gate start beside it.
        _assert_gate_killed_and_reaped(pid)
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


def test_run_gate_refuses_a_symlinked_log_and_leaves_its_target(repo: Path) -> None:
    # The direct (non-symlink) tracked-log case is owned by
    # test_verify_log_refusal.py::test_run_gate_refuses_tracked_log_without_opening.
    # A symlinked log never reaches the gate either: the link itself is
    # untracked, so it shows up as dirt in the ordinary pre-spawn scan and
    # the gate never runs at all -- dirty, unrecorded, target untouched.
    head = _commit(repo, "logs/gate.log", "committed log body\n")
    log_path = repo / "link.log"
    log_path.symlink_to(Path("logs") / "gate.log")

    result = verification.run_gate(SUMMARY, repo, head, 1, log_path=log_path)

    assert result["recorded"] is False
    assert result["dirty"] is True
    assert (repo / "logs" / "gate.log").read_bytes() == b"committed log body\n"


@pytest.mark.parametrize("leftover", [None, b"an older run's log\n"], ids=["new", "leftover"])
def test_run_gate_writes_an_untracked_log_inside_the_repo(
    repo: Path, leftover: bytes | None
) -> None:
    # Neither sitting inside the repo nor already existing makes a log
    # "tracked": an untracked destination, brand-new or left over from an
    # earlier run, is written and the gate records.
    log_path = repo / "logs" / "gate.log"
    if leftover is not None:
        log_path.parent.mkdir(parents=True)
        log_path.write_bytes(leftover)
    head = _git(repo, "rev-parse", "HEAD")

    result = verification.run_gate(
        f"echo from-the-gate; {SUMMARY}", repo, head, 1, log_path=log_path
    )

    assert result["recorded"] is True
    assert result["dirty"] is False
    assert (repo / RECORD_REL).exists()
    assert log_path.read_bytes() == b"from-the-gate\nPASS 1 FAIL 0 SKIP 0 EXIT 0\n"
