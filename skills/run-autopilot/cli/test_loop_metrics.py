"""Tests for cli/loop.py's metrics row (PRD 00106), split out of
test_loop.py to stay under its 800-line cap (rules/coding-style.md).

Covers the `killed_by` field: it rides the session row from
`SpawnResult.cap_reason` (itself sourced from `Watchdog.fired_reason`,
PRD task 2) only when the watchdog actually fired.
"""

from __future__ import annotations

from cli.loop_testutil import make_loop, metrics_rows, write_state
from cli.runner import SpawnResult


def _spawn_fn(cap_fired: bool, cap_reason: str | None):
    def spawn_fn(
        model,
        effort,
        *,
        cap_secs,
        autopilot_dir,
        env,
        runner_bin,
        proc_slot=None,
        **kwargs,
    ):
        return SpawnResult(
            0,
            autopilot_dir / "last-session.log",
            cap_fired,
            cap_reason=cap_reason,
        )

    return spawn_fn


def test_row_carries_killed_by_only_when_the_cap_fired(tmp_path):
    # A session the watchdog never touched must carry no `killed_by`
    # key at all (not a null), so a reader can tell "unknown" from
    # "not capped".
    lp = make_loop(tmp_path, [], spawn_fn=_spawn_fn(True, "idle"))
    write_state(lp._test["ap_dir"], prd="p.md", next_phase="review", batch={"id": "b"})
    lp.run_once()
    (capped_row,) = metrics_rows(lp._test["ap_dir"])
    assert capped_row["killed_by"] == "idle"

    lp2 = make_loop(tmp_path / "other", [], spawn_fn=_spawn_fn(False, None))
    write_state(lp2._test["ap_dir"], prd="p.md", next_phase="review", batch={"id": "b"})
    lp2.run_once()
    (clean_row,) = metrics_rows(lp2._test["ap_dir"])
    assert "killed_by" not in clean_row
