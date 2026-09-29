"""cli/wave_slots.py - a mkdir semaphore that caps concurrent wave sessions.

Slot N is the dir `<slots_dir>/N`; `os.mkdir` is the atomic claim, and the
dir's `owner` file holds the claimant's pid. A slot whose owner file is
missing, malformed, or names a dead pid is stale and gets reclaimed.

Allowed imports: stdlib only.
"""

from __future__ import annotations

import os
import shutil
import time
from collections.abc import Callable
from pathlib import Path


def _pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except OSError:
        return True  # EPERM etc.: it exists, we just can't signal it
    return True


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
    (slot / "owner").write_text(str(pid))
    return True


def acquire(
    slots_dir: Path,
    cap: int,
    pid: int,
    *,
    sleep_fn: Callable[[float], None] = time.sleep,
    clock: Callable[[], float] = time.monotonic,
    poll_secs: float = 5,
) -> Path:
    """Claim the first free slot in 1..cap, reclaiming stale ones; poll
    every `poll_secs` until one frees. Returns the claimed slot dir."""
    slots_dir.mkdir(parents=True, exist_ok=True)
    while True:
        for n in range(1, cap + 1):
            slot = slots_dir / str(n)
            if _claim(slot, pid):
                return slot
            if _stale(slot):
                shutil.rmtree(slot, ignore_errors=True)
                if _claim(slot, pid):
                    return slot
        sleep_fn(poll_secs)


def release(slot: Path) -> None:
    """Free a claimed slot; a missing slot is a no-op."""
    shutil.rmtree(slot, ignore_errors=True)
