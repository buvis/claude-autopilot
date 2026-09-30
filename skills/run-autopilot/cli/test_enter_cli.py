#!/usr/bin/env python3
"""Tests for the `autopilot enter` CLI verb - the subprocess lane.

Split out of `test_enter.py` when that file passed the 800-line limit. Its
siblings drive `enter()` in-process; every test here runs the real verb as a
subprocess through `run_cli` and judges what it prints on stdout, what it
writes to stderr, and its exit code.

The expected JSON lines are hand-written literals (`_printed_line`), never a
value computed by `enter()` or by `enter_twin`, which calls it. An expectation
derived from the code under test makes that code its own oracle: a canned
implementation returning one constant dict for every tree satisfies it exactly.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from cli import custody, notify_out, schema, state
from cli.enter_harness import (
    KEYS,
    OTHER,
    PRD,
    Env,
    _custody_entry,
    _open_state,
    run_cli,
)


@pytest.fixture
def env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Env:
    monkeypatch.setattr(notify_out, "notify", lambda *a, **k: None)
    monkeypatch.delenv("_AUTOPILOT_LANES", raising=False)
    return Env(tmp_path)


def _printed_line(**overrides) -> dict:
    """The JSON line the verb must print for a clean `wip` pick, written out by
    hand; each caller states the fields its own fixture changes.

    Literal on purpose. An expected value computed by `enter()` — or by
    `enter_twin`, which calls it — makes the code under test its own oracle: a
    canned implementation returning one constant dict for every tree matches
    such an expectation exactly. These values are specified independently, so
    two fixtures whose decisions differ cannot both be satisfied by one reply.
    """
    return {
        "stop": None,
        "detail": "",
        "prd": PRD,
        "source": "wip",
        "parked": None,
        "custody_pending": 0,
        "lane_effective": "full",
        "catchup": "full",
        "design": "skip",
        "resume_target": "build: catchup then planning",
        "batch": "open",
        **overrides,
    }


def test_cli_prints_one_json_line_with_every_key(env: Env) -> None:
    env.write_state(_open_state())
    env.put("wip")
    expected = _printed_line()

    # no --prds: the verb must resolve it from the state path's parent
    proc = run_cli(env, "enter", "--state", str(env.state_path))

    assert proc.returncode == 0, proc.stderr
    lines = proc.stdout.splitlines()
    assert len(lines) == 1, proc.stdout
    assert set(json.loads(lines[0])) == KEYS
    # every value, not the key set alone, and `warnings` is returned to the
    # caller but never printed on stdout
    assert lines[0] == json.dumps(expected, sort_keys=True)
    # side effects no constant-printing stub produces: step 0's tree...
    assert (env.prds_dir / "backlog").is_dir()
    assert (env.autopilot_dir / "reports").is_dir()
    # ...and step 10's frontmatter fields, not only `prd`
    written = env.read_state()
    assert written["prd"] == PRD
    assert (written["design_mode"], written["lane_effective"]) == ("skip", "full")


def test_cli_moves_a_backlog_prd_into_wip(env: Env) -> None:
    env.write_state(_open_state())
    env.put("backlog")
    expected = _printed_line(source="backlog")

    proc = run_cli(env, "enter", "--state", str(env.state_path))

    assert proc.returncode == 0, proc.stderr
    assert proc.stdout == json.dumps(expected, sort_keys=True) + "\n"
    # the verified move happened in the real tree, not only in the printed line
    assert env.has("wip")
    assert not env.has("backlog")


@pytest.mark.parametrize("shape", ["{not json", "[]"], ids=["truncated", "not-object"])
def test_cli_unreadable_state_exits_two(env: Env, shape: str) -> None:
    env.state_path.write_text(shape, encoding="utf-8")
    env.put("wip")
    with pytest.raises(state.StateError) as raised:
        state.load(env.state_path)  # the real loader's own diagnostic

    proc = run_cli(env, "enter", "--state", str(env.state_path))

    assert proc.returncode == 2
    assert proc.stdout == ""
    assert f"enter failed: {raised.value}" in proc.stderr
    assert str(env.state_path) in proc.stderr
    assert env.state_path.read_text(encoding="utf-8") == shape


@pytest.mark.parametrize("bump", [1, 7])
def test_cli_future_schema_exits_six(env: Env, bump: int) -> None:
    version = schema.SCHEMA_VERSION + bump
    env.write_state(_open_state(schema_version=version))
    env.put("wip")
    before = env.state_path.read_bytes()

    proc = run_cli(env, "enter", "--state", str(env.state_path))

    assert proc.returncode == 6
    assert proc.stdout == ""
    assert f"v{version} > v{schema.SCHEMA_VERSION}" in proc.stderr
    assert str(env.state_path) in proc.stderr
    # refused before any effect: state byte-unchanged, step 0 never made the dirs
    assert env.state_path.read_bytes() == before
    assert not (env.prds_dir / "backlog").exists()


def test_cli_prd_flag_selects_the_named_prd(env: Env) -> None:
    env.write_state(_open_state())
    env.put("wip", PRD)  # the one plain selection would pick (lower number)
    env.put("wip", OTHER)
    expected = _printed_line(prd=OTHER, source="arg")

    proc = run_cli(env, "enter", "--state", str(env.state_path), "--prd", OTHER)

    assert proc.returncode == 0, proc.stderr
    assert proc.stdout == json.dumps(expected, sort_keys=True) + "\n"


def test_cli_in_loop_is_read_from_the_environment(env: Env) -> None:
    env.write_state(_open_state())
    env.put("wip")
    custody.write_marker(env.autopilot_dir / "critical-on-master", [_custody_entry()])
    argv = ("enter", "--state", str(env.state_path))

    inside = json.loads(run_cli(env, *argv, extra_env={"_AUTOPILOT_LOOP": "1"}).stdout)
    outside = json.loads(run_cli(env, *argv).stdout)

    assert (inside["stop"], inside["custody_pending"]) == (None, 1)
    assert (outside["stop"], outside["custody_pending"]) == ("custody", 1)
