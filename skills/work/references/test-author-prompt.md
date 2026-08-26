# Test Author Prompt (Tess)

Tess writes tests from requirements. She has NOT seen and must NOT think about implementation.

## Prompt Template

The prompt template lives in `work/references/tess-prompt.md` (single source
of truth, registry-shaped single-brace placeholders — `render_prompt.py`
consumes it directly; see `agent-registry.md` for the placeholder table).

## Context Selection

When building Tess's prompt, include:

| Include | Why |
|---------|-----|
| Task description + acceptance criteria | The spec Tess tests against |
| Public types/interfaces | So Tess knows the API surface |
| One sample test file | So Tess follows project conventions |
| Test framework config | So imports and assertions are correct |
| `<dir>/tests/HARNESS_CONTRACT.md`, when it exists | The project's own harness rules, for each Contract path `<dir>/<file>` the task touches |

| Exclude | Why |
|---------|-----|
| Architecture docs | Would leak implementation thinking |
| AGENTS.md internals | Same - Tess doesn't need to know how things are built |
| Implementation files | Defeats the entire purpose |
| "How to build this" guidance | Tess is a test author, not an implementor |

Moved verbatim out of `SKILL.md` step 2.7 (PRD 00119-v2) — the two lists the
step used to spell out inline. **Read this section before the first Tess
dispatch of a batch.**

**Tess receives:**
- Task description and acceptance criteria
- The **exact file paths** the task touches — spelled **absolute** — and the **exact symbol names** to test, taken from the plan task — not "find the relevant file"
- Public interfaces/types relevant to the task
- The project's test-harness contract when one exists (PRD 00141): for each Contract path `<dir>/<file>`, `<dir>/tests/HARNESS_CONTRACT.md` joins the `PUBLIC_INTERFACES` `--set-cmd`, once per distinct file. No such file adds nothing — this is a convention, not a requirement on the project. It exists because a harness can make a test pass for reasons the test author cannot guess from requirements (PRD 00141's case: a `capture_main` helper that installs its own `sys.stdin`, so a "marker checked before stdin" test would have passed against the old code too). The contract states harness rules, never implementation
- Existing test patterns (one sample test file from the project)
- Test framework and conventions used

**Tess does NOT receive:**
- Implementation strategy or architecture docs (loaded in step 2.5 for the main session and Ivan only)
- "How to build this" context
- Access to modify non-test files

The stdout integer from step 2.7's render call **is** the Subagent Dispatch Budget measurement — no separate `wc -c`. `tess-prompt.md` bakes in the read-only-scope instruction, the dispatch prologue, and the Assumptions footer permanently (mirroring `ivan.md`), so nothing further needs adding to the prompt by hand — open-ended discovery is where subagents burn turns and stall, and keeping Tess scoped to the listed files/symbols is the template's job now. Dispatch the Agent tool with the file at `dev/local/tmp/dispatch-tess-<task-id>.txt` as the prompt source. The template also embeds Simplicity/Think-Before-Coding/Surgical rules to prevent Tess from writing speculative tests or silently assuming input shape.

## Quality gate (step 2.8)

Moved verbatim out of `SKILL.md` step 2.8 (PRD 00119-v2). SKILL.md keeps the
gate rule and the total-Tess budget; the rubric and the retry render live here.
**Read this section before running the gate on Tess's first test file.**

Before committing Tess's tests, review them in the main session against this checklist:

1. **Behavior names?** Each test name describes a behavior ("rejects empty email"), not an implementation detail ("calls validateEmail")
2. **Real assertions?** Assertions check outputs/effects, not mock internals
3. **Edge cases?** Empty, null, boundary, error, and concurrent cases covered where relevant
4. **No tautologies?** Tests don't just restate what the code obviously does

If any check fails, dispatch Tess again with specific feedback about what's weak. Render the retry the same way as the initial dispatch — never author it by hand:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/skills/work/scripts/render_prompt.py ${CLAUDE_PLUGIN_ROOT}/skills/work/references/tess-retry-prompt.md \
  --out dev/local/tmp/dispatch-tess-<task-id>-retry-<n>.txt \
  --set-file QUALITY_FEEDBACK=dev/local/tmp/tess-<task-id>-gate-<n>.txt \
  --set-file TASK_DESCRIPTION=<the same scratch file step 2.7 used> \
  --set-file TASK_ACCEPTANCE_CRITERIA=dev/local/tmp/tess-<task-id>-acceptance.txt
```

Write the gate findings (one per line) to the `QUALITY_FEEDBACK` scratch file with the Write tool. Max 2 quality gate retries.

## Retry Prompt (after quality gate failure)

The retry template lives in `work/references/tess-retry-prompt.md` (single
source of truth, registry-shaped single-brace placeholders — `render_prompt.py`
consumes it directly; see `agent-registry.md` for the placeholder table). It
takes `{QUALITY_FEEDBACK}`, `{TASK_DESCRIPTION}` and
`{TASK_ACCEPTANCE_CRITERIA}`, and bakes in the same fixed guards the initial
template carries (read-only scope, 100K abort line, dispatch prologue,
ASSUMPTIONS footer).

`{QUALITY_FEEDBACK}` is the step-2.8 gate's own findings, one per line, e.g.:

- Test "handles validation" is too vague. Name the specific behavior.
- Test 3 would pass with a function that always returns true. Add constraints.
- No edge case for empty input.
