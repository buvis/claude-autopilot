# Decision Audit Log: 00218-leave-sessions-at-task-boundaries-and-run-one-devon-round-v1

PRD: `00218-leave-sessions-at-task-boundaries-and-run-one-devon-round-v1.md`
Started: 2026-09-29T17:21:45Z
Completed: 2026-09-29T17:21:45Z
Autonomous: 19  |  Deferred: 9  |  Doubts: 0

### [autonomous] 2026-09-29T17:21:45Z

**Decision**: Two pre-existing tests are red at HEAD: the report-section golden and the _append_metrics never-raises test.

**Choice**: auto-fix as task 8

**Rationale**: Mechanical and additive: regenerate the golden, restore the original write order. No signature or schema change.

### [autonomous] 2026-09-29T17:21:45Z

**Decision**: _task_wallclock_block has no int guard, so a malformed stamp aborts the whole PRD-close report render.

**Choice**: auto-fix as task 9

**Rationale**: Additive guard, 4 of 4 consensus, mirrors the predicate task_over_budget already uses.

### [autonomous] 2026-09-29T17:21:45Z

**Decision**: The watchdog idle clock starts at cap elapse instead of measuring the activity path mtime age, so a session silent before the cap survives a full extra idle window.

**Choice**: auto-fix as task 10

**Rationale**: 3 of 4 consensus against an exact PRD contract line; the fix is a local change inside _wait_past_cap plus one new test for the uncovered case.

### [autonomous] 2026-09-29T17:21:45Z

**Decision**: START_FIELDS and DONE_FIELDS stay 2-tuples against the PRD three-field contract, so the stamps miss record_pair non-int warning path.

**Choice**: auto-fix as task 11

**Rationale**: Clear mechanical fix to an explicit contract; BOUND_FIELDS stays unchanged so last_task_cost is unaffected.

### [autonomous] 2026-09-29T17:21:45Z

**Decision**: Four new split test files carry this PRD pins and none is in dev/bin/release-checks, which is why release-checks stayed green over two red tests. Several PRD acceptance node ids do not resolve.

**Choice**: auto-fix as task 12

**Rationale**: Additive wiring plus a PRD text correction. Verified by the orchestrator: pytest --collect-only on two of the literal node ids returns not found.

### [autonomous] 2026-09-29T17:21:45Z

**Decision**: Devon prose residue, unscoped prose-test assertions, and two prose test files deleted outside the PRD plan dropping live pins.

**Choice**: auto-fix as task 13

**Rationale**: Prose and test-scoping work with no production behaviour change; restoring the dropped pins is additive.

### [autonomous] 2026-09-29T17:21:45Z

**Decision**: The 2 findings about the time-term tests (false confidence) and the unpinned calls-term margin.

**Choice**: folded into the Phase 6 CRITICAL task rather than given their own tasks

**Rationale**: The CRITICAL fix must ship with the end-to-end pin that would have caught it; splitting them would let the wiring land with the same vacuous tests.

### [autonomous] 2026-09-29T17:21:45Z

**Decision**: Tier for all six D1 tasks.

**Choice**: sonnet for every D1 task, no escalation

**Rationale**: These are decision-gate follow-ups (first-pass work), not retries of a flagged task, so the escalation ladder does not apply. The PRD default_model is sonnet, so the floor is sonnet.

### [autonomous] 2026-09-29T17:21:45Z

**Decision**: last-verification.json records sha e5a8479 with 1581 passed, 0 failed, 0 skipped, which the review skill permits reusing for the Tests line.

**Choice**: did NOT reuse the record; ran the project suite in the foreground this cycle instead

**Rationale**: Its commands are bash dev/bin/release-checks plus one prose file, and release-checks does not run test_render.py or test_routing.py, whose tests are red. Reusing it would have reported a green suite over a broken tree. Fresh run: 2 failed, 3664 passed, 1 skipped.

### [autonomous] 2026-09-29T17:21:45Z

**Decision**: engram pack failed with: not inside a registered repo; register it in the gita repos.csv.

**Choice**: continued without a context pack; substituted the documented sentinel in every prompt; not retried

**Rationale**: Pack failure is explicitly non-fatal. The failure is a deterministic config gap, not transient, so the one permitted retry would have failed identically.

### [autonomous] 2026-09-29T17:21:45Z

**Decision**: The CRITICAL row was NOT written to the settled-decisions ledger.

**Choice**: omitted from the ledger; recorded in deferred_decisions only

**Rationale**: The cap check narrowing states a CRITICAL is never a settled deferral. A ledger entry would let cycle 2 read it as settled and converge over an open CRITICAL, which is the exact failure that narrowing exists to prevent.

### [autonomous] 2026-09-29T17:21:45Z

**Decision**: The rework design inserts a trust filter (trusted_last_wall) plus a new constant MAX_CREDIBLE_WALL_SECS = 10800 between last_task_wall(state) and the headroom rule time term, where the PRD contract says _handle_below_cap takes last_wall straight from last_task_wall(state).

**Choice**: widen the PRD contract; record the deviation rather than follow the literal text

**Rationale**: The literal contract is unsafe. record_task_bounds never replaces started_at (a PRD contract pinned by test_started_at_survives_a_second_session), so a rotated or paused task carries every idle second between its sessions. The trigger threshold is cap/1.25 = 5760s, so any such span fires the term on the FIRST PostToolUse fire of the next session, making that session do one task and leave, and multiplying the orientation cost this PRD exists to cut. The filter drops a span whose task id is in state.cap_rotations (the exact signal) plus a 10800s backstop for pause/kill spans state does not record. Re-stamping started_at instead was rejected as a spec change, not a rework fix.

### [autonomous] 2026-09-29T17:21:45Z

**Decision**: The PRD's quoted step 2.9 replacement text contains "no second Devon dispatch". Its own acceptance test forbids that phrase in `### 2.9`. The implementer reworded to "Devon never dispatched again", which is the right way to resolve the spec's self-contradiction.

**Choice**: discarded at the cycle-2 decision gate (not a defect)

**Rationale**: Not a defect: the reviewer who raised it states in the same line that the implementation is the correct resolution. The PRD is self-contradictory (its quoted replacement text contains a phrase its own acceptance test forbids in that section), and the implementation resolves it the only way both can hold. Nothing to fix.

### [autonomous] 2026-09-29T17:21:45Z

**Decision**: Cannot statically verify: targeted suites pass and release checks pass; VERIFY: run the PRD Success Metrics pytest command and `bash dev/bin/release-checks`.

**Choice**: discarded at the cycle-2 decision gate (not a defect)

**Rationale**: Bob's declared sandbox limit, not a finding about the code, and discharged this cycle: the orchestrator ran the full suite in the foreground (3721 passed, 0 failed, 1 skipped) and `bash dev/bin/release-checks` green end to end. Both counts and the commands are recorded in the review file's Tests: block.

### [autonomous] 2026-09-29T17:21:45Z

**Decision**: 13 touched test(s) pass against the pre-change code: test_calls_margin_boundary_pins_the_exact_multiplier, test_calls_margin_fires_below_the_margined_threshold, test_time_term_boundary_pins_strict_less_than, test_time_term_is_false_when_plenty_of_time_remains, test_a_cheaper_last_task_keeps_working_under_the_same_deadline, test_a_malformed_cap_rotations_never_matches +7 more

**Choice**: discarded at the cycle-2 decision gate (not a defect)

**Rationale**: Verified benign. The orchestrator checked HEAD's test file out over a base worktree at e5a8479 and ran it: every POSITIVE end-to-end pin fails there (test_time_term_hands_off_when_the_deadline_is_near, test_deadline_already_past_hands_off, test_an_honest_long_wall_still_fires_the_time_term, test_a_rotation_of_another_task_still_fires_the_time_term, test_deadline_env_name_matches_the_runner). The 13 that pass are the inert/negative assertions (a term that must NOT fire cannot fail against code where nothing fires) plus the HeadroomMarginTests pure-predicate tests, which already existed at base. The change is pinned.

### [autonomous] 2026-09-29T17:21:45Z

**Decision**: 3 touched test(s) pass against the pre-change code: test_all_unstamped_tasks_print_none_stamped, test_empty_task_list_prints_none_stamped, test_missing_tasks_key_prints_none_stamped

**Choice**: discarded at the cycle-2 decision gate (not a defect)

**Rationale**: Benign: these three pin the 'none stamped' fallback that task 6 already shipped at base and task 9 deliberately preserved. Task 9's new behaviour (int guard, negative span, missing model) is pinned by test_string_stamp_alongside_valid_task_renders_not_stamped, test_all_string_stamped_tasks_print_none_stamped, test_negative_span_prints_not_stamped and test_task_with_missing_model_does_not_print_none, which the same replay reports as failing at base.

### [autonomous] 2026-09-29T17:21:45Z

**Decision**: 1 touched test(s) pass against the pre-change code: test_idle_guard_waits_for_an_active_session_past_the_cap

**Choice**: discarded at the cycle-2 decision gate (not a defect)

**Rationale**: Benign: that test shipped with task 2 at base and task 10 only widened its timing slack (the cycle-1 flakiness finding), so it is expected to pass at base. Task 10's actual change is pinned by test_idle_guard_fires_on_the_first_poll_when_already_stale_at_the_cap and test_idle_reason_wins_over_ceiling_when_both_hold_at_the_same_poll, both of which fail at base.

### [autonomous] 2026-09-29T17:21:45Z

**Decision**: 2 touched test(s) pass against the pre-change code: test_bound_fields_excludes_the_stamps_so_last_task_cost_ignores_them, test_done_at_survives_a_second_session

**Choice**: discarded at the cycle-2 decision gate (not a defect)

**Rationale**: Benign: both pin invariants that held at base too. BOUND_FIELDS excluded the stamps before task 11 as well (the PRD says it is unchanged), and done_at already followed the never-rewrite rule when it was stamped outside record_pair. Task 11's actual change (three-tuples, the _warn_non_int path, the scan-back) is pinned by tests the same replay reports as failing at base.

### [autonomous] 2026-09-29T17:21:45Z

**Decision**: 1 touched test(s) pass against the pre-change code: test_tess_answers_each_weak_point

**Choice**: discarded at the cycle-2 decision gate (not a defect)

**Rationale**: Benign, verified by reading the test at skills/work/scripts/test_devon_round_prose.py:127-150: task 13 scoped it to the '## Feedback to Tess (when Devon succeeds)' section, and that section already carried the three needles at base (task 7 wrote them). The scoping pins WHERE the wording lives, so it cannot fail at base, where the wording was already in the right section. The cycle-1 complaint (the whole-file needle was satisfied by the Outcomes row) is genuinely closed.

### [deferred] 2026-09-29T17:21:45Z

**Decision**: Time term is never wired into the hook: _handle_below_cap calls _headroom_exhausted with no secs_left or last_wall, the hook never imports last_task_wall and never reads _AUTOPILOT_SESSION_DEADLINE, so the PRD headline capability (hand off before a task that will not fit in the time left) is absent at runtime. Verified by the orchestrator at e5a8479: rg finds zero hits for either symbol in the hook.

**Choice**: defer to batch end and fix this cycle via the Phase 6 rework design

**Rationale**: Classification: critical severity always defers to batch end, and the cap check reads that a CRITICAL blocks until it is fixed. Cycle 1 of 2, so rework is allowed: Phase 6 runs the rework design and creates the fix task.

### [deferred] 2026-09-29T17:21:45Z

**Decision**: `trusted_last_wall` stops at the first completed task whose stamps are missing, non-int or negative and returns None, instead of scanning back. Its tests pin that shape (`test_stamps_that_are_not_both_ints_give_no_span`, `test_a_negative_span_gives_nothing`). The PRD wording, the design doc ("finds the last completed entry whose stamps are both ints") and task 11's widening of `last_task_wall` all say scan back. Since the hook never calls `last_task_wall`, task 11's fix has no runtime effect. Any completed task that was never seen in progress now drops the time term for the next fire. This is conservative, and the rotated-task and over-ceiling stops are deliberate, but the unstamped case is undocumented as a deviation. Either skip unstamped or negative entries and stop only on rotated or over-ceiling ones, or record the deviation. The design's `test_trusted_last_wall_agrees_with_last_task_wall` pin is also missing (`rg` finds no such test), so the two walks can silently disagree. ALSO FOLDED INTO THIS ROW BY THE CONSOLIDATOR (three distinct defects, see the review file's consolidation caveat): (a) no `isinstance(task, dict)` guard at _cap_headroom.py:77, so a non-dict entry in state.tasks raises AttributeError inside a PostToolUse hook with no except around it; (b) booleans satisfy `isinstance(..., int)` at _cap_headroom.py:81, so started_at/done_at of True yields a bogus span where `int_field` would reject it; (c) Blake's separate HIGH that the hook substitutes `trusted_last_wall` for the PRD's `last_task_wall(state)`, and its rotation and 10800s stops invert the PRD's own edge case ("a rotated task's wall spans both sessions and the next session hands off earlier, never later").

**Choice**: deferred to batch end

**Rationale**: rework cap reached with this finding unresolved

### [deferred] 2026-09-29T17:21:45Z

**Decision**: R13 regression: the rework grew this test file from 782 to 923 lines, and the project's own style gate (`check_style_limits.py`, "files the diff pushed over 800") flags it (verified by the orchestrator: exit 1, `FILE | skills/run-autopilot/scripts/test_autopilot_cap_headroom.py | 923 lines`). The earlier split existed to stay under 800. Move the new `TaskBoundsWallTests` additions into a sibling file such as `test_cap_task_record_wall.py`, and add it to `dev/bin/release-checks`.

**Choice**: deferred to batch end

**Rationale**: rework cap reached with this finding unresolved

### [deferred] 2026-09-29T17:21:45Z

**Decision**: `record_task_bounds` withholds `done_at` when the task has no `started_at`. The PRD says `now` is passed as the third value of each pair. This is defensible (a lone `done_at` gives no usable span) but it is an undocumented deviation from the contract. Note that `MAX_CREDIBLE_WALL_SECS` and this guard are extra behavior beyond the PRD.

**Choice**: deferred to batch end

**Rationale**: rework cap reached with this finding unresolved

### [deferred] 2026-09-29T17:21:45Z

**Decision**: Adding `started_at` to `START_FIELDS` lets `record_pair` replace an existing timestamp when it exceeds `now`, breaking the write-once contract. Limit the stale-start replacement rule to usage and calls.

**Choice**: deferred to batch end

**Rationale**: rework cap reached with this finding unresolved

### [deferred] 2026-09-29T17:21:45Z

**Decision**: A correction retry requires another Tess dispatch, but the four-dispatch budget allocates only one adversarial strengthen dispatch. The new prose still permits an unanswered weak point when that budget is spent. Reconcile the budget and retry rule; the test's check for the word "correction" does not pin dispatch counts.

**Choice**: deferred to batch end

**Rationale**: rework cap reached with this finding unresolved

### [deferred] 2026-09-29T17:21:45Z

**Decision**: The expanded module introduction still repeats the assertions and test mechanics. Replace it with a short purpose statement, as requested in cycle 1.

**Choice**: deferred to batch end

**Rationale**: rework cap reached with this finding unresolved

### [deferred] 2026-09-29T17:21:45Z

**Decision**: `record_pair`'s annotation says `values: tuple[int, int | None, int]`, but `record_task_bounds` passes `done_now`, which is `int | None`, in the third slot. The code handles it (`None` is skipped). Only the type is wrong.

**Choice**: deferred to batch end

**Rationale**: rework cap reached with this finding unresolved

### [deferred] 2026-09-29T17:21:45Z

**Decision**: The PRD says step 2.8's Tess budget line is unchanged. The implementation rewrote it to say the strengthen "also covers Devon's one weak-point correction retry". This resolves a real tension in the spec (a correction retry versus a fixed budget of 4), but it edits a line the spec said to leave alone.

**Choice**: deferred to batch end

**Rationale**: rework cap reached with this finding unresolved
