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
