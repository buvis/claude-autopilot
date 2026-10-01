"""Tests for the wrapper's own store recording (PRD 00236): the loop records
the store after each metrics append (site "loop"), and the drained exit
records it once more after the state-final archive (site "drained"). The
harness (fake clock, scripted spawn, make_loop) is cli/loop_testutil.py.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from cli import loop_act
from cli import loop_testutil
from cli import store_tree
from cli.loop import Loop
from cli.loop_testutil import make_loop, terminal_step, write_log, write_state

# The autouse fixture registers by being a module attribute.
_no_real_drain_side_effects = loop_testutil._no_real_drain_side_effects


def _record_store_into(monkeypatch, events: list, calls: list, probe=None):
    def fake(repo, site, prd, run_git=store_tree.run_git):
        events.append(("store", site, prd))
        calls.append(
            {"repo": repo, "site": site, "prd": prd, "run_git": run_git,
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


# ── site "loop": once per iteration, between metrics and act ────────────────


def test_each_iteration_records_the_store_after_metrics_and_before_acting(
    tmp_path, monkeypatch,
):
    events, calls = [], []
    _record_store_into(monkeypatch, events, calls)
    _trace_metrics_and_act(monkeypatch, events)
    lp = make_loop(tmp_path, [_review_step("p.md"), terminal_step(batch="b-1")])
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
        ("metrics", second_prd),
        ("store", "loop", second_prd),
        ("act",),
        ("store", "drained", calls[-1]["prd"]),
    ]


def test_loop_site_records_the_projects_repo_with_a_git_runner_bound_to_it(
    tmp_path, monkeypatch,
):
    events, calls = [], []
    _record_store_into(monkeypatch, events, calls)
    lp = make_loop(tmp_path, [terminal_step()])
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


def test_loop_site_runner_uses_the_bare_git_dir_recorded_in_state(
    tmp_path, monkeypatch,
):
    events, calls = [], []
    _record_store_into(monkeypatch, events, calls)
    lp = make_loop(tmp_path, [])
    git_dir = tmp_path / "bare.git"
    subprocess.run(["git", "init", "-q", "--bare", str(git_dir)], check=True)

    def bare_terminal(ap_dir: Path) -> None:
        terminal_step()(ap_dir)
        state = json.loads((ap_dir / "state.json").read_text())
        state.update(repo_root=str(lp.cwd), git_dir=str(git_dir))
        (ap_dir / "state.json").write_text(json.dumps(state))

    lp._test["spawn"].steps.append(bare_terminal)
    write_state(lp._test["ap_dir"], prd="p.md", next_phase="build", batch={"id": "b-1"})
    assert lp.run() == 0

    call = next(c for c in calls if c["site"] == "loop")
    assert Path(call["repo"]).resolve() == lp.cwd.resolve()
    seen = call["run_git"](["rev-parse", "--git-dir"], lp.cwd)
    assert Path(seen.stdout.strip()).resolve() == git_dir.resolve()


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
    write_state(ap, prd="p.md", next_phase="build", batch={"id": "b-7"})
    assert lp.run() == 0

    drained = [c for c in calls if c["site"] == "drained"]
    assert len(drained) == 1
    assert drained[0]["probe"] == (True, False)  # archived, live state gone
    assert Path(drained[0]["repo"]).resolve() == lp.cwd.resolve()
    assert callable(drained[0]["run_git"])
    # Nothing touches the store after the drained record: it is the last event.
    assert events[-1][:2] == ("store", "drained")
    assert events.index(("agoge",)) < len(events) - 1
    assert events.index(("purge",)) < len(events) - 1
    assert "Backlog drained." in lp._test["out"].getvalue()
