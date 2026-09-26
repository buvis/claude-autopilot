#!/usr/bin/env python3
"""Tests for cli/wave_launch.py and cli/wave_cli.py - launching a wave (PRD 00214).

Every proof runs against a throwaway `git init` repo under `tmp_path`, never this
checkout's own backlog or `dev/local/autopilot/wave.json`. No real loop is ever
started: a recording `spawn_fn` stands in for one, except in the single test that
needs a live process, which puts a stub `python3` on PATH.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from cli import wave, wave_cli, wave_launch
from cli.loop_gates import live_wrapper_pid
from cli.loop_testutil import _spawn_tagged_incumbent

CLI_MAIN = Path(__file__).resolve().parent / "__main__.py"
SKILL_MD = "skills/run-autopilot/SKILL.md"
RECORDS_PY = "skills/run-autopilot/cli/records.py"


def _prd(*paths: str) -> str:
    """A PRD naming `paths` on one `- **Location**:` line."""
    spans = ", ".join(f"`{path}`" for path in paths)
    return f"# A PRD\n\n- **Location**: {spans}\n"


ONE_LANE = {"00001-a.md": _prd("x/a.py")}
TWO_LANES = {"00001-a.md": _prd("x/a.py"), "00002-b.md": _prd("y/b.py")}


def _git(cwd: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=True,
    )


def _backlog(root: Path) -> Path:
    return root / "dev" / "local" / "prds" / "backlog"


def _autopilot(root: Path) -> Path:
    return root / "dev" / "local" / "autopilot"


def _repo(tmp_path: Path, prds: dict[str, str]) -> tuple[Path, Path]:
    """A committed git repo with `prds` in backlog: (repo, wave.json path)."""
    repo = tmp_path / "proj"
    _backlog(repo).mkdir(parents=True)
    for name, text in prds.items():
        (_backlog(repo) / name).write_text(text, encoding="utf-8")
    _autopilot(repo).mkdir(parents=True)
    (repo / ".gitignore").write_text("dev/local/\n", encoding="utf-8")
    (repo / "README.md").write_text("seed\n", encoding="utf-8")
    _git(repo, "init", "-q", "-b", "master")
    _git(repo, "config", "user.email", "wave@example.com")
    _git(repo, "config", "user.name", "Wave Test")
    _git(repo, "add", ".gitignore", "README.md")
    _git(repo, "commit", "-qm", "seed")
    return repo, _autopilot(repo) / "wave.json"


def _planned(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    prds: dict[str, str],
    max_lanes: int = 2,
) -> tuple[Path, Path]:
    """`_repo` with a planned wave saved, and the process cwd moved off the repo
    so a git call that forgets `cwd=repo` fails instead of hitting a real repo."""
    repo, wave_path = _repo(tmp_path, prds)
    monkeypatch.chdir(tmp_path)
    assert wave.plan(repo, wave_path, max_lanes=max_lanes) == 0
    return repo, wave_path


def _utc_dates() -> set[str]:
    """Today and yesterday in UTC: a stamp taken moments ago starts with one."""
    now = datetime.now(timezone.utc)
    return {(now - timedelta(days=days)).strftime("%Y-%m-%d") for days in (0, 1)}


class _Handle:
    def __init__(self, pid: int) -> None:
        self.pid = pid


class _FakeSpawn:
    """Stands in for `_default_spawn`: records the call, starts nothing."""

    def __init__(self) -> None:
        self.calls: list[dict] = []

    def __call__(self, cmd: list[str], **kwargs: object) -> _Handle:
        self.calls.append({"cmd": cmd, **kwargs})
        return _Handle(9000 + len(self.calls))


def _recording_git(calls: list[tuple[list[str], object]]) -> Callable[..., object]:
    """A `run_git` that records (args, cwd) and then runs the real thing."""

    def run_git(args: list[str], cwd: object = None) -> subprocess.CompletedProcess:
        calls.append((list(args), cwd))
        return subprocess.run(
            ["git", *args],
            cwd=cwd,
            capture_output=True,
            text=True,
            check=True,
        )

    return run_git


def _stub_python3(bin_dir: Path, record: Path) -> None:
    """A `python3` on PATH that records how the wrapper invoked it, then exits."""
    bin_dir.mkdir()
    script = bin_dir / "python3"
    partial = f"{record}.tmp"
    script.write_text(
        f"#!{sys.executable}\n"
        "import json, os, sys\n"
        "print('the lane loop ran', flush=True)\n"
        "payload = json.dumps(\n"
        "    {\n"
        "        'pid': os.getpid(),\n"
        "        'argv': sys.argv,\n"
        "        'cwd': os.getcwd(),\n"
        "        'env': dict(os.environ),\n"
        "    }\n"
        ")\n"
        f"open({partial!r}, 'w').write(payload)\n"
        f"os.replace({partial!r}, {str(record)!r})\n",
        encoding="utf-8",
    )
    script.chmod(0o755)


def _spawned_record(record: Path) -> dict:
    """The stub's record, once the spawned lane process has written it."""
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        if record.exists():
            return json.loads(record.read_text(encoding="utf-8"))
        time.sleep(0.05)
    raise AssertionError(f"the lane process never wrote {record}")


def _dead_pid() -> int:
    """The pid of a process that has exited and been reaped."""
    proc = subprocess.Popen([sys.executable, "-c", ""])
    proc.wait(30)
    return proc.pid


# ── validate ─────────────────────────────────────────────────────────────────


def test_validate_passes_the_backlog_it_was_planned_from(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo, wave_path = _planned(tmp_path, monkeypatch, TWO_LANES)
    assert wave_launch.validate(repo, wave.load(wave_path), TWO_LANES) == []


def test_validate_flags_a_prd_that_left_the_backlog(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo, wave_path = _planned(tmp_path, monkeypatch, TWO_LANES)
    left = {"00001-a.md": TWO_LANES["00001-a.md"]}
    assert wave_launch.validate(repo, wave.load(wave_path), left) == [
        "lane l2: 00002-b.md is no longer in backlog/",
    ]


def test_validate_flags_a_prd_that_now_names_no_paths(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo, wave_path = _planned(tmp_path, monkeypatch, TWO_LANES)
    drifted = {**TWO_LANES, "00002-b.md": "# Prose only\n"}
    assert wave_launch.validate(repo, wave.load(wave_path), drifted) == [
        (
            "lane l2: 00002-b.md now names no paths - move it to held_back by"
            " hand before launching"
        ),
    ]


def test_validate_flags_two_lanes_that_now_share_a_path(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo, wave_path = _planned(tmp_path, monkeypatch, TWO_LANES)
    drifted = {**TWO_LANES, "00002-b.md": _prd("y/b.py", "x/a.py")}
    assert wave_launch.validate(repo, wave.load(wave_path), drifted) == [
        "lane l1 and lane l2 share x/a.py",
    ]


def test_validate_flags_two_lanes_that_both_touch_force_shared_files(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo, wave_path = _planned(tmp_path, monkeypatch, TWO_LANES)
    drifted = {
        "00001-a.md": _prd("x/a.py", SKILL_MD),
        "00002-b.md": _prd("y/b.py", RECORDS_PY),
    }
    assert wave_launch.validate(repo, wave.load(wave_path), drifted) == [
        (
            "lane l1 and lane l2 both touch force-shared files"
            f" ({SKILL_MD} in l1, {RECORDS_PY} in l2)"
        ),
    ]


def test_validate_reports_a_shape_problem_before_re_deriving_paths(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # No "lanes" key at all: re-deriving paths first would raise KeyError.
    repo, wave_path = _planned(tmp_path, monkeypatch, TWO_LANES)
    loaded = wave.load(wave_path)
    broken = {key: value for key, value in loaded.items() if key != "lanes"}
    assert wave_launch.validate(repo, broken, {}) == [
        "wave.json: malformed top-level field lanes",
    ]


# ── launch ───────────────────────────────────────────────────────────────────


def test_launch_adds_a_worktree_per_lane_at_base_sha(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo, wave_path = _planned(tmp_path, monkeypatch, TWO_LANES)
    head = _git(repo, "rev-parse", "HEAD").stdout.strip()
    spawn = _FakeSpawn()
    assert wave_launch.launch(repo, wave_path, spawn_fn=spawn) == 0
    saved = wave.load(wave_path)
    assert (saved["status"], saved["base_sha"], saved["base_branch"]) == (
        "running",
        head,
        "master",
    )
    assert [each["order"] for each in saved["lanes"]] == [1, 2]
    dates = _utc_dates()
    for each in saved["lanes"]:
        worktree = Path(each["worktree"])
        assert worktree == tmp_path / f"proj-l{each['order']}"
        assert _git(worktree, "rev-parse", "HEAD").stdout.strip() == head
        checked_out = _git(worktree, "rev-parse", "--abbrev-ref", "HEAD")
        assert checked_out.stdout.strip() == each["branch"]
        assert (each["worktree_created"], each["status"]) == (True, "running")
        assert each["started_at"][:10] in dates, each["started_at"]
    assert [each["pid"] for each in saved["lanes"]] == [9001, 9002]
    assert [Path(call["cwd"]) for call in spawn.calls] == [
        Path(each["worktree"]) for each in saved["lanes"]
    ]


def test_launch_moves_lane_prds_out_of_the_main_backlog(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo, wave_path = _planned(tmp_path, monkeypatch, TWO_LANES)
    assert wave_launch.launch(repo, wave_path, spawn_fn=_FakeSpawn()) == 0
    assert list(_backlog(repo).iterdir()) == []
    for each in wave.load(wave_path)["lanes"]:
        worktree = Path(each["worktree"])
        moved = sorted(path.name for path in _backlog(worktree).iterdir())
        assert moved == sorted(each["prds"])
        for prd in each["prds"]:
            text = (_backlog(worktree) / prd).read_text(encoding="utf-8")
            assert text == TWO_LANES[prd]
        for folder in ("wip", "done", "hold"):
            assert (_backlog(worktree).parent / folder).is_dir()
        assert _autopilot(worktree).is_dir()
        assert not (worktree / "dev" / "local" / "meta").exists()


def test_launch_copies_meta_when_present(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo, wave_path = _planned(tmp_path, monkeypatch, TWO_LANES)
    meta = repo / "dev" / "local" / "meta"
    (meta / "sub").mkdir(parents=True)
    (meta / "capsule.md").write_text("capsule\n", encoding="utf-8")
    (meta / "sub" / "cursors.json").write_text("{}\n", encoding="utf-8")
    assert wave_launch.launch(repo, wave_path, spawn_fn=_FakeSpawn()) == 0
    for each in wave.load(wave_path)["lanes"]:
        copied = Path(each["worktree"]) / "dev" / "local" / "meta"
        assert (copied / "capsule.md").read_text(encoding="utf-8") == "capsule\n"
        assert (copied / "sub" / "cursors.json").read_text(encoding="utf-8") == "{}\n"
    assert (meta / "capsule.md").exists(), "meta left the main repo"


def test_launch_refuses_overlapping_lanes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    repo, wave_path = _planned(tmp_path, monkeypatch, TWO_LANES)
    before = wave_path.read_text(encoding="utf-8")
    # A hand edit between plan and launch: l2's PRD now names l1's file too.
    (_backlog(repo) / "00002-b.md").write_text(
        _prd("y/b.py", "x/a.py"),
        encoding="utf-8",
    )
    spawn = _FakeSpawn()
    assert wave_launch.launch(repo, wave_path, spawn_fn=spawn) == 1
    err = capsys.readouterr().err
    assert "lane l1" in err and "lane l2" in err, err
    assert "share x/a.py" in err, err
    assert "refusing to launch" in err, err
    assert spawn.calls == []
    assert wave_path.read_text(encoding="utf-8") == before
    assert not (tmp_path / "proj-l1").exists()
    assert sorted(path.name for path in _backlog(repo).iterdir()) == sorted(TWO_LANES)


def test_launch_refuses_a_dirty_tree(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    repo, wave_path = _planned(tmp_path, monkeypatch, TWO_LANES)
    (repo / "README.md").write_text("an uncommitted edit\n", encoding="utf-8")
    spawn = _FakeSpawn()
    assert wave_launch.launch(repo, wave_path, spawn_fn=spawn) == 1
    assert "dirty tree" in capsys.readouterr().err
    assert spawn.calls == []
    saved = wave.load(wave_path)
    assert (saved["status"], saved["base_sha"], saved["base_branch"]) == (
        "planned",
        None,
        None,
    )
    assert not (tmp_path / "proj-l1").exists()
    assert sorted(path.name for path in _backlog(repo).iterdir()) == sorted(TWO_LANES)


def test_launch_refuses_a_wave_that_is_not_planned(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    repo, wave_path = _planned(tmp_path, monkeypatch, ONE_LANE, max_lanes=1)
    wave.save(wave_path, {**wave.load(wave_path), "status": "running"})
    spawn = _FakeSpawn()
    assert wave_launch.launch(repo, wave_path, spawn_fn=spawn) == 1
    assert "not in planned state" in capsys.readouterr().err
    assert spawn.calls == []
    assert not (tmp_path / "proj-l1").exists()


def test_launch_refuses_a_structurally_invalid_wave(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    repo, wave_path = _planned(tmp_path, monkeypatch, ONE_LANE, max_lanes=1)
    wave.save(wave_path, {**wave.load(wave_path), "review_slots": 0})
    spawn = _FakeSpawn()
    assert wave_launch.launch(repo, wave_path, spawn_fn=spawn) == 1
    err = capsys.readouterr().err
    assert "malformed top-level field review_slots" in err, err
    assert "refusing to launch" in err, err
    assert spawn.calls == []
    assert not (tmp_path / "proj-l1").exists()


def test_launch_spawns_the_loop_with_its_own_pid_tag(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo, wave_path = _planned(tmp_path, monkeypatch, ONE_LANE, max_lanes=1)
    record = tmp_path / "lane-record.json"
    _stub_python3(tmp_path / "bin", record)
    monkeypatch.setenv("PATH", f"{tmp_path / 'bin'}{os.pathsep}{os.environ['PATH']}")
    assert wave_launch.launch(repo, wave_path) == 0
    spawned = _spawned_record(record)
    lane = wave.load(wave_path)["lanes"][0]
    assert spawned["env"]["_AUTOPILOT_LOOP"] == str(spawned["pid"])
    assert spawned["pid"] == lane["pid"]
    # The stub's own path leads argv, so the wrapper's words are the tail.
    tail = [Path(spawned["argv"][-2]).name, spawned["argv"][-1]]
    assert tail == ["__main__.py", "loop"], spawned["argv"]
    assert Path(spawned["cwd"]).resolve() == Path(lane["worktree"]).resolve()
    log = _autopilot(Path(lane["worktree"])) / "wrapper.log"
    assert "the lane loop ran" in log.read_text(encoding="utf-8")


def test_launch_env_carries_the_slot_dir_and_count(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo, wave_path = _planned(tmp_path, monkeypatch, ONE_LANE, max_lanes=1)
    # review_slots is a hand-edit surface: the count comes from wave.json.
    wave.save(wave_path, {**wave.load(wave_path), "review_slots": 5})
    monkeypatch.setenv("_AUTOPILOT_LOOP", "4242")
    monkeypatch.setenv("WAVE_TEST_SENTINEL", "carried")
    spawn = _FakeSpawn()
    assert wave_launch.launch(repo, wave_path, spawn_fn=spawn) == 0
    call = spawn.calls[0]
    env = call["env"]
    assert env["_AUTOPILOT_REVIEW_SLOTS_DIR"] == str(_autopilot(repo) / "wave-slots")
    assert env["_AUTOPILOT_REVIEW_SLOTS"] == "5"
    assert env["_AUTOPILOT_TRACON_CHILD"] == "1"
    assert "_AUTOPILOT_LOOP" not in env
    assert env["WAVE_TEST_SENTINEL"] == "carried"
    assert call["start_new_session"] is True
    assert call["stdin"] is subprocess.DEVNULL
    assert call["stderr"] is subprocess.STDOUT
    assert call["cmd"][:2] == ["bash", "-c"]
    assert "_AUTOPILOT_LOOP=$$" in call["cmd"][2]
    assert Path(call["cmd"][3]).name == "__main__.py"


def test_launch_runs_every_git_call_in_the_repo(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo, wave_path = _planned(tmp_path, monkeypatch, ONE_LANE, max_lanes=1)
    calls: list[tuple[list[str], object]] = []
    exit_code = wave_launch.launch(
        repo,
        wave_path,
        spawn_fn=_FakeSpawn(),
        run_git=_recording_git(calls),
    )
    assert exit_code == 0
    assert calls, "launch never called run_git"
    for args, cwd in calls:
        assert args[0] != "git", f"the call site prepended git itself: {args}"
        assert cwd is not None and Path(cwd) == repo, (args, cwd)
    assert ["status", "--porcelain"] in [args for args, _ in calls]
    assert any(args[:2] == ["worktree", "add"] for args, _ in calls)


def test_a_failed_lane_leaves_the_earlier_lane_running_and_recorded(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo, wave_path = _planned(tmp_path, monkeypatch, TWO_LANES)
    _git(repo, "branch", wave.load(wave_path)["lanes"][1]["branch"])
    spawn = _FakeSpawn()
    with pytest.raises(subprocess.CalledProcessError):
        wave_launch.launch(repo, wave_path, spawn_fn=spawn)
    saved = wave.load(wave_path)
    assert saved["status"] == "running"
    assert saved["base_sha"] == _git(repo, "rev-parse", "HEAD").stdout.strip()
    first, second = saved["lanes"]
    assert (first["worktree_created"], first["status"], first["pid"]) == (
        True,
        "running",
        9001,
    )
    assert (second["worktree_created"], second["status"], second["pid"]) == (
        False,
        "planned",
        None,
    )
    assert len(spawn.calls) == 1
    worktrees = _git(repo, "worktree", "list").stdout
    assert "proj-l1" in worktrees, worktrees
    assert "proj-l2" not in worktrees, worktrees


def test_lane_roots_are_distinct_registry_roots(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo, wave_path = _planned(tmp_path, monkeypatch, ONE_LANE, max_lanes=1)
    assert wave_launch.launch(repo, wave_path, spawn_fn=_FakeSpawn()) == 0
    lane_root = Path(wave.load(wave_path)["lanes"][0]["worktree"])
    assert lane_root.name == f"{repo.name}-l1"
    loops = tmp_path / "loops"
    loops.mkdir()
    entry = loops / "incumbent.json"
    incumbent = _spawn_tagged_incumbent()
    try:
        for registered, other in ((repo, lane_root), (lane_root, repo)):
            entry.write_text(
                json.dumps({"pid": incumbent.pid, "root": str(registered)}),
                encoding="utf-8",
            )
            assert live_wrapper_pid(registered, loops) == incumbent.pid
            assert live_wrapper_pid(other, loops) is None
    finally:
        incumbent.kill()
        incumbent.wait(10)


# ── lane_status ──────────────────────────────────────────────────────────────


def test_lane_status_reports_the_stored_status_without_a_pid(tmp_path: Path) -> None:
    lane = {"pid": None, "status": "planned", "worktree": str(tmp_path / "proj-l1")}
    assert wave_launch.lane_status(lane) == "planned"
    assert wave_launch.lane_status({**lane, "status": "aborted"}) == "aborted"


def test_lane_status_reports_running_while_the_pid_is_alive(tmp_path: Path) -> None:
    # The stored status goes stale the moment a lane runs; liveness wins.
    lane = {
        "pid": os.getpid(),
        "status": "planned",
        "worktree": str(tmp_path / "proj-l1"),
    }
    assert wave_launch.lane_status(lane) == "running"


@pytest.mark.parametrize(
    ("state", "expected"),
    [
        ('{"next_phase": ""}', "drained"),
        ('{"next_phase": "work"}', "unfinished"),
        ("{}", "unfinished"),
        ("{not json", "unfinished"),
        (None, "unfinished"),
    ],
)
def test_lane_status_reads_a_dead_lanes_state_json(
    tmp_path: Path,
    state: str | None,
    expected: str,
) -> None:
    worktree = tmp_path / "proj-l1"
    _autopilot(worktree).mkdir(parents=True)
    if state is not None:
        (_autopilot(worktree) / "state.json").write_text(state, encoding="utf-8")
    lane = {"pid": _dead_pid(), "status": "running", "worktree": str(worktree)}
    assert wave_launch.lane_status(lane) == expected


# ── the wave verbs ───────────────────────────────────────────────────────────


def _parse(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    wave_cli.add(subparsers)
    return parser.parse_args(argv)


def test_add_registers_every_verb_with_state_and_plan_with_max_lanes() -> None:
    assert _parse(["wave", "plan"]).max_lanes == 3
    planned = _parse(["wave", "plan", "--max-lanes", "5", "--state", "/tmp/s.json"])
    assert (planned.verb, planned.max_lanes, planned.state) == (
        "plan",
        5,
        "/tmp/s.json",
    )
    for verb in ("launch", "status", "abort"):
        parsed = _parse(["wave", verb, "--state", "/tmp/s.json"])
        assert (parsed.verb, parsed.state) == (verb, "/tmp/s.json")
        assert _parse(["wave", verb]).state is None
    with pytest.raises(SystemExit):
        _parse(["wave"])


def test_run_plan_cuts_the_backlog_into_the_paths_it_was_given(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo, wave_path = _repo(tmp_path, TWO_LANES)
    monkeypatch.chdir(tmp_path)
    args = _parse(["wave", "plan", "--max-lanes", "1"])
    assert wave_cli.run(args, repo, wave_path) == 0
    saved = wave.load(wave_path)
    assert saved["status"] == "planned"
    assert [each["prds"] for each in saved["lanes"]] == [["00001-a.md", "00002-b.md"]]
    assert wave._structural_errors(repo, saved) == []


def test_run_launch_reports_a_missing_wave_json(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    repo, wave_path = _repo(tmp_path, ONE_LANE)
    monkeypatch.chdir(tmp_path)
    assert wave_cli.run(_parse(["wave", "launch"]), repo, wave_path) == 1
    captured = capsys.readouterr()
    assert f"no wave.json at {wave_path}" in captured.out + captured.err
    assert "wave plan" in captured.out + captured.err
    assert not wave_path.exists()


def test_run_launch_refuses_a_corrupt_wave_json(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    repo, wave_path = _repo(tmp_path, ONE_LANE)
    monkeypatch.chdir(tmp_path)
    wave_path.write_text('{"id": "2026', encoding="utf-8")
    assert wave_cli.run(_parse(["wave", "launch"]), repo, wave_path) == 1
    captured = capsys.readouterr()
    assert "refusing to touch a corrupt wave.json" in captured.out + captured.err
    assert wave_path.read_text(encoding="utf-8") == '{"id": "2026'
    assert not (tmp_path / "proj-l1").exists()


def test_run_launch_reports_a_failed_git_call_instead_of_raising(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    repo, wave_path = _planned(tmp_path, monkeypatch, ONE_LANE, max_lanes=1)
    # The lane's branch is taken, so `git worktree add -b` fails before any spawn.
    _git(repo, "branch", wave.load(wave_path)["lanes"][0]["branch"])
    assert wave_cli.run(_parse(["wave", "launch"]), repo, wave_path) == 1
    captured = capsys.readouterr()
    assert "returned non-zero exit status" in captured.out + captured.err
    assert "proj-l1" not in _git(repo, "worktree", "list").stdout


def test_the_cli_registers_wave_and_derives_the_repo_from_the_state_path(
    tmp_path: Path,
) -> None:
    repo, wave_path = _repo(tmp_path, ONE_LANE)
    proc = subprocess.run(
        [
            sys.executable,
            str(CLI_MAIN),
            "wave",
            "plan",
            "--max-lanes",
            "1",
            "--state",
            str(_autopilot(repo) / "state.json"),
        ],
        capture_output=True,
        text=True,
        cwd=str(tmp_path),
    )
    assert proc.returncode == 0, proc.stderr
    saved = json.loads(wave_path.read_text(encoding="utf-8"))
    assert saved["repo"] == str(repo)
    assert [each["prds"] for each in saved["lanes"]] == [["00001-a.md"]]
    assert wave._structural_errors(repo, saved) == []
