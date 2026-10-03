---
catchup: skip
design: skip
ledger: deferred/202610031511-deferred.json
ledger_key: 6d8acd1560bb
source_prd: 00241-bound-rework-batches-by-file-v1.md
severity: high
---

# Triage: The store .gitignore recursive lock pattern will be reverted again by ensure-...

## Problem

Deferred finding with no PRD owner when this stub was minted: batch `202610031511`, ledger `deferred/202610031511-deferred.json`, type `review-deferral`, cycle `1`, consensus `3/4`, raised against `00241-bound-rework-batches-by-file-v1.md`.

Issue: The store .gitignore recursive lock pattern will be reverted again by ensure-store on every build gate until a release carrying PRD 00240 reaches the installed plugin cache

## Solution

Attended triage. A human promotes this finding into a backlog PRD through normal PRD authoring and review, or closes it. Autopilot never drains `docs/dev/project-management/prds/hold/`, and this stub is never auto-promoted.

## Requirements

### Must have
- A triage decision for ledger key `6d8acd1560bb`: a backlog PRD, or closed.

### Nice to have
- None until triage.

## Implementation

### Module: triage
- **Location**: `docs/dev/project-management/prds/hold/`
- **Responsibility**: hold ledger key `6d8acd1560bb` from `00241-bound-rework-batches-by-file-v1.md` until a human triages it
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
