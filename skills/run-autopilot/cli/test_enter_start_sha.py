#!/usr/bin/env python3
"""Tests for the work_start_sha stamp `enter()` writes at selection (PRD 00369).

Split out of `test_enter.py`, which is past the 800-line limit. `enter()` runs
in-process with the harness's fake `git rev-parse HEAD`; the git work-tree
probe that decides between the empty-tree sentinel and leaving the field unset
runs real git against the test's own tmp root, so a test that needs an unborn
HEAD initializes that root itself.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from cli import notify_out
from cli.enter_harness import HEAD, Env, _open_state

EMPTY_TREE = "4b825dc642cb6eb9a060e54bf8d69288fbee4904"


@pytest.fixture
def env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Env:
    monkeypatch.setattr(notify_out, "notify", lambda *a, **k: None)
    monkeypatch.delenv("_AUTOPILOT_LANES", raising=False)
    # git must judge the tmp root alone, never a repository above it.
    monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(tmp_path.parent))
    return Env(tmp_path)


def test_enter_stamps_work_start_sha_on_a_fresh_selection(env: Env) -> None:
    env.write_state(_open_state())
    env.put("backlog")
    env.head = HEAD

    out = env.run()

    assert out["stop"] is None
    assert env.read_state()["work_start_sha"] == HEAD


def test_enter_keeps_work_start_sha_on_a_wip_resume(env: Env) -> None:
    env.write_state(_open_state(work_start_sha="abc123"))
    env.put("wip")

    out = env.run()

    assert out["stop"] is None
    assert env.read_state()["work_start_sha"] == "abc123"


def test_enter_stamps_the_empty_tree_sentinel_on_an_unborn_head(env: Env) -> None:
    # An empty template keeps git from writing hooks, which a sandbox may refuse.
    subprocess.run(["git", "init", "-q", "--template=", str(env.root)], check=True)
    env.write_state(_open_state())
    env.put("backlog")
    env.head = None  # `git rev-parse HEAD` fails inside a work tree with no commit

    out = env.run()

    assert out["stop"] is None
    assert env.read_state()["work_start_sha"] == EMPTY_TREE
    assert "empty-tree sentinel stamped" in out["detail"]


def test_enter_leaves_work_start_sha_unset_outside_a_git_work_tree(env: Env) -> None:
    # A bare-repo-backed root such as ~/.claude has no work tree git finds from
    # the root alone. The sentinel there would make the review diff the whole
    # bare-repo tree, so the build session captures the sha instead, in the git
    # context the repo_root step records.
    env.write_state(_open_state())
    env.put("backlog")
    env.head = None

    out = env.run()

    assert out["stop"] is None
    assert "work_start_sha" not in env.read_state()
    assert "sentinel" not in out["detail"]
