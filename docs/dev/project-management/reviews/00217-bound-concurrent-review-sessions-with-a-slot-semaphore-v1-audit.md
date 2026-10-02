# Decision Audit Log: 00217-bound-concurrent-review-sessions-with-a-slot-semaphore-v1

PRD: `00217-bound-concurrent-review-sessions-with-a-slot-semaphore-v1.md`
Started: 2026-09-29T09:26:01Z
Completed: 2026-09-29T09:26:01Z
Autonomous: 21  |  Deferred: 11  |  Doubts: 0

### [autonomous] 2026-09-29T09:26:01Z

**Decision**: Slot claim is not atomic and reclaim is not exclusive: the semaphore can hand one slot to two holders, or raise FileNotFoundError out of acquire (wave_slots.py:32). 4/4 consensus; reproduced independently by Blake and Carl. This is the MEDIUM the per-task review left unfixed.

**Choice**: auto-fix via rework task 4

**Rationale**: Bounded, well-specified fix both reproductions converged on (stage n.tmp-pid holding owner, then rename onto n). Not a data-model or public-API change, so no research protocol applies; not additive, but the contract is unchanged.

### [autonomous] 2026-09-29T09:26:01Z

**Decision**: The five-minute stderr heartbeat that names the slots dir has no test; every acquire test injects a constant clock so the branch never runs (test_wave_slots.py:64).

**Choice**: auto-fix via rework task 4

**Rationale**: Additive test-only fix for a PRD-mandated behavior. 4/4 consensus.

### [autonomous] 2026-09-29T09:26:01Z

**Decision**: A nonpositive _AUTOPILOT_REVIEW_SLOTS makes acquire poll forever; the hand-export path the PRD names is unvalidated (loop.py:381 / wave_slots.py:54). Blake confirmed count 0 reaches sleep_fn.

**Choice**: auto-fix via rework task 4

**Rationale**: Clear mechanical fix (reject or clamp below 1). 3/4 consensus.

### [autonomous] 2026-09-29T09:26:01Z

**Decision**: release swallows every rmtree error, not just a missing slot, so a failed release silently leaks a slot for the loop lifetime (wave_slots.py:81, also :70).

**Choice**: auto-fix via rework task 4

**Rationale**: Clear mechanical fix; the PRD only asks that an already-gone slot be a no-op. 3/4 consensus.

### [autonomous] 2026-09-29T09:26:01Z

**Decision**: _stale guards only FileNotFoundError: a non-UTF-8 owner raises UnicodeDecodeError out of acquire, and an owner of 0 passes isdigit and os.kill(0,0) so the slot is never reclaimed (wave_slots.py:24). Both confirmed by Blake.

**Choice**: auto-fix via rework task 4

**Rationale**: The PRD mandates reclaiming a malformed owner; the tests cover only the not-a-pid shape. Split back out of the consolidator row it was wrongly merged into.

### [autonomous] 2026-09-29T09:26:01Z

**Decision**: test_docs_name_the_two_variables pins only one variable: the second assertion is a substring of the first, so the test would still pass if the count variable and its default were deleted from waves.md (test_wave_slots.py:141).

**Choice**: auto-fix via rework task 4

**Rationale**: The PRD Phase 2 acceptance criterion says the test pins both variables, so the criterion is not currently met. 2/4 consensus.

### [autonomous] 2026-09-29T09:26:01Z

**Decision**: test_pid_alive_tells_a_live_pid_from_an_exited_one retests an unchanged imported helper (test_wave_slots.py:128).

**Choice**: auto-fix via rework task 4

**Rationale**: De-slop lens finding; removing it loses no coverage of changed behavior.

### [autonomous] 2026-09-29T09:26:01Z

**Decision**: A review row ts_start and wall_secs include the slot wait, so queued review rows overlap beyond the slot count exactly when the semaphore works, defeating the PRD post-release signal (loop.py:506, also :379).

**Choice**: auto-fix via rework task 5

**Rationale**: The PRD third success metric is unmeasurable as built. 2/4 consensus; bounded change at one stash point covering both callers.

### [autonomous] 2026-09-29T09:26:01Z

**Decision**: Two touched tests pass against the pre-change code: test_build_launch_never_touches_slots and test_no_slot_dir_means_no_semaphore (test_loop_slots.py:128). Raised by the doubt lens and by the computed fail-first replay.

**Choice**: settled deferral, ledgered

**Rationale**: Both are PRD-named acceptance criteria asserting that an unchanged path stays unchanged. A negative assertion of preserved behavior passes against the base by construction; making either fail first would change what it tests. The doubt lens filed it in KNOWN with the same justification.

### [autonomous] 2026-09-29T09:26:01Z

**Decision**: Liveness is _pid_alive only, so a recycled pid holds a slot indefinitely (wave_slots.py:29).

**Choice**: settled deferral, ledgered

**Rationale**: Out of scope by the PRD Risks section, which states liveness is by pid; the raiser explicitly declined to count it against the spec. Adding _pid_tagged changes the shared liveness helper, not this PRD semaphore.

### [autonomous] 2026-09-29T09:26:01Z

**Decision**: Bob: cannot statically verify that the recorded test and release-check runs pass at HEAD (codex sandbox is static-only).

**Choice**: routed to verification

**Rationale**: Queued as the command: bash dev/bin/release-checks, in 00217-bound-concurrent-review-sessions-with-a-slot-semaphore-v1-checks-1.json. The work phase step 7 runs it; no task created.

### [autonomous] 2026-09-29T09:26:01Z

**Decision**: Carl first run was not an independent lens: it read dev/local/tmp/bob-output-00217-c1.txt mid-run and returned Bob six findings and all twelve of his R verdicts verbatim, relabelled CARL.

**Choice**: discarded that output and re-dispatched Carl once

**Rationale**: Consolidating it would have inflated every Bob finding from 1/4 to 2/4, corrupting the consensus scores the decision gate reads. Set aside as carl-output-00217-c1.contaminated.txt, dispatch row closed error/non-independent, retried within the one-retry budget with an explicit rule forbidding him to open any other reviewer output, prompt, or the review and state directories. The retry is independent: own reproduction script, own wording, different severity and verdict set.

### [autonomous] 2026-09-29T09:26:01Z

**Decision**: Task 4: the per-task review raised a three-party put-back race in _discard - while a reclaimer holds a live claim aside, the slot name is vacant, so a third acquirer can claim it; the put-back then fails and the live claim is stranded, breaking the never-more-than-N invariant

**Choice**: deferred to the PRD-level review, not fixed in this task

**Rationale**: Closing it completely needs a different primitive. Every check-then-move on a shared directory name has this property because the name itself is the claimable resource and POSIX rename cannot atomically replace a non-empty directory. The correct fix is kernel-released locks (fcntl.flock per slot), which removes liveness probing and the reclaim path entirely - but that replaces the mechanism this PRD specifies (numbered dirs, an owner pid file, loop_gates._pid_alive) and would invalidate most of the 25 tests. Per instruction the implementor changed no behavior for it; it only made the loss loud (the put-back-failure stderr line now names both paths and says a live claim is stranded) and recorded the residual plus the fcntl.flock note in the docstring. NOTE: this is the fourth distinct race found in this family on this task (Blake at review, the orchestrator twice while reading the fixes, then Pat), each narrower than the last - that progression is itself the argument that pid-file liveness is the wrong primitive for an exact semaphore.

### [autonomous] 2026-09-29T09:26:01Z

**Decision**: Task 4: Blake 4/4 finding mentions that release removes whatever dir it is handed with no ownership check, so it would delete a second claimant slot

**Choice**: no ownership check added to release; clause treated as closed by the atomic claim

**Rationale**: That clause is a consequence of the two-holder race it is part of, not an independent defect. Once the claim is atomic, acquire only ever returns a slot the caller owns, so the precondition for releasing someone else slot cannot arise. The PRD contract for release is removes the dir; already gone is a no-op and specifies no ownership check, so adding one would be validation for an unreachable state. Recorded so the review phase can re-raise if it disagrees.

### [autonomous] 2026-09-29T09:26:01Z

**Decision**: Task 4 is a fix commit, and the changelog rule requires a CHANGELOG entry in the same commit for every fix

**Choice**: amended the existing [Unreleased] ### Added entry for the slot semaphore instead of adding a ### Fixed entry

**Rationale**: The semaphore is unreleased and already carries an Added entry from task 3, so a Fixed line would describe a bug no user ever saw - actively misleading in a changelog. Amending the Added entry to state what actually ships (atomic publish, nonpositive count refused, unfreeable slot reported) keeps CHANGELOG.md staged in the fix commit as the rule requires while staying accurate.

### [autonomous] 2026-09-29T09:26:01Z

**Decision**: Task 4: two defects were confirmed after the test suite went green (the reclaim stealing a live claim, and isdigit admitting digits int rejects). rules/testing.md requires a bug fix to ship with its regression test, but Tess 4-dispatch authoring budget was closed and Ivan is normally forbidden from editing test files

**Choice**: authorised Ivan to add exactly one regression test per fix to test_wave_slots.py, changing no existing test

**Rationale**: A fix without its regression test violates the standing testing rule, and the alternative - shipping the fixes untested and letting cycle 2 rediscover them - is worse. Each allowance was scoped to one added test with no existing test touched, and each was watched failing against the prior commit before the fix landed. Four such tests were added this way (reclaim-steals-live-claim, judged-vs-later-read, non-decimal-digit owner, leftover staging dir).

### [autonomous] 2026-09-29T09:26:01Z

**Decision**: Task 4: the PRD pins neither the exception type for a nonpositive slot count nor whether release should raise or report a removal failure, and Tess rule 10a would have made her stop and report a blocker

**Choice**: orchestrator pinned both contracts before dispatching Tess: acquire raises ValueError naming the count before creating dir; release reports a non-FileNotFoundError removal failure on one stderr line and returns None without raising

**Rationale**: Both are boundary contracts a test must assert exactly, and leaving them open would have stalled the task on a blocker report. The release decision is forced by the call site: cli/loop.py invokes release from a finally: block at loop.py:396, where a raise would replace the in-flight exception from _spawn and destroy the real failure. ValueError before dir.mkdir is the fail-loud choice over the alternative of polling forever, and matches the finding wording reject nonpositive counts.

### [autonomous] 2026-09-29T09:26:01Z

**Decision**: Cycle-2 fail-first replay flagged two touched tests in test_loop_slots.py as passing against pre-change code: test_build_launch_ts_start_matches_pre_launch_clock and test_review_launch_without_slots_dir_ts_start_matches_pre_launch_clock.

**Choice**: settled deferral, ledgered

**Rationale**: Same class as the cycle-1 settled entry with new names: both are negative assertions that an UNCHANGED path keeps today timing. The PRD requires every other phase, and every loop without the variable, runs exactly as today, so a test of preserved behavior passes against the base by construction. Task 5 own acceptance criteria name these two tests explicitly. Alice reached the same conclusion unprompted.

### [autonomous] 2026-09-29T09:26:01Z

**Decision**: Cycle-2 fail-first replay flagged 12 touched tests in test_wave_slots.py as passing against pre-change code.

**Choice**: discarded, ledgered

**Rationale**: Artifact of the INCREMENTAL replay base, not a tautology. The base 1ca6f5cb6b73 is cycle 1 HEAD, where test_wave_slots.py already existed with 11 passing test functions. Verified with git show 1ca6f5c: five of the six named tests are present at that base, so they pass there because cycle 1 wrote them; the cycle-2 diff only reorganised the file around them. The sixth is new but backfills coverage of behavior already correct at base, which the replay block itself says passes by design. The cycle-2 fixes are pinned by the 11 touched tests that DID fail against base.

### [autonomous] 2026-09-29T09:26:01Z

**Decision**: Bob: cannot statically verify that the recorded tests and release checks pass at HEAD (codex sandbox is static-only).

**Choice**: routed to verification

**Rationale**: Queued as the command: bash dev/bin/release-checks, in 00217-bound-concurrent-review-sessions-with-a-slot-semaphore-v1-checks-2.json; no task created. The cap-out path runs no work pass, so step 7 never executed it. It is already answered at the reviewed HEAD 83165038f9dfd92ebf64ae94f38f61b946a17ee3 by two independent runs: dev/local/autopilot/last-verification.json records that exact command at exit 0 at that sha, and Carl re-ran it this cycle under env -u AUTOPILOT_DISPATCH_DEPTH -u COPILOT_CLI -u _AUTOPILOT_LOOP and it completed. Recorded in the queue file result.note so the evidence is not lost.

### [autonomous] 2026-09-29T09:26:01Z

**Decision**: Cycle 2 did not converge: an unresolved 3/4 HIGH remains (the three-party put-back race in _discard). state.cycle (2) has reached state.rework_cap (2), so the Phase 5 Cap check applies.

**Choice**: cap-out: created no follow-up tasks, recorded 11 cap-overflow deferrals, finalized as converged-with-deferrals

**Rationale**: Loop mode cap-out defers, never pauses. No 🔴 CRITICAL is present (the highest unresolved severity is 🟠 HIGH), so the cap_critical stall branch does not apply; instead every unresolved finding is written to state.deferred_decisions as a cap-overflow record and the PRD finalizes as converged-with-deferrals. review-work-completion step 7 deliberately created NO follow-up tasks: tasks created here would be stranded pending, since the cap-out path dispatches no rework pass, and that would break the Phase 9 all-tasks-completed invariant. The Tail sweep is skipped because its selection excludes anything already in deferred_decisions, which is now every actionable Medium/Low finding. The HIGH is NOT a settled deferral: cycle 1 recorded it as deferred TO the PRD-level review (this gate), it is absent from the ledger, and deferred_decisions was empty on entry.

### [deferred] 2026-09-29T09:26:01Z

**Decision**: The reclaim can still hand one slot to two holders (three-party put-back race). _discard moves a stale-looking slot aside before judging it; if it wins that rename against a peer that just re-claimed the slot live, the slot name is vacant from os.rename(slot, aside) at wave_slots.py:110 until the put-back at :116. A third acquirer _claim can take the name in that window, the put-back then fails, the live claim is stranded in N.stale-<pid>, and count=1 admits two concurrent sessions. The stranded holder release (no ownership check) later removes the third party slot. The source documents the residual at wave_slots.py:102-106 and names the fix: a per-slot fcntl.flock. File: skills/run-autopilot/cli/wave_slots.py:116

**Choice**: deferred at rework cap

**Rationale**: rework cap reached with this finding unresolved

### [deferred] 2026-09-29T09:26:01Z

**Decision**: Leaked N.tmp-* and N.stale-* dirs are never swept. A kill between mkdtemp and rename, or an ENOSPC on the owner write, leaves a staging dir; a failed _remove leaves an aside dir. Nothing cleans either until the wave-slots dir is removed at wave end. Harmless to correctness because acquire reads only <dir>/<n>. File: skills/run-autopilot/cli/wave_slots.py:77

**Choice**: deferred at rework cap

**Rationale**: rework cap reached with this finding unresolved

### [deferred] 2026-09-29T09:26:01Z

**Decision**: A decimal owner too large for a C int crashes acquire instead of being reclaimed. _is_stale passes a 20-digit decimal (isdecimal true, >0 true) to _pid_alive, whose os.kill raises OverflowError; _pid_alive catches only OSError, so it escapes out of acquire. Reproduced directly against acquire by Alice. A string over 4300 digits would also raise ValueError from int(). Same class as the cycle-1 malformed-owner finding, and the PRD says a malformed owner is reclaimed. Fix: bound the parsed pid, or catch (OverflowError, ValueError) and treat the owner as stale. File: skills/run-autopilot/cli/wave_slots.py:61

**Choice**: deferred at rework cap

**Rationale**: rework cap reached with this finding unresolved

### [deferred] 2026-09-29T09:26:01Z

**Decision**: _discard aside name N.stale-<pid> is deterministic, the exact collision commit ef9314e removed from _claim. If _remove(aside) fails, or a live claim is stranded there by the race above, the next _discard by the same pid renames onto a non-empty leftover, raises OSError and returns False permanently. The loop pid is stable for its lifetime, so that slot number can never be reclaimed again by that loop, silently shrinking wave capacity. Fix: use a unique aside name as _claim does. File: skills/run-autopilot/cli/wave_slots.py:108

**Choice**: deferred at rework cap

**Rationale**: rework cap reached with this finding unresolved

### [deferred] 2026-09-29T09:26:01Z

**Decision**: Scope creep (blind lens, sole B6 fail): _launch and _announce_and_launch now return a ts_start taken after the slot wait, and the metrics clock uses it. The PRD Feature text asks only to acquire, spawn and release in a finally. Counterpoint: the PRD third success metric is unmeasurable without it, which is why cycle 1 created task 5 for exactly this. File: skills/run-autopilot/cli/loop.py:389

**Choice**: deferred at rework cap

**Rationale**: rework cap reached with this finding unresolved

### [deferred] 2026-09-29T09:26:01Z

**Decision**: A bad slot count crashes the loop. _AUTOPILOT_REVIEW_SLOTS=0 or negative makes acquire raise ValueError at loop.py:382, outside the try at :390, so it escapes _launch and kills the loop at its first review launch. A non-numeric value silently falls back to 3 via routing._env_int. Confirmed by reading the call site. The raise is a deliberate cycle-1 decision (fail-loud over polling forever); the open question is fail-loud-crash vs clamp-to-1. File: skills/run-autopilot/cli/wave_slots.py:140

**Choice**: deferred at rework cap

**Rationale**: rework cap reached with this finding unresolved

### [deferred] 2026-09-29T09:26:01Z

**Decision**: The acquire/reclaim mechanism differs from the spec literal wording (mkdir, write owner, rmdir on reclaim); the code stages a mkdtemp dir and publishes with os.rename. That deviation is the sanctioned cycle-1 4/4 fix. The substantive half: os.rename onto an existing EMPTY dir succeeds on POSIX, so an empty <n> from a hand-made mkdir would be silently overwritten. No code path here creates an empty <n>. File: skills/run-autopilot/cli/wave_slots.py:64

**Choice**: deferred at rework cap

**Rationale**: rework cap reached with this finding unresolved

### [deferred] 2026-09-29T09:26:01Z

**Decision**: _claim treats every rename error as a lost slot race. A permission or filesystem error is indistinguishable from an occupied destination, so acquire can poll indefinitely on a broken filesystem. Fix: distinguish ENOTEMPTY/EEXIST from other errors and surface the rest. File: skills/run-autopilot/cli/wave_slots.py:78

**Choice**: deferred at rework cap

**Rationale**: rework cap reached with this finding unresolved

### [deferred] 2026-09-29T09:26:01Z

**Decision**: Review metrics still END after the slot is released: ts_end is read after _launch returns, so decision work runs inside the measured interval while another loop may already hold the slot. Cycle 1 fixed the start of the interval; the same argument applies to its end. Fix: capture the session end before release. File: skills/run-autopilot/cli/loop.py:402

**Choice**: deferred at rework cap

**Rationale**: rework cap reached with this finding unresolved

### [deferred] 2026-09-29T09:26:01Z

**Decision**: Moving ts_start into _launch also changes timing for builds and reviews without a slots dir: their rows now exclude routing and banner time, despite the PRD requiring those paths run exactly as today. UNADJUDICATED DISAGREEMENT: Alice reports two tests pin that these paths keep the old timing, but the fail-first replay shows both of those tests pass against the base, so they cannot demonstrate preservation. The gate did not adjudicate it. File: skills/run-autopilot/cli/loop.py:387

**Choice**: deferred at rework cap

**Rationale**: rework cap reached with this finding unresolved

### [deferred] 2026-09-29T09:26:01Z

**Decision**: The waves.md paragraph sits inside the ## wave run section and reads as a wave run feature. The PRD names manual export for two loops in two repos as a use case, and that is not described. Both variable names and the default 3 are present, so the Phase 2 acceptance criterion itself is met. File: skills/run-autopilot/references/waves.md:205

**Choice**: deferred at rework cap

**Rationale**: rework cap reached with this finding unresolved
