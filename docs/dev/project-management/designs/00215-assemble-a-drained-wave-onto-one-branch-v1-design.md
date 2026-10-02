## Architecture fit

`skills/run-autopilot/cli/` is a flat package of small, single-responsibility
modules dispatched from `cli/__main__.py`'s `wave` subcommand
(`cli/wave_cli.py`). PRD 00214 already split wave concerns into `wave.py`
(schema, `plan`, load/save/lock) and `wave_launch.py` (`launch`, `status`,
`abort`, plus the `lane_status` liveness overlay). This PRD adds the fourth
verb, `assemble`, as a peer module `wave_assemble.py` - same layer, same
dependency direction (`wave_assemble` depends on `wave` for schema/IO
primitives and on `wave_launch.lane_status` for liveness, never the other
way). No new layer, no new package: this is the last verb the `wave.json`
control surface needs before a wave's output can reach master (00216 lands
the branch after review).

`wave_assemble.py` is a **CLI-only, session-free** module: unlike every other
autopilot verb, nothing here spawns a Claude session or touches a lane's own
`state.json` (beyond reading it, read-only, to find a lane's batch id and its
migrated rows). It runs entirely inside one `autopilot wave assemble`
invocation from the main checkout, which is why `references/recovery.md`'s
stall-`site` catalogue needs a note that `assembly_conflict` is the one entry
with no session and no `state.json` behind it.

## Module placement

New files:

- `skills/run-autopilot/cli/wave_assemble.py` - the merge pass, migration and
  summary (all three features; Structural Decomposition already places them
  in one file).
- `skills/run-autopilot/cli/test_wave_assemble.py` - real `tmp_path` git
  repos with real lane branches and real conflicts, per the PRD's Test
  Strategy and per-task Acceptance lists.

Edited files:

- `skills/run-autopilot/cli/wave.py` - extend `LANE_STATUSES` with the four
  new persisted per-lane outcomes (`assembled`, `conflict`, `checks_failed`,
  `unfinished`); extend `WAVE_STATUSES` with the one wave-level outcome
  `LANE_STATUSES` does not already cover (`assembled_partial` - `assembled`
  arrives for free through `WAVE_STATUSES = (*LANE_STATUSES, ...)`); extend
  `_LANE_CHECKS` with the five new optional per-lane fields (`files`,
  `integrator_notes`, `migrated_at`, `conflict_detail`, `conflict_paths`) -
  validated in their own `_LANE_OPTIONAL_CHECKS` dict and a separate,
  presence-optional pass, never merged into `_LANE_CHECKS`'s own
  presence-required loop (see Interfaces & contracts); teach
  `_reject_existing_wave` that
  `assembled` and `assembled_partial` are terminal too (today it only accepts
  `done`/`aborted`, and nothing has ever set `done` - see Risks).
- `skills/run-autopilot/cli/wave_cli.py` - register the `assemble` verb
  (`--state` only, no extra flags) and dispatch it.
- `skills/run-autopilot/references/waves.md` - add `## \`autopilot wave
  assemble\`` (mirroring the existing verb sections' shape) and rewrite the
  "Deferred: assembly and review slots" note now that assembly ships (the
  review-slot semaphore stays deferred, and its stale "00216" cross-reference
  is corrected to 00217 in the same edit since it sits in the sentence this
  PRD rewrites anyway).
- `skills/run-autopilot/references/recovery.md` - add `assembly_conflict` to
  § Stall `site` slugs, flagged as the session-free exception.
- `skills/run-autopilot/references/batch-report-format.md` - add a `##
  Wave summary` section describing `reports/<wave id>-wave.md` as a sibling
  report type to the per-batch report this file otherwise documents.
- `skills/run-autopilot/SKILL.md` - add `reports/<wave id>-wave.md` to the
  Retention § Durable list.
- `dev/bin/release-checks` - append `test_wave_assemble.py` to the `[checks]
  waves` block.
- `CHANGELOG.md` - one `### Added` bullet under `[Unreleased]`, scoped
  `**run-autopilot**` (Keep a Changelog orders `Added` before the existing
  `[Unreleased] ### Fixed` block, so the new heading goes above it).

## Interfaces & contracts

### `wave.py` additions

```python
LANE_STATUSES = (
    "planned", "running", "aborted", "abort_failed",
    "assembled", "conflict", "checks_failed", "unfinished",
)
WAVE_STATUSES = (*LANE_STATUSES, "done", "assembled_partial")
```

`_LANE_CHECKS` gains, as **optional** fields (absent is valid - a lane that
has never been assembled carries none of them; `ok(v)` runs only when the
key is present, matching every other optional check already in the table):

```python
"files": lambda v: v is None or (
    isinstance(v, list) and all(isinstance(p, str) for p in v)
),
"integrator_notes": lambda v: v is None or (
    isinstance(v, list)
    and all(
        isinstance(n, dict)
        and isinstance(n.get("sha"), str)
        and isinstance(n.get("text"), str)
        for n in v
    )
),
"migrated_at": lambda v: v is None or isinstance(v, str),
"conflict_detail": lambda v: v is None or isinstance(v, str),
"conflict_paths": lambda v: v is None or (
    isinstance(v, list) and all(isinstance(p, str) for p in v)
),
```

`_collect_shape_errors`'s existing loop (`if field not in each or not
ok(each[field])`) requires every checked field to be PRESENT, so these five
need a default of `None` written at `plan()` time... but `plan()` runs before
this PRD's code ever touches a lane. Resolution (**revised after dispatch-1
review, which caught a broken first draft here**): the five live in a
SEPARATE `_LANE_OPTIONAL_CHECKS` dict, validated by a SECOND, separately
gated list comprehension appended after the existing one -
`_LANE_CHECKS`'s own loop is byte-for-byte unchanged (still `if field not in
each or not ok(each[field])`, still catching a dropped required field like
`name` or `worktree_created` exactly as `cli/test_wave.py`'s
`test_structural_errors_names_a_malformed_lane_field` already pins), and
`_LANE_OPTIONAL_CHECKS` gets its own loop with the presence-optional
condition:

```python
errors += [
    f"lane {label}: malformed field {field}"
    for field, ok in _LANE_CHECKS.items()
    if field not in each or not ok(each[field])
]
errors += [
    f"lane {label}: malformed field {field}"
    for field, ok in _LANE_OPTIONAL_CHECKS.items()
    if field in each and not ok(each[field])
]
```

The first draft of this design merged both dicts into one loop with one
uniform `if field in each and ...` condition, which silently disabled
presence-validation for every REQUIRED field too (a dropped `"name"` would
no longer be flagged at all). Two loops, two conditions, no merged dict.

`_reject_existing_wave`:

```python
if existing["status"] not in ("done", "aborted", "assembled", "assembled_partial"):
```

### `wave_assemble.py`

```python
WAVE_ASSEMBLY_BRANCH_FMT = "wave/{wave_id}/assembly"     # matches _format_branch's style
WAVE_ASSEMBLY_WORKTREE_FMT = "{repo_parent}/{repo_name}-wave-{wave_id}"  # wave-scoped (see below)
_CONFLICT_MARKERS = re.compile(r"^(<{7}(?: .*)?|={7}|>{7}(?: .*)?)$", re.MULTILINE)

def keep_both(text: str) -> str:
    """Strip git's <<<<<<</=======/>>>>>>> marker lines, keeping every other
    line exactly as it appears - both sides of every hunk survive, in file
    order, because only the marker lines themselves are removed. A `text`
    with no markers is returned unchanged. Pure: no disk, no git."""

def merge_lane(
    assembly: Path,
    lane: dict,
    *,
    run_git: Callable[..., subprocess.CompletedProcess],
    run_checks: Callable[[Path], subprocess.CompletedProcess],
) -> str:
    """Rebase `lane["branch"]` (checked out at `lane["worktree"]`) onto the
    assembly worktree's current HEAD, resolve every conflict inside
    `wave.WAVE_APPEND_ONLY` with `keep_both`, `git rebase --continue`
    (GIT_EDITOR=true - no interactive editor), then `git merge --ff-only` it
    into `assembly` and run `run_checks(assembly)`.

    Returns exactly one of "assembled", "conflict", "checks_failed" - this IS
    `lane["status"]` afterward; the caller does not re-derive it. On anything
    but "assembled" also SETS `lane["conflict_detail"]` (a one-line string:
    the conflicted paths outside the append-only set, or "release-checks
    exit <rc> after merging <lane>: <last stderr line>") - the caller hands
    this straight to `records.record_defer`'s `"detail"` without re-deriving
    it either. On "conflict" specifically, ALSO sets `lane["conflict_paths"]`
    (`list[str]`, sorted) - the conflicted paths outside `WAVE_APPEND_ONLY`,
    read from `git diff --name-only --diff-filter=U` at the moment the
    rebase is aborted. This is a DIFFERENT list from `lane["files"]` (the
    full pre-rebase diff `lane_files_and_notes` already recorded) and is
    the caller's ONLY specified source for the `assembly_conflict` record's
    required `"files"` key - `lane["files"]` must never be substituted there
    (dispatch-1 review finding: the first draft named no source for this
    key at all). Unset (`None`) on "checks_failed" - that record's `detail`
    already names the failing lane and exit code; no path list applies.
    Never raises for an ordinary conflict or a checks failure; an
    unexpected git failure (anything `run_git` raises that is not the
    rebase/merge this function expects to fail sometimes) propagates.

    Does NOT compute `lane["files"]` / `lane["integrator_notes"]` (the PRD's
    "record ... before touching the branch" - the caller does this first,
    against the ORIGINAL pre-rebase branch tip, because a rebase rewrites
    commits and `merge_lane` only receives the branch name, not the
    pre-rebase sha to diff from)."""

def lane_files_and_notes(
    lane: dict,
    base_sha: str,
    *,
    run_git: Callable[..., subprocess.CompletedProcess],
) -> tuple[list[str], list[dict]]:
    """(files, integrator_notes) for `lane` against `base_sha`, read from the
    lane's OWN worktree before any rebase touches it:
    - files: sorted `git diff --name-only <base_sha>..<lane["branch"]>`.
    - integrator_notes: one {"sha": <7-char short sha>, "text": <text>} per
      commit in the same range whose body has a line matching
      `^Integrator: (.+)$`, oldest first, via one
      `git log --format=%H%x1f%B%x1e <base_sha>..<branch>` call split on
      \\x1e records and \\x1f fields."""

def migrate_lane(main: Path, wave_id: str, lane: dict) -> None:
    """**Revised after dispatch-1 review**: the first draft guarded the
    WHOLE function - including PRD routing - behind `lane["migrated_at"]`.
    Traced against the PRD's own operator workflow ("A kept lane blocks
    nothing... an operator finishing the kept lane by hand rebases... then
    rerun `assemble`"), that lost data: a lane kept in run 1 (migrated_at
    set, `done/*` correctly left in place - "unassembled") that the operator
    then fixes and `assemble` merges in run 2 would skip `migrate_lane`
    entirely as a no-op, so its `done/*` PRDs are never reclassified into
    main `done/` before `assemble` force-removes the now-merged lane's
    worktree - permanent loss of PRDs whose only copy was that worktree.
    Fixed by splitting what `migrated_at` guards from what always re-runs:

    - **Guarded by `lane["migrated_at"]`** (skip entirely once set - these
      would DUPLICATE, not just no-op, on a second run): append every JSON
      line of `loop-metrics.jsonl`, every `ledger/*.jsonl`, and
      `dispatch-metrics.jsonl` under the lane's `dev/local/autopilot/` to
      the SAME-NAMED file under `main`'s, each line re-serialized with
      `lane`/`wave` merged in (inline `open(..., "a")` + `json.dumps(row) +
      "\\n"`, the idiom every other jsonl writer in this package already
      uses - no shared helper exists or is added). The lane's batch id used
      for the tag: `<lane worktree>/dev/local/autopilot/state.json`'s
      `batch.id` if the file exists and parses, else the newest
      `<lane worktree>/dev/local/autopilot/reports/*-state-final.json`'s
      `batch.id`, else None (the append still runs; only the tag differs).
      Set `lane["migrated_at"] = now()` only once this step succeeds.
    - **NOT guarded - re-evaluated on EVERY call, including a rerun after
      `migrated_at` is already set** (each is naturally idempotent on its
      own terms, so the guard would only cost correctness, never buy
      anything): every item of `deferred/<lane batch id>-deferred.json`
      goes through `records.record_defer(main / "dev/local/autopilot",
      item["prd"], lane_batch_id, item)` (its own `op_id` dedup is the
      idempotency); copy `reports/*` and `dev/local/reviews/*` from the
      lane, skipping any name that already exists under `main` (idempotent
      by the skip-existing rule); and PRD routing, by the folder each PRD
      sits in RIGHT NOW (re-scanned fresh every call - a PRD already moved
      out is simply absent from its old folder on the next scan, which is
      what makes this idempotent without a flag): merged lane's `done/*`
      -> main `done/`, `hold/*` -> main `hold/`; kept lane's `hold/*` ->
      main `hold/`, `wip/*` and `backlog/*` -> main `backlog/`; kept lane's
      `done/*` STAYS (unassembled work, reported by `summary`, never
      moved) - until a LATER call finds the same lane now `"assembled"`,
      at which point that same re-scan routes its `done/*` to main `done/`
      like any other merged lane, before `assemble` removes the worktree.
    Called by `assemble` only while `not lane.get("worktree_removed")` - a
    lane whose worktree is already gone has nothing left to scan and
    `migrate_lane` must not be invoked against a path that no longer
    exists."""

def summary(wave: dict, rows: list[dict], records: list[dict]) -> str:
    """Pure - `wave` (with every lane's `files`/`integrator_notes` and the
    top-level `assembly` block already populated), `rows` (this wave's
    migrated `loop-metrics.jsonl` rows, already read by the caller) and
    `records` (this wave's `assembly_conflict` deferred items, already read
    by the caller) render `dev/local/autopilot/reports/<wave id>-wave.md`:
    header, lane table, one `- <prd>: Wave <id>, lane <name>,
    <done|parked|unassembled|backlog>` line per PRD (label derived from
    which lifecycle folder it was found in - `assemble` does not pass the
    label separately), totals (session count, wall hours summed from
    `rows`, `cost_usd` summed where present), every `records` item verbatim,
    and `## Integrator notes` (`(none)` when every lane's `integrator_notes`
    is empty)."""

def assemble(
    repo: Path,
    wave_path: Path,
    *,
    run_git: Callable[..., subprocess.CompletedProcess] = _default_run_git,
    run_checks: Callable[[Path], subprocess.CompletedProcess] = _default_run_checks,
) -> int:
    """The verb. Holds `wave.locked(wave_path)` for its whole body (matching
    `launch`/`abort`). Preconditions, in order, each a plain `print(...,
    file=sys.stderr); return 1` (no `records.record_defer` - a precondition
    failure is the operator's to retry, not a per-lane outcome):
    1. every lane's `wave_launch.lane_status(lane) != "running"` - a live one
       names itself: "lane <name> is still running - wait or abort".
    2. `run_git(["status", "--porcelain"], cwd=repo).stdout.strip()` empty.
    3. `wave["status"] in ("running", "assembled", "assembled_partial")`
       (**revised after dispatch-1 review**: a bare `== "running"` check
       made the PRD's own mandated rerun path impossible - `assemble`'s
       last step, below, sets `wave["status"]` to `"assembled"` or
       `"assembled_partial"` and NEVER back to `"running"`, so the very
       next call - a true no-op rerun, or a retry after the operator
       hand-fixed a kept lane - would refuse before touching a single
       lane. Accepting all three lets both rerun shapes proceed; a wave
       still `"planned"`/`"aborted"`/`"abort_failed"` is correctly refused,
       since none of those has ever been through a merge pass).
    Then: create the assembly worktree (`git worktree add <worktree> -b
    wave/<id>/assembly <base_sha>`, at
    `f"{repo.parent}/{repo.name}-wave-{wave['id']}"` - **revised after
    dispatch-2 review**: the first draft used the fixed path
    `<repo.parent>/<repo.name>-wave` for EVERY wave, with nothing that ever
    removes it (00216 needs the assembly worktree to persist for its
    review) and `_reject_existing_wave` now accepting `"assembled"`/
    `"assembled_partial"` as terminal (this doc's own dispatch-1 fix) means
    an operator can legally `wave plan` a second wave while the first
    wave's fixed-name worktree still exists on disk - the second wave's
    `assemble` would then `git worktree add` a path git already has
    registered to a DIFFERENT branch, a hard git failure rather than a
    handled precondition. Wave-scoping the path, matching the branch name's
    own convention, closes it: two waves can never collide) unless
    `wave.get("assembly")` already names one that exists (a rerun). For each
    lane in `order`:
    - `lane["status"] == "assembled"` -> already merged; skip the merge.
    - `wave_launch.lane_status(lane) == "unfinished"` -> `lane["status"] =
      "unfinished"`; no merge_lane call.
    - otherwise (drained, not yet assembled) -> `lane_files_and_notes` then
      `merge_lane`; on "conflict"/"checks_failed", call `records.record_defer`
      with `op_id=f"wave-{wave['id']}-{lane['name']}"`, `"files"` =
      `lane["conflict_paths"]` (== `None` on "checks_failed" - omit the key
      rather than send `null`) and the PRD's own record shape otherwise.
    - THEN, regardless of which branch above ran, **while
      `not lane.get("worktree_removed")`**: call `migrate_lane(repo, wave["id"],
      lane)` - this is what re-drains a kept lane's `done/*` once a LATER
      call finds it `"assembled"` (see `migrate_lane`'s own note); a lane
      whose worktree was already removed on a prior call is skipped, since
      there is nothing left under it to scan.
    - `save(wave_path, wave)` after every lane (matches `launch`'s per-lane
      save discipline).
    Remove a merged lane's worktree/branch only once `lane["status"] ==
    "assembled"` AND this call's `migrate_lane` step just ran for it (so
    its `done/*` - if any - is already drained into main `done/` first);
    set `lane["worktree_removed"] = True` together with the removal, never
    before it, so a crash between the two still reads as "not yet removed"
    on the next call.
    Finally: `wave["assembly"] = {"worktree": ..., "branch": ..., "head_sha":
    run_git(["rev-parse", "HEAD"], cwd=assembly).stdout.strip(), "merged":
    [...], "kept": [...]}`; `wave["status"] = "assembled" if not kept else
    "assembled_partial"`; write `reports/<id>-wave.md` from `summary(...)`
    (rewritten whole file, not appended - matches the PRD's "written last,
    rewritten on rerun"); `save(wave_path, wave)` one last time; return 0 if
    not kept else 3.
    """
```

`_default_run_checks` mirrors `wave_launch._default_run_git`'s shape but
**without** `check=True` - a non-zero `release-checks` exit is an expected,
handled outcome here (`checks_failed`), not a call-site bug, so it must not
raise:

```python
def _default_run_checks(cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["bash", "dev/bin/release-checks"], cwd=cwd, capture_output=True, text=True,
    )
```

### `wave_cli.py`

```python
verbs.add_parser("assemble").add_argument("--state")
```

`run()` gains one branch before the generic `wave.load` early-message block
(same shape as `launch`/`abort`'s own try/except around `wave_assemble
.assemble`, since it also runs `git worktree` commands that can raise
`subprocess.CalledProcessError`):

```python
if args.verb == "assemble":
    try:
        return wave_assemble.assemble(repo, wave_path)
    except subprocess.CalledProcessError as err:
        print(f"autopilot: {err}", file=sys.stderr)
        return 1
```

## Data flow

```
operator: autopilot wave assemble --state <repo>/dev/local/autopilot/state.json
  -> __main__._run_wave resolves (repo, wave_path)          [unchanged]
  -> wave_cli.run(verb="assemble") -> wave_assemble.assemble(repo, wave_path)
       -> wave.locked(wave_path); wave.load(wave_path)
       -> preconditions (wave_launch.lane_status per lane, git status, wave.status)
       -> git worktree add <repo>-wave-<id>  (once, wave-scoped; reused on rerun)
       -> per lane, in wave["lanes"] order:
            lane_files_and_notes (lane worktree, read-only git)
              -> lane["files"], lane["integrator_notes"]
            merge_lane (lane worktree + assembly worktree, mutates)
              -> lane["status"], lane.get("conflict_detail"), lane.get("conflict_paths")
            [conflict|checks_failed] -> records.record_defer ("files" = conflict_paths)
              -> dev/local/autopilot/deferred/<wave id>-deferred.json  (batch_id = wave["id"]
                 verbatim, no "wave-" prefix - record_defer's own file_path is
                 f"{batch_id}-deferred.json"; **fixed after dispatch-2 review**,
                 which caught this doc's Data flow and Test strategy sections
                 both stating "wave-<id>-deferred.json", a filename the PRD's
                 own record_defer(..., <wave id>, ...) call - batch_id = the
                 wave id, unprefixed - cannot produce. The op_id used for
                 dedup, f"wave-{wave['id']}-{lane['name']}", DOES carry the
                 "wave-" prefix; that is a different value serving a different
                 purpose (dedup key, not filename) and was never wrong)
            migrate_lane (lane's dev/local/autopilot/* -> main's; skipped once worktree_removed)
              -> main loop-metrics.jsonl / ledger/*.jsonl / dispatch-metrics.jsonl
              -> main deferred/<lane batch id>-deferred.json (via record_defer)
              -> main reports/*, dev/local/reviews/*
              -> main prds/{done,hold,backlog}/*.md
            [merged lane only] git worktree remove --force; git branch -D
            wave.save(wave_path, wave)
       -> wave["assembly"] = {...}; wave["status"] = assembled|assembled_partial
       -> reports/<wave id>-wave.md  <-  summary(wave, migrated rows, conflict records)
       -> wave.save(wave_path, wave)
  <- exit 0 (all merged) | 3 (a lane kept)
```

No new I/O direction crosses process boundaries: everything is filesystem
and `git`/`bash` subprocesses under one CLI invocation, exactly like
`launch`/`abort`.

## Reuse inventory

- **`cli/wave.py`**: `load`/`save`/`locked` (wave.json IO + the exclusive
  flock, reused as-is - `assemble` is the fourth verb sharing this trio),
  `WAVE_APPEND_ONLY` (the two-path append-only allowlist, reused verbatim
  for the conflict-path classification), `_structural_errors` /
  `_format_branch`/`_format_worktree`-style naming conventions (the assembly
  worktree/branch names follow the same `f"{repo.parent}/{repo.name}-..."`
  and `f"wave/{wave_id}/..."` shapes `_format_worktree`/`_format_branch`
  already establish, though those two helpers are `order`-keyed and
  assembly has no `order`, so this PRD adds two small sibling constants
  rather than parameterizing the existing ones for a single non-lane
  caller).
- **`cli/wave_launch.py`**: `lane_status` (liveness-vs-stored-state overlay,
  reused unmodified as the "every lane pid dead" / "drained vs unfinished"
  source - this PRD adds no second way to ask that question),
  `_default_run_git` (the exact `run_git` shape and default,
  duplicated-by-necessity rather than imported since it is module-private
  in `wave_launch.py`; searched: no shared `git_util.py` exists in this
  package - every wave module defines its own `_default_run_git`, so this
  PRD follows the established per-module convention instead of
  introducing a shared import for one four-line function), `_RETURN_TO` /
  `_return_prds`'s folder-routing IDEA (kept-lane PRDs land in the same
  `{"backlog": "backlog", "wip": "backlog", "done": "done", "hold": "hold"}`
  shape `abort` already uses for its own PRD return - `migrate_lane` reuses
  this exact mapping for a kept lane's `wip/`+`backlog/`+`hold/` folders,
  diverging only for `done/`, which `abort` returns but `assemble` does not
  (00214's `abort` has no "unassembled" concept; this PRD introduces it)).
- **`cli/records.py`**: `record_defer` (op_id-deduplicated, locked, atomic
  append - reused as-is for both the `assembly_conflict` stall record and
  every migrated deferred item; no new deferred-writing code is written).
- **`cli/state.py`**: `atomic_write`'s tmp-then-`os.replace` pattern is
  already embodied in `wave.save`, which this PRD calls rather than
  reimplementing atomic writes for `wave.json` a second time.
- **Greps tried, nothing found** (helper genuinely does not exist, write it
  once): `rg -n "rebase" cli/*.py` and `rg -n "conflict" cli/*.py` (only
  prose matches - custody's revert-conflict *messages*, no automation);
  `rg -n "keep_both|marker" cli/*.py`; `rg -n "def.*jsonl|append_jsonl|
  def.*ledger.*append" cli/*.py` (every jsonl writer - `loop.py`,
  `custody.py` - appends inline with `open(path, "a")` +
  `json.dumps(row) + "\n"`; no shared helper to call, so `migrate_lane`
  follows the same inline idiom rather than inventing the package's first
  one); `rg -n "def summary\(|def render_wave" cli/*.py` (the batch
  report's own renderer is `render_report.py`, a different shape entirely -
  session/cycle/task sections, not lanes - confirmed by reading it; not
  reused, a new pure function is the right size for this PRD's summary).

## Alternatives considered

1. **(smallest diff) One flat script, no wave.json schema changes**: write
   `assemble` as a script that only prints a report and NEVER mutates
   `wave.json` - the operator reads git's own state afterward. Rejected: the
   whole point of `wave status`/rerun-safety is that `wave.json` is the
   single source of truth for a lane's fate; a lane whose worktree is gone
   (merged and removed) with no persisted record of what happened to it
   is exactly the "silently misplaces the PRD" failure mode `SKILL.md`'s
   "Verified moves" invariant exists to prevent elsewhere in this pack. Kept
   only as the floor to size the chosen design against - it is roughly a
   third of the code, all of it in `merge_lane`/`summary`, none of the
   schema or migration work.
2. **(chosen) New `wave_assemble.py`, wave.json schema extended in place**:
   as specified above. The extra size buys rerun-safety (`migrated_at`,
   skip-if-`assembled`), the "unassembled" concept for a kept lane's
   already-finished work, and a `wave status`-visible per-lane outcome
   after assembly - all three are explicit PRD requirements (Test Strategy's
   edge case names "its done/ PRDs listed unassembled" as an expected
   observable), not gold-plating.
3. **A generic `run_git`/`run_checks`-free assemble that always shells out
   directly**: drop the two injected callables and call `subprocess.run`
   inline throughout, matching a "just make it work" minimal diff. Rejected:
   every existing wave verb (`plan`, `launch`, `abort`) is built test-first
   against a real `tmp_path` git repo specifically because these callables
   let a test substitute a `_FakeSpawn`-style recorder or, per this PRD's
   own Acceptance list (`test_checks_failure_undoes_the_lane_merge_and_keeps
   _it`), a `run_checks` stub that returns a chosen exit code without
   actually invoking `bash dev/bin/release-checks` inside a test fixture
   repo that has none. Matching the established pattern costs nothing extra
   here since `wave_launch.py` already proves it out.

## Risks & edge cases

- **`_reject_existing_wave` gap this PRD must close**: `WAVE_STATUSES`
  already lists `"done"`, but nothing before this PRD ever sets a wave to
  `"done"` - a fully-drained, never-assembled wave would have been stuck at
  `"running"` forever, and `wave plan` refuses to replace anything but
  `"done"`/`"aborted"`. This PRD's `"assembled"`/`"assembled_partial"` are
  the first values that actually reach that terminal state naturally, so the
  `_reject_existing_wave` check must accept them too or the same trap
  reappears one status name later. (Whether `"done"` itself should still be
  reachable some other way is out of scope here - it is simply not touched.)
- **Rebase rewrites lane commits**: acceptable per the PRD - branches are
  unpublished, and `wave["assembly"]["head_sha"]` plus each lane's
  (pre-rebase) `files`/`integrator_notes` are the durable record of what
  each lane contributed, independent of the rewritten shas.
- **A kept lane blocks nothing**: later lanes still merge; the runbook
  (`waves.md`) states the manual finish-then-rerun path explicitly, and
  `assemble` is safe to call again once the operator has rebased the kept
  lane by hand onto the (possibly moved) assembly head, because unmerged
  lanes are re-attempted on every call and merged ones are skipped via
  `lane["status"] == "assembled"`.
- **Two likely next changes**: (1) 00216 (review the assembled branch, land
  it on master) reads `wave["assembly"]["branch"]`/`head_sha` and this PRD's
  per-lane `files` to size its review scope - so neither field's shape
  should change without checking 00216's design once it exists; (2) 00217's
  review-slot semaphore is orthogonal (concurrency during a *running* wave,
  not assembly of a *drained* one) and touches none of this PRD's code.
  Nothing in this design boxes either one in: `assembly` is a plain dict
  appended to `wave.json`, not a new file, so a future field is additive.
- **`state-schema.md`'s "wave.json shape" pointer** (`waves.md`'s own intro
  line names it) is intentionally left unedited - it is not in this PRD's
  Repository Structure list. The four new lane statuses and the `files`/
  `integrator_notes`/`migrated_at`/`conflict_detail` fields exist in
  `wave.py` and are exercised by tests, but the prose description in
  `state-schema.md` will drift until a later change touches that file.
  Flagged, not fixed here, per this PRD's own explicit file list.

## Test strategy outline

Every proof is a real `git init` repo under `tmp_path` with real lane
branches (the `test_wave_launch.py` `_repo`/`_git`/`_recording_git` fixtures
are reused verbatim - `from cli.test_wave_launch import _git, _repo` rather
than re-authoring them), plus a `_planned_and_launched`-style helper unique
to this file that additionally fast-forwards a lane branch past `base_sha`
with a couple of real commits (one carrying an `Integrator:` trailer) and
marks the lane `drained` (a `state.json` with `next_phase: ""` dropped into
the lane worktree, matching `lane_status`'s own contract) or leaves it
`unfinished` (`next_phase` non-empty) as each test needs. `run_checks` is a
stub in most tests (returns a fixed `CompletedProcess`); one test only
constructs a fixture repo whose `dev/bin/release-checks` is a trivial
`exit 0`/`exit 1` shell script to prove the default wiring end to end.

Per-task acceptance lists are already enumerated verbatim in the PRD's
Implementation Phases and are the authoritative test names; this section
adds only the fixtures/mechanics that list does not spell out:

- `keep_both`/`summary` tests take plain strings/dicts, no fixture at all.
- The merge-pass tests (`test_assemble_merges_drained_lanes_in_order`, the
  two conflict tests, `test_checks_failure_undoes_the_lane_merge_and_keeps
  _it`, `test_unfinished_lane_is_skipped_not_merged`,
  `test_live_lane_refuses_assembly`,
  `test_assemble_records_each_lanes_files_and_integrator_trailers`) each
  build a 2-3-lane planned-and-launched wave, hand-edit one lane branch with
  real commits (a same-line conflict for the "other conflict" case, a
  `CHANGELOG.md` append for the append-only case), kill the recorded pid (or
  leave it alive for the live-lane test), and assert on the returned exit
  code, the saved `wave.json`'s per-lane `status`/`conflict_detail`, and
  (for the conflict tests) the written `deferred/<wave id>-deferred.json`
  (no "wave-" prefix - see Interfaces & contracts' dispatch-2 correction).
- The migration tests
  (`test_ledger_rows_gain_lane_and_wave_fields`,
  `test_dispatch_rows_migrate_too`,
  `test_deferred_items_migrate_idempotently`,
  `test_prds_land_in_done_hold_or_backlog_by_lane_status`,
  `test_merged_worktrees_and_branches_are_removed`,
  `test_kept_lane_keeps_its_done_prds_and_worktree`) seed a lane worktree's
  `dev/local/autopilot/` with hand-written fixture rows/files before calling
  `assemble`, then assert on the main checkout's copies (tagged rows,
  `record_defer` output, PRD locations) and, for `test_deferred_items_
  migrate_idempotently`, call `migrate_lane` twice directly and assert the
  second call appends nothing.
- `test_rerun_is_idempotent` runs `assemble` twice over the same wave with
  no state changed in between and asserts identical exit code and an
  unchanged `wave.json` (modulo nothing - a true no-op rerun changes zero
  bytes since every lane is already `"assembled"`/terminal and every
  `migrated_at` is already set).
- `test_docs_name_the_site_and_the_summary` follows `test_wave_docs.py`'s
  anchored-region pattern exactly (`_checks_block`/`_pytest_paths` reused
  via import, or duplicated if that file's helpers are not exported for
  cross-file reuse - checked at implementation time) to pin `assembly_
  conflict` inside `recovery.md`'s Stall `site` slugs section and `-wave.md`
  inside both `batch-report-format.md`'s new section and `SKILL.md`'s
  Retention list.

## Review log

### Dispatch 1 (claude) findings not fixed (non-blocker / question)

- **non-blocker**: `assemble()` never runs `wave._structural_errors(repo,
  wave)` as a precondition (unlike `launch`'s `_refusal()` and `abort`,
  both of which do), and `wave_cli.py`'s dispatch places the `assemble`
  branch before the generic "no wave.json; run plan first" friendly-message
  block every other verb gets. A missing or corrupt `wave.json` plausibly
  crashes on `wave["lanes"]`/`wave["status"]` against `None` instead of
  printing a controlled message. Suggested fix: run `_structural_errors`
  as `assemble`'s own first precondition and dispatch it alongside
  `launch`/`status`/`abort`, after that shared check.
- **non-blocker**: `worktree_removed` (introduced in `assemble`'s contract
  as load-bearing rerun-safety state) has no `_LANE_OPTIONAL_CHECKS` entry,
  unlike every other field this design adds for the same "resume after a
  crash" purpose. Suggested fix: add
  `"worktree_removed": lambda v: v is None or isinstance(v, bool)`.
- **non-blocker**: this design's Module placement claimed `waves.md`'s
  "Deferred: assembly and review slots" section has a stale "00216"
  cross-reference to correct to "00217". Checked against the file directly
  (`rg -n "00216"` - no hits; `rg -n "00217"` - hits, confirming the search
  itself works): no such "00216" reference exists: the section already
  correctly names the review-slot semaphore as 00217. Only the "Assembly
  ... is PRD 00215" bullet needs rewriting (assembly is no longer
  deferred); no PRD-number correction is needed anywhere in that edit.
- **non-blocker**: caught and folded into the blocker-3/4 fixes above
  during this same pass (the optional-field count/list disagreed between
  Module placement's summary and the Interfaces & contracts code block) -
  no separate action needed; noted here only so the finding has a record.
- **question**: `wave["assembly"]["merged"]` / `["kept"]`'s element type
  (lane name strings, or full lane dicts?) is unspecified, and 00216 is
  flagged elsewhere in this doc as a reader of exactly this structure.
- **question**: whether an `"unfinished"` lane (no conflict, no
  checks-failure, just still-dead-with-work-left) counts toward `kept`
  (and therefore `assembled_partial`/exit 3) is only inferable, never
  stated, and the Test Strategy's scenarios do not cover an
  unfinished-only wave.

dispatch 1 (claude): cardinal-sin 0, blocker 4, non-blocker 4, question 2

### Dispatch 2 (claude-fallback) findings not fixed (non-blocker / question)

dispatch 2: codex unavailable, Claude fallback (codex hung twice on this
task - the first attempt derailed into reading an unrelated skill file
after a tool-use hook denial and never produced findings; the retry showed
zero output growth and near-zero CPU progress for 5+ minutes and was
killed as a hang, not a parse failure).

- **non-blocker**: `record_defer`'s op_id dedup
  (`f"wave-{wave['id']}-{lane['name']}"`) can leave a STALE
  `assembly_conflict` record after a second, differently-shaped conflict on
  the same lane - a retried kept lane that conflicts on a different path
  the second time silently keeps its first attempt's `conflict_detail`/
  `files` in the deferred record, since `record_defer` skips the append
  outright once that op_id exists rather than updating it. Undermines the
  PRD's own success metric ("every kept lane's `assembly_conflict` record
  names the exact conflicted paths").
- **non-blocker**: `merge_lane` never clears a lane's stale
  `conflict_detail`/`conflict_paths` when a later call returns "assembled"
  for the same lane - untidy residual state in `wave.json` (a lane marked
  successfully assembled still carries its old failure detail alongside),
  though nothing currently reads those fields on the success path so it
  does not visibly break the report.
- **question**: does a crash between `migrate_lane`'s guarded jsonl appends
  and setting `migrated_at` risk duplicate rows BEYOND what the PRD's own
  "Row duplication on rerun" risk already accepts? The accepted risk is
  about retrying an unfinished migration; a mid-step crash (some rows
  already flushed, `migrated_at` never set) replays the WHOLE guarded step
  from the top on the next call, which can duplicate rows for an
  otherwise-clean, conflict-free lane too (e.g. `assemble` killed mid-run) -
  plausibly a strict superset of the accepted risk. Worth confirming this
  is intentionally accepted rather than overlooked.

dispatch 2 (claude-fallback): cardinal-sin 0, blocker 2, non-blocker 2, question 1

### Dispatch 3 (claude-fallback, verification) findings not fixed (non-blocker / question)

dispatch 3: codex unavailable, Claude fallback (codex had already failed
twice this session for this exact task - one garbled/derailed run, one
hang with zero output growth over 5+ minutes; a third attempt was judged
low-value and skipped in favor of a direct fallback).

- **non-blocker**: the PRD's own Outputs bullet for the merge feature still
  describes the pre-fix, un-wave-scoped worktree path
  (`<repo parent>/<repo basename>-wave`, no wave id) - the design
  deliberately overrides this (a reasonable HOW refinement of the PRD's
  WHAT), but nothing in the design flags that the PRD text itself is now
  stale on this one point, which a PRD-literal reader (a future blind
  review lens, or an implementor who only skims the PRD) could read as the
  authoritative shape and reintroduce the collision this design closed.
- **question**: when a lane's batch id cannot be resolved (neither
  `state.json` nor a `*-state-final.json` exists), `migrate_lane`'s
  docstring says jsonl tagging still runs with no id, but does not say how
  the SAME lane's `deferred/<lane batch id>-deferred.json` is located for
  the following `record_defer` step - whether a `None` id simply finds no
  file to migrate (safe) or could pass `batch_id=None` into
  `records.record_defer`, which raises `ValueError` on any non-string
  `batch_id` per the real `cli/records.py`. Needs an explicit answer at
  implementation time; not resolved here.

Its one blocker (Data flow's worktree-add line still showed the
pre-dispatch-2 fixed path) is fixed above; Data flow now reads
`<repo>-wave-<id>`.

dispatch 3 (claude-fallback): cardinal-sin 0, blocker 1, non-blocker 1, question 1
