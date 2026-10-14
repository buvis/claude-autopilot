---
catchup: skip
design: skip
ledger: deferred/202610111300-deferred.json
ledger_key: dc5a1f822d5b
source_prd: 00271-guard-v2-structural-delegation-check-v1.md
severity: high
---

# Triage: [cycle 2 R1] Quadratic work is still present for SKILL.md candidates, so prio...

## Problem

Deferred finding with no PRD owner when this stub was minted: batch `202610111300`, ledger `deferred/202610111300-deferred.json`, type `cap-overflow`, consensus `3/3`, raised against `00271-guard-v2-structural-delegation-check-v1.md`.

Issue: [cycle 2 R1] Quadratic work is still present for SKILL.md candidates, so prior R2 is only partly resolved and the PRD rule "every regex runs in linear time" is still unmet. `_ordered_to_follow` finds the sentence end with `next((s for s in sentences if s >= end), len(text))`, which walks the sentence list from index 0 for each SKILL.md candidate. 680 KB of repeated `work/SKILL.md.` sentences takes 5.7 s, past the 5 s hook timeout, so the hook fails open. Replace the `next(...)` with `bisect_left(sentences, end)` and add a many-SKILL.md-mentions linearity case.

## Solution

Attended triage. A human promotes this finding into a backlog PRD through normal PRD authoring and review, or closes it. Autopilot never drains `docs/dev/project-management/prds/hold/`, and this stub is never auto-promoted.

## Requirements

### Must have
- A triage decision for ledger key `dc5a1f822d5b`: a backlog PRD, or closed.

### Nice to have
- None until triage.

## Implementation

### Module: triage
- **Location**: `docs/dev/project-management/prds/hold/`
- **Responsibility**: hold ledger key `dc5a1f822d5b` from `00271-guard-v2-structural-delegation-check-v1.md` until a human triages it
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

Promoted into PRD 00307 (`guard-citations-and-replay-contract`): `_ordered_to_follow` uses `bisect_left`, pinned by `test_ordered_to_follow_uses_bisect`. Closed into `done/`.
