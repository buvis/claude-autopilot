# Decision Audit Log: 00242-harden-the-wave-verbs-v1

PRD: `00242-harden-the-wave-verbs-v1.md`
Started: 2026-10-03T23:25:10Z
Completed: 2026-10-03T23:25:10Z
Autonomous: 12  |  Deferred: 4  |  Doubts: 0

### [autonomous] 2026-10-03T23:25:10Z

**Decision**: Design for six wave-verb hardening fixes (00221,00222,00225,00226,00227,00239): save-before-teardown ordering, foreign_dirty gate + seeded-backlog hold, hand-review land path, per-slot fcntl lock, in_wave_lane guard, release-checks wiring

**Choice**: approved design, proceeding to planning

**Rationale**: 3/3 reviewer dispatches (claude, codex, codex), 0 open cardinal sins/blockers after fixes

### [autonomous] 2026-10-03T23:25:10Z

**Decision**: 00226: land never saves converged on the hand-review route; _land_review_failed is unchanged and the window between _land_migrate and the done save leaves wave.json at review_failed with the stub already moved

**Choice**: auto-fix, task [D1] created

**Rationale**: Orchestrator-verified in cycle 1 against wave_review.py:501 and :543-564: signature is still (repo, wave) and no converged save exists. The fix is the design doc verbatim contract, so this is a pinned regression, not a new design. The reviewers refusal-path variant (returns 5) was refuted: _land_converged checks base_sha before any mutation.

### [autonomous] 2026-10-03T23:25:10Z

**Decision**: 00222: _drain_lane early return at :519 means a crash between the worktree_removed save and branch -D never retries the delete, leaking the lane branch

**Choice**: auto-fix, task [D1] created

**Rationale**: 3/4 consensus (Alice, Blake, Bob) in cycle 1; clear mechanical fix and the new docstring currently claims the opposite behaviour.

### [autonomous] 2026-10-03T23:25:10Z

**Decision**: 00222: the OSError guard was added only to the assemble verb; wave run chains the same assemble under _GUARDED_ERRORS, which omits OSError

**Choice**: auto-fix, folded into the 00222 task

**Rationale**: 2/4 consensus in cycle 1. Same-class gap found by the bug-fix-discipline question; a one-token fix in the same area as the primary 00222 change.

### [autonomous] 2026-10-03T23:25:10Z

**Decision**: 00225/00221: the PRD named acceptance tests do not exist at their named ids (test_wave_review.py::test_store_churn_... landed as test_wave_review_cleanup.py::test_store_only_churn_...), and three PRD-named or touched tests pass against the pre-change code

**Choice**: auto-fix, task [D1] created

**Rationale**: 2/4 consensus on the id deviation plus mech-check replay evidence in cycle 1. B15 fails on acceptance-by-test-id, and 00221 acceptance explicitly requires fail-first.

### [autonomous] 2026-10-03T23:25:10Z

**Decision**: 00225: _hold_backlog leaves the move renamed and staged but uncommitted when git commit fails, and Path.rename silently overwrites an existing hold/<name>

**Choice**: auto-fix, task [D1] created

**Rationale**: 2/4 consensus (Alice, Bob) in cycle 1; contradicts the function own docstring claim that retry is safe.

### [autonomous] 2026-10-03T23:25:10Z

**Decision**: 00227: _slot_lock mkdir and open are unguarded, so release can raise from loop.py finally, mask the in-flight error and leak the slot, breaking the never-raise contract documented on _remove

**Choice**: auto-fix, task [D1] created

**Rationale**: 2/4 consensus (Alice, Blake) in cycle 1; a fail-open in a cleanup path, and _remove already models the catch-and-report-on-stderr shape to copy.

### [autonomous] 2026-10-03T23:25:10Z

**Decision**: Verification-check queue for cycle 1 is empty

**Choice**: no checks queued

**Rationale**: Eve is not active this cycle (doubt_reviewer=codex and the codex rung guard did not fire), and Bob assembled persona carries no FIX/VERIFY/KNOWN buckets, so no doubt-lens VERIFY bucket existed to queue. Bob cannot-statically-verify line was answered in-cycle by the orchestrator release-checks run (2247 passed) and Blake -k run (435 passed).

### [autonomous] 2026-10-03T23:25:10Z

**Decision**: Cycle 2 converged: 13 consolidated findings, all medium/low, across Alice, Blake, Bob and Carl. 7 actionable medium/low findings remain.

**Choice**: swept into one [D2] Tail sweep task

**Rationale**: No unresolved CRITICAL or HIGH remains, so the review-rework loop converged and the cap (cycle 2 of 2) is irrelevant. The medium/low tail is swept, not dropped: one rework task closes it, then the PRD finalizes. Per-finding task creation in review-work-completion step 7 was skipped on purpose so the sweep is the only dispatch.

### [autonomous] 2026-10-03T23:25:10Z

**Decision**: Blake (blind): scope creep in _hold_backlog - the FileExistsError collision refusal and the staged/untracked retry logic are absent from the PRD text.

**Choice**: discarded with a verified reason

**Rationale**: Both halves were mandated by cycle 1's own [2/4] finding (uncommitted-move retry gap plus the silent hold/<name> overwrite) and by the PRD's 00225 Risks mitigation. Blake is blind by design and cannot see the prior cycle. Reverting would reopen the cycle-1 finding. Ledgered.

### [autonomous] 2026-10-03T23:25:10Z

**Decision**: Blake (blind): _drain_lane's rerun branch-delete path is beyond the spec but harmless.

**Choice**: discarded with a verified reason

**Rationale**: That path is exactly what cycle 1's [3/4] branch-leak finding required; without it a crash between the second save and `branch -D` leaks wave/<id>/lN permanently. The raiser calls it harmless and guarded. Ledgered.

### [autonomous] 2026-10-03T23:25:10Z

**Decision**: mech-check replay: test_store_churn_in_the_assembly_worktree_does_not_refuse and test_retrying_seed_state_does_not_recommit_the_held_backlog pass against the pre-change code.

**Choice**: discarded with a verified reason

**Rationale**: The first is cycle 1's renamed acceptance test, pinning behaviour that landed in cycle 1, so it passes at this cycle's base by construction; the second gained the asserts that removed its vacuity and still passes because the base already had the non-recommit behaviour. Five of seven replayed tests fail against base. Ledgered.

### [deferred] 2026-10-03T23:25:10Z

**Decision**: 00225: the PRD Risks promise that the wave report names every PRD moved to hold/, but only the git commit body names them; and landing may park master backlog PRDs in hold/ against waves.md:22

**Choice**: deferred to batch end

**Rationale**: Requirements ambiguity between the PRD Outputs and the PRD Risks (cycle 1). The design doc already flagged the report-surfacing gap as an explicit planner task. The land-routing half is suspected, not confirmed by an end-to-end land run, so a blind fix could change land semantics.

### [deferred] 2026-10-03T23:25:10Z

**Decision**: 00222: a pre-existing crash window remains before _drain_lane first save - held_prds and migrated_at are in memory only while migrate_lane moves PRDs and appends jsonl rows

**Choice**: deferred to batch end

**Rationale**: Both raising reviewers call it pre-existing and matching the PRD literal wording (cycle 1). 00222 scope is the window around the two destructive git calls, which is now closed.

### [deferred] 2026-10-03T23:25:10Z

**Decision**: 00225: _land_cleanup exempts every store path then runs worktree remove --force, discarding uncommitted store files _land_migrate does not copy

**Choice**: deferred to batch end

**Rationale**: Spec-directed and labelled not-a-bug by the reviewer who raised it (cycle 1); the PRD requires this widening. Recorded so the residual discard stays visible.

### [deferred] 2026-10-03T23:25:10Z

**Decision**: _hold_backlog calls _default_run_git directly; seed_state has no injectable run_git, so the held-backlog git step cannot be faked or crash-simulated in tests (Blake, medium). Behaviour is correct.

**Choice**: deferred to batch end

**Rationale**: Adding a run_git parameter changes seed_state signature for testability neither the PRD nor the design doc asks for; operator call. Recorded via autopilot defer into 202610031511-deferred.json and the ledger.
