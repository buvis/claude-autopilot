---
catchup: skip
design: skip
ledger: deferred/202610141430-deferred.json
ledger_key: 5249678dbb24
source_prd: 00307-guard-citations-and-replay-contract-v1.md
severity: high
---

# Triage: R2: spec names test_six_corpus_dispatches_are_allowed; the substitute test pi...

## Problem

Deferred finding with no PRD owner when this stub was minted: batch `202610141430`, ledger `deferred/202610141430-deferred.json`, type `cap-overflow`, cycle `2`, consensus `1/4`, raised against `00307-guard-citations-and-replay-contract-v1.md`.

Issue: R2: spec names test_six_corpus_dispatches_are_allowed; the substitute test pins only 2 of the 6 recorded corpus ids, the other four are documented unrecoverable (hold stub 00294 carries no prompts) and are covered only by synthetic tests (hooks/test_guard_phase_delegation_corpus.py:35)

## Solution

Attended triage. A human promotes this finding into a backlog PRD through normal PRD authoring and review, or closes it. Autopilot never drains `docs/dev/project-management/prds/hold/`, and this stub is never auto-promoted.

## Requirements

### Must have
- A triage decision for ledger key `5249678dbb24`: a backlog PRD, or closed.

### Nice to have
- None until triage.

## Implementation

### Module: triage
- **Location**: `docs/dev/project-management/prds/hold/`
- **Responsibility**: hold ledger key `5249678dbb24` from `00307-guard-citations-and-replay-contract-v1.md` until a human triages it
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

## Triage 2026-10-15

Accepted as a documented limit. The four missing prompts were never recorded (stub 00294 carried none), so no test can pin them verbatim; `hooks/test_guard_phase_delegation_corpus.py` names its synthetic shapes as such. PRD 00324 records the decision and adds no task for it. Closed into `done/`.
