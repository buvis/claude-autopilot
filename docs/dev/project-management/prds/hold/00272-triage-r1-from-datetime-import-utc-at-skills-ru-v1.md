---
catchup: skip
design: skip
ledger: deferred/202610101000-deferred.json
ledger_key: 2656bc1dd975
source_prd: 00269-sweep-every-findings-token-v1.md
severity: high
---

# Triage: R1: `from datetime import UTC` at skills/run-autopilot/cli/__main__.py:243 br...

## Problem

Deferred finding with no PRD owner when this stub was minted: batch `202610101000`, ledger `deferred/202610101000-deferred.json`, type `cap-overflow`, cycle `2`, consensus `3/4`, raised against `00269-sweep-every-findings-token-v1.md`.

Issue: R1: `from datetime import UTC` at skills/run-autopilot/cli/__main__.py:243 breaks Python 3.10 (that alias needs 3.11). Carl reproduced it: `uv run --python 3.10 python -m cli --help` raises ImportError. The hunk is an unrelated end-of-turn formatter reflow; reverting it to the `timezone.utc` form fixes both the break and the diff surgicality.

## Solution

Attended triage. A human promotes this finding into a backlog PRD through normal PRD authoring and review, or closes it. Autopilot never drains `docs/dev/project-management/prds/hold/`, and this stub is never auto-promoted.

## Requirements

### Must have
- A triage decision for ledger key `2656bc1dd975`: a backlog PRD, or closed.

### Nice to have
- None until triage.

## Implementation

### Module: triage
- **Location**: `docs/dev/project-management/prds/hold/`
- **Responsibility**: hold ledger key `2656bc1dd975` from `00269-sweep-every-findings-token-v1.md` until a human triages it
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
