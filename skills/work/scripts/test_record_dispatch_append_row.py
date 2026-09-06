"""Tests for record_dispatch.py's append_row plumbing and dir resolution —
split out of test_record_dispatch.py (PRD 00168) to stay under the file size
limit. See that file's module docstring for the shared testing approach.
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
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
_MODULE_PATH = _testutil.MODULE_PATH
_HEX_ID = _testutil.HEX_ID
_project = _testutil.project
_rows = _testutil.rows


def test_both_the_working_file_and_the_ledger_mirror_receive_the_row(
    tmp_path: Path,
) -> None:
    autopilot = _project(tmp_path)
    (autopilot / "ledger").mkdir()

    record_dispatch.append_row(
        autopilot,
        {"id": "0badf00d", "kind": "pat", "task": "1"},
    )

    working = (autopilot / "dispatch-metrics.jsonl").read_text(encoding="utf-8")
    mirror = (autopilot / "ledger" / "dispatch-metrics.jsonl").read_text(
        encoding="utf-8",
    )
    assert working == mirror == '{"id":"0badf00d","kind":"pat","task":"1"}\n'


def test_a_missing_ledger_directory_is_created_before_the_mirror_append(
    tmp_path: Path,
) -> None:
    # ledger/ is created lazily by whichever writer arrives first; on a repo
    # whose batch has not mirrored a session row yet, this is that writer.
    autopilot = _project(tmp_path)
    assert not (autopilot / "ledger").exists()

    record_dispatch.append_row(autopilot, {"id": "feedface"})

    assert _rows(autopilot / "ledger" / "dispatch-metrics.jsonl") == [
        {"id": "feedface"},
    ]


@pytest.mark.parametrize(
    "argv",
    [
        ["end", "deadbeef", "--outcome", "ok"],
        [
            "handoff",
            "--site",
            "build",
            "--edge",
            "resume",
            "--phase",
            "build",
            "--prd",
            "x.md",
        ],
        ["start", "--kind", "tess", "--task", "1", "--prompt-file", "prompt.txt"],
    ],
)
def test_an_unresolvable_autopilot_dir_writes_nothing_and_exits_zero(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    argv: list[str],
) -> None:
    # Telemetry outside any autopilot tree (a manual /work run, a scratch
    # checkout) is a no-op, not an error: nothing is written anywhere and the
    # dispatch proceeds. `start` still prints the count and an id so the
    # caller's next line is the same either way.
    (tmp_path / "prompt.txt").write_text("hello", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    exit_code = record_dispatch.main(argv)

    assert exit_code == 0
    assert list(tmp_path.rglob("dispatch-metrics.jsonl")) == []
    captured = capsys.readouterr()
    assert captured.err == ""
    if argv[0] == "start":
        count, printed = captured.out.splitlines()
        assert count == "5"
        assert _HEX_ID.match(printed)
    else:
        assert captured.out == ""


def test_an_unwritable_file_drops_the_row_loudly_and_exits_zero(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    # A directory where the file should be makes every append fail. The
    # failure is named on stderr (never silent) and never becomes an exit
    # code the orchestrator would read as a failed dispatch.
    autopilot = _project(tmp_path)
    (autopilot / "dispatch-metrics.jsonl").mkdir()
    monkeypatch.chdir(tmp_path / "proj")

    exit_code = record_dispatch.main(["end", "deadbeef", "--outcome", "error"])

    assert exit_code == 0
    err = capsys.readouterr().err
    assert "record_dispatch: start row lookup failed" in err
    assert "record_dispatch: append failed" in err


def test_concurrent_appends_from_parallel_processes_all_survive(
    tmp_path: Path,
) -> None:
    # Parallel rework tasks dispatch at once. Two rows per dispatch instead
    # of one mutated row is what makes every write a pure one-line append,
    # and this is the check that the appends do not clobber each other.
    autopilot = _project(tmp_path)
    procs = [
        subprocess.Popen(
            [
                sys.executable,
                str(_MODULE_PATH),
                "handoff",
                "--site",
                "build",
                "--edge",
                "leave",
                "--phase",
                "build",
                "--prd",
                f"p{i}",
            ],
            cwd=tmp_path / "proj",
        )
        for i in range(8)
    ]
    for proc in procs:
        assert proc.wait() == 0

    for path in (
        autopilot / "dispatch-metrics.jsonl",
        autopilot / "ledger" / "dispatch-metrics.jsonl",
    ):
        rows = _rows(path)
        assert sorted(row["prd"] for row in rows) == [f"p{i}" for i in range(8)]
