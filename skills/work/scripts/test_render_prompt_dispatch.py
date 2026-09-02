"""Tests for render_prompt.py's dispatch telemetry flags (PRD 00168).

Split from test_render_prompt.py: that file sits at 748 lines and these cases
pushed it past the pack's own 800-line file limit (the step-5.65 style gate
flagged `FILE | test_render_prompt.py | 870 lines` on this PRD's first gate
run), the same reason test_command_budget_prose.py is its own module.

Same loader idiom as the sibling file, so the module under test is the real
script at its real path and the cwd is whatever each test chose.
"""

from __future__ import annotations

import importlib.util
import json
import re
from pathlib import Path

import pytest

_MODULE_PATH = Path(__file__).with_name("render_prompt.py")
_SPEC = importlib.util.spec_from_file_location("render_prompt", _MODULE_PATH)
assert _SPEC is not None and _SPEC.loader is not None
render_prompt = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(render_prompt)

_HEX_ID = re.compile(r"^[0-9a-f]{8}$")


def _persona(tmp_path: Path, content: str) -> Path:
    path = tmp_path / "persona.md"
    path.write_text(content, encoding="utf-8")
    return path


def _project(tmp_path: Path) -> Path:
    """A project root holding dev/local/autopilot/; returns the autopilot dir."""
    autopilot = tmp_path / "proj" / "dev" / "local" / "autopilot"
    autopilot.mkdir(parents=True)
    return autopilot


@pytest.mark.parametrize(
    "flags",
    [[], ["--dispatch-kind", "tess"], ["--dispatch-task", "1"]],
    ids=["neither", "kind-only", "task-only"],
)
def test_without_both_dispatch_flags_stdout_is_the_count_alone_and_nothing_is_written(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    flags: list[str],
) -> None:
    # Every caller this PRD did not wire keeps today's contract to the byte:
    # one line, the count, and no file anywhere. The render's stdout is the
    # budget measurement, and a surprise second line would break a caller
    # that reads it as one integer.
    autopilot = _project(tmp_path)
    monkeypatch.chdir(autopilot.parents[2])
    persona = _persona(tmp_path, "Hello {NAME}!")
    out_path = tmp_path / "out.txt"

    exit_code = render_prompt.main(
        [str(persona), "--out", str(out_path), "--set", "NAME=World", *flags],
    )

    assert exit_code == 0
    assert capsys.readouterr().out == "12\n"
    assert not (autopilot / "dispatch-metrics.jsonl").exists()
    assert not (autopilot / "ledger").exists()


def test_both_dispatch_flags_open_a_start_row_carrying_the_printed_count_and_echo_its_id(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    # The count on line one IS the row's prompt_bytes — one measurement, two
    # readers — and line two is the id the end call joins on. A multibyte
    # value keeps "bytes, not characters" honest on the row as well.
    autopilot = _project(tmp_path)
    monkeypatch.chdir(autopilot.parents[2])
    persona = _persona(tmp_path, "Value: {V}")
    out_path = tmp_path / "out.txt"

    exit_code = render_prompt.main(
        [
            str(persona),
            "--out",
            str(out_path),
            "--set",
            "V=café",
            "--dispatch-kind",
            "ivan",
            "--dispatch-task",
            "7",
        ],
    )

    assert exit_code == 0
    count_line, id_line = capsys.readouterr().out.splitlines()
    assert count_line == str(len(out_path.read_bytes()))
    assert _HEX_ID.match(id_line)
    working = (autopilot / "dispatch-metrics.jsonl").read_text(encoding="utf-8")
    rows = [json.loads(line) for line in working.splitlines()]
    assert len(rows) == 1
    assert rows[0]["id"] == id_line
    assert rows[0]["kind"] == "ivan"
    assert rows[0]["task"] == "7"
    assert rows[0]["prompt_bytes"] == int(count_line)
    assert isinstance(rows[0]["queued_at"], int)
    mirror = autopilot / "ledger" / "dispatch-metrics.jsonl"
    assert mirror.read_text(encoding="utf-8") == working


def test_an_unresolvable_autopilot_dir_still_renders_and_prints_the_count(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    # Telemetry never blocks a dispatch: outside any autopilot tree the render
    # is complete and its budget line intact. The id is still printed so the
    # caller's next line is the same either way, and it opens nothing.
    monkeypatch.chdir(tmp_path)
    persona = _persona(tmp_path, "Hello {NAME}!")
    out_path = tmp_path / "out.txt"

    exit_code = render_prompt.main(
        [
            str(persona),
            "--out",
            str(out_path),
            "--set",
            "NAME=World",
            "--dispatch-kind",
            "pat",
            "--dispatch-task",
            "2",
        ],
    )

    assert exit_code == 0
    assert out_path.read_text(encoding="utf-8") == "Hello World!"
    count_line, id_line = capsys.readouterr().out.splitlines()
    assert count_line == "12"
    assert _HEX_ID.match(id_line)
    assert list(tmp_path.rglob("dispatch-metrics.jsonl")) == []
