# Design: Trust only real gate runs

## Architecture fit

`skills/run-autopilot/cli/verification.py` is already the sole module that
knows how to run the gate and read/reuse `last-verification.json`
(`RECORD_REL = docs/dev/project-management/autopilot/last-verification.json`,
`run_gate`/`reuse_verdict`). This PRD does not add a new layer: it closes the
one gap in that module (nothing stops `run_gate` from stamping a dirty tree)
and removes the one place outside it that still writes the record by hand
(`skills/work/references/final-verification.md` § Recorded verification
result, prose only — step 7 already runs the suite itself and then
hand-writes the JSON with the Write tool). The new `autopilot verify` CLI verb
sits beside the other review verbs in `cli/__main__.py`'s `_SUBCOMMANDS`
registry (`review-stage`, `review-close`, …) and is the one path every
session-facing skill (`work/SKILL.md` step 7, `review-work-completion/SKILL.md`
step 3/6, `lane-solo.md` § 3) now calls instead of running the suite directly
and writing the file themselves.

`cli/state.py`'s `transaction()` is the locked read-modify-write boundary; the
no-change sentinel is a one-line addition to its contract (skip the write when
`fn` signals nothing changed), not a new boundary. `statectl.mutate()` already
separates "what changed" (`apply`) from "how it's persisted" (`transaction`),
so the sentinel passes straight through both layers with no new control flow
at either call site except `review_close._close_mutator`'s existing
already-applied branch.

## Module placement

- `skills/run-autopilot/cli/verification.py` — edits: `normalize_command`
  (new function), `_dirty_outside_store` (new function), `_ancestor_and_clean`
  (replace the `git log --name-only` call), `run_gate` (dirty-tree checks,
  `log_path`, `recorded`/`dirty` result keys), `_record_shape_ok`/
  `_write_record` (normalize before compare/write), module docstring.
- `skills/run-autopilot/cli/__main__.py` — edit: add the `verify` verb
  (`_add_verify`, `_run_verify`) to `_SUBCOMMANDS` and its docstring, beside
  `review-stage`.
- `skills/run-autopilot/cli/review_stage.py` — edit: `run_gate_line` passes a
  log path and returns `"log"`; Blake's appended prompt sections gain the
  `## Test gate` block.
- `skills/run-autopilot/cli/state.py` — edit: add `NO_CHANGE` sentinel;
  `transaction()` special-cases it.
- `skills/run-autopilot/cli/statectl.py` — edit: one-line edit inside
  `mutate()`'s inner `fn` closure so it returns `state.NO_CHANGE` when
  `apply` does; `mutate`'s external contract (it still returns `outcome`
  verbatim) is unaffected — see Interfaces.
- `skills/run-autopilot/cli/review_close.py` — edit: `_close_mutator`'s
  already-applied branch (`review_close.py:343-345`) returns
  `state.NO_CHANGE` instead of `state`.
- `skills/run-autopilot/cli/rework_groups.py` — edit: one `# ponytail:`
  comment above `_merge_pair` (`rework_groups.py:51`). No behavior change.
- `skills/run-autopilot/cli/test_release_checks_counts.py` — edit: drop the
  two hardcoded counts from the `_REVIEW_VERB_TEST_FILES` comment.
- New test files: `skills/run-autopilot/cli/test_state_no_change.py`,
  `skills/work/scripts/test_gate_record_writer_prose.py`.
- Prose edits (no code): `skills/work/references/final-verification.md`,
  `skills/work/SKILL.md` step 7, `skills/run-autopilot/references/lane-solo.md`
  § 3, `skills/review-work-completion/SKILL.md` step 3/6,
  `skills/review-work-completion/references/agent-invocation.md`,
  `agents/blake.md`.
- `skills/run-autopilot/cli/fixtures/blake-prompt-00244c1.md` — regenerated
  golden fixture (mechanical, from the `review_stage.py` change).
- `dev/bin/release-checks`, `docs/dev/project-management/reviews/00266-…-audit.md`,
  `CHANGELOG.md` — registration/audit/changelog edits, no new modules.

No new files under `cli/` beyond the two test files; everything else is an
edit to a module that already owns the capability it is being asked to
tighten.

## Interfaces & contracts

```python
# verification.py

def normalize_command(command: str) -> str:
    """" ".join(command.split())`, then strip one leading "bash " or "sh ",
    then strip one leading "./". Used before every command comparison and
    before every write, so recorded commands are already normalized.
    Non-str input (a forged/malformed record's `commands[i]["command"]"
    missing or null) must compare as never-matching, never raise: callers
    pass it a `str | None` and it returns `""` for anything that is not a
    `str`, so `_record_shape_ok`'s comparison degrades to `"" ==
    normalize_command(gate_command)` (false, since a real gate command is
    never empty) instead of crashing. This preserves the module's existing
    fail-toward-rerun invariant (module docstring) under hostile input."""

def _dirty_outside_store(repo_root: Path) -> bool:
    """True iff the working tree has any change outside STORE_PREFIX, or the
    git calls themselves fail (non-git cwd, any OSError/non-zero exit counts
    as dirty — fail toward refusing the record). Runs
    `git rev-parse --show-prefix` + `git status --porcelain=1 -z
    --untracked-files=all` and reuses `_iter_porcelain_z_records` and
    `_dirty_path_is_in_store`, exactly as `_ancestor_and_clean` already does."""

def run_gate(
    command: str,
    cwd: Path,
    sha: str,
    cycle: int | None,
    timeout: float = GATE_TIMEOUT_S,
    log_path: Path | None = None,
) -> dict:
    """Unchanged spawn/drain/reap. New: checks `_dirty_outside_store(cwd)`
    before spawning the child AND after `_reap` returns — writes the record
    only when both checks are clean AND a summary line parsed. Streams both
    pipes into `log_path` (when given) in read order, in addition to keeping
    the bounded stdout tail for parsing (`_drain_bounded` grows a sink
    parameter; memory stays bounded exactly as today, only the parse tail is
    retained in memory). Result dict gains two keys:
      "recorded": bool  # True iff `_write_record` ran
      "dirty": bool     # True iff either dirty check tripped
    A dirty-tree refusal is its OWN result shape, distinct from
    `_timed_out_result()`: `{"passed": None, "failed": None, "skipped": None,
    "exit": None, "raw_line": None, "timed_out": False, "recorded": False,
    "dirty": True}` — `timed_out` is explicitly `False` here, never inherited
    from the timeout helper, because `run_gate_line` (below) branches on
    `timed_out` first to build its human-readable Tests line and a dirty
    tree is not a timeout. The real `_timed_out_result()` path is untouched
    and gets `recorded=False, dirty=False` added to its dict for shape
    consistency."""
```

```python
# verification.py — reuse side

def _record_shape_ok(record: dict, gate_command: str) -> bool:
    """Unchanged except the final `all(...)` line compares
    `normalize_command(c.get("command")) == normalize_command(gate_command)`
    — `.get`, not `[...]`, kept exactly as today so a `commands[i]` dict
    missing the key still degrades to `None` (normalized to `""`) rather
    than raising `KeyError`."""

def _ancestor_and_clean(repo_root: Path, sha: str, head_sha: str) -> bool:
    """Unchanged ancestor check and status check. The change list source
    becomes `git diff --name-only --no-renames -z <sha> <head_sha>` split on
    `\0` (replacing the `git log ... --name-only --format=` call, which is
    silent for a merge commit's own resolution edits — `git diff` between the
    two endpoints is not). The status call gains `--untracked-files=all`."""

def _write_record(cwd, command, sha, cycle, result) -> None:
    """Unchanged shape, except `command` is normalized before being stored:
    `normalize_command(command)`."""
```

```python
# state.py

NO_CHANGE = object()  # module-level sentinel, identity-compared only

def transaction(path, fn, *, validator=schema.validate) -> dict:
    """Unchanged lock/read/parse. `fn(current)` may now return `NO_CHANGE`
    instead of the mutated state. When `fn`'s return value `is NO_CHANGE`:
    skip the validator, skip the schema-version stamp, skip both the `.bak`
    write and the atomic replace, and return `json.loads(raw)` — a FRESH
    parse of the pre-transaction `raw` bytes already held in scope (line
    145's `raw, current = read_and_parse(path)`), not `current` itself.
    `current` is unsafe to return as-is because `fn` (via `statectl.mutate`'s
    in-place-mutating `apply`) may have mutated it before deciding nothing
    changed, exactly as `review_close._close_mutator` does when it sets
    `outcome["already"] = True"` before returning the sentinel — re-parsing
    `raw` is the same aliasing defense `transaction` already relies on for
    its `.bak` write (lines 155-160's comment) and costs one extra
    `json.loads` only on the no-change path. Every existing caller whose `fn`
    returns the mutated `current` dict is byte-identical in behavior — the
    `result is NO_CHANGE` check is the only new branch."""
```

```python
# statectl.py

def mutate(state_path: Path, apply: Callable[[Any], Any]) -> Any:
    """No signature change. Its inner `fn` already returns whatever
    `state.transaction` needs: today it always returns `current` (the
    mutated dict). The one-line change: `fn` returns `state.NO_CHANGE` when
    `apply(current)` itself returns `state.NO_CHANGE` (the sentinel recognized
    by identity), else returns `current` as today. `outcome` (and therefore
    `mutate`'s own return value to ITS caller) is unaffected — it is still
    whatever `apply` assigned via its closure, which `_close_mutator` already
    sets (`outcome["already"] = True`) before returning the sentinel."""
```

```python
# review_close.py

def _close_mutator(ctx: dict) -> Callable:
    def _apply(state: dict) -> dict:
        ...
        if identity in state.get("applied_review_batches", []):
            outcome["already"] = True
            return statectl.NO_CHANGE  # was: `return state`
        ...
    return _apply
```
(`statectl.NO_CHANGE` re-exports `state.NO_CHANGE`, matching how `statectl.py`
already re-exports `read_and_parse`/`atomic_write` from `state.py` — see
`statectl.py:67-69`.)

```python
# __main__.py — new verb

# autopilot verify --gate-command CMD [--repo-root PATH] [--cycle N] [--log PATH]
def _run_verify(args) -> int:
    """repo_root defaults to cwd. Resolves HEAD via `git rev-parse HEAD` in
    repo_root — failure (non-git repo, detached-but-unparseable, etc.) exits 2
    before anything else runs. Default log path:
    `docs/dev/tmp/gate-<sha[:7]>.log` (relative to repo_root). Calls
    `verification.run_gate(args.gate_command, repo_root, sha=head,
    cycle=args.cycle, log_path=log_path)`. Prints ONE JSON line: the result
    dict (`passed/failed/skipped/exit/raw_line/timed_out/recorded/dirty`)
    plus `"sha": head` and `"log": str(log_path)`. A pre-spawn dirty tree
    returns `run_gate`'s own dirty-refusal shape (`exit: None, timed_out:
    False, recorded: False, dirty: True` — see `run_gate`'s contract above;
    it is NOT `_timed_out_result()`'s shape, only the same `exit: None`),
    and `_run_verify` maps `exit is None` (dirty OR timed out) to **exit 1**
    either way (never ran = not a pass) — the two causes share an exit code
    but not a result shape, so a caller inspecting `dirty`/`timed_out`
    still tells them apart. Exit 0 only when `result["exit"] == 0 and not
    result["timed_out"]`. Exit 2 is reserved for two causes that both
    precede any dirty-tree check: HEAD cannot be resolved, or the log file
    can't be opened for writing. `run_gate` opens `log_path` itself
    (creating parent dirs first) before its pre-spawn dirty check and
    RAISES the bare `OSError` on failure rather than swallowing it;
    `_run_verify` wraps its one `run_gate(...)` call in `try/except
    OSError` and on that path still prints the one JSON line (`{"sha":
    head, "log": str(log_path), "error": "<str(err)>"}`) before exiting 2 —
    so this failure is never a bare traceback with no output. So "writes no
    record on a dirty tree" and
    "exits 2 outside a git repo" are disjoint tests — a non-git cwd fails
    HEAD resolution before `run_gate` is even called."""
```

```python
# review_stage.py

def run_gate_line(repo_root: Path, gate_command: str, cycle_id: str) -> dict:
    """Unchanged reuse-check-then-run logic. New: passes
    `log_path=repo_root / TMP_REL / f"gate-{cycle_id}.log"` to `run_gate` on
    the run branch (the reuse branch has no log — nothing ran). Result dict
    gains `"log": str(log_path)` on the run branch; omitted (or None) on the
    reuse branch, matching how the reuse branch already has no `"recorded"`/
    `"dirty"` keys to add. **New branch, checked BEFORE the existing
    `timed_out` branch**: when `result["dirty"]` is true, the Tests line
    reads `(gate skipped: working tree dirty outside the store)` instead of
    running the existing timed-out/failed/passed branches — a dirty result
    always has `timed_out=False` (see `run_gate`'s contract above) so without
    this explicit dirty-first check it would fall through to the
    passed/failed branch on `exit=None`, which is also wrong. The
    `timed_out` branch's existing wording and behavior are otherwise
    unchanged."""
```

```python
# agents/blake.md — one new sentence after the existing Bash rules:
"When your run inputs carry a `## Test gate` block, it is this cycle's
full-suite result at HEAD: do not rerun the full suite; a narrow run of one
test file to check a spec claim is fine."
```

## Data flow

1. A work-phase or review-phase session needs the full suite's verdict →
   calls `autopilot verify --gate-command "<cmd>" [--cycle N]` as a single
   Bash call, never shells the command out itself.
2. `_run_verify` resolves HEAD, calls `run_gate`, which:
   a. checks `_dirty_outside_store` — dirty or a git failure → no spawn, no
      record, `recorded=False, dirty=True`.
   b. spawns the command, drains both pipes into the bounded in-memory tail
      AND the log file concurrently, reaps under the deadline.
   c. on timeout → no record (unchanged today), `recorded=False`.
   d. on a clean exit, checks `_dirty_outside_store` again (the run itself
      may have dirtied the tree, e.g. a test writing a stray file) — dirty →
      no record, `recorded=False, dirty=True`.
   e. on both checks clean and a summary line parsed → `_write_record` writes
      `last-verification.json` with the normalized command, `recorded=True`.
3. `_run_verify` prints the JSON line (sha, log path, result) and exits
   0/1/2. The caller reads the log with `rg` if it needs output, never by
   rerunning the gate.
4. A later reuse check (`review-stage`'s `run_gate_line`, or
   `review-work-completion` step 6's reader) calls `reuse_verdict(record,
   repo_root, head_sha, gate_command)`:
   a. `_record_shape_ok` compares `normalize_command` of both commands.
   b. `_ancestor_and_clean` walks `record["sha"]..head_sha` with `git diff
      --name-only --no-renames -z` (catches merge-resolution edits a `git
      log --name-only` would miss) and `git status --porcelain=1 -z
      --untracked-files=all` (catches a product file an untracked-hiding
      repo config would otherwise swallow).
   c. `("reused", record)` only when both hold; `("stale", {})` otherwise.
5. `review_stage.stage()` appends the `## Test gate` block (the cycle's
   Tests line) to Blake's prompt inputs; `agents/blake.md` tells him not to
   rerun the suite when that block is present.
6. `review_close._close_mutator`'s already-applied branch returns
   `statectl.NO_CHANGE` → `statectl.mutate` → `state.transaction` skips the
   `.bak` refresh and the state write entirely, leaving the pre-apply `.bak`
   as the rollback point for the WINNING racer's close.

## Reuse inventory

- `verification._iter_porcelain_z_records` / `_dirty_path_is_in_store` —
  already exist, already decode `git status --porcelain=1 -z` records and
  classify them as store-only or not; `_dirty_outside_store` is a thin
  wrapper that calls the existing status command (with `--untracked-files=all`
  added) and reduces its records with `all(_dirty_path_is_in_store(...))` —
  the same reduction `_ancestor_and_clean` already does, just invoked before
  and after the gate run instead of only at reuse time.
- `verification._drain_bounded` — already drains two pipes with a selector
  under a deadline; the log-file sink is an additional write inside the same
  loop body, no new concurrency primitive.
- `statectl.py:67-69`'s re-export pattern (`read_and_parse = state.read_and_parse`)
  is the template for `statectl.NO_CHANGE = state.NO_CHANGE`.
- `cli/__main__.py`'s existing `_SUBCOMMANDS` registry (grep:
  `rg -n "review-stage|review-close" skills/run-autopilot/cli/__main__.py`)
  — `verify` is registered the same way, no new dispatch mechanism.
- Greps tried for an existing "run the suite and record it" helper outside
  `verification.py`: `rg -n "last-verification|run_gate" skills/` (hits only
  `verification.py`, `review_stage.py`, and the prose files this PRD already
  lists — confirms `final-verification.md`'s hand-write instruction is the
  only other writer, matching the PRD's packet-5 finding) and
  `rg -n "def normalize|normalize_command" skills/run-autopilot/cli/` (no
  hits — nothing to reuse, write new).

## Alternatives considered

1. **Stamp `dirty: true` on a dirty-tree run instead of writing no record**
   (the PRD's own rejected alternative). Smallest diff: `run_gate` always
   writes, adding one field. Rejected: every reader (`reuse_verdict`,
   `review-work-completion/SKILL.md` step 6's prose matcher) would need a new
   branch to treat a present-but-dirty record as stale, and the prose reader
   matches by sha alone today — it would silently reuse a stamped record.
   Writing nothing needs no reader change at all: absence already means
   `stale`. **Chosen: no record.**
2. **Smallest-diff version: only the dirty-tree refusal (packet 4), skip the
   CLI verb and the command-normalizing / diff-vs-log fixes.** This alone
   closes the HIGH-severity forgery gap. Rejected as the full scope because
   packets 5/9/10/6/11 are all symptoms of the same root cause named in the
   PRD title ("trust only real gate runs") — a record with no CLI verb behind
   it is still hand-writable, and a reuse check still blind to merge
   resolutions or untracked files. Shipping only packet 4 would leave `/work`
   step 7's prose instruction ("write `last-verification.json`" ) in place,
   which is the exact instruction packet 5 says must go. **Chosen: the full
   PRD scope** — it is still one Phase 0 foundation layer plus two thin
   integration layers, not a redesign.
3. **A `git diff --raw -z` instead of `--name-only -z` for the tree-to-tree
   change list**, to also get status codes (could special-case renames).
   Rejected: `_ancestor_and_clean` only needs the path set to test against
   `STORE_PREFIX`; `--name-only -z` already gives exactly that with no
   parsing beyond a NUL split, and nothing downstream needs the status code.
   **Chosen: `--name-only -z`**, extra size buys nothing here.

## Risks & edge cases

- **A determined forger can still hand-write the file.** Accepted (PRD Risks,
  packet 5 option 1): this PRD closes the *routine* unaudited path (prose
  telling every session to write it), not a hostile one. No hook added.
- **A project whose `docs/dev/tmp/` is not gitignored** sees its own log file
  and staged review inputs as dirty paths outside the store, so `run_gate`
  records nothing and reuse never fires — fails safe (a rerun), not fails
  open. This pack's own `.gitignore` already covers it.
- **Likely next changes this design should not box in:**
  1. A future reader that wants the dirty-tree reason surfaced in the review
     file (today `recorded=False` is silent beyond "no record exists") — the
     result dict's `dirty` key is already there for a caller to log, so
     nothing here blocks adding a `## Test gate: skipped (dirty tree)` prose
     line later.
  2. Extending `normalize_command` to also fold `python3` vs `python`, or
     quoting differences — the function is a single pure `str -> str`
     transform with one call site on each side (compare, write), so widening
     its rule set later touches no caller.
  3. A per-slot lock replacing the `fcntl.flock` on `state.json.bak` — the
     `NO_CHANGE` sentinel is orthogonal to the lock granularity; it only
     decides whether a WRITE happens once the lock is already held.
- **`NO_CHANGE` blast radius**: every other `transaction`/`mutate` caller
  returns the mutated dict today and continues to; the sentinel only changes
  behavior for a caller that deliberately returns it. Guarded by keeping
  `test_a_changing_transaction_still_refreshes_the_backup` green.
- **Blake's independence** (packet 9b): he no longer runs the full suite
  himself once a `## Test gate` block is present. Accepted by the operator;
  he may still run one narrow test file to check a specific claim.
- **`normalize_command` can equate commands with different behavior**
  (whitespace collapse inside a quoted argument, `bash`/`sh` prefix strip
  conflating interpreters). This is the PRD's OWN specified contract
  (Feature: Command normalizing, packet 10) and its own Risks section
  already accepts it ("unlikely for a gate command; accepted for the reruns
  it saves") — this design doc implements that contract verbatim, it does
  not introduce the risk. Not re-litigated here; carried forward as
  already-accepted.
- **The gate log has no explicit byte cap**, unlike the in-memory parse
  tail (`GATE_OUTPUT_CAP`). It is still not unbounded in the open-ended
  sense: `GATE_TIMEOUT_S` (1800s) bounds every gate run's wall-clock time,
  so a log's size is bounded by 30 minutes of a child process's own output
  rate, the same bound that already governs the rest of `run_gate`'s
  behavior today. The PRD's own Feature: Gate log (packet 9c) specifies
  the log holds "every byte of stdout and stderr" precisely so a session
  never has to rerun the gate to read output it already produced —
  capping the log would reintroduce that rerun. Accepted as-is; the
  deadline is the backstop, not a separate new one.

## Test strategy outline

- `test_verification.py`: command-normalizing reuse/write tests; the
  `git diff` vs `git log` change-list tests (merge resolution, untracked
  product file under `status.showUntrackedFiles=no`, untracked store dir,
  non-ASCII store filename, store-only-below-toplevel and committed-rename
  regression guards); the dirty-tree refusal tests (dirty before spawn,
  dirtied during the run, outside a git repo, dirty-but-inside-store
  tolerated, log streaming) — three existing record-on-a-non-git-tmp_path
  tests move onto the `repo` fixture per the task's premise check.
- `test_state_no_change.py` (new): `transaction` writes neither backup nor
  state on `NO_CHANGE`; `mutate` passes `NO_CHANGE` through and still reports
  `outcome`; a changing transaction still refreshes the backup (regression
  guard); every review-verb test file stays registered (regression guard on
  the `_REVIEW_VERB_TEST_FILES`/`dev/bin/release-checks` listing itself);
  the already-applied `review_close` path keeps the pre-apply `.bak` on a
  simulated race.
- `test_cli_review_verbs.py`: `verify` runs the gate once and writes record +
  log; exits 1 on a red gate; writes no record on a dirty tree; exits 2
  outside a git repo.
- `test_review_stage.py`: Blake's prompt carries the staged Tests line and
  the gate log path; no `## Test gate` block when the context has none;
  `run_gate_line` on a dirty-tree result produces the
  `(gate skipped: working tree dirty outside the store)` Tests line, not
  the timed-out wording; golden fixture regenerated and re-pinned.
- `skills/work/scripts/test_gate_record_writer_prose.py` (new): no prose in
  the four touched files tells a session to write `last-verification.json`
  directly; `final-verification.md`, `lane-solo.md`, and
  `review-work-completion/SKILL.md`'s fallback all route through
  `autopilot verify`; `agent-invocation.md` documents the Blake test-gate
  sentence.
- `test_release_checks_counts.py`: comment no longer hardcodes stale counts.

## Review log

- QUESTION (dispatch 1): the `statectl.mutate()` module-placement bullet
  originally read "no-op" where the Interfaces section describes a real
  one-line edit inside `fn`'s closure — reworded for consistency, no
  behavior change.
dispatch 1 (claude): cardinal-sin 0, blocker 2, non-blocker 1, question 1
dispatch 2: codex unavailable, Claude fallback
- NON-BLOCKER (dispatch 2): the log-open OSError path's exception contract
  was unstated — fixed: `run_gate` opens the log file and raises; `_run_verify`
  catches it and still prints a JSON line before exit 2.
dispatch 2 (claude-fallback): cardinal-sin 0, blocker 1, non-blocker 1, question 1
- Dispatch 3 confirmed the dirty/timed_out fix holds across all three
  contracts (run_gate, run_gate_line, _run_verify).
- CARDINAL-SIN (dispatch 3): gate log has no byte cap — addressed in Risks &
  edge cases: bounded by GATE_TIMEOUT_S's wall-clock deadline, same bound
  `run_gate` already relies on; PRD's own Feature: Gate log specifies no
  truncation, so capping would contradict the PRD. Accepted, not fixed.
- BLOCKER (dispatch 3): normalize_command can equate commands with
  different behavior (quoted-whitespace collapse, bash/sh conflation) —
  addressed in Risks & edge cases: this is the PRD's own specified contract
  (packet 10) and its own Risks section already accepts it; not a design
  defect to fix here.
- NON-BLOCKER (dispatch 3): a dirty result from a run that completed (vs.
  pre-spawn refusal) still renders as "gate skipped" in `run_gate_line`,
  which is imprecise for the post-run case. Recorded, not fixed (the PRD's
  packet-4 wording treats both as one outcome: no record).
dispatch 3 (codex): cardinal-sin 1, blocker 1, non-blocker 1, question 0
result: ok
