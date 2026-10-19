---
design: skip
default_model: sonnet
model_tier_rationale: one subcommand with its exact fold rule and output shape given, one prose paragraph given verbatim, additive tests with their assertions given
---

# Fast-track survivors reach the batch ledger

Source: batch 202610100952 in the agent-skills repo, 2026-10-18. PRD 00087 ran on the fast-track lane. Alice and Carl both raised a MEDIUM (`main()` at 53 lines, over the repo's 50-line limit), Alice and Blake raised three LOWs. The exit rule took the item to `committed`, as designed, and the five rows went into the item's `loop-metrics.jsonl` row and nowhere else: the PRD's audit log reads "no decisions recorded", its batch-report section has no Deferred table, and the batch deferred ledger holds no 00087 row. The full lane records every surviving Medium and Low in the ledger (0.10.0), so the same finding is kept or lost depending on the lane the classifier picked.

## Problem

`skills/fast-track/SKILL.md:447` says a MEDIUM or a LOW neither reworks nor blocks the exit, and the Verify step writes every raised row to the item's raised file with the keys `severity`, `title`, `file` and `lane` (`skills/fast-track/SKILL.md:434`). `verify_targets` (`skills/fast-track/scripts/fast_track_plan.py:51`) selects the CRITICAL and HIGH rows for Victor; the others reach `record_item.py` together with the outcome `committed` (`skills/fast-track/SKILL.md:637`), which stores the array as `findings` in the metrics row (`skills/fast-track/scripts/record_item.py:128`). The batch deferred ledger is written by the `defer` verb (`skills/run-autopilot/cli/__main__.py:535`, `record_defer` at `skills/run-autopilot/cli/records.py:138`), which the lane never calls, so `_deferred_to_batch_end` (`skills/run-autopilot/cli/render_report.py:273`) has nothing to render for a fast-track PRD and the batch-end triage never sees the rows.

## Solution

`fast_track_plan.py` gains a `ledger-rows` verb, registered beside its siblings through `add_parser` (`skills/fast-track/scripts/fast_track_plan.py:116`): `ledger-rows <raised.json> --lenses <n>` reads the raised array through `_load_findings` (`skills/fast-track/scripts/fast_track_plan.py:96`), which exits 2 on a file that is anything but that array, keeps the rows whose severity is MEDIUM or LOW, folds them by `(severity, file with a trailing ':N' or ':N-M' suffix removed)`, and prints a JSON array with one object per group in first-raised order: `{"type": "review-deferral", "cycle": 1, "severity": "<medium|low>", "issue": "<the first-raised title>", "file": "<the stripped file>", "consensus": "<count of distinct lanes in the group>/<n>", "reason": "fast-track exit: a medium or low neither reworks nor blocks", "lane": "fast-track"}`, and prints `[]` when no row qualifies.

`skills/fast-track/SKILL.md` gains this paragraph right after the sentence ending `neither reworks nor blocks the exit. It exits 2 on a file that is anything but that array.` (`skills/fast-track/SKILL.md:447`):

`Those rows are kept, not dropped. Under the loop (the variable _AUTOPILOT_LOOP is set) run ledger-rows over the same file with --lenses set to the number of lenses that reported, and for each printed object run autopilot defer --prd <the card's PRD filename> --batch <state.batch.id> --json '<the object>', so the survivors land in the batch deferred ledger beside the full lane's deferrals and the batch report's Deferred table and the batch-end triage see them. Outside the loop print the objects in the item report instead.`

with `_AUTOPILOT_LOOP`, `ledger-rows`, `--lenses`, `autopilot defer` and the three flags in backticks.

## Requirements

### Must have
- `ledger_rows(findings, lenses)` in `skills/fast-track/scripts/fast_track_plan.py` and the `ledger-rows` verb wired in `_parser` and `_main`, with the fold and output shape above.
- Tests in `skills/fast-track/scripts/test_fast_track_plan.py`: `test_ledger_rows_keeps_medium_and_low_only` (one CRITICAL, one HIGH, one MEDIUM, one LOW: two objects, severities `medium` and `low`), `test_ledger_rows_folds_one_file_across_lanes` (two MEDIUM rows for one file, the first cited with a line suffix and the second without, from lanes `fast-track:alice` and `fast-track:carl`, `--lenses 4`: one object with `consensus` `2/4`, `issue` from the first row and `file` without the suffix), `test_ledger_rows_prints_an_empty_array_without_survivors`, `test_ledger_rows_exits_two_on_a_non_array`.
- A prose test in `skills/fast-track/scripts/test_fast_track_prose.py` pinning the paragraph: `test_skill_sends_survivors_to_the_batch_ledger` asserts the skill text contains `ledger-rows`, `autopilot defer` and `Those rows are kept, not dropped.`.
- A CHANGELOG `[Unreleased]` Fixed entry under **fast-track**: a card's surviving Medium and Low findings are written to the batch deferred ledger under the loop, so the batch report and the batch-end triage see them as they do the full lane's.

### Nice to have
- None.

## Implementation

### Module: plan-ledger-rows
- **Location**: `skills/fast-track/scripts/fast_track_plan.py`
- **Responsibility**: fold the surviving rows into ledger objects
- **Exports**: `ledger_rows()`, `verify_targets()` (unchanged), `exit_action()` (unchanged)
- New symbols: `ledger_rows`

### Module: plan-tests
- **Location**: `skills/fast-track/scripts/test_fast_track_plan.py`
- **Responsibility**: pin the fold, the filter and the refusals
- **Exports**: none
- New symbols: `test_ledger_rows_keeps_medium_and_low_only`, `test_ledger_rows_folds_one_file_across_lanes`, `test_ledger_rows_prints_an_empty_array_without_survivors`, `test_ledger_rows_exits_two_on_a_non_array`

### Module: skill-prose
- **Location**: `skills/fast-track/SKILL.md`, `skills/fast-track/scripts/test_fast_track_prose.py`
- **Responsibility**: tell the lane to write the survivors and pin the sentence
- **Exports**: none
- New symbols: `test_skill_sends_survivors_to_the_batch_ledger`

### Dependencies
- plan-ledger-rows: No dependencies (foundation)
- plan-tests: Depends on [plan-ledger-rows]
- skill-prose: Depends on [plan-ledger-rows]

## Tasks

### Phase 0: Foundation
- [ ] Add the four plan tests and the prose test. Premise: `rg -c "def ledger_rows" skills/fast-track/scripts/fast_track_plan.py` prints 0 before the edit; a different count means the verb already landed and the task stops and reports. - Acceptance: `uv run --no-project --with pytest python -m pytest -q skills/fast-track/scripts/test_fast_track_plan.py skills/fast-track/scripts/test_fast_track_prose.py -k "ledger_rows or survivors"` fails all five against the current code and prose.

### Phase 1: Core
- [ ] Implement `ledger_rows` and the verb, add the paragraph and the CHANGELOG entry (depends on: Phase 0) - Acceptance: `uv run --no-project --with pytest python -m pytest -q skills/fast-track/scripts/test_fast_track_plan.py skills/fast-track/scripts/test_fast_track_prose.py` passes; `rg -c "Those rows are kept, not dropped." skills/fast-track/SKILL.md` prints 1; `rg -n "fast-track.*batch deferred ledger" CHANGELOG.md` prints one line under `[Unreleased]`.

## Success Criteria

- Both test modules pass in full, including `test_lane_reference_names_every_kind`.
- Post-release signal: the next fast-track PRD whose reviewers raise a Medium shows that Medium in the batch report's Deferred table and in `deferred/<batch>-deferred.json`.
