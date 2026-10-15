---
catchup: run
design: skip
default_model: sonnet
model_tier_rationale: one red rule with its exact expression applied at two call sites; the rest are wording and record-shape fixes with named tests
---

# The review's Tests: line and the verify record say red when the gate was red

Source: `docs/dev/project-management/audit-results/agoge-2026-10-15.md` packets 2 (HIGH), 15, 24; the PRD 00311 cycle-2 deferred ledger (the folded EXIT token, the JSON error prefix, the `log` key on a refusal, the `writer` key missing from the docs). Line numbers are from HEAD 807ed12b; PRDs 00320 and 00322 drain first and edit `verification.py` and `_run_verify`, so the symbols anchor and the numbers may have moved. CHANGELOG lines are identified by their quoted text, not their number.

## Problem

`_gate_result_line` (`skills/run-autopilot/cli/review_stage.py:348-373`) builds the `Tests:` line that the review skill copies into the review file and that Blake's prompt trusts ("do not rerun the full suite"). It reads only the counts, so a gate that prints `PASS 3 FAIL 0 SKIP 0 EXIT 0` and exits 5, one that prints `EXIT 1` and exits 0, and one that echoes a summary inside test output and crashes with exit 2 all reach every reviewer as `Tests: 3 passed, 0 failed, 0 skipped (suite run this cycle)`, and the review gate accepts the line because `TESTS_RE` (`skills/run-autopilot/cli/gate.py:126-129`) matches it (packet 2; measured through `review-stage --cycle-id 2`, the same line lands in the context file and in Blake's prompt; 00311 fixed only `verify`'s own exit, in `_report_verify` at `skills/run-autopilot/cli/__main__.py:1064-1090`). A gate that ran and then dirtied the tree is reported `Tests: (gate skipped: working tree dirty outside the store: stray.txt)` while its log holds `PASS 2 FAIL 1 SKIP 0 EXIT 1` (packet 15). `_write_record` (`skills/run-autopilot/cli/verification.py:151-179`) folds a non-zero summary EXIT token into the persisted `failed` count, so the record reads `failed: 1` for a suite that failed nothing (ledger, 2/4). `run_gate_line` (`skills/run-autopilot/cli/review_stage.py:376-409`) returns `"log": str(log_path)` on a lock-timeout, head-moved or pre-spawn dirty refusal that created no log; the exit-2 JSON that `_run_verify` (`skills/run-autopilot/cli/__main__.py:1093-1122`) prints omits the `autopilot: verify: ` prefix its stderr line carries; CHANGELOG line 33 says `verify` takes its exit from the parsed summary line and omits the process-exit rule (packet 24); and the record shape documented in `skills/work/references/final-verification.md` lacks the `writer` key the code writes and reuse requires.

## Solution

One red rule, `is_red(result, summary_exit)` in `verification.py`: true when `failed` is above zero, when the summary's EXIT token is non-zero, or when the process exit is non-zero. `_report_verify` calls it in place of its inline expression. `_gate_result_line` calls it too: a red result renders in the shape `TESTS_RE` already reads for a timed-out suite, with the failed count forced to at least one and a suffix that names the cause, `Tests: 3 passed, 1 failed, 0 skipped (suite exit 5, EXIT 0, treated as failed)`, so no reviewer sees `0 failed` for a red gate; a result that ran and then dirtied the tree renders `Tests: 2 passed, 1 failed, 0 skipped (suite exit 1, gate dirtied the tree: stray.txt; not recorded)`, the counts taken from the parsed summary. `_write_record` keeps the true `failed` and adds `"summary_exit": <token or null>` to the record; `_record_shape_ok` refuses reuse of a record whose `summary_exit` is non-zero (today's folded-count refusal, made explicit). `run_gate_line` returns `"log": None` when `result["exit"]` is None and `timed_out` is false. The exit-2 JSON `error` field carries the stderr line verbatim, prefix included. CHANGELOG line 33 is reworded to "red when the parsed summary (FAIL above zero or a non-zero EXIT token) or the gate process says so", and `final-verification.md` documents `writer: run_gate` and `summary_exit` in the record shape.

## Requirements

### Must have
- `_gate_result_line` renders a red line (failed at least one, cause named) for each of the three packet 2 gates; the line matches `TESTS_RE` and never reads `0 failed`.
- The ran-then-dirtied result renders the parsed counts and the dirtying paths with `not recorded`.
- `_write_record` persists the true `failed` and `summary_exit`; `_record_shape_ok` refuses reuse when `summary_exit` is non-zero or any `commands[].exit` is non-zero.
- `run_gate_line` returns `"log": None` for a result that spawned no gate.
- The exit-2 JSON `error` equals the stderr line, prefix included, for both refusals in `_run_verify`.
- CHANGELOG line 33 reworded; `final-verification.md` documents `writer` and `summary_exit`.
- A CHANGELOG `[Unreleased]` Fixed entry under **run-autopilot** for the `Tests:` line.

### Nice to have
- None.

## Implementation

### Module: red-rule
- **Location**: `skills/run-autopilot/cli/verification.py` (`_write_record`, `_record_shape_ok`), `skills/run-autopilot/cli/__main__.py` (`_report_verify`, `_run_verify`)
- **Responsibility**: one definition of red, a truthful record, a verbatim error field
- **Exports**: `is_red()`
- New symbols: `is_red`, `summary_exit`

### Module: tests-line
- **Location**: `skills/run-autopilot/cli/review_stage.py` (`_gate_result_line`, `_tests_line`, `run_gate_line`)
- **Responsibility**: the `Tests:` line reviewers read says red when the gate was red
- **Exports**: `run_gate_line()` (unchanged signature)

### Module: verify-docs
- **Location**: `CHANGELOG.md`, `skills/work/references/final-verification.md`
- **Responsibility**: the documented exit rule and record shape match the code
- **Exports**: none

### Module: tests-line-tests
- **Location**: `skills/run-autopilot/cli/test_review_stage.py`, `skills/run-autopilot/cli/test_verify_truth.py`, `skills/run-autopilot/cli/test_verification_reuse_verdict.py`, `skills/work/scripts/test_verify_queue_prose.py`
- **Responsibility**: pin the red line, the record keys, the reuse refusal, the error field and the docs
- **Exports**: none
- New symbols: `test_gate_line_marks_nonzero_process_exit_red`, `test_gate_line_marks_nonzero_exit_token_red`, `test_gate_line_never_reads_zero_failed_for_a_red_gate`, `test_gate_line_reports_ran_then_dirtied_with_counts`, `test_run_gate_line_log_is_none_when_no_gate_spawned`, `test_record_keeps_true_failed_and_summary_exit`, `test_record_with_nonzero_summary_exit_is_not_reused`, `test_exit_2_json_error_carries_the_stderr_prefix`, `test_final_verification_documents_writer_and_summary_exit`

### Dependencies
- tests-line-tests: No dependencies (foundation)
- red-rule: Depends on [tests-line-tests]
- tests-line: Depends on [red-rule]
- verify-docs: Depends on [tests-line]

## Tasks

### Phase 0: Foundation
- [ ] Add `test_gate_line_marks_nonzero_process_exit_red`, `test_gate_line_marks_nonzero_exit_token_red`, `test_gate_line_never_reads_zero_failed_for_a_red_gate` (the summary-inside-output gate: `assert out == "PASS 9 FAIL 0 SKIP 0 EXIT 0"` then exit 2), `test_gate_line_reports_ran_then_dirtied_with_counts` and `test_run_gate_line_log_is_none_when_no_gate_spawned` to `skills/run-autopilot/cli/test_review_stage.py`; `test_record_keeps_true_failed_and_summary_exit` and `test_exit_2_json_error_carries_the_stderr_prefix` to `skills/run-autopilot/cli/test_verify_truth.py`; `test_record_with_nonzero_summary_exit_is_not_reused` to `skills/run-autopilot/cli/test_verification_reuse_verdict.py`; `test_final_verification_documents_writer_and_summary_exit` to `skills/work/scripts/test_verify_queue_prose.py` - Acceptance: `uv run --no-project --with pytest python -m pytest -q skills/run-autopilot/cli/test_review_stage.py skills/run-autopilot/cli/test_verify_truth.py skills/run-autopilot/cli/test_verification_reuse_verdict.py skills/work/scripts/test_verify_queue_prose.py` reports the nine new tests failing at the task's base commit and no existing test failing.

### Phase 1: Core
- [ ] Add `is_red` and `summary_exit` to `skills/run-autopilot/cli/verification.py` (`_write_record`, `_record_shape_ok`), call `is_red` from `_report_verify` and carry the stderr line into the JSON `error` in `_run_verify` of `skills/run-autopilot/cli/__main__.py`, then render the red and ran-then-dirtied lines in `_gate_result_line` and return `"log": None` from `run_gate_line` in `skills/run-autopilot/cli/review_stage.py` (depends on: Phase 0) - Acceptance: the Phase 0 command passes every test; `uv run --no-project --with pytest python -m pytest -q skills/run-autopilot/cli/test_verification.py skills/run-autopilot/cli/test_gate_findings_table.py` passes.

### Phase 2: Integration
- [ ] Reword CHANGELOG line 33, add the Fixed entry for the `Tests:` line, and document `writer` and `summary_exit` in `skills/work/references/final-verification.md` (depends on: Phase 1) - Acceptance: `uv run --no-project --with pytest python -m pytest -q skills/work/scripts/test_verify_queue_prose.py` passes; `rg -n 'or the gate process says so' CHANGELOG.md` prints one hit under `[Unreleased]`; `rg -n 'treated as failed' CHANGELOG.md` prints at least one hit under `[Unreleased]`.

## Success Criteria

- The three packet 2 gates each render a `Tests:` line with at least `1 failed` and a cause in its suffix, in the context file and in Blake's prompt.
- The packet 15 gate renders `2 passed, 1 failed` with `stray.txt` and `not recorded`.
- A record written for `FAIL 0 ... EXIT 1` reads `failed: 0, summary_exit: 1` and is never reused.
