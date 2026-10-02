---
catchup: skip
design: skip
ledger: deferred/202609252154-deferred.json
ledger_key: d190c6d3ccb8
source_prd: 00217-bound-concurrent-review-sessions-with-a-slot-semaphore-v1.md
severity: high
---

# Triage: The reclaim can still hand one slot to two holders (three-party put-back race...

## Problem

Deferred finding with no PRD owner when this stub was minted: batch `202609252154`, ledger `deferred/202609252154-deferred.json`, type `cap-overflow`, cycle `2`, consensus `3/4`, raised against `00217-bound-concurrent-review-sessions-with-a-slot-semaphore-v1.md`.

Issue: The reclaim can still hand one slot to two holders (three-party put-back race). _discard moves a stale-looking slot aside before judging it; if it wins that rename against a peer that just re-claimed the slot live, the slot name is vacant from os.rename(slot, aside) at wave_slots.py:110 until the put-back at :116. A third acquirer _claim can take the name in that window, the put-back then fails, the live claim is stranded in N.stale-<pid>, and count=1 admits two concurrent sessions. The stranded holder release (no ownership check) later removes the third party slot. The source documents the residual at wave_slots.py:102-106 and names the fix: a per-slot fcntl.flock. File: skills/run-autopilot/cli/wave_slots.py:116

## Solution

Attended triage. A human promotes this finding into a backlog PRD through normal PRD authoring and review, or closes it. Autopilot never drains `dev/local/prds/hold/`, and this stub is never auto-promoted.

## Requirements

### Must have
- A triage decision for ledger key `d190c6d3ccb8`: a backlog PRD, or closed.

### Nice to have
- None until triage.

## Implementation

### Module: triage
- **Location**: `dev/local/prds/hold/`
- **Responsibility**: hold ledger key `d190c6d3ccb8` from `00217-bound-concurrent-review-sessions-with-a-slot-semaphore-v1.md` until a human triages it
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
