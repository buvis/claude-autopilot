"""Tests for record_dispatch.py's open_ids() — split out of
test_record_dispatch.py (PRD 00168) to stay under the file size limit. See
that file's module docstring for the shared testing approach.
"""

from __future__ import annotations

import importlib.util
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

_UNCLOSED_STARTS_ROWS = [
    {
        "id": "aaaaaaaa",
        "kind": "ivan",
        "task": "1",
        "queued_at": 1000,
        "prompt_bytes": 1,
    },
    {
        "id": "aaaaaaaa",
        "ended_at": 1010,
        "elapsed_s": 10,
        "outcome": "ok",
        "detail": None,
    },
    {
        "id": "bbbbbbbb",
        "kind": "pat",
        "task": "2",
        "queued_at": 2000,
        "prompt_bytes": 2,
    },
    {
        "kind": "handoff",
        "site": "build",
        "edge": "leave",
        "at": 2500,
        "phase": "build",
        "prd": "x.md",
    },
    {
        "id": "bbbbbbbb",
        "ended_at": 2010,
        "elapsed_s": 10,
        "outcome": "ok",
        "detail": None,
    },
    {
        "id": "cccccccc",
        "kind": "tess",
        "task": "3",
        "queued_at": 3000,
        "prompt_bytes": 3,
    },
]


def test_open_ids_lists_only_unclosed_starts(tmp_path: Path) -> None:
    # Two ids get both a start and an end row, one gets only a start, and a
    # handoff row carries neither queued_at nor id: only the truly open id
    # should surface.
    autopilot = _project(tmp_path)
    for row in _UNCLOSED_STARTS_ROWS:
        record_dispatch.append_row(autopilot, row)

    assert record_dispatch.open_ids(autopilot) == ["cccccccc"]


def test_open_ids_on_a_missing_working_file_returns_an_empty_list(
    tmp_path: Path,
) -> None:
    autopilot = _project(tmp_path)

    assert record_dispatch.open_ids(autopilot) == []


def test_open_ids_preserves_first_seen_order_across_multiple_open_ids(
    tmp_path: Path,
) -> None:
    # ids land in the file in an order that is neither alphabetical nor
    # numeric, so a result that happened to sort would still look plausible
    # without this.
    autopilot = _project(tmp_path)
    for row in (
        {
            "id": "cccccccc",
            "kind": "ivan",
            "task": "1",
            "queued_at": 1000,
            "prompt_bytes": 1,
        },
        {
            "id": "aaaaaaaa",
            "kind": "pat",
            "task": "2",
            "queued_at": 2000,
            "prompt_bytes": 2,
        },
        {
            "id": "bbbbbbbb",
            "kind": "tess",
            "task": "3",
            "queued_at": 3000,
            "prompt_bytes": 3,
        },
    ):
        record_dispatch.append_row(autopilot, row)

    assert record_dispatch.open_ids(autopilot) == ["cccccccc", "aaaaaaaa", "bbbbbbbb"]


def test_open_ids_skips_unparseable_lines_and_names_the_skipped_count_on_stderr(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    autopilot = _project(tmp_path)
    (autopilot / "dispatch-metrics.jsonl").write_text(
        "not json\n"
        '{"id":"deadbeef","kind":"ivan","task":"1","queued_at":1000,"prompt_bytes":9}\n'
        "also not json\n",
        encoding="utf-8",
    )

    ids = record_dispatch.open_ids(autopilot)

    assert ids == ["deadbeef"]
    assert "skipped 2 unparseable line" in capsys.readouterr().err


def test_open_ids_dedupes_an_id_with_two_start_rows_and_no_end(
    tmp_path: Path,
) -> None:
    # A retried dispatch reuses its id and opens a second start row (see
    # test_a_second_end_on_the_same_id_...); the id must still surface once.
    autopilot = _project(tmp_path)
    for row in (
        {
            "id": "deadbeef",
            "kind": "ivan",
            "task": "1",
            "queued_at": 1000,
            "prompt_bytes": 1,
        },
        {
            "id": "deadbeef",
            "kind": "ivan",
            "task": "1",
            "queued_at": 1050,
            "prompt_bytes": 1,
        },
    ):
        record_dispatch.append_row(autopilot, row)

    assert record_dispatch.open_ids(autopilot) == ["deadbeef"]


def test_open_ids_closes_an_id_whose_end_row_appears_before_its_start_row(
    tmp_path: Path,
) -> None:
    # An end row is "any parsed JSON object with id equal to that id and
    # ended_at present" - order within the file does not gate the match.
    autopilot = _project(tmp_path)
    for row in (
        {
            "id": "deadbeef",
            "ended_at": 1010,
            "elapsed_s": 10,
            "outcome": "ok",
            "detail": None,
        },
        {
            "id": "deadbeef",
            "kind": "ivan",
            "task": "1",
            "queued_at": 1000,
            "prompt_bytes": 1,
        },
    ):
        record_dispatch.append_row(autopilot, row)

    assert record_dispatch.open_ids(autopilot) == []
