---
catchup: skip
design: skip
ledger: deferred/202609252154-deferred.json
ledger_key: d799b85ccee1
source_prd: 00223-enter-the-build-gate-in-one-cli-call-v1.md
severity: high
---

# Triage: enter.py is 414 lines against the PRD Phase 0 exit criterion "under 400 lines...

## Problem

Deferred finding with no PRD owner when this stub was minted: batch `202609252154`, ledger `deferred/202609252154-deferred.json`, type `cap-overflow`, cycle `2`, consensus `4/4`, raised against `00223-enter-the-build-gate-in-one-cli-call-v1.md`.

Issue: enter.py is 414 lines against the PRD Phase 0 exit criterion "under 400 lines" (computed: over by 14). Named fixes: move the three side-effect helpers (_git_head_sha, _record_resume_row, _review_log_has_dispatch_line) to a sibling module, inline the single-caller _prepare_tree into _bootstrap, or trim 14 lines of restating docstring.

## Solution

Attended triage. A human promotes this finding into a backlog PRD through normal PRD authoring and review, or closes it. Autopilot never drains `dev/local/prds/hold/`, and this stub is never auto-promoted.

## Requirements

### Must have
- A triage decision for ledger key `d799b85ccee1`: a backlog PRD, or closed.

### Nice to have
- None until triage.

## Implementation

### Module: triage
- **Location**: `dev/local/prds/hold/`
- **Responsibility**: hold ledger key `d799b85ccee1` from `00223-enter-the-build-gate-in-one-cli-call-v1.md` until a human triages it
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
