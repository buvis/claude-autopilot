# Decision Audit Log: 00223-enter-the-build-gate-in-one-cli-call-v1

PRD: `00223-enter-the-build-gate-in-one-cli-call-v1.md`
Started: 2026-09-30T08:38:26Z
Completed: 2026-09-30T08:38:26Z
Autonomous: 12  |  Deferred: 3  |  Doubts: 0

### [autonomous] 2026-09-30T08:38:26Z

**Decision**: how to compose the Phase 0 step chain into one autopilot enter call

**Choice**: wrote cli/enter.py as a pure orchestrator over existing functions (do_park, resume_target, custody.pending, selection.select, frontmatter.apply), lifting select and frontmatter cores into shared non-printing functions so the standalone verbs cannot drift from enter()

**Rationale**: 3/3 review dispatches; first draft was built against the stale installed-plugin-cache path convention (dev/local/) instead of this repo live source (docs/dev/project-management/), caught and corrected mid-review along with a dropped batch_init step, an unguarded malformed-stall_op check, and a wrong record_dispatch.py path; no unresolved non-blockers

### [autonomous] 2026-09-30T08:38:26Z

**Decision**: Cycle 1 review: 35 consolidated findings, 0 critical, 6 high, 20 medium, 9 low, from all four lenses (Alice consensus, Blake blind, Bob doubt+de-slop, Carl ui/generalist)

**Choice**: auto-fix via ten [D1] rework tasks, ids 4-13, all at the opus tier per the PRD default_model floor

**Rationale**: cycle 1 of rework_cap 2, so rework is allowed; no CRITICAL row exists so no rework design was run; the ten themed tasks are exactly the scope-alarm ceiling and each carries its findings verbatim

### [autonomous] 2026-09-30T08:38:26Z

**Decision**: Six blind-lens findings assert deviations from the PRD sketch: resume-row written before the lane check, five extra stop values plus --prds and two extra files, the enter() signature, batch carrying null, the synthetic detail string, and python3 instead of sys.executable

**Choice**: discarded, each recorded in the settled-decisions ledger with its reason

**Rationale**: Each is specified verbatim in the design doc and copied into the task contract, which Blake never sees because his lens is PRD-only by construction. The PRD itself allows the design doc to rename but not drop keys.

### [autonomous] 2026-09-30T08:38:26Z

**Decision**: Bob VERIFY item: tests and release checks pass, exact command bash dev/bin/release-checks

**Choice**: routed to verification, queued in checks-1.json, no task created

**Rationale**: It names one exact runnable project check, so the work phase step 7 runs it rather than a task re-running the same suite. Blake and Carl both already ran it green this cycle outside the nested-dispatch environment.

### [autonomous] 2026-09-30T08:38:26Z

**Decision**: The engram context pack failed: engram pack exited 1 with not inside a registered repo, register it in ~/.config/gita/repos.csv

**Choice**: continued with the sentinel (no pack available this cycle) in every prompt, recorded in the review file

**Rationale**: The pack is additive retrieval context; the skill says a pack failure degrades the review but never blocks it. The failure is deterministic (this repo is not gita-registered), so the one permitted retry was skipped.

### [autonomous] 2026-09-30T08:38:26Z

**Decision**: Devon spent both adversarial rounds on task 13 and broke the strengthened tests again with four new defects: a sys.modules hijack that restores sys.path, moving the marker clear to the end of the chain and gating it on success, re-deriving the autopilot dir by walking up, and a prose sentence that is regex-compliant but false

**Choice**: closed only the one weakness that guards this task own change (test_stops_park_halt_when_do_park_returns_an_unmapped_code now asserts parked is None); recorded the other three as residual and did not fix them

**Rationale**: The adversarial budget is 2 Devon dispatches and 1 Tess strengthen per task, and all three were spent; the outcome table says flag and proceed. The unmapped-exit leak was the exception because the task collapse of the _park branches is exactly what could introduce it and no test covered it.

### [autonomous] 2026-09-30T08:38:26Z

**Decision**: Pat raised 6 LOW findings across tasks 12 and 13 and no CRITICAL, HIGH or in-file MEDIUM; all 6 CLOSURE verdicts were resolved

**Choice**: noted all 6, fixed none; refuted one with evidence

**Rationale**: The step 5.7 ladder notes LOW-only findings and proceeds. Two are em-dash complaints already settled at task 8 (matching the file existing style beats rules/writing.md inside phase-build.md and its test modules). One claimed the test_enter_guards docstring wrongly says the import-hygiene pins moved from test_enter.py; git show 67b08ff proves the pin was in test_enter.py and the strengthen commit 4252cdf moved it, so the docstring is accurate and the finding is wrong. The remaining three are wording and readability notes with no behavioural effect.

### [autonomous] 2026-09-30T08:38:26Z

**Decision**: The end-of-turn formatter reflowed .py files three more times this session, on files no agent had opened: test_enter_prose.py twice and enter.py once (110 insertions, 33 deletions, pure magic-trailing-comma and argument-list expansion). One of those reflows would have pushed test_enter.py from 797 to about 820 lines and failed the 800-line style gate on formatting alone. Total measured occurrences in this PRD is now eleven.

**Choice**: reverted every reflow with git checkout -- on the exact paths after confirming no semantic line was touched, and ran git diff --stat immediately before each of the five commits

**Rationale**: The repo has no pyproject.toml and release-checks runs no formatter, so the churn is unrequested and belongs to no task. Committing it would hand the next review cycle formatting hunks to re-read as the task work, and in one case would have tripped a size gate the task did not breach.

### [autonomous] 2026-09-30T08:38:26Z

**Decision**: Blake re-raised the stop vocabulary going beyond the spec (five extra STOPS values, and park exit 2 mapped to park_precondition_failed) as a HIGH at enter.py:29

**Choice**: excluded from the convergence test as a settled deferral

**Rationale**: Same design-approved scope-creep discard the ledger recorded in cycle 1, re-cited at a different file:line so --ledger-dismiss did not match it mechanically. All five values appear verbatim in the design docs STOPS tuple. The one new sub-claim - that mapping park exit 2 is invented - was checked and refuted: _PARK_STOPS[2] is park_precondition_failed (enter.py:62-66), one of the five approved values, and phase-build.md:35 documents its routing to recovery.mds exit-code row 2 second branch. Appended to the ledger as a cycle-2 settled-deferral so it is not re-argued.

### [autonomous] 2026-09-30T08:38:26Z

**Decision**: The computed fail-first replay reported 51 of 139 touched tests passing against cycle 1s HEAD, absorbed as six mech-check findings; the largest is test_shared_lift.pys 16 tests

**Choice**: discarded the test_shared_lift.py row; kept the other five as recorded Medium findings

**Rationale**: The replay base is cycle 1s HEAD, where cli.enter already existed and worked, so a rework cycles strengthened pins and coverage backfills legitimately pass against it. test_shared_lift.py was written by task 9 (commit 4f11652) BEFORE the lift, expressly to prove the refactor preserved behaviour - a pin that failed at base would mean the lift changed behaviour. The replay blocks own caveat covers this case. The other five stay on the record as Medium; test_enter_prose.py::test_every_stop_value_has_a_row passing at base is real signal, since it checks row existence rather than routing correctness, which is the gap the second cap-overflow HIGH names.

### [autonomous] 2026-09-30T08:38:26Z

**Decision**: Nine Medium and six Low findings survived cycle 2, and review-work-completion step 7 would normally create follow-up tasks for them

**Choice**: created no follow-up tasks

**Rationale**: cycle 2 >= rework_cap 2, so the Phase 5 cap check routes this cycle to the loop-mode cap-out, which the gate states has no rework pass and no tail sweep. Creating [D2] tasks would leave them pending at finalize and contradict the gate that just declined to dispatch rework. Every Medium and Low is recorded in the consolidated table of dev/local/reviews/00223-...-review-2.md, which cleanup never deletes; the two unresolved HIGHs went to deferred_decisions as cap-overflow records. Recorded rather than silently skipped.

### [autonomous] 2026-09-30T08:38:26Z

**Decision**: The 414-line enter.py breach was rated High by Blake (blind/spec lens) and Medium by Alice, Bob and Carl; consolidate_findings.py kept the highest severity, making it a 4/4 HIGH that blocks convergence at the cap

**Choice**: kept HIGH as consolidated; did not downgrade to Medium

**Rationale**: It is a written, mechanically measured acceptance criterion of the PRD (Phase 0 Exit Criteria: enter.py under 400 lines) that is not met, and catching exactly that is the blind lenss purpose. Downgrading it to Medium at the cap cycle is what would have let the PRD converge and sweep it, so the reclassification would have been self-serving. Keeping it HIGH routes it to a cap-overflow deferral that is visible at batch-end review instead. Noted that the fix is small (Carl named inlining the single-caller _prepare_tree), which is why it belongs in the deferred record with its remedy rather than being dropped.

### [deferred] 2026-09-30T08:38:26Z

**Decision**: cli/__main__.py is now 1289 lines against the 800-line limit (1253 before this PRD)

**Choice**: deferred to batch end

**Rationale**: Pre-existing debt the PRD explicitly refuses to touch: the task says do not restructure the file. Splitting the CLI registry is its own PRD.

### [deferred] 2026-09-30T08:38:26Z

**Decision**: enter.py is 414 lines against the PRD Phase 0 exit criterion "under 400 lines" (computed: over by 14). Named fixes: move the three side-effect helpers (_git_head_sha, _record_resume_row, _review_log_has_dispatch_line) to a sibling module, inline the single-caller _prepare_tree into _bootstrap, or trim 14 lines of restating docstring.

**Rationale**: rework cap reached with this finding unresolved

### [deferred] 2026-09-30T08:38:26Z

**Decision**: The enter stop-table rows for fs_error and park_halt each name one owning section while the code now raises them from several distinct causes. fs_error fires at enter.py:158 (mkdir failed), :161 (shallow --prds, no grandparent) and :358 (design-doc read failed), but its row routes only to the mkdir block. park_halt fires at :184 (exit 5, systemic halt) and :188 (unmapped park exit code), but its row names only exit-code row 5. Fix: state in both rows that detail selects the owner, as the deferred_io row already does, and name the design-gate non-zero branch for the design-doc cause.

**Rationale**: rework cap reached with this finding unresolved
