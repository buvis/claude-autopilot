---
catchup: skip
design: skip
default_model: sonnet
model_tier_rationale: exact replacement strings given for every prose edit; one additive prose contract test with its assert strings listed
---

# Cap the adversarial test loop at one round

Source: discovery `dev/local/discovery/00177-cut-review-and-test-loop-overhead.md` (reviewed 2026-09-05), measured on task 2 of PRD 00015 in agent-skills, batch 202609050909.

## Overview

### Problem Statement

`skills/work/references/adversarial-test-prompt.md:18-19` lets the Tess/Devon loop run two strengthen rounds after Devon's first pass (three Devon dispatches, two strengthen-side Tess dispatches), and `skills/work/SKILL.md:242` budgets five Tess dispatches for the test-authoring phase. Task 2 of PRD 00015 spent 20 minutes on that loop (tess 09:44, devon 09:47, tess 09:51, devon 09:55, tess 09:59, devon 10:03) before the implementor ran, and still shipped a test gap (a present, non-list `entries`) that codex found in one pass at the cycle review. Autopilot 0.5.0's `detect_tautological_tests.py` now runs in the step-2.8 gate and covers part of what a second Devon round hunts, so the second round buys little.

### Target Users

Every `opus`- and `fable`-tier task under `/autopilot:work`, where Devon runs.

### Success Metrics

- `adversarial-test-prompt.md` says `Max 1 Tess/Devon round` and `SKILL.md` step 2.8 says `max 4 dispatches`; `test_adversarial_cap_prose.py` pins both and runs from `dev/bin/release-checks`.
- For every task built after this lands, `dev/local/autopilot/ledger/dispatch-metrics.jsonl` holds at most 2 `devon` start rows and at most 4 `tess` start rows per `task` value (`jq -r 'select(.kind=="devon") | .task' dev/local/autopilot/ledger/dispatch-metrics.jsonl`, counted per task); reported in the batch review, never gated on wall-clock.
- `bash dev/bin/release-checks` green.

## Functional Decomposition

### Capability: Adversarial loop cap
One strengthen round, then flag and proceed.

#### Feature: The outcome table allows one round
- **Description**: Devon's outcome table caps the loop at Devon, Tess strengthens, Devon re-checks, then flag weakness and proceed.
- **Inputs**: `skills/work/references/adversarial-test-prompt.md` lines 18-19 (the second and third rows of the Outcomes table).
- **Outputs**: the two rows read exactly:

  ```
  | Breaks tests with wrong impl that passes | Send Devon's exploit back to Tess: "These tests can be passed by: {wrong impl}. Strengthen them." Then re-run Devon once against the strengthened tests. Max 1 Tess/Devon round (2 Devon dispatches, 1 strengthen-side Tess dispatch per task). |
  | 1 round exhausted (Devon still breaks the strengthened tests) | Flag weakness in task output, proceed anyway. |
  ```
- **Behavior**: the first row (`Cannot break tests`) and the prompt template are unchanged; the § Feedback to Tess block is unchanged.

#### Feature: The Tess budget shrinks to match
- **Description**: `SKILL.md` step 2.8's total Tess budget counts the one strengthen instead of two, and step 2.85 states Devon's per-task maximum.
- **Inputs**: `skills/work/SKILL.md:242` (the `**Total Tess budget:**` paragraph) and the step 2.85 paragraph that begins `See `references/adversarial-test-prompt.md` § Procedure`.
- **Outputs**: line 242 reads exactly `**Total Tess budget:** max 4 dispatches across the entire test authoring phase (1 initial + 2 quality-gate retries + 1 adversarial strengthen). If exhausted, flag weakness in task output and proceed. Don't block the pipeline forever.`; the step 2.85 paragraph gains, as its first sentence, `Devon runs at most twice per task: the first pass and one re-check after Tess strengthens (`references/adversarial-test-prompt.md` § Outcomes).`
- **Behavior**: `Max 2 quality gate retries` in step 2.8 and in `references/test-author-prompt.md:80` stay as they are; `references/red-check.md`'s accidentally-green row keeps drawing on the total budget. `test_dispatch_prose.py`'s 500-line ceiling on `SKILL.md` still holds (one sentence added).

### Capability: Prose pins
The numbers cannot drift back without a red test.

#### Feature: A contract test pins both files
- **Description**: `skills/work/scripts/test_adversarial_cap_prose.py` binds the live text of both files, in the pattern of `test_dispatch_prose.py` (resolve the path relative to the test file, read once, assert short reword-resistant substrings with a message naming what drifted).
- **Inputs**: `skills/work/references/adversarial-test-prompt.md`, `skills/work/SKILL.md`.
- **Outputs**: tests named `test_outcome_table_caps_the_loop_at_one_round` (asserts `Max 1 Tess/Devon round` and `2 Devon dispatches, 1 strengthen-side Tess dispatch` present, `Max 2 Tess/Devon rounds` and `2 A/C rounds exhausted` absent), `test_total_tess_budget_is_four` (asserts `max 4 dispatches` and `1 adversarial strengthen` present, `max 5 dispatches` absent), and `test_step_2_85_states_devons_per_task_maximum` (asserts `Devon runs at most twice per task` present). `dev/bin/release-checks` gains a `[checks] adversarial cap prose` block running the file the way the registry block does.
- **Behavior**: pytest via `uv run --no-project --with pytest python -m pytest -q skills/work/scripts/test_adversarial_cap_prose.py`.

## Structural Decomposition

### Repository Structure

```
skills/work/references/adversarial-test-prompt.md     # Maps to: the outcome table allows one round
skills/work/SKILL.md                                  # Maps to: the Tess budget shrinks to match
skills/work/scripts/test_adversarial_cap_prose.py     # Maps to: a contract test pins both files (new)
dev/bin/release-checks                                # Maps to: runs the new prose test
CHANGELOG.md
```

### Module: adversarial-cap
- **Maps to capability**: Adversarial loop cap
- **Responsibility**: the two table rows, the budget paragraph and the step 2.85 sentence.
- **Exports**: none (skill prose).

### Module: cap-pins
- **Maps to capability**: Prose pins
- **Responsibility**: `test_adversarial_cap_prose.py` and its `release-checks` block.
- **Exports**: none.

## Dependency Graph

### Foundation Layer (Phase 0)
No dependencies - built first.

- **adversarial-cap**: the prose numbers.

### Core Layer (Phase 1)
- **cap-pins**: Depends on [adversarial-cap].

## Implementation Phases

### Phase 0: Foundation
**Goal**: the loop's numbers say one round.

**Tasks**:
- [ ] Replace the two outcome-table rows in `adversarial-test-prompt.md`, the `**Total Tess budget:**` paragraph in `SKILL.md` step 2.8, and prepend the Devon-maximum sentence to the step 2.85 pointer paragraph, all with the exact text above; CHANGELOG `**work**` under Changed: `the Tess/Devon adversarial loop runs one strengthen round (at most 2 Devon and 4 Tess dispatches per task), then flags and proceeds` (no deps) - Acceptance: `rg -c 'Max 1 Tess/Devon round' skills/work/references/adversarial-test-prompt.md` prints 1; `rg -c 'Max 2 Tess/Devon rounds' skills/work/references/adversarial-test-prompt.md` exits 1; `rg -c 'max 4 dispatches' skills/work/SKILL.md` prints 1; `rg -c 'max 5 dispatches' skills/work/SKILL.md` exits 1; `uv run --no-project --with pytest python -m pytest -q skills/work/scripts/test_dispatch_prose.py` green.

**Exit Criteria**: both files carry the new numbers and no old one.

### Phase 1: Core
**Goal**: the numbers are pinned.

**Tasks**:
- [ ] Write `skills/work/scripts/test_adversarial_cap_prose.py` with the three tests named above and add the `[checks] adversarial cap prose` block to `dev/bin/release-checks` (depends on: Phase 0) - Acceptance: `uv run --no-project --with pytest python -m pytest -q skills/work/scripts/test_adversarial_cap_prose.py` green with 3 passed; `rg -c 'test_adversarial_cap_prose.py' dev/bin/release-checks` prints 1; `bash dev/bin/release-checks` green.

**Exit Criteria**: `bash dev/bin/release-checks` green with the new block present.

## Test Strategy

### Critical Scenarios
- **Happy path**: Devon cannot break Tess's tests on the first pass → Expected: one `devon` row, one `tess` row, proceed to step 2.9 (unchanged).
- **Edge case**: Devon breaks the tests, Tess strengthens, Devon breaks them again → Expected: two `devon` rows, two `tess` rows (initial plus strengthen), weakness flagged in task output, implementor runs.
- **Error case**: a later edit restores `Max 2 Tess/Devon rounds` → Expected: `test_outcome_table_caps_the_loop_at_one_round` fails naming the file.

## Risks

- **Weaker tests reach the implementor after one round**: Pat's per-task review, the 0.5.0 tautological check in step 2.8 and the cycle review remain; PRD 00015's real gap was found there, not by Devon's round two.
- **Prose caps drift silently**: the contract test and its `release-checks` block are the pin, the same shape PRD 00157's PRDs used.
