# Decision Audit Log: 00265-close-the-critical-row-escapes-v1

PRD: `00265-close-the-critical-row-escapes-v1.md`
Started: 2026-10-07T19:09:23Z
Completed: 2026-10-07T19:09:23Z
Autonomous: 10  |  Deferred: 31  |  Doubts: 0

### [autonomous] 2026-10-07T19:09:23Z

**Decision**: PRD #24 is only partly done: no `^[A-Za-z0-9._][A-Za-z0-9._-]*$` shape check, no stderr line naming a refused id, no `--` separator before the id in the `end` argv (neither in review_close nor in skills/work/scripts/record_dispatch.py). `_dispatch_outcomes` only drops ids starting with `-`, silently.

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-10-07T19:09:23Z

**Decision**: Tail sweep is refused on every converged cycle: `_tail_sweep_refusal` requires a `<review>::decision-gate` stamp in `applied_review_batches`, but the converged path never makes a decision-gate call (that call lives only in Phase 6 Dispatch rework, which convergence skips). A converged cycle with a Medium/Low tail exits 2 with `tail_sweep_before_decision_gate` and the loop stalls.

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-10-07T19:09:23Z

**Decision**: The findings-table parse fails open on an indented pipe data row: `_CANDIDATE_ROW_RE` is `^\|`, so ` | R1 | [2/2] | 🔴 | ...` is silently skipped and a CRITICAL gets no disposition and no task. An indented header is refused as `malformed`, but an indented data row under a valid header is dropped.

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-10-07T19:09:23Z

**Decision**: Converged cycles jump directly to tail sweep, but the new guard requires a decision-gate stamp created only in Phase 6, which convergence skips. Apply the decision-gate batch before the sweep and prevent duplicate task creation; add a workflow regression.

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-10-07T19:09:23Z

**Decision**: The new state vocabulary is undocumented: the `lost` lens status and the `carry_refs`/`carry_cycle` task fields are in code and prose but not in state-schema.md, and the tracon docstring at scripts/tracon/model.py:281 still says `running|done|failed`.

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-10-07T19:09:23Z

**Decision**: A complete data row missing only its closing pipe still parses: `_table_cells` strips delimiters without checking termination. Enforce the required closing pipe and test it through both verbs.

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-10-07T19:09:23Z

**Decision**: Deferral matching only strips strings, so an existing `medium` deferral does not match a 🟡 finding for the same file. Reuse the shared severity/file normalization and test word/emoji equivalence.

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-10-07T19:09:23Z

**Decision**: The moved verdict-preservation test calls an empty tail sweep without its decision-gate stamp; the call now refuses, making the preservation assertion vacuous. Supply valid sweep prerequisites and assert successful application before checking preserved verdicts.

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-10-07T19:09:23Z

**Decision**: The `unreadable-table` message still describes the old row shape, does not mention that a Ref-less table is refused as `ref-required`, and does not name the offending row, so the exit-2 operator cannot fix it in one round trip.

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-10-07T19:09:23Z

**Decision**: Cannot statically verify: release-checks passes at the reviewed revision. The context reports cached results; the exact check is `bash dev/bin/release-checks`.

**Choice**: routed to verification

**Rationale**: queued in 00265-close-the-critical-row-escapes-v1-checks-1.json as `bash dev/bin/release-checks`; runs in the work phase step 7, no task created

### [deferred] 2026-10-07T19:09:23Z

**Decision**: Unspecified behaviour added: a tail-sweep batch with a `carry` row is refused with a new `carry_in_tail_sweep` kind, which the PRD does not ask for (though CHANGELOG.md:15 and __main__.py document it).

**Rationale**: deferred by review-close

### [deferred] 2026-10-07T19:09:23Z

**Decision**: The backup-preservation test exercises three first-time refusals, never an already-applied repeat. Apply a batch, snapshot backup bytes and mtime, repeat that batch, and assert both remain unchanged.

**Rationale**: deferred by review-close

### [deferred] 2026-10-07T19:09:23Z

**Decision**: Simplification: the duplicate-deferral test and fixtures substantially repeat test_review_close_lowsev.py:145. Consolidate both input variants into one parametrized test.

**Rationale**: deferred by review-close

### [deferred] 2026-10-07T19:09:23Z

**Decision**: `_run_review_close` returns `2 if result.get("refused") else 1` instead of the design's explicit `_EXIT_2_REFUSALS` tuple. Behaviour is equivalent today and every kind is pinned by tests.

**Rationale**: deferred by review-close

### [deferred] 2026-10-07T19:09:23Z

**Decision**: For a refless table or bullet-shape findings the spec says `unreadable-table`; the code returns a distinct `ref-required` verdict. Both exit 2, but the tag differs from the spec's wording and `_FINDINGS_REFUSALS` gains a kind.

**Rationale**: deferred by review-close

### [deferred] 2026-10-07T19:09:23Z

**Decision**: The `review-close` message for an unknown classification is generic; it names neither the row nor the value. The spec only requires the per-row message in `gate --findings`, which is implemented.

**Rationale**: deferred by review-close

### [deferred] 2026-10-07T19:09:23Z

**Decision**: Pre-existing size violations remain: __main__.py has 1,679 lines. Splitting unrelated rendering code is outside this review-verb change.

**Rationale**: deferred by review-close

### [deferred] 2026-10-07T19:09:23Z

**Decision**: 6 touched test(s) pass against the pre-change code.

**Rationale**: deferred by review-close

### [deferred] 2026-10-07T19:09:23Z

**Decision**: 7 touched test(s) pass against the pre-change code.

**Rationale**: deferred by review-close

### [deferred] 2026-10-07T19:09:23Z

**Decision**: 6 touched test(s) pass against the pre-change code.

**Rationale**: deferred by review-close

### [deferred] 2026-10-07T19:09:23Z

**Decision**: 4 touched test(s) pass against the pre-change code.

**Rationale**: deferred by review-close

### [deferred] 2026-10-07T19:09:23Z

**Decision**: 12 touched test(s) pass against the pre-change code.

**Rationale**: deferred by review-close

### [deferred] 2026-10-07T19:09:23Z

**Decision**: 8 touched test(s) pass against the pre-change code.

**Rationale**: deferred by review-close

### [deferred] 2026-10-07T19:09:23Z

**Decision**: 8 touched test(s) pass against the pre-change code.

**Rationale**: deferred by review-close

### [deferred] 2026-10-07T19:09:23Z

**Decision**: 14 touched test(s) pass against the pre-change code.

**Rationale**: deferred by review-close

### [deferred] 2026-10-07T19:09:23Z

**Decision**: 2 touched test(s) pass against the pre-change code.

**Rationale**: deferred by review-close

### [deferred] 2026-10-07T19:09:23Z

**Decision**: 3 touched test(s) pass against the pre-change code.

**Rationale**: deferred by review-close

### [deferred] 2026-10-07T19:09:23Z

**Decision**: R4: gate._table_keys fails open on a findings table whose header is not recognised. A CRITICAL row under an unrecognised header gets no task, no record and no refusal - the same escape class as #2.

**Rationale**: rework cap reached with this finding unresolved

### [deferred] 2026-10-07T19:09:23Z

**Decision**: R1: the _tail_sweep_refusal docstring contradicts the prose it points at (it claims an empty decision-gate batch; the prose supplies full coverage) and pushes the function to 56 lines, over the 50-line style limit.

**Rationale**: rework cap reached with this finding unresolved

### [deferred] 2026-10-07T19:09:23Z

**Decision**: R2/R8: PRD clause #24 is only partly implemented - the -- separator before the row id is still missing in the review_close end argv and in record_dispatch.py. The id-shape refusal makes it unreachable today, so this is defense-in-depth only.

**Rationale**: rework cap reached with this finding unresolved

### [deferred] 2026-10-07T19:09:23Z

**Decision**: R3: the unreadable-table refusal message is reworded but still does not name the offending row, so an operator cannot fix it in one round trip as the PRD Risks section promised. Its new test also has a tautological first assert.

**Rationale**: rework cap reached with this finding unresolved

### [deferred] 2026-10-07T19:09:23Z

**Decision**: R5/R11: the converged-path fix (phase-review.md Tail sweep step 0) is prose-only with no regression test, although cycle-1 R4 explicitly asked for a workflow regression. A later prose edit can silently reintroduce the converged-cycle stall.

**Rationale**: rework cap reached with this finding unresolved

### [deferred] 2026-10-07T19:09:23Z

**Decision**: R6: Tail sweep step 0 runs before step 1 zero-actionable skip, so a clean converged cycle now pays an extra review-close decision-gate call that can itself refuse. Step 0 also forward-references rows step 1 will select. Reorder: select, skip if zero, gate, create.

**Rationale**: rework cap reached with this finding unresolved

### [deferred] 2026-10-07T19:09:23Z

**Decision**: R7: the new lost lens-status documentation does not match the code. state-schema.md and the tracon docstring say lost means an open dispatch row plus no agents line, but _lens_states marks every persona absent from agents as lost, dispatch rows unread.

**Rationale**: rework cap reached with this finding unresolved

### [deferred] 2026-10-07T19:09:23Z

**Decision**: R10: carry_refs is documented as unioned across cycles, but Phase 6 resets refs when the cycle changes. Retaining old refs could authorize unrelated carry rows. Document same-cycle union and cross-cycle reset.

**Rationale**: rework cap reached with this finding unresolved

### [deferred] 2026-10-07T19:09:23Z

**Decision**: R12: the closing-pipe refusal test exercises the gate cross-check only; cycle-1 R7 asked for both verbs. The review-close side is covered only indirectly through shared findings_verdict.

**Rationale**: rework cap reached with this finding unresolved

### [deferred] 2026-10-07T19:09:23Z

**Decision**: R13: the pre-lock refusals (carry match, tail-sweep order, empty, above-medium, open deferral) run on an advisory read while the in-lock check re-verifies only the apply-once stamp - a check-then-act window under the single-orchestrator assumption.

**Rationale**: rework cap reached with this finding unresolved

### [deferred] 2026-10-07T19:09:23Z

**Decision**: R14: _carry_unmatched does not require the [C{cycle}] name prefix its own docstring and error text promise; it rejects only [D-prefixed names and relies on carry_refs, carry_cycle, escalation_reason, rework_task_ids and status instead. Cosmetic - stricter elsewhere.

**Rationale**: rework cap reached with this finding unresolved

### [deferred] 2026-10-07T19:09:23Z

**Decision**: R15: the PRD names two homes for the help-text pin (skills/run-autopilot/scripts/test_review_verbs_prose.py in the task, skills/review-work-completion/scripts/test_review_verbs_prose.py in the structure). Only the second exists. A PRD inconsistency, not a code fault.

**Rationale**: rework cap reached with this finding unresolved

### [deferred] 2026-10-07T19:09:23Z

**Decision**: R16: a CRITICAL row classified discard or verify still needs no backing row and creates no task or record at the CLI layer, and a discard of a ghost ref is accepted. The PRD closes this only for carry, so it is a residual out of scope.

**Rationale**: rework cap reached with this finding unresolved

### [deferred] 2026-10-07T19:09:23Z

**Decision**: R19: a tail sweep holding only verify or discard rows passes the new empty check - it applies, creates zero tasks and stamps the batch, which is the never-zero failure mode the prose describes. The refusal tests literal array length only.

**Rationale**: rework cap reached with this finding unresolved
