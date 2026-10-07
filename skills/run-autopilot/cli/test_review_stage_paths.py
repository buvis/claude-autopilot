#!/usr/bin/env python3
"""Gate-command reuse and path-refusal tests for cli/review_stage.stage()
(PRD 00266). Fixtures and helpers come from test_review_stage.py."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from cli import review_stage, verification
from cli import test_review_stage as base
from cli.__main__ import main

AUTOPILOT_REL = base.AUTOPILOT_REL
CYCLE = base.CYCLE
GATE = base.GATE
TASKS = base.TASKS
env = base.env
_git = base._git
_commit = base._commit
_stage = base._stage


def test_stage_runs_the_gate_when_the_recorded_command_differs(env: dict) -> None:
    repo = env["repo"]
    head = _git(repo, "rev-parse", "HEAD")
    record = {
        "sha": head,
        "cycle": 1,
        "commands": [{"command": "true", "exit": 0}],
        "passed": 4242,
        "failed": 0,
        "skipped": 0,
    }
    # Committed, like a real one: store-only since `head`, clean tree.
    _commit(repo, {str(verification.RECORD_REL): json.dumps(record)})

    summary = _stage(env)

    assert summary["gate"]["verdict"] == "stale"
    assert "4242" not in summary["gate"]["tests_line"]
    assert summary["gate"]["tests_line"].startswith("Tests: 3 passed, 0 failed")


def _state_file(env: dict, **fields: object) -> Path:
    path = env["repo"] / AUTOPILOT_REL / "state.json"
    data = {"phase": "review", "tasks": TASKS, "prd": "00001-calc-v1.md", **fields}
    path.write_text(json.dumps(data))
    return path


def _cli_stage(
    env: dict, monkeypatch: pytest.MonkeyPatch, state_path: Path
) -> tuple[int, list]:
    calls: list = []
    monkeypatch.setattr(
        review_stage, "stage", lambda *a, **kw: calls.append(kw) or {"ok": True}
    )
    argv = ["review-stage", "--cycle-id", CYCLE, "--gate-command", GATE]
    argv += ["--repo-root", str(env["repo"]), "--state", str(state_path)]
    return main(argv), calls


def test_stage_refuses_a_prd_outside_wip(
    env: dict, monkeypatch: pytest.MonkeyPatch
) -> None:
    prds = env["repo"] / "docs/dev/project-management/prds"
    (prds / "wip").mkdir(parents=True)
    (prds / "wip" / "00001-calc-v1.md").write_text("# in wip\n")
    (prds / "outside.md").write_text("OUTSIDE-MARKER\n")

    code, calls = _cli_stage(env, monkeypatch, _state_file(env))
    assert code == 0 and len(calls) == 1  # control: a PRD inside wip/ is staged

    code, calls = _cli_stage(env, monkeypatch, _state_file(env, prd="../outside.md"))
    assert code != 0
    assert calls == []


def test_stage_refuses_a_design_doc_outside_the_repo(
    env: dict, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = env["repo"] / "docs/dev/project-management"
    (store / "prds" / "wip").mkdir(parents=True)
    (store / "prds" / "wip" / "00001-calc-v1.md").write_text("# in wip\n")
    (store / "designs").mkdir(parents=True)
    (store / "designs" / "d.md").write_text("design\n")

    inside = _state_file(env, design_doc="docs/dev/project-management/designs/d.md")
    code, calls = _cli_stage(env, monkeypatch, inside)
    assert code == 0 and len(calls) == 1  # control: a design doc in the repo

    for escape in (str(env["design"]), "../design.md"):
        code, calls = _cli_stage(env, monkeypatch, _state_file(env, design_doc=escape))
        assert code != 0, escape
        assert calls == [], escape


def test_stage_refuses_a_symlinked_tmp_outside_the_repo(env: dict) -> None:
    outside = env["tmp"] / "elsewhere"
    outside.mkdir()
    (env["repo"] / "docs" / "dev").mkdir(parents=True, exist_ok=True)
    (env["repo"] / "docs" / "dev" / "tmp").symlink_to(outside)

    summary = _stage(env)

    assert summary["ok"] is False
    assert "resolves outside the repo" in summary["error"]
    assert list(outside.iterdir()) == []


def test_stage_refuses_a_symlinked_dev_dir_before_creating_tmp(env: dict) -> None:
    outside = env["tmp"] / "elsewhere"
    outside.mkdir()
    dev = env["repo"] / "docs" / "dev"
    dev.rename(env["tmp"] / "moved-dev")
    dev.symlink_to(outside)

    summary = _stage(env)

    assert summary["ok"] is False
    assert "resolves outside the repo" in summary["error"]
    assert list(outside.iterdir()) == []


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
