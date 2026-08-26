"""Tests for check_build_overhead.py — transcript clerical-overhead metrics report."""

from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path

import pytest

_MODULE_PATH = Path(__file__).with_name("check_build_overhead.py")
_SPEC = importlib.util.spec_from_file_location("check_build_overhead", _MODULE_PATH)
assert _SPEC is not None and _SPEC.loader is not None
check_build_overhead = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(check_build_overhead)


_ENGRAM_REPO = Path.home() / "git" / "src" / "github.com" / "buvis" / "engram"
GOLDEN_TRANSCRIPT = (
    Path.home()
    / ".claude"
    / "projects"
    / str(_ENGRAM_REPO).replace("/", "-").replace(".", "-")
    / "4bddd2d6-0c28-4a2d-aa41-bbf06873027d.jsonl"
)


# --- fixture helpers ---------------------------------------------------


def _tool_use(name: str, input_: dict[str, object]) -> dict[str, object]:
    return {"type": "tool_use", "name": name, "input": input_}


def _statectl(*args: str) -> dict[str, object]:
    command = "python3 /p/statectl.py dev/local/autopilot/state.json " + " ".join(args)
    return _tool_use("Bash", {"command": command})


def _assistant_turn(*blocks: dict[str, object]) -> dict[str, object]:
    return {"type": "assistant", "message": {"content": list(blocks)}}


def _write_transcript(tmp_path: Path, lines: list[object]) -> Path:
    transcript = tmp_path / "transcript.jsonl"
    with transcript.open("w") as f:
        for line in lines:
            f.write(line if isinstance(line, str) else json.dumps(line))
            f.write("\n")
    return transcript


# --- TaskCreate turn dedupe ---------------------------------------------------


def test_taskcreate_turns_dedupe_multiple_calls_in_one_turn(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    # A batched hydration turn issuing several TaskCreate calls in one message
    # must count as ONE TaskCreate turn, not one per call.
    lines = [
        _assistant_turn(
            _tool_use("TaskCreate", {"title": "a"}),
            _tool_use("TaskCreate", {"title": "b"}),
            _tool_use("TaskCreate", {"title": "c"}),
        ),
    ]
    transcript = _write_transcript(tmp_path, lines)

    exit_code = check_build_overhead.main([str(transcript)])

    assert exit_code == 0
    captured = capsys.readouterr()
    assert "TaskCreate turns: 1" in captured.out.splitlines()


def test_taskcreate_turns_counted_once_per_turn_across_separate_turns(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    lines = [
        _assistant_turn(_tool_use("TaskCreate", {"title": "a"})),
        _assistant_turn(_tool_use("TaskCreate", {"title": "b"})),
        _assistant_turn(_tool_use("TaskCreate", {"title": "c"})),
    ]
    transcript = _write_transcript(tmp_path, lines)

    exit_code = check_build_overhead.main([str(transcript)])

    assert exit_code == 0
    captured = capsys.readouterr()
    assert "TaskCreate turns: 3" in captured.out.splitlines()


def test_taskcreate_turns_zero_when_none_present(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    lines = [
        _assistant_turn(
            {"type": "text", "text": "hello"},
            _tool_use("Bash", {"command": "echo hi"}),
        ),
    ]
    transcript = _write_transcript(tmp_path, lines)

    exit_code = check_build_overhead.main([str(transcript)])

    assert exit_code == 0
    captured = capsys.readouterr()
    assert "TaskCreate turns: 0" in captured.out.splitlines()


# --- statectl Bash call counting ---------------------------------------------------


def test_statectl_bash_calls_counted_per_call_not_per_turn(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    # Unlike TaskCreate, the statectl counter has no stated dedupe rule: two
    # calls batched into one turn must both count.
    lines = [
        _assistant_turn(
            _tool_use("Bash", {"command": "python3 work/scripts/statectl.py update"}),
            _tool_use("Bash", {"command": "python3 work/scripts/statectl.py complete"}),
        ),
    ]
    transcript = _write_transcript(tmp_path, lines)

    exit_code = check_build_overhead.main([str(transcript)])

    assert exit_code == 0
    captured = capsys.readouterr()
    assert "statectl calls: 2" in captured.out.splitlines()


@pytest.mark.parametrize(
    "command",
    [
        "python work/scripts/statectl.py update",  # not "python3"
        "python3 work/scripts/other_tool.py",  # no "statectl.py"
        "echo python3 statectl.py",  # does not start with "python3"
    ],
)
def test_bash_calls_not_matching_statectl_pattern_are_excluded(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    command: str,
) -> None:
    lines = [_assistant_turn(_tool_use("Bash", {"command": command}))]
    transcript = _write_transcript(tmp_path, lines)

    exit_code = check_build_overhead.main([str(transcript)])

    assert exit_code == 0
    captured = capsys.readouterr()
    assert "statectl calls: 0" in captured.out.splitlines()


# --- prompt-authoring Write call counting ---------------------------------------------------


def test_prompt_authoring_write_calls_matched_for_both_glob_patterns(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    lines = [
        _assistant_turn(
            _tool_use(
                "Write",
                {
                    "file_path": "/Users/dev/.claude/dev/local/tmp/task-prompt-3.txt",
                    "content": "x",
                },
            ),
            _tool_use(
                "Write",
                {
                    "file_path": "/Users/dev/.claude/dev/local/tmp/dispatch-tess-7.txt",
                    "content": "y",
                },
            ),
        ),
    ]
    transcript = _write_transcript(tmp_path, lines)

    exit_code = check_build_overhead.main([str(transcript)])

    assert exit_code == 0
    captured = capsys.readouterr()
    assert "prompt-authoring Write calls: 2" in captured.out.splitlines()


@pytest.mark.parametrize(
    "file_path",
    [
        "/Users/dev/.claude/dev/local/tmp/notes.txt",  # no "prompt", no "dispatch-" prefix
        "/Users/dev/.claude/dev/local/other/prompt-file.txt",  # "prompt" but wrong dir
        "/Users/dev/.claude/work/scripts/check_build_overhead.py",  # unrelated path
    ],
)
def test_write_calls_outside_prompt_glob_patterns_are_not_counted(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    file_path: str,
) -> None:
    lines = [
        _assistant_turn(_tool_use("Write", {"file_path": file_path, "content": "x"})),
    ]
    transcript = _write_transcript(tmp_path, lines)

    exit_code = check_build_overhead.main([str(transcript)])

    assert exit_code == 0
    captured = capsys.readouterr()
    assert "prompt-authoring Write calls: 0" in captured.out.splitlines()


# --- completed-task counting (statectl completion verbs) ---------------------


def test_completed_tasks_counts_only_statectl_completion_verbs(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    lines = [
        _assistant_turn(
            _statectl("task-done", "task-1", "dev/local/tmp/attempt-task-1.json"),
        ),
        _assistant_turn(_statectl("task-start", "task-2")),
        _assistant_turn(
            _statectl("task-done", "task-3", "dev/local/tmp/attempt-task-3.json"),
        ),
    ]
    transcript = _write_transcript(tmp_path, lines)

    exit_code = check_build_overhead.main([str(transcript)])

    assert exit_code == 0
    captured = capsys.readouterr()
    assert "completed tasks: 2" in captured.out.splitlines()


def test_task_set_status_counts_only_when_the_status_is_completed(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    lines = [
        _assistant_turn(_statectl("task-set-status", "task-9", "completed")),
        _assistant_turn(_statectl("task-set-status", "task-10", "pending")),
    ]
    transcript = _write_transcript(tmp_path, lines)

    exit_code = check_build_overhead.main([str(transcript)])

    assert exit_code == 0
    captured = capsys.readouterr()
    assert "completed tasks: 1" in captured.out.splitlines()


def test_completed_tasks_counts_each_call_even_when_batched_in_one_turn(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    lines = [
        _assistant_turn(
            _statectl("task-done", "task-1"),
            _statectl("task-done", "task-2"),
        ),
    ]
    transcript = _write_transcript(tmp_path, lines)

    exit_code = check_build_overhead.main([str(transcript)])

    assert exit_code == 0
    captured = capsys.readouterr()
    assert "completed tasks: 2" in captured.out.splitlines()


def test_count_completed_tasks_survives_unbalanced_quotes_and_a_missing_id() -> None:
    # shlex.split raises on an unbalanced quote; the count must still be made
    # from the whitespace split rather than losing the whole session. A verb
    # with no id after it counts nothing instead of raising.
    commands = [
        'python3 /p/statectl.py state.json task-done task-1 "unclosed',
        "python3 /p/statectl.py state.json task-done",
        "python3 /p/statectl.py state.json task-set-status task-2",
    ]

    assert check_build_overhead.count_completed_tasks(commands) == 1


# --- Agent dispatch counting -------------------------------------------------


def test_agent_dispatches_are_counted(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    lines = [
        _assistant_turn(
            _tool_use("Agent", {"subagent_type": "autopilot:ivan"}),
            _tool_use("Task", {"subagent_type": "autopilot:pat"}),
        ),
        _assistant_turn(_tool_use("Agent", {"subagent_type": "autopilot:tess"})),
        _assistant_turn(_tool_use("Bash", {"command": "echo hi"})),
    ]
    transcript = _write_transcript(tmp_path, lines)

    exit_code = check_build_overhead.main([str(transcript)])

    assert exit_code == 0
    captured = capsys.readouterr()
    assert "Agent dispatches: 3" in captured.out.splitlines()


# --- statectl-calls-per-completed-task ratio ---------------------------------------------------


def test_statectl_ratio_rounds_to_two_decimal_places(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    lines = [
        _assistant_turn(*[_statectl("task-start", "task-1") for _ in range(7)]),
        _assistant_turn(_statectl("task-done", "task-1")),
        _assistant_turn(_statectl("task-done", "task-2")),
        _assistant_turn(_statectl("task-done", "task-3")),
    ]
    # 10 statectl calls / 3 completed tasks = 3.333... -> 3.33
    transcript = _write_transcript(tmp_path, lines)

    exit_code = check_build_overhead.main([str(transcript)])

    assert exit_code == 0
    captured = capsys.readouterr()
    assert "statectl calls per completed task: 3.33" in captured.out.splitlines()


def test_zero_completed_tasks_prints_the_explicit_line_and_no_ratio(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    # A ratio over zero completed tasks used to print "0.00", which reads as a
    # perfect score. Zero completions must say so and print no ratio at all.
    lines = [
        _assistant_turn(_statectl("task-start", "task-1")),
        _assistant_turn(_statectl("task-set-status", "task-1", "pending")),
    ]
    transcript = _write_transcript(tmp_path, lines)

    exit_code = check_build_overhead.main([str(transcript)])

    assert exit_code == 0
    captured = capsys.readouterr()
    out_lines = captured.out.splitlines()
    assert "completed tasks: 0 (no statectl task-done calls found)" in out_lines
    assert not [
        line
        for line in out_lines
        if line.startswith("statectl calls per completed task:")
    ]


def test_ratio_counts_distinct_task_done_ids(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    # 9 statectl calls, four of them task-done but only three distinct ids:
    # 9 / 3 = 3.00. The completion verbs are statectl calls themselves.
    lines = [
        _assistant_turn(*[_statectl("task-start", "task-1") for _ in range(5)]),
        _assistant_turn(_statectl("task-done", "task-1")),
        _assistant_turn(_statectl("task-done", "task-2")),
        _assistant_turn(_statectl("task-done", "task-3")),
        _assistant_turn(_statectl("task-done", "task-1")),
    ]
    transcript = _write_transcript(tmp_path, lines)

    exit_code = check_build_overhead.main([str(transcript)])

    assert exit_code == 0
    captured = capsys.readouterr()
    out_lines = captured.out.splitlines()
    assert "statectl calls: 9" in out_lines
    assert "completed tasks: 3" in out_lines
    assert "statectl calls per completed task: 3.00" in out_lines


def test_statectl_ratio_formatted_with_two_decimals_for_whole_number(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    lines = [
        _assistant_turn(*[_statectl("task-start", "task-1") for _ in range(2)]),
        _assistant_turn(_statectl("task-done", "task-1")),
        _assistant_turn(_statectl("task-done", "task-2")),
    ]
    # 4 statectl calls / 2 completed tasks = 2.0 -> "2.00", not "2" or "2.0"
    transcript = _write_transcript(tmp_path, lines)

    exit_code = check_build_overhead.main([str(transcript)])

    assert exit_code == 0
    captured = capsys.readouterr()
    assert "statectl calls per completed task: 2.00" in captured.out.splitlines()


# --- full stdout report shape ---------------------------------------------------


def test_stdout_report_has_exact_line_format_in_order(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    lines = [
        _assistant_turn(_tool_use("TaskCreate", {"title": "a"})),
        _assistant_turn(
            _tool_use("Bash", {"command": "python3 work/scripts/statectl.py update"}),
        ),
        _assistant_turn(
            _tool_use(
                "Write",
                {
                    "file_path": "/Users/dev/.claude/dev/local/tmp/dispatch-x.txt",
                    "content": "y",
                },
            ),
        ),
        _assistant_turn(_tool_use("Agent", {"subagent_type": "autopilot:ivan"})),
        _assistant_turn(_statectl("task-done", "task-1")),
    ]
    transcript = _write_transcript(tmp_path, lines)

    exit_code = check_build_overhead.main([str(transcript)])

    assert exit_code == 0
    captured = capsys.readouterr()
    assert captured.out == (
        "TaskCreate turns: 1\n"
        "statectl calls: 2\n"
        "statectl calls per completed task: 2.00\n"
        "prompt-authoring Write calls: 1\n"
        "completed tasks: 1\n"
        "Agent dispatches: 1\n"
    )


# --- non-assistant lines and malformed JSON ---------------------------------------------------


def test_non_assistant_type_lines_are_ignored(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    lines = [
        {
            "type": "user",
            "message": {"content": [{"type": "tool_result", "content": "ok"}]},
        },
        {"type": "summary", "summary": "session recap"},
        _assistant_turn(_tool_use("TaskCreate", {"title": "a"})),
    ]
    transcript = _write_transcript(tmp_path, lines)

    exit_code = check_build_overhead.main([str(transcript)])

    assert exit_code == 0
    captured = capsys.readouterr()
    assert "TaskCreate turns: 1" in captured.out.splitlines()


def test_malformed_json_lines_are_skipped_when_some_valid_lines_exist(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    lines: list[object] = [
        "not valid json at all",
        _assistant_turn(_tool_use("TaskCreate", {"title": "a"})),
        "{broken",
    ]
    transcript = _write_transcript(tmp_path, lines)

    exit_code = check_build_overhead.main([str(transcript)])

    assert exit_code == 0
    captured = capsys.readouterr()
    assert "TaskCreate turns: 1" in captured.out.splitlines()


def test_malformed_json_lines_emit_stderr_warning_naming_skipped_count(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    lines: list[object] = [
        "not valid json at all",
        _assistant_turn(_tool_use("TaskCreate", {"title": "a"})),
        "{broken",
    ]
    transcript = _write_transcript(tmp_path, lines)

    exit_code = check_build_overhead.main([str(transcript)])

    assert exit_code == 0
    captured = capsys.readouterr()
    assert captured.out.splitlines() == [
        "TaskCreate turns: 1",
        "statectl calls: 0",
        "prompt-authoring Write calls: 0",
        "completed tasks: 0 (no statectl task-done calls found)",
        "Agent dispatches: 0",
    ]
    assert (
        captured.err.strip()
        == f"warning: skipped 2 unparseable line(s) in {transcript}"
    )


# --- exit codes ---------------------------------------------------


def test_exit_code_two_when_no_line_is_parseable_json(tmp_path: Path) -> None:
    lines: list[object] = ["not json", "{also broken", "still not json"]
    transcript = _write_transcript(tmp_path, lines)

    exit_code = check_build_overhead.main([str(transcript)])

    assert exit_code == 2


def test_exit_code_two_when_transcript_file_is_empty(tmp_path: Path) -> None:
    transcript = tmp_path / "empty.jsonl"
    transcript.write_text("")

    exit_code = check_build_overhead.main([str(transcript)])

    assert exit_code == 2


def test_exit_code_one_when_transcript_file_does_not_exist(tmp_path: Path) -> None:
    missing = tmp_path / "does_not_exist.jsonl"

    exit_code = check_build_overhead.main([str(missing)])

    assert exit_code == 1


@pytest.mark.skipif(os.name != "posix", reason="permission bits are POSIX-only")
def test_exit_code_one_when_transcript_file_is_not_readable(tmp_path: Path) -> None:
    if hasattr(os, "geteuid") and os.geteuid() == 0:
        pytest.skip("root bypasses POSIX permission bits")
    lines = [_assistant_turn(_tool_use("TaskCreate", {"title": "a"}))]
    transcript = _write_transcript(tmp_path, lines)
    transcript.chmod(0o000)
    try:
        exit_code = check_build_overhead.main([str(transcript)])
    finally:
        transcript.chmod(0o644)

    assert exit_code == 1


def test_exit_code_zero_on_normal_run_regardless_of_zero_counts(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    # Exit 0 is a report-printed signal, not a pass/fail gate: a transcript
    # with valid JSON lines but no matching tool calls at all must still
    # exit 0, distinct from the exit-2 "zero parseable lines" case.
    lines = [_assistant_turn({"type": "text", "text": "hello"})]
    transcript = _write_transcript(tmp_path, lines)

    exit_code = check_build_overhead.main([str(transcript)])

    assert exit_code == 0
    captured = capsys.readouterr()
    assert "TaskCreate turns: 0" in captured.out.splitlines()
    assert (
        "completed tasks: 0 (no statectl task-done calls found)"
        in captured.out.splitlines()
    )


# --- golden baseline acceptance test ---------------------------------------------------


@pytest.mark.skipif(
    not GOLDEN_TRANSCRIPT.exists(),
    reason="golden baseline transcript fixture not present on this machine",
)
def test_golden_baseline_engram_session_matches_recorded_numbers(
    capsys: pytest.CaptureFixture[str],
) -> None:
    exit_code = check_build_overhead.main([str(GOLDEN_TRANSCRIPT)])

    assert exit_code == 0
    captured = capsys.readouterr()
    out_lines = captured.out.splitlines()
    assert "TaskCreate turns: 10" in out_lines

    # This transcript predates the statectl task verbs: its completions were
    # recorded with the retired TaskUpdate tool, so the honest count is zero
    # and no ratio may be printed. The old assertion here (2.80) came from
    # counting TaskUpdate calls, which PRD 00120 retired.
    assert "completed tasks: 0 (no statectl task-done calls found)" in out_lines
    assert not [
        line
        for line in out_lines
        if line.startswith("statectl calls per completed task:")
    ]


# --- completed-task counting dedupes by distinct task id ------------------


def test_completed_tasks_deduplicates_repeated_completion_of_same_task_id(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    # A rework cycle re-opens and re-completes the same task id; the report
    # must count it once, and the derived ratio must use that deduped count.
    lines = [
        _assistant_turn(_statectl("task-start", "task-1")),
        _assistant_turn(_statectl("task-start", "task-1")),
        _assistant_turn(_statectl("task-done", "task-1")),
        _assistant_turn(_statectl("task-done", "task-1")),
    ]
    transcript = _write_transcript(tmp_path, lines)

    exit_code = check_build_overhead.main([str(transcript)])

    assert exit_code == 0
    captured = capsys.readouterr()
    out_lines = captured.out.splitlines()
    assert "completed tasks: 1" in out_lines
    assert "statectl calls per completed task: 4.00" in out_lines


def test_completed_tasks_does_not_collapse_distinct_task_ids_when_one_repeats(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    # task-1 is completed twice (a rework re-completion) and task-2 once; the
    # dedupe must land on 2 distinct ids, not collapse everything down to 1.
    lines = [
        _assistant_turn(_statectl("task-done", "task-1")),
        _assistant_turn(_statectl("task-done", "task-2")),
        _assistant_turn(_statectl("task-done", "task-1")),
    ]
    transcript = _write_transcript(tmp_path, lines)

    exit_code = check_build_overhead.main([str(transcript)])

    assert exit_code == 0
    captured = capsys.readouterr()
    assert "completed tasks: 2" in captured.out.splitlines()


# --- transcript path is a directory ------------------


def test_directory_passed_as_transcript_exits_one_with_one_line_stderr_message(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    directory = tmp_path / "not_a_file"
    directory.mkdir()

    exit_code = check_build_overhead.main([str(directory)])

    assert exit_code == 1
    captured = capsys.readouterr()
    stderr_lines = captured.err.strip("\n").splitlines()
    assert len(stderr_lines) == 1
    assert stderr_lines[0] != ""


# --- malformed message.content shapes are skipped, not raised ------------------


def test_string_valued_message_content_is_skipped_without_raising(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    lines: list[object] = [
        _assistant_turn(_tool_use("TaskCreate", {"title": "a"})),
        {
            "type": "assistant",
            "message": {"content": "plain string content, not a list"},
        },
        _assistant_turn(_tool_use("TaskCreate", {"title": "b"})),
    ]
    transcript = _write_transcript(tmp_path, lines)

    exit_code = check_build_overhead.main([str(transcript)])

    assert exit_code == 0
    captured = capsys.readouterr()
    assert "TaskCreate turns: 2" in captured.out.splitlines()


def test_content_list_with_non_object_entry_is_skipped_without_raising(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    lines: list[object] = [
        _assistant_turn(_tool_use("TaskCreate", {"title": "a"})),
        {"type": "assistant", "message": {"content": ["not a dict", 42, None]}},
        _assistant_turn(_tool_use("TaskCreate", {"title": "b"})),
    ]
    transcript = _write_transcript(tmp_path, lines)

    exit_code = check_build_overhead.main([str(transcript)])

    assert exit_code == 0
    captured = capsys.readouterr()
    assert "TaskCreate turns: 2" in captured.out.splitlines()


# --- portable synthetic golden-baseline (replaces machine-local dependency) ---


def test_synthetic_fixture_report_matches_expected_metrics_without_machine_local_transcript(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    # Committed, self-contained replacement for the machine-local golden
    # baseline: this fixture is written by the test itself, so the full
    # five-line report is exercised on every machine, not just the one that
    # happens to have the real transcript on disk.
    lines = [
        _assistant_turn(_tool_use("TaskCreate", {"title": "a"})),
        _assistant_turn(_tool_use("TaskCreate", {"title": "b"})),
        _assistant_turn(
            _tool_use("Bash", {"command": "python3 work/scripts/statectl.py update"}),
            _tool_use("Bash", {"command": "python3 work/scripts/statectl.py update"}),
            _tool_use("Bash", {"command": "python3 work/scripts/statectl.py update"}),
        ),
        _assistant_turn(
            _tool_use("Bash", {"command": "python3 work/scripts/statectl.py complete"}),
            _tool_use("Bash", {"command": "python3 work/scripts/statectl.py complete"}),
        ),
        _assistant_turn(
            _tool_use(
                "Write",
                {
                    "file_path": "/Users/dev/.claude/dev/local/tmp/task-prompt-9.txt",
                    "content": "x",
                },
            ),
        ),
        _assistant_turn(
            _tool_use(
                "Write",
                {
                    "file_path": "/Users/dev/.claude/dev/local/tmp/dispatch-tess-99.txt",
                    "content": "y",
                },
            ),
        ),
        _assistant_turn(
            _statectl("task-done", "task-alpha", "dev/local/tmp/attempt-alpha.json"),
        ),
        _assistant_turn(_statectl("task-set-status", "task-beta", "completed")),
    ]
    transcript = _write_transcript(tmp_path, lines)

    exit_code = check_build_overhead.main([str(transcript)])

    assert exit_code == 0
    captured = capsys.readouterr()
    assert captured.out == (
        "TaskCreate turns: 2\n"
        "statectl calls: 7\n"
        "statectl calls per completed task: 3.50\n"
        "prompt-authoring Write calls: 2\n"
        "completed tasks: 2\n"
        "Agent dispatches: 0\n"
    )
