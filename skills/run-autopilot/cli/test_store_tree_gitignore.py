#!/usr/bin/env python3
"""Tests for store_tree.STORE_GITIGNORE / ensure_store_gitignore.

The patterns are the contract, so they are spelled out here, not derived.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from cli import store_tree
from cli.store_tree_testutil import _autopilot_dir, _write_state

_GIT_ENV = {**os.environ, "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1"}

EXPECTED_GITIGNORE_PATTERNS = [
    "autopilot/state.json",
    "autopilot/state.json.bak",
    "autopilot/**/*.lock",
    "autopilot/.turn-counts.json",
    "autopilot/.handoff-requested",
    "autopilot/.cap-fired",
    "autopilot/.session-left",
    "autopilot/.review-gate-blocks",
    "autopilot/.review-gate-failed",
    "autopilot/.lane-guard-blocks",
    "autopilot/lanes/",
    "autopilot/wave-slots/",
    "autopilot/wave.json",
    "autopilot/review-paths",
    "autopilot/last-session.log",
    "autopilot/wrapper.log",
    "autopilot/pause-requested",
    "autopilot/paused-by-operator",
    "autopilot/park-requested",
    "autopilot/session-brief.md",
    "autopilot/contract-card.md",
    "autopilot/replan-context.md",
    "autopilot/last-verification.json",
]

EXACT_BODY = "".join(f"{pattern}\n" for pattern in EXPECTED_GITIGNORE_PATTERNS)
# Each near miss below shares the line count, the word set or the last line with
# the contract's body; only a byte-exact body already matches.
EXISTING_BODIES = {
    "absent": (None, True),
    "exact": (EXACT_BODY, False),
    "reordered": ("".join(f"{p}\n" for p in EXPECTED_GITIGNORE_PATTERNS[::-1]), True),
    "same-line-count-of-junk": ("junk\n" * len(EXPECTED_GITIGNORE_PATTERNS), True),
    "same-words-on-one-line": (" ".join(EXPECTED_GITIGNORE_PATTERNS) + "\n", True),
    "last-line-only": (EXPECTED_GITIGNORE_PATTERNS[-1] + "\n", True),
    "extra-line": (EXACT_BODY + "autopilot/extra\n", True),
    "missing-line": ("".join(f"{p}\n" for p in EXPECTED_GITIGNORE_PATTERNS[:-1]), True),
    "trailing-blank-line": (EXACT_BODY + "\n", True),
    # read_text translates CRLF to LF, so the contract's comparison matches
    "crlf": (EXACT_BODY.replace("\n", "\r\n"), False),
}


def _store_dir(tmp_path: Path) -> Path:
    """A store holding two files the writer must never touch."""
    autopilot_dir = _autopilot_dir(tmp_path)
    _write_state(autopilot_dir, {"phase": "build"})
    (autopilot_dir.parent / "decisions.md").write_text("# kept\n", encoding="utf-8")
    return autopilot_dir.parent


def _fingerprint(path: Path) -> tuple:
    stat = path.stat()
    return (path.read_bytes(), stat.st_ino, stat.st_mtime_ns, stat.st_ctime_ns)


def test_store_gitignore_is_a_literal_not_a_join_call() -> None:
    """STORE_GITIGNORE is a readable multiline string literal, not built via
    `"".join(...)` over a tuple - a readability change only; the byte-exact
    rendered body is pinned by the tests below, untouched."""
    source = (Path(__file__).resolve().parent / "store_tree.py").read_text(
        encoding="utf-8",
    )
    assert 'STORE_GITIGNORE = "".join(' not in source, source


def test_ensure_store_gitignore_writes_the_pattern_list(tmp_path: Path) -> None:
    store_dir = _store_dir(tmp_path)

    wrote = store_tree.ensure_store_gitignore(store_dir)

    assert wrote is True, "a missing .gitignore is written and the write reported"
    body = (store_dir / ".gitignore").read_text(encoding="utf-8")
    assert body == store_tree.STORE_GITIGNORE, "the file body is STORE_GITIGNORE itself"
    assert body.endswith("\n") and not body.endswith("\n\n"), "one single final newline"
    assert body.splitlines() == EXPECTED_GITIGNORE_PATTERNS, "one per line, in order"
    assert [p.name for p in store_dir.parent.iterdir()] == ["project-management"]


@pytest.mark.parametrize(
    ("existing", "expected"),
    list(EXISTING_BODIES.values()),
    ids=list(EXISTING_BODIES),
)
def test_ensure_store_gitignore_is_idempotent(
    tmp_path: Path,
    existing: str | None,
    expected: bool,
) -> None:
    store_dir = _store_dir(tmp_path)
    gitignore = store_dir / ".gitignore"
    siblings = [store_dir / "decisions.md", store_dir / "autopilot" / "state.json"]
    if existing is not None:
        gitignore.write_text(existing, encoding="utf-8")
    before = _fingerprint(gitignore) if existing is not None else ()
    siblings_before = [_fingerprint(path) for path in siblings]

    wrote = store_tree.ensure_store_gitignore(store_dir)

    assert wrote is expected, f"only a byte-exact body already matches: {existing!r}"
    assert gitignore.read_text(encoding="utf-8") == store_tree.STORE_GITIGNORE
    assert [_fingerprint(p) for p in siblings] == siblings_before, (
        "no other file touched"
    )
    assert sorted(p.name for p in store_dir.parent.iterdir()) == ["project-management"]
    if not expected:
        assert _fingerprint(gitignore) == before, "a matching file is never rewritten"


def test_nested_lock_files_are_ignored(tmp_path: Path) -> None:
    """The recursive pattern `autopilot/**/*.lock` ignores a lock file nested
    under a subdirectory (`deferred/`), not just one directly in `autopilot/`."""
    store_dir = _store_dir(tmp_path)
    subprocess.run(
        ["git", "init", "-q"],
        cwd=tmp_path,
        env=_GIT_ENV,
        check=True,
        timeout=30,
    )

    store_tree.ensure_store_gitignore(store_dir)

    autopilot_dir = store_dir / "autopilot"
    (autopilot_dir / "state.json.lock").write_text("lock", encoding="utf-8")
    deferred_dir = autopilot_dir / "deferred"
    deferred_dir.mkdir(parents=True, exist_ok=True)
    (deferred_dir / "b-deferred.json.lock").write_text("lock", encoding="utf-8")
    (deferred_dir / "b-deferred.json").write_text("{}", encoding="utf-8")

    status = subprocess.run(
        ["git", "status", "--porcelain", "--untracked-files=all"],
        cwd=tmp_path,
        env=_GIT_ENV,
        capture_output=True,
        text=True,
        check=True,
        timeout=30,
    ).stdout

    assert "b-deferred.json" in status
    assert "state.json.lock" not in status
    assert "b-deferred.json.lock" not in status
