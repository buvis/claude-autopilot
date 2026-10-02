---
prd: dev/local/prds/wip/00216-review-the-assembled-wave-and-run-a-wave-end-to-end-v1.md
review: 2
date: 2026-09-29
head_sha: 5bed041ff0d73d69a560ed382d8e6b78c5a17cac
codex_thread_id: 01a0eb4c-7e04-74c3-9f89-dbdc81635592
reviewers: alice,blake,bob,carl
agents:
  alice: available
  blake: available
  bob: available
  carl: available
---

# Review: 00216-review-the-assembled-wave-and-run-a-wave-end-to-end-v1

Diff range: `fc5e559feb59baa9320f17127ed8ed6b8870cfa0..5bed041ff0d73d69a560ed382d8e6b78c5a17cac`

codex_rung_guard: not fired

## Run conditions

- **Incremental cycle 2.** `gather-context.sh --since fc5e559…`, the cycle-1 `head_sha`. The range holds only the eight `[D1]` rework tasks (6-13), 25 commits, 14 files, +1863/-628.
- **Cap reached.** `state.cycle` is 2 and `rework_cap` is 2. One unresolved 🟠 HIGH survives this cycle, so the loop did NOT converge and there is no cycle 3 — the loop-mode cap-out applies (`phase-review.md` § Cap check): every unresolved finding below is recorded as a `cap-overflow` deferral and the PRD finalizes with them open. No CRITICAL survives, so this is the defer branch, not the `cap_critical` custody stall.
- **No follow-up tasks created (deliberate).** `review-work-completion` step 7 creates rework tasks for the Phase 6 dispatch the cap-out never reaches. Creating them here would leave ~20 permanently-pending tasks in `state.tasks` and finalize the PRD at 13/33 completed. The findings are recorded as deferrals instead, which is the sink the cap-out branch names.
- **Context pack:** `engram pack` failed again, deterministically (`not inside a registered repo; register it in ~/.config/gita/repos.csv`). Substituted `(no pack available this cycle)` in every prompt that takes it; no retry. Review degraded, not invalid.
- **Bob prompt shape (deviation, recorded — same as cycle 1).** Bob was dispatched with the **inlined** prompt on the first dispatch (review context + full diff inlined verbatim, 239 KB), because this repo has a recorded history of the codex reviewer failing on path references. He returned a complete review with all twelve `R{n}` and all five `D{n}` lines on the first run; no retry was spent.
- **Bob was NOT resumed (deviation, recorded).** The cycle-1 `codex_thread_id` `01a0e9e5-9c75-7cb3-9e4f-3e236de8b1e3` exists, but `--resume-thread` was deliberately omitted: stacking a resumed cycle-1 session under a 239 KB inlined prompt risks a context overflow that would cost the doubt lens entirely, and the inlined prompt already carries cycle 1's consolidated findings verbatim. A fresh thread id was captured for the frontmatter above.
- **Carl's first `release-checks` run failed on inherited environment, not on the repo.** `AUTOPILOT_DISPATCH_DEPTH`/`COPILOT_CLI`/`_AUTOPILOT_LOOP` leaked into his shell and made the `[checks] runner recursion guard` block report 20 failures (`refusing nested dispatch (depth=1)`). He re-ran with `env -u …` and the suite passed. This is a reviewer-environment artifact; the orchestrator's own clean run of the same command is the `Tests:` line below.
- **Consolidation:** `consolidate_findings.py`, 4 reviewers, with `--ledger … --ledger-dismiss BLAKE`. Nothing was auto-dismissed (no `### Auto-dismissed (ledger)` section emitted).
- **Consolidation was corrected by hand (fail loud).** The script's suffix-stripping merge folded **three distinct findings** into one row: `wave_review.py:522` (land after a hand review, 🟠), `wave_review.py:482` (the `review_failed` summary omitting the stub location, 🟡) and `wave_review.py:418` (`branch -d` vs `branch -D`, ⚪) all matched after suffix stripping and were emitted as a single `[3/4] 🟠` row. They are un-merged below, and the HIGH's real consensus is **2/4** (ALICE, BLAKE), not 3/4. Separately, Carl's terse `land does not hold wave.json's lock` (`:516`) was NOT merged with the identical ALICE/BOB row (`:514`); it is merged below, raising that row to `[3/4]`. Both corrections are orchestrator judgment on issue text plus file, recorded here rather than applied silently.

## Alice (consensus lens)

Ran the five wave test files (87 passed). Checked every cycle-1 finding against the current code and reported 18 of them resolved: the CRITICAL `--state` registration, the real TTY confirmation, the `--review-slots` refusal, the pinned status cadence, both summary lines, the `interrupted` status under the lock, the resumable destructive tail, `wave-slots/` removal, the `wave.json` move, the missing-worktree guard, `_is_basename` on `review`/`land`, the `_guarded` refusal contract, the file/function size splits, the collapsed `git diff` call sites, the separate stub field sections, the de-hedged test, the restored keyword-only seams, and the docs/docstring corrections.

8 findings: 1 High, 3 Medium, 4 Low. Full text: `dev/local/tmp/alice-output-00216c2.txt`.

R1: pass
R2: pass
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

## Blake (blind lens — PRD only, no diff)

Ran the four wave test files (78 passed). Did not run `release-checks` or `test_gather_context_paths.sh`.

Verified as implemented from the spec alone: `stub_text`/`review_paths`, `seed_state`'s call order and `meta/` copy, `review`'s seed/marker/spawn/outcome, `land`'s exit 5, `merge --ff-only`, `lane: "assembly"` migration, cleanup, archive and converged line, the `gather-context.sh` filter on both diff commands, the release-gate and schema plumbing, and `wave run`'s poll, cadence, refusal, exit codes and interrupt handling.

8 findings: 1 High, 4 Medium, 3 Low. Full text: `dev/local/tmp/blake-output-00216c2.txt`.

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
B15: fail
B16: pass
B17: pass
B18: pass
B19: pass

## Bob (codex — consensus + doubt/de-slop lens)

Static-only sandbox, inlined prompt, no resume. 8 findings. Full text: `dev/local/tmp/bob-output-00216c2.txt`.

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

Doubt buckets: 6 FIX, VERIFY `- (none)`, KNOWN 2 (the all-kept-wave lifecycle, and signals during the nested review — both recorded as out of this PRD's scope). Because VERIFY is empty, **no verification-check queue file was written for cycle 2**.

D1: pass
D2: pass
D3: pass
D4: pass
D5: pass

## Carl (gemini — frontend/design specialist, generalist here)

Backend: copilot. Read the context, the full diff and the changed sources, re-ran `release-checks` (after sanitizing the inherited dispatch-guard environment, see Run conditions), swept for TODO/FIXME/skip/xfail markers, and probed `fcntl.flock` reentrancy directly to check the `land` locking claim. 1 finding, no frontend surface in this diff. Full text: `dev/local/tmp/carl-output-00216c2.txt`.

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

## Mechanical checks (computed)

- **Function line counts:** every function in the changed files is under the 50-line cap. The largest are `assemble` (49), `wave_cli.run` (46), `wave_run.run` (45), `review` (45) and `land` (44). File sizes: `test_wave_run.py` 699, `test_wave_review.py` 704, `test_wave_review_land.py` 404 — all under 800. Cycle 1's R12/R13 failures are cleared.
- **Tautological shapes:** none. 71 test functions checked across 5 files. Cycle 1's `or`-hedged `test_stub_prd_lists_the_diff_scope` is fixed.
- **Fail-first replay against `fc5e559feb59`:** 60 touched tests ran, 39 failed at base, 21 passed there, 0 files uncollectable. The 21 are absorbed into the table below as four rows (one folded onto Bob's existing docstring row, three new). Most are task 10's verbatim test split — a behaviour-preserving move of tests that already passed — which the replay block itself names as passing by design.

## Consolidated Findings

| Consensus | Severity | Issue | File | Task | Found By |
|-----------|----------|-------|------|------|----------|
| [2/4] | 🟠 | `land` still cannot land after a hand review (cycle-1 finding not fixed). `review_failed` returns 4 unconditionally via `_land_review_failed`, even when the operator has since moved the stub to the assembly worktree's `prds/done/`. `assembled`/`assembled_partial` are refused as "not landable". The only route is hand-editing `wave.json` status to `converged`, which nothing documents or tests. The PRD's Edge case says "a later `wave land` after a hand review still lands" and the feature text says `land` is its own verb so an operator who reviewed by hand can still land. `test_review_failed_keeps_master_untouched` pins the 4; nothing tests a landable hand-reviewed wave | skills/run-autopilot/cli/wave_review.py:522 | 7 | ALICE, BLAKE |
| [3/4] | 🟡 | `land` does not hold `wave.json`'s lock for its body (cycle-1 finding, still open). It takes the lock only for the initial load (`wave_review.py:515-516`) and for short later saves; the merge, migration and cleanup run unlocked, so a concurrent `wave abort` or `assemble` can interleave and migration can repeat. The design and the PRD say `assemble` holds it for the whole body and `land` should match | skills/run-autopilot/cli/wave_review.py:514 | 7 | ALICE, BOB, CARL |
| [2/4] | 🟡 | Docs in `waves.md` now contradict the rework. § wave run says `land` runs "only once review reports `converged`" (waves.md:201), but `run` also calls `land` on `review_failed` to record the summary line and exit 4. The exit-`1` row (waves.md:224) omits the `--review-slots < 1` refusal and a declined or EOF confirmation, and the TTY Enter prompt is never described. § `wave review` says preconditions are "propagated rather than caught" (waves.md:174-176), but `wave_cli` now prints `autopilot: …` and returns 1. § `wave land` says ValueError is raised for any status other than `converged`/`review_failed` (waves.md:193), but `done` is now accepted as a resume path; it also omits the summary line, the `wave-slots/` removal, the archive to `reports/<id>-wave.json`, and the uncommitted-edit refusal | skills/run-autopilot/references/waves.md:174 | general | ALICE, BLAKE |
| [2/4] | 🟡 | The `review_failed` summary line names only the review file, not "where the stub sits" (`hold/` or `wip/`) as the PRD's Land behavior requires. The line reads `## Assembly review: review_failed, see <path>`, or "see no review file written" when none exists | skills/run-autopilot/cli/wave_review.py:482 | 7 | BLAKE, BOB |
| [1/4] | 🟡 | The release gate omits the new refusal tests, so `release-checks` can pass without exercising them. **Verified by the orchestrator:** `dev/bin/release-checks:108-122` lists 14 wave test files and `test_wave_cli_refusals.py` (256 lines, 14 tests, added by task 9) is not among them | dev/bin/release-checks:117 | 9 | BOB |
| [1/4] | 🟡 | A malformed `plugins` value can raise an uncaught `TypeError` instead of the promised refusal message that task 9's own review fix introduced | skills/run-autopilot/cli/wave_review.py:169 | 9 | BOB |
| [1/4] | 🟡 | The confirmation gate launches on an unrecognized reply such as `cancel`. It honours Enter and EOF and a declined reply, but anything else falls through to launch | skills/run-autopilot/cli/wave_run.py:75 | 6 | BOB |
| [1/4] | 🟡 | Simplification (cycle-1 finding, not addressed): `review()` re-implements `_spawn_lane`'s recipe inline — the env filter, `_AUTOPILOT_TRACON_CHILD`, the `wrapper.log` open, the `Popen` kwargs and `_SPAWN_CMD` (`wave_review.py:314-326` against `wave_launch.py:186-199`). Give `_spawn_lane` an optional slots argument, or drop the slot env when it is None, and call it, so the two spawn sites cannot drift | skills/run-autopilot/cli/wave_review.py:314 | 2 | ALICE |
| [1/4] | 🟡 | `_land_cleanup` refuses to remove a dirty assembly worktree, but the fixtures gitignore `docs/dev/project-management/` entirely (`test_wave_launch.py:71`). In a repo that tracks that tree the worktree keeps untracked `state.json`, `review-paths`, `wrapper.log`, the copied `meta/` and the copied reviews; the dirty check then raises `ValueError` after the fast-forward merge and after status is already `done` (`wave_review.py:402`). Suspected, not reproduced. Related to but distinct from the settled cycle-1 deferral, which is about the precondition rather than the cleanup tail | skills/run-autopilot/cli/wave_review.py:399 | 3 | BLAKE |
| [1/4] | 🟡 | The § Review and land "Scope note" in `references/waves.md` says the review covers "the paths the wave's assembled lanes actually touched". The code and the PRD narrow it to files listed by two or more lanes plus `WAVE_APPEND_ONLY`. The CHANGELOG entry repeats the wrong wording | skills/run-autopilot/references/waves.md:178 | 2 | BLAKE |
| [1/4] | 🟡 | 3 touched tests pass against the pre-change code, so they do not pin this cycle's change: `test_stub_field_sections_name_every_merged_lane`, `test_stub_prd_lists_the_diff_scope`, `test_review_releases_the_lock_during_the_wait`. The task-11 fix itself IS pinned by `test_stub_prd_lists_description_inputs_outputs_behavior_separately`, which fails at base | skills/run-autopilot/cli/test_wave_review.py | general | mech-check |
| [1/4] | 🟡 | 6 touched tests pass against the pre-change code: `test_land_fast_forwards_master_and_removes_the_worktree`, `test_land_migrates_the_assembly_artifacts_as_lane_assembly`, `test_land_refuses_when_master_moved`, `test_review_failed_keeps_master_untouched`, `test_land_precondition_rejects_assembled_status`, `test_land_refreshes_the_archived_head_sha`. All six are task 10's verbatim move out of `test_wave_review.py`, so passing at base is expected of a behaviour-preserving split | skills/run-autopilot/cli/test_wave_review_land.py | general | mech-check |
| [1/4] | 🟡 | 11 touched tests pass against the pre-change code, including `test_run_orders_plan_launch_wait_assemble_review_land`, `test_run_without_tty_needs_yes` and `test_run_exit_code_follows_the_weakest_step`. Mostly task 10's verbatim move into the new file; verify each one that is NOT a move, because a new regression test that passes at base pins nothing | skills/run-autopilot/cli/test_wave_run.py | general | mech-check |
| [2/4] | ⚪ | When `assemble` returns 3 with `merged: []`, `_review_and_land` still runs a full-roster review over an empty assembly and then lands a no-op (cycle-1 finding, unchanged). Return the assemble code before `review` when nothing merged | skills/run-autopilot/cli/wave_run.py:141 | 5 | ALICE, BOB |
| [2/4] | ⚪ | `_review_and_land` wraps `land` in `if outcome in ("review_failed", "converged")`, but `review()` only returns those two values, so the guard is always true and the branch is dead. Call `land` directly and drop `outcome` | skills/run-autopilot/cli/wave_run.py:94 | 6 | ALICE, BLAKE |
| [2/4] | ⚪ | The new docstring test passes against the pre-change revision and does not pin this rework — it asserts about a test file's own content, which the replay overlays with HEAD's version, so it can never fail there | skills/run-autopilot/cli/test_wave_docs.py:376 | 12 | BOB, mech-check |
| [1/4] | ⚪ | `_GUARDED_ERRORS` omits `OSError`, so I/O failures still surface as raw tracebacks: `_cycle_count` reading a missing `state.json` (`wave_review.py:366-369`) after master has already been fast-forwarded, and `_repo_from_worktree` reading the worktree's `.git` file (`wave_review.py:238`) | skills/run-autopilot/cli/wave_cli.py:37 | 9 | ALICE |
| [1/4] | ⚪ | In the SIGINT/SIGTERM handler, `_kill_lane` failure strings are discarded. The handler also holds the wave lock while each lane's group gets up to 60 s of SIGTERM grace plus 10 s of SIGKILL grace, and still writes `interrupted` and exits 130 even if a group survived | skills/run-autopilot/cli/wave_run.py:29 | 4 | BLAKE |
| [1/4] | ⚪ | `land` runs `branch -d` where the design says `branch -D` (cycle-1 finding, unchanged). It works after a clean fast-forward, but it is a documented deviation | skills/run-autopilot/cli/wave_review.py:418 | 7 | ALICE |
| [1/4] | ⚪ | Signals during the nested review wait still have no resume or termination handler. Bob bucketed this KNOWN, matching the design doc's own recorded scope-out; carried for visibility, not as a regression | skills/run-autopilot/cli/wave_review.py:292 | 5 | BOB |
| [1/4] | ⚪ | The PRD's literal paths (`dev/local/prds/wip`, `dev/local/autopilot/review-paths`, `dev/local/meta`) are implemented as `docs/dev/project-management/…` throughout, consistently across code, docs and tests, matching the repo's own working-documents convention. Spec drift by deliberate design correction, not a defect | skills/review-work-completion/scripts/gather-context.sh:108 | 2 | BLAKE |

Verdict: 21 findings
Tests: 1828 passed, 0 failed, 0 skipped (suite run this cycle)

`bash dev/bin/release-checks` exit 0 at `5bed041`, run once this cycle by the orchestrator. Composition: 1401 pytest + 303 subtests + 124 shell assertions. `dev/local/autopilot/last-verification.json` matched this HEAD but carried null counts, so its record could not be reused and the suite was run fresh — the counts above are this cycle's own run, not a reused record. Cycle 1 measured 1795 at `fc5e559`; the +33 is the `[checks] waves` block going 280 → 313.
