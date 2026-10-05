---
prd: 00256-finish-the-review-verbs-before-release-v1.md
cycle: 2
date: 2026-10-05
head_sha: 6bca6b5f3b85bfb7cea36edd9a05ec6a8cd36d7c
codex_thread_id: 01a10994-c52c-7de1-ba77-bd20b4060edb
reviewers: alice,blake,bob,carl
---

# Review: 00256-finish-the-review-verbs-before-release-v1

Diff range: `b4c071ddd8a0b48fa5a1ac3439145f4e4a06ae56..6bca6b5f3b85bfb7cea36edd9a05ec6a8cd36d7c`
Scope: incremental review (cycle 2), the rework commits since cycle 1 (tasks 8-12).
pack: `docs/dev/tmp/engram-pack-00256-c2.md` (2841 tokens)

codex_rung_guard: not fired

## Review Summary

Reviewed: 12 completed tasks (tasks 8-12 are this cycle's rework; tasks 1-7 were reviewed in cycle 1)
PRDs checked: 00256-finish-the-review-verbs-before-release-v1.md

### Agent Status
- Alice: ✅ Available (consensus lens, legacy engine)
- Blake: ✅ Available (blind lens, PRD-only)
- Bob: ✅ Available (codex, doubt rubric D1-D5 + de-slop; resumed his cycle-1 thread `01a10994`)
- Carl: ✅ Available (gemini via copilot backend)

Eve did not run: `doubt_reviewer` resolves to `codex` and no task was implemented by codex, so the doubt-roster guard did not fire.

**What the rework closed.** All three implementation-aware reviewers and the blind lens agree the cycle-1 🔴 is fixed: `_table_keys` reads the pipe table by header name, with and without the `Ref` column, and `convergence.py` imports `TABLE_DATA_ROW_RE` from `gate.py` with no import cycle. All four cycle-1 🟠 rows are fixed too (release-checks exit status, `run_gate` at 47 lines, the `proc.wait` deadline via `_reap`, and `reuse_verdict` refusing a failed record with a docstring that states the rule it applies).

**Orchestrator correction, stated loud.** The mechanical-blocks file this session wrote (`docs/dev/tmp/review-mech-00256-c2.md`) asserted `review_stage.py` is 800 lines. That figure was not measured and is wrong: `wc -l` gives **802**. Alice caught it. Carl's `R13: pass` was returned against that bad figure. Treat the 802 row below as the measured fact.

## Consolidated Findings

| Ref | Consensus | Severity | Issue | File | Task | Found By |
|-----|-----------|----------|-------|------|------|----------|
| R1 | [1/4] | 🔴 | **The PRD's own exit criterion is false at HEAD.** `bash dev/bin/release-checks` exits 1, measured twice in this session with no concurrent reviewer suites: `PASS 2590 FAIL 1 SKIP 0 EXIT 1`. The single failure is `test_no_gate_parses_porcelain_by_hand`, tripped by `skills/run-autopilot/cli/fixtures/00256-review-1.md` — a fixture **this cycle's task 12 added** (commit dbe0ad5; the path does not exist at the cycle-1 head b4c071d). The prose test predates this PRD (00236). The fixture copies a real review file whose quoted finding text contains `git status --porcelain`, which the prose scan forbids outside its allowlist. PRD Success Metric 1 is "Every named test below passes, and `bash dev/bin/release-checks` exits 0", and the PRD Risks say "Blocks the 0.9.0 release until done". The prior session's handoff recorded this as a "pre-existing unrelated failure"; it is neither pre-existing nor unrelated. Fix: exempt the fixture path in `test_store_tree_prose.py`'s `_EXEMPT`, or exclude `cli/fixtures/` from `_prose_files()`. | skills/run-autopilot/scripts/test_store_tree_prose.py | 12 | gate-run (orchestrator measurement) |
| R2 | [1/4] | 🟠 | The PRD Test Strategy error case says "findings JSON drops one table row -> gate exits 2". `_cross_check_findings` is deliberately one-directional (subset). A JSON missing a table row exits 0, and `test_gate_accepts_matching_findings_json` plus the "subset is fine" tests pin that. The design doc (designs/00256-...-design.md:198-210) chose this, but the PRD text conflicts with it and is unreconciled. | skills/run-autopilot/cli/gate.py:386 | general | BLAKE |
| R3 | [1/4] | 🟠 | Scope beyond the PRD. The Ref-column mechanism (a new "ref" field matched by `_backed`) was added. It changed `consolidate_findings.py` output, `TABLE_DATA_ROW_RE`, `convergence.py`, `output-formats.md` and `phase-review.md`. `review_close.close()` now runs the cross-check itself and returns a new `refused: "findings_mismatch"` result, and the CLI exits 2 on it. The result also gains a `findings_cross_check: "malformed"` key. The PRD asks for none of these. The design doc sanctions them, but they are new behavior and a changed review-table format. | skills/run-autopilot/cli/gate.py:358 | general | BLAKE |
| R4 | [1/4] | 🟠 | FIX: `run_pytest` checks whether `f` is empty, not zero. Output containing `3 passed, 0 failed` with exit 1 still produces EXIT 0. Use a numeric zero check and add that regression case. **Confirmed by reading the code this session:** `release-checks:55` is `if [[ "$rc" -ne 0 && -z "$f" ]]`, while the sibling `run_harness:74` uses the numeric `if [[ "$rc" -ne 0 && "$f" -eq 0 ]]`. The two helpers guard the same fail-open condition inconsistently, and the numeric form is the safe one. | dev/bin/release-checks:55 | 8 | BOB |
| R5 | [2/4] | 🟡 | A header-only findings table with no rows (a hand-written empty table) returns `unreadable-table`. `gate --findings` with an empty JSON array then exits 1 instead of 0. The cycle-1 design says an empty set is valid, not malformed. Reproduced with `_cross_check_findings(<header-only table>, [])`, which returned `('malformed', ...)`. `consolidate_findings.py` emits no table when there are zero findings, so real files are unaffected. `test_empty_findings_is_not_malformed` only covers the bullet-heading shape. | skills/run-autopilot/cli/gate.py:329 | 12 | ALICE, BOB |
| R6 | [1/4] | 🟡 | `review_stage.py` is 802 lines, not 800, so task 11's acceptance ("800 lines or fewer") is unmet. `wc -l` and `rg -c ""` both give 802, and `git diff b4c071d HEAD --numstat` shows +7/-6, net +1 on the cycle-1 head's 801. The 800-line cap in R13 is still breached. | skills/run-autopilot/cli/review_stage.py:749 | 11 | ALICE |
| R7 | [1/4] | 🟡 | `_replay_base` still derives a second base (`merge-base HEAD <recorded base>`) and its one-line comment ("Not a 2nd resolver: anchors gather-context.sh's own base (7b1f589)") does not explain why that equals what gather-context resolved. `gather-context.sh:76-81` and `:112` diff against the base ref itself, with no merge-base step. The task allowed either using the recorded base as-is or one line stating why they agree. The comment asserts the second without showing it. | skills/run-autopilot/cli/review_stage.py:750 | 11 | ALICE |
| R8 | [1/4] | 🟡 | `_lens_states` closes a persona that is absent from `agents:` as `"failed"` (`setdefault`). A run where Carl or Eve were never rostered, and so never stamped, gets phantom `ui: failed` and `fable: failed` keys in `state.review_lenses`. That contradicts SKILL.md:81 ("no `ui` key ... when step 3 replaces the lens"). | skills/run-autopilot/cli/review_close.py:138 | general | BLAKE |
| R9 | [1/4] | 🟡 | `review_lenses` can now take the value `"skipped"` (for `disabled`). `state-schema.md:216` and `tracon/model.py:281` document only running\|done\|failed, so the vocabulary is unreconciled. | skills/run-autopilot/cli/review_close.py:44 | general | BLAKE |
| R10 | [1/4] | 🟡 | Suspected (Blake could not run his reproduction; the write-scope hook blocked it), so unconfirmed. `_ancestor_and_clean` checks committed paths with `git log --name-only`, which prints only the NEW path of a rename. A committed `git mv src/x docs/dev/project-management/x` would look clean, because the deleted source outside the store is never seen. The PRD only asks for the porcelain rename fix, which is done. | skills/run-autopilot/cli/verification.py:80 | general | BLAKE |
| R11 | [1/4] | 🟡 | FIX: Truncated rows that reach the File column but omit trailing columns pass the length guard and enter the embedded-pipe reconstruction branch, corrupting Issue/File. Reject rows shorter than their header before reconstructing excess cells. | skills/run-autopilot/cli/gate.py:283 | 12 | BOB |
| R12 | [1/4] | 🟡 | FIX: A matching ref returns before the empty-issue guard, so a chosen finding with `issue: ""` passes and can create an empty task description. Apply the nonempty normalized-issue requirement before either matching branch. | skills/run-autopilot/cli/gate.py:374 | 12 | BOB |
| R13 | [1/4] | 🟡 | FIX: The replay reports three new parser tests passing at base: `test_a_truncated_data_row_is_malformed_not_a_crash`, `test_cross_check_still_refuses_a_different_finding_about_the_same_file`, and `test_escaped_pipe_in_a_table_cell_keys_like_an_unescaped_one`. Strengthen their discrimination or document justified preservation of existing behavior. | skills/run-autopilot/cli/test_gate_findings_table.py:272 | 12 | BOB, mech-check |
| R14 | [1/4] | 🟡 | [MECH] 1 touched test passes against the pre-change code: `test_blake_reraising_a_settled_deferral_is_auto_dismissed`. | skills/review-work-completion/scripts/test_consolidate_findings.py | general | mech-check |
| R15 | [1/4] | 🟡 | [MECH] 1 touched test passes against the pre-change code: `test_bad_findings_file_fails_cleanly_without_a_traceback` — the very test task 11 was asked to make discriminating. It no longer passes for the argparse reason, but it still passes at the cycle-1 head. | skills/run-autopilot/cli/test_gate.py | 11 | mech-check |
| R16 | [1/4] | 🟡 | [MECH] 3 touched tests pass against the pre-change code: `test_nonzero_exit_keeps_the_real_failed_count`, `test_harness_without_summary_line_counts_one_pass_per_clean_exit`, `test_harness_without_summary_line_counts_one_fail_per_bad_exit`. | skills/run-autopilot/cli/test_release_checks_counts.py | 8 | mech-check |
| R17 | [1/4] | 🟡 | [MECH] 3 touched tests pass against the pre-change code: `test_close_applies_a_findings_subset_of_the_review`, `test_cli_exits_1_when_the_review_itself_fails_the_gate`, `test_cli_still_exits_1_on_other_not_applied_reasons`. | skills/run-autopilot/cli/test_review_close.py | general | mech-check |
| R18 | [1/4] | ⚪ | The timed-out gate still prints `Tests: 0 passed, 0 failed, 0 skipped (suite timed out ...)`. Task 11 listed this finding and its acceptance says every quoted finding no longer reproduces, but the code is unchanged. The only record is a deferral line in `meta/assumptions.md:198`. The comment at line 367 explains why (`TESTS_RE` needs counts). If this stays, record it as an accepted deferral rather than listing it as closed. | skills/run-autopilot/cli/review_stage.py:372 | 11 | ALICE, BOB |
| R19 | [1/4] | ⚪ | Task 10 required either a fail-at-base result or a one-line pass-at-base note per test. `test_rename_into_store_from_production_is_not_clean`, `test_copy_record_checks_both_paths` and `test_blank_status_column_does_not_desync_fields` pass at the cycle-1 head and carry no note; only `test_run_gate_drains_stderr_without_deadlock` (line 201) and `test_run_gate_uses_last_summary_line_not_first` (line 393) do. | skills/run-autopilot/cli/test_verification.py:168 | 10 | ALICE |
| R20 | [1/4] | ⚪ | `_lens_states` marks every persona missing from `agents:` as `failed`, including a lens the roster never stamped, such as Carl on a non-UI PRD whose file omits him. That writes `review_lenses.ui = failed` for a lens that never ran, and tracon panels read that state. An unproven side effect rather than a confirmed bug. | skills/run-autopilot/cli/review_close.py:136 | 11 | ALICE |
| R21 | [1/4] | ⚪ | `test_summary_line_printed_on_failure` and the other count tests re-implement the EXIT_CODE and summary lines inside the test body. They source only the helpers, so a regression in the real script's final summary or exit block would not fail them. | skills/run-autopilot/cli/test_release_checks_counts.py:48 | general | BLAKE |
| R22 | [1/4] | ⚪ | Several tests in `test_review_close.py` and `test_review_stage.py` carry comments saying they "pass against the pre-change code too", e.g. `test_close_leaves_no_lens_running`. They do not prove the regression the PRD names. | skills/run-autopilot/cli/test_review_close.py:660 | general | BLAKE |
| R23 | [1/4] | ⚪ | Cannot statically verify: VERIFY cycle-2 acceptance tests and `bash dev/bin/release-checks` exit 0; run the gate without concurrent suites that mutate repository state. **Discharged this cycle:** queued in `-checks-2.json` and run — exit 1 (see R1). | N/A | general | BOB |

Consolidation ran `consolidate_findings.py` over four reviewer outputs with `--ledger ... --ledger-dismiss BLAKE`; it merged Alice's and Bob's empty-table rows (R5) after suffix stripping. Four `mech-check` replay lines the table did not already cover were absorbed by hand per the skill's mechanical-check rule (R14-R17); two folded onto existing rows as extra finders (R13, and Alice's R19 row). R1 is this session's own measurement, added before the `Verdict:` line was composed.

### Discarded this cycle

- None. Nothing in the three settled-ledger entries was re-raised: `--ledger-dismiss BLAKE` dismissed nothing, and no implementation-aware reviewer re-litigated a settled call.

## Alice

Six findings (two 🟡, four ⚪) plus a verified pass on every cycle-1 🔴/🟠 row. She ran 8 narrow test files: 215 passed, 39 subtests passed. She did not run `release-checks` (concurrency note), so her report leaves the gate unverified — this session measured it instead. Her sharpest catch is the 802-line measurement that refutes the orchestrator's own mechanical-block figure; she reproduced it three ways (`wc -l`, `rg -c ""`, and the diff's net +1 on 801).

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
R13: fail

## Blake

Seven findings (two 🟠, three 🟡, two ⚪), none dismissed by the ledger. From the code alone he confirmed every Phase 0/1/2 item implemented, the 00255 hold stub gone, `_DISPATCH_OUTCOME["unavailable"] == "error"`, both emoji in `SEVERE`, `resolve_base` gone, Bob's appendix unconditional, `_eve_inputs` on `prd_body`, and renames judged by both paths. He ran 16 named tests plus two narrow sets: 189 and 142 passed. He declined the full gate per the concurrency note and reported its exit as unverified rather than as a finding — the correct call, and the opposite of his cycle-1 mistake. His two 🟠 are both spec-vs-design reconciliation gaps, not code defects.

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

Six findings and one VERIFY, resumed on his cycle-1 codex thread (`--resume-thread 01a10994`), static-only sandbox so he ran nothing. His 🟠 on `release-checks:55` is a genuine fail-open inconsistency this session confirmed by reading both helpers. His VERIFY named an exact command and was queued to `-checks-2.json`, then discharged here: exit 1.

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
R13: pass
D1: pass
D2: pass
D3: pass
D4: pass
D5: pass

## Carl

No issues found, all twelve rubric rules pass. Backend: copilot (`gemini-run.sh`, exit 0). He read the context, diff, mechanical blocks and pack, ran the 8 touched test files plus `test_convergence.py`, checked `import cli.gate` in isolation, and grepped the diff for TODO/FIXME/breakpoint markers (none). **Caveat on his `R13: pass`:** it was returned against the orchestrator's incorrect 800-line figure for `review_stage.py`; the measured value is 802, so R13 is in fact a fail (Alice's R6).

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

## Follow-up Tasks Created

None. `state.cycle` (2) has reached `state.rework_cap` (2), so Phase 5's cap check routes this cycle to the cap-out path and no rework pass runs — a task created here would never be dispatched. Every finding above is recorded instead: R1 as the `cap_critical` stall that sidelines this PRD, R2-R23 as cap-overflow deferrals. This is a deliberate deviation from step 7's task-creation instruction, stated here rather than left silent.

Verdict: 23 findings
Tests: 2590 passed, 1 failed, 0 skipped (suite run this cycle)
