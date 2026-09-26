"""Port of the `test_autoclaude_watchdog.sh` contract (PRD 00106).

The bash suite's sections map here as: A (under the cap nothing is
signaled; the sidecar returns when the child dies), B (over the cap a
TERM-obeying child dies by SIGTERM), C (a TERM-immune child is
KILL-escalated after the grace). The bash comm-resolution rows
(claude_immune invisible, bystanders untouched) are retired by
construction: the watchdog holds the Popen handle and can signal
nothing else.
"""

from __future__ import annotations

import signal
import subprocess
import sys
import time

from cli.watchdog import Watchdog


def _spawn_sleeper(secs: float = 300) -> subprocess.Popen:
    return subprocess.Popen([sys.executable, "-c", f"import time; time.sleep({secs})"])


def _spawn_term_immune() -> subprocess.Popen:
    code = (
        "import signal, time\n"
        "signal.signal(signal.SIGTERM, signal.SIG_IGN)\n"
        "print('armed', flush=True)\n"
        "time.sleep(300)\n"
    )
    proc = subprocess.Popen([sys.executable, "-c", code], stdout=subprocess.PIPE)
    assert proc.stdout is not None
    proc.stdout.readline()  # handler installed before the cap can fire
    return proc


def test_under_cap_child_untouched_and_watchdog_returns_on_exit():
    proc = _spawn_sleeper(0.3)
    dog = Watchdog(proc, cap_secs=60, grace_secs=1).start()
    proc.wait(timeout=10)
    dog.cancel()
    assert dog.fired is False
    # A negative returncode would mean the watchdog signaled it.
    assert proc.returncode == 0


def test_over_cap_term_obeying_child_dies_by_sigterm():
    proc = _spawn_sleeper(300)
    dog = Watchdog(proc, cap_secs=0.2, grace_secs=5).start()
    proc.wait(timeout=10)
    dog.cancel()
    assert dog.fired is True
    assert proc.returncode == -signal.SIGTERM


def test_term_immune_child_is_kill_escalated_after_grace():
    proc = _spawn_term_immune()
    dog = Watchdog(proc, cap_secs=0.2, grace_secs=0.3).start()
    proc.wait(timeout=10)
    dog.cancel()
    assert dog.fired is True
    assert proc.returncode == -signal.SIGKILL


def test_cancel_disarms_a_pending_cap():
    proc = _spawn_sleeper(300)
    dog = Watchdog(proc, cap_secs=60, grace_secs=1).start()
    # The loop's post-exit path: the session is being torn down by its
    # owner, not by the cap.
    proc.terminate()
    proc.wait(timeout=10)
    dog.cancel()
    assert dog.fired is False


def test_cap_messages_name_term_then_kill(capsys):
    proc = _spawn_term_immune()
    dog = Watchdog(proc, cap_secs=0.2, grace_secs=0.3).start()
    proc.wait(timeout=10)
    dog.cancel()
    err = capsys.readouterr().err
    assert "wall-clock cap; SIGTERM (session cap)." in err
    assert "ignored SIGTERM; SIGKILL (session cap)." in err


def test_watchdog_never_fires_for_a_fast_child():
    proc = _spawn_sleeper(0.1)
    dog = Watchdog(proc, cap_secs=30, grace_secs=1).start()
    proc.wait(timeout=10)
    dog.cancel()
    dog.cancel()  # second cancel is a no-op, not a re-signal
    assert dog.fired is False


def _wait_watchdog_settled(dog: Watchdog, secs: float = 5.0) -> None:
    deadline = time.monotonic() + secs
    while dog._thread.is_alive() and time.monotonic() < deadline:
        time.sleep(0.02)


def test_thread_exits_after_child_death_without_cancel():
    # The bash sidecar exited when the child died even if nobody killed
    # the sidecar; the thread must not linger either.
    proc = _spawn_sleeper(0.1)
    dog = Watchdog(proc, cap_secs=30, grace_secs=1).start()
    proc.wait(timeout=10)
    _wait_watchdog_settled(dog)
    assert dog._thread.is_alive() is False


# The warning window (2026-09-26): a session that reaches cap minus warn is
# told to hand off at its next task boundary; the cap itself is unchanged.


def test_warn_callback_fires_before_the_cap_and_the_cap_still_terms():
    proc = _spawn_sleeper(300)
    seen: list[float] = []
    dog = Watchdog(
        proc, cap_secs=0.8, grace_secs=5, warn_secs=0.4, on_warn=lambda: seen.append(1)
    ).start()
    proc.wait(timeout=10)
    dog.cancel()
    assert seen == [1]
    assert dog.warned is True
    assert dog.fired is True
    assert proc.returncode == -signal.SIGTERM


def test_warn_callback_is_skipped_when_the_child_exits_first():
    proc = _spawn_sleeper(0.1)
    seen: list[int] = []
    dog = Watchdog(
        proc, cap_secs=30, grace_secs=1, warn_secs=10, on_warn=lambda: seen.append(1)
    ).start()
    proc.wait(timeout=10)
    _wait_watchdog_settled(dog)
    assert seen == []
    assert dog.warned is False


def test_warn_window_not_below_the_cap_disables_the_warning():
    proc = _spawn_sleeper(300)
    seen: list[int] = []
    dog = Watchdog(
        proc, cap_secs=0.2, grace_secs=5, warn_secs=5, on_warn=lambda: seen.append(1)
    ).start()
    proc.wait(timeout=10)
    dog.cancel()
    assert seen == []
    assert dog.warned is False
    assert dog.fired is True


def test_warn_callback_failure_does_not_cancel_the_cap(capsys):
    proc = _spawn_sleeper(300)

    def boom() -> None:
        raise RuntimeError("marker dir gone")

    dog = Watchdog(proc, cap_secs=0.6, grace_secs=5, warn_secs=0.3, on_warn=boom).start()
    proc.wait(timeout=10)
    dog.cancel()
    assert dog.fired is True
    assert "cap warning failed: marker dir gone" in capsys.readouterr().err


def test_warn_message_names_the_window(capsys):
    proc = _spawn_sleeper(300)
    dog = Watchdog(
        proc, cap_secs=0.6, grace_secs=5, warn_secs=0.3, on_warn=lambda: None
    ).start()
    proc.wait(timeout=10)
    dog.cancel()
    err = capsys.readouterr().err
    assert "0.3s from the 0.6s wall-clock cap; requesting a task-boundary handoff" in err
