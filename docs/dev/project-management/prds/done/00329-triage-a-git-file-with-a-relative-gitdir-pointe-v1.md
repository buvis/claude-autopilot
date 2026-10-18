---
catchup: skip
design: skip
ledger: deferred/202610161547-deferred.json
ledger_key: 6da9cfe213cf
source_prd: 00320-refuse-every-unsafe-verify-log-sink-v2.md
severity: high
---

# Triage: A `.git` file with a RELATIVE `gitdir:` pointer is still not refused. `_workt...

> Closed 2026-10-18 by the operator's triage (`audit-results/backlog-review-2026-10-18.md`): holds at HEAD; carried by discovery 00360 (verify log-sink refusal residue) for elicitation and review before a PRD.

## Problem

Deferred finding with no PRD owner when this stub was minted: batch `202610161547`, ledger `deferred/202610161547-deferred.json`, type `cap-overflow`, cycle `2`, consensus `3/4`, raised against `00320-refuse-every-unsafe-verify-log-sink-v2.md`.

Issue: A `.git` file with a RELATIVE `gitdir:` pointer is still not refused. `_worktree_gitdir_pointer` returns the pointer unresolved, so `os.path.samefile` resolves it against cwd, raises, and the `continue` swallows it; reproduced on a submodule and on a `worktree.useRelativePaths` worktree. `_open_log_sink` would unlink and recreate that `.git` file. Fix: anchor a relative pointer on `resolved.parent`, plus a regression test.

## Solution

Attended triage. A human promotes this finding into a backlog PRD through normal PRD authoring and review, or closes it. Autopilot never drains `docs/dev/project-management/prds/hold/`, and this stub is never auto-promoted.

## Requirements

### Must have
- A triage decision for ledger key `6da9cfe213cf`: a backlog PRD, or closed.

### Nice to have
- None until triage.

## Implementation

### Module: triage
- **Location**: `docs/dev/project-management/prds/hold/`
- **Responsibility**: hold ledger key `6da9cfe213cf` from `00320-refuse-every-unsafe-verify-log-sink-v2.md` until a human triages it
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
