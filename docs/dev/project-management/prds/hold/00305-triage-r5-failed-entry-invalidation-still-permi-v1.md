---
catchup: skip
design: skip
ledger: deferred/202610111300-deferred.json
ledger_key: 954b261e19b5
source_prd: 00282-loop-guards-v1.md
severity: high
---

# Triage: [R5] Failed entry invalidation still permits stale replay: `_invalidate_loop_...

## Problem

Deferred finding with no PRD owner when this stub was minted: batch `202610111300`, ledger `deferred/202610111300-deferred.json`, type `cap-overflow`, cycle `2`, consensus `1/3`, raised against `00282-loop-guards-v1.md`.

Issue: [R5] Failed entry invalidation still permits stale replay: `_invalidate_loop_entry` silently ignores another write failure, leaving the previous same-PRD result available to the child. Disable cached replay for that launch when invalidation fails; test persistent write failure with an existing entry. (file: skills/run-autopilot/cli/loop.py:628)

## Solution

Attended triage. A human promotes this finding into a backlog PRD through normal PRD authoring and review, or closes it. Autopilot never drains `docs/dev/project-management/prds/hold/`, and this stub is never auto-promoted.

## Requirements

### Must have
- A triage decision for ledger key `954b261e19b5`: a backlog PRD, or closed.

### Nice to have
- None until triage.

## Implementation

### Module: triage
- **Location**: `docs/dev/project-management/prds/hold/`
- **Responsibility**: hold ledger key `954b261e19b5` from `00282-loop-guards-v1.md` until a human triages it
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
