---
catchup: run
design: run
default_model: opus
model_tier_rationale: a new headroom predicate inside the hook that rotates sessions, plus a routing change that decides which model every build session runs on
---

# Hand off on usage headroom and decouple the session model

Source: `dev/local/discovery/00193-cut-loop-overhead-without-thinning-review.md`
(PRD 2 of three; elicited 2026-09-07). Re-grounded 2026-09-13; at the
2026-09-13 backlog review it absorbed the turn-headroom capability from PRD
00196 so one predicate covers usage and calls. Lands after backlog PRD 00191
(`clear the handoff marker at phase edges`, which owns the marker's JSON
shape and step 6.5's phase preservation) and after 00196 (the hook's phase
guard).

## Overview

### Problem Statement

The context-cap hook writes `.handoff-requested` at a flat
`SOFT_CAP = 320_000` (`autopilot_context_cap_hook.py:84`) regardless of what
the next task needs, so a session either hands off with 180K of headroom
left (one small task per session, ~$8 of orientation each) or runs a second
opus task into the 500K hard cap and rotates. The turn tripwire
`TURN_TRIPWIRE = 300` (:90) has no boundary form at all: the measured norm
is ~100 calls of orientation plus ~200 per opus task, so the second task in
a session always dies mid-flight (agent-skills 2026-09-13: tasks 10, 12 and
13 each rotated after their tests or code were already committed), and a
second fire on one task parks the PRD as `oversized_task`.

`routing.build_model` (`cli/routing.py:170`) promotes the whole build
session to opus when the PRD frontmatter says `default_model: opus` (:184,
`_frontmatter_pins_opus` :85). That key is documented as the per-task tier
floor for `/autopilot:plan-tasks`; using it to pick the orchestrator model
cost $283 of $556 build spend across three pinned PRDs in the last two
batches for sessions that only orchestrate.

### Target Users

The loop operator paying per session, and PRD authors who pin a task floor
without meaning to buy an opus orchestrator.

### Success Metrics

- Cap-hook tests: no `.handoff-requested` while both headrooms exceed the
  last task's usage and calls; the marker appears once either does not.
- `test_routing.py`: `build_model` returns SONNET for a PRD that pins
  `default_model: opus` and OPUS for `session_model: opus`.
- Post-release signals, not judged in-session: fewer `build->build` handoff
  rows per PRD than tasks in `dispatch-metrics.jsonl`; no `cap_rotations`
  entry whose task already had a test commit; no session at opus for a PRD
  without `session_model: opus` or a promotion signal.

## Functional Decomposition

### Capability: Headroom handoff
The soft cap becomes "hand off when the next task would not fit", measured
in both context and tool calls.

#### Feature: Task usage and call record
- **Description**: The hook writes `state.tasks[i].usage_at_start` and
  `calls_at_start` on the first PostToolUse after the task turns
  `in_progress`, and `usage_at_done` and `calls_at_done` on the first
  PostToolUse after it turns `completed`.
- **Inputs**: `_latest_usage_total(transcript)` (hook :193), the session's
  count in `.turn-counts.json`, `state.tasks[]`.
- **Outputs**: the four integers on the task entry, written through
  `_write_via_transaction` (hook :322).
- **Behavior**: one write per transition; a task that already carries the
  field is not rewritten; a non-int value is treated as absent with one
  stderr line.

#### Feature: Headroom rule
- **Description**: `.handoff-requested` is written when
  `USAGE_CAP - total < last_task_usage` or
  `TURN_TRIPWIRE - count < last_task_calls`, where the last-task values come
  from the most recently completed task in this session, or the fixed
  estimates `FIRST_TASK_USAGE_ESTIMATE = 150_000` (measured opus tasks:
  118K and 187K) and `FIRST_TASK_CALLS_ESTIMATE = 200` when none.
- **Inputs**: the task record, `USAGE_CAP`, `TURN_TRIPWIRE`.
- **Outputs**: the one-shot marker exactly as `_request_handoff` (hook :442)
  writes it after 00191.
- **Behavior**: `_headroom_exhausted(total, count, last_usage, last_calls)
  -> bool`. `SOFT_CAP` is deleted, together with its docstring mentions
  (hook :21, :28, :79) and the `_soft_limit` accessor (:166);
  `work/references/task-boundary-handoff.md:7` ("crosses the soft
  threshold") says "when the headroom rule fires". `TURN_TRIPWIRE` becomes
  450 (orientation plus two measured opus tasks, minus the margin the rule
  provides); the hard tripwire keeps its rotation semantics. Two rules for
  the no-task case, both observed 2026-09-13: a breach with no task in
  progress (`_in_progress_task_id` returns `"unknown"`, hook :243-251,
  as during design or planning) writes its rotation entry as today but
  never counts toward the livelock guard in `_fire_breach` (:558), so two
  long design or planning phases in a row cannot park a PRD as
  `oversized_task "unknown"`; and the build gate checks the same headroom
  rule at the design->plan and plan->work edges (`references/phase-build.md`
  Phase 1.5 exit and Phase 2 exit), handing off to a fresh build session
  when `TURN_TRIPWIRE - count < FIRST_TASK_CALLS_ESTIMATE` or
  `USAGE_CAP - total < FIRST_TASK_USAGE_ESTIMATE`. PRD 00187's design step
  alone used 249 calls and 338K before planning started.

### Capability: Marker placement
The work skill honours the marker in exactly one place.

#### Feature: Step 6.5 only, after task-done
- **Description**: `skills/work/SKILL.md` step 6.5 (:459) states that
  `.handoff-requested` is read only there, after the `task-done` write of
  step 6 (:452) has landed; a marker noticed earlier is carried, never acted
  on. Today step 6.5 and `task-boundary-handoff.md:16-19` are the only
  readers, so this is one clarifying sentence that pins the placement PRD
  00182's batch violated when a session handed off with task 1 committed but
  still `in_progress`.
- **Inputs**: the marker file.
- **Outputs**: the handoff procedure in `task-boundary-handoff.md`, unchanged.
- **Behavior**: step 6.5 gains the sentence `A marker seen before this step
  is carried to this step; between the commit of step 5 and the task-done
  write of step 6 the marker is never acted on.` A prose test pins it.

### Capability: Session model decoupled from the task floor
`default_model` floors tasks; `session_model` picks the orchestrator.

#### Feature: `session_model` frontmatter key
- **Description**: `cli/frontmatter.py` accepts `session_model: sonnet | opus`
  (default `sonnet`, silent default on absence, one-line warning on an
  unrecognized value) into state field `session_model`, the eighth
  recognized key beside `catchup`, `design`, `doubt_reviewer`,
  `consensus_engine`, `rework_cap`, `design_gate` and `pause_on_ambiguity`.
- **Inputs**: PRD frontmatter.
- **Outputs**: `state.session_model`; a row in `references/state-schema.md`;
  a line in the `create-prd` frontmatter list of the agent-skills repo (out
  of this repo; recorded in the CHANGELOG entry as a follow-up).
- **Behavior**: re-derived per PRD at Phase 0 like `doubt_reviewer`, and
  like it NOT listed in `records.PER_PRD_RESET_FIELDS` (`records.py:95-96`
  keeps the frontmatter-derived enums out of that list on purpose).

#### Feature: Routing reads `session_model`
- **Description**: `routing.build_model` returns OPUS on
  `session_model: opus` and no longer on `default_model: opus`; the other
  promotion signals (replan, stall, cap rotation, rescue ledger, deferred
  stall) are unchanged.
- **Inputs**: `build_model(state_path, prds_dir, ledger_path, deferred_dir)`
  as today (:170-175); the target PRD path is derived inside via
  `build_target(prds_dir)` (:180).
- **Outputs**: `OPUS` or `SONNET`.
- **Behavior**: `_frontmatter_pins_opus(prd_path)` becomes
  `_frontmatter_session_model(prd_path) -> str | None` using the same line
  grammar (`_DEFAULT_MODEL_OPUS` :44 renamed `_SESSION_MODEL_RE`, key
  `session_model`, values `opus|sonnet`). `loop-metrics.jsonl` already
  records `model` (`cli/loop.py:916`); no change.

## Structural Decomposition

### Repository Structure

```
skills/
├── run-autopilot/
│   ├── scripts/
│   │   ├── autopilot_context_cap_hook.py       # Maps to: Headroom handoff
│   │   └── test_autopilot_context_cap_hook.py  # rewritten soft-cap and tripwire cases
│   ├── cli/
│   │   ├── frontmatter.py                       # Maps to: session_model key
│   │   ├── routing.py                           # Maps to: routing reads it
│   │   ├── test_frontmatter.py, test_routing.py
│   └── references/
│       ├── state-schema.md                      # Maps to: session_model row; signal table :453, :464
│       └── model-ladder.md                      # signal row :303
└── work/
    ├── SKILL.md                                 # Maps to: marker placement
    ├── references/task-boundary-handoff.md      # soft-threshold wording
    └── scripts/test_handoff_placement_prose.py  # new prose pin
```

### Module: autopilot_context_cap_hook
- **Maps to capability**: Headroom handoff
- **Responsibility**: record task usage and calls; request a handoff when
  the next task will not fit in context or in calls
- **Exports**: `_record_task_bounds(state, task_id, total, count)`,
  `_headroom_exhausted(total, count, last_usage, last_calls) -> bool`

### Module: frontmatter + routing
- **Maps to capability**: Session model decoupled from the task floor
- **Responsibility**: parse the key; route the build session on it
- **Exports**: `frontmatter.parse()` (extended), `routing.build_model()`,
  `routing._frontmatter_session_model()`

### Module: work SKILL prose
- **Maps to capability**: Marker placement
- **Responsibility**: the one place the marker is read
- **Exports**: none (prose pinned)

## Dependency Graph

### Foundation Layer (Phase 0)
No dependencies - built first.

- **frontmatter**: the key.
- **autopilot_context_cap_hook (task record)**: the four fields.

### Core Layer (Phase 1)
- **routing**: Depends on [frontmatter].
- **autopilot_context_cap_hook (headroom rule)**: Depends on [task record].

### Integration Layer (Phase 2)
- **work SKILL prose, state-schema.md, model-ladder.md**: Depends on [Phase 1].

## Implementation Phases

### Phase 0: Foundation
**Goal**: the inputs exist.

**Tasks**:
- [ ] `session_model` in `frontmatter.py` (no deps) - Acceptance:
  `test_frontmatter.py::test_session_model_defaults_to_sonnet`,
  `::test_session_model_opus_is_accepted`,
  `::test_session_model_bad_value_warns_and_defaults`;
  `test_optional_markers_stay_absent_rather_than_false` unchanged.
- [ ] Task usage and call record in the hook (no deps) - Acceptance: in the
  existing `unittest` classes of `test_autopilot_context_cap_hook.py`, new
  methods `test_usage_and_calls_at_start_are_written_once` and
  `test_usage_and_calls_at_done_are_written_on_completion`.

**Exit Criteria**: both suites green.

### Phase 1: Core
**Goal**: the decisions use them.

**Tasks**:
- [ ] Headroom rule replaces `SOFT_CAP`; `TURN_TRIPWIRE` becomes 450
  (depends on: Phase 0) - Acceptance: new methods
  `test_headroom_above_last_task_writes_no_marker` (total 300K, count 120,
  last task 150K / 200 -> none), `test_usage_headroom_below_last_task_writes_marker`
  (total 380K -> marker), `test_call_headroom_below_last_task_writes_marker`
  (count 260 -> marker), `test_first_task_uses_the_fixed_estimates`,
  `test_unknown_task_breach_never_livelocks` (two consecutive breaches with
  no in-progress task -> two rotation entries, no `stall_reason`);
  `test_soft_threshold_writes_handoff_marker` (:529) and
  `test_below_soft_threshold_writes_no_marker` (:553) are rewritten to the
  rule; `test_cap_constants_and_tripwire` (:814), `test_tripwire_fires_at_300`
  (:827) and `test_tripwire_does_not_fire_at_299` (:842) become their 450
  and 449 forms; `test_hard_cap_overrun_writes_no_handoff_marker` (:566)
  unchanged; `rg -c "SOFT_CAP|_soft_limit|soft threshold" skills/run-autopilot/scripts/autopilot_context_cap_hook.py skills/work/references/task-boundary-handoff.md`
  returns 0 for both files.
- [ ] Routing reads `session_model` (depends on: Phase 0) - Acceptance: the
  four signal-1 tests in `test_routing.py` are repointed to the new key:
  `test_signal1_frontmatter_opus_promotes` (:158) becomes
  `test_signal1_session_model_opus_promotes`, `test_signal1_body_mention_is_not_frontmatter`
  (:166) and `test_signal1_no_frontmatter_at_all_ignores_body` (:178) keep
  their names with `session_model` fixtures, and the parametrized
  `test_signal1_frontmatter_edge_grammar` table (:180-254) is rewritten
  case-for-case with `session_model` in place of `default_model`; new
  `test_default_model_opus_no_longer_promotes` and
  `test_session_model_sonnet_is_explicit_sonnet`; the signal 2-5 tests
  (:262, :270, :278, :373, :381) unchanged.

**Exit Criteria**: `pytest -q skills/run-autopilot` green.

### Phase 2: Integration
**Goal**: prose and schema say what the code does.

**Tasks**:
- [ ] Step 6.5 placement sentence and the `task-boundary-handoff.md`
  soft-threshold rewording (depends on: Phase 1) - Acceptance:
  `test_handoff_placement_prose.py::test_marker_is_read_only_at_step_6_5`
  pins the sentence; `test_style_gate_prose.py` still green.
- [ ] Gate-edge headroom check in `phase-build.md` at the Phase 1.5 and
  Phase 2 exits (depends on: Phase 1) - Acceptance:
  `test_handoff_placement_prose.py::test_build_gate_hands_off_at_design_and_plan_edges`
  finds the sentence naming both estimates at both exits.
- [ ] `state-schema.md` row for `session_model` and its signal table rows
  (:453, :464) plus `model-ladder.md:303` say `session_model`, not
  `default_model`, drives the session (depends on: Phase 1) - Acceptance:
  `rg -c "session_model" skills/run-autopilot/references/state-schema.md skills/run-autopilot/references/model-ladder.md`
  returns 1 or more for each; `rg -n "default_model: opus" skills/run-autopilot/references/model-ladder.md skills/run-autopilot/references/state-schema.md`
  returns only lines that describe the task floor.
- [ ] CHANGELOG: `### Changed` for the headroom rule, the tripwire form and
  the decoupling, naming that backlog PRDs pinning `default_model: opus`
  now run a sonnet orchestrator unless they add `session_model: opus`, and
  that the create-prd skill (agent-skills repo) needs the new key (depends
  on: all) - Acceptance: `rg -c "session_model" CHANGELOG.md` returns 1 or
  more.

**Exit Criteria**: `bash dev/bin/release-checks` green.

## Test Strategy

### Critical Scenarios
- **Happy path**: two tasks of 120K / 150 calls each in a 500K / 450-call
  session -> no marker after task 1, marker after task 2 once the totals
  reach 390K or 300 calls.
- **Edge case**: `usage_at_start` present but `usage_at_done` absent on the
  last completed task -> the fixed estimates are used, never a negative.
- **Edge case**: PRD with both `default_model: opus` and no `session_model`
  -> SONNET session, opus task floor untouched.
- **Error case**: non-int record fields on a task -> treated as absent; one
  stderr line; no crash.

## Risks

- **A longer session hits the hard cap or tripwire**: the headroom rule
  keeps taking tasks while they fit; the hard-cap rotation and the 450-call
  tripwire stay the backstops and the first-task estimates err high.
- **`session_model` drift**: `default_model: opus` PRDs already in the
  backlog silently lose the opus orchestrator; the release note says so and
  the create-prd skill (agent-skills repo) gets the new key in a follow-up.
- **00196 and this PRD edit the hook**: sequenced 00196 first; this PRD's
  fixtures set `phase: "build"` and do not depend on 00196's guard.
