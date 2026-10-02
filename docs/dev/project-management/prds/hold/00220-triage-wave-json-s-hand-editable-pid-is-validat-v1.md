---
catchup: skip
design: skip
ledger: deferred/202609252154-deferred.json
ledger_key: d42c5f014382
source_prd: 00214-plan-and-launch-a-wave-of-lanes-v1.md
severity: critical
---

# Triage: wave.json's hand-editable `pid` is validated only as int-or-None with no posi...

## Problem

Deferred finding with no PRD owner when this stub was minted: batch `202609252154`, ledger `deferred/202609252154-deferred.json`, type `deferred_decision`, cycle `1`, raised against `00214-plan-and-launch-a-wave-of-lanes-v1.md`.

Issue: wave.json's hand-editable `pid` is validated only as int-or-None with no positivity bound, so `"pid": 0` reaches os.killpg(0, SIGTERM) in wave_launch._kill_lane and signals the caller's own process group - the operator's shell, or the autopilot loop itself under a wave (skills/run-autopilot/cli/wave.py:289, found by bob, 1/4)

## Solution

Attended triage. A human promotes this finding into a backlog PRD through normal PRD authoring and review, or closes it. Autopilot never drains `dev/local/prds/hold/`, and this stub is never auto-promoted.

## Requirements

### Must have
- A triage decision for ledger key `d42c5f014382`: a backlog PRD, or closed.

### Nice to have
- None until triage.

## Implementation

### Module: triage
- **Location**: `dev/local/prds/hold/`
- **Responsibility**: hold ledger key `d42c5f014382` from `00214-plan-and-launch-a-wave-of-lanes-v1.md` until a human triages it
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
