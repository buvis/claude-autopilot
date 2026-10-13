# Assumption ledger

Per-plan. Replaced at the first completed task of a full-plan pass.

Plan: PRD 00276 (make the gate record trustworthy), batch 202610111300.

## 4: verification: flock-serialize run_gate; invalidate the record at start; re-verify sha after the lock

Tess (test author):

- The flock is advisory and taken per open file, so a lock the test takes with its own `os.open` + `fcntl.flock(LOCK_EX)` on `<cwd>/docs/dev/tmp/gate.lock` blocks `run_gate`'s lock, even in the same process.
- `docs/dev/tmp/` is in the paths the dirty check ignores, so the lock file there does not make the tree dirty.
- "Refusing" on a sha mismatch means the gate command never runs, checked by a marker file outside the repo that must stay absent.
- Treated the new stale-sha test (sha argument already behind HEAD, no lock contention) as asked for by Devon's feedback, not as an unrequested extra test.
- A 1s gate timeout is enough for the shell to run the probe line before it is killed.

Ivan (implementor):

- The log opens after the sha re-check and before the record delete; the contract only says no log opens on a refusal path and that the lock is taken before the log opens.
- In `test_run_gate_writes_last_verification_json_on_fresh_run` and `test_run_gate_writes_the_normalized_command`, the expected record's literal placeholder sha was swapped for the real HEAD the call now passes, since the record echoes the sha argument.
- In `test_verification_hidden_flags.py`, `_run_passing_gate` gained an optional `sha: str = "abc"` parameter; only the one test that needs the gate to actually run passes HEAD explicitly (flagged by Pat's review as a latent weak default, not fixed in this task).
- Closing `log_file` in the extracted `_run_locked_gate`'s own `finally` instead of `run_gate`'s satisfies "release in the same finally that already closes log_file" by effect (same ordering on every path) rather than literal placement, because the 50-line style cap forced splitting `run_gate` into two helpers after the first implementation landed.

Orchestrator note (not an implementor assumption, recorded for visibility): the sha re-check as contracted makes every pre-existing `run_gate` test that passed a placeholder sha ("abc", "cafe", "deadbeef", "f00d") and expected the gate to actually run fail, across this task's own test file plus `test_verification_dirty.py`, `test_verification_dirty_paths.py`, and `test_verification_hidden_flags.py` (none in this task's original `files` list). Resolved by updating each such call site to pass the real current HEAD instead of a placeholder, preserving what each test asserts. Call sites that expect a refusal, or that run outside a git repo, kept the placeholder.

## 5: verification: a log-sink write error kills and reaps the gate's process group; refuse a tracked --log destination

Orchestrator premise check: the task's own Premise line claimed PRD 00274 already fixed the kill/reap-on-sink-error behavior. Read `_drain_bounded`/`_reap` before dispatching anything: the claim was false -- `sink.write(chunk)` had no error handling, so an `OSError` there propagated straight out without `_reap` ever running. Both (a) and (b) were implemented.

Tess (test author):

- The new tests live in a new sibling file, `test_verification_log_sink.py`, not `test_verification.py` as the task's own Verify line names -- `test_verification.py` is already at the 800-line cap. Flagged for the orchestrator to override, per the existing split pattern (`test_verification_dirty_paths.py`).
- The failing sink is injected by monkeypatching `verification._drain_bounded` to hand the real drain a sink that raises -- this seam breaks if the drain call is renamed or bypassed.
- `OSError(errno.ENOSPC)` (and, after strengthening, EIO/EFBIG) stands in for a full disk; the test asserts the same errno comes out of `run_gate` unchanged.
- With cwd at a subdirectory, the tracked-log refusal still names the toplevel-relative path.
- Devon flagged two of his own weak-point reports (kill-before-unlock ordering, and dirty_paths listing only the tracked path when other paths are also dirty) as his own inference, not spec-stated; Tess marked both in-contract rather than strengthening, since the design doc's step 2.5 returns `_dirty_result([log_path_toplevel])` before the dirty check runs, and the contract only says the flock "must still be released" without ordering kill vs. unlock.

Ivan (implementor):

- Registered the new test file's new/test git call surface via a module-level `_tracked_log_path` helper that duplicates `_untracked_log_exclusion`'s toplevel/relative-path logic rather than refactoring the existing function, to keep the change surgical (flagged by Pat's review as a duplicate-git-call inefficiency, not fixed in this task).
- Copied `_reap`'s unguarded `os.killpg` + `wait` exactly for the sink-error kill path, with no `ProcessLookupError` guard, per the brief's instruction to mirror `_reap`'s pattern (flagged by Pat's review as a latent gap if `killpg` itself raises, not fixed in this task).
- The kill/reap handler catches `OSError` only, per the task text's own framing ("OSError, e.g. the log file's disk fills or the fd is closed underneath it"); Pat's review noted a closed Python file object actually raises `ValueError` on write, which this handler would not catch -- not fixed in this task, as it is outside what the task described.

## 6: verification: reuse_verdict refuses reuse when a product symlink aliases a changed store path, committed or uncommitted

Tess (test author):

- Split the 3 contract-required tests into a new sibling file, `test_verification_dirty_symlink.py` (the PRD-named test stayed in `test_verification_dirty.py`, as its acceptance criterion requires), since the latter was at 766/800 lines.
- A symlink is "outside the store" when the symlink's own path is outside `docs/dev/project-management/`.
- A staged-but-uncommitted edit to the aliased store file counts as uncommitted and is stale.
- After Devon's exploits: Devon's weak points 6 (absolute symlink targets) and 7 (symlink chains) were marked in-contract, since the task's own contract text explicitly scopes both out ("an accepted, recorded gap, not fixed here"). The remaining 6 weak points were strengthened or added as new tests, including a 3-deep nested symlink and a repo_root-below-toplevel case (following `test_store_only_change_below_toplevel_is_reused`'s `root = repo / "sub"` pattern).

Ivan (implementor):

- Computed the store prefix via a new `_store_roots` helper (the `STORE_PREFIXES` tuple, not the single `STORE_PREFIX`) rather than reusing `_ancestor_and_clean`'s own `store` variable, since the two serve different helpers; this means `git rev-parse --show-prefix` runs more than once per `reuse_verdict` call (flagged by Pat's review as a duplication/performance LOW, not fixed in this task).
- Used `git ls-files -s -z --full-name` so symlink paths come out toplevel-relative, matching the status/diff paths, including when `repo_root` sits below the toplevel.
- A symlink resolving to `"."` (e.g. a one-level-deep `x -> ..`) is not specially handled -- `p.startswith("./")` never matches, so this edge case silently fails to alias (flagged by Pat's review as bordering the recorded single-hop gap, not fixed in this task).
- Orchestrator verified Pat's one MEDIUM finding (a git failure in the new helpers could escape `reuse_verdict` as an uncaught exception) against the code and found it FALSE: `reuse_verdict` already wraps its `_ancestor_and_clean` call in `try/except OSError`, and `_GitProbeFailed` (raised by all three new helpers) is an `OSError` subclass. Discarded, not fixed.

## 7: cli: verify refuses a store-resolving or tracked --log, joins relative --log against --repo-root, exits 3 when green but unrecorded, prints dirty_paths

Tess (test author):

- The exit-3 test patches `cli.verification.run_gate` with a hand-built result (keys: exit, timed_out, dirty, dirty_paths, recorded, passed), because no black-box trigger for a green/clean/unrecorded run was found without reading `verification.py` (blind-lens rule).
- "Resolves" means the path lands in the store after `..` is collapsed and the arg is joined to `--repo-root`; symlinks were not tested in the initial pass (added after Devon's exploit).
- Refused runs print nothing on stdout (`captured.out == ""`), and stderr carries the original `--log` argument text (not the resolved path).
- `dirty_paths` entries are repo-relative POSIX paths, matched by substring in the first pass, then by exact list equality after strengthening.
- After Devon's exploits: all 7 weak points were strengthened (untracked-log-is-not-automatically-refused, force-added tracked file under docs/dev/tmp, symlink into the store, store check scoped to `<repo>/docs/dev/project-management` not any path containing that name, an absolute out-of-repo log is never redirected, the exit-3 hand-built result uses the full real `run_gate` key set with a mirror exit-0 case, and a `timed_out=True` green-shaped result must exit 1). None were marked in-contract.

Ivan (implementor):

- The dirty case exits 1 unconditionally ("not dirty" required for exit 0/3), which also silently fixes a pre-existing docstring/code mismatch (the docstring already said dirty means exit 1; the old code returned 0 for a dirty-but-green run). Not flagged as a separate finding since it is exactly what the task's own contract specifies.
- Extracted `_refuse_verify_log` (one fix dispatch) to bring `_run_verify` under the 50-line style cap; no behavior change.
- Pat's review (LOW) noted the `return 3 if not result["recorded"] and not result["dirty"] else 0` line could make the dirty exclusion more explicit; left as-is since the surrounding `if result["exit"] == 0 and not result["timed_out"]:` already guards entry and a real dirty+exit-0 result cannot reach that line given `run_gate`'s own `_record_gate`/`_dirty_result` shapes -- not fixed in this task, Pat flagged it as defensive-only.
- Pat's second LOW (duplicated record-seeding setup across three new tests) was not fixed -- a test-file behavior-preserving refactor out of scope for this task's contract.
