---
catchup: skip
design: skip
ledger: deferred/202609252154-deferred.json
ledger_key: dba0c0eb393a
source_prd: 00216-review-the-assembled-wave-and-run-a-wave-end-to-end-v1.md
severity: high
---

# Triage: The wave feature family assumes docs/dev/project-management is gitignored (de...

## Problem

Deferred finding with no PRD owner when this stub was minted: batch `202609252154`, ledger `deferred/202609252154-deferred.json`, type `requirements-ambiguity`, cycle `1`, consensus `3/4`, raised against `00216-review-the-assembled-wave-and-run-a-wave-end-to-end-v1.md`.

Issue: The wave feature family assumes docs/dev/project-management is gitignored (design Architecture fit, test_wave_launch.py:71 fixture), but commit 5d9036a in this same range states the store is tracked and never age-purged, and git check-ignore confirms the path is NOT ignored in this repo. review()/launch() dirty-tree gates therefore refuse in a real managed repo, and a tracked store would also seed the assembly worktree with backlog PRDs the nested loop could select

## Solution

Attended triage. A human promotes this finding into a backlog PRD through normal PRD authoring and review, or closes it. Autopilot never drains `dev/local/prds/hold/`, and this stub is never auto-promoted.

## Requirements

### Must have
- A triage decision for ledger key `dba0c0eb393a`: a backlog PRD, or closed.

### Nice to have
- None until triage.

## Implementation

### Module: triage
- **Location**: `dev/local/prds/hold/`
- **Responsibility**: hold ledger key `dba0c0eb393a` from `00216-review-the-assembled-wave-and-run-a-wave-end-to-end-v1.md` until a human triages it
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
