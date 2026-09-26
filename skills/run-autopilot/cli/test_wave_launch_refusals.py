#!/usr/bin/env python3
"""Tests for what the wave verbs refuse: a checkout a live loop already owns, and
the bad input a CLI must report instead of traceback (PRD 00214).

Split off `test_wave_launch.py` to keep that file under the 800-line style limit;
launch's own proofs stayed there. Every proof runs against a throwaway
`git init` repo under `tmp_path`, never this checkout's own backlog or
`dev/local/autopilot/wave.json`, and no real loop is ever started: the incumbent
is a tagged stand-in process, and `live_wrapper_pid` is patched to report it.

The git failure is injected the only way the CLI entry point allows - a `git` on
PATH that fails one call and execs the real git for the rest - because
`wave_cli.run` takes no `run_git` seam.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

import pytest

from cli import wave, wave_cli, wave_launch
from cli.loop_testutil import _spawn_tagged_incumbent
from cli.test_wave_launch import (
    CLI_MAIN,
    ONE_LANE,
    TWO_LANES,
    _backlog,
    _FakeSpawn,
    _git,
    _parse,
    _planned,
    _repo,
)
from cli.test_wave_launch_abort import _launched


def _reporting_pid(pid: int, owner: Path) -> Callable[..., int | None]:
    """A `live_wrapper_pid` that reports `pid` for `owner`'s checkout and nothing
    for any other root."""

    def live_wrapper_pid(root: object, *_args: object, **_kw: object) -> int | None:
        return pid if Path(str(root)) == owner else None

    return live_wrapper_pid


def _stub_git(bin_dir: Path, blocked: list[str]) -> None:
    """A `git` on PATH that exits 1 on a call starting with `blocked` - so its
    caller sees a `subprocess.CalledProcessError` - and execs the real git for
    every other call."""
    real = shutil.which("git")
    assert real, "no real git on PATH to delegate to"
    bin_dir.mkdir(exist_ok=True)
    script = bin_dir / "git"
    script.write_text(
        f"#!{sys.executable}\n"
        "import os, sys\n"
        f"blocked = {blocked!r}\n"
        "if sys.argv[1 : 1 + len(blocked)] == blocked:\n"
        "    sys.stderr.write('fatal: stubbed git failure\\n')\n"
        "    raise SystemExit(1)\n"
        f"os.execv({real!r}, [{real!r}, *sys.argv[1:]])\n",
        encoding="utf-8",
    )
    script.chmod(0o755)


def test_launch_refuses_a_checkout_a_live_loop_already_owns(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    # A coverage gap, not a bug: launch already refuses, so this is expected
    # GREEN before and after the fix. `test_lane_roots_are_distinct_registry_roots`
    # covers registry distinctness, which is a different claim.
    repo, wave_path = _planned(tmp_path, monkeypatch, ONE_LANE, max_lanes=1)
    capsys.readouterr()  # the plan listing, not launch's output
    lane = wave.load(wave_path)["lanes"][0]
    incumbent = _spawn_tagged_incumbent()
    spawn = _FakeSpawn()
    try:
        patched = _reporting_pid(incumbent.pid, repo)
        # patched where `wave_launch` looks the helper up: it holds its own
        # binding, so patching `loop_gates`' attribute would not be seen at all
        monkeypatch.setattr(wave_launch, "live_wrapper_pid", patched)
        exit_code = wave_launch.launch(repo, wave_path, spawn_fn=spawn)
    finally:
        incumbent.kill()
        incumbent.wait(10)
    assert exit_code == 1
    printed = capsys.readouterr()
    assert str(incumbent.pid) in printed.err, printed.err
    # Nothing started and nothing moved: no lane spawned, no worktree, no branch,
    # the PRD still in the main backlog and the wave still waiting to be launched.
    assert spawn.calls == []
    assert not Path(lane["worktree"]).exists()
    assert _git(repo, "branch", "--list", lane["branch"]).stdout.strip() == ""
    assert (_backlog(repo) / lane["prds"][0]).exists()
    assert wave.load(wave_path)["status"] == "planned"


@pytest.mark.parametrize(
    "relative",
    [
        # Nowhere near the canonical directory, then two NEAR-MISSES: one a level
        # too deep inside it, one a directory whose name merely starts with it.
        # A substring check on the path waves both near-misses through and then
        # derives a repo root that is off by a directory, in silence.
        "state.json",
        "dev/local/autopilot/lanes/state.json",
        "dev/local/autopilot-old/state.json",
        # Parent directory NAMED `autopilot` but at the wrong depth entirely, so
        # checking the parent's name alone waves it through and derives a repo
        # root a directory off - the same silent wrong-root failure.
        "work/autopilot/state.json",
        # The canonical DIRECTORY under the wrong FILENAME: checking the directory
        # alone accepts it and derives a repo root from a file that is not the
        # state file at all. The `.bak` suffix also catches a check that merely
        # looks for `state.json` somewhere inside the basename.
        "dev/local/autopilot/state.json.bak",
    ],
)
def test_the_cli_reports_a_non_canonical_state_path_instead_of_asserting(
    tmp_path: Path,
    relative: str,
) -> None:
    repo, wave_path = _repo(tmp_path, ONE_LANE)
    stray = repo / relative  # not <repo>/dev/local/autopilot/state.json
    proc = subprocess.run(
        [
            sys.executable,
            str(CLI_MAIN),
            "wave",
            "plan",
            "--max-lanes",
            "1",
            "--state",
            str(stray),
        ],
        capture_output=True,
        text=True,
        cwd=str(tmp_path),
    )
    assert proc.returncode == 1, (proc.returncode, proc.stdout, proc.stderr)
    assert str(stray) in proc.stderr, proc.stderr
    # A reported path, not a crash: under `python -O` a bare `assert` vanishes and
    # the wrong repo root is derived in silence, so this has to be a real check.
    printed = proc.stdout + proc.stderr
    assert "AssertionError" not in printed, printed
    assert "Traceback" not in printed, printed
    # Nothing was planned ANYWHERE: a near-miss path that slips the check plants
    # its wave.json beside itself, not at the canonical `wave_path`.
    assert not wave_path.exists()
    assert sorted(tmp_path.rglob("wave.json")) == []


def test_run_abort_reports_a_failed_worktree_listing_instead_of_raising(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    repo, wave_path = _launched(tmp_path, monkeypatch, TWO_LANES)
    capsys.readouterr()  # the fixture's own plan listing, not the verb's output
    worktrees = [Path(lane["worktree"]) for lane in wave.load(wave_path)["lanes"]]
    # `launch` already ran, so the stub only ever sees abort's own calls, and the
    # context manager takes it back off PATH before the assertions below.
    _stub_git(tmp_path / "bin", ["worktree", "list"])
    with monkeypatch.context() as stubbed:
        stubbed.setenv("PATH", f"{tmp_path / 'bin'}{os.pathsep}{os.environ['PATH']}")
        exit_code = wave_cli.run(_parse(["wave", "abort"]), repo, wave_path)
    assert exit_code == 1
    printed = capsys.readouterr()
    assert "non-zero exit status" in printed.out + printed.err, printed
    # The FAILING CALL is named too, not just "a git call failed": one hardcoded
    # line cannot report which of abort's calls it was. Quoting and commas vary
    # with how the cause is rendered, so they are normalised away first.
    flat = " ".join((printed.out + printed.err).split())
    for noise in ("'", '"', ","):
        flat = flat.replace(noise, "")
    assert "worktree list" in flat, printed
    # The listing is the first git call abort makes, so nothing was cleaned up
    # behind it either.
    assert [each for each in worktrees if not each.exists()] == []
