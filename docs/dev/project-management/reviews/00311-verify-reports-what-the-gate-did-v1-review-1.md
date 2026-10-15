---
prd: 00311-verify-reports-what-the-gate-did-v1.md
cycle: 1
date: 2026-10-15
head_sha: b2408046b02a95cdf19448e7429b832d4f311a7d
codex_thread_id: 01a13fae-906c-79f1-b679-f1a0a1b2cf42
reviewers: alice,blake,bob,carl
---

# Review: 00311-verify-reports-what-the-gate-did-v1 (cycle 1)

Diff range: 82f63a12ff7fef147d7d0596d5512d8b5511b7f1..b2408046b02a95cdf19448e7429b832d4f311a7d

codex_rung_guard: not fired

pack: failed (engram pack exit 1: sqlite3.OperationalError: attempt to write a readonly database)

Notes:
- `state.work_start_sha` was `null` when this session entered the review gate, so the full-review diff range had no base. It was recovered as `82f63a12ff7f` — the commit before `5f23135c` (`test(run-autopilot): pin six verify-truth reproductions as failing regressions`), this PRD's first work commit — and written to state before staging. Without that recovery `gather-context.sh` would have refused an empty diff.
- The working tree carried an uncommitted formatter reflow of `skills/run-autopilot/cli/test_review_stage.py` and `skills/run-autopilot/cli/test_verification.py` (145 insertions, magic trailing commas and line wrapping only, no assertion changed). It was reverted with `git checkout --` before staging, never committed, so the reviewed diff is the committed work alone.
- Bob's first codex run returned a lack-of-input refusal (`sandbox_apply: Operation not permitted` before any read-only command ran; every R verdict emitted as `fail`, no findings). One retry was dispatched with the inlined retry prompt (`docs/dev/tmp/bob-prompt-20261015-1252-retry.md`, context + full diff inlined, 224 KB); it produced a complete review. Bob's section below is the retry's output, after one retry (inlined). The first run's output is kept at `docs/dev/tmp/bob-output-20261015-1252-run1-refusal.txt`.
- `consolidate_findings.py` dropped Bob's issue lines on the first pass: the doubt contract emits them as `- [BOB] ...` bullets inside the FIX/VERIFY/KNOWN sections, and the consolidator's line parser requires `[BOB]` at column zero. Bob's output was normalized (leading `- ` stripped) into `docs/dev/tmp/bob-output-20261015-1252-normalized.txt` and re-consolidated, so the doubt lens is represented below. This is the same review-pack defect recorded in 00310's cycle-1 review; it is out of scope here.
- A first transcription of Blake's output into `blake-output-20261015-1252.txt` dropped the `Task:` field from five of his six finding lines. The file was rewritten verbatim and the consolidation re-run; the table below is the corrected run.
- Mechanical checks: 0 tautological test shapes across 153 test functions. The fail-first replay found 21 of 43 touched tests passing against the pre-change base; both `[MECH]` rows are absorbed into the table below as R14 and R15.
- Tests for the reviewed revision were run by `review-stage` this cycle (the prior `last-verification.json` was stale against this HEAD).

## Consolidated Findings

| Ref | Consensus | Severity | Issue | File | Task | Found By |
|-----|-----------|----------|-------|------|------|----------|
| R1 | [3/4] | 🟠 | High: `_report_verify` derives red only from the parsed summary, so the process exit no longer counts. I ran the CLI and confirmed both drifts. (a) `--gate-command "echo build failed; exit 2"` (no summary, process exit 2) now returns rc 3. It returned 1 before this diff. The PRD says exit 3 "keeps today's meaning", and the exit table says 3 is for "the gate exited 0 ... no summary line". skills/work/references/final-verification.md:176 says exit 3 "means the suite did not fail, so it does not enter Handling failures". A crashed or build-broken gate therefore skips failure handling. (b) `echo PASS 1 FAIL 0 SKIP 0 EXIT 0; exit 5` returns rc 0 with `recorded: true` and `exit: 5`. The table says 0 means "gate ran green", but the record's command exit is 5, so `_record_shape_ok` will never reuse it. Fix: also return 1 when `result["exit"] not in (None, 0)`, and add tests for a non-zero process exit with no summary and with a green summary. The design snippet has the same gap, but the PRD and the doc table do not allow it. | skills/run-autopilot/cli/__main__.py:1072 | 3 | ALICE, BLAKE, BOB |
| R2 | [3/4] | 🟡 | Medium: The PRD must-have says `run_gate_line`'s dirty line "names the paths", but `_gate_result_line` still prints the generic "working tree dirty outside the store". Only the `dirty_paths` dict key was added. Name the paths in the line, or record that the PRD sentence is deliberately dropped. | skills/run-autopilot/cli/review_stage.py:364 | 4 | ALICE, BLAKE, BOB |
| R3 | [3/4] | 🟡 | Medium: `_spawn_gate` is 63 lines, over the 50-line limit (see the mechanical facts block). Split the SIGTERM handler install/restore from the Popen, drain and reap body. For example, a small context manager would hold `gate_started`, `sigterm_pending` and the main-thread guard. This row also carries Alice's and Carl's file-size finding, merged on the same file: the diff pushes `verification.py` from 657 to 808 lines, over the 800-line limit. | skills/run-autopilot/cli/verification.py:646 | 2 | ALICE, BOB, CARL |
| R4 | [1/4] | 🟠 | `PASS 4 FAIL 0 SKIP 0 EXIT 1` with process exit 0 produces a reusable green record: persistence drops the summary's EXIT token, retaining zero failures and command exit 0. Preserve that failure in record eligibility and add a run→reuse regression test. | skills/run-autopilot/cli/verification.py:560 | 2 | BOB |
| R5 | [1/4] | 🟠 | SIGINT during child creation bypasses cleanup because `Popen` sits outside the `BaseException` handler and only SIGTERM is deferred. The outer `LOCK_UN` then releases the inherited lock while the gate survives. Defer SIGINT through spawning too, and test interruption after child creation but before `Popen` returns. | skills/run-autopilot/cli/verification.py:680 | 2 | BOB |
| R6 | [1/4] | 🟡 | Both `test_verification.py` and `test_verification_dirty.py` now extend beyond 800 lines, as their final function locations and lengths establish. Trim redundant commentary or move a coherent test group into a registered sibling module without removing assertions. | skills/run-autopilot/cli/test_verification.py:788 | 2 | BOB |
| R7 | [1/4] | 🟡 | `SUMMARY_RE.search` called without None-check on `raw_line`; guard regex match before accessing `group(4)` | skills/run-autopilot/cli/__main__.py:1056 | 3 | CARL |
| R8 | [1/4] | ⚪ | Low: `test_run_gate_line_names_lock_timeout_and_head_moved` compares `dirty_paths` against `[]` on both sides, so it does not show that non-empty paths pass through to the returned dict. Use a non-empty `dirty_paths` in one case. | skills/run-autopilot/cli/test_verify_truth.py:377 | 1 | ALICE |
| R9 | [1/4] | ⚪ | Low: Nothing exercises the pending-SIGTERM branch (`sigterm_pending`) in `_spawn_gate`. `_run_verify` also catches only `OSError`, so the SIGTERM `RuntimeError` surfaces as a traceback with exit 1. This is acceptable but undocumented. | skills/run-autopilot/cli/verification.py:669 | 2 | ALICE |
| R10 | [1/4] | ⚪ | On the reuse path, the dict `run_gate_line` returns has no `dirty_paths` key (only `verdict`, `tests_line`, `timed_out`). The PRD says the returned gate dict carries `dirty_paths`. Any consumer indexing it unconditionally would raise `KeyError`. | skills/run-autopilot/cli/review_stage.py:387 | Phase 2 review-stage-lines | BLAKE |
| R11 | [1/4] | ⚪ | `run_gate_line` still returns `"log": str(log_path)` on a lock-timeout, head-moved or dirty refusal, when no log was created. The Problem section names this as a defect ("review-stage's dirty line names a log that does not exist"), but no requirement covers it, so it remains. | skills/run-autopilot/cli/review_stage.py:405 | Phase 2 review-stage-lines | BLAKE |
| R12 | [1/4] | ⚪ | The SIGTERM handler raises a bare `RuntimeError`. An uncaught SIGTERM therefore ends `verify` with a traceback and rc 1, with no JSON line. The PRD only says "raises", so this is within spec, but it does not match the tidy exit table. | skills/run-autopilot/cli/verification.py:674 | Phase 1 gate-runner | BLAKE |
| R13 | [1/4] | ⚪ | The `_spawn_gate` helper has an extra `sigterm_pending` and `gate_started` mechanism and a main-thread guard that the PRD does not ask for. It is defensive, harmless, and the cost of the Popen race, so I flag it only for completeness. | skills/run-autopilot/cli/verification.py:665 | Phase 1 gate-runner | BLAKE |
| R14 | [1/4] | 🟡 | 1 touched test(s) pass against the pre-change code: test_review_close_rejects_an_unknown_batch_id | skills/run-autopilot/cli/test_cli_review_verbs.py | general | mech-check |
| R15 | [1/4] | 🟡 | 20 touched test(s) pass against the pre-change code: test_verify_runs_the_gate_once_and_writes_the_record_and_log, test_verify_exits_1_on_a_red_gate, test_verify_writes_no_record_on_a_dirty_tree, test_verify_dirtied_during_the_run_still_reports_the_process_exit, test_verify_exits_2_outside_a_git_repo, test_verify_exits_2_when_head_resolution_raises_oserror +14 more | skills/run-autopilot/cli/test_cli_verify_verb.py | general | mech-check |

## Alice

Six findings, listed above as R1, R2, R3 (with its merged file-size row), R8 and R9. Her run inputs were the staged context and diff; she ran the CLI directly to confirm both halves of R1.

R1: pass
R2: pass
R3: pass
R4: pass
R6: pass
R7: pass
R8: pass
R9: fail
R10: pass
R11: pass
R12: fail
R13: fail

## Blake

Blind lens, PRD only. He confirmed the writer marker, the `pass_fds` lock handoff, the `BaseException` group kill, the `lock_timeout`/`head_moved` shapes, both JSON refusals, the exit table in `final-verification.md`, the CHANGELOG entries and the single `test_verify_truth.py` registration in `dev/bin/release-checks`, and ran 163 tests green. Six findings, listed above as R1, R2, R10, R11, R12 and R13.

B1: fail
B2: pass
B3: pass
B4: pass
B5: fail
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

Doubt lens + de-slop, after one retry (inlined). Six findings, listed above as R1, R2, R3, R4, R5 and R6.

FIX: all six findings above.
VERIFY: (none)
KNOWN: (none)

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
R12: fail
R13: fail

D1: pass
D2: pass
D3: pass
D4: pass
D5: pass

## Carl

Backend: copilot. Three findings, listed above as R3 (function length and file size) and R7. He ran `skills/work/scripts/check_style_limits.py` and reported its exit-1 output mechanically: `_spawn_gate` 63 lines, `verification.py` 808 lines.

R1: pass
R2: pass
R3: pass
R4: pass
R6: pass
R7: pass
R8: pass
R9: pass
R10: pass
R11: pass
R12: fail
R13: fail

Verdict: 15 findings
Tests: 6896 passed, 0 failed, 34 skipped (suite run this cycle)
