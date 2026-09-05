"""Contract for replay_tests_against_base.py.

Built on a real two-commit repo: base ships a bug, HEAD ships the fix plus
three tests. Exactly one of them - the one that passes against the buggy
base - must be reported, the pinning test must not, and the untouched
pre-existing test must not be counted at all.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import replay_tests_against_base as r

SCRIPT = Path(__file__).with_name("replay_tests_against_base.py")
PYTEST = f"{sys.executable} -m pytest"

BASE_IMPL = "def clamp(x):\n    return x\n"
HEAD_IMPL = "def clamp(x):\n    return min(x, 10)\n"
BASE_TESTS = "from calc import clamp\n\n\ndef test_zero():\n    assert clamp(0) == 0\n"
HEAD_TESTS = BASE_TESTS + (
    "\n\ndef test_clamps_above_ten():\n    assert clamp(50) == 10\n"
    "\n\ndef test_passes_small_values_through():\n    assert clamp(3) == 3\n"
)


def _repo_git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(root), "-c", "user.name=t", "-c", "user.email=t@t", "-c", "commit.gpgsign=false", *args],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()


def _commit(root: Path, message: str, files: dict[str, str]) -> str:
    for name, text in files.items():
        (root / name).write_text(text, encoding="utf-8")
    _repo_git(root, "add", "-A")
    _repo_git(root, "commit", "-q", "-m", message)
    return _repo_git(root, "rev-parse", "HEAD")


def _repo(tmp_path: Path, head_files: dict[str, str]) -> tuple[Path, str]:
    root = tmp_path / "repo"
    root.mkdir()
    _repo_git(root, "init", "-q")
    base = _commit(root, "base", {"calc.py": BASE_IMPL, "test_calc.py": BASE_TESTS})
    _commit(root, "head", head_files)
    return root, base


def test_reports_only_the_touched_test_that_passes_against_the_buggy_base(tmp_path: Path) -> None:
    root, base = _repo(tmp_path, {"calc.py": HEAD_IMPL, "test_calc.py": HEAD_TESTS})
    block = r.replay(root, base, PYTEST, 120)
    assert (
        "[MECH] 🟡 1 touched test(s) pass against the pre-change code: "
        "test_passes_small_values_through | File: test_calc.py | Task: general"
    ) in block
    assert "test_clamps_above_ten" not in block
    assert "test_zero" not in block
    assert "Replay: 2 touched test(s) ran, 1 failed against base, 1 passed; 0 test file(s) could not be collected" in block
    assert _repo_git(root, "worktree", "list").count("\n") == 0, "the temp worktree must be removed"
    assert (root / "calc.py").read_text() == HEAD_IMPL, "the real checkout must be untouched"


def test_a_test_only_diff_is_skipped_as_a_backfill(tmp_path: Path) -> None:
    root, base = _repo(tmp_path, {"test_calc.py": HEAD_TESTS})
    block = r.replay(root, base, PYTEST, 120)
    assert "replay: skipped (no non-test change" in block
    assert "[MECH]" not in block


def test_a_runner_that_cannot_run_is_a_skip_not_a_crash(tmp_path: Path) -> None:
    root, base = _repo(tmp_path, {"calc.py": HEAD_IMPL, "test_calc.py": HEAD_TESTS})
    block = r.replay(root, base, f"{sys.executable} -c 'import sys; sys.exit(4)'", 120)
    assert "replay: skipped (runner produced no results (exit 4" in block
    assert _repo_git(root, "worktree", "list").count("\n") == 0


def test_hunk_ranges_cover_a_pure_deletion() -> None:
    assert r.head_ranges("@@ -3,2 +3,0 @@\n@@ -10 +9,4 @@\n") == [(3, 3), (9, 12)]


def test_the_cli_exits_zero_and_skips_outside_a_git_worktree(tmp_path: Path) -> None:
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--base", "HEAD~1"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
    assert result.stdout.strip() == "replay: skipped (no git worktree)"
