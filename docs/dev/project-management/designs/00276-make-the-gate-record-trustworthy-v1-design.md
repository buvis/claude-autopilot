# The gate record can lie or go missing

## Architecture fit

All six fixes land in the existing `verification` module (`cli/verification.py`),
the sole writer of `last-verification.json`, plus the thin `verify` CLI verb in
`cli/__main__.py` that calls it. `store_tree.py` already owns the canonical
dirt/store-prefix contract (`STORE_PREFIXES`, `_store_prefix`) used by the
unrelated `record_store`/`foreign_dirty` path; `verification.py` currently
duplicates a narrower, single-prefix version of that same idea
(`STORE_PREFIX`, `_dirty_path_is_in_store`). This PRD does not unify the two
dirt predicates (`foreign_dirty` returns a path list for a different caller,
`_dirty_outside_store` returns a bool fast-fail for the gate's pre/post-spawn
checks — different shapes, different callers, out of scope to merge here) but
it does make `verification.py` consume `store_tree.STORE_PREFIXES` as the
source of truth for *which prefixes* count as store, closing the drift
between the two modules that caused finding 1. No new module, no new file
beyond tests; `skills/work/references/final-verification.md` gets prose-only
edits.

## Module placement

- **Edit** `skills/run-autopilot/cli/verification.py` — all six behavior
  changes (dirt prefixes, hidden-flag dirt, `dirty_paths`, invalidate-at-start,
  flock, symlink-aware reuse).
- **Edit** `skills/run-autopilot/cli/__main__.py` — `_run_verify`: `--log`
  path resolution/refusal, exit-3 branch, printing `dirty_paths`.
- **Read-only** `skills/run-autopilot/cli/store_tree.py` — import
  `STORE_PREFIXES` only; no behavior change to this module.
- **New tests**: `test_verification.py` (invalidate, flock, log-sink-error —
  already exists, gains cases), `test_verification_dirty.py` (dirt-prefix,
  hidden-flag, dirty_paths, symlink reuse — already exists, gains cases),
  `test_cli_review_verbs.py` (verify log refusal/relative-join/exit-3 — gains
  cases).
- **Edit** `skills/work/references/final-verification.md` — document exit 3
  and the `--log`-inside-store refusal.
- **Edit** `CHANGELOG.md` — `[Unreleased] ### Fixed`.

## Interfaces & contracts

### `verification.py`

```python
from cli.store_tree import STORE_PREFIXES  # ("docs/dev/project-management/", "docs/dev/tmp/")

GATE_LOCK_REL = Path("docs/dev/tmp") / "gate.lock"   # new constant

def _dirty_outside_store_paths(
    repo_root: Path,
    extra_excluded: tuple[str, ...] = (),
) -> list[str]:
    """New. `extra_excluded` holds TOPLEVEL-relative POSIX paths (the same
    coordinate space `git status`/`git ls-files` already print in, and the
    same one `STORE_PREFIXES` is joined into below) — never `cwd`-relative,
    since `cwd` can sit below the toplevel (the bare-repo case
    `store_tree.py` itself documents) and a cwd-relative value would then
    fail to match the toplevel-relative paths git prints, silently
    re-opening finding 1/2 in exactly that deployment. The caller (`run_gate`,
    below) is responsible for computing the value in that coordinate space.
    Behavior:
    1. store roots become `{prefix + p for p in STORE_PREFIXES} | set(extra_excluded)`
       (was the single `prefix + STORE_PREFIX`, no `extra_excluded`), where
       `prefix` is `git rev-parse --show-prefix`. `extra_excluded` entries are
       used as-given (already toplevel-relative) — not re-joined with `prefix`.
    2. the existing porcelain-status dirt check runs first, exactly as today,
       against this widened root set.
    3. then run `git ls-files -v -z --full-name` with NO pathspec argument
       (cwd=`repo_root`) — omitting the pathspec is what gives the WHOLE
       tracked index, not just the subtree under `cwd`; a `-- .` or any
       other pathspec argument would reintroduce the exact cwd-scoping bug
       this fix exists to close, so none is ever added here. `--full-name`
       then forces the PRINTED paths to be toplevel-relative (git's default
       is cwd-relative display) even when `repo_root` sits below the
       toplevel — the bare-repo case this module already has to handle —
       and `-z` NUL-terminates each `"<tag> <path>"` record so a
       quoted/escaped path from `core.quotePath` cannot be mis-split,
       unlike a newline parse. Treat any record whose tag is `S`
       (skip-worktree) or lowercase (assume-unchanged: any lowercase
       single-letter tag per `git ls-files` conventions) outside the same
       root set as dirty.
    4. a `git` call failure (status OR ls-files) counts as dirty — this
       function itself catches nothing; it propagates `OSError`/non-zero
       exit as today's status check already does via its own `_git`
       wrapper's returncode check. The bool-returning caller below owns the
       fail-closed `except OSError: return True` wrapper; this function
       never swallows an error into a `[]` (which would read as "clean").
    Returns the sorted, deduplicated list of offending paths (both status
    and ls-files hits), `[]` when clean.
    """

def _dirty_outside_store(
    repo_root: Path,
    extra_excluded: tuple[str, ...] = (),
) -> bool:
    """Unchanged signature plus one new optional parameter (same
    toplevel-relative convention as `_dirty_outside_store_paths`).
    Becomes `bool(_dirty_outside_store_paths(repo_root, extra_excluded))`
    wrapped in `try/except OSError: return True` — the single place this
    module fails closed on an unexpected error, matching today's contract
    exactly. The two functions can never disagree on what counts as dirty:
    one predicate, two shapes, one error-handling boundary (here, not in
    `_dirty_outside_store_paths`)."""

def run_gate(
    command: str,
    cwd: Path,
    sha: str,
    cycle: int | None,
    timeout: float = GATE_TIMEOUT_S,
    log_path: Path | None = None,
) -> dict:
    """Signature unchanged. New behavior, in order — the flock is acquired
    FIRST, before any of the operations it protects, so two concurrent
    `run_gate` calls against the same `cwd` cannot both reach the log-open,
    the record-delete, or the record-write (closing finding 15 for real,
    not just for the record write):
    1. Acquire `fcntl.flock(fd, fcntl.LOCK_EX)` on `cwd / GATE_LOCK_REL`
       (parent dir created first), blocking, no timeout of its own — the
       caller's own process can still be killed by its surrounding
       timeout/signal handling; `run_gate` does not add a second one. Hold
       it through every step below, including the pre-spawn dirty check,
       the log open, the invalidate-at-start delete, the spawn/drain/reap,
       and the final `_write_record`/`result["recorded"]` assignment;
       release (and close the lock fd) in the same `finally` that already
       closes `log_file`, so a lock acquired is always released even on an
       exception mid-run.
    2. Compute `log_path_toplevel`: when `log_path` resolves inside `cwd`'s
       git toplevel, its toplevel-relative POSIX path (via the same
       `git rev-parse --show-prefix` + relative-path math
       `_dirty_outside_store_paths` uses internally — computed once here
       and threaded through, not recomputed per call); else `None`. ALL
       tracked-ness and exclusion checks below use this SAME toplevel-
       relative value and run their `git` calls with `cwd=<toplevel>`
       (`git rev-parse --show-toplevel`, not `cwd`/`repo_root`) — one
       coordinate space, one working directory, for both this check and
       `_is_tracked` in `__main__.py` below, so a nested `repo_root` can
       never cause either side to query the wrong index path.
    2.5. **Refuse a tracked log destination outright.** When
       `log_path_toplevel` is not `None` and
       `git ls-files --error-unmatch -- <log_path_toplevel>` (cwd=toplevel)
       exits 0 (tracked) -> release the lock, return `_dirty_result([log_path_toplevel])`
       with NO log file opened and no record touched. This is an explicit
       refusal, not a silent fall-through: a tracked destination is never
       added to the exclusion set in step 3 below, so without this step it
       would reach step 4's log-open and be truncated while reading as
       clean. `_run_verify` (below) performs the same refusal earlier, at
       the CLI layer, for a better error message; this step is `run_gate`'s
       OWN backstop for any caller that passes `log_path` directly (tests,
       future callers), so the exemption mechanism can never depend solely
       on the CLI layer remembering to check first.
       `extra_excluded = (log_path_toplevel,) if log_path_toplevel else ()`
       — reached only once 2.5 has confirmed (or `log_path_toplevel` is
       `None`, or tracked-ness is moot) that nothing tracked is being
       excluded.
    3. Pre-spawn: `_dirty_outside_store_paths(cwd, extra_excluded)`. Non-empty
       -> release the lock, return `_dirty_result(paths)` (see below) with
       `dirty_paths` set to that list. This replaces the old bool pre-spawn
       check. No log file is opened and no record is deleted on this path.
    3.5. **Re-verify `sha`**: run `git rev-parse HEAD` (cwd) and compare to
       the `sha` argument. A mismatch means the tree advanced between
       `_run_verify`'s HEAD capture (before the lock) and this call
       acquiring the lock — release the lock and return `_dirty_result([])`
       (a TOCTOU window, not a dirty path; `dirty_paths` stays `[]` since
       no path is at fault, only the moment) rather than certifying a
       commit that is no longer what actually ran. This closes the race a
       second, lock-queued `verify` invocation would otherwise hit: without
       it, a clean HEAD advance during the wait writes a correct-looking
       record under the WRONG sha.
    4. Open `log_path` — reordered to AFTER the pre-spawn dirty check above
       (today's code opens it before; see `## Alternatives considered` for
       why this PRD moves it), since a dirty-tree refusal must open nothing.
    5. **Invalidate at start**: once the pre-spawn dirty check has passed
       (never before — an aborted run must not cost the record when the
       tree was already too dirty to run at all), delete
       `cwd / RECORD_REL` if it exists (`missing_ok=True`), before spawning
       the child. A delete failure (OSError other than FileNotFoundError)
       propagates uncaught — same "bare OSError, not caught here" contract
       `run_gate`'s docstring already states for the log-open failure.
    6. Spawn, drain, reap — unchanged.
    7. Post-reap dirty check becomes
       `_dirty_outside_store_paths(cwd, extra_excluded)`; its result list
       populates `result["dirty_paths"]`, and `result["dirty"] = bool(...)`
       as before (so the `dirty` boolean key keeps its contract for every
       existing caller that reads only that key).
    8. `_write_record` unchanged; still gated on `found and not dirty`.
    Result dict gains one key, always present: `"dirty_paths": list[str]`
    (empty when clean) on every return path — `_timed_out_result()` and
    `_dirty_result()` both get it (`_timed_out_result` always `[]`,
    `_dirty_result` takes the offending list as a new required parameter).
    """

def _dirty_result(dirty_paths: list[str]) -> dict:
    """Signature change: now takes the offending paths. Body unchanged plus
    `"dirty_paths": dirty_paths`."""

def _timed_out_result() -> dict:
    """Unchanged except the literal now includes `"dirty_paths": []`."""

def reuse_verdict(
    record: dict | None,
    repo_root: Path,
    head_sha: str,
    gate_command: str,
) -> tuple[str, dict]:
    """Signature unchanged. Two new checks inserted between the existing
    ancestor-and-clean check and the final `("reused", record)` return, both
    against the same symlink inventory and both able to independently
    return `_STALE`:

    **(a) Committed store changes reached through a symlink.** For every
    path the `_ancestor_and_clean` diff found INSIDE the store (today those
    are the only paths it lets through), check whether any tracked symlink
    OUTSIDE the store (`git ls-files -s`, mode `120000`, target read from
    the blob content via `git cat-file -p <blob>` — not `os.readlink`,
    since the symlink's target string is the blob content, not a
    filesystem readlink against a path that may not exist in this checkout
    state) aliases that store path. POSIX symlink targets are relative to
    the symlink's OWN containing directory, not the repo root: resolve each
    target as
    `posixpath.normpath(posixpath.join(posixpath.dirname(symlink_path), target))`.
    A symlink ALIASES a store path `p` when the resolved target equals `p`
    (file symlink onto `p` directly) OR `p` equals the target joined with
    some remaining suffix, i.e. `p == target or p.startswith(target + "/")`
    — this is the minimum fix needed to also catch a symlinked DIRECTORY
    (e.g. `assets -> docs/dev/project-management/assets`) aliasing a
    changed file inside it (`assets/theme.css` aliasing
    `docs/dev/project-management/assets/theme.css`), which exact-string
    equality alone misses. Symlink CHAINS (a symlink whose target is itself
    a symlink) and absolute in-checkout targets are NOT resolved further —
    recorded as a known gap below, not fixed here (no evidence any such
    chain exists in this repo's own tree; the PRD's own packet-16 example
    is a single-hop relative file symlink).

    **(b) Uncommitted store changes reached through a symlink.** The dirt
    checks (`_dirty_outside_store_paths`) already tolerate a dirty/untracked
    path INSIDE the store — that is their whole purpose — so an uncommitted
    edit to a store file is invisible to them, and check (a) above only
    ever sees COMMITTED diffs between the two shas. A store file changed
    only in the working tree (staged or unstaged) and reached through a
    product symlink would therefore still read as `reused` without this
    second check. Add a new `_dirty_store_paths(repo_root) -> list[str]`
    (the inverse filter of `_dirty_outside_store_paths`'s own porcelain-
    status scan — same git call, same records, kept paths flipped) and run
    the same alias test from (a) against ITS output too, every call,
    regardless of whether the committed diff found anything.

    Either check's hit -> `return _STALE`. Implemented as one new helper,
    `_store_symlink_targets_changed(repo_root, store_paths: list[str]) -> bool`,
    called twice from `_ancestor_and_clean` — once with the committed-diff
    store paths (so the symlink check shares that function's existing
    `store` prefix and early-return-on-git-failure shape), once with
    `_dirty_store_paths(repo_root)` — rather than being open-coded twice or
    called from `reuse_verdict` directly. This keeps `reuse_verdict`'s own
    docstring-as-contract list a single ordered pipeline instead of two
    call sites deciding staleness."""
```

### `__main__.py`

```python
def _run_verify(args: argparse.Namespace) -> int:
    """New step, inserted immediately after `head = proc.stdout.strip()` and
    the default-log-path computation, BEFORE `run_gate` is called (so a
    refused log path opens nothing — no log file, no lock, no record
    delete):
        resolved_log = (
            args.log if args.log.is_absolute() else repo_root / args.log
        ) if args.log is not None else <existing default, already absolute>
        resolved_log = resolved_log.resolve()  # no symlink games
        store_root = (repo_root / "docs/dev/project-management").resolve()
        if store_root in resolved_log.parents or resolved_log == store_root:
            print(
                f"autopilot: verify: --log {args.log} resolves inside the store",
                file=sys.stderr,
            )
            return 2
        # Second refusal, same shape: a --log destination that is a TRACKED
        # file (anywhere, not just the store) must not be writable by this
        # command — run_gate's own log open would truncate it, and nothing
        # about dirt-exclusion should ever apply to tracked product code.
        # _is_tracked resolves `resolved_log` to a TOPLEVEL-relative path
        # and runs `git ls-files --error-unmatch` with cwd=<git toplevel>
        # (never `repo_root`, which may sit below the toplevel) — the same
        # coordinate space and working directory run_gate's own step 2.5
        # uses, so neither side can land on a different index path for the
        # same file.
        if _is_tracked(repo_root, resolved_log):
            print(
                f"autopilot: verify: --log {args.log} resolves to a tracked file",
                file=sys.stderr,
            )
            return 2
    Pass `log_path=resolved_log` to `run_gate` (replacing the current
    `args.log`-or-default expression) so a RELATIVE `--log` joins
    `--repo-root`, not the process cwd (closes finding 14) — today's default
    branch already joins `repo_root`; this makes the explicit-`--log` branch
    do the same.
    After `run_gate` returns and the existing
    `print(json.dumps({**result, "sha": head, "log": str(log_path)}))` line
    (now `str(resolved_log)`, and `result` already carries `dirty_paths`,
    which the `**result` spread prints for free — no separate print needed):
        if result["exit"] == 0 and not result["timed_out"] and not result["dirty"]:
            if result["recorded"]:
                return 0
            return 3   # green, not dirty/timed-out, but no record (finding 10)
        return 1
    This keeps exit 2 (HEAD/log-open failure) and exit 1 (dirty, timed out,
    or non-zero gate exit) exactly as today's docstring states, and adds
    exit 3 as the one new code, documented in both the `__main__.py` module
    docstring's `verify` entry and `final-verification.md`.
    """

def _is_tracked(repo_root: Path, path: Path) -> bool:
    """New, `__main__.py`-local helper (mirrors `verification._git`'s shape
    but lives beside the verb it serves — `run_gate`'s step 2.5 does its own
    narrower `ls-files --error-unmatch` check inline, so this is not shared
    code, just the same one-line idiom used twice, in the same coordinate
    space). Resolves `path` to its TOPLEVEL-relative POSIX form (via
    `git rev-parse --show-toplevel` + relative-path math, never
    `repo_root`-relative — `repo_root` may sit below the toplevel) and runs
    `git ls-files --error-unmatch -- <that path>` with `cwd=<toplevel>`.
    True iff it exits 0. A path outside the repo, or any non-git-related
    OSError, is treated as NOT tracked (fails toward the narrower
    store-only refusal already covering that case, never toward blocking
    an unrelated path the repo cannot even see)."""
```

## Data flow

1. `_run_verify` resolves `repo_root`, `HEAD`, and now the log path (checked
   against the store before anything is opened).
2. `run_gate` takes the lock, refuses a tracked `--log` destination outright,
   checks dirt (store roots ∪ hidden-flag paths ∪ the log's own path when it
   resolves inside the repo, is untracked, and falls outside the store),
   re-verifies the certified sha, THEN deletes any stale record, spawns the
   gate command, streams its output to the now-locked log file, reaps it,
   checks dirt again, and writes the record only when both checks were
   clean and a summary line parsed.
3. The lock is released in `run_gate`'s `finally`, after the record write (or
   its skip) — so two concurrent `verify` invocations against the same
   `cwd` serialize end-to-end rather than interleaving log bytes or racing
   the record write (finding 15). `flock` blocks with NO deadline of its
   own — the second invocation waits as long as the first run takes, not
   bounded by its own `timeout` argument (that `timeout` only bounds the
   gate subprocess once spawned, after the lock is already held). A hung
   first run therefore blocks the second indefinitely; this is the accepted
   cost the PRD's own Risks section names ("a hung gate blocks the next
   until it expires" — read as "until the first run's own process is
   killed by its external supervisor," not by a deadline inside `flock`
   itself, since none exists).
4. `_run_verify` prints the result (now carrying `dirty_paths`) and maps it
   to an exit code, with the new exit 3 distinguishing "ran green but wrote
   no record" from exit 0.
5. `review-stage` (unchanged by this PRD) later reads the same record via
   `reuse_verdict`, which now also refuses a record whose certified store
   paths are symlink-aliased into product (finding 16).

## Reuse inventory

- `cli/store_tree.STORE_PREFIXES` — the two-prefix store definition
  (`docs/dev/project-management/`, `docs/dev/tmp/`) already used by
  `record_store`/`foreign_dirty`. `verification.py` adopts it directly for
  its own `_dirty_outside_store*` checks instead of keeping its own
  single-prefix `STORE_PREFIX` constant, closing finding 1 by construction
  rather than by special-casing `docs/dev/tmp/`.
- `_git`, `_iter_porcelain_z_records`, `_dirty_path_is_in_store` — existing
  helpers in `verification.py`; reused as-is for the status half of the dirt
  check. The new ls-files hidden-flag scan is additive, not a replacement.
- `_ancestor_and_clean`'s existing `store` (prefix-joined) computation is
  reused by the new symlink-staleness helper rather than recomputing the
  prefix a second time.
- `fcntl` — stdlib; no new dependency. (Greps tried: `rg -n "import fcntl"
  skills/run-autopilot/cli/` — no existing use in this pack, but `fcntl.flock`
  is the standard POSIX advisory-lock primitive and this project already
  targets POSIX-only tooling — darwin/linux dev hosts, `ctypes`-based
  `procinfo.py` darwin syscalls elsewhere in this same `cli/` package.)
- `Path.unlink(missing_ok=True)` — stdlib; replaces a hand-rolled
  exists-then-remove for the invalidate-at-start delete.
- Greps tried for an existing symlink-resolution helper:
  `rg -n "120000|readlink|S_ISLNK" skills/run-autopilot/cli/` — nothing
  found; `git ls-files -s` plus `git cat-file -p <blob>` is the new, minimal
  path (no `os.readlink` since the symlink's *target string* is the blob
  content, not a filesystem readlink against a path that may not exist in
  this checkout state).

## Alternatives considered

- **Check-then-open vs. open-then-check for `log_path`.** Today `run_gate`
  opens `log_path` before its pre-spawn dirty check (PRD finding 2's root
  cause touches this ordering too: an early-open could itself make a path
  under `docs/dev/tmp/` dirty before the check runs, refusing a run that
  would otherwise be clean). Considered: (a) keep open-before-check but add
  `log_path`'s own toplevel-relative path to `extra_excluded` (smallest
  diff) vs. (b) reorder to check-then-open. **Chosen: (b), check-then-open**
  — once the flock is acquired first (the lock-ordering fix above), nothing
  stops moving the dirty check ahead of the log open too, and doing so means
  a dirty-tree refusal creates no log file at all rather than relying on
  `extra_excluded` to paper over a file it already created. `extra_excluded`
  is still needed (and still computed) for the SECOND, post-reap dirty
  check, where the log file necessarily exists by then — so this is not an
  either/or against the PRD's own "extra excluded path" ask, it is doing
  both: check-then-open removes the pre-spawn half of the problem
  structurally, `extra_excluded` covers the post-reap half that structural
  ordering cannot reach.
- **Symlink check scope.** Considered: (a) a general "does the store root
  move" symlink audit (smaller) vs. (b) PRD's literal ask, checking only
  symlinks whose target lands inside a path either dirt/diff check actually
  found changed. **Chosen: (b)**, the PRD's own wording — a general audit
  would flag symlinks irrelevant to either sha pair being judged or to the
  working tree's current state, and cost an extra full-repo `ls-files -s`
  scan on every `reuse_verdict` call even when nothing store-related
  changed at all. Within (b), the symlink probe still runs TWICE
  unconditionally per `reuse_verdict` call — once against committed
  store-only diff paths (check (a) in Interfaces & contracts), once against
  CURRENT dirty store paths (check (b) there) — because "the diff found
  store-only changes" and "the working tree currently has store dirt" are
  independent conditions (a committed change and an uncommitted edit through
  the same symlink are two different ways the finding-16 scenario happens);
  neither check gates the other.
- **Lock granularity.** Considered: (a) one global `docs/dev/tmp/gate.lock`
  per repo (PRD's ask) vs. (b) per-`cycle` locks. **Chosen: (a)** — two
  concurrent gate runs in the same working tree are not just a record race,
  they are *actually* running the same suite over the same files
  concurrently (resource contention, port clashes, flaky shared caches);
  serializing fully is the correct behavior, and the PRD accepts the
  "second run waits" cost explicitly (Risks). Per-cycle locking would let
  two gate runs stomp each other's working tree while only pretending to
  fix the record race.

## Risks & edge cases

- **Invalidate-at-start timing.** The delete must happen strictly after the
  pre-spawn dirty check passes and strictly before the child spawns, inside
  the same lock acquisition — deleting on a dirty-tree refusal would cost a
  good record for a run that never even started (PRD explicitly rejects
  this: dirty-tree refusal must stay non-destructive). Covered by
  `test_failed_run_leaves_no_older_green_record`, which must assert the record
  is still PRESENT after a dirty-tree refusal, not just after a gate failure.
- **Lock held across the log-write and the record-write, not just the
  record-write.** If only the record write were locked, two runs could still
  interleave their log *bytes* (finding 15's second symptom). The design
  locks from before step 1 (log open) through the record write for exactly
  this reason.
- **`git ls-files -v` on a very large repo** is a second full-tree git call
  per dirty check (now 2x per `run_gate` call: pre-spawn and post-reap, same
  as today's status call). Likely next change: cache the ls-files hidden-flag
  scan per `run_gate` invocation if it becomes a measured cost — out of scope
  here, no evidence of cost yet.
  - Boxed-in by this design: `_dirty_outside_store_paths` runs both checks
  unconditionally every call; a future perf PR adding a cache would change
  this function's internals only, not its signature.
- **Next likely changes**: (1) unifying `verification._dirty_outside_store*`
  with `store_tree.foreign_dirty` into one shared predicate, now that both
  consume `STORE_PREFIXES` — deferred here because `foreign_dirty` already
  has its own caller contract (`record_store`) this PRD does not touch; (2)
  a configurable store-prefix list per repo (today both modules hard-code
  `docs/dev/project-management`) if a third repo shape appears; (3) the
  `--log` store-refusal check could extend to any `--log` path that is
  itself a symlink into the store — not needed by any of the 7 findings,
  noted as a gap this design does not box in (a future PR can add the same
  `.resolve()` call that already follows symlinks today).
- **Symlink chains and absolute in-checkout targets are not resolved.** The
  symlink-alias check (Interfaces & contracts, `reuse_verdict`) follows one
  hop and only normalizes a relative target string; a symlink whose target
  is itself a symlink, or whose target is an absolute path rather than a
  relative one, is not traced further and would not be caught. No evidence
  this repo's own tree has either shape today — recorded as a known gap,
  not fixed, to keep the helper a single normalize-and-compare rather than
  a general filesystem graph walk.
- **Exit 3 is new.** Any prose or script treating "non-zero = red suite" must
  special-case 3 as "green, unrecorded" — `final-verification.md` is the one
  place this PRD updates; no other prose in this repo currently branches on
  `verify`'s exit code (confirmed: `rg -n "autopilot verify"` outside this
  PRD's own files returns only the doc line being edited and the CLI itself).

## Test strategy outline

- **`verification.py` unit tests** (`test_verification.py`,
  `test_verification_dirty.py`), each pinned per the PRD's own task
  acceptance list:
  - dirt-prefix: a repo with no `.gitignore`, `GIT_CONFIG_GLOBAL=/dev/null`,
    a staged `docs/dev/tmp/*.md` file -> `recorded: True`; the run's own log
    path under `docs/dev/tmp/` is not itself dirt.
  - hidden-flag dirt: `update-index --skip-worktree` / `--assume-unchanged`
    on a path outside the store blocks the record; restoring/clearing the
    flag un-blocks it.
  - `dirty_paths`: a dirty run's result lists the exact offending paths,
    sorted; a clean run's list is empty.
  - invalidate-at-start: a failed run (gate exits non-zero, or output
    unparseable) leaves NO record, even when a good one existed before;
    a dirty-tree refusal leaves the EXISTING record untouched (see Risks).
  - flock: two `run_gate` calls launched concurrently against the same
    `cwd` (threads or subprocesses) serialize — the second's start time is
    provably after the first's record write, asserted via a shared
    timestamp/log rather than a sleep race.
  - log-sink OSError: a `sink.write` that raises mid-drain kills and reaps
    the gate's process group before the error propagates (already covered;
    confirm the lock is released in this path too — assert a SEPARATE
    process/fd can acquire `LOCK_EX | LOCK_NB` on the lock file after the
    exception; removing or renaming the lock-file path does NOT prove the
    held advisory lock was released, since POSIX `flock` locks the open
    file descriptor's underlying inode, not the pathname).
  - sha re-verify: a `run_gate` call whose `sha` argument no longer matches
    `git rev-parse HEAD` once the lock is acquired (simulate by advancing
    HEAD between a monkeypatched pre-lock capture and the lock acquisition)
    returns the dirty-refusal shape and writes no record.
  - symlink reuse, directory alias: a tracked directory symlink (e.g.
    `assets -> docs/dev/project-management/assets`) aliasing a changed file
    beneath it (`assets/theme.css`) -> `stale`.
  - symlink reuse, uncommitted: an unstaged (or staged, uncommitted) edit to
    a store file reached through a tracked symlink, with HEAD unchanged
    since the last recorded run -> `stale`, not `reused`.
  - symlink reuse: a tracked symlink outside the store resolving into a
    store path that changed between the two shas -> `stale`, even though
    the raw diff is store-only; the existing
    `test_store_only_change_below_toplevel_is_reused` must keep passing
    (no symlink in that fixture).
- **`__main__.py` verify-verb tests** (`test_cli_review_verbs.py`):
  - `--log` resolving inside the store (absolute, and relative-that-resolves-
    inside) exits 2 with the record bytes on disk UNCHANGED (prove nothing
    was opened/truncated).
  - `--log` resolving to a TRACKED file outside the store (e.g. a fixture's
    own `src/module.py`) exits 2 with that file's bytes UNCHANGED (prove
    the exclusion-then-truncate gap is closed); an UNTRACKED `--log`
    destination outside the store still works exactly as today.
  - a relative `--log` with `--repo-root` set to a fixture, invoked from a
    different cwd, resolves against `--repo-root`, not cwd.
  - green gate + `recorded: false` (e.g. a gate that exits 0 printing no
    summary) -> exit 3.
  - the existing `test_verify_exits_2_when_the_log_cannot_be_opened` keeps
    passing unchanged (that failure path precedes the new store check only
    when the store check itself passes first — order both checks so the
    store-path refusal, being cheaper and not touching the filesystem, runs
    before the attempt to open the log file).
- **Prose/CHANGELOG** checked by `rg` per the PRD's own Phase 2 acceptance
  criteria (`exit 3|exits 3` in `final-verification.md`; `docs/dev/tmp` under
  `[Unreleased]` in `CHANGELOG.md`).
- **Full gate**: `bash dev/bin/release-checks` per the PRD's own Phase 2 exit
  criteria.

## Review log

- Dispatch 1 fixed: self-contradictory log-open ordering narrative (unified
  to check-then-open, with Alternatives updated to match); flock acquired
  after the operations it was meant to protect (reordered to first step,
  held across log-open/invalidate/spawn/write); `extra_excluded` specified
  as cwd-relative when it must be toplevel-relative to match git's own
  path coordinate space; symlink target resolved against repo root instead
  of the symlink's own containing directory (fixed to resolve relative to
  `dirname(symlink_path)`).
- Question (not fixed, recorded): which function owns the `OSError` fail-
  closed boundary between `_dirty_outside_store_paths` and
  `_dirty_outside_store` — resolved in the fix above: `_dirty_outside_store`
  alone catches `OSError`; `_dirty_outside_store_paths` propagates.
dispatch 1 (claude): cardinal-sin 0, blocker 3, non-blocker 0, question 1
- Dispatch 2 fixed: `--log` exclusion could hide and then truncate a tracked
  product file (added a tracked-file refusal, both at the CLI verb and
  inside `run_gate` itself); the hidden-flag `ls-files` scan was
  pathspec-limited and cwd-relative with newline parsing (fixed to
  `-v -z --full-name` from repo_root); the symlink-alias check missed
  directory aliases (fixed to a prefix-boundary comparison, not exact
  equality) and ignored uncommitted store edits reached through a symlink
  (added a second check against current dirty store paths, not only the
  committed diff); the certified sha was captured before the lock
  (`_run_verify`'s HEAD read precedes `run_gate`'s lock acquisition) with
  no re-check, letting a lock-queued run certify a stale sha (added a
  post-lock sha re-verify that refuses on mismatch).
- Non-blocking (not fixed as a design change, test strategy corrected): a
  removable/renamed lock file does not prove the advisory lock itself was
  released (POSIX `flock` locks the inode via the fd, not the pathname) —
  the affected test assertion is rewritten to probe `LOCK_EX | LOCK_NB`
  from a second fd instead.
- Question (not fixed, recorded): whether the gate `timeout` bounds lock
  wait time — resolved by removing the incorrect claim from Data flow:
  `flock` blocks with no deadline of its own; `timeout` only bounds the
  spawned subprocess once the lock is already held.
- Symlink chains and absolute in-checkout targets remain an explicit,
  recorded gap (Risks & edge cases) — not fixed, no evidence of need.
dispatch 2 (codex): cardinal-sin 0, blocker 5, non-blocker 1, question 1
- Dispatch 3 (verification of dispatch 2's fixes) confirmed finding 5
  (sha re-verify) closed, and found the other 4 fixes incomplete or
  ambiguously worded, plus 1 new blocking and 1 new non-blocking gap, all
  fixed:
  - #1 (tracked `--log`): the prior fix only skipped ADDING a tracked path
    to the exclusion set; nothing explicitly refused it, so it still
    reached the log-open and got truncated. Fixed: `run_gate` now has an
    explicit step 2.5 that refuses a tracked `log_path` outright (returns
    `_dirty_result`, opens nothing), not just an omission from
    `extra_excluded`.
  - #2 (ls-files scope): clarified that the fix already omits any pathspec
    argument (the actual fix for cwd-scoping; `--full-name` only affects
    PRINTED path format) — reworded so the two concerns aren't conflated.
  - #4 (uncommitted symlink check unconditional): the Alternatives section
    still said the symlink probe "only runs when the ancestor-and-clean
    check already found store-only changes," contradicting the Interfaces
    fix that added an unconditional second check. Fixed: Alternatives now
    states both checks run unconditionally and independently.
  - NEW blocking (coordinate mismatch): `_is_tracked`'s toplevel-relative
    contract and `run_gate`'s own tracked-check used inconsistent
    coordinate spaces/cwd. Fixed: both now explicitly resolve to
    toplevel-relative paths and run from the git toplevel, not `repo_root`.
  - NEW non-blocking (Data flow wording): the prose summary listed
    "deletes any stale record, checks dirt" in the wrong order versus the
    numbered steps. Fixed: reworded to match the actual step order (dirt
    check and sha re-verify precede the invalidate-at-start delete).
  - #3 (symlink chains/absolute targets) was re-flagged as "still open"
    for not resolving indirect targets — accepted as a recorded gap, not
    fixed: the PRD's own packet-16 acceptance test is a single-hop relative
    file symlink, and dispatch 2's own suggested_fix for this finding
    asked for directory-alias coverage (done) without demanding full
    chain resolution.
dispatch 3 (codex): cardinal-sin 0, blocker 1, non-blocker 1, question 0
