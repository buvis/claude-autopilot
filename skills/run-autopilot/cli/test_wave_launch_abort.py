#!/usr/bin/env python3
"""Tests for cli/wave_launch.py's status/abort and their wave verbs (PRD 00214).

Every proof runs against a throwaway `git init` repo under `tmp_path`, never this
checkout's own backlog or `dev/local/autopilot/wave.json`. No real loop is ever
started: lanes launch with a recording `spawn_fn` and then have their pids
cleared, except the tests that need a live process group of their own, each of
which reaps that group in a `finally`.

The launch-side helpers live in the sibling `test_wave_launch` module; this file
imports them rather than restating them.

`status` renders a table, and these tests read it one cell at a time: each field
the contract lists (lane name, pid, state.prd, phase, next_phase, one count per
lifecycle dir, phase_end, signal, lane_status, abort_error) is its own cell,
separated by whitespace or a "|", and every row is the same width.
"""

from __future__ import annotations

import contextlib
import copy
import os
import signal
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

import pytest

from cli import wave, wave_cli, wave_launch
from cli.test_wave_launch import (
    ONE_LANE,
    TWO_LANES,
    _autopilot,
    _backlog,
    _dead_pid,
    _FakeSpawn,
    _git,
    _parse,
    _planned,
    _recording_git,
    _repo,
    _spawned_record,
)

# A leader that spawns one child and exits at once: the child stays in the
# leader's process group and outlives it, which is the case `_pgid_alive` exists
# for. The child records its own pid so the test can prove it is not the leader.
_CHILD_SRC = (
    "import json, os, sys, time\n"
    "open(sys.argv[1] + '.tmp', 'w').write(json.dumps({'pid': os.getpid()}))\n"
    "os.replace(sys.argv[1] + '.tmp', sys.argv[1])\n"
    "time.sleep(120)\n"
)
_LEADER_SRC = (
    "import subprocess, sys\n"
    "subprocess.Popen([sys.executable, '-c', sys.argv[1], sys.argv[2]])\n"
)


def _cells(line: str) -> list[str]:
    """One rendered table line split into its cells."""
    return line.replace("|", " ").split()


def _row(rendered: str, name: str) -> list[str]:
    """The cells of the one rendered row that names lane `name`."""
    rows = [cells for line in rendered.splitlines() if name in (cells := _cells(line))]
    assert len(rows) == 1, rendered
    return rows[0]


def _group_alive(pgid: int) -> bool:
    """The `os.killpg(pgid, 0)` probe itself - never the leader pid, never pgrep."""
    try:
        os.killpg(pgid, 0)
    except ProcessLookupError:
        return False
    return True


def _launched(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    prds: dict[str, str],
) -> tuple[Path, Path]:
    """A launched wave whose worktrees are on disk and whose lanes are not live:
    every pid is cleared, so the kill step has nothing to signal."""
    repo, wave_path = _planned(tmp_path, monkeypatch, prds)
    assert wave_launch.launch(repo, wave_path, spawn_fn=_FakeSpawn()) == 0
    saved = wave.load(wave_path)
    for lane in saved["lanes"]:
        lane["pid"] = None
    wave.save(wave_path, saved)
    assert wave._structural_errors(repo, saved) == []
    return repo, wave_path


def _lane_state(worktree: Path, state: str, metrics: list[str]) -> None:
    """A lane worktree's own loop state and metrics ledger."""
    _autopilot(worktree).mkdir(parents=True, exist_ok=True)
    (_autopilot(worktree) / "state.json").write_text(state, encoding="utf-8")
    ledger = _autopilot(worktree) / "ledger"
    ledger.mkdir(parents=True, exist_ok=True)
    (ledger / "loop-metrics.jsonl").write_text("".join(metrics), encoding="utf-8")


def _lane_prds(worktree: Path, counts: dict[str, int]) -> None:
    """`counts[folder]` PRD files in each of a worktree's lifecycle dirs."""
    for folder, count in counts.items():
        lifecycle = worktree / "dev" / "local" / "prds" / folder
        lifecycle.mkdir(parents=True, exist_ok=True)
        for index in range(count):
            (lifecycle / f"9000{index}-{folder}.md").write_text("x\n", encoding="utf-8")


def _breaking_git(needle: str, boom: Exception) -> Callable[..., object]:
    """A `run_git` that raises `boom` on `git worktree remove <needle>`, and runs
    the real thing for every other call."""

    def run_git(args: list[str], cwd: object = None) -> subprocess.CompletedProcess:
        if args[:2] == ["worktree", "remove"] and needle in args:
            raise boom
        return subprocess.run(
            ["git", *args],
            cwd=cwd,
            capture_output=True,
            text=True,
            check=True,
        )

    return run_git


# ── _pgid_alive ──────────────────────────────────────────────────────────────


def test_pgid_alive_probes_the_group_not_a_single_pid() -> None:
    live = subprocess.Popen(
        [sys.executable, "-c", "import time; time.sleep(120)"],
        start_new_session=True,
    )
    try:
        # start_new_session made it its own group leader, so pid == pgid.
        assert wave_launch._pgid_alive(live.pid) is True
    finally:
        live.kill()
        live.wait(30)
    assert wave_launch._pgid_alive(live.pid) is False


# ── status ───────────────────────────────────────────────────────────────────


def test_status_derives_drained_from_a_dead_pid_and_empty_next_phase(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo, wave_path = _planned(tmp_path, monkeypatch, ONE_LANE, max_lanes=1)
    loaded = wave.load(wave_path)
    lane = loaded["lanes"][0]
    lane["pid"] = _dead_pid()
    lane["status"] = "running"
    _lane_state(
        Path(lane["worktree"]),
        '{"prd": "00001-a.md", "phase": "work", "next_phase": ""}',
        [
            '{"phase_end": "plan", "signal": "stale-amber"}\n',
            '{"phase_end": "review", "signal": "fresh-green"}\n',
            "{not json\n",
        ],
    )
    _lane_prds(Path(lane["worktree"]), {"backlog": 2, "wip": 1, "done": 3, "hold": 0})
    rendered = wave_launch.status(repo, loaded)
    cells = _row(rendered, lane["name"])
    assert str(lane["pid"]) in cells
    assert "00001-a.md" in cells
    assert "work" in cells
    # the LAST PARSEABLE metrics line wins: not the unparseable final line, and
    # not the first line either
    assert {"review", "fresh-green"} <= set(cells)
    assert "stale-amber" not in rendered
    assert {"2", "1", "3", "0"} <= set(cells)
    assert "drained" in cells


def test_status_prints_dashes_for_a_lane_whose_worktree_is_gone(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo, wave_path = _planned(tmp_path, monkeypatch, TWO_LANES)
    loaded = wave.load(wave_path)
    live, gone = loaded["lanes"]
    live["pid"] = _dead_pid()
    live["status"] = "running"
    _lane_state(
        Path(live["worktree"]),
        '{"prd": "00001-a.md", "phase": "work", "next_phase": "review"}',
        ['{"phase_end": "work", "signal": "green"}\n'],
    )
    _lane_prds(Path(live["worktree"]), {"backlog": 1, "wip": 1, "done": 1, "hold": 1})
    gone["pid"] = None
    gone["status"] = "aborted"
    assert not Path(gone["worktree"]).exists()
    rendered = wave_launch.status(repo, loaded)
    dashes = _row(rendered, gone["name"])
    # nothing is left on disk to read, so every worktree-backed field is "-",
    # and the row is still as wide as the lane that does have a worktree
    assert set(dashes) == {gone["name"], "aborted", "-"}
    assert len(dashes) == len(_row(rendered, live["name"]))


def test_status_shows_a_lanes_abort_error_as_an_extra_column(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo, wave_path = _planned(tmp_path, monkeypatch, ONE_LANE, max_lanes=1)
    loaded = wave.load(wave_path)
    lane = loaded["lanes"][0]
    lane["status"] = "abort_failed"
    lane["abort_error"] = "process group 4242 survived SIGKILL"
    rendered = wave_launch.status(repo, loaded)
    assert "process group 4242 survived SIGKILL" in rendered
    assert "abort_failed" in _row(rendered, lane["name"])
    # the column comes from the lane, not from boilerplate: a clean lane has none
    assert "survived SIGKILL" not in wave_launch.status(repo, wave.load(wave_path))


def test_status_mutates_neither_the_wave_dict_nor_wave_json(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo, wave_path = _launched(tmp_path, monkeypatch, TWO_LANES)
    loaded = wave.load(wave_path)
    before_dict = copy.deepcopy(loaded)
    before_bytes = wave_path.read_bytes()
    assert wave_launch.status(repo, loaded).strip() != ""
    assert loaded == before_dict
    assert wave_path.read_bytes() == before_bytes


# ── abort ────────────────────────────────────────────────────────────────────


def test_abort_refuses_a_structurally_invalid_wave_before_touching_anything(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    repo, wave_path = _launched(tmp_path, monkeypatch, TWO_LANES)
    saved = wave.load(wave_path)
    # A hand edit between launch and abort. The premise is proved here, not
    # assumed: this is a shape `_structural_errors` does reject.
    saved["lanes"][0]["order"] = None
    wave.save(wave_path, saved)
    violations = wave._structural_errors(repo, saved)
    assert violations != [], saved["lanes"]
    frozen = wave_path.read_bytes()
    assert wave_launch.abort(repo, wave_path) == 1
    captured = capsys.readouterr()
    printed = captured.out + captured.err
    for violation in violations:
        assert violation in printed, printed
    assert "refusing to touch this wave.json" in printed, printed
    # Nothing was signalled, moved, removed or written: a wave whose control
    # fields are untrustworthy is left exactly as the operator left it.
    assert wave_path.read_bytes() == frozen
    for lane in saved["lanes"]:
        worktree = Path(lane["worktree"])
        assert worktree.exists()
        assert _git(repo, "branch", "--list", lane["branch"]).stdout.strip() != ""
        for prd in lane["prds"]:
            assert (_backlog(worktree) / prd).exists()
            assert not (_backlog(repo) / prd).exists()


def test_abort_returns_prds_and_removes_clean_worktrees(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo, wave_path = _launched(tmp_path, monkeypatch, TWO_LANES)
    lanes = wave.load(wave_path)["lanes"]
    first, second = (Path(lane["worktree"]) for lane in lanes)
    # a lane that finished one PRD and parked another before it was killed
    (first / "dev/local/prds/done/90008-done.md").write_text("done\n", encoding="utf-8")
    (first / "dev/local/prds/hold/90009-held.md").write_text("held\n", encoding="utf-8")
    slots = _autopilot(repo) / "wave-slots"
    slots.mkdir()
    (slots / "slot-1").write_text("taken\n", encoding="utf-8")
    assert wave_launch.abort(repo, wave_path) == 0
    for name, text in TWO_LANES.items():
        assert (_backlog(repo) / name).read_text(encoding="utf-8") == text
    done = repo / "dev/local/prds/done/90008-done.md"
    held = repo / "dev/local/prds/hold/90009-held.md"
    assert done.read_text(encoding="utf-8") == "done\n"
    assert held.read_text(encoding="utf-8") == "held\n"
    assert not first.exists()
    assert not second.exists()
    assert not slots.exists()
    assert _git(repo, "branch", "--list", "wave/*").stdout.strip() == ""
    after = wave.load(wave_path)
    assert after["status"] == "aborted"
    assert [
        (each["pid"], each["status"], each["abort_error"]) for each in after["lanes"]
    ] == [(None, "aborted", None), (None, "aborted", None)]


def test_abort_keeps_a_worktree_with_commits(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    repo, wave_path = _launched(tmp_path, monkeypatch, TWO_LANES)
    lanes = wave.load(wave_path)["lanes"]
    kept, removed = (Path(lane["worktree"]) for lane in lanes)
    (kept / "x").mkdir()
    (kept / "x/a.py").write_text("print('lane work')\n", encoding="utf-8")
    _git(kept, "add", "x/a.py")
    _git(kept, "commit", "-qm", "lane work")
    assert wave_launch.abort(repo, wave_path) == 0
    kept_prd = lanes[0]["prds"][0]
    assert kept.exists()
    assert (kept / "dev/local/prds/backlog" / kept_prd).exists()
    assert not (_backlog(repo) / kept_prd).exists()
    assert _git(repo, "branch", "--list", lanes[0]["branch"]).stdout.strip() != ""
    # the lane with nothing to lose is still finished in the same call
    assert not removed.exists()
    assert (_backlog(repo) / lanes[1]["prds"][0]).exists()
    out = capsys.readouterr().out
    assert str(kept) in out
    assert "uncommitted change(s)" not in out
    after = wave.load(wave_path)
    assert after["status"] == "aborted"
    assert [each["status"] for each in after["lanes"]] == ["aborted", "aborted"]


def test_abort_keeps_a_dirty_worktree_with_no_commits(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    repo, wave_path = _launched(tmp_path, monkeypatch, TWO_LANES)
    saved = wave.load(wave_path)
    lane = saved["lanes"][0]
    kept = Path(lane["worktree"])
    (kept / "NOTES.md").write_text("half-finished work\n", encoding="utf-8")
    spec = f"{saved['base_sha']}..{lane['branch']}"
    assert _git(repo, "rev-list", "--count", spec).stdout.strip() == "0"
    assert wave_launch.abort(repo, wave_path) == 0
    assert (kept / "NOTES.md").read_text(encoding="utf-8") == "half-finished work\n"
    assert (kept / "dev/local/prds/backlog" / lane["prds"][0]).exists()
    assert not (_backlog(repo) / lane["prds"][0]).exists()
    assert _git(repo, "branch", "--list", lane["branch"]).stdout.strip() != ""
    out = capsys.readouterr().out
    assert "1 uncommitted change(s), inspect before reusing this worktree" in out
    after = wave.load(wave_path)
    assert after["status"] == "aborted"
    assert (after["lanes"][0]["status"], after["lanes"][0]["pid"]) == ("aborted", None)


def test_abort_leaves_a_worktree_whose_branch_belongs_to_another_wave(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo, wave_path = _launched(tmp_path, monkeypatch, TWO_LANES)
    saved = wave.load(wave_path)
    lane = saved["lanes"][0]
    squatter = "wave/199001010000/l1"
    _git(repo, "worktree", "remove", "--force", lane["worktree"])
    base = saved["base_sha"]
    _git(repo, "worktree", "add", "-q", "-b", squatter, lane["worktree"], base)
    stranger = Path(lane["worktree"]) / "keep.txt"
    stranger.write_text("another wave's work\n", encoding="utf-8")
    assert wave_launch.abort(repo, wave_path) == 0
    assert stranger.read_text(encoding="utf-8") == "another wave's work\n"
    assert _git(repo, "branch", "--list", squatter).stdout.strip() != ""
    assert _git(repo, "branch", "--list", lane["branch"]).stdout.strip() != ""
    after = wave.load(wave_path)
    assert after["status"] == "aborted"
    assert (after["lanes"][0]["status"], after["lanes"][0]["pid"]) == ("aborted", None)


def test_abort_leaves_a_worktree_this_wave_never_recorded_creating(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo, wave_path = _launched(tmp_path, monkeypatch, TWO_LANES)
    saved = wave.load(wave_path)
    lane = saved["lanes"][0]
    lane["worktree_created"] = False
    wave.save(wave_path, saved)
    kept = Path(lane["worktree"])
    assert wave_launch.abort(repo, wave_path) == 0
    assert kept.exists()
    assert (kept / "dev/local/prds/backlog" / lane["prds"][0]).exists()
    assert _git(repo, "branch", "--list", lane["branch"]).stdout.strip() != ""
    # git still registers the pair, so only the missing flag held abort back
    porcelain = _git(repo, "worktree", "list", "--porcelain").stdout
    assert f"worktree {kept}" in porcelain
    after = wave.load(wave_path)
    assert after["status"] == "aborted"
    assert (after["lanes"][0]["status"], after["lanes"][0]["pid"]) == ("aborted", None)


@pytest.mark.parametrize(
    "boom",
    [
        OSError("worktree is busy"),
        subprocess.CalledProcessError(1, "git worktree remove"),
    ],
    ids=["oserror", "git-failure"],
)
def test_abort_finishes_every_other_lane_after_one_lane_raises(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    boom: Exception,
) -> None:
    repo, wave_path = _launched(tmp_path, monkeypatch, TWO_LANES)
    lanes = wave.load(wave_path)["lanes"]
    broken, healthy = (Path(lane["worktree"]) for lane in lanes)
    run_git = _breaking_git(str(broken), boom)
    assert wave_launch.abort(repo, wave_path, run_git=run_git) == 1
    after = wave.load(wave_path)
    assert after["status"] == "abort_failed"
    failed, finished = after["lanes"]
    assert failed["status"] == "abort_failed"
    assert "worktree" in (failed["abort_error"] or "")
    assert failed["pid"] is None
    assert broken.exists()
    # the other lane is still finished, and the warning names the failing lane
    assert (finished["status"], finished["abort_error"]) == ("aborted", None)
    assert not healthy.exists()
    assert (_backlog(repo) / lanes[1]["prds"][0]).exists()
    assert lanes[0]["name"] in capsys.readouterr().out


def test_a_second_abort_retries_only_the_lane_that_failed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo, wave_path = _launched(tmp_path, monkeypatch, TWO_LANES)
    lanes = wave.load(wave_path)["lanes"]
    broken = Path(lanes[0]["worktree"])
    first = _breaking_git(str(broken), OSError("worktree is busy"))
    assert wave_launch.abort(repo, wave_path, run_git=first) == 1
    assert wave.load(wave_path)["status"] == "abort_failed"
    calls: list[tuple[list[str], object]] = []
    assert wave_launch.abort(repo, wave_path, run_git=_recording_git(calls)) == 0
    after = wave.load(wave_path)
    assert after["status"] == "aborted"
    assert [each["status"] for each in after["lanes"]] == ["aborted", "aborted"]
    assert not broken.exists()
    # only the unfinished lane is touched: the lane already cleaned up is gone
    # from the registry, so it is neither removed nor deleted a second time
    removals = [args for args, _ in calls if args[:2] == ["worktree", "remove"]]
    assert removals == [["worktree", "remove", "--force", lanes[0]["worktree"]]]
    deletions = [args for args, _ in calls if args[:2] == ["branch", "-D"]]
    assert deletions == [["branch", "-D", lanes[0]["branch"]]]


def test_abort_on_a_planned_wave_is_a_noop(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo, wave_path = _planned(tmp_path, monkeypatch, TWO_LANES)
    planned = wave.load(wave_path)
    before = {path.name: path.read_bytes() for path in _backlog(repo).glob("*.md")}
    assert wave_launch.abort(repo, wave_path) == 0
    now = {path.name: path.read_bytes() for path in _backlog(repo).glob("*.md")}
    assert now == before
    for lane in planned["lanes"]:
        assert not Path(lane["worktree"]).exists()
    assert _git(repo, "branch", "--list", "wave/*").stdout.strip() == ""
    after = wave.load(wave_path)
    assert after["status"] == "aborted"
    assert [
        (each["pid"], each["status"], each["abort_error"]) for each in after["lanes"]
    ] == [(None, "aborted", None), (None, "aborted", None)]


def test_abort_kills_a_group_whose_leader_has_already_exited(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo, wave_path = _launched(tmp_path, monkeypatch, TWO_LANES)
    saved = wave.load(wave_path)
    marker = tmp_path / "child.json"
    leader = subprocess.Popen(
        [sys.executable, "-c", _LEADER_SRC, _CHILD_SRC, str(marker)],
        start_new_session=True,
    )
    try:
        assert leader.wait(30) == 0
        assert _spawned_record(marker)["pid"] != leader.pid
        # the leader is gone and reaped, yet its group lives on in the child
        assert _group_alive(leader.pid)
        saved["lanes"][0]["pid"] = leader.pid
        wave.save(wave_path, saved)
        assert wave_launch.abort(repo, wave_path) == 0
        assert not _group_alive(leader.pid)
        after = wave.load(wave_path)
        assert after["status"] == "aborted"
        lane = after["lanes"][0]
        assert (lane["pid"], lane["status"], lane["abort_error"]) == (
            None,
            "aborted",
            None,
        )
    finally:
        with contextlib.suppress(ProcessLookupError):
            os.killpg(leader.pid, signal.SIGKILL)


def test_abort_leaves_a_lane_whose_group_outlived_sigkill_mid_loop(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo, wave_path = _launched(tmp_path, monkeypatch, TWO_LANES)
    saved = wave.load(wave_path)
    # A group that never dies: `kill_fn` only records, so the real 60s and 10s
    # poll windows both run out and the lane's kill genuinely fails.
    immovable = subprocess.Popen(
        [sys.executable, "-c", "import time; time.sleep(600)"],
        start_new_session=True,
    )
    kills: list[tuple[int, int]] = []
    try:
        saved["lanes"][0].update(pid=immovable.pid, status="running")
        wave.save(wave_path, saved)
        exit_code = wave_launch.abort(
            repo,
            wave_path,
            kill_fn=lambda pgid, sig: kills.append((pgid, sig)),
        )
    finally:
        with contextlib.suppress(ProcessLookupError):
            os.killpg(immovable.pid, signal.SIGKILL)
        immovable.wait(30)
    assert exit_code == 1
    assert kills == [(immovable.pid, signal.SIGTERM), (immovable.pid, signal.SIGKILL)]
    after = wave.load(wave_path)
    assert after["status"] == "abort_failed"
    alive, finished = after["lanes"]
    # a live group's lane must not look inert: its pre-abort pid and status stay
    assert (alive["pid"], alive["status"]) == (immovable.pid, "running")
    assert str(immovable.pid) in (alive["abort_error"] or "")
    assert "survived SIGKILL" in (alive["abort_error"] or "")
    # killing failed, so its files were left alone entirely
    assert Path(alive["worktree"]).exists()
    assert (_backlog(Path(alive["worktree"])) / alive["prds"][0]).exists()
    assert not (_backlog(repo) / alive["prds"][0]).exists()
    # the healthy lane is still finished in the same call
    assert (finished["pid"], finished["status"], finished["abort_error"]) == (
        None,
        "aborted",
        None,
    )
    assert not Path(finished["worktree"]).exists()
    assert _git(repo, "branch", "--list", finished["branch"]).stdout.strip() == ""
    restored = _backlog(repo) / finished["prds"][0]
    assert restored.read_text(encoding="utf-8") == TWO_LANES[finished["prds"][0]]


@pytest.mark.parametrize("status", ["running", "abort_failed"])
def test_plan_refuses_an_abort_failed_wave_like_a_planned_one(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    status: str,
) -> None:
    repo, wave_path = _planned(tmp_path, monkeypatch, TWO_LANES)
    frozen = wave_path.read_bytes()
    refused = wave.plan(repo, wave_path, max_lanes=2)
    assert refused != 0
    assert wave_path.read_bytes() == frozen
    saved = wave.load(wave_path)
    saved["status"] = status
    wave.save(wave_path, saved)
    frozen = wave_path.read_bytes()
    assert wave.plan(repo, wave_path, max_lanes=2) == refused
    assert wave_path.read_bytes() == frozen


# ── the status and abort verbs ───────────────────────────────────────────────


def test_run_status_prints_the_rendered_table(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    repo, wave_path = _planned(tmp_path, monkeypatch, TWO_LANES)
    assert wave_cli.run(_parse(["wave", "status"]), repo, wave_path) == 0
    printed = capsys.readouterr().out
    assert printed.strip() == wave_launch.status(repo, wave.load(wave_path)).strip()
    for lane in wave.load(wave_path)["lanes"]:
        assert lane["name"] in _row(printed, lane["name"])


def test_run_abort_aborts_the_wave_at_the_path_it_was_given(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo, wave_path = _launched(tmp_path, monkeypatch, TWO_LANES)
    lanes = wave.load(wave_path)["lanes"]
    worktrees = [Path(lane["worktree"]) for lane in lanes]
    assert wave_cli.run(_parse(["wave", "abort"]), repo, wave_path) == 0
    assert wave.load(wave_path)["status"] == "aborted"
    assert [each for each in worktrees if each.exists()] == []
    names = sorted(path.name for path in _backlog(repo).glob("*.md"))
    assert names == sorted(TWO_LANES)


def test_run_still_plans_a_wave_after_the_new_verbs(
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
