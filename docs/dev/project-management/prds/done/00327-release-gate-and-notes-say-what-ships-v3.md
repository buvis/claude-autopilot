---
catchup: skip
design: skip
default_model: sonnet
model_tier_rationale: four small exact edits to two shell scripts, one test deletion and three CHANGELOG lines, every edit and assertion given verbatim
---

# The release gate and the notes say what ships (v3)

> Closed by hand on 2026-10-19 from the operator's monitoring session. The card landed on master (13d02bab implementation, 1fbc3256 rework after Victor confirmed Alice's HIGH), both card gates green, Eve's delta clean. The park at 09:10 CEST came from the batch suite failing two CHANGELOG prose tests in `test_review_verbs_prose.py` that read `[Unreleased]` alone and went red the moment the v0.10.0 cut moved their entries into the release section; fixed in 81c0f2b4 (the tests now read the newest release section too). Nothing in this card caused it.

Source: v2 of this PRD (now under done/) was parked on 2026-10-17 at 13:44 CEST. Its fast-track card lifted the success criterion that named the release script into a gate, warden refused the publish, and the item stalled with one of six gaps landed: commit 23555ea5 with its test 2b643ac5, the release refuses on an open critical triage stub. PRD 00347 stops the card parser from lifting a release command again, but the loop runs the installed cache until the next release, so this version names no publish command anywhere a parser could lift it. Gap 1 (a measured gate time written into the CHANGELOG) is dropped on purpose: the number rots the day a check block is added, the batch reports already record every timed gate run, and 00313's unmet line stays as the record it is.

## Problem

Four gaps remain between what the release machinery claims and what it does.
(2) `close_from_artifacts` (`skills/work/scripts/record_dispatch.py:231`, called by the handoff verb at `skills/work/scripts/record_dispatch.py:318`) is live and tested with no `[Unreleased]` line; PRD 00309's must-have named an Added entry under **work**.
(4) `run_harness` (`dev/bin/release-checks:69-89`) reads only the harness's summary line, so a harness skip never reaches the gate's skip count: `SKIP` (`skills/use-codex/scripts/codex_run_test_lib.sh:14`) prints a `SKIP:` line and `skills/use-codex/scripts/test_codex_run.sh:307` emits it, while `run_pytest` (`dev/bin/release-checks:40-65`) adds every pytest skip to `TOTAL_SKIP` and fails the gate above the ceiling (`dev/bin/release-checks:57-60`).
(5) `test_golden_baseline_engram_session_matches_recorded_numbers` (`skills/work/scripts/test_check_build_overhead.py:587-594`) skips on every machine, its golden transcript long pruned, and holds one of the three slots of `SKIP_ALLOWED` (`dev/bin/release-checks:33-35`).
(6) The release step "run the live MCP launch test by hand" lives only in two audit notes: the shim (`dev/bin/release:11-27`) checks the block, pulls the central repo and execs the shared script, and never runs that test.
Its two tests skip unless `LIVE` (`skills/run-autopilot/cli/test_launch_mcp_live.py:31`) is set (`test_default_launch_loads_only_context7` and `test_override_launch_loads_no_servers`, `skills/run-autopilot/cli/test_launch_mcp_live.py:67-73`), so the gate tolerates them as two skips and nothing ever runs them.

## Solution

(2) One Added line under **work** in `CHANGELOG.md`: `**work**: handoff closes Ivan, Tess and Pat rows from their commits and review artifacts instead of marking them lost`.

(4) `run_harness` (`dev/bin/release-checks:69-89`) counts its harness's skip lines. Directly after its `echo "$out"` line it gains:

```bash
  local s
  s="$(echo "$out" | grep -cE '^SKIP:' || true)"
  TOTAL_SKIP=$((TOTAL_SKIP + ${s:-0}))
  if [[ "$TOTAL_SKIP" -gt "$SKIP_ALLOWED" ]]; then
    echo "release-checks: SKIP $TOTAL_SKIP exceeds the ceiling of $SKIP_ALLOWED"
    INFRA_FAIL=1
  fi
```

That is the ceiling check of `TOTAL_SKIP` against `SKIP_ALLOWED` that the pytest runner already applies (`dev/bin/release-checks:57-60`), unchanged there.

(5) `SKIP_ALLOWED` (`dev/bin/release-checks:33-35`) becomes `SKIP_ALLOWED=2` and its two comment lines read `# The only skips this gate tolerates: the two AUTOPILOT_LIVE-gated tests in` and `# skills/run-autopilot/cli/test_launch_mcp_live.py.`.
The golden test block (the comment line, the skip decorator, `test_golden_baseline_engram_session_matches_recorded_numbers` at `skills/work/scripts/test_check_build_overhead.py:587-594` and its body) is deleted.

(6) `dev/bin/release` runs the live test between the block check and the central-repo check. After the `fi` that closes the block check (`dev/bin/release:16`) and before the `RELEASE` existence check (`dev/bin/release:18-21`) it gains:

```bash
echo "[release] live MCP launch test (AUTOPILOT_LIVE=1)"
env AUTOPILOT_LIVE=1 uv run --no-project --with pytest python -m pytest -q "$REPO_ROOT/skills/run-autopilot/cli/test_launch_mcp_live.py"
```

The shim's `set -euo pipefail` (`dev/bin/release:5`) turns a failing test into a refused release before anything is pulled or pushed.

## Requirements

### Must have
- The four edits above, verbatim; the pytest ceiling path in `run_pytest` unchanged.
- Fail-first tests in `skills/run-autopilot/cli/test_release_checks_counts.py` (registered at `dev/bin/release-checks:355`):
  - `test_release_runs_the_live_mcp_test_before_the_central_repo_check`: a fixture from `_fixture_repo` (`skills/run-autopilot/cli/test_release_checks_counts.py:331-341`) with no hold PRD and no claude-plugins sibling, plus a directory holding an executable `uv` that appends its arguments to a file and exits 1, placed first on `PATH` for the run; the release copy exits non-zero, the recorded arguments contain `test_launch_mcp_live.py`, and `claude-plugins` is absent from stderr, the way `test_release_block_check_runs_before_the_central_repo_check` (`skills/run-autopilot/cli/test_release_checks_counts.py:369-384`) asserts ordering.
  - `test_harness_skip_lines_count_toward_the_ceiling`: through `_run_helpers` (`skills/run-autopilot/cli/test_release_checks_counts.py:38-52`), one `run_harness bash -c` call that prints five `SKIP: x` lines and `SUMMARY: 1 passed, 0 failed`, then `echo "PASS $TOTAL_PASS FAIL $TOTAL_FAIL SKIP $TOTAL_SKIP INFRA $INFRA_FAIL"`; the output contains `SKIP 5`, `INFRA 1` and `exceeds the ceiling`, beside `test_harness_summary_line_supplies_the_measured_totals` (`skills/run-autopilot/cli/test_release_checks_counts.py:144-152`).
  - `test_skip_ceiling_is_two`: the text of `dev/bin/release-checks` contains the line `SKIP_ALLOWED=2`.
  - `test_skip_ceiling_fails_the_gate_above_three` (`skills/run-autopilot/cli/test_release_checks_counts.py:305-328`) is renamed `test_skip_ceiling_fails_the_gate_above_the_ceiling`, its stub reports `1 passed, 3 skipped`, its docstring names the ceiling of 2, and its last assertion checks the ceiling message alone (`exceeds the ceiling` in the output), dropping today's either-or hedge; it fails against the current ceiling and passes after.
- CHANGELOG `[Unreleased]`: the **work** line from (2); a Changed line under **run-autopilot**: `**run-autopilot**: the release gate counts a shell harness's SKIP: lines toward the skip ceiling, now 2 (the two AUTOPILOT_LIVE tests); the golden engram baseline test that skipped on every machine is gone`; an Added line under **release**: `**release**: dev/bin/release runs the live MCP launch test (AUTOPILOT_LIVE=1) after the block checks and before it touches the central claude-plugins repo, and refuses the release when it fails`.

### Nice to have
- None.

## Implementation

### Module: release-script
- **Location**: `dev/bin/release`
- **Responsibility**: run the live MCP test before touching the central repo
- **Exports**: none

### Module: release-checks
- **Location**: `dev/bin/release-checks` (`run_harness`, `SKIP_ALLOWED`), `skills/work/scripts/test_check_build_overhead.py`
- **Responsibility**: count harness skips, lower the ceiling, drop the dead test
- **Exports**: none

### Module: release-notes
- **Location**: `CHANGELOG.md`
- **Responsibility**: the three missing lines
- **Exports**: none

### Module: release-truth-tests
- **Location**: `skills/run-autopilot/cli/test_release_checks_counts.py`
- **Responsibility**: pin the live-test ordering, the harness skip count and the ceiling
- **Exports**: none
- New symbols: `test_release_runs_the_live_mcp_test_before_the_central_repo_check`, `test_harness_skip_lines_count_toward_the_ceiling`, `test_skip_ceiling_is_two`, `test_skip_ceiling_fails_the_gate_above_the_ceiling`

### Dependencies
- release-truth-tests: No dependencies (foundation)
- release-script: Depends on [release-truth-tests]
- release-checks: Depends on [release-truth-tests]
- release-notes: Depends on [release-checks]

## Tasks

### Phase 0: Foundation
- [ ] Add the three tests and the rename to `skills/run-autopilot/cli/test_release_checks_counts.py`. Premise: `rg -c "SKIP_ALLOWED=3" dev/bin/release-checks` prints 1 and `rg -c "golden baseline" skills/work/scripts/test_check_build_overhead.py` prints 2 before the edit; a different count means the gate already changed and the task stops and reports. - Acceptance: `uv run --no-project --with pytest python -m pytest -q skills/run-autopilot/cli/test_release_checks_counts.py -k "live_mcp or skip_lines or ceiling"` fails `test_release_runs_the_live_mcp_test_before_the_central_repo_check`, `test_harness_skip_lines_count_toward_the_ceiling`, `test_skip_ceiling_is_two` and `test_skip_ceiling_fails_the_gate_above_the_ceiling` against the current scripts and reports no other failure.

### Phase 1: Core
- [ ] Make the four edits and add the three CHANGELOG lines (depends on: Phase 0) - Acceptance: `uv run --no-project --with pytest python -m pytest -q skills/run-autopilot/cli/test_release_checks_counts.py` passes; `rg -c "SKIP_ALLOWED=2" dev/bin/release-checks` prints 1; `rg -c "golden baseline" skills/work/scripts/test_check_build_overhead.py` prints 0; `rg -c "test_launch_mcp_live" dev/bin/release` prints 1; `rg -n "closes Ivan, Tess and Pat rows|SKIP: lines toward|live MCP launch test" CHANGELOG.md` prints three lines under `[Unreleased]`.

## Success Criteria

- The four new or renamed tests pass and every other test in the file passes unchanged.
- The gate script, run by a non-root user, ends FAIL 0 SKIP 2 EXIT 0 (the codex harness adds one more skip only when run as root).
- Post-release signal: the next `dev/bin/release` prints `[release] live MCP launch test` before `[release] pulling latest claude-plugins`.
