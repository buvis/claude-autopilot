#!/usr/bin/env python3
"""`enter()`'s `prd_budget_since` tests (step 10), split out of test_enter.py
when it passed the 800-line limit (rules/coding-style.md). The fixture and
harness imports mirror test_enter.py: the same on-disk project-management
tree, only the clock injected.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from cli import notify_out
from cli.enter_harness import NOW, OTHER, PRD, Env, _open_state, _prd_text


@pytest.fixture
def env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Env:
    monkeypatch.setattr(notify_out, "notify", lambda *a, **k: None)
    monkeypatch.delenv("_AUTOPILOT_LANES", raising=False)
    return Env(tmp_path)


# -- prd_budget_since (step 10) ------------------------------------------------

LATER = "2026-10-01T00:00:00Z"
OLD_STAMP = "2020-01-01T00:00:00Z"


def test_budget_since_is_set_to_now_on_first_entry(env: Env) -> None:
    env.write_state(_open_state())
    env.put("wip")

    out = env.run(now=lambda: LATER)

    assert (out["stop"], out["prd"]) == (None, PRD)
    assert env.read_state()["prd_budget_since"] == LATER


def test_budget_since_is_kept_when_the_same_prd_is_entered_again(env: Env) -> None:
    env.write_state(_open_state())
    env.put("wip")
    env.run()
    assert env.read_state()["prd_budget_since"] == NOW

    out = env.run(now=lambda: LATER)

    assert (out["stop"], out["prd"]) == (None, PRD)
    assert env.read_state()["prd_budget_since"] == NOW


def test_budget_since_already_in_state_survives_same_prd_reentry(env: Env) -> None:
    env.write_state(_open_state(prd=PRD, prd_budget_since=OLD_STAMP))
    env.put("wip")

    out = env.run(prd_arg=PRD, now=lambda: LATER)

    assert (out["stop"], out["prd"]) == (None, PRD)
    assert env.read_state()["prd_budget_since"] == OLD_STAMP


@pytest.mark.parametrize(
    "previous", [{"prd": OTHER}, {}], ids=["other-prd", "prd-absent"]
)
def test_budget_since_is_refreshed_when_the_previous_prd_differs(
    env: Env, previous: dict
) -> None:
    env.write_state(_open_state(prd_budget_since=OLD_STAMP, **previous))
    env.put("wip")

    out = env.run(prd_arg=PRD, now=lambda: LATER)

    assert (out["stop"], out["prd"]) == (None, PRD)
    assert env.read_state()["prd_budget_since"] == LATER


def test_budget_since_is_refreshed_on_a_switch_to_another_prd(env: Env) -> None:
    env.write_state(_open_state())
    env.put("wip")
    env.put("wip", OTHER)
    env.run(prd_arg=PRD)
    assert env.read_state()["prd_budget_since"] == NOW

    out = env.run(prd_arg=OTHER, now=lambda: LATER)

    assert (out["stop"], out["prd"]) == (None, OTHER)
    assert env.read_state()["prd_budget_since"] == LATER


def test_budget_since_is_set_when_absent_on_same_prd_reentry(env: Env) -> None:
    env.write_state(_open_state(prd=PRD))
    env.put("wip")

    out = env.run(prd_arg=PRD, now=lambda: LATER)

    assert out["stop"] is None
    assert out["prd"] == PRD
    assert env.read_state()["prd_budget_since"] == LATER


def test_budget_since_is_set_before_the_lane_stop(env: Env) -> None:
    env.write_state(_open_state())
    env.put("wip", PRD, _prd_text(lane="solo"))

    out = env.run(now=lambda: LATER)

    assert (out["stop"], out["prd"]) == ("lane", PRD)
    assert env.read_state()["prd_budget_since"] == LATER
