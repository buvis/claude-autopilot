#!/usr/bin/env python3
"""Tests for cli/enter.py - the step 10/11 decisions: the frontmatter write,
the default handoff row, the lane override, and catchup freshness against a
moving clock, plus the `--prd` argument checks that reject any value which is
not a bare basename. Split from test_enter.py for size; shares its Env harness.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from cli import enter, frontmatter, notify_out
from cli.enter_harness import OTHER, PRD, Env, _cache, _open_state, _prd_text


@pytest.fixture
def env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Env:
    monkeypatch.setattr(notify_out, "notify", lambda *a, **k: None)
    monkeypatch.delenv("_AUTOPILOT_LANES", raising=False)
    return Env(tmp_path)


# -- step 10: frontmatter write, handoff row, lane -----------------------------


def test_default_resume_row_runs_the_record_dispatch_handoff(env: Env, monkeypatch) -> None:
    env.write_state(_open_state())
    env.put("wip")
    real_run = subprocess.run
    calls: list[tuple[list, dict]] = []

    def fake_run(args, *a, **k):
        if isinstance(args, list) and str(enter._RECORD_DISPATCH) in args:
            calls.append((args, k))
            return subprocess.CompletedProcess(args, 0, "", "")
        return real_run(args, *a, **k)

    monkeypatch.setattr(subprocess, "run", fake_run)

    out = env.run(default_recorder=True)

    assert out["stop"] is None
    assert [args for args, _ in calls] == [[
        "python3", str(enter._RECORD_DISPATCH), "handoff", "--site", "build",
        "--edge", "resume", "--phase", "build", "--prd", PRD,
    ]]
    assert calls[0][1]["timeout"] == 10


def test_lanes_off_forces_a_solo_prd_to_the_full_lane(env: Env, monkeypatch) -> None:
    monkeypatch.setenv("_AUTOPILOT_LANES", "off")
    env.write_state(_open_state())
    env.put("wip", PRD, _prd_text(lane="solo"))

    out = env.run()

    assert (out["stop"], out["lane_effective"]) == (None, "full")
    assert env.read_state()["lane_effective"] == "full"


def test_frontmatter_fields_land_in_state_as_declared_or_default(env: Env) -> None:
    env.write_state(_open_state())
    env.put("wip", PRD, _prd_text(doubt_reviewer="fable", rework_cap="5", session_model="opus"))

    out = env.run()

    assert out["stop"] is None
    data = env.read_state()
    keys = ("catchup_mode", "design_mode", "rework_cap", "doubt_reviewer",
            "consensus_engine", "session_model")
    assert {k: data.get(k) for k in keys} == {
        "catchup_mode": "run", "design_mode": "skip", "rework_cap": 5,
        "doubt_reviewer": "fable", "consensus_engine": "legacy", "session_model": "opus",
    }


def test_invalid_frontmatter_value_takes_the_default(env: Env) -> None:
    # enter() is a pure function that returns a dict (see its docstring); it
    # has no stdout/stderr contract of its own. Printing `frontmatter.apply`'s
    # warnings, if any, is the CLI wrapper's job (a later task), not this
    # function's — so this test only pins the one behavior the Contract
    # actually promises: an invalid value still resolves to its default.
    text = _prd_text(consensus_engine="bogus")
    env.write_state(_open_state())
    env.put("wip", PRD, text)
    _fields, warnings = frontmatter.parse(text)
    assert len(warnings) == 1

    out = env.run()

    assert out["stop"] is None
    assert env.read_state()["consensus_engine"] == "legacy"


# -- step 11: catchup freshness against the injected clock ---------------------


@pytest.mark.parametrize(
    ("now", "completed_at", "expected"),
    [
        ("2026-09-29T14:30:00Z", "2026-09-29T11:00:00Z", "delta"),
        ("2026-09-30T12:00:00Z", "2026-09-29T11:00:00Z", "full"),
        ("2026-09-29T12:00:00Z", "2026-09-29T08:01:00Z", "delta"),
        ("2026-09-29T12:00:00Z", "2026-09-29T07:59:00Z", "full"),
        ("2026-09-30T02:00:00Z", "2026-09-29T22:01:00Z", "delta"),
        ("2026-09-30T02:00:00Z", "2026-09-29T21:59:00Z", "full"),
    ],
    ids=["3h30m", "same-cache-a-day-later", "3h59m", "4h01m",
         "3h59m-across-midnight", "4h01m-across-midnight"],
)
def test_catchup_freshness_is_four_hours_before_now(
    env: Env, now: str, completed_at: str, expected: str,
) -> None:
    env.write_state(_open_state(batch=_cache(catchup_completed_at=completed_at)))
    env.put("wip")

    out = env.run(now=lambda: now)

    assert (out["stop"], out["catchup"]) == (None, expected)


# -- the --prd argument must be a bare basename -------------------------------


def _assert_rejected(out: dict, prd_arg: str) -> None:
    """The rejection contract: the `prd_not_found` stop, nothing selected, and a
    detail naming both the offending argument and the rule it broke."""
    assert (out["stop"], out["prd"], out["source"]) == ("prd_not_found", None, None)
    assert out["detail"] and prd_arg in out["detail"]
    assert "bare basename" in out["detail"].lower()


@pytest.mark.parametrize(
    "prd_arg",
    [f"../hold/{OTHER}", f"./{PRD}", f"prds/wip/{PRD}", f"wip/{PRD}", "sub/x.md",
     f"{PRD}/", f"a/../{PRD}", ".", "..", "/etc/passwd"],
    ids=["parent-traversal-reaching-hold", "dot-slash-reaching-wip", "nested-relative",
         "nested-into-wip", "nested-unrelated", "trailing-separator", "dot-dot-inside",
         "the-wip-folder-itself", "the-parent-folder-itself", "absolute-outside-the-tree"],
)
def test_a_prd_arg_that_is_not_a_bare_basename_is_rejected(env: Env, prd_arg: str) -> None:
    # Both arranged files are reachable by joining the argument onto a PRD
    # folder, so a run that consults the filesystem would select one of them;
    # the rejection has to fire before that lookup happens. The shapes that reach
    # nothing (`sub/x.md`, `/etc/passwd`) need no arrangement at all - the rule
    # fires before any disk access, so absence is not what stops them.
    env.write_state(_open_state())
    env.put("wip", PRD)
    env.put("hold", OTHER)

    out = env.run(prd_arg=prd_arg)

    _assert_rejected(out, prd_arg)
    assert env.has("hold", OTHER) and env.has("wip", PRD)
    assert not env.has("wip", OTHER)


def test_a_nested_prd_arg_is_rejected_even_when_it_resolves_inside_wip(env: Env) -> None:
    # Joined onto the wip folder this argument reaches a real file, so a run that
    # consults the filesystem ACCEPTS it. Only a rule applied before the lookup
    # rejects it - a missing target cannot be what does the work here.
    nested = f"prds/wip/{PRD}"
    env.write_state(_open_state())
    env.put("wip", PRD)
    env.put("wip", nested)

    out = env.run(prd_arg=nested)

    _assert_rejected(out, nested)
    assert env.has("wip", nested) and env.has("wip", PRD)


def test_an_absolute_prd_arg_is_rejected_even_though_that_file_exists(env: Env) -> None:
    env.write_state(_open_state())
    target = env.put("hold", OTHER)

    out = env.run(prd_arg=str(target))

    _assert_rejected(out, str(target))
    assert env.has("hold", OTHER)
    assert not env.has("wip", OTHER)


@pytest.mark.parametrize("name", [PRD, OTHER], ids=["sample-prd", "other-prd"])
def test_a_bare_basename_in_wip_is_still_selected_from_the_argument(env: Env, name: str) -> None:
    env.write_state(_open_state())
    env.put("wip", name)

    out = env.run(prd_arg=name)

    assert (out["stop"], out["prd"], out["source"]) == (None, name, "arg")
    assert env.has("wip", name)


@pytest.mark.parametrize("name", [PRD, OTHER], ids=["sample-prd", "other-prd"])
def test_a_bare_basename_in_backlog_is_still_moved_into_wip(env: Env, name: str) -> None:
    env.write_state(_open_state())
    env.put("backlog", name)

    out = env.run(prd_arg=name)

    assert (out["stop"], out["prd"], out["source"]) == (None, name, "arg")
    assert env.has("wip", name) and not env.has("backlog", name)
