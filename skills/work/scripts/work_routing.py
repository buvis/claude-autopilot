"""Implementor routing for /work step 3 — the deterministic table plus the codex rung.

Pure decision core: three functions over plain dicts, no I/O, no env reads of its
own, no side effects. It pins the step-3 routing table (the `fable` override,
rows 1-7, first match wins), the codex interception, and codex attempt outcomes
so the SKILL.md prose cannot drift from the rules silently.
"""

from __future__ import annotations

from fnmatch import fnmatchcase

# The rows whose verdict is "Claude at the task's (original) tier" — the only
# rows the codex rung may intercept.
_INTERCEPTION_ROWS = frozenset({"row3", "row4", "row6", "row7"})

_CODEX_ATTEMPT_OUTCOMES = {
    "timeout": {
        "arm": "infra",
        "next": "claude_at_tier",
        "cause": "timeout",
        "codex_outcome": "aborted",
        "escalation_reason": None,
        "escalated_from": None,
    },
    "no_output": {
        "arm": "infra",
        "next": "claude_at_tier",
        "cause": "subagent_infra_failure",
        "codex_outcome": "aborted",
        "escalation_reason": None,
        "escalated_from": None,
    },
    "no_edit": {
        "arm": "infra",
        "next": "claude_at_tier",
        "cause": "codex_no_edit",
        "codex_outcome": "aborted",
        "escalation_reason": None,
        "escalated_from": None,
    },
    "pass": {
        "arm": "pass",
        "next": "proceed",
        "cause": None,
        "codex_outcome": "completed",
        "escalation_reason": None,
        "escalated_from": None,
    },
    "retry": {
        "arm": "capability",
        "next": "feedback_retry_codex",
        "cause": None,
        "codex_outcome": None,
        "escalation_reason": None,
        "escalated_from": None,
    },
    "escalate": {
        "arm": "capability",
        "next": "escalate_claude_at_tier",
        "cause": None,
        "codex_outcome": "escalated",
        "escalation_reason": "gate_failure",
        "escalated_from": "codex",
    },
}


# Test-path recognition: a closed list, matched exactly and case-sensitively.
# Anything unmatched is production, so a misjudged path costs the full pipeline
# rather than a skipped review.
_TEST_DIR_SEGMENTS = frozenset(
    {
        "test",
        "tests",
        "__tests__",
        "spec",
        "specs",
        "fixtures",
        "__fixtures__",
        "__snapshots__",
        "testdata",
    },
)

_JS_TEST_EXTENSIONS = ("js", "jsx", "ts", "tsx", "mjs", "cjs")

_TEST_BASENAME_GLOBS = (
    "conftest.py",
    "test_*.py",
    "*_test.py",
    "*_test.go",
    "*_spec.rb",
    "*Test.java",
    "*Tests.java",
    "test_*.sh",
    "*_test.sh",
    *(f"*.test.{ext}" for ext in _JS_TEST_EXTENSIONS),
    *(f"*.spec.{ext}" for ext in _JS_TEST_EXTENSIONS),
)


def _tier(task: dict) -> str:
    """The task's model tier. A legacy plan (no `model`, or `model: None`) is sonnet."""
    return task.get("model") or "sonnet"


def route(task: dict, env: dict, state: dict, probes: dict) -> dict:
    """Pick the implementor for one claimed task."""
    tier = _tier(task)
    if tier == "fable":
        return {"implementor": "claude", "tier": tier, "rule": "fable_override"}

    rule = _table_row(task, env, state, probes)
    if rule in _INTERCEPTION_ROWS and _intercepted_by_codex(task, env, state):
        return {"implementor": "codex", "tier": tier, "rule": "codex_interception"}

    if rule == "row1":
        implementor = "gemini" if probes["gemini_available"] else "claude"
    elif rule == "row5":
        implementor = "qwen"
    else:
        implementor = "claude"
    return {"implementor": implementor, "tier": tier, "rule": rule}


def micro_lane_eligible(
    severities: list[str],
    files: list[str],
    in_rework: bool,
) -> bool:
    """True when a rework task is small enough for the orchestrator to edit.

    `files` entries may carry a `:line` suffix as the verbatim findings block
    writes them; only the path before it counts. Empty `severities` means the
    block did not parse — nothing to bound, so not eligible. The 2/2 bound is a
    proxy for the expected diff size; the post-edit overrun ceiling in
    `references/rework-mode.md` is the real guard.
    """
    return (
        in_rework
        and bool(severities)
        and len(severities) <= 2
        and len({path.split(":", 1)[0] for path in files}) <= 2
        and not any(s.strip().upper() == "CRITICAL" for s in severities)
    )


def needs_probe(state: dict, batch_id: str) -> bool:
    """True when no codex probe verdict is cached for exactly this batch."""
    return state.get("codex_probe", {}).get("batch_id") != batch_id


def needs_qwen_probe(state: dict, batch_id: str) -> bool:
    """True when no qwen preflight verdict is cached for exactly this batch."""
    return state.get("qwen_preflight", {}).get("batch_id") != batch_id


def red_check_disposition(
    contract_paths: list[str],
    imported_paths: list[str],
    existing_paths: list[str],
) -> str:
    """Skip the red check only when an imported Contract-named path is missing."""
    candidates = [path for path in contract_paths if path in imported_paths]
    if any(path not in existing_paths for path in candidates):
        return "n/a:new_module"
    return "run"


def codex_attempt_outcome(signals: dict) -> dict:
    """Classify a codex implementor attempt and name its next action."""
    if signals["watchdog_timeout"]:
        outcome = "timeout"
    elif not signals["output_nonempty"]:
        outcome = "no_output"
    elif signals["no_edit"] is True:
        outcome = "no_edit"
    elif signals["gate_failures_at_codex"] == 0:
        outcome = "pass"
    elif signals["gate_failures_at_codex"] == 1:
        outcome = "retry"
    else:
        outcome = "escalate"
    return _CODEX_ATTEMPT_OUTCOMES[outcome].copy()


def is_test_path(path: str) -> bool:
    """True when a repo-relative path is test or fixture code.

    Directory segments and basenames match exactly and case-sensitively, so
    `testing/x.py` and `contest/x.py` are production, and a Rust file carrying
    an inline `#[cfg(test)]` module is production too — the path is all this
    predicate sees.
    """
    segments = path.split("/")
    if any(segment in _TEST_DIR_SEGMENTS for segment in segments[:-1]):
        return True
    return any(fnmatchcase(segments[-1], glob) for glob in _TEST_BASENAME_GLOBS)


def test_only_diff(paths: list[str]) -> bool:
    """True when every changed path is test code. An empty diff is never test-only."""
    return bool(paths) and all(is_test_path(path) for path in paths)


def test_only_gate(paths: list[str], in_rework: bool) -> dict[str, str]:
    """The skip stamps a test-only task's attempt record carries.

    A rework task keeps its reviewer: the CLOSURE verdicts are what stop a
    second review cycle, the same reason the micro lane keeps him.
    """
    if not test_only_diff(paths):
        return {}
    stamps = {"self_deslop": "skipped:test-only"}
    if not in_rework:
        stamps["review"] = "skipped:test-only"
    return stamps


def _table_row(task: dict, env: dict, state: dict, probes: dict) -> str:
    if _is_ui(task):
        return "row1"
    if _tier(task) == "opus":
        return "row2"
    if not task.get("qwen_eligible", False):
        return "row7"
    if env.get("_AUTOPILOT_ESCALATION") != "legacy" and state.get(
        "qwen_breaker",
        {},
    ).get("tripped"):
        return "row3"
    if probes["memory_gate_exit"] != 0:
        return "row4"
    if probes.get("qwen_preflight") == "healthy":
        return "row5"
    return "row6"


def _is_ui(task: dict) -> bool:
    if "is_ui" in task:
        return bool(task["is_ui"])
    return task.get("qwen_excluded_reason") == "ui"


def _codex_eligible(task: dict) -> bool:
    return bool(task.get("qwen_eligible", False)) or (
        task.get("qwen_excluded_reason") == "files"
    )


def _terminal_attempt_was_codex(task: dict) -> bool:
    attempts = task.get("attempts", [])
    return bool(attempts) and attempts[-1].get("implementor") == "codex"


def _intercepted_by_codex(task: dict, env: dict, state: dict) -> bool:
    return (
        _codex_eligible(task)
        and env.get("_WORK_CODEX_RUNG") != "off"
        and env.get("_AUTOPILOT_ESCALATION") != "legacy"
        and state.get("codex_probe", {}).get("verdict") == "healthy"
        and not _terminal_attempt_was_codex(task)
    )
