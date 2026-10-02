---
prd: dev/local/prds/wip/00188-record-convergence-cap-and-roster-per-prd-v1.md
review: 1
date: 2026-09-14
head_sha: 7f51b0f71e5a9a1b6546065b0e27a5c86b286ac2
codex_thread_id: 01a09f08-236c-7170-9758-bf919331050e
reviewers: alice,blake,bob,carl
agents:
  alice: available
  blake: available
  bob: available
  carl: available
---

# Review: 00188-record-convergence-cap-and-roster-per-prd-v1

Diff range: `e718214d6375205895ad9a1b76b55ae54fe647d2..7f51b0f71e5a9a1b6546065b0e27a5c86b286ac2`

codex_rung_guard: not fired

pack: failed (`engram pack` exited 1 — "not inside a registered repo; register it in /Users/bob/.config/gita/repos.csv"; the registry lists 18 buvis repos and not this one, verified with a control search, so the error is deterministic and no retry was spent). `{PACK_FILE}` and `{PACK_FINDINGS}` were substituted with the literal `(no pack available this cycle)` in every prompt that takes them. The review is degraded by the missing retrieval context, not invalid.

scope note: cycle 1, full review of the PRD's whole work range (11 commits, 17 files, +1406/-30). `gather-context.sh` was run with `--since e718214…` (`state.work_start_sha`) because its default base is `master` and the batch works on `master`, so the bare form yields an empty diff (measured in the 00184 and 00187 cycles); the scope label in the context file therefore reads "incremental" although this is the full PRD range. Blake stayed blind: PRD and rubric only, no filesystem-notes block (`test -L dev/local` exits 1 and the root has no dot prefix). No design doc exists (`design: skip`).

bob note: codex ran this cycle (exit 0, first dispatch, thread `01a09f08-…` captured for the next cycle's `--resume-thread`); the `usage_limit_exceeded` block the 00187 cycles hit did not recur. His first two `cat`/`rg` calls were denied by the host's Fact-Forcing Gate hook and he retried past it; no `Cannot statically verify` lines, no lack-of-input shape, all twelve `R` lines and five `D` lines present, so no retry was spent.

verification queue: none written this cycle. Bob emitted seven FIX items and explicit `VERIFY: - (none)` / `KNOWN: - (none)`, so there is nothing to queue.

## Review Summary

Reviewed: 5 completed tasks
PRDs checked: 00188-record-convergence-cap-and-roster-per-prd-v1

### Agent Status

- Alice: ✅ Available (Claude subagent, sonnet; re-ran the cli suite (1007) and the prompt-contract suite (12) herself, both green, and the phase-review.md contract greps)
- Blake: ✅ Available (Claude subagent, sonnet, blind/PRD-only; ran the full cli + contract suites (1019 passed, 639 subtests) and `release-checks`, all green)
- Bob: ✅ Available (codex, exit 0, static analysis; doubt + de-slop lens)
- Carl: ✅ Available (gemini-run backend=copilot model=gemini-3.8-flash, exit 0, 2.4 KB output; ran the cli + contract suites and `release-checks` twice, once with the host dispatch markers unset)

## Consolidated Findings

9 findings: 10 rows from `consolidate_findings.py` (Bob's `File:` values carry `:line` suffixes, so the script's same-file paraphrase merge did not fire across reviewers) with two cross-reviewer duplicates merged by the orchestrator — Bob's High and Blake's Low on the uncaught `KeyError` (Bob names the call site `loop.py:961`, Blake the indexing site `convergence.py`) into one `[2/4]` row, and Bob's Medium and Alice's Low on the missing review→paused test into one `[2/4]` row — plus the fail-first replay's two `[MECH]` lines absorbed: one half of the second line (`test_convergence_is_keyword_only`) joins Bob's matching row as `mech-check`; the rest is discarded with a measured reason (Mechanical checks below). No 🔴 Critical; **two 🟠 High** (both Bob's, both confirmed by the orchestrator against the code); 5 🟡 Medium; 2 ⚪ Low. Bob's absolute `File:` line suffixes are kept as he wrote them.

Alice and Carl passed the implementation on every rubric rule; Blake passed all nineteen B rules and found one Low. The doubt lens carried the weight again: Bob's seven issue lines are where both Highs and four of the five Mediums come from.

| Consensus | Severity | Issue | File | Task | Found By |
|-----------|----------|-------|------|------|----------|
| [2/4] | 🟠 High | Convergence collection can abort the loop: absent identity keys raise KeyError, and schema-allowed non-dict deferrals raise AttributeError; neither reaches the existing exception handler. / convergence.build_row indexes state["prd"]/state["batch"]["id"] directly; a state dict missing those keys (not merely unreadable/non-dict) would raise KeyError uncaught by _append_metrics's except clause | skills/run-autopilot/cli/loop.py:961 | 2 | Bob, Blake |
| [1/4] | 🟠 High | Empty or garbage review files produce zero severity counts instead of null, contradicting the PRD and making unparseable reviews appear clean. | skills/run-autopilot/cli/convergence.py:64 | 1 | Bob |
| [1/4] | 🟡 Medium | Invalid UTF-8 in a review or PRD escapes _read_text and suppresses the entire convergence event instead of leaving only the unreadable fields null. | skills/run-autopilot/cli/convergence.py:34 | 1 | Bob |
| [2/4] | 🟡 Medium | No test asserts that review→paused emits no convergence event; the required exclusion remains unpinned. / No negative test for `phase_launched == "review"` exiting to `paused` (only `review`→`review` and `build`→`done` are tested), but the PRD's own must-have text names `paused` explicitly | skills/run-autopilot/cli/test_loop.py:860 | 2 | Bob, Alice |
| [1/4] | 🟡 Medium | test_convergence_is_keyword_only passes against the base implementation because an unsupported sixth argument also raises TypeError; it never establishes keyword acceptance. | skills/run-autopilot/cli/test_render_run_conditions.py:165 | 3 | Bob, mech-check |
| [1/4] | 🟡 Medium | CAP_DEFERRED_ROW and the null fixture unnecessarily parse concatenated JSON strings; ordinary dictionaries would expose their structure directly, matching SKEWED_ROW. | skills/run-autopilot/cli/test_render_run_conditions.py:38 | 3 | Bob |
| [1/4] | 🟡 Medium | The two negative loop tests duplicate state-writing closures already implemented by _state_step; reuse that helper with the same state fields. | skills/run-autopilot/cli/test_loop.py:861 | 2 | Bob |
| [1/4] | ⚪ Low | `_select_report_block`'s event-row match uses a `key` dict + `all(r.get(k) == v ...)` where the task text prescribed three direct field comparisons (already self-flagged as LOW by the work-phase's own de-slop pass); purely stylistic, behavior is correct and covers `event`+`prd`+`batch` | skills/run-autopilot/cli/__main__.py | 3 | Alice |
| [1/4] | 🟡 Medium | Fail-first replay: 2 touched test(s) pass against the pre-change code: test_review_exit_to_review_writes_no_convergence_row, test_build_exit_writes_no_convergence_row (discarded, reason below) | skills/run-autopilot/cli/test_loop.py | general | mech-check |

### Decision gate (Phase 5)

Cycle 1 < rework cap 2, two 🟠 High unresolved → not converged → rework. Every decision is in `state.autonomous_decisions` (10 entries); the two discards are in `00188-record-convergence-cap-and-roster-per-prd-v1-ledger.json`. No settled deferrals, no cap-overflow, no scope alarm (2 follow-up tasks), no recurring issue (cycle 1).

- **Auto-fix, reworked (8 findings → 2 `[D1]` tasks):** both Highs (the `KeyError` path verified: `schema.py:192-199` makes `batch`/`batch.id` optional and validates `deferred_decisions` as a bare list, `loop.py:750` tolerates a missing batch for the session row while `build_row` indexes it at `convergence.py:104-105`, so a `review-once` state from `autopilot init` would kill the driver at the finalize hand-off; the zeros-not-null path verified at `convergence.py:64-70`, where the PRD's "unparseable file yields null, never zeros" must-have loses to the work-phase assumption "no [n/m] rows yields a zero dict"), the UTF-8 Medium (`UnicodeDecodeError` is a `ValueError`, swallowed by `_append_metrics` only after the whole row is lost), the four test Mediums and the one Low. Both Highs are bounded input guards with no signature change and no new exception class, so they are auto-fix rather than deferral.
- **Discarded (2 replay rows, reasons in the ledger):** the two negative loop tests pass at base by design (the base emits no event rows; the positive pin fails there), and the replay's claim about `test_tasks_line_falls_back_to_the_event_row_when_record_reads_zero` is refuted by a manual base run (3 `SUBFAILED`, `TypeError: unexpected keyword argument 'convergence'`; the script misreads `unittest.subTest` failures as passes).

## Follow-up Tasks Created

Two `[D1]` tasks at tier `opus` (classifier default `sonnet` raised by the PRD's `default_model: opus` floor), covering 8 of the 9 findings; `state.rework_task_ids = ["6", "7"]`.

1. Task 6 — Make the review_converged append unable to escape `_append_metrics`: guard missing identity keys and non-dict deferrals, treat undecodable text as unreadable, read an unparseable review file as null (M) - 🟠 High - 3 findings
2. Task 7 — Test hygiene: pin the review-to-paused exclusion, make the keyword-only test prove acceptance, dict-literal fixtures, reuse `_state_step`, three direct comparisons in `_select_report_block` (S) - 🟡 Medium - 5 findings

## Alice

Consensus lens, Claude subagent (sonnet). She re-ran both suites herself (1007 + 12 passed, matching the work-phase record), traced `convergence.py`, `_append_metrics`/`_append_convergence`, `run_conditions_line`/`_tasks_line`/`prd_section` and `_select_report_block` against the PRD's verbatim contract (row shape, null-vs-zero, bare/padded review names, `outcome`, `build_models`/`attempt_tiers`, the task-count fallback chain, the byte-exact golden render), and confirmed the only callers of `prd_section` and `_select_report_block` were updated. 2 ⚪ Low.

```
[ALICE] ⚪ No negative test for `phase_launched == "review"` exiting to `paused` (only `review`→`review` and `build`→`done` are tested); functionally low-risk since the branch only distinguishes `phase_end == "done"` vs. anything else, which the existing `review`→`review` test already exercises, but the PRD's own must-have text names `paused` explicitly | File: skills/run-autopilot/cli/test_loop.py | Task: 2
[ALICE] ⚪ `_select_report_block`'s event-row match uses a `key` dict + `all(r.get(k) == v ...)` where the task text prescribed three direct field comparisons (already self-flagged as LOW by the work-phase's own de-slop pass); purely stylistic, behavior is correct and covers `event`+`prd`+`batch` | File: skills/run-autopilot/cli/__main__.py | Task: 3

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
```

## Blake

Blind lens, Claude subagent (sonnet), PRD and rubric only. He located the code himself, read all five modules, the three reference docs, CHANGELOG and every test file, ran the full cli + contract suites (1019 passed, 639 subtests) and `release-checks` (green), confirmed the diffstat touches exactly the PRD's named files with `gate.py` untouched, and checked the row's key order against the golden byte for byte. He found no functional gap and no scope creep; his one Low is the same `KeyError` path Bob rates High. 1 ⚪ Low.

```
[BLAKE] ⚪ convergence.build_row indexes state["prd"]/state["batch"]["id"] directly; a state dict missing those keys (not merely unreadable/non-dict) would raise KeyError uncaught by _append_metrics's except clause, though this matches pre-existing codebase convention (custody.py, records.py) and is not explicitly promised against by the spec | File: skills/run-autopilot/cli/convergence.py | Task: 1
[BLAKE] ✅ No other issues found

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
```

## Bob

Doubt + de-slop lens, codex (exit 0, static analysis in the read-only sandbox). 2 🟠 High, 5 🟡 Medium; seven FIX items, no VERIFY item, no KNOWN item. His R1/R2/R4/R7/R9/R10 fails map to the unpinned paused exit and the keyword-only test (R1, R2), the uncaught `KeyError` reaching the loop (R4, R10), the zeros-not-null review read (R9) and the unguarded state/deferral shapes (R7). The orchestrator confirmed both Highs against the code before routing them (Decision gate above).

```
[BOB] 🟠 Convergence collection can abort the loop: absent identity keys raise KeyError, and schema-allowed non-dict deferrals raise AttributeError; neither reaches the existing exception handler. | File: skills/run-autopilot/cli/loop.py:961 | Task: 2
[BOB] 🟠 Empty or garbage review files produce zero severity counts instead of null, contradicting the PRD and making unparseable reviews appear clean. | File: skills/run-autopilot/cli/convergence.py:64 | Task: 1
[BOB] 🟡 Invalid UTF-8 in a review or PRD escapes _read_text and suppresses the entire convergence event instead of leaving only the unreadable fields null. | File: skills/run-autopilot/cli/convergence.py:34 | Task: 1
[BOB] 🟡 No test asserts that review→paused emits no convergence event; the required exclusion remains unpinned. | File: skills/run-autopilot/cli/test_loop.py:860 | Task: 2
[BOB] 🟡 test_convergence_is_keyword_only passes against the base implementation because an unsupported sixth argument also raises TypeError; it never establishes keyword acceptance. | File: skills/run-autopilot/cli/test_render_run_conditions.py:165 | Task: 3
[BOB] 🟡 CAP_DEFERRED_ROW and the null fixture unnecessarily parse concatenated JSON strings; ordinary dictionaries would expose their structure directly, matching SKEWED_ROW. | File: skills/run-autopilot/cli/test_render_run_conditions.py:38 | Task: 3
[BOB] 🟡 The two negative loop tests duplicate state-writing closures already implemented by _state_step; reuse that helper with the same state fields. | File: skills/run-autopilot/cli/test_loop.py:861 | Task: 2

FIX:
- Uncaught convergence exceptions — skills/run-autopilot/cli/loop.py:961 — Guard missing identity fields before building; ignore non-dict deferrals. Add regressions proving collection cannot terminate the loop.
- Unparseable reviews appear clean — skills/run-autopilot/cli/convergence.py:64 — Detect invalid review content before initializing counts; return null metadata while retaining zeros for valid clean reviews.
- Decode errors discard the event — skills/run-autopilot/cli/convergence.py:34 — Handle UnicodeError locally as unreadable input; test that the event survives with null affected fields.
- Missing paused-exit coverage — skills/run-autopilot/cli/test_loop.py:860 — Add review→paused coverage asserting a session row and no event in both metrics files.
- Incomplete keyword-only proof — skills/run-autopilot/cli/test_render_run_conditions.py:165 — Assert successful rendering with convergence= before asserting positional rejection.
- Encoded test fixtures — skills/run-autopilot/cli/test_render_run_conditions.py:38 — Replace both inline JSON strings with equivalent dictionary literals and None values.
- Duplicate session closures — skills/run-autopilot/cli/test_loop.py:861 — Replace rework_review and finishing_build with equivalent _state_step calls, preserving assertions.
VERIFY:
- (none)
KNOWN:
- (none)

R1: fail
R2: fail
R3: pass
R4: fail
R6: pass
R7: fail
R8: pass
R9: fail
R10: fail
R11: pass
R12: pass
R13: pass
D1: pass
D2: pass
D3: pass
D4: pass
D5: pass
```

## Carl

Frontend & design specialist, generalist here (no UI surface). Backend `copilot`, model `gemini-3.8-flash`, exit 0, non-empty output (2.4 KB). He read the context and the diff, `gate.py`'s regexes, the `deferred_decisions` readers, `records.py`'s reset and `_append_metrics` in full, ran the cli + contract suites and `release-checks` (twice, once with the host dispatch markers unset) and searched the new code for debug markers. All twelve rules pass.

```
[CARL] ✅ No issues found

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
```

## Mechanical checks

- **Mechanical facts**: computed from `ast` over the 17 changed files (11 Python) and appended to the reviewer context. Every function this diff adds or touches is under 50 lines (`build_row` 44, `prd_section` 49, `_select_report_block` 49, the two long loop tests 49 each); the over-50 functions in `loop.py` (`_decide_no_progress` 94, `_act_park` 67, `_register` 52, `_decide` 52) are pre-existing and untouched. File counts by `wc -l`: `convergence.py` 144, `test_convergence.py` 547, `test_render_run_conditions.py` 194, `render_report.py` 689 (all under the cap); `loop.py` 1415, `test_loop.py` 1626 and `__main__.py` 1020 are pre-existing overflows deferred to PRD 00192 and the 00187 batch-end deferral, and no reviewer re-raised them. No reviewer contradicted the block, so nothing was discarded on that ground.
- **Tautological test shapes**: 179 test functions checked in 6 files, **0 `[MECH]` findings**.
- **Fail-first replay**: 19 touched tests ran against `e718214`; 15 failed at base, 4 reported as passing; `test_convergence.py` could not be collected at base (it imports `cli.convergence`, which does not exist there: fail-first evidence, not a gap). Of the 4: `test_review_exit_to_review_writes_no_convergence_row` and `test_build_exit_writes_no_convergence_row` pass at base by design (negative pins of the must-have "exits to review/build/paused write none"; discarded, ledgered); `test_convergence_is_keyword_only` genuinely passes at base (a six-positional call raises `TypeError` on the base signature too) and is reworked in task 7; `test_tasks_line_falls_back_to_the_event_row_when_record_reads_zero` is a **false positive of the replay script**: re-run by hand against a fresh base worktree it fails with 3 `SUBFAILED` (`TypeError: prd_section() got an unexpected keyword argument 'convergence'`), the same `unittest.subTest` misread first measured in the 00187 cycle-2 review (discarded, ledgered with the measurement).

Verdict: 9 findings

Tests: 1019 passed, 0 failed, 0 skipped (reused from last-verification.json at 7f51b0f71e5a9a1b6546065b0e27a5c86b286ac2)
