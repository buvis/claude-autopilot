#!/usr/bin/env python3
"""Tests for the `catchup-probe` CLI surface: no-argument invocation, state
path resolution, and the one-JSON-line stdout contract.

The gh/engram probes never run for real: `probe` is wrapped so every binary
reads as absent (no subprocess call at all).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from cli import __main__ as main_mod
from cli import catchup_probe

AUTOPILOT_REL = Path("docs") / "dev" / "project-management" / "autopilot"


def _make_repo(root: Path, batch_id: str) -> Path:
    autopilot_dir = root / AUTOPILOT_REL
    autopilot_dir.mkdir(parents=True)
    state_path = autopilot_dir / "state.json"
    state_path.write_text(json.dumps({"batch": {"id": batch_id}}), encoding="utf-8")
    return state_path


def _read_state(state_path: Path) -> dict:
    return json.loads(state_path.read_text(encoding="utf-8"))


@pytest.fixture
def offline_probe(monkeypatch):
    """Route probe() through the real code with every binary absent; record
    which state paths it was asked to probe."""
    real_probe = catchup_probe.probe
    seen: list[Path] = []

    def fake_probe(state_path, **_kwargs):
        seen.append(Path(state_path))
        return real_probe(state_path, run=None, which=lambda _name: None)

    monkeypatch.setattr(catchup_probe, "probe", fake_probe)
    return seen


def _one_json_line(capsys) -> dict:
    lines = capsys.readouterr().out.splitlines()
    assert len(lines) == 1, f"expected exactly one stdout line, got {lines!r}"
    return json.loads(lines[0])


def test_bare_invocation_exits_zero_and_prints_one_json_line_with_skip_list(
    tmp_path, monkeypatch, capsys, offline_probe
) -> None:
    repo = tmp_path / "repo"
    _make_repo(repo, "B1")
    monkeypatch.chdir(repo)

    code = main_mod.main(["catchup-probe"])

    assert code == 0
    assert isinstance(_one_json_line(capsys)["skip"], list)


def test_bare_invocation_from_a_nested_subdirectory_probes_the_ancestor_state(
    tmp_path, monkeypatch, capsys, offline_probe
) -> None:
    repo = tmp_path / "repo"
    state_path = _make_repo(repo, "B1")
    nested = repo / "src" / "deep"
    nested.mkdir(parents=True)
    monkeypatch.chdir(nested)

    code = main_mod.main(["catchup-probe"])

    assert code == 0
    assert isinstance(_one_json_line(capsys)["skip"], list)
    assert _read_state(state_path)["catchup_probe"]["batch_id"] == "B1"


def test_explicit_state_flag_exits_zero_and_prints_one_json_line_with_skip_list(
    tmp_path, capsys, offline_probe
) -> None:
    state_path = _make_repo(tmp_path / "repo", "B1")

    code = main_mod.main(["catchup-probe", "--state", str(state_path)])

    assert code == 0
    assert isinstance(_one_json_line(capsys)["skip"], list)
    assert _read_state(state_path)["catchup_probe"]["batch_id"] == "B1"


def test_explicit_state_wins_over_the_cwd_walk_up(
    tmp_path, monkeypatch, capsys, offline_probe
) -> None:
    cwd_state = _make_repo(tmp_path / "cwd_repo", "CWD-BATCH")
    explicit_state = _make_repo(tmp_path / "explicit_repo", "EXPLICIT-BATCH")
    monkeypatch.chdir(tmp_path / "cwd_repo")

    code = main_mod.main(["catchup-probe", "--state", str(explicit_state)])

    assert code == 0
    _one_json_line(capsys)
    assert _read_state(explicit_state)["catchup_probe"]["batch_id"] == "EXPLICIT-BATCH"
    assert "catchup_probe" not in _read_state(cwd_state)
    assert [p.resolve() for p in offline_probe] == [explicit_state.resolve()]


def test_bare_invocation_without_an_autopilot_ancestor_exits_one_naming_state(
    tmp_path, monkeypatch, capsys, offline_probe
) -> None:
    bare = tmp_path / "no_repo_here"
    bare.mkdir()
    monkeypatch.chdir(bare)

    with pytest.raises(SystemExit) as excinfo:
        main_mod.main(["catchup-probe"])

    assert excinfo.value.code == 1
    captured = capsys.readouterr()
    assert "--state" in captured.err
    assert captured.out == ""
    assert offline_probe == [], "the probe must not run when no state path resolves"
