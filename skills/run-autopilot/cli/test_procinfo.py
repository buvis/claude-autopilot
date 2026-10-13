"""Tests for cli/procinfo.py (PRD 00285): process facts read without ps.

Every test runs against a real spawned process, never a mocked sysctl, so
they pin what the kernel actually reports for a live, a reaped and our own
pid.
"""

from __future__ import annotations

import os
import signal
import subprocess
import sys
import time
import uuid

from cli.procinfo import child_names, cpu_seconds, exec_env


def _child_env(**extra: str) -> dict[str, str]:
    """A minimal env for a child: PATH plus `extra`, nothing inherited."""
    return {"PATH": os.environ["PATH"], **extra}


def _spawn_tagged_child(env: dict[str, str]) -> subprocess.Popen:
    """exec keeps the shell's pid, so $$ IS the final python's pid."""
    return subprocess.Popen(
        [
            "bash",
            "-c",
            f"exec env _AUTOPILOT_LOOP=$$ {sys.executable} -c "
            '"import time; time.sleep(60)"',
        ],
        env=env,
    )


def _reaped_pid() -> int:
    proc = subprocess.Popen([sys.executable, "-c", "pass"])
    proc.wait()
    return proc.pid


def _wait_for_env_key(pid: int, key: str) -> dict[str, str] | None:
    deadline = time.monotonic() + 10
    env = exec_env(pid)
    while time.monotonic() < deadline:
        env = exec_env(pid)
        if env is not None and key in env:
            break
        time.sleep(0.05)
    return env


def _kill_quietly(pid: int) -> None:
    try:
        os.kill(pid, signal.SIGKILL)
    except ProcessLookupError:
        pass


def test_exec_env_reads_the_tag_of_a_spawned_child(monkeypatch):
    probe = uuid.uuid4().hex
    caller_only = uuid.uuid4().hex
    # Set in this process only; the child's explicit env leaves it out.
    monkeypatch.setenv("_TESS_CALLER_ONLY", caller_only)
    proc = _spawn_tagged_child(_child_env(_DEVON_PROBE=probe))
    try:
        # bash -> env -> python is two more execs after Popen returns.
        env = _wait_for_env_key(proc.pid, "_AUTOPILOT_LOOP")
        assert env is not None
        assert env["_AUTOPILOT_LOOP"] == str(proc.pid)
        assert env.get("_DEVON_PROBE") == probe
        assert "_TESS_CALLER_ONLY" not in env
    finally:
        proc.kill()
        proc.wait()


def test_exec_env_omits_the_tag_of_an_untagged_child():
    probe = uuid.uuid4().hex
    proc = subprocess.Popen(["sleep", "60"], env=_child_env(_DEVON_PROBE=probe))
    try:
        env = _wait_for_env_key(proc.pid, "_DEVON_PROBE")
        assert env is not None
        assert env.get("_DEVON_PROBE") == probe
        assert "_AUTOPILOT_LOOP" not in env
    finally:
        proc.kill()
        proc.wait()


def test_exec_env_is_none_for_a_reaped_pid():
    assert exec_env(_reaped_pid()) is None


def test_cpu_seconds_is_nonnegative_and_monotonic_for_own_pid():
    before = cpu_seconds(os.getpid())
    start = time.process_time()
    while time.process_time() - start < 0.1:
        pass
    after = cpu_seconds(os.getpid())
    assert before is not None and after is not None
    assert before >= 0
    assert after > before


def test_cpu_seconds_reads_the_target_pid_not_the_caller():
    busy = subprocess.Popen(
        [
            sys.executable,
            "-c",
            "import time\n"
            "t = time.process_time()\n"
            "while time.process_time() - t < 0.5:\n"
            "    pass\n"
            "time.sleep(60)\n",
        ]
    )
    idle = subprocess.Popen(["sleep", "60"])
    try:
        deadline = time.monotonic() + 10
        busy_cpu = cpu_seconds(busy.pid)
        while time.monotonic() < deadline:
            busy_cpu = cpu_seconds(busy.pid)
            if busy_cpu is not None and busy_cpu > 0.2:
                break
            time.sleep(0.05)
        idle_cpu = cpu_seconds(idle.pid)
        assert busy_cpu is not None and busy_cpu > 0.2
        assert idle_cpu is not None and 0 <= idle_cpu < 0.1
    finally:
        for proc in (busy, idle):
            proc.kill()
            proc.wait()


def test_cpu_seconds_is_none_for_a_reaped_pid():
    assert cpu_seconds(_reaped_pid()) is None


def test_exec_env_is_none_for_a_negative_pid():
    # A real syscall failure (EINVAL), not a mocked one: no process table
    # lookup can ever resolve a negative pid.
    assert exec_env(-1) is None


def test_cpu_seconds_is_none_for_a_negative_pid():
    assert cpu_seconds(-1) is None


def test_child_names_lists_a_spawned_child():
    # Absolute path: a PATH-first coreutils `sleep` is named "gsleep".
    proc = subprocess.Popen(["/bin/sleep", "60"])
    try:
        children = child_names(os.getpid())
        pids = [pid for pid, _ in children]
        assert (proc.pid, "sleep") in children
        assert pids.count(proc.pid) == 1
        assert os.getpid() not in pids
    finally:
        proc.kill()
        proc.wait()


def test_child_names_is_empty_for_a_childless_process():
    proc = subprocess.Popen(["/bin/sleep", "60"])
    try:
        assert child_names(proc.pid) == []
    finally:
        proc.kill()
        proc.wait()


def test_child_names_is_empty_when_pgrep_is_missing(monkeypatch, tmp_path):
    # A real OSError, not a mocked one: PATH holds no `pgrep` binary at all.
    monkeypatch.setenv("PATH", str(tmp_path))
    assert child_names(os.getpid()) == []


def test_child_names_is_empty_on_subprocess_timeout(monkeypatch):
    def _raise_timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired(cmd=["pgrep"], timeout=10)

    monkeypatch.setattr(subprocess, "run", _raise_timeout)
    assert child_names(os.getpid()) == []


def test_child_names_lists_exactly_the_target_pids_children_by_real_name():
    # bash forks each job and the job execs its binary; $! is its pid.
    proc = subprocess.Popen(
        [
            "bash",
            "-c",
            "/bin/sleep 60 & echo $!; /usr/bin/tail -f /dev/null & echo $!; wait",
        ],
        stdout=subprocess.PIPE,
        text=True,
    )
    assert proc.stdout is not None
    sleep_pid = int(proc.stdout.readline())
    tail_pid = int(proc.stdout.readline())
    try:
        expected = sorted([(sleep_pid, "sleep"), (tail_pid, "tail")])
        deadline = time.monotonic() + 10
        children = sorted(child_names(proc.pid))
        while time.monotonic() < deadline and children != expected:
            time.sleep(0.05)
            children = sorted(child_names(proc.pid))
        assert children == expected
    finally:
        _kill_quietly(sleep_pid)
        _kill_quietly(tail_pid)
        proc.kill()
        proc.wait()
        proc.stdout.close()
