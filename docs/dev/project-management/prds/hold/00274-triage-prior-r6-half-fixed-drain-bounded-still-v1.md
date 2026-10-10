---
catchup: skip
design: skip
ledger: deferred/202610101000-deferred.json
ledger_key: 7e7e4a58095b
source_prd: 00270-trust-only-real-gate-runs-v1.md
severity: high
---

# Triage: Prior R6 half fixed: _drain_bounded still writes to the log sink with no OSEr...

## Problem

Deferred finding with no PRD owner when this stub was minted: batch `202610101000`, ledger `deferred/202610101000-deferred.json`, type `cap-overflow`, cycle `2`, consensus `3/4`, raised against `00270-trust-only-real-gate-runs-v1.md`.

Issue: Prior R6 half fixed: _drain_bounded still writes to the log sink with no OSError guard, so a write error raises out of run_gate before _reap and leaks the gate process group.

## Solution

Attended triage. A human promotes this finding into a backlog PRD through normal PRD authoring and review, or closes it. Autopilot never drains `docs/dev/project-management/prds/hold/`, and this stub is never auto-promoted.

## Requirements

### Must have
- A triage decision for ledger key `7e7e4a58095b`: a backlog PRD, or closed.

### Nice to have
- None until triage.

## Implementation

### Module: triage
- **Location**: `docs/dev/project-management/prds/hold/`
- **Responsibility**: hold ledger key `7e7e4a58095b` from `00270-trust-only-real-gate-runs-v1.md` until a human triages it
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
