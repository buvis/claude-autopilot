---
catchup: skip
design: skip
ledger: deferred/202610031511-deferred.json
ledger_key: 36c2461f9d70
source_prd: 00249-stage-and-close-reviews-in-code-v1.md
severity: high
---

# Triage: resolve_base() is a second diff-base resolver beside gather-context.sh, so th...

## Problem

Deferred finding with no PRD owner when this stub was minted: batch `202610031511`, ledger `deferred/202610031511-deferred.json`, type `review-deferral`, consensus `2/4`, raised against `00249-stage-and-close-reviews-in-code-v1.md`.

Issue: resolve_base() is a second diff-base resolver beside gather-context.sh, so the replay could certify a different range (review_stage.py:183)

## Solution

Attended triage. A human promotes this finding into a backlog PRD through normal PRD authoring and review, or closes it. Autopilot never drains `docs/dev/project-management/prds/hold/`, and this stub is never auto-promoted.

## Requirements

### Must have
- A triage decision for ledger key `36c2461f9d70`: a backlog PRD, or closed.

### Nice to have
- None until triage.

## Implementation

### Module: triage
- **Location**: `docs/dev/project-management/prds/hold/`
- **Responsibility**: hold ledger key `36c2461f9d70` from `00249-stage-and-close-reviews-in-code-v1.md` until a human triages it
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
