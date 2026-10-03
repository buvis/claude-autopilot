# Harden the wave verbs - design

## Architecture fit

This PRD lands entirely inside the existing `skills/run-autopilot/cli/` wave
stack (PRDs 00214-00217) plus the two repo-root gate files that keep the
`waves` test family honest. No new module, no new layer, no new public
interface: every fix tightens an existing function's ordering, guard, or
predicate inside the modules that already own that responsibility
(`wave_assemble` owns teardown, `wave_cli` owns verb dispatch and error
translation, `wave_review` owns the assembly worktree's gate and land path,
`wave_slots` owns the slot semaphore, `loop.py` owns the review-once store
write). The six fixes are independent of each other except for the shared
release-gate wiring (00221), which both gates and gives test coverage to the
rest. `store_tree.foreign_dirty`/`in_wave_lane` (PRD 00236/00239's own
module) is the store-aware primitive two of the six fixes (00225, 00239)
must now call instead of raw `git status --porcelain` or no guard at all -
it already exists and ships unchanged.

## Module placement

All edits are to existing files; no new files.

- `skills/run-autopilot/cli/wave_assemble.py` - reorder `_drain_lane`'s
  `save()` relative to `migrate_lane`/`worktree remove`/`branch -D` (00222).
- `skills/run-autopilot/cli/wave_cli.py` - catch `OSError` from the
  `assemble` verb (00222).
- `skills/run-autopilot/cli/wave_review.py` - swap `_land_cleanup`'s raw
  `git status --porcelain` for `store_tree.foreign_dirty` (00225); add a
  seed-time backlog-to-hold move before the nested loop spawns (00225); add
  the hand-review check to `_land_review_failed` (00226).
- `skills/run-autopilot/cli/wave_slots.py` - add a per-slot `N.lock` file,
  acquired by `_claim`, `_discard`, `release` (00227).
- `skills/run-autopilot/cli/loop.py` - add the `in_wave_lane` guard to
  `_record_review_once_store` (00239).
- `skills/run-autopilot/cli/test_wave_docs.py` - extend `_WAVE_TEST_FILES`
  and add `test_every_wave_test_file_is_listed` (00221).
- `dev/bin/release-checks` - add `test_wave_assemble_summary.py` to the
  `[checks] waves` pytest invocation (00221).
- `skills/run-autopilot/references/waves.md` - document the hand-review
  land route (00226, Phase 2 of the PRD).
- `CHANGELOG.md` - one `[Unreleased]` `### Fixed` `**run-autopilot**` line
  naming the six fixes (Phase 2 of the PRD).

Test files already exist at HEAD as the PRD's named acceptance tests'
homes (`test_wave_slots.py`, `test_wave_assemble_migrate.py`,
`test_wave_cli_refusals.py`, `test_wave_review.py`,
`test_wave_review_land.py`, `test_loop_record_store.py`,
`test_wave_docs.py`); none of the ten named test functions exist yet
(verified absent by `rg -n "def test_<name>"` against each file, with
`rg -n "def load"` on `wave.py` as the known-hit control proving the search
itself works). Planning adds the test bodies alongside each fix, in the
same file.

## Interfaces & contracts

### 00221 - gate the summary tests

`dev/bin/release-checks`'s `[checks] waves` block (currently lines 146-161+)
gets one more line added to its `\`-continued pytest invocation, in the same
alphabetised-by-topic position used by its neighbors (after
`test_wave_assemble_migrate.py`, before `test_wave_cli_assemble.py`, matching
`_WAVE_TEST_FILES`'s own ordering):

```
  skills/run-autopilot/cli/test_wave_assemble_summary.py \
```

`skills/run-autopilot/cli/test_wave_docs.py`'s `_WAVE_TEST_FILES` tuple
(currently lines 41-58) gets the same basename added, in the same relative
position (after `"test_wave_assemble_migrate.py"`, before
`"test_wave_cli_assemble.py"`):

```python
_WAVE_TEST_FILES = (
    "test_wave.py",
    "test_wave_launch.py",
    "test_wave_launch_status.py",
    "test_wave_launch_abort.py",
    "test_wave_launch_abort_keep.py",
    "test_wave_launch_abort_kill.py",
    "test_wave_launch_refusals.py",
    "test_wave_assemble.py",
    "test_wave_assemble_migrate.py",
    "test_wave_assemble_summary.py",
    "test_wave_cli_assemble.py",
    "test_wave_docs.py",
    "test_wave_run.py",
    "test_wave_review.py",
    "test_wave_review_land.py",
    "test_wave_slots.py",
    "test_loop_slots.py",
)
```

New test `test_wave_docs.py::test_every_wave_test_file_is_listed` - ONE
contract, given directly (an earlier draft of this doc showed a naive
first cut and then a "corrected" second version side by side, which read
as two competing specs; only the version below is the contract):

```python
def test_every_wave_test_file_is_listed() -> None:
    """`_WAVE_TEST_FILES` (minus `test_loop_slots.py`, the one entry that is
    not a `test_wave*.py` basename and so can never appear in the glob) and
    the `cli/` directory's own `test_wave*.py` files agree, so a file
    present on only one side fails loudly instead of the silent gap 00221
    found."""
    on_disk = {
        path.name
        for path in Path(__file__).resolve().parent.glob("test_wave*.py")
    }
    listed = set(_WAVE_TEST_FILES) - {"test_loop_slots.py"}
    assert on_disk == listed, (
        f"cli/: {sorted(on_disk - listed)} not in _WAVE_TEST_FILES; "
        f"_WAVE_TEST_FILES: {sorted(listed - on_disk)} not on disk"
    )
```

Note: `rg --files -g "test_wave*.py"` under `cli/` is the PRD's own stated
comparison shape; `Path.glob("test_wave*.py")` over the same directory the
module lives in is the stdlib equivalent with no subprocess dependency, and
is what the implementation task should use (the PRD names `rg` only to
describe the target set, not to mandate invoking it from Python). This is
exactly the comparison `test_wave.py::test_docs_name_the_wave_files`
performs for `references/waves.md`'s own file list; `test_wave_docs.py`'s
module docstring already calls itself "a sibling" of that pattern, so this
is the same idiom applied to `_WAVE_TEST_FILES`, not a new one. `test_loop_slots.py`
is NOT a `test_wave*.py` file, so this new test's `on_disk` glob (`test_wave*.py`)
intentionally excludes it; `_WAVE_TEST_FILES` keeps `"test_loop_slots.py"` as a
named exception the way the module docstring (line 39-40) already explains
("plus this one" - meaning `test_wave_docs.py` itself; `test_loop_slots.py`
is a second, pre-existing non-`test_wave*` entry in the tuple; the module
docstring's "plus this one" names only `test_wave_docs.py` itself and does
not mention or explain `test_loop_slots.py` - that entry's presence is
unexplained in prose, verified fact for the planner, not an assumption).
Because the new test's `on_disk` set only ever contains `test_wave*.py`
basenames, `test_loop_slots.py` must be special-cased out of the equality
check (done above) or the test fails permanently on a file that correctly
belongs in the gate but never matches the glob.

### 00222 - persist before tearing down; catch OSError in wave_cli

`wave_assemble._drain_lane` (current body, lines 501-528) reorders to save
immediately after each state mutation and again right after the worktree
actually comes down:

```python
def _drain_lane(
    repo: Path,
    wave: dict,
    lane: dict,
    wave_path: Path,
    *,
    run_git: Callable[..., subprocess.CompletedProcess],
) -> set[str]:
    names = set(lane.get("held_prds") or [])
    if lane.get("worktree_removed"):
        return names
    names |= _lane_prd_names(Path(lane["worktree"]))
    lane["held_prds"] = sorted(names)
    migrate_lane(repo, wave["id"], lane)
    save(wave_path, wave)  # held_prds, status, batch_id on disk BEFORE any
                           # destructive git call below runs.
    if lane["status"] == "assembled":
        if Path(lane["worktree"]).exists():
            run_git(["worktree", "remove", "--force", lane["worktree"]], cwd=repo)
        lane["worktree_removed"] = True
        save(wave_path, wave)  # worktree_removed saved right after the
                               # worktree remove succeeds - BEFORE branch -D,
                               # not after it, so a crash between the two
                               # still reads worktree_removed correctly and
                               # only needs to retry the (idempotent) branch
                               # delete on rerun.
        if run_git(["branch", "--list", lane["branch"]], cwd=repo).stdout.strip():
            run_git(["branch", "-D", lane["branch"]], cwd=repo)
    return names
```

`_drain_lane` gains a `wave_path: Path` parameter (positional, after
`lane`, before the keyword-only `run_git`) so it can call `save` itself
instead of relying on its caller's single post-call `save` (`assemble`'s
loop body, currently `_assemble_lane(...); held = _drain_lane(...);
...; save(wave_path, wave)` - that trailing `save` at the end of the loop
body stays, as a backstop for the mutations `_assemble_lane` itself makes
to `lane["status"]`/`lane["conflict_detail"]`/`lane["conflict_paths"]`
before `_drain_lane` runs; `_drain_lane`'s own two saves are what close the
00222 gap, since today's only `save()` is that trailing one, called after
both destructive git ops). `assemble`'s call site becomes:

```python
held = _drain_lane(repo, wave, lane, wave_path, run_git=run_git)
```

`wave_cli.py`'s `run` function gets `OSError` added to the `assemble` verb's
catch tuple (currently `(subprocess.CalledProcessError, wave.WaveCorruptError)`
at line 74):

```python
if args.verb == "assemble":
    return _guarded(
        lambda: wave_assemble.assemble(repo, wave_path),
        (subprocess.CalledProcessError, wave.WaveCorruptError, OSError),
    )
```

`_guarded`'s existing message format (`autopilot: <message>`, one stderr
line, return 1) needs no change: `str(OSError_instance)` already renders
one readable line (e.g. `[Errno 2] No such file or directory: '...'`), and
`_guarded`'s `else: str(caught)` branch already covers any caught type that
is not `WaveCorruptError`. No new message-formatting code - this is purely
adding `OSError` to the tuple.

### 00225a - assembly worktree gate uses `foreign_dirty`

`wave_review.py`'s `_land_cleanup` (lines 391-419), the raw-`git
status --porcelain` call this PRD's finding names (the PRD cites line 403,
which in the current file is inside this function's dirty check, lines
403-412):

```python
def _land_cleanup(
    repo: Path,
    wave_path: Path,
    wave: dict,
    run_git: Callable[..., subprocess.CompletedProcess],
) -> None:
    worktree = Path(wave["assembly"]["worktree"])
    if worktree.is_dir():
        dirty = store_tree.foreign_dirty(worktree, run_git=run_git)
        if dirty:
            raise ValueError(
                f"{worktree} has uncommitted changes:\n" + "\n".join(dirty)
            )
        run_git(["-C", str(repo), "worktree", "remove", "--force", str(worktree)])
    ...
```

The migrated-stub exclude pathspec
(`:(exclude)docs/dev/project-management/prds/done/<stub>`) that the raw call
used is DROPPED: `store_tree.foreign_dirty`'s own store-root exemption
(`STORE_PREFIXES = ("docs/dev/project-management/", "docs/dev/tmp/")`)
already covers the whole store tree, including the migrated stub under
`prds/done/`, so the narrower single-file exclude the old code needed is
now redundant. `foreign_dirty`'s signature is `foreign_dirty(repo: Path,
store_dir: Path | None = None, run_git=run_git) -> list[str]` - called here
positionally with `worktree` as `repo` (the assembly worktree IS the
repository this check runs against) and the existing `run_git` parameter
passed through by keyword, `store_dir` left at its default `None` (the
assembly worktree's store sits at the conventional
`<worktree>/docs/dev/project-management`, which `_store_prefix` resolves
correctly with `store_dir=None` the same way every other `foreign_dirty`
call site in this file already relies on - see `_check_reviewable`,
line 287, which calls it the same way).

Verified directly against `store_tree.py`'s own body (not inferred from
its docstring): `foreign_dirty` iterates `git status --porcelain -z`
entries and does `if path.startswith(roots): continue` before ever
appending to its returned list, where `roots` is built from
`STORE_PREFIXES = ("docs/dev/project-management/", "docs/dev/tmp/")` (plus
any `_store_prefix` offset). A `git status` entry whose path falls under
the store root is therefore never added to the returned "foreign dirty"
list - "foreign" here means "outside the store," by construction, not an
inference from the module's prose summary. This is the existing,
unmodified behavior `_check_reviewable` already depends on at line 287;
`_land_cleanup`'s swap reuses the same guarantee, not a new one.

### 00225b - hold the seeded backlog before the nested loop spawns

`wave_review.seed_state` (current body, lines 243-267) gains one step
between `_seed_prd` and the CLI invocations, moving every
`prds/backlog/*.md` the assembly worktree picked up (by inheriting the
tracked store from `base_sha`) into `prds/hold/`, committed on the
assembly branch, before `_seed_steps`'s `init`/`statectl`/`phase-done`
calls run (which is what spawns the nested loop later in `review`):

```python
def _hold_seeded_backlog(worktree: Path, wave_id: str) -> list[str]:
    """Move every prds/backlog/*.md the assembly worktree inherited into
    prds/hold/ and commit that move on the assembly branch, so the nested
    loop this seed feeds cannot select a main-checkout backlog PRD. Returns
    the moved basenames, sorted, for the commit message and the caller's
    own reporting; [] (no commit) when backlog/ is empty."""
    pm = worktree / "docs/dev/project-management"
    backlog, hold = pm / "prds/backlog", pm / "prds/hold"
    moved = sorted(path.name for path in backlog.glob("*.md"))
    if not moved:
        return []
    hold.mkdir(parents=True, exist_ok=True)
    for name in moved:
        (backlog / name).rename(hold / name)
    message = (
        f"chore(autopilot): hold seeded backlog PRDs for wave {wave_id} review\n\n"
        + "\n".join(f"- {name}" for name in moved)
    )
    _default_run_git(["add", "--", "prds/backlog", "prds/hold"], cwd=worktree)
    _default_run_git(["commit", "-m", message], cwd=worktree)
    return moved
```

Called from `seed_state`, right after `stub = _seed_prd(pm, wave)`:

```python
    stub = _seed_prd(pm, wave)
    _hold_seeded_backlog(state_path.parents[4], wave["id"])
```

`state_path.parents[4]` is the worktree root, and it is already in scope
unchanged: `seed_state`'s very next line calls
`repo = _repo_from_worktree(state_path.parents[4])`, passing the assembly
worktree itself as that helper's argument (`_repo_from_worktree` resolves
the *main checkout* from a worktree path, so its argument, not its return
value, is the worktree this fix needs). Index check against
`state_path`'s actual depth: `state_path` is
`<worktree>/docs/dev/project-management/autopilot/state.json`, so
`state_path.parents[0]` is `.../autopilot`, `[1]` is
`.../docs/dev/project-management` (= `pm`, matching `pm =
state_path.parent.parent`), `[2]` is `.../docs/dev`, `[3]` is `.../docs`,
and `[4]` is `<worktree>` - four hops below the worktree root, confirming
`state_path.parents[4]` (not `pm.parent`, which lands two levels short, at
`.../docs/dev`) is correct.

The design in Phase 1's Feature description for 00225 ("the design doc
confirms whether moving to hold/ or deleting is right") is resolved here:
**move to `hold/`, committed**, matching the PRD's own guess, because
`land`'s PRD-routing path (`wave_assemble._route_prds`,
`_PRD_HOME = {"hold": "hold"}`) already knows how to bring a held PRD home
unmerged, and deleting would make an operator-visible backlog PRD vanish
with no trace if the review worktree is ever inspected by hand.

### 00226 - land after a hand review

`wave_review._land_review_failed` (lines 483-494) gains a check for the
hand-reviewed stub before falling back to its current unconditional
behavior:

```python
def _land_review_failed(repo: Path, wave_path: Path, wave: dict) -> int | None:
    """None when the operator hand-moved the stub to prds/done/ in the
    assembly worktree - the caller then continues into the normal `converged`
    land path. Otherwise records the review_failed outcome and returns 4, as
    before."""
    worktree = Path(wave["assembly"]["worktree"])
    stub = worktree / "docs/dev/project-management/prds/done" / _stub_name(wave)
    if stub.exists():
        with locked(wave_path):
            current = load(wave_path)
            current["status"] = "converged"
            save(wave_path, current)
        return None
    review_file = _review_file(worktree, wave)
    line = (
        f"## Assembly review: review_failed, see {review_file}"
        if review_file is not None
        else "## Assembly review: review_failed, see no review file written"
    )
    _append_summary_line(repo, wave["id"], line)
    print(f"autopilot: {line}", file=sys.stderr)
    return 4
```

`land`'s call site (current lines 522-524) adopts the `None`-means-continue
contract:

```python
    status = wave.get("status")
    if status == "review_failed":
        code = _land_review_failed(repo, wave_path, wave)
        if code is not None:
            return code
        status = "converged"
```

(`land` then falls into its existing `if status == "converged":` branch
unchanged, re-entering `_land_converged`'s normal path - no other line in
`land` changes.) `_land_review_failed` gains the `wave_path: Path`
parameter (positional, between `repo` and `wave`) because it now needs to
save; it did not before.

**On lock span**: `_land_review_failed`'s own `with locked(wave_path):`
block is scoped to its one save, not to the rest of `land`'s body - this
matches `land`'s EXISTING locking pattern exactly, not a new gap this fix
introduces. `land` itself only holds the lock around its initial
`wave = load(wave_path)` (current code, lines 516-517) and runs everything
after that - including the entire `_land_converged`/`_land_cleanup`
sequence - unlocked; `_land_converged`'s own closing `with locked(wave_path):
wave = load(wave_path); ...; save(wave_path, wave)` (lines 457-461) is the
same short-scoped-lock idiom `_land_review_failed` now reuses. A true
whole-body lock across every wave verb is `references/waves.md`'s stated
intent but is not how any existing `land`-path function in this file
actually behaves today; closing that gap, if ever done, is a separate,
pre-existing concern this PRD does not scope in, not a regression this fix
introduces.

`references/waves.md`'s `### autopilot wave land` section gains one
sentence documenting the hand-review route (Phase 2 of the PRD): after the
existing "Returns `4` when the wave's status is `review_failed`" sentence,
add: "An operator who hand-reviewed a `review_failed` assembly and moved
its stub PRD to the assembly worktree's `prds/done/` can rerun `land`: it
finds the stub there, sets the wave's status to `converged`, and lands
normally instead of returning `4` again."

### 00227 - lock the slot reclaim

`wave_slots.py` gains one lock-file-naming convention and three call sites
that hold it. Lock file: sibling of the slot, named `<slot>.lock` (so slot
`3`'s lock is `<slots_dir>/3.lock`), opened in append mode and never
removed (same pattern as `wave.locked`/`custody.py`/`records.py`/
`state.py`'s `<path>.lock` siblings already in this repo - reused verbatim,
not reinvented):

`wave_slots.py` does not import `fcntl` today (its current imports are
`os`, `shutil`, `sys`, `tempfile`, `time`, `Callable`, `Path`, and
`cli.loop_gates._pid_alive`); this fix adds both `import fcntl` and
`import contextlib` to that list.

```python
import contextlib
import fcntl

@contextlib.contextmanager
def _slot_lock(slot: Path):
    """Hold an exclusive flock on `<slot>.lock` for the body. The lock file
    is a permanent sibling, never removed - removing it would race a second
    opener between close and unlink, defeating the lock."""
    lock_path = slot.with_name(f"{slot.name}.lock")
    with open(lock_path, "a") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        yield
```

`_claim(slot, pid)` wraps its whole body (the stage-then-rename) in
`with _slot_lock(slot):`. `_discard(slot, pid, judged)` wraps its whole
body (the aside-rename, the owner comparison, the put-back-or-remove) in
`with _slot_lock(slot):` - this is the fix for the residual race the
function's own docstring already names (lines 102-106 today): the lock
serializes against a concurrent `_claim` that would otherwise take the
vacated name while `_discard` holds the slot aside. `release(slot)` wraps
its body in `with _slot_lock(slot):` too, and gains an ownership check
before removing:

```python
def release(slot: Path, owner_pid: int) -> None:
    """Free a claimed slot IF `owner_pid` still owns it; a missing slot or a
    slot some other pid now owns is a no-op (a crash-and-reclaim cycle
    already moved it on)."""
    with _slot_lock(slot):
        if _owner(slot) == str(owner_pid):
            _remove(slot)
```

`release` gains a required `owner_pid: int` parameter - a breaking
signature change from today's `release(slot: Path) -> None`. The one
production call site, `cli/loop.py::_launch` (acquire at line 421, release
at line 441, both already holding `self.loop_pid`), adds that same pid as
`release`'s second argument - no new pid lookup needed. (Not
`wave_run.py`: that module carries no `wave_slots` reference; see the
Risks section for the corrected citation.)

`acquire`'s internals also move under the lock for consistency: the
existing `_claim`/`_discard` calls inside `acquire`'s loop body are
unchanged in shape (they already call the now-locking `_claim`/`_discard`),
so `acquire`'s own signature and loop structure do not change.

The residual-race comment at `wave_slots.py:102-106` (`_discard`'s
docstring, "One residual stays open... Closing it needs a primitive the
kernel releases (a per-slot `fcntl.flock`) rather than a name; until then
the loss is reported on stderr rather than papered over.") is replaced by
one line: "The per-slot `<slot>.lock` (`_slot_lock`) now closes this
window: `_claim` cannot take the vacated name while `_discard` holds it
aside." The `print(..., file=sys.stderr)` dead-letter path in the old
docstring's described failure mode becomes unreachable once the lock is in
place and should be left as-is in code (defensive, now unreachable under
normal operation, not a scenario the fix needs to delete code over) but the
docstring sentence describing it as a known, accepted loss is what gets
replaced.

### 00239 - guard review-once in a lane

`loop.py`'s `_record_review_once_store` (lines 506-517) gains the same
guard its two siblings (`loop.py:611`, `loop_act.py:218`) already carry:

```python
def _record_review_once_store(self, ap_dir: Path, decision: dict) -> None:
    if store_tree.in_wave_lane(self.env):
        return
    try:
        store_repo, store_run_git = store_git(ap_dir)
        store_tree.record_store(
            store_repo,
            "review_once",
            decision.get("prd", ""),
            ap_dir.parent,
            run_git=store_run_git,
        )
    except Exception:
        pass
```

This mirrors `loop.py:608-611`'s `if (decision["signal"] == "continue" and
decision.get("state_touched") and not store_tree.in_wave_lane(self.env)):`
and `loop_act.py:218`'s `if not store_tree.in_wave_lane(self.env):` exactly
- `store_tree.in_wave_lane(env: Mapping[str, str] | None = None) -> bool`
is called the same way at all three sites, with `self.env` (the `Loop`
instance's own environment mapping, already used by both existing guarded
call sites) as the single argument.

## Data flow

**00221**: no runtime data flow - a static text/list edit to two files that
`release-checks` and `test_wave_docs.py` both read at test-collection time.

**00222**: `_drain_lane` already mutates `lane` (a sub-dict of the in-memory
`wave` dict `assemble` holds) before this change; the only flow change is
WHEN `wave` reaches disk relative to the two destructive git calls. On a
crash between the new first `save()` and the `worktree remove` call, a
rerun of `assemble` finds `lane["worktree_removed"]` absent (because that
flag is set and saved right after the `worktree remove` call succeeds, not
before it) but `lane["status"] == "assembled"` and `held_prds` already
populated and saved - so `_drain_lane` re-enters, re-runs `migrate_lane`
(idempotent per its own docstring: jsonl append is migrated_at-guarded,
deferred/reports/PRD-route steps are re-evaluated every call and are
no-ops on a second pass), and retries the git teardown; `Path(lane["worktree"]).exists()`
is false the second time (the worktree is actually gone), so the `worktree
remove` call is skipped and `worktree_removed` is immediately re-saved
`True`, then the `branch --list`/`branch -D` pair runs (git's own `--list`
check already makes a second `branch -D` a no-op if the first one
completed before a crash between the worktree-removal save and the branch
delete). `wave_cli.run`'s `OSError` catch sits one layer above: if the
removed-but-not-yet-saved worktree path makes a *later* call (e.g.
`lane_files_and_notes` reading a cwd that is gone) raise `OSError` rather
than being caught by the save-ordering fix itself, `_guarded` now converts
that into one stderr line and exit 1 instead of a raw traceback.

**00225a**: `_land_cleanup`'s dirty check now reads the assembly worktree's
git status through the same `foreign_dirty` filter the main checkout
already uses (since 00236) before every other gate in this pack - so a
store commit sitting uncommitted in the assembly worktree (produced by the
nested loop's own `record_store` calls during review) no longer blocks
`land`'s destructive cleanup.

**00225b**: `seed_state` runs once per wave's review pass, before the
nested loop spawns. The move-then-commit happens on the assembly branch,
so it is part of that branch's history going forward; `land`'s eventual
fast-forward of the main checkout onto the assembly branch's tip means the
main checkout's `backlog/` never regains those PRDs through this path (they
land in the main checkout's `hold/` instead, via the normal merge).

**00226**: `_land_review_failed` now reads one extra path
(`<worktree>/prds/done/<stub>`) before deciding its return value; when
present, it writes `wave.json`'s status itself (under the existing
`wave_path.lock`) and returns `None` instead of `4`, letting `land`'s own
flow fall through into the already-existing `converged` branch - no
duplicate landing logic.

**00227**: every `_claim`/`_discard`/`release` call now takes the slot's
flock before touching the slot's filesystem state, and releases it (via
the `with` block) once that touch - and, for `_discard`, the full
judge-and-decide sequence - is done. The lock serializes concurrent holders
of the SAME slot number only; two different slot numbers lock
independently, so `acquire`'s scan across `1..count` is unaffected in
concurrency shape, only the per-slot critical section is now atomic from
the kernel's point of view instead of relying on rename atomicity alone.

**00239**: identical data flow to the two existing guarded sites - the
guard is a pure early return, no new data touched.

## Reuse inventory

- `cli/store_tree.py::foreign_dirty(repo, store_dir=None, run_git=run_git)`
  - reused verbatim in `wave_review._land_cleanup` (00225a), same call
    shape `_check_reviewable` (same file, line 287) already uses.
- `cli/store_tree.py::in_wave_lane(env=None) -> bool` - reused verbatim in
  `loop.py::_record_review_once_store` (00239), same call shape as
  `loop.py:611` and `loop_act.py:218`.
- `cli/wave.py::locked(wave_path)` / `load(path)` / `save(path, wave)` -
  reused verbatim in `_land_review_failed`'s new save (00226); already the
  pattern every other wave.json mutation in `wave_review.py`/`wave_assemble.py`
  uses (e.g. `review`'s own `with locked(wave_path): ...; save(...)` at
  lines 333-336).
- `fcntl.flock(fd, fcntl.LOCK_EX)` on a sidecar `<path>.lock` file - the
  exact primitive `cli/wave.py::locked` (line 206), `cli/custody.py` (line
  54), `cli/records.py` (line 161), `cli/state.py` (lines 144, 209), and
  `skills/run-autopilot/scripts/fablectl.py` (line 159) all already use for
  the same purpose (one exclusive lock per logical resource, held for a
  whole check-and-mutate body). `wave_slots.py`'s new `_slot_lock` (00227)
  is the same idiom applied one level finer (per-slot rather than
  per-file), reusing the stdlib call shape these five sites already settled
  on rather than inventing a new locking primitive.
- `cli/wave_assemble.py::migrate_lane` - already idempotent (its own
  docstring states this); 00222's save-ordering fix relies on that
  idempotency for a crash-and-rerun to be clean, and adds no new
  idempotency logic of its own.
- `cli/wave_review.py::_stub_name(wave)` - reused verbatim in both 00225b
  (none needed there, but 00226's hand-review path reuses it to compute
  the `prds/done/` path) and the existing `review`/`_land_migrate` call
  sites.
- nothing found for "per-slot lock file naming convention distinct from
  `wave.locked`'s whole-file lock" - greps tried: `rg -n "N.lock|slot.*lock"
  cli/`, `rg -n "flock.*slot" cli/` - every existing flock use in this repo
  locks a single named resource file, none locks one-of-N numbered
  resources, so `_slot_lock`'s sibling-file-per-slot convention is new
  within this repo but follows the existing single-resource idiom exactly.
- nothing found for "existing OSError translation inside `wave_cli.py`'s
  `_guarded` beyond the three tuples already there" - greps tried: `rg -n
  "OSError" cli/wave_cli.py`, `rg -n "except.*Error" cli/wave_cli.py` -
  confirms `_guarded`'s generic `str(caught)` branch already handles any
  added exception type with no new formatting code, which is why 00222's
  fix is a one-token tuple edit.

## Alternatives considered

**Teardown ordering (00222):**
1. **Chosen: two `save()` calls inside `_drain_lane`** (after state
   mutation, after worktree removal) - smallest-diff version that closes
   the exact window the PRD names, reusing the existing `save` signature
   with no new parameters beyond threading `wave_path` through one more
   call.
2. Wrap the whole `_assemble_lane`/`_drain_lane` pair in a single
   try/finally that always saves on the way out - rejected: a save-on-exit
   still runs AFTER the destructive git calls if they're inside the
   try-block's tail, so it does not actually move the save earlier; it
   would need the same two-point restructuring as the chosen option but
   with worse locality (the save site is far from the mutation it saves).
3. Make `wave_assemble.assemble`'s outer loop save after every lane
   regardless of `_drain_lane`'s internals (today's status quo, just
   moved earlier in the loop) - rejected: this still leaves
   `worktree_removed` unsaved between the `remove` and `branch -D` calls
   within one lane's processing, which is the exact crash window 00222
   names; only a save inside `_drain_lane`, bracketing the destructive
   calls themselves, closes it.

**Slot lock mechanism (00227):**
1. **Chosen: per-slot `fcntl.flock` on a sibling `N.lock` file**, held by
   `_claim`/`_discard`/`release` across their whole check-and-rename - this
   is the fix the PRD names explicitly and the one the existing code
   comment (`wave_slots.py:102-106`) already points to as the closing
   primitive; it is advisory-local but every slot path in this pack runs on
   one host by design (`references/waves.md`), so that limitation is
   already accepted elsewhere in this system.
2. A single whole-pool lock (one `wave-slots.lock` guarding the entire
   `acquire`/`_discard`/`release` traffic, not per-slot) - rejected:
   serializes every claimant against every other regardless of which slot
   they touch, turning a bounded-concurrency semaphore into a fully
   sequential one; defeats the feature's purpose (`count` concurrent
   holders) for the sake of fixing one narrow race.
3. A lease/heartbeat timestamp inside the owner file instead of a lock (a
   slot older than N seconds is reclaimable, written and checked
   atomically via `os.rename` of a whole replacement file) - rejected as
   the larger-diff option: it does not actually close the race (a stale
   check followed by a rename is still two steps a third claimant can land
   between), and it discards the already-present pid-liveness check
   (`_is_stale`/`_pid_alive`) that correctly detects a crashed holder
   immediately rather than waiting out a lease window. The flock option is
   strictly smaller and closes the race outright.

## Risks & edge cases

- **flock is advisory and local** (named in the PRD's own Risks section):
  a slot lock taken by one process only excludes another process ON THE
  SAME HOST that also calls `fcntl.flock` on the same path - it provides no
  protection against a holder that bypasses `wave_slots.py` entirely (there
  is none today) or against two hosts sharing a slots directory over NFS
  (flock semantics over NFS are unreliable on some kernels/mounts). Every
  wave path in this pack runs on one host by design, so this is accepted,
  not mitigated further here.
- **`release`'s new required `owner_pid` parameter is a breaking change**:
  any caller of `wave_slots.release` outside this pack's own call sites
  would need updating. The one production call site is
  `cli/loop.py::_launch` (lines 418-441): `slot = wave_slots.acquire(Path(slots_dir),
  self._int("_AUTOPILOT_REVIEW_SLOTS", 3), self.loop_pid, ...)` at line 421,
  released at line 441 inside a `finally:` as `wave_slots.release(slot)` -
  that becomes `wave_slots.release(slot, self.loop_pid)`, reusing
  `self.loop_pid`, already in scope and already the pid passed to `acquire`
  two lines above it. (`wave_run.py` has no `wave_slots` reference at all;
  `references/waves.md`'s "wrapped in a `wave_slots.acquire`/`release` pair"
  describes the review spawn's behavior, which this `_launch` call
  implements, not a literal location in `wave_run.py`.) The planner should
  re-run `rg -n "wave_slots.release|from cli.wave_slots import" cli/
  skills/` against HEAD at plan time to confirm no new caller landed
  between design and planning.
- **00225b's hold-then-commit surprises an operator** (also named in the
  PRD's Risks): the commit message and the wave report must name every PRD
  moved, which the design above provides (commit body lists each moved
  basename); the PRD additionally asks that "the wave report" name them -
  this design does not yet thread the held-backlog list into
  `wave_assemble.summary`'s report; the planner should treat surfacing
  those names in the wave's `*-wave.md` report (not just the git commit
  message) as an explicit task, since the PRD's own Outputs bullet for
  00225 says only "moves ... into prds/hold/ and commits that move," while
  the Risks section's mitigation claim ("the wave report names every PRD
  moved") is a slightly stronger promise this design flags rather than
  silently drops.
- **00226's hand-review check trusts filesystem presence alone**: any file
  named `<stub>.md` dropped into the assembly worktree's `prds/done/` by
  ANY means (not necessarily a genuine hand review) flips the wave to
  `converged`. This matches the PRD's own stated design exactly ("If it is
  [in prds/done/] ... sets the status to converged") and is an operator-
  trusted hand-edit surface analogous to `wave.json` itself being a
  "supported hand-edit surface" per `references/waves.md` - not a new kind
  of trust boundary in this codebase.
- **Likely next changes after this PRD:**
  1. The planner-flagged report-surfacing gap above (naming held-backlog
     PRDs in the wave's markdown report, not just the commit message) is
     the most likely immediate follow-up if an operator finds the
     commit-message-only trail insufficient in practice.
  2. `wave_slots.release`'s signature change ripples to any future caller;
     a follow-up PRD adding a new review-slot consumer must remember the
     `owner_pid` argument - worth a docstring note on `release` itself
     (already included in the Interfaces contract above) to prevent a
     silent `TypeError` at call time, or more defensively, a loud fast-fail
     wrapper in a review if a future diff calls `release(slot)` with one
     argument.
  3. If a future PRD moves wave sessions off a single host (the flock
     limitation above), the whole `wave_slots.py` locking strategy would
     need revisiting - this design does not box that in any harder than
     the status quo already does (the module docstring already states the
     one-host assumption).

## Test strategy outline

- `test_wave_slots.py::test_reclaim_put_back_race_admits_one_holder` - three
  processes (or three threads/fakes simulating the interleave), `count=1`,
  a forced interleave at the rename inside `_discard`'s aside step; asserts
  exactly one holder ends up with the slot. Exercises the `_slot_lock`
  acquired across `_discard`'s whole body (00227).
- `test_wave_slots.py::test_release_never_removes_another_holders_slot` -
  claim a slot as pid A, have pid B's `acquire` reclaim it after A is
  marked dead, then call `release(slot, owner_pid=A)`; asserts the slot
  (now owned by B) survives. Exercises `release`'s new ownership check
  (00227).
- `test_wave_assemble_migrate.py::test_crash_after_save_before_remove_reruns_clean`
  - run `_drain_lane` far enough to reach the point right after the first
  `save()` but before `worktree remove` (a fake `run_git` that raises on
  the `worktree remove` call simulates the crash), assert `wave.json` on
  disk already carries the new `held_prds`/`status`/`batch_id`; then rerun
  `_drain_lane` with a working `run_git` and assert the lane ends
  assembled, exit 0, and the report still names non-roster PRDs correctly.
  Exercises both new `save()` calls (00222).
- `test_wave_cli_refusals.py::test_assemble_os_error_is_one_line_exit_one` -
  a fake `wave_assemble.assemble` (or a fake `run_git`) that raises
  `OSError`, dispatched through `wave_cli.run(args, repo, wave_path)` with
  `args.verb == "assemble"`; asserts stdout/stderr carries exactly one
  `autopilot: ...` line and the return value is `1`, no traceback.
  Exercises the `OSError` addition to `_guarded`'s catch tuple (00222).
- `test_wave_review.py::test_store_churn_in_the_assembly_worktree_does_not_refuse`
  - seed an assembly worktree, commit a store-only change there (simulating
  a nested loop's own `record_store` write) left uncommitted, call `land`'s
  cleanup path; asserts it does NOT raise, where today's raw `git status`
  check would. Exercises `_land_cleanup`'s `foreign_dirty` swap (00225a).
- `test_wave_review.py::test_seeded_backlog_prds_are_held_before_the_nested_loop`
  - seed an assembly worktree whose inherited `prds/backlog/` holds one or
  more `.md` files, call `seed_state`, assert those files are now under
  `prds/hold/` and the assembly branch carries a commit naming them, before
  any nested loop spawn is simulated. Exercises `_hold_seeded_backlog`
  (00225b).
- `test_wave_review_land.py::test_hand_reviewed_stub_in_done_lands` - a wave
  at status `review_failed` whose assembly worktree's `prds/done/` already
  holds the stub (simulating the operator's hand move), call `land`;
  asserts it proceeds through the normal `converged` path (fast-forward,
  migrate, exit 0) rather than returning 4. Exercises `_land_review_failed`'s
  new check and `None` return (00226).
- `test_wave_review_land.py::test_review_failed_without_hand_review_still_exits_four`
  - the same `review_failed` wave, but the stub is absent from
  `prds/done/`; asserts `land` still returns 4 and still records the
  summary line, unchanged from today. Regression guard for 00226's
  else-branch.
- `test_loop_record_store.py::test_review_once_skips_the_store_in_a_wave_lane`
  - a `Loop` instance whose `self.env` sets `_AUTOPILOT_REVIEW_SLOTS_DIR`
  (so `in_wave_lane` reads true), drive `_record_review_once_store`, assert
  `store_tree.record_store` is never called. Exercises the new guard
  (00239); mirrors the existing sibling tests for `loop.py:611` and
  `loop_act.py:218`'s guards, if present, as the pattern to copy.
- `test_wave_docs.py::test_every_wave_test_file_is_listed` - as specified
  in Interfaces & contracts: compares the on-disk `test_wave*.py` glob
  (minus the named `test_loop_slots.py` exception) against `_WAVE_TEST_FILES`.
  Fail-first: red today (file glob already includes
  `test_wave_assemble_summary.py`, which `_WAVE_TEST_FILES` is missing
  before this PRD's own 00221 edit lands) - this test and the
  `_WAVE_TEST_FILES`/`release-checks` additions should land in the same
  commit per the PRD's own fail-first acceptance note.

## Review log

- non-blocker: docstring rationale for `test_loop_slots.py`'s exception
  overstated - `test_wave_docs.py:39-40`'s "plus this one" names only
  `test_wave_docs.py` itself, not `test_loop_slots.py`; fixed by correcting
  the claim in Interfaces & contracts rather than relying on it.
- question: none beyond the fixed items above.
dispatch 1 (claude): cardinal-sin 0, blocker 2, non-blocker 1, question 0

- question: the held-backlog PRD names promised in the PRD's Risks
  mitigation ("the wave report names every PRD moved") are not yet threaded
  into `wave_assemble.summary`'s report, only into the git commit message -
  already recorded in Risks & edge cases as an explicit planner task;
  tracked there, not fixed in this design doc (a report-content change is
  planning-stage work, not a design-contract gap).
dispatch 2 (codex): cardinal-sin 0, blocker 3, non-blocker 0, question 1

- blocker (fixed): the 00221 parity-test section showed two code blocks
  (a naive first cut, then a "corrected" one) back to back, reading as
  conflicting specs; collapsed to one contract.
- blocker (closed with evidence, no behavior change needed): dispatch 3
  flagged `foreign_dirty`'s store exemption as unverified; `store_tree.py`'s
  actual body (`if path.startswith(roots): continue` against
  `STORE_PREFIXES`) was already read and quoted earlier in this review
  process (see the Reuse inventory and this section's own citations); the
  Interfaces & contracts 00225a entry now quotes that exact control-flow
  line directly rather than relying on the module docstring, closing the
  evidence gap the finding correctly named even though the design's
  original conclusion was already correct.
- blocker (closed with evidence, no behavior change needed): dispatch 3
  flagged `_land_review_failed`'s new lock-scoped save as a possible
  concurrent-overwrite gap; verified against `land`/`_land_converged`'s
  own existing code (lines 516-517, 457-461), which already locks only
  around individual load/save calls, not the whole verb body - the new
  code matches an existing, pre-existing-scope pattern rather than
  introducing a new one; a design doc for this PRD is not the place to
  redesign wave.json's locking granularity, so this is recorded as
  accepted-as-matching-existing-pattern, not fixed by a behavior change.
dispatch 3 (codex): cardinal-sin 0, blocker 3, non-blocker 0, question 0
