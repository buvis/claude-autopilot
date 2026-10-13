"""Tests for the autopilot-loop committer identity stamped on git commits
made during a loop-driven session.

Covers `enter_io.loop_committer` (the pure string builder) and its effect,
through `Loop._launch`, on the GIT_COMMITTER_NAME seen by the scripted
spawn's `env` dict - plus one integration case proving the mechanism a
real git commit consumes that env var at all.
"""

from __future__ import annotations

import os
import subprocess

from cli import enter_io
from cli.loop_testutil import make_loop, terminal_step, write_state


def test_loop_committer_formats_a_given_batch_id():
    assert enter_io.loop_committer("my-batch-id") == "autopilot-loop/my-batch-id"


def test_loop_committer_falls_back_to_no_batch_for_none():
    assert enter_io.loop_committer(None) == "autopilot-loop/no-batch"


def test_loop_committer_falls_back_to_no_batch_for_empty_string():
    assert enter_io.loop_committer("") == "autopilot-loop/no-batch"


def test_build_launch_stamps_committer_from_state_batch_id(tmp_path):
    lp = make_loop(tmp_path, [terminal_step()])
    write_state(
        lp._test["ap_dir"],
        prd="p.md",
        next_phase="build",
        batch={"id": "20261013-abc"},
    )
    assert lp.run() == 0
    launch = lp._test["spawn"].launches[0]
    assert launch["env"]["GIT_COMMITTER_NAME"] == "autopilot-loop/20261013-abc"


def test_bootstrap_launch_without_batch_stamps_no_batch_committer(tmp_path):
    lp = make_loop(tmp_path, [terminal_step()])
    assert lp.run() == 0
    launch = lp._test["spawn"].launches[0]
    assert launch["env"]["GIT_COMMITTER_NAME"] == "autopilot-loop/no-batch"


def test_git_commit_honors_the_committer_name_env_var(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    subprocess.run(
        ["git", "config", "user.email", "autopilot@example.com"],
        cwd=repo,
        check=True,
    )
    subprocess.run(["git", "config", "user.name", "placeholder"], cwd=repo, check=True)
    (repo / "f.txt").write_text("x\n")
    subprocess.run(["git", "add", "f.txt"], cwd=repo, check=True)
    commit_env = {
        "PATH": os.environ["PATH"],
        "GIT_AUTHOR_NAME": "autopilot-loop/b-1",
        "GIT_AUTHOR_EMAIL": "autopilot@example.com",
        "GIT_COMMITTER_NAME": "autopilot-loop/b-1",
        "GIT_COMMITTER_EMAIL": "autopilot@example.com",
    }
    subprocess.run(
        ["git", "commit", "-q", "-m", "test commit"],
        cwd=repo,
        check=True,
        env=commit_env,
    )
    result = subprocess.run(
        ["git", "log", "-1", "--format=%cn"],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    )
    assert result.stdout.strip() == "autopilot-loop/b-1"
