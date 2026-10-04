#!/usr/bin/env python3
"""Tests for lane_check.diff_signal's store exclusion in a bare-repo-backed
project (PRD 00244 / 00238): the store sits below git's work-tree root (e.g.
`~/.claude`'s `.claude/docs/dev/project-management`), so the exclusion
pathspec must carry the same prefix `store_tree._store_prefix` derives for
`foreign_dirty`/`record_store`, not the bare store-root spelling that only
matches a flat layout.

A new file: `diff_signal` previously had no direct-unit coverage, only the
subprocess-level `test_lane_cli.py` tests, which run a flat (non-bare) repo.
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from cli import lane_check
from cli.store_tree_testutil import Fixture

GIT = shutil.which("git")
needs_git = pytest.mark.skipif(GIT is None, reason="no git binary on PATH")


@pytest.fixture
def bare_repo(tmp_path: Path) -> Fixture:
    return Fixture(tmp_path, bare=True)


@needs_git
def test_bare_repo_store_commits_are_not_production_paths(bare_repo: Fixture) -> None:
    # state.json is not a doc/test/packaging path, so lane.is_production_path
    # would flag it - unless the store exclusion actually reaches it.
    bare_repo.commit_store_file(
        "autopilot/state.json", '{"phase": "build"}\n'
    )

    signal = lane_check.diff_signal(
        bare_repo.base_sha,
        str(bare_repo.wt),
        str(bare_repo.git_dir),
        bare_repo.store,
    )

    assert signal is None, signal


@needs_git
def test_bare_repo_production_path_outside_store_still_escalates(
    bare_repo: Fixture,
) -> None:
    bare_repo.commit_production_file("pkg/mod.py", "x = 2\n")

    signal = lane_check.diff_signal(
        bare_repo.base_sha,
        str(bare_repo.wt),
        str(bare_repo.git_dir),
        bare_repo.store,
    )

    assert signal == "unnamed_path", signal


@needs_git
def test_bare_repo_store_security_keyword_does_not_escalate(bare_repo: Fixture) -> None:
    # The security keyword lives only inside the excluded store, so it must
    # never be read as a production security signal.
    bare_repo.commit_store_file("autopilot/notes.md", 'password = "hunter2"\n')
    bare_repo.commit_production_file("README.md", "# notes\n")

    signal = lane_check.diff_signal(
        bare_repo.base_sha,
        str(bare_repo.wt),
        str(bare_repo.git_dir),
        bare_repo.store,
    )

    assert signal is None, signal
