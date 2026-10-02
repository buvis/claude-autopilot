# Decision Audit Log: 00216-review-the-assembled-wave-and-run-a-wave-end-to-end-v1

PRD: `00216-review-the-assembled-wave-and-run-a-wave-end-to-end-v1.md`
Started: 2026-09-29T04:14:09Z
Completed: 2026-09-29T04:14:09Z
Autonomous: 7  |  Deferred: 24  |  Doubts: 0

### [autonomous] 2026-09-29T04:14:09Z

**Decision**: Design for PRD 00216 (wave review/land/run) needed 3 review dispatches (Claude, codex, Claude-fallback verification) that together found 1 cardinal-sin and 14 blockers, the most significant being a false claim that docs/dev/project-management is git-tracked (it is gitignored everywhere per test_wave_launch.py:71), a missing wave.json locking discipline in review()/land(), an internally-impossible review-outcome state machine, a wrong plugin-version pin shape in seed_state, and a non-persisting migrate_lane guard in land() that would double-append ledger jsonl lines on a crash retry.

**Choice**: Fixed all findings directly in the design doc: corrected the gitignored-everywhere architecture note, added wave.locked() usage to review()/land(), reconciled the converged/review_failed state machine, fixed the plugin-version extraction, and made land() pass wave["assembly"] itself (not a fresh dict) to migrate_lane so migrated_at persists across retries.

**Rationale**: No open cardinal sins or blockers remain after the 3rd dispatch; one non-blocker (review-wait SIGINT/SIGTERM handling) is a deliberately scoped-out risk documented in the design doc rather than silently dropped, since the PRDs own acceptance criteria scope signal handling to the lane-launch wait only.

### [autonomous] 2026-09-29T04:14:09Z

**Decision**: Cycle 1 review ran the full roster (Alice consensus, Blake blind, Bob codex doubt+de-slop, Carl gemini) and consolidated 33 findings: 1 critical, 6 high, 19 medium, 7 low. The critical (wave run unusable) was found independently by Alice and Blake and reproduced by the orchestrator directly.

**Choice**: No convergence. Grouped the non-critical findings into 9 themed follow-up tasks and routed the critical to Phase 6 behind a mandatory rework design.

**Rationale**: An unresolved CRITICAL plus six unresolved HIGH findings block convergence; cycle 1 < rework_cap 2, so rework is allowed rather than a cap-out.

### [autonomous] 2026-09-29T04:14:09Z

**Decision**: Task 10 (style-limit overruns + duplicated shapes) is a behavior-preserving refactor: split test_wave_review.py without losing cases, extract wave_cli.run into helpers with no verb behavior/exit-code change, reuse _default_run_git in _check_reviewable instead of raw subprocess.run, dedupe gather-context.sh's git diff with no behavior change - the task's own text pins all four as non-behavioral

**Choice**: skip Tess and Devon for task 10 (same construct precedent 00192-decision-tess-skip.json used for verbatim-move refactors); dispatch Ivan directly via the test-only/docs-only/config-only 'no failing tests' path (task Verify: line + acceptance criteria as FAILING_TESTS); record red_check n/a:refactor-existing-suite on the attempt; the existing suite (test_wave_cli_refusals.py, the remaining test_wave_review.py cases, test_gather_context_id.sh/test_gather_context_paths.sh) plus check_style_limits.py are the regression tests

**Rationale**: rules/testing.md binds new tests to new behavior and bug fixes; this task is neither - it is a style-limit fix and a simplification, and a Tess-authored test for a pure line-count/DI-seam change would either duplicate the existing behavioral coverage or assert on the refactor's own shape rather than on behavior

### [autonomous] 2026-09-29T04:14:09Z

**Decision**: Cycle 2 ran the full roster (Alice consensus, Blake blind, Bob codex doubt+de-slop, Carl gemini) over the incremental range fc5e559..5bed041 and consolidated 21 findings: 0 critical, 1 high, 13 medium, 7 low. Cycle 1's CRITICAL (`autopilot wave run` crashing on every invocation) is fixed and verified through `main()` by two new tests; 18 of cycle 1's other findings are confirmed resolved. The surviving HIGH is cycle 1's `land` cannot land after a hand review, which task 7 did not close. state.cycle 2 >= rework_cap 2.

**Choice**: Loop-mode cap-out: no CRITICAL survives, so all 21 unresolved findings were appended to deferred_decisions as cap-overflow records and the PRD proceeds to the finalize hand-off as converged-with-deferrals. No rework design, no fix task, no cycle 3.

**Rationale**: phase-review.md Cap check: at the cap with no unresolved CRITICAL, loop mode defers rather than pauses or stalls - stop polishing, not the batch. `autopilot defer` was deliberately NOT called: deferred_decisions is the only sink a cap-out writes.

### [autonomous] 2026-09-29T04:14:09Z

**Decision**: review-work-completion step 7 would create ~21 follow-up tasks for a Phase 6 dispatch that the cap-out never reaches, leaving them permanently pending in state.tasks and finalizing the PRD at 13/34 completed.

**Choice**: Skipped step 7 task creation entirely; recorded every finding as a cap-overflow deferral instead and said so in the review file's Run conditions.

**Rationale**: The cap-out branch pre-empts Classification and Phase 6, and names deferred_decisions as its sink. Orphan pending tasks would corrupt the Phase 9 task accounting and the batch report without any runner ever picking them up.

### [autonomous] 2026-09-29T04:14:09Z

**Decision**: consolidate_findings.py's suffix-stripping merge folded three distinct findings into one [3/4] HIGH row: wave_review.py:522 (land after a hand review, high), :482 (review_failed summary omits the stub location, medium) and :418 (branch -d vs -D, low). Separately it failed to merge Carl's terse `land` lock finding at :516 with the identical ALICE/BOB row at :514.

**Choice**: Un-merged the over-merged row into its three real findings (the HIGH's true consensus is 2/4, not 3/4) and merged Carl's row into the land-lock row (raising it to 3/4). Both corrections are stated in the review file's Run conditions rather than applied silently.

**Rationale**: rules/operating-principles.md Fail Loud: a hand-corrected consolidation must not read as the script's output, and an inflated consensus count on the one HIGH that decides the cap-out would misrepresent the evidence behind that decision.

### [autonomous] 2026-09-29T04:14:09Z

**Decision**: The cycle-1 codex_thread_id existed, so agent-invocation.md's incremental recipe would add --resume-thread to Bob's dispatch. Bob is also dispatched with the inlined prompt in this repo (recorded history of the codex reviewer failing on path references), which was 239 KB this cycle.

**Choice**: Dispatched Bob with the inlined prompt and WITHOUT --resume-thread, capturing a fresh thread id for the frontmatter. Recorded as a deviation in the review file.

**Rationale**: Stacking a resumed cycle-1 codex session under a 239 KB inlined prompt risks a context overflow that would cost the doubt lens entirely; the inlined prompt already carries cycle 1's consolidated findings verbatim, which is what the resume would have supplied.

### [deferred] 2026-09-29T04:14:09Z

**Decision**: autopilot wave run crashes on every real invocation (run sub-parser registers no --state, __main__._run_wave reads args.state)

**Choice**: deferred to batch end for the audit trail; fix task created in Phase 6 behind a rework design

**Rationale**: Classification routes Critical severity always to batch end, but a CRITICAL blocks convergence until fixed - this is not a decision to ship it

### [deferred] 2026-09-29T04:14:09Z

**Decision**: The wave family assumes docs/dev/project-management is gitignored, but commit 5d9036a in the same range states the store is tracked and git check-ignore confirms it is not ignored here; review()/launch() dirty-tree gates would refuse in a real managed repo

**Choice**: deferred to batch end

**Rationale**: requirements ambiguity spanning PRDs 00214/00215/00216; needs an operator decision on whether waves support a tracked store

### [deferred] 2026-09-29T04:14:09Z

**Decision**: Test-quality findings in commit 5d9036a files (two tests pass against pre-change code, one or-hedge assertion) that are not part of PRD 00216 tasks

**Choice**: deferred to batch end as out of scope

**Rationale**: those files belong to the tracked-store migration commit that landed inside the review range; fixing them here would widen scope beyond the PRD

### [deferred] 2026-09-29T04:14:09Z

**Decision**: `land` still cannot land after a hand review. `review_failed` returns 4 unconditionally via `_land_review_failed`, even after the operator moved the stub to the assembly worktree's `prds/done/`; `assembled`/`assembled_partial` are refused as 'not landable'. The only route is hand-editing `wave.json` status to `converged`, which nothing documents or tests. The PRD's Edge case requires a later `wave land` after a hand review to still land (skills/run-autopilot/cli/wave_review.py:522)

**Choice**: deferred to batch end

**Rationale**: rework cap reached with this finding unresolved

### [deferred] 2026-09-29T04:14:09Z

**Decision**: `land` does not hold `wave.json`'s lock for its body; it locks only the initial load and short later saves, so the merge, migration and cleanup run unlocked and a concurrent `wave abort`/`assemble` can interleave (skills/run-autopilot/cli/wave_review.py:514)

**Choice**: deferred to batch end

**Rationale**: rework cap reached with this finding unresolved

### [deferred] 2026-09-29T04:14:09Z

**Decision**: `references/waves.md` contradicts the rework in five places: land runs on `review_failed` too, the exit-1 row omits the `--review-slots < 1` and declined-confirm refusals, the TTY Enter prompt is undocumented, preconditions are now caught not propagated, and `done` is accepted as a land resume path (skills/run-autopilot/references/waves.md:174)

**Choice**: deferred to batch end

**Rationale**: rework cap reached with this finding unresolved

### [deferred] 2026-09-29T04:14:09Z

**Decision**: The `review_failed` summary line names only the review file, not where the stub sits (`hold/` or `wip/`) as the PRD's Land behavior requires (skills/run-autopilot/cli/wave_review.py:482)

**Choice**: deferred to batch end

**Rationale**: rework cap reached with this finding unresolved

### [deferred] 2026-09-29T04:14:09Z

**Decision**: The release gate omits `test_wave_cli_refusals.py` (256 lines, 14 tests, added by task 9), so `release-checks` passes without exercising the refusal contract. Verified by the orchestrator against dev/bin/release-checks:108-122

**Choice**: deferred to batch end

**Rationale**: rework cap reached with this finding unresolved

### [deferred] 2026-09-29T04:14:09Z

**Decision**: A malformed `plugins` value can raise an uncaught `TypeError` instead of the refusal message task 9's own review fix introduced (skills/run-autopilot/cli/wave_review.py:169)

**Choice**: deferred to batch end

**Rationale**: rework cap reached with this finding unresolved

### [deferred] 2026-09-29T04:14:09Z

**Decision**: The `wave run` confirmation gate launches on an unrecognized reply such as `cancel`; it honours Enter, EOF and an explicit decline, but anything else falls through to launch (skills/run-autopilot/cli/wave_run.py:75)

**Choice**: deferred to batch end

**Rationale**: rework cap reached with this finding unresolved

### [deferred] 2026-09-29T04:14:09Z

**Decision**: Simplification, carried from cycle 1: `review()` re-implements `_spawn_lane`'s recipe inline (env filter, `_AUTOPILOT_TRACON_CHILD`, `wrapper.log` open, `Popen` kwargs, `_SPAWN_CMD`), so the two spawn sites can drift (skills/run-autopilot/cli/wave_review.py:314)

**Choice**: deferred to batch end

**Rationale**: rework cap reached with this finding unresolved

### [deferred] 2026-09-29T04:14:09Z

**Decision**: `_land_cleanup` refuses to remove a dirty assembly worktree, but in a repo that tracks `docs/dev/project-management/` that worktree always holds untracked `state.json`, `review-paths`, `wrapper.log`, the copied `meta/` and reviews, so the check raises after the fast-forward and after status is already `done`. Suspected, not reproduced (skills/run-autopilot/cli/wave_review.py:399)

**Choice**: deferred to batch end

**Rationale**: rework cap reached with this finding unresolved; a downstream consequence of the settled tracked-store deferral, on the cleanup tail rather than the precondition

### [deferred] 2026-09-29T04:14:09Z

**Decision**: The `waves.md` Scope note and the CHANGELOG entry both say the assembly review covers the paths the lanes 'actually touched'; the code and the PRD narrow it to files listed by two or more lanes plus `WAVE_APPEND_ONLY` (skills/run-autopilot/references/waves.md:178)

**Choice**: deferred to batch end

**Rationale**: rework cap reached with this finding unresolved

### [deferred] 2026-09-29T04:14:09Z

**Decision**: Three touched tests in test_wave_review.py pass against the pre-change code and so pin nothing this cycle: test_stub_field_sections_name_every_merged_lane, test_stub_prd_lists_the_diff_scope, test_review_releases_the_lock_during_the_wait. The task-11 fix itself is pinned by test_stub_prd_lists_description_inputs_outputs_behavior_separately, which does fail at base

**Choice**: deferred to batch end

**Rationale**: rework cap reached with this finding unresolved

### [deferred] 2026-09-29T04:14:09Z

**Decision**: Six touched tests in test_wave_review_land.py pass against the pre-change code; all six are task 10's verbatim move out of test_wave_review.py, so passing at base is expected of a behaviour-preserving split

**Choice**: deferred to batch end

**Rationale**: rework cap reached with this finding unresolved; computed fact recorded rather than dropped

### [deferred] 2026-09-29T04:14:09Z

**Decision**: Eleven touched tests in test_wave_run.py pass against the pre-change code. Most are task 10's verbatim move into the new file, but each one that is not a move pins nothing and needs checking

**Choice**: deferred to batch end

**Rationale**: rework cap reached with this finding unresolved; computed fact recorded rather than dropped

### [deferred] 2026-09-29T04:14:09Z

**Decision**: When `assemble` returns 3 with `merged: []`, `_review_and_land` still runs a full-roster review over an empty assembly and then lands a no-op (skills/run-autopilot/cli/wave_run.py:141)

**Choice**: deferred to batch end

**Rationale**: rework cap reached with this finding unresolved

### [deferred] 2026-09-29T04:14:09Z

**Decision**: `_review_and_land` wraps `land` in `if outcome in ("review_failed", "converged")`, but `review()` only returns those two values, so the guard is always true and the branch is dead (skills/run-autopilot/cli/wave_run.py:94)

**Choice**: deferred to batch end

**Rationale**: rework cap reached with this finding unresolved

### [deferred] 2026-09-29T04:14:09Z

**Decision**: test_wave_review_test_docstring_has_no_stale_not_implemented_sentence passes against the pre-change revision: it asserts about a test file's own content, which the replay overlays with HEAD's version, so it can never fail there (skills/run-autopilot/cli/test_wave_docs.py:376)

**Choice**: deferred to batch end

**Rationale**: rework cap reached with this finding unresolved

### [deferred] 2026-09-29T04:14:09Z

**Decision**: `_GUARDED_ERRORS` omits `OSError`, so I/O failures still surface as raw tracebacks: `_cycle_count` reading a missing `state.json` after master is already fast-forwarded, and `_repo_from_worktree` reading the worktree's `.git` file (skills/run-autopilot/cli/wave_cli.py:37)

**Choice**: deferred to batch end

**Rationale**: rework cap reached with this finding unresolved

### [deferred] 2026-09-29T04:14:09Z

**Decision**: The SIGINT/SIGTERM handler discards `_kill_lane` failure strings, holds the wave lock through up to 70 s of per-lane kill grace, and writes `interrupted` and exits 130 even if a lane group survived (skills/run-autopilot/cli/wave_run.py:29)

**Choice**: deferred to batch end

**Rationale**: rework cap reached with this finding unresolved

### [deferred] 2026-09-29T04:14:09Z

**Decision**: `land` runs `git branch -d` where the design specifies `branch -D`; safe after a clean fast-forward, but a recorded deviation carried from cycle 1 (skills/run-autopilot/cli/wave_review.py:418)

**Choice**: deferred to batch end

**Rationale**: rework cap reached with this finding unresolved

### [deferred] 2026-09-29T04:14:09Z

**Decision**: Signals during the nested review wait still have no resume or termination handler. Bob bucketed this KNOWN, matching the design doc's own recorded scope-out (skills/run-autopilot/cli/wave_review.py:292)

**Choice**: deferred to batch end

**Rationale**: rework cap reached with this finding unresolved; already a documented scope-out, carried for visibility

### [deferred] 2026-09-29T04:14:09Z

**Decision**: The PRD's literal paths (dev/local/prds/wip, dev/local/autopilot/review-paths, dev/local/meta) are implemented as docs/dev/project-management/... throughout, consistently across code, docs and tests. Spec drift by deliberate design correction, not a defect (skills/review-work-completion/scripts/gather-context.sh:108)

**Choice**: deferred to batch end

**Rationale**: rework cap reached with this finding unresolved
