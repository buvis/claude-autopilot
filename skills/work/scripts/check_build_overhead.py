"""Transcript clerical-overhead metrics report.

Reads a Claude Code session transcript (JSONL) and reports counts of
clerical/bookkeeping tool calls made during a build session: TaskCreate
turns, statectl Bash invocations, prompt-authoring Write calls, completed
tasks and Agent dispatches.

Completed tasks come from the statectl task verbs (``task-done <id>`` and
``task-set-status <id> completed``), counted by distinct task id. When no
completion verb is found the report says so and prints no per-task ratio: a
ratio over zero tasks reads as a perfect score when it is really no data.
"""

from __future__ import annotations

import argparse
import fnmatch
import json
import shlex
import sys
from collections.abc import Iterable
from pathlib import Path

_PROMPT_WRITE_GLOBS = (
    "*/dev/local/tmp/*prompt*",
    "*/dev/local/tmp/dispatch-*",
)
_AGENT_TOOL_NAMES = ("Agent", "Task")
_ZERO_TASKS_LINE = "completed tasks: 0 (no statectl task-done calls found)"


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Report clerical-overhead metrics from a build transcript.",
    )
    parser.add_argument("transcript", help="Path to the transcript JSONL file.")
    return parser.parse_args(argv)


def _is_statectl_call(command: str) -> bool:
    return command.startswith("python3") and "statectl.py" in command


def _is_prompt_authoring_write(file_path: str) -> bool:
    return any(fnmatch.fnmatch(file_path, pattern) for pattern in _PROMPT_WRITE_GLOBS)


def count_completed_tasks(commands: Iterable[str]) -> int:
    """Count distinct task ids completed by statectl verbs in `commands`."""
    completed: set[str] = set()
    for command in commands:
        try:
            tokens = shlex.split(command)
        except ValueError:
            tokens = command.split()
        for index, token in enumerate(tokens):
            if (token == "task-done" and index + 1 < len(tokens)) or (
                token == "task-set-status"
                and index + 2 < len(tokens)
                and tokens[index + 2] == "completed"
            ):
                completed.add(tokens[index + 1])
    return len(completed)


def _classify_content_blocks(
    content: list[object],
) -> tuple[bool, list[str], int, int]:
    """Classify one assistant turn's content blocks.

    Returns (turn_has_taskcreate, statectl_commands, prompt_write_calls,
    agent_dispatches).
    """
    turn_has_taskcreate = False
    statectl_commands: list[str] = []
    prompt_write_calls = 0
    agent_dispatches = 0

    for block in content:
        if not isinstance(block, dict):
            continue
        if block.get("type") != "tool_use":
            continue
        name = block.get("name")
        tool_input = block.get("input", {})
        if name == "TaskCreate":
            turn_has_taskcreate = True
        elif name == "Bash":
            command = tool_input.get("command", "")
            if _is_statectl_call(command):
                statectl_commands.append(command)
        elif name == "Write":
            if _is_prompt_authoring_write(tool_input.get("file_path", "")):
                prompt_write_calls += 1
        elif name in _AGENT_TOOL_NAMES:
            agent_dispatches += 1

    return turn_has_taskcreate, statectl_commands, prompt_write_calls, agent_dispatches


def _classify_lines(lines: Iterable[str]) -> tuple[int, list[str], int, int, bool, int]:
    """Stream-classify transcript lines.

    Returns (taskcreate_turns, statectl_commands, prompt_write_calls,
    agent_dispatches, any_parseable, malformed_line_count).
    """
    taskcreate_turns = 0
    statectl_commands: list[str] = []
    prompt_write_calls = 0
    agent_dispatches = 0
    any_parseable = False
    malformed_line_count = 0

    for raw_line in lines:
        raw_line = raw_line.strip()
        if not raw_line:
            continue
        try:
            entry = json.loads(raw_line)
        except json.JSONDecodeError:
            malformed_line_count += 1
            continue
        any_parseable = True

        if entry.get("type") != "assistant":
            continue
        content = entry.get("message", {}).get("content", [])
        if not isinstance(content, list):
            continue

        has_taskcreate, commands, writes, dispatches = _classify_content_blocks(content)
        statectl_commands.extend(commands)
        prompt_write_calls += writes
        agent_dispatches += dispatches
        if has_taskcreate:
            taskcreate_turns += 1

    return (
        taskcreate_turns,
        statectl_commands,
        prompt_write_calls,
        agent_dispatches,
        any_parseable,
        malformed_line_count,
    )


def report(path: Path) -> str:
    """Return the stdout report for `path`, or "" when nothing was parseable.

    Malformed-line warnings go to stderr as a side effect.
    """
    with path.open() as f:
        (
            taskcreate_turns,
            statectl_commands,
            prompt_write_calls,
            agent_dispatches,
            any_parseable,
            malformed_line_count,
        ) = _classify_lines(f)

    if not any_parseable:
        return ""

    completed_tasks = count_completed_tasks(statectl_commands)
    statectl_calls = len(statectl_commands)

    lines = [
        f"TaskCreate turns: {taskcreate_turns}",
        f"statectl calls: {statectl_calls}",
    ]
    if completed_tasks:
        ratio = statectl_calls / completed_tasks
        lines.append(f"statectl calls per completed task: {ratio:.2f}")
    lines.append(f"prompt-authoring Write calls: {prompt_write_calls}")
    lines.append(
        f"completed tasks: {completed_tasks}" if completed_tasks else _ZERO_TASKS_LINE,
    )
    lines.append(f"Agent dispatches: {agent_dispatches}")

    if malformed_line_count > 0:
        print(
            f"warning: skipped {malformed_line_count} unparseable line(s) in {path}",
            file=sys.stderr,
        )

    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    transcript_path = Path(args.transcript)

    try:
        text = report(transcript_path)
    except FileNotFoundError:
        print(f"error: transcript file not found: {transcript_path}", file=sys.stderr)
        return 1
    except IsADirectoryError:
        print(f"error: not a file: {transcript_path}", file=sys.stderr)
        return 1
    except PermissionError:
        print(f"error: permission denied: {transcript_path}", file=sys.stderr)
        return 1

    if not text:
        print(f"error: no parseable JSON lines in {transcript_path}", file=sys.stderr)
        return 2

    print(text, end="")
    return 0


if __name__ == "__main__":
    sys.exit(main())
