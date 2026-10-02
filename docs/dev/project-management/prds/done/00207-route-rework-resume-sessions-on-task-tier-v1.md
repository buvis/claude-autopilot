---
catchup: skip
design: skip
default_model: sonnet
model_tier_rationale: one routing branch with an exact rule, a state fixture per case, and a docstring/prose update; no design call
rework_cap: 2
---

# Route rework-resume sessions on the rework tasks' tier

Source: `dev/local/notes/validation-batch-054-2026-09-20.md` finding V6 (2026-09-21).
Grounded at `b78bc11` (0.5.4). Lands with 00208 (hand off after the rework design),
which produces the sessions this PRD routes; independent of 00209-00211.

## Overview

### Problem Statement

`cli/routing.route` sends every `review` launch to Opus (xhigh on cycle 1, high
after). In the 0.5.4 validation batch review sessions were 10 of 22 sessions and
$364 of $492 (74%). Five of those ten were rework-resume sessions: Phases 4 and 5
had already run (the cycle's review file was on disk), `state.rework_task_ids`
named the tasks left, and the orchestrator's only work was dispatching
`/autopilot:work` for sonnet-tier fixes (00052 sessions 4 and 5: `[D1]` tasks 5
and 6, both `model: sonnet`, $20 and $38 on an Opus orchestrator; 00052 session
7: the `[D2]` tail sweep, sonnet, $10). The orchestrator copies prompts and reads
attempt rows in those sessions; nothing in them needs Opus judgment. The cycle's
lenses are subagents and CLIs whose models this route never touches.

### Target Users

The loop operator paying per session; the review-rework loop under
`_AUTOPILOT_LOOP`.

### Success Metrics

- `uv run --no-project --with pytest python -m pytest -q skills/run-autopilot/cli/test_routing.py`
  green with the four new cases below present.
- `bash dev/bin/release-checks` green.
- Post-release signal: in `loop-metrics.jsonl`, a `review` row that follows a
  `review` row for the same PRD and cycle carries `model: claude-sonnet-5[1m]`
  unless a rework task carries `model: opus`.

## Functional Decomposition

### Capability: Rework-resume routing

#### Feature: Detect a rework-resume launch
- **Description**: a `review` launch is a rework resume when Phases 4-5 are
  already done for the current cycle and rework is queued.
- **Inputs**: `state.json` (`prd`, `cycle`, `rework_task_ids`, `tasks[]`),
  `dev/local/reviews/<prd-stem>-review-<cycle>.md` (the cycle's review file,
  the same pattern `references/phase-review.md` § Phase 4 skips on).
- **Outputs**: a boolean, `rework_resume(autopilot_dir) -> bool`, in
  `cli/routing.py`.
- **Behavior**: true iff `state.rework_task_ids` is a non-empty list, at least
  one listed id names a task in `state.tasks` whose `status` is not
  `completed`, and the review file for `state.cycle` exists (either the
  `-review-<n>.md` or `-review-0<n>.md` spelling `cli/gate.py` accepts).
  Missing or malformed state, a missing review file, or an empty list → false
  (the launch is a fresh review: Opus as today).

#### Feature: Route on the queued tasks' tier
- **Description**: a rework-resume launch takes the highest tier among the
  unfinished rework tasks.
- **Inputs**: the `model` of each unfinished task in `state.rework_task_ids`.
- **Outputs**: `Route.model` = `OPUS` when any such task carries `model: opus`
  (or `fable`, the rescue rung), else `SONNET`; `Route.effort` unchanged (the
  cycle rule and the two env overrides apply as today); `Route.cap_secs`
  unchanged. `_AUTOPILOT_MODEL_REVIEW` still overrides everything.
- **Behavior**: a task with no `model` key counts as sonnet (the legacy default
  `/autopilot:work` already uses). The decision is recomputed on every launch
  from state, no latch (PRD 00111's decay rule). One stderr line names the
  route: `review: rework resume, <n> task(s) left, routing <model>`.

## Structural Decomposition

### Repository Structure

```
skills/run-autopilot/
├── cli/routing.py            # Maps to: both features (rework_resume, route)
├── cli/test_routing.py       # Maps to: Test Strategy
├── references/model-ladder.md  # Maps to: the review-session row of the ladder
└── SKILL.md                  # Maps to: Execution Model paragraph (one sentence)
```

### Module: routing
- **Maps to capability**: Rework-resume routing
- **Responsibility**: decide the review launch model from state and the review
  file, never write.
- **Exports**: `rework_resume`, the changed `route`.

## Dependency Graph

### Foundation Layer (Phase 0)
- **routing**: no dependencies.

### Integration Layer (Phase 1)
- **docs**: depends on [routing].

## Implementation Phases

### Phase 0: Routing
**Goal**: rework-resume launches route on task tier.

**Tasks**:
- [ ] Add `rework_resume` and the tier rule to `cli/routing.route` (no deps) -
  Acceptance: `test_routing.py` gains `test_rework_resume_with_sonnet_tasks_routes_sonnet`,
  `test_rework_resume_with_one_opus_task_routes_opus`,
  `test_fresh_review_without_review_file_routes_opus`,
  `test_rework_resume_with_all_tasks_completed_routes_opus` (a stale list is a
  fresh review), each building `state.json` and the review file in `tmp_path`;
  the sonnet case is watched red against the pre-change code; the existing
  cycle-effort and env-override tests stay green.

### Phase 1: Docs
**Goal**: the ladder and the core skill say what the route does.

**Tasks**:
- [ ] Update `references/model-ladder.md`'s review-session row and the
  `SKILL.md` Execution Model sentence ("Review sessions run on opus ...") to
  name the rework-resume rule (depends on: Phase 0) - Acceptance:
  `test_routing.py::test_docs_name_the_rework_resume_rule` pins the phrase
  `rework resume` in both files; CHANGELOG `### Changed` entry under
  `**run-autopilot**`.

**Exit Criteria**: suites green; release-checks green.

## Test Strategy

### Critical Scenarios
- **Happy path**: review file for cycle 1 exists, `rework_task_ids: ["5","6"]`,
  both tasks sonnet and pending → `SONNET`, effort xhigh on cycle 1.
- **Edge case**: one of the queued tasks is `opus` → `OPUS`; a queued task with
  no `model` key → sonnet; ids naming no task → ignored.
- **Error case**: `state.json` unreadable, or the review file absent → the
  fresh-review route (`OPUS`), no exception.

## Risks

- **A sonnet orchestrator drops a lens or a step on rework**: the rework
  session runs `/autopilot:work` only; the lenses ran in Phase 4 on Opus and
  run again on the next cycle's fresh review session, which this PRD leaves on
  Opus. Accepted.
- **Cycle-2 fresh reviews still cost Opus**: out of scope; the rerun effort
  rule (00185) already lowers them to high.

### Deferred

Review 1 (2026-09-21, 14 findings, 0 CRITICAL / 1 HIGH / 12 MEDIUM / 1 info). HIGH fixed
and re-reviewed: `rework_resume` returns the bool the PRD promised (`_rework_tasks`
holds the list, the tier rule is inlined into `_review_model`). Mediums taken: stale
module docstring, fable named in the core sentence, docs pin without an `or` hedge,
rework tests moved to `test_routing_rework.py`, the redundant `review_cycle` re-read
replaced by the loaded state's `cycle`.

- [Medium] `test_routing.py` was 802 lines before this PRD and stays over the 800-line ceiling (803) after the split; a further split is pre-existing debt (Alice, Bob)
- [Medium] four rework tests pass against the pre-change code (opus, missing file, completed list, override all routed Opus before too) - the sonnet case is the fail-first pin (Bob, Carl, mech-check)
- [Medium] a missing or non-int `cycle` reads as 1 (as `review_cycle` does) and ids are compared as strings; a malformed state can therefore classify as a resume when a `-review-1.md` exists - by design, the same reading the Phase 4 skip makes (Bob)
- [Medium] tests omit the fable tier, the zero-padded review filename and the exact stderr line (Bob)
- [Info] Bob's VERIFY: `test_routing.py` and `test_routing_rework.py` green at HEAD (answered)

Review 2 (2026-09-21, 7 findings, 0 CRITICAL / 0 HIGH, converged). Taken after the cap:
`rework_resume` is now called directly (`test_rework_resume_is_a_bool_true_only_on_a_resume`),
the fable-tier and zero-padded-filename cases are pinned with the stderr line, the docs
pin has no `or` hedge.
- [Medium] `test_routing.py` stays at 803 lines (802 before this PRD); pre-existing debt, a further split is its own task (Alice, Bob)
- [Medium] a missing or non-int `cycle` reads as 1, the same reading `review_cycle` and the Phase 4 skip make; a stale `-review-1.md` beside pending ids therefore classifies as a resume - documented in `_rework_tasks`'s docstring (Bob)
- [Medium] the PRD's success metric and acceptance name `test_routing.py`; the cases live in `test_routing_rework.py` since the split (traceability only) (Blake)
- [Medium] several rework tests pass against the pre-change code because those cases routed Opus before too; the sonnet case is the fail-first pin (Alice, Bob, mech-check)

