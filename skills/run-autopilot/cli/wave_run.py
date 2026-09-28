"""cli/wave_run.py - `autopilot wave run`: chain plan, launch, wait, assemble,
review and land into one call (PRD 00214 follow-on).
"""

from __future__ import annotations

import os
import signal
import sys
import time
from collections.abc import Callable
from pathlib import Path

from cli import wave, wave_assemble, wave_launch, wave_review


def _wait_for_lanes(
    repo: Path,
    wave_path: Path,
    sleep_fn: Callable[[float], None],
    clock: Callable[[], float],
) -> None:
    """Poll every 30s (via sleep_fn) until every lane pid reads dead, printing
    the status table every 10 minutes of elapsed wall time. SIGINT/SIGTERM
    during the wait kill every still-running lane's process group directly,
    mark the wave interrupted, and exit 130."""
    previous: dict[int, object] = {}

    def handler(signum: int, frame: object) -> None:
        loaded = wave.load(wave_path)
        for lane in loaded["lanes"]:
            if wave_launch.lane_status(lane) == "running":
                wave_launch._kill_lane(lane, os.killpg)
        loaded["status"] = "interrupted"
        wave.save(wave_path, loaded)
        signal.signal(signal.SIGINT, previous[signal.SIGINT])
        signal.signal(signal.SIGTERM, previous[signal.SIGTERM])
        sys.exit(130)

    previous[signal.SIGINT] = signal.signal(signal.SIGINT, handler)
    previous[signal.SIGTERM] = signal.signal(signal.SIGTERM, handler)
    try:
        last_print = clock()
        while True:
            loaded = wave.load(wave_path)
            if all(
                wave_launch.lane_status(lane) != "running" for lane in loaded["lanes"]
            ):
                return
            now = clock()
            if now - last_print >= 600:
                print(wave_launch.status(repo, loaded))
                last_print = now
            sleep_fn(30)
    finally:
        signal.signal(signal.SIGINT, previous[signal.SIGINT])
        signal.signal(signal.SIGTERM, previous[signal.SIGTERM])


def _check_preconditions(review_slots: int, yes: bool) -> int | None:
    """An error exit code, or None once both preconditions pass."""
    if review_slots < 1:
        print(
            f"autopilot: review slots must be at least 1, got {review_slots}",
            file=sys.stderr,
        )
        return 1
    if not sys.stdin.isatty() and not yes:
        print("autopilot: pass --yes to run a wave unattended", file=sys.stderr)
        return 1
    return None


def _confirm_launch(confirm_fn: Callable[..., str]) -> int | None:
    """An error exit code, or None once the operator confirms."""
    try:
        confirm_fn("autopilot: launch this wave? [Y/n] ")
    except EOFError:
        print(
            "autopilot: no confirmation received; refusing to launch",
            file=sys.stderr,
        )
        return 1
    return None


def _review_and_land(repo: Path, wave_path: Path, exit_code: int) -> int:
    loaded = wave.load(wave_path)
    outcome = wave_review.review(repo, loaded)
    if outcome == "review_failed":
        return 4
    if outcome == "converged":
        land_code = wave_review.land(repo, loaded)
        if land_code:
            return land_code
    return exit_code


def run(
    repo: Path,
    *,
    max_lanes: int = 3,
    review_slots: int = 3,
    yes: bool = False,
    confirm_fn: Callable[..., str] = input,
    sleep_fn: Callable[[float], None] = time.sleep,
    clock: Callable[[], float] = time.monotonic,
) -> int:
    """Chain plan, launch, wait, assemble, review and land for one wave.
    Exit codes: 0 landed; 1 a precondition refused; 3 assemble kept a lane;
    4 review failed; 5 master moved before land - see references/waves.md
    § wave run for the full contract."""
    wave_path = repo / "docs/dev/project-management/autopilot/wave.json"

    precondition_error = _check_preconditions(review_slots, yes)
    if precondition_error is not None:
        return precondition_error

    plan_code = wave.plan(repo, wave_path, max_lanes)
    if plan_code != 0:
        return plan_code

    if review_slots != 3:
        loaded = wave.load(wave_path)
        loaded["review_slots"] = review_slots
        wave.save(wave_path, loaded)

    if not yes:
        confirm_error = _confirm_launch(confirm_fn)
        if confirm_error is not None:
            return confirm_error

    launch_code = wave_launch.launch(repo, wave_path)
    if launch_code != 0:
        return launch_code

    _wait_for_lanes(repo, wave_path, sleep_fn, clock)

    assemble_code = wave_assemble.assemble(repo, wave_path)
    if assemble_code not in (0, 3):
        return assemble_code

    return _review_and_land(repo, wave_path, assemble_code)
