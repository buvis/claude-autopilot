#!/usr/bin/env python3
"""Tests for cli/review_stage._run_script's signal handling (split from
test_review_stage_run_script.py, which already covers the plain timeout
escalation and must not be re-tested here).

Two behaviors under test:
- A SIGTERM/SIGHUP landing on the caller's own process group while a helper
  is running underneath `_run_script` must tear the helper down too (not
  leave it orphaned) and surface as a RuntimeError naming the signal,
  mirroring `cli/verification._signal_error`'s guard shape applied to the
  helper subprocess instead of the gate's subprocess.
- The `os.killpg` race on timeout escalation (the helper exits on its own
  between the timeout firing and the kill call) must not propagate as an
  uncaught ProcessLookupError; `_run_script` still returns its normal
  timeout block.

The caller-signal tests run `_run_script` inside a disposable child
process and deliver the signal to *that child*, never to this test's own
pid: before the fix exists, the signal's default disposition just kills
whatever process receives it, and that must never be this pytest process
(it would abort the whole run and mask every other test's result).
"""

from __future__ import annotations

import os
import signal
import subprocess
import sys
import time
from pathlib import Path

import pytest

from cli import review_stage

SLEEPER = """\
import os, sys, time
with open(sys.argv[1], "w") as f:
    f.write(str(os.getpid()))
time.sleep(30)
"""

# SIGTERM is ignored so a real SIGTERM delivered by the test (rather than by
# the mocked killpg) cannot end the helper on its own, which would make the
# grace-period wait succeed without ever reaching the SIGKILL branch under
# test.
IGNORER = """\
import os, signal, sys, time
signal.signal(signal.SIGTERM, signal.SIG_IGN)
tmp = sys.argv[1] + ".tmp"
with open(tmp, "w") as f:
    f.write(str(os.getpid()))
os.replace(tmp, sys.argv[1])
time.sleep(30)
"""

# Runs _run_script in a disposable child process and reports the outcome to
# a file. Used so a signal landing on the caller can be delivered to this
# child's pid, never to the test process's own pid.
RUNNER = """\
import sys
sys.path.insert(0, sys.argv[1])
from pathlib import Path
from cli import review_stage

helper = Path(sys.argv[2])
helper_arg = sys.argv[3]
cwd = Path(sys.argv[4])
result_file = sys.argv[5]
timeout = float(sys.argv[6])

try:
    review_stage._run_script(helper, [helper_arg], cwd, timeout=timeout)
except RuntimeError as e:
    with open(result_file, "w") as f:
        f.write("RuntimeError:" + str(e))
except BaseException as e:
    with open(result_file, "w") as f:
        f.write(type(e).__name__ + ":" + str(e))
else:
    with open(result_file, "w") as f:
        f.write("returned normally")
"""

# Same as RUNNER, but self-signals its own pid right before the real Popen
# call that starts the helper, simulating a signal landing before the
# helper subprocess handle exists.
RUNNER_SIGNAL_BEFORE_POPEN = """\
import os
import sys
sys.path.insert(0, sys.argv[1])
from pathlib import Path
from cli import review_stage

helper = Path(sys.argv[2])
helper_arg = sys.argv[3]
cwd = Path(sys.argv[4])
result_file = sys.argv[5]
timeout = float(sys.argv[6])
sig = int(sys.argv[7])

real_popen = review_stage.subprocess.Popen


def popen_after_signal(*args, **kwargs):
    os.kill(os.getpid(), sig)
    return real_popen(*args, **kwargs)


review_stage.subprocess.Popen = popen_after_signal

try:
    review_stage._run_script(helper, [helper_arg], cwd, timeout=timeout)
except RuntimeError as e:
    with open(result_file, "w") as f:
        f.write("RuntimeError:" + str(e))
except BaseException as e:
    with open(result_file, "w") as f:
        f.write(type(e).__name__ + ":" + str(e))
else:
    with open(result_file, "w") as f:
        f.write("returned normally")
"""


def _skill_dir() -> str:
    # The directory that must be on sys.path for "from cli import
    # review_stage" to resolve: review_stage.py's grandparent.
    return str(Path(review_stage.__file__).resolve().parent.parent)


def _alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    return True


def _exited_within(pid: int, seconds: float) -> bool:
    deadline = time.monotonic() + seconds
    while True:
        if not _alive(pid):
            return True
        if time.monotonic() >= deadline:
            return False
        time.sleep(0.05)


def _wait_for_file(path: Path, seconds: float = 5) -> None:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if path.exists():
            return
        time.sleep(0.02)
    raise AssertionError(f"{path} was never written")


def _end_child(child: subprocess.Popen) -> None:
    try:
        child.wait(timeout=5)
    except subprocess.TimeoutExpired:
        child.kill()
        child.wait()


@pytest.mark.parametrize("sig", [signal.SIGTERM, signal.SIGHUP])
def test_run_script_kills_helper_on_caller_signal_and_raises(
    tmp_path: Path, sig: int
) -> None:
    # A signal landing on the caller while the helper is already running
    # (blocked in communicate()) must terminate the helper's process group
    # and surface as a RuntimeError naming the signal, not hang or return
    # normally.
    helper = tmp_path / "sleeper.py"
    helper.write_text(SLEEPER)
    pid_file = tmp_path / "sleeper.pid"
    result_file = tmp_path / "result.txt"
    runner = tmp_path / "runner.py"
    runner.write_text(RUNNER)

    child = subprocess.Popen(
        [
            sys.executable,
            str(runner),
            _skill_dir(),
            str(helper),
            str(pid_file),
            str(tmp_path),
            str(result_file),
            "10",
        ]
    )
    try:
        _wait_for_file(pid_file)
        os.kill(child.pid, sig)
    finally:
        _end_child(child)

    assert result_file.exists(), "the caller process exited without reporting"
    text = result_file.read_text()
    assert text.startswith("RuntimeError:"), text
    assert signal.Signals(sig).name in text

    helper_pid = int(pid_file.read_text())
    assert _exited_within(helper_pid, 2), "the helper outlived the caller's own signal"


def test_run_script_defers_signal_arriving_before_popen_returns(
    tmp_path: Path,
) -> None:
    # A signal landing before the helper subprocess handle exists must be
    # deferred, not lost, and raised immediately once the handle exists
    # rather than being silently absorbed while the helper runs on.
    helper = tmp_path / "sleeper.py"
    helper.write_text(SLEEPER)
    pid_file = tmp_path / "sleeper.pid"
    result_file = tmp_path / "result.txt"
    runner = tmp_path / "runner.py"
    runner.write_text(RUNNER_SIGNAL_BEFORE_POPEN)

    child = subprocess.Popen(
        [
            sys.executable,
            str(runner),
            _skill_dir(),
            str(helper),
            str(pid_file),
            str(tmp_path),
            str(result_file),
            "10",
            str(int(signal.SIGTERM)),
        ]
    )
    _end_child(child)

    assert result_file.exists(), "the caller process exited without reporting"
    text = result_file.read_text()
    assert text.startswith("RuntimeError:"), text
    assert "SIGTERM" in text

    _wait_for_file(pid_file)
    helper_pid = int(pid_file.read_text())
    assert _exited_within(helper_pid, 2), "the deferred signal left the helper running"


def test_run_script_survives_race_on_sigterm_killpg(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # The helper exits on its own in the window between the timeout firing
    # and the SIGTERM killpg call: killpg raises ProcessLookupError, which
    # must not propagate out of _run_script.
    helper = tmp_path / "sleeper.py"
    helper.write_text(SLEEPER)
    pid_file = tmp_path / "sleeper.pid"

    real_killpg = review_stage.os.killpg

    def killpg_raising_on_sigterm(pgid, sig):
        if sig == signal.SIGTERM:
            try:
                os.kill(pgid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            raise ProcessLookupError()
        return real_killpg(pgid, sig)

    monkeypatch.setattr(review_stage.os, "killpg", killpg_raising_on_sigterm)

    block = review_stage._run_script(helper, [str(pid_file)], tmp_path, timeout=0.1)
    assert block == "_sleeper.py failed (timeout after 0s)_"


def test_run_script_survives_race_on_sigkill_killpg(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # The helper exits on its own in the window between the SIGTERM grace
    # period expiring and the SIGKILL killpg call: killpg raises
    # ProcessLookupError, which must not propagate out of _run_script.
    monkeypatch.setattr(review_stage, "SCRIPT_GRACE_S", 0.3)
    helper = tmp_path / "ignorer.py"
    helper.write_text(IGNORER)
    pid_file = tmp_path / "ignorer.pid"

    real_killpg = review_stage.os.killpg

    def killpg_raising_on_sigkill(pgid, sig):
        if sig == signal.SIGKILL:
            try:
                os.kill(pgid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            raise ProcessLookupError()
        return real_killpg(pgid, sig)

    monkeypatch.setattr(review_stage.os, "killpg", killpg_raising_on_sigkill)

    block = review_stage._run_script(helper, [str(pid_file)], tmp_path, timeout=2)
    assert block == "_ignorer.py failed (timeout after 2s)_"


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
