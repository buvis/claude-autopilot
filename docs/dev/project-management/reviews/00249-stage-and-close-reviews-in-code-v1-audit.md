# Decision Audit Log: 00249-stage-and-close-reviews-in-code-v1

PRD: `00249-stage-and-close-reviews-in-code-v1.md`
Started: 2026-10-04T20:00:24Z
Completed: 2026-10-04T20:00:24Z
Autonomous: 9  |  Deferred: 22  |  Doubts: 0

### [autonomous] 2026-10-04T20:00:24Z

**Decision**: render_roster task 3 implemented Bob's Eve-section appendage as firing only when eve is absent from roster; existing SKILL.md/bob.md/agent-invocation.md say Bob carries the doubt lens (and its Eve sections) every cycle regardless of whether Eve also joins as a 5th lens under the fable doubt_reviewer

**Choice**: left for the PRD review phase to confirm/fix rather than blocking task completion

**Rationale**: surfaced by the task-3 implementor as a judgment call between two readings of the design doc vs. existing prose

### [autonomous] 2026-10-04T20:00:24Z

**Decision**: task 5 registered autopilot review-stage/review-close, which turns test_doc_contract.py red until review-work-completion/SKILL.md and phase-review.md name both verbs in prose (tasks 6 and 7 of this PRD); also review_stage.stage()'s settled_ledger parameter has no CLI flag yet (--settled-ledger missing)

**Choice**: left for tasks 6/7 to close the doc-contract gap by naming both verbs; settled_ledger flag gap flagged for the PRD review phase, not fixed now

**Rationale**: sequencing artifact of per-task TDD on an interdependent PRD; the full suite is expected red until Phase 2 tasks land

### [autonomous] 2026-10-04T20:00:24Z

**Decision**: task 7's phase-review.md rewrite makes test_rework_groups_prose.py (3 tests) and test_design_rework_prose.py::test_dispatch_rework_designs_critical_rework_once_before_any_task_add/test_loop_mode_hands_off_after_task_add_before_work red, since they pin the old group-rework/task-add literal text this PRD intentionally replaces; also flags that the design doc's classification-mapping table (every CRITICAL -> defer) conflicts with PRD 00194's existing rule that every unresolved CRITICAL becomes a fix task, and that close() does not write the Design/Contract body or apply the default_model floor for CRITICAL tasks (phase-review.md now does both by hand after the call)

**Choice**: will update the two stale prose-test files to match the new review-close-based text before closing out the PRD's build phase, per the Phase 2 exit criteria (bash dev/bin/release-checks exits 0); the 00194/default_model gaps are accepted as phase-review.md-side compensation, to be confirmed by the review phase

**Rationale**: the per-task test list in planning named only test_phase_review_closes_via_review_close and test_review_resume_prose.py; the wider regression surfaced only once the edit landed, same class of sequencing gap as the doc_contract gap from task 5

### [autonomous] 2026-10-04T20:00:24Z

**Decision**: task 6's SKILL.md rewrite (deleting step 7) breaks test_design_rework_prose.py (collection error, anchor text gone) and 2 cases in test_verify_queue_prose.py (pin step-7 sentences); test_agent_registry.py has 1 pre-existing failure (unrelated to task 6) now surfaced by task 3's blake golden fixture needing a skip-list entry. Task 6 also flagged 5 design/implementation mismatches: review-stage has no --settled-ledger/--prior-findings flags so the model still hand-edits prompts for those; review-prd-{id}.md (carrying the design doc) feeds Blake/Eve, breaking PRD-only blind/doubt; render_roster gives Bob eve.md sections only when eve is absent from roster (same bug flagged after task 3) risking Bob's D{n} lines when Eve also runs; no ui lens key so Carl runs never stamp it; --state mode has no design-doc-path fallback and no engram retry

**Choice**: left all of these for the PRD's review phase (Alice/Blake/Bob/Carl, review-rework loop) to triage and fix via rework cycles rather than fixing unplanned scope myself mid-build; the build phase's own 7 planned tasks are now all complete with their named acceptance criteria passing

**Rationale**: fixing every mismatch now would expand scope well beyond the planned 7 tasks; the review-rework loop exists exactly to catch and fix gaps like these before the PRD closes

### [autonomous] 2026-10-04T20:00:24Z

**Decision**: Blake: module signatures, CLI flags and the review-close --review-file interface differ from the PRD module sketches

**Choice**: discarded

**Rationale**: cycle 1 decision gate: the reviewed design doc is the authority for the HOW and chose these shapes deliberately; the PRD Structural Decomposition lists sketches, not binding signatures. The one real sub-gap (close() writes no autonomous_decisions) was split into the [D1] __main__.py rework task.

### [autonomous] 2026-10-04T20:00:24Z

**Decision**: Blake: review-work-completion/SKILL.md step 6 does not end with an autopilot review-close call as the PRD Phase 2 task text says

**Choice**: discarded

**Rationale**: cycle 1 decision gate: the design doc moved the call to the decision gate on purpose (the skill has no state authority over task creation), and prose tests pin it in phase-review.md, so the behavior exists in one place rather than two

### [autonomous] 2026-10-04T20:00:24Z

**Decision**: Carl reported bash dev/bin/release-checks as SUMMARY: 6 passed, 20 failed in the runner recursion guard group

**Choice**: discarded

**Rationale**: cycle 1 decision gate: contradicts a measured fact. Carl ran with COPILOT_CLI, CODEX_SESSION_ID and AUTOPILOT_DISPATCH_DEPTH set, so every codex-wrapper assertion hit the nested-dispatch refusal (exit 3). This orchestrator ran the same script in a clean environment this cycle: every group passed (2621 passed, 0 failed, 0 skipped).

### [autonomous] 2026-10-04T20:00:24Z

**Decision**: Bob VERIFY: run the four new review-verb test files, then bash dev/bin/release-checks

**Choice**: routed to verification

**Rationale**: cycle 1 decision gate: queued in 00249-stage-and-close-reviews-in-code-v1-checks-1.json as the single pytest command (uv run --no-project --with pytest python -m pytest skills/run-autopilot/cli/test_verification.py skills/run-autopilot/cli/test_review_stage.py skills/run-autopilot/cli/test_review_close.py skills/run-autopilot/cli/test_cli_review_verbs.py -q), already run this cycle with exit 0 (66 passed). The release-checks half was not queued (command shape: the VERIFY text chains two commands) and was run directly this cycle instead.

### [autonomous] 2026-10-04T20:00:24Z

**Decision**: 12 high and 7 medium findings chosen for rework; no CRITICAL raised, so no rework design ran

**Choice**: auto-fix via 4 [D1] rework tasks

**Rationale**: cycle 1 decision gate: autopilot group-rework produced 4 groups (skills/run-autopilot/cli/, dev/bin/release-checks, prose/CHANGELOG, test_rework_groups_prose.py); tasks 8-11 at sonnet, the classifier default, since the default_model opus floor applies only to a task carrying a CRITICAL line

### [deferred] 2026-10-04T20:00:24Z

**Decision**: Settled-ledger and prior-findings wiring exists in code (--settled-ledger / --prior-findings reach render_roster) but SKILL.md:216-218 and :248 still tell the model to hand-append both with the Edit tool, and the step 3 synopsis lists neither flag. Every cycle still falls back to the hand-editing this PRD removes.

**Rationale**: rework cap reached with this finding unresolved

### [deferred] 2026-10-04T20:00:24Z

**Decision**: run_gate is still 75 lines (over the 50-line limit) and still buffers all output through communicate(), so the output cap does not bound memory. Only the keep-tail fix landed from the cycle-1 finding.

**Rationale**: rework cap reached with this finding unresolved

### [deferred] 2026-10-04T20:00:24Z

**Decision**: The review-file format still omits the dispatch_rows: block review_close parses and lists only alice/bob/carl under agents:, so no model stamps the rows close() ends and Blake's blind and Eve's fable lenses are stamped running and never closed.

**Rationale**: rework cap reached with this finding unresolved

### [deferred] 2026-10-04T20:00:24Z

**Decision**: _eve_inputs still passes the merged run['prd'] (PRD plus design doc) to Eve, while only Blake gets the raw _prd_body slice. The doubt lens must stay PRD-only.

**Rationale**: rework cap reached with this finding unresolved

### [deferred] 2026-10-04T20:00:24Z

**Decision**: The gate's one-line summary reports check-block counts as passed tests (grep -c over its own echo lines), hardcodes zero skips, and emits nothing on failure. run_gate writes those counts to last-verification.json and a later cycle reuses them as real test counts: measured 25 against an actual 2564 this cycle.

**Rationale**: rework cap reached with this finding unresolved

### [deferred] 2026-10-04T20:00:24Z

**Decision**: reuse_verdict's docstring still requires an empty git status --porcelain although the code now ignores dirty store paths, and line[3:] on a porcelain rename record checks only the old path, so a staged rename out of the store reads as clean (fail-open).

**Rationale**: rework cap reached with this finding unresolved

### [deferred] 2026-10-04T20:00:24Z

**Decision**: review-close takes its findings from a separate --findings JSON the model writes, and gate.py never cross-checks that file against the review's consolidated table. The design doc's settled answer to the second-source-of-truth risk was 'the gate refusal is the cross-check', and that check does not exist, so the settled reason no longer holds.

**Rationale**: rework cap reached with this finding unresolved

### [deferred] 2026-10-04T20:00:24Z

**Decision**: _DISPATCH_OUTCOME maps an unavailable reviewer to --outcome 'failed', which is not in record_dispatch.OUTCOMES ('ok','timeout','killed','error','lost'), so the row-closing call exits 2 for every unavailable reviewer. Confirmed mechanically; the value should be 'error'.

**Rationale**: rework cap reached with this finding unresolved

### [deferred] 2026-10-04T20:00:24Z

**Decision**: run['doubt'] is 'eve' not in roster, so Bob's doubt appendix (lenses, FIX/VERIFY/KNOWN buckets, D1-D5) is dropped exactly when Eve is on the roster - the one case where agent-invocation.md sends Eve's failure fallback to Bob's assembled prompt. The fallback therefore carries no doubt lens. Cycle-1 F4, untouched.

**Rationale**: rework cap reached with this finding unresolved

### [deferred] 2026-10-04T20:00:24Z

**Decision**: review_stage.py is 823 lines, over the 800-line file limit, after the rework added helpers without extracting anything.

**Rationale**: rework cap reached with this finding unresolved

### [deferred] 2026-10-04T20:00:24Z

**Decision**: The tail-sweep prose test still hedges with '"at most 4" in section or "caps at 4" in section' while phase-review.md carries only 'at most 4, never zero'. The floor split landed, but the cap assert still passes against the pre-change prose and the fail-first replay still reports the test passing at base.

**Rationale**: rework cap reached with this finding unresolved

### [deferred] 2026-10-04T20:00:24Z

**Decision**: test_main_review_close_validation.py is absent from the review-verbs block, so the release gate never runs it. Run directly this cycle: 7 passed.

**Rationale**: rework cap reached with this finding unresolved

### [deferred] 2026-10-04T20:00:24Z

**Decision**: The cycle-1 rework behaviours are mostly unpinned: nothing tests autonomous_decisions being written or its emoji-to-word severity map, 'disabled' mapping to 'skipped', the per-status --outcome mapping (the one assertion still expects 'ok'), the three new CLI flags, or the CLI rejecting an unknown classification with exit 2.

**Rationale**: rework cap reached with this finding unresolved

### [deferred] 2026-10-04T20:00:24Z

**Decision**: The stricter found_by validation (a list of strings) contradicts the tail-sweep prose, which says found_by is copied verbatim from the table, where it is the string 'ALICE, BOB'. Following the prose now exits 2, and the stderr message names neither the allowed values nor the emoji severities.

**Rationale**: rework cap reached with this finding unresolved

### [deferred] 2026-10-04T20:00:24Z

**Decision**: The new 'skipped' review_lenses value is undocumented: state-schema.md and tracon/model.py define only running|done|failed.

**Rationale**: rework cap reached with this finding unresolved

### [deferred] 2026-10-04T20:00:24Z

**Decision**: review-stage runs the gate itself on a stale verdict through a mandatory --gate-command, so a long gate runs inside the staging call, and a timed-out gate emits a zero-count Tests: line that still satisfies the gate's own pattern.

**Rationale**: rework cap reached with this finding unresolved

### [deferred] 2026-10-04T20:00:24Z

**Decision**: Doubt verdicts are still extracted globally without source tags, overwriting reviewer-attributed verdicts that dual-reviewer reporting needs.

**Rationale**: rework cap reached with this finding unresolved

### [deferred] 2026-10-04T20:00:24Z

**Decision**: _add_decisions records every fix row as action 'auto-fixed' with reason 'fixed by review-close' at the moment the rework task is queued, before any implementor runs, so the audit claims a fix that may never land.

**Rationale**: rework cap reached with this finding unresolved

### [deferred] 2026-10-04T20:00:24Z

**Decision**: Unrelated reformatting churn (trailing commas, re-wrapped calls) in functions the PRD does not touch, which buries the real changes.

**Rationale**: rework cap reached with this finding unresolved

### [deferred] 2026-10-04T20:00:24Z

**Decision**: On a tail-sweep call close() still returns a populated lenses_closed although _set_lens_state applied none of it, misreporting the result.

**Rationale**: rework cap reached with this finding unresolved

### [deferred] 2026-10-04T20:00:24Z

**Decision**: last-verification.json is written with a plain write_text, so a crash mid-write leaves a truncated record. It parses to None and reads as stale, so the failure is safe but not atomic.

**Rationale**: rework cap reached with this finding unresolved

### [deferred] 2026-10-04T20:00:24Z

**Decision**: Fail-first replay: four touched tests pass against the base - three accept-valid-input guards and one CLI forwarding test. Bob justifies these as regression guards outside the fail-first requirement for new behavior.

**Rationale**: rework cap reached with this finding unresolved
