---
catchup: skip
design: run
default_model: opus
model_tier_rationale: an invented predicate on Agent calls that must block one delegation shape while passing every real dispatch; 16 legitimate dispatch prompts already mention the guarded skill names, so the obvious substring rule is wrong
---

# Keep phase skills in the session

Source: `docs/dev/project-management/notes/batch-0.7.0-reflection-2026-10-03.md`
B1 and B3.

## Overview

### Problem Statement

**B1.** On 2026-10-03 the build session for 00242 (sonnet, medium effort)
did not run `/autopilot:work` itself:

- It wrote "I'll delegate the entire Phase 3 work execution to an agent" and
  dispatched `Agent · Execute work phase for harden-wave-verbs PRD 00242`.
  That agent dispatched Tess as a nested subagent.
- The harness forced the nested agent to hand back mid-task, and the
  orchestrator dispatched a second "Resume" agent to continue.
- Planning and design ran in "Plan" and "Design" agents the same way.

Every contract that keeps a batch safe assumes the phase skill runs in the
session:

- the context-cap hook measures the session's context, not a subagent's;
- the task-boundary handoff can only end the session's turn;
- dispatch telemetry rows are written by the session.

`work/SKILL.md` already says "If you find yourself writing an Agent prompt
that mentions multiple tasks, STOP", but prose did not stop it. The next
session (20:17) ran `/work` correctly, so no damage this time.

**B3.** The orchestrator still calls `cat`, `head` and `grep`, which aegis
blocks. That was 27 of 41 blocks in the batch's first 5.4 active hours, each
a wasted round trip. The launch prompt's CLI sentence (`cli/runner.py`
`CLI_SUFFIX`) is the one line every session reads first, and it says
nothing about this.

### Target Users

Every unattended build and review session.

### Success Metrics

- `uv run --no-project --with pytest python -m pytest -q hooks/test_guard_phase_delegation.py skills/run-autopilot/cli/test_runner.py`
  green.
- `bash dev/bin/release-checks` green.
- Post-release signal: no `Agent ·` line in a loop log whose prompt runs a
  phase skill; aegis blocks by the orchestrator under 1 per active hour.

## Functional Decomposition

### Capability: Phase skills run in the session

#### Feature: Deny phase delegation in loop mode
- **Description**: a PreToolUse hook on the `Agent` tool refuses, in loop
  mode only, a subagent dispatch whose job is to run a phase skill.
- **Inputs**: the hook payload (`tool_input.prompt`,
  `tool_input.description`, `tool_input.subagent_type`); `_AUTOPILOT_LOOP`.
- **Outputs**: exit 2 with a one-paragraph reason naming the rule ("run
  /autopilot:work in this session; dispatch only per-task subagents"), or
  exit 0.
- **Behavior**: the design doc picks the predicate. It must satisfy:
  - **deny** the observed prompts:
    - "Execute work phase for … PRD …", told to read `work/SKILL.md` and run
      every task;
    - "Resume work phase for PRD …, task 1 onward";
    - the "Plan" agent told to run plan-tasks;
    - the "Design" agent told to run design-solution;
  - **allow** every prompt in `docs/dev/tmp/dispatch-*.txt` (about 180 real
    Tess, Ivan, Devon, deslop and review dispatches, 16 of which mention
    `autopilot:work`, `skills/work/SKILL.md` or `plan-tasks` because this
    repo edits those skills), plus the review roster's Alice, Blake and
    Watcher prompts.

  Candidate signals for the design doc to weigh, each tested against both
  sets:
  - the prompt instructs invoking or executing a phase skill (an imperative
    such as "run /autopilot:work", "execute the work phase", "follow
    work/SKILL.md for all tasks") rather than mentioning it;
  - `subagent_type` is general-purpose (per-task dispatches use the pack's
    named agents);
  - the prompt names more than one task.

  A payload the hook cannot parse passes (fail open), with one stderr line.

#### Feature: Say so in the gate prose
- **Outputs**:
  - `references/phase-build.md` Phase 2 gains: "Invoke `/autopilot:plan-tasks`
    with the Skill tool in this session; never delegate planning to an
    Agent."
  - Phase 3 gains the same sentence for `/autopilot:work`.
  - `work/SKILL.md`'s existing STOP line gains: "In loop mode a hook
    enforces this (`hooks/guard_phase_delegation.py`)."

### Capability: The launch prompt carries the shell rule

#### Feature: One more sentence in CLI_SUFFIX
- **Outputs**: `cli/runner.py` `CLI_SUFFIX` gains, after its current text:
  " Never call `cat`, `head`, `tail`, `grep` or `find` (a hook blocks them):
  use Read, `rg`, and `jq <file>`."
- **Behavior**: `prompt_for` is unchanged; the sentence rides on every
  autopilot launch prompt.

## Structural Decomposition

### Repository Structure

```
hooks/
├── guard_phase_delegation.py         # Maps to: Deny phase delegation in loop mode
├── test_guard_phase_delegation.py    # Maps to: Test Strategy (deny set, allow corpus)
└── hooks.json                        # PreToolUse matcher "Agent"
hooks/fixtures/phase_delegation/      # the four observed delegation prompts, verbatim from the 2026-10-03 log
skills/run-autopilot/cli/runner.py    # Maps to: One more sentence in CLI_SUFFIX
skills/run-autopilot/cli/test_runner.py
skills/run-autopilot/references/phase-build.md
skills/work/SKILL.md
dev/bin/release-checks
CHANGELOG.md
```

### Module: guard_phase_delegation
- **Maps to capability**: Phase skills run in the session
- **Responsibility**: one predicate, fail-open, loop mode only.
- **Exports**: `is_phase_delegation(tool_input: dict) -> bool`.

## Dependency Graph

### Foundation Layer (Phase 0)
No dependencies - built first.

- **guard predicate and fixtures**; **CLI_SUFFIX sentence**: independent.

### Core Layer (Phase 1)
- **hook registration and gate prose**: Depends on [guard predicate].

### Integration Layer (Phase 2)
- **release-checks wiring and CHANGELOG**: Depends on [Phase 1].

## Implementation Phases

### Phase 0: Foundation
**Goal**: the predicate is right on real data; the prompt carries the shell
rule.

**Tasks**:
- [ ] Write `hooks/guard_phase_delegation.py` with `is_phase_delegation` and
  the fixtures (no deps) - Acceptance:
  `test_guard_phase_delegation.py::test_the_four_observed_delegations_are_denied`,
  `::test_every_real_dispatch_prompt_is_allowed` (parametrized over
  `docs/dev/tmp/dispatch-*.txt` when present, else over a committed sample of
  20 copied into `hooks/fixtures/phase_delegation/allowed/`),
  `::test_outside_the_loop_everything_passes`,
  `::test_unparseable_payload_fails_open` green.
- [ ] Add the sentence to `CLI_SUFFIX` (no deps) - Acceptance:
  `test_runner.py::test_launch_prompt_forbids_blocked_coreutils` green (the
  rendered prompt contains "Never call `cat`, `head`, `tail`, `grep` or
  `find`").

**Exit Criteria**: both tests green.

### Phase 1: Core
**Goal**: enforced and documented.

**Tasks**:
- [ ] Register the hook under PreToolUse matcher `Agent` in `hooks/hooks.json`
  and add the three prose sentences (depends on: Phase 0) - Acceptance:
  `test_guard_phase_delegation.py::test_hooks_json_registers_the_guard_on_agent`
  and `::test_gate_prose_names_the_guard` green.

**Exit Criteria**: both green.

### Phase 2: Integration
**Goal**: shipped.

**Tasks**:
- [ ] Add `hooks/test_guard_phase_delegation.py` to `dev/bin/release-checks`
  and a `CHANGELOG.md` `[Unreleased]` `### Added` `**hooks**` line (depends
  on: Phase 1) - Acceptance: `bash dev/bin/release-checks` green.

**Exit Criteria**: `release-checks` green.

## Test Strategy

### Critical Scenarios
- **Happy path**: a loop session dispatching Ivan with a rendered dispatch
  file → allowed.
- **Edge case**: an Ivan prompt for a task that edits `skills/work/SKILL.md`
  → allowed (a mention, not a delegation).
- **Error case**: the exact "Execute work phase for … PRD 00242" prompt →
  exit 2 with the reason; outside the loop the same prompt passes.

## Risks

- **A false positive blocks real work mid-batch**: the allow corpus of about
  180 real prompts is the gate, the hook fails open on anything it cannot
  parse, and a blocked dispatch costs one retry turn, never data.
- **Delegation by other words**: the predicate covers the observed shapes;
  the post-release signal (a loop-log grep) catches a new shape.
