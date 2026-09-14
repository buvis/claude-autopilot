"""The cli.loop compat surface (PRD 00192): every name loop.py defined before
the split is still importable from cli.loop and is the same object its seam
module defines. Lives apart from test_loop.py on purpose: that module's autouse
drain stubs replace loop_act.run_agoge / run_purge for every test there and
would mask the identity checks below."""

from __future__ import annotations

from cli import loop, loop_act, loop_decision, loop_gates

_EXPECTED_ALL = {
    "DEFAULT_LOOPS_DIR",
    "Loop",
    "PURGE_SCRIPT",
    "died_next",
    "fingerprint",
    "last_result_field",
    "live_wrapper_pid",
    "main",
    "pause_detail",
    "plugin_drift",
    "prune_registry",
    "run_agoge",
    "run_purge",
}


def test_public_names_remain_importable_from_loop():
    assert set(loop.__all__) == _EXPECTED_ALL
    for name in loop.__all__:
        assert getattr(loop, name) is not None
    assert loop.died_next is loop_decision.died_next
    assert loop.fingerprint is loop_decision.fingerprint
    assert loop.last_result_field is loop_decision.last_result_field
    assert loop.pause_detail is loop_decision.pause_detail
    assert loop.plugin_drift is loop_decision.plugin_drift
    assert loop.live_wrapper_pid is loop_gates.live_wrapper_pid
    assert loop.prune_registry is loop_gates.prune_registry
    assert loop.DEFAULT_LOOPS_DIR is loop_gates.DEFAULT_LOOPS_DIR
    assert loop.run_agoge is loop_act.run_agoge
    assert loop.run_purge is loop_act.run_purge
    assert loop.PURGE_SCRIPT is loop_act.PURGE_SCRIPT
    assert loop_act.run_agoge.__module__ == "cli.loop_act"
    assert loop_act.run_purge.__module__ == "cli.loop_act"
    assert loop.Loop.__bases__ == (
        loop_gates.GatesMixin,
        loop_decision.DecisionMixin,
        loop_act.ActMixin,
    )
