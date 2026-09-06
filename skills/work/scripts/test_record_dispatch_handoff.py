"""Tests for record_dispatch.py's handoff verb — split out of
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
_rows = _testutil.rows
_pin_clock = _testutil.pin_clock
_run_handoff = _testutil.run_handoff


def test_handoff_writes_its_site_edge_stamp_phase_and_prd(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    autopilot = _project(tmp_path)
    monkeypatch.chdir(tmp_path / "proj")
    _pin_clock(monkeypatch, 3000)

    exit_code = record_dispatch.main(
        [
            "handoff",
            "--site",
            "review",
            "--edge",
            "leave",
            "--phase",
            "done",
            "--prd",
            "00168-record-dispatch-timing-telemetry-v1.md",
        ],
    )

    assert exit_code == 0
    assert _rows(autopilot / "dispatch-metrics.jsonl") == [
        {
            "kind": "handoff",
            "site": "review",
            "edge": "leave",
            "at": 3000,
            "phase": "done",
            "prd": "00168-record-dispatch-timing-telemetry-v1.md",
        },
    ]


def test_handoff_closes_open_rows_as_lost(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # A crash or forced handoff must not leave a start row open forever: the
    # id open_ids still reports gets a synthetic lost end row, stamped with
    # this invocation's own site and edge, before the handoff's own row.
    autopilot = _project(tmp_path)
    record_dispatch.append_row(
        autopilot,
        {
            "id": "aaaaaaaa",
            "kind": "ivan",
            "task": "1",
            "queued_at": 1000,
            "prompt_bytes": 1,
        },
    )
    monkeypatch.chdir(tmp_path / "proj")
    _pin_clock(monkeypatch, 4000)

    exit_code = _run_handoff("build", "leave", "review", "X")

    assert exit_code == 0
    expected_tail = [
        {
            "id": "aaaaaaaa",
            "ended_at": 4000,
            "elapsed_s": None,
            "outcome": "lost",
            "detail": "open at build/leave handoff",
        },
        {
            "kind": "handoff",
            "site": "build",
            "edge": "leave",
            "at": 4000,
            "phase": "review",
            "prd": "X",
        },
    ]
    assert _rows(autopilot / "dispatch-metrics.jsonl")[-2:] == expected_tail
    assert _rows(autopilot / "ledger" / "dispatch-metrics.jsonl")[-2:] == expected_tail


def test_handoff_leaves_closed_rows_alone(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # An id with an end row is not open, so it must not get a second,
    # synthetic lost row on top of its real outcome; only the handoff's own
    # row should land. Uses the resume edge to cover it alongside leave.
    autopilot = _project(tmp_path)
    record_dispatch.append_row(
        autopilot,
        {
            "id": "bbbbbbbb",
            "kind": "pat",
            "task": "2",
            "queued_at": 1000,
            "prompt_bytes": 2,
        },
    )
    record_dispatch.append_row(
        autopilot,
        {
            "id": "bbbbbbbb",
            "ended_at": 1010,
            "elapsed_s": 10,
            "outcome": "ok",
            "detail": None,
        },
    )
    monkeypatch.chdir(tmp_path / "proj")
    _pin_clock(monkeypatch, 5000)
    rows_before = len(_rows(autopilot / "dispatch-metrics.jsonl"))

    exit_code = _run_handoff("review", "resume", "done", "Y")

    assert exit_code == 0
    rows_after = _rows(autopilot / "dispatch-metrics.jsonl")
    assert len(rows_after) == rows_before + 1
    assert rows_after[-1] == {
        "kind": "handoff",
        "site": "review",
        "edge": "resume",
        "at": 5000,
        "phase": "done",
        "prd": "Y",
    }
