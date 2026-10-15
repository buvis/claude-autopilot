#!/usr/bin/env python3
"""Tests for cli/enter.py - catchup stays a delta when the only commits past
`catchup_head_sha` are the loop's own, plus the real `git rev-parse HEAD` read.
Split from test_enter_decisions.py for size; shares its Env harness.
"""

from __future__ import annotations

import json
import os
import shlex
import signal
import subprocess
import sys
import time
from pathlib import Path

import pytest

from cli import enter, enter_io, notify_out
from cli.enter_harness import (
    LOOP,
    NOW,
    PRD,
    STALE,
    Env,
    _cache,
    _loop_repo,
    _open_state,
    _prd_text,
)


@pytest.fixture
def env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Env:
    monkeypatch.setattr(notify_out, "notify", lambda *a, **k: None)
    monkeypatch.delenv("_AUTOPILOT_LANES", raising=False)
    return Env(tmp_path)


# Loop-only commits past `catchup_head_sha` keep the cache: real git repos at
# env.root, committer `autopilot-loop/<batch id>`, author always someone else.
TASKS = [{"id": "t1", "name": "a", "status": "pending"}]


def test_force_is_delta_when_all_commits_are_loop_commits(env: Env) -> None:
    base, head = _loop_repo(env.root, LOOP, LOOP)
    # stale on purpose: a first-entry `force` never consults freshness
    batch = _cache(catchup_head_sha=base, catchup_completed_at=STALE)
    env.write_state(_open_state(batch=batch))
    env.put("wip", PRD, _prd_text(catchup="force"))

    out = env.run()

    assert (out["stop"], out["catchup"]) == (None, "delta")
    assert enter_io.commits_all_loop(env.root, base, LOOP) is True
    assert enter_io.commits_all_loop(env.root, head, "anyone") is True, "empty range"
    calls: list[tuple] = []
    out = env.run(loop_only=lambda *a: calls.append(a) or False)
    assert calls == [(env.root, base, LOOP)]
    assert out["catchup"] == "full", "the decision must follow loop_only's answer"


@pytest.mark.parametrize(
    "foreign",
    ["a human", "autopilot-loop/202609280000", "autopilot-loop/no-batch", LOOP + "0"],
)
def test_force_is_full_when_one_commit_is_not(env: Env, foreign: str) -> None:
    base, _ = _loop_repo(env.root, LOOP, foreign, LOOP)
    env.write_state(_open_state(batch=_cache(catchup_head_sha=base)))
    env.put("wip", PRD, _prd_text(catchup="force"))

    out = env.run()

    assert (out["stop"], out["catchup"]) == (None, "full")
    assert enter_io.commits_all_loop(env.root, base, LOOP) is False


@pytest.mark.parametrize("repo", ["not-a-repo", "unknown-sha", "undecodable-committer"])
def test_force_is_full_on_git_failure(env: Env, repo: str) -> None:
    sha = "d" * 40
    if repo == "unknown-sha":
        _loop_repo(env.root, LOOP)
    elif repo == "undecodable-committer":
        sha, _ = _loop_repo(env.root, LOOP.encode() + b"\xff")
    env.write_state(_open_state(batch=_cache(catchup_head_sha=sha)))
    env.put("wip", PRD, _prd_text(catchup="force"))

    out = env.run()

    assert (out["stop"], out["catchup"]) == (None, "full")
    assert enter_io.commits_all_loop(env.root, sha, LOOP) is False
    # a lossy decode would turn the \xff into U+FFFD and match this name
    assert enter_io.commits_all_loop(env.root, sha, LOOP + "�") is False


@pytest.mark.parametrize("mode", [None, "force"], ids=["run", "force-with-tasks"])
def test_resume_is_delta_when_head_moved_by_loop_commits_only(
    env: Env, mode: str | None
) -> None:
    base, head = _loop_repo(env.root, LOOP, LOOP)
    env.put("wip", PRD, _prd_text(**({"catchup": mode} if mode else {})))
    for batch, seen, expected in (
        (_cache(catchup_head_sha=base), head, "delta"),
        (_cache(catchup_head_sha=base, catchup_completed_at=STALE), head, "full"),
        (_cache(catchup_head_sha=base), None, "full"),
    ):
        env.write_state(_open_state(batch=batch, tasks=TASKS))
        env.head = seen

        out = env.run()

        assert (out["stop"], out["catchup"]) == (None, expected), (batch, seen)


@pytest.mark.parametrize("mode", [None, "force"], ids=["run", "force-with-tasks"])
def test_resume_is_full_when_head_moved_by_a_foreign_commit(
    env: Env, mode: str | None
) -> None:
    base, head = _loop_repo(env.root, LOOP, "a human")
    env.write_state(_open_state(batch=_cache(catchup_head_sha=base), tasks=TASKS))
    env.put("wip", PRD, _prd_text(**({"catchup": mode} if mode else {})))
    env.head = head

    out = env.run()

    assert (out["stop"], out["catchup"]) == (None, "full")


def test_force_is_full_when_every_commit_is_one_foreign_committer(env: Env) -> None:
    # one distinct committer and an even count: neither may pass for loop-only
    base, _ = _loop_repo(env.root, "a human", "a human")
    env.write_state(_open_state(batch=_cache(catchup_head_sha=base)))
    env.put("wip", PRD, _prd_text(catchup="force"))

    out = env.run()

    assert (out["stop"], out["catchup"]) == (None, "full")
    assert enter_io.commits_all_loop(env.root, base, LOOP) is False


def test_force_is_delta_for_a_single_loop_commit(env: Env) -> None:
    # an odd-length range: a commit-count rule cannot stand in for the names
    base, _ = _loop_repo(env.root, LOOP)
    env.write_state(_open_state(batch=_cache(catchup_head_sha=base)))
    env.put("wip", PRD, _prd_text(catchup="force"))

    out = env.run()

    assert (out["stop"], out["catchup"]) == (None, "delta")
    assert enter_io.commits_all_loop(env.root, base, LOOP) is True


@pytest.mark.parametrize(
    ("merge", "expected"),
    [(("a human", LOOP), "full"), ((LOOP, "a human"), "full"), ((LOOP, LOOP), "delta")],
    ids=["foreign-side-commit", "foreign-merge-commit", "all-loop-merge"],
)
def test_force_is_delta_or_full_by_every_commit_of_a_merge(
    env: Env, merge: tuple[str, str], expected: str
) -> None:
    # `--first-parent` misses the side commit, `--no-merges` the merge itself
    base, _ = _loop_repo(env.root, LOOP, merge)
    env.write_state(_open_state(batch=_cache(catchup_head_sha=base)))
    env.put("wip", PRD, _prd_text(catchup="force"))

    out = env.run()

    assert (out["stop"], out["catchup"]) == (None, expected)
    assert enter_io.commits_all_loop(env.root, base, LOOP) is (expected == "delta")


OTHER_BATCH = "202610010000"


@pytest.mark.parametrize(
    ("committer", "expected"),
    [(f"autopilot-loop/{OTHER_BATCH}", "delta"), (LOOP, "full")],
    ids=["this-batch-loop", "another-batch-loop"],
)
def test_force_is_full_unless_the_commits_carry_this_batch_id(
    env: Env, committer: str, expected: str
) -> None:
    # every other case runs under BATCH_ID, so a hardcoded name would pass them
    base, _ = _loop_repo(env.root, committer, committer)
    env.write_state(_open_state(batch=_cache(id=OTHER_BATCH, catchup_head_sha=base)))
    env.put("wip", PRD, _prd_text(catchup="force"))

    out = env.run()

    assert (out["stop"], out["catchup"]) == (None, expected)
    calls: list[tuple] = []
    out = env.run(loop_only=lambda *a: calls.append(a) or True)
    assert calls == [(env.root, base, enter_io.loop_committer(OTHER_BATCH))]
    assert out["catchup"] == "delta"


@pytest.mark.parametrize("mode", [None, "force"], ids=["run", "force-with-tasks"])
@pytest.mark.parametrize(
    ("committer", "answer", "expected"),
    [(LOOP, False, "full"), ("a human", True, "delta")],
    ids=["loop-repo-fake-says-no", "foreign-repo-fake-says-yes"],
)
def test_resume_is_delta_only_when_the_injected_loop_only_says_so(
    env: Env, mode: str | None, committer: str, answer: bool, expected: str
) -> None:
    # The fake contradicts the real repo both ways, so a resume path that calls
    # `enter_io.commits_all_loop` directly gets the opposite answer. It must be
    # handed the cached sha: HEAD would make the range empty, hence vacuous.
    base, head = _loop_repo(env.root, LOOP, committer)
    env.write_state(_open_state(batch=_cache(catchup_head_sha=base), tasks=TASKS))
    env.put("wip", PRD, _prd_text(**({"catchup": mode} if mode else {})))
    env.head = head
    calls: list[tuple] = []

    out = env.run(loop_only=lambda *a: calls.append(a) or answer)

    assert (out["stop"], out["catchup"]) == (None, expected)
    assert calls == [(env.root, base, LOOP)]


def test_catchup_is_full_when_head_is_behind_base(tmp_path: Path) -> None:
    # A reset (or a fast-track park resetting master) can leave HEAD no
    # longer a descendant of the capsule's recorded base. `git log
    # base..HEAD` over that range is empty (vacuously "all loop"), which
    # wrongly reuses a capsule describing commits no longer in history.
    root = tmp_path / "repo"
    root.mkdir()
    base, head = _loop_repo(root, LOOP, LOOP)
    subprocess.run(
        ["git", "-C", str(root), "reset", "--hard", base],
        capture_output=True, check=True, timeout=30,
    )

    assert enter_io.commits_all_loop(root, head, LOOP) is False


def test_force_is_delta_check_is_not_cached_per_root(env: Env) -> None:
    base, _ = _loop_repo(env.root, LOOP, LOOP)

    assert enter_io.commits_all_loop(env.root, base, LOOP) is True
    assert enter_io.commits_all_loop(env.root, base, "a human") is False


@pytest.mark.parametrize("mode", [None, "force"], ids=["run", "force-with-tasks"])
def test_an_empty_catchup_head_sha_is_full_without_consulting_loop_only(
    env: Env, mode: str | None
) -> None:
    # "" is a str, so a type-only guard would let it through and the range
    # f"..HEAD" reads as vacuously all-loop; the guard must check truthiness too.
    env.write_state(_open_state(batch=_cache(catchup_head_sha=""), tasks=TASKS))
    env.put("wip", PRD, _prd_text(**({"catchup": mode} if mode else {})))
    env.head = "c" * 40
    calls: list[tuple] = []

    out = env.run(loop_only=lambda *a: calls.append(a) or True)

    assert (out["stop"], out["catchup"]) == (None, "full")
    assert calls == []


def test_force_with_no_batch_id_checks_the_no_batch_committer(tmp_path: Path) -> None:
    # A batch missing "id" never reaches _catchup through enter() (step 9's
    # _batch_report halts first on a non-str id), so this calls the function
    # directly - the defensive `batch.get("id")` guard is unit-level only.
    root = tmp_path / "root"
    autopilot_dir = root / "autopilot"
    autopilot_dir.mkdir(parents=True)
    base, _ = _loop_repo(root, LOOP)
    calls: list[tuple] = []
    current = {
        "catchup_mode": "force",
        "batch": {"catchup_head_sha": base},
        "tasks": None,
    }

    result = enter._catchup(
        current,
        autopilot_dir / "state.json",
        autopilot_dir,
        now=lambda: NOW,
        git_head=lambda r: None,
        loop_only=lambda *a: calls.append(a) or True,
    )

    assert result == "delta"
    assert calls == [(root, base, enter_io.loop_committer(None))]


# -- step 11: the real `git rev-parse HEAD` read -------------------------------


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess:
    """git against `repo` by path — never a cd, and never the real repo."""
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        check=True,
    )


def test_git_head_sha_reads_the_stripped_head_of_a_real_repo(tmp_path: Path) -> None:
    # The real function, not the injected stand-in every other test passes: a
    # trailing newline here never matches `batch.catchup_head_sha`, so every
    # session would silently take `full` and the delta saving would vanish.
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "--quiet")
    # local identity: the commit must work on a machine with no global one
    _git(repo, "config", "user.email", "test@example.invalid")
    _git(repo, "config", "user.name", "Enter Test")
    _git(repo, "config", "commit.gpgsign", "false")
    (repo / "f.txt").write_text("x\n", encoding="utf-8")
    _git(repo, "add", "f.txt")
    _git(repo, "commit", "--quiet", "-m", "first")
    head = _git(repo, "rev-parse", "HEAD").stdout.strip()

    sha = enter_io.git_head_sha(repo)

    assert sha == head
    assert sha == sha.strip() and "\n" not in sha


def test_git_head_sha_is_none_outside_a_repo(tmp_path: Path) -> None:
    assert enter_io.git_head_sha(tmp_path) is None


# -- registry blind from inside the tree (packet 1): live_wrapper_pid from a
# grandchild -------------------------------------------------------------

_ASK_SCRIPT = (
    "import os, sys, time\n"
    "sys.path.insert(0, sys.argv[4])\n"
    "from pathlib import Path\n"
    "from cli.loop_gates import live_wrapper_pid\n"
    "root, loops_dir, result_file = sys.argv[1], sys.argv[2], sys.argv[3]\n"
    "deadline = time.monotonic() + 5\n"
    "while time.monotonic() < deadline and not list(Path(loops_dir).glob('*.json')):\n"
    "    time.sleep(0.02)\n"
    "found = live_wrapper_pid(Path(root), Path(loops_dir))\n"
    "tmp = result_file + '.tmp'\n"
    "Path(tmp).write_text(str(found))\n"
    "os.replace(tmp, result_file)\n"
)

_M_SCRIPT = (
    "import subprocess, sys, time\n"
    "subprocess.run(sys.argv[1:])\n"
    "time.sleep(60)\n"
)


@pytest.mark.skipif(sys.platform != "darwin", reason="darwin-only pgrep ancestor exclusion")
def test_live_wrapper_pid_found_from_a_grandchild(tmp_path: Path) -> None:
    # macOS pgrep excludes the CALLER's own ancestors from a match by
    # default: a direct child M of the registered wrapper W, tagged via
    # inherited exec env, is invisible to `pgrep -P W` when the process
    # asking is itself a further descendant of M (a grandchild of W) - M is
    # that grandchild's own ancestor. -a is required to see it.
    root = tmp_path / "repo"
    root.mkdir()
    loops = tmp_path / "loops"
    loops.mkdir()
    result_file = tmp_path / "result.txt"
    ask_script = tmp_path / "ask.py"
    m_script = tmp_path / "m.py"
    ask_script.write_text(_ASK_SCRIPT, encoding="utf-8")
    m_script.write_text(_M_SCRIPT, encoding="utf-8")
    cli_parent = str(Path(__file__).resolve().parents[1])

    ask_argv = [
        sys.executable, str(ask_script), str(root), str(loops),
        str(result_file), cli_parent,
    ]
    m_argv = [sys.executable, str(m_script), *ask_argv]
    bash_cmd = (
        "export _AUTOPILOT_LOOP=$$; "
        + " ".join(shlex.quote(a) for a in m_argv)
        + " &\nwait"
    )

    wrapper = subprocess.Popen(["bash", "-c", bash_cmd], start_new_session=True)
    try:
        (loops / f"{wrapper.pid}.json").write_text(
            json.dumps({"pid": wrapper.pid, "root": str(root)}),
        )
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline and not result_file.exists():
            time.sleep(0.05)
        assert result_file.exists(), "grandchild never finished asking"
        assert result_file.read_text() == str(wrapper.pid)
    finally:
        os.killpg(wrapper.pid, signal.SIGKILL)
        wrapper.wait()
