"""Tests for cli/loop_gates.py (PRD 00192 seam 3): the loop registry and
the preflight gates of the loop driver, moved out of test_loop.py with the
code they cover. The harness (fake clock, scripted spawn, make_loop) is
cli/loop_testutil.py.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from cli import __main__ as cli_main
from cli import enter as enter_mod
from cli import enter_io, loop_gates, loop_testutil, schema, state, statectl
from cli.loop_testutil import (
    _notified,
    make_loop,
    terminal_step,
    write_state,
)

# The autouse fixture registers by being a module attribute.
_no_real_drain_side_effects = loop_testutil._no_real_drain_side_effects


def test_child_pids_passes_dash_a_on_darwin(monkeypatch):
    # macOS pgrep leaves out the caller's own ancestors unless -a is given;
    # on Linux -a means something else, so it must be added only on darwin.
    calls = []

    def fake_run(cmd, **kwargs):
        calls.append(cmd)
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)

    monkeypatch.setattr(sys, "platform", "darwin")
    loop_gates._child_pids(123)
    assert "-a" in calls[-1]

    monkeypatch.setattr(sys, "platform", "linux")
    loop_gates._child_pids(123)
    assert "-a" not in calls[-1]


# ── preflights ───────────────────────────────────────────────────────────────


def test_pause_marker_stops_before_any_spawn(tmp_path):
    lp = make_loop(tmp_path, [])
    ap = lp._test["ap_dir"]
    (ap / "pause-requested").touch()
    assert lp.run() == 0
    assert not (ap / "pause-requested").exists()
    assert lp._test["spawn"].launches == []
    assert _notified(lp, "Paused by operator")


def test_pause_exit_stamps_the_stop_for_the_observer(tmp_path):
    # The exit appends no metrics row, so the stamp is the only trace that
    # tells tracon this was a deliberate stop and not a dropped batch.
    lp = make_loop(tmp_path, [])
    ap = lp._test["ap_dir"]
    (ap / "pause-requested").touch()
    assert lp.run() == 0
    assert (ap / "paused-by-operator").is_file()


def test_pause_exit_names_autoclaude_as_the_resume(tmp_path):
    # An operator pause consumes its marker and blocks on nothing, so
    # autoclaude alone resumes. Only the _act_paused exit (a paused STATE
    # the loop would re-read) makes the interactive step mandatory.
    lp = make_loop(tmp_path, [])
    (lp._test["ap_dir"] / "pause-requested").touch()
    assert lp.run() == 0
    out = lp._test["out"].getvalue()
    assert "Resume unattended: autoclaude" in out
    assert "/autopilot:run-autopilot" in out  # the take-over path, namespaced


def test_a_resumed_loop_clears_the_pause_stamp(tmp_path):
    lp = make_loop(tmp_path, [terminal_step()])
    ap = lp._test["ap_dir"]
    (ap / "paused-by-operator").touch()
    assert lp.run() == 0
    assert not (ap / "paused-by-operator").exists()


def test_plugin_drift_halts_before_any_spawn(tmp_path):
    plugins = tmp_path / "installed_plugins.json"
    plugins.write_text(
        json.dumps({"plugins": {"aegis@buvis-plugins": [{"version": "9.9.9"}]}}),
    )
    lp = make_loop(
        tmp_path,
        [],
        env={"_AUTOPILOT_PLUGINS_JSON": str(plugins)},
    )
    write_state(
        lp._test["ap_dir"],
        prd="p.md",
        next_phase="build",
        batch={"id": "b", "plugin_versions": {"aegis@buvis-plugins": "0.3.1"}},
    )
    assert lp.run() == 1
    assert "plugin version drift" in lp._test["err"].getvalue()
    assert lp._test["spawn"].launches == []
    assert _notified(lp, "Plugin drift")


def test_matching_plugin_pins_proceed(tmp_path):
    plugins = tmp_path / "installed_plugins.json"
    plugins.write_text(
        json.dumps({"plugins": {"aegis@buvis-plugins": [{"version": "0.3.1"}]}}),
    )
    lp = make_loop(
        tmp_path,
        [terminal_step()],
        env={"_AUTOPILOT_PLUGINS_JSON": str(plugins)},
    )
    write_state(
        lp._test["ap_dir"],
        prd="p.md",
        next_phase="build",
        batch={"id": "b", "plugin_versions": {"aegis@buvis-plugins": "0.3.1"}},
    )
    assert lp.run() == 0


def test_memory_pressure_that_never_clears_halts(tmp_path):
    lp = make_loop(
        tmp_path,
        [],
        pressure_fn=lambda: 4,
        env={"_AUTOPILOT_MEM_WAIT_MAX": "120", "_AUTOPILOT_MEM_POLL_SECS": "60"},
    )
    assert lp.run() == 1
    assert "memory pressure still elevated" in lp._test["err"].getvalue()
    assert lp._test["spawn"].launches == []
    assert _notified(lp, "memory pressure")


def test_memory_pressure_that_clears_resumes(tmp_path):
    readings = [4, 1, 1]
    lp = make_loop(
        tmp_path,
        [terminal_step()],
        pressure_fn=lambda: readings.pop(0) if readings else 1,
        env={"_AUTOPILOT_MEM_WAIT_MAX": "600"},
    )
    assert lp.run() == 0
    assert "memory pressure cleared" in lp._test["err"].getvalue()


def test_future_schema_state_refuses_before_spawn(tmp_path):
    lp = make_loop(tmp_path, [])
    write_state(
        lp._test["ap_dir"],
        prd="p.md",
        next_phase="build",
        schema_version=99,
        batch={"id": "b"},
    )
    assert lp.run() == 1
    assert "newer than this CLI understands" in lp._test["err"].getvalue()
    assert lp._test["spawn"].launches == []


def test_unstamped_state_warns_and_proceeds(tmp_path):
    lp = make_loop(tmp_path, [terminal_step()])
    write_state(lp._test["ap_dir"], prd="p.md", next_phase="build", batch={"id": "b"})
    assert lp.run() == 0
    assert "schema status 'unstamped'" in lp._test["err"].getvalue()


# ── registry ─────────────────────────────────────────────────────────────────
# Moved to test_loop_gates_registry.py (style-limit split).


# ── pre-launch enter (PRD 00282 F2): Loop._pre_enter + the enter replay ──────

_PRD = "00010-alpha-v1.md"
_OTHER = "00020-beta-v1.md"
# Prose-only body with design skipped: Phase 0 reads it as the full lane.
_PRD_TEXT = "---\ndesign: skip\n---\n\n# Prose only\n\nNo paths here.\n"


def _build_tree(ap: Path, **overrides) -> None:
    """A wip PRD and an open batch whose next session is a build."""
    wip = ap.parent / "prds" / "wip"
    wip.mkdir(parents=True, exist_ok=True)
    (wip / _PRD).write_text(_PRD_TEXT, encoding="utf-8")
    fields = {
        "prd": _PRD,
        "phase": "build",
        "next_phase": "build",
        "batch": {"id": "b-1", "completed_prds": [], "parks_consecutive": 0},
    }
    fields.update(overrides)
    write_state(ap, **fields)


def _read_state(ap: Path) -> dict:
    return json.loads((ap / "state.json").read_text(encoding="utf-8"))


def _count_resume_rows(monkeypatch) -> list:
    """Every handoff row the real enter() writes. enter() binds
    record_resume_row as a keyword default at import time, so patching the
    enter_io attribute alone would miss its calls: patch both, and keep git
    out of the tmp tree the same way."""
    rows: list = []

    def record(prd, site, autopilot_dir):
        rows.append((prd, site))

    monkeypatch.setattr(enter_io, "record_resume_row", record)
    monkeypatch.setitem(enter_mod.enter.__kwdefaults__, "record_resume_row", record)
    monkeypatch.setitem(enter_mod.enter.__kwdefaults__, "git_head", lambda root: None)
    monkeypatch.delenv("_AUTOPILOT_LANES", raising=False)
    monkeypatch.delenv("_AUTOPILOT_LOOP", raising=False)
    return rows


def _entered(*args, **kwargs) -> dict:
    return {
        "stop": None,
        "detail": "",
        "prd": _PRD,
        "catchup": "full",
        "design": "skip",
        "warnings": ["frontmatter: lane reset"],
    }


def _raise_state_error(*args, **kwargs) -> dict:
    raise state.StateError("state file is not valid JSON")


def _pre_enter_lines(lp) -> list[str]:
    return [
        line
        for line in lp._test["err"].getvalue().splitlines()
        if "pre-launch enter" in line
    ]


def test_loop_entry_then_skill_entry_writes_one_resume_row(
    tmp_path, monkeypatch, capsys
):
    rows = _count_resume_rows(monkeypatch)
    lp = make_loop(tmp_path, [], enter_fn=enter_mod.enter)
    ap = lp._test["ap_dir"]
    _build_tree(ap)

    lp._pre_enter(ap)

    entry = _read_state(ap)["loop_entry"]
    assert entry["entered_by"] == "loop"
    assert entry["prd"] == _PRD
    assert "warnings" not in entry["result"]
    brief = (ap / "session-brief.md").read_text(encoding="utf-8")
    assert f"## Entry\n- prd: {_PRD}\n" in brief

    # The session's own `autopilot enter` replays the loop's line.
    assert cli_main.main(["enter", "--state", str(ap / "state.json")]) == 0
    assert json.loads(capsys.readouterr().out) == entry["result"]
    assert "loop_entry" not in _read_state(ap)
    assert rows == [(_PRD, "build")]


def test_stale_loop_entry_is_dropped(tmp_path, monkeypatch, capsys):
    rows = _count_resume_rows(monkeypatch)
    ap = tmp_path / "docs" / "dev" / "project-management" / "autopilot"
    ap.mkdir(parents=True)
    stale = {
        "stop": None,
        "detail": "",
        "prd": _OTHER,
        "catchup": "delta",
        "design": "reuse",
    }
    _build_tree(ap, loop_entry={"entered_by": "loop", "prd": _OTHER, "result": stale})

    assert cli_main.main(["enter", "--state", str(ap / "state.json")]) == 0

    printed = json.loads(capsys.readouterr().out)
    assert printed["prd"] == _PRD
    assert printed["catchup"] == "full"
    assert "loop_entry" not in _read_state(ap)
    assert rows == [(_PRD, "build")]


def test_manual_prd_arg_skips_the_replay_even_with_a_matching_entry(
    tmp_path,
    monkeypatch,
    capsys,
):
    # Review finding 6 (PRD 00282, task 9): a manual `autopilot enter --prd
    # X` must run enter() for real even when a loop_entry for the CURRENT
    # prd waits to be replayed - args.prd is not None is the explicit-
    # selection signal that overrides the loop's own pre-run, matching
    # _replay_loop_entry's `prd_arg is not None` gate.
    rows = _count_resume_rows(monkeypatch)
    ap = tmp_path / "docs" / "dev" / "project-management" / "autopilot"
    ap.mkdir(parents=True)
    matching = {
        "stop": None,
        "detail": "",
        "prd": _PRD,
        "catchup": "full",
        "design": "skip",
    }
    _build_tree(ap, loop_entry={"entered_by": "loop", "prd": _PRD, "result": matching})

    assert (
        cli_main.main(["enter", "--state", str(ap / "state.json"), "--prd", _PRD]) == 0
    )

    printed = json.loads(capsys.readouterr().out)
    assert printed["prd"] == _PRD
    assert "loop_entry" not in _read_state(ap)
    # enter() ran for real (not the replayed line): it recorded its own
    # resume row, which a pure replay never does.
    assert rows == [(_PRD, "build")]


def test_loop_entry_delete_failure_halts_enter(tmp_path, monkeypatch, capsys):
    # Review finding 6: a failed loop_entry delete (statectl.mutate
    # raising) must surface as exit 2, not fall through to enter() over an
    # entry it could not clear.
    ap = tmp_path / "docs" / "dev" / "project-management" / "autopilot"
    ap.mkdir(parents=True)
    stale = {
        "stop": None,
        "detail": "",
        "prd": _PRD,
        "catchup": "delta",
        "design": "reuse",
    }
    _build_tree(ap, loop_entry={"entered_by": "loop", "prd": _PRD, "result": stale})

    def refuse(path, apply):
        raise OSError("disk full")

    monkeypatch.setattr(statectl, "mutate", refuse)

    assert cli_main.main(["enter", "--state", str(ap / "state.json")]) == 2
    assert "enter failed: loop_entry delete: disk full" in capsys.readouterr().err


def test_pre_enter_utime_failure_is_reported(tmp_path, monkeypatch):
    # Review finding 6: the loop_entry write succeeding but the post-write
    # backdate (os.utime) failing for a reason other than a vanished file
    # (FileNotFoundError, already handled) must surface on stderr instead
    # of disappearing - a touched-but-unbackdated state.json would dodge
    # the no-progress ladder on a session that dies at once.
    lp = make_loop(tmp_path, [], enter_fn=_entered)
    ap = lp._test["ap_dir"]
    _build_tree(ap)
    real_utime = os.utime

    def fail_utime(path, times):
        if Path(path) == ap / "state.json":
            raise PermissionError("utime denied")
        real_utime(path, times)

    monkeypatch.setattr(os, "utime", fail_utime)

    lp._pre_enter(ap)

    assert "loop_entry" in _read_state(ap)
    assert _pre_enter_lines(lp) == [
        "autoclaude: pre-launch enter: state.json backdate failed: utime denied",
    ]


def test_pre_enter_failure_launches_without_entry(tmp_path):
    seen: dict = {}

    def step(ap_dir: Path) -> None:
        seen["state"] = _read_state(ap_dir)
        terminal_step()(ap_dir)

    lp = make_loop(tmp_path, [step], enter_fn=_raise_state_error)
    ap = lp._test["ap_dir"]
    _build_tree(ap)

    assert lp.run() == 0

    assert len(lp._test["spawn"].launches) == 1
    assert "loop_entry" not in seen["state"]
    assert _pre_enter_lines(lp) == [
        "autoclaude: pre-launch enter failed: state file is not valid JSON",
    ]


@pytest.mark.parametrize(
    "raiser",
    [
        lambda *a, **k: (_ for _ in ()).throw(state.StateExistsError("exists")),
        lambda *a, **k: (_ for _ in ()).throw(OSError("disk full")),
        lambda *a, **k: (_ for _ in ()).throw(schema.SchemaError("bad schema")),
    ],
    ids=["state_exists_error", "os_error", "schema_error"],
)
def test_pre_enter_never_halts_the_loop_on_a_wider_enter_failure(tmp_path, raiser):
    # Review finding 7/8 (PRD 00282): the CLI's own enter gate also catches
    # StateExistsError, and an OSError or SchemaError out of enter() (a
    # permission error reading state.json, a corrupt schema write) must not
    # crash the unattended loop either - spec intent is "never halts the
    # loop".
    lp = make_loop(tmp_path, [], enter_fn=raiser)
    ap = lp._test["ap_dir"]
    _build_tree(ap)

    lp._pre_enter(ap)  # must not raise

    assert "loop_entry" not in _read_state(ap)


def test_pre_enter_failure_invalidates_a_stale_same_prd_entry(tmp_path):
    # Review finding 2 (PRD 00282, task 10): an earlier session's loop_entry
    # for this same PRD must not survive a pre-entry failure, or a later
    # child replays its stale catchup/design/stop result instead of running
    # enter() for real.
    stale = {
        "stop": None,
        "detail": "",
        "prd": _PRD,
        "catchup": "delta",
        "design": "reuse",
    }
    lp = make_loop(tmp_path, [], enter_fn=_raise_state_error)
    ap = lp._test["ap_dir"]
    _build_tree(ap, loop_entry={"entered_by": "loop", "prd": _PRD, "result": stale})

    lp._pre_enter(ap)

    assert "loop_entry" not in _read_state(ap)


def test_pre_enter_write_failure_invalidates_a_stale_same_prd_entry(
    tmp_path,
    monkeypatch,
):
    # Same as above, for the statectl.mutate write-failure branch: a real
    # enter() succeeds but the new loop_entry cannot be written, so the
    # earlier same-PRD entry must still be invalidated, not left to replay.
    stale = {
        "stop": None,
        "detail": "",
        "prd": _PRD,
        "catchup": "delta",
        "design": "reuse",
    }
    lp = make_loop(tmp_path, [], enter_fn=_entered)
    ap = lp._test["ap_dir"]
    _build_tree(ap, loop_entry={"entered_by": "loop", "prd": _PRD, "result": stale})

    real_mutate = statectl.mutate
    calls = {"n": 0}

    def flaky(path, apply):
        calls["n"] += 1
        if calls["n"] == 1:
            raise OSError("disk full")
        return real_mutate(path, apply)

    monkeypatch.setattr(statectl, "mutate", flaky)

    lp._pre_enter(ap)

    assert "loop_entry" not in _read_state(ap)


def test_pre_enter_state_write_failure_leaves_no_entry(tmp_path, monkeypatch):
    def refuse(path, apply):
        raise OSError("disk full")

    lp = make_loop(tmp_path, [], enter_fn=_entered)
    ap = lp._test["ap_dir"]
    _build_tree(ap)
    monkeypatch.setattr(statectl, "mutate", refuse)

    lp._pre_enter(ap)

    assert "loop_entry" not in _read_state(ap)
    assert not (ap / "session-brief.md").exists()
    assert _pre_enter_lines(lp) == [
        "autoclaude: pre-launch enter: loop_entry write failed: disk full",
    ]
    # enter's warnings still reach the loop's stderr, never its stdout.
    assert "frontmatter: lane reset" in lp._test["err"].getvalue()
    assert "frontmatter: lane reset" not in lp._test["out"].getvalue()


@pytest.mark.parametrize(
    ("next_phase", "marker", "called"),
    [
        ("build", False, True),
        ("review", True, True),
        ("review", False, False),
        ("done", False, False),
    ],
)
def test_pre_enter_runs_only_for_a_build_or_a_park_marker(
    tmp_path,
    next_phase,
    marker,
    called,
):
    calls: list = []

    def enter_fn(*args, **kwargs):
        calls.append((args, kwargs))
        return _entered()

    lp = make_loop(tmp_path, [], enter_fn=enter_fn)
    ap = lp._test["ap_dir"]
    write_state(ap, prd=_PRD, next_phase=next_phase)
    if marker:
        (ap / "park-requested").write_text(json.dumps({"prd": _PRD, "reason": "died"}))

    lp._pre_enter(ap)

    expected = (
        (ap / "state.json",),
        {
            "prds_dir": ap.parent / "prds",
            "autopilot_dir": ap,
            "prd_arg": None,
            "in_loop": True,
        },
    )
    assert calls == ([expected] if called else [])


def test_pre_enter_write_is_not_session_progress(tmp_path):
    # The loop's own loop_entry write must not read as the session touching
    # state.json, or a session that dies at once would dodge the
    # no-progress ladder and relaunch forever.
    lp = make_loop(tmp_path, [], enter_fn=_entered)
    ap = lp._test["ap_dir"]
    _build_tree(ap)

    lp._pre_enter(ap)

    assert "loop_entry" in _read_state(ap)
    assert lp._decide(ap, lp._test["clock"]())["state_touched"] is False
