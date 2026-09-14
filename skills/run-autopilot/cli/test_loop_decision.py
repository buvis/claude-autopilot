"""Tests for cli/loop_decision.py (PRD 00192 seam 2): the pure ports and
the decision table of the loop driver, moved out of test_loop.py with the
code they cover. The harness (fake clock, scripted spawn, make_loop) is
cli/loop_testutil.py.
"""

from __future__ import annotations

import json
from pathlib import Path

from cli.loop_decision import (
    died_next,
    fingerprint,
    last_result_field,
    pause_detail,
    plugin_drift,
)
from cli import loop_testutil
from cli.loop_testutil import (
    FakeClock,
    _notified,
    make_loop,
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


# ── decision table ───────────────────────────────────────────────────────────


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
    assert _notified(lp, "Parking 00044-x-v1.md.")
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
    assert "Polling connectivity, max 1800s (retry 1/3)" in lp._test["err"].getvalue()
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
    assert "API unreachable for 60s" in lp._test["err"].getvalue()


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
        write_log(ap_dir, {"type": "result"})

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
    assert len(lp._test["spawn"].launches) == 3
