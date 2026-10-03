## 1: Gate the summary tests (00221)

- I treated the existing (already-uncommitted) `test_every_wave_test_file_is_listed` function as the one the brief asked for, since only the formatter's line join differed from the spec, and did not rewrite it from scratch.
- Ran pytest via `uv run --no-project --with pytest` because system `python3` has no pytest installed.
- (strengthening pass) Same `uv run --with pytest` assumption repeated.
- (strengthening pass) The `ast` duplicate-assignment check scans only top-level `Assign` nodes; an annotated (`AnnAssign`) or augmented reassignment of `_WAVE_TEST_FILES` would not be counted as a second assignment. Fine for today's plain assignment.
- (Ivan) None reported.
