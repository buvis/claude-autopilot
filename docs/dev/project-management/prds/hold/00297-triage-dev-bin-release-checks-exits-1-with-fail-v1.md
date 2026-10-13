---
catchup: skip
design: skip
ledger: deferred/202610111300-deferred.json
ledger_key: 7281e8f0c729
source_prd: 00278-make-release-checks-tell-truth-v1.md
severity: high
---

# Triage: dev/bin/release-checks exits 1 with FAIL 67 at 0d525d4; all 67 failures are i...

## Problem

Deferred finding with no PRD owner when this stub was minted: batch `202610111300`, ledger `deferred/202610111300-deferred.json`, type `pre-existing-failure`, raised against `00278-make-release-checks-tell-truth-v1.md`.

Issue: dev/bin/release-checks exits 1 with FAIL 67 at 0d525d4; all 67 failures are in skills/run-autopilot/cli/test_gate_findings_unread_shapes.py, which was already gated before PRD 00278 and fails identically at task base 6c91048 (67 failed, 38 passed). That file was authored by PRD 00277 task 7, and 00277 is parked in hold/ on a blocking escalation, so its tests pin gate.py behavior that was never implemented.

## Solution

Attended triage. A human promotes this finding into a backlog PRD through normal PRD authoring and review, or closes it. Autopilot never drains `docs/dev/project-management/prds/hold/`, and this stub is never auto-promoted.

## Requirements

### Must have
- A triage decision for ledger key `7281e8f0c729`: a backlog PRD, or closed.

### Nice to have
- None until triage.

## Implementation

### Module: triage
- **Location**: `docs/dev/project-management/prds/hold/`
- **Responsibility**: hold ledger key `7281e8f0c729` from `00278-make-release-checks-tell-truth-v1.md` until a human triages it
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
