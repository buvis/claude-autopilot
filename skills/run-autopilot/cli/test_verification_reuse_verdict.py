#!/usr/bin/env python3
"""Tests for cli/verification.py split out of test_verification.py:
reuse_verdict's red-gate refusal and its documented tolerances. Split
because test_verification.py outgrew the 800-line style cap.

The reuse checks run against real temporary git repos: the point is to bind
real git behavior (ancestry, diff paths, dirty tree), not a mock of it.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest

from cli import verification

STORE = "docs/dev/project-management"
GATE = "dev/bin/release-checks"


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


def _record(sha: object, passed=5, failed=0, skipped=1) -> dict:
    return {
        "sha": sha,
        "cycle": 1,
        "writer": "run_gate",
        "commands": [{"command": "dev/bin/release-checks", "exit": 0}],
        "passed": passed,
        "failed": failed,
        "skipped": skipped,
    }


def test_reuse_verdict_refuses_a_record_of_a_failed_gate(repo: Path) -> None:
    # Otherwise fully reusable: ancestor sha, only store paths changed since,
    # clean tree. The gate still never certifies HEAD from a red run.
    base = _git(repo, "rev-parse", "HEAD")
    head = _commit(repo, f"{STORE}/autopilot/state.json", "{}\n")
    green = _record(base)
    assert verification.reuse_verdict(green, repo, head, gate_command=GATE) == ("reused", green)

    nonzero_exit = _record(base)
    nonzero_exit["commands"] = [{"command": "dev/bin/release-checks", "exit": 1}]
    assert verification.reuse_verdict(nonzero_exit, repo, head, gate_command=GATE) == ("stale", {})

    some_failed = _record(base, passed=5, failed=2)
    assert verification.reuse_verdict(some_failed, repo, head, gate_command=GATE) == ("stale", {})


def test_reuse_verdict_refuses_a_non_dict_commands_entry(repo: Path) -> None:
    # reuse_verdict fails toward a rerun and never raises, so a record whose
    # commands hold a non-dict entry is stale, not an AttributeError in the
    # caller.
    base = _git(repo, "rev-parse", "HEAD")
    head = _commit(repo, f"{STORE}/autopilot/state.json", "{}\n")

    a_string = _record(base)
    a_string["commands"] = ["x"]
    assert verification.reuse_verdict(a_string, repo, head, gate_command=GATE) == ("stale", {})

    a_null = _record(base)
    a_null["commands"] = [None]
    assert verification.reuse_verdict(a_null, repo, head, gate_command=GATE) == ("stale", {})


def test_reuse_verdict_refuses_an_empty_commands_list(repo: Path) -> None:
    # run_gate always records one entry, so a record with no recorded exit
    # never certifies a green gate -- it is malformed.
    base = _git(repo, "rev-parse", "HEAD")
    head = _commit(repo, f"{STORE}/autopilot/state.json", "{}\n")

    empty = _record(base)
    empty["commands"] = []
    assert verification.reuse_verdict(empty, repo, head, gate_command=GATE) == ("stale", {})


def test_record_with_nonzero_summary_exit_is_not_reused(repo: Path) -> None:
    # A record whose `commands` entry exited 0 and whose `failed` count is
    # 0, but whose `summary_exit` names the gate's dropped EXIT token (1).
    # Reuse eligibility has to read `summary_exit` itself, not only the
    # already-folded `failed` count: a shape check that forgets the new key
    # would let a record like this -- failed==0, commands all green --
    # certify a gate the EXIT token says was actually red.
    base = _git(repo, "rev-parse", "HEAD")
    head = _commit(repo, f"{STORE}/autopilot/state.json", "{}\n")

    record = _record(base)
    record["summary_exit"] = 1

    assert verification.reuse_verdict(record, repo, head, gate_command=GATE) == (
        "stale",
        {},
    )


def test_reuse_verdict_docstring_states_the_tolerances_it_applies() -> None:
    doc = (verification.reuse_verdict.__doc__ or "").lower()

    # The empty-porcelain claim is gone: no clause pairs the two any more.
    clauses = re.split(r"[.;\n]", doc)
    assert [c for c in clauses if "porcelain" in c and "empty" in c] == []
    # One clause says dirty paths under the store tree are tolerated.
    assert [c for c in clauses if "docs/dev/project-management/" in c and "dirty" in c]
    # One clause says a rename or copy is judged by both of its endpoints.
    assert [
        c
        for c in clauses
        if ("rename" in c or "copy" in c) and ("both" in c or "endpoint" in c)
    ]
