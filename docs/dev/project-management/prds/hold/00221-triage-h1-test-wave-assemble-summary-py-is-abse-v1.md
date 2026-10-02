---
catchup: skip
design: skip
ledger: deferred/202609252154-deferred.json
ledger_key: 49a475b28c63
source_prd: 00215-assemble-a-drained-wave-onto-one-branch-v1.md
severity: high
---

# Triage: H1: test_wave_assemble_summary.py is absent from both the `[checks] waves` bl...

## Problem

Deferred finding with no PRD owner when this stub was minted: batch `202609252154`, ledger `deferred/202609252154-deferred.json`, type `cap-overflow`, cycle `2`, consensus `2/4`, raised against `00215-assemble-a-drained-wave-onto-one-branch-v1.md`.

Issue: H1: test_wave_assemble_summary.py is absent from both the `[checks] waves` block's pytest invocation (dev/bin/release-checks:107-119) and test_wave_docs.py's _WAVE_TEST_FILES whitelist (:41-53), so its 12 tests - three of them PRD-named Phase 0 acceptance tests - never run in the repo's only CI gate while release-checks still reports green. test_the_release_gate_runs_every_wave_test_file cannot catch it: it asserts named == set(_WAVE_TEST_FILES) and task 10 updated neither side.

## Solution

Attended triage. A human promotes this finding into a backlog PRD through normal PRD authoring and review, or closes it. Autopilot never drains `dev/local/prds/hold/`, and this stub is never auto-promoted.

## Requirements

### Must have
- A triage decision for ledger key `49a475b28c63`: a backlog PRD, or closed.

### Nice to have
- None until triage.

## Implementation

### Module: triage
- **Location**: `dev/local/prds/hold/`
- **Responsibility**: hold ledger key `49a475b28c63` from `00215-assemble-a-drained-wave-onto-one-branch-v1.md` until a human triages it
- **Exports**: none

### Dependencies
- triage: No dependencies (foundation)

## Tasks

### Phase 0: Foundation
- [ ] triage: promote to backlog or close - Acceptance: this file is no longer under dev/local/prds/hold/

### Phase 1: Core
No implementation tasks until attended triage.

## Success Criteria

- This file is no longer under `dev/local/prds/hold/`.
