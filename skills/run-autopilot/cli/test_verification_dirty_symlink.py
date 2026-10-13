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
    (repo / rel).parent.mkdir(parents=True, exist_ok=True)
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
    # static -> docs/dev/project-management/skin aliases every file below
    # it, so a committed edit to static/theme.css changes product content.
    _commit(repo, f"{STORE}/skin/theme.css", "body {}\n")
    _commit(repo, f"{STORE}/skin-old/theme.css", "body {}\n")
    _commit(repo, f"{STORE}/static/theme.css", "body {}\n")
    record = _record(_commit_symlink(repo, "static", f"{STORE}/skin"))

    # A sibling whose name merely starts with the target is not aliased, nor
    # is a store directory that only shares the link's name.
    _commit(repo, f"{STORE}/skin-old/theme.css", "p {}\n")
    sibling = _commit(repo, f"{STORE}/static/theme.css", "p {}\n")
    assert verification.reuse_verdict(record, repo, sibling, gate_command=GATE) == (
        "reused",
        record,
    )

    head = _commit(repo, f"{STORE}/skin/theme.css", "body { color: red }\n")
    assert verification.reuse_verdict(record, repo, head, gate_command=GATE) == (
        "stale",
        {},
    )


def test_uncommitted_store_edit_behind_a_product_symlink_is_stale(repo: Path) -> None:
    # HEAD equals the recorded sha: only the working tree moved. The dirt
    # checks tolerate store edits, but not one a product symlink reaches.
    _commit(repo, f"{STORE}/x.toml", "a = 1\n")
    _commit(repo, f"{STORE}/notes/cfg", "n\n")
    head = _commit_symlink(repo, "src/cfg", f"../{STORE}/x.toml")
    record = _record(head)

    # Unaliased store dirt stays tolerated: an edit to a file sharing the
    # link's name, and a new settings-like file.
    (repo / STORE / "notes" / "cfg").write_text("edited\n")
    (repo / STORE / "settings.json").write_text("{}\n")
    assert verification.reuse_verdict(record, repo, head, gate_command=GATE) == (
        "reused",
        record,
    )

    (repo / STORE / "x.toml").write_text("a = 2\n")
    assert verification.reuse_verdict(record, repo, head, gate_command=GATE) == (
        "stale",
        {},
    )

    # Staged but uncommitted is still uncommitted.
    _git(repo, "add", "--", f"{STORE}/x.toml")
    assert verification.reuse_verdict(record, repo, head, gate_command=GATE) == (
        "stale",
        {},
    )


def test_uncommitted_aliased_edit_is_stale_beside_an_unaliased_store_commit(
    repo: Path,
) -> None:
    # The committed-diff check and the dirt check are independent: a
    # committed store change no symlink reaches must not skip the dirt check.
    _commit(repo, f"{STORE}/x.toml", "a = 1\n")
    base = _commit_symlink(repo, "src/cfg", f"../{STORE}/x.toml")
    record = _record(base)
    head = _commit(repo, f"{STORE}/notes/n.md", "n\n")
    assert verification.reuse_verdict(record, repo, head, gate_command=GATE) == (
        "reused",
        record,
    )

    (repo / STORE / "x.toml").write_text("a = 2\n")
    assert verification.reuse_verdict(record, repo, head, gate_command=GATE) == (
        "stale",
        {},
    )


def test_committed_aliased_edit_is_stale_beside_unaliased_store_dirt(
    repo: Path,
) -> None:
    # Mirror case: unrelated store dirt must not gate the committed-diff check.
    _commit(repo, f"{STORE}/x.toml", "a = 1\n")
    _commit(repo, f"{STORE}/autopilot/state.json", "{}\n")
    base = _commit_symlink(repo, "src/cfg", f"../{STORE}/x.toml")
    record = _record(base)
    (repo / STORE / "autopilot" / "state.json").write_text('{"phase": "build"}\n')
    assert verification.reuse_verdict(record, repo, base, gate_command=GATE) == (
        "reused",
        record,
    )

    head = _commit(repo, f"{STORE}/x.toml", "a = 2\n")
    assert verification.reuse_verdict(record, repo, head, gate_command=GATE) == (
        "stale",
        {},
    )


def test_untracked_file_beneath_a_product_directory_symlink_is_stale(
    repo: Path,
) -> None:
    # A brand-new untracked file under a symlinked store directory is
    # product content too, though no tracked file changed.
    _commit(repo, f"{STORE}/skin/theme.css", "body {}\n")
    _commit(repo, f"{STORE}/notes/n.md", "n\n")
    head = _commit_symlink(repo, "static", f"{STORE}/skin")
    record = _record(head)

    (repo / STORE / "notes" / "new.md").write_text("new\n")
    assert verification.reuse_verdict(record, repo, head, gate_command=GATE) == (
        "reused",
        record,
    )

    (repo / STORE / "skin" / "new.css").write_text("p {}\n")
    assert verification.reuse_verdict(record, repo, head, gate_command=GATE) == (
        "stale",
        {},
    )


def test_relative_symlink_target_resolves_against_the_links_own_directory(
    repo: Path,
) -> None:
    _commit(repo, f"{STORE}/x.toml", "a = 1\n")
    _commit(repo, f"{STORE}/y.toml", "b = 1\n")
    # a/b/near -> ../STORE/x.toml names a/STORE/x.toml, not the store's x.toml.
    _commit_symlink(repo, "a/b/near", f"../{STORE}/x.toml")
    # Three directories deep, with enough ../ to reach the store's y.toml.
    base = _commit_symlink(repo, "a/b/c/far", f"../../../{STORE}/y.toml")
    record = _record(base)

    near = _commit(repo, f"{STORE}/x.toml", "a = 2\n")
    assert verification.reuse_verdict(record, repo, near, gate_command=GATE) == (
        "reused",
        record,
    )

    head = _commit(repo, f"{STORE}/y.toml", "b = 2\n")
    assert verification.reuse_verdict(record, repo, head, gate_command=GATE) == (
        "stale",
        {},
    )


def test_store_edit_behind_a_symlink_below_the_toplevel_is_stale(repo: Path) -> None:
    # repo_root is a subdirectory of the git toplevel, as in
    # test_store_only_change_below_toplevel_is_reused.
    root = repo / "sub"
    _commit(repo, f"sub/{STORE}/x.toml", "a = 1\n")
    _commit(repo, f"sub/{STORE}/notes/n.md", "n\n")
    base = _commit_symlink(repo, "sub/src/cfg", f"../{STORE}/x.toml")
    record = _record(base)

    other = _commit(repo, f"sub/{STORE}/notes/n.md", "edited\n")
    assert verification.reuse_verdict(record, root, other, gate_command=GATE) == (
        "reused",
        record,
    )

    (root / STORE / "x.toml").write_text("a = 2\n")
    assert verification.reuse_verdict(record, root, other, gate_command=GATE) == (
        "stale",
        {},
    )

    head = _commit(repo, f"sub/{STORE}/x.toml", "a = 2\n")
    assert verification.reuse_verdict(record, root, head, gate_command=GATE) == (
        "stale",
        {},
    )


def test_directory_symlink_aliasing_the_repo_root_is_stale(repo: Path) -> None:
    # A single-hop directory symlink to the repository root normalizes to
    # ".", which must be treated as an ancestor of every store path -- no
    # store path literally starts with "./", so a naive startswith check
    # would miss this alias entirely and wrongly call the run reusable.
    _commit(repo, f"{STORE}/x.toml", "a = 1\n")
    (repo / "src" / "root").symlink_to("..")
    _git(repo, "add", "--", "src/root")
    _git(repo, "commit", "--no-verify", "-q", "-m", "link root")
    record = _record(_git(repo, "rev-parse", "HEAD"))

    head = _commit(repo, f"{STORE}/x.toml", "a = 2\n")
    assert verification.reuse_verdict(record, repo, head, gate_command=GATE) == (
        "stale",
        {},
    )


def test_directory_symlink_aliasing_the_repo_root_blocks_uncommitted_reuse(
    repo: Path,
) -> None:
    # Same alias, but the store edit is uncommitted: an uncommitted store
    # path is normally tolerated, except when a product symlink reaches it,
    # which the "." branch must still catch.
    (repo / "src" / "root").symlink_to("..")
    _git(repo, "add", "--", "src/root")
    _git(repo, "commit", "--no-verify", "-q", "-m", "link root")
    head = _commit(repo, f"{STORE}/x.toml", "a = 1\n")
    record = _record(head)
    (repo / STORE / "x.toml").write_text("a = 2\n")

    assert verification.reuse_verdict(record, repo, head, gate_command=GATE) == (
        "stale",
        {},
    )
