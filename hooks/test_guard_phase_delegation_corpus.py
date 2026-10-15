"""PRD 00307: the recorded corpus dispatches the guard must allow.

Split out of test_guard_phase_delegation_citations.py: the recovered payloads
are ~17 KB of verbatim literals, and keeping them beside the behaviour tests
pushed that file past the 800-line limit. The rule they pin is one rule.
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

import pytest

HOOKS = Path(__file__).resolve().parent


def _find(
    prompt: str,
    subagent_type: str | None = "general-purpose",
    description: str | None = None,
) -> str | None:
    sys.path.insert(0, str(HOOKS))
    tool_input = {"prompt": prompt}
    if subagent_type is not None:
        tool_input["subagent_type"] = subagent_type
    if description is not None:
        tool_input["description"] = description
    return importlib.import_module("guard_phase_delegation").find_phase_delegation(
        tool_input
    )


# The six corpus dispatches PRD 00307 replays, recovered verbatim from the
# session transcripts by tool-use id. Only two still exist: measured
# 2026-10-15, twice and independently, by running the extraction
# dev/bin/replay_delegation_guard.py:_dispatches performs over every *.jsonl
# under ~/.claude/projects (Agent tool_use records / any tool_use records):
#   toolu_011UqbqFtUDPuSeCiLLgMvEg  1 / 1  recovered, below
#   toolu_013ePUKbLDE7DLnbnGmgszzR  1 / 1  recovered, below
#   toolu_015DM18ubZLJZbA65ozvuw8c  0 / 0  unrecoverable
#   toolu_013NAWvgMnP4WatpZDVyiNAa  0 / 0  unrecoverable
#   toolu_01DAQSaS3uAph2VZnfn5NC9d  0 / 0  unrecoverable
#   toolu_019nCz3WRsAZSwdaHb9itXiT  0 / 0  unrecoverable
# The four unrecoverable payloads are left out, not replaced: a sentence
# invented around the span the guard quoted is the defect this fixture
# exists to kill, since such a prompt is allowed in isolation whatever the
# guard does with the real one.
_RECORDED_CORPUS = (
    (
        "toolu_011UqbqFtUDPuSeCiLLgMvEg",
        {
            "subagent_type": "autopilot:worker-opus",
            "description": "Implement task 6 tests",
            "prompt": (
                "You are Ivan, the implementor. Make all failing tests pass. Tests ARE the\n"
                "spec. Do NOT modify test files unless your allowlist below names them (a\n"
                "test-only task lists them on purpose). Do NOT read the task's acceptance criteria \u2014\n"
                "none are provided to you on purpose.\n"
                "\n"
                "## Failing tests\n"
                "\n"
                "TASK 6: Exempt agoge personas and quote the match in a per-type deny message.\n"
                "\n"
                "IMPORTANT SCOPE NOTE. The production code for this task ALREADY LANDED with\n"
                "task 5: `/Users/bob/git/src/github.com/buvis/claude-autopilot/hooks/guard_phase_delegation.py`\n"
                "already carries `_AGOGE_PREFIX`, the `startswith(_AGOGE_PREFIX)` exemption as\n"
                "step 0 of `find_phase_delegation`, and `_deny_message`. The orchestrator\n"
                "probed all eight dispatch cases against the current tree and every one of them\n"
                "already produces the exact verdict and the exact message the acceptance\n"
                "criteria below demand. So your job is ONLY to pin that behavior with a new\n"
                "test module and register it in the release gate. DO NOT modify\n"
                "`hooks/guard_phase_delegation.py` - it is not in your allowlist. If a test you\n"
                "write fails, the test is wrong, not the guard: re-read the guard and fix your\n"
                "test.\n"
                "\n"
                "WHAT TO BUILD\n"
                "\n"
                "1. Create `/Users/bob/git/src/github.com/buvis/claude-autopilot/hooks/test_guard_phase_delegation_dispatch.py`\n"
                "   with exactly these four tests. Every case uses the one prompt\n"
                "   `Run the work phase for PRD 00300.` (verbatim, including the period).\n"
                "   Run the guard as a SUBPROCESS with a stdin JSON payload, exactly as\n"
                "   `hooks/test_guard_phase_delegation_replay.py` already does - copy its\n"
                "   `_run` and payload helpers' shape (env\n"
                "   `{\"PATH\": \"/usr/bin:/bin\", \"HOME\": str(Path.home()), \"_AUTOPILOT_LOOP\": \"4242\"}`,\n"
                "   `{\"session_id\": ..., \"tool_name\": \"Agent\", \"tool_input\": {...}}`). Reuse\n"
                "   the `REASON` constant text from `hooks/test_guard_phase_delegation.py`\n"
                "   line 33: `\"hooks/guard_phase_delegation.py denied this Agent call.\"`\n"
                "\n"
                "   - `test_agoge_personas_are_exempt`: for each of\n"
                "     `agoge:walter`, `agoge:wendy`, `agoge:trudy`, `agoge:heidi`,\n"
                "     `agoge:peggy`, `agoge:olivia`, `agoge:judy` the guard exits 0.\n"
                "   - `test_agoge_lookalike_types_are_still_checked`: for each of\n"
                "     `agoge`, `walter`, `agoge-walter`, `xagoge:walter` the guard exits 2.\n"
                "   - `test_per_task_persona_refusal_says_rephrase_and_quotes_the_match`: for\n"
                "     each of `autopilot:ivan`, `autopilot:tess`, `autopilot:devon`,\n"
                "     `autopilot:worker-sonnet`, `autopilot:worker-opus` the guard exits 2 and\n"
                "     its stderr holds `rephrase that sentence`, holds the quoted span\n"
                "     `\"Run the work phase for PRD 0\"` (with the double quotes around it),\n"
                "     holds the REASON line, and does NOT contain the word `Matched`.\n"
                "   - `test_other_refusals_keep_the_skill_tool_text_and_quote_the_match`: for\n"
                "     `general-purpose`, `Explore`, and a payload with NO `subagent_type` key\n"
                "     at all, the guard exits 2 and its stderr holds\n"
                "     `with the Skill tool in THIS session` and\n"
                "     `Matched: \"Run the work phase for PRD 0\"` and the REASON line.\n"
                "\n"
                "   Prefer `pytest.mark.parametrize` over in-test for-loops so each persona is\n"
                "   its own reported case. Name each test exactly as given above. The module\n"
                "   needs a short docstring saying what it pins and why the one shared prompt\n"
                "   is used.\n"
                "\n"
                "2. Register the new module in\n"
                "   `/Users/bob/git/src/github.com/buvis/claude-autopilot/dev/bin/release-checks`:\n"
                "   add `hooks/test_guard_phase_delegation_dispatch.py` to the existing\n"
                "   `[checks] hook registration` block (lines 128-138), as one more\n"
                "   backslash-continued line beside the other four\n"
                "   `test_guard_phase_delegation*` entries. Keep the surrounding style\n"
                "   identical; change nothing else in that file.\n"
                "\n"
                "Verify: `python3 -m pytest hooks/test_guard_phase_delegation_dispatch.py hooks/test_guard_phase_delegation_replay.py -q`\n"
                "must be all green, including task 2's verdict test. Run ONLY that command for\n"
                "verification - not the full project suite, not the whole hooks directory.\n"
                "\n"
                "## Architecture context\n"
                "\n"
                "See `/Users/bob/git/src/github.com/buvis/claude-autopilot/hooks/test_guard_phase_delegation_replay.py`\n"
                "for the exact subprocess-and-stdin house style to copy.\n"
                "\n"
                "## Files you may read and modify\n"
                "\n"
                "/Users/bob/git/src/github.com/buvis/claude-autopilot/hooks/test_guard_phase_delegation_dispatch.py\n"
                "/Users/bob/git/src/github.com/buvis/claude-autopilot/dev/bin/release-checks\n"
                "\n"
                "You may also READ (never modify) these three, which you need for the exact\n"
                "behavior and the house test style:\n"
                "/Users/bob/git/src/github.com/buvis/claude-autopilot/hooks/guard_phase_delegation.py\n"
                "/Users/bob/git/src/github.com/buvis/claude-autopilot/hooks/test_guard_phase_delegation.py\n"
                "/Users/bob/git/src/github.com/buvis/claude-autopilot/hooks/test_guard_phase_delegation_replay.py\n"
                "\n"
                "Read only the files listed above. If a file or symbol you need is not\n"
                "listed, stop and report it as a blocker \u2014 do not run broad `rg` sweeps to\n"
                "discover scope.\n"
                "\n"
                "### Code quality rules (mandatory)\n"
                "\n"
                "Follow these four rules. They override any instinct to \"improve\" the code\n"
                "beyond what the failing tests require.\n"
                "\n"
                "**1. Think before coding.** Re-read the task and the failing tests. If scope,\n"
                "data shape, target file, or success criteria are ambiguous - more than one\n"
                "reasonable implementation would pass the tests differently - STOP and report\n"
                "the ambiguity as a blocker. Do not guess and proceed.\n"
                "\n"
                "**2. Simplicity.** Write the simplest code that makes the failing tests pass.\n"
                "\n"
                "- No abstractions, helpers, or interfaces built for a single caller.\n"
                "- No error handling, fallbacks, or validation for inputs the tests never\n"
                "  exercise. Validate at real system boundaries only.\n"
                "- No features, options, or configuration the task did not ask for.\n"
                "- If your draft runs long and the same behavior fits in far fewer lines,\n"
                "  rewrite it before returning.\n"
                "\n"
                "**3. Surgical changes.** Touch only what the task requires.\n"
                "\n"
                "- Do not refactor, reformat, or \"improve\" code outside the change.\n"
                "- Match the surrounding style even if you would write it differently.\n"
                "- Remove imports, variables, and functions that YOUR change orphaned. Do not\n"
                "  delete pre-existing dead code - mention it instead.\n"
                "- Every changed line must trace to the task or a failing test.\n"
                "\n"
                "**4. Goal-driven.** The failing tests are the spec. Make them pass - do not\n"
                "modify them, do not weaken them, do not add tests. If a test looks wrong,\n"
                "report it as a blocker rather than changing it.\n"
                "\n"
                "Abort and report if you read more than 100K of total input. Return the\n"
                "partial result and an abort_reason: context_overrun field.\n"
                "\n"
                "Read every file before your first Edit to it. Never call bash `head`,\n"
                "`tail`, `cat`, `grep`, or `find` - a hook blocks them. Use the Read tool\n"
                "(offset/limit), `rg`, or `rg --files` instead. Never combine an inspection\n"
                "(read, list, search, diff) with a test, lint or build invocation in one Bash\n"
                "call - run them as two calls, because a combined command has two ways to hang\n"
                "and one exit code. Pass an explicit `timeout` on every Bash call: 60000 ms for\n"
                "an inspection, 300000 ms for a lint run or a narrow test run, 600000 ms for a\n"
                "full suite or a full build.\n"
                "\n"
                "Run only the test files this task names (the tests you wrote, or the\n"
                "failing tests in your prompt), with `-q --tb=line`. Never run a whole test\n"
                "directory or `dev/bin/release-checks`: the orchestrator runs the full suite\n"
                "once, after every task. Read the pass count and exit code from that one\n"
                "run; never re-run a suite to recover a number.\n"
                "\n"
                "End your report with `ASSUMPTIONS:` - one line per assumption you made\n"
                "where the task, tests, or listed files were silent (guessed interface, data\n"
                "shape, resolved ambiguity, unstated behavior). Write `ASSUMPTIONS: none` if\n"
                "you made none.\n"
                "\n"
                "Also end your report with `FILES_TOUCHED:` - one line per file you created\n"
                "or modified, path relative to the repo root. Write `FILES_TOUCHED: none` if\n"
                "you changed no files."
            ),
        },
    ),
    (
        "toolu_013ePUKbLDE7DLnbnGmgszzR",
        {
            "subagent_type": "general-purpose",
            "description": "Tess: write tests for stub_text/review_paths",
            "prompt": (
                "You are writing tests for a feature. You have NOT seen any implementation and must NOT think about how to implement it.\n"
                "\n"
                "Task: Add stub_text and review_paths with their tests\n"
                "\n"
                "\n"
                "Description:\n"
                "Target module (does not exist yet \u2014 you are writing tests against it first, TDD-style): skills/run-autopilot/cli/wave_review.py\n"
                "Target symbols: stub_text(wave: dict) -> str, review_paths(wave: dict) -> list[str]\n"
                "Test file to write/extend: skills/run-autopilot/cli/test_wave_review.py (new file; no new fixture module \u2014 import _repo/_planned/_FakeSpawn from skills/run-autopilot/cli/test_wave_launch.py and _launched/_checks_pass from skills/run-autopilot/cli/test_wave_assemble.py only if you actually need them; these two functions are pure and likely need only hand-built `wave` dicts, no git/tmp_path fixtures).\n"
                "\n"
                "stub_text(wave: dict) -> str\n"
                "Pure. Renders the assembly stub PRD body from wave[\"assembly\"] and wave[\"lanes\"]. Frontmatter block (exactly these five key: value pairs, each on its own line inside a --- delimited YAML block at the top of the returned text):\n"
                "    catchup: skip\n"
                "    design: skip\n"
                "    rework_cap: 2\n"
                "    default_model: sonnet\n"
                "    model_tier_rationale: fixes to conflict resolutions and lane interactions found by the assembly review\n"
                "\n"
                "Body sections, in order, after the frontmatter:\n"
                "  # Wave <wave[\"id\"]> assembly\n"
                "  ## Overview\n"
                "    - one line per merged lane: \"- <lane name> (<lane prds, comma-joined>)\"\n"
                "    - \"Diff range: <wave['base_sha']>..<wave['assembly']['head_sha']>\"\n"
                "    - \"Diff scope:\" followed by one review_paths(wave) entry per line\n"
                "  ## Functional Decomposition\n"
                "    ### Capability: Assembly\n"
                "    #### Feature: Lane merges\n"
                "    - Description / Inputs / Outputs / Behavior naming each merged lane (wave[\"assembly\"][\"merged\"]) and its keep-both resolutions, read from that lane's `integrator_notes` list (wave.py's optional per-lane field; empty list -> \"no keep-both resolutions recorded\")\n"
                "  ## Implementation Phases\n"
                "    ### Phase 0: Assembly\n"
                "    - \"- [x] Merge lane <name> (<prds>) - Acceptance: release-checks green\" one per entry in wave[\"assembly\"][\"merged\"]\n"
                "  ## Test Strategy\n"
                "    - \"bash dev/bin/release-checks\"\n"
                "    - one line per merged lane naming its PRDs by basename, e.g. \"- See <prd basename>'s own Test Strategy\" (stub_text takes only wave and stays pure \u2014 it does not read any PRD file to extract its Success Metrics text; wave[\"lanes\"][*][\"prds\"] already names every PRD by basename)\n"
                "\n"
                "Raises ValueError if wave[\"assembly\"] is absent (review_paths and stub_text are only ever called after an assemble() step that populates wave[\"assembly\"]).\n"
                "\n"
                "review_paths(wave: dict) -> list[str]\n"
                "Pure. Returns the sorted, de-duplicated union of:\n"
                "  - wave.WAVE_APPEND_ONLY (skills/run-autopilot/cli/wave.py:21, the tuple (\"CHANGELOG.md\", \"dev/bin/release-checks\")) \u2014 always included, unconditionally, regardless of how many lanes name them.\n"
                "  - every repo-relative path that appears in the `files` list of two or more entries in wave[\"lanes\"] \u2014 every lane, not only the merged ones (a lane that could not merge still counts if its files overlap another lane's). A lane missing `files` counts as an empty list.\n"
                "\n"
                "The `#### Feature:` heading, `### Phase 0:` heading and `- [x]` list-item lines must be literal substrings of the rendered PRD body \u2014 a downstream PRD parser (cli/frontmatter.parse and plan-tasks) looks for these exact markdown patterns.\n"
                "\n"
                "The frontmatter must parse cleanly through cli/frontmatter.parse (skills/run-autopilot/cli/frontmatter.py) with no warning \u2014 that module already exists in this repo; read it to understand the exact YAML shape it expects (delimited by --- lines at the very top of the file).\n"
                "\n"
                "\n"
                "Acceptance Criteria:\n"
                "- test_stub_prd_names_every_merged_lane_and_the_range\n"
                "- test_stub_prd_carries_the_headings_plan_tasks_parses (`#### Feature:`, `### Phase 0:`, `- [x]` items)\n"
                "- test_stub_frontmatter_is_the_five_pairs (the five pairs: catchup: skip, design: skip, rework_cap: 2, default_model: sonnet, model_tier_rationale: fixes to conflict resolutions and lane interactions found by the assembly review \u2014 parsed by cli/frontmatter.parse without a warning)\n"
                "- test_stub_prd_lists_the_diff_scope\n"
                "- test_review_paths_are_the_multi_lane_files_plus_append_only (lanes l1 and l2 both list cli/records.py, l1 alone lists cli/x.py: the result is CHANGELOG.md, cli/records.py, dev/bin/release-checks and never cli/x.py; a kept (unmerged) lane's files count too)\n"
                "- stub_text and review_paths are each under 50 lines (implementation size, not a test)\n"
                "\n"
                "\n"
                "Existing test patterns (follow these conventions) \u2014 from skills/run-autopilot/cli/test_wave_assemble.py (a sibling test file in the same directory, testing another pure/side-effecting wave module):\n"
                "```python\n"
                "#!/usr/bin/env python3\n"
                "\"\"\"Tests for cli/wave_assemble.py - keep_both and the assemble merge pass. ...\"\"\"\n"
                "\n"
                "from __future__ import annotations\n"
                "\n"
                "import json\n"
                "import re\n"
                "import subprocess\n"
                "from pathlib import Path\n"
                "\n"
                "import pytest\n"
                "\n"
                "from cli import wave, wave_assemble, wave_launch\n"
                "from cli.loop_testutil import _spawn_tagged_incumbent\n"
                "from cli.test_wave_docs import _claims, _sentences\n"
                "from cli.test_wave_launch import (\n"
                "    THREE_LANES,\n"
                "    _autopilot,\n"
                "    _dead_pid,\n"
                "    _FakeSpawn,\n"
                "    _git,\n"
                "    _repo,\n"
                ")\n"
                "\n"
                "\n"
                "def test_keep_both_keeps_both_sides_in_file_order() -> None:\n"
                "    ours_marker = \"<\" * 7 + \" HEAD\"\n"
                "    ...\n"
                "    assert wave_assemble.keep_both(text) == expected\n"
                "```\n"
                "(This is a real, already-shipped test file in the repo at skills/run-autopilot/cli/test_wave_assemble.py \u2014 read it directly for the full picture of naming, docstring, and fixture style if useful; you do not need any git/tmp_path fixtures for stub_text/review_paths since both are pure functions over hand-built dicts.)\n"
                "\n"
                "Public interfaces/types relevant to this task \u2014 skills/run-autopilot/cli/wave.py (read it directly; it defines WAVE_APPEND_ONLY = (\"CHANGELOG.md\", \"dev/bin/release-checks\") at module level, plus the Lane dataclass and WAVE_STATUSES).\n"
                "\n"
                "Test framework: pytest\n"
                "\n"
                "Rules:\n"
                "1. Write tests from requirements only. You are a USER of this API, not its builder.\n"
                "2. Each test name describes a behavior: \"rejects empty email\", \"returns 404 for missing user\"\n"
                "3. Assert on outputs, return values, side effects, and errors. Never assert on mock existence.\n"
                "4. Cover edge cases: empty input, null/undefined, boundary values, error conditions\n"
                "5. Use real code paths. Mock only external dependencies (network, filesystem, databases).\n"
                "6. For EACH test, ask yourself: \"What wrong implementation would still pass this?\" If easy to answer, add constraints.\n"
                "7. Do not write implementation code. Do not modify non-test files.\n"
                "8. Do not add test-only methods to production classes. Use test utilities instead.\n"
                "9. SIMPLICITY FIRST: Test only the behavior in the acceptance criteria. Do not add tests for features nobody asked for. If you write 20 tests when 6 cover the spec, cut back.\n"
                "10. THINK BEFORE CODING: If the acceptance criteria are ambiguous (unclear input shape, unstated error behavior, multiple valid interpretations), STOP and report the ambiguity instead of picking an interpretation silently.\n"
                "10a. NEVER INVENT A CONTRACT: If the task names a data structure (JSON object, API response, enum, config schema, record type) but does not pin its EXACT field names, enum values, or types, STOP and report it as a blocker. Do not invent a plausible schema and test against it \u2014 a self-consistent wrong contract is worse than a reported gap, because the implementer will build to your tests and the mistake survives until PRD-level review. Likewise for \"which kind of thing\" choices the task leaves open (e.g. which hook event, which file location). The task description must hand you the exact strings; if it does not, that is a blocker, not a judgement call.\n"
                "11. SURGICAL: Only create/modify test files. Match the existing test file's style (quote style, import order, assertion library, naming). Do not reformat sample files you were given for reference.\n"
                "12. SIZE LIMITS: keep every test function under 50 lines and every test file under 800 lines; split by behavior into sibling files named after the test module (for example test_events_completion.py, test_events_usage.py) before you exceed either.\n"
                "\n"
                "Do NOT:\n"
                "- Think about how to implement the feature\n"
                "- Read or reference implementation files\n"
                "- Write stubs, placeholders, or TODO comments\n"
                "- Mock internal modules (only mock external boundaries)\n"
                "- Create tests that just check a function exists or returns truthy\n"
                "\n"
                "Read only skills/run-autopilot/cli/wave.py, skills/run-autopilot/cli/frontmatter.py, skills/run-autopilot/cli/test_wave_assemble.py and skills/run-autopilot/cli/test_wave_launch.py as needed. If a file or symbol you need is not listed, stop and report it as a blocker \u2014 do not run broad `rg` sweeps to discover scope.\n"
                "\n"
                "Abort and report if you read more than 100K of total input. Return the partial result and an abort_reason: context_overrun field.\n"
                "\n"
                "Read every file before your first Edit to it. Never call bash `head`, `tail`, `cat`, `grep`, or `find` - a hook blocks them. Use the Read tool (offset/limit), `rg`, or `rg --files` instead. Never combine an inspection (read, list, search, diff) with a test, lint or build invocation in one Bash call - run them as two calls, because a combined command has two ways to hang and one exit code. Pass an explicit `timeout` on every Bash call: 60000 ms for an inspection, 300000 ms for a lint run or a narrow test run, 600000 ms for a full suite or a full build.\n"
                "\n"
                "End your report with `ASSUMPTIONS:` - one line per assumption you made where the task, tests, or listed files were silent (guessed interface, data shape, resolved ambiguity, unstated behavior). Write `ASSUMPTIONS: none` if you made none."
            ),
        },
    ),
)


@pytest.mark.parametrize(
    ("tool_use_id", "tool_input"),
    _RECORDED_CORPUS,
    ids=[tool_use_id for tool_use_id, _ in _RECORDED_CORPUS],
)
def test_every_recorded_corpus_dispatch_is_allowed(
    tool_use_id: str,
    tool_input: dict,
) -> None:
    span = _find(
        tool_input["prompt"],
        tool_input["subagent_type"],
        tool_input["description"],
    )
    assert span is None, f"{tool_use_id} refused on {span!r}"
