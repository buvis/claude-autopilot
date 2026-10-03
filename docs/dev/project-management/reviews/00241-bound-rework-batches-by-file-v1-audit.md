# Decision Audit Log: 00241-bound-rework-batches-by-file-v1

PRD: `00241-bound-rework-batches-by-file-v1.md`
Started: 2026-10-03T17:32:37Z
Completed: 2026-10-03T17:32:37Z
Autonomous: 15  |  Deferred: 21  |  Doubts: 0

### [autonomous] 2026-10-03T17:32:37Z

**Decision**: Bob (codex) failed twice with exit 1 (codex-event: error, turn.failed), publishing no output and no sidecar

**Choice**: dispatched Bob's Claude fallback on his exact assembled prompt

**Rationale**: Phase 5 Safety Checks: a transient reviewer error is logged and the cycle continues on the reviewers that succeeded. The doubt lens must never silently drop, so the fallback ran the same doubt+de-slop prompt and the D1-D5 rubric; its output is Bob's for this cycle. codex-run.sh returns codex's real exit code and writes no sidecar, so there was nothing to salvage. Both CLI dispatch rows are closed as error (exit 1, retry: exit 1).

### [autonomous] 2026-10-03T17:32:37Z

**Decision**: gather-context.sh with no --since produced a 2-file, 18-line diff: its master base resolves to HEAD because this PRD's work is committed directly on master

**Choice**: re-ran gather-context.sh --since bf07e177401aa1c4e6a9bca377a8cc500d737ca3 (state.work_start_sha)

**Rationale**: A review of an effectively empty diff would have converged over the whole PRD. The skill's own full-review rule prefers work_start_sha..HEAD under autopilot; passing it as --since produced the real 19-file, 897-line range. Recorded because the no---since path is the documented default and is wrong for a repo that commits on master.

### [autonomous] 2026-10-03T17:32:37Z

**Decision**: The engram context pack could not be built: engram pack exits 1 with 'not inside a registered repo; register it in /Users/bob/.config/gita/repos.csv'

**Choice**: ran the cycle degraded with the sentinel (no pack available this cycle)

**Rationale**: The failure is deterministic, not transient, so no retry was burned. The skill states a review without the pack is degraded, not invalid; Blake never receives one by design. Alice, Bob and Carl got the sentinel in place of {PACK_FILE} and {PACK_FINDINGS}.

### [autonomous] 2026-10-03T17:32:37Z

**Decision**: 25 auto-fix findings would have produced far more than the 10 follow-up tasks the Phase 5 scope alarm allows if split by hand

**Choice**: bounded the rework batch with the repo build of autopilot group-rework, yielding exactly 4 [D1] tasks

**Rationale**: This is the feature under review, so using it is also its first end-to-end exercise on real data. The installed cache (v0.7.0) has no group-rework subcommand, which confirms the release gap; the repo build grouped 25 findings across 7 file keys into skills/run-autopilot/cli/ (19), prose (2), docs/dev/project-management/.gitignore (1) and dev/bin/release-checks (3), ordered correctly by severity then count then key.

### [autonomous] 2026-10-03T17:32:37Z

**Decision**: Observation from that run: the cap allocates slots by key count, not by load, so one task carries 19 findings beside three carrying 1-3

**Choice**: accepted the grouping unchanged; left splitting to /autopilot:work's own task-splitting and prompt-budget rules

**Rationale**: The PRD's Risks section accepts this explicitly ('A merged task grows too large for one implementor: /autopilot:work's existing task-splitting and prompt-budget rules still apply per task'). Overriding the grouping by hand would hide the feature's real behavior in the one cycle that measured it.

### [autonomous] 2026-10-03T17:32:37Z

**Decision**: Requirements ambiguity: the PRD input grammar allows only '<path>[:<line>]' or 'general', but the real consolidated table and the reviewer output format emit 'N/A' for cross-cutting findings

**Choice**: resolved by the simplest safe assumption: normalize N/A (and the 'N/A (path:line)' form) onto the general key in file_key

**Rationale**: The PRD's general-merge rule is plainly meant to fire on findings that name no file; with the grammar as written it never fires in production and N/A instead burns one of the four cap slots as a junk key whose directory component is 'N'. Normalizing makes the PRD's own rule 5 effective rather than changing it. Queued in the skills/run-autopilot/cli/ [D1] task.

### [autonomous] 2026-10-03T17:32:37Z

**Decision**: The Tail sweep's PRD-mandated Split rule sentence contradicts step 2's 'Build ONE [D{cycle}] task' and omits both the mandatory 'Tail sweep' name prefix PRD 00196's resume rule reads and the --findings path the command requires

**Choice**: resolved additively: keep the PRD's sentence verbatim and add the missing naming and findings-file clauses around it

**Rationale**: The sentence is pinned by this PRD's own new prose test, so reverting it would fail test_rework_groups_prose.py; the regression is what the sentence leaves unsaid, not what it says. Adding the clauses closes the resume-rule break (pinned at test_review_resume_prose.py:55) and the small-sweep task-count inflation without contradicting the PRD. Queued in the prose [D1] task.

### [autonomous] 2026-10-03T17:32:37Z

**Decision**: Critical groups are emitted in input order, while PRD rule 6 read as one sort would tie-break them by key

**Choice**: kept input order and queued documenting it as an assumption plus a code comment

**Rationale**: Rule 6's 'then by' clauses describe the non-critical ordering; 'critical groups first' says nothing about their internal order, and test_critical_findings_stay_separate_and_uncapped already pins input order deliberately. The defect is the undocumented interpretation, not the behavior. Queued in the skills/run-autopilot/cli/ [D1] task.

### [autonomous] 2026-10-03T17:32:37Z

**Decision**: Bob's single VERIFY item names three commands, and the queue contract allows exactly one command per entry

**Choice**: queued the two project test commands as two entries; did not queue 'git check-ignore -q ...' (not queued: command shape) and ran it this cycle instead

**Rationale**: The queue admits tests, lints, builds, type-checks and project-defined checks; a git query is none of those, so writing it would break the writer/runner shape rule. It was run here as review evidence: exit 1, confirming nested store lock files are not ignored, which is the [3/4] HIGH. The other two were also run this cycle (18 passed; release-checks exit 0).

### [autonomous] 2026-10-03T17:32:37Z

**Decision**: The fail-first replay flagged test_critical_d_task_carries_design_then_contract_then_findings as passing against the pre-change code

**Choice**: absorbed the [MECH] line into Alice's existing row for the same file and test rather than adding a 28th row

**Rationale**: Step 6's first branch applies: a consolidated row already names that file and that test's assertion. Alice judged the flag expected, because the base lacks the new Group-first bullet that the f2d82e3 fix scoped around, so the test change is behavior-preserving by construction. mech-check is appended to that row's finders and the judgment is recorded in the review file rather than left silent.

### [autonomous] 2026-10-03T17:32:37Z

**Decision**: Tiering the four [D1] rework tasks with no CRITICAL row present, so the default_model floor does not apply

**Choice**: skills/run-autopilot/cli/ at opus; prose, .gitignore and release-checks at sonnet

**Rationale**: Phase 6 applies the default_model floor only to a task carrying a CRITICAL line; this cycle has none, so each task keeps its classifier tier. The cli group is 19 findings of algorithmic change across four files (input validation, file_key normalization, citation-suffix widening, cap-test strengthening), which the plan-tasks classifier reads as algorithmic risk. The other three are one-to-three-line mechanical edits.

### [autonomous] 2026-10-03T17:32:37Z

**Decision**: Bob's assembled prompt gained the FIX/VERIFY/KNOWN bucket instruction, which the skill's Bob assembly table does not list (it names only eve.md's 'Two lenses' and 'Rubric verdicts' sections)

**Choice**: kept the buckets and recorded the addition here and in the review file

**Rationale**: Bob is the doubt lane this cycle (doubt_reviewer: codex, Eve not activated) and was mandated to answer D1-D5, every one of which is a statement about the FIX/VERIFY/KNOWN buckets. Without them D1, D2, D3, D4 and D5 are unanswerable and would all have to be failed. Flagged rather than left implicit, since it is a deviation from the assembly table.

### [autonomous] 2026-10-03T17:32:37Z

**Decision**: Bob raised Cannot statically verify: success metrics 1-2 (both pytest suites and bash dev/bin/release-checks green) at this HEAD, since the recorded exit 0 in checks-1.json is from cycle 1 HEAD before tasks 4-7.

**Choice**: resolved by evidence, no task and no deferral

**Rationale**: Both commands were run at this HEAD during cycle 2. bash dev/bin/release-checks exited 0 with 2082 pytest passes and 116 shell-harness checks across four SUMMARY blocks, 0 failed. Blake independently reported EXIT=0, and Blake and Alice ran the named pytest selection green (48 and 64 passes). Also queued in checks-2.json so the record survives.

### [autonomous] 2026-10-03T17:32:37Z

**Decision**: Fail-first replay MECH row: 1 touched test passes against the pre-change code, test_critical_d_task_carries_design_then_contract_then_findings in skills/run-autopilot/cli/test_design_rework_prose.py.

**Choice**: discarded

**Rationale**: Behavior-preserving by construction, the same call cycle 1 made. The f2d82e3 fix scoped this test ordering assertion around the new Group first bullet, which does not exist at the base commit, so the test cannot fail there and that is correct rather than a gap. Ledgered this cycle so a third cycle auto-dismisses it.

### [autonomous] 2026-10-03T17:32:37Z

**Decision**: Cycle 2 reached the rework cap (cycle 2 of rework_cap 2) with two unresolved HIGH findings and no CRITICAL.

**Choice**: cap-out: deferred 17 findings to batch end, created no follow-up tasks, handed off to finalize as converged-with-deferrals

**Rationale**: Loop mode cap-out defers rather than pausing, and only a CRITICAL triggers the custody stall. Creating [D2] tasks after the cap fired would leave orphaned pending tasks blocking the same finalize this gate hands off to, so autopilot group-rework was not invoked. Both HIGHs are partial fixes of cycle 1 findings whose remaining halves are contract decisions the PRD never states, not capability failures.

### [deferred] 2026-10-03T17:32:37Z

**Decision**: The store .gitignore recursive lock pattern will be reverted again by ensure-store on every build gate until a release carrying PRD 00240 reaches the installed plugin cache

**Choice**: deferred to batch end (release-gated)

**Rationale**: The batch runs the installed cache v0.7.0, whose cli/store_tree.STORE_GITIGNORE predates PRD 00240. The cycle-1 rework fix restores docs/dev/project-management/.gitignore:3 and untracks the four deferred/*.json.lock files, but only a release carrying 00240 stops ensure-store rewriting it back. Found by alice, bob, carl [3/4].

### [deferred] 2026-10-03T17:32:37Z

**Decision**: _RANK in rework_groups.py re-declares consolidate_findings.SEVERITY_ORDER with different numbers and an implicit unknown rank; one severity table, two copies free to drift

**Choice**: deferred to batch end

**Rationale**: De-duplicating needs an import across the review-work-completion/scripts to run-autopilot/cli skill boundary, coupling PRD 00241 never sanctioned and that release-checks runs as separate blocks. Bob raised it and filed it in his own KNOWN bucket with this reason. Found by bob [1/4].

### [deferred] 2026-10-03T17:32:37Z

**Decision**: Stale neighbouring prose: the Phase 5 scope-alarm row and the Phase 6 becomes-or-joins sentence still assume hand-chosen task counts now that grouping caps non-CRITICAL tasks at 4

**Choice**: deferred to batch end

**Rationale**: Blake classified it himself as drift rather than a defect, and both sentences sit outside PRD 00241's explicit edit list (which names only the Phase 6 Group-first bullet and the Tail sweep Split rule). Rewriting unrelated gate prose inside a review cycle is scope creep. Found by blake [1/4].

### [deferred] 2026-10-03T17:32:37Z

**Decision**: __main__.py is 1315 lines, over the 800-line limit, and this diff adds 23 more

**Choice**: deferred to batch end

**Rationale**: Pre-existing breach already settled as a deferral in the 00223 review, and PRD 00241's own Repository Structure section directs the group-rework subparser into this file. Splitting the module is its own PRD. Found by alice [1/4].

### [deferred] 2026-10-03T17:32:37Z

**Decision**: Tail sweep step 2 still reads Build ONE [D{cycle}] task and the intro still reads one normal /autopilot:work task, both contradicting the Split rules one-task-per-group. The old >10 findings gate stays gone, so a 3-finding sweep over 3 files still yields 3 tasks. Partial fix of cycle 1 [3/4] Tail sweep HIGH.

**Rationale**: rework cap reached with this finding unresolved

### [deferred] 2026-10-03T17:32:37Z

**Decision**: _LINE_SUFFIX still misses three citation shapes the canonical consolidate_findings._TRAILING_LINENO_RE strips -- (line 3), (lines 18-22, 423) and #L12-L20 -- so each still becomes its own junk key and burns a cap slot. Unresolved remainder of cycle 1 file_key HIGH.

**Rationale**: rework cap reached with this finding unresolved

### [deferred] 2026-10-03T17:32:37Z

**Decision**: file_key discards the cited file for N/A (path:77), mapping it to general where the canonical _NA_PARENS_RE unwraps it to the path, so a finding naming a real file is routed away from that files group.

**Rationale**: rework cap reached with this finding unresolved

### [deferred] 2026-10-03T17:32:37Z

**Decision**: file_key goes beyond the spec key rule: it also strips the (lines a-b) and #Ln shapes and maps N/A and N/A (...) to general, where the spec lists only general and <path>[:<line>]. A harmless superset, but unrequested.

**Rationale**: rework cap reached with this finding unresolved

### [deferred] 2026-10-03T17:32:37Z

**Decision**: The Tail sweep Split rule is not the exact sentence the spec gave. The implementation appends five sentences (findings JSON path, naming rule, one-task floor, max-2-parallel). Sensible but unrequested.

**Rationale**: rework cap reached with this finding unresolved

### [deferred] 2026-10-03T17:32:37Z

**Decision**: The CHANGELOG entry adds three clauses beyond the single spec line about capping at 4 non-CRITICAL tasks grouped by file: suffix shapes, N/A handling and the exit-2 message.

**Rationale**: rework cap reached with this finding unresolved

### [deferred] 2026-10-03T17:32:37Z

**Decision**: The prose test asserts the literal word floor is in the paragraph rather than asserting the rule, so any sentence containing floor satisfies it -- and the clause it guards is itself vacuous.

**Rationale**: rework cap reached with this finding unresolved

### [deferred] 2026-10-03T17:32:37Z

**Decision**: Task 5 release-checks wiring ships with no regression test, though the sibling suite pins its own wiring the same way (test_design_rework_prose.py::test_release_checks_runs_both_design_contract_suites). Deleting the new line leaves everything green.

**Rationale**: rework cap reached with this finding unresolved

### [deferred] 2026-10-03T17:32:37Z

**Decision**: The new prose test copies about 15 lines of landmark lookup and paragraph bounding verbatim from test_tail_sweep_split_rule_uses_the_command. The duplicated block should be one _split_rule_paragraph() helper.

**Rationale**: rework cap reached with this finding unresolved

### [deferred] 2026-10-03T17:32:37Z

**Decision**: The guard that breaks out of _cap when no code group remains is unreachable through the public API and untested. A cap of 0 with prose-only input would drive it, and the guard exits with the group count still above the cap.

**Rationale**: rework cap reached with this finding unresolved

### [deferred] 2026-10-03T17:32:37Z

**Decision**: Two weaker pieces remain: _LINE_SUFFIX is still narrower than the canonical regex (misses (line 3), (lines 3, 5) and #L12-L14), and the comment at test_design_rework_prose.py:379 still says the Findings-verbatim mention lands first while the assertion below orders only the two bullet leads.

**Rationale**: rework cap reached with this finding unresolved

### [deferred] 2026-10-03T17:32:37Z

**Decision**: The spec names test_the_00223_cycle_one_set_yields_at_most_four_non_critical_tasks. The implemented test is test_the_00223_cycle_one_set_yields_four_non_critical_tasks: different name, stricter assertion (exactly 4).

**Rationale**: rework cap reached with this finding unresolved

### [deferred] 2026-10-03T17:32:37Z

**Decision**: Beyond the spec test for malformed input, the CLI also rejects elements lacking a string severity or file and adds test_cli_malformed_element_exits_two. The spec required only exit 2 on unreadable or malformed input.

**Rationale**: rework cap reached with this finding unresolved

### [deferred] 2026-10-03T17:32:37Z

**Decision**: The last clause of spec rule 5 (merge prose into the single remaining group) is unreachable at cap 4. The code documents this and keeps a guarded branch.

**Rationale**: rework cap reached with this finding unresolved

### [deferred] 2026-10-03T17:32:37Z

**Decision**: Neither _is_finding nor file_key rejects an empty file value, so a finding with file set to the empty string yields a group -- and a [D] task -- with an empty name.

**Rationale**: rework cap reached with this finding unresolved

### [deferred] 2026-10-03T17:32:37Z

**Decision**: The new cannot-read versus cannot-parse message split has no test that pins either wording: every malformed-input case asserts only exit 2, empty stdout and one stderr line, so collapsing the two clauses back into one stays green.

**Rationale**: rework cap reached with this finding unresolved

### [deferred] 2026-10-03T17:32:37Z

**Decision**: Review-tooling defect, not PRD 00241 code: replay_tests_against_base.py reads a unittest subTest parent as PASSED while its subtests report SUBFAILED, so the fail-first replay under-reports coverage and names tests that do pin new behavior. Alice, Bob and Carl each confirmed it independently this cycle. Needs its own PRD.

**Rationale**: rework cap reached with this finding unresolved
