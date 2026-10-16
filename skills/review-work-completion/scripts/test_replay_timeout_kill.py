"""A replay that times out must kill the runner's whole process group.

The fake runner backgrounds a long sleep, records both pids, then blocks
past the timeout. Killing only the direct child would leave the sleep alive.
"""

from __future__ import annotations

import os
import signal
import subprocess
import sys
import time
from pathlib import Path

import pytest
import replay_tests_against_base as r
from test_replay_tests_against_base import HEAD_IMPL, HEAD_TESTS, PYTEST, _repo

SCRIPTS = Path(__file__).resolve().parent
SCRIPT = SCRIPTS / "replay_tests_against_base.py"

# Runs replay() in its own process, so the test can SIGTERM its group.
REPLAY_DRIVER = """\
import sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
import replay_tests_against_base as r
print(r.replay(Path(sys.argv[2]), sys.argv[3], sys.argv[4], 60.0))
"""


class _StraySignal(Exception):
    """SIGTERM reached the test's own fallback handler: nothing in the code
    under test handled it (its default action would kill pytest itself)."""


def _raise_stray(signum, frame):
    raise _StraySignal(signal.Signals(signum).name)


def _slow_runner(tmp_path: Path) -> tuple[Path, Path, Path]:
    """A runner that records its pid and a backgrounded child's, then blocks."""
    leader_file = tmp_path / "leader.pid"
    child_file = tmp_path / "child.pid"
    runner = tmp_path / "runner.sh"
    runner.write_text(
        "#!/bin/sh\n"
        f"echo $$ > '{leader_file}'\n"
        "sleep 300 >/dev/null 2>&1 &\n"
        f"echo $! > '{child_file}'\n"
        "sleep 300\n",
        encoding="utf-8",
    )
    runner.chmod(0o755)
    return runner, leader_file, child_file


def _worktree_count(root: Path) -> int:
    listed = r.run_git(root, "worktree", "list", "--porcelain").stdout
    return sum(1 for line in listed.splitlines() if line.startswith("worktree "))


def _group_gone_within(proc: subprocess.Popen, seconds: float) -> bool:
    """True once `proc` (a session leader this process spawned) is reaped
    and nothing is left in its process group."""
    deadline = time.monotonic() + seconds
    while True:
        proc.poll()
        try:
            os.killpg(proc.pid, 0)
        except ProcessLookupError:
            return True
        if time.monotonic() >= deadline:
            return False
        time.sleep(0.1)


def _alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    return True


def _gone_within(pid: int, seconds: float) -> bool:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if not _alive(pid):
            return True
        time.sleep(0.1)
    return not _alive(pid)


def _wait_for_runner_pids(
    leader_file: Path,
    child_file: Path,
    deadline_s: float = 30,
) -> list[int]:
    """Block until the runner has written both pid files, then return them."""
    deadline = time.monotonic() + deadline_s
    while not (child_file.exists() and child_file.read_text().strip()):
        assert time.monotonic() < deadline, "the runner never started"
        time.sleep(0.1)
    return [
        int(leader_file.read_text().strip()),
        int(child_file.read_text().strip()),
    ]


def _kill_driver_and_runner(driver: subprocess.Popen, pids: list[int]) -> None:
    """Make sure the driver subprocess and any runner pids it spawned are
    gone, however the test under it exited."""
    if driver.poll() is None:
        os.killpg(driver.pid, signal.SIGKILL)
        driver.wait()
    if pids:
        # The runner leads its own session: its group holds the
        # foreground sleep too, whose pid it never records.
        try:
            os.killpg(pids[0], signal.SIGKILL)
        except ProcessLookupError:
            pass
    for pid in pids:
        if _alive(pid):
            os.kill(pid, signal.SIGKILL)


def test_timeout_kills_the_runner_process_group(tmp_path: Path) -> None:
    root, base = _repo(tmp_path, {"calc.py": HEAD_IMPL, "test_calc.py": HEAD_TESTS})
    leader_file = tmp_path / "leader.pid"
    child_file = tmp_path / "child.pid"
    runner = tmp_path / "runner.sh"
    runner.write_text(
        "#!/bin/sh\n"
        f"echo $$ > '{leader_file}'\n"
        "sleep 300 >/dev/null 2>&1 &\n"
        f"echo $! > '{child_file}'\n"
        "sleep 300\n",
        encoding="utf-8",
    )
    runner.chmod(0o755)
    pids: list[int] = []
    # Same command line as the runner's children, but outside its group:
    # a kill-by-name implementation would take it down too.
    decoy = subprocess.Popen(["sleep", "300"], start_new_session=True)
    timeout = 1.5
    try:
        started = time.monotonic()
        stdout, reason = r._run_in_worktree(
            root,
            base,
            ["test_calc.py"],
            str(runner),
            timeout,
        )
        elapsed = time.monotonic() - started
        pids = [
            int(leader_file.read_text().strip()),
            int(child_file.read_text().strip()),
        ]
        assert reason is not None
        assert stdout == ""
        assert timeout <= elapsed < timeout + 2.0, (
            f"caller's timeout not honored: took {elapsed:.2f}s"
        )
        assert _gone_within(pids[0], 3), "the runner itself must be killed"
        assert _gone_within(pids[1], 3), (
            "the runner's backgrounded child must be killed with its group"
        )
        assert decoy.poll() is None, "a process outside the runner's group must survive"
    finally:
        decoy.kill()
        decoy.wait()
        for pid in pids:
            if _alive(pid):
                os.kill(pid, signal.SIGKILL)


# PRD 00322 names SIGTERM and SIGHUP (the loop's orphan sweep) for the
# replay's guard; SIGINT is outside its contract.
REPLAY_SIGNALS = pytest.mark.parametrize(
    "signum",
    [signal.SIGTERM, signal.SIGHUP],
    ids=lambda s: s.name,
)


@REPLAY_SIGNALS
def test_group_sigterm_kills_runner_and_removes_worktree(
    tmp_path: Path,
    signum: int,
) -> None:
    # A SIGTERM or SIGHUP to the replay's whole process group (what a
    # supervisor's killpg does) must not orphan the runner, which lives in
    # its own session, nor leave the temporary worktree registered or on disk.
    root, base = _repo(tmp_path, {"calc.py": HEAD_IMPL, "test_calc.py": HEAD_TESTS})
    runner, leader_file, child_file = _slow_runner(tmp_path)
    tmp_root = tmp_path / "tmproot"  # the driver's whole system tmp root
    tmp_root.mkdir()
    driver = subprocess.Popen(
        [
            sys.executable,
            "-c",
            REPLAY_DRIVER,
            str(SCRIPTS),
            str(root),
            base,
            str(runner),
        ],
        env={**os.environ, "TMPDIR": str(tmp_root)},
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    pids: list[int] = []
    try:
        pids = _wait_for_runner_pids(leader_file, child_file)

        os.killpg(driver.pid, signum)
        driver.wait(timeout=15)

        assert _gone_within(pids[0], 3), "the runner itself must be killed"
        assert _gone_within(pids[1], 3), (
            "the runner's backgrounded child must be killed"
        )
        assert _worktree_count(root) == 1, "only the original worktree may remain"
        assert sorted(p.name for p in tmp_root.glob("replay-*")) == []
    finally:
        _kill_driver_and_runner(driver, pids)


def test_second_signal_during_cleanup_still_removes_worktree(
    tmp_path: Path,
) -> None:
    # A second signal (the loop's orphan sweep sends SIGHUP then SIGTERM in
    # quick succession) that arrives while the first signal's cleanup is
    # still killing the runner must not stop _run_in_worktree's own cleanup:
    # the worktree and its temp dir must still be removed.
    root, base = _repo(tmp_path, {"calc.py": HEAD_IMPL, "test_calc.py": HEAD_TESTS})
    runner, leader_file, child_file = _slow_runner(tmp_path)
    tmp_root = tmp_path / "tmproot"
    tmp_root.mkdir()
    driver = subprocess.Popen(
        [
            sys.executable,
            "-c",
            REPLAY_DRIVER,
            str(SCRIPTS),
            str(root),
            base,
            str(runner),
        ],
        env={**os.environ, "TMPDIR": str(tmp_root)},
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    pids: list[int] = []
    try:
        pids = _wait_for_runner_pids(leader_file, child_file)

        os.killpg(driver.pid, signal.SIGHUP)
        os.killpg(driver.pid, signal.SIGTERM)
        driver.wait(timeout=15)

        assert _worktree_count(root) == 1, "only the original worktree may remain"
        assert sorted(p.name for p in tmp_root.glob("replay-*")) == [], (
            "the temp dir must be removed even though a second signal "
            "arrived during cleanup"
        )
    finally:
        _kill_driver_and_runner(driver, pids)


@REPLAY_SIGNALS
def test_sigterm_during_popen_kills_the_runner(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    signum: int,
) -> None:
    # SIGTERM or SIGHUP arriving while subprocess.Popen is still executing
    # inside _run_in_worktree (the runner already forked, its handle not yet
    # back to the caller) must still reach the replay's signal handling: the
    # runner group dies and the worktree is removed. An unhandled signal
    # hits the test's fallback handler (_StraySignal) instead of pytest.
    root, base = _repo(tmp_path, {"calc.py": HEAD_IMPL, "test_calc.py": HEAD_TESTS})
    runner, _, _ = _slow_runner(tmp_path)
    real_popen = subprocess.Popen
    spawned: list[subprocess.Popen] = []

    def popen_then_signal(*args, **kwargs):
        proc = real_popen(*args, **kwargs)
        # Only the runner uses start_new_session; git calls pass untouched.
        if kwargs.get("start_new_session"):
            spawned.append(proc)
            os.kill(os.getpid(), signum)
        return proc

    monkeypatch.setattr(r.subprocess, "Popen", popen_then_signal)
    caught: BaseException | None = None
    old_handler = signal.signal(signum, _raise_stray)
    try:
        try:
            r._run_in_worktree(root, base, ["test_calc.py"], str(runner), 30)
        except BaseException as exc:
            caught = exc
    finally:
        signal.signal(signum, old_handler)

    try:
        assert spawned, "the runner's Popen call never ran"
        assert not isinstance(caught, _StraySignal), (
            f"{signum.name} during Popen went unhandled"
        )
        assert _group_gone_within(spawned[0], 3), "the runner group must be killed"
        assert _worktree_count(root) == 1, "the temporary worktree must be removed"
    finally:
        for proc in spawned:
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            proc.wait()


def _kill_runner_pids(pids: list[int]) -> None:
    """Make sure a runner a driver spawned (and its session) is gone."""
    if pids:
        try:
            os.killpg(pids[0], signal.SIGKILL)
        except ProcessLookupError:
            pass
    for pid in pids:
        if _alive(pid):
            os.kill(pid, signal.SIGKILL)


def _run_main_as_subprocess(
    root: Path, base: str, cmd: str, timeout: float
) -> subprocess.Popen:
    """Start `main()` itself, as a real child process, inside `root`."""
    return subprocess.Popen(
        [
            sys.executable,
            str(SCRIPT),
            "--base",
            base,
            "--cmd",
            cmd,
            "--timeout",
            str(timeout),
        ],
        cwd=root,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
    )


@REPLAY_SIGNALS
def test_main_terminates_by_the_signal_that_stopped_an_in_progress_replay(
    tmp_path: Path,
    signum: int,
) -> None:
    # main()'s own process receives SIGTERM/SIGHUP (the orphan sweep) while
    # its replay is mid-run. It must actually die by that signal, not
    # swallow it and exit 0.
    root, base = _repo(tmp_path, {"calc.py": HEAD_IMPL, "test_calc.py": HEAD_TESTS})
    runner, leader_file, child_file = _slow_runner(tmp_path)
    driver = _run_main_as_subprocess(root, base, str(runner), 30.0)
    pids: list[int] = []
    try:
        pids = _wait_for_runner_pids(leader_file, child_file)
        os.kill(driver.pid, signum)
        stdout, _ = driver.communicate(timeout=15)
        assert driver.returncode == -signum, (
            f"expected termination by {signal.Signals(signum).name}, "
            f"got exit status {driver.returncode}"
        )
        assert f"killed by {signal.Signals(signum).name}" in stdout
    finally:
        if driver.poll() is None:
            driver.kill()
            driver.wait()
        _kill_runner_pids(pids)


def test_main_exits_zero_on_a_plain_timeout_with_no_external_signal(
    tmp_path: Path,
) -> None:
    # A runner that times out on its own, with nobody sending this process a
    # signal, is unaffected: main() still prints the timeout skip text and
    # still exits 0, exactly as today.
    root, base = _repo(tmp_path, {"calc.py": HEAD_IMPL, "test_calc.py": HEAD_TESTS})
    runner, leader_file, child_file = _slow_runner(tmp_path)
    driver = _run_main_as_subprocess(root, base, str(runner), 1.5)
    pids: list[int] = []
    try:
        pids = _wait_for_runner_pids(leader_file, child_file)
        stdout, _ = driver.communicate(timeout=15)
        assert driver.returncode == 0
        assert (
            "replay: skipped (runner did not complete: timed out after 1.5 seconds)"
            in stdout
        )
    finally:
        if driver.poll() is None:
            driver.kill()
            driver.wait()
        _kill_runner_pids(pids)


def test_main_exits_zero_on_normal_completion(tmp_path: Path) -> None:
    # No signal, no timeout: unaffected.
    root, base = _repo(tmp_path, {"calc.py": HEAD_IMPL, "test_calc.py": HEAD_TESTS})
    driver = _run_main_as_subprocess(root, base, PYTEST, 30.0)
    stdout, _ = driver.communicate(timeout=30)
    assert driver.returncode == 0
    assert "replay: skipped" not in stdout
