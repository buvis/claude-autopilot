#!/usr/bin/env python3
"""Tests for custody.repo_and_git_dir: resolving the repo root and git dir an
autopilot store's state.json names, falling back to the project root when
the state is missing or unusable. Also tests custody.store_git, the shared
git-runner store_git binds to that repo (PRD 00236), and pins that
loop_act.store_git and __main__._store_repo consolidate onto this one
custody.store_git definition with no other `run_git` closure left under
skills/run-autopilot/cli/.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from cli import __main__ as cli_main
from cli import custody, loop_act
from cli.store_tree_testutil import _autopilot_dir, _write_state

needs_git = pytest.mark.skipif(
    shutil.which("git") is None, reason="no git binary on PATH"
)


def test_repo_and_git_dir_reads_repo_root_and_git_dir_from_state(
    tmp_path: Path,
) -> None:
    autopilot_dir = _autopilot_dir(tmp_path)
    repo, git_dir = tmp_path / "work", str(tmp_path / "bare.git")
    _write_state(autopilot_dir, {"repo_root": str(repo), "git_dir": git_dir})

    assert custody.repo_and_git_dir(autopilot_dir) == (repo, git_dir)


def test_repo_and_git_dir_defaults_git_dir_to_none_when_state_omits_it(
    tmp_path: Path,
) -> None:
    autopilot_dir = _autopilot_dir(tmp_path)
    repo = tmp_path / "work"
    _write_state(autopilot_dir, {"repo_root": str(repo)})

    assert custody.repo_and_git_dir(autopilot_dir) == (repo, None)


@pytest.mark.parametrize(
    "state_text",
    [
        None,
        "{not json",
        json.dumps({"git_dir": "/abs/bare.git"}),
        json.dumps({"repo_root": "", "git_dir": "/abs/bare.git"}),
        "[]",
        json.dumps("x"),
        json.dumps({"repo_root": ["x"], "git_dir": "/abs/bare.git"}),
        json.dumps({"repo_root": 5}),
    ],
    ids=[
        "no-state-file",
        "invalid-json",
        "no-repo-root",
        "empty-repo-root",
        "list-body",
        "string-body",
        "list-repo-root",
        "int-repo-root",
    ],
)
def test_repo_and_git_dir_falls_back_to_the_project_root(
    tmp_path: Path,
    state_text: str | None,
) -> None:
    autopilot_dir = _autopilot_dir(tmp_path)
    if state_text is not None:
        (autopilot_dir / "state.json").write_text(state_text, encoding="utf-8")

    result = custody.repo_and_git_dir(autopilot_dir)

    assert result == (custody.project_root(autopilot_dir), None)
    assert result[0] == tmp_path, "the store's four-level parent is the repo"


def test_repo_and_git_dir_falls_back_when_the_state_file_is_unreadable(
    tmp_path: Path,
) -> None:
    autopilot_dir = _autopilot_dir(tmp_path)
    state_path = _write_state(autopilot_dir, {"repo_root": str(tmp_path / "work")})
    state_path.chmod(0)
    try:
        if os.access(state_path, os.R_OK):
            pytest.skip("running with privileges that ignore file modes")
        result = custody.repo_and_git_dir(autopilot_dir)
    finally:
        state_path.chmod(0o600)

    assert result == (custody.project_root(autopilot_dir), None)


def _bare_backed_store(tmp_path: Path) -> tuple[Path, Path, Path]:
    """A state.json naming a bare repo's git_dir and an ordinary (non-git)
    work-tree directory `repo` - the bare-backed-home-repo shape
    custody.store_git resolves. Returns (autopilot_dir, repo, git_dir)."""
    git_dir = tmp_path / "bare.git"
    subprocess.run(["git", "init", "-q", "--bare", str(git_dir)], check=True)
    repo = tmp_path / "work"
    repo.mkdir()
    autopilot_dir = _autopilot_dir(tmp_path)
    _write_state(autopilot_dir, {"repo_root": str(repo), "git_dir": str(git_dir)})
    return autopilot_dir, repo, git_dir


@needs_git
def test_store_git_returns_the_repo_named_in_state(tmp_path: Path) -> None:
    autopilot_dir, repo, _git_dir = _bare_backed_store(tmp_path)

    repo_result, _run_git = custody.store_git(autopilot_dir)

    assert repo_result == repo


@needs_git
def test_store_git_run_git_targets_the_bare_repo_named_in_state(
    tmp_path: Path,
) -> None:
    autopilot_dir, repo, git_dir = _bare_backed_store(tmp_path)
    _repo, run_git = custody.store_git(autopilot_dir)

    result = run_git(["rev-parse", "--git-dir"], repo)

    assert Path(result.stdout.strip()).resolve() == git_dir.resolve()


@needs_git
def test_store_git_run_git_passes_cwd_through_to_anchor_the_pathspec(
    tmp_path: Path,
) -> None:
    autopilot_dir, repo, _git_dir = _bare_backed_store(tmp_path)
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    _repo, run_git = custody.store_git(autopilot_dir)

    result = run_git(["rev-parse", "--show-toplevel"], elsewhere)

    assert Path(result.stdout.strip()).resolve() == repo.resolve()


@needs_git
def test_store_git_run_git_raises_on_a_failing_git_call(tmp_path: Path) -> None:
    autopilot_dir, repo, _git_dir = _bare_backed_store(tmp_path)
    _repo, run_git = custody.store_git(autopilot_dir)

    with pytest.raises(subprocess.CalledProcessError):
        run_git(["rev-parse", "--verify", "nonexistent-ref"], repo)


def test_loop_act_store_git_is_the_same_object_as_custody_store_git() -> None:
    assert loop_act.store_git is custody.store_git


def test_store_repo_delegates_to_custody_store_git(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sentinel_repo = object()
    sentinel_run_git = object()
    calls: list[Path] = []

    def _stub(ap_dir: Path) -> tuple[object, object]:
        calls.append(ap_dir)
        return sentinel_repo, sentinel_run_git

    monkeypatch.setattr(custody, "store_git", _stub)
    autopilot_dir = _autopilot_dir(tmp_path)
    state_path = _write_state(autopilot_dir, {"repo_root": str(tmp_path / "work")})

    repo_result, store_dir_result, run_git_result = cli_main._store_repo(
        str(state_path)
    )

    assert calls == [state_path.parent]
    assert repo_result is sentinel_repo
    assert run_git_result is sentinel_run_git
    assert store_dir_result == state_path.parents[1]


def test_no_cli_module_other_than_custody_defines_its_own_run_git() -> None:
    cli_dir = Path(__file__).resolve().parent
    main_text = (cli_dir / "__main__.py").read_text(encoding="utf-8")
    loop_act_text = (cli_dir / "loop_act.py").read_text(encoding="utf-8")

    assert "def run_git(" not in main_text
    assert "def run_git(" not in loop_act_text
