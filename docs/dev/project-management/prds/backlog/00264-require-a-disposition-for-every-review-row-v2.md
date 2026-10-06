---
catchup: skip
design: skip
default_model: sonnet
model_tier_rationale: transcription - the commits to bring over, the new classification value and every follow-up are named exactly; each change is pinned by a named test
ledger_keys: 83449f8a9b37
---

# Require a disposition for every review row (v2)

## Problem

Supersedes `00264-require-a-disposition-for-every-review-row-v1.md`. v1's
fast-track card was parked on 2026-10-06 (`a972527`, stall
`fast_track_blocked`); its work sits on branch
`fast-track/00264-require-a-disposition-for-every-review-row-v1-c1` and is
sound: `gate._cross_check_findings` refuses (`uncovered`, exit 2) a review row
whose `Ref` no findings-JSON row names, and `review-close` refuses the same.
Hold stub 00260 (ledger key `83449f8a9b37`) is what it closes.

One HIGH survived adversarial verification: re-queued `[C{cycle}]` rows must
now also carry a classification, and the only values are `fix`, `defer`,
`verify` and `discard`. A carry-over classified `defer` makes
`review_close._add_decisions` write a false `deferred_decisions` entry that
`custody.migration_records` (`custody.py:305-318`) can surface as a pending
HIGH/CRITICAL at a stall, and the row competes with the 🔴 exception for a
duplicate `[D{cycle}]` task. Operator decision (2026-10-06): add a fifth
classification, `carry`, that counts as covered and writes nothing.

## Solution

Bring the branch's work over, add `carry`, and clear the seven follow-ups the
review left.

## Requirements

### Must have
- Commits `1ec6eff`, `a220e50`, `170848d`, `0b383d8` and `857cf9b` from the parked branch are on master; `72dc013` (a notes commit, already re-applied as `03ef43d`) and the branch's `chore(autopilot)` store commits are not brought over.
- `carry` is a valid classification: it satisfies coverage, is skipped by the backed-row check like `verify`/`discard`, and `review-close` writes no decision, deferral or task for it.
- `phase-review.md` tells the orchestrator to classify every re-queued `[C{cycle}]` row as `carry`, and states the Tail sweep's findings JSON is exempt from coverage.
- Hold stub 00260 leaves `prds/hold/`.

### Nice to have
- None.

## Implementation

### Module: gate
- **Location**: `skills/run-autopilot/cli/gate.py`
- **Responsibility**: findings cross-check
- **Exports**: `_cross_check_findings()`

### Module: review_close
- **Location**: `skills/run-autopilot/cli/review_close.py`
- **Responsibility**: apply a saved review
- **Exports**: `close()`

### Module: phase-review prose
- **Location**: `skills/run-autopilot/references/phase-review.md`
- **Responsibility**: decision gate and Tail sweep text
- **Exports**: none

### Module: changelog
- **Location**: `CHANGELOG.md`
- **Responsibility**: `[Unreleased]` entries
- **Exports**: none

### Module: triage
- **Location**: `docs/dev/project-management/prds/hold/`
- **Responsibility**: stub 00260
- **Exports**: none

### Dependencies
- gate: No dependencies (foundation)
- review_close: Depends on [gate]
- phase-review prose: Depends on [gate]
- changelog: Depends on [gate, review_close]
- triage: Depends on [gate]

## Tasks

### Phase 0: Foundation
- [ ] gate: `git cherry-pick 1ec6eff a220e50 170848d 0b383d8 857cf9b` onto master. Premise: those five commits exist on `fast-track/00264-require-a-disposition-for-every-review-row-v1-c1` and none is already on master (`git branch --contains <sha>` lists no `master`); re-check at execution, and if any premise fails, skip that commit and report - Acceptance: `python3 -m pytest skills/run-autopilot/cli/test_gate_findings_table.py skills/run-autopilot/cli/test_review_close.py` passes.
- [ ] gate: add `"carry"` to `_SKIPPED_CLASSIFICATIONS` (`gate.py:141`); rewrite `_cross_check_findings`' docstring to say both directions are checked and to name the `uncovered` result (the MEDIUM "docstring still claims one-direction-only") - Acceptance: `test_carry_row_counts_as_covered` passes in `test_gate_findings_table.py`.

### Phase 1: Core
- [ ] review_close: a `carry` row writes no `autonomous_decisions`/`deferred_decisions` entry and creates no task; `close()`'s docstring names both `findings_mismatch` and `findings_uncovered`; fix the test docstring "Exit 2 belongs to the mismatch alone" in `test_review_close.py` (depends on: Phase 0) - Acceptance: `test_carry_row_writes_no_decision_and_no_task` and `test_close_refuses_an_uncovered_review_row` pass.
- [ ] phase-review prose: re-queued `[C{cycle}]` rows are classified `carry`; the Tail sweep's findings JSON is exempt from coverage (one clause); replace the em dash the v1 rewrite introduced with a comma or colon (depends on: Phase 0) - Acceptance: `test_requeued_rows_are_classified_carry_prose` and `test_tail_sweep_is_exempt_from_coverage_prose` pass (new, in `test_gate_findings_table.py`), and `rg -c "—" skills/run-autopilot/references/phase-review.md` returns no more than it does at master before this PRD.
- [ ] changelog: under `[Unreleased]` `### Fixed`, one entry: `- **run-autopilot**: the findings cross-check also refuses a review row the findings JSON leaves without a disposition (exit 2); re-queued rows use the new \`carry\` classification` (depends on: Phase 1 review_close task) - Acceptance: `rg -c "carry" CHANGELOG.md` is at least 1.
- [ ] triage: delete `docs/dev/project-management/prds/hold/00260-triage-r2-prd-test-strategy-says-a-findings-jso-v1.md` (depends on: Phase 0). Premise: the file exists and names ledger key `83449f8a9b37`; re-check at execution, skip and report if not - Acceptance: `test ! -e` on that path.

## Success Criteria

- `test_carry_row_counts_as_covered`, `test_carry_row_writes_no_decision_and_no_task`, `test_close_refuses_an_uncovered_review_row`, `test_requeued_rows_are_classified_carry_prose` and `test_tail_sweep_is_exempt_from_coverage_prose` pass.
- `bash dev/bin/release-checks` exits 0.
