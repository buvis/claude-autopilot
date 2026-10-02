---
catchup: skip
design: skip
ledger: deferred/202609252154-deferred.json
ledger_key: d2d2ea9958bb
source_prd: 00218-leave-sessions-at-task-boundaries-and-run-one-devon-round-v1.md
severity: high
---

# Triage: R13 regression: the rework grew this test file from 782 to 923 lines, and the...

## Problem

Deferred finding with no PRD owner when this stub was minted: batch `202609252154`, ledger `deferred/202609252154-deferred.json`, type `cap-overflow`, cycle `2`, consensus `2/4`, raised against `00218-leave-sessions-at-task-boundaries-and-run-one-devon-round-v1.md`.

Issue: R13 regression: the rework grew this test file from 782 to 923 lines, and the project's own style gate (`check_style_limits.py`, "files the diff pushed over 800") flags it (verified by the orchestrator: exit 1, `FILE | skills/run-autopilot/scripts/test_autopilot_cap_headroom.py | 923 lines`). The earlier split existed to stay under 800. Move the new `TaskBoundsWallTests` additions into a sibling file such as `test_cap_task_record_wall.py`, and add it to `dev/bin/release-checks`.

## Solution

Attended triage. A human promotes this finding into a backlog PRD through normal PRD authoring and review, or closes it. Autopilot never drains `dev/local/prds/hold/`, and this stub is never auto-promoted.

## Requirements

### Must have
- A triage decision for ledger key `d2d2ea9958bb`: a backlog PRD, or closed.

### Nice to have
- None until triage.

## Implementation

### Module: triage
- **Location**: `dev/local/prds/hold/`
- **Responsibility**: hold ledger key `d2d2ea9958bb` from `00218-leave-sessions-at-task-boundaries-and-run-one-devon-round-v1.md` until a human triages it
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
