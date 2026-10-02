---
catchup: skip
design: skip
ledger: deferred/202609252154-deferred.json
ledger_key: b4dc57e2fb78
source_prd: 00218-leave-sessions-at-task-boundaries-and-run-one-devon-round-v1.md
severity: high
---

# Triage: `trusted_last_wall` stops at the first completed task whose stamps are missin...

## Problem

Deferred finding with no PRD owner when this stub was minted: batch `202609252154`, ledger `deferred/202609252154-deferred.json`, type `cap-overflow`, cycle `2`, consensus `4/4`, raised against `00218-leave-sessions-at-task-boundaries-and-run-one-devon-round-v1.md`.

Issue: `trusted_last_wall` stops at the first completed task whose stamps are missing, non-int or negative and returns None, instead of scanning back. Its tests pin that shape (`test_stamps_that_are_not_both_ints_give_no_span`, `test_a_negative_span_gives_nothing`). The PRD wording, the design doc ("finds the last completed entry whose stamps are both ints") and task 11's widening of `last_task_wall` all say scan back. Since the hook never calls `last_task_wall`, task 11's fix has no runtime effect. Any completed task that was never seen in progress now drops the time term for the next fire. This is conservative, and the rotated-task and over-ceiling stops are deliberate, but the unstamped case is undocumented as a deviation. Either skip unstamped or negative entries and stop only on rotated or over-ceiling ones, or record the deviation. The design's `test_trusted_last_wall_agrees_with_last_task_wall` pin is also missing (`rg` finds no such test), so the two walks can silently disagree. ALSO FOLDED INTO THIS ROW BY THE CONSOLIDATOR (three distinct defects, see the review file's consolidation caveat): (a) no `isinstance(task, dict)` guard at _cap_headroom.py:77, so a non-dict entry in state.tasks raises AttributeError inside a PostToolUse hook with no except around it; (b) booleans satisfy `isinstance(..., int)` at _cap_headroom.py:81, so started_at/done_at of True yields a bogus span where `int_field` would reject it; (c) Blake's separate HIGH that the hook substitutes `trusted_last_wall` for the PRD's `last_task_wall(state)`, and its rotation and 10800s stops invert the PRD's own edge case ("a rotated task's wall spans both sessions and the next session hands off earlier, never later").

## Solution

Attended triage. A human promotes this finding into a backlog PRD through normal PRD authoring and review, or closes it. Autopilot never drains `dev/local/prds/hold/`, and this stub is never auto-promoted.

## Requirements

### Must have
- A triage decision for ledger key `b4dc57e2fb78`: a backlog PRD, or closed.

### Nice to have
- None until triage.

## Implementation

### Module: triage
- **Location**: `dev/local/prds/hold/`
- **Responsibility**: hold ledger key `b4dc57e2fb78` from `00218-leave-sessions-at-task-boundaries-and-run-one-devon-round-v1.md` until a human triages it
- **Exports**: none

### Dependencies
- triage: No dependencies (foundation)

## Tasks

### Phase 0: Foundation
- [ ] triage: promote to backlog or close - Acceptance: this file is no longer under dev/local/prds/hold/

### Phase 1: Core
No implementation tasks until attended triage.

## Success Criteria

- This file is no longer under `dev/local/prds/hold/`.
