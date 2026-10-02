---
catchup: skip
design: skip
default_model: sonnet
model_tier_rationale: prose-only change with the exact replacement sentence given below; prose-pin tests fail loudly on a wrong edit
---

# Route rework fixes on their own tier

Source: `dev/local/notes/review-time-analysis-2026-09-30.md` R1.

## Overview

### Problem Statement

Phase 6 (`skills/run-autopilot/references/phase-review.md`, "Decision gate
`[D{cycle}]` follow-ups") computes a rework task's tier as
`max(classifier_tier, default_model)`. The Tail sweep reuses the same
mechanics. A PRD pinned to `default_model: opus` for its initial build
therefore runs every review fix through the opus pipeline, Devon and his
strengthen rounds included, however small the fix.

Measured on 00223 (opus floor), 2026-09-29/30:
- Rework tasks took 71-118 min each. Task 5, rejecting a non-basename
  `--prd`, took 71 min and 4 test commits for a 2-line fix.
- 00218's sonnet-floor rework tasks took 10-33 min each.

The floor exists for the initial build's design risk. A `[D]` fix is a
pinned regression against a quoted finding, which the classifier already
routes to sonnet unless it edits a contract or carries algorithmic risk.

### Target Users

The unattended loop's review-rework cycles.

### Success Metrics

- `uv run --no-project --with pytest python -m pytest -q skills/run-autopilot/scripts/test_rework_tier_prose.py`
  green; every existing prose test under `skills/run-autopilot/` and
  `skills/plan-tasks/scripts/` green.
- `bash dev/bin/release-checks` green.
- Post-release signal: in the next batch, a `[D]` task on an opus-floor PRD
  records `tier_reason` from the classifier (never `floor`) unless its
  findings include a 🔴 line.

## Functional Decomposition

### Capability: Rework tiers ignore the build floor

#### Feature: The floor applies to CRITICAL rework only
- **Description**: a `[D{cycle}]` task takes the PRD floor only when it
  carries a 🔴 finding.
- **Inputs**: the task's `### Findings (verbatim)` block; PRD frontmatter
  `default_model`.
- **Outputs**: the task's `model` in `task-add`.
- **Behavior**: in `phase-review.md`, the Phase 6 bullet that begins
  "Compute the tier:" changes its second sentence from "Then apply the
  `default_model` floor **exactly as `/autopilot:plan-tasks` step 4.7 defines
  it** (the single source of truth): `final_tier = max(tier, default_model)`;"
  to "Then, only when the task's findings include at least one 🔴 CRITICAL
  line, apply the `default_model` floor **exactly as `/autopilot:plan-tasks`
  step 4.7 defines it** (the single source of truth): `final_tier = max(tier,
  default_model)`. A task with no 🔴 line keeps the classifier tier (or
  `sonnet`): the floor buys design depth for the initial build, and a
  rework fix is a pinned regression the classifier already routes (measured:
  opus-floor rework tasks 71-118 min against 10-33 min at sonnet, 00223 and
  00218, 2026-09-30);". The rest of that bullet (re-parse, warnings, not
  persisted) is unchanged. The Tail sweep sentence ("then the `default_model`
  floor exactly as that section computes it") is unchanged; it now inherits
  the rule because it points at the same section. `plan-tasks/SKILL.md`
  step 4.7 gains one sentence at the end of its floor list: "Review-rework
  `[D]` tasks take this floor only when they carry a 🔴 finding
  (`run-autopilot/references/phase-review.md` Phase 6)."

## Structural Decomposition

### Repository Structure

```
skills/run-autopilot/references/phase-review.md       # Maps to: The floor applies to CRITICAL rework only
skills/plan-tasks/SKILL.md                            # step 4.7 pointer sentence
skills/run-autopilot/scripts/test_rework_tier_prose.py  # Maps to: Test Strategy
dev/bin/release-checks                                # the new prose test
CHANGELOG.md
```

### Module: phase-review prose
- **Maps to capability**: Rework tiers ignore the build floor
- **Responsibility**: the rework tier rule.
- **Exports**: the sentence above.

## Dependency Graph

### Foundation Layer (Phase 0)
No dependencies - built first.

- **phase-review prose and the plan-tasks pointer**: prose only.

### Core Layer (Phase 1)
- **prose test and release wiring**: Depends on [phase-review prose].

### Integration Layer (Phase 2)
- **CHANGELOG**: Depends on [prose test and release wiring].

## Implementation Phases

### Phase 0: Foundation
**Goal**: the rule is written.

**Tasks**:
- [ ] Replace the floor sentence in `phase-review.md` Phase 6 and add the
  step 4.7 pointer in `plan-tasks/SKILL.md` (no deps) - Acceptance: `rg -c
  "only when the task's findings include at least one 🔴 CRITICAL line"
  skills/run-autopilot/references/phase-review.md` prints 1; `rg -c
  "Review-rework \`\[D\]\` tasks take this floor only when they carry a 🔴
  finding" skills/plan-tasks/SKILL.md` prints 1.

**Exit Criteria**: both greps print 1.

### Phase 1: Core
**Goal**: the rule is pinned.

**Tasks**:
- [ ] Add `skills/run-autopilot/scripts/test_rework_tier_prose.py` and
  list it in `dev/bin/release-checks` beside the other run-autopilot prose
  tests (depends on: Phase 0) - Acceptance:
  `test_rework_tier_prose.py::test_floor_applies_only_to_critical_rework`
  (the "Compute the tier" bullet contains "only when the task's findings
  include at least one 🔴 CRITICAL line" and still contains
  "`final_tier = max(tier, default_model)`"),
  `::test_non_critical_rework_keeps_the_classifier_tier` (the same bullet
  contains "keeps the classifier tier"),
  `::test_plan_tasks_points_at_the_rework_rule` green; every existing prose
  test green.

**Exit Criteria**: the new file green.

### Phase 2: Integration
**Goal**: shipped.

**Tasks**:
- [ ] `CHANGELOG.md` `[Unreleased]` `### Changed`: `**run-autopilot**`
  line saying review-rework fixes take the PRD's `default_model` floor only
  for CRITICAL findings (depends on: Phase 1) - Acceptance: `bash
  dev/bin/release-checks` green; `rg -c "floor only for CRITICAL"
  CHANGELOG.md` prints 1.

**Exit Criteria**: `release-checks` green.

## Test Strategy

### Critical Scenarios
- **Happy path**: an opus-floor PRD, a `[D1]` task with only 🟡 findings on
  one test file → classifier `sonnet`/`test_port`, task runs at sonnet, no
  Devon.
- **Edge case**: the same PRD, a `[D1]` task with one 🔴 line → `opus`
  (floor), with the rework design contract block as today.
- **Error case**: malformed frontmatter → warn once, classifier tier passes
  through (unchanged behavior).

## Risks

- **A non-critical fix that needed opus depth**: the classifier still
  raises `contract_edit` and `algorithmic_risk` tasks to opus, the per-task
  Pat review and the next cycle's review still see the fix, and the task
  escalates on failure as today.
