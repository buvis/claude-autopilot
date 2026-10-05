---
catchup: skip
design: skip
ledger: deferred/202610031511-deferred.json
ledger_key: e4952a3686e6
source_prd: 00256-finish-the-review-verbs-before-release-v1.md
severity: critical
---

# Triage: R1: the PRD exit criterion is false at HEAD - bash dev/bin/release-checks exi...

> **Closed 2026-10-05 (operator triage): fixed.** c78527c excludes
> `cli/fixtures/` from the porcelain prose scan (frozen records, like
> `golden/`). `bash dev/bin/release-checks` at c78527c: `PASS 2572 FAIL 0
> SKIP 0 EXIT 0`.

## Problem

Deferred finding with no PRD owner when this stub was minted: batch `202610031511`, ledger `deferred/202610031511-deferred.json`, type `cap-overflow`, cycle `2`, consensus `1/4`, op_id `6dcd9cbf27b9-dd23`, raised against `00256-finish-the-review-verbs-before-release-v1.md`.

Issue: R1: the PRD exit criterion is false at HEAD - bash dev/bin/release-checks exits 1 (PASS 2590 FAIL 1 SKIP 0 EXIT 1, measured twice with no concurrent suites). test_no_gate_parses_porcelain_by_hand is tripped by skills/run-autopilot/cli/fixtures/00256-review-1.md, a fixture this cycles task 12 added in dbe0ad5; the prose test predates this PRD. Fix: exempt the fixture path in test_store_tree_prose.py _EXEMPT, or exclude cli/fixtures/ from _prose_files().

## Solution

Attended triage. A human promotes this finding into a backlog PRD through normal PRD authoring and review, or closes it. Autopilot never drains `docs/dev/project-management/prds/hold/`, and this stub is never auto-promoted.

## Requirements

### Must have
- A triage decision for ledger key `e4952a3686e6`: a backlog PRD, or closed.

### Nice to have
- None until triage.

## Implementation

### Module: triage
- **Location**: `docs/dev/project-management/prds/hold/`
- **Responsibility**: hold ledger key `e4952a3686e6` from `00256-finish-the-review-verbs-before-release-v1.md` until a human triages it
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
