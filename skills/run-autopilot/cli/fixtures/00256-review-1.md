---
prd: 00256-finish-the-review-verbs-before-release-v1.md
cycle: 1
date: 2026-10-05
head_sha: b4c071ddd8a0b48fa5a1ac3439145f4e4a06ae56
codex_thread_id: 01a10994-c52c-7de1-ba77-bd20b4060edb
reviewers: alice,blake,bob,carl
---

# Review: 00256-finish-the-review-verbs-before-release-v1

Diff range: `540edd9e98dce6319c2946b21f5c4890658b454a..b4c071ddd8a0b48fa5a1ac3439145f4e4a06ae56`
Scope: full review (cycle 1), the PRD's whole work range.
pack: `docs/dev/tmp/engram-pack-00256-c1.md` (3572 tokens)

codex_rung_guard: not fired

## Review Summary

Reviewed: 7 completed tasks
PRDs checked: 00256-finish-the-review-verbs-before-release-v1.md

### Agent Status
- Alice: ✅ Available (consensus lens, legacy engine)
- Blake: ✅ Available (blind lens, PRD-only)
- Bob: ✅ Available (codex, doubt rubric D1-D5 + de-slop)
- Carl: ✅ Available (gemini via copilot backend)

Eve did not run: `doubt_reviewer` resolves to `codex` and no task was implemented by codex, so the doubt-roster guard did not fire.

## Consolidated Findings

| Consensus | Severity | Issue | File | Task | Found By |
|-----------|----------|-------|------|------|----------|
| [2/4] | 🔴 | The findings cross-check only parses the bullet shape `- [m/n] <sev> issue \| file \| Found by:` (gate.py:102, gate.py:217). Every saved review file in this repo uses the pipe table `\| Consensus \| Severity \| Issue \| File \| Task \| Found By \|`. phase-review.md:267 and phase-review.md:195 also tell the orchestrator to copy chosen findings from that table. On a real file `_reviewed_keys` returns an empty set (section present, zero rows), so every fix/defer row reports "mismatch". `close()` therefore refuses with exit 2 on essentially every real decision-gate and tail-sweep batch, which stops the review loop. No test uses a table-shaped review file, so the suite does not catch it. Blake independently raised the related one-direction gap (a findings JSON that drops a table row still passes). Fix: parse the pipe table too (Severity, Issue, File columns), or pin the review-file writer to the bullet shape and update the phase-review.md and design-solution/SKILL.md:69 wording. Add a test fed from a real review file. | skills/run-autopilot/cli/gate.py:102 | 5 | ALICE, BLAKE |
| [4/4] | 🟠 | `run_pytest` never checks pytest's exit status, so the release gate can pass with failures it does not count (a fail-open path, the PRD's stated concern). It only greps `N passed/failed/skipped`. Collection or setup errors alongside some passes, and xdist worker crashes, are all treated as green. Fix: when the block's exit code is non-zero and `f` is zero, set `INFRA_FAIL=1` (or add `errors` to `TOTAL_FAIL`). Add a test for that case. | dev/bin/release-checks:37 | 2 | ALICE, BLAKE, BOB, CARL |
| [3/4] | 🟠 | `run_gate` is 60 lines (verification.py:181-240, from the mechanical facts). The PRD says "under 50 lines per function" for it, and the design requires it explicitly. About 17 of those lines are docstring. | skills/run-autopilot/cli/verification.py:181 | 2 | ALICE, BOB, CARL |
| [2/4] | 🟠 | Closing both output pipes makes `_drain_bounded` report completion even while the process runs; the subsequent unbounded `proc.wait()` bypasses the timeout. Apply the remaining deadline to process exit and test a command that closes both pipes before sleeping. | skills/run-autopilot/cli/verification.py:224 | 2 | BOB, CARL |
| [1/4] | 🟠 | `reuse_verdict` accepts a record whenever passed/failed/skipped are non-null. It ignores `commands[0].exit` and `failed > 0`. `run_gate` writes the record even for a nonzero exit, and release-checks deliberately prints "FAIL 0 ... EXIT 1" on an infrastructure failure. The next cycle would reuse that record and certify a failed gate. This breaks the PRD's "never receives a count the gate did not measure". | skills/run-autopilot/cli/verification.py:124 | 2 | BLAKE |
| [1/4] | 🟠 | The `reuse_verdict` docstring still says it requires `git status --porcelain` to be empty and does not mention renames. The code allows dirty paths under the store and judges a rename by both paths. The PRD requires "the docstring states the rule the code applies". | skills/run-autopilot/cli/verification.py:111 | 2 | BLAKE |
| [3/4] | 🟡 | `test_run_gate_streams_and_keeps_tail` passes against the pre-change code (fail-first replay). The old `communicate()` plus `_cap` also kept the tail of an unbroken burst. It asserts only the parsed result, so it cannot fail if the drain stops being byte-bounded. | skills/run-autopilot/cli/test_verification.py:235 | 2 | ALICE, BOB, CARL, mech-check |
| [2/4] | 🟡 | This diff pushes `stage()` to 53 lines (review_stage.py:749-801), from 49, and the file to 801 lines. Extract `_replay_base(context, repo_root)` holding the scope lookup and the merge-base fallback. | skills/run-autopilot/cli/review_stage.py:779 | 4 | ALICE, CARL |
| [2/4] | 🟡 | `test_codex_run.sh` emits measured "SUMMARY: N passed, M failed" totals, but `run_harness` replaces them with one pass/fail per invocation. Add the mandated summary adapter and coverage for its real totals. | dev/bin/release-checks:138 | 2 | BOB, CARL |
| [2/4] | 🟡 | `test_bad_findings_file_fails_cleanly_without_a_traceback` passes against pre-change code because argparse rejecting `--findings` satisfies every assertion. Assert the specific file-read/JSON-validation diagnostic. | skills/run-autopilot/cli/test_gate.py:450 | 5 | BOB, CARL, mech-check |
| [1/4] | 🟡 | Rename and copy handling is under-tested relative to the PRD ("BOTH endpoints"). `test_rename_into_store_from_production_is_not_clean`, `test_copy_record_checks_both_paths`, `test_blank_status_column_does_not_desync_fields` and `test_run_gate_drains_stderr_without_deadlock` were all named in the design and not written. | skills/run-autopilot/cli/test_verification.py:146 | 2 | ALICE |
| [1/4] | 🟡 | Unrelated reformatting churn in this diff (test_verification.py:24-34, :110-116; test_review_close.py signature re-wraps, import reorder, trailing commas). These lines do not trace to the PRD. Loupe reflows edited `.py` files at turn end; revert that reflow rather than committing it. | skills/run-autopilot/cli/test_review_close.py | general | ALICE |
| [1/4] | 🟡 | Two sets of tests the PRD names are not wired into the release gate: `cli/test_gate.py` and `scripts/test_review_verbs_prose.py`. The gate can pass green with these regressed. | dev/bin/release-checks:276 | general | BLAKE |
| [1/4] | 🟡 | The replay base is not what `gather-context.sh` resolved. `stage()` takes the recorded scope and then runs `merge-base HEAD <base>`, so the two bases can differ. The PRD says the replay uses the base gather-context resolved, not a second resolver. Commit 7b1f589 added this deliberately. | skills/run-autopilot/cli/review_stage.py:781 | 4 | BLAKE |
| [1/4] | 🟡 | [MECH] 13 touched test(s) pass against the pre-change code: test_close_refuses_a_gate_failing_review_file, test_close_group_uses_emoji_severity_not_english_word, test_close_idempotency_check_is_inside_the_transaction, test_close_state_mutations_use_parse_path, test_close_uses_statectl_mutate_scoped_validator, test_close_maps_every_classification_row_to_a_chosen_finding_value +7 more | skills/run-autopilot/cli/test_review_close.py | 3 | mech-check |
| [1/4] | 🟡 | [MECH] 2 touched test(s) pass against the pre-change code: test_replay_cmd_never_receives_gate_command, test_replay_base_is_branch_point_when_scope_records_a_branch_name | skills/run-autopilot/cli/test_review_stage.py | 4 | mech-check |
| [1/4] | 🟡 | Beyond the PRD: `review_close.close()` now refuses with `refused: "findings_mismatch"`, `__main__` maps it to exit 2, and a "malformed" cross-check field is added. The PRD only requires `autopilot gate --review-file`. Design-approved, but new behaviour and a new refusal path in the close flow. | skills/run-autopilot/cli/review_close.py:336 | 5 | BLAKE |
| [1/4] | ⚪ | `_drain_bounded` never closes `proc.stdout` and `proc.stderr`, and `run_gate` does not either after `proc.wait()`. Close both in a `finally` or after the drain. | skills/run-autopilot/cli/verification.py:154 | 2 | ALICE |
| [1/4] | ⚪ | "Close every lens" depends on the review file listing all five personas under `agents:`. A hand-written file that omits Blake or Eve leaves those lenses `running`. There is no fail-safe in `_lens_states` or `close()`. | skills/run-autopilot/cli/review_close.py:129 | 3 | BLAKE |
| [1/4] | ⚪ | The timed-out gate prints a fabricated "Tests: 0 passed, 0 failed, 0 skipped (suite timed out ...)" line in the context file. Not written to `last-verification.json`, but it is an unmeasured count. | skills/run-autopilot/cli/review_stage.py:372 | general | BLAKE |
| [2/4] | ⚪ | Pre-existing file-size violations: `__main__.py` 1665 lines, `review_stage.py` 801. Settled for `__main__.py` (out of scope); the `review_stage.py` half is actionable this cycle. | skills/run-autopilot/cli/__main__.py | general | BOB, CARL |
| [1/4] | ⚪ | The hold stub 00255 was moved to `prds/done/` rather than deleted. `test ! -e` on the hold path passes, and this matches the standing close-stubs-into-done rule. | docs/dev/project-management/prds/done/00255-triage-resolve-base-is-a-second-diff-base-resol-v1.md | 7 | BLAKE |

Consolidation ran `consolidate_findings.py` over four reviewer outputs; it merged four citation groups after suffix stripping. The two `mech-check` replay rows for `test_review_close.py` and `test_review_stage.py` were absorbed by hand per the skill's mechanical-check rule; the other two replay lines folded onto existing rows as extra finders.

### Discarded this cycle

- 🟡 Blake: "`bash dev/bin/release-checks` exits 0 is not demonstrated; my run exited 1 in the `[checks] waves` block." **Discarded, refuted by measurement.** This session ran the gate itself at the reviewed HEAD: `PASS 2390 FAIL 0 SKIP 0 EXIT 0`. Blake's and Carl's exit-1 runs were concurrent with each other and with this session, and the wave tests mutate the repo's git state, so their failures were contention — as Blake himself suspected. Recorded in the ledger.

## Alice

Nine findings, listed in the table above (one 🔴, two 🟠, four 🟡, two ⚪). She ran the changed test files from the repo root: 149 passed, 0 failed, 0 skipped. Her 🔴 is the pivotal finding of this cycle and she reproduced it live: `gate._cross_check_findings` against the real `00249-stage-and-close-reviews-in-code-v1-review-2.md` returned `mismatch`, with `_reviewed_keys` returning `set()`. This session re-ran that check independently and confirms it: 0 keys parsed from a real review file whose `## Consolidated Findings` section is a populated pipe table.

Notes she raised with no finding attached: the Blake "history-free" sentence is present in SKILL.md step 3, so reverting `2e5a234` as `f040476` was correct; moving the 00255 stub to `done/` meets the acceptance criterion and avoids the re-mint; and the task-5 settled decision (only `mismatch` refuses, `malformed` is surfaced) matches the code.

## Blake

Eleven findings (four 🟠, four 🟡, three ⚪), one of them discarded above. He confirmed implemented and checked, from the code alone: `_DISPATCH_OUTCOME["unavailable"] == "error"`, `output-formats.md` listing `dispatch_rows:` and all five personas, Eve on `prd_body`, the `run["doubt"]` gate removed, `resolve_base` gone, `triage.SEVERE` carrying 🔴 and 🟠, `phase-review.md` saying severity is a word, `run_gate` streaming and byte-capped, and renames checked by both paths. He ran the eight named test files: 169 passed.

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
B16: fail
B17: pass
B18: pass
B19: pass

## Bob

Six FIX findings, one KNOWN, one VERIFY (static-only sandbox, so he could run nothing). His two highest are the release-checks exit-status fail-open and the `proc.wait()` deadline bypass; both are in the table. His VERIFY item ("run the PRD acceptance tests and `bash dev/bin/release-checks` and confirm their exit statuses and measured totals") was queued and discharged this cycle: `docs/dev/project-management/reviews/00256-finish-the-review-verbs-before-release-v1-checks-1.json` records exit 0.

R1: fail
R2: fail
R3: pass
R4: pass
R6: pass
R7: pass
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

Eight findings (two 🟠, five 🟡, one ⚪), all in the table; he agreed with Bob on both of the 🟠 rows and added the `stage()` size and file-length pair. Backend: copilot (`gemini-run.sh`, exit 0). He ran the touched test files and attempted `bash dev/bin/release-checks`, which exited 1 in his run — the concurrent-run contention discussed under Discarded.

R1: fail
R2: fail
R3: pass
R4: pass
R6: pass
R7: pass
R8: pass
R9: fail
R10: fail
R11: pass
R12: fail
R13: fail

## Follow-up Tasks Created

1. [D1] Tail: dev/bin/release-checks counts the exit status and the harness summaries (M) - 🟠 4/4 consensus - task 8
2. [D1] Tail: verification.py honours the deadline, refuses a failed record, and states its rule (L) - 🟠 - task 9
3. [D1] Tail: make the new tests pin this change, and drop the reformat churn (M) - 🟡 - task 10
4. [D1] Tail: one replay base in review_stage, and the smaller close/stage loose ends (M) - 🟡 - task 11

The 🔴 row gets its own task in Phase 6, behind a rework design, per `phase-review.md` § Dispatch rework.

Verdict: 22 findings
Tests: 2390 passed, 0 failed, 0 skipped (suite run this cycle)
