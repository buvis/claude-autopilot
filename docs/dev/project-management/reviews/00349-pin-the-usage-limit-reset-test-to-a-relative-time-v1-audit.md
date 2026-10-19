# Decision Audit Log: 00349-pin-the-usage-limit-reset-test-to-a-relative-time-v1

PRD: `00349-pin-the-usage-limit-reset-test-to-a-relative-time-v1.md`
Started: 2026-10-19T07:42:30Z
Completed: 2026-10-19T07:42:30Z
Autonomous: 3  |  Deferred: 0  |  Doubts: 0

### [autonomous] 2026-10-19T07:42:30Z

**Decision**: PRD 00349's task premise and acceptance miscount rg -c "8:10pm" (said 5 before / 4 after; measured 6 before at c19e8f8e~1 and 5 now)

**Choice**: swept as a tail-sweep fix: correct both counts in the wip PRD's task line

**Rationale**: cycle 1: verified by direct measurement; the code matches the Solution verbatim and 19 tests pass, so only the PRD record is wrong

### [autonomous] 2026-10-19T07:42:30Z

**Decision**: R2 replay row plus DST residual on test_limit_stuck_returns_next_reset_epoch; R3-R6 single-voice rows

**Choice**: discarded, ledgered in 00349-...-ledger.json

**Rationale**: cycle 1: R2 is a computed replay row the PRD's mandated test form explains; R3-R6 are [1/4] single-voice rows, two of them scoped to 81c0f2b4 rather than this PRD

### [autonomous] 2026-10-19T07:42:30Z

**Decision**: PRD acceptance count is wrong, not the code: `rg -c "8:10pm" skills/run-autopilot/scripts/test_detect_usage_limit.py` prints 5 after the exact edit, and printed 6 before it (measured at c19e8f8e~1). PRD 00349's Phase 0 task line claims 5 before and 4 after, so its literal premise and acceptance can never both hold. Fix: in docs/dev/project-management/prds/wip/00349-pin-the-usage-limit-reset-test-to-a-relative-time-v1.md, change the task line's premise count from 5 to 6 and its acceptance count from 4 to 5; leave the `def test_` count at 19 and change no test code.

**Choice**: auto-fixed

**Rationale**: fixed by review-close
