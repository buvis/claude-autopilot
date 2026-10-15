# Decision Audit Log: 00312-close-ten-loop-truths-v1

PRD: `00312-close-ten-loop-truths-v1.md`
Started: 2026-10-15T17:08:44Z
Completed: 2026-10-15T17:08:44Z
Autonomous: 18  |  Deferred: 0  |  Doubts: 0

### [autonomous] 2026-10-15T17:08:44Z

**Decision**: Fail-first replay: 24 touched tests pass against the pre-change code (test_loop_gates.py, test_loop_gates_registry.py)

**Choice**: discarded

**Rationale**: Cycle 1 decision gate: verified not a defect. test_loop_gates_registry.py is a pure carve-out of test_loop_gates.py and holds exactly the 15 tests reported as base-passing; all 17 of the PRD named tests are absent at base 57fb258a, and the only new test in test_loop_gates.py (test_child_pids_passes_dash_a_on_darwin) cannot pass at base because procinfo.py:126 -a does not exist there. 18 of 42 replayed tests failed at base, which is the fail-first evidence.

### [autonomous] 2026-10-15T17:08:44Z

**Decision**: Bob codex first run refused for lack of input (sandbox denied reads); his retry output bulleted every issue line so consolidate_findings dropped all nine findings

**Choice**: auto-fixed

**Rationale**: Cycle 1 decision gate: the refusal matched all three lack-of-input conditions, so Bob single retry was spent on the inlined retry prompt (178 KB, context and diff inlined verbatim), which produced a real review. His budget being spent, the format non-compliance was handled per retry-policy Format Compliance step 2: the - bullet prefix was stripped mechanically to a normalized copy (9 lines, no other edit) and consolidation re-run, so the doubt lens findings reached the table instead of being lost. Marked (format warning) in the review file.

### [autonomous] 2026-10-15T17:08:44Z

**Decision**: Working tree held 8 modified cli/*.py files at review entry; engram context pack failed to build

**Choice**: auto-fixed

**Rationale**: Cycle 1: the modifications were pure end-of-turn formatter reflow (line wrapping, timezone.utc to UTC, __all__ sort, one behaviour-preserving SIM114 merge) with no PRD work, so they were discarded with git checkout before staging and the reviewed tree is clean at HEAD 257141c1. The pack failed with engram sqlite readonly database under the sandbox; every prompt carried the no-pack sentinel, so the cycle is degraded in reuse precedent but not invalid.

### [autonomous] 2026-10-15T17:08:44Z

**Decision**: The PRD contract says `_AUTOPILOT_LOOP_ENTRY_STALE` is never set after a successful write or a successful invalidation, but no test covers it. Removing either `env.pop` (loop.py:580 and loop.py:611) leaves every test green. A stale marker from one launch could then leak into the next successful launch and disable replay. Add a test with a failure followed by a success, asserting the variable is absent on the second child.

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-10-15T17:08:44Z

**Decision**: The first new CHANGELOG entry says the "catchup guard" now finds Darwin ancestor processes, but the catchup guard is the `merge-base --is-ancestor` change and has nothing to do with `pgrep`. Its own entry is the next line, so this is a wording slip

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-10-15T17:08:44Z

**Decision**: The usage-limit wait print and notify are copied from `_act_continue` into `_budget_bound`, so two sites must now stay in step. Extract one helper (for example `_announce_limit_wait(decision)`) and call it from both.

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-10-15T17:08:44Z

**Decision**: `_decision_fields` assigns `fields["limit_wait"]` in two branches, and the `elif` line is over 100 characters. Merge them into one condition, `limit_wait is not None and (effective_signal(decision) == "continue" or (decision["signal"] == "park" and decision.get("park_site") == "budget"))`.

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-10-15T17:08:44Z

**Decision**: `_record_entry` repeats the "invalidate, else set `_AUTOPILOT_LOOP_ENTRY_STALE`" pair in two except branches. The pop is also written twice, at the top of `_record_entry` and in the `_pre_enter` early return. Pop once at the top of `_pre_enter`, and have `_invalidate_loop_entry` or a small helper own the marking.

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-10-15T17:08:44Z

**Decision**: `test_budget_park_row_carries_limit_wait` and `test_instant_exit_limit_row_carries_limit_wait` call `_decision_fields` directly. The PRD and task text ask for the metrics row from the scripted loop. The negative case is also untested: a non-budget park must carry no `limit_wait`.

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-10-15T17:08:44Z

**Decision**: The doc-contract test accepts invalid argv containing the expected flag substrings. Removing `[--state]` or adding obsolete positionals still passes. Validate the invocation's required, optional, and positional arguments against the parser.

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-10-15T17:08:44Z

**Decision**: Both wait-metrics tests inspect `_decision_fields` directly, although the PRD requires reading emitted metrics rows. Exercise the scripted loop and assert `limit_wait` in `metrics_rows` for both paths.

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-10-15T17:08:44Z

**Decision**: The grandchild can query before the parent writes its registry entry; the result file can also become visible before writing finishes. Synchronize registry readiness and result completion to prevent intermittent failures.

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-10-15T17:08:44Z

**Decision**: The budget branch duplicates `_act_continue`'s wait announcement and notification. Extract one shared announcement method, retaining each caller's existing sleep ordering.

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-10-15T17:08:44Z

**Decision**: The drained row repeats its existing absent-state condition, while its test checks a phrase anywhere in the document. Consolidate the row into conditional init followed by phase-done, and scope the assertion to that row.

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-10-15T17:08:44Z

**Decision**: `test_loop_gates.py` carries unrelated reformatting: wrapped dict literals, parameter lists exploded one per line and an `assert (...)` wrap, in tests the PRD does not touch. This looks like an end-of-turn reflow. Revert it so the diff traces only to the PRD.

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-10-15T17:08:44Z

**Decision**: `_invalidate_loop_entry` now returns False on a failed write but prints nothing. The operator sees the first failure and not why the entry stays replayable. One stderr line would make the new stale-marker path visible.

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-10-15T17:08:44Z

**Decision**: In `_replay_loop_entry` the `_AUTOPILOT_LOOP_ENTRY_STALE` check comes after the `loop_entry` delete. If the state file stays unwritable, the child's `autopilot enter` returns 2 at the delete and never reaches the "run the entry for real" path. This only matters under persistent write failure and the PRD does not specify the order

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-10-15T17:08:44Z

**Decision**: `test_state_schema_cli_rows_match_the_parsers` only checks that the required flags appear in the two rows. It does not assert the old positional forms (`<state.json>`, `<review-file>`) are gone, and it ignores the optional `--state`. A row that keeps the old text and adds the flags would still pass

**Choice**: auto-fixed

**Rationale**: fixed by review-close
