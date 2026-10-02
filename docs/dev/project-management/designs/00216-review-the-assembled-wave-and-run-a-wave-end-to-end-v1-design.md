# Design: Review the assembled wave and run a wave end to end

## Architecture fit

This lands in `skills/run-autopilot/cli/`, the same package as 00214's
`wave.py`/`wave_launch.py` and 00215's `wave_assemble.py`. The pack's existing
layering for the `autopilot wave` verb group is: a pure-data module
(`wave.py`: plan, load, validate), a side-effecting module per lifecycle step
(`wave_launch.py`: launch/status/abort; `wave_assemble.py`: assemble), and a
thin CLI dispatcher (`wave_cli.py`) that argparse-registers each verb and
calls straight through with no logic of its own. This PRD adds the next two
lifecycle steps (review, land) as one more side-effecting module,
`wave_review.py`, plus the orchestrator (`wave_run.py`) that chains every verb
already built (plan/launch/assemble, from 00214/00215) with the two new ones.
It does not touch `wave.py`'s schema beyond reading the `assembly` block
00215 already writes.

Every existing wave module hardcodes the managed repo's project-management
path as the literal `docs/dev/project-management/...` (confirmed:
`wave.py:257`, `wave_assemble.py:36-38`, `wave_launch.py:128,166-190`) rather
than importing a shared constant module - each file repeats the literal.
`wave_review.py` follows the same established convention (own literals, not
a new shared-constants module) rather than introducing a refactor this PRD
was not asked for.

**Corrected during review (codex dispatch 2 caught the original claim as
false): `docs/dev/project-management/` is GITIGNORED in every repo
`autopilot wave` manages, not tracked.** The wave test fixtures' own seeded
repo proves it: `test_wave_launch.py:71` writes
`(repo / ".gitignore").write_text("docs/dev/project-management/\n")` before
the first commit - the already-shipped 00214/00215 code is built and tested
against a gitignored tree, the same shape this source repo's own `dev/local/`
override uses (`.gitignore:6`), just under a different directory name. There
is no tracked-vs-gitignored split between "this repo" and "managed repos" -
it is gitignored everywhere, by design (PRD state is local working state,
not source). (This appears to sit in tension with this operator's own
global `rules/working-documents.md` "never gitignore this tree" rule, but
that rule governs how they organize their OWN repos' project-management
tree; it says nothing about what convention the shipped `autopilot wave` CLI
code assumes for whatever repo it is pointed at, and reconciling the two is
a separate decision outside this PRD's scope.)

Two consequences of this correction, both resolving findings that were
based on the original false "tracked" claim rather than real defects:
- A fresh `git worktree add` at any commit - a lane worktree OR the assembly
  worktree - starts with NO pre-existing PRD/state content under
  `docs/dev/project-management/`, because gitignored content is never part
  of any commit. `_seed_lane_worktree`'s mkdir-fresh-and-copy-meta pattern
  (wave_launch.py:165-177) is not special-casing a lane; it is the ONLY way
  a fresh worktree ever gets that content, and `seed_state` doing the same
  for the assembly worktree is the identical case, not a novel one.
  Concretely: the assembly worktree only ever contains the ONE stub PRD
  `seed_state` writes - never a kept lane's PRDs, never a held-back PRD -
  since none of that content ever reaches any git branch to merge in the
  first place. A codex finding worried the nested loop could drift into
  other backlog PRDs after finishing the stub (treating an
  `assembled_partial` wave's kept-lane PRDs as if they'd be present); they
  cannot be, for the reason above - `select` finds exactly the stub and
  nothing else, so the loop drains after it, matching `review()`'s own
  "converged"/"review_failed" outcome contract with no third case.
- The dirty-tree refusals `wave_launch.launch`/`wave_assemble.assemble`
  already run (`wave_launch.py:141-147`, `wave_assemble.py:273-276`) check
  `git status --porcelain`, which never reports a gitignored path as dirty
  regardless of how many PRD/state files get written under it. `review()`'s
  own clean-tree precondition (below) is checking the SAME thing for the
  same reason and is equally unaffected - a codex finding that treated this
  as newly broken was reasoning from the false "tracked" premise.

`test_wave_review.py` runs, like every existing wave test, against a
disposable `tmp_path` git repo seeded with that same gitignore line, never
this checkout's own PRD folders.

## Module placement

New files:
- `skills/run-autopilot/cli/wave_review.py` - `stub_text`, `review_paths`,
  `seed_state`, `review`, `land`.
- `skills/run-autopilot/cli/wave_run.py` - `run`.
- `skills/run-autopilot/cli/test_wave_review.py` - all five functions above.
- `skills/review-work-completion/scripts/test_gather_context_paths.sh` - the
  new marker-file filter.

Edits to existing files:
- `skills/run-autopilot/cli/wave.py` - append `"converged"` and
  `"review_failed"` to `WAVE_STATUSES` (wave.py:28-38). These are wave-level
  outcome statuses `review()`/`land()` write, parallel to how 00215 already
  added `assembled`/`assembled_partial`/`conflict`/`checks_failed` for its
  own outcomes - without this, `_TOP_CHECKS`'s status validation
  (`_structural_errors`, used by every verb's own refusal check) rejects a
  reviewed wave.json as structurally invalid.
- `skills/run-autopilot/cli/wave_cli.py` - register `review`, `land`, `run`
  verbs on the SAME `verbs` subparsers object the existing five verbs use
  (`verbs.add_parser("review")` etc, `wave_cli.py:20-26`) - not a fresh
  `subparsers.add_parser` call, which would register them as top-level
  siblings of `wave` instead of `wave` sub-verbs (caught in review: an
  earlier draft of this section made exactly that mistake).
- `skills/review-work-completion/scripts/gather-context.sh` - read
  `docs/dev/project-management/autopilot/review-paths` (in
  `$PROJECT_ROOT`, the repo `gather-context.sh` is invoked against) and
  narrow both `git diff` calls when it exists and is non-empty. **Corrects
  the PRD's own literal wording** ("`$PROJECT_ROOT/dev/local/autopilot/review-paths`"):
  `gather-context.sh` already hardcodes `docs/dev/...` for its own `TMP_DIR`
  (`gather-context.sh:38`), and every wave module hardcodes
  `docs/dev/project-management/autopilot/...` for this exact directory
  (`wave_assemble.py:36`, `wave_launch.py:187,190`) - see `## Architecture
  fit`'s correction above (gitignored everywhere, not "tracked elsewhere,
  gitignored only here"). Using the PRD's literal would write a marker file
  no shipped code reads.
- `skills/run-autopilot/references/waves.md` - `## Review and land` and
  `## wave run` sections (exit codes, interrupted-resume, the alias line, the
  `review-paths` scope note), replacing the "Deferred: assembly and review
  slots" bullet that names review as not-yet-shipped.
- `skills/run-autopilot/references/state-schema.md` - add a `review-paths`
  row to `## Marker files` in the table's real four-column style (`Marker |
  Writer | Consumer | Content`, `state-schema.md:244-245` - an earlier draft
  of this section miscounted it as five), **and** correct the existing stale
  `wave.json` row (still lists only the pre-00215 status enum and lane
  fields, no `assembly` block, no
  `assembled`/`assembled_partial`/`conflict`/`checks_failed`/`converged`/`review_failed`
  - drift flagged during research for this PRD, fixed in the same edit since
  both rows are touched together).
- `skills/run-autopilot/SKILL.md` - add `review-paths` to § Retention's
  disposable list (removed with the assembly worktree, same lifecycle as
  `wave.json`/`wave-slots/`).
- `dev/bin/release-checks` - append `test_wave_review.py` to the existing
  `[checks] waves` pytest block (line list at `release-checks:107-119`); add
  a new two-line `[checks] <name>` + `bash .../test_gather_context_paths.sh`
  block following the existing shell-test pattern (e.g. `release-checks:51-55`).
- `CHANGELOG.md` - one `### Added` entry under `**run-autopilot**`.

## Interfaces & contracts

All new functions live in `skills/run-autopilot/cli/wave_review.py` unless
noted. Dependency injection follows the pack's existing idiom throughout
(`wave_assemble.py`'s `run_git`/`run_checks` keyword-only defaults): every
side-effecting function takes its subprocess/CLI seam as a keyword-only
parameter defaulting to a real implementation, so tests inject a fake and
production calls need no argument.

```python
def stub_text(wave: dict) -> str:
    """Pure. Renders the assembly stub PRD body from `wave["assembly"]` and
    `wave["lanes"]`. Frontmatter block:
        catchup: skip
        design: skip
        rework_cap: 2
        default_model: sonnet
        model_tier_rationale: fixes to conflict resolutions and lane interactions found by the assembly review
    Body sections, in order:
      # Wave <wave["id"]> assembly
      ## Overview
        - one line per merged lane: "- <lane name> (<lane prds, comma-joined>)"
        - "Diff range: <wave['base_sha']>..<wave['assembly']['head_sha']>"
        - "Diff scope:" followed by one `review_paths(wave)` entry per line
      ## Functional Decomposition
        ### Capability: Assembly
        #### Feature: Lane merges
        - Description / Inputs / Outputs / Behavior naming each merged lane
          (wave["assembly"]["merged"]) and its keep-both resolutions, read
          from that lane's `integrator_notes` list (wave.py's optional
          per-lane field; empty list -> "no keep-both resolutions recorded")
      ## Implementation Phases
        ### Phase 0: Assembly
        - "- [x] Merge lane <name> (<prds>) - Acceptance: release-checks green"
          one per entry in wave["assembly"]["merged"]
      ## Test Strategy
        - "bash dev/bin/release-checks"
        - one line per merged lane naming its PRDs by basename, e.g.
          "- See <prd basename>'s own Test Strategy" - NOT the extracted
          Success Metrics command text itself: `stub_text` takes only `wave`
          and stays pure per the PRD's own `stub_text(wave) -> str` (pure)
          export contract, and `wave["lanes"][*]["prds"]` already names every
          PRD by basename with no file read needed. A reviewer or planner
          wanting the actual commands opens the named PRD in `prds/done/`.
    Raises ValueError if wave["assembly"] is absent (review_paths and
    stub_text are only ever called after assemble()).
    """

def review_paths(wave: dict) -> list[str]:
    """Pure. Returns the sorted, de-duplicated union of:
      - `wave.WAVE_APPEND_ONLY` (`("CHANGELOG.md", "dev/bin/release-checks")`,
        already defined in `wave.py:21`, reused not redefined) - always
        included, unconditionally, regardless of how many lanes name them;
        every PRD touches them by convention, so they are always a shared
        surface, never a signal to look for.
      - every repo-relative path that appears in the `files` list of two or
        more entries in `wave["lanes"]` - **every** lane, not only the merged
        ones ("a kept lane's files count too", the PRD's own acceptance
        wording: a lane `assemble` could not merge still touched the same
        file another lane landed, which is exactly the interaction surface
        the review exists to catch). A lane missing `files` counts as an
        empty list.
    """

def seed_state(
    state_path: Path,
    wave: dict,
    plugins_json: Path,
    *,
    run_cli: Callable[[list[str]], subprocess.CompletedProcess] = _default_run_cli,
) -> None:
    """`state_path` names the target `state.json` directly, matching the
    PRD's own Exports line verbatim (an earlier draft renamed this parameter
    to `assembly_root`, contradicting the PRD's authoritative signature -
    caught in review). `assembly_root = state_path.parents[4]` - the same
    derivation `__main__.py`'s `_run_wave`/`_resolve_state_path` already uses
    to recover a repo root from a `--state` path (`state_path` sits at
    `<assembly_root>/docs/dev/project-management/autopilot/state.json`, four
    path segments below `assembly_root`).

    Ensures the assembly worktree's docs/dev/project-management lifecycle
    dirs exist (mkdir(parents=True, exist_ok=True) for
    prds/{backlog,wip,done,hold} and autopilot/, mirroring
    wave_launch.py:165-177's `_seed_lane_worktree`). Because that whole tree
    is gitignored (`## Architecture fit`), a freshly-created assembly
    worktree has NOTHING there yet - these dirs are created empty, not
    populated from any pre-existing content. Copies the managed repo's own
    `docs/dev/project-management/meta/` from the main checkout (same
    `shutil.copytree(..., dirs_exist_ok=True)` idiom `_seed_lane_worktree`
    already uses). Writes the stub to
    <assembly_root>/docs/dev/project-management/prds/wip/<wave["id"]>-wave-assembly-v1.md
    - the ONLY PRD that will ever be in that worktree (see `## Architecture
    fit`).

    Reads `plugins_json` and extracts EXACTLY the two enforcement-plugin
    version strings Phase 0 step 3 of `run-autopilot`'s own `SKILL.md`
    already pins:
    `{"aegis@buvis-plugins": data["plugins"]["aegis@buvis-plugins"][0]["version"],
    "warden@buvis-plugins": data["plugins"]["warden@buvis-plugins"][0]["version"]}`
    - NOT the whole parsed file (an earlier draft assigned
    `json.loads(plugins_json.read_text())` wholesale to `batch.plugin_versions`,
    which is a different, much larger shape than the two-key mapping the
    loop's own plugin-drift preflight expects, and would report false drift
    on every relaunch - caught in review).

    Then drives the seed through `run_cli` in this exact order (one
    subprocess.CompletedProcess per call, all via run_cli so a test captures
    every argv):
      1. ["python3", <__main__.py>, "init", "--state", str(state_path), "--prd", <stub basename>]
      2. ["python3", <statectl.py>, str(state_path), "set", "work_start_sha", json.dumps(wave["base_sha"])]
      3. ["python3", <statectl.py>, str(state_path), "set", "cycle", "1"]
      4. ["python3", <statectl.py>, str(state_path), "set", "rework_cap", "2"]
      5. ["python3", <statectl.py>, str(state_path), "set", "batch", json.dumps({
             "id": wave["id"], "mode": "autopilot", "completed_prds": [],
             "plugin_versions": {"aegis@buvis-plugins": ..., "warden@buvis-plugins": ...},
         })]
      6. ["python3", <__main__.py>, "phase-done", "--state", str(state_path), "--outcome", "tasks_done"]
    Step 1 is skip-if-present, not unconditional: `init` returns 7 when
    `state_path` already exists (`__main__.py:263-276`), so a caller retrying
    `review()` after a crash mid-seed (e.g. a killed process between steps 2
    and 6) would otherwise fail this step outright, unable to resume - a
    real gap in an earlier draft's "no partial state is a caller concern"
    claim, caught in review. `seed_state` checks `state_path.exists()` first
    and skips straight to step 2 when true, so a retry continues the
    unfinished statectl/phase-done sequence rather than refusing at init.
    Raises RuntimeError naming the failing argv and stderr on any other
    non-zero exit.
    """

def review(
    repo: Path,
    wave: dict,
    *,
    spawn_fn: Callable[..., subprocess.Popen] = subprocess.Popen,
    run_git: Callable[..., subprocess.CompletedProcess] = _default_run_git,
) -> str:
    """Positional signature matches the PRD's Exports line exactly -
    `(repo, wave, *, spawn_fn)` - so `wave` (the caller's already-loaded
    dict, e.g. right
    after `wave_assemble.assemble()` in `wave_run.run`) is what the caller
    hands in and what drives the FIRST precondition check below. Internally
    derives `wave_path = repo / "docs/dev/project-management/autopilot/wave.json"`
    (the one fixed location every wave module assumes, same derivation
    `wave_run.run` uses) for every lock/reload/save this function needs -
    `review` is long-running (it blocks on an entire nested review-rework
    loop) and must not hold `wave.json`'s lock for that whole span, unlike
    `assemble()`, which holds the lock for its whole body because that body
    is short (`wave_assemble.py:567`, "The lock is held for the whole
    body"). Review's own locking discipline (caught in review - an earlier
    draft mutated the passed-in `wave` dict across the whole function with
    no locking at all, which risks a lost update against a concurrent
    write). `run_git` is kept as a public keyword-only param beyond the
    PRD's terse `(repo, wave, *, spawn_fn)` exports line (flagged in review
    as a signature drift; a defensible one, not reverted): `land`'s own
    exports line explicitly lists `run_git`, and every existing side-effecting
    wave module (`wave_assemble.assemble(repo, wave_path, *, run_git=...,
    run_checks=...)`) already carries DI seams beyond a one-line summary -
    the PRD's terse notation is inconsistent about naming every kwarg, not a
    deliberate signal that `review()` alone should hide its git seam:

      1. NO LOCK NEEDED YET - nothing here touches `wave.json` itself.
         Check preconditions against the passed-in `wave` (raise ValueError,
         no side effect, on any failure): wave["status"] in ("assembled",
         "assembled_partial"); the assembly worktree
         (wave["assembly"]["worktree"]) exists on disk; `repo`'s tree is
         clean (`run_git(["status", "--porcelain"], cwd=repo)` empty stdout -
         gitignored `docs/dev/project-management/` never shows here
         regardless of what `seed_state` writes under it, `## Architecture
         fit`). Write
         <assembly_worktree>/docs/dev/project-management/autopilot/review-paths
         (one `review_paths(wave)` entry per line, newline-terminated,
         sorted; empty file, not omitted, when review_paths(wave) is empty)
         and call seed_state(<assembly_worktree>/docs/dev/project-management/autopilot/state.json,
         wave, plugins_json) - `plugins_json = Path.home() /
         ".claude/plugins/installed_plugins.json"` as review()'s own literal
         (matching every other wave module's own-literal convention, and the
         PRD's own Inputs line naming that exact path). These are all writes
         INSIDE the assembly worktree, never to the main `wave.json` - the
         caller's own load of `wave` (moments earlier, in `wave_run.run` or
         `wave_cli.run`'s `review` verb) is trustworthy for this step. This
         is the one wave-mutating verb that skips the pack's usual
         "reload fresh under lock before any read" discipline for its FIRST
         read (flagged in dispatch-3 verification as a minor inconsistency,
         not fixed): the only concurrent action that could invalidate a
         stale `wave` here is `wave abort`, and abort never touches the
         assembly worktree or its lane record, so a staleness window here
         has no real scenario that bites - accepted rather than added
         lock/reload overhead around a check with nothing to protect
         against yet.
      2. STILL no lock: spawn the loop with the SAME recipe
         `wave_launch.py`'s `_spawn_lane` already uses for a lane
         (`_SPAWN_CMD = 'export _AUTOPILOT_LOOP=$$; exec python3 "$0" loop'`,
         argv `["bash", "-c", _SPAWN_CMD, str(CLI_MAIN_PATH)]`,
         `cwd=str(assembly_worktree)`, `start_new_session=True`, logging to
         `<assembly_worktree>/docs/dev/project-management/autopilot/wrapper.log`)
         - no `caffeinate` (that only wraps the outer one-shot `autoclaude
         wave` alias, a different layer) - but with the `env` built WITHOUT
         `_AUTOPILOT_REVIEW_SLOTS_DIR`/`_AUTOPILOT_REVIEW_SLOTS` (assembly
         review is a single session, not a lane contending for the
         semaphore) via `spawn_fn`, then blocks on it (`Popen.wait()`) -
         unlike launch (which spawns and returns immediately for N lanes to
         run in parallel), review is a single blocking step inside
         `review()`'s own caller chain (`wave_run.run` or the operator
         running `wave review` directly waits for exactly one loop). No lock
         is held while this runs - a concurrent `wave status` still works
         during the whole review-rework cycle.
      3. `with locked(wave_path): wave = load(wave_path)` - the ONE point in
         `review()` that touches `wave.json`'s own lock: reload fresh rather
         than trusting the caller's original copy (safe against anything
         that changed meanwhile - e.g. a hand-edit, or a future concurrent
         verb). Determine the outcome by
         inspecting the assembly worktree's PRD folders (unchanged from the
         earlier design): "converged" - the stub is in `prds/done/`;
         "review_failed" - the stub is in `prds/hold/`, OR the loop process
         exited with the stub still in `prds/wip/` (a died-and-parked-nothing
         bootstrap failure, or a genuine crash). Set `wave["status"] =
         outcome` (that exact string - "converged" or "review_failed", the
         two values `land()`'s own precondition now checks for, matching the
         PRD's land Behavior text "status review_failed" - an earlier draft
         had `land()` still checking `("assembled", "assembled_partial")`,
         an internally-impossible state machine caught in review), save,
         release the lock, and return `outcome`.
    """

def land(
    repo: Path,
    wave: dict,
    *,
    run_git: Callable[..., subprocess.CompletedProcess] = _default_run_git,
) -> int:
    """Signature matches the PRD's Exports line exactly - `(repo, wave, *,
    run_git)`. Internally derives `wave_path = repo /
    "docs/dev/project-management/autopilot/wave.json"` (the fixed location,
    same derivation `review()`/`wave_run.run` use) and immediately
    RE-LOADS under lock rather than trusting the passed-in `wave` -
    `with locked(wave_path): wave = load(wave_path)` - holding the lock for
    the whole body exactly like `assemble()` does (`wave_assemble.py:567`):
    unlike `review()`, `land`'s own work (a fast-forward, an artifact
    migration, some file moves) is bounded and short, so the same
    whole-body-locked convention every other mutating verb uses applies here
    unchanged (caught in review - an earlier draft locked nothing at all).
    The passed-in `wave` parameter is never read past this reload - it exists
    only so the signature matches the PRD and a caller that already has a
    dict in hand (e.g. `wave_run.run` right after `review()` returns) can
    call this the same way it calls `review()`.

    Precondition: `wave["status"] not in ("converged", "review_failed")` ->
    raise ValueError. These are the two values `review()` itself writes
    (`## Interfaces & contracts`'s `review()` entry) - an earlier draft
    checked `("assembled", "assembled_partial")` here, which `review()`
    always overwrites before `land()` can ever run, making the
    `review_failed` branch below unreachable and the whole precondition
    internally impossible (a state-machine contradiction caught in review).
    "Land is its own verb so an operator who reviewed by hand can still
    land" (the PRD's own words) means an operator may have hand-set
    `wave["status"]` to one of these two values too; `land` only reads it,
    never re-derives convergence itself.

    On `wave["status"] == "review_failed"`: no git write, worktree/branch
    kept, appends "## Assembly review: review_failed, see <review file
    path>" to the wave summary (path read from the stub's own
    `docs/dev/project-management/reviews/<stub-stem>-review-<n>.md` inside
    the assembly worktree, or "no review file written" if none exists - e.g.
    a died-bootstrap outcome), saves, releases the lock. Returns 4.

    On `wave["status"] == "converged"`, resumable end to end (a retry after
    ANY failure below - a killed process, a raised exception - re-enters
    here and safely continues; caught in review as a cardinal sin when
    absent: the original draft fast-forwarded first, then archived, with no
    way back if a later step failed and HEAD had already moved past
    `base_sha`). Every step is either a no-op if already done, or moved to
    the very end if destructive:
      1. Resolve the assembly branch's CURRENT tip fresh -
         `run_git(["rev-parse", f"wave/{wave['id']}/assembly"], cwd=repo).stdout.strip()`
         - never trust the `wave["assembly"]["head_sha"]` `assemble()`
         recorded; the review-rework loop may have committed fix-up work on
         that branch since, and landing an implicit newer tip is correct as
         long as the field naming it is refreshed to match (a non-blocker
         caught in review: an earlier draft archived the stale recorded
         value even though the landed SHA could differ).
      2. Read the CURRENT `run_git(["rev-parse", "HEAD"],
         cwd=repo).stdout.strip()`. Refuse (return 5, no write) unless it
         equals EITHER `wave["base_sha"]` (the normal case) OR the resolved
         assembly tip from step 1 (a retry landing on a checkout the merge
         already fast-forwarded - the merge in step 3 is then a no-op, and
         the retry proceeds to finish migration/cleanup instead of refusing
         a wave it already half-landed).
      3. If HEAD is still at `base_sha`: `run_git(["merge", "--ff-only",
         f"wave/{wave['id']}/assembly"], cwd=repo)`. Skipped (already a
         no-op) if HEAD already equals the assembly tip from step 1.
      4. `wave["assembly"]["name"] = "assembly"; wave["assembly"]["status"] =
         "assembled"; wave_assemble.migrate_lane(repo, wave["id"],
         wave["assembly"])` - reusing 00215's migration verbatim
         (wave_assemble.py:399-421), passing `wave["assembly"]` ITSELF as the
         lane dict rather than a fresh literal (caught in review, dispatch 3
         verification: `migrate_lane` guards its jsonl append with
         `lane.get("migrated_at")` and sets `lane["migrated_at"]` on the SAME
         dict object it was given - for a real lane that object is
         `wave["lanes"][i]`, which `assemble()`'s own loop saves back to
         `wave.json` right after, so the flag survives a reload; a fresh
         `{"name": ..., "status": ...}` literal built new on every call, as
         an earlier draft did, has nowhere to persist that flag, so a retry
         after any crash past this point would re-append every ledger jsonl
         line a second time - the "safe no-op" claim was false against
         `migrate_lane`'s real mechanics). Passing `wave["assembly"]` directly
         means `migrate_lane`'s own `lane["migrated_at"] = ...` mutation
         lands on the exact sub-dict step 5 below saves back to `wave.json`,
         so a retry's `wave["assembly"].get("migrated_at")` already being set
         is what makes the jsonl-append guard hold for real. Since the
         assembly worktree only ever holds the ONE stub
         PRD (`## Architecture fit` - gitignored, nothing else ever reaches
         it), this call's own `_route_prds(main, worktree, merged=True)`
         (wave_assemble.py:386-396) moves ONLY the stub from the assembly
         worktree's `prds/done/` to the main checkout's `prds/done/` -
         `merged=True` is exactly what makes `_route_prds` NOT skip the
         `done/` folder. Verify the stub's arrival in the main checkout's
         `prds/done/` (the verified-move invariant, checked the same way
         every other lifecycle move is); on failure, save `wave.json` as-is
         (still `status: "converged"`, so a retry re-enters this whole
         function) and raise rather than proceed to the destructive steps.
      5. Append "## Assembly review: converged (<cycle> cycle(s)), landed
         <sha>" to the wave's summary (`<cycle>` from the stub's own
         `state.json` `cycle` field; `<sha>` = step 1's resolved tip). Save
         `wave["status"] = "done"` and `wave["assembly"]["head_sha"]` =
         step 1's resolved tip - this save happens BEFORE the destructive
         steps below, so a crash between here and step 6 leaves a wave.json
         that already reads "done" and a retry's own idempotent re-checks
         (steps 2-4) find nothing left to do.
      6. ONLY NOW, once every non-destructive step above is verified
         complete: `git worktree remove --force` + `git branch -D` the
         assembly worktree/branch, remove `wave-slots/`, move `wave.json` to
         `reports/<wave id>-wave.json` (mirrors `phase-done`'s batch-end
         archive convention, not a new idiom). Release the lock. Returns 0.
    """
```

`skills/run-autopilot/cli/wave_run.py`:

```python
def run(
    repo: Path,
    *,
    max_lanes: int = 3,
    review_slots: int = 3,
    yes: bool = False,
    sleep_fn: Callable[[float], None] = time.sleep,
    clock: Callable[[], float] = time.monotonic,
) -> int:
    """`wave_path = repo / "docs/dev/project-management/autopilot/wave.json"`
    (the one fixed location every wave module already assumes - `wave.py`'s
    own module docstring, wave_cli.py's dispatch - not a new convention).

    Chains, in order: a TTY confirmation gate FIRST (`sys.stdin.isatty()`;
    not a tty and not yes -> print "pass --yes", return 1, before any write -
    matches the PRD's own "without a TTY and without --yes exit 1 ... before
    planning"); `wave.plan(repo, wave_path, max_lanes)` (the real signature,
    `wave.py:246`; prints the plan table via wave.py's own existing print
    helper). When `review_slots != 3` (plan's own hardcoded default,
    `wave.py:270-283` - `plan()` itself takes no `review_slots` argument):
    `w = wave.load(wave_path); w["review_slots"] = review_slots;
    wave.save(wave_path, w)` - using the hand-edit surface
    `references/waves.md` already documents ("wave.json is a supported
    hand-edit surface between plan and launch"), so `wave.py`/`wave_launch.py`
    need no signature change for this flag. Then `wave_launch.launch(repo,
    wave_path)`; a poll loop that reloads `wave.load(wave_path)` and calls
    `wave_launch.status(repo, loaded)` every 30s via sleep_fn (the real
    `status(repo, wave: dict)` signature takes an already-loaded dict, not a
    path - `wave_cli.py`'s own `status` verb dispatch loads it first the same
    way), printing the status table every 10 minutes of elapsed wall time
    (clock() deltas, not a call counter, so an injected fake clock drives the
    print cadence in tests) until every lane pid reads dead;
    `wave_assemble.assemble(repo, wave_path)` (the real signature takes
    `wave_path`, not a loaded dict); THEN `wave = wave.load(wave_path)` -
    assemble() saved the `assembly` block and new `status` to disk, so `run`
    reloads before handing a dict to the two functions that need one (both
    match the PRD's own Exports signatures, `(repo, wave, ...)` - see `##
    Interfaces & contracts` for how each internally re-derives `wave_path`
    and reloads under lock rather than trusting this copy for anything but
    its own first precondition check): `outcome = wave_review.review(repo,
    wave, ...)` - `review()` itself persists `wave["status"] = outcome`
    under its own lock/reload/save cycle before returning, so `run` does
    NOT also save here (an earlier draft double-saved outside any lock,
    caught in review alongside the locking-contract finding). If `outcome
    == "converged"`: `wave = wave.load(wave_path)` (reload once more -
    `review()`'s own save already changed the file) then
    `wave_review.land(repo, wave, ...)`.
    Exit codes: 0 landed; 1 a precondition refused (plan/launch's own exit-1
    refusals surface here unchanged, and the non-tty-without-yes gate);
    3 assemble returned 3 (a lane was kept) AND the rest of the chain still
    ran to completion on what did merge (assembled_partial still reviews
    and lands, per the PRD's "the run still reviews and lands what merged");
    4 review returned "review_failed"; 5 land returned 5 (master moved
    between the confirmation gate and land - the one refusal `run` cannot
    prevent by construction, since planning happens before the wave's own
    long launch/wait/assemble/review span). **Combination rule** (a question
    raised in review: what happens when more than one step's own code is
    non-zero, e.g. assemble returns 3 and land later returns 5 on the same
    run): the final code is the LAST non-zero code produced, in execution
    order - each code describes the wave's CURRENT terminal state, not an
    aggregate severity, so land's 5 (nothing landed) correctly overrides
    assemble's earlier 3 (some lanes still merged fine) once land refuses.
    `test_run_exit_code_follows_the_weakest_step` gains a second case pinning
    this: assemble=3, review converges, land=5 (master moved) -> final 5.
    SIGINT/SIGTERM: a signal handler installed for the duration of the wait
    loop forwards SIGTERM to every live lane's process group (same signal
    path as `wave abort`'s step 1, reused rather than re-implemented -
    `wave_launch`'s per-lane SIGTERM-then-SIGKILL escalation is called
    directly, not `wave abort` the verb, since abort also does PRD hand-back
    which an interrupted-not-aborted wave should not do), writes
    wave["status"] = "interrupted", saves, and calls sys.exit(130). A
    subsequent `autopilot wave assemble` on the same wave.json resumes from
    there exactly as any other assemble invocation (assemble's own
    already-drained-lane detection needs no new code).
    """
```

`wave_cli.py` additions, inside the same `add(subparsers)` function, on the
SAME `verbs` object the existing five verbs register on (`wave_cli.py:18-26`
- `p = subparsers.add_parser("wave")`, `verbs = p.add_subparsers(dest="verb",
required=True)`; `review`/`land`/`run` are sub-verbs of `wave`, not new
top-level commands, so they register on `verbs`, never on the outer
`subparsers` again):

```python
verbs.add_parser("review")   # --state only
verbs.add_parser("land")     # --state only
run_p = verbs.add_parser("run")
run_p.add_argument("--max-lanes", type=int, default=3)
run_p.add_argument("--review-slots", type=int, default=3)
run_p.add_argument("--yes", action="store_true")
```

`gather-context.sh` addition (own script, not `wave_review.py`): before the
two existing `git diff "$DIFF_BASE" ...` calls at `gather-context.sh:106-121`,
read `$PROJECT_ROOT/docs/dev/project-management/autopilot/review-paths` if it
exists and is non-empty into a bash array `PATHS`; when non-empty, append
`-- "${PATHS[@]}"` to both `git diff` invocations and set
`DIFF_SCOPE="path-scoped review (${#PATHS[@]} paths from docs/dev/project-management/autopilot/review-paths)"`
(overriding whatever `DIFF_SCOPE` the `--since` branch set - path-scoping and
incremental-since are independent axes, and the PRD's acceptance criterion
only pins the path-scoped line's wording, not an interaction with `--since`,
so path-scoping wins the display line when both are present since it is the
narrower, more specific claim). An empty marker file behaves as absent (the
acceptance criterion's own wording): `[[ -s "$marker" ]]`, not `[[ -f
"$marker" ]]`, gates the whole block.

## Data flow

1. `wave assemble` (00215, already shipped) leaves `wave.json` with
   `status: assembled|assembled_partial` and the `assembly` block.
2. `wave review` (or `wave_run.run`'s review step): `review_paths(wave)` reads
   `wave["lanes"]` (every lane, merged or kept - in memory, from the loaded
   `wave.json` - no filesystem read beyond that one file). `stub_text(wave)`
   stays pure over that same in-memory dict (no disk read at all - see
   `## Interfaces & contracts`'s note on why it names PRDs by basename
   rather than extracting their Success Metrics text).
   `seed_state` writes the stub file, copies `meta/`, and shells out through
   `run_cli` to `init`/`statectl`/`phase-done` - the only network of state
   writes in the whole PRD, all inside the assembly worktree.
3. The spawned `autopilot loop` (unchanged, 00106/00017 machinery) runs
   entirely inside the assembly worktree: it is a full, ordinary autopilot
   loop that happens to start from the review gate because the seeded state
   already reads `phase: review`. Every read the review-rework cycle makes
   (the PRD's own body, `docs/dev/project-management/autopilot/review-paths`, the diff range)
   comes from files `seed_state`/`review` wrote inside that worktree; nothing
   crosses back into the main checkout until `land`. `review()` holds no
   lock on the MAIN `wave.json` during this whole span (`## Interfaces &
   contracts`), so `wave status`/other read-only verbs keep working the
   entire time; `wave["status"]` still reads `assembled`/`assembled_partial`
   until the loop exits and `review()` reacquires the lock to write the
   outcome.
4. `land` reads the finished worktree's outcome (`wave["status"] ==
   "converged"` or `"review_failed"`, as `review()`'s own final locked write
   set it) and, on convergence, is the one function that writes the main
   checkout: the `git merge --ff-only` (skipped if a retry finds it already
   done), `migrate_lane`'s ledger/report/review copies (idempotent on a
   retry), and the stub's own `done/` move - resumable end to end (`##
   Interfaces & contracts`'s `land()` entry), so a crash partway through is
   safe to retry rather than a stuck half-landed wave. On `review_failed`,
   `land` writes nothing to the main checkout - the assembly worktree and
   its branch stay exactly as the loop left them, available for a later
   manual `wave land` after a hand review.

## Reuse inventory

- `wave.locked(wave_path)` (wave.py:196-200) - the exclusive-flock context
  manager `launch`/`abort`/`assemble` already hold for their whole bodies.
  `land()` reuses it the same way; `review()` reuses it only around its two
  short wave.json touches, releasing it for the long spawn-and-wait span
  (`## Interfaces & contracts` - a locking discipline an earlier draft
  omitted entirely, caught in review).
- `wave.py`'s `WAVE_STATUSES` tuple (wave.py:28-38) - extended with
  `"converged"` and `"review_failed"` (`## Module placement`); the same
  extension pattern 00215 already used for `assembled`/`assembled_partial`/
  `conflict`/`checks_failed`.
- `wave_assemble.migrate_lane(main, wave_id, lane)` (wave_assemble.py:399-421)
  - `land()` calls this directly with a synthesized `{"name": "assembly", ...}`
    lane dict instead of reimplementing jsonl/deferred/report/review copying.
- `wave_launch.py`'s `_seed_lane_worktree` mkdir-and-copy-meta pattern
  (wave_launch.py:165-177) - `seed_state` mirrors its shape (own literals,
  not an import, matching every other wave module's convention) rather than
  inventing a new worktree-seeding idiom.
- `wave_launch.py`'s `_spawn_lane`/`_SPAWN_CMD` recipe (the bash-exec/
  session-group/env invocation `launch()` already uses per lane) -
  `review()` reuses the same spawn shape minus the review-slot env vars,
  per the PRD's "no slot variables" line.
- `cli/__main__.py`'s existing `init` and `phase-done --state` subcommands,
  and `scripts/statectl.py set` - `seed_state` drives all three exactly as
  they already exist; no new CLI surface needed for the state seed itself.
- `wave abort`'s per-lane SIGTERM/SIGKILL escalation (wave_launch.py, the
  function backing the `abort` verb's step 1) - `wave_run.run`'s interrupt
  handler calls that same per-lane kill routine, not the `abort` verb
  end-to-end (abort's PRD-hand-back step 2 is wrong for an interrupted, not
  aborted, wave).
- Searches tried for anything already resembling "run a nested review loop
  from a seeded state": `rg -n "phase-done.*tasks_done|seed.*state|nested
  loop" skills/run-autopilot` - nothing found beyond the design-solution
  rework-mode doc's own use of `phase-done`/seeding language, which is prose,
  not code to reuse.
- The stub's own `wip` -> `done` relocation needs no new helper at all: it
  rides inside `migrate_lane`'s existing `_route_prds` call (`##
  Interfaces & contracts`'s `land()` entry) since the assembly worktree only
  ever holds the one stub PRD. An earlier draft looked for a dedicated
  "verified wip -> done move" helper here (`records.py`'s
  `_move_prd_to_hold`, records.py:367-380, is the closest existing idiom but
  is wip->hold only) and wrote a second, separate `shutil.move` for the
  stub - redundant once the gitignored-everywhere correction (`##
  Architecture fit`) established that nothing else is ever present to
  conflict with `_route_prds`'s own move.

## Alternatives considered

1. **Chosen: seed a stub PRD and run the ordinary `autopilot loop`, unchanged,
   inside the assembly worktree.** Every review-rework mechanism (roster,
   cap, doubt lens, VERIFY-finding routing, audit log) is reused with zero
   new code; the only new surface is what gets the loop into that state
   (`stub_text`/`seed_state`) and what happens after it exits (`land`). This
   is what 00212 asked for ("the full roster, through the ordinary loop").
2. **A dedicated, standalone assembly-review skill (no nested loop, no
   stub PRD).** Smallest-diff option: a single `/autopilot:review-work-completion`
   invocation over the merge range, findings written straight to a report,
   no rework loop, no cap. Rejected: 00212's open question 2 explicitly
   decided against this - a merge that introduces a CRITICAL needs the same
   rework discipline any other PRD gets, and a one-shot review has no rework
   step at all. Kept in mind as the fallback if the nested-loop approach
   proves too fragile in practice (see Risks).
3. **Teach `review-work-completion` a "merge review" mode directly (no
   `autopilot loop` spawn, no stub PRD, but still a rework loop) by having
   the invoking `wave review`/`wave run` process run the review-rework cycle
   in-process against the assembly worktree, instead of spawning a separate
   loop.** Rejected: this duplicates the cap/cycle/audit-log bookkeeping
   `run-autopilot`'s Phase 5/6 already implement (cycle counting, rework
   dispatch, the audit-log render - all `run-autopilot`-internal, not
   exposed as a library `review-work-completion` alone could call). It would
   also need its own state.json for the assembly worktree's review anyway
   (the cap/cycle bookkeeping reads and writes one), so the "no second state
   file" saving this alternative might seem to offer does not materialize -
   a nested, separately-spawned `autopilot loop` gets that state file, the
   whole review-rework machinery, and process-level isolation (the survives-
   a-crashed-parent property `launch()` already gives lanes) for the same
   cost.

## Risks & edge cases

- **A `review_failed` wave's assembly worktree is a second live checkout an
  operator must remember to clean up by hand** (accepted by the PRD: "the
  wave then fails to land rather than landing unreviewed work" - the same
  tradeoff `wave abort`'s kept-worktree case already accepts).
- **`land`'s master-moved refusal (exit 5) is a race**: the confirmation gate
  in `wave_run.run` happens before the long launch/wait/assemble/review span,
  so master can move at any point after planning. `land` itself re-checks
  HEAD immediately before its one git write, which is the same as-late-as-
  possible check `wave_launch.launch` already uses for its own dirty-tree
  refusal - not a new pattern, just applied at this PRD's own git-writing
  step. Unlike that check, this one is now retriable rather than terminal
  (`## Interfaces & contracts`'s `land()` entry): a `5` means master moved
  and land refused outright, an operator resolves it by hand (merge or
  rebase master) exactly as today, but a failure AFTER the merge already
  landed (a crashed migration, an interrupted cleanup) is a plain retry, not
  a stuck wave.
- **A codex/gemini-dependent reviewer inside the nested loop is unavailable
  on the host running `wave run`** - already handled by every existing
  fallback (Claude subagent substitution) inside `review-work-completion`;
  nothing new here, just inherited.
- **A SIGINT/SIGTERM delivered during `review()`'s own wait (as opposed to
  `wave_run.run`'s lane-launch wait, which the PRD explicitly scopes signal
  handling to) is not covered by any handler in this design** (raised in
  review, codex dispatch 2). The spawned review loop is its own session
  leader (`start_new_session=True`, same as a lane), so it is not killed by
  a signal to the parent and is not left orphaned either - it keeps running
  and can still converge or fail on its own, exactly as a lane does when
  `wave_run.run` itself is killed outright. What this design does NOT
  provide is a clean `wave review --resume`/attach-to-a-running-pid path for
  an operator who wants to reconnect to it (the same gap already named
  above under "Likely next changes" - `review()`'s pid is not persisted
  anywhere). The PRD's own SIGINT/SIGTERM acceptance criterion is scoped to
  the launch-wait step only ("poll every 30s until every lane pid is dead...
  SIGINT or SIGTERM forwards SIGTERM to every live lane group"); this design
  does not extend that scope to the review step, and flags it here rather
  than silently narrowing the finding away.
- **Likely next changes after this PRD**: (1) PRD 00217's review-slot
  semaphore, which this design already accommodates by not needing slot
  variables for the single assembly-review loop (only lanes contend for
  slots); (2) a `wave review --resume` or similar for re-attaching to a
  still-running assembly loop after the operator's own session died -
  `review()`'s current design blocks on `spawn_fn(...).wait()` inside one
  process, so a crash of the *spawning* session (not the loop) currently
  loses the wait, not the loop itself (the loop is its own session leader,
  same survival property `launch()` already gives lanes) - a future PRD
  would need `review()` to also support attaching to an already-running pid
  rather than always spawning; this design does not block that follow-up,
  it just does not build it now; (3) surfacing `wave_run.run`'s per-step
  timing (plan/launch/wait/assemble/review/land) in the wave summary the way
  the PRD's own post-release success metric asks for (wall-clock per PRD) -
  this design's `land` already writes one summary line per outcome, which is
  where that follow-up would append.
- **This design does not box in** a future per-lane parallel *review* (only
  the assembly gets one nested loop right now); `wave_review.review`'s
  signature takes the whole `wave` dict, not a single lane, so extending it
  to a lane-scoped call later is a signature-compatible addition, not a
  rewrite.

## Test strategy outline

Every new Python test imports its fixtures from the sibling modules already
established (explore research, item 12): `_repo`/`_planned`/`_FakeSpawn` from
`test_wave_launch.py`, `_launched`/`_checks_pass` from `test_wave_assemble.py`
- `test_wave_review.py` defines no new fixture module, following the existing
convention of siblings importing each other's helpers.

- `stub_text`/`review_paths`: pure-function tests need only a hand-built
  `wave` dict (no git, no tmp_path) - `test_stub_prd_names_every_merged_lane_and_the_range`,
  `test_stub_prd_carries_the_headings_plan_tasks_parses`,
  `test_stub_frontmatter_is_the_five_pairs` (parsed through
  `cli.frontmatter.parse` with no warning - the real parser, not a
  hand-rolled check), `test_stub_prd_lists_the_diff_scope`,
  `test_review_paths_are_the_multi_lane_files_plus_append_only` (per the
  PRD's own worked example: l1+l2 both list `cli/records.py`, l1 alone lists
  `cli/x.py` -> result is exactly `CHANGELOG.md`, `cli/records.py`,
  `dev/bin/release-checks` and never `cli/x.py`; a third, kept (unmerged)
  lane also listing `cli/records.py` still counts toward the two-or-more
  threshold - "a kept lane's files count too")
- `seed_state`: `test_seeded_state_is_the_tasks_done_shape` - injected
  `run_cli` records every argv and returns a canned
  `CompletedProcess(returncode=0)`; assert on the recorded argv list's shape
  and order (init, four statectl sets, phase-done last) rather than a real
  subprocess; then run the *real* CLI once in a `tmp_path` git repo (no
  injection) and assert `schema.validate` passes on the resulting
  `state.json` plus the exact field values the PRD pins.
  `test_seed_state_extracts_only_the_two_pinned_plugin_versions` - a
  realistic multi-plugin `installed_plugins.json` fixture (several plugins
  besides aegis/warden) -> assert `batch.plugin_versions` is exactly the
  two-key `{"aegis@buvis-plugins": ..., "warden@buvis-plugins": ...}`
  mapping, not the whole file, and that the loop's own `plugin_drift` check
  (`cli/loop.py`) reports no drift against it.
- `review`: `test_review_writes_review_paths_in_the_assembly_worktree`,
  `test_review_copies_meta_and_spawns_the_loop_in_the_assembly_worktree`
  (`_FakeSpawn` records cwd + argv + absence of slot env vars),
  `test_review_outcome_reads_done_and_hold` (fake spawn moves the stub PRD
  to `done/` or `hold/` inside the assembly worktree before "exiting"; assert
  the persisted `wave.json`'s `status` reads exactly `"converged"` or
  `"review_failed"`, not the pre-review `assembled`/`assembled_partial`),
  `test_review_refuses_before_assembly` (wave status `running` -> ValueError),
  `test_review_releases_the_lock_during_the_wait` (acquire `wave.json.lock`
  from the test itself between the fake spawn starting and finishing;
  assert a concurrent `wave_launch.status` call succeeds rather than
  blocking - pins the locking-discipline fix).
- `land`: `test_land_fast_forwards_master_and_removes_the_worktree`,
  `test_land_migrates_the_assembly_artifacts_as_lane_assembly` (assert the
  migrated jsonl lines carry `"lane": "assembly"`),
  `test_land_refuses_when_master_moved` (exit 5, no git write - assert via a
  commit-count check before/after), `test_review_failed_keeps_master_untouched`,
  `test_land_precondition_rejects_assembled_status` (wave["status"] still
  `"assembled"`, never reviewed -> ValueError, pinning the corrected
  precondition), `test_land_resumes_after_a_migration_crash` (inject a
  `migrate_lane` that raises AFTER setting `lane["migrated_at"]` but before
  returning, on its first call; land raises too, `wave.json` still reads
  `status: "converged"` but its `assembly.migrated_at` is now set; a second
  `land()` call with the crash removed completes cleanly, the merge step is
  a no-op since HEAD already equals the assembly tip, AND the jsonl ledger
  files gained exactly one set of appended lines, not two - pinning the
  fix that passes `wave["assembly"]` itself, not a fresh dict, as the lane
  argument so `migrated_at` survives the retry), `test_land_
  refreshes_the_archived_head_sha` (commit one more rework change on the
  assembly branch after `assemble()` recorded its `head_sha`; assert the
  archived `reports/<id>-wave.json`'s `assembly.head_sha` matches the
  branch's ACTUAL tip at land time, not the stale assemble-time value).
- `wave.py`: `test_wave_statuses_include_converged_and_review_failed` -
  `_TOP_CHECKS["status"]` accepts both new values, pinning the
  `WAVE_STATUSES` extension.
- `wave_cli.py`: `test_wave_cli_registers_review_land_run_as_wave_subverbs` -
  parse `["wave", "review", "--state", ...]` (and `land`, `run`) through the
  real `argparse` parser `add()` builds and assert `args.verb` is set (a
  top-level-command mistake, the one caught in review, would instead raise
  `SystemExit` on an unrecognized top-level command or produce a namespace
  with no `verb` attribute at all).
- `wave_run.run`: `test_run_orders_plan_launch_wait_assemble_review_land`
  (every step replaced by a recording fake, assert call order),
  `test_run_without_tty_needs_yes` (monkeypatch `sys.stdin.isatty` False, no
  `--yes` -> exit 1 before `wave.plan` is ever called),
  `test_run_exit_code_follows_the_weakest_step` (assemble returns 3, review
  converges, land succeeds -> final exit 3),
  `test_run_exit_code_last_nonzero_step_wins` (assemble returns 3, review
  converges, land returns 5 (master moved) -> final exit 5, pinning the
  combination rule from `## Interfaces & contracts`), `test_run_interrupt_terminates_lane_groups`
  (injected `kill_fn`; raise a fake `KeyboardInterrupt`/send a real `SIGINT`
  to the test process inside the poll loop and assert every recorded live
  lane got a forwarded SIGTERM).
- `gather-context.sh` filter:
  `bash skills/review-work-completion/scripts/test_gather_context_paths.sh`
  - a `tmp_path`-equivalent throwaway git repo (bash `mktemp -d`, `git init`),
  a `master` base, a branch touching `a.py`/`b.py`, marker holding `a.py` ->
  assert the diff file holds `a.py` hunks only and the printed scope line
  matches `path-scoped review (1 paths from docs/dev/project-management/autopilot/review-paths)`;
  no marker -> both files, today's scope line; empty marker (`: >
  review-paths`) -> behaves as absent; re-run the existing
  `test_gather_context_id.sh` unmodified and confirm it still passes (no
  regression from the new branch in the script).
- `dev/bin/release-checks`: no new test of the script itself - the PRD's own
  Phase 2 acceptance is `release-checks green`, which is exercised by running
  the real script once the two new suites are wired in, not by testing
  `release-checks`'s own bash.

## Review log

- non-blocker (dispatch 1, claude): the `review()` spawn-recipe description
  originally said `caffeinate -is autopilot loop`, which doesn't match
  `wave_launch.py`'s real `_spawn_lane`/`_SPAWN_CMD` shape (`caffeinate` only
  wraps the outer `autoclaude wave` alias, a different layer). Folded into
  the `plugins_json` blocker fix above (same paragraph rewritten) rather than
  left open, since both touched the same docstring; recorded here per the
  non-blocker protocol.
- question (dispatch 1, claude): Alternative 3's original rejection
  rationale claimed the main checkout's own session "already tracks
  `state.prd` for the wave's *next* backlog PRD" during a wave, which isn't
  how launch/assemble actually work (lane PRDs move OUT of the main
  checkout's backlog at launch time; nothing runs an ordinary per-PRD loop
  against the main checkout concurrently with a live wave). Reworded above
  to ground the rejection in the bookkeeping-duplication argument only,
  which holds regardless.
- dispatch 1 (claude): cardinal-sin 0, blocker 6, non-blocker 1, question 1
- **Process note on dispatch 2**: the mandatory codex dispatch was launched
  as a background Bash call per protocol, with a Watcher subagent polling
  `await_reviewer_outputs.py` to keep the session open. That script reported
  `DONE` after ~7 minutes based on a 10s mtime-stability heuristic, but codex
  (gpt-5.6-sol, reasoning effort xhigh) was still actively grounding itself
  in the codebase - its own tool-call cadence has pauses longer than 10s, so
  the heuristic false-positived. Reading the file at that point (330KB,
  ending mid-tool-output with no closing JSON) looked exactly like an
  unparseable-output outage per the skill's own contingency, so a Claude
  fallback was dispatched in its place. Codex was, in fact, still running;
  it completed for real about 20 minutes later with a full, far more
  thorough JSON findings array. Both passes' findings are recorded below;
  the fallback pass is folded in as a bonus supplemental pass (not counted
  against the 3-dispatch ceiling) since it ran to completion honestly and
  found real, valid issues before codex's own answer was known to exist.
- non-blocker (claude-fallback pass, supplemental): `wave_cli.py`'s
  verb-registration snippet added `review`/`land`/`run` on a fresh
  `subparsers.add_parser(...)` instead of the existing `verbs` subparsers
  object every other wave verb registers on - fixed in `## Module placement`
  and the `wave_cli.py` code block (`## Interfaces & contracts`).
- non-blocker (claude-fallback pass, supplemental): `wave.py` was missing
  from `## Module placement`'s edited-files list even though
  `WAVE_STATUSES` needed extending - fixed (folded into the same fix codex's
  dispatch 2 independently raised for `converged`/`review_failed`).
- non-blocker (claude-fallback pass, supplemental): state-schema.md's
  Marker files table is four columns, not the "five-column" the design
  claimed - fixed in `## Module placement`.
- question (claude-fallback pass, supplemental): `wave_run.run`'s combined
  exit code was unspecified when more than one step returns non-zero in the
  same run - resolved with an explicit "last non-zero step wins" rule and a
  pinning test, in the `wave_run.run` docstring and `## Test strategy
  outline`.
- non-blocker (claude-fallback pass, supplemental, dissolved rather than
  patched): a concern that `land()`'s reuse of `migrate_lane` would
  redundantly re-move every already-migrated lane's PRDs, not just the
  stub's - this was reasoning from the same false "docs/dev/project-management
  is tracked" premise dispatch 2 (codex) independently flagged; once
  corrected (`## Architecture fit`), the assembly worktree never holds any
  PRD but the stub, so there is nothing else for `_route_prds` to
  redundantly move.
- dispatch 2 (codex): cardinal-sin 1, blocker 7, non-blocker 1, question 0.
  Two of the seven blockers (the "tracked working-document layout" finding
  and the "loop can continue into unrelated backlog PRDs" finding) were
  built on the same false "tracked" premise the design originally stated;
  correcting that premise (`## Architecture fit`) resolves both directly
  rather than requiring a structural code fix - documented there rather than
  silently dropped. The cardinal-sin (no rollback/forward-recovery path for
  `land`) and the remaining five blockers (the impossible review-outcome
  state machine, the wrong plugin-version pin shape, non-resumable/
  non-interrupt-safe detached review execution, the signature drift from
  the PRD's authoritative exports, and the missing wave.json locking
  contract) are all fixed in `## Interfaces & contracts`'s `seed_state`,
  `review`, and `land` entries, `## Module placement`, and `## Reuse
  inventory`. The one non-blocker (stale archived `assembly.head_sha` after
  rework) is fixed in `land()`'s entry (step 1 resolves the tip fresh).
  Detached-review interrupt-safety (recording a reviewing pid/pgid and
  covering it with a signal handler) is flagged but NOT fully designed here
  - see `## Risks & edge cases`'s new entry below; the happy-path and
  crash-then-retry behavior are both specified and testable, but a clean
  SIGINT/SIGTERM path for the review step specifically (as opposed to
  `wave_run.run`'s existing lane-wait interrupt handling) is deferred as a
  named risk rather than solved by this design.
- **Process note on dispatch 3**: the mandatory codex verification pass
  stalled - its output file and the underlying `codex exec` process's CPU
  time both stayed frozen across two full ~10-minute `await_reviewer_outputs.py`
  waits (well past the 2x10min outage deadline), so it was killed and a
  Claude fallback ran the same verification prompt in its place.
- dispatch 3 (claude-fallback, verifying dispatch 2's 9 findings): 8 of 9
  RESOLVED with fresh, independently re-checked evidence (the review outcome
  state machine, the plugin-version extraction against the real
  `plugin_drift` consumer, the gitignored-everywhere correction re-verified
  directly against `test_wave_launch.py:71`, the unreachable-backlog-PRDs
  finding as a direct consequence of that correction, the signature drift
  reverted for `seed_state` and defensibly kept for `review`'s `run_git`,
  the locking contract now used by both `review()` and `land()`, and the
  stale `head_sha` fix). 1 (detached-review interrupt-safety) PARTIALLY
  RESOLVED and accepted as such - crash-then-retry resumability is verified
  sound, signal-handling during the review wait remains a named, deliberate
  gap (`## Risks & edge cases`), not silently dropped. The pass also
  surfaced ONE NEW BLOCKER before this doc's own fixes were applied:
  `land()`'s synthetic lane dict for `migrate_lane` was a fresh literal on
  every call, so `migrated_at` never persisted across a retry and a crash
  after a first `migrate_lane` call would double-append every ledger jsonl
  line on the next attempt - fixed by passing `wave["assembly"]` itself as
  the lane argument (`## Interfaces & contracts`'s `land()` step 4), so
  `migrate_lane`'s own mutation of `lane["migrated_at"]` lands on the exact
  sub-dict step 5 saves back to `wave.json`. One non-blocker (review()'s
  first read skips the lock-reload discipline every other verb uses) is
  addressed with a justification note in `review()`'s own entry rather than
  an added lock, since no concurrent action currently invalidates that read.
  No open cardinal sins or blockers remain after this pass; the 3-dispatch
  ceiling is reached.
- dispatch 3 (claude-fallback): cardinal-sin 0, blocker 1, non-blocker 1, question 0
