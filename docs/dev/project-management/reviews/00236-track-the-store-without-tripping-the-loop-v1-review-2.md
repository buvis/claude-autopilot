---
prd: docs/dev/project-management/prds/wip/00236-track-the-store-without-tripping-the-loop-v1.md
review: 2
date: 2026-10-03
head_sha: 1daea55509ef17d8eb7703b905273b15d0bcaa9e
codex_thread_id: 01a0fce2-df57-7220-8f24-ad3af1e88258
reviewers: alice,blake,bob,carl
agents:
  alice: available
  blake: available
  bob: available
  carl: available
---

# Review: 00236-track-the-store-without-tripping-the-loop-v1

Diff range: `5ab1a1fdca6dc9cf7c885ae6fe2f69b2350cb8b3..1daea55509ef17d8eb7703b905273b15d0bcaa9e`

codex_rung_guard: not fired

pack: failed (`engram pack` exits 1: "not inside a registered repo; register it in
/Users/bob/.config/gita/repos.csv"). Same deterministic configuration refusal as cycle 1, so
no retry; every implementation-aware prompt carried the documented
`(no pack available this cycle)` sentinel. Blake never receives a pack by design.

carl: ran on backend=copilot.

## Scope of this review

**Cycle 2, an incremental review.** The diff is scoped to the cycle-1 rework with
`gather-context.sh --since 5ab1a1f` — 29 files, +3025/-956, covering the eight `[D1]` tasks
(ids 9-16) plus the task-13 regression fix. Bob resumed his own cycle-1 codex session
(`--resume-thread 01a0fce2`), so his verification of the fixes is against his own critique.
The cycle-1 settled-decisions ledger (8 entries) was fed to Alice, Bob and Carl as
"do not re-raise", and passed to the consolidator as `--ledger --ledger-dismiss BLAKE`.

**Rework cap reached.** `state.cycle` is 2 and `state.rework_cap` is 2, so this is the last
cycle this PRD gets. Two unresolved HIGH findings remain and no CRITICAL, which is the
loop-mode cap-out branch: defer, do not pause, do not rework. See "Decision gate" below.

## Gate verification of the two HIGHs

Neither was taken on the reviewer's word, because both are what the cap-out defers:

- **lane_check nested-store exclusion (Alice + Bob).** `store_tree._store_prefix(Path("/tmp/h"),
  Path("/tmp/h/.claude/docs/dev/project-management"))` returns `'.claude/'` — the prefix
  machinery knows the answer — while `lane_check.diff_signal` builds its pathspec from the
  un-prefixed `STORE_EXCLUDE_PATHSPECS`, which is still
  `(':(exclude)docs/dev/project-management', ':(exclude)docs/dev/tmp')`. And
  `lane.is_production_path('.claude/docs/dev/project-management/autopilot/ledger/dispatch-metrics.jsonl')`
  returns `True`. So in a bare-repo-backed project every store commit inside
  `work_start_sha..HEAD` is production evidence and every solo PRD escalates. **Confirmed.**
  Recurring class: the same boundary assumption as cycle 1's task-9 finding, at a site task 10
  did not cover (Protocol B recorded in the deferral reason).
- **review-once missing the wave-lane guard (Bob).** `rg -n 'record_store|in_wave_lane'` over
  `loop.py`, `loop_act.py` and `__main__.py` puts `in_wave_lane` at `loop.py:611`,
  `loop_act.py:218` and `__main__.py:1216`, and nowhere in `_record_review_once_store`
  (`loop.py:506`). The one recorder call site without the guard is the one that can commit onto
  a lane branch. **Confirmed.** Exposure is narrow (wave lanes run `autopilot loop`, not
  `review-once`), which is why it did not hold the batch.
- **Task 13 incompleteness (Bob).** `git diff --name-only 5ab1a1f..HEAD` lists neither
  `test_wave_assemble.py` nor `test_wave_launch_refusals.py`, both named verbatim in task 13's
  cluster 1. **Confirmed:** the task was marked completed with three of its quoted findings
  undelivered (those two files, plus the `wave_review` and intake replay survivors this cycle's
  own replay still reports).
- **Bob's one `Cannot statically verify`** was answered rather than deferred: the gate ran
  `bash dev/bin/release-checks` at exactly `1daea55` and it exited 0.

## Consolidation corrections (read before the table)

`consolidate_findings.py` warned on one suffix-stripped merge (`lane_check.py:53 ~
lane_check.py:55`), which was a legitimate paraphrase merge — Alice and Bob found the same
defect, so the row is [2/4] 🟠 rather than two [1/4] rows. Two merges the script **missed**
were applied by hand:

1. Bob's `loop.py:516` finding (review-once swallows every exception) folded onto Alice's
   `loop.py:506` finding of the same defect, and Blake named it too → one row at **[3/4]**, the
   cycle's highest-consensus finding. Left split, it would have read as three minority rows.
2. Blake's `__main__.py:1200` finding (exit 13 undefined, gates read stdout, fail-open) folded
   onto Alice's `work/SKILL.md:364` finding (gates still say "comes back empty", step 5 gives no
   invocation) → one row at **[2/4]**.

Net: 25 rows — 21 reviewer rows after those two merges, plus 4 rows the mechanical replay block
contributed that no reviewer raised. Consolidation was **script-run, gate-corrected**.

## Consolidated findings

| Consensus | Severity | Issue | File | Found By | Disposition |
|-----------|----------|-------|------|----------|-------------|
| [2/4] | 🟠 High | `lane_check` excludes the un-prefixed store pathspec, so a bare-backed project's store commits read as production paths and every solo PRD escalates | skills/run-autopilot/cli/lane_check.py:55 | ALICE, BOB | cap-overflow deferral (gate-confirmed) |
| [1/4] | 🟠 High | `review-once` records the store with no `in_wave_lane` guard, so it can commit store files onto a lane branch | skills/run-autopilot/cli/loop.py:506 | BOB | cap-overflow deferral (gate-confirmed) |
| [3/4] | 🟡 Medium | `_record_review_once_store` wraps the recorder in `except Exception: pass`: every failure is dropped with no output | skills/run-autopilot/cli/loop.py:516 | ALICE, BOB, BLAKE | cap-overflow deferral |
| [2/4] | 🟡 Medium | `autopilot dirty` exit 13 is undefined by the PRD and the prose gates still read stdout ("comes back empty"), so a failed probe reads as a clean tree; `work/SKILL.md` step 5 gives no invocation | skills/work/SKILL.md:364 | BLAKE, ALICE | cap-overflow deferral |
| [2/4] | 🟡 Medium | Task 13 reported complete with three quoted findings undelivered: `test_wave_assemble.py` and `test_wave_launch_refusals.py` untouched, `wave_review` and intake replay survivors still passing at base | skills/run-autopilot/cli/test_wave_assemble.py:473 | BOB, mech-check | cap-overflow deferral (gate-confirmed) |
| [2/4] | 🟡 Medium | `test_store_tree_legibility.py` re-defines `FakeGit` and six helpers that already live in the shared `store_tree_testutil.py` | skills/run-autopilot/cli/test_store_tree_legibility.py:48 | ALICE, BOB | cap-overflow deferral |
| [1/4] | 🟡 Medium | `in_wave_lane` keys on `_AUTOPILOT_REVIEW_SLOTS_DIR`, the general review-concurrency semaphore, so a plain loop with it set silently skips every `record-store` | skills/run-autopilot/cli/store_tree.py:72 | ALICE | cap-overflow deferral |
| [1/4] | 🟡 Medium | The task-boundary pin asserts leave-before-record but never record-before-STOP; the replay also finds it passing at base | skills/run-autopilot/scripts/test_store_tree_prose.py:162 | BOB, mech-check | cap-overflow deferral |
| [1/4] | 🟡 Medium | `test_solo_repo_commits_despite_host_signing_config` asserts git config and the fixture, not product behavior | skills/run-autopilot/cli/test_lane_cli.py:215 | BOB, mech-check | cap-overflow deferral |
| [1/4] | 🟡 Medium | The PRD's first Success Metric and its Phase 0/1 acceptance criteria name `test_store_tree.py`, which the cycle-1 style-gate split deleted | docs/dev/project-management/prds/wip/00236-track-the-store-without-tripping-the-loop-v1.md:47 | BLAKE | cap-overflow deferral (doc drift) |
| [1/4] | 🟡 Medium | `record-store` does nothing inside a wave lane; the PRD specifies no lane exception | skills/run-autopilot/cli/__main__.py:1216 | BLAKE | settled deferral (cycle-1 gate decision) |
| [1/4] | 🟡 Medium | The loop records at three sites, two beyond the PRD's named list | skills/run-autopilot/cli/loop.py:509 | BLAKE | settled deferral (swallow half deferred live) |
| [1/4] | 🟡 Medium | `STORE_GITIGNORE` ships 23 patterns where the PRD lists 18, interleaved | skills/run-autopilot/cli/store_tree.py:30 | BLAKE | auto-dismissed by `--ledger-dismiss` |
| [1/4] | ⚪ Low | The three wave modules call `foreign_dirty` without `store_dir`, so a bare-backed prefix is empty and store paths read as foreign | skills/run-autopilot/cli/wave_assemble.py:273 | BLAKE | cap-overflow deferral (same class as the HIGH) |
| [1/4] | ⚪ Low | Three test docstrings still point at the deleted `test_store_tree.py` | skills/run-autopilot/cli/test_store_boundary.py:8 | ALICE | cap-overflow deferral (grouped) |
| [1/4] | ⚪ Low | `test_task_boundary_handoff_records_the_store_before_the_leave_row` states the opposite of what it asserts, and this name is not PRD-mandated | skills/run-autopilot/scripts/test_store_tree_prose.py:158 | ALICE | cap-overflow deferral (grouped) |
| [1/4] | ⚪ Low | `test_store_gitignore_is_a_literal_not_a_join_call` pins a source-text spelling, not behavior | skills/run-autopilot/cli/test_store_tree_gitignore.py:75 | ALICE | cap-overflow deferral (grouped) |
| [1/4] | ⚪ Low | Raw `status --porcelain` remains in `wave_launch.py` and `wave_review.py` | skills/run-autopilot/cli/wave_review.py:403 | BLAKE | settled deferral (destructive-step rule) |
| [1/4] | ⚪ Low | `pause.py` does not import `foreign_dirty`; PRD premise mismatch, not a defect | skills/run-autopilot/cli/pause.py:46 | BLAKE | settled deferral |
| [1/4] | ⚪ Low | `--state`, `store_dir` and the `enter.py` call go beyond the PRD text | skills/run-autopilot/cli/__main__.py:1186 | BLAKE | settled deferral |
| [1/4] | ⚪ Low | Cannot statically verify: release-checks pass at `1daea55` | N/A | BOB | discarded — gate ran it, exit 0 |
| [1/4] | 🟡 Medium | Replay: 3 intake layout tests still pass against the pre-change code | hooks/test_enforce_prd_location.py | mech-check | folded into the task-13 row |
| [1/4] | 🟡 Medium | Replay: 2 recorder tests pass at base (`..._uses_the_bare_git_dir_recorded_in_state`, `..._drained_exit_records_the_store_once...`) | skills/run-autopilot/cli/test_loop_record_store.py | mech-check | discarded — control / behavior-preserving |
| [1/4] | 🟡 Medium | Replay: `test_cli_dirty_still_reports_a_change_outside_the_store` passes at base | skills/run-autopilot/cli/test_store_boundary.py | mech-check | discarded — explicit control test |
| [1/4] | 🟡 Medium | Replay: 3 writer tests pass at base (`..._rewrites_a_body_it_cannot_read`, `..._raises_when_an_unreadable_body_cannot_be_overwritten`) | skills/run-autopilot/cli/test_store_gitignore.py | mech-check | discarded — contract-amendment tests |
| [1/4] | 🟡 Medium | Replay: `test_the_record_store_verb_commits_outside_a_wave_lane` passes at base | skills/run-autopilot/cli/test_store_lane.py | mech-check | discarded — control test |

### Why four replay rows were discarded rather than deferred

This is an **incremental** review, so the replay base is cycle-1 HEAD, where `dirty`,
`record-store` and the flat-layout exclusion already existed. A test that pins *pre-existing*
behavior as a control passes there by construction — the replay block's own caveat ("a
behavior-preserving refactor's tests pass by design") is exactly this case. Named individually:
`test_cli_dirty_still_reports_a_change_outside_the_store` and
`test_the_record_store_verb_commits_outside_a_wave_lane` are the positive controls for the
narrowing task 10 introduced; `test_loop_site_runner_uses_the_bare_git_dir_recorded_in_state`
pins task 15's behavior-preserving collapse; and the two
`test_ensure_store_gitignore_*unreadable*` tests pass at base **because task 13 chose to amend
the contract rather than change the writer** — the defect was the either-or `except` hedge that
asserted nothing, and that hedge is gone. The four rows that stayed as findings (task-13
cluster, prose ordering, host-signing) are the ones where a reviewer independently showed the
test pins nothing it claims to.

## Decision gate

`state.cycle` (2) `>= state.rework_cap` (2) and an unresolved HIGH remains, so the cap gate
fired. `$_AUTOPILOT_LOOP` is set, and **no CRITICAL** was raised, so the loop-mode cap-out
branch applies: every unresolved finding is appended to `state.deferred_decisions` as a
`cap-overflow` record and the PRD proceeds to the finalize hand-off as
converged-with-deferrals. No third review cycle, no rework dispatch, no batch pause, no stall.

**12 cap-overflow records** were written (2 high, 8 medium, 2 low groups); six findings were
settled or discarded into the ledger, one was auto-dismissed by the consolidator, and four
replay rows were discarded with the reason above. Nothing was dropped silently.

The two HIGHs share one root cause worth naming for whoever picks up the deferrals: **the
derived store prefix is threaded into `foreign_dirty` and `record_store` but not into every
other store-aware caller**, and **the wave-lane guard is applied at three of four recorder call
sites**. One follow-up PRD that threads the prefix through `lane_check` and the wave modules and
adds the missing guard closes four of the twelve records.

## Alice

Consensus lens, implementation-aware. 4 Medium, 4 Low, no High, no Critical. She verified every
one of the eight cycle-1 tasks resolved (task 9 prefix derivation with real bare-repo tests,
task 10's flat-layout exclusion and session-outcome gate, task 11's recording, task 12's exit 13
and reported write failures, task 13's removed hedges and real-git recorder test, task 14's
pinned `--site`, task 15's single `custody.store_git` runner, task 16's literal bytes and
reworded `work/SKILL.md`), and ran the 13 touched store, lane and prose suites: 194 passed, 6
subtests passed. She did not run `release-checks` and said so.

- 🟡 `_record_review_once_store` wraps the recorder in `except Exception: pass`, so any failure in `store_git`, `repo_and_git_dir` or an unexpected raise in `record_store` is dropped with no output. A swallowed failure here leaves the review-once store writes uncommitted with no trace. Fix: catch the same `(OSError, subprocess.SubprocessError)` set `record_store` uses, or print one `autopilot: review-once store record failed: ...` stderr line, and keep the unchanged return code. | File: skills/run-autopilot/cli/loop.py:506 | Task: 11
- 🟡 `lane_check.diff_signal` excludes the literal `STORE_EXCLUDE_PATHSPECS` with `cwd=repo_root`. It never receives the store dir, so it does not follow the derived store prefix that task 9 added to `foreign_dirty` and `record_store`. For a bare-backed root such as `~/.claude` under `$HOME`, `repo_root` is the work-tree root and the store is at `.claude/docs/dev/project-management`. The exclusion then misses it, and store commits count as production paths again, so every solo PRD escalates. Same defect class as the cycle-1 task 9 finding. I read the code and did not run it, so confidence is medium. | File: skills/run-autopilot/cli/lane_check.py:53 | Task: 10
- 🟡 `in_wave_lane` treats any non-empty `_AUTOPILOT_REVIEW_SLOTS_DIR` as "this is a wave lane". That variable is also the generic review-concurrency semaphore. A standalone loop with the slots dir set would silently skip every `record-store` call. The tracked store would then go uncommitted, which is the PRD's own failure mode. | File: skills/run-autopilot/cli/store_tree.py:72 | Task: 10
- 🟡 Redundancy added in this diff. `test_store_tree_legibility.py` re-defines `FakeGit`, `_subcommand`, `_one_line`, `_autopilot_dir`, `_write_state`, `SUBCOMMANDS` and `REPO`. Every one already exists in the new shared `store_tree_testutil.py`, which four sibling modules import. | File: skills/run-autopilot/cli/test_store_tree_legibility.py:48 | Task: 12
- ⚪ The new `test_task_boundary_handoff_records_the_store_before_the_leave_row` is not a PRD-mandated name, but it copies the misleading one. Its body asserts the leave row comes before `record-store`, the opposite of what the name says. | File: skills/run-autopilot/scripts/test_store_tree_prose.py:158 | Task: 14
- ⚪ Stale docstrings after the style-gate split deleted `test_store_tree.py`. | File: skills/run-autopilot/cli/test_store_boundary.py:8 | Task: 13
- ⚪ `test_store_gitignore_is_a_literal_not_a_join_call` pins a formatting choice by searching `store_tree.py` source text for a substring. It fails only on that one spelling and fails on no behavior. | File: skills/run-autopilot/cli/test_store_tree_gitignore.py:75 | Task: 16
- ⚪ `autopilot dirty` now returns exit 13 on a failed probe, but the prose gates still read "comes back empty". A session following that wording sees empty stdout plus a stderr line and an exit it has no instruction for. | File: skills/work/SKILL.md:364 | Task: 16

```
R1: pass
R2: pass
R3: pass
R4: fail
R6: pass
R7: pass
R8: pass
R9: pass
R10: fail
R11: pass
R12: pass
R13: fail
```

## Blake

Blind lens: PRD and rubric only, no diff, no file list, no review history, no settled-decisions
list. He located the code himself, ran the six store and prose suites (69 passed) and
`release-checks` (no failures). No filesystem-notes block was needed. 5 Medium, 4 Low. One of
his Mediums was auto-dismissed against the ledger by `--ledger-dismiss BLAKE` (below).

- 🟡 `record-store` silently does nothing inside a wave lane and `loop.py` and `loop_act.py` skip it there too. The PRD specifies no lane exception, so this is added behaviour. | File: skills/run-autopilot/cli/__main__.py:1216 | Task: Phase 1
- 🟡 The loop calls `record_store` on its own at three sites. The PRD names only the handoff procedure, the task-boundary handoff, the rotation commit and the drained exit. The per-session loop commit and the `review_once` commit are extra, and the latter swallows every exception with a bare `except Exception: pass`. | File: skills/run-autopilot/cli/loop.py:509 | Task: Phase 1
- 🟡 `autopilot dirty` returns exit 13 when the git probe fails, which the PRD does not define. The prose gates read "comes back empty". A failed probe prints nothing to stdout, so a gate that reads stdout instead of the exit code treats a failed probe as a clean tree. That is a fail-open path. | File: skills/run-autopilot/cli/__main__.py:1200 | Task: Phase 1
- 🟡 The PRD's acceptance tests and its success-metric command name `skills/run-autopilot/cli/test_store_tree.py`, and that file does not exist. Every named test exists in a split file, and `release-checks` lists them, but the PRD's literal metric command fails with "file not found". | File: skills/run-autopilot/cli/test_store_tree_cli.py | Task: general
- ⚪ The three wave modules call `foreign_dirty(repo, run_git=run_git)` without `store_dir`. In a bare-repo-backed project the prefix is then empty. Store paths would read as foreign and the wave refusals would fire on store churn. | File: skills/run-autopilot/cli/wave_assemble.py:273 | Task: Phase 1
- ⚪ Raw `status --porcelain` remains in `wave_launch.py` and `wave_review.py` on lane and assembly worktrees. This is probably deliberate, since the rule is a destructive precondition. | File: skills/run-autopilot/cli/wave_review.py:403 | Task: Phase 1
- ⚪ `pause.py` does not import `foreign_dirty`. The PRD lists it as a site, but the file contains no porcelain parsing. This is a PRD premise mismatch, not a defect. | File: skills/run-autopilot/cli/pause.py:46 | Task: Phase 1
- ⚪ `record-store` and `dirty` take an extra `--state` flag the PRD does not list, and `foreign_dirty` and `record_store` gain a `store_dir` parameter. `autopilot enter` also now calls `ensure_store_gitignore` itself. | File: skills/run-autopilot/cli/__main__.py:1186 | Task: Phase 1

He also recorded what he checked and found sound: `foreign_dirty`'s `-z` porcelain with
rename/copy handling and the collapsed-untracked-directory re-listing; `record_store`'s
store-only staging and commit, its `None` on nothing staged, and its single stderr line on
failure; `ensure-store`'s idempotence and code-not-editor writer; and every rewritten prose
site plus the CHANGELOG entry.

```
B1: pass
B2: pass
B3: pass
B4: pass
B5: pass
B6: fail
B7: fail
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

### Auto-dismissed (ledger)

- [BLAKE] 🟡 `STORE_GITIGNORE` and the Disposable bullet go beyond the PRD list. They add `.review-gate-blocks`, `.review-gate-failed`, `.lane-guard-blocks`, `wave.json` and `review-paths`, and the extras are interleaved, so the list no longer matches the PRD's order. All 18 PRD patterns are still present. | File: skills/run-autopilot/cli/store_tree.py:30 — dismissed against the cycle-1 ledger: requirements ambiguity resolved in the design doc, which states the 23-pattern body IS the union of the PRD's draft list and the live Retention Disposable bullet, and that the two sources disagreeing was the defect. The shipped superset is the correct answer; the PRD text is the stale side.

## Bob

Doubt + de-slop lens, codex in its read-only sandbox, **resumed from his cycle-1 thread**
(`--resume-thread 01a0fce2-df57-7220-8f24-ad3af1e88258`). Ran first time, no retry, no fallback.
2 High, 6 Medium, 1 Low, plus the FIX/VERIFY/KNOWN buckets and the D-rubric verdicts. He raised
both of this cycle's HIGHs; the gate confirmed both against the code.

- 🟠 Lane routing still excludes only top-level store paths; `.claude/docs/dev/project-management/*.jsonl` remains production evidence and escalates nested bare-backed solo projects | File: skills/run-autopilot/cli/lane_check.py:55 | Task: 10
- 🟠 review-once bypasses the wave-lane guard and can commit store files onto a lane branch, reopening the assembly conflict problem | File: skills/run-autopilot/cli/loop.py:506 | Task: 11
- 🟡 review-once silently swallows every resolver or recorder exception; preserve its exit behavior but report recording failures | File: skills/run-autopilot/cli/loop.py:516 | Task: 11
- 🟡 Task 13 left the seven assembly refusal replay survivors unchanged; the requested paired store-only controls remain missing | File: skills/run-autopilot/cli/test_wave_assemble.py:473 | Task: 13
- 🟡 Task 13 left the six launch refusal replay survivors unchanged; the requested paired store-only controls remain missing | File: skills/run-autopilot/cli/test_wave_launch_refusals.py:158 | Task: 13
- 🟡 The new task-boundary pin checks leave-before-record but never checks record-before-STOP, leaving half the required ordering untested | File: skills/run-autopilot/scripts/test_store_tree_prose.py:162 | Task: 14
- 🟡 The new legibility suite duplicates FakeGit and helpers already provided by store_tree_testutil; import the shared implementations instead | File: skills/run-autopilot/cli/test_store_tree_legibility.py:48 | Task: 13
- 🟡 The host-signing test verifies Git configuration and the test fixture rather than product behavior; remove it while retaining the fixture's signing override | File: skills/run-autopilot/cli/test_lane_cli.py:215 | Task: 13
- ⚪ Cannot statically verify: release-checks pass at revision 1daea55509ef17d8eb7703b905273b15d0bcaa9e | File: N/A | Task: general

```
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
R12: pass
R13: fail
```

FIX:

- Nested-store lane exclusions — skills/run-autopilot/cli/lane_check.py:55 — Pass the state-derived store directory into the check, derive exclusions relative to `repo_root`, and test a nested bare-backed ledger-only commit.
- Wave recording through review-once — skills/run-autopilot/cli/loop.py:506 — Apply `in_wave_lane(self.env)` before recording and add a wave-environment review-once test.
- Silent review-once failures — skills/run-autopilot/cli/loop.py:516 — Emit a normalized stderr diagnostic while preserving the original exit result; assert the diagnostic in the raising-recorder test.
- Assembly replay survivors — skills/run-autopilot/cli/test_wave_assemble.py:473 — Add paired store-only acceptance controls to the unresolved refusal cases.
- Launch replay survivors — skills/run-autopilot/cli/test_wave_launch_refusals.py:158 — Add paired store-only acceptance controls to the unresolved refusal cases.
- Incomplete handoff-order pin — skills/run-autopilot/scripts/test_store_tree_prose.py:162 — Assert leave-row position < record-store invocation position < final STOP position.
- Duplicated test utilities — skills/run-autopilot/cli/test_store_tree_legibility.py:48 — Replace the duplicated FakeGit and matching helpers with imports from `store_tree_testutil`.
- Fixture-only signing test — skills/run-autopilot/cli/test_lane_cli.py:215 — Remove this test; keep signing disabled in the fixture and retain product behavior tests.

VERIFY:

- Release verification — Run `bash dev/bin/release-checks` at revision `1daea55509ef17d8eb7703b905273b15d0bcaa9e` and confirm exit 0. **Queued** in `00236-track-the-store-without-tripping-the-loop-v1-checks-2.json` (it names one exact runnable command). There is no work phase on the cap-out path, so the **review gate ran it itself** at that exact HEAD: exit 0. Recorded as `result.exit: 0`, and the same run is this cycle's `Tests:` source.

KNOWN:

- (none)

```
D1: pass
D2: pass
D3: pass
D4: pass
D5: pass
```

## Carl

Gemini lens on backend=copilot. Reviewed as a generalist (no frontend surface in this diff) and
ran the store, wave, lane and hook suites himself, plus `release-checks`. He reported **no
issues** and passed every rubric rule — the panel's most lenient read for the second cycle
running.

- ✅ No issues found

Two artifacts of his run, neither a finding: his first `release-checks` invocation failed
because he launched it inside the nested-dispatch guard environment (`AUTOPILOT_DISPATCH_DEPTH`
set, so every `codex-run.sh`/`gemini-run.sh` sub-test refused with exit 3); he diagnosed that
himself and re-ran with `env -u AUTOPILOT_DISPATCH_DEPTH -u COPILOT_CLI -u _AUTOPILOT_LOOP`,
which passed. He also observed that a bare whole-repo `pytest` collects 125 errors, all from
scratch files under `docs/dev/tmp/` (for example `devon2_probe_test.py`); that tree is
gitignored scratch and `dev/bin/release-checks` is the project's gate.

```
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

## Mechanical blocks (computed, absorbed into the table)

Tautological-shape check: 176 test functions across 15 changed test files, **no `[MECH]` lines**
— no constant, self-comparing or hedged assert shapes. Notably the cycle-1 either-or `except`
hedge is gone from `test_store_gitignore.py`, which is what task 13 was for.

Mechanical facts block: computed over the 11 changed non-test Python files; no reviewer made a
countable claim that contradicts it, so nothing was discarded on that ground this cycle.

Fail-first replay against `5ab1a1f`: 100 touched tests ran, **76 failed at base, 24 passed**; 6
test files could not be collected at base. Eight `[MECH]` lines. Four folded onto rows reviewers
had already raised (`test_lane_cli.py`, `test_store_tree_prose.py`, and the `test_wave_review.py`
and `hooks/test_enforce_prd_location.py` survivors onto the task-13 row), with `mech-check`
appended as a finder. The other four became their own rows and were discarded as control or
contract-amendment tests — reasoning in "Why four replay rows were discarded" above.

## Follow-up tasks created

**None.** The cap-out path creates no tasks and dispatches no rework: `state.cycle` 2
`>= state.rework_cap` 2. The twelve open findings live in `state.deferred_decisions` as
`cap-overflow` records and surface at batch end.

Verdict: 25 findings
Tests: 2156 passed, 0 failed, 0 skipped (suite run this cycle)
