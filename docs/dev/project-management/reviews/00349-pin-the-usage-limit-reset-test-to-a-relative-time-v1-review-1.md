---
prd: docs/dev/project-management/prds/wip/00349-pin-the-usage-limit-reset-test-to-a-relative-time-v1.md
review: 1
date: 2026-10-19
head_sha: 2dca8b5a4858cfdf0256c3d543928cee430f80ad
codex_thread_id: 01a1530c-7b4d-7bd1-b29f-d89962b57abc
reviewers: alice,blake,bob,carl
agents:
  alice: available
  blake: available
  bob: available
  carl: available
dispatch_rows:
  bob: a92b52b3
  carl: 7ff8ad33
---

# Review: 00349-pin-the-usage-limit-reset-test-to-a-relative-time-v1

Diff range: `cc6972572771c3d2f421b369b810fcc46ffbb8d2..2dca8b5a4858cfdf0256c3d543928cee430f80ad`

codex_rung_guard: not fired

## Review Summary

Reviewed: 1 completed task
PRDs checked: 00349-pin-the-usage-limit-reset-test-to-a-relative-time-v1

Lane: full (classified solo, `no_production_code`)
Consensus engine: legacy. Doubt reviewer: codex (Bob). Eve not activated.
pack: ok

### Agent Status

- Alice: ✅ Available
- Blake: ✅ Available
- Bob: ✅ Available (codex, exit 0)
- Carl: ✅ Available (gemini backend, exit 0)

## Consolidated Findings

| Ref | Consensus | Severity | Issue | File | Task | Found By |
|-----|-----------|----------|-------|------|------|----------|
| R1 | [2/4] | ⚪ | PRD acceptance count is wrong, not the code: `rg -c "8:10pm"` prints 5 after the exact edit (lines 10, 154, 201, 236, 274, including the module docstring at line 10). The PRD premise said 5 before and 4 after; measured counts are 6 before (`c19e8f8e~1`) and 5 now. The edit matches the Solution text verbatim and 19 tests pass. Correct the miscounted premise and acceptance; no code change needed. | skills/run-autopilot/scripts/test_detect_usage_limit.py:10 | 1 | ALICE, BLAKE |
| R2 | [3/4] | 🟡 | The "passes against pre-change code" replay row for `test_limit_stuck_returns_next_reset_epoch` is expected: the rewrite fixes a time-of-day flake, so the old test also passed outside the 20:12-20:15 Prague window. Residual: `err_at + timedelta(hours=3)` is absolute time while the helper uses wall-clock `replace` (`skills/run-autopilot/cli/usage_limit.py:120`), so a Prague DST transition inside the 3-hour offset could shift the expected hour. The PRD mandates this exact form. | skills/run-autopilot/scripts/test_detect_usage_limit.py:98 | 1 | ALICE, BLAKE, mech-check |
| R3 | [1/4] | 🟡 | F1: `_shipped_notes()` excludes v0.10.0 after the next release, making both prose tests fail again unless their historical wording is repeated. Pin the relevant release section and test a subsequent release rollover. | skills/review-work-completion/scripts/test_review_verbs_prose.py:142 | general | BOB |
| R4 | [1/4] | 🟡 | F2: The relative reset can fall in Prague's repeated autumn hour. Formatting only `%I:%M%p` loses `fold`, potentially making the parser return an epoch one hour earlier than expected. Verify this boundary before claiming all-clock-time reliability. (not queued: command shape - the stated check names no runnable command line) | skills/run-autopilot/scripts/test_detect_usage_limit.py:98 | 1 | BOB |
| R5 | [1/4] | ⚪ | The diff range also holds the `_shipped_notes` change in `test_review_verbs_prose.py`, which is outside PRD 00349, whose "other tests untouched" scope covers only the usage-limit file. It was committed separately as 81c0f2b4 and the 00327 close note documents it. It is correct: both tests read `[Unreleased]` plus the newest release section and pass. No action beyond keeping it out of 00349's attribution. | skills/review-work-completion/scripts/test_review_verbs_prose.py:136 | general | ALICE |
| R6 | [1/4] | 🟡 | 2 touched test(s) pass against the pre-change code: `test_changelog_states_what_review_close_refuses_truthfully`, `test_carry_creates_nothing_prose` - both from 81c0f2b4, outside this PRD's scope. | skills/review-work-completion/scripts/test_review_verbs_prose.py | general | mech-check |

Tautological test shapes: none (29 test functions checked in 2 files).
Fail-first replay: 3 touched tests ran, 0 failed against base - absorbed as R2 (merged) and R6.

## Alice

Three Low observations, no blocking findings; all twelve consensus rules pass.

- Low: the PRD's `rg -c "8:10pm"` acceptance count is wrong, not the code (R1).
- Low: the diff range also carries 81c0f2b4's `_shipped_notes` change, outside 00349's scope (R5).
- Low: the replay flags are expected for a time-of-day flake fix; residual DST edge noted (R2).

R1-R4, R6-R13: pass (12/12).

## Blake

Blind lens, PRD only. Three Low observations; all nineteen blind rules pass.

- Low: the rewrite matches the Solution line for line; 19 `def test_`, other 18 tests, helper module and `dev/bin/release-checks` untouched; no CHANGELOG entry, `test` commit type.
- Low: the task's literal `rg -c "8:10pm"` premise and acceptance cannot both hold; the PRD miscounted by one (R1).
- Low: the new test is time-of-day independent; the one edge is a DST transition inside the 3-hour offset (R2).

Blake did not rerun the suite (he read the cycle's `Tests:` line, as his brief directs).

B1-B19: pass (19/19).

## Bob

Doubt lens (codex, static-only sandbox), with de-slop.

- Medium: F1, `_shipped_notes()` release-window fragility (R3).
- Medium: F2, Prague repeated-hour / `fold` boundary (R4).

FIX:
- F1 - `skills/review-work-completion/scripts/test_review_verbs_prose.py:142` - select the release containing the required entries independently of its position; cover insertion of a newer release.

VERIFY:
- F2 - Freeze the clock at `2026-10-24T22:35:00Z` and run `test_limit_stuck_returns_next_reset_epoch`; confirm the parsed epoch equals `2026-10-25T01:30:00Z`, the second Prague 02:30.

KNOWN:
- (none)

R1: fail
R2: pass
R3: pass
R4: fail
R6: pass
R7: pass
R8: pass
R9: pass
R10: pass
R11: pass
R12: pass
R13: pass

D1: pass
D2: pass
D3: pass
D4: pass
D5: pass

Bob's R1/R4 fails are his two findings above, both scoped to code this PRD did not write (R3 targets 81c0f2b4's prose test) or to an edge the PRD's mandated form accepts (R4).

## Carl

`[CARL] ✅ No issues found`. He ran the task's acceptance commands and inspected both commits plus the helper module and CHANGELOG.

R1-R4, R6-R13: pass (12/12).

Verdict: 6 findings
Tests: 7195 passed, 0 failed, 2 skipped (reused from last-verification.json at 81c0f2b)
