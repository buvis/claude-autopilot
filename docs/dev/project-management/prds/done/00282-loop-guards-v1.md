---
default_model: opus
model_tier_rationale: watchdog thread timing (idle from launch, busy pause) and a new park site through do_stall - concurrency and destructive-path rows of the gate
---

# Loop guards: spend budget, instant exits, idle hangs, in-code entry

## Overview

### Problem Statement
The autoclaude loop has no guard against three kinds of waste, and it makes
every build session enter by hand. Source: discovery
`docs/dev/project-management/discovery/00281-loop-efficiency.md` (F1-F4).
Across 239 sessions in one repo ($4,888): one PRD burned $1,420 with nothing
to stop it; a hung session sat 2 h 10 min because only the wall cap could end
it; ten 2-7 s, $0 sessions were logged as `continue` progress. Each build
session also spends its first calls running `autopilot enter`, which the loop
can run in code before launch.

### Target Users
The operator running `autoclaude` overnight, unattended.

### Success Metrics
- `test_budget_park_lands_prd_in_hold_and_next_prd_launches` and
  `test_budget_resets_after_resume_from_hold` pass.
- `test_loop_entry_then_skill_entry_writes_one_resume_row` passes.
- `test_instant_exit_signal_then_died_retry_without_limit` and
  `test_instant_exit_waits_when_usage_limit_detected` pass.
- `test_idle_kill_before_cap_when_silent_and_no_open_tool_use` and
  `test_no_idle_kill_while_tool_use_open` pass.
- `bash dev/bin/release-checks` exits 0 with `FAIL 0` on its summary line at the end of the last phase.

## Functional Decomposition

### Capability: Spend guard
Stop a PRD that keeps spending without finishing.

#### Feature: Per-PRD budget (F1)
- **Description**: Park a PRD once the cost of its sessions since it last entered wip/ passes `_AUTOPILOT_PRD_BUDGET_USD`.
- **Inputs**: env `_AUTOPILOT_PRD_BUDGET_USD` (float; default 300; `0` disables; unparseable keeps 300); `state.prd`; `state.prd_budget_since` (ISO UTC); rows of `loop-metrics.jsonl`; the current session's `total_cost_usd` from `last-session.log`.
- **Outputs**: decision `signal: "park"`, `park_site: "budget"`, detail `budget: $<total:.2f> > $<budget:g>; parking <prd>`; the PRD lands in `hold/` with a deferred stall record whose `site` is `"budget"`.
- **Behavior**: `enter()` step 10 sets `prd_budget_since = now()` when the field is absent or when the state's previous `prd` differs from the entered one. `prd_budget_since` joins `PER_PRD_RESET_FIELDS`, so every park and PRD reset clears it and a resume from hold/ starts a fresh budget. After each session, for a decision that would relaunch (`continue`, or `instant_exit` whose `then` is `continue`): total = sum of `cost_usd` over metrics rows with `prd == state.prd` and `ts_start >= prd_budget_since` (every row counts, `died` and `instant_exit` included) plus this session's cost. `total > budget` turns the decision into `park` with `park_site: "budget"`. No `prd`, no `prd_budget_since`, or budget 0: no check. `_act_park` writes `"site": "budget"` into `park-requested`; `_parse_marker` returns `site` (default `"wrapper_died"`); `_finish_park` with site `budget` calls `do_stall(site="budget", extra_mutator=None)`, exit 0, never the systemic halt. The batch continues.

### Capability: Session health signals
Tell a session that did nothing, or went silent, apart from real progress.

#### Feature: Instant-exit signal (F3)
- **Description**: A session under 30 s wall with `total_cost_usd` 0 or absent gets signal `instant_exit`.
- **Inputs**: `ts_start`, the loop clock, `last-session.log`.
- **Outputs**: decision `signal: "instant_exit"` plus `then`: the signal the ladder chose (`continue` for a limit wait or a retry, `park`, or `died`). The metrics row records `signal: "instant_exit"`.
- **Behavior**: Checked in `_decide` before the `state_touched` counter reset, so an instant exit never resets `_died_retries`. Applies when the state rows would give `continue` or nothing (paused, done and state_write_failed keep their signal). If `self._detect_limit(log)` returns a reset time, `_decide_limit_wait` decides. Otherwise `_decide_died` decides: retry once, then park. `_act_branch` acts on `then`. A 0 or absent cost means no model turn was billed, so a short session that wrote state counts too.

#### Feature: Idle watchdog from launch (F4)
- **Description**: Kill a session silent for `_AUTOPILOT_SESSION_IDLE` seconds (default 1200) at any point after launch, not only past the wall cap.
- **Inputs**: the tee'd log's mtime; `session_busy(log_path)`.
- **Outputs**: `fired_reason: "idle"`, SIGTERM then SIGKILL after grace; the metrics row carries `killed_by: "idle"`.
- **Behavior**: Before the cap, the watchdog polls every `poll_secs`. It fires `idle` when silence >= `idle_secs` and `session_busy` is False. `session_busy` scans the stream-json log and returns True when a `tool_use` id (in `assistant` message content) has no matching `tool_result` `tool_use_id` (in `user` message content), or when the last `system`/`background_tasks_changed` event has a non-empty `tasks` list. That event carries the full live task list and ends at `[]` (seen in a recorded review session, 2026-10-11). An exception inside `session_busy` counts as busy, so a parse fault never kills a session. The post-cap path (`_wait_past_cap`: idle or ceiling) is unchanged, so the cap still bounds a hung tool call. With `idle_secs == 0` or no activity path, behavior is exactly today's. The warning-window hand-off still fires at `cap - warn_secs`. The loop's decision table handles the killed session as it handles a post-cap idle kill today: `continue` when the dead session touched state, else the no-progress path (died/retry). A kill is not forced onto the died path; this is a ratified deviation from discovery F4's wording (backlog review 2026-10-12).

### Capability: In-code entry
Run Phase 0 in the loop, not in the session.

#### Feature: Loop pre-launch enter (F2)
- **Description**: Before launching a session whose `state.next_phase` is `build`, or whenever `park-requested` exists, the loop calls `enter()` in-process and records the result.
- **Inputs**: `state.json`, `<ap_dir>.parent / "prds"`, `in_loop=True`.
- **Outputs**: `state.loop_entry = {"entered_by": "loop", "prd": <result.prd>, "result": <the enter dict minus warnings>}`; the session brief re-rendered with an `## Entry` section; enter's warnings on the loop's stderr.
- **Behavior**: `enter()` raising `StateError`, or a failed state write, prints one stderr line and launches the session without `loop_entry` (the session enters normally). `autopilot enter` (CLI `_run_enter`) checks for `loop_entry` first. When `loop_entry.prd == state.prd`, it prints the stored result as its JSON line (sort_keys), deletes `loop_entry`, and exits 0 without calling `enter()` again: one resume row, one park, one selection. Any other `loop_entry` is deleted and `enter()` runs as today. A manual session never has one. The replay lives in code rather than prose because sessions ignore brief lines (discovery F10). The prose in `references/phase-build.md` § Enter in one call gains one sentence: when the brief has an `## Entry` section, take `prd`, `catchup` and `design` from it, and calling `autopilot enter` anyway replays the same line. The done session is unchanged.

## Structural Decomposition

### Repository Structure

```
skills/run-autopilot/
├── cli/
│   ├── loop_decision.py   # Maps to: Per-PRD budget, Instant-exit signal
│   ├── loop.py            # Maps to: Loop pre-launch enter, Per-PRD budget
│   ├── loop_act.py        # Maps to: Per-PRD budget (marker site), Instant-exit signal (act on then)
│   ├── records.py         # Maps to: Per-PRD budget (budget park site, reset field)
│   ├── enter.py           # Maps to: Per-PRD budget (prd_budget_since)
│   ├── __main__.py        # Maps to: Loop pre-launch enter (replay)
│   ├── brief.py           # Maps to: Loop pre-launch enter (## Entry section)
│   ├── watchdog.py        # Maps to: Idle watchdog from launch
│   └── runner.py          # Maps to: Idle watchdog from launch (wires busy_fn)
└── references/
    ├── phase-build.md     # Maps to: Loop pre-launch enter (one sentence)
    └── state-schema.md    # rows for loop_entry, prd_budget_since
```

### Module: loop_decision
- **Maps to capability**: Spend guard, Session health signals
- **Responsibility**: Decide the budget park and the instant-exit signal.
- **Exports**:
  - `budget_usd_for(env)` - parsed `_AUTOPILOT_PRD_BUDGET_USD`.
  - `DecisionMixin._budget_bound(decision, ap_dir)` - the budget override, called in `Loop._run_loop` right after `_fingerprint_bound`.
- New symbols: `budget_usd_for`, `_budget_bound`, `_INSTANT_EXIT_SECS`, `_AUTOPILOT_PRD_BUDGET_USD`, `instant_exit`, `test_budget_park_lands_prd_in_hold_and_next_prd_launches`, `test_budget_resets_after_resume_from_hold`, `test_instant_exit_signal_then_died_retry_without_limit`, `test_instant_exit_waits_when_usage_limit_detected`

### Module: records
- **Maps to capability**: Spend guard
- **Responsibility**: Carry the park site from the marker into `do_stall`.
- **Exports**: `_parse_marker` (now returns `site`), `_finish_park` (budget branch), `PER_PRD_RESET_FIELDS` (+ `prd_budget_since`).

### Module: watchdog
- **Maps to capability**: Session health signals
- **Responsibility**: Idle detection from launch, paused while work is open.
- **Exports**:
  - `session_busy(log_path)` - open tool call or live background task.
  - `Watchdog(..., busy_fn=None)` - new keyword; the runner passes `lambda: session_busy(log_path)`.
- New symbols: `session_busy`, `busy_fn`, `_wait_pre_cap`, `test_idle_kill_before_cap_when_silent_and_no_open_tool_use`, `test_no_idle_kill_while_tool_use_open`

### Module: loop entry
- **Maps to capability**: In-code entry
- **Responsibility**: Pre-launch `enter()`, the stored result, and its replay.
- **Exports**:
  - `Loop._pre_enter(ap_dir)` - called in `Loop._launch_phase` before routing; `enter_fn` is a new injectable `Loop.__init__` keyword (default `enter.enter`).
  - `brief._entry_lines(state)` - the `## Entry` section (prd, catchup, design, stop), rendered after `## Where` only when `loop_entry` is present, so the golden brief is unchanged.
- New symbols: `_pre_enter`, `enter_fn`, `loop_entry`, `_entry_lines`, `prd_budget_since`, `Loop._pre_enter`, `brief._entry_lines`, `state.prd_budget_since`, `test_loop_entry_then_skill_entry_writes_one_resume_row`

## Dependency Graph

### Foundation Layer (Phase 0)
No dependencies - built first.

- **records**: park site in the marker, reset field.
- **watchdog**: `session_busy`.
- **enter**: `prd_budget_since` write.

### Core Layer (Phase 1)
- **loop_decision**: Depends on [records, enter]
- **watchdog pre-cap idle + runner**: Depends on [watchdog]
- **loop entry**: Depends on [enter, records]

### Integration Layer (Phase 2)
- **docs**: Depends on [loop_decision, loop entry]

## Implementation Phases

### Phase 0: Foundation
**Goal**: Building blocks with their own tests.

**Tasks**:
- [ ] `_parse_marker` returns `site` (default `"wrapper_died"`); `_finish_park` with `site == "budget"` calls `do_stall(site="budget", extra_mutator=None)` and returns 0 (no `park_decision` systemic branch); add `"prd_budget_since"` to `PER_PRD_RESET_FIELDS` (no deps) - Acceptance: `uv run --no-project --with pytest python -m pytest -q skills/run-autopilot/cli/test_records_park.py -k "budget_site"` passes: a budget marker parks to hold/, the deferred record has `site: "budget"`, and `batch.parks_consecutive` is 0 after.
- [ ] `session_busy(log_path)` in `cli/watchdog.py` per the Behavior above (no deps) - Acceptance: `uv run --no-project --with pytest python -m pytest -q skills/run-autopilot/cli/test_watchdog.py -k session_busy` passes on fixtures for: open tool_use, closed pair, non-empty then empty `background_tasks_changed`, unreadable file (False), malformed lines skipped.
- [ ] `enter._write_prd` sets `prd_budget_since` (from the injected `now`) when absent or when the pre-write `state.prd` differs (no deps) - Acceptance: `uv run --no-project --with pytest python -m pytest -q skills/run-autopilot/cli/test_enter.py -k budget_since` passes: set on first entry, kept on same-PRD re-entry, refreshed on a different PRD. (Note 2026-10-14: these tests moved to `skills/run-autopilot/cli/test_enter_budget.py`; run `-k budget_since` there, 8 pass. agoge-2026-10-14 packet 29.)

**Exit Criteria**: the three filters above pass.

### Phase 1: Core
**Goal**: The guards act in the loop.

**Tasks**:
- [ ] `budget_usd_for`, `_budget_bound`, the call in `_run_loop`, and `_act_park` writing `"site"` when `decision["park_site"]` is set (depends on: Phase 0) - Acceptance: `uv run --no-project --with pytest python -m pytest -q skills/run-autopilot/cli -k "test_budget_park_lands_prd_in_hold_and_next_prd_launches or test_budget_resets_after_resume_from_hold or test_budget_zero_disables"` passes. The first drives the loop with scripted sessions whose costs sum past $300 for one PRD. The second parks at $310, moves the PRD back to backlog/, and asserts the next session relaunches without a park.
- [ ] Instant exit in `_decide` and the `then` dispatch in `_act_branch` (depends on: Phase 0) - Acceptance: `uv run --no-project --with pytest python -m pytest -q skills/run-autopilot/cli/test_loop_decision.py -k instant_exit` passes, including `test_instant_exit_signal_then_died_retry_without_limit` (3 s, $0: retry first, park second, `_died_retries` not reset by the touched state) and `test_instant_exit_waits_when_usage_limit_detected`.
- [ ] `Watchdog` `busy_fn` and the pre-cap idle polling (`_wait_pre_cap`); `runner._run_session` passes `busy_fn` (depends on: Phase 0) - Acceptance: `uv run --no-project --with pytest python -m pytest -q skills/run-autopilot/cli/test_watchdog.py -k "test_idle_kill_before_cap_when_silent_and_no_open_tool_use or test_no_idle_kill_while_tool_use_open or test_idle_zero_keeps_cap_only"` passes, with small `idle_secs`/`cap_secs` against a real sleeping child.
- [ ] `Loop._pre_enter`, `enter_fn`, `loop_entry`, the `_run_enter` replay, `brief._entry_lines` (depends on: Phase 0) - Acceptance: `uv run --no-project --with pytest python -m pytest -q skills/run-autopilot/cli -k "test_loop_entry_then_skill_entry_writes_one_resume_row or test_stale_loop_entry_is_dropped or test_pre_enter_failure_launches_without_entry or test_brief_entry_section"` passes. The first counts calls to a patched `enter_io.record_resume_row` across the loop's `_pre_enter` plus `__main__.main(["enter", ...])`: exactly 1. `uv run --no-project --with pytest python -m pytest -q skills/run-autopilot/cli/test_brief.py` stays green (golden unchanged).

**Exit Criteria**: all Phase 1 filters pass.

### Phase 2: Integration
**Goal**: Docs match the code.

**Tasks**:
- [ ] `references/state-schema.md` rows for `loop_entry` and `prd_budget_since`; the `## Entry` sentence in `references/phase-build.md` § Enter in one call; the `_AUTOPILOT_PRD_BUDGET_USD` knob beside the other `_AUTOPILOT_*` knobs in the run-autopilot docs; CHANGELOG `[Unreleased]` Added entries for the budget, instant-exit and idle-from-launch guards (depends on: Phase 1) - Acceptance: `rg -n "prd_budget_since|loop_entry" skills/run-autopilot/references/state-schema.md` hits both; `rg -n "_AUTOPILOT_PRD_BUDGET_USD" skills/run-autopilot` hits code and docs; `uv run --no-project --with pytest python -m pytest -q skills/run-autopilot/cli/test_enter_prose.py skills/run-autopilot/cli/test_doc_contract.py` passes.

**Exit Criteria**: `bash dev/bin/release-checks` exits 0 with `FAIL 0` on its summary line.

## Test Strategy

### Critical Scenarios
- **Happy path**: three scripted sessions at $120 each for PRD X → the third decision is `park` with `park_site: "budget"`; the loop's next `_pre_enter` moves X to hold/ and selects PRD Y → Expected: Y launches.
- **Edge case**: X parked at $310, moved to backlog/ → `prd_budget_since` refreshed on entry → Expected: next $50 session continues.
- **Edge case**: 25 min silent inside an open Bash `tool_use`, cap not reached → Expected: no kill.
- **Edge case**: a review session idle after its `result` while `background_tasks_changed` lists a live codex task → Expected: no kill.
- **Error case**: `enter()` raises in `_pre_enter` → Expected: one stderr line, session launches, no `loop_entry`.
- **Error case**: 3 s, $0 session, no limit event → Expected: `instant_exit`, `then: continue` (retry 1/1), next one `then: park`.

## Risks

- **`total_cost_usd` not cumulative**: the budget reads the last `result` event (`last_result_field`). The watched run showed 14 events at the same $18.58 before it rose, which fits a cumulative total. If it is not, the guard undercounts and parks late, never early.
- **Idle kill on a quiet reviewer**: work held in a background task or an open tool call pauses the timer. Only true silence with nothing in flight is killed.
- **Crash loop dodging the cap**: every row for the PRD counts, `died` and `instant_exit` included.
- **Kill routing**: discovery F4 says a kill routes to died/retry; this PRD keeps today's decision table so a session that touched state resumes instead of re-running a half-done task. Ratified at the backlog review of 2026-10-12.
- **Two writers at hand-off**: the loop's `enter()` runs strictly before launch and the session's call replays it. The one-resume-row test pins the order.
- **Resume straight to wip/ by hand**: still a fresh budget, because the park cleared `prd_budget_since` through `PER_PRD_RESET_FIELDS`.
- **Unknown cause of the 2-7 s sessions**: their logs were not kept. F3 routes them deterministically whatever the cause; the `instant_exit` rows give the next batch the data.
