---
design: skip
default_model: sonnet
model_tier_rationale: one refusal predicate with its exact condition and messages, one Classification row and one Select sentence with their exact text, additive tests in the existing review-close and prose suites
---

# Sweep only findings two reviewers raised

Source: the consolidated findings tables of `docs/dev/project-management/reviews/00312-close-ten-loop-truths-v1-review-1.md`, `docs/dev/project-management/reviews/00320-refuse-every-unsafe-verify-log-sink-v2-review-1.md`, `docs/dev/project-management/reviews/00320-refuse-every-unsafe-verify-log-sink-v2-review-2.md` and `docs/dev/project-management/reviews/00307-guard-citations-and-replay-contract-v1-review-1.md`, counted 2026-10-16, and the `review_converged` rows of `docs/dev/project-management/autopilot/loop-metrics.jsonl`.

## Problem

Most review findings have exactly one voice behind them. The consolidator writes each row's Consensus cell as the finder count over `total_agents` (`skills/review-work-completion/scripts/consolidate_findings.py:444`) and copies every finder into the row's `found_by`. Counting the `[1/N]` rows: 00312 cycle 1 had 20 single-voice rows of 22; 00320 cycle 1 had 19 of 23 and cycle 2 had 14 of 19; 00307 cycle 1 had 15 of 18.

Nothing downstream reads that cell. The `Classification` rows (`skills/run-autopilot/references/phase-review.md:106-145`) route a Medium or Low by kind, never by how many reviewers saw it; the Tail sweep's `Select` step (`skills/run-autopilot/references/phase-review.md:195`) takes every actionable Medium/Low row; and `review-close` groups the result into up to `NON_CRITICAL_CAP` tasks (`skills/run-autopilot/cli/rework_groups.py:20`) at the decision gate and again at the sweep.

That is where plans grow: `tasks_planned` against `tasks_in_prd` reads 10 against 3, 9 against 3, 11 against 4 and 9 against 5 for the last batch, and 7 against 3 for 00320, and each extra task runs the full per-task pipeline (tests-first, implementor, self-deslop, Pat, retries). The HIGH that forced 00320's second cycle was itself a `[1/4]` row (R5, Carl alone); CRITICAL and HIGH rows stay outside this PRD, since the convergence test depends on them.

## Solution

A Medium or Low finding becomes a task only when at least two reviewers raised it. The prose decides it where findings are classified and selected; `review-close` enforces it so a hand-built batch cannot bypass it. In Classification, a `[1/N]` Medium or Low row maps to `discard` with the ledger reason `single-voice`, so the settled-decisions ledger (`{prd-stem}-ledger.json`, `skills/run-autopilot/references/phase-review.md:147-157`) dismisses the same finding when a reviewer re-raises it next cycle (step 6 passes it to the consolidator and dismisses `BLAKE` re-raises against it, `skills/review-work-completion/SKILL.md:386`). In the Tail sweep, Select excludes `[1/N]` rows and writes the same ledger entry for each; zero multi-voice rows skips the sweep. In `review_close.py`, a `decision-gate` batch refuses a `fix` row whose `found_by` has fewer than two entries at 🟡 or ⚪ (`single_voice_fix`), and a `tail-sweep` batch refuses any row with fewer than two (`tail_sweep_single_voice`), each naming the first offending `ref`. A single-voice row that is a real defect still reaches the batch report through the ledger and the Phase 9 audit, and agoge's product QA stays the external check.

## Requirements

### Must have
- `_prelock_refusal` (`skills/run-autopilot/cli/review_close.py:639-656`) refuses a `decision-gate` batch containing a row with `classification == "fix"`, `severity` in (🟡, ⚪) and fewer than two `found_by` entries with `{"applied": False, "refused": "single_voice_fix", "reason": "a single-voice medium/low row cannot become a task: <ref>"}`; `_tail_sweep_refusal` (`skills/run-autopilot/cli/review_close.py:549-604`) refuses any row with fewer than two `found_by` entries with `refused: "tail_sweep_single_voice"`, checked after `tail_sweep_above_medium` and before `tail_sweep_duplicates_deferral`. A missing `found_by` counts as zero finders. CLI exit 2, nothing written, as for every other refusal.
- The `Classification` section of `skills/run-autopilot/references/phase-review.md` gains, before **Defer to batch end**: `**Single-voice Medium or Low** (Consensus cell `[1/N]`): `discard`, never a task. Append it to the ledger with `disposition: "discarded"` and reason `single-voice`, so a re-raise is auto-dismissed next cycle. A CRITICAL or HIGH is never single-voiced away: it keeps the rows above.` The `classification` mapping table (`skills/run-autopilot/references/phase-review.md:294-302`) gains the row `| Single-voice Medium or Low | `"discard"` |`.
- Tail sweep step 1 `Select` (`skills/run-autopilot/references/phase-review.md:195`) gains the sentence: `Exclude every row whose Consensus cell is `[1/N]`: append each to the ledger as `discarded`, reason `single-voice`, and sweep only rows two or more reviewers raised. Zero such rows → skip the sweep.`
- Fail-first tests: `test_decision_gate_refuses_a_single_voice_fix_row` and `test_tail_sweep_refuses_a_single_voice_row` in `skills/run-autopilot/cli/test_review_close_tail_sweep.py` (registered under `[checks] review verbs`, `dev/bin/release-checks:347`); `test_classification_discards_single_voice_rows` and `test_tail_sweep_select_excludes_single_voice_rows` in a new `skills/run-autopilot/scripts/test_single_voice_prose.py` registered under `[checks] cap hook` in `dev/bin/release-checks`.
- A CHANGELOG `[Unreleased]` Changed entry under **run-autopilot**.

### Nice to have
- None.

## Implementation

### Module: single-voice-refusal
- **Location**: `skills/run-autopilot/cli/review_close.py` (`_prelock_refusal`, `_tail_sweep_refusal`)
- **Responsibility**: no Medium or Low row with one finder becomes a task through either batch
- **Exports**: `close()` (unchanged signature)
- New symbols: `_single_voice_refusal`, `single_voice_fix`, `tail_sweep_single_voice`

### Module: single-voice-prose
- **Location**: `skills/run-autopilot/references/phase-review.md` (Classification, the mapping table, Tail sweep Select)
- **Responsibility**: the orchestrator discards single-voice Medium/Low rows into the ledger instead of classifying them for fix
- **Exports**: none (prose)

### Module: single-voice-tests
- **Location**: `skills/run-autopilot/cli/test_review_close_tail_sweep.py`, `skills/run-autopilot/scripts/test_single_voice_prose.py`
- **Responsibility**: pin both refusals and both prose rules
- **Exports**: none
- New symbols: `test_single_voice_prose.py`, `test_decision_gate_refuses_a_single_voice_fix_row`, `test_tail_sweep_refuses_a_single_voice_row`, `test_classification_discards_single_voice_rows`, `test_tail_sweep_select_excludes_single_voice_rows`

### Dependencies
- single-voice-tests: No dependencies (foundation)
- single-voice-refusal: Depends on [single-voice-tests]
- single-voice-prose: Depends on [single-voice-tests]

## Tasks

### Phase 0: Foundation
- [ ] Add the two review-close tests to `skills/run-autopilot/cli/test_review_close_tail_sweep.py`, built from its existing fixtures (a review file holding a `[1/4]` 🟡 row and a `[2/4]` 🟡 row, the decision-gate stamp arranged as `test_a_clean_tail_sweep_still_applies` at `skills/run-autopilot/cli/test_review_close_tail_sweep.py:180` arranges it). `test_decision_gate_refuses_a_single_voice_fix_row` closes a `decision-gate` batch whose `[1/4]` row carries `classification: "fix"` and `found_by: ["CARL"]` and asserts `refused == "single_voice_fix"`, the row's ref in `reason`, and no task created. `test_tail_sweep_refuses_a_single_voice_row` closes a `tail-sweep` batch holding that row and asserts `refused == "tail_sweep_single_voice"`, then closes the same batch without it and asserts it applies. Write `skills/run-autopilot/scripts/test_single_voice_prose.py` with `test_classification_discards_single_voice_rows` (the text between `### Classification (per finding):` and `### Settled-decisions ledger` contains `**Single-voice Medium or Low**`, and the file contains `| Single-voice Medium or Low | `"discard"` |`) and `test_tail_sweep_select_excludes_single_voice_rows` (the text between `**1. Select.**` and `**2. Create.**` contains `Consensus cell is `[1/N]`` and `reason `single-voice``). Register the new file under `[checks] cap hook` in `dev/bin/release-checks` - Acceptance: `uv run --no-project --with pytest python -m pytest -q skills/run-autopilot/cli/test_review_close_tail_sweep.py skills/run-autopilot/scripts/test_single_voice_prose.py -k single_voice` reports the four new tests failing at the task's base commit; `rg -c 'test_single_voice_prose.py' dev/bin/release-checks` prints 1.

### Phase 1: Core
- [ ] Add `_single_voice_refusal(chosen_findings, batch_id)` to `skills/run-autopilot/cli/review_close.py`, returning the refusal dict from Requirements or None (`decision-gate`: only `fix` rows at 🟡 or ⚪; `tail-sweep`: every row), call it from `_tail_sweep_refusal` between the above-medium and duplicate-deferral checks and from `_prelock_refusal` for `batch_id == "decision-gate"` before `_carry_refusal`; apply the three prose edits from Requirements verbatim (depends on: Phase 0) - Acceptance: `uv run --no-project --with pytest python -m pytest -q skills/run-autopilot/cli/test_review_close_tail_sweep.py skills/run-autopilot/cli/test_review_close.py skills/run-autopilot/cli/test_review_close_apply.py skills/run-autopilot/scripts/test_single_voice_prose.py skills/run-autopilot/scripts/test_review_resume_prose.py skills/run-autopilot/scripts/test_rework_groups_prose.py skills/work/scripts/test_verify_queue_prose.py` passes.
- [ ] Add the CHANGELOG `[Unreleased]` Changed entry `**run-autopilot**: a Medium or Low finding raised by one reviewer is recorded in the ledger instead of becoming a rework or tail-sweep task, and review-close refuses a batch that tries` (depends on: Phase 1) - Acceptance: `rg -c 'raised by one reviewer is recorded in the ledger' CHANGELOG.md` prints 1.

## Success Criteria

- No `review_converged` row of the next batch has `tasks_planned` above `tasks_in_prd` plus four.
- `review-close` exits 2 with `single_voice_fix` or `tail_sweep_single_voice` on a hand-built batch carrying a `[1/N]` Medium row, and the four new tests are green.
