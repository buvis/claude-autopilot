---
catchup: run
design: run
default_model: opus
model_tier_rationale: a classifier whose failure modes all point toward "not a regression", measured on its own review pair; the ledger and stub routing touch three modules
---

# cap-check classifies every File cell, proves its range and records what it parks (v2)

Source: hold PRD 00310 v1 (parked 2026-10-15 13:28 by its own `cap_regression` stall; its code is on master and claimed on CHANGELOG line 19); `docs/dev/project-management/reviews/00310-park-cap-regressions-v1-review-2.md` R1, R5, R6, R7, R8; `docs/dev/project-management/audit-results/agoge-2026-10-15.md` packets 3 (HIGH), 4, 5, 21, 23, 27.

## Problem

`autopilot cap-check` decides at a loop-mode cap-out whether a remaining HIGH stalls the PRD or is deferred. As shipped it fails toward "not a regression" in six ways. (a) `_split_file_line` (`skills/run-autopilot/cli/cap_check.py:64-68`) applies `_FILE_LINE_RE` (`skills/run-autopilot/cli/cap_check.py:17`) to the whole File cell, so a cell with two paths, a range, backticks, `#L<n>`, `:L<n>`, `a.py: 3`, a case variant or a trailing `(note)` is taken as one path or one line, and git's "no such path" is then read as not-a-regression: on 00310's own review pair the verb exits 1 but reports R5's cell `skills/run-autopilot/references/phase-review.md:59, skills/run-autopilot/cli/triage.py` as `"regression": false` while R6 on the same line is `"regression": true, "commit": "8b3a58f2"`, so the live stall detail "Non-regression highs still open: R5, R8" is wrong about R5; on a fixture whose rework adds line 4 of one file, a cell naming that file and a second one, the same two in the other order, a two-line range ending before line 4, the file name wrapped in backticks, the hash-L and colon-L line forms, a space after the colon, an upper-case spelling of the name, and a trailing parenthesised note all exit 0 (packet 3). (b) `_add_cap_check` (`skills/run-autopilot/cli/__main__.py:890-894`) defaults `--repo-root` to the cwd and the cap-out prose calls the verb without it, so from a subdirectory every row reads false and the verb exits 0 (packet 4). (c) The range is trusted from the two `head_sha` lines: `_head_sha` (`skills/run-autopilot/cli/cap_check.py:31-37`) accepts any 4-40 hex string through `_SHA_RE` (`skills/run-autopilot/cli/cap_check.py:18`), so an equal, reversed or branch-named value (a branch named beef, later moved to the base commit) turns a stall into a deferral (packet 5). (d) `_file_exists_at` (`skills/run-autopilot/cli/cap_check.py:117-122`) swallows every `CapCheckError`, and `_missing_path_error` (`skills/run-autopilot/cli/cap_check.py:71-76`) searches the whole message including the command text, so a filename containing "does not exist" hides a real git failure (R7). (e) An absolute in-repository path never matches the changed-file set and an annotated cell bypasses blame (R8); (f) `classify_findings` (`skills/run-autopilot/cli/cap_check.py:155-194`) reads `git diff --name-only` without `-z`, so a non-ASCII filename comes back quoted and never matches (R1). And the stall records nothing: the cap-out bullet at `skills/run-autopilot/references/phase-review.md:59` says the `cap_regression` path captures no custody and mints no stub, `qualifies` (`skills/run-autopilot/cli/triage.py:156-162`) accepts a stall row only at `CUSTODY_SITE` (`skills/run-autopilot/cli/custody.py:29`), and the `cap-overflow` records for the other unresolved rows are skipped because the Exit 1 branch precedes them, so the regressed HIGH reaches no ledger and no stub, the gap v1 set out to close (R5, R6). `skills/run-autopilot/references/recovery.md:101-108` tells the operator to resume "exactly like `cap_critical`", through a custody command that answers `no pending custody` for it (packet 27). A heavily rewritten rename blames unchanged lines to the rework (packet 23, a limit to document); the verb spawns one or two git processes per row (packet 21, accepted: 0.13 s on a real pair).

## Solution

Parse strictly, prove the range, fail toward stalling, and record. A new `_parse_file_cell` returns a list of (path, lines) pairs from one cell: split on `;` and on `,` whose next non-space character is not a digit; strip backticks, surrounding whitespace and a trailing parenthesised annotation; accept `path`, `path:N`, `path:LN`, `path#LN` and `path:A-B` (every line of the range is blamed); turn an absolute path under the toplevel into its repo-relative form; and when the exact spelling is absent from the changed-file set but exactly one case-insensitive match exists, use that spelling. A row is a regression when any pair is. A pair whose path git cannot resolve at `head` makes the row `{"regression": null, "reason": "unresolved path <p>"}`, and a null row counts toward exit 1: a cell the verb cannot read stalls, never defers. Every git call runs in `git rev-parse --show-toplevel` of `--repo-root`, the changed files come from `git diff --name-only -z` split on NUL, `_file_exists_at` re-raises everything but a missing path, and `CapCheckError` carries git's stderr separately so `_missing_path_error` inspects only that. Before any row is classified: both `head_sha` values are 40 hex, resolve with `git rev-parse --verify <sha>^{commit}`, differ, `git merge-base --is-ancestor <previous> <head>` holds and `<head>` is an ancestor-or-equal of HEAD; otherwise exit 2 naming the failing condition. The stall records: the cap-out prose appends the `cap-overflow` records for every unresolved row (all severities) to `state.deferred_decisions` first, then stalls with `site: cap_regression`; `do_stall` (`skills/run-autopilot/cli/records.py:507`) migrates those pending deferrals into the batch ledger for `cap_regression` exactly as it does for `cap_critical` (records under `<op_id>-dd<i>`); `qualifies` accepts a `cap_regression` stall row through a new `REGRESSION_SITE` constant, so the prose's `mint-stubs` call after the stall mints one stub titled from the stall detail; custody stays as v1 shipped it (no master reset). `recovery.md` gets the real resume steps (the PRD sits in `hold/`, its regressed rows are in the batch deferred JSON and its stub, fix on a branch or write a v2, move it back to `backlog/`, no custody command applies), and the cap-out bullet in `phase-review.md` names the rename limit.

## Requirements

### Must have
- Every cell shape in the Problem's fixture list classifies the row as a regression when any of its paths is; a cell with an unresolvable path yields `regression: null` with a `reason` and the verb exits 1.
- `cap-check` run with cwd in a subdirectory of the repo returns the same rows as from the toplevel.
- Equal, reversed, non-40-hex, unresolvable or non-descending `head_sha` pairs exit 2 with the condition named on stderr; a `head` not reachable from HEAD exits 2.
- `_file_exists_at` propagates a non-missing-path git failure as `CapCheckError`; `_missing_path_error` matches only git's stderr.
- A non-ASCII changed filename matches a file-only row.
- A `cap_regression` stall migrates the PRD's pending deferrals into the batch ledger and `mint-stubs` mints a stub for it; the cap-out prose writes the `cap-overflow` records for every unresolved row before the stall.
- `recovery.md` carries the real resume steps for `cap_regression`; `phase-review.md` names the rename limit.
- CHANGELOG `[Unreleased]` Fixed entry under **run-autopilot**.

### Nice to have
- `autopilot render report` prints `stalled: cap_regression` in the PRD's section, pinned by a test.

## Implementation

### Module: cap-check-parser
- **Location**: `skills/run-autopilot/cli/cap_check.py` (`_split_file_line`, `_classify_row`, `classify_findings`, `_head_sha`, `_git`, `_file_exists_at`, `_missing_path_error`, `CapCheckError`), `skills/run-autopilot/cli/__main__.py` (`_add_cap_check`, `_run_cap_check`)
- **Responsibility**: read every cell, prove the range, run git from the toplevel, fail toward stalling
- **Exports**: `classify_findings()`, `rework_range()`
- New symbols: `_parse_file_cell`, `_verify_range`, `_toplevel`

### Module: cap-regression-records
- **Location**: `skills/run-autopilot/cli/triage.py` (`qualifies`), `skills/run-autopilot/cli/records.py` (`do_stall`), `skills/run-autopilot/references/phase-review.md`, `skills/run-autopilot/references/recovery.md`
- **Responsibility**: a `cap_regression` stall leaves a ledger record and a stub, and the operator can follow the resume steps
- **Exports**: `qualifies()`, `do_stall()` (unchanged signatures)
- New symbols: `REGRESSION_SITE`

### Module: cap-check-tests
- **Location**: `skills/run-autopilot/cli/test_cap_check.py`, `skills/run-autopilot/cli/test_triage.py`, `skills/run-autopilot/scripts/test_cap_regression_prose.py`, `skills/run-autopilot/cli/test_records_stall.py`
- **Responsibility**: pin every cell shape, the range proof, the cwd independence, the stderr-only missing-path rule, the ledger migration, the stub and the prose
- **Exports**: none
- New symbols: `test_multi_path_cell_is_regression_when_any_path_is`, `test_range_cell_blames_every_line`, `test_backtick_hash_l_and_colon_l_shapes_parse`, `test_annotated_cell_is_parsed_without_its_note`, `test_absolute_in_repo_path_is_normalised`, `test_case_variant_path_matches_its_one_changed_file`, `test_unresolved_path_counts_as_a_stall`, `test_non_ascii_changed_file_matches`, `test_subdirectory_cwd_classifies_the_same_rows`, `test_equal_or_reversed_head_shas_exit_2`, `test_ref_name_head_sha_exits_2`, `test_blame_failure_propagates_from_file_exists_at`, `test_missing_path_detection_reads_stderr_only`, `test_cap_regression_stall_row_mints_a_stub`, `test_cap_regression_stall_migrates_pending_deferrals`, `test_cap_out_records_every_unresolved_row_before_the_stall`, `test_recovery_names_the_real_resume_steps`, `test_phase_review_names_the_rename_limit`

### Dependencies
- cap-check-tests: No dependencies (foundation)
- cap-check-parser: Depends on [cap-check-tests]
- cap-regression-records: Depends on [cap-check-tests]

## Tasks

### Phase 0: Foundation
- [ ] Extend the fixture of `skills/run-autopilot/cli/test_cap_check.py` (a rework that adds line 4 of `a.py`, renames nothing, and adds a file named `café.py`) and add the thirteen `test_cap_check.py` tests named under Implementation, each driving `classify_findings` or the CLI with the cell or `head_sha` shape it names; add `test_cap_regression_stall_row_mints_a_stub` to `skills/run-autopilot/cli/test_triage.py`; add `test_cap_regression_stall_migrates_pending_deferrals` to `skills/run-autopilot/cli/test_records_stall.py` (a state with two pending `deferred_decisions`, a `do_stall` at `site: cap_regression`, the batch ledger then holding the stall record and two `-dd` records); add `test_cap_out_records_every_unresolved_row_before_the_stall`, `test_recovery_names_the_real_resume_steps` and `test_phase_review_names_the_rename_limit` to `skills/run-autopilot/scripts/test_cap_regression_prose.py` - Acceptance: `uv run --no-project --with pytest python -m pytest -q skills/run-autopilot/cli/test_cap_check.py skills/run-autopilot/cli/test_triage.py skills/run-autopilot/cli/test_records_stall.py skills/run-autopilot/scripts/test_cap_regression_prose.py` reports every new test failing at the task's base commit and no existing test failing.

### Phase 1: Core
- [ ] Implement `_parse_file_cell`, `_verify_range` and `_toplevel` in `skills/run-autopilot/cli/cap_check.py`, the null-row exit rule in `_run_cap_check`, the `-z` diff, the stderr-carrying `CapCheckError`, and the re-raise in `_file_exists_at` (depends on: Phase 0) - Acceptance: `uv run --no-project --with pytest python -m pytest -q skills/run-autopilot/cli/test_cap_check.py` passes; `python3 skills/run-autopilot/cli/__main__.py cap-check --review-file docs/dev/project-management/reviews/00310-park-cap-regressions-v1-review-2.md --previous docs/dev/project-management/reviews/00310-park-cap-regressions-v1-review-1.md` exits 1 and its R5 row reads `"regression": true`.

### Phase 2: Integration
- [ ] Add `REGRESSION_SITE` to `skills/run-autopilot/cli/triage.py` and accept it in `qualifies`, extend `do_stall` in `skills/run-autopilot/cli/records.py` to migrate pending deferrals for that site, reorder the cap-out bullet in `skills/run-autopilot/references/phase-review.md` (records first, then the stall, then `mint-stubs`) and name the rename limit, write the resume steps in `skills/run-autopilot/references/recovery.md`, and add the CHANGELOG entry (depends on: Phase 1) - Premise: `rg -c 'cap_regression' skills/run-autopilot/references/recovery.md` prints at least 1 at execution time; skip and report otherwise - Acceptance: `uv run --no-project --with pytest python -m pytest -q skills/run-autopilot/cli/test_triage.py skills/run-autopilot/cli/test_records_stall.py skills/run-autopilot/scripts/test_cap_regression_prose.py` passes; `rg -n 'cap-check' CHANGELOG.md` prints two hits under `[Unreleased]`.

## Success Criteria

- On the 00310 review pair the verb exits 1 and classifies R5 and R6 both as regressions introduced by 8b3a58f2.
- Every cell shape from packet 3's fixture list exits 1; the plain, dot-slash and absolute-path controls still classify correctly.
- The packet 5 probes (equal, reversed, branch-named `head_sha`) exit 2.
- A `cap_regression` stall on a fixture state leaves a stall record and the migrated deferrals in the batch ledger and one minted stub under `prds/hold/`.
