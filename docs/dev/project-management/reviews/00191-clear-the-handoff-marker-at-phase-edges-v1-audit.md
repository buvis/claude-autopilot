# Decision Audit Log: 00191-clear-the-handoff-marker-at-phase-edges-v1

PRD: `00191-clear-the-handoff-marker-at-phase-edges-v1.md`
Started: 2026-09-14T20:29:12Z
Completed: 2026-09-14T20:29:12Z
Autonomous: 11  |  Deferred: 1  |  Doubts: 0

### [autonomous] 2026-09-14T20:29:12Z

**Decision**: _marker_task_id misparses a numeric legacy marker (json.loads("7") -> int) as no task, so a same-task legacy marker is rewritten

**Choice**: auto-fix (tail sweep, task 5)

**Rationale**: cycle 1 converged (no C/H); 3/4 consensus, Alice reproduced _marker_task_id("7") == "" by running the module; task ids are integer strings in production; mechanical 2-line fix plus a pinning test

### [autonomous] 2026-09-14T20:29:12Z

**Decision**: stale-marker stderr note reads from phase {p}, expected {state.phase} instead of the PRD literal from phase <p> removed

**Choice**: auto-fix (tail sweep, task 5)

**Rationale**: cycle 1; spec deviation on an exact PRD string, 3/4 consensus (Blake rated it Low); prose edit plus pin the full literal

### [autonomous] 2026-09-14T20:29:12Z

**Decision**: test_dispatch_prose.py grew 756 -> 998 lines, newly over the 800-line cap; check_style_limits.py --diff flags it (task 3 style gate recorded clean in error)

**Choice**: auto-fix (tail sweep, task 5): split the task-boundary tests into test_task_boundary_handoff_prose.py

**Rationale**: cycle 1; 3/4 consensus, orchestrator re-ran check_style_limits.py (exit 1, FILE 998 lines); release-checks does not enumerate this file so the split has no gate impact

### [autonomous] 2026-09-14T20:29:12Z

**Decision**: consumer prose validates JSON field presence, not string types; PRD says invalid field shapes are malformed

**Choice**: auto-fix (tail sweep, task 5)

**Rationale**: cycle 1; 2/4 consensus (Bob, Carl - Carl read Bob output, so effectively one independent voice); orchestrator confirmed step 3b names no type; prose plus pin

### [autonomous] 2026-09-14T20:29:12Z

**Decision**: prose tests do not pin next_phase assignment, telemetry --phase, or malformed removal; leave row hardcodes --site build

**Choice**: auto-fix (tail sweep, task 5)

**Rationale**: cycle 1; Bob+Carl on the test gap, Alice on --site; orchestrator read test_dispatch_prose.py 770-998 and confirmed no test names next_phase or --site; subagent-dispatch.md says site is the gate that writes the row, so the review gate handoff must not stamp build

### [autonomous] 2026-09-14T20:29:12Z

**Decision**: _parse_iso_utc normalizes naive and non-UTC stamps, masking the UTC ISO-8601 contract

**Choice**: auto-fix (tail sweep, task 5)

**Rationale**: cycle 1; 2/4 (Bob, Carl); one-assertion strictness fix in a test helper

### [autonomous] 2026-09-14T20:29:12Z

**Decision**: do_stall clears markers in the supplied autopilot_dir, not state_path.parent as the PRD words it

**Choice**: auto-fix (tail sweep, task 5)

**Rationale**: cycle 1; 1/4 (Bob); park accepts --autopilot-dir so the dirs can differ; one-token fix plus a differing-dir test

### [autonomous] 2026-09-14T20:29:12Z

**Decision**: lifecycle tests never assert the reported path on stderr, nor same-phase resume or commit-write failure preserving markers

**Choice**: auto-fix (tail sweep, task 5)

**Rationale**: cycle 1; 1/4 (Bob); orchestrator read test_handoff.py 287-302: no stderr path assertion; additive tests only

### [autonomous] 2026-09-14T20:29:12Z

**Decision**: handoff.py repeats the absence/OSError contract in module and function docstrings

**Choice**: auto-fix (tail sweep, task 5)

**Rationale**: cycle 1; 1/4 (Bob, de-slop lens); trivial trim

### [autonomous] 2026-09-14T20:29:12Z

**Decision**: [MECH] fail-first replay reports 12 touched hook tests passing against base, naming test_handoff_marker_empty_or_malformed_is_replaced_with_json and test_handoff_marker_task_whose_id_prefixes_the_marked_one_is_overwritten; Bob asked to verify

**Choice**: discarded (ledger: refuted)

**Rationale**: cycle 1; Alice rebuilt the replay in a base worktree with HEAD test files overlaid and both named tests FAIL at base (12 failed, 48 passed in the hook file); the remaining passers are guards the PRD says to preserve (unreadable-state, review-phase, dangling symlink, no-ancestor), which pass at base by design. The script mis-scored subTest-carrying methods. Bob VERIFY item not queued: command shape (needs a worktree plus overlay, not one project command) and Alice already ran it

### [autonomous] 2026-09-14T20:29:12Z

**Decision**: Carl (gemini via copilot) read bob-output-00191-c1.txt before emitting his findings; his 6 Medium lines mirror Bob

**Choice**: logged; consensus for Bob+Carl rows read as one independent voice

**Rationale**: cycle 1; reviewer independence caveat recorded in the review file; no roster change (the CLI runners share dev/local/tmp)

### [deferred] 2026-09-14T20:29:12Z

**Decision**: inherited size violations: record_defer 54 lines, do_park 61, _bump_and_check_tripwire 62 (50-line rule); cli/__main__.py 1099 lines and test_autopilot_context_cap_hook.py 958 -> 1210 lines (800-line rule, both already over before this PRD)

**Choice**: deferred

**Rationale**: pre-existing before 68c624d; the surgical-changes rule keeps adjacent code untouched and the PRD names none of these functions; the hook test file grew by ~250 lines while already over the cap - a split belongs to a hygiene PRD, not this fix
