"""Tests for cli/loop_decision.py (PRD 00192 seam 2): the pure ports and
the instant-exit acceptance tests of the loop driver, moved out of
test_loop.py with the code they cover. The harness (fake clock, scripted
spawn, make_loop) is cli/loop_testutil.py.

The decision table's own tests (state write failure, pause/review-cap,
died retry ladder, usage-limit wait and window yield, network outage, the
fingerprint bound) moved to test_loop_decision_table.py (PRD 00282, review
finding 7: this file crossed the 800-line limit). `_rejected_event` stays
here - test_loop_decision_table.py imports it back - since the instant-
exit usage-limit test below needs it too.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import pytest

from cli import loop_testutil, usage_limit
from cli.loop_decision import (
    died_next,
    fingerprint,
    last_result_field,
    pause_detail,
    plugin_drift,
)
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

# The autouse fixture registers by being a module attribute.
_no_real_drain_side_effects = loop_testutil._no_real_drain_side_effects


# ── pure ports ───────────────────────────────────────────────────────────────


def test_died_next_bootstrap_halts_loud():
    assert died_next("", 0, 1) == "die"


def test_died_next_retries_until_budget_then_parks():
    assert died_next("00001-x.md", 0, 1) == "retry"
    assert died_next("00001-x.md", 1, 1) == "park"


def test_pause_detail_prefers_the_reason_detail():
    assert pause_detail({"pause_reason": {"detail": "need a human"}}) == "need a human"


def test_pause_detail_string_reason_passes_through():
    assert pause_detail({"pause_reason": "blocked on credentials"}) == (
        "blocked on credentials"
    )


def test_pause_detail_summarizes_the_review_cap():
    state = {
        "phase": "paused",
        "cap_pause_reason": {
            "cycle": 3,
            "cap": 3,
            "unresolved_findings": [{"issue": "a"}, {"issue": "b"}],
        },
    }
    assert pause_detail(state) == "review cap hit: cycle 3/3 · 2 unresolved findings"


def test_pause_detail_paused_phase_alone_says_paused():
    assert pause_detail({"phase": "paused"}) == "paused"


def test_pause_detail_empty_when_not_paused():
    assert pause_detail({"phase": "review", "pause_reason": None}) == ""


def test_fingerprint_binds_the_progress_fields():
    state = {
        "prd": "p.md",
        "next_phase": "review",
        "tasks_completed": 3,
        "review_cycles": 1,
        "cycle": 2,
        "cap_rotations": [{}],
        "replan_count": 0,
    }
    assert fingerprint(state) == "p.md|review|3|1|2|1|0"


def test_fingerprint_defaults_missing_fields_like_jq():
    assert fingerprint({}) == "null|null|-1|-1|-1|0|-1"


def test_plugin_drift_names_the_rotated_plugin():
    state = {"batch": {"plugin_versions": {"aegis@buvis-plugins": "0.3.1"}}}
    installed = {"plugins": {"aegis@buvis-plugins": [{"version": "0.4.0"}]}}
    assert plugin_drift(state, installed) == (
        "aegis@buvis-plugins pinned=0.3.1 now=0.4.0"
    )


def test_plugin_drift_missing_install_reads_missing():
    state = {"batch": {"plugin_versions": {"warden@buvis-plugins": "0.13.0"}}}
    assert plugin_drift(state, {"plugins": {}}) == (
        "warden@buvis-plugins pinned=0.13.0 now=MISSING"
    )


def test_plugin_drift_unpinned_batch_never_blocks():
    assert plugin_drift({"batch": {}}, {"plugins": {}}) is None
    assert plugin_drift({}, {}) is None


def test_plugin_drift_matching_pins_pass():
    state = {"batch": {"plugin_versions": {"a": "1.0"}}}
    installed = {"plugins": {"a": [{"version": "1.0"}]}}
    assert plugin_drift(state, installed) is None


def test_last_result_field_takes_the_final_event(tmp_path):
    log = tmp_path / "log"
    log.write_text(
        json.dumps({"type": "result", "total_cost_usd": 1.0})
        + "\n"
        + "not json\n"
        + json.dumps({"type": "result", "total_cost_usd": 2.5})
        + "\n",
    )
    assert last_result_field(log, "total_cost_usd") == 2.5


def test_last_result_field_error_only_filters(tmp_path):
    log = tmp_path / "log"
    log.write_text(
        json.dumps({"type": "result", "result": "fine"})
        + "\n"
        + json.dumps({"type": "result", "is_error": True, "result": "ECONNREFUSED"})
        + "\n",
    )
    assert last_result_field(log, "result", error_only=True) == "ECONNREFUSED"


def _rejected_event(reset: int, overage: str = "allowed") -> dict:
    return {
        "type": "rate_limit_event",
        "rate_limit_info": {
            "status": "rejected",
            "resetsAt": reset,
            "rateLimitType": "five_hour",
            "overageStatus": overage,
            "isUsingOverage": True,
        },
    }


# ── instant exit ─────────────────────────────────────────────────────────────


_ZERO = {"type": "result", "total_cost_usd": 0}
_BUILD = {"prd": "p.md", "next_phase": "build", "batch": {"id": "b"}}
_DONE = {"prd": "00099-drained-v1.md", "next_phase": "", "batch": {"id": "b-1"}}
_PAUSED = {**_BUILD, "next_phase": "review", "pause_reason": {"detail": "gate"}}
_RETRY = "instant exit (session died; retry 1/1); then continue."


def _quick_session(clock: FakeClock, secs: float, *events, log=True, state=None):
    """Runs `secs` past ScriptedSpawn's own 1 s; writes `state`, then `events` if `log`."""

    def step(ap_dir: Path) -> None:
        clock.now += secs
        if state is not None:
            (ap_dir / "state.json").write_text(json.dumps(state))
        if log:
            write_log(ap_dir, *events)

    return step


def test_instant_exit_signal_then_died_retry_without_limit(tmp_path):
    # Two 3 s sessions ($0, then no cost) on an untouched state; 3-4 trip the park guard.
    clock = FakeClock()
    zero = _quick_session(clock, 2, _ZERO)
    absent = _quick_session(clock, 2, {"type": "result"})
    lp = make_loop(tmp_path, [zero, absent, noop_step, noop_step], clock=clock)
    ap = lp._test["ap_dir"]
    write_state(ap, prd="00044-x-v1.md", next_phase="build", batch={"id": "b"})
    assert lp.run() == 1
    out = lp._test["out"].getvalue()
    second = "instant exit (died after 1 retries; parking 00044-x-v1.md); then park."
    cont = out.index("Continuing (next phase: build)")
    assert out.index(_RETRY) < cont < out.index(second)
    assert "parking 00044-x-v1.md (died after 1 retries" in out
    assert json.loads((ap / "park-requested").read_text())["prd"] == "00044-x-v1.md"
    assert lp._died_retries == 1
    rows = metrics_rows(ap)[:2]
    assert [row["signal"] for row in rows] == ["instant_exit"] * 2
    # Review finding 5 (PRD 00282): `then` is pinned too, not just `signal` -
    # the retry row continues, the row that exhausts the ladder parks.
    assert [row["then"] for row in rows] == ["continue", "park"]


def test_instant_exit_waits_when_usage_limit_detected(tmp_path):
    clock = FakeClock(start=time.time())  # the live-limit staleness check reads it
    hit = _quick_session(clock, 2, _ZERO, _rejected_event(int(clock.now) + 600))
    detect = usage_limit.detect_from_log
    lp = make_loop(
        tmp_path, [hit, terminal_step()], clock=clock, detect_limit_fn=detect
    )
    write_state(lp._test["ap_dir"], **_BUILD)
    assert lp.run() == 0
    out = lp._test["out"].getvalue()
    assert "instant exit (usage-limit; resuming ~" in out and "); then continue." in out
    assert "usage limit hit; waiting" in out
    assert any(secs >= 500 for secs in lp._test["sleeps"])
    assert _notified(lp, "Usage limit")
    row = metrics_rows(lp._test["ap_dir"])[0]
    assert row["signal"] == "instant_exit"
    assert row["then"] == "continue"  # review finding 5, PRD 00282
    assert len(lp._test["spawn"].launches) == 2


def test_instant_exit_with_touched_state_still_runs_the_died_ladder(tmp_path):
    # Review finding 1 (PRD 00282, task 9): the instant-exit check must run
    # before the state_touched counter reset, so a sub-30s, $0 session that
    # nonetheless rewrote state.json does not reset _died_retries either -
    # the died ladder (retry once, then park) still decides, exactly as it
    # does for an untouched state.
    clock = FakeClock()
    touched = _quick_session(clock, 2, _ZERO, state=_BUILD)
    lp = make_loop(tmp_path, [touched, touched, noop_step, noop_step], clock=clock)
    ap = lp._test["ap_dir"]
    write_state(ap, **_BUILD)
    assert lp.run() == 1
    out = lp._test["out"].getvalue()
    second = "instant exit (died after 1 retries; parking p.md); then park."
    assert _RETRY in out
    assert second in out
    assert json.loads((ap / "park-requested").read_text())["prd"] == "p.md"
    assert lp._died_retries == 1
    rows = metrics_rows(ap)[:2]
    assert [row["signal"] for row in rows] == ["instant_exit"] * 2
    assert [row["then"] for row in rows] == ["continue", "park"]  # finding 5, PRD 00282


@pytest.mark.parametrize(
    ("session", "want"),  # (secs, costs | None=no log, state), (rc, signal, runs)
    [
        pytest.param((29, (0,), None), (0, "continue", 2), id="wall_exactly_30s"),
        pytest.param((2, (0.01,), None), (0, "continue", 2), id="billed_cent"),
        pytest.param((2, (0.5,), None), (0, "continue", 2), id="billed_half"),
        pytest.param((2, (5.0,), None), (0, "continue", 2), id="billed_5"),
        pytest.param((2, (0, 0.5), None), (0, "continue", 2), id="last_billed"),
        pytest.param((28, (0,), None), (0, "instant_exit", 2), id="wall_29s"),
        pytest.param((2, (), None), (0, "instant_exit", 2), id="log_without_result"),
        pytest.param((2, None, None), (0, "instant_exit", 2), id="no_log"),
        pytest.param((2, (0,), _DONE), (0, "done", 1), id="done"),
        pytest.param((2, (0,), _PAUSED), (1, "paused", 1), id="paused"),
    ],
)
def test_instant_exit_flags_only_sub_30s_unbilled_sessions(tmp_path, session, want):
    (secs, costs, state), (rc, signal, runs) = session, want
    expect_instant = signal == "instant_exit"
    clock = FakeClock()
    events = [{"type": "result", "total_cost_usd": cost} for cost in costs or ()]
    quick = _quick_session(clock, secs, *events, log=costs is not None, state=state)
    lp = make_loop(tmp_path, [quick, terminal_step()], clock=clock)
    write_state(lp._test["ap_dir"], **_BUILD)
    assert lp.run() == rc
    out = lp._test["out"].getvalue()
    assert ("instant exit" in out) is expect_instant
    assert (_RETRY in out) is expect_instant
    row = metrics_rows(lp._test["ap_dir"])[0]
    assert row["signal"] == signal
    # Review finding 5 (PRD 00282): `then` is pinned too, not just `signal`.
    assert ("then" in row) is expect_instant
    if expect_instant:
        assert row["then"] == "continue"
    assert len(lp._test["spawn"].launches) == runs


@pytest.mark.parametrize(
    ("reset_in", "err_fragment"),
    [(50_000, "beyond _AUTOPILOT_LIMIT_WAIT_MAX"), (None, "no state.json")],
    ids=["limit_beyond_cap", "bootstrap_no_state"],
)
def test_instant_exit_still_halts_a_died_session(tmp_path, reset_in, err_fragment):
    clock = FakeClock()
    reset = reset_in and int(clock.now) + reset_in
    quick = _quick_session(clock, 2, _ZERO)
    lp = make_loop(tmp_path, [quick], clock=clock, detect_limit_fn=lambda path: reset)
    if reset_in:
        write_state(lp._test["ap_dir"], **_BUILD)
    assert lp.run() == 1
    assert "); then died." in lp._test["out"].getvalue()
    assert err_fragment in lp._test["err"].getvalue()
    assert len(lp._test["spawn"].launches) == 1
