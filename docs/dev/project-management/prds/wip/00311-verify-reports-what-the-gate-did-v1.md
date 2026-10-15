---
catchup: run
design: run
default_model: opus
model_tier_rationale: passing the gate lock to the child and killing the group on a signal are invented expressions inside a runner pinned by the verification suites; the exit, record and label rules are exact
---

# Make `autopilot verify` report what the gate did

Source: `docs/dev/project-management/audit-results/agoge-2026-10-14.md` (packets 2, 3, 9, 19, 20, 21; all confirmed). Line numbers below are HEAD f6a99ab of 2026-10-14; PRD 00306 edits `_refuse_verify_log` and `_lock_and_check` first and shifts them, so the symbol names are the anchor.

## Problem

`_run_verify` (`skills/run-autopilot/cli/__main__.py:1007-1052`) takes the verb's exit from the gate process, so a gate run as `bash gate.sh | tee /dev/null` with a red suite prints `"failed": 1, "exit": 0, "recorded": true` and exits 0, and `skills/work/references/final-verification.md` tells the work phase that exit 0 means green and recorded. `_record_shape_ok` (`skills/run-autopilot/cli/verification.py:288-307`) accepts any record with a full sha, counts and a green command list, so the hand-written 0.9.0-era `last-verification.json` found live on 2026-10-14 (no `cycle` key, a one-line commands entry, the `Write` call in transcript ecc5d361) is reused by `reuse_verdict` (`skills/run-autopilot/cli/verification.py:317-364`) with invented counts, although CHANGELOG line 62 says `run_gate` is the only writer. `_run_locked_gate` (`skills/run-autopilot/cli/verification.py:551-603`) spawns the gate with `start_new_session=True` while `run_gate` (`skills/run-autopilot/cli/verification.py:605-657`) holds the flock; when the Python holder dies (SIGKILL 1.5 s into a 6 s gate, or SIGINT) the kernel drops the lock, nothing kills the gate's group, and a second `verify` runs its gate beside the orphan (the two tick traces interleaved). `run_gate` returns `_timed_out_result` (`skills/run-autopilot/cli/verification.py:423-435`) when it never got the lock and `_dirty_result` with no paths (`skills/run-autopilot/cli/verification.py:438-454`) when HEAD moved during the wait, so `run_gate_line` (`skills/run-autopilot/cli/review_stage.py:348-395`) prints "suite timed out after 1800s" for a lock-wait expiry and a dirty tree with no paths for a moved HEAD. A pre-spawn refusal returns the default log path, which still holds the previous run's output, and review-stage's dirty line names a log that does not exist. The store refusal in `_refuse_verify_log` (`skills/run-autopilot/cli/__main__.py:992-1004`) and the no-HEAD refusal print stderr only, while the OSError exit-2 path prints a JSON line.

## Solution

One rule per defect, all in code. The verb's exit comes from the parsed summary: 1 when `failed` is greater than 0 or the summary line's `EXIT` token is non-zero, whatever the process exited; the JSON keeps `exit` as the process exit. `_write_record` writes `"writer": "run_gate"` and `_record_shape_ok` refuses a record without it, so every hand-written or pre-upgrade record forces one rerun (CHANGELOG line 22 already promises that cost and now says a hand-written record never reuses). `_run_locked_gate` receives the lock fd, passes it to the child through `pass_fds` so an orphaned gate keeps the flock until it exits, and kills the gate's process group on any exception or signal (a SIGTERM handler installed for the gate's duration raises). `run_gate` results carry `lock_timeout` and `head_moved`, both False in every other result, and `timed_out` is True only for a gate killed at its deadline; `run_gate_line` prints one line per cause and carries `dirty_paths`. `_run_verify` prints `"log": null` when no gate spawned, and both stderr-only refusals also print `{"error": "<the stderr line>", "exit": 2}` on stdout. `final-verification.md` states the exit table.

## Requirements

### Must have
- `autopilot verify` exits 1 whenever the parsed `failed` is greater than 0 or the summary's `EXIT` token is non-zero, whatever the gate process exited; a gate printing `PASS 4 FAIL 1 SKIP 0 EXIT 1` and exiting 0 gives rc 1 with `"exit": 0` in the JSON. Exit 0 (green and recorded) and exit 3 (no summary, or mid-run dirt) keep today's meaning.
- `_write_record` writes `"writer": "run_gate"`; `_record_shape_ok` returns False for a record without `writer == "run_gate"`, so `reuse_verdict` returns stale for it; existing tests that build records by hand add the key deliberately, none is deleted.
- `_run_locked_gate` takes the lock fd, spawns with `pass_fds=(lock_fd,)`, wraps drain and reap in `try/except BaseException` that `os.killpg` the group with SIGKILL (a `ProcessLookupError` is tolerated) and re-raises, and installs a SIGTERM handler for the gate's duration that raises; the previous handler is restored in `finally`. A `verify` killed with SIGKILL mid-gate leaves a gate whose flock blocks the next `verify` until it exits; two gates never run at once.
- `run_gate` results carry `lock_timeout` (True only when the flock was not acquired by the deadline) and `head_moved` (True only when HEAD differed from `sha` after the lock); both keys are present and False in every other result shape, including `_timed_out_result` and `_dirty_result`.
- `run_gate_line` prints `Tests: (gate skipped: another gate held the lock for <timeout>s)` for `lock_timeout`, `Tests: (gate skipped: HEAD moved during the lock wait)` for `head_moved`, and its dirty line names the paths; the returned gate dict carries `dirty_paths`.
- `_run_verify` prints `"log": null` when the result has `exit` None and `timed_out` False (no gate spawned); the store refusal and the no-HEAD refusal print `{"error": "<the stderr line>", "exit": 2}` on stdout as well as the stderr line.
- `skills/work/references/final-verification.md` states: 0 green and recorded; 1 red (`failed` above 0 or `EXIT` non-zero), timed out, lock timeout, HEAD moved, or pre-spawn dirt; 2 refusal (one JSON line with `error`); 3 no summary or mid-run dirt.
- CHANGELOG line 22 says a record without the writer marker never reuses; `[Unreleased]` Fixed entries under **run-autopilot** for the exit rule, the writer marker, the orphan kill and the two labels.

### Nice to have
- None.

## Implementation

### Module: verify-exit
- **Location**: `skills/run-autopilot/cli/__main__.py` (`_run_verify`, `_refuse_verify_log`)
- **Responsibility**: the verb's exit and JSON tell the truth about the run
- **Exports**: `_run_verify()` (unchanged signature)

### Module: gate-runner
- **Location**: `skills/run-autopilot/cli/verification.py` (`_write_record`, `_record_shape_ok`, `_run_locked_gate`, `run_gate`, `_timed_out_result`, `_dirty_result`)
- **Responsibility**: a record is only ever the runner's, an orphaned gate cannot overlap the next one, and every refusal shape names its cause
- **Exports**: `run_gate()`, `reuse_verdict()` (unchanged signatures)
- New symbols: `_lock_timeout_result`, `_head_moved_result`, `lock_timeout`, `head_moved`, `pass_fds`

### Module: review-stage-lines
- **Location**: `skills/run-autopilot/cli/review_stage.py` (`run_gate_line`)
- **Responsibility**: one human line per gate outcome
- **Exports**: `run_gate_line()` (unchanged signature)

### Module: verify-truth-tests
- **Location**: `skills/run-autopilot/cli/test_verify_truth.py`
- **Responsibility**: pin the six reproductions from the agoge run as regression tests
- **Exports**: none
- New symbols: `test_verify_truth.py`, `test_red_summary_with_green_process_exits_1`, `test_hand_written_record_without_writer_is_never_reused`, `test_sigkilled_verify_leaves_no_overlapping_gate`, `test_sigterm_kills_the_gate_group`, `test_lock_wait_expiry_reports_lock_timeout`, `test_head_moved_reports_head_moved`, `test_pre_spawn_refusal_reports_null_log`, `test_exit_2_refusals_print_json`, `test_run_gate_line_names_lock_timeout_and_head_moved`

### Dependencies
- verify-truth-tests: No dependencies (foundation)
- gate-runner: Depends on [verify-truth-tests]
- verify-exit: Depends on [gate-runner]
- review-stage-lines: Depends on [gate-runner]

## Tasks

### Phase 0: Foundation
- [ ] Write `skills/run-autopilot/cli/test_verify_truth.py` against a fixture repo with a scripted gate: `test_red_summary_with_green_process_exits_1` (gate prints `PASS 4 FAIL 1 SKIP 0 EXIT 1`, exits 0; `verify` rc 1, JSON `exit` 0), `test_hand_written_record_without_writer_is_never_reused` (a green record lacking `writer` gives `reuse_verdict` stale; the same record with `writer: run_gate` reuses), `test_sigkilled_verify_leaves_no_overlapping_gate` (a 3 s gate appending timestamped ticks to a file; SIGKILL the `verify` subprocess at 0.5 s; start a second `verify` at once; the second's ticks all start after the first's last tick), `test_sigterm_kills_the_gate_group` (SIGTERM the `verify` subprocess; within 2 s no process of the gate's group is alive), `test_lock_wait_expiry_reports_lock_timeout` (hold the flock from the test; `run_gate(timeout=0.2)` returns `lock_timeout` True, `timed_out` False, no log created), `test_head_moved_reports_head_moved` (commit between lock and check through a patched `_acquire_lock`; `head_moved` True, `dirty` False), `test_pre_spawn_refusal_reports_null_log` (dirty tree; JSON `log` is null), `test_exit_2_refusals_print_json` (store `--log` and a repo with no commits; stdout holds one JSON line with `error` and `exit` 2), `test_run_gate_line_names_lock_timeout_and_head_moved` (patched `run_gate` results; the two `tests_line` strings and `dirty_paths` present). Register the file in a `[checks]` block of `dev/bin/release-checks` - Acceptance: `uv run --no-project --with pytest python -m pytest -q skills/run-autopilot/cli/test_verify_truth.py` reports every test failing at the task's base commit; `rg -c 'test_verify_truth.py' dev/bin/release-checks` prints 1.

### Phase 1: Core
- [ ] In `skills/run-autopilot/cli/verification.py`: `writer` in `_write_record` and `_record_shape_ok`; `_lock_timeout_result` and `_head_moved_result` returned by `run_gate` in place of the two misused shapes, with `lock_timeout` and `head_moved` False in `_timed_out_result` and `_dirty_result`; the lock fd passed into `_run_locked_gate` and through `pass_fds`; the `BaseException` kill-and-reraise around drain and reap; the SIGTERM handler installed and restored around the spawn. Add `"writer": "run_gate"` to every hand-built record in `skills/run-autopilot/cli/test_verification_log_sink.py`, `skills/run-autopilot/cli/test_verification_dirty.py`, `skills/run-autopilot/cli/test_verification_dirty_symlink.py`, `skills/run-autopilot/cli/test_verification_hidden_flags.py`, `skills/run-autopilot/cli/test_verification_dirty_paths.py` and `skills/run-autopilot/cli/test_cli_review_verbs.py` (depends on: Phase 0) - Acceptance: `uv run --no-project --with pytest python -m pytest -q skills/run-autopilot/cli/test_verify_truth.py skills/run-autopilot/cli/test_verification_log_sink.py skills/run-autopilot/cli/test_verification_dirty.py skills/run-autopilot/cli/test_verification_dirty_symlink.py skills/run-autopilot/cli/test_verification_hidden_flags.py skills/run-autopilot/cli/test_verification_dirty_paths.py skills/run-autopilot/cli/test_cli_review_verbs.py` passes with the record, lock and signal tests green and no test deleted (`rg -c '^def test_' skills/run-autopilot/cli/test_verification_dirty.py` unchanged from the task's base commit).
- [ ] In `skills/run-autopilot/cli/__main__.py`: `_run_verify` returns 1 on parsed red or a non-zero `EXIT` token, prints `"log": null` for a pre-spawn refusal, and both stderr-only refusals print the JSON error line (depends on: Phase 1 verification) - Acceptance: the Phase 0 command passes `test_red_summary_with_green_process_exits_1`, `test_pre_spawn_refusal_reports_null_log` and `test_exit_2_refusals_print_json`.

### Phase 2: Integration
- [ ] `run_gate_line` in `skills/run-autopilot/cli/review_stage.py` prints the lock-timeout and HEAD-moved lines and carries `dirty_paths`; `skills/work/references/final-verification.md` states the exit table; CHANGELOG line 22 reworded and the Fixed entries added (depends on: Phase 1) - Acceptance: the Phase 0 command passes `test_run_gate_line_names_lock_timeout_and_head_moved`; `rg -n 'lock timeout' skills/work/references/final-verification.md` prints one hit; `rg -n 'writer' CHANGELOG.md` prints a hit under `[Unreleased]`.

## Success Criteria

- The six reproductions in the Problem section flip: rc 1 for the piped red gate; stale for the hand-written record; no overlapping ticks after a SIGKILL; `lock_timeout` and `head_moved` named in JSON and in the review-stage line; `log` null and a JSON error line on the refusals.
- `test_verify_truth.py` is green and listed in `dev/bin/release-checks`.
