# Decision Audit Log: 00282-loop-guards-v1

PRD: `00282-loop-guards-v1.md`
Started: 2026-10-13T18:46:09Z
Completed: 2026-10-13T18:46:09Z
Autonomous: 33  |  Deferred: 30  |  Doubts: 0

### [autonomous] 2026-10-13T18:46:09Z

**Decision**: Design the implementation approach for PRD 00282 (budget guard, in-code entry, instant-exit signal, idle watchdog) before task planning

**Choice**: Chosen: sum-on-demand budget guard over the metrics ledger; loop pre-launch enter() replayed via state.loop_entry; instant-exit as a pure post-dispatch reclassification; idle watchdog polls the whole [0,cap] window via a new _wait_pre_cap falling through to the unchanged post-cap ceiling path

**Rationale**: 3 review dispatches (2 codex attempts failed on a sandbox hook outage, Claude fallback both times); 4 blockers found and fixed across dispatches 1-2; dispatch 3 verified all fixes against the real code with 0 open findings

### [autonomous] 2026-10-13T18:46:09Z

**Decision**: Instant-exit does not follow the spec for a short session that touched state. Spec: the check runs before the `state_touched` counter reset, so an instant exit never resets `_died_retries`, and the died ladder (retry once, then park) decides. Code: `_decide` resets `_died_retries` at the state_touched block first (skills/run-autopilot/cli/loop_decision.py:242), then `_apply_instant_exit` (:255, :258) only relabels, with `then=continue`. A sub-30s, $0 session that wrote state therefore always gets then=continue and the ladder never runs. The new test deliberately uses an untouched state (skills/run-autopilot/cli/test_loop_decision.py:738), so the touched-state case in the spec's acceptance text is not covered.

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-10-13T18:46:09Z

**Decision**: The instant-exit change (task 5) leaves 14 existing loop tests red, and assumptions.md:225 records them as "already failing" without fixing them. Fixture sessions are under 30 s with no cost log, so they are now classed `instant_exit`. Reproduced: test_loop.py::test_one_metrics_line_per_session (signal is now instant_exit, expected continue), 4 tests in test_loop_decision.py (test_fingerprint_bound_parks_a_prd_burning_sessions, test_a_wait_the_fingerprint_bound_overrides_never_reaches_the_row, test_rejected_with_overage_allowed_still_sleeps, test_younger_loop_yields_at_allowed_warning), and 9 in test_loop_record_store.py. Update those fixtures to bill a cost or advance the clock, or the suite stays red

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-10-13T18:46:09Z

**Decision**: The new test file skills/run-autopilot/cli/test_loop_budget.py is not named in dev/bin/release-checks. test_release_checks_counts.py::test_every_tracked_test_file_is_gated fails with "does not name ['skills/run-autopilot/cli/test_loop_budget.py']". The PRD exit criterion (`release-checks` exits 0 with FAIL 0) cannot be met until it gets a [checks] block

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-10-13T18:46:09Z

**Decision**: The success metric `bash dev/bin/release-checks` does not exit 0. I ran it: the `test_loop_decision` block reports "4 failed, 157 passed". Re-running `uv run --no-project --with pytest python -m pytest -q skills/run-autopilot/cli/test_loop_decision.py` gives 4 failed, 55 passed. The failures are test_fingerprint_bound_parks_a_prd_burning_sessions, test_a_wait_the_fingerprint_bound_overrides_never_reaches_the_row, test_younger_loop_yields_at_allowed_warning and test_rejected_with_overage_allowed_still_sleeps. Each now gets `instant_exit` where it expected `continue` or `park` (e.g. skills/run-autopilot/cli/test_loop_decision.py:345, :440, :559, :709). Their fake sessions run 1s with no billed cost. The listed `-k` acceptance filters pass (97 passed), but the full file regresses and the Phase 2 exit criterion (`FAIL 0`) is unmet. The implementer neither adjusted these tests nor handled the signal change.

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-10-13T18:46:09Z

**Decision**: The budget guard excludes `instant_exit` with `then: continue` and every decision carrying `limit_wait`, although the PRD includes both. Normalize the effective signal and preserve the scheduled sleep when applying a budget park, rather than exempting these decisions.

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-10-13T18:46:09Z

**Decision**: Pre-entry failures can retain an earlier same-PRD `loop_entry`. Both exception branches return without invalidating it, allowing the child to replay stale catchup/design/stop results. Scope replay to the successful current launch and test both failure paths with an existing entry.

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-10-13T18:46:09Z

**Decision**: The completion gate remains red: 82 tests failed, and the supplied assumptions identify instant-exit regressions in existing loop tests. Resolve introduced failures, then run `bash dev/bin/release-checks`; completion requires exit 0 and `FAIL 0`.

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-10-13T18:46:09Z

**Decision**: `_budget_bound` returns unless `decision["signal"] == "continue"`, so an `instant_exit` whose `then` is `continue` is never budget-checked. PRD F1 says the check applies to "`continue`, or `instant_exit` whose `then` is `continue`". Read `decision["then"]` when the signal is instant_exit, and set `signal` to "park" as well as `park_site`

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-10-13T18:46:09Z

**Decision**: Downstream `signal == "continue"` consumers also skip an `instant_exit` with `then == "continue"`. `_run_loop` skips `store_tree.record_store("loop")`, so a short session that touched state is never recorded. `_fingerprint_bound` takes its else-branch and resets `_fp_repeats`/`_fp_prev`. This is the product-level cause of the red tests in the first finding. Decide deliberately whether those paths should see the `then` signal, and pin the choice with a test

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-10-13T18:46:09Z

**Decision**: SKILL.md:142 is now stale. It still says a headless turn "is never interrupted except by the wrapper's wall-clock cap", and it describes `_AUTOPILOT_SESSION_IDLE` as acting only past the cap. Task 6 now kills a silent, nothing-in-flight session before the cap. Only the CHANGELOG mentions this. Update the paragraph in the same place the budget sentence was added

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-10-13T18:46:09Z

**Decision**: Test gap: nothing combines `on_warn`/`warn_secs` with `busy_fn`, and production always passes both. `_wait_under_cap` now owns the warn-window wait (cap minus warn), and the "hand-off still fires at cap - warn_secs" claim is untested with idle polling on. `runner._run_session` passing `busy_fn` is also untested

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-10-13T18:46:09Z

**Decision**: Test gap: the `args.prd is None` gate in `_replay_loop_entry` has no test. The case is a manual `autopilot enter --prd X` while a matching `loop_entry` exists. The design doc records this as a fixed review finding. The `loop_entry` delete-failure path (exit 2) and the `_pre_enter` utime-failure message are also untested

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-10-13T18:46:09Z

**Decision**: Files over the 800-line limit, newly crossed by this diff: records.py 802, test_loop_decision.py 820, test_records_park.py 844, test_enter.py 862 (test_enter.py was 775 before, and its own footer says it was split at 800). assumptions.md:201 sanctions the test_loop_decision.py case. Split into new files, registering each in release-checks. __main__.py at 1863 lines was already over the limit

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-10-13T18:46:09Z

**Decision**: `_run_session` grew from about 49 to 52 lines (+1 `busy_fn` line, +2 docstring lines), crossing the 50-line function limit. Trim the docstring or extract the Watchdog construction

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-10-13T18:46:09Z

**Decision**: An invalid but present `prd_budget_since` disables the budget check. The design explicitly requires an invalid timestamp to fall back to epoch zero, counting all rows for that PRD. Distinguish an absent stamp from an invalid one and implement that fallback.

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-10-13T18:46:09Z

**Decision**: Ledger read errors silently become zero historical spend through `except OSError: pass`. An unreadable existing ledger can therefore disable cumulative enforcement without a diagnostic. Treat a missing initial ledger separately and report other read failures explicitly.

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-10-13T18:46:09Z

**Decision**: `prd_spend_since` introduces another JSONL reader despite the explicit reuse requirement. Delegate row loading to `cli.render_metrics.load_rows`, retaining the PRD, timestamp, and numeric filters.

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-10-13T18:46:09Z

**Decision**: The budget integration test disables real pre-launch entry and asserts launch order `[A, A, A, B]`. This preserves the wasted launch F2 should eliminate. Inject real `enter()` into the loop and assert that the first launch after parking A selects B, without entering inside the child fixture.

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-10-13T18:46:09Z

**Decision**: Instant-exit tests assert only the metrics `signal`, leaving the design's required `then` field unpinned. Assert `then: continue` for the retry/wait rows and `then: park` for the escalation row; ensure serialization preserves them.

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-10-13T18:46:09Z

**Decision**: The supplied fail-first replay identifies nine touched cases passing against base: budget-stamp preservation, legacy park-marker shape, and seven instant-exit cases. Under the requested R2 criterion, add feature-positive controls while retaining these compatibility assertions.

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-10-13T18:46:09Z

**Decision**: Supplied AST counts show the new budget acceptance tests at 61 and 65 lines, exceeding the function limit. Extract their repeated PRD-tree/state setup into a shared fixture while retaining their behavioral assertions.

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-10-13T18:46:09Z

**Decision**: `_run_session` now spans 52 lines according to the supplied AST counts. Trim its repetitive expanded docstring to retain the existing function boundary within the limit.

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-10-13T18:46:09Z

**Decision**: Added tests push three files beyond 800 lines: skills/run-autopilot/cli/test_enter.py:851, skills/run-autopilot/cli/test_records_park.py:837, and skills/run-autopilot/cli/test_loop_decision.py:810. Move older unrelated cases into companion files; keep the new acceptance tests at their pinned paths.

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-10-13T18:46:09Z

**Decision**: Operator documentation still says sessions are interrupted only by the wall cap and describes idle detection only after it. Document pre-cap idle termination and its busy-work exemption. Also correct CHANGELOG.md:14, which incorrectly excludes usage-limit sessions from instant-exit classification.

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-10-13T18:46:09Z

**Decision**: `_scan_busy` says it reads events tolerantly, but `(event.get("message") or {}).get("content")` raises AttributeError when `message` is a truthy non-dict. That reaches the outer `except Exception` and returns busy for the rest of the session, the latch the comment says it avoids. Add an `isinstance(message, dict)` check

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-10-13T18:46:09Z

**Decision**: `_record_entry` catches only `state.StateError` from `enter()`. The CLI path also catches `StateExistsError`, and an OSError or SchemaError from `enter()` would crash the unattended loop. The finally block only backdates the mtime. The spec names only StateError, but "never halts the loop" is the stated intent, so consider widening the catch

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-10-13T18:46:09Z

**Decision**: A session that follows the brief's `## Entry` section and skips `autopilot enter` never deletes `loop_entry`. The stale section then renders in the review-phase brief until a PRD reset. Normal operation is safe because the next `_pre_enter` overwrites the entry. Consider rendering `## Entry` only for the build phase

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-10-13T18:46:09Z

**Decision**: Stale docs. skills/run-autopilot/SKILL.md:142 and the `idle_secs_for` docstring (skills/run-autopilot/cli/runner.py:112) still say idle detection applies only past the wall-clock cap. Pre-cap idle kill is now live, and the CHANGELOG entry exists (CHANGELOG.md:15).

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-10-13T18:46:09Z

**Decision**: `_pre_enter` catches only `state.StateError` from `enter()` (skills/run-autopilot/cli/loop.py:596). Any other exception, such as an OSError from an unforeseen path, would crash the loop rather than launch without `loop_entry` as the spec's error case describes. `enter()` handles most OSErrors itself, so this is low risk.

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-10-13T18:46:09Z

**Decision**: 7 touched test(s) pass against the pre-change code: test_instant_exit_flags_only_sub_30s_unbilled_sessions +1 more

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-10-13T18:46:09Z

**Decision**: 30 of 35 consolidated cycle-1 findings (7 high, 19 medium, 4 low) routed to rework

**Choice**: auto-fix via review-close decision-gate: tasks 9-12 at sonnet

**Rationale**: no CRITICAL row, so no rework design; cycle 1 < rework_cap 2, so rework is allowed and every HIGH blocks convergence until fixed

### [autonomous] 2026-10-13T18:46:09Z

**Decision**: Carl (gemini) produced no review this cycle; Bob (codex) returned a lack-of-input refusal on his first run

**Choice**: continue with Alice, Blake and Bob-after-inlined-retry; Carl recorded unavailable, not latched for the batch

**Rationale**: graceful degradation per the review gate Safety Checks row: copilot auth failed (exit 1, not the exit-4 permanent contract) and the native-gemini retry stalled past the Watcher budget; Bob retry budget spent on the documented inlined-retry path

### [deferred] 2026-10-13T18:46:09Z

**Decision**: 67 further failures in test_gate_findings_unread_shapes.py (e.g. `_is_unread_line` on an emoji-bullet row) come from code this diff does not touch. I did not check them against the base commit, so they are probably pre-existing. They are part of the "82 failed" suite total (14 loop tests, the release-checks test, and these 67)

**Rationale**: deferred by review-close

### [deferred] 2026-10-13T18:46:09Z

**Decision**: Small extras beyond the spec: `budget_usd_for` also rejects negative, nan and inf values (loop_decision.py:145); `_parse_marker` normalizes any non-"budget" site to "wrapper_died" (records.py:586); `loop_entry` is added to `PER_PRD_RESET_FIELDS` (records.py:104); `_replay_loop_entry` also drops and does not replay when `--prd` is given (__main__.py:390). All are defensible and documented. They are not in the PRD.

**Rationale**: deferred by review-close

### [deferred] 2026-10-13T18:46:09Z

**Decision**: The idle watchdog treats a missing log as infinite silence (skills/run-autopilot/cli/watchdog.py:211). `session_busy` on a missing log returns False, so a session whose log is absent would be killed at the first poll. The log is created before launch (skills/run-autopilot/cli/runner.py:264), so this is not reachable in practice.

**Rationale**: deferred by review-close

### [deferred] 2026-10-13T18:46:09Z

**Decision**: 1 touched test(s) pass against the pre-change code: test_budget_since_already_in_state_survives_same_prd_reentry

**Rationale**: deferred by review-close

### [deferred] 2026-10-13T18:46:09Z

**Decision**: 1 touched test(s) pass against the pre-change code: test_non_budget_park_marker_carries_no_site

**Rationale**: deferred by review-close

### [deferred] 2026-10-13T18:46:09Z

**Decision**: [R1] `_budget_bound` re-implements `effective_signal` inline (`effective = decision["then"] if decision["signal"] == "instant_exit" else decision["signal"]`) instead of calling the helper added in the same diff. Replace it with `effective_signal(decision)`. Also, a budget park derived from an `instant_exit` keeps the stale `then: continue` key, so its metrics row reads `signal: park, then: continue`. Pop `then` or set it when parking. (file: skills/run-autopilot/cli/loop_decision.py:541)

**Rationale**: rework cap reached with this finding unresolved

### [deferred] 2026-10-13T18:46:09Z

**Decision**: [R2] `prd_spend_since` now crashes on a non-UTF-8 ledger. The new `metrics_path.read_text(encoding="utf-8")` pre-probe only catches OSError, and UnicodeDecodeError is a ValueError. I checked: a ledger holding bytes `\xff\xfe{}` raises UnicodeDecodeError out of `_budget_bound`, into the unattended loop. The old binary reader skipped such lines. The probe also reads the whole ledger twice, since `load_rows` reads it again. Drop the probe and catch `(OSError, UnicodeDecodeError)`, or open and read once and hand the rows over. (file: skills/run-autopilot/cli/loop_decision.py:188)

**Rationale**: rework cap reached with this finding unresolved

### [deferred] 2026-10-13T18:46:09Z

**Decision**: [R3] New runner test cannot fail: it sets `_AUTOPILOT_SESSION_IDLE` to "0.1", but `idle_secs_for` does `int(raw)`. That raises ValueError and falls back to DEFAULT_IDLE_SECS. I checked: `idle_secs_for({'_AUTOPILOT_SESSION_IDLE':'0.1'})` returns 1200. The stub exits after 0.5 s, so `cap_fired is False` holds whether or not `busy_fn` is wired. The test claims to cover the runner wiring from prior finding R11 and covers nothing. Use an integer such as "1" with a longer silent stub, and confirm it fails when `busy_fn` is unwired. (file: skills/run-autopilot/cli/test_runner.py:474)

**Rationale**: rework cap reached with this finding unresolved

### [deferred] 2026-10-13T18:46:09Z

**Decision**: [R4] The `records.py` / `records_park.py` split has a fragile circular import. `records.py` re-exports from `records_park` at the bottom of the module (:579). `records_park` does `from . import records` (:27) and expects `records` to be fully initialised. Importing `cli.records_park` first fails: "ImportError: cannot import name '_finish_park' from partially initialized module 'cli.records_park'". Today only `records` imports it, so all callers work. Any direct `from cli import records_park` breaks, though, and the module docstring invites exactly that. Either import `records_park` lazily inside `do_park`'s callers, or have `records_park` hold no back-import, with `do_stall` injected. If neither, state the "import via records only" constraint in the `records_park` docstring and pin it with a test. (file: skills/run-autopilot/cli/records_park.py:27)

**Rationale**: rework cap reached with this finding unresolved

### [deferred] 2026-10-13T18:46:09Z

**Decision**: [R5] Failed entry invalidation still permits stale replay: `_invalidate_loop_entry` silently ignores another write failure, leaving the previous same-PRD result available to the child. Disable cached replay for that launch when invalidation fails; test persistent write failure with an existing entry. (file: skills/run-autopilot/cli/loop.py:628)

**Rationale**: rework cap reached with this finding unresolved

### [deferred] 2026-10-13T18:46:09Z

**Decision**: [R6] Out-of-scope production behavior change in the gate parser, with no CHANGELOG entry. This diff widens `_is_unread_line` in `gate.py` (:434) so any bullet- or ordinal-led line carrying a bare severity emoji counts as unread. As a result, 17 historical review files flip to "malformed", listed in `_ACCEPTED_FLIPS` (test_gate_findings_real_fixtures.py:173). The real fixture `fixtures/00256-review-1.md` was edited so its "- 🟡 Blake:" and numbered follow-up lines stop tripping the rule. That cuts against the file's own policy ("never fixed by editing it"). The earlier cycle settled the 67 `test_gate_findings_unread_shapes` failures as out of scope for this PRD. The rework then fixed them in production code anyway. The change may be justified, since those tests pinned the rule in earlier commits 34744e6 and 7a386b5. It is still a user-visible behavior change: a live review file with a "- 🟠 ..." bullet outside the findings table is now refused. It needs a CHANGELOG Fixed entry and a note in the assumptions ledger, or a move to its own PRD. (file: skills/run-autopilot/cli/gate.py:434)

**Rationale**: rework cap reached with this finding unresolved

### [deferred] 2026-10-13T18:46:09Z

**Decision**: [R7] The warning test asserts only that the callback eventually occurred; firing it at the cap or ceiling would also pass. Record the callback time and assert the configured pre-cap warning window. (file: skills/run-autopilot/cli/test_watchdog.py:366)

**Rationale**: rework cap reached with this finding unresolved

### [deferred] 2026-10-13T18:46:09Z

**Decision**: [R8] The reader-delegation test's event row lacks `ts_start`, so the old independent parser already excludes it; the supplied replay confirms this test passes against base. Give that event an eligible timestamp or explicitly verify shared-reader invocation. (file: skills/run-autopilot/cli/test_loop_budget.py:380)

**Rationale**: rework cap reached with this finding unresolved

### [deferred] 2026-10-13T18:46:09Z

**Decision**: [R9] Moving every budget-stamp test out of `test_enter.py` breaks the pinned acceptance command using that file with `-k budget_since`. Keep those acceptance tests at their required path and move older unrelated tests instead. (file: skills/run-autopilot/cli/test_enter.py:774)

**Rationale**: rework cap reached with this finding unresolved

### [deferred] 2026-10-13T18:46:09Z

**Decision**: [R10] The new bullet predicate treats ordinary severity summaries, such as `- Severity split: 0 🟠 High`, as unread findings. The baseline flips and rewritten fixture accept this regression. Preserve summary/disposition prose, restore the fixture, and test that actual finding bullets still trigger refusal. (file: skills/run-autopilot/cli/gate.py:430)

**Rationale**: rework cap reached with this finding unresolved

### [deferred] 2026-10-13T18:46:09Z

**Decision**: [R11] Unspecified behavior: `_budget_bound` sleeps the usage-limit wait before turning the decision into a park, and `_pre_enter` back-dates state.json's mtime with os.utime. Both are reasoned in comments and neither is in the PRD (file: skills/run-autopilot/cli/loop_decision.py:563)

**Rationale**: rework cap reached with this finding unresolved

### [deferred] 2026-10-13T18:46:09Z

**Decision**: [R12] Small defensive extras beyond the PRD: `loop_entry` added to PER_PRD_RESET_FIELDS, `--prd` makes the replay drop the entry and run enter(), negative or non-finite budget falls back to 300, an unparseable `prd_budget_since` counts from epoch 0, `_invalidate_loop_entry`, and `then` is written into metrics rows. None adds a flag or dependency, but together they go past the literal spec (file: skills/run-autopilot/cli/records.py:99)

**Rationale**: rework cap reached with this finding unresolved

### [deferred] 2026-10-13T18:46:09Z

**Decision**: [R13] `_record_entry` catches StateError, StateExistsError, OSError and SchemaError. Any other exception from `enter()` (KeyError, ValueError) would propagate out of `_guarded` and halt the unattended loop, contrary to the "never halts the loop" intent (file: skills/run-autopilot/cli/loop.py:610)

**Rationale**: rework cap reached with this finding unresolved

### [deferred] 2026-10-13T18:46:09Z

**Decision**: [R14] tracon's `SIGNALS` tuple does not list `instant_exit` or `park`, so a dashboard that classifies the last row by signal shows neither distinctly. This is cosmetic and was not required by the PRD (file: skills/run-autopilot/scripts/tracon/model.py:17)

**Rationale**: rework cap reached with this finding unresolved

### [deferred] 2026-10-13T18:46:09Z

**Decision**: [R15] Known and documented limitation: a session that follows the brief's `## Entry` section and never calls `autopilot enter` leaves `loop_entry` on disk, so a stale `## Entry` can render in later briefs for the same PRD (file: skills/run-autopilot/cli/brief.py:130)

**Rationale**: rework cap reached with this finding unresolved

### [deferred] 2026-10-13T18:46:09Z

**Decision**: [R16] `do_park` remains 61 lines according to the supplied AST counts, exceeding the 50-line limit. Its body was relocated unchanged; this size violation predates the incremental rework. (file: skills/run-autopilot/cli/records_park.py:205)

**Rationale**: rework cap reached with this finding unresolved

### [deferred] 2026-10-13T18:46:09Z

**Decision**: [R17] 8 touched test(s) pass against the pre-change code: test_budget_since_is_set_to_now_on_first_entry, test_budget_since_is_kept_when_the_same_prd_is_entered_again, test_budget_since_already_in_state_survives_same_prd_reentry, test_budget_since_is_refreshed_when_the_previous_prd_differs, test_budget_since_is_refreshed_on_a_switch_to_another_prd +2 more (file: skills/run-autopilot/cli/test_enter_budget.py)

**Rationale**: rework cap reached with this finding unresolved

### [deferred] 2026-10-13T18:46:09Z

**Decision**: [R18] 1 touched test(s) pass against the pre-change code: test_one_metrics_line_per_session (file: skills/run-autopilot/cli/test_loop.py)

**Rationale**: rework cap reached with this finding unresolved

### [deferred] 2026-10-13T18:46:09Z

**Decision**: [R19] 4 touched test(s) pass against the pre-change code: test_budget_park_lands_prd_in_hold_and_next_prd_launches, test_budget_resets_after_resume_from_hold, test_prd_spend_since_missing_ledger_is_silently_zero, test_prd_spend_since_delegates_row_loading_to_render_metrics_load_rows (file: skills/run-autopilot/cli/test_loop_budget.py)

**Rationale**: rework cap reached with this finding unresolved

### [deferred] 2026-10-13T18:46:09Z

**Decision**: [R20] 7 touched test(s) pass against the pre-change code: test_instant_exit_flags_only_sub_30s_unbilled_sessions +1 more (file: skills/run-autopilot/cli/test_loop_decision.py)

**Rationale**: rework cap reached with this finding unresolved

### [deferred] 2026-10-13T18:46:09Z

**Decision**: [R21] 30 touched test(s) pass against the pre-change code: test_state_write_failed_marker_wins_over_a_healthy_state, test_paused_state_prints_detail_runbook_and_notifies, test_review_cap_pause_summarizes_and_lists_findings, test_subagent_prompt_overrun_replans_in_place, test_bootstrap_death_halts_loud_with_no_state, test_unreadable_state_death_names_it +24 more (file: skills/run-autopilot/cli/test_loop_decision_table.py)

**Rationale**: rework cap reached with this finding unresolved

### [deferred] 2026-10-13T18:46:09Z

**Decision**: [R22] 3 touched test(s) pass against the pre-change code: test_manual_prd_arg_skips_the_replay_even_with_a_matching_entry, test_loop_entry_delete_failure_halts_enter, test_pre_enter_utime_failure_is_reported (file: skills/run-autopilot/cli/test_loop_gates.py)

**Rationale**: rework cap reached with this finding unresolved

### [deferred] 2026-10-13T18:46:09Z

**Decision**: [R23] 18 touched test(s) pass against the pre-change code: test_no_marker_and_no_stall_op_exits_3_and_changes_nothing, test_marker_missing_or_empty_prd_is_deleted_and_ignored, test_unparseable_json_marker_is_deleted_and_ignored, test_marker_prd_not_in_wip_and_no_stall_op_is_deleted_as_stale, test_normal_park_moves_prd_records_stall_and_resets_state, test_park_detail_carries_the_lane_of_a_lane_routed_prd +12 more (file: skills/run-autopilot/cli/test_records_park_wrapper_died.py)

**Rationale**: rework cap reached with this finding unresolved

### [deferred] 2026-10-13T18:46:09Z

**Decision**: [R24] 1 touched test(s) pass against the pre-change code: test_spawn_idle_guard_reads_busy_fn_from_the_teed_log (file: skills/run-autopilot/cli/test_runner.py)

**Rationale**: rework cap reached with this finding unresolved

### [deferred] 2026-10-13T18:46:09Z

**Decision**: [R25] 1 touched test(s) pass against the pre-change code: test_warn_callback_fires_before_the_cap_with_idle_polling_and_busy_fn_on (file: skills/run-autopilot/cli/test_watchdog.py)

**Rationale**: rework cap reached with this finding unresolved
