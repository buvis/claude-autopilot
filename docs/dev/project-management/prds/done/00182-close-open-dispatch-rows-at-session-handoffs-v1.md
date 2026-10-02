---
catchup: skip
design: skip
default_model: sonnet
model_tier_rationale: exact row shapes and rules given; the writer is one 186-line script with an existing test module
---

# Close open dispatch rows at session handoffs

## Overview

### Problem Statement
`skills/work/scripts/record_dispatch.py` (PRD 00168) opens a row per dispatch and closes it with `elapsed_s = ended_at - queued_at`. A row opened in one session stays open when that session ends, and whichever later session closes it records the whole gap. Measured in the week to 2026-09-05: ivan row `66850dfe` (PRD 00171 task 1) was opened at 07:13Z on Sep 4 by a session that ended, and closed `ok` at 17:28Z by a later one, elapsed 36,909 s; ddb row `706126cc` was opened 12:37Z Sep 5, a second ivan row for the same task was opened and closed 4.4 h later, and only then was the first closed `ok`, elapsed 17,651 s. Across the four ledgers, 22 of 46 ivan rows and 22 of 45 pat rows never received an end row at all. The subagent-dispatch reference caps a dispatch at 45 minutes, so no honest row can exceed 2,700 s. Nothing reads the ledger yet (the script's docstring says so; tracon does not), which is why the drift went unnoticed, and the routing tuner from PRD 00170 is its intended reader.

### Target Users
Whoever tunes routing or audits dispatch cost from `dev/local/autopilot/ledger/dispatch-metrics.jsonl`; the batch report, once it renders dispatch timing.

### Success Metrics
- `uv run --no-project --with pytest python -m pytest -q skills/work/scripts/test_record_dispatch.py` passes with the four new tests named below.
- After the change, a `handoff` row is never preceded in the same file by an open start row: `test_handoff_closes_open_rows_as_lost` proves it on a fixture ledger.

## Functional Decomposition

### Capability: Ledger rows bounded by the session that opened them
A dispatch row's elapsed time never spans a session handoff; a row left open at a handoff is closed as lost there.

#### Feature: Open-row scan
- **Description**: `open_ids(autopilot_dir) -> list[str]` in `record_dispatch.py`.
- **Inputs**: the working file `dev/local/autopilot/dispatch-metrics.jsonl`.
- **Outputs**: ids that have a start row (`queued_at` present) and no end row (`ended_at` present), in first-seen order. Unparseable lines are skipped and counted on stderr exactly as `_queued_at` does today.
- **Behavior**: a missing file yields an empty list.

#### Feature: Handoff closes open rows
- **Description**: the `handoff` verb, on both edges, closes every open row before appending its own row.
- **Inputs**: `--site`, `--edge`, `--phase`, `--prd` (unchanged).
- **Outputs**: one end row per open id, `{"id": ID, "ended_at": NOW, "elapsed_s": null, "outcome": "lost", "detail": "open at <site>/<edge> handoff"}`, then the existing handoff row. Both go to the working file and the `ledger/` mirror through `append_row`.
- **Behavior**: `elapsed_s` is null because the true end is unknown; `null` is already the documented value for a row whose start could not be found. The `resume` edge closes rows too, so a crash between `leave` and `resume` still leaves no row open.

#### Feature: End after a boundary
- **Description**: the `end` verb refuses to report idle time as elapsed.
- **Inputs**: the id, `--outcome`, `--detail` (unchanged).
- **Outputs**: when any `handoff` row's `at` lies between the start row's `queued_at` and now, the end row carries `elapsed_s: null` and `detail` prefixed with `spans handoff; ` (the prefix alone when no detail was given). Otherwise unchanged.
- **Behavior**: the docstring's re-dispatch rule stands: an id can carry more than one end row and the last one is terminal; this feature only decides what `elapsed_s` may claim.

## Structural Decomposition

### Repository Structure

```
skills/work/scripts/
├── record_dispatch.py        # Maps to: Ledger rows bounded by the session (open_ids, handoff close, boundary rule)
└── test_record_dispatch.py   # Maps to: the four new tests
skills/work/references/
└── subagent-dispatch.md      # Maps to: § Dispatch telemetry row catalogue (lost-at-handoff row, null rule)
CHANGELOG.md
```

### Module: record_dispatch
- **Maps to capability**: Ledger rows bounded by the session that opened them
- **Responsibility**: the only writer of the dispatch ledger; owns every rule about what a row may claim
- **Exports**:
  - `open_ids(autopilot_dir)` - ids with a start row and no end row
  - `main(argv)` - the three verbs, `handoff` now closing open rows first, `end` now applying the boundary rule
  - `start_row(...)`, `append_row(...)` - unchanged

## Dependency Graph

### Foundation Layer (Phase 0)
No dependencies - built first.

- **record_dispatch.open_ids**: the scan both rules need.

### Core Layer (Phase 1)
- **record_dispatch handoff and end verbs**: Depends on [open_ids].

### Integration Layer (Phase 2)
- **docs**: Depends on [record_dispatch] (row catalogue, CHANGELOG).

## Implementation Phases

### Phase 0: Foundation
**Goal**: the scan exists and is tested on its own.

**Tasks**:
- [ ] Add `open_ids(autopilot_dir)` to `record_dispatch.py` (no deps) - Acceptance: `test_open_ids_lists_only_unclosed_starts` (fixture with two closed ids, one open id and one handoff row returns exactly the open id) passes in `test_record_dispatch.py`.

**Exit Criteria**: `python -m pytest -q skills/work/scripts/test_record_dispatch.py -k open_ids` passes.

### Phase 1: Core
**Goal**: no row survives a handoff open, and no end row claims idle time.

**Tasks**:
- [ ] Make the `handoff` verb close every open id as `lost` with the detail `open at <site>/<edge> handoff` before appending its own row (depends on: Phase 0) - Acceptance: `test_handoff_closes_open_rows_as_lost` (fixture with one open ivan row; after `handoff --site build --edge leave --phase review --prd X` the working file and the mirror both end with the lost row then the handoff row, `elapsed_s` null) and `test_handoff_leaves_closed_rows_alone` (fixture with only closed rows; exactly one row appended) pass.
- [ ] Apply the boundary rule in the `end` verb (depends on: Phase 0) - Acceptance: `test_end_after_handoff_reports_null_elapsed` (start row, then a handoff row, then `end ID --outcome ok`; the end row has `elapsed_s` null and `detail` equal to `spans handoff; ` plus nothing) and `test_end_without_handoff_keeps_elapsed` (start row then `end`; `elapsed_s` is an int) pass.

**Exit Criteria**: `python -m pytest -q skills/work/scripts/test_record_dispatch.py` passes.

### Phase 2: Integration
**Goal**: the row catalogue tells readers what `lost` and null now mean.

**Tasks**:
- [ ] Add the lost-at-handoff row and the null-elapsed rule to `skills/work/references/subagent-dispatch.md` § Dispatch telemetry, and a `### Fixed` CHANGELOG entry under `[Unreleased]` (depends on: Phase 1) - Acceptance: `rg -n 'open at .* handoff' skills/work/references/subagent-dispatch.md` returns one hit and `rg -n 'spans handoff' CHANGELOG.md` returns one hit.

**Exit Criteria**: `bash dev/bin/release-checks` passes.

## Test Strategy

### Critical Scenarios
- **Happy path**: dispatch opened and closed inside one session → unchanged row shapes, integer `elapsed_s`.
- **Edge case**: session ends with an ivan row open → the next `leave` or `resume` handoff closes it as `lost`; a later `end` for that id writes a second end row with null elapsed.
- **Error case**: the working file is missing at `handoff` → no lost rows, the handoff row is written as today, exit 0.

## Risks
- **Historical rows stay wrong**: the fix is forward-only; readers of the week's ledgers must drop rows with `elapsed_s` above 2,700 s themselves. No migration.
- **Both edges close rows**: a `resume` immediately after a `leave` finds nothing open, so the double pass costs one file read and no rows.

## Post-completion notes (2026-09-07)

Converged (batch 202609061630); two deferred rows walked 2026-09-07 in the config-audit closure walkthrough
(`~/.claude/dev/local/audit-results/2026-09-05.md`).

- A `.handoff-requested` marker written during the build phase survived the build-to-review handoff and was
  still present when the review gate dispatched its rework pass; at a task boundary step 6.5 would have set
  `next_phase` to build while the phase was review, hijacking the review cycle: PRD 00191 consumes the marker
  at the phase edge and makes step 6.5 ignore a marker whose phase does not match.
- `dev/bin/release-checks` never runs `skills/work/scripts/test_record_dispatch.py`, so this PRD's Phase 2
  exit criterion was a vacuous gate (pre-existing): the block is added in PRD 00190.
