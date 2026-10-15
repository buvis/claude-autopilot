"""Tests for the loop registry (cli/loop_gates.py), split out of
test_loop_gates.py to keep that file under the style-limit line count. The
harness (fake clock, scripted spawn, make_loop) is cli/loop_testutil.py.
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

from cli import loop_gates, loop_testutil
from cli.loop_gates import live_wrapper_pid, prune_registry
from cli.loop_testutil import _spawn_tagged_incumbent, make_loop, terminal_step, write_state

# The autouse fixture registers by being a module attribute.
_no_real_drain_side_effects = loop_testutil._no_real_drain_side_effects


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
        json.dumps(
            {"pid": dead.pid, "root": "/a", "started_at": "1999-01-01T00:00:00Z"}
        ),
    )
    (loops / "junk.json").write_text("{not json")
    (loops / "nostart.json").write_text(json.dumps({"pid": 1, "root": "/b"}))
    (loops / "own.json").write_text(
        json.dumps(
            {"pid": lp.loop_pid, "root": "/c", "started_at": "2026-01-01T00:00:00Z"}
        ),
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
