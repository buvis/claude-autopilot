---
catchup: skip
design: skip
ledger: deferred/202610111300-deferred.json
ledger_key: dd31e69f2870
source_prd: 00271-guard-v2-structural-delegation-check-v1.md
severity: high
---

# Triage: [cycle 2 R2] The rework for prior R12 introduced a false-allow: the SKILL.md...

## Problem

Deferred finding with no PRD owner when this stub was minted: batch `202610111300`, ledger `deferred/202610111300-deferred.json`, type `cap-overflow`, consensus `3/3`, raised against `00271-guard-v2-structural-delegation-check-v1.md`.

Issue: [cycle 2 R2] The rework for prior R12 introduced a false-allow: the SKILL.md follow phrase is negated by any negation word in the five words before the verb, even across a clause boundary. `_ordered_to_follow` calls `_negated(text, end, match.start())`, so the floor is the path end, not the verb's clause start. `Read skills/work/SKILL.md, do not stop, then follow it for every task.` is allowed. Use `max(end, start of the verb's clause)` as the floor.

## Solution

Attended triage. A human promotes this finding into a backlog PRD through normal PRD authoring and review, or closes it. Autopilot never drains `docs/dev/project-management/prds/hold/`, and this stub is never auto-promoted.

## Requirements

### Must have
- A triage decision for ledger key `dd31e69f2870`: a backlog PRD, or closed.

### Nice to have
- None until triage.

## Implementation

### Module: triage
- **Location**: `docs/dev/project-management/prds/hold/`
- **Responsibility**: hold ledger key `dd31e69f2870` from `00271-guard-v2-structural-delegation-check-v1.md` until a human triages it
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

## Triage 2026-10-14

Promoted into PRD 00307 (`guard-citations-and-replay-contract`): the negation floor becomes the verb's clause start, pinned by `test_negation_in_previous_clause_does_not_excuse_follow`. Closed into `done/`.
