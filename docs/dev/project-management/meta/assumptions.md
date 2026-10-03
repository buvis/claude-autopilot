# Assumption ledger

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
