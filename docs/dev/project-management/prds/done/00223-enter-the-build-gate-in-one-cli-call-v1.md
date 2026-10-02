---
catchup: skip
design: run
default_model: opus
model_tier_rationale: invented CLI contract (the enter verb's JSON line and stop values) composed across select, park, custody, frontmatter, resume and the handoff row; a wrong stop mapping resumes a PRD past a handler silently
---

# Enter the build gate in one CLI call

Source: `dev/local/notes/autoclaude-observation-2026-09-28.md` O3 (measured
2026-09-27 session 1 on 0.5.6: 8 min from launch to `/autopilot:work`, of
which 2.5 min were about 15 separate model calls for deterministic Phase 0
steps, all at `--effort xhigh`). Follows 00093 (clerical overhead) and 00201
(session brief). The effort half of O3 is out of scope: `_AUTOPILOT_EFFORT_BUILD`
already exists in `cli/routing.py`, so trying `medium` is an operator
experiment, not code.

## Overview

### Problem Statement

Every build session re-runs Phase 0 of `references/phase-build.md` as a chain
of single Bash calls, each followed by a model turn that reads the output and
picks the next call:

1. the lifecycle `mkdir -p`,
2. `_walk_up.py --clear-markers`,
3. `autopilot park` (exit 3 "nothing to do" on nearly every session),
4. the `stall_reason` / cap-pause checks, read from `state.json` by hand,
5. `autopilot resume-target`,
6. `autopilot custody list`,
7. `autopilot select`, then the verified backlog-to-`wip/` move,
8. a `statectl set prd`, then `autopilot frontmatter`,
9. the `record_dispatch.py handoff --edge resume` row,
10. the Phase 1 batch-cache decision (three conditions, read by hand),
11. the Phase 1.5 design-doc existence check and the empty-review-log `awk`.

Each step is deterministic; the code for most already exists. On a 15-session
two-PRD run that is roughly 35-40 min of wall time (guess: 2.5 min per
session, one session measured) spent on bookkeeping the rules say belongs in
code (`rules/ai-app-design.md`: "if code can answer, code answers").

### Target Users

The unattended loop's build sessions, and the operator reading how long a
session took to reach its first task.

### Success Metrics

- `uv run --no-project --with pytest python -m pytest -q skills/run-autopilot/cli/test_enter.py skills/run-autopilot/cli/test_enter_prose.py`
  green; every existing `test_cli*.py`, `test_resume*.py`, `test_selection.py`,
  `test_lifecycle_cli.py` and `test_autopilot_lifecycle.py` stays green.
- `bash dev/bin/release-checks` green.
- Post-release signal, next batch: a build session's first `autopilot enter`
  call comes before any other Phase 0 Bash call in `last-session.log`, and a
  resumed build session reaches its first `Skill · autopilot:work` within
  3 minutes of launch.

## Functional Decomposition

### Capability: One call runs Phase 0 up to the first judgment

#### Feature: `autopilot enter`
- **Description**: runs the deterministic Phase 0 steps in their documented
  order and prints one JSON line naming where the session goes next.
- **Inputs**: `--state <path>` (default: walk up from cwd, as every verb
  does); `--prd <basename>` (optional, the explicit-argument selection of
  Normal PRD selection step 1); the `_AUTOPILOT_LOOP` environment variable.
- **Outputs**: exit 0 and one JSON line on stdout with exactly these keys
  (guess, the design doc may rename but not drop any):
  `{"stop": <null|string>, "detail": <string>, "prd": <string|null>,
  "source": <"wip"|"backlog"|"arg"|null>, "parked": <string|null>,
  "custody_pending": <int>, "lane_effective": <string|null>,
  "catchup": <"skip"|"delta"|"full"|null>, "design": <"skip"|"reuse"|"run"|null>,
  "resume_target": <string|null>, "batch": <"open"|"absent"|"closed">}`.
  Exit 2 only for an unreadable `state.json` (the corrupted-state row), exit
  6 for a future schema (the `resume-target` preflight, unchanged).
- **Behavior**: steps run in this order; the first step that yields a `stop`
  prints the line and exits 0 without running later steps.
  1. Create the lifecycle directories named in core `SKILL.md` § Phase 0
     invariants.
  2. Clear inherited markers with the function behind `_walk_up.py
     --clear-markers` (import it, do not shell out).
  3. Run the park decision and executor behind `autopilot park`. Its exit 3
     continues; exit 0 continues with `parked` set to the parked basename;
     exits 5, 4, 9, 10 stop with `stop` = `"park_halt"`, `"mv_verify"`,
     `"deferred_io"`, `"stall_op_conflict"` and `detail` = the executor's
     message.
  4. Read `state.json`: `stall_reason.stalled == "subagent_prompt_overrun"`
     stops with `"replan"`; `== "escalation_exhausted"` stops with
     `"escalation_exhausted"`; `phase == "paused"` with `cap_pause_reason`
     set stops with `"cap_pause"`. A `pause_reason` is deleted first (core
     `SKILL.md` § Resuming, unconditional).
  5. Set `resume_target` from `cli/resume.resume_target` (the same string
     `autopilot resume-target` prints).
  6. Count pending custody entries (`cli/custody.pending`). Outside the loop,
     a count above 0 stops with `"custody"`; in the loop the count is
     reported and selection continues.
  7. Select (`cli/selection` plus the eligibility gate, recording skips as
     `select` does). Drained stops with `"drained"`. A `backlog` pick is moved
     to `wip/` and verified; a failed move stops with `"mv_verify"`.
  8. `batch` reports `"absent"` when `state.batch` is missing and `"closed"`
     when `phase == "done"` and `next_phase == ""`; both stop with
     `"batch_init"`, because the batch pin reads the installed plugins and
     stays in the skill. `"open"` continues.
  9. Write `state.prd`, then apply the frontmatter with the code behind
     `autopilot frontmatter` in its single transaction; `lane_effective` is
     read back from the result. A lane other than `full` stops with
     `"lane"` (the lane runbooks own the rest of the session).
  10. Write the `resume` handoff row with the `record_dispatch.py` function
      (best-effort, as today).
  11. `catchup`: `"skip"` when `catchup_mode` is `skip` or `skipped`;
      `"delta"` when the three batch-cache conditions of phase-build.md
      § Batch cache check hold; else `"full"`.
  12. `design`: `"skip"` when `design_mode` is `skip`; `"reuse"` when the
      design doc exists and passes the empty-review-log check (a Python port
      of the pinned `awk` in core `SKILL.md` § Design-gate invariant, same
      regex, section-scoped); an existing doc that fails the check stops with
      `"design_review_log_empty"`; no doc gives `"run"`.
  13. `stop` is null: the session continues at Phase 1 with `catchup` and
      `design` already decided.

### Capability: The skill uses it

#### Feature: Phase 0 starts with `autopilot enter`
- **Description**: the build gate's first action is the verb, and the
  existing sections become the reference for its stops.
- **Inputs**: the JSON line.
- **Outputs**: prose in `references/phase-build.md` and core `SKILL.md`.
- **Behavior**: `phase-build.md` § Phase 0 gains, directly after the session
  brief paragraph, a section `### Enter in one call` that says: run
  `autopilot enter` (one Bash call); when `stop` is null, print the PRD
  banner and go straight to Phase 1 using `catchup` and `design` as decided
  (do not re-run any step 1-12 by hand); when `stop` is set, follow the table
  mapping each `stop` value to the existing section that owns it
  (`park_halt`/`mv_verify`/`deferred_io`/`stall_op_conflict` → § Handle park
  request table rows; `replan`/`escalation_exhausted`/`cap_pause` → § Handle
  Work-phase abort; `custody` → § Handle pending custody; `drained` →
  Normal PRD selection's drained row; `batch_init` → Normal PRD selection
  step 3, then run `autopilot enter` again; `lane` → § 5.5 Route by lane;
  `design_review_log_empty` → the design-gate invariant's non-zero branch).
  Every existing Phase 0 section stays; each gains one line saying `autopilot
  enter` runs it. Core `SKILL.md` § Phase 0 invariants gains one sentence
  naming the verb as the first Bash call of a build session.

## Structural Decomposition

### Repository Structure

```
skills/run-autopilot/cli/
├── enter.py              # Maps to: autopilot enter (the step chain)
├── __main__.py           # Maps to: the `enter` subparser only (the file is already 1253 lines; add a thin dispatch)
├── test_enter.py         # Maps to: Test Strategy (one test per stop value and the null path)
└── test_enter_prose.py   # Maps to: Phase 0 starts with autopilot enter
skills/run-autopilot/references/phase-build.md    # Enter in one call
skills/run-autopilot/SKILL.md                     # Phase 0 invariants sentence
dev/bin/release-checks                            # test_enter_prose.py
CHANGELOG.md
```

### Module: enter
- **Maps to capability**: One call runs Phase 0 up to the first judgment
- **Responsibility**: order the existing Phase 0 functions and translate
  their results into one JSON line; owns no policy of its own.
- **Exports**:
  - `enter(state_path, prd_arg, in_loop, now) -> dict` - the JSON line as a
    dict; pure over its injected callables for git, the clock and the
    handoff row.
  - `STOPS` - the tuple of every `stop` value, which the prose test reads.

## Dependency Graph

### Foundation Layer (Phase 0)
No dependencies - built first.

- **enter**: composes `resume`, `selection`, `eligibility`, `custody`,
  `frontmatter`, `records` (park), `_walk_up` marker clearing and
  `record_dispatch`, all existing.

### Core Layer (Phase 1)
- **`enter` subparser**: Depends on [enter].

### Integration Layer (Phase 2)
- **phase-build.md and SKILL.md prose, prose test, release-checks,
  CHANGELOG**: Depends on [`enter` subparser].

## Implementation Phases

### Phase 0: Foundation
**Goal**: the step chain exists and every stop is reachable in a test.

**Tasks**:
- [ ] Write `cli/enter.py` with `enter()` and `STOPS` (no deps) - Acceptance:
  `test_enter.py::test_fresh_wip_prd_continues_with_null_stop`,
  `::test_backlog_pick_is_moved_and_verified`,
  `::test_failed_move_stops_mv_verify`,
  `::test_park_exit_three_continues`, `::test_park_exit_zero_sets_parked`,
  `::test_park_halt_codes_map_to_their_stops` (parametrized over 5, 4, 9, 10),
  `::test_prompt_overrun_stops_replan`,
  `::test_escalation_exhausted_stops`, `::test_cap_pause_stops`,
  `::test_pause_reason_is_deleted_before_the_checks`,
  `::test_custody_stops_outside_the_loop_only`,
  `::test_drained_stops`, `::test_absent_and_closed_batch_stop_batch_init`,
  `::test_non_full_lane_stops_lane`,
  `::test_catchup_delta_needs_all_three_conditions`,
  `::test_design_reuse_needs_a_review_log_line`,
  `::test_empty_review_log_stops`,
  `::test_resume_target_matches_the_resume_target_verb`,
  `::test_every_stop_value_is_in_STOPS` green.

**Exit Criteria**: `test_enter.py` green; `enter.py` under 400 lines, every
function under 50.

### Phase 1: Core
**Goal**: the verb is callable.

**Tasks**:
- [ ] Add the `enter` subparser and dispatch to `cli/__main__.py` (depends
  on: Phase 0) - Acceptance:
  `test_enter.py::test_cli_prints_one_json_line_with_every_key`,
  `::test_cli_unreadable_state_exits_two`,
  `::test_cli_future_schema_exits_six` green; every existing `test_cli*.py`
  green.

**Exit Criteria**: `python3 skills/run-autopilot/cli/__main__.py enter
--state <fixture>` prints one JSON line in the tests.

### Phase 2: Integration
**Goal**: sessions use it.

**Tasks**:
- [ ] Add `### Enter in one call` to `references/phase-build.md`, the one-line
  pointers in each Phase 0 section, the `SKILL.md` sentence,
  `test_enter_prose.py` in `dev/bin/release-checks`, and the CHANGELOG entry
  (depends on: Phase 1) - Acceptance:
  `test_enter_prose.py::test_phase_0_opens_with_autopilot_enter`
  (the section exists before `### Ensure lifecycle directories exist`),
  `::test_every_stop_value_has_a_row` (each value in `enter.STOPS` appears in
  the section's table),
  `::test_skill_names_enter_as_the_first_build_call` green; every existing
  prose test green; `bash dev/bin/release-checks` green; `CHANGELOG.md`
  `[Unreleased]` carries under `### Added` a `**run-autopilot**` line for
  `autopilot enter`.

**Exit Criteria**: `release-checks` green.

## Test Strategy

### Critical Scenarios
- **Happy path**: a resumed batch with 00216 in `wip/`, tasks present, fresh
  cache, design doc with a review-log line → `{"stop": null, "prd":
  "00216-...", "source": "wip", "catchup": "delta", "design": "reuse", ...}`,
  one `resume` row written, no file moved.
- **Edge case**: a backlog pick whose eligibility command fails → skipped and
  recorded, the next backlog PRD picked; a `force` catchup on a PRD with
  tasks → reads as `run` (00209) and so can be `delta`.
- **Error case**: `park-requested` for a PRD whose move to `hold/` fails →
  `stop: "mv_verify"`, nothing after step 3 runs, state untouched beyond what
  the park executor already did.

## Risks

- **The verb drifts from the prose it replaces**: each step imports the same
  function the single-step verb uses, and `test_resume_target_matches_the_resume_target_verb`
  plus the STOPS table test keep the two in step; the old sections stay as
  the reference, so a reader can still follow any stop by hand.
- **A stop value the skill does not know**: the prose test fails release
  checks when `STOPS` grows without a table row.
- **Savings smaller than hoped**: most of session 1's 8 minutes was reading
  the brief and forensics, not these calls; the post-release signal (first
  `autopilot:work` within 3 min) says whether it paid off, and the rest of
  O3 (orchestrator effort) is a separate experiment.
