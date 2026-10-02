# Decision Audit Log: 00188-record-convergence-cap-and-roster-per-prd-v1

PRD: `00188-record-convergence-cap-and-roster-per-prd-v1.md`
Started: 2026-09-14T09:48:32Z
Completed: 2026-09-14T09:48:32Z
Autonomous: 14  |  Deferred: 2  |  Doubts: 0

### [autonomous] 2026-09-14T09:48:32Z

**Decision**: Convergence collection can abort the loop: absent identity keys raise KeyError, and schema-allowed non-dict deferrals raise AttributeError; neither reaches the existing exception handler (loop.py:961 / convergence.py:104-105, :78-79)

**Choice**: auto-fix, reworked in [D1] task 6 (cycle 1)

**Rationale**: orchestrator-confirmed: schema.py:192-199 makes batch/batch.id optional and validates deferred_decisions as a bare list, loop.py:750 tolerates a missing batch for the session row while build_row indexes it; a review-once state from `autopilot init` would kill the driver at the finalize hand-off. Bounded fix (input guards, no new exception class, no signature change), so auto-fix rather than defer. Found by Bob (High) and Blake (Low); merged as [2/4].

### [autonomous] 2026-09-14T09:48:32Z

**Decision**: Empty or garbage review files produce zero severity counts instead of null, contradicting the PRD and making unparseable reviews appear clean (convergence.py:64-70)

**Choice**: auto-fix, reworked in [D1] task 6 (cycle 1)

**Rationale**: PRD must-have says an unparseable file yields null, never zeros; read_cycle zeroes findings for any readable text. The work-phase assumptions ledger recorded the opposite reading (Tess, task 1); the PRD text wins. Fix: no reviewers line and no verdict line means unparseable -> all-None cycle; a parseable file with no table keeps its zeros. Bounded, single caller, so auto-fix.

### [autonomous] 2026-09-14T09:48:32Z

**Decision**: Invalid UTF-8 in a review or PRD escapes _read_text and suppresses the entire convergence event instead of leaving only the unreadable fields null (convergence.py:30-35)

**Choice**: auto-fix, reworked in [D1] task 6 (cycle 1)

**Rationale**: UnicodeDecodeError is a ValueError, swallowed by _append_metrics after the whole row is lost; catching it in _read_text keeps the per-field null contract. Mechanical, one-line fix plus a test.

### [autonomous] 2026-09-14T09:48:32Z

**Decision**: No test asserts that review->paused emits no convergence event; the PRD names paused explicitly (test_loop.py)

**Choice**: auto-fix, reworked in [D1] task 7 (cycle 1)

**Rationale**: additive test; found by Bob (Medium) and Alice (Low), merged as [2/4]; the assumptions ledger's Devon round-2 note for task 2 flagged the same gap.

### [autonomous] 2026-09-14T09:48:32Z

**Decision**: test_convergence_is_keyword_only passes against the base implementation because an unsupported sixth argument also raises TypeError; it never establishes keyword acceptance (test_render_run_conditions.py:165)

**Choice**: auto-fix, reworked in [D1] task 7 (cycle 1)

**Rationale**: orchestrator-confirmed by a manual base run (passes at e718214); additive positive assertion. Found by Bob and the fail-first replay (mech-check).

### [autonomous] 2026-09-14T09:48:32Z

**Decision**: CAP_DEFERRED_ROW and the null fixture unnecessarily parse concatenated JSON strings; ordinary dictionaries would expose their structure directly (test_render_run_conditions.py:38)

**Choice**: auto-fix, reworked in [D1] task 7 (cycle 1)

**Rationale**: the stated reason (800-line cap of test_render.py) no longer holds since the tests were split into a 194-line module; behavior-preserving fixture rewrite.

### [autonomous] 2026-09-14T09:48:32Z

**Decision**: The two negative loop tests duplicate state-writing closures already implemented by _state_step (test_loop.py:861)

**Choice**: auto-fix, reworked in [D1] task 7 (cycle 1)

**Rationale**: mechanical reuse of an existing module helper; assertions unchanged.

### [autonomous] 2026-09-14T09:48:32Z

**Decision**: _select_report_block's event-row match uses a key dict + all(...) where the task text prescribed three direct field comparisons (__main__.py:806-809)

**Choice**: auto-fix, reworked in [D1] task 7 (cycle 1)

**Rationale**: Low, stylistic, one-line; Pat and the work-phase de-slop pass flagged the same.

### [autonomous] 2026-09-14T09:48:32Z

**Decision**: Fail-first replay: test_review_exit_to_review_writes_no_convergence_row and test_build_exit_writes_no_convergence_row pass against the pre-change code (test_loop.py)

**Choice**: discarded (cycle 1), recorded in the settled-decisions ledger

**Rationale**: by-design negative pins of preserved behavior (the base emits no event rows); the positive pin test_review_exit_to_done_writes_the_convergence_row fails at base. Not a tautology.

### [autonomous] 2026-09-14T09:48:32Z

**Decision**: Fail-first replay: test_tasks_line_falls_back_to_the_event_row_when_record_reads_zero passes against the pre-change code (test_render_run_conditions.py)

**Choice**: discarded (cycle 1), recorded in the settled-decisions ledger

**Rationale**: refuted by measurement: a manual run against a fresh base worktree at e718214 shows 3 SUBFAILED (TypeError: unexpected keyword argument 'convergence'); the replay script misreads unittest.subTest failures as passes, as first measured in the 00187 cycle-2 review.

### [autonomous] 2026-09-14T09:48:32Z

**Decision**: Fail-first replay: test_review_exit_to_review_writes_no_convergence_row, test_build_exit_writes_no_convergence_row, test_review_exit_to_paused_writes_no_convergence_row pass against the pre-change code (test_loop.py)

**Choice**: discarded (cycle 2), recorded in the settled-decisions ledger

**Rationale**: the first two are the cycle-1 settled discard (negative pins of preserved behavior); the paused test is the same class: the emission branch at the replay base 7f51b0f already fires only on phase_end == done, so a review-to-paused exit wrote no row there either, and the test pins that exclusion against a future loosening of the trigger. Not a tautology.

### [autonomous] 2026-09-14T09:48:32Z

**Decision**: Fail-first replay: test_partially_parsed_review_file_keeps_its_counts passes against the pre-change code (test_convergence.py)

**Choice**: discarded (cycle 2), recorded in the settled-decisions ledger

**Rationale**: preservation pin by construction: it asserts that a file the parser accepts keeps its findings dict, which 7f51b0f already did for every readable file; its paired fail-first pin test_unparseable_review_file_reads_null_not_zero fails at 7f51b0f. Discarded as a replay row only; Bob’s cycle-2 High that one of its expectations (Verdict: 1 finding with no table -> zeros) is wrong is recorded separately as a cap-overflow deferral.

### [autonomous] 2026-09-14T09:48:32Z

**Decision**: Fail-first replay: test_convergence_is_keyword_only, test_run_conditions_line_marks_nulls_with_question_marks pass against the pre-change code (test_render_run_conditions.py)

**Choice**: discarded (cycle 2), recorded in the settled-decisions ledger

**Rationale**: refuted by measurement: the replay base is 7f51b0f, where prd_section already accepts convergence=, so a test-only rework passes there by construction; re-run with --base e718214 (the PRD base) both tests FAIL (14 of 15 touched tests fail there; only the ledgered subTest misread is reported passing). The keyword-only test now proves keyword acceptance, which is what the cycle-1 finding asked for.

### [autonomous] 2026-09-14T09:48:32Z

**Decision**: Cap check: cycle 2 >= rework_cap 2 with one unresolved High (Bob, 1/4: read_cycle still reads a metadata-only review file, or a Verdict: N findings file with no table, as zero findings) - loop-mode cap-out

**Choice**: cap-out: the High and the one Low (Alice, batch -> batch_id naming) appended to deferred_decisions as cap-overflow records; finalize as converged-with-deferrals, outcome cap_deferred; no tail sweep on a cap-out

**Rationale**: orchestrator-confirmed by a probe over convergence.read_cycle: a file holding only `reviewers: alice` returns findings {0,0,0,0} with verdict None, and `Verdict: 1 finding` with no table returns verdict 1 with findings {0,0,0,0}; the cycle-1 task-6 brief defined parsed as either regex matching, which the PRD text (absence must not read as clean) is stricter than. Severity kept as reported (the gate reads severity from the reviewer, and the cycle-1 gate accepted the broader form of this same class as High). Alice, Blake and Carl passed R9/B1 without raising it, so consensus is 1/4. Eight of the nine cycle-1 findings verified resolved by Alice against HEAD; cycle 2 raised no regression in the rework.

### [deferred] 2026-09-14T09:48:32Z

**Decision**: The false-clean finding is only partially resolved: a file containing just `reviewers: alice` still produces zero severity counts because one regex matched. The new partial-parse test also expects zeros for `Verdict: 1 finding` without a findings table. Missing findings evidence still appears clean, contrary to the PRD’s null requirement. (Gate-verified by probe: reviewers-only -> findings {0,0,0,0}, verdict None; `Verdict: 1 finding` with no table -> verdict 1, findings {0,0,0,0}. Bob’s FIX: return null findings when neither parseable findings rows nor an explicit clean verdict (converged / 0 findings) establishes counts; add a metadata-only fixture and correct the positive-verdict-without-table expectation in test_partially_parsed_review_file_keeps_its_counts.)

**Choice**: deferred to batch end (cap-overflow)

**Rationale**: rework cap reached with this finding unresolved

### [deferred] 2026-09-14T09:48:32Z

**Decision**: `batch` in `_append_convergence` holds only the batch id, not the batch dict; `batch_id` would read clearer (already self-noted by the work phase as LOW, left unapplied)

**Choice**: deferred to batch end (cap-overflow)

**Rationale**: rework cap reached with this finding unresolved
