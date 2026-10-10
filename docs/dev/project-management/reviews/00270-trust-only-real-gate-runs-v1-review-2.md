---
prd: docs/dev/project-management/prds/wip/00270-trust-only-real-gate-runs-v1.md
review: 2
date: 2026-10-10
head_sha: 033cf5664fdf6bb364a33b8ade7098a3f80db271
codex_thread_id: 01a125bf-3c30-7d53-b23d-8dcfe3b7cac2
reviewers: alice,blake,bob,carl
agents:
  alice: available
  blake: available
  bob: available
  carl: available
dispatch_rows:
  bob: 9b9a3313
  carl: 8ad8f66b
---

# Review: 00270-trust-only-real-gate-runs-v1

Diff range: `07fa37c3e205feac1e0e952d7b9778a393e48e3c..033cf5664fdf6bb364a33b8ade7098a3f80db271`

codex_rung_guard: not fired

Incremental review (cycle 2) of the cycle-1 rework. Bob resumed his cycle-1 codex
thread. Pack: ok. Ledger: 3 settled entries fed to Alice, Bob and Carl; Blake's
re-raises auto-dismissed via `--ledger-dismiss BLAKE` (nothing was dismissed this
cycle - he did not re-raise a settled item).

## Consolidated Findings

| Ref | Consensus | Severity | Issue | File | Task | Found By |
|-----|-----------|----------|-------|------|------|----------|
| R1 | [3/4] | 🟠 | Prior R6 is only half fixed. `_drain_bounded` still calls `sink.write(chunk)` with no `OSError` guard, and `run_gate`'s `finally` only closes the log. A disk-full or write error mid-run therefore still raises out of `run_gate` before `_reap`, leaving the gate's process group running and possibly dirtying the tree. The new handler in `_append_context_blocks` only stops `review-stage` from crashing, and it hides the leaked child. Fix: catch `OSError` around the drain and the log write, kill the process group (`_reap` with drained=False, or `os.killpg`), then re-raise. Add a test with a failing sink. | skills/run-autopilot/cli/verification.py:251 | 12 | ALICE, BLAKE, BOB |
| R2 | [3/4] | 🟠 | Prior R1(a) is still unfixed. The `except OSError` branch in `_run_verify` that prints `{"sha","log","error"}` and exits 2 has no verb-level test. The only new OSError test covers the HEAD-resolution branch, which is a different code path. Bob's R17 asked for "exit 2 with one JSON error line". Fix: add a test in `test_cli_review_verbs.py` that passes `--log` pointing at a directory and asserts exit 2 plus one JSON line with `error`, `sha` and `log`. | skills/run-autopilot/cli/__main__.py:980 | 13 | ALICE, BOB, CARL |
| R3 | [3/4] | 🟡 | `test_review_stage.py` is now 802 lines, over the 800-line cap. It was about 752 before this rework added 50 lines, so the breach is new in this diff. Fix: move the two new tests, or the dirty-line test plus the log-failure test, into a small module such as `test_review_stage_gate.py`. Register it in `dev/bin/release-checks` and `_REVIEW_VERB_TEST_FILES`. | skills/run-autopilot/cli/test_review_stage.py:802 | 13 | ALICE, BOB, CARL |
| R4 | [3/4] | 🟡 | Prior R2 is only partly resolved. `_parse_summary` was extracted, but `run_gate` still spans lines 323-383, 61 lines including a 15-line docstring, over the 50-line limit. Fix: trim the docstring to the contract, since the record shape, dirty rule and log behavior are already documented on `_write_record`, `_dirty_result` and `_drain_bounded`. Alternatively move the result-dict construction into a helper. | skills/run-autopilot/cli/verification.py:323 | 12 | ALICE, BOB, CARL |
| R5 | [2/4] | 🟡 | The new test `test_gate_log_write_failure_degrades_instead_of_crashing` ends in an either-or hedge: `signalled = bool(summary["errors"]) or "error" in json.dumps(summary["gate"]).lower()`. The implementation always sets both (`verdict: "error"` and an errors entry), so either branch alone passes and neither pins behavior. Fix: assert `summary["gate"]["tests_line"].startswith("Tests: (gate failed to run")` and `any("gate failed" in e for e in summary["errors"])`. It should also assert that the `## Test gate` block still lands in the context file. | skills/run-autopilot/cli/test_review_stage.py:545 | 13 | ALICE, BOB |
| R6 | [2/4] | 🟡 | The R12 fix pins the wrong sentence. `'`"verify"` rows create nothing'` matches only the parenthetical in phase-review.md:193 ("coverage still holds; `"verify"` rows create nothing"). The Phase 6 sentence at phase-review.md:305 reads `"verify"`, `"discard"` and `"carry"` rows create nothing`. Deleting that sentence would not fail this test, though test_review_verbs_prose.py:154 does pin it. Fix: pin the exact :305 string, as R12 asked. | skills/work/scripts/test_verify_queue_prose.py:273 | 15 | ALICE, BOB |
| R7 | [2/4] | 🟡 | `test_verification_dirty.py` has two copy-paste leftovers. Its docstring cites "PRD 00249 task 1 rework", but this is PRD 00270. It also duplicates `_git`, `_commit`, `repo` and `_record` from `test_verification.py`; a shared helper or conftest fixture would remove about 45 lines. In `test_verification.py`, `STORE_PREFIX` (line 24) is now unused. | skills/run-autopilot/cli/test_verification_dirty.py:1 | 12 | ALICE, BOB |
| R8 | [1/4] | 🟡 | A dirty-tree refusal before the run looks like a red suite to a session. `run_gate` returns `_dirty_result()` with `exit: None` without ever spawning the gate. `_run_verify` then exits 1, the same code as a failing suite (`skills/run-autopilot/cli/__main__.py:984`). `final-verification.md` never tells sessions to read the JSON `recorded` or `dirty` keys, and never tells them to commit first. `final-verification.md` line 164 onward sends them into the regression loop on a failing suite. The same file at lines 147-149 describes only the dirty-tree no-record outcome. | skills/work/references/final-verification.md:147 | 11 | BLAKE |
| R9 | [1/4] | 🟡 | `autopilot verify` exits 0 when the gate exits 0 but the tree was dirtied during the run. No record is written and the JSON has `recorded: false`. Exit 0 is spec-compliant, and a test pins it (`test_verify_dirtied_during_the_run_still_reports_the_process_exit`). But the prose never says to check `recorded`, so a session can believe a record exists when none does. | skills/run-autopilot/cli/__main__.py:984 | 6 | BLAKE |
| R10 | [1/4] | 🟡 | Switching to unbuffered FileIO introduces possible short writes, but `_drain_bounded` ignores `sink.write()`’s returned byte count. This can silently omit output. Retain buffered writes with an explicit flush, or loop until every byte is written; test partial writes. | skills/run-autopilot/cli/verification.py:349 | 12 | BOB |
| R11 | [1/4] | ⚪ | The `_dirty_outside_store` docstring says it works "exactly as `_ancestor_and_clean` already does". `_ancestor_and_clean` now delegates to it, so the claim is circular. | skills/run-autopilot/cli/verification.py:107 | 12 | ALICE |
| R12 | [1/4] | ⚪ | `open(log_path, "wb", buffering=0)` returns a raw `FileIO`, so `sink.write(chunk)` can write fewer bytes than asked, and `_drain_bounded` ignores the return value. The log can then silently lose bytes, against the "every byte" contract. The risk is low on regular files. Fix: wrap the write in a loop, or use `BufferedWriter` and flush per chunk. | skills/run-autopilot/cli/verification.py:252 | 12 | ALICE |
| R13 | [1/4] | ⚪ | The new tests do not sit where the Acceptance lines name them. The spec says nine tests live in `test_verification.py`. They live in a new file, `skills/run-autopilot/cli/test_verification_dirty.py`, which is not in the spec's file list. It is registered in `dev/bin/release-checks` and `_REVIEW_VERB_TEST_FILES`, and all 38 tests in it pass. This is a structural deviation only. | skills/run-autopilot/cli/test_verification_dirty.py:302 | 1 | BLAKE |
| R14 | [1/4] | ⚪ | `run_gate_line` returns `"log"` only on the run path. The reuse branch returns no `log` key, but the spec adds `"log"` to `summary["gate"]` and `review-work-completion/SKILL.md:181` documents `gate.log`. A consumer reading `gate["log"]` on a reused gate would get a KeyError or a missing key. | skills/run-autopilot/cli/review_stage.py:360 | 15 | BLAKE |
| R15 | [1/4] | ⚪ | `run_gate` opens and truncates `log_path` before the pre-spawn dirty check. A refused run therefore destroys the previous run's log at the same path. `gate-<cycle_id>.log` and `gate-<sha7>.log` repeat across reruns. The comment at `final-verification.md:115` documents the ordering but not the truncation. | skills/run-autopilot/cli/verification.py:348 | 3 | BLAKE |
| R16 | [1/4] | ⚪ | A refused dirty gate still reaches Blake with the instruction not to rerun. In that case the Test gate block reads "Tests: (gate skipped: working tree dirty outside the store)", and the new sentence in `agents/blake.md` tells him not to rerun the suite. That is spec-faithful, but he gets no suite result to rely on. | agents/blake.md:15 | 15 | BLAKE |
| R17 | [1/4] | ⚪ | `normalize_command` is declared `(command: str)` in the spec, but the implementation takes `object` and maps a non-str to "". It is harmless and defensive. | skills/run-autopilot/cli/verification.py:146 | 1 | BLAKE |
| R18 | [1/4] | ⚪ | Cannot statically verify: focused gate regressions pass independently of global Git configuration. Run `GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_NOSYSTEM=1 uv run --no-project --with pytest python -m pytest -q skills/run-autopilot/cli/test_cli_review_verbs.py skills/run-autopilot/cli/test_review_stage.py skills/run-autopilot/cli/test_verification*.py`. | N/A | general | BOB |
| R19 | [1/4] | 🟡 | 1 touched test(s) pass against the pre-change code: test_verify_dirtied_during_the_run_still_reports_the_process_exit | skills/run-autopilot/cli/test_cli_review_verbs.py | general | mech-check |
| R20 | [1/4] | 🟡 | 1 touched test(s) pass against the pre-change code: test_stage_renders_the_dirty_tests_line_when_the_tree_is_dirty | skills/run-autopilot/cli/test_review_stage.py | general | mech-check |
| R21 | [1/4] | 🟡 | 1 touched test(s) pass against the pre-change code: test_no_change_is_not_equal_to_any_dict | skills/run-autopilot/cli/test_state_no_change.py | general | mech-check |
| R22 | [1/4] | 🟡 | 1 touched test(s) pass against the pre-change code: test_gate_timeout_default_lets_a_real_suite_finish | skills/run-autopilot/cli/test_verification.py | general | mech-check |
| R23 | [1/4] | 🟡 | 38 touched test(s) pass against the pre-change code: test_reuse_when_only_store_paths_changed, test_stale_when_code_changed, test_reuse_verdict_fails_closed_on_git_error, test_reuse_verdict_rejects_non_ancestor_sha, test_reuse_verdict_rejects_dirty_tree, test_rename_out_of_store_is_not_clean +32 more | skills/run-autopilot/cli/test_verification_dirty.py | general | mech-check |
| R24 | [1/4] | 🟡 | 1 touched test(s) pass against the pre-change code: test_gate_output_is_read_from_the_log_not_a_rerun | skills/work/scripts/test_gate_record_writer_prose.py | general | mech-check |
| R25 | [1/4] | 🟡 | 1 touched test(s) pass against the pre-change code: test_zero_tasks_is_delivered_where_tasks_are_actually_created | skills/work/scripts/test_verify_queue_prose.py | general | mech-check |
| R26 | [1/4] | ⚪ | Cycle 1's queued verification check carries no `result` in `00270-trust-only-real-gate-runs-v1-checks-1.json`, so it is carried forward: `GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_NOSYSTEM=1 uv run --no-project --with pytest python -m pytest -q ...` (the seven cycle-1 modules). | docs/dev/project-management/reviews/00270-trust-only-real-gate-runs-v1-checks-1.json | general | verify-check |

## Alice

Consensus lens, implementation-aware. Confirmed 15 of the 27 cycle-1 findings
resolved (R3, R4, R5, R7, R8, R9, R11, R13a, R14, R16, R18, R19, R20, R21, R22,
R23). Raised 9 findings (2 🟠, 3 🟡, 4 ⚪): the unguarded log-sink `OSError` still
leaking the gate process group (prior R6, half fixed), the still-untested
`except OSError` verb branch (prior R1a), an either-or hedge in the new
log-failure test, `test_review_stage.py` newly over the 800-line cap, `run_gate`
still at 61 lines (prior R2), the R12 assertion pinning the wrong sentence, a
circular docstring, copy-paste leftovers in the new test module, and short-write
risk from `buffering=0`. She verified by running the touched suites with
`GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_NOSYSTEM=1` (182 passed, 0 skipped) and
`ruff --select F` clean. She did not re-raise any settled item.

R1: fail
R2: fail
R3: pass
R4: pass
R6: pass
R7: pass
R8: pass
R9: pass
R10: fail
R11: pass
R12: fail
R13: fail

## Blake

Blind lens, PRD-only. Raised 8 findings (3 🟡, 5 ⚪) and dropped his cycle-1
central claim: B1 now passes. His remaining findings are the orphaned gate child
on a log-write `OSError`, exit 1 conflating a dirty refusal with a red suite in
the prose, `recorded: false` being invisible to a session, the new tests living
in a file the Acceptance lines do not name, the missing `log` key on the reuse
branch, pre-check log truncation, Blake's own no-rerun instruction on a refused
gate, and `normalize_command`'s widened signature. He ran `bash
dev/bin/release-checks` himself: `PASS 3001 FAIL 0 SKIP 0 EXIT 0`, plus 144 and
38 passed on the focused modules. Nothing he raised matched a ledger entry, so
`--ledger-dismiss BLAKE` dismissed nothing.

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
B14: fail
B15: pass
B16: pass
B17: pass
B18: pass
B19: pass

## Bob

Doubt + de-slop lens (codex, resumed from the cycle-1 thread). FIX bucket: 8
findings (1 🟠, 7 🟡) — the log-sink `OSError` still bypassing `_reap`, short
writes under unbuffered `FileIO`, the missing CLI test for the log-error exit-2
response, the either-or hedge in the new error test, `run_gate` at 61 lines,
`test_review_stage.py` at 802 lines, duplicated fixtures in the split test
module, and the R12 assertion still unpinned at phase-review.md:305. VERIFY
bucket: one item, queued to
`00270-trust-only-real-gate-runs-v1-checks-2.json`. KNOWN: none.

R1: fail
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

D1: pass
D2: pass
D3: pass
D4: pass
D5: pass

## Carl

Frontend & design specialist, generalist here (gemini-run.sh on the copilot
backend, `gemini-3.8-flash`). Raised 3 findings (1 🟠, 2 🟡), all already seen by
others: the untested `except OSError` verb branch, `run_gate` at 61 lines, and
`test_review_stage.py` at 802 lines. He ran the focused suites with a clean git
config and `dev/bin/release-checks`, and confirmed the two size breaches with
`check_style_limits.py --diff`.

R1: fail
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

Verdict: 26 findings
Tests: 3001 passed, 0 failed, 0 skipped (suite run this cycle)
