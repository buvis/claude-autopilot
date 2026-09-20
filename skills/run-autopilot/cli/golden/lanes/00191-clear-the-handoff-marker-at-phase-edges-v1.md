---
catchup: skip
design: skip
default_model: sonnet
model_tier_rationale: explicit marker schema and lifecycle edge matrix, with production-entrypoint regressions
rework_cap: 3
---

# Clear the handoff marker at phase edges

Source: batch 202609061630, PRD 00182 infra-bug row and the config-audit closure walkthrough (`~/.claude/dev/local/audit-results/2026-09-05.md`). The build's marker survived into review rework; no further task boundary happened to consume it.

## Overview

### Problem Statement
`skills/run-autopilot/scripts/autopilot_context_cap_hook.py` currently writes the active task ID into `.handoff-requested`, once per task, only with readable build state. Work step 6.5 consumes it through `skills/work/references/task-boundary-handoff.md`, but skips that step when no tasks remain. A marker created on the last build task therefore survives into review. Review rework invokes work again, where the stale marker can select build as the next phase. The real phase transition is `cli/__main__.py:_run_phase_done`, calling pure `transitions.apply`; cleanup belongs at lifecycle I/O boundaries, not an invented loop edge.

### Target Users
The loop and operator, who need task-boundary handoffs to preserve the active phase and review cycle.

### Success Metrics
- Both markers are absent after every successful lifecycle edge in the matrix below.
- Same-phase, same-PRD resumes preserve valid markers; stale/malformed markers cannot route review back to build.
- Hook, lifecycle and prose regressions plus `bash dev/bin/release-checks` pass.

## Functional Decomposition

### Capability: Markers die with their phase
#### Feature: The hook stamps phase and task identity
- **Description**: write JSON `{"phase":"build","session":"<sid>","at":"<ISO-8601>","task_id":"<active task ID>"}`.
- **Inputs**: the existing soft-cap event, readable state, active task ID and hook session ID.
- **Outputs**: the JSON marker with non-empty task identity; session is the payload's ID (empty string only if unavailable), timestamp is UTC ISO-8601.
- **Behavior**: retain the build-only and unreadable-state no-write guards. Existing JSON with the same task ID is a no-op, preserving its timestamp/session; another task overwrites it. Legacy non-empty plain task IDs have the same deduplication rule. Empty or malformed contents may be replaced by the next valid build request. Keep best-effort I/O and existing hard-cap thresholds unchanged.

#### Feature: Step 6.5 honours only its own phase
- **Description**: check marker format and phase before taking the handoff path.
- **Inputs**: marker text and readable current state.
- **Outputs**: matching requests hand off within the current phase; stale requests are discarded.
- **Behavior**: non-empty plain task-ID markers are legacy build requests; empty legacy markers count as the current phase. JSON requires the four typed fields above and a non-empty task ID. JSON-looking malformed text, invalid field shapes and phase mismatches remove both markers with a stderr note, then continue as absent. For a mismatch print `autopilot: stale handoff marker from phase <p> removed`; malformed markers get an explicit malformed-marker note. If state cannot be read, do not hand off or invent a phase. A valid legacy empty marker during review preserves review as the handoff target. Update both the step-6.5 trigger summary and its reference procedure so neither unconditionally selects build.

#### Feature: Lifecycle edges clear both markers
- **Description**: remove `.handoff-requested` and `.cap-fired` from the directory containing the resolved state file after a successful lifecycle commit.
- **Inputs**: production phase-done, stall/park and reset-prd entrypoints.
- **Outputs**: cleanup after the following edges; absence is harmless.
- **Behavior**: attach I/O to `__main__._run_phase_done`, `__main__._run_reset_prd` and the successful commit path in `records.do_stall` (also reached by park/reconciliation). Keep `transitions.apply` and `records.reset_prd_fields` pure. Failed state transitions preserve markers. Cleanup errors report the path; the consumer's phase guard remains effective if deletion fails.

| Operation | Result | Markers |
|---|---|---|
| phase-done: build + tasks_done | review | clear |
| phase-done: review + converged | done | clear |
| phase-done: done + more_prds | build, next PRD | clear |
| phase-done: build/done + drained | terminal, empty next_phase | clear |
| successful stall/park or reset-prd | current PRD ends, even build to build | clear |
| phase-done: review + rework | same phase and PRD | preserve |
| ordinary same-phase resume or session spawn | same phase and PRD | preserve |
| rejected/failed lifecycle transaction | no successful transition | preserve |

## Structural Decomposition

### Repository Structure
```
skills/run-autopilot/scripts/autopilot_context_cap_hook.py
skills/run-autopilot/scripts/test_autopilot_context_cap_hook.py
skills/run-autopilot/cli/handoff.py                  # NEW: lifecycle cleanup helper
skills/run-autopilot/cli/__main__.py                 # phase-done and reset-prd callers
skills/run-autopilot/cli/records.py                  # successful stall commit caller
skills/run-autopilot/cli/test_handoff.py             # NEW: real-entrypoint regressions
skills/work/SKILL.md
skills/work/references/task-boundary-handoff.md
skills/work/scripts/test_dispatch_prose.py
CHANGELOG.md
```

### Module: context-cap hook
- **Maps to capability**: Markers die with their phase
- **Responsibility**: the two run-autopilot/scripts files; stamp and test the producer contract.
- **Exports**: unchanged hook CLI; internal request helper receives task, phase and session context.

### Module: lifecycle cleanup
- **Maps to capability**: Markers die with their phase
- **Responsibility**: `cli/handoff.py`, `cli/__main__.py`, `cli/records.py` and `cli/test_handoff.py`; clear only after the specified successful transitions.
- **Exports**: `clear_markers(autopilot_dir) -> None`; existing lifecycle command signatures remain unchanged.

### Module: work handoff
- **Maps to capability**: Markers die with their phase
- **Responsibility**: the three skills/work files and CHANGELOG; describe and pin compatible consumption and phase-preserving handoff.
- **Exports**: skill prose and contract tests.

## Dependency Graph

### Foundation Layer (Phase 0)
- **context-cap hook**: no dependencies.
- **lifecycle cleanup**: no dependency on the marker's content; deletes both paths after the matrix's successful commits.

### Core Layer (Phase 1)
- **work handoff**: depends on [context-cap hook, lifecycle cleanup].

### Integration Layer (Phase 2)
- **work handoff** and **lifecycle cleanup**: integrated regression/release verification after Phase 1.

## Implementation Phases

### Phase 0: Producer and lifecycle
**Goal**: make task identity explicit and bind deletion to the real lifecycle.
**Tasks**:
- [ ] Stamp the four-field marker and preserve the producer's guards (no deps). Premise: the hook currently writes/deduplicates a plain task ID and main returns on unreadable state or non-build phase; recheck before editing, skip/report if changed. Acceptance: hook tests cover same-task JSON no-op, changed-task overwrite, matching/different legacy task IDs, empty/malformed replacement, session/timestamp fields, unreadable-state no-write and review-phase no-write; preserve existing per-task and hard-cap assertions while updating fixtures for JSON.
- [ ] Add handoff.clear_markers and call it after successful phase-done, reset-prd and do_stall commits (no deps). Premise: lifecycle wrappers own I/O and transitions.apply/reset_prd_fields are pure; recheck all callers, including park/reconciliation, before editing; skip/report changed premises. Acceptance: cli/test_handoff.py invokes this checkout's cli/__main__.py through subprocess fixtures for every matrix row, covers real park/stall call paths, missing files, failed transactions and cleanup errors; both pure helpers remain filesystem-free.
**Exit Criteria**: producer and production-entrypoint lifecycle tests pass with every matrix row covered.

### Phase 1: Consumer
**Goal**: consume only compatible requests without changing the active phase.
**Tasks**:
- [ ] Update work step 6.5 and its reference procedure (depends on: Phase 0). Premise: both currently treat any present marker as a build handoff; recheck before editing, skip/report if changed. Acceptance: test_dispatch_prose.py pins the typed JSON contract, legacy task-ID/build and empty/current-phase cases, stale/malformed removal and notes, unreadable-state behavior, and preservation of the current phase in next_phase and handoff telemetry; neither path can unconditionally select build during review.
**Exit Criteria**: prose contract tests pass and the last-build-task to review-rework fixture finds no marker.

### Phase 2: Integration
**Goal**: verify migration and document the fix.
**Tasks**:
- [ ] Add targeted Unreleased Fixed entries for work handoff compatibility and run-autopilot lifecycle cleanup; run the integrated checks (depends on: Phase 1). Acceptance: `uv run --no-project --with pytest python -m pytest -q skills/run-autopilot/scripts/test_autopilot_context_cap_hook.py skills/run-autopilot/cli skills/work/scripts/test_dispatch_prose.py` and `bash dev/bin/release-checks` pass; each new subject appears under Unreleased without counting unrelated scope entries.
**Exit Criteria**: all Success Metrics hold against the checkout.

## Test Strategy

### Critical Scenarios
- **Happy path**: build soft cap with tasks pending → one request per task and a build handoff.
- **Edge case**: soft cap on the final build task → tasks_done clears both markers before review; same-review rework preserves a valid same-phase request.
- **Error case**: unreadable state produces no request; stale or malformed consumer data cannot change phase; failed transition preserves markers.

## Risks
- **Mid-batch format migration**: preserve both existing task-ID markers and empty legacy markers with explicit phase semantics.
- **Multiple cleanup sites**: all tolerate absence; entrypoint tests catch an uncalled helper or same-phase over-cleaning.
