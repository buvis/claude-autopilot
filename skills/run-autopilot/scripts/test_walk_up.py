"""Tests for _walk_up.py — the shared autopilot-dir walk-up helper."""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path


SCRIPT = Path(__file__).with_name("_walk_up.py")


def _run(args: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=cwd,
        capture_output=True,
        text=True,
    )


def _make_autopilot_dir(root: Path) -> Path:
    autopilot = root / "dev" / "local" / "autopilot"
    autopilot.mkdir(parents=True)
    return autopilot


def test_bash_prints_resolved_dir(tmp_path: Path) -> None:
    autopilot = _make_autopilot_dir(tmp_path)
    result = _run(["--bash"], cwd=autopilot)
    assert result.returncode == 0
    assert Path(result.stdout.strip()) == autopilot.resolve()


def test_bash_exits_nonzero_when_no_autopilot_dir(tmp_path: Path) -> None:
    result = _run(["--bash"], cwd=tmp_path)
    assert result.returncode == 1
    assert result.stdout.strip() == ""


def test_clear_cap_removes_marker(tmp_path: Path) -> None:
    autopilot = _make_autopilot_dir(tmp_path)
    marker = autopilot / ".cap-fired"
    marker.write_text("task-7")
    sub = autopilot / "nested"
    sub.mkdir()

    result = _run(["--clear-cap"], cwd=sub)

    assert result.returncode == 0
    assert not marker.exists()


def test_clear_cap_noop_when_marker_absent(tmp_path: Path) -> None:
    autopilot = _make_autopilot_dir(tmp_path)
    result = _run(["--clear-cap"], cwd=autopilot)
    assert result.returncode == 0
    assert not (autopilot / ".cap-fired").exists()


def test_clear_cap_noop_when_no_autopilot_dir(tmp_path: Path) -> None:
    result = _run(["--clear-cap"], cwd=tmp_path)
    assert result.returncode == 0


def test_clear_cap_leaves_other_files_untouched(tmp_path: Path) -> None:
    autopilot = _make_autopilot_dir(tmp_path)
    (autopilot / ".cap-fired").write_text("task-1")
    (autopilot / "signal").write_text("next")
    (autopilot / "state.json").write_text("{}")

    _run(["--clear-cap"], cwd=autopilot)

    assert not (autopilot / ".cap-fired").exists()
    assert (autopilot / "signal").exists()
    assert (autopilot / "state.json").exists()


def test_unknown_arg_exits_2(tmp_path: Path) -> None:
    result = _run(["--bogus"], cwd=tmp_path)
    assert result.returncode == 2
    assert "usage:" in result.stderr


# ── --clear-markers (PRD 00210): inherited markers at session start ──────────


def test_clear_markers_removes_both_inherited_markers(tmp_path: Path) -> None:
    autopilot = _make_autopilot_dir(tmp_path)
    handoff = autopilot / ".handoff-requested"
    cap = autopilot / ".cap-fired"
    handoff.write_text('{"phase": "build", "task_id": "3"}')
    cap.write_text("3")

    result = _run(["--clear-markers"], cwd=autopilot)

    assert result.returncode == 0
    assert not handoff.exists() and not cap.exists()
    lines = result.stderr.splitlines()
    assert len(lines) == 2
    assert re.fullmatch(
        r"autopilot: cleared inherited \.handoff-requested written \d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z",
        lines[0],
    )
    assert re.fullmatch(
        r"autopilot: cleared inherited \.cap-fired written \d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z",
        lines[1],
    )


def test_clear_markers_removes_a_lone_cap_fired(tmp_path: Path) -> None:
    # A missing first marker must not stop the second from being removed.
    autopilot = _make_autopilot_dir(tmp_path)
    cap = autopilot / ".cap-fired"
    cap.write_text("3")
    result = _run(["--clear-markers"], cwd=autopilot)
    assert result.returncode == 0
    assert not cap.exists()
    assert result.stderr.count("cleared inherited") == 1
    assert ".handoff-requested" not in result.stderr


def test_clear_markers_reports_a_marker_it_could_not_remove(tmp_path: Path) -> None:
    autopilot = _make_autopilot_dir(tmp_path)
    stuck = autopilot / ".cap-fired"
    stuck.mkdir()  # unlink() on a directory raises, the marker survives
    result = _run(["--clear-markers"], cwd=autopilot)
    assert result.returncode == 0
    assert "could not clear inherited .cap-fired" in result.stderr


def test_clear_markers_is_a_noop_without_markers(tmp_path: Path) -> None:
    autopilot = _make_autopilot_dir(tmp_path)
    result = _run(["--clear-markers"], cwd=autopilot)
    assert result.returncode == 0
    assert result.stderr == ""
    result = _run(["--clear-markers"], cwd=tmp_path)  # no autopilot dir above
    assert result.returncode == 0
    assert result.stderr == ""


def test_clear_cap_still_leaves_handoff_requested(tmp_path: Path) -> None:
    autopilot = _make_autopilot_dir(tmp_path)
    handoff = autopilot / ".handoff-requested"
    handoff.write_text("x")
    (autopilot / ".cap-fired").write_text("x")
    result = _run(["--clear-cap"], cwd=autopilot)
    assert result.returncode == 0
    assert handoff.exists() and not (autopilot / ".cap-fired").exists()


def test_inherited_markers_match_handoff_markers() -> None:
    sys.path.insert(0, str(SCRIPT.parent))
    sys.path.insert(0, str(SCRIPT.parent.parent))
    import _walk_up
    from cli import handoff

    assert tuple(_walk_up.INHERITED_MARKERS) == tuple(handoff.MARKERS)

