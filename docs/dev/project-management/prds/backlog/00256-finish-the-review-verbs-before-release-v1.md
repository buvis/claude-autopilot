---
catchup: skip
design: run
default_model: opus
model_tier_rationale: fixes contracts other code consumes (review-file dispatch_rows block, gate cross-check of the findings JSON, last-verification counts) and a fail-open path
ledger_keys: 36c2461f9d70 6d4f6ba76e71 48f78f9210db fd29fd6660d9 691521d0e855 ea9194742172 51d4e95831ce 80d062746248 301475eacdce fbedf9570240
---

# Finish the review verbs before release

## Overview

### Problem Statement

PRD 00249 (`review-stage`, `review-close`, gate reuse) reached its rework cap
with ten HIGH findings open, ledger `deferred/202610031511-deferred.json`
(keys in the frontmatter). They block shipping 00249 in a release: on the
first cycle where codex is unavailable, `review-close` exits 2; Eve and the
Bob fallback get the wrong inputs; and the gate summary writes check-block
counts (25) into `last-verification.json` as test counts (2564 real).

Also, only one of the ten got a hold stub (00255). The other nine were
written with emoji severities (`🟠`), and `cli/triage.py:qualifies` matches
only the words `critical`/`high`, so `mint-stubs` skipped them without a
word. Measured 2026-10-04: every 00249 cap-overflow row carries an emoji
severity, every 00241/00248 one a word.

### Target Users

The autopilot review phase once 00249 ships; the batch-end triage.

### Success Metrics

- Every named test below passes, and `bash dev/bin/release-checks` exits 0.
- A cap-overflow row written with `🔴` or `🟠` mints a hold stub.

## Functional Decomposition

### Capability: review-close correctness

#### Feature: Close unavailable reviewers
- **Description**: an unavailable reviewer's dispatch row closes with `error`.
- **Inputs**: review file roster entry `unavailable`.
- **Outputs**: `record_dispatch.py end <id> --outcome error`.
- **Behavior**: `_DISPATCH_OUTCOME["unavailable"]` becomes `"error"` (`review_close.py:48`); a test asserts every value of `_DISPATCH_OUTCOME` is in `record_dispatch.OUTCOMES`.

#### Feature: Close every lens
- **Description**: the review-file format carries the `dispatch_rows:` block `review_close` parses, and lists Blake and Eve under `agents:`.
- **Inputs**: `review-work-completion/references/output-formats.md`.
- **Outputs**: format text and a fixture review file that closes all five lenses.
- **Behavior**: after `close()`, no lens in `state.review_lenses` is left `running`.

#### Feature: Cross-check the findings JSON
- **Description**: `autopilot gate --review-file` refuses when the `--findings` JSON and the review's consolidated table disagree.
- **Inputs**: review file, findings JSON.
- **Outputs**: exit 2 naming the first mismatched row.
- **Behavior**: same rows by (severity, file key, issue text normalized as `consolidate_findings` does); the design doc fixes the exact comparison.

### Capability: review-stage inputs

#### Feature: Doubt lens stays PRD-only
- **Description**: Eve gets the raw PRD body, never the PRD merged with the design doc.
- **Behavior**: `_eve_inputs` uses `_prd_body`, like Blake.

#### Feature: Bob's doubt appendix survives Eve
- **Description**: Bob's prompt carries the doubt appendix whether or not Eve is on the roster.
- **Behavior**: drop the `run["doubt"] = "eve" not in roster` gate (`review_stage.py:491`); a test renders Bob with Eve on the roster and asserts D1-D5 are present.

#### Feature: One diff-base resolver
- **Description**: the replay uses the base `gather-context.sh` resolved, not a second resolver.
- **Behavior**: `resolve_base()` (`review_stage.py:183`) is removed; the base comes from the context file's recorded scope.

#### Feature: Skill uses the flags
- **Description**: `review-work-completion/SKILL.md` passes `--settled-ledger` and `--prior-findings` to `review-stage` and no longer tells the model to hand-append either (lines 216-218, 248; step 3 synopsis).

### Capability: gate reuse correctness

#### Feature: Real test counts
- **Description**: the gate summary line reports pytest/harness totals, not counts of its own echo lines, and reports skips and failures.
- **Behavior**: on failure it still prints the line with the failed count; `last-verification.json` never receives a count the gate did not measure (null instead).

#### Feature: Bounded run_gate
- **Description**: `run_gate` streams output and keeps only the tail, under 50 lines per function.

#### Feature: Rename-safe reuse
- **Description**: `reuse_verdict` treats a porcelain rename record by its NEW path too, so a rename out of the store is not clean; the docstring states the rule the code applies.

### Capability: triage

#### Feature: Emoji severities mint stubs
- **Description**: `triage.qualifies` treats `🔴` as critical and `🟠` as high.
- **Behavior**: `SEVERE` gains both emoji; `phase-review.md` cap-out text says severity is written as a word.

## Structural Decomposition

### Repository Structure

```
skills/run-autopilot/cli/
├── review_close.py      # Close unavailable reviewers, Close every lens
├── review_stage.py      # Doubt lens PRD-only, Bob appendix, one resolver
├── verification.py      # Real test counts, Bounded run_gate, Rename-safe reuse
├── gate.py              # Cross-check the findings JSON
└── triage.py            # Emoji severities
dev/bin/release-checks   # summary line counts
skills/review-work-completion/SKILL.md, references/output-formats.md
skills/run-autopilot/references/phase-review.md
```

### Module: review_close
- **Maps to capability**: review-close correctness
- **Responsibility**: apply a saved review
- **Exports**: `close()` (unchanged)

### Module: review_stage
- **Maps to capability**: review-stage inputs
- **Responsibility**: stage and render
- **Exports**: `stage()`, `render_roster()` (unchanged signatures)

### Module: verification
- **Maps to capability**: gate reuse correctness
- **Responsibility**: reuse verdict and gate run
- **Exports**: `reuse_verdict()`, `run_gate()`

### Module: gate
- **Maps to capability**: review-close correctness
- **Responsibility**: review-file checks
- **Exports**: `main()`

### Module: triage
- **Maps to capability**: triage
- **Responsibility**: mint hold stubs
- **Exports**: `qualifies()`

## Dependency Graph

### Foundation Layer (Phase 0)
No dependencies - built first.

- **triage**: emoji severities
- **verification**: counts, bounds, rename

### Core Layer (Phase 1)
- **review_close**: Depends on []
- **review_stage**: Depends on []
- **gate**: Depends on [review_close]

### Integration Layer (Phase 2)
- **skill prose**: Depends on [review_stage, review_close, gate]

## Implementation Phases

### Phase 0: Foundation
**Goal**: no severe finding is lost, and gate counts are real.

**Tasks**:
- [ ] triage: emoji severities (no deps) - Acceptance: `test_emoji_high_row_qualifies`, `test_emoji_critical_row_qualifies` pass in `cli/test_triage.py`.
- [ ] verification + release-checks: real counts, bounded streaming `run_gate` under 50 lines, rename-safe `reuse_verdict` (no deps) - Acceptance: `test_summary_counts_tests_not_check_blocks`, `test_summary_line_printed_on_failure`, `test_run_gate_streams_and_keeps_tail`, `test_rename_out_of_store_is_not_clean` pass.

**Exit Criteria**: `python3 -m pytest skills/run-autopilot/cli/test_triage.py skills/run-autopilot/cli/test_verification.py` passes.

### Phase 1: Core
**Goal**: the verbs produce correct prompts and close every lens.

**Tasks**:
- [ ] review_close: `error` outcome and all-lens close (depends on: Phase 0) - Acceptance: `test_every_dispatch_outcome_is_recordable`, `test_close_leaves_no_lens_running` pass.
- [ ] review_stage: Eve PRD-only, Bob appendix with Eve present, `resolve_base` removed (depends on: Phase 0) - Acceptance: `test_eve_gets_raw_prd_only`, `test_bob_keeps_doubt_appendix_when_eve_rostered`, `test_replay_uses_gather_context_base` pass.
- [ ] gate: findings JSON cross-check (depends on: review_close task) - Acceptance: `test_gate_refuses_findings_json_mismatch`, `test_gate_accepts_matching_findings_json` pass.

**Exit Criteria**: the four test files touched pass.

### Phase 2: Integration
**Goal**: the skill text matches the code.

**Tasks**:
- [ ] SKILL.md, output-formats.md, phase-review.md: flags passed, hand-append text removed, `dispatch_rows:` and Blake/Eve in the format, severity written as a word (depends on: Phase 1) - Acceptance: `test_skill_passes_ledger_and_prior_findings_flags`, `test_output_format_lists_dispatch_rows_and_all_lenses`, `test_cap_out_severity_is_a_word` pass.
- [ ] triage: delete `docs/dev/project-management/prds/hold/00255-triage-resolve-base-is-a-second-diff-base-resol-v1.md` (depends on: review_stage task). Premise: the file exists and names ledger key `36c2461f9d70`; re-check at execution, skip and report if not - Acceptance: `test ! -e` on that path.

**Exit Criteria**: `bash dev/bin/release-checks` exits 0.

## Test Strategy

### Critical Scenarios
- **Happy path**: a full cycle-1 fixture closes all five lenses and writes real counts.
- **Edge case**: codex unavailable → `review-close` exits 0 and the Bob row closes `error`.
- **Edge case**: Eve on the roster → Bob's prompt still has D1-D5.
- **Error case**: findings JSON drops one table row → `gate` exits 2.

## Risks

- **Count parsing is brittle across pytest and the bash harnesses**: the design doc names the exact lines parsed; an unparseable block yields null, never a guess.
- **Blocks the 0.9.0 release until done**: release only after this PRD converges.
