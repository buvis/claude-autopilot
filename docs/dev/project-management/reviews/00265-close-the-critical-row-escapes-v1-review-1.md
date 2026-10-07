---
prd: docs/dev/project-management/prds/wip/00265-close-the-critical-row-escapes-v1.md
review: 1
date: 2026-10-07
head_sha: 885a09505756880b3a6336bd3b028606495727e1
codex_thread_id: 01a1178a-26fd-7021-a6c7-567d2889dad2
reviewers: alice,blake,bob,carl
agents:
  alice: available
  blake: available
  bob: available
  carl: available
dispatch_rows:
  bob: cbea0069
  carl: 38811dda
---

# Review: 00265-close-the-critical-row-escapes-v1

Diff range: `14315a98f1209713dc1526554e36908d7c7f1e40..885a09505756880b3a6336bd3b028606495727e1`

codex_rung_guard: not fired

## Review Summary

Reviewed: 9 completed tasks
PRDs checked: 00265-close-the-critical-row-escapes-v1

### Agent Status
- Alice: ✅ Available
- Blake: ✅ Available
- Bob: ✅ Available (codex)
- Carl: ✅ Available (copilot backend)

Notes:
- pack: ok
- Bob's issue lines are emitted as markdown bullets (`- [BOB] …`); the leading `- ` was stripped in `docs/dev/tmp/bob-output-20261007-c1.txt` before consolidation, because `consolidate_findings.py`'s `_LINE_RE` anchors on `^\[`. Without that, all seven of Bob's findings were silently dropped from the first consolidation run. No finding text was changed.
- Consolidation ran through `consolidate_findings.py` (not model-side). No ledger exists (cycle 1), so no `--ledger` flags were passed.

## Consolidated Findings

| Ref | Consensus | Severity | Issue | File | Task | Found By |
|-----|-----------|----------|-------|------|------|----------|
| R1 | [3/4] | 🟡 | PRD #24 is only partly done. The `--` separator fix in `skills/work/scripts/record_dispatch.py` is missing (the file is not in the diff). The `^[A-Za-z0-9._][A-Za-z0-9._-]*$` shape check is also missing. `_dispatch_outcomes` only drops ids that start with `-`, and it does so with no stderr line, so the dispatch row stays open unnoticed. The design says "refuse", not "drop". Fix: validate with the regex, write a stderr line naming each refused id, and add `--` before the id in the `end` argv or in record_dispatch's own arg parsing. | skills/run-autopilot/cli/review_close.py:135 | 6 | ALICE, BLAKE, BOB |
| R2 | [1/4] | 🟠 | Tail sweep is refused on every converged cycle. `_tail_sweep_refusal` requires `<review>::decision-gate` in `applied_review_batches`. The prose never makes that call on the converged path. The only `--batch-id decision-gate` call is in Phase 6 "Dispatch rework", which a converged cycle never enters (Outcomes: Converged goes straight to Tail sweep, then finalize). Tail sweep step 2 also says the decision gate "already" ran "earlier in the cycle", which is false for a converged cycle. A converged cycle with a swept Medium/Low tail would therefore exit 2 with `tail_sweep_before_decision_gate`. Prose reads that as a sub-skill failure, so the loop retries once and then stalls. The PRD's own Risks section names this stall. The prose needs a decision-gate call before the sweep, or the rule needs a carve-out. | skills/run-autopilot/references/phase-review.md:195 | 3 | BLAKE |
| R3 | [1/4] | 🟠 | The findings-table parse still fails open on an indented pipe row, which the spec says must be refused. `_CANDIDATE_ROW_RE` is `^\|`, so a data row with leading whitespace is silently skipped. I ran `findings_verdict` on a table with a 🔴 R1 row written as ` \| R1 \| [2/2] \| 🔴 \| ...` and a findings JSON that names only R2. The result was `('ok', None)`, so the Critical gets no disposition and no task. This is the same escape class as agoge finding 2. The spec says "every following pipe row that is not a separator is a data row". An indented header is refused (`malformed`), but an indented data row under a valid header is dropped. | skills/run-autopilot/cli/gate.py:128 | 1 | BLAKE |
| R4 | [1/4] | 🟠 | Converged cycles jump directly to tail sweep, but the new guard requires a decision-gate stamp created only in Phase 6, which convergence skips. Apply the decision-gate batch before the sweep and prevent duplicate task creation; add a workflow regression. | skills/run-autopilot/cli/review_close.py:432 | 3 | BOB |
| R5 | [1/4] | 🟡 | The new state vocabulary is undocumented. The `lost` lens status and the `carry_refs`/`carry_cycle` task fields appear in code and prose but not in the schema reference. `review_lenses` is still described as `running\|done\|failed` in skills/run-autopilot/references/state-schema.md:216 and in the tracon docstring at skills/run-autopilot/scripts/tracon/model.py:281. state-schema.md has no entry for `carry_refs`/`carry_cycle`. Add both to state-schema.md and the docstring. | skills/run-autopilot/references/state-schema.md:216 | general | ALICE |
| R6 | [1/4] | 🟡 | Unspecified behaviour was added. A tail-sweep batch with a `carry` row is refused with a new `carry_in_tail_sweep` kind. The PRD does not ask for this, though it is documented in CHANGELOG.md:15 and `__main__.py`. | skills/run-autopilot/cli/review_close.py:425 | 3 | BLAKE |
| R7 | [1/4] | 🟡 | A complete data row missing only its closing pipe still parses successfully: `_table_cells` strips delimiters without checking termination. Enforce the required closing pipe and test this case through both verbs; existing truncation tests retain closing pipes. | skills/run-autopilot/cli/gate.py:373 | 1 | BOB |
| R8 | [1/4] | 🟡 | Deferral matching only strips strings, so an existing `medium` deferral does not match a 🟡 finding for the same file. Reuse the shared severity/file normalization and test word/emoji equivalence. | skills/run-autopilot/cli/review_close.py:402 | 3 | BOB |
| R9 | [1/4] | 🟡 | The backup-preservation test exercises three first-time refusals, never an already-applied repeat. Apply a batch, snapshot backup bytes and mtime, repeat that batch, and assert both remain unchanged. | skills/run-autopilot/cli/test_review_close_lowsev.py:311 | 6 | BOB |
| R10 | [1/4] | 🟡 | The moved verdict-preservation test calls an empty tail sweep without its decision-gate stamp; the call now refuses, making the preservation assertion vacuous. Supply valid sweep prerequisites and assert successful application before checking preserved verdicts. | skills/run-autopilot/cli/test_review_close_apply.py:133 | general | BOB |
| R11 | [1/4] | 🟡 | Simplification: the duplicate-deferral test and fixtures substantially repeat `test_review_close_lowsev.py:145`. Consolidate both input variants into one parametrized test, retaining all distinct assertions and controls. | skills/run-autopilot/cli/test_review_close_tail_sweep.py:111 | general | BOB |
| R12 | [1/4] | ⚪ | The `unreadable-table` message still describes the old shape: rows "shaped \| [m/n] \| ... (optionally led by a \| R1 \| ref cell)". The parser now requires a single `R<digits>` ref and a bracketed `[m/n]` consensus, and a table with no Ref column is refused as `ref-required`. The message also does not name the offending row. The exit-2 operator therefore cannot see which row to fix in one round trip, which the PRD risk section promised. Reword the message and, if cheap, name the row. | skills/run-autopilot/cli/gate.py:152 | 1 | ALICE |
| R13 | [1/4] | ⚪ | `_run_review_close` returns `2 if result.get("refused") else 1` instead of the design's explicit `_EXIT_2_REFUSALS` tuple. Today's behaviour is equivalent and the CLI test pins every kind, so this is a note only. Any future `refused` key silently becomes exit 2. | skills/run-autopilot/cli/__main__.py:1112 | 2 | ALICE |
| R14 | [1/4] | ⚪ | For a refless table or bullet-shape findings, the spec says `unreadable-table`. The code returns a distinct `ref-required` verdict (`gate.py:503`). Both verbs still exit 2, but the tag and message differ from the spec's wording, and `_FINDINGS_REFUSALS` gains an extra kind. A tail-sweep batch accepts a refless table or bullet rows, because coverage is skipped for it. | skills/run-autopilot/cli/gate.py:503 | 1 | BLAKE |
| R15 | [1/4] | ⚪ | The `review-close` message for an unknown classification is still generic. It names neither the row nor the value (`__main__.py:1083`). The spec only asks for the per-row message in `gate --findings`, which is implemented. | skills/run-autopilot/cli/__main__.py:1083 | 4 | BLAKE |
| R16 | [1/4] | ⚪ | Cannot statically verify: release-checks passes at the reviewed revision. The context reports cached results; the exact check is `bash dev/bin/release-checks`. | N/A | 7 | BOB |
| R17 | [1/4] | ⚪ | Existing size violations remain: `__main__.py` has 1,679 lines; the supplied mechanical report measures `_select_report_block` at 55 lines and `_render_report_surface` at 51. Splitting unrelated rendering code is outside this review-verb change. | skills/run-autopilot/cli/__main__.py:1256 | general | BOB |
| R18 | [1/4] | 🟡 | 6 touched test(s) pass against the pre-change code: test_direct_invocation_cross_checks_findings, test_cross_check_matches_an_issue_starting_with_a_severity_word, test_cross_check_normalizes_combined_severity_cell, test_gate_accepts_a_review_row_invented_at_runtime, test_gate_accepts_matching_findings_json, test_partial_batch_is_not_a_mismatch | skills/run-autopilot/cli/test_gate.py | general | mech-check |
| R19 | [1/4] | 🟡 | 7 touched test(s) pass against the pre-change code: test_a_batch_of_known_classifications_still_exits_0, test_unknown_classification_outranks_the_cross_check_verdict, test_findings_exit_accepts_every_known_classification +1 more | skills/run-autopilot/cli/test_gate_findings_classification.py | general | mech-check |
| R20 | [1/4] | 🟡 | 6 touched test(s) pass against the pre-change code: test_cross_check_backs_the_same_real_pair_once_refs_are_carried, test_cross_check_reads_a_real_saved_review_file, test_cross_check_refuses_the_real_paraphrased_findings_json_without_refs, test_findings_json_covers_every_row_prose, test_requeued_rows_are_classified_carry_prose, test_tail_sweep_is_exempt_from_coverage_prose | skills/run-autopilot/cli/test_gate_findings_real_fixtures.py | general | mech-check |
| R21 | [1/4] | 🟡 | 4 touched test(s) pass against the pre-change code: test_ghost_ref_row_is_refused_for_every_applied_classification, test_a_row_carrying_only_a_ref_and_a_classification_is_backed_by_that_ref, test_each_findings_verdict_exits_by_its_own_tag | skills/run-autopilot/cli/test_gate_findings_shapes.py | general | mech-check |
| R22 | [1/4] | 🟡 | 12 touched test(s) pass against the pre-change code: test_a_ref_less_chosen_row_still_matches_exactly_as_before, test_a_truncated_data_row_is_malformed_not_a_crash, test_bullet_rows_without_ref_need_coverage_and_are_refused, test_cross_check_reads_a_pipe_table_review_file, test_cross_check_reads_the_five_column_documented_table, test_cross_check_refuses_an_empty_issue_with_no_ref +6 more | skills/run-autopilot/cli/test_gate_findings_table.py | general | mech-check |
| R23 | [1/4] | 🟡 | 8 touched test(s) pass against the pre-change code: test_rejects_an_actionable_row_missing_the_file_or_issue_close_reads, test_rejects_a_findings_entry_that_is_not_a_row, test_cli_exits_2_when_a_findings_row_mismatches, test_cli_exits_2_when_a_review_row_has_no_disposition, test_every_refusal_kind_exits_2_and_names_itself +2 more | skills/run-autopilot/cli/test_main_review_close_validation.py | general | mech-check |
| R24 | [1/4] | 🟡 | 8 touched test(s) pass against the pre-change code: test_tail_sweep_applies_cleanly_against_a_partial_ref_table, test_close_applies_a_findings_subset_of_the_review, test_cli_exit_2_on_findings_uncovered, test_cli_accepts_a_carry_classification, test_cli_exits_1_when_the_review_itself_fails_the_gate, test_cli_still_exits_1_on_other_not_applied_reasons +2 more | skills/run-autopilot/cli/test_review_close.py | general | mech-check |
| R25 | [1/4] | 🟡 | 14 touched test(s) pass against the pre-change code: test_close_is_idempotent, test_close_refuses_a_gate_failing_review_file, test_close_records_doubt_verdicts, test_close_group_uses_emoji_severity_not_english_word, test_close_idempotency_check_is_inside_the_transaction, test_close_decision_gate_and_tail_sweep_batches_are_independently_idempotent +8 more | skills/run-autopilot/cli/test_review_close_apply.py | general | mech-check |
| R26 | [1/4] | 🟡 | 2 touched test(s) pass against the pre-change code: test_two_carry_refs_backed_by_one_task_are_accepted, test_a_tail_sweep_batch_skips_the_carry_match | skills/run-autopilot/cli/test_review_close_carry.py | general | mech-check |
| R27 | [1/4] | 🟡 | 3 touched test(s) pass against the pre-change code: test_a_clean_tail_sweep_still_applies, test_a_tail_sweep_over_a_gate_failing_review_is_refused_by_the_gate | skills/run-autopilot/cli/test_review_close_tail_sweep.py | general | mech-check |

R18-R27 are the fail-first replay block's `[MECH]` rows, absorbed verbatim per SKILL step 6. Each states a computed fact (the touched tests pass against the pre-change code); whether that is a defect is the decision gate's call.

## Alice

See the four findings above attributed to ALICE (R1, R5, R12, R13). Alice did not run the suite; she read the context's recorded counts.

R1: pass
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
R13: pass

## Blake

Blind lens, PRD-only. Findings above attributed to BLAKE (R2, R3, R6, R14, R15, and R1 jointly).

Verified as working (Blake's own words):
- `carry` is checked against a task's `carry_refs`, `carry_cycle`, `rework_task_ids` and `escalation_reason`, before the lock.
- Ghost `carry` refs, off-shape refs, duplicated refs and double-classified refs refuse.
- `review-close` and `gate` share `findings_verdict` and refuse `unreadable-table`. Only `no-section` keeps the legacy pass.
- Tail-sweep refusals for above-medium rows, empty arrays and open deferrals work. A tail sweep returns `lenses_closed: {}`.
- A persona absent from `agents:` closes as `lost`. The apply-once read happens before `mutate`.
- The `release-checks` list and the test that pins it are in place. CHANGELOG, help text and prose were updated.
- His targeted pytest run gave 162 passed; `bash dev/bin/release-checks` exited 0 (PASS 2815 FAIL 0 SKIP 0 EXIT 0).

B1: fail
B2: pass
B3: pass
B4: pass
B5: pass
B6: fail
B7: pass
B8: pass
B9: pass
B10: fail
B11: pass
B12: pass
B13: pass
B14: pass
B15: pass
B16: fail
B17: pass
B18: pass
B19: pass

## Bob

Doubt lens + de-slop (codex). FIX bucket: R4, R7, R8, R9, R10, R11, and R1 jointly. VERIFY bucket: R16 (`bash dev/bin/release-checks`, queued). KNOWN: R17.

R1: fail
R2: fail
R3: pass
R4: fail
R6: pass
R7: fail
R8: pass
R9: fail
R10: pass
R11: pass
R12: fail
R13: fail

D1: pass
D2: pass
D3: pass
D4: pass
D5: pass

## Carl

[CARL] ✅ No issues found. Backend: copilot. He ran the targeted pytest files and `bash dev/bin/release-checks` himself.

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

Verdict: 27 findings
Tests: 2815 passed, 0 failed, 0 skipped (reused from last-verification.json at 885a095)
