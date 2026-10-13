---
prd: docs/dev/project-management/prds/wip/00282-loop-guards-v1.md
review: 2
date: 2026-10-13
head_sha: 134569cbf988c6e3773dab2eb338b9ad67690105
codex_thread_id: 01a13663-c319-7671-b4d6-1e1a049b740b
reviewers: alice,blake,bob
agents:
  alice: available
  blake: available
  bob: available
  carl: unavailable
dispatch_rows:
  bob: 23fda5c5
  carl: 76f524dc
---

# Review: 00282-loop-guards-v1

Diff range: `14423e65b0145bb2e64f7a0c50d6bbb9ff0b2cff..134569cbf988c6e3773dab2eb338b9ad67690105`

codex_rung_guard: not fired

pack: failed (engram pack exit 1: sqlite3.OperationalError: attempt to write a readonly database) — review degraded, not invalid.

carl: unavailable. First dispatch exit 1 (copilot backend authentication failed: "Your GitHub token may be invalid, expired, or lacking the required permissions"). One retry on the native `gemini` backend (`GEMINI_BACKEND=gemini`) started, printed `backend=gemini model=CLI-default` and then produced no output for ~40 min until the background lane hit its time limit and was stopped. Retry budget spent; Carl counts as failed. Not latched for the batch: exit 1 and a stopped lane are runtime failures, not the exit-4 permanent-unavailability contract.

bob: after one retry (inlined). First run returned the lack-of-input refusal shape (both staged file readers died with `sandbox-exec: sandbox_apply: Operation not permitted`); the inlined retry prompt (387 KB, context plus full diff inlined) produced a full review.

bob format normalization: Bob's retry emitted his ten issue lines as markdown bullets (`- [BOB] …`), which `consolidate_findings.py` does not match, so the first consolidation run silently dropped all ten. The leading `- ` was stripped from those lines and consolidation re-run; the table below includes them. Recorded rather than fixed silently.

carry-forward: `00282-loop-guards-v1-checks-1.json` holds one entry, `bash dev/bin/release-checks`, with `result: null`. That command was executed at this cycle's reviewed HEAD by `review-stage`'s gate step and exited 0 (`6473 passed, 0 failed, 32 skipped`), so the queued check is satisfied at this revision and is not carried forward as a finding.

## Consolidated Findings

| Ref | Consensus | Severity | Issue | File | Task | Found By |
|-----|-----------|----------|-------|------|------|----------|
| R1 | [3/3] | 🟡 | `_budget_bound` re-implements `effective_signal` inline (`effective = decision["then"] if decision["signal"] == "instant_exit" else decision["signal"]`) instead of calling the helper added in the same diff. Replace it with `effective_signal(decision)`. Also, a budget park derived from an `instant_exit` keeps the stale `then: continue` key, so its metrics row reads `signal: park, then: continue`. Pop `then` or set it when parking. | skills/run-autopilot/cli/loop_decision.py:541 | 4 | ALICE, BLAKE, BOB |
| R2 | [2/3] | 🟠 | `prd_spend_since` now crashes on a non-UTF-8 ledger. The new `metrics_path.read_text(encoding="utf-8")` pre-probe only catches OSError, and UnicodeDecodeError is a ValueError. I checked: a ledger holding bytes `\xff\xfe{}` raises UnicodeDecodeError out of `_budget_bound`, into the unattended loop. The old binary reader skipped such lines. The probe also reads the whole ledger twice, since `load_rows` reads it again. Drop the probe and catch `(OSError, UnicodeDecodeError)`, or open and read once and hand the rows over. | skills/run-autopilot/cli/loop_decision.py:188 | 9 | ALICE, BOB |
| R3 | [2/3] | 🟡 | New runner test cannot fail: it sets `_AUTOPILOT_SESSION_IDLE` to "0.1", but `idle_secs_for` does `int(raw)`. That raises ValueError and falls back to DEFAULT_IDLE_SECS. I checked: `idle_secs_for({'_AUTOPILOT_SESSION_IDLE':'0.1'})` returns 1200. The stub exits after 0.5 s, so `cap_fired is False` holds whether or not `busy_fn` is wired. The test claims to cover the runner wiring from prior finding R11 and covers nothing. Use an integer such as "1" with a longer silent stub, and confirm it fails when `busy_fn` is unwired. | skills/run-autopilot/cli/test_runner.py:474 | 9 | ALICE, BOB |
| R4 | [2/3] | 🟡 | The `records.py` / `records_park.py` split has a fragile circular import. `records.py` re-exports from `records_park` at the bottom of the module (:579). `records_park` does `from . import records` (:27) and expects `records` to be fully initialised. Importing `cli.records_park` first fails: "ImportError: cannot import name '_finish_park' from partially initialized module 'cli.records_park'". Today only `records` imports it, so all callers work. Any direct `from cli import records_park` breaks, though, and the module docstring invites exactly that. Either import `records_park` lazily inside `do_park`'s callers, or have `records_park` hold no back-import, with `do_stall` injected. If neither, state the "import via records only" constraint in the `records_park` docstring and pin it with a test. | skills/run-autopilot/cli/records_park.py:27 | 9 | ALICE, BOB |
| R5 | [1/3] | 🟠 | Failed entry invalidation still permits stale replay: `_invalidate_loop_entry` silently ignores another write failure, leaving the previous same-PRD result available to the child. Disable cached replay for that launch when invalidation fails; test persistent write failure with an existing entry. | skills/run-autopilot/cli/loop.py:628 | 10 | BOB |
| R6 | [1/3] | 🟡 | Out-of-scope production behavior change in the gate parser, with no CHANGELOG entry. This diff widens `_is_unread_line` in `gate.py` (:434) so any bullet- or ordinal-led line carrying a bare severity emoji counts as unread. As a result, 17 historical review files flip to "malformed", listed in `_ACCEPTED_FLIPS` (test_gate_findings_real_fixtures.py:173). The real fixture `fixtures/00256-review-1.md` was edited so its "- 🟡 Blake:" and numbered follow-up lines stop tripping the rule. That cuts against the file's own policy ("never fixed by editing it"). The earlier cycle settled the 67 `test_gate_findings_unread_shapes` failures as out of scope for this PRD. The rework then fixed them in production code anyway. The change may be justified, since those tests pinned the rule in earlier commits 34744e6 and 7a386b5. It is still a user-visible behavior change: a live review file with a "- 🟠 ..." bullet outside the findings table is now refused. It needs a CHANGELOG Fixed entry and a note in the assumptions ledger, or a move to its own PRD. | skills/run-autopilot/cli/gate.py:434 | 11 | ALICE |
| R7 | [1/3] | 🟡 | The warning test asserts only that the callback eventually occurred; firing it at the cap or ceiling would also pass. Record the callback time and assert the configured pre-cap warning window. | skills/run-autopilot/cli/test_watchdog.py:366 | 9 | BOB |
| R8 | [1/3] | 🟡 | The reader-delegation test's event row lacks `ts_start`, so the old independent parser already excludes it; the supplied replay confirms this test passes against base. Give that event an eligible timestamp or explicitly verify shared-reader invocation. | skills/run-autopilot/cli/test_loop_budget.py:380 | 9 | BOB |
| R9 | [1/3] | 🟡 | Moving every budget-stamp test out of `test_enter.py` breaks the pinned acceptance command using that file with `-k budget_since`. Keep those acceptance tests at their required path and move older unrelated tests instead. | skills/run-autopilot/cli/test_enter.py:774 | 11 | BOB |
| R10 | [1/3] | 🟡 | The new bullet predicate treats ordinary severity summaries, such as `- Severity split: 0 🟠 High`, as unread findings. The baseline flips and rewritten fixture accept this regression. Preserve summary/disposition prose, restore the fixture, and test that actual finding bullets still trigger refusal. | skills/run-autopilot/cli/gate.py:430 | 11 | BOB |
| R11 | [1/3] | ⚪ | Unspecified behavior: `_budget_bound` sleeps the usage-limit wait before turning the decision into a park, and `_pre_enter` back-dates state.json's mtime with os.utime. Both are reasoned in comments and neither is in the PRD | skills/run-autopilot/cli/loop_decision.py:563 | general | BLAKE |
| R12 | [1/3] | ⚪ | Small defensive extras beyond the PRD: `loop_entry` added to PER_PRD_RESET_FIELDS, `--prd` makes the replay drop the entry and run enter(), negative or non-finite budget falls back to 300, an unparseable `prd_budget_since` counts from epoch 0, `_invalidate_loop_entry`, and `then` is written into metrics rows. None adds a flag or dependency, but together they go past the literal spec | skills/run-autopilot/cli/records.py:99 | general | BLAKE |
| R13 | [1/3] | ⚪ | `_record_entry` catches StateError, StateExistsError, OSError and SchemaError. Any other exception from `enter()` (KeyError, ValueError) would propagate out of `_guarded` and halt the unattended loop, contrary to the "never halts the loop" intent | skills/run-autopilot/cli/loop.py:610 | general | BLAKE |
| R14 | [1/3] | ⚪ | tracon's `SIGNALS` tuple does not list `instant_exit` or `park`, so a dashboard that classifies the last row by signal shows neither distinctly. This is cosmetic and was not required by the PRD | skills/run-autopilot/scripts/tracon/model.py:17 | general | BLAKE |
| R15 | [1/3] | ⚪ | Known and documented limitation: a session that follows the brief's `## Entry` section and never calls `autopilot enter` leaves `loop_entry` on disk, so a stale `## Entry` can render in later briefs for the same PRD | skills/run-autopilot/cli/brief.py:130 | general | BLAKE |
| R16 | [1/3] | ⚪ | `do_park` remains 61 lines according to the supplied AST counts, exceeding the 50-line limit. Its body was relocated unchanged; this size violation predates the incremental rework. | skills/run-autopilot/cli/records_park.py:205 | general | BOB |
| R17 | [1/3] | 🟡 | 8 touched test(s) pass against the pre-change code: test_budget_since_is_set_to_now_on_first_entry, test_budget_since_is_kept_when_the_same_prd_is_entered_again, test_budget_since_already_in_state_survives_same_prd_reentry, test_budget_since_is_refreshed_when_the_previous_prd_differs, test_budget_since_is_refreshed_on_a_switch_to_another_prd +2 more | skills/run-autopilot/cli/test_enter_budget.py | general | mech-check |
| R18 | [1/3] | 🟡 | 1 touched test(s) pass against the pre-change code: test_one_metrics_line_per_session | skills/run-autopilot/cli/test_loop.py | general | mech-check |
| R19 | [1/3] | 🟡 | 4 touched test(s) pass against the pre-change code: test_budget_park_lands_prd_in_hold_and_next_prd_launches, test_budget_resets_after_resume_from_hold, test_prd_spend_since_missing_ledger_is_silently_zero, test_prd_spend_since_delegates_row_loading_to_render_metrics_load_rows | skills/run-autopilot/cli/test_loop_budget.py | general | mech-check |
| R20 | [1/3] | 🟡 | 7 touched test(s) pass against the pre-change code: test_instant_exit_flags_only_sub_30s_unbilled_sessions +1 more | skills/run-autopilot/cli/test_loop_decision.py | general | mech-check |
| R21 | [1/3] | 🟡 | 30 touched test(s) pass against the pre-change code: test_state_write_failed_marker_wins_over_a_healthy_state, test_paused_state_prints_detail_runbook_and_notifies, test_review_cap_pause_summarizes_and_lists_findings, test_subagent_prompt_overrun_replans_in_place, test_bootstrap_death_halts_loud_with_no_state, test_unreadable_state_death_names_it +24 more | skills/run-autopilot/cli/test_loop_decision_table.py | general | mech-check |
| R22 | [1/3] | 🟡 | 3 touched test(s) pass against the pre-change code: test_manual_prd_arg_skips_the_replay_even_with_a_matching_entry, test_loop_entry_delete_failure_halts_enter, test_pre_enter_utime_failure_is_reported | skills/run-autopilot/cli/test_loop_gates.py | general | mech-check |
| R23 | [1/3] | 🟡 | 18 touched test(s) pass against the pre-change code: test_no_marker_and_no_stall_op_exits_3_and_changes_nothing, test_marker_missing_or_empty_prd_is_deleted_and_ignored, test_unparseable_json_marker_is_deleted_and_ignored, test_marker_prd_not_in_wip_and_no_stall_op_is_deleted_as_stale, test_normal_park_moves_prd_records_stall_and_resets_state, test_park_detail_carries_the_lane_of_a_lane_routed_prd +12 more | skills/run-autopilot/cli/test_records_park_wrapper_died.py | general | mech-check |
| R24 | [1/3] | 🟡 | 1 touched test(s) pass against the pre-change code: test_spawn_idle_guard_reads_busy_fn_from_the_teed_log | skills/run-autopilot/cli/test_runner.py | general | mech-check |
| R25 | [1/3] | 🟡 | 1 touched test(s) pass against the pre-change code: test_warn_callback_fires_before_the_cap_with_idle_polling_and_busy_fn_on | skills/run-autopilot/cli/test_watchdog.py | general | mech-check |

Note on R17-R25: the replay base is cycle 1's HEAD, so most of these rows are pre-existing tests that this cycle's rework only moved or reformatted; they pass against the base by design. R19's `test_prd_spend_since_delegates_row_loading_to_render_metrics_load_rows` and R25's warn-window test are the two the doubt lens independently raised as genuinely unpinning (R8, R7).

## Alice

Consensus lens (implementation-aware), legacy engine. 5 findings: 4 🟡, 1 ⚪ — see R1-R4, R6 above. Alice verified every cycle-1 finding resolved in code except as noted: R1/R2/R3/R4/R5/R6/R7/R8/R9/R10/R14/R15/R17/R18/R19/R21/R22/R23/R24/R25/R26/R30 resolved, R16 resolved with the new UnicodeDecodeError regression (R2 here), R11's runner-wiring half added as a tautological test (R3 here), R27 documented as a known limitation. 396 targeted tests across the touched files pass; `bash dev/bin/release-checks` printed `PASS 6473 FAIL 0 SKIP 32 EXIT 0`.

R1: pass
R2: fail
R3: pass
R4: pass
R6: pass
R7: pass
R8: pass
R9: pass
R10: pass
R11: pass
R12: pass
R13: pass

## Blake

Blind lens (PRD-only). 6 findings, all ⚪ — see R1, R11-R15 above. No Critical or High defects: every spec feature is implemented as described, and the named tests and the release gate pass. Evidence: 187 targeted tests passed across test_loop_budget, test_loop_decision, test_watchdog, test_loop_gates, test_brief, test_records_park, test_enter_budget, test_enter_prose and test_doc_contract; `bash dev/bin/release-checks` printed `PASS 6473 FAIL 0 SKIP 32 EXIT 0`; `prd_budget_since` and `loop_entry` have state-schema rows (:169-170), the `## Entry` sentence is in phase-build.md:24, `_AUTOPILOT_PRD_BUDGET_USD` is documented in SKILL.md:144, and CHANGELOG.md:13-16 carries the four Added entries.

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
B15: pass
B16: pass
B17: pass
B18: pass
B19: pass

## Bob

Doubt lens + de-slop (codex), after one retry (inlined). 10 findings: 2 🟠, 7 🟡, 1 ⚪ — see R1-R5, R7-R10, R16 above. FIX bucket held nine entries, VERIFY none, KNOWN one (`do_park` at 61 lines, relocated unchanged).

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
R13: pass

D1: pass
D2: pass
D3: pass
D4: pass
D5: pass

## Carl

Not run: unavailable this cycle (see the `carl:` line in the top matter). The reviewed diff has no frontend or UI surface, so the lens Carl specializes in had no material to judge; his absence degrades the roster but does not leave a UI change unreviewed.

Verdict: 25 findings
Tests: 6473 passed, 0 failed, 32 skipped (suite run this cycle)
