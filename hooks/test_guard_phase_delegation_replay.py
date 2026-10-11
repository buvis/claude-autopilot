"""Replay the real Agent dispatches this machine's transcripts captured.

Each record in `fixtures/phase_delegation/replay.jsonl` is one real `Agent`
tool-use `input` (`description`, `prompt`, `subagent_type`), copied verbatim
from a Claude Code transcript. `expect: deny` are the four phase delegations
the 2026-10-03 00242 build session made; `expect: allow` are the real
per-task and reviewer dispatches the operator wants passed.

The guard runs as a subprocess with a stdin payload, exactly as the harness
invokes it - the same shape as `test_guard_phase_delegation.py`.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

HOOKS = Path(__file__).resolve().parent
GUARD = HOOKS / "guard_phase_delegation.py"
REPLAY = HOOKS / "fixtures" / "phase_delegation" / "replay.jsonl"

# The four 00242 delegations PRD 00248 pins by id: the fixture is worthless
# as a regression gate if any of them goes missing.
PINNED_DENY = (
    "toolu_011eQouP7ZMWxba7b8ijXmiR",
    "toolu_01WwjmFapBm8w3NYCwWddUbk",
    "toolu_01S6V4tZDtrS3ePnXWtD9dT2",
    "toolu_01Ku4TbcQoeik6ZLf5XkkAuD",
)


def _records() -> list[dict]:
    lines = REPLAY.read_text(encoding="utf-8").splitlines()
    records = [json.loads(line) for line in lines if line.strip()]
    assert records, "no replay records found: an empty fixture must fail loudly"
    return records


def _run(stdin: str) -> subprocess.CompletedProcess[str]:
    env = {"PATH": "/usr/bin:/bin", "HOME": str(Path.home()), "_AUTOPILOT_LOOP": "4242"}
    return subprocess.run(
        [sys.executable, str(GUARD)],
        input=stdin,
        capture_output=True,
        text=True,
        env=env,
    )


def _agent_payload(tool_input: dict) -> str:
    return json.dumps(
        {
            "session_id": "11111111-2222-3333-4444-555555555555",
            "tool_name": "Agent",
            "tool_input": tool_input,
        }
    )


def test_replay_fixture_holds_the_four_real_delegations() -> None:
    by_id = {r["id"]: r for r in _records()}
    missing = [i for i in PINNED_DENY if i not in by_id]
    assert missing == []
    assert [by_id[i]["expect"] for i in PINNED_DENY] == ["deny"] * len(PINNED_DENY)


@pytest.mark.parametrize("record", _records(), ids=lambda r: f"{r['expect']}-{r['id']}")
def test_every_captured_real_dispatch_gets_its_expected_verdict(record: dict) -> None:
    expected = 2 if record["expect"] == "deny" else 0
    result = _run(_agent_payload(record["tool_input"]))
    assert result.returncode == expected, (record["id"], result.stderr)
