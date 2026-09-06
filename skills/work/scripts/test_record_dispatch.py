"""Tests for record_dispatch.py — the /work dispatch timing ledger (PRD 00168).

Every case drives the real module against a temporary project tree holding
``dev/local/autopilot/``, because the script's whole contract is where and
whether a line lands: the working file, its ``ledger/`` mirror, or nowhere at
all when no autopilot dir resolves. Time is pinned through the module's own
``time`` name so the elapsed arithmetic is asserted, not eyeballed.

This file holds the ``end`` verb's tests. Its siblings
(test_record_dispatch_handoff.py, test_record_dispatch_start.py,
test_record_dispatch_append_row.py, test_record_dispatch_open_ids.py) hold
the rest, split out to stay under the file size limit; all of them load
record_dispatch.py and share their helpers through
record_dispatch_testutil.py.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

_TESTUTIL_PATH = Path(__file__).with_name("record_dispatch_testutil.py")
_TESTUTIL_SPEC = importlib.util.spec_from_file_location(
    "record_dispatch_testutil",
    _TESTUTIL_PATH,
)
assert _TESTUTIL_SPEC is not None and _TESTUTIL_SPEC.loader is not None
_testutil = importlib.util.module_from_spec(_TESTUTIL_SPEC)
_TESTUTIL_SPEC.loader.exec_module(_testutil)

record_dispatch = _testutil.record_dispatch
_project = _testutil.project
_rows = _testutil.rows
_pin_clock = _testutil.pin_clock


def test_end_after_a_start_row_computes_elapsed_from_queued_at(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # The caller never handles a clock: the end row carries the difference
    # between its own stamp and the start row's, found by walking up from a
    # subdirectory the way every autopilot script resolves the dir.
    autopilot = _project(tmp_path)
    record_dispatch.append_row(
        autopilot,
        {
            "id": "deadbeef",
            "kind": "ivan",
            "task": "3",
            "queued_at": 1000,
            "prompt_bytes": 42,
        },
    )
    monkeypatch.chdir(tmp_path / "proj" / "src")
    _pin_clock(monkeypatch, 1042.9)

    exit_code = record_dispatch.main(["end", "deadbeef", "--outcome", "ok"])

    assert exit_code == 0
    assert _rows(autopilot / "dispatch-metrics.jsonl")[-1] == {
        "id": "deadbeef",
        "ended_at": 1042,
        "elapsed_s": 42,
        "outcome": "ok",
        "detail": None,
    }


def test_a_second_end_on_the_same_id_is_its_own_row_measured_from_the_one_start(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # A verbatim re-dispatch keeps its id: the first attempt's end row stays,
    # the re-dispatch's return adds another, and both measure from the one
    # start row, so the last end row spans every attempt as documented.
    autopilot = _project(tmp_path)
    record_dispatch.append_row(
        autopilot,
        {
            "id": "deadbeef",
            "kind": "ivan",
            "task": "3",
            "queued_at": 1000,
            "prompt_bytes": 42,
        },
    )
    monkeypatch.chdir(tmp_path / "proj")
    _pin_clock(monkeypatch, 1010)
    assert record_dispatch.main(["end", "deadbeef", "--outcome", "lost"]) == 0
    _pin_clock(monkeypatch, 1030)

    exit_code = record_dispatch.main(["end", "deadbeef", "--outcome", "ok"])

    assert exit_code == 0
    ends = [
        row for row in _rows(autopilot / "dispatch-metrics.jsonl") if "ended_at" in row
    ]
    assert [(row["outcome"], row["elapsed_s"]) for row in ends] == [
        ("lost", 10),
        ("ok", 30),
    ]


def test_end_with_no_start_row_records_a_null_elapsed_and_exits_zero(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    # A lost or mistyped id must not turn a telemetry call into a failure the
    # dispatch pays for; the row still lands so the outcome is on record, and
    # stderr says why the elapsed time is null.
    autopilot = _project(tmp_path)
    monkeypatch.chdir(tmp_path / "proj")
    _pin_clock(monkeypatch, 2000)

    exit_code = record_dispatch.main(
        ["end", "cafebabe", "--outcome", "timeout", "--detail", "watchdog 45 min"],
    )

    assert exit_code == 0
    assert "no start row for cafebabe" in capsys.readouterr().err
    assert _rows(autopilot / "dispatch-metrics.jsonl") == [
        {
            "id": "cafebabe",
            "ended_at": 2000,
            "elapsed_s": None,
            "outcome": "timeout",
            "detail": "watchdog 45 min",
        },
    ]


def test_end_names_a_skipped_unparseable_line_even_when_the_start_row_is_found(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    # A garbage line in the working copy is reported whether or not the
    # lookup succeeds; a warning that depends on where the garbage sits
    # relative to the match is a warning nobody can rely on.
    autopilot = _project(tmp_path)
    (autopilot / "dispatch-metrics.jsonl").write_text(
        'not json\n{"id":"deadbeef","kind":"ivan","task":"1","queued_at":1000,"prompt_bytes":9}\n',
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path / "proj")
    _pin_clock(monkeypatch, 6000)

    exit_code = record_dispatch.main(["end", "deadbeef", "--outcome", "ok"])

    assert exit_code == 0
    err = capsys.readouterr().err
    assert "skipped 1 unparseable line" in err
    assert "no start row" not in err
    last = (
        (autopilot / "dispatch-metrics.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()[-1]
    )
    assert json.loads(last)["elapsed_s"] == 5000


def test_end_after_handoff_reports_null_elapsed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # A handoff mid-dispatch means part of the window was spent away from the
    # work, not on it; the clock cannot tell idle time from working time, so
    # it must refuse to claim a number at all.
    autopilot = _project(tmp_path)
    record_dispatch.append_row(
        autopilot,
        {
            "id": "deadbeef",
            "kind": "ivan",
            "task": "3",
            "queued_at": 1000,
            "prompt_bytes": 42,
        },
    )
    record_dispatch.append_row(
        autopilot,
        {
            "kind": "handoff",
            "site": "build",
            "edge": "leave",
            "at": 1020,
            "phase": "build",
            "prd": "x.md",
        },
    )
    monkeypatch.chdir(tmp_path / "proj")
    _pin_clock(monkeypatch, 1042)

    exit_code = record_dispatch.main(["end", "deadbeef", "--outcome", "ok"])

    assert exit_code == 0
    assert _rows(autopilot / "dispatch-metrics.jsonl")[-1] == {
        "id": "deadbeef",
        "ended_at": 1042,
        "elapsed_s": None,
        "outcome": "ok",
        "detail": "spans handoff; ",
    }


def test_end_without_handoff_keeps_elapsed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    autopilot = _project(tmp_path)
    record_dispatch.append_row(
        autopilot,
        {
            "id": "deadbeef",
            "kind": "ivan",
            "task": "3",
            "queued_at": 1000,
            "prompt_bytes": 42,
        },
    )
    monkeypatch.chdir(tmp_path / "proj")
    _pin_clock(monkeypatch, 1042)

    exit_code = record_dispatch.main(["end", "deadbeef", "--outcome", "ok"])

    assert exit_code == 0
    last = _rows(autopilot / "dispatch-metrics.jsonl")[-1]
    assert isinstance(last["elapsed_s"], int)
    assert last["elapsed_s"] == 42
    assert last["detail"] is None


def test_end_after_handoff_with_detail_prepends_the_spans_handoff_prefix(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # The prefix must prepend to whatever detail the caller gave, not replace
    # it, so the original reason for the outcome still reaches the row.
    autopilot = _project(tmp_path)
    record_dispatch.append_row(
        autopilot,
        {
            "id": "deadbeef",
            "kind": "ivan",
            "task": "3",
            "queued_at": 1000,
            "prompt_bytes": 42,
        },
    )
    record_dispatch.append_row(
        autopilot,
        {
            "kind": "handoff",
            "site": "build",
            "edge": "leave",
            "at": 1020,
            "phase": "build",
            "prd": "x.md",
        },
    )
    monkeypatch.chdir(tmp_path / "proj")
    _pin_clock(monkeypatch, 1042)

    exit_code = record_dispatch.main(
        ["end", "deadbeef", "--outcome", "ok", "--detail", "watchdog 45 min"],
    )

    assert exit_code == 0
    last = _rows(autopilot / "dispatch-metrics.jsonl")[-1]
    assert last["elapsed_s"] is None
    assert last["detail"] == "spans handoff; watchdog 45 min"


@pytest.mark.parametrize(
    "handoff_at",
    [1000, 1042, 900],
    ids=["at_queued_at", "at_now", "before_queued_at"],
)
def test_end_ignores_a_handoff_outside_the_open_window(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    handoff_at: int,
) -> None:
    # "Strictly between" excludes both endpoints, and a handoff from before
    # this dispatch even opened is not this dispatch's idle time either.
    autopilot = _project(tmp_path)
    record_dispatch.append_row(
        autopilot,
        {
            "id": "deadbeef",
            "kind": "ivan",
            "task": "3",
            "queued_at": 1000,
            "prompt_bytes": 42,
        },
    )
    record_dispatch.append_row(
        autopilot,
        {
            "kind": "handoff",
            "site": "build",
            "edge": "leave",
            "at": handoff_at,
            "phase": "build",
            "prd": "x.md",
        },
    )
    monkeypatch.chdir(tmp_path / "proj")
    _pin_clock(monkeypatch, 1042)

    exit_code = record_dispatch.main(["end", "deadbeef", "--outcome", "ok"])

    assert exit_code == 0
    last = _rows(autopilot / "dispatch-metrics.jsonl")[-1]
    assert last["elapsed_s"] == 42
    assert last["detail"] is None
