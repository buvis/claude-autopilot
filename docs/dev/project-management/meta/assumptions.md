# Assumptions ledger — PRD 00241 (bound rework batches by file)

Per-plan ledger of ASSUMPTIONS lines Tess and Ivan reported where the task,
tests, or listed files were silent. Replaced at the first completed task of
each plan, then appended to per task.

## 1: Write cli/rework_groups.py (the grouping rule)

- After `general` merges into another group, the merged group's key is not
  asserted (the spec does not say). The test only checks that general's
  findings are in the target group and that no `general` key remains.
- A directory key such as `p/q/r/` takes part in later prefix merges as the
  directory `p/q/r`. A root-level file (`y.py`) shares no directory with
  anything, so it merges as `mixed`.
- In the 00223 fixture, `N/A` is a plain file key, not `general`; its
  directory is `N`.
- The rule "merge prose when only prose and one other group remain above the
  cap" cannot trigger when the cap is 4, so it has no test.
- `file_key` takes only paths, `general` and `N/A`. Nothing tests empty or
  odd input, since the spec says nothing about it. `file_key` keeps a colon
  that is not a trailing `:<digits>` or `:<digits>-<digits>` suffix, so
  `"a.py:oops"` stays whole and `"C:/x/a.py:3"` becomes `"C:/x/a.py"`.
- Prose detection is "key ends in `.md`", per spec rule 3, so `a.md.bak` and
  `src/cmd.mdx.py` are not prose.
- The general merge only happens when there are more than 4 groups, and it
  never targets `prose`.
- When `prose` folds into the last remaining non-prose group (unreachable at
  `NON_CRITICAL_CAP = 4`, but implemented per spec), the merged group keeps
  that group's `name_hint` and `critical` value.
- An unknown severity counts as lower than LOW when sorting.
- Groups carry only the three fields the tests read (`name_hint`,
  `critical`, `findings`).

## 2: Add the group-rework CLI subparser

- "Unreadable file" is exercised by passing a directory path as
  `--findings` (triggers `OSError` on read) rather than chmod'ing a file to
  0 permissions, since the latter is flaky across sandboxed or
  root-executed test runs.
- No case for syntactically invalid (unparseable) JSON was added - the
  contract's Details section enumerates exactly three failure categories
  (missing file, unreadable file, valid-JSON-but-not-an-array).
- The exact stderr message text is not pinned, only that exactly one line
  is written.
- `--findings` is required, matching the other path-bearing flags like
  `--review-file` on `gate` - no default path is implied.
- Exit code 2 for malformed `--findings` input is a subcommand-local
  contract (like `gate`'s own 0/1/2 scheme), independent of the state-CLI's
  0-13 exit table, since `group-rework` takes no `--state`.

## 3: Wire Phase 6/Tail sweep to group-rework, release-checks, CHANGELOG

- The exact final indentation/bullet markup of the "Group first." bullet in
  Phase 6 and the exact paragraph boundaries around the Tail sweep "Split
  rule:" sentence are not pinned by the test (the window between "Group
  first." and the CRITICAL-D-tasks bullet, and the `\n\n` paragraph break
  after "**Split rule:**", matching sibling prose tests' slicing
  convention) - a false pass is possible only if the wording later moves
  across a landmark these tests anchor on.
- The new `### Changed` CHANGELOG subsection's position (before `### Fixed`,
  under `[Unreleased]`) follows the Added/Changed/Fixed ordering convention
  visible elsewhere in the file; the task only said to create it if absent,
  without specifying position relative to `### Fixed`.

## 7: [D1] Harden group-rework input handling, file_key normalization and the cap tests

- **Critical groups come out in input order, and that is deliberate** (the
  decision gate's ruling 3, recorded here as the ruling required). Rule 6's
  "then by severity, count, key" clauses order the non-critical groups only;
  "critical groups first" says nothing about their internal order, so the
  critical groups are never sorted. The existing test pins input order on
  purpose.
- The ` (lines a-b)` suffix is matched with a literal single space inside the
  parens, as every test case spells it. Other spellings (`(line 3)`,
  `(lines 3)`) are not stripped because no test names them.
- `N/A`-wrapping is accepted with any parenthesized tail, not only a
  path-looking one: the findings give two shapes and no counterexample of a
  non-general `n/a (...)`.
- `#L12-L14` style anchor ranges are not handled; the acceptance criteria name
  only `#L<digits>`.
- Ruling 2's "loops until the key is stable" is bound by
  `file_key("a/b.py#L12:7") == "a/b.py"`; the criteria never named a
  doubled-suffix form, so an anchor-plus-line pair was chosen.
- Error wording is the implementor's: `cannot read` for `OSError`,
  `cannot parse` for `ValueError`/`UnicodeDecodeError`, and one line naming a
  finding without a string `severity` and `file` for a malformed element. The
  tests assert only exit 2, empty stdout and exactly one stderr line.
- A usage error from a missing `--findings` exits via `SystemExit` with an
  unspecified code (observed 1, not argparse's default 2), so the test asserts
  the raise plus empty stdout rather than a specific code. Demanding 2 would
  have been an unrequested behavior change.
- Ruling 6's `IndexError` guard is **not reachable through the public API**:
  prose-only input always collapses to one group, so the fold branch needs a
  cap of 0 to reach an empty `code` list. The branch itself is driven by a test
  at a patched cap of 1; the guard is defensive and deliberately untested.
- The 00223 fixture's expected shape (4 tasks, sizes 2/5/12/21, `enter.py`
  separate, the rest of `cli/` under one directory key) is derived from the
  current tree plus ruling 1, not documented anywhere.
- Nothing pins whether a `general` merge keeps its target group's key or
  relabels it, so the tests locate that group by a finding it holds rather than
  by key.
- `test_design_rework_prose.py`'s unguarded `.index` lookup was removed with the
  redundant assertion that used it, rather than guarded in place. Deleting the
  line eliminates the bare-`ValueError` path the finding named; no other
  unguarded `.index` remains in that file.
- Duplicate merged `name_hint`s remain reachable in production (six
  single-finding files under one directory can yield two groups keyed the same).
  This task made the tests able to see a cap breach but did not change the
  merge rule, which no finding asked for.

## 6: [D1] Reconcile the Tail sweep split rule with step 2 and restore the ledger title

- Named the new prose test `test_tail_sweep_split_rule_states_findings_path_naming_and_floor`
  and wrote it as one combined assertion covering all three required clauses,
  rather than three separate test functions, matching the file's one-test-per-
  landmark-group pattern.
- Did not modify the module docstring, which still describes only the two
  pre-existing tests — only surgically added the new test function.
- Interpreted the "floor bounds only the upper end" instruction as: the 4-task
  cap is a ceiling, and a single group still produces exactly one task (floor
  of one, never zero) — the test only pins the literal word "floor", not a
  specific numeric claim.
- Restored the original PRD sentence verbatim per the reviewer's confirmed
  finding, then appended the three required clauses as new sentences
  immediately after it and before the closing "max-2-parallel" sentence, since
  no specific phrasing was mandated for the appended clauses beyond the facts
  themselves.
