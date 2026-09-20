---
catchup: skip
design: run
default_model: opus
model_tier_rationale: cross-skill rework routing and verbatim design-contract propagation before fix tasks
---

# Design CRITICAL rework before task dispatch

## Overview

### Problem Statement
The review rework branch goes directly from a consolidated CRITICAL to an Ivan D-task. The ddb assessment `/Users/bob/git/src/github.com/doogat/ddb/dev/local/audit-results/refactor-assessment-2026-09-06.md` (F2, Decision step 3) found that 8 of 13 cycle-2 CRITICAL/HIGH findings across 00167/00168/00170 were born in cycle-1 rework. ddb 00168's cycle-2 review describes each new Critical/High as introduced by, or newly exposed by, the prior fix.

This is the design capability split from backlog 00187. Custody remains in 00187; this PRD adds reviewed fix design before CRITICAL rework, and changes no review lens, cap or task budget.

### Target Users
The review session dispatching a severe fix, and the implementor who needs its architectural contract before writing code.

### Success Metrics
- Every CRITICAL rework below the cap routes through design before task-add.
- Each CRITICAL D-task carries the cycle's Design path and verbatim Interfaces & contracts above Findings (verbatim).
- Design failure routes to the specified loop stall or interactive pause, and every existing review lens still runs.
- Design/review prose contract tests and release-checks pass against the checkout.

## Functional Decomposition

### Capability: Reviewed design before CRITICAL rework
#### Feature: Design-solution rework mode
- **Description**: `/autopilot:design-solution <prd> --rework <review-file>` designs the cycle's CRITICAL fixes.
- **Inputs**: PRD, consolidated review CRITICAL rows, current cycle and `git diff --stat <work_start_sha>..HEAD`.
- **Outputs**: `dev/local/designs/<prd-stem>-rework-<cycle>-design.md`, using the existing nine design sections; summary `design-solution: <prd-stem> (rework cycle <n>)`.
- **Behavior**: Architecture fit opens with what the prior fix changed and why it regressed (first rework states there was no prior rework fix). Keep the existing three-dispatch design review procedure, ceiling and exit report. The rework document's Interfaces & contracts section is the sole contract source for the subsequent CRITICAL tasks.

#### Feature: Phase 6 routing and task contract
- **Description**: design severe rework before creating its fix tasks.
- **Inputs**: consolidated severity table, cycle and rework_cap.
- **Outputs**: each CRITICAL `[D{cycle}]` task includes `Design: <path>` and a `### Contract` block copied verbatim from the rework design's `## Interfaces & contracts`, above the existing `### Findings (verbatim)`.
- **Behavior**: when at least one CRITICAL exists and cycle < rework_cap, invoke rework design once for that cycle before any task-add in Dispatch rework. Other severity handling remains as today. At the cap, existing cap_critical custody/stall handling applies and no fix task/design is launched. On design failure, loop mode executes the normal stall procedure with new site `design_rework`; interactive mode PAUSEs with `sub_skill_fail`. Preserve the escalation caveat and every consensus, blind and doubt/de-slop lens.

## Structural Decomposition

### Repository Structure
```
skills/design-solution/SKILL.md
skills/run-autopilot/references/phase-review.md
skills/run-autopilot/references/recovery.md
skills/run-autopilot/references/state-schema.md
skills/run-autopilot/scripts/test_design_review_contract.py
skills/run-autopilot/cli/test_design_rework_prose.py      # NEW
dev/bin/release-checks
CHANGELOG.md
```

### Module: rework design
- **Maps to capability**: Reviewed design before CRITICAL rework
- **Responsibility**: design-solution/SKILL.md and test_design_review_contract.py; rework inputs, cycle-scoped output and existing review procedure.
- **Exports**: design-solution --rework skill mode.

### Module: rework routing
- **Maps to capability**: Reviewed design before CRITICAL rework
- **Responsibility**: phase-review.md, recovery.md, state-schema.md and test_design_rework_prose.py; ordering, verbatim task contract and failure routing.
- **Exports**: documented design_rework stall site and D-task contract.

### Module: release integration
- **Maps to capability**: Reviewed design before CRITICAL rework
- **Responsibility**: release-checks and CHANGELOG; execute contract tests and describe the routing.
- **Exports**: no runtime API.

## Dependency Graph

### Foundation Layer (Phase 0)
- **rework design**: existing design-solution sections and review procedure; no new custody API dependency.

### Core Layer (Phase 1)
- **rework routing**: depends on [rework design]; preserve the earlier 00187 cap-out custody branch and 00188 convergence prose.

### Integration Layer (Phase 2)
- **release integration**: depends on [rework design, rework routing].

## Implementation Phases

### Phase 0: Rework design mode
**Goal**: supply a reviewed contract for one cycle's CRITICAL fixes.
**Tasks**:
- [ ] Add Rework mode to design-solution (no deps). Premise: the skill has no existing rework mode; recheck semantic headings/dispatch procedure, skip/report if superseded. Acceptance: test_design_review_contract.py pins review-file input, cycle-scoped filename, nine sections, Architecture fit's prior-fix explanation, unchanged three-dispatch procedure/ceiling and cycle-specific summary.
**Exit Criteria**: design mode contract tests pass.

### Phase 1: Dispatch contract
**Goal**: route and fail deterministically before fix-task creation.
**Tasks**:
- [ ] Update Phase 6 Dispatch rework and add design_rework to recovery/state-schema (depends on: Phase 0). Premise: CRITICAL below-cap rework currently task-adds without design; recheck after earlier backlog changes, skip/report a superseding route. Acceptance: cli/test_design_rework_prose.py pins one design call before any task-add, Design/Contract/Findings ordering and verbatim contract source, below-cap versus at-cap behavior, non-CRITICAL unchanged routing, loop design_rework stall and interactive sub_skill_fail pause; the execution-time review-lens roster sentence remains byte-identical.
**Exit Criteria**: all routing and failure branches are pinned with no runtime request for an implementation-time operator decision.

### Phase 2: Integration
**Goal**: run the regression contracts in the shipped gate.
**Tasks**:
- [ ] Verify/register both contract test files in release-checks and add targeted Unreleased entries for design-solution rework mode and run-autopilot design-before-dispatch (depends on: Phase 1). Acceptance: `uv run --no-project --with pytest python -m pytest -q skills/run-autopilot/scripts/test_design_review_contract.py skills/run-autopilot/cli/test_design_rework_prose.py` and `bash dev/bin/release-checks` pass; each new changelog subject is present under Unreleased while unrelated entries remain.
**Exit Criteria**: all Success Metrics hold without running a live batch as a completion gate.

## Test Strategy

### Critical Scenarios
- **Happy path**: CRITICAL below cap → reviewed cycle design → task with the exact contract.
- **Edge case**: at-cap CRITICAL → existing custody stall, no further rework design; non-CRITICAL rework retains existing routing.
- **Error case**: design fails → design_rework stall in loop mode, sub_skill_fail pause interactively, no blind fix task.

## Risks
- **One more design session on severe cycles**: bounded by rework_cap and the existing design review dispatch ceiling.
- **Shared phase-review prose**: recheck current sections and preserve custody/convergence behavior from lower-numbered PRDs.
