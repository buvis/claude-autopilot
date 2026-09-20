---
catchup: run
design: run
default_model: opus
model_tier_rationale: the hook that rotates sessions gains a phase predicate and a phase-aware rotation, and the review gate's resume rule changes with it
---

# Guard review-phase rework sessions

Source: measured on batches 202609050909 (agent-skills) and 202609061630
(claude-autopilot), 2026-09-13; report `dev/local/notes/autoclaude-inefficiencies-2026-09-13.md`
finding 1. Reshaped at the 2026-09-13 backlog review: the turn-headroom
capability moved to PRD 00200 (one headroom predicate over usage and calls),
the lossless-rotation capability moved to PRD 00202. Lands after backlog PRD
00191 (`clear the handoff marker at phase edges`), which owns the marker's
JSON shape and step 6.5's phase preservation; this PRD widens 00191's hook
guard and names the 00191 test it repoints.

## Overview

### Problem Statement

`skills/run-autopilot/scripts/autopilot_context_cap_hook.py:680` returns
before any check unless `state.phase == "build"`. Cycle-1 rework runs
`/autopilot:work` inside the review session (`references/phase-review.md`
§ Session model, :223), where `phase` stays `"review"`, so no soft cap, hard
cap or turn tripwire applies. On 2026-09-07 the claude-autopilot review
session finished its review in 26 minutes, then ran rework tasks 7 and 8
unguarded to 448K context and 427 tool calls until
`_AUTOPILOT_SESSION_MAX_REVIEW` (10800 s, `cli/loop.py:1043`) killed it
mid-Ivan; the 2026-09-13 review session repeated it at 10801 s and $138.53
(`loop-metrics.jsonl`). Ivan's in-flight edit was lost both times.

When the hook does fire, `_append_rotation_to_state` (hook :357) writes
`next_phase = "build"` (:393) unconditionally, and `references/phase-review.md`
Phase 4 has two skips (:14 loop-level, :18 cycle) but none for "review file
written, rework tasks pending", so a rotation inside a review session would
re-enter the build gate, not the rework it left.

### Target Users

The review-phase rework session, which today has no budget at all, and the
operator paying for a 3-hour session that ends with a kill.

### Success Metrics

- No `loop-metrics.jsonl` row with `phase_launched: review` and
  `wall_secs >= 10800` in the next batch (the wall cap no longer fires).
- `uv run --no-project --with pytest python -m pytest -q skills/run-autopilot/scripts/test_autopilot_context_cap_hook.py`
  green with the cases named below, including 00191's review-phase case
  repointed.

## Functional Decomposition

### Capability: Cap guard in rework sessions
The hook applies its checks whenever a task is in progress, not only in the
build gate.

#### Feature: Phase guard admits review-phase rework
- **Description**: The hook runs when `state.phase` is `"build"`, or is
  `"review"` and `state.rework_task_ids` is a non-empty list.
- **Inputs**: `state.json` (`phase`, `rework_task_ids`, `tasks[]`).
- **Outputs**: unchanged hook behaviour (soft marker, rotation, livelock
  stall) in both phases.
- **Behavior**: `main()` replaces `state.get("phase") != "build"` with
  `_guarded_phase(state) -> bool`: True for `build`, True for `review` with
  a non-empty `rework_task_ids`, False otherwise. A review session with no
  rework (Phase 4 and 5 only) stays unguarded. Premise (re-check at
  execution): PRD 00191 has landed and its hook test asserting no write in
  the review phase exists; that test is renamed to the review-without-rework
  case in the same commit. If 00191 has not landed, skip and report.

#### Feature: Rotation returns to the phase it left
- **Description**: A rotation or livelock stall in a review session sets
  `next_phase` to `"review"`, never `"build"`.
- **Inputs**: `state.phase` at fire time.
- **Outputs**: `state.next_phase == state.phase`; the rotation envelope names
  the phase.
- **Behavior**: `_append_rotation_to_state` writes
  `fresh["next_phase"] = fresh["phase"]`; `_rotation_instructions(limit, phase)`
  says "next_phase is set to <phase>". The soft-marker handoff path is
  00191's ("Step 6.5 honours only its own phase") and is not edited here.

#### Feature: Review gate resumes rework without re-reviewing
- **Description**: `references/phase-review.md` Phase 4 gains a third skip.
- **Inputs**: this cycle's review file, `state.rework_task_ids`, `state.tasks[]`.
- **Outputs**: the session resumes at Phase 6 "Dispatch rework" (:254).
- **Behavior**: after the cycle skip at :18: `Skip Phases 4 and 5 and resume
  at Phase 6 "Dispatch rework" when this cycle's review file exists and
  state.rework_task_ids names a task whose status is not completed.`

## Structural Decomposition

### Repository Structure

```
skills/
├── run-autopilot/
│   ├── scripts/
│   │   ├── autopilot_context_cap_hook.py        # Maps to: Cap guard in rework sessions
│   │   └── test_autopilot_context_cap_hook.py   # Maps to: new and repointed cases
│   ├── references/
│   │   └── phase-review.md                      # Maps to: Review gate resumes rework
│   └── scripts/
│       └── test_review_resume_prose.py          # Maps to: Review gate resumes rework (new)
└── work/
    └── references/task-boundary-handoff.md      # unchanged (owned by 00191)
```

### Module: autopilot_context_cap_hook
- **Maps to capability**: Cap guard in rework sessions
- **Responsibility**: decide, once per PostToolUse, whether this session
  rotates, stalls, or requests a boundary handoff, in either guarded phase
- **Exports**:
  - `_guarded_phase(state) -> bool`
  - `_rotation_instructions(limit, phase) -> str`

### Module: phase-review prose
- **Maps to capability**: Cap guard in rework sessions
- **Responsibility**: the Phase 4 third skip
- **Exports**: none (prose pinned by `test_review_resume_prose.py`)

## Dependency Graph

### Foundation Layer (Phase 0)
No dependencies - built first.

- **autopilot_context_cap_hook**: phase predicate and phase-aware rotation.

### Core Layer (Phase 1)
- **phase-review prose**: Depends on [autopilot_context_cap_hook] (a rotation
  now lands on the review gate).

### Integration Layer (Phase 2)
- **CHANGELOG and release gate**: Depends on [Phase 0, Phase 1].

## Implementation Phases

### Phase 0: Foundation
**Goal**: the hook guards review-phase rework and returns to the phase it left.

**Tasks**:
- [ ] Add `_guarded_phase` and use it in `main()`; repoint 00191's
  review-phase no-write case (no deps) - Acceptance: in
  `test_autopilot_context_cap_hook.py`, `test_phase_not_build_is_noop`
  (:133) and 00191's review-phase case become `test_review_without_rework_is_noop`;
  new `test_review_with_rework_ids_is_guarded` sees the marker written at
  `USAGE_CAP - 1` with `phase: "review"`, `rework_task_ids: ["7"]` and
  headroom exhausted per 00200's rule (or, if 00200 has not landed, at
  `SOFT_CAP + 1`); `test_noops_on_work_phase` (:143) unchanged.
- [ ] Rotation and stall write `next_phase = phase`; `_rotation_instructions`
  takes `(limit, phase)` (no deps) - Acceptance:
  `test_rotation_in_review_phase_sets_next_phase_review`,
  `test_rotation_text_names_the_phase` pass; `test_rotation_instructions_takes_only_limit_parameter`
  (:638) is rewritten as `test_rotation_instructions_takes_limit_and_phase`;
  every existing rotation test still passes with `phase: "build"`.

**Exit Criteria**: cap hook suite green; a review-phase fixture with rework
ids over the cap produces `.handoff-requested`; one without rework ids at
600K produces nothing.

### Phase 1: Core
**Goal**: a rotated review session resumes its rework.

**Tasks**:
- [ ] phase-review.md Phase 4 third skip (depends on: Phase 0) - Acceptance:
  `scripts/test_review_resume_prose.py::test_review_gate_resumes_rework_from_the_review_file`
  finds the skip sentence between the cycle skip and the
  `/autopilot:review-work-completion` invocation; `test_review_coverage_hook_registration.py`
  still green.

**Exit Criteria**: `pytest -q skills/run-autopilot/scripts` green.

### Phase 2: Integration
**Goal**: the change is recorded and gated.

**Tasks**:
- [ ] CHANGELOG `### Fixed` entry under `**run-autopilot**` naming the
  review-phase rework guard (depends on: all) - Acceptance:
  `rg -c "review-phase rework" CHANGELOG.md` returns 1 or more;
  `bash dev/bin/release-checks` green.

**Exit Criteria**: `bash dev/bin/release-checks` green.

## Test Strategy

### Critical Scenarios
- **Happy path**: review-phase fixture, `rework_task_ids: ["7"]`, usage over
  the headroom rule -> marker present; a rotation sets `next_phase: review`.
- **Edge case**: review-phase fixture with empty `rework_task_ids` at 600K ->
  hook is a no-op.
- **Edge case**: `rework_task_ids` present but every listed task `completed`
  -> the Phase 4 skip does not fire; the gate continues to Phase 5 as today.
- **Error case**: `rework_task_ids` not a list -> treated as empty (no crash,
  one stderr line).

## Risks

- **00191 lands with a different test name**: the premise re-check names the
  behaviour ("no write in the review phase"), not the identifier; the task
  reports and skips if no such case exists.
- **A rotated review session re-runs Phase 4**: mitigated by the third skip;
  the prose test pins it.
