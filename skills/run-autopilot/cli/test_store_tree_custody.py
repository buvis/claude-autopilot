#!/usr/bin/env python3
"""Tests for custody.repo_and_git_dir: resolving the repo root and git dir an
autopilot store's state.json names, falling back to the project root when
the state is missing or unusable.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from cli import custody
from cli.store_tree_testutil import _autopilot_dir, _write_state


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
