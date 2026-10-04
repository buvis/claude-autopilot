#!/usr/bin/env python3
"""Tests for cli/review_close.py (PRD 00249 task 4).

Every test runs close() against a real state.json in tmp_path through the
real statectl/state boundary; only the seams a test is about are spied on.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from cli import gate, rework_groups, review_close, schema, statectl

CRIT = "\U0001f534"
HIGH = "\U0001f7e0"
MED = "\U0001f7e1"

D_LINES = "D1: pass\nD2: fail\nD3: pass\nD4: pass\nD5: pass\n"


def _review(
    tmp_path: Path,
    *,
    d_lines: str = D_LINES,
    verdict: str = "Verdict: 3 findings\n",
    agents: str = "  alice: available\n  bob: available\n",
    extra_frontmatter: str = "",
    name: str = "00249-x-review-01.md",
) -> Path:
    text = (
        "---\n"
        "reviewers: alice,bob\n"
        "agents:\n"
        f"{agents}"
        f"{extra_frontmatter}"
        "---\n\n"
        "# Review\n\n"
        "## Alice\n\nOne finding.\n\n"
        "## Bob\n\n"
        f"{d_lines}\n"
        "Some doubts.\n\n"
        f"{verdict}"
        "Tests: 12 passed, 0 failed\n"
    )
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return path


def _state(tmp_path: Path, **extra: object) -> Path:
    data = {
        "cycle": 2,
        "tasks": [{"id": "1", "name": "original", "status": "completed"}],
        "tasks_total": 1,
        "rework_task_ids": [],
        "deferred_decisions": [],
        **extra,
    }
    path = tmp_path / "state.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _finding(sev: str, file: str, issue: str, cls: str = "fix") -> dict:
    return {
        "severity": sev,
        "file": file,
        "issue": issue,
        "classification": cls,
        "found_by": ["bob"],
    }


def test_close_adds_one_task_per_group(tmp_path: Path) -> None:
    review = _review(tmp_path, agents="  alice: available\n  bob: unavailable\n")
    state_path = _state(tmp_path)
    findings = [
        _finding(CRIT, "src/a.py:3", "crash on empty input"),
        _finding(HIGH, "src/b.py:10", "wrong default"),
        _finding(MED, "src/b.py:20", "unclear name"),
    ]

    result = review_close.close(review, state_path, "decision-gate", findings)

    data = _load(state_path)
    new_tasks = [t for t in data["tasks"] if t["id"] != "1"]
    assert result["applied"] is True
    assert [t["name"] for t in new_tasks] == ["[D2] src/a.py", "[D2] src/b.py"]
    assert result["tasks_created"] == ["2", "3"]
    assert data["rework_task_ids"] == ["2", "3"]
    assert result["rework_task_ids"] == ["2", "3"]
    assert all(t["model"] == "sonnet" and t["status"] == "pending" for t in new_tasks)
    b_desc = new_tasks[1]["description"]
    assert b_desc.startswith("### Findings (verbatim)\n")
    assert "wrong default" in b_desc and "unclear name" in b_desc
    assert "crash on empty input" not in b_desc
    assert data["tasks_total"] == 3
    assert result["lenses_closed"] == {"consensus": "done", "doubt": "failed"}
    assert data["review_lenses"] == {"consensus": "done", "doubt": "failed"}


def test_close_is_idempotent(tmp_path: Path) -> None:
    review = _review(tmp_path)
    state_path = _state(tmp_path)
    findings = [_finding(HIGH, "src/b.py", "wrong default")]

    first = review_close.close(review, state_path, "decision-gate", findings)
    after_first = _load(state_path)
    second = review_close.close(review, state_path, "decision-gate", findings)

    assert first["applied"] is True
    assert second == {"applied": False, "reason": "already applied"}
    assert _load(state_path) == after_first
    assert len(after_first["applied_review_batches"]) == 1


def test_close_refuses_a_gate_failing_review_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    review = _review(tmp_path, verdict="")  # no Verdict: line -> gate exit 1
    state_path = _state(tmp_path)
    before = state_path.read_bytes()

    def _no_mutate(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("a gate-failing review must open no transaction")

    monkeypatch.setattr(statectl, "mutate", _no_mutate)
    result = review_close.close(
        review, state_path, "decision-gate", [_finding(HIGH, "x.py", "y")]
    )

    assert result["applied"] is False
    assert "no verdict line" in result["reason"]
    assert state_path.read_bytes() == before
    assert not Path(f"{state_path}.lock").exists()
    assert not Path(f"{state_path}.bak").exists()


def test_close_records_doubt_verdicts(tmp_path: Path) -> None:
    state_path = _state(tmp_path)
    review = _review(tmp_path)

    review_close.close(review, state_path, "decision-gate", [])

    assert _load(state_path)["doubts_rubric_verdicts"] == [
        {"rule_id": "D1", "verdict": "pass"},
        {"rule_id": "D2", "verdict": "fail"},
        {"rule_id": "D3", "verdict": "pass"},
        {"rule_id": "D4", "verdict": "pass"},
        {"rule_id": "D5", "verdict": "pass"},
    ]

    # A review file with no D{n} lines must not wipe what is recorded.
    bare = _review(tmp_path, d_lines="", name="tail.md")
    review_close.close(bare, state_path, "tail-sweep", [])
    assert len(_load(state_path)["doubts_rubric_verdicts"]) == 5


def test_close_group_uses_emoji_severity_not_english_word(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    review = _review(tmp_path)
    state_path = _state(tmp_path)
    seen: list[list[dict]] = []
    real_group = rework_groups.group

    def _spy(findings: list[dict]) -> list[dict]:
        seen.append(findings)
        return real_group(findings)

    monkeypatch.setattr(rework_groups, "group", _spy)
    findings = [
        _finding(CRIT, "src/a.py:1", "critical bug"),
        _finding(HIGH, "src/a.py:9", "high bug"),
    ]

    review_close.close(review, state_path, "decision-gate", findings)

    assert [f["severity"] for f in seen[0]] == [CRIT, HIGH]
    # The critical finding splits off into its own task: an English
    # "critical" would miss rework_groups' exact-emoji check and merge.
    names = [t["name"] for t in _load(state_path)["tasks"][1:]]
    assert names == ["[D2] src/a.py", "[D2] src/a.py"]


def test_close_idempotency_check_is_inside_the_transaction(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Two racing calls: the rival commits after the first call has passed
    every pre-lock step but before it takes the lock. Only an in-lock check
    can see the rival's commit, so exactly one call wins."""
    review = _review(tmp_path)
    state_path = _state(tmp_path)
    findings = [_finding(HIGH, "src/b.py", "wrong default")]
    real_mutate = statectl.mutate
    rival: list[dict] = []

    def _racing_mutate(path: Path, apply: object) -> object:
        if not rival:
            rival.append({})
            rival[0] = review_close.close(review, state_path, "decision-gate", findings)
        return real_mutate(path, apply)

    monkeypatch.setattr(statectl, "mutate", _racing_mutate)
    first = review_close.close(review, state_path, "decision-gate", findings)

    assert rival[0]["applied"] is True
    assert first == {"applied": False, "reason": "already applied"}
    assert len(_load(state_path)["tasks"]) == 2


def test_close_decision_gate_and_tail_sweep_batches_are_independently_idempotent(
    tmp_path: Path,
) -> None:
    review = _review(tmp_path)
    state_path = _state(tmp_path)
    gate_findings = [_finding(HIGH, "src/b.py", "wrong default")]
    tail_findings = [_finding(MED, "src/c.py", "small nit")]

    gate_first = review_close.close(review, state_path, "decision-gate", gate_findings)
    tail_first = review_close.close(review, state_path, "tail-sweep", tail_findings)
    gate_again = review_close.close(review, state_path, "decision-gate", gate_findings)
    tail_again = review_close.close(review, state_path, "tail-sweep", tail_findings)

    assert gate_first["applied"] is True and tail_first["applied"] is True
    assert gate_again["applied"] is False and tail_again["applied"] is False
    data = _load(state_path)
    assert [t["name"] for t in data["tasks"][1:]] == [
        "[D2] src/b.py",
        "[D2] Tail sweep: src/c.py",
    ]
    identity = str(review.resolve())
    assert data["applied_review_batches"] == [
        f"{identity}::decision-gate",
        f"{identity}::tail-sweep",
    ]


def test_close_state_mutations_use_parse_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    review = _review(tmp_path, agents="  alice: available\n  blake: available\n")
    state_path = _state(tmp_path)
    paths: list[object] = []
    real_set, real_append = statectl.do_set, statectl.do_append

    def _spy_set(data: object, tokens: object, value: object) -> None:
        paths.append(tokens)
        real_set(data, tokens, value)

    def _spy_append(data: object, tokens: object, value: object) -> None:
        paths.append(tokens)
        real_append(data, tokens, value)

    monkeypatch.setattr(statectl, "do_set", _spy_set)
    monkeypatch.setattr(statectl, "do_append", _spy_append)
    findings = [
        _finding(HIGH, "src/b.py", "wrong default"),
        _finding(MED, "src/c.py", "later", "defer"),
    ]

    review_close.close(review, state_path, "decision-gate", findings)

    assert paths, "close() must route its writes through do_set/do_append"
    assert all(isinstance(p, list) for p in paths), paths
    assert ["rework_task_ids"] in paths
    assert ["deferred_decisions"] in paths
    assert ["doubts_rubric_verdicts"] in paths
    assert ["review_lenses", "blind"] in paths
    assert ["applied_review_batches"] in paths
    # A bare string would have been walked char by char into nested keys.
    assert not {"r", "a", "d"} & set(_load(state_path))


def test_close_uses_statectl_mutate_scoped_validator(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    review = _review(tmp_path)
    # An unrelated pre-existing odd field: whole-state validation refuses
    # the write, the scoped validator leaves it alone.
    state_path = _state(tmp_path, phase="not-a-phase")
    calls: list[Path] = []
    real_mutate = statectl.mutate

    def _spy(path: Path, apply: object) -> object:
        calls.append(Path(path))
        return real_mutate(path, apply)

    monkeypatch.setattr(statectl, "mutate", _spy)
    with pytest.raises(schema.SchemaError):
        schema.validate(_load(state_path))

    result = review_close.close(
        review, state_path, "decision-gate", [_finding(HIGH, "src/b.py", "x")]
    )

    assert calls == [state_path]
    assert result["applied"] is True
    assert _load(state_path)["phase"] == "not-a-phase"


def test_close_maps_every_classification_row_to_a_chosen_finding_value(
    tmp_path: Path,
) -> None:
    review = _review(tmp_path)
    state_path = _state(tmp_path)
    findings = [
        _finding(HIGH, "src/fix.py", "fix me", "fix"),
        _finding(MED, "src/defer.py", "defer me", "defer"),
        _finding(MED, "src/verify.py", "verify me", "verify"),
        _finding(MED, "src/discard.py", "discard me", "discard"),
    ]

    result = review_close.close(review, state_path, "decision-gate", findings)

    data = _load(state_path)
    new_tasks = data["tasks"][1:]
    assert [t["name"] for t in new_tasks] == ["[D2] src/fix.py"]
    assert result["tasks_created"] == [new_tasks[0]["id"]]
    assert data["deferred_decisions"] == [
        {
            "issue": "defer me",
            "severity": MED,
            "file": "src/defer.py",
            "reason": "deferred by review-close",
        }
    ]
    every_text = json.dumps(data, ensure_ascii=False)
    assert "verify me" not in every_text
    assert "discard me" not in every_text


def test_close_omits_found_by_suffix_when_no_author(tmp_path: Path) -> None:
    review = _review(tmp_path)
    state_path = _state(tmp_path)
    finding = _finding(HIGH, "src/b.py", "wrong default")
    finding["found_by"] = []

    review_close.close(review, state_path, "decision-gate", [finding])

    desc = _load(state_path)["tasks"][1]["description"]
    assert "(found by:" not in desc
    assert "wrong default" in desc


def test_close_threads_require_codex_guard_flag_to_the_gate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    review = _review(tmp_path)
    state_path = _state(tmp_path)
    calls: list[bool | None] = []
    real_run_gate = gate.run_gate

    def _spy(review_file, reviewers=None, require_codex_guard=False):
        calls.append(require_codex_guard)
        return real_run_gate(
            review_file, reviewers=reviewers, require_codex_guard=require_codex_guard
        )

    monkeypatch.setattr(review_close.gate, "run_gate", _spy)

    review_close.close(
        review, state_path, "decision-gate", [], require_codex_guard=True
    )
    review_close.close(
        review, state_path, "tail-sweep", [], require_codex_guard=False
    )

    assert calls == [True, False]


def test_close_tail_sweep_skips_lens_verdict_and_dispatch_row_steps(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    review = _review(tmp_path, extra_frontmatter="dispatch_rows:\n  bob: d-999\n")
    state_path = _state(
        tmp_path,
        review_lenses={"consensus": "running"},
        doubts_rubric_verdicts=[{"rule_id": "D9", "verdict": "pass"}],
    )
    commands: list[list[str]] = []
    monkeypatch.setattr(
        review_close.subprocess, "run", lambda cmd, **_kwargs: commands.append(cmd)
    )

    result = review_close.close(review, state_path, "tail-sweep", [])

    assert result["applied"] is True
    data = _load(state_path)
    assert data["review_lenses"] == {"consensus": "running"}
    assert data["doubts_rubric_verdicts"] == [{"rule_id": "D9", "verdict": "pass"}]
    assert commands == []


def test_close_ends_frontmatter_dispatch_rows_best_effort(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    review = _review(
        tmp_path,
        extra_frontmatter="dispatch_rows:\n  bob: d-111\n  carl: d-222\n",
    )
    state_path = _state(tmp_path)
    commands: list[list[str]] = []

    def _fake_run(cmd: list[str], **_kwargs: object) -> None:
        commands.append(cmd)
        raise subprocess.CalledProcessError(1, cmd)

    monkeypatch.setattr(review_close.subprocess, "run", _fake_run)

    result = review_close.close(review, state_path, "decision-gate", [])

    assert result["applied"] is True
    assert [cmd[cmd.index("end") + 1] for cmd in commands] == ["d-111", "d-222"]
    assert all(cmd[-2:] == ["--outcome", "ok"] for cmd in commands)
    assert _load(state_path)["applied_review_batches"]
