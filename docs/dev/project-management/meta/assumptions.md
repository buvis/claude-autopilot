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
