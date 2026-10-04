#!/usr/bin/env python3
"""Tests for the `review-stage` and `review-close` CLI verbs (PRD 00249 task 5).

Both handlers are thin wrappers: stage() and close() have their own suites
(test_review_stage.py, test_review_close.py), so these tests swap them for
recorders and prove only the CLI side - registration, how the inputs are
built (autopilot mode reads state.json, standalone mode reads flags), the
one-line JSON print, and the exit codes.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from cli import review_close, review_stage
from cli.__main__ import _SUBCOMMANDS, main

PRD = "00249-x-v1.md"
DESIGN_REL = "docs/dev/project-management/designs/00249-x-v1-design.md"
GATE = "make test"
TASKS = [{"id": "1", "name": "first", "status": "completed"}]


def _state(tmp_path: Path, **extra: object) -> Path:
    autopilot = tmp_path / "docs/dev/project-management/autopilot"
    autopilot.mkdir(parents=True)
    path = autopilot / "state.json"
    data = {"prd": PRD, "phase": "review", "tasks": TASKS, **extra}
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


@pytest.fixture
def staged(monkeypatch: pytest.MonkeyPatch) -> dict:
    """Swap stage() for a recorder; `result` is what it returns."""
    seen: dict = {"result": {"ok": True, "mode": "autopilot"}}

    def fake_stage(*args, **kwargs) -> dict:
        seen["args"], seen["kwargs"] = args, kwargs
        return seen["result"]

    monkeypatch.setattr(review_stage, "stage", fake_stage)
    return seen


@pytest.fixture
def closed(monkeypatch: pytest.MonkeyPatch) -> dict:
    """Swap close() for a recorder; `result` is what it returns."""
    seen: dict = {"result": {"applied": True, "tasks_created": ["2"]}}

    def fake_close(*args) -> dict:
        seen["args"] = args
        return seen["result"]

    monkeypatch.setattr(review_close, "close", fake_close)
    return seen


def _stage_argv(tmp_path: Path, *extra: str) -> list[str]:
    return [
        "review-stage",
        "--cycle-id",
        "00249-c1",
        "--gate-command",
        GATE,
        "--repo-root",
        str(tmp_path),
        *extra,
    ]


@pytest.mark.parametrize("verb", ["review-stage", "review-close"])
def test_cli_registers_review_stage_and_close(
    verb: str, capsys: pytest.CaptureFixture[str]
) -> None:
    assert verb in _SUBCOMMANDS
    with pytest.raises(SystemExit) as exc:
        main([verb, "--help"])
    assert exc.value.code == 0
    assert verb in capsys.readouterr().out


def test_review_stage_builds_autopilot_inputs_from_state(
    tmp_path: Path, staged: dict, capsys: pytest.CaptureFixture[str]
) -> None:
    state_path = _state(
        tmp_path,
        design_doc=DESIGN_REL,
        review_lenses={"consensus": "done", "blind": "done", "doubt": "done"},
        doubt_reviewer="codex",
    )

    code = main(_stage_argv(tmp_path, "--state", str(state_path), "--since", "abc"))

    assert code == 0
    kwargs = staged["kwargs"]
    assert kwargs["cycle_id"] == "00249-c1"
    assert kwargs["tasks"] == TASKS
    assert kwargs["prd_path"] == state_path.parents[1] / "prds" / "wip" / PRD
    assert kwargs["design_doc"] == tmp_path / DESIGN_REL
    assert kwargs["roster"] == ["alice", "bob", "carl", "blake"]
    assert kwargs["repo_root"] == tmp_path
    assert kwargs["gate_command"] == GATE
    assert kwargs["replay_cmd"] is None
    assert kwargs["since"] == "abc"
    assert kwargs["state_path"] == state_path
    assert json.loads(capsys.readouterr().out) == staged["result"]


def test_review_stage_fable_doubt_reviewer_puts_eve_on_the_roster(
    tmp_path: Path, staged: dict
) -> None:
    # No review_lenses yet (first cycle): the standard lenses, plus Eve.
    state_path = _state(tmp_path, doubt_reviewer="fable")

    assert main(_stage_argv(tmp_path, "--state", str(state_path))) == 0

    assert staged["kwargs"]["roster"] == ["alice", "bob", "carl", "blake", "eve"]


def test_review_stage_codex_implemented_task_forces_eve_onto_the_roster(
    tmp_path: Path, staged: dict
) -> None:
    # review-work-completion's codex doubt-roster guard: the doubt leg must
    # not be codex alone, whatever state.doubt_reviewer says.
    tasks = [{"id": "1", "attempts": [{"implementor": "codex"}]}]
    state_path = _state(tmp_path, tasks=tasks, doubt_reviewer="codex")

    assert main(_stage_argv(tmp_path, "--state", str(state_path))) == 0

    assert staged["kwargs"]["roster"] == ["alice", "bob", "carl", "blake", "eve"]


def test_review_stage_roster_flag_overrides_the_state_roster(
    tmp_path: Path, staged: dict
) -> None:
    state_path = _state(tmp_path)

    code = main(_stage_argv(tmp_path, "--state", str(state_path), "--roster", "blake"))

    assert code == 0
    assert staged["kwargs"]["roster"] == ["blake"]


@pytest.mark.parametrize("flag", ["--tasks-json", "--prd", "--design-doc"])
def test_review_stage_refuses_standalone_inputs_beside_state(
    tmp_path: Path, staged: dict, flag: str, capsys: pytest.CaptureFixture[str]
) -> None:
    state_path = _state(tmp_path)

    code = main(_stage_argv(tmp_path, "--state", str(state_path), flag, "x"))

    assert code == 1
    assert "args" not in staged
    assert flag in capsys.readouterr().err


def test_review_stage_standalone_reads_flags_and_skips_state(
    tmp_path: Path, staged: dict
) -> None:
    tasks_json = tmp_path / "tasks.json"
    tasks_json.write_text(json.dumps(TASKS), encoding="utf-8")
    prd = tmp_path / PRD

    code = main(
        _stage_argv(
            tmp_path,
            "--tasks-json",
            str(tasks_json),
            "--prd",
            str(prd),
            "--roster",
            "alice, blake,alice",
            "--replay-cmd",
            "pytest",
        )
    )

    assert code == 0
    kwargs = staged["kwargs"]
    assert kwargs["tasks"] == TASKS
    assert kwargs["prd_path"] == prd
    assert kwargs["design_doc"] is None
    assert kwargs["roster"] == ["alice", "blake"]
    assert kwargs["replay_cmd"] == "pytest"
    assert kwargs["state_path"] is None


@pytest.mark.parametrize("missing", ["--tasks-json", "--prd", "--roster"])
def test_review_stage_standalone_refuses_without_its_inputs(
    tmp_path: Path,
    staged: dict,
    missing: str,
    capsys: pytest.CaptureFixture[str],
) -> None:
    tasks_json = tmp_path / "tasks.json"
    tasks_json.write_text("[]", encoding="utf-8")
    flags = {"--tasks-json": str(tasks_json), "--prd": "p.md", "--roster": "alice"}
    del flags[missing]

    code = main(_stage_argv(tmp_path, *[x for kv in flags.items() for x in kv]))

    assert code == 1
    assert "args" not in staged
    assert missing in capsys.readouterr().err


def test_review_stage_propagates_a_gather_refusal_exit(
    tmp_path: Path, staged: dict, capsys: pytest.CaptureFixture[str]
) -> None:
    staged["result"] = {"ok": False, "error": "empty diff", "exit": 3}

    code = main(_stage_argv(tmp_path, "--state", str(_state(tmp_path))))

    assert code == 3
    captured = capsys.readouterr()
    assert json.loads(captured.out) == staged["result"]
    assert "empty diff" in captured.err


def _findings(tmp_path: Path, payload: object) -> Path:
    path = tmp_path / "findings.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _close_argv(tmp_path: Path, findings: Path, *extra: str) -> list[str]:
    return [
        "review-close",
        "--review-file",
        str(tmp_path / "review.md"),
        "--state",
        str(tmp_path / "state.json"),
        "--batch-id",
        "decision-gate",
        "--findings",
        str(findings),
        *extra,
    ]


def test_review_close_passes_findings_through_and_exits_zero_when_applied(
    tmp_path: Path, closed: dict, capsys: pytest.CaptureFixture[str]
) -> None:
    chosen = [{"severity": "x", "file": "a.py", "issue": "i", "classification": "fix"}]
    findings = _findings(tmp_path, chosen)

    code = main(_close_argv(tmp_path, findings, "--default-tier", "opus"))

    assert code == 0
    assert closed["args"] == (
        tmp_path / "review.md",
        tmp_path / "state.json",
        "decision-gate",
        chosen,
        "opus",
    )
    assert json.loads(capsys.readouterr().out) == closed["result"]


def test_review_close_exits_nonzero_with_the_reason_when_not_applied(
    tmp_path: Path, closed: dict, capsys: pytest.CaptureFixture[str]
) -> None:
    closed["result"] = {"applied": False, "reason": "already applied"}

    code = main(_close_argv(tmp_path, _findings(tmp_path, [])))

    assert code != 0
    captured = capsys.readouterr()
    assert json.loads(captured.out) == closed["result"]
    assert "already applied" in captured.err


@pytest.mark.parametrize(
    "payload",
    [
        pytest.param({"classification": "fix"}, id="not_a_list"),
        pytest.param(["fix"], id="element_not_a_dict"),
        pytest.param([{"file": "a.py"}], id="no_classification"),
    ],
)
def test_review_close_refuses_a_malformed_findings_file_before_close(
    tmp_path: Path, closed: dict, payload: object
) -> None:
    code = main(_close_argv(tmp_path, _findings(tmp_path, payload)))

    assert code == 2
    assert "args" not in closed


def test_review_close_rejects_an_unknown_batch_id(tmp_path: Path) -> None:
    argv = _close_argv(tmp_path, _findings(tmp_path, []))
    argv[argv.index("decision-gate")] = "cycle-3"

    with pytest.raises(SystemExit) as exc:
        main(argv)
    assert exc.value.code == 1
