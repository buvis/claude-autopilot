# Review Context

## Completed Tasks

# Review task context

Standalone review: no canonical task store or autopilot state exists. Both PRD task checkboxes are complete.

| Task | Description | Commit |
|---|---|---|
| 1 | Guard target reads and stat; directory/read/race regressions. Folded with task 2. | ece9ac34053a17e9629e9af50355e7c84dc32fe2 |
| 2 | Guard repair write/replace/cleanup; error detail and read-only regressions; changelog. Folded with task 1. Rework covers orphan stat/unlink and helper extraction, guarded symlink status, exclusive temporary creation, and unique target rows. | ece9ac34053a17e9629e9af50355e7c84dc32fe2; 31fe06b59973374da818a116ec4b3606845049d6; 6906a89bff8f0cf8067b61628844561d94553a5f |

## Code Changes

### Changed Files
_Diff scope: incremental review (changes since 31fe06b59973374da818a116ec4b3606845049d6)_

```
 CHANGELOG.md                                       |   2 +-
 skills/use-codex/scripts/codex_hook_doctor.py      |  29 ++++--
 .../scripts/test_codex_hook_doctor_parse_errors.py | 111 +++++++++++++++++++--
 3 files changed, 124 insertions(+), 18 deletions(-)
```

### Diff Content
Full diff available at: /Users/bob/git/src/github.com/buvis/claude-autopilot/dev/local/tmp/review-diff-00176-03.diff

(228 lines)

## PRD Requirements

---
catchup: skip
design: skip
default_model: sonnet
model_tier_rationale: guards at named call sites with the verdict pinned; additive fail-first tests
---

# Guard the target reads in the doctor

Source: PRD 00173's review cycle 1 — Blake's residual-unguarded-operations finding and Eve's first KNOWN item, both against `dev/local/reviews/00173-guard-the-canonical-read-in-the-doctor-verdict-v1-review-1.md`. Filed 2026-09-05. This is the next layer of the onion PRD 00169 → 00173 has been peeling: 00169 guarded the import scan, 00173 guarded the canonical reads, and the target-side reads are what remain.

## Overview

### Problem Statement

`skills/use-codex/scripts/codex_hook_doctor.py` still aborts the whole run with exit 2 and no TSV rows when a **target** (rather than a canonical) cannot be read. Three unguarded paths remain, all confirmed by reading, one confirmed live:

1. `_verdict_for` compiles the target with `compile(target.read_bytes(), ...)`. `read_bytes()` raises `OSError` when the target is a directory or is unreadable. `check` collects targets from `hooks_dir.glob("*.py")`, and **glob matches directories**, so a directory literally named `something.py` under `hooks/` aborts the run. Confirmed live during the 00173 review: `error: [Errno 21] Is a directory: .../hooks/x.py`, exit 2.
2. `_verdict_for`'s staleness comparison reads the target a second time (`canonical_bytes != target.read_bytes()`). Same exposure, and it is a second read of a file that may have changed since the first.
3. `_repair_known`'s write path (`tmp_path.write_bytes(canonical_bytes)` then `os.replace(tmp_path, target)`) is unguarded. A read-only hooks directory, a full disk, or a permission change between check and write raises `OSError` out of `repair`: exit 2, and any targets not yet processed get no row at all.

`_verdict_for` also calls `target.stat()` right after `target.exists()`. That is a check-then-act window: a target removed between the two calls raises `OSError` from `stat()`.

The batch codex health probe reads this exit code. Exit 2 means "the doctor itself could not run", so one broken file on the host currently masks the verdict of every other hook.

### Target Users

The operator running `repair` against a damaged plugin cache, and the batch codex health probe reading the doctor's exit code.

### Success Metrics

- A target that is a directory, or unreadable, yields one row for that target and the run exits 1 or 3, never 2.
- A repair whose write fails yields `unrepairable` for that target, still processes every remaining target, and never exits 2.
- A target deleted between `exists()` and `stat()` is verdicted, not raised.
- Every existing verdict string and `_report`'s counting stay unchanged; `skills/use-codex/SKILL.md`'s exit-code list needs no edit.

## Functional Decomposition

### Capability: Doctor verdicts

#### Feature: An unreadable target verdicts itself
- **Description**: a target that exists but cannot be read verdicts that one target instead of aborting the run.
- **Inputs**: a target whose `read_bytes()` or `stat()` raises `OSError` — a directory, a permission-denied file, or one removed mid-run.
- **Outputs**: a `syntax_error` verdict for that target with the `OSError` text in the detail; exit 1 or 3 through `_report`'s existing counting.
- **Behavior**: guard both `target.read_bytes()` calls and the `stat()` in `_verdict_for`, mapping `OSError` to `syntax_error` with the `OSError` text as the detail. No new verdict string: `syntax_error` already carries a detail and gates the rung off, which is the safe direction for a hook that cannot be read.

#### Feature: A failed write costs one row, not the run
- **Description**: an `OSError` from the repair write is reported for that target and does not stop the remaining targets.
- **Inputs**: a hooks directory that is read-only, full, or whose permissions changed after the check.
- **Outputs**: `unrepairable` for that target with the `OSError` in the detail; every other target still processed.
- **Behavior**: guard `tmp_path.write_bytes(...)` and `os.replace(...)` in `_repair_known`, and remove the temp file if it was created before the failure, so a failed repair leaves no `.tmp` litter beside the hook.

## Structural Decomposition

### Repository Structure

```
skills/use-codex/scripts/codex_hook_doctor.py                  # Maps to: both features
skills/use-codex/scripts/test_codex_hook_doctor_parse_errors.py  # Maps to: regression tests (the other three doctor test modules are at 772/789/795 against the 800-line limit)
CHANGELOG.md
```

### Module: hook-doctor
- **Maps to capability**: Doctor verdicts
- **Responsibility**: the guarded target reads and the guarded repair write.
- **Exports**: none new (`_verdict_for` and `_repair_known` keep their signatures)

## Dependency Graph

### Foundation Layer (Phase 0)
No dependencies.

- **hook-doctor**: the guarded target reads and write.

## Implementation Phases

### Phase 0: Guard the target paths
**Goal**: no host file can abort the doctor with exit 2.

**Tasks**:
- [x] Guard both `target.read_bytes()` calls and the `stat()` in `_verdict_for`, mapping `OSError` to `syntax_error` with the `OSError` text as the detail; one fail-first test using a directory named `*.py` under `hooks/` asserting `check` never exits 2 (no deps) - Acceptance: `uv run --no-project --with pytest python -m pytest -q skills/use-codex/scripts` green with the new test present, and the test fails against the pre-change module.
- [x] Guard `tmp_path.write_bytes` and `os.replace` in `_repair_known`, cleaning up a partial `.tmp`; one fail-first test with a read-only hooks directory asserting the other targets still get rows (depends on task 1); CHANGELOG `**use-codex**` under Fixed - Acceptance: suite green; `bash dev/bin/release-checks` green.

**Exit Criteria**: suite green; `bash dev/bin/release-checks` green.

## Test Strategy

### Critical Scenarios
- **Happy path**: a readable stale target with a readable canonical → Expected: `repaired`, unchanged from today.
- **Edge case**: a directory named `x.py` under `hooks/` → Expected: one row for it, exit 1 or 3, never 2, and every other target still verdicted.
- **Error case**: a read-only hooks directory during repair → Expected: `unrepairable` for the target that could not be written, rows for all others, no leftover `.tmp` file, never exit 2.

## Risks

- A test that makes a directory read-only must restore its mode in teardown, or it leaves an undeletable `tmp_path` behind and poisons later runs. Use a fixture with explicit cleanup; skip the case when running as root, where mode bits do not deny.
- Mapping target `OSError` onto `syntax_error` widens what that verdict means; the detail column carries the `OSError` text, and the code comment records why no new verdict was added (a new string would touch `_report`'s counting and `SKILL.md`'s exit-code list).

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
  - `_repair_known` — line 184, 45 lines
  - `_write_repair` — line 231, 22 lines
  - `_repair_target` — line 255, 38 lines
  - `_remove_orphaned_empty` — line 295, 22 lines
  - `repair` — line 319, 38 lines
  - `_default_config` — line 359, 5 lines
  - `_default_aegis_root` — line 366, 4 lines
  - `_default_autopilot_root` — line 372, 2 lines
  - `_build_parser` — line 376, 13 lines
  - `_resolve_roots` — line 391, 13 lines
  - `_run_subcommand` — line 406, 21 lines
  - `_report` — line 429, 21 lines
  - `main` — line 452, 20 lines
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
  - `readonly_hooks` — line 205, 13 lines
  - `test_readonly_repair_reports_all_targets_without_tmp_litter` — line 220, 22 lines
  - `test_failed_repair_cleans_tmp_and_repairs_next_target` — line 245, 46 lines
  - `test_failed_repair_cleans_tmp_and_repairs_next_target.partial_open` — line 258, 11 lines
  - `test_failed_repair_cleans_tmp_and_repairs_next_target.partial_open.failed_write` — line 263, 3 lines
  - `test_failed_repair_cleans_tmp_and_repairs_next_target.failed_replace` — line 270, 4 lines
  - `test_cleanup_failure_is_reported_without_losing_remaining_rows` — line 293, 38 lines
  - `test_cleanup_failure_is_reported_without_losing_remaining_rows.failed_replace` — line 304, 4 lines
  - `test_cleanup_failure_is_reported_without_losing_remaining_rows.failed_unlink` — line 309, 4 lines
  - `test_orphan_cleanup_error_still_processes_next_target` — line 334, 35 lines
  - `test_orphan_cleanup_error_still_processes_next_target.failed_stat` — line 347, 4 lines
  - `test_orphan_cleanup_error_still_processes_next_target.failed_unlink` — line 352, 4 lines
  - `test_symlink_status_error_keeps_remaining_repair_rows` — line 371, 25 lines
  - `test_symlink_status_error_keeps_remaining_repair_rows.failed_is_symlink` — line 381, 4 lines
  - `test_repair_preserves_preexisting_temp_and_processes_next_target` — line 399, 30 lines
  - `test_dangling_orphan_gets_one_row_and_later_orphan_is_removed` — line 431, 29 lines

## Tautological test shapes (computed, do not re-judge)

Each `[MECH]` line is a test whose shape cannot fail as written. Raise
it; step 6 adds any line the table lacks. `mech-check` is the finder.


Checked 12 test function(s) in 1 test file(s).

## Fail-first replay (computed, do not re-judge)

Touched tests from HEAD, run against the pre-change code at `31fe06b59973`
(HEAD's test files overlaid on a base worktree). A test that passes there
does not pin this change. A behavior-preserving refactor's tests pass by
design, so weigh the PRD's intent before raising one. `mech-check` is the finder.

[MECH] 🟡 2 touched test(s) pass against the pre-change code: test_failed_repair_cleans_tmp_and_repairs_next_target | File: skills/use-codex/scripts/test_codex_hook_doctor_parse_errors.py | Task: general

Replay: 7 touched test(s) ran, 5 failed against base, 2 passed; 0 test file(s) could not be collected at base (their tests fail there). Command: uv run --no-project --with pytest python -m pytest
