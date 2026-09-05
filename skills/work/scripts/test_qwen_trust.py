"""Single-file dispatch and pre-commit Qwen capability boundaries."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

_SPEC = importlib.util.spec_from_file_location(
    "work_routing", Path(__file__).with_name("work_routing.py")
)
assert _SPEC is not None and _SPEC.loader is not None
routing = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(routing)


@pytest.mark.parametrize("tier", ["haiku", "sonnet"])
@pytest.mark.parametrize("paths", ["src/a.py\nsrc/b.py", "a.py\nb.py\nc.py"])
@pytest.mark.parametrize("fence", [None, "off", "legacy", "unhealthy", "terminal"])
def test_stale_multifile_uses_existing_codex_fences(
    tier: str, paths: str, fence: str | None
) -> None:
    task = {"model": tier, "qwen_eligible": True}
    env = {}
    state = {"codex_probe": {"verdict": "healthy"}}
    if fence == "off":
        env["_WORK_CODEX_RUNG"] = "off"
    elif fence == "legacy":
        env["_AUTOPILOT_ESCALATION"] = "legacy"
    elif fence == "unhealthy":
        state["codex_probe"]["verdict"] = "unhealthy"
    elif fence == "terminal":
        task["attempts"] = [{"implementor": "codex"}]
    original = task.copy()
    verdict = routing.route(task, env, state, {}, file_paths=paths)
    assert verdict == {
        "implementor": "codex" if fence is None else "claude",
        "tier": tier,
        "rule": "codex_interception" if fence is None else "row7",
        "qwen_excluded_reason": "files",
    }
    assert task == original


@pytest.mark.parametrize("paths", ["", "\n \n", None])
@pytest.mark.parametrize("eligible", [True, False])
def test_empty_write_set_fails_closed_even_with_files_exclusion(
    paths: str | None, eligible: bool
) -> None:
    verdict = routing.route(
        {"model": "haiku", "qwen_eligible": eligible, "qwen_excluded_reason": "files"},
        {},
        {"codex_probe": {"verdict": "healthy"}},
        {},
        file_paths=paths,
    )
    assert verdict == {
        "implementor": "claude",
        "tier": "haiku",
        "rule": "empty_write_set",
        "qwen_excluded_reason": "files",
    }


@pytest.mark.parametrize("paths", ["src/a.py", "\nsrc/a.py\n\n", "src/a.py\nsrc/a.py"])
def test_exactly_one_distinct_nonempty_path_reaches_qwen(paths: str) -> None:
    assert routing.route(
        {"model": "sonnet", "qwen_eligible": True},
        {},
        {},
        {"memory_gate_exit": 0, "qwen_preflight": "healthy"},
        file_paths=paths,
    ) == {"implementor": "qwen", "tier": "sonnet", "rule": "row5"}


def test_named_test_only_task_never_dispatches_qwen() -> None:
    assert routing.route(
        {"model": "sonnet", "qwen_eligible": True, "is_test_only": True},
        {},
        {},
        {},
        file_paths="tests/test_a.py",
    ) == {"implementor": "claude", "tier": "sonnet", "rule": "test_only"}


@pytest.mark.parametrize(
    "root", ["/srv/project", "/srv/tests/project", "/srv/fixtures/project"]
)
def test_repository_ancestors_do_not_change_task_classification(root: str) -> None:
    verdict = routing.route(
        {"model": "sonnet", "qwen_eligible": True, "is_test_only": False},
        {},
        {},
        {"memory_gate_exit": 0, "qwen_preflight": "healthy"},
        file_paths=f"{root}/src/app.py",
    )
    assert verdict == {"implementor": "qwen", "tier": "sonnet", "rule": "row5"}


@pytest.mark.parametrize("reason", ["ui", "tier", "contract"])
@pytest.mark.parametrize("eligible", [False, True])
def test_multifile_does_not_replace_prior_exclusion(
    reason: str, eligible: bool
) -> None:
    verdict = routing.route(
        {"model": "sonnet", "qwen_eligible": eligible, "qwen_excluded_reason": reason},
        {},
        {"codex_probe": {"verdict": "healthy"}},
        {"gemini_available": True},
        file_paths="a.py\nb.py",
    )
    assert verdict["implementor"] == ("gemini" if reason == "ui" else "claude")
    assert "qwen_excluded_reason" not in verdict


@pytest.mark.parametrize(
    "edited,mutated,cause",
    [
        (False, False, "qwen_no_edit"),
        (True, True, "qwen_test_mutation"),
        (False, True, "qwen_test_mutation"),
    ],
)
def test_qwen_output_failure_consumes_one_shot_and_selects_sonnet(
    edited: bool, mutated: bool, cause: str
) -> None:
    assert routing.qwen_attempt_outcome(edited, mutated) == {
        "arm": "capability",
        "next": "sonnet",
        "cause": cause,
        "outcome": "escalated",
        "qwen_gate_failed": True,
        "escalation_reason": "gate_failure",
        "escalated_from": "qwen",
    }


def test_clean_qwen_implementation_proceeds_to_commit_and_gate() -> None:
    assert routing.qwen_attempt_outcome(True, False) == {
        "arm": "pass",
        "next": "proceed",
        "cause": None,
    }
