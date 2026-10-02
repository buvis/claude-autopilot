---
catchup: skip
design: skip
default_model: sonnet
model_tier_rationale: one condition added to an existing three-condition rule and one prose pin; no design call
rework_cap: 2
---

# Run a forced catchup once per PRD entry, never on a same-PRD resume

Source: `dev/local/notes/validation-batch-054-2026-09-20.md` finding V2
(2026-09-20). Grounded at `b78bc11` (0.5.4). Independent of 00207-00211.

## Overview

### Problem Statement

`references/phase-build.md` § Batch cache check skips the full catchup only when
`state.catchup_mode != "force"` (condition 1). A PRD stamped `catchup: force`
therefore re-runs `/git-ferry:catchup` at EVERY Phase 0 entry, including a
task-boundary resume inside the same PRD, right after the session read the
brief (PRD 00201) that already says where the batch stands. Measured on
agent-skills 00052 session 2: context 80K → 267K in 66 calls before task 3
started, the headroom rule fired at task-start, and the same happened on the
00055 resume. `force` exists to defeat a stale batch cache at PRD entry, not to
re-derive the capsule between two tasks of one PRD.

### Target Users

PRDs that pin `catchup: force`; the loop operator.

### Success Metrics

- `uv run --no-project --with pytest python -m pytest -q skills/run-autopilot/cli/test_custody_prose.py skills/work/scripts/test_handoff_placement_prose.py`
  green with the new pin.
- `bash dev/bin/release-checks` green.
- Post-release signal: a build session that resumes with `state.tasks` present
  logs `catchup: delta refresh` (or `skipped`) rather than a full catchup, and
  `usage_at_start` of its first task is under 150K.

## Functional Decomposition

### Capability: Force scope

#### Feature: Force applies at PRD entry only
- **Description**: condition 1 of the cache check reads `force` only when the
  PRD has not been planned yet.
- **Inputs**: `state.catchup_mode`, `state.tasks`.
- **Outputs**: the amended condition and a one-line note printed on the
  resume path.
- **Behavior**: condition 1 becomes: `state.catchup_mode != "force"`, OR
  `state.tasks` is a non-empty list (planning already ran for this PRD, so this
  entry is a same-PRD resume and `force` is spent). When `force` is spent the
  session prints `── AUTOPILOT ── catchup: force already spent on this PRD
  (tasks present) ──` and evaluates conditions 2 and 3 as today. `skip` and
  `run` are unchanged.

## Structural Decomposition

### Repository Structure

```
skills/run-autopilot/
├── references/phase-build.md          # Maps to: the cache check condition
└── cli/test_custody_prose.py          # Maps to: Test Strategy (phase-build pins live here)
```

### Module: phase-build prose
- **Maps to capability**: Force scope
- **Responsibility**: the cache-check condition text and the frontmatter table
  row for `catchup`.
- **Exports**: the amended § Batch cache check and § Frontmatter parse row.

## Dependency Graph

### Foundation Layer (Phase 0)
- **phase-build prose**: no dependencies.

## Implementation Phases

### Phase 0: Condition
**Goal**: `force` is spent once planning exists.

**Tasks**:
- [ ] Amend condition 1 of § Batch cache check and the `catchup` row of the
  frontmatter table (no deps) - Acceptance:
  `test_custody_prose.py::test_forced_catchup_is_spent_once_the_prd_has_tasks`
  pins `force already spent`, `state.tasks` and `same-PRD resume` inside the
  § Batch cache check section and asserts the phrase `re-runs full catchup
  regardless of recency` no longer appears in the frontmatter row; CHANGELOG
  `### Changed` entry under `**run-autopilot**`.

**Exit Criteria**: suites green; release-checks green.

## Test Strategy

### Critical Scenarios
- **Happy path**: `catchup: force`, tasks present → delta refresh when
  conditions 2 and 3 hold.
- **Edge case**: `catchup: force`, tasks absent (fresh PRD entry) → full
  catchup as today.
- **Error case**: `state.tasks` not a list → treated as absent (full catchup,
  the safe side).

## Risks

- **A resume after a long pause runs on a stale capsule**: conditions 2 (4-hour
  age) and 3 (HEAD match) still force a full catchup when the cache is stale.
  Accepted.

### Deferred

Review 1 (2026-09-21, 7 findings, 0 CRITICAL / 2 HIGH / 3 MEDIUM / 2 info). Both HIGHs
fixed after review 1 and re-reviewed: `resume_target` reads a non-list `tasks` as
"no tasks" (the schema already rejects one at write time, so the crash was reachable
only by hand edit), and Phase 0 now says the resume-target line adjudicates the abort
handlers only and never skips the cache check. Fixed Mediums: the schema's
`catchup_mode` row carries the spent-once nuance; the prose pin binds the `OR`
predicate, the exact banner and the non-list rule.

- [Medium] condition 1 mixes predicate, resume action, malformed-state rule and measurement in one item; split into sub-bullets and move the measurement to design-rationale (Bob)
- [Info] post-release metric (a forced same-PRD resume logs delta/skipped and starts its first task under 150K) needs a live batch to verify

Review 2 (2026-09-21, 5 findings, 0 CRITICAL / 0 HIGH, converged). Taken after the cap:
the regression test class moved above the `unittest.main()` guard, `_build_resume_target`'s
docstring names itself the post-Phase-1 resume point, the prose slice is named
`abort_handler`.
- [Medium] mech-check reports `test_build_with_a_non_list_tasks_reads_as_no_tasks` passing at the replay base; at the review branch's base the walker raises on a non-list, so this reads as a replay artifact (mech-check)

