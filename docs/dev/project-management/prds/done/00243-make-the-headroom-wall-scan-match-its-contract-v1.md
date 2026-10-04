---
catchup: skip
design: skip
default_model: sonnet
model_tier_rationale: the scan rule, both guards and the file split are specified exactly below; every branch has a named test, and the hook's PostToolUse crash path is pinned
---

# Make the headroom wall scan match its contract

Source: attended triage on 2026-10-03, checked against HEAD. Ledger trail
(batch `202609252154`): 00229 `b4dc57e2fb78`, 00230 `d2d2ea9958bb`.

## Overview

### Problem Statement

PRD 00218 gave the context-cap hook a time term. The hook gets the last
task's wall time from `_cap_headroom.trusted_last_wall(state)`, not from the
`last_task_wall(state)` the PRD names. `trusted_last_wall` has four defects
(00229):

- **It stops early.** It stops at the first completed task whose stamps are
  missing, not ints, or negative, and returns None, instead of scanning back
  as the PRD and design doc say. One unstamped task drops the time term for
  the next fire.
- **No dict guard.** A non-dict entry in `state.tasks` raises
  `AttributeError` inside a PostToolUse hook, and nothing catches it there.
- **Booleans pass as ints.** `True` satisfies `isinstance(..., int)`, so
  `started_at: true` yields a bogus span.
- **The agreement pin is missing.** The design doc's
  `test_trusted_last_wall_agrees_with_last_task_wall` was never written, so
  the two walks can drift apart silently.

The rotated-task and over-ceiling stops are deliberate (a rotated wall spans
two sessions) and stay.

Separately (00230), the rework grew
`scripts/test_autopilot_cap_headroom.py` to 923 lines, over the 800-line
limit that `check_style_limits.py` enforces.

### Target Users

Every loop session; the hook runs on each tool call.

### Success Metrics

- `uv run --no-project --with pytest python -m pytest -q skills/run-autopilot/scripts -k "headroom or cap_task_record or trusted_last_wall"`
  green.
- `wc -l skills/run-autopilot/scripts/test_autopilot_cap_headroom.py` under
  800; `bash dev/bin/release-checks` green.

## Functional Decomposition

### Capability: The wall scan is total and correct

#### Feature: Scan back past bad stamps
- **Description**: `trusted_last_wall` skips unusable entries instead of
  giving up.
- **Inputs**: `state["tasks"]`.
- **Outputs**: the wall seconds of the most recent completed task with
  usable stamps, or None.
- **Behavior**: walk completed tasks newest first:
  - **Skip:** any entry that is not a dict, and any task whose `started_at`
    or `done_at` is missing, not an `int`, a `bool` (rejected explicitly), or
    whose span is negative.
  - **Stop and return None:** on a rotated task, or a span over the
    10800-second ceiling, as today.
  - **Return:** the first remaining span.

  The function never raises. `last_task_wall` gets the same skip rules for
  the dict and bool cases.

#### Feature: Pin agreement
- **Description**: the two walks agree whenever no rotation or ceiling
  applies.
- **Outputs**: `test_trusted_last_wall_agrees_with_last_task_wall`,
  parametrized over a state with only clean stamps, one with an unstamped
  middle task, and one with a negative span.

### Capability: The test file is under the limit

#### Feature: Split the wall tests out
- **Description**: the wall-time tests move to their own file.
- **Outputs**: `scripts/test_cap_task_record_wall.py`, holding the
  `TaskBoundsWallTests` class and the new tests, listed in
  `dev/bin/release-checks` beside `test_autopilot_cap_headroom.py`.
- **Behavior**: `test_autopilot_cap_headroom.py` loses exactly the moved
  class; a test count check (`pytest --collect-only -q`) before and after
  gives the same total across the two files.

## Structural Decomposition

### Repository Structure

```
skills/run-autopilot/scripts/
├── _cap_headroom.py                  # Maps to: Scan back past bad stamps
├── _cap_task_record.py               # last_task_wall dict/bool guards
├── test_autopilot_cap_headroom.py    # loses TaskBoundsWallTests
└── test_cap_task_record_wall.py      # Maps to: Split the wall tests out; Pin agreement
dev/bin/release-checks
CHANGELOG.md
```

### Module: _cap_headroom
- **Maps to capability**: The wall scan is total and correct
- **Responsibility**: headroom arithmetic for the hook.
- **Exports**: `trusted_last_wall` (signature unchanged).

## Dependency Graph

### Foundation Layer (Phase 0)
No dependencies - built first.

- **the split**: a pure move.

### Core Layer (Phase 1)
- **scan rules and guards**: Depends on [the split] (their tests go in the
  new file).

### Integration Layer (Phase 2)
- **CHANGELOG**: Depends on [scan rules].

## Implementation Phases

### Phase 0: Foundation
**Goal**: the file is under the limit with no test lost.

**Tasks**:
- [ ] Move `TaskBoundsWallTests` to `test_cap_task_record_wall.py` and list
  it in release-checks (no deps) - Acceptance: `wc -l` of the old file under
  800; collected test count across the two files equals the count before the
  move; `bash dev/bin/release-checks` green.

**Exit Criteria**: release-checks green.

### Phase 1: Core
**Goal**: the scan matches its contract.

**Tasks**:
- [ ] Rewrite the walk in `trusted_last_wall` and add the guards to
  `last_task_wall` (depends on: Phase 0) - Acceptance:
  `test_cap_task_record_wall.py::test_an_unstamped_task_is_skipped_not_fatal`,
  `::test_a_negative_span_is_skipped`,
  `::test_a_non_dict_entry_never_raises`,
  `::test_boolean_stamps_are_rejected`,
  `::test_rotation_still_stops_the_scan`,
  `::test_the_ceiling_still_stops_the_scan`,
  `::test_trusted_last_wall_agrees_with_last_task_wall` green; the two
  existing tests that pinned the old early-return
  (`test_stamps_that_are_not_both_ints_give_no_span`,
  `test_a_negative_span_gives_nothing`) are rewritten to the scan-back
  expectation, and the attempt entry says so (premise: `rg -c` finds each
  name once before the edit).

**Exit Criteria**: all named tests green.

### Phase 2: Integration
**Goal**: shipped.

**Tasks**:
- [ ] `CHANGELOG.md` `[Unreleased]` `### Fixed` `**run-autopilot**` line: the
  headroom time term scans back past unstamped or malformed tasks and never
  raises on a malformed task list (depends on: Phase 1) - Acceptance: `bash
  dev/bin/release-checks` green.

**Exit Criteria**: `release-checks` green.

## Test Strategy

### Critical Scenarios
- **Happy path**: three completed tasks, the newest unstamped → the second
  task's wall is returned.
- **Edge case**: the newest usable task is rotated → None, as today.
- **Error case**: `state["tasks"]` holds a string → None, no exception from
  the hook.

## Risks

- **Rewritten tests weaken coverage**: the two rewritten tests keep their
  inputs and change only the expected value, and the attempt entry records
  both diffs.
