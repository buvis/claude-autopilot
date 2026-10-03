#!/usr/bin/env python3
"""Tests for cli/wave_review.py - _land_cleanup's dirty-tree gate and
seed_state's backlog-holding step.

Both run against the same throwaway `git init` repo and assembly worktree
`_assembled` (in `test_wave_review.py`) builds.

The stub_text/review_paths/seed_state/review() tests live in
`test_wave_review.py`.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from cli import wave_assemble, wave_review
from cli.test_wave_launch import _autopilot, _git
from cli.test_wave_launch_refusals import (
    FOREIGN_CASES,
    STORE_FILES,
    _dirty_store_and_foreign,
    _dirty_store_only,
    _track_store_file,
)
from cli.test_wave_review import WAVE_ID, _assembled, _plugins_json, _pm, _recording_cli

# ── _land_cleanup: the assembly worktree's dirty-tree gate ─────────────────


def test_store_churn_in_the_assembly_worktree_does_not_refuse(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo, wave_path, wave_dict = _assembled(tmp_path, monkeypatch, status="converged")
    worktree = Path(wave_dict["assembly"]["worktree"])
    # Tracked-then-edited store files, exactly as `record_store` would leave
    # them uncommitted: a plain untracked file would be masked by the
    # fixture's own store `.gitignore` regardless of the gate under test.
    _track_store_file(worktree)
    _git(repo, "merge", "--ff-only", f"wave/{WAVE_ID}/assembly")
    _dirty_store_only(worktree)

    wave_review._land_cleanup(
        repo,
        wave_path,
        wave_dict,
        run_git=wave_assemble._default_run_git,
    )
    assert not worktree.exists()
    assert not wave_path.exists()


# Every kind of foreign dirt beside store churn still has to refuse - not just
# a README edit, which a gate that string-matches one path would also pass.
@pytest.mark.parametrize("case", FOREIGN_CASES)
def test_foreign_dirt_beside_store_churn_in_the_assembly_worktree_refuses(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    case: str,
) -> None:
    repo, wave_path, wave_dict = _assembled(tmp_path, monkeypatch, status="converged")
    worktree = Path(wave_dict["assembly"]["worktree"])
    _track_store_file(worktree)
    foreign = _dirty_store_and_foreign(worktree, case)

    with pytest.raises(ValueError, match="uncommitted changes") as refused:
        wave_review._land_cleanup(
            repo,
            wave_path,
            wave_dict,
            run_git=wave_assemble._default_run_git,
        )
    assert foreign in str(refused.value), refused.value
    for rel in STORE_FILES:
        assert rel not in str(refused.value), refused.value
    assert worktree.is_dir()
    assert wave_path.exists()


# ── seed_state: holding backlog PRDs the assembly worktree inherited ───────


@pytest.mark.parametrize(
    "has_backlog",
    [True, False],
    ids=["with-backlog", "empty-backlog"],
)
def test_seeded_backlog_prds_are_held_before_the_nested_loop(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    has_backlog: bool,
) -> None:
    _, _, wave_dict = _assembled(tmp_path, monkeypatch)
    worktree = Path(wave_dict["assembly"]["worktree"])
    backlog = _pm(worktree) / "prds" / "backlog"
    backlog.mkdir(parents=True, exist_ok=True)
    # A non-`.md` backlog entry that must survive untouched either way: a
    # glob that also swept up non-PRD files would move or lose it silently.
    (backlog / "00051-other.txt").write_text("not a prd\n", encoding="utf-8")
    if has_backlog:
        (backlog / "00050-already-seeded.md").write_text("# stub\n", encoding="utf-8")
        (backlog / "00049-another.md").write_text("# stub\n", encoding="utf-8")
    state_path = _autopilot(worktree) / "state.json"
    before_head = _git(worktree, "rev-parse", "HEAD").stdout.strip()

    wave_review.seed_state(state_path, wave_dict, _plugins_json(tmp_path))

    hold = _pm(worktree) / "prds" / "hold"
    after_head = _git(worktree, "rev-parse", "HEAD").stdout.strip()
    assert (backlog / "00051-other.txt").exists()
    if has_backlog:
        assert sorted(p.name for p in hold.glob("*.md")) == [
            "00049-another.md",
            "00050-already-seeded.md",
        ]
        assert list(backlog.glob("*.md")) == []
        assert after_head != before_head
        message = _git(worktree, "log", "-1", "--pretty=%B").stdout
        assert message.startswith(
            f"chore(autopilot): hold seeded backlog PRDs for wave {WAVE_ID} review",
        )
        assert "- 00049-another.md" in message
        assert "- 00050-already-seeded.md" in message
        assert message.index("00049-another.md") < message.index(
            "00050-already-seeded.md",
        )
    else:
        assert list(hold.glob("*.md")) == []
        assert after_head == before_head


def _seed_with_backlog(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[Path, dict, Path]:
    """`seed_state` run once over a two-PRD backlog: (worktree, wave_dict,
    state_path), ready for a second call or a git-record check."""
    _, _, wave_dict = _assembled(tmp_path, monkeypatch)
    worktree = Path(wave_dict["assembly"]["worktree"])
    backlog = _pm(worktree) / "prds" / "backlog"
    backlog.mkdir(parents=True, exist_ok=True)
    (backlog / "00050-already-seeded.md").write_text("# stub\n", encoding="utf-8")
    (backlog / "00049-another.md").write_text("# stub\n", encoding="utf-8")
    state_path = _autopilot(worktree) / "state.json"
    wave_review.seed_state(state_path, wave_dict, _plugins_json(tmp_path))
    return worktree, wave_dict, state_path


def test_holding_seeded_backlog_prds_is_a_real_git_record(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    worktree, _wave_dict, _state_path = _seed_with_backlog(tmp_path, monkeypatch)
    pm_rel = "docs/dev/project-management"
    # The move is a real git record, not a filesystem rename beside an
    # unrelated `--allow-empty` commit: git itself must show both PRDs under
    # hold/, and prds/ must be clean afterward (not a dangling index entry).
    show = _git(worktree, "show", "--name-status", "HEAD").stdout
    assert f"{pm_rel}/prds/hold/00049-another.md" in show, show
    assert f"{pm_rel}/prds/hold/00050-already-seeded.md" in show, show
    porcelain = _git(worktree, "status", "--porcelain", "--", f"{pm_rel}/prds").stdout
    assert porcelain == "", porcelain


def test_retrying_seed_state_does_not_recommit_the_held_backlog(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # The same fail-then-retry shape as
    # `test_seed_state_raises_on_a_failed_step_and_a_retry_resumes_past_init`:
    # a real retry resumes after a step failure, it does not re-run a
    # finished seed_state from the top.
    _, _, wave_dict = _assembled(tmp_path, monkeypatch)
    worktree = Path(wave_dict["assembly"]["worktree"])
    backlog = _pm(worktree) / "prds" / "backlog"
    backlog.mkdir(parents=True, exist_ok=True)
    (backlog / "00050-already-seeded.md").write_text("# stub\n", encoding="utf-8")
    state_path = _autopilot(worktree) / "state.json"
    real = _recording_cli([])

    def dies_at_cycle(argv: list[str]) -> subprocess.CompletedProcess:
        if "cycle" in argv:
            return subprocess.CompletedProcess(argv, 1, "", "disk went away")
        return real(argv)

    before_first_hold = _git(worktree, "rev-parse", "HEAD").stdout.strip()

    with pytest.raises(RuntimeError):
        wave_review.seed_state(
            state_path,
            wave_dict,
            _plugins_json(tmp_path),
            run_cli=dies_at_cycle,
        )
    head_after_first_hold = _git(worktree, "rev-parse", "HEAD").stdout.strip()

    # The first call must have actually committed the hold: an unchanged HEAD
    # here would pass the retry-idempotency check below vacuously even if
    # `_hold_backlog` silently did nothing on the first call too.
    assert head_after_first_hold != before_first_hold
    assert (_pm(worktree) / "prds" / "hold" / "00050-already-seeded.md").exists()
    assert not (backlog / "00050-already-seeded.md").exists()

    # The backlog is already held; a resumed seed_state must not re-commit it.
    wave_review.seed_state(state_path, wave_dict, _plugins_json(tmp_path))

    retry_head = _git(worktree, "rev-parse", "HEAD").stdout.strip()
    assert retry_head == head_after_first_hold


# ── _hold_backlog: partial-failure safety on retry and name collisions ─────


def _crash_on_hold_backlog_commit(monkeypatch: pytest.MonkeyPatch) -> None:
    """`_hold_backlog`'s `rm --cached` and `add -f` run for real; only the
    `commit` call raises, exactly as a real `check=True` git failure would -
    so the rename survives on disk and staged in the index, uncommitted."""
    real_run_git = wave_assemble._default_run_git

    def dies_at_commit(
        args: list[str],
        cwd: Path | None = None,
        check: bool = True,
    ) -> subprocess.CompletedProcess:
        if "commit" in args:
            raise subprocess.CalledProcessError(
                1,
                args,
                output="",
                stderr="disk went away",
            )
        return real_run_git(args, cwd=cwd, check=check)

    monkeypatch.setattr(wave_review, "_default_run_git", dies_at_commit)


def test_retrying_hold_backlog_after_a_failed_commit_converges_to_one_commit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, _, wave_dict = _assembled(tmp_path, monkeypatch)
    worktree = Path(wave_dict["assembly"]["worktree"])
    pm = _pm(worktree)
    backlog = pm / "prds" / "backlog"
    backlog.mkdir(parents=True, exist_ok=True)
    (pm / "prds" / "hold").mkdir(parents=True, exist_ok=True)
    (backlog / "00050-already-seeded.md").write_text("# stub\n", encoding="utf-8")
    real_run_git = wave_assemble._default_run_git
    _crash_on_hold_backlog_commit(monkeypatch)
    before_head = _git(worktree, "rev-parse", "HEAD").stdout.strip()

    with pytest.raises(subprocess.CalledProcessError):
        wave_review._hold_backlog(worktree, pm, wave_dict)

    # The retry runs with working git: the earlier failure must not have
    # discarded the pending move, so this call has to actually commit it.
    monkeypatch.setattr(wave_review, "_default_run_git", real_run_git)
    wave_review._hold_backlog(worktree, pm, wave_dict)

    hold = pm / "prds" / "hold"
    after_head = _git(worktree, "rev-parse", "HEAD").stdout.strip()
    assert list(backlog.glob("*.md")) == []
    assert (hold / "00050-already-seeded.md").exists()
    assert after_head != before_head
    commit_count = _git(
        worktree,
        "rev-list",
        "--count",
        f"{before_head}..{after_head}",
    ).stdout.strip()
    assert commit_count == "1", commit_count
    message = _git(worktree, "log", "-1", "--pretty=%B", after_head).stdout
    assert message.count("00050-already-seeded.md") == 1, message


def test_hold_backlog_refuses_a_name_collision_without_overwriting(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, _, wave_dict = _assembled(tmp_path, monkeypatch)
    worktree = Path(wave_dict["assembly"]["worktree"])
    pm = _pm(worktree)
    backlog = pm / "prds" / "backlog"
    hold = pm / "prds" / "hold"
    backlog.mkdir(parents=True, exist_ok=True)
    hold.mkdir(parents=True, exist_ok=True)
    name = "00050-already-seeded.md"
    (hold / name).write_text("original held content\n", encoding="utf-8")
    (backlog / name).write_text("colliding backlog content\n", encoding="utf-8")

    with pytest.raises(FileExistsError) as excinfo:
        wave_review._hold_backlog(worktree, pm, wave_dict)

    message = str(excinfo.value)
    assert str(backlog / name) in message, message
    assert str(hold / name) in message, message
    assert (hold / name).read_text(encoding="utf-8") == "original held content\n"
    assert (backlog / name).exists()


def _crash_on_hold_backlog_step(monkeypatch: pytest.MonkeyPatch, step: str) -> None:
    """Every git call runs for real except the first one naming `step` (`rm`
    or `add`), which raises as a real `check=True` failure would, then puts
    real git back. The renames into hold/ have already happened by then, so
    the only evidence of the pending move is files untracked under hold/."""
    real_run_git = wave_assemble._default_run_git

    def dies_at_step(
        args: list[str],
        cwd: Path | None = None,
        check: bool = True,
    ) -> subprocess.CompletedProcess:
        if step in args:
            monkeypatch.setattr(wave_review, "_default_run_git", real_run_git)
            raise subprocess.CalledProcessError(
                1,
                args,
                output="",
                stderr="disk went away",
            )
        return real_run_git(args, cwd=cwd, check=check)

    monkeypatch.setattr(wave_review, "_default_run_git", dies_at_step)


def _worktree_with_backlog(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *names: str,
) -> tuple[Path, Path, dict]:
    """(worktree, pm, wave_dict) with one stub PRD per name in the backlog."""
    _, _, wave_dict = _assembled(tmp_path, monkeypatch)
    worktree = Path(wave_dict["assembly"]["worktree"])
    pm = _pm(worktree)
    (pm / "prds" / "backlog").mkdir(parents=True, exist_ok=True)
    (pm / "prds" / "hold").mkdir(parents=True, exist_ok=True)
    for name in names:
        (pm / "prds" / "backlog" / name).write_text("# stub\n", encoding="utf-8")
    return worktree, pm, wave_dict


def _head_commit_files(worktree: Path) -> list[str]:
    return _git(
        worktree,
        "show",
        "--name-only",
        "--pretty=format:",
        "HEAD",
    ).stdout.splitlines()


def _commits_since(worktree: Path, before_head: str) -> str:
    after_head = _git(worktree, "rev-parse", "HEAD").stdout.strip()
    return _git(
        worktree,
        "rev-list",
        "--count",
        f"{before_head}..{after_head}",
    ).stdout.strip()


def test_a_backlog_prd_with_a_space_in_its_name_is_held_and_committed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    name = "00050-two words.md"
    worktree, pm, wave_dict = _worktree_with_backlog(tmp_path, monkeypatch, name)
    before_head = _git(worktree, "rev-parse", "HEAD").stdout.strip()

    wave_review._hold_backlog(worktree, pm, wave_dict)

    assert (pm / "prds" / "hold" / name).exists()
    assert list((pm / "prds" / "backlog").glob("*.md")) == []
    assert _commits_since(worktree, before_head) == "1"
    message = _git(worktree, "log", "-1", "--pretty=%B").stdout
    assert f"- {name}" in message, message
    # Named in the message is not enough: the file itself must be in the commit.
    assert f"docs/dev/project-management/prds/hold/{name}" in _head_commit_files(
        worktree,
    )


def test_retrying_a_held_prd_with_a_space_in_its_name_converges_to_one_commit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    name = "00050-two words.md"
    worktree, pm, wave_dict = _worktree_with_backlog(tmp_path, monkeypatch, name)
    real_run_git = wave_assemble._default_run_git
    _crash_on_hold_backlog_commit(monkeypatch)
    before_head = _git(worktree, "rev-parse", "HEAD").stdout.strip()

    with pytest.raises(subprocess.CalledProcessError):
        wave_review._hold_backlog(worktree, pm, wave_dict)

    monkeypatch.setattr(wave_review, "_default_run_git", real_run_git)
    wave_review._hold_backlog(worktree, pm, wave_dict)

    assert _commits_since(worktree, before_head) == "1"
    assert list((pm / "prds" / "backlog").glob("*.md")) == []
    assert f"docs/dev/project-management/prds/hold/{name}" in _head_commit_files(
        worktree,
    )


@pytest.mark.parametrize("step", ["rm", "add"])
def test_retry_recovers_a_move_that_failed_before_anything_was_staged(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    step: str,
) -> None:
    # Failing at `rm`/`add` leaves nothing staged: the renamed files sitting
    # untracked under hold/ are the only sign of the pending move, so a retry
    # that only looked at the index would commit nothing and strand them.
    names = ("00049-another.md", "00050-already-seeded.md")
    worktree, pm, wave_dict = _worktree_with_backlog(tmp_path, monkeypatch, *names)
    before_head = _git(worktree, "rev-parse", "HEAD").stdout.strip()
    _crash_on_hold_backlog_step(monkeypatch, step)

    with pytest.raises(subprocess.CalledProcessError):
        wave_review._hold_backlog(worktree, pm, wave_dict)
    assert _commits_since(worktree, before_head) == "0"

    wave_review._hold_backlog(worktree, pm, wave_dict)

    assert _commits_since(worktree, before_head) == "1"
    assert list((pm / "prds" / "backlog").glob("*.md")) == []
    committed = _head_commit_files(worktree)
    message = _git(worktree, "log", "-1", "--pretty=%B").stdout
    for name in names:
        assert (pm / "prds" / "hold" / name).exists()
        assert f"docs/dev/project-management/prds/hold/{name}" in committed
        assert message.count(name) == 1, message
