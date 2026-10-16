# Assumption ledger

## PRD 00320-refuse-every-unsafe-verify-log-sink-v2

### Task 2 (implement the six-case refusal and exclusive sink open)

- `_open_log_sink` is handed the repo root as `root` (default `/`) so the
  strict `O_NOFOLLOW` descent starts at the trust boundary. The repo's OWN
  path is trusted: a checkout reached through a symlinked ancestor (a repo
  under macOS `/tmp`) is normal and must not be refused, while everything
  below the root is walked strictly. The design doc's contract gave
  `_open_log_sink(log_path)` only and told it to walk "from the toplevel
  downward", which the one-argument signature cannot do; the added parameter
  is what makes the documented walk possible, and `_run_locked_gate` passes
  `cwd`.
- The sink is created with mode `0o666` (builtin `open`'s mode), not
  `os.open`'s `0o777` default -- an executable sink would make the next run
  refuse its own log.
- Case 1 refuses a literal `docs/dev/project-management/` prefix match in
  addition to the inode walk, so a store path whose directory does not exist
  yet is still refused (it has no inode to compare).
- A failing `git rev-parse --show-toplevel` from `repo_root` fails closed as
  `resolves outside the repository`.
- Case 3's component walk can report a path outside the repo as
  `is a symlink` rather than `resolves outside the repository`; no test pins
  the reason text for that path, only exit 2.
- `repo_root` reaching `refuse()` is always absolute (as `__main__` and
  `run_gate`'s `cwd` provide it), so the walk's stop test matches by path
  equality; a relative `repo_root` would not stop the walk.
- A root/log spelling mismatch in `_pinned_parent_fd` raises `OSError`
  rather than `ValueError`, so a caller's existing handling of a refused
  sink covers it.
- The symlinked-root regression test asserts on `log_sink_refusal.refuse`
  directly rather than through a CLI `verify` run, to keep the two findings
  it separates from conflating.

## PRD 00321-cap-check-classifies-every-cell-and-records-what-it-parks-v2

### Task 1 (pin the test contract)

- "Adds line 4 of a.py" means inserting a new line 4 in the second rework
  commit, together with `b.py` and `café.py`, so `rework_short` keeps its
  existing meaning for pre-existing tests.
- Exit-2 `_verify_range` stderr is checked loosely by substring family
  rather than one exact string per condition.
- The unresolved-row `reason` is pinned verbatim as `unresolved path
  missing.py`, per the contract's f-string.

### Task 2 (implement the parser and range proof)

- A `null` row keeps `"commit": null` and adds a `"reason"` key — the dict
  shape stays the same with one optional extra key.
- In a multi-path cell, the row's `file`/`line` name the pair that decided
  the verdict: the first missing path for `null`, the first regressing pair
  for `true`, otherwise the first pair.
- A comma-separated line list (`a.py:3,9`) still blames only its first
  line, as before `_parse_file_cell` existed — the PRD's named test shapes
  stop short of requiring every comma-listed line blamed, only a dash
  range's every line.
- `_verify_range` uses `git rev-parse --verify --quiet`; its failure
  message says the sha "does not resolve to a commit".
- Two pre-existing `test_cap_check.py` tests (`test_rows_outside_
  rework_range_are_not_regressions`, `test_deleted_file_only_row_is_not_a_
  regression`) asserted the OLD "gone path -> False" behavior; updated to
  assert `None`, since a gone path is now unresolved by contract, not a
  fixed test weakened to dodge a bug.

### Task 3 (wire the stall site and prose)

- The `records.py` migration of pending `deferred_decisions` is gated on
  `cap_regression` only, not both `cap_regression` and `cap_critical` — the
  design doc's draft gate (both sites) broke an existing custody failpoint
  test, because `cap_critical` already migrates pending deferrals inside
  `custody.record_critical`, under the marker lock, after that failpoint.
  Adding the step at the earlier `do_stall` splice point for `cap_critical`
  too would have run it twice. This is a deliberate, verified narrowing of
  the design doc, not an oversight.
- Migrated records reuse `custody.migration_records`'s existing shape
  (`<op_id>-dd<i>` ids, pending-only filter, stamped cycle/type defaults),
  so both stall sites write the same ledger row shape.
- `phase-review.md`'s mint-stubs step names the batch argument by
  reference ("the same `--batch` argument as the `cap_critical` branch
  above") rather than repeating the full `autopilot mint-stubs --batch`
  string, because a second literal copy failed the prose-pin test's
  one-call-per-bullet rule.
