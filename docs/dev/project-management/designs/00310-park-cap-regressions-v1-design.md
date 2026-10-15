# Design: Park a PRD at the rework cap when the last rework introduced a HIGH

## Architecture fit

`skills/run-autopilot/cli/` is the sole `state.json` mutator surface and the
home of every deterministic verb (`gate`, `stall`, `verify`, …) the phase
prose calls instead of hand-rolling logic. This PRD adds one more verb in the
same family: `cap-check`, a pure classifier with no state mutation of its
own. It sits beside `gate.py` (the review-file shape/coverage gate) and reuses
`findings_section.py`'s table parser — the same parser `gate --findings`
already uses to read `## Consolidated Findings` — so a findings-table format
change is read in one place, not two.

The stall mechanism this PRD routes into already exists and is generic:
`autopilot stall --prd <> --site <slug> --detail <>` (`cli/records.do_stall`,
documented in `references/recovery.md` § Loop-mode stall procedure) moves the
PRD to `hold/`, stamps a durable intent, appends a deferred record, and resets
per-PRD state in one commit — identical for `cap_critical` and any other
`site` string. `cap_regression` needs no new stall code, only a new slug and
a new caller: the cap-out bullet in `phase-review.md`.

## Module placement

- **New file**: `skills/run-autopilot/cli/cap_check.py` — `classify_findings()`,
  `rework_range()`, and the git/file-reading helpers they need.
- **Edit**: `skills/run-autopilot/cli/__main__.py` — add `_add_cap_check` /
  `_run_cap_check` and a `"cap-check": (_add_cap_check, _run_cap_check)`
  entry in `_SUBCOMMANDS`, following the `gate` verb's exact shape (parser
  function + run function, both named `_add_<verb>`/`_run_<verb>`).
- **New file**: `skills/run-autopilot/cli/test_cap_check.py` — fixture-repo
  tests (Phase 0 of the PRD's own task list).
- **New file**: `skills/run-autopilot/scripts/test_cap_regression_prose.py` —
  prose-routing tests (Phase 2).
- **Edit**: `skills/run-autopilot/references/phase-review.md` — the cap-out
  bullet at the "Loop mode ... cap-out defers, never pauses" line (core
  `SKILL.md` § Error Handling references it as the cap-overflow branch).
- **Edit**: `skills/run-autopilot/references/recovery.md` — add the
  `cap_regression` slug next to `cap_critical` in the `site` slugs list
  (line 90 area) and in the stall-site enumeration (state-schema row 510
  companion).
- **Edit**: `skills/run-autopilot/references/state-schema.md` — add
  `cap_regression` beside `cap_critical` in the `stall` record's `site`
  slugs row (row 510).
- **Edit**: `CHANGELOG.md` — one `### Added` entry under `[Unreleased]`,
  scope `run-autopilot`.
- **Edit**: `dev/bin/release-checks` — register `test_cap_check.py` and
  `test_cap_regression_prose.py` in their `[checks]` blocks (mirroring how
  other `cli/test_*.py` / `scripts/test_*.py` files are already listed).

No existing file's behavior changes for a PRD that never reaches the rework
cap, or whose cap-time findings carry no high/critical row — `cap-check` is
called from exactly one branch, the loop-mode cap-out bullet, and that
branch's existing cap-overflow-deferral behavior is otherwise untouched.

## Interfaces & contracts

### `cli/cap_check.py`

```python
def rework_range(previous_head: str, head: str) -> tuple[str, str]:
    """(previous_head, head) unchanged — a thin named pair, not a lookup, so
    callers have one symbol to import instead of building the tuple inline."""

def classify_findings(
    repo_root: str | Path,
    review_file: str | Path,
    previous_review_file: str | Path | None,
) -> list[dict]:
    """Every high/critical row of `review_file`'s `## Consolidated Findings`
    section, classified against the rework range between
    `previous_review_file`'s `head_sha` and `review_file`'s `head_sha`.

    Returns `[]` (no git call made) when `previous_review_file` is None or
    does not exist on disk — there is no rework range to check against
    (a cycle-1 cap, `rework_cap: 1`).

    Each returned dict: `{"ref": str, "severity": "high"|"critical",
    "file": str, "line": int | None, "regression": bool, "commit": str | None}`.
    `ref` is `""` when the row carries no Ref column (pre-Ref review files,
    same convention as `findings_section.Row.ref`). `file` is the Row's file
    cell with any trailing `:<digits>` line suffix split off; `line` is that
    suffix as `int`, or `None` when the cell carries no `:<digits>` suffix or
    no file at all (a File cell is the whole table-row cell, matching how a
    reviewer writes `path/to/mod.py:42` or `path/to/mod.py`). `commit` is the
    first commit (short SHA, `git log --format=%h -1 <path-or-line-blame>`)
    that made the row a regression, or `None` when `regression` is `False`.

    Raises `CapCheckError(str)` — a RuntimeError subclass — when `review_file`
    is unreadable, has no `## Consolidated Findings` section (any
    `findings_section._reviewed_keys` failure), has no parseable
    `head_sha:` frontmatter line, or a `head_sha`/git call fails (unknown
    revision, not a git repo at `repo_root`). The CLI verb (below) catches
    this and exits 2 with the message on stderr; nothing else in this module
    prints or exits.
    """
```

Classification rule per high/critical row (medium/low rows are never
examined — `classify_findings` filters to severity in `{"high", "critical"}`
before doing any git work):

- **No `file`** (an empty File cell) → `regression: False`, `commit: None`.
  Nothing in the rework range can be blamed for a row with no location.
- **`file` with `line`** → regression when
  `git blame -L <line>,<line> --porcelain <head> -- <file>` names a commit
  that is `git rev-list <previous_head>..<head>` (the commit set of the
  rework range, read once per call and reused for every row — not one
  `rev-list` per row).
- **`file`, no `line`** → regression when `file` appears in
  `git diff --name-only <previous_head>..<head>` (also read once per call).

All git calls run with `cwd=repo_root`. A path that `git blame`/`git diff`
reports as not existing at `<head>` (renamed or deleted since the review was
written) is **not** a regression — `git blame` exits non-zero for a missing
path; that exit is caught and treated as "cannot blame, not a regression",
never as a `CapCheckError` (a reviewer citing a path that later moved is a
pre-existing report-accuracy gap, out of scope here, not a reason to misread
the cap-out verdict as clean when the classifier merely couldn't look).

### `autopilot cap-check` verb

```
autopilot cap-check --review-file <path> --previous <path> [--state STATE]
```

- `--review-file` (required): the current cycle's review file.
- `--previous` (optional, default omitted = `None`): the prior cycle's
  review file. Absent, or naming a file that does not exist, is read exactly
  like `None` — `classify_findings` returns `[]`, exit 0.
- `--state`/repo-root resolution follows the existing `_walk_up_or_exit`
  convention other verbs use (`gate` does not need a repo root; `cap-check`
  does, for the git calls) — resolve `repo_root` via
  `state_path.parent`'s project root the same way `records.do_stall`'s
  caller (`_run_stall`) resolves `prds_dir`, i.e.
  `state_path.parent.parent.parent` (autopilot dir → `docs/dev/project-management` →
  project root) is wrong by inspection; use the already-proven resolver
  `cli/enter_io.py`'s repo-root walk, or — simpler and sufficient here,
  since `cap-check` never needs the state file's content, only a
  filesystem anchor — accept an explicit `--repo-root` defaulting to `Path.cwd()`.
  (Decision: add `--repo-root` default `.`, not a state-derived resolution;
  see Alternatives.)

Exit codes:
- **1**: `classify_findings` returned at least one row with
  `regression: True` (severity is already filtered to high/critical by the
  function itself). Prints one JSON line per **classified** row (every
  high/critical row, not only the regressions) to stdout, in table order,
  e.g. `{"ref": "R2", "severity": "high", "file": "a.py", "line": 3,
  "regression": true, "commit": "abc1234"}`.
- **0**: every classified row (if any) has `regression: False`, or there
  was nothing to classify (no previous review file, or no high/critical
  rows at all). Prints the same one-JSON-line-per-row stdout (possibly
  zero lines).
- **2**: `CapCheckError` — unreadable review file, missing/malformed
  `head_sha`, or a git call failed for a reason other than "path not found
  at head" above. Message on stderr, nothing on stdout.

## Data flow

```
phase-review.md cap-out bullet (loop mode, at the rework cap)
  -> autopilot cap-check --review-file <this cycle> --previous <prior cycle or omitted>
       -> classify_findings()
            -> findings_section._reviewed_keys(review_file text)   [existing parser]
            -> filter to severity in {high, critical}
            -> read head_sha from review_file and previous_review_file frontmatter
            -> if no previous or no rows: return []
            -> git rev-list <previous_head>..<head>   (commit set, once)
            -> git diff --name-only <previous_head>..<head>   (changed files, once)
            -> per row: git blame -L / membership test against the two sets above
       -> exit 1 (>=1 regression) or exit 0, JSON lines on stdout
  -> exit 1: autopilot stall --prd <filename> --site cap_regression --detail "<refs + commits>"
  -> exit 0: existing cap-overflow deferral path, unchanged
  -> exit 2: route through the EXISTING "Sub-skill invocation fails
             outright" row of core SKILL.md's Error Handling table, verbatim,
             not a new handling path: interactive -> PAUSE and report;
             loop mode -> re-invoke `cap-check` ONCE, and if it fails again,
             `autopilot stall --prd <filename> --site sub_skill_fail --detail
             "<cap-check stderr>"` and continue the batch. `sub_skill_fail`
             is the existing generic stall/pause slug this row already uses
             for every other sub-skill failure (design-solution failures,
             plan-tasks failures, etc.) — it needs no new entry in
             `recovery.md`/`state-schema.md`'s slug lists, unlike
             `cap_regression`, and no new test: the row's behavior is
             already pinned by whatever test currently covers that Error
             Handling row for another sub-skill (if any does; this PRD adds
             no new assertion here because it adds no new behavior here).
             Why the Safety Checks table's "reviewer or sub-skill errored
             transiently" row does NOT apply instead: that row governs a
             reviewer/sub-skill failing during findings-gathering (Phase 4),
             where graceful degradation is possible because other reviewers
             still produced a usable verdict. `cap-check` runs at the
             decision gate (Phase 5), after findings already exist, to
             classify them; a failed classifier cannot "degrade gracefully"
             into a correct cap-out verdict — there is no second opinion to
             fall back on, only retry-then-stall.
```

No new state field. The regression classification is read fresh every
cap-out; nothing about it is persisted beyond the `detail` string passed to
the existing `cap_regression`-slugged stall record.

## Reuse inventory

- `cli/findings_section._reviewed_keys(text) -> (list[Row], str | None)` —
  the exact parser `gate --findings` uses for the pipe-table and bullet
  shapes of `## Consolidated Findings`; `Row` is `(ref, severity, file,
  issue)` with `severity` already normalized to the lowercase word
  (`cli/findings_section.py:80-88`, `:47-57`). `classify_findings` imports
  this directly rather than re-parsing the section — the PRD's own
  requirement ("the findings rows come from the same table parser … never a
  second parser").
- `cli/records.do_stall` / the `autopilot stall` verb (`cli/__main__.py`
  `_add_stall`/`_run_stall`, `references/recovery.md` § Loop-mode stall
  procedure) — generic over `--site`; `cap_regression` is a new value for an
  existing parameter, not new stall logic.
- `_finding_key`/`_split_severity_cell` (`findings_section.py:47-77`) already
  normalize the severity word and collapse `\|` escapes in the File cell —
  reused as-is for the File-cell line-suffix split rather than re-deriving
  the escape handling.
- Greps tried, nothing found: `rg -n "git blame" skills/run-autopilot/cli/`,
  `rg -n "rev-list" skills/run-autopilot/cli/`, `rg -n "classify" skills/run-autopilot/cli/`
  — no existing git-blame/rev-list/classification helper to reuse for the
  regression test itself.

## Alternatives considered

1. **Chosen**: a small pure module (`cap_check.py`) with two exported
   functions, called from a thin `cap-check` CLI verb that only parses args,
   resolves `repo_root`, prints, and exits. Keeps the git-plumbing and the
   classification rule unit-testable against a fixture repo with no CLI
   involved (the PRD's own task list drives tests straight at
   `classify_findings`/`rework_range`), while the verb stays a thin shim like
   every other entry in `_SUBCOMMANDS`.
2. **Smallest-diff version**: skip the dedicated module and inline the git
   calls directly into the `phase-review.md` prose as ad-hoc `git blame`/
   `git diff` Bash calls the model runs by hand at cap-out. Rejected: the
   classification rule (line-blame vs path-diff vs no-file; rev-list
   membership) is exactly the kind of multi-branch logic the project's own
   `SKILL.md`/`AGENTS.md` conventions push into tested code rather than
   prose a model re-derives correctly or not each cap-out; it would also be
   untestable without a live git repo inside a skill-prose test.
3. **Classify every severity, not just high/critical**: symmetrical with
   "A CRITICAL is never a settled deferral" but broader than the PRD asks.
   Rejected: `recovery.md`'s existing cap-out metric is "zero escaped
   CRITICAL/HIGH" — classifying medium/low rows would add git calls (and
   false-positive noise on cosmetic regressions) for severities the cap-out
   bullet already always defers regardless of origin. The PRD's own
   `classify_findings` docstring says "severity high or critical" explicitly.
4. **`--repo-root` resolution**: considered deriving it from `--state` the
   way other verbs resolve `prds_dir`/`autopilot_dir` from the state path's
   parent. Rejected for this verb specifically: `cap-check` does no state
   read or write at all (it is a pure classifier other prose calls before
   any stall), so requiring a state path only to extract a directory three
   levels up adds a dependency with no payoff. `--repo-root` (default
   `Path.cwd()`, matching how `phase-review.md`'s prose already runs every
   other Bash call from the project root) is simpler and makes the verb
   testable with no `state.json` fixture at all.

## Risks & edge cases

- **Renamed/deleted file between cycles**: `git blame -L` on a path gone at
  `<head>` fails; treated as "not a regression" (see Interfaces). A reviewer
  citing a stale path is a report-accuracy gap, not this PRD's job to fix.
- **Row with no Ref column** (pre-0.9.1 review files, per
  `findings_section.py`'s own ref-required note): `classify_findings` still
  classifies it (ref is not required for classification, only for
  `gate --findings` coverage); the row's JSON carries `"ref": ""`.
- **Merge commits inside the rework range**: `git rev-list prev..head`
  includes merge commits; `git blame --porcelain` already resolves a line's
  true introducing commit through merges, so no special-casing needed.
- **Two review files with the same `head_sha`** (a no-op cycle): `rev-list`
  returns empty, every row reads as `regression: False` — correct, nothing
  changed.
- **`mint-stubs` does not cover `cap_regression`**: `cli/triage.py`'s
  `qualifies()` mints a hold stub only for a stall row whose `site ==
  "cap_critical"` — a `cap_regression` stall never qualifies. This is
  intentional, not a gap: unlike `cap_critical`'s deferred-JSON finding
  (which has no PRD left to carry it once the batch moves on), a
  `cap_regression` stall parks the whole PRD to `hold/`, where it is already
  visible in the batch's STALLED PRDS block (state-schema row 510 now lists
  the slug). A hold stub would duplicate that visibility. Not extending
  `mint-stubs` in this PRD.
- **Likely next changes**: (1) extending the same classifier to the
  interactive Cap-pause path, so a human-attended cap-out also sees which
  findings are self-inflicted — `classify_findings` is already
  mode-agnostic, only the `phase-review.md` interactive bullet would need a
  parallel call; (2) once a PRD un-parked from a `cap_regression` stall is
  itself re-reworked and re-capped, feeding `commit` into that PRD's own
  rework-design doc (not `mint-stubs`, corrected per the note above) so the
  next design pass sees which commit regressed; (3) widening
  classification to MEDIUM once the HIGH/CRITICAL signal is proven, which
  the severity filter in `classify_findings` makes a one-line change, not a
  redesign. Nothing in this design hard-codes "high/critical only" below the
  one filter line, so none of these three require reworking the git-call
  plumbing.

## Test strategy outline

- `cli/test_cap_check.py` (Phase 0, written first against the fixture
  described in the PRD's own task list — a base commit, a rework commit
  touching `a.py` line 3 and adding `b.py`, two review files naming the two
  commits via `head_sha`): the eight named unit tests exercise
  `classify_findings`/`rework_range` directly, no CLI invocation.
- `scripts/test_cap_regression_prose.py` (Phase 2): `test_cap_out_runs_cap_check_before_deferring`
  greps `phase-review.md`'s cap-out bullet for a `cap-check` mention ahead of
  the cap-overflow-deferral sentence; `test_exit_1_routes_to_cap_regression_stall`
  greps the same bullet for `cap_regression` beside the `autopilot stall`
  mention; `test_recovery_lists_cap_regression_slug` greps
  `recovery.md`/`state-schema.md` for `cap_regression` appearing next to
  `cap_critical`. These are prose-pin tests (string/structure assertions
  against the `.md` files), matching the pattern `test_cap_out_defers...`-
  style tests already use elsewhere in this skill's `scripts/` tree.
- `--help` smoke test (PRD acceptance criterion): `cap-check --help` exits 0
  and names `--review-file` and `--previous`.
- Replay test (Success Criteria): running the verb against
  `test_cap_check.py`'s own fixture end-to-end (not just unit-level) proves
  the CLI wiring, not just the module.

## Review log

- Non-blocking (dispatch 1): `--repo-root` default `.` relies on cwd being
  the project root; this precondition should live in `cap_check.py`'s module
  docstring, not only the design doc's Alternatives section. Will be
  addressed as an implementation note, not a design change.
- Question (dispatch 1): does `rework_range()` need its own direct test, or
  is transitive coverage through `classify_findings`'s tests sufficient?
  Left to planning to decide; not a design defect either way.

dispatch 1 (claude): cardinal-sin 0, blocker 1, non-blocker 1, question 1

- Question (dispatch 2, resolved in Data flow above): why the Safety Checks
  table's "reviewer or sub-skill errored transiently" row does not govern
  `cap-check`'s exit-2 handling instead of SKILL.md's generic sub-skill-
  failure row. Resolved: `cap-check` runs at the decision gate after
  findings already exist, not during findings-gathering, so there is no
  graceful degradation available.
- Non-blocker (dispatch 2): `mint-stubs` does not qualify a `cap_regression`
  stall row; confirmed intentional and noted in Risks & edge cases.
- Non-blocker (dispatch 2, same as dispatch 1): `--repo-root` default
  precondition belongs in `cap_check.py`'s module docstring.
- Question (dispatch 2, same as dispatch 1): `rework_range()` direct test
  vs. transitive coverage — left to planning.

dispatch 2 (claude-fallback): cardinal-sin 0, blocker 0, non-blocker 2, question 2
