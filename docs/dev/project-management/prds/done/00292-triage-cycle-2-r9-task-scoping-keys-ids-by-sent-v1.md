---
catchup: skip
design: skip
ledger: deferred/202610111300-deferred.json
ledger_key: 1993a7556e15
source_prd: 00271-guard-v2-structural-delegation-check-v1.md
severity: high
---

# Triage: [cycle 2 R9] Task scoping keys ids by (sentence index, id) instead of distinc...

## Problem

Deferred finding with no PRD owner when this stub was minted: batch `202610111300`, ledger `deferred/202610111300-deferred.json`, type `cap-overflow`, consensus `2/3`, raised against `00271-guard-v2-structural-delegation-check-v1.md`.

Issue: [cycle 2 R9] Task scoping keys ids by (sentence index, id) instead of distinct ids, so the same id repeated in a second sentence counts as two and does not scope. `Fix task 3. The hook must run the work phase for PRD 7. Report when task 3 passes.` is refused, and ordinary per-task prompts repeat their task number. The PRD says "exactly one distinct task id". Deduplicate ids alone.

## Solution

Attended triage. A human promotes this finding into a backlog PRD through normal PRD authoring and review, or closes it. Autopilot never drains `docs/dev/project-management/prds/hold/`, and this stub is never auto-promoted.

## Requirements

### Must have
- A triage decision for ledger key `1993a7556e15`: a backlog PRD, or closed.

### Nice to have
- None until triage.

## Implementation

### Module: triage
- **Location**: `docs/dev/project-management/prds/hold/`
- **Responsibility**: hold ledger key `1993a7556e15` from `00271-guard-v2-structural-delegation-check-v1.md` until a human triages it
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

## Triage 2026-10-14

Rejected. The (sentence, id) key is the documented design of `_is_scoped` (`hooks/guard_phase_delegation.py`): a bare number is a reference its sentence carries, so forty sentences naming task 1 before "Run the work phase now." must not scope a whole run. The stub's own example carries a whole-PRD order ("the hook must run the work phase for PRD 7") and is refused correctly; a per-task prompt that repeats its task number but orders no phase run is never denied. PRD 00307 names this as out of scope. Closed into `done/`.
