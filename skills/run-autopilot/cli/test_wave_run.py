#!/usr/bin/env python3
"""Tests for `autopilot wave <verb>` going through the REAL dispatch edge:
`cli.__main__.main(argv)` parsing argv with the real parser (built from
`cli.wave_cli.add`) and `_run_wave` routing the parsed namespace to
`cli.wave_cli.run`.

Every other wave test drives `wave_cli.run` directly or calls a verb
implementation itself, so none of them goes through `cli.__main__.main()`;
none of them could have caught `run_p` never registering `--state`, which
made `_run_wave` read `args.state` and blow up with an `AttributeError`
before `wave_cli.run` was ever reached for the `run` verb. This file tests
only that parse -> dispatch edge, for every verb `wave_cli.add` registers -
not what any verb itself does once dispatched.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pytest

from cli import __main__ as cli_main
from cli import wave_cli


def _wave_verbs() -> list[str]:
    """The verb names `wave_cli.add` registers on the `wave` sub-parser,
    read from a freshly built parser instead of hand-listed, so a verb
    added or removed there is reflected here automatically."""
    parser = argparse.ArgumentParser(prog="autopilot")
    subparsers = parser.add_subparsers(dest="command")
    wave_cli.add(subparsers)
    wave_parser = subparsers.choices["wave"]
    verbs_action = next(
        action
        for action in wave_parser._actions
        if isinstance(action, argparse._SubParsersAction)
    )
    return list(verbs_action.choices.keys())


def test_every_wave_verb_parses_and_dispatches_with_no_state_flag(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """`autopilot wave <verb>` reaches wave_cli.run with a resolvable state
    path for every verb, instead of dying in _run_wave on a missing
    args.state. Drives cli.__main__.main(argv) - the real parser and the
    real dispatch table - not wave_cli.add() alone."""
    calls: list[str] = []

    def fake_run(args: argparse.Namespace, repo: Path, wave_path: Path) -> int:
        calls.append(args.verb)
        return 0

    monkeypatch.setattr(wave_cli, "run", fake_run)
    autopilot_dir = tmp_path / "docs" / "dev" / "project-management" / "autopilot"
    autopilot_dir.mkdir(parents=True)
    monkeypatch.chdir(tmp_path)

    verbs = _wave_verbs()
    for verb in verbs:
        result = cli_main.main(["wave", verb])
        assert result == 0, f"wave {verb} did not return the recorder's exit code"

    assert calls == verbs


def test_run_reaches_the_recorder_with_an_explicit_state_flag(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Case B: even with an explicit --state, `wave run` must not be
    rejected by argparse as an unrecognized argument - `run_p` has to
    register --state like every other wave verb does."""
    calls: list[tuple[str, Path, Path]] = []

    def fake_run(args: argparse.Namespace, repo: Path, wave_path: Path) -> int:
        calls.append((args.verb, repo, wave_path))
        return 0

    monkeypatch.setattr(wave_cli, "run", fake_run)
    state_path = (
        tmp_path / "docs" / "dev" / "project-management" / "autopilot" / "state.json"
    )

    result = cli_main.main(["wave", "run", "--state", str(state_path)])

    assert result == 0
    assert calls == [("run", tmp_path, state_path.parent / "wave.json")]
