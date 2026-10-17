---
design: skip
default_model: sonnet
model_tier_rationale: one dictionary entry with its exact key and value, one docstring line, one existing test's key tuple extended, one additive test
---

# Launch loop sessions with ponytail off

Source: batch 202610161547, PRD 00326 build session ce5b54e7 (2026-10-17 11:38Z, a sonnet orchestrator), in its own words before it implemented two opus-tier tasks with no Ivan, Pat or Devon: "Given this is well-scoped and I have the full contract, I'll implement directly (ponytail: simplest path) rather than going through a heavy multi-agent dispatch ceremony, since I'm the orchestrator session and this is straightforward code." The 00324 design session (d2db03ee, 01:32Z) said the same thing as "compress some of the heavier dispatch scaffolding ... given session budget", and 00324's rework session (8ac68b02) wrote all four D-tasks itself. Seven transcripts in this project since 2026-09-29 carry an assistant turn that cites ponytail.

## Problem

The operator's ponytail plugin (`ponytail@ponytail` 4.7.0, a user-level plugin) runs a SessionStart hook, `hooks/ponytail-activate.js`, in every session, and `claude -p` sessions the loop launches are sessions: each one starts with "PONYTAIL MODE ACTIVE — level: full" and the ponytail ruleset ("the best code is the code never written", "fewest files", "ship the lazy version"). The operator's own global rule says ponytail must never thin, skip or down-scope skill-mandated steps, but a headless session has nobody to hold it to that, and the work skill's dispatch procedure is the step it thins: the orchestrator writes the code itself, stamps the attempt with an invented value, and the per-task gates that exist to catch a wrong implementation never run. `LAUNCH_ENV` (`skills/run-autopilot/cli/runner.py:56-60`) is where the loop already tells its sessions what kind of session they are (`WARDEN_UNATTENDED`, `CLAUDE_UNATTENDED`, `CLAUDE_CODE_PRINT_BG_WAIT_CEILING_MS`), layered onto the child environment by `child_env` (`skills/run-autopilot/cli/runner.py:149-158`). The plugin reads `PONYTAIL_DEFAULT_MODE` first, before its config file, and `off` makes the activation hook exit before it emits any rules (the plugin's default-mode resolver in its hooks/ponytail-config.js, and the off branch at the top of hooks/ponytail-activate.js). Nothing in the launch sets it.

## Solution

`LAUNCH_ENV` gains the entry `"PONYTAIL_DEFAULT_MODE": "off"`. `child_env` already copies every `LAUNCH_ENV` entry into the child, so no other code changes. The module docstring's launch line, which lists `WARDEN_UNATTENDED` and its two siblings (`skills/run-autopilot/cli/runner.py:5`), names the new variable beside them. One side effect is accepted and named in the docstring: the plugin's off branch calls its `clearMode()`, which clears the operator's `~/.claude/.ponytail-active` statusline flag until the operator's next interactive session start; the loop's sessions never shared that flag on purpose, so nothing else changes for them.

Out of scope and named for the record: the loupe plugin's end-of-turn formatter has no environment switch and needs a `CLAUDE_UNATTENDED` guard in its own repository.

## Requirements

### Must have
- `LAUNCH_ENV["PONYTAIL_DEFAULT_MODE"] == "off"` in `skills/run-autopilot/cli/runner.py`, and the docstring launch line at `skills/run-autopilot/cli/runner.py:5` names `PONYTAIL_DEFAULT_MODE=off`.
- `test_spawn_sets_the_command_scoped_unattended_env` (`skills/run-autopilot/cli/test_runner.py:363-382`) extends the stub's key tuple with `PONYTAIL_DEFAULT_MODE` so its equality against `LAUNCH_ENV` keeps covering every entry; `test_child_env_drops_every_host_marker` (`skills/run-autopilot/cli/test_runner.py:593-604`) already loops over `LAUNCH_ENV` and needs no edit.
- New test `test_launch_env_turns_ponytail_off` in `skills/run-autopilot/cli/test_runner.py` (registered under `[checks] run-autopilot cli remainder`, `dev/bin/release-checks:207`): `LAUNCH_ENV["PONYTAIL_DEFAULT_MODE"] == "off"`, and `child_env({"PONYTAIL_DEFAULT_MODE": "full"})[0]["PONYTAIL_DEFAULT_MODE"] == "off"` (the launch value wins over an inherited interactive one).
- A CHANGELOG `[Unreleased]` Fixed entry under **run-autopilot**: loop sessions start with the ponytail plugin off, so a headless orchestrator no longer cites it to skip the work skill's implementor, reviewer and adversarial dispatches.

### Nice to have
- None.

## Implementation

### Module: launch-env
- **Location**: `skills/run-autopilot/cli/runner.py` (`LAUNCH_ENV`, `child_env`)
- **Responsibility**: every loop-launched session starts with the ponytail plugin off
- **Exports**: `LAUNCH_ENV`, `child_env()` (unchanged signature)
- New symbols: `PONYTAIL_DEFAULT_MODE`

### Module: launch-env-tests
- **Location**: `skills/run-autopilot/cli/test_runner.py`
- **Responsibility**: pin the new entry and its precedence over an inherited value
- **Exports**: none
- New symbols: `test_launch_env_turns_ponytail_off`

### Dependencies
- launch-env: No dependencies (foundation)
- launch-env-tests: Depends on [launch-env]

## Tasks

### Phase 0: Foundation
- [ ] Extend `test_spawn_sets_the_command_scoped_unattended_env` and add `test_launch_env_turns_ponytail_off` in `skills/run-autopilot/cli/test_runner.py`. Premise: `rg -c "PONYTAIL_DEFAULT_MODE" skills/run-autopilot/cli/runner.py` prints 0 before the edit; a different count means the launch env already changed and the task stops and reports. - Acceptance: `uv run --no-project --with pytest python -m pytest -q skills/run-autopilot/cli/test_runner.py -k "ponytail or unattended_env"` fails both tests against the current `LAUNCH_ENV`.

### Phase 1: Core
- [ ] Add the `LAUNCH_ENV` entry, the docstring line and the CHANGELOG entry (depends on: Phase 0) - Acceptance: `uv run --no-project --with pytest python -m pytest -q skills/run-autopilot/cli/test_runner.py` passes; `rg -c "PONYTAIL_DEFAULT_MODE" skills/run-autopilot/cli/runner.py` prints 2; `rg -n "run-autopilot.*ponytail" CHANGELOG.md` prints one line under `[Unreleased]`.

## Success Criteria

- `test_launch_env_turns_ponytail_off` passes and every existing `test_runner.py` test still passes.
- Post-release signal: no loop session transcript under `~/.claude/projects/<repo>/` written after the release contains "PONYTAIL MODE ACTIVE" (`rg -l`), and the dispatch ledger shows an `ivan` row for every non-docs task of a full-lane PRD.
