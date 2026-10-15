#!/usr/bin/env python3
"""Tests for cli/verification.py (PRD 00249 task 1).

The reuse checks run against real temporary git repos: the point is to bind
real git behavior (ancestry, diff paths, dirty tree), not a mock of it.
"""

from __future__ import annotations

import fcntl
import json
import os
import signal
import subprocess
import threading
import time
from pathlib import Path

import pytest

from cli import verification

STORE = "docs/dev/project-management"
GATE = "dev/bin/release-checks"
STORE_PREFIX = verification.STORE_PREFIX
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


def _record(sha: object, passed=5, failed=0, skipped=1) -> dict:
    return {
        "sha": sha,
        "cycle": 1,
        "writer": "run_gate",
        "commands": [{"command": "dev/bin/release-checks", "exit": 0}],
        "passed": passed,
        "failed": failed,
        "skipped": skipped,
    }


@pytest.mark.parametrize("field", ["passed", "failed", "skipped"])
def test_stale_when_counts_null(repo: Path, field: str) -> None:
    head = _git(repo, "rev-parse", "HEAD")
    nulled = _record(head)
    nulled[field] = None
    missing = _record(head)
    del missing[field]

    assert verification.reuse_verdict(nulled, repo, head, gate_command=GATE) == ("stale", {})
    assert verification.reuse_verdict(missing, repo, head, gate_command=GATE) == ("stale", {})


def test_run_gate_drains_stderr_without_deadlock(repo: Path) -> None:
    # Passes against the pre-change code too: `communicate()` already read
    # both pipes concurrently, so this is pre-existing, unchanged behavior,
    # not something the new manual `_drain_bounded` loop had to add -- it
    # only has to not regress it, which this still pins.
    # A child writing far more than one OS pipe buffer's worth to stderr,
    # before it ever prints its stdout summary line: a drain that reads
    # stdout but never stderr would leave the child blocked writing to a
    # full stderr pipe, and run_gate would hang past its deadline.
    command = (
        "head -c 2000000 /dev/zero | tr '\\0' 'e' 1>&2; "
        "echo 'PASS 1 FAIL 0 SKIP 0 EXIT 0'"
    )
    result = verification.run_gate(command, repo, _git(repo, "rev-parse", "HEAD"), None, timeout=10)

    assert result["passed"] == 1
    assert result["timed_out"] is False


def test_gate_timeout_default_lets_a_real_suite_finish() -> None:
    # A default deadline of a few seconds would kill every real gate run
    # mid-flight; the suite this gate runs takes minutes.
    assert verification.GATE_TIMEOUT_S >= 600
    assert verification.GATE_OUTPUT_CAP >= 100_000


def _spy_on_drain(monkeypatch) -> list[dict]:
    """Records every drain call's cap and the tail it handed back, while
    still running the real drain."""
    real = verification._drain_bounded
    calls: list[dict] = []

    def _wrapper(proc, cap, deadline, sink=None):
        tail, done = real(proc, cap, deadline, sink)
        calls.append({"cap": cap, "tail": tail, "done": done})
        return tail, done

    monkeypatch.setattr(verification, "_drain_bounded", _wrapper)
    return calls


def _popen(command: str) -> subprocess.Popen:
    return subprocess.Popen(
        ["/bin/sh", "-c", command],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        start_new_session=True,
    )


def test_drain_bounded_keeps_only_the_last_cap_bytes() -> None:
    proc = _popen("printf '%0300d' 0")
    try:
        tail, done = verification._drain_bounded(proc, 64, time.monotonic() + 10)
    finally:
        proc.wait()
        proc.stdout.close()
        proc.stderr.close()

    assert tail == b"0" * 64
    assert done is True


def test_drain_bounded_reports_not_done_for_a_lingering_child() -> None:
    proc = _popen("echo hi; sleep 30")
    try:
        start = time.monotonic()
        tail, done = verification._drain_bounded(proc, 4096, time.monotonic() + 0.5)
        elapsed = time.monotonic() - start
    finally:
        os.killpg(proc.pid, signal.SIGKILL)
        proc.wait()
        proc.stdout.close()
        proc.stderr.close()

    assert done is False
    assert tail == b"hi\n"
    assert elapsed < 5


def test_run_gate_prints_one_summary_line(repo: Path) -> None:
    command = (
        "printf 'PASS 1 FAIL 1 SKIP 1 EXIT 1\\n"
        "noise PASS x\\n"
        "PASS 12 FAIL 0 SKIP 3 EXIT 0\\n'"
    )
    result = verification.run_gate(command, repo, _git(repo, "rev-parse", "HEAD"), 2)

    assert result == {
        "passed": 12,
        "failed": 0,
        "skipped": 3,
        "exit": 0,
        "raw_line": "PASS 12 FAIL 0 SKIP 3 EXIT 0",
        "timed_out": False,
        "recorded": True,
        "dirty": False,
        "dirty_paths": [],
        "lock_timeout": False,
        "head_moved": False,
    }


def test_run_gate_unparseable_output_records_nothing(repo: Path) -> None:
    result = verification.run_gate(
        "echo 'pass 1 fail 0 skip 0 exit 0'; exit 3",
        repo,
        _git(repo, "rev-parse", "HEAD"),
        1,
    )

    assert result["passed"] is None
    assert result["failed"] is None
    assert result["skipped"] is None
    assert result["exit"] == 3
    assert result["timed_out"] is False
    assert not (repo / RECORD_REL).exists()

    # A line that merely looks like the summary is not one either.
    near_miss = verification.run_gate(
        "echo 'PASSED 3 of 4 in 5 s 6'",
        repo,
        _git(repo, "rev-parse", "HEAD"),
        1,
    )
    assert near_miss["passed"] is None
    assert near_miss["raw_line"] is None
    assert not (repo / RECORD_REL).exists()


def test_run_gate_keeps_tail_so_a_late_summary_line_still_parses(
    repo: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(verification, "GATE_OUTPUT_CAP", 64)
    calls = _spy_on_drain(monkeypatch)
    # The summary line is always last; a cap that keeps the tail (not the
    # head) of output exceeding GATE_OUTPUT_CAP must still find it, and the
    # bytes beyond the cap really are dropped.
    command = "printf '%0100d\\n' 0; echo 'PASS 1 FAIL 0 SKIP 0 EXIT 0'"
    result = verification.run_gate(command, repo, _git(repo, "rev-parse", "HEAD"), None)

    assert result["passed"] == 1
    assert result["failed"] == 0
    assert result["skipped"] == 0
    assert result["raw_line"] == "PASS 1 FAIL 0 SKIP 0 EXIT 0"
    assert (repo / RECORD_REL).exists()
    assert [call["cap"] for call in calls] == [verification.GATE_OUTPUT_CAP]
    assert len(calls[0]["tail"]) <= 64


def test_run_gate_streams_and_keeps_tail(repo: Path, monkeypatch) -> None:
    monkeypatch.setattr(verification, "GATE_OUTPUT_CAP", 4096)
    calls = _spy_on_drain(monkeypatch)
    # One unbroken burst, no newlines, far larger than the cap -- proves the
    # drain is byte-bounded as it reads, not only truncated after a full
    # buffered capture: what it hands back never exceeds the cap.
    command = "head -c 2000000 /dev/zero | tr '\\0' 'x'; echo; echo 'PASS 1 FAIL 0 SKIP 0 EXIT 0'"
    result = verification.run_gate(command, repo, _git(repo, "rev-parse", "HEAD"), None, timeout=30)

    assert result["passed"] == 1
    assert result["raw_line"] == "PASS 1 FAIL 0 SKIP 0 EXIT 0"
    assert [call["cap"] for call in calls] == [4096]
    assert len(calls[0]["tail"]) <= 4096


def test_run_gate_uses_last_summary_line_not_first(repo: Path) -> None:
    command = "echo 'PASS 1 FAIL 1 SKIP 0 EXIT 1'; echo 'PASS 1 FAIL 0 SKIP 0 EXIT 0'"
    result = verification.run_gate(command, repo, _git(repo, "rev-parse", "HEAD"), None)

    assert result["raw_line"] == "PASS 1 FAIL 0 SKIP 0 EXIT 0"
    assert result["failed"] == 0


def test_run_gate_times_out_and_writes_nothing(repo: Path) -> None:
    # `sleep 30; echo` keeps sleep as a child of the shell: killing only the
    # shell would leave sleep holding the pipes open for 30s.
    start = time.monotonic()
    result = verification.run_gate(
        "echo 'PASS 1 FAIL 0 SKIP 0 EXIT 0'; sleep 30; echo done",
        repo,
        _git(repo, "rev-parse", "HEAD"),
        1,
        timeout=6,
    )
    elapsed = time.monotonic() - start

    assert result == {
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
    # The deadline tracks the `timeout` argument: waiting out the given 6s
    # (not some constant deadline of its own) and then returning promptly.
    assert 5 < elapsed < 10
    assert not (repo / RECORD_REL).exists()


def test_run_gate_times_out_when_the_child_closes_both_pipes_and_lingers(
    repo: Path,
) -> None:
    # The deadline bounds the process's exit, not just its output: a child
    # that closes stdout AND stderr hits EOF on both pipes immediately, so a
    # drain-only deadline would then wait 30s for the shell to exit.
    start = time.monotonic()
    result = verification.run_gate(
        "exec 1>&-; exec 2>&-; sleep 30",
        repo,
        _git(repo, "rev-parse", "HEAD"),
        1,
        timeout=1,
    )
    elapsed = time.monotonic() - start

    assert result == {
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
    # A 1s timeout returns in about 1s: paired with the 6s case above, no
    # single hardcoded deadline can satisfy both bounds.
    assert 0.5 < elapsed < 4
    assert not (repo / RECORD_REL).exists()


def test_run_gate_closes_the_child_pipes_before_returning(
    repo: Path,
    monkeypatch,
) -> None:
    real_popen = subprocess.Popen
    created: list[subprocess.Popen] = []

    def _spy(*args, **kwargs):
        proc = real_popen(*args, **kwargs)
        created.append(proc)
        return proc

    monkeypatch.setattr(verification.subprocess, "Popen", _spy)
    result = verification.run_gate(
        "echo 'PASS 1 FAIL 0 SKIP 0 EXIT 0'",
        repo,
        _git(repo, "rev-parse", "HEAD"),
        1,
    )

    assert result["passed"] == 1
    assert result["timed_out"] is False
    # `_dirty_outside_store`'s own `git` calls go through `subprocess.run`,
    # which also spawns via `Popen` - filter down to the gate's own shell
    # child, the only one started with shell=True.
    shell_procs = [
        proc
        for proc in created
        if getattr(proc, "args", None) == "echo 'PASS 1 FAIL 0 SKIP 0 EXIT 0'"
    ]
    assert len(shell_procs) == 1
    proc = shell_procs[0]
    assert proc.stdout is not None and proc.stdout.closed
    assert proc.stderr is not None and proc.stderr.closed


def test_run_gate_writes_last_verification_json_on_fresh_run(repo: Path) -> None:
    command = "echo 'PASS 7 FAIL 2 SKIP 1 EXIT 1'; exit 1"
    head = _git(repo, "rev-parse", "HEAD")
    result = verification.run_gate(command, repo, head, 4)

    assert result["exit"] == 1
    written = json.loads((repo / RECORD_REL).read_text())
    assert written == {
        "sha": head,
        "cycle": 4,
        "writer": "run_gate",
        "commands": [{"command": command, "exit": 1}],
        "passed": 7,
        "failed": 2,
        "skipped": 1,
    }


def test_run_gate_reports_the_process_exit_not_the_printed_one(
    repo: Path,
) -> None:
    # The command lies about its own status: the gate reports what the
    # process actually exited with.
    command = "echo 'PASS 1 FAIL 0 SKIP 0 EXIT 0'; exit 2"
    result = verification.run_gate(command, repo, _git(repo, "rev-parse", "HEAD"), 1)

    assert result["exit"] == 2
    assert result["passed"] == 1
    written = json.loads((repo / RECORD_REL).read_text())
    assert written["commands"] == [{"command": command, "exit": 2}]


def test_reuse_is_stale_when_the_gate_command_differs(repo: Path) -> None:
    head = _git(repo, "rev-parse", "HEAD")
    record = _record(head)  # recorded from "dev/bin/release-checks"

    same = verification.reuse_verdict(
        record, repo, head, gate_command="dev/bin/release-checks"
    )
    assert same == ("reused", record)
    other = verification.reuse_verdict(record, repo, head, gate_command="make test")
    assert other == ("stale", {})


def test_symbolic_sha_record_is_stale(repo: Path) -> None:
    head = _git(repo, "rev-parse", "HEAD")

    for symbolic in ("HEAD", "master", head[:12], head.upper()):
        verdict = verification.reuse_verdict(
            _record(symbolic), repo, head, gate_command="dev/bin/release-checks"
        )
        assert verdict == ("stale", {}), symbolic


def test_reuse_is_stale_not_raising_when_a_recorded_command_is_missing_or_null(
    repo: Path,
) -> None:
    head = _git(repo, "rev-parse", "HEAD")

    missing = _record(head)
    missing["commands"] = [{"exit": 0}]
    assert verification.reuse_verdict(missing, repo, head, gate_command=GATE) == ("stale", {})

    null = _record(head)
    null["commands"] = [{"command": None, "exit": 0}]
    assert verification.reuse_verdict(null, repo, head, gate_command=GATE) == ("stale", {})

    # Any other non-str command is stale too, not just None.
    for bad in ({"a": 1}, 1.5):
        odd = _record(head)
        odd["commands"] = [{"command": bad, "exit": 0}]
        assert verification.reuse_verdict(odd, repo, head, gate_command=GATE) == (
            "stale",
            {},
        ), bad


def test_run_gate_outside_a_git_repo_writes_no_record(tmp_path: Path) -> None:
    result = verification.run_gate(
        "echo 'PASS 1 FAIL 0 SKIP 0 EXIT 0'", tmp_path, "abc", 1
    )

    assert result["recorded"] is False
    assert result["dirty"] is True
    assert not (tmp_path / RECORD_REL).exists()


def test_run_gate_streams_stdout_and_stderr_to_the_log(
    repo: Path, tmp_path_factory
) -> None:
    log_path = tmp_path_factory.mktemp("log") / "gate.log"
    command = "echo 'out line'; echo 'err line' 1>&2; echo 'PASS 1 FAIL 0 SKIP 0 EXIT 0'"

    result = verification.run_gate(command, repo, _git(repo, "rev-parse", "HEAD"), 1, log_path=log_path)

    assert result["passed"] == 1
    logged = log_path.read_bytes()
    assert b"out line" in logged
    assert b"err line" in logged
    assert b"PASS 1 FAIL 0 SKIP 0 EXIT 0" in logged


def test_run_gate_writes_the_normalized_command(repo: Path) -> None:
    script = repo / "gate.sh"
    script.write_text("echo 'PASS 3 FAIL 0 SKIP 0 EXIT 0'\n")
    _git(repo, "add", "--", "gate.sh")
    _git(repo, "commit", "--no-verify", "-q", "-m", "add gate script")
    command = "bash  ./gate.sh   --quick"

    head = _git(repo, "rev-parse", "HEAD")
    result = verification.run_gate(command, repo, head, 2)

    assert result["passed"] == 3
    written = json.loads((repo / RECORD_REL).read_text())
    assert written == {
        "sha": head,
        "cycle": 2,
        "writer": "run_gate",
        "commands": [{"command": "bash ./gate.sh --quick", "exit": 0}],
        "passed": 3,
        "failed": 0,
        "skipped": 0,
    }


def _hold_gate_lock(repo: Path) -> int:
    """Takes the gate lock from outside run_gate, standing in for a
    concurrent run that already holds it."""
    path = repo / GATE_LOCK_REL
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(path, os.O_RDWR | os.O_CREAT)
    fcntl.flock(fd, fcntl.LOCK_EX)
    return fd


def _release_gate_lock(fd: int) -> None:
    fcntl.flock(fd, fcntl.LOCK_UN)
    os.close(fd)


def _gate_lock_is_free(repo: Path) -> bool:
    """True iff the gate lock can be taken at once (LOCK_NB), i.e. no
    run_gate call still holds it."""
    path = repo / GATE_LOCK_REL
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(path, os.O_RDWR | os.O_CREAT)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        fcntl.flock(fd, fcntl.LOCK_UN)
        return True
    except BlockingIOError:
        return False
    finally:
        os.close(fd)


def _wait_for(predicate, timeout: float = 10.0) -> None:
    deadline = time.monotonic() + timeout
    while not predicate():
        assert time.monotonic() < deadline, "condition never came true"
        time.sleep(0.05)


def _probed(repo: Path, probe: Path, command: str) -> str:
    """`command`, prefixed by a line appended to `probe` saying whether the
    record file existed when the gate's child started."""
    return (
        f"if test -e '{repo / RECORD_REL}'; then echo PRESENT; "
        f"else echo absent; fi >> '{probe}'; {command}"
    )


# A sha refusal: head-moved-shaped, not dirty, nothing recorded.
SHA_REFUSAL = {
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


def _start_gate(
    command: str, repo: Path, sha: str, cycle: int = 1, **kwargs
) -> tuple[threading.Thread, dict]:
    out: dict = {}

    def _run() -> None:
        out["result"] = verification.run_gate(command, repo, sha, cycle, **kwargs)

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()
    return thread, out


def test_failed_run_leaves_no_older_green_record(
    repo: Path, tmp_path_factory
) -> None:
    parent = _git(repo, "rev-parse", "HEAD")
    record = repo / RECORD_REL
    probe = tmp_path_factory.mktemp("probe") / "probe.txt"
    assert verification.run_gate(SUMMARY, repo, parent, 1)["recorded"] is True
    green = record.read_bytes()

    # A dirty-tree refusal never ran the gate, so it must not cost the record.
    (repo / "stray.txt").write_text("stray\n")
    refused = verification.run_gate(SUMMARY, repo, parent, 2)
    assert refused["dirty"] is True
    assert refused["recorded"] is False
    assert record.read_bytes() == green
    (repo / "stray.txt").unlink()

    # HEAD moves to a child commit while the parent's green record stays on
    # disk: a run at the child that fails without a summary line must not
    # leave that record behind, whatever sha the record itself names.
    head = _commit(repo, "src/next.py", "print(3)\n")
    failed = verification.run_gate(_probed(repo, probe, "echo boom; exit 1"), repo, head, 3)
    assert failed["exit"] == 1
    assert failed["recorded"] is False
    assert not record.exists()

    # Same for a run killed at its deadline...
    assert verification.run_gate(SUMMARY, repo, head, 4)["recorded"] is True
    timed_out = verification.run_gate(_probed(repo, probe, "sleep 5"), repo, head, 5, timeout=1)
    assert timed_out["timed_out"] is True
    assert not record.exists()

    # ...and for a run that dirtied the tree after the pre-spawn check passed.
    assert verification.run_gate(SUMMARY, repo, head, 6)["recorded"] is True
    dirty_cmd = _probed(repo, probe, f"echo d > src/d.py; {SUMMARY}")
    dirtied = verification.run_gate(dirty_cmd, repo, head, 7)
    assert dirtied["dirty"] is True
    assert dirtied["recorded"] is False
    assert not record.exists()

    # The record was already gone WHILE each child ran, not only afterwards.
    assert probe.read_text().split() == ["absent", "absent", "absent"]


def test_gate_lock_wait_expires_without_running_the_gate(repo: Path) -> None:
    # The lock wait is bounded by the gate's own timeout: a holder that
    # never lets go must not block run_gate forever.
    head = _git(repo, "rev-parse", "HEAD")
    fd = _hold_gate_lock(repo)
    try:
        result = verification.run_gate(SUMMARY, repo, head, 1, timeout=0.2)
    finally:
        _release_gate_lock(fd)

    assert result == verification._lock_timeout_result()
    assert not (repo / RECORD_REL).exists()
    # The expiry released nothing it never held.
    assert _gate_lock_is_free(repo)


def test_concurrent_runs_serialize_on_the_gate_lock(
    repo: Path, tmp_path_factory
) -> None:
    head = _git(repo, "rev-parse", "HEAD")
    record = repo / RECORD_REL
    marks = tmp_path_factory.mktemp("marks") / "marks.txt"

    def _command(n: int, hold: int) -> str:
        return (
            f"echo start-{n} >> '{marks}'; sleep {hold}; "
            f"if test -e '{record}'; then echo present-{n} >> '{marks}'; fi; "
            f"echo end-{n} >> '{marks}'; {SUMMARY}"
        )

    # The first run holds the lock for 5s, longer than any wait-then-go-ahead
    # fallback; the second only starts once the first's child is running.
    first, first_out = _start_gate(_command(1, 5), repo, head, cycle=1)
    _wait_for(marks.exists)
    second, second_out = _start_gate(_command(2, 1), repo, head, cycle=2)
    first.join(timeout=30)
    second.join(timeout=30)

    assert not first.is_alive() and not second.is_alive()
    # No interleaving, and no "present-2": the first run's record write landed
    # before the second run took the lock and invalidated it, never during
    # the second run's child.
    assert marks.read_text().split() == ["start-1", "end-1", "start-2", "end-2"]
    assert first_out["result"]["recorded"] is True
    assert second_out["result"]["recorded"] is True
    written = json.loads(record.read_text())
    assert (written["sha"], written["cycle"]) == (head, 2)


def test_held_gate_lock_blocks_before_the_log_open_and_record_delete(
    repo: Path, tmp_path_factory
) -> None:
    head = _git(repo, "rev-parse", "HEAD")
    record = repo / RECORD_REL
    assert verification.run_gate(SUMMARY, repo, head, 1)["recorded"] is True
    green = record.read_bytes()
    log_path = tmp_path_factory.mktemp("log") / "gate.log"
    log_path.write_bytes(b"previous run\n")

    fd = _hold_gate_lock(repo)
    try:
        thread, out = _start_gate(SUMMARY, repo, head, log_path=log_path)
        # 5s: longer than any plausible wait-then-run-anyway fallback.
        thread.join(timeout=5.0)
        # Still waiting, and nothing the lock protects has been touched yet.
        assert thread.is_alive()
        assert log_path.read_bytes() == b"previous run\n"
        assert record.read_bytes() == green
    finally:
        _release_gate_lock(fd)
    thread.join(timeout=10)

    assert not thread.is_alive()
    assert out["result"]["recorded"] is True
    assert b"PASS 1 FAIL 0 SKIP 0 EXIT 0" in log_path.read_bytes()
    assert b"previous run" not in log_path.read_bytes()


@pytest.mark.parametrize("move", ["advance", "rewind"])
def test_run_gate_refuses_a_sha_that_head_moved_past_while_waiting_for_the_lock(
    repo: Path, tmp_path_factory, move: str
) -> None:
    # The caller captures HEAD before run_gate takes the lock; HEAD then
    # moves (forward to a new commit, or back to the parent) while run_gate
    # waits on the lock held by another run.
    captured = _commit(repo, "src/second.py", "print(2)\n")
    record = repo / RECORD_REL
    assert verification.run_gate(SUMMARY, repo, captured, 1)["recorded"] is True
    green = record.read_bytes()
    ran = tmp_path_factory.mktemp("ran") / "ran.txt"

    fd = _hold_gate_lock(repo)
    try:
        thread, out = _start_gate(f"echo ran > '{ran}'; {SUMMARY}", repo, captured)
        thread.join(timeout=1.0)
        assert thread.is_alive()
        if move == "advance":
            _commit(repo, "src/later.py", "print(3)\n")
        else:
            _git(repo, "reset", "--hard", "-q", "HEAD~1")
        moved = _git(repo, "rev-parse", "HEAD")
    finally:
        _release_gate_lock(fd)
    thread.join(timeout=10)

    assert not thread.is_alive()
    assert moved != captured
    # Head-moved refusal shape, not dirty; the gate never ran and the
    # older record (never invalidated on a refusal) is untouched.
    assert out["result"] == SHA_REFUSAL
    assert not ran.exists()
    assert record.read_bytes() == green
    # The refusal released the lock on its way out.
    assert _gate_lock_is_free(repo)


def test_run_gate_refuses_a_sha_argument_that_is_already_behind_head(
    repo: Path, tmp_path_factory
) -> None:
    # No lock contention and nothing moves during the call: the sha argument
    # alone is stale against HEAD when run_gate starts.
    stale = _git(repo, "rev-parse", "HEAD")
    head = _commit(repo, "src/later.py", "print(2)\n")
    record = repo / RECORD_REL
    assert verification.run_gate(SUMMARY, repo, head, 1)["recorded"] is True
    green = record.read_bytes()
    ran = tmp_path_factory.mktemp("ran") / "ran.txt"

    result = verification.run_gate(f"echo ran > '{ran}'; {SUMMARY}", repo, stale, 2)

    assert result == SHA_REFUSAL
    assert not ran.exists()
    assert record.read_bytes() == green
    # The lock is free at once, and the next call at the real HEAD runs.
    assert _gate_lock_is_free(repo)
    assert verification.run_gate(SUMMARY, repo, head, 3)["recorded"] is True
