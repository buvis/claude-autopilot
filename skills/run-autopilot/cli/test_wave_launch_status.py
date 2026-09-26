#!/usr/bin/env python3
"""Tests for cli/wave_launch.py's `status` and the `wave status` verb (PRD 00214).

Split off `test_wave_launch_abort.py` when that file reached the 800-line style
limit; the abort and `_pgid_alive` proofs stayed there. Every proof here runs
against a throwaway `git init` repo under `tmp_path`, never this checkout's own
backlog or `dev/local/autopilot/wave.json`, and no real loop is ever started.

The launch-side helpers live in the sibling `test_wave_launch` module and the
launched-wave fixture in `test_wave_launch_abort`; this file imports them rather
than restating them.

`status` renders a table, and these tests read it one cell at a time: each field
the contract lists (lane name, pid, state.prd, phase, next_phase, one count per
lifecycle dir, phase_end, signal, lane_status, abort_error) is its own cell,
separated by whitespace or a "|", and every row is the same width.

Cells are bound BY NAME, never by position and never by set membership, so the
table carries a header row whose cells are exactly these words:

    lane pid prd phase next_phase backlog wip done hold phase_end signal status

plus `abort_error` when a lane carries one. A field with nothing to show prints
"-": an empty cell would collapse under the whitespace split, and then no
operator (and no test) could tell which column a value belongs to.
"""

from __future__ import annotations

import copy
from pathlib import Path

import pytest

from cli import wave, wave_cli, wave_launch
from cli.test_wave_launch import (
    ONE_LANE,
    TWO_LANES,
    _autopilot,
    _dead_pid,
    _parse,
    _planned,
)
from cli.test_wave_launch_abort import _launched

_HEADERS = (
    "lane",
    "pid",
    "prd",
    "phase",
    "next_phase",
    "backlog",
    "wip",
    "done",
    "hold",
    "phase_end",
    "signal",
    "status",
)


def _cells(line: str) -> list[str]:
    """One rendered table line split into its cells."""
    return line.replace("|", " ").split()


def _row(rendered: str, name: str) -> list[str]:
    """The cells of the one rendered row that names lane `name`."""
    rows = [cells for line in rendered.splitlines() if name in (cells := _cells(line))]
    assert len(rows) == 1, rendered
    return rows[0]


def _by_name(rendered: str, name: str) -> dict[str, str]:
    """Lane `name`'s row as {column name: cell}, read through the header row so
    every assertion names the column it means instead of trusting its position."""
    headers = [
        cells
        for line in rendered.splitlines()
        if set(_HEADERS) <= set(cells := _cells(line))
    ]
    assert len(headers) == 1, rendered
    row = _row(rendered, name)
    assert len(row) == len(headers[0]), rendered
    return dict(zip(headers[0], row, strict=True))


def _lane_state(worktree: Path, state: str, metrics: list[str]) -> None:
    """A lane worktree's own loop state and metrics ledger."""
    _autopilot(worktree).mkdir(parents=True, exist_ok=True)
    (_autopilot(worktree) / "state.json").write_text(state, encoding="utf-8")
    ledger = _autopilot(worktree) / "ledger"
    ledger.mkdir(parents=True, exist_ok=True)
    (ledger / "loop-metrics.jsonl").write_text("".join(metrics), encoding="utf-8")


def _lane_prds(worktree: Path, counts: dict[str, int]) -> None:
    """`counts[folder]` PRD files in each of a worktree's lifecycle dirs."""
    for folder, count in counts.items():
        lifecycle = worktree / "dev" / "local" / "prds" / folder
        lifecycle.mkdir(parents=True, exist_ok=True)
        for index in range(count):
            (lifecycle / f"9000{index}-{folder}.md").write_text("x\n", encoding="utf-8")


# ── status ───────────────────────────────────────────────────────────────────


def test_status_derives_drained_from_a_dead_pid_and_empty_next_phase(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo, wave_path = _planned(tmp_path, monkeypatch, ONE_LANE, max_lanes=1)
    loaded = wave.load(wave_path)
    lane = loaded["lanes"][0]
    lane["pid"] = _dead_pid()
    lane["status"] = "running"
    _lane_state(
        Path(lane["worktree"]),
        '{"prd": "00001-a.md", "phase": "work", "next_phase": ""}',
        [
            '{"phase_end": "plan", "signal": "stale-amber"}\n',
            '{"phase_end": "review", "signal": "fresh-green"}\n',
            "{not json\n",
        ],
    )
    _lane_prds(Path(lane["worktree"]), {"backlog": 2, "wip": 1, "done": 3, "hold": 0})
    rendered = wave_launch.status(repo, loaded)
    cells = _by_name(rendered, lane["name"])
    assert cells["pid"] == str(lane["pid"])
    assert cells["prd"] == "00001-a.md"
    assert (cells["phase"], cells["next_phase"]) == ("work", "-")
    # the LAST PARSEABLE metrics line wins: not the unparseable final line, and
    # not the first line either. phase_end and signal are distinct columns, so
    # swapping them is a failure, not a set that still matches.
    assert (cells["phase_end"], cells["signal"]) == ("review", "fresh-green")
    assert "stale-amber" not in rendered
    # one count per lifecycle dir, each under its own name: a table that reports
    # them in another order tells the operator the wrong folder is filling up
    counts = [cells[folder] for folder in ("backlog", "wip", "done", "hold")]
    assert counts == ["2", "1", "3", "0"]
    assert cells["status"] == "drained"


def test_status_prints_dashes_for_a_lane_whose_worktree_is_gone(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo, wave_path = _planned(tmp_path, monkeypatch, TWO_LANES)
    loaded = wave.load(wave_path)
    live, gone = loaded["lanes"]
    live["pid"] = _dead_pid()
    live["status"] = "running"
    _lane_state(
        Path(live["worktree"]),
        '{"prd": "00001-a.md", "phase": "work", "next_phase": "review"}',
        ['{"phase_end": "work", "signal": "green"}\n'],
    )
    _lane_prds(Path(live["worktree"]), {"backlog": 1, "wip": 1, "done": 1, "hold": 1})
    gone["pid"] = None
    gone["status"] = "aborted"
    assert not Path(gone["worktree"]).exists()
    rendered = wave_launch.status(repo, loaded)
    dashes = _by_name(rendered, gone["name"])
    # nothing is left on disk to read, so every worktree-backed field is "-",
    # and the row is still as wide as the lane that does have a worktree
    worktree_backed = set(_HEADERS) - {"lane", "status"}
    assert {dashes[field] for field in worktree_backed} == {"-"}
    assert dashes["status"] == "aborted"
    assert set(_row(rendered, gone["name"])) == {gone["name"], "aborted", "-"}
    # the lane that still has a worktree is unaffected by its neighbour's dashes
    kept = _by_name(rendered, live["name"])
    assert kept["pid"] == str(live["pid"])
    assert [kept[folder] for folder in ("backlog", "wip", "done", "hold")] == ["1"] * 4
    assert (kept["phase_end"], kept["signal"]) == ("work", "green")


def test_status_shows_a_lanes_abort_error_as_an_extra_column(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo, wave_path = _planned(tmp_path, monkeypatch, ONE_LANE, max_lanes=1)
    loaded = wave.load(wave_path)
    lane = loaded["lanes"][0]
    lane["status"] = "abort_failed"
    lane["abort_error"] = "process group 4242 survived SIGKILL"
    rendered = wave_launch.status(repo, loaded)
    assert "process group 4242 survived SIGKILL" in rendered
    # the error rides the failing lane's OWN row, not a footnote somewhere
    row = _row(rendered, lane["name"])
    assert "abort_failed" in row
    assert {"process", "group", "4242", "survived", "SIGKILL"} <= set(row)
    # the column comes from the lane, not from boilerplate: a clean lane has none
    assert "survived SIGKILL" not in wave_launch.status(repo, wave.load(wave_path))


def test_status_shows_the_pid_of_a_lane_that_has_no_state_json_yet(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo, wave_path = _planned(tmp_path, monkeypatch, ONE_LANE, max_lanes=1)
    loaded = wave.load(wave_path)
    lane = loaded["lanes"][0]
    lane["pid"] = _dead_pid()
    lane["status"] = "running"
    worktree = Path(lane["worktree"])
    # A lane that has only just started: its worktree and ledger are on disk but
    # the loop has not written state.json yet. Only the fields that file feeds
    # are unknown - an operator must still be able to read the pid to kill it.
    ledger = _autopilot(worktree) / "ledger"
    ledger.mkdir(parents=True)
    (ledger / "loop-metrics.jsonl").write_text(
        '{"phase_end": "plan", "signal": "fresh-green"}\n',
        encoding="utf-8",
    )
    _lane_prds(worktree, {"backlog": 1, "wip": 2, "done": 0, "hold": 1})
    assert not (_autopilot(worktree) / "state.json").exists()
    cells = _by_name(wave_launch.status(repo, loaded), lane["name"])
    assert cells["pid"] == str(lane["pid"])
    assert [cells[folder] for folder in ("backlog", "wip", "done", "hold")] == [
        "1",
        "2",
        "0",
        "1",
    ]
    assert (cells["phase_end"], cells["signal"]) == ("plan", "fresh-green")
    assert cells["status"] == "unfinished"
    unknown = {field for field, value in cells.items() if value == "-"}
    assert unknown - {"abort_error"} == {"prd", "phase", "next_phase"}


def test_status_mutates_neither_the_wave_dict_nor_wave_json(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo, wave_path = _launched(tmp_path, monkeypatch, TWO_LANES)
    loaded = wave.load(wave_path)
    before_dict = copy.deepcopy(loaded)
    before_bytes = wave_path.read_bytes()
    assert wave_launch.status(repo, loaded).strip() != ""
    assert loaded == before_dict
    assert wave_path.read_bytes() == before_bytes


# ── the status verb ──────────────────────────────────────────────────────────


def test_run_status_prints_the_rendered_table(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    repo, wave_path = _planned(tmp_path, monkeypatch, TWO_LANES)
    capsys.readouterr()  # the fixture's own plan listing, not the verb's output
    assert wave_cli.run(_parse(["wave", "status"]), repo, wave_path) == 0
    printed = capsys.readouterr().out
    # the verb prints the rendered table and nothing else
    assert printed.strip() == wave_launch.status(repo, wave.load(wave_path)).strip()
    for lane in wave.load(wave_path)["lanes"]:
        assert lane["name"] in _row(printed, lane["name"])
