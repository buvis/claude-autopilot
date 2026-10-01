#!/usr/bin/env python3
"""Tests for what the wave verbs refuse: a checkout a live loop already owns, and
the bad input a CLI must report instead of traceback (PRD 00214).

Split off `test_wave_launch.py` to keep that file under the 800-line style limit;
launch's own proofs stayed there. Every proof runs against a throwaway
`git init` repo under `tmp_path`, never this checkout's own backlog or
`docs/dev/project-management/autopilot/wave.json`, and no real loop is ever started: the incumbent
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


# One file under each store root, so no literal path can be special-cased.
STORE_FILES = (
    "docs/dev/project-management/decisions/0001-store.md",
    "docs/dev/tmp/0001-store.md",
)
# Foreign look-alikes: the store file's basename elsewhere, a repo-root `docs/`
# file, and a sibling directory whose name only starts like the store's.
LOOKALIKES = (
    "decisions/0001-store.md",
    "docs/guide.md",
    "docs/dev/project-management-old/x.md",
)
# Each kind of foreign dirt that must still refuse beside store churn.
FOREIGN_CASES = [
    "readme_edited",
    "same_basename",
    "docs_root",
    "near_miss_dir",
    "renamed_out_of_store",
    "untracked",
]


def _track_store_file(repo: Path) -> None:
    """Commit the store files and look-alikes past `_repo`'s `.gitignore`, so a
    later edit to any of them shows in `git status --porcelain`."""
    for rel in (*STORE_FILES, *LOOKALIKES):
        (repo / rel).parent.mkdir(parents=True, exist_ok=True)
        (repo / rel).write_text("decided\n", encoding="utf-8")
    _git(repo, "add", "-f", "--", *STORE_FILES, *LOOKALIKES)
    _git(repo, "commit", "-qm", "track store files and look-alikes")


def _append(repo: Path, rel: str) -> None:
    with (repo / rel).open("a", encoding="utf-8") as tracked:
        tracked.write("revised\n")


def _dirty_store_only(repo: Path) -> None:
    """Edit both tracked store files and prove they are the tree's ONLY dirty
    paths, so a refusal-free result can only come from store churn being ignored."""
    for rel in STORE_FILES:
        _append(repo, rel)
    porcelain = _git(repo, "status", "--porcelain", "--untracked-files=all").stdout
    assert sorted(porcelain.splitlines()) == [f" M {rel}" for rel in STORE_FILES]


def _dirty_store_and_foreign(repo: Path, case: str) -> str:
    """Store churn plus one foreign change of kind `case`; the foreign path."""
    _dirty_store_only(repo)
    if case == "renamed_out_of_store":
        # Destination inside the store, source outside: the source is foreign.
        _git(repo, "mv", "README.md", "docs/dev/project-management/x.md")
        return "README.md"
    if case == "untracked":
        (repo / "stray.py").write_text("x = 1\n", encoding="utf-8")
        return "stray.py"
    rel = {
        "readme_edited": "README.md",
        "same_basename": LOOKALIKES[0],
        "docs_root": LOOKALIKES[1],
        "near_miss_dir": LOOKALIKES[2],
    }[case]
    _append(repo, rel)
    return rel


def test_launch_ignores_a_tree_dirty_only_inside_the_store(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    repo, wave_path = _planned(tmp_path, monkeypatch, ONE_LANE, max_lanes=1)
    _track_store_file(repo)
    _dirty_store_only(repo)
    capsys.readouterr()  # the plan listing, not launch's output
    spawn = _FakeSpawn()
    assert wave_launch.launch(repo, wave_path, spawn_fn=spawn) == 0
    err = capsys.readouterr().err
    assert "dirty tree" not in err, err
    assert len(spawn.calls) == 1, spawn.calls


@pytest.mark.parametrize("case", FOREIGN_CASES)
def test_launch_refuses_foreign_dirt_beside_dirt_inside_the_store(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    case: str,
) -> None:
    repo, wave_path = _planned(tmp_path, monkeypatch, ONE_LANE, max_lanes=1)
    _track_store_file(repo)
    _dirty_store_and_foreign(repo, case)
    capsys.readouterr()  # the plan listing, not launch's output
    spawn = _FakeSpawn()
    assert wave_launch.launch(repo, wave_path, spawn_fn=spawn) == 1
    assert "dirty tree" in capsys.readouterr().err
    assert spawn.calls == []
    assert wave.load(wave_path)["status"] == "planned"


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
        "docs/dev/project-management/autopilot/lanes/state.json",
        "docs/dev/project-management/autopilot-old/state.json",
        # Parent directory NAMED `autopilot` but at the wrong depth entirely, so
        # checking the parent's name alone waves it through and derives a repo
        # root a directory off - the same silent wrong-root failure.
        "work/autopilot/state.json",
        # The canonical DIRECTORY under the wrong FILENAME: checking the directory
        # alone accepts it and derives a repo root from a file that is not the
        # state file at all. The `.bak` suffix also catches a check that merely
        # looks for `state.json` somewhere inside the basename.
        "docs/dev/project-management/autopilot/state.json.bak",
        # Four more wrong FILENAMES in that same directory, each one outside any
        # suffix blacklist: the wave's OWN file, which sits right there; a suffix a
        # blacklist of `.bak` misses; no extension at all; and the same name under a
        # different case, which is a different file to a case-sensitive checkout.
        # Together they leave only a positive `name == "state.json"` check passing.
        "docs/dev/project-management/autopilot/wave.json",
        "docs/dev/project-management/autopilot/state.json.tmp",
        "docs/dev/project-management/autopilot/state",
        "docs/dev/project-management/autopilot/State.json",
    ],
)
def test_the_cli_reports_a_non_canonical_state_path_instead_of_asserting(
    tmp_path: Path,
    relative: str,
) -> None:
    repo, wave_path = _repo(tmp_path, ONE_LANE)
    stray = repo / relative  # not <repo>/docs/dev/project-management/autopilot/state.json
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
