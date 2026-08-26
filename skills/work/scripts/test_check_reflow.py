"""Tests for check_reflow.py — the /work step-5 reflow tripwire.

Every test drives a real temporary git repo rather than a patched
``subprocess``: the whole point of the script is that ``git diff -U0`` counts
hunks the way git counts them, and a fake would pin our idea of that instead
of git's. The 30-hunk fixture is the shape the tripwire exists for — a
formatter sweep that touches every other line of a file nobody asked it to
touch (PRD 00148).
"""

from __future__ import annotations

import importlib.util
import subprocess
from pathlib import Path

import pytest

_MODULE_PATH = Path(__file__).with_name("check_reflow.py")
_SPEC = importlib.util.spec_from_file_location("check_reflow", _MODULE_PATH)
assert _SPEC is not None and _SPEC.loader is not None
check_reflow = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(check_reflow)


def _git(repo: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", *args],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    )


def _reflowed(count: int = 60) -> str:
    """Every other line rewritten — `count // 2` hunks under -U0."""
    return (
        "\n".join(f"EDITED {i}" if i % 2 == 0 else f"line {i}" for i in range(count))
        + "\n"
    )


def _repo_with_committed_file(tmp_path: Path, lines: list[str]) -> tuple[Path, Path]:
    """A git repo whose single commit holds `sample.txt` with `lines`."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q")
    target = repo / "sample.txt"
    target.write_text("\n".join(lines) + "\n", encoding="utf-8")
    _git(repo, "add", "sample.txt")
    _git(repo, "commit", "-q", "-m", "seed")
    return repo, target


def _seeded(tmp_path: Path) -> tuple[Path, Path]:
    return _repo_with_committed_file(tmp_path, [f"line {i}" for i in range(60)])


def test_a_targeted_edit_stays_silent_and_exits_zero(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    # One contiguous hunk is what a task's own edit looks like. Flagging it
    # would make the stamp meaningless: every commit would carry `reflow:`.
    repo, target = _seeded(tmp_path)
    target.write_text(
        "\n".join(["line 0", "EDITED", *[f"line {i}" for i in range(2, 60)]]) + "\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(repo)

    exit_code = check_reflow.main(["sample.txt"])

    assert exit_code == 0
    assert capsys.readouterr().out == ""


def test_a_whole_file_reflow_is_flagged_with_its_hunk_count(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    # Every other line changed: 60 lines, 30 separate hunks under -U0 — the
    # observed formatter sweep in miniature. The count is printed because the
    # attempt record stamps it, so a wrong number is a wrong record.
    repo, target = _seeded(tmp_path)
    target.write_text(_reflowed(), encoding="utf-8")
    monkeypatch.chdir(repo)

    exit_code = check_reflow.main(["sample.txt"])

    assert exit_code == 1
    assert capsys.readouterr().out == "sample.txt\t30\n"


def test_a_path_outside_any_repo_fails_loud_on_stderr(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    # Exit 2 is its own arm: "git could not answer" must never be recorded as
    # "no reflow found" (rules/operating-principles.md, fail loud).
    (tmp_path / "loose.txt").write_text("hello\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    exit_code = check_reflow.main(["loose.txt"])

    captured = capsys.readouterr()
    assert exit_code == 2
    assert captured.out == ""
    assert captured.err.strip() != ""


def test_git_dir_and_work_tree_reach_git_for_a_bare_repo_home(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    # The buvis home is a bare repo with a detached work tree, so /work has to
    # be able to hand git both. The flags only work ahead of the subcommand;
    # this test fails if they are appended after `diff`.
    repo, target = _seeded(tmp_path)
    target.write_text(_reflowed(), encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    exit_code = check_reflow.main(
        ["--git-dir", str(repo / ".git"), "--work-tree", str(repo), "sample.txt"],
    )

    assert exit_code == 1
    assert capsys.readouterr().out == "sample.txt\t30\n"


def test_the_threshold_is_the_flagging_boundary(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    # "at or above" — a file sitting exactly on the threshold is flagged, and
    # one hunk short of it is not. Off by one here means the default of 20
    # does not mean what step 5 says it means.
    repo, target = _seeded(tmp_path)
    target.write_text(_reflowed(), encoding="utf-8")
    monkeypatch.chdir(repo)

    assert check_reflow.main(["--threshold", "30", "sample.txt"]) == 1
    assert capsys.readouterr().out == "sample.txt\t30\n"
    assert check_reflow.main(["--threshold", "31", "sample.txt"]) == 0
    assert capsys.readouterr().out == ""


def test_several_paths_report_only_the_ones_over_the_threshold(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    # step 5 hands the script the whole stage list, so a clean sibling must
    # not be named in a stamp that claims it was reflowed.
    repo, target = _seeded(tmp_path)
    quiet = repo / "quiet.txt"
    quiet.write_text("one\n", encoding="utf-8")
    _git(repo, "add", "quiet.txt")
    _git(repo, "commit", "-q", "-m", "quiet")
    quiet.write_text("two\n", encoding="utf-8")
    target.write_text(_reflowed(), encoding="utf-8")
    monkeypatch.chdir(repo)

    exit_code = check_reflow.main(["quiet.txt", "sample.txt"])

    assert exit_code == 1
    assert capsys.readouterr().out == "sample.txt\t30\n"


def test_the_tripwire_never_touches_the_files_it_measures(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # It runs mid-commit, between the stage list and `git add`. A script that
    # rewrote what it read would corrupt the very commit it reports on.
    repo, target = _seeded(tmp_path)
    target.write_text(_reflowed(), encoding="utf-8")
    monkeypatch.chdir(repo)
    before = target.read_bytes()

    check_reflow.main(["sample.txt"])

    assert target.read_bytes() == before
    assert _git_status(repo) == " M sample.txt\n"


def _git_status(repo: Path) -> str:
    result = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout
