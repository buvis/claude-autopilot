#!/usr/bin/env python3
"""Shared test doubles and fixtures for the test_store_tree_*.py modules.

`FakeGit` records every (args, cwd) call and answers from canned stdout, so
no test using it runs real git. `_autopilot_dir`/`_write_state` build a fake
autopilot store's state.json for the CLI- and custody-facing tests.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

REPO = Path("/abs/repo")
SHA = "0123456789abcdef0123456789abcdef01234567"
SUBCOMMANDS = ("add", "diff", "commit", "rev-parse")

GIT = shutil.which("git")


class FakeGit:
    """Records every (args, cwd) call and answers from canned stdout.

    `outputs` maps a git subcommand to its stdout; `fail_on` names one
    subcommand whose call raises `error` instead of answering.
    """

    def __init__(
        self,
        outputs: dict[str, str] | None = None,
        fail_on: str | None = None,
        error: Exception | None = None,
    ) -> None:
        self.outputs = outputs or {}
        self.fail_on = fail_on
        self.error = error
        self.calls: list[tuple[list[str], Path | None]] = []

    def __call__(
        self,
        args: list[str],
        cwd: Path | None = None,
    ) -> subprocess.CompletedProcess:
        self.calls.append((list(args), cwd))
        sub = _subcommand(args)
        if sub is not None and sub == self.fail_on:
            raise self.error
        return subprocess.CompletedProcess(
            ["git", *args],
            0,
            stdout=self.outputs.get(sub, ""),
            stderr="",
        )

    def calls_for(self, sub: str) -> list[list[str]]:
        return [args for args, _ in self.calls if _subcommand(args) == sub]


def _subcommand(args: list[str]) -> str | None:
    for arg in args:
        if arg in SUBCOMMANDS or arg == "status":
            return arg
    return None


def _one_line(text: str) -> bool:
    return len(text.strip("\n").splitlines()) == 1


def _autopilot_dir(root: Path) -> Path:
    path = root / "docs" / "dev" / "project-management" / "autopilot"
    path.mkdir(parents=True)
    return path


def _write_state(autopilot_dir: Path, state: dict) -> Path:
    path = autopilot_dir / "state.json"
    path.write_text(json.dumps(state), encoding="utf-8")
    return path


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
            "GIT_AUTHOR_NAME": "Store Boundary",
            "GIT_AUTHOR_EMAIL": "store@example.invalid",
            "GIT_COMMITTER_NAME": "Store Boundary",
            "GIT_COMMITTER_EMAIL": "store@example.invalid",
            "GIT_TERMINAL_PROMPT": "0",
        },
    )
    return env


class Fixture:
    """A repository whose work-tree root holds the store under `.claude/`."""

    def __init__(self, tmp_path: Path, *, bare: bool) -> None:
        self.env = _clean_git_env(tmp_path)
        self.wt = tmp_path / "worktree"
        self.store = self.wt / ".claude" / "docs" / "dev" / "project-management"
        self.store.mkdir(parents=True)
        self.state = self.store / "autopilot" / "state.json"
        self.state.parent.mkdir(parents=True)
        if bare:
            self.git_dir = tmp_path / "bare.git"
            self.prefix = [f"--git-dir={self.git_dir}", f"--work-tree={self.wt}"]
            self._exec(["init", "--bare", str(self.git_dir)])
        else:
            self.git_dir = self.wt / ".git"
            self.prefix = ["-C", str(self.wt)]
            self._exec(["init", str(self.wt)])
        (self.wt / "outside.txt").write_text("tracked\n", encoding="utf-8")
        (self.store / "notes.md").write_text("one\n", encoding="utf-8")
        self.state.write_text(
            json.dumps({"phase": "build", "repo_root": str(self.wt)}),
            encoding="utf-8",
        )
        self.git("add", "--", "outside.txt", ".claude")
        self.git("commit", "-m", "init")
        self.git("config", "status.showUntrackedFiles", "no")
        self.base_sha = self.git("rev-parse", "HEAD").strip()

    def _exec(self, args: list[str], cwd: Path | None = None):
        return subprocess.run(
            [GIT, *args],
            cwd=str(cwd or self.wt),
            env=self.env,
            check=True,
            capture_output=True,
            text=True,
            timeout=60,
        )

    def git(self, *args: str) -> str:
        return self._exec([*self.prefix, *args]).stdout

    def run_git(self, args: list[str], cwd: Path | None = None):
        assert cwd is not None, (
            f"git must be run inside the work-tree, not the process cwd: {args}"
        )
        return self._exec([*self.prefix, *args], cwd=cwd)

    def dirty_the_tree(self) -> None:
        (self.store / "notes.md").write_text("two\n", encoding="utf-8")
        (self.wt / "outside.txt").write_text("changed\n", encoding="utf-8")
        (self.wt / "untracked-outside.txt").write_text("junk\n", encoding="utf-8")

    def add_sibling_docs(self) -> None:
        sibling = self.wt / "docs" / "dev" / "project-management"
        sibling.mkdir(parents=True)
        (sibling / "sibling.md").write_text("not the store\n", encoding="utf-8")

    def committed_paths(self) -> list[str]:
        return self.git(
            "diff-tree",
            "--no-commit-id",
            "--name-only",
            "-r",
            "HEAD",
        ).split()

    def commit_store_file(self, relpath: str, text: str) -> None:
        path = self.store / relpath
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        self.git("add", "--", str(path.relative_to(self.wt)))
        self.git("commit", "-m", "store change")

    def commit_production_file(self, relpath: str, text: str) -> None:
        path = self.wt / relpath
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        self.git("add", "--", relpath)
        self.git("commit", "-m", "production change")
