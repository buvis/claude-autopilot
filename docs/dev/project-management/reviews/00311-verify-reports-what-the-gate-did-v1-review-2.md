---
prd: 00311-verify-reports-what-the-gate-did-v1.md
cycle: 2
date: 2026-10-15
head_sha: 108cce62358e87a9d632bfc79f5a6a811fc832e5
codex_thread_id: 01a13fae-906c-79f1-b679-f1a0a1b2cf42
reviewers: alice,blake,bob,carl
scope: incremental
---

# Review cycle 2 - 00311-verify-reports-what-the-gate-did-v1

Diff range: b2408046b02a95cdf19448e7429b832d4f311a7d..108cce62358e87a9d632bfc79f5a6a811fc832e5
(incremental: the cycle-1 rework commits only; cycle 1 reviewed the full work range)

codex_rung_guard: not fired

pack: failed (engram pack exit 1: sqlite3.OperationalError: attempt to write a readonly database)

Notes:
- Incremental cycle: reviewers verified the nine cycle-1 findings routed to rework (R1, R2, R3, R4, R5, R6, R8, R9, R10) and reviewed the rework diff for regressions. The three cycle-1 discards and three settled deferrals were fed to Alice, Bob and Carl as settled decisions; Blake stayed blind and his one re-raise was auto-dismissed mechanically.
- Bob's prompt was pre-inlined (context and full diff inlined into one 199 KB file) because the codex sandbox denies filesystem reads; this cycle he produced a complete review on the first run, with no refusal and no retry. He resumed his cycle-1 thread (`--resume-thread 01a13fae`).
- An uncommitted formatter reflow of nine `cli/*.py` files (203 insertions: line wrapping, magic trailing commas, `RSE102`, unused-import strip) was present when this session entered the gate. It was reverted with `git checkout --` before staging and never committed, so the reviewed diff is the committed work alone. Same class of event as cycle 1.
- `consolidate_findings.py` merged four `verification.py` citations into R1 after line-suffix stripping (`:538 ~ :441 ~ :483 ~ :490`). Alice, Bob and Carl each raised the defect independently at 🟠; Blake's merged line was a ⚪ that called the same `_child_from_exception` frame-walking "fragile" but defensible. R1's [4/4] therefore rests on three independent HIGH voices plus one corroborating low-severity mention, not four HIGH votes.
- Mechanical checks: 0 tautological test shapes across 129 test functions in 7 files. The fail-first replay ran 29 touched tests against the cycle-1 base, 5 failed there and 24 passed; its three `[MECH]` rows are absorbed below as R8, R9 and R10.
- No verification-check queue was written: Bob's VERIFY bucket was empty and no doubt lens emitted a runnable check. Cycle 1 queued none either, so there was no carry-forward to fold in.
- Tests were run by `review-stage` this cycle (the `last-verification.json` record at this HEAD carries null counts, so it was not reusable).

## Consolidated Findings

| Ref | Consensus | Severity | Issue | File | Task | Found By |
|-----|-----------|----------|-------|------|------|----------|
| R1 | [4/4] | 🟠 | Prior finding R5 (SIGINT during child creation leaks the gate) is only partly fixed. `_spawn_gate` recovers the child with `_child_from_exception`, which scans the traceback for a `Popen` and then calls `_kill_gate`. If SIGINT lands after `_fork_exec` returns but before `self.pid = ...` runs in `Popen._execute_child`, the recovered object has `pid is None`. `os.killpg(None, SIGKILL)` then raises `TypeError`, which replaces the `KeyboardInterrupt`. The forked gate keeps running, and the outer `LOCK_UN` still releases the lock. A second hole sits between `Popen()` returning and the `proc =` store, where no `Popen` is reachable at all. I measured this by calling `_spawn_gate("sleep 72", ...)` 1500 times with a SIGALRM-raised `KeyboardInterrupt` at random 0-12ms. 75 trials raised `TypeError: 'NoneType' object cannot be interpreted as an integer` instead of `KeyboardInterrupt`, and 68 left a live `sleep 72` gate behind. The remedy R5 asked for is to defer SIGINT the way SIGTERM is deferred (`gate_started` and `raise_if_pending` in `_SigtermGuard`). That closes both holes and makes `_child_from_exception` and `_POPEN_TYPE` unnecessary, so the frame-local introspection goes away. | skills/run-autopilot/cli/verification.py:538 | 5 | ALICE, BLAKE, BOB, CARL |
| R2 | [2/4] | 🟡 | `_write_record` now folds a non-zero summary EXIT token into the persisted `failed`, so a summary of `FAIL 0 ... EXIT 1` is stored as `failed: 1`. This does fix the reuse hole (R4), and the new test `test_exit_token_drop_record_not_reused` binds it. The cost is a record whose count disagrees with the gate's own summary, in a PRD about reporting what the gate did. It also adds a required positional parameter that the design called unchanged. Persisting the EXIT token as its own record field, or setting `commands[0].exit` from it, would keep the counts faithful. No other reader of the record depends on `failed`, so this is optional. | skills/run-autopilot/cli/verification.py:168 | 2 | ALICE, BOB |
| R3 | [1/4] | 🟡 | Swallowed error and untested branch behind the finding above: `_kill_gate` does not guard against `proc.pid is None`, so a `TypeError` hides the original interrupt. `test_sigint_during_popen_leaves_the_gate_running` raises after `real_popen` returns, with the `Popen` still bound in a test-frame local. It never exercises the real `Popen.__init__` frame where `pid` is unset, so it passes while the real race still leaks. Add a case where the recovered `Popen` has `pid=None`, or defer SIGINT and test that path. | skills/run-autopilot/cli/test_verify_truth.py:213 | 8 | ALICE |
| R4 | [1/4] | 🟡 | Phase 1 acceptance `rg -c '^def test_' skills/run-autopilot/cli/test_verification_dirty.py` was required to be unchanged from the base commit. It went from 31 (f6a99ab) to 26. The reuse-verdict and normalize tests were moved to `test_verification_normalize.py`, `test_verification_reuse_verdict.py` and `test_cli_verify_verb.py` by the "split oversized test files" commits. I could not confirm that every one of the 31 original test names survives elsewhere, so "no test deleted" is unproven. The literal criterion fails regardless. | skills/run-autopilot/cli/test_verification_dirty.py | Phase 1 | BLAKE |
| R5 | [1/4] | ⚪ | The JSON `error` on both exit-2 refusals omits the `autopilot: verify: ` prefix that the stderr line carries. The spec asks for `{"error": "<the stderr line>", "exit": 2}`. The text after the prefix is identical, and `test_exit_2_refusals_print_json` only checks that `error` is non-empty, so it does not catch the difference. | skills/run-autopilot/cli/__main__.py:1048 | Phase 1 | BLAKE |
| R6 | [1/4] | ⚪ | The recorded-result JSON shape in `final-verification.md` (lines 127-134) does not show the new `writer: run_gate` key. The exit table and the `log: null` note are present and correct. | skills/work/references/final-verification.md:127 | Phase 2 | BLAKE |
| R7 | [1/4] | ⚪ | The dirty-tree helpers moved into a new module, `skills/run-autopilot/cli/dirty_tree.py` (270 lines), and `verification.py` re-exports them. The PRD does not mention this. It is a pure refactor for the 800-line limit and no behaviour changed. | skills/run-autopilot/cli/dirty_tree.py | general | BLAKE |
| R8 | [1/4] | 🟡 | 18 touched test(s) pass against the pre-change code: test_normalize_command_collapses_whitespace_only +12 more | skills/run-autopilot/cli/test_verification_normalize.py | general | mech-check |
| R9 | [1/4] | 🟡 | 4 touched test(s) pass against the pre-change code: test_reuse_verdict_refuses_a_record_of_a_failed_gate, test_reuse_verdict_refuses_a_non_dict_commands_entry, test_reuse_verdict_refuses_an_empty_commands_list, test_reuse_verdict_docstring_states_the_tolerances_it_applies | skills/run-autopilot/cli/test_verification_reuse_verdict.py | general | mech-check |
| R10 | [1/4] | 🟡 | 2 touched test(s) pass against the pre-change code: test_sigterm_pending_before_gate_started_kills_the_gate, test_run_gate_line_names_lock_timeout_and_head_moved | skills/run-autopilot/cli/test_verify_truth.py | general | mech-check |

### Auto-dismissed (ledger)

- [BLAKE] 🟡 A verify killed by SIGTERM raises `RuntimeError("verify: SIGTERM during gate")`. The group is killed correctly, but `_run_verify` only catches `OSError` (skills/run-autopilot/cli/__main__.py:1107). The user sees a Python traceback, exit 1, and no JSON line. Exit 1 is also the "red suite" code in the exit table, so a signalled verify reads as a red gate. The spec says only that the handler raises, so this is a gap in the spec as much as in the code. | File: skills/run-autopilot/cli/verification.py:457 — Within spec, as the finding states: the Must-have says the handler "raises" and says nothing about the exception type or about a JSON line on signal death. The resulting rc 1 is also the correct colour for a killed gate. Changing the exception type or adding a signal-path JSON line is a new requirement, not this PRD's.

## Alice

Three findings, listed above as R1, R2 and R3. Her run inputs were the staged context and diff. She confirmed the SIGINT race empirically: 1500 `_spawn_gate` trials with a SIGALRM-raised `KeyboardInterrupt` at random 0-12ms, of which 75 raised `TypeError` instead of `KeyboardInterrupt` and 68 left a live gate process behind.

Verified resolved from cycle 1:
- **R1:** `_report_verify` now also returns 1 on a non-zero process exit (`skills/run-autopilot/cli/__main__.py:1060`). Two tests added in `test_cli_verify_verb.py`, covering no summary with exit 2 and a green summary with exit 5.
- **R2:** the dirty line now names the paths, and `test_review_stage.py` asserts it.
- **R3:** `_spawn_gate` is 41 lines; the dirty-tree helpers moved to `dirty_tree.py`; `verification.py` is 643 lines.
- **R6:** the oversized test files were split into `test_verification_normalize.py` and `test_verification_reuse_verdict.py`, both registered in `dev/bin/release-checks`; every file is now under 800 lines.
- **R8:** `test_run_gate_line_names_lock_timeout_and_head_moved` now passes a non-empty `dirty_paths` and asserts it passes through.
- **R9:** `test_sigterm_pending_before_gate_started_kills_the_gate` was added.
- **R10:** the reuse path of `run_gate_line` now returns `dirty_paths: []`.

She did not re-raise the settled discards or deferrals.

R1: fail
R2: pass
R3: pass
R4: pass
R6: pass
R7: pass
R8: pass
R9: fail
R10: fail
R11: pass
R12: pass
R13: pass

## Blake

Blind lens, PRD only. He confirmed the exit rule (derived from parsed `failed` plus the summary `EXIT` token, with the process exit preserved in the JSON), the `writer: run_gate` marker and `_record_shape_ok`'s refusal without it, the `pass_fds` lock handoff, the `BaseException` group SIGKILL with `ProcessLookupError` tolerance, the main-thread-only handler install and its `finally` restore, the `lock_timeout` / `head_moved` result shapes and their presence-and-False in the sibling shapes, both new `_gate_result_line` "gate skipped" lines, the path-naming dirty line, `dirty_paths` on both the fresh and reuse paths, the null `log` when no gate spawned, both exit-2 JSON refusals, the `final-verification.md` exit table, the CHANGELOG entries, the single `test_verify_truth.py` registration in `dev/bin/release-checks:331`, and all nine named tests plus three extras. Narrow run: 12 passed.

Six findings, listed above as R1 (merged), R4, R5, R6, R7 and one auto-dismissed by the ledger.

B1: pass
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
B15: fail
B16: pass
B17: pass
B18: pass
B19: pass

## Bob

Doubt lens plus de-slop, codex, resumed on his cycle-1 thread. Complete review on the first run, no retry needed. Two findings in FIX (R1 and R2); VERIFY and KNOWN both empty.

R1: fail
R2: pass
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

Gemini backend. He reproduced the `_child_from_exception` defect directly — constructing a partially initialized `Popen`, confirming `os.killpg(None, ...)` raises `TypeError`, and exercising `_spawn_gate` with an invalid `pass_fds` to reach the pre-fork failure path. He also checked the file-size limits (`verification.py` and `dirty_tree.py` both under the cap) and ran the narrow verification suites green. One finding, merged into R1.

R1: pass
R2: pass
R3: pass
R4: pass
R6: pass
R7: pass
R8: pass
R9: pass
R10: fail
R11: pass
R12: pass
R13: pass

Verdict: 10 findings
Tests: 6901 passed, 0 failed, 34 skipped (suite run this cycle)
