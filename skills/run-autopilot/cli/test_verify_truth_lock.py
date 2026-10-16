#!/usr/bin/env python3
"""Regression pins for PRD 00322's lock budget (split from
test_verify_truth.py, which sits at the 800-line limit): the lock wait has
its own `lock_timeout`, separate from the gate's `timeout`; every result
says how long the lock wait took (`waited_s`); and a signal that lands
around the lock wait or the pre-spawn checks is never swallowed by a
refusal result.

Same fixtures as test_verify_truth.py: a real temporary git repo and an
inline shell gate.
"""

from __future__ import annotations

import fcntl
import inspect
import os
import signal
import time
from pathlib import Path

import pytest

from cli import verification
from cli.test_verify_truth import (
    _commit,
    _git,
    _hold_lock,
    _lock_free,
    _stray_signals_raise,
    _StraySignal,
)

PASS_GATE = "echo 'PASS 1 FAIL 0 SKIP 0 EXIT 0'"


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    # test_verify_truth.py's fixture shape: the repo sits one level down so
    # files beside it in tmp_path never count as dirt inside it.
    root = tmp_path / "repo"
    root.mkdir()
    _git(root, "init", "-q")
    _commit(root, "src/app.py", "print(1)\n")
    return root


def test_lock_wait_expiry_reports_lock_timeout(repo: Path) -> None:
    # The lock is held throughout. The wait ends at `lock_timeout` (0.3s),
    # not at the gate's own 60s `timeout`.
    head = _git(repo, "rev-parse", "HEAD")
    lock_path = repo / verification.GATE_LOCK_REL
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    log_path = repo / "docs" / "dev" / "tmp" / "gate-lock-timeout.log"
    held = os.open(lock_path, os.O_RDWR | os.O_CREAT)
    try:
        fcntl.flock(held, fcntl.LOCK_EX)
        started = time.monotonic()
        result = verification.run_gate(
            PASS_GATE,
            repo,
            head,
            1,
            timeout=60,
            log_path=log_path,
            lock_timeout=0.3,
        )
        elapsed = time.monotonic() - started
    finally:
        fcntl.flock(held, fcntl.LOCK_UN)
        os.close(held)

    assert result.get("lock_timeout") is True
    assert result["timed_out"] is False
    assert not log_path.exists()
    assert elapsed < 5, f"lock wait ran past lock_timeout: {elapsed:.1f}s"
    assert isinstance(result["waited_s"], float)
    assert 0.25 <= result["waited_s"] < 1.5, result["waited_s"]


def test_late_waiter_gate_gets_full_timeout(repo: Path) -> None:
    # The lock wait has its own budget: a gate that gets the lock 3s into a
    # 4s lock wait still gets its whole 2s run, so a 1.5s gate finishes.
    # Neither a 2s nor a 4s deadline shared with the lock wait allows that.
    head = _git(repo, "rev-parse", "HEAD")
    held, release = _hold_lock(repo, 3.0)
    try:
        result = verification.run_gate(
            "sleep 1.5; echo 'PASS 1 FAIL 0 SKIP 0 EXIT 0'",
            repo,
            head,
            1,
            timeout=2,
            lock_timeout=4,
        )
    finally:
        release.join()
        os.close(held)

    assert result["lock_timeout"] is False
    assert result["timed_out"] is False
    assert result["passed"] == 1
    assert 2.8 <= result["waited_s"] < 3.6, result["waited_s"]


def test_result_reports_waited_s(repo: Path) -> None:
    # The lock is held ~1s, then the gate is killed at its own 0.5s
    # timeout: `waited_s` is the lock wait alone, not the wait plus the run.
    head = _git(repo, "rev-parse", "HEAD")
    held, release = _hold_lock(repo, 1.0)
    try:
        result = verification.run_gate(
            "sleep 30",
            repo,
            head,
            1,
            timeout=0.5,
            lock_timeout=5,
        )
    finally:
        release.join()
        os.close(held)

    assert result["timed_out"] is True
    assert isinstance(result["waited_s"], float)
    assert 0.8 <= result["waited_s"] < 1.4, result["waited_s"]


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

    result = verification.run_gate(PASS_GATE, repo, head, 1)

    assert result.get("head_moved") is True
    assert result["dirty"] is False
    # Every result shape carries the lock wait, refusals included; this one
    # also spans the commit made inside the patched lock wait.
    assert isinstance(result["waited_s"], float)
    assert 0.0 <= result["waited_s"] < 2.0, result["waited_s"]


def test_default_lock_budget_is_its_own_not_the_gate_timeout(repo: Path) -> None:
    # PRD 00322: `lock_timeout: float = GATE_LOCK_TIMEOUT_S` (600). The
    # default is bound into the signature, so a monkeypatched constant
    # cannot shorten it; the value and the binding are pinned directly. A
    # call that leaves lock_timeout unset then waits out a 2s hold even
    # though its gate timeout is 1s.
    assert verification.GATE_LOCK_TIMEOUT_S == 600
    params = inspect.signature(verification.run_gate).parameters
    assert params["lock_timeout"].default == verification.GATE_LOCK_TIMEOUT_S

    head = _git(repo, "rev-parse", "HEAD")
    held, release = _hold_lock(repo, 2.0)
    try:
        result = verification.run_gate(PASS_GATE, repo, head, 1, timeout=1)
    finally:
        release.join()
        os.close(held)

    assert result["lock_timeout"] is False
    assert result["timed_out"] is False
    assert result["passed"] == 1
    assert 1.8 <= result["waited_s"] < 2.6, result["waited_s"]


def _run_uncontended(repo: Path, shape: str) -> dict:
    head = _git(repo, "rev-parse", "HEAD")
    if shape == "pre_spawn_dirty":
        (repo / "src" / "stray.py").write_text("print('dirty')\n")
    if shape == "post_reap_dirty":
        return verification.run_gate(f"echo x > src/late.py; {PASS_GATE}", repo, head, 1)
    if shape == "timed_out":
        return verification.run_gate("sleep 30", repo, head, 1, timeout=0.3)
    return verification.run_gate(PASS_GATE, repo, head, 1)


@pytest.mark.parametrize(
    ("shape", "expected"),
    [
        ("recorded", {"recorded": True, "dirty": False, "exit": 0}),
        ("pre_spawn_dirty", {"recorded": False, "dirty": True, "exit": None}),
        ("post_reap_dirty", {"recorded": False, "dirty": True, "exit": 0}),
        ("timed_out", {"recorded": False, "timed_out": True, "exit": None}),
    ],
)
def test_every_result_shape_carries_waited_s(
    repo: Path, shape: str, expected: dict
) -> None:
    # No one holds the lock, so every shape reports a near-zero wait: a
    # fixed value, or a field present on only one shape, fails here.
    result = _run_uncontended(repo, shape)

    assert {key: result[key] for key in expected} == expected
    assert isinstance(result["waited_s"], float)
    assert 0.0 <= result["waited_s"] < 0.3, result["waited_s"]


@pytest.mark.parametrize("refusal", ["lock_timeout", "dirty", "head_moved"])
def test_signal_before_a_refusal_is_not_swallowed(
    repo: Path, monkeypatch: pytest.MonkeyPatch, refusal: str
) -> None:
    # A SIGTERM that lands as the lock wait ends, before the refusal result
    # is built, still ends the call: it reaches the handler installed before
    # run_gate (here the test's fallback, _StraySignal), or a guard turns it
    # into "verify: SIGTERM during gate". Returning the refusal as if
    # nothing happened would drop a supervisor's kill. The lock frees
    # either way.
    head = _git(repo, "rev-parse", "HEAD")
    original = verification._acquire_lock

    def acquire_then_signal(lock_fd: int, deadline: float) -> bool:
        acquired = original(lock_fd, deadline)
        if refusal == "head_moved":
            _commit(repo, "src/other.py", "print(2)\n")
        os.kill(os.getpid(), signal.SIGTERM)
        return acquired

    monkeypatch.setattr(verification, "_acquire_lock", acquire_then_signal)
    if refusal == "dirty":
        (repo / "src" / "stray.py").write_text("print('dirty')\n")
    held = release = None
    kwargs: dict = {}
    if refusal == "lock_timeout":
        held, release = _hold_lock(repo, 1.0)
        kwargs = {"lock_timeout": 0.3}
    try:
        with _stray_signals_raise(signal.SIGTERM):
            with pytest.raises((_StraySignal, RuntimeError)) as info:
                verification.run_gate(PASS_GATE, repo, head, 1, timeout=30, **kwargs)
    finally:
        if release is not None:
            release.join()
            os.close(held)

    if not isinstance(info.value, _StraySignal):
        assert str(info.value) == "verify: SIGTERM during gate"
    assert _lock_free(repo / verification.GATE_LOCK_REL)
