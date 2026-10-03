## 1: Gate the summary tests (00221)

- I treated the existing (already-uncommitted) `test_every_wave_test_file_is_listed` function as the one the brief asked for, since only the formatter's line join differed from the spec, and did not rewrite it from scratch.
- Ran pytest via `uv run --no-project --with pytest` because system `python3` has no pytest installed.
- (strengthening pass) Same `uv run --with pytest` assumption repeated.
- (strengthening pass) The `ast` duplicate-assignment check scans only top-level `Assign` nodes; an annotated (`AnnAssign`) or augmented reassignment of `_WAVE_TEST_FILES` would not be counted as a second assignment. Fine for today's plain assignment.
- (Ivan) None reported.

## 5: Switch the assembly worktree gate to foreign_dirty and hold the seeded backlog (00225)

- (Tess, initial) Used `wave_assemble._default_run_git` as the `run_git` argument to `_land_cleanup` in both tests - the contract doesn't name a fake; this is the same default `_check_reviewable`/`review()` rely on elsewhere in the file.
- (Tess, initial) Represented "foreign dirt beside store churn" with one case (`readme_edited`) rather than the full `FOREIGN_CASES` matrix, per SIMPLICITY FIRST.
- (Tess, initial) Assumed backlog PRDs for the "seeded backlog" test can be plain unstaged files written directly into the worktree's `prds/backlog/` before `seed_state` runs, rather than first committing them in the main repo.
- (Tess, strengthen) Git's default rename detection means point 5's "lists ... as added" can't be asserted via an `A\t` prefix; asserted the destination path's presence in the diff instead.
- (Tess, strengthen) Point 8 ("call seed_state a second time... assert HEAD unchanged") interpreted as the fail-then-retry scenario the codebase already supports, not a second call after a fully successful run (the real CLI steps reject a second `phase-done` once phase is already `review`).
- (Tess, strengthen) Did not add a non-md-file assertion to the `_seed_with_backlog`/retry helper, since point 7 is specific to the test named in the brief.
- (Ivan, initial) `branch -D` assumed acceptable in `_land_cleanup` (flagged for review attention; the per-task reviewer caught this and it was reverted to `-d`).
- (Ivan, initial) The hold commit uses pathspec `prds`, so it also picks up other edits to tracked files under `prds/` that are not staged; untracked files like a new wip stub are not included.
- (Ivan, initial) Backlog PRDs may be tracked, untracked, or gitignored; `rm --cached --ignore-unmatch` plus `add -f` handles both.
- (Ivan, retry) `cli/test_wave_review_cleanup.py` assumed to be the right test file to check, since it is the only test that references `_land_cleanup`.

## 6: Land after a hand review (00226)

- (Tess, initial) "Without writing any stub" means the stub must be absent from the worktree's `prds/done/`. Removed it by `git rm` plus commit, not an uncommitted delete, so the result doesn't depend on any dirty-tree check in the review_failed path.
- (Tess, initial) In the hand-reviewed test, the stub content must match what `_landable` already committed, to avoid tripping the pre-removal dirty check.
- (Tess, initial) After a hand-reviewed land, the stub should appear in the main repo's `prds/done/` - the same migration the converged path already does.
- (Tess, strengthen) A hand-reviewed wave reuses the converged path's existing summary-line format `"## Assembly review: converged (1 cycle(s)), landed <tip>"`, with the cycle count read from the worktree's `state.json`.
- (Tess, strengthen) The master-moved sibling does not assert the persisted `wave.json` status (it would be "converged" after the flip) - only the "nothing landed or removed" effects are pinned.
- (Ivan) The hand-review signal is only "the stub file exists in the worktree's prds/done/". No commit is needed, and wave.json is not re-checked.
- (Ivan) A hand-reviewed land never writes the review_failed summary line - only the converged one, as the test's single "## Assembly review:" count requires.

## 7: Document the hand-review route and changelog the six fixes

- (Ivan) The "existing sentence" ends with its parenthetical "(no git write).", so the new sentence goes after that and not in the middle of the parenthetical.

## 8: [D1] Save converged on the hand-review land route (00226) (S)

- (Ivan) The brief's description of `_land_review_failed`'s new behavior ("gains a wave_path param... returns None and saves converged on the hand-reviewed path") meant the hand-reviewed-stub-exists check itself moves inside `_land_review_failed`, rather than staying in `land()` with `_land_review_failed` only ever handling the no-stub case. Both constructions are observably equivalent against the given tests, but the docstring's phrasing only makes sense if `_land_review_failed` owns that branch, so this was not treated as a real ambiguity.

## 9: [D1] Retry the branch delete on rerun and widen the OSError guard (00222) (S)

- (Tess) "Re-run the SAME single-lane scenario fresh" read literally as pytest's own `tmp_path_factory.mktemp(...)` mechanism for a genuinely fresh temp directory, rather than reusing the same `tmp_path`.
- (Tess) Used a named nested function `boom` to raise the OSError (matching this file's own existing idiom), rather than the generator-lambda form the brief offered as an alternative - the brief allowed either.
- (Tess) Exact test/helper names and placement within each file were her own choice; the brief specified required behavior and conventions to follow, not exact names or line position.
- (Ivan) The fix for the branch-delete retry belongs in `_drain_lane`'s early-return branch itself (duplicating the two-line branch-delete check rather than extracting a helper), since that is the only place that can see "worktree already gone, branch maybe not" on a rerun, and there are only two call sites.
- (Ivan) No `lane["status"] == "assembled"` guard was added before the early-return branch-delete check, since `worktree_removed` is only ever set inside the `status == "assembled"` block, so status is already guaranteed assembled whenever that early return is reached.

## 10: [D1] Restore the PRD's acceptance test ids and make them fail-first (00221, 00225) (M)

- (Ivan) Items 2 and 3's hand demonstrations both needed the same temporary `wave_review.py` edit (disabling the `_hold_backlog` call site), so they were combined into one sequence instead of two separate edit/restore cycles - the net effect and evidence gathered are identical.
- (Ivan) Treated the task's own explicit "Verify (run exactly these, in order, as your final check before reporting)" section, which names `bash dev/bin/release-checks` as a required final command, as superseding the generic rule against running the full suite inside a task dispatch - this task's brief is more specific and one of its sub-items depends on that command's output.

## 11: [D1] Make _hold_backlog safe under partial failure (00225) (S)

- (Tess) Simulated the commit failure via `subprocess.CalledProcessError` raised directly by a monkeypatched `_default_run_git` (one of two exception types the brief offered as equally valid) rather than `RuntimeError`.
- (Tess) Asserted a generic `Exception` type for the collision refusal (the brief explicitly offered either `Exception` or `ValueError` as defensible) and asserted the exception message contains the full absolute paths of both the backlog and hold files.
- (Tess) Both new tests call `_hold_backlog` directly rather than through `seed_state`, per the brief's explicit "your choice" - this keeps each test isolated to the function under test.
- (Tess) Added `(pm / "prds" / "hold").mkdir(parents=True, exist_ok=True)` to test 1's setup, mirroring the precondition `seed_state`'s earlier steps already guarantee for the other tests in this file - calling `_hold_backlog` directly bypasses that guarantee.
- (Ivan, review retry 1) Added a new git subcommand (`ls-files --others --exclude-standard`) to detect held-but-uncommitted files on disk, since `diff --cached` alone cannot see untracked files - necessary to cover a failure at `rm --cached` before anything is staged.
- (Ivan, review retry 1) Kept `names` in the three-way union (`names | staged | untracked`) defensively, even though `untracked` alone already covers freshly-renamed files once the rename loop has run.
- (Ivan, review retry 1) Moved the no-op guard to run after the rename loop and the staged/untracked recomputation (rather than before, as in the original code), since the fix requires detection to happen after renaming - this costs two extra git calls in the true-no-op case but is otherwise behavior-equivalent.

## 13: [D2] Tail sweep: close the cycle-2 medium/low tail on the wave slot lock, hold-backlog and drain-lane paths (M)

- (Tess) Took the lock through the module-level `_slot_lock` seam rather than patching `builtins.open`, because the brief offered either and the lock's file-opening shape was not visible from the interface notes; the vanish-before-lock test wraps it with a `*args, **kwargs` shim. Both tests ran as intended against the pre-fix code.
- (Tess) For the vanish-before-lock case, asserted only "no raise and nothing created", not stderr content, since the brief is silent on output there.
- (Tess) `_crash_on_hold_backlog_step` matches the first git call carrying `rm` or `add` as a list element and then restores real git; this assumes `_hold_backlog` renames before its first `rm`, which the brief states.
- (Tess) The space-in-name tests pre-create `prds/hold/`, mirroring the existing retry test; whether `_hold_backlog` creates it itself is untested.
- (Tess) A filename containing a space appears unquoted in `git show --name-only`, which held when run.
- (Ivan) The `-z` queries need no `core.quotePath` handling, because `-z` output is unquoted.
- (Ivan) Placed `_delete_lane_branch` directly above `_drain_lane` and `_pending_hold_names` directly above `_hold_backlog`.
