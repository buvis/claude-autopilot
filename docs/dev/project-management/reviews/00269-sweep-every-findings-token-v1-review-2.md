---
prd: 00269-sweep-every-findings-token-v1.md
cycle: 2
date: 2026-10-10
head_sha: 709864f8262596a352d994076c56c406981a7eee
codex_thread_id: 01a12535-e793-71d3-b69e-2ef34b62bff6
reviewers: alice,blake,bob,carl
---

# Review Cycle 2 - 00269-sweep-every-findings-token-v1

Scope: incremental review (rework since cycle 1)
Diff range: ee019d36f6f3850ee3e8640eedfebc7dc66d2af7..709864f8262596a352d994076c56c406981a7eee

codex_rung_guard: not fired

Pack: ok
Tasks: 18/18 completed

Carried forward from cycle 1: `00269-...-checks-1.json` queued
`bash dev/bin/release-checks` with no recorded result, so it enters this
cycle's table as R17. This cycle's staging ran that exact gate at HEAD
(2943 passed, 0 failed, 0 skipped), which is why it is ⚪ rather than higher.

## Consolidated Findings

| Ref | Consensus | Severity | Issue | File | Task | Found By |
|-----|-----------|----------|-------|------|------|----------|
| R1 | [3/4] | 🟠 | `from datetime import UTC` breaks Python 3.10: that alias needs 3.11. Carl reproduced it (`uv run --python 3.10 python -m cli --help` → `ImportError: cannot import name 'UTC' from 'datetime'`). The hunk is an unrelated end-of-turn formatter reflow (same class as the cycle-1 settled R12, different hunks): it also rewrote `_utc_now` (`__main__.py:1173`), single-lined `uncovered = [...]` (`gate.py:649`), dropped local `from cli import gate` imports and a trailing comma (`test_gate_findings_shapes.py:500`, `:570`) and reflowed asserts in `test_review_close_carry.py`. Revert the reflow to the `timezone.utc` form to keep the diff surgical and 3.10 working. | skills/run-autopilot/cli/__main__.py:243 | 15 | ALICE, BOB, CARL |
| R2 | [3/4] | 🟡 | Prior R13/R15 got worse: `test_review_close.py` is now 835 lines, over the 800 limit. It was 764 at base and 784 last cycle. The new `_covered` and `_table` helpers (about 46 lines) and the added tests caused it. Move the helpers to a small shared test-helper module, or move tests out, to get back under 800. | skills/run-autopilot/cli/test_review_close.py:1 | 15 | ALICE, BLAKE, BOB |
| R3 | [3/4] | ⚪ | Prior R17 is only partly fixed. The blank-line `in_table` reset refuses a non-header-shaped second block, but a second table whose header is itself `| Severity | Issue | File | Found By |` still passes. `_unread_token` marks it consumed, and `_table_keys` reads the second header as a data row. Reproduced: with a Ref-less first table and a blank line before a second header, `findings_verdict` returns `('ok', None)` and `_table_keys` returns a `Row(severity='', file='File', issue='Issue')`. The row still reaches the cross-check, so a red row is not hidden, but the "second table is refused" claim is untrue for this shape. Either refuse a header-shaped line after the first header in `_table_keys`, or document the gap. | skills/run-autopilot/cli/gate.py:563 | 15 | ALICE, BLAKE, BOB |
| R4 | [2/4] | 🟡 | Prior R7 is not resolved: `_no_verdict_refusal` still restates the no-verdict text as a literal that duplicates `gate.py:218`. Task 16 and the design say to reuse the exact `gate.check` string. Expose it as one `gate` constant and import it so the two cannot drift. | skills/run-autopilot/cli/review_close.py:243 | 16 | ALICE, BOB |
| R5 | [2/4] | 🟡 | Prior R10 is not addressed. `test_carry_refusal_names_the_closest_task_and_its_first_failing_condition` still passes a single `[task]`. Nothing tests that the longest passing run wins, nor tie-breaking by first occurrence in either order. Add multi-candidate cases (different first failures, then equal ranks in both orders) and assert the exact id and reason. | skills/run-autopilot/cli/test_review_close_carry.py:331 | 15 | ALICE, BOB |
| R6 | [2/4] | 🟡 | `_carry_reason` remains over the 50-line limit and has grown to 60 lines, per the mechanical facts. Shorten its repetitive explanation while retaining the ranking order, tie-break rule, and unmatched-task precondition. | skills/run-autopilot/cli/review_close.py:441 | 16 | BOB, CARL |
| R7 | [1/4] | 🟡 | Prior R9 is only partly resolved. Two assertions were hardcoded (`test_review_close.py` around lines 713 and 740). The test helper `_carry_reason` still calls production `review_close._carry_reason`, and `test_review_close_carry.py:103`, `:220` and `:240` still compare the implementation against its own output, so a wrong message passes. Replace those with literal expected strings. | skills/run-autopilot/cli/test_review_close.py:227 | 15 | ALICE |
| R8 | [1/4] | 🟡 | Fence opener rule lets an inline triple-backtick line (for example "```x``` mention") open a fence. Any later fence line then closes it, so a real 🔴 findings table between them is treated as quoted. Probe: that text plus a table plus a later closed fence, with findings `[]`, returns `("malformed", no-section)`. That means gate exit 1 and review-close applying the legacy path, with the Critical leaving the gate and no task created. The spec's "starts with three or more backticks" wording allows this, but it reopens the "CRITICAL leaves with no task" class the PRD closes. A fix: refuse an opener whose info string contains a backtick, as CommonMark does. | skills/run-autopilot/cli/gate.py:142 | gate sweep (Phase 0) | BLAKE |
| R9 | [1/4] | 🟡 | The new blank-line reset makes consumption tracking disagree with `_table_keys`: a closed fenced example between two covered data rows becomes blank lines, resets `in_table`, and causes the second row to be refused although the parser reads it. Preserve quoted-line identity and derive consumption from the parser's actual matches; add this regression case. | skills/run-autopilot/cli/gate.py:563 | 15 | BOB |
| R10 | [1/4] | 🟡 | Prior R9 is only partially fixed: three assertions in `test_review_close_carry.py` still use the test helper that calls production `_carry_reason`. Replace their expected values with independent strings and remove that helper. | skills/run-autopilot/cli/test_review_close_carry.py:103 | 15 | BOB |
| R11 | [1/4] | 🟡 | The revised idempotency test overwrites the gate's table with the tail-sweep table before `gate_again`; that retry now fails findings validation, so `applied == False` no longer proves idempotency. Restore the matching table before each retry and assert `reason == "already applied"`. | skills/run-autopilot/cli/test_review_close_apply.py:240 | 15 | BOB |
| R12 | [1/4] | ⚪ | `test_a_carry_row_with_no_usable_ref_is_refused_naming_none` now asserts `findings_malformed` and the "yet the findings JSON names 1 rows" text, not the `(none)` naming its name and the `_carry_reason` call promise. The `(none)` message is already pinned in `test_carry_refusal_names_no_usable_ref_for_a_ref_less_row`. Rename the test to say what it now enforces. | skills/run-autopilot/cli/test_review_close_carry.py:40 | 6 | ALICE |
| R13 | [1/4] | ⚪ | Simplification: `_boundary_refusal_line` is a single-caller helper, and `_refuse_escaped_boundaries` calls `path.resolve()` twice per field. The old inline form was shorter. Inline the line or compute `resolved` once. Behaviour is preserved and the function is under 50 lines either way. | skills/run-autopilot/cli/__main__.py:939 | 8 | ALICE |
| R14 | [1/4] | ⚪ | Two spec deviations, both cosmetic. (a) The spec's Exports line says `_FINDINGS_PROBLEMS` gains the no-section-with-findings text. It is inlined in `_malformed_detail` instead. (b) The `no_verdict` reason is a hard-coded copy of `gate.check`'s verdict message instead of being derived from it, so the two strings can drift. | skills/run-autopilot/cli/gate.py:601 | gate sweep / review_close no_verdict | BLAKE |
| R15 | [1/4] | ⚪ | Prior R13 is only partially fixed: the stdout assertion rejects review-context paths but permits review-diff paths. Assert stdout is empty, covering every published artifact path. | skills/review-work-completion/scripts/test_gather_context_id.sh:241 | 18 | BOB |
| R16 | [1/4] | ⚪ | Cannot statically verify: tests and release checks pass. Run `bash dev/bin/release-checks` after corrections; the supplied context reports 2943 passing tests, but this review executed none. | N/A | general | BOB |
| R17 | [1/4] | ⚪ | Carried forward: cycle 1 queued `bash dev/bin/release-checks` and recorded no result. This cycle's staging ran that gate at HEAD 709864f (2943 passed, 0 failed, 0 skipped), so the check is satisfied, but no cycle-1 result was ever written back. | N/A | general | verify-check |
| R18 | [1/4] | 🟡 | 3 touched test(s) pass against the pre-change code: test_a_fenced_h2_line_does_not_end_the_findings_section, test_an_indented_fence_still_quotes_its_rows, test_a_closer_with_trailing_text_still_closes_the_fence | skills/run-autopilot/cli/test_gate_findings_shapes.py | general | mech-check |
| R19 | [1/4] | 🟡 | 7 touched test(s) pass against the pre-change code: test_both_verbs_refuse_every_sweep_payload +1 more | skills/run-autopilot/cli/test_main_review_close_validation.py | general | mech-check |
| R20 | [1/4] | 🟡 | 2 touched test(s) pass against the pre-change code: test_carry_on_critical_without_requeued_task_is_refused, test_ghost_carry_ref_is_refused | skills/run-autopilot/cli/test_review_close.py | general | mech-check |
| R21 | [1/4] | 🟡 | 12 touched test(s) pass against the pre-change code: test_close_adds_one_task_per_group, test_close_is_idempotent, test_close_records_doubt_verdicts, test_close_group_uses_emoji_severity_not_english_word, test_close_idempotency_check_is_inside_the_transaction, test_close_decision_gate_and_tail_sweep_batches_are_independently_idempotent +6 more | skills/run-autopilot/cli/test_review_close_apply.py | general | mech-check |
| R22 | [1/4] | 🟡 | 4 touched test(s) pass against the pre-change code: test_a_requeued_d_task_with_correct_stamps_backs_a_carry, test_a_fresh_d_task_with_no_escalation_reason_is_refused, test_carry_refusal_names_no_task_lists_the_ref_when_no_candidate_exists, test_carry_refusal_names_no_usable_ref_for_a_ref_less_row | skills/run-autopilot/cli/test_review_close_carry.py | general | mech-check |
| R23 | [1/4] | 🟡 | 3 touched test(s) pass against the pre-change code: test_tail_sweep_refuses_an_open_deferral, test_deferred_entries_carry_cycle_and_action, test_tail_sweep_reports_no_lenses_closed | skills/run-autopilot/cli/test_review_close_lowsev.py | general | mech-check |
| R24 | [1/4] | 🟡 | 16 touched test(s) pass against the pre-change code: test_tail_sweep_refuses_a_carry_row_ahead_of_its_other_checks, test_tail_sweep_refuses_a_row_duplicating_an_open_deferral, test_tail_sweep_duplicate_deferral_match_is_severity_vocabulary_agnostic, test_a_clean_tail_sweep_still_applies +10 more | skills/run-autopilot/cli/test_review_close_tail_sweep.py | general | mech-check |

Consolidation note: `consolidate_findings.py` produced R1-R16; it merged the
`datetime.UTC` 🟠 from Bob and Carl onto Alice's reflow row (same file
citation after suffix stripping), so R1's text above was rewritten to lead
with the reproduced 3.10 breakage rather than the formatting. R17 is the
carry-forward, R18-R24 the absorbed `[MECH]` fail-first replay lines.

## Alice

Consensus lens, engine `legacy`. Eight findings: four 🟡 (the unresolved
no-verdict literal duplication, the 835-line test file, the partly-fixed
self-referential assertions, the single-candidate closest-task test) and four
⚪ (the partly-fixed second-table escape, the returned formatter reflow
including the `datetime.UTC` hunk, a now-misnamed test, and one
simplification).

Resolved from cycle 1, in her verification: R1, R2, R3, R4, R5, R6, R8, R11,
R13 (shell), R14, R16. Not resolved: R7, R9 (partial), R10, R15 (worse), R17
(partial).

Ran: pytest over 12 gate / review_close / review_stage_paths modules - 317
passed, 0 failed, 0 skipped. Not run: `test_gather_context_id.sh` (warden
blocks it by name).

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

## Blake

Blind lens, PRD-only. Five findings: one 🟡 (an inline triple-backtick line
such as ```` ```x``` mention ```` opens a fence, so a later fence line closes
it and a real 🔴 table between them reads as quoted - the "CRITICAL leaves
with no task" class the PRD closes) and four ⚪ (a blank line between data
rows now refused with a misleading "did not read" detail, a repeated-header
second table refused by the generic `unreadable-table` text instead of the
spec'd line detail, two cosmetic spec deviations, and the broken file budget).

He verified compliant: the exit routing, the no-verdict refusal ordering, the
staging escape exit 2, the path-refusal shape, the version-skew hint, the
carry match and closest-task ranking, the `gather-context.sh` `^{commit}` and
unswallowed diff failures, and every prose/record item including the rewritten
CHANGELOG. He also ran `bash dev/bin/release-checks` himself:
`PASS 2943 FAIL 0 SKIP 0 EXIT 0`, plus 327 tests and nine refusal probes.

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

Doubt lens + de-slop (codex, exit 0; cycle-1 thread resumed via
`--resume-thread`, same id re-emitted for cycle 3). Ten FIX findings, led by
the 🟠 `datetime.UTC` 3.10 break, then the blank-line consumption
disagreement, the unresolved no-verdict literal, two partly-fixed test
weaknesses, the 60-line `_carry_reason`, the duplicated `_covered`/`_table`
helpers with the 835-line file, and the idempotency test that no longer
proves idempotency.

FIX: the 🟠 3.10 break, gate.py:563 blank-line reset, prior R7, prior R9
(partial), prior R10, `_carry_reason` length, the test-helper duplication and
file budget, the idempotency test, prior R17 (⚪), prior R13 (⚪).
VERIFY: `bash dev/bin/release-checks` after corrections (queued in
`00269-sweep-every-findings-token-v1-checks-2.json`).
KNOWN: (none)

D1: pass
D2: pass
D3: pass
D4: pass
D5: pass

## Carl

Gemini (copilot backend, model `gemini-3.8-flash`). Two findings, and he is
the one who proved the 🟠: `uv run --python 3.10 python -m cli --help` fails
with `ImportError: cannot import name 'UTC' from 'datetime'` at
`__main__.py:243`. His second is the 60-line `_carry_reason`, matching Bob.

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

Verdict: 24 findings
Tests: 2943 passed, 0 failed, 0 skipped (suite run this cycle)
