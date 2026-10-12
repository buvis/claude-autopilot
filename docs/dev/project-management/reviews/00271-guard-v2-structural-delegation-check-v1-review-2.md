---
prd: docs/dev/project-management/prds/wip/00271-guard-v2-structural-delegation-check-v1.md
review: 2
date: 2026-10-13
head_sha: 357cf41d3ed9a5b95dbd78e2e450cf427a35542b
codex_thread_id: 01a1322b-ab17-7dd2-8777-1a1ad6ca7853
reviewers: alice,blake,bob
agents:
  alice: available
  blake: available
  bob: available
  carl: unavailable
dispatch_rows:
  bob: cfe56a5b, 553ff726 (retry)
  carl: 01b49ce6
---

# Review: 00271-guard-v2-structural-delegation-check-v1 (cycle 2)

Diff range: `851c38619d72bfa08b3600436b2cfa2a9c1d4801..357cf41d3ed9a5b95dbd78e2e450cf427a35542b` (incremental — the rework since cycle 1)

codex_rung_guard: not fired

## Review Summary

Reviewed: 14 completed tasks
PRDs checked: 00271-guard-v2-structural-delegation-check-v1

### Agent Status

- Alice: ✅ Available (consensus lens, legacy engine)
- Blake: ✅ Available (blind lens, PRD-only)
- Bob: ✅ Available (doubt lens, codex) — after one retry (inlined). His first run refused with the same sandbox read failure as cycle 1 (`sandbox-exec: sandbox_apply: Operation not permitted` on both reads) and emitted twelve unevidenced `fail` verdicts; the inlined retry prompt carried the review context and the full diff verbatim, and its output is what is consolidated here. The thread resume (`--resume-thread` on the first run) was therefore dropped for the retry, per the inlined-retry contract.
- Carl: ⚠️ Unavailable: `gemini-run` exit 1 on both the first run and the retry, backend `copilot` model `gemini-3.8-flash`, `Error: Authentication failed` (GitHub Copilot token invalid, expired, or missing the `Copilot Requests` permission). Exit 1 is a runtime failure, not the exit-4 permanent shape, so no `state.batch.unavailable_reviewers` latch was written and the next cycle will try him again.

pack: failed (engram pack exit 1: `sqlite3.OperationalError: attempt to write a readonly database`) — the review ran without the findings-precedent pack, which is degraded, not invalid.

Mechanical checks: no tautological test shapes were detected (82 test functions across 6 files). The fail-first replay was **skipped**: its pytest run timed out after 600 s in the scratch worktree, so this cycle has no replay evidence either way — recorded, not silently dropped.

Consolidation note (fail loud): `consolidate_findings.py`'s same-file merge folded six distinct per-file findings into row R1 (its own merge note names the citations `:511 ~ :492 ~ :474 ~ :104 ~ :510 ~ :443`). Two of the folded items are cycle-1 settled deferrals that the ledger filter would otherwise have auto-dismissed (Blake's replay-exit-1 finding, and his `(?<![-/:\w])` lookbehind deviation); they are treated as settled and are NOT table rows. The remaining merged-away items are restored verbatim below as R9 and R10 and carried into the decision gate separately.

## Consolidated Findings

| Ref | Consensus | Severity | Issue | File | Task | Found By |
|-----|-----------|----------|-------|------|------|----------|
| R1 | [3/3] | 🟠 | Quadratic work is still present for SKILL.md candidates, so prior R2 is only partly resolved and the PRD rule "every regex runs in linear time" is still unmet. `_ordered_to_follow` finds the sentence end with `next((s for s in sentences if s >= end), len(text))`, which walks the sentence list from index 0 for each SKILL.md candidate. Measured with `'x work/SKILL.md. ' * n`: 170 KB takes 0.43 s, 340 KB takes 1.58 s, 680 KB takes 5.7 s, which is past the 5 s hook timeout and so fails open. `'Read skills/work/SKILL.md. ' * n` shows the same 3.3x growth per doubling (0.16 s, 0.48 s, 1.59 s). Replace the `next(...)` with `bisect_left(sentences, end)`, indexing `sentences` when the result is in range and using `len(text)` otherwise. `hooks/test_guard_phase_delegation_linearity.py` has no many-SKILL.md-mentions case, so nothing catches this; add one. | hooks/guard_phase_delegation.py:511 | 11 | ALICE, BLAKE, BOB |
| R2 | [3/3] | 🟠 | The rework for prior R12 introduced a false-allow: the SKILL.md follow phrase is negated by any negation word in the five words before the verb, even across a clause boundary. `_ordered_to_follow` calls `_negated(text, end, match.start())`, so the floor is the path end, not the verb's clause start. The PRD says negation counts only "within four words before the verb in the same clause". Measured: `Read skills/work/SKILL.md, then follow it for every task.` is denied, but `Read skills/work/SKILL.md, do not stop, then follow it for every task.` and `Read skills/work/SKILL.md; never mind, follow it.` are both allowed. That reopens the bypass the rework closed for phase names ("Do not stop - run the work phase" is denied). Pass the clause starts into `_ordered_to_follow` and use `max(end, start of the verb's clause)` as the floor. | hooks/guard_phase_delegation.py:515 | 11 | ALICE, BLAKE, BOB |
| R3 | [2/3] | 🟡 | Prior R4 is not resolved. `CHANGELOG.md` line 18 ("normalizes lookalike text before matching...") still sits beside the new guard line at line 30, which already states the normalization. The rework also adds line 17, which claims the guard "scans every field in linear time". That is false while the SKILL.md quadratic above exists. The PRD said the replacement should be exactly three lines with no other CHANGELOG edit. Drop or fold line 18, and fix the wording of line 17 once the quadratic is fixed. | CHANGELOG.md:17 | 10 | ALICE, BLAKE |
| R4 | [1/3] | 🟡 | The new SKILL.md negation test covers only the same-clause case (`Read skills/work/SKILL.md; you must never follow it`). It cannot catch the cross-clause false-allow above, and nothing pins the clause-bounded case or a many-SKILL.md-mentions linearity case. Add one denied case with the negation in an earlier clause (`..., do not stop, then follow it`) and one linearity case with thousands of SKILL.md mentions. | hooks/test_guard_phase_delegation_linearity.py:206 | 11 | ALICE |
| R5 | [1/3] | 🟡 | `test_blocks_lone_surrogate_path_over_a_real_subprocess_pipe` says in its own comment that it is green at base. Prior R9 asked for a case that fails at base, and this one cannot fail on the encoding bug. It duplicates coverage rather than pinning the targeted failure. Either drop it or relabel it as a coverage test and record that no strict-UTF-8 subprocess case can fail at base, because `read_input` already decodes with `errors="replace"`. | hooks/test_enforce_prd_location.py:177 | 13 | ALICE |
| R6 | [1/3] | 🟡 | `(?![-\w])` does not enforce a whole first token: `/autopilot:work/helper task 3 only` still triggers unconditional denial. Require whitespace or end-of-input after the command, leaving other forms to ordinary structural matching; add slash- and dot-suffixed token tests. | hooks/guard_phase_delegation.py:170 | 11 | BOB |
| R7 | [1/3] | ⚪ | Scope: the diff carries unrelated changes. They are the `skills/work/SKILL.md` ambiguity-check rewrite, its test, the `**work**` CHANGELOG line, the 00283 PRD edit and the new 00285 PRD. They come from the loop-efficiency audit, not from PRD 00271. They look operator-intended and harmless, so I am noting them and not requiring a revert. | skills/work/SKILL.md:216 | general | ALICE |
| R8 | [1/3] | ⚪ | Prior finding R4 remains unresolved: the redundant normalization CHANGELOG entry remains beside the structural guard documentation. Remove the duplicate entry while retaining the required verbatim description. | CHANGELOG.md:18 | 10 | BOB |
| R9 | [2/3] | 🟠 | Merged away by the consolidator, restored verbatim. Blake: task scoping is stricter than the spec. The spec says a field is scoped when it names "exactly one distinct task id". The code keys ids by (sentence index, id), so the same id repeated in a second sentence counts as two ids and does not scope. `Fix task 3. The hook must run the work phase for PRD 7. Report when task 3 passes.` sent to `autopilot:ivan` is refused. Ordinary per-task prompts repeat their task number, so this is another false-deny source. The docstring defends it as deliberate, but it contradicts the PRD wording. Bob, same defect: `Run the work phase for task 3. Also do task 3.` must scope under the PRD but is explicitly tested as denied. Deduplicate IDs alone; change that test and remove task IDs from the unrelated normalization test's filler. | hooks/guard_phase_delegation.py:474 | 11 | BLAKE, BOB |
| R10 | [1/3] | 🟡 | Merged away by the consolidator, restored verbatim: range-lead matching still truncates to 24 characters after trimming trailing whitespace, missing whitespace inside `starting … at/with`. `Run the work phase for PRD 7, starting` + 40 spaces + `at task 3` incorrectly gains task scope. Recognize the preceding range words without a character cap and add both multiword-prefix cases. | hooks/guard_phase_delegation.py:443 | 11 | BOB |

### Auto-dismissed (ledger)

- [BLAKE] 🟡 The spec contradicts itself on `toolu_01Ku4TbcQoeik6ZLf5XkkAuD`. It is a pinned must-deny id. Its description, "Resume work phase for PRD 00242, task 1 onward", matches the `per-task` bucket regex `\btask\s+[A-Z]?\d+\b`. It is therefore both required to be refused and counted as a refused per-task record, which sets the failure flag. The replay can never exit 0 on a machine holding that transcript, whatever the predicate does. The implementation follows the spec literally (`dev/bin/replay_delegation_guard.py:48`, `dev/bin/replay_delegation_guard.py:167`), so this is a spec defect. Fix it by excluding pinned-deny ids from the per-task failure test. | File: dev/bin/replay_delegation_guard.py:156 — Already recorded as deferred during the build phase (batch 202610111300 deferred JSON, task 9): the acceptance criterion is provably unreachable as specified, and the only fix is a design-doc change exempting pinned deny ids from the per-task-refusal clause. Settled; not re-argued here.
- [BLAKE] ⚪ `_PRD_PATH_TAIL` (`hooks/guard_phase_delegation.py:128`) is a strong anchor the spec does not list (strong anchors are `for|on` plus PRD/task/slug/number, `from task`, or a whole-run marker). The spec test "Run the work phase for docs/dev/project-management/prds/wip/00300.md." needs it to be denied, so it is arguably required. It is a documented omission in the anchor list. | File: hooks/guard_phase_delegation.py:128 — The reviewer who raised it judged it justified in the same breath: the anchor is load-bearing for a deny the PRD itself requires. Keeping it is correct; the PRD's anchor list is the stale side. Deferred as a spec-text follow-up.
- Held settled by this cycle's gate rather than by the script (the same-file merge folded them into R1 before the ledger filter could see them): Blake's 🟠 "the full local replay exits 1, so the Phase 2 exit criterion is unmet" (ledger cycle 1, `dev/bin/replay_delegation_guard.py:148`, plus its six-false-refusal companion), and Blake's 🟡 "the bare-name lookbehind differs from the spec (`(?<![-/:\w])` vs `(?<![-/\w])`)" (ledger cycle 1, `hooks/guard_phase_delegation.py:98`).

## Alice

Findings: R1, R2, R3, R4, R5, R7 (see the table).

Her prior-finding verification, in her own words:
- Prior R1 and R7: settled deferrals, not re-raised.
- R2: partly resolved. `_PATH_TOKEN` is now a linear token scan, `_words_before` is lazy and `_negated` takes only five words. Timings were flat for phase mentions, task ids, paths and negations at about 1 MB (0.14 s to 0.25 s). The SKILL.md candidate path is still quadratic (R1 above).
- R3: resolved. The normalize sweep moved to `hooks/test_guard_phase_delegation_normalize.py` and both new modules are registered in `dev/bin/release-checks`. The structure file is now 644 lines.
- R4: not resolved (R3 above).
- R5 and R14: resolved. Scoping uses distinct paths, `_PRD_STORE_PATH` matches both `prds/` and `/prds/`, and any ranged id disqualifies task scope.
- R6: resolved. `_negated` takes at most five words from the lazy backward walk.
- R8: resolved. The skill-suffix and task-range probes are offset matches with no character caps.
- R9: not resolved (R5 above).
- R10 and R11: settled deferrals, not re-raised.
- R12: unsound — the fix introduced the cross-clause false-allow (R2 above).
- R13: resolved. `_BARE_SLASH_PREFIX` ends with `(?![-\w])`.
- R15: resolved. `dev/bin/replay_delegation_guard.py` raises `GuardError` on an exit code other than 0 or 2, and the new crash test fails at base. The missing-guard test now asserts `code == 2`.

Her scoped test run: 670 passed, 22 subtests passed.

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

## Blake

Findings: R1, R2, R3, R9 (see the table), plus the two ledger-settled items listed under Auto-dismissed.

His runs:
- `pytest -q` over the 12 files in the release-checks "hook registration" block: 717 passed, 22 subtests passed.
- `python3 dev/bin/replay_delegation_guard.py`: `total 1188`, `per-task 810 refused 7`, `reviewer 152 refused 0`, `agoge 43 refused 0`, `other 183 refused 7`, exit 1 (the spec requires exit 0 — the cycle-1 settled deferral).

Verified compliant in his own words: normalization (NFKD, drop Cf/Mn, Pd and U+2212 to `-`, NFKC, curly quote fold, `*` strip); exemptions (`agoge:` prefix, the 13 reviewers, lookalike types still checked, unhashable type fails open); both deny-message texts and the `text[start-10:start+20]` span; bound negation (double-negation exception, 4-word bound, clause scoping); bare `/autopilot:` first-token refusal; fixture `replay.jsonl` (17 records, 4 deny and 13 allow, correct ids and keys); `enforce_prd_location.py:177` surrogate normalization; U+FFFD session-id allow in `note_session_leave.py:62` and `guard_skill_after_leave.py:68`; six-hook stdin matrix tests; the cost-bound test; gate registration of all new test files in `dev/bin/release-checks:135-143`.

B1: fail
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
B16: fail
B17: pass
B18: pass
B19: pass

## Bob

Ran after one retry (inlined). Doubt + de-slop lens.

FIX: R1, R2, R3 (as R8), R6, R9, R10 (see the table).

VERIFY: (none) — so no verification-check queue file was written this cycle.

KNOWN: (none).

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

## Carl

Carl: unavailable (gemini-run exit 1 twice; backend `copilot`, model `gemini-3.8-flash`; `Error: Authentication failed` — GitHub Copilot token invalid, expired, or missing the `Copilot Requests` permission). Exit 1 is a runtime failure, not the exit-4 permanent-unavailability shape, so no `state.batch.unavailable_reviewers` latch was written and the next cycle will try him again.

Verdict: 10 findings
Tests: 3484 passed, 9 failed, 0 skipped (suite run this cycle)
