#!/usr/bin/env python3
"""Tests for cli/verification.py split out of test_verification_dirty.py:
reuse_verdict refusing reuse when a tracked product symlink aliases a store
path that changed, in a commit or in the working tree. Split because
test_verification_dirty.py outgrew the 800-line style cap.

The checks run against real temporary git repos: the point is to bind real
git behavior (symlink blobs, diffs, status records), not a mock of it.
"""

from __future__ import annotations

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


def _commit_symlink(repo: Path, rel: str, target: str) -> str:
    (repo / rel).symlink_to(target)
    _git(repo, "add", "--", rel)
    _git(repo, "commit", "--no-verify", "-q", "-m", f"link {rel}")
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


def test_store_edit_beneath_a_product_directory_symlink_is_stale(repo: Path) -> None:
    # assets -> docs/dev/project-management/assets aliases every file below
    # it, so a committed edit to assets/theme.css changes product content.
    _commit(repo, f"{STORE}/assets/theme.css", "body {}\n")
    _commit(repo, f"{STORE}/assets-old/theme.css", "body {}\n")
    record = _record(_commit_symlink(repo, "assets", f"{STORE}/assets"))

    # A sibling whose name merely starts with the target is not aliased.
    sibling = _commit(repo, f"{STORE}/assets-old/theme.css", "p {}\n")
    assert verification.reuse_verdict(record, repo, sibling, gate_command=GATE) == (
        "reused",
        record,
    )

    head = _commit(repo, f"{STORE}/assets/theme.css", "body { color: red }\n")
    assert verification.reuse_verdict(record, repo, head, gate_command=GATE) == (
        "stale",
        {},
    )


def test_uncommitted_store_edit_behind_a_product_symlink_is_stale(repo: Path) -> None:
    # HEAD equals the recorded sha: only the working tree moved. The dirt
    # checks tolerate store edits, but not one a product symlink reaches.
    _commit(repo, f"{STORE}/settings.json", "{}\n")
    _commit(repo, f"{STORE}/notes/n.md", "n\n")
    head = _commit_symlink(repo, "src/settings.json", f"../{STORE}/settings.json")
    record = _record(head)

    # An unstaged edit to a store file no symlink reaches stays tolerated.
    (repo / STORE / "notes" / "n.md").write_text("edited\n")
    assert verification.reuse_verdict(record, repo, head, gate_command=GATE) == (
        "reused",
        record,
    )

    (repo / STORE / "settings.json").write_text('{"debug": true}\n')
    assert verification.reuse_verdict(record, repo, head, gate_command=GATE) == (
        "stale",
        {},
    )

    # Staged but uncommitted is still uncommitted.
    _git(repo, "add", "--", f"{STORE}/settings.json")
    assert verification.reuse_verdict(record, repo, head, gate_command=GATE) == (
        "stale",
        {},
    )


def test_uncommitted_aliased_edit_is_stale_beside_an_unaliased_store_commit(
    repo: Path,
) -> None:
    # The committed-diff check and the dirt check are independent: a
    # committed store change no symlink reaches must not skip the dirt check.
    _commit(repo, f"{STORE}/settings.json", "{}\n")
    base = _commit_symlink(repo, "src/settings.json", f"../{STORE}/settings.json")
    record = _record(base)
    head = _commit(repo, f"{STORE}/notes/n.md", "n\n")
    assert verification.reuse_verdict(record, repo, head, gate_command=GATE) == (
        "reused",
        record,
    )

    (repo / STORE / "settings.json").write_text('{"debug": true}\n')
    assert verification.reuse_verdict(record, repo, head, gate_command=GATE) == (
        "stale",
        {},
    )
