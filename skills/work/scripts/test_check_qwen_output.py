"""Exercise the actual Qwen guard in isolated Git repositories."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

_SCRIPT = Path(__file__).with_name("check_qwen_output.py")


def git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    git(tmp_path, "init", "-q")
    git(tmp_path, "config", "user.email", "test@example.invalid")
    git(tmp_path, "config", "user.name", "Test")
    git(tmp_path, "config", "core.hooksPath", "/dev/null")
    (tmp_path / "impl.py").write_text("answer = 0\n")
    (tmp_path / "test_impl.py").write_text("assert answer == 42\n")
    (tmp_path / "foreign.txt").write_text("original\n")
    git(tmp_path, "add", ".")
    git(tmp_path, "commit", "-qm", "baseline")
    return tmp_path


def guard(repo: Path, action: str, *extra: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            str(_SCRIPT),
            action,
            "--snapshot",
            str(repo / ".git/qwen.json"),
            *extra,
        ],
        capture_output=True,
        text=True,
        cwd=repo,
        check=False,
    )


def prepare(repo: Path, implementation: str = "impl.py") -> None:
    (repo / ".git/files.txt").write_text(str(repo / implementation) + "\n")
    (repo / ".git/tests.txt").write_text(str(repo / "test_impl.py") + "\n")
    result = guard(
        repo,
        "before",
        "--repo-root",
        str(repo),
        "--test-commit",
        git(repo, "rev-parse", "HEAD"),
        "--files-file",
        str(repo / ".git/files.txt"),
        "--tests-file",
        str(repo / ".git/tests.txt"),
    )
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize("implementation", ["impl.py", "new.py"])
def test_foreign_dirty_paths_do_not_count_as_qwen_edits(
    repo: Path, implementation: str
) -> None:
    (repo / "foreign.txt").write_text("user edit\n")
    git(repo, "add", "foreign.txt")
    prepare(repo, implementation)
    head = git(repo, "rev-parse", "HEAD")
    result = guard(repo, "after")
    assert result.returncode == 1, result.stderr
    verdict = json.loads(result.stdout)
    assert verdict["cause"] == "qwen_no_edit"
    assert verdict["outcome"] == "escalated"
    assert verdict["next"] == "sonnet"
    assert git(repo, "rev-parse", "HEAD") == head
    assert (repo / "foreign.txt").read_text() == "user edit\n"
    assert git(repo, "diff", "--cached", "--name-only") == "foreign.txt"


@pytest.mark.parametrize("staged", [False, True])
def test_test_mutation_rejects_attempt_and_restores_only_canonical_tests(
    repo: Path, staged: bool
) -> None:
    prepare(repo)
    (repo / "impl.py").write_text("answer = 42\n")
    (repo / "test_impl.py").write_text("assert True\n")
    (repo / "foreign.txt").write_text("user edit\n")
    if staged:
        git(repo, "add", "test_impl.py")
    result = guard(repo, "after", "--restore-tests")
    assert result.returncode == 1, result.stderr
    verdict = json.loads(result.stdout)
    assert verdict["cause"] == "qwen_test_mutation"
    assert verdict["next"] == "sonnet"
    assert verdict["tests_restored"] is True
    assert (repo / "test_impl.py").read_text() == "assert answer == 42\n"
    assert git(repo, "diff", "--cached") == ""
    assert (repo / "foreign.txt").read_text() == "user edit\n"
    assert (repo / "impl.py").read_text() == "answer = 42\n"


def test_staged_mutation_cannot_hide_behind_clean_worktree_content(repo: Path) -> None:
    prepare(repo)
    (repo / "test_impl.py").write_text("assert True\n")
    git(repo, "add", "test_impl.py")
    (repo / "test_impl.py").write_text("assert answer == 42\n")
    result = guard(repo, "after")
    assert result.returncode == 1
    assert json.loads(result.stdout)["cause"] == "qwen_test_mutation"


@pytest.mark.parametrize("implementation", ["impl.py", "new.py"])
def test_real_implementation_edit_proceeds_without_staging(
    repo: Path, implementation: str
) -> None:
    prepare(repo, implementation)
    (repo / implementation).write_text("answer = 42\n")
    result = guard(repo, "after")
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["next"] == "proceed"
    assert git(repo, "diff", "--cached") == ""


def test_foreign_commit_prevents_test_restoration(repo: Path) -> None:
    prepare(repo)
    (repo / "foreign.txt").write_text("user commit\n")
    git(repo, "add", "foreign.txt")
    git(repo, "commit", "-qm", "foreign")
    head = git(repo, "rev-parse", "HEAD")
    (repo / "test_impl.py").write_text("assert True\n")
    result = guard(repo, "after", "--restore-tests")
    assert result.returncode == 2
    assert "HEAD moved" in result.stderr
    assert (repo / "test_impl.py").read_text() == "assert True\n"
    assert git(repo, "rev-parse", "HEAD") == head


def test_guard_error_never_reports_success(repo: Path) -> None:
    result = guard(repo, "after")
    assert result.returncode == 2
    assert result.stdout == ""
    assert "Qwen guard indeterminate" in result.stderr


def test_index_only_implementation_change_is_not_a_worktree_edit(repo: Path) -> None:
    prepare(repo)
    (repo / "impl.py").write_text("answer = 42\n")
    git(repo, "add", "impl.py")
    (repo / "impl.py").write_text("answer = 0\n")
    result = guard(repo, "after")
    assert result.returncode == 1
    assert json.loads(result.stdout)["cause"] == "qwen_no_edit"


@pytest.mark.parametrize("path", ["impl.py", "test_impl.py"])
def test_dirty_owned_path_prevents_dispatch(repo: Path, path: str) -> None:
    (repo / path).write_text("pre-existing work\n")
    (repo / ".git/files.txt").write_text(str(repo / "impl.py"))
    (repo / ".git/tests.txt").write_text(str(repo / "test_impl.py"))
    result = guard(
        repo,
        "before",
        "--repo-root",
        str(repo),
        "--test-commit",
        git(repo, "rev-parse", "HEAD"),
        "--files-file",
        str(repo / ".git/files.txt"),
        "--tests-file",
        str(repo / ".git/tests.txt"),
    )
    assert result.returncode == 2
    assert "Qwen guard indeterminate" in result.stderr
    assert not (repo / ".git/qwen.json").exists()
    assert (repo / path).read_text() == "pre-existing work\n"


@pytest.mark.parametrize("flag", ["--assume-unchanged", "--skip-worktree"])
@pytest.mark.parametrize("introduced_during_dispatch", [False, True])
def test_git_index_shortcuts_cannot_hide_mutated_test_content(
    repo: Path, flag: str, introduced_during_dispatch: bool
) -> None:
    if not introduced_during_dispatch:
        git(repo, "update-index", flag, "test_impl.py")
    prepare(repo)
    if introduced_during_dispatch:
        git(repo, "update-index", flag, "test_impl.py")
    (repo / "impl.py").write_text("answer = 42\n")
    (repo / "test_impl.py").write_text("assert True\n")
    result = guard(repo, "after", "--restore-tests")
    assert result.returncode == 1, result.stderr
    assert json.loads(result.stdout)["cause"] == "qwen_test_mutation"
    assert (repo / "test_impl.py").read_text() == "assert answer == 42\n"


@pytest.mark.parametrize("mutated", [False, True])
def test_failed_helper_still_checks_tests_but_never_claims_no_edit(
    repo: Path, mutated: bool
) -> None:
    prepare(repo)
    if mutated:
        (repo / "test_impl.py").write_text("assert True\n")
    result = guard(repo, "after", "--tests-only")
    assert result.returncode == (1 if mutated else 0)
    verdict = json.loads(result.stdout)
    assert verdict["cause"] == ("qwen_test_mutation" if mutated else None)
    assert verdict["next"] == ("sonnet" if mutated else "handle_failure")


@pytest.mark.parametrize("edit", ["normalized_newlines", "ignored_filemode"])
def test_noncommittable_implementation_edit_escalates_without_empty_commit(
    repo: Path, edit: str
) -> None:
    if edit == "normalized_newlines":
        (repo / ".gitattributes").write_text("impl.py text eol=lf\n")
        git(repo, "add", ".gitattributes")
        git(repo, "commit", "-qm", "attributes")
    else:
        git(repo, "config", "core.filemode", "false")
    prepare(repo)
    if edit == "normalized_newlines":
        (repo / "impl.py").write_bytes(b"answer = 0\r\n")
    else:
        (repo / "impl.py").chmod(0o755)
    result = guard(repo, "after")
    assert result.returncode == 1, result.stderr
    assert json.loads(result.stdout)["cause"] == "qwen_no_edit"
    assert json.loads(result.stdout)["next"] == "sonnet"
    assert git(repo, "diff", "--cached") == ""


def test_index_deletion_with_unchanged_disk_does_not_count_as_implementation(
    repo: Path,
) -> None:
    prepare(repo)
    git(repo, "rm", "--cached", "impl.py")
    index_before = git(repo, "diff", "--cached")
    result = guard(repo, "after")
    assert result.returncode == 1, result.stderr
    assert json.loads(result.stdout)["cause"] == "qwen_no_edit"
    assert (repo / "impl.py").read_text() == "answer = 0\n"
    assert git(repo, "diff", "--cached") == index_before


@pytest.mark.parametrize("already_staged", [False, True])
def test_implementation_deletion_is_a_real_edit_without_live_staging(
    repo: Path, already_staged: bool
) -> None:
    prepare(repo)
    (repo / "impl.py").unlink()
    if already_staged:
        git(repo, "rm", "--cached", "impl.py")
    index_before = git(repo, "diff", "--cached")
    result = guard(repo, "after")
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["next"] == "proceed"
    assert git(repo, "diff", "--cached") == index_before
