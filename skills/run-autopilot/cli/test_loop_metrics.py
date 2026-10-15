"""Tests for cli/loop.py's metrics row (PRD 00106), split out of
test_loop.py to stay under its 800-line cap (rules/coding-style.md).

Covers the `killed_by` field: it rides the session row from
`SpawnResult.cap_reason` (itself sourced from `Watchdog.fired_reason`,
PRD task 2) only when the watchdog actually fired.
"""

from __future__ import annotations

from cli import render_metrics
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


def _row_for_decision(tmp_path, monkeypatch, **overrides) -> dict:
    # Drives the scripted loop through one session; the loop exposes no
    # decision seam, so the instance's `_decide` is pinned to the decision
    # under test and the emitted metrics row is what gets asserted on.
    lp = make_loop(tmp_path, [], spawn_fn=_spawn_fn(False, None))
    write_state(lp._test["ap_dir"], prd="p.md", next_phase="review", batch={"id": "b"})
    decision = {
        "signal": "continue",
        "detail": "",
        "next": "review",
        "phase_end": "review",
        "prd": "p.md",
        "batch": {"id": "b"},
        "limit_wait": None,
        "lane": None,
        "lane_effective": None,
        "state_touched": True,
        **overrides,
    }
    monkeypatch.setattr(lp, "_decide", lambda ap_dir, ts_start: decision)
    lp.run_once()
    (row,) = metrics_rows(lp._test["ap_dir"])
    return row


def test_instant_exit_limit_row_carries_limit_wait(tmp_path, monkeypatch):
    # Packet 23: an instant_exit row whose `then` is "continue" (the
    # died-retry ladder, a usage-limit wait, a scheduling yield) carried
    # no limit_wait - the effective signal must decide, not the presented one.
    row = _row_for_decision(
        tmp_path,
        monkeypatch,
        signal="instant_exit",
        then="continue",
        limit_wait=180,
    )

    assert row["limit_wait"] == 180


def test_budget_park_row_carries_limit_wait(tmp_path, monkeypatch):
    # Packet 23: a budget park reached through a scheduled wait carried
    # no limit_wait either.
    row = _row_for_decision(
        tmp_path,
        monkeypatch,
        signal="park",
        park_site="budget",
        limit_wait=180,
    )

    assert row["limit_wait"] == 180


def test_park_row_at_a_non_budget_site_carries_no_limit_wait_key(tmp_path, monkeypatch):
    # Absent, not null: only the budget park site records the slept seconds.
    row = _row_for_decision(
        tmp_path,
        monkeypatch,
        signal="park",
        park_site="review",
        limit_wait=180,
    )

    assert "limit_wait" not in row


def test_failed_loop_entry_invalidation_prints_a_line_to_stderr(tmp_path):
    # A failed clear leaves a replayable stale entry; the operator must be
    # told on stderr. A successful clear stays silent.
    lp = make_loop(tmp_path, [])
    ap = lp._test["ap_dir"]
    err = lp._test["err"]
    write_state(ap, prd="p.md", next_phase="build", loop_entry={"prd": "p.md"})

    assert lp._invalidate_loop_entry(ap / "state.json") is True
    assert err.getvalue() == ""

    assert lp._invalidate_loop_entry(ap / "missing" / "state.json") is False
    assert "loop_entry" in err.getvalue()


def test_prd_table_says_it_excludes_the_finalizing_session():
    # Packet 24: the per-PRD table is written inside the finalizing
    # session, whose own row lands after it - the caption must say so.
    out = render_metrics.render_metrics(
        [{"prd": "00001-a.md", "wall_secs": 10, "cost_usd": 1.0}],
    )
    caption = (
        "Cost USD excludes the finalizing session, which is recorded "
        "after this report is written."
    )

    assert caption in out
    assert out.index(caption) < out.index("| PRD |")
