"""Tests for cli/wave_slots.py: the mkdir semaphore that caps concurrent
wave sessions. Slots are numbered dirs under the slots dir, each holding an
`owner` file with the claimant's pid. Liveness is faked by patching
`wave_slots._pid_alive`, and sleep/clock are injected, so nothing here
depends on real processes or real time.
"""

from __future__ import annotations

from pathlib import Path

from cli import wave_slots
from cli.wave_slots import acquire, release

LIVE_PEER = 1111
DEAD_PEER = 2222
ME = 4242


def _fake_clock() -> float:
    return 0.0


def _no_sleep(secs: float) -> None:
    raise AssertionError(f"acquire slept {secs}s with a slot free")


def _only_alive(monkeypatch, *alive: int) -> None:
    monkeypatch.setattr(wave_slots, "_pid_alive", lambda pid: pid in alive)


def _hold(slots: Path, n: int, owner: str) -> Path:
    slot = slots / str(n)
    slot.mkdir(parents=True)
    (slot / "owner").write_text(owner)
    return slot


def test_acquire_creates_the_slots_dir(tmp_path, monkeypatch):
    _only_alive(monkeypatch)
    slots = tmp_path / "state" / "wave-slots"
    assert not slots.exists()
    slot = acquire(slots, 2, ME, sleep_fn=_no_sleep, clock=_fake_clock)
    assert slots.is_dir()
    assert slot == slots / "1"
    assert (slot / "owner").read_text().strip() == str(ME)


def test_acquire_takes_the_first_free_slot(tmp_path, monkeypatch):
    _only_alive(monkeypatch, LIVE_PEER)
    slots = tmp_path / "wave-slots"
    _hold(slots, 1, str(LIVE_PEER))
    slot = acquire(slots, 3, ME, sleep_fn=_no_sleep, clock=_fake_clock)
    assert slot == slots / "2"
    assert (slot / "owner").read_text().strip() == str(ME)
    # The live peer's slot is untouched, and slot 3 was never claimed.
    assert (slots / "1" / "owner").read_text().strip() == str(LIVE_PEER)
    assert not (slots / "3").exists()


def test_acquire_blocks_until_release(tmp_path, monkeypatch):
    _only_alive(monkeypatch, LIVE_PEER)
    slots = tmp_path / "wave-slots"
    held = _hold(slots, 1, str(LIVE_PEER))
    sleeps: list[float] = []

    def sleep_fn(secs: float) -> None:
        sleeps.append(secs)
        if len(sleeps) == 2:
            release(held)

    slot = acquire(slots, 1, ME, sleep_fn=sleep_fn, clock=_fake_clock, poll_secs=7)
    assert sleeps == [7, 7]
    assert slot == slots / "1"
    assert (slot / "owner").read_text().strip() == str(ME)


def test_dead_owner_slot_is_reclaimed(tmp_path, monkeypatch):
    _only_alive(monkeypatch, LIVE_PEER)
    slots = tmp_path / "wave-slots"
    stale = _hold(slots, 1, str(DEAD_PEER))
    (stale / "leftover").write_text("junk from the dead session")
    slot = acquire(slots, 1, ME, sleep_fn=_no_sleep, clock=_fake_clock)
    assert slot == slots / "1"
    assert (slot / "owner").read_text().strip() == str(ME)
    assert not (slot / "leftover").exists()  # stale dir was removed, not reused


def test_missing_owner_file_is_reclaimed(tmp_path, monkeypatch):
    _only_alive(monkeypatch, LIVE_PEER)
    slots = tmp_path / "wave-slots"
    (slots / "1").mkdir(parents=True)
    slot = acquire(slots, 1, ME, sleep_fn=_no_sleep, clock=_fake_clock)
    assert slot == slots / "1"
    assert (slot / "owner").read_text().strip() == str(ME)


def test_malformed_owner_is_reclaimed(tmp_path, monkeypatch):
    # Every pid reads as alive, so only the malformed content can free it.
    monkeypatch.setattr(wave_slots, "_pid_alive", lambda pid: True)
    slots = tmp_path / "wave-slots"
    _hold(slots, 1, "not-a-pid")
    slot = acquire(slots, 1, ME, sleep_fn=_no_sleep, clock=_fake_clock)
    assert slot == slots / "1"
    assert (slot / "owner").read_text().strip() == str(ME)


def test_release_frees_the_slot(tmp_path, monkeypatch):
    _only_alive(monkeypatch, ME)
    slots = tmp_path / "wave-slots"
    slot = acquire(slots, 1, ME, sleep_fn=_no_sleep, clock=_fake_clock)
    release(slot)
    assert not slot.exists()
    # With our own (live) claim gone, a second acquire gets slot 1 at once.
    again = acquire(slots, 1, ME, sleep_fn=_no_sleep, clock=_fake_clock)
    assert again == slots / "1"


def test_release_of_a_missing_slot_is_a_noop(tmp_path):
    slot = tmp_path / "wave-slots" / "1"
    assert release(slot) is None
    assert not slot.exists()
