---
catchup: run
design: skip
default_model: sonnet
model_tier_rationale: four small verbs with exact contracts and one brief line; the artifact rule is stated as an expression
---

# Replace the shell work loop sessions get wrong with verbs

Source: `docs/dev/project-management/audit-results/loop-efficiency-2026-10-13.md` (E1, E4).

## Problem

A census of the 55 loop session transcripts of batch 202610111300 counts 437 errored tool calls in 6,851 (6.4%). The repeatable ones are the model doing by shell what a verb should do.

Markers: 7 `ls` and 6 `rm` on the `handoff-requested` and `cap-fired` markers when they are absent; the prose at `skills/work/SKILL.md:456` says to read the `handoff-requested` marker and leaves the how to the model.

Decisions: 11 `autonomous_decisions` appends rejected by `_validate_decision_entry` (`skills/run-autopilot/cli/schema.py:247-270`) for a missing issue or severity, each a wasted turn; the instruction that asks for the append is at `skills/run-autopilot/references/phase-review.md:145`.

Reads: 5 `statectl.py get` calls that exit 1 with `json-path key not found` before the key exists (`skills/run-autopilot/scripts/statectl.py:14-28`).

Tool ban: 101 blocked `head`, `tail` and `cat` calls although both skill bodies forbid them (`skills/work/SKILL.md:125`, `skills/run-autopilot/SKILL.md:304`); prose alone is not holding.

Dispatch rows: the ledger cannot measure subagent time. This batch closed 29 of 42 `pat` rows, 30 of 60 `tess` rows and 24 of 55 `ivan` rows as `lost` because the model never called the `end` verb, and `_handoff` (`skills/work/scripts/record_dispatch.py:175-200`) marks every open row lost at the session edge even when the result was used.

## Solution

Four verbs and one brief line, all code-decided. `autopilot markers --check <name>...` and `--clear <name>...` answer and remove markers without an error on absence. `statectl.py decide` takes the entry's fields as flags and builds the dict `_validate_decision_entry` accepts. `statectl.py get <path> --default <json>` prints the default instead of failing. `record_dispatch.py handoff` closes an open row from the artifact its subagent leaves behind before falling back to `lost`: an `ivan` or `tess` row closes `ok` on the newest commit after `queued_at` whose subject ends with `(task <task>)` (for `tess`, one whose subject starts with `test(`), with `elapsed_s` = commit time minus `queued_at` and `detail: "closed-by: commit <sha>"`; a `pat` row closes `ok` when the review output file that `sonnet-run.sh` writes (`skills/work/references/per-task-review.md:42`) has an mtime at or after `queued_at`, `detail: "closed-by: artifact"`. The session brief rendered by `render_brief` (`skills/run-autopilot/cli/brief.py:161`) gains one line under its title: `Tools: Read, Edit, Write, rg. Bash head, tail, cat, grep and find are hook-blocked.`

## Requirements

### Must have
- `autopilot markers --check a b` prints one JSON object `{"a": true|false, "b": ...}` and exits 0; `--clear a b` removes each present marker, prints the same object as it was before clearing, exits 0; names are restricted to `handoff-requested`, `cap-fired`, `park-requested`, `pause-requested`, `state-write-failed`; any other name exits 1.
- `statectl.py <state> decide --issue T --severity S --cycle N --action A --reason R [--type T]` appends an `autonomous_decisions` entry that passes `_validate_decision_entry`; a missing flag exits 1 naming it before any write.
- `statectl.py <state> get <path> --default <json>` prints the parsed default when the path is absent and exits 0; without `--default` the existing exit 1 stays.
- `_handoff` closes rows from artifacts as the Solution states; a row with no artifact still closes `lost` with today's detail.
- The brief line is present in every rendered brief.
- The `handoff-requested` read at `skills/work/SKILL.md:456` names `autopilot markers --check`.
- The `cap-fired` clearing described at `skills/run-autopilot/references/phase-build.md:96-97` names `autopilot markers --clear`.
- The `autonomous_decisions` append at `skills/run-autopilot/references/phase-review.md:145` uses `statectl.py decide`.
- CHANGELOG `[Unreleased]` Added entry under **run-autopilot** and one under **work**.

### Nice to have
- None.

## Implementation

### Module: markers-verb
- **Location**: `skills/run-autopilot/cli/__main__.py`, `skills/run-autopilot/cli/markers.py`
- **Responsibility**: check and clear the autopilot-dir markers idempotently
- **Exports**: `check_markers()`, `clear_markers()`
- New symbols: `markers.py`, `check_markers`, `clear_markers`

### Module: statectl-verbs
- **Location**: `skills/run-autopilot/scripts/statectl.py`
- **Responsibility**: the `decide` verb and `get --default`
- **Exports**: `do_decide()`
- New symbols: `do_decide`

### Module: dispatch-closure
- **Location**: `skills/work/scripts/record_dispatch.py`
- **Responsibility**: close open rows from commits and review artifacts at handoff
- **Exports**: `open_ids()` (unchanged)
- New symbols: `close_from_artifacts`

### Module: brief-line
- **Location**: `skills/run-autopilot/cli/brief.py`
- **Responsibility**: the tool line under the brief title
- **Exports**: `render_brief()` (unchanged)

### Module: friction-tests
- **Location**: `skills/run-autopilot/cli/test_markers.py`, `skills/run-autopilot/scripts/test_statectl_decide.py`, `skills/work/scripts/test_record_dispatch.py`, `skills/run-autopilot/cli/test_brief.py`, `skills/run-autopilot/scripts/test_friction_verbs_prose.py`
- **Responsibility**: pin each verb's contract and the prose sites
- **Exports**: none
- New symbols: `test_markers.py`, `test_statectl_decide.py`, `test_friction_verbs_prose.py`, `test_check_reports_absent_as_false`, `test_clear_is_idempotent`, `test_unknown_name_exits_1`, `test_decide_appends_a_valid_entry`, `test_decide_missing_severity_exits_1_before_write`, `test_get_default_prints_default_on_missing_key`, `test_get_without_default_still_exits_1`, `test_handoff_closes_ivan_row_from_task_commit`, `test_handoff_closes_tess_row_from_test_commit`, `test_handoff_closes_pat_row_from_review_artifact`, `test_handoff_still_marks_lost_without_artifact`, `test_brief_names_the_blocked_bash_commands`, `test_work_skill_checks_handoff_marker_by_verb`, `test_phase_build_clears_markers_by_verb`, `test_phase_review_appends_decisions_by_verb`

### Dependencies
- friction-tests: No dependencies (foundation)
- markers-verb: Depends on [friction-tests]
- statectl-verbs: Depends on [friction-tests]
- dispatch-closure: Depends on [friction-tests] (a sibling PRD adds a `retry` verb to the same file, different function)
- brief-line: Depends on [friction-tests]

## Tasks

### Phase 0: Foundation
- [ ] Write `skills/run-autopilot/cli/test_markers.py` (`test_check_reports_absent_as_false`, `test_clear_is_idempotent`, `test_unknown_name_exits_1`), `skills/run-autopilot/scripts/test_statectl_decide.py` (`test_decide_appends_a_valid_entry`, `test_decide_missing_severity_exits_1_before_write`, `test_get_default_prints_default_on_missing_key`, `test_get_without_default_still_exits_1`), add `test_handoff_closes_ivan_row_from_task_commit`, `test_handoff_closes_tess_row_from_test_commit`, `test_handoff_closes_pat_row_from_review_artifact`, `test_handoff_still_marks_lost_without_artifact` to `skills/work/scripts/test_record_dispatch.py`, and `test_brief_names_the_blocked_bash_commands` to `skills/run-autopilot/cli/test_brief.py`; register the two new files in a `[checks]` block of `dev/bin/release-checks` - Acceptance: `uv run --no-project --with pytest python -m pytest -q skills/run-autopilot/cli/test_markers.py skills/run-autopilot/scripts/test_statectl_decide.py skills/work/scripts/test_record_dispatch.py skills/run-autopilot/cli/test_brief.py` reports every new test failing at the task's base commit and no existing test failing; `rg -c 'test_markers.py|test_statectl_decide.py' dev/bin/release-checks` prints 2.

### Phase 1: Core
- [ ] Implement `markers.py` and the `markers` verb, `do_decide` and `get --default` in `statectl.py`, `close_from_artifacts` called from `_handoff` in `record_dispatch.py`, and the brief line in `render_brief` (depends on: Phase 0) - Acceptance: the Phase 0 command passes every test; `python3 skills/run-autopilot/cli/__main__.py markers --check handoff-requested cap-fired` prints `{"handoff-requested": false, "cap-fired": false}` in a fresh fixture dir.

### Phase 2: Integration
- [ ] Point the prose sites at the verbs: the `handoff-requested` read in `skills/work/SKILL.md` becomes `autopilot markers --check handoff-requested`, the marker clearing in `skills/run-autopilot/references/phase-build.md` describes `autopilot markers --clear handoff-requested cap-fired`, and the `autonomous_decisions` append in `skills/run-autopilot/references/phase-review.md` uses `statectl.py decide`; write `skills/run-autopilot/scripts/test_friction_verbs_prose.py` (`test_work_skill_checks_handoff_marker_by_verb`, `test_phase_build_clears_markers_by_verb`, `test_phase_review_appends_decisions_by_verb`), register it, and add the CHANGELOG entries (depends on: Phase 1) - Premise: `rg -c 'handoff-requested' skills/work/SKILL.md` prints at least 1 at execution time; skip and report otherwise - Acceptance: `uv run --no-project --with pytest python -m pytest -q skills/run-autopilot/scripts/test_friction_verbs_prose.py` passes; `rg -n 'autopilot markers' CHANGELOG.md` prints one hit under `[Unreleased]`.

## Success Criteria

- On the next batch, the session transcripts hold zero `cannot remove` or `cannot access` errors for the two marker names, zero `rejected: autonomous_decisions entry missing` errors, and `lost` rows for `ivan`, `tess` and `pat` fall below 10% of their rows in `dispatch-metrics.jsonl`.
- Every brief rendered by `statectl.py write-brief` contains the tool line.
