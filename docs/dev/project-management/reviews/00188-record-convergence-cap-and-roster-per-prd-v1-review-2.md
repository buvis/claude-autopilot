---
prd: dev/local/prds/wip/00188-record-convergence-cap-and-roster-per-prd-v1.md
review: 2
date: 2026-09-14
head_sha: 184db706c61f0c6f649de98bd365cc6b63a5cce7
codex_thread_id: 01a09f08-236c-7170-9758-bf919331050e
reviewers: alice,blake,bob,carl
agents:
  alice: available
  blake: available
  bob: available
  carl: available
---

# Review: 00188-record-convergence-cap-and-roster-per-prd-v1

Diff range: `7f51b0f71e5a9a1b6546065b0e27a5c86b286ac2..184db706c61f0c6f649de98bd365cc6b63a5cce7`

codex_rung_guard: not fired

pack: failed (`engram pack` exited 1 with the same deterministic "not inside a registered repo; register it in /Users/bob/.config/gita/repos.csv" as cycle 1; no retry spent). `{PACK_FILE}` and `{PACK_FINDINGS}` were substituted with `(no pack available this cycle)` in every prompt that takes them. Degraded, not invalid.

scope note: cycle 2, incremental review of the cycle-1 rework (`--since 7f51b0f`, 4 commits, 7 files, +305/-46: tasks 6 and 7). Each implementation-aware prompt carried the cycle-1 consolidated table with dispositions, the two settled-ledger discards, and the rework assumptions ledger § 6-7. Blake stayed blind: PRD and rubric only (his cycle-1 prompt reused byte for byte; `dev/local` is a real directory and the root has no dot prefix, so no filesystem-notes block). No design doc exists (`design: skip`).

bob note: codex ran once (exit 0, `--resume-thread 01a09f08-…` resumed the cycle-1 thread; the sidecar re-emitted the same id). One issue line, one FIX item, explicit `VERIFY: - (none)` / `KNOWN: - (none)`, all twelve `R` lines and five `D` lines present; no lack-of-input shape, no retry spent.

verification queue: none written this cycle (Bob's VERIFY bucket is empty); `00188-…-checks-1.json` does not exist either, so there was nothing to carry forward.

## Review Summary

Reviewed: 2 completed rework tasks (6, 7) against the 8 cycle-1 findings they were created to close
PRDs checked: 00188-record-convergence-cap-and-roster-per-prd-v1

### Agent Status

- Alice: ✅ Available (Claude subagent, sonnet; verified all 8 reworked findings against HEAD by reading the source, and the three "worth your own eyes" questions: the spy guards the real call path, the paused branch reaches `_append_metrics`, the non-dict `batch` case is pre-existing and schema-excluded)
- Blake: ✅ Available (Claude subagent, sonnet, blind/PRD-only; ran the cli suite (1017 passed, 643 subtests) and the prompt-contract suite (12), all green)
- Bob: ✅ Available (codex, exit 0, resumed thread, static analysis; doubt + de-slop lens)
- Carl: ✅ Available (gemini-run backend=copilot model=gemini-3.8-flash, exit 0, 1.6 KB output; read the diff, context, both loop call sites, `convergence.py`, CHANGELOG and every changed test file)

## Consolidated Findings

5 findings: 2 rows from `consolidate_findings.py` (no cross-reviewer overlap this cycle) plus the fail-first replay's three `[MECH]` lines absorbed as their own rows (`Found by: mech-check`). No 🔴 Critical; **one 🟠 High** (Bob's, confirmed by the orchestrator against `convergence.py:57-68` with a probe); 3 🟡 Medium (all three replay rows, all discarded at the gate with measured reasons); 1 ⚪ Low. Alice, Blake and Carl each verified the rework and passed every rubric rule; Blake passed all nineteen B rules with no finding.

| Consensus | Severity | Issue | File | Task | Found By |
|-----------|----------|-------|------|------|----------|
| [1/4] | 🟠 High | The false-clean finding is only partially resolved: a file containing just `reviewers: alice` still produces zero severity counts because one regex matched. The new partial-parse test also expects zeros for `Verdict: 1 finding` without a findings table. Missing findings evidence still appears clean, contrary to the PRD’s null requirement. | skills/run-autopilot/cli/convergence.py:57 | 6 | Bob |
| [1/4] | ⚪ Low | `batch` in `_append_convergence` holds only the batch id, not the batch dict; `batch_id` would read clearer (already self-noted by the work phase as LOW, left unapplied) | skills/run-autopilot/cli/loop.py | 6 | Alice |
| [1/4] | 🟡 Medium | Fail-first replay: 3 touched test(s) pass against the pre-change code: test_review_exit_to_review_writes_no_convergence_row, test_build_exit_writes_no_convergence_row, test_review_exit_to_paused_writes_no_convergence_row (discarded, reason below) | skills/run-autopilot/cli/test_loop.py | general | mech-check |
| [1/4] | 🟡 Medium | Fail-first replay: 1 touched test(s) pass against the pre-change code: test_partially_parsed_review_file_keeps_its_counts (discarded, reason below) | skills/run-autopilot/cli/test_convergence.py | general | mech-check |
| [1/4] | 🟡 Medium | Fail-first replay: 2 touched test(s) pass against the pre-change code: test_convergence_is_keyword_only, test_run_conditions_line_marks_nulls_with_question_marks (discarded, reason below) | skills/run-autopilot/cli/test_render_run_conditions.py | general | mech-check |

### Cycle-1 findings verified

All 8 reworked cycle-1 findings were verified resolved at HEAD by Alice (each against the source), and by Carl and Bob for the ones they re-read; Bob's only issue line is that the cycle-1 High on null-vs-zero is resolved for empty and garbage files but not for two narrower shapes (below). The ninth cycle-1 finding was a settled discard and no reviewer re-raised it.

### Decision gate (Phase 5)

**Cap check.** `state.cycle` 2 >= `rework_cap` 2 and one unresolved 🟠 High remains (not a settled deferral, not discardable: the orchestrator's probe over `convergence.read_cycle` reproduces both shapes Bob names, `reviewers: alice` alone -> `findings {0,0,0,0}` with `verdict None`, and `Verdict: 1 finding` with no table -> `verdict 1` with `findings {0,0,0,0}`; the cycle-1 task-6 brief defined "parsed" as either regex matching, which is looser than the PRD's "absence must not read as clean"). Loop mode, no CRITICAL -> **cap-out, converged-with-deferrals**: the High and the one Low are recorded in `state.deferred_decisions` as `cap-overflow` records (2), the convergence line is appended with `outcome: cap_deferred`, and the PRD finalizes. No tail sweep runs on a cap-out (`phase-review.md` Cap check), so the Low is deferred rather than swept. Every decision is in `state.autonomous_decisions` (14 entries, 4 from this cycle); the three discards are in `00188-record-convergence-cap-and-roster-per-prd-v1-ledger.json` (5 entries). No scope alarm, no blocking escalation, no recurring-issue protocol (the High is the narrowed residue of a cycle-1 finding, recorded as such rather than as a recurrence). Consensus on the High is 1/4: Alice, Blake and Carl passed R9/B1 without raising it. Severity kept as Bob reported it, consistent with the cycle-1 gate accepting the broader form of the same class as High.

- **Deferred to batch end, cap-overflow (2):** the 🟠 High above (Bob's FIX: return null findings when neither parseable findings rows nor an explicit clean verdict establishes counts; add a metadata-only fixture; correct the `Verdict: 1 finding`-without-table expectation in `test_partially_parsed_review_file_keeps_its_counts`), and the ⚪ Low naming nit (`batch` -> `batch_id` in `_append_convergence`).
- **Discarded (3 replay rows, reasons in the ledger):** the three loop negative tests pass at the replay base by construction (the first two are the cycle-1 settled discard; the paused test pins the same must-have and the base branch already fired only on `done`); `test_partially_parsed_review_file_keeps_its_counts` is a preservation pin paired with `test_unparseable_review_file_reads_null_not_zero`, which fails at base; the two `test_render_run_conditions.py` tests pass at `7f51b0f` because that base already carries the `convergence=` parameter, and a re-run of the replay against the PRD base `e718214` shows both FAILING there (14 of 15 touched tests fail; only the ledgered `subTest` misread is reported passing).

## Follow-up Tasks Created

None. The cap is reached: no rework task and no tail-sweep task are dispatched; the two unresolved findings are `cap-overflow` records for the batch-end review.

## Alice

Consensus lens, Claude subagent (sonnet). She verified all 8 reworked cycle-1 findings against HEAD by reading `convergence.py`, `loop.py:960-964`, the new and rewritten tests in `test_loop.py` and `test_render_run_conditions.py`, and `_select_report_block` (49 lines per the facts block). She also answered the three open questions herself: the `convergence` name in `test_loop.py` is the same module object `loop.py` imports, so the spy guards the real call; `_append_metrics` runs unconditionally before `_act_branch`, so the paused test exercises the exclusion branch; a non-dict `batch` fails identically and earlier at `_decide` (loop.py:750) and `schema.py` enforces `batch` as a dict (`test_schema.py:262-273`), so it is out of scope. 1 ⚪ Low.

```
[ALICE] ⚪ `batch` in `_append_convergence` holds only the batch id, not the batch dict; `batch_id` would read clearer (already self-noted by the work phase as LOW, left unapplied) | File: skills/run-autopilot/cli/loop.py | Task: 6

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

Blind lens, Claude subagent (sonnet), PRD and rubric only. He located and read all five modules, `gate.py` (confirmed untouched), the three reference docs, CHANGELOG, every test file and both goldens; ran the cli suite (1017 passed, 643 subtests, 0 failures) and the prompt-contract suite (12 passed); confirmed every acceptance-criteria-named test exists and passes, the row shape and key order, the null-vs-zero semantics, the try/except containment, the CLI wiring and the removal of the `printf` prose. No destructive operations, no new dependencies, no new flags, no out-of-scope logic. 0 findings.

```
[BLAKE] ✅ No issues found

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

Doubt + de-slop lens, codex (exit 0, resumed cycle-1 thread, static analysis in the read-only sandbox). 1 🟠 High, one FIX item, no VERIFY item, no KNOWN item. His R1/R2/R9 fails all map to the one finding: the rework closes the null-vs-zero gap for empty and garbage files but a metadata-only file and a `Verdict: N findings` file with no table still read as zero findings, and the new test pins the latter as correct. The orchestrator confirmed both shapes by probe before routing (Decision gate above).

```
[BOB] 🟠 The false-clean finding is only partially resolved: a file containing just `reviewers: alice` still produces zero severity counts because one regex matched. The new partial-parse test also expects zeros for `Verdict: 1 finding` without a findings table. Missing findings evidence still appears clean, contrary to the PRD’s null requirement. | File: skills/run-autopilot/cli/convergence.py:57 | Task: 6

FIX:
- Truncated reviews still appear clean — skills/run-autopilot/cli/convergence.py:57 — Return null findings when neither parseable findings nor an explicit clean verdict establishes counts. Add a metadata-only fixture and correct the positive-verdict-without-table expectation in test_convergence.py.
VERIFY:
- (none)
KNOWN:
- (none)

R1: fail
R2: fail
R3: pass
R4: pass
R6: pass
R7: pass
R8: pass
R9: fail
R10: pass
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

Frontend & design specialist, generalist here (no UI surface). Backend `copilot`, model `gemini-3.8-flash`, exit 0, non-empty output (1.6 KB). He read the diff and context, `_decide`, `_append_metrics`/`_append_convergence`, both call sites and `_run_loop`, `read_cycle`/`outcome`, CHANGELOG, `_select_report_block` and every changed test file. All twelve rules pass.

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

- **Mechanical facts**: computed from `ast` over the 7 changed files (6 Python) and appended to the reviewer context. Every function this rework touches is under 50 lines (`read_cycle` 38, `_append_metrics` 46, `_append_convergence` 23, `_select_report_block` 49, the longest new tests `test_partially_parsed_review_file_keeps_its_counts` 44 and `test_outcome_ignores_non_dict_deferrals` 40). File counts by `wc -l`: `convergence.py` 148, `test_convergence.py` 680, `test_render_run_conditions.py` 223 (all under the cap); `loop.py` 1420, `test_loop.py` 1714 and `__main__.py` 1020 are pre-existing overflows (PRD 00192 and the 00187 batch-end deferral) and no reviewer re-raised them. No reviewer contradicted the block, so nothing was discarded on that ground.
- **Tautological test shapes**: 110 test functions checked in 3 files, **0 `[MECH]` findings**.
- **Fail-first replay**: 14 touched tests ran against `7f51b0f` (the cycle-1 head, the incremental base); 8 failed at base, 6 reported as passing across three `[MECH]` lines, all three discarded with the reasons in the Decision gate and the ledger. A second replay against the PRD base `e718214` (run by the orchestrator to verify the `test_render_run_conditions.py` line) reports 14 of 15 touched tests failing there, with only the ledgered `subTest` misread (`test_tasks_line_falls_back_to_the_event_row_when_record_reads_zero`) reported passing.

Verdict: 5 findings

Tests: 1029 passed, 0 failed, 0 skipped (reused from last-verification.json at 184db706c61f0c6f649de98bd365cc6b63a5cce7)
