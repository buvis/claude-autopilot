# PRD 00176 cycle 1 verification evidence

Reviewed HEAD: ece9ac34053a17e9629e9af50355e7c84dc32fe2
Explicit full-review base: 9336ab507525e13a685957a41b338561e74032fd

## Full project suite — independently run in review session

Command: `mise exec -- uv run --no-project --with pytest --with rich --with textual python -m pytest -q skills`

Exit 0. Summary: `2608 passed, 1 skipped, 4 warnings, 459 subtests passed in 79.14s (0:01:19)`.

Warnings, all from `skills/run-autopilot/cli/schema.py:199`:
- `ValidateBatchCompletedPrdsElementShapeTest::test_bare_string_entry_passes_legacy_tolerance`: `batch.completed_prds[0]: legacy bare-string entry '00001-x.md'`.
- `ValidateWidenedScalarFieldsTest::test_well_formed_widened_scalar_fields_pass`: same `00001-x.md` warning.
- `GoldenFixturesTest::test_all_golden_state_fixtures_validate_clean`: `batch.completed_prds[0]: legacy bare-string entry '00120-migrate-task-tracking-to-statectl-v1.md'`.
- The same golden-fixtures test: `batch.completed_prds[0]: legacy bare-string entry '00001-legacy-string-entry-v1.md'`.

The existing `last-verification.json` SHA is `57ed616f4022e5ab623a173924202b6ba8fb16fd`; it was not reused.

## Mechanical checks — independently run in review session

## Mechanical facts (computed, do not re-count)

Function line counts from `ast`. Cite these for countable claims; a
finding that contradicts this block is discarded at the review gate.

- `CHANGELOG.md` — skipped (non-python)
- `skills/use-codex/scripts/codex_hook_doctor.py`
  - `_iter_commands` — line 31, 8 lines
  - `_resolve_target` — line 41, 6 lines
  - `_verdict_for` — line 49, 43 lines
  - `_load_hooks` — line 94, 5 lines
  - `check` — line 101, 29 lines
  - `_missing_common_import_names` — line 132, 39 lines
  - `_repair_unknown` — line 173, 9 lines
  - `_repair_known` — line 184, 53 lines
  - `_repair_target` — line 239, 38 lines
  - `_remove_orphaned_empty` — line 279, 20 lines
  - `repair` — line 301, 37 lines
  - `_default_config` — line 340, 5 lines
  - `_default_aegis_root` — line 347, 4 lines
  - `_default_autopilot_root` — line 353, 2 lines
  - `_build_parser` — line 357, 13 lines
  - `_resolve_roots` — line 372, 13 lines
  - `_run_subcommand` — line 387, 21 lines
  - `_report` — line 410, 21 lines
  - `main` — line 433, 20 lines
- `skills/use-codex/scripts/test_codex_hook_doctor_parse_errors.py`
  - `test_bare_value_error_from_parse_marks_sibling_and_canonical_unreadable` — line 48, 23 lines
  - `test_bare_value_error_from_parse_marks_sibling_and_canonical_unreadable.fake_parse` — line 60, 4 lines
  - `test_check_directory_target_reports_error_and_remaining_rows` — line 73, 32 lines
  - `test_target_deleted_between_exists_and_stat_is_verdicted` — line 107, 21 lines
  - `test_target_deleted_between_exists_and_stat_is_verdicted.disappearing_exists` — line 116, 5 lines
  - `test_staleness_uses_the_target_bytes_that_compiled` — line 130, 24 lines
  - `test_staleness_uses_the_target_bytes_that_compiled.disappearing_read` — line 142, 5 lines
  - `unreadable_target` — line 157, 11 lines
  - `test_unreadable_target_is_verdicted` — line 170, 10 lines
  - `repair_targets` — line 183, 19 lines
  - `readonly_hooks` — line 205, 12 lines
  - `test_readonly_repair_reports_all_targets_without_tmp_litter` — line 219, 19 lines
  - `test_failed_repair_cleans_tmp_and_repairs_next_target` — line 241, 40 lines
  - `test_failed_repair_cleans_tmp_and_repairs_next_target.partial_write` — line 254, 5 lines
  - `test_failed_repair_cleans_tmp_and_repairs_next_target.failed_replace` — line 260, 4 lines
  - `test_cleanup_failure_is_reported_without_losing_remaining_rows` — line 283, 38 lines
  - `test_cleanup_failure_is_reported_without_losing_remaining_rows.failed_replace` — line 294, 4 lines
  - `test_cleanup_failure_is_reported_without_losing_remaining_rows.failed_unlink` — line 299, 4 lines

## Tautological test shapes (computed, do not re-judge)

Each `[MECH]` line is a test whose shape cannot fail as written. Raise
it; step 6 adds any line the table lacks. `mech-check` is the finder.


Checked 8 test function(s) in 1 test file(s).

## Fail-first replay (computed, do not re-judge)

Touched tests from HEAD, run against the pre-change code at `9336ab507525`
(HEAD's test files overlaid on a base worktree). A test that passes there
does not pin this change. A behavior-preserving refactor's tests pass by
design, so weigh the PRD's intent before raising one. `mech-check` is the finder.


Replay: 8 touched test(s) ran, 8 failed against base, 0 passed; 0 test file(s) could not be collected at base (their tests fail there). Command: mise exec -- uv run --no-project --with pytest python -m pytest


## Release checks — builder observed; independent review rerun blocked

Command: `mise exec -- env -u CODEX_SESSION_ID -u COPILOT_CLI -u AUTOPILOT_DISPATCH_DEPTH bash dev/bin/release-checks`.

Builder reports 224 passing checks on this unchanged HEAD. Review session's direct rerun exited 2 before checks could run: uv could not open `/Users/bob/.cache/uv/sdists-v9/.git` (Operation not permitted). The required escalation then remained pending for 432 seconds and was interrupted by the parent. Parent instructed no further release rerun this cycle. This report does not claim independent confirmation of those 224 checks.

Those three environment markers were removed only for hermetic stub CLI tests. They remained intact for real reviewer dispatch.

## Reviewer dispatch

Both `codex-run.sh` and `gemini-run.sh` returned exit 3: `refusing nested dispatch (already inside a CLI agent)`. No backend ran. Bob uses the mandatory native-subagent fallback; Carl has no completed review and is omitted from the reviewer count.

## Additive context pack

`engram pack --cycle 00176-01 ...` exited 1: `not inside a registered repo; register it in /Users/bob/.config/gita/repos.csv`. No registry changes were made. All applicable prompts received `(no pack available this cycle)`.

## Scope and cleanup

`git diff --check 9336ab507525e13a685957a41b338561e74032fd HEAD` passed. The replay removed its temporary worktree; `git worktree list` shows only the main checkout. Tracked content remained at the reviewed HEAD throughout this cycle.
