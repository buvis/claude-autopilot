#!/usr/bin/env python3
"""Tests for cli/wave_slots.py - `release` in the caller's `finally:`.

Two contracts: releasing never resurrects a slots directory that `wave land`
or `wave abort` already removed, and it never raises, not even from the
per-slot lock. The rest of the slot tests live in `test_wave_slots.py`.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from cli import wave_slots
from cli.wave_slots import release

ME = 4242


def _stderr_lines(capsys) -> list[str]:
    return [line for line in capsys.readouterr().err.splitlines() if line.strip()]


def _held_slot(slots: Path) -> Path:
    slot = slots / "1"
    slot.mkdir(parents=True)
    (slot / "owner").write_text(str(ME))
    return slot


def test_release_creates_nothing_when_the_slots_dir_is_already_torn_down(
    tmp_path,
    capsys,
):
    slots = tmp_path / "wave-slots"

    assert release(slots / "1", ME) is None

    assert not slots.exists(), "release recreated the torn-down slots dir"
    assert list(tmp_path.iterdir()) == [], "release left a slot or lock behind"
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == ""


def test_release_creates_nothing_when_the_slots_dir_vanishes_before_the_lock(
    tmp_path,
    monkeypatch,
):
    slots = tmp_path / "wave-slots"
    slot = _held_slot(slots)
    real_lock = wave_slots._slot_lock

    def lock_after_teardown(*args, **kwargs):
        # `wave land` removes the slots dir after the caller decided to
        # release but before the lock is taken.
        shutil.rmtree(slots)
        return real_lock(*args, **kwargs)

    monkeypatch.setattr(wave_slots, "_slot_lock", lock_after_teardown)

    assert release(slot, ME) is None

    assert not slots.exists(), "release recreated the slots dir under a lock"
    assert list(tmp_path.iterdir()) == [], "release left a slot or lock behind"


def test_release_reports_a_lock_failure_instead_of_raising_and_keeps_the_slot(
    tmp_path,
    monkeypatch,
    capsys,
):
    slots = tmp_path / "wave-slots"
    slot = _held_slot(slots)

    def lock_denied(*args, **kwargs):
        raise PermissionError("Permission denied")

    monkeypatch.setattr(wave_slots, "_slot_lock", lock_denied)

    try:
        result = release(slot, ME)
    except OSError as exc:
        pytest.fail(f"release raised {type(exc).__name__} from the lock: {exc}")

    assert result is None
    lines = _stderr_lines(capsys)
    assert len(lines) == 1, f"expected one report of the failure, got {lines}"
    assert str(slot) in lines[0], lines[0]
    assert slot.is_dir(), "release must not guess when it could not take the lock"
    assert (slot / "owner").read_text() == str(ME)
