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
    return sorted(p.name for p in slots_dir.iterdir())


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
