#!/usr/bin/env python3
"""Tests for cli/verification.py split out of test_verification_dirty.py:
normalize_command's whitespace-only collapsing and the cross-reuse checks
that depend on it. Split because test_verification_dirty.py outgrew the 800
line style cap.

The reuse checks run against real temporary git repos: the point is to bind
real git behavior (ancestry, diff paths, dirty tree), not a mock of it.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from cli import verification

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


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("dev/bin/release-checks", "dev/bin/release-checks"),
        # Whitespace collapses, but no shell prefix or "./" is stripped.
        ("bash  ./dev/bin/release-checks", "bash ./dev/bin/release-checks"),
        ("sh ./dev/bin/release-checks", "sh ./dev/bin/release-checks"),
        ("./dev/bin/release-checks", "./dev/bin/release-checks"),
        ("  dev/bin/release-checks\t--fast\n", "dev/bin/release-checks --fast"),
        ("bash\t./dev/bin/release-checks", "bash ./dev/bin/release-checks"),
        ("bash bash ./dev/bin/release-checks", "bash bash ./dev/bin/release-checks"),
        ("././dev/bin/release-checks", "././dev/bin/release-checks"),
        # Any whitespace collapses (str.split semantics), an inner newline too.
        ("dev/bin/release-checks\n--fast", "dev/bin/release-checks --fast"),
        ("make test", "make test"),
    ],
)
def test_normalize_command_collapses_whitespace_only(raw: str, expected: str) -> None:
    assert verification.normalize_command(raw) == expected


@pytest.mark.parametrize(
    "value",
    [
        None,
        123,
        ["dev/bin/release-checks"],
        b"dev/bin/release-checks",
        {"command": "x"},
    ],
)
def test_normalize_command_maps_non_str_to_empty_string(value: object) -> None:
    assert verification.normalize_command(value) == ""


def test_reuse_matches_a_command_spelled_with_bash_dot_slash_and_extra_spaces(
    repo: Path,
) -> None:
    head = _git(repo, "rev-parse", "HEAD")
    record = _record(head)  # recorded from "dev/bin/release-checks"

    # Whitespace-only normalization: shell/"./" spellings are now distinct.
    for spelled in ("bash  ./dev/bin/release-checks", "sh ./dev/bin/release-checks"):
        verdict = verification.reuse_verdict(record, repo, head, gate_command=spelled)
        assert verdict == ("stale", {}), spelled

    # Extra/different whitespace alone still collapses and still matches.
    loose = _record(head)
    loose["commands"] = [{"command": "dev/bin/release-checks  ", "exit": 0}]
    assert verification.reuse_verdict(loose, repo, head, gate_command=GATE) == (
        "reused",
        loose,
    )

    # Normalizing never makes a different command match.
    for other in (
        "bash bash ./dev/bin/release-checks",
        "dev/bin/release-checks --fast",
    ):
        assert verification.reuse_verdict(record, repo, head, gate_command=other) == (
            "stale",
            {},
        ), other


def test_sh_and_bash_records_do_not_cross_reuse(repo: Path) -> None:
    head = _git(repo, "rev-parse", "HEAD")
    record = _record(head)
    record["commands"] = [{"command": "sh shdep.sh", "exit": 0}]
    assert verification.reuse_verdict(
        record, repo, head, gate_command="bash shdep.sh"
    ) == ("stale", {})


def test_dot_slash_and_bare_records_do_not_cross_reuse(repo: Path) -> None:
    head = _git(repo, "rev-parse", "HEAD")
    record = _record(head)
    record["commands"] = [{"command": "bash ./gate.sh", "exit": 0}]
    for spelled in ("./gate.sh", "gate.sh"):
        reuse = verification.reuse_verdict(record, repo, head, gate_command=spelled)
        assert reuse == ("stale", {}), spelled
