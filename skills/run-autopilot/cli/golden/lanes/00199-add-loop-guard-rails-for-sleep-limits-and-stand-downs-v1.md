---
catchup: run
design: run
default_model: opus
model_tier_rationale: timing and interleaving decide correctness (poll budget across sleep, reset waits, a bounded peer wait), and the loop code is the batch's own life support
---

# Add loop guard rails for sleep, limits and stand-downs

Source: `dev/local/discovery/00193-cut-loop-overhead-without-thinning-review.md`
(PRD 1 of three; elicited 2026-09-07). Re-grounded against the tree on
2026-09-13. Lands after backlog PRD 00192 (`split cli/loop.py and
test_loop.py under the file cap`): both edit `loop.py`, and 00192 moves the
decision table into sibling modules, so the locations below are read as
"wherever 00192 put `_decide_no_progress`" when it has landed first.

Premise (re-check at execution, skip and report if it fails): the `autoclaude`
shell function in `~/.config/bash/plugins/development.plugin.bash` already
runs the loop under `caffeinate -is` (commit `ff42cbd` pins its test stub), so
the discovery's caffeinate requirement is already met and is NOT part of this
PRD. Nothing here adds a second `caffeinate`.

## Overview

### Problem Statement

Batches 202609061630 and 202609050909 lost about 17 idle hours to three kinds
of loop misjudgement, none of which touched what the review lenses check:

- A lid-close sleep was counted by the API-unreachable poll as outage:
  `_decide_no_progress` sets `deadline = self._clock() + net_max` (loop.py
  :807) with `self._clock` defaulting to `time.time`, inside an outer retry
  loop bounded by `_AUTOPILOT_NET_RETRIES_MAX` (default 3, :803-805), so a
  sleeping machine "spends" up to three `_AUTOPILOT_NET_WAIT_MAX` budgets
  and three relaunches before the loop declares `repeated API connection
  failures`.
- Two loops on one account both consumed the five-hour window; the overage
  allowance was drained overnight and a hard stop followed. `usage_limit`
  parses only `status: "rejected"` events and only inside branch 5
  (no-progress), so a session that made progress and ended with a rejected
  event is relaunched immediately, and an `allowed_warning` event is never
  read.
- A stand-down fired on a monitoring session: the rule in run-autopilot
  `SKILL.md` (the bold run-in paragraph `**Stand-down procedure (a peer
  session owns the PRD).**` at :168, inside `## Session Loop`; there is no
  heading of that name) pauses on "busy interactive peer AND a state or
  artifact write within 15 minutes", and a reader that merely inspects
  state while the loop writes satisfies both halves.

### Target Users

The loop operator running one or two batches on one account, usually away
from the machine.

### Success Metrics

- `uv run --no-project --with pytest python -m pytest -q skills/run-autopilot/cli`
  green with the new tests named in the phases below.
- Post-release signals, not judged in-session: no `loop-metrics.jsonl` row
  with `signal: died` and detail `API unreachable` across a sleep; no
  `paused` row whose `stood_down` reason names a reader; the younger of two
  loops shows a `limit_wait` row at the warning instead of a hard stop.

## Functional Decomposition

### Capability: Sleep-proof connectivity poll
The outage budget counts probes, not wall-clock.

#### Feature: Probe-count outage budget
- **Description**: The API-unreachable poll in `_decide_no_progress` makes at
  most `net_max // 30` probes per retry, 30 s apart, and relaunches on the
  first success; a machine sleep between probes costs nothing.
- **Inputs**: `_AUTOPILOT_NET_WAIT_MAX` (default 1800),
  `_AUTOPILOT_NET_RETRIES_MAX` (default 3, unchanged), the injected
  `probe_fn` and `sleep_fn`.
- **Outputs**: `decision["signal"]` `continue` on a successful probe, `died`
  with `API unreachable for <n> probes` after one retry's budget; the outer
  retry counter `self._net_retries` and its `repeated API connection
  failures` verdict are unchanged.
- **Behavior**: replace the `deadline` / `self._clock()` comparison with a
  `for _ in range(max(1, net_max // 30))` loop inside the existing retry
  branch; `self._clock` stays for the usage-limit arithmetic. The stderr
  line says `max <n> probes` instead of `max <net_max>s`.

### Capability: Window-aware relaunch
The loop yields the shared five-hour window to the oldest loop and never
spends overage.

#### Feature: Warning parse
- **Description**: `usage_limit` gains `_warning_reset(tail) -> int | None`
  beside `_rejected_reset`: the `resetsAt` of the tail's last
  `rate_limit_event` whose `rate_limit_info.status == "allowed_warning"`
  and whose `rateLimitType == "five_hour"` (the seven-day window is a
  reporting signal, per the discovery's stated default), with the same
  `GRACE_SECS` staleness rule.
- **Inputs**: the session log tail.
- **Outputs**: an epoch or None.
- **Behavior**: `detect_from_log` is unchanged; a new
  `detect_warning_from_log(path)` wraps the warning parse for the loop.

#### Feature: Yield at the warning
- **Description**: After any session, if the log carries a live
  `allowed_warning` and this loop is not the live loop with the oldest
  `started_at` in `~/.claude/autopilot-loops/*.json`, the loop sleeps until
  that `resetsAt` (through `wait_decision`, bounded by
  `_AUTOPILOT_LIMIT_WAIT_MAX`) before the next launch.
- **Inputs**: the registry entries (`pid`, `started_at`), `_pid_alive`.
- **Outputs**: `decision["limit_wait"]` and a detail
  `yielding the window to loop <pid> until ~HH:MM`.
- **Behavior**: the check runs on the `continue` path too, not only in
  branch 5. The oldest live loop never yields. Kill switch:
  `_AUTOPILOT_NO_YIELD=1`.

#### Feature: Rejected never enters overage
- **Description**: A session log whose tail carries a live `rejected` event
  makes the loop sleep to `resetsAt` before relaunching, whatever
  `overageStatus` says and whether or not the session made progress.
- **Inputs**: `_rejected_reset(tail)`.
- **Outputs**: `limit_wait` on the continue path.
- **Behavior**: today the limit check lives only in `_decide_no_progress`;
  it moves to a `_limit_wait_for(ap_dir, decision)` helper called from both
  the progress and the no-progress paths. The beyond-cap branch keeps its
  `died` semantics.

### Capability: Ask-first stand-down
Phase 0 pauses only for a writer.

#### Feature: Ask the peer, then decide
- **Description**: When Phase 0 sees a busy interactive peer in this repo
  (a peer counts only when its `ListAgents` name starts with this repo's
  directory basename, e.g. `agent-skills-`; on 2026-09-14 10:15 an
  agent-skills session stood down for `claude-autopilot-c7`, another repo's
  loop session, because it also read its own predecessor's 60-second-old
  state write as a peer write), it sends the peer one `SendMessage` naming
  the PRD and waits at most 120 s for a reply; it stands down only when the reply claims the PRD, or when
  writer evidence is present: `git status --porcelain` lists a tracked path
  (an uncommitted edit this session did not make), or the mtime of
  `state.json` or `contract-card.md` is later than the `at` of this batch's
  most recent `handoff` row with `edge: "leave"` in `dispatch-metrics.jsonl`
  (state written after the previous loop session left). Commit trailers are
  not consulted: no commit in this repo carries a session trailer (aegis
  `validate_commit_msg.py` rejects them).
- **Inputs**: `ListAgents`, `git status --porcelain`, the two mtimes, the
  last `leave` row, `SendMessage`.
- **Outputs**: `pause-requested` written with
  `{"reason": "...", "condition": "peer_claimed" | "dirty_tree" | "state_after_leave"}`;
  or the session continues.
- **Behavior**: `pause.stand_down_reason` returns the reason as today and
  the loop writes both `stood_down` (the reason, today only on `decision`)
  and `stood_down_condition` (from the marker's `condition` field,
  `"unknown"` when absent) into the `paused` loop-metrics row, which today
  carries neither. A peer that only reads, or never answers, never pauses a
  batch. When no `leave` row exists for this batch, the mtime test is
  skipped and only the dirty-tree test and the reply decide.

## Structural Decomposition

### Repository Structure

```
skills/run-autopilot/
├── cli/
│   ├── loop.py                 # Maps to: probe budget, yield, rejected wait
│   ├── usage_limit.py          # Maps to: warning parse
│   ├── pause.py                # Maps to: stand-down condition
│   ├── test_loop.py            # new cases (post-00192 file if split)
│   ├── test_usage_limit.py     # new cases
│   └── test_pause.py           # new file
├── SKILL.md                    # Maps to: ask-first stand-down prose
└── scripts/
    └── test_stand_down_prose.py   # new prose pin
```

### Module: loop
- **Maps to capability**: Sleep-proof connectivity poll; Window-aware relaunch
- **Responsibility**: the branch-5 decision and the pre-launch wait
- **Exports**:
  - `Loop._probe_budget(net_max) -> int`
  - `Loop._limit_wait_for(ap_dir, decision) -> None`
  - `Loop._oldest_live_loop_pid() -> int | None`

### Module: usage_limit
- **Maps to capability**: Window-aware relaunch
- **Responsibility**: read reset epochs out of a session log tail
- **Exports**: `_warning_reset()`, `detect_warning_from_log()`

### Module: pause
- **Maps to capability**: Ask-first stand-down
- **Responsibility**: the marker's reason and condition
- **Exports**: `stand_down_reason()`, `stand_down_condition()`

### Module: run-autopilot SKILL.md
- **Maps to capability**: Ask-first stand-down
- **Responsibility**: the Phase 0 procedure text
- **Exports**: none (prose pinned by `test_stand_down_prose.py`)

## Dependency Graph

### Foundation Layer (Phase 0)
No dependencies - built first.

- **usage_limit**: warning parse.
- **pause**: condition field.

### Core Layer (Phase 1)
- **loop**: Depends on [usage_limit, pause].

### Integration Layer (Phase 2)
- **run-autopilot SKILL.md**: Depends on [pause].

## Implementation Phases

### Phase 0: Foundation
**Goal**: the parsers exist and are pinned.

**Tasks**:
- [ ] Add `_warning_reset` and `detect_warning_from_log` (no deps) -
  Acceptance: `test_usage_limit.py::test_warning_reset_reads_allowed_warning`
  and `::test_warning_reset_ignores_a_stale_warning` pass; the existing
  four wait tests unchanged.
- [ ] Add `stand_down_condition` reading the marker's `condition` (no deps)
  - Acceptance: `test_pause.py::test_condition_defaults_to_unknown` and
  `::test_condition_is_read_from_the_marker` pass.

**Exit Criteria**: `pytest -q skills/run-autopilot/cli/test_usage_limit.py skills/run-autopilot/cli/test_pause.py` green.

### Phase 1: Core
**Goal**: the loop uses them.

**Tasks**:
- [ ] Probe-count outage budget (depends on: none) - Acceptance:
  `test_loop.py::test_outage_poll_survives_a_two_hour_clock_jump` (fake clock
  jumps 7200 s between two probes; the loop still relaunches on the third
  probe's success) and `::test_outage_poll_dies_after_the_probe_budget`
  (60 failed probes at `net_max=1800` -> `died`).
- [ ] `_limit_wait_for` on both paths (depends on: Phase 0) - Acceptance:
  `test_loop.py::test_rejected_with_overage_allowed_still_sleeps` (progress
  made, tail has `rejected` + `overageStatus: allowed` -> `limit_wait` set)
  and `::test_rejected_beyond_cap_still_dies`.
- [ ] Yield at the warning (depends on: Phase 0) - Acceptance:
  `test_loop.py::test_younger_loop_yields_at_allowed_warning` (two registry
  entries, this pid younger -> `limit_wait`), `::test_oldest_loop_never_yields`,
  `::test_no_yield_kill_switch`.
- [ ] Record `stood_down` and `stood_down_condition` in the paused row
  (depends on: Phase 0) - Acceptance:
  `test_loop.py::test_paused_row_carries_the_stand_down_reason_and_condition`;
  `test_metrics_line_lands_in_primary_and_ledger_mirror` (:683) unchanged.

**Exit Criteria**: `pytest -q skills/run-autopilot/cli` green.

### Phase 2: Integration
**Goal**: Phase 0 asks before it pauses.

**Tasks**:
- [ ] Rewrite the stand-down paragraph (SKILL.md:168, inside `## Session
  Loop`; also the cross-reference at :119) to the ask-first rule (depends
  on: Phase 1) - Acceptance: `test_stand_down_prose.py` locates the
  paragraph by its literal opening `**Stand-down procedure (a peer session
  owns the PRD).**` and pins `SendMessage`, the `120` second bound,
  `git status --porcelain`, the `leave` row, and the three `condition`
  values inside it, plus the repo-basename peer filter sentence;
  `test_doc_contract.py` still green.
- [ ] CHANGELOG entries: `### Fixed` for the poll and the overage rule,
  `### Changed` for the yield and the stand-down (depends on: all) -
  Acceptance: `rg -c "probe|allowed_warning|stand-down" CHANGELOG.md`
  returns 3 or more.

**Exit Criteria**: `bash dev/bin/release-checks` green.

## Test Strategy

### Critical Scenarios
- **Happy path**: outage, probes fail twice, machine sleeps 2 h, third probe
  succeeds -> `continue`, detail `network restored`.
- **Edge case**: registry holds only this loop -> never yields even at
  `allowed_warning`.
- **Edge case**: `allowed_warning` whose `resetsAt` is past `GRACE_SECS` ->
  ignored.
- **Error case**: registry entry unreadable or missing `started_at` -> treated
  as absent (never crashes, one stderr line); the loop does not yield.

## Risks

- **Oldest-loop rule starves a newer batch**: the newer loop idles until the
  reset; the stop line and the `limit_wait` detail say why.
- **Peer that never answers**: the 120 s bound then the writer evidence; a
  silent writer shows up as a dirty tracked path or a state write after the
  last `leave` row. A peer that committed and left a clean tree within the
  window is not caught; that case is the reply's job.
- **00192 lands first or second**: the tasks name functions, not line
  numbers; the design step re-grounds file placement.
