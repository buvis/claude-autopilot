# Decision Audit Log: 00279-run-one-exact-reuse-rule-v1

PRD: `00279-run-one-exact-reuse-rule-v1.md`
Started: 2026-10-13T12:04:53Z
Completed: 2026-10-13T12:04:53Z
Autonomous: 18  |  Deferred: 1  |  Doubts: 0

### [autonomous] 2026-10-13T12:04:53Z

**Decision**: R11 pre-existing >50-line functions in cli/verification.py (_run_locked_gate 52, run_gate 53)

**Choice**: settled deferral, not swept

**Rationale**: bodies untouched by this diff; Bob raised it in his own KNOWN bucket as out of scope

### [autonomous] 2026-10-13T12:04:53Z

**Decision**: R13 committed formatter-only churn (quote flips, run_gate argument reflow)

**Choice**: discarded

**Rationale**: cosmetic-only with no behavioral effect; re-reverting committed reflow churns the diff for zero gain

### [autonomous] 2026-10-13T12:04:53Z

**Decision**: R14 step 6 runs autopilot verify for non-counts lines as well as an absent gate line

**Choice**: discarded

**Rationale**: a dirty / counts-unavailable Test gate section yields no counts, so the fallback must fire there; narrowing to absent-only would regress

### [autonomous] 2026-10-13T12:04:53Z

**Decision**: R16 _write_record stores normalize_command(command) rather than the raw command

**Choice**: discarded

**Rationale**: PRD is self-contradictory here; behavior matches its prose and final-verification.md:131, and reuse normalizes both sides

### [autonomous] 2026-10-13T12:04:53Z

**Decision**: R17 uncommitted formatter reflow in test_verification_dirty.py and test_verify_queue_prose.py

**Choice**: fixed at the decision gate

**Rationale**: git checkout -- reverted both files; git status --porcelain then showed no modified source file

### [autonomous] 2026-10-13T12:04:53Z

**Decision**: R4/R7 release gate reports 67 failures, FAIL 0 exit criterion unmet

**Choice**: settled deferral after verification

**Rationale**: a targeted run of test_gate_findings_unread_shapes.py at HEAD aea2279 gives exactly 67 failed, 38 passed; that file is not in the PRD diff and exercises cli/gate.py, untouched here

### [autonomous] 2026-10-13T12:04:53Z

**Decision**: Stale reader contract: final-verification.md still says step 6 "composes the `Tests:` line from the record when its `sha` equals the reviewed HEAD and the three counts are non-null". That is the exact rule this PRD removes. Rewrite it to "step 6 copies `gate.tests_line` (the `## Test gate` section) and runs `autopilot verify` only when that line is not a counts line". The "review composes its Tests: line from it" clause in skills/work/SKILL.md:462 needs the same fix.

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-10-13T12:04:53Z

**Decision**: The retargeted prose pin is partly tautological. `"gate.tests_line" in review or "## Test gate" in review` and `"suite run this cycle" in review` scan the whole SKILL.md and are already true at base (SKILL.md:181 has both tokens, and the old step 6 had the suffix). Only the "never re-derive reuse" assertion binds the change. The test name still says "gated_on_the_sha", which is no longer true. Scope the assertions to the step-6 slice and rename the test.

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-10-13T12:04:53Z

**Decision**: test_step_6_has_no_sha_counts_reuse_rule matches only the `sha … equals/==/matches … HEAD` shape, so a rephrased sha-or-counts condition would pass. The new step-6 sentence "Fail loud: a copied counts line must never read as a fresh run" is also confusing, because a copied `(suite run this cycle)` line is a fresh run. Reword it.

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-10-13T12:04:53Z

**Decision**: The CHANGELOG bullet landed under `### Fixed` (the section runs from line 18 to 64), but the PRD and task 3 require `[Unreleased] ### Changed`. The assumptions note claims it was placed in Changed, which is false. Move the bullet to Changed (line 14) and correct the note.

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-10-13T12:04:53Z

**Decision**: The `or` hedge in test_step_6_composes_from_gate_tests_line (also flagged by the mech block) is satisfied by either token. The new text contains both, so assert both separately. Optionally also pin the TESTS_RE-match and `autopilot verify` fallback wording.

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-10-13T12:04:53Z

**Decision**: The `[Unreleased]` CHANGELOG entry for the `normalize_command` change sits under `### Fixed`. The PRD asks for it under `### Changed`, and the existing `### Changed` section holds only the Python 3.11 line. It also appears as a single line deep in the Fixed list, which makes it easy to miss.

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-10-13T12:04:53Z

**Decision**: Source test checks only that either source name appears; removing the counts-shaped guard or verbatim-copy instruction still passes. Assert those requirements within the step-6 slice.

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-10-13T12:04:53Z

**Decision**: Added tests push this file beyond the 800-line limit: the supplied mechanical facts place the final function through line 805. Move the command-normalization tests into a focused test module and register it.

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-10-13T12:04:53Z

**Decision**: 4 touched test(s) pass against the pre-change code, including test_normalize_command_collapses_whitespace_only: the new whitespace-only tests do not pin this change at base.

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-10-13T12:04:53Z

**Decision**: The prose test `test_step_6_has_no_sha_counts_reuse_rule` is weak. Its single regex needs `sha`, then `==`/`equals`/`matches`, then `HEAD` within 40 characters each. A reworded sha/counts rule, such as "record sha is the reviewed HEAD", would pass it. The positive test accepts any mention of `## Test gate`.

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-10-13T12:04:53Z

**Decision**: R10 test_verification_dirty.py claimed past the 800-line limit (reported as line 805)

**Choice**: discarded - contradicts computed facts

**Rationale**: the file is 799 lines and check_style_limits.py (file_limit 800) exits 0 on this task diff; no violation to fix

### [autonomous] 2026-10-13T12:04:53Z

**Decision**: R12 mech replay said the new normalize_command tests pass against pre-change code

**Choice**: discarded after measurement

**Rationale**: run against a base worktree at d17dde6 the same test file gives 6 failed, 9 passed for -k normalize_command; the six bash/sh/./ cases fail at base, so the tests do pin the change

### [deferred] 2026-10-13T12:04:53Z

**Decision**: dev/bin/release-checks reports 67 pre-existing failures at HEAD aea2279, all in skills/run-autopilot/cli/test_gate_findings_unread_shapes.py (cli/gate.py _is_unread_line), untouched by PRD 00279

**Choice**: deferred to batch end

**Rationale**: verified pre-existing and outside PRD 00279 scope; the gate cannot reach FAIL 0 until that red file gets its own PRD
