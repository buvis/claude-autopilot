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
import os
import re
import signal
import sys
from collections.abc import Callable
from pathlib import Path

import pytest

from cli import __main__ as cli_main
from cli import wave, wave_assemble, wave_cli, wave_launch, wave_review, wave_run
from cli.test_wave_launch import _repo


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


# ── run ──────────────────────────────────────────────────────────────────


def _run_wave(wave_path: Path) -> None:
    """A wave.json valid enough for wave.load to parse. wave_run.run's own
    plan/launch/assemble/review/land calls are all faked in the tests below,
    so only the wait loop's own wave.load(wave_path) reload touches this
    file for real."""
    wave.save(
        wave_path,
        {
            "id": "202609281200",
            "base_sha": "1111111",
            "status": "planned",
            "lanes": [
                {
                    "name": "l1",
                    "prds": ["00001-a.md"],
                    "pid": 111,
                    "status": "running",
                    "worktree": None,
                    "abort_error": None,
                },
                {
                    "name": "l2",
                    "prds": ["00002-b.md"],
                    "pid": 222,
                    "status": "running",
                    "worktree": None,
                    "abort_error": None,
                },
            ],
        },
    )


def _dead_after_one_pass(monkeypatch: pytest.MonkeyPatch) -> None:
    """wave_launch.lane_status reports both lanes "running" through the
    first full pass over the lane list, then "drained" from then on - the
    wait loop's "every lane pid reads dead" condition trips after one poll,
    matching lane_status's own "pid alive" / "dead pid" vocabulary."""
    seen: list[str] = []

    def fake_lane_status(lane: dict) -> str:
        seen.append(lane["name"])
        return "running" if len(seen) <= 2 else "drained"

    monkeypatch.setattr(wave_launch, "lane_status", fake_lane_status)


def _rising_clock() -> Callable[[], float]:
    """Jumps 700s (past the 10-minute print cadence) on every call, so the
    status print/poll fires on the first iteration regardless of exactly
    when and how often run() samples the clock."""
    ticks = {"value": 0.0}

    def clock() -> float:
        ticks["value"] += 700.0
        return ticks["value"]

    return clock


def _bounded_sleep(limit: int = 20) -> Callable[[float], None]:
    """Fails the test fast and legibly instead of hanging the suite if the
    wait loop's termination check never reads a lane as dead."""
    calls = {"n": 0}

    def sleep_fn(_seconds: float) -> None:
        calls["n"] += 1
        if calls["n"] > limit:
            pytest.fail("wave_run.run's wait loop never exited")

    return sleep_fn


def _run_wave_one_lane(wave_path: Path) -> None:
    """A one-lane wave.json: with a single lane, the wait loop's
    `all(lane_status(lane) != "running" for lane in loaded["lanes"])` check
    never short-circuits past a second lane, so a lane_status fake keyed on
    call count maps 1:1 onto wait-loop polls."""
    wave.save(
        wave_path,
        {
            "id": "202609281200",
            "base_sha": "1111111",
            "status": "planned",
            "lanes": [
                {
                    "name": "l1",
                    "prds": ["00001-a.md"],
                    "pid": 111,
                    "status": "running",
                    "worktree": None,
                    "abort_error": None,
                },
            ],
        },
    )


def _dead_after_n_polls(n: int) -> Callable[[dict], str]:
    """wave_launch.lane_status reports "running" for the first n calls, then
    "drained" - paired with _run_wave_one_lane so the wait loop takes exactly
    n non-terminal polls before it exits."""
    calls = {"n": 0}

    def fake_lane_status(lane: dict) -> str:
        calls["n"] += 1
        return "running" if calls["n"] <= n else "drained"

    return fake_lane_status


def _stepped_clock(step: float) -> Callable[[], float]:
    """Advances by a fixed `step` seconds on every call, so a cadence test
    can pin exactly how many polls it takes to cross the 10-minute print
    threshold, unlike `_rising_clock`'s fixed 700s jump."""
    ticks = {"value": 0.0}

    def clock() -> float:
        ticks["value"] += step
        return ticks["value"]

    return clock


def test_run_orders_plan_launch_wait_assemble_review_land(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo, wave_path = _repo(tmp_path, {})
    _run_wave(wave_path)
    _dead_after_one_pass(monkeypatch)
    calls: list[str] = []
    monkeypatch.setattr(wave, "plan", lambda *a, **k: calls.append("plan") or 0)
    monkeypatch.setattr(
        wave_launch,
        "launch",
        lambda *a, **k: calls.append("launch") or 0,
    )
    monkeypatch.setattr(
        wave_launch,
        "status",
        lambda *a, **k: calls.append("status") or "lane table",
    )
    monkeypatch.setattr(
        wave_assemble,
        "assemble",
        lambda *a, **k: calls.append("assemble") or 0,
    )
    monkeypatch.setattr(
        wave_review,
        "review",
        lambda *a, **k: calls.append("review") or "converged",
    )
    monkeypatch.setattr(wave_review, "land", lambda *a, **k: calls.append("land") or 0)

    exit_code = wave_run.run(
        repo,
        yes=True,
        sleep_fn=_bounded_sleep(),
        clock=_rising_clock(),
    )

    assert exit_code == 0
    assert calls[:2] == ["plan", "launch"]
    assert calls[-3:] == ["assemble", "review", "land"]
    assert "status" in calls[2:-3]


def test_run_status_cadence_skips_the_print_under_ten_minutes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo, wave_path = _repo(tmp_path, {})
    _run_wave_one_lane(wave_path)
    monkeypatch.setattr(wave_launch, "lane_status", _dead_after_n_polls(3))
    monkeypatch.setattr(wave, "plan", lambda *a, **k: 0)
    monkeypatch.setattr(wave_launch, "launch", lambda *a, **k: 0)
    status_calls: list[str] = []
    monkeypatch.setattr(
        wave_launch,
        "status",
        lambda *a, **k: status_calls.append("status") or "lane table",
    )
    monkeypatch.setattr(wave_assemble, "assemble", lambda *a, **k: 0)
    monkeypatch.setattr(wave_review, "review", lambda *a, **k: "converged")
    monkeypatch.setattr(wave_review, "land", lambda *a, **k: 0)

    exit_code = wave_run.run(
        repo,
        yes=True,
        sleep_fn=_bounded_sleep(),
        clock=_stepped_clock(100.0),
    )

    assert exit_code == 0
    assert status_calls == []


def test_run_status_cadence_prints_once_after_crossing_ten_minutes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo, wave_path = _repo(tmp_path, {})
    _run_wave_one_lane(wave_path)
    monkeypatch.setattr(wave_launch, "lane_status", _dead_after_n_polls(2))
    monkeypatch.setattr(wave, "plan", lambda *a, **k: 0)
    monkeypatch.setattr(wave_launch, "launch", lambda *a, **k: 0)
    status_calls: list[str] = []
    monkeypatch.setattr(
        wave_launch,
        "status",
        lambda *a, **k: status_calls.append("status") or "lane table",
    )
    monkeypatch.setattr(wave_assemble, "assemble", lambda *a, **k: 0)
    monkeypatch.setattr(wave_review, "review", lambda *a, **k: "converged")
    monkeypatch.setattr(wave_review, "land", lambda *a, **k: 0)

    exit_code = wave_run.run(
        repo,
        yes=True,
        sleep_fn=_bounded_sleep(),
        clock=_stepped_clock(350.0),
    )

    assert exit_code == 0
    assert status_calls == ["status"]


def test_run_without_tty_needs_yes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    repo, _ = _repo(tmp_path, {})
    monkeypatch.setattr(sys.stdin, "isatty", lambda: False)
    plan_calls: list[str] = []
    monkeypatch.setattr(wave, "plan", lambda *a, **k: plan_calls.append("plan") or 0)

    exit_code = wave_run.run(repo, yes=False)

    assert exit_code == 1
    assert plan_calls == []
    captured = capsys.readouterr()
    assert "--yes" in captured.out + captured.err


def test_run_tty_without_yes_waits_for_confirm_before_launch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo, wave_path = _repo(tmp_path, {})
    _run_wave(wave_path)
    _dead_after_one_pass(monkeypatch)
    monkeypatch.setattr(sys.stdin, "isatty", lambda: True)
    calls: list[str] = []
    monkeypatch.setattr(wave, "plan", lambda *a, **k: calls.append("plan") or 0)
    monkeypatch.setattr(
        wave_launch,
        "launch",
        lambda *a, **k: calls.append("launch") or 0,
    )
    monkeypatch.setattr(wave_launch, "status", lambda *a, **k: "lane table")
    monkeypatch.setattr(wave_assemble, "assemble", lambda *a, **k: 0)
    monkeypatch.setattr(wave_review, "review", lambda *a, **k: "converged")
    monkeypatch.setattr(wave_review, "land", lambda *a, **k: 0)

    def confirm(*args: object, **kwargs: object) -> str:
        calls.append("confirm")
        return ""

    exit_code = wave_run.run(
        repo,
        yes=False,
        confirm_fn=confirm,
        sleep_fn=_bounded_sleep(),
        clock=_rising_clock(),
    )

    assert exit_code == 0
    assert calls[:3] == ["plan", "confirm", "launch"]


def test_run_tty_without_yes_eof_at_confirm_refuses_without_launching(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo, wave_path = _repo(tmp_path, {})
    _run_wave(wave_path)
    monkeypatch.setattr(sys.stdin, "isatty", lambda: True)
    monkeypatch.setattr(wave, "plan", lambda *a, **k: 0)
    launch_calls: list[str] = []
    monkeypatch.setattr(
        wave_launch,
        "launch",
        lambda *a, **k: launch_calls.append("launch") or 0,
    )

    def confirm(*args: object, **kwargs: object) -> str:
        raise EOFError

    exit_code = wave_run.run(repo, yes=False, confirm_fn=confirm)

    assert exit_code == 1
    assert launch_calls == []


def test_run_yes_on_a_tty_skips_the_confirm_prompt(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo, wave_path = _repo(tmp_path, {})
    _run_wave(wave_path)
    _dead_after_one_pass(monkeypatch)
    monkeypatch.setattr(sys.stdin, "isatty", lambda: True)
    monkeypatch.setattr(wave, "plan", lambda *a, **k: 0)
    monkeypatch.setattr(wave_launch, "launch", lambda *a, **k: 0)
    monkeypatch.setattr(wave_launch, "status", lambda *a, **k: "lane table")
    monkeypatch.setattr(wave_assemble, "assemble", lambda *a, **k: 0)
    monkeypatch.setattr(wave_review, "review", lambda *a, **k: "converged")
    monkeypatch.setattr(wave_review, "land", lambda *a, **k: 0)
    confirm_calls: list[str] = []

    def confirm(*args: object, **kwargs: object) -> str:
        confirm_calls.append("confirm")
        return ""

    exit_code = wave_run.run(
        repo,
        yes=True,
        confirm_fn=confirm,
        sleep_fn=_bounded_sleep(),
        clock=_rising_clock(),
    )

    assert exit_code == 0
    assert confirm_calls == []


@pytest.mark.parametrize("review_slots", [0, -1], ids=["zero", "negative"])
def test_run_rejects_a_non_positive_review_slots_before_any_write(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    review_slots: int,
) -> None:
    repo, wave_path = _repo(tmp_path, {})
    plan_calls: list[str] = []
    monkeypatch.setattr(wave, "plan", lambda *a, **k: plan_calls.append("plan") or 0)

    exit_code = wave_run.run(repo, review_slots=review_slots, yes=True)

    assert exit_code == 1
    assert plan_calls == []
    assert not wave_path.exists()


def test_run_writes_a_valid_review_slots_value_into_wave_json(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo, wave_path = _repo(tmp_path, {})
    _run_wave(wave_path)
    _dead_after_one_pass(monkeypatch)
    monkeypatch.setattr(wave, "plan", lambda *a, **k: 0)
    monkeypatch.setattr(wave_launch, "launch", lambda *a, **k: 0)
    monkeypatch.setattr(wave_launch, "status", lambda *a, **k: "lane table")
    monkeypatch.setattr(wave_assemble, "assemble", lambda *a, **k: 0)
    monkeypatch.setattr(wave_review, "review", lambda *a, **k: "converged")
    monkeypatch.setattr(wave_review, "land", lambda *a, **k: 0)

    exit_code = wave_run.run(
        repo,
        review_slots=5,
        yes=True,
        sleep_fn=_bounded_sleep(),
        clock=_rising_clock(),
    )

    assert exit_code == 0
    assert wave.load(wave_path)["review_slots"] == 5


def test_run_exit_code_follows_the_weakest_step(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """assemble reports a lane held back (3); review still converges and
    land still succeeds - the run's own exit code carries assemble's 3
    forward instead of flattening it to 0."""
    repo, wave_path = _repo(tmp_path, {})
    _run_wave(wave_path)
    _dead_after_one_pass(monkeypatch)
    monkeypatch.setattr(wave, "plan", lambda *a, **k: 0)
    monkeypatch.setattr(wave_launch, "launch", lambda *a, **k: 0)
    monkeypatch.setattr(wave_launch, "status", lambda *a, **k: "lane table")
    monkeypatch.setattr(wave_assemble, "assemble", lambda *a, **k: 3)
    monkeypatch.setattr(wave_review, "review", lambda *a, **k: "converged")
    monkeypatch.setattr(wave_review, "land", lambda *a, **k: 0)

    exit_code = wave_run.run(
        repo,
        yes=True,
        sleep_fn=_bounded_sleep(),
        clock=_rising_clock(),
    )

    assert exit_code == 3


def test_run_exit_code_last_nonzero_step_wins(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Pins the combination rule: the LAST non-zero code wins. land's 5
    (master moved between the confirmation gate and land) supersedes
    assemble's earlier 3 - not the reverse, and not a sum or a max."""
    repo, wave_path = _repo(tmp_path, {})
    _run_wave(wave_path)
    _dead_after_one_pass(monkeypatch)
    monkeypatch.setattr(wave, "plan", lambda *a, **k: 0)
    monkeypatch.setattr(wave_launch, "launch", lambda *a, **k: 0)
    monkeypatch.setattr(wave_launch, "status", lambda *a, **k: "lane table")
    monkeypatch.setattr(wave_assemble, "assemble", lambda *a, **k: 3)
    monkeypatch.setattr(wave_review, "review", lambda *a, **k: "converged")
    monkeypatch.setattr(wave_review, "land", lambda *a, **k: 5)

    exit_code = wave_run.run(
        repo,
        yes=True,
        sleep_fn=_bounded_sleep(),
        clock=_rising_clock(),
    )

    assert exit_code == 5


def test_run_returns_1_at_once_when_assemble_refuses(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """assemble's 1 is a refusal (a live lane, or a corrupt/absent
    wave.json), not a kept lane - run must return it immediately instead
    of handing an unmet precondition to review, which would raise
    ValueError."""
    repo, wave_path = _repo(tmp_path, {})
    _run_wave(wave_path)
    _dead_after_one_pass(monkeypatch)
    calls: list[str] = []
    monkeypatch.setattr(wave, "plan", lambda *a, **k: 0)
    monkeypatch.setattr(wave_launch, "launch", lambda *a, **k: 0)
    monkeypatch.setattr(wave_launch, "status", lambda *a, **k: "lane table")
    monkeypatch.setattr(wave_assemble, "assemble", lambda *a, **k: 1)
    monkeypatch.setattr(
        wave_review,
        "review",
        lambda *a, **k: calls.append("review") or "converged",
    )

    exit_code = wave_run.run(
        repo,
        yes=True,
        sleep_fn=_bounded_sleep(),
        clock=_rising_clock(),
    )

    assert exit_code == 1
    assert calls == []


def test_run_calls_land_when_review_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """review_failed must still reach land() - it is the only caller of the
    land() branch that appends the "review_failed" summary line, and the
    run's own exit code carries land's 4 forward."""
    repo, wave_path = _repo(tmp_path, {})
    _run_wave(wave_path)
    _dead_after_one_pass(monkeypatch)
    monkeypatch.setattr(wave, "plan", lambda *a, **k: 0)
    monkeypatch.setattr(wave_launch, "launch", lambda *a, **k: 0)
    monkeypatch.setattr(wave_launch, "status", lambda *a, **k: "lane table")
    monkeypatch.setattr(wave_assemble, "assemble", lambda *a, **k: 0)
    monkeypatch.setattr(wave_review, "review", lambda *a, **k: "review_failed")
    land_calls: list[str] = []
    monkeypatch.setattr(
        wave_review,
        "land",
        lambda *a, **k: land_calls.append("land") or 4,
    )

    exit_code = wave_run.run(
        repo,
        yes=True,
        sleep_fn=_bounded_sleep(),
        clock=_rising_clock(),
    )

    assert land_calls == ["land"]
    assert exit_code == 4


def test_run_interrupt_terminates_lane_groups(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A real SIGINT delivered mid-wait - whether run() installs its own
    signal.signal handler or just lets the default SIGINT -> KeyboardInterrupt
    propagate through a try/except - must call wave_launch's own per-lane
    kill routine for every lane still "running" (the SIGTERM-forwarding
    itself is _kill_lane's own concern, reused rather than reimplemented -
    not re-verified here), mark the wave interrupted, and exit 130.
    _kill_lane itself is faked: its real SIGTERM-then-60s-grace-then-SIGKILL
    escalation needs a genuine process group to observe dying, which these
    made-up lane pids never are."""
    repo, wave_path = _repo(tmp_path, {})
    _run_wave(wave_path)
    monkeypatch.setattr(wave, "plan", lambda *a, **k: 0)
    monkeypatch.setattr(wave_launch, "launch", lambda *a, **k: 0)
    monkeypatch.setattr(wave_launch, "lane_status", lambda lane: "running")
    killed: list[str] = []
    monkeypatch.setattr(
        wave_launch,
        "_kill_lane",
        lambda lane, kill_fn: killed.append(lane["name"]),
    )

    def interrupt(_seconds: float) -> None:
        os.kill(os.getpid(), signal.SIGINT)

    with pytest.raises(SystemExit) as raised:
        wave_run.run(repo, yes=True, sleep_fn=interrupt, clock=lambda: 0.0)

    assert raised.value.code == 130
    assert sorted(killed) == ["l1", "l2"]
    saved_status = wave.load(wave_path)["status"]
    assert saved_status == "interrupted"
    # Not just the literal string: the real per-field validator must accept it too,
    # or `wave assemble`/`plan`/`launch`/`abort` all refuse the saved wave.json.
    assert wave._TOP_CHECKS["status"](saved_status) is True


# ── docs: waves.md names the run() exit codes ───────────────────────────

WAVES_MD = Path(__file__).resolve().parent.parent / "references" / "waves.md"


def test_docs_name_the_exit_codes() -> None:
    text = WAVES_MD.read_text(encoding="utf-8")
    assert "## wave run" in text
    section = text.split("## wave run", 1)[1].split("\n## ", 1)[0]
    for code, phrase in (
        ("0", "landed"),
        ("1", "precondition refused"),
        ("3", "assemble kept a lane"),
        ("4", "review failed"),
        ("5", "master moved"),
    ):
        assert re.search(rf"(?<!\d){code}(?!\d)", section), code
        assert phrase in section, phrase


# ── wave.py: WAVE_STATUSES ───────────────────────────────────────────────


def test_wave_statuses_include_converged_and_review_failed() -> None:
    assert "converged" in wave.WAVE_STATUSES
    assert "review_failed" in wave.WAVE_STATUSES
    assert wave._TOP_CHECKS["status"]("converged") is True
    assert wave._TOP_CHECKS["status"]("review_failed") is True


def test_wave_statuses_include_interrupted() -> None:
    assert "interrupted" in wave.WAVE_STATUSES
    assert wave._TOP_CHECKS["status"]("interrupted") is True


# ── wave_cli.py: review/land/run verbs ───────────────────────────────────


def test_wave_cli_registers_review_land_run_as_wave_subverbs() -> None:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers()
    wave_cli.add(subparsers)

    review_args = parser.parse_args(["wave", "review", "--state", "x"])
    assert review_args.verb == "review"

    land_args = parser.parse_args(["wave", "land", "--state", "x"])
    assert land_args.verb == "land"

    run_args = parser.parse_args(
        ["wave", "run", "--max-lanes", "2", "--review-slots", "1", "--yes"],
    )
    assert run_args.verb == "run"
    assert run_args.max_lanes == 2
    assert run_args.review_slots == 1
    assert run_args.yes is True
