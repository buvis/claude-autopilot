# Review Context

## Completed Tasks

# Completed tasks

Standalone manual review: no state.json or canonical task store exists. The two checked PRD tasks and commit scope supply the table below; they do not substitute for independent verification.

| Task | Description | Commit |
|---|---|---|
| 1 | Guard target read_bytes calls and stat in _verdict_for; map OSError to syntax_error and cover directory targets with fail-first tests. Shared commit with task 2. | ece9ac34053a17e9629e9af50355e7c84dc32fe2 |
| 2 | Guard write_bytes and replace in _repair_known, clean partial temp files, preserve later rows; add regression tests and Fixed changelog entry. Shared commit with task 1. | ece9ac34053a17e9629e9af50355e7c84dc32fe2 |

## Code Changes

### Changed Files
_Diff scope: full PRD review, explicit authorized base 9336ab507525e13a685957a41b338561e74032fd (the gather script's --since selects this base; this is cycle 1)._

```
 CHANGELOG.md                                       |   1 +
 skills/use-codex/scripts/codex_hook_doctor.py      |  31 ++-
 .../scripts/test_codex_hook_doctor_parse_errors.py | 263 ++++++++++++++++++++-
 3 files changed, 285 insertions(+), 10 deletions(-)
```

### Diff Content
Full diff available at: /Users/bob/git/src/github.com/buvis/claude-autopilot/dev/local/tmp/review-diff-00176-01.diff

(361 lines)

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

## Architecture context

# Project Capsule: claude-autopilot

Generated: 2026-09-01

## Key Invariants

- This repo IS the `autopilot@buvis-plugins` skill pack's source. An autopilot
  batch drained *in this repo* executes the **marketplace-cached** install
  (`~/.claude/plugins/cache/buvis-plugins/autopilot/<version>`), not the
  checkout — nothing a PRD changes here is live until `dev/bin/release` +
  `/plugin update`. See memory `project-batch-runs-installed-cache`.
- Bob (codex reviewer) needs his prompt fully inlined (header + context + diff
  + PRD text in one file) — path references are unreadable in his sandbox. See
  memory `project-bob-codex-needs-inlined-prompt`.
- `enforce_prd_location.py` keeps `dev/local/prds/` lifecycle dirs canonical;
  a repo-root `backlog/`/`wip/`/`hold/`/`done/` reference is blocked.

## Architecture Decisions

- Ten skills drive a PRD lifecycle: catchup → design → plan-tasks → work →
  review-rework loop (consensus/blind/doubt lenses every cycle) → done.
- Fourteen agents: one implementor (`ivan`), thirteen reviewers across four
  lenses (consensus: alice/bob/carl; blind: blake; doubt: eve; dimensions:
  rita/cora/grace/toby/mallory/trent/victor/pat).
  bob (codex) and carl (gemini) dispatch to external CLIs; both refuse to
  recurse when already inside a CLI agent (`AUTOPILOT_DISPATCH_DEPTH` /
  host markers) — see README "Recursion guard".
- PRD 00164 (this batch's selection) added VERIFY-finding routing: a
  doubt-lens finding with an exact named check gets queued to
  `dev/local/reviews/{prd-stem}-checks-{cycle}.json` instead of becoming a
  task; `work` step 7 runs the queue inside its one mandatory verification
  pass and writes `dev/local/autopilot/last-verification.json`; the review's
  `Tests:` line reuses that record when its `sha` matches the reviewed HEAD.
  This collapses the "full suite runs up to 3x per cycle" duplication.

## Component Boundaries

- `skills/run-autopilot/cli/` is the sole `state.json` mutator surface
  (`statectl.py` + the `autopilot` subcommand CLI); skills invoke it rather
  than hand-editing state.
- `skills/work/references/final-verification.md` owns the verification
  procedure (suite run, queued checks, the recorded-result write); the
  review skill only *reads* `last-verification.json`, never writes it.

## Active Work

### Batch 202609011951
- [x] 00164-close-verify-findings-through-the-final-gate-v1 (0 cycles this
      batch — retroactive finalize; the work was already implemented, tested,
      changelogged and released as v0.3.0 in a prior session, the PRD file
      just never moved out of wip/)
- [x] 00161-doctor-codex-host-hooks-v1 (2 cycles)
- [x] 00160-route-opus-on-task-local-risk-v1 (2 cycles)
- [x] 00171-route-sonnet-prompt-through-stdin-v1 (1 cycle)
- [ ] 00173-guard-the-canonical-read-in-the-doctor-verdict-v1 (backlog)
- [ ] 00174-align-qwen-routing-with-single-file-trust-v1 (backlog)

Observations: PRD numbering here continues independently of the `~/.claude`
repo's sequence (same numbers across the two repos are not a collision).

## GitHub State

- 0 open issues, 0 open PRs.
- Only `origin`/`origin/master` active (both current, no stale branches).
- No tagged GitHub releases; CHANGELOG.md tracks versions instead (latest:
  0.3.0, 2026-09-01).
- No workflow runs found (no CI configured, or none has run).

## Project Health

CI: none configured/observed. Backlog has 3 PRDs (00160, 00161, 00168)
untouched. Working tree is clean on `master`.

## Project Memories

- `project-batch-runs-installed-cache`: batches here run the installed cache,
  need a release to take effect, must not write to `~/.claude`.
- `project-bob-codex-needs-inlined-prompt`: Bob's codex sandbox needs an
  inlined prompt, not path references.

## Verification independently run this cycle

Full suite: `mise exec -- uv run --no-project --with pytest --with rich --with textual python -m pytest -q skills` exited 0: 2608 passed, 1 skipped, 4 warnings, 459 subtests passed in 79.14s. The one skip is outside this diff. Release checks are pending independent verification.

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
