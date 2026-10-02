---
catchup: skip
design: skip
default_model: sonnet
model_tier_rationale: prose edits in two reference files with an existing skip path to reuse, pinned by substring tests; no code
rework_cap: 2
---

# Hand off between the rework design and the first fix task

Source: `dev/local/notes/validation-batch-054-2026-09-20.md` findings V3b and V5
(2026-09-21). Grounded at `b78bc11` (0.5.4). Pairs with 00207 (the fresh session
this hand-off produces routes on task tier); independent of 00209-00211.

## Overview

### Problem Statement

Phase 6 (`references/phase-review.md` § Dispatch rework) runs the cycle's rework
design (three dispatches), creates the `[D{cycle}]` tasks and then invokes
`/autopilot:work` in the same session. By that point the session already holds
the review consolidation and three design-review prompt packages: 00052's
session 3 was at 464K when task 4 started (`usage_at_start` in `state.tasks`),
the headroom rule fired at task-start, the hard cap then hit mid-task and the
session rotated after 56 minutes and $60 with the task unfinished; session 4
redid it. 00055 showed the same shape at smaller scale. The 00196 resume path
already exists: a review session whose cycle review file is on disk and whose
`rework_task_ids` names an unfinished task skips Phases 4-5 and lands in
Dispatch rework. Nothing uses it on purpose today; it is reached only after a
rotation.

### Target Users

The loop operator; the review-rework loop under `_AUTOPILOT_LOOP`.

### Success Metrics

- `uv run --no-project --with pytest python -m pytest -q skills/run-autopilot/cli/test_design_rework_prose.py skills/run-autopilot/cli/test_custody_prose.py`
  green with the new pins present.
- `bash dev/bin/release-checks` green.
- Post-release signal: a rework session's `usage_at_start` for its first rework
  task is under 150K (a fresh session that read the brief), and no `review`
  row rotates on its first rework task.

## Functional Decomposition

### Capability: Rework hand-off

#### Feature: Hand off after task-add in loop mode
- **Description**: once both rework sources are merged into
  `state.rework_task_ids`, a loop-mode session hands off instead of invoking
  `/autopilot:work`.
- **Inputs**: `$_AUTOPILOT_LOOP`, `state.rework_task_ids` (non-empty after
  task-add), the cycle's review file on disk.
- **Outputs**: the Session handoff procedure's artifacts (contract card, brief,
  `leave` row, banner) with `state.phase`/`next_phase` staying `review` and
  `state.cycle` unchanged (no `phase-done`: the cycle is not over).
- **Behavior**: replace "Invoke `/autopilot:work`" in loop mode with: write the
  contract card naming the rework tasks and the design doc path, write the
  brief, write the `leave` row (`--site review --edge leave --phase review`),
  print `── AUTOPILOT ── PRD: {prd} ── rework designed, handing off {n} task(s)
  ──`, END TURN. The next session enters Phase 4's existing skip ("Skip Phases
  4 and 5 and resume at Phase 6 Dispatch rework", PRD 00196) and invokes
  `/autopilot:work` there. Interactive runs (no `_AUTOPILOT_LOOP`) keep
  invoking `/autopilot:work` in-session as today.

#### Feature: The resume path names its entry
- **Description**: the 00196 skip paragraph in Phase 4 says it is also the
  normal loop-mode entry after a rework hand-off, not only a rotation's.
- **Inputs**: `references/phase-review.md` § Phase 4, the skip paragraph.
- **Outputs**: one added sentence; `references/state-schema.md`'s
  `rework_task_ids` row notes that a non-empty list with the cycle's review
  file on disk means "rework queued, dispatch pending".
- **Behavior**: prose only; the skip's conditions are unchanged.

## Structural Decomposition

### Repository Structure

```
skills/run-autopilot/
├── references/phase-review.md      # Maps to: both features
├── references/state-schema.md      # Maps to: the resume path row
├── cli/test_design_rework_prose.py # Maps to: Test Strategy (Dispatch rework pins)
└── cli/custody_prose_testutil.py   # Maps to: no change (helpers reused)
```

### Module: phase-review prose
- **Maps to capability**: Rework hand-off
- **Responsibility**: the loop-mode hand-off sentence and the resume note.
- **Exports**: the two amended sections.

## Dependency Graph

### Foundation Layer (Phase 0)
- **phase-review prose**: no dependencies.

## Implementation Phases

### Phase 0: Hand-off
**Goal**: loop-mode Phase 6 ends the session after task-add.

**Tasks**:
- [ ] Amend `### Dispatch rework`'s closing paragraph ("After both sources are
  merged ... Invoke `/autopilot:work`") with the loop-mode hand-off and keep the
  interactive path (no deps) - Acceptance:
  `test_design_rework_prose.py::test_loop_mode_hands_off_after_task_add_before_work`
  pins, in the Dispatch section: `rework designed, handing off`, `END TURN`,
  `$_AUTOPILOT_LOOP` before `Invoke `/autopilot:work``, and the absence of
  `invoke /autopilot:work in this session` for loop mode; existing pins
  (roster sentence, escalation caveat, `task-add <task-json-file>` order) stay
  green.
- [ ] Add the resume sentence to the Phase 4 skip paragraph and the
  `rework_task_ids` schema note (depends on: task 1) - Acceptance:
  `test_design_rework_prose.py::test_phase_4_skip_is_the_rework_handoff_entry`
  pins `after a rework hand-off` in the skip paragraph and `dispatch pending`
  in the schema row; `test_custody_prose.py` and `test_custody_prose_schema.py`
  stay green; CHANGELOG `### Changed` entry under `**run-autopilot**`.

**Exit Criteria**: suites green; release-checks green.

## Test Strategy

### Critical Scenarios
- **Happy path**: loop mode, two D-tasks created → the section orders task-add,
  hand-off artifacts, END TURN, and never `/autopilot:work` before END TURN.
- **Edge case**: interactive mode → `/autopilot:work` is still invoked in the
  section (the pin checks the interactive sentence survives).
- **Error case**: the rework design failure branch is untouched (its pins in
  `test_rework_design_failure_stalls_in_loop_and_pauses_interactively` stay
  green).

## Risks

- **One more session per rework cycle**: a fresh session costs ~3 minutes of
  orientation (brief) and, with 00207, runs on sonnet; it replaces a rotation
  that cost 56 minutes. Accepted.
- **The next session re-reviews instead of resuming**: guarded by the existing
  00196 skip, which keys on the review file and an unfinished listed task; both
  hold after task-add.

### Deferred

Review 1 (2026-09-21, 5 findings, 0 CRITICAL / 2 HIGH / 1 MEDIUM / 2 info). Both HIGHs
fixed and re-reviewed: the hand-off now belongs to the session that ran Phases 4-5 and
created the tasks, a session entering through the Phase 4 skip invokes `/autopilot:work`
and never hands off again (no endless hand-off), and the paragraph names steps 2 and 3
of the Session handoff procedure explicitly with step 1 (`phase-done`) skipped on
purpose. The Medium (pins for card → brief → leave row → banner order, unchanged state,
the resume bypass) is fixed in the same commit; Alice's PEP8 blank-line nit fixed.

- [Info] Bob's VERIFY: `test_design_rework_prose.py`, `test_custody_prose.py` and `release-checks` green at HEAD (answered)

Review 2 (2026-09-21, 1 finding, 1 HIGH, cap reached). Fixed after the cap, unreviewed -
verbatim: "The new first-session guard requires that the session 'created the tasks
above,' but Phase 6 also supports C-only rework batches whose existing tasks are merely
requeued; in that valid loop-mode path no branch invokes `/autopilot:work`. Guard on
rework being queued in the current session - or on not entering through the Phase 4 skip
- and pin the C-only case." The guard now keys on how the session entered (it ran Phases
4-5 of this cycle versus it came through the Phase 4 skip), states that it covers D-only,
C-only and mixed batches, and the pin binds the C-only sentence.

