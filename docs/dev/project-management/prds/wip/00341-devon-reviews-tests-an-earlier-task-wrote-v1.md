---
design: skip
default_model: sonnet
model_tier_rationale: three prose sentences with their exact text and three additive prose-pin tests; nothing executable changes
---

# Devon reviews tests an earlier task wrote

Source: batch 202610161547 (cache 0.9.0). The dispatch ledger `docs/dev/project-management/autopilot/dispatch-metrics.jsonl` holds, for rows queued in the batch, 18 `ivan`, 10 `tess`, 11 `pat` and 1 `devon` row, against 9 opus attempts in `ledger/attempts.jsonl` for 00320-00322 plus 00324's opus tasks 2 and 3. In the batch before (2026-10-15) Devon ran on every opus task and found an exploit on 46 of 47 rounds.

## Problem

Step 2.7 of `/autopilot:work` (`Tess`, `skills/work/SKILL.md:207-213`) skips the test author for a test-only task, and step 2.9's tier gate (`skills/work/SKILL.md:250-256`) dispatches Devon only at `opus` and `fable`. A plan shaped as "Phase 0: red-first tests" (a test-only task, which the planner's test-slice rule pins to `sonnet`) followed by "Phase 1: implementation" (`opus`) runs Devon in neither task: the test task is below his tier, and the implementation task reaches step 2.9 with no tests Tess wrote in it, so the session skips him and stamps nothing. 00324 task 2 (2026-10-17, session 04bc5092) recorded `pipeline: "full"` with no `devon` dispatch row and no `devon` field. Every rework task Phase 6 creates has the same shape. The adversarial round the opus tier pays for disappears whenever a plan separates tests from implementation, which is the shape the PRD template asks for.

## Solution

Tests an earlier task of this plan committed are this task's tests for steps 2.9 and 2.95. Three sentences in `skills/work/SKILL.md`, exact text:

- Step 2.7, a new sentence after `**Skip for:** test-only, docs-only, or config-only tasks.` (`skills/work/SKILL.md:213`): `Skipping Tess here does not skip step 2.9 or 2.95: when this task's Contract names test files an earlier task of this plan committed, those files are this task's tests for both steps.`
- Step 2.9, a new paragraph after the prose-gate paragraph (`skills/work/SKILL.md:260`): `**Earlier-task tests.** When step 2.7 skipped Tess because an earlier task of this plan committed this task's tests, Devon still runs at `opus` and `fable` against those files: his test-runner command names them, and an exploit routes to Tess's one strengthen dispatch exactly as for tests written in this task. A plan that splits tests from implementation must not lose the adversarial round the implementation tier bought.`
- Step 2.95, the sentence `Implicitly skipped when step 2.7 was skipped (no new tests).` (`skills/work/SKILL.md:266`) becomes `Implicitly skipped when step 2.7 was skipped and no earlier task of this plan committed this task's tests (nothing to run).`

The prose gate, the once-per-task rule, the dispatch budget and the attempt stamps are unchanged: an earlier task's prose-pin files still skip Devon with `devon: skipped:prose`, and an exploit still stamps `devon: exploit_fixed`.

## Requirements

### Must have
- The three sentences above, verbatim, at the three anchors in `skills/work/SKILL.md`.
- Three fail-first tests in `skills/work/scripts/test_devon_round_prose.py` (registered under `[checks] work scripts remainder`, `dev/bin/release-checks:129`), using the file's existing `_section` helper: `test_devon_runs_on_tests_an_earlier_task_wrote` (the `### 2.9` section contains `**Earlier-task tests.**` and `still runs at `opus` and `fable` against those files`), `test_tess_skip_does_not_skip_devon` (the `### 2.7` section contains `does not skip step 2.9 or 2.95`), `test_red_check_runs_on_earlier_task_tests` (the `### 2.95` section contains `no earlier task of this plan committed this task's tests`).
- A CHANGELOG `[Unreleased]` Fixed entry under **work**: Devon runs on an opus task whose tests an earlier task of the plan wrote, so a tests-first plan keeps its adversarial round.

### Nice to have
- None.

## Implementation

### Module: work-skill-prose
- **Location**: `skills/work/SKILL.md` (steps 2.7, 2.9, 2.95)
- **Responsibility**: tests committed by an earlier task of the plan count as the task's tests for the Devon round and the red check
- **Exports**: none

### Module: devon-prose-tests
- **Location**: `skills/work/scripts/test_devon_round_prose.py`
- **Responsibility**: pin the three sentences inside their sections through `_section`
- **Exports**: none
- New symbols: `test_devon_runs_on_tests_an_earlier_task_wrote`, `test_tess_skip_does_not_skip_devon`, `test_red_check_runs_on_earlier_task_tests`

### Dependencies
- work-skill-prose: No dependencies (foundation)
- devon-prose-tests: Depends on [work-skill-prose]

## Tasks

### Phase 0: Foundation
- [ ] Add the three tests to `skills/work/scripts/test_devon_round_prose.py`. Premise: `rg -c "Earlier-task tests" skills/work/SKILL.md` prints 0 before the edit; a different count means the prose already moved and the task stops and reports. - Acceptance: `uv run --no-project --with pytest python -m pytest -q skills/work/scripts/test_devon_round_prose.py -k "earlier_task or tess_skip"` fails all three against the current `SKILL.md`.

### Phase 1: Core
- [ ] Make the three prose edits in `skills/work/SKILL.md` and add the CHANGELOG entry (depends on: Phase 0) - Acceptance: `uv run --no-project --with pytest python -m pytest -q skills/work/scripts/test_devon_round_prose.py` passes; `rg -c "Earlier-task tests" skills/work/SKILL.md` prints 1; `rg -n "work.*adversarial round" CHANGELOG.md` prints one line under `[Unreleased]`.

## Success Criteria

- The three prose-pin tests pass and the existing `test_step_2_9_runs_devon_once` still passes.
- Post-release signal: in the next batch, every opus task that follows a test-only task has a `devon` row in `docs/dev/project-management/autopilot/dispatch-metrics.jsonl` (`jq -s '[.[] | select(.kind=="devon")]'`) or a `devon: skipped:prose` stamp.
