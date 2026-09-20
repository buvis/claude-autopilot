---
catchup: skip
design: skip
default_model: sonnet
model_tier_rationale: transcription - the two prose lines and the gate invocation are given verbatim; a wrong edit fails the named prose tests
---

# Carry style limits into the Tess prompt and gate the test commit

Source: `dev/local/notes/autoclaude-inefficiencies-2026-09-13.md` finding 7
(measured 2026-09-13). Advisory discovery gate skipped: the change
is two prose lines and one gate call, all sourced from existing files.

## Problem

`skills/work/scripts/check_style_limits.py` flags functions over 50 lines and
files over 800 lines, but only at step 5.65, after Ivan has implemented.
`skills/work/references/tess-prompt.md` never tells Tess the limits, so she
writes one large test file, the gate fails on Ivan's commit, and an extra Ivan
dispatch splits the test file: 19 minutes and one more Pat run on
claude-autopilot task 7 (session `8f7c779f`, "Ivan splits the oversized test
file"), 13 minutes on agent-skills task 10 (commit `066e05b`, "split the engine
test file under the file line cap"). Every opus task with a big test surface
pays it.

## Solution

Tell Tess the limits up front, and run the style gate on the test files at
step 2.8 so a violation is fixed by a Tess retry (cheap, tests-only) instead of
an Ivan style-fix dispatch after implementation. The step-5.65 gate is
unchanged; it still catches Ivan's own violations.

## Requirements

### Must have
- `tess-prompt.md` rule 12, verbatim: `12. SIZE LIMITS: keep every test
  function under 50 lines and every test file under 800 lines; split by
  behavior into sibling files named after the test module (for example
  test_events_completion.py, test_events_usage.py) before you exceed either.`
- `tess-retry-prompt.md` accepts the style gate's violation lines as feedback
  the same way it accepts the quality-gate feedback (no new placeholder; the
  feedback text carries them).
- Work SKILL.md step 2.8 gains, after the four-check rubric sentence: `Then run
  the step-5.65 gate over the test files only - python3
  ${CLAUDE_PLUGIN_ROOT}/skills/work/scripts/check_style_limits.py --diff
  dev/local/tmp/test-diff-<task-id>.txt <each new or changed test file as an
  absolute path> - where the diff is git diff --no-index /dev/null <file> per
  untracked file plus git diff <task_base_sha> -- <tracked test files>. Exit 1
  is a quality-gate failure: feed the violation lines to the Tess retry. It
  counts toward the two quality-gate retries.`
- A prose test `skills/work/scripts/test_tess_size_limits_prose.py` pins rule
  12's two numbers and the step-2.8 invocation sentence.

### Nice to have
- `references/test-author-prompt.md` § Context Selection notes that the limits
  are baked into the prompt, so the orchestrator never adds them by hand.

## Implementation

### Module: tess-prompt
- **Location**: `skills/work/references/tess-prompt.md`, `tess-retry-prompt.md`
- **Responsibility**: the rules Tess writes under
- **Exports**: none (prose)

### Module: work SKILL step 2.8
- **Location**: `skills/work/SKILL.md`
- **Responsibility**: the test quality gate
- **Exports**: none (prose pinned by `test_tess_size_limits_prose.py`)

### Dependencies
- tess-prompt: No dependencies (foundation)
- work SKILL step 2.8: Depends on [tess-prompt]

## Tasks

### Phase 0: Foundation
- [ ] Add rule 12 to `tess-prompt.md` and the retry-feedback sentence to
  `tess-retry-prompt.md` - `test_tess_size_limits_prose.py::test_tess_prompt_states_both_limits`
  finds `under 50 lines` and `under 800 lines` in rule 12.

### Phase 1: Core
- [ ] Add the step-2.8 gate sentence (depends on: Phase 0) -
  `test_tess_size_limits_prose.py::test_quality_gate_runs_the_style_script_on_test_files`
  finds the `check_style_limits.py` invocation between the `### 2.8` and
  `### 2.85` headings; `test_style_gate_prose.py` stays green.
- [ ] CHANGELOG `### Changed` entry under `**work**` (depends on: Phase 1) -
  `rg -c "Tess.*50 lines|test files.*style gate" CHANGELOG.md` returns 1 or
  more.

## Success Criteria

- `uv run --no-project --with pytest python -m pytest -q skills/work/scripts/test_tess_size_limits_prose.py skills/work/scripts/test_style_gate_prose.py`
  green.
- Post-release signal, not judged in-session: the next batch's
  `dispatch-metrics.jsonl` has no `ivan` row whose `detail` contains
  `split` for a file Tess created in the same task.
