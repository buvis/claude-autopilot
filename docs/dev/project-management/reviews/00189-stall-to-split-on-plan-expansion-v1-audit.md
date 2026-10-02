# Decision Audit Log: 00189-stall-to-split-on-plan-expansion-v1

PRD: `00189-stall-to-split-on-plan-expansion-v1.md`
Started: 2026-09-14T15:04:08Z
Completed: 2026-09-14T15:04:08Z
Autonomous: 17  |  Deferred: 9  |  Doubts: 0

### [autonomous] 2026-09-14T15:04:08Z

**Decision**: The PRD's Repository Structure parse rules never mention trailing comments, yet its own 00169 fixture tree carries `# Maps to: ...` after every file name. Strip them, or treat the comment as part of the name?

**Choice**: Strip a trailing ` #` comment and trailing whitespace from each tree line before rebuilding the path (task 2 Details); the ddb fixtures cannot parse otherwise and no PRD tree relies on `#` in a file name.

### [autonomous] 2026-09-14T15:04:08Z

**Decision**: The PRD adds the `plan_expansion_override` state marker and its state-schema row beside `design_gate`, whose row promises a PRD-to-PRD clear, but names no reset for the new marker; without one an opt-in on PRD A survives as a stale `true` in PRD B's state.json.

**Choice**: Task 1 also adds `plan_expansion_override` to `cli/records.PER_PRD_RESET_FIELDS` (and the pinned set in `test_records.py`), matching its siblings `design_gate` and `pause_on_ambiguity`.

**Rationale**: A three-line delta that keeps the schema row truthful and the marker per-PRD; the gate itself reads the PRD text, so this is hygiene, not behavior.

### [autonomous] 2026-09-14T15:04:08Z

**Decision**: Task 3 says a missing --prd is an argparse usage error with exit 2, but cli/__main__.py's _ArgumentParser maps every usage error to exit 1 and reserves 2 for state errors (its docstring exit-code table). Which exit does test_missing_prd_flag_is_a_usage_error pin?

**Choice**: Exit 1, the CLI's documented usage-error code; the PRD contract itself only says 'argparse usage error'. Changed the one assertion Tess wrote from 2 to 1 with a comment naming the table; the --prd-in-stderr assertion is unchanged.

### [autonomous] 2026-09-14T15:04:08Z

**Decision**: F1: Slash-separated file entries lose implicit directory ancestry. A tree containing src/ and a file entry auth/login.py leaves src recursively covered, allowing unrelated src/payments and src/orders tasks through the drift gate (policy.py:126)

**Choice**: auto-fix, reworked in [D1] task 6 (cycle 1); mirrored to the batch deferred JSON via autopilot defer

**Rationale**: orchestrator-confirmed against policy.py:110-134 (only names ending in / feed the ancestry loop). Bounded additive change (a third set in _tree_entries, one leaf-test edit in prd_modules, no signature or Verdict change), so auto-fix at the assumed reading rather than a stall.

### [autonomous] 2026-09-14T15:04:08Z

**Decision**: F2: An absolute tree directory such as /tmp/src/ hangs the ancestor loop: posixpath.dirname("/") == "/", so parsing never terminates, even with the override set (policy.py:131)

**Choice**: auto-fix, reworked in [D1] task 6 (cycle 1)

**Rationale**: orchestrator-confirmed by reading the loop `while path and path != "."`: dirname("/") is "/", so a tree line starting with / spins forever and hangs check-plan and the planning session. One-token guard (stop at "/" too) plus a terminating test; additive, no signature change.

### [autonomous] 2026-09-14T15:04:08Z

**Decision**: F3: Coverage compares unnormalized paths. ./src/auth/a.py is falsely unlisted, while src/auth/../payments/a.py is falsely covered by the src/auth leaf (policy.py:152)

**Choice**: auto-fix, reworked in [D1] task 6 (cycle 1)

**Rationale**: confirmed by reading _file_module (raw startswith and membership tests). Mechanical fix: posixpath.normpath on tree entries and task files before comparison; no rejection logic beyond that.

### [autonomous] 2026-09-14T15:04:08Z

**Decision**: F4: Task metadata lacks boundary validation. schema.py:93-104 skips non-dict task entries, which then crash _group_tasks at task.get; a task with files: [null] disappears from the note with unfiled=0 (policy.py:165)

**Choice**: auto-fix, reworked in [D1] task 6 (cycle 1)

**Rationale**: confirmed against schema.py:96-97 (non-dict entries pass validation) and _group_tasks (non-string items are skipped without counting the task as unfiled). Simplest fix keeps the PRD contract - both shapes count as unfiled and land under (no files declared) - rather than Bob`s proposed new CLI input-error path; no new exception, no schema edit.

### [autonomous] 2026-09-14T15:04:08Z

**Decision**: F5: Split-note directory creation and writing leave OSError uncaught. An existing regular file named split-notes produces a traceback and exit 1, outside step 5.5 documented error handling (__main__.py:435)

**Choice**: auto-fix, reworked in [D1] task 7 (cycle 1)

**Rationale**: confirmed by reading _run_check_plan lines 434-436 (mkdir and write_text unguarded). Mechanical fix: catch OSError, print the one-line check-plan failed message naming the path, return 2, the same fail-loud path an unreadable state or PRD takes.

### [autonomous] 2026-09-14T15:04:08Z

**Decision**: F6: Stall verdicts return before emitting the unfiled/skipped-drift diagnostic; 16 unfiled tasks against a PRD without a tree print neither diagnostic on stderr (__main__.py:439)

**Choice**: auto-fix, reworked in [D1] task 7 (cycle 1)

**Rationale**: confirmed by reading the stall branch (returns 3 right after the two stall lines). The PRD says the diagnostics are visible even on success, which reads as at least on success; printing the same line as a third stderr line on a stall is additive, the stall tests assert only the first two lines, and the detail regex in the report fixture is unaffected.

### [autonomous] 2026-09-14T15:04:08Z

**Decision**: test_step_4_7_payloads_carry_files no longer asserts a files key exists in the payloads (the check moved to test_step_4_7_payload_files_are_real_repo_relative_paths in the fb58278 function-cap split); its name promises what the body does not check, and the fail-first replay shows it passing against the pre-change SKILL.md

**Choice**: auto-fix, reworked in [D1] task 7 (cycle 1)

**Rationale**: found by Alice (Medium), Carl (Medium), Bob (Low, F8) and the mech-check replay; merged by the orchestrator into one [3/4] row (consolidate_findings.py emitted three rows: Bob`s File value carries a :559 suffix and the two Claude-side paraphrases fell below its merge threshold). The PRD`s acceptance list names the test, so the fix keeps the name and adds Carl`s files-key assertion, which also makes it fail at base.

### [autonomous] 2026-09-14T15:04:08Z

**Decision**: SKILL.md step 5.5 still reads "the gate is advice here, not a gate", a self-contradictory carry-over from the pre-PRD wording (Pat LOW carried from the build)

**Choice**: auto-fix, reworked in [D1] task 7 (cycle 1)

**Rationale**: Low, four-word deletion, found by Alice and Carl; no prose pin covers the clause (rg for advice / not a gate over both prose suites returns nothing).

### [autonomous] 2026-09-14T15:04:08Z

**Decision**: Fail-first replay: test_production_parser_exposes_no_count_flag passes against the pre-change code (test_check_plan_cli.py)

**Choice**: discarded (cycle 1), recorded in the settled-decisions ledger

**Rationale**: a pre-existing test moved unchanged into the new file in e1691bb; it pins the absence of a --count flag, already absent at base, so passing there is by design.

### [autonomous] 2026-09-14T15:04:08Z

**Decision**: Fail-first replay: test_optional_markers_stay_absent_rather_than_false and test_plan_expansion_only_counts_inside_a_well_formed_block pass against the pre-change code (test_frontmatter.py)

**Choice**: discarded (cycle 1), recorded in the settled-decisions ledger

**Rationale**: both are negative pins by design (the key is absent by default; a body mention or unterminated block does not opt in), which hold at base because the key was never written there; the positive pin test_plan_expansion_recognized_only_at_allow is among the 55 tests the replay reports failing at base.

### [autonomous] 2026-09-14T15:04:08Z

**Decision**: PRD task 3 literal acceptance command (test_policy.py -k CheckPlanCli) collects zero tests because CheckPlanCliTests moved to test_check_plan_cli.py in e1691bb; the PRD does not document the move

**Choice**: discarded (cycle 2), recorded in the settled-decisions ledger

**Rationale**: the move kept test_policy.py under the 800-line file cap (rules/coding-style.md), is recorded in the cycle-1 review task table, and the tests exist and pass in the new file (Blake and Alice both ran them); the PRD is the spec document, not an artifact the implementation edits, and a test-file relocation is not a user-visible CHANGELOG change

### [autonomous] 2026-09-14T15:04:08Z

**Decision**: Fail-first replay: test_step_4_7_payloads_carry_files passes against the pre-change code at a44f2e03 (test_plan_size_gate_prose.py)

**Choice**: discarded (cycle 2), recorded in the settled-decisions ledger

**Rationale**: the replay base is the cycle-1 head, where the files key was already present; the added `"files": [` assertion fails against the pre-PRD SKILL.md at 184db706 (rg counts 0 occurrences there vs 2 now), so the pin fails where it must

### [autonomous] 2026-09-14T15:04:08Z

**Decision**: Fail-first replay: test_stall_writes_split_note_and_names_the_site passes against the pre-change code at a44f2e03 (test_check_plan_cli.py)

**Choice**: discarded (cycle 2), recorded in the settled-decisions ledger

**Rationale**: the test gained the complementary exactly-two-stderr-lines pin (the negative half of F6: a fully filed plan against a tree earns no third line), which held before the fix by construction; it is a guard on the new report condition, not a tautology

### [autonomous] 2026-09-14T15:04:08Z

**Decision**: Fail-first replay: test_junk_items_in_files_are_ignored_not_disqualifying, test_one_character_directory_is_still_a_leaf and test_root_slash_file_entry_does_not_grant_its_directory pass against the pre-change code at a44f2e03 (test_policy.py)

**Choice**: discarded (cycle 2), recorded in the settled-decisions ledger

**Rationale**: all three are negative pins of behaviour the fix had to preserve: the root-slash file entry test was recorded at task time as a guard against over-correction (a glyph-less root file recorded no directory before the fix either), and the other two are Tess-strengthen pins from the Devon round (a one-character root directory, a junk item beside real paths); the seven positive pins for F1-F4 are among the 12 the replay reports failing at base

### [deferred] 2026-09-14T15:04:08Z

**Decision**: Task-boundary handoff marker cannot be cleared in-session: step 6.5(b) removes dev/local/autopilot/.handoff-requested, but autopilot_context_cap_hook.py re-writes it on the very next PostToolUse fire because the session is still over SOFT_CAP (320K), so the marker (content `unknown`, no in-progress task) survives into the fresh session, whose step 6.5 will hand off again after its first task - a one-task-per-session cadence for the rest of the PRD.

**Choice**: Handed off anyway (lossless; the cost is extra session starts). Recorded here for batch-end review; the fix belongs in the hook or in `_walk_up.py --clear-cap` (clear `.handoff-requested` at task start / session start), outside PRD 00189's scope.

**Rationale**: The marker is a hook-owned artifact and the fix is not in this PRD's files; a stale marker degrades cadence, never correctness.

### [deferred] 2026-09-14T15:04:08Z

**Decision**: F7: _mask_non_prose duplicates the existing implementation in test_plan_tasks_prose.py:55, creating two copies of the same masking behavior to maintain (test_plan_size_gate_prose.py:65)

**Choice**: not reworked; recorded as a settled deferral in the review ledger and the batch deferred JSON

**Rationale**: task 4 mandated copying the private helpers into the new suite rather than importing them, so the two prose suites stay independent; a shared helper module is a new file the plan chose not to add. Batch-end review may overrule (a one-file extraction, S).

### [deferred] 2026-09-14T15:04:08Z

**Decision**: _run_check_plan re-parses the PRD tree via policy.prd_modules(text) to derive drift_word instead of reading it off Verdict (Pat LOW carried from the build; __main__.py:420-424)

**Choice**: not reworked; recorded as a settled deferral in the review ledger and the batch deferred JSON

**Rationale**: the PRD pins Verdict`s field list exactly, so tree presence cannot ride on the dataclass without a spec deviation, and task 3 prescribed deriving drift_word from policy.prd_modules(text); the second parse is pure and costs one string scan. Batch-end review may overrule (e.g. by amending the PRD-level Verdict contract).

### [deferred] 2026-09-14T15:04:08Z

**Decision**: F2 residue: a tree entry `//tmp/src/` still hangs the parse. posixpath.normpath keeps two leading slashes and posixpath.dirname("//") == "//", so _ancestors never stops and grows its list unbounded; the cycle-1 fix bounded the walk at "/" only (orchestrator-confirmed by computing both posixpath values)

**Choice**: deferred to batch end (cap-overflow); the fix is one condition (stop when posixpath.dirname(path) == path, or add "//" to the stop set) plus a bounded test for `//tmp/src/` directory and file entries

**Rationale**: rework cap reached with this finding unresolved

### [deferred] 2026-09-14T15:04:08Z

**Decision**: F9: the _bounded test helper reports a timeout but leaves the looping daemon thread running, so a termination regression keeps consuming CPU (and memory, as _ancestors grows its list) for the rest of the suite; daemon status only affects process shutdown

**Choice**: deferred to batch end (cap-overflow); Bob proposes running the termination probes in an isolated process and terminating it on timeout, following the cleanup precedent in test_state.py

**Rationale**: rework cap reached with this finding unresolved

### [deferred] 2026-09-14T15:04:08Z

**Decision**: step 5.5 Exit 2 bullet still names only an unreadable state or PRD; the rework made an unwritable split note a third exit-2 cause (documented in the CLI docstring and CHANGELOG, not in the skill prose the planner follows)

**Choice**: deferred to batch end (cap-overflow); a four-word addition to the Exit 2 bullet

**Rationale**: rework cap reached with this finding unresolved

### [deferred] 2026-09-14T15:04:08Z

**Decision**: `for item in files if isinstance(files, list) else []:` embeds the type guard in the loop iterable; hoisting it to `files = files if isinstance(files, list) else []` reads cleaner

**Choice**: deferred to batch end (cap-overflow); style only

**Rationale**: rework cap reached with this finding unresolved

### [deferred] 2026-09-14T15:04:08Z

**Decision**: PRD task 3 acceptance line says test_missing_prd_flag_is_a_usage_error pins exit 2; the shipped test pins exit 1 because _ArgumentParser.error maps every usage error to 1 and the CLI docstring exit-code table reserves 2 for state errors

**Choice**: not reworked; the build phase already resolved this as an assumed-ambiguity (autonomous_decisions: the PRD Requirements text says only argparse usage error) and cycle-1 Blake judged the same reading consistent; recorded as a settled deferral in the review ledger and the batch deferred JSON for the batch-end review to confirm or overrule

**Rationale**: the normative Requirements text names no exit code, the literal 2 sits only in the task acceptance line, and making one subcommand usage error exit 2 would break the CLI own exit-code table; overruling costs one assertion plus an _ArgumentParser special case (S)

### [deferred] 2026-09-14T15:04:08Z

**Decision**: test_unwritable_split_note_fails_loud and test_unwritable_split_note_file_fails_loud are near-duplicates differing only in which call inside _write_split_note raises; a subTest loop over the blocker kind would fold them

**Choice**: not reworked; recorded as a settled deferral in the review ledger and the batch deferred JSON

**Rationale**: task 7 kept them separate as independent coverage of the two wrapped calls (mkdir and write_text); Alice own line says no action needed. Batch-end review may overrule (a subTest fold, S)
