"""Tests for record_dispatch.py's read-failure handling: an OSError or
non-UTF-8 byte from the working file must not crash `open_ids` or the
`end`/`handoff` verbs that depend on it, and a ledger with one unparseable
line must warn once per `end` call, not once per internal read. See
test_record_dispatch_append_row.py's module docstring for the shared testing
approach.
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
_pin_clock = _testutil.pin_clock
_run_handoff = _testutil.run_handoff


def test_open_ids_returns_empty_list_when_the_working_file_is_unreadable(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    # A directory where the file should be raises OSError (IsADirectoryError)
    # from read_text for every user including root; open_ids must treat that
    # the same way it treats a missing file, not propagate it.
    autopilot = _project(tmp_path)
    (autopilot / "dispatch-metrics.jsonl").mkdir()

    ids = record_dispatch.open_ids(autopilot)

    assert ids == []
    assert "record_dispatch:" in capsys.readouterr().err


def test_open_ids_returns_empty_list_when_the_working_file_is_not_utf8(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    # A stray non-UTF-8 byte (a corrupted write, a stray binary paste) must
    # not crash the lookup any more than a directory does: it is named on
    # stderr and treated as an empty ledger.
    autopilot = _project(tmp_path)
    (autopilot / "dispatch-metrics.jsonl").write_bytes(b"\xff\xfe not utf8\n")

    ids = record_dispatch.open_ids(autopilot)

    assert ids == []
    assert "record_dispatch:" in capsys.readouterr().err


def test_handoff_over_an_unreadable_working_file_exits_zero_and_reports_both_failures(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    # handoff calls open_ids before appending its own row. Today that read is
    # unguarded for OSError and crashes before the row is ever attempted; the
    # fix must reach the append instead of dying earlier. The append itself
    # still fails here (the same directory blocks the write too), so the
    # observable proof of "reached the append" is its own reported failure.
    autopilot = _project(tmp_path)
    (autopilot / "dispatch-metrics.jsonl").mkdir()
    monkeypatch.chdir(tmp_path / "proj")

    exit_code = _run_handoff("build", "resume", "build", "x.md")

    assert exit_code == 0
    err_lines = [
        line
        for line in capsys.readouterr().err.splitlines()
        if line.startswith("record_dispatch:")
    ]
    assert len(err_lines) >= 2
    assert any("append failed" in line for line in err_lines)


def test_handoff_over_a_non_utf8_working_file_still_appends_its_row(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Non-UTF-8 content only breaks reads; the append itself is a plain
    # UTF-8 write in "a" mode that never decodes what is already there, so
    # the handoff row must still land on disk even though the lookup that
    # precedes it could not be read.
    autopilot = _project(tmp_path)
    working = autopilot / "dispatch-metrics.jsonl"
    working.write_bytes(b"\xff\xfe not utf8\n")
    monkeypatch.chdir(tmp_path / "proj")
    _pin_clock(monkeypatch, 1234567890.0)

    exit_code = _run_handoff("build", "resume", "build", "x.md")

    assert exit_code == 0
    lines = working.read_bytes().splitlines()
    assert len(lines) == 2
    appended_row = json.loads(lines[-1].decode("utf-8"))
    assert appended_row == {
        "kind": "handoff",
        "site": "build",
        "edge": "resume",
        "at": 1234567890,
        "phase": "build",
        "prd": "x.md",
    }


def test_end_over_one_unparseable_line_warns_exactly_once(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    # end calls _queued_at and then, when a start row was found,
    # _spans_handoff — both walk the same lines and each names its own
    # unparseable-line count, so a ledger with exactly one bad line prints
    # the same warning twice for a single `end` call. It must print once.
    autopilot = _project(tmp_path)
    (autopilot / "dispatch-metrics.jsonl").write_text(
        json.dumps({"id": "deadbeef", "queued_at": 1000}) + "\n" + "not json at all\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path / "proj")

    exit_code = record_dispatch.main(["end", "deadbeef", "--outcome", "ok"])

    assert exit_code == 0
    warning = (
        f"record_dispatch: skipped 1 unparseable line(s) in {record_dispatch.FILENAME}"
    )
    assert capsys.readouterr().err.count(warning) == 1
