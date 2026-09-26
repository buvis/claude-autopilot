#!/usr/bin/env python3
"""Tests for cli/wave.py - the lane cut and wave.json I/O (PRD 00214).

`cut` is pinned on hand-built PRD texts (one `- **Location**:` line each, the
form `lane.named_paths` reads); the I/O half runs against a throwaway repo
under `tmp_path`.
"""

from __future__ import annotations

import builtins
import io
import json
import os
import re
import threading
from datetime import datetime
from pathlib import Path

import pytest

from cli import wave

REPO = Path("/work/proj")
WAVE_ID = "202609261200"
_DROP = object()


def _prd(*paths: str) -> str:
    """A PRD naming `paths` on one `- **Location**:` line."""
    spans = ", ".join(f"`{path}`" for path in paths)
    return f"# A PRD\n\n- **Location**: {spans}\n"


def _groups(lanes: list[wave.Lane]) -> list[tuple[str, ...]]:
    return [each.prds for each in lanes]


def _unstamped(*prds: str, paths: tuple[str, ...]) -> wave.Lane:
    return wave.Lane(name="", order=0, branch="", worktree="", prds=prds, paths=paths)


def _lane_dict(repo: Path, order: int, *prds: str) -> dict:
    return {
        "name": f"l{order}",
        "order": order,
        "branch": f"wave/{WAVE_ID}/l{order}",
        "worktree": f"{repo.parent}/{repo.name}-l{order}",
        "prds": list(prds),
        "paths": [f"x/{order}.py"],
        "status": "planned",
        "pid": None,
        "started_at": None,
        "worktree_created": False,
        "abort_error": None,
    }


def _wave(repo: Path, status: str = "planned") -> dict:
    """A structurally sound two-lane wave.json dict for `repo`."""
    return {
        "id": WAVE_ID,
        "status": status,
        "repo": str(repo),
        "base_branch": None,
        "base_sha": None,
        "review_slots": 3,
        "created_at": "2026-09-26T12:00:00+00:00",
        "lanes": [_lane_dict(repo, 1, "00001-a.md"), _lane_dict(repo, 2, "00002-b.md")],
        "held_back": [],
    }


def _set(target: dict, field: str, value: object) -> None:
    if value is _DROP:
        del target[field]
    else:
        target[field] = value


def _repo(tmp_path: Path, prds: dict[str, str]) -> tuple[Path, Path]:
    """A repo with `prds` in its backlog; returns (repo, wave.json path)."""
    repo = tmp_path / "proj"
    backlog = repo / "dev" / "local" / "prds" / "backlog"
    backlog.mkdir(parents=True)
    for name, text in prds.items():
        (backlog / name).write_text(text, encoding="utf-8")
    wave_path = repo / "dev" / "local" / "autopilot" / "wave.json"
    wave_path.parent.mkdir(parents=True)
    return repo, wave_path


# ── the cut ──────────────────────────────────────────────────────────────────


def test_cut_joins_prds_that_share_a_path() -> None:
    lanes, held_back = wave.cut(
        {
            "00001-a.md": _prd("x/a.py", "x/shared.py"),
            "00002-b.md": _prd("y/b.py"),
            "00003-c.md": _prd("z/c.py", "x/shared.py"),
            "00004-d.md": _prd("z/c.py", "w/d.py"),  # joins a only through c
        }
    )
    assert held_back == []
    assert _groups(lanes) == [("00001-a.md", "00003-c.md", "00004-d.md"), ("00002-b.md",)]
    assert set(lanes[0].paths) == {"x/a.py", "x/shared.py", "z/c.py", "w/d.py"}
    assert set(lanes[1].paths) == {"y/b.py"}
    for each in lanes:
        assert (each.name, each.order, each.branch, each.worktree) == ("", 0, "", "")
        assert (each.status, each.pid, each.worktree_created) == ("planned", None, False)


def test_cut_treats_a_directory_prefix_as_shared() -> None:
    lanes, _ = wave.cut(
        {
            "00001-dir.md": _prd("docs/guide"),
            "00002-file.md": _prd("docs/guide/intro.md"),
            "00003-sibling.md": _prd("docs/guidebook.md"),
        }
    )
    assert _groups(lanes) == [("00001-dir.md", "00002-file.md"), ("00003-sibling.md",)]
    assert wave.shares(frozenset({"docs/guide"}), frozenset({"docs/guide/intro.md"}))
    assert wave.shares(frozenset({"docs/guide/intro.md"}), frozenset({"docs/guide"}))
    assert wave.shares(frozenset({"docs"}), frozenset({"docs/guide/a/b.md"}))
    assert not wave.shares(frozenset({"docs/guide"}), frozenset({"docs/guidebook.md"}))


def test_append_only_files_never_join_lanes() -> None:
    text = _prd("CHANGELOG.md", "dev/bin/release-checks", "x/a.py")
    assert wave.prd_paths(text) == frozenset({"x/a.py"})
    lanes, held_back = wave.cut(
        {
            "00001-a.md": text,
            "00002-b.md": _prd("CHANGELOG.md", "dev/bin/release-checks", "y/b.py"),
            "00003-log.md": _prd("CHANGELOG.md"),
        }
    )
    assert _groups(lanes) == [("00001-a.md",), ("00002-b.md",)]
    owned = {path for each in lanes for path in each.paths}
    assert not owned & {"CHANGELOG.md", "dev/bin/release-checks"}
    assert held_back == [{"prd": "00003-log.md", "reason": "no named paths"}]


def test_force_shared_paths_pull_prds_into_one_lane() -> None:
    lanes, _ = wave.cut(
        {
            "00001-skill.md": _prd("skills/run-autopilot/SKILL.md", "docs/a.md"),
            "00002-other.md": _prd("x/b.py"),
            "00003-records.md": _prd("skills/run-autopilot/cli/records.py", "y/c.py"),
            "00004-schema.md": _prd("skills/run-autopilot/references/state-schema.md"),
        }
    )
    assert _groups(lanes) == [
        ("00001-skill.md", "00003-records.md", "00004-schema.md"),
        ("00002-other.md",),
    ]
    assert not wave.shares(
        frozenset({"skills/run-autopilot/SKILL.md"}),
        frozenset({"skills/run-autopilot/cli/lane.py"}),
    )


def test_cut_packs_components_into_max_lanes() -> None:
    big = ("00002-big.md", "00003-big.md", "00004-big.md")
    mid = ("00005-mid.md", "00006-mid.md")
    prds = {"00001-solo.md": _prd("a/one.py")}
    prds.update({name: _prd("b/shared.py") for name in big})
    prds.update({name: _prd("c/shared.py") for name in mid})
    prds = dict(sorted(prds.items()))
    # Largest component first; the singleton joins the lighter lane and the
    # lane lists its PRDs in sequence order.
    lanes, held_back = wave.cut(prds, max_lanes=2)
    assert held_back == []
    assert _groups(lanes) == [big, ("00001-solo.md", *mid)]
    (single,), _ = wave.cut(prds, max_lanes=1)
    assert single.prds == tuple(prds)
    wide, _ = wave.cut(prds)  # default max_lanes=3
    assert _groups(wide) == [big, mid, ("00001-solo.md",)]
    ties, _ = wave.cut(
        {
            "00001-p.md": _prd("p/shared.py"),
            "00002-q.md": _prd("q/shared.py"),
            "00003-q.md": _prd("q/shared.py"),
            "00004-p.md": _prd("p/shared.py"),
        }
    )
    assert _groups(ties) == [("00001-p.md", "00004-p.md"), ("00002-q.md", "00003-q.md")]


def test_prd_without_named_paths_is_held_back() -> None:
    lanes, held_back = wave.cut(
        {
            "00001-prose.md": "# Prose\n\nSee `cli/loop.py` in passing.\n",
            "00002-a.md": _prd("x/a.py"),
            "00003-empty.md": "",
        }
    )
    assert held_back == [
        {"prd": "00001-prose.md", "reason": "no named paths"},
        {"prd": "00003-empty.md", "reason": "no named paths"},
    ]
    assert _groups(lanes) == [("00002-a.md",)]
    assert wave.cut({}) == ([], [])


def test_cut_reads_nothing_from_disk(monkeypatch: pytest.MonkeyPatch) -> None:
    def _no_disk(*args: object, **kwargs: object) -> None:
        raise AssertionError("cut touched the filesystem")

    prds = {"00001-a.md": _prd("x/a.py"), "00002-b.md": _prd("x/a.py", "y/b.py")}
    with monkeypatch.context() as patch:
        patch.setattr(builtins, "open", _no_disk)
        patch.setattr(io, "open", _no_disk)
        for name in ("open", "stat", "scandir", "listdir"):
            patch.setattr(os, name, _no_disk)
        lanes, held_back = wave.cut(prds)
    assert (_groups(lanes), held_back) == ([("00001-a.md", "00002-b.md")], [])


# ── lane order ───────────────────────────────────────────────────────────────


def test_lane_order_puts_core_lanes_first() -> None:
    core_two = ("skills/run-autopilot/SKILL.md", "skills/run-autopilot/references/phase-build.md")
    packed = [
        _unstamped("00006-big.md", "00007-big.md", paths=("y/c.py",)),
        _unstamped("00001-docs.md", paths=("docs/a.md",)),
        _unstamped("00004-refs.md", paths=("skills/run-autopilot/references/x.md",)),
        _unstamped("00003-core.md", paths=core_two),
        _unstamped("00002-cli.md", paths=("skills/run-autopilot/cli/loop.py",)),
    ]
    stamped = wave._order_lanes(packed, WAVE_ID, REPO)
    ordered = sorted(stamped, key=lambda each: each.order)
    assert [(each.order, each.prds) for each in ordered] == [
        (1, ("00003-core.md",)),
        (2, ("00002-cli.md",)),
        (3, ("00004-refs.md",)),
        (4, ("00006-big.md", "00007-big.md")),
        (5, ("00001-docs.md",)),
    ]
    assert ordered[0].paths == core_two
    for each in ordered:
        n = each.order
        assert each.name == f"l{n}"
        assert each.branch == f"wave/{WAVE_ID}/l{n}"
        assert each.worktree == f"/work/proj-l{n}"


# ── wave.json I/O ────────────────────────────────────────────────────────────


def test_wave_json_round_trips(tmp_path: Path) -> None:
    path = tmp_path / "wave.json"
    assert wave.load(path) is None
    lane = wave.Lane(
        name="l1",
        order=1,
        branch=f"wave/{WAVE_ID}/l1",
        worktree="/work/proj-l1",
        prds=("00001-a.md", "00003-c.md"),
        paths=("x/a.py", "x/c.py"),
    )
    assert lane.as_dict() == {
        "name": "l1",
        "order": 1,
        "branch": f"wave/{WAVE_ID}/l1",
        "worktree": "/work/proj-l1",
        "prds": ["00001-a.md", "00003-c.md"],
        "paths": ["x/a.py", "x/c.py"],
        "status": "planned",
        "pid": None,
        "started_at": None,
        "worktree_created": False,
        "abort_error": None,
    }
    data = {**_wave(REPO), "lanes": [lane.as_dict()]}
    wave.save(path, data)
    assert wave.load(path) == data
    replaced = {**data, "status": "aborted"}
    wave.save(path, replaced)
    assert wave.load(path) == replaced
    assert [each.name for each in tmp_path.iterdir()] == ["wave.json"]


def test_locked_blocks_a_second_holder_until_the_first_releases(tmp_path: Path) -> None:
    wave_path = tmp_path / "wave.json"
    first_in, release, second_in = threading.Event(), threading.Event(), threading.Event()
    events: list[str] = []

    def first() -> None:
        with wave.locked(wave_path):
            events.append("first in")
            first_in.set()
            release.wait(5)
            events.append("first out")

    def second() -> None:
        first_in.wait(5)
        with wave.locked(wave_path):
            events.append("second in")
            second_in.set()

    threads = [threading.Thread(target=first, daemon=True), threading.Thread(target=second, daemon=True)]
    for thread in threads:
        thread.start()
    try:
        assert first_in.wait(5)
        assert not second_in.wait(0.3), "a second holder entered while the first held the lock"
    finally:
        release.set()
        for thread in threads:
            thread.join(5)
    assert events == ["first in", "first out", "second in"]


# ── plan ─────────────────────────────────────────────────────────────────────


def test_plan_writes_the_cut_as_a_planned_wave(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    repo, wave_path = _repo(
        tmp_path,
        {
            "00001-a.md": _prd("x/shared.py"),
            "00002-b.md": _prd("y/b.py"),
            "00003-c.md": _prd("x/shared.py", "z/c.py"),
            "00004-prose.md": "# Prose only\n",
        },
    )
    wave_path.write_text(json.dumps(_wave(repo, "aborted")), encoding="utf-8")
    assert wave.plan(repo, wave_path, max_lanes=3) == 0
    saved = json.loads(wave_path.read_text(encoding="utf-8"))
    assert re.fullmatch(r"\d{12}", saved["id"])
    top = (saved["status"], saved["repo"], saved["base_branch"], saved["base_sha"], saved["review_slots"])
    assert top == ("planned", str(repo), None, None, 3)
    datetime.fromisoformat(saved["created_at"])
    assert saved["held_back"] == [{"prd": "00004-prose.md", "reason": "no named paths"}]
    assert [(each["name"], each["prds"]) for each in saved["lanes"]] == [
        ("l1", ["00001-a.md", "00003-c.md"]),
        ("l2", ["00002-b.md"]),
    ]
    first = saved["lanes"][0]
    assert first["branch"] == f"wave/{saved['id']}/l1"
    assert first["worktree"] == f"{repo.parent}/{repo.name}-l1"
    assert (first["status"], first["pid"], first["worktree_created"]) == ("planned", None, False)
    assert wave._structural_errors(repo, saved) == []
    out = capsys.readouterr().out
    assert f"wave/{saved['id']}/l1" in out
    assert "00004-prose.md" in out
    assert wave.plan(repo, wave_path) == 1, "a fresh plan is itself a live wave"


@pytest.mark.parametrize("status", ["planned", "running", "abort_failed"])
def test_plan_refuses_a_live_wave(tmp_path: Path, capsys: pytest.CaptureFixture[str], status: str) -> None:
    repo, wave_path = _repo(tmp_path, {"00003-c.md": _prd("x/c.py")})
    before = json.dumps(_wave(repo, status))
    wave_path.write_text(before, encoding="utf-8")
    assert wave.plan(repo, wave_path) == 1
    assert wave_path.read_text(encoding="utf-8") == before
    assert status in capsys.readouterr().err


def test_plan_refuses_a_corrupt_wave_json(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    repo, wave_path = _repo(tmp_path, {"00001-a.md": _prd("x/a.py")})
    wave_path.write_text('{"id": "2026', encoding="utf-8")
    with pytest.raises(wave.WaveCorruptError):
        wave.load(wave_path)
    assert wave.plan(repo, wave_path) == 1
    assert wave_path.read_text(encoding="utf-8") == '{"id": "2026'
    captured = capsys.readouterr()
    assert "wave.json is corrupt" in captured.out + captured.err


def test_plan_refuses_a_structurally_invalid_wave_json(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    repo, wave_path = _repo(tmp_path, {"00001-a.md": _prd("x/a.py")})
    broken = _wave(repo)
    del broken["status"]
    before = json.dumps(broken)
    wave_path.write_text(before, encoding="utf-8")
    assert wave.plan(repo, wave_path) == 1
    assert wave_path.read_text(encoding="utf-8") == before
    captured = capsys.readouterr()
    assert "structurally invalid" in captured.out + captured.err
    assert "wave.json: malformed top-level field status" in captured.out + captured.err


@pytest.mark.parametrize("max_lanes", [0, -1])
def test_plan_refuses_max_lanes_below_one_before_cutting(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch, max_lanes: int
) -> None:
    def _no_cut(*args: object, **kwargs: object) -> None:
        raise AssertionError("plan called cut")

    repo, wave_path = _repo(tmp_path, {"00001-a.md": _prd("x/a.py")})
    monkeypatch.setattr(wave, "cut", _no_cut)
    assert wave.plan(repo, wave_path, max_lanes=max_lanes) == 1
    assert not wave_path.exists()
    captured = capsys.readouterr()
    assert captured.out + captured.err


# ── _structural_errors ───────────────────────────────────────────────────────


@pytest.mark.parametrize("status", ["planned", "running", "aborted", "abort_failed"])
def test_structural_errors_accepts_a_sound_wave(status: str) -> None:
    assert wave._structural_errors(REPO, _wave(REPO, status)) == []


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("id", _DROP),
        ("id", 202609261200),
        ("repo", _DROP),
        ("repo", None),
        ("status", _DROP),
        ("status", "bogus"),
        ("lanes", _DROP),
        ("lanes", []),
        ("lanes", {"l1": {}}),
        ("review_slots", _DROP),
        ("review_slots", 0),
        ("review_slots", "3"),
    ],
)
def test_structural_errors_names_a_malformed_top_level_field(field: str, value: object) -> None:
    broken = _wave(REPO)
    _set(broken, field, value)
    assert f"wave.json: malformed top-level field {field}" in wave._structural_errors(REPO, broken)


def test_structural_errors_rejects_a_wave_planned_for_another_repo() -> None:
    errors = wave._structural_errors(Path("/work/other"), _wave(REPO))
    assert "wave.json was planned for a different repo" in errors


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("order", _DROP),
        ("order", None),
        ("order", 0),
        ("order", -1),
        ("order", "1"),
        ("pid", "4242"),
        ("pid", 1.5),
        ("worktree_created", _DROP),
        ("worktree_created", 0),
        ("worktree_created", None),
        ("name", _DROP),
        ("name", None),
        ("branch", 7),
        ("worktree", None),
        ("status", 3),
        ("status", "bogus"),
        ("prds", "00001-a.md"),
        ("prds", []),
        ("prds", [7]),
        ("prds", ["backlog/00001-a.md"]),
    ],
)
def test_structural_errors_names_a_malformed_lane_field(field: str, value: object) -> None:
    broken = _wave(REPO)
    _set(broken["lanes"][0], field, value)
    errors = wave._structural_errors(REPO, broken)
    # The label is the lane's name, or its index when the name is unusable.
    expected = re.compile(rf"lane (l1|0|1): malformed field {field}")
    assert any(expected.fullmatch(error) for error in errors), errors


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("order", 1),
        ("name", "l1"),
        ("branch", f"wave/{WAVE_ID}/l1"),
        ("worktree", "/work/proj-l1"),
    ],
)
def test_structural_errors_rejects_a_value_two_lanes_share(field: str, value: object) -> None:
    broken = _wave(REPO)
    broken["lanes"][1][field] = value
    errors = wave._structural_errors(REPO, broken)
    expected = re.compile(rf"lane \S+ and lane \S+ both use {field} {re.escape(str(value))}")
    assert any(expected.fullmatch(error) for error in errors), errors


def test_structural_errors_rejects_a_prd_listed_in_two_lanes() -> None:
    broken = _wave(REPO)
    broken["lanes"][1]["prds"] = ["00002-b.md", "00001-a.md"]
    errors = wave._structural_errors(REPO, broken)
    assert "00001-a.md is listed in more than one lane" in errors


def test_structural_errors_rejects_a_prd_listed_twice_in_one_lane() -> None:
    broken = _wave(REPO)
    broken["lanes"][0]["prds"] = ["00001-a.md", "00001-a.md"]
    errors = wave._structural_errors(REPO, broken)
    assert "lane l1 lists 00001-a.md twice" in errors


def test_structural_errors_rejects_a_worktree_off_the_canonical_path() -> None:
    broken = _wave(REPO)
    broken["lanes"][0]["worktree"] = "/Users/someone/important"
    errors = wave._structural_errors(REPO, broken)
    assert "lane l1: worktree does not match the canonical path for order 1" in errors


def test_structural_errors_rejects_a_branch_off_the_canonical_name() -> None:
    broken = _wave(REPO)
    broken["lanes"][0]["branch"] = "wave/209901010000/l1"
    errors = wave._structural_errors(REPO, broken)
    assert len(errors) == 1, errors
    assert errors[0].startswith("lane l1: branch"), errors
