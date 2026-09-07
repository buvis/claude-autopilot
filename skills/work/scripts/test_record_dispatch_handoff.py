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
