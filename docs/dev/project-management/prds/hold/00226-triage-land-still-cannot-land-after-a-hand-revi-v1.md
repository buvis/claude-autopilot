---
catchup: skip
design: skip
ledger: deferred/202609252154-deferred.json
ledger_key: eaf3898e53e1
source_prd: 00216-review-the-assembled-wave-and-run-a-wave-end-to-end-v1.md
severity: high
---

# Triage: `land` still cannot land after a hand review. `review_failed` returns 4 uncon...

## Problem

Deferred finding with no PRD owner when this stub was minted: batch `202609252154`, ledger `deferred/202609252154-deferred.json`, type `cap-overflow`, cycle `2`, consensus `2/4`, raised against `00216-review-the-assembled-wave-and-run-a-wave-end-to-end-v1.md`.

Issue: `land` still cannot land after a hand review. `review_failed` returns 4 unconditionally via `_land_review_failed`, even after the operator moved the stub to the assembly worktree's `prds/done/`; `assembled`/`assembled_partial` are refused as 'not landable'. The only route is hand-editing `wave.json` status to `converged`, which nothing documents or tests. The PRD's Edge case requires a later `wave land` after a hand review to still land (skills/run-autopilot/cli/wave_review.py:522)

## Solution

Attended triage. A human promotes this finding into a backlog PRD through normal PRD authoring and review, or closes it. Autopilot never drains `dev/local/prds/hold/`, and this stub is never auto-promoted.

## Requirements

### Must have
- A triage decision for ledger key `eaf3898e53e1`: a backlog PRD, or closed.

### Nice to have
- None until triage.

## Implementation

### Module: triage
- **Location**: `dev/local/prds/hold/`
- **Responsibility**: hold ledger key `eaf3898e53e1` from `00216-review-the-assembled-wave-and-run-a-wave-end-to-end-v1.md` until a human triages it
- **Exports**: none

### Dependencies
- triage: No dependencies (foundation)

## Tasks

### Phase 0: Foundation
- [ ] triage: promote to backlog or close - Acceptance: this file is no longer under dev/local/prds/hold/

### Phase 1: Core
No implementation tasks until attended triage.

## Success Criteria

- This file is no longer under `dev/local/prds/hold/`.
