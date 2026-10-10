---
catchup: skip
design: skip
ledger: deferred/202610101000-deferred.json
ledger_key: 03cf94591ace
source_prd: 00270-trust-only-real-gate-runs-v1.md
severity: 🟠
---

# Triage: `run_gate` returns before spawning when the pre-run dirty check fires, so the...

## Triage decision (2026-10-10)

Closed, not promoted (operator, 2026-10-10). PRD 00276 stops the product's own scratch files from counting as dirt; a tree with real dirt outside the store still skips the gate, by design.

## Problem

Deferred finding with no PRD owner when this stub was minted: batch `202610101000`, ledger `deferred/202610101000-deferred.json`, type `deferred_decision`, cycle `2`, raised against `00270-trust-only-real-gate-runs-v1.md`.

Issue: `run_gate` returns before spawning when the pre-run dirty check fires, so the gate never runs on a tree dirty outside the store.

## Solution

Attended triage. A human promotes this finding into a backlog PRD through normal PRD authoring and review, or closes it. Autopilot never drains `docs/dev/project-management/prds/hold/`, and this stub is never auto-promoted.

## Requirements

### Must have
- A triage decision for ledger key `03cf94591ace`: a backlog PRD, or closed.

### Nice to have
- None until triage.

## Implementation

### Module: triage
- **Location**: `docs/dev/project-management/prds/hold/`
- **Responsibility**: hold ledger key `03cf94591ace` from `00270-trust-only-real-gate-runs-v1.md` until a human triages it
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
