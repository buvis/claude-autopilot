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


def test_both_the_working_file_and_the_ledger_mirror_receive_the_row(
    tmp_path: Path,
) -> None:
    autopilot = _project(tmp_path)
    (autopilot / "ledger").mkdir()

    record_dispatch.append_row(
        autopilot, {"id": "0badf00d", "kind": "pat", "task": "1"}
    )

    working = (autopilot / "dispatch-metrics.jsonl").read_text(encoding="utf-8")
    mirror = (autopilot / "ledger" / "dispatch-metrics.jsonl").read_text(
        encoding="utf-8"
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
        {"id": "feedface"}
    ]


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

    exit_code = record_dispatch.main(
        [
            "handoff",
            "--site",
            "build",
            "--edge",
            "leave",
            "--phase",
            "review",
            "--prd",
            "X",
        ],
    )

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

    exit_code = record_dispatch.main(
        [
            "handoff",
            "--site",
            "review",
            "--edge",
            "resume",
            "--phase",
            "done",
            "--prd",
            "Y",
        ],
    )

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
