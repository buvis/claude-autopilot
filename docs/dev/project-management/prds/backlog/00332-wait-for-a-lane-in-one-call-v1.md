---
design: skip
default_model: sonnet
model_tier_rationale: one constant and a parser accessor in a 60-line script, prose edits with their exact replacement text, additive tests; nothing is designed
---

# Wait for a reviewer lane in one call

Source: batch 202610161547's first session (2026-10-16, session cdf17745): 35 of its first 108 requests fell between the codex design-review launch at 13:59:12Z and the first read of its output; the 00312 review session (2026-10-15, session 2adad986): five `await_reviewer_outputs.py --budget 100` calls, 11 `Monitor` calls, 10 `TaskStop` calls.

## Problem

Every CLI reviewer lane (codex, gemini) is a background Bash task, and the session that launched it has to stay alive and idle until the `-o` file lands.

The wait helper `skills/review-work-completion/scripts/await_reviewer_outputs.py` caps one call at a `--budget` of 100 seconds by default: its `add_argument` call at `skills/review-work-completion/scripts/await_reviewer_outputs.py:34-38` says "keep well under the Bash tool timeout so the harness never auto-backgrounds the call". The Watcher prompt quoted verbatim at `skills/review-work-completion/SKILL.md:272` and `skills/fast-track/SKILL.md:39` re-runs it "up to 30 times total" and returns `DONE` or `WAITING`.

`skills/design-solution/SKILL.md:206-215` launches codex with `run_in_background` and says to read the output "when the background command completes"; the deadline paragraph at `skills/design-solution/SKILL.md:250-259` tells the session to `Read` the file on the completion notification within a ~10-min×2 deadline, but prescribes no wait call.

The orchestrator fills the gap with turns: on 2026-10-16 a three-minute codex design review cost 35 requests and 8.2M cache-read tokens (47% of the session so far) spent on `pgrep`, `wc`, a hook-blocked `ps aux | grep`, `sleep 60`, `sleep 90`, three `Monitor` calls, three `ToolSearch` calls, a `ScheduleWakeup`, and reading the wait script and `codex-run.sh` themselves. The Bash tool blocks a foreground call for up to 600000 ms when its `timeout` parameter is set, so one call can cover the whole wait; the 100-second budget predates that parameter.

## Solution

Raise the helper's default budget to 570 seconds and tell every call site to pass the Bash tool's `timeout` parameter as 600000, so a wait is one blocking call that returns when the files are complete or after 9.5 minutes. The Watcher prompt runs it up to 6 times (about 57 minutes, the same ceiling as 30 runs of 100 s). `design-solution` gets an explicit wait step: one foreground call right after the background launch, repeated once at most on `WAITING` (its existing ~10-min×2 deadline), and a ban on status pokes between launch and read. A prose test pins the budget and the ban in each file; a unit test pins the default.

## Requirements

### Must have
- `await_reviewer_outputs.py` exposes `DEFAULT_BUDGET = 570.0` and `build_parser()`; `main()` uses `build_parser()`; the `--budget` help text reads `max seconds this call blocks; pass the Bash tool's timeout parameter as 600000 ms so one call covers the whole wait`.
- The Watcher prompt at `skills/review-work-completion/SKILL.md:272` and `skills/fast-track/SKILL.md:39` reads `--budget 570`, `as ONE foreground Bash call with the Bash tool's timeout parameter set to 600000`, and `up to 6 times total`; `skills/review-work-completion/SKILL.md:274` reads `after 6 runs (~57 min)`.
- `skills/design-solution/SKILL.md` step 2 gains, right after the background launch block at lines 208-211: `Then wait with ONE foreground Bash call, the Bash tool's timeout parameter set to 600000: python3 ${CLAUDE_PLUGIN_ROOT}/skills/review-work-completion/scripts/await_reviewer_outputs.py --budget 570 <the -o path above>. On WAITING run it once more; a second WAITING is the deadline below. Between the launch and the read of the -o file run nothing else about the lane: no pgrep, ps, wc or sleep, no Monitor or ScheduleWakeup, no reading of the helper scripts.`
- No `--budget 100` remains in any `skills/**/*.md` file.
- Fail-first tests: `test_default_budget_fits_one_max_length_bash_call` in `skills/review-work-completion/scripts/test_await_reviewer_outputs.py`, and a new `skills/review-work-completion/scripts/test_lane_wait_prose.py` registered in `dev/bin/release-checks` under `[checks] review-work-completion scripts` (`dev/bin/release-checks:380`). Existing pins of the old numbers in `skills/review-work-completion/scripts/test_carl_skip_prose.py` and `skills/fast-track/scripts/test_fast_track_prose.py`, if any, move to the new numbers without changing their test count.
- A CHANGELOG `[Unreleased]` Changed entry under **review-work-completion**.

### Nice to have
- None.

## Implementation

### Module: lane-wait-helper
- **Location**: `skills/review-work-completion/scripts/await_reviewer_outputs.py`
- **Responsibility**: one call blocks for as long as the Bash tool allows
- **Exports**: `main()`, `is_complete()`
- New symbols: `DEFAULT_BUDGET`, `build_parser`

### Module: lane-wait-prose
- **Location**: `skills/review-work-completion/SKILL.md`, `skills/fast-track/SKILL.md`, `skills/design-solution/SKILL.md`
- **Responsibility**: every lane wait is one long call, never a poll loop in the orchestrator's own turns
- **Exports**: none (prose)

### Module: lane-wait-tests
- **Location**: `skills/review-work-completion/scripts/test_await_reviewer_outputs.py`, `skills/review-work-completion/scripts/test_lane_wait_prose.py`
- **Responsibility**: pin the default budget, the three call sites and the no-poke sentence
- **Exports**: none
- New symbols: `test_lane_wait_prose.py`, `test_default_budget_fits_one_max_length_bash_call`, `test_watcher_prompts_wait_in_long_calls`, `test_design_review_waits_once_and_never_polls`, `test_no_prose_keeps_the_hundred_second_budget`

### Dependencies
- lane-wait-tests: No dependencies (foundation)
- lane-wait-helper: Depends on [lane-wait-tests]
- lane-wait-prose: Depends on [lane-wait-tests]

## Tasks

### Phase 0: Foundation
- [ ] Add `test_default_budget_fits_one_max_length_bash_call` to `skills/review-work-completion/scripts/test_await_reviewer_outputs.py` (import the module from the test file's own directory and assert `build_parser().get_default("budget") == 570.0`), and write `skills/review-work-completion/scripts/test_lane_wait_prose.py` with `test_watcher_prompts_wait_in_long_calls` (both Watcher prompt lines contain `--budget 570`, `timeout parameter set to 600000` and `up to 6 times total`; `skills/review-work-completion/SKILL.md` contains `after 6 runs (~57 min)`), `test_design_review_waits_once_and_never_polls` (`skills/design-solution/SKILL.md` contains `await_reviewer_outputs.py --budget 570`, `On WAITING run it once more`, and one sentence naming `pgrep`, `Monitor` and `ScheduleWakeup`), and `test_no_prose_keeps_the_hundred_second_budget` (`rg -l -F -- '--budget 100' skills --glob '*.md'` run through `subprocess` from the repo root prints no path). Register the new file in the `[checks] review-work-completion scripts` block of `dev/bin/release-checks` - Acceptance: `uv run --no-project --with pytest python -m pytest -q skills/review-work-completion/scripts/test_await_reviewer_outputs.py skills/review-work-completion/scripts/test_lane_wait_prose.py` reports the four new tests failing and the seven existing tests passing at the task's base commit; `rg -c 'test_lane_wait_prose.py' dev/bin/release-checks` prints 1.

### Phase 1: Core
- [ ] In `await_reviewer_outputs.py` add `DEFAULT_BUDGET = 570.0` after the imports, move the parser construction into `def build_parser() -> argparse.ArgumentParser` with `default=DEFAULT_BUDGET` and the help text from Requirements, and have `main()` call `build_parser().parse_args()`; apply the three prose edits from Requirements verbatim; update any pin of `--budget 100`, `30 times` or `30 runs (~50 min)` in `test_carl_skip_prose.py` and `test_fast_track_prose.py` to the new values (depends on: Phase 0) - Acceptance: `uv run --no-project --with pytest python -m pytest -q skills/review-work-completion/scripts/test_await_reviewer_outputs.py skills/review-work-completion/scripts/test_lane_wait_prose.py skills/review-work-completion/scripts/test_carl_skip_prose.py skills/fast-track/scripts/test_fast_track_prose.py skills/run-autopilot/scripts/test_design_review_contract.py` passes; `rg -c '^def test_' skills/review-work-completion/scripts/test_carl_skip_prose.py skills/fast-track/scripts/test_fast_track_prose.py` prints the same counts as at the task's base commit.
- [ ] Add the CHANGELOG `[Unreleased]` Changed entry `**review-work-completion**: a reviewer-lane wait is one foreground call of up to 570 s with the Bash timeout raised, in the review Watcher, the fast-track Watcher and the design review, instead of 100 s polls` (depends on: Phase 1) - Acceptance: `rg -c 'one foreground call of up to 570 s' CHANGELOG.md` prints 1.

## Success Criteria

- On the next batch, a design-review transcript shows at most two requests between the `codex-run.sh` launch and the first `Read` of `design-codex-output-<id>.txt`.
- `test_lane_wait_prose.py` and `test_await_reviewer_outputs.py` are green and listed in `dev/bin/release-checks`.
