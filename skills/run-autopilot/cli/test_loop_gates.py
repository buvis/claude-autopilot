"""Tests for cli/loop_gates.py (PRD 00192 seam 3): the loop registry and
the preflight gates of the loop driver, moved out of test_loop.py with the
code they cover. The harness (fake clock, scripted spawn, make_loop) is
cli/loop_testutil.py.
"""

from __future__ import annotations

import json
import os
import re
import signal
import subprocess
import sys
import time
from pathlib import Path

import pytest

from cli import __main__ as cli_main
from cli import enter as enter_mod
from cli import enter_io, loop_gates, state, statectl
from cli.loop_gates import live_wrapper_pid, prune_registry
from cli import loop_testutil
from cli.loop_testutil import (
    _notified,
    _spawn_tagged_incumbent,
    make_loop,
    terminal_step,
    write_state,
)

# The autouse fixture registers by being a module attribute.
_no_real_drain_side_effects = loop_testutil._no_real_drain_side_effects


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


def test_duplicate_loop_guard_refuses_a_second_loop(tmp_path):
    loops = tmp_path / "loops"
    loops.mkdir()
    lp = make_loop(tmp_path, [])
    root = tmp_path / "repo"
    incumbent = _spawn_tagged_incumbent()
    try:
        (loops / f"{incumbent.pid}.json").write_text(
            json.dumps({"pid": incumbent.pid, "root": str(root)}),
        )
        assert lp.run() == 1
        assert "already running" in lp._test["err"].getvalue()
        assert lp._test["spawn"].launches == []
    finally:
        incumbent.kill()
        incumbent.wait()


def test_registry_entry_written_and_removed_at_teardown(tmp_path):
    lp = make_loop(tmp_path, [terminal_step()])
    write_state(lp._test["ap_dir"], prd="p.md", next_phase="build", batch={"id": "b"})
    assert lp.run() == 0
    assert list((tmp_path / "loops").glob("*.json")) == []


def test_registry_entry_carries_the_tracon_contract_shape(tmp_path):
    # tracon.discovery parses these entries: pid int, root/ap_dir absolute
    # strings (root = ap_dir minus /docs/dev/project-management/autopilot), started_at ISO.
    lp = make_loop(tmp_path, [])
    ap_dir = lp._resolve_ap_dir()
    assert lp._register(ap_dir) is None
    entries = list((tmp_path / "loops").glob("*.json"))
    assert len(entries) == 1
    entry = json.loads(entries[0].read_text())
    assert entry["pid"] == lp.loop_pid
    assert entry["ap_dir"] == str(ap_dir)
    assert Path(entry["root"]).is_absolute()
    assert str(ap_dir) == entry["root"] + "/docs/dev/project-management/autopilot"
    assert entries[0].name == f"{lp.loop_pid}.json"
    assert re.match(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$", entry["started_at"])


def test_own_stale_registry_entry_is_overwritten_not_refused(tmp_path):
    # A SIGKILLed python driver leaves an entry naming this shell's own
    # (still-alive) pid; the relaunch from the same shell must overwrite
    # it rather than refuse against itself.
    loops = tmp_path / "loops"
    loops.mkdir()
    lp = make_loop(tmp_path, [terminal_step()])
    (loops / f"{lp.loop_pid}.json").write_text(
        json.dumps({"pid": lp.loop_pid, "root": str(tmp_path / "repo")}),
    )
    assert lp.run() == 0
    assert "already running" not in lp._test["err"].getvalue()
    assert list(loops.glob("*.json")) == []  # teardown removed the rewrite


def test_registry_write_failure_runs_unregistered_loud(tmp_path):
    # A read-only loops dir: the write fails, the loop says so and keeps
    # going rather than halting (the bash jq-failure contract).
    loops = tmp_path / "loops"
    loops.mkdir()
    loops.chmod(0o500)
    try:
        lp = make_loop(tmp_path, [terminal_step()])
        assert lp.run() == 0
        assert "registry write failed; running unregistered" in (
            lp._test["err"].getvalue()
        )
    finally:
        loops.chmod(0o700)


def test_loops_dir_is_propagated_to_session_children(tmp_path):
    # The resolved loops dir must reach children via the env (tracon's
    # discovery.py reads it from its own environment at import time).
    lp = make_loop(tmp_path, [terminal_step()])
    assert lp.run() == 0
    assert lp.env["_AUTOPILOT_LOOPS_DIR"] == str(tmp_path / "loops")
    assert lp.env["_AUTOPILOT_LOOP"] == str(lp.loop_pid)


def test_oldest_live_loop_pid_picks_the_earliest_started_live_entry(tmp_path):
    # PRD 00199: the window yield needs the oldest LIVE loop on the account.
    # A dead pid with an earlier start is skipped; a malformed entry and one
    # with no started_at are named on stderr and skipped; own pid counts
    # without a liveness probe.
    loops = tmp_path / "loops"
    loops.mkdir()
    dead = subprocess.Popen([sys.executable, "-c", "pass"])
    dead.wait()
    lp = make_loop(tmp_path, [])
    (loops / "dead.json").write_text(
        json.dumps({"pid": dead.pid, "root": "/a", "started_at": "1999-01-01T00:00:00Z"}),
    )
    (loops / "junk.json").write_text("{not json")
    (loops / "nostart.json").write_text(json.dumps({"pid": 1, "root": "/b"}))
    (loops / "own.json").write_text(
        json.dumps({"pid": lp.loop_pid, "root": "/c", "started_at": "2026-01-01T00:00:00Z"}),
    )
    assert lp._oldest_live_loop_pid() == lp.loop_pid
    (loops / "peer.json").write_text(
        json.dumps({"pid": 1, "root": "/d", "started_at": "2025-12-31T23:59:59Z"}),
    )
    assert lp._oldest_live_loop_pid() == 1
    err = lp._test["err"].getvalue()
    assert "junk.json is unreadable or has no started_at" in err
    assert "nostart.json is unreadable or has no started_at" in err


def test_oldest_live_loop_pid_is_none_on_an_empty_or_missing_registry(tmp_path):
    lp = make_loop(tmp_path, [])
    assert lp._oldest_live_loop_pid() is None  # loops dir does not exist yet
    (tmp_path / "loops").mkdir()
    assert lp._oldest_live_loop_pid() is None


def _spawn_forked_loop_shell() -> subprocess.Popen:
    """The tracon layout: a shell that exports the tag AFTER its own exec
    and keeps a tagged child alive. ps reports the EXEC-time environment,
    so the tag is visible on the child only - never on the shell whose pid
    the registry stores."""
    proc = subprocess.Popen(
        [
            "bash",
            "-c",
            f"export _AUTOPILOT_LOOP=$$; {sys.executable} -c "
            '"import time; time.sleep(60)" & wait',
        ],
        start_new_session=True,
    )
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        kids = subprocess.run(
            ["pgrep", "-P", str(proc.pid)],
            capture_output=True,
            text=True,
        ).stdout
        if kids.strip():
            return proc
        time.sleep(0.05)
    os.killpg(proc.pid, signal.SIGKILL)
    raise AssertionError("forked loop shell never spawned its tagged child")


def test_prune_keeps_a_loop_shell_tagged_only_on_its_child(tmp_path):
    # The registry stores the process-group LEADER (the forked shell), but
    # the tag reaches ps only on the exec'd driver beneath it. Pruning that
    # entry blinds tracon to a live loop: no pause chip, no limit-wait, and
    # q -> s reports "nothing to stop".
    loops = tmp_path / "loops"
    loops.mkdir()
    shell = _spawn_forked_loop_shell()
    try:
        entry = loops / f"{shell.pid}.json"
        entry.write_text(json.dumps({"pid": shell.pid, "root": "/x"}))
        prune_registry(loops, own_pid=4242)
        assert entry.exists()
    finally:
        os.killpg(shell.pid, signal.SIGKILL)
        shell.wait()


def test_prune_removes_dead_untagged_and_malformed_entries(tmp_path):
    loops = tmp_path / "loops"
    loops.mkdir()
    dead = subprocess.Popen([sys.executable, "-c", "pass"])
    dead.wait()
    (loops / "dead.json").write_text(json.dumps({"pid": dead.pid, "root": "/x"}))
    (loops / "junk.json").write_text("{not json")
    # pid 1 is alive but its env carries no _AUTOPILOT_LOOP tag: recycled.
    (loops / "recycled.json").write_text(json.dumps({"pid": 1, "root": "/z"}))
    (loops / "own.json").write_text(json.dumps({"pid": 4242, "root": "/y"}))
    prune_registry(loops, own_pid=4242)
    assert not (loops / "dead.json").exists()
    assert not (loops / "junk.json").exists()
    assert not (loops / "recycled.json").exists()
    assert (loops / "own.json").exists()  # never our own entry


def test_live_wrapper_pid_ignores_an_alive_but_untagged_pid(tmp_path):
    # A recycled or borrowed pid can be genuinely alive at the right root
    # without ever having been the loop - only the _AUTOPILOT_LOOP tag
    # proves incumbency.
    loops = tmp_path / "loops"
    loops.mkdir()
    root = tmp_path / "repo"
    proc = subprocess.Popen(
        [sys.executable, "-c", "import time; time.sleep(60)"],
    )
    try:
        (loops / f"{proc.pid}.json").write_text(
            json.dumps({"pid": proc.pid, "root": str(root)}),
        )
        assert live_wrapper_pid(root, loops) is None
    finally:
        proc.kill()
        proc.wait()


def test_prune_spares_an_unreadable_entry_and_it_resolves_once_readable(tmp_path):
    # An OSError reading the file means "I couldn't check this", not "this
    # is garbage" - prune must leave it alone, and once it can be read
    # again the tagged loop it names must still resolve.
    loops = tmp_path / "loops"
    loops.mkdir()
    root = tmp_path / "repo"
    shell = _spawn_forked_loop_shell()
    entry = loops / f"{shell.pid}.json"
    try:
        entry.write_text(json.dumps({"pid": shell.pid, "root": str(root)}))
        try:
            entry.chmod(0o000)
            prune_registry(loops, own_pid=4242)
            assert entry.exists()
            assert live_wrapper_pid(root, loops) is None
        finally:
            if entry.exists():
                entry.chmod(0o644)
        assert live_wrapper_pid(root, loops) == shell.pid
    finally:
        os.killpg(shell.pid, signal.SIGKILL)
        shell.wait()


def test_prune_deletes_an_entry_with_invalid_utf8_bytes_without_raising(tmp_path):
    # UnicodeDecodeError is a ValueError subclass, not an OSError: it must
    # not escape the except OSError guarding the read, and the entry is
    # garbage (like invalid JSON), not merely unreadable - it gets deleted.
    loops = tmp_path / "loops"
    loops.mkdir()
    entry = loops / "garbage.json"
    entry.write_bytes(b"\xff\xfe\x00binary")
    prune_registry(loops, own_pid=4242)
    assert not entry.exists()


def test_prune_deletes_a_utf16_encoded_entry_even_when_its_pid_is_live_and_tagged(
    tmp_path,
):
    # The registry is a UTF-8 JSON directory by contract. A spawned, live,
    # correctly TAGGED pid is used here so nothing else could explain a
    # deletion: json.loads auto-detects UTF-16 from the BOM and parses this
    # entry fine, so only the encoding - not liveness, not the tag - can be
    # the reason it gets pruned.
    loops = tmp_path / "loops"
    loops.mkdir()
    shell = _spawn_forked_loop_shell()
    try:
        entry = loops / f"{shell.pid}.json"
        entry.write_bytes(
            json.dumps({"pid": shell.pid, "root": "/x"}).encode("utf-16"),
        )
        prune_registry(loops, own_pid=4242)
        assert not entry.exists()
    finally:
        os.killpg(shell.pid, signal.SIGKILL)
        shell.wait()


def test_pid_tagged_requires_an_exact_pid_match(monkeypatch):
    def fake_exec_env(pid):
        return {"_AUTOPILOT_LOOP": "4321"} if pid == 1000 else None
    monkeypatch.setattr(loop_gates, "exec_env", fake_exec_env)
    monkeypatch.setattr(loop_gates, "_child_pids", lambda pid: ["1000"])
    assert loop_gates._pid_tagged(999, 4321) is True
    assert loop_gates._pid_tagged(999, 432) is False
    assert loop_gates._pid_tagged(999, 321) is False
    assert loop_gates._pid_tagged(999, 43210) is False


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


def test_loop_entry_then_skill_entry_writes_one_resume_row(tmp_path, monkeypatch, capsys):
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
    stale = {"stop": None, "detail": "", "prd": _OTHER, "catchup": "delta", "design": "reuse"}
    _build_tree(ap, loop_entry={"entered_by": "loop", "prd": _OTHER, "result": stale})

    assert cli_main.main(["enter", "--state", str(ap / "state.json")]) == 0

    printed = json.loads(capsys.readouterr().out)
    assert printed["prd"] == _PRD
    assert printed["catchup"] == "full"
    assert "loop_entry" not in _read_state(ap)
    assert rows == [(_PRD, "build")]


def test_manual_prd_arg_skips_the_replay_even_with_a_matching_entry(
    tmp_path, monkeypatch, capsys
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

    assert cli_main.main(["enter", "--state", str(ap / "state.json"), "--prd", _PRD]) == 0

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
    tmp_path, next_phase, marker, called
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
