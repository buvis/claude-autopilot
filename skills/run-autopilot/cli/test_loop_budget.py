"""Tests for the per-PRD dollar budget of the loop driver.

Contract under test: after each session whose decision would relaunch,
the loop sums `cost_usd` over `loop-metrics.jsonl` rows for `state.prd`
whose `ts_start >= state.prd_budget_since`, adds this session's
`total_cost_usd`, and turns the decision into `park` with
`park_site: "budget"` when the total exceeds `_AUTOPILOT_PRD_BUDGET_USD`
(default 300, `0` disables). `_act_park` then writes `"site": "budget"`
into `park-requested`; a non-budget park keeps the marker without a site.

The sessions are scripted on the shared fake clock. The ones that cross a
PRD boundary run the real Phase 0 (`cli.enter.enter`), so the park marker
the loop writes is consumed by the same code a live session runs, and
`prd_budget_since` is stamped by it on the fake clock.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

import pytest

from cli import enter as enter_mod
from cli import loop_testutil
from cli.loop import Loop
from cli.loop_testutil import (
    _BEFORE_CLOCK,
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

PRD_A = "00010-alpha-v1.md"
PRD_B = "00020-beta-v1.md"
BATCH = "202610130000"
# Prose-only body with design skipped: Phase 0 reads it as the full lane.
PRD_TEXT = "---\ndesign: skip\n---\n\n# Prose only\n\nNo paths here.\n"


def _iso(epoch: float) -> str:
    return datetime.fromtimestamp(epoch, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _epoch(stamp: str) -> float:
    return datetime.strptime(stamp, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc).timestamp()


def _prds(ap_dir: Path) -> Path:
    return ap_dir.parent / "prds"


def _put(ap_dir: Path, folder: str, name: str) -> None:
    path = _prds(ap_dir) / folder / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(PRD_TEXT, encoding="utf-8")


def _has(ap_dir: Path, folder: str, name: str) -> bool:
    return (_prds(ap_dir) / folder / name).exists()


def _open_batch() -> dict:
    return {"id": BATCH, "completed_prds": [], "parks_consecutive": 0}


def _cost_log(ap_dir: Path, cost: float) -> None:
    write_log(
        ap_dir,
        {"type": "result", "total_cost_usd": cost, "usage": {"output_tokens": 10}},
    )


def _work_step(prd: str, cost: float, tasks_completed: int):
    """A healthy build session on `prd`: moves the progress fingerprint,
    queues another build, spends `cost`. prd_budget_since is left as is."""

    def step(ap_dir: Path) -> None:
        state = json.loads((ap_dir / "state.json").read_text())
        state.update(prd=prd, next_phase="build", tasks_completed=tasks_completed)
        (ap_dir / "state.json").write_text(json.dumps(state))
        _cost_log(ap_dir, cost)

    return step


def _entry_step(clock: FakeClock, cost: float, seen: dict, *, prd_arg=None, before=None):
    """A session that runs the real Phase 0 first (park marker consumption,
    selection, prd_budget_since stamp on the fake clock), then does one
    build step's worth of work and spends `cost`."""

    def step(ap_dir: Path) -> None:
        if before is not None:
            before(ap_dir)
        marker = ap_dir / "park-requested"
        seen["marker"] = json.loads(marker.read_text()) if marker.exists() else None
        out = enter_mod.enter(
            ap_dir / "state.json",
            prds_dir=_prds(ap_dir),
            autopilot_dir=ap_dir,
            prd_arg=prd_arg,
            in_loop=True,
            now=lambda: _iso(clock.now),
            git_head=lambda root: None,
            record_resume_row=lambda prd, site, autopilot_dir: None,
        )
        assert out["stop"] is None, out
        seen["enter"] = out
        state = json.loads((ap_dir / "state.json").read_text())
        seen["budget_since"] = state.get("prd_budget_since")
        state.update(next_phase="build", tasks_completed=1)
        (ap_dir / "state.json").write_text(json.dumps(state))
        _cost_log(ap_dir, cost)

    return step


def _capture_decisions(monkeypatch) -> list[dict]:
    """Every decision the loop acts on, as handed to the act branch."""
    seen: list[dict] = []
    original = Loop._act_branch

    def spy(self, decision, ap_dir):
        seen.append(dict(decision))
        return original(self, decision, ap_dir)

    monkeypatch.setattr(Loop, "_act_branch", spy)
    return seen


def _launched_prds(lp) -> list[str]:
    return re.findall(r"· prd (\S+) ·", lp._test["out"].getvalue())


def _loop_enter_fn(clock: FakeClock):
    """A loop enter_fn that runs the real Phase 0 (`cli.enter.enter`) on
    the fake clock, for tests exercising the loop's own pre-launch enter
    (F2) rather than a child session's replay."""

    def enter_fn(state_path, *, prds_dir, autopilot_dir, prd_arg, in_loop):
        return enter_mod.enter(
            state_path,
            prds_dir=prds_dir,
            autopilot_dir=autopilot_dir,
            prd_arg=prd_arg,
            in_loop=in_loop,
            now=lambda: _iso(clock.now),
            git_head=lambda root: None,
            record_resume_row=lambda prd, site, autopilot_dir: None,
        )

    return enter_fn


def _resume_from_hold(clock: FakeClock, prd: str):
    """The operator resumes `prd` after a while: hold/ -> backlog/."""

    def before(ap_dir: Path) -> None:
        clock.now += 600
        (_prds(ap_dir) / "hold" / prd).rename(_prds(ap_dir) / "backlog" / prd)

    return before


def _seed_ab_batch(lp) -> Path:
    """The wip/backlog PRD tree and PRD_A's open-batch, budget-tracked
    state shared by the budget park acceptance tests."""
    ap = lp._test["ap_dir"]
    _put(ap, "wip", PRD_A)
    _put(ap, "backlog", PRD_B)
    write_state(
        ap,
        prd=PRD_A,
        phase="build",
        next_phase="build",
        tasks_completed=0,
        prd_budget_since=_iso(_BEFORE_CLOCK),
        batch=_open_batch(),
    )
    return ap


def _deferred_items(ap_dir: Path) -> list[dict]:
    path = ap_dir / "deferred" / f"{BATCH}-deferred.json"
    return json.loads(path.read_text(encoding="utf-8"))["items"]


# ── acceptance ───────────────────────────────────────────────────────────────


def test_budget_park_lands_prd_in_hold_and_next_prd_launches(tmp_path, monkeypatch):
    # Review finding 4 (PRD 00282): the loop's own pre-launch enter (F2)
    # runs Phase 0 in-process before the launch after the park, so that
    # launch selects B directly - no child session wastes a launch just to
    # run Phase 0 itself, the way a pre-F2 loop would have.
    clock = FakeClock()
    steps = [
        _work_step(PRD_A, 200.0, tasks_completed=1),  # A at $200: under $300
        _work_step(PRD_A, 150.0, tasks_completed=2),  # A at $350: over, park
        terminal_step(prd=PRD_B, batch=BATCH),
    ]
    decisions = _capture_decisions(monkeypatch)
    lp = make_loop(tmp_path, steps, clock=clock, enter_fn=_loop_enter_fn(clock))
    ap = _seed_ab_batch(lp)

    assert lp.run() == 0

    # The crossing session's decision is a budget park with the contract detail.
    assert [d["signal"] for d in decisions] == ["continue", "park", "done"]
    assert decisions[0].get("park_site") != "budget"
    park = decisions[1]
    assert park["park_site"] == "budget"
    assert park["prd"] == PRD_A
    assert park["detail"] == f"budget: $350.00 > $300; parking {PRD_A}"

    # Phase 0 consumed the marker in-process: A sits in hold/ with a budget
    # stall record, and the very next launch is B's, not another on A.
    assert _has(ap, "hold", PRD_A)
    assert not _has(ap, "wip", PRD_A)
    assert not (ap / "park-requested").exists()
    stalls = [i for i in _deferred_items(ap) if i.get("prd") == PRD_A]
    assert len(stalls) == 1
    assert stalls[0]["site"] == "budget"

    rows = metrics_rows(ap)
    assert [(r["prd"], r["signal"]) for r in rows] == [
        (PRD_A, "continue"),
        (PRD_A, "park"),
        (PRD_B, "done"),
    ]
    # The park's very next launch selects B directly: no wasted launch on A.
    assert _launched_prds(lp) == [PRD_A, PRD_A, PRD_B]


def test_budget_resets_after_resume_from_hold(tmp_path, monkeypatch):
    clock = FakeClock()
    park_entry, resume_entry = {}, {}
    steps = [
        _work_step(PRD_A, 310.0, tasks_completed=1),  # A at $310: park
        _entry_step(clock, 5.0, park_entry),  # Phase 0 parks A, selects B
        _entry_step(
            clock, 50.0, resume_entry, prd_arg=PRD_A, before=_resume_from_hold(clock, PRD_A)
        ),
        terminal_step(prd=PRD_A, batch=BATCH),
    ]
    decisions = _capture_decisions(monkeypatch)
    lp = make_loop(tmp_path, steps, clock=clock)
    ap = _seed_ab_batch(lp)

    assert lp.run() == 0

    # First window: $310 parks A.
    assert decisions[0]["signal"] == "park"
    assert decisions[0]["park_site"] == "budget"
    assert decisions[0]["detail"] == f"budget: $310.00 > $300; parking {PRD_A}"
    assert park_entry["enter"]["parked"] == PRD_A

    # Resume: Phase 0 re-entered A and stamped a fresh window after the
    # $310 session started.
    assert resume_entry["enter"]["prd"] == PRD_A
    rows = metrics_rows(ap)
    first_a_row = rows[0]
    assert (first_a_row["prd"], first_a_row["cost_usd"]) == (PRD_A, 310.0)
    assert _epoch(resume_entry["budget_since"]) > first_a_row["ts_start"]

    # The $50 session continues: the old $310 is outside the new window
    # (counted lifetime, A would sit at $360 and park again).
    assert sum(r.get("cost_usd", 0) for r in rows if r["prd"] == PRD_A) > 300
    resumed = decisions[2]
    assert resumed["prd"] == PRD_A
    assert resumed["signal"] == "continue"
    assert resumed.get("park_site") != "budget"
    # row["prd"] is now the PRD the session was *launched* with (PRD 00326),
    # not the decision's PRD: the Phase-0-and-build entry session that parks
    # A and selects B is still launched while state still names A, so its
    # own row credits A, with B showing up only once a later session is
    # itself launched against it.
    assert [(r["prd"], r["signal"]) for r in rows] == [
        (PRD_A, "park"),
        (PRD_A, "continue"),
        (PRD_B, "continue"),
        (PRD_A, "done"),
    ]
    assert not (ap / "park-requested").exists()
    assert _has(ap, "wip", PRD_A)
    assert not _has(ap, "hold", PRD_A)


def test_budget_zero_disables(tmp_path, monkeypatch):
    def seeded_loop(root: Path, env: dict | None):
        steps = [
            _work_step(PRD_A, 1000.0, tasks_completed=1),
            _work_step(PRD_A, 1000.0, tasks_completed=2),
            terminal_step(prd=PRD_A, batch=BATCH),
        ]
        lp = make_loop(root, steps, env=env)
        write_state(
            lp._test["ap_dir"],
            prd=PRD_A,
            phase="build",
            next_phase="build",
            tasks_completed=0,
            prd_budget_since=_iso(_BEFORE_CLOCK),
            batch=_open_batch(),
        )
        return lp

    decisions = _capture_decisions(monkeypatch)
    lp = seeded_loop(tmp_path / "disabled", {"_AUTOPILOT_PRD_BUDGET_USD": "0"})

    assert lp.run() == 0

    ap = lp._test["ap_dir"]
    assert [d["signal"] for d in decisions] == ["continue", "continue", "done"]
    assert all(d.get("park_site") != "budget" for d in decisions)
    assert not (ap / "park-requested").exists()
    assert [r["signal"] for r in metrics_rows(ap)] == ["continue", "continue", "done"]
    assert sum(r.get("cost_usd", 0) for r in metrics_rows(ap)) > 2000

    # Control: the same sessions under the default budget park on the first.
    decisions.clear()
    control = seeded_loop(tmp_path / "control", None)
    assert control.run() == 0
    assert decisions[0]["signal"] == "park"
    assert decisions[0]["park_site"] == "budget"


# ── contract details ─────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("env", "expected"),
    [
        ({}, 300),
        ({"_AUTOPILOT_PRD_BUDGET_USD": "0"}, 0),
        ({"_AUTOPILOT_PRD_BUDGET_USD": "450.5"}, 450.5),
        ({"_AUTOPILOT_PRD_BUDGET_USD": "lots"}, 300),
        ({"_AUTOPILOT_PRD_BUDGET_USD": "nan"}, 300),
        ({"_AUTOPILOT_PRD_BUDGET_USD": "inf"}, 300),
        ({"_AUTOPILOT_PRD_BUDGET_USD": "-50"}, 300),
    ],
    ids=[
        "default", "zero-disables", "float", "unparseable-keeps-default",
        "nan-keeps-default", "inf-keeps-default", "negative-keeps-default",
    ],
)
def test_budget_usd_for_reads_the_env_knob(env, expected):
    from cli.loop_decision import budget_usd_for

    assert budget_usd_for(env) == expected


def test_prd_spend_since_missing_ledger_is_silently_zero(tmp_path, capsys):
    # Review finding 10 (PRD 00282, task 9): no loop-metrics.jsonl yet (a
    # brand-new budget window) is the ordinary case - no warning.
    from cli.loop_decision import prd_spend_since

    assert prd_spend_since(tmp_path / "loop-metrics.jsonl", PRD_A, 0.0) == 0.0
    assert capsys.readouterr().err == ""


def test_prd_spend_since_reports_other_read_failures_on_stderr(tmp_path, capsys):
    # Review finding 10: a ledger that exists but cannot be read (here, a
    # directory where a file is expected) must not silently read as $0 -
    # that previously masked a broken budget check behind an always-false
    # "under budget" result. The failure is reported, not swallowed.
    from cli.loop_decision import prd_spend_since

    broken = tmp_path / "loop-metrics.jsonl"
    broken.mkdir()

    assert prd_spend_since(broken, PRD_A, 0.0) == 0.0
    assert "loop-metrics read failed" in capsys.readouterr().err


def test_prd_spend_since_survives_a_non_utf8_ledger(tmp_path, capsys):
    # Stub 00304 (PRD 00282 cycle 2): the probe catches OSError only, so a
    # ledger holding non-UTF-8 bytes raised UnicodeDecodeError out of
    # _budget_bound into the unattended loop. It must read as 0.0, loud on
    # stderr, never a crash.
    from cli.loop_decision import prd_spend_since

    path = tmp_path / "loop-metrics.jsonl"
    path.write_bytes(b"\xff\xfe{}")

    assert prd_spend_since(path, PRD_A, 0.0) == 0.0
    assert "loop-metrics read failed" in capsys.readouterr().err


def test_prd_spend_since_delegates_row_loading_to_render_metrics_load_rows(tmp_path):
    # Review finding 11 (PRD 00282, task 9): row loading is cli.render_
    # metrics.load_rows, not a parallel reader - so a malformed line and an
    # `event` row (PRD 00094's review_converged rows) are skipped the same
    # way render_metrics itself skips them, while the PRD/timestamp/numeric
    # filters still apply.
    from cli.loop_decision import prd_spend_since

    path = tmp_path / "loop-metrics.jsonl"
    path.write_text(
        "\n".join(
            [
                json.dumps({"prd": PRD_A, "ts_start": 10, "cost_usd": 100.0}),
                "{not json at all",
                json.dumps({"event": "review_converged", "prd": PRD_A, "cost_usd": 999.0}),
                json.dumps({"prd": PRD_B, "ts_start": 10, "cost_usd": 500.0}),
                json.dumps({"prd": PRD_A, "ts_start": 20, "cost_usd": 50.0}),
            ],
        )
        + "\n",
    )

    assert prd_spend_since(path, PRD_A, 0.0) == 150.0


def test_non_budget_park_marker_carries_no_site(tmp_path):
    # A died-ladder park (retry 1/1, then park) keeps today's marker shape,
    # which records._parse_marker reads as wrapper_died.
    lp = make_loop(tmp_path, [noop_step, noop_step, noop_step, noop_step])
    ap = lp._test["ap_dir"]
    write_state(ap, prd=PRD_A, next_phase="build", batch={"id": BATCH})

    lp.run()

    marker = json.loads((ap / "park-requested").read_text())
    assert set(marker) == {"prd", "reason"}
    assert marker["prd"] == PRD_A


# ── _budget_bound, called directly ───────────────────────────────────────────
#
# These skip the session dance: a Loop built by make_loop (never run), a
# hand-seeded state.json, loop-metrics.jsonl and last-session.log, and a
# hand-built decision shaped like the one _decide returns.

_SINCE = _iso(_BEFORE_CLOCK)
_SINCE_EPOCH = int(_BEFORE_CLOCK)


def _bound_loop(tmp_path: Path, env: dict | None = None):
    lp = make_loop(tmp_path, [noop_step], env=env)
    return lp, lp._test["ap_dir"]


def _decision(prd: str, signal: str = "continue", detail: str = "") -> dict:
    """The dict _decide returns after _decide_from_state on a touched state."""
    return {
        "signal": signal,
        "detail": detail,
        "next": "build",
        "phase_end": "build",
        "prd": prd,
        "batch": BATCH,
        "limit_wait": None,
        "lane": None,
        "lane_effective": None,
        "state_touched": True,
    }


def _row(prd: str, ts_start: int, cost, signal: str = "continue") -> dict:
    """A row in the shape Loop._append_metrics writes (_metrics_line)."""
    return {
        "ts_start": ts_start,
        "ts_end": ts_start + 60,
        "wall_secs": 60,
        "prd": prd,
        "batch": BATCH,
        "phase_launched": "build",
        "phase_end": "build",
        "signal": signal,
        "model": "opus",
        "effort": "high",
        "lane": None,
        "lane_effective": None,
        "cost_usd": cost,
    }


def _seed_metrics(ap_dir: Path, *lines) -> None:
    """Write loop-metrics.jsonl verbatim: dicts are JSON-encoded, strings
    are written as-is (for malformed lines)."""
    encoded = [
        line if isinstance(line, str) else json.dumps(line, separators=(",", ":"))
        for line in lines
    ]
    (ap_dir / "loop-metrics.jsonl").write_text("\n".join(encoded) + "\n", encoding="utf-8")


def _seed_state(ap_dir: Path, **fields) -> None:
    write_state(ap_dir, next_phase="build", batch=_open_batch(), **fields)


def test_budget_bound_sums_only_same_prd_rows_inside_the_window(tmp_path):
    lp, ap = _bound_loop(tmp_path)
    _seed_state(ap, prd=PRD_A, prd_budget_since=_SINCE)
    _seed_metrics(
        ap,
        # Before the window: a big same-PRD spend that must not count.
        _row(PRD_A, _SINCE_EPOCH - 1, 500.0),
        # Exactly at the window start: counts (>=, not >).
        _row(PRD_A, _SINCE_EPOCH, 120.25),
        # Another PRD's spend, however large, never counts.
        _row(PRD_B, _SINCE_EPOCH + 10, 9999.0),
        # A died session still spent money: counts.
        _row(PRD_A, _SINCE_EPOCH + 20, 100.5, signal="died"),
        _row(PRD_A, _SINCE_EPOCH + 30, 50.0),
    )
    _cost_log(ap, 40.0)  # this session's own cost
    decision = _decision(PRD_A)

    lp._budget_bound(decision, ap)

    # 120.25 + 100.5 + 50 + 40 = 310.75. Dropping the boundary row (190.5)
    # or the died row (210.25) stays under $300; counting the pre-window
    # row (810.75) or PRD_B (10309.75) names a different total.
    assert decision["signal"] == "park"
    assert decision["park_site"] == "budget"
    assert decision["detail"] == f"budget: $310.75 > $300; parking {PRD_A}"


def test_budget_bound_window_rows_alone_stay_under_budget(tmp_path):
    # Same window as above minus the in-window rows that tip it: the
    # excluded rows (pre-window, other PRD) alone must not park.
    lp, ap = _bound_loop(tmp_path)
    _seed_state(ap, prd=PRD_A, prd_budget_since=_SINCE)
    _seed_metrics(
        ap,
        _row(PRD_A, _SINCE_EPOCH - 1, 500.0),
        _row(PRD_B, _SINCE_EPOCH + 10, 9999.0),
        _row(PRD_A, _SINCE_EPOCH, 120.25),
    )
    _cost_log(ap, 40.0)
    decision = _decision(PRD_A)
    before = dict(decision)

    lp._budget_bound(decision, ap)

    assert decision == before


@pytest.mark.parametrize(
    ("signal", "detail"),
    [
        ("paused", "operator pause"),
        ("done", ""),
        ("died", "session made no progress (state.json untouched)"),
        ("park", f"no progress across 5 sessions; parking {PRD_A}"),
    ],
    ids=["paused", "done", "died", "fingerprint-park"],
)
def test_budget_bound_leaves_non_relaunch_decisions_alone(tmp_path, signal, detail):
    lp, ap = _bound_loop(tmp_path)
    _seed_state(ap, prd=PRD_A, prd_budget_since=_SINCE)
    _seed_metrics(ap, _row(PRD_A, _SINCE_EPOCH + 1, 900.0))
    _cost_log(ap, 900.0)
    decision = _decision(PRD_A, signal=signal, detail=detail)
    before = dict(decision)

    lp._budget_bound(decision, ap)

    assert decision.get("park_site") != "budget"
    assert decision == before


def test_budget_bound_sleeps_out_a_scheduled_limit_wait_then_parks(tmp_path):
    # Review finding 3 (PRD 00282, task 9): a continue decision carrying
    # limit_wait is not exempt from the budget bound - exempting it let a
    # PRD run up unlimited spend for as long as it kept hitting usage
    # limits. The scheduled sleep still runs first (a relaunch into the
    # still-live limit would halt on an unconsumed park marker), then the
    # decision becomes a budget park.
    lp, ap = _bound_loop(tmp_path)
    _seed_state(ap, prd=PRD_A, prd_budget_since=_SINCE)
    _seed_metrics(ap, _row(PRD_A, _SINCE_EPOCH + 1, 900.0))
    _cost_log(ap, 900.0)
    decision = _decision(PRD_A)
    decision["limit_wait"] = 600

    lp._budget_bound(decision, ap)

    assert lp._test["sleeps"] == [600]
    assert decision["signal"] == "park"
    assert decision["park_site"] == "budget"
    assert decision["detail"] == f"budget: $1800.00 > $300; parking {PRD_A}"


def test_budget_park_prints_the_wait_line_before_sleeping(tmp_path):
    # Review packet 13: _budget_bound sleeps out a scheduled limit_wait
    # itself, before turning the decision into a park, so the usage-limit
    # line and notification _act_continue would otherwise print must
    # appear here too - and before the sleep, not after.
    lp, ap = _bound_loop(tmp_path)
    _seed_state(ap, prd=PRD_A, prd_budget_since=_SINCE)
    _seed_metrics(ap, _row(PRD_A, _SINCE_EPOCH + 1, 900.0))
    _cost_log(ap, 900.0)
    decision = _decision(PRD_A)
    decision["limit_wait"] = 600
    snapshot = {}
    real_sleep = lp._sleep

    def spy_sleep(secs):
        snapshot["out"] = lp._test["out"].getvalue()
        snapshot["notified"] = _notified(lp, "Usage limit")
        return real_sleep(secs)

    lp._sleep = spy_sleep

    lp._budget_bound(decision, ap)

    assert "usage limit hit; waiting 10 min" in snapshot["out"]
    assert snapshot["notified"] is True


def test_budget_bound_reads_through_an_instant_exit_signal_to_then(tmp_path):
    # Review finding 4 (PRD 00282, task 9): _budget_bound must not skip an
    # instant_exit decision whose `then` is "continue" - that signal masked
    # every budget-exceeding session short enough (or free enough) to be
    # presented as instant_exit.
    lp, ap = _bound_loop(tmp_path)
    _seed_state(ap, prd=PRD_A, prd_budget_since=_SINCE)
    _seed_metrics(ap, _row(PRD_A, _SINCE_EPOCH + 1, 900.0))
    _cost_log(ap, 900.0)
    decision = _decision(PRD_A, signal="instant_exit")
    decision["then"] = "continue"

    lp._budget_bound(decision, ap)

    assert decision["signal"] == "park"
    assert decision["park_site"] == "budget"
    assert decision["detail"] == f"budget: $1800.00 > $300; parking {PRD_A}"


def test_budget_bound_total_equal_to_budget_does_not_park(tmp_path):
    lp, ap = _bound_loop(tmp_path)
    _seed_state(ap, prd=PRD_A, prd_budget_since=_SINCE)
    _seed_metrics(ap, _row(PRD_A, _SINCE_EPOCH + 1, 150.0))
    _cost_log(ap, 150.0)
    decision = _decision(PRD_A)
    before = dict(decision)

    lp._budget_bound(decision, ap)

    assert decision == before  # $300.00 is not > $300

    # Control: one cent over parks.
    _cost_log(ap, 150.01)
    over = _decision(PRD_A)
    lp._budget_bound(over, ap)
    assert over["signal"] == "park"
    assert over["park_site"] == "budget"
    assert over["detail"] == f"budget: $300.01 > $300; parking {PRD_A}"


def test_budget_bound_skips_malformed_and_partial_metrics_rows(tmp_path):
    lp, ap = _bound_loop(tmp_path)
    _seed_state(ap, prd=PRD_A, prd_budget_since=_SINCE)
    no_cost = _row(PRD_A, _SINCE_EPOCH + 2, None)
    del no_cost["cost_usd"]
    no_ts = _row(PRD_A, _SINCE_EPOCH + 4, 1000.0)
    del no_ts["ts_start"]
    _seed_metrics(
        ap,
        _row(PRD_A, _SINCE_EPOCH + 1, 140.0),
        no_cost,
        _row(PRD_A, _SINCE_EPOCH + 3, None),  # cost_usd: null
        "{not json at all",
        no_ts,
        "",
        _row(PRD_A, _SINCE_EPOCH + 5, 140.0),
    )
    _cost_log(ap, 10.0)
    decision = _decision(PRD_A)
    before = dict(decision)

    lp._budget_bound(decision, ap)  # must not raise

    # 140 + 140 + 10 = 290: the no-ts_start $1000 row is not counted.
    assert decision == before

    # The valid rows around the junk still count: +$30 this session parks
    # at exactly 140 + 140 + 30.
    _cost_log(ap, 30.0)
    over = _decision(PRD_A)
    lp._budget_bound(over, ap)
    assert over["signal"] == "park"
    assert over["park_site"] == "budget"
    assert over["detail"] == f"budget: $310.00 > $300; parking {PRD_A}"


def test_budget_bound_honours_a_custom_budget(tmp_path):
    lp, ap = _bound_loop(tmp_path, env={"_AUTOPILOT_PRD_BUDGET_USD": "450.5"})
    _seed_state(ap, prd=PRD_A, prd_budget_since=_SINCE)

    # $400: over the $300 default, under the custom $450.5.
    _seed_metrics(ap, _row(PRD_A, _SINCE_EPOCH + 1, 300.0))
    _cost_log(ap, 100.0)
    under = _decision(PRD_A)
    before = dict(under)
    lp._budget_bound(under, ap)
    assert under == before

    # $460: over the custom budget.
    _seed_metrics(ap, _row(PRD_A, _SINCE_EPOCH + 1, 360.0))
    over = _decision(PRD_A)
    lp._budget_bound(over, ap)
    assert over["signal"] == "park"
    assert over["park_site"] == "budget"
    assert over["detail"] == f"budget: $460.00 > $450.5; parking {PRD_A}"


def test_budget_bound_invalid_budget_since_falls_back_to_epoch_zero(tmp_path):
    # Review finding 9 (PRD 00282, task 9): a present but unparseable
    # prd_budget_since must not disable the budget check the way an
    # absent one does - it falls back to epoch zero, counting every row
    # for the PRD, same as a never-reset budget window.
    lp, ap = _bound_loop(tmp_path)
    _seed_state(ap, prd=PRD_A, prd_budget_since="not-a-timestamp")
    _seed_metrics(ap, _row(PRD_A, 0, 150.0))
    _cost_log(ap, 150.01)
    decision = _decision(PRD_A)

    lp._budget_bound(decision, ap)

    assert decision["signal"] == "park"
    assert decision["park_site"] == "budget"
    assert decision["detail"] == f"budget: $300.01 > $300; parking {PRD_A}"


@pytest.mark.parametrize(
    ("state_fields", "decision_prd"),
    [
        ({"prd_budget_since": _SINCE}, ""),
        ({"prd": PRD_A}, PRD_A),
    ],
    ids=["no-prd", "no-budget-since"],
)
def test_budget_bound_needs_both_prd_and_budget_since(tmp_path, state_fields, decision_prd):
    lp, ap = _bound_loop(tmp_path)
    _seed_state(ap, **state_fields)
    _seed_metrics(
        ap,
        _row(PRD_A, _SINCE_EPOCH + 1, 5000.0),
        # An empty-prd row must not match an empty decision prd.
        _row("", _SINCE_EPOCH + 2, 5000.0),
    )
    _cost_log(ap, 5000.0)
    decision = _decision(decision_prd)
    before = dict(decision)

    lp._budget_bound(decision, ap)

    assert decision.get("park_site") != "budget"
    assert decision == before
