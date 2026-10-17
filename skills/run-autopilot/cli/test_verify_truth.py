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
import random
import shlex
import signal
import subprocess
import sys
import threading
import time
from contextlib import contextmanager
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


class _StraySignal(Exception):
    """A signal reached the test's own fallback handler: no handler in the
    code under test was installed for it (and the default action would
    have killed or interrupted the pytest process itself)."""


@contextmanager
def _stray_signals_raise(*signums: int):
    def raise_stray(signum, frame):
        raise _StraySignal(signal.Signals(signum).name)

    old = {signum: signal.signal(signum, raise_stray) for signum in signums}
    try:
        yield
    finally:
        for signum, handler in old.items():
            signal.signal(signum, handler)


def _popen_then_signal(spawned: list, signum: int):
    """A Popen that delivers `signum` to this process right after the
    gate's own spawn returns, before `_spawn_gate` sees the handle. Only
    the gate's spawn uses start_new_session; git calls pass untouched."""
    real_popen = subprocess.Popen

    def fake(*args, **kwargs):
        proc = real_popen(*args, **kwargs)
        if kwargs.get("start_new_session"):
            spawned.append(proc)
            os.kill(os.getpid(), signum)
        return proc

    return fake


def _kill_spawned(spawned: list) -> None:
    for proc in spawned:
        if _group_alive(proc.pid):
            os.killpg(proc.pid, signal.SIGKILL)
        proc.wait()


def _group_gate_command(tmp_path: Path) -> tuple[str, Path]:
    gate = tmp_path / "group_gate.py"
    gate.write_text(GROUP_GATE)
    pgid_file = tmp_path / "gate.pgid"
    command = " ".join(
        shlex.quote(part) for part in (sys.executable, str(gate), str(pgid_file))
    )
    return command, pgid_file


def _lock_free(lock_path: Path) -> bool:
    fd = os.open(lock_path, os.O_RDWR | os.O_CREAT)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        return False
    finally:
        os.close(fd)
    return True


def _hold_lock(repo: Path, seconds: float) -> tuple[int, threading.Timer]:
    """Takes the gate lock on a separate open file description and
    releases it after `seconds` from a timer thread."""
    lock_path = repo / verification.GATE_LOCK_REL
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    held = os.open(lock_path, os.O_RDWR | os.O_CREAT)
    fcntl.flock(held, fcntl.LOCK_EX)
    release = threading.Timer(seconds, fcntl.flock, (held, fcntl.LOCK_UN))
    release.start()
    return held, release


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


def test_exit_token_drop_record_not_reused(repo: Path) -> None:
    # The summary says EXIT 1 but the gate's own process exits 0 (FAIL 0, so
    # the failure only shows up in the EXIT token). The written record must
    # not be eligible for reuse on a later cycle: reuse eligibility has to
    # treat EXIT 1 as a failure, not just the FAIL count.
    head = _git(repo, "rev-parse", "HEAD")
    command = "printf 'PASS 4 FAIL 0 SKIP 0 EXIT 1\\n'"

    result = verification.run_gate(command, repo, head, 1)

    assert result["recorded"] is True
    record = json.loads((repo / verification.RECORD_REL).read_text())

    verdict, _ = verification.reuse_verdict(record, repo, head, gate_command=command)
    assert verdict == "stale"


def test_sigint_during_spawn_kills_the_gate(
    repo: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # A real SIGINT landing while Popen() is still spawning the gate (before
    # `gate_started` is set) must reach the gate's own signal guard, like
    # SIGTERM: the gate group dies and run_gate raises the guard's error,
    # not a bare interrupt. The fallback handler turns an unguarded SIGINT
    # into _StraySignal instead of a KeyboardInterrupt that aborts pytest.
    head = _git(repo, "rev-parse", "HEAD")
    spawned: list[subprocess.Popen] = []
    monkeypatch.setattr(
        verification.subprocess,
        "Popen",
        _popen_then_signal(spawned, signal.SIGINT),
    )

    try:
        with _stray_signals_raise(signal.SIGINT):
            with pytest.raises(RuntimeError) as info:
                verification.run_gate("sleep 60", repo, head, 1)

        assert str(info.value) == "verify: SIGINT during gate"
        assert spawned, "the gate's Popen call never ran"
        pgid = spawned[0].pid  # start_new_session makes the child its own pgid
        assert _wait_for(lambda: not _group_alive(pgid), 2.0), (
            "gate group still alive 2s after SIGINT during spawn"
        )
    finally:
        _kill_spawned(spawned)


def _interrupt_one_gate(
    repo: Path,
    head: str,
    marker: Path,
    delay: float,
) -> BaseException | None:
    """Runs one gate that records its pgid in `marker` and sends this
    process SIGINT `delay` seconds in. Returns what run_gate raised."""
    command = f"echo $$ > {shlex.quote(str(marker))}; exec sleep 60"
    timer = threading.Timer(delay, os.kill, (os.getpid(), signal.SIGINT))
    try:
        try:
            timer.start()
            verification.run_gate(command, repo, head, 1, timeout=5)
        finally:
            timer.join()
            time.sleep(0.001)  # run a pending handler inside the try
    except BaseException as exc:
        return exc
    return None


def test_sigint_storm_leaks_no_gate(repo: Path, tmp_path: Path) -> None:
    # 100 interrupts, each at a random point of a run_gate call (lock wait,
    # git checks, spawn, drain). Every gate that got far enough to record
    # its pgid must be dead afterward, and every such run must have ended
    # through the guard's error, not a stray interrupt.
    head = _git(repo, "rev-parse", "HEAD")
    markers = tmp_path / "storm"
    markers.mkdir()
    rng = random.Random(311)
    outcomes: list[tuple[Path, BaseException | None]] = []
    started = time.monotonic()
    try:
        with _stray_signals_raise(signal.SIGINT):
            for trial in range(100):
                if time.monotonic() - started > 20:
                    break
                marker = markers / f"{trial}.pgid"
                delay = rng.uniform(0.0, 0.08)
                outcomes.append(
                    (marker, _interrupt_one_gate(repo, head, marker, delay))
                )
        elapsed = time.monotonic() - started
        time.sleep(0.5)  # a leaked gate's shell writes its pgid well within this
        pgids = {
            path: int(text)
            for path in markers.iterdir()
            if (text := path.read_text().strip())
        }
        assert len(outcomes) == 100 and elapsed < 20, (
            f"{len(outcomes)} trials in {elapsed:.1f}s"
        )
        assert [pgid for pgid in pgids.values() if _group_alive(pgid)] == []
        for marker, caught in outcomes:
            assert caught is not None, f"{marker.name}: the interrupt never landed"
            if marker in pgids:
                assert isinstance(caught, RuntimeError), repr(caught)
                assert str(caught) == "verify: SIGINT during gate"
    finally:
        for path in markers.iterdir():
            text = path.read_text().strip()
            if text and _group_alive(int(text)):
                os.killpg(int(text), signal.SIGKILL)


def test_sigterm_pending_before_gate_started_kills_the_gate(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # SIGTERM delivered while `gate_started` is still False (before Popen()
    # returns to `_spawn_gate`): `_raise_on_sigterm` only sets
    # `sigterm_pending`; the raise happens right after Popen returns,
    # inside the try that `_kill_gate` guards, so the gate still gets
    # killed.
    head = _git(repo, "rev-parse", "HEAD")
    real_popen = subprocess.Popen
    spawned: list[subprocess.Popen] = []

    def popen_then_sigterm(*args, **kwargs):
        proc = real_popen(*args, **kwargs)
        # Only the gate's own spawn uses start_new_session: the git calls
        # `run_gate` makes for its dirty/HEAD checks must pass through
        # untouched, or this signal fires outside the protected window
        # entirely (no handler installed yet) and kills the test process.
        if kwargs.get("start_new_session"):
            spawned.append(proc)
            os.kill(os.getpid(), signal.SIGTERM)
        return proc

    monkeypatch.setattr(verification.subprocess, "Popen", popen_then_sigterm)

    try:
        with pytest.raises(RuntimeError, match="SIGTERM during gate"):
            verification.run_gate("sleep 60", repo, head, 1)

        assert spawned, "the gate's Popen call never ran"
        pgid = spawned[0].pid
        assert _wait_for(lambda: not _group_alive(pgid), 2.0), (
            "gate group still alive 2s after pending SIGTERM"
        )
    finally:
        for proc in spawned:
            if _group_alive(proc.pid):
                os.killpg(proc.pid, signal.SIGKILL)
            proc.wait()


def test_sighup_before_spawn_kills_the_gate(
    repo: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # The SIGTERM-pending shape above, for SIGHUP (a closed terminal):
    # delivered while `gate_started` is still False, it is recorded as
    # pending and raised right after Popen returns, so the gate still dies.
    # Unguarded, the fallback handler raises _StraySignal instead of letting
    # SIGHUP's default action kill pytest.
    head = _git(repo, "rev-parse", "HEAD")
    spawned: list[subprocess.Popen] = []
    monkeypatch.setattr(
        verification.subprocess,
        "Popen",
        _popen_then_signal(spawned, signal.SIGHUP),
    )

    try:
        with _stray_signals_raise(signal.SIGHUP):
            with pytest.raises(RuntimeError) as info:
                verification.run_gate("sleep 60", repo, head, 1)

        assert str(info.value) == "verify: SIGHUP during gate"
        assert spawned, "the gate's Popen call never ran"
        pgid = spawned[0].pid
        assert _wait_for(lambda: not _group_alive(pgid), 2.0), (
            "gate group still alive 2s after pending SIGHUP"
        )
    finally:
        _kill_spawned(spawned)


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


def test_sighup_kills_the_gate_group_and_frees_the_lock(
    repo: Path,
    tmp_path: Path,
) -> None:
    command, pgid_file = _group_gate_command(tmp_path)

    verify = subprocess.Popen(
        _verify_argv(repo, command),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    pgid = None
    try:
        assert _wait_for(pgid_file.exists, 15), "gate never started"
        pgid = int(pgid_file.read_text())
        assert _group_alive(pgid)

        verify.send_signal(signal.SIGHUP)
        assert _wait_for(lambda: not _group_alive(pgid), 2.0), (
            "gate group still alive 2s after SIGHUP"
        )
        lock_path = repo / verification.GATE_LOCK_REL
        assert _wait_for(lambda: _lock_free(lock_path), 1.0), (
            "gate lock still held 1s after the gate group died"
        )
        stdout, _ = verify.communicate(timeout=15)
    finally:
        if verify.poll() is None:
            verify.kill()
            verify.communicate()
        verify.wait()
        if pgid is not None and _group_alive(pgid):
            os.killpg(pgid, signal.SIGKILL)

    # The JSON line names the signal that arrived, not a fixed one.
    lines = [line for line in stdout.splitlines() if line.strip()]
    assert len(lines) == 1, stdout
    payload = json.loads(lines[0])
    assert payload["error"] == "verify: SIGHUP during gate"
    assert payload["exit"] == 2
    assert verify.returncode == 2


def test_signal_exit_prints_one_json_line(repo: Path, tmp_path: Path) -> None:
    head = _git(repo, "rev-parse", "HEAD")
    command, pgid_file = _group_gate_command(tmp_path)

    verify = subprocess.Popen(
        _verify_argv(repo, command),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    pgid = None
    try:
        assert _wait_for(pgid_file.exists, 15), "gate never started"
        pgid = int(pgid_file.read_text())
        verify.send_signal(signal.SIGTERM)
        stdout, stderr = verify.communicate(timeout=15)
    finally:
        if verify.poll() is None:
            verify.kill()
            verify.communicate()
        if pgid is not None and _group_alive(pgid):
            os.killpg(pgid, signal.SIGKILL)

    lines = [line for line in stdout.splitlines() if line.strip()]
    assert len(lines) == 1, stdout
    payload = json.loads(lines[0])
    assert payload["error"] == "verify: SIGTERM during gate"
    assert payload["exit"] == 2
    # The log was opened before the gate spawned, so it exists.
    assert payload["log"] == str(repo / "docs/dev/tmp" / f"gate-{head[:7]}.log")
    assert verify.returncode == 2
    assert "Traceback" not in stderr, stderr


def test_signal_exit_reports_the_custom_log_path(repo: Path, tmp_path: Path) -> None:
    # With --log, the signal's JSON line names that log, not the default
    # gate-<sha7>.log; SIGINT here also proves the name follows the signal.
    head = _git(repo, "rev-parse", "HEAD")
    command, pgid_file = _group_gate_command(tmp_path)
    custom = "docs/dev/tmp/custom-signal-gate.log"

    verify = subprocess.Popen(
        _verify_argv(repo, command, "--log", custom),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    pgid = None
    try:
        assert _wait_for(pgid_file.exists, 15), "gate never started"
        pgid = int(pgid_file.read_text())
        verify.send_signal(signal.SIGINT)
        stdout, stderr = verify.communicate(timeout=15)
    finally:
        if verify.poll() is None:
            verify.kill()
            verify.communicate()
        if pgid is not None and _group_alive(pgid):
            os.killpg(pgid, signal.SIGKILL)

    lines = [line for line in stdout.splitlines() if line.strip()]
    assert len(lines) == 1, stdout
    payload = json.loads(lines[0])
    assert payload["error"] == "verify: SIGINT during gate"
    assert payload["exit"] == 2
    assert payload["log"] == str(repo / custom)
    assert (repo / custom).exists()
    assert not (repo / "docs/dev/tmp" / f"gate-{head[:7]}.log").exists()
    assert verify.returncode == 2
    assert "Traceback" not in stderr, stderr


@pytest.mark.parametrize(
    ("signum", "expected"),
    [
        (signal.SIGTERM, "verify: SIGTERM during gate"),
        (signal.SIGINT, "verify: SIGINT during gate"),
        (signal.SIGHUP, "verify: SIGHUP during gate"),
        # Never guarded, so only this direct call reaches it: the name
        # still comes from the number, not a fixed fallback.
        (signal.SIGUSR1, "verify: SIGUSR1 during gate"),
    ],
    ids=["SIGTERM", "SIGINT", "SIGHUP", "SIGUSR1"],
)
def test_signal_error_names_the_signal_it_got(signum: int, expected: str) -> None:
    err = verification._signal_error(signum)

    assert isinstance(err, RuntimeError)
    assert str(err) == expected


def test_sigterm_during_cleanup_does_not_leak(
    repo: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # A second SIGTERM lands inside the cleanup itself (`_kill_gate`'s
    # killpg/wait window). It must not abort the cleanup: the gate group
    # still dies and the lock still frees.
    head = _git(repo, "rev-parse", "HEAD")
    command, pgid_file = _group_gate_command(tmp_path)
    original = verification._kill_gate

    def kill_gate_under_second_sigterm(*args, **kwargs):
        os.kill(os.getpid(), signal.SIGTERM)
        return original(*args, **kwargs)

    monkeypatch.setattr(verification, "_kill_gate", kill_gate_under_second_sigterm)
    sender = threading.Thread(
        target=lambda: (
            _wait_for(pgid_file.exists, 15) and os.kill(os.getpid(), signal.SIGTERM)
        ),
    )
    try:
        with _stray_signals_raise(signal.SIGTERM):
            sender.start()
            with pytest.raises(RuntimeError, match="SIGTERM during gate"):
                verification.run_gate(command, repo, head, 1, timeout=30)
            sender.join()

        pgid = int(pgid_file.read_text())
        assert _wait_for(lambda: not _group_alive(pgid), 2.0), (
            "gate group still alive 2s after a SIGTERM during cleanup"
        )
        lock_path = repo / verification.GATE_LOCK_REL
        assert _wait_for(lambda: _lock_free(lock_path), 1.0)
    finally:
        sender.join()
        if pgid_file.exists() and _group_alive(int(pgid_file.read_text())):
            os.killpg(int(pgid_file.read_text()), signal.SIGKILL)


# The lock-wait tests (lock_timeout, head_moved, waited_s) live in the
# sibling test_verify_truth_lock.py: this file sits at the 800-line limit.


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
            f"{int(verification.GATE_LOCK_TIMEOUT_S)}s)",
        ),
        (
            _refusal(head_moved=True, dirty_paths=["src/foo.py"]),
            "Tests: (gate skipped: HEAD moved during the lock wait)",
        ),
    ]
    for fake, expected in cases:
        monkeypatch.setattr(verification, "run_gate", lambda *a, _r=fake, **k: _r)

        out = review_stage.run_gate_line(repo, GATE, "1")

        assert out["tests_line"] == expected
        assert out.get("dirty_paths") == fake["dirty_paths"]


def test_record_keeps_true_failed_and_summary_exit(repo: Path) -> None:
    # The summary line's own EXIT token (1) disagrees with its FAIL count
    # (0): the gate's process exits 0. The caller-facing `result["failed"]`
    # must stay the true parsed count (0) -- only the PERSISTED record is
    # forced non-zero, and it must also carry the dropped EXIT token
    # explicitly as `summary_exit`, not only as a folded `failed`.
    head = _git(repo, "rev-parse", "HEAD")
    command = "printf 'PASS 4 FAIL 0 SKIP 0 EXIT 1\\n'"

    result = verification.run_gate(command, repo, head, 1)

    assert result["recorded"] is True
    assert result["failed"] == 0

    record = json.loads((repo / verification.RECORD_REL).read_text())
    assert record["failed"] != 0
    assert record["summary_exit"] == 1


def test_exit_2_json_error_carries_the_stderr_prefix(tmp_path: Path) -> None:
    # Every exit-2 refusal's stderr line is prefixed "autopilot: verify: ".
    # The JSON line on stdout -- the one a caller actually parses -- must
    # carry the same prefix in its "error" field, not a bare message that
    # silently drops the context stderr already names.
    empty = tmp_path / "empty"
    empty.mkdir()
    _git(empty, "init", "-q")

    proc = _run_verify(empty, "echo 'PASS 1 FAIL 0 SKIP 0 EXIT 0'")

    assert proc.returncode == 2
    lines = proc.stdout.splitlines()
    assert len(lines) == 1, proc.stdout
    payload = json.loads(lines[0])
    assert payload["error"].startswith("autopilot: verify: "), payload
