# Decision Audit Log: 00322-kill-the-gate-on-every-signal-v1

PRD: `00322-kill-the-gate-on-every-signal-v1.md`
Started: 2026-10-17T00:02:24Z
Completed: 2026-10-17T00:02:24Z
Autonomous: 20  |  Deferred: 19  |  Doubts: 0

### [autonomous] 2026-10-17T00:02:24Z

**Decision**: signal-handling gaps across the gate and replay runner, plus a shared lock/gate timeout

**Choice**: generalized the gate signal guard to SIGINT/SIGTERM/SIGHUP, added a matching two-phase guard to the replay runner, split the lock-wait and gate timeout budgets, and rewrote _run_script around a SIGTERM-then-grace-then-SIGKILL escalation

**Rationale**: matches the PRD solution symbol-for-symbol; 3 reviewer dispatches fixed 5 blockers inline (scope citation, pre-spawn/cleanup-reentry guard gaps, an outer-timeout re-leak, a dispatch-3 placement bug), none open at close

### [autonomous] 2026-10-17T00:02:24Z

**Decision**: Replay `_run_runner` re-delivers a signal recorded during cleanup with `os.kill(os.getpid(), ...)` after the handlers are restored. With the default disposition this kills the replay process before `_run_in_worktree`'s `finally` removes the worktree and temp dir, which is the leak this PRD closes. It also contradicts the design contract, which says a second signal during cleanup is "recorded and dropped". An orphan sweep that sends SIGHUP then SIGTERM hits this window. It applies to the TimeoutExpired and `_SignalRaised` branches alike. Fix: drop the re-delivery, or re-raise it only after the `finally` has run.

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-10-17T00:02:24Z

**Decision**: `test_signal_before_a_refusal_is_not_swallowed` passes against the pre-change code, per the fail-first replay block (2 of its 3 params pass at base), so it does not pin this change. Its `pytest.raises((_StraySignal, RuntimeError))` plus the conditional `if not isinstance(...)` assert is an either-or hedge. Pin the new `_SignalGuard` behaviour (the exact "verify: SIGTERM during gate" error), or drop the test.

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-10-17T00:02:24Z

**Decision**: `test_group_sigterm_kills_runner_and_removes_worktree` is 59 lines (mechanical facts), over the 50-line limit. Move the wait loop and the cleanup `finally` into helpers.

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-10-17T00:02:24Z

**Decision**: Starting helpers in a new session detaches them from the review-stage caller's process group. SIGTERM/SIGHUP to that caller now misses the helper, and `_run_script` has no interruption cleanup, leaving replay and its runner executing. Guard the helper lifecycle, forward termination, and wait for cleanup; test signaling the review-stage caller's group.

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-10-17T00:02:24Z

**Decision**: `_run_script` now starts helpers with `start_new_session=True` but installs no signal handling of its own. A SIGTERM or SIGHUP aimed at the review-stage caller's group no longer reaches the helper, which previously shared that group. A swept review stage therefore leaves the replay running for up to 480s. The replay's own guard only fires on a signal sent to the helper's own group. Fix: guard `_run_script` the same way, or document the accepted gap in the design.

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-10-17T00:02:24Z

**Decision**: In `_run_script`, `os.killpg(proc.pid, SIGTERM)` and the later SIGKILL are unguarded. If the helper exits between the `communicate` timeout and the `killpg` call, `ProcessLookupError` propagates. The design says "no exception propagates". `_kill_gate` and the replay both catch `ProcessLookupError` on the same idiom. Wrap both calls in `try/except ProcessLookupError`.

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-10-17T00:02:24Z

**Decision**: A signalled replay swallows the signal. It returns "killed by SIGTERM" as a skip reason, prints a "replay: skipped" block and exits 0, rather than terminating. The spec only requires cleanup, but a caller that sent SIGTERM sees a clean exit.

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-10-17T00:02:24Z

**Decision**: A signal recorded during `_spawn_gate` cleanup after a non-signal error, such as a log-sink OSError, is silently dropped. `_SignalGuard.handle` records it and nothing re-raises it, so a SIGINT in that window is lost.

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-10-17T00:02:24Z

**Decision**: Between the end of `_reap` and the end of the `with` block, a signal still raises. `_kill_gate` then runs `killpg` on an already-reaped pid. `ProcessLookupError` is caught, but pid or group reuse is theoretically possible.

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-10-17T00:02:24Z

**Decision**: Both timeout `killpg` calls can raise `ProcessLookupError` if the helper exits between timeout detection and signaling, aborting review staging instead of returning the timeout block. Catch that race at both calls and still drain/reap; add a deterministic regression.

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-10-17T00:02:24Z

**Decision**: ProcessLookupError not caught around os.killpg in _run_script during timeout escalation

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-10-17T00:02:24Z

**Decision**: Lock timeout message in _gate_result_line cites GATE_TIMEOUT_S (1800s) instead of new GATE_LOCK_TIMEOUT_S (600s)

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-10-17T00:02:24Z

**Decision**: Unspecified behavior added: `_run_script` sends SIGTERM and waits `SCRIPT_GRACE_S` (30 s, per CHANGELOG.md:100) before SIGKILL on timeout. The spec names no grace period or extra constant. It is arguably needed for the replay's handler to run, but it was not specified.

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-10-17T00:02:24Z

**Decision**: Two new tests are not where the PRD names them, so the PRD's acceptance commands do not run them. `test_run_script_times_out_and_says_so` is in skills/run-autopilot/cli/test_review_stage_run_script.py:114, not `test_review_stage.py`. `test_late_waiter_gate_gets_full_timeout` and `test_result_reports_waited_s` are in skills/run-autopilot/cli/test_verify_truth_lock.py:81, not `test_verify_truth.py`.

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-10-17T00:02:24Z

**Decision**: The run-autopilot CHANGELOG entry names SIGINT and SIGTERM but not SIGHUP, and does not mention the replay or `waited_s`.

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-10-17T00:02:24Z

**Decision**: R1 [3/4] HIGH: replay _run_runner re-delivers a cleanup signal with os.kill after restoring handlers, killing the process before _run_in_worktree finally removes the worktree and temp dir

**Choice**: auto-fix (rework task)

**Rationale**: Spec-compliance defect in this PRD own subject matter; the fix is a local change to the signal guard region, not a new dependency, data model or public API, so no research protocol applies

### [autonomous] 2026-10-17T00:02:24Z

**Decision**: R4 [1/4] HIGH: start_new_session=True detaches review-stage helpers from the caller process group, so SIGTERM/SIGHUP to the caller misses the helper and _run_script has no interruption cleanup

**Choice**: auto-fix (rework task)

**Rationale**: Same spec-compliance class as R1 and corroborated by Alice R5; the fix guards the helper lifecycle inside code this PRD already touches

### [autonomous] 2026-10-17T00:02:24Z

**Decision**: R2, R3, R5, R6, R7, R8, R9, R10, R12, R13 (medium) and R16, R17, R18 (low): tautological/either-or test, 59-line test function, unguarded _run_script signal and killpg races, swallowed replay signal, dropped cleanup signal, reaped-pid killpg, stale GATE_TIMEOUT_S message, unspecified SCRIPT_GRACE_S, misplaced tests, incomplete CHANGELOG entry

**Choice**: auto-fix (rework tasks 4-7)

**Rationale**: All are mechanical or additive fixes inside files this PRD already changed; medium and low never block convergence but are reworked here because the cycle is not converging on the two HIGHs

### [autonomous] 2026-10-17T00:02:24Z

**Decision**: Safety check: Bob first dispatch returned the lack-of-input refusal shape (codex sandbox_apply denied every read); engram context pack failed with a readonly-database error; Bob retry output arrived with issue lines nested under FIX/KNOWN behind a leading dash

**Choice**: logged and continued (graceful degradation)

**Rationale**: Bob one retry produced a real review via the inlined prompt, so the doubt lens did not drop; the pack failure leaves the review degraded not invalid; his format deviation was normalized mechanically per retry-policy Format Compliance since his retry budget was spent, and is flagged as a format warning in the review file

### [deferred] 2026-10-17T00:02:24Z

**Decision**: The supplied mechanical check identifies an either-or assertion that cannot fail as written. Replace it with the required single outcome in its owning maintenance task; the assertion predates this diff and is outside this signal/timeout PRD.

**Rationale**: deferred by review-close

### [deferred] 2026-10-17T00:02:24Z

**Decision**: test_skip_ceiling_fails_the_gate_above_three hedges with or: either outcome satisfies it

**Rationale**: deferred by review-close

### [deferred] 2026-10-17T00:02:24Z

**Decision**: File review_stage.py exceeds the 800-line limit (874 lines)

**Rationale**: deferred by review-close

### [deferred] 2026-10-17T00:02:24Z

**Decision**: Caller-signal cleanup in _run_script SIGKILLs the replay helper with no grace period (verification._kill_gate), so the replay's _raise_on_signal guard and its worktree-removal finally never run, and the pytest runner in its own session survives: a SIGTERM/SIGHUP to the review-stage caller during a replay still leaves the runner, grandchildren, a registered worktree and a replay-* temp dir. Fix: SIGTERM the helper group, wait SCRIPT_GRACE_S, then SIGKILL; add a caller-signal test on the real replay helper. (skills/run-autopilot/cli/review_stage.py:262)

**Choice**: deferred to batch end

**Rationale**: rework cap reached with this finding unresolved

### [deferred] 2026-10-17T00:02:24Z

**Decision**: The replay signal guard is installed only inside _run_runner, not around _run_in_worktree, so a signal during git worktree add / the overlay checkout / the rest of setup takes the default action and skips the finally, leaving a registered worktree and a replay-* temp dir. The new test only signals after the runner pids appear. (skills/review-work-completion/scripts/replay_tests_against_base.py:158)

**Choice**: deferred to batch end

**Rationale**: rework cap reached with this finding unresolved

### [deferred] 2026-10-17T00:02:24Z

**Decision**: CHANGELOG acceptance not met: rg -n 'SIGHUP' CHANGELOG.md prints two hits (lines 99 and 100 under [Unreleased]), not the required one; the review-work-completion entry also advertises an unspecified 30-second SIGTERM grace. (CHANGELOG.md:100)

**Choice**: deferred to batch end

**Rationale**: rework cap reached with this finding unresolved

### [deferred] 2026-10-17T00:02:24Z

**Decision**: Replay signal protection ends before worktree removal: a second SIGTERM/SIGHUP arriving during _run_in_worktree cleanup meets the restored default handler and terminates replay before removal completes. Keep the guard installed through worktree cleanup and synchronise the regression's second signal with removal. (skills/review-work-completion/scripts/replay_tests_against_base.py:189)

**Choice**: deferred to batch end

**Rationale**: rework cap reached with this finding unresolved

### [deferred] 2026-10-17T00:02:24Z

**Decision**: _run_script nests to 5 levels, over the 4-level limit; move the timeout escalation into a _terminate_with_grace(proc) helper, which also trims the 48-line function. (skills/run-autopilot/cli/review_stage.py:246)

**Choice**: deferred to batch end

**Rationale**: rework cap reached with this finding unresolved

### [deferred] 2026-10-17T00:02:24Z

**Decision**: test_main_exits_zero_on_a_plain_timeout_with_no_external_signal and test_main_exits_zero_on_normal_completion pass against the pre-rework code, and test_signal_before_a_refusal_is_not_swallowed still passes at base for two of three params: pin the new _SignalGuard behaviour or accept them as explicit negative controls. (skills/review-work-completion/scripts/test_replay_timeout_kill.py:390)

**Choice**: deferred to batch end

**Rationale**: rework cap reached with this finding unresolved

### [deferred] 2026-10-17T00:02:24Z

**Decision**: _kill_runner_pids duplicates the pid-kill half of _kill_driver_and_runner (and the two main-process tests repeat the driver-kill block); have _kill_driver_and_runner call it. The cycle also reformatted unrelated lines in the same file. (skills/review-work-completion/scripts/test_replay_timeout_kill.py:112)

**Choice**: deferred to batch end

**Rationale**: rework cap reached with this finding unresolved

### [deferred] 2026-10-17T00:02:24Z

**Decision**: Beyond-spec behaviour in the replay's main: it re-delivers the caught signal to itself via the global _stop_signum; the PRD only asks that the replay clean up and exit. (skills/review-work-completion/scripts/replay_tests_against_base.py:295)

**Choice**: deferred to batch end

**Rationale**: rework cap reached with this finding unresolved

### [deferred] 2026-10-17T00:02:24Z

**Decision**: test_run_script_times_out_and_says_so passes timeout=0.1 explicitly instead of monkeypatching SCRIPT_TIMEOUT_S as the PRD says (the default is bound at definition time), nothing pins the 540 default or _append_mech_blocks' reliance on it, and the message reads 'timeout after 0s'. (skills/run-autopilot/cli/test_review_stage_run_script.py:114)

**Choice**: deferred to batch end

**Rationale**: rework cap reached with this finding unresolved

### [deferred] 2026-10-17T00:02:24Z

**Decision**: Fail-first replay: 3 touched tests pass against the pre-change code, test_signal_before_a_refusal_is_not_swallowed among them, so they do not pin this change. (skills/run-autopilot/cli/test_verify_truth_lock.py:212)

**Choice**: deferred to batch end

**Rationale**: rework cap reached with this finding unresolved

### [deferred] 2026-10-17T00:02:24Z

**Decision**: _stop_signum is module-global state set in _run_runner, read in main() and never reset, so an in-process main() caller after a signal test would SIGTERM itself; nothing calls main() in-process today. (skills/review-work-completion/scripts/replay_tests_against_base.py:148)

**Choice**: deferred to batch end

**Rationale**: rework cap reached with this finding unresolved

### [deferred] 2026-10-17T00:02:24Z

**Decision**: test_timeout_kills_the_runner_process_group (1.5 s timeout) failed twice under concurrent load (FileNotFoundError on leader.pid) and passed in three later runs; the 1.5 s budget is the fragile part, not the rework logic. (skills/review-work-completion/scripts/test_replay_timeout_kill.py:148)

**Choice**: deferred to batch end

**Rationale**: rework cap reached with this finding unresolved

### [deferred] 2026-10-17T00:02:24Z

**Decision**: Cycle-1 R17 (new tests outside the files the PRD names) and cycle-1 R9 (signal between _reap and the end of the with block) are still open and were not touched by the rework. (N/A)

**Choice**: deferred to batch end

**Rationale**: rework cap reached with this finding unresolved

### [deferred] 2026-10-17T00:02:24Z

**Decision**: The new tests are not in the files the PRD names: test_late_waiter_gate_gets_full_timeout and test_result_reports_waited_s live in test_verify_truth_lock.py, test_run_script_times_out_and_says_so in test_review_stage_run_script.py, so the PRD's acceptance command does not run them. (skills/run-autopilot/cli/test_verify_truth_lock.py:82)

**Choice**: deferred to batch end

**Rationale**: rework cap reached with this finding unresolved

### [deferred] 2026-10-17T00:02:24Z

**Decision**: A signal landing after the replay's inner try completes but before the with exits sees spawned=True and cleaning=False, so _SignalRaised is raised outside the except and leaves an uncaught traceback out of main (cleanup still runs). (skills/review-work-completion/scripts/replay_tests_against_base.py:158)

**Choice**: deferred to batch end

**Rationale**: rework cap reached with this finding unresolved

### [deferred] 2026-10-17T00:02:24Z

**Decision**: test_timeout_kills_the_runner_process_group failed once in a combined run of the six PRD test files (109 passed, 1 failed, leader.pid never written) and passed 10 of 10 alone; load flakiness, not attributed to this change. (skills/review-work-completion/scripts/test_replay_timeout_kill.py:160)

**Choice**: deferred to batch end

**Rationale**: rework cap reached with this finding unresolved
