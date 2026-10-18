# Discovery: Replay and helper signal residue

## Classification
Depth: light | Date: 2026-10-18 | Status: pre-elicitation (triage of batch 202610161547's deferred findings on PRD 00322, no questions asked yet)

## Problem
PRD 00322 (kill the gate on every signal) capped out at cycle 2 with four
HIGHs and twelve Medium/Low findings unresolved. Verified at HEAD e8ca2f7 on
2026-10-18:

- HIGH, hold stub 00336 (ledger key 3a338afd1712, consensus 3/4): the
  caller-signal path of `_run_script`
  (`skills/run-autopilot/cli/review_stage.py:220-262`) ends in
  `verification._kill_gate(proc)` (line 262), which SIGKILLs the helper's
  process group (`skills/run-autopilot/cli/verification.py:646-654`) with no
  grace, while the timeout path of the same function sends SIGTERM, waits
  `SCRIPT_GRACE_S` and only then SIGKILLs (lines 247-251). A SIGTERM or
  SIGHUP to the review-stage caller during a replay therefore skips the
  replay's own `_raise_on_signal` guard and its worktree-removal `finally`,
  leaving the pytest runner, a registered worktree and a `replay-*` temp dir.
- HIGH, hold stub 00337 (557e1d62e8fd, 1/4): the replay's signal guard is
  installed only inside `_run_runner`
  (`skills/review-work-completion/scripts/replay_tests_against_base.py:158`),
  not around `_run_in_worktree` (line 189), so a signal during `git worktree
  add` or the overlay checkout takes the default action and skips the
  `finally` at line 221.
- HIGH, hold stub 00339 (470a046570d6, 1/4): the guard is restored before
  the worktree removal runs, so a second signal during cleanup terminates
  the replay before removal completes.
- HIGH, hold stub 00338 (61fe1a3ae2f0, 1/4): closed in this triage. The two
  `SIGHUP` CHANGELOG lines (114 and 115) describe two changes, `verify` and
  the replay, and the 30-second grace is now the named constant
  `SCRIPT_GRACE_S` (`review_stage.py:50`).
- Medium: `_run_script` nests five levels (a `_terminate_with_grace(proc)`
  helper would hold the escalation); two main-process tests and
  `test_signal_before_a_refusal_is_not_swallowed` pass against the
  pre-rework code; `_kill_runner_pids` duplicates half of
  `_kill_driver_and_runner`; the replay's `main` re-delivers the caught
  signal to itself through the module global `_stop_signum`, beyond the
  spec; `test_run_script_times_out_and_says_so` passes `timeout=0.1` instead
  of patching `SCRIPT_TIMEOUT_S` and prints `timeout after 0s`; three touched
  tests in `test_verify_truth_lock.py` pass at base.
- Low: `_stop_signum` is never reset; `test_timeout_kills_the_runner_process_group`
  is load-flaky on a 1.5 s budget (failed twice under concurrent load, once
  in a combined run); cycle-1 R17 and R9 untouched; new tests live outside
  the files the PRD names, so its acceptance command never runs them; a
  signal between the inner `try` and the `with` exit escapes as a traceback.

## Requirements (candidate, to be elicited)

### Must have
- F1: the caller-signal path of `_run_script` uses the same SIGTERM, grace,
  SIGKILL escalation as its timeout path, in one `_terminate_with_grace`
  helper, with a caller-signal test on the real replay helper that asserts
  no runner, worktree or temp dir survives.
- F2: the replay installs its guard once around the whole of
  `_run_in_worktree`, setup through cleanup, and a second signal during
  cleanup is recorded and dropped; the regression test signals during
  `worktree add` and during removal.
- F3: the flaky process-group test gets a budget that holds under load, or a
  synchronisation point instead of a sleep.

### Nice to have
- The Medium test-quality items (pin the `_SignalGuard` behaviour, patch
  `SCRIPT_TIMEOUT_S`, dedupe the kill helpers) in one tail task.

### Out of scope
- The replay's self-signal in `main` (beyond spec but harmless; decide in
  elicitation whether to keep it).

## Constraints
- Signal handling tests are timing-sensitive; the fast-track lane's one
  rework round may not fit a flaky test, so this may need the full lane.
- `default_model: opus` (signal races).

## Codebase Context
- `skills/run-autopilot/cli/review_stage.py` (`_run_script`, `SCRIPT_GRACE_S`),
  `skills/run-autopilot/cli/verification.py` (`_kill_gate`,
  `_deferred_signals`).
- `skills/review-work-completion/scripts/replay_tests_against_base.py`
  (`_raise_on_signal`, `_run_runner`, `_run_in_worktree`, `main`) and
  `test_replay_timeout_kill.py`.
- Review evidence: `reviews/00322-kill-the-gate-on-every-signal-v1-review-2.md`.

## Approach (candidate)
One PRD, full lane, `design: run`: the three HIGHs share one design (where
the guard lives and how a helper is terminated).

## Success Criteria (candidate)
- A SIGTERM to the review-stage caller mid-replay leaves no process in the
  runner's session, no `git worktree list` entry and no `replay-*` dir.

## Risks
- A guard around `worktree add` must not swallow a KeyboardInterrupt in an
  attended run; SIGINT stays outside the guard as today.

## Open Questions
- Is the replay's self re-delivery of the signal wanted (so the caller sees
  the same termination cause) or should the replay exit with a code?

## Discovery Log

### Inferred (not asked)
- Hold stubs 00336, 00337 and 00339 are closed into done/ with a note naming
  this document; 00338 is closed as resolved; the deferred ledger rows carry
  `disposition: discovery 00361`.
