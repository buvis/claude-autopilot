"""A replay that times out must kill the runner's whole process group.

The fake runner backgrounds a long sleep, records both pids, then blocks
past the timeout. Killing only the direct child would leave the sleep alive.
"""

from __future__ import annotations

import os
import signal
import time
from pathlib import Path

import replay_tests_against_base as r
from test_replay_tests_against_base import HEAD_IMPL, HEAD_TESTS, _repo


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
    try:
        stdout, reason = r._run_in_worktree(root, base, ["test_calc.py"], str(runner), 1.5)
        pids = [int(leader_file.read_text().strip()), int(child_file.read_text().strip())]
        assert reason is not None
        assert stdout == ""
        assert _gone_within(pids[0], 3), "the runner itself must be killed"
        assert _gone_within(pids[1], 3), "the runner's backgrounded child must be killed with its group"
    finally:
        for pid in pids:
            if _alive(pid):
                os.kill(pid, signal.SIGKILL)
