"""Tests for record_dispatch.py's start verb — split out of
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
_HEX_ID = _testutil.HEX_ID
_project = _testutil.project
_rows = _testutil.rows
_pin_clock = _testutil.pin_clock


def test_start_with_a_prompt_file_measures_it_and_prints_the_count_then_the_id(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    # The hand-built lanes already spend a call measuring their prompt for the
    # budget; this is that call, printing the same two lines a flagged render
    # prints, so opening the row costs them nothing extra.
    autopilot = _project(tmp_path)
    prompt = tmp_path / "proj" / "prompt.txt"
    prompt.write_bytes("café\n".encode())
    monkeypatch.chdir(tmp_path / "proj")
    _pin_clock(monkeypatch, 5000)

    exit_code = record_dispatch.main(
        ["start", "--kind", "deslop", "--task", "4", "--prompt-file", str(prompt)],
    )

    assert exit_code == 0
    count, printed = capsys.readouterr().out.splitlines()
    assert count == "6"  # bytes, not characters
    assert _HEX_ID.match(printed)
    assert _rows(autopilot / "dispatch-metrics.jsonl") == [
        {
            "id": printed,
            "kind": "deslop",
            "task": "4",
            "queued_at": 5000,
            "prompt_bytes": 6,
        },
    ]


@pytest.mark.parametrize("prompt", ["no.txt", "proj"], ids=["missing", "directory"])
def test_start_on_an_unreadable_prompt_file_exits_2_and_opens_no_row(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    prompt: str,
) -> None:
    # This call doubles as the budget measurement, and a prompt that cannot be
    # read cannot be dispatched, so it is the one telemetry call that fails
    # loud with a non-zero exit instead of stamping a null count. The file is
    # read, not stat'ed: a directory has a size and is not a prompt.
    autopilot = _project(tmp_path)
    monkeypatch.chdir(tmp_path / "proj")

    exit_code = record_dispatch.main(
        [
            "start",
            "--kind",
            "devon",
            "--task",
            "1",
            "--prompt-file",
            str(tmp_path / prompt),
        ],
    )

    assert exit_code == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "record_dispatch: prompt file unreadable" in captured.err
    assert not (autopilot / "dispatch-metrics.jsonl").exists()
