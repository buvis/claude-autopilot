#!/usr/bin/env python3
"""Tests for cli/wave_review.py - _land_cleanup's dirty-tree gate and
seed_state's backlog-holding step.

Both run against the same throwaway `git init` repo and assembly worktree
`_assembled` (in `test_wave_review.py`) builds.

The stub_text/review_paths/seed_state/review() tests live in
`test_wave_review.py`.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from cli import wave_assemble, wave_review
from cli.test_wave_launch import _autopilot, _git
from cli.test_wave_launch_refusals import (
    STORE_FILES,
    _dirty_store_and_foreign,
    _dirty_store_only,
    _track_store_file,
)
from cli.test_wave_review import WAVE_ID, _assembled, _pm, _plugins_json

# ── _land_cleanup: the assembly worktree's dirty-tree gate ─────────────────


@pytest.mark.parametrize(
    "foreign_too",
    [False, True],
    ids=["store-only", "store-plus-foreign"],
)
def test_store_churn_in_the_assembly_worktree_does_not_refuse(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    foreign_too: bool,
) -> None:
    repo, wave_path, wave_dict = _assembled(tmp_path, monkeypatch, status="converged")
    worktree = Path(wave_dict["assembly"]["worktree"])
    # Tracked-then-edited store files, exactly as `record_store` would leave
    # them uncommitted: a plain untracked file would be masked by the
    # fixture's own store `.gitignore` regardless of the gate under test.
    _track_store_file(worktree)
    if foreign_too:
        foreign = _dirty_store_and_foreign(worktree, "readme_edited")
    else:
        _dirty_store_only(worktree)

    if foreign_too:
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
    else:
        wave_review._land_cleanup(
            repo,
            wave_path,
            wave_dict,
            run_git=wave_assemble._default_run_git,
        )
        assert not worktree.exists()
        assert not wave_path.exists()


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
    if has_backlog:
        backlog.mkdir(parents=True, exist_ok=True)
        (backlog / "00050-already-seeded.md").write_text("# stub\n", encoding="utf-8")
        (backlog / "00049-another.md").write_text("# stub\n", encoding="utf-8")
    state_path = _autopilot(worktree) / "state.json"
    before_head = _git(worktree, "rev-parse", "HEAD").stdout.strip()

    wave_review.seed_state(state_path, wave_dict, _plugins_json(tmp_path))

    hold = _pm(worktree) / "prds" / "hold"
    after_head = _git(worktree, "rev-parse", "HEAD").stdout.strip()
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
