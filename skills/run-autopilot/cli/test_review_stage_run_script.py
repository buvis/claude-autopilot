#!/usr/bin/env python3
"""Tests for cli/review_stage._run_script's timeout (split from
test_review_stage.py, which is already past the 800-line limit).

A helper script that hangs must not hang the review stage: `_run_script`
stops it at its timeout (SIGTERM first, SIGKILL only after a grace window),
says so in the returned block, and never raises.
"""

from __future__ import annotations

import os
import signal
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

TRAPPER = """\
import signal, sys, time
def on_term(signum, frame):
    with open(sys.argv[1], "w") as f:
        f.write("SIGTERM")
    sys.exit(0)
signal.signal(signal.SIGTERM, on_term)
time.sleep(30)
"""


def _alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    return True


def test_run_script_times_out_and_says_so(tmp_path: Path) -> None:
    helper = tmp_path / "sleeper.py"
    helper.write_text(SLEEPER)
    pid_file = tmp_path / "sleeper.pid"

    started = time.monotonic()
    block = review_stage._run_script(helper, [str(pid_file)], tmp_path, timeout=0.1)
    elapsed = time.monotonic() - started

    assert block == "_sleeper.py failed (timeout after 0s)_"
    assert elapsed < 10, f"the 30s helper was not stopped: took {elapsed:.1f}s"
    # A helper killed before it wrote its pid can never write it later; a
    # leaked one writes it well within this wait.
    time.sleep(0.5)
    text = pid_file.read_text().strip() if pid_file.exists() else ""
    if text:
        pid = int(text)
        try:
            assert not _alive(pid), "the helper is still running after the timeout"
        finally:
            if _alive(pid):
                os.kill(pid, signal.SIGKILL)


def test_run_script_sigterms_before_sigkill(tmp_path: Path) -> None:
    # The helper exits cleanly on SIGTERM, well inside the grace window: the
    # marker proves SIGTERM came first (a SIGKILL cannot be trapped), and
    # the elapsed time proves the grace window was not sat out in full.
    helper = tmp_path / "trapper.py"
    helper.write_text(TRAPPER)
    marker = tmp_path / "sigterm.marker"

    started = time.monotonic()
    block = review_stage._run_script(helper, [str(marker)], tmp_path, timeout=2)
    elapsed = time.monotonic() - started

    assert block == "_trapper.py failed (timeout after 2s)_"
    assert marker.exists(), "the helper never saw SIGTERM before it was stopped"
    assert marker.read_text() == "SIGTERM"
    assert elapsed < 2 + 8, f"waited out the grace window: took {elapsed:.1f}s"


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
