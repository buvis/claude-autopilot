# Decision Audit Log: 00278-make-release-checks-tell-truth-v1

PRD: `00278-make-release-checks-tell-truth-v1.md`
Started: 2026-10-13T10:25:13Z
Completed: 2026-10-13T10:25:13Z
Autonomous: 14  |  Deferred: 12  |  Doubts: 0

### [autonomous] 2026-10-13T10:25:13Z

**Decision**: 00278 design: packet 7 CHANGELOG premise (stale, from the 2026-10-10 agoge audit) had already been closed by PRD 00271 before this PRD was selected; tracon [checks] block description self-contradicted within the draft; release guard clause was ordered after git pull; refusal-test fixture listed a non-working REPO_ROOT strategy

**Choice**: replaced the stale CHANGELOG instruction with a new bullet citing PRD 00271 (verified live against the hook: all four cited false-negative phrasings now deny); fixed the tracon block description to match the correct no-existing-block framing; moved the release guard before git pull; narrowed the fixture design to the one working REPO_ROOT strategy (copy the script into the fixture tree)

**Rationale**: a fresh Claude dispatch and a mandatory codex cross-model dispatch (3 reviewer passes total) found these before task planning; PRD 00278 self-matching "release is blocked" while in wip/ was recorded as an accepted operational risk, not fixed, since the pinned acceptance test uses an isolated fixture

### [autonomous] 2026-10-13T10:25:13Z

**Decision**: task 4 discovered a pre-existing stricter gate (hooks/test_hook_registration.py::test_every_hooks_test_file_is_in_the_release_gate) requiring every hooks/test_*.py be named in dev/bin/release-checks, independent of the PRD 00278 whole-repo pin task 9 builds; the new scratch-replay test file tripped it

**Choice**: added hooks/test_guard_phase_delegation_scratch_replay.py to the existing [checks] hook registration block in dev/bin/release-checks (it skips cleanly, no scratch files in a clean checkout); kept the design doc's planned UNGATED entry for it too in task 9 (harmless redundancy - either condition satisfies the new pin)

**Rationale**: both pins must stay green; the file being named directly in release-checks and also listed in UNGATED is not a contradiction since the new pin test only fails when neither condition holds

### [autonomous] 2026-10-13T10:25:13Z

**Decision**: Task 9 contract specified a plain substring membership test (path not in text) for the gate pin; the implementation added a _dir_is_bare_target clause so a whole-directory pytest target counts as covering the files it collects.

**Choice**: Kept the clause but tightened it to a whole-word match that rejects the repo root. It is load-bearing: the [checks] fast-track lane block runs pytest over skills/fast-track/scripts, which really collects 11 tracked test files, so a plain substring test would have failed falsely. The loose form also matched the repo-root parent "." (a live hole: any root-level test file always passed the pin) and any longer token sharing the prefix. Now pinned by two unit tests. Residual, accepted and carried to the PRD-level review: a directory path written as its own space-delimited word in an echo label or comment still satisfies the matcher; closing that needs an argument-line parser.

**Rationale**: The deviation makes the gate stricter than the contract text, not looser, and the contract wording assumed no whole-directory pytest targets existed.

### [autonomous] 2026-10-13T10:25:13Z

**Decision**: The scratch-replay file was added to the gated `[checks] hook registration` block, which contradicts PRD 00278 (the file is "not run by `release-checks`" and is the one `UNGATED` entry). The `UNGATED` entry is now dead because the file is named in the script. The gate's counts now depend on whether gitignored scratch files exist: skipped in a clean clone, run in the live checkout. That is the live-vs-clone mismatch packet 12 set out to remove. Remove the line from the block so `UNGATED` is real and the pin stays honest.

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-10-13T10:25:13Z

**Decision**: `test_a_directory_matching_only_part_of_a_longer_token_is_not_a_gated_target` and `test_the_repo_root_is_never_a_gated_target` pass against base. They exercise only the new `_dir_is_bare_target` helper defined in the same file. They are not tautological as written, but they pin an addition the design did not ask for. The design's pin is a plain `path not in text` substring check. The directory-target branch is needed for the whole-directory `skills/fast-track/scripts` target at release-checks:171, so keep it. Add a one-line comment saying so, and add a test that names the fast-track case. Also note that a bare mention of a directory in an `echo` or comment line would mark every test file under it as gated.

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-10-13T10:25:13Z

**Decision**: The replay file redefines `_tool_input` and `_guard_module`, which duplicate the originals in `hooks/test_guard_phase_delegation.py`. It already imports `_agent_payload`, `_description` and `_run` from that module. Import the two helpers too.

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-10-13T10:25:13Z

**Decision**: The new `## Two more CLI verbs` heading was inserted in the middle of the "Build-Session Model Promotion Signals" section. The `**Target resolution.**` and `**The five signals.**` paragraphs that follow now sit under the wrong heading. The two verb lines also have no list markers, so Markdown renders them as one run-on paragraph. Move them into a real CLI-verb listing or the end of an existing section, and use bullets.

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-10-13T10:25:13Z

**Decision**: `test_allow_corpus_ignores_scratch_dispatch_files` passes against the pre-change code. The replay overlays HEAD's test file, so the narrowed `_allow_corpus` already applies. It also compares `_allow_corpus()` to a `before` value taken from the same function, not to the committed fixtures glob. The contract asked for `== sorted((FIXTURES / "allowed").glob("*.txt"))` before and after the scratch file exists. Assert that literal so the test pins the rule.

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-10-13T10:25:13Z

**Decision**: The pin deviates from the spec. The spec says it compares tracked files with "the paths literally named in the script". `test_every_tracked_test_file_is_gated` also accepts any file whose parent directory appears as a bare token (`_dir_is_bare_target`)

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-10-13T10:25:13Z

**Decision**: The corpus regression test compares against `_allow_corpus()` itself rather than the committed fixtures; the supplied replay confirms it passes at base. Assert the exact fixture list before and during scratch-file presence, and verify that restoring the old implementation fails.

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-10-13T10:25:13Z

**Decision**: The regression test overwrites and deletes a fixed file in the live checkout, risking existing scratch content and concurrent-test interference. Use an isolated temporary corpus with monkeypatching.

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-10-13T10:25:13Z

**Decision**: The gate time cost is not recorded anywhere I could find. The spec asks the task report to state the new wall time, and I did not run the full gate, so I could not measure it

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-10-13T10:25:13Z

**Decision**: The required before/after gate wall-time report is absent from the supplied evidence. Check the task-9 report against the recorded baseline and revised gate elapsed times; record both and their delta.

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-10-13T10:25:13Z

**Decision**: Cycle 1 review raised 15 findings, no CRITICAL. R1/R2/R3/R4/R7/R9/R10/R11/R14/R15 classified auto-fix (mechanical or additive); R5/R6/R8 are the settled pre-existing-failure deferral for PRD 00277s test_gate_findings_unread_shapes.py; R12/R13 settled as no-defect (transient by design / reviewer-unverified note).

**Choice**: queued 4 [D1] rework tasks (10,11,12,13) at sonnet; 5 findings ledgered as settled deferrals

**Rationale**: No CRITICAL row, so no rework design; cycle 1 < cap 2, so rework proceeds. Alice and Bob disagreed on _dir_is_bare_target: kept Alices position (the helper is needed for the whole-directory skills/fast-track/scripts target at release-checks:171) and queued the comment plus a fast-track test instead of removing it.

### [deferred] 2026-10-13T10:25:13Z

**Decision**: The gate does not reach `FAIL 0`. Phase 1 acceptance and exit criterion, "`bash dev/bin/release-checks` exits 0 with `FAIL 0`", is unmet

**Rationale**: deferred by review-close

### [deferred] 2026-10-13T10:25:13Z

**Decision**: The required FAIL 0 acceptance remains unmet: 67 failures reproduce identically at base and belong to parked PRD 00277. Resolving that PRD's unfinished behavior is outside this change's scope; retain the documented deferral.

**Rationale**: deferred by review-close

### [deferred] 2026-10-13T10:25:13Z

**Decision**: The task 9 acceptance criterion (`bash dev/bin/release-checks` exits 0 with `FAIL 0`) is unmet. The gate shows 67 failures, all in `test_gate_findings_unread_shapes.py`, a PRD 00277 file that was already gated and is parked in hold. The deferred-findings record documents this and it is out of scope here. It still means the PRD's exit criterion is not met, and the gate stays RED for any release until 00277 is finished or its tests are retired.

**Rationale**: deferred by review-close

### [deferred] 2026-10-13T10:25:13Z

**Decision**: The new refusal guard in `dev/bin/release` matches the open PRD 00278 itself, because it contains the phrase "release is blocked" and sits in `wip/`. No real release can run until the PRD reaches `done/`. The design doc records this and the test uses an isolated fixture, so no change is needed. Keep it in mind at release time.

**Rationale**: deferred by review-close

### [deferred] 2026-10-13T10:25:13Z

**Decision**: `skills/work/SKILL.md` is 492 lines and the leave-row test passes, but I could not confirm the moved text landed in a reference file. All of these pass in the combined run: the three red tests, `test_release_refuses_while_a_held_prd_blocks_it`, `test_every_tracked_test_file_is_gated`, and `test_allow_corpus_ignores_scratch_dispatch_files` (197 passed across those five files)

**Rationale**: deferred by review-close

### [deferred] 2026-10-13T10:25:13Z

**Decision**: test_allow_corpus_ignores_scratch_dispatch_files is tautological: it writes the scratch file into tmp_path, which neither the current nor the old _allow_corpus() globs, so the second assert cannot differ from the first. The fail-first replay confirms it passes at base. Plant the file where _allow_corpus reads it (or monkeypatch the corpus directory) and assert the committed fixtures list.

**Rationale**: rework cap reached with this finding unresolved

### [deferred] 2026-10-13T10:25:13Z

**Decision**: state-schema.md documents CLI invocations that do not exist: `autopilot group-rework <state.json>` and `autopilot review-stage <state.json> <review-file>`. The real parsers take `group-rework --findings <path>` and `review-stage --cycle-id --gate-command [--state ...]`. test_doc_contract goes green on a false doc.

**Rationale**: rework cap reached with this finding unresolved

### [deferred] 2026-10-13T10:25:13Z

**Decision**: Prior R1 only half resolved: the new comment in dev/bin/release-checks repeats the scratch-replay path literally, so the plain `path not in text` pin passes whether or not UNGATED lists it. The UNGATED entry is dead again. Reword the comment, or pin that every UNGATED path is absent from the script text.

**Rationale**: rework cap reached with this finding unresolved

### [deferred] 2026-10-13T10:25:13Z

**Decision**: The gate pin accepts any substring hit in the script text, so a test path named only in a comment or echo counts as gated, and _dir_is_bare_target treats a bare directory word in a comment as gating every test under it. Match only inside run_pytest/run_harness argument lines.

**Rationale**: rework cap reached with this finding unresolved

### [deferred] 2026-10-13T10:25:13Z

**Decision**: Doubt lens on the same defect as the high above: nothing redirects corpus discovery to tmp_path, so restoring the original scratch-reading _allow_corpus can still pass in a clean checkout. Monkeypatch the corpus location and verify failure against the original implementation.

**Rationale**: rework cap reached with this finding unresolved

### [deferred] 2026-10-13T10:25:13Z

**Decision**: The PRD asks the task report to state the gate's new wall time; it is absent. Blake measured 5m08s on a sandboxed host against the ~220s baseline, unconfirmed. Bob asks for /usr/bin/time -p bash dev/bin/release-checks at base a15cbe13 and at e0101faa, with both elapsed times and the delta recorded.

**Rationale**: rework cap reached with this finding unresolved

### [deferred] 2026-10-13T10:25:13Z

**Decision**: The CHANGELOG packet-7 bullet is not the observed-split form the PRD asks for (denies X, still allows Y); it says the four phrasings now correctly deny. Blake confirmed the claim is true at HEAD, so this is a form deviation only.

**Rationale**: rework cap reached with this finding unresolved
