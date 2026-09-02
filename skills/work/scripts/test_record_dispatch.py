"""Tests for record_dispatch.py — the /work dispatch timing ledger (PRD 00168).

Every case drives the real module against a temporary project tree holding
``dev/local/autopilot/``, because the script's whole contract is where and
whether a line lands: the working file, its ``ledger/`` mirror, or nowhere at
all when no autopilot dir resolves. Time is pinned through the module's own
``time`` name so the elapsed arithmetic is asserted, not eyeballed.
"""

from __future__ import annotations

import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

_MODULE_PATH = Path(__file__).with_name("record_dispatch.py")
_SPEC = importlib.util.spec_from_file_location("record_dispatch", _MODULE_PATH)
assert _SPEC is not None and _SPEC.loader is not None
record_dispatch = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(record_dispatch)

_HEX_ID = re.compile(r"^[0-9a-f]{8}$")


def _project(tmp_path: Path) -> Path:
    """A project tree with an autopilot dir and a nested cwd; returns the dir."""
    autopilot = tmp_path / "proj" / "dev" / "local" / "autopilot"
    autopilot.mkdir(parents=True)
    (tmp_path / "proj" / "src").mkdir()
    return autopilot


def _rows(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def _pin_clock(monkeypatch: pytest.MonkeyPatch, now: float) -> None:
    monkeypatch.setattr(record_dispatch, "time", SimpleNamespace(time=lambda: now))


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
        {"id": "deadbeef", "kind": "ivan", "task": "3", "queued_at": 1000, "prompt_bytes": 42},
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


def test_end_with_no_start_row_records_a_null_elapsed_and_exits_zero(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # A lost or mistyped id must not turn a telemetry call into a failure the
    # dispatch pays for; the row still lands so the outcome is on record.
    autopilot = _project(tmp_path)
    monkeypatch.chdir(tmp_path / "proj")
    _pin_clock(monkeypatch, 2000)

    exit_code = record_dispatch.main(
        ["end", "cafebabe", "--outcome", "timeout", "--detail", "watchdog 45 min"],
    )

    assert exit_code == 0
    assert _rows(autopilot / "dispatch-metrics.jsonl") == [
        {
            "id": "cafebabe",
            "ended_at": 2000,
            "elapsed_s": None,
            "outcome": "timeout",
            "detail": "watchdog 45 min",
        },
    ]


def test_both_the_working_file_and_the_ledger_mirror_receive_the_row(
    tmp_path: Path,
) -> None:
    autopilot = _project(tmp_path)
    (autopilot / "ledger").mkdir()

    record_dispatch.append_row(autopilot, {"id": "0badf00d", "kind": "pat", "task": "1"})

    working = (autopilot / "dispatch-metrics.jsonl").read_text(encoding="utf-8")
    mirror = (autopilot / "ledger" / "dispatch-metrics.jsonl").read_text(encoding="utf-8")
    assert working == mirror == '{"id":"0badf00d","kind":"pat","task":"1"}\n'


def test_a_missing_ledger_directory_is_created_before_the_mirror_append(
    tmp_path: Path,
) -> None:
    # ledger/ is created lazily by whichever writer arrives first; on a repo
    # whose batch has not mirrored a session row yet, this is that writer.
    autopilot = _project(tmp_path)
    assert not (autopilot / "ledger").exists()

    record_dispatch.append_row(autopilot, {"id": "feedface"})

    assert _rows(autopilot / "ledger" / "dispatch-metrics.jsonl") == [{"id": "feedface"}]


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


def test_start_opens_a_row_carrying_the_prompt_bytes_and_prints_its_id(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    # Devon and the self-deslop pass fill their prompts by hand, so no render
    # opens their row; this verb is their one call, and its id is what the
    # end call later joins on.
    autopilot = _project(tmp_path)
    monkeypatch.chdir(tmp_path / "proj")
    _pin_clock(monkeypatch, 4000)

    exit_code = record_dispatch.main(
        ["start", "--kind", "devon", "--task", "2", "--prompt-bytes", "1234"],
    )

    assert exit_code == 0
    count, printed = capsys.readouterr().out.splitlines()
    assert count == "1234"
    assert _HEX_ID.match(printed)
    assert _rows(autopilot / "dispatch-metrics.jsonl") == [
        {"id": printed, "kind": "devon", "task": "2", "queued_at": 4000, "prompt_bytes": 1234},
    ]


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
    prompt.write_bytes("café\n".encode("utf-8"))
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
        {"id": printed, "kind": "deslop", "task": "4", "queued_at": 5000, "prompt_bytes": 6},
    ]


def test_start_on_an_unreadable_prompt_file_exits_2_and_opens_no_row(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    # This call doubles as the budget measurement, and a prompt that cannot be
    # read cannot be dispatched, so it is the one telemetry call that fails
    # loud with a non-zero exit instead of stamping a null count.
    autopilot = _project(tmp_path)
    monkeypatch.chdir(tmp_path / "proj")

    exit_code = record_dispatch.main(
        ["start", "--kind", "devon", "--task", "1", "--prompt-file", str(tmp_path / "no.txt")],
    )

    assert exit_code == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "record_dispatch: prompt file unreadable" in captured.err
    assert not (autopilot / "dispatch-metrics.jsonl").exists()


def test_end_names_a_skipped_unparseable_line_and_the_missing_start_row(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    # A null elapsed_s has to say why on stderr: a garbage line in the working
    # copy, or simply no start row, is otherwise indistinguishable from a
    # dispatch that was never opened.
    autopilot = _project(tmp_path)
    (autopilot / "dispatch-metrics.jsonl").write_text("not json\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path / "proj")
    _pin_clock(monkeypatch, 6000)

    exit_code = record_dispatch.main(["end", "deadbeef", "--outcome", "ok"])

    assert exit_code == 0
    err = capsys.readouterr().err
    assert "skipped 1 unparseable line" in err
    assert "no start row for deadbeef" in err
    last = (autopilot / "dispatch-metrics.jsonl").read_text(encoding="utf-8").splitlines()[-1]
    assert json.loads(last)["elapsed_s"] is None


@pytest.mark.parametrize(
    "argv",
    [
        ["end", "deadbeef", "--outcome", "ok"],
        ["handoff", "--site", "build", "--edge", "resume", "--phase", "build", "--prd", "x.md"],
        ["start", "--kind", "tess", "--task", "1", "--prompt-bytes", "5"],
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
    # dispatch proceeds. `start` still prints an id so the caller's next
    # line is the same either way.
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
