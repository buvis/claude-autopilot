---
design: skip
default_model: sonnet
model_tier_rationale: one default value and one prose number, two additive tests with the exact assertions given
---

# Give the drain agoge run two hours

Source: batch 202610161547 drained at 20:48 CEST on 2026-10-17 and the driver started its product-QA pass (`agoge: product QA over the drained batch`). The session spent 17 minutes on recon because the agoge profile was one whole batch stale (00320-00348), dispatched its lanes at 21:08, and was killed at 21:48 by the driver's wall-clock cap (`autoclaude: session exceeded the 3600s wall-clock cap; SIGTERM (session cap)`, rc 143). The log `reports/202610161547-agoge.log` is 0 bytes because agoge writes its report at the end, so an hour of claude time and six subagent dispatches produced nothing, and the batch of 2026-10-03 (`202610031511-agoge.log`, also 0 bytes) ended the same way. The runs that finished took 29 to 45 minutes (report to log mtimes of the 2026-10-10, 2026-10-11 and 2026-10-14 batches), so one hour is the normal duration plus nothing; a stale profile pushes it over.

## Problem

`run_agoge` (`skills/run-autopilot/cli/loop_act.py:75-114`) launches the QA session and `_run_agoge_process` (`skills/run-autopilot/cli/loop_act.py:48-72`) hands the cap to the `Watchdog` that terminates it.
The cap is read as `routing._env_int(env, "_AUTOPILOT_AGOGE_CAP", 3600)` (`skills/run-autopilot/cli/loop_act.py:103`).
The default is documented beside `_AUTOPILOT_AGOGE_CAP` as `(default 3600s)` in `skills/run-autopilot/SKILL.md:138`.
No test pins the default, so nothing fails when it changes.

## Solution

The default becomes 7200: `skills/run-autopilot/cli/loop_act.py:103` reads `cap = routing._env_int(env, "_AUTOPILOT_AGOGE_CAP", 7200)`.
The prose beside `_AUTOPILOT_AGOGE_CAP` in `skills/run-autopilot/SKILL.md:138` says `(default 7200s)`. The environment override is unchanged.
Two tests in `skills/run-autopilot/cli/test_loop_act.py`, beside `test_run_agoge_launches_authorized_and_logs` (`skills/run-autopilot/cli/test_loop_act.py:176-191`), replace `loop_act._run_agoge_process` with a recorder (`monkeypatch.setattr`, the recorder appends its `cap` argument to a list and returns 0) and call `run_agoge(tmp_path, "b-1", 2, env, out)` after `(tmp_path / "reports").mkdir()`: `test_run_agoge_default_cap_is_two_hours` with `env = {}` asserts the recorded cap is `7200`; `test_run_agoge_cap_env_overrides_the_default` with `env = {"_AUTOPILOT_AGOGE_CAP": "900"}` asserts `900`.

## Requirements

### Must have
- The default `7200` on the `_AUTOPILOT_AGOGE_CAP` line (`skills/run-autopilot/cli/loop_act.py:103`) and the SKILL.md number, nothing else in the function changed.
- The two tests above in `skills/run-autopilot/cli/test_loop_act.py` (registered at `dev/bin/release-checks:413`); `test_run_agoge_default_cap_is_two_hours` fails against the current default, `test_run_agoge_cap_env_overrides_the_default` passes before and after.
- A CHANGELOG `[Unreleased]` Changed entry under **run-autopilot**: the drained batch's agoge QA run gets two hours before the driver stops it (was one), since a profile one batch stale needs the first quarter hour for recon.

### Nice to have
- None.

## Implementation

### Module: agoge-cap
- **Location**: `skills/run-autopilot/cli/loop_act.py` (`run_agoge`)
- **Responsibility**: the default wall-clock cap of the drain's QA session
- **Exports**: `run_agoge()` (unchanged signature)

### Module: agoge-cap-tests
- **Location**: `skills/run-autopilot/cli/test_loop_act.py`
- **Responsibility**: pin the default and the override
- **Exports**: none
- New symbols: `test_run_agoge_default_cap_is_two_hours`, `test_run_agoge_cap_env_overrides_the_default`

### Module: skill-prose
- **Location**: `skills/run-autopilot/SKILL.md` (Product QA bullet)
- **Responsibility**: document the default the code uses
- **Exports**: none

### Dependencies
- agoge-cap: No dependencies (foundation)
- agoge-cap-tests: Depends on [agoge-cap]
- skill-prose: Depends on [agoge-cap]

## Tasks

### Phase 0: Foundation
- [ ] Add the two tests to `skills/run-autopilot/cli/test_loop_act.py`. Premise: `rg -c '"_AUTOPILOT_AGOGE_CAP", 3600' skills/run-autopilot/cli/loop_act.py` prints 1 before the edit; a different count means the default already changed and the task stops and reports. - Acceptance: `uv run --no-project --with pytest python -m pytest -q skills/run-autopilot/cli/test_loop_act.py -k "agoge_cap or agoge_default_cap"` fails `test_run_agoge_default_cap_is_two_hours` and passes `test_run_agoge_cap_env_overrides_the_default`.

### Phase 1: Core
- [ ] Change the default, the SKILL.md number and add the CHANGELOG entry (depends on: Phase 0) - Acceptance: `uv run --no-project --with pytest python -m pytest -q skills/run-autopilot/cli/test_loop_act.py` passes; `rg -c '"_AUTOPILOT_AGOGE_CAP", 7200' skills/run-autopilot/cli/loop_act.py` prints 1; `rg -c "default 7200s" skills/run-autopilot/SKILL.md` prints 1; `rg -n "run-autopilot.*agoge QA run" CHANGELOG.md` prints one line under `[Unreleased]`.

## Success Criteria

- Both new tests pass and the four existing `run_agoge` tests pass unchanged.
- Post-release signal: the next drained batch's `reports/<batch>-agoge.log` is non-empty and the wrapper prints `agoge: packets written` instead of `agoge: run failed (rc 143)`.
