---
catchup: skip
design: skip
---

# Surface cap-out deferrals in batch reports

## Overview

### Problem Statement

A PRD that ends on the loop-mode cap-out branch hands the user a batch report that silently omits its open findings.

Observed while closing PRD 00140 on 2026-08-26 (batch `202608180438`, run from `~/.claude`). Cycle 2 raised six findings, hit `rework_cap` 2, and took the cap-out branch. All six were recorded, correctly, in `~/.claude/dev/local/autopilot/deferred/202608180438-deferred.json` (`items[]` entries with `prd` = 00140: one `high` carrying a `resolved` block, five `medium` without; a read-only source on the author's machine, copied into an in-repo fixture by Phase 1). But the batch report's `## 00140-...` section rendered with **no `### Deferred to Batch End` table at all**, while five of those findings were still open. Every other PRD in that batch has the table, because they converged normally instead of capping out.

Three distinct defects combine to produce it:

1. **Two sinks, no arbiter.** `references/phase-review.md:53` tells the cap-out branch to append each unresolved finding to `state.deferred_decisions`. `references/phase-done.md` step 6 then migrates that array into the batch deferred JSON via `autopilot defer`. The cycle-2 session skipped step one and called `autopilot defer` directly, which is a legal-looking way to "record a deferral" and is exactly what step 6 does. Nothing detected the difference.
2. **The renderer reads only one sink.** `cli/render_report.py:321` builds its list from `state.get("deferred_decisions")` alone, so records that reached only the JSON are invisible to it.
3. **Cap-overflow records cannot fill the table they belong in.** `_deferred_to_batch_end` (`cli/render_report.py:168-180`) renders the Reason column as `d.get("disposition") or d.get("reason")`, but the record shape `phase-review.md:53` mandates is `{"type", "issue", "severity", "consensus"}` — neither key. Even with the correct sink, every cap-out row would render an empty Reason.

The pipeline's stated purpose is that nothing fails quiet. A cap-out is precisely the moment a PRD ships with known open findings, so it is the moment the report most needs to be complete.

### Target Users

The operator reading a batch report at batch end to decide what still needs attention, and any future session triaging `deferred/<batch>-deferred.json`. Both currently get an incomplete picture from a PRD that capped out, with no signal that anything is missing.

### Success Metrics

- Replaying PRD 00140's cycle-2 records (the in-repo fixture) through `autopilot render report` produces a `### Deferred to Batch End` table with one row per unresolved record, each with a non-empty Reason cell. Today it produces no table.
- A record written to EITHER sink appears exactly once in the rendered table (no duplicate row when it is present in both).
- Seeding the batch deferred JSON with a pending item for the PRD being finalized that the rendered report does not contain makes the finalize step exit non-zero and name the missing item. Today it exits 0.
- The fixture replay renders the same five rows the hand-patched 00140 section of `~/.claude/dev/local/autopilot/reports/202608180438-report.md` lists (a read-only comparison; regenerating that report in place is a post-release signal, not judged in-session).

## Functional Decomposition

### Capability: Unambiguous deferral recording

Covers making a cap-out deferral land somewhere the report can always see, and carry enough text to render.

#### Feature: Self-describing cap-overflow record
- **Description**: The cap-out record gains the field the report's Reason column actually reads, so a cap-out row is never blank.
- **Inputs**: An unresolved finding from the converging review cycle (issue text, severity, consensus).
- **Outputs**: A record carrying `type: "cap-overflow"`, `issue`, `severity`, `consensus`, and a `reason` explaining that the rework cap was reached with the finding unresolved.
- **Behavior**: `_deferred_to_batch_end` reads `d.get("disposition") or d.get("reason")`; populating `reason` fills the column with no renderer change. The prose in `references/phase-review.md` § cap-out is updated to specify the field as part of the mandated record shape.

#### Feature: Named single sink for a cap-out
- **Description**: The cap-out branch's prose names `state.deferred_decisions` as the one sink it writes, and says explicitly that `autopilot defer` is Phase 9's migration tool, not a cap-out recording tool.
- **Inputs**: `references/phase-review.md` § loop-mode cap-out; `references/phase-done.md` step 6.
- **Outputs**: Prose that a session cannot satisfy by calling `autopilot defer` at review time.
- **Behavior**: Documentation only. The union read below is what makes a mistake here harmless; this feature makes the mistake less likely.

### Capability: Complete rendering and reconciliation

Covers the report showing every open finding regardless of which sink holds it, and failing loud when it cannot.

#### Feature: Union read across both sinks
- **Description**: The report's deferred table renders the union of `state.deferred_decisions` and the batch deferred JSON's entries for the PRD being rendered, deduplicated.
- **Inputs**: `state.deferred_decisions`; `dev/local/autopilot/deferred/<batch_id>-deferred.json` filtered to `prd == <the PRD being rendered>`.
- **Outputs**: One row per distinct unresolved finding.
- **Behavior**: Both sinks are filtered by the existing `_is_pending` rule, then merged. Dedup key is the normalized `issue` string (whitespace-collapsed, case-folded) — chosen because it is the only field both record shapes always carry; `file` and `cycle` appear in the JSON shape but not in the `phase-review.md:53` state shape. An entry carrying a `resolved` block (as PRD 00140's High does) is excluded from the table and does not count as pending. That exclusion lives in `_merge_deferral_sinks`, NOT in `_is_pending`: `_is_pending` keys on `status` only, and its negation `is_escalated_row` is how `statectl._completed_prd_record` counts `escalated_decisions`, so widening `_is_pending` would count every resolved item as escalated.
- **Dedup key (guess)**: the normalized-`issue` key is a judgement call, not an observed contract; two reviewers wording the same defect differently would produce two rows rather than one. That is the same failure mode `consolidate_findings` already has and is acceptable here — over-reporting an open finding is safe, under-reporting is the bug being fixed.

#### Feature: Finalize-time reconciliation guard
- **Description**: After rendering, finalize verifies that every pending deferred-JSON item for this PRD appears in the report it just wrote, and fails loud when one does not.
- **Inputs**: The rendered report text for this PRD's section; the deferred JSON's pending items for this PRD.
- **Outputs**: Exit 0 and silence when reconciled; exit non-zero plus a stderr line naming each missing item's issue text when not.
- **Behavior**: The backstop for the whole class, independent of which sink a future writer picks. It catches a renderer regression, a new record type nobody taught the renderer about, and the exact 00140 failure. It must not fire on items carrying a `resolved` block.

## Structural Decomposition

### Repository Structure

```
skills/run-autopilot/
├── cli/
│   ├── render_report.py             # Maps to: Union read across both sinks; missing_from_report (pure)
│   ├── __main__.py                  # Maps to: Finalize-time reconciliation guard (exit wiring in _run_render, :590)
│   ├── test_render_deferrals.py     # NEW: union + dedup + resolved-exclusion + guard coverage (test_render.py is 684 of the 800-line cap)
│   └── golden/
│       └── deferred-00140-cycle2.json   # NEW: the six 00140 cycle-2 records, copied verbatim
└── references/
    ├── phase-review.md              # Maps to: Named single sink, Self-describing record
    └── phase-done.md                # Maps to: Finalize-time reconciliation guard (step 7a)
```

### Module: render-report-union
- **Maps to capability**: Complete rendering and reconciliation
- **Responsibility**: Render the deferred table from both sinks, deduplicated, excluding resolved entries.
- **Exports**:
  - `_deferred_to_batch_end(deferred)` - unchanged signature; callers pass the merged list
  - `_merge_deferral_sinks(state_deferrals, json_items)` - pure merge, dedup and `resolved` exclusion, no I/O

### Module: reconcile-deferrals
- **Maps to capability**: Complete rendering and reconciliation
- **Responsibility**: Compare the deferred JSON's pending items for one PRD against a rendered report and report what is missing.
- **Exports**:
  - `missing_from_report(report_text, json_items, prd)` - PURE, in `render_report.py`; returns the list of unreconciled items
  - `autopilot render report` (`cli/__main__.py::_run_render`) gains a non-zero exit and stderr naming them

### Module: cap-out-prose
- **Maps to capability**: Unambiguous deferral recording
- **Responsibility**: State the record shape and the single sink for a loop-mode cap-out.
- **Exports**: none (prose)

## Dependency Graph

### Foundation Layer (Phase 0)
No dependencies - built first.

- **cap-out-prose**: Fixes the record shape (`reason`) and names the sink. Pure documentation; nothing imports it.

### Core Layer (Phase 1)
- **render-report-union**: Depends on [cap-out-prose] for the record shape it renders.

### Integration Layer (Phase 2)
- **reconcile-deferrals**: Depends on [render-report-union] - it verifies the output that module produces, so it must be built against the finished renderer or it would pin today's incomplete behaviour.

## Implementation Phases

### Phase 0: Foundation
**Goal**: The mandated cap-out record can fill the table it belongs in, and the sink is named.

**Premise**: `references/phase-review.md:53` specifies the cap-out record as `{"type": "cap-overflow", "issue", "severity", "consensus"}` with no `reason` or `disposition` key, and `references/phase-done.md` step 6 is the `autopilot defer` migration step. Re-check both at execution time; if either has already been changed to carry a reason field or to name the sink, skip that edit and report it rather than forcing.

**Tasks**:
- [ ] Add `reason` to the cap-out record shape in `references/phase-review.md` § loop-mode cap-out, and state that `state.deferred_decisions` is the only sink a cap-out writes, with `autopilot defer` named as Phase 9's migration tool (no deps) - Acceptance: `rg -n 'reason' references/phase-review.md` hits the cap-out record shape; `rg -n 'autopilot defer' references/phase-review.md` hits a line saying it is NOT the cap-out path.

**Exit Criteria**: The mandated record shape carries every field `_deferred_to_batch_end` reads.

### Phase 1: Core
**Goal**: A deferral in either sink reaches the report exactly once.

**Premise**: `cli/render_report.py:321` builds its deferred list from `state.get("deferred_decisions")` only, and `_deferred_to_batch_end` filters with `_is_pending`. Re-check at execution time; if the renderer already reads the JSON, skip and report.

**Tasks**:
- [ ] Add `_merge_deferral_sinks(state_deferrals, json_items)` and render the deferred table from the merged list, excluding entries carrying a `resolved` block (depends on: Phase 0) - Acceptance: a unit test in the new `cli/test_render_deferrals.py` seeds a record in the JSON sink ONLY and asserts it renders as a row; a second seeds the same normalized issue in BOTH sinks and asserts exactly one row; a third seeds an entry with a `resolved` block and asserts no row. All three fail against the current renderer.
- [ ] Replay PRD 00140's six cycle-2 records through the renderer as a fixture (depends on: Phase 0) - Acceptance: the six records are copied verbatim from `~/.claude/dev/local/autopilot/deferred/202608180438-deferred.json` (`items[]` entries whose `prd` names 00140; read-only author-machine source) into `cli/golden/deferred-00140-cycle2.json`; five rows render (the sixth carries a `resolved` block naming `c175402` and is excluded), and every rendered row has a non-empty Reason cell.

**Exit Criteria**: `autopilot render report` reproduces the hand-written 00140 section from fixture data rather than by hand.

### Phase 2: Integration
**Goal**: A deferral that never reaches the report stops the finalize step instead of passing silently.

**Premise**: `references/phase-done.md` step 7 runs `autopilot render report` and today ignores its relationship to step 6's JSON writes. Re-check the step numbering at execution time before inserting a step 7a.

**Tasks**:
- [ ] Add `missing_from_report(report_text, json_items, prd)` as a pure function in `render_report.py` and wire it into `autopilot render report` (`cli/__main__.py::_run_render`) so an unreconciled pending item exits non-zero naming each one (depends on: Phase 1) - Acceptance: a test seeds a pending JSON item absent from the report text and asserts a non-zero exit with the issue text on stderr; a second asserts a `resolved`-bearing item does NOT trip the guard; a third asserts a fully reconciled report exits 0 silently.
- [ ] Document the guard as `references/phase-done.md` step 7a (depends on: Phase 1) - Acceptance: `rg -n '7a' references/phase-done.md` hits the reconciliation step and names its non-zero exit.

**Exit Criteria**: Seeding a mismatch makes finalize fail loud; a clean batch finalizes silently as before.

## Test Strategy

### Critical Scenarios
- **Happy path**: a PRD converges normally with two deferrals in `state.deferred_decisions` → both render, guard exits 0, behaviour identical to today.
- **The 00140 case**: cap-out records exist ONLY in the batch deferred JSON → they render as rows with populated Reason cells, and the guard exits 0 because the report now contains them.
- **Edge case**: the same finding is present in both sinks with differently-whitespaced issue text → exactly one row.
- **Edge case**: an item carrying a `resolved` block → excluded from the table, and does not trip the guard.
- **Error case**: a pending JSON item that the renderer cannot place (unknown shape, missing `issue`) → guard exits non-zero and names it, rather than dropping it.

## Risks

- **Dedup collapses two genuinely distinct findings that share issue text**: over-merging hides a finding, which is the same class of bug being fixed. Mitigated by keying on the full normalized issue string rather than a prefix or a token subset, and by the guard: a collapsed row still satisfies reconciliation, so a test asserts two distinct issues always yield two rows.
- **The guard fires on historical batches whose reports predate it**: `~/.claude/dev/local/autopilot/deferred/202607202320-deferred.json` and others hold items from batches whose reports were rendered by the old code. Scope the guard to the PRD currently being finalized, never to the whole file, so old batches are untouched.
- **Union read changes an existing report's content on re-render**: re-rendering an old batch could now add rows. Acceptable and arguably correct, but the reconciliation guard must not retroactively fail a finalize for a PRD closed before this PRD shipped.
