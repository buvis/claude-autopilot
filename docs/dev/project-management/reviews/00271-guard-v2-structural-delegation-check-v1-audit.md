# Decision Audit Log: 00271-guard-v2-structural-delegation-check-v1

PRD: `00271-guard-v2-structural-delegation-check-v1.md`
Started: 2026-10-12T22:19:02Z
Completed: 2026-10-12T22:19:02Z
Autonomous: 13  |  Deferred: 16  |  Doubts: 0

### [autonomous] 2026-10-12T22:19:02Z

**Decision**: Cycle 1 review raised 23 findings; R2,R3,R4,R5,R6,R8,R9,R12,R13,R14,R15,M1 routed to rework fixes

**Choice**: auto-fix

**Rationale**: All twelve are mechanical or additive: linear-time rescans, distinct-id/path dedup, clause-bound negation, first-token slash-command check, replay exit-code discrimination, a test-file split and two added test cases. No signature, schema or contract change, so no escalation and no operator decision needed.

### [autonomous] 2026-10-12T22:19:02Z

**Decision**: `_PATH_TOKEN = \S*/\S+\.\w+` is quadratic, which breaks the PRD requirement "every regex runs in linear time" and the per-MB bound. `_is_scoped` runs `finditer` over the whole field once any phase candidate exists. A prompt `"Run the work phase for PRD 7. " + "a" * N` takes 0.29 s at N=20k, 0.98 s at 40k and 3.76 s at 80k, so the 5 s hook timeout is reached near 95 KB (a base64 blob or minified JSON would do it). Many candidates in one huge clause also scale quadratically (`'about the work phase and ' * 160000`: 4.5 s, and 0.375 s/MB at 1 MB, above the 0.3 budget). That path slices `text[end:clause_end]` per candidate (hooks/guard_phase_delegation.py:365) and lists every word in the clause per candidate (hooks/guard_phase_delegation.py:367 and :389). Replace the path regex with a linear token scan (split on whitespace, then test each token for `/` and a suffix) and bound the per-candidate clause slices. `test_guard_time_per_mb_stays_under_the_baseline` uses only prompts with zero candidates and spaces, so it cannot see this. Add a long-unbroken-token case and a many-mentions case.

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-10-12T22:19:02Z

**Decision**: `_negated` materializes every preceding word before slicing the last five; repeated negated, strongly anchored candidates in one clause therefore cause quadratic work. Precompute word positions once and use binary searches or implement the specified backward walk.

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-10-12T22:19:02Z

**Decision**: File scoping counts occurrences instead of distinct paths and accepts root-relative `prds/wip/00300.md` as an ordinary file. Thus a scoped-looking phase sentence naming one store path is allowed. Deduplicate paths and exclude both `prds/` and `/prds/` segments.

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-10-12T22:19:02Z

**Decision**: Merged away by the consolidator, restored verbatim: task scoping counts occurrences instead of distinct IDs and discards range matches before deciding scope. Repeating one task id incorrectly removes scope, and a mixed id-plus-range sentence incorrectly gains it. Collect distinct IDs and reject task-based scope if ANY occurrence has range adjacency.

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-10-12T22:19:02Z

**Decision**: Merged away by the consolidator, restored verbatim: the SKILL.md follow phrase ignores a negation sitting before the verb. `_ordered_to_follow` checks only the verb-object gap while `_negated` checks only before the path, so `Read skills/work/SKILL.md; you must never follow it` is denied. A false-deny path.

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-10-12T22:19:02Z

**Decision**: Merged away by the consolidator, restored verbatim: the bare slash-command check uses `\b` after the skill name, not "first token is", so a longer hyphenated token beginning with the command name is always refused. The PRD says the first token must be the command.

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-10-12T22:19:02Z

**Decision**: Fixed character slices silently narrow unbounded contracts: the 16-character skill-suffix probe misses longer whitespace, and 24-character task-range probes miss longer whitespace between range words. Match against the original string using positions and explicit boundaries instead of arbitrary character caps.

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-10-12T22:19:02Z

**Decision**: Merged away by the consolidator, restored verbatim: the replay treats every non-zero subprocess exit as a policy denial. A guard crashing with exit 1 satisfies the pinned-deny checks and can produce exit 0 for an all-`other` corpus. Test for exit 2 and report any other non-zero exit as an execution error with stderr.

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-10-12T22:19:02Z

**Decision**: The supplied fail-first result says the lone-surrogate denial test passes at base, so it does not demonstrate the targeted subprocess encoding failure. Add a strict-UTF-8 subprocess case asserting exit 2 and the lifecycle message, then confirm failure at base.

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-10-12T22:19:02Z

**Decision**: `hooks/test_guard_phase_delegation_structure.py` is 804 lines, over the 800-line limit. Split off the normalization sweep (`test_normalize_*`, lines 224-330) into its own module, and register it in `dev/bin/release-checks`.

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-10-12T22:19:02Z

**Decision**: [D1] task 11 carries seven findings (R2, R5, R6, R8, R12, R13, R14) that narrow a contract-pinned regex predicate with 564 tests behind it and must also hold a measured per-MB linear-time budget

**Choice**: tier raised sonnet -> opus for task 11 only (tasks 12-14 stay sonnet)

**Rationale**: plan-tasks tier classifier: multi-finding predicate narrowing plus a perf bound in one file is opus-shaped work; no CRITICAL row reached this cycle, so no default_model floor applies and no rework design was run

### [autonomous] 2026-10-12T22:19:02Z

**Decision**: M1: dev/bin/test_replay_delegation_guard.py test_missing_guard_cannot_report_an_allowed_run passes against the pre-change code (accepts any non-zero exit, so the explicit return 2 is unpinned)

**Choice**: folded into task 12 (R15) instead of its own row

**Rationale**: review-close refused the M1 row as absent from the consolidated findings (findings_mismatch on a mech-check row); R15's fix instruction already requires testing for exit 2 specifically, which is the same assertion

### [deferred] 2026-10-12T22:19:02Z

**Decision**: R1: live replay exits 1 — the pinned deny id toolu_01Ku4TbcQoeik6ZLf5XkkAuD buckets per-task, so its correct refusal trips the contract's own per-task-refusal clause; PRD success metric 2 is unreachable as specified

**Choice**: defer-to-batch-end

**Rationale**: settled deferral: contract conflict needing a design-doc change (batch deferred record type contract-conflict); re-raised by Alice, Blake and Bob in cycle 1

### [deferred] 2026-10-12T22:19:02Z

**Decision**: R7: the recorded live replay refuses six legitimate per-task dispatches, each because a phase name sits inside a longer quoted run (citation, not an order)

**Choice**: defer-to-batch-end

**Rationale**: settled deferral: a quoted-citation rule is a new anchoring concept in a contract-pinned predicate with 564 tests behind it (batch deferred record type guard-false-positives)

### [deferred] 2026-10-12T22:19:02Z

**Decision**: R10: _PHASE_BARE lookbehind carries an extra ':' the PRD anchor text does not (hooks/guard_phase_delegation.py:98)

**Choice**: defer-to-batch-end

**Rationale**: settled deferral: harmless today because the autopilot: form covers the prefixed case

### [deferred] 2026-10-12T22:19:02Z

**Decision**: R11: _PRD_PATH_TAIL anchor is load-bearing for a PRD-required deny but is absent from the PRD anchor list (hooks/guard_phase_delegation.py:120)

**Choice**: defer-to-batch-end

**Rationale**: settled deferral: justified small addition needed to satisfy a required deny; spec text does not produce it

### [deferred] 2026-10-12T22:19:02Z

**Decision**: M2-M8: touched tests pass against the pre-change code across the guard, dispatch, narrowing, structure, leave-marker and read_input test files

**Choice**: defer-to-batch-end

**Rationale**: settled deferral: behavior-preserving allow-path and still-checked assertions plus the shared stdin sweep; M2 discarded as a subtest reporting artifact

### [deferred] 2026-10-12T22:19:02Z

**Decision**: R4: CHANGELOG.md keeps the task-1 normalization line beside the new guard line, so one entry is redundant

**Choice**: defer-to-batch-end

**Rationale**: settled deferral: the contracted three-line block overlapped lines tasks 3 and 4 had already landed (batch deferred record type assumed-ambiguity); resolved to one copy each

### [deferred] 2026-10-12T22:19:02Z

**Decision**: [cycle 2 R1] Quadratic work is still present for SKILL.md candidates, so prior R2 is only partly resolved and the PRD rule "every regex runs in linear time" is still unmet. `_ordered_to_follow` finds the sentence end with `next((s for s in sentences if s >= end), len(text))`, which walks the sentence list from index 0 for each SKILL.md candidate. 680 KB of repeated `work/SKILL.md.` sentences takes 5.7 s, past the 5 s hook timeout, so the hook fails open. Replace the `next(...)` with `bisect_left(sentences, end)` and add a many-SKILL.md-mentions linearity case.

**Rationale**: rework cap reached with this finding unresolved

### [deferred] 2026-10-12T22:19:02Z

**Decision**: [cycle 2 R2] The rework for prior R12 introduced a false-allow: the SKILL.md follow phrase is negated by any negation word in the five words before the verb, even across a clause boundary. `_ordered_to_follow` calls `_negated(text, end, match.start())`, so the floor is the path end, not the verb's clause start. `Read skills/work/SKILL.md, do not stop, then follow it for every task.` is allowed. Use `max(end, start of the verb's clause)` as the floor.

**Rationale**: rework cap reached with this finding unresolved

### [deferred] 2026-10-12T22:19:02Z

**Decision**: [cycle 2 R3] Prior R4 is not resolved. CHANGELOG.md line 18 still restates the normalization beside the new guard line at line 30, and the new line 17 claims the guard "scans every field in linear time", which is false while R1 stands. The PRD asked for exactly three replacement lines and no other CHANGELOG edit.

**Rationale**: rework cap reached with this finding unresolved

### [deferred] 2026-10-12T22:19:02Z

**Decision**: [cycle 2 R4] The new SKILL.md negation test covers only the same-clause case, so nothing catches the cross-clause false-allow (R2) and nothing pins a many-SKILL.md-mentions linearity case.

**Rationale**: rework cap reached with this finding unresolved

### [deferred] 2026-10-12T22:19:02Z

**Decision**: [cycle 2 R5] `test_blocks_lone_surrogate_path_over_a_real_subprocess_pipe` is green at base by its own comment, so it cannot pin the targeted encoding failure prior R9 asked for. Drop it or relabel it as coverage and record that no strict-UTF-8 subprocess case can fail at base, because `read_input` decodes with `errors="replace"`.

**Rationale**: rework cap reached with this finding unresolved

### [deferred] 2026-10-12T22:19:02Z

**Decision**: [cycle 2 R6] `(?![-\w])` does not enforce a whole first token: `/autopilot:work/helper task 3 only` still triggers unconditional denial. Require whitespace or end-of-input after the command and add slash- and dot-suffixed token tests.

**Rationale**: rework cap reached with this finding unresolved

### [deferred] 2026-10-12T22:19:02Z

**Decision**: [cycle 2 R7] Scope: the diff carries unrelated changes (the `skills/work/SKILL.md` ambiguity-check rewrite and its test, the `**work**` CHANGELOG line, the 00283 PRD edit, the new 00285 PRD). They come from the loop-efficiency audit, not this PRD, and look operator-intended.

**Rationale**: rework cap reached with this finding unresolved

### [deferred] 2026-10-12T22:19:02Z

**Decision**: [cycle 2 R8] The redundant normalization CHANGELOG entry remains beside the structural guard documentation (the same defect as R3, Bob's wording). Remove the duplicate entry while retaining the required verbatim description.

**Rationale**: rework cap reached with this finding unresolved

### [deferred] 2026-10-12T22:19:02Z

**Decision**: [cycle 2 R9] Task scoping keys ids by (sentence index, id) instead of distinct ids, so the same id repeated in a second sentence counts as two and does not scope. `Fix task 3. The hook must run the work phase for PRD 7. Report when task 3 passes.` is refused, and ordinary per-task prompts repeat their task number. The PRD says "exactly one distinct task id". Deduplicate ids alone.

**Rationale**: rework cap reached with this finding unresolved

### [deferred] 2026-10-12T22:19:02Z

**Decision**: [cycle 2 R10] Range-lead matching still truncates to 24 characters after trimming trailing whitespace, missing whitespace inside `starting ... at/with`: `Run the work phase for PRD 7, starting` + 40 spaces + `at task 3` incorrectly gains task scope. Recognize the range words without a character cap.

**Rationale**: rework cap reached with this finding unresolved
