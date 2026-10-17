---
design: skip
default_model: sonnet
model_tier_rationale: one string constant and one expression with their exact text, four test expectations extended by the same constant, one additive test; the premise rg -c pins the existing-test edit
---

# Tell the session it is the loop

Source: batch 202610161547 (cache 0.9.0). Session 3c3ba0b1 (2026-10-17 01:13Z) was launched by the loop driver, ran `pgrep -lf "__main__.py loop"` as its first call, saw its own driver's pid, wrote "a running loop means I must not launch a competing manual session ... not starting", and ended after 22 seconds; the driver relaunched. Session e717febe (2026-10-16 19:33Z) did the same after reverting a formatter reflow: "a live autoclaude loop (pid 95710) is already running against this repo ... would race the same state.json". Both cited the project's auto-memory, which every session whose cwd is the checkout loads, headless ones included, and which tells interactive sessions to stop when a loop is live.

## Problem

The launch prompt (`prompt_for`, `skills/run-autopilot/cli/runner.py:99-106`) is the loop's only word to its session: the skill name, the brief sentence (`BRIEF_SUFFIX`, `skills/run-autopilot/cli/runner.py:86-87`) and the CLI and coreutils sentences (`CLI_SUFFIX`, `skills/run-autopilot/cli/runner.py:91-96`). Nothing in it says who started the session. A memory, rule or note that says "if an autopilot loop is live, stop, ask, or do not edit the checkout" is written for a human-started session, but the loop's own session reads the same text about itself, and whether it obeys the memory or the prompt is decided per session. Twice in one batch it obeyed the memory: a relaunch each time, and a build session mid-task honouring "never edit the checkout while a loop runs" would stall the batch. The same hazard exists in every repo the loop runs in, so the memory-side carve-out written on 2026-10-17 covers only this checkout.

## Solution

The prompt names its author. `runner.py` gains `LOOP_SUFFIX` beside `CLI_SUFFIX` with this exact text: ` This session was launched by the autopilot loop driver: a `__main__.py loop` process is your parent, not a competing session, and this checkout is yours to edit; never stop or ask because a loop is running.` `prompt_for` appends it after `CLI_SUFFIX` under the same `prompt.startswith(DEFAULT_PROMPT)` condition (`cli = CLI_SUFFIX + LOOP_SUFFIX if ... else ""`), so a custom prompt still gets neither sentence. The four existing prompt tests extend their expected strings by the same constant; one new test pins the sentence and its position.

## Requirements

### Must have
- `LOOP_SUFFIX` in `skills/run-autopilot/cli/runner.py` with the exact text above, and `prompt_for` returning `prompt + brief + CLI_SUFFIX + LOOP_SUFFIX` for the default prompt, `prompt + brief` for any other prompt.
- `test_prompt_names_the_brief_when_present`, `test_prompt_without_a_brief_still_names_the_cli`, `test_a_brief_that_is_a_directory_does_not_count` and `test_launch_prompt_forbids_blocked_coreutils` (`skills/run-autopilot/cli/test_runner.py:216-279`) keep their exact-equality shape with `+ LOOP_SUFFIX` (the literal-string test adds the sentence as a fourth literal) appended after the CLI sentence.
- New test `test_launch_prompt_says_the_session_is_the_loop` in `skills/run-autopilot/cli/test_runner.py` (registered under `[checks] run-autopilot cli remainder`, `dev/bin/release-checks:207`): with and without a brief, the prompt ends with `LOOP_SUFFIX`, contains "launched by the autopilot loop driver" and "never stop or ask because a loop is running", and `prompt_for(ap, "custom")` contains neither.
- A CHANGELOG `[Unreleased]` Fixed entry under **run-autopilot**: the loop's launch prompt tells each session it was started by the loop driver, so a live-loop rule in memory or notes no longer makes it refuse to work.

### Nice to have
- None.

## Implementation

### Module: launch-prompt
- **Location**: `skills/run-autopilot/cli/runner.py` (`prompt_for`)
- **Responsibility**: the launch prompt says the loop driver started the session and that the running loop is its parent
- **Exports**: `prompt_for()`, `DEFAULT_PROMPT`, `BRIEF_SUFFIX`, `CLI_SUFFIX` (unchanged)
- New symbols: `LOOP_SUFFIX`

### Module: launch-prompt-tests
- **Location**: `skills/run-autopilot/cli/test_runner.py`
- **Responsibility**: pin the sentence, its position after the CLI sentence, and its absence on a custom prompt
- **Exports**: none
- New symbols: `test_launch_prompt_says_the_session_is_the_loop`

### Dependencies
- launch-prompt: No dependencies (foundation)
- launch-prompt-tests: Depends on [launch-prompt]

## Tasks

### Phase 0: Foundation
- [ ] Extend the four prompt tests and add `test_launch_prompt_says_the_session_is_the_loop` in `skills/run-autopilot/cli/test_runner.py`. Premise: `rg -c "CLI_SUFFIX" skills/run-autopilot/cli/test_runner.py` prints 4 before the edit (the import and three expectations; the coreutils test spells the sentences out) and `rg -c "LOOP_SUFFIX" skills/run-autopilot/cli/test_runner.py` prints at least 5 after it; a different count before the edit means the file moved and the task stops and reports. - Acceptance: `uv run --no-project --with pytest python -m pytest -q skills/run-autopilot/cli/test_runner.py -k "prompt"` fails on `LOOP_SUFFIX` (ImportError) against the old runner and names the five prompt tests.

### Phase 1: Core
- [ ] Add `LOOP_SUFFIX` and the `cli = CLI_SUFFIX + LOOP_SUFFIX` expression in `skills/run-autopilot/cli/runner.py` `prompt_for`, and the CHANGELOG entry (depends on: Phase 0) - Acceptance: `uv run --no-project --with pytest python -m pytest -q skills/run-autopilot/cli/test_runner.py` passes; `rg -c "launched by the autopilot loop driver" skills/run-autopilot/cli/runner.py` prints 1; `rg -n "run-autopilot.*loop driver" CHANGELOG.md` prints one line under `[Unreleased]`.

## Success Criteria

- `test_launch_prompt_says_the_session_is_the_loop` passes and the four extended prompt tests keep their exact-equality assertions.
- Post-release signal: no loop-metrics row with `phase_launched` equal to `phase_end` and `wall_secs` under 60 whose transcript contains "competing manual session" or "already running against this repo" (`rg -l` over `~/.claude/projects/<repo>/*.jsonl`).
