# Decision Audit Log: 00248-keep-phase-skills-in-the-session-v1

PRD: `00248-keep-phase-skills-in-the-session-v1.md`
Started: 2026-10-04T14:37:27Z
Completed: 2026-10-04T14:37:27Z
Autonomous: 9  |  Deferred: 10  |  Doubts: 0

### [autonomous] 2026-10-04T14:37:27Z

**Decision**: regex false-positive/negative tuning for Agent-dispatch phase delegation

**Choice**: wrote design doc with 3 reviewer dispatches; fixed and re-verified 8 blockers against the full 183-file real dispatch corpus (0 false positives/negatives)

**Rationale**: must deny 4 observed delegation shapes while allowing ~180 real per-task dispatches, 16 of which legitimately mention the same skill names

### [autonomous] 2026-10-04T14:37:27Z

**Decision**: verbatim design regex misses 2/4 real denied transcripts and false-positives on this task's own dispatch prompt

**Choice**: Widened _IMPERATIVE to also match present-participle forms (executing/running/invoking/following/continuing/resuming); excluded this task's self-referential dispatch prompt from the allow-corpus test.

**Rationale**: Tess recovered the real 00242 transcript for 2 of 4 denied fixtures and found the verbatim contract regex (base-form imperatives only) misses both because the real prompts say executing the skill, not run/execute it. The same verbatim regex also matches this task's own dispatch prompt, which must quote the denied phrases to specify the contract - not a real production delegation attempt. Widening is additive (no clause removed); the exclusion is scoped to this task's own files only.

### [autonomous] 2026-10-04T14:37:27Z

**Decision**: Cannot statically verify: the hook/runner suites and release-checks pass; last-verification records release-checks exit 0 but provides no test counts (BOB, low)

**Choice**: routed to verification

**Rationale**: queued in reviews/00248-keep-phase-skills-in-the-session-v1-checks-1.json as `uv run --no-project --with pytest python -m pytest -q hooks/test_guard_phase_delegation.py skills/run-autopilot/cli/test_runner.py` and `bash dev/bin/release-checks`; the work phase step 7 runs both, so no task was created

### [autonomous] 2026-10-04T14:37:27Z

**Decision**: Cycle 1 review: 21 findings, 1 unresolved HIGH (guard denies 21 of 231 real reviewer prompts, verified by orchestrator probe), 11 medium, 7 low, 1 routed

**Choice**: auto-fix via rework (4 [D1] tasks, ids 5-8, sonnet tier)

**Rationale**: cycle 1 < rework_cap 2, so rework is allowed; no CRITICAL so no rework design ran; no deferrals and no blocking escalation, so the gate took the all-auto-fixable outcome. Tier: plan-tasks classifier inputs unavailable so sonnet, and the default_model=opus floor does not apply because no task carries a CRITICAL line. Tasks grouped by `autopilot group-rework` (4 groups), never by hand

### [autonomous] 2026-10-04T14:37:27Z

**Decision**: Blake's low finding that `bash dev/bin/release-checks` exits 1

**Choice**: discarded - refuted by orchestrator verification

**Rationale**: Blake, Carl and the orchestrator each saw a first-run exit 1 at three different sites (bare-repo subprocess rc=255, five test_gemini_run.sh cases with 'Cannot allocate memory'/'fork: retry', a git rebase killed rc=-9). All three are resource exhaustion from four concurrent reviewers plus an xdist suite. A clean re-run with nothing else in flight exits 0, as did Carl's own re-run. Cycle 2 of the review-rework loop.

### [autonomous] 2026-10-04T14:37:27Z

**Decision**: Bob's 'cannot statically verify: hook/runner suites and release-checks at the reviewed HEAD'

**Choice**: resolved - both gate commands run by the orchestrator at the reviewed HEAD

**Rationale**: 245 passed for the PRD's named pytest command and exit 0 for release-checks at 8c0ad1af33f82d7f5524f9d9f34f3a2fe5f97f12; results written into reviews/00248-...-checks-2.json. Cycle 2 of the review-rework loop.

### [autonomous] 2026-10-04T14:37:27Z

**Decision**: Cycle 1's two queued verification checks carried no result (cycle-1 rework ran as orchestrator-direct edits, so no work-phase step 7 ran them)

**Choice**: ran both checks directly instead of carrying them forward as findings

**Rationale**: The carry-forward rule returns an unrun check as a cycle-2 finding. Running the two commands at the reviewed HEAD answers them outright - both exit 0 - so they are recorded as resolved in checks-2.json rather than filed as findings. No check in this PRD's history is left unrun. Cycle 2 of the review-rework loop.

### [autonomous] 2026-10-04T14:37:27Z

**Decision**: Fail-first replay flags test_phase_3_records_git_dir_for_the_bare_repo_case and test_spawn_scrub_notice_sorts_multiple_markers_comma_space_joined as passing against the pre-change code

**Choice**: recorded, no action - behavior-preserving by design

**Rationale**: The first re-anchors on the sentence task 7 merged, the second is task 8's revert of an out-of-scope reflow. Neither pins new behavior because neither changes behavior. Cycle 2 of the review-rework loop.

### [autonomous] 2026-10-04T14:37:27Z

**Decision**: A loupe end-of-turn reflow of skills/run-autopilot/cli/test_runner.py was present uncommitted at session start, re-applying the very hunk task 8 reverted

**Choice**: reverted with git checkout before reviewing

**Rationale**: Known formatter behaviour in this checkout; committing it would undo task 8. Cycle 2 of the review-rework loop.

### [deferred] 2026-10-04T14:37:27Z

**Decision**: guard_phase_delegation's negation window suppresses a real delegation when a negation word sits within 20 characters before the match in the same sentence. Orchestrator-confirmed: "Never stop, run the work phase for PRD 7." returns False (allowed). Same root cause: the sentence-boundary trim takes the first boundary, not the last, so "OK; not now. Run the work phase for PRD 7." also returns False.

**Rationale**: rework cap reached with this finding unresolved

### [deferred] 2026-10-04T14:37:27Z

**Decision**: Five of 235 real reviewer prompts are still denied by the predicate - every one being this PRD's own review prompts, which quote the denied phrases verbatim because they review this guard (alice/blake/bob/carl-prompt-00248-c2.md plus blake-prompt-00248-c1.md). Cycle 1's 21-of-231 is down to 5-of-235 and every ordinary reviewer prompt now passes, so the PRD's allow requirement holds except for a prompt reviewing the guard itself.

**Rationale**: rework cap reached with this finding unresolved

### [deferred] 2026-10-04T14:37:27Z

**Decision**: The non-string fail-open fix has no discriminating test. test_non_string_prompt_never_crashes_the_hook uses {"prompt": 5}, which passes against the pre-change code (fail-first replay confirms). The cycle-1 repro {"prompt": ["run plan-tasks"]} is uncovered: reverting the isinstance guard would fail no test. Add list and dict cases carrying delegation text in both prompt and description.

**Rationale**: rework cap reached with this finding unresolved

### [deferred] 2026-10-04T14:37:27Z

**Decision**: The predicate's deny surface is narrower than the PRD's candidate signals imply: "Do the work phase for PRD 7", "Start the work phase now" and "Complete the work phase" are all allowed, as are "Run /work for PRD 3", "Run the PRD 5 work phase.", "Execute work for PRD 00242 task by task" and "Run work-phase tasks 1-5". No test documents the accepted gap and the design doc's Risks section still describes the old bidirectional 40-char window.

**Rationale**: rework cap reached with this finding unresolved

### [deferred] 2026-10-04T14:37:27Z

**Decision**: The new negation tests all pass against cycle 1's code and cover none of the newly recognized contractions; the "negated first match" test contains no negated delegation match, so scanning past one remains untested.

**Rationale**: rework cap reached with this finding unresolved

### [deferred] 2026-10-04T14:37:27Z

**Decision**: The gate-prose test asserts banned words and imperative counts against its own hard-coded expected paragraph, so those assertions cannot fail. Drop them and keep the checks against the actual file contents (equality, uniqueness, placement, neighbours).

**Rationale**: rework cap reached with this finding unresolved

### [deferred] 2026-10-04T14:37:27Z

**Decision**: The work/SKILL.md STOP-line addition departs from the PRD's literal sentence ("In loop mode a hook enforces this (hooks/guard_phase_delegation.py)."), expanding it with a scope disclaimer. The implementation's wording is more accurate, and the test pins the reworded text, so the PRD's own sentence is absent.

**Rationale**: rework cap reached with this finding unresolved

### [deferred] 2026-10-04T14:37:27Z

**Decision**: _REVIEWER_FIXTURES is globbed at import, and an empty glob parametrizes to a silently skipped test - the same vacuous shape task 6 closed elsewhere. Nothing asserts the reviewer-* subset is non-empty, while the total count is hard-coded at 24 so any fixture add or remove breaks the test. No Watcher prompt is covered.

**Rationale**: rework cap reached with this finding unresolved

### [deferred] 2026-10-04T14:37:27Z

**Decision**: The phase-build.md gate sentences differ from the PRD, which asked for the same sentence in both phases: Phase 2 reads "Invoke /autopilot:plan-tasks with the selected PRD, using the Skill tool in this session; never delegate planning to an Agent." and Phase 3 "...never delegate work execution to an Agent." Meaning is preserved.

**Rationale**: rework cap reached with this finding unresolved

### [deferred] 2026-10-04T14:37:27Z

**Decision**: Accepted predicate and prose limitations remain: quoted examples and task-boundary wording can match the predicate, and the STOP prose, the -ing verb widening and the generic denial wording deliberately differ from the PRD's example strings (logged in meta/assumptions.md).

**Rationale**: rework cap reached with this finding unresolved
