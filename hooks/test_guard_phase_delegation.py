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


def _self_referential(p: Path) -> bool:
    # This PRD's own dispatch prompts (Tess, Devon, Ivan, their retries)
    # quote the denied phrases verbatim ("guard_phase_delegation") to
    # specify the hook's contract - not a real delegation attempt, so they
    # are excluded rather than counted as false positives. Content-only
    # check: every file this ever excluded (dispatch-tess-1[.txt/-strengthen],
    # dispatch-ivan-1, dispatch-tess-3, dispatch-ivan-3) names the module
    # literally, so no hard-coded filename list is needed.
    return "guard_phase_delegation" in p.read_text(encoding="utf-8")


def _allow_corpus() -> list[Path]:
    real = sorted(p for p in CORPUS.glob("dispatch-*.txt") if not _self_referential(p))
    return real or sorted((FIXTURES / "allowed").glob("*.txt"))


def _denied() -> list[Path]:
    fixtures = sorted((FIXTURES / "denied").glob("*.txt"))
    assert len(fixtures) == 4, fixtures
    return fixtures


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
    assert len(samples) == 24
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


_REVIEWER_FIXTURES = sorted((FIXTURES / "allowed").glob("reviewer-*.txt"))


@pytest.mark.parametrize("prompt_file", _REVIEWER_FIXTURES, ids=lambda p: p.name)
def test_review_roster_prompts_are_allowed(prompt_file: Path) -> None:
    # The PRD's allow set explicitly names "the review roster's Alice,
    # Blake and Watcher prompts" (no Watcher prompt exists in the corpus to
    # commit a sample of). These are real Alice/Blake/Carl review-cycle
    # prompts, committed so this half of the allow set has a durable gate
    # rather than relying on scratch docs/dev/tmp files.
    guard = _guard_module()
    prompt = prompt_file.read_text(encoding="utf-8")
    assert prompt.strip(), prompt_file.name
    assert guard.is_phase_delegation({"prompt": prompt, "description": ""}) is False


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


@pytest.mark.parametrize(
    "prompt",
    [
        "Does not run the work phase for PRD 300; implement task 2 only.",
        "This task doesn't invoke the design phase at all.",
        "We won't execute the autopilot:work skill here, just task 4.",
    ],
    ids=["does-not-run", "doesnt-invoke", "wont-execute"],
)
def test_negated_invocations_are_allowed(prompt: str) -> None:
    assert _guard_module().is_phase_delegation({"prompt": prompt}) is False


def test_negated_first_match_then_real_delegation_is_still_denied() -> None:
    # A negation in an earlier sentence must not suppress a real delegation
    # that follows it, beyond the negation window, in a later sentence.
    prompt = "Do not wait for me. Run the work phase for PRD 7."
    assert _guard_module().is_phase_delegation({"prompt": prompt}) is True


def test_negation_before_a_comma_does_not_hide_delegation() -> None:
    # A comma separates the negation "Never stop" from the delegation "run
    # the work phase" - the comma is a boundary, so the negation must not
    # suppress the match.
    prompt = "Never stop, run the work phase for PRD 7."
    assert _guard_module().is_phase_delegation({"prompt": prompt}) is True


def test_negation_in_an_earlier_clause_does_not_hide_delegation() -> None:
    # The negation "not now" is in an earlier sentence, separated by both a
    # semicolon and a period from the delegation - it must not suppress the
    # match.
    prompt = "OK; not now. Run the work phase for PRD 7."
    assert _guard_module().is_phase_delegation({"prompt": prompt}) is True


def test_direct_negation_still_allows() -> None:
    # The negation "Do not" is in the SAME clause immediately before the
    # delegation phrase, with no boundary between them - this must still
    # suppress the match.
    prompt = "Do not run the work phase."
    assert _guard_module().is_phase_delegation({"prompt": prompt}) is False


def test_comma_boundary_hides_leading_negation() -> None:
    # Measured: the last boundary in the window is the second comma, so the
    # leading "Do not" never reaches the match and this reads as a delegation.
    prompt = "Do not, under any circumstances, run the work phase."
    assert _guard_module().is_phase_delegation({"prompt": prompt}) is True


def _exempt_types() -> list[str]:
    # Derived from the guard's own frozenset, never a hand-copied list: a
    # persona added there must reach these tests, or the safety invariant below
    # is checked against the copy instead of against production.
    types = sorted(_guard_module()._READ_ONLY_REVIEWERS)
    assert types, "the guard's exemption set is empty"
    return types


@pytest.mark.parametrize("subagent_type", _exempt_types())
def test_reviewer_dispatch_quoting_the_guard_is_allowed(subagent_type: str) -> None:
    tool_input = {"subagent_type": subagent_type, "prompt": "run the work phase"}
    assert _guard_module().is_phase_delegation(tool_input) is False


def test_worker_dispatch_is_still_checked() -> None:
    tool_input = {"subagent_type": "autopilot:worker-sonnet", "prompt": "run the work phase"}
    assert _guard_module().is_phase_delegation(tool_input) is True


def test_bare_reviewer_name_is_still_checked() -> None:
    # Only the namespaced plugin personas are exempt; a bare `blake` is some
    # other agent of the same name and must still be checked.
    tool_input = {"subagent_type": "blake", "prompt": "run the work phase"}
    assert _guard_module().is_phase_delegation(tool_input) is True


def test_unhashable_subagent_type_fails_open() -> None:
    # A set-membership test on an unhashable value raises TypeError; the hook's
    # contract is to fail open on a malformed payload, never to crash. Fail open
    # here means "treat it as no subagent_type at all", so the verdict must equal
    # the one for the same payload with the key absent - not merely be a bool.
    guard = _guard_module()
    payload = {"prompt": "run the work phase"}
    assert guard.is_phase_delegation({**payload, "subagent_type": {"a": 1}}) is (
        guard.is_phase_delegation(payload)
    )


def test_every_exempt_reviewer_lacks_the_skill_tool() -> None:
    # Exempting a read-only reviewer from the delegation guard cannot be
    # exploited to delegate: none of the 13 personas can themselves invoke
    # the Skill tool (its persona file never grants it).
    agents_dir = HOOKS.parent / "agents"
    for subagent_type in _exempt_types():
        name = subagent_type.removeprefix("autopilot:")
        text = (agents_dir / f"{name}.md").read_text(encoding="utf-8")
        assert text.startswith("---\n"), name
        end = text.index("\n---", 4)
        frontmatter = text[4:end]
        tools_line = next(
            line for line in frontmatter.splitlines() if line.startswith("tools:")
        )
        tools = [t.strip() for t in tools_line.removeprefix("tools:").split(",")]
        assert "Skill" not in tools, (name, tools)


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
    # The predicate coerces a non-string prompt to "" (isinstance check,
    # no f-string coercion) and does not raise, so stderr is empty.
    assert result.stderr == ""


PLUGIN = HOOKS.parent


def test_hooks_json_registers_the_guard_on_agent() -> None:
    # Only the Agent-matcher registration is pinned here, not the shape of
    # any other PreToolUse entry - a future unrelated hook addition must
    # not break this test.
    assert GUARD.is_file()
    data = json.loads((HOOKS / "hooks.json").read_text(encoding="utf-8"))
    assert set(data) == {"hooks"}
    hooks = data["hooks"]
    pre = hooks["PreToolUse"]
    agent_entries = [e for e in pre if e.get("matcher") == "Agent"]
    assert len(agent_entries) == 1
    assert agent_entries[0] == {
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


def test_gate_prose_names_the_guard_in_phase_build() -> None:
    # Each gate states the selected-PRD/runs-until-done fact and the
    # Skill-tool rule ONCE, in one merged sentence pair - not the old
    # duplicated-imperative shape ("Invoke X with the Skill tool...Invoke X
    # with the selected PRD.").
    build_md = PLUGIN / "skills" / "run-autopilot" / "references" / "phase-build.md"
    paras = _paragraphs(build_md)
    plan_para = (
        "Invoke `/autopilot:plan-tasks` with the selected PRD, using the Skill"
        " tool in this session; never delegate planning to an Agent."
    )
    plan_next = "**PAUSE site - requirements clarification.**"
    work_para = (
        "Invoke `/autopilot:work` with the Skill tool in this session; never"
        " delegate work execution to an Agent. It runs until all tasks complete."
    )
    work_next = "While `/autopilot:work` runs"
    for para, next_text in ((plan_para, plan_next), (work_para, work_next)):
        matches = [p for p in paras if p == para]
        assert len(matches) == 1, para
        assert sum(1 for p in paras if para in p) == 1
        for banned in _BANNED_NEAR_GATE:
            assert banned not in para.lower(), (banned, para)
        idx = paras.index(para)
        assert next_text in paras[idx + 1], (next_text, paras[idx + 1])
        # Each sentence's imperative appears exactly once in the paragraph,
        # not twice (the duplication this test was written to catch).
        assert para.count("Invoke `/autopilot:") == 1, para
    text = build_md.read_text(encoding="utf-8")
    assert text.index("## Phase 2: Planning") < text.index(plan_para)
    assert text.index(plan_para) < text.index("## Phase 3: Work")


def test_gate_prose_names_the_guard_in_work_skill() -> None:
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
    skill_md = PLUGIN / "skills" / "work" / "SKILL.md"
    work_skill_text = skill_md.read_text(encoding="utf-8")
    work_skill = _paragraphs(skill_md)
    assert f"{stop} {guard_note}" in work_skill
    assert sum(guard_note in p for p in work_skill) == 1
    # The STOP+note paragraph must stay inside its original section.
    section_start = work_skill_text.index("## CRITICAL: One Task at a Time")
    section_end = work_skill_text.index("##", section_start + 2)
    note_pos = work_skill_text.index(guard_note)
    assert section_start < note_pos < section_end


def test_gate_prose_names_the_guard() -> None:
    # The PRD's Phase 1 acceptance test id names this single test; the
    # implementation split it into the two functions above to stay under
    # the 50-line function limit (commit a7c6416). This thin wrapper makes
    # the PRD's literal node-id runnable again without re-merging them.
    test_gate_prose_names_the_guard_in_phase_build()
    test_gate_prose_names_the_guard_in_work_skill()
