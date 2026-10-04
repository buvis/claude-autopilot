"""PRD 00248: deny an Agent call that hands a whole phase skill to a subagent.

`guard_phase_delegation.py` (PreToolUse, Agent) runs here as a subprocess with
a stdin payload, exactly as the harness invokes it; the allow corpus goes
straight through `is_phase_delegation` because it is ~180 prompts.

Fixtures:
- `fixtures/phase_delegation/denied/*.txt` - the four Agent calls the
  2026-10-03 00242 build session made instead of running the phase skills
  itself, captured byte-for-byte from that session's transcript. Line 1 is
  the call's `description`, the rest is its `prompt`.
- `fixtures/phase_delegation/allowed/*.txt` - 20 real per-task dispatch
  prompts copied verbatim from `docs/dev/tmp/dispatch-*.txt`; each file is a
  whole `prompt`. Six of them name a phase skill without delegating it.
"""

from __future__ import annotations

import importlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

HOOKS = Path(__file__).resolve().parent
GUARD = HOOKS / "guard_phase_delegation.py"
FIXTURES = HOOKS / "fixtures" / "phase_delegation"
CORPUS = HOOKS.parent / "docs" / "dev" / "tmp"
REASON = "hooks/guard_phase_delegation.py denied this Agent call."


_SELF_REFERENTIAL = {"dispatch-tess-1.txt", "dispatch-ivan-1.txt"}


def _allow_corpus() -> list[Path]:
    # This PRD's own task-1 dispatch prompts quote the denied phrases
    # verbatim to specify the hook's contract - not a real delegation
    # attempt, so they are excluded rather than counted as false positives.
    real = sorted(
        p for p in CORPUS.glob("dispatch-*.txt") if p.name not in _SELF_REFERENTIAL
    )
    return real or sorted((FIXTURES / "allowed").glob("*.txt"))


def _denied() -> list[Path]:
    return sorted((FIXTURES / "denied").glob("*.txt"))


def _tool_input(fixture: Path) -> dict:
    description, _, prompt = fixture.read_text(encoding="utf-8").partition("\n")
    return {"description": description, "prompt": prompt, "subagent_type": "general-purpose"}


def _run(stdin: str, *, loop: bool) -> subprocess.CompletedProcess[str]:
    env = {"PATH": "/usr/bin:/bin", "HOME": str(Path.home())}
    if loop:
        env["_AUTOPILOT_LOOP"] = "4242"
    return subprocess.run(
        [sys.executable, str(GUARD)],
        input=stdin,
        capture_output=True,
        text=True,
        env=env,
    )


def _agent_payload(tool_input: object) -> str:
    return json.dumps(
        {
            "session_id": "11111111-2222-3333-4444-555555555555",
            "tool_name": "Agent",
            "tool_input": tool_input,
        }
    )


def test_the_four_observed_delegations_are_denied() -> None:
    fixtures = _denied()
    assert len(fixtures) == 4
    results = {f.name: _run(_agent_payload(_tool_input(f)), loop=True) for f in fixtures}
    let_through = sorted(name for name, r in results.items() if r.returncode != 2)
    assert let_through == []
    for name, result in results.items():
        assert REASON in result.stderr, name
        assert "with the Skill tool in THIS session" in result.stderr, name


@pytest.mark.parametrize("prompt_file", _allow_corpus(), ids=lambda p: p.name)
def test_every_real_dispatch_prompt_is_allowed(prompt_file: Path) -> None:
    sys.path.insert(0, str(HOOKS))
    guard = importlib.import_module("guard_phase_delegation")
    prompt = prompt_file.read_text(encoding="utf-8")
    assert prompt.strip(), prompt_file.name
    assert guard.is_phase_delegation({"prompt": prompt, "description": ""}) is False


def test_outside_the_loop_everything_passes() -> None:
    for fixture in _denied():
        result = _run(_agent_payload(_tool_input(fixture)), loop=False)
        assert result.returncode == 0, fixture.name
        assert result.stderr == "", fixture.name


@pytest.mark.parametrize(
    ("stdin", "message"),
    [
        ("", "empty/unparseable payload, allowing"),
        ("not json {", "empty/unparseable payload, allowing"),
        ('["Agent"]', "empty/unparseable payload, allowing"),
        (_agent_payload("Execute the work phase for PRD 00242"), "unparseable tool_input, allowing"),
        (_agent_payload(None), "unparseable tool_input, allowing"),
    ],
    ids=["empty", "not-json", "json-array", "tool-input-string", "tool-input-null"],
)
def test_unparseable_payload_fails_open(stdin: str, message: str) -> None:
    result = _run(stdin, loop=True)
    assert result.returncode == 0
    assert f"guard_phase_delegation: {message}" in result.stderr
