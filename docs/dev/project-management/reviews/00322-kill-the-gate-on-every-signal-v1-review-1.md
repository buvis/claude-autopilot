---
prd: docs/dev/project-management/prds/wip/00322-kill-the-gate-on-every-signal-v1.md
review: 1
date: 2026-10-17
head_sha: 385079686d66e8549634718b787db5b15fa39962
codex_thread_id: 01a146d6-4bb7-7b62-8d9b-c4ded6b98e1a
reviewers: alice,blake,bob,carl
agents:
  alice: available
  blake: available
  bob: available
  carl: available
dispatch_rows:
  bob: b4d8d619
  carl: 30fce38e
---

# Review: 00322-kill-the-gate-on-every-signal-v1

Diff range: `c657de35074c8abbb0e0e88fb59a07295deba948..385079686d66e8549634718b787db5b15fa39962`

codex_rung_guard: not fired

Cycle: 1 of rework_cap 2. Consensus engine: `legacy`. Doubt reviewer: `codex` (Bob); Eve not activated.

Staging notes (fail-loud):

- `pack: failed (engram pack exit 1: sqlite3.OperationalError: attempt to write a readonly database)`. The engram context pack was unavailable this cycle, so `{PACK_FILE}` / `{PACK_FINDINGS}` carried the `(no pack available this cycle)` sentinel for every lens. This review is degraded in that one respect, not invalid.
- Bob's first dispatch returned the lack-of-input refusal shape (codex could not read any supplied path: `sandbox-exec: sandbox_apply: Operation not permitted`). His one retry was spent on the inlined retry prompt (`docs/dev/tmp/bob-prompt-20261017-00322-c1-retry.md`, 264 KB, context + full diff inlined), which produced a real review. Bob's section below records `after one retry (inlined)`.
- Bob's retry emitted his issue lines nested inside his `FIX:` / `KNOWN:` buckets with a leading `- `, which `consolidate_findings.py` does not parse. His retry budget was already spent, so per `retry-policy.md` § Format Compliance his lines were normalized mechanically (leading `- ` stripped, nothing else changed) into `docs/dev/tmp/bob-output-20261017-00322-c1-normalized.txt` and consolidated from there. **(format warning)** applies to Bob's findings.
- `consolidate_findings.py` merged four replay citations into row R1 after suffix stripping (`replay_tests_against_base.py:1166 ~ :177 ~ :148 ~ :178`). Blake's R1 contribution is strictly the narrower re-delivery window; his separate claim that the handler does not wrap all of `_run_in_worktree` was folded into the same row by the script.

## Alice

Consensus lens, implementation-aware. 5 findings.

```
[ALICE] 🟡 Replay `_run_runner` re-delivers a signal recorded during cleanup with `os.kill(os.getpid(), ...)` after the handlers are restored. With the default disposition this kills the replay process before `_run_in_worktree`'s `finally` removes the worktree and temp dir, which is the leak this PRD closes. It also contradicts the design contract, which says a second signal during cleanup is "recorded and dropped". An orphan sweep that sends SIGHUP then SIGTERM hits this window. It applies to the TimeoutExpired and `_SignalRaised` branches alike. Fix: drop the re-delivery, or re-raise it only after the `finally` has run. | File: skills/review-work-completion/scripts/replay_tests_against_base.py:1166 | Task: 3
[ALICE] 🟡 `_run_script` now starts helpers with `start_new_session=True` but installs no signal handling of its own. A SIGTERM or SIGHUP aimed at the review-stage caller's group no longer reaches the helper, which previously shared that group. A swept review stage therefore leaves the replay running for up to 480s. The replay's own guard only fires on a signal sent to the helper's own group. Fix: guard `_run_script` the same way, or document the accepted gap in the design. | File: skills/run-autopilot/cli/review_stage.py:1460 | Task: 3
[ALICE] 🟡 In `_run_script`, `os.killpg(proc.pid, SIGTERM)` and the later SIGKILL are unguarded. If the helper exits between the `communicate` timeout and the `killpg` call, `ProcessLookupError` propagates. The design says "no exception propagates". `_kill_gate` and the replay both catch `ProcessLookupError` on the same idiom. Wrap both calls in `try/except ProcessLookupError`. | File: skills/run-autopilot/cli/review_stage.py:1473 | Task: 3
[ALICE] 🟡 `test_signal_before_a_refusal_is_not_swallowed` passes against the pre-change code, per the fail-first replay block (2 of its 3 params pass at base), so it does not pin this change. Its `pytest.raises((_StraySignal, RuntimeError))` plus the conditional `if not isinstance(...)` assert is an either-or hedge. Pin the new `_SignalGuard` behaviour (the exact "verify: SIGTERM during gate" error), or drop the test. | File: skills/run-autopilot/cli/test_verify_truth_lock.py:2482 | Task: 2
[ALICE] ⚪ `test_group_sigterm_kills_runner_and_removes_worktree` is 59 lines (mechanical facts), over the 50-line limit. Move the wait loop and the cleanup `finally` into helpers. | File: skills/review-work-completion/scripts/test_replay_timeout_kill.py:1296 | Task: 1
```

R1: pass
R2: fail
R3: pass
R4: pass
R6: pass
R7: pass
R8: pass
R9: fail
R10: pass
R11: pass
R12: fail
R13: pass

## Blake

Blind lens, PRD-only. He located the code himself and ran the five relevant test files (100 passed). He did not run the storm test as a separate timed check and did not confirm the new tests fail at the base commit.

Verified against the spec: `_SignalGuard` / `_deferred_signals` cover SIGTERM, SIGINT and SIGHUP; `Popen` runs inside the guarded region; `_child_from_exception` and `_POPEN_TYPE` are gone; `_kill_gate` only receives a real `Popen` or `None`; `run_gate` carries `lock_timeout` defaulting to `GATE_LOCK_TIMEOUT_S` = 600; the gate deadline is computed after the lock is acquired; `waited_s` is in every result shape including `_lock_timeout_result`; `_run_verify` prints the one JSON line and returns 2; `SCRIPT_TIMEOUT_S` = 540 is passed and named in the timeout block; `_append_mech_blocks` passes `--timeout 480`; both CHANGELOG `[Unreleased]` Fixed entries exist.

```
[BLAKE] 🟠 The replay's signal handler is installed only around the runner's `Popen`/`communicate` in `_run_runner`, not around the whole of `_run_in_worktree`. A SIGTERM or SIGHUP during `git worktree add`, the overlay checkout, or any step before the runner spawns keeps the default action. The process dies, the `finally` is skipped, and the worktree and `replay-*` temp dir leak. The spec says the exception lands inside `_run_in_worktree` and the group SIGTERM leaves one worktree and no temp dir. | File: skills/review-work-completion/scripts/replay_tests_against_base.py:148 | Task: 3
[BLAKE] 🟡 A signal recorded while the replay is cleaning up is re-delivered with `os.kill` after the handlers are restored, still inside `_run_runner` (lines 177-178). The default handler kills the process before `_run_in_worktree`'s `finally` removes the worktree, so that narrow race still leaks. | File: skills/review-work-completion/scripts/replay_tests_against_base.py:177 | Task: 3
[BLAKE] 🟡 A signalled replay swallows the signal. It returns "killed by SIGTERM" as a skip reason, prints a "replay: skipped" block and exits 0, rather than terminating. The spec only requires cleanup, but a caller that sent SIGTERM sees a clean exit. | File: skills/review-work-completion/scripts/replay_tests_against_base.py:172 | Task: 3
[BLAKE] 🟡 A signal recorded during `_spawn_gate` cleanup after a non-signal error, such as a log-sink OSError, is silently dropped. `_SignalGuard.handle` records it and nothing re-raises it, so a SIGINT in that window is lost. | File: skills/run-autopilot/cli/verification.py:561 | Task: 4
[BLAKE] 🟡 Between the end of `_reap` and the end of the `with` block, a signal still raises. `_kill_gate` then runs `killpg` on an already-reaped pid. `ProcessLookupError` is caught, but pid or group reuse is theoretically possible. | File: skills/run-autopilot/cli/verification.py:629 | Task: 4
[BLAKE] ⚪ Unspecified behavior added: `_run_script` sends SIGTERM and waits `SCRIPT_GRACE_S` (30 s, per CHANGELOG.md:100) before SIGKILL on timeout. The spec names no grace period or extra constant. It is arguably needed for the replay's handler to run, but it was not specified. | File: skills/run-autopilot/cli/review_stage.py:226 | Task: 5
[BLAKE] ⚪ Two new tests are not where the PRD names them, so the PRD's acceptance commands do not run them. `test_run_script_times_out_and_says_so` is in skills/run-autopilot/cli/test_review_stage_run_script.py:114, not `test_review_stage.py`. `test_late_waiter_gate_gets_full_timeout` and `test_result_reports_waited_s` are in skills/run-autopilot/cli/test_verify_truth_lock.py:81, not `test_verify_truth.py`. | File: N/A | Task: 1
[BLAKE] ⚪ The run-autopilot CHANGELOG entry names SIGINT and SIGTERM but not SIGHUP, and does not mention the replay or `waited_s`. | File: CHANGELOG.md:99 | Task: 6
```

B1: fail
B2: pass
B3: pass
B4: pass
B5: pass
B6: pass
B7: pass
B8: pass
B9: pass
B10: pass
B11: pass
B12: pass
B13: pass
B14: pass
B15: pass
B16: pass
B17: pass
B18: pass
B19: pass

## Bob

Doubt lens (D1-D5 rubric) plus de-slop, codex, after one retry (inlined). **(format warning)** — his issue lines arrived nested in his buckets with a leading `- ` and were normalized mechanically for consolidation.

FIX:
```
[BOB] 🟠 A second signal during runner cleanup is re-delivered after restoring the default handler, terminating replay before `_run_in_worktree` reaches its worktree-removal `finally`. Keep signal protection through worktree removal and consume cleanup signals; add a repeated-signal regression. | File: skills/review-work-completion/scripts/replay_tests_against_base.py:178 | Task: 3
[BOB] 🟠 Starting helpers in a new session detaches them from the review-stage caller's process group. SIGTERM/SIGHUP to that caller now misses the helper, and `_run_script` has no interruption cleanup, leaving replay and its runner executing. Guard the helper lifecycle, forward termination, and wait for cleanup; test signaling the review-stage caller's group. | File: skills/run-autopilot/cli/review_stage.py:215 | Task: 3
[BOB] 🟡 Both timeout `killpg` calls can raise `ProcessLookupError` if the helper exits between timeout detection and signaling, aborting review staging instead of returning the timeout block. Catch that race at both calls and still drain/reap; add a deterministic regression. | File: skills/run-autopilot/cli/review_stage.py:226 | Task: 3
```

VERIFY:
- (none)

KNOWN:
```
[BOB] 🟡 The supplied mechanical check identifies an either-or assertion that cannot fail as written. Replace it with the required single outcome in its owning maintenance task; the assertion predates this diff and is outside this signal/timeout PRD. | File: skills/run-autopilot/cli/test_release_checks_counts.py:326 | Task: general
```

R1: fail
R2: fail
R3: pass
R4: fail
R6: pass
R7: pass
R8: pass
R9: fail
R10: fail
R11: pass
R12: pass
R13: pass

D1: pass
D2: pass
D3: pass
D4: pass
D5: pass

## Carl

Gemini backend (`copilot` resolved; `gemini` also available). 6 findings.

```
[CARL] 🟡 Function test_group_sigterm_kills_runner_and_removes_worktree is 59 lines, exceeding the 50-line limit | File: skills/review-work-completion/scripts/test_replay_timeout_kill.py:141 | Task: 1
[CARL] 🟡 ProcessLookupError not caught around os.killpg in _run_script during timeout escalation | File: skills/run-autopilot/cli/review_stage.py:226 | Task: 3
[CARL] 🟡 Lock timeout message in _gate_result_line cites GATE_TIMEOUT_S (1800s) instead of new GATE_LOCK_TIMEOUT_S (600s) | File: skills/run-autopilot/cli/review_stage.py:371 | Task: 2
[CARL] 🟡 test_skip_ceiling_fails_the_gate_above_three hedges with or: either outcome satisfies it | File: skills/run-autopilot/cli/test_release_checks_counts.py:326 | Task: general
[CARL] 🟡 2 touched test(s) pass against the pre-change code: test_signal_before_a_refusal_is_not_swallowed | File: skills/run-autopilot/cli/test_verify_truth_lock.py:211 | Task: 1
[CARL] 🟡 File review_stage.py exceeds the 800-line limit (874 lines) | File: skills/run-autopilot/cli/review_stage.py:874 | Task: general
```

R1: pass
R2: fail
R3: pass
R4: pass
R6: pass
R7: pass
R8: pass
R9: fail
R10: fail
R11: pass
R12: fail
R13: fail

## Mechanical test checks (absorbed)

Both `[MECH]` lines from the context file's two computed blocks are absorbed into the table below rather than dropped:

```
[MECH] 🟡 test_skip_ceiling_fails_the_gate_above_three hedges with `or`: either outcome satisfies it | File: skills/run-autopilot/cli/test_release_checks_counts.py:326 | Task: general
[MECH] 🟡 2 touched test(s) pass against the pre-change code: test_signal_before_a_refusal_is_not_swallowed | File: skills/run-autopilot/cli/test_verify_truth_lock.py | Task: general
```

The first names the same test and file as rows R11 (Bob) and R14 (Carl); `mech-check` is appended to R14's finders. The second names the same test and file as row R2; `mech-check` is appended to R2's finders.

## Consolidated Findings

| Ref | Consensus | Severity | Issue | File | Task | Found By |
|-----|-----------|----------|-------|------|------|----------|
| R1 | [3/4] | 🟠 | Replay `_run_runner` re-delivers a signal recorded during cleanup with `os.kill(os.getpid(), ...)` after the handlers are restored. With the default disposition this kills the replay process before `_run_in_worktree`'s `finally` removes the worktree and temp dir, which is the leak this PRD closes. It also contradicts the design contract, which says a second signal during cleanup is "recorded and dropped". An orphan sweep that sends SIGHUP then SIGTERM hits this window. It applies to the TimeoutExpired and `_SignalRaised` branches alike. Fix: drop the re-delivery, or re-raise it only after the `finally` has run. | skills/review-work-completion/scripts/replay_tests_against_base.py:1166 | 3 | ALICE, BLAKE, BOB |
| R2 | [2/4] | 🟡 | `test_signal_before_a_refusal_is_not_swallowed` passes against the pre-change code, per the fail-first replay block (2 of its 3 params pass at base), so it does not pin this change. Its `pytest.raises((_StraySignal, RuntimeError))` plus the conditional `if not isinstance(...)` assert is an either-or hedge. Pin the new `_SignalGuard` behaviour (the exact "verify: SIGTERM during gate" error), or drop the test. | skills/run-autopilot/cli/test_verify_truth_lock.py:2482 | 2 | ALICE, CARL, mech-check |
| R3 | [2/4] | 🟡 | `test_group_sigterm_kills_runner_and_removes_worktree` is 59 lines (mechanical facts), over the 50-line limit. Move the wait loop and the cleanup `finally` into helpers. | skills/review-work-completion/scripts/test_replay_timeout_kill.py:1296 | 1 | ALICE, CARL |
| R4 | [1/4] | 🟠 | Starting helpers in a new session detaches them from the review-stage caller's process group. SIGTERM/SIGHUP to that caller now misses the helper, and `_run_script` has no interruption cleanup, leaving replay and its runner executing. Guard the helper lifecycle, forward termination, and wait for cleanup; test signaling the review-stage caller's group. | skills/run-autopilot/cli/review_stage.py:215 | 3 | BOB |
| R5 | [1/4] | 🟡 | `_run_script` now starts helpers with `start_new_session=True` but installs no signal handling of its own. A SIGTERM or SIGHUP aimed at the review-stage caller's group no longer reaches the helper, which previously shared that group. A swept review stage therefore leaves the replay running for up to 480s. The replay's own guard only fires on a signal sent to the helper's own group. Fix: guard `_run_script` the same way, or document the accepted gap in the design. | skills/run-autopilot/cli/review_stage.py:1460 | 3 | ALICE |
| R6 | [1/4] | 🟡 | In `_run_script`, `os.killpg(proc.pid, SIGTERM)` and the later SIGKILL are unguarded. If the helper exits between the `communicate` timeout and the `killpg` call, `ProcessLookupError` propagates. The design says "no exception propagates". `_kill_gate` and the replay both catch `ProcessLookupError` on the same idiom. Wrap both calls in `try/except ProcessLookupError`. | skills/run-autopilot/cli/review_stage.py:1473 | 3 | ALICE |
| R7 | [1/4] | 🟡 | A signalled replay swallows the signal. It returns "killed by SIGTERM" as a skip reason, prints a "replay: skipped" block and exits 0, rather than terminating. The spec only requires cleanup, but a caller that sent SIGTERM sees a clean exit. | skills/review-work-completion/scripts/replay_tests_against_base.py:172 | 3 | BLAKE |
| R8 | [1/4] | 🟡 | A signal recorded during `_spawn_gate` cleanup after a non-signal error, such as a log-sink OSError, is silently dropped. `_SignalGuard.handle` records it and nothing re-raises it, so a SIGINT in that window is lost. | skills/run-autopilot/cli/verification.py:561 | 4 | BLAKE |
| R9 | [1/4] | 🟡 | Between the end of `_reap` and the end of the `with` block, a signal still raises. `_kill_gate` then runs `killpg` on an already-reaped pid. `ProcessLookupError` is caught, but pid or group reuse is theoretically possible. | skills/run-autopilot/cli/verification.py:629 | 4 | BLAKE |
| R10 | [1/4] | 🟡 | Both timeout `killpg` calls can raise `ProcessLookupError` if the helper exits between timeout detection and signaling, aborting review staging instead of returning the timeout block. Catch that race at both calls and still drain/reap; add a deterministic regression. | skills/run-autopilot/cli/review_stage.py:226 | 3 | BOB |
| R11 | [1/4] | 🟡 | The supplied mechanical check identifies an either-or assertion that cannot fail as written. Replace it with the required single outcome in its owning maintenance task; the assertion predates this diff and is outside this signal/timeout PRD. | skills/run-autopilot/cli/test_release_checks_counts.py:326 | general | BOB |
| R12 | [1/4] | 🟡 | ProcessLookupError not caught around os.killpg in _run_script during timeout escalation | skills/run-autopilot/cli/review_stage.py:226 | 3 | CARL |
| R13 | [1/4] | 🟡 | Lock timeout message in _gate_result_line cites GATE_TIMEOUT_S (1800s) instead of new GATE_LOCK_TIMEOUT_S (600s) | skills/run-autopilot/cli/review_stage.py:371 | 2 | CARL |
| R14 | [1/4] | 🟡 | test_skip_ceiling_fails_the_gate_above_three hedges with or: either outcome satisfies it | skills/run-autopilot/cli/test_release_checks_counts.py:326 | general | CARL, mech-check |
| R15 | [1/4] | 🟡 | File review_stage.py exceeds the 800-line limit (874 lines) | skills/run-autopilot/cli/review_stage.py:874 | general | CARL |
| R16 | [1/4] | ⚪ | Unspecified behavior added: `_run_script` sends SIGTERM and waits `SCRIPT_GRACE_S` (30 s, per CHANGELOG.md:100) before SIGKILL on timeout. The spec names no grace period or extra constant. It is arguably needed for the replay's handler to run, but it was not specified. | skills/run-autopilot/cli/review_stage.py:226 | 5 | BLAKE |
| R17 | [1/4] | ⚪ | Two new tests are not where the PRD names them, so the PRD's acceptance commands do not run them. `test_run_script_times_out_and_says_so` is in skills/run-autopilot/cli/test_review_stage_run_script.py:114, not `test_review_stage.py`. `test_late_waiter_gate_gets_full_timeout` and `test_result_reports_waited_s` are in skills/run-autopilot/cli/test_verify_truth_lock.py:81, not `test_verify_truth.py`. | N/A | 1 | BLAKE |
| R18 | [1/4] | ⚪ | The run-autopilot CHANGELOG entry names SIGINT and SIGTERM but not SIGHUP, and does not mention the replay or `waited_s`. | CHANGELOG.md:99 | 6 | BLAKE |

No verification-check queue was written this cycle: the only doubt lens that emits buckets (Bob) reported `VERIFY: (none)`, and Eve was not activated.

Verdict: 18 findings
Tests: 7048 passed, 0 failed, 3 skipped (reused from last-verification.json at 5b6679f)
