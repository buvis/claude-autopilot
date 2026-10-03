#!/usr/bin/env python3
"""Tests for cli/wave_review.py - land(), plus the review_failed-branch land
counterparts and the wave.py WAVE_STATUSES pin that rides along with them.

`land()` runs against the same throwaway `git init` repo and assembly
worktree `_assembled` (in `test_wave_review.py`) builds, plus a real commit
on the assembly branch (`_landable`, below) so the fast-forward, artifact
migration, and summary-line behavior can be exercised for real - no loop is
ever started here, land() only runs once review() has already converged or
failed.

The stub_text/review_paths/seed_state/review() tests live in
`test_wave_review.py`.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from cli import wave, wave_assemble, wave_review
from cli.test_wave_assemble import _launched
from cli.test_wave_launch import _autopilot, _git
from cli.test_wave_review import STUB, WAVE_ID, _assembled, _pm

# ── land ─────────────────────────────────────────────────────────────────


def _git_out(cwd: Path, *args: str) -> str:
    """`git <args>` run inside `cwd`, stdout stripped - the existing `_git`
    helper never returns anything, so a land() test that needs the real
    output (a rev-parse, a commit count) shells out itself."""
    return subprocess.run(
        ["git", "-C", str(cwd), *args],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()


def _branch_exists(repo: Path, branch: str) -> bool:
    return bool(_git_out(repo, "branch", "--list", branch))


def _landable(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    status: str = "converged",
) -> tuple[Path, Path, dict]:
    """`_assembled`, plus a real `base_sha` (the repo's actual HEAD, not
    `_wave`'s placeholder "1111111") and, for every status except
    `"review_failed"`, one commit on the assembly branch that both lands the
    stub PRD in the worktree's `prds/done/` (what a converged review leaves
    behind) and gives the branch a real, current tip ahead of the stale
    "2222222" `_wave` records in `assembly.head_sha` (the
    rework-since-assemble() commit `land`'s own head-sha refresh must see). A
    `"review_failed"` wave gets no stub here - that is exactly the hand-review
    signal `_land_review_failed` looks for, and callers that want it write it
    themselves (see `test_hand_reviewed_stub_in_done_lands`)."""
    repo, wave_path, wave_dict = _assembled(tmp_path, monkeypatch, status=status)
    worktree = Path(wave_dict["assembly"]["worktree"])
    base_sha = _git_out(repo, "rev-parse", "HEAD")
    # `_assembled` already redirected HOME to a fixture dir with no
    # .gitconfig, so a real commit here needs its own identity.
    _git(worktree, "config", "user.email", "wave-test@example.com")
    _git(worktree, "config", "user.name", "Wave Test")
    if status != "review_failed":
        stub = _pm(worktree) / "prds" / "done" / STUB
        stub.parent.mkdir(parents=True, exist_ok=True)
        stub.write_text("stub prd\n", encoding="utf-8")
        # docs/dev/tmp/ is gitignored in this fixture repo (see
        # `_check_reviewable`'s dirty-check tests), so the stub needs --force.
        _git(worktree, "add", "--force", str(stub))
        _git(worktree, "commit", "-m", "test: complete assembly review")
    _autopilot(worktree).mkdir(parents=True, exist_ok=True)
    (_autopilot(worktree) / "state.json").write_text(
        json.dumps({"cycle": 1}),
        encoding="utf-8",
    )
    wave_dict = {**wave_dict, "base_sha": base_sha}
    wave.save(wave_path, wave_dict)
    return repo, wave_path, wave_dict


def test_land_fast_forwards_master_and_removes_the_worktree(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo, _, wave_dict = _landable(tmp_path, monkeypatch)
    worktree = Path(wave_dict["assembly"]["worktree"])
    assembly_tip = _git_out(worktree, "rev-parse", "HEAD")
    assert wave_review.land(repo, wave_dict) == 0
    assert _git_out(repo, "rev-parse", "HEAD") == assembly_tip
    assert not worktree.exists()
    assert not _branch_exists(repo, f"wave/{WAVE_ID}/assembly")


def test_land_migrates_the_assembly_artifacts_as_lane_assembly(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo, _, wave_dict = _landable(tmp_path, monkeypatch)
    worktree = Path(wave_dict["assembly"]["worktree"])
    (_autopilot(worktree) / "loop-metrics.jsonl").write_text(
        json.dumps({"event": "cycle_done"}) + "\n",
        encoding="utf-8",
    )
    assert wave_review.land(repo, wave_dict) == 0
    lines = (
        (_autopilot(repo) / "loop-metrics.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    )
    [row] = [json.loads(line) for line in lines]
    assert row == {"event": "cycle_done", "lane": "assembly", "wave": WAVE_ID}


def test_land_refuses_when_master_moved(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo, wave_path, wave_dict = _landable(tmp_path, monkeypatch)
    worktree = Path(wave_dict["assembly"]["worktree"])
    (repo / "unrelated.txt").write_text("x\n", encoding="utf-8")
    _git(repo, "add", "unrelated.txt")
    _git(repo, "commit", "-m", "test: land unrelated work on master meanwhile")
    before = _git_out(repo, "rev-list", "--count", "HEAD")
    assert wave_review.land(repo, wave_dict) == 5
    assert _git_out(repo, "rev-list", "--count", "HEAD") == before
    assert worktree.exists()
    assert wave.load(wave_path)["status"] == "converged"


def test_review_failed_keeps_master_untouched(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo, wave_path, wave_dict = _landable(
        tmp_path,
        monkeypatch,
        status="review_failed",
    )
    worktree = Path(wave_dict["assembly"]["worktree"])
    before = _git_out(repo, "rev-list", "--count", "HEAD")
    assert wave_review.land(repo, wave_dict) == 4
    assert _git_out(repo, "rev-list", "--count", "HEAD") == before
    assert worktree.exists()
    assert _branch_exists(repo, f"wave/{WAVE_ID}/assembly")
    assert wave.load(wave_path)["status"] == "review_failed"


def test_land_precondition_rejects_assembled_status(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo, wave_path, wave_dict = _assembled(tmp_path, monkeypatch, status="assembled")
    with pytest.raises(ValueError):
        wave_review.land(repo, wave_dict)
    assert wave.load(wave_path)["status"] == "assembled"


def test_land_resumes_after_a_migration_crash(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo, wave_path, wave_dict = _landable(tmp_path, monkeypatch)
    worktree = Path(wave_dict["assembly"]["worktree"])
    ledger = _autopilot(repo) / "loop-metrics.jsonl"
    (_autopilot(worktree) / "loop-metrics.jsonl").write_text(
        json.dumps({"event": "cycle_done"}) + "\n",
        encoding="utf-8",
    )
    real_migrate_lane = wave_assemble.migrate_lane
    calls = {"n": 0}

    def crashes_once(main: Path, wave_id: str, lane: dict) -> None:
        real_migrate_lane(main, wave_id, lane)
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("simulated crash after migration")

    monkeypatch.setattr(wave_assemble, "migrate_lane", crashes_once)
    with pytest.raises(RuntimeError, match="simulated crash after migration"):
        wave_review.land(repo, wave_dict)

    saved = wave.load(wave_path)
    assert saved["status"] == "converged"
    assert saved["assembly"].get("migrated_at")
    assert worktree.exists()
    assert ledger.read_text(encoding="utf-8").count("cycle_done") == 1
    assert (_pm(repo) / "prds" / "done" / STUB).exists()

    monkeypatch.setattr(wave_assemble, "migrate_lane", real_migrate_lane)
    assert wave_review.land(repo, wave_dict) == 0
    # A successful land moves wave.json to reports/ rather than leaving it
    # readable at wave_path (task 7: "move, not copy" - see
    # test_land_removes_wave_slots_and_moves_wave_json_to_reports).
    assert not wave_path.exists()
    archived = json.loads(
        (_autopilot(repo) / "reports" / f"{WAVE_ID}-wave.json").read_text(
            encoding="utf-8",
        ),
    )
    assert archived["status"] == "done"
    assert ledger.read_text(encoding="utf-8").count("cycle_done") == 1
    assert not worktree.exists()


def test_land_refreshes_the_archived_head_sha(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo, _, wave_dict = _landable(tmp_path, monkeypatch)
    worktree = Path(wave_dict["assembly"]["worktree"])
    actual_tip = _git_out(worktree, "rev-parse", "HEAD")
    assert wave_dict["assembly"]["head_sha"] != actual_tip
    assert wave_review.land(repo, wave_dict) == 0
    archived = json.loads(
        (_autopilot(repo) / "reports" / f"{WAVE_ID}-wave.json").read_text(
            encoding="utf-8",
        ),
    )
    assert archived["assembly"]["head_sha"] == actual_tip


def test_land_appends_the_converged_summary_line(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo, _, wave_dict = _landable(tmp_path, monkeypatch)
    worktree = Path(wave_dict["assembly"]["worktree"])
    assembly_tip = _git_out(worktree, "rev-parse", "HEAD")

    assert wave_review.land(repo, wave_dict) == 0

    expected_line = f"## Assembly review: converged (1 cycle(s)), landed {assembly_tip}"
    for folder in ("reports", "ledger"):
        text = (_autopilot(repo) / folder / f"{WAVE_ID}-wave.md").read_text(
            encoding="utf-8",
        )
        assert text.count("## Assembly review:") == 1
        assert expected_line in text.splitlines()


def test_review_failed_appends_the_summary_line_with_no_review_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo, wave_path, wave_dict = _landable(
        tmp_path,
        monkeypatch,
        status="review_failed",
    )
    worktree = Path(wave_dict["assembly"]["worktree"])
    before = _git_out(repo, "rev-list", "--count", "HEAD")

    assert wave_review.land(repo, wave_dict) == 4

    assert _git_out(repo, "rev-list", "--count", "HEAD") == before
    assert worktree.exists()
    assert _branch_exists(repo, f"wave/{WAVE_ID}/assembly")
    assert wave.load(wave_path)["status"] == "review_failed"
    expected_line = "## Assembly review: review_failed, see no review file written"
    for folder in ("reports", "ledger"):
        text = (_autopilot(repo) / folder / f"{WAVE_ID}-wave.md").read_text(
            encoding="utf-8",
        )
        assert text.count("## Assembly review:") == 1
        assert expected_line in text.splitlines()


def test_hand_reviewed_stub_in_done_lands(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An operator who hand-reviewed a review_failed assembly moves the stub
    into the worktree's prds/done/; land() must then take the converged path
    and actually land instead of exiting 4. The stub is left uncommitted -
    docs/dev/project-management/ is store-exempt from the worktree dirty
    check, so this models the operator's own hand-moved file faithfully."""
    repo, wave_path, wave_dict = _landable(
        tmp_path,
        monkeypatch,
        status="review_failed",
    )
    worktree = Path(wave_dict["assembly"]["worktree"])
    stub = _pm(worktree) / "prds" / "done" / STUB
    stub.parent.mkdir(parents=True, exist_ok=True)
    stub.write_text("stub prd\n", encoding="utf-8")
    assembly_tip = _git_out(worktree, "rev-parse", "HEAD")

    assert wave_review.land(repo, wave_dict) == 0

    assert _git_out(repo, "rev-parse", "HEAD") == assembly_tip
    assert not worktree.exists()
    assert not _branch_exists(repo, f"wave/{WAVE_ID}/assembly")
    assert not wave_path.exists()
    archived = json.loads(
        (_autopilot(repo) / "reports" / f"{WAVE_ID}-wave.json").read_text(
            encoding="utf-8",
        ),
    )
    assert archived["status"] == "done"
    assert (_pm(repo) / "prds" / "done" / STUB).exists()


def test_review_failed_without_hand_review_still_exits_four(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """With no stub in the worktree's prds/done/, a review_failed wave still
    exits 4 and lands nothing. `_landable` leaves no stub there for
    `status="review_failed"`, so this models a wave the operator never
    hand-reviewed with no setup beyond that default."""
    repo, wave_path, wave_dict = _landable(
        tmp_path,
        monkeypatch,
        status="review_failed",
    )
    worktree = Path(wave_dict["assembly"]["worktree"])
    stub = _pm(worktree) / "prds" / "done" / STUB
    assert not stub.exists()
    master_tip = _git_out(repo, "rev-parse", "HEAD")

    assert wave_review.land(repo, wave_dict) == 4

    assert _git_out(repo, "rev-parse", "HEAD") == master_tip
    assert worktree.exists()
    assert _branch_exists(repo, f"wave/{WAVE_ID}/assembly")
    assert wave.load(wave_path)["status"] == "review_failed"
    assert not (_autopilot(repo) / "reports" / f"{WAVE_ID}-wave.json").exists()


def test_land_resumes_after_a_crash_between_save_and_cleanup(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The design saves status "done" and the refreshed head_sha BEFORE the
    destructive worktree/branch/wave-slots/wave.json cleanup, so a kill in
    between leaves status already "done" while the worktree, branch, and
    wave.json's own location are all still there - the retry must finish the
    leftover cleanup without redoing the merge/migrate/save and without
    duplicating the summary line."""
    repo, wave_path, wave_dict = _landable(tmp_path, monkeypatch)
    worktree = Path(wave_dict["assembly"]["worktree"])
    assembly_tip = _git_out(worktree, "rev-parse", "HEAD")
    real_run_git = wave_assemble._default_run_git

    def crashes_on_worktree_remove(
        argv: list[str],
        **kwargs: object,
    ) -> subprocess.CompletedProcess:
        if "worktree" in argv and "remove" in argv:
            raise RuntimeError("simulated crash before the destructive cleanup")
        return real_run_git(argv, **kwargs)

    with pytest.raises(
        RuntimeError,
        match="simulated crash before the destructive cleanup",
    ):
        wave_review.land(repo, wave_dict, run_git=crashes_on_worktree_remove)

    saved = wave.load(wave_path)
    assert saved["status"] == "done"
    assert saved["assembly"]["head_sha"] == assembly_tip
    assert worktree.exists()
    assert _branch_exists(repo, f"wave/{WAVE_ID}/assembly")
    report = (_autopilot(repo) / "reports" / f"{WAVE_ID}-wave.md").read_text(
        encoding="utf-8",
    )
    assert report.count("## Assembly review:") == 1

    assert wave_review.land(repo, saved) == 0

    assert not worktree.exists()
    assert not _branch_exists(repo, f"wave/{WAVE_ID}/assembly")
    assert not wave_path.exists()
    report_after = (_autopilot(repo) / "reports" / f"{WAVE_ID}-wave.md").read_text(
        encoding="utf-8",
    )
    assert report_after.count("## Assembly review:") == 1


def test_land_removes_wave_slots_and_moves_wave_json_to_reports(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo, wave_path, wave_dict = _landable(tmp_path, monkeypatch)
    slots = _autopilot(repo) / "wave-slots"
    slots.mkdir(parents=True)
    (slots / "slot-0").write_text("held\n", encoding="utf-8")

    assert wave_review.land(repo, wave_dict) == 0

    assert not slots.exists()
    assert not wave_path.exists()
    assert (_autopilot(repo) / "reports" / f"{WAVE_ID}-wave.json").exists()


def test_land_refuses_when_master_moved_and_worktree_is_gone(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The guard must resolve the assembly branch's tip directly (it stays
    resolvable via the branch ref even once the worktree checkout is
    removed), not fall back to a substitute that makes "master moved" pass
    vacuously."""
    repo, wave_path, wave_dict = _landable(tmp_path, monkeypatch)
    worktree = Path(wave_dict["assembly"]["worktree"])
    assembly_branch = f"wave/{WAVE_ID}/assembly"
    _git(repo, "worktree", "remove", "--force", str(worktree))
    (repo / "unrelated.txt").write_text("x\n", encoding="utf-8")
    _git(repo, "add", "unrelated.txt")
    _git(repo, "commit", "-m", "test: land unrelated work while the worktree is gone")
    before = _git_out(repo, "rev-list", "--count", "HEAD")

    assert wave_review.land(repo, wave_dict) == 5

    assert _git_out(repo, "rev-list", "--count", "HEAD") == before
    assert _branch_exists(repo, assembly_branch)
    assert wave.load(wave_path)["status"] == "converged"


def test_land_refuses_to_discard_uncommitted_changes_in_the_assembly_worktree(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The pre-removal dirty-check sits right before `git worktree remove
    --force`, after the merge and migrate have already landed and status has
    already advanced to "done" - it protects only the worktree itself from
    being discarded, not the earlier steps from completing."""
    repo, wave_path, wave_dict = _landable(tmp_path, monkeypatch)
    worktree = Path(wave_dict["assembly"]["worktree"])
    assembly_tip = _git_out(worktree, "rev-parse", "HEAD")
    (worktree / "dirty.txt").write_text("uncommitted rework\n", encoding="utf-8")

    with pytest.raises(ValueError):
        wave_review.land(repo, wave_dict)

    assert _git_out(repo, "rev-parse", "HEAD") == assembly_tip
    assert worktree.exists()
    assert (worktree / "dirty.txt").exists()
    assert _branch_exists(repo, f"wave/{WAVE_ID}/assembly")
    assert wave.load(wave_path)["status"] == "done"


# ── wave.py: WAVE_STATUSES ───────────────────────────────────────────────


def test_structural_errors_and_assemble_accept_an_interrupted_wave(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The interrupt handler's `status: "interrupted"` must be a value
    `_structural_errors` accepts and `_refusals` does not refuse assembly for
    on status grounds alone - otherwise the documented `wave assemble` resume
    is impossible. The one lane is marked already "assembled" (a
    structurally valid lane status with a real precedent - a rerun that
    finds a lane already merged) so this test isolates the wave-level status
    check from the lane's own liveness and merge machinery."""
    repo, wave_path = _launched(tmp_path, monkeypatch, 1)
    saved = wave.load(wave_path)
    finished = {**saved["lanes"][0], "pid": None, "status": "assembled"}
    interrupted = {**saved, "status": "interrupted", "lanes": [finished]}
    assert wave._structural_errors(repo, interrupted) == []
    wave.save(wave_path, interrupted)
    refusal_code = 1
    assert wave_assemble.assemble(repo, wave_path) != refusal_code
