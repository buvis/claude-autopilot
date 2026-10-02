---
catchup: skip
design: skip
default_model: sonnet
model_tier_rationale: prose-only; the exact sentence and its four insertion points are given below and prose-pin tests fail loudly on a miss
---

# Keep subagent test runs narrow

Source: `dev/local/notes/review-time-analysis-2026-09-30.md` R2 (narrow half).
The parallel-suite half is PRD 00233.

## Overview

### Problem Statement

`skills/work/SKILL.md` already says "Per-task verification runs only the
tests Tess wrote in step 2.7, not the full project suite. The full suite runs
once at the end." The subagents never receive that rule.

- Devon's template asks for a generic `Test runner command: {e.g. npm test,
  pytest, cargo test}`.
- Tess's template (`tess-prompt.md`) and Ivan's persona (`agents/ivan.md`)
  only give a timeout for "a full suite".

The 2026-09-27 to 09-30 run shows the cost:
- At least 72 full `cli` suite or `release-checks` runs, about 4 min each,
  roughly 4.8 h in total.
- Devon ran the whole directory once per exploit ("Run the full cli test
  suite with exploit 1 in place").
- Tess and Ivan ran it "to check for collateral damage".
- Several runs only re-read a number: "Rerun cli suite for the final count
  line", "Re-run release-checks capturing its exit code".

### Target Users

The per-task subagents (Tess, Devon, Ivan) in unattended batches.

### Success Metrics

- `uv run --no-project --with pytest python -m pytest -q skills/work/scripts/test_narrow_runs_prose.py`
  green; every existing work-skill prose test green (in particular the
  tool-discipline parity tests, which this PRD must not disturb).
- `bash dev/bin/release-checks` green.
- Post-release signal: in the next batch's `last-session.log`, no `⟨Devon⟩`,
  `⟨Tess⟩` or `⟨Ivan⟩` Bash call runs a whole test directory or
  `release-checks`.

## Functional Decomposition

### Capability: Subagents run only their task's tests

#### Feature: One narrow-run sentence in every subagent prompt
- **Description**: each subagent prompt states the narrow-run rule once.
- **Inputs**: none.
- **Outputs**: prose.
- **Behavior**: the sentence below (NARROW) is added verbatim, as its own
  paragraph, directly after the existing tool-discipline paragraph (the one
  beginning "Read every file before your first Edit to it.") in
  `skills/work/references/tess-prompt.md` and `agents/ivan.md`. The
  tool-discipline paragraph itself is NOT edited, because other tests pin it
  byte-identical across files. NARROW:
  "Run only the test files this task names (the tests you wrote, or the
  failing tests in your prompt), with `-q --tb=line`. Never run a whole test
  directory or `dev/bin/release-checks`: the orchestrator runs the full suite
  once, after every task. Read the pass count and exit code from that one
  run; never re-run a suite to recover a number."

#### Feature: Devon's runner is the task's test files
- **Description**: Devon verifies each exploit against the task's tests
  only.
- **Inputs**: the task's test file paths.
- **Outputs**: prose in `skills/work/references/adversarial-test-prompt.md`.
- **Behavior**: in the Devon template, the line `Test runner command: {e.g.
  npm test, pytest, cargo test}` becomes `Test runner command: {the command
  that runs ONLY this task's test files, e.g. uv run --no-project --with
  pytest python -m pytest -q --tb=line <the task's test files>; never a whole
  test directory}`. The Context Selection row `| Test runner command | So
  Devon can verify exploits |` becomes `| Test runner command (the task's test
  files only) | So Devon can verify exploits without a full-suite run per
  attempt |`. The template's Rules list gains, as its last rule: "Run only
  the test runner command above, once per exploit; never a whole test
  directory."

#### Feature: The orchestrator's rule names rework mode
- **Description**: the one-line rule in `work/SKILL.md` covers rework
  sessions too.
- **Inputs**: none.
- **Outputs**: prose.
- **Behavior**: `skills/work/SKILL.md`, after the sentence "The full suite
  runs once at the end (why: `references/design-rationale.md` § narrow
  verification).", adds: "This holds in rework mode and for every subagent
  prompt (Tess, Devon, Ivan): each carries the same narrow-run sentence."

## Structural Decomposition

### Repository Structure

```
skills/work/references/tess-prompt.md             # Maps to: One narrow-run sentence
agents/ivan.md                                    # Maps to: One narrow-run sentence
skills/work/references/adversarial-test-prompt.md # Maps to: Devon's runner
skills/work/SKILL.md                              # Maps to: The orchestrator's rule
skills/work/scripts/test_narrow_runs_prose.py     # Maps to: Test Strategy
dev/bin/release-checks                            # the new prose test
CHANGELOG.md
```

### Module: work prompts
- **Maps to capability**: Subagents run only their task's tests
- **Responsibility**: carry the narrow-run rule to every subagent.
- **Exports**: the NARROW sentence (the prose test holds its literal as a
  constant and checks each file against it).

## Dependency Graph

### Foundation Layer (Phase 0)
No dependencies - built first.

- **prompt prose (tess-prompt, ivan, adversarial, work SKILL)**: prose only.

### Core Layer (Phase 1)
- **prose test and release wiring**: Depends on [prompt prose].

### Integration Layer (Phase 2)
- **CHANGELOG**: Depends on [prose test].

## Implementation Phases

### Phase 0: Foundation
**Goal**: every prompt carries the rule.

**Tasks**:
- [ ] Add NARROW to `tess-prompt.md` and `agents/ivan.md`, rewrite Devon's
  runner line, Context Selection row and last rule, and add the `work/SKILL.md`
  sentence (no deps) - Acceptance: `rg -c "never re-run a suite to recover a
  number" skills/work/references/tess-prompt.md agents/ivan.md` prints 1 per
  file; `rg -c "runs ONLY this task's test files"
  skills/work/references/adversarial-test-prompt.md` prints 1; every existing
  test under `skills/work/scripts/` green (the tool-discipline paragraph is
  unchanged).

**Exit Criteria**: greps as stated; the work-skill suite green.

### Phase 1: Core
**Goal**: the rule is pinned.

**Tasks**:
- [ ] Add `skills/work/scripts/test_narrow_runs_prose.py` and list it in
  `dev/bin/release-checks` in the work-skill prose block (depends on:
  Phase 0) - Acceptance:
  `test_narrow_runs_prose.py::test_tess_and_ivan_carry_the_narrow_sentence`
  (NARROW appears verbatim in both files, directly after the paragraph
  beginning "Read every file before your first Edit to it."),
  `::test_devon_runner_is_the_tasks_test_files` (the template line contains
  "runs ONLY this task's test files" and no longer contains "e.g. npm test,
  pytest, cargo test"),
  `::test_devon_rules_forbid_a_directory_run`,
  `::test_work_skill_names_rework_mode` green.

**Exit Criteria**: the new file green.

### Phase 2: Integration
**Goal**: shipped.

**Tasks**:
- [ ] `CHANGELOG.md` `[Unreleased]` `### Changed`: `**work**` line saying
  Tess, Devon and Ivan run only their task's tests and never re-run a suite
  for a count (depends on: Phase 1) - Acceptance: `bash dev/bin/release-checks`
  green.

**Exit Criteria**: `release-checks` green.

## Test Strategy

### Critical Scenarios
- **Happy path**: a rendered Tess prompt (`render_prompt.py` over
  `tess-prompt.md`) contains NARROW once.
- **Edge case**: the tool-discipline parity tests still pass, because the
  shared paragraph is untouched.
- **Error case**: a later edit that deletes NARROW from one file fails
  `test_tess_and_ivan_carry_the_narrow_sentence` naming that file.

## Risks

- **Collateral breakage found later**: a change that breaks an untouched
  test surfaces at step 7's single full-suite run instead of inside the task,
  so the fix costs one more gate-failure dispatch. How often that happens is
  not measured (guess: rarely, since each task's slice is narrow), against a
  measured 4.8 h of per-task full runs.
