---
catchup: run
design: run
default_model: opus
model_tier_rationale: cross-cutting routing-policy change across planning, dispatch, escalation, telemetry, and compatibility behavior
---

# Align Qwen Routing with Single-File Trust

## Overview

### Problem Statement

The 2026-09-03 Qwen3.8 multi-file capability eval in the `agent-skills`
repository currently reports Qwen at 4/6 against Sonnet at 6/6, including one
silent all-files drop and one two-file logic failure. Its first completion
review found evidence-integrity defects that prevent treating that comparison
as decision-grade: narrowed tasks retained post-task code/tests, several retry
trees reused another tree's baseline, and required line-history checks were not
recorded. The last valid qualification therefore remains the earlier 6/6
single-file round, so the safe autonomous `--approved-only` trust scope remains
`single-file-only` until a clean multi-file rerun proves otherwise. Autopilot
still marks backend Haiku/Sonnet tasks touching up to three files as
`qwen_eligible`, and `/work` trusts that persisted flag without rechecking the
current write set. Guidance and runtime behavior now disagree.

Two adjacent failure paths are also implicit rather than first-class. A Qwen
run that exits successfully without editing anything reaches generic commit or
test handling instead of an immediate Qwen capability escalation. The external
Qwen helper is instructed not to modify Tess-owned tests, but no deterministic
guard rejects such a mutation before those tests become the acceptance gate.

### Target Users

The solo maintainer running unattended autopilot batches who wants local Qwen
to save Claude quota without letting unmeasured task shapes or self-modified
tests become completion authorities.

### Success Metrics

- A newly planned task is Qwen-eligible only when its expected implementor
  write set contains exactly one file, in addition to the existing backend,
  tier, and public-contract predicates.
- A stale task carrying `qwen_eligible: true` cannot dispatch to Qwen when the
  actual `FILE_PATHS` write set contains two or more files.
- A two- or three-file backend task records the existing `files` exclusion and
  follows the existing Codex-or-Claude routing fences; narrowing Qwen does not
  silently disable the Codex rung.
- A successful Qwen process with no implementation diff is recorded as a Qwen
  capability failure and escalates through the existing one-shot
  `qwen -> sonnet` edge without attempting an empty commit.
- Any Qwen mutation of Tess-owned test paths is detected before staging or
  gate execution, cannot become the test oracle, and escalates through the
  same one-shot edge.
- The plugin's Qwen integration documentation names Qwen3.8, the qualified
  single-file scope, and the multi-file eval's pending-review status; no active
  documentation claims that three-file tasks are within Qwen's trust scope.

## Functional Decomposition

### Capability: Measured Qwen Eligibility

Keep plan-time classification and task splitting within the scope the eval
actually established.

#### Feature: Single-file eligibility predicate
- **Description**: Narrow the persisted Qwen eligibility decision from up to
  three files to exactly one expected implementor-writable file.
- **Inputs**: Task backend/UI classification, final tier, public-contract fact,
  and planned file slice.
- **Outputs**: Existing `qwen_eligible` Boolean and
  `qwen_excluded_reason` value.
- **Behavior**: Preserve the current precedence for `ui`, `tier`, and
  `contract`; when an otherwise eligible task has two or more writable files,
  persist `qwen_eligible: false` and `qwen_excluded_reason: "files"`. A
  one-file backend task at Haiku/Sonnet tier with no public-contract edit stays
  eligible. An empty or missing file slice is never Qwen-eligible.

#### Feature: Eligibility-aware splitting
- **Description**: Align the eligibility split target with the one-file
  predicate without manufacturing invalid task boundaries.
- **Inputs**: Functional decomposition, dependency graph, Qwen preflight, and
  per-task file slices.
- **Outputs**: Either independently testable one-file tasks or the original
  multi-file task marked Qwen-ineligible.
- **Behavior**: A Qwen-only split may produce one-file slices only when every
  resulting task independently compiles, carries its own passing gate, and
  introduces no symbol required by a sibling. Correlated implementation/test,
  interface/implementation, and implementation/caller edits remain together
  and route above Qwen. The context-budget split remains independent and
  unchanged.

### Capability: Dispatch-Time Trust Fence

Prevent stale planner metadata and untrusted Qwen output from bypassing the
measured scope.

#### Feature: Runtime write-set reconciliation
- **Description**: Reconcile `qwen_eligible` with the concrete `FILE_PATHS`
  list before implementor selection.
- **Inputs**: Persisted task routing fields and the newline-delimited write set
  already rendered for Ivan.
- **Outputs**: Effective routing decision and exclusion telemetry.
- **Behavior**: Exactly one non-empty path may reach the Qwen row. Two or more
  paths take the same effective `files` exclusion used by new plans, then flow
  through the existing Codex interception and Claude fallback rules. Zero
  paths fail closed to Claude at the task tier. The compatibility fence is
  evaluated per task and does not rewrite unrelated state.

#### Feature: Qwen no-edit escalation
- **Description**: Make an exit-zero Qwen no-op an explicit capability
  failure.
- **Inputs**: Qwen process success and the task-scoped implementation diff.
- **Outputs**: Attempt outcome/cause and a Sonnet re-dispatch.
- **Behavior**: When no task-owned implementation path changed, do not stage,
  commit, or accept the helper's report. Record cause `qwen_no_edit`, consume
  the one Qwen attempt, and enter the existing `qwen -> sonnet` capability
  edge. Foreign dirty paths never count as Qwen edits and remain untouched.

#### Feature: Tess-test immutability guard
- **Description**: Prevent Qwen from changing the tests that judge its work.
- **Inputs**: Tess-owned test paths, `<test_commit_sha>`, and the post-Qwen
  working tree.
- **Outputs**: Either an unchanged canonical test set or a Qwen capability
  escalation.
- **Behavior**: Before staging or running step 5.5, compare every Tess-owned
  test path to `<test_commit_sha>`. Any difference records cause
  `qwen_test_mutation`, rejects the Qwen attempt, and uses the existing safe
  reset/escalation machinery so Sonnet receives the original committed tests.
  Test-only tasks, where Ivan is intentionally allowed to edit named tests,
  retain their current non-Qwen path.

### Capability: Integration Contract and Evidence

Keep code, prose, state documentation, and tests in agreement.

#### Feature: Routing and telemetry contract
- **Description**: Extend the pure routing model and attempt documentation to
  represent the narrowed scope and the two Qwen-specific failure causes.
- **Inputs**: Planner output, runtime write-set count, and Qwen attempt result.
- **Outputs**: Deterministic routing verdicts and documented attempt records.
- **Behavior**: Unit tests pin one-file Qwen routing, stale multi-file
  rejection, two/three-file Codex interception, zero-file fail-closed routing,
  `qwen_no_edit`, and `qwen_test_mutation`. Existing preflight, breaker,
  memory-pressure, tier, and public-contract cases remain byte-for-byte in
  behavior.

#### Feature: Qwen integration documentation sync
- **Description**: Replace the plugin's stale Qwen3.6/three-file guidance with
  Qwen3.8's qualified single-file rule and the multi-file eval's
  not-yet-decision-grade status.
- **Inputs**: Agent-skills audit result dated 2026-09-03 and the implemented
  routing behavior.
- **Outputs**: Updated plugin references and changelog entry.
- **Behavior**: Documentation distinguishes Qwen as a speculative one-shot
  implementor from Sonnet as the correctness fallback/reviewer, and states
  that two-or-more-file tasks route above Qwen.

## Structural Decomposition

### Repository Structure

```
skills/
├── plan-tasks/
│   ├── SKILL.md                          # Single-file predicate and split rule
│   └── scripts/test_plan_tasks_prose.py  # Prose contract pins
├── work/
│   ├── SKILL.md                          # Runtime fence and failure handling
│   ├── references/
│   │   ├── qwen-integration.md           # Measured scope and Qwen3.8 docs
│   │   ├── gate-failure.md               # One-shot escalation causes
│   │   └── attempt-logging.md            # Attempt-field semantics
│   └── scripts/
│       ├── work_routing.py                # Pure effective-routing model
│       └── test_work_routing.py           # Routing matrices
├── run-autopilot/references/
│   ├── model-ladder.md                    # Preserved qwen -> sonnet edge
│   └── state-schema.md                    # New cause values
└── use-qwen/                               # External personal skill; unchanged
CHANGELOG.md
```

### Module: Plan-Time Qwen Scope
- **Maps to capability**: Measured Qwen Eligibility
- **Responsibility**: Produce task shapes and routing metadata consistent with
  single-file trust.
- **Exports**:
  - `qwen_eligible` / `qwen_excluded_reason` task metadata
  - Step 4.6 eligibility-split contract

### Module: Work Routing and Guards
- **Maps to capability**: Dispatch-Time Trust Fence
- **Responsibility**: Enforce the scope at dispatch and reject no-edit or
  test-mutating Qwen attempts before acceptance.
- **Exports**:
  - Effective implementor verdict
  - `qwen_no_edit` and `qwen_test_mutation` failure causes

### Module: Qwen Integration Contract
- **Maps to capability**: Integration Contract and Evidence
- **Responsibility**: Keep the model ladder, attempt schema, documentation,
  tests, and changelog synchronized with runtime behavior.
- **Exports**:
  - Regression suite for routing and failure paths
  - Operator-facing measured-scope documentation

## Dependency Graph

### Foundation Layer (Phase 0)
No dependencies - built first.

- **Plan-Time Qwen Scope**: Establishes the one-file authority used by later
  runtime and documentation work.

### Core Layer (Phase 1)
- **Work Routing and Guards**: Depends on [Plan-Time Qwen Scope].

### Integration Layer (Phase 2)
- **Qwen Integration Contract**: Depends on [Plan-Time Qwen Scope, Work
  Routing and Guards].

## Implementation Phases

### Phase 0: Foundation
**Goal**: Newly planned work never advertises unmeasured multi-file Qwen
eligibility.

**Tasks**:
- [x] Change plan-tasks' Qwen predicate to exactly one non-empty writable file,
  change the `files` exclusion boundary to two-or-more files, and update every
  worked example and prose pin (no deps) - Acceptance: the plan-tasks prose
  suite passes; `rg -n "files_touched <= 3|files_touched >= 4|<=3.file"
  skills/plan-tasks` finds no active rule; the one-file and two-file examples
  state opposite eligibility verdicts.
- [x] Align step 4.6's eligibility splitting with one-file slices while
  preserving the independent-compilation/test and dependency prohibitions (no
  deps) - Acceptance: prose tests prove an inseparable two-file task remains
  one task and is Qwen-ineligible, while a separable two-file task may become
  two independently gated one-file tasks; context-budget wording remains
  unchanged.

**Exit Criteria**: New task plans expose Qwen only for a single writable file.

### Phase 1: Core
**Goal**: Runtime rejects stale or untrustworthy Qwen dispatches before they
can become accepted work.

**Tasks**:
- [x] Add the per-task runtime write-set reconciliation to `/work` and its pure
  routing model (depends on: Phase 0) - Acceptance: routing tests cover one,
  two, three, and zero paths; two/three take the existing Codex interception
  when its six fences pass and otherwise Claude; no multi-file case reaches
  the Qwen row even with stale `qwen_eligible: true`.
- [x] Add the exit-zero no-edit guard and route it through the existing Qwen
  one-shot escalation (depends on: Phase 1 routing fence) - Acceptance: a test
  fixture with only foreign dirty paths records `qwen_no_edit`, leaves those
  paths untouched, performs no empty commit, and selects Sonnet next.
- [x] Add the Tess-test immutability guard before staging/gating and route a
  violation through the same safe reset and escalation path (depends on:
  Phase 1 routing fence) - Acceptance: a fixture where Qwen changes both an
  implementation file and a Tess-owned test records `qwen_test_mutation`,
  restores the committed test content, rejects the Qwen attempt, and selects
  Sonnet; a test-only task's existing path is unchanged.

**Exit Criteria**: Planner drift, no-op success, and self-modified tests cannot
produce an accepted Qwen result.

### Phase 2: Integration
**Goal**: Every consumer and operator-facing reference agrees with the
enforced scope.

**Tasks**:
- [x] Update gate-failure, attempt-logging, state-schema, and model-ladder
  references for the new effective fence and cause values, without changing
  the one-shot budget or escalation target (depends on: Phase 1) - Acceptance:
  prose-contract tests find both cause values exactly once in their authority
  sections and still find `qwen -> sonnet` as the capability edge.
- [x] Update `skills/work/references/qwen-integration.md` from Qwen3.6 and the
  three-file claim to Qwen3.8, the qualified single-file evidence, the
  2026-09-03 multi-file eval's pending-review status, and the enforced
  single-file rule; add a CHANGELOG entry (depends on: Phase 1) -
  Acceptance: `rg -n "Qwen3.6|<= ?3|≤ ?3" skills/work/references/qwen-integration.md`
  finds no active Qwen trust-scope claim, and the document retains the
  preflight and one-shot Sonnet fallback sections.
- [x] Run the focused plan/work suites and the full repository suite (depends
  on: all prior tasks) - Acceptance: `uv run pytest -q
  skills/plan-tasks/scripts/test_plan_tasks_prose.py
  skills/work/scripts/test_work_routing.py` exits 0; `uv run pytest -q` exits
  0; plugin validation/release checks required by repository instructions pass.

**Exit Criteria**: Code, tests, state contract, operator guidance, and changelog
all encode the same single-file Qwen scope.

## Test Strategy

### Critical Scenarios
- **Happy path**: one-file backend Haiku/Sonnet task, healthy Qwen, clean
  output diff -> Expected: one Qwen attempt proceeds through the normal gate.
- **Edge case**: stale `qwen_eligible: true` on a two-file task -> Expected:
  Qwen is skipped and existing Codex/Claude fences decide the implementor.
- **Edge case**: correlated implementation/test or interface/caller files ->
  Expected: planner keeps them together and marks the task Qwen-ineligible.
- **Error case**: Qwen exits 0 with no task-owned edit -> Expected:
  `qwen_no_edit`, no empty commit, immediate Sonnet escalation.
- **Error case**: Qwen edits a Tess-owned test -> Expected:
  `qwen_test_mutation`, canonical tests restored, immediate Sonnet escalation.
- **Regression case**: Qwen preflight, breaker, memory gate, UI, Opus, or
  contract exclusion -> Expected: current routing and telemetry remain
  unchanged.

## Risks

- **Reduced local-model utilization**: Two- and three-file work leaves Qwen.
  The existing Codex interception remains available for `files` exclusions,
  and telemetry can justify a later widening only after a new eval.
- **Over-splitting to chase Qwen eligibility**: Single-file slices can sever a
  real dependency. The independent compile, test, and symbol-dependency gates
  are mandatory; otherwise the original task stays intact.
- **Planner/runtime disagreement**: Duplicating the boundary can drift. The
  runtime fence is intentionally fail-closed, and tests pin the same one-file
  examples at both layers.
- **Test restoration discards unrelated work**: Compare and restore only
  Tess-owned paths captured at the task's own test commit, using the existing
  foreign-work/reset guards; any ambiguity takes the safe escalation path
  without destructive reset.
