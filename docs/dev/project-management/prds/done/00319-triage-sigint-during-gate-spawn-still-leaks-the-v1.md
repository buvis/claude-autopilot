---
catchup: skip
design: skip
ledger: deferred/202610141430-deferred.json
ledger_key: 8b3657b45a74
source_prd: 00311-verify-reports-what-the-gate-did-v1.md
severity: high
---

# Triage: SIGINT during gate spawn still leaks the gate process: _child_from_exception...

## Problem

Deferred finding with no PRD owner when this stub was minted: batch `202610141430`, ledger `deferred/202610141430-deferred.json`, type `cap-overflow`, cycle `2`, consensus `4/4`, raised against `00311-verify-reports-what-the-gate-did-v1.md`.

Issue: SIGINT during gate spawn still leaks the gate process: _child_from_exception can recover a Popen whose pid is None, so _kill_gate raises TypeError (masking the KeyboardInterrupt) and the forked gate survives while the outer LOCK_UN releases the flock. A second hole sits between Popen() returning and the proc= store. Measured 68 leaked gates in 1500 trials. Remedy: defer SIGINT the way SIGTERM is deferred, which also removes _child_from_exception and _POPEN_TYPE.

## Solution

Attended triage. A human promotes this finding into a backlog PRD through normal PRD authoring and review, or closes it. Autopilot never drains `docs/dev/project-management/prds/hold/`, and this stub is never auto-promoted.

## Requirements

### Must have
- A triage decision for ledger key `8b3657b45a74`: a backlog PRD, or closed.

### Nice to have
- None until triage.

## Implementation

### Module: triage
- **Location**: `docs/dev/project-management/prds/hold/`
- **Responsibility**: hold ledger key `8b3657b45a74` from `00311-verify-reports-what-the-gate-did-v1.md` until a human triages it
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

## Triage 2026-10-15

Promoted into PRD 00322 (`kill-the-gate-on-every-signal`) together with agoge-2026-10-15 packets 10 (SIGHUP), 11 (the replay runner) and 22 (the shared lock deadline): one signal guard for SIGTERM, SIGINT and SIGHUP, and `_child_from_exception` removed. Closed into `done/`.
