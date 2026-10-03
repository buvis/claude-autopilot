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


def test_store_only_churn_in_the_assembly_worktree_does_not_refuse(
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

    with pytest.raises(RuntimeError):
        wave_review.seed_state(
            state_path,
            wave_dict,
            _plugins_json(tmp_path),
            run_cli=dies_at_cycle,
        )
    head_after_first_hold = _git(worktree, "rev-parse", "HEAD").stdout.strip()

    # The backlog is already held; a resumed seed_state must not re-commit it.
    wave_review.seed_state(state_path, wave_dict, _plugins_json(tmp_path))

    retry_head = _git(worktree, "rev-parse", "HEAD").stdout.strip()
    assert retry_head == head_after_first_hold
