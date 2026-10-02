---
catchup: skip
design: skip
default_model: sonnet
model_tier_rationale: two small Python hooks with an exact stdin contract, fixture-driven tests in both directions, and a hooks.json registration; no design call
rework_cap: 2
---

# Deny autopilot skill invocations after the session's leave row

Source: `dev/local/notes/validation-batch-054-2026-09-20.md` finding V3
(2026-09-20). Grounded at `b78bc11` (0.5.4). Independent of 00207-00210.

## Overview

### Problem Statement

The Session handoff procedure ends with "print the banner and end the turn"; the
core `SKILL.md` Execution Model says "run all phases in sequence without
stopping ... completing a sub-skill invocation is NOT a stopping point". On
agent-skills 00052 the sonnet build session wrote its contract card, brief and
`leave` row, printed the banner, and in the SAME assistant message called
`Skill autopilot:run-autopilot` again: the whole review cycle then ran inside
the build session (503K context, the cap hook unguarded in `review` with no
rework queued, no Watcher for the CLI reviewers, one 75-minute $27 session,
the rework design done twice). Prose alone did not hold under a sonnet
orchestrator; the boundary needs a mechanical guard, the way the cap hook and
the push guard already are.

### Target Users

Headless loop sessions (`_AUTOPILOT_LOOP` set). Interactive sessions are
untouched.

### Success Metrics

- `uv run --no-project --with pytest python -m pytest -q hooks/test_guard_skill_after_leave.py hooks/test_hook_registration.py`
  green.
- `bash dev/bin/release-checks` green (the new test joins the
  `[checks] hook registration` block).
- Post-release signal: no `loop-metrics.jsonl` row whose session wrote both a
  `leave` row and a later `resume` row (same session id in the two
  `dispatch-metrics.jsonl` rows' surrounding session log).

## Functional Decomposition

### Capability: Post-hand-off guard

#### Feature: Record the leave row's session
- **Description**: a PostToolUse hook on `Bash` notes which session wrote its
  `leave` row.
- **Inputs**: hook stdin JSON (`session_id`, `tool_name`, `tool_input.command`,
  `tool_response`); `_AUTOPILOT_LOOP`.
- **Outputs**: `dev/local/autopilot/.session-left` holding one JSON line
  `{"session": "<session_id>", "at": "<ISO UTC>"}`, overwritten on each write.
- **Behavior**: fires only when `_AUTOPILOT_LOOP` is set, the tool is `Bash`,
  the command contains both `record_dispatch.py handoff` and `--edge leave`,
  and the tool did not error (`tool_response` carries no `is_error: true` or
  non-zero exit). Located via `_walk_up.find_autopilot_dir` like the cap hook;
  a missing dir is a silent no-op; every failure is a silent exit 0 (the hook
  must never block the hand-off it observes).

#### Feature: Deny skill invocations after it
- **Description**: a PreToolUse hook on `Skill` denies an autopilot skill call
  from a session that already left.
- **Inputs**: hook stdin JSON (`session_id`, `tool_name`, `tool_input.skill`);
  `.session-left`; `_AUTOPILOT_LOOP`.
- **Outputs**: exit 2 with the stderr reason
  `autopilot: this session wrote its leave row at <at>; the hand-off ended it.
  End the turn now - do not invoke <skill>. The loop relaunches the next phase
  from state.json.` when denying; exit 0 otherwise.
- **Behavior**: denies iff `_AUTOPILOT_LOOP` is set, the marker exists, its
  `session` equals the hook's `session_id`, and the requested skill starts
  with `autopilot:` or equals `git-ferry:catchup`. A marker from another
  session (a stale file) never denies. Any other skill passes. Malformed
  marker → pass (fail open: the guard is a backstop, the prose still says
  STOP).

#### Feature: Registration
- **Description**: both hooks are registered in `hooks/hooks.json`; the
  PreToolUse entry uses matcher `Skill`.
- **Inputs**: `hooks/hooks.json`, `hooks/test_hook_registration.py` (which pins
  the matcher/command table).
- **Outputs**: two new entries; the registration test's expected table grows.
- **Behavior**: `${CLAUDE_PLUGIN_ROOT}/hooks/note_session_leave.py`
  (PostToolUse, matcher `Bash`) and
  `${CLAUDE_PLUGIN_ROOT}/hooks/guard_skill_after_leave.py` (PreToolUse,
  matcher `Skill`), timeout 5 each.

## Structural Decomposition

### Repository Structure

```
hooks/
├── note_session_leave.py          # Maps to: Record the leave row's session
├── guard_skill_after_leave.py     # Maps to: Deny skill invocations after it
├── test_guard_skill_after_leave.py  # Maps to: Test Strategy (both hooks)
├── hooks.json                     # Maps to: Registration
└── test_hook_registration.py      # Maps to: Registration pin
skills/run-autopilot/
├── SKILL.md                       # Maps to: § Session handoff procedure (one sentence naming the guard) and § Retention (the marker is disposable)
└── references/design-rationale.md # Maps to: why a hook, not prose (one section)
```

### Module: leave-guard hooks
- **Maps to capability**: Post-hand-off guard
- **Responsibility**: note the leave, deny the re-entry, never block anything
  else.
- **Exports**: the two hook scripts.

## Dependency Graph

### Foundation Layer (Phase 0)
- **leave-guard hooks**: no dependencies (they import `_walk_up` by path the
  way `review_coverage_hook.py` does).

### Integration Layer (Phase 1)
- **registration + docs**: depends on [leave-guard hooks].

## Implementation Phases

### Phase 0: Hooks
**Goal**: the two scripts behave per the features.

**Tasks**:
- [ ] Add `hooks/note_session_leave.py` and `hooks/guard_skill_after_leave.py`
  with `hooks/test_guard_skill_after_leave.py` (no deps) - Acceptance: tests
  run each script as a subprocess with stdin JSON and a `tmp_path` autopilot
  dir: `test_leave_row_marks_the_session` (marker written with the id),
  `test_leave_row_outside_loop_writes_nothing`,
  `test_failed_leave_row_writes_nothing`,
  `test_autopilot_skill_after_leave_is_denied_with_the_reason` (exit 2, stderr
  names the skill), `test_other_session_marker_never_denies`,
  `test_non_autopilot_skill_passes`, `test_malformed_marker_passes`,
  `test_guard_outside_loop_passes`; the deny test is watched red against the
  pre-change tree (no script → the harness would not deny).

### Phase 1: Registration and docs
**Goal**: the hooks are live and explained.

**Tasks**:
- [ ] Register both hooks in `hooks/hooks.json`, extend
  `test_hook_registration.py`, add the sentence to § Session handoff procedure
  step 2 ("a `Skill` call to any `autopilot:*` skill after this row is denied
  by `hooks/guard_skill_after_leave.py`"), list `.session-left` under
  § Retention's disposable set, add the design-rationale section (depends on:
  Phase 0) - Acceptance: `test_hook_registration.py` green with the two new
  rows; `cli/test_loop_prose.py::test_every_handoff_site_writes_the_brief`
  stays green; a new `cli/test_loop_prose.py::test_handoff_names_the_skill_guard`
  pins `guard_skill_after_leave.py` in the procedure; CHANGELOG `### Added`
  entry under `**hooks**`.

**Exit Criteria**: suites green; release-checks green.

## Test Strategy

### Critical Scenarios
- **Happy path**: loop session writes its leave row, then calls
  `Skill autopilot:run-autopilot` → denied with the reason; the turn ends.
- **Edge case**: the next session (new id) finds the marker → its Phase 0
  `Skill` calls pass; an interactive session with a marker present → pass.
- **Error case**: marker holds garbage → pass; autopilot dir missing → pass.

## Risks

- **A legitimate post-leave skill call exists somewhere**: none found; every
  hand-off site ends with the banner and END TURN, and the row is the last
  write (PRD 00199). If one appears, the deny reason names the file to fix.
- **Hook cost**: one file stat per `Skill` call and one regex per Bash call;
  negligible.

### Deferred

Review 1, first attempt (2026-09-21): the session dispatched no Watcher, ended its turn
while Bob and Carl ran in the background, and wrote no review file (finding V8 in the
validation notes). Blake reported before the death: one HIGH, the PRD names
`hooks/test_hook_registration.py` and its literal acceptance command failed; fixed by
adding that file as the runnable pin beside the pack-wide table (which keeps its two
rows) and listing it in the `[checks] hook registration` block. Review 1 re-run after
the fix; its findings are appended below.

Review 1 (2026-09-21, 8 findings, 0 CRITICAL / 1 HIGH refuted / 6 MEDIUM / 1 LOW closed).
The HIGH (`tool_failed` reads no exit code) is refuted by the event contract: a non-zero
Bash exit fires `PostToolUseFailure`, never this PostToolUse hook; `tool_failed`'s
docstring now says so. Fixed in commit 303aaca: the catchup deny test asserts the reason
text (M2), the existence test is restricted to the two new hooks (M3), both hooks get a
no-autopilot-dir test (M6), the timeout pin requires the key (M7). 0 open C/H: converged
without a second cycle.

- [Medium] `test_hooks_json_is_valid` in the pack-wide table only parses `hooks.json`
  (pre-existing, not this PRD's diff): deferred to the next PRD touching that file.
- [Medium] a same-session marker without `at` denies (unreachable: the only writer
  always sets `at`; denying after a leave row is the intended direction): accepted.

