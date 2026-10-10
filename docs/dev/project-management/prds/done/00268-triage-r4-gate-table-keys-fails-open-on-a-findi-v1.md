---
catchup: skip
design: skip
ledger: deferred/202610071409-deferred.json
ledger_key: 6597ba533369
source_prd: 00265-close-the-critical-row-escapes-v1.md
severity: high
---

# Triage: R4: gate._table_keys fails open on a findings table whose header is not recog...

> **Triaged 2026-10-10 (operator):** folded into `prds/backlog/00269-sweep-every-findings-token-v1.md`, whose token sweep refuses any `[m/n]` token or pipe row the parser did not consume, an unrecognised header included. Closed here.

## Problem

Deferred finding with no PRD owner when this stub was minted: batch `202610071409`, ledger `deferred/202610071409-deferred.json`, type `cap-overflow`, cycle `2`, consensus `1/4`, raised against `00265-close-the-critical-row-escapes-v1.md`.

Issue: R4: gate._table_keys fails open on a findings table whose header is not recognised. A CRITICAL row under an unrecognised header gets no task, no record and no refusal - the same escape class as #2.

## Solution

Attended triage. A human promotes this finding into a backlog PRD through normal PRD authoring and review, or closes it. Autopilot never drains `docs/dev/project-management/prds/hold/`, and this stub is never auto-promoted.

## Requirements

### Must have
- A triage decision for ledger key `6597ba533369`: a backlog PRD, or closed.

### Nice to have
- None until triage.

## Implementation

### Module: triage
- **Location**: `docs/dev/project-management/prds/hold/`
- **Responsibility**: hold ledger key `6597ba533369` from `00265-close-the-critical-row-escapes-v1.md` until a human triages it
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
