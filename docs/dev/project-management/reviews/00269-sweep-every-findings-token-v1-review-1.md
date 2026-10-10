---
prd: 00269-sweep-every-findings-token-v1.md
cycle: 1
date: 2026-10-10
head_sha: ee019d36f6f3850ee3e8640eedfebc7dc66d2af7
codex_thread_id: 01a12535-e793-71d3-b69e-2ef34b62bff6
reviewers: alice,blake,bob,carl
---

# Review Cycle 1 - 00269-sweep-every-findings-token-v1

Scope: full review
Diff range: 11da57c15b4f3323bb38a5993866f7e6bd27b2e6..ee019d36f6f3850ee3e8640eedfebc7dc66d2af7

codex_rung_guard: not fired

Pack: ok
Tasks: 14/14 completed

**Consolidation note (fail loud).** The first `consolidate_findings.py` run
dropped every one of Bob's eight findings silently. Cause: the installed
pack copy (`autopilot/0.9.0`) matches `_LINE_RE` from line start with no
bullet tolerance, while Bob's doubt persona emits bulleted FIX/VERIFY/KNOWN
lines; the repo working copy already carries the `(?:[-*]\s+)?` prefix, so
this is installed-vs-repo version skew, and the installed copy also lacks the
"unparsed finding-shaped line" warning that would have surfaced it. Bob's
output file was normalized to the documented `[BOB] ...` line contract and the
consolidation re-run, after which Bob appears in R1, R3, R6, R9, R10, R18 and
R19. The table below is the re-run's output, produced by the script, not by
hand.

## Consolidated Findings

| Ref | Consensus | Severity | Issue | File | Task | Found By |
|-----|-----------|----------|-------|------|------|----------|
| R1 | [4/4] | 🟠 | review-close still legacy-applies a review file with no findings section, no token and a NON-EMPTY findings JSON, while `gate --findings` exits 2 on the same pair. `_findings_refusal` exempts any detail starting with `no '## Consolidated Findings' section` (a prefix match), so the new "yet the findings JSON names k rows" detail slips through. The PRD and design say only the exact `no-section` text may pass, and the PRD makes `test_a_missing_section_with_findings_rows_is_refused` the acceptance test. I ran it: `findings_verdict` returns `malformed` with that detail both for a bare file and for a file whose whole findings table sits inside a closed fence. Gate exits 2 for both, and review-close applies the batch unchecked. | skills/run-autopilot/cli/review_close.py:587 | 3 | ALICE, BLAKE, BOB, CARL |
| R2 | [3/4] | 🟠 | `test_a_missing_section_with_findings_rows_still_applies_as_legacy` pins the opposite of the PRD contract. It replaces the required `test_a_missing_section_with_findings_rows_is_refused`, asserts `code == 0`, and passes against the pre-change code (the fail-first replay flags it). `test_both_verbs_refuse_every_sweep_payload` is parametrized over only 3 payloads (unreadable table, repeated heading, one stray token). The PRD says it covers the Phase 0 payloads, which include heading typos, bullets, comment rows and the 00268 shape. No review-close CLI test covers a heading typo or no heading. | skills/run-autopilot/cli/test_main_review_close_validation.py:235 | 3 | ALICE, BLAKE, CARL, mech-check |
| R3 | [3/4] | 🟡 | `review_close.close()` is now 62 lines (def at line 617 through the return at line 678), over the 50-line limit. The added `pre_text` read-and-check block (lines 640-652) is the cause. Simpler: move it into a small helper, or give `_gate_review` a way to report the missing verdict. The block also reads the file twice, once here and once in `_gate_review`. | skills/run-autopilot/cli/review_close.py:638 | 4 | ALICE, BOB, CARL |
| R4 | [2/4] | 🟡 | The rewritten CHANGELOG claim is false for the deviation above: "review-close refuses, exit 2, every findings file gate --findings refuses with exit 2". The no-section-plus-rows case contradicts it. This was the false-claim correction the PRD asked for, and it needs to be true once finding 1 is fixed. | CHANGELOG.md:14 | 13 | ALICE, BLAKE |
| R5 | [2/4] | 🟡 | `_stage_inputs_from_state` grew to 53 lines (def at line 937 through the return dict at line 989), over the 50-line limit. Simpler: a helper that returns the two refusal lines, or a loop over (field, raw, resolved, boundary) tuples. | skills/run-autopilot/cli/__main__.py:937 | 8 | ALICE, CARL |
| R6 | [1/4] | 🟠 | An unclosed four-backtick opener followed by a three-backtick pair around a CRITICAL row hides that row: scanning resumes after the unmatched opener and blanks the inner pair. The contract requires every remaining line to stay live. Stop fence scanning when an opener has no closer; add both-verb regression coverage. | skills/run-autopilot/cli/gate.py:518 | 1 | BOB |
| R7 | [1/4] | 🟡 | The no-verdict reason text is restated as a literal. The design says to reuse the exact string `gate.check` produces, and `gate.py:218` holds the same literal. Expose it as a `gate` constant and import it so the two cannot drift. | skills/run-autopilot/cli/review_close.py:648 | 4 | ALICE |
| R8 | [1/4] | 🟡 | Section-bounds logic is written three times: heading search plus `_NEXT_H2_RE` in `_reviewed_keys` (gate.py:419-425), again in `_unread_token` (gate.py:535-543), and a `findall` in `_malformed_detail`. `_reviewed_keys(live)` is also parsed twice per call, at gate.py:571 and gate.py:608 (the result of the first is discarded). Return the rows from `_malformed_detail`, or hoist the section slice into one helper, so the consumed-set and the parser cannot drift. | skills/run-autopilot/cli/gate.py:527 | 1 | ALICE |
| R9 | [1/4] | 🟡 | The test `_carry_reason` helper now calls production `_carry_reason`, so refusal-message assertions compare the implementation against itself. Restore independently specified expected strings so incorrect messages fail tests. | skills/run-autopilot/cli/test_review_close.py:181 | 6 | BOB |
| R10 | [1/4] | 🟡 | The closest-task test supplies only `[task]`; it cannot detect incorrect ranking or tie-breaking. Add multiple candidates with different first failures, then equal-rank candidates in both orders, asserting the exact selected task and reason. | skills/run-autopilot/cli/test_review_close_carry.py:332 | 6 | BOB |
| R11 | [1/4] | 🟡 | Simplification: run[0] * len(run) redundantly reconstructs run from _FENCE_RE match; startswith(run) is simpler | skills/run-autopilot/cli/gate.py:516 | 1 | CARL |
| R12 | [1/4] | ⚪ | Unrelated formatter reflow of pre-existing tests, from the end-of-turn reformat. Hunks: `test_duplicate_table_ref_is_refused_wherever_the_pair_sits`, `test_an_indented_data_row_under_a_valid_header_is_still_read` and `test_a_data_row_missing_its_closing_pipe_is_refused`. Revert them to keep the diff surgical. | skills/run-autopilot/cli/test_gate_findings_shapes.py:156 | 1 | ALICE |
| R13 | [1/4] | ⚪ | The "a failing diff exits non-zero" harness case sends stdout to /dev/null (`2>&1 >/dev/null`). It never asserts the PRD's "prints no file paths on stdout". | skills/review-work-completion/scripts/test_gather_context_id.sh:664 | 9 | ALICE |
| R14 | [1/4] | ⚪ | `_carry_reason` indexes `fields[_rank(best)]`. If a caller passes a task that satisfies all four conditions, the rank is 4 and this raises IndexError. Today it is only reachable after `_carry_unmatched` is True, so it is latent. A guard or a comment stating the precondition would help. | skills/run-autopilot/cli/review_close.py:1115 | 6 | ALICE |
| R15 | [1/4] | ⚪ | `test_review_close.py` grew from 764 to 784 lines, against the design's "stays untouched at 764" budget. It is still under 800. The `_findings_refusal` docstring ("A review file carrying no such section is not refused") is stale for the new rules. | skills/run-autopilot/cli/test_review_close.py:1 | general | ALICE |
| R16 | [1/4] | ⚪ | Stale prose contradicts the spec. The `_FINDINGS_REFUSALS` comment, the `_NO_SECTION_PREFIX` comment and the `_findings_refusal` docstring all describe the prefix exemption. The `close()` docstring still says "re-queued `[C{cycle}]` task", although the carry rule no longer names a prefix. | skills/run-autopilot/cli/review_close.py:71 | general | BLAKE |
| R17 | [1/4] | ⚪ | A table-looking second block can slip past the sweep, though only in an odd case. `_unread_token` sets `in_table` once and never resets it, so every later pipe line in the section counts as read. `_table_keys` then treats a second header row as a data row. If the first header has neither a `ref` nor a `consensus` column, as with `| Severity | Issue | File |`, the second header is read as a row (severity "severity") instead of being refused. A second table with the same columns is therefore accepted rather than refused. With the usual Ref/Consensus headers it is refused. Low severity because it needs a Ref-less table, which the coverage batches refuse anyway; the tail-sweep batch is the only one that would let it through. | skills/run-autopilot/cli/gate.py:545 | gate: fence-aware scan | BLAKE |
| R18 | [1/4] | ⚪ | Cannot statically verify: tests and release checks pass. Run `bash dev/bin/release-checks` after corrections; the supplied context reports 2936 passing tests, but this review executed none. | N/A | general | BOB |
| R19 | [1/4] | ⚪ | `__main__.py` has 1703 lines and `review_stage.py` has 815, exceeding 800. Both already exceeded the limit before this diff; splitting these modules is outside this bounded refusal-fix PRD. | skills/run-autopilot/cli/__main__.py:1 | general | BOB |
| R20 | [1/4] | 🟡 | 8 touched test(s) pass against the pre-change code: test_duplicate_table_ref_is_refused_wherever_the_pair_sits, test_each_findings_verdict_exits_by_its_own_tag, test_an_indented_data_row_under_a_valid_header_is_still_read, test_a_data_row_missing_its_closing_pipe_is_refused +2 more | skills/run-autopilot/cli/test_gate_findings_shapes.py | general | mech-check |
| R21 | [1/4] | 🟡 | 1 touched test(s) pass against the pre-change code: test_a_findings_table_whose_rows_do_not_match_is_malformed | skills/run-autopilot/cli/test_gate_findings_table.py | general | mech-check |
| R22 | [1/4] | 🟡 | 6 touched test(s) pass against the pre-change code: test_cli_accepts_a_carry_classification, test_cli_exits_1_when_the_review_itself_fails_the_gate, test_a_missing_section_with_no_tokens_and_no_findings_still_applies_as_legacy, test_tail_sweep_refused_before_decision_gate_applied, test_tail_sweep_refuses_rows_above_medium | skills/run-autopilot/cli/test_review_close.py | general | mech-check |
| R23 | [1/4] | 🟡 | 14 touched test(s) pass against the pre-change code: test_carry_unmatched_matches_only_a_live_this_cycle_requeued_task +8 more | skills/run-autopilot/cli/test_review_close_carry.py | general | mech-check |

## Alice

Consensus lens, engine `legacy`. Twelve findings: the `_findings_refusal`
prefix-match deviation and the inverted acceptance test as 🟠, then the false
CHANGELOG claim, three over-50-line functions, a duplicated no-verdict
literal, thrice-written section-bounds logic and the prefix coupling as 🟡,
plus four ⚪ (the formatter reflow, a stdout assertion gap in the shell
harness, a latent `_carry_reason` IndexError, and a stale docstring with the
test-file line budget).

She ran: the seven core pytest modules for gate / review_close / validation
(232 passed, 0 failed, 0 skipped), `test_review_verbs_prose.py` (10 passed),
`test_gather_context_id.sh` (all PASS), and a base-overlay run confirming the
`repeated-section` and `unread-token` sweep params and the blob `--since`
case fail against the pre-change tree. `gate.py` is 755 lines; this leaves a
temp copy at `/tmp/alice-base-x` for manual deletion.

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
R12: fail
R13: pass

## Blake

Blind lens, PRD-only. Six findings, reached without the diff: the same
`_findings_refusal` prefix exemption (reproduced directly against
`gate.findings_verdict` and `review_close._findings_refusal`), the missing
PRD-mandated `test_a_missing_section_with_findings_rows_is_refused`, the
under-parametrized both-verbs sweep test, the false CHANGELOG claim, stale
prose across three comments and a docstring, and a Ref-less second-table
escape in `_unread_token`.

He also listed fourteen spec points he verified as correctly implemented,
including the fence-aware scan, the live-only section bounds, the exit-1
no-section equality routing, the ref-required hint text, the `no_verdict`
ordering, the path-refusal shape and the `gather-context.sh` `^{commit}` fix.
Note that his "an unclosed fence quotes nothing" verification is narrower
than it reads - see R6, which this gate verified as real.

Not run: pytest was unavailable in his environment and warden blocked
`test_gather_context_id.sh` by name; his findings come from reading the code
plus direct Python repros.

B1: fail
B2: pass
B3: fail
B4: pass
B5: fail
B6: pass
B7: pass
B8: pass
B9: pass
B10: fail
B11: pass
B12: pass
B13: pass
B14: pass
B15: fail
B16: pass
B17: pass
B18: pass
B19: pass

## Bob

Doubt lens + de-slop (codex, exit 0; thread id captured for cycle 2 resume).
Eight findings across FIX / VERIFY / KNOWN. His FIX bucket carries the
prefix-exemption 🟠 and one finding no other reviewer reached: the unclosed
four-backtick opener followed by a three-backtick pair, which blanks an inner
🔴 row while the unmatched opener itself stays live (R6). This gate verified
that repro independently - `_unfenced` blanks the CRITICAL row and
`_unread_token` returns `None`, so the row escapes the sweep entirely. His
remaining FIX items are two self-referential or single-candidate test
weaknesses and two simplifications.

FIX: R1, R6, R9, R10, R3, and the over-50-line pair.
VERIFY: `bash dev/bin/release-checks` after corrections (queued in
`00269-sweep-every-findings-token-v1-checks-1.json`).
KNOWN: `__main__.py` at 1703 lines and `review_stage.py` at 815, both already
over 800 before this diff and out of scope here.

D1: pass
D2: pass
D3: pass
D4: pass
D5: pass

## Carl

Gemini (copilot backend). Six findings, agreeing with the panel on the
prefix-match 🟠 and the inverted acceptance test 🟠, the three over-50-line
functions, and one simplification of his own: `run[0] * len(run)` rebuilds the
fence run the `_FENCE_RE` match already holds, where `startswith(run)` would
do.

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
R12: fail
R13: pass

Verdict: 23 findings
Tests: 2936 passed, 0 failed, 0 skipped (suite run this cycle)
