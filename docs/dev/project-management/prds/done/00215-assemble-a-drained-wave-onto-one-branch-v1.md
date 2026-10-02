---
catchup: skip
design: run
default_model: sonnet
model_tier_rationale: sonnet floor by operator decision 2026-09-26 (the opus floor cost 109 min per task on 00214, 95 of them in test rounds); the planner still lifts the rebase resolver and the ledger migration to opus per task through the two escalator rows they hit
rework_cap: 2
---

# Assemble a drained wave onto one branch

Source: `dev/local/discovery/00212-route-prds-in-waves.md` must-haves 4 and 6,
open questions 3 and 4 (2026-09-21). Grounded at `8885300` (0.5.5). Depends on
00214 (`wave.json`, lane worktrees); 00216 reviews the assembled branch and
lands it on master.

## Overview

### Problem Statement

After a wave drains, its work sits on N lane branches in N worktrees, with N
sets of ledgers, reports, reviews and lifecycle dirs. On 2026-09-20 the
integration was done by hand: rebase each lane onto the current head in a fixed
order, keep both sides of every `CHANGELOG.md` and `dev/bin/release-checks`
conflict, resolve six same-line conflicts by hand, run `release-checks` after
each merge. The plugin has no owner for any of it. This PRD makes the
deterministic part code: `autopilot wave assemble` merges the drained lanes in
order onto one assembly branch, keeps both sides of append-only conflicts,
stops a lane on any other conflict, and pulls every lane's artifacts into the
main checkout. Master is untouched: 00216 lands the branch after its review.
Lane commits' `Integrator:` trailers (discovery must-have 4; `16c451a` carries
`Integrator: CHANGELOG.md, one bullet appended at the END of [Unreleased] Added`)
are prose for a human integrator; code cannot apply them, so the summary
surfaces every one verbatim and applies none.

Open questions 3 and 4 are decided here: a lane's parked PRDs move to the main
`hold/` at assembly; each lane keeps the batch id its loop minted, and the wave
id plus a `lane` field are added to the migrated rows.

### Target Users

The operator, after `autopilot wave status` shows every lane `drained` or
`unfinished`.

### Success Metrics

- `uv run --no-project --with pytest python -m pytest -q skills/run-autopilot/cli/test_wave_assemble.py`
  green (real git repos in `tmp_path`, real conflicts).
- `bash dev/bin/release-checks` green (`test_wave_assemble.py` joins the
  `[checks] waves` block).
- Post-release signal: on the first real wave, every lane that assembled
  cleanly needed zero operator git commands, and every kept lane's
  `assembly_conflict` record names the exact conflicted paths.

## Functional Decomposition

### Capability: Assembly
Merge drained lanes onto one branch, in order, with the append-only rule.

#### Feature: Merge lanes in order onto an assembly branch
- **Description**: `autopilot wave assemble` rebases each drained lane onto the
  assembly branch and fast-forwards it in, running `release-checks` after each.
- **Inputs**: `wave.json` (`base_sha`, lanes in `order`, each lane's derived
  status per 00214 `lane_status`), the lane worktrees.
- **Outputs**: worktree `<repo parent>/<repo basename>-wave` on branch
  `wave/<id>/assembly` holding every merged lane; per-lane `status` in
  `wave.json`: `assembled`, `conflict`, `checks_failed` or `unfinished`; per
  lane (merged or kept) `files` = `git diff --name-only <base_sha>..<lane
  branch>` (sorted; 00216 sizes the review scope from it) and
  `integrator_notes` = every `Integrator:` trailer line in the same range as
  `[{"sha": "<short sha>", "text": "<line after the colon>"}]`; wave
  `status`: `assembled` (all merged) or `assembled_partial`; exit 0 when all
  merged, 3 when any lane was kept.
- **Behavior**: preconditions: every lane pid dead (a live one exits 1 naming
  it: "wait or abort"), main tree clean, wave status `running`. Create the
  assembly worktree at `base_sha` with its own `dev/local/{autopilot,prds/...}`
  (the 00214 worktree layout). For each lane in `order` with status `drained`:
  record `files` and `integrator_notes` (above) before touching the branch;
  `git -C <lane worktree> rebase <assembly branch>`; while the rebase stops on
  conflicts, for each conflicted path in `WAVE_APPEND_ONLY` strip the
  `<<<<<<<`, `=======` and `>>>>>>>` lines keeping both sides in file order
  (the 2026-09-20 `keep_both.py` rule), `git add` it, and `GIT_EDITOR=true git
  rebase --continue`; a conflicted path outside that set → `git rebase
  --abort`, lane status `conflict`, one record via
  `records.record_defer(<main autopilot dir>, <lane's first PRD>, <wave id>,
  {"type": "stall", "site": "assembly_conflict", "lane", "files": [...],
  "detail": "<n> conflicted path(s) outside the append-only set: <paths>",
  "op_id": "wave-<id>-<lane>"})`, continue with the next lane. A clean rebase
  → `git -C <assembly worktree> merge --ff-only <lane branch>` → `bash
  dev/bin/release-checks` in the assembly worktree; non-zero → `git reset
  --hard <sha before this merge>`, lane status `checks_failed`, the same record
  shape with `"detail": "release-checks exit <rc> after merging <lane>: <last
  stderr line>"`, continue. A lane with status `unfinished` is skipped, never
  merged. Sequential and deterministic; no model session anywhere in this verb.

#### Feature: Migrate lane artifacts into the main checkout
- **Description**: every lane's ledgers, deferred items, reports, reviews and
  PRDs land in the main checkout, tagged with the lane and the wave.
- **Inputs**: each lane worktree's `dev/local/autopilot/` and lifecycle dirs;
  the lane's batch id (its `state.json`, or the newest
  `reports/*-state-final.json`).
- **Outputs**: appended rows in the main `loop-metrics.jsonl`,
  `ledger/*.jsonl` and `dispatch-metrics.jsonl`; migrated deferred items;
  copied reports and reviews; PRDs in `done/`, `hold/` or `backlog/`.
- **Behavior**: for EVERY lane, merged or kept: append each row of
  `loop-metrics.jsonl` and `ledger/*.jsonl` to the main file of the same name
  with `"lane": "<name>", "wave": "<id>"` added (the `ledger/` mirror too);
  same for `dispatch-metrics.jsonl`; each `deferred/<batch>-deferred.json`
  item goes through `records.record_defer(<main dir>, item["prd"], <lane batch
  id>, item)` (its `op_id` dedupe makes a rerun idempotent); copy `reports/*`
  and `dev/local/reviews/*` skipping names that exist. PRDs: a merged lane's
  `done/*` → main `done/`, `hold/*` → main `hold/`; a kept lane's `hold/*` →
  main `hold/`, `wip/*` and `backlog/*` → main `backlog/`, and its `done/*`
  stay in the kept worktree (finished work that is not on the assembly branch;
  the summary lists them as `unassembled`). A merged lane's worktree is removed
  (`git worktree remove --force`, `git branch -D`); a kept lane's worktree and
  branch stay. A rerun skips lanes already `assembled`.

#### Feature: Wave summary report
- **Description**: one durable file per wave in the main `reports/`.
- **Inputs**: `wave.json` (lanes with `files` and `integrator_notes`), the
  migrated rows, the `assembly_conflict` records.
- **Outputs**: `dev/local/autopilot/reports/<wave id>-wave.md`.
- **Behavior**: header (wave id, `base_branch@base_sha`, assembly branch and
  head sha), the lane table (lane, branch, PRDs, owned paths, status, lane
  batch id), one line per PRD in the form `- <prd>: Wave <id>, lane <name>,
  <done|parked|unassembled|backlog>`, totals over the migrated session rows
  (sessions, wall hours, `cost_usd` where present), every
  `assembly_conflict` record verbatim, and `## Integrator notes`: one line
  `- <lane> <sha>: <text>` per `integrator_notes` entry of every lane, merged
  or kept, verbatim and unapplied; `(none)` when there are none. `wave.json`
  gains `"assembly":
  {"worktree", "branch", "head_sha", "merged": [...], "kept": [...]}`.
  Written last, rewritten on rerun.

## Structural Decomposition

### Repository Structure

```
skills/run-autopilot/cli/
├── wave_assemble.py        # Maps to: Assembly (all three features)
├── wave_cli.py             # Maps to: the `assemble` verb (file from 00214)
├── test_wave_assemble.py   # Maps to: Test Strategy
skills/run-autopilot/references/waves.md          # Maps to: § Assemble (file from 00214)
skills/run-autopilot/references/recovery.md       # Maps to: § Stall `site` slugs row
skills/run-autopilot/references/batch-report-format.md  # Maps to: § Wave summary
skills/run-autopilot/SKILL.md                     # Maps to: Retention (the summary is durable)
dev/bin/release-checks                            # Maps to: `[checks] waves` block
CHANGELOG.md
```

### Module: wave_assemble
- **Maps to capability**: Assembly
- **Responsibility**: the merge pass, the migration and the summary.
- **Exports**: `keep_both(text) -> str` (pure), `merge_lane(assembly, lane, *,
  run_git, run_checks) -> str` (returns the lane status), `migrate_lane(main,
  wave_id, lane) -> None`, `summary(wave, rows, records) -> str` (pure),
  `assemble(repo, wave_path, *, run_git, run_checks) -> int`.

## Dependency Graph

### Foundation Layer (Phase 0)
No dependencies - built first.

- **keep_both and summary**: pure text functions.

### Core Layer (Phase 1)
- **merge_lane, migrate_lane**: Depends on [keep_both, 00214 `wave` module,
  `cli/records.record_defer`].

### Integration Layer (Phase 2)
- **assemble verb, prose, changelog**: Depends on [merge_lane, migrate_lane,
  summary].

## Implementation Phases

### Phase 0: Foundation
**Goal**: the two pure pieces are exact.

**Tasks**:
- [ ] Add `keep_both` and `summary` to `cli/wave_assemble.py` with their tests
  (no deps) - Acceptance: `test_keep_both_keeps_both_sides_in_file_order`,
  `test_keep_both_leaves_a_clean_file_alone`,
  `test_summary_names_every_prd_with_its_lane_and_outcome`,
  `test_summary_lists_conflict_records_verbatim`,
  `test_summary_lists_integrator_trailers` (two lanes, three notes, rendered
  verbatim under `## Integrator notes`; a wave without any renders `(none)`)
  green.

**Exit Criteria**: the two functions under 50 lines, no disk access.

### Phase 1: Core
**Goal**: lanes merge or are kept with a record; artifacts migrate.

**Tasks**:
- [ ] Add `merge_lane` and the merge pass (depends on: Phase 0) - Acceptance:
  in `tmp_path` git repos with real lane branches:
  `test_assemble_merges_drained_lanes_in_order`,
  `test_append_only_conflicts_keep_both_sides_in_order`,
  `test_other_conflict_keeps_the_lane_and_records_assembly_conflict`,
  `test_checks_failure_undoes_the_lane_merge_and_keeps_it`,
  `test_unfinished_lane_is_skipped_not_merged`,
  `test_live_lane_refuses_assembly`,
  `test_assemble_records_each_lanes_files_and_integrator_trailers` (a lane
  branch with two commits, one carrying an `Integrator:` trailer: the lane
  entry's `files` is the sorted name-only diff and `integrator_notes` holds
  that one sha and text; a kept lane is recorded too) green.
- [ ] Add `migrate_lane` (depends on: Phase 0) - Acceptance:
  `test_ledger_rows_gain_lane_and_wave_fields`,
  `test_dispatch_rows_migrate_too`,
  `test_deferred_items_migrate_idempotently`,
  `test_prds_land_in_done_hold_or_backlog_by_lane_status`,
  `test_merged_worktrees_and_branches_are_removed`,
  `test_kept_lane_keeps_its_done_prds_and_worktree` green.

**Exit Criteria**: `test_rerun_is_idempotent` green (a second `assemble` on
the same wave changes nothing and exits with the same code).

### Phase 2: Integration
**Goal**: the verb is wired and documented.

**Tasks**:
- [ ] Register `assemble` in `wave_cli.py`, add § Assemble to
  `references/waves.md` (what merges, what is kept, how the operator finishes
  a kept lane: rebase by hand in its worktree, then rerun `assemble`), add
  `assembly_conflict` to `references/recovery.md` § Stall `site` slugs (written
  by `autopilot wave assemble`, no session and no `state.json` behind it), add
  § Wave summary to `references/batch-report-format.md`, list
  `reports/<wave id>-wave.md` as durable in core `SKILL.md` § Retention, add
  `test_wave_assemble.py` to the `[checks] waves` block, and a CHANGELOG
  `### Added` entry under `**run-autopilot**` (depends on: Phase 1) -
  Acceptance: `test_wave_assemble.py::test_docs_name_the_site_and_the_summary`
  pins `assembly_conflict` in `recovery.md` and `-wave.md` in
  `batch-report-format.md` and the Retention list; `release-checks` green.

**Exit Criteria**: suites green; `release-checks` green.

## Test Strategy

### Critical Scenarios
- **Happy path**: three drained lanes, two of which append to `CHANGELOG.md`
  and `release-checks` → both-added conflicts resolved by keeping both, all
  three fast-forwarded, checks green after each, worktrees gone, PRDs in main
  `done/`, rows tagged → Expected: exit 0, summary lists three lanes
  `assembled`.
- **Edge case**: lane 2 edits the same line as lane 1 in `cli/records.py` →
  rebase aborted, lane 2 `conflict` with the path in its record, lane 3 still
  merges → Expected: exit 3, lane 2's worktree present, its `done/` PRDs
  listed `unassembled`, its `wip/` PRD back in main `backlog/`.
- **Error case**: a lane's `release-checks` fails after a clean merge → the
  merge is undone (`reset --hard`), lane `checks_failed`, later lanes merge on
  the pre-merge head → Expected: the assembly branch never carries a red
  lane; a live lane pid → exit 1 before any git command.

## Risks

- **Rebase rewrites lane commits**: acceptable, the branches are unpublished;
  the summary records the post-rebase head per lane.
- **A kept lane blocks nothing**: later lanes merge without it, so an operator
  finishing the kept lane by hand rebases onto the newer assembly head; the
  runbook says so.
- **Row duplication on rerun**: session and dispatch rows carry no op_id, so
  migration is guarded by a per-lane `migrated_at` stamp in `wave.json`
  rather than by dedupe; deferred items dedupe on `op_id` as today.
