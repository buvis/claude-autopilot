---
catchup: skip
design: skip
ledger: deferred/202610031511-deferred.json
ledger_key: c4ac572ad5ca
source_prd: 00256-finish-the-review-verbs-before-release-v1.md
severity: high
---

# Triage: R3: scope beyond the PRD - the Ref-column mechanism, review_close.close() run...

> **Closed 2026-10-05 (operator triage): ratified.** The Ref column replaces
> brittle issue-wording matching (the orchestrator rewords issues), shipped in
> v0.9.0 with tests, and PRD 00264's coverage check builds on it.

## Problem

Deferred finding with no PRD owner when this stub was minted: batch `202610031511`, ledger `deferred/202610031511-deferred.json`, type `cap-overflow`, cycle `2`, consensus `1/4`, op_id `6dcd9cbf27b9-dd2`, raised against `00256-finish-the-review-verbs-before-release-v1.md`.

Issue: R3: scope beyond the PRD - the Ref-column mechanism, review_close.close() running the cross-check itself, the new refused: findings_mismatch result and the findings_cross_check key. Design-sanctioned but not asked for by the PRD, and it changes the review-table format.

## Solution

Attended triage. A human promotes this finding into a backlog PRD through normal PRD authoring and review, or closes it. Autopilot never drains `docs/dev/project-management/prds/hold/`, and this stub is never auto-promoted.

## Requirements

### Must have
- A triage decision for ledger key `c4ac572ad5ca`: a backlog PRD, or closed.

### Nice to have
- None until triage.

## Implementation

### Module: triage
- **Location**: `docs/dev/project-management/prds/hold/`
- **Responsibility**: hold ledger key `c4ac572ad5ca` from `00256-finish-the-review-verbs-before-release-v1.md` until a human triages it
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
