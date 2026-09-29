"""Tests for cli/wave_slots.py: the mkdir semaphore that caps concurrent
wave sessions. Slots are numbered dirs under the slots dir, each holding an
`owner` file with the claimant's pid. Liveness is faked by patching
`wave_slots._pid_alive`, and sleep/clock are injected, so nothing here
depends on real time. Only the `_pid_alive` test uses real processes.
"""

from __future__ import annotations

import os
import subprocess
import sys
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


def test_pid_alive_tells_a_live_pid_from_an_exited_one():
    # The real helper, unpatched: a stub that calls every pid alive would
    # never reclaim a dead owner's slot in production.
    assert wave_slots._pid_alive(os.getpid()) is True
    child = subprocess.Popen([sys.executable, "-c", "pass"])
    child.wait()
    assert wave_slots._pid_alive(child.pid) is False


def test_docs_name_the_two_variables():
    waves_md = Path(__file__).parent.parent / "references" / "waves.md"
    text = waves_md.read_text()
    assert "_AUTOPILOT_REVIEW_SLOTS_DIR" in text
    assert "_AUTOPILOT_REVIEW_SLOTS" in text


def test_claim_is_exclusive_when_a_peer_wins_the_mkdir_race(tmp_path, monkeypatch):
    # A live peer creates slot 1 in the gap after acquire sees it free and
    # before acquire's own mkdir lands. mkdir must be the claim: acquire has
    # to lose that race and move on, not overwrite or ignore the peer's dir.
    _only_alive(monkeypatch, LIVE_PEER)
    slots = tmp_path / "wave-slots"
    contested = os.fspath(slots / "1")
    real_mkdir = os.mkdir
    peer_won: list[str] = []

    def racing_mkdir(path, *args, **kwargs):
        if os.fspath(path) == contested and not peer_won:
            peer_won.append(contested)
            real_mkdir(path, *args, **kwargs)  # the peer's claim lands first
            (slots / "1" / "owner").write_text(str(LIVE_PEER))
        return real_mkdir(path, *args, **kwargs)

    monkeypatch.setattr(os, "mkdir", racing_mkdir)
    slot = acquire(slots, 2, ME, sleep_fn=_no_sleep, clock=_fake_clock)
    assert peer_won, "acquire never tried to mkdir slot 1"
    assert slot == slots / "2"
    assert (slot / "owner").read_text().strip() == str(ME)
    # The peer's slot is still the peer's.
    assert (slots / "1" / "owner").read_text().strip() == str(LIVE_PEER)
