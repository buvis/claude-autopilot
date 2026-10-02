# Decision Audit Log: 00233-run-the-test-suites-in-parallel-v1

PRD: `00233-run-the-test-suites-in-parallel-v1.md`
Started: 2026-10-01T04:47:39Z
Completed: 2026-10-01T04:47:39Z
Autonomous: 13  |  Deferred: 0  |  Doubts: 0

### [autonomous] 2026-10-01T04:47:39Z

**Decision**: Root cause of wave-test parallel failures unknown; needed diagnosis before any fix (default_model: opus).

**Choice**: Diagnosed root cause via reproduction: host global commit.gpgsign=true leaks into wave-test throwaway repos (test_wave_launch.py::_repo), so concurrent pytest-xdist commits contend on the shared gpg-agent (confirmed: CalledProcessError 128, gpg signing failed under load, clean under -n auto with signing simulated off). Designed fix: one git config commit.gpgsign false line in _repo(), plus a new test_parallel_safety.py regression guard wired into release-checks waves block.

**Rationale**: Smallest-diff fix at the single shared fixture import point (11 files reuse _repo); rejected HOME-redirect (wider blast radius) and xdist_group serialization (resource is per-repo config, not genuinely global) as alternatives. 3 reviewer dispatches (claude, codex, codex-verify) found and fixed 2 blockers: the draft regression test disabled signing in its own helper (would not catch a _repo regression) and was never wired into release-checks; both fixed by routing the test through the real _repo() fixture and adding it to the waves block.

### [autonomous] 2026-10-01T04:47:39Z

**Decision**: PRD 00233 Phase 2 and task 3 specify -n auto for the four parallelized release-checks blocks, but -n auto resolves to 18 workers on this host and reproducibly hit fork-level resource exhaustion (BlockingIOError: Resource temporarily unavailable) on the waves and custody core blocks under real load, independent of test_parallel_safety.py.

**Choice**: Used -n 4 instead of -n auto in the custody core, l3, reporting and waves blocks of dev/bin/release-checks (task 3, build phase).

**Rationale**: -n 4 is green end to end on this host while -n auto is not, and the PRD intent (parallel blocks, roughly halved wall clock) is met. Consequence to flag at review: the PRD Phase 2 acceptance check counting -n auto occurrences in dev/bin/release-checks now returns 0 instead of at least 1.

### [autonomous] 2026-10-01T04:47:39Z

**Decision**: Task 3 asks for the [checks] enter block to be parallelized, but a pre-existing prose pin (skills/run-autopilot/cli/test_enter_prose.py) pins that block exact invocation text, so parallelizing it would require editing the pin.

**Choice**: Left the [checks] enter block serial and unchanged (task 3, build phase).

**Rationale**: The block runs in about 2 seconds serially, so the pin edit buys no measurable wall-clock gain and widens the diff into a test file the task explicitly scopes out.

### [autonomous] 2026-10-01T04:47:39Z

**Decision**: Task 3 asks for skills/run-autopilot/cli/test_parallel_safety.py to be added to the [checks] waves block file list, but a pre-existing prose pin (skills/run-autopilot/cli/test_wave_docs.py) asserts that block file list equals an exact closed set.

**Choice**: Gave test_parallel_safety.py its own [checks] parallel safety block in dev/bin/release-checks (serial, pytest-xdist installed so its internal -n 2 subprocess can run) instead of adding it to the waves block (task 3, build phase).

**Rationale**: The regression test still runs in the gate, which is the requirement, without editing a closed-set pin the task scopes out.

### [autonomous] 2026-10-01T04:47:39Z

**Decision**: Cycle 1 raised 3 unresolved HIGH findings (xdist hard-requirement turning the project serial suite red, the -n 4 versus -n auto acceptance gap, and final-verification.md prose claiming the gate proves -n auto) plus 3 actionable Mediums. None is CRITICAL, so no rework design was required.

**Choice**: Classified all of them as auto-fix (additive or mechanical; no new dependency, no data-model change, no public API change) and created 3 sonnet-tier [D1] rework tasks: id 4 (make the parallel-safety guard xdist-safe and deterministic), id 5 (restore the -n auto contract in release-checks and its prose, plus the missing serial comments and a pin for the new block), id 6 (isolate test_lane_cli git commits from the host signing config). Queued as rework_task_ids [4,5,6].

**Rationale**: Each fix has a named shape the reviewers verified by running it, so none needs research. Tier is sonnet per the Phase 6 rule that the default_model opus floor applies only to tasks carrying a CRITICAL line; these are pinned regressions, and measured rework at opus ran 71-118 min against 10-33 min at sonnet. Findings were transcribed verbatim from each reviewer section rather than from the consolidated table, because consolidate_findings.py over-merged distinct defects that share a file.

### [autonomous] 2026-10-01T04:47:39Z

**Decision**: The computed fail-first replay block reported that all 3 touched tests pass against the pre-change code, which would normally mean the new tests do not pin the change.

**Choice**: Discarded the replay finding with a verified reason, and recorded the discard in the per-PRD ledger. Kept it visible as a table row rather than deleting it.

**Rationale**: Read replay_tests_against_base.py and confirmed at line 155 that the replay overlays every changed TEST file from HEAD onto the base worktree. This PRD entire production fix is one line inside test_wave_launch.py, which is itself a test file, so the overlay restored the fix and the replay compared HEAD against HEAD. It could not have reported a failure for this diff shape. The genuinely real sibling concern, that the guard is probabilistic and host-dependent, was NOT discarded: it is an actionable finding in rework task 4.

### [autonomous] 2026-10-01T04:47:39Z

**Decision**: Bob emitted two Cannot statically verify lines (whether the converted blocks finish under half their serial time, and whether the tests pass), each naming an exact runtime check he could not run inside the codex sandbox.

**Choice**: Resolved both in-cycle by measurement instead of queueing or deferring them, and recorded both as discards in the per-PRD ledger. No verification-check queue file was written for this cycle.

**Rationale**: The under-half question was answered like-for-like by Alice (identical waves file list: 350 passed in 165.89s serial against 79.14s at four workers, 47.7 percent) and corroborated by Blake (78s against 160s). The tests-pass question was answered by the orchestrator running the documented full suite, which was mandatory anyway because last-verification.json carried the right sha but null counts: 1 failed, 4199 passed, 1 skipped, 3 pre-existing rich collection errors, and the single failure is already the cycle HIGH. No queue file was written because the queue is fed from a doubt lens FIX/VERIFY/KNOWN bucket; Eve was not active and Bob assembled prompt carries no bucket section, and output-formats.md reserves source bob, so inventing buckets he did not emit was declined.

### [autonomous] 2026-10-01T04:47:39Z

**Decision**: gather-context.sh full-review path would have handed every cycle-1 reviewer an EMPTY diff: it resolves its diff base to the detected branch (master) and this repo works directly on master, so git diff master at a clean HEAD is empty. An empty diff must never reach a reviewer, and the review skill says an empty diff STOPS the review.

**Choice**: Passed the base explicitly as --since <work_start_sha>, which yields exactly the work_start_sha..HEAD range the review gate specifies, then hand-corrected the context file scope label from incremental review to FULL review so no reviewer was told this was a rework slice. Verified the resulting diff is 187 lines across the 3 expected commits. Deferred the underlying tool defect to batch end for its own PRD.

**Rationale**: The alternative was a review of nothing that could have reached Verdict: converged. The workaround changes only which base sha is diffed, not the scope: work_start_sha..HEAD is the exact range the gate mandates for a full review under autopilot. Recorded loudly because the next full review in a master-only repo hits the same trap silently.

### [autonomous] 2026-10-01T04:47:39Z

**Decision**: [BLAKE] HIGH: the PRD literal success metric (-n auto over skills/run-autopilot/cli green three times in a row) is not reliably met on this host; one of two runs failed with about 15 wave-family failures and a fork-exhaustion signature.

**Choice**: discarded - contradicted by measurement

**Rationale**: Cycle 2: Blake red run happened while Alice and Carl were each driving full suites on the same 18-core host, and carried a resource-exhaustion signature (BlockingIOError Errno 35 at fork, SIGKILLed git children). With the host idle after every reviewer finished, the orchestrator ran bare -n auto over that directory three consecutive times: 1952 passed each, 77.86s / 77.83s / 78.04s, 0 failed. Success Metric 1 is met 3/3. The residual near-the-fork-limit risk is carried as a low and is exactly what the shipped --maxprocesses 4 cap mitigates.

### [autonomous] 2026-10-01T04:47:39Z

**Decision**: [BLAKE] HIGH: Phase 1 acceptance requires -n auto green on three consecutive runs, and no three-run record exists for the shipped capped invocation; the design doc 3x-green evidence is a simulated uncapped run.

**Choice**: discarded - evidence gap closed by running it this cycle

**Rationale**: Cycle 2: the orchestrator ran the shipped capped form three consecutive times with the host idle: 1952 passed each, 153.96s / 91.18s / 92.28s, 0 failed (run 1 cold-cache, runs 2-3 settle near 92s). Against Alice measured 221s serial for the same directory that is 41.6% of serial, so the under-half metric holds on the whole directory and not only on the dominant waves block. Counts recorded in the cycle-2 review file. The separate complaint that the DESIGN DOC lacks these numbers survives as its own medium and is swept.

### [autonomous] 2026-10-01T04:47:39Z

**Decision**: [MECH] two fail-first replay lines: 3 touched tests in test_parallel_safety.py and 2 in test_release_checks_parallel_prose.py pass against the pre-change code.

**Choice**: discarded - computed against the wrong baseline for the question

**Rationale**: Cycle 2 is an INCREMENTAL review whose replay base is c502c2f, the end of the cycle-1 build. The production fix those tests pin (the commit.gpgsign false line in test_wave_launch.py::_repo) landed at d9868f8, BEFORE that base, and test_wave_launch.py is not in this cycle changed-file list, so the base worktree already carries it. The two prose pins likewise pin a block that already existed at the base by design, to stop a FUTURE deletion. Alice independently verified the real fail-first property in a scratch copy: deleting the _repo line reddened the deterministic test and test_hammer_a, and removing --with pytest-xdist reddened the pin as an ordinary assertion failure.

### [autonomous] 2026-10-01T04:47:39Z

**Decision**: [BOB] LOW VERIFY: check records for three consecutive runs of the parallel cli command and its serial counterpart; the verification record contains neither parallel evidence nor counts for that directory.

**Choice**: discarded - ran the named check

**Rationale**: Cycle 2: bare -n auto over skills/run-autopilot/cli gave 1952 passed, 0 failed on three consecutive runs (77.86s / 77.83s / 78.04s); the shipped capped form gave 1952 passed, 0 failed on three consecutive runs (153.96s / 91.18s / 92.28s); the serial counterpart is Alice measured 1951 passed, 1 skipped, 0 failed in 221s, the skip being the xdist-gated meta-test that task 4 importorskip intends. All six parallel runs green with the host idle. The counts are now in the cycle-2 review file, which is the record Bob asked for.

### [autonomous] 2026-10-01T04:47:39Z

**Decision**: [BLAKE] LOW: extra artifacts beyond the PRD file list - test_release_checks_parallel_prose.py, the test_repo_disables_signing test, and the test_lane_cli.py fix.

**Choice**: discarded - not a defect

**Rationale**: Cycle 2: Blake judges all three justified in the same line. Each was created by the cycle-1 decision gate against a named finding - the pin file closes the unpinned-block finding (task 5 item 5), the deterministic test closes the probabilistic-guard finding (task 4 item 2), the test_lane_cli.py line closes the same-bug-class finding (task 6) - and each is named in its task file list with its acceptance criterion, so none is unrequested scope.
