"""Tests for cli/procinfo.py (PRD 00285): process facts read without ps.

Every test runs against a real spawned process, never a mocked sysctl, so
they pin what the kernel actually reports for a live, a reaped and our own
pid.
"""

from __future__ import annotations

import os
import subprocess
import sys
import time

from cli.procinfo import child_names, cpu_seconds, exec_env


def _spawn_tagged_child() -> subprocess.Popen:
    """exec keeps the shell's pid, so $$ IS the final python's pid."""
    return subprocess.Popen(
        [
            "bash",
            "-c",
            f"exec env _AUTOPILOT_LOOP=$$ {sys.executable} -c "
            '"import time; time.sleep(60)"',
        ],
    )


def _reaped_pid() -> int:
    proc = subprocess.Popen([sys.executable, "-c", "pass"])
    proc.wait()
    return proc.pid


def test_exec_env_reads_the_tag_of_a_spawned_child():
    proc = _spawn_tagged_child()
    try:
        # bash -> env -> python is two more execs after Popen returns.
        deadline = time.monotonic() + 10
        env = exec_env(proc.pid)
        while time.monotonic() < deadline:
            env = exec_env(proc.pid)
            if env is not None and "_AUTOPILOT_LOOP" in env:
                break
            time.sleep(0.05)
        assert env is not None
        assert env["_AUTOPILOT_LOOP"] == str(proc.pid)
    finally:
        proc.kill()
        proc.wait()


def test_exec_env_is_none_for_a_reaped_pid():
    assert exec_env(_reaped_pid()) is None


def test_cpu_seconds_is_nonnegative_and_monotonic_for_own_pid():
    before = cpu_seconds(os.getpid())
    total = 0
    for i in range(1_000_000):
        total += i
    after = cpu_seconds(os.getpid())
    assert total == 499_999_500_000
    assert before is not None and after is not None
    assert before >= 0
    assert after >= before


def test_cpu_seconds_is_none_for_a_reaped_pid():
    assert cpu_seconds(_reaped_pid()) is None


def test_child_names_lists_a_spawned_child():
    proc = subprocess.Popen(["sleep", "60"])
    try:
        children = child_names(os.getpid())
        assert (proc.pid, "sleep") in children
    finally:
        proc.kill()
        proc.wait()
