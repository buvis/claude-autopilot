---
catchup: skip
design: run
default_model: opus
model_tier_rationale: invents the carry-to-task link and changes the refusal contract both review verbs consume; a wrong rule either stalls the loop or lets a critical finding vanish
---

# Close the critical-row escapes

## Overview

### Problem Statement

The 2026-10-06 agoge run (`docs/dev/project-management/audit-results/agoge-2026-10-06.md`,
findings 1-3, all HIGH, all confirmed by running the code) shows three ways a
🔴 review row can still leave the decision gate with no task and no record
after PRD 00264. 00264 is on master but not yet released, so all three ship
with the next release unless fixed:

1. **`carry` is unchecked.** `gate.py:141` puts `carry` in
   `_SKIPPED_CLASSIFICATIONS`, and `review_close.py` never looks it up. A 🔴
   "deletes user data" row classified `carry` converged a PRD with
   `tasks_created: []` and an empty audit. A ghost `carry` for `R99` (not in
   the review) also passes. The 0.9.0 cache refuses that ghost, so 00264
   opened the hole.
2. **Off-shape rows skip coverage.** Only rows matching `TABLE_DATA_ROW_RE`
   (`gate.py:114`) with a Ref are covered. Ref cells `r1`, `R1.`, `R1a`,
   `R1 \| R3`, an unbracketed consensus `2/2`, a table with no Ref column,
   bullet rows, a duplicated ref, and one ref given two classifications all
   pass `gate` and `review-close` with zero tasks.
3. **The verbs disagree on a damaged table.** `gate` refuses an
   `unreadable-table` (exit 1), but `review-close` treats `malformed` like "no
   section" and applies the batch with both cross-checks off
   (`review_close.py:309`).

Operator decision (2026-10-06): fix all three with the report's recommended
options in one PRD, and fold in the four MEDIUM findings on the same verbs:

4. `--batch-id tail-sweep` is accepted first, at any severity, with coverage
   skipped; a later decision gate then applies too and duplicates rework.
5. An empty tail-sweep array exits 0 and stamps the batch applied, so the real
   sweep gets `already applied` (`phase-review.md:195` says "never zero").
7. `gate --findings` passes rows with a missing or unknown classification
   (`"Carry"`, `"carried"`) that `review-close` then refuses with a message
   naming neither row nor value.
10. `gate.py:52,67-68,138-141` and `__main__.py:65-67,79-82` still describe the
   pre-00264 one-way check and omit the uncovered refusal.

### Target Users

The autopilot decision gate and Tail sweep; every `autopilot gate --findings`
and `autopilot review-close` call.

### Success Metrics

- Every scenario in the problem statement exits 2 from both verbs, writing nothing.
- `release-checks` exits 0.

## Functional Decomposition

### Capability: carry is backed

#### Feature: Refuse an unmatched carry
- **Description**: a `carry` row is accepted only when its ref is a row of the review table and a `[C{cycle}]` task for that finding exists in `state.tasks`.
- **Inputs**: the findings JSON, the review table, `state.tasks`.
- **Outputs**: `refused: "carry_unmatched"`, exit 2, checked before the state lock.
- **Behavior**: the design doc fixes how a `[C]` task is matched to a review row (an explicit ref stamped on the task at re-queue time is preferred; file plus severity is the fallback the design must justify).

### Capability: parse fails closed

#### Feature: Unreadable on any off-shape row
- **Description**: once the findings table header is found, every following pipe row that is not a separator is a data row; one that does not parse makes the table `unreadable-table`.
- **Behavior**: refs match `R\d+` case-insensitively and are normalized to upper case; a duplicated table ref, and a JSON ref given two classifications, are refusals. A table with no Ref column, and bullet-shape findings, are `unreadable-table` once a findings JSON is passed (no coverage is possible).

### Capability: one verdict for both verbs

#### Feature: Shared parse-and-verdict
- **Description**: `gate` and `review-close` call one function for the cross-check verdict, so they cannot drift again.
- **Behavior**: `review-close` refuses `unreadable-table` exactly like `gate`; only `no-section` keeps the legacy pass.

#### Feature: Classification checked in both verbs
- **Description**: `gate --findings` validates each row's classification with the same rule `review-close` uses.
- **Outputs**: exit 2 with a per-row message, e.g. `row R1: unknown classification 'Carry' (expected verify|discard|fix|defer|carry)`.

### Capability: tail sweep in order

#### Feature: Sweep only after the gate, never empty
- **Description**: `review-close --batch-id tail-sweep` refuses (exit 2, nothing recorded) unless `<review>::decision-gate` is in `applied_review_batches`, refuses rows above 🟡, and refuses an empty findings array.

### Capability: help text matches the check

#### Feature: Two-way check documented
- **Description**: the `gate.py` module docstring, its exit table, the `_SKIPPED_CLASSIFICATIONS` comment and `__main__.py`'s help for `gate` and `review-close` describe the two-way check and the `uncovered` and `carry_unmatched` refusals.

## Structural Decomposition

### Repository Structure

```
skills/run-autopilot/cli/
├── gate.py                      # Shared parse-and-verdict, Unreadable on any off-shape row
├── review_close.py              # Refuse an unmatched carry, refuse unreadable-table
├── test_gate_findings_table.py
└── test_review_close.py
skills/run-autopilot/references/phase-review.md   # carry rule, re-queue stamping
```

### Module: gate
- **Maps to capability**: parse fails closed; one verdict for both verbs
- **Responsibility**: read the findings table and judge a findings JSON against it
- **Exports**:
  - `findings_verdict(text, findings) -> tuple[str, str | None]` - the one verdict both verbs use

### Module: review_close
- **Maps to capability**: carry is backed; one verdict for both verbs
- **Responsibility**: apply a saved review
- **Exports**:
  - `close()` - unchanged signature, new `carry_unmatched` refusal

### Module: cli entry
- **Maps to capability**: help text matches the check
- **Responsibility**: `skills/run-autopilot/cli/__main__.py` help and exit tables for `gate` and `review-close`, pinned by `skills/run-autopilot/scripts/test_review_verbs_prose.py`
- **Exports**: none new

### Module: phase-review prose
- **Maps to capability**: carry is backed
- **Responsibility**: tell the orchestrator how a re-queued row and its `[C]` task are linked
- **Exports**: none

## Dependency Graph

### Foundation Layer (Phase 0)
No dependencies - built first.

- **gate**: the shared verdict and fail-closed parse

### Core Layer (Phase 1)
- **review_close**: Depends on [gate]

### Integration Layer (Phase 2)
- **phase-review prose**: Depends on [review_close]

## Implementation Phases

### Phase 0: Foundation
**Goal**: one fail-closed verdict.

**Tasks**:
- [ ] gate: `findings_verdict` shared by both verbs; off-shape rows, missing Ref column, bullet rows, duplicate refs and double-classified refs refuse (no deps) - Acceptance: `test_rejects_review_row_with_offshape_ref_instead_of_skipping_it` (parametrized over `r1`, `R1.`, `R1a`, `R1 \| R3`, unbracketed `2/2`), `test_refless_table_with_findings_is_unreadable`, `test_duplicate_table_ref_is_refused`, `test_ref_with_two_classifications_is_refused` pass in `cli/test_gate_findings_table.py`.

**Exit Criteria**: `python3 -m pytest skills/run-autopilot/cli/test_gate_findings_table.py` passes.

### Phase 1: Core
**Goal**: review-close refuses what gate refuses, and carry is backed.

**Tasks**:
- [ ] review_close: call `findings_verdict`; refuse `unreadable-table`; refuse an unmatched `carry` before the lock (depends on: Phase 0) - Acceptance: `test_refuses_unreadable_table_instead_of_applying`, `test_carry_on_critical_without_requeued_task_is_refused`, `test_ghost_carry_ref_is_refused`, `test_matched_carry_is_accepted` pass in `cli/test_review_close.py`.

- [ ] review_close: tail sweep refused before the decision gate, above 🟡, or empty (depends on: Phase 0) - Acceptance: `test_tail_sweep_refused_before_decision_gate_applied`, `test_tail_sweep_refuses_rows_above_medium`, `test_empty_tail_sweep_is_refused_and_records_nothing` pass in `cli/test_review_close.py`.
- [ ] gate: per-row classification validation in `gate --findings` (depends on: Phase 0) - Acceptance: `test_gate_names_the_row_with_an_unknown_classification` passes in `cli/test_gate_findings_table.py`.

**Exit Criteria**: `python3 -m pytest skills/run-autopilot/cli/test_review_close.py` passes.

### Phase 2: Integration
**Goal**: the prose creates the link the code checks.

**Tasks**:
- [ ] phase-review prose: the re-queue step records the link the design chose, and the decision gate says `carry` is refused without it (depends on: Phase 1) - Acceptance: `test_requeue_records_the_carry_link_prose` passes.
- [ ] help text: rewrite the `gate.py` docstring, exit table and skip-list comment, and the `__main__.py` help for `gate` and `review-close`; pin them in `skills/run-autopilot/scripts/test_review_verbs_prose.py` (depends on: Phase 1) - Acceptance: `test_gate_help_describes_the_two_way_check` passes.

**Exit Criteria**: `bash dev/bin/release-checks` exits 0.

## Test Strategy

### Critical Scenarios
- **Happy path**: a 🔴 row re-queued as `[C2]` with its link, classified `carry` -> accepted, no deferral, no new task.
- **Edge case**: `carry` on a 🟡 row with a matching `[C]` task -> accepted.
- **Error case**: heidi's payload (🔴 R1 `carry` with no `[C]` task) -> exit 2 `carry_unmatched`, state unchanged.
- **Error case**: `| r1 |` Ref cell with R1 omitted from the JSON -> exit 2 from both verbs.

## Risks

- **Stricter parsing stalls the loop on reviewer formatting drift**: the refusal message names the offending row so a re-run can fix it in one round trip; the design checks the reviewer templates emit the exact Ref shape.
- **The carry link may not exist on `[C]` tasks today**: the design step decides whether to stamp a ref at re-queue time; file plus severity matching is the fallback, never silent acceptance.
