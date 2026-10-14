---
catchup: run
design: skip
default_model: sonnet
model_tier_rationale: every edit carries its exact expression; the fail-first tests pin the byte-identical file and the exit code
---

# Refuse a tracked or symlinked `verify --log` sink before opening it

Source: `docs/dev/project-management/audit-results/loop-efficiency-2026-10-13.md` (Q1), hold stubs 00295 and 00296.

## Problem

`autopilot verify --log <path>` opens the log sink for writing before the gate runs: `_run_locked_gate` (`skills/run-autopilot/cli/verification.py:551-568`) opens the path in write mode as its first act. The only refusal in front of it is `_refuse_verify_log` (`skills/run-autopilot/cli/__main__.py:992-1004`), which rejects a path inside the store and nothing else. Reproduced on HEAD 2026-10-13 against a scratch repo: `verify --gate-command "printf 'PASS 1 FAIL 0 SKIP 0\n'" --log src/app.py` on a clean tree exits 3 with `dirty: true, recorded: false`, and `src/app.py` now holds the gate output instead of its source line. The design for PRD 00276 required the tracked-path refusal; the cycle-1 rework removed it and changed the tests to require the overwrite; cycle 2 raised it HIGH and the rework cap deferred it.

`_log_rel_and_tracked` and `_untracked_log_exclusion` (`skills/run-autopilot/cli/verification.py:256-285`) already answer "is this path tracked" and are used only to decide the dirty-check exclusion.

The agoge run of 2026-10-14 (`docs/dev/project-management/audit-results/agoge-2026-10-14.md`, packets 7, 8, 18) found three more sinks the store refusal misses. On the default case-insensitive APFS, `--log docs/dev/Project-Management/autopilot/trudy-case.log` passes the `is_relative_to` string check and writes into the store (confirmed: exit 0, `recorded: true`, the file created beside `last-verification.json`). `--log .git/hooks/pre-push.sample` replaces the hook with gate output and keeps its exec bit, and `--log .git/config` leaves `git status` failing with `bad config line 1`, while the porcelain dirty check, which ignores `.git/`, still records green (confirmed). A FIFO sink blocks the `open(..., "wb")` forever inside the lock, so every later gate waits on it (confirmed, 10 s probe).

## Solution

Refuse before any byte is written, at both entry points. The CLI refuses (exit 2, stderr names the path and the reason) when the resolved log is inside the store or inside the git directory by file identity (the standard library's samefile check of each existing ancestor of the resolved path against the store directory and against the directories `git rev-parse --absolute-git-dir` and `git rev-parse --git-common-dir` print), is tracked in the git toplevel, is a symlink, resolves outside the toplevel, or names an existing target that is not a regular file (a FIFO, a device, a directory) or carries any executable bit. The identity check replaces the string `is_relative_to` check, so spelling and case no longer matter. The library `run_gate` refuses the tracked and symlink cases itself, returning the `_dirty_result` shape with the log's path as the one dirty path and `recorded: false`, before `_run_locked_gate` opens anything, so a library caller cannot bypass the CLI check. The untracked default sink under `docs/dev/tmp/` keeps working unchanged.

## Requirements

### Must have
- `_refuse_verify_log` refuses, exit 2, a `--log` that is tracked (`git ls-files --error-unmatch`), a symlink (`Path.is_symlink()` on the unresolved path), or outside the git toplevel, with one stderr line per cause: `autopilot: verify: --log <path> is tracked`, `... is a symlink`, `... resolves outside the repository` (guess: the exact wording).
- `_refuse_verify_log` refuses, exit 2, a `--log` whose resolved path has an existing ancestor that the samefile check matches to the store directory or the git directory (`... resolves inside the store`, `... resolves inside the git directory`), and one whose existing target is not a regular file or has an executable bit (`... is not a regular file`, `... is executable`); every refusal runs before `run_gate` is called, so no lock is taken and no file is opened.
- `_lock_and_check` (`skills/run-autopilot/cli/verification.py:534-548`) returns `_dirty_result([rel])` for a tracked or symlinked log before `_run_locked_gate` runs, using `_log_rel_and_tracked`; the sink file's bytes are unchanged afterwards.
- Fail-first regression tests that are red at the task's base commit and green after the fix.
- A CHANGELOG `[Unreleased]` Fixed entry under **run-autopilot**.

### Nice to have
- None.

## Implementation

### Module: verify-log-refusal
- **Location**: `skills/run-autopilot/cli/__main__.py` (`_refuse_verify_log`, `_run_verify`), `skills/run-autopilot/cli/verification.py` (`_lock_and_check`, `_log_rel_and_tracked`, `_dirty_result`)
- **Responsibility**: no `verify` run writes into a tracked or symlinked path
- **Exports**: `_refuse_verify_log()` (extended), `run_gate()` (unchanged signature)

### Module: verify-log-tests
- **Location**: `skills/run-autopilot/cli/test_verify_log_refusal.py`
- **Responsibility**: pin the eight refusal cases and the untracked-sink happy path against a fixture repo
- **Exports**: none
- New symbols: `test_verify_log_refusal.py`, `test_cli_refuses_tracked_log_and_leaves_bytes_intact`, `test_cli_refuses_symlinked_log`, `test_cli_refuses_log_outside_toplevel`, `test_cli_refuses_case_variant_store_path`, `test_cli_refuses_git_dir_log`, `test_cli_refuses_fifo_log`, `test_cli_refuses_executable_target`, `test_run_gate_refuses_tracked_log_without_opening`, `test_untracked_tmp_log_still_records`

### Dependencies
- verify-log-tests: No dependencies (foundation)
- verify-log-refusal: Depends on [verify-log-tests]

## Tasks

### Phase 0: Foundation
- [ ] Write `skills/run-autopilot/cli/test_verify_log_refusal.py` with a fixture repo (one committed source file, a committed ignore rule for docs/dev/tmp/) and these tests: `test_cli_refuses_tracked_log_and_leaves_bytes_intact` (exit 2, stderr contains `is tracked`, file bytes equal the committed bytes, `git status --short` empty), `test_cli_refuses_symlinked_log` (a symlink under docs/dev/tmp/ pointing at the source file: exit 2, target bytes intact), `test_cli_refuses_log_outside_toplevel` (`--log ../outside.log`: exit 2), `test_cli_refuses_case_variant_store_path` (`--log docs/dev/Project-Management/autopilot/x.log`: exit 2 and no file created; skipped with a reason when the case-variant directory does not exist on the test volume), `test_cli_refuses_git_dir_log` (parametrized over `.git/hooks/pre-commit` and `.git/config`: exit 2, bytes unchanged, `git status --short` still works), `test_cli_refuses_fifo_log` (an `os.mkfifo` sink under docs/dev/tmp/: exit 2 within 2 seconds, no reader attached), `test_cli_refuses_executable_target` (an existing mode-0755 file under docs/dev/tmp/: exit 2, bytes unchanged), `test_run_gate_refuses_tracked_log_without_opening` (library call with `log_path` = the tracked file: `recorded` false, `dirty_paths` names the file, bytes intact), `test_untracked_tmp_log_still_records` (default sink: `recorded` true). Register the file in a `[checks]` block of `dev/bin/release-checks` - Acceptance: `uv run --no-project --with pytest python -m pytest -q skills/run-autopilot/cli/test_verify_log_refusal.py` reports the eight refusal tests failing (or skipped, for the case-variant test on a case-sensitive volume) and the happy-path test passing at the task's base commit; `rg -c 'test_verify_log_refusal.py' dev/bin/release-checks` prints 1.

### Phase 1: Core
- [ ] Extend `_refuse_verify_log` in `skills/run-autopilot/cli/__main__.py` with the tracked, symlink, outside-toplevel, store-and-git-directory identity and non-regular-or-executable refusals (tracked via `verification._log_rel_and_tracked`; symlink via `Path.is_symlink()` on the pre-resolve path; outside via the `None` result of `_log_rel_and_tracked` when `--log` was given; identity via the samefile check over the existing ancestors of the resolved path against the store directory and the two `git rev-parse` directories; target via an lstat, the regular-file mode test and the `0o111` bits), and make `_lock_and_check` in `skills/run-autopilot/cli/verification.py` return `extra_excluded, _dirty_result([rel])` when `_log_rel_and_tracked` reports tracked or the path is a symlink (depends on: Phase 0) - Acceptance: `uv run --no-project --with pytest python -m pytest -q skills/run-autopilot/cli/test_verify_log_refusal.py skills/run-autopilot/cli/test_verification_dirty.py` passes with all five new tests green and no test of `test_verification_dirty.py` removed (`rg -c '^def test_' skills/run-autopilot/cli/test_verification_dirty.py` prints the same count as at the task's base commit).
- [ ] Add the CHANGELOG `[Unreleased]` Fixed entry `**run-autopilot**: \`autopilot verify --log\` refuses a tracked, symlinked, out-of-repo, store, git-directory, non-regular or executable sink before opening it, so a gate run can no longer overwrite committed source, git internals or a hook` (depends on: Phase 1 refusal) - Acceptance: `rg -n 'verify --log` refuses a tracked' CHANGELOG.md` prints one hit under `[Unreleased]`.

## Success Criteria

- The probe from the Problem section (clean tree, `--log src/app.py`) exits 2, prints `is tracked` on stderr, and leaves `src/app.py` byte-identical with `git status --short` empty.
- `--log docs/dev/Project-Management/autopilot/x.log` and `--log .git/config` each exit 2 and create or change no file; a FIFO sink exits 2 without blocking.
- `test_verify_log_refusal.py` is green and listed in `dev/bin/release-checks`.
