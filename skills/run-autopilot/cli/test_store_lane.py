#!/usr/bin/env python3
"""Tests for keeping store commits out of lane routing and out of wave
lanes: store_tree's exclude pathspecs (derived from the store prefixes,
so a new store root needs no second edit), its wave-lane predicate, and
the `record-store` verb's wave-lane gate.

A new file rather than an addition to test_store_tree.py, which is at its
size ceiling. Written from the design contract only.
"""

from __future__ import annotations

import inspect
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from cli import __main__ as cli_main
from cli import store_tree

LANE_VAR = "_AUTOPILOT_REVIEW_SLOTS_DIR"
SHA = "0123456789abcdef0123456789abcdef01234567"


def _run(argv: list[str]) -> int:
    try:
        return cli_main.main(argv)
    except SystemExit as exc:
        return exc.code


def _state(tmp_path: Path, repo: Path) -> Path:
    autopilot = tmp_path / "docs" / "dev" / "project-management" / "autopilot"
    autopilot.mkdir(parents=True)
    path = autopilot / "state.json"
    path.write_text(json.dumps({"repo_root": str(repo)}), encoding="utf-8")
    return path


def _spy(answer: object, calls: list) -> object:
    """A stand-in for store_tree.record_store recording its positional
    parameters by the real signature, however the caller spelled them."""
    signature = inspect.signature(store_tree.record_store)

    def spy(*args: object, **kwargs: object) -> object:
        calls.append(signature.bind(*args, **kwargs).args)
        return answer

    return spy


def _record_store_argv(state_path: Path) -> list[str]:
    return [
        "record-store",
        "--state",
        str(state_path),
        "--site",
        "build",
        "--prd",
        "00236-x.md",
    ]


# -- the exclude pathspecs ----------------------------------------------------


def test_every_store_prefix_has_its_own_exclude_pathspec() -> None:
    derived = tuple(
        ":(exclude)" + prefix.removesuffix("/") for prefix in store_tree.STORE_PREFIXES
    )

    assert derived == store_tree.STORE_EXCLUDE_PATHSPECS, (
        "a store root added to STORE_PREFIXES must be excluded without a second edit"
    )
    # Today's two roots, spelled out once so the derivation above is readable.
    assert derived == (
        ":(exclude)docs/dev/project-management",
        ":(exclude)docs/dev/tmp",
    )


# -- the wave-lane predicate --------------------------------------------------


@pytest.mark.parametrize(
    ("env", "expected"),
    [
        ({LANE_VAR: "/tmp/wave-slots"}, True),
        ({LANE_VAR: "x", "PATH": "/usr/bin"}, True),
        ({LANE_VAR: ""}, False),
        ({"PATH": "/usr/bin"}, False),
        ({}, False),
    ],
    ids=[
        "slots-dir-set",
        "slots-dir-among-other-variables",
        "slots-dir-empty",
        "slots-dir-missing",
        "empty-environment",
    ],
)
def test_only_a_non_empty_review_slots_dir_marks_a_wave_lane(
    env: dict[str, str],
    expected: bool,
) -> None:
    assert store_tree.in_wave_lane(env) is expected


def test_in_wave_lane_reads_the_environment_at_call_time(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Every value below lands after import: one captured at import time
    # would answer the same way three times.
    monkeypatch.delenv(LANE_VAR, raising=False)
    assert store_tree.in_wave_lane() is False

    monkeypatch.setenv(LANE_VAR, "/tmp/wave-slots")
    assert store_tree.in_wave_lane() is True
    assert store_tree.in_wave_lane(None) is True

    monkeypatch.setenv(LANE_VAR, "")
    assert store_tree.in_wave_lane() is False


# -- the `record-store` verb --------------------------------------------------


@pytest.mark.parametrize(
    "lane_value",
    [None, ""],
    ids=["no-slots-dir", "empty-slots-dir"],
)
def test_the_record_store_verb_commits_outside_a_wave_lane(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture,
    lane_value: str | None,
) -> None:
    if lane_value is None:
        monkeypatch.delenv(LANE_VAR, raising=False)
    else:
        monkeypatch.setenv(LANE_VAR, lane_value)
    repo = tmp_path / "elsewhere"
    state_path = _state(tmp_path, repo)
    calls: list[tuple] = []
    monkeypatch.setattr(store_tree, "record_store", _spy(SHA, calls))

    code = _run(_record_store_argv(state_path))

    assert code == 0
    assert [args[:3] for args in calls] == [(repo, "build", "00236-x.md")], calls
    assert capsys.readouterr().out.strip() == SHA


def test_the_record_store_verb_records_nothing_inside_a_wave_lane(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture,
) -> None:
    monkeypatch.setenv(LANE_VAR, str(tmp_path / "wave-slots"))
    repo = tmp_path / "elsewhere"
    state_path = _state(tmp_path, repo)
    calls: list[tuple] = []
    monkeypatch.setattr(store_tree, "record_store", _spy(SHA, calls))

    code = _run(_record_store_argv(state_path))

    assert code == 0, "a lane skips the record, it does not fail"
    assert calls == [], "a lane branch takes no store commit"
    assert capsys.readouterr().out == ""
