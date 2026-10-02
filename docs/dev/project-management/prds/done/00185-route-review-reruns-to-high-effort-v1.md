---
catchup: skip
design: skip
default_model: sonnet
model_tier_rationale: one branch in routing.route with the exact rule given, one field added to a metrics row, additive tests
---

# Route review reruns to high effort

## Overview

### Problem Statement
`cli/routing.py:216` routes every review session to `claude-opus-5[1m]` at effort `xhigh` with no awareness of `state.cycle`. The review subagents are not the cost: Alice and Blake pin `model: sonnet`, Eve pins fable, Bob is codex. The orchestrator session itself is. In the week to 2026-09-05 review phases were 57 to 76 percent of loop spend; the 00161 cycle-2 review session alone cost $144.03 over 8,887 s, and batch 202609050909 spent $79 of $134 on four review sessions. Five of six agent-skills PRDs converged in cycle 1, so cycle 2 and later is where the opus thinking budget is spent with the least return. Nothing in `loop-metrics.jsonl` records the effort a session ran at, so the effect of any change cannot be measured from the ledger.

### Target Users
The operator paying the review bill; the loop, which keeps opus for judgment work on every cycle and only trims the thinking budget on reruns.

### Success Metrics
- `uv run --no-project --with pytest python -m pytest -q skills/run-autopilot/cli/test_routing.py -k review` passes with the four new tests named below.
- The next batch's `dev/local/autopilot/ledger/loop-metrics.jsonl` rows for review sessions carry an `effort` field, and every row whose PRD was at `cycle >= 2` when launched reads `"effort":"high"` (checked by the operator with `jq -c 'select(.phase_launched=="review") | {prd, model, effort, cost_usd}'`).

## Functional Decomposition

### Capability: Cycle-aware review effort
The review session keeps its model and drops one effort step on reruns.

#### Feature: Cycle read
- **Description**: `review_cycle(autopilot_dir) -> int` in `cli/routing.py`.
- **Inputs**: `autopilot_dir / "state.json"`.
- **Outputs**: `state["cycle"]` when it is an int, else `1`.
- **Behavior**: never raises and never writes, like `build_model`; a missing, unreadable or malformed state file is a fresh batch and reads as cycle 1.

#### Feature: Rerun effort
- **Description**: the `review` branch of `route()` picks effort by cycle.
- **Inputs**: `phase == "review"`, the cycle, `env`.
- **Outputs**: `Route(model=env.get("_AUTOPILOT_MODEL_REVIEW") or OPUS, effort=E, cap_secs=...)` where `E = env["_AUTOPILOT_EFFORT_REVIEW"]` when set (the explicit override wins on every cycle), else `"xhigh"` when the cycle is 1 or lower, else `env.get("_AUTOPILOT_EFFORT_REVIEW_RERUN") or "high"`.
- **Behavior**: the model never changes with the cycle; `cap_secs` is unchanged. The loop banner already prints `plan.model/plan.effort` (`cli/loop.py:1181` and `:1245`), so a rerun shows `claude-opus-5[1m]/high` to the operator with no new output.

### Capability: Effort in the session ledger
Every loop-metrics row says what effort the session ran at.

#### Feature: Effort field
- **Description**: `_append_metrics` (`cli/loop.py:880`) takes `effort: str` and writes `"effort": effort` after `"model"` in the row.
- **Inputs**: `plan.effort` from both call sites (`cli/loop.py:1189` and the loop-mode call near `:1241`).
- **Outputs**: the row `{..., "model": M, "effort": E, "cost_usd": ..., "tokens_out": ...}` in `loop-metrics.jsonl` and its `ledger/` mirror.
- **Behavior**: additive; `render_report._batch_rows` and the Loop Metrics table ignore the key, so the table and its golden do not change.

## Structural Decomposition

### Repository Structure

```
skills/run-autopilot/cli/
├── routing.py                # Maps to: Cycle read, Rerun effort
├── loop.py                   # Maps to: Effort field (row writer and its two call sites)
├── test_routing.py           # Maps to: the four review routing tests
└── <loop metrics test module> # Maps to: test_metrics_row_carries_effort (module found by rg, see Phase 1)
skills/run-autopilot/
└── SKILL.md                  # Maps to: § Execution Model sentence on rerun effort
CHANGELOG.md
```

### Module: routing
- **Maps to capability**: Cycle-aware review effort
- **Responsibility**: model, effort and cap for the next spawn, from state and env only
- **Exports**:
  - `review_cycle(autopilot_dir)` - the cycle the next review session resumes
  - `route(phase, autopilot_dir, env)` - unchanged signature

### Module: loop
- **Maps to capability**: Effort in the session ledger
- **Responsibility**: the loop-metrics row writer
- **Exports**:
  - `_append_metrics(..., model, effort)` - one more field

## Dependency Graph

### Foundation Layer (Phase 0)
No dependencies - built first.

- **routing.review_cycle, routing.route**: the rule.

### Core Layer (Phase 1)
- **loop._append_metrics**: Depends on [routing] only through `plan.effort`, which already exists.

### Integration Layer (Phase 2)
- **docs**: Depends on [routing, loop].

## Implementation Phases

### Phase 0: Foundation
**Goal**: reruns route to high effort, tested against a fixture state.

**Tasks**:
- [ ] Add `review_cycle` and the cycle-aware effort to `cli/routing.py` (no deps) - Acceptance: `test_review_rerun_drops_effort_to_high` (state.json with `cycle: 2` → `Route.effort == "high"`, `Route.model == OPUS`), `test_review_first_cycle_keeps_xhigh` (`cycle: 1`), `test_review_effort_override_wins_on_reruns` (`_AUTOPILOT_EFFORT_REVIEW=xhigh`, `cycle: 3` → `xhigh`), and `test_review_missing_state_keeps_xhigh` (no state.json) pass in `cli/test_routing.py`; every existing test in that module still passes.

**Exit Criteria**: `python -m pytest -q skills/run-autopilot/cli/test_routing.py` passes.

### Phase 1: Core
**Goal**: the ledger records the effort.

**Tasks**:
- [ ] Add the `effort` parameter and row field to `_append_metrics` and pass `plan.effort` at both call sites (depends on: Phase 0) - Acceptance: `test_metrics_row_carries_effort` passes in the module `rg -l '_append_metrics' skills/run-autopilot/cli --glob 'test_*'` names (add it there; if the search names nothing, add the test to `cli/test_routing.py` and say so in the task's commit body); `rg -n '_append_metrics\(' skills/run-autopilot/cli/loop.py` shows every call passing `plan.effort`; `cli/golden/expected/report-section.md` is byte-identical before and after.

**Exit Criteria**: `python -m pytest -q skills/run-autopilot/cli` passes.

### Phase 2: Integration
**Goal**: the rule is written where the phase routing is described.

**Tasks**:
- [ ] Add one sentence to `skills/run-autopilot/SKILL.md` § Execution Model: `Review sessions run on opus at xhigh in cycle 1 and at high on cycle 2 and later; _AUTOPILOT_EFFORT_REVIEW forces one effort for every cycle and _AUTOPILOT_EFFORT_REVIEW_RERUN sets the rerun value.` and a `### Changed` CHANGELOG entry under `[Unreleased]` (depends on: Phase 1) - Acceptance: `rg -n 'cycle 2 and later' skills/run-autopilot/SKILL.md` returns one hit; `rg -n '_AUTOPILOT_EFFORT_REVIEW_RERUN' CHANGELOG.md skills/run-autopilot/SKILL.md` returns one hit in each.

**Exit Criteria**: `bash dev/bin/release-checks` passes.

## Test Strategy

### Critical Scenarios
- **Happy path**: cycle 2 review → opus at high; the banner reads `claude-opus-5[1m]/high`; the metrics row carries `"effort":"high"`.
- **Edge case**: `_AUTOPILOT_EFFORT_REVIEW` set → that effort on every cycle, rerun override ignored.
- **Error case**: state.json unreadable → cycle 1 behavior (xhigh), nothing raised, nothing written.

## Risks
- **Weaker consolidation on reruns**: the decision gate runs with a smaller thinking budget on exactly the PRDs that did not converge in cycle 1; the model stays opus, and `_AUTOPILOT_EFFORT_REVIEW=xhigh` restores today's behavior for one batch without a code change.
- **Unmeasured saving**: no ledger row today separates thinking from context cost; the `effort` field is what makes the next batch comparable to this week's rows.

## Open Questions

- Do the delta-aware reruns from PRD 00165 shrink the cycle-2 review input at all? The 00161 cycle-2 review diff was 83 KB against 85 KB in cycle 1 (2026-09-05 audit, finding A4). Check on the first batch that carries the `effort` field: if cycle-2 diffs stay near cycle-1 size, effort is the only rerun lever and 00165 needs its own look.
