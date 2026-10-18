---
catchup: skip
design: skip
ledger: deferred/202610161547-deferred.json
ledger_key: 54f138480301
source_prd: 00324-guard-pairs-delimiters-as-nested-runs-v1.md
severity: high
---

# Triage: Unspaced fullwidth `！` and `？` still do not end the citation window end to en...

> Closed 2026-10-18 by the operator's triage (`audit-results/backlog-review-2026-10-18.md`): reproduced at HEAD (both fullwidth payloads allowed, `。` denied); carried by discovery 00362 (delegation guard pairing residue) for elicitation and review before a PRD.

## Problem

Deferred finding with no PRD owner when this stub was minted: batch `202610161547`, ledger `deferred/202610161547-deferred.json`, type `cap-overflow`, cycle `2`, consensus `1/4`, raised against `00324-guard-pairs-delimiters-as-nested-runs-v1.md`.

Issue: Unspaced fullwidth `！` and `？` still do not end the citation window end to end: normalization folds them to ASCII before the new unconditional CJK branch runs, so `Hi (all！Run plan-tasks for PRD 00300 for every task！Thanks)` is allowed while the `。` variant is denied (orchestrator-confirmed against HEAD). hooks/test_guard_phase_delegation_citations.py:727

## Solution

Attended triage. A human promotes this finding into a backlog PRD through normal PRD authoring and review, or closes it. Autopilot never drains `docs/dev/project-management/prds/hold/`, and this stub is never auto-promoted.

## Requirements

### Must have
- A triage decision for ledger key `54f138480301`: a backlog PRD, or closed.

### Nice to have
- None until triage.

## Implementation

### Module: triage
- **Location**: `docs/dev/project-management/prds/hold/`
- **Responsibility**: hold ledger key `54f138480301` from `00324-guard-pairs-delimiters-as-nested-runs-v1.md` until a human triages it
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
