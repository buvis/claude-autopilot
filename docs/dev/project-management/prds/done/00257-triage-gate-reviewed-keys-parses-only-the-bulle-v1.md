---
catchup: skip
design: skip
ledger: deferred/202610031511-deferred.json
ledger_key: 5a00e20d5b7f
source_prd: 00256-finish-the-review-verbs-before-release-v1.md
severity: critical
---

# Triage: gate._reviewed_keys parses only the bullet finding shape, so the --findings c...

> **Closed 2026-10-05 (operator triage): fixed.** 996fc70 (00256 task 12)
> makes `_reviewed_keys` read the pipe table too (`gate.py:334-355`, `_table_keys`).

## Problem

Deferred finding with no PRD owner when this stub was minted: batch `202610031511`, ledger `deferred/202610031511-deferred.json`, type `review-finding`, cycle `1`, consensus `2/4`, raised against `00256-finish-the-review-verbs-before-release-v1.md`.

Issue: gate._reviewed_keys parses only the bullet finding shape, so the --findings cross-check reports mismatch on every real pipe-table review file and review_close.close() refuses with exit 2, stalling the review loop

## Solution

Attended triage. A human promotes this finding into a backlog PRD through normal PRD authoring and review, or closes it. Autopilot never drains `docs/dev/project-management/prds/hold/`, and this stub is never auto-promoted.

## Requirements

### Must have
- A triage decision for ledger key `5a00e20d5b7f`: a backlog PRD, or closed.

### Nice to have
- None until triage.

## Implementation

### Module: triage
- **Location**: `docs/dev/project-management/prds/hold/`
- **Responsibility**: hold ledger key `5a00e20d5b7f` from `00256-finish-the-review-verbs-before-release-v1.md` until a human triages it
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
