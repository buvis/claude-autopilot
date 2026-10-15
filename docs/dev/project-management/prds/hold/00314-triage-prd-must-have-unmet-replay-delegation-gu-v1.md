---
catchup: skip
design: skip
ledger: deferred/202610141430-deferred.json
ledger_key: 283fd0b00a36
source_prd: 00307-guard-citations-and-replay-contract-v1.md
severity: critical
---

# Triage: PRD must-have unmet: replay_delegation_guard.py exits 1 with per-task refused...

## Problem

Deferred finding with no PRD owner when this stub was minted: batch `202610141430`, ledger `deferred/202610141430-deferred.json`, type `review-critical`, cycle `1`, consensus `3/4`, raised against `00307-guard-citations-and-replay-contract-v1.md`.

Issue: PRD must-have unmet: replay_delegation_guard.py exits 1 with per-task refused 3; ids toolu_011UqbqFtUDPuSeCiLLgMvEg and toolu_013ePUKbLDE7DLnbnGmgszzR still refused because _cited bounds its close/opener search by sentence

## Solution

Attended triage. A human promotes this finding into a backlog PRD through normal PRD authoring and review, or closes it. Autopilot never drains `docs/dev/project-management/prds/hold/`, and this stub is never auto-promoted.

## Requirements

### Must have
- A triage decision for ledger key `283fd0b00a36`: a backlog PRD, or closed.

### Nice to have
- None until triage.

## Implementation

### Module: triage
- **Location**: `docs/dev/project-management/prds/hold/`
- **Responsibility**: hold ledger key `283fd0b00a36` from `00307-guard-citations-and-replay-contract-v1.md` until a human triages it
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
