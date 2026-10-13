# Decision Audit Log: 00276-make-the-gate-record-trustworthy-v1

PRD: `00276-make-the-gate-record-trustworthy-v1.md`
Started: 2026-10-13T04:58:38Z
Completed: 2026-10-13T04:58:38Z
Autonomous: 20  |  Deferred: 20  |  Doubts: 0

### [autonomous] 2026-10-13T04:58:38Z

**Decision**: [R1] `verify` exits 0 when the tree turns dirty after the gate ran and no record was written. `_run_verify` returns `3 if not recorded and not dirty else 0`, so exit 0, dirty True and recorded False falls to 0. The PRD success metric says "verify exits non-zero whenever it wrote no record". Fix: test `not dirty` before the `recorded` branch and return non-zero for any dirty result; flip test_verify_dirtied_during_the_run_still_reports_the_process_exit, which pins the wrong behavior.

**Choice**: auto-fix (queued as a cycle-1 rework task)

**Rationale**: Protocol D (high + public API: the verify exit codes are the documented contract). The PRD states both the success metric (exits non-zero whenever it wrote no record) and the exact code (exit 3 when green, not timed out, recorded false), so the PRD requires the change and specifies the behavior. Verdict: proceed. Unanimous 3/3 across consensus, blind and doubt lenses.

### [autonomous] 2026-10-13T04:58:38Z

**Decision**: [R2] `_tracked_log_path` and `_untracked_log_exclusion` both do the same work: find the toplevel, compute the resolved toplevel-relative POSIX path, and run `ls-files --error-unmatch`. Fold them into one helper that returns (rel, tracked).

**Choice**: auto-fix (queued as a cycle-1 rework task)

**Rationale**: Auto-fix: low or medium severity with a clear mechanical fix, or an additive-only change (docstring, test strengthening, guard, dedup). No signature, schema or public interface is modified beyond what the PRD already specifies.

### [autonomous] 2026-10-13T04:58:38Z

**Decision**: [R3] The `gate.lock` wait is unbounded and the PRD's expiry behavior is missing. The PRD says the wait is bounded by the gate timeout and on expiry the second caller returns the timed-out result and writes nothing. `_lock_and_check` calls a blocking `fcntl.flock(lock_fd, fcntl.LOCK_EX)` with no timeout or `LOCK_NB` loop, so a hung or orphaned holder blocks every later `verify` indefinitely.

**Choice**: auto-fix (queued as a cycle-1 rework task)

**Rationale**: Spec compliance, not a design decision: the PRD states verbatim that the wait is bounded by the gate timeout and that on expiry the second caller returns the timed-out result and writes nothing. The code implements neither, so this is unimplemented specified behavior rather than a judgment call.

### [autonomous] 2026-10-13T04:58:38Z

**Decision**: [R4] Hidden-flag handling violates the required flag-alone refusal. `_hidden_flag_edits` compares content hashes instead, overlooking executable-bit changes and potentially treating a replacement symlink as unchanged when its referent matches the indexed bytes. The PRD says any `S` or lowercase `ls-files -v` tag outside the store counts as dirty, in one extra git call. Return every flagged outside-store path as required; remove the hashing branch and reverse the flag-alone acceptance test.

**Choice**: auto-fix (queued as a cycle-1 rework task)

**Rationale**: Spec compliance: the PRD states any S or lowercase ls-files -v tag outside the store counts as dirty, in one extra git call. The code hashes content instead, which misses mode-only changes. Alice (R6) and Blake (R10) raised the same deviation at medium, so this is a 3/3 defect split across severities and fixed once.

### [autonomous] 2026-10-13T04:58:38Z

**Decision**: [R5] A single-hop directory symlink resolving to the repository root escapes staleness detection: `src/root -> ..` normalizes to `"."`, while store paths never start with `"./"`. Treat `"."` as an ancestor of every repository-relative store path and add committed/uncommitted regression cases.

**Choice**: auto-fix (queued as a cycle-1 rework task)

**Rationale**: Spec compliance within the stated packet-16 scope (relative, single-hop directory aliases): a parent-dir symlink normalizing to a bare dot escapes the ancestor test, so a real store edit behind a product symlink reads as reusable.

### [autonomous] 2026-10-13T04:58:38Z

**Decision**: [R6] `_hidden_flag_edits` does not treat every skip-worktree or assume-unchanged path outside the store as dirt. It only counts a flagged path when its work-tree content differs from the index blob or the file is missing, where the PRD and design say any `S` or lowercase `ls-files -v` tag outside the store counts as dirty. test_hidden_flag_alone_without_an_edit_is_not_dirt enshrines the narrower behavior.

**Choice**: auto-fix (queued as a cycle-1 rework task)

**Rationale**: Auto-fix: low or medium severity with a clear mechanical fix, or an additive-only change (docstring, test strengthening, guard, dedup). No signature, schema or public interface is modified beyond what the PRD already specifies.

### [autonomous] 2026-10-13T04:58:38Z

**Decision**: [R7] `_dirty_outside_store_paths` repeats the `rev-parse --show-prefix` and `prefix + STORE_PREFIXES` logic that `_store_roots` already holds. Replace the inline block with `store = _store_roots(repo_root)`. The status scan is also duplicated between `_dirty_store_paths` and `_dirty_outside_store_paths`.

**Choice**: auto-fix (queued as a cycle-1 rework task)

**Rationale**: Auto-fix: low or medium severity with a clear mechanical fix, or an additive-only change (docstring, test strengthening, guard, dedup). No signature, schema or public interface is modified beyond what the PRD already specifies.

### [autonomous] 2026-10-13T04:58:38Z

**Decision**: [R8] The `reuse_verdict` and `_ancestor_and_clean` docstrings, which list the conditions for "reused", do not mention the new symlink-alias staleness checks (committed and uncommitted). Add them to the "Returns reused only when ALL hold" list.

**Choice**: auto-fix (queued as a cycle-1 rework task)

**Rationale**: Auto-fix: low or medium severity with a clear mechanical fix, or an additive-only change (docstring, test strengthening, guard, dedup). No signature, schema or public interface is modified beyond what the PRD already specifies.

### [autonomous] 2026-10-13T04:58:38Z

**Decision**: [R9] Scope creep: a tracked-file `--log` refusal that the spec does not ask for. `_refuse_verify_log` adds an exit-2 path ("resolves to a tracked file"), `run_gate` adds a `_tracked_log_path` refusal returning `_dirty_result`, and the docstring and `final-verification.md` document both. The spec asks only for the store-resolving refusal. `run_gate` also runs its tracked-log check after taking the lock but before the dirty check, so it reports a different `dirty_paths`.

**Choice**: auto-fix (queued as a cycle-1 rework task)

**Rationale**: Auto-fix: low or medium severity with a clear mechanical fix, or an additive-only change (docstring, test strengthening, guard, dedup). No signature, schema or public interface is modified beyond what the PRD already specifies.

### [autonomous] 2026-10-13T04:58:38Z

**Decision**: [R10] Hidden-flag rule deviates from the spec. The spec says the tree is dirty when `ls-files -v` shows an `S` or lowercase tag outside the store, with one extra git call. `_hidden_flag_edits` counts a flagged path only if its work-tree content differs from the index blob or the file is gone, and makes three or more git calls. A flagged symlink or gitlink makes `hash-object` follow the symlink or fail.

**Choice**: auto-fix (queued as a cycle-1 rework task)

**Rationale**: Auto-fix: low or medium severity with a clear mechanical fix, or an additive-only change (docstring, test strengthening, guard, dedup). No signature, schema or public interface is modified beyond what the PRD already specifies.

### [autonomous] 2026-10-13T04:58:38Z

**Decision**: [R11] Hidden-edit refusal tests pass `"abc"` as the SHA and assert only refusal. The new SHA check independently produces that result even if hidden-edit detection is removed. Pass actual HEAD and assert the offending `dirty_paths`; verify these tests fail with the hidden-flag scan disabled.

**Choice**: auto-fix (queued as a cycle-1 rework task)

**Rationale**: Auto-fix: low or medium severity with a clear mechanical fix, or an additive-only change (docstring, test strengthening, guard, dedup). No signature, schema or public interface is modified beyond what the PRD already specifies.

### [autonomous] 2026-10-13T04:58:38Z

**Decision**: [R12] `_run_verify` checks resolved paths but passes and prints the unresolved path, contrary to its contract; it also skips CLI validation for the default destination. Resolve the selected destination once, validate both explicit and default destinations before `run_gate`, then pass and print that same path.

**Choice**: auto-fix (queued as a cycle-1 rework task)

**Rationale**: Auto-fix: low or medium severity with a clear mechanical fix, or an additive-only change (docstring, test strengthening, guard, dedup). No signature, schema or public interface is modified beyond what the PRD already specifies.

### [autonomous] 2026-10-13T04:58:38Z

**Decision**: [R13] Drive-by edits unrelated to the task: `text[len(shell) :]` was reflowed in `normalize_command`, and one docstring line in `_dirty_outside_store_paths` is over-long. Both look like the formatter pass; revert them.

**Choice**: auto-fix (queued as a cycle-1 rework task)

**Rationale**: Auto-fix: low or medium severity with a clear mechanical fix, or an additive-only change (docstring, test strengthening, guard, dedup). No signature, schema or public interface is modified beyond what the PRD already specifies.

### [autonomous] 2026-10-13T04:58:38Z

**Decision**: [R14] In the log-sink error path, `os.killpg` in `_run_locked_gate` can raise `ProcessLookupError`, which is an OSError. That would mask the original sink error and skip `proc.wait()`, leaving a zombie. Guard the `killpg` call.

**Choice**: auto-fix (queued as a cycle-1 rework task)

**Rationale**: Auto-fix: low or medium severity with a clear mechanical fix, or an additive-only change (docstring, test strengthening, guard, dedup). No signature, schema or public interface is modified beyond what the PRD already specifies.

### [autonomous] 2026-10-13T04:58:38Z

**Decision**: [R15] The symlink-reuse check lives in `_ancestor_and_clean`, not in `reuse_verdict` as the spec words it. The behavior is equivalent, since `reuse_verdict` calls it, and a git failure becomes stale through `OSError`. Note the placement in the docstring so the spec and the code agree.

**Choice**: auto-fix (queued as a cycle-1 rework task)

**Rationale**: Auto-fix: low or medium severity with a clear mechanical fix, or an additive-only change (docstring, test strengthening, guard, dedup). No signature, schema or public interface is modified beyond what the PRD already specifies.

### [autonomous] 2026-10-13T04:58:38Z

**Decision**: [R16] `_hidden_flag_edits` and `_untracked_log_exclusion` swallow some git failures into "no exclusion" or "no log". Both fail toward refusing or re-running, so this is acceptable. `_tracked_log_path` has no try/except around `resolve()`, though that is low risk.

**Choice**: auto-fix (queued as a cycle-1 rework task)

**Rationale**: Auto-fix: low or medium severity with a clear mechanical fix, or an additive-only change (docstring, test strengthening, guard, dedup). No signature, schema or public interface is modified beyond what the PRD already specifies.

### [autonomous] 2026-10-13T04:58:38Z

**Decision**: [R17] The new tests sit in files other than those named in the PRD (`test_verification_dirty_paths.py`, `test_verification_hidden_flags.py`, `test_verification_log_sink.py`). The test names match. Record the file placement so the PRD's named layout and the shipped layout agree.

**Choice**: auto-fix (queued as a cycle-1 rework task)

**Rationale**: Auto-fix: low or medium severity with a clear mechanical fix, or an additive-only change (docstring, test strengthening, guard, dedup). No signature, schema or public interface is modified beyond what the PRD already specifies.

### [autonomous] 2026-10-13T04:58:38Z

**Decision**: Carl (gemini) failed both his dispatch and his retry with copilot exit 1, Authentication failed.

**Choice**: logged and continued with the remaining three lenses

**Rationale**: Safety Checks row: a transient reviewer failure degrades gracefully. Exit 1 is a runtime failure, not the exit-4 permanent shape, so no batch latch was written and the next cycle tries him again.

### [autonomous] 2026-10-13T04:58:38Z

**Decision**: consolidate_findings.py silently dropped all seven of Bob's findings because his doubt buckets emit dash-bullet lines and the parser anchors issue lines at column zero.

**Choice**: stripped the bullet prefix from his output file, retained the raw copy, re-ran the consolidator, and recorded the normalization in the review file

**Rationale**: A silent drop of a whole lens is the one failure the consolidation step forbids. The same defect hit the previous PRD review (00285 cycle 1) and is a pack bug outside this PRD's diff, so it is surfaced rather than fixed here.

### [autonomous] 2026-10-13T04:58:38Z

**Decision**: Bob (doubt lens): mid-run dirt returns exit 3 where task 7 allegedly requires exit 1

**Choice**: discarded

**Rationale**: Contradicts the PRD: task 7 reads "exit 3 when green but unrecorded" and the success metric is "verify exits non-zero whenever it wrote no record"; exit 3 satisfies both, and cycle 1 R1 was fixed to this shape by three-lens consensus.

### [deferred] 2026-10-13T04:58:38Z

**Decision**: Absolute symlink targets and symlink chains remain outside reuse detection; the design explicitly accepts these limitations for this change.

**Rationale**: deferred by review-close

### [deferred] 2026-10-13T04:58:38Z

**Decision**: Existing unchanged functions exceed 50 lines, and `__main__.py` exceeds 800 lines according to the supplied mechanical facts; restructuring unrelated CLI code is outside this review's scope.

**Rationale**: deferred by review-close

### [deferred] 2026-10-13T04:58:38Z

**Decision**: 6 touched test(s) pass against the pre-change code: test_verify_accepts_a_store_like_path_outside_the_repo, test_verify_writes_an_absolute_out_of_repo_log_where_asked, test_verify_untracked_log_outside_the_store_still_works, test_verify_exits_2_when_the_log_cannot_be_opened, test_verify_exits_0_when_the_same_green_result_is_recorded, test_verify_exits_1_when_the_gate_timed_out_with_exit_0

**Rationale**: deferred by review-close

### [deferred] 2026-10-13T04:58:38Z

**Decision**: 10 touched test(s) pass against the pre-change code: test_run_gate_drains_stderr_without_deadlock, test_run_gate_unparseable_output_records_nothing, test_run_gate_keeps_tail_so_a_late_summary_line_still_parses, test_run_gate_streams_and_keeps_tail, test_run_gate_uses_last_summary_line_not_first, test_run_gate_closes_the_child_pipes_before_returning +4 more

**Rationale**: deferred by review-close

### [deferred] 2026-10-13T04:58:38Z

**Decision**: 35 touched test(s) pass against the pre-change code: test_reuse_when_only_store_paths_changed, test_stale_when_code_changed, test_reuse_verdict_fails_closed_on_git_error, test_reuse_verdict_rejects_non_ancestor_sha, test_reuse_verdict_rejects_dirty_tree, test_rename_out_of_store_is_not_clean +29 more

**Rationale**: deferred by review-close

### [deferred] 2026-10-13T04:58:38Z

**Decision**: The tracked-`--log` refusal was removed, but the design doc and tasks 5 and 7 still require it; `autopilot verify --log src/app.py` now truncates and overwrites tracked product code before any check. The PRD feature text names only the store check, so the PRD and the design doc conflict and cycle 1's R9 ruling settled it by dropping the safer behaviour. Restore the refusal, or record the conflict in the PRD and design doc so the contracts agree.

**Rationale**: rework cap reached with this finding unresolved

### [deferred] 2026-10-13T04:58:38Z

**Decision**: Two docs omit a path that exits 1 (pre-spawn dirty refusal, sha mismatch, lock-wait expiry, a `--log` refused by `run_gate`): both define exit 1 as "timed out or non-zero gate exit", so a reader cannot tell a dirty-tree refusal from a red suite.

**Rationale**: rework cap reached with this finding unresolved

### [deferred] 2026-10-13T04:58:38Z

**Decision**: Removing the tracked-log refusal reintroduces destructive writes: `verify --log src/app.py` truncates committed source before spawning the gate, and the changed tests explicitly require that overwrite. Restore both refusals and byte-preservation tests, including nested repo roots.

**Rationale**: rework cap reached with this finding unresolved

### [deferred] 2026-10-13T04:58:38Z

**Decision**: `_acquire_lock` catches every `OSError` as "lock busy"; only `BlockingIOError` means that for `LOCK_EX | LOCK_NB`, so a persistent `ENOLCK`/`EBADF` is polled for the whole timeout and then reported as a timed-out gate.

**Rationale**: rework cap reached with this finding unresolved

### [deferred] 2026-10-13T04:58:38Z

**Decision**: The `os.killpg` `ProcessLookupError` guard added for cycle-1 R14 has no test; make `os.killpg` raise it in the existing sink-error test and assert the original sink `OSError` still propagates and the child is reaped.

**Rationale**: rework cap reached with this finding unresolved

### [deferred] 2026-10-13T04:58:38Z

**Decision**: `_run_locked_gate` exceeds the 50-line limit once the kill-and-reap block was added; `_reap` already does `killpg`, `wait` and both pipe closes, so the sink-error `except` should call a shared helper carrying the `ProcessLookupError` guard.

**Rationale**: rework cap reached with this finding unresolved

### [deferred] 2026-10-13T04:58:38Z

**Decision**: `_hidden_flag_edits` no longer looks at edits (it returns every flagged path) yet still runs `ls-files -v -s` and unpacks `mode`, `blob` and `stage`; rename it and parse plain `ls-files -v -z` output as the design contract specifies.

**Rationale**: rework cap reached with this finding unresolved

### [deferred] 2026-10-13T04:58:38Z

**Decision**: Cycle-1 R7 is only half fixed: `_store_roots` is reused, but `_dirty_store_paths` and `_dirty_outside_store_paths` still duplicate the same `git status --porcelain=1 -z` call and record parse with the filter flipped.

**Rationale**: rework cap reached with this finding unresolved

### [deferred] 2026-10-13T04:58:38Z

**Decision**: `_acquire_lock` conceals permanent locking failures as contention until they surface as misleading timeout results; retry only contention errors, propagate the rest, and test that a non-contention error propagates immediately.

**Rationale**: rework cap reached with this finding unresolved

### [deferred] 2026-10-13T04:58:38Z

**Decision**: The hidden-flag scan retains machinery from the deleted hashing implementation (toplevel lookup, staged metadata, three unused fields); the design specifies a single `git ls-files -v -z --full-name` call parsing only tag and path.

**Rationale**: rework cap reached with this finding unresolved

### [deferred] 2026-10-13T04:58:38Z

**Decision**: The rework pushes `_run_locked_gate` to 52 lines and `run_gate` to 53 per the mechanical facts; both are changed functions, outside the settled exemption for unchanged oversized functions.

**Rationale**: rework cap reached with this finding unresolved

### [deferred] 2026-10-13T04:58:38Z

**Decision**: `_run_verify` resolves `log_path`, then `_refuse_verify_log` calls `.resolve()` again on the already-resolved path; drop the second call.

**Rationale**: rework cap reached with this finding unresolved

### [deferred] 2026-10-13T04:58:38Z

**Decision**: `run_gate` excludes its own log only when the log is untracked, where the PRD says to pass `log_path` as an extra excluded path; safer than the PRD and documented, but a recorded deviation.

**Rationale**: rework cap reached with this finding unresolved

### [deferred] 2026-10-13T04:58:38Z

**Decision**: `verify --log <tracked product file>` is not refused: `_run_locked_gate` opens it "wb" and truncates it before the gate runs. The record is correctly refused as dirty, but the file's content is lost (same defect family as R1/R3).

**Rationale**: rework cap reached with this finding unresolved

### [deferred] 2026-10-13T04:58:38Z

**Decision**: Extras beyond the PRD, all inside packets 16 and 2: `_store_symlink_targets_changed` handles a directory alias to the repo root and checks uncommitted store edits. The CHANGELOG records them.

**Rationale**: rework cap reached with this finding unresolved
