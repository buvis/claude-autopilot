---
catchup: skip
design: skip
ledger: deferred/202610141430-deferred.json
ledger_key: 53914e9a0c9b
source_prd: 00307-guard-citations-and-replay-contract-v1.md
severity: critical
---

# Triage: The replay does not exit 0 and does not read per-task <n> refused 1; it exits...

## Problem

Deferred finding with no PRD owner when this stub was minted: batch `202610141430`, ledger `deferred/202610141430-deferred.json`, type `review-critical`, cycle `1`, consensus `1/4`, raised against `00307-guard-citations-and-replay-contract-v1.md`.

Issue: The replay does not exit 0 and does not read per-task <n> refused 1; it exits 1 with refused 3, two of them non-pinned, failing the Phase 2 acceptance and Success Criterion 1

## Solution

Attended triage. A human promotes this finding into a backlog PRD through normal PRD authoring and review, or closes it. Autopilot never drains `docs/dev/project-management/prds/hold/`, and this stub is never auto-promoted.

## Requirements

### Must have
- A triage decision for ledger key `53914e9a0c9b`: a backlog PRD, or closed.

### Nice to have
- None until triage.

## Implementation

### Module: triage
- **Location**: `docs/dev/project-management/prds/hold/`
- **Responsibility**: hold ledger key `53914e9a0c9b` from `00307-guard-citations-and-replay-contract-v1.md` until a human triages it
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
