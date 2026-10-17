"""Tests for record_item.py's --started bound checks and started-file fallback.

Split from test_record_item.py once that file reached the 800-line test-file
cap (PRD 00326 rework task 6, D1 review findings): --started must be refused
when it is more than 24h before ts_end or in the future, the same refusal
must apply to a value read from the started-file fallback, and
_read_started_file() must not let a non-UTF-8 started file surface as an
unhandled traceback.
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
import time
from pathlib import Path

import pytest

_MODULE_PATH = Path(__file__).with_name("record_item.py")

_SPEC = importlib.util.spec_from_file_location(
    "fast_track_record_item_started_bounds",
    _MODULE_PATH,
)
assert _SPEC is not None and _SPEC.loader is not None
_record_item = importlib.util.module_from_spec(_SPEC)
# Registered before exec_module on purpose, the same reason test_record_item.py
# does it: a module that resolves its own annotations at import time looks
# itself up in sys.modules, and an unregistered module makes that lookup fail.
sys.modules[_SPEC.name] = _record_item
_SPEC.loader.exec_module(_record_item)

_LEDGER_FILENAME = "loop-metrics.jsonl"
_MAX_STARTED_AGE_SECS = 24 * 3600


def _autopilot_tree(root: Path) -> Path:
    """A tmp tree the walk-up can land in, returning its autopilot dir."""
    autopilot_dir = root / "docs" / "dev" / "project-management" / "autopilot"
    autopilot_dir.mkdir(parents=True)
    return autopilot_dir


def _started_file(root: Path) -> Path:
    path = root / "docs" / "dev" / "tmp" / "fast-track-started"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _cli_args(*, started: int | None, card: str = "widget-slice.md") -> list[str]:
    args = [
        "--item",
        "widget-slice",
        "--card",
        card,
        "--model",
        "sonnet",
        "--outcome",
        "committed",
        "--rework",
        "0",
        "--findings",
        "[]",
        "--confirmed",
        "0",
    ]
    if started is not None:
        args += ["--started", str(started)]
    return args


def _run_cli(cwd: Path, args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(_MODULE_PATH), *args],
        capture_output=True,
        text=True,
        check=False,
        cwd=str(cwd),
    )


def test_a_future_started_value_is_refused_naming_it(tmp_path: Path) -> None:
    autopilot_dir = _autopilot_tree(tmp_path)
    future = int(time.time()) + 3600

    result = _run_cli(tmp_path, _cli_args(started=future))

    assert result.returncode == 2, result.stderr
    assert str(future) in result.stderr
    assert not (autopilot_dir / _LEDGER_FILENAME).exists()


def test_started_exactly_24_hours_before_ts_end_is_accepted(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # A controlled clock pins the exact boundary: ts_end is frozen so the
    # value 24h before it lands exactly on the bound, with no subprocess
    # startup delay able to push it over.
    autopilot_dir = _autopilot_tree(tmp_path)
    monkeypatch.chdir(tmp_path)
    fixed_end = 2_000_000_000
    monkeypatch.setattr(_record_item.time, "time", lambda: float(fixed_end))
    boundary = fixed_end - _MAX_STARTED_AGE_SECS

    exit_code = _record_item.main(_cli_args(started=boundary))

    assert exit_code == 0
    assert (autopilot_dir / _LEDGER_FILENAME).is_file()


def test_started_one_second_past_the_24_hour_boundary_is_refused(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    autopilot_dir = _autopilot_tree(tmp_path)
    monkeypatch.chdir(tmp_path)
    fixed_end = 2_000_000_000
    monkeypatch.setattr(_record_item.time, "time", lambda: float(fixed_end))
    past_boundary = fixed_end - _MAX_STARTED_AGE_SECS - 1

    exit_code = _record_item.main(_cli_args(started=past_boundary))

    assert exit_code == 2
    assert str(past_boundary) in capsys.readouterr().err
    assert not (autopilot_dir / _LEDGER_FILENAME).exists()


def test_started_omitted_and_started_file_missing_exits_two(tmp_path: Path) -> None:
    autopilot_dir = _autopilot_tree(tmp_path)

    result = _run_cli(tmp_path, _cli_args(started=None))

    assert result.returncode == 2, result.stderr
    assert result.stderr.strip() != ""
    assert not (autopilot_dir / _LEDGER_FILENAME).exists()


def test_started_omitted_and_started_file_malformed_exits_two(tmp_path: Path) -> None:
    autopilot_dir = _autopilot_tree(tmp_path)
    _started_file(tmp_path).write_text("not-a-number\n", encoding="utf-8")

    result = _run_cli(tmp_path, _cli_args(started=None))

    assert result.returncode == 2, result.stderr
    assert result.stderr.strip() != ""
    assert not (autopilot_dir / _LEDGER_FILENAME).exists()


def test_an_out_of_bound_value_read_from_the_started_file_is_refused(
    tmp_path: Path,
) -> None:
    # The bound check must fire on a value read from the fallback file, not
    # only on a value passed directly via --started.
    autopilot_dir = _autopilot_tree(tmp_path)
    year_old = int(time.time()) - 365 * 24 * 3600
    _started_file(tmp_path).write_text(f"{year_old}\n", encoding="utf-8")

    result = _run_cli(tmp_path, _cli_args(started=None))

    assert result.returncode == 2, result.stderr
    assert str(year_old) in result.stderr
    assert not (autopilot_dir / _LEDGER_FILENAME).exists()


def test_a_non_utf8_started_file_exits_two_without_a_traceback(
    tmp_path: Path,
) -> None:
    autopilot_dir = _autopilot_tree(tmp_path)
    _started_file(tmp_path).write_bytes(b"\xff\xfe\x00bad")

    result = _run_cli(tmp_path, _cli_args(started=None))

    assert result.returncode == 2, result.stderr
    assert "Traceback" not in result.stderr
    assert result.stderr.strip() != ""
    assert not (autopilot_dir / _LEDGER_FILENAME).exists()
