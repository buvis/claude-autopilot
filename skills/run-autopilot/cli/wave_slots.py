"""cli/wave_slots.py - a mkdir semaphore that caps concurrent wave sessions.

Slot N is the dir `<slots_dir>/N`; `os.mkdir` is the atomic claim, and the
dir's `owner` file holds the claimant's pid. A slot whose owner file is
missing, malformed, or names a dead pid is stale and gets reclaimed.

Allowed imports: stdlib, `cli.loop_gates`.
"""

from __future__ import annotations

import os
import shutil
import sys
import time
from collections.abc import Callable
from pathlib import Path

from cli.loop_gates import _pid_alive

HEARTBEAT_SECS = 300


def _stale(slot: Path) -> bool:
    try:
        owner = (slot / "owner").read_text().strip()
    except FileNotFoundError:
        return True
    return not owner.isdigit() or not _pid_alive(int(owner))


def _claim(slot: Path, pid: int) -> bool:
    try:
        os.mkdir(slot)
    except FileExistsError:
        return False
    tmp = slot / f"owner.tmp-{pid}"
    tmp.write_text(str(pid))
    os.rename(tmp, slot / "owner")
    return True


def acquire(
    dir: Path,
    count: int,
    owner_pid: int,
    *,
    sleep_fn: Callable[[float], None] = time.sleep,
    clock: Callable[[], float] = time.monotonic,
    poll_secs: float = 30,
) -> Path:
    """Claim the first free slot in 1..count, reclaiming stale ones; poll
    every `poll_secs` until one frees, naming the slots dir on stderr once
    per five minutes of waiting. Returns the claimed slot dir."""
    dir.mkdir(parents=True, exist_ok=True)
    last_note = clock()
    while True:
        for n in range(1, count + 1):
            slot = dir / str(n)
            if _claim(slot, owner_pid):
                return slot
            if _stale(slot):
                # Move the stale slot aside before removing it: only one
                # reclaimer can win the rename; a loser retries next poll.
                aside = dir / f"{n}.stale-{owner_pid}"
                try:
                    os.rename(slot, aside)
                except OSError:
                    continue
                shutil.rmtree(aside, ignore_errors=True)
                if _claim(slot, owner_pid):
                    return slot
        if clock() - last_note >= HEARTBEAT_SECS:
            print(f"waiting for a slot in {dir}", file=sys.stderr)
            last_note = clock()
        sleep_fn(poll_secs)


def release(slot: Path) -> None:
    """Free a claimed slot; a missing slot is a no-op."""
    shutil.rmtree(slot, ignore_errors=True)
