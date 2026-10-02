---
catchup: skip
design: skip
default_model: sonnet
model_tier_rationale: verbatim block pasted into five named files, each pinned by a contract test; no judgment
---

# Carry tool discipline into every Bash-bearing loop prompt

## Overview

### Problem Statement
The implementor prompts (`agents/ivan.md:64`, `skills/work/references/tess-prompt.md:44`) carry a tool-discipline block that keeps the model off `cat`, `head`, `tail`, `grep`, `find` and heterogeneous pipes, all of which the aegis `prefer_tools` hook blocks before they run. The review personas that hold Bash (`agents/alice.md`, `agents/blake.md`, `agents/eve.md`, `agents/victor.md`) and the orchestrator itself (`skills/run-autopilot/SKILL.md` § Shell Command Rules) do not. The 7-day session analysis to 2026-09-05 counted 112 cat/head/tail, 53 find, 34 grep and 30 pipe calls blocked across about 150 sessions, with 20 storms of 4 to 11 consecutive rejections; loop session 7da00fc4 (this repo, build phase) opened with `cat`, `find` and `head` blocked in a row. Every blocked call is a wasted turn in an opus or sonnet [1m] session.

### Target Users
The loop orchestrator session and the four Bash-bearing reviewer subagents; the operator paying for their turns.

### Success Metrics
- `uv run --no-project --with pytest python -m pytest -q skills/run-autopilot/scripts/test_review_prompt_contracts.py -k tool_discipline` passes with the two new tests.
- `rg -c 'Never call bash `head`' agents/alice.md agents/blake.md agents/eve.md agents/victor.md skills/run-autopilot/SKILL.md` reports 1 for each of the five files.

## Functional Decomposition

### Capability: One tool-discipline block, everywhere Bash is held
The same sentences reach every prompt that can spend a turn on a blocked command.

#### Feature: Reviewer block
- **Description**: the verbatim paragraph added to each of the four reviewer persona files, after the persona's tools line and before its first `##` heading.
- **Inputs**: none.
- **Outputs**: this exact text, one paragraph:
  `Never call bash `head`, `tail`, `cat`, `grep`, or `find` - a hook blocks them. Use the Read tool (offset/limit), `rg`, or `rg --files` instead. Never pipe between heterogeneous commands and never combine an inspection (read, list, search, diff) with a test, lint or build invocation in one Bash call - run them as separate calls. Pass an explicit `timeout` on every Bash call: 60000 ms for an inspection, 300000 ms for a lint run or a narrow test run, 600000 ms for a full suite or a full build.`
- **Behavior**: the first two sentences match `tess-prompt.md:44` word for word (minus the Edit clause reviewers have no use for); the pipe sentence adds the second most frequent block.

#### Feature: Orchestrator block
- **Description**: the same paragraph added to `skills/run-autopilot/SKILL.md` § Shell Command Rules as its first bullet.
- **Inputs**: none.
- **Outputs**: the paragraph above, as a bullet.
- **Behavior**: the section already governs the orchestrator's own shell use; the bullet makes the hook's rule the first thing it says.

#### Feature: Contract pins
- **Description**: two tests in `skills/run-autopilot/scripts/test_review_prompt_contracts.py`.
- **Inputs**: the five files.
- **Outputs**: `test_bash_bearing_personas_carry_tool_discipline` asserts each of the four persona files contains the paragraph exactly once and that the Read-only personas (`pat`, `rita`, `cora`, `grace`, `toby`, `mallory`, `trent`) do not contain it; `test_orchestrator_skill_carries_tool_discipline` asserts the SKILL.md bullet.
- **Behavior**: the paragraph text lives once in the test module as `TOOL_DISCIPLINE` and the persona files are read from `${CLAUDE_PLUGIN_ROOT}`-relative paths the module already resolves.

## Structural Decomposition

### Repository Structure

```
agents/
├── alice.md                                  # Maps to: Reviewer block
├── blake.md                                  # Maps to: Reviewer block
├── eve.md                                    # Maps to: Reviewer block
└── victor.md                                 # Maps to: Reviewer block
skills/run-autopilot/
├── SKILL.md                                  # Maps to: Orchestrator block (§ Shell Command Rules)
└── scripts/test_review_prompt_contracts.py   # Maps to: Contract pins
CHANGELOG.md
```

### Module: agents
- **Maps to capability**: One tool-discipline block, everywhere Bash is held
- **Responsibility**: persona system prompts for the reviewer subagents
- **Exports**:
  - `alice.md`, `blake.md`, `eve.md`, `victor.md` - each now carries the block

### Module: run-autopilot SKILL
- **Maps to capability**: One tool-discipline block, everywhere Bash is held
- **Responsibility**: the orchestrator's own operating rules
- **Exports**:
  - `## Shell Command Rules` - first bullet is the block

## Dependency Graph

### Foundation Layer (Phase 0)
No dependencies - built first.

- **contract pins**: the two tests, written first so they fail on the untouched files.

### Core Layer (Phase 1)
- **agents, run-autopilot SKILL**: Depends on [contract pins] (the edits make them pass).

### Integration Layer (Phase 2)
- **CHANGELOG**: Depends on [agents, run-autopilot SKILL].

## Implementation Phases

### Phase 0: Foundation
**Goal**: the pins exist and fail.

**Tasks**:
- [ ] Add `TOOL_DISCIPLINE` and the two tests to `scripts/test_review_prompt_contracts.py` (no deps) - Acceptance: `python -m pytest -q skills/run-autopilot/scripts/test_review_prompt_contracts.py -k tool_discipline` reports 2 failed before the Phase 1 edits.

**Exit Criteria**: the two tests exist and fail for the right reason (paragraph absent).

### Phase 1: Core
**Goal**: the five files carry the block.

**Tasks**:
- [ ] Paste the paragraph into `agents/alice.md`, `agents/blake.md`, `agents/eve.md`, `agents/victor.md` after the tools line (depends on: Phase 0) - Acceptance: `test_bash_bearing_personas_carry_tool_discipline` passes.
- [ ] Add the bullet to `skills/run-autopilot/SKILL.md` § Shell Command Rules (depends on: Phase 0) - Acceptance: `test_orchestrator_skill_carries_tool_discipline` passes; the existing SKILL.md prose pins in `scripts/` still pass (`python -m pytest -q skills/run-autopilot/scripts`).

**Exit Criteria**: `python -m pytest -q skills/run-autopilot/scripts/test_review_prompt_contracts.py` passes.

### Phase 2: Integration
**Goal**: the change is announced.

**Tasks**:
- [ ] Add a `### Changed` CHANGELOG entry under `[Unreleased]` naming the five files (depends on: Phase 1) - Acceptance: `rg -n 'tool discipline' CHANGELOG.md` returns one hit under `[Unreleased]`.

**Exit Criteria**: `bash dev/bin/release-checks` passes.

## Test Strategy

### Critical Scenarios
- **Happy path**: every Bash-bearing persona and the orchestrator carry the paragraph once.
- **Edge case**: a Read-only persona must not carry it (the test asserts absence for the seven).
- **Error case**: a future edit that drops or paraphrases the paragraph fails the pin.

## Risks
- **Prompt lines are obeyed, not enforced**: a residual block rate stays; the measure of success is the next 7-day analysis, not a suite count.
- **Persona byte-parity goldens**: the seven fanout personas are pinned byte-for-byte by the review-fanout workflow goldens; this PRD does not touch them.
