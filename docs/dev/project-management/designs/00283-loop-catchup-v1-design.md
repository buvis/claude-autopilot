# Design: 00283-loop-catchup-v1

## Architecture fit

Two independent slices inside `skills/run-autopilot/`:

- **Loop commit identity** lands in `cli/loop.py`'s `Loop` class — the only
  place that spawns a headless session and the only place that makes "the
  loop's own" store commits (`store_tree`).
- **Catchup decision** lands in `cli/enter.py`'s `_catchup` helper (already
  the sole decision point `enter()` calls — see `Loop._launch` → `enter.enter`
  → `_catchup`) plus a new git-log read in `cli/enter_io.py`, which already
  holds `enter()`'s other side-effecting reads (`git_head_sha`,
  `record_resume_row`).
- **Batch-scoped catchup probes** land as a new sibling module
  `cli/catchup_probe.py` (same shape as `cli/wave_slots.py` or
  `cli/custody.py` — a standalone verb module registered in `__main__.py`),
  reusing `cli/statectl.py`'s `mutate` for the state write and
  `cli/state.py`'s load/save, exactly like every other verb.

No new layers. All three pieces sit beside code that already owns the same
responsibility (spawn env, Phase 0 decisions, verb dispatch).

## Module placement

New files:

- `skills/run-autopilot/cli/catchup_probe.py` — the probe.
- `skills/run-autopilot/cli/test_catchup_probe.py` — its tests.

Edited files:

- `skills/run-autopilot/cli/loop.py` — add `loop_committer()` and the
  `GIT_COMMITTER_NAME` stamp in `Loop._launch`.
- `skills/run-autopilot/cli/enter_io.py` — add `commits_all_loop()`.
- `skills/run-autopilot/cli/enter.py` — add the `loop_only` keyword to
  `enter()`, thread it into `_catchup`, rewrite the force/moved-HEAD branches.
- `skills/run-autopilot/cli/enter_decisions.py` or `cli/test_enter.py` — the
  PRD names `test_enter_decisions.py`; no such file exists today (verified:
  `rg -n "class.*Decision|_catchup" cli/test_enter.py` — the force/moved-HEAD
  cases live in `cli/test_enter.py` at lines 605-620 per the PRD's own
  premise). Per the PRD's own Phase-1 task premise ("the existing force cases
  live in `test_enter.py`... re-check before editing"), the new tests join
  `cli/test_enter.py` rather than a new file — the PRD's module-placement
  table names `test_enter_decisions.py` aspirationally but its own task text
  points at the real file. Using the real file avoids a split that contract
  thrashes with the premise check in Phase 1.
- `skills/run-autopilot/cli/__main__.py` — register the `catchup-probe`
  subcommand.
- `skills/run-autopilot/references/phase-build.md` — Phase 1 prose: the
  loop-only rule, and the probe-then-catchup sequencing.
- `skills/run-autopilot/references/state-schema.md` — `catchup_probe` row.
- `dev/bin/release-checks` — `[checks] enter` block gets
  `test_catchup_probe.py`.
- `CHANGELOG.md` — `[Unreleased]` Added/Changed entries.

## Interfaces & contracts

### `cli/enter_io.py`

```python
def loop_committer(batch_id: str | None) -> str:
    """f"autopilot-loop/{batch_id or 'no-batch'}" """
```

Module-level function, defined in `enter_io.py` rather than `loop.py` (the
PRD's own prose names `cli/loop.py`, but `loop.py` already imports
`enter.enter` as `Loop.__init__`'s `enter_fn` default, and `enter.py` needs
this same function for `_catchup` — see Risks for the circular-import
reasoning). `loop.py` imports it (`from cli import enter_io`, a new but
one-directional dependency: `enter_io.py` imports nothing from `loop.py`),
and `enter.py` imports it the same way it already imports `enter_io`'s other
helpers (`git_head_sha`, `record_resume_row`).

### `cli/loop.py`

In `Loop._launch`, before the `self._spawn(...)` call, read the batch id from
state and stamp it:

```python
def _launch(self, plan: routing.Route, ap_dir: Path, phase: str) -> float:
    state = _load_json(ap_dir / "state.json")
    batch_id = (state.get("batch") or {}).get("id") if isinstance(state, dict) else None
    self.env["GIT_COMMITTER_NAME"] = enter_io.loop_committer(batch_id)
    os.environ["GIT_COMMITTER_NAME"] = self.env["GIT_COMMITTER_NAME"]
    ...  # existing slot-acquire / spawn / slot-release unchanged
```

`_load_json` is the helper already used by `_run_once` (module-level in
`loop.py`); reuse it rather than adding a second JSON reader. A missing or
unreadable `state.json` makes `state` a non-dict or `{}` — `batch_id` reads
`None`, `loop_committer(None)` returns `"autopilot-loop/no-batch"`, no
exception. `os.environ` is set because the loop process itself may run git
commands (store commits) outside a spawned child; `self.env` is what children
inherit. `# ponytail: process-wide env, the loop process commits nothing
else.` `_launch` is the sole place that sets this key and runs once per
spawn, always from a fresh state read, so a later call with a different
`batch_id` overwrites rather than leaks a stale value — no reset path is
needed because every call is already a fresh assignment, not an accumulation.

### `cli/enter_io.py`

```python
def commits_all_loop(root: Path, sha: str, name: str) -> bool:
    """True iff every commit in `sha..HEAD` (inclusive of an empty range)
    has committer name `name`. False on any git failure or unknown sha."""
```

Implementation:

```python
def commits_all_loop(root: Path, sha: str, name: str) -> bool:
    try:
        proc = subprocess.run(
            ["git", "-C", str(root), "log", "--format=%cn", f"{sha}..HEAD"],
            capture_output=True, text=True, timeout=10,
            encoding="utf-8", errors="strict",
        )
    except (OSError, subprocess.SubprocessError, UnicodeDecodeError):
        return False
    if proc.returncode != 0:
        return False
    lines = [ln for ln in proc.stdout.splitlines() if ln]
    return all(ln == name for ln in lines)
```

An empty range (`lines == []`) makes `all(...)` vacuously `True` — matches
the PRD's "including an empty range" requirement (HEAD already at `sha`).
An unknown `sha` makes `git log` exit non-zero (ambiguous argument) → `False`
→ caller reads "full", matching the PRD's error case. `encoding="utf-8",
errors="strict"` pins the decode to UTF-8 regardless of process locale (an
earlier revision used `errors="replace"`, but a `name` that itself contains
the replacement character `U+FFFD` would have let a corrupted line decode
to a false match — an unstated invariant on `name`'s shape, not a real
guarantee); explicitly catching `UnicodeDecodeError` alongside
`OSError`/`SubprocessError` keeps the same fail-closed contract — any
decode failure returns `False` → "full", exactly like every other fault
case, rather than propagating an uncaught exception out of `_catchup` and
crashing `enter()`.

### `cli/enter.py`

`enter()` gains one new keyword, defaulted so every existing caller (and
every existing test that doesn't pass it) is unaffected:

```python
def enter(
    state_path: Path,
    *,
    prds_dir: Path,
    autopilot_dir: Path,
    prd_arg: str | None,
    in_loop: bool,
    now: Callable[[], str] = _utc_now,
    git_head: Callable[[Path], str | None] = enter_io.git_head_sha,
    record_resume_row: Callable[[str, str, Path], None] = enter_io.record_resume_row,
    loop_only: Callable[[Path, str, str], bool] = enter_io.commits_all_loop,
) -> dict:
```

`_catchup` gains the same keyword and a `batch_id` read, and is rewritten:

```python
def _catchup(
    current: dict, state_path: Path, autopilot_dir: Path,
    now: Callable[[], str], git_head: Callable[[Path], str | None],
    loop_only: Callable[[Path, str, str], bool] = enter_io.commits_all_loop,
) -> str:
    """Step 11: skip, delta (loop-only commits, or batch cache fresh and
    HEAD unmoved), or full."""
    mode = current.get("catchup_mode")
    if mode in ("skip", "skipped"):
        if mode == "skip":
            _mutate(
                state_path, "catchup_mode",
                lambda data: data.update(catchup_mode="skipped"),
            )
        return "skip"
    batch = current["batch"]
    tasks = current.get("tasks")
    root = custody.project_root(autopilot_dir)
    name = enter_io.loop_committer(batch.get("id"))
    if mode == "force" and not (isinstance(tasks, list) and tasks):
        sha = batch.get("catchup_head_sha")
        if sha and loop_only(root, sha, name):
            return "delta"
        return "full"
    if "catchup_completed_at" not in batch or not _fresh(batch["catchup_completed_at"], now()):
        return "full"
    head = git_head(root)
    sha = batch.get("catchup_head_sha")
    if head is None or sha != head:
        if sha and head is not None and loop_only(root, sha, name):
            return "delta"
        return "full"
    return "delta"
```

`enter_io.loop_committer` needs no new import — `enter.py` already imports
`enter_io` for `git_head_sha`/`record_resume_row`/`commits_all_loop`.

Call site (`enter()`, line ~375 today) passes the new keyword through:

```python
out["catchup"] = _catchup(current, state_path, autopilot_dir, now, git_head, loop_only)
```

New symbols and tests, exactly as the PRD's module table names them:
`enter_io.commits_all_loop`, `enter.loop_only` (keyword), plus
`test_force_is_delta_when_all_commits_are_loop_commits`,
`test_force_is_full_when_one_commit_is_not`,
`test_force_is_full_on_git_failure`,
`test_resume_is_delta_when_head_moved_by_loop_commits_only`,
`test_resume_is_full_when_head_moved_by_a_foreign_commit` — all added to
`cli/test_enter.py` (see Module placement for why, not a new
`test_enter_decisions.py`).

### `cli/catchup_probe.py`

```python
def probe(
    state_path: Path,
    *,
    run: Callable[..., subprocess.CompletedProcess] = subprocess.run,
    which: Callable[[str], str | None] = shutil.which,
    now: Callable[[], str] = _utc_now,
) -> dict:
    """Returns {"skip": [...]}. Writes state.catchup_probe through
    statectl.mutate unless the batch's existing probe already covers this
    batch.id."""
```

Behavior:

0. `autopilot_dir = state_path.parent` and `root = custody.project_root(autopilot_dir)`
   — the first two lines of `probe()`'s body, made explicit here rather than
   left to be inferred by analogy to `__main__.py`'s other subcommands.
1. Load `state.json` (plain read, not `statectl.mutate`, to decide whether a
   write is even needed — mirrors the `codex_probe` lazy-reset idiom cited
   by the PRD, `skills/work/references/codex-implementor.md:40-80`).
2. `batch_id = (state.get("batch") or {}).get("id") or "no-batch"`.
3. If `state.get("catchup_probe", {}).get("batch_id") == batch_id`: reuse the
   stored `gh`/`engram` verdicts, run neither binary.
4. Else probe fresh:
   - `gh`: `which("gh") is None` → `"absent"`; else
     `run(["gh", "auth", "status"], capture_output=True, text=True,
     timeout=15, cwd=<project_root>)` — exit 0 → `"ok"`; any other exit or a
     `TimeoutExpired`/`OSError` → `"unauthenticated"` (per the PRD: "any
     other result"), **except** a timeout, which the PRD separately pins to
     `"absent"` — so: `TimeoutExpired` → `"absent"`; non-timeout
     `OSError`/non-zero exit → `"unauthenticated"`.
   - `engram`: `which("engram") is None` → `"absent"`; else
     `run(["engram", "status", "--scope", "repo"], capture_output=True,
     text=True, timeout=15, cwd=<project_root>)` — stderr containing
     `"not inside a registered repo"` → `"unregistered"`; `TimeoutExpired` →
     `"absent"`; anything else (including a nonzero exit for stale rows) →
     `"ok"`.
   - Write `state.catchup_probe = {"batch_id": batch_id, "gh": <verdict>,
     "engram": <verdict>, "checked_at": now()}` via `statectl.mutate`.
5. Return `{"skip": [s for s in (("github-state" if gh != "ok" else None),
   ("engram" if engram != "ok" else None)) if s]}`.
6. `main(argv)` prints that dict as one JSON line to stdout; registered as
   `catchup-probe --state <path>` in `__main__.py`, following the existing
   subcommand-registration pattern (each verb module exports `main(argv)`,
   `__main__.py` dispatches by `sys.argv[1]`).

`project_root` reuses `custody.project_root(autopilot_dir)` — already the
one function every other verb in this pack uses to resolve "the directory
holding `docs/dev/project-management`"; `--state <path>`'s parent chain
yields `autopilot_dir` the same way `__main__.py`'s other subcommands derive
it (`state_path.parent` is `.../autopilot/`).

New symbols: `catchup_probe.py`, `test_catchup_probe.py`, `probe`,
`catchup-probe` (subcommand name), `state.catchup_probe`, `"unauthenticated"`
(the new, only-here-used verdict string), plus the PRD's named tests
`test_probe_records_unauthenticated_then_reuses_within_batch`,
`test_new_batch_reprobes`, `test_engram_unregistered_from_stderr`.

### `references/phase-build.md` (Phase 1 prose, no code)

Replace the "Batch cache check" condition text to state: condition 1 for
`catchup: force` reads delta when every commit since `catchup_head_sha` has
committer `autopilot-loop/<batch.id>`; the three-condition delta test for
`catchup: run` gets a fourth escape clause: a moved-HEAD that failed
condition 3 still reads delta when every commit past `catchup_head_sha` is
loop-committed. Add, directly above the existing "If any condition fails →
full catchup" line:

> Before invoking `/git-ferry:catchup` on the full-catchup path, run
> `autopilot catchup-probe` (one Bash call). Its `skip` list names which of
> `github-state.sh`/the `gh` commands, and `engram`, to omit this run — pass
> that list to `/git-ferry:catchup` as "do not run `github-state.sh` or any
> `gh` command" / "do not run any `engram` command" per entry. Write one gap
> line per skipped step in the capsule's relevant section (GitHub State /
> Related context), same as today's manual skip-on-failure handling, just
> decided before the attempt instead of after a failed one.

### `references/state-schema.md`

New row beside `batch.catchup_head_sha` (same table, batch-scoped section):

```
| `catchup_probe` | object? | `{"batch_id": <string>, "gh": "ok"|"unauthenticated"|"absent", "engram": "ok"|"unregistered"|"absent", "checked_at": <ISO UTC>}` — written by `autopilot catchup-probe`, once per `batch.id`; a stale `batch_id` (different from the current batch) means the next call reprobes. Not reset by the per-PRD reset (`cli/records.PER_PRD_RESET_FIELDS` does not list it) — it is batch-scoped, like `batch.catchup_head_sha`. |
```

## Data flow

**Loop commit identity**: `Loop._launch` reads `state.json` → derives
`batch_id` → sets `self.env["GIT_COMMITTER_NAME"]` and
`os.environ["GIT_COMMITTER_NAME"]` → `self._spawn(..., env=self.env, ...)`
passes the env to the child `claude -p` process → any git commit that
process makes (task commits, loop-record commits) carries the stamped
committer name. The loop process's own direct commits (state-record commits
outside a spawned session, if any exist today) pick it up via the
`os.environ` write.

**Catchup decision**: `enter()` → `_catchup(current, ...)` reads
`state.batch.id`, `state.batch.catchup_head_sha`, `state.catchup_mode`,
`state.tasks` → calls `loop_committer(batch_id)` to build the expected name
→ calls `loop_only(root, sha, name)` (= `enter_io.commits_all_loop`) which
shells to `git log --format=%cn <sha>..HEAD` → every line matches the name →
`"delta"`; any mismatch or git failure → `"full"`. The verdict flows back
through `enter()`'s returned dict to `references/phase-build.md`'s "Enter in
one call" step, which branches on it exactly as today (no change to the
branch-handling prose beyond the condition text).

**Catchup probe**: `autopilot catchup-probe --state <path>` → `probe()`
reads `state.json` (plain read) → compares `catchup_probe.batch_id` to the
current `batch.id` → on mismatch or absence, shells to `gh auth status` and
`engram status --scope repo` from the project root → writes verdicts via
`statectl.mutate` → prints `{"skip": [...]}` to stdout → the calling session
(Phase 1 prose) reads that line and passes the named skips into
`/git-ferry:catchup`'s invocation.

## Reuse inventory

- `cli/custody.project_root(autopilot_dir)` — already resolves the project
  root from the autopilot dir; reused by `commits_all_loop` and `probe`
  instead of re-deriving it. (`rg -n "def project_root" skills/run-autopilot/cli/custody.py`
  confirms it exists and is imported into `enter.py` already.)
- `cli/enter_io.py`'s existing `git_head_sha` — same subprocess-timeout-catch
  shape (`capture_output=True, text=True, timeout=10`, catch
  `OSError, subprocess.SubprocessError`, check `returncode`); `commits_all_loop`
  copies this exact idiom rather than inventing a new one. Greps tried:
  `rg -n "subprocess.run" skills/run-autopilot/cli/enter_io.py` (hit:
  `git_head_sha`), `rg -n "def git_head_sha|def record_resume_row" skills/run-autopilot/cli/enter_io.py`.
- `cli/statectl.py`'s `mutate` — the sole `state.json` writer every verb uses;
  `catchup_probe.py` reuses it rather than writing JSON directly. Greps
  tried: `rg -n "statectl.mutate|statectl import" skills/run-autopilot/cli/enter.py`
  (multiple hits, e.g. the `catchup_mode` → `"skipped"` write at `_catchup`'s
  first branch — copied verbatim as the pattern for `catchup_probe`'s write).
- `skills/work/references/codex-implementor.md:40-80`'s `codex_probe`
  lazy-reset idiom — the PRD names it directly as the pattern to follow
  (probe once per scope key, reuse while the key matches); `catchup_probe.py`
  mirrors its "check stored key, reprobe only on mismatch" shape rather than
  introducing a different caching convention. Confirmed present: `rg -n "codex_probe"
  skills/work/references/codex-implementor.md`.
- `cli/loop.py`'s `_load_json` (used by `_run_once`) — reused by `_launch`
  instead of adding a second ad-hoc JSON reader. Greps tried: `rg -n "_load_json"
  skills/run-autopilot/cli/loop.py` (hit: module-level function, one existing
  call site).
- `cli/__main__.py`'s subcommand dispatch table — `catchup-probe` registers
  exactly like `custody list`/`custody resolve`/`ensure-store`/`select`, no
  new dispatch mechanism. Greps tried: `rg -n "def main|SUBCOMMANDS|argv\[1\]"
  skills/run-autopilot/cli/__main__.py`.

Nothing found for "env stamping before spawn" as an existing helper —
`Loop._launch` is the first and only place a committer identity is set;
greps tried: `rg -n "COMMITTER|GIT_AUTHOR" skills/run-autopilot/cli/*.py`
(no hits before this change).

## Alternatives considered

1. **Chosen**: commit-range-scan (`git log --format=%cn <sha>..HEAD`),
   driven by a committer-name stamp the loop sets on its own spawned
   sessions. Smallest correctness-preserving option that needs no new
   persistent bookkeeping beyond the name itself — git already records
   committer identity on every commit, so the check is free to compute from
   data that already exists.
2. **Rejected — commit count/shape heuristic** (e.g. "every commit message
   starts with `chore(autopilot):`"): cheaper (no `git log --format=%cn`
   needed, could reuse `git log --oneline`), but fragile — a human fixing a
   typo in a `chore(autopilot):`-prefixed commit message would misclassify
   as loop-only, and a loop commit that happens to get a different prefix
   (unlikely today, not guaranteed forever) would misclassify the other way.
   Message-based detection is explicitly the thing the PRD's own Risks
   section rules out ("Message prefixes are never used").
3. **Smallest-diff alternative — stamp committer but skip the range-scan,
   trust `catchup_head_sha == HEAD` check alone, and only use the committer
   stamp as an audit trail**: this is strictly smaller (no `enter_io`
   change, no `_catchup` rewrite) but does not solve the stated problem — the
   PRD's whole point is that HEAD moves on every loop commit, so an
   equality-only check never reaches delta once any commit has landed.
   Rejected because it does not meet the Success Metrics (the four
   `test_*_delta_when_*`/`test_*_full_when_*` tests require the range-scan
   logic to exist).
4. **Rejected — separate persistent cache file for probe verdicts** (e.g.
   `docs/dev/project-management/autopilot/catchup-probe.json`) instead of a
   `state.json` field: `state.json` already carries every other batch-scoped
   field (`batch.catchup_head_sha`, `batch.catchup_completed_at`) and already
   has the per-PRD-reset exclusion machinery (`PER_PRD_RESET_FIELDS`) that
   makes a field batch-scoped "for free" by omission. A second file would
   need its own read/write/cleanup/retention rules for no benefit.

## Risks & edge cases

- **Circular import, resolved by placement**: `cli/loop.py` already imports
  `cli/enter.py` for `enter.enter` (the `enter_fn=enter.enter` default in
  `Loop.__init__`), so a naive `loop_committer` defined in `loop.py` and
  imported back into `enter.py` would cycle (verified:
  `rg -n "^from cli import|^import cli" skills/run-autopilot/cli/loop.py`
  and the same on `enter.py`). Placing `loop_committer` in `cli/enter_io.py`
  instead — which `enter.py` already imports, and which imports nothing from
  `loop.py` — avoids the cycle structurally: `loop.py` adds one new,
  one-directional `from cli import enter_io`. This departs from the PRD's
  literal "`loop_committer` in `cli/loop.py`" line for a structural reason
  the PRD text doesn't address; the planner should set task 1's file target
  to `cli/enter_io.py` and its acceptance import path to
  `from cli.enter_io import loop_committer`.
- **Loop's own direct store commits**: `store_tree`-related commits the loop
  process itself makes (not via a spawned session) need `os.environ` set,
  not just `self.env` — confirmed in the Interfaces section above; a
  mitigation already designed in, not an open risk.
- **Next change after this PRD — PRD 00284 (loop launch context)**: both
  PRDs touch `Loop._launch`/`Loop._launch_phase`. This design's edit is
  additive (two new lines before the existing spawn call) and does not
  rename or restructure `_launch`'s signature, so it should not conflict;
  flagged for the planner to re-check `_launch`'s diff when 00284 starts.
- **Next change — a probe verdict going stale mid-batch** (the PRD's own
  Risk: someone runs `gh auth login` mid-batch): the PRD's own fix is
  `statectl del catchup_probe`, an operator action, not something this
  design needs to automate. No code change implied; noted so the planner
  doesn't invent an auto-expiry feature beyond scope.
- **Boxing in a future change**: `commits_all_loop`'s `False`-on-any-failure
  default is deliberately conservative (full catchup) — a future caller that
  wants a different default for a different fault class would need its own
  keyword, not a change to this function's default. This is intentional
  boxing-in: the PRD's Risks section explicitly wants faults to cost full
  catchup, never skip it.

## Test strategy outline

- **`test_loop.py -k committer`**: `ScriptedSpawn` fixture asserts
  `env["GIT_COMMITTER_NAME"] == f"autopilot-loop/{batch_id}"` when a
  `state.json` with `batch.id` is present before `_launch`; a fallback case
  with no `batch` key (or no `state.json`) asserts `"autopilot-loop/no-batch"`.
  A temp-repo integration case commits with the stamped env and reads it back
  via `git log --format=%cn`.
- **`cli/test_enter.py`** (not a new file — see Module placement): the five
  named tests from the PRD, built on temp repos with controlled committer
  names per commit (`git commit --author`/`GIT_COMMITTER_NAME` env per call),
  plus the existing force/moved-HEAD cases re-run unchanged to confirm no
  regression (their fake `git_head`/default `loop_only` still fails closed).
  Fixtures set `GIT_AUTHOR_NAME`/`GIT_AUTHOR_EMAIL` explicitly in the
  commit env alongside `GIT_COMMITTER_NAME` (git refuses to commit with no
  resolvable author identity, and this sandbox has no guaranteed ambient
  `user.name`/`user.email`) — do not rely on global/system git config.
  One case uses a non-UTF-8 committer name (e.g. a raw latin-1 byte via
  `git -c i18n.commitEncoding=...` or a crafted `GIT_COMMITTER_NAME`) and
  asserts `commits_all_loop` returns `False` (the `errors="strict"` +
  `UnicodeDecodeError` fail-closed path), not a false match.
- **`cli/test_catchup_probe.py`**: stub `which`/`run` callables (dependency
  injection matches `probe`'s signature above) for `gh` absent/ok/
  unauthenticated/timeout, and `engram` absent/ok/unregistered(stderr
  match)/timeout; `test_probe_records_unauthenticated_then_reuses_within_batch`
  calls `probe` twice with the same `batch.id` and asserts the stub `run` is
  invoked once; `test_new_batch_reprobes` changes `batch.id` between calls
  and asserts a second probe runs.
- **`test_enter_prose.py` / `test_doc_contract.py`** (PRD-named, Phase 2):
  `rg` assertions that `phase-build.md` mentions `catchup-probe` and
  `state-schema.md` mentions `catchup_probe`, matching the PRD's own
  Acceptance lines verbatim.

## Review log

- non-blocker (dispatch 1): the probe's engram verdict description buckets
  any non-timeout failure (including a real `OSError`, e.g. a present-but-
  non-executable binary) into the catch-all `"ok"` branch alongside stale-
  rows nonzero exits, so a genuine engram failure could misreport as `ok`.
  Not fixed now — the planner should make `probe`'s engram branch bucket a
  non-timeout `OSError`/`SubprocessError` the same explicit way the gh
  branch separates timeout from other failures, rather than falling through
  to the `"ok"` catch-all.
- question (dispatch 1): the PRD's own Phase 1 acceptance command names
  `test_enter_decisions.py -k "force or head_moved"`, but this design puts
  the five new tests in the existing `cli/test_enter.py` instead (Module
  placement). Unresolved: whether `/autopilot:plan-tasks` silently
  substitutes the file path in the acceptance command, or whether the PRD
  text itself should be corrected first. Left to planning to decide; this
  design's own Acceptance-pointing prose already uses `cli/test_enter.py`.
dispatch 1 (claude): cardinal-sin 0, blocker 1, non-blocker 2, question 1
- non-blocker (dispatch 2): `commits_all_loop` treats a `catchup_head_sha`
  that resolves but is not an ancestor of HEAD (post-rebase/force-push/reset)
  as a vacuous-True empty range rather than the "unknown sha" failure case,
  so a rewritten-history state could misread as loop-only delta. This is a
  pre-existing class of risk shared with today's plain equality check, not a
  regression this PRD introduces; accepted as-is rather than adding a second
  `git merge-base --is-ancestor` call, but called out explicitly here rather
  than left silent.
- non-blocker (dispatch 2): the gh branch's "non-timeout OSError/non-zero
  exit → unauthenticated" bucketing has the same shape as the already-noted
  engram bucketing gap (dispatch 1) — a non-timeout `OSError` (binary
  vanished/non-executable after `which` succeeded) means gh never ran, which
  reads closer to `absent` than `unauthenticated`. Not fixed now; the planner
  should apply the same explicit-bucketing fix to both branches together
  when addressing dispatch 1's engram finding, so one class of bug isn't
  half-fixed.
- non-blocker (dispatch 2): the test strategy's temp-repo commit fixtures
  name only `GIT_COMMITTER_NAME` per call; git refuses to commit with no
  resolvable author identity, so a sandbox with no ambient
  `user.name`/`user.email` could make these tests flaky. Reflected directly
  in the Test strategy outline above (`GIT_AUTHOR_NAME`/`GIT_AUTHOR_EMAIL`
  set explicitly alongside `GIT_COMMITTER_NAME`) rather than left as a
  standalone log entry only, since it is a one-line fixture clarification
  with no design-contract impact.
dispatch 2 (claude-fallback): cardinal-sin 0, blocker 1, non-blocker 3, question 1
dispatch 3 (codex): cardinal-sin 0, blocker 1, non-blocker 0, question 0
