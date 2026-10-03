---
catchup: skip
design: skip
ledger: deferred/202610031511-deferred.json
ledger_key: 92b585072b81
source_prd: 00241-bound-rework-batches-by-file-v1.md
severity: high
---

# Triage: _LINE_SUFFIX still misses three citation shapes the canonical consolidate_fin...

## Problem

Deferred finding with no PRD owner when this stub was minted: batch `202610031511`, ledger `deferred/202610031511-deferred.json`, type `cap-overflow`, cycle `2`, consensus `1/4`, raised against `00241-bound-rework-batches-by-file-v1.md`.

Issue: _LINE_SUFFIX still misses three citation shapes the canonical consolidate_findings._TRAILING_LINENO_RE strips -- (line 3), (lines 18-22, 423) and #L12-L20 -- so each still becomes its own junk key and burns a cap slot. Unresolved remainder of cycle 1 file_key HIGH.

## Solution

Attended triage. A human promotes this finding into a backlog PRD through normal PRD authoring and review, or closes it. Autopilot never drains `docs/dev/project-management/prds/hold/`, and this stub is never auto-promoted.

## Requirements

### Must have
- A triage decision for ledger key `92b585072b81`: a backlog PRD, or closed.

### Nice to have
- None until triage.

## Implementation

### Module: triage
- **Location**: `docs/dev/project-management/prds/hold/`
- **Responsibility**: hold ledger key `92b585072b81` from `00241-bound-rework-batches-by-file-v1.md` until a human triages it
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
