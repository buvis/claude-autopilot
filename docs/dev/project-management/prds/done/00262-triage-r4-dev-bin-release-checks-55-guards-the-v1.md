---
catchup: skip
design: skip
ledger: deferred/202610031511-deferred.json
ledger_key: 678c6f3c1d2b
source_prd: 00256-finish-the-review-verbs-before-release-v1.md
severity: high
---

# Triage: R4: dev/bin/release-checks:55 guards the fail-open case with -z "$f" (empty)...

> **Closed 2026-10-05 (operator triage): fixed.** c78527c makes line 55 a
> numeric `"${f:-0}" -eq 0` check, pinned by
> `test_nonzero_exit_with_a_literal_zero_failed_is_not_reported_green`
> (fails against the old line).

## Problem

Deferred finding with no PRD owner when this stub was minted: batch `202610031511`, ledger `deferred/202610031511-deferred.json`, type `cap-overflow`, cycle `2`, consensus `1/4`, op_id `6dcd9cbf27b9-dd3`, raised against `00256-finish-the-review-verbs-before-release-v1.md`.

Issue: R4: dev/bin/release-checks:55 guards the fail-open case with -z "$f" (empty) while run_harness:74 uses the numeric "$f" -eq 0, so a block printing an explicit '0 failed' with a non-zero exit still reports green. Confirmed by reading both helpers.

## Solution

Attended triage. A human promotes this finding into a backlog PRD through normal PRD authoring and review, or closes it. Autopilot never drains `docs/dev/project-management/prds/hold/`, and this stub is never auto-promoted.

## Requirements

### Must have
- A triage decision for ledger key `678c6f3c1d2b`: a backlog PRD, or closed.

### Nice to have
- None until triage.

## Implementation

### Module: triage
- **Location**: `docs/dev/project-management/prds/hold/`
- **Responsibility**: hold ledger key `678c6f3c1d2b` from `00256-finish-the-review-verbs-before-release-v1.md` until a human triages it
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
