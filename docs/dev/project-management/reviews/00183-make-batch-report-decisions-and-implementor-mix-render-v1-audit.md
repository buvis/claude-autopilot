# Decision Audit Log: 00183-make-batch-report-decisions-and-implementor-mix-render-v1

PRD: `00183-make-batch-report-decisions-and-implementor-mix-render-v1.md`
Started: 2026-09-07T10:51:41Z
Completed: 2026-09-07T10:51:41Z
Autonomous: 13  |  Deferred: 0  |  Doubts: 0

### [autonomous] 2026-09-07T10:51:41Z

**Decision**: Task 3 alias table: the investigation file maps decision and detail to issue-or-reason without choosing, and the PRD pins only disposition -> action

**Choice**: auto-fix

**Rationale**: Assigned decision, finding, supersedes and detail to the Issue cell; rationale and assumption to the Reason cell. The investigation names decision as the only text carried by the cycle-only shapes, and the new predicate requires issue text, so routing decision to Reason would keep those rows dropped and defeat the stated goal. Issue chain order: issue, question, decision, finding, supersedes, detail. Action chain: action, disposition. Reason chain: reason, resolution, rationale, assumption.

### [autonomous] 2026-09-07T10:51:41Z

**Decision**: Task 3 acceptance names test_complete_prd_count_matches_rendered_rows in scripts/test_statectl_complete_prd.py, but no test of that name exists, and two tests there pin the rule this PRD replaces

**Choice**: auto-fix

**Rationale**: Read the count-parity test as test_persisted_autonomous_count_matches_rendered_autonomous_data_rows (line 571); it stays untouched and keeps passing. Rewrote the two tests that pin the old any-non-empty-cell rule: test_autonomous_decision_entry_with_only_cycle_populated_is_counted and test_entry_with_non_renderable_key_and_populated_renderable_cell_is_counted. Both assert behaviour the PRD deliberately changes, so leaving them would block the change. Checked the golden-fixture test still expects 6: all six non-blank fixture entries carry issue text.

### [autonomous] 2026-09-07T10:51:41Z

**Decision**: Task 4 contract says _implementor_mix(state, ledger_rows) takes the attempt objects, but it also mandates dedup by (task_id, attempt.attempt) and task_id lives at the ledger row top level, not inside the nested attempt object

**Choice**: auto-fix

**Rationale**: ledger_rows is the list of FULL ledger row dicts already filtered by prd and batch_id; _implementor_mix reads row[task_id] and row[attempt]. Passing bare attempt objects makes the mandated dedup key unbuildable. prd_section does the prd/batch_id filtering because it holds state.prd and state.batch.id, and it gains one optional trailing parameter (ledger path, default None) so every existing positional caller and test keeps working.

### [autonomous] 2026-09-07T10:51:41Z

**Decision**: Task 4 adversarial round cap (2 Devon dispatches) reached with a known test gap still open: the committed suite passes against an implementation that has NO prd/batch filter, because the foreign-PRD and foreign-batch rows in test_rows_for_another_prd_or_batch_are_not_counted share the local implementor and attempt number, so an over-aggressive ledger dedup keyed on (attempt, implementor) hides them

**Choice**: defer-to-review

**Rationale**: The work skill caps the Tess/Devon loop at 2 Devon dispatches per task, then flags and proceeds. Flagged rather than iterated. Two assertions would close it: give a foreign row an implementor that appears nowhere locally and assert it is absent, and add two different tasks sharing an attempt number AND an implementor asserting the count is 2. The prd+batch filter and the (task_id, attempt) dedup key are both stated explicitly in the implementor brief and in the review brief, so the requirement is not lost; the PRD-level review lenses see the same diff.

### [autonomous] 2026-09-07T10:51:41Z

**Decision**: Task 7 is planned to add the Implementor Mix CHANGELOG entry, but task 4 is the fix commit and rules/changelog.md requires the entry in the same commit as the user-visible change, not deferred

**Choice**: auto-fix

**Rationale**: Added the `### Fixed` line for the Implementor Mix in task 4 commit 8b5a2b6, where the blocking rule requires it. Task 7 keeps its other half (the ledger-source note in references/batch-report-format.md) and its acceptance check `rg -n implementor mix CHANGELOG.md` returns one hit, so task 7 verifies the line rather than adding it. Same call was made for task 3, which also shipped its own Fixed line.

### [autonomous] 2026-09-07T10:51:41Z

**Decision**: Task 7's acceptance criterion is `rg -n 'implementor mix' CHANGELOG.md` returns one hit under [Unreleased]. That command is case-sensitive and returns zero hits, because the CHANGELOG prose capitalises the section name as 'Implementor Mix'. Should the CHANGELOG prose be lowercased to satisfy the literal grep, or should the criterion be read as case-insensitive?

**Choice**: Read the criterion as case-insensitive. The required entry already exists verbatim at CHANGELOG.md line 22 under [Unreleased] / ### Fixed, and `rg -ni 'implementor mix' CHANGELOG.md` returns exactly one hit inside [Unreleased] (a second hit at line 117 sits under an older released version). Lowercasing correct prose to satisfy a grep would be fixing the test rather than the implementation, so the CHANGELOG was left untouched and task 7 verified it instead of adding it.

### [autonomous] 2026-09-07T10:51:41Z

**Decision**: The fail-first replay block fed to all four reviewers reported 51 of 89 touched tests as passing against the pre-change code, which would have failed R2 and forced a large rework

**Choice**: auto-fix

**Rationale**: Discarded all six [MECH] replay rows as refuted by direct measurement. Replayed in a real git worktree at 479142e with HEAD test files overlaid: test_cycles_falls_back_to_completed_prd_record, test_every_issue_alias_feeds_the_issue_cell, test_every_reason_alias_feeds_the_reason_cell, test_an_empty_earlier_alias_falls_through_to_the_next_one and test_disposition_renders_as_action all fail there. Cause: replay_tests_against_base.py credits a pytest subTest parent node as passed. Alice reached the same conclusion independently. Five flagged tests do genuinely pass at base and are legitimate precedence/back-compat guards. The tool defect is deferred to batch end as out of this PRD diff scope.

### [autonomous] 2026-09-07T10:51:41Z

**Decision**: Alice declared the build gates carry-forward item 4 (ledger fixture does not pin the prd/batch filter) resolved, while Bob and Carl both raised it as a live gap

**Choice**: auto-fix

**Rationale**: Upheld Bob and Carl. Alice tested only the single mutation (filter removed), which does fail the test. Ran the combined mutation the carry-forward actually describes: filter removed AND dedup keyed on (attempt, implementor) instead of (task_id, attempt). Result: unmutated PASS, filter-only FAIL, combined PASS. The fixture therefore does not independently pin the filter, so the gap is real and is tasked as [D1] task 11.

### [autonomous] 2026-09-07T10:51:41Z

**Decision**: consolidate_findings.py under-merged three defects that reviewers described in different words at the same file: the unreadable-ledger gap appeared as 3 rows, the test_schema.py size as 2, and the str.find anchor weakness as 2

**Choice**: auto-fix

**Rationale**: Applied a documented hand-merge on top of the script output rather than falling back to model-side consolidation, since the script itself ran clean. The merges raise those three findings to [3/4], [3/4] and [3/4] consensus. The scripts raw output is left unmodified on disk and the hand-merge is disclosed in the review files cycle notes, so a wrong merge is visible rather than silent.

### [autonomous] 2026-09-07T10:51:41Z

**Decision**: gather-context.sh resolves the branch base to master, which equals HEAD in this repo, so a bare full review would have produced an empty diff and reviewed nothing

**Choice**: auto-fix

**Rationale**: Ran the script with --since <work_start_sha> (479142e) so the diff covers the PRDs whole work range, which is what the skills COVERAGE_DIFF_RANGE rule prescribes for a full review under autopilot. The script then labels the scope incremental, so the context files diff-scope line was corrected in place to say FULL review and to tell reviewers to read the entire diff. Recorded because an empty diff must never reach a converged verdict.

### [autonomous] 2026-09-07T10:51:41Z

**Decision**: Task 9 adversarial cap (2 Devon dispatches) reached with Devon still able to pass the suite using an enumeration+blacklist implementation: cycle and severity cells answered from lookup tables (range(20) and the 8 sampled severity strings), an unnamed key leaking into Issue/Action/Reason past a blacklist of the bookkeeping keys the test enumerates, and a non-string type blacklist that a tuple, bytes or object() slips through

**Choice**: defer-to-review

**Rationale**: The work skill caps the Tess/Devon loop at 2 Devon dispatches per task, then flags and proceeds; round 1 already closed four different weaknesses and was verified against Devon's own implementation. Devon states the chain-order tests, the empty-string fall-through, the assumed-ambiguity type rule and the blank-row filter are all solid, so task 9's OWN behaviour (non-string shadowing, finding-before-decision) is pinned. Three of the four residual gaps are in tests that predate this task (cycle echo, severity echo, keys-outside-the-chains), and the fourth only bites an implementation that blacklists types instead of testing isinstance(value, str) - which is what the implementor brief mandates. Closing assertions Devon supplied verbatim, for whoever picks this up: object() sentinel with assertIs for the cycle and severity echo, an unpredictable key name like zz_unknown_9f3 for the leak, and a tuple or bytes added to the non-string value set.

### [autonomous] 2026-09-07T10:51:41Z

**Decision**: The PRD's task-2 acceptance criterion, and the task-11 finding derived from it, both name `python3 skills/run-autopilot/cli/statectl.py <tmp state> append autonomous_decisions '{"cycle": 1}'` as the command that must exit 1 with `rejected: autonomous_decisions entry missing issue`. That path is not runnable: cli/statectl.py does `from . import render_report, schema, state` with no __main__ guard, so executing it directly raises ImportError: attempted relative import with no known parent package. Reproduced directly, exit 1 with that traceback. The only process entry point is the shim skills/run-autopilot/scripts/statectl.py, which re-exports main and is what the documented call sites use.

**Choice**: auto-fix

**Rationale**: Wrote the task-11 subprocess test against the runnable shim, scripts/statectl.py, resolved from Path(__file__) rather than hardcoded. The criterion's intent is the statectl CLI rejection contract - exit 1, the exact stderr line, a byte-identical state file - and the shim is the only way to exercise that contract from a subprocess, so testing it there satisfies the intent while the literal path in the criterion does not. Flagging the consequence rather than burying it: task 2 shipped earlier in this same cycle carrying this criterion, so its stated verification command could never have run as written; whoever reviews this cycle should confirm task 2's rejection behaviour was checked some other way. The production code is not at fault here - only the acceptance prose is.

### [autonomous] 2026-09-07T10:51:41Z

**Decision**: Task 12's acceptance criteria are arithmetically unsatisfiable as written. They require `wc -l test_schema.py` at or under 800, 'the new sibling module' (singular) also at or under 800, and the total `def test_` across 'the two files' to equal the count before the split. But test_schema.py now holds 1608 lines of content, and 800 + 800 = 1600 < 1608 - so no two-file split can put both files under the limit even before the new module's own header. The criteria also quote a stale test count, '109 currently in test_schema.py'; the real count is 119, because task 8 added 9 tests and task 11 added 1 after this task was written.

**Choice**: auto-fix

**Rationale**: Resolved by the simplest safe reading of the intent rather than the stale letter. The criterion's purpose is 'no file over the 800-line limit, with no test lost or weakened', and 'the two files' was an estimate made when the file was 1400 lines and this PRD had not yet added two more test classes to it. So the split may produce as many sibling modules as the limit requires (three files, or two plus a shared fixtures module), and the count to preserve is the 119 measured immediately before the split, not the literal 109. Every other constraint is kept exactly: a pure move, no test renamed, deleted, weakened or rewritten, and every resulting file at or under 800 lines. Measured before briefing: 1608 lines, 119 `def test_`, decision-contract block at lines 755-1608.
