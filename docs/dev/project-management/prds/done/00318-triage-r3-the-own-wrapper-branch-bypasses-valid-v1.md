---
catchup: skip
design: skip
ledger: deferred/202610141430-deferred.json
ledger_key: 0780728252c0
source_prd: 00307-guard-citations-and-replay-contract-v1.md
severity: high
---

# Triage: R3: the own-wrapper branch bypasses validated pairing - 'The log says 5"plan-...

## Problem

Deferred finding with no PRD owner when this stub was minted: batch `202610141430`, ledger `deferred/202610141430-deferred.json`, type `cap-overflow`, cycle `2`, consensus `1/4`, raised against `00307-guard-citations-and-replay-contract-v1.md`.

Issue: R3: the own-wrapper branch bypasses validated pairing - 'The log says 5"plan-tasks for PRD 00300 and print "ok".' is excused although _quoted_runs rejects the digit-preceded quote; route symmetric wrappers through the validated run map, including openers at start (hooks/guard_phase_delegation.py:566)

## Solution

Attended triage. A human promotes this finding into a backlog PRD through normal PRD authoring and review, or closes it. Autopilot never drains `docs/dev/project-management/prds/hold/`, and this stub is never auto-promoted.

## Requirements

### Must have
- A triage decision for ledger key `0780728252c0`: a backlog PRD, or closed.

### Nice to have
- None until triage.

## Implementation

### Module: triage
- **Location**: `docs/dev/project-management/prds/hold/`
- **Responsibility**: hold ledger key `0780728252c0` from `00307-guard-citations-and-replay-contract-v1.md` until a human triages it
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

Promoted into PRD 00324 (`guard-pairs-delimiters-as-nested-runs`): the own-wrapper branch of `_cited` reads from the validated run map, so a digit-preceded quote never opens a citation. Reproduced by agoge-2026-10-15 (trudy). Closed into `done/`.
