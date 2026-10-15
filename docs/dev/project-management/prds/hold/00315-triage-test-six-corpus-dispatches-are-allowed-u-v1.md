---
catchup: skip
design: skip
ledger: deferred/202610141430-deferred.json
ledger_key: bb2aba03864c
source_prd: 00307-guard-citations-and-replay-contract-v1.md
severity: critical
---

# Triage: test_six_corpus_dispatches_are_allowed uses invented prompts instead of the s...

## Problem

Deferred finding with no PRD owner when this stub was minted: batch `202610141430`, ledger `deferred/202610141430-deferred.json`, type `review-critical`, cycle `1`, consensus `3/4`, raised against `00307-guard-citations-and-replay-contract-v1.md`.

Issue: test_six_corpus_dispatches_are_allowed uses invented prompts instead of the six stub-00294 prompts verbatim, so it is green while the real corpus replay is red

## Solution

Attended triage. A human promotes this finding into a backlog PRD through normal PRD authoring and review, or closes it. Autopilot never drains `docs/dev/project-management/prds/hold/`, and this stub is never auto-promoted.

## Requirements

### Must have
- A triage decision for ledger key `bb2aba03864c`: a backlog PRD, or closed.

### Nice to have
- None until triage.

## Implementation

### Module: triage
- **Location**: `docs/dev/project-management/prds/hold/`
- **Responsibility**: hold ledger key `bb2aba03864c` from `00307-guard-citations-and-replay-contract-v1.md` until a human triages it
- **Exports**: none

### Dependencies
- triage: No dependencies (foundation)

## Tasks

### Phase 0: Foundation
- [ ] triage: promote to backlog or close - Acceptance: this file is no longer under docs/dev/project-management/prds/hold/

### Phase 1: Core
No implementation tasks until attended triage.

## Success Criteria

- This file is no longer under `docs/dev/project-management/prds/hold/`.
