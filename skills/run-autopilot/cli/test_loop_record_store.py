"""Tests for the wrapper's own store recording (PRD 00236): the loop records
the store after the metrics append of a session that made progress (site
"loop"), and the drained exit records it once more after the state-final
archive (site "drained"). Inside a wave lane neither record fires. The
harness (fake clock, scripted spawn, make_loop) is cli/loop_testutil.py.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from cli import loop_act
from cli import loop_testutil
from cli import store_tree
from cli.loop import Loop
from cli.loop_testutil import (
    make_loop,
    noop_step,
    terminal_step,
    write_log,
    write_state,
)

# The autouse fixture registers by being a module attribute.
_no_real_drain_side_effects = loop_testutil._no_real_drain_side_effects


def _record_store_into(monkeypatch, events: list, calls: list, probe=None):
    def fake(repo, site, prd, store_dir=None, run_git=store_tree.run_git):
        events.append(("store", site, prd))
        calls.append(
            {"repo": repo, "site": site, "prd": prd, "run_git": run_git,
             "store_dir": store_dir,
             "probe": probe() if probe else None},
        )
        return None  # nothing committed: the wrapper must carry on regardless

    monkeypatch.setattr(store_tree, "record_store", fake)


def _trace_metrics_and_act(monkeypatch, events: list) -> None:
    orig_metrics, orig_act = Loop._append_metrics, Loop._act_branch

    def metrics(self, *args, **kwargs):
        decision = args[3] if len(args) > 3 else kwargs["decision"]
        events.append(("metrics", decision.get("prd", "")))
        return orig_metrics(self, *args, **kwargs)

    def act(self, *args, **kwargs):
        events.append(("act",))
        return orig_act(self, *args, **kwargs)

    monkeypatch.setattr(Loop, "_append_metrics", metrics)
    monkeypatch.setattr(Loop, "_act_branch", act)


def _review_step(prd: str):
    def step(ap_dir: Path) -> None:
        (ap_dir / "state.json").write_text(
            json.dumps({"prd": prd, "next_phase": "review", "batch": {"id": "b-1"}}),
        )
        write_log(ap_dir, {"type": "result"})

    return step


def _git_init(repo: Path) -> None:
    subprocess.run(["git", "init", "-q", str(repo)], check=True)


def _bare_terminal(lp, git_dir: Path, batch: str = "b-1"):
    """A drained session whose state names a bare git dir for the repo."""
    subprocess.run(["git", "init", "-q", "--bare", str(git_dir)], check=True)

    def step(ap_dir: Path) -> None:
        terminal_step(batch=batch)(ap_dir)
        state = json.loads((ap_dir / "state.json").read_text())
        state.update(repo_root=str(lp.cwd), git_dir=str(git_dir))
        (ap_dir / "state.json").write_text(json.dumps(state))

    return step


def _bare_review(lp, git_dir: Path, prd: str = "p.md"):
    """A session that made progress, whose state names a bare git dir."""
    subprocess.run(["git", "init", "-q", "--bare", str(git_dir)], check=True)

    def step(ap_dir: Path) -> None:
        _review_step(prd)(ap_dir)
        state = json.loads((ap_dir / "state.json").read_text())
        state.update(repo_root=str(lp.cwd), git_dir=str(git_dir))
        (ap_dir / "state.json").write_text(json.dumps(state))

    return step


def _lane_env(tmp_path: Path) -> dict:
    """The two variables `autopilot wave launch` sets on every lane loop."""
    return {
        "_AUTOPILOT_REVIEW_SLOTS_DIR": str(tmp_path / "wave-slots"),
        "_AUTOPILOT_REVIEW_SLOTS": "1",
    }


def _assert_runner_bound_to_bare_repo(run_git, lp, git_dir: Path, tmp_path) -> None:
    seen = run_git(["rev-parse", "--git-dir"], lp.cwd)
    assert Path(seen.stdout.strip()).resolve() == git_dir.resolve()
    # A bare git dir needs the work tree set, or add/commit cannot work.
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir(exist_ok=True)
    top = run_git(["rev-parse", "--show-toplevel"], elsewhere)
    assert Path(top.stdout.strip()).resolve() == lp.cwd.resolve()


# ── site "loop": once per iteration, between metrics and act ────────────────


def test_each_iteration_records_the_store_after_metrics_and_before_acting(
    tmp_path, monkeypatch,
):
    events, calls = [], []
    _record_store_into(monkeypatch, events, calls)
    _trace_metrics_and_act(monkeypatch, events)
    lp = make_loop(
        tmp_path, [_review_step("p.md"), terminal_step(prd="q.md", batch="b-1")],
    )
    write_state(lp._test["ap_dir"], prd="p.md", next_phase="build", batch={"id": "b-1"})

    # record_store returned None both times; the loop still drained normally.
    assert lp.run() == 0
    assert len(lp._test["spawn"].launches) == 2

    first_prd, second_prd = (e[1] for e in events if e[0] == "metrics")
    assert first_prd == "p.md"
    assert events == [
        ("metrics", first_prd),
        ("store", "loop", first_prd),
        ("act",),
        # The second session drained the batch: no per-iteration record.
        ("metrics", second_prd),
        ("act",),
        # The drained record carries the PRD the final state named.
        ("store", "drained", "q.md"),
    ]


def test_loop_site_records_the_projects_repo_with_a_git_runner_bound_to_it(
    tmp_path, monkeypatch,
):
    events, calls = [], []
    _record_store_into(monkeypatch, events, calls)
    # The first session made progress, so it is the one that records.
    lp = make_loop(tmp_path, [_review_step("p.md"), terminal_step()])
    _git_init(lp.cwd)
    write_state(lp._test["ap_dir"], prd="p.md", next_phase="build", batch={"id": "b-1"})
    assert lp.run() == 0

    loop_calls = [c for c in calls if c["site"] == "loop"]
    assert len(loop_calls) == 1
    call = loop_calls[0]
    assert Path(call["repo"]).resolve() == lp.cwd.resolve()
    # The runner targets the project repo even when invoked from elsewhere.
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    top = call["run_git"](["rev-parse", "--show-toplevel"], elsewhere)
    assert Path(top.stdout.strip()).resolve() == lp.cwd.resolve()
    # A failed git call must raise, never pass as a quiet nonzero result.
    with pytest.raises(subprocess.CalledProcessError):
        call["run_git"](["rev-parse", "--verify", "nonexistent-ref"], lp.cwd)


def test_loop_site_runner_uses_the_bare_git_dir_recorded_in_state(
    tmp_path, monkeypatch,
):
    events, calls = [], []
    _record_store_into(monkeypatch, events, calls)
    lp = make_loop(tmp_path, [])
    git_dir = tmp_path / "bare.git"
    # A session that made progress, then one that drains the batch.
    lp._test["spawn"].steps.append(_bare_review(lp, git_dir))
    lp._test["spawn"].steps.append(terminal_step())
    write_state(lp._test["ap_dir"], prd="p.md", next_phase="build", batch={"id": "b-1"})
    assert lp.run() == 0

    call = next(c for c in calls if c["site"] == "loop")
    assert Path(call["repo"]).resolve() == lp.cwd.resolve()
    _assert_runner_bound_to_bare_repo(call["run_git"], lp, git_dir, tmp_path)


# ── site "drained": once, after the archive, purge and agoge ────────────────


def test_drained_exit_records_the_store_once_after_archive_and_agoge(
    tmp_path, monkeypatch,
):
    events, calls = [], []
    lp = make_loop(tmp_path, [terminal_step(batch="b-7")])
    ap = lp._test["ap_dir"]
    archived = ap / "reports" / "b-7-state-final.json"
    _record_store_into(
        monkeypatch, events, calls,
        probe=lambda: (archived.is_file(), (ap / "state.json").exists()),
    )
    monkeypatch.setattr(loop_act, "run_purge", lambda repo: events.append(("purge",)))
    monkeypatch.setattr(
        loop_act,
        "run_agoge",
        lambda ap_dir, batch, drained, env, out, claude_bin="claude": events.append(
            ("agoge",),
        ),
    )
    _git_init(lp.cwd)
    write_state(ap, prd="p.md", next_phase="build", batch={"id": "b-7"})
    assert lp.run() == 0

    drained = [c for c in calls if c["site"] == "drained"]
    assert len(drained) == 1
    assert drained[0]["probe"] == (True, False)  # archived, live state gone
    assert Path(drained[0]["repo"]).resolve() == lp.cwd.resolve()
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    top = drained[0]["run_git"](["rev-parse", "--show-toplevel"], elsewhere)
    assert Path(top.stdout.strip()).resolve() == lp.cwd.resolve()
    # Nothing touches the store after the drained record: it is the last event.
    assert events[-1][:2] == ("store", "drained")
    assert events.index(("agoge",)) < len(events) - 1
    assert events.index(("purge",)) < len(events) - 1
    assert "Backlog drained." in lp._test["out"].getvalue()


def test_drained_site_runner_uses_the_bare_git_dir_from_state_before_archive(
    tmp_path, monkeypatch,
):
    # The live state.json is archived before the drained record, so the
    # repo and git dir must come from the state as it stood before that.
    events, calls = [], []
    _record_store_into(monkeypatch, events, calls)
    lp = make_loop(tmp_path, [])
    git_dir = tmp_path / "bare.git"
    lp._test["spawn"].steps.append(_bare_terminal(lp, git_dir, batch="b-7"))
    write_state(lp._test["ap_dir"], prd="p.md", next_phase="build", batch={"id": "b-7"})
    assert lp.run() == 0

    drained = [c for c in calls if c["site"] == "drained"]
    assert len(drained) == 1
    assert Path(drained[0]["repo"]).resolve() == lp.cwd.resolve()
    _assert_runner_bound_to_bare_repo(drained[0]["run_git"], lp, git_dir, tmp_path)


def test_operator_pause_exit_records_no_drained_store(tmp_path, monkeypatch):
    # A stand-down also exits 0, but the batch is not drained and the
    # session made no progress: neither record may fire.
    events, calls = [], []
    _record_store_into(monkeypatch, events, calls)

    def stand_down(ap_dir: Path) -> None:
        (ap_dir / "pause-requested").write_text(json.dumps({"reason": "peer owns it"}))

    lp = make_loop(tmp_path, [stand_down])
    ap = lp._test["ap_dir"]
    write_state(ap, prd="p.md", next_phase="build", batch={"id": "b-1"})
    assert lp.run() == 0
    assert (ap / "paused-by-operator").is_file()
    assert "stood down" in lp._test["out"].getvalue()

    assert [c["site"] for c in calls] == []


# ── the gate: a session that made progress, outside a wave lane ────────────


def test_a_session_that_died_records_no_store(tmp_path, monkeypatch):
    monkeypatch.delenv("_AUTOPILOT_REVIEW_SLOTS_DIR", raising=False)
    events, calls = [], []
    _record_store_into(monkeypatch, events, calls)
    # The first session touches nothing (it died and is retried); the
    # second drains the batch.
    lp = make_loop(tmp_path, [noop_step, terminal_step(prd="q.md")])
    write_state(lp._test["ap_dir"], prd="p.md", next_phase="build", batch={"id": "b-1"})
    assert lp.run() == 0
    assert len(lp._test["spawn"].launches) == 2

    assert [c["site"] for c in calls] == ["drained"]


def test_a_paused_session_records_no_store(tmp_path, monkeypatch):
    monkeypatch.delenv("_AUTOPILOT_REVIEW_SLOTS_DIR", raising=False)
    events, calls = [], []
    _record_store_into(monkeypatch, events, calls)

    def pausing(ap_dir: Path) -> None:
        (ap_dir / "state.json").write_text(
            json.dumps(
                {
                    "prd": "p.md",
                    "phase": "paused",
                    "next_phase": "paused",
                    "pause_reason": {"detail": "design gate needs the operator"},
                    "batch": {"id": "b-1"},
                },
            ),
        )
        write_log(ap_dir, {"type": "result"})

    lp = make_loop(tmp_path, [pausing])
    write_state(lp._test["ap_dir"], prd="p.md", next_phase="build", batch={"id": "b-1"})
    assert lp.run() == 1

    assert calls == []


def test_a_wave_lane_records_no_store_for_a_session_that_made_progress(
    tmp_path, monkeypatch,
):
    events, calls = [], []
    _record_store_into(monkeypatch, events, calls)
    lp = make_loop(
        tmp_path,
        [_review_step("p.md"), terminal_step(prd="q.md", batch="b-1")],
        env=_lane_env(tmp_path),
    )
    write_state(lp._test["ap_dir"], prd="p.md", next_phase="build", batch={"id": "b-1"})
    assert lp.run() == 0
    assert len(lp._test["spawn"].launches) == 2

    assert calls == [], "a lane branch takes no store commit, at any site"


def test_a_wave_lane_drained_exit_archives_but_records_no_store(tmp_path, monkeypatch):
    events, calls = [], []
    _record_store_into(monkeypatch, events, calls)
    lp = make_loop(tmp_path, [terminal_step(batch="b-7")], env=_lane_env(tmp_path))
    ap = lp._test["ap_dir"]
    write_state(ap, prd="p.md", next_phase="build", batch={"id": "b-7"})
    assert lp.run() == 0

    assert calls == []
    # Only the record is skipped: the drained exit itself ran to the end.
    assert (ap / "reports" / "b-7-state-final.json").is_file()
    assert not (ap / "state.json").exists()
    assert "Backlog drained." in lp._test["out"].getvalue()
