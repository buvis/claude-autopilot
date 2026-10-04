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
import re
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


def _self_referential(p: Path) -> bool:
    # This PRD's own dispatch prompts (Tess, Devon, Ivan, their retries)
    # quote the denied phrases verbatim to specify the hook's contract - not
    # a real delegation attempt, so they are excluded rather than counted
    # as false positives.
    return p.name in _SELF_REFERENTIAL or "guard_phase_delegation" in p.read_text(
        encoding="utf-8"
    )


def _allow_corpus() -> list[Path]:
    real = sorted(p for p in CORPUS.glob("dispatch-*.txt") if not _self_referential(p))
    return real or sorted((FIXTURES / "allowed").glob("*.txt"))


def _denied() -> list[Path]:
    return sorted((FIXTURES / "denied").glob("*.txt"))


def _description(prompt_file: Path) -> str:
    # A realistic Agent `description` for a per-task dispatch, e.g.
    # "Tess 9 strengthen subagent" for dispatch-tess-9-strengthen.txt.
    return prompt_file.stem.removeprefix("dispatch-").replace("-", " ").capitalize() + " subagent"


def _tool_input(fixture: Path, subagent_type: str | None = "general-purpose") -> dict:
    description, _, prompt = fixture.read_text(encoding="utf-8").partition("\n")
    tool_input = {"description": description, "prompt": prompt}
    if subagent_type is not None:
        tool_input["subagent_type"] = subagent_type
    return tool_input


def _run(stdin: str, *, loop: bool, loop_value: str = "4242") -> subprocess.CompletedProcess[str]:
    env = {"PATH": "/usr/bin:/bin", "HOME": str(Path.home())}
    if loop:
        env["_AUTOPILOT_LOOP"] = loop_value
    return subprocess.run(
        [sys.executable, str(GUARD)],
        input=stdin,
        capture_output=True,
        text=True,
        env=env,
    )


def _agent_payload(tool_input: object, tool_name: str = "Agent") -> str:
    return json.dumps(
        {
            "session_id": "11111111-2222-3333-4444-555555555555",
            "tool_name": tool_name,
            "tool_input": tool_input,
        }
    )


def _guard_module():
    sys.path.insert(0, str(HOOKS))
    return importlib.import_module("guard_phase_delegation")


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
    guard = _guard_module()
    prompt = prompt_file.read_text(encoding="utf-8")
    assert prompt.strip(), prompt_file.name
    assert guard.is_phase_delegation({"prompt": prompt, "description": ""}) is False
    described = {"prompt": prompt, "description": _description(prompt_file)}
    assert guard.is_phase_delegation(described) is False


def test_committed_allowed_prompts_pass_the_hook_in_the_loop() -> None:
    # main() must route allowed prompts through the predicate, not deny every Agent call.
    samples = sorted((FIXTURES / "allowed").glob("*.txt"))
    assert len(samples) == 20
    blocked = []
    for sample in samples:
        tool_input = {
            "description": _description(sample),
            "prompt": sample.read_text(encoding="utf-8"),
            "subagent_type": "general-purpose",
        }
        result = _run(_agent_payload(tool_input), loop=True)
        if result.returncode != 0 or result.stderr != "":
            blocked.append((sample.name, result.returncode, result.stderr))
    assert blocked == []


def test_work_phase_named_only_in_the_description_without_a_verb_is_allowed() -> None:
    # The phase jargon alone is not a delegation: the contract needs an
    # imperative verb (run/execute/continue/resume) beside it.
    tool_input = {
        "description": "Ivan: work phase task 3 of PRD 00300",
        "prompt": "Implement task 3 of PRD 00300: add the parser and its tests.",
    }
    assert _guard_module().is_phase_delegation(tool_input) is False
    result = _run(_agent_payload(tool_input), loop=True)
    assert result.returncode == 0
    assert result.stderr == ""


_NEUTRAL_PROMPT = "Implement task 3 of PRD 00300: add the parser and its tests."


@pytest.mark.parametrize(
    ("description", "prompt"),
    [
        ("PRD 00300 build", "Run the autopilot:work skill on PRD 00300 and report back."),
        ("PRD 00300 plan", "Follow /autopilot:plan-tasks for 00300 exactly."),
        ("PRD 00300 design", "Invoke `/autopilot:design-solution` for PRD 00300."),
        ("PRD 00300", "EXECUTE THE AUTOPILOT:WORK SKILL FOR PRD 00300."),
        ("PRD 00300", "Please resume the Work Phase from task 2 of PRD 00300."),
        ("PRD 00300", "Planning phase for PRD 00300: continue it from task 4."),
        ("PRD 00300", "Read skills/work/SKILL.md and follow every task in it for PRD 00300."),
        ("Run plan-tasks for PRD 00300", _NEUTRAL_PROMPT),
        ("Continue the design phase for PRD 00300", _NEUTRAL_PROMPT),
    ],
    ids=[
        "run-the-skill", "follow-slash", "invoke-backticks", "upper-case",
        "resume-phase-mixed-case", "phase-then-verb", "read-skill-md-follow-every-task",
        "description-only-skill", "description-only-phase",
    ],
)
def test_reworded_delegations_are_denied(description: str, prompt: str) -> None:
    tool_input = {"description": description, "prompt": prompt, "subagent_type": "general-purpose"}
    result = _run(_agent_payload(tool_input), loop=True)
    assert result.returncode == 2
    assert REASON in result.stderr


@pytest.mark.parametrize("subagent_type", ["Explore", "Plan", None], ids=["explore", "plan", "omitted"])
def test_delegations_are_denied_whatever_the_subagent_type(subagent_type: str | None) -> None:
    for fixture in _denied():
        result = _run(_agent_payload(_tool_input(fixture, subagent_type)), loop=True)
        assert result.returncode == 2, fixture.name
        assert REASON in result.stderr, fixture.name


@pytest.mark.parametrize("loop_value", ["1", "98765"])
def test_any_non_empty_loop_value_arms_the_guard(loop_value: str) -> None:
    for fixture in _denied():
        result = _run(_agent_payload(_tool_input(fixture)), loop=True, loop_value=loop_value)
        assert result.returncode == 2, fixture.name
        assert REASON in result.stderr, fixture.name


@pytest.mark.parametrize("tool_name", ["Bash", "Skill"])
def test_non_agent_tools_pass_even_with_a_delegation_payload(tool_name: str) -> None:
    for fixture in _denied():
        result = _run(_agent_payload(_tool_input(fixture), tool_name), loop=True)
        assert result.returncode == 0, fixture.name
        assert result.stderr == "", fixture.name


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


@pytest.mark.parametrize(
    "tool_input",
    [{}, {"prompt": None}, {"prompt": None, "description": None}],
    ids=["empty-dict", "prompt-none", "both-none"],
)
def test_dict_without_a_string_prompt_or_description_is_allowed_silently(tool_input: dict) -> None:
    # Contract: neither key present as a non-empty string -> predicate False.
    assert _guard_module().is_phase_delegation(tool_input) is False
    result = _run(_agent_payload(tool_input), loop=True)
    assert result.returncode == 0
    assert result.stderr == ""


def test_non_string_prompt_never_crashes_the_hook() -> None:
    # The contract leaves a non-string prompt beside a string description
    # unspecified for the predicate; main() must still fail open, never exit
    # 1 with a traceback.
    result = _run(_agent_payload({"prompt": 5, "description": "x"}), loop=True)
    assert result.returncode == 0
    assert result.stderr in ("", "guard_phase_delegation: predicate raised, allowing\n")


PLUGIN = HOOKS.parent


# The three PreToolUse entries that must survive untouched - verbatim from
# HEAD, so Devon's "empty an existing entry's hooks" and "add a stray
# top-level key" exploits are both caught by exact equality.
_EXISTING_PRE = [
    {
        "matcher": "Edit|Write|MultiEdit",
        "hooks": [
            {
                "type": "command",
                "command": "python3 ${CLAUDE_PLUGIN_ROOT}/hooks/enforce_prd_location.py",
                "timeout": 5,
            }
        ],
    },
    {
        "matcher": "Bash",
        "hooks": [
            {
                "type": "command",
                "command": "python3 ${CLAUDE_PLUGIN_ROOT}/hooks/enforce_prd_location.py",
                "timeout": 5,
            },
            {
                "type": "command",
                "command": "python3 ${CLAUDE_PLUGIN_ROOT}/hooks/guard_push_on_critical.py",
                "timeout": 10,
            },
        ],
    },
    {
        "matcher": "Skill",
        "hooks": [
            {
                "type": "command",
                "command": "python3 ${CLAUDE_PLUGIN_ROOT}/hooks/guard_skill_after_leave.py",
                "timeout": 5,
            }
        ],
    },
]


def test_hooks_json_registers_the_guard_on_agent() -> None:
    assert GUARD.is_file()
    data = json.loads((HOOKS / "hooks.json").read_text(encoding="utf-8"))
    assert set(data) == {"hooks"}
    hooks = data["hooks"]
    pre = hooks["PreToolUse"]
    # Exactly one new entry, appended after the three existing ones, which
    # must be byte-for-byte unchanged (no emptied/deleted existing hook).
    assert pre[:3] == _EXISTING_PRE
    assert len(pre) == 4
    agent = pre[3]
    assert agent == {
        "matcher": "Agent",
        "hooks": [
            {
                "type": "command",
                "command": "python3 ${CLAUDE_PLUGIN_ROOT}/hooks/guard_phase_delegation.py",
                "timeout": 5,
            }
        ],
    }
    # Registered exactly once, anywhere in the file, under any spelling
    # that would actually invoke the module (with or without ".py").
    commands = [
        hook["command"]
        for event in hooks.values()
        for entry in event
        for hook in entry["hooks"]
    ]
    assert sum("guard_phase_delegation" in c for c in commands) == 1


def _paragraphs(path: Path) -> list[str]:
    # Markdown rendering: a blank line (possibly whitespace-only) splits
    # paragraphs; any other run of whitespace (a hard wrap) reads as one
    # space. Using the raw, un-flattened text keeps an HTML comment, a
    # code fence or a heading marker (#, >, <!--) visible in the result,
    # so a gate/anchor hidden inside one of those never matches a plain
    # sentence-level assertion below.
    raw = path.read_text(encoding="utf-8")
    paragraphs = re.split(r"\n[ \t]*\n", raw)
    return [" ".join(p.split()) for p in paragraphs]


_BANNED_NEAR_GATE = ("ignore", "advisory", "may be ignored", "dispatch an agent to")


def test_gate_prose_names_the_guard() -> None:
    build_md = PLUGIN / "skills" / "run-autopilot" / "references" / "phase-build.md"
    paras = _paragraphs(build_md)
    plan_anchor = "Invoke `/autopilot:plan-tasks` with the selected PRD."
    plan_gate = (
        "Invoke `/autopilot:plan-tasks` with the Skill tool in this session; never"
        " delegate planning to an Agent."
    )
    plan_next = "**PAUSE site - requirements clarification.**"
    work_anchor = "Invoke `/autopilot:work` skill."
    work_gate = (
        "Invoke `/autopilot:work` with the Skill tool in this session; never"
        " delegate work execution to an Agent."
    )
    work_next = "While `/autopilot:work` runs"
    for gate, anchor, next_text in (
        (plan_gate, plan_anchor, plan_next),
        (work_gate, work_anchor, work_next),
    ):
        # The gate and its anchor must sit in ONE paragraph together (not a
        # comment, a heading, or split across a blank line), and that
        # paragraph's own neighbourhood must be unchanged from HEAD, so
        # neither sentence can be relocated elsewhere in the file.
        matches = [p for p in paras if gate in p and anchor in p]
        assert len(matches) == 1, (gate, anchor)
        para = matches[0]
        assert para.startswith(f"{gate} {anchor}") or para == f"{gate} {anchor}"
        for banned in _BANNED_NEAR_GATE:
            assert banned not in para.lower(), (banned, para)
        idx = paras.index(para)
        assert next_text in paras[idx + 1], (next_text, paras[idx + 1])
    assert sum(1 for p in paras if plan_gate in p) == 1
    assert sum(1 for p in paras if work_gate in p) == 1
    assert build_md.read_text(encoding="utf-8").index(
        "## Phase 2: Planning"
    ) < build_md.read_text(encoding="utf-8").index(plan_gate)
    assert build_md.read_text(encoding="utf-8").index(
        plan_gate
    ) < build_md.read_text(encoding="utf-8").index("## Phase 3: Work")

    stop = (
        "**STOP.** Before dispatching ANY Agent or helper-script call, verify you"
        " are sending it EXACTLY ONE task. Batching tasks into one Agent call"
        " leaves `state.tasks` (and every dashboard reading state.json) stale for"
        " the entire duration and collapses per-task attempt logging."
    )
    guard_note = (
        "In loop mode a hook denies dispatching a whole phase skill to an Agent"
        ' (`hooks/guard_phase_delegation.py`) - it does not enforce the'
        ' one-task-per-dispatch rule in general (e.g. `"Implement tasks 1 and 2"`'
        " is outside its scope; the STOP rule above still governs that case by"
        " prose alone)."
    )
    work_skill_text = (PLUGIN / "skills" / "work" / "SKILL.md").read_text(
        encoding="utf-8"
    )
    work_skill = _paragraphs(PLUGIN / "skills" / "work" / "SKILL.md")
    assert f"{stop} {guard_note}" in work_skill
    assert sum(guard_note in p for p in work_skill) == 1
    # The STOP+note paragraph must stay inside its original section.
    section_start = work_skill_text.index("## CRITICAL: One Task at a Time")
    section_end = work_skill_text.index("##", section_start + 2)
    note_pos = work_skill_text.index(guard_note)
    assert section_start < note_pos < section_end
