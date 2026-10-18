---
catchup: skip
design: skip
ledger: deferred/202610161547-deferred.json
ledger_key: 470a046570d6
source_prd: 00322-kill-the-gate-on-every-signal-v1.md
severity: high
---

# Triage: Replay signal protection ends before worktree removal: a second SIGTERM/SIGHU...

> Closed 2026-10-18 by the operator's triage (`audit-results/backlog-review-2026-10-18.md`): holds at HEAD; carried by discovery 00361 (replay and helper signal residue) for elicitation and review before a PRD.

## Problem

Deferred finding with no PRD owner when this stub was minted: batch `202610161547`, ledger `deferred/202610161547-deferred.json`, type `cap-overflow`, cycle `2`, consensus `1/4`, raised against `00322-kill-the-gate-on-every-signal-v1.md`.

Issue: Replay signal protection ends before worktree removal: a second SIGTERM/SIGHUP arriving during _run_in_worktree cleanup meets the restored default handler and terminates replay before removal completes. Keep the guard installed through worktree cleanup and synchronise the regression's second signal with removal. (skills/review-work-completion/scripts/replay_tests_against_base.py:189)

## Solution

Attended triage. A human promotes this finding into a backlog PRD through normal PRD authoring and review, or closes it. Autopilot never drains `docs/dev/project-management/prds/hold/`, and this stub is never auto-promoted.

## Requirements

### Must have
- A triage decision for ledger key `470a046570d6`: a backlog PRD, or closed.

### Nice to have
- None until triage.

## Implementation

### Module: triage
- **Location**: `docs/dev/project-management/prds/hold/`
- **Responsibility**: hold ledger key `470a046570d6` from `00322-kill-the-gate-on-every-signal-v1.md` until a human triages it
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
