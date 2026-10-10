---
prd: docs/dev/project-management/prds/wip/00270-trust-only-real-gate-runs-v1.md
review: 1
date: 2026-10-10
head_sha: 07fa37c3e205feac1e0e952d7b9778a393e48e3c
codex_thread_id: 01a125bf-3c30-7d53-b23d-8dcfe3b7cac2
reviewers: alice,blake,bob,carl
agents:
  alice: available
  blake: available
  bob: available
  carl: available
dispatch_rows:
  bob: 4c375937
  carl: 0281eb16
---

# Review: 00270-trust-only-real-gate-runs-v1

Diff range: `8f0d43faad364b82bfffeb8f14bf35b508432819..07fa37c3e205feac1e0e952d7b9778a393e48e3c`

codex_rung_guard: not fired

Consolidation note: `consolidate_findings.py` anchors its issue-line pattern at
`^[`, and Bob emitted his issue lines as `- [BOB] …` markdown bullets, so the
first consolidation run silently dropped the whole doubt lens. The bullet
prefixes were stripped from `bob-output-00270-c1.txt` and the script re-run; the
table below is that second run, with Bob's findings included. Pack: ok.

## Consolidated Findings

| Ref | Consensus | Severity | Issue | File | Task | Found By |
|-----|-----------|----------|-------|------|------|----------|
| R1 | [3/4] | 🟠 | `autopilot verify` has two untested paths: (a) the `except OSError` branch that prints `{"sha","log","error"}` and exits 2; (b) a run that dirties the tree mid-run, which exits 0 with `recorded:false, dirty:true` and is only tested at the run_gate level. Add a verb-level test for each. | skills/run-autopilot/cli/__main__.py:963 | 7 | ALICE, BLAKE, CARL |
| R2 | [3/4] | 🟡 | run_gate is about 70 lines including its docstring (verification.py:315-384), over the 50-line limit. Simplification: move the summary-line parse loop into a `_parse_summary(stdout_buf)` helper returning `(raw_line, found)`, and shrink the docstring. | skills/run-autopilot/cli/verification.py:315 | 3 | ALICE, BOB, CARL |
| R3 | [3/4] | 🟡 | test_verification.py is now 905 lines (800-line cap), grown by about 330 lines in this diff. Split the new normalize, tree-to-tree and dirty-refusal tests into a focused module, e.g. test_verification_dirty.py (register it in dev/bin/release-checks and _REVIEW_VERB_TEST_FILES). | skills/run-autopilot/cli/test_verification.py:1 | 3 | ALICE, BOB, CARL |
| R4 | [2/4] | 🟠 | verify tests are not hermetic: the `repo` fixture has no .gitignore, so the default log skills/run-autopilot/cli/ docs/dev/tmp/gate-<sha>.log is an untracked path outside the store and run_gate refuses as dirty. The tests only pass because ~/.gitignore_global ignores docs/dev/tmp/. Replayed with `env GIT_CONFIG_GLOBAL=/dev/null ... pytest -k verify`: 2 failed (test_verify_runs_the_gate_once_and_writes_the_record_and_log gets exit 1 and dirty:true; test_verify_exits_1_on_a_red_gate gets exit None). Fix: commit a `.gitignore` with `docs/dev/tmp/` in the fixture, as test_review_stage.py:76 does. | skills/run-autopilot/cli/test_cli_review_verbs.py:332 | 7 | ALICE, BOB |
| R5 | [2/4] | 🟠 | Dirty-first Tests-line branch in run_gate_line has no test. The PRD design's test strategy lists the `(gate skipped: working tree dirty outside the store)` line, but test_review_stage.py only covers the clean path, the Blake block and the log key. Removing the branch would fall through to "counts unavailable" with no test failing. | skills/run-autopilot/cli/review_stage.py:374 | 8 | ALICE, BLAKE |
| R6 | [2/4] | 🟠 | `_drain_bounded` writes to the log sink with no OSError guard (verification.py:254-255). A disk-full or write error mid-run raises out of `run_gate` before `_reap`, leaving the gate's process group running. `review_stage.run_gate_line` does not catch the OSError from opening the log (verification.py:346), so a log open failure crashes `review-stage`. `verify` does catch it and exits 2. | skills/run-autopilot/cli/verification.py:254 | 3 | BLAKE, BOB |
| R7 | [2/4] | 🟡 | `_run_verify` HEAD resolution only checks the return code. A nonexistent `--repo-root` or a missing git binary raises FileNotFoundError from `subprocess.run` as a bare traceback, not the documented "exit 2". Wrap it in `try/except OSError` and return 2. | skills/run-autopilot/cli/__main__.py:946 | 7 | ALICE, BOB |
| R8 | [2/4] | 🟡 | rework_groups.py carries unrelated formatter reflow in a task meant to be comment-only. The `_LINE_SUFFIX` regex is split across lines (rework_groups.py:26-28) and a trailing comma is added after the sort key tuple in `group()`. Revert both and keep only the `# ponytail:` comment. | skills/run-autopilot/cli/rework_groups.py:26 | 5 | ALICE, BLAKE |
| R9 | [2/4] | ⚪ | agent-invocation.md names `run_stage.run_gate_line`. No such module exists; it is `review_stage.run_gate_line`. | skills/review-work-completion/references/agent-invocation.md:78 | 8 | ALICE, BLAKE |
| R10 | [1/4] | 🟠 | `run_gate` returns before spawning when the pre-run dirty check fires, so the gate never runs on a tree dirty outside the store. The spec has the gate run and only withholds the record (Test Strategy: "gate runs over an uncommitted product edit ... no record from that run"; Risks: a project that does not ignore docs/dev/tmp "fails safe (a rerun)"). The implementation opens the log first (verification.py:345-346), then calls `_dirty_outside_store` (verification.py:348-349) and returns `_dirty_result()`. In a repo that does not ignore `docs/dev/tmp`, the log file `autopilot verify` just created is itself untracked product-side dirt. So `autopilot verify` and `review-stage` NEVER run the suite there. I reproduced it with `GIT_CONFIG_GLOBAL=/dev/null` and `GIT_CONFIG_SYSTEM=/dev/null` on `test_cli_review_verbs.py -k verify`. The verify output was `{"exit": null, "dirty": true, "recorded": false}`, and `test_verify_runs_the_gate_once_and_writes_the_record_and_log` and `test_verify_exits_1_on_a_red_gate` failed. | skills/run-autopilot/cli/verification.py:343 | 3 | BLAKE |
| R11 | [1/4] | 🟠 | The `verify` tests in `test_cli_review_verbs.py` pass only because this host's global gitignore ignores `docs/dev/tmp`. The `repo` fixture (test_cli_review_verbs.py:331-338) writes no `.gitignore`, unlike the `test_review_stage.py` fixture, which the spec says does. A CI machine or another contributor's machine fails two of the four Phase 1 acceptance tests: `test_verify_runs_the_gate_once_and_writes_the_record_and_log` and `test_verify_exits_1_on_a_red_gate`. | skills/run-autopilot/cli/test_cli_review_verbs.py:331 | 12 | BLAKE |
| R12 | [1/4] | 🟡 | Out-of-scope edit weakens an assertion. test_zero_tasks_is_delivered_where_tasks_are_actually_created changed from the exact string `` `"verify"` and `"discard"` rows create nothing `` to `` `"verify"` in phase_review and "rows create nothing" in phase_review ``. This is not one of the four assertions the task named, and phase-review.md is untouched by this diff. The test also passes against base. The old string was stale since 00269 (phase-review.md:305 now reads `"verify"`, `"discard"` and `"carry"` rows create nothing). Pin the current sentence instead of loosening. | skills/work/scripts/test_verify_queue_prose.py:273 | 9 | ALICE, mech-check |
| R13 | [1/4] | 🟡 | Tautological or constant asserts. (a) test_gate_output_is_read_from_the_log_not_a_rerun: the first assert `"rg" in verification and "log" in verification` holds for any prose ("rg" is a substring of "target", "args" and similar); drop it and keep the phrase pin. (b) test_no_change_is_an_object_compared_only_by_identity: `assertIsInstance(x, object)` is always true, and `assertIsNot(object(), {})` and `assertIsNot(object(), None)` cannot fail. Replace with a check that NO_CHANGE is not equal to any dict (`NO_CHANGE != {}`, `not isinstance(NO_CHANGE, dict)`) or delete it. | skills/work/scripts/test_gate_record_writer_prose.py:66 | 9 | ALICE |
| R14 | [1/4] | 🟡 | Same constant-assert shape in the sentinel test (see above). | skills/run-autopilot/cli/test_state_no_change.py:48 | 4 | ALICE |
| R15 | [1/4] | 🟡 | More tests were moved from tmp_path to repo than the task premise allows ("move exactly those that assert a write"). Moved without asserting a write: drains_stderr_without_deadlock, uses_last_summary_line_not_first, streams_and_keeps_tail, closes_the_child_pipes_before_returning (also rewritten to filter Popen args). The move is defensible for the `not exists` tests, which would otherwise pass vacuously outside a git repo. The set difference is not reported anywhere. | skills/run-autopilot/cli/test_verification.py:202 | 3 | ALICE, mech-check |
| R16 | [1/4] | 🟡 | Step 7 still schedules "Recorded verification result" after the suite, but that section now runs the suite itself, directing two full runs. Make `autopilot verify` the initial suite invocation and update final-verification.md's unchanged full-suite bullet accordingly. | skills/work/SKILL.md:475 | 9 | BOB |
| R17 | [1/4] | 🟡 | The new log-open error response and review-stage dirty-first rendering branch have no regression tests. Add tests asserting exit 2 with one JSON error line, and dirty rendering without timeout or fabricated counts. | skills/run-autopilot/cli/test_review_stage.py:242 | general | BOB |
| R18 | [1/4] | 🟡 | The sentinel identity test checks Python truisms: every value is an object, and the newly constructed dict cannot be the sentinel. It never exercises identity comparison in transaction. Remove this test or replace it with a behavioral identity-boundary test; also remove the unused `schema` import. | skills/run-autopilot/cli/test_state_no_change.py:48 | 4 | BOB |
| R19 | [1/4] | 🟡 | _ancestor_and_clean duplicates git status and store filtering already implemented in _dirty_outside_store | skills/run-autopilot/cli/verification.py:98 | 2 | CARL |
| R20 | [1/4] | ⚪ | final-verification.md misdescribes the verb. "the verb's own reuse-or-run contract" is wrong, because `autopilot verify` always runs and never reuses. The sentence "untrusted-input and budget rules aside, a second run can land on a different tree" is a non sequitur. | skills/work/references/final-verification.md:111 | 9 | ALICE |
| R21 | [1/4] | ⚪ | The log sink is a buffered file. `_drain_bounded` writes chunks to `log_file` opened with `open(log_path, "wb")` and never flushes, so a live `rg`/tail on the printed log sees nothing until the run ends or the buffer fills. Consider `buffering=0` or a flush per chunk if the log is meant to be readable mid-run. | skills/run-autopilot/cli/verification.py:253 | 3 | ALICE |
| R22 | [1/4] | ⚪ | The verb's own log makes the tree dirty when `docs/dev/tmp/` is not ignored. The log is opened before the pre-spawn dirty check, so on a downstream project without that ignore, `autopilot verify` never records. The design accepts this as fail-safe, but the prose in final-verification.md and work/SKILL.md never says to ignore `docs/dev/tmp/` first. A one-line note would save an operator a confusing `dirty:true`. | skills/work/references/final-verification.md:103 | 9 | ALICE |
| R23 | [1/4] | ⚪ | The `reuse_verdict` docstring still describes the old mechanism: `git log <sha>..<head> --name-only`, and `git status --porcelain=1 -z` without `--untracked-files=all` (verification.py:181-185). The code now uses `git diff --name-only --no-renames -z` and `-uall`. | skills/run-autopilot/cli/verification.py:181 | 2 | BLAKE |
| R24 | [1/4] | ⚪ | Cannot statically verify: tests pass independently of machine Git configuration. Run `GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_NOSYSTEM=1 uv run --no-project --with pytest python -m pytest -q skills/run-autopilot/cli/test_cli_review_verbs.py skills/run-autopilot/cli/test_verification.py skills/run-autopilot/cli/test_state_no_change.py skills/run-autopilot/cli/test_review_stage.py skills/work/scripts/test_gate_record_writer_prose.py skills/work/scripts/test_verify_queue_prose.py skills/work/scripts/test_command_budget_prose.py`. | N/A | general | BOB |
| R25 | [1/4] | ⚪ | File __main__.py has 1792 lines, exceeding the 800-line file limit | skills/run-autopilot/cli/__main__.py:1792 | 7 | CARL |
| R26 | [1/4] | 🟡 | 1 touched test(s) pass against the pre-change code: test_blake_prompt_has_no_test_gate_block_without_one_in_the_context | skills/run-autopilot/cli/test_review_stage.py | general | mech-check |
| R27 | [1/4] | 🟡 | 2 touched test(s) pass against the pre-change code: test_a_changing_transaction_still_refreshes_the_backup, test_mutate_still_writes_and_returns_outcome_when_apply_changes_state | skills/run-autopilot/cli/test_state_no_change.py | general | mech-check |

## Alice

Consensus lens, implementation-aware. Raised 16 findings (2 🟠, 10 🟡, 4 ⚪),
dominated by missing verb-level tests around `autopilot verify`, the
non-hermetic `repo` fixture (replayed with `GIT_CONFIG_GLOBAL=/dev/null`, 2
failures), out-of-scope test weakening in `test_verify_queue_prose.py`, the
surviving `rework_groups.py` reflow, and two size-limit breaches (`run_gate` at
~70 lines, `test_verification.py` at 905).

R1: fail
R2: fail
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

## Blake

Blind lens, PRD-only. Raised 9 findings (3 🟠, 4 🟡, 2 ⚪). His central claim is
a spec deviation: `run_gate` returns before spawning on a pre-run dirty tree,
while the PRD's Test Strategy and Risks sections have the gate run and only
withhold the record. He reproduced the consequence with
`GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_SYSTEM=/dev/null` (`{"exit": null,
"dirty": true, "recorded": false}`, two test failures). He also flags the
`Tests: (gate skipped: ...)` line not matching `TESTS_RE`, the missing `log` key
on the reuse path, and exit 1 conflating a dirty refusal with a red suite.

Verified as correct: `normalize_command` on both paths, the `git diff
--name-only --no-renames -z` change list, `-uall` on status, `NO_CHANGE`
short-circuiting the validator/backup/write, `statectl.mutate` pass-through,
`review_close._close_mutator`'s already-applied return, the Blake sentence in
`agents/blake.md:15`, the `## Blake: Test gate` section, no prose telling a
session to write `last-verification.json`, the ponytail comment, the 00266 audit
entry, the CHANGELOG lines, and both new test modules registered in
`dev/bin/release-checks` and `_REVIEW_VERB_TEST_FILES`. He ran 8 suites himself
(178 passed) but not the full gate.

B1: fail
B2: pass
B3: pass
B4: pass
B5: pass
B6: fail
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

Doubt + de-slop lens (codex). FIX bucket: 8 findings (1 🟠, 7 🟡) — the
unguarded log-sink OSError leaking the gate process group, unguarded HEAD
resolution, the double full-suite run directed by `work/SKILL.md` step 7, the
non-hermetic CLI fixture, missing regression tests for the log-open error and
the dirty-first rendering branch, `run_gate` over the line limit,
`test_verification.py` over the file limit, and the truism-only sentinel test
(plus its unused `schema` import). VERIFY bucket: one item, queued to
`00270-trust-only-real-gate-runs-v1-checks-1.json`. KNOWN: none.

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
R12: fail
R13: fail

D1: pass
D2: pass
D3: pass
D4: pass
D5: pass

## Carl

Frontend & design specialist, generalist here (gemini/copilot backend). Raised 5
findings (1 🟠, 3 🟡, 1 ⚪): `_run_verify` exiting 0 on a tree the gate command
dirtied mid-run, `run_gate` and `test_verification.py` over their size limits,
`_ancestor_and_clean` duplicating `_dirty_outside_store`'s status-and-filter
logic, and `__main__.py` at 1792 lines.

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

Verdict: 27 findings
Tests: 2995 passed, 0 failed, 0 skipped (suite run this cycle)
