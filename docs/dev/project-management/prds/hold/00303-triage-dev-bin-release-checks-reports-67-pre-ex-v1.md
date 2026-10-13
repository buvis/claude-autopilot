---
catchup: skip
design: skip
ledger: deferred/202610111300-deferred.json
ledger_key: 185654f0d425
source_prd: 00279-run-one-exact-reuse-rule-v1.md
severity: high
---

# Triage: dev/bin/release-checks reports 67 pre-existing failures at HEAD aea2279, all...

## Problem

Deferred finding with no PRD owner when this stub was minted: batch `202610111300`, ledger `deferred/202610111300-deferred.json`, type `deferred_decision`, cycle `1`, raised against `00279-run-one-exact-reuse-rule-v1.md`.

Issue: dev/bin/release-checks reports 67 pre-existing failures at HEAD aea2279, all in skills/run-autopilot/cli/test_gate_findings_unread_shapes.py (cli/gate.py _is_unread_line), untouched by PRD 00279

## Solution

Attended triage. A human promotes this finding into a backlog PRD through normal PRD authoring and review, or closes it. Autopilot never drains `docs/dev/project-management/prds/hold/`, and this stub is never auto-promoted.

## Requirements

### Must have
- A triage decision for ledger key `185654f0d425`: a backlog PRD, or closed.

### Nice to have
- None until triage.

## Implementation

### Module: triage
- **Location**: `docs/dev/project-management/prds/hold/`
- **Responsibility**: hold ledger key `185654f0d425` from `00279-run-one-exact-reuse-rule-v1.md` until a human triages it
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
