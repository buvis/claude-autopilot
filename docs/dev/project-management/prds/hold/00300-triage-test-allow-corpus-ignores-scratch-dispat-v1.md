---
catchup: skip
design: skip
ledger: deferred/202610111300-deferred.json
ledger_key: b2fb4c95e26f
source_prd: 00278-make-release-checks-tell-truth-v1.md
severity: high
---

# Triage: test_allow_corpus_ignores_scratch_dispatch_files is tautological: it writes t...

## Problem

Deferred finding with no PRD owner when this stub was minted: batch `202610111300`, ledger `deferred/202610111300-deferred.json`, type `cap-overflow`, cycle `2`, consensus `2/3`, raised against `00278-make-release-checks-tell-truth-v1.md`.

Issue: test_allow_corpus_ignores_scratch_dispatch_files is tautological: it writes the scratch file into tmp_path, which neither the current nor the old _allow_corpus() globs, so the second assert cannot differ from the first. The fail-first replay confirms it passes at base. Plant the file where _allow_corpus reads it (or monkeypatch the corpus directory) and assert the committed fixtures list.

## Solution

Attended triage. A human promotes this finding into a backlog PRD through normal PRD authoring and review, or closes it. Autopilot never drains `docs/dev/project-management/prds/hold/`, and this stub is never auto-promoted.

## Requirements

### Must have
- A triage decision for ledger key `b2fb4c95e26f`: a backlog PRD, or closed.

### Nice to have
- None until triage.

## Implementation

### Module: triage
- **Location**: `docs/dev/project-management/prds/hold/`
- **Responsibility**: hold ledger key `b2fb4c95e26f` from `00278-make-release-checks-tell-truth-v1.md` until a human triages it
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
