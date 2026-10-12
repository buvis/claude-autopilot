---
catchup: skip
design: skip
ledger: deferred/202610111300-deferred.json
ledger_key: 2464402736d2
source_prd: 00271-guard-v2-structural-delegation-check-v1.md
severity: high
---

# Triage: The contract says exit 1 when ANY per-task/agoge/reviewer record is refused,...

## Problem

Deferred finding with no PRD owner when this stub was minted: batch `202610111300`, ledger `deferred/202610111300-deferred.json`, type `contract-conflict`, raised against `00271-guard-v2-structural-delegation-check-v1.md`.

Detail: The contract says exit 1 when ANY per-task/agoge/reviewer record is refused, AND separately when a pinned deny id is allowed. The pinned deny id toolu_01Ku4TbcQoeik6ZLf5XkkAuD (general-purpose, "Resume work phase for PRD 00242, task 1 onward") buckets as per-task because its description matches \btask\s+1\b, and it MUST be refused. So its correct refusal trips the first clause: exit 1 is forced no matter what the predicate does. Only three resolutions exist and the task forbids two of them (change buckets, change the deny list); the third is to exempt pinned-deny ids from the bucket-refusal clause, which cannot mask a regression (an ALLOWED pinned id still fails, a refused non-pinned per-task record still fails). Left unapplied: it is a design-doc change, not an implementor call. Verbatim contract kept, exit 1 recorded as evidence, same handling as task 7s unreachable fails-at-base criterion.

## Solution

Attended triage. A human promotes this finding into a backlog PRD through normal PRD authoring and review, or closes it. Autopilot never drains `docs/dev/project-management/prds/hold/`, and this stub is never auto-promoted.

## Requirements

### Must have
- A triage decision for ledger key `2464402736d2`: a backlog PRD, or closed.

### Nice to have
- None until triage.

## Implementation

### Module: triage
- **Location**: `docs/dev/project-management/prds/hold/`
- **Responsibility**: hold ledger key `2464402736d2` from `00271-guard-v2-structural-delegation-check-v1.md` until a human triages it
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
