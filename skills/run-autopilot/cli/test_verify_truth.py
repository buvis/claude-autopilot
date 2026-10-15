#!/usr/bin/env python3
"""Regression pins for PRD 00311 (`autopilot verify` reports what the gate
did): the verb's exit code follows the parsed summary, a hand-written record
is never reused, a killed verify leaves no gate running beside the next one,
and every refusal names its own cause.

Each test drives a real temporary git repo and a scripted gate (an inline
shell command or a small Python script written outside the repo), the same
fixture shape as test_verification_dirty.py.
"""

from __future__ import annotations

import fcntl
import json
import os
import shlex
import signal
import subprocess
import sys
import time
from pathlib import Path

import pytest

from cli import review_stage, verification

STORE = "docs/dev/project-management"
GATE = "dev/bin/release-checks"
CLI_MAIN = Path(__file__).resolve().parent / "__main__.py"

TICK_GATE = """\
import sys, time
ticks, label, seconds = sys.argv[1], sys.argv[2], float(sys.argv[3])
end = time.time() + seconds
with open(ticks, "a") as f:
    while time.time() < end:
        f.write(f"{label} tick {time.time()}\\n")
        f.flush()
        time.sleep(0.1)
    f.write(f"{label} end {time.time()}\\n")
    f.flush()
print("PASS 1 FAIL 0 SKIP 0 EXIT 0", flush=True)
"""

GROUP_GATE = """\
import os, sys, time
tmp = sys.argv[1] + ".tmp"
with open(tmp, "w") as f:
    f.write(str(os.getpgrp()))
os.replace(tmp, sys.argv[1])
time.sleep(60)
"""


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
    # The repo sits one level down so gate scripts and tick files can live
    # beside it in tmp_path without counting as dirt inside it.
    root = tmp_path / "repo"
    root.mkdir()
    _git(root, "init", "-q")
    _commit(root, "src/app.py", "print(1)\n")
    return root


def _record(sha: object, passed=5, failed=0, skipped=1) -> dict:
    return {
        "sha": sha,
        "cycle": 1,
        "commands": [{"command": GATE, "exit": 0}],
        "passed": passed,
        "failed": failed,
        "skipped": skipped,
    }


def _verify_argv(repo: Path, gate_command: str, *extra: str) -> list[str]:
    return [
        sys.executable,
        str(CLI_MAIN),
        "verify",
        "--gate-command",
        gate_command,
        "--repo-root",
        str(repo),
        *extra,
    ]


def _run_verify(repo: Path, gate_command: str, *extra: str):
    return subprocess.run(
        _verify_argv(repo, gate_command, *extra),
        capture_output=True,
        text=True,
        timeout=60,
    )


def _spawn_verify(repo: Path, gate_command: str) -> subprocess.Popen:
    return subprocess.Popen(
        _verify_argv(repo, gate_command),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def _json_lines(stdout: str) -> list[dict]:
    return [json.loads(line) for line in stdout.splitlines() if line.strip()]


def _ticks(path: Path, label: str, kind: str) -> list[float]:
    if not path.exists():
        return []
    return [
        float(parts[2])
        for parts in (line.split() for line in path.read_text().splitlines())
        if len(parts) == 3 and parts[0] == label and parts[1] == kind
    ]


def _wait_for(predicate, timeout: float) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.05)
    return bool(predicate())


def _group_alive(pgid: int) -> bool:
    try:
        os.killpg(pgid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def test_red_summary_with_green_process_exits_1(repo: Path) -> None:
    # The gate says it failed (FAIL 1, EXIT 1) but its process exits 0: the
    # verb must follow the summary line, not the returncode.
    proc = _run_verify(repo, "printf 'PASS 4 FAIL 1 SKIP 0 EXIT 1\\n'")

    lines = _json_lines(proc.stdout)
    assert lines, proc.stderr
    assert lines[-1]["exit"] == 0
    assert proc.returncode == 1


def test_hand_written_record_without_writer_is_never_reused(repo: Path) -> None:
    head = _git(repo, "rev-parse", "HEAD")
    hand_written = _record(head)

    assert verification.reuse_verdict(hand_written, repo, head, gate_command=GATE) == (
        "stale",
        {},
    )

    stamped = {**_record(head), "writer": "run_gate"}
    assert verification.reuse_verdict(stamped, repo, head, gate_command=GATE) == (
        "reused",
        stamped,
    )


def test_sigkilled_verify_leaves_no_overlapping_gate(
    repo: Path, tmp_path: Path
) -> None:
    gate = tmp_path / "tick_gate.py"
    gate.write_text(TICK_GATE)
    ticks = tmp_path / "ticks.txt"

    def command(label: str) -> str:
        return " ".join(
            shlex.quote(part)
            for part in (sys.executable, str(gate), str(ticks), label, "3")
        )

    first = _spawn_verify(repo, command("A"))
    started = time.monotonic()
    second = None
    try:
        # The gate must have spawned before the kill, or there is nothing
        # to orphan; then the kill lands at 0.5s.
        assert _wait_for(lambda: _ticks(ticks, "A", "tick"), 15), "gate A never ticked"
        time.sleep(max(0.0, 0.5 - (time.monotonic() - started)))
        first.send_signal(signal.SIGKILL)
        first.wait(timeout=10)

        second = _spawn_verify(repo, command("B"))
        second.wait(timeout=30)
        assert _wait_for(lambda: _ticks(ticks, "A", "end"), 10), "gate A never ended"
    finally:
        for proc in (first, second):
            if proc is not None and proc.poll() is None:
                proc.kill()
                proc.wait()

    first_ticks = _ticks(ticks, "A", "tick")
    second_ticks = _ticks(ticks, "B", "tick")
    assert second_ticks, "gate B never ticked"
    assert min(second_ticks) > max(first_ticks)


def test_sigterm_kills_the_gate_group(repo: Path, tmp_path: Path) -> None:
    gate = tmp_path / "group_gate.py"
    gate.write_text(GROUP_GATE)
    pgid_file = tmp_path / "gate.pgid"
    command = " ".join(
        shlex.quote(part) for part in (sys.executable, str(gate), str(pgid_file))
    )

    verify = _spawn_verify(repo, command)
    pgid = None
    try:
        assert _wait_for(pgid_file.exists, 15), "gate never started"
        pgid = int(pgid_file.read_text())
        assert _group_alive(pgid)

        verify.send_signal(signal.SIGTERM)
        assert _wait_for(lambda: not _group_alive(pgid), 2.0), (
            "gate group still alive 2s after SIGTERM"
        )
    finally:
        if verify.poll() is None:
            verify.kill()
        verify.wait()
        if pgid is not None and _group_alive(pgid):
            os.killpg(pgid, signal.SIGKILL)


def test_lock_wait_expiry_reports_lock_timeout(repo: Path) -> None:
    head = _git(repo, "rev-parse", "HEAD")
    lock_path = repo / verification.GATE_LOCK_REL
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    log_path = repo / "docs" / "dev" / "tmp" / "gate-lock-timeout.log"
    held = os.open(lock_path, os.O_RDWR | os.O_CREAT)
    try:
        fcntl.flock(held, fcntl.LOCK_EX)
        result = verification.run_gate(
            "echo 'PASS 1 FAIL 0 SKIP 0 EXIT 0'",
            repo,
            head,
            1,
            timeout=0.2,
            log_path=log_path,
        )
    finally:
        fcntl.flock(held, fcntl.LOCK_UN)
        os.close(held)

    assert result.get("lock_timeout") is True
    assert result["timed_out"] is False
    assert not log_path.exists()


def test_head_moved_reports_head_moved(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    head = _git(repo, "rev-parse", "HEAD")
    original = verification._acquire_lock

    def acquire_then_commit(lock_fd: int, deadline: float) -> bool:
        held = original(lock_fd, deadline)
        # A concurrent commit lands while the lock is held: the tree stays
        # clean, only HEAD moves.
        _commit(repo, "src/other.py", "print(2)\n")
        return held

    monkeypatch.setattr(verification, "_acquire_lock", acquire_then_commit)

    result = verification.run_gate("echo 'PASS 1 FAIL 0 SKIP 0 EXIT 0'", repo, head, 1)

    assert result.get("head_moved") is True
    assert result["dirty"] is False


def test_pre_spawn_refusal_reports_null_log(repo: Path) -> None:
    (repo / "src" / "stray.py").write_text("print('dirty')\n")

    proc = _run_verify(repo, "echo 'PASS 1 FAIL 0 SKIP 0 EXIT 0'")

    lines = _json_lines(proc.stdout)
    assert lines, proc.stderr
    assert lines[-1]["dirty"] is True
    assert lines[-1]["log"] is None


def test_exit_2_refusals_print_json(repo: Path, tmp_path: Path) -> None:
    store_log = _run_verify(
        repo,
        "echo 'PASS 1 FAIL 0 SKIP 0 EXIT 0'",
        "--log",
        f"{STORE}/gate.log",
    )
    empty = tmp_path / "empty"
    empty.mkdir()
    _git(empty, "init", "-q")
    no_head = _run_verify(empty, "echo 'PASS 1 FAIL 0 SKIP 0 EXIT 0'")

    for proc in (store_log, no_head):
        assert proc.returncode == 2
        lines = proc.stdout.splitlines()
        assert len(lines) == 1, proc.stdout
        payload = json.loads(lines[0])
        assert payload.get("error")
        assert payload.get("exit") == 2


def _refusal(**overrides) -> dict:
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
        "head_moved": False,
        **overrides,
    }


def test_run_gate_line_names_lock_timeout_and_head_moved(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cases = [
        (
            _refusal(lock_timeout=True),
            "Tests: (gate skipped: another gate held the lock for "
            f"{int(verification.GATE_TIMEOUT_S)}s)",
        ),
        (
            _refusal(head_moved=True),
            "Tests: (gate skipped: HEAD moved during the lock wait)",
        ),
    ]
    for fake, expected in cases:
        monkeypatch.setattr(verification, "run_gate", lambda *a, _r=fake, **k: _r)

        out = review_stage.run_gate_line(repo, GATE, "1")

        assert out["tests_line"] == expected
        assert out.get("dirty_paths") == fake["dirty_paths"]
