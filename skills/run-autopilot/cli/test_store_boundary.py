#!/usr/bin/env python3
"""Tests for store_tree's store boundary: the store prefixes and the recording
pathspec follow the store directory instead of assuming the store sits directly
under git's work-tree root, the status probe stops overriding the repository's
own `status.showUntrackedFiles`, and a failing probe surfaces as
`StoreGitError` rather than a raw subprocess traceback.

A new file rather than an addition to test_store_tree.py, which is at its size
ceiling. Written from the design contract only.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from cli import __main__ as cli_main
from cli import store_tree

GIT = shutil.which("git")
needs_git = pytest.mark.skipif(GIT is None, reason="no git binary on PATH")

NESTED = ".claude/docs/dev/project-management"


def _run(argv: list[str]) -> int:
    try:
        return cli_main.main(argv)
    except SystemExit as exc:
        return exc.code


def _porcelain(*entries: str) -> str:
    """`git status --porcelain -z` stdout for the given `XY path` entries."""
    return "".join(entry + "\0" for entry in entries)


class FakeGit:
    """A `run_git` stand-in. Replies are returned, or raised, in order."""

    def __init__(self, replies: list) -> None:
        self.replies = list(replies)
        self.calls: list[list[str]] = []

    def __call__(self, args: list[str], cwd: Path | None = None):
        self.calls.append(list(args))
        reply = self.replies.pop(0) if self.replies else ""
        if isinstance(reply, BaseException):
            raise reply
        return subprocess.CompletedProcess(
            args=["git", *args],
            returncode=0,
            stdout=reply,
            stderr="",
        )

    @property
    def pathspecs(self) -> set[str]:
        """Every `:(top)...` pathspec the caller handed to git."""
        return {a for call in self.calls for a in call if a.startswith(":(top)")}


def _worktree(tmp_path: Path) -> Path:
    root = tmp_path / "worktree"
    root.mkdir()
    return root


# --------------------------------------------------------------------------
# constants
# --------------------------------------------------------------------------


def test_the_store_roots_are_published_relative_to_a_project_root() -> None:
    assert store_tree.STORE_PREFIXES == (
        "docs/dev/project-management/",
        "docs/dev/tmp/",
    )
    assert store_tree.STORE_SUBDIR == "docs/dev/project-management"
    assert store_tree.STORE_PATHSPEC == ":(top)docs/dev/project-management"
    assert issubclass(store_tree.StoreGitError, RuntimeError)


# --------------------------------------------------------------------------
# prefix derivation
# --------------------------------------------------------------------------


def test_foreign_dirty_shifts_every_store_prefix_under_a_nested_store_dir(
    tmp_path: Path,
) -> None:
    repo = _worktree(tmp_path)
    store_dir = repo / NESTED
    store_dir.mkdir(parents=True)
    git = FakeGit(
        [
            _porcelain(
                f" M {NESTED}/autopilot/state.json",
                " M .claude/docs/dev/tmp/scratch.md",
                " M .config/foo",
                " M docs/dev/tmp/x",
                " M docs/dev/project-management/old.md",
            ),
        ],
    )

    out = store_tree.foreign_dirty(repo, store_dir=store_dir, run_git=git)

    assert sorted(out) == [
        ".config/foo",
        "docs/dev/project-management/old.md",
        "docs/dev/tmp/x",
    ]
    assert git.calls == [["status", "--porcelain", "-z"]], (
        "the repository's own status.showUntrackedFiles must be honoured"
    )


@pytest.mark.parametrize(
    "store_rel",
    [
        None,
        "docs/dev/project-management",
        ".claude/store",
        "../outside/docs/dev/project-management",
    ],
    ids=["default-none", "directly-under-repo", "wrong-tail", "outside-the-repo"],
)
def test_foreign_dirty_falls_back_to_the_unprefixed_store_roots(
    tmp_path: Path,
    store_rel: str | None,
) -> None:
    repo = _worktree(tmp_path)
    (repo / "docs" / "dev" / "project-management").mkdir(parents=True)
    store_dir = None if store_rel is None else repo / store_rel
    if store_dir is not None:
        store_dir.mkdir(parents=True, exist_ok=True)
    git = FakeGit(
        [
            _porcelain(
                " M docs/dev/project-management/autopilot/state.json",
                " M docs/dev/tmp/scratch.md",
                f" M {NESTED}/notes.md",
                " M outside.txt",
            ),
        ],
    )

    out = store_tree.foreign_dirty(repo, store_dir=store_dir, run_git=git)

    assert sorted(out) == [f"{NESTED}/notes.md", "outside.txt"], (
        "a store_dir it cannot place must not be guessed at"
    )
    assert git.calls == [["status", "--porcelain", "-z"]]


# --------------------------------------------------------------------------
# collapsed untracked directories
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("prefix", "collapsed"),
    [("", "docs/"), (".claude/", ".claude/")],
    ids=["store-under-the-repo", "store-under-a-dot-dir"],
)
def test_foreign_dirty_expands_a_collapsed_ancestor_and_keeps_only_non_store_paths(
    tmp_path: Path,
    prefix: str,
    collapsed: str,
) -> None:
    repo = _worktree(tmp_path)
    store_dir = repo / prefix / "docs/dev/project-management"
    store_dir.mkdir(parents=True)
    git = FakeGit(
        [
            _porcelain(f"?? {collapsed}"),
            _porcelain(
                f"?? {prefix}docs/dev/project-management/autopilot/state.json",
                f"?? {prefix}docs/dev/tmp/scratch.md",
                f"?? {prefix}docs/other.md",
            ),
        ],
    )

    out = store_tree.foreign_dirty(repo, store_dir=store_dir, run_git=git)

    assert out == [f"{prefix}docs/other.md"]
    assert git.calls[0] == ["status", "--porcelain", "-z"]
    assert len(git.calls) == 2, git.calls
    assert git.calls[1][:5] == [
        "status",
        "--porcelain",
        "-z",
        "--untracked-files=all",
        "--",
    ]
    assert git.calls[1][5].rstrip("/") == collapsed.rstrip("/")
    assert len(git.calls[1]) == 6, "one scoped call for the one collapsed entry"


@pytest.mark.parametrize(
    ("entry", "expected"),
    [
        ("?? docs/dev/project-management/autopilot/", []),
        ("?? docs/dev/tmp/", []),
        ("?? vendor/", ["vendor"]),
    ],
    ids=["inside-the-store", "inside-the-tmp-store", "unrelated-directory"],
)
def test_foreign_dirty_classifies_a_non_ancestor_directory_without_a_second_probe(
    tmp_path: Path,
    entry: str,
    expected: list[str],
) -> None:
    repo = _worktree(tmp_path)
    git = FakeGit([_porcelain(entry)])

    out = store_tree.foreign_dirty(repo, run_git=git)

    assert [path.rstrip("/") for path in out] == expected
    assert len(git.calls) == 1, git.calls


# --------------------------------------------------------------------------
# failing probes
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("boom", "fragments"),
    [
        (
            subprocess.CalledProcessError(
                128,
                ["git", "status"],
                stderr="fatal: not a git repository",
            ),
            ("128", "not a git repository"),
        ),
        (subprocess.TimeoutExpired(["git", "status"], 30), ("30", "timed out")),
        (
            OSError(2, "No such file or directory: 'git'"),
            ("No such file or directory", "Errno 2"),
        ),
    ],
    ids=["called-process-error", "timeout", "os-error"],
)
def test_foreign_dirty_converts_a_failing_status_probe_into_a_store_git_error(
    tmp_path: Path,
    boom: BaseException,
    fragments: tuple[str, ...],
) -> None:
    git = FakeGit([boom])

    with pytest.raises(store_tree.StoreGitError) as caught:
        store_tree.foreign_dirty(_worktree(tmp_path), run_git=git)

    message = str(caught.value)
    assert any(fragment in message for fragment in fragments), message


def test_foreign_dirty_converts_a_failing_expansion_probe_into_a_store_git_error(
    tmp_path: Path,
) -> None:
    git = FakeGit(
        [
            _porcelain("?? docs/"),
            subprocess.TimeoutExpired(["git", "status"], 30),
        ],
    )

    with pytest.raises(store_tree.StoreGitError):
        store_tree.foreign_dirty(_worktree(tmp_path), run_git=git)

    assert len(git.calls) == 2, git.calls


# --------------------------------------------------------------------------
# record_store's derived pathspec
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("store_rel", "expected"),
    [
        (None, ":(top)docs/dev/project-management"),
        (NESTED, f":(top){NESTED}"),
        (".claude/store", ":(top)docs/dev/project-management"),
    ],
    ids=["default-none", "nested-store", "wrong-tail-falls-back"],
)
def test_record_store_targets_the_pathspec_derived_from_the_store_dir(
    tmp_path: Path,
    store_rel: str | None,
    expected: str,
) -> None:
    repo = _worktree(tmp_path)
    (repo / "docs" / "dev" / "project-management").mkdir(parents=True)
    store_dir = None if store_rel is None else repo / store_rel
    if store_dir is not None:
        store_dir.mkdir(parents=True, exist_ok=True)
    git = FakeGit(
        ["M\tnotes.md\n" if index % 2 else "0" * 40 + "\n" for index in range(12)],
    )

    store_tree.record_store(repo, "handoff", "00236", store_dir, run_git=git)

    assert git.pathspecs == {expected}, git.calls


@pytest.mark.parametrize(
    "boom",
    [
        subprocess.CalledProcessError(
            1,
            ["git", "add"],
            stderr="fatal: pathspec did not match\nsecond line\n",
        ),
        subprocess.TimeoutExpired(["git", "add"], 30),
        OSError(2, "No such file or directory: 'git'"),
    ],
    ids=["called-process-error", "timeout", "os-error"],
)
def test_record_store_swallows_a_git_failure_instead_of_raising(
    tmp_path: Path,
    boom: BaseException,
) -> None:
    repo = _worktree(tmp_path)
    (repo / "docs" / "dev" / "project-management").mkdir(parents=True)
    git = FakeGit([boom])

    assert store_tree.record_store(repo, "handoff", "00236", None, run_git=git) is None


# --------------------------------------------------------------------------
# real git: a bare-backed project whose store sits under a dot-directory
# --------------------------------------------------------------------------


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


@pytest.fixture
def bare_repo(tmp_path: Path) -> Fixture:
    return Fixture(tmp_path, bare=True)


@pytest.fixture
def plain_repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Fixture:
    fixture = Fixture(tmp_path, bare=False)
    for key in [k for k in os.environ if k.startswith("GIT_")]:
        monkeypatch.delenv(key, raising=False)
    for key, value in fixture.env.items():
        if key.startswith("GIT_"):
            monkeypatch.setenv(key, value)
    return fixture


@needs_git
def test_foreign_dirty_reports_only_the_change_outside_a_bare_backed_nested_store(
    bare_repo: Fixture,
) -> None:
    bare_repo.dirty_the_tree()
    control = bare_repo.git("status", "--porcelain")
    assert "untracked-outside.txt" not in control, (
        "the fixture must really carry status.showUntrackedFiles=no"
    )

    out = store_tree.foreign_dirty(
        bare_repo.wt,
        store_dir=bare_repo.store,
        run_git=bare_repo.run_git,
    )

    assert out == ["outside.txt"], out


@needs_git
def test_record_store_commits_the_nested_store_and_not_a_sibling_docs_tree(
    bare_repo: Fixture,
) -> None:
    (bare_repo.store / "notes.md").write_text("two\n", encoding="utf-8")
    bare_repo.add_sibling_docs()

    sha = store_tree.record_store(
        bare_repo.wt,
        "handoff",
        "00236",
        bare_repo.store,
        run_git=bare_repo.run_git,
    )

    assert sha, "a store change must produce a commit"
    head = bare_repo.git("rev-parse", "HEAD").strip()
    assert head.startswith(sha.strip()), (sha, head)
    assert bare_repo.committed_paths() == [f"{NESTED}/notes.md"]


# --------------------------------------------------------------------------
# real git: the CLI derives the store dir from --state
# --------------------------------------------------------------------------


@needs_git
def test_cli_dirty_accepts_churn_in_a_store_below_the_work_tree_root(
    plain_repo: Fixture,
    capsys: pytest.CaptureFixture,
) -> None:
    (plain_repo.store / "notes.md").write_text("two\n", encoding="utf-8")
    (plain_repo.wt / "untracked-outside.txt").write_text("junk\n", encoding="utf-8")

    code = _run(["dirty", "--state", str(plain_repo.state)])

    out = capsys.readouterr().out
    assert code == 0, out
    assert out == "", out


@needs_git
def test_cli_dirty_still_reports_a_change_outside_the_store(
    plain_repo: Fixture,
    capsys: pytest.CaptureFixture,
) -> None:
    (plain_repo.wt / "outside.txt").write_text("changed\n", encoding="utf-8")

    code = _run(["dirty", "--state", str(plain_repo.state)])

    out = capsys.readouterr().out
    assert code == 1, out
    assert out.strip().splitlines() == ["outside.txt"], out


@needs_git
def test_cli_record_store_commits_the_store_the_state_path_points_at(
    plain_repo: Fixture,
    capsys: pytest.CaptureFixture,
) -> None:
    (plain_repo.store / "notes.md").write_text("two\n", encoding="utf-8")
    plain_repo.add_sibling_docs()

    code = _run(
        [
            "record-store",
            "--state",
            str(plain_repo.state),
            "--site",
            "handoff",
            "--prd",
            "00236",
        ],
    )

    out = capsys.readouterr().out.strip()
    assert code == 0, out
    assert plain_repo.committed_paths() == [f"{NESTED}/notes.md"]
    assert out and plain_repo.git("rev-parse", "HEAD").strip().startswith(out)


if __name__ == "__main__":
    unittest.main()
