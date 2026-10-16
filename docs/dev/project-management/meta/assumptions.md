## 1: Add failing regression tests for every signal/timeout fix

- The `_run_script` tests live in a sibling file `test_review_stage_run_script.py`, not `test_review_stage.py`, because of the 800-line rule.
- The SIGINT-during-spawn test sends a real SIGINT with `os.kill` instead of raising `KeyboardInterrupt` directly. Only a real signal can reach the guard and produce `RuntimeError("verify: SIGINT during gate")`.
- The guard's signal set includes SIGINT, SIGTERM and SIGHUP, as the test names imply.
- The storm test also asserts that every trial whose gate recorded its pgid raised `RuntimeError("verify: SIGINT during gate")`. Each trial runs `run_gate` with `timeout=5`, a seeded RNG and a random delay of 0 to 0.08s.
- `waited_s` is tested on the timed-out result (lock held ~1s, gate timeout 0.5s, expected 0.8 <= waited_s < 1.4). The contract does not list the success-path result builder in `_record_gate` as gaining `waited_s`.
- The late-waiter test uses a 1.5s gate so that neither a 2s nor a 4s deadline shared with the lock wait would pass it.
- The timeout text is matched exactly: `_sleeper.py failed (timeout after 0s)_` for `timeout=0.1` and `_trapper.py failed (timeout after 2s)_` for `timeout=2`, with no ": detail" suffix. That implies integer formatting of the timeout.
- "No SIGKILL was needed" is shown by a marker that only a trapped SIGTERM writes, plus elapsed < 10s (the grace window is 30s).
- The SIGTERM exit-JSON test asserts `log == str(repo/"docs/dev/tmp"/f"gate-{head[:7]}.log")` and checks `error`, `exit` and `log` individually, so extra keys are allowed.
- The cleanup-SIGTERM wrapper sends the second SIGTERM before calling the original `_kill_gate`. It passes `*args, **kwargs` through because the target's `_kill_gate` signature isn't pinned.
- `test_sigterm_during_popen_kills_the_runner` does not pin whether `_run_in_worktree` raises `_SignalRaised` or returns. It asserts only that the signal didn't go unhandled, the runner group is dead and the worktree is removed.
- The `replay()` subprocess test isolates the system temp root with `TMPDIR`. `_repo(tmp_path, {...})` (from `test_replay_tests_against_base.py`) is used as the existing test uses it.
- (Strengthen pass) Appended the new sibling file `test_verify_truth_lock.py` to the mandated pytest command; otherwise its tests could not run.
- (Strengthen pass) Pinning the signature defaults (`lock_timeout=GATE_LOCK_TIMEOUT_S`, `timeout=SCRIPT_TIMEOUT_S`) and the values 600 and 540 is in-contract, because the PRD and design state those exact signatures.
- (Strengthen pass) The sibling `test_verify_truth_lock.py` defines its own copy of the `repo` fixture instead of importing it, to avoid ruff F811/F401 noise.
- (Strengthen pass) Devon's weak point 8 excludes SIGINT for the replay guard because PRD 00322 scopes `_raise_on_signal` to SIGTERM and SIGHUP only.

**Open note for task 2/3 implementors:** `dev/bin/release-checks` does not currently list `test_verify_truth_lock.py` or `test_review_stage_run_script.py` — registering them in the `[checks]` block may be needed so the release gate runs them (outside task 1's test-file-only allowlist). Also flagged: `test_run_gate_line_names_lock_timeout_and_head_moved` expects the lock-held message to quote `GATE_TIMEOUT_S` (1800s); now that the lock wait has its own 600s budget, that may need to change to `GATE_LOCK_TIMEOUT_S` — the PRD does not say which.

## 2: Generalize the gate's signal guard to SIGINT/SIGTERM/SIGHUP and split the lock/gate timeout budget

- The contract has `_dirty_result`, `_timed_out_result` and `_record_gate`'s dict all carrying `waited_s`, but those are called inside `_lock_and_check` and `_run_locked_gate`. So `waited_s` is passed into both functions as a new last argument, and `_run_locked_gate` adds it to `_record_gate`'s dict, rather than `_gate_under_lock` adding it itself. Each result still gets the field exactly once, from the one value measured in `_gate_under_lock`.
- `_deferred_signals` restores old handlers using what `signal.signal` returns, instead of calling `getsignal` first.

**Flagged (not fixed this cycle, Pat review — all LOW):** `_gate_under_lock` now takes 9 parameters (`lock_deadline`/`wait_start` could move inside it, computed from a passed-through `lock_timeout`); its docstring's new sentences read awkwardly spliced into the old list; `_spawn_gate`'s `except BaseException` sets `guard.cleaning = True` after entering the block, leaving a tiny window where a non-signal exception (e.g. a log-sink write error) racing a real signal could skip `_kill_gate`; `_deferred_signals` installs handlers outside its `try`, so a failing `signal.signal` call could leave earlier handlers unrestored, and restoring with a `None` previous handler would raise `TypeError` instead of falling back to `SIG_DFL`.
**Not done, needs someone else (from task 1):** `dev/bin/release-checks` still does not list `test_verify_truth_lock.py` or `test_review_stage_run_script.py`.

## 3: Guard the replay runner against every signal and make the helper-script timeout escalate gracefully

- A helper in the same file (`_run_runner`) was enough to split `_run_in_worktree` under the 50-line style limit, no sibling module needed.
- Re-send a pending signal (recorded during cleanup) with the caller's own handlers back in place, not with a temporary switch to the default action — this respects whatever the caller installed and lets `_run_in_worktree`'s `finally` still remove the worktree. The cost: if the caller's handler for that signal is "ignore", it gets ignored.
- The pending-signal check runs only when the signal-guard `with` block exits normally, not on the `except OSError` path (an OSError at Popen time means no runner ever started, so there is nothing pending to re-deliver).
- `_run_in_worktree`'s exact contract shape (now split into `_run_runner`) is treated as satisfied by the split, since the earlier style-fix commit only moved code and did not change its shape.

**Flagged (not fixed this cycle, Pat review — all LOW):** `_run_script`'s SIGTERM `killpg` call in `review_stage.py` is unguarded against `ProcessLookupError` (unlike `_run_runner`'s equivalent call); the "killpg, ignore ProcessLookupError, communicate" sequence is duplicated across `_run_runner` and `_run_script` rather than extracted into a shared helper; one f-string return line in `_run_runner` is long and hard to scan next to its neighbors.
