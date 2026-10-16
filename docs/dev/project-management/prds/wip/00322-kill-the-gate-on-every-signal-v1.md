---
catchup: run
design: run
default_model: opus
model_tier_rationale: signal races measured at 68 leaks in 1500 trials; the fix removes a traceback walker and splits a shared deadline
---

# A killed verify or replay leaves no gate, runner or worktree behind

Source: hold stub 00319 (ledger key 8b3657b45a74, PRD 00311 cycle 2, HIGH 4/4); `docs/dev/project-management/audit-results/agoge-2026-10-15.md` packets 10, 11, 22. Line numbers below are from HEAD 807ed12b; PRD 00320 drains first and edits `verification.py` and `_run_verify`, so the symbols anchor and the numbers may have moved.

## Problem

Four leaks around the gate and the replay. (1) SIGINT during spawn: `_spawn_gate` (`skills/run-autopilot/cli/verification.py:500-540`) defers only SIGTERM through `_deferred_sigterm` (`skills/run-autopilot/cli/verification.py:465-480`); a KeyboardInterrupt inside the Popen call leaves `proc` unassigned, `_child_from_exception` (`skills/run-autopilot/cli/verification.py:483-497`) can recover a Popen whose pid is None, `_kill_gate` (`skills/run-autopilot/cli/verification.py:543-556`) then raises TypeError, masks the interrupt, and the forked gate survives while `run_gate`'s `finally` releases the flock; a second hole sits between Popen returning and the assignment. Measured: 68 leaked gates in 1500 trials (stub 00319). (2) SIGHUP is not deferred at all, and the loop's orphan sweep sends `SIGHUP` (`skills/run-autopilot/cli/loop.py:281`), so a swept `verify` leaves its gate running with the lock held for up to the gate's length; measured on a gate sleeping 8 s: `verify rc=-1`, gate alive, lock held, the next `verify` waited 7.5 s (packet 10). (3) The replay runner: `_run_in_worktree` (`skills/review-work-completion/scripts/replay_tests_against_base.py:100-147`) starts pytest with its own session, so a SIGTERM aimed at the caller's group misses it and skips the `finally` that removes the worktree; `_run_script` (`skills/run-autopilot/cli/review_stage.py:206-218`) calls the replay with no timeout and the replay's default of 600 s equals the Bash tool's maximum. Measured after a caller-group SIGTERM: runner and grandchild alive, two worktrees registered, a `replay-*` temp dir left behind; this is the mechanism behind the leaked runners 14557 and 28178 seen live (packet 11). (4) The lock wait and the gate share one deadline (`run_gate`, `skills/run-autopilot/cli/verification.py:559-605`): a waiter that gets the lock late has little time left and its result says `timed_out: true` with nothing about the wait; measured with the lock held 3 s and a 4 s timeout on a 2 s gate: `wall=4.00s lock_timeout=False timed_out=True`; at `GATE_TIMEOUT_S` (`skills/run-autopilot/cli/verification.py:49`) and a 293 s gate, the sixth queued `verify` would be killed 42 s into its gate (packet 22).

## Solution

One deferral guard for every catchable signal, no traceback walking, and a separate lock budget. `_SigtermGuard` becomes `_SignalGuard`, installed by `_deferred_signals` for SIGTERM, SIGINT and SIGHUP with the same handler (record before the gate starts, raise once it has); `_child_from_exception` and `_POPEN_TYPE` are deleted; `_spawn_gate` assigns `proc` from Popen inside the guarded region and `_kill_gate` only ever receives a real Popen. `_run_verify` catches the guard's exception, prints `{"error": "verify: <SIGNAME> during gate", "exit": 2, "log": <path or null>}` and returns 2 (no traceback). The replay installs the same kind of handler, `_raise_on_signal`, for SIGTERM and SIGHUP: the exception lands inside `_run_in_worktree`, its except branch kills the runner's process group with SIGKILL, and the `finally` removes the worktree and temp dir as it does today; `_run_script` bounds every helper script with `timeout=SCRIPT_TIMEOUT_S` (540) and reports `_<script> failed (timeout after 540s)_` on expiry, and `_append_mech_blocks` passes `--timeout 480` to the replay. `run_gate` gains `lock_timeout: float = GATE_LOCK_TIMEOUT_S` (600): `_acquire_lock` is bounded by it, the gate deadline is computed when the lock is acquired, and the result carries `waited_s` (seconds spent waiting for the lock) in every shape, including `_lock_timeout_result()`.

## Requirements

### Must have
- SIGINT, SIGTERM or SIGHUP delivered to `verify` at any point from before the Popen call to after the reap kills the gate's process group and frees the flock (a non-blocking flock on the lock path succeeds within 1 s), and `verify` prints the one JSON line above and exits 2.
- `_child_from_exception` and `_POPEN_TYPE` no longer exist: `rg -c '_child_from_exception|_POPEN_TYPE' skills/run-autopilot/cli/verification.py` prints 0.
- 100 trials of SIGINT at random points of the spawn leak 0 gates (the storm test runs under 20 s); the existing `test_sigint_during_popen_leaves_the_gate_running` is replaced by `test_sigint_during_spawn_kills_the_gate`.
- A SIGTERM to the replay's process group leaves no runner, no grandchild, exactly one entry in `git worktree list`, and no `replay-*` temp dir.
- `_run_script` times every helper script out at `SCRIPT_TIMEOUT_S` and names the timeout in its block.
- `run_gate`'s result carries `waited_s`; a waiter that acquires the lock after N seconds still gets the full `timeout` for its gate; lock-wait expiry still returns `_lock_timeout_result()`.
- CHANGELOG `[Unreleased]` Fixed entries under **run-autopilot** and **review-work-completion**.

### Nice to have
- None.

## Implementation

### Module: gate-signals
- **Location**: `skills/run-autopilot/cli/verification.py` (`_SigtermGuard`, `_deferred_sigterm`, `_spawn_gate`, `_kill_gate`, `run_gate`, `_gate_under_lock`, `_acquire_lock`, `_lock_timeout_result`), `skills/run-autopilot/cli/__main__.py` (`_run_verify`)
- **Responsibility**: every catchable signal kills the gate group and frees the lock; the lock wait has its own budget
- **Exports**: `run_gate()` (new keyword `lock_timeout`)
- New symbols: `_SignalGuard`, `_deferred_signals`, `GATE_LOCK_TIMEOUT_S`, `waited_s`

### Module: replay-signals
- **Location**: `skills/review-work-completion/scripts/replay_tests_against_base.py` (`_run_in_worktree`), `skills/run-autopilot/cli/review_stage.py` (`_run_script`, `_append_mech_blocks`)
- **Responsibility**: a signalled replay cleans up; no helper script outlives the tool limit
- **Exports**: `replay()` (unchanged)
- New symbols: `_raise_on_signal`, `SCRIPT_TIMEOUT_S`

### Module: signal-tests
- **Location**: `skills/run-autopilot/cli/test_verify_truth.py`, `skills/review-work-completion/scripts/test_replay_timeout_kill.py`, `skills/run-autopilot/cli/test_review_stage.py`
- **Responsibility**: pin each signal path and the lock budget
- **Exports**: none
- New symbols: `test_sigint_storm_leaks_no_gate`, `test_sighup_kills_the_gate_group_and_frees_the_lock`, `test_sigint_during_spawn_kills_the_gate`, `test_signal_exit_prints_one_json_line`, `test_group_sigterm_kills_runner_and_removes_worktree`, `test_run_script_times_out_and_says_so`, `test_late_waiter_gate_gets_full_timeout`, `test_result_reports_waited_s`

### Dependencies
- signal-tests: No dependencies (foundation)
- gate-signals: Depends on [signal-tests]
- replay-signals: Depends on [signal-tests]

## Tasks

### Phase 0: Foundation
- [ ] Add `test_sigint_storm_leaks_no_gate` (100 trials, asserting zero surviving gate pids), `test_sighup_kills_the_gate_group_and_frees_the_lock`, `test_sigint_during_spawn_kills_the_gate` (replacing `test_sigint_during_popen_leaves_the_gate_running`), `test_signal_exit_prints_one_json_line`, `test_late_waiter_gate_gets_full_timeout` (lock held 3 s, timeout 4 s, 2 s gate: `timed_out` false) and `test_result_reports_waited_s` to `skills/run-autopilot/cli/test_verify_truth.py`; add `test_group_sigterm_kills_runner_and_removes_worktree` to `skills/review-work-completion/scripts/test_replay_timeout_kill.py`; add `test_run_script_times_out_and_says_so` to `skills/run-autopilot/cli/test_review_stage.py` (a helper script that sleeps past a monkeypatched `SCRIPT_TIMEOUT_S` of 1) - Acceptance: `uv run --no-project --with pytest python -m pytest -q skills/run-autopilot/cli/test_verify_truth.py skills/review-work-completion/scripts/test_replay_timeout_kill.py skills/run-autopilot/cli/test_review_stage.py` reports each new test failing at the task's base commit and no existing test failing.

### Phase 1: Core
- [ ] Implement `_SignalGuard` and `_deferred_signals` in `skills/run-autopilot/cli/verification.py`, delete `_child_from_exception` and `_POPEN_TYPE`, assign `proc` inside the guarded region of `_spawn_gate`, add `GATE_LOCK_TIMEOUT_S`, `lock_timeout` and `waited_s` to `run_gate`, `_gate_under_lock` and `_lock_timeout_result`, and catch the guard's exception in `_run_verify` of `skills/run-autopilot/cli/__main__.py` (depends on: Phase 0) - Acceptance: `uv run --no-project --with pytest python -m pytest -q skills/run-autopilot/cli/test_verify_truth.py skills/run-autopilot/cli/test_verification.py` passes; `rg -c '_child_from_exception|_POPEN_TYPE' skills/run-autopilot/cli/verification.py` prints 0.

### Phase 2: Integration
- [ ] Add `_raise_on_signal` to `skills/review-work-completion/scripts/replay_tests_against_base.py` and the SIGKILL of the runner's group on that exception in `_run_in_worktree`; add `SCRIPT_TIMEOUT_S` to `skills/run-autopilot/cli/review_stage.py`, pass it in `_run_script` and `--timeout 480` in `_append_mech_blocks`; add the two CHANGELOG entries (depends on: Phase 1) - Acceptance: `uv run --no-project --with pytest python -m pytest -q skills/review-work-completion/scripts/test_replay_timeout_kill.py skills/run-autopilot/cli/test_review_stage.py` passes; `rg -n 'SIGHUP' CHANGELOG.md` prints one hit under `[Unreleased]`.

## Success Criteria

- The packet 10 probe (SIGHUP to `verify` mid-gate) leaves no gate pid and a free lock.
- The packet 11 probe (SIGTERM to the replay's group after 1 s) leaves one worktree and no `replay-*` temp dir.
- The packet 22 probe reports `timed_out: false` and `waited_s` of about 3.
- `rg -c '_child_from_exception|_POPEN_TYPE' skills/run-autopilot/cli/verification.py` prints 0.
