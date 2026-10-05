---
catchup: skip
design: skip
ledger: deferred/202610031511-deferred.json
ledger_key: bba4a7097dfa
source_prd: 00256-finish-the-review-verbs-before-release-v1.md
severity: critical
---

# Triage: cycle 2/2 cap reached with an unresolved CRITICAL: bash dev/bin/release-check...

## Problem

Deferred finding with no PRD owner when this stub was minted: batch `202610031511`, ledger `deferred/202610031511-deferred.json`, type `stall`, site `cap_critical`, op_id `6dcd9cbf27b9`, raised against `00256-finish-the-review-verbs-before-release-v1.md`.

Detail: cycle 2/2 cap reached with an unresolved CRITICAL: bash dev/bin/release-checks exits 1 at HEAD 6bca6b5 (PASS 2590 FAIL 1 SKIP 0 EXIT 1), falsifying PRD Success Metric 1. test_no_gate_parses_porcelain_by_hand is tripped by cli/fixtures/00256-review-1.md, the fixture task 12 added in dbe0ad5; the prose test predates this PRD. Fix: exempt that fixture path in test_store_tree_prose.py _EXEMPT, or exclude cli/fixtures/ from _prose_files(). 22 further findings deferred (3 high: PRD-vs-design one-directional cross-check, Ref-column scope beyond the PRD, release-checks:55 -z vs numeric fail-open guard). Review: docs/dev/project-management/reviews/00256-finish-the-review-verbs-before-release-v1-review-2.md

## Solution

Attended triage. A human promotes this finding into a backlog PRD through normal PRD authoring and review, or closes it. Autopilot never drains `docs/dev/project-management/prds/hold/`, and this stub is never auto-promoted.

## Requirements

### Must have
- A triage decision for ledger key `bba4a7097dfa`: a backlog PRD, or closed.

### Nice to have
- None until triage.

## Implementation

### Module: triage
- **Location**: `docs/dev/project-management/prds/hold/`
- **Responsibility**: hold ledger key `bba4a7097dfa` from `00256-finish-the-review-verbs-before-release-v1.md` until a human triages it
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
