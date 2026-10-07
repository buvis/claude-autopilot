#!/usr/bin/env python3
"""Pre-existing close() behavior for cli/review_close.py (PRD 00249 task 4).

These tests pin behavior that predates the findings cross-check and the carry
match: task grouping, idempotency, lens bookkeeping, dispatch rows. They live
beside test_review_close.py (which keeps the cross-check and the four
acceptance-named carry tests) so neither module runs past the file-size limit;
fixtures are shared from there.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from cli import gate, review_close, rework_groups, schema, statectl
from cli.test_review_close import (
    CRIT,
    HIGH,
    MED,
    _carry_state,
    _carry_task,
    _finding,
    _load,
    _review,
    _state,
)


# Pins pre-existing one-task-per-group behavior; unrelated to the new cross-check.
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
    # blake/carl/eve have no line at all under agents: here, so the
    # missing-persona fail-safe closes their lenses as "lost" - never
    # dispatched is a different fact from reported-and-failed, which is
    # bob's case: present with an unrecognized status, so still "failed".
    expected_lenses = {
        "consensus": "done",
        "doubt": "failed",
        "blind": "lost",
        "ui": "lost",
        "fable": "lost",
    }
    assert result["lenses_closed"] == expected_lenses
    assert data["review_lenses"] == expected_lenses


# Pins pre-existing idempotency behavior; unrelated to the new cross-check.
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


# Pins pre-existing gate-failure refusal behavior; unrelated to the new cross-check.
def test_close_refuses_a_gate_failing_review_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    review = _review(tmp_path, verdict="")  # no Verdict: line -> gate exit 1
    state_path = _state(tmp_path)
    before = state_path.read_bytes()

    def _no_mutate(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("a gate-failing review must open no transaction")

    monkeypatch.setattr(statectl, "mutate", _no_mutate)
    result = review_close.close(
        review,
        state_path,
        "decision-gate",
        [_finding(HIGH, "x.py", "y")],
    )

    assert result["applied"] is False
    assert "no verdict line" in result["reason"]
    assert state_path.read_bytes() == before
    assert not Path(f"{state_path}.lock").exists()
    assert not Path(f"{state_path}.bak").exists()


# Pins pre-existing doubt-verdict recording behavior; unrelated to the new cross-check.
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


# Pins pre-existing emoji-severity grouping behavior; unrelated to the new cross-check.
def test_close_group_uses_emoji_severity_not_english_word(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
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


# Pins pre-existing in-lock idempotency behavior; unrelated to the new cross-check.
def test_close_idempotency_check_is_inside_the_transaction(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
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


# Pins pre-existing per-batch idempotency behavior; unrelated to the new cross-check.
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


# Pins pre-existing parse-path routing behavior; unrelated to the new cross-check.
def test_close_state_mutations_use_parse_path(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
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


# Pins pre-existing scoped-validator usage behavior; unrelated to the new cross-check.
def test_close_uses_statectl_mutate_scoped_validator(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
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
        review,
        state_path,
        "decision-gate",
        [_finding(HIGH, "src/b.py", "x")],
    )

    assert calls == [state_path]
    assert result["applied"] is True
    assert _load(state_path)["phase"] == "not-a-phase"


# Pins pre-existing classification-mapping behavior; unrelated to the new cross-check.
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
            "cycle": 2,
            "issue": "defer me",
            "severity": MED,
            "file": "src/defer.py",
            "action": "deferred",
            "reason": "deferred by review-close",
        },
    ]
    every_text = json.dumps(data, ensure_ascii=False)
    assert "verify me" not in every_text
    assert "discard me" not in every_text


def test_carry_row_writes_no_decision_and_no_task(tmp_path: Path) -> None:
    """A `carry` row is a re-queued `[C{cycle}]` row's classification: it
    satisfies coverage but, like `verify`/`discard`, writes no decision and
    creates no rework task - a carry-forward row is already matched to its
    own re-queued task, so a second write here would be a duplicate. That
    re-queued task has to be in state for the batch to apply at all, so this
    one carries it."""
    review = _review(tmp_path)
    state_path = _carry_state(tmp_path, [_carry_task()], ["4"])
    findings = [
        _finding(HIGH, "src/fix.py", "fix me", "fix"),
        dict(_finding(MED, "src/carry.py", "carry me", "carry"), ref="R1"),
    ]

    result = review_close.close(review, state_path, "decision-gate", findings)

    data = _load(state_path)
    new_tasks = [t for t in data["tasks"] if t["id"] not in {"1", "4"}]
    assert [t["name"] for t in new_tasks] == ["[D2] src/fix.py"]
    assert result["tasks_created"] == [new_tasks[0]["id"]]
    assert data["deferred_decisions"] == []
    every_text = json.dumps(data, ensure_ascii=False)
    assert "carry me" not in every_text


# Pins pre-existing found-by-suffix omission behavior; unrelated to the new cross-check.
def test_close_omits_found_by_suffix_when_no_author(tmp_path: Path) -> None:
    review = _review(tmp_path)
    state_path = _state(tmp_path)
    finding = _finding(HIGH, "src/b.py", "wrong default")
    finding["found_by"] = []

    review_close.close(review, state_path, "decision-gate", [finding])

    desc = _load(state_path)["tasks"][1]["description"]
    assert "(found by:" not in desc
    assert "wrong default" in desc


# Pins pre-existing codex-guard threading behavior; unrelated to the new cross-check.
def test_close_threads_require_codex_guard_flag_to_the_gate(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    review = _review(tmp_path)
    state_path = _state(tmp_path)
    calls: list[bool | None] = []
    real_run_gate = gate.run_gate

    def _spy(review_file, reviewers=None, require_codex_guard=False):
        calls.append(require_codex_guard)
        return real_run_gate(
            review_file,
            reviewers=reviewers,
            require_codex_guard=require_codex_guard,
        )

    monkeypatch.setattr(review_close.gate, "run_gate", _spy)

    review_close.close(
        review,
        state_path,
        "decision-gate",
        [],
        require_codex_guard=True,
    )
    review_close.close(
        review,
        state_path,
        "tail-sweep",
        [],
        require_codex_guard=False,
    )

    assert calls == [True, False]


# Pins pre-existing tail-sweep skip behavior; unrelated to the new cross-check.
def test_close_tail_sweep_skips_lens_verdict_and_dispatch_row_steps(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    review = _review(tmp_path, extra_frontmatter="dispatch_rows:\n  bob: d-999\n")
    # A tail sweep only applies once this cycle's decision-gate batch has, and
    # never with an empty findings list, so this one carries a Medium row.
    state_path = _state(
        tmp_path,
        applied_review_batches=[f"{review.resolve()}::decision-gate"],
        review_lenses={"consensus": "running"},
        doubts_rubric_verdicts=[{"rule_id": "D9", "verdict": "pass"}],
    )
    commands: list[list[str]] = []
    monkeypatch.setattr(
        review_close.subprocess,
        "run",
        lambda cmd, **_kwargs: commands.append(cmd),
    )

    result = review_close.close(
        review,
        state_path,
        "tail-sweep",
        [_finding(MED, "src/c.py:20", "unclear name")],
    )

    assert result["applied"] is True
    data = _load(state_path)
    assert data["review_lenses"] == {"consensus": "running"}
    assert data["doubts_rubric_verdicts"] == [{"rule_id": "D9", "verdict": "pass"}]
    assert commands == []


# Pins pre-existing best-effort dispatch-row behavior; unrelated to the new cross-check.
def test_close_ends_frontmatter_dispatch_rows_best_effort(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
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
    # bob is available, so d-111 closes "ok"; carl has no agents: line at all,
    # so d-222 closes "lost" - the row was never reported back.
    assert [cmd[-1] for cmd in commands] == ["ok", "lost"]
    assert all(cmd[-2] == "--outcome" for cmd in commands)
    assert _load(state_path)["applied_review_batches"]


def test_every_dispatch_outcome_is_recordable() -> None:
    from skills.work.scripts import record_dispatch

    assert set(review_close._DISPATCH_OUTCOME.values()) <= set(record_dispatch.OUTCOMES)


def test_close_ends_unavailable_dispatch_with_error_outcome(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    review = _review(
        tmp_path,
        agents="  alice: available\n  bob: unavailable\n",
        extra_frontmatter="dispatch_rows:\n  bob: d-333\n",
    )
    state_path = _state(tmp_path)
    commands: list[list[str]] = []
    monkeypatch.setattr(
        review_close.subprocess,
        "run",
        lambda cmd, **_kwargs: commands.append(cmd),
    )

    result = review_close.close(review, state_path, "decision-gate", [])

    assert result["applied"] is True
    assert commands[0][-2:] == ["--outcome", "error"]


def test_malformed_dispatch_row_id_is_named_on_stderr(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A dash-led id is already refused (test_review_close_lowsev.py); this
    pins the other half of PRD #24 - the refusal names the persona and the
    id on stderr instead of dropping it silently."""
    review = _review(
        tmp_path,
        extra_frontmatter="dispatch_rows:\n  bob: -d-111\n  carl: d-222\n",
    )
    state_path = _state(tmp_path)
    commands: list[list[str]] = []
    monkeypatch.setattr(
        review_close.subprocess,
        "run",
        lambda cmd, **_kwargs: commands.append(cmd),
    )

    result = review_close.close(review, state_path, "decision-gate", [])

    assert result["applied"] is True
    assert [cmd[cmd.index("end") + 1] for cmd in commands] == ["d-222"]
    captured = capsys.readouterr()
    assert "-d-111" in captured.err
    assert "bob" in captured.err
