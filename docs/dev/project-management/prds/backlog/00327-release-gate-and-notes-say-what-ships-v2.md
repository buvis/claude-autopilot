---
catchup: run
design: skip
default_model: sonnet
model_tier_rationale: six small exact fixes to two shell scripts, the CHANGELOG and one dead test
---

# The release gate and the notes say what ships (v2)

Source: `docs/dev/project-management/audit-results/agoge-2026-10-15.md` packets 12, 13, 14, 25, 26, 28; done PRD 00313.

## Problem

Six gaps between what the release machinery claims and what it does. (1) PRD 00313 closed as done with its success line "finishes in under 240 s wall" unmet: two clone runs of `dev/bin/release-checks` took 293.55 s and 292.95 s under load, recon measured 261 s and wendy 272 s, and its must-have "CHANGELOG line 22 carries the median of two timed gate runs" was never written (00311's commit d807c22c deleted the line; `rg -n 'about 220|median' CHANGELOG.md` prints nothing). The largest block is the serial `review verbs` block whose `run_pytest` call starts at `dev/bin/release-checks:329`, 83-87 s (packet 12). (2) 00308's replay process-group kill (commit 618e792b) and 00309's `close_from_artifacts` (commit 5a451ed5) are live and tested with no `[Unreleased]` line; 00309's must-have named an Added entry under **work** (packet 13). (3) `BLOCKED` (`dev/bin/release:11`) matches only the literal phrase "release is blocked"; triage stubs carry `severity: critical` and no phrase, so a cut today would ship 00307's open CRITICAL stubs with no refusal, while CHANGELOG line 20 claims the script "refuses first on a held/in-progress PRD" (packet 14; the script itself was not run, so this half is read from the code). (4) `run_harness` (`dev/bin/release-checks:69-89`) ignores `SKIP:` lines, which `SKIP` at `skills/use-codex/scripts/test_codex_run.sh:307` emits, so five harness skips count as `SKIP 0` while the pytest ceiling `SKIP_ALLOWED` (`dev/bin/release-checks:35`) fires on four (packet 25). (5) `test_golden_baseline_engram_session_matches_recorded_numbers` (`skills/work/scripts/test_check_build_overhead.py:594`) skips on every machine, its golden transcript having been pruned, and holds one of the three tolerated skip slots (packet 26). (6) The release step "run `skills/run-autopilot/cli/test_launch_mcp_live.py` once by hand" lives only in two audit notes; `dev/bin/release` and the CHANGELOG do not name it, and the gate counts both `AUTOPILOT_LIVE` tests (`LIVE` at `skills/run-autopilot/cli/test_launch_mcp_live.py:31`) as tolerated skips (packet 28).

## Solution

State the measurement, write the missing lines, and make the script enforce its own claims. (1) This PRD times the gate twice on a quiet machine, adds a Changed line under `[Unreleased]` stating the median wall time, and appends a "## Measured" note with both `real` lines to the done PRD 00313; no parallelisation (recorded as an `/assess-evolution` candidate). (2) Two lines: Fixed under **review-work-completion** (the replay kills its runner's whole process group on its own timeout) and Added under **work** (handoff closes Ivan, Tess and Pat rows from their commits and review artifacts instead of marking them lost). (3) `dev/bin/release` also refuses when any file under `prds/hold` or `prds/wip` carries a frontmatter line `severity: critical`, listing the files, and line 20 of the CHANGELOG states both rules. (4) `run_harness` counts `^SKIP:` lines into `TOTAL_SKIP` and applies the same ceiling check `run_pytest` applies. (5) The golden test is deleted and `SKIP_ALLOWED` drops to 2 with its comment naming the two live tests. (6) `dev/bin/release` runs `env AUTOPILOT_LIVE=1 uv run --no-project --with pytest python -m pytest -q skills/run-autopilot/cli/test_launch_mcp_live.py` after the block checks and before the central-repo check, printing the step and refusing on a non-zero exit.

## Requirements

### Must have
- CHANGELOG `[Unreleased]` carries a Changed line with the measured median gate time, the two missing lines from (2), and a reworded line 20 naming the phrase rule and the `severity: critical` rule.
- `dev/bin/release` exits 1 naming the file when a `prds/hold` or `prds/wip` file carries `severity: critical`, before the phrase check's own message and before the central-repo check.
- `dev/bin/release` runs the live MCP test after the block checks and before the central-repo check and exits non-zero when it fails.
- `run_harness` adds every `^SKIP:` line to `TOTAL_SKIP` and reports `SKIP N exceeds the ceiling` the same way `run_pytest` does.
- `SKIP_ALLOWED=2`; `test_golden_baseline_engram_session_matches_recorded_numbers` no longer exists.
- Done PRD 00313 carries the "## Measured" note with both timed runs.

### Nice to have
- None.

## Implementation

### Module: release-script
- **Location**: `dev/bin/release`
- **Responsibility**: refuse on a CRITICAL stub and run the live MCP test before touching the central repo
- **Exports**: none

### Module: release-checks
- **Location**: `dev/bin/release-checks` (`run_harness`, `SKIP_ALLOWED`), `skills/work/scripts/test_check_build_overhead.py`
- **Responsibility**: count harness skips, lower the ceiling, drop the dead test
- **Exports**: none

### Module: release-notes
- **Location**: `CHANGELOG.md`, `docs/dev/project-management/prds/done/00313-release-gate-runs-what-it-claims-v1.md`
- **Responsibility**: the measured time, the two missing lines, the reworded block rule
- **Exports**: none

### Module: release-truth-tests
- **Location**: `skills/run-autopilot/cli/test_release_checks_counts.py`
- **Responsibility**: pin the two new refusals, the harness skip count and the ceiling
- **Exports**: none
- New symbols: `test_release_refuses_on_a_critical_hold_stub`, `test_release_runs_the_live_mcp_test_before_the_central_repo_check`, `test_harness_skip_lines_count_toward_the_ceiling`, `test_skip_ceiling_is_two`, `test_skip_ceiling_fails_the_gate_above_the_ceiling`

### Dependencies
- release-truth-tests: No dependencies (foundation)
- release-script: Depends on [release-truth-tests]
- release-checks: Depends on [release-truth-tests]
- release-notes: Depends on [release-checks]

## Tasks

### Phase 0: Foundation
- [ ] Add `test_release_refuses_on_a_critical_hold_stub` (a fixture hold file with `severity: critical` and no phrase: exit 1, the file named on stderr), `test_release_runs_the_live_mcp_test_before_the_central_repo_check` (a fake `uv` first on PATH that records its arguments and exits 1: `release` exits non-zero, the recorded arguments name `test_launch_mcp_live.py`, and no central-repo message is printed), `test_harness_skip_lines_count_toward_the_ceiling` (a stub harness printing five `SKIP:` lines and a `SUMMARY:` line: the gate's own summary reports `SKIP 5` and the ceiling message) and `test_skip_ceiling_is_two` to `skills/run-autopilot/cli/test_release_checks_counts.py`, renaming `test_skip_ceiling_fails_the_gate_above_three` to `test_skip_ceiling_fails_the_gate_above_the_ceiling` - Acceptance: `uv run --no-project --with pytest python -m pytest -q skills/run-autopilot/cli/test_release_checks_counts.py` reports the four new tests failing at the task's base commit and no existing test failing.

### Phase 1: Core
- [ ] Add the `severity: critical` refusal and the live MCP step to `dev/bin/release` in the stated order; count `^SKIP:` lines in `run_harness` and set `SKIP_ALLOWED=2` in `dev/bin/release-checks`; delete `test_golden_baseline_engram_session_matches_recorded_numbers` from `skills/work/scripts/test_check_build_overhead.py` (depends on: Phase 0) - Acceptance: the Phase 0 command passes every test; `rg -c 'golden baseline transcript' skills/work/scripts/test_check_build_overhead.py` prints 0; `rg -n '^SKIP_ALLOWED=2' dev/bin/release-checks` prints one hit.

### Phase 2: Integration
- [ ] Time `bash dev/bin/release-checks` twice with `time` on a quiet machine, write the median as a Changed line under `[Unreleased]` (`**run-autopilot**: a full gate run takes about <median> s wall (median of two timed runs on 2026-10-1x)`), add the two missing lines and reword line 20, and append `## Measured <date>` with both `real` lines to `docs/dev/project-management/prds/done/00313-release-gate-runs-what-it-claims-v1.md` (depends on: Phase 1) - Acceptance: `rg -n 'median of two timed runs|close_from_artifacts|process group on its own timeout|severity: critical' CHANGELOG.md` prints four hits under `[Unreleased]`; `rg -n '^## Measured' docs/dev/project-management/prds/done/00313-release-gate-runs-what-it-claims-v1.md` prints one hit; the gate ends `FAIL 0 SKIP 2 EXIT 0`.

## Success Criteria

- With a `severity: critical` stub in `prds/hold`, `bash dev/bin/release` exits 1 and names it before any other output.
- `bash dev/bin/release-checks` ends `PASS <n> FAIL 0 SKIP 2 EXIT 0`, and a harness that skips raises `TOTAL_SKIP`.
- `rg -n 'test_launch_mcp_live' dev/bin/release` prints one hit.
