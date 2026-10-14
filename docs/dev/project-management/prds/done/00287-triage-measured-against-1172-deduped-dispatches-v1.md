---
catchup: skip
design: skip
ledger: deferred/202610111300-deferred.json
ledger_key: b3426cdd4278
source_prd: 00271-guard-v2-structural-delegation-check-v1.md
severity: high
---

# Triage: Measured against 1172 deduped dispatches (800 per-task): 7 per-task refusals....

## Problem

Deferred finding with no PRD owner when this stub was minted: batch `202610111300`, ledger `deferred/202610111300-deferred.json`, type `guard-false-positives`, raised against `00271-guard-v2-structural-delegation-check-v1.md`.

Detail: Measured against 1172 deduped dispatches (800 per-task): 7 per-task refusals. One is the pinned deny id (correct). The other six, with the span the guard quoted: (1) toolu_015DM18ubZLJZbA65ozvuw8c, no subagent_type, span "e-invokes `/autopilot:work`, w" - narrative prose about what re-invokes the skill. (2) toolu_013NAWvgMnP4WatpZDVyiNAa, (3) toolu_01DAQSaS3uAph2VZnfn5NC9d, (4) toolu_019nCz3WRsAZSwdaHb9itXiT, general-purpose, spans "d reports `design-solution: <p", ".assertIn(\"design-solution: <p", "ine reads `design-solution: <p" - a log-line FORMAT quoted as expected test output. (5) toolu_013ePUKbLDE7DLnbnGmgszzR, general-purpose, span "parse and plan-tasks) looks fo" - paren aside. (6) toolu_011UqbqFtUDPuSeCiLLgMvEg, autopilot:worker-opus, span "`Run the work phase for PRD 0" - this PRDs own trigger string quoted as test data, strong-anchored, and the one the session brief already records as costing a denied dispatch. Common shape: an open wrapper (backtick, double quote, paren) opens BEFORE the name and closes AFTER more text, so the name is a citation rather than the thing to run. The guard treats a wrapper as neutral: _candidates consumes a close only when it sits immediately after the name, so a longer quoted run leaves the bare name weakly anchored by the following punctuation. Five of the six also depend on per_task being false because the historical dispatch used general-purpose or no type. NOT fixed in task 9: a quoted-citation concept is a new anchoring rule in a predicate whose shape is pinned verbatim by the design doc and covered by 564 tests across three suites, so it is a design decision, not an implementor rewrite. Fixing all six would still not reach exit 0 (see the contract-conflict record), so no partial fix buys the stated goal either.

## Solution

Attended triage. A human promotes this finding into a backlog PRD through normal PRD authoring and review, or closes it. Autopilot never drains `docs/dev/project-management/prds/hold/`, and this stub is never auto-promoted.

## Requirements

### Must have
- A triage decision for ledger key `b3426cdd4278`: a backlog PRD, or closed.

### Nice to have
- None until triage.

## Implementation

### Module: triage
- **Location**: `docs/dev/project-management/prds/hold/`
- **Responsibility**: hold ledger key `b3426cdd4278` from `00271-guard-v2-structural-delegation-check-v1.md` until a human triages it
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

## Triage 2026-10-14

Promoted into PRD 00307 (`guard-citations-and-replay-contract`): the six ids above are its `test_six_corpus_dispatches_are_allowed`. Closed into `done/`.
