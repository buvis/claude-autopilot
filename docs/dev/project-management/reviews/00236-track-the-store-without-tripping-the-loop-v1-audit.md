# Decision Audit Log: 00236-track-the-store-without-tripping-the-loop-v1

PRD: `00236-track-the-store-without-tripping-the-loop-v1.md`
Started: 2026-10-02T22:52:58Z
Completed: 2026-10-02T22:52:58Z
Autonomous: 13  |  Deferred: 19  |  Doubts: 0

### [autonomous] 2026-10-02T22:52:58Z

**Decision**: Phase 2 replan scope and the .git/info/exclude site

**Choice**: Planned the 8 remaining items only; deferred design site 10 (.git/info/exclude) to the operator; rewrote the PRD Repository Structure tree so its comma/glob lines list one path each.

**Rationale**: Original tasks 1-5 are committed and state.json had lost the task record. Site 10 is per-checkout and untestable, and flipping it under a loop running the installed 0.6.0 cache would surface the whole store as dirt to the old stand-down check - recorded in the batch deferred JSON instead. The four module dirs were already named in the PRD tree, but check-plan parses one entry per line and read the comma/glob lines as module drift.

### [autonomous] 2026-10-02T22:52:58Z

**Decision**: Cycle 1 review returned 4 unresolved HIGH findings and no CRITICAL

**Choice**: Queued 8 rework tasks (ids 9-16) and handed off to a fresh session per the loop-mode rework handoff. Cycle 1 of cap 2.

**Rationale**: No 🔴 row in the consolidated table, so no rework design doc is required and no cap-out branch applies. An unresolved HIGH blocks convergence, so the cycle reworks.

### [autonomous] 2026-10-02T22:52:58Z

**Decision**: consolidate_findings.py merged two pairs of genuinely distinct defects

**Choice**: Split the review-once recording gap out of the wave-lane row and the gitignore-write-swallow out of the dirty-fails-open row; merged the third bare-repo row into the matching one. The review file carries the corrected table and names each correction.

**Rationale**: The script warned on five suffix-stripped citation merges. Three were legitimate paraphrase merges; two folded different defects onto one wording, which would have lost a HIGH and a 2-of-4 MEDIUM.

### [autonomous] 2026-10-02T22:52:58Z

**Decision**: Reviewer asked for an operator decision on wave-lane store recording

**Choice**: Chose skip store recording inside wave lanes over defining lane store merge semantics; recorded in rework task 10 as a decision not to re-open.

**Rationale**: Skip is additive and non-destructive, introduces no new merge semantics, and cannot lose work: a lane store write stays in its worktree exactly as it does today. Defining merge semantics for ledger appends is a design change this cycle has no mandate for.

### [autonomous] 2026-10-02T22:52:58Z

**Decision**: Model tier for the rework batch

**Choice**: Tasks 9 and 10 at opus; tasks 11-16 at sonnet.

**Rationale**: No CRITICAL row, so the default_model opus floor does not apply and the classifier tier governs. Git work-tree and pathspec semantics (task 9) and lane routing plus wave assembly (task 10) are cross-cutting and data-loss adjacent; the remaining six are bounded single-site fixes where sonnet is measurably faster.

### [autonomous] 2026-10-02T22:52:58Z

**Decision**: state.work_start_sha does not mark the start of this PRD work

**Choice**: Reviewed the range 23bf974..5ab1a1f instead of the documented work_start_sha..HEAD.

**Rationale**: work_start_sha is 4f336ff, which sits two commits into this PRD own work (29f4d5a and 4f336ff are both its store_tree test commits). The documented range would have shown foreign_dirty and record_store implementation with their fail-first tests cut out of the diff, inviting a false no-tests finding. 23bf974 is the last commit before PRD 00236 started.

### [autonomous] 2026-10-02T22:52:58Z

**Decision**: engram context pack unavailable

**Choice**: Ran the cycle with no pack, substituting the documented sentinel for the pack path and the findings precedent in every implementation-aware prompt, and recorded the failure in the review file.

**Rationale**: engram pack exits 1 here with: not inside a registered repo, register it in the gita repos.csv. That is a deterministic configuration refusal, so a retry would fail identically. The pack is additive retrieval context, never a gate.

### [autonomous] 2026-10-02T22:52:58Z

**Decision**: Verification-check queue has no entries

**Choice**: Wrote an empty checks-1.json and recorded the single VERIFY item as not queued (command shape), deferring it to batch end.

**Rationale**: The doubt lens VERIFY names a post-release batch observation rather than one runnable command, which the queue rules exclude. Rubric D3 already requires a VERIFY item to name its exact check.

### [autonomous] 2026-10-02T22:52:58Z

**Decision**: Tests line composition

**Choice**: Composed the Tests line from docs/dev/project-management/autopilot/last-verification.json and ran no suite in this cycle, naming the reuse on the line itself.

**Rationale**: The record sha equals the reviewed HEAD 5ab1a1f and its three counts are non-null, which is the documented reuse condition. The diff touches code, so the docs-only sentinel does not apply.

### [autonomous] 2026-10-02T22:52:58Z

**Decision**: Two load-bearing HIGH findings needed confirming before they drove rework

**Choice**: Verified both by direct measurement rather than accepting the reviewer claims.

**Rationale**: loop.py shows _append_metrics at lines 487 and 583 but record_store only at 593, so the review-once path records nothing - confirmed. lane.is_production_path returns True for the store ledger jsonl and for the store gitignore and False for a PRD markdown file, so store commits inside the review range would escalate every solo lane - confirmed.

### [autonomous] 2026-10-02T22:52:58Z

**Decision**: Five mechanical fail-first replay findings

**Choice**: Appended mech-check as an extra finder on the five consolidated rows the doubt lens had already raised; created no additional rows.

**Rationale**: Every replay line named a test file the doubt lens already reported, so the documented absorption rule applies rather than the add-a-row branch. All five are queued in rework task 13.

### [autonomous] 2026-10-02T22:52:58Z

**Decision**: Two unresolved HIGH findings at the rework cap (lane_check nested-store exclusion; review-once missing the wave-lane guard)

**Choice**: cap-out: deferred to batch end, PRD finalized as converged-with-deferrals

**Rationale**: state.cycle 2 >= state.rework_cap 2 and no CRITICAL remained, so the loop-mode cap-out branch applies: 12 unresolved findings appended to deferred_decisions as cap-overflow records, no third review cycle, no rework dispatch, batch keeps draining. Both HIGHs were gate-verified against the code rather than taken on the reviewer word.

### [autonomous] 2026-10-02T22:52:58Z

**Decision**: Bob VERIFY item: run bash dev/bin/release-checks at revision 1daea55509ef17d8eb7703b905273b15d0bcaa9e and confirm exit 0

**Choice**: routed to verification and run by the gate; discarded as answered

**Rationale**: The command named one exact runnable check, so it was queued in 00236-track-the-store-without-tripping-the-loop-v1-checks-2.json. There is no work phase on the cap-out path, so the review gate ran it itself at that exact HEAD: exit 0. Recorded with result.exit 0 and in the ledger as discarded with the measurement, so the queue carries no unrun check.

### [deferred] 2026-10-02T22:52:58Z

**Decision**: PRD lists 18 gitignore patterns, STORE_GITIGNORE ships 23

**Choice**: deferred to batch end

**Rationale**: Requirements ambiguity already adjudicated in the design doc: the 23-pattern body is the union of the PRD draft list and the live Retention Disposable bullet, and the two sources disagreeing was the defect. The shipped superset is correct and the PRD sentence is the stale side; amending PRD prose is an operator doc change, not code rework.

### [deferred] 2026-10-02T22:52:58Z

**Decision**: PRD puts record-store between the brief and the leave row, the implementation puts it after the row, and the PRD-mandated test name reads backwards from what it asserts

**Choice**: deferred to batch end

**Rationale**: Design prose-site contract 2 already adjudicated this: committing before the leave row cannot satisfy the PRD own success metric, because the leave row itself appends to the tracked dispatch-metrics.jsonl. The test name is PRD-mandated verbatim, so renaming it would break a named acceptance criterion; its docstring and body both state the asserted order correctly.

### [deferred] 2026-10-02T22:52:58Z

**Decision**: Four porcelain gates stay unrewritten although the PRD says every gate is rewritten

**Choice**: deferred to batch end

**Rationale**: Settled by the design destructive-step rule, reached over three review dispatches: a step that discards uncommitted work (git reset --hard, worktree remove --force, abort discard) must never be gated on a predicate that calls store work invisible. rework-mode.md is a per-file check, not a whole-tree gate. The 10-entry allowlist is the auditable form of that decision.

### [deferred] 2026-10-02T22:52:58Z

**Decision**: skills/run-autopilot/cli/__main__.py is 1278 lines against the 800-line limit

**Choice**: deferred to batch end

**Rationale**: Confirmed by measurement. Pre-existing debt named in the design doc and in the PRD 00223 batch report; the doubt lens itself filed it as KNOWN and out of scope. Splitting the dispatcher is its own PRD, not store-tracking rework.

### [deferred] 2026-10-02T22:52:58Z

**Decision**: Out-of-PRD intake-tree change inside the review range

**Choice**: deferred to batch end

**Rationale**: Commits 9815f62 and 0fdfe71 are the operator-sanctioned fix for the tooling_conflict stall that forced this PRD replan - they are why the PRD could proceed at all. Already landed and green; unpicking them into a separate PRD now buys nothing. Their fail-first weakness is queued as rework task 13.

### [deferred] 2026-10-02T22:52:58Z

**Decision**: PRD says normalized repo-relative path comparison, the code uses a raw startswith, and the new verbs take a --state flag the PRD does not enumerate

**Choice**: deferred to batch end

**Rationale**: The reviewer concedes the behavior is correct for porcelain -z output, which is the only input the function takes, so this is a wording gap rather than a defect. --state matches every other verb in this CLI and is the established convention.

### [deferred] 2026-10-02T22:52:58Z

**Decision**: Doubt lens VERIFY on post-release tracked-store batch behavior, not queued

**Choice**: deferred to batch end

**Rationale**: Not queued: command shape. It names a post-release batch observation rather than one runnable command, it is the PRD own third Success Metric, and it is gated on the deferred operator step (design site 10). It cannot run in a work phase, so it is recorded to stay visible at batch end.

### [deferred] 2026-10-02T22:52:58Z

**Decision**: lane_check.diff_signal excludes the un-prefixed STORE_EXCLUDE_PATHSPECS with cwd=repo_root, so in a bare-repo-backed project (store at .claude/docs/dev/project-management under a $HOME work-tree) the exclusion misses the store, store commits read as production paths, and every solo-lane PRD escalates to the full lane. Task 10 fixed only the flat layout; the derived prefix task 9 threaded into foreign_dirty and record_store was never threaded into lane_check.

**Choice**: deferred to batch end

**Rationale**: rework cap reached with this finding unresolved. Gate-verified, not taken on the reviewer word: store_tree._store_prefix(/tmp/h, /tmp/h/.claude/docs/dev/project-management) returns .claude/ while STORE_EXCLUDE_PATHSPECS stays (:(exclude)docs/dev/project-management, :(exclude)docs/dev/tmp), and lane.is_production_path(.claude/docs/dev/project-management/autopilot/ledger/dispatch-metrics.jsonl) returns True. Recurring defect class (Protocol B): same bare-backed boundary assumption as the cycle-1 task-9 finding, resurfacing at a site task 10 did not cover.

### [deferred] 2026-10-02T22:52:58Z

**Decision**: Loop._record_review_once_store calls record_store with no in_wave_lane guard, while the per-session loop site (loop.py:611) and the drained exit (loop_act.py:218) both carry one. An autopilot review-once run inside a wave lane worktree therefore commits store files onto the lane branch, reopening the assembly ledger-conflict and double-migration problem task 10 was created to close.

**Choice**: deferred to batch end

**Rationale**: rework cap reached with this finding unresolved. Gate-verified by reading all three call sites: in_wave_lane appears at loop.py:611 and loop_act.py:218 and in the record-store CLI verb at __main__.py:1216, and is absent from _record_review_once_store. Exposure is narrow (an operator running review-once from inside a lane worktree; wave lanes themselves run autopilot loop), which is why it did not block the batch.

### [deferred] 2026-10-02T22:52:58Z

**Decision**: _record_review_once_store wraps the whole recorder in except Exception: pass, so any failure in store_git, repo_and_git_dir or an unexpected raise inside record_store is dropped with no output at all, leaving the review-once store writes uncommitted and untraceable. Every other site either reports on stderr or lets record_store print its own one-line reason.

**Choice**: deferred to batch end

**Rationale**: rework cap reached with this finding unresolved. Highest-consensus finding of the cycle (Alice, Bob and Blake all named it). Fix is one line: catch (OSError, subprocess.SubprocessError) and print one autopilot: review-once store record failed line, preserving the exit code.

### [deferred] 2026-10-02T22:52:58Z

**Decision**: in_wave_lane treats any non-empty _AUTOPILOT_REVIEW_SLOTS_DIR as proof of a wave lane, but that variable is the general review-concurrency semaphore: Loop._launch reads it for any loop and the CHANGELOG documents it as configuration. An operator who sets it on a plain loop to bound review concurrency silently disables every record-store call (loop site, drained exit and CLI verb), so the tracked store never gets committed, which is the exact failure mode this PRD exists to prevent. wave_review.review already strips the variable for the assembly loop, which shows it is not a clean lane marker.

**Choice**: deferred to batch end

**Rationale**: rework cap reached with this finding unresolved. Gate-verified: wave_launch.py:188 is the only product writer of the variable today, so no current code path misfires, but the documented operator configuration reaches it. Task 10 asked for the wave control file or lane marker the launch path writes, not a new signal.

### [deferred] 2026-10-02T22:52:58Z

**Decision**: Task 13 was marked completed with three of its quoted findings undelivered. test_wave_assemble.py and test_wave_launch_refusals.py were never touched this cycle, so the seven assembly and six launch refusal replay survivors still pin nothing; test_wave_review.py was touched but this cycle fail-first replay still reports five of its cases passing against the pre-change code; and hooks/test_enforce_prd_location.py was touched but its three intake layout tests still pass at base.

**Choice**: deferred to batch end

**Rationale**: rework cap reached with this finding unresolved. Gate-verified: git diff --name-only 5ab1a1f..HEAD lists neither test_wave_assemble.py nor test_wave_launch_refusals.py, and the cycle-2 replay block independently reports the wave_review and intake survivors. A task reported complete with named findings unaddressed is the finding here, not just the weak tests.

### [deferred] 2026-10-02T22:52:58Z

**Decision**: autopilot dirty now returns exit 13 on a failed git probe, an exit code the PRD never defined (it specifies 0 and 1 only), while the prose gates still read comes back empty or prints at least one path. A failed probe prints nothing on stdout, so a session following that wording reads a crashed check as a clean tree: a fail-open path. work/SKILL.md step 5 names autopilot dirty as the check the rule means but, unlike the task-boundary and fast-track sites, never gives the invocation.

**Choice**: deferred to batch end

**Rationale**: rework cap reached with this finding unresolved. Blake raised the fail-open reading and Alice the missing invocation; one clause at each gate site (a non-0 non-1 exit is a failed probe, not a clean tree) closes both. Task 12 added the distinct exit code but did not reword the readers.

### [deferred] 2026-10-02T22:52:58Z

**Decision**: test_store_tree_legibility.py re-defines FakeGit, _subcommand, _one_line, _autopilot_dir, _write_state, SUBCOMMANDS and REPO, every one of which already lives in the shared store_tree_testutil.py that four sibling modules import, with byte-identical FakeGit bodies. Redundancy introduced by this diff. test_store_boundary.py also keeps a second, differently shaped FakeGit under the same name.

**Choice**: deferred to batch end

**Rationale**: rework cap reached with this finding unresolved. Alice and Bob both named it; the fix is an import swap in one test module and costs no behavior.

### [deferred] 2026-10-02T22:52:58Z

**Decision**: The new task-boundary ordering pin asserts the leave row comes before record-store but never asserts record-store comes before the final STOP, so half the required ordering is untested; the cycle-2 fail-first replay also reports this test passing against the pre-change code. Bob asks for leave-row index < record-store index < STOP index.

**Choice**: deferred to batch end

**Rationale**: rework cap reached with this finding unresolved. Corroborated mechanically: the replay block lists test_task_boundary_handoff_records_the_store_before_the_leave_row among the tests that pass at base.

### [deferred] 2026-10-02T22:52:58Z

**Decision**: test_solo_repo_commits_despite_host_signing_config asserts git configuration and the test fixture rather than product behavior, and the cycle-2 replay confirms it passes against the pre-change code. Bob asks for its removal while keeping the fixture signing override.

**Choice**: deferred to batch end

**Rationale**: rework cap reached with this finding unresolved. Corroborated mechanically by the replay block, which lists it first among the seven test_lane_cli.py tests that pass at base.

### [deferred] 2026-10-02T22:52:58Z

**Decision**: The PRD first Success Metric and its Phase 0 and Phase 1 acceptance criteria all name skills/run-autopilot/cli/test_store_tree.py, and the cycle-1 rework deleted that file when the style gate split it into test_store_tree_foreign_dirty.py, _record_store.py, _cli.py, _custody.py, _gitignore.py and _legibility.py. Every named test still exists in a split file and dev/bin/release-checks lists them all, but the PRD literal metric command now fails with file not found.

**Choice**: deferred to batch end

**Rationale**: rework cap reached with this finding unresolved. Documentation drift, not a code defect: the implementation and the release gate are both correct and green, the PRD text is the stale side. Operator doc fix, same class as the other PRD-text deferrals in this PRD ledger.

### [deferred] 2026-10-02T22:52:58Z

**Decision**: The three wave modules call foreign_dirty(repo, run_git=run_git) without store_dir, so the derived store prefix is empty there. In a bare-repo-backed project the store paths would read as foreign and the wave refusals would fire on store churn alone. Same un-threaded-prefix class as the confirmed lane_check HIGH of this cycle.

**Choice**: deferred to batch end

**Rationale**: rework cap reached with this finding unresolved. Grouped with the lane_check HIGH: one fix that threads the derived store prefix through every foreign_dirty and exclusion caller closes both.

### [deferred] 2026-10-02T22:52:58Z

**Decision**: Three test modules carry docstrings that still point at the deleted test_store_tree.py: test_store_boundary.py and test_store_lane.py say they are a new file rather than an addition to test_store_tree.py, which is at its size ceiling, and test_store_gitignore.py says it was split out of test_store_tree.py, which holds the rest. Alongside it, the new test_task_boundary_handoff_records_the_store_before_the_leave_row copies the misleading cycle-1 name while its body asserts the opposite order, and test_store_gitignore_is_a_literal_not_a_join_call pins a source-text spelling rather than behavior and prints the whole file as its assert message.

**Choice**: deferred to batch end

**Rationale**: rework cap reached with these findings unresolved. Three cosmetic cleanups grouped into one record: stale docstrings, one misleading test name that is NOT PRD-mandated (unlike its cycle-1 namesake, so renaming it breaks no acceptance criterion), and one source-text pin the byte-exact tests beside it already cover.
