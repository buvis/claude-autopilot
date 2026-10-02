# Enter the build gate in one CLI call - Design

## Architecture fit

`cli/enter.py` is a new Foundation-layer module in `skills/run-autopilot/cli/`,
peer to `resume.py`, `selection.py`, `custody.py`, `frontmatter.py`, and
`records.py`. It adds **no new policy** - every decision it makes already
exists as an importable pure function or a state-mutating verb in one of
those modules. `enter()` is purely an **orchestrator**: it calls the existing
functions in the documented Phase 0 order and translates each return value
into one field of the output JSON, stopping at the first step that demands
attention outside the deterministic chain (a park, a stall, a custody
backlog, a drained batch, a non-`full` lane, an empty review log).

It sits below `cli/__main__.py`'s subparser layer (Core Layer) exactly like
every other verb, and is consumed by `references/phase-build.md` § Phase 0
(Integration Layer), which replaces its own step-by-step Bash chain with one
`autopilot enter` call plus a stop-value dispatch table.

**Path convention note (verified live against this repo's own checkout, not
the installed plugin cache):** this repo's own `skills/run-autopilot/*`
already targets `docs/dev/project-management/<autopilot|prds|reviews|designs|meta>/`
and `docs/dev/tmp/` (the buvis `rules/working-documents.md` convention),
distinct from the older `dev/local/` layout an installed 0.5.6 plugin still
ships. Every path in this design is written against the **live repo source**
(`AUTOPILOT_REL_PATH` in `scripts/_walk_up.py`, `custody.project_root`,
`__main__._project_root`) - confirmed by diffing this repo's files against
the installed cache before writing this revision, after the first draft of
this doc was caught doing exactly the opposite (see `## Review log`).

## Module placement

New files:
- `skills/run-autopilot/cli/enter.py` - `enter()`, `STOPS`, the git-HEAD and
  review-log helpers.
- `skills/run-autopilot/cli/test_enter.py` - one test per stop value plus the
  null path and the CLI wrapper tests.
- `skills/run-autopilot/cli/test_enter_prose.py` - pins the three prose
  changes below.

Edited files:
- `skills/run-autopilot/cli/__main__.py` - one `_add_enter`/`_run_enter` pair
  registered in `_SUBCOMMANDS` (the existing registry pattern; no new
  dispatch mechanism).
- `skills/run-autopilot/references/phase-build.md` - new `### Enter in one
  call` section directly after the session-brief paragraph in Phase 0, plus
  one `autopilot enter runs this` line appended to each existing Phase 0
  subsection it now covers (Ensure lifecycle directories, Clear inherited
  hand-off markers, Handle park request, Handle Work-phase abort, Handle
  pending custody, Normal PRD selection, Frontmatter parse, § 5.5 Route by
  lane) and to Phase 1 (Batch cache check) and Phase 1.5 (the design-doc
  existence check / empty-review-log gate).
- `skills/run-autopilot/SKILL.md` - one sentence in § "Phase 0 invariants"
  naming `autopilot enter` as the first Bash call of a build session.
- `dev/bin/release-checks` - add `test_enter.py test_enter_prose.py` to the
  existing pytest invocation line (same pattern as every prior CLI module).
- `CHANGELOG.md` - one `### Added` / `**run-autopilot**` line.

## Interfaces & contracts

### `cli/enter.py`

```python
STOPS: tuple[str, ...] = (
    "fs_error",
    "park_halt", "mv_verify", "deferred_io", "stall_op_conflict",
    "stall_op_malformed", "park_precondition_failed",
    "replan", "escalation_exhausted", "cap_pause",
    "custody", "drained", "prd_not_found", "batch_init", "lane",
    "state_write_failed", "design_review_log_empty",
)

def enter(
    state_path: Path,
    *,
    prds_dir: Path,
    autopilot_dir: Path,
    prd_arg: str | None,
    in_loop: bool,
    now: Callable[[], str] = _utc_now,
    git_head: Callable[[Path], str | None] = _git_head_sha,
    record_resume_row: Callable[[str, str], None] = _record_resume_row,
) -> dict:
    """Run the Phase 0 step chain in documented order; return the one JSON
    line (see the schema below). `now`, `git_head`, `record_resume_row` are
    the three side-effecting callables not already owned by an existing
    module (the clock, `git rev-parse HEAD`, and the cross-pack
    `record_dispatch.py handoff` row) - injected so `enter()` itself is
    testable with fakes. Every other side effect (state reads/writes, the
    park executor, custody, selection, frontmatter) runs through the
    existing module that already owns it; `enter()` performs no ad hoc
    path arithmetic where an existing helper (`custody.project_root`,
    `_resolve_prds_path`) already computes it correctly.
    """
```

Output schema (`json.dumps(..., sort_keys=True)` on stdout, **exactly one
line**, exactly these keys - a superset key is a contract break the prose
test catches via `STOPS`):

```
{"stop": <null|one of STOPS>, "detail": <string>, "prd": <string|null>,
 "source": <"wip"|"backlog"|"arg"|null>, "parked": <string|null>,
 "custody_pending": <int>, "lane_effective": <string|null>,
 "catchup": <"skip"|"delta"|"full"|null>, "design": <"skip"|"reuse"|"run"|null>,
 "resume_target": <string|null>, "batch": <"open"|"absent"|"closed"|null>}
```

`batch` gained `|null` over the PRD's own draft schema (a real defect the
review caught, not a PRD change): four earlier steps (park, stall/cap-pause,
custody-outside-the-loop, select) can each stop before step 9 ever evaluates
`batch`, and `"absent"` is already a load-bearing, *checked* condition
("`state.batch` key is missing") that must not double as "this step never
ran." `null` means the latter; the dispatch table's stop-specific rows never
need to read `batch` at all, so this costs nothing downstream.

`detail` is the human-readable one-liner for the `stop` (empty string when
`stop` is null) - the same string the CLI wrapper prints to stderr and the
skill quotes verbatim in its banner/pause_reason. `resume_target` is `null`
on every stop reachable before step 6 runs (`resume_target` is computed at
step 6) - not only the three step-5 stalls, but also `fs_error` (steps 0/2),
`stall_op_malformed` (step 3), and every step-4 park-family stop, since
step 6 never runs on any of those paths either.

### Step chain (each step is a call into an existing function; `enter()` adds only the glue)

0. **mkdir** - `for name in ("backlog","wip","done","hold"): (prds_dir/name).mkdir(parents=True, exist_ok=True)`,
   `(prds_dir.parent/"reviews").mkdir(...)`, `(prds_dir.parents[1]/"tmp").mkdir(...)`
   (`docs/dev/tmp`, NOT nested under `project-management/` - confirmed against
   the pinned `mkdir -p` line in `SKILL.md` § Phase 0 invariants, not assumed),
   `(autopilot_dir/"reports").mkdir(...)`, `(autopilot_dir/"deferred").mkdir(...)`.
   Wrapped in `try/except OSError` (review-caught: the first draft left these
   raw, unlike every other filesystem-touching function in the codebase,
   which all catch `OSError` and return a coded exit) - on failure,
   `stop="fs_error"`, `detail=str(err)`. Runs FIRST, before the bootstrap
   step below (review-caught, verification pass: `state.init` writes via
   `tempfile.mkstemp(dir=str(path.parent))`, so `autopilot_dir` must already
   exist before it can run - the original ordering had this backwards).
   **Pre-existing limitation this design does not fix:** `_run_enter`'s
   default `--state` resolution (`_walk_up_or_exit`, used by every verb, not
   new here) still requires SOME ancestor named `docs/dev/project-management/autopilot`
   to already exist above cwd, or it exits 1 before `enter()` ever runs.
   `enter()` bootstraps the *file*, not that first ancestor directory; a
   truly-from-nothing repo must pass `--state` explicitly (or have the
   directory pre-created) for its very first call, exactly as every other
   verb already requires today.
1. **bootstrap state.json if absent.** `state_path.exists()` is checked
   before any step that reads state - a brand-new repo's first `autopilot
   enter` call has no file yet, and core `SKILL.md`'s Gate Dispatch table
   already treats a missing `state.json` as a legitimate "fresh start," not
   an error. When absent: `state.init(state_path, {"phase": "build",
   "next_phase": "build"})` (the exact initial dict `_run_init` already
   writes, minus the `--prd` field `_run_init` requires but `enter()`
   doesn't know yet - selection hasn't run). This makes every later step's
   `state.load`/`state.transaction` call succeed unconditionally from here
   on. (Review-caught: the first draft of this design let `records.do_park`'s
   own `state.load` failure - which returns exit 2 for *any* unreadable
   state, missing or corrupt, indistinguishably - stand in for "fresh
   start," which would have made `autopilot enter` unusable on a brand-new
   repo. `state.init` raises `StateExistsError` only when the file already
   exists, which this branch has already excluded, so it cannot race itself
   within one process.)
2. **clear markers** - `for name in _walk_up.INHERITED_MARKERS: (autopilot_dir/name).unlink(missing_ok=True)`
   (`_walk_up.INHERITED_MARKERS` reused directly; no walk-up needed, `enter()`
   already has the resolved `autopilot_dir`). `missing_ok=True` makes this
   step itself unable to raise `FileNotFoundError`; a different `OSError`
   (permissions) is folded into the same `try/except` as step 1, same
   `"fs_error"` stop - matching `_walk_up._main_clear_markers`'s own
   best-effort contract (never blocks Phase 0 on a marker it can't remove) by
   still surfacing the rare failure rather than silently eating it, since
   `enter()`'s single JSON line is the only place left for that to surface.
3. **load state + malformed-stall_op precheck** - `state.load(state_path)`.
   Any `state.StateError` here IS the CLI's own exit-2 case (§ CLI wrapper
   below) - by construction this can now only be a genuinely corrupt file,
   never "missing" (step 1 excluded that). Then, WITH A PRESENCE GUARD
   (review-caught, verification pass: `records._stall_op_malformed(None)`
   returns `True` in the live implementation - a bare, unguarded call would
   stop every ordinary state that simply has no `stall_op` at all, which is
   most of them):
   ```python
   stall_op = current.get("stall_op")
   if stall_op is not None and records._stall_op_malformed(stall_op):
       stop = "stall_op_malformed"
   ```
   (`records._stall_op_malformed` reused directly - the exact check
   `do_park`'s and `do_stall`'s own guards use). This narrows, but does NOT
   fully close, `do_park`'s exit-2 ambiguity - see step 4's `park_precondition_failed`
   below (review-caught, verification pass: `do_stall`'s own step-0 guard,
   reached only via the marker/stall_op reconciliation path inside `do_park`,
   ALSO returns exit 2 for a missing `batch.id` or a `cap_critical` capture
   failure - causes this step-3 precheck cannot see, since they live inside
   `do_stall`, not in the state shape step 3 inspects).
4. **park** - `io.StringIO()` capture via `contextlib.redirect_stdout`
   around `records.do_park(state_path, prds_dir=prds_dir, autopilot_dir=autopilot_dir)`.
   (Review-caught: `do_park` prints its own status lines to stdout on the
   ordinary no-marker path and the parked path - `"autopilot: no
   park-requested; nothing to do"`, `"autopilot: parked {prd}..."` - which
   would land inside `enter()`'s promised single-JSON-line stdout. The
   captured text carries nothing `enter()` doesn't already derive from the
   exit code and its own pre-call marker read below, so it is discarded, not
   forwarded.) Read the marker itself (`records._parse_marker`) BEFORE
   calling `do_park` (which deletes it on a successful park), so `parked`
   is knowable independent of `do_park`'s own report. Exit 3 -> continue,
   `parked` stays `None`. Exit 0 -> continue, `parked` = the marker's `prd`.
   Exit 5 -> `stop="park_halt"`, `detail=f"parked {prd}; systemic halt (2+
   consecutive wrapper_died parks)"`. Exit 4 -> `stop="mv_verify"`. Exit 9 ->
   `stop="deferred_io"`. Exit 10 -> `stop="stall_op_conflict"`. Exit 2 ->
   `stop="park_precondition_failed"` (a NEW, DISTINCT token - review-caught,
   verification pass: step 3 only excludes "state unreadable" and "malformed
   stall_op" from `do_park`'s own two exit-2 causes; `do_stall`'s deeper
   internal guard, reachable only through `do_park`'s marker/stall_op
   reconciliation path, can ALSO exit 2 for a missing `batch.id` or a failed
   `cap_critical` range capture - neither of which step 3 can see, so this
   is NOT provably the same "unreadable state" case the CLI wrapper's own
   exit 2 means, and claiming otherwise would be asserting something this
   design cannot verify. `detail` names the exit code and points at
   `do_stall`'s preflight guard as the source, rather than guessing which of
   its internal causes fired).
5. **stall/cap-pause checks** - re-load `state.json` (park may have mutated
   it); delete `pause_reason` unconditionally first via `statectl.mutate` if
   present (mirrors core `SKILL.md` § Resuming - this is the ONE place that
   rule now lives in code instead of prose). Then:
   `stall_reason.stalled == "subagent_prompt_overrun"` -> `stop="replan"`;
   `== "escalation_exhausted"` -> `stop="escalation_exhausted"`;
   `phase == "paused" and cap_pause_reason` -> `stop="cap_pause"`. None of
   these three stops mutate state further - the skill's own recovery
   handlers (`references/recovery.md`) own the follow-up writes, exactly as
   today.
6. **resume_target** - `resume.resume_target(state)` (the state as reloaded
   in step 5, pre-selection) -> `resume_target` field. Reached only when
   steps 3-5 did not stop (documented order: this step is "later" relative
   to any of those stops, so `resume_target` stays `null` on all of them -
   see the schema note above).
7. **custody** - `custody.pending(autopilot_dir)` -> `custody_pending` = its
   length. `custody.CustodyError` -> treat as `stop="deferred_io"` (shared
   with step 4's exit 9 - both mean "a durable Phase-0 record was
   unreadable/unwritable," and the skill's dispatch table routes both to
   "§ Handle pending custody" via the `detail` text, not the bare token).
   Outside the loop (`in_loop is False`) and count > 0 -> `stop="custody"`.
   In the loop, count is carried in `custody_pending` and selection
   continues (matches today's `custody: <n> entries await an attended
   resume` print, which the skill still prints itself from the field).
8. **select** - `prd_arg` given: present in `wip/` -> `source="arg"`, no
   eligibility check (matches "Normal PRD selection" step 1 - a `wip/`
   candidate is already past the eligibility question); present in
   `backlog/` -> `source="arg"` after the verified move; absent from both ->
   `stop="prd_not_found"` (a NEW, DISTINCT token - review-caught: the first
   draft reused `mv_verify` here, but nothing was being moved, and the
   skill's existing `mv_verify` handler retries a move and can PAUSE the
   whole batch - the wrong recovery action for "the operator typed the
   wrong filename"). No `prd_arg`: `selection.select(listdir(prds_dir/"wip"), listdir(prds_dir/"backlog"))`
   plus the eligibility loop, lifted from `_run_select`'s body into a shared
   `selection.select_eligible(prds_dir, project_root) -> tuple[str|None, str, list[dict]]`
   that returns data only (prints nothing - the printing stays in the CLI
   wrapper `_run_select`, which becomes a thin caller of this same function,
   so the two verbs cannot drift). `source="drained"` -> `stop="drained"`.
   `source="backlog"` -> move with the verified-move invariant
   (`shutil.move` + existence check - not `git mv`, since PRDs under
   `docs/dev/project-management/` are untracked, confirmed live in this
   session's own Phase 0); a failed verify -> `stop="mv_verify"` (this IS a
   real move that failed - the token fits here). Skips (the loop's third
   return value) are recorded unconditionally now via a `_record_skips`-
   equivalent - step 0's bootstrap means `state_path.exists()` is always
   true by this point, so the old "only when state_path.exists()" guard in
   `_run_select` (needed there because a truly-fresh `select` call could
   predate `state.json`) no longer applies inside `enter()` and is not
   carried over (review-caught: without step 0's bootstrap, a fresh batch's
   very first eligibility skips would have been silently dropped, since the
   PRD's own step 8 stops with `batch_init` before frontmatter/state-init
   ever ran in the original draft).
9. **batch report** - re-load state; `state.batch` missing OR present but
   its `id` key is missing/not a string -> `batch="absent"` (NOT a bare
   `"batch" not in state` check - step 8's skip-write, when it fires, calls
   `statectl.mutate` with `data.setdefault("batch", {}).setdefault("skips",
   []).extend(...)`, which can leave `state.batch = {"skips": [...]}` with
   no `id` on a genuinely fresh batch; `batch.id` is the field
   `references/phase-build.md` § Normal PRD selection step 3 actually gates
   "already present" on, so checking for it, not merely for the `batch` key,
   is what makes this step correctly stop on a batch that skip-recording
   partially created); present with a valid `id` and `phase=="done" and
   next_phase==""` -> `batch="closed"`; both -> `stop="batch_init"` (the
   skill's own Normal PRD selection step 3 owns minting/rolling the batch,
   including the `plugin_versions` pin, which reads the installed-plugins
   file - a policy decision left in the skill, not `enter()`; that same step
   3 already handles "preserve an existing `skips` list on an otherwise-fresh
   batch" as part of minting, so nothing here is lost). Otherwise
   `batch="open"`, continue. (Review-caught,
   verification pass: this step existed in `STOPS` and in the Test strategy
   outline's list of `batch_init` cases, but the prior revision's step chain
   never actually reached it - steps went straight from select to
   frontmatter. Reinserted here, in the position the original PRD's own
   Behavior list names: after selection, before the frontmatter write.)
10. **write prd + frontmatter + handoff row, THEN the lane check** - in this
   exact order (review-caught: the first draft stopped on a non-`full` lane
   BEFORE writing the handoff row, silently dropping it for every solo/
   fast-track PRD, even though the existing Normal PRD selection procedure
   writes that row unconditionally for the selected PRD):
   1. `statectl.mutate` to set `state["prd"] = prd`.
   2. `frontmatter.apply(prd_path, state_path) -> tuple[dict, list[str]]`
      (fields, warnings) - the existing `_run_frontmatter` body factored out
      into this shared, non-printing core (both the standalone `autopilot
      frontmatter` verb and `enter()` call the identical one-transaction
      write; `_run_frontmatter` becomes the thin CLI wrapper printing
      `fields`/warnings to stderr, unchanged from today's behavior). Wrapped
      in `try/except (OSError, state.StateError, schema.SchemaError)` ->
      `stop="state_write_failed"`, `detail=str(err)` (review-caught,
      verification pass: the live `_run_frontmatter` already catches an
      unreadable PRD path as `OSError` and a failed transaction as
      `state.StateError`/`OSError`, both returning exit 2 from that
      standalone verb; the prior revision's `enter()` sketch caught neither,
      so either failure would have propagated out of `enter()` uncaught
      instead of producing the promised JSON line).
   3. `record_resume_row(prd, "build")` unconditionally - the injected
      callable; the default resolves the sibling pack's script from
      `enter.py`'s own file location (review-caught, verification pass: the
      first draft wrote the path as `work/scripts/record_dispatch.py`,
      borrowing the `${CLAUDE_PLUGIN_ROOT}`-prefixed form
      `references/phase-build.md` uses in Bash/SKILL.md prose - but per
      `rules/claude-tooling.md`, that placeholder resolves ONLY in SKILL.md
      bodies and `hooks.json`, never inside a Python script, and no existing
      `cli/*.py` file shells out to `record_dispatch.py` today, so there was
      no established pattern to copy). Correct resolution, `enter.py` sits
      at `skills/run-autopilot/cli/enter.py`:
      ```python
      _RECORD_DISPATCH = (
          Path(__file__).resolve().parents[2]
          / "work" / "scripts" / "record_dispatch.py"
      )
      ```
      (`parents[0]` = `cli/`, `parents[1]` = `run-autopilot/`, `parents[2]`
      = `skills/` - the common ancestor both packs share). Then
      `subprocess.run(["python3", str(_RECORD_DISPATCH), "handoff",
      "--site", "build", "--edge", "resume", "--phase", "build", "--prd",
      prd], timeout=10, ...)`, swallowing failure to stderr (matching the
      existing row's best-effort contract; see Alternatives for why this
      stays a subprocess call rather than a cross-pack import). A test
      asserts `_RECORD_DISPATCH.exists()` against the real repo tree, so a
      future pack reshuffle that moves `work/scripts/` fails loudly here
      instead of silently swallowing every resume row (review-caught: left
      unresolved, this would have been "exactly the 'wrong parent' defect
      class this design review already caught twice elsewhere" - a silent,
      permanent, best-effort-swallowed failure of the resume-handoff-row
      metric the PRD's own Success Metrics section measures).
   4. THEN read `lane_effective` from `fields`; not `"full"` ->
      `stop="lane"`, `detail=f"lane: {fields['lane']} ({fields['lane_reason']})"`.
11. **catchup decision** - `catchup_mode in ("skip","skipped")` ->
    `catchup="skip"`, and if it was `"skip"` write it to `"skipped"` (matches
    Phase 1's own skip-write). Else evaluate the three batch-cache
    conditions from `references/phase-build.md` § Batch cache check: (a)
    `catchup_mode != "force"` or `tasks` is a non-empty list, (b)
    `batch.catchup_completed_at` present and < 4h old (`now()` minus the ISO
    timestamp), (c) `batch.catchup_head_sha == git_head(repo_root)` where
    `repo_root = custody.project_root(autopilot_dir)` (reused directly -
    review-caught: the first draft hand-rolled `autopilot_dir.parents[2]`,
    which is not merely stale under the old path convention but was never
    correct for any override depth `custody.project_root`'s own guard exists
    to handle; calling the existing function removes the bug and the
    duplication at once). `git_head` returning `None` (repo unreadable,
    unborn HEAD) counts condition (c) as failed, forcing `catchup="full"`
    (the safe side). All three hold -> `catchup="delta"`. Any fails ->
    `catchup="full"`. **`enter()` does not itself invoke `/git-ferry:catchup`
    or write `catchup_completed_at`/`catchup_head_sha`** - those remain the
    skill's job after this call returns (a headless CLI call cannot invoke a
    Skill), exactly as the PRD's Behavior step 11 only asks for the
    classification, not the run.
12. **design decision** - `design_mode == "skip"` -> `design="skip"`. Else
    compute `design_doc = autopilot_dir.parent / "designs" / f"{prd_stem}-design.md"`
    (i.e. `docs/dev/project-management/designs/<stem>-design.md` - review-
    caught twice, independently, by both reviewers: the first draft used
    `autopilot_dir.parents[1]`, which is one level too high regardless of
    which path convention it's read against; `.parent` - `parents[0]` - is
    the sibling directory `prds/`, `reviews/`, and `designs/` all share);
    doesn't exist -> `design="run"`. Exists -> run the review-log check
    (`_review_log_has_dispatch_line(text)` below); passes -> `design="reuse"`;
    fails -> `stop="design_review_log_empty"`,
    `detail=f"{design_doc} has empty ## Review log (review never ran)"`.
    `enter()` does not invoke `/autopilot:design-solution` (same
    CLI-cannot-invoke-Skill reasoning as step 11) and does not write
    `state.design_doc` - the skill still does that after receiving
    `design="run"|"reuse"`, mirroring Phase 1.5's existing contract.
13. **stop null** - `resume_target`, `catchup`, `design` all populated; the
    skill proceeds straight to Phase 1 using the returned `catchup`/`design`
    values without re-deriving them.

### `_review_log_has_dispatch_line(text: str) -> bool`

Pure Python port of the pinned `awk` in `SKILL.md` § "Design-gate invariant"
(confirmed against the live line, not the cache's copy - both are
byte-identical in this case, so no wording change was needed here), same
regex, same section-scoping, so the two can never drift silently (a future
edit to the `awk` line must be mirrored here by hand - `test_enter_prose.py`
pins the `awk` line's literal text so an edit to one without the other fails
release-checks):

```python
_DISPATCH_RE = re.compile(
    r"dispatch \d+ \((claude|codex|claude-fallback)\): "
    r"cardinal-sin \d+, blocker \d+, non-blocker \d+, question \d+"
)

def _review_log_has_dispatch_line(text: str) -> bool:
    in_section = False
    for line in text.splitlines():
        if line.startswith("## Review log"):
            in_section = True
            continue
        if line.startswith("## "):
            in_section = False
        if in_section and _DISPATCH_RE.search(line):
            return True
    return False
```

### `_git_head_sha(repo_root: Path) -> str | None`

```python
def _git_head_sha(repo_root: Path) -> str | None:
    try:
        proc = subprocess.run(
            ["git", "-C", str(repo_root), "rev-parse", "HEAD"],
            capture_output=True, text=True, timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return proc.stdout.strip() if proc.returncode == 0 else None
```

Bare-repo-backed roots (`~/.claude` under `~/.buvis`) are **out of scope**
for this helper, same as `custody.project_root`'s own fallback (`.parent`
when the depth check misses): `state.git_dir` is only ever set by Phase 3
(work capture), never by Phase 0, so `enter()` has no `--git-dir` value to
pass at catchup time. Such a repo degrades to `catchup="full"` every entry
(condition (c) always fails). Noted, not fixed, in Risks.

### `cli/__main__.py`

```python
def _add_enter(subparsers) -> None:
    p = subparsers.add_parser("enter")
    p.add_argument("--state")
    p.add_argument("--prd")
    p.add_argument("--prds")

def _run_enter(args: argparse.Namespace) -> int:
    state_path = _resolve_state_path(args.state)
    refuse = _schema_version_preflight(state_path)
    if refuse is not None:
        return refuse
    autopilot_dir = state_path.parent
    prds_dir = Path(args.prds) if args.prds else Path(_resolve_prds_path(None, autopilot_dir))
    try:
        result = enter.enter(
            state_path,
            prds_dir=prds_dir,
            autopilot_dir=autopilot_dir,
            prd_arg=args.prd,
            in_loop=bool(os.environ.get("_AUTOPILOT_LOOP")),
        )
    except (state.StateError, state.StateExistsError) as err:
        print(f"autopilot: enter failed: {err}", file=sys.stderr)
        return 2
    print(json.dumps(result, sort_keys=True))
    if result["detail"]:
        print(f"autopilot: {result['detail']}", file=sys.stderr)
    return 0
```

`_schema_version_preflight` runs against whatever `state_path` currently
holds - on a step-0 bootstrap (no file yet), `state.load` inside the
preflight raises `state.StateError`, which its own `except` clause already
treats as "not this function's concern, let the caller's own load surface
it" (returns `None`, i.e. "no refusal") - so a fresh repo passes the
preflight and reaches `enter()`, whose own step 0 then creates the file.
This is existing behavior, unchanged by this design; confirmed by reading
`_schema_version_preflight`'s docstring rather than assumed.

Registered as `"enter": (_add_enter, _run_enter)` in `_SUBCOMMANDS`, same
registry every other verb uses - no new dispatch code.

## Data flow

```
Bash: autopilot enter --state ... [--prd ...]
  -> _run_enter (CLI wrapper: schema preflight, path resolution, exit 2)
    -> enter.enter(...)
        0. mkdir lifecycle dirs (try/except OSError)     [filesystem]
        1. state.init if state_path absent               [state.json, bootstrap]
        2. clear inherited markers (try/except OSError)  [filesystem]
        3. state.load + records._stall_op_malformed      [state.json, read-only]
        4. records.do_park, stdout captured & discarded  [state.json + hold/ move]
        5. state.load (fresh) + statectl.mutate(del pause_reason) + stall checks [state.json]
        6. resume.resume_target(state)                   [pure]
        7. custody.pending(autopilot_dir)                [marker + journal]
        8. selection.select_eligible(prds_dir)            [backlog/wip listing + eligibility subprocess + move]
        9. batch report (absent/closed -> batch_init)     [state.json, read-only]
       10. statectl.mutate(prd) + frontmatter.apply + record_resume_row + lane check [state.json, subprocess]
       11. batch-cache three-condition check              [state.json + git_head via custody.project_root]
       12. design-doc existence + review-log check        [docs/dev/project-management/designs/*.md]
       13. assemble + return the result dict
    <- one JSON dict
  print(json.dumps(result))                              [stdout, the caller's only read]
```

Every state mutation still goes through `state.transaction`/`statectl.mutate`
(single-writer, schema-validated, advisory-locked) - `enter()` introduces no
second writer and no new lock. The one addition, `state.init` at step 1, is
the same primitive `autopilot init` already uses, called with the identical
initial dict shape minus the not-yet-known `prd`.

## Reuse inventory

- `cli/state.init`, `cli/state.load`, `cli/state.transaction` - the
  bootstrap and read/write primitives every step above uses; `enter()`'s own
  two direct writes (delete `pause_reason`, set `prd`) go through
  `cli/statectl.mutate`, the existing `select`/`mint-stubs` pattern
  (`_record_skips`, `_record_minted`) reused verbatim for shape.
- `cli/records.do_park`, `cli/records._parse_marker`,
  `cli/records._stall_op_malformed` - called as-is (steps 3-4); the last one
  narrows, but (per the verification pass) does not fully close, the
  exit-2 ambiguity - see step 4's `park_precondition_failed`.
- `cli/resume.resume_target` - called as-is (step 6).
- `cli/custody.pending`, `cli/custody.CustodyError`,
  `cli/custody.project_root` - called as-is (steps 7, 11 - `project_root` is
  a new use of an existing function, replacing hand-rolled path arithmetic).
- `cli/selection.select`, `cli/selection.selectable` - the pure core, reused
  by the new `selection.select_eligible` wrapper (step 8).
- `cli/eligibility.command_for`, `cli/eligibility.evaluate` - called from
  the lifted `select_eligible` (step 8).
- `cli/frontmatter.parse`, `cli/frontmatter.declared` - called from the
  lifted `frontmatter.apply` (step 10).
- `cli/lane.classify`, `cli/lane.effective`, `cli/lane.LANES` - called from
  the lifted `frontmatter.apply` via the existing `_lane_fields` logic,
  moved alongside it.
- `scripts/_walk_up.INHERITED_MARKERS` - the marker-name tuple reused
  directly (step 2).
- `cli/__main__._schema_version_preflight`, `_resolve_state_path`,
  `_resolve_prds_path` - reused unchanged by the new `_run_enter` wrapper.
- `skills/work/scripts/record_dispatch.py` (the `handoff` subcommand) -
  reused via subprocess (step 10), not imported, located relative to
  `enter.py`'s own file path (`Path(__file__).resolve().parents[2]`), not a
  `${CLAUDE_PLUGIN_ROOT}` string (that placeholder does not resolve inside a
  Python script per `rules/claude-tooling.md`); see Alternatives for why a
  subprocess call at all.

**New glue code, not a reuse** (flagged so a task planner doesn't go looking
for an existing function that doesn't exist): the `--prd`-argument branch of
step 8 (`selection.select` takes no `prd_arg` parameter at all - the
present-in-wip/present-in-backlog/absent-from-both handling is new prose
this design writes out, composing `selection.selectable`'s membership check
with the verified-move invariant, not a call into a pre-existing function).

Nothing found for: a Python port of the design-gate `awk`
(`_review_log_has_dispatch_line` is new); a stdout-capture wrapper for a
reused CLI verb (`contextlib.redirect_stdout` is stdlib, no project helper
does this today - greps tried `redirect_stdout`, `StringIO` across
`cli/*.py`, both empty, confirming nothing to reuse rather than assuming it).

## Alternatives considered

1. **Chosen: one `enter.py` orchestrator calling existing functions,
   subprocess for the cross-pack handoff row, `state.init` bootstrap at
   step 0.** Smallest surface that keeps every existing verb (`park`,
   `select`, `frontmatter`, `custody`, `resume-target`, `init`) independently
   runnable and independently tested; `enter` adds zero new policy, only
   sequencing + JSON assembly + the three narrow fixes the review surfaced
   (a malformed-stall_op precheck, a stdout capture, a reordering).
2. **Cross-pack Python import of `record_dispatch.append_row`/`_handoff`
   instead of a subprocess call.** Saves one process spawn per session but
   requires `sys.path` surgery identical to what `record_dispatch.py` itself
   already does in the other direction (`importlib.util.spec_from_file_location`
   for `_walk_up`), coupling two independently-versioned skill packs at
   import time instead of at the existing CLI-invocation boundary. Rejected:
   the row is best-effort and already tolerates a failed write; a subprocess
   call framed as another best-effort step is a smaller behavior change than
   a new cross-pack import path, and it's the smallest-diff version of step 10.3.
3. **Inline every step's logic into `enter.py` instead of lifting
   `select`'s eligibility loop and `frontmatter`'s transaction into shared
   helpers.** Zero-risk to the existing verbs (they stay untouched) but
   creates two copies of the eligibility loop and two copies of the
   frontmatter transaction that can silently diverge - exactly the "verb
   drifts from the prose it replaces" risk the PRD names, except CLI-vs-CLI
   instead of CLI-vs-prose. Rejected: the lift is ~15 lines moved per site,
   and pinning `_run_select`/`_run_frontmatter` to call the same lifted
   function `enter()` calls is the only way to make two callers of the same
   logic provably identical rather than merely similar today.

The smallest-diff version is #3; the chosen design (#1, with the two lifts)
costs ~40 extra lines across `selection.py`/`frontmatter.py` to buy the
drift-proof guarantee the PRD's own Risks section asks for.

## Risks & edge cases

- **`enter()` cannot invoke a Skill.** Steps 10-11 classify `catchup` and
  `design` but never run `/git-ferry:catchup` or `/autopilot:design-solution`
  - those stay the skill's job, driven by the returned classification. A
  future session that treats a non-null `catchup`/`design` field as "already
  executed" would silently skip real work; `test_enter_prose.py` pins the
  prose wording specifically to keep this boundary legible to a reader, but
  nothing in code enforces it - a documentation-only guardrail, named here
  so it isn't mistaken for a code-enforced one.
- **Bare-repo-backed project roots always take `catchup="full"`** (see
  `_git_head_sha` above) - a real but pre-existing-in-spirit cost: no code
  previously computed `git_head` at Phase 0 at all before this PRD (the
  model did it by hand via Bash). Fixing it needs `state.git_dir`, which
  nothing populates until Phase 3, i.e. after `enter()`'s only call site.
  Next PRD candidate if such a repo's batches show the cost.
- **`resume_target` is null on any stop at or before step 5** (every
  park-family stop at step 4, plus the three step-5 stalls) - this is by
  design (those stops already carry an equivalent message via `detail`), but
  every one of the seven codes needs its own test asserting `resume_target
  is None`, not only the three stall ones (review-caught: the first draft's
  Risk note and its named test list covered only 3 of the 7).
- **A concurrent state.json corruption between step 3's load and step 4's
  `do_park` call** would surface as `do_park`'s exit 2 - by elimination
  (step 3 already excluded "missing" and "malformed stall_op") this is
  folded into the same exit-2-is-a-StateError handling step 3 uses, on the
  reasoning that within one single-writer-per-session process this window is
  the same class of race every other multi-step CLI verb in this codebase
  already accepts without a retry.
- **Two likely next changes**: (1) once `state.git_dir` is populated
  earlier, `_git_head_sha` gains a `git_dir` parameter and the bare-repo gap
  above closes; (2) `enter()`'s step boundaries are exactly where a future
  `--dry-run` would hook in, since steps 0-2 and 10's row/lane-check are the
  only ones with side effects beyond `state.json`/`hold/`/`wip/` - this
  design doesn't build `--dry-run` (not asked for), but the step-function
  decomposition is what keeps that addition cheap later.
- **A stop value the skill's dispatch table doesn't know.** `STOPS` growing
  without `references/phase-build.md`'s new table gaining a row is caught by
  `test_enter_prose.py::test_every_stop_value_has_a_row`.
- **`contextlib.redirect_stdout` only swaps Python's `sys.stdout` object, not
  OS file descriptor 1** (review-caught, verification pass). The narrow case
  it misses: if `do_park`'s reconciliation path (step 4) hits a pending
  `cap_critical` `stall_op`, `do_stall` calls `custody.record_critical`,
  which on a new notice calls `notify_out.notify`, which runs
  `subprocess.run([sys.executable, notify.py, ...])` with no `stdout=`
  kwarg - that child inherits real fd 1 and anything it prints bypasses the
  Python-level redirect. This requires a pending `cap_critical` stall
  reconciled at the exact moment `enter()` calls `do_park`, which is rare
  (custody stalls are already a loop-mode-only, systemic-halt-adjacent
  path) and not worth an `os.dup2` fd-level redirect for. Documented, not
  fixed - if `dispatch-metrics.jsonl` or a future batch shows this actually
  corrupting a caller's JSON parse, escalate to an fd-level redirect then.
- **`mv_verify` is deliberately the same token whether the failing move is
  `do_park`'s `wip/`→`hold/` (step 4, before `resume_target` is computed) or
  step 8's `backlog/`→`wip/` (after)** (review-caught, verification pass, and
  confirmed intentional against `SKILL.md`'s own "one PAUSE/retry-once
  handler for backlog→wip, wip→done, wip→hold" framing - not a defect, but
  worth saying plainly: the same stop name can carry a null or a populated
  `resume_target` depending on which move failed, and a reader inspecting
  only the `stop` field can't tell which without also checking
  `resume_target`).

## Test strategy outline

- `test_enter.py` - one test per `STOPS` value plus the null path, each
  driving `enter()` against a temp `state.json`/`prds/` fixture tree laid
  out as `docs/dev/project-management/{autopilot,prds,reviews,designs}` +
  `docs/dev/tmp` (no real git, no real subprocess for the two injected
  callables; `records.do_park`/`custody.pending`/`selection.select_eligible`/
  `frontmatter.apply` run for real against the temp tree, since they are
  already independently unit-tested and fast). Covers: a bootstrap call with
  no `state.json` at all proceeds through selection rather than exiting 2;
  fresh `wip/` PRD with tasks and fresh cache -> null stop, `catchup="delta"`,
  `design="reuse"`; a `--prd` argument selecting from `backlog/` with the
  verified move; a `--prd` argument naming neither `wip/` nor `backlog/` ->
  `prd_not_found` (asserting it is NOT `mv_verify`); a failed backlog move ->
  `mv_verify`; every `do_park` exit code mapped to its stop, including that
  `do_park`'s own stdout is captured and `enter()`'s stdout stays exactly one
  JSON line; a malformed `stall_op` -> `stall_op_malformed`, asserted
  distinct from a corrupt-file exit 2, AND asserted that an absent `stall_op`
  (the ordinary case) does NOT stop `stall_op_malformed` (the presence-guard
  regression this design almost shipped); `do_park` exit 2 reached via the
  reconciliation path (a pending `stall_op` plus a state missing `batch.id`)
  -> `park_precondition_failed`, distinct from step 3's own exit-2 cases; the
  three stall/cap-pause branches; `state.batch` absent/closed AFTER a fresh
  select -> `batch_init` is actually reached (not just declared in `STOPS`);
  `resume_target is None` on every stop reachable before step 6 runs
  (`fs_error`, `stall_op_malformed`, the five step-4 park-family stops, the
  three step-5 stalls - parametrized over the full list read from `STOPS`
  minus the stops that occur at or after step 6, not a hand-counted number);
  `pause_reason` present and deleted before any check runs; custody count
  above zero in-loop (continues) vs. out-of-loop (stops); drained;
  absent/closed batch, AND `batch is None` on an earlier stop (park/stall/
  custody/select), parametrized; a non-`full` lane, asserting the handoff row
  (`record_resume_row`, faked) was still called before the `lane` stop; a
  faked `record_resume_row` that raises, asserted to be swallowed to stderr
  (best-effort) without blocking the null-stop result; the default
  `record_resume_row`'s `_RECORD_DISPATCH` path resolves to a file that
  actually exists in the checked-out repo (not just a plausible-looking
  string); a `frontmatter.apply` that raises `OSError` (unreadable PRD) or
  `state.StateError` (a broken transaction) -> `state_write_failed`; the
  three-condition catchup delta/full split (parametrized over each condition
  failing alone), asserting `git_head` is called with the value
  `custody.project_root` returns, not a hand-computed
  path; a permission-denied mkdir (temp dir made read-only) -> `fs_error`; an
  existing design doc with/without a review-log dispatch line; every `STOPS`
  value is reachable (parametrized against the tuple itself).
- `test_enter_prose.py` - `references/phase-build.md` opens Phase 0 with
  `### Enter in one call` before `### Ensure lifecycle directories exist`;
  every `enter.STOPS` value has a table row; `SKILL.md` names `autopilot
  enter` as the first Bash call; the pinned `awk` line's literal text
  matches the regex embedded in `_review_log_has_dispatch_line`.
- CLI-level: `test_cli_prints_one_json_line_with_every_key`,
  `test_cli_unreadable_state_exits_two` (a genuinely corrupt file, not a
  missing one - the missing case is now the bootstrap test above),
  `test_cli_future_schema_exits_six`, plus every existing `test_cli*.py`/
  `test_resume*.py`/`test_selection.py`/`test_lifecycle_cli.py`/
  `test_autopilot_lifecycle.py` stays green (the lifted `select_eligible`/
  `frontmatter.apply` must not change `_run_select`'s/`_run_frontmatter`'s
  observable behavior).

## Review log

dispatch 1 (claude): cardinal-sin 0, blocker 8, non-blocker 3, question 1
dispatch 2 (codex): cardinal-sin 0, blocker 7, non-blocker 1, question 0

Both dispatches independently found the `designs_dir` off-by-one
(`parents[1]` instead of `.parent`) and the stale `dev/local/` vs. live
`docs/dev/project-management/` path convention (the design was first written
against the installed plugin cache, not this repo's own checked-out source -
corrected throughout this revision, with the discrepancy called out in
`## Architecture fit` so a future reader doesn't repeat it).

Cardinal sins/blockers fixed in this revision:
- `designs_dir` computed from the wrong parent (both dispatches).
- Every literal path updated from the cache's `dev/local/` convention to
  this repo's live `docs/dev/project-management/` + `docs/dev/tmp`
  convention, including `repo_root`, which now reuses
  `custody.project_root` instead of a hand-rolled `parents[2]` (both
  dispatches flagged the hand-rolled arithmetic; codex additionally named
  the exact wrong resolved paths).
- Fresh-start bootstrap: step 0 now calls `state.init` when `state.json` is
  absent, instead of letting `do_park`'s exit 2 (indistinguishable from a
  corrupt file) stand in for "nothing to park yet" (codex).
- `do_park`'s stdout leak into `enter()`'s single-JSON-line contract, fixed
  with `contextlib.redirect_stdout` (codex).
- `do_park` exit 2's two meanings (unreadable state vs. malformed
  `stall_op`) disambiguated by a step-3 precheck using
  `records._stall_op_malformed` directly (claude, codex).
- The `--prd`-not-found case now stops with a new `prd_not_found` token
  instead of reusing `mv_verify`, which would have triggered the skill's
  move-retry/PAUSE recovery for a case where nothing was ever being moved
  (claude flagged the ambiguity; codex named the wrong-recovery-action
  consequence).
- `batch` schema gained `|null` for the three earlier steps that can stop
  before it is ever evaluated (claude).
- The handoff row now writes before the lane check, not after, so a solo/
  fast-track PRD still gets its resume row (codex).
- Eligibility skips are now recorded unconditionally (step 0's bootstrap
  means `state_path` always exists inside `enter()`), removing the "lost on
  a fresh batch" gap the original per-call guard left open (codex).
- Steps 1-2 wrapped in `try/except OSError` -> `stop="fs_error"`, instead of
  an uncaught traceback (claude, codex).
- `resume_target`'s null-scope corrected from "the 3 step-4/5 stalls" to
  "every stop at or before step 5, including the 4 step-4 park-family
  stops," with the test list widened to match (claude).

Non-blockers logged, not fixed (do not block planning): the bare-repo
`catchup="full"` regression has no measured frequency/cost bound (codex) -
tracked in Risks as a next-PRD candidate; the `--prd`-arg branch of step 8
is new glue code with no existing function to point to, now flagged
explicitly in Reuse inventory rather than left implicit (claude); a
concurrent state.json corruption in the narrow window between step 3's load
and step 4's `do_park` call fails through the same exit-2 path step 3 uses,
accepted as the same single-writer-process race every other multi-step verb
here already accepts (claude, elevated from question to non-blocker after
review since it is a real, if narrow, window).

dispatch 3 (codex): cardinal-sin 0, blocker 2, non-blocker 0, question 0 (5
of the original 7 blockers verified CLOSED, 2 PARTIALLY CLOSED, 1 STILL
OPEN, plus 2 new blockers)

A duplicate dispatch-3-shaped Claude fallback was launched in parallel by
mistake (codex had briefly hit a transient websocket 503 mid-run, which read
as an outage until its process was confirmed still alive and later finished
normally) - its findings substantially overlapped codex's and are folded in
below rather than counted as a 4th dispatch against the 3-dispatch ceiling;
it additionally caught one concrete bug codex's pass did not (the
`record_dispatch.py` path resolution), fixed below on its merits regardless
of dispatch bookkeeping.

Dispatch-3 findings and fixes:
- **STILL OPEN, now fixed**: `do_park` exit 2 is not fully disambiguated by
  the step-3 precheck alone - `do_stall`'s own internal preflight (reached
  only through `do_park`'s marker/stall_op reconciliation path) can also
  exit 2 for a missing `batch.id` or a failed `cap_critical` capture, causes
  step 3 cannot see. Given a new, honest token, `park_precondition_failed`,
  rather than asserting it definitively means "unreadable state."
- **PARTIALLY CLOSED, now fixed**: the fresh-start bootstrap ran before
  `mkdir` in the prior revision; `state.init` needs its parent directory to
  already exist. Reordered: mkdir first, bootstrap second. Also documented,
  as a pre-existing and out-of-scope limitation shared by every verb, that
  `--state`'s default resolution still needs some ancestor
  `docs/dev/project-management/autopilot` directory to exist before
  `enter()` is even reached.
- **PARTIALLY CLOSED, now fixed**: the `stall_op_malformed` precheck had no
  presence guard - `records._stall_op_malformed(None)` returns `True` in the
  live implementation, so an ordinary state with no `stall_op` at all would
  have stopped. Added `stall_op is not None and ...`.
- **New blocker, fixed**: `batch_init` was declared in `STOPS` and named in
  the Test strategy outline, but the step chain itself never reached it -
  select flowed straight into frontmatter. Reinserted as its own step, and
  widened its "absent" check to catch a batch dict select's skip-write may
  have partially created (missing `id`, not merely a missing `batch` key).
- **New blocker, fixed**: the default `record_resume_row`'s path was written
  as `work/scripts/record_dispatch.py` with an implied `${CLAUDE_PLUGIN_ROOT}`
  prefix borrowed from SKILL.md/Bash prose - but that placeholder resolves
  only in SKILL.md bodies and `hooks.json`, never inside a Python script
  (`rules/claude-tooling.md`), and no existing `cli/*.py` file shells out to
  `record_dispatch.py` today, so there was no established pattern to copy.
  Replaced with a `Path(__file__).resolve().parents[2]`-relative resolution
  and a test asserting the resolved path exists in the real tree - this is
  the same "wrong parent" defect class the earlier dispatches already caught
  twice elsewhere in this document.
- **Non-blocker, logged**: `contextlib.redirect_stdout` swaps only Python's
  `sys.stdout`, not fd 1 - a subprocess `notify_out.notify` spawns during a
  rare `cap_critical`-reconciliation path inside `do_park` inherits the real
  fd and could still print past the redirect. Narrow (requires a pending
  `cap_critical` stall reconciled at exactly that moment) and not worth an
  `os.dup2` fd-level redirect pre-emptively; documented in Risks with the
  signal (a corrupted `dispatch-metrics.jsonl`-adjacent batch report) that
  would justify revisiting it.
- **Question, addressed with one clarifying sentence**: `mv_verify` is
  deliberately the same token for both `do_park`'s hold-move failure (before
  `resume_target` is computed) and select's backlog-move failure (after) -
  confirmed intentional against `SKILL.md`'s own single PAUSE/retry-once
  framing for every lifecycle move; now stated explicitly in Risks so a
  future reader isn't left to infer it.

No cardinal sin was found at any dispatch. No blocker or cardinal sin remains
open after this revision.

result: ok
