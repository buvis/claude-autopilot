#!/usr/bin/env python3
"""Tests for cli/wave_assemble.py - `migrate_lane`, and what `assemble` does
once a lane's merge is settled: draining the lane's own dev/local into the main
checkout, removing a merged lane's worktree and branch, and writing the wave's
durable report.

The pure `keep_both`/`summary` proofs and the merge pass itself live in the
sibling cli/test_wave_assemble.py, whose fixtures this file reuses: run both
files. Every proof here runs against a throwaway `git init` repo under
`tmp_path` whose lane worktrees are seeded by hand - rows, deferred items,
reports and PRD folders - before `assemble` is called, and then asserts on the
main checkout's copies.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from cli import wave, wave_assemble
from cli.test_wave_assemble import (
    _checks_pass,
    _clashing_edits,
    _commit,
    _deferred,
    _finish,
    _launched,
    _saved,
    _write,
)
from cli.test_wave_launch import _autopilot, _backlog, _git

_AP = "dev/local/autopilot"
_PRDS = "dev/local/prds"
LANE_BATCH = "202609260900"
# Seeded on the base commit so two lanes editing the same lines conflict.
CLASH_SEED = {
    "CHANGELOG.md": "# Changelog\n",
    "src/alpha.py": "alpha = 0\n",
    "src/zeta.py": "zeta = 0\n",
}


def _jsonl(rows: list[dict]) -> str:
    return "".join(json.dumps(row) + "\n" for row in rows)


def _rows(path: Path) -> list[dict]:
    text = path.read_text(encoding="utf-8")
    return [json.loads(line) for line in text.splitlines()]


def _batched(worktree: Path, batch_id: str) -> None:
    """The drained lane's state.json, also naming the batch its loop ran."""
    state = json.dumps({"next_phase": "", "batch": {"id": batch_id}})
    _write(worktree, {f"{_AP}/state.json": state})


def _to_done(worktree: Path, prd: str) -> None:
    """The lane's loop finished `prd`: it sits in the lane's own done/ now."""
    (_backlog(worktree) / prd).rename(worktree / _PRDS / "done" / prd)


def _assert_tagged(
    migrated: list[dict],
    source: list[dict],
    lane: str,
    wave_id: str,
) -> None:
    """Every row arrived once, kept its own fields, and gained the lane's tags:
    the lane name, the wave id, and the batch id the lane's loop ran under."""
    assert len(migrated) == len(source)
    for row, before in zip(migrated, source, strict=True):
        assert {key: row[key] for key in before} == before, row
        assert (row["lane"], row["wave"]) == (lane, wave_id), row
        assert LANE_BATCH in row.values(), row


# ── migrate_lane: the lane's own records ─────────────────────────────────


def test_ledger_rows_gain_lane_and_wave_fields(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo, wave_path = _launched(tmp_path, monkeypatch, 1)
    worktree = _finish(wave_path, "l1", "")
    _commit(worktree, {"x/a.py": "# l1\n"}, "l1 change")
    _batched(worktree, LANE_BATCH)
    _to_done(worktree, "00001-a.md")
    ledger = [
        {"prd": "00001-a.md", "event": "task_done", "task": 1},
        {"prd": "00001-a.md", "event": "task_done", "task": 2},
    ]
    metric = {"prd": "00001-a.md", "batch": LANE_BATCH, "wall_secs": 5400}
    _write(
        worktree,
        {
            f"{_AP}/ledger/00001-a.jsonl": _jsonl(ledger),
            f"{_AP}/loop-metrics.jsonl": _jsonl([metric]),
        },
    )
    # A row the main checkout already had: the migration appends, never rewrites.
    earlier = {"prd": "00000-z.md", "batch": "202609250800", "wall_secs": 60}
    _write(repo, {f"{_AP}/loop-metrics.jsonl": _jsonl([earlier])})
    assert wave_assemble.assemble(repo, wave_path, run_checks=_checks_pass) == 0
    wave_id = wave.load(wave_path)["id"]
    _assert_tagged(
        _rows(_autopilot(repo) / "ledger" / "00001-a.jsonl"),
        ledger,
        "l1",
        wave_id,
    )
    metrics = _rows(_autopilot(repo) / "loop-metrics.jsonl")
    assert metrics[0] == earlier, metrics
    _assert_tagged(metrics[1:], [metric], "l1", wave_id)


def test_dispatch_rows_migrate_too(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo, wave_path = _launched(tmp_path, monkeypatch, 1)
    worktree = _finish(wave_path, "l1", "")
    _commit(worktree, {"x/a.py": "# l1\n"}, "l1 change")
    _batched(worktree, LANE_BATCH)
    _to_done(worktree, "00001-a.md")
    dispatch = [
        {"id": "d1", "kind": "implementor", "task": "task 1", "prompt_bytes": 40},
        {"id": "d1", "ended_at": "2026-09-26T09:10:00Z", "outcome": "ok"},
        {"kind": "handoff", "site": "work", "phase": "work", "prd": "00001-a.md"},
    ]
    _write(worktree, {f"{_AP}/dispatch-metrics.jsonl": _jsonl(dispatch)})
    assert wave_assemble.assemble(repo, wave_path, run_checks=_checks_pass) == 0
    wave_id = wave.load(wave_path)["id"]
    migrated = _rows(_autopilot(repo) / "dispatch-metrics.jsonl")
    _assert_tagged(migrated, dispatch, "l1", wave_id)


def test_deferred_items_migrate_idempotently(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo, wave_path = _launched(tmp_path, monkeypatch, 1)
    worktree = _finish(wave_path, "l1", "")
    _batched(worktree, LANE_BATCH)
    items = [
        {"type": "stall", "detail": f"d{n}", "op_id": f"l1-{n}", "prd": "00001-a.md"}
        for n in (1, 2)
    ]
    metric = {"prd": "00001-a.md", "batch": LANE_BATCH, "wall_secs": 60}
    _write(
        worktree,
        {
            f"{_AP}/deferred/{LANE_BATCH}-deferred.json": json.dumps(
                {"batch_id": LANE_BATCH, "items": items},
            ),
            f"{_AP}/loop-metrics.jsonl": _jsonl([metric]),
        },
    )
    loaded = wave.load(wave_path)
    lane = loaded["lanes"][0]
    wave_assemble.migrate_lane(repo, loaded["id"], lane)
    landed = _deferred(wave_path, LANE_BATCH)
    content = json.loads(landed.read_text(encoding="utf-8"))
    # Each item reached the main checkout through record_defer, untouched.
    assert content == {"batch_id": LANE_BATCH, "items": items}
    assert lane["migrated_at"], lane
    metrics = _autopilot(repo) / "loop-metrics.jsonl"
    before = (landed.read_text(encoding="utf-8"), metrics.read_text(encoding="utf-8"))
    wave_assemble.migrate_lane(repo, loaded["id"], lane)
    after = (landed.read_text(encoding="utf-8"), metrics.read_text(encoding="utf-8"))
    assert after == before


# ── assemble: after the merge ────────────────────────────────────────────


def test_prds_land_in_done_hold_or_backlog_by_lane_status(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo, wave_path = _launched(tmp_path, monkeypatch, 2, CLASH_SEED)
    merged = _finish(wave_path, "l1", "")
    _commit(merged, _clashing_edits("l1"), "l1 change")
    kept = _finish(wave_path, "l2", "")
    _commit(kept, _clashing_edits("l2"), "l2 change")
    _to_done(merged, "00001-a.md")
    _write(merged, {f"{_PRDS}/hold/00080-parked.md": "parked in l1\n"})
    (_backlog(kept) / "00002-b.md").rename(kept / _PRDS / "wip" / "00002-b.md")
    _write(
        kept,
        {
            f"{_PRDS}/hold/00081-parked.md": "parked in l2\n",
            f"{_PRDS}/backlog/00082-next.md": "next in l2\n",
        },
    )
    assert wave_assemble.assemble(repo, wave_path, run_checks=_checks_pass) == 3
    _, lanes = _saved(repo, wave_path)
    assert (lanes["l1"]["status"], lanes["l2"]["status"]) == ("assembled", "conflict")
    main = repo / _PRDS
    assert [path.name for path in (main / "done").iterdir()] == ["00001-a.md"]
    assert sorted(path.name for path in (main / "hold").iterdir()) == [
        "00080-parked.md",
        "00081-parked.md",
    ]
    assert sorted(path.name for path in (main / "backlog").iterdir()) == [
        "00002-b.md",
        "00082-next.md",
    ]
    parked = main / "hold" / "00081-parked.md"
    assert parked.read_text(encoding="utf-8") == "parked in l2\n"
    # The kept lane's PRDs moved out of its own folders; they were not copied.
    assert list((kept / _PRDS / "wip").iterdir()) == []
    assert list(_backlog(kept).iterdir()) == []


def test_merged_worktrees_and_branches_are_removed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo, wave_path = _launched(tmp_path, monkeypatch, 2)
    for name, rel, prd in (
        ("l1", "x/a.py", "00001-a.md"),
        ("l2", "y/b.py", "00002-b.md"),
    ):
        worktree = _finish(wave_path, name, "")
        _commit(worktree, {rel: f"# {name}\n"}, f"{name} change")
        _to_done(worktree, prd)
    was = {
        each["name"]: Path(each["worktree"]) for each in wave.load(wave_path)["lanes"]
    }
    assert wave_assemble.assemble(repo, wave_path, run_checks=_checks_pass) == 0
    saved, lanes = _saved(repo, wave_path)
    assert saved["status"] == "assembled"
    assembled = (saved["assembly"]["merged"], saved["assembly"]["kept"])
    assert assembled == (["l1", "l2"], [])
    listed = _git(repo, "worktree", "list").stdout
    for name in ("l1", "l2"):
        assert lanes[name]["worktree_removed"] is True, lanes[name]
        assert not was[name].exists(), was[name]
        assert was[name].name not in listed, listed
        assert _git(repo, "branch", "--list", lanes[name]["branch"]).stdout == ""
    # Each lane's done/ was drained into the main checkout before its removal.
    landed = sorted(path.name for path in (repo / _PRDS / "done").iterdir())
    assert landed == ["00001-a.md", "00002-b.md"]
    # The wave's own assembly worktree and branch belong to no lane: they stay.
    ref = f"wave/{saved['id']}/assembly"
    assert saved["assembly"]["branch"] == ref
    assert saved["assembly"]["head_sha"] == _git(repo, "rev-parse", ref).stdout.strip()
    assembly = Path(saved["assembly"]["worktree"])
    assert assembly.resolve() == (tmp_path / f"proj-wave-{saved['id']}").resolve()
    assert assembly.is_dir()


@pytest.mark.parametrize("reason", ["conflict", "checks_failed"])
def test_kept_lane_keeps_its_done_prds_and_worktree(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    reason: str,
) -> None:
    repo, wave_path = _launched(tmp_path, monkeypatch, 2, CLASH_SEED)
    clashing = reason == "conflict"
    merged = _finish(wave_path, "l1", "")
    _commit(merged, _clashing_edits("l1") if clashing else {"x/a.py": "# l1\n"}, "l1")
    kept = _finish(wave_path, "l2", "")
    _commit(kept, _clashing_edits("l2") if clashing else {"y/b.py": "# l2\n"}, "l2")
    _to_done(merged, "00001-a.md")
    _to_done(kept, "00002-b.md")

    def run_checks(cwd: Path) -> subprocess.CompletedProcess:
        # Only l2's own file breaks the checks, and only in the other case.
        if clashing or not (Path(cwd) / "y/b.py").exists():
            return _checks_pass(cwd)
        return subprocess.CompletedProcess(["bash", "release-checks"], 3, "", "broken")

    assert wave_assemble.assemble(repo, wave_path, run_checks=run_checks) == 3
    saved, lanes = _saved(repo, wave_path)
    wave_id = saved["id"]
    assert (lanes["l1"]["status"], lanes["l2"]["status"]) == ("assembled", reason)
    assert saved["status"] == "assembled_partial"
    assert (saved["assembly"]["merged"], saved["assembly"]["kept"]) == (["l1"], ["l2"])
    assert not lanes["l2"].get("worktree_removed"), lanes["l2"]
    assert kept.is_dir()
    assert _git(repo, "branch", "--list", lanes["l2"]["branch"]).stdout.strip()
    assert (kept / _PRDS / "done" / "00002-b.md").exists()
    assert not (repo / _PRDS / "done" / "00002-b.md").exists()
    report = _autopilot(repo) / "reports" / f"{wave_id}-wave.md"
    text = report.read_text(encoding="utf-8")
    assert f"- 00002-b.md: Wave {wave_id}, lane l2, unassembled" in text, text
    assert f"- 00001-a.md: Wave {wave_id}, lane l1, done" in text, text


def _snapshot(repo: Path, kept: Path) -> dict[str, str]:
    """Everything a second `assemble` must leave exactly as it found it: the
    main checkout's whole dev/local, the kept lane's PRD folders, and the
    repo's refs and registered worktrees."""
    snapshot = {
        str(path.relative_to(repo)): path.read_text(encoding="utf-8")
        for path in sorted((repo / "dev" / "local").rglob("*"))
        if path.is_file()
    }
    snapshot["kept prds"] = "\n".join(
        str(path.relative_to(kept)) for path in sorted((kept / _PRDS).rglob("*"))
    )
    refs = _git(repo, "for-each-ref", "--format=%(refname) %(objectname)")
    snapshot["refs"] = refs.stdout
    snapshot["worktrees"] = _git(repo, "worktree", "list", "--porcelain").stdout
    return snapshot


def test_rerun_is_idempotent(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo, wave_path = _launched(tmp_path, monkeypatch, 2, CLASH_SEED)
    merged = _finish(wave_path, "l1", "")
    _commit(merged, _clashing_edits("l1"), "l1 change")
    kept = _finish(wave_path, "l2", "")
    _commit(kept, _clashing_edits("l2"), "l2 change")
    for worktree, batch, prd in (
        (merged, "202609260800", "00001-a.md"),
        (kept, LANE_BATCH, "00002-b.md"),
    ):
        _batched(worktree, batch)
        _to_done(worktree, prd)
        _write(
            worktree,
            {
                f"{_AP}/loop-metrics.jsonl": _jsonl([{"prd": prd, "wall_secs": 900}]),
                f"{_AP}/ledger/{batch}.jsonl": _jsonl([{"prd": prd, "event": "done"}]),
                f"{_AP}/deferred/{batch}-deferred.json": json.dumps(
                    {"batch_id": batch, "items": [{"op_id": batch, "prd": prd}]},
                ),
                f"{_AP}/reports/{prd}-review.md": f"{prd} review\n",
                f"dev/local/reviews/{prd}-findings.md": f"{prd} findings\n",
            },
        )
    assert wave_assemble.assemble(repo, wave_path, run_checks=_checks_pass) == 3
    first = _snapshot(repo, kept)
    assert wave_assemble.assemble(repo, wave_path, run_checks=_checks_pass) == 3
    assert _snapshot(repo, kept) == first
