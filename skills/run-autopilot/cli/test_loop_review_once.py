"""Tests for Loop.run_once() - the `autopilot review-once` verb (PRD 00149).

One session, no acting branches: the loop's preflights, a phase guard
that refuses anything but review/done before spawning, one routed
spawn, the decision read, one metrics row, exit. No relaunch, no park,
no notification, and the operator's pause marker is left where it is.

Fixtures come from cli/test_loop.py rather than being duplicated (that
file is already past 1300 lines; these nine cases would push it further).
"""

from __future__ import annotations

import json

import pytest

from cli.loop import Loop
from cli.routing import OPUS, SONNET
from cli.test_loop import (
    _spawn_tagged_incumbent,
    make_loop,
    noop_step,
    write_log,
    write_state,
)


@pytest.fixture(autouse=True)
def _no_real_orphan_sweep(monkeypatch):
    """run_once() sweeps orphans like the loop does; keep it off the
    real process table. test_loop.py's own autouse fixture does not
    reach this module."""
    monkeypatch.setattr(Loop, "_cleanup_orphans", lambda self: None)


def _review_step(next_phase: str = "build"):
    def step(ap_dir) -> None:
        (ap_dir / "state.json").write_text(
            json.dumps(
                {"prd": "p.md", "next_phase": next_phase, "batch": {"id": "b"}},
            ),
        )
        write_log(
            ap_dir,
            {"type": "result", "total_cost_usd": 0.01, "usage": {"output_tokens": 10}},
        )

    return step


def test_review_once_spawns_the_review_route_once_and_exits_zero(tmp_path):
    lp = make_loop(tmp_path, [_review_step()])
    write_state(lp._test["ap_dir"], prd="p.md", next_phase="review", batch={"id": "b"})

    assert lp.run_once() == 0
    assert lp._test["spawn"].launches == [
        {"model": OPUS, "effort": "xhigh", "cap_secs": 10800},
    ]
    out = lp._test["out"].getvalue()
    assert "signal continue" in out
    assert "next phase 'build'" in out


def test_review_once_finalize_routes_sonnet_medium(tmp_path):
    lp = make_loop(tmp_path, [_review_step(next_phase="")])
    write_state(lp._test["ap_dir"], prd="p.md", next_phase="done", batch={"id": "b"})

    assert lp.run_once() == 0
    assert lp._test["spawn"].launches == [
        {"model": SONNET, "effort": "medium", "cap_secs": 7200},
    ]


def test_review_once_refuses_a_build_phase_without_spawning(tmp_path):
    lp = make_loop(tmp_path, [])
    write_state(lp._test["ap_dir"], prd="p.md", next_phase="build", batch={"id": "b"})

    assert lp.run_once() == 1
    assert lp._test["spawn"].launches == []
    err = lp._test["err"].getvalue()
    assert "review-once" in err
    assert "build" in err


def test_review_once_refuses_without_state_json(tmp_path):
    lp = make_loop(tmp_path, [])

    assert lp.run_once() == 1
    assert lp._test["spawn"].launches == []
    assert "next_phase is 'missing'" in lp._test["err"].getvalue()


def test_review_once_dead_session_exits_one_without_retry_or_park(tmp_path):
    lp = make_loop(tmp_path, [noop_step])
    write_state(lp._test["ap_dir"], prd="p.md", next_phase="review", batch={"id": "b"})
    wip = tmp_path / "repo" / "dev" / "local" / "prds" / "wip"
    wip.mkdir(parents=True)
    (wip / "00001-x.md").write_text("# x\n")

    assert lp.run_once() == 1
    assert len(lp._test["spawn"].launches) == 1
    assert (wip / "00001-x.md").is_file()
    assert lp._test["notify"].calls == []


def test_review_once_exits_zero_when_the_session_pauses(tmp_path):
    def paused(ap_dir) -> None:
        (ap_dir / "state.json").write_text(
            json.dumps(
                {
                    "prd": "p.md",
                    "next_phase": "review",
                    "phase": "paused",
                    "cap_pause_reason": {
                        "cycle": 3,
                        "cap": 3,
                        "unresolved_findings": [
                            {"severity": "High", "issue": "the gate lies"},
                        ],
                    },
                    "batch": {"id": "b"},
                },
            ),
        )

    lp = make_loop(tmp_path, [paused])
    write_state(lp._test["ap_dir"], prd="p.md", next_phase="review", batch={"id": "b"})

    assert lp.run_once() == 0
    assert "signal paused" in lp._test["out"].getvalue()
    assert lp._test["notify"].calls == []


def test_review_once_writes_one_metrics_line(tmp_path):
    lp = make_loop(tmp_path, [_review_step()])
    ap_dir = lp._test["ap_dir"]
    write_state(ap_dir, prd="p.md", next_phase="review", batch={"id": "b"})

    assert lp.run_once() == 0
    rows = [
        json.loads(line)
        for line in (ap_dir / "loop-metrics.jsonl").read_text().splitlines()
        if line.strip()
    ]
    assert len(rows) == 1
    assert rows[0]["phase_launched"] == "review"


def test_review_once_leaves_the_pause_marker_in_place(tmp_path):
    lp = make_loop(tmp_path, [_review_step()])
    ap_dir = lp._test["ap_dir"]
    write_state(ap_dir, prd="p.md", next_phase="review", batch={"id": "b"})
    marker = ap_dir / "pause-requested"
    marker.touch()

    assert lp.run_once() == 0
    assert marker.is_file()
    assert len(lp._test["spawn"].launches) == 1


def test_review_once_shares_the_loops_interrupt_contract(tmp_path):
    # The wrapper is extracted, not duplicated - so Ctrl-C during the
    # one-shot's session must exit 130 exactly as it does in the loop.
    def interrupted(*args, **kwargs):
        raise KeyboardInterrupt

    lp = make_loop(tmp_path, [], spawn_fn=interrupted)
    write_state(lp._test["ap_dir"], prd="p.md", next_phase="review", batch={"id": "b"})

    assert lp.run_once() == 130


def test_review_once_refuses_when_a_loop_is_live(tmp_path):
    loops = tmp_path / "loops"
    loops.mkdir()
    lp = make_loop(tmp_path, [])
    write_state(lp._test["ap_dir"], prd="p.md", next_phase="review", batch={"id": "b"})
    incumbent = _spawn_tagged_incumbent()
    try:
        (loops / f"{incumbent.pid}.json").write_text(
            json.dumps({"pid": incumbent.pid, "root": str(tmp_path / "repo")}),
        )
        assert lp.run_once() == 1
        assert "already running" in lp._test["err"].getvalue()
        assert lp._test["spawn"].launches == []
    finally:
        incumbent.kill()
        incumbent.wait()
