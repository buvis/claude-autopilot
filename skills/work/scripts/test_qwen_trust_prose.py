"""Pin the model-followed call sites and attempt contract for Qwen guards."""

from pathlib import Path

import pytest

_WORK = Path(__file__).resolve().parents[1]
_LADDER = _WORK.parent / "run-autopilot/references/model-ladder.md"
_SCHEMA = _LADDER.with_name("state-schema.md")


def test_runtime_fence_precedes_the_routing_table() -> None:
    text = (_WORK / "SKILL.md").read_text()
    fence = text.split("**Runtime write-set reconciliation", 1)[1].split(
        "Apply the rows", 1
    )[0]
    assert "`FILE_PATHS`" in fence
    assert "zero paths fail closed to Claude" in fence
    assert "two or more paths replace eligibility with false" in fence
    assert "all six Codex interception fences" in fence
    assert "Do not rewrite planner metadata" in fence
    assert "test-only write set keeps the non-Qwen Claude path" in fence


def test_guard_is_required_before_dispatch_and_before_staging() -> None:
    text = (_WORK / "SKILL.md").read_text()
    dispatch = text.split("### 3. Implement", 1)[1].split("### 4. Handle result", 1)[0]
    result = text.split("### 4. Handle result", 1)[1].split("### 4.2.", 1)[0]
    assert "run its `check_qwen_output.py before` command" in dispatch
    assert "must first run `check_qwen_output.py after`" in result
    assert "before staging, committing, or running step 5.5" in result
    assert "Only exit 0 continues to step 5" in result
    assert "exit 2 stops acceptance" in result
    assert "non-success Qwen result (including timeout/lost result)" in result
    assert "verify it is gone" in result
    assert "`--tests-only` before any fallback" in result


def test_watchdog_does_not_run_mutated_tests_before_result_handling() -> None:
    text = (_WORK / "references/subagent-dispatch.md").read_text()
    kill = text.split("4. **After ANY kill", 1)[1].split("**Right-size", 1)[0]
    assert "check_qwen_output.py after" in kill
    assert "--tests-only" in kill
    assert kill.index("--tests-only") < kill.index("Work looks complete")


def test_dispatch_self_check_accepts_the_effective_fences() -> None:
    text = (_WORK / "SKILL.md").read_text()
    check = text.split("Self-check before each initial Ivan dispatch:", 1)[1].split(
        "\n\n", 1
    )[0]
    assert "effective routing decision" in check
    assert "write-set or test-only fence" in check
    assert "recorded output-guard preparation failure" in check
    assert "Capability escalations dispatch directly" in check


def test_state_schema_attempt_shape_admits_runtime_files_exclusion() -> None:
    row = _SCHEMA.read_text().split("| `tasks[].attempts`", 1)[1].split("\n", 1)[0]
    assert (
        '"qwen_excluded_reason"?: "files"\\|"memory_pressure"\\|"memory_probe_failed"'
        in row
    )
    assert "effective eligibility after runtime write-set reconciliation" in row
    assert "whose pre-commit output guard or step-5.5 gate FAILED" in row


def test_attempt_payload_example_admits_runtime_files_exclusion() -> None:
    text = (_WORK / "references/attempt-logging.md").read_text()
    example = text.split("```json", 1)[1].split("```", 1)[0]
    assert (
        '"qwen_excluded_reason": "files" | "memory_pressure" | "memory_probe_failed" | null'
        in example
    )


@pytest.mark.parametrize(
    "path,start,end",
    [
        (_WORK / "references/attempt-logging.md", "- `cause`:", "\n- `implementor`:"),
        (
            _WORK / "references/gate-failure.md",
            "## Qwen output rejection",
            "## Retry render",
        ),
        (
            _SCHEMA,
            "| `tasks[].attempts[].cause`",
            "\n| `tasks[].attempts[].qwen_excluded_reason`",
        ),
        (_LADDER, "## Capability ladders", "## Fable rescue"),
    ],
)
def test_authorities_name_each_output_cause_once(
    path: Path, start: str, end: str
) -> None:
    section = path.read_text().split(start, 1)[1].split(end, 1)[0]
    assert section.count("qwen_no_edit") == 1
    assert section.count("qwen_test_mutation") == 1


def test_mutation_recovery_retains_safe_reset_and_sonnet_edge() -> None:
    text = (_WORK / "references/gate-failure.md").read_text()
    section = text.split("## Qwen output rejection", 1)[1].split("## Retry render", 1)[
        0
    ]
    assert "`qwen -> sonnet`" in section
    assert "--restore-tests" in section
    assert "HEAD movement or\nambiguous ownership prohibits this restoration" in section
    assert "Never dispatch\nSonnet against mutated tests" in section
    assert "Skip the routing table" in section


def test_qwen_guidance_names_qualified_scope_and_pending_multifile_evidence() -> None:
    text = (_WORK / "references/qwen-integration.md").read_text()
    assert "Qwen3.8" in text
    assert "single-file-only" in text
    assert "2026-09-03" in text
    assert "pending review and a clean rerun" in text
    assert "## Preflight" in text
    assert "## One-shot attempt budget" in text
    assert "Qwen3.6" not in text
