---
catchup: skip
design: skip
ledger: deferred/202610161547-deferred.json
ledger_key: 557e1d62e8fd
source_prd: 00322-kill-the-gate-on-every-signal-v1.md
severity: high
---

# Triage: The replay signal guard is installed only inside _run_runner, not around _run...

> Closed 2026-10-18 by the operator's triage (`audit-results/backlog-review-2026-10-18.md`): holds at HEAD; carried by discovery 00361 (replay and helper signal residue) for elicitation and review before a PRD.

## Problem

Deferred finding with no PRD owner when this stub was minted: batch `202610161547`, ledger `deferred/202610161547-deferred.json`, type `cap-overflow`, cycle `2`, consensus `1/4`, raised against `00322-kill-the-gate-on-every-signal-v1.md`.

Issue: The replay signal guard is installed only inside _run_runner, not around _run_in_worktree, so a signal during git worktree add / the overlay checkout / the rest of setup takes the default action and skips the finally, leaving a registered worktree and a replay-* temp dir. The new test only signals after the runner pids appear. (skills/review-work-completion/scripts/replay_tests_against_base.py:158)

## Solution

Attended triage. A human promotes this finding into a backlog PRD through normal PRD authoring and review, or closes it. Autopilot never drains `docs/dev/project-management/prds/hold/`, and this stub is never auto-promoted.

## Requirements

### Must have
- A triage decision for ledger key `557e1d62e8fd`: a backlog PRD, or closed.

### Nice to have
- None until triage.

## Implementation

### Module: triage
- **Location**: `docs/dev/project-management/prds/hold/`
- **Responsibility**: hold ledger key `557e1d62e8fd` from `00322-kill-the-gate-on-every-signal-v1.md` until a human triages it
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
