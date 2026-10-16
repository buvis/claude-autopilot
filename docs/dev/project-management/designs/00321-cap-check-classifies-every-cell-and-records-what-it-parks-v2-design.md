## Architecture fit

`skills/run-autopilot/cli/cap_check.py` is the classifier the loop-mode
cap-out path calls at `references/phase-review.md:59` before deferring an
unresolved HIGH/CRITICAL; it decides stall-vs-defer with zero human in the
loop, so every failure mode it has today fails toward "defer" (the unsafe
side). The fix is confined to that module plus the three call sites that
read its verdict: `cli/__main__.py` (`--repo-root` default), `cli/triage.py`
(`qualifies`, for `mint-stubs` eligibility) and `cli/records.py` (`do_stall`,
for the ledger migration). `references/phase-review.md` and
`references/recovery.md` get the matching prose. No new module, no new
layer — this is a parser/validator hardening pass inside the existing
cap-check verb plus one new named stall site it now shares with
`cap_critical`.

## Module placement

- Edit `skills/run-autopilot/cli/cap_check.py`: new `_parse_file_cell`,
  `_verify_range`, `_toplevel`; rewritten `_classify_row`,
  `classify_findings`, `_file_exists_at`, `_missing_path_error`,
  `_introducing_commit`; new `CapCheckError.stderr` carry-through.
- Edit `skills/run-autopilot/cli/__main__.py`: no code change — `_run_cap_check`
  keeps passing `--repo-root` straight through; `classify_findings` resolves
  it to the toplevel internally (see Interfaces & contracts below).
- Edit `skills/run-autopilot/cli/triage.py`: `qualifies` gains
  `REGRESSION_SITE`.
- Edit `skills/run-autopilot/cli/records.py`: `do_stall` migrates pending
  `deferred_decisions` into the batch ledger for `CUSTODY_SITE` and
  `REGRESSION_SITE` before `reset_prd_fields` drops them.
- Edit `skills/run-autopilot/references/phase-review.md` (cap-out bullet:
  records-then-stall ordering, rename limit) and
  `skills/run-autopilot/references/recovery.md` (real `cap_regression`
  resume steps).
- Edit `CHANGELOG.md` `[Unreleased]` → Fixed, scope `run-autopilot`.
- New tests only, no new test module: `cli/test_cap_check.py`,
  `cli/test_triage.py`, `cli/test_records_stall.py`,
  `scripts/test_cap_regression_prose.py`.

## Interfaces & contracts

### `cli/cap_check.py`

```python
_SHA_RE = re.compile(r"^[0-9a-fA-F]{40}$")          # tightened: full sha only
_FILE_LINE_RE = re.compile(r"^(.*):(\d+)(?:[-,]\d+)*$")   # unchanged, reused per-segment
_ANNOTATION_RE = re.compile(r"\s*\([^)]*\)\s*$")
_SPLIT_RE = re.compile(r";|,(?!\s*\d)")             # split on ';' always, ',' only when
                                                     # not followed by a digit
_HASH_L_RE = re.compile(r"^(.*)#[Ll](\d+)(?:-(\d+))?$")
_COLON_L_RE = re.compile(r"^(.*):[Ll]\s*(\d+)(?:-(\d+))?$")
_COLON_RANGE_RE = re.compile(r"^(.*):(\d+)-(\d+)$")


class CapCheckError(RuntimeError):
    """review_file could not be read, parsed, or diffed against git.
    `.stderr` carries git's raw stderr for a CalledProcessError, else "" —
    `_missing_path_error` inspects only this field, never the formatted
    message (which also contains the command text)."""

    def __init__(self, message: str, stderr: str = ""):
        super().__init__(message)
        self.stderr = stderr


def _toplevel(repo_root: str | Path) -> Path:
    """git rev-parse --show-toplevel of `repo_root`; raises CapCheckError on
    a non-repo cwd. Every _git call below runs with cwd=_toplevel(...), not
    the raw `repo_root`, so cap-check from a subdirectory classifies the
    same rows as from the toplevel (problem b)."""


def _parse_file_cell(
    cell: str, toplevel: Path, changed_files: set[str],
) -> list[tuple[str, list[int] | None]]:
    """One File-cell's (path, lines) pairs. `lines` is None (no line spec),
    or the full inclusive list of line numbers a range names (every line of
    "A-B" is blamed, per the PRD). Steps, in order:
      1. strip a trailing parenthesised annotation (_ANNOTATION_RE)
      2. split on _SPLIT_RE into segments (';' always; ',' only when the next
         non-space char is not a digit, so "a.py:1,2" stays one segment and
         is handled by the existing comma-list group in _FILE_LINE_RE)
      3. per segment: strip whitespace, strip one layer of surrounding
         backticks, then try _HASH_L_RE, _COLON_L_RE (handles "path:L5" and
         "path:L5-9"), _COLON_RANGE_RE, _split_file_line/_FILE_LINE_RE
         (handles the pre-existing "path:N", "path:N,M" and "path:N-M"
         forms unchanged), else bare path. _COLON_LINE_RE is dropped as
         redundant — _FILE_LINE_RE already matches a plain "path:N" and
         the comma-list form the old single-cell parser supported, so
         trying it ahead of _FILE_LINE_RE would just shadow that case for
         no gain.
      4. normalise the path: if absolute and under `toplevel`, make it
         repo-relative (Path.relative_to); if the exact spelling is not in
         `changed_files` but exactly one case-insensitive match is, rewrite
         to that spelling; otherwise leave the path as parsed (classification
         proper decides unresolved vs. not-a-regression)
    A segment that is empty after stripping is dropped (does not yield a
    pair) — a cell ending in a stray delimiter does not fabricate a path."""


def _verify_range(repo_root: Path, previous_head: str, head: str) -> None:
    """Raises CapCheckError, message naming the failing condition, unless
    ALL hold: both `previous_head` and `head` match _SHA_RE (40 hex); both
    resolve via `git rev-parse --verify <sha>^{commit}`; previous_head !=
    head; `git merge-base --is-ancestor previous_head head` exits 0; `git
    merge-base --is-ancestor head HEAD` exits 0 (head is HEAD or an
    ancestor of it). Called once per classify_findings() call, before any
    row is classified."""


def _file_exists_at(repo_root: Path, head: str, file: str) -> bool:
    """Unchanged return shape; now re-raises any CapCheckError whose
    .stderr does not name a missing path (via _missing_path_error), instead
    of swallowing every CapCheckError (problem d)."""


def _missing_path_error(err: CapCheckError) -> bool:
    """Inspects err.stderr ONLY (never str(err), which also carries the
    command text) for "does not exist" / "no such path" (case-insensitive)."""


def _introducing_commit(
    repo_root: Path, head: str, file: str, line: int,
) -> str | None:
    """Unchanged signature. New behaviour: on a `git blame` CapCheckError,
    re-raise unless `_missing_path_error(err)` is True (mirrors
    `_file_exists_at`'s new split, same helper, same rule) — a blame
    failure that is NOT about a missing path (a corrupt object, a
    permission error) must propagate, not silently read as "line not
    introduced here". A missing-path blame failure still returns None (the
    file does not exist at `head` at all), which `_classify_row` below
    turns into the pair's unresolved verdict — `_introducing_commit`
    itself never returns a special "unresolved" value; the caller decides
    that from the None plus a path-existence check it makes itself for the
    lines-given branch (see `_classify_row` below)."""


def _classify_row(
    repo_root: Path, previous_head: str, head: str, row,
    rework_commits: set[str], changed_files: set[str],
) -> dict:
    """Parses row.file via _parse_file_cell. For each (path, lines) pair,
    first call `_file_exists_at(repo_root, head, path)` (the same check
    used today only in the no-lines branch) — a non-missing-path
    CapCheckError propagates from `_file_exists_at` and makes this whole
    call raise (caller treats as CapCheckError, exit 2, same as any other
    git failure). Then:
      - `_file_exists_at` returns False (path does not exist at `head`) ->
        pair is {"regression": None, "reason": f"unresolved path {path}"}
        — this is the ONE unresolved case, decided once per pair before
        either branch below runs, so the lines-given branch can no longer
        silently read a missing path as "not introduced"
      - lines given -> blame every line in the range at `head` via
        `_introducing_commit`; the pair is a regression iff ANY blamed
        line's introducing commit is in rework_commits
      - no lines -> existing file-only rule: path in changed_files ->
        commit = first commit touching path in the range; regression iff
        commit is not None
    Row-level `regression`: None if any pair is unresolved (a cell the verb
    cannot read stalls, never defers — the null row itself counts toward
    exit 1 in classify_findings); else True if any pair is a regression;
    else False. `commit` is the first regression pair's commit, or the
    first unresolved pair's `reason` under a `"reason"` key, mirroring
    today's dict shape plus the new optional `"reason"` key."""


def classify_findings(
    repo_root: str | Path, review_file, previous_review_file,
) -> list[dict]:
    """Unchanged signature and early-return shape. New behaviour: resolves
    `repo_root` through `_toplevel` once; reads changed files via
    `git diff --name-only -z <previous_head> <head>` split on NUL (not
    newline) so a non-ASCII filename matches without git's quoting; calls
    `_verify_range` before classifying any row (a failure here raises
    CapCheckError, which `_run_cap_check` turns into exit 2 exactly as any
    other CapCheckError)."""
```

`_run_cap_check` (`cli/__main__.py`): exit 1 when ANY row has
`regression is True` OR `regression is None` (an unresolved row stalls,
never defers) — i.e. `any(row["regression"] is not False for row in rows)`.

### `cli/triage.py`

```python
REGRESSION_SITE = "cap_regression"

def qualifies(row) -> bool:
    if not isinstance(row, dict) or not render_report._is_open(row):
        return False
    if row.get("type") == "stall":
        return row.get("site") in (custody.CUSTODY_SITE, REGRESSION_SITE)
    return str(row.get("severity") or "").strip().casefold() in SEVERE
```

### `cli/records.py`

```python
def _migrate_stall_deferrals(
    autopilot_dir: Path, current: dict, prd: str, op_id: str,
) -> int | None:
    """do_stall's new step 4a (spliced between the existing step 4
    `_append_stall_deferred` and step 4b `_record_stall_custody`),
    **cap_regression only** — cap_critical migrates the same records inside
    its own custody write, so gating both sites here would write them twice:
    append every item of current.get("deferred_decisions", []) to the batch
    deferred JSON via record_defer (same sink _append_stall_deferred uses),
    BEFORE _commit_stall's reset_prd_fields drops state.deferred_decisions
    (it is in PER_PRD_RESET_FIELDS). Each migrated record keeps its own
    shape untouched plus the stamped "prd" record_defer always adds, and is
    keyed `op_id: "<op_id>-dd<i>"` (via `custody.migration_records`) so a
    retry of the same stall dedupes instead of duplicating. Returns 9
    on an OSError/ValueError from record_defer (same failure code as
    _append_stall_deferred), None on success (including an empty/absent
    deferred_decisions list, which migrates nothing)."""
```

`records.py` imports `triage` module-style (`from . import triage`, then
`triage.REGRESSION_SITE`) — matching the existing `custody`/`records` cycle
convention (`custody.py:27` does `from . import ... records ...` and
`records.py:55` does `from . import custody ...`, both lazy
module-attribute access, not `from .x import name`). `triage.py` already
imports `custody` (`triage.py:51`), so the chain is
`records → triage → custody → records`; a direct
`from .triage import REGRESSION_SITE` in `records.py` risks the same
circular-import failure the existing code already avoids by using
module-style imports throughout this cycle.

Called from `_write_stall_records`, gated on
`site in (custody.CUSTODY_SITE, triage.REGRESSION_SITE)`, after
`_append_stall_deferred` and before `_record_stall_custody` — so a
`cap_regression` stall (which takes no custody branch) still gets this step,
and a failure here returns exit 9 exactly like the existing deferred-append
failure.

`do_stall`'s docstring gains `REGRESSION_SITE` to its exit-code table
(unchanged codes; `REGRESSION_SITE` just takes the `cap_critical`-shaped
path through steps 3b, never 4b).

### `cli/__main__.py`

`_add_cap_check`: `--repo-root` default stays `Path.cwd()` (callers that
pass it explicitly are unaffected); `_run_cap_check` passes it straight to
`classify_findings`, which now resolves the toplevel itself — the
subdirectory bug (problem b) is fixed inside `cap_check.py`, not by
changing the CLI default, so a caller that already runs from a
subdirectory on purpose keeps working.

### Prose

`references/phase-review.md:59`, the `cap-check` exit-1 branch: reorder to
(1) append the `cap-overflow` record for every unresolved row of this
cycle (all severities, as today) to `state.deferred_decisions`, THEN (2)
stall with `site: cap_regression`, THEN (3) run `mint-stubs`. Add one
sentence naming the rename limit: "a heavily rewritten rename blames
unchanged lines to the rework range and is accepted as a documented
limit, not a defect — packet 23." Also add one sentence covering the
null-row case for the stall's `detail` text: a row with `"regression":
null` has no `commit` field (it was never classified, only marked
unresolvable) — build that row's `detail` fragment from its `ref` and
`reason` instead of `ref`+`commit`, so "the regressed rows' refs and
commits from cap-check's stdout" reads, for a null row, as
"ref + reason" in place of "ref + commit".

`references/recovery.md`, `cap_regression` entry (replace the current "same
as cap_critical" line): the PRD sits in `prds/hold/<filename>`; its
regressed rows are in `deferred/<batch_id>-deferred.json` and in the
hold-stub `mint-stubs` minted; fix the regression on a branch or write a v2
PRD against the stub; `mv` the original back to `backlog/` when ready, or
let it stay parked; **no `autopilot custody` command applies to this site**
— `cap_regression` takes no custody branch, unlike `cap_critical`.

## Data flow

Phase 5 cap-out (loop mode) → `cap-check --review-file <cycle> --previous
<cycle-1>` → `classify_findings` resolves toplevel, verifies the range,
reads `-z`-split changed files, parses every row's File cell into
(path, lines) pairs, blames each pair → rows list with
`regression: true|false|null`. Exit 1 on any non-`false` row →
`state.deferred_decisions` gets the cap-overflow records for every
unresolved row of the cycle → `autopilot stall --site cap_regression` →
`do_stall` migrates `state.deferred_decisions` (now including those
just-appended records) into `deferred/<batch_id>-deferred.json` →
`reset_prd_fields` drops the now-migrated `state.deferred_decisions` →
`mint-stubs --batch <id>` reads the deferred JSON, sees `qualifies()` now
accept the `cap_regression` stall row, mints a hold stub.

## Reuse inventory

- `frontmatter.declared` (`cli/frontmatter.py`) — already used by
  `_head_sha` to read the `head_sha:` line; unchanged, reused as-is.
- `findings_section._reviewed_keys` / `Row` (`cli/findings_section.py`) —
  already the source of `row.file`/`row.severity`/`row.ref`; unchanged.
- `record_defer` (`cli/records.py:138`) — already the sink
  `_append_stall_deferred` writes to; `_migrate_stall_deferrals` calls
  the same function per pending item instead of introducing a second
  writer.
- `custody.CUSTODY_SITE`, `custody.record_critical`, `custody.marker_entry`
  (`cli/custody.py`) — unchanged; `cap_regression` deliberately does not
  call into any of these (no custody branch), matching the PRD's "custody
  stays as v1 shipped it" instruction.
- `render_report._is_open` (`cli/render_report.py`) — already used by
  `triage.qualifies`; unchanged, reused for the widened site check.
- Searched for an existing multi-path/cell parser before designing
  `_parse_file_cell`: `rg -n "def _parse|def _split" skills/run-autopilot/cli/*.py`
  and `rg -n "class.*Cell|parse.*cell" skills/run-autopilot/cli/*.py` —
  nothing found; `_split_file_line`/`_FILE_LINE_RE` are the only existing
  File-cell parsing and are reused inside `_parse_file_cell` per-segment
  rather than replaced outright (same regex, same comma/dash range
  semantics, just no longer asked to also split multiple paths).
- Searched for an existing ancestor/sha-verification helper:
  `rg -n "is-ancestor|rev-parse --verify" skills/run-autopilot/cli/*.py` —
  nothing found; `_verify_range` is new, built from `_git` (reused as-is,
  no change to its signature).

## Alternatives considered

1. **Smallest-diff option: patch `_FILE_LINE_RE` to also strip a trailing
   `(note)` and accept `#L`, but leave multi-path cells unparsed** (treat
   the whole multi-path cell as one unresolvable path, which already
   exits 1 under the new null-row rule). Rejected as the shipped design
   because it still gets Success Criterion 2 wrong for a benign two-path
   cell where only one path is actually touched by the rework — a cell
   naming an unrelated file alongside the regressed one would stall for the
   wrong reason (an "unresolved" verdict, not a "regression: true" one),
   which is safe (it still stalls) but makes `cap-check`'s JSON output
   actively misleading for the operator reading `recovery.md`'s resume
   steps. Worth noting: this smaller version is almost free (one regex
   tweak) and would still satisfy "fail toward stalling" — if operator
   readability of the per-path verdict turns out not to matter in
   practice, this is the fallback to shrink back to.
2. **Replace regex parsing with a tiny grammar/parser combinator for the
   File cell.** Rejected: the cell shapes are finite and simple
   (semicolon/comma-separated path[:line[-line]] tokens with optional
   backticks/annotation); a parser library is a dependency for a problem
   five `re.compile` patterns and a split already solve, and ponytail's
   ladder stops well before "add a parsing library" for this shape.
3. **Chosen: `_parse_file_cell` as a small, pure, regex-sequence function,
   `_verify_range` as a small sequence of `_git` calls, no new
   dependencies, no new classes.** The extra size over option 1 buys a
   row-level verdict that is actually true to each path in a multi-path
   cell, which is what Success Criterion 2's full fixture list (packet 3)
   requires pinned, not just "still stalls somehow."

## Risks & edge cases

- **Likely next change 1:** a File cell naming a path with a line range
  that spans a rename boundary (file renamed mid-range by the rework) —
  today's design blames post-rename line numbers only; documented as the
  rename limit (packet 23), not fixed here.
- **Likely next change 2:** `cap-check` currently spawns one-or-two git
  processes per row (packet 21, accepted at 0.13s on a real pair); a
  future PRD batching all rows into one `git blame` invocation would need
  `_classify_row`'s per-pair blame call kept as a separately-callable unit
  (it already is) so batching can replace the loop body without touching
  the per-pair semantics.
- **Likely next change 3:** extending `_parse_file_cell`'s accepted shapes
  (e.g. a `path@<ref>` form) only needs a new regex alternative tried
  before the bare-path fallback — the function is designed as an ordered
  list of regex attempts for exactly this reason.
- **Edge case boxed in by this design:** `_migrate_stall_deferrals` is
  gated on site (`cap_regression` alone — `cap_critical` migrates the same
  records inside `custody.record_critical`), not called unconditionally from
  `do_stall`. A future third site that also wants its PRD's pending
  `deferred_decisions` preserved through a stall must add itself to the same
  gate; this design does not generalize it to "every stall site" because
  `cap_critical`'s own
  custody capture depends on site-specific branching already, and widening
  the migration to every site (including, say, `design_gate` or
  `clarification`) is outside this PRD's scope and untested here.
- **Edge case:** `_SPLIT_RE`'s comma rule (`,(?!\s*\d)`) does not split a
  cell where a second filename immediately follows the comma and itself
  starts with a digit (e.g. `a.py,3abc.py`) — the two paths stay joined
  into one unresolvable segment. This degrades safely (the row still
  stalls via the null-row rule, never defers) and is accepted rather than
  special-cased further; a digit-leading filename immediately after a bare
  comma is not a shape seen in the problem's fixture list.
- **Edge case:** a review file's `head_sha` pointing at a commit that was
  later rewritten out of history (force-push, rebase) between cycles makes
  `git rev-parse --verify <sha>^{commit}` fail — correctly exits 2, not a
  silent pass-through.

## Test strategy outline

- `cli/test_cap_check.py`: extend the fixture with a rework that adds line
  4 of `a.py`, renames nothing, and adds `café.py`; one test per named cell
  shape (multi-path, range, backtick, `#L`, `:L`, space-after-colon,
  case-variant, annotated), the two controls (plain, dot-slash, absolute),
  the unresolved-path-stalls rule, the non-ASCII match, the subdirectory
  cwd-independence, the four `_verify_range` failure probes (equal,
  reversed, non-40-hex, non-ancestor/ref-named), and the
  stderr-only-missing-path propagation test. Each test drives
  `classify_findings` directly or the CLI, per the PRD's named test list.
- `cli/test_triage.py`: `test_cap_regression_stall_row_mints_a_stub` — a
  deferred-JSON stall row at `site="cap_regression"` satisfies
  `qualifies()`.
- `cli/test_records_stall.py`:
  `test_cap_regression_stall_migrates_pending_deferrals` — state with two
  pending `deferred_decisions`, `do_stall(..., site="cap_regression", ...)`,
  assert the batch ledger holds the stall record and both migrated
  `-dd<i>` records, and `state.deferred_decisions` is empty/absent after
  (confirming the migration ran before the drop, not after).
- `scripts/test_cap_regression_prose.py`: three prose-pin tests —
  cap-out bullet records-before-stall-before-mint-stubs ordering and the
  rename-limit sentence in `phase-review.md`; the real resume steps
  (no-custody-command, hold/deferred-JSON/stub pointers) in `recovery.md`.
- Acceptance commands as given in the PRD's Phase 0/1/2 task rows; Phase 1's
  acceptance additionally re-runs `cap-check` against the 00310 review pair
  and checks R5 now reads `"regression": true`.

## Review log

- non-blocker: row-level precedence (null wins over true, wins over false)
  is stated in the `_classify_row` docstring but not restated in
  Requirements, which only says "a row is a regression when any pair is" —
  cosmetic, Implementation is unambiguous.
- non-blocker: `_SHA_RE` tightened to exactly 40 hex (was 4-40); verified
  safe against `lane-fast-track.md`/`lane-solo.md`, which both instruct
  writers to emit full `git rev-parse HEAD` output.
dispatch 1 (claude): cardinal-sin 0, blocker 2, non-blocker 3, question 0
- non-blocker: `_migrate_pending_deferrals`'s two-site gate is explicit and
  matches `do_stall`'s existing site-specific branching; no action needed.
dispatch 2 (claude-fallback): cardinal-sin 0, blocker 1, non-blocker 1, question 1
- non-blocker: `_introducing_commit`'s re-raise-unless-missing-path logic
  is defense-in-depth, not load-bearing — `_classify_row` now checks
  existence before calling it either way.
dispatch 3 (claude-fallback): cardinal-sin 0, blocker 1, non-blocker 1, question 0
result: ok
