"""Drive the read-only replay CLI over synthetic transcript directories.

Every fixture here is written under `tmp_path`: the real corpus under
`~/.claude/projects/` rotates (1,112 records one day, 1,082 the next), so no
assertion may depend on it.

The guard is a stub script that logs one line per invocation to a file under
`tmp_path`, so a run that skips the guard is visible. It refuses only when the
CLI put `_AUTOPILOT_LOOP=1` in its environment AND the payload carries the
marker `DENY-ME`, which lives in the dispatch's `prompt` and never in its
`description`: a CLI that infers refusal from the printed text, or that drops
the environment variable, cannot reproduce the stub's verdicts.

`total N` is read as the number of deduped dispatches, so it is always
asserted to equal the sum of the per-bucket counts.
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

# Carried in the `prompt`, so it never reaches a printed refusal line.
MARKER = "DENY-ME"

BUCKET_LINE = r"\S+ \d+ refused \d+"

STUB_GUARD = '''\
import os
import sys

raw = sys.stdin.read()
with open({log!r}, "a", encoding="utf-8") as handle:
    handle.write(" ".join(raw.split()) + "\\n")
loop = os.environ.get("_AUTOPILOT_LOOP") == "1"
if {refuse_without_loop} and not loop:
    sys.stderr.write("guard ran without _AUTOPILOT_LOOP\\n")
    sys.exit(2)
if loop and "{marker}" in raw:
    sys.stderr.write("stub refusal\\n")
    sys.exit(2)
sys.exit(0)
'''


def _module():
    spec = importlib.util.spec_from_file_location("replay_delegation_guard", CLI)
    assert spec is not None and spec.loader is not None, f"cannot load {CLI}"
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _stub_guard(
    tmp_path: Path,
    name: str = "stub_guard",
    *,
    refuse_without_loop: bool = False,
) -> tuple[Path, Path]:
    """Return the stub guard's path and the path it logs its invocations to."""
    log = tmp_path / f"{name}.log"
    guard = tmp_path / f"{name}.py"
    guard.write_text(
        STUB_GUARD.format(
            log=str(log),
            refuse_without_loop=refuse_without_loop,
            marker=MARKER,
        ),
        encoding="utf-8",
    )
    return guard, log


def _guard_calls(log: Path) -> list[str]:
    if not log.exists():
        return []
    return [line for line in log.read_text(encoding="utf-8").splitlines() if line]


def _write_jsonl(path: Path, records: list[tuple[str, dict]]) -> None:
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
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _transcripts(
    tmp_path: Path,
    records: list[tuple[str, dict]],
    name: str = "transcripts",
) -> Path:
    directory = tmp_path / name
    directory.mkdir()
    _write_jsonl(directory / "session.jsonl", records)
    return directory


def _dispatch(
    description: str,
    subagent_type: str | None = None,
    *,
    deny: bool = False,
) -> dict:
    prompt = f"prompt for {description}"
    if deny:
        prompt = f"{prompt} {MARKER}"
    tool_input = {"description": description, "prompt": prompt}
    if subagent_type is not None:
        tool_input["subagent_type"] = subagent_type
    return tool_input


def _main(directory: Path, guard: Path) -> int:
    return _module().main(["--transcripts", str(directory), "--guard", str(guard)])


def _report(out: str) -> tuple[int, list[str], list[str]]:
    """Split stdout into `total`, the bucket-line block, and the refusal lines."""
    lines = out.splitlines()
    assert lines and re.fullmatch(r"total \d+", lines[0]), out
    rest = lines[1:]
    cut = 0
    while cut < len(rest) and re.fullmatch(BUCKET_LINE, rest[cut]):
        cut += 1
    buckets, details = rest[:cut], rest[cut:]
    assert not [line for line in details if re.fullmatch(BUCKET_LINE, line)], out
    total = int(lines[0].split()[1])
    assert total == sum(int(line.split()[1]) for line in buckets), out
    return total, buckets, details


def test_buckets_follow_subagent_type_and_description() -> None:
    bucket = _module().bucket
    # The same description recurs under different `subagent_type`s with
    # different verdicts, so no description table can answer these.
    cases: list[tuple[dict, str]] = [
        (_dispatch("do the work", "agoge:run"), "agoge"),
        (_dispatch("do the work", "autopilot:blake"), "reviewer"),
        (_dispatch("do the work", "autopilot:ivan"), "per-task"),
        (_dispatch("do the work", "autopilot:tess"), "per-task"),
        (_dispatch("do the work", "autopilot:devon"), "per-task"),
        (_dispatch("do the work", "autopilot:worker-3"), "per-task"),
        (_dispatch("do the work", "autopilot:scribe"), "other"),
        (_dispatch("do the work", "general-purpose"), "other"),
        (_dispatch("do the work"), "other"),
        (_dispatch("task 12 for ivan", "agoge:review"), "agoge"),
        (_dispatch("task 12 for ivan", "general-purpose"), "per-task"),
        (_dispatch("task 12 for ivan"), "per-task"),
        (_dispatch("task 12 for ivan", "autopilot:scribe"), "other"),
        (_dispatch("tess drafts it", "general-purpose"), "per-task"),
        (_dispatch("devon ships it"), "per-task"),
        (_dispatch("Task B3 ships", "general-purpose"), "per-task"),
        (_dispatch("contest the matter", "general-purpose"), "other"),
        (_dispatch("multitask 4 things"), "other"),
    ]
    assert [bucket(tool_input, EXEMPT) for tool_input, _ in cases] == [
        verdict for _, verdict in cases
    ]


def test_reviewer_bucket_follows_the_exempt_set() -> None:
    bucket = _module().bucket
    # Every exempt name is a reviewer, not just the few that show up in
    # fixtures; a name dropped from the set stops being one.
    verdicts = {name: bucket(_dispatch("do the work", name), EXEMPT) for name in EXEMPT}
    assert verdicts == {name: "reviewer" for name in EXEMPT}
    for dropped in sorted(EXEMPT):
        lone = _dispatch("do the work", dropped)
        assert bucket(lone, EXEMPT - {dropped}) == "other", dropped
        assert bucket(lone, frozenset()) == "other", dropped


def test_refused_per_task_record_exits_one(tmp_path: Path, capsys) -> None:
    guard, log = _stub_guard(tmp_path)
    directory = _transcripts(
        tmp_path,
        [
            (
                "toolu_pertask_denied",
                _dispatch("task 7 build", "autopilot:ivan", deny=True),
            ),
            ("toolu_reviewer_ok", _dispatch("do the work", "autopilot:blake")),
            ("toolu_agoge_ok", _dispatch("run the external check", "agoge:run")),
            ("toolu_other_ok", _dispatch("summarise the notes", "general-purpose")),
        ],
    )
    code = _main(directory, guard)
    total, buckets, details = _report(capsys.readouterr().out)
    assert code == 1, (total, buckets, details)
    assert total == 4, buckets
    assert sorted(buckets) == [
        "agoge 1 refused 0",
        "other 1 refused 0",
        "per-task 1 refused 1",
        "reviewer 1 refused 0",
    ]
    assert details == ["per-task toolu_pertask_denied autopilot:ivan task 7 build"]
    assert len(_guard_calls(log)) == 4, _guard_calls(log)


def test_allowed_known_delegation_exits_one(tmp_path: Path, capsys) -> None:
    phase = _dispatch("run the build phase", "autopilot:ivan")
    guard, log = _stub_guard(tmp_path)
    # Identical `tool_input` twice, the pinned id second: it is never the
    # first-seen id of its dedupe group.
    pinned_dir = _transcripts(
        tmp_path,
        [("toolu_first_of_group", dict(phase)), (PINNED_DENY[0], dict(phase))],
        name="pinned",
    )
    code = _main(pinned_dir, guard)
    total, buckets, details = _report(capsys.readouterr().out)
    assert code == 1, (total, buckets, details)
    # Both records collapse into one group, so the guard ran exactly once.
    assert total == 1 and buckets == ["per-task 1 refused 0"], buckets
    assert details == [], details
    assert len(_guard_calls(log)) == 1, _guard_calls(log)

    # The same directory with an ordinary second id is a clean, exit-0 run, so
    # exit 1 above came from the pinned id and not from the record count.
    clean_guard, clean_log = _stub_guard(tmp_path, "clean_guard")
    clean_dir = _transcripts(
        tmp_path,
        [("toolu_first_of_group", dict(phase)), ("toolu_second_of_group", dict(phase))],
        name="clean",
    )
    assert _main(clean_dir, clean_guard) == 0, capsys.readouterr().out
    assert _report(capsys.readouterr().out)[1] == ["per-task 1 refused 0"]
    assert len(_guard_calls(clean_log)) == 1, _guard_calls(clean_log)


def test_each_pinned_deny_id_fails_when_allowed(tmp_path: Path, capsys) -> None:
    for index, pinned in enumerate(PINNED_DENY):
        guard, log = _stub_guard(tmp_path, f"guard_{index}")
        directory = _transcripts(
            tmp_path,
            [(pinned, _dispatch("run the build phase", "autopilot:ivan"))],
            name=f"pinned_{index}",
        )
        code = _main(directory, guard)
        total, buckets, details = _report(capsys.readouterr().out)
        assert code == 1, (pinned, total, buckets, details)
        assert buckets == ["per-task 1 refused 0"] and details == [], pinned
        assert len(_guard_calls(log)) == 1, pinned


def test_unpinned_tool_id_of_the_same_shape_does_not_fail(
    tmp_path: Path,
    capsys,
) -> None:
    guard, log = _stub_guard(tmp_path)
    directory = _transcripts(
        tmp_path,
        [
            (
                "toolu_01Zz9QouP7ZMWxba7b8ijXmQ",
                _dispatch("task 2 build", "autopilot:tess"),
            ),
        ],
    )
    code = _main(directory, guard)
    total, buckets, details = _report(capsys.readouterr().out)
    assert code == 0, (total, buckets, details)
    assert buckets == ["per-task 1 refused 0"] and details == [], buckets
    assert len(_guard_calls(log)) == 1, _guard_calls(log)


def test_guard_runs_with_the_loop_environment_variable(
    tmp_path: Path,
    capsys,
    monkeypatch,
) -> None:
    monkeypatch.delenv("_AUTOPILOT_LOOP", raising=False)
    # This stub refuses every dispatch unless `_AUTOPILOT_LOOP=1` reached it,
    # so a clean report proves the CLI set the variable.
    guard, log = _stub_guard(tmp_path, refuse_without_loop=True)
    directory = _transcripts(
        tmp_path,
        [
            ("toolu_pertask", _dispatch("task 7 build", "autopilot:ivan")),
            ("toolu_reviewer", _dispatch("do the work", "autopilot:blake")),
        ],
    )
    code = _main(directory, guard)
    total, buckets, details = _report(capsys.readouterr().out)
    assert code == 0, (total, buckets, details)
    assert sorted(buckets) == ["per-task 1 refused 0", "reviewer 1 refused 0"]
    assert details == [], details
    assert len(_guard_calls(log)) == 2, _guard_calls(log)


def test_missing_guard_cannot_report_an_allowed_run(tmp_path: Path, capsys) -> None:
    directory = _transcripts(
        tmp_path,
        [("toolu_pertask", _dispatch("task 7 build", "autopilot:ivan"))],
    )
    absent = tmp_path / "no_such_guard.py"
    assert not absent.exists()
    try:
        code: int | None = _main(directory, absent)
    except OSError:
        code = None
    # Nothing can vouch for this dispatch, so the run must not come back clean.
    assert code != 0, capsys.readouterr().out


def test_missing_or_empty_transcript_dir_exits_two(tmp_path: Path) -> None:
    guard, log = _stub_guard(tmp_path)
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
    # No Agent input anywhere, so the guard had nothing to replay.
    assert _guard_calls(log) == []


def test_every_jsonl_transcript_in_the_tree_is_scanned(
    tmp_path: Path,
    capsys,
) -> None:
    guard, log = _stub_guard(tmp_path)
    root = tmp_path / "projects"
    nested = root / "-Users-bob-git-src-github-com-buvis-claude-autopilot"
    nested.mkdir(parents=True)
    _write_jsonl(
        nested / "0f3c8b42-7d11-4a90-9c5e-1b2d3e4f5a61.jsonl",
        [("toolu_from_first_file", _dispatch("task 1 build", "autopilot:ivan"))],
    )
    _write_jsonl(
        nested / "9b12ca07-3e55-42aa-8f01-77c6d9e0b4f3.jsonl",
        [("toolu_from_second_file", _dispatch("task 2 build", "autopilot:tess"))],
    )
    code = _main(root, guard)
    total, buckets, details = _report(capsys.readouterr().out)
    assert code == 0, (total, buckets, details)
    assert total == 2, buckets
    assert buckets == ["per-task 2 refused 0"] and details == [], buckets
    assert len(_guard_calls(log)) == 2, _guard_calls(log)


def test_other_refusals_are_printed_but_exit_zero(tmp_path: Path, capsys) -> None:
    guard, log = _stub_guard(tmp_path)
    directory = _transcripts(
        tmp_path,
        [
            (
                "toolu_other_denied",
                _dispatch("summarise the notes", "general-purpose", deny=True),
            ),
            ("toolu_pertask_1", _dispatch("task 1 build", "autopilot:ivan")),
            ("toolu_pertask_2", _dispatch("task 2 tests", "autopilot:tess")),
            ("toolu_pertask_3", _dispatch("task 3 docs", "autopilot:devon")),
        ],
    )
    code = _main(directory, guard)
    total, buckets, details = _report(capsys.readouterr().out)
    assert code == 0, (total, buckets, details)
    # Uneven split: `total` tracks the sum of the counts, not a fixed 2.
    assert total == 4, buckets
    assert sorted(buckets) == ["other 1 refused 1", "per-task 3 refused 0"]
    assert details == [
        "other toolu_other_denied general-purpose summarise the notes",
    ]
    assert len(_guard_calls(log)) == 4, _guard_calls(log)
