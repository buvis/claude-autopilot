---
prd: docs/dev/project-management/prds/wip/00326-close-the-loops-remaining-verb-and-ledger-truths-v2.md
review: 1
date: 2026-10-17
head_sha: 61029a3ec5dad8a6fa46c656d674957f53e4f8e9
codex_thread_id: 01a1495d-19df-7d53-bd9b-903d381d327d
reviewers: alice,blake,bob,carl
agents:
  alice: available
  blake: available
  bob: available
  carl: available
dispatch_rows:
  bob: 65af91d8
  carl: d07287f5
---

# Review: 00326-close-the-loops-remaining-verb-and-ledger-truths-v2

Diff range: `6d7c97f3124819a33aa3dc2b499cfd89f1621a58..61029a3ec5dad8a6fa46c656d674957f53e4f8e9`

codex_rung_guard: not fired

pack: ok

## Review Summary

Four lenses ran: Alice (consensus), Blake (blind, PRD-only), Bob (codex doubt + de-slop,
after one retry (inlined)), Carl (gemini). 21 consolidated findings, two of them 🟠 High.
Bob's first dispatch returned the sandbox lack-of-input refusal (exit 0, `sandbox_apply:
Operation not permitted`); the inlined retry prompt produced a full review. Bob's issue
lines arrive with a `- ` list prefix that `consolidate_findings.py`'s `^\[` anchor drops,
so a prefix-normalized copy of his output (`bob-output-00326-c1-normalized.txt`) was the
consolidation input — the text is otherwise byte-identical.

### Agent Status

- alice: available
- blake: available
- bob: available (after one retry (inlined))
- carl: available (backend: copilot)

## Consolidated Findings

| Ref | Consensus | Severity | Issue | File | Task | Found By |
|-----|-----------|----------|-------|------|------|----------|
| R1 | [3/4] | 🟠 | `qualifies` excludes every non-stall row whose `action` starts with "fix in cycle". The PRD narrows this to `review-critical` rows. A `cap-overflow` or other open CRITICAL/HIGH row carrying such an action would be silently dropped and never minted. The test only checks a `cap-overflow` row with no action, so it cannot catch the over-broad match. Gate on `row.get("type") == "review-critical"`, and add a `cap-overflow` plus "fix in cycle" case to the test. | skills/run-autopilot/cli/triage.py:166 | 3 | ALICE, BLAKE, BOB |
| R2 | [3/4] | 🟡 | lane-dispatch.md says "the lane writes that file at item start", but no lane step writes `docs/dev/tmp/fast-track-started`. skills/fast-track/SKILL.md:634 still tells the session to pass `--started <epoch seconds of the first dispatch>`. The new fallback is therefore unreachable in practice, and the prose states something the lane does not do. Add the write step to the lane prose, or reword lane-dispatch.md to say the file is optional and operator-written. | skills/fast-track/references/lane-dispatch.md:292 | 3 | ALICE, BLAKE, BOB |
| R3 | [3/4] | 🟡 | `_dispatch` hand-parses `get` with `_parse_get_args`, where the PRD says "parses `get` with argparse". Extra positionals are silently dropped, and a repeated `--default` silently takes the last value. Use argparse (exit 1 on usage error) or reject the extras explicitly. | skills/run-autopilot/scripts/statectl.py:139 | 2 | ALICE, BLAKE, BOB |
| R4 | [2/4] | 🟡 | The new `get --default` tests are looser than the PRD. The malformed-path and trailing-`--default` tests assert only `returncode != 0` (the PRD says exit 1 with the usage text). `test_get_default_never_masks_a_present_key` uses a different shape from the PRD's `batch.id --default null`. No test covers a falsy but present value (0, null, false) staying unmasked. Assert `== 1` and a "usage" substring, and add a falsy-value case. | skills/run-autopilot/scripts/test_statectl_decide.py:156 | 1 | ALICE, BOB |
| R5 | [2/4] | 🟡 | Mechanical facts report `_run_loop` at 51 lines, exceeding the 50-line limit. Remove the redundant blank line between launch and decision without changing control flow. | skills/run-autopilot/cli/loop.py:732 | 3 | BOB, CARL |
| R6 | [1/4] | 🟠 | A git timeout or launch error sets `toplevel = None`, enabling an unrestricted ancestor walk. From a nested repository, `markers --clear` can consequently clear the parent store. Refuse automatic resolution after these errors and require `--state`; add a timeout regression test. | skills/run-autopilot/cli/__main__.py:1935 | 2 | BOB |
| R7 | [1/4] | 🟡 | Unrelated formatter reflow is mixed into the diff (import blocks, `__all__` order, signatures, call sites and asserts rewrapped). It touches loop.py:48, loop.py:91, loop.py:444, loop.py:583, loop.py:627, loop.py:654, loop.py:669, loop.py:699, test_triage.py (about 15 hunks), test_discovery.py (about 17 hunks), test_doc_contract.py:167, test_markers.py:44, test_selection.py:104, test_record_item.py:54. None of it traces to the PRD, and it buries the real change in a roughly 680-line diff. Revert the reflow hunks and keep only the seven fixes. | skills/run-autopilot/cli/loop.py:48 | general | ALICE |
| R8 | [1/4] | 🟡 | `--started` bounds are under-tested. The future-timestamp refusal is a PRD must-have (">24h before ts_end or in the future") but has no test. Only the year-old case is covered. Nothing covers the new "--started omitted and the started file missing or malformed, exit 2" branch, or an out-of-bound value read from the started file. | skills/fast-track/scripts/test_record_item.py:747 | 3 | ALICE |
| R9 | [1/4] | 🟡 | `_find_autopilot_dir_in_repo` copies the body of `_walk_up.find_autopilot_dir` (the resolve, walk and OSError handling) just to add a stop directory. It sits in `__main__.py`, already 2030 lines. Add an optional `stop` parameter to `_walk_up.find_autopilot_dir`, or put the helper in `markers.py`, and delete the 33-line copy. | skills/run-autopilot/cli/__main__.py:1916 | 2 | ALICE |
| R10 | [1/4] | 🟡 | The toplevel guard fails open. If `git rev-parse --show-toplevel` times out, raises OSError or is missing, `toplevel` becomes None and the walk climbs to the filesystem root with no message. That is exactly the cross-repository clearing the fix is meant to prevent. Fail loud in the error cases (timeout, OSError) and allow an unbounded walk only when git reports "not a repository". | skills/run-autopilot/cli/__main__.py:1927 | 2 | ALICE |
| R11 | [1/4] | 🟡 | `_read_started_file()` does not catch `UnicodeDecodeError`. A non-UTF-8 started file produces a traceback instead of the controlled exit-2 diagnostic. Handle decoding errors alongside read failures and test invalid bytes. | skills/fast-track/scripts/record_item.py:76 | 3 | BOB |
| R12 | [1/4] | 🟡 | Timestamp tests cover a year-old value and a valid fallback, but omit future timestamps, the exact 24-hour boundary, and diagnostics naming the rejected value. Add these cases with a fixed clock. | skills/fast-track/scripts/test_record_item.py:747 | 1 | BOB |
| R13 | [1/4] | 🟡 | skills/run-autopilot/cli/test_routing.py exceeds the 800-line limit at 804 lines | skills/run-autopilot/cli/test_routing.py:804 | 3 | CARL |
| R14 | [1/4] | 🟡 | Replace custom 23-line while-loop in _parse_get_args with argparse.ArgumentParser to enforce argument validation and simplify dispatch | skills/run-autopilot/scripts/statectl.py:139 | 2 | CARL |
| R15 | [1/4] | ⚪ | The PRD's fallback case, where `launched_prd` is empty on a bootstrap session and `prd` falls back to the decision's PRD, has no test. The `launched_prd: str = ""` default also lets a future caller omit the argument silently. test_routing.py already calls `_append_metrics` without it. Make the argument required, or test the fallback. | skills/run-autopilot/cli/loop.py:176 | 3 | ALICE |
| R16 | [1/4] | ⚪ | test_selection.py:86 embeds a raw, invisible U+2028 character in the string literal, while the NEL case on line 85 uses an escape. Write it as an escape so a reader or editor sees which case the test pins. The new test comments also still describe pre-fix behavior ("currently slip through", "no --state flag today", "has no STARTED_FILE ... today") and name the removed `_has_control_char`. Reword them as the rule being enforced. | skills/run-autopilot/cli/test_selection.py:86 | 1 | ALICE |
| R17 | [1/4] | ⚪ | The diff adds code to files already past the 800-line cap: `__main__.py` is 2030 lines and test_discovery.py is 1703. test_record_item.py is at 799 and test_loop_budget.py is edited. All except test_record_item.py were over the cap before this diff, but the diff adds to them. | skills/run-autopilot/cli/__main__.py:1951 | general | ALICE |
| R18 | [1/4] | ⚪ | `_find_autopilot_dir_in_repo` falls back to an unbounded walk to the filesystem root when `git rev-parse --show-toplevel` fails (cwd outside a repo, git missing or timed out). The cross-store clear the PRD fixes can still occur in that case, and `markers --clear` is destructive. | skills/run-autopilot/cli/__main__.py:1924 | 3 | BLAKE |
| R19 | [1/4] | ⚪ | `markers --state` takes `Path(args.state).resolve().parent` as the store without checking that it exists or is an autopilot dir. A typo'd path makes `--check` report all markers false and `--clear` a silent no-op, and the output names the bogus store. | skills/run-autopilot/cli/__main__.py:1953 | 3 | BLAKE |
| R20 | [1/4] | ⚪ | `cli/__main__.py` and `scripts/tracon/test_discovery.py` already exceed the 800-line limit. Splitting these existing modules is outside this PRD's seven targeted fixes. | skills/run-autopilot/cli/__main__.py:2023 | general | BOB |
| R21 | [1/4] | ⚪ | Backlog PRD 00342 modified with unrequested notes and grammar additions outside PRD 00326 scope | docs/dev/project-management/prds/backlog/00342-task-done-refuses-an-undefined-attempt-stamp-v1.md:9 | general | CARL |
| R22 | [1/4] | 🟡 | [MECH] 1 touched test(s) pass against the pre-change code: test_state_schema_cli_rows_match_the_parsers | skills/run-autopilot/cli/test_doc_contract.py | general | mech-check |
| R23 | [1/4] | 🟡 | [MECH] 2 touched test(s) pass against the pre-change code: test_check_reports_absent_as_false, test_check_reports_present_as_true | skills/run-autopilot/cli/test_markers.py | general | mech-check |
| R24 | [1/4] | 🟡 | [MECH] 1 touched test(s) pass against the pre-change code: test_newline_named_backlog_file_is_not_selectable | skills/run-autopilot/cli/test_selection.py | general | mech-check |
| R25 | [1/4] | 🟡 | [MECH] 21 touched test(s) pass against the pre-change code: test_severity_is_matched_case_insensitively, test_key_in_first_20_lines_of_any_lifecycle_dir_claims_ownership, test_key_past_line_20_does_not_claim +15 more | skills/run-autopilot/cli/test_triage.py | general | mech-check |
| R26 | [1/4] | 🟡 | [MECH] 14 touched test(s) pass against the pre-change code: test_exact_slack_boundary_is_not_in_flight, test_loop_status_end_to_end_populates_row_cells_from_current_batch, test_missing_registry_returns_home_claude_when_autopilot_dir_present +11 more | skills/run-autopilot/scripts/tracon/test_discovery.py | general | mech-check |

No tautological-test shapes were reported by `detect_tautological_tests.py`.

## Alice

Eleven findings, listed above as R1-R4, R7-R10, R15-R17 (consensus lens, implementation-aware).

R1: fail
R2: pass
R3: pass
R4: pass
R6: pass
R7: pass
R8: pass
R9: fail
R10: fail
R11: pass
R12: pass
R13: fail

## Blake

Five findings (R1, R2, R3, R18, R19). Blind lens; he confirmed truths 1, 4, 5, 6 and the
CHANGELOG entries by reading the code himself, and ran the seven phase-0 test files
(143 passed, 0 failed).

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

Doubt + de-slop lens, after one retry (inlined). FIX: R1, R3, R4, R5, R6, R11, R12.
VERIFY: the fast-track started-file write step (no exact runnable command, so not queued).
KNOWN: R20 (pre-existing 800-line files, out of scope).

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
R12: fail
R13: fail

D1: pass
D2: pass
D3: pass
D4: pass
D5: pass

## Carl

Four findings (R5, R13, R14, R21). Backend: copilot. No frontend surface in this diff.

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
R12: fail
R13: fail

Verdict: 26 findings
Tests: 7124 passed, 0 failed, 3 skipped (reused from last-verification.json at 288417c; the two commits since it touch only autopilot ledger jsonl files, no code)
