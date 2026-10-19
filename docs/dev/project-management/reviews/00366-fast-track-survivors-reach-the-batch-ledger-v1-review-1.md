---
head_sha: ad7ba6030ff2d914be9e1d77866f65254f05116d
reviewers: alice, blake, eve, bob, carl
---

## Alice

**00366-fast-track-survivors-reach-the-batch-ledger-v1-c1**
- CRITICAL - the `ledger-rows` verb was missing: `_parser`/`_main` carried no subcommand and `ledger_rows` took no `lenses` argument; SKILL.md told the lane to call `record_defer`, a Python function the lane cannot invoke from bash - skills/fast-track/scripts/fast_track_plan.py:71 - FIXED in db8e8f8e.
- CRITICAL - the SKILL.md paragraph was neither the PRD's verbatim text nor in the required place (after the Verify sentence ending "anything but that array."), and dropped the `_AUTOPILOT_LOOP` gate, the `--lenses` count, the `autopilot defer` call and the outside-loop branch - skills/fast-track/SKILL.md:646 - FIXED in db8e8f8e.
- CRITICAL - `ledger_rows` returned raw `asdict(Finding)` instead of the PRD's `review-deferral` row (lowercase severity, `issue`/`reason`/`consensus`, suffix-stripped file) and did not fold by (severity, stripped file) - skills/fast-track/scripts/fast_track_plan.py:73 - FIXED in db8e8f8e.
- HIGH - the prose test pinned only the literal sentence and never asserted `ledger-rows` or `autopilot defer` appear in SKILL.md - skills/fast-track/scripts/test_fast_track_prose.py:843 - FIXED in db8e8f8e.
- HIGH - the PRD's four named plan tests were missing, leaving the fold, the CLI verb and the exit-2 path untested - skills/fast-track/scripts/test_fast_track_plan.py:648 - FIXED in db8e8f8e.
- MEDIUM - the CHANGELOG entry claimed survivors reach the batch deferred ledger before the code did - CHANGELOG.md:21 - deferred to the batch ledger.
- MEDIUM - test_fast_track_prose.py was already over the 800-line limit and this diff takes it to 885 - skills/fast-track/scripts/test_fast_track_prose.py:843 - deferred to the batch ledger.

## Blake

**00366-fast-track-survivors-reach-the-batch-ledger-v1-c1**
- MEDIUM - test_ledger_rows_rows_match_record_defer_item_shape checks a contract that does not exist and repeats another test - skills/fast-track/scripts/test_fast_track_plan.py:688 - deferred to the batch ledger.
- MEDIUM - the Phase 0 premise and its fail-first acceptance cannot be shown for the tests the spec specifies - skills/fast-track/scripts/test_fast_track_plan.py - deferred to the batch ledger.
- LOW - the deferred objects carry no `op_id`, so `record_defer` appends on every call and a retried exit step would duplicate survivors - skills/run-autopilot/cli/records.py:138 - deferred to the batch ledger.

## Eve

**00366-fast-track-survivors-reach-the-batch-ledger-v1-c1**
- CRITICAL - even with rows in the ledger, `_deferred_to_batch_end` reads `issue`/`severity`/`reason`, which the emitted rows lacked, so the Deferred table would render blank and `render report` would exit 12 - skills/fast-track/scripts/fast_track_plan.py:73 - FIXED in db8e8f8e.
- MEDIUM - `ledger_rows` hardcodes the literal tuple ("MEDIUM", "LOW") instead of reusing the existing `_BLOCKING` constant, two independent literals that can drift - skills/fast-track/scripts/fast_track_plan.py:84 - the one survivor of the delta pass; deferred to the batch ledger.

## Bob

**00366-fast-track-survivors-reach-the-batch-ledger-v1-c1**
- LOW - cannot statically verify that the pytest gate passes (static-only sandbox) - N/A - deferred to the batch ledger.

## Carl

**00366-fast-track-survivors-reach-the-batch-ledger-v1-c1**
- CRITICAL - no CLI interface for `ledger-rows` in `_parser()`/`_main()` - skills/fast-track/scripts/fast_track_plan.py:112 - same defect as Alice's first row; FIXED in db8e8f8e.
- HIGH - `ledger_rows()` took no `lenses`, did not fold, did not compute consensus and emitted raw Finding dicts - skills/fast-track/scripts/fast_track_plan.py:71 - FIXED in db8e8f8e.
- HIGH - SKILL.md specified Python-level calls instead of the CLI invocations under `_AUTOPILOT_LOOP` - skills/fast-track/SKILL.md:646 - FIXED in db8e8f8e.
- HIGH - the four PRD-specified unit tests were not implemented - skills/fast-track/scripts/test_fast_track_plan.py:648 - FIXED in db8e8f8e.
- MEDIUM - the prose test did not assert `ledger-rows` and `autopilot defer` appear in SKILL.md - skills/fast-track/scripts/test_fast_track_prose.py:843 - FIXED in db8e8f8e.
- MEDIUM - test_fast_track_prose.py is 885 lines, over the 800-line limit - skills/fast-track/scripts/test_fast_track_prose.py:843 - deferred to the batch ledger (same row as Alice's).

Verdict: converged
Tests: 7207 passed, 0 failed, 2 skipped (fast-track batch suite)
codex_rung_guard: not fired
