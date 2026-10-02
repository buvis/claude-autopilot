---
catchup: skip
design: skip
ledger: deferred/202609252154-deferred.json
ledger_key: b11361de7d00
source_prd: 00233-run-the-test-suites-in-parallel-v1.md
severity: high
---

# Triage: gather-context.sh full-review path produces an EMPTY diff in a repo that work...

## Problem

Deferred finding with no PRD owner when this stub was minted: batch `202609252154`, ledger `deferred/202609252154-deferred.json`, type `tooling-defect`, cycle `1`, consensus `orchestrator`, raised against `00233-run-the-test-suites-in-parallel-v1.md`.

Issue: gather-context.sh full-review path produces an EMPTY diff in a repo that works directly on master. It resolves its base to the detected branch (origin/HEAD or master) and runs git diff <base>, so at a clean HEAD on master the diff is empty and every cycle-1 reviewer would receive nothing to review. This review worked around it by passing --since <work_start_sha>, which yields exactly the work_start_sha..HEAD range the gate specifies, and the context file scope label was corrected by hand from incremental review to full review. The workaround is undocumented, so the next full review in a master-only repo can silently review an empty diff.

## Solution

Attended triage. A human promotes this finding into a backlog PRD through normal PRD authoring and review, or closes it. Autopilot never drains `docs/dev/project-management/prds/hold/`, and this stub is never auto-promoted.

## Requirements

### Must have
- A triage decision for ledger key `b11361de7d00`: a backlog PRD, or closed.

### Nice to have
- None until triage.

## Implementation

### Module: triage
- **Location**: `docs/dev/project-management/prds/hold/`
- **Responsibility**: hold ledger key `b11361de7d00` from `00233-run-the-test-suites-in-parallel-v1.md` until a human triages it
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
