#!/usr/bin/env python3
"""Tests for cli/verification.py (PRD 00249 task 1).

The reuse checks run against real temporary git repos: the point is to bind
real git behavior (ancestry, diff paths, dirty tree), not a mock of it.
"""

from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path

import pytest

from cli import verification

STORE = "docs/dev/project-management"
RECORD_REL = Path(STORE) / "autopilot" / "last-verification.json"


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        [
            "git",
            "-c", "user.name=t",
            "-c", "user.email=t@example.com",
            "-c", "commit.gpgsign=false",
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
        "commands": [{"command": "dev/bin/release-checks", "exit": 0}],
        "passed": passed,
        "failed": failed,
        "skipped": skipped,
    }


def test_reuse_when_only_store_paths_changed(repo: Path) -> None:
    base = _git(repo, "rev-parse", "HEAD")
    _commit(repo, f"{STORE}/autopilot/state.json", "{}\n")
    head = _commit(repo, f"{STORE}/reviews/r1.md", "review\n")
    record = _record(base)

    assert verification.reuse_verdict(record, repo, head) == ("reused", record)
    # An empty diff (record at HEAD itself) is vacuously store-only.
    same = _record(head)
    assert verification.reuse_verdict(same, repo, head) == ("reused", same)


def test_stale_when_code_changed(repo: Path) -> None:
    base = _git(repo, "rev-parse", "HEAD")
    _commit(repo, f"{STORE}/autopilot/state.json", "{}\n")
    head = _commit(repo, "src/app.py", "print(2)\n")

    assert verification.reuse_verdict(_record(base), repo, head) == ("stale", {})


@pytest.mark.parametrize("field", ["passed", "failed", "skipped"])
def test_stale_when_counts_null(repo: Path, field: str) -> None:
    head = _git(repo, "rev-parse", "HEAD")
    nulled = _record(head)
    nulled[field] = None
    missing = _record(head)
    del missing[field]

    assert verification.reuse_verdict(nulled, repo, head) == ("stale", {})
    assert verification.reuse_verdict(missing, repo, head) == ("stale", {})


def test_reuse_verdict_fails_closed_on_git_error(repo: Path, tmp_path_factory) -> None:
    head = _git(repo, "rev-parse", "HEAD")
    not_a_repo = tmp_path_factory.mktemp("plain")

    assert verification.reuse_verdict(None, repo, head) == ("stale", {})
    assert verification.reuse_verdict(_record(""), repo, head) == ("stale", {})
    no_sha = _record(head)
    del no_sha["sha"]
    assert verification.reuse_verdict(no_sha, repo, head) == ("stale", {})
    assert verification.reuse_verdict(_record(123), repo, head) == ("stale", {})
    unknown = _record("0123456789abcdef0123456789abcdef01234567")
    assert verification.reuse_verdict(unknown, repo, head) == ("stale", {})
    assert verification.reuse_verdict(_record("no-such-ref"), repo, head) == ("stale", {})
    assert verification.reuse_verdict(_record(head), not_a_repo, head) == ("stale", {})


def test_reuse_verdict_rejects_non_ancestor_sha(repo: Path) -> None:
    root = _git(repo, "rev-parse", "HEAD")
    _git(repo, "checkout", "-q", "-b", "side")
    sibling = _commit(repo, f"{STORE}/notes/side.md", "side\n")
    _git(repo, "checkout", "-q", "-")
    head = _commit(repo, f"{STORE}/notes/main.md", "main\n")

    # Sibling commit (survived a reset/rebase): not an ancestor of HEAD.
    assert verification.reuse_verdict(_record(sibling), repo, head) == ("stale", {})
    # Descendant: record newer than the HEAD being checked.
    assert verification.reuse_verdict(_record(head), repo, root) == ("stale", {})


def test_reuse_verdict_rejects_dirty_tree(repo: Path) -> None:
    head = _git(repo, "rev-parse", "HEAD")
    record = _record(head)
    assert verification.reuse_verdict(record, repo, head) == ("reused", record)

    (repo / "src" / "app.py").write_text("print('dirty')\n")
    assert verification.reuse_verdict(record, repo, head) == ("stale", {})

    _git(repo, "checkout", "--", "src/app.py")
    (repo / "src" / "new.py").write_text("untracked\n")
    assert verification.reuse_verdict(record, repo, head) == ("stale", {})


def test_reuse_verdict_ignores_dirty_paths_under_the_store(repo: Path) -> None:
    head = _git(repo, "rev-parse", "HEAD")
    store_dir = repo / STORE / "autopilot"
    store_dir.mkdir(parents=True)
    tracked = store_dir / "state.json"
    tracked.write_text("{}\n")
    _git(repo, "add", "--", f"{STORE}/autopilot/state.json")
    _git(repo, "commit", "--no-verify", "-q", "-m", "add store file")
    head = _git(repo, "rev-parse", "HEAD")
    record = _record(head)
    assert verification.reuse_verdict(record, repo, head) == ("reused", record)

    # Dirty a tracked store file and add an untracked one: both ignored.
    tracked.write_text("{\"dirty\": true}\n")
    (store_dir / "dispatch-metrics.jsonl").write_text("{}\n")
    assert verification.reuse_verdict(record, repo, head) == ("reused", record)

    # A non-store path dirty at the same time still makes the record stale.
    (repo / "src" / "app.py").write_text("print('dirty')\n")
    assert verification.reuse_verdict(record, repo, head) == ("stale", {})


def test_run_gate_prints_one_summary_line(tmp_path: Path) -> None:
    command = (
        "printf 'PASS 1 FAIL 1 SKIP 1 EXIT 1\\n"
        "noise PASS x\\n"
        "PASS 12 FAIL 0 SKIP 3 EXIT 0\\n'"
    )
    result = verification.run_gate(command, tmp_path, "abc123", 2)

    assert result == {
        "passed": 12,
        "failed": 0,
        "skipped": 3,
        "exit": 0,
        "raw_line": "PASS 12 FAIL 0 SKIP 3 EXIT 0",
        "timed_out": False,
    }


def test_run_gate_unparseable_output_records_nothing(tmp_path: Path) -> None:
    result = verification.run_gate(
        "echo 'pass 1 fail 0 skip 0 exit 0'; exit 3", tmp_path, "abc", 1
    )

    assert result["passed"] is None
    assert result["failed"] is None
    assert result["skipped"] is None
    assert result["exit"] == 3
    assert result["timed_out"] is False
    assert not (tmp_path / RECORD_REL).exists()


def test_run_gate_keeps_tail_so_a_late_summary_line_still_parses(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setattr(verification, "GATE_OUTPUT_CAP", 64)
    # The summary line is always last; a cap that keeps the tail (not the
    # head) of output exceeding GATE_OUTPUT_CAP must still find it.
    command = "printf '%0100d\\n' 0; echo 'PASS 1 FAIL 0 SKIP 0 EXIT 0'"
    result = verification.run_gate(command, tmp_path, "abc", None)

    assert result["passed"] == 1
    assert result["failed"] == 0
    assert result["skipped"] == 0
    assert result["raw_line"] == "PASS 1 FAIL 0 SKIP 0 EXIT 0"
    assert (tmp_path / RECORD_REL).exists()


def test_run_gate_times_out_and_writes_nothing(tmp_path: Path) -> None:
    # `sleep 30; echo` keeps sleep as a child of the shell: killing only the
    # shell would leave sleep holding the pipes open for 30s.
    start = time.monotonic()
    result = verification.run_gate(
        "echo 'PASS 1 FAIL 0 SKIP 0 EXIT 0'; sleep 30; echo done",
        tmp_path,
        "abc",
        1,
        timeout=0.5,
    )
    elapsed = time.monotonic() - start

    assert result == {
        "passed": None,
        "failed": None,
        "skipped": None,
        "exit": None,
        "raw_line": None,
        "timed_out": True,
    }
    assert elapsed < 10
    assert not (tmp_path / RECORD_REL).exists()


def test_run_gate_writes_last_verification_json_on_fresh_run(tmp_path: Path) -> None:
    command = "echo 'PASS 7 FAIL 2 SKIP 1 EXIT 1'; exit 1"
    result = verification.run_gate(command, tmp_path, "deadbeef", 4)

    assert result["exit"] == 1
    written = json.loads((tmp_path / RECORD_REL).read_text())
    assert written == {
        "sha": "deadbeef",
        "cycle": 4,
        "commands": [{"command": command, "exit": 1}],
        "passed": 7,
        "failed": 2,
        "skipped": 1,
    }
