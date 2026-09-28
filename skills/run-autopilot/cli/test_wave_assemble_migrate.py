#!/usr/bin/env python3
"""Tests for cli/wave_assemble.py - `migrate_lane`, and what `assemble` does
once a lane's merge is settled: draining the lane's own docs/dev/project-management into the main
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

_AP = "docs/dev/project-management/autopilot"
_PRDS = "docs/dev/project-management/prds"
LANE_BATCH = "202609260900"
# A second lane's batch: no two fixtures below share one id, so a tag lifted
# from a constant instead of the lane's own state.json fails somewhere.
DISPATCH_BATCH = "202609261100"
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
    batch: str,
) -> None:
    """Every row arrived once, kept its own fields, and gained the lane's tags:
    the lane name, the wave id, and the batch id this lane's own state.json
    named, each under its own key."""
    assert len(migrated) == len(source)
    for row, before in zip(migrated, source, strict=True):
        assert {key: row[key] for key in before} == before, row
        assert (row["lane"], row["wave"]) == (lane, wave_id), row
        assert row["batch"] == batch, row


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
    # The row carries no batch of its own: the only batch it can gain is the
    # one this lane's state.json named.
    metric = {"prd": "00001-a.md", "wall_secs": 5400}
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
        LANE_BATCH,
    )
    metrics = _rows(_autopilot(repo) / "loop-metrics.jsonl")
    assert metrics[0] == earlier, metrics
    _assert_tagged(metrics[1:], [metric], "l1", wave_id, LANE_BATCH)


def test_dispatch_rows_migrate_too(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo, wave_path = _launched(tmp_path, monkeypatch, 1)
    worktree = _finish(wave_path, "l1", "")
    _commit(worktree, {"x/a.py": "# l1\n"}, "l1 change")
    # A different batch from the ledger test's: the tag is read, not constant.
    _batched(worktree, DISPATCH_BATCH)
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
    _assert_tagged(migrated, dispatch, "l1", wave_id, DISPATCH_BATCH)


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
    # A stall the lane filed against a PRD that is not the lane's own: the item
    # keeps the PRD it names, never the lane's first one.
    items.append(
        {"type": "stall", "detail": "d3", "op_id": "l1-3", "prd": "00009-other.md"},
    )
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
    foreign = next(item for item in content["items"] if item["op_id"] == "l1-3")
    assert foreign["prd"] == "00009-other.md", foreign
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
    saved, lanes = _saved(repo, wave_path)
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
    # The report labels every PRD by the folder it actually reached, including
    # the ones no lane listed in its own `prds`.
    wave_id = saved["id"]
    report = _autopilot(repo) / "reports" / f"{wave_id}-wave.md"
    text = report.read_text(encoding="utf-8")
    for prd, lane, label in (
        ("00001-a.md", "l1", "done"),
        ("00080-parked.md", "l1", "parked"),
        ("00081-parked.md", "l2", "parked"),
        ("00082-next.md", "l2", "backlog"),
        ("00002-b.md", "l2", "backlog"),
    ):
        assert f"- {prd}: Wave {wave_id}, lane {lane}, {label}" in text, text


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
    # Why l2 was kept out is in the report, not only in wave.json.
    conflicts = text[text.index("## Assembly conflicts") :]
    assert lanes["l2"]["conflict_detail"] in conflicts, conflicts


# Each lane's own batch id and its own loop-metrics rows: 3 sessions, 8100 wall
# seconds (2.25 hours) and $1.75 captured across the wave.
_REPORT_LANES: tuple[tuple[str, str, list[dict]], ...] = (
    (
        "l1",
        "202609260600",
        [
            {"prd": "00001-a.md", "wall_secs": 5400, "cost_usd": 1.5},
            {"prd": "00001-a.md", "wall_secs": 1800},
        ],
    ),
    (
        "l2",
        "202609260700",
        [{"prd": "00002-b.md", "wall_secs": 900, "cost_usd": 0.25}],
    ),
)


# Already in the main checkout's own loop-metrics.jsonl before any lane
# migrates into it, tagged with a wave id that is not this test's wave: a
# `_wave_rows` that dropped or weakened its wave-id filter would fold this
# into the totals below, whose real total is otherwise nowhere near it.
_FOREIGN_WAVE_ROW = {
    "wave": "some-other-wave-id",
    "wall_secs": 999999,
    "cost_usd": 999.99,
}


def test_wave_report_states_the_real_base_totals_and_lane_batches(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo, wave_path = _launched(tmp_path, monkeypatch, 2, CLASH_SEED)
    _write(repo, {f"{_AP}/loop-metrics.jsonl": _jsonl([_FOREIGN_WAVE_ROW])})
    for name, batch, rows in _REPORT_LANES:
        worktree = _finish(wave_path, name, "")
        _commit(worktree, _clashing_edits(name), f"{name} change")
        _batched(worktree, batch)
        _write(worktree, {f"{_AP}/loop-metrics.jsonl": _jsonl(rows)})
    # l2 edits the lines l1 already changed, so it is kept out on conflict.
    assert wave_assemble.assemble(repo, wave_path, run_checks=_checks_pass) == 3
    saved, lanes = _saved(repo, wave_path)
    wave_id = saved["id"]
    report = _autopilot(repo) / "reports" / f"{wave_id}-wave.md"
    text = report.read_text(encoding="utf-8")
    header = text[: text.index("## ")]
    for token in (
        wave_id,
        saved["base_branch"],
        saved["base_sha"][:7],
        saved["assembly"]["branch"],
        saved["assembly"]["head_sha"][:7],
    ):
        assert token in header, header
    # The foreign row actually landed in the file: the exclusion below is
    # proven, not merely assumed.
    migrated = _rows(_autopilot(repo) / "loop-metrics.jsonl")
    assert _FOREIGN_WAVE_ROW in migrated, migrated
    assert "totals: 3 sessions, 2.25 wall hours, $1.75 captured cost" in text, text
    for name, batch, _rows_seeded in _REPORT_LANES:
        row = [line for line in text.splitlines() if lanes[name]["branch"] in line]
        assert len(row) == 1, row
        assert batch in row[0], row[0]
    conflicts = text[text.index("## Assembly conflicts") :]
    assert lanes["l2"]["conflict_detail"] in conflicts, conflicts


def test_wave_report_is_mirrored_into_the_durable_ledger(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo, wave_path = _launched(tmp_path, monkeypatch, 1)
    worktree = _finish(wave_path, "l1", "")
    _commit(worktree, {"x/a.py": "# l1\n"}, "l1 change")
    _to_done(worktree, "00001-a.md")
    assert wave_assemble.assemble(repo, wave_path, run_checks=_checks_pass) == 0
    wave_id = wave.load(wave_path)["id"]
    report = _autopilot(repo) / "reports" / f"{wave_id}-wave.md"
    mirror = _autopilot(repo) / "ledger" / f"{wave_id}-wave.md"
    report_text = report.read_text(encoding="utf-8")
    mirror_text = mirror.read_text(encoding="utf-8")
    assert "## PRDs" in report_text, report_text
    assert mirror_text == report_text, (mirror_text, report_text)


def _snapshot(repo: Path, kept: Path) -> dict[str, str]:
    """Everything a second `assemble` must leave exactly as it found it: the
    main checkout's whole docs/dev/project-management, the kept lane's PRD folders, and the
    repo's refs and registered worktrees."""
    snapshot = {
        str(path.relative_to(repo)): path.read_text(encoding="utf-8")
        for path in sorted((repo / "docs" / "dev" / "project-management").rglob("*"))
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
                f"docs/dev/project-management/reviews/{prd}-findings.md": f"{prd} findings\n",
            },
        )
    assert wave_assemble.assemble(repo, wave_path, run_checks=_checks_pass) == 3
    # Each lane's per-PRD review report and findings reached the main checkout
    # before its worktree could take them down with it.
    for prd in ("00001-a.md", "00002-b.md"):
        review = _autopilot(repo) / "reports" / f"{prd}-review.md"
        findings = repo / "docs" / "dev" / "project-management" / "reviews" / f"{prd}-findings.md"
        assert review.read_text(encoding="utf-8") == f"{prd} review\n", review
        assert findings.read_text(encoding="utf-8") == f"{prd} findings\n", findings
    first = _snapshot(repo, kept)
    assert wave_assemble.assemble(repo, wave_path, run_checks=_checks_pass) == 3
    assert _snapshot(repo, kept) == first


# Two names no other fixture here uses: a report that names a held PRD from a
# constant instead of from what the lane held cannot satisfy both.
HELD_OUTSIDE_ROSTER = ("00085-parked.md", "00096-shelved.md")


@pytest.mark.parametrize("held_prd", HELD_OUTSIDE_ROSTER)
def test_rerun_report_still_names_a_prd_outside_the_lane_roster(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    held_prd: str,
) -> None:
    repo, wave_path = _launched(tmp_path, monkeypatch, 2)
    first_lane = _finish(wave_path, "l1", "")
    _commit(first_lane, {"x/a.py": "# l1\n"}, "l1 change")
    _to_done(first_lane, "00001-a.md")
    holder = _finish(wave_path, "l2", "")
    _commit(holder, {"y/b.py": "# l2\n"}, "l2 change")
    _to_done(holder, "00002-b.md")
    # Nobody listed held_prd in l2's own `prds`: the lane only ever held it,
    # parked. l1 never held it, and neither lane's edits clash, so both merge and
    # the first run takes both worktrees down with it - a second run can only
    # name this PRD from what the first run recorded. The holder is deliberately
    # NOT the first lane in `order`: crediting every stray PRD to lane one is a
    # guess, not a record.
    _write(holder, {f"{_PRDS}/hold/{held_prd}": "parked in l2\n"})
    for run in ("first", "second"):
        assert wave_assemble.assemble(repo, wave_path, run_checks=_checks_pass) == 0
        saved, lanes = _saved(repo, wave_path)
        assert lanes["l2"]["worktree_removed"] is True, (run, lanes["l2"])
        wave_id = saved["id"]
        report = _autopilot(repo) / "reports" / f"{wave_id}-wave.md"
        prds = report.read_text(encoding="utf-8")
        prds = prds[prds.index("## PRDs") :]
        held = f"- {held_prd}: Wave {wave_id}, lane l2, parked"
        assert held in prds, (run, prds)
        assert f"- 00001-a.md: Wave {wave_id}, lane l1, done" in prds, (run, prds)
        assert f"- 00002-b.md: Wave {wave_id}, lane l2, done" in prds, (run, prds)
        # Only the lane that held it may be credited with it: reading the main
        # checkout back is not remembering what each lane held.
        assert f"- {held_prd}: Wave {wave_id}, lane l1," not in prds, (run, prds)


# ── crash-safety on rerun ─────────────────────────────────────────────────


def test_assemble_adopts_a_preexisting_assembly_worktree_after_a_crash(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo, wave_path = _launched(tmp_path, monkeypatch, 1)
    worktree = _finish(wave_path, "l1", "")
    _commit(worktree, {"x/a.py": "# l1\n"}, "l1 change")
    _to_done(worktree, "00001-a.md")
    loaded = wave.load(wave_path)
    wave_id, base_sha = loaded["id"], loaded["base_sha"]
    branch = wave_assemble.WAVE_ASSEMBLY_BRANCH_FMT.format(wave_id=wave_id)
    assembly = Path(
        wave_assemble.WAVE_ASSEMBLY_WORKTREE_FMT.format(
            repo_parent=repo.parent,
            repo_name=repo.name,
            wave_id=wave_id,
        ),
    )
    # A crash between `git worktree add` and the end of the per-lane loop:
    # the worktree is registered and present on disk, but wave.json never
    # learned about it.
    _git(repo, "worktree", "add", str(assembly), "-b", branch, base_sha)
    assert "assembly" not in wave.load(wave_path)
    assert wave_assemble.assemble(repo, wave_path, run_checks=_checks_pass) == 0
    saved = wave.load(wave_path)
    assert saved["status"] == "assembled"
    assert Path(saved["assembly"]["worktree"]).resolve() == assembly.resolve()
    assert saved["assembly"]["branch"] == branch
    assert assembly.is_dir()
    # Adopted, not recreated: git still lists this worktree exactly once.
    listed = _git(repo, "worktree", "list").stdout
    assert listed.count(assembly.name) == 1, listed
    assert (repo / _PRDS / "done" / "00001-a.md").exists()


def test_assemble_tolerates_a_lane_worktree_removed_before_its_flag_was_saved(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo, wave_path = _launched(tmp_path, monkeypatch, 1)
    worktree = _finish(wave_path, "l1", "")
    _commit(worktree, {"x/a.py": "# l1\n"}, "l1 change")
    _to_done(worktree, "00001-a.md")
    assert wave_assemble.assemble(repo, wave_path, run_checks=_checks_pass) == 0
    _, lanes = _saved(repo, wave_path)
    assert lanes["l1"]["worktree_removed"] is True, lanes["l1"]
    assert not worktree.exists(), worktree
    # A crash between the real `git worktree remove` and the moment its own
    # flag was saved: the worktree is truly gone, but wave.json never
    # learned it - a rerun must not choke on the missing path.
    with wave.locked(wave_path):
        loaded = wave.load(wave_path)
        lane = next(each for each in loaded["lanes"] if each["name"] == "l1")
        del lane["worktree_removed"]
        wave.save(wave_path, loaded)
    assert not wave.load(wave_path)["lanes"][0].get("worktree_removed")
    assert wave_assemble.assemble(repo, wave_path, run_checks=_checks_pass) == 0
    assert wave_assemble.assemble(repo, wave_path, run_checks=_checks_pass) == 0
    landed = [path.name for path in (repo / _PRDS / "done").iterdir()]
    assert landed == ["00001-a.md"], landed


# ── _migrate_jsonl and _wave_rows: a blank line in the file ──────────────


def test_migrate_jsonl_skips_a_blank_or_whitespace_only_line(
    tmp_path: Path,
) -> None:
    # A realistic artifact of an interrupted append to a file long-running
    # loops write to: the well-formed lines around it must still land.
    lane_ap = tmp_path / "lane_ap"
    main_ap = tmp_path / "main_ap"
    lane_ap.mkdir()
    main_ap.mkdir()
    rows = [
        {"prd": "00001-a.md", "wall_secs": 900},
        {"prd": "00002-b.md", "wall_secs": 60},
    ]
    text = "\n".join([json.dumps(rows[0]), "", "   ", json.dumps(rows[1])]) + "\n"
    (lane_ap / "loop-metrics.jsonl").write_text(text, encoding="utf-8")
    wave_assemble._migrate_jsonl(lane_ap, main_ap, {"lane": "l1", "wave": "w1"})
    migrated = _rows(main_ap / "loop-metrics.jsonl")
    assert len(migrated) == 2, migrated
    for row, before in zip(migrated, rows, strict=True):
        assert {key: row[key] for key in before} == before, row
        assert (row["lane"], row["wave"]) == ("l1", "w1"), row


def test_wave_rows_skips_a_blank_or_whitespace_only_line(tmp_path: Path) -> None:
    main = tmp_path / "main"
    ap_dir = main / _AP
    ap_dir.mkdir(parents=True)
    rows = [
        {"wave": "w1", "wall_secs": 900},
        {"wave": "w2", "wall_secs": 60},
        {"wave": "w1", "wall_secs": 300},
    ]
    text = (
        "\n".join(
            [json.dumps(rows[0]), "", json.dumps(rows[1]), "   ", json.dumps(rows[2])],
        )
        + "\n"
    )
    (ap_dir / "loop-metrics.jsonl").write_text(text, encoding="utf-8")
    # Every well-formed line is still processed and the wave-id filter still
    # applies: only the blank/whitespace line is skipped, nothing else changes.
    assert wave_assemble._wave_rows(main, "w1") == [rows[0], rows[2]]
