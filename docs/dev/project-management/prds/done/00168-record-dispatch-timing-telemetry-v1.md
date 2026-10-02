# Record dispatch timing telemetry

## Overview

### Problem Statement

Nothing in the pack records when anything happened. The attempt schema
(`skills/work/references/attempt-logging.md:5-31`) carries 24 fields — model,
implementor, pipeline, preflight, escalation, six best-effort gate stamps — and
**not one timestamp**. No queued time, no start, no end, no prompt size, no tool
runtime, no timeout reason.

`skills/work/references/subagent-dispatch.md:64` does say "Record the dispatch
wall-clock time", in-session, with nowhere to write it.

What exists cannot answer the question. `loop-metrics.jsonl` holds one row per
session (`wall_secs`, `cost_usd`) and one `review_converged` row per PRD
(`skills/run-autopilot/references/phase-review.md:154-172`). Measured
consequence (batch feedback 2026-08-27): review and rework commits spanning about
15.3 hours, including a 6-hour and a 3.6-hour gap, with no artifact able to
separate model work from quota waits, session handoffs, tool hangs or idle time —
the session log was gone. Efficiency tuning on that basis is guesswork.

### Target Users

The operator tuning batch throughput and cost, and the `audit-qwen` /
`brief-portfolio` style reports that already read this pack's JSONL ledgers.

### Success Metrics

- Every subagent and helper-script dispatch in the work phase produces one row
  carrying queued time, end time, elapsed seconds, prompt bytes and outcome.
- The rows survive `dev/local` GC: mirrored into `dev/local/autopilot/ledger/`
  the same way `loop-metrics.jsonl` already is.
- A 6-hour gap between two commits can be attributed — dispatch runtime, handoff
  latency, or neither — from the ledger alone, without a session transcript.
- Cost: at most **one** extra Bash call per dispatch. The start row is written by
  a call the pack already makes.

## Functional Decomposition

### Capability: Dispatch rows

One row per dispatch, written where the pack already runs something.

#### Feature: Start row from the render call
- **Description**: `render_prompt.py` writes the dispatch's start row as a side
  effect of rendering its prompt.
- **Inputs**: two new optional flags, `--dispatch-kind KIND` and
  `--dispatch-task ID`; the rendered byte count it already computes and prints.
- **Outputs**: a line appended to `dev/local/autopilot/dispatch-metrics.jsonl`:
  `{"id": "<8 hex chars>", "kind": KIND, "task": ID, "queued_at": <epoch>, "prompt_bytes": <int>}`;
  the id echoed to stdout on its own line after the existing byte count.
- **Behavior**: Absent either flag, `render_prompt.py` behaves byte-identically
  to today — same stdout, no file touched. This is the free half: every Tess,
  Ivan, Devon and Pat dispatch already renders through this script, and the byte
  count it prints is already the Subagent Dispatch Budget measurement. The
  autopilot dir is resolved with the existing `_walk_up.py` pattern; an
  unresolvable dir writes nothing and exits 0 — telemetry never blocks a
  dispatch.

#### Feature: End row
- **Description**: One helper call after the dispatch returns closes the row.
- **Inputs**: `record_dispatch.py end <id> --outcome ok|timeout|killed|error|lost [--detail TEXT]`.
- **Outputs**: a second line appended to the same file:
  `{"id": ..., "ended_at": <epoch>, "elapsed_s": <int>, "outcome": ..., "detail": ...}`.
- **Behavior**: The script stamps `ended_at` itself and computes `elapsed_s`
  against the start row's `queued_at`, so the caller never handles a clock. An id
  with no start row records `elapsed_s: null` rather than failing. Two rows per
  dispatch rather than one mutated row keeps every write a pure append, which is
  what makes the file safe under the concurrent sessions this pack already runs.

#### Feature: Handoff rows
- **Description**: The gap between sessions is measured, not inferred.
- **Inputs**: the session-handoff sites — `/autopilot:work` step 6.5's
  task-boundary handoff, and `autopilot phase-done`.
- **Outputs**: `{"kind": "handoff", "site": "build"|"review"|"done", "at": <epoch>, "phase": ..., "prd": ...}`
  rows in the same file.
- **Behavior**: A row at the end of the session that hands off and a row at the
  start of the session that resumes; the difference is the handoff latency the
  feedback could not measure. Written best-effort, never blocking a phase
  transition.

### Capability: Ledger durability

Keep the rows past the GC horizon.

#### Feature: Mirrored append
- **Description**: Every row is written twice, exactly as `loop-metrics.jsonl`
  is.
- **Inputs**: the row.
- **Outputs**: `dev/local/autopilot/dispatch-metrics.jsonl` and
  `dev/local/autopilot/ledger/dispatch-metrics.jsonl`.
- **Behavior**: `record_dispatch.py` and `render_prompt.py`'s start-row path both
  `mkdir -p` the ledger directory before the second append — the same
  not-optional step `phase-review.md:170` documents for the metrics mirror,
  because `ledger/` is created lazily by whichever writer arrives first. The
  working copy is GC'd at 14 days by `purge-devlocal`; the ledger copy is
  GC-exempt.

## Structural Decomposition

### Repository Structure

```
skills/work/scripts/
├── record_dispatch.py                     # Maps to: End row, Handoff rows
├── test_record_dispatch.py                # Row-shape and elapsed tests
├── render_prompt.py                       # Maps to: Start row
└── test_render_prompt.py                  # Flag tests
skills/work/
├── SKILL.md                               # Call sites
└── references/
    ├── subagent-dispatch.md               # The telemetry procedure
    └── attempt-logging.md                 # Pointer: timing lives in the ledger, not the attempt
skills/run-autopilot/references/
├── phase-build.md                         # Handoff row at the build site
└── phase-review.md                        # Handoff rows at the review/done sites
```

### Module: dispatch-metrics
- **Maps to capability**: Dispatch rows, Ledger durability
- **Responsibility**: append rows and compute elapsed time; no state.json access,
  no git, no network.
- **Exports**:
  - CLI `record_dispatch.py end <id> --outcome ... [--detail ...]`
  - CLI `record_dispatch.py handoff --site ... --phase ... --prd ...`
  - `append_row(autopilot_dir, row) -> None` - the mirrored append, imported by
    `render_prompt.py`

### Module: render-prompt
- **Maps to capability**: Dispatch rows
- **Responsibility**: the two optional flags and the id echo; every existing code
  path unchanged.
- **Exports**: CLI flags `--dispatch-kind KIND`, `--dispatch-task ID`

### Module: telemetry-prose
- **Maps to capability**: Dispatch rows
- **Responsibility**: the call sites and the row catalogue.
- **Exports**: none (prose)

## Dependency Graph

### Foundation Layer (Phase 0)
No dependencies - built first.

- **dispatch-metrics**: the appender and the two CLI verbs.

### Core Layer (Phase 1)
- **render-prompt**: Depends on [dispatch-metrics] - it imports `append_row`.

### Integration Layer (Phase 2)
- **telemetry-prose**: Depends on [render-prompt, dispatch-metrics] - it names
  both CLIs and both flags.

## Implementation Phases

### Phase 0: Foundation
**Goal**: Rows can be appended and closed.

**Tasks**:
- [ ] Write `skills/work/scripts/record_dispatch.py` (stdlib only) exporting
      `append_row(autopilot_dir, row)` (mirrored append with `mkdir -p` on
      `ledger/`) and the `end` and `handoff` CLI verbs, resolving the autopilot
      dir with the existing `_walk_up.py` pattern and exiting 0 with no write
      when it cannot be resolved (no deps) - Acceptance:
      `python3 skills/work/scripts/record_dispatch.py end deadbeef --outcome ok`
      exits 0 outside any autopilot tree and writes nothing.
- [ ] Write `skills/work/scripts/test_record_dispatch.py` covering: `end` after a
      start row computes `elapsed_s` from `queued_at`; `end` with no start row
      records `elapsed_s: null` and exits 0; both files receive the row; a
      missing `ledger/` directory is created; `handoff` writes its four fields;
      an unresolvable autopilot dir writes nothing and exits 0; two concurrent
      appends both survive (no deps) - Acceptance:
      `uv run --no-project --with pytest python -m pytest -q skills/work/scripts/test_record_dispatch.py`
      green with all seven cases present.

**Exit Criteria**: The appender is correct in isolation; nothing calls it yet.

### Phase 1: Core
**Goal**: The render call emits start rows for free.

**Tasks**:
- [ ] Add `--dispatch-kind KIND` and `--dispatch-task ID` to
      `skills/work/scripts/render_prompt.py`: when both are present, generate an
      8-hex-char id, append the start row via `append_row` with the byte count it
      already computes, and echo the id on its own line after the existing byte
      count; when either is absent, change nothing. Add cases to
      `test_render_prompt.py`: absent flags, stdout is byte-identical to today
      and no file is written; both flags present, the row carries `prompt_bytes`
      equal to the printed count and stdout's second line is the id; an
      unresolvable autopilot dir still renders and still prints the count
      (depends on: Phase 0) - Acceptance:
      `uv run --no-project --with pytest python -m pytest -q skills/work/scripts/test_render_prompt.py`
      green with the three new cases present.

**Exit Criteria**: A render with the two flags produces a start row and an id, and one without is unchanged.

### Phase 2: Integration
**Goal**: Every dispatch and handoff site is wired and documented.

**Tasks**:
- [ ] Add a `## Dispatch telemetry` section to
      `skills/work/references/subagent-dispatch.md`: the row catalogue, the two
      flags on every render, the one `record_dispatch.py end` call after each
      dispatch returns, the outcome vocabulary mapped to the existing result
      table (`ok`, `timeout` for a watchdog kill, `killed` for a `TaskStop`,
      `error`, `lost` for an empty result), and the rule that a telemetry failure
      is never a dispatch failure (depends on: Phase 1) - Acceptance:
      `rg -n "dispatch-metrics.jsonl|record_dispatch.py" skills/work/references/subagent-dispatch.md`
      hits both.
- [ ] Wire the call sites: `skills/work/SKILL.md` steps 2.7, 2.85, 3, 5.5, 5.7
      and 7 pass the two render flags and make the closing `end` call; step 6.5
      writes a `handoff` row before the STOP. Add a pointer in
      `skills/work/references/attempt-logging.md` stating that timing lives in
      the dispatch ledger and is deliberately not an attempt field (depends on:
      Phase 2 task 1) - Acceptance:
      `rg -n "dispatch-kind" skills/work/SKILL.md` hits;
      `rg -n "dispatch-metrics" skills/work/references/attempt-logging.md` hits;
      `uv run --no-project --with pytest python -m pytest -q skills/work/scripts/test_dispatch_prose.py`
      green, its SKILL.md line-ceiling test included.
- [ ] Add the resume-side `handoff` rows to
      `skills/run-autopilot/references/phase-build.md` (session start) and
      `phase-review.md` (the review → review and review → done sites, beside the
      existing `review_converged` metric write); add prose pins to
      `test_dispatch_prose.py`; add the CHANGELOG entry (`feat` commit:
      `**work**` under Added, "per-dispatch timing ledger at
      dev/local/autopilot/dispatch-metrics.jsonl") (depends on: Phase 2 task 2) -
      Acceptance:
      `rg -n "handoff" skills/run-autopilot/references/phase-build.md skills/run-autopilot/references/phase-review.md`
      hits in both;
      `uv run --no-project --with pytest python -m pytest -q skills/run-autopilot/scripts/test_autopilot_lifecycle.py`
      green; `rg -n "dispatch-metrics" CHANGELOG.md` hits under `[Unreleased]`.

**Exit Criteria**: One PRD's work phase produces a ledger from which every dispatch's runtime and every handoff gap can be read.

## Test Strategy

### Critical Scenarios
- **Happy path**: a task's Tess, Ivan and Pat dispatches produce three start rows
  and three end rows with plausible `elapsed_s` and the prompt bytes each render
  reported.
- **Edge case**: a dispatch killed by the watchdog → an end row with
  `outcome: "timeout"` and the elapsed time that justified the kill.
- **Edge case**: a render without the flags (any caller this PRD did not wire) →
  no row, no id, byte-identical stdout.
- **Error case**: `dev/local/autopilot/` is not resolvable → every telemetry call
  exits 0 silently and the dispatch proceeds.

## Risks

- **Telemetry becomes a failure surface.** Every write is best-effort: an
  unresolvable directory, an unwritable file or a missing start row all exit 0,
  and no dispatch, gate or phase transition reads these rows.
- **Clerical overhead, which PRD 00093 exists to cut.** The start row costs zero
  extra calls (it rides the render the pack already makes) and the end row costs
  one. Measured against a dispatch of minutes, one append is noise.
- **File growth.** One dispatch is two short lines; a large PRD is a few hundred.
  The working copy is GC'd at 14 days by `purge-devlocal` and only the ledger
  mirror persists, matching `loop-metrics.jsonl`.
- **Concurrent appends from parallel rework tasks.** Every write is an
  append of one line, which is what the two-row design buys; the test suite
  covers the concurrent case.
