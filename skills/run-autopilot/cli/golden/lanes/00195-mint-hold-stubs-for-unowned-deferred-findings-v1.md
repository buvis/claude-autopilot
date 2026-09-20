---
catchup: skip
design: run
default_model: opus
model_tier_rationale: deterministic ledger ownership, cross-directory numbering with collision recovery, and three lifecycle integration sites
---

# Mint hold stubs for unowned deferred findings

## Overview

### Problem Statement
Open severe deferred findings live only in JSON, with no PRD owner. Source: ddb assessment `/Users/bob/git/src/github.com/doogat/ddb/dev/local/audit-results/refactor-assessment-2026-09-06.md` (Decision step 3) and read-only `/Users/bob/git/src/github.com/doogat/ddb/dev/local/autopilot/deferred/202607161128-deferred.json`. Done 00169 is a manual follow-up for one cap-out's leftovers; the ledger still needs a repeatable way to expose unowned CRITICAL/HIGH findings.

This capability was split from backlog 00187. Custody already records cap_critical stalls and migrates pending decisions; this PRD owns mint-stubs and all calls to it. Generated files are HOLD triage artifacts, not executable backlog PRDs, and are never auto-promoted.

### Target Users
The operator triaging a completed batch and the backlog reviewer, who need a file identifying each unowned severe finding.

### Success Metrics
- A frozen fixture filtered to source PRDs 00167–00170 mints exactly 12 hold stubs, then zero on repeat.
- Ownership scans all four PRD lifecycle directories; sequence allocation also includes discovery and survives a concurrent number claim.
- Non-qualifying/owned rows create no files, and lifecycle integration reports minted counts without changing review/custody behavior.
- CLI, fixture, prose and release checks pass against the checkout with no live ddb writes.

## Functional Decomposition

### Capability: A home for every deferred severe finding
#### Feature: Deterministic triage stubs
- **Description**: `autopilot mint-stubs --batch <id>` creates one hold artifact for each qualifying unowned ledger key.
- **Inputs**: the batch deferred JSON and PRDs under backlog, wip, hold and done.
- **Outputs**: `hold/<NNNNN>-triage-<slug>-v1.md`; stdout JSON `{"minted":[...],"skipped":<n>}`. Frontmatter: catchup: skip, design: skip, ledger: deferred/<batch>-deferred.json, ledger_key, source_prd, severity.
- **Behavior**: qualify open critical/high rows case-insensitively using existing render_report._is_open, or stall rows with site cap_critical. Use the first 12 hex characters of sha1 over render_report._normalize(issue or detail) as ledger_key; skip/count rows with neither text field. A matching ledger_key in the first 20 lines of any PRD in the four lifecycle directories claims ownership, including hand-written PRDs. Deduplicate identical normalized text within the input and across reruns. Preserve issue and detail verbatim in Problem. Exit 2 for unreadable/invalid JSON, 9 for write failure; a partial run remains idempotent on retry.

The generated hold artifact freezes this minimal heading order in plugin-owned code/tests: H1 title, Problem, Solution, Requirements, Must have, Nice to have, Implementation, Module: triage, Dependencies, Tasks, Phase 0: Foundation, Phase 1: Core, Success Criteria (with the heading levels of the create-prd minimal template). Fill these with ledger provenance and the single triage action, not executable implementation guesses. Its sole checkbox is `- [ ] triage: promote to backlog or close - Acceptance: this file is no longer under dev/local/prds/hold/`. Phase 1 explicitly has no implementation tasks until attended triage. Promotion requires normal PRD authoring/review. The shipped plugin must not depend on an operator's personal template path at runtime.

#### Feature: Discovery-aware allocation and collision retry
- **Description**: reserve new five-digit numbers without claiming existing PRD/discovery sequences.
- **Inputs**: backlog, wip, hold, done and dev/local/discovery listings.
- **Outputs**: next free sequence at the tail, using existing selection.sequence semantics.
- **Behavior**: scan all five directories before allocation, write the candidate, then rescan for a concurrent claim; if a different work item claimed the number, renumber this attempt's own new file to a fresh tail number and rescan until unique. Never move another writer's file. Distinct revisions of the same existing work unit are not new collisions. Discovery supplies sequence reservations only, not ledger ownership.

#### Feature: Lifecycle minting and reporting
- **Description**: give migrated severe findings an owner at every relevant boundary.
- **Inputs**: successful cap_critical stall, Phase 9 step 6 after deferred migration, loop-mode batch end.
- **Outputs**: invoke mint-stubs at all three sites; batch-end notification gains `<s> stubs`.
- **Behavior**: mint only after the source ledger write succeeds; preserve custody retry/reset order and run each site idempotently. The notify count is the unique artifacts minted for that batch across its mint calls, not merely the final call's usually-zero result; persist/deduplicate minted paths in batch state while retaining the CLI stdout contract. The reviewed design fixes the internal counter storage before planning. Never stop to triage, auto-promote stubs or change the review roster.

## Structural Decomposition

### Repository Structure
```
skills/run-autopilot/cli/triage.py                       # NEW: ledger/key/template/allocator
skills/run-autopilot/cli/__main__.py                     # mint-stubs verb
skills/run-autopilot/cli/test_triage.py                  # NEW: CLI/fixture/allocation tests
skills/run-autopilot/cli/test_triage_prose.py            # NEW: lifecycle contracts
skills/run-autopilot/cli/golden/triage-ddb-202607161128.json  # NEW: frozen filtered ledger
skills/run-autopilot/references/phase-review.md
skills/run-autopilot/references/phase-done.md
skills/run-autopilot/references/state-schema.md
dev/bin/release-checks
CHANGELOG.md
```

### Module: triage
- **Maps to capability**: A home for every deferred severe finding
- **Responsibility**: cli/triage.py, test_triage.py and the frozen golden fixture; qualification, ownership, template and allocation.
- **Exports**: ledger_key(text) -> str; mint_stubs(autopilot_dir, prds_dir, batch_id) -> dict. Reuse existing read-only render_report._normalize/_is_open and selection.sequence.

### Module: mint CLI
- **Maps to capability**: A home for every deferred severe finding
- **Responsibility**: cli/__main__.py; resolve paths, invoke triage and map errors.
- **Exports**: mint-stubs --batch with the JSON/exit contract above.

### Module: lifecycle integration
- **Maps to capability**: A home for every deferred severe finding
- **Responsibility**: the three reference docs, test_triage_prose.py, release-checks and CHANGELOG; invocation order and batch stub count.
- **Exports**: documented call sites and count metadata.

## Dependency Graph

### Foundation Layer (Phase 0)
- **triage**: existing ledger normalization/open predicate and sequence parser; no new dependency on rework design.

### Core Layer (Phase 1)
- **mint CLI**: depends on [triage].
- **lifecycle integration**: depends on [mint CLI] and earlier 00187 successful custody/migration behavior.

### Integration Layer (Phase 2)
- **lifecycle integration**: release/fixture verification after Phase 1.

## Implementation Phases

### Phase 0: Ownership and allocation
**Goal**: create deterministic hold artifacts without sequence collisions.
**Tasks**:
- [ ] Add triage helpers, frozen template and test fixtures (no deps). Premise: existing _normalize/_is_open and selection.sequence provide these predicates, with no mint-stubs implementation; recheck before adding, skip/report a superseding implementation. Acceptance: test_triage.py covers unowned critical/high and cap_critical stalls, owned keys in each lifecycle directory, identical-text folding, case-insensitive severity, medium/low/resolved/severity-less/no-text skips, template heading order/provenance/verbatim text, discovery-only maximum, concurrent claim after write with own-file renumber/recheck, partial-write retry and no auto-promotion.
- [ ] Freeze the historical ledger slice in cli/golden/triage-ddb-202607161128.json (no deps). Acceptance: copy source rows verbatim only for PRDs 00167, 00168, 00169 and 00170; provenance names that explicit filter. Tests prove 12 then zero: 3 for 00167, 3 for 00168 including its cap_critical stall, 4 for 00169, 2 for 00170 after duplicate folding. Do not assert 12 from the current full ledger, which also includes a qualifying 00171 row.
**Exit Criteria**: helper/allocation tests and frozen-fixture assertions pass.

### Phase 1: CLI and lifecycle
**Goal**: invoke minting after durable migration and report the whole batch's count.
**Tasks**:
- [ ] Add mint-stubs CLI and update phase-review after successful cap_critical stall, phase-done after step-6 migration and at loop batch end; document count metadata in state-schema (depends on: Phase 0). Premise: these sections now contain custody/convergence/rework changes from earlier PRDs but no mint calls; recheck by heading and behavior, skip/report if superseded. Acceptance: checkout subprocess tests assert stdout/exit 2/9 and path resolution; test_triage_prose.py pins all three call sites after successful writes, never minting after a failed stall, unchanged custody ordering and review roster, and the notification's count accumulated across calls. A fixture with earlier mint count 12 and final mint count 0 still reports 12 stubs.
**Exit Criteria**: CLI/prose contracts pass with reruns creating no duplicates.

### Phase 2: Release
**Goal**: validate the complete feature with isolated data.
**Tasks**:
- [ ] Verify/register triage tests in release-checks and add an Unreleased run-autopilot stub-minting entry (depends on: Phase 1). Acceptance: `uv run --no-project --with pytest python -m pytest -q skills/run-autopilot/cli/test_triage.py skills/run-autopilot/cli/test_triage_prose.py` and `bash dev/bin/release-checks` pass; the specific changelog subject appears under Unreleased, preserving other entries. CLI proofs use this checkout's skills/run-autopilot/cli/__main__.py and temporary state, never the installed cache or live ddb.
**Exit Criteria**: all Success Metrics hold.

## Test Strategy

### Critical Scenarios
- **Happy path**: filtered historical rows → 12 hold owners, then zero; batch notification retains the first call's count.
- **Edge case**: max number exists only in discovery, or another writer claims a candidate after creation → renumber only this attempt and recheck.
- **Error case**: bad JSON → exit 2; partial write failure → exit 9 and safe retry; missing text → counted skip.

## Risks
- **Identical normalized text folds distinct rows**: accepted policy; attended triage can split the owner.
- **A burst of hold artifacts**: intentional visibility; hold is never drained by autopilot and promotion remains attended.
