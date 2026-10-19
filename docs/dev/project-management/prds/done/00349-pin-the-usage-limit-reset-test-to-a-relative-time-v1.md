---
design: skip
default_model: sonnet
model_tier_rationale: one test rewritten with its exact lines given, no production code, no other test touched
---

# Pin the usage-limit reset test to a relative time

Source: batch 202610161547, PRD 00347's fast-track card, 2026-10-17 20:1x CEST. The card passed both gates and a clean four-lens review, then the item's batch suite returned `PASS 7189 FAIL 1 SKIP 3 EXIT 1` with the one failure in `skills/run-autopilot/scripts/test_detect_usage_limit.py::DetectUsageLimitTests::test_limit_stuck_returns_next_reset_epoch`, a file the card never touched, so the lane parked the PRD (`fast_track_blocked`) with its commits already on master and a human had to un-park it. The same file passed 19 of 19 at 09:04 the next morning.

## Problem

`test_limit_stuck_returns_next_reset_epoch` (`skills/run-autopilot/scripts/test_detect_usage_limit.py:96-116`) writes a banner that always says `resets 8:10pm (Europe/Prague)` for an error stamped five minutes before the run, and expects the next 20:10 after that error. `_reset_epoch` (`skills/run-autopilot/cli/usage_limit.py:97-127`) computes the same candidate from the error's timestamp, then returns `None` once the wall clock is past it by more than `GRACE_SECS` (`skills/run-autopilot/cli/usage_limit.py:42`, 120 s), because a reset that already passed is a stale record. A run between 20:12 and 20:15 Europe/Prague therefore puts the error before 20:10 and the clock more than two minutes after it: the helper answers `None`, the test's `assertIsNotNone` fails, and every suite that runs in that window is red for three minutes a day. `test_expired_limit_record_is_not_limited` (`skills/run-autopilot/scripts/test_detect_usage_limit.py:174-184`) already shows the clock-free form: it derives the banner's time from the error time with `strftime("%I:%M%p")`.

## Solution

The test derives its banner from the error time the way the expired-record test does, so the reset is always about three hours ahead of both the error and the clock. In `test_limit_stuck_returns_next_reset_epoch`, after the `err_at` line, add `reset_at = (err_at + timedelta(hours=3)).astimezone(ZoneInfo("Europe/Prague"))` and `hour12 = reset_at.strftime("%I:%M%p").lower().lstrip("0")`; the `_limit_entry` text becomes `f"You've hit your session limit · resets {hour12} (Europe/Prague)"`; the expectation block (the `tz`, `anchor` and `expected` lines and the `if expected <= anchor` roll-over) becomes the single line `expected = reset_at.replace(second=0, microsecond=0)`, followed by the unchanged `self.assertEqual(epoch, int(expected.timestamp()))`. Nothing in the helper module changes.

## Requirements

### Must have
- The rewritten test exactly as above, the other 18 tests in the file untouched.
- No CHANGELOG entry: the change is test-only (`test` commit type).

### Nice to have
- None.

## Implementation

### Module: usage-limit-test
- **Location**: `skills/run-autopilot/scripts/test_detect_usage_limit.py` (`test_limit_stuck_returns_next_reset_epoch`)
- **Responsibility**: the limit-stuck case passes at any time of day
- **Exports**: none

### Dependencies
- usage-limit-test: No dependencies (foundation)

## Tasks

### Phase 0: Foundation
- [ ] Rewrite `test_limit_stuck_returns_next_reset_epoch` in `skills/run-autopilot/scripts/test_detect_usage_limit.py` as the Solution says. Premise: `rg -c "8:10pm" skills/run-autopilot/scripts/test_detect_usage_limit.py` prints 6 before the edit; a different count means the file already changed and the task stops and reports. - Acceptance: `uv run --no-project --with pytest python -m pytest -q skills/run-autopilot/scripts/test_detect_usage_limit.py` passes 19 tests; `rg -c "8:10pm" skills/run-autopilot/scripts/test_detect_usage_limit.py` prints 5; `rg -c "def test_" skills/run-autopilot/scripts/test_detect_usage_limit.py` prints 19.

## Success Criteria

- The file passes at any wall-clock time; the registration at `dev/bin/release-checks:456` is unchanged.
- Post-release signal: no fast-track item parks on `test_limit_stuck_returns_next_reset_epoch` again, whatever the hour its batch suite runs.
