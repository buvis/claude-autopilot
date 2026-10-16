#!/usr/bin/env python3
"""Tests for PRD 00320 (v2): `autopilot verify --log <path>` must refuse to
open its log sink for writing before it is proven safe: tracked, symlinked,
outside the git toplevel, a case-variant spelling of the store, inside
.git/, a FIFO, an existing executable, hard-linked, inside another repo's
store (nested or sibling), or reached through a symlink-swapped parent
directory. Today only a literal path-prefix check against the store
(`_refuse_verify_log` in cli/__main__.py) exists, so every refusal test
below is expected to FAIL (or ERROR) against the current code -- that is
the point. The one happy-path test (an untracked docs/dev/tmp sink) must
already pass.

See docs/dev/project-management/designs/00320-refuse-every-unsafe-verify-log-
sink-v2-design.md for the full case list this file pins.
"""

from __future__ import annotations

import json
import os
import shutil
import stat
import subprocess
import sys
import time
from pathlib import Path

import pytest

from cli import verification

try:
    from cli import log_sink_refusal
except ImportError:  # not implemented yet at this task's base commit
    log_sink_refusal = None

CLI_DIR = Path(__file__).resolve().parent
CLI_MAIN = CLI_DIR / "__main__.py"
STORE = "docs/dev/project-management"


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess:
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
        capture_output=True,
        text=True,
    )


def _git_ok(repo: Path, *args: str) -> str:
    result = _git(repo, *args)
    assert result.returncode == 0, result.stderr
    return result.stdout.strip()


def _commit(repo: Path, rel: str, body: str = "x\n") -> str:
    path = repo / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body)
    _git_ok(repo, "add", "--", rel)
    _git_ok(repo, "commit", "--no-verify", "-q", "-m", f"touch {rel}")
    return _git_ok(repo, "rev-parse", "HEAD")


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    _git_ok(tmp_path, "init", "-q")
    (tmp_path / ".gitignore").write_text("docs/dev/tmp/\n")
    _git_ok(tmp_path, "add", "--", ".gitignore")
    _git_ok(tmp_path, "commit", "--no-verify", "-q", "-m", "add gitignore")
    _commit(tmp_path, "src/app.py", "print(1)\n")
    _commit(tmp_path, f"{STORE}/autopilot/marker.txt", "marker\n")
    return tmp_path


def _run(
    args: list[str],
    cwd: Path,
    timeout: float | None = None,
) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(CLI_MAIN), *args],
        capture_output=True,
        text=True,
        cwd=str(cwd),
        timeout=timeout,
    )


GATE = "printf 'PASS 1 FAIL 0 SKIP 0 EXIT 0\\n'"


def _verify(
    repo: Path,
    log: str | None = None,
    timeout: float | None = None,
) -> subprocess.CompletedProcess:
    args = ["verify", "--gate-command", GATE]
    if log is not None:
        args += ["--log", log]
    return _run(args, repo, timeout=timeout)


def test_cli_refuses_tracked_log_and_leaves_bytes_intact(repo: Path) -> None:
    before = (repo / "src" / "app.py").read_bytes()

    result = _verify(repo, "src/app.py")

    assert result.returncode == 2
    assert "is tracked" in result.stderr
    assert (repo / "src" / "app.py").read_bytes() == before
    assert _git_ok(repo, "status", "--short") == ""


def test_cli_refuses_symlinked_log(repo: Path) -> None:
    target = repo / "docs" / "dev" / "tmp" / "untracked-target.log"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("before\n")
    before = target.read_bytes()
    link = repo / "docs" / "dev" / "tmp" / "link.log"
    link.symlink_to(target)

    result = _verify(repo, "docs/dev/tmp/link.log")

    assert result.returncode == 2
    assert "symlink" in result.stderr
    assert target.read_bytes() == before


def test_cli_refuses_log_outside_toplevel(repo: Path) -> None:
    result = _verify(repo, "../outside.log")

    assert result.returncode == 2
    assert not (repo.parent / "outside.log").exists()


def test_cli_refuses_case_variant_store_path(repo: Path) -> None:
    marker = repo / STORE / "autopilot" / "marker.txt"
    variant = repo / "docs" / "dev" / "Project-Management" / "autopilot" / "marker.txt"
    if not variant.exists():
        pytest.skip("filesystem under test is case-sensitive; no case collision")

    result = _verify(repo, "docs/dev/Project-Management/autopilot/x.log")

    assert result.returncode == 2
    assert not (repo / STORE / "autopilot" / "x.log").exists()
    assert not variant.parent.joinpath("x.log").exists()


@pytest.mark.parametrize("rel", [".git/hooks/pre-commit", ".git/config"])
def test_cli_refuses_git_dir_log(repo: Path, rel: str) -> None:
    target = repo / rel
    if not target.exists():
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("#!/bin/sh\nexit 0\n")
        os.chmod(target, 0o755)
    before = target.read_bytes()

    result = _verify(repo, rel)

    assert result.returncode == 2
    assert target.read_bytes() == before
    assert _git(repo, "status", "--short").returncode == 0


def test_cli_refuses_fifo_log(repo: Path) -> None:
    tmp = repo / "docs" / "dev" / "tmp"
    tmp.mkdir(parents=True, exist_ok=True)
    fifo = tmp / "sink.fifo"
    os.mkfifo(fifo)

    start = time.monotonic()
    try:
        result = _verify(repo, "docs/dev/tmp/sink.fifo", timeout=2.0)
    except subprocess.TimeoutExpired:
        pytest.fail("verify blocked on the FIFO sink instead of refusing it")
    elapsed = time.monotonic() - start

    assert elapsed < 2.0
    assert result.returncode == 2


def test_cli_refuses_executable_target(repo: Path) -> None:
    tmp = repo / "docs" / "dev" / "tmp"
    tmp.mkdir(parents=True, exist_ok=True)
    target = tmp / "runme.sh"
    target.write_text("#!/bin/sh\necho hi\n")
    os.chmod(target, 0o755)
    before = target.read_bytes()
    assert stat.S_IMODE(target.stat().st_mode) & 0o111

    result = _verify(repo, "docs/dev/tmp/runme.sh")

    assert result.returncode == 2
    assert target.read_bytes() == before


def test_run_gate_refuses_tracked_log_without_opening(repo: Path) -> None:
    before = (repo / "src" / "app.py").read_bytes()
    head = _git_ok(repo, "rev-parse", "HEAD")

    result = verification.run_gate(
        GATE,
        repo,
        head,
        1,
        log_path=repo / "src" / "app.py",
    )

    assert result["recorded"] is False
    assert "src/app.py" in result["dirty_paths"]
    assert (repo / "src" / "app.py").read_bytes() == before


def test_untracked_tmp_log_still_records(repo: Path) -> None:
    result = _verify(repo, "docs/dev/tmp/custom.log")

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["recorded"] is True
    assert (repo / "docs" / "dev" / "tmp" / "custom.log").exists()


def test_cli_refuses_hardlinked_log(repo: Path) -> None:
    marker = repo / STORE / "autopilot" / "marker.txt"
    before = marker.read_bytes()
    tmp = repo / "docs" / "dev" / "tmp"
    tmp.mkdir(parents=True, exist_ok=True)
    hardlink = tmp / "hardlinked.log"
    os.link(marker, hardlink)

    result = _verify(repo, "docs/dev/tmp/hardlinked.log")

    assert result.returncode == 2
    assert marker.read_bytes() == before


def _default_sink_rel(repo: Path) -> str:
    head = _git_ok(repo, "rev-parse", "HEAD")
    return f"docs/dev/tmp/gate-{head[:7]}.log"


def test_default_sink_symlink_is_refused(repo: Path) -> None:
    tmp = repo / "docs" / "dev" / "tmp"
    tmp.mkdir(parents=True, exist_ok=True)
    target = tmp / "sink-target.log"
    target.write_text("before\n")
    before = target.read_bytes()
    sink = repo / _default_sink_rel(repo)
    sink.parent.mkdir(parents=True, exist_ok=True)
    sink.symlink_to(target)

    result = _verify(repo)

    assert result.returncode == 2
    assert target.read_bytes() == before


def test_default_sink_hardlink_is_refused(repo: Path) -> None:
    marker = repo / STORE / "autopilot" / "marker.txt"
    before = marker.read_bytes()
    sink = repo / _default_sink_rel(repo)
    sink.parent.mkdir(parents=True, exist_ok=True)
    os.link(marker, sink)

    result = _verify(repo)

    assert result.returncode == 2
    assert marker.read_bytes() == before


def test_git_dir_identity_holds_from_a_subdirectory_cwd(repo: Path) -> None:
    subdir = repo / "src"

    result = _run(
        [
            "verify",
            "--gate-command",
            GATE,
            "--repo-root",
            str(repo),
            "--log",
            ".git/config",
        ],
        subdir,
    )

    assert result.returncode == 2
    assert _git(repo, "status", "--short").returncode == 0


def test_log_into_another_repos_store_is_refused(repo: Path, tmp_path_factory) -> None:
    other = tmp_path_factory.mktemp("other-repo")
    _git_ok(other, "init", "-q")
    _commit(other, f"{STORE}/autopilot/other-marker.txt", "other\n")
    other_marker = other / STORE / "autopilot" / "other-marker.txt"
    before = other_marker.read_bytes()

    rel = os.path.relpath(other_marker, repo)

    result = _verify(repo, rel)

    assert result.returncode == 2
    assert other_marker.read_bytes() == before


def test_parent_dir_symlink_swap_is_refused(repo: Path, monkeypatch) -> None:
    if log_sink_refusal is None:
        pytest.fail(
            "cli.log_sink_refusal does not exist yet at this task's base commit",
        )
    monkeypatch.setattr(log_sink_refusal, "refuse", lambda *a, **k: None)

    before = (repo / ".git" / "config").read_bytes()

    tmp = repo / "docs" / "dev" / "tmp"
    if tmp.exists():
        shutil.rmtree(tmp)
    tmp.symlink_to(repo / ".git")

    sink = tmp / "config"

    with pytest.raises(OSError):
        verification._open_log_sink(sink)

    assert (repo / ".git" / "config").read_bytes() == before


def test_nested_repo_store_is_refused(repo: Path) -> None:
    nested = repo / "docs" / "dev" / "tmp" / "other"
    nested.mkdir(parents=True, exist_ok=True)
    _git_ok(nested, "init", "-q")
    _commit(nested, f"{STORE}/autopilot/nested-marker.txt", "nested\n")

    result = _verify(
        repo,
        "docs/dev/tmp/other/" + STORE + "/autopilot/nested-marker.txt",
    )

    assert result.returncode == 2


def test_symlink_above_repo_root_does_not_refuse_default_sink(tmp_path: Path) -> None:
    """A symlink in the REPOSITORY's own ancestry is not the sink's symlink.

    The component walk must stop at the repo root; climbing past it (as on
    macOS, where `/tmp` is a symlink to `/private/tmp`) refuses every run,
    the default `docs/dev/tmp/gate-<sha7>.log` sink included.
    """
    if log_sink_refusal is None:
        pytest.fail(
            "cli.log_sink_refusal does not exist yet at this task's base commit",
        )
    real = tmp_path / "real"
    real.mkdir()
    _git_ok(real, "init", "-q")
    _commit(real, ".gitignore", "docs/dev/tmp/\n")
    linked_root = tmp_path / "linked"
    linked_root.symlink_to(real)
    assert linked_root.is_symlink()

    sink = linked_root / "docs" / "dev" / "tmp" / "gate-abcdef0.log"

    assert log_sink_refusal.refuse(sink, linked_root) is None


def test_worktree_dotgit_file_log_is_refused(tmp_path: Path) -> None:
    """A linked worktree's `.git` is a regular FILE pointing at the shared
    gitdir (`gitdir: /path/to/main/.git/worktrees/<name>`), not a directory.
    `refuse()` must still treat it as a git-internals sink: today the
    identity walk only inspects ANCESTORS of the resolved path (it starts at
    `resolved.parent`), so the `.git` file itself is never compared against
    the git-dir identity targets, and it then sails through the plain
    is-regular-file / is-executable / hardlink checks untouched."""
    if log_sink_refusal is None:
        pytest.fail(
            "cli.log_sink_refusal does not exist yet at this task's base commit",
        )
    main = tmp_path / "main"
    main.mkdir()
    _git_ok(main, "init", "-q")
    _commit(main, "src/app.py", "print(1)\n")
    worktree = tmp_path / "wt"
    _git_ok(main, "worktree", "add", "-q", "-b", "wtbranch", str(worktree))

    git_file = worktree / ".git"
    assert git_file.is_file()  # linked worktree: a file, not a directory
    before = git_file.read_bytes()

    result = log_sink_refusal.refuse(git_file, worktree)

    assert result is not None, (
        "a linked worktree's .git FILE must be refused as a git-internals "
        "sink, not silently allowed through the is-regular-file check"
    )
    assert git_file.read_bytes() == before


@pytest.mark.parametrize("rel", ["config", "hooks/pre-commit", "hooks/newhook"])
def test_nested_repo_git_internals_are_refused(repo: Path, rel: str) -> None:
    """`_in_nested_repo` treats a failing `git rev-parse --show-toplevel` as
    "not nested", but git also fails that probe (rc 128) when run from
    inside a `.git` directory itself -- which is exactly where
    `resolved.parent` lands for `<nested-repo>/.git/<rel>`. The failure is
    read as permission to fall through to the plain file-type checks
    instead of being refused as the nested repo's own git internals."""
    if log_sink_refusal is None:
        pytest.fail(
            "cli.log_sink_refusal does not exist yet at this task's base commit",
        )
    nested = repo / "docs" / "dev" / "tmp" / "other"
    nested.mkdir(parents=True)
    _git_ok(nested, "init", "-q")
    _commit(nested, "x.txt", "x\n")

    target = nested / ".git" / rel
    if not target.exists():
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("#!/bin/sh\nexit 0\n")

    result = log_sink_refusal.refuse(target, repo)

    assert result is not None, f"{rel} must be refused as a nested repo's git internals"


def test_absolute_log_outside_repo_via_symlinked_ancestor_reports_outside(
    tmp_path: Path,
) -> None:
    """An absolute --log path reached through a symlinked ancestor that is
    OUTSIDE the repository (the macOS `/tmp` -> `/private/tmp` shape) must
    be refused as "resolves outside the repository", not misreported as "is
    a symlink": `refuse()` runs the symlink-component check before the
    outside-toplevel check, so the symlink reason wins even though the path
    never touches the repository at all."""
    if log_sink_refusal is None:
        pytest.fail(
            "cli.log_sink_refusal does not exist yet at this task's base commit",
        )
    repo = tmp_path / "repo"
    repo.mkdir()
    _git_ok(repo, "init", "-q")
    _commit(repo, "src/app.py", "print(1)\n")

    real_outside = tmp_path / "real-outside"
    real_outside.mkdir()
    linked_outside = tmp_path / "linked-outside"
    linked_outside.symlink_to(real_outside)

    target = linked_outside / "sink.log"

    result = log_sink_refusal.refuse(target, repo)

    assert result == "resolves outside the repository", result


def test_probe_failure_inside_toplevel_fails_closed_as_outside(
    repo: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When `_log_rel_and_tracked` returns None (its own `ls-files` probe
    raised an OSError), `refuse()` must fail closed as "resolves outside
    the repository" for a target that IS inside the toplevel, not silently
    treat the failed probe as "not tracked" and fall through to the plain
    file-type checks, which can allow the sink through."""
    if log_sink_refusal is None:
        pytest.fail(
            "cli.log_sink_refusal does not exist yet at this task's base commit",
        )
    monkeypatch.setattr(log_sink_refusal, "_log_rel_and_tracked", lambda *a, **k: None)

    target = repo / "docs" / "dev" / "tmp" / "sink.log"

    result = log_sink_refusal.refuse(target, repo)

    assert result == "resolves outside the repository", result


def test_symlinked_ancestor_component_walk_is_bounded_to_the_repo(
    tmp_path: Path,
) -> None:
    """`_symlinked_component`'s walk stops at `repo_root`/`toplevel` by
    design, but a candidate path that never passes through either --  a
    differently-spelled, symlinked location entirely outside the repository
    -- makes the loop keep climbing past filesystem ancestors that have
    nothing to do with the repo, until it hits a symlink somewhere up the
    tree and reports "is a symlink" instead of first recognizing the path
    is outside the repository altogether."""
    if log_sink_refusal is None:
        pytest.fail(
            "cli.log_sink_refusal does not exist yet at this task's base commit",
        )
    repo = tmp_path / "project" / "repo"
    repo.mkdir(parents=True)
    _git_ok(repo, "init", "-q")
    _commit(repo, "src/app.py", "print(1)\n")

    real_elsewhere = tmp_path / "elsewhere" / "real"
    real_elsewhere.mkdir(parents=True)
    aliased_elsewhere = tmp_path / "project" / "aliased"
    aliased_elsewhere.symlink_to(real_elsewhere)

    target = aliased_elsewhere / "deep" / "sink.log"

    result = log_sink_refusal.refuse(target, repo)

    assert result == "resolves outside the repository", result
