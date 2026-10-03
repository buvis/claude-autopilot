"""cli/wave_slots.py - a directory semaphore that caps concurrent wave sessions.

Slot N is the dir `<slots_dir>/N`, holding an `owner` file with the claimant's
pid. A claim is staged under a non-digit name with its owner already inside
and published with a single `os.rename`, so a peer never sees a numbered slot
without an owner. A slot whose owner file is missing, malformed, or names a
dead pid is stale and gets reclaimed.

Each slot N also has a `<slots_dir>/N.lock` sibling, used to serialize claim,
reclaim and release of that slot. The lock files are permanent and never
removed - removing one would race a second opener between close and unlink.

Allowed imports: stdlib, `cli.loop_gates`.
"""

from __future__ import annotations

import contextlib
import fcntl
import os
import shutil
import sys
import tempfile
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


@contextlib.contextmanager
def _slot_lock(slot: Path):
    """Hold an exclusive flock on `<slot>.lock` for the body. The lock file
    is a permanent sibling, never removed - removing it would race a second
    opener between close and unlink, defeating the lock."""
    lock_path = slot.with_name(f"{slot.name}.lock")
    with open(lock_path, "a") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        yield


def _owner(slot: Path) -> str:
    """The slot's owner text, empty when there is nothing readable to read."""
    try:
        return (slot / "owner").read_bytes().decode(errors="replace").strip()
    except OSError:
        return ""


def _is_stale(owner: str) -> bool:
    """True unless the owner text names a live claimant's pid.

    Judging owner text rather than a path keeps the reading and the judgement
    one step: a reclaim has to compare against the very text it judged, so
    the caller holds that text and asks about it here.

    Bytes that do not decode, and the text "0", are rejected while the owner
    is parsed instead of reaching the oracle: `os.kill(0, 0)` signals our own
    process group, so "0" would read as a live peer forever.
    """
    return not (owner.isdecimal() and int(owner) > 0 and _pid_alive(int(owner)))


def _claim(slot: Path, pid: int) -> bool:
    """Publish a whole claim - dir and owner file - with one rename.

    `os.rename` onto a non-empty dir fails, so a slot a peer already
    published stays theirs, and that failure is how a lost race is seen.

    Each attempt stages under a name of its own, because a name reused across
    attempts collides with a staging dir that outlived a lost race - `_remove`
    reports such a failure rather than raising it - and the collision would
    abort the very next poll. A leaked staging dir costs nothing instead:
    `acquire` reads only `<dir>/<n>`, so a non-digit name is invisible to
    every code path and to the reclaim rule every peer applies.
    """
    with _slot_lock(slot):
        staged = Path(tempfile.mkdtemp(dir=slot.parent, prefix=f"{slot.name}.tmp-"))
        (staged / "owner").write_text(str(pid))
        try:
            os.rename(staged, slot)
        except OSError:
            _remove(staged)
            return False
        return True


def _discard(slot: Path, pid: int, judged: str) -> bool:
    """Clear a stale slot, moving it aside first so the slot name never
    lingers half-emptied. Winning that rename only serialises the move - one
    reclaimer carries the slot off - and the owner comparison below is what
    decides whether the reclaim goes through.

    The rename moves whatever sits at the path, so the owner it carried off
    is read there and held against `judged`, the text the staleness check
    actually ruled on. Reading the owner afresh here instead would capture
    the pid of a peer that reclaimed the slot and published a live claim
    since that ruling, match it against itself, and delete a claim in use.
    An owner still equal to what we judged is the one we judged; a changed
    one gets its own question, and a live answer puts the claim back and
    reads the slot as taken.

    The per-slot <slot>.lock (_slot_lock) now closes this window: _claim
    cannot take the vacated name while _discard holds it aside.
    """
    with _slot_lock(slot):
        aside = slot.parent / f"{slot.name}.stale-{pid}"
        try:
            os.rename(slot, aside)
        except OSError:
            return False
        moved = _owner(aside)
        if moved != judged and not _is_stale(moved):
            try:
                os.rename(aside, slot)
            except OSError as exc:
                print(
                    f"another claimant took {slot} while it was moved aside, so a"
                    f" live claim is left stranded in {aside}: {exc}",
                    file=sys.stderr,
                )
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
            owner = _owner(slot)
            cleared = _is_stale(owner) and _discard(slot, owner_pid, owner)
            if cleared and _claim(slot, owner_pid):
                return slot
        sleep_fn(poll_secs)
        # Periods come off the elapsed clock: re-basing on the moment of the
        # last line slips by up to one poll interval per period.
        periods = int((clock() - started) // HEARTBEAT_SECS)
        if periods > noted:
            print(f"waiting for a slot in {dir}", file=sys.stderr)
            noted = periods


def release(slot: Path, owner_pid: int) -> None:
    """Free a claimed slot IF `owner_pid` still owns it; a missing slot or a
    slot some other pid now owns is a no-op (a crash-and-reclaim cycle
    already moved it on).

    Runs in the caller's `finally:`, so this never raises: an `OSError` from
    the lock is reported on stderr instead, exactly as `_remove` reports a
    failed removal. A slot whose parent dir is already gone (torn down by
    `land`/`abort`) makes the lock fail with `FileNotFoundError`, a silent
    no-op: `_slot_lock` never recreates the slots directory.
    """
    try:
        with _slot_lock(slot):
            if _owner(slot) == str(owner_pid):
                _remove(slot)
    except FileNotFoundError:
        return
    except OSError as exc:
        print(f"could not release {slot}: {exc}", file=sys.stderr)
