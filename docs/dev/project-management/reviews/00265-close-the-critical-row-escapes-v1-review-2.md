---
prd: docs/dev/project-management/prds/wip/00265-close-the-critical-row-escapes-v1.md
review: 2
date: 2026-10-07
head_sha: 3fc3ae77a7d6da1c9692a82fa36b4a4168c33526
codex_thread_id: 01a1178a-26fd-7021-a6c7-567d2889dad2
reviewers: alice,blake,bob,carl
agents:
  alice: available
  blake: available
  bob: available
  carl: available
dispatch_rows:
  bob: 8e7ae91f
  carl: eb2b6a9c
---

# Review: 00265-close-the-critical-row-escapes-v1

Diff range: `885a09505756880b3a6336bd3b028606495727e1..3fc3ae77a7d6da1c9692a82fa36b4a4168c33526`

codex_rung_guard: not fired

## Review Summary

Reviewed: 13 completed tasks (incremental review of the cycle-1 rework)
PRDs checked: 00265-close-the-critical-row-escapes-v1

### Agent Status
- Alice: ✅ Available
- Blake: ✅ Available
- Bob: ✅ Available (codex, resumed thread `01a1178a`)
- Carl: ✅ Available (copilot backend)

Notes:
- pack: ok
- Consolidation ran through `consolidate_findings.py` (not model-side), with `--ledger` and `--ledger-dismiss BLAKE` (the cycle-1 ledger holds 8 entries). One Blake finding was auto-dismissed; it is reproduced below.
- `consolidate_findings.py` warned twice about citations merged only after line-suffix stripping. The second merge (R2, `review_close.py:122 ~ :131`) is a genuine paraphrase pair. The first (`review_close.py:454 ~ :476 ~ :445`) over-merged: Blake's distinct ⚪ finding at `:476` (a tail sweep of `verify`/`discard`-only rows applies and creates zero tasks) was folded into R1 and its text lost. It is restored verbatim as **R19** so no finding is silently dropped.
- Carl's first targeted pytest run showed one `ModuleNotFoundError: No module named 'skills'` — a missing `PYTHONPATH`, not a defect. He re-ran with `PYTHONPATH=.` and then `bash dev/bin/release-checks` himself; both passed.
- Carry-forward: cycle 1's verification queue held one entry (`bash dev/bin/release-checks`) whose `result.exit` was `null` (never run by that cycle's work pass). It is carried forward and merges onto **R17**, which re-raises the same command. The check has since been **observed green** at this HEAD: `review-stage`'s gate ran `dev/bin/release-checks` to exit 0 (2820 passed, 0 failed, 0 skipped), and Blake and Carl each ran it independently to `EXIT 0`. Cycle 2's queue records that result.
- Mechanical blocks: one `[MECH]` fail-first replay row this cycle, absorbed verbatim as **R18**. No consolidated row named that test file and test, so it stands alone.

## Consolidated Findings

| Ref | Consensus | Severity | Issue | File | Task | Found By |
|-----|-----------|----------|-------|------|------|----------|
| R4 | [1/4] | 🟠 | Fail-open for a findings table whose header is not recognised. `_table_keys` only goes fail-closed after it finds a header naming Severity, Issue and File. With no recognised header it treats the section as "no table" unless a row matches `TABLE_DATA_ROW_RE`. Probe: header `\| Ref \| Cons \| Sev \| Issue \| Files \|` plus row `\| R1 \| 2/2 \| 🔴 \| deletes data \| a.py \|` gives `findings_verdict(..., [])` = `('ok', None)`. A 🔴 row leaves with no task, no record and no refusal, the same class as escape #2. The identical table with the correct header and an unbracketed `2/2` is refused. | skills/run-autopilot/cli/gate.py:386 | general | BLAKE |
| R1 | [4/4] | 🟡 | The new `_tail_sweep_refusal` docstring contradicts the prose it points at. It says the caller "applies an empty decision-gate batch" under "Converged Outcome". The prose builds a full `chosen_findings` array with sweep-selected rows set to `verify` (an empty array would be `uncovered` against any review table with rows), and no heading named "Converged Outcome" exists (it is Outcomes "Converged (no unresolved CRITICAL/HIGH)"). The docstring also grew the function to 56 lines, over the 50-line limit. Cut the added paragraph to one line that points at phase-review.md Tail sweep step 0. | skills/run-autopilot/cli/review_close.py:454 | 12 | ALICE, BLAKE, BOB, CARL |
| R2 | [2/4] | 🟡 | Cycle-1 R1 is only partly closed. The PRD #24 `--` separator before the row id is still missing in the `end` argv (review_close.py:122) and in `record_dispatch.py`. The new `_end_dispatch_rows` docstring documents the shape check as the substitute. The shape check does keep dash ids out, so this is defense-in-depth, but it is a literal PRD clause. Add `"--"` before `row_id` in the argv, which is a one-token change. | skills/run-autopilot/cli/review_close.py:122 | 6 | ALICE, BOB |
| R3 | [2/4] | 🟡 | The `unreadable-table` message is reworded but still does not name the offending row. `_table_keys` returns no row info, so the operator still cannot fix it in one round trip. The new text is also run-on ("...reported separately as 'ref-required', not here"). `test_unreadable_table_message_names_the_ref_required_shape` has a tautological first assert, `"ref" in message.lower()`, which was true before the change because the old text said "ref cell". Only the `ref-required` assert binds. | skills/run-autopilot/cli/gate.py:152 | 1 | ALICE, BLAKE |
| R5 | [1/4] | 🟡 | The R2/R4 fix is prose-only (phase-review.md step 0) with no regression test. R4 explicitly asked for a workflow regression. No test in the diff pins the new step 0, for example that the converged path calls `--batch-id decision-gate` before `--batch-id tail-sweep`. A later prose edit can reintroduce the converged-cycle stall silently. Add a pin to `skills/review-work-completion/scripts/test_review_verbs_prose.py` or `skills/run-autopilot/scripts/test_phase_review_closes_via_review_close.py`. | skills/run-autopilot/references/phase-review.md:193 | 12 | ALICE |
| R6 | [1/4] | 🟡 | Step 0 runs before step 1's "zero actionable Medium/Low, skip the sweep entirely" exit. A clean converged cycle that needs no sweep now pays an extra `review-close decision-gate` call that can itself stall on a refusal. That contradicts step 1's "today's clean path, unchanged". Step 0 also forward-references "rows step 1 will select". Simpler order: select (step 1), skip if zero, then run the decision gate, then create (step 2). | skills/run-autopilot/references/phase-review.md:193 | 12 | ALICE |
| R7 | [1/4] | 🟡 | The new `lost` documentation does not match the code. state-schema.md and the tracon docstring say `lost` means "the persona had an open dispatch row and no line under `agents:`". `_lens_states` marks every `_PERSONA_LENS` persona absent from `agents:` as `lost` (including ui and fable), with no reference to dispatch rows. Reword the docs to the real condition, or gate the code on the dispatch row. | skills/run-autopilot/references/state-schema.md:218 | general | ALICE |
| R8 | [1/4] | 🟡 | Spec deviation on #24: `_end_dispatch_rows` does not pass `--` before the row id. The PRD says it "passes `--` before the id and refuses ids not matching `[A-Za-z0-9._][A-Za-z0-9._-]*`". The id-shape refusal is done in `_dispatch_outcomes` (skip plus stderr line), so a dash-led id never reaches argv. The belt-and-braces `--` is missing, and `test_dispatch_id_with_leading_dash_is_refused` pins only the refusal. | skills/run-autopilot/cli/review_close.py:126 | general | BLAKE |
| R9 | [1/4] | 🟡 | A Ref-less table and bullet rows are reported as `ref-required` (`findings_ref_required`), not `unreadable-table` as the PRD says. Both exit 2 from both verbs, so the contract holds. For a tail-sweep batch (`require_coverage=False`) neither is refused at all, although the PRD says they are `unreadable-table` "once a findings JSON is passed". | skills/run-autopilot/cli/gate.py:510 | general | BLAKE |
| R10 | [1/4] | 🟡 | `carry_refs` is incorrectly documented as unioned across cycles. Phase 6 resets refs when the cycle changes; retaining old refs can authorize unrelated carry rows. Document same-cycle union and cross-cycle reset. | skills/run-autopilot/references/state-schema.md:200 | 12 | BOB |
| R11 | [1/4] | 🟡 | The converged-path fix lacks its requested workflow regression. Pin decision-gate-before-sweep ordering and exercise a Ref-bearing findings table: gate selected rows as `verify`, then sweep them as `fix`, asserting exactly one task is created. Existing tests do not cover this new mapping. | skills/run-autopilot/references/phase-review.md:193 | 11 | BOB |
| R18 | [1/4] | 🟡 | 1 touched test(s) pass against the pre-change code: test_close_records_doubt_verdicts | skills/run-autopilot/cli/test_review_close_apply.py | general | mech-check |
| R12 | [1/4] | ⚪ | The closing-pipe test (`test_a_data_row_missing_its_closing_pipe_is_refused`) exercises the gate cross-check only. R7 asked for both verbs. The review-close side is covered only indirectly through `findings_verdict` sharing. | skills/run-autopilot/cli/test_gate_findings_shapes.py:529 | 1 | ALICE |
| R13 | [1/4] | ⚪ | The pre-lock refusals (carry match, tail-sweep order, empty, above-medium, open deferral) run on an advisory read. The in-lock check in `_close_mutator` re-checks only the apply-once stamp. This matches the PRD's "before the state lock" and the single-orchestrator model, but it is a check-then-act window if state changes between the read and the mutate. | skills/run-autopilot/cli/review_close.py:293 | general | BLAKE |
| R14 | [1/4] | ⚪ | `_carry_unmatched` does not require the `[C{cycle}]` name prefix. It rejects only names starting `[D`, and instead relies on `carry_refs`, `carry_cycle`, `escalation_reason`, `rework_task_ids` and status. The docstring and error text say `[C]`-prefixed. This is stricter than the PRD in other ways, so it is cosmetic. | skills/run-autopilot/cli/review_close.py:390 | general | BLAKE |
| R15 | [1/4] | ⚪ | The PRD names two homes for the help-text pin: `skills/run-autopilot/scripts/test_review_verbs_prose.py` in the task and `skills/review-work-completion/scripts/test_review_verbs_prose.py` in the structure. Only the second exists. `test_gate_help_describes_the_two_way_check`, `test_requeue_records_the_carry_link_prose` and `test_carry_creates_nothing_prose` live there and pass. This is a PRD inconsistency, not a code fault. | skills/review-work-completion/scripts/test_review_verbs_prose.py:82 | general | BLAKE |
| R16 | [1/4] | ⚪ | Residual not in scope: a 🔴 row classified `discard` or `verify` still needs no backing row and creates no task or record at the CLI layer. A `discard` of a ghost ref is also accepted. The PRD only closes this for `carry`. | skills/run-autopilot/cli/gate.py:471 | general | BLAKE |
| R19 | [1/4] | ⚪ | A tail sweep holding only `verify` or `discard` rows passes the new "empty" check. It applies, creates zero tasks and stamps `<review>::tail-sweep`, the failure mode #5 describes ("never zero", `phase-review.md:197`). The refusal is literal array length only. | skills/run-autopilot/cli/review_close.py:476 | general | BLAKE |
| R17 | [1/4] | ⚪ | Cannot statically verify: release checks pass at the reviewed revision. Exact check: `bash dev/bin/release-checks`. The supplied context reports 2,820 passing tests; this review did not execute them. | N/A | 7 | BOB, verify-check |

### Auto-dismissed (ledger)

- [BLAKE] 🟡 Unrequested refusal: a `carry` row inside a tail-sweep batch is refused as `carry_in_tail_sweep` (exit 2). The PRD lists only three tail-sweep refusals (before the decision gate, above 🟡, empty); the open-deferral refusal is #12, which the PRD also lists. It is a new refusal kind, and it is also added to the `__main__` help and the CHANGELOG. | File: skills/run-autopilot/cli/review_close.py:460 — Accepted as a fail-closed refusal in the PRD's own direction (a carry row belongs to a decision-gate batch); documented in CHANGELOG and help text. Removing it would re-open an escape.

## Alice

Implementation-aware consensus lens. Findings above attributed to ALICE (R1, R2, R3, R5, R6, R7, R12). She verified cycle-1 R3, R7, R8, R10 as resolved and R1, R12 as partly resolved; she ran the five touched test files (104 passed, 28 subtests, 0 failed) and did not re-run `release-checks`.

R1: fail
R2: pass
R3: pass
R4: pass
R6: pass
R7: pass
R8: pass
R9: fail
R10: pass
R11: pass
R12: fail
R13: pass

## Blake

Blind lens, PRD-only. Findings above attributed to BLAKE (R1 jointly, R3 jointly, R4, R8, R9, R13, R14, R15, R16, R19), plus one ledger-dismissed row.

Verified as working (Blake's own words): the three HIGH escapes and the four MEDIUM findings are closed in the cases the PRD names. He ran 165 targeted tests (all passed) and `bash dev/bin/release-checks` to `PASS 2820 FAIL 0 SKIP 0 EXIT 0`, plus probe scripts against `gate.findings_verdict`.

B1: fail
B2: pass
B3: pass
B4: pass
B5: pass
B6: fail
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

Doubt lens + de-slop (codex, resumed thread). FIX bucket: R10, R2 jointly, R11, R1 jointly. VERIFY bucket: R17 (`bash dev/bin/release-checks`, queued in checks-2.json). KNOWN: (none).

R1: fail
R2: pass
R3: pass
R4: pass
R6: pass
R7: pass
R8: pass
R9: fail
R10: pass
R11: pass
R12: fail
R13: pass

D1: pass
D2: pass
D3: pass
D4: pass
D5: pass

## Carl

Frontend & design specialist (copilot backend). One finding, folded into R1: `_tail_sweep_refusal` is 56 lines, over the 50-line style limit, confirmed by his own `check_style_limits.py --diff` run. He ran the targeted pytest files (113 passed after supplying `PYTHONPATH=.`) and `bash dev/bin/release-checks` himself.

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
R13: pass

Verdict: 19 findings
Tests: 2820 passed, 0 failed, 0 skipped (suite run this cycle by review-stage, recorded in last-verification.json at 3fc3ae7)
