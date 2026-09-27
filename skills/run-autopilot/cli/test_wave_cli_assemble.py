#!/usr/bin/env python3
"""Tests for the `assemble` verb wiring in cli/wave_cli.py: `add` registering it
next to `plan`, `launch`, `status` and `abort`, and `run` dispatching an
already-parsed namespace to `cli.wave_assemble.assemble(repo, wave_path)`.

`assemble`'s own merge behaviour - what it does to a repo, a wave.json, or a
git history - is proved in cli/test_wave_assemble.py and
cli/test_wave_assemble_migrate.py; here `wave_assemble.assemble` is a
stand-in, so this file tests only the CLI's own job: parsing, dispatch,
exit-code passthrough, and turning a subprocess.CalledProcessError into an
exit code 1 and a stderr line instead of a traceback.
"""

from __future__ import annotations

import argparse
import subprocess
from pathlib import Path

import pytest

from cli import wave, wave_assemble, wave_cli, wave_launch


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="autopilot")
    subparsers = parser.add_subparsers(dest="command")
    wave_cli.add(subparsers)
    return parser


def _parse(argv: list[str]) -> argparse.Namespace:
    return _parser().parse_args(argv)


# ── add: the assemble verb ───────────────────────────────────────────────


def test_add_accepts_assemble_with_a_state_path() -> None:
    ns = _parse(["wave", "assemble", "--state", "/tmp/x/state.json"])
    assert ns.verb == "assemble"
    assert ns.state == "/tmp/x/state.json"


# ── run: dispatch to wave_assemble.assemble ──────────────────────────────


@pytest.mark.parametrize("code", [0, 1, 3])
def test_run_returns_the_assembly_routines_exit_code_unchanged(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    code: int,
) -> None:
    calls: list[tuple[Path, Path]] = []

    def fake_assemble(repo: Path, wave_path: Path) -> int:
        calls.append((repo, wave_path))
        return code

    monkeypatch.setattr(wave_assemble, "assemble", fake_assemble)
    repo, wave_path = tmp_path / "repo", tmp_path / "repo" / "wave.json"
    ns = _parse(["wave", "assemble", "--state", "/tmp/x/state.json"])
    assert wave_cli.run(ns, repo, wave_path) == code
    assert calls == [(repo, wave_path)]


def test_run_does_not_read_wave_json_before_reaching_assemble(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    # `assemble` loads and locks wave.json itself; a dispatcher that reads it
    # first cannot let assemble report a missing or corrupt file as its own.
    def _boom(_wave_path: Path) -> dict:
        raise AssertionError("run must not load wave.json before calling assemble")

    monkeypatch.setattr(wave, "load", _boom)
    monkeypatch.setattr(wave_assemble, "assemble", lambda repo, wave_path: 0)
    ns = _parse(["wave", "assemble", "--state", "/tmp/x/state.json"])
    assert wave_cli.run(ns, tmp_path, tmp_path / "wave.json") == 0


def test_run_reports_a_git_failure_on_stderr_and_returns_1(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    error = subprocess.CalledProcessError(13, ["git", "merge", "--no-ff", "lane-x"])

    def fake_assemble(repo: Path, wave_path: Path) -> int:
        raise error

    monkeypatch.setattr(wave_assemble, "assemble", fake_assemble)
    ns = _parse(["wave", "assemble", "--state", "/tmp/x/state.json"])
    result = wave_cli.run(ns, tmp_path, tmp_path / "wave.json")
    assert result == 1
    err = capsys.readouterr().err
    assert "13" in err, err
    assert "git" in err, err


def test_run_reports_a_corrupt_wave_json_on_stderr_and_returns_1(
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    wave_path = tmp_path / "wave.json"
    wave_path.write_text("{ not json")
    ns = _parse(["wave", "assemble", "--state", "/tmp/x/state.json"])
    result = wave_cli.run(ns, tmp_path, wave_path)
    assert result == 1
    err = capsys.readouterr().err
    assert "refusing to touch a corrupt wave.json" in err, err


def test_run_reports_a_missing_wave_json_on_stderr_and_returns_1(
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    wave_path = tmp_path / "wave.json"
    ns = _parse(["wave", "assemble", "--state", "/tmp/x/state.json"])
    result = wave_cli.run(ns, tmp_path, wave_path)
    assert result == 1
    err = capsys.readouterr().err
    assert "run `autopilot wave plan` first" in err, err
    assert str(wave_path) in err, err


# ── run: the pre-existing verbs stay intact ──────────────────────────────


def test_status_and_abort_still_parse_after_assemble_is_registered() -> None:
    for verb in ("status", "abort"):
        ns = _parse(["wave", verb, "--state", "/tmp/x/state.json"])
        assert ns.verb == verb
        assert ns.state == "/tmp/x/state.json"


def test_run_still_dispatches_status_and_abort_to_their_own_routines(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    calls: list[str] = []
    monkeypatch.setattr(wave, "load", lambda wave_path: {"id": "x"})

    def fake_status(repo: Path, loaded: dict) -> str:
        calls.append("status")
        return "text"

    def fake_abort(repo: Path, wave_path: Path) -> int:
        calls.append("abort")
        return 0

    monkeypatch.setattr(wave_launch, "status", fake_status)
    monkeypatch.setattr(wave_launch, "abort", fake_abort)
    wave_path = tmp_path / "wave.json"
    wave_cli.run(_parse(["wave", "status", "--state", "x"]), tmp_path, wave_path)
    wave_cli.run(_parse(["wave", "abort", "--state", "x"]), tmp_path, wave_path)
    assert calls == ["status", "abort"]
