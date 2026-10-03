"""Tests for the review-slot wrap around Loop._launch.

A review session claims a slot under _AUTOPILOT_REVIEW_SLOTS_DIR before
it spawns and frees it after, even when the spawn raises. Build
sessions, and loops without the dir variable, never touch a slot. The
semaphore itself (cli.wave_slots) runs for real on dirs under tmp_path.

Shared fixtures come from cli/loop_testutil.py.
"""

from __future__ import annotations

import os
import shutil

import pytest

from cli import loop_testutil
from cli.loop_testutil import make_loop, terminal_step, write_state

_no_real_drain_side_effects = loop_testutil._no_real_drain_side_effects


def _slot_env(slots_dir) -> dict:
    return {
        "_AUTOPILOT_REVIEW_SLOTS_DIR": str(slots_dir),
        "_AUTOPILOT_REVIEW_SLOTS": "1",
    }


def _held_slots(slots_dir) -> list[str]:
    return sorted(p.name for p in slots_dir.iterdir() if not p.name.endswith(".lock"))


def _recording_step(slots_dir, events: list):
    """A terminal session that records whether slot 1 was claimed
    while it ran."""
    inner = terminal_step()

    def step(ap_dir) -> None:
        events.append(("spawn", (slots_dir / "1" / "owner").is_file()))
        inner(ap_dir)

    return step


def test_review_launch_waits_for_a_slot(tmp_path, monkeypatch):
    slots_dir = tmp_path / "state" / "wave-slots"
    held = slots_dir / "1"
    held.mkdir(parents=True)
    (held / "owner").write_text(str(os.getpid()))
    events: list = []
    lp = make_loop(
        tmp_path, [_recording_step(slots_dir, events)], env=_slot_env(slots_dir)
    )
    write_state(lp._test["ap_dir"], prd="p.md", next_phase="review", batch={"id": "b"})

    def sleep(secs: float) -> None:
        events.append(("sleep", held.exists()))
        if held.exists():
            shutil.rmtree(held)
        if len(events) > 5:
            raise AssertionError("the loop never claimed the freed slot")

    monkeypatch.setattr(lp, "_sleep", sleep)

    assert lp.run() == 0
    kinds = [kind for kind, _ in events]
    assert events[0] == ("sleep", True)  # waited while the slot was held
    assert kinds.count("spawn") == 1
    assert events[kinds.index("spawn")] == ("spawn", True)  # loop held slot 1
    assert len(lp._test["spawn"].launches) == 1
    assert _held_slots(slots_dir) == []


def test_review_launch_honours_the_configured_slot_count(tmp_path, monkeypatch):
    slots_dir = tmp_path / "state" / "wave-slots"
    held = slots_dir / "1"
    held.mkdir(parents=True)
    (held / "owner").write_text(str(os.getpid()))
    seen: list = []

    def step(ap_dir) -> None:
        seen.append((slots_dir / "2" / "owner").is_file())
        terminal_step()(ap_dir)

    env = {**_slot_env(slots_dir), "_AUTOPILOT_REVIEW_SLOTS": "2"}
    lp = make_loop(tmp_path, [step], env=env)
    write_state(lp._test["ap_dir"], prd="p.md", next_phase="review", batch={"id": "b"})
    sleeps: list = []

    def sleep(secs: float) -> None:
        # Records only; never frees slot 1. Raising stops a loop that
        # ignores the count from waiting on slot 1 forever.
        sleeps.append(secs)
        raise AssertionError("slept although slot 2 was free")

    monkeypatch.setattr(lp, "_sleep", sleep)

    assert lp.run() == 0
    assert sleeps == []  # slot 2 was free, so no wait at all
    assert seen == [True]  # the session ran holding slot 2
    assert len(lp._test["spawn"].launches) == 1
    assert (held / "owner").read_text() == str(os.getpid())  # slot 1 untouched
    assert _held_slots(slots_dir) == ["1"]  # slot 2 released


def test_review_slot_owner_is_the_loop_identity(tmp_path):
    slots_dir = tmp_path / "state" / "wave-slots"
    loop_tag = "1"  # never the test process's own pid
    assert loop_tag != str(os.getpid())
    owners: list = []

    def step(ap_dir) -> None:
        owners.append((slots_dir / "1" / "owner").read_text().strip())
        terminal_step()(ap_dir)

    env = {**_slot_env(slots_dir), "_AUTOPILOT_LOOP": loop_tag}
    lp = make_loop(tmp_path, [step], env=env)
    assert lp.loop_pid == int(loop_tag)
    write_state(lp._test["ap_dir"], prd="p.md", next_phase="review", batch={"id": "b"})

    assert lp.run() == 0
    assert owners == [loop_tag]  # the loop's tracked pid, not os.getpid()
    assert _held_slots(slots_dir) == []


def test_build_launch_never_touches_slots(tmp_path):
    slots_dir = tmp_path / "state" / "wave-slots"
    lp = make_loop(tmp_path, [terminal_step()], env=_slot_env(slots_dir))
    write_state(lp._test["ap_dir"], prd="p.md", next_phase="build", batch={"id": "b"})

    assert lp.run() == 0
    assert len(lp._test["spawn"].launches) == 1
    assert not slots_dir.exists()


@pytest.mark.parametrize("verb", ["run", "run_once"])
def test_slot_is_released_after_the_session(tmp_path, verb):
    slots_dir = tmp_path / "state" / "wave-slots"
    events: list = []
    lp = make_loop(
        tmp_path, [_recording_step(slots_dir, events)], env=_slot_env(slots_dir)
    )
    write_state(lp._test["ap_dir"], prd="p.md", next_phase="review", batch={"id": "b"})

    assert getattr(lp, verb)() == 0
    assert events == [("spawn", True)]  # slot 1 held during the session
    assert len(lp._test["spawn"].launches) == 1
    assert slots_dir.is_dir()
    assert _held_slots(slots_dir) == []  # and freed after it


@pytest.mark.parametrize("verb", ["run", "run_once"])
def test_slot_is_released_when_the_spawn_raises(tmp_path, verb):
    slots_dir = tmp_path / "state" / "wave-slots"
    seen: list = []

    def boom(*args, **kwargs):
        seen.append((slots_dir / "1" / "owner").is_file())
        raise RuntimeError("boom")

    lp = make_loop(tmp_path, [], spawn_fn=boom, env=_slot_env(slots_dir))
    write_state(lp._test["ap_dir"], prd="p.md", next_phase="review", batch={"id": "b"})

    with pytest.raises(RuntimeError, match="boom"):
        getattr(lp, verb)()
    assert seen == [True]  # the slot was claimed before the spawn
    assert slots_dir.is_dir()
    assert _held_slots(slots_dir) == []  # the release ran despite the raise


def test_no_slot_dir_means_no_semaphore(tmp_path):
    slots_dir = tmp_path / "state" / "wave-slots"
    lp = make_loop(tmp_path, [terminal_step()], env={"_AUTOPILOT_REVIEW_SLOTS": "1"})
    write_state(lp._test["ap_dir"], prd="p.md", next_phase="review", batch={"id": "b"})

    assert lp.run() == 0
    assert len(lp._test["spawn"].launches) == 1
    assert not slots_dir.exists()
    assert not (tmp_path / "state").exists()


def test_review_metrics_ts_start_excludes_the_slot_wait(tmp_path, monkeypatch):
    slots_dir = tmp_path / "state" / "wave-slots"
    held = slots_dir / "1"
    held.mkdir(parents=True)
    (held / "owner").write_text(str(os.getpid()))
    lp = make_loop(tmp_path, [terminal_step()], env=_slot_env(slots_dir))
    write_state(lp._test["ap_dir"], prd="p.md", next_phase="review", batch={"id": "b"})
    clock = lp._test["clock"]
    acquired_at = None
    calls = 0

    def sleep(secs: float) -> None:
        nonlocal acquired_at, calls
        calls += 1
        if calls > 5:
            raise AssertionError("the loop never claimed the freed slot")
        clock.sleep(1000)  # advance the fake clock across the wait
        if held.exists():
            shutil.rmtree(held)
        acquired_at = clock.now

    monkeypatch.setattr(lp, "_sleep", sleep)

    assert lp.run() == 0
    assert acquired_at is not None  # confirms the wait actually happened
    rows = loop_testutil.metrics_rows(lp._test["ap_dir"])
    assert len(rows) == 1
    # ts_start marks when the session started, not when the loop began
    # waiting for the slot: no earlier than the clock reading taken when
    # the wait ended and the slot was claimed.
    assert rows[0]["ts_start"] >= acquired_at
    # wall_secs describes the session, not the ~1000s spent queued.
    assert rows[0]["wall_secs"] < 500


def test_build_launch_ts_start_matches_pre_launch_clock(tmp_path):
    slots_dir = tmp_path / "state" / "wave-slots"
    lp = make_loop(tmp_path, [terminal_step()], env=_slot_env(slots_dir))
    write_state(lp._test["ap_dir"], prd="p.md", next_phase="build", batch={"id": "b"})
    before = lp._test["clock"].now

    assert lp.run() == 0

    rows = loop_testutil.metrics_rows(lp._test["ap_dir"])
    assert len(rows) == 1
    assert rows[0]["ts_start"] == int(before)  # no wait, no timing change


def test_review_launch_without_slots_dir_ts_start_matches_pre_launch_clock(tmp_path):
    lp = make_loop(tmp_path, [terminal_step()], env={"_AUTOPILOT_REVIEW_SLOTS": "1"})
    write_state(lp._test["ap_dir"], prd="p.md", next_phase="review", batch={"id": "b"})
    before = lp._test["clock"].now

    assert lp.run() == 0

    rows = loop_testutil.metrics_rows(lp._test["ap_dir"])
    assert len(rows) == 1
    assert rows[0]["ts_start"] == int(before)  # no slots dir, no wait, no change
