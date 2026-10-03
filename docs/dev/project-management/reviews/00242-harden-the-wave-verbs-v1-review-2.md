---
prd: 00242-harden-the-wave-verbs-v1.md
cycle: 2
date: 2026-10-04
head_sha: b47e874fda8e281f3b245d991b827425e13145e4
codex_thread_id: 01a1038c-2e11-7791-ba2a-31554e5facc8
reviewers: alice,blake,bob,carl
---

# Review cycle 2 — 00242-harden-the-wave-verbs-v1

Diff range: `11b281506a80903d7941f28e70295c563886b4db..b47e874fda8e281f3b245d991b827425e13145e4`
Scope: incremental review (cycle 2). Base is cycle 1's `head_sha`, so the diff
covers only the five rework tasks' commits. Bob resumed his cycle-1 codex
session via `--resume-thread 01a1038c-2e11-7791-ba2a-31554e5facc8`.

pack: failed (engram: "not inside a registered repo; register it in
/Users/bob/.config/gita/repos.csv" — the same configuration failure as cycle 1,
so no retry was spent). Alice, Bob and Carl ran without the context pack and
the `{PACK_FINDINGS}` input was the `(no pack available this cycle)` sentinel.
Degraded, not invalid.

codex_rung_guard: not fired

Lens roster: consensus (Alice), blind (Blake), doubt (Bob), ui (Carl). Eve is
not active this cycle — `doubt_reviewer` resolved to `codex` and the codex
doubt-roster guard did not fire (0 of 14 attempts across the 12 tasks used
`implementor: "codex"`; 13 ran `claude`, task 12 ran `orchestrator`).

Carl backend: `gemini-run: backend=copilot model=gemini-3.8-flash` (exit 0,
non-empty reviewer text).

Consolidation: `consolidate_findings.py` with four agent pairs, `--ledger` and
`--ledger-dismiss BLAKE` (the cycle-1 ledger holds 10 settled entries). Two
Blake rows were auto-dismissed against it — reproduced verbatim below. The
script merged one row whose six citations matched only after suffix stripping
(the `wave_slots.py` release/lock cluster at `:49`, `:54`, `:180`, `:189`,
`:191`, `:194`).

## Consolidated Findings

13 rows: the 12 the script emitted, plus 1 row absorbed from the context file's
fail-first replay block (`mech-check`). The other `[MECH]` line (the
`raises(Exception)` shape at `test_wave_review_cleanup.py:294`) matched three
existing rows and contributed `mech-check` to their finders rather than a new
row.

**Dedup note (fail loud):** rows 5, 9 and 10 below are the SAME defect — the
`pytest.raises(Exception)` hedge at `test_wave_review_cleanup.py:294` — raised
by Alice, Bob and Carl in different words. `consolidate_findings.py` did not
fold them because their wordings diverge too far. The decision gate treats them
as ONE finding at effective consensus [3/4] + `mech-check`, as the Phase 5
triage rule requires; they are left as three rows here because a reviewer's
recorded output is not rewritten.

| Consensus | Severity | Issue | File | Task | Found By |
|-----------|----------|-------|------|------|----------|
| [4/4] | 🟡 | `release` guards against a missing parent with a racy `is_dir()` precheck (Pat LOW 2, TOCTOU, not fixed). `_slot_lock` still does `mkdir(parents=True)` (wave_slots.py:54), so if `land` or `abort` removes the dir between the check and the lock, the dir and `<n>.lock` are recreated. The `mkdir` in `_slot_lock` is dead for `_claim` and `_discard`: `acquire` already makes the dir, and nothing but `acquire` calls them (rg over the tests and sources). Simpler and race-free: remove the `mkdir` from `_slot_lock`. In `release`, drop the `is_dir()` precheck, add `except FileNotFoundError: return` before the `except OSError`, and keep the stderr report for other errors. | skills/run-autopilot/cli/wave_slots.py:54 | 12 | ALICE, BLAKE, BOB, CARL |
| [3/4] | 🟡 | `_hold_backlog` is now 58 lines (mechanical block), over the 50-line limit, because the retry detection was inlined. Extract the staged and untracked name detection (the two `git` calls and the set union, wave_review.py:251-275) into a verb-named helper such as `_pending_hold_names(worktree, prds, names)` returning the sorted names. That brings the function to about 35 lines with no behaviour change. | skills/run-autopilot/cli/wave_review.py:235 | 11 | ALICE, BOB, CARL |
| [2/4] | 🟡 | Task 12 changed `release` (it no longer raises, and it no longer recreates the slots dir) but shipped no regression test (Pat LOW 3, not fixed). `test_release_of_a_missing_slot_is_a_noop` (test_wave_slots.py:340) only asserts `not slot.exists()`, so it passes against the old code that recreated `wave-slots/` and `<n>.lock`. Add `assert not slot.parent.exists()` there, plus a test that an OSError from the lock open (for example a monkeypatched `_slot_lock`) prints one stderr line and does not raise. test_wave_slots.py is 799 lines, so these will push it past the 800 cap. Put them in a new `test_wave_slots_release.py` and add it to `_WAVE_TEST_FILES` and to the `[checks] waves` block in `dev/bin/release-checks` (the parity test would otherwise fail). | skills/run-autopilot/cli/test_wave_slots.py:340 | 12 | ALICE, BOB |
| [1/4] | 🟡 | The `ls-files --others` branch of `_hold_backlog` (the "failure at `rm --cached` or `add -f` before anything is staged, including ignored hold files" case from commit f237664) has no test. The commit-failure test only exercises the staged branch, because the files are already in the index by then. Deleting the `untracked` set from the union would leave every test green. Add a test where `rm --cached` or `add` raises after the renames, then the retry commits; one with a gitignored `hold/` would also pin the ignored-file claim. | skills/run-autopilot/cli/test_wave_review_cleanup.py:240 | 11 | ALICE |
| [1/4] | 🟡 | `test_hold_backlog_refuses_a_name_collision_without_overwriting` uses `pytest.raises(Exception)`, which is the either-or hedge the mech block flags. The code raises `FileExistsError` (wave_review.py:246), so tighten it to `pytest.raises(FileExistsError)`. The path-in-message and content-preserved asserts limit the damage, but the exception type is not pinned. | skills/run-autopilot/cli/test_wave_review_cleanup.py:294 | 11 | ALICE, mech-check |
| [1/4] | 🟡 | Scope creep in `_hold_backlog`. It raises FileExistsError when a backlog name already exists in `hold/`. It also adds multi-step retry and resume logic (staged/untracked/ignored detection, `rm --cached`, `add -f`). The PRD asked only to move `backlog/*.md` into `hold/` and commit. The collision refusal can block a review with a new error path the spec never mentions. | skills/run-autopilot/cli/wave_review.py:235 | 4 | BLAKE |
| [1/4] | 🟡 | `_hold_backlog` calls `_default_run_git` directly instead of an injected `run_git`. `seed_state` has no `run_git` parameter, so the step cannot be faked in tests or crash-simulated. Behaviour is correct; this is a testability gap. | skills/run-autopilot/cli/wave_review.py:251 | 4 | BLAKE |
| [1/4] | 🟡 | FIX: Recovery parses Git paths with `.split()`, corrupting valid filenames containing spaces or Git-quoted characters. A backlog PRD named `00050-two words.md` produces nonexistent staging paths. Use `-z` and NUL-delimited parsing for both queries; add a regression test. | skills/run-autopilot/cli/wave_review.py:261 | 11 | BOB |
| [1/4] | 🟡 | FIX: The mechanical checker flags `pytest.raises(Exception)` in the collision test. Require `FileExistsError` so unrelated exceptions cannot satisfy the refusal assertion. | skills/run-autopilot/cli/test_wave_review_cleanup.py:294 | 11 | BOB, mech-check |
| [1/4] | 🟡 | test_hold_backlog_refuses_a_name_collision_without_overwriting accepts any exception via raises(Exception) rather than FileExistsError | skills/run-autopilot/cli/test_wave_review_cleanup.py:294 | 11 | CARL, mech-check |
| [1/4] | 🟡 | [MECH] 2 touched test(s) pass against the pre-change code: test_store_churn_in_the_assembly_worktree_does_not_refuse, test_retrying_seed_state_does_not_recommit_the_held_backlog | skills/run-autopilot/cli/test_wave_review_cleanup.py | general | mech-check |
| [1/4] | ⚪ | `_drain_lane` now repeats the 2-line `branch --list` and `-D` step in the early return and again at the end (wave_assemble.py:520 and 532). A small `_drop_branch(repo, lane, run_git)` helper, or restructuring so both paths share one tail, would remove the duplicate. Behaviour would not change, and the duplication is the kind the checklist asks to flag. | skills/run-autopilot/cli/wave_assemble.py:520 | 9 | ALICE |
| [1/4] | ⚪ | `_drain_lane` adds a rerun path that deletes the branch when `worktree_removed` is already set. This is beyond the spec but harmless, since it guards with `branch --list`. | skills/run-autopilot/cli/wave_assemble.py:519 | 3 | BLAKE |

### Auto-dismissed (ledger)

- [BLAKE] 🟡 The PRD Risks section says "the commit message and the wave report name every PRD moved to `hold/`". The commit message does, but nothing writes the held PRD names into the wave report (`_write_report` and `_append_summary_line` are untouched by `_hold_backlog`). | File: skills/run-autopilot/cli/wave_review.py:285 — Requirements ambiguity between the PRD's own sections, deferred to batch end rather than guessed. The 00225 Outputs bullet asks only to move the PRDs to hold/ and commit that move, which the code does; the stronger promise lives in the Risks mitigation. The design doc already recorded the report-surfacing gap as an explicit planner task, so this is a known open decision, not a missed fix. The second half (backlog PRDs landing in master's hold/ after land, against waves.md:22's 'left in the main backlog') is marked suspected by the reviewer and not confirmed by an end-to-end land run; changing land's PRD routing on an unconfirmed reading could alter land semantics, so it needs the operator's call.
- [BLAKE] ⚪ The acceptance text for `test_reclaim_put_back_race_admits_one_holder` says "three processes". The test drives threads in one process, each opening its own lock fd. `flock` contends per open file description, so the race is exercised, but the wording is not met literally. | File: skills/run-autopilot/cli/test_wave_slots.py:573 — Discarded on the raising reviewer's own evidence: fcntl.flock is per open file description, so two threads each opening <slot>.lock exercise the same mutual exclusion a two-process test would. The PRD's 'three processes' describes the scenario, not a mandated harness, and the test does drive three concurrent acquirers at count=1 with a forced interleave at the rename.

## Cycle-1 findings: resolution status

Every cycle-1 row routed to the five rework tasks was checked against HEAD.
Both implementation-aware lenses and the blind lens agree the six PRD fixes are
in place; the residue below is new, narrower, and all Medium/Low.

| Cycle-1 finding | Task | Status at cycle 2 |
|-----------------|------|-------------------|
| 🟠 00226 spec deviation + recovery hole | 8 | **Resolved.** `_land_review_failed(repo, wave_path, wave) -> int \| None` (wave_review.py:534) saves `converged` under the lock before returning `None`; `test_hand_reviewed_land_resumes_after_a_crash_before_done` crashes in `_cycle_count` after the stub moved and lands cleanly on rerun (fails against the old code). Confirmed independently by Blake. |
| 🟡 `_drain_lane` branch leak on rerun | 9 | **Resolved.** The `worktree_removed` early return now retries `branch --list`/`-D` (wave_assemble.py:519), with a crash-after-second-save test and a clean-run baseline. |
| 🟡 `waves.md:192` documents behaviour the code lacked | 8 | **Resolved.** `land` is 49 lines and the doc text matches the code. |
| 🟡 PRD-named acceptance test id missing | 10 | **Resolved.** `test_store_churn_in_the_assembly_worktree_does_not_refuse` exists under that id. |
| 🟡 `_hold_backlog` partial-failure gaps | 11 | **Half resolved.** The commit-retry and collision-refusal gaps are closed; the fix introduced the 58-line overrun, the untested `ls-files --others` branch, and Bob's `.split()` path-parsing bug. |
| 🟡 retry test passed against base | 10 | **Resolved.** It now asserts the first attempt moved HEAD and the file reached `hold/`, so it cannot pass vacuously. |
| 🟡 `land` at the 50-line ceiling | 8 | **Resolved** (49 lines). |
| ⚪ `release` can raise / recreates the slots dir | 12 | **Partly resolved.** The never-raises and no-recreate behaviour is in place, but it shipped with no test and Pat's three LOW items are only partly closed — hence the [4/4] and [2/4] rows above. |
| 🟡 mech-check: two tests passed against base | 10 | **Resolved** (both explained and now non-vacuous). |
| ⚪ `wave run` OSError gap | 9 | **Resolved.** `_GUARDED_ERRORS` includes `OSError` (wave_cli.py:42), with a one-line/exit-1/no-traceback test. |

## Alice

7 findings (0 critical, 0 high, 5 medium, 2 low). Implementation-aware with the
context file, the full incremental diff and the three computed blocks; no pack.
She ran the six touched wave test files narrowly (105 passed, 0 skipped) and
states plainly that she did not run the full `release-checks`.

R1: fail
R2: fail
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

## Blake

6 findings (0 critical, 0 high, 3 medium, 3 low). Blind lens: PRD only, no
diff, no file list, no design doc, no review history, and no ledger feed (his
re-raises are absorbed mechanically instead — see the auto-dismissed section).
He located the code himself and ran both verification commands.

Blake's own verification run:

- `pytest -q -n 4 skills/run-autopilot/cli -k "wave or review_once"` gave 440 passed.
- `bash dev/bin/release-checks` showed no `failed`/`ERROR` lines; he did not capture an exit code (the orchestrator's own run below did: exit 0, 2260 passed).
- Confirmed against the code: 00221 gating and `test_every_wave_test_file_is_listed`; 00222 save ordering plus the `OSError` catch; 00225 `foreign_dirty` and the committed `hold/` move before the nested loop; 00226 the saved `converged` transition and the documented route; 00227 the per-slot flock across `_claim`/`_discard`/`release` with the ownership check; 00239 the `in_wave_lane` guard at `loop.py:507`; and the CHANGELOG entry naming all six fixes.

B1: pass
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

> Orchestrator note on B6 (`no new functionality beyond the PRD`): Blake's
> `fail` rests on the `_hold_backlog` collision refusal and retry logic being
> absent from the PRD text. That work was mandated by cycle 1's own [2/4]
> finding and by the PRD's 00225 Risks mitigation, so the gate discards the
> finding (below) rather than reverting a fix the previous cycle required. His
> verdict line stands as emitted.

## Bob

6 findings (0 critical, 0 high, 3 medium, 3 low), doubt + de-slop lens, codex
static-only sandbox, resumed from his cycle-1 thread. He prefixed every finding
`FIX:`, so his residual set is wholly in the FIX bucket — there is no VERIFY
bucket and therefore no verification-check queue this cycle (see below).

R1: fail
R2: fail
R3: pass
R4: fail
R6: pass
R7: pass
R8: pass
R9: fail
R10: fail
R11: pass
R12: fail
R13: pass

D1: pass
D2: pass
D3: pass
D4: pass
D5: pass

## Carl

5 findings (0 critical, 0 high, 2 medium, 3 low). Carl ran as a generalist (the
change has no frontend surface) on `backend=copilot model=gemini-3.8-flash`,
exit 0, with real tool activity in his transcript (the diff and context reads,
four targeted source reads, and his own `-k "wave or review_once"` pytest run).

R1: fail
R2: fail
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

## Verification-check queue

Empty for this cycle, and no `00242-harden-the-wave-verbs-v1-checks-2.json` was
written. Eve is not active (see the lens roster), and Bob's assembled persona
carries the two doubt lenses and the D-rubric but not the FIX/VERIFY/KNOWN
bucket section, so no doubt-lens VERIFY bucket existed to collect. Cycle 1 also
wrote no `checks-1.json`, so the carry-forward step had nothing to carry.

## Decision gate (Phase 5)

Cap check: `state.cycle` 2, `state.rework_cap` 2. **No unresolved CRITICAL or
HIGH finding remains** — all 13 rows are 🟡 Medium or ⚪ Low, across four
independent lenses — so the cycle CONVERGED and the cap is irrelevant (the cap
gates rework, not convergence).

Safety checks: 7 findings swept into one task, well under the 10-task scope
alarm. Issue count fell from 21 to 13 and from one 🟠 to none. The
`raises(Exception)` row is a reappearance only in the sense that cycle 1's
`mech-check` already flagged that test shape; it is being fixed now, not
re-argued. All four reviewers produced parseable output — no transient
degradation beyond the pack failure recorded above.

**Follow-up task creation was deliberately deferred to the Tail sweep** rather
than run in `review-work-completion` step 7: on a converged cycle Phase 5's
Tail sweep owns the single `[D2]` task, and creating per-finding tasks here as
well would double-dispatch the same fixes. Recorded loud, per the skill's own
fail-loud rule.

Dispositions, covering all 13 rows:

**Swept — one `[D2] Tail sweep` task** (7 findings; see the task's
`### Findings (verbatim)` block):

1. [4/4] 🟡 `release`/`_slot_lock` TOCTOU, dead `mkdir`, `is_dir()` outside the `try`.
2. [3/4] 🟡 `_hold_backlog` at 58 lines, over the 50-line limit.
3. [2/4] 🟡 Task 12 shipped no regression test for `release`.
4. [1/4] 🟡 The `ls-files --others` branch of `_hold_backlog` is untested.
5. [3/4 effective] 🟡 `pytest.raises(Exception)` instead of `FileExistsError` (rows 5, 9, 10 merged, + `mech-check`).
6. [1/4] 🟡 `.split()` on git path output corrupts names containing spaces.
7. [1/4] ⚪ `_drain_lane` duplicates the 2-line branch-delete step.

**Deferred to batch end — 1** (recorded via `autopilot defer`, in
`state.deferred_decisions`, and in the ledger):

- `_hold_backlog` calls `_default_run_git` directly; `seed_state` has no injectable `run_git` (Blake, 🟡). Behaviour is correct by the raiser's own words; adding the parameter changes `seed_state`'s signature for testability the PRD never asked for, so it is the operator's call.

**Discarded with a verified reason — 3** (all in the ledger):

- Blake's 🟡 `_hold_backlog` scope creep: the collision refusal and retry logic were mandated by cycle 1's own [2/4] finding and the PRD's 00225 Risks mitigation.
- Blake's ⚪ `_drain_lane` rerun path "beyond the spec": that path is exactly what cycle 1's [3/4] branch-leak finding required, and he calls it harmless and guarded.
- The `mech-check` replay row (two tests passing against base): both are explained — the renamed churn test pins behaviour the base already had, and the retry test's new asserts make it non-vacuous.

Next: sweep the 7 Medium/Low findings in one `[D2]` task, then finalize. No
further review cycle — Phase 5 does not reopen after convergence.

Verdict: 13 findings
Tests: 2260 passed, 0 failed, 0 skipped (suite run this cycle)
