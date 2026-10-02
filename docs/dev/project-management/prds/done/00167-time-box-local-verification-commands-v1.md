---
design: skip
---

# Time-box local verification commands

## Overview

### Problem Statement

The Subagent Watchdog covers dispatches, never plain Bash.
`skills/work/references/subagent-dispatch.md:60-88` scopes it to Agent
dispatches (15-minute check-in, 45-minute cap) and helper scripts
(`TaskOutput` 10 minutes twice). Line 88 grants exactly one Bash exception — a
20-minute `Monitor` on backgrounded `cargo` full-suite runs — and nothing else. A
foreground `ruff`, `pytest`, `git` or inspection call has no deadline, no
no-output probe and no kill path.

Measured (batch feedback 2026-08-27): a command that combined an inspection read
with a Ruff invocation stalled for 17 minutes 48 seconds, wrote nothing, and
needed manual interruption — in a loop whose whole premise is that nobody is
watching.

There is also no rule against building such a command. The "do not chain with
`&&`" instruction exists in two places
(`skills/work/references/final-verification.md:19`, `skills/work/SKILL.md:366`)
but is scoped to the step-7 suite and the commit pair, so a combined
inspect-and-verify command is unremarkable everywhere else.

The harness already provides the mechanism: the Bash tool takes a `timeout`
parameter in milliseconds, default 120000, maximum 600000. Nothing in this pack
ever passes it.

### Target Users

The unattended autopilot loop. A hung foreground command there costs wall-clock
until a human notices, which is exactly what the loop exists to avoid.

### Success Metrics

- Every verification and lint command this pack documents carries an explicit
  `timeout`; a hang costs at most that budget instead of unbounded wall-clock.
- A timed-out verification is recorded, not silently retried or reported green.
- Zero behavior change on a command that completes inside its budget.
- The full-suite path keeps its existing 20-minute `Monitor` treatment — this
  PRD does not shrink any deadline that already exists.

## Functional Decomposition

### Capability: Bounded local commands

Every command the loop waits on has a deadline it can survive.

#### Feature: Explicit timeout budgets
- **Description**: Documented per-class Bash `timeout` values for the commands
  this pack runs in the foreground.
- **Inputs**: the command class.
- **Outputs**: a `timeout` argument on the Bash call.
- **Behavior**: Three budgets, stated once and referenced at every call site.
  **Inspection** (`git diff`, `git status`, `rg`, `ls`, a render call): 60000 ms.
  **Lint and narrow tests** (`ruff check`, `eslint`, the step-5.5 narrow test
  command, a queued verification check): 300000 ms. **Full suite** (step 7's
  documented or improvised suite): the existing backgrounded-plus-`Monitor`
  treatment at 20 minutes, unchanged — a foreground full suite is capped at the
  tool maximum, 600000 ms. A command with no documented class takes the
  inspection budget.

#### Feature: Timeout is recorded, not retried blind
- **Description**: A budget that fires is evidence, on the attempt and in the
  phase report.
- **Inputs**: the timed-out command and its class.
- **Outputs**: `verification: "timeout:<command>"` on the attempt record for a
  step-5.5 or step-7 command; a phase-report line naming the command and its
  budget for every class.
- **Behavior**: Reuses the existing `verification` field and its
  best-effort-gate-stamp semantics, which already carry `"skipped:<cause>"` for a
  verification that could not run. One re-run is allowed at the next larger
  budget when a larger one exists for that class; a second timeout records the
  stamp and proceeds (fail loud, never blocking) rather than looping.
- **Implementation note (added 2026-08-30, during review):** the attempt stamp
  shipped for step-5.5 commands only. Step 7 runs after every task has exited,
  and `task-done` / `append-attempt` are the only attempt writers — both at task
  exit — so there is no entry for a step-7 timeout to stamp and no verb to amend
  one. A step-7 timeout is recorded in the phase report instead, beside the
  `verification: none (no suite found)` line that step already uses. A step-2.95
  red-check timeout likewise keeps its own field, `red_check: "skipped:<cause>"`,
  rather than colliding with `verification` on the same attempt.

### Capability: Command separation rule

A verification command that also inspects has two ways to hang and one exit
code.

#### Feature: Never combine inspection with verification
- **Description**: One rule, stated where the pack's Bash rules already live.
- **Inputs**: none.
- **Outputs**: a rule paragraph in `subagent-dispatch.md`, referenced from the
  step-5.5 and step-7 procedures and repeated in the dispatch prologue.
- **Behavior**: A single Bash call runs either an inspection (read, list,
  search, diff) or a verification (test, lint, build) — never both, and never
  two verifications chained. Rationale stated in the rule: a combined command's
  exit code and output cannot be attributed to either half, and the pack's
  existing no-`&&` instructions were scoped too narrowly to prevent it. The
  dispatch prologue gains one sentence so implementors inherit it too.

## Structural Decomposition

### Repository Structure

```
skills/work/
├── SKILL.md                                  # Dispatch prologue sentence; step 5.5 and step 7 pointers
└── references/
    ├── subagent-dispatch.md                  # Maps to: both capabilities (the rules live here)
    ├── final-verification.md                 # Step 7 budgets
    ├── gate-failure.md                       # Step 5.5 narrow-test budget
    └── attempt-logging.md                    # The timeout: value
skills/work/scripts/
└── test_dispatch_prose.py                    # Prose pins
```

### Module: dispatch-rules
- **Maps to capability**: Bounded local commands, Command separation rule
- **Responsibility**: own the three budgets and the separation rule in the file
  that already owns the deadline table, so there is one place to change them.
- **Exports**: none (prose)

### Module: call-site-prose
- **Maps to capability**: Bounded local commands
- **Responsibility**: reference the budgets from the step-5.5 and step-7
  procedures and the dispatch prologue; record the timeout stamp.
- **Exports**: none (prose)

## Dependency Graph

### Foundation Layer (Phase 0)
No dependencies - built first.

- **dispatch-rules**: the budgets and the rule every call site cites.

### Core Layer (Phase 1)
- **call-site-prose**: Depends on [dispatch-rules] - it names the budget classes
  that file defines.

### Integration Layer (Phase 2)
No integration module - this PRD is prose plus prose pins.

## Implementation Phases

### Phase 0: Foundation
**Goal**: The budgets and the separation rule exist in one place.

**Tasks**:
- [ ] Add a `## Foreground command budgets` section to
      `skills/work/references/subagent-dispatch.md` giving the three classes,
      their millisecond values, the one-larger-budget re-run allowance and the
      unchanged full-suite `Monitor` path; add a `## Never combine inspection
      with verification` section giving the rule and its rationale. Extend the
      existing deadline summary list (the "15 min / 10 min × 2 / 20 min" block)
      with the new rows so the file still has one complete deadline table (no
      deps) - Acceptance:
      `rg -n "^## (Foreground command budgets|Never combine inspection with verification)$" skills/work/references/subagent-dispatch.md`
      hits both; `rg -n "300000|60000" skills/work/references/subagent-dispatch.md`
      hits.

**Exit Criteria**: A reader of `subagent-dispatch.md` can see every deadline this pack enforces in one table.

### Phase 1: Core
**Goal**: The call sites carry the budgets and the stamp.

**Tasks**:
- [ ] Edit `skills/work/references/final-verification.md`: state the timeout
      class for each command in `## What to run`, extend the existing "Run each
      as a separate Bash call. Do not chain with `&&`." line with a pointer to
      the separation rule, and add a `## Timed-out commands` section giving the
      one-larger-budget re-run and the `verification: "timeout:<command>"` stamp
      (depends on: Phase 0) - Acceptance:
      `rg -n "timeout" skills/work/references/final-verification.md` hits;
      `rg -n "Never combine" skills/work/references/final-verification.md` hits.
- [ ] Edit `skills/work/references/gate-failure.md` § Narrow scope to name the
      lint-and-narrow-tests budget for the per-language commands, and add one
      sentence to the Dispatch prologue in `skills/work/SKILL.md` telling
      implementors never to combine an inspection with a test or lint invocation
      in one Bash call (depends on: Phase 1 task 1) - Acceptance:
      `rg -n "300000" skills/work/references/gate-failure.md` hits;
      `rg -n "never combine" -i skills/work/SKILL.md` hits;
      `uv run --no-project --with pytest python -m pytest -q skills/work/scripts/test_dispatch_prose.py`
      green, its SKILL.md line-ceiling test included.

**Exit Criteria**: Every documented verification command names its budget.

### Phase 2: Integration
**Goal**: The stamp is documented and the rules are pinned.

**Tasks**:
- [ ] Add `"timeout:<command>"` to the `verification` field semantics in
      `skills/work/references/attempt-logging.md` and to the `tasks[].attempts`
      signature in `skills/run-autopilot/references/state-schema.md`; add prose
      pins to `test_dispatch_prose.py` (`subagent-dispatch.md` names both new
      section headings and `300000`; `final-verification.md` names `Never
      combine`; SKILL.md's dispatch prologue names the separation rule); add the
      CHANGELOG entry (`feat` commit: `**work**` under Added, "explicit timeout
      budgets for foreground verification commands and a rule against combining
      inspection with verification") (depends on: Phase 1) - Acceptance:
      `rg -n "timeout:" skills/work/references/attempt-logging.md` hits;
      `uv run --no-project --with pytest python -m pytest -q skills/work/scripts/test_dispatch_prose.py`
      green; `rg -n "timeout budgets" CHANGELOG.md` hits under `[Unreleased]`.

**Exit Criteria**: The prose suite fails if any of the three rules is deleted.

## Test Strategy

### Critical Scenarios
- **Happy path**: `ruff check` finishes in 8 seconds under a 300000 ms budget →
  no stamp, no report line, behavior identical to today.
- **Edge case**: the step-7 full suite is backgrounded by the session → the
  existing 20-minute `Monitor` path applies, unchanged.
- **Error case**: a lint command hangs → the tool returns at 300000 ms, one
  re-run at 600000 ms, a second hang records
  `verification: "timeout:ruff check"` and the phase proceeds with the failure
  named in the report.
- **Error case**: an implementor is about to run `sed -n '1,80p' x.py && ruff check x.py`
  → the prologue rule forbids it; the two halves run as two calls with their own
  budgets.

## Risks

- **A budget too tight kills honest work.** The values are set above measured
  runtimes for their class (lint and narrow tests are seconds, not minutes), the
  full-suite path is untouched, and the first timeout buys a re-run at a larger
  budget rather than an abort.
- **The rules are prose and prose drifts.** Every rule added here gets a pin in
  `test_dispatch_prose.py`, which is the pack's existing mechanism for exactly
  this.
- **The timeout parameter is a harness feature, not a repo one.** If a future
  harness drops or renames it, the budgets become advisory and the failure mode
  is today's behavior — unbounded but reported. No state or script depends on the
  parameter existing.
