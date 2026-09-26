#!/usr/bin/env python3
"""Tests for cli/wave_launch.py's kill seam: what `abort` does when the signal it
sends raises instead of landing (PRD 00214).

Split off `test_wave_launch_abort.py` to keep that file under the 800-line style
limit; the rest of abort's proofs stayed there. Every proof runs against a
throwaway `git init` repo under `tmp_path`, never this checkout's own backlog or
`dev/local/autopilot/wave.json`, and no real loop is ever started: the lane pid
is a process group of this test's own making, reaped in a `finally`.

The group has to be genuinely alive, because `abort` probes liveness with
`os.killpg(pgid, 0)` directly and only reaches the injectable `kill_fn` for a
group that answers. What the injected `kill_fn` then does is the whole subject:
losing the race against a group that exits between the probe and the signal is
the ORDINARY case, since the group is being asked to die.
"""

from __future__ import annotations

import contextlib
import os
import signal
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

import pytest

from cli import wave, wave_launch
from cli.test_wave_launch import ONE_LANE, TWO_LANES, _autopilot, _spawned_record
from cli.test_wave_launch_abort import _assert_finished, _launched

# A group that sits still until it is killed. The SIGTERM-deaf variant ignores
# SIGTERM and records its pid once the handler is installed, so a test can wait
# for that before signalling: an unignored SIGTERM would kill it instead.
_SLEEPER_SRC = "import time; time.sleep(600)"
_DEAF_SRC = (
    "import json, os, signal, sys, time\n"
    "signal.signal(signal.SIGTERM, signal.SIG_IGN)\n"
    "open(sys.argv[1] + '.tmp', 'w').write(json.dumps({'pid': os.getpid()}))\n"
    "os.replace(sys.argv[1] + '.tmp', sys.argv[1])\n"
    "time.sleep(600)\n"
)


def _vanishing_kill(
    record: list[tuple[int, int]],
    *,
    at: int,
) -> Callable[[int, int], None]:
    """A `kill_fn` that records every signal, raises `ProcessLookupError` for the
    `at` signal, and delivers every other one for real.

    The raised error carries NO message on purpose: only its TYPE says the group
    is gone. Classifying on text ("No such process") instead reads a live lane's
    EPERM as death and removes its worktree under it.
    """

    def kill_fn(pgid: int, sig: int) -> None:
        record.append((pgid, sig))
        if sig == at:
            raise ProcessLookupError
        os.killpg(pgid, sig)

    return kill_fn


def test_abort_finishes_a_lane_whose_group_vanishes_at_the_sigterm(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo, wave_path = _launched(tmp_path, monkeypatch, TWO_LANES)
    saved = wave.load(wave_path)
    doomed = subprocess.Popen(
        [sys.executable, "-c", _SLEEPER_SRC],
        start_new_session=True,
    )
    kills: list[tuple[int, int]] = []
    try:
        # The FIRST lane loses the race, so the SECOND lane is the proof that the
        # ProcessLookupError never escaped: today it propagates out of `abort`,
        # the wave is never saved and no later lane is processed at all.
        saved["lanes"][0].update(pid=doomed.pid, status="running")
        wave.save(wave_path, saved)
        exit_code = wave_launch.abort(
            repo,
            wave_path,
            kill_fn=_vanishing_kill(kills, at=signal.SIGTERM),
        )
    finally:
        with contextlib.suppress(ProcessLookupError):
            os.killpg(doomed.pid, signal.SIGKILL)
        doomed.wait(30)
    assert exit_code == 0
    # A group already gone is a group successfully killed: no escalation, so no
    # 60s grace window is burned on a group that answered "gone".
    assert kills == [(doomed.pid, signal.SIGTERM)]
    after = wave.load(wave_path)  # read from disk: `save` ran
    assert after["status"] == "aborted"
    for lane in after["lanes"]:
        _assert_finished(repo, lane, TWO_LANES)


def test_abort_finishes_a_lane_whose_group_vanishes_at_the_sigkill(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # ~60s: the SIGTERM is delivered for real to a group that ignores it, so the
    # whole grace window runs before the escalation this test is about.
    repo, wave_path = _launched(tmp_path, monkeypatch, ONE_LANE)
    saved = wave.load(wave_path)
    marker = tmp_path / "deaf.json"
    deaf = subprocess.Popen(
        [sys.executable, "-c", _DEAF_SRC, str(marker)],
        start_new_session=True,
    )
    kills: list[tuple[int, int]] = []
    try:
        assert _spawned_record(marker)["pid"] == deaf.pid
        saved["lanes"][0].update(pid=deaf.pid, status="running")
        wave.save(wave_path, saved)
        exit_code = wave_launch.abort(
            repo,
            wave_path,
            kill_fn=_vanishing_kill(kills, at=signal.SIGKILL),
        )
    finally:
        with contextlib.suppress(ProcessLookupError):
            os.killpg(deaf.pid, signal.SIGKILL)
        deaf.wait(30)
    assert exit_code == 0
    assert kills == [(deaf.pid, signal.SIGTERM), (deaf.pid, signal.SIGKILL)]
    after = wave.load(wave_path)  # read from disk: `save` ran
    assert after["status"] == "aborted"
    _assert_finished(repo, after["lanes"][0], ONE_LANE)


@pytest.mark.parametrize(
    "reason",
    [
        "not allowed to signal this group",
        # A message that READS like a vanished group behind a type that says the
        # opposite. Only the type may classify, so this lane still failed - and
        # text-matching here would delete a live lane's worktree.
        "No such process on that host",
    ],
    ids=["denied", "gone-sounding"],
)
def test_abort_records_a_lane_whose_kill_raises_anything_else_as_a_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    reason: str,
) -> None:
    repo, wave_path = _launched(tmp_path, monkeypatch, TWO_LANES)
    saved = wave.load(wave_path)
    slots = _autopilot(repo) / "wave-slots"
    slots.mkdir()
    (slots / "slot-1").write_text("taken\n", encoding="utf-8")
    doomed = subprocess.Popen(
        [sys.executable, "-c", _SLEEPER_SRC],
        start_new_session=True,
    )
    kills: list[tuple[int, int]] = []

    def kill_fn(pgid: int, sig: int) -> None:
        kills.append((pgid, sig))
        raise PermissionError(1, reason)

    try:
        saved["lanes"][0].update(pid=doomed.pid, status="running")
        wave.save(wave_path, saved)
        exit_code = wave_launch.abort(repo, wave_path, kill_fn=kill_fn)
    finally:
        with contextlib.suppress(ProcessLookupError):
            os.killpg(doomed.pid, signal.SIGKILL)
        doomed.wait(30)
    # Not a ProcessLookupError, so not a group that died on its own: this lane
    # failed and says why. A bare `except Exception` around the signal would
    # report it as aborted and drop the reason on the floor.
    assert exit_code == 1
    assert kills != []
    after = wave.load(wave_path)
    assert after["status"] == "abort_failed"
    failed, finished = after["lanes"]
    assert failed["status"] != "aborted", failed
    assert reason in (failed["abort_error"] or ""), failed
    _assert_finished(repo, finished, TWO_LANES)  # per-lane isolation holds
    # This lane's group is genuinely ALIVE - the kill never landed - so the slot
    # directory its loop still reads has to survive the abort. A "keep it when
    # anything failed"/"keep it when the error says SIGKILL" rule gets this wrong
    # and rmtree's the slots out from under a running loop.
    assert (slots / "slot-1").read_text(encoding="utf-8") == "taken\n"
