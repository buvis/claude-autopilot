---
catchup: run
design: skip
default_model: sonnet
model_tier_rationale: prose reorder with the exact sentences given; every edit is pinned by a named prose test and no code changes
---

# Commit subagent output before a rotation can lose it

Source: `dev/local/notes/autoclaude-inefficiencies-2026-09-13.md` finding 5,
split out of PRD 00196 at the 2026-09-13 backlog review. Lands after 00196
and 00200 (the rotation envelope this PRD extends is the one they
parameterise).

## Problem

A rotation resets the in-flight task to `pending` and its envelope says
"commit any safe partial work", but on 2026-09-08 (agent-skills, task 10) the
tripwire fired while Devon was running and the session ended with Tess's
603-line test file uncommitted; on 2026-09-13 (task 13) it fired after the
tests were committed and the next session re-dispatched Tess anyway with the
identical prompt, 33 minutes of duplicated work. Step 2.85 (Devon) runs
before step 2.9 (commit tests) in `skills/work/SKILL.md` (:244, :258), so the
quality-gated tests sit uncommitted through the longest dispatches of a task.

## Solution

Commit Tess's tests as soon as they pass the 2.8 quality gate, before Devon;
commit the strengthened tests again after a strengthen round; have the
rotation envelope name a `chore(<scope>): wip - rotated mid-task` commit for
every dirty allowlisted file; and let step 2 of the next session resume from
that commit's body instead of re-dispatching Tess.

## Requirements

### Must have
- `skills/work/SKILL.md` renumbers the steps: 2.8 quality gate, 2.85 commit
  tests (today's 2.9 text, unchanged), 2.9 adversarial validation (today's
  2.85 text), 2.95 red-check. After a strengthen round the sentence `Commit
  the strengthened tests as test(<scope>): strengthen <feature> before the
  second Devon dispatch.` follows the round. `<test_commit_sha>` (today
  :269) is the last test commit. Every cross-reference to "step 2.85" and
  "step 2.9" elsewhere in `skills/work/` and `skills/run-autopilot/` is
  updated in the same commit (`rg -n "2\.85|2\.9\b" skills/work skills/run-autopilot`
  lists them).
- `_rotation_instructions` in `skills/run-autopilot/scripts/autopilot_context_cap_hook.py`
  gains the sentence `Before stopping, commit every dirty file named in this
  task's Tess or Ivan allowlist as chore(<scope>): wip - rotated mid-task,
  with the body naming the step reached (tess, devon or ivan).` `chore` is
  an accepted type in aegis `validate_commit_msg.py:21`; `wip` is not, hence
  the subject form.
- Work SKILL.md step 2 gains: `Read git log -1 --format=%s. When the subject
  ends in "wip - rotated mid-task" for this task, read the commit body and
  continue at the step it names instead of dispatching Tess.`
- `references/design-rationale.md` gains one line: a `wip - rotated mid-task`
  subject is a rotation scar, not a release note; `chore` needs no CHANGELOG
  entry.
- Prose tests in `skills/work/scripts/test_step_order_prose.py`:
  `test_tests_commit_before_devon` (the `git commit -m "test(` block sits
  above the Devon heading), `test_strengthened_tests_are_committed_before_devon_round_two`,
  `test_step_2_resumes_from_a_wip_commit`; and in
  `skills/run-autopilot/scripts/test_autopilot_context_cap_hook.py`
  `test_rotation_text_names_the_wip_commit`.

### Nice to have
- The step-2 resume sentence also covers `test(` subjects for this task with
  no wip commit (tests committed, rotation before Devon): continue at Devon.

## Implementation

### Module: work SKILL step order
- **Location**: `skills/work/SKILL.md`, `skills/work/references/adversarial-test-prompt.md`
- **Responsibility**: the order 2.8 -> 2.85 commit -> 2.9 Devon -> 2.95 red-check
- **Exports**: none (prose)

### Module: rotation envelope
- **Location**: `skills/run-autopilot/scripts/autopilot_context_cap_hook.py`
- **Responsibility**: the wip-commit sentence in `_rotation_instructions`
- **Exports**: `_rotation_instructions()` (text change only)

### Dependencies
- work SKILL step order: No dependencies (foundation)
- rotation envelope: No dependencies (foundation)

## Tasks

### Phase 0: Foundation
- [ ] Reorder steps 2.85/2.9, add the strengthen-commit sentence, update
  cross-references - `test_step_order_prose.py::test_tests_commit_before_devon`
  and `::test_strengthened_tests_are_committed_before_devon_round_two` pass;
  `test_adversarial_cap_prose.py` and `test_style_gate_prose.py` still green;
  `rg -n "step 2\.85" skills/work/references/adversarial-test-prompt.md`
  names Devon.

### Phase 1: Core
- [ ] Rotation envelope names the wip commit; step 2 resumes from it (depends
  on: Phase 0) - `test_rotation_text_names_the_wip_commit` and
  `test_step_order_prose.py::test_step_2_resumes_from_a_wip_commit` pass;
  `test_rotation_text_still_describes_rotation_and_stop` still green.
- [ ] design-rationale line and CHANGELOG `### Changed` under `**work**`
  (depends on: Phase 1) - `rg -c "rotated mid-task" skills/run-autopilot/references/design-rationale.md CHANGELOG.md`
  returns 1 for each.

## Success Criteria

- `uv run --no-project --with pytest python -m pytest -q skills/work/scripts skills/run-autopilot/scripts/test_autopilot_context_cap_hook.py`
  green with the four named tests present.
- Post-release signal, not judged in-session: the next batch's `git log`
  shows no `test(` commit for a task followed by a second `test(` commit
  with the same subject from a later session.

## Lane scope note (lane L2, 2026-09-20)

The branch's first four commits (02ee72c, f001bd1, 57de72b, 4cf18b9) belong to
PRD 00197, reviewed separately on this branch and converged at review 2; this
PRD's work starts at 526597b. This branch (`lane/work-skill`) owns `skills/work/**` only. The three
run-autopilot pieces of this PRD - the `_rotation_instructions` wip-commit
sentence in `skills/run-autopilot/scripts/autopilot_context_cap_hook.py`, its
test `test_rotation_text_names_the_wip_commit`, and the
`skills/run-autopilot/references/design-rationale.md` line - are handed to the
integrator as `Integrator:` paragraphs in commit eed322d's message with the
exact text, not implemented here. `skills/run-autopilot/scripts/test_fablectl.py`
pins the Devon table under the old `### 2.85.` heading; its three one-token
edits are in commit 526597b's `Integrator:` paragraph (verified green on a
probe copy) and `test_devon_is_dispatched_for_a_fable_task` is red on this
branch until they land. Two tests were already red on the base commit b6bdc12
and are untouched: `test_dispatch_telemetry_prose.py::test_step_6_5_writes_the_leave_row_before_the_stop`
and `test_verify_queue_prose.py::test_zero_tasks_is_delivered_where_tasks_are_actually_created`.

## Hand-landed findings

Two loop-blocker fixes from `dev/local/notes/autoclaude-inefficiencies-2026-09-13.md`
landed on this branch beside the PRD, one commit each, to be reviewed with it.

### Finding 15 - commit 0ad4e9f `fix(work): dispatch Pat's per-task review as a foreground Bash call, never backgrounded`

A build session launched Pat's `sonnet-run.sh` as a `run_in_background` Bash
call and ended its turn "waiting"; headless mode does not keep a session alive
for a pending background Bash, so the harness wrote `[killed]` into the output
file, Pat's dispatch row read `lost`, and the wrapper relaunched a session that
re-ran him (2026-09-14, 00191 T1 and agent-skills 00052 T2). Fix:
`skills/work/references/per-task-review.md` § Dispatch gains a paragraph:
foreground Bash call bounded by the Bash tool's `timeout` (600000 ms, the tool's
maximum; the parked hand patch said 900000 ms, above the cap), never
`run_in_background`; if a run was backgrounded anyway the next call is
`Monitor` on its output file, never a bare end of turn. Pinned by
`skills/work/scripts/test_loop_blockers_prose.py::test_pat_dispatch_is_foreground_never_backgrounded`
(failed once against the old prose). CHANGELOG `### Fixed` line under `**work**`.

### Finding 16 - commit a7213b5 `feat(work): skip Devon on a task whose tests are all prose pins`

Four prose tasks (skill markdown edits pinned by substring tests) ran the full
Tess -> Devon -> Tess -> Devon chain and every round ended "exhausted, flagged"
on the same ceiling, that a substring pin cannot see negation, inversion or
past-tense narration: about 55 minutes of Opus time bought zero kept
strengthenings. Fix: `skills/work/SKILL.md` step 2.9 (Devon) gains the prose
gate paragraph: when every test file Tess created or changed for the task has a
basename ending in `_prose.py`, skip Devon, record `devon: skipped:prose` in the
attempt entry and proceed to step 2.95. Pinned by
`test_loop_blockers_prose.py::test_devon_skips_prose_pin_tasks`. CHANGELOG
`### Changed` line under `**work**`.

### Deferred

- [Medium] `test_pat_dispatch_is_foreground_never_backgrounded` passes against the pre-rework base (review 2, mech-check) - dismissed: the `600000` needle strengthens a pin on prose that was already right; it guards a future edit, not this diff
- [Low] commit 0ebe44b's body says "three new needles failed once" while four tests were touched (review 2, Bob) - accepted as written; the fourth (600000) needle is the dismissed row above
- [Medium] the six `step 2.85` hits in `skills/run-autopilot/scripts/test_fablectl.py`'s PRD 00119 comment block (lines 657-709, 1844) are dated narrative (review 1 finding 3, option A) - left for the integrator's own judgement; the live line `references/design-rationale.md:139` is in commit 0ebe44b's `Integrator:` paragraph
- [Medium] `devon` attempt field documented as `"skipped:prose" | null` only (review 1 finding 6, option B) - tier skips stay unstamped, as the note asked; widen to `skipped:tier` in a later PRD if a batch report needs it
