"""cli/wave_slots.py - a mkdir semaphore that caps concurrent wave sessions.

Slot N is the dir `<slots_dir>/N`, holding an `owner` file with the claimant's
pid. A claim is staged under a non-digit name with its owner already inside
and published with a single `os.rename`, so a peer never sees a numbered slot
without an owner. A slot whose owner file is missing, malformed, or names a
dead pid is stale and gets reclaimed.

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


def _remove(path: Path) -> None:
    """Remove a slot tree, reporting a failure rather than raising it.

    `release` runs in the caller's `finally:`, where a raise would replace
    the in-flight error, and a swallowed failure would leave a slot held
    that the pool can never hand out again. Already gone is not news.
    """
    try:
        shutil.rmtree(path)
    except FileNotFoundError:
        pass
    except OSError as exc:
        print(f"could not remove {path}: {exc}", file=sys.stderr)


def _stale(slot: Path) -> bool:
    """True unless the slot's owner file names a live claimant's pid.

    Bytes that do not decode, and the text "0", are rejected while the owner
    is parsed instead of reaching the oracle: `os.kill(0, 0)` signals our own
    process group, so "0" would read as a live peer forever.
    """
    try:
        owner = (slot / "owner").read_bytes().decode(errors="replace").strip()
    except OSError:
        return True
    return not (owner.isdigit() and int(owner) > 0 and _pid_alive(int(owner)))


def _claim(slot: Path, pid: int) -> bool:
    """Publish a whole claim - dir and owner file - with one rename.

    `os.rename` onto a non-empty dir fails, so a slot a peer already
    published stays theirs, and that failure is how a lost race is seen.
    """
    staged = slot.parent / f"{slot.name}.tmp-{pid}"
    staged.mkdir()
    (staged / "owner").write_text(str(pid))
    try:
        os.rename(staged, slot)
    except OSError:
        _remove(staged)
        return False
    return True


def _discard(slot: Path, pid: int) -> bool:
    """Clear a stale slot, moving it aside first so the slot name never
    lingers half-emptied and only one reclaimer can win the rename."""
    aside = slot.parent / f"{slot.name}.stale-{pid}"
    try:
        os.rename(slot, aside)
    except OSError:
        return False
    _remove(aside)
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
    if count < 1:
        raise ValueError(f"wave slot count must be at least 1, got {count}")
    dir.mkdir(parents=True, exist_ok=True)
    started = clock()
    noted = 0
    while True:
        for n in range(1, count + 1):
            slot = dir / str(n)
            if _claim(slot, owner_pid):
                return slot
            # Losing either step of a reclaim means a peer got there first.
            if _stale(slot) and _discard(slot, owner_pid) and _claim(slot, owner_pid):
                return slot
        sleep_fn(poll_secs)
        # Periods come off the elapsed clock: re-basing on the moment of the
        # last line slips by up to one poll interval per period.
        periods = int((clock() - started) // HEARTBEAT_SECS)
        if periods > noted:
            print(f"waiting for a slot in {dir}", file=sys.stderr)
            noted = periods


def release(slot: Path) -> None:
    """Free a claimed slot; a missing slot is a no-op."""
    _remove(slot)
