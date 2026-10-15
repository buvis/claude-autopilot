"""Tests for cli/loop_decision.py's decision table (PRD 00192/00199): state
write failure, pause/review-cap, subagent replan, the died retry ladder,
usage-limit wait and window yield, network outage, and the no-progress
fingerprint bound.

Split out of test_loop_decision.py (PRD 00282, review finding 7: that file
crossed the 800-line limit). The pure ports and the newer instant-exit
acceptance tests (PRD 00282) stay at test_loop_decision.py's pinned path,
including `_rejected_event`, which this file imports back since both
files' usage-limit tests need it. The harness (fake clock, scripted spawn,
make_loop) is cli/loop_testutil.py.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path

from cli import loop_testutil, usage_limit
from cli.loop_testutil import (
    FakeClock,
    _notified,
    make_loop,
    metrics_rows,
    noop_step,
    terminal_step,
    write_log,
    write_state,
)
from cli.test_loop_decision import _rejected_event

# The autouse fixture registers by being a module attribute.
_no_real_drain_side_effects = loop_testutil._no_real_drain_side_effects


def test_state_write_failed_marker_wins_over_a_healthy_state(tmp_path):
    def step(ap_dir: Path) -> None:
        terminal_step()(ap_dir)
        (ap_dir / "state-write-failed").write_text(
            json.dumps({"detail": "transaction raised"}),
        )

    lp = make_loop(tmp_path, [step])
    assert lp.run() == 1
    assert "transaction raised" in lp._test["err"].getvalue()
    assert _notified(lp, "State write failed")


def test_paused_state_prints_detail_runbook_and_notifies(tmp_path):
    def step(ap_dir: Path) -> None:
        (ap_dir / "state.json").write_text(
            json.dumps(
                {
                    "prd": "p.md",
                    "next_phase": "review",
                    "pause_reason": {"detail": "design gate needs the operator"},
                    "batch": {"id": "b"},
                },
            ),
        )

    lp = make_loop(tmp_path, [step])
    assert lp.run() == 1
    err = lp._test["err"].getvalue()
    assert "design gate needs the operator" in err
    assert "/autopilot:run-autopilot" in err
    assert _notified(lp, "Paused: design gate needs the operator")


def test_review_cap_pause_summarizes_and_lists_findings(tmp_path):
    def step(ap_dir: Path) -> None:
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
                            {"severity": "Low", "issue": "typo"},
                        ],
                    },
                    "batch": {"id": "b"},
                },
            ),
        )

    lp = make_loop(tmp_path, [step])
    assert lp.run() == 1
    err = lp._test["err"].getvalue()
    assert "review cap hit: cycle 3/3 · 2 unresolved findings" in err
    assert "[High] the gate lies" in err


def test_subagent_prompt_overrun_replans_in_place(tmp_path):
    def overrun(ap_dir: Path) -> None:
        (ap_dir / "state.json").write_text(
            json.dumps(
                {
                    "prd": "p.md",
                    "next_phase": "build",
                    "stall_reason": {"stalled": "subagent_prompt_overrun"},
                    "batch": {"id": "b"},
                },
            ),
        )

    lp = make_loop(tmp_path, [overrun, terminal_step()])
    assert lp.run() == 0
    assert "replanned" in lp._test["out"].getvalue()


def test_bootstrap_death_halts_loud_with_no_state(tmp_path):
    lp = make_loop(tmp_path, [noop_step])
    assert lp.run() == 1
    assert "no state.json" in lp._test["err"].getvalue()
    assert _notified(lp, "Needs attention")


def test_unreadable_state_death_names_it(tmp_path):
    def step(ap_dir: Path) -> None:
        (ap_dir / "state.json").write_text("{broken")

    lp = make_loop(tmp_path, [step])
    assert lp.run() == 1
    assert "state.json unreadable" in lp._test["err"].getvalue()


def test_died_session_retries_once_then_parks_then_guard_halts(tmp_path):
    # A valid but never-touched state: retry 1/1, then park (marker +
    # notify ⏭), then the unconsumed-marker guard backs off once and
    # halts on the second relaunch. Four sessions total.
    lp = make_loop(tmp_path, [noop_step, noop_step, noop_step, noop_step])
    ap = lp._test["ap_dir"]
    write_state(ap, prd="00044-x-v1.md", next_phase="build", batch={"id": "b"})
    rc = lp.run()
    assert rc == 1
    out = lp._test["out"].getvalue()
    err = lp._test["err"].getvalue()
    # The retry detail is recorded in the decision, not printed - the
    # bash act branch prints the plain continue line (parity).
    assert "Continuing (next phase: build)" in out
    assert "parking 00044-x-v1.md" in out
    marker = json.loads((ap / "park-requested").read_text())
    assert marker["prd"] == "00044-x-v1.md"
    assert "died after 1 retries" in marker["reason"]
    assert "park-requested pending (relaunch 1)" in err
    assert 30 in lp._test["sleeps"]
    assert "park-requested unconsumed (2 relaunches" in err
    assert _notified(lp, "Park marker unconsumed")
    assert _notified(lp, "Parking 00044-x-v1.md (died after 1 retries")
    assert len(lp._test["spawn"].launches) == 4


def test_usage_limit_waits_then_resumes(tmp_path):
    clock = FakeClock()
    reset = int(clock.now) + 300
    lp = make_loop(
        tmp_path,
        [noop_step, terminal_step()],
        clock=clock,
        detect_limit_fn=lambda path: reset,
    )
    write_state(lp._test["ap_dir"], prd="p.md", next_phase="build", batch={"id": "b"})
    assert lp.run() == 0
    assert any(secs >= 300 for secs in lp._test["sleeps"])
    assert _notified(lp, "Usage limit")
    assert "usage-limit; resuming ~" in lp._test["out"].getvalue()


def test_usage_limit_beyond_the_wait_cap_dies(tmp_path):
    clock = FakeClock()
    lp = make_loop(
        tmp_path,
        [noop_step],
        clock=clock,
        detect_limit_fn=lambda path: int(clock.now) + 50_000,
    )
    write_state(lp._test["ap_dir"], prd="p.md", next_phase="build", batch={"id": "b"})
    assert lp.run() == 1
    assert "beyond _AUTOPILOT_LIMIT_WAIT_MAX" in lp._test["err"].getvalue()


def _progress_then_rejected(reset: int):
    """A session that advanced state AND ended with a rejected event."""

    def step(ap_dir: Path) -> None:
        (ap_dir / "state.json").write_text(
            json.dumps({"prd": "p.md", "next_phase": "review", "batch": {"id": "b"}}),
        )
        write_log(ap_dir, {"type": "result", "total_cost_usd": 0.01}, _rejected_event(reset))

    return step


def test_rejected_with_overage_allowed_still_sleeps(tmp_path):
    # PRD 00199: progress made, tail carries rejected + overageStatus allowed.
    # The loop sleeps to the reset before relaunching instead of spending
    # overage. The event's staleness check reads the real clock, so the fake
    # clock starts at real time here.
    clock = FakeClock(start=time.time())
    reset = int(clock.now) + 300
    lp = make_loop(
        tmp_path,
        [_progress_then_rejected(reset), terminal_step()],
        clock=clock,
    )
    write_state(lp._test["ap_dir"], prd="p.md", next_phase="build", batch={"id": "b"})
    assert lp.run() == 0
    assert any(secs >= 300 for secs in lp._test["sleeps"])
    assert "usage limit hit; waiting" in lp._test["out"].getvalue()
    assert _notified(lp, "Usage limit")
    assert len(lp._test["spawn"].launches) == 2
    rows = metrics_rows(lp._test["ap_dir"])
    assert rows[0]["signal"] == "continue" and rows[0]["limit_wait"] >= 300
    assert "limit_wait" not in rows[1]


def test_rejected_beyond_cap_still_dies(tmp_path):
    clock = FakeClock(start=time.time())
    lp = make_loop(
        tmp_path,
        [_progress_then_rejected(int(clock.now) + 50_000)],
        clock=clock,
    )
    write_state(lp._test["ap_dir"], prd="p.md", next_phase="build", batch={"id": "b"})
    assert lp.run() == 1
    assert "beyond _AUTOPILOT_LIMIT_WAIT_MAX" in lp._test["err"].getvalue()
    assert len(lp._test["spawn"].launches) == 1


def test_progress_path_ignores_a_limit_banner_in_prose(tmp_path):
    # Hand-off text that merely mentions a limit is not a hit: only the
    # rejected event schedules a wait after a session that made progress.
    def progress_with_prose(ap_dir: Path) -> None:
        (ap_dir / "state.json").write_text(
            json.dumps({"prd": "p.md", "next_phase": "review", "batch": {"id": "b"}}),
        )
        write_log(
            ap_dir,
            {
                "type": "result",
                "total_cost_usd": 0.01,
                "result": "usage limit reached earlier",
            },
        )

    # The REAL detector, not the harness's always-None stub: a progress path
    # that consulted `self._detect_limit` would parse this prose and sleep.
    lp = make_loop(
        tmp_path,
        [progress_with_prose, terminal_step()],
        detect_limit_fn=usage_limit.detect_from_log,
    )
    write_state(lp._test["ap_dir"], prd="p.md", next_phase="build", batch={"id": "b"})
    assert lp.run() == 0
    assert lp._test["sleeps"] == []


def _warning_event(reset: int) -> dict:
    return {
        "type": "rate_limit_event",
        "rate_limit_info": {
            "status": "allowed_warning",
            "resetsAt": reset,
            "rateLimitType": "five_hour",
            "utilization": 0.95,
            "isUsingOverage": False,
        },
    }


def _progress_with_warning(reset: int, tmp_path: Path, peer: dict | None):
    """A session that advanced state and ended with an allowed_warning. The
    peer registry entry is written INSIDE the session, after this loop's own
    `_register` ran its prune (which would sweep an untagged pid)."""

    def step(ap_dir: Path) -> None:
        if peer is not None:
            (tmp_path / "loops" / "peer.json").write_text(json.dumps(peer))
        (ap_dir / "state.json").write_text(
            json.dumps({"prd": "p.md", "next_phase": "review", "batch": {"id": "b"}}),
        )
        write_log(ap_dir, {"type": "result", "total_cost_usd": 0.01}, _warning_event(reset))

    return step


# pid 1 is alive on every host; started_at far in the past makes it the oldest.
_OLDER_PEER = {"pid": 1, "root": "/elsewhere", "started_at": "2000-01-01T00:00:00Z"}
_YOUNGER_PEER = {"pid": 1, "root": "/elsewhere", "started_at": "2999-01-01T00:00:00Z"}


def _run_with_warning(tmp_path, peer, env=None):
    clock = FakeClock(start=time.time())
    reset = int(clock.now) + 600
    lp = make_loop(
        tmp_path,
        [_progress_with_warning(reset, tmp_path, peer), terminal_step()],
        clock=clock,
        env=env,
    )
    write_state(lp._test["ap_dir"], prd="p.md", next_phase="build", batch={"id": "b"})
    assert lp.run() == 0
    return lp


def test_younger_loop_yields_at_allowed_warning(tmp_path):
    # PRD 00199: two registry entries, this loop the younger -> it sleeps to
    # the warning's reset before its next launch, naming the loop it yields to.
    lp = _run_with_warning(tmp_path, _OLDER_PEER)
    assert any(secs >= 600 for secs in lp._test["sleeps"])
    assert "yielding the window to loop 1 until ~" in lp._test["out"].getvalue()
    assert _notified(lp, "Usage limit")
    assert len(lp._test["spawn"].launches) == 2
    assert (
        metrics_rows(lp._test["ap_dir"])[0]["limit_wait"] >= 600
    )  # the ledger shows it


def test_oldest_loop_never_yields(tmp_path):
    lp = _run_with_warning(tmp_path, _YOUNGER_PEER)
    assert lp._test["sleeps"] == []
    assert "yielding" not in lp._test["out"].getvalue()


def test_a_lone_loop_never_yields(tmp_path):
    lp = _run_with_warning(tmp_path, None)
    assert lp._test["sleeps"] == []


def test_no_yield_kill_switch(tmp_path):
    lp = _run_with_warning(tmp_path, _OLDER_PEER, env={"_AUTOPILOT_NO_YIELD": "1"})
    assert lp._test["sleeps"] == []
    assert "yielding" not in lp._test["out"].getvalue()


def _yield_probe(tmp_path, monkeypatch, *, oldest, env=None):
    """Drive `_yield_at_warning` directly with a live warning on disk and a
    pinned oldest-loop answer, returning (result, decision). Each negative
    branch is asserted on its own early return, not only on a missing
    side effect, so an inverted comparison cannot pass."""
    clock = FakeClock(start=time.time())
    lp = make_loop(tmp_path, [], clock=clock, env=env)
    ap = lp._test["ap_dir"]
    write_log(ap, _warning_event(int(clock.now) + 600))
    monkeypatch.setattr(lp, "_oldest_live_loop_pid", lambda: oldest)
    decision = {"signal": "continue", "detail": "", "limit_wait": None}
    return lp._yield_at_warning(decision, ap / "last-session.log"), decision


def test_yield_at_warning_returns_false_when_this_loop_is_the_oldest(
    tmp_path,
    monkeypatch,
):
    # make_loop's env carries no _AUTOPILOT_LOOP tag, so loop_pid is os.getpid().
    result, decision = _yield_probe(tmp_path, monkeypatch, oldest=os.getpid())
    assert result is False
    assert decision == {"signal": "continue", "detail": "", "limit_wait": None}


def test_yield_at_warning_returns_false_with_no_other_live_loop(tmp_path, monkeypatch):
    result, decision = _yield_probe(tmp_path, monkeypatch, oldest=None)
    assert result is False
    assert decision["limit_wait"] is None


def test_yield_at_warning_kill_switch_short_circuits_before_reading_the_log(
    tmp_path,
    monkeypatch,
):
    from cli import loop_decision

    def must_not_read(path):
        raise AssertionError("the kill switch must return before the log is read")

    monkeypatch.setattr(
        loop_decision.usage_limit, "detect_warning_from_log", must_not_read
    )
    result, decision = _yield_probe(
        tmp_path,
        monkeypatch,
        oldest=1,
        env={"_AUTOPILOT_NO_YIELD": "1"},
    )
    assert result is False
    assert decision["limit_wait"] is None


def test_yield_at_warning_beyond_the_wait_cap_relaunches_and_says_so(
    tmp_path, monkeypatch
):
    # Review 00199: with a lowered cap the younger loop relaunches rather
    # than yielding; the stderr line names it so the ledger's bare continue
    # row is explained.
    result, decision = _yield_probe(
        tmp_path, monkeypatch, oldest=1, env={"_AUTOPILOT_LIMIT_WAIT_MAX": "60"}
    )
    assert result is False
    assert decision["limit_wait"] is None


def test_beyond_cap_warning_line_names_the_loop_it_did_not_yield_to(
    tmp_path, monkeypatch
):
    clock = FakeClock(start=time.time())
    lp = make_loop(tmp_path, [], clock=clock, env={"_AUTOPILOT_LIMIT_WAIT_MAX": "60"})
    ap = lp._test["ap_dir"]
    write_log(ap, _warning_event(int(clock.now) + 600))
    monkeypatch.setattr(lp, "_oldest_live_loop_pid", lambda: 1)
    lp._yield_at_warning({"signal": "continue", "limit_wait": None}, ap / "last-session.log")
    err = lp._test["err"].getvalue()
    assert "beyond _AUTOPILOT_LIMIT_WAIT_MAX; not yielding the window to loop 1" in err


def test_a_wait_the_fingerprint_bound_overrides_never_reaches_the_row(tmp_path):
    # Review 00199: _fingerprint_bound can turn a continue-with-wait into a
    # park; _act_continue then never sleeps, so the park row carries no
    # limit_wait it did not spend.
    clock = FakeClock(start=time.time())
    reset = int(clock.now) + 300

    def same_state_then_operator_pause(ap_dir: Path) -> None:
        _progress_then_rejected(reset)(ap_dir)
        (ap_dir / "pause-requested").touch()  # stops the park relaunch

    lp = make_loop(
        tmp_path,
        [_progress_then_rejected(reset), same_state_then_operator_pause],
        clock=clock,
        env={"_AUTOPILOT_PHASE_REPEATS_MAX": "1"},
    )
    write_state(lp._test["ap_dir"], prd="p.md", next_phase="build", batch={"id": "b"})
    assert lp.run() == 0
    rows = metrics_rows(lp._test["ap_dir"])
    assert [row["signal"] for row in rows] == ["continue", "park"]
    assert rows[0]["limit_wait"] >= 300
    assert "limit_wait" not in rows[1]


def test_yield_at_warning_yields_to_an_older_live_loop(tmp_path, monkeypatch):
    result, decision = _yield_probe(tmp_path, monkeypatch, oldest=1)
    assert result is True
    assert decision["limit_wait"] >= 600
    assert decision["detail"].startswith("yielding the window to loop 1 until ~")


def test_a_registry_entry_without_started_at_is_ignored_loudly_and_never_yields(
    tmp_path,
):
    lp = _run_with_warning(tmp_path, {"pid": 1, "root": "/elsewhere"})
    assert lp._test["sleeps"] == []
    assert "peer.json is unreadable or has no started_at" in lp._test["err"].getvalue()


def test_network_outage_polls_and_resumes(tmp_path):
    def netfail(ap_dir: Path) -> None:
        write_log(
            ap_dir,
            {
                "type": "result",
                "is_error": True,
                "result": "fetch failed: unable to connect to api.anthropic.com",
            },
        )

    lp = make_loop(tmp_path, [netfail, terminal_step()], probe_fn=lambda: True)
    write_state(lp._test["ap_dir"], prd="p.md", next_phase="build", batch={"id": "b"})
    assert lp.run() == 0
    # The poll message lands on stderr during the decision; the act
    # branch then prints the plain continue line (bash parity).
    assert (
        "Polling connectivity, max 60 probes (retry 1/3)" in lp._test["err"].getvalue()
    )
    assert "Backlog drained" in lp._test["out"].getvalue()


def test_network_outage_that_never_clears_dies(tmp_path):
    def netfail(ap_dir: Path) -> None:
        write_log(
            ap_dir,
            {"type": "result", "is_error": True, "result": "ECONNREFUSED"},
        )

    lp = make_loop(
        tmp_path,
        [netfail],
        probe_fn=lambda: False,
        env={"_AUTOPILOT_NET_WAIT_MAX": "60"},
    )
    write_state(lp._test["ap_dir"], prd="p.md", next_phase="build", batch={"id": "b"})
    assert lp.run() == 1
    assert "API unreachable for 2 probes" in lp._test["err"].getvalue()


def test_outage_poll_survives_a_two_hour_clock_jump(tmp_path):
    # PRD 00199: the budget counts probes, not wall-clock. A lid-close sleep
    # between two probes moves the clock two hours; the loop still relaunches
    # on the third probe's success instead of reading the sleep as outage.
    clock = FakeClock()
    probes: list[float] = []

    def probe() -> bool:
        probes.append(clock.now)
        if len(probes) == 2:
            clock.now += 7200  # the machine slept between probes 2 and 3
        return len(probes) >= 3

    lp = make_loop(
        tmp_path,
        [_netfail_step("fetch failed"), terminal_step()],
        clock=clock,
        probe_fn=probe,
    )
    write_state(lp._test["ap_dir"], prd="p.md", next_phase="build", batch={"id": "b"})
    assert lp.run() == 0
    assert len(probes) == 3
    assert "Backlog drained" in lp._test["out"].getvalue()


def test_outage_poll_dies_after_the_probe_budget(tmp_path):
    # net_max 1800 -> 60 probes 30 s apart, then died; never a 61st probe
    # and never a wall-clock comparison.
    probes: list[int] = []

    def probe() -> bool:
        probes.append(1)
        return False

    lp = make_loop(tmp_path, [_netfail_step("ECONNRESET")], probe_fn=probe)
    write_state(lp._test["ap_dir"], prd="p.md", next_phase="build", batch={"id": "b"})
    assert lp.run() == 1
    assert len(probes) == 60
    assert lp._test["sleeps"].count(30) == 59  # between probes, not after the last
    assert "API unreachable for 60 probes" in lp._test["err"].getvalue()


def _netfail_step(text: str):
    def step(ap_dir: Path) -> None:
        write_log(ap_dir, {"type": "result", "is_error": True, "result": text})

    return step


def test_repeated_network_failures_exhaust_the_retry_cap(tmp_path):
    def netfail(ap_dir: Path) -> None:
        write_log(
            ap_dir,
            {"type": "result", "is_error": True, "result": "connection reset"},
        )

    lp = make_loop(tmp_path, [netfail], probe_fn=lambda: True)
    write_state(lp._test["ap_dir"], prd="p.md", next_phase="build", batch={"id": "b"})
    lp._net_retries = 3  # three prior relaunches this loop
    assert lp.run() == 1
    assert "repeated API connection failures (3 relaunches)" in (
        lp._test["err"].getvalue()
    )


def test_fingerprint_bound_parks_a_prd_burning_sessions(tmp_path):
    def same_state(ap_dir: Path) -> None:
        (ap_dir / "state.json").write_text(
            json.dumps(
                {
                    "prd": "p.md",
                    "next_phase": "review",
                    "review_cycles": 2,
                    "batch": {"id": "b"},
                },
            ),
        )
        write_log(ap_dir, {"type": "result", "total_cost_usd": 0.01})

    def same_state_then_operator_pause(ap_dir: Path) -> None:
        same_state(ap_dir)
        (ap_dir / "pause-requested").touch()

    lp = make_loop(
        tmp_path,
        [same_state, same_state, same_state_then_operator_pause],
        env={"_AUTOPILOT_PHASE_REPEATS_MAX": "2"},
    )
    rc = lp.run()  # session 3 parks; iteration 4 consumes the pause
    assert rc == 0
    assert "no progress across 2 sessions; parking p.md" in (lp._test["out"].getvalue())
    assert (lp._test["ap_dir"] / "park-requested").exists()


def test_fingerprint_bound_treats_instant_exit_continue_like_plain_continue(tmp_path):
    # Review finding 3 (PRD 00282): decision["signal"] == "instant_exit"
    # with decision["then"] == "continue" must feed the fingerprint bound
    # exactly like a plain "continue" signal - otherwise a loop stuck
    # relaunching sub-30s, $0 sessions on an unmoving fingerprint never
    # trips the no-progress park.
    lp = make_loop(tmp_path, [], env={"_AUTOPILOT_PHASE_REPEATS_MAX": "2"})
    ap = lp._test["ap_dir"]
    state_path = ap / "state.json"
    write_state(ap, prd="p.md", next_phase="review", review_cycles=2, batch={"id": "b"})

    def row():
        return {
            "signal": "instant_exit",
            "then": "continue",
            "state_touched": True,
            "detail": "session died; retry 1/3",
            "prd": "p.md",
        }

    lp._fingerprint_bound(row(), state_path)
    assert lp._fp_repeats == 0  # first sighting: nothing to compare against yet

    second = row()
    lp._fingerprint_bound(second, state_path)
    assert lp._fp_repeats == 1
    assert second["signal"] == "instant_exit"  # under the cap, unchanged

    third = row()
    lp._fingerprint_bound(third, state_path)
    assert third["signal"] == "park"
    assert "no progress across 2 sessions; parking p.md" in third["detail"]
