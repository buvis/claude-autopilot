---
catchup: skip
design: skip
default_model: sonnet
model_tier_rationale: sonnet floor by operator decision 2026-09-26 (the opus floor cost 109 min per task on 00214, 95 of them in test rounds); the planner still lifts the blocking acquire at the loop's spawn site to opus per task if its algorithmic-risk row hits
rework_cap: 2
---

# Bound concurrent review sessions with a slot semaphore

Source: `dev/local/discovery/00212-route-prds-in-waves.md` must-have 7
(2026-09-21). Grounded at `8885300` (0.5.5). Split out of 00214, which passes
the two variables below to every lane loop; independent of 00215 and 00216. A
loop without the variables is untouched.

## Overview

### Problem Statement

A wave runs N loops at once and each loop's review phase costs the most (74% of
the 0.5.4 batch's spend was review sessions). Five reviews in flight exhaust the
five-hour window; the 2026-09-20 hand wave held reviews to three at a time with
a directory semaphore (`review-slot.sh`: `mkdir` a slot, `owner` file, poll).
The loop has no such brake, and the window yield (PRD 00199) throttles only
after the warning fires.

### Target Users

Lane loops launched by `autopilot wave launch`; any operator who exports the
variables by hand for two loops in two repos.

### Success Metrics

- `uv run --no-project --with pytest python -m pytest -q skills/run-autopilot/cli/test_wave_slots.py skills/run-autopilot/cli/test_loop_slots.py`
  green.
- `bash dev/bin/release-checks` green (both files join the `[checks] waves`
  block, created by 00214; when 00214 is not yet merged, create the block).
- Post-release signal: across a wave's lanes, no more than
  `_AUTOPILOT_REVIEW_SLOTS` `loop-metrics.jsonl` rows with `phase_launched:
  "review"` overlap in time.

## Functional Decomposition

### Capability: Review-slot semaphore
Never more than N review sessions at once across the loops that share a dir.

#### Feature: The mkdir semaphore
- **Description**: `cli/wave_slots.py` acquires and releases numbered slot
  directories.
- **Inputs**: a slots dir, a count, the owner pid, injected `sleep_fn` and
  `clock`.
- **Outputs**: `<dir>/<n>/owner` holding the pid while held.
- **Behavior**: `acquire(dir, count, owner_pid, *, sleep_fn, clock,
  poll_secs=30) -> Path` creates `dir` first (`mkdir -p`; nothing else
  creates `wave-slots/`), then tries `mkdir <dir>/<n>` for n in 1..count and
  writes `owner`; a slot whose `owner` pid is dead (`loop_gates._pid_alive`) or whose
  `owner` file is missing or malformed is reclaimed (rmdir, retry); otherwise
  it sleeps `poll_secs` and retries, printing one stderr line per five minutes
  of waiting that names the dir. `release(slot)` removes the dir; releasing a
  slot that is already gone is a no-op.

#### Feature: The loop takes a slot around a review session
- **Description**: `Loop._launch` (the one `self._spawn` call site) acquires
  before a `review` spawn and releases after the session exits.
- **Inputs**: `_AUTOPILOT_REVIEW_SLOTS_DIR`, `_AUTOPILOT_REVIEW_SLOTS`
  (default 3), the phase being launched.
- **Outputs**: the slot held for exactly the session's lifetime.
- **Behavior**: `routing.Route` carries no phase, so `_announce_and_launch`
  passes its `phase` argument down to `_launch`; the `review-once` verb
  (`_run_once`) reaches `_launch` through the same call and so takes a slot
  too. In `_launch`, when that phase is `review` and the dir variable is set:
  acquire (count from the count variable, the loop's own `sleep_fn` and
  clock), spawn, release in a `finally`, so a spawn that raises or a capped
  session still frees the slot.
  Every other phase, and every loop without the variable, runs exactly as
  today. The `[checks] waves` block and the `references/waves.md` runbook
  (from 00214) gain one paragraph naming the two variables and the default.

## Structural Decomposition

### Repository Structure

```
skills/run-autopilot/cli/
├── wave_slots.py           # Maps to: The mkdir semaphore
├── loop.py                 # Maps to: The loop takes a slot around a review session
├── test_wave_slots.py      # Maps to: Test Strategy (semaphore)
└── test_loop_slots.py      # Maps to: Test Strategy (loop integration, ScriptedSpawn)
skills/run-autopilot/references/waves.md   # Maps to: the two variables (paragraph)
dev/bin/release-checks                      # Maps to: `[checks] waves` block
CHANGELOG.md
```

### Module: wave_slots
- **Maps to capability**: Review-slot semaphore
- **Responsibility**: the semaphore, nothing about loops.
- **Exports**: `acquire(...) -> Path`, `release(slot) -> None`.

## Dependency Graph

### Foundation Layer (Phase 0)
No dependencies - built first.

- **wave_slots**: uses `loop_gates._pid_alive` (existing).

### Core Layer (Phase 1)
- **loop.py integration**: Depends on [wave_slots].

### Integration Layer (Phase 2)
- **prose, registration, changelog**: Depends on [loop.py integration].

## Implementation Phases

### Phase 0: Foundation
**Goal**: the semaphore is exact and reclaims dead owners.

**Tasks**:
- [ ] Add `cli/wave_slots.py` with `test_wave_slots.py` (no deps) -
  Acceptance: `test_acquire_creates_the_slots_dir`,
  `test_acquire_takes_the_first_free_slot`,
  `test_acquire_blocks_until_release` (the injected `sleep_fn` releases the
  slot on its second call and the test asserts two sleeps),
  `test_dead_owner_slot_is_reclaimed`, `test_malformed_owner_is_reclaimed`,
  `test_release_frees_the_slot`, `test_release_of_a_missing_slot_is_a_noop`
  green.

**Exit Criteria**: `acquire` under 50 lines.

### Phase 1: Core
**Goal**: a review session cannot start without a slot when a dir is set.

**Tasks**:
- [ ] Wrap the review spawn in `Loop._launch`, with the phase passed down
  from `_announce_and_launch` (depends on: Phase 0) -
  Acceptance: `test_loop_slots.py` with `ScriptedSpawn` and `FakeClock`
  (`cli/loop_testutil.py`): `test_review_launch_waits_for_a_slot`,
  `test_build_launch_never_touches_slots`,
  `test_slot_is_released_after_the_session`,
  `test_slot_is_released_when_the_spawn_raises`,
  `test_no_slot_dir_means_no_semaphore` green; every existing `test_loop*.py`
  stays green.

**Exit Criteria**: both files green.

### Phase 2: Integration
**Goal**: documented and checked at release.

**Tasks**:
- [ ] Add the paragraph to `references/waves.md` (create the file with that
  paragraph if 00214 has not landed), list both test files in the `[checks]
  waves` block, and a CHANGELOG `### Added` entry under `**run-autopilot**`
  (depends on: Phase 1) - Acceptance:
  `test_wave_slots.py::test_docs_name_the_two_variables` pins
  `_AUTOPILOT_REVIEW_SLOTS_DIR` and `_AUTOPILOT_REVIEW_SLOTS` in
  `references/waves.md`; `release-checks` green.

**Exit Criteria**: suites green; `release-checks` green.

## Test Strategy

### Critical Scenarios
- **Happy path**: count 2, two loops (two pids) each take a slot; a third
  acquire sleeps until one releases → Expected: the third holds the freed
  number, the `owner` files name the right pids.
- **Edge case**: a slot left by a killed loop (dead pid) → reclaimed on the
  next acquire without waiting; a build session with the dir set → no slot
  touched.
- **Error case**: the spawn raises → the slot is released and the exception
  propagates as today.

## Risks

- **A stuck review holds a slot for its whole cap**: the session's wall-clock
  cap (`cap_secs`) bounds it, and a killed loop's slot is reclaimed by pid.
- **Two machines**: the dir is local; a wave never spans machines (00212 out
  of scope).
