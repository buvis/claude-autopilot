---
catchup: run
design: skip
default_model: sonnet
model_tier_rationale: a flag, a constant with a parameter, a skip ceiling, a grep option, a reorder and two doc lines; every acceptance is a named test or an rg hit
---

# Make the release gate run what it claims and the release script block what it says

Source: `docs/dev/project-management/audit-results/agoge-2026-10-14.md` (packets 11, 12, 26, 28; all confirmed).

## Problem

The `[checks] tracon` block (`dev/bin/release-checks:440-446`) runs without `--with textual`, so the 31 Textual pilot tests in `skills/run-autopilot/scripts/tracon/test_screens.py` self-skip and the gate prints `PASS 6545 FAIL 0 SKIP 34` while CHANGELOG line 12 calls `verify` the full suite; `test_every_tracked_test_file_is_gated` (`skills/run-autopilot/cli/test_release_checks_counts.py:339-355`) checks only that a file is named, and `run_pytest` (`dev/bin/release-checks:37-58`) folds every skip into `TOTAL_SKIP` without a ceiling, so the next `importorskip` joins the pile silently. The same file run with textual passes 65. `_kill_lane` (`skills/run-autopilot/cli/wave_launch.py:386-408`) hard-codes `((signal.SIGTERM, 60), (signal.SIGKILL, 10))`; `test_abort_leaves_a_lane_whose_group_outlived_sigkill_mid_loop` (`skills/run-autopilot/cli/test_wave_launch_abort.py:638`) and `test_abort_finishes_a_lane_whose_group_vanishes_at_the_sigkill` (`skills/run-autopilot/cli/test_wave_launch_abort_kill.py:122`) wait the real windows out, 131 s of every gate run (two timed runs: 338 s and 324 s, waves block 137 s each). CHANGELOG line 22 still says a forced rerun takes "about 220 seconds". `dev/bin/release` (`dev/bin/release:11-21`) refuses on a held or in-progress PRD saying "release is blocked" (commit 9f65c81) without a CHANGELOG entry, matches case-sensitively through `grep -rl`, and runs that check after the central-repo check, so a clone without `../claude-plugins` never reaches it.

## Solution

`release-checks` adds `--with textual` to the tracon block and a skip ceiling: `SKIP_ALLOWED=3` beside `run_pytest`, with a comment naming the three skips it covers (two `AUTOPILOT_LIVE` tests and one golden fixture), every pytest call passes `-rs` so each skip prints its reason, and a `TOTAL_SKIP` above the ceiling sets `INFRA_FAIL=1` with a line naming the count. A ceiling rather than a reason allowlist (the packet's first option): five lines of bash, and a new legitimate skip must raise the number with a reason in the same diff. `_kill_lane` reads its windows from a module constant `KILL_GRACE` and takes a `grace` argument that `abort` passes through, so the two abort tests run with sub-second windows while one new test pins the constant at `((signal.SIGTERM, 60), (signal.SIGKILL, 10))`. After that lands, the gate is timed twice and CHANGELOG line 22 states the median. `dev/bin/release` moves the block check above the central-repo check, uses `grep -rli`, and gets its `[Unreleased]` Added line.

## Requirements

### Must have
- The tracon block runs `--with textual`; `bash dev/bin/release-checks` reports `SKIP 3` or fewer and `FAIL 0`.
- `SKIP_ALLOWED=3` is defined once in `dev/bin/release-checks`, every `run_pytest` call passes `-rs`, and a run whose `TOTAL_SKIP` exceeds it ends with `EXIT` non-zero and a line `release-checks: SKIP <n> exceeds the ceiling of 3`.
- `KILL_GRACE` is a module constant in `skills/run-autopilot/cli/wave_launch.py`; `_kill_lane` and `abort` take `grace` defaulting to it; the two existing abort tests pass sub-second windows and finish in under 5 s together; `test_default_kill_grace_is_sixty_then_ten` pins the constant.
- CHANGELOG line 22 carries the median of two timed gate runs made after the abort tests shrink, not "about 220 seconds".
- `dev/bin/release` checks for a blocking PRD before it checks for the central repo, matches the phrase case-insensitively, and CHANGELOG `[Unreleased]` Added says the release script refuses while a held or in-progress PRD says the release is blocked.

### Nice to have
- None.

## Implementation

### Module: gate-script
- **Location**: `dev/bin/release-checks`
- **Responsibility**: run every gated test and refuse a skip pile
- **Exports**: `run_pytest` (unchanged)
- New symbols: `SKIP_ALLOWED`

### Module: abort-grace
- **Location**: `skills/run-autopilot/cli/wave_launch.py`
- **Responsibility**: the abort escalation windows are one constant with a test seam
- **Exports**: `abort()` (gains an optional `grace` keyword)
- New symbols: `KILL_GRACE`

### Module: release-script
- **Location**: `dev/bin/release`, `CHANGELOG.md`
- **Responsibility**: block first, case-insensitively, and say so in the CHANGELOG
- **Exports**: none

### Module: gate-truth-tests
- **Location**: `skills/run-autopilot/cli/test_release_checks_counts.py`, `skills/run-autopilot/cli/test_wave_launch_abort.py`
- **Responsibility**: pin the textual flag, the ceiling, the grace seam and the release-script order
- **Exports**: none
- New symbols: `test_tracon_block_runs_with_textual`, `test_skip_ceiling_fails_the_gate_above_three`, `test_abort_escalates_after_the_configured_grace`, `test_default_kill_grace_is_sixty_then_ten`, `test_release_block_check_is_case_insensitive`, `test_release_block_check_runs_before_the_central_repo_check`

### Dependencies
- gate-truth-tests: No dependencies (foundation)
- gate-script: Depends on [gate-truth-tests]
- abort-grace: Depends on [gate-truth-tests]
- release-script: Depends on [gate-truth-tests]

## Tasks

### Phase 0: Foundation
- [ ] Add `test_tracon_block_runs_with_textual` (the tracon block's command line contains `--with textual`), `test_skip_ceiling_fails_the_gate_above_three` (a copy of `dev/bin/release-checks` whose `run_pytest` is fed a stub summary of `1 passed, 4 skipped` ends with `EXIT` non-zero and the ceiling line), `test_release_block_check_is_case_insensitive` (a held PRD saying `Release is blocked` makes the copied script exit 1) and `test_release_block_check_runs_before_the_central_repo_check` (no `claude-plugins` sibling, a blocking PRD: stderr names the PRD, not the missing script) to `skills/run-autopilot/cli/test_release_checks_counts.py`; add `test_abort_escalates_after_the_configured_grace` (grace 0.2 s, the SIGKILL arrives within 1 s) and `test_default_kill_grace_is_sixty_then_ten` to `skills/run-autopilot/cli/test_wave_launch_abort.py`; rewrite the two existing abort tests to pass a sub-second `grace` - Acceptance: `uv run --no-project --with pytest python -m pytest -q skills/run-autopilot/cli/test_release_checks_counts.py skills/run-autopilot/cli/test_wave_launch_abort.py skills/run-autopilot/cli/test_wave_launch_abort_kill.py` reports the six new tests failing at the task's base commit and the two rewritten tests failing on the unknown `grace` argument.

### Phase 1: Core
- [ ] Implement `SKIP_ALLOWED`, `-rs` and the ceiling check in `dev/bin/release-checks` with `--with textual` on the tracon block; `KILL_GRACE` and the `grace` parameter in `skills/run-autopilot/cli/wave_launch.py`; the reorder and `grep -rli` in `dev/bin/release`; the CHANGELOG Added line for the release block and a Changed line for the textual gate and the skip ceiling (depends on: Phase 0) - Acceptance: the Phase 0 command passes every test; `rg -n 'with textual' dev/bin/release-checks` prints one hit; `rg -n 'grep -rli' dev/bin/release` prints one hit; `bash dev/bin/release-checks` prints `FAIL 0` and `SKIP 3` on its summary line.

### Phase 2: Integration
- [ ] Time `bash dev/bin/release-checks` twice with `time`, put the median wall time on CHANGELOG line 22 in place of "about 220 seconds", and record both measurements in the task report (depends on: Phase 1) - Acceptance: `rg -n 'about 220' CHANGELOG.md` prints nothing; the task report quotes both `real` lines.

## Success Criteria

- `bash dev/bin/release-checks` ends `FAIL 0 SKIP 3` and finishes in under 240 s wall on the same machine that measured 324 s and 338 s.
- `dev/bin/release` in a clone without `../claude-plugins` and with a hold PRD saying `Release is blocked` exits 1 naming the PRD.
