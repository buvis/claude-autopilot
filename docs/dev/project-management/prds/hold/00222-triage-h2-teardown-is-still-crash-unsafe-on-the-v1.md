---
catchup: skip
design: skip
ledger: deferred/202609252154-deferred.json
ledger_key: 56d35c9d46d7
source_prd: 00215-assemble-a-drained-wave-onto-one-branch-v1.md
severity: high
---

# Triage: H2: teardown is still crash-unsafe on the real pre-save crash. _drain_lane wr...

## Problem

Deferred finding with no PRD owner when this stub was minted: batch `202609252154`, ledger `deferred/202609252154-deferred.json`, type `cap-overflow`, cycle `2`, consensus `1/4`, raised against `00215-assemble-a-drained-wave-onto-one-branch-v1.md`.

Issue: H2: teardown is still crash-unsafe on the real pre-save crash. _drain_lane writes lane[held_prds] and _assemble_lane writes lane[status] in memory only; the single save() is at wave_assemble.py:591, after the git worktree remove / branch -D at :524-526, so a crash in that window loses held_prds, status, batch_id and worktree_removed together. On the rerun lane_status either returns unfinished (the merged lane is relabelled unfinished, lands in kept, exit flips 0 to 3, the report drops non-roster PRDs and blanks the lane batch id, and worktree_removed is never set so every later rerun repeats it) or returns the stale drained, in which case lane_files_and_notes runs subprocess.run with a removed cwd and raises an uncaught OSError that wave_cli.run does not catch. Task 12's new test cannot catch either: it runs a full successful assemble first and then deletes only worktree_removed.

## Solution

Attended triage. A human promotes this finding into a backlog PRD through normal PRD authoring and review, or closes it. Autopilot never drains `dev/local/prds/hold/`, and this stub is never auto-promoted.

## Requirements

### Must have
- A triage decision for ledger key `56d35c9d46d7`: a backlog PRD, or closed.

### Nice to have
- None until triage.

## Implementation

### Module: triage
- **Location**: `dev/local/prds/hold/`
- **Responsibility**: hold ledger key `56d35c9d46d7` from `00215-assemble-a-drained-wave-onto-one-branch-v1.md` until a human triages it
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
