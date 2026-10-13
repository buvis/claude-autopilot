#!/usr/bin/env python3
"""Tests for cli/verification.py split out of test_verification_dirty.py:
dirty-tree refusal for product edits hidden by the skip-worktree and
assume-unchanged index flags. Split because test_verification_dirty.py
outgrew the 800-line style cap.

The checks run against real temporary git repos: the point is to bind real
git behavior (index flags, dirty tree), not a mock of it.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from cli import verification

STORE = "docs/dev/project-management"
RECORD_REL = Path(STORE) / "autopilot" / "last-verification.json"


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        [
            "git",
            "-c",
            "user.name=t",
            "-c",
            "user.email=t@example.com",
            "-c",
            "commit.gpgsign=false",
            *args,
        ],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _commit(repo: Path, rel: str, body: str = "x\n") -> str:
    path = repo / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body)
    _git(repo, "add", "--", rel)
    _git(repo, "commit", "--no-verify", "-q", "-m", f"touch {rel}")
    return _git(repo, "rev-parse", "HEAD")


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    _git(tmp_path, "init", "-q")
    _commit(tmp_path, "src/app.py", "print(1)\n")
    return tmp_path


HIDDEN_FLAGS = pytest.mark.parametrize(
    "flag",
    ["--skip-worktree", "--assume-unchanged"],
    ids=["skip_worktree", "assume_unchanged"],
)


def _run_passing_gate(cwd: Path, sha: str) -> dict:
    return verification.run_gate("echo 'PASS 1 FAIL 0 SKIP 0 EXIT 0'", cwd, sha, 1)


def _assert_refused(repo: Path, result: dict, dirty_paths: list[str]) -> None:
    # Asserting the exact dirty_paths, not just "dirty is True", is what
    # proves the refusal comes from the hidden-flag scan: a sha that simply
    # does not match HEAD produces the same recorded/dirty shape with
    # dirty_paths == [] (see `_dirty_result([])` in verification.py), so
    # these tests must pass the real HEAD sha or they would pass unchanged
    # with hidden-flag detection disabled entirely.
    assert result["recorded"] is False
    assert result["dirty"] is True
    assert result["dirty_paths"] == dirty_paths
    assert not (repo / RECORD_REL).exists()


def _assert_hidden_flag_only_dirties_outside_the_store(
    repo: Path,
    flag: str,
    not_a_repo: Path,
) -> None:
    # Fail closed: when git cannot answer at all (cwd is no repository), the
    # tree counts as dirty and nothing is recorded. There is no HEAD to pass
    # here, so this one case keeps an arbitrary sha.
    no_git = _run_passing_gate(not_a_repo, "abc")
    _assert_refused(not_a_repo, no_git, [])

    # Control: the flag on a tracked store file, edited under it, is no dirt.
    store_file = f"{STORE}/autopilot/state.json"
    _commit(repo, store_file, "{}\n")
    _git(repo, "update-index", flag, "--", store_file)
    (repo / store_file).write_text('{"edited": true}\n')
    allowed = _run_passing_gate(repo, _git(repo, "rev-parse", "HEAD"))
    assert allowed["passed"] == 1
    assert allowed["recorded"] is True
    assert allowed["dirty"] is False
    assert (repo / RECORD_REL).exists()

    # The same flag on a tracked product file hides its edit from plain
    # status, yet must still refuse the record.
    (repo / RECORD_REL).unlink()
    _git(repo, "update-index", flag, "--", "src/app.py")
    (repo / "src" / "app.py").write_text("print('hidden edit')\n")
    status = _git(repo, "status", "--porcelain=1", "--untracked-files=all")
    assert "src/app.py" not in status
    refused = _run_passing_gate(repo, _git(repo, "rev-parse", "HEAD"))
    _assert_refused(repo, refused, ["src/app.py"])


def test_skip_worktree_edit_blocks_record(repo: Path, tmp_path_factory) -> None:
    _assert_hidden_flag_only_dirties_outside_the_store(
        repo,
        "--skip-worktree",
        tmp_path_factory.mktemp("plain"),
    )


def test_assume_unchanged_edit_blocks_record(repo: Path, tmp_path_factory) -> None:
    _assert_hidden_flag_only_dirties_outside_the_store(
        repo,
        "--assume-unchanged",
        tmp_path_factory.mktemp("plain"),
    )


@HIDDEN_FLAGS
def test_hidden_flag_alone_without_an_edit_is_dirt(repo: Path, flag: str) -> None:
    # The flag alone is dirt even with no edit: it hides the path from
    # plain status, so its on-disk content can never be trusted to still
    # match the index blob without reading it, which the gate does not do.
    _git(repo, "update-index", flag, "--", "src/app.py")
    assert (repo / "src" / "app.py").read_text() == "print(1)\n"

    result = _run_passing_gate(repo, _git(repo, "rev-parse", "HEAD"))

    _assert_refused(repo, result, ["src/app.py"])


@HIDDEN_FLAGS
def test_hidden_flag_same_length_edit_blocks_record(repo: Path, flag: str) -> None:
    # Content, not size, decides: "print(1)" -> "print(2)" keeps the length.
    _git(repo, "update-index", flag, "--", "src/app.py")
    (repo / "src" / "app.py").write_text("print(2)\n")
    assert (repo / "src" / "app.py").stat().st_size == len("print(1)\n")
    assert "src/app.py" not in _git(
        repo,
        "status",
        "--porcelain=1",
        "--untracked-files=all",
    )

    result = _run_passing_gate(repo, _git(repo, "rev-parse", "HEAD"))

    _assert_refused(repo, result, ["src/app.py"])


@HIDDEN_FLAGS
def test_hidden_flag_deleted_product_file_blocks_record(repo: Path, flag: str) -> None:
    # A flagged product file that is gone from disk is an edit too.
    _git(repo, "update-index", flag, "--", "src/app.py")
    (repo / "src" / "app.py").unlink()

    result = _run_passing_gate(repo, _git(repo, "rev-parse", "HEAD"))

    _assert_refused(repo, result, ["src/app.py"])


def test_skip_worktree_and_assume_unchanged_together_edit_blocks_record(
    repo: Path,
) -> None:
    # Both flags on one file give it a tag of its own in `git ls-files -v`;
    # it is still a hidden product edit.
    _git(repo, "update-index", "--skip-worktree", "--", "src/app.py")
    _git(repo, "update-index", "--assume-unchanged", "--", "src/app.py")
    (repo / "src" / "app.py").write_text("print('hidden edit')\n")
    assert "src/app.py" not in _git(
        repo,
        "status",
        "--porcelain=1",
        "--untracked-files=all",
    )

    result = _run_passing_gate(repo, _git(repo, "rev-parse", "HEAD"))

    _assert_refused(repo, result, ["src/app.py"])


@HIDDEN_FLAGS
@pytest.mark.parametrize(
    "rel",
    [
        # Contains "docs/dev" but sits under neither store root.
        "docs/dev-notes/tool.py",
        # Starts with the store prefix's characters but is a sibling dir.
        f"{STORE}-old/x.py",
    ],
)
def test_hidden_flag_edit_near_but_outside_the_store_blocks_record(
    repo: Path,
    flag: str,
    rel: str,
) -> None:
    # The store is matched by directory, not by substring or name stem, for
    # flagged paths as for any other.
    _commit(repo, rel, "x = 1\n")
    _git(repo, "update-index", flag, "--", rel)
    (repo / rel).write_text("x = 'hidden edit'\n")
    assert rel not in _git(repo, "status", "--porcelain=1", "--untracked-files=all")

    result = _run_passing_gate(repo, _git(repo, "rev-parse", "HEAD"))

    _assert_refused(repo, result, [rel])
