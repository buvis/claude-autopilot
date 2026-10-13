#!/usr/bin/env python3
"""Tests for cli/verification.py split out of test_verification_dirty.py:
the dirty_paths list every run_gate result carries. Split because
test_verification_dirty.py outgrew the 800-line style cap.

The checks run against real temporary git repos: the point is to bind real
git behavior (status records, renames, deletions), not a mock of it.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from cli import verification

STORE = "docs/dev/project-management"
SUMMARY = "echo 'PASS 1 FAIL 0 SKIP 0 EXIT 0'"


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


def _assert_dirty_paths_agree_with_dirty(result: dict) -> None:
    # dirty_paths is non-empty exactly when the result is dirty; a timed-out
    # run is neither dirty nor lists any path.
    if result["timed_out"]:
        assert result["dirty"] is False
        assert result["dirty_paths"] == []
    else:
        assert bool(result["dirty_paths"]) == result["dirty"]


def test_dirty_result_lists_the_dirty_paths(repo: Path) -> None:
    # Every result carries dirty_paths: [] when clean, the sorted offending
    # paths when a pre-spawn or post-reap check refuses the record.
    clean = verification.run_gate(SUMMARY, repo, "abc", 1)
    assert clean["recorded"] is True
    assert clean["dirty_paths"] == []
    _assert_dirty_paths_agree_with_dirty(clean)

    (repo / "src" / "untracked.py").write_text("print('new')\n")
    (repo / "a-stray.txt").write_text("stray\n")
    pre = verification.run_gate(SUMMARY, repo, "abc", 1)
    assert pre["dirty"] is True
    assert pre["passed"] is None
    assert pre["dirty_paths"] == ["a-stray.txt", "src/untracked.py"]
    _assert_dirty_paths_agree_with_dirty(pre)

    (repo / "src" / "untracked.py").unlink()
    (repo / "a-stray.txt").unlink()
    post = verification.run_gate(f"echo dirty > src/dirty.py; {SUMMARY}", repo, "abc", 1)
    assert post["passed"] == 1
    assert post["dirty"] is True
    assert post["dirty_paths"] == ["src/dirty.py"]
    _assert_dirty_paths_agree_with_dirty(post)

    (repo / "src" / "dirty.py").unlink()
    timed_out = verification.run_gate("sleep 5", repo, "abc", 1, timeout=0.2)
    assert timed_out["timed_out"] is True
    assert timed_out["dirty_paths"] == []
    _assert_dirty_paths_agree_with_dirty(timed_out)


def test_pre_spawn_dirty_paths_list_modified_deleted_nested_and_untracked(
    repo: Path,
) -> None:
    # A different, larger set than the round above: a modified tracked file,
    # a deleted tracked file, a nested untracked file and a top-level one,
    # all outside the store, plus store dirt that must not be listed.
    _commit(repo, "lib/util.py", "def f():\n    return 1\n")
    (repo / "src" / "app.py").write_text("print('modified')\n")
    (repo / "lib" / "util.py").unlink()
    nested = repo / "pkg" / "sub" / "deep.txt"
    nested.parent.mkdir(parents=True)
    nested.write_text("deep\n")
    (repo / "z-top.md").write_text("top\n")
    store_note = repo / STORE / "notes" / "n.md"
    store_note.parent.mkdir(parents=True)
    store_note.write_text("note\n")

    pre = verification.run_gate(SUMMARY, repo, "abc", 1)

    assert pre["dirty"] is True
    assert pre["passed"] is None
    assert pre["recorded"] is False
    assert pre["dirty_paths"] == [
        "lib/util.py",
        "pkg/sub/deep.txt",
        "src/app.py",
        "z-top.md",
    ]
    _assert_dirty_paths_agree_with_dirty(pre)


def test_post_reap_dirty_paths_list_every_path_the_run_dirtied(repo: Path) -> None:
    # Clean at spawn; the command leaves three dirty paths outside the store
    # (one nested), and every one of them must be listed, not a prefix slice.
    command = (
        "mkdir -p out/deep; echo a > out/deep/one.txt; echo b > two.txt; "
        f"echo c > src/three.py; {SUMMARY}"
    )

    post = verification.run_gate(command, repo, "abc", 1)

    assert post["passed"] == 1
    assert post["dirty"] is True
    assert post["recorded"] is False
    assert post["dirty_paths"] == ["out/deep/one.txt", "src/three.py", "two.txt"]
    _assert_dirty_paths_agree_with_dirty(post)


def test_dirty_paths_list_both_endpoints_of_a_staged_rename(repo: Path) -> None:
    # Both endpoints sit outside the store and differ: the rename's source
    # and its destination must each appear, not only the new path.
    (repo / "lib").mkdir()
    _git(repo, "mv", "src/app.py", "lib/renamed.py")

    pre = verification.run_gate(SUMMARY, repo, "abc", 1)

    assert pre["dirty"] is True
    assert pre["passed"] is None
    assert pre["dirty_paths"] == ["lib/renamed.py", "src/app.py"]
    _assert_dirty_paths_agree_with_dirty(pre)


def test_dirty_paths_excuse_the_gates_own_untracked_log(
    repo: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # A user-level ignore rule (a global `*.log`) must not be what hides the
    # log, so git config outside the repo is switched off.
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", "/dev/null")
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    log_path = repo / "logs" / "gate.log"
    assert not log_path.exists()

    clean = verification.run_gate(SUMMARY, repo, "abc", 1, log_path=log_path)

    assert log_path.exists()
    assert _git(repo, "ls-files", "--", "logs/gate.log") == ""
    assert clean["recorded"] is True
    assert clean["dirty"] is False
    assert clean["dirty_paths"] == []
    _assert_dirty_paths_agree_with_dirty(clean)

    # With real dirt beside it, the list names the dirt and still not the log.
    dirty = verification.run_gate(
        f"echo dirty > src/dirty.py; {SUMMARY}",
        repo,
        "abc",
        1,
        log_path=log_path,
    )

    assert dirty["passed"] == 1
    assert dirty["dirty"] is True
    assert dirty["dirty_paths"] == ["src/dirty.py"]
    _assert_dirty_paths_agree_with_dirty(dirty)
