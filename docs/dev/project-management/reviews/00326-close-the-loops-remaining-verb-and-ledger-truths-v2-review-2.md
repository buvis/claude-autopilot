---
prd: docs/dev/project-management/prds/wip/00326-close-the-loops-remaining-verb-and-ledger-truths-v2.md
review: 2
date: 2026-10-17
head_sha: a72e274fbcd86bf34df0eb137eabcec69b052b26
codex_thread_id: 01a1499a-4963-7733-99b6-5c5b9e9d9cbd
reviewers: alice,blake,bob,carl
agents:
  alice: available
  blake: available
  bob: available
  carl: available
dispatch_rows:
  bob: b914313c,26b61dea
  carl: 687941f6
---

# Review: 00326-close-the-loops-remaining-verb-and-ledger-truths-v2

Diff range: `61029a3ec5dad8a6fa46c656d674957f53e4f8e9..a72e274fbcd86bf34df0eb137eabcec69b052b26`

codex_rung_guard: not fired

pack: ok

## Review Summary

Incremental cycle-2 review of the cycle-1 rework (tasks 5-8). Four lenses ran: Alice
(consensus), Blake (blind, PRD-only), Bob (codex doubt + de-slop, after one retry
(inlined)), Carl (gemini). 18 consolidated findings, one of them 🟠 High (R4).

Bob's first dispatch — launched with `--resume-thread` on his cycle-1 session — returned
the sandbox lack-of-input shape (exit 0, all R verdicts `fail`, a single ⚪ line asking for
the context, diff and pack to be inlined). The inlined retry prompt
(`bob-prompt-00326-c2-retry.md`, 186 KB, no `--resume-thread`) produced a full review; the
first row is closed `error / lack-of-input` and the retry row `ok / retry`.

Every cycle-1 finding except the git-toplevel family (R6/R10/R18) and `launched_prd`'s
default (R15) was verified fixed by Alice and by Blake independently. The git-failure path
is the one recurring theme: the rework stopped the unbounded walk but left the error path
fail-open and untidy, which is what R1, R2, R4, R6 and R7 below restate.

### Agent Status

- alice: available
- blake: available
- bob: available (after one retry (inlined))
- carl: available (backend: copilot)

## Consolidated Findings

| Ref | Consensus | Severity | Issue | File | Task | Found By |
|-----|-----------|----------|-------|------|------|----------|
| R1 | [2/4] | 🟡 | `_find_autopilot_dir_in_repo` lets `subprocess.TimeoutExpired` and `OSError` from `git rev-parse` escape uncaught, so `markers --check/--clear` dies with a traceback instead of a controlled refusal. Cycle 1 asked to "refuse automatic resolution and require `--state`". Replacement: catch `(OSError, subprocess.TimeoutExpired)` in `_run_markers`, print a message naming `--state`, and return 1. | skills/run-autopilot/cli/__main__.py:1925 | 5 | ALICE, BOB |
| R2 | [2/4] | 🟡 | Both new git-failure tests assert `raised or code != 0`, an either-or hedge. Any unrelated exception, such as an AttributeError from a later bug, satisfies it. Once finding 1 is fixed, assert `code == 1` and that stderr names `--state`. | skills/run-autopilot/cli/test_markers.py:845 | 5 | ALICE, BOB |
| R3 | [2/4] | 🟡 | The new lane-dispatch.md sentence "No lane step writes that file today" is time-relative prose. State the rule instead, for example "optional and operator-written". | skills/fast-track/references/lane-dispatch.md:294 | 8 | ALICE, BLAKE |
| R4 | [1/4] | 🟠 | Every nonzero Git result still enables an unrestricted ancestor walk, including failures caused by repository corruption or dubious ownership. An unrelated parent marker can therefore be cleared. Permit unbounded discovery only for an explicit "not a repository" result; refuse other failures. | skills/run-autopilot/cli/__main__.py:1931 | 5 | BOB |
| R5 | [1/4] | 🟡 | The CHANGELOG entry still says `docs/dev/tmp/fast-track-started` is "the epoch the lane writes at item start". The reworked lane-dispatch.md now says no lane step writes it and it is optional and operator-written. Reword the entry to match. | CHANGELOG.md:105 | 8 | ALICE |
| R6 | [1/4] | 🟡 | `markers` without `--state` runs `git rev-parse` with no guard for a missing git binary or a timeout, so either raises a traceback. When cwd is outside any git repo, `toplevel` stays None and the walk-up is unbounded again, which is the old cross-store behaviour. The spec only requires the stop at the toplevel, so this is a gap in the error path, not a spec failure. | skills/run-autopilot/cli/__main__.py:1925 | markers-state | BLAKE |
| R7 | [1/4] | 🟡 | test_clear_refuses_when_git_toplevel_lookup_times_out hedges with 'or': either outcome satisfies it (same shape in test_clear_refuses_when_git_toplevel_lookup_raises_oserror at :256) | skills/run-autopilot/cli/test_markers.py:226 | general | CARL, mech-check |
| R8 | [1/4] | ⚪ | The new `stop` parameter on `_walk_up.find_autopilot_dir` has no direct test in test_walk_up.py. It is covered only through the markers toplevel test. | skills/run-autopilot/scripts/_walk_up.py:53 | 5 | ALICE |
| R9 | [1/4] | ⚪ | `argparse.ArgumentParser(..., exit_on_error=True)` passes the default value, so the argument is redundant. | skills/run-autopilot/scripts/statectl.py:156 | 7 | ALICE |
| R10 | [1/4] | ⚪ | Omitting both `--started` and the started file exits 2. The module docstring still says "Every write is best-effort and exits 0" and shows `--started EPOCH` as mandatory. The no-autopilot-dir path returns 0 before any `--started` validation. | skills/fast-track/scripts/record_item.py:6 | ledger-truth | BLAKE |
| R11 | [1/4] | ⚪ | `get` parsing goes beyond the spec: it rejects a repeated `--default` through `_RejectRepeatedDefault`, and it rejects an extra positional. This is a small, defensible extra. A `--default` value that starts with `-` and is not a number, such as `--default -x`, is read by argparse as an option and gives a usage error. | skills/run-autopilot/scripts/statectl.py:139 | statectl-get | BLAKE |
| R12 | [1/4] | ⚪ | The `selectable()` docstring still says only "below U+0020, or U+007F" are excluded. It is stale now that line breaks and every Cc character are excluded. | skills/run-autopilot/cli/selection.py:61 | selection-names | BLAKE |
| R13 | [1/4] | ⚪ | The tracon test asserts `usage` and `root` as two separate substrings of stderr. It does not assert that the usage line itself names `root`, so a script printing "usage: x" plus an unrelated "root" would pass. It does fail the `root`-only script, as the PRD requires. | skills/run-autopilot/scripts/tracon/test_discovery.py:1700 | test-truth | BLAKE |
| R14 | [1/4] | 🟡 | [MECH] 6 touched test(s) pass against the pre-change code: test_a_future_started_value_is_refused_naming_it, test_started_exactly_24_hours_before_ts_end_is_accepted, test_started_one_second_past_the_24_hour_boundary_is_refused, test_started_omitted_and_started_file_missing_exits_two, test_started_omitted_and_started_file_malformed_exits_two, test_an_out_of_bound_value_read_from_the_started_file_is_refused | skills/fast-track/scripts/test_record_item_started_bounds.py | general | mech-check |
| R15 | [1/4] | 🟡 | [MECH] 1 touched test(s) pass against the pre-change code: test_review_once_with_no_prd_in_state_falls_back_to_the_decisions_prd | skills/run-autopilot/cli/test_loop_metrics.py | general | mech-check |
| R16 | [1/4] | 🟡 | [MECH] 3 touched test(s) pass against the pre-change code: test_check_reports_absent_as_false, test_check_reports_present_as_true, test_clear_still_walks_unbounded_when_git_reports_not_a_repository | skills/run-autopilot/cli/test_markers.py | general | mech-check |
| R17 | [1/4] | 🟡 | [MECH] 1 touched test(s) pass against the pre-change code: test_c1_and_line_separator_names_are_not_selectable | skills/run-autopilot/cli/test_selection.py | general | mech-check |
| R18 | [1/4] | 🟡 | [MECH] 3 touched test(s) pass against the pre-change code: test_get_default_never_masks_a_present_key, test_get_present_falsy_value_is_not_masked_by_default, test_get_trailing_default_is_a_usage_error | skills/run-autopilot/scripts/test_statectl_decide.py | general | mech-check |

Two `[MECH]` tautological-shape lines (test_markers.py:226 and :256) were absorbed onto R7,
which already named the same tests; `mech-check` is appended to its finders. The five
`[MECH]` replay rows are R14-R18. No carry-forward: this PRD has no cycle-1
`checks-1.json` (Bob's cycle-1 VERIFY item named no runnable command, so nothing was
queued).

## Alice

Six findings (R1, R2, R5, R3, R8, R9). Consensus lens, implementation-aware. She
re-verified every cycle-1 finding against the code and ran 128 + 81 tests, all passing.
Resolved: R1, R2, R3, R4, R5, R8, R9, R11, R12, R14, R16, R19 of cycle 1. Partly resolved:
R6/R10/R18 (no unbounded walk now, but a raw traceback instead of a controlled refusal).
Unchanged by decision: R15 (`launched_prd: str = ""`), with a fallback test added and the
reason recorded in the assumptions file.

R1: pass
R2: pass
R3: pass
R4: pass
R6: pass
R7: pass
R8: pass
R9: pass
R10: pass
R11: pass
R12: pass
R13: pass

## Blake

Six findings (R3, R6, R10, R11, R12, R13). Blind lens, PRD-only: he located the code
himself, confirmed all seven truths and both CHANGELOG entries, and ran the PRD's phase-0
and phase-1 test files plus all of `skills/fast-track/scripts` (335 passed, 0 failed). He
did not run the tracon `test_discovery.py` file or the full gate. No Critical or High
defect found.

B1: pass
B2: pass
B3: pass
B4: pass
B5: pass
B6: pass
B7: pass
B8: pass
B9: pass
B10: pass
B11: pass
B12: pass
B13: pass
B14: pass
B15: pass
B16: pass
B17: pass
B18: pass
B19: pass

## Bob

Doubt + de-slop lens, after one retry (inlined). FIX: R4 (🟠), R1, R2. VERIFY: (none).
KNOWN: (none).

R1: fail
R2: fail
R3: pass
R4: pass
R6: pass
R7: fail
R8: pass
R9: fail
R10: fail
R11: pass
R12: pass
R13: fail

D1: pass
D2: pass
D3: pass
D4: pass
D5: pass

## Carl

Two findings (both the hedging git-failure tests, consolidated as R7). Backend: copilot.
No frontend surface in this diff.

R1: pass
R2: fail
R3: pass
R4: pass
R6: pass
R7: pass
R8: pass
R9: pass
R10: pass
R11: pass
R12: pass
R13: fail

Verdict: 18 findings
Tests: 7140 passed, 0 failed, 3 skipped (reused from last-verification.json at c360940)
