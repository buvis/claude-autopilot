---
catchup: skip
design: run
default_model: opus
model_tier_rationale: crash-safety ordering, a three-party race fixed with a lock, and a landing state machine across wave_assemble, wave_slots and wave_review; each fix has a concurrency or destructive-path edge
---

# Harden the wave verbs

Source: attended triage of six hold stubs on 2026-10-03, each checked against
HEAD (v0.7.0 + the 00240 build in flight). Ledger trail (batch
`202609252154` unless noted):

- 00221 `49a475b28c63`
- 00222 `56d35c9d46d7`
- 00225 `dba0c0eb393a`
- 00226 `eaf3898e53e1`
- 00227 `d190c6d3ccb8`
- 00239 `777766a9a0a1` (batch `202610021244`)

## Overview

### Problem Statement

The wave verbs (PRDs 00214-00217) shipped with six findings their reviews
deferred, and each one still reproduces at HEAD:

1. **Untested in the release gate (00221).**
   `cli/test_wave_assemble_summary.py` (12 tests, three of them PRD-named
   acceptance tests) is in neither `dev/bin/release-checks`' `[checks]
   waves` block nor `test_wave_docs.py`'s `_WAVE_TEST_FILES`. It never runs,
   and the parity test cannot notice because both sides omit it.
2. **Teardown is not crash-safe (00222).** `_drain_lane` and `_assemble_lane`
   change `lane["held_prds"]`, `lane["status"]`, `batch_id` and
   `worktree_removed` in memory only. The single `save()` runs after `git
   worktree remove` and `branch -D`. A crash in that window relabels a merged
   lane `unfinished`, or reruns `lane_files_and_notes` with a removed cwd
   (an uncaught `OSError`).
3. **The assembly worktree check predates the tracked store (00225).** The
   main-checkout gates use `store_tree.foreign_dirty` since 00236, but
   `wave_review.py:403` still reads raw `git status --porcelain` in the
   assembly worktree, so store churn there refuses a review. A tracked store
   also seeds that worktree with the main checkout's `backlog/` PRDs, which
   the nested loop could select.
4. **`land` cannot land after a hand review (00226).** `_land_review_failed`
   (`wave_review.py:483`) returns 4 unconditionally, even after the operator
   moved the stub to the assembly worktree's `prds/done/`. The only way out
   is hand-editing `wave.json`, which nothing documents.
5. **One review slot can reach two holders (00227).** `_discard` renames a
   stale-looking slot aside before judging it (`wave_slots.py:108-116`).
   Between that rename and the put-back, a third `_claim` can take the name,
   so `count=1` admits two sessions. The source comment already names the
   fix: a per-slot `fcntl.flock`.
6. **Review-once commits the store on a lane branch (00239).**
   `Loop._record_review_once_store` (`loop.py:506`) calls `record_store`
   without the `store_tree.in_wave_lane(self.env)` guard that the
   per-session site (`loop.py:611`) and the drained exit
   (`loop_act.py:218`) carry.

### Target Users

Operators running `autopilot wave`; the loop inside a lane.

### Success Metrics

- `uv run --no-project --with pytest --with pytest-xdist python -m pytest -q -n 4 skills/run-autopilot/cli -k "wave or review_once"`
  green, including every test named below.
- `bash dev/bin/release-checks` green, and its `[checks] waves` block now
  runs `test_wave_assemble_summary.py`.

## Functional Decomposition

### Capability: The wave verbs survive crashes, races and hand reviews

#### Feature: Gate the summary tests (00221)
- **Description**: the summary tests run in the release gate.
- **Inputs**: `dev/bin/release-checks`, `test_wave_docs.py`.
- **Outputs**: `cli/test_wave_assemble_summary.py` added to the `[checks]
  waves` pytest call and to `_WAVE_TEST_FILES`.
- **Behavior**: the existing parity test then covers it. A new
  `test_wave_docs.py::test_every_wave_test_file_is_listed` compares
  `_WAVE_TEST_FILES` with `rg --files -g "test_wave*.py"` under `cli/`, so a
  file missing from both sides fails.

#### Feature: Persist before tearing down (00222)
- **Description**: no destructive git step runs before the lane's new
  status is on disk.
- **Inputs**: `wave_assemble.py` `_drain_lane`, `_assemble_lane` and the
  teardown at its current `:524-526`.
- **Outputs**: `wave.save()` runs after `held_prds`, `status` and `batch_id`
  are set and before `worktree remove` and `branch -D`. `worktree_removed` is
  saved right after the remove succeeds.
- **Behavior**: on rerun, a lane whose saved status is merged and whose
  worktree is gone skips `lane_files_and_notes`. `wave_cli.run` catches
  `OSError` from assemble and prints one `autopilot:` line with exit 1.

#### Feature: The assembly worktree ignores store churn (00225)
- **Description**: the assembly-worktree gate uses the store-aware
  predicate, and the nested loop cannot pick up main-checkout backlog PRDs.
- **Inputs**: `wave_review.py:403`; the assembly worktree's
  `docs/dev/project-management/prds/backlog/`.
- **Outputs**: `:403` calls `store_tree.foreign_dirty(worktree,
  run_git=run_git)`. When review seeds the assembly worktree, it moves every
  `prds/backlog/*.md` there into `prds/hold/` and commits that move on the
  assembly branch, before spawning the nested loop.
- **Behavior**: the design doc confirms whether moving to `hold/` or
  deleting is right for the assembly branch (guess: `hold/`, so `land` brings
  nothing back).

#### Feature: Land after a hand review (00226)
- **Description**: a review-failed wave lands once the operator has
  reviewed it by hand.
- **Inputs**: `wave.json` status `review_failed`; the assembly worktree's
  `prds/done/<wave stub>`.
- **Outputs**: `_land_review_failed` checks whether the wave's review stub
  is in the assembly worktree's `prds/done/`. If it is, it sets the status to
  `converged` (saved) and continues into the normal land path. If not, it
  returns 4 as today.
- **Behavior**: `references/waves.md` documents the hand-review route: move
  the stub to `prds/done/` in the assembly worktree, then `autopilot wave
  land`.

#### Feature: Lock the slot reclaim (00227)
- **Description**: a slot cannot reach two holders.
- **Inputs**: `wave_slots.py` `_claim`, `_discard`, `release`.
- **Outputs**: each slot `N` gets a sibling lock file `N.lock`. `_claim`,
  `_discard` and `release` take `fcntl.flock(LOCK_EX)` on it for their whole
  check-and-rename. `release` verifies ownership (the pid in the slot) before
  removing it.
- **Behavior**: the residual-race comment at `:102-106` is replaced by one
  line naming the lock.

#### Feature: Guard review-once in a lane (00239)
- **Description**: review-once never commits the store on a lane branch.
- **Inputs**: `loop.py:506`.
- **Outputs**: `_record_review_once_store` returns early when
  `store_tree.in_wave_lane(self.env)` is true, matching `loop.py:611`.

## Structural Decomposition

### Repository Structure

```
skills/run-autopilot/cli/
├── wave_assemble.py           # Maps to: Persist before tearing down
├── wave_cli.py                # Maps to: OSError handling for assemble
├── wave_review.py             # Maps to: assembly worktree gate; land after hand review
├── wave_slots.py              # Maps to: Lock the slot reclaim
├── loop.py                    # Maps to: Guard review-once in a lane
├── test_wave_docs.py          # Maps to: Gate the summary tests
└── test_wave_*.py, test_loop*.py   # new tests named below
skills/run-autopilot/references/waves.md   # hand-review land route
dev/bin/release-checks
CHANGELOG.md
```

### Module: wave_slots
- **Maps to capability**: Lock the slot reclaim
- **Responsibility**: at most `count` concurrent holders, under any
  interleaving.
- **Exports**: unchanged (`acquire`, `release`).

## Dependency Graph

### Foundation Layer (Phase 0)
No dependencies - built first.

- **release gate and loop guard** (00221, 00239): independent one-site
  changes.

### Core Layer (Phase 1)
- **slot lock, teardown ordering, assembly gate, hand-review land**: each
  depends only on Phase 0's gate, so its tests run in release-checks.

### Integration Layer (Phase 2)
- **waves.md and CHANGELOG**: Depends on [Phase 1].

## Implementation Phases

### Phase 0: Foundation
**Goal**: the gate sees every wave test; review-once is guarded.

**Tasks**:
- [ ] Add `test_wave_assemble_summary.py` to release-checks and
  `_WAVE_TEST_FILES`, plus `test_every_wave_test_file_is_listed` (no deps) -
  Acceptance: that test green, and red before the two additions (fail-first
  recorded); `bash dev/bin/release-checks` runs the 12 summary tests.
- [ ] Add the `in_wave_lane` guard to `_record_review_once_store` (no deps) -
  Acceptance: `test_loop_record_store.py::test_review_once_skips_the_store_in_a_wave_lane`
  green and red before the guard.

**Exit Criteria**: both tests green.

### Phase 1: Core
**Goal**: crash, race and hand-review paths are safe.

**Tasks**:
- [ ] Lock the slot reclaim (depends on: Phase 0) - Acceptance:
  `test_wave_slots.py::test_reclaim_put_back_race_admits_one_holder` (three
  processes, `count=1`, a forced interleave at the rename) and
  `::test_release_never_removes_another_holders_slot` green.
- [ ] Persist before teardown and catch `OSError` (depends on: Phase 0) -
  Acceptance: `test_wave_assemble_migrate.py::test_crash_after_save_before_remove_reruns_clean`
  (save, then simulate a crash before `worktree remove`, rerun: the lane
  stays assembled, exit 0, the report keeps non-roster PRDs) and
  `test_wave_cli_refusals.py::test_assemble_os_error_is_one_line_exit_one`
  green.
- [ ] Switch the assembly worktree gate to `foreign_dirty` and hold the
  seeded backlog (depends on: Phase 0) - Acceptance:
  `test_wave_review.py::test_store_churn_in_the_assembly_worktree_does_not_refuse`
  and `::test_seeded_backlog_prds_are_held_before_the_nested_loop` green.
- [ ] Land after a hand review (depends on: Phase 0) - Acceptance:
  `test_wave_review_land.py::test_hand_reviewed_stub_in_done_lands` and
  `::test_review_failed_without_hand_review_still_exits_four` green.

**Exit Criteria**: every Phase 1 test green.

### Phase 2: Integration
**Goal**: documented.

**Tasks**:
- [ ] Add the hand-review route to `references/waves.md` and a `CHANGELOG.md`
  `[Unreleased]` `### Fixed` `**run-autopilot**` line naming the six fixes
  (depends on: Phase 1) - Acceptance: `bash dev/bin/release-checks` green.

**Exit Criteria**: `release-checks` green.

## Test Strategy

### Critical Scenarios
- **Happy path**: a two-lane wave assembles, reviews and lands with the
  store tracked, and nothing refuses on store churn.
- **Edge case**: three acquirers racing one slot → exactly one holder; a
  crash between save and worktree removal → a clean rerun.
- **Error case**: assemble hits a removed worktree → one `autopilot:` line
  and exit 1, no traceback.

## Risks

- **flock is advisory and local**: every slot path goes through
  `wave_slots`, and lanes share one host by design (`references/waves.md`).
- **Holding seeded backlog PRDs surprises an operator**: the commit message
  and the wave report name every PRD moved to `hold/` on the assembly branch.
