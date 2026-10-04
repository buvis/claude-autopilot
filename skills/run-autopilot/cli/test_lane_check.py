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

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from cli import lane_check

GIT = shutil.which("git")
needs_git = pytest.mark.skipif(GIT is None, reason="no git binary on PATH")


def _clean_git_env(tmp_path: Path) -> dict[str, str]:
    """An environment that never reads the developer's git configuration."""
    config = tmp_path / "gitconfig"
    config.write_text(
        "[init]\n\tdefaultBranch = master\n[commit]\n\tgpgsign = false\n",
        encoding="utf-8",
    )
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    env.update(
        {
            "GIT_CONFIG_GLOBAL": str(config),
            "GIT_CONFIG_SYSTEM": str(tmp_path / "no-system-gitconfig"),
            "GIT_AUTHOR_NAME": "Lane Check",
            "GIT_AUTHOR_EMAIL": "lane-check@example.invalid",
            "GIT_COMMITTER_NAME": "Lane Check",
            "GIT_COMMITTER_EMAIL": "lane-check@example.invalid",
            "GIT_TERMINAL_PROMPT": "0",
        },
    )
    return env


class BareRepo:
    """A bare-backed repository whose work-tree root holds the store under
    `.claude/`, the same layout `~/.claude` carries over `~/.buvis`."""

    def __init__(self, tmp_path: Path) -> None:
        self.env = _clean_git_env(tmp_path)
        self.wt = tmp_path / "worktree"
        self.store = self.wt / ".claude" / "docs" / "dev" / "project-management"
        self.store.mkdir(parents=True)
        self.git_dir = tmp_path / "bare.git"
        self._exec(["init", "--bare", str(self.git_dir)])
        (self.wt / "outside.py").write_text("x = 1\n", encoding="utf-8")
        (self.store / "notes.md").write_text("one\n", encoding="utf-8")
        self._git("add", "--", "outside.py", ".claude")
        self._git("commit", "-m", "init")
        self.base_sha = self._git("rev-parse", "HEAD").strip()

    def _exec(self, args: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess:
        return subprocess.run(
            [GIT, *args],
            cwd=str(cwd or self.wt),
            env=self.env,
            check=True,
            capture_output=True,
            text=True,
            timeout=60,
        )

    def _git(self, *args: str) -> str:
        return self._exec(
            [f"--git-dir={self.git_dir}", f"--work-tree={self.wt}", *args]
        ).stdout

    def commit_store_file(self, relpath: str, text: str) -> None:
        path = self.store / relpath
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        self._git("add", "--", str(path.relative_to(self.wt)))
        self._git("commit", "-m", "store change")

    def commit_production_file(self, relpath: str, text: str) -> None:
        path = self.wt / relpath
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        self._git("add", "--", relpath)
        self._git("commit", "-m", "production change")


@pytest.fixture
def bare_repo(tmp_path: Path) -> BareRepo:
    return BareRepo(tmp_path)


@needs_git
def test_bare_repo_store_commits_are_not_production_paths(bare_repo: BareRepo) -> None:
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
    bare_repo: BareRepo,
) -> None:
    bare_repo.commit_production_file("pkg/mod.py", "x = 2\n")

    signal = lane_check.diff_signal(
        bare_repo.base_sha,
        str(bare_repo.wt),
        str(bare_repo.git_dir),
        bare_repo.store,
    )

    assert signal == "unnamed_path", signal
