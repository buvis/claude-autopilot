---
catchup: skip
design: skip
default_model: sonnet
model_tier_rationale: four small mechanical changes with exact contracts below (two stamps, one time term in an existing predicate, one idle guard on one thread, one report line) plus a prose cut; the planner lifts the hook's headroom edit to opus if its contract row hits
rework_cap: 2
---

# Leave sessions at task boundaries and run one Devon round

Source: `dev/local/notes/validation-batch-202609252154-2026-09-26.md` V45, V46,
V36, V2, V16, V22 and the operator's decision of 2026-09-26 12:50 ("the
timeouts cause rework when they cut work in progress"; option "sonnet floor
now, throughput PRD next"). Grounded at `edace9a` (0.5.6). Independent of
00215-00217.

## Overview

### Problem Statement

A batch's wall-clock is set by how often a session is cut mid-task and by how
many dispatches one task runs, and nothing in 0.5.6 bounds either:

- The wrapper's wall-clock cap (`_AUTOPILOT_SESSION_MAX` 7200 s,
  `_AUTOPILOT_SESSION_MAX_REVIEW` 10800 s) SIGTERMs the session at the cap
  whatever it is doing. 00214 session 4 died at task 3 with its work committed
  and its attempt record unwritten (V45); the next session spent 40 minutes
  re-orienting. 0.5.6 added a warning 15 minutes before the cap that writes
  `.handoff-requested`, but a marker only acts at a task boundary, and no
  opus-depth task in the batch finished inside 15 minutes (task 5: 109 min).
- The context-cap hook hands off on headroom (PRD 00200) but compares the
  context left against the last task's cost one to one. 00214 task 6 opened
  with 173K left against a last task of 164K, passed, and two minutes later
  the rule was exhausted with the task already running (V46): the marker can
  no longer help, and the 500K hard rotation will cut the task if it costs
  what the last one did (V36 shape, 00214 task 1 and agent-skills 00062 task 1
  both rotated mid-task on 2026-09-26).
- The hook has no notion of time at all, so a session that will be killed in
  20 minutes starts a task it cannot finish.
- Devon's second round (the re-check after Tess strengthens) ended "1 round
  exhausted, flag and proceed" on every task measured: 4 of 4 on 00213 kept
  nothing from it (V2: 8 dispatches, ~26 min, ~0.5M tokens), 00062 task 1
  and 00214 task 5 the same at 17-21 minutes of opus each, and on 00057 task
  1 the round named a real exploit which the orchestrator dismissed and the
  cycle-1 review then raised as CRITICAL on its own (V33). Seven re-checks,
  none of which changed a test or prevented a finding.
- The re-check does find things; nothing acts on them. On 00215 task 3
  (2026-09-27, `dev/local/notes/autoclaude-observation-2026-09-28.md` O2)
  round 2 named 7 weak points and "flag and proceed" left every one in the
  tests. Cycle-1 review then raised 5 of them as findings (3 of 4 reviewers),
  and one (a rerun-idempotency test that passes on an incomplete report) is
  why HIGH H1 was never caught. That rework cycle and its re-review cost
  about 4 h. Round 1 finds too few because Devon's prompt stops at the first
  exploit ("If tests pass: you broke them. Report the exploit."), so Tess
  only ever sees one weak point.

### Target Users

The unattended loop (`autoclaude`), and the operator reading a batch report
to see where the hours went.

### Success Metrics

- `uv run --no-project --with pytest python -m pytest -q skills/run-autopilot/scripts/test_autopilot_cap_headroom.py skills/run-autopilot/scripts/test_autopilot_cap_headroom_margin.py skills/run-autopilot/cli/test_watchdog.py skills/run-autopilot/cli/test_runner.py skills/run-autopilot/cli/test_policy.py skills/run-autopilot/cli/test_policy_budget.py skills/work/scripts/test_devon_round_prose.py`
  green; every existing `test_autopilot_cap_*.py`, `test_loop*.py` and
  `test_render_report*.py` stays green.
- `bash dev/bin/release-checks` green (`test_devon_round_prose.py` joins the
  work-skill prose block).
- Post-release signal, next batch: no `loop-metrics.jsonl` row carries
  `killed_by` unless the session's `last-session.log` was silent for the idle
  window; no session opens a task with less than a quarter of margin over the
  last task's context or time; no `devon` dispatch row follows a `tess`
  strengthen row for the same task; the batch report prints a wall-clock line
  per task.

## Functional Decomposition

### Capability: A session leaves at a task boundary, never mid-task

#### Feature: Time stamps on the task record
- **Description**: the context-cap hook stamps when a task started and ended
  beside the usage and call bounds it already writes.
- **Inputs**: the fire's wall-clock (`int(time.time())`).
- **Outputs**: `state.tasks[i].started_at` and `state.tasks[i].done_at`, epoch
  seconds as ints.
- **Behavior**: `_cap_task_record.START_FIELDS` becomes `("usage_at_start",
  "calls_at_start", "started_at")` and `DONE_FIELDS` becomes
  `("usage_at_done", "calls_at_done", "done_at")`;
  `record_task_bounds(state, task_id, total, count, now, warn=True)` passes
  `now` as the third value of each pair. `started_at` is written once and
  never replaced (time does not restart at a rotation, so a rotated task's
  wall spans its sessions and the rule below errs toward leaving early);
  `done_at` follows the existing never-rewrite rule. New helper
  `last_task_wall(state) -> int | None`: `done_at - started_at` of the most
  recently completed task in `state.tasks` order whose two stamps are ints
  and whose difference is not negative; None otherwise. `BOUND_FIELDS` is
  unchanged, so `last_task_cost` still ignores the stamps.
  `references/state-schema.md` documents both fields beside `usage_at_start`.

#### Feature: The headroom rule knows the deadline and keeps a margin
- **Description**: the hook hands off at a boundary when the next task would
  not fit in the context, the calls, or the time left, each with a quarter to
  spare.
- **Inputs**: `_AUTOPILOT_SESSION_DEADLINE` (epoch int, set by the runner),
  `last_task_cost`, `last_task_wall`.
- **Outputs**: the existing `.handoff-requested` marker, written earlier.
- **Behavior**: `runner.spawn` adds `_AUTOPILOT_SESSION_DEADLINE =
  str(int(time.time()) + int(cap_secs))` to `env_for_child` after
  `child_env(env)` (interactive sessions have no deadline). New constant
  `HEADROOM_MARGIN = 1.25` in `autopilot_context_cap_hook.py`.
  `_headroom_exhausted(total, count, last_usage, last_calls, secs_left=None,
  last_wall=None) -> bool` is True when `USAGE_CAP - total < last_usage *
  HEADROOM_MARGIN`, or `TURN_TRIPWIRE - count < last_calls * HEADROOM_MARGIN`,
  or `secs_left < last_wall * HEADROOM_MARGIN`; a None on either side of a
  term drops that term, as today. `_handle_below_cap` computes `secs_left =
  deadline - int(time.time())` from the env var (absent, empty or non-int
  drops the time term) and `last_wall` from `last_task_wall(state)` (no
  completed task with stamps drops the time term; there is no first-task
  wall estimate, the wrapper's warning covers the first task).

#### Feature: The wrapper kills only a hung session
- **Description**: past the cap the watchdog waits for the session to leave
  on its own, and signals only a session that has gone silent, or one that has
  run to twice its cap.
- **Inputs**: `_AUTOPILOT_SESSION_IDLE` (seconds, default 1200; `0` restores
  the kill-at-cap behaviour), the mtime of `last-session.log` (the runner
  writes and flushes every session line to it, so its mtime is the activity
  clock), `cap_secs`.
- **Outputs**: one stderr line naming the reason; `Watchdog.fired_reason` in
  `{"cap", "idle", "ceiling", None}`; `SpawnResult.cap_reason` with the same
  values; a `killed_by` field on the session's `loop-metrics.jsonl` row,
  present only when the watchdog fired.
- **Behavior**: `Watchdog(proc, cap_secs, grace_secs, warn_secs=0.0,
  on_warn=None, idle_secs=0.0, activity_path=None, poll_secs=60.0)`. With
  `idle_secs > 0` and an `activity_path`, once the cap elapses the thread
  loops: wait `poll_secs` for the child; if it exited, return unsignaled; if
  `now - mtime(activity_path) >= idle_secs`, print
  `autoclaude: session silent for {idle}s past the {cap}s wall-clock cap;
  SIGTERM (idle).` and fire with reason `idle`; if `now - start >= 2 *
  cap_secs`, print `autoclaude: session reached twice the {cap}s wall-clock
  cap; SIGTERM (ceiling).` and fire with reason `ceiling`. An unreadable
  `activity_path` counts as silent. With `idle_secs == 0` or no path, the
  existing kill at the cap runs unchanged with reason `cap`. The TERM-then-
  KILL grace and `fired` are unchanged; `fired_reason` is None until the
  watchdog fires. `_run_session` passes `idle_secs` and `activity_path=
  log_path`; `spawn` reads `idle_secs_for(env)` (`_AUTOPILOT_SESSION_IDLE`,
  default 1200, non-int falls back to the default, like `warn_secs_for`).
  The loop's row writer (the `wall_secs` line of `cli/loop.py`) adds
  `killed_by` from `SpawnResult.cap_reason` when it is not None. The
  run-autopilot SKILL.md Operator runbook sentence on the cap gains the idle
  window and the ceiling.

### Capability: One Devon round per task

#### Feature: Strengthen once, no re-check
- **Description**: Devon runs once; an exploit goes to Tess once and the task
  proceeds on the strengthened tests.
- **Inputs**: Devon's outcome.
- **Outputs**: the attempt entry's `devon` field gains `"exploit_fixed"`.
- **Behavior**: `work/SKILL.md` step 2.9 replaces "Devon runs at most twice
  per task: the first pass and one re-check after Tess strengthens" with
  "Devon runs once per task; when he breaks the tests, Tess strengthens once
  and the task proceeds on the strengthened tests with no second Devon
  dispatch (seven measured re-checks on 2026-09-25/26 changed no test; the
  one that named a real exploit was dismissed and the review caught it)".
  `references/adversarial-test-prompt.md` § Outcomes keeps row 1, rewrites
  row 2 to: send the exploit to Tess, commit the strengthened tests as
  `test(<scope>): strengthen <feature>` (this commit is now
  `<test_commit_sha>`), record `devon: exploit_fixed` and `devon_exploit:
  <Devon's one-line weak-point summary>` in the task's attempt entry so the
  ledger keeps the signal V33 lost, proceed to 2.95; and drops row 3. The "Max 1 Tess/Devon round (2 Devon dispatches, ...)" sentence and
  every "re-run Devon" or "second Devon dispatch" phrase go. Step 2.8's Tess
  budget line is unchanged (the strengthen dispatch stays). `references/
  attempt-logging.md` lists `"exploit_fixed"` beside `"skipped:prose"` for
  `devon`, and `run-autopilot/references/state-schema.md` mirrors it.

#### Feature: Devon lists every weak point; Tess answers each one
- **Description**: the single round finds what the old re-check found, and
  no named weak point reaches review unanswered.
- **Inputs**: Devon's report; Tess's strengthen reply.
- **Outputs**: two attempt-entry fields, `devon_weak_points` (int) and
  `devon_in_contract` (list of strings).
- **Behavior**: in `references/adversarial-test-prompt.md`, Devon's Process
  step 4 becomes "If tests pass: you broke them. Keep going: show every other
  weak point you can prove the same way, up to 8 in total, before
  reporting." The Output format's "If you CAN break the tests" bullet becomes
  "If you CAN break the tests: show the wrong implementation and the passing
  test output, then a numbered `Weak points:` list, one line each: `N. <test
  name> - <what a wrong implementation gets away with> - <assertion that
  would prevent it>`". In § Feedback to Tess, the line "Strengthen these
  specific tests so the above exploit no longer works." becomes "Address
  every numbered weak point. Answer each in your reply as `N. strengthened:
  <test name>` or `N. in-contract: <why the behavior is allowed>`." ("Do not
  change tests that Devon could NOT break." stays.) The rewritten Outcomes
  row 2 (above) also records `devon_weak_points: <count of Devon's list>` and
  `devon_in_contract: [<each "N. in-contract: ..." line Tess returned>]` in
  the attempt entry, and adds: "A weak point Tess neither strengthened nor
  marked in-contract goes back to Tess in the same strengthen dispatch's one
  correction retry; the orchestrator never dismisses one itself (V33)."
  `attempt-logging.md` and `state-schema.md` list both fields.

### Capability: Per-task wall-clock in the batch report

#### Feature: One line per task with a budget flag
- **Description**: the per-PRD report section shows how long each task took
  and marks the ones over budget.
- **Inputs**: `state.tasks[]` stamps at PRD close; `cli/policy.py`.
- **Outputs**: a `Task wall-clock:` block in `reports/{batch_id}-report.md`.
- **Behavior**: `cli/policy.py` gains `TASK_WALL_BUDGET_SECS = {"haiku": 900,
  "sonnet": 1200, "opus": 2700, "fable": 2700}` and `task_over_budget(task)
  -> bool` (False when a stamp is missing or the model is unknown).
  `render_report.py` prints, after the existing per-PRD lines, `Task
  wall-clock:` and one line per task `- <id> (<model>): <mm> min` with
  ` [over budget]` appended when `task_over_budget`, `- <id> (<model>): not
  stamped` when a stamp is missing; a PRD whose tasks carry no stamps prints
  the block header and `- none stamped`. Nothing blocks on the flag: the
  report is the gate the operator reads.

## Structural Decomposition

### Repository Structure

```
skills/run-autopilot/scripts/
├── _cap_task_record.py                 # Maps to: Time stamps on the task record
├── autopilot_context_cap_hook.py       # Maps to: The headroom rule knows the deadline
└── test_autopilot_cap_headroom.py      # Maps to: Test Strategy (stamps, margin, time term)
skills/run-autopilot/cli/
├── watchdog.py                         # Maps to: The wrapper kills only a hung session
├── runner.py                           # Maps to: deadline env, idle_secs_for, cap_reason
├── loop.py                             # Maps to: killed_by on the metrics row
├── policy.py                           # Maps to: TASK_WALL_BUDGET_SECS, task_over_budget
├── render_report.py                    # Maps to: Task wall-clock block
├── test_watchdog.py, test_runner.py, test_policy.py, test_render_report.py
skills/run-autopilot/references/state-schema.md   # started_at, done_at, devon values
skills/run-autopilot/SKILL.md                     # runbook: idle window and ceiling
skills/work/SKILL.md                              # Maps to: Strengthen once, no re-check
skills/work/references/adversarial-test-prompt.md # Maps to: Outcomes table; Devon lists every weak point
skills/work/references/attempt-logging.md         # devon: exploit_fixed
skills/work/scripts/test_devon_round_prose.py     # Maps to: Test Strategy (prose pin)
dev/bin/release-checks                            # the new prose test
CHANGELOG.md
```

### Module: _cap_task_record
- **Maps to capability**: A session leaves at a task boundary
- **Responsibility**: the pure task record; nothing about disk or time sources.
- **Exports**: `START_FIELDS`, `DONE_FIELDS`, `BOUND_FIELDS`, `record_pair`,
  `record_task_bounds(state, task_id, total, count, now, warn=True)`,
  `last_task_cost`, `last_task_wall(state)`.

### Module: watchdog
- **Maps to capability**: A session leaves at a task boundary
- **Responsibility**: one child, one thread, three ways to fire.
- **Exports**: `Watchdog` with `fired`, `warned`, `fired_reason`.

## Dependency Graph

### Foundation Layer (Phase 0)
No dependencies - built first.

- **_cap_task_record stamps**: pure.
- **watchdog idle guard**: pure (a temp file is the activity path in tests).
- **policy budgets**: pure.

### Core Layer (Phase 1)
- **hook time term + margin**: Depends on [_cap_task_record stamps].
- **runner/loop wiring**: Depends on [watchdog idle guard].
- **report block**: Depends on [policy budgets].

### Integration Layer (Phase 2)
- **Devon prose cut, docs, release-checks, CHANGELOG**: Depends on nothing
  above (prose), sequenced last so one commit carries the release wiring.

## Implementation Phases

### Phase 0: Foundation
**Goal**: the record carries time; the watchdog can wait past the cap; the
budgets exist.

**Tasks**:
- [ ] Stamp `started_at`/`done_at` in `_cap_task_record.py`, add
  `last_task_wall`, document both fields in `state-schema.md` - Acceptance:
  `test_autopilot_cap_headroom.py::TaskBoundsWallTests::test_start_fire_stamps_started_at`,
  `::TaskBoundsWallTests::test_done_fire_stamps_done_at`,
  `::TaskBoundsWallTests::test_started_at_survives_a_second_session`,
  `::TaskBoundsWallTests::test_last_task_wall_reads_the_latest_completed_task`,
  `::TaskBoundsWallTests::test_last_task_wall_is_none_without_stamps`,
  `::TaskBoundsWallTests::test_last_task_wall_rejects_a_negative_span` green; every existing test
  in the file green. (Node ids below corrected 2026-09-29 to match the shipped
  layout: unittest.TestCase methods need a `::ClassName::` segment, and four
  tests moved to new split files - task 12.)
- [ ] Add the idle guard and ceiling to `cli/watchdog.py` - Acceptance:
  `test_watchdog.py::test_idle_guard_waits_for_an_active_session_past_the_cap`
  (activity path touched every poll, child exits on its own after the cap:
  never signaled, `fired_reason` None),
  `::test_idle_guard_fires_after_the_idle_window` (reason `idle`),
  `::test_ceiling_fires_at_twice_the_cap` (reason `ceiling`),
  `::test_zero_idle_keeps_the_kill_at_the_cap` (reason `cap`),
  `::test_unreadable_activity_path_counts_as_silent` green; the five existing
  warn tests green.
- [ ] Add `TASK_WALL_BUDGET_SECS` and `task_over_budget` to `cli/policy.py` -
  Acceptance: `test_policy_budget.py::TaskOverBudgetTests::test_opus_task_over_forty_five_minutes_is_over_budget`,
  `::TaskOverBudgetTests::test_sonnet_task_under_twenty_minutes_is_within_budget`,
  `::TaskOverBudgetTests::test_missing_stamp_is_never_over_budget`,
  `::TaskOverBudgetTests::test_unknown_model_is_never_over_budget` green.

**Exit Criteria**: the three files green; `watchdog.py` under 200 lines.

### Phase 1: Core
**Goal**: the session hands off before a task it cannot finish; a live
session is never killed; the report shows the hours.

**Tasks**:
- [ ] Add `HEADROOM_MARGIN`, the time term and the deadline read to
  `autopilot_context_cap_hook.py`; export `_AUTOPILOT_SESSION_DEADLINE` from
  `runner.spawn` (depends on: Phase 0 stamps) - Acceptance:
  `test_autopilot_cap_headroom_margin.py::HeadroomMarginTests::test_margin_hands_off_when_left_is_under_five_quarters_of_the_last_task`
  (usage 173K left, last 164K: marker written),
  `::TimeTermHookTests::test_time_term_hands_off_when_the_deadline_is_near` (deadline 1000 s
  away, last wall 900 s: marker written),
  `::TimeTermHookTests::test_time_term_is_inert_without_a_deadline`,
  `::TimeTermHookTests::test_time_term_is_inert_without_a_completed_task`,
  `::TimeTermHookTests::test_malformed_deadline_drops_the_time_term`,
  `test_runner.py::test_spawn_exports_the_session_deadline` (env carries
  `_AUTOPILOT_SESSION_DEADLINE` within cap_secs + 5 of now) green; every
  existing `test_autopilot_cap_*.py` green.
- [ ] Wire `idle_secs_for(env)`, `activity_path`, `SpawnResult.cap_reason`
  and the row's `killed_by`; extend the runbook sentence (depends on: Phase 0
  watchdog) - Acceptance: `test_runner.py::test_idle_window_defaults_to_twenty_minutes`,
  `::test_spawn_reports_the_cap_reason`, the loop test that pins the metrics
  row (`test_loop*.py`, `::test_row_carries_killed_by_only_when_the_cap_fired`)
  green; `skills/run-autopilot/SKILL.md` names `_AUTOPILOT_SESSION_IDLE`,
  the 1200 s default and "twice the cap" in the Operator runbook.
- [ ] Print the `Task wall-clock:` block in `render_report.py` (depends on:
  Phase 0 budgets) - Acceptance:
  `test_render_report.py::TaskWallClockBlockTests::test_report_prints_one_wall_line_per_task`,
  `::TaskWallClockBlockTests::test_over_budget_task_is_flagged`,
  `::TaskWallClockBlockTests::test_unstamped_task_prints_not_stamped`,
  `::TaskWallClockBlockTests::test_all_unstamped_tasks_print_none_stamped` green
  (already shipped beside `render_report.py`).

**Exit Criteria**: all suites green.

### Phase 2: Integration
**Goal**: one Devon round, documented and checked at release.

**Tasks**:
- [ ] Cut the second Devon round in `work/SKILL.md` step 2.9 and
  `references/adversarial-test-prompt.md` § Outcomes, add `exploit_fixed` to
  `attempt-logging.md` and `state-schema.md`, add
  `skills/work/scripts/test_devon_round_prose.py` to `dev/bin/release-checks`,
  and the CHANGELOG entries (depends on: Phase 1) - Acceptance:
  `test_devon_round_prose.py::test_step_2_9_runs_devon_once`
  (`### 2.9` section contains "runs once per task" and neither "re-run Devon"
  nor "second Devon dispatch"),
  `::test_outcomes_table_has_no_re_check_row` (the file contains neither
  "re-run Devon" nor "1 round exhausted"),
  `::test_attempt_logging_lists_exploit_fixed`,
  `::test_devon_lists_every_weak_point` (`adversarial-test-prompt.md`
  contains "show every other weak point" and "a numbered `Weak points:`
  list", and no longer contains "Report the exploit."),
  `::test_tess_answers_each_weak_point` (the file contains "Address every
  numbered weak point", "strengthened:" and "in-contract:"),
  `::test_orchestrator_never_dismisses_a_weak_point` (the file contains
  "the orchestrator never dismisses one itself"),
  `::test_attempt_logging_lists_weak_point_fields` (`attempt-logging.md` and
  `state-schema.md` each contain `devon_weak_points` and
  `devon_in_contract`) green; `bash
  dev/bin/release-checks` green; `CHANGELOG.md` `[Unreleased]` carries under
  `### Changed` `**run-autopilot**` (boundary hand-off on time and margin,
  idle-only kill, wall-clock report lines) and `**work**` (one Devon round).

**Exit Criteria**: `release-checks` green.

## Test Strategy

### Critical Scenarios
- **Happy path**: a session at 327K after a 164K task, deadline 50 minutes
  away, last wall 109 minutes → the done fire writes the marker; the session
  leaves at that boundary; the watchdog never fires; the row has no
  `killed_by`; the report prints `- 5 (opus): 109 min [over budget]`.
- **Edge case**: a session past its cap whose log is still growing → no
  signal until the log stops for 1200 s; a rotated task whose `started_at`
  came from an earlier session → `last_task_wall` spans both sessions and the
  next session hands off earlier, never later.
- **Error case**: `_AUTOPILOT_SESSION_DEADLINE=abc` → the time term is
  dropped and the usage and call terms still run; an activity path that
  vanished → the session is treated as silent and killed after the idle
  window, with the `idle` line printed.

## Risks

- **A live but useless session runs to twice its cap**: a session that keeps
  writing lines without progress (a reviewer loop, a retry storm) is bounded
  only by the ceiling; the ceiling is the price of never cutting a working
  task, and the idle window catches the common hang (a dead subprocess, a
  stuck Watcher).
- **The margin hands off more often**: sessions leave a quarter earlier than
  today, so a batch pays more orientations (V28) until the orientation cost
  itself is cut (out of scope here; the `usage_at_start` of a session's
  first task remains the measure for that follow-up).
- **Devon's exploit survives Tess's strengthen**: the per-task Pat review and
  the PRD review still see the tests, and the attempt entry now carries the
  exploit summary and the in-contract list. The re-check's findings were real
  (00215 task 3: 5 of 7 came back as review findings), but only because
  nothing acted on them; listing every weak point in round 1 and making Tess
  answer each one moves that signal ahead of Ivan instead of dropping it.
- **A longer round 1**: Devon now proves up to 8 weak points instead of
  stopping at the first, which adds minutes to his one dispatch (guess:
  3-5 min on an opus task) against the 10-21 min re-check it replaces.
