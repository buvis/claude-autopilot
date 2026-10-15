# Assumptions ledger — PRD 00311-verify-reports-what-the-gate-did-v1

## 1: Write test_verify_truth.py pinning the six verify-truth reproductions

- "SIGKILL the verify subprocess at 0.5s": the test waits until gate A's first tick appears (so a gate has spawned), then kills at 0.5s after launch or right away if that has passed. Starting the CLI can take longer than 0.5s.
- The fixture repo is `tmp_path/"repo"`, not `tmp_path`, so gate scripts and tick or pgid files sit outside the repo and are not dirt.
- verify is run as `sys.executable skills/run-autopilot/cli/__main__.py verify --gate-command ... --repo-root ...`.
- The exact `tests_line` strings in the `run_gate_line` test come from the design, because the contract does not spell them out: `Tests: (gate skipped: another gate held the lock for {int(GATE_TIMEOUT_S)}s)` and `Tests: (gate skipped: HEAD moved during the lock wait)`.
- "dirty_paths present" is checked as `out.get("dirty_paths") == fake["dirty_paths"]` (`[]`).
- The exit-2 refusals use `--log docs/dev/project-management/gate.log` for the store log, and a freshly `git init`-ed repo with no commits for the HEAD-resolution refusal.
- The fake lock-timeout result in the `run_gate_line` test uses `timed_out False`, matching the contract.

## 2: Add writer marker, named lock/HEAD-moved result shapes, and orphan-kill signal handling to verification.py

- Adding `lock_timeout`/`head_moved` to `_green_result` and to the two exact-dict asserts in `test_verification_dirty.py` counts as keeping test fixtures in line with the real result shape, not weakening tests.
- The SIGTERM handler is installed in `_run_locked_gate`/`_spawn_gate` exactly as the design shows, with no main-thread guard.
- Updating the stale comment in `test_verification_hidden_flags.py` (a HEAD mismatch is no longer reported as dirty) counts as cleaning up after the implementor's own change.
- If `Popen` itself raises while a SIGTERM is pending, the `Popen` exception propagates and the pending SIGTERM is dropped; with no gate process spawned, there is nothing to kill.

## 3: Derive _run_verify's exit code from the parsed gate summary, not the process returncode

- Mid-run dirt (`dirty` with a spawned gate) exits 3, not 1. This follows the design's own exit table and the existing tests, not its inline code snippet's literal `result["dirty"]` check.
- Used the design's inline `re.search(r"EXIT (\d+)")` instead of `verification.SUMMARY_RE` on the first pass, because `verification.py` was not in the allowlist (the self-deslop pass later replaced it with `verification.SUMMARY_RE`, per the task's own Reuse note).
- Tests were run via `uv run --with pytest`; the plain gate form was unavailable to the implementor.
- The JSON shape for the two reconciled `test_cli_review_verbs.py` assertions (exactly one stdout line, `"error"` containing "resolves inside the store", `"exit": 2`) was inferred from the retry dispatch's wording, without reading `test_verify_truth.py::test_exit_2_refusals_print_json` (outside that retry's allowlist).
- The style-fix split cut `test_cli_review_verbs.py` at the existing review-verbs/verify-verb boundary, moving the `verify` section's tests and helpers unedited into a new sibling file named `test_cli_verify_verb.py` (matching the `test_cli_*` naming convention); the new private helpers in `__main__.py`, `_resolve_verify_head` and `_report_verify`, are also the implementor's naming choice.

## 4: Print the lock-timeout and HEAD-moved review-stage lines; restate the exit table; reword CHANGELOG

- The design's "line-22 writer-reuse claim" is the `normalize_command` bullet now at CHANGELOG line 24 (two lines were added to `[Unreleased]` since the design was written), since it is the only bullet about a stale `last-verification.json` going unreused; only its post-semicolon clause was replaced, as the design gave.
- CHANGELOG prose uses " - " instead of an em dash, per this user's writing-style rule against em dashes.
- `final-verification.md` gained one sentence stating the JSON `log` is `null` when no gate spawned, taken from the design's spawned/log rule; the design's own exit table did not include that sentence.
- The CHANGELOG carries four `[Unreleased]`/`### Fixed` bullets, one per defect group the design lists (exit rule, writer marker, orphaned-gate kill, lock-timeout/HEAD-moved labels); the exit-2 JSON line and the null-log behavior were folded into the exit-rule bullet rather than given their own.
- The style-fix split moved `run_gate_line`'s Tests:-line if/elif chain into a new private helper, `_gate_result_line(result) -> str`, with only this one caller — judged an allowed style-limit split even though the helper has a single consumer.

## Step 7 regression fixes (full-suite run surfaced 14 pre-existing-file regressions)

- `test_verification.py` was not in task 2's original six-test-file list but has the same hand-built-record-dict pattern, so its `writer`/`lock_timeout`/`head_moved` fixes follow the same shape as the six files task 2 did update.
- `SHA_REFUSAL`'s constant name was kept unchanged (only its value/comment updated to the `_head_moved_result()` shape) to keep the diff small, rather than renaming it to something like `HEAD_MOVED_REFUSAL`.
- The head-moved shape in `test_verification.py` was written out as a literal dict rather than calling `verification._head_moved_result()`, so the test still pins the exact field set independently of the production helper.
- The genuine production bug `test_concurrent_runs_serialize_on_the_gate_lock` and `test_held_gate_lock_blocks_before_the_log_open_and_record_delete` exposed (`signal.signal` raising `ValueError` off the main thread, because these two tests call `run_gate` from a worker thread) was fixed by gating the SIGTERM handler install/restore in `_spawn_gate` on `threading.current_thread() is threading.main_thread()` — a non-main-thread caller gets no SIGTERM handling, but the gate still spawns, drains and reaps normally; the `BaseException` kill-and-reraise path is unaffected since it never touched `signal.signal` itself.
