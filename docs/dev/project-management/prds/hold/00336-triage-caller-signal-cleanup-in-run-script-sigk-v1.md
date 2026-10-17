---
catchup: skip
design: skip
ledger: deferred/202610161547-deferred.json
ledger_key: 3a338afd1712
source_prd: 00322-kill-the-gate-on-every-signal-v1.md
severity: high
---

# Triage: Caller-signal cleanup in _run_script SIGKILLs the replay helper with no grace...

## Problem

Deferred finding with no PRD owner when this stub was minted: batch `202610161547`, ledger `deferred/202610161547-deferred.json`, type `cap-overflow`, cycle `2`, consensus `3/4`, raised against `00322-kill-the-gate-on-every-signal-v1.md`.

Issue: Caller-signal cleanup in _run_script SIGKILLs the replay helper with no grace period (verification._kill_gate), so the replay's _raise_on_signal guard and its worktree-removal finally never run, and the pytest runner in its own session survives: a SIGTERM/SIGHUP to the review-stage caller during a replay still leaves the runner, grandchildren, a registered worktree and a replay-* temp dir. Fix: SIGTERM the helper group, wait SCRIPT_GRACE_S, then SIGKILL; add a caller-signal test on the real replay helper. (skills/run-autopilot/cli/review_stage.py:262)

## Solution

Attended triage. A human promotes this finding into a backlog PRD through normal PRD authoring and review, or closes it. Autopilot never drains `docs/dev/project-management/prds/hold/`, and this stub is never auto-promoted.

## Requirements

### Must have
- A triage decision for ledger key `3a338afd1712`: a backlog PRD, or closed.

### Nice to have
- None until triage.

## Implementation

### Module: triage
- **Location**: `docs/dev/project-management/prds/hold/`
- **Responsibility**: hold ledger key `3a338afd1712` from `00322-kill-the-gate-on-every-signal-v1.md` until a human triages it
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
