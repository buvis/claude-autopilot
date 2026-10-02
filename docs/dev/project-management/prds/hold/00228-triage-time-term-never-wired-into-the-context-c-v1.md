---
catchup: skip
design: skip
ledger: deferred/202609252154-deferred.json
ledger_key: 0859de2c4a00
source_prd: 00218-leave-sessions-at-task-boundaries-and-run-one-devon-round-v1.md
severity: critical
---

# Triage: Time term never wired into the context-cap hook: _handle_below_cap calls _hea...

## Problem

Deferred finding with no PRD owner when this stub was minted: batch `202609252154`, ledger `deferred/202609252154-deferred.json`, type `review-critical`, consensus `4/4`, raised against `00218-leave-sessions-at-task-boundaries-and-run-one-devon-round-v1.md`.

Issue: Time term never wired into the context-cap hook: _handle_below_cap calls _headroom_exhausted with no secs_left or last_wall, the hook never imports last_task_wall and never reads _AUTOPILOT_SESSION_DEADLINE. The PRD headline capability is absent at runtime. Orchestrator-verified at e5a8479.

## Solution

Attended triage. A human promotes this finding into a backlog PRD through normal PRD authoring and review, or closes it. Autopilot never drains `dev/local/prds/hold/`, and this stub is never auto-promoted.

## Requirements

### Must have
- A triage decision for ledger key `0859de2c4a00`: a backlog PRD, or closed.

### Nice to have
- None until triage.

## Implementation

### Module: triage
- **Location**: `dev/local/prds/hold/`
- **Responsibility**: hold ledger key `0859de2c4a00` from `00218-leave-sessions-at-task-boundaries-and-run-one-devon-round-v1.md` until a human triages it
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
