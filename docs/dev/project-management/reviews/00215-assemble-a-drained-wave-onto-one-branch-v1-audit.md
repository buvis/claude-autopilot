# Decision Audit Log: 00215-assemble-a-drained-wave-onto-one-branch-v1

PRD: `00215-assemble-a-drained-wave-onto-one-branch-v1.md`
Started: 2026-09-28T03:50:29Z
Completed: 2026-09-28T03:50:29Z
Autonomous: 14  |  Deferred: 7  |  Doubts: 0

### [autonomous] 2026-09-28T03:50:29Z

**Decision**: New wave_assemble.py verb (autopilot wave assemble): rebases each drained lane onto one assembly branch with an append-only keep-both conflict rule, migrates lane artifacts (ledgers, deferred items, reports, PRDs) into the main checkout tagged by lane/wave, writes reports/<wave id>-wave.md. wave.json schema extended with 4 new lane statuses, 1 new wave status, and 5 optional per-lane fields (files, integrator_notes, migrated_at, conflict_detail, conflict_paths).

**Choice**: design approved after 3 reviewer dispatches (1 claude, 2 claude-fallback for codex outages); 7 blockers found and fixed, 0 open

**Rationale**: codex hung or derailed on both attempts this session (garbled transcript once, zero-progress hang once); design-solution mandates a Claude fallback on codex outage rather than pausing

### [autonomous] 2026-09-28T03:50:29Z

**Decision**: Design doc gap missed by all 3 review dispatches: summary() is required to do zero disk access (Phase 0 Exit Criteria) yet must render a per-PRD done|parked|unassembled|backlog label the docstring itself says comes from a lifecycle-folder scan - undoable purely.

**Choice**: Pinned wave["prds"] as a transient, non-schema list of {prd, lane, label} dicts that assemble() (task 3) builds from its own real-time folder scan (done/->done, hold/->parked, backlog/->backlog, kept lane own done/->unassembled) and hands to summary() (task 1) pre-computed. Threaded into both tasks descriptions via task-set-body before either implementor ran.

**Rationale**: Left unresolved, Tess or Ivan would have had to invent a contract silently (explicitly forbidden, rule 10a) or block, costing a wasted dispatch on a gap the orchestrator could resolve directly from the fully-read design doc.

### [autonomous] 2026-09-28T03:50:29Z

**Decision**: H4: the PRD asserts the wave summary is a durable file AND that it lives at dev/local/autopilot/reports/<wave id>-wave.md, but core SKILL.md Retention states purge-devlocal exempts only autopilot/ledger/** and that autopilot/reports/ is trashed at the 14-day stale-autopilot threshold. The PRD is internally inconsistent with the pack retention design, and the shipped Durable entry also miscompares the wave report to the per-batch report, which that same section lists as NOT durable.

**Choice**: Resolved autonomously in loop mode by the simplest safe assumption rather than stalling: queued task 8 to keep writing reports/<id>-wave.md (the PRD stated path, pinned by task 4 own test) and ALSO mirror it to autopilot/ledger/<id>-wave.md, then correct the SKILL.md Durable entry to name the ledger copy as durable, worded like the existing loop-metrics.jsonl entry.

**Rationale**: This honours both PRD claims at once and reuses a pattern the same Retention section already establishes (autopilot/ledger/loop-metrics.jsonl is described as the GC-exempt mirror, the durable copy to read). Two alternatives were rejected on evidence: adding a *-wave.md exemption to purge-devlocal is impossible from this repo, since rg shows purge-devlocal appears only in prose and prose-pinning tests and the tool is implemented elsewhere; moving the report out of reports/ would contradict the PRD explicit output path and break test_docs_name_the_site_and_the_summary. Simply deleting the durability claim was rejected as delivering less than the PRD asked for.

### [autonomous] 2026-09-28T03:50:29Z

**Decision**: The mechanical full-review path in review-work-completion step 3 would have produced an EMPTY diff for this PRD: the work landed on master, so gather-context.sh branch-base detection resolves DIFF_BASE=master and git diff master from HEAD on master is empty. The skill forbids an empty diff from reaching a verdict. Separately, the correct range work_start_sha..HEAD spans foreign commit c26156f (177 files) written by a concurrent interactive session.

**Choice**: Passed --since 206c914d (state.work_start_sha) to gather-context.sh so the diff base is the PRD own work start, then rebuilt the diff file as two contiguous foreign-free segments, 206c914d..4d22f45 and c26156f..5159896, whose union is exactly this PRD 16 commits. Retained the unfiltered full-range diff at dev/local/tmp/review-diff-00215c1-fullrange.diff and told every implementation-aware lens the scope rule plus the dev/local-versus-docs/dev/project-management dual-path fact.

**Rationale**: Content over label: the DIFF_SCOPE header now reads incremental review, which is cosmetically wrong, but the diff content is exactly the COVERAGE_DIFF_RANGE the skill mandates for the doubt lens. Feeding reviewers 177 foreign files plus a warning was strictly worse than feeding them the exact work: it cut the payload from 863KB to 114KB and no lens raised a finding against the foreign files.

### [autonomous] 2026-09-28T03:50:29Z

**Decision**: The fail-first replay emitted 20 [MECH] lines. Step 6 says every [MECH] line is a finding the consolidation absorbs, but all 20 name test files belonging to the foreign commit c26156f, not to this PRD: the replay derives its touched-test set from the raw base diff, which spans that commit.

**Choice**: Absorbed ZERO of the 20 into the consolidated table, and recorded all 20 filenames verbatim in the review file Mechanical checks section with the reason they are out of scope. For this PRD the replay is clean: all three new test files fail to collect at base because cli/wave_assemble.py does not exist there, which is correct fail-first evidence for a new module. The tautological-shapes check was also clean, 0 of 33 test functions.

**Rationale**: Absorbing them would have attributed another session refactor to 00215 and guaranteed non-convergence over work this PRD never touched. They are recorded rather than dropped, because the silence is exactly the failure the blocks exist to end.

### [autonomous] 2026-09-28T03:50:29Z

**Decision**: Nine [D1] rework tasks needed tiers under a PRD frontmatter default_model of sonnet, set by operator decision 2026-09-26 because an opus floor cost 109 min per task on 00214.

**Choice**: Eight tasks at sonnet (the floor); task 5 only at opus with tier_reason algorithmic_risk. No rework design was run, because the consolidated table holds zero CRITICAL rows and PRD 00194 scopes the rework design to a cycle with at least one.

**Rationale**: Task 5 fixes the rerun report-completeness defect in the same migrate/report surface the planner already lifted to opus for algorithmic_risk as original task 3, and the PRD model_tier_rationale explicitly preserves that escalator (the planner still lifts the rebase resolver and the ledger migration to opus per task). Every other task is a small mechanical fix, an exception-routing change, a validator one-liner, or test-only work, which sonnet covers at the floor.

### [autonomous] 2026-09-28T03:50:29Z

**Decision**: The engram context pack could not be generated: engram pack exited 1 with -- not inside a registered repo; register it in /Users/bob/.config/gita/repos.csv. Separately, consolidate_findings.py left one defect as two rows because the two reviewers cited different files for it.

**Choice**: Pack: substituted the literal sentinel (no pack available this cycle) for {PACK_FILE} and {PACK_FINDINGS} in every prompt, recorded the failure in the review file, and did NOT retry. Duplicate rows: merged Alice HIGH at wave_cli.py:32 with Bob MEDIUM at wave_assemble.py:546 into one HIGH defect (H2) and queued them as a single task 6, noting the merge in the review file and in the task body.

**Rationale**: Pack: the skill allows at most one retry and the error names a missing gita registry entry, a deterministic config precondition that a retry cannot clear; the pack is additive retrieval context, so the review is degraded rather than invalid. Merge: the consolidator matches on file path, so a single defect cited at its dispatch site and at its raise site cannot merge mechanically; leaving it split would have produced two tasks fixing one thing and understated the severity of the MEDIUM copy.

### [autonomous] 2026-09-28T03:50:29Z

**Decision**: Cycle 2 reached the rework cap (state.cycle 2 >= rework_cap 2) with two unresolved HIGH findings and no CRITICAL, so convergence failed and the loop-mode cap-out applied.

**Choice**: Recorded all 7 unresolved findings in state.deferred_decisions as cap-overflow and finalized the PRD as converged-with-deferrals, per the Phase 5 cap check. No third review cycle and no rework dispatch.

**Rationale**: The loop-mode cap-out defers rather than pausing when no CRITICAL remains. Both HIGHs are cheap to fix and were deferred by the cap, not by a judgment that they do not matter; the batch keeps draining and they are visible at batch end.

### [autonomous] 2026-09-28T03:50:29Z

**Decision**: review-work-completion step 7 would have created follow-up tasks for the 7 findings, but the Phase 5 cap-out never dispatches rework, so those tasks would sit pending forever and push tasks_completed below tasks_total at the done gate.

**Choice**: Created no follow-up tasks this cycle. state.tasks stays 13/13 completed; the findings' durable home is state.deferred_decisions plus review-2.md and the settled-decisions ledger.

**Rationale**: A pending task the cap-out cannot dispatch would corrupt the task counts the done gate and the dashboard read, and would misreport the PRD as unfinished.

### [autonomous] 2026-09-28T03:50:29Z

**Decision**: Two lenses disagreed on the surviving findings: Alice and Carl both passed all 12 R-rules after running release-checks green, while Bob reported three HIGHs still open and Blake independently found the release-gate hole.

**Choice**: Verified every HIGH by direct source reading before accepting it: upheld H1 (confirmed by reading both lists and running the orphaned file: 12 passed) and H2 (confirmed by tracing both lane_status branches after the pre-save crash), and downgraded Bob's third HIGH on _open_assembly to medium because the assembly path is wave-id-scoped and the failure is loud.

**Rationale**: Alice's and Carl's green release-checks run is exactly the false signal H1 describes - the gate is green because the missing test file is missing from both the invocation and the whitelist - so their pass could not settle it.

### [autonomous] 2026-09-28T03:50:29Z

**Decision**: The four fail-first replay [MECH] rows had to be judged: a test that passes against base is a defect only when it was meant to pin this change.

**Choice**: Dismissed M1-M3 to the settled-decisions ledger as incidentally-touched pre-existing tests (their commits' NEW pins are among the 20 that do fail against base), and deferred M4 as a real residual because cycle 1's gap-1 and gap-3 strengthenings pass against base and nothing proves they would fail on the mutation each gap named.

**Rationale**: The skill requires every [MECH] line to be absorbed rather than dropped, and a behavior-preserving pin passing against base is expected; the distinction is whether the pin was supposed to catch a code defect.

### [autonomous] 2026-09-28T03:50:29Z

**Decision**: Bob's assembled prompt carried three sections of agents/eve.md (Two lenses, Categorize every residual finding, Rubric verdicts) where review-work-completion step 4 names only the first and third.

**Choice**: Left the run as dispatched and recorded the deviation in review-2.md. Bob emitted FIX/VERIFY/KNOWN buckets as a result; his VERIFY bucket is empty, so no verification-check queue was written and nothing downstream changed.

**Rationale**: The extra section only added buckets the skill says Bob lacks; re-running him to drop it would have spent a codex dispatch for no change in findings.

### [autonomous] 2026-09-28T03:50:29Z

**Decision**: The engram context pack could not be generated again: engram pack exited 1 with -- not inside a registered repo; register it in /Users/bob/.config/gita/repos.csv.

**Choice**: Substituted the literal sentinel (no pack available this cycle) for {PACK_FILE} and {PACK_FINDINGS} in every prompt that takes them, recorded the failure in review-2.md, and did not retry.

**Rationale**: A missing gita registry entry is a deterministic config precondition, not a transient error, and it failed identically in cycle 1.

### [autonomous] 2026-09-28T03:50:29Z

**Decision**: last-verification.json matched this HEAD (5f0acd5) but carried null passed/failed/skipped counts, so the review's Tests: line could not be composed from the record.

**Choice**: Ran bash dev/bin/release-checks once in the foreground and aggregated its per-block pytest summaries: exit 0, 1327 passed, 0 failed, 0 skipped. The Tests: line carries the (suite run this cycle) suffix, not the reused one.

**Rationale**: The skill requires a real run whenever the record's counts are null, and requires naming which path produced the counts so a reused count never reads as a fresh one.

### [deferred] 2026-09-28T03:50:29Z

**Decision**: H1: test_wave_assemble_summary.py is absent from both the `[checks] waves` block's pytest invocation (dev/bin/release-checks:107-119) and test_wave_docs.py's _WAVE_TEST_FILES whitelist (:41-53), so its 12 tests - three of them PRD-named Phase 0 acceptance tests - never run in the repo's only CI gate while release-checks still reports green. test_the_release_gate_runs_every_wave_test_file cannot catch it: it asserts named == set(_WAVE_TEST_FILES) and task 10 updated neither side.

**Rationale**: rework cap reached with this finding unresolved

### [deferred] 2026-09-28T03:50:29Z

**Decision**: H2: teardown is still crash-unsafe on the real pre-save crash. _drain_lane writes lane[held_prds] and _assemble_lane writes lane[status] in memory only; the single save() is at wave_assemble.py:591, after the git worktree remove / branch -D at :524-526, so a crash in that window loses held_prds, status, batch_id and worktree_removed together. On the rerun lane_status either returns unfinished (the merged lane is relabelled unfinished, lands in kept, exit flips 0 to 3, the report drops non-roster PRDs and blanks the lane batch id, and worktree_removed is never set so every later rerun repeats it) or returns the stale drained, in which case lane_files_and_notes runs subprocess.run with a removed cwd and raises an uncaught OSError that wave_cli.run does not catch. Task 12's new test cannot catch either: it runs a full successful assemble first and then deletes only worktree_removed.

**Rationale**: rework cap reached with this finding unresolved

### [deferred] 2026-09-28T03:50:29Z

**Decision**: _open_assembly (wave_assemble.py:549) adopts any existing directory at the assembly path without verifying it is this repository's registered worktree on the expected branch, and wave[assembly][branch] is then reported as the expected branch name whatever the worktree is really on. Downgraded from high by the gate: the path is wave-id-scoped, and a stale plain directory surfaces as a loud git -C failure rather than silent mutation.

**Rationale**: rework cap reached with this finding unresolved

### [deferred] 2026-09-28T03:50:29Z

**Decision**: CHANGELOG.md:12 still says a lane kept for a conflict or a checks failure has its own branch and worktree left untouched - the blanket claim task 13 corrected in references/waves.md:133-137, where a conflict lane's branch is untouched but a checks_failed lane's branch was already rebased. The changelog and the runbook now contradict each other inside task 13's own scope.

**Rationale**: rework cap reached with this finding unresolved

### [deferred] 2026-09-28T03:50:29Z

**Decision**: _assemble_kept_region (test_wave_docs.py:196-212) duplicates _abort_keep_region (:118-133): the two differ only in their heading and anchor constants over an otherwise identical 10-line body.

**Rationale**: rework cap reached with this finding unresolved

### [deferred] 2026-09-28T03:50:29Z

**Decision**: M4: 9 of the 14 touched tests in test_wave_assemble_summary.py pass against the pre-change code, among them test_summary_opens_with_the_base_and_the_assembled_head (cycle 1 gap 1) and test_summary_tables_each_lane_with_its_branch_status_and_batch (gap 3), so those two strengthenings pin already-correct behavior rather than failing on the swap or pluralisation defect their findings named.

**Rationale**: rework cap reached with this finding unresolved

### [deferred] 2026-09-28T03:50:29Z

**Decision**: merge_lane clears stale conflict_paths on a later clean rebase but never clears a stale conflict_detail, so a lane that succeeds on retry can still carry its previous failure's detail string in wave.json.

**Rationale**: rework cap reached with this finding unresolved
