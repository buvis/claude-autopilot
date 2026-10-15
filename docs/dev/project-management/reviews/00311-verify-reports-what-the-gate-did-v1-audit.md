# Decision Audit Log: 00311-verify-reports-what-the-gate-did-v1

PRD: `00311-verify-reports-what-the-gate-did-v1.md`
Started: 2026-10-15T14:51:19Z
Completed: 2026-10-15T14:51:19Z
Autonomous: 24  |  Deferred: 8  |  Doubts: 0

### [autonomous] 2026-10-15T14:51:19Z

**Decision**: High: `_report_verify` derives red only from the parsed summary, so the process exit no longer counts. I ran the CLI and confirmed both drifts. (a) `--gate-command "echo build failed; exit 2"` (no summary, process exit 2) now returns rc 3. It returned 1 before this diff. The PRD says exit 3 "keeps today's meaning", and the exit table says 3 is for "the gate exited 0 ... no summary line". skills/work/references/final-verification.md:176 says exit 3 "means the suite did not fail, so it does not enter Handling failures". A crashed or build-broken gate therefore skips failure handling. (b) `echo PASS 1 FAIL 0 SKIP 0 EXIT 0; exit 5` returns rc 0 with `recorded: true` and `exit: 5`. The table says 0 means "gate ran green", but the record's command exit is 5, so `_record_shape_ok` will never reuse it. Fix: also return 1 when `result["exit"] not in (None, 0)`, and add tests for a non-zero process exit with no summary and with a green summary. The design snippet has the same gap, but the PRD and the doc table do not allow it.

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-10-15T14:51:19Z

**Decision**: Medium: The PRD must-have says `run_gate_line`'s dirty line "names the paths", but `_gate_result_line` still prints the generic "working tree dirty outside the store". Only the `dirty_paths` dict key was added. Name the paths in the line, or record that the PRD sentence is deliberately dropped.

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-10-15T14:51:19Z

**Decision**: Medium: `_spawn_gate` is 63 lines, over the 50-line limit (see the mechanical facts block). Split the SIGTERM handler install/restore from the Popen, drain and reap body. For example, a small context manager would hold `gate_started`, `sigterm_pending` and the main-thread guard. This row also carries Alice's and Carl's file-size finding, merged on the same file: the diff pushes `verification.py` from 657 to 808 lines, over the 800-line limit.

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-10-15T14:51:19Z

**Decision**: `PASS 4 FAIL 0 SKIP 0 EXIT 1` with process exit 0 produces a reusable green record: persistence drops the summary's EXIT token, retaining zero failures and command exit 0. Preserve that failure in record eligibility and add a run→reuse regression test.

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-10-15T14:51:19Z

**Decision**: SIGINT during child creation bypasses cleanup because `Popen` sits outside the `BaseException` handler and only SIGTERM is deferred. The outer `LOCK_UN` then releases the inherited lock while the gate survives. Defer SIGINT through spawning too, and test interruption after child creation but before `Popen` returns.

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-10-15T14:51:19Z

**Decision**: Both `test_verification.py` and `test_verification_dirty.py` now extend beyond 800 lines, as their final function locations and lengths establish. Trim redundant commentary or move a coherent test group into a registered sibling module without removing assertions.

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-10-15T14:51:19Z

**Decision**: Low: `test_run_gate_line_names_lock_timeout_and_head_moved` compares `dirty_paths` against `[]` on both sides, so it does not show that non-empty paths pass through to the returned dict. Use a non-empty `dirty_paths` in one case.

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-10-15T14:51:19Z

**Decision**: Low: Nothing exercises the pending-SIGTERM branch (`sigterm_pending`) in `_spawn_gate`. `_run_verify` also catches only `OSError`, so the SIGTERM `RuntimeError` surfaces as a traceback with exit 1. This is acceptable but undocumented.

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-10-15T14:51:19Z

**Decision**: On the reuse path, the dict `run_gate_line` returns has no `dirty_paths` key (only `verdict`, `tests_line`, `timed_out`). The PRD says the returned gate dict carries `dirty_paths`. Any consumer indexing it unconditionally would raise `KeyError`.

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-10-15T14:51:19Z

**Decision**: R1 [3/4] 🟠 _report_verify derives red only from the parsed summary, so a gate that exits non-zero reports rc 0 (green summary) or rc 3 (no summary) instead of the pre-diff rc 1

**Choice**: auto-fix (task 6)

**Rationale**: Clear mechanical fix named identically by three lenses and reproduced by two of them on the live CLI: return 1 when result['exit'] is neither None nor 0, with tests for both drifts. The PRD Must-have says exit 0 and exit 3 keep today's meaning, and today's meaning included the process exit, so this restores the documented contract rather than changing it. No signature, schema or data-model change, so no research protocol applies.

### [autonomous] 2026-10-15T14:51:19Z

**Decision**: R4 [1/4] 🟠 a green-counts summary carrying EXIT 1 with process exit 0 produces a reusable green record: record eligibility drops the summary's EXIT token

**Choice**: auto-fix (task 5)

**Rationale**: Same defect class as R1 on the persistence side, and the PRD's whole point is that the record tells the truth about the run. Additive: preserve the EXIT token in record eligibility plus one run-to-reuse regression test.

### [autonomous] 2026-10-15T14:51:19Z

**Decision**: R5 [1/4] 🟠 SIGINT during child creation bypasses cleanup because Popen sits outside the BaseException handler and only SIGTERM is deferred, so LOCK_UN releases the inherited lock while the gate survives

**Choice**: auto-fix (task 5)

**Rationale**: The PRD Must-have requires that an orphaned gate keep the flock until it exits and that two gates never run at once; SIGINT is the same hole commit 132cd9e7 closed for SIGTERM. Extends the existing mechanism rather than adding a new one.

### [autonomous] 2026-10-15T14:51:19Z

**Decision**: R2 [3/4] 🟡 run_gate_line's dirty line does not name the dirty paths, which a PRD Must-have requires

**Choice**: auto-fix (task 7)

**Rationale**: An unimplemented Must-have with a one-line fix, raised by three lenses. R10 (the reuse path returning no dirty_paths key) is grouped into the same task as the other half of the same requirement.

### [autonomous] 2026-10-15T14:51:19Z

**Decision**: R3 [3/4] 🟡 _spawn_gate is 63 lines (50-line limit) and verification.py reached 808 lines (800-line limit); R6 the two verification test files also passed 800

**Choice**: auto-fix (tasks 5, 6)

**Rationale**: Objective, mechanically verified by check_style_limits.py exiting 1 on this diff and by the cycle's own mechanical-facts block. Not a judgment call, and the project's style limits are a standing rule.

### [autonomous] 2026-10-15T14:51:19Z

**Decision**: R7 [1/4] 🟡 SUMMARY_RE.search called without a None-check on raw_line before .group(4)

**Choice**: discarded

**Rationale**: Verified false positive. _parse_summary (verification.py:526-531) returns the raw line only when SUMMARY_RE already matched it, and every other result shape sets raw_line to None, so the re-search in _report_verify cannot return None and .group(4) cannot raise. Recorded in the settled-decisions ledger with the same evidence. The re-search is redundant work, which is cosmetic, not the crash claimed.

### [autonomous] 2026-10-15T14:51:19Z

**Decision**: R14, R15 [1/4] 🟡 21 touched tests pass against the pre-change code (mech-check fail-first replay)

**Choice**: discarded

**Rationale**: Behavior-preserving relocation, the case the mech-check block itself says to weigh before raising. Commit 42fb6210 split test_cli_verify_verb.py out of test_cli_review_verbs.py for the 800-line limit; the new file does not exist at the base commit, so its relocated tests pin behavior that already held there. This PRD's own new tests do fail at base (22 of 43 touched tests), which is where fail-first is evidenced.

### [autonomous] 2026-10-15T14:51:19Z

**Decision**: R8, R9, R10 ⚪ three Low findings: a dirty_paths assertion that compares [] to [], no test for the pending-SIGTERM branch, and no dirty_paths key on run_gate_line's reuse path

**Choice**: auto-fix (tasks 5, 7, 8)

**Rationale**: All three are additive and land in code the HIGH fixes already touch, so sweeping them now costs nothing extra. R10 is also half of the same PRD Must-have as R2.

### [autonomous] 2026-10-15T14:51:19Z

**Decision**: Bob's first codex run returned a lack-of-input refusal (sandbox_apply: Operation not permitted before any read-only command ran)

**Choice**: logged, continued after one inlined retry

**Rationale**: Safety Checks row for a transient reviewer error: graceful degradation, not a pause. The one allowed retry used the inlined prompt (context plus full diff, 224 KB) and produced a complete review, so the doubt lens is represented and Bob counts as done.

### [autonomous] 2026-10-15T14:51:19Z

**Decision**: state.work_start_sha was null on entry to the review gate, leaving the full-review diff range undefined

**Choice**: recovered to 82f63a12ff7f before staging

**Rationale**: The build gate's Phase 3 invariant should have captured it. Recovered as the parent of 5f23135c, this PRD's first work commit, so review-stage had the PRD's whole work range; without it gather-context.sh refuses an empty diff and the cycle cannot review anything. The capture miss is a product defect in the build gate, recorded for the batch.

### [autonomous] 2026-10-15T14:51:19Z

**Decision**: autopilot review-close rewrote state.review_lenses to five failed keys, inventing a fable lens that never ran

**Choice**: restored the accurate roster, recorded the defect

**Rationale**: All four dispatched reviewers produced usable reviews, so review-work-completion step 6's rule makes every lens done and adds no fable key. The CLI's re-derivation from the review file reads the per-rule fail verdicts as failed lenses. Dashboard-only state, so the restore is safe; the mis-derivation is a product defect for the batch.

### [autonomous] 2026-10-15T14:51:19Z

**Decision**: Blake: Phase 1 acceptance required the test count in test_verification_dirty.py unchanged from base; it went 31 -> 26 and no test deleted was unproven.

**Choice**: discarded - contradicts computed facts

**Rationale**: Measured: all 31 def test_ names present at f6a99ab still exist across skills/run-autopilot/cli/ at HEAD (0 missing, against 1439 HEAD test names). No test was deleted. The per-file count changed because the split IS cycle 1 accepted R6 fix for the 800-line limit, which this same cycle verifies as resolved; enforcing the per-file count would forbid the fix the prior cycle demanded.

### [autonomous] 2026-10-15T14:51:19Z

**Decision**: Blake: the new dirty_tree.py module (270 lines) is not mentioned in the PRD.

**Choice**: discarded - not a defect

**Rationale**: This is cycle 1 accepted R3 fix. R3 required verification.py back under the 800-line limit; extracting the dirty-tree helpers is how that was achieved (verification.py now 643 lines). Behaviour unchanged, re-exports keep callers working, and the finding itself concedes it is a pure refactor. A PRD need not pre-authorise the refactor its own style limit forces.

### [autonomous] 2026-10-15T14:51:19Z

**Decision**: mech-check: 22 touched tests in test_verification_normalize.py and test_verification_reuse_verdict.py pass against the pre-change code.

**Choice**: discarded - behavior-preserving relocation

**Rationale**: Measured: neither file exists at the cycle-1 base b2408046 (git cat-file -e fails for both), so the replay overlays them onto code that already satisfied their assertions. Both files were created by cycle 1 accepted R6 split. Same disposition as the two equivalent cycle-1 relocation rows.

### [autonomous] 2026-10-15T14:51:19Z

**Decision**: mech-check: test_sigterm_pending_before_gate_started_kills_the_gate and test_run_gate_line_names_lock_timeout_and_head_moved pass against the pre-change code.

**Choice**: discarded - tests written for already-correct behaviour

**Rationale**: These pass at base by construction, because that is what cycle 1 asked for: R9 was nothing exercises the pending-SIGTERM branch and R8 was the dirty_paths assertion compares empty on both sides. Both are requests to cover behaviour that was already correct, so the resulting tests must pass against that code. Raising it would punish the prior cycle accepted fix.

### [deferred] 2026-10-15T14:51:19Z

**Decision**: `run_gate_line` still returns `"log": str(log_path)` on a lock-timeout, head-moved or dirty refusal, when no log was created. The Problem section names this as a defect ("review-stage's dirty line names a log that does not exist"), but no requirement covers it, so it remains.

**Rationale**: deferred by review-close

### [deferred] 2026-10-15T14:51:19Z

**Decision**: The SIGTERM handler raises a bare `RuntimeError`. An uncaught SIGTERM therefore ends `verify` with a traceback and rc 1, with no JSON line. The PRD only says "raises", so this is within spec, but it does not match the tidy exit table.

**Rationale**: deferred by review-close

### [deferred] 2026-10-15T14:51:19Z

**Decision**: The `_spawn_gate` helper has an extra `sigterm_pending` and `gate_started` mechanism and a main-thread guard that the PRD does not ask for. It is defensive, harmless, and the cost of the Popen race, so I flag it only for completeness.

**Rationale**: deferred by review-close

### [deferred] 2026-10-15T14:51:19Z

**Decision**: SIGINT during gate spawn still leaks the gate process: _child_from_exception can recover a Popen whose pid is None, so _kill_gate raises TypeError (masking the KeyboardInterrupt) and the forked gate survives while the outer LOCK_UN releases the flock. A second hole sits between Popen() returning and the proc= store. Measured 68 leaked gates in 1500 trials. Remedy: defer SIGINT the way SIGTERM is deferred, which also removes _child_from_exception and _POPEN_TYPE.

**Choice**: deferred to batch end

**Rationale**: rework cap reached with this finding unresolved

### [deferred] 2026-10-15T14:51:19Z

**Decision**: _write_record folds a non-zero summary EXIT token into the persisted failed count, so FAIL 0 ... EXIT 1 is stored as failed: 1. The reuse hole is closed and tested, but the record now disagrees with the gate summary it reports. Remedy: persist the summary exit as its own field, or set commands[0].exit from it.

**Choice**: deferred to batch end

**Rationale**: rework cap reached with this finding unresolved

### [deferred] 2026-10-15T14:51:19Z

**Decision**: test_sigint_during_popen_leaves_the_gate_running does not exercise the real Popen.__init__ frame where pid is unset, so it passes while the race still leaks; _kill_gate also lacks a proc.pid is None guard. Travels with the HIGH above: the SIGINT deferral fix and the test that catches its regression belong in one change.

**Choice**: deferred to batch end

**Rationale**: rework cap reached with this finding unresolved

### [deferred] 2026-10-15T14:51:19Z

**Decision**: The JSON error field on both exit-2 verify refusals omits the autopilot: verify: prefix the stderr line carries, while the spec asks for the stderr line verbatim. test_exit_2_refusals_print_json only asserts non-empty, so it does not catch the difference.

**Choice**: deferred to batch end

**Rationale**: rework cap reached with this finding unresolved

### [deferred] 2026-10-15T14:51:19Z

**Decision**: The recorded-result JSON shape documented in skills/work/references/final-verification.md (lines 127-134) omits the new writer: run_gate key, which the code writes and _record_shape_ok requires. Doc drift against implemented behaviour.

**Choice**: deferred to batch end

**Rationale**: rework cap reached with this finding unresolved
