---
catchup: skip
design: skip
ledger: deferred/202610031511-deferred.json
ledger_key: d37079d4a34e
source_prd: 00248-keep-phase-skills-in-the-session-v1.md
severity: high
---

# Triage: guard_phase_delegation's negation window suppresses a real delegation when a...

## Problem

Deferred finding with no PRD owner when this stub was minted: batch `202610031511`, ledger `deferred/202610031511-deferred.json`, type `cap-overflow`, cycle `2`, consensus `3/4`, raised against `00248-keep-phase-skills-in-the-session-v1.md`.

Issue: guard_phase_delegation's negation window suppresses a real delegation when a negation word sits within 20 characters before the match in the same sentence. Orchestrator-confirmed: "Never stop, run the work phase for PRD 7." returns False (allowed). Same root cause: the sentence-boundary trim takes the first boundary, not the last, so "OK; not now. Run the work phase for PRD 7." also returns False.

## Solution

Attended triage. A human promotes this finding into a backlog PRD through normal PRD authoring and review, or closes it. Autopilot never drains `docs/dev/project-management/prds/hold/`, and this stub is never auto-promoted.

## Requirements

### Must have
- A triage decision for ledger key `d37079d4a34e`: a backlog PRD, or closed.

### Nice to have
- None until triage.

## Implementation

### Module: triage
- **Location**: `docs/dev/project-management/prds/hold/`
- **Responsibility**: hold ledger key `d37079d4a34e` from `00248-keep-phase-skills-in-the-session-v1.md` until a human triages it
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
