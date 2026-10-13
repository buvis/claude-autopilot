---
catchup: skip
design: skip
ledger: deferred/202610111300-deferred.json
ledger_key: 1f20a3eab657
source_prd: 00282-loop-guards-v1.md
severity: high
---

# Triage: [R2] `prd_spend_since` now crashes on a non-UTF-8 ledger. The new `metrics_pa...

## Problem

Deferred finding with no PRD owner when this stub was minted: batch `202610111300`, ledger `deferred/202610111300-deferred.json`, type `cap-overflow`, cycle `2`, consensus `2/3`, raised against `00282-loop-guards-v1.md`.

Issue: [R2] `prd_spend_since` now crashes on a non-UTF-8 ledger. The new `metrics_path.read_text(encoding="utf-8")` pre-probe only catches OSError, and UnicodeDecodeError is a ValueError. I checked: a ledger holding bytes `\xff\xfe{}` raises UnicodeDecodeError out of `_budget_bound`, into the unattended loop. The old binary reader skipped such lines. The probe also reads the whole ledger twice, since `load_rows` reads it again. Drop the probe and catch `(OSError, UnicodeDecodeError)`, or open and read once and hand the rows over. (file: skills/run-autopilot/cli/loop_decision.py:188)

## Solution

Attended triage. A human promotes this finding into a backlog PRD through normal PRD authoring and review, or closes it. Autopilot never drains `docs/dev/project-management/prds/hold/`, and this stub is never auto-promoted.

## Requirements

### Must have
- A triage decision for ledger key `1f20a3eab657`: a backlog PRD, or closed.

### Nice to have
- None until triage.

## Implementation

### Module: triage
- **Location**: `docs/dev/project-management/prds/hold/`
- **Responsibility**: hold ledger key `1f20a3eab657` from `00282-loop-guards-v1.md` until a human triages it
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
