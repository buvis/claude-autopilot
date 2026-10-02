---
prd: dev/local/prds/wip/00218-leave-sessions-at-task-boundaries-and-run-one-devon-round-v1.md
review: 1
date: 2026-09-29
head_sha: e5a8479cb07bb3d9d62fbdb873aa4dab3b271c5e
reviewers: alice,blake,bob,carl
agents:
  alice: available
  blake: available
  bob: available
  carl: available
---

# Review: 00218-leave-sessions-at-task-boundaries-and-run-one-devon-round-v1

Diff range: `83165038f9dfd92ebf64ae94f38f61b946a17ee3..e5a8479cb07bb3d9d62fbdb873aa4dab3b271c5e`

codex_rung_guard: not fired

## Run conditions

- Lenses: consensus (Alice, legacy engine), blind (Blake), doubt + de-slop (Bob via codex), UI/generalist (Carl via gemini-run.sh). Eve not active: the codex doubt-roster guard did not fire, because no `state.tasks[].attempts[].implementor` is `codex` (all seven attempts are `claude`).
- Carl backend: `backend=copilot model=gemini-3.8-flash` (from `gemini-run.sh` stderr). Exit 0, non-empty review text.
- Bob: exit 0. `--emit-thread-id` wrote an EMPTY `bob-thread-00218-c1.txt`, so no `codex_thread_id` is stamped and cycle 2 runs Bob fresh rather than resuming his session.
- Consolidation: `consolidate_findings.py` (script, not model-side). It merged citations that matched only after suffix stripping on rows 1, 2, 3, 4 and 7.
- Ledger: none (cycle 1), so `--ledger` / `--ledger-dismiss` were not passed.
- pack: FAILED. `engram pack` exited 1 with `not inside a registered repo; register it in /Users/bob/.config/gita/repos.csv`. Not retried (the failure is a deterministic config gap, not transient). Every prompt that takes `{PACK_FILE}` / `{PACK_FINDINGS}` received the sentinel `(no pack available this cycle)`. The review is degraded by the missing retrieval context, not invalid.
- Diff scope: this is a FULL cycle-1 review over `work_start_sha..HEAD`. `gather-context.sh` was invoked with `--since <work_start_sha>` (so its own label reads "incremental") because autopilot commits straight to `master` here and the script's base detection resolves to HEAD, which would have produced an empty diff.
- Verification-check queue: NOT written this cycle. Eve did not run, and `agents/bob.md` defines no FIX/VERIFY/KNOWN buckets (`source: "bob"` is reserved), so no doubt lens emitted a VERIFY bucket to queue.

## Consolidated Findings

| Consensus | Severity | Issue | File | Task | Found By |
|-----------|----------|-------|------|------|----------|
| [4/4] | 🔴 | Time term is never wired into the hook. `_handle_below_cap` still calls `_headroom_exhausted(total, count, last_usage, last_calls)` with no `secs_left` or `last_wall`. The hook never reads `_AUTOPILOT_SESSION_DEADLINE` and never imports `last_task_wall` (only `last_task_cost, record_task_bounds` at line 72). The runner exports a deadline that nothing reads, and the stamps feed only the report, so the PRD's "session hands off before a task it cannot finish" does not exist at runtime. The tests call the predicate directly. `test_time_term_hands_off_when_the_deadline_is_near` and `test_malformed_deadline_drops_the_time_term` cannot fail if the wiring is missing, and no test drives the hook with a deadline. The hook file is exactly 800 lines, so the fix must move the deadline parse into a sibling module. | skills/run-autopilot/scripts/autopilot_context_cap_hook.py:585 | 4 | ALICE, BLAKE, BOB, CARL |
| [4/4] | 🟠 | `_task_wallclock_block` has no int guard, unlike `task_over_budget`. A string stamp raises `TypeError` and aborts the whole report. A negative span prints negative minutes. `int(... // 60)` wraps an already-int value. An absent model prints "None". | skills/run-autopilot/cli/render_report.py:589 | 6 | ALICE, BLAKE, BOB, CARL |
| [3/4] | 🟠 | The idle clock differs from the PRD rule `now - mtime(activity_path) >= idle_secs`. `_wait_past_cap` starts `last_change` at the moment the cap elapses and only detects mtime changes. A log already silent for at least idle_secs at the cap is therefore killed idle_secs later, not at the first poll. The printed "silent for {idle}s" understates the real silence, and no test covers a log already stale at the cap. | skills/run-autopilot/cli/watchdog.py:164 | 2 | ALICE, BLAKE, BOB |
| [3/4] | 🟡 | `START_FIELDS` and `DONE_FIELDS` stay 2-tuples. `started_at` and `done_at` are stamped outside `record_pair`, whereas the PRD contract makes them the third field with `now` as the third pair value. A non-int `started_at` is overwritten with no `_warn_non_int` line. The module docstring (lines 3-8) still says "four ints". | skills/run-autopilot/scripts/_cap_task_record.py:19 | 1 | ALICE, BLAKE, CARL |
| [2/4] | 🟠 | The tests for the time term give false confidence. `test_time_term_hands_off_when_the_deadline_is_near`, `test_time_term_is_inert_without_a_deadline`, `test_time_term_is_inert_without_a_completed_task` and `test_malformed_deadline_drops_the_time_term` call `_headroom_exhausted(..., secs_left=..., last_wall=...)` directly. None runs the hook with the env var set and a stamped state, so the missing wiring passes. `test_malformed_deadline_drops_the_time_term` passes `secs_left=None` itself and asserts nothing about deadline parsing. No test exercises the hook end to end for the time term | skills/run-autopilot/scripts/test_autopilot_cap_headroom_margin.py:25 | general | BLAKE, CARL |
| [2/4] | 🟡 | The calls-term margin (`TURN_TRIPWIRE - count < last_calls * HEADROOM_MARGIN`) is unpinned. Dropping `* HEADROOM_MARGIN` on that term breaks no test. The docstring says "251 calls leave 199, under the margined 250-call threshold", but 199 < 200 also fires without the margin. Add a case such as `_headroom_exhausted(None, 220, 150_000, 200)` (True; 230 < 250) plus the exact boundary (count 200 is False). | skills/run-autopilot/scripts/test_autopilot_cap_headroom.py:118 | 4 | ALICE, BLAKE |
| [2/4] | 🟡 | The new split test files are not in `dev/bin/release-checks`: `test_autopilot_cap_headroom_margin.py` (margin and time-term pins), `test_loop_metrics.py`, `test_render_report.py`, `test_policy_budget.py`. Only `test_devon_round_prose.py` was added, so these pins never run at release. | dev/bin/release-checks:76 | general | ALICE, BOB |
| [2/4] | 🟡 | CHANGELOG `[Unreleased]` now has two `### Changed` headings. The new one is at line 10, the pre-existing one at line 21. Merge the two new bullets into the existing section. | CHANGELOG.md:10 | 7 | ALICE, BLAKE |
| [2/4] | 🟡 | The `test_devon_round_prose.py` module docstring says presence assertions are section-scoped via `_section`, but only `test_step_2_9_runs_devon_once` is. In `test_tess_answers_each_weak_point` the whole-file needle "in-contract:" is satisfied by the Outcomes row alone, so the Feedback section is unpinned. Top-level functions are separated by one blank line, not two. | skills/work/scripts/test_devon_round_prose.py:106 | 7 | ALICE, BOB |
| [1/4] | 🟠 | Existing golden test now fails: `test_render.py::GoldenRenderTests::test_report_section_matches_golden`. `prd_section` now ends with `Task wall-clock:\n- none stamped`, but `report-section.md` was not regenerated. The full `cli` suite shows 1 of its 2 failures here. Neither test is in `dev/bin/release-checks`, so release-checks stayed green. | skills/run-autopilot/cli/golden/expected/report-section.md | 6 | ALICE |
| [1/4] | 🟠 | The `_append_metrics` line-budget refactor changed behavior. `ledger_dir.mkdir(parents=True)` now runs before the first write, so an absent `ap_dir` gets created, and a mkdir failure loses the primary `loop-metrics.jsonl` row. `test_routing.py::test_metrics_append_with_effort_still_never_raises` (line 796) now fails: `never-created` exists. Restore the original write order and extract a helper for the line budget, instead of the for-loop and the walrus one-liner at line 293. | skills/run-autopilot/cli/loop.py:301 | 5 | ALICE |
| [1/4] | 🟡 | Several acceptance node ids from the PRD do not resolve. Tests sit in classes (`TaskBoundsWallTests`, `HeadroomMarginTests`, `TaskOverBudgetTests`, `TaskWallClockBlockTests`) or moved to new files (`test_autopilot_cap_headroom_margin.py`, `test_policy_budget.py`). So `test_autopilot_cap_headroom.py::test_start_fire_stamps_started_at`, `::test_margin_hands_off_...`, `test_policy.py::test_opus_...` and `test_render_report.py::test_report_prints_...` all fail with "not found". Only task 7's ids were flattened (e5a8479). | N/A | general | ALICE |
| [1/4] | 🟡 | The gate-edge headroom check prose says it applies "the hook's own rule" with the first-task estimates, but it still hardcodes the unmargined `450 - count < 200` and `500000 - usage < 150000`. The hook now uses 1.25x (250 calls, 187.5K). `test_handoff_placement_prose.py:54,63` pins the old formulas. Decide whether the plan-to-work edge should follow the margin, and either update both or state the exception. | skills/run-autopilot/references/phase-build.md:234 | 4 | ALICE |
| [1/4] | 🟡 | The spec-named acceptance node ids do not resolve as written. `test_autopilot_cap_headroom.py::test_margin_...` and the four `::test_time_term_...` / `::test_malformed_deadline_...` tests live in `test_autopilot_cap_headroom_margin.py`, which the PRD's Success Metrics command does not run. The four `test_policy.py::test_..._budget` tests live in `test_policy_budget.py`. The PRD's own command therefore never exercises the margin or time tests | skills/run-autopilot/scripts/test_autopilot_cap_headroom_margin.py:1 | general | BLAKE |
| [1/4] | 🟡 | FIX: `START_FIELDS` and `DONE_FIELDS` remain pairs despite the three-field contract; a completed record with its usage and call bounds already present cannot acquire `done_at`. | skills/run-autopilot/scripts/_cap_task_record.py:19 | 1 | BOB |
| [1/4] | 🟡 | FIX: Fail-first replay reports that the new `test_prd_without_stamps_prints_none_stamped` passes against pre-change code; strengthen the assertion so it pins the new fallback. | skills/run-autopilot/cli/test_render_report.py:66 | 6 | BOB, mech-check |
| [1/4] | 🟡 | FIX: The new test module's long introduction repeats its assertions and incorrectly says all presence checks are section-scoped; replace it with a short purpose statement. | skills/work/scripts/test_devon_round_prose.py:1 | 7 | BOB |
| [1/4] | 🟡 | test_prd_without_stamps_prints_none_stamped uses self.subTest which masks assertion failures when run under pytest without pytest-subtests | skills/run-autopilot/cli/test_render_report.py:66 | 6 | CARL |
| [1/4] | 🟡 | Simplify _task_wallclock_block duration calculation by removing redundant int() wrapping around integer floor division // | skills/run-autopilot/cli/render_report.py:605 | 6 | CARL |
| [1/4] | 🟡 | 1 touched test(s) pass against the pre-change code: test_total_tess_budget_is_four | skills/work/scripts/test_adversarial_cap_prose.py | 7 | mech-check |
| [1/4] | ⚪ | `last_task_wall` returns None as soon as the latest completed task lacks stamps or has a negative span. The PRD wording ("most recently completed task ... whose two stamps are ints and whose difference is not negative") reads as scanning back to the most recent valid one. | skills/run-autopilot/scripts/_cap_task_record.py:132 | 1 | ALICE |
| [1/4] | ⚪ | The Feedback-to-Tess template still says `{Devon's explanation of which tests are weak}` under `Weak points:`. Devon now emits a numbered list, and Tess's `N.` answers only key correctly if it is passed verbatim. Also, the outcome row's "one correction retry" of the strengthen dispatch conflicts with the step 2.8 budget "1 adversarial strengthen" (SKILL.md:243), and "correction retry" is undefined for Tess. | skills/work/references/adversarial-test-prompt.md:88 | 7 | ALICE |
| [1/4] | ⚪ | Deleting `test_strengthened_tests_are_committed_before_devon_round_two` also dropped two live pins. One is that step 2.85 calls `<test_commit_sha>` "the last test commit", so an ESCALATE reset keeps the strengthened tests. The other is that the strengthen commit shape is documented. Keep those assertions in a slimmer test. | skills/work/scripts/test_step_order_prose.py:57 | 7 | ALICE |
| [1/4] | ⚪ | The `watchdog.py` module docstring (lines 4-5, 21) still says a session past the cap gets SIGTERM and "The cap itself is unchanged". It is stale after the idle guard and ceiling. | skills/run-autopilot/cli/watchdog.py:1 | 2 | ALICE |
| [1/4] | ⚪ | `_IDLE_POLL_SECS = 5.0` is a production constant chosen to serve small test caps, against the PRD's `poll_secs=60` default. `math.ceil(time.time() + cap_secs)` needs a new `import math`, where the PRD's `int(time.time()) + int(cap_secs)` needs none. | skills/run-autopilot/cli/runner.py:229 | 5 | ALICE |
| [1/4] | ⚪ | Timing margin in `test_idle_guard_waits_for_an_active_session_past_the_cap`. The child exits around 0.5 s plus interpreter start-up, and the ceiling fires at 0.6 s. That is about 0.1 s of slack, so the test is flaky under load. | skills/run-autopilot/cli/test_watchdog.py:199 | 2 | ALICE |
| [1/4] | ⚪ | Note for the gate on the [MECH] lines. `test_prd_without_stamps_prints_none_stamped` is a subTest reporting artefact. I ran the HEAD test against the base code and it fails (`SUBFAILED` on all 3 states, plus 3 plain failures in the same file). `test_total_tess_budget_is_four` is a pre-existing, unchanged test in a touched file. Neither needs rework. | skills/run-autopilot/cli/test_render_report.py:66 | general | ALICE |
| [1/4] | ⚪ | `last_task_wall` gives up (returns None) when the last completed task is unstamped or negative, rather than falling back to the most recent completed task with valid stamps. The spec sentence is ambiguous. This mirrors `last_task_cost` but may drop the time term more often than intended, for example after a partly stamped resume | skills/run-autopilot/scripts/_cap_task_record.py:127 | general | BLAKE |
| [1/4] | ⚪ | Small watchdog and runner deviations. (1) `_wait_past_cap` checks the ceiling before idle; the spec lists idle first, so the reason label differs when both hold at one poll. (2) The runner hard-codes `poll_secs=5.0` (`_IDLE_POLL_SECS`), not the spec default 60. (3) The deadline is `math.ceil(time.time() + cap_secs)` instead of `int(time.time()) + int(cap_secs)`, which is equivalent within one second | skills/run-autopilot/cli/watchdog.py:181 | general | BLAKE |
| [1/4] | ⚪ | Doc residue. Step 2.9's prose gate still says every Devon round "ends `round exhausted` at that ceiling", but that ceiling no longer exists. `attempt-logging.md` still calls the state-schema mirror "an integrator hand-off" although the mirror is done. Outcomes row 2 tells the orchestrator to record `devon_exploit`, but neither `attempt-logging.md` nor `state-schema.md` lists that field, while both list the two other new fields. Line-wrapped code span in the Feedback to Tess text | skills/work/SKILL.md:265 | general | BLAKE |
| [1/4] | ⚪ | Phase-number mismatch. The rubric speaks of Phases 1-3 but the PRD has Phases 0, 1 and 2. The B15/B16 fails below rest on PRD Phase 1 (Core) not meeting its acceptance, which is B15 by literal numbering and B16 under a shifted numbering. PRD Phase 2 (Devon prose, `test_devon_round_prose.py`, release-checks wiring, CHANGELOG) meets its criteria. The spec'd node ids there are module-level and resolve | N/A | general | BLAKE |
| [1/4] | ⚪ | Cannot statically verify: the targeted suites and `bash dev/bin/release-checks` pass; VERIFY by running both after rework. | N/A | general | BOB |

## Orchestrator verification of the 🔴

The top row is not taken on the reviewers' word. Verified directly at `e5a8479`:

```
$ rg -n 'last_task_wall|_cap_task_record import|_AUTOPILOT_SESSION_DEADLINE' skills/run-autopilot/scripts/autopilot_context_cap_hook.py
72:from _cap_task_record import last_task_cost, record_task_bounds
```

One hit, and it is the import line — which does NOT import `last_task_wall`. Zero hits for `last_task_wall` and zero for `_AUTOPILOT_SESSION_DEADLINE` anywhere in the hook. And at `autopilot_context_cap_hook.py:584-586`:

```python
    last_usage, last_calls = _last_task_cost(state)
    if _headroom_exhausted(total, count, last_usage, last_calls):
        request_handoff(autopilot_dir, task_id, session_id, _phase_of(state))
```

`_headroom_exhausted` accepts `secs_left=None, last_wall=None` and drops the time term when either is None, so the call above can never fire on time. CONFIRMED: the PRD's headline capability ("the hook has no notion of time at all" → fixed) is absent at runtime. `HEADROOM_MARGIN` and the predicate signature landed; only the wiring is missing.

Also verified: `_cap_task_record.py:19-20` still reads `START_FIELDS = ("usage_at_start", "calls_at_start")` / `DONE_FIELDS = ("usage_at_done", "calls_at_done")`, and the module docstring still says the hook "stamps four ints".

## Alice

Alice (consensus, legacy engine) raised 19 findings: 3 🟠, 6 🟡, 10 ⚪. Her 🟠 set is the time-term wiring gap, the un-regenerated `report-section.md` golden, and the `_append_metrics` write-order regression. Her last ⚪ is an adjudication note on the two `[MECH]` replay lines rather than a defect: she re-ran the HEAD `test_render_report.py` against the base code and it fails there, so the replay's "passes against base" reading on `test_prd_without_stamps_prints_none_stamped` is a subTest reporting artefact.

Rubric verdicts:

```
R1: fail
R2: fail
R3: pass
R4: fail
R6: pass
R7: pass
R8: pass
R9: fail
R10: pass
R11: pass
R12: pass
R13: pass
```

## Blake

Blake (blind, PRD-only; he never saw the diff, the file list or any review history) independently located the code and raised 12 findings: 1 🔴, 3 🟠, 4 🟡, 4 ⚪. His 🔴 is the same time-term wiring gap, reached from the spec alone and supported by his own `git log -S last_task_wall` on the hook returning nothing. He also confirmed as implemented-per-spec: the stamps, `HEADROOM_MARGIN` and the predicate signature, the `Watchdog` signature/`fired_reason`/`idle_secs_for`/`SpawnResult.cap_reason`/`killed_by`/runbook sentence, `TASK_WALL_BUDGET_SECS` and `task_over_budget`, the `Task wall-clock:` block including both fallback lines, `watchdog.py` at 197 lines and the hook at exactly 800, the single Devon round, Devon's every-weak-point instruction, Tess's per-weak-point answer wording, "the orchestrator never dismisses one itself", the three new attempt fields in the docs, and `test_devon_round_prose.py` wired into `release-checks`.

Rubric verdicts:

```
B1: fail
B2: pass
B3: fail
B4: fail
B5: fail
B6: pass
B7: pass
B8: pass
B9: pass
B10: fail
B11: pass
B12: pass
B13: pass
B14: pass
B15: fail
B16: fail
B17: pass
B18: pass
B19: pass
```

## Bob

Bob (doubt + de-slop lens via codex, static-only sandbox) raised 9 findings: 2 🟠, 6 🟡, 1 ⚪. First run, no inlined retry needed. His ⚪ is the sandbox's declared runtime limit (`Cannot statically verify` the suites), which the orchestrator discharged by running the suite this cycle — see the `Tests:` line.

Rubric verdicts:

```
R1: fail
R2: fail
R3: pass
R4: fail
R6: pass
R7: fail
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
```

## Carl

Carl (`backend=copilot model=gemini-3.8-flash`) raised 6 findings: 1 🔴, 2 🟠, 3 🟡. No frontend surface in this diff, so he reviewed as a generalist. His 🔴 is the time-term wiring gap; his grep for `last_task_wall` in the hook returning "No matches found" is the same evidence the orchestrator re-verified above.

Rubric verdicts:

```
R1: fail
R2: fail
R3: pass
R4: fail
R6: pass
R7: fail
R8: pass
R9: fail
R10: pass
R11: pass
R12: pass
R13: pass
```

## Mechanical checks

- **Tautological test shapes**: clean. 102 test functions checked across 8 changed test files; no `[MECH]` line.
- **Fail-first replay**: 31 touched tests ran against `83165038f9df`; 29 failed there (correctly pinning the change), 2 passed, 2 test files could not be collected at base. Both `[MECH]` lines are absorbed into the table above — the first folded onto the existing `test_prd_without_stamps_prints_none_stamped` row (finders gained `mech-check`), the second added as its own row.
- **Mechanical facts** (`ast` line counts) were appended to the context file and reached every implementation-aware prompt. No finding contradicts that block, so nothing was discarded under the computed-facts rule.

## Follow-up Tasks Created

Six `[D1]` tasks, all `sonnet` (the PRD's `default_model` floor), grouped by theme. The 🔴 row deliberately has no task here: `run-autopilot/references/phase-review.md` Phase 6 § Dispatch rework creates it after the cycle's rework design, so a CRITICAL fix never starts without a reviewed contract.

1. Task 8 (M) — Fix the two red tests: regenerate the report-section golden and restore `_append_metrics` write order — 🟠, addresses 2 findings
2. Task 9 (S) — Harden the Task wall-clock block against malformed stamps and drop its redundant `int()` — 🟠 [4/4], addresses 4 findings
3. Task 10 (M) — Measure watchdog silence from the log's mtime age, not from cap elapse; fix reason order and stale docs — 🟠 [3/4], addresses 5 findings
4. Task 11 (M) — Align `_cap_task_record` with the PRD's three-field contract and widen `last_task_wall`'s scan — 🟡 [3/4], addresses 4 findings
5. Task 12 (M) — Put the new split test files in `release-checks` and reconcile the PRD's acceptance node ids — 🟡, addresses 4 findings
6. Task 13 (M) — Clear the Devon prose residue, scope the prose test, restore the dropped step-order and Tess-budget pins — 🟡, addresses 8 findings

Two findings are folded into the Phase 6 CRITICAL task rather than given their own: the 🟠 "tests for the time term give false confidence" and the 🟡 unpinned calls-term margin. The 🔴 fix must ship with the end-to-end pin that would have caught it.

Four rows produce no task (recorded in the settled-decisions ledger with their reasons): Alice's `[MECH]` adjudication note (evidence, not a defect), Blake's phase-numbering note (a rubric-numbering artefact he flags himself), Bob's `Cannot statically verify` (discharged by the suite run below), and the PRD's own acceptance-node-id mismatch is instead carried by Task 12.

## Notes on the deleted test files

The diff removes `skills/work/scripts/test_adversarial_cap_prose.py` (40 lines) and `skills/work/scripts/test_step_order_prose.py` (35 lines). Neither deletion appears in the PRD's plan, and the PRD says Step 2.8's Tess budget line is unchanged — so `test_total_tess_budget_is_four`, which pinned it, left the tree with no replacement. Task 13 restores the dropped pins.

Verdict: 32 findings
Tests: 3664 passed, 2 failed, 1 skipped (suite run this cycle)

`last-verification.json` was NOT reused even though its `sha` matches this HEAD and its counts are non-null. Its `commands` are `bash dev/bin/release-checks` and one prose-test file; `release-checks` does not run `skills/run-autopilot/cli/test_render.py` or `test_routing.py`, so its "1581 passed, 0 failed, 0 skipped" is green over two genuinely red tests. Reusing it would have reported a passing suite for a broken tree. The counts above come from a fresh foreground run this cycle:

```
$ uv run --no-project --with pytest python -m pytest -q skills/ --ignore=skills/run-autopilot/scripts/tracon
FAILED skills/run-autopilot/cli/test_render.py::GoldenRenderTests::test_report_section_matches_golden
FAILED skills/run-autopilot/cli/test_routing.py::test_metrics_append_with_effort_still_never_raises
2 failed, 3664 passed, 1 skipped, 7 warnings, 825 subtests passed in 270.96s (0:04:30)
```

`skills/run-autopilot/scripts/tracon` is excluded because its three test modules fail to import for want of the `rich` package — a pre-existing environment gap unrelated to this diff, not a regression from it.
