# Decision Audit Log: 00283-loop-catchup-v1

PRD: `00283-loop-catchup-v1.md`
Started: 2026-10-13T23:00:12Z
Completed: 2026-10-13T23:00:12Z
Autonomous: 30  |  Deferred: 2  |  Doubts: 0

### [autonomous] 2026-10-13T23:00:12Z

**Decision**: 00283-loop-catchup-v1 design: loop_committer placement, UnicodeDecodeError fail-closed, probe() project-root derivation

**Choice**: placed loop_committer in cli/enter_io.py (not cli/loop.py) to avoid a loop.py<->enter.py circular import; commits_all_loop uses strict UTF-8 decode plus an explicit UnicodeDecodeError catch (not errors=replace, which risked a false match against a committer name itself containing U+FFFD); probe() derives autopilot_dir/project_root explicitly from state_path.parent

**Rationale**: 3 review dispatches (claude, claude-fallback for an outaged codex, codex) found and fixed 3 blockers in turn; 5 non-blockers and 2 questions recorded in the design doc Review log, left unfixed by design (engram/gh OSError-vs-stale-exit bucketing, non-ancestor-sha acceptance, PRD acceptance-command file-path question, test fixture author-identity note)

### [autonomous] 2026-10-13T23:00:12Z

**Decision**: Phase 1 prose contradicts `_catchup`: condition 1 claims a spent `force` reads delta on loop-only commits before falling through to conditions 2 and 3, but with tasks present `_catchup` checks `catchup_completed_at` freshness first and a stale cache returns `full`. The prose also never states the actual first-entry `force` rule (tasks empty, loop-only commits, freshness not consulted).

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-10-13T23:00:12Z

**Decision**: Phase 1 invokes `autopilot catchup-probe` without arguments, but the parser requires `--state`, so the documented call fails before probing. Use the existing state-path resolver for an optional argument and test that invocation.

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-10-13T23:00:12Z

**Decision**: The task specified a `# ponytail: process-wide env, the loop process commits nothing else` comment on the `os.environ` write, and it is missing.

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-10-13T23:00:12Z

**Decision**: `catchup_probe.main(argv)` is dead code: nothing calls it because `__main__.py` registers its own `_run_catchup_probe`, and no test covers it. Either drop `main` and its now-unused imports, or make `_run_catchup_probe` delegate to it.

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-10-13T23:00:12Z

**Decision**: The Phase 0 acceptance command for the committer stamp does not pass: `pytest ... test_loop.py -k committer` deselects all tests and exits 5, because the committer tests live in the new `test_loop_committer.py`.

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-10-13T23:00:12Z

**Decision**: `Loop._launch` assigns a local named `state`, shadowing the imported `state` module; loop.py:571 warns about this exact hazard and uses `current` instead. Rename the local to `current`.

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-10-13T23:00:12Z

**Decision**: `os.environ["GIT_COMMITTER_NAME"]` is set by `Loop._launch` and never restored, so every test that runs a Loop leaks the stamp into the pytest process and later git-committing tests inherit a committer name they did not ask for.

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-10-13T23:00:12Z

**Decision**: `test_git_commit_honors_the_committer_name_env_var` is tautological: it exercises only git's own env handling, never `_launch` or `loop_committer`, and the fail-first replay confirms it passes against the pre-change code. Delete it, or make it commit using the env `_launch` produced.

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-10-13T23:00:12Z

**Decision**: The `catchup-probe` CLI wiring is untested: `_add_catchup_probe`/`_run_catchup_probe` and the dispatch-table entry have no test, so a broken argument parse or JSON print would pass the suite, although the PRD pins "Stdout gets one JSON line".

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-10-13T23:00:12Z

**Decision**: `test_enter_decisions.py` is now 850 lines, over the 800-line cap, and it is not one of the files 00192 excluded. Move the new loop-only block to a new `test_enter_loop_only.py` and register it in the `[checks] enter` block of `dev/bin/release-checks`.

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-10-13T23:00:12Z

**Decision**: Nothing tests the `os.environ["GIT_COMMITTER_NAME"]` stamp on the loop process itself, which the spec requires for the loop's own store commits; the tests only check the env handed to the spawn, so deleting the `os.environ` line would break no test.

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-10-13T23:00:12Z

**Decision**: Tests assert only individual child-environment snapshots; parent-process stamping and replacement after a batch change remain unpinned. Add a two-launch test checking both environment sources, with cleanup restoring `os.environ`.

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-10-13T23:00:12Z

**Decision**: `probe()` has no docstring, though the design contract specifies one saying it returns `{"skip": [...]}` and writes `state.catchup_probe` unless the batch is already covered.

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-10-13T23:00:12Z

**Decision**: The `batch.catchup_completed_at` row still says delta needs `catchup_head_sha` to match current HEAD; it now also reads delta after loop-only commits.

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-10-13T23:00:12Z

**Decision**: In the first batch session `Loop._launch` can run before `state.json` has a `batch.id`, so those commits get `autopilot-loop/no-batch`, which `_catchup` does not recognise and the next entry reads full once per batch. Bounded and fails safe, but unmentioned in the PRD Risks section.

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-10-13T23:00:12Z

**Decision**: `probe` trusts the stored record's shape: a non-dict `catchup_probe`, or a dict missing `gh` or `engram`, raises `AttributeError` or `KeyError` in `probe` or `_skips` instead of re-probing.

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-10-13T23:00:12Z

**Decision**: The refreshed capsule contains the placeholder timestamp `2026-10-13T18:xx`. Replace it with the actual refresh time or a date-only value.

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-10-13T23:00:12Z

**Decision**: The Phase 1 acceptance filter (`pytest test_enter_decisions.py -k "force or head_moved"`) passes but does not select the five named tests. They live in `test_enter_loop_only.py`, so the literal acceptance command never runs them. I ran them directly and they pass, along with the existing `test_enter.py` force and moved-HEAD cases.

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-10-13T23:00:12Z

**Decision**: Moving the five named acceptance tests leaves the Phase 1 command targeting only `test_enter_decisions.py`; it can pass without exercising them. Add `test_enter_loop_only.py` to that command.

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-10-13T23:00:12Z

**Decision**: First-entry `force` still fails condition 1 of the “ALL” list, while the same paragraph permits delta without condition 2. Move the first-entry rule before the shared conditions, requiring a recorded SHA and loop-only commits.

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-10-13T23:00:12Z

**Decision**: R14 is only partly resolved: the `batch.catchup_completed_at` row (state-schema.md:237) still says delta needs `catchup_head_sha` to "match current HEAD". The edit landed on the adjacent `batch.catchup_head_sha` row instead, so the cited row stays stale against the loop-only rule

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-10-13T23:00:12Z

**Decision**: Prior R14 remains: the `batch.catchup_completed_at` row still documents only exact HEAD equality; the rework changed the adjacent row. Update this row to include loop-only movement and the first-entry `force` freshness exemption.

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-10-13T23:00:12Z

**Decision**: The new `batch.catchup_head_sha` text names the internal closure `_loop_moved` (enter.py:308) in a schema reference. The user-facing rule is "every commit since it has committer `autopilot-loop/<batch.id>`", so drop the symbol name

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-10-13T23:00:12Z

**Decision**: Cycle 2 converged: 14 findings, zero CRITICAL and zero HIGH; the doubt-roster constraint gate exited 0.

**Choice**: converged, tail sweep instead of a third cycle

**Rationale**: Medium and Low never block convergence; the actionable tail was swept by tasks 9 and 10 and the PRD finalizes.

### [autonomous] 2026-10-13T23:00:12Z

**Decision**: Six Medium/Low findings (R2, R4, R5, R6, R7, R11) swept into two tail-sweep tasks; the other eight settled in the ledger.

**Choice**: swept

**Rationale**: All six are one-line prose fixes against the code the cycle verified; the eight settled ones are accepted risks, optional refactors, or replay artifacts of the incremental base.

### [autonomous] 2026-10-13T23:00:12Z

**Decision**: Task 10's single finding duplicated task 9's first bullet (the Phase 1 acceptance command named only test_enter_decisions.py).

**Choice**: closed with no further edit

**Rationale**: Task 9's PRD edit added test_enter_loop_only.py; the acceptance filter now selects 25 tests across both files and all pass.

### [autonomous] 2026-10-13T23:00:12Z

**Decision**: Ivan's task-9 restructure broke test_custody_prose::test_forced_catchup_is_spent_once_the_prd_has_tasks by rewording the pinned not-a-list sentence.

**Choice**: fixed in the same work phase (commit 339825d)

**Rationale**: The pinned sentence is a prose contract; the first-entry paragraph now carries it verbatim and the gate is green at 6533 passed.

### [autonomous] 2026-10-13T23:00:12Z

**Decision**: Carl (gemini/copilot) failed again on authentication (exit 1) and the native gemini lane was past the 60 min ceiling.

**Choice**: continued with Alice, Blake and Bob; Carl not latched

**Rationale**: Exit 1 is a runtime failure, not the exit 4 that latches a reviewer for the batch. Graceful degradation per the review gate's safety-checks row.

### [autonomous] 2026-10-13T23:00:12Z

**Decision**: Bob's first codex run refused for lack of input (sandbox_apply: Operation not permitted on both staged files).

**Choice**: one inlined retry (181 KB prompt), which produced a full review

**Rationale**: The retry-policy inlined-retry prompt exists for exactly this sandbox refusal; the doubt lens delivered FIX/VERIFY/KNOWN buckets and all five D-rule verdicts.

### [deferred] 2026-10-13T23:00:12Z

**Decision**: `loop_committer` is defined in `enter_io.py`, not `cli/loop.py` as the Phase 0 task states. `loop.py` and `enter.py` both import it, so behavior is correct.

**Rationale**: deferred by review-close

### [deferred] 2026-10-13T23:00:12Z

**Decision**: Small edits outside the spec's file list: an unused `NOW` import was removed from `test_enter.py`, imports in `test_loop_review_once.py` were reordered, and a shared helper was added to `enter_harness.py`. The force and moved-HEAD cases in `test_enter.py` are unchanged.

**Rationale**: deferred by review-close
