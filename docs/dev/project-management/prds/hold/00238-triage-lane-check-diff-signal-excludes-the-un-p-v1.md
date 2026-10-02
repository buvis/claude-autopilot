---
catchup: skip
design: skip
ledger: deferred/202610021244-deferred.json
ledger_key: 9f75f53ae7f7
source_prd: 00236-track-the-store-without-tripping-the-loop-v1.md
severity: high
---

# Triage: lane_check.diff_signal excludes the un-prefixed STORE_EXCLUDE_PATHSPECS with...

## Problem

Deferred finding with no PRD owner when this stub was minted: batch `202610021244`, ledger `deferred/202610021244-deferred.json`, type `cap-overflow`, cycle `2`, consensus `2/4`, raised against `00236-track-the-store-without-tripping-the-loop-v1.md`.

Issue: lane_check.diff_signal excludes the un-prefixed STORE_EXCLUDE_PATHSPECS with cwd=repo_root, so in a bare-repo-backed project (store at .claude/docs/dev/project-management under a $HOME work-tree) the exclusion misses the store, store commits read as production paths, and every solo-lane PRD escalates to the full lane. Task 10 fixed only the flat layout; the derived prefix task 9 threaded into foreign_dirty and record_store was never threaded into lane_check.

## Solution

Attended triage. A human promotes this finding into a backlog PRD through normal PRD authoring and review, or closes it. Autopilot never drains `docs/dev/project-management/prds/hold/`, and this stub is never auto-promoted.

## Requirements

### Must have
- A triage decision for ledger key `9f75f53ae7f7`: a backlog PRD, or closed.

### Nice to have
- None until triage.

## Implementation

### Module: triage
- **Location**: `docs/dev/project-management/prds/hold/`
- **Responsibility**: hold ledger key `9f75f53ae7f7` from `00236-track-the-store-without-tripping-the-loop-v1.md` until a human triages it
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
