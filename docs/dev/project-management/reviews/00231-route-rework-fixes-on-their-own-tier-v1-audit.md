# Decision Audit Log: 00231-route-rework-fixes-on-their-own-tier-v1

PRD: `00231-route-rework-fixes-on-their-own-tier-v1.md`
Started: 2026-09-30T21:53:03Z
Completed: 2026-09-30T21:53:03Z
Autonomous: 7  |  Deferred: 2  |  Doubts: 0

### [autonomous] 2026-09-30T21:53:03Z

**Decision**: release-checks exits 1 at HEAD: test_changelog_unreleased_has_one_changed_heading requires exactly one ### Changed heading under [Unreleased], and the v0.6.0 release commit emptied that section

**Choice**: auto-fix via rework task 4

**Rationale**: cycle 1 of cap 2, so rework is allowed. Classified auto-fix rather than the safety-default deferral: the severity is high by blast radius (the repo release gate and wave assembly are red), not by fix risk. The fix is mechanical and provably intent-preserving, because the assertion message itself states the invariant as no-duplicate-headings while the assertion encodes exactly-one. Deferring would finalize the PRD with its own Success Metric (release-checks green) red.

### [autonomous] 2026-09-30T21:53:03Z

**Decision**: test_rework_tier_prose.py pins slice to end of file instead of to the end of the Compute-the-tier bullet; one test lacks a presence assert; the plan-tasks pin is file-wide; the module docstring restates the tests and claims each file is read once

**Choice**: auto-fix via rework task 5

**Rationale**: medium severity with a clear mechanical fix, and three reviewers reported the window-bound defect in different words (the consolidator left them as separate rows because they cite different lines of one file). Folded into one task because every change is in the same new file and the same theme.

### [autonomous] 2026-09-30T21:53:03Z

**Decision**: Tail sweep sentence still reads as if a default_model floor may apply, though a sweep carries only Medium/Low findings and so never a CRITICAL line

**Choice**: discarded

**Rationale**: contradicts the PRD contract, which states verbatim that the Tail sweep sentence is unchanged and inherits the rule by pointing at the same section. The no-op is the intended consequence, not a defect. Recorded in the settled-decisions ledger.

### [autonomous] 2026-09-30T21:53:03Z

**Decision**: Bob could not statically verify that release checks pass; exact check named: bash dev/bin/release-checks

**Choice**: discarded

**Rationale**: resolved by evidence this cycle: the orchestrator ran bash dev/bin/release-checks at HEAD f550a2e and it exited 1. The named check has been run and its result is the high-severity row now queued as rework task 4. Recorded in the settled-decisions ledger.

### [autonomous] 2026-09-30T21:53:03Z

**Decision**: _compute_tier_bullet stops at the named task-add item, not the bullet boundary; moving any needle into a new sibling bullet inserted before task-add would still pass

**Choice**: auto-fix via the [D2] Tail sweep task

**Rationale**: medium severity with a clear mechanical fix, and it narrows rather than reopens the cycle-1 finding: the window is the bullet today (markers at phase-review.md:269 and :270 are adjacent), but it is bounded by text rather than by Markdown structure. Swept rather than reworked because Medium never blocks convergence.

### [autonomous] 2026-09-30T21:53:03Z

**Decision**: floor_list spans This guarantees: to the qwen_eligible heading, so it includes the paragraphs between them rather than only the contiguous step 4.7 floor list; moving the pointer sentence into a standalone paragraph there would still pass

**Choice**: auto-fix via the [D2] Tail sweep task

**Rationale**: same defect class as the bullet-window row and in the same file: the rework bounded the window by text markers rather than by Markdown structure. Mechanical fix, Medium severity, so swept rather than reworked.

### [autonomous] 2026-09-30T21:53:03Z

**Decision**: the bullet-end marker _NEXT_BULLET and the two plan-tasks slice markers are located with bare str.index, so a reworded sibling bullet or heading kills the test with a ValueError instead of the drift message the suite promises; the presence assert covers only the start marker

**Choice**: auto-fix via the [D2] Tail sweep task

**Rationale**: low severity, additive fix (adds presence asserts, changes no assertion the PRD contract fixes). It is the same defect cycle 1 raised about the start marker, one step out to the end markers, so fixing it now closes the class rather than leaving half of it.

### [deferred] 2026-09-30T21:53:03Z

**Decision**: PRD 00231 Success Metric 3 (a [D] task records tier_reason from the classifier, never floor) may not be observable: the Phase 6 task-add payload line names only estimated_tokens and est_context_peak as classifier-produced fields, and tier_reason is read only in cli/statectl.py:418

**Choice**: deferred to batch end

**Rationale**: out of scope by the PRD text itself (the reviewer notes the spec did not ask for a change here); a gap in the PRD post-release metric, not a spec/implementation divergence

### [deferred] 2026-09-30T21:53:03Z

**Decision**: bash dev/bin/release-checks fails its [checks] runner recursion guard section (6 passed, 20 failed, every failure refusing nested dispatch (depth=1)) when run from inside a nested CLI dispatch, because AUTOPILOT_DISPATCH_DEPTH / COPILOT_CLI / _AUTOPILOT_LOOP are inherited and the guard under test refuses; re-running with env -u for those three passes

**Choice**: deferred to batch end

**Rationale**: out of scope for a prose-only PRD and pre-existing: release-checks exits 0 in a normal shell at this HEAD (orchestrator-verified). It only reproduces from inside a reviewer CLI dispatch, so it affects CLI reviewers running the gate, not the release gate itself. Making those tests scrub their inherited markers is a separate change to the test harness.
