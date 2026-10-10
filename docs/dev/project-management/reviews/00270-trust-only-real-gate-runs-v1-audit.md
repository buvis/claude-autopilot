# Decision Audit Log: 00270-trust-only-real-gate-runs-v1

PRD: `00270-trust-only-real-gate-runs-v1.md`
Started: 2026-10-10T13:35:06Z
Completed: 2026-10-10T13:35:06Z
Autonomous: 25  |  Deferred: 28  |  Doubts: 0

### [autonomous] 2026-10-10T13:35:06Z

**Decision**: `autopilot verify` has two untested paths: (a) the `except OSError` branch that prints `{"sha","log","error"}` and exits 2; (b) a run that dirties the tree mid-run, which exits 0 with `recorded:false, dirty:true` and is only tested at the run_gate level. Add a verb-level test for each.

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-10-10T13:35:06Z

**Decision**: verify tests are not hermetic: the `repo` fixture has no .gitignore, so the default log docs/dev/tmp/gate-<sha>.log is an untracked path outside the store and run_gate refuses as dirty. The tests only pass because ~/.gitignore_global ignores docs/dev/tmp/. Fix: commit a `.gitignore` with `docs/dev/tmp/` in the fixture, as test_review_stage.py:76 does.

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-10-10T13:35:06Z

**Decision**: Dirty-first Tests-line branch in run_gate_line has no test. The PRD design's test strategy lists the `(gate skipped: working tree dirty outside the store)` line, but test_review_stage.py only covers the clean path, the Blake block and the log key. Removing the branch would fall through to "counts unavailable" with no test failing.

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-10-10T13:35:06Z

**Decision**: `_drain_bounded` writes to the log sink with no OSError guard. A disk-full or write error mid-run raises out of `run_gate` before `_reap`, leaving the gate's process group running. `review_stage.run_gate_line` does not catch the OSError from opening the log, so a log open failure crashes `review-stage`. `verify` does catch it and exits 2.

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-10-10T13:35:06Z

**Decision**: The `verify` tests in `test_cli_review_verbs.py` pass only because this host's global gitignore ignores `docs/dev/tmp`. A CI machine or another contributor's machine fails two of the four Phase 1 acceptance tests: `test_verify_runs_the_gate_once_and_writes_the_record_and_log` and `test_verify_exits_1_on_a_red_gate`.

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-10-10T13:35:06Z

**Decision**: run_gate is about 70 lines including its docstring (verification.py:315-384), over the 50-line limit. Simplification: move the summary-line parse loop into a `_parse_summary(stdout_buf)` helper returning `(raw_line, found)`, and shrink the docstring.

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-10-10T13:35:06Z

**Decision**: test_verification.py is now 905 lines (800-line cap), grown by about 330 lines in this diff. Split the new normalize, tree-to-tree and dirty-refusal tests into a focused module, e.g. test_verification_dirty.py (register it in dev/bin/release-checks and _REVIEW_VERB_TEST_FILES).

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-10-10T13:35:06Z

**Decision**: `_run_verify` HEAD resolution only checks the return code. A nonexistent `--repo-root` or a missing git binary raises FileNotFoundError from `subprocess.run` as a bare traceback, not the documented "exit 2". Wrap it in `try/except OSError` and return 2.

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-10-10T13:35:06Z

**Decision**: rework_groups.py carries unrelated formatter reflow in a task meant to be comment-only. The `_LINE_SUFFIX` regex is split across lines (rework_groups.py:26-28) and a trailing comma is added after the sort key tuple in `group()`. Revert both and keep only the `# ponytail:` comment.

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-10-10T13:35:06Z

**Decision**: agent-invocation.md names `run_stage.run_gate_line`. No such module exists; it is `review_stage.run_gate_line`.

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-10-10T13:35:06Z

**Decision**: Out-of-scope edit weakens an assertion. test_zero_tasks_is_delivered_where_tasks_are_actually_created changed from an exact string to two loose substring checks. This is not one of the four assertions the task named, and phase-review.md is untouched by this diff. The test also passes against base. Pin the current sentence instead of loosening.

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-10-10T13:35:06Z

**Decision**: Tautological or constant asserts. (a) test_gate_output_is_read_from_the_log_not_a_rerun: the first assert `"rg" in verification and "log" in verification` holds for any prose; drop it and keep the phrase pin. (b) test_no_change_is_an_object_compared_only_by_identity: `assertIsInstance(x, object)` is always true, and `assertIsNot(object(), {})` and `assertIsNot(object(), None)` cannot fail. Replace with a check that NO_CHANGE is not equal to any dict or delete it.

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-10-10T13:35:06Z

**Decision**: Same constant-assert shape in the sentinel test (see above).

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-10-10T13:35:06Z

**Decision**: The sentinel identity test checks Python truisms: every value is an object, and the newly constructed dict cannot be the sentinel. It never exercises identity comparison in transaction. Remove this test or replace it with a behavioral identity-boundary test; also remove the unused `schema` import.

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-10-10T13:35:06Z

**Decision**: More tests were moved from tmp_path to repo than the task premise allows ("move exactly those that assert a write"). Moved without asserting a write: drains_stderr_without_deadlock, uses_last_summary_line_not_first, streams_and_keeps_tail, closes_the_child_pipes_before_returning. The set difference is not reported anywhere.

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-10-10T13:35:06Z

**Decision**: Step 7 still schedules "Recorded verification result" after the suite, but that section now runs the suite itself, directing two full runs. Make `autopilot verify` the initial suite invocation and update final-verification.md's unchanged full-suite bullet accordingly.

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-10-10T13:35:06Z

**Decision**: The new log-open error response and review-stage dirty-first rendering branch have no regression tests. Add tests asserting exit 2 with one JSON error line, and dirty rendering without timeout or fabricated counts.

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-10-10T13:35:06Z

**Decision**: _ancestor_and_clean duplicates git status and store filtering already implemented in _dirty_outside_store

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-10-10T13:35:06Z

**Decision**: final-verification.md misdescribes the verb. "the verb's own reuse-or-run contract" is wrong, because `autopilot verify` always runs and never reuses. The sentence "untrusted-input and budget rules aside, a second run can land on a different tree" is a non sequitur.

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-10-10T13:35:06Z

**Decision**: The log sink is a buffered file. `_drain_bounded` writes chunks to `log_file` opened with `open(log_path, "wb")` and never flushes, so a live `rg`/tail on the printed log sees nothing until the run ends or the buffer fills. Consider `buffering=0` or a flush per chunk if the log is meant to be readable mid-run.

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-10-10T13:35:06Z

**Decision**: The verb's own log makes the tree dirty when `docs/dev/tmp/` is not ignored. The log is opened before the pre-spawn dirty check, so on a downstream project without that ignore, `autopilot verify` never records. The prose in final-verification.md and work/SKILL.md never says to ignore `docs/dev/tmp/` first. A one-line note would save an operator a confusing `dirty:true`.

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-10-10T13:35:06Z

**Decision**: The `reuse_verdict` docstring still describes the old mechanism: `git log <sha>..<head> --name-only`, and `git status --porcelain=1 -z` without `--untracked-files=all`. The code now uses `git diff --name-only --no-renames -z` and `-uall`.

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-10-10T13:35:06Z

**Decision**: 1 touched test(s) pass against the pre-change code: test_blake_prompt_has_no_test_gate_block_without_one_in_the_context

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-10-10T13:35:06Z

**Decision**: Cannot statically verify: tests pass independently of machine Git configuration.

**Choice**: routed to verification

**Rationale**: queued in 00270-trust-only-real-gate-runs-v1-checks-1.json; command: GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_NOSYSTEM=1 uv run --no-project --with pytest python -m pytest -q skills/run-autopilot/cli/test_cli_review_verbs.py skills/run-autopilot/cli/test_verification.py skills/run-autopilot/cli/test_state_no_change.py skills/run-autopilot/cli/test_review_stage.py skills/work/scripts/test_gate_record_writer_prose.py skills/work/scripts/test_verify_queue_prose.py skills/work/scripts/test_command_budget_prose.py - runs in the rework work pass step 7

### [autonomous] 2026-10-10T13:35:06Z

**Decision**: 2 touched test(s) pass against the pre-change code: test_a_changing_transaction_still_refreshes_the_backup, test_mutate_still_writes_and_returns_outcome_when_apply_changes_state

**Choice**: discarded

**Rationale**: both are deliberate behavior-preserving guards (their names say still): they pin that the NO_CHANGE sentinel did not change the changing-transaction path, so passing against base is their purpose

### [deferred] 2026-10-10T13:35:06Z

**Decision**: `run_gate` returns before spawning when the pre-run dirty check fires, so the gate never runs on a tree dirty outside the store.

**Rationale**: deferred by review-close

### [deferred] 2026-10-10T13:35:06Z

**Decision**: File __main__.py has 1792 lines, exceeding the 800-line file limit

**Rationale**: deferred by review-close

### [deferred] 2026-10-10T13:35:06Z

**Decision**: Prior R6 half fixed: _drain_bounded still writes to the log sink with no OSError guard, so a write error raises out of run_gate before _reap and leaks the gate process group.

**Rationale**: rework cap reached with this finding unresolved

### [deferred] 2026-10-10T13:35:06Z

**Decision**: Prior R1(a) still unfixed: the except OSError branch in _run_verify that prints {sha,log,error} and exits 2 has no verb-level test.

**Rationale**: rework cap reached with this finding unresolved

### [deferred] 2026-10-10T13:35:06Z

**Decision**: test_review_stage.py is now 802 lines, a new breach of the 800-line cap in this diff.

**Rationale**: rework cap reached with this finding unresolved

### [deferred] 2026-10-10T13:35:06Z

**Decision**: Prior R2 partly resolved: run_gate is still 61 lines, over the 50-line limit.

**Rationale**: rework cap reached with this finding unresolved

### [deferred] 2026-10-10T13:35:06Z

**Decision**: test_gate_log_write_failure_degrades_instead_of_crashing ends in an either-or hedge, so neither branch pins behavior.

**Rationale**: rework cap reached with this finding unresolved

### [deferred] 2026-10-10T13:35:06Z

**Decision**: The R12 fix pins the phase-review.md:193 parenthetical instead of the Phase 6 sentence at :305 that R12 named.

**Rationale**: rework cap reached with this finding unresolved

### [deferred] 2026-10-10T13:35:06Z

**Decision**: test_verification_dirty.py cites PRD 00249 in its docstring and duplicates _git/_commit/repo/_record from test_verification.py; STORE_PREFIX is now unused there.

**Rationale**: rework cap reached with this finding unresolved

### [deferred] 2026-10-10T13:35:06Z

**Decision**: A dirty-tree refusal exits 1, the same code as a red suite, and the prose never tells a session to read the recorded/dirty keys or to commit first.

**Rationale**: rework cap reached with this finding unresolved

### [deferred] 2026-10-10T13:35:06Z

**Decision**: autopilot verify exits 0 with recorded:false when the tree was dirtied mid-run, and the prose never says to check recorded.

**Rationale**: rework cap reached with this finding unresolved

### [deferred] 2026-10-10T13:35:06Z

**Decision**: Unbuffered FileIO allows short writes and _drain_bounded ignores the returned byte count, so log output can be silently truncated.

**Rationale**: rework cap reached with this finding unresolved

### [deferred] 2026-10-10T13:35:06Z

**Decision**: _dirty_outside_store's docstring claims it works exactly as _ancestor_and_clean, which now delegates to it - a circular claim.

**Rationale**: rework cap reached with this finding unresolved

### [deferred] 2026-10-10T13:35:06Z

**Decision**: open(log_path, 'wb', buffering=0) returns a raw FileIO whose short writes are ignored, against the every-byte contract.

**Rationale**: rework cap reached with this finding unresolved

### [deferred] 2026-10-10T13:35:06Z

**Decision**: The nine new tests live in test_verification_dirty.py, a file the Acceptance lines do not name (registered and passing; structural deviation only).

**Rationale**: rework cap reached with this finding unresolved

### [deferred] 2026-10-10T13:35:06Z

**Decision**: run_gate_line returns the log key only on the run path; the reuse branch omits it although the spec and SKILL.md document gate.log.

**Rationale**: rework cap reached with this finding unresolved

### [deferred] 2026-10-10T13:35:06Z

**Decision**: run_gate truncates log_path before the pre-spawn dirty check, so a refused run destroys the previous run's log at the same path.

**Rationale**: rework cap reached with this finding unresolved

### [deferred] 2026-10-10T13:35:06Z

**Decision**: On a refused dirty gate Blake is told not to rerun the suite but gets no suite result to rely on.

**Rationale**: rework cap reached with this finding unresolved

### [deferred] 2026-10-10T13:35:06Z

**Decision**: normalize_command is specced as (command: str) but implemented as (command: object) mapping non-str to '' (harmless, defensive).

**Rationale**: rework cap reached with this finding unresolved

### [deferred] 2026-10-10T13:35:06Z

**Decision**: VERIFY item queued to checks-2.json: confirm the focused gate regressions pass independently of global Git configuration.

**Rationale**: rework cap reached with this finding unresolved

### [deferred] 2026-10-10T13:35:06Z

**Decision**: mech-check: test_verify_dirtied_during_the_run_still_reports_the_process_exit passes against the pre-change code.

**Rationale**: rework cap reached with this finding unresolved

### [deferred] 2026-10-10T13:35:06Z

**Decision**: mech-check: test_stage_renders_the_dirty_tests_line_when_the_tree_is_dirty passes against the pre-change code.

**Rationale**: rework cap reached with this finding unresolved

### [deferred] 2026-10-10T13:35:06Z

**Decision**: mech-check: test_no_change_is_not_equal_to_any_dict passes against the pre-change code.

**Rationale**: rework cap reached with this finding unresolved

### [deferred] 2026-10-10T13:35:06Z

**Decision**: mech-check: test_gate_timeout_default_lets_a_real_suite_finish passes against the pre-change code.

**Rationale**: rework cap reached with this finding unresolved

### [deferred] 2026-10-10T13:35:06Z

**Decision**: mech-check: 38 touched tests in the split module pass against the pre-change code (they were moved, so this may be expected - unverified).

**Rationale**: rework cap reached with this finding unresolved

### [deferred] 2026-10-10T13:35:06Z

**Decision**: mech-check: test_gate_output_is_read_from_the_log_not_a_rerun passes against the pre-change code.

**Rationale**: rework cap reached with this finding unresolved

### [deferred] 2026-10-10T13:35:06Z

**Decision**: mech-check: test_zero_tasks_is_delivered_where_tasks_are_actually_created passes against the pre-change code.

**Rationale**: rework cap reached with this finding unresolved

### [deferred] 2026-10-10T13:35:06Z

**Decision**: Cycle 1's queued verification check carries no result, so it is carried forward unrun.

**Rationale**: rework cap reached with this finding unresolved
