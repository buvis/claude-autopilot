---
catchup: skip
design: skip
ledger: deferred/202610111300-deferred.json
ledger_key: 87ce20aed208
source_prd: 00278-make-release-checks-tell-truth-v1.md
severity: high
---

# Triage: state-schema.md documents CLI invocations that do not exist: autopilot group-...

## Problem

Deferred finding with no PRD owner when this stub was minted: batch `202610111300`, ledger `deferred/202610111300-deferred.json`, type `cap-overflow`, cycle `2`, consensus `1/3`, raised against `00278-make-release-checks-tell-truth-v1.md`.

Issue: state-schema.md documents CLI invocations that do not exist: autopilot group-rework <state.json> and autopilot review-stage <state.json> <review-file>. The real parsers take group-rework --findings <path> and review-stage --cycle-id --gate-command [--state ...]. test_doc_contract goes green on a false doc.

## Solution

Attended triage. A human promotes this finding into a backlog PRD through normal PRD authoring and review, or closes it. Autopilot never drains `docs/dev/project-management/prds/hold/`, and this stub is never auto-promoted.

## Requirements

### Must have
- A triage decision for ledger key `87ce20aed208`: a backlog PRD, or closed.

### Nice to have
- None until triage.

## Implementation

### Module: triage
- **Location**: `docs/dev/project-management/prds/hold/`
- **Responsibility**: hold ledger key `87ce20aed208` from `00278-make-release-checks-tell-truth-v1.md` until a human triages it
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
