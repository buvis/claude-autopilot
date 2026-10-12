"""Drive the read-only replay CLI over synthetic transcript directories.

Every fixture here is written under `tmp_path`: the real corpus under
`~/.claude/projects/` rotates (1,112 records one day, 1,082 the next), so no
assertion may depend on it. The guard is a stub script that refuses whenever a
dispatch's `description` carries the marker `REFUSE`, which keeps the run fast
and pins refusal without depending on the real guard's wording.
"""

from __future__ import annotations

import importlib.util
import json
import re
from pathlib import Path

BIN = Path(__file__).resolve().parent
CLI = BIN / "replay_delegation_guard.py"

# The guard's exempt read-only reviewer set, which `bucket()` is called with.
EXEMPT = frozenset(
    {
        "autopilot:alice",
        "autopilot:blake",
        "autopilot:bob",
        "autopilot:carl",
        "autopilot:cora",
        "autopilot:eve",
        "autopilot:grace",
        "autopilot:mallory",
        "autopilot:pat",
        "autopilot:rita",
        "autopilot:toby",
        "autopilot:trent",
        "autopilot:victor",
    },
)

PINNED_DENY = (
    "toolu_011eQouP7ZMWxba7b8ijXmiR",
    "toolu_01WwjmFapBm8w3NYCwWddUbk",
    "toolu_01S6V4tZDtrS3ePnXWtD9dT2",
    "toolu_01Ku4TbcQoeik6ZLf5XkkAuD",
)

# Exits 0 unless the CLI put `_AUTOPILOT_LOOP` in the environment, so a run
# that forgets the variable can never produce a refusal.
STUB_GUARD = """\
import json
import os
import sys

payload = json.load(sys.stdin)
if not os.environ.get("_AUTOPILOT_LOOP"):
    sys.exit(0)
if "REFUSE" in payload["tool_input"].get("description", ""):
    sys.stderr.write("stub refusal\\n")
    sys.exit(2)
sys.exit(0)
"""


def _module():
    spec = importlib.util.spec_from_file_location("replay_delegation_guard", CLI)
    assert spec is not None and spec.loader is not None, f"cannot load {CLI}"
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _stub_guard(tmp_path: Path) -> Path:
    guard = tmp_path / "stub_guard.py"
    guard.write_text(STUB_GUARD, encoding="utf-8")
    return guard


def _transcripts(tmp_path: Path, records: list[tuple[str, dict]]) -> Path:
    directory = tmp_path / "transcripts"
    directory.mkdir()
    lines = [
        json.dumps(
            {
                "type": "assistant",
                "message": {
                    "role": "assistant",
                    "content": [
                        {
                            "type": "tool_use",
                            "name": "Agent",
                            "id": tool_id,
                            "input": tool_input,
                        },
                    ],
                },
            },
        )
        for tool_id, tool_input in records
    ]
    (directory / "session.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return directory


def _dispatch(description: str, subagent_type: str | None = None) -> dict:
    tool_input = {"description": description, "prompt": f"prompt for {description}"}
    if subagent_type is not None:
        tool_input["subagent_type"] = subagent_type
    return tool_input


def test_buckets_follow_subagent_type_and_description() -> None:
    bucket = _module().bucket
    cases: list[tuple[dict, str]] = [
        (_dispatch("run the external check", "agoge:run"), "agoge"),
        (_dispatch("Task 4 for ivan", "agoge:review"), "agoge"),
        (_dispatch("blind review", "autopilot:blake"), "reviewer"),
        (_dispatch("verify the claims", "autopilot:victor"), "reviewer"),
        (_dispatch("implement the task", "autopilot:ivan"), "per-task"),
        (_dispatch("write the failing tests", "autopilot:tess"), "per-task"),
        (_dispatch("update the docs", "autopilot:devon"), "per-task"),
        (_dispatch("do the work", "autopilot:worker-3"), "per-task"),
        (_dispatch("Task 3: wire the flag", "general-purpose"), "per-task"),
        (_dispatch("tess writes the tests first", "general-purpose"), "per-task"),
        (_dispatch("Devon updates the changelog"), "per-task"),
        (_dispatch("summarise the changelog", "general-purpose"), "other"),
        (_dispatch("fetch the release notes"), "other"),
        (_dispatch("Task 3 for ivan", "autopilot:scribe"), "other"),
    ]
    assert [bucket(tool_input, EXEMPT) for tool_input, _ in cases] == [
        verdict for _, verdict in cases
    ]


def test_refused_per_task_record_exits_one(tmp_path: Path, capsys) -> None:
    directory = _transcripts(
        tmp_path,
        [
            (
                "toolu_pertask_refused",
                _dispatch("REFUSE task 7 build", "autopilot:ivan"),
            ),
            ("toolu_reviewer_ok", _dispatch("blind review", "autopilot:blake")),
        ],
    )
    code = _module().main(
        ["--transcripts", str(directory), "--guard", str(_stub_guard(tmp_path))],
    )
    lines = capsys.readouterr().out.splitlines()
    assert code == 1, lines
    assert "per-task 1 refused 1" in lines
    assert "per-task toolu_pertask_refused autopilot:ivan REFUSE task 7 build" in lines


def test_allowed_known_delegation_exits_one(tmp_path: Path, capsys) -> None:
    pinned = PINNED_DENY[0]
    phase = _dispatch("run the build phase", "autopilot:ivan")
    directory = _transcripts(
        tmp_path,
        [("toolu_first_of_group", dict(phase)), (pinned, dict(phase))],
    )
    code = _module().main(
        ["--transcripts", str(directory), "--guard", str(_stub_guard(tmp_path))],
    )
    out = capsys.readouterr().out
    # Nothing was refused: the only failure is the pinned id being allowed, and
    # that id is the second of its dedupe group, never the first-seen one.
    assert code == 1, out
    assert re.search(r"^per-task \d+ refused 0$", out, re.MULTILINE), out
    # A bucket line is `<bucket> <count> refused <n>`, whose third token is the
    # literal `refused`; a refusal line is `<bucket> <id> <subagent_type>
    # <description>`. Only bucket lines may follow the `total N` line here.
    details = [
        line
        for line in out.splitlines()[1:]
        if not re.fullmatch(r"\S+ \d+ refused \d+", line)
    ]
    assert details == [], out


def test_missing_or_empty_transcript_dir_exits_two(tmp_path: Path) -> None:
    guard = _stub_guard(tmp_path)
    main = _module().main

    missing = tmp_path / "no-such-dir"
    assert main(["--transcripts", str(missing), "--guard", str(guard)]) == 2

    empty = tmp_path / "empty"
    empty.mkdir()
    assert main(["--transcripts", str(empty), "--guard", str(guard)]) == 2

    no_agents = tmp_path / "no-agents"
    no_agents.mkdir()
    (no_agents / "session.jsonl").write_text(
        json.dumps(
            {
                "type": "assistant",
                "message": {
                    "role": "assistant",
                    "content": [
                        {"type": "text", "text": "thinking it over"},
                        {
                            "type": "tool_use",
                            "name": "Read",
                            "id": "toolu_read_only",
                            "input": {"file_path": "/tmp/x"},
                        },
                    ],
                },
            },
        )
        + "\n",
        encoding="utf-8",
    )
    assert main(["--transcripts", str(no_agents), "--guard", str(guard)]) == 2


def test_other_refusals_are_printed_but_exit_zero(tmp_path: Path, capsys) -> None:
    directory = _transcripts(
        tmp_path,
        [
            (
                "toolu_other_refused",
                _dispatch("REFUSE summarise the notes", "general-purpose"),
            ),
            ("toolu_pertask_ok", _dispatch("task 1 build", "autopilot:ivan")),
        ],
    )
    code = _module().main(
        ["--transcripts", str(directory), "--guard", str(_stub_guard(tmp_path))],
    )
    lines = capsys.readouterr().out.splitlines()
    assert code == 0, lines
    assert lines[0] == "total 2"
    assert "other 1 refused 1" in lines
    assert "per-task 1 refused 0" in lines
    assert (
        "other toolu_other_refused general-purpose REFUSE summarise the notes" in lines
    )
