# Decision Audit Log: 00190-bind-the-codex-run-tests-and-dedupe-their-split-v1

PRD: `00190-bind-the-codex-run-tests-and-dedupe-their-split-v1.md`
Started: 2026-09-14T16:58:03Z
Completed: 2026-09-14T16:58:03Z
Autonomous: 6  |  Deferred: 2  |  Doubts: 0

### [autonomous] 2026-09-14T16:58:03Z

**Decision**: Leading-dash plain-path case (2b) never asserts the final argv token is "-" though the PRD requires stdin bytes AND argv ends with - on each of plain/json/resume

**Choice**: auto-fix (rework task 4, [D1])

**Rationale**: Cycle 1: additive fix (one read_argv_array plus a conjunct and a combined label); confirmed by reading test_codex_run.sh:47-61 where 2b diffs stdin only while 2c and the resume case check the final token

### [autonomous] 2026-09-14T16:58:03Z

**Decision**: test_codex_run_resume.sh is 413 lines, over the PRD Output contract "two scripts under 400 lines each"

**Choice**: auto-fix (rework task 4, [D1])

**Rationale**: Cycle 1: measured wc -l 145/350/413; mechanical fix by condensing the resume script commentary without dropping a case or assertion

### [autonomous] 2026-09-14T16:58:03Z

**Decision**: F2: New JSON/resume leading-dash cases never assert their dispatch mode; a plain invocation or fresh fallback can satisfy their checks

**Choice**: auto-fix (rework task 4, [D1])

**Rationale**: Cycle 1: Medium 1/4 and additive - one argv_has_pair --output-last-message conjunct on 2c and an exec resume <uuid> prefix check on the resume case, mirroring case 14

### [autonomous] 2026-09-14T16:58:03Z

**Decision**: F4: Folded JSON marker check retains its standalone PASS label instead of the required combined host label

**Choice**: auto-fix (rework task 4, [D1])

**Rationale**: Cycle 1: Low; the PRD says the folded cases old labels become combined host labels, so the final-token conjunct and label join case 10 of the --emit-thread-id block

### [autonomous] 2026-09-14T16:58:03Z

**Decision**: Release-checks block is labeled [checks] dispatch ledger rather than the PRD literal [checks] record_dispatch

**Choice**: auto-fix (rework task 4, [D1])

**Rationale**: Cycle 1: Low; one-word rename of the echo at dev/bin/release-checks:24 to the PRD name

### [autonomous] 2026-09-14T16:58:03Z

**Decision**: PRD file still sits in dev/local/prds/wip/ rather than dev/local/prds/done/ despite implementation being verified complete

**Choice**: discarded at the decision gate (ledger disposition: discarded); no task

**Rationale**: Cycle 2: not a defect in the reviewed work. The PRD lifecycle keeps a PRD in wip/ until the Phase 9 finalize session performs the verified wip->done move, which runs only after the review loop converges; at review time wip/ is correct by construction and no rework task may move it early. Verified: state.phase == review and phases_completed lacks 'review'.

### [deferred] 2026-09-14T16:58:03Z

**Decision**: F6: New leading-dash cases remove output files before use even though their unique paths are inside a freshly created temporary directory; remove these redundant cleanup commands.

**Choice**: deferred (ledger settled-deferral, batch deferred JSON)

**Rationale**: Cycle 1: the new cases copy the rm -f pattern every sibling case already uses (test_codex_run_resume.sh:22, the --emit-thread-id block); removing it from the new cases alone leaves the harness inconsistent and touching baseline cases is outside the PRD contract; batch-end review may overrule

### [deferred] 2026-09-14T16:58:03Z

**Decision**: Unchecked negative array index on empty ARGV_ARR causes bad array subscript in bash 3.2

**Choice**: deferred (ledger settled-deferral, batch deferred JSON)

**Rationale**: Cycle 1: confirmed on /bin/bash 3.2.57 (stderr line, FAIL branch taken, script continues); the pattern is baseline (case 14, old case 45) and only fires when codex was never invoked, which already FAILs, so the verdict is correct; a guard would touch pre-existing cases; batch-end review may overrule
