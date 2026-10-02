---
catchup: skip
design: skip
ledger: deferred/202609252154-deferred.json
ledger_key: f9c890a6856c
source_prd: 00223-enter-the-build-gate-in-one-cli-call-v1.md
severity: high
---

# Triage: The enter stop-table rows for fs_error and park_halt each name one owning sec...

## Problem

Deferred finding with no PRD owner when this stub was minted: batch `202609252154`, ledger `deferred/202609252154-deferred.json`, type `cap-overflow`, cycle `2`, consensus `2/4`, raised against `00223-enter-the-build-gate-in-one-cli-call-v1.md`.

Issue: The enter stop-table rows for fs_error and park_halt each name one owning section while the code now raises them from several distinct causes. fs_error fires at enter.py:158 (mkdir failed), :161 (shallow --prds, no grandparent) and :358 (design-doc read failed), but its row routes only to the mkdir block. park_halt fires at :184 (exit 5, systemic halt) and :188 (unmapped park exit code), but its row names only exit-code row 5. Fix: state in both rows that detail selects the owner, as the deferred_io row already does, and name the design-gate non-zero branch for the design-doc cause.

## Solution

Attended triage. A human promotes this finding into a backlog PRD through normal PRD authoring and review, or closes it. Autopilot never drains `dev/local/prds/hold/`, and this stub is never auto-promoted.

## Requirements

### Must have
- A triage decision for ledger key `f9c890a6856c`: a backlog PRD, or closed.

### Nice to have
- None until triage.

## Implementation

### Module: triage
- **Location**: `dev/local/prds/hold/`
- **Responsibility**: hold ledger key `f9c890a6856c` from `00223-enter-the-build-gate-in-one-cli-call-v1.md` until a human triages it
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
