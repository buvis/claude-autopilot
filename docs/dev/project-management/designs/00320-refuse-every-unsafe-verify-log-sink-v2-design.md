# Design: Refuse every unsafe verify --log sink before opening it (v2)

## Architecture fit

`skills/run-autopilot/cli/__main__.py`'s `_run_verify` is the CLI entry point
for `autopilot verify`; `_refuse_verify_log` is its pre-flight gate, called
before anything opens or writes the log path. `skills/run-autopilot/cli/
verification.py`'s `run_gate` → `_lock_and_check` → `_run_locked_gate` is the
locked spawn path a library caller can reach directly, bypassing the CLI's
gate entirely — so the PRD's refusal must also land inside `_lock_and_check`,
not only in `_refuse_verify_log`. `cli/dirty_tree.py` already owns every git
probe this PRD needs (store identity, toplevel resolution, tracked-file
check); this design adds no new git plumbing, only identity/filesystem checks
that `dirty_tree.py` does not yet do (symlink walk, hard-link count, mode
bits, git-directory identity).

## Module placement

- **Edit** `skills/run-autopilot/cli/__main__.py`:
  - Rewrite `_refuse_verify_log` to run all six case groups (identity,
    tracked, symlink, outside-repo, non-regular/executable, hard-link),
    called at both the user-supplied `--log` path and the default sink.
  - `_run_verify` **must stop pre-resolving the log path before the
    refusal call** (today it does `log_path = (...).resolve()` then
    passes that resolved path in). Case 3's symlink walk needs the
    UNRESOLVED path — resolving first silently follows any symlink in
    the ancestry, so the walk would never see one. `_run_verify` now
    computes an unresolved candidate (`repo_root / args.log` or the
    default, no `.resolve()`) and passes THAT SAME unresolved path both
    to `_refuse_verify_log` and on into `run_gate(..., log_path=...)` —
    it is never resolved in `_run_verify` at all. This matters beyond the
    CLI path: `_lock_and_check`'s own `_refuse_verify_log_path` call
    (library path, § Interfaces below) needs the same unresolved input
    for ITS case-3 check to be reachable, so `run_gate`'s `log_path`
    parameter is documented as "pass unresolved; every internal check and
    `_open_log_sink` resolve only where they individually need to." A
    direct `run_gate()` caller that resolves before calling loses case 3
    for itself, exactly as a resolving CLI would — this is a caller
    contract, not something `run_gate` can enforce from inside.
  - `_run_verify`'s call site changes from printing its own JSON line
    after a True return to simply returning 2: the wrapper (below) now
    owns printing both the stderr line and the JSON line with the actual
    case's reason text, so the call site must NOT print a second,
    hardcoded JSON line (today's code does, and it would be wrong for 5
    of the 6 cases, plus missing `"log": null"`).
- **Edit** `skills/run-autopilot/cli/verification.py`:
  - Add `_open_log_sink(log_path: Path) -> object` (a file object), called
    from `_run_locked_gate` in place of today's `open(log_path, "wb",
    buffering=0)`.
  - `_lock_and_check` gains a call to the new `_refuse_verify_log_path`
    check (see below) before its existing dirty/head checks, returning
    `_dirty_result([rel])` when it fires.
- **New file** `skills/run-autopilot/cli/test_verify_log_refusal.py` (the
  fourteen tests named in the PRD, plus two more this design adds — see
  Test strategy outline — for sixteen total).
- **No change** to `cli/dirty_tree.py`'s public surface; `_refuse_verify_log`
  reuses `_log_rel_and_tracked` (toplevel resolution + tracked check) and
  `STORE_PREFIX` (store identity, the single-prefix constant — NOT
  `_store_roots`/`STORE_PREFIXES`, which also covers `docs/dev/tmp/`; see
  § Reuse inventory) rather than re-deriving them.
- The PRD's own Phase 1 task already lists the CHANGELOG `[Unreleased]`
  Fixed entry as a deliverable; this design adds nothing beyond
  implementing that entry's exact text as given in the PRD's Tasks
  section, under `**run-autopilot**`.

## Interfaces & contracts

```python
# skills/run-autopilot/cli/__main__.py

def _refuse_verify_log(log: Path, repo_root: Path, log_path: Path) -> bool:
    """`log_path` is the UNRESOLVED candidate path (`repo_root / args.log`
    or the default sink, built with no `.resolve()` call) — resolving
    before this call would silently follow any symlink in the ancestry
    and make case 3 unreachable. Checked, in this order, against
    `repo_root` (passed by the caller; never cwd). Calls
    `log_sink_refusal.refuse(log_path, repo_root)` (below); on a non-None
    reason, builds ONE message string
    `message = f"autopilot: verify: --log {log} {reason}"` and prints BOTH
    the stderr line (`message` verbatim) and the JSON line
    `{"error": message, "exit": 2, "log": None}` — the PRD requires "the
    same text" in both, which means the FULL stderr line including the
    `autopilot: verify: ` prefix, not just the `--log ... reason` tail (an
    earlier draft of this design got this wrong by building the JSON
    `error` from a shorter string). Returns True. Returns False when
    `refuse()` returns None (path may be opened).
    `_run_verify`'s call site becomes `if _refuse_verify_log(...): return 2`
    — no second print at the call site; this function is now the SOLE
    place that prints the refusal's stderr and JSON lines. Runs on BOTH
    the user-supplied --log path and the default
    `docs/dev/tmp/gate-<sha7>.log` sink — the caller passes the same
    `log_path`/`log` pair either way; there is no "default sink is
    exempt" branch.

    Case order (first match wins; every case is checked even though only
    one message is returned, so the implementation does not need to find
    all seven — these are the seven in the order the PRD's refusal cases
    must be checked for the "tracked" vs "git-dir" vs "outside" cases to
    produce a consistent reason on an overlapping path, e.g. a tracked
    file inside .git/):

    1. identity (store OR git directory), via os.path.samefile walking
       EVERY existing ancestor of the RESOLVED `log_path` — from the
       resolved path's immediate parent up to the filesystem root,
       stopping once past `repo_root`'s toplevel — against:
       - the store directory: `repo_root / 'docs/dev/project-management'`
       - `git rev-parse --absolute-git-dir` (run from `repo_root`, NEVER cwd)
       - `git rev-parse --git-common-dir` (ditto; resolved against
         `repo_root` if relative)
       Checking only the NEAREST existing ancestor is wrong: for
       `.git/hooks/pre-push.sample`, the nearest existing ancestor might
       be `.git/hooks` while the git-dir identity target is `.git` itself
       two levels up — a single-ancestor check would miss it. Every
       existing ancestor is checked (cheap: at most a handful of
       `samefile` calls), not just one.
       -> 'resolves inside the store' / 'resolves inside the git directory'
    2. tracked at HEAD: `git ls-files --error-unmatch -- <rel>` from the
       toplevel, where `<rel>` is `log_path` resolved then made relative to
       `git rev-parse --show-toplevel` (run from `repo_root`). Reuses
       `cli.dirty_tree._log_rel_and_tracked(repo_root, log_path)` for the
       toplevel-relative path + tracked bool in one call; `None` back from
       that helper (log outside the toplevel, or a git failure) is NOT a
       pass-through here — case 4 below handles "outside" explicitly, so
       a `None` with the path actually outside falls to case 4; a `None`
       from a git failure fails closed as 'resolves outside the repository'.
       -> 'is tracked'
    3. symlink: lstat every path component of the ORIGINAL (unresolved)
       `log_path` from the toplevel down to the full path, including the
       final component. Any component that is a symlink (`os.path.islink`)
       -> 'is a symlink'. This must run BEFORE case 4's resolve, since
       resolving first would silently follow the symlink and the walk
       would then inspect the wrong (target) ancestry.
    4. outside (two sub-checks, same reason text, either one refuses):
       (a) `Path(log_path).resolve()` is not relative to
       `git rev-parse --show-toplevel` (run from `repo_root`) via
       `Path.is_relative_to`. Covers a path outside this repo AND a path
       resolving inside a DIFFERENT repository's store when that other
       repository is NOT nested under this one (the PRD's
       `test_log_into_another_repos_store_is_refused` — that second
       repo's toplevel differs from `repo_root`'s, so the `is_relative_to`
       check against THIS repo's toplevel already refuses it).
       (b) a NESTED-repository check (b)'s gap is real and must be
       closed: a second git repository can sit entirely inside this
       repo's working tree (e.g. an ignored `docs/dev/tmp/other/` holding
       its own `.git`), with its own committed store file — that file is
       inside `repo_root`'s toplevel (passes 4a), untracked by THIS
       repo's index (passes case 2, since `git ls-files` only sees this
       repo's tracked set), and not a symlink (passes case 3). Close it
       by running `git -C <log_path's resolved parent dir>
       rev-parse --show-toplevel` (a SECOND toplevel probe, scoped to
       where the target actually lives, not to `repo_root`) and comparing
       it to `repo_root`'s own toplevel (from 4a); a mismatch means
       `log_path` lives inside a different repository nested under this
       one, and refuses the same way as 4a. A git failure from this probe
       (the resolved parent dir does not exist yet) is not dirty — there
       is no nested repo to detect when the directory itself does not
       exist — and the check is skipped for that path (case 4a and the
       rest of the pipeline still apply).
       -> 'resolves outside the repository'
    5. non-regular / executable: if the resolved path exists, `os.lstat`
       it (not `stat` — a symlink target already failed case 3, but an
       existing non-symlink FIFO/device must not be `stat`-opened, since
       opening a FIFO for read can block): `stat.S_ISREG(mode)` must hold
       -> 'is not a regular file'; else `mode & 0o111` -> 'is executable'.
    6. hard link: if the resolved path exists and is a regular file,
       `os.lstat(...).st_nlink > 1` -> 'has more than one hard link'.

    A path that does not exist yet passes cases 5 and 6 (nothing to
    inspect) and is eligible to open.
    """
```

```python
# skills/run-autopilot/cli/verification.py

def _open_log_sink(log_path: Path) -> "io.BufferedWriter":
    """Opens `log_path` for a fresh write, inside the gate lock, never
    following a symlink and never truncating an existing multi-link
    regular file in place — AND never following a symlinked PARENT
    directory either. `O_EXCL`/`O_NOFOLLOW` on the final `open()` call
    alone only protect the final path component: if `log_path`'s parent
    (e.g. `docs/dev/tmp`) is itself swapped for a symlink to `.git` in the
    window between `_refuse_verify_log`'s check and this function's open,
    an approved `docs/dev/tmp/config` sink resolves to `.git/config` at
    open time, and `O_NOFOLLOW` on the leaf does nothing to stop it (the
    leaf `config` may be a perfectly ordinary non-symlink file sitting
    inside the swapped-in `.git`). So parent containment must be pinned
    by a directory FILE DESCRIPTOR, not by a pathname re-walked at open
    time:

    1. Resolve `log_path`'s parent directory ONCE, before any
       create/unlink, via `os.open(parent, os.O_DIRECTORY | os.O_NOFOLLOW)`
       walking from the toplevel downward one component at a time (each
       `os.open(component, os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent_fd)`
       chained from the previous fd) — this is the standard `openat`-style
       no-follow traversal: a symlink swapped in at ANY level fails that
       level's open with `ELOOP`/`ENOTDIR` rather than being silently
       followed. Missing trailing directories are created with
       `os.mkdir(component, dir_fd=parent_fd)` then reopened the same way
       (replaces today's `log_path.parent.mkdir(parents=True,
       exist_ok=True)`).
    2. With `parent_fd` now a verified, non-symlink directory descriptor,
       unlink any pre-existing leaf with `os.unlink(name, dir_fd=parent_fd)`
       (ignore `FileNotFoundError`) — safe per `_refuse_verify_log`'s
       earlier proof that an existing leaf is untracked, non-symlink,
       single-link, regular and non-executable.
    3. Open with
       `os.open(name, os.O_CREAT | os.O_WRONLY | os.O_EXCL | os.O_NOFOLLOW, dir_fd=parent_fd)`
       — `dir_fd` makes this relative to the pinned parent descriptor, so
       even a symlink swap of the PATHNAME `docs/dev/tmp` after step 1
       cannot redirect this open: the fd from step 1 keeps pointing at the
       original directory's inode regardless of what the pathname now
       names.

    Returns a file object wrapping the final fd (`os.fdopen(fd, 'wb',
    buffering=0)`), so `_run_locked_gate` keeps its existing
    `log_file.close()` in `finally`. `test_default_sink_symlink_is_refused`
    pins the leaf case; a new `test_parent_dir_symlink_swap_is_refused`
    (added to the Test strategy below) pins this parent-swap case
    specifically — plant the swap between a stubbed refusal-check call and
    the open (monkeypatching the check to return None, then racing the
    swap in test setup, since a real concurrent race is non-deterministic
    to pin in a unit test).
    """


def _refuse_verify_log_path(cwd: Path, log_path: Path | None) -> str | None:
    """The `_lock_and_check`-side mirror of `__main__._refuse_verify_log`,
    for the library entry point (`run_gate` called directly, bypassing the
    CLI). Returns None when `log_path` is None (no log requested) or safe;
    else the refusal reason text. Reuses
    `cli.dirty_tree._log_rel_and_tracked(cwd, log_path)` for the
    tracked check and runs the same symlink/outside/non-regular/hard-link/
    identity checks as `__main__._refuse_verify_log`, with `repo_root=cwd`
    (the library caller has no separate repo_root; `cwd` IS the repo root
    by `run_gate`'s existing contract). To avoid duplicating the six-case
    logic twice, `__main__._refuse_verify_log` and this function both call
    a single shared implementation — `cli.log_sink_refusal.refuse(log_path,
    repo_root)` — returning `str | None`; `__main__._refuse_verify_log`
    additionally prints the message and the JSON line and returns `bool`,
    `_refuse_verify_log_path` returns the reason text straight through for
    `_lock_and_check` to fold into `_dirty_result`.
    """


def _lock_and_check(
    cwd: Path,
    sha: str,
    log_path: Path | None,
) -> tuple[tuple[str, ...], dict | object | None]:
    """Unchanged signature. New first check, before the existing dirty/head
    checks: `reason = _refuse_verify_log_path(cwd, log_path)`; if `reason`
    is not None, compute `rel` via
    `cli.dirty_tree._log_rel_and_tracked(cwd, log_path)` (fall back to
    `str(log_path)` when that returns None — an outside-repo or git-failure
    path has no toplevel-relative form) and return
    `(extra_excluded, _dirty_result([rel]))` without taking the lock's
    gate-spawn path at all. `extra_excluded` here is still computed the
    normal way (`_untracked_log_exclusion`) since the caller
    (`run_gate`) always needs a value for that tuple position, even on
    this early-refusal branch.
    """
```

New shared module: `skills/run-autopilot/cli/log_sink_refusal.py`:

```python
def refuse(log_path: Path, repo_root: Path) -> str | None:
    """The six-case check shared by `__main__._refuse_verify_log` and
    `verification._refuse_verify_log_path`. Pure: no printing, no JSON,
    only git/filesystem reads. Signature and case order exactly as
    documented on `__main__._refuse_verify_log` above."""
```

`__main__._refuse_verify_log` becomes a thin wrapper: call `log_sink_refusal.refuse`, and on a non-None reason, print the stderr line and the JSON line, return `True`; else return `False`. `_run_verify`'s call site CHANGES: today it prints a second, hardcoded JSON line after a True return (`{"error": f"--log {log_display} resolves inside the store", "exit": 2}` — wrong text for 5 of the 6 cases, and missing `"log": null`); that print is deleted, leaving `if _refuse_verify_log(log_display, repo_root, log_path): return 2`. This keeps the PRD's exact stderr/JSON text in `__main__.py` where the other verify-CLI text already lives, printed exactly once per refusal.

## Data flow

```
autopilot verify --log <path>
  -> _run_verify
       -> _refuse_verify_log(log_display, repo_root, log_path)
            -> log_sink_refusal.refuse(log_path, repo_root)   # 6 cases
            -> (reason) -> print stderr + json, return True -> exit 2, no open, no lock
       -> verification.run_gate(..., log_path=log_path)
            -> _lock_and_check(cwd, sha, log_path)
                 -> _refuse_verify_log_path(cwd, log_path)      # same 6 cases, library path
                      -> (reason) -> _dirty_result([rel]), no spawn, no open
                 -> (no reason) -> existing dirty/head checks
            -> _run_locked_gate(..., log_path, ...)
                 -> _open_log_sink(log_path)                    # O_CREAT|O_EXCL|O_NOFOLLOW, unlink-then-create
```

**Lock-scope clarification** (the PRD's "no lock is taken" guarantee is
CLI-pre-flight-scoped, not absolute): for the CLI path, `_refuse_verify_log`
runs entirely BEFORE `run_gate` — a refusal there means `run_gate` (and
therefore the flock) is never even called. For a direct `run_gate()`
caller, the refusal runs inside `_lock_and_check`, which the existing
code already calls only AFTER the flock is acquired (`run_gate`'s
unchanged locking preamble) — so a direct-caller refusal still means the
flock was briefly taken and released, with no file opened, no gate
spawned, and no record written. This matches the PRD's actual
requirement ("`_lock_and_check` returns `_dirty_result([rel])`... before
`_run_locked_gate` runs") precisely — the guarantee is "no file touched
and no gate run," which both paths meet; "no lock taken" additionally
holds for the CLI path specifically, since that pre-flight sits outside
`run_gate` entirely.

Both the CLI path and the direct-library path run the identical six-case
check (`log_sink_refusal.refuse`) before any file is touched; the CLI path
additionally refuses a second time inside the lock (via `_lock_and_check`)
because `run_gate` is a public function any caller can invoke without going
through `_refuse_verify_log` first — the PRD's "a library caller cannot
bypass the CLI" requirement.

## Reuse inventory

- `cli.dirty_tree._log_rel_and_tracked(cwd, log_path)` — already resolves
  `log_path` against the git toplevel and runs `git ls-files
  --error-unmatch`; reused for case 2 (tracked) and to derive `rel` for
  `_dirty_result`. Searched: `tracked`, `ls-files`, `log_path` — found this
  and its caller `_untracked_log_exclusion`.
- `cli.dirty_tree.STORE_PREFIX` (the single constant, `"docs/dev/project-
  management/"`) — case 1's store identity is scoped to THIS prefix only,
  NOT the plural `_store_roots`/`STORE_PREFIXES` (which also yields
  `docs/dev/tmp/`, the default sink's own home — reusing the plural form
  would make every default-sink run refuse itself). `repo_root /
  STORE_PREFIX`, `samefile`-compared against each existing ancestor,
  replaces today's hand-rolled `repo_root / "docs/dev/project-management"`
  path (the "string is_relative_to check" the PRD's Problem section calls
  out as insufficient). The "Next likely change 3" bullet in Risks below
  is corrected to match: a future second `STORE_PREFIXES` entry does NOT
  automatically become store-forbidden ground for case 1 — only a change
  to `STORE_PREFIX` itself would.
- `git rev-parse --absolute-git-dir` / `--git-common-dir` / `--show-toplevel`
  — no existing wrapper for these three specifically; `cli.dirty_tree._git`
  (a thin `subprocess.run` wrapper) is reused to invoke them rather than
  adding a second git-subprocess helper. Searched: `absolute-git-dir`,
  `git-common-dir`, `rev-parse` — only `_git`, `_store_roots`,
  `_log_rel_and_tracked` exist; none covers git-directory identity.
- `os.path.samefile` (stdlib) for case 1 — nothing found attempting
  inode-identity comparison anywhere in `cli/`; searched `samefile`,
  `st_ino`, `identity`.
- No existing `_open_log_sink`-shaped helper; searched `O_EXCL`,
  `O_NOFOLLOW`, `os.open(`, `exclusive` — nothing found. `_run_locked_gate`'s
  plain `open(log_path, "wb", buffering=0)` is the only existing log-open
  site and is what this PRD replaces.

## Alternatives considered

1. **Smallest diff: extend `_refuse_verify_log` in `__main__.py` only,
   leave `verification.py` untouched.** Closes the CLI path but not the
   PRD's explicit requirement ("so a library caller cannot bypass the
   CLI") — `run_gate` stays directly callable with an unchecked `log_path`
   and `_run_locked_gate`'s plain `open(..., "wb")` still truncates
   through a pre-existing hard link even if the CLI itself now refuses.
   Rejected: fails a Must-have.
2. **Duplicate the six-case logic once in `__main__.py` and once in
   `verification.py`, no shared module.** Avoids a new file. Rejected:
   the six cases (especially the git-directory identity resolution and the
   symlink walk) are exactly the kind of logic that drifts between two
   copies under later edits; a PRD fixing a security refusal should not
   create a second place the same refusal can rot. The shared
   `log_sink_refusal.refuse` costs one small new file and removes the
   duplication risk entirely.
3. **Chosen: shared `log_sink_refusal.refuse`, called from both
   `__main__._refuse_verify_log` (CLI, printing) and
   `verification._refuse_verify_log_path` (library, silent, folded into
   `_dirty_result`).** One definition of "safe", two call sites matching
   the PRD's two enforcement points (`_refuse_verify_log` pre-flight and
   `_lock_and_check` inside the lock).

## Risks & edge cases

- **Race between the identity checks and `_open_log_sink`'s open, on the
  LEAF component.** The PRD's checks run, then (CLI path) `run_gate` is
  called, which re-checks inside the lock, then opens. A symlink or hard
  link planted at the leaf in the narrow window between the check and
  `_open_log_sink`'s `os.unlink` + `open` is the TOCTOU case `O_EXCL` +
  `O_NOFOLLOW` closes on that single component: the final `open()` itself
  fails on a symlink (`O_NOFOLLOW`) or a file that reappeared after unlink
  (`O_EXCL`).
- **Race on a PARENT directory, not just the leaf.** A pathname-based
  open is not enough even with `O_EXCL`/`O_NOFOLLOW` on the leaf: if
  `log_path`'s PARENT directory (e.g. `docs/dev/tmp`) is itself swapped
  for a symlink to `.git` in that same window, the leaf open still
  resolves through the swapped parent and lands inside `.git`, with
  `O_NOFOLLOW` blind to it (the leaf name itself may be an ordinary
  non-symlink file once resolved through the hijacked parent). This is
  why `_open_log_sink` (above) pins the parent as a directory file
  descriptor via no-follow `openat`-style traversal BEFORE unlinking or
  opening the leaf, rather than re-resolving the parent pathname at open
  time.
- **Next likely change 1**: a `--log` flag on another verb (`review-stage`
  already takes gate-adjacent flags) would want the same refusal; the
  shared `log_sink_refusal.refuse(log_path, repo_root)` module is already
  verb-agnostic (no `verify`-specific state), so adding a second call site
  does not require touching this PRD's code.
- **Next likely change 2**: Windows/non-POSIX support would break the
  `0o111` executable-bit check and hard-link semantics; out of scope here
  (the project is POSIX-only today, no change boxes this in further than
  it already was).
- **Next likely change 3**: a future `STORE_PREFIX` change (not a
  `STORE_PREFIXES` addition — see § Reuse inventory's correction) is the
  one thing case 1 would need to pick up; a plain `STORE_PREFIXES`
  addition is deliberately NOT picked up automatically, since that tuple
  also holds `docs/dev/tmp/`.
- **Edge case**: `--repo-root` pointing above the actual git toplevel (a
  monorepo parent dir) — case 1's git-directory probes run `git
  rev-parse` from `repo_root`, which git resolves to the containing repo
  regardless of subdirectory depth, so this holds without special-casing;
  this is also exactly what `test_git_dir_identity_holds_from_a_subdirectory_cwd`
  pins.
- **Edge case**: the default sink path (`docs/dev/tmp/gate-<sha7>.log`)
  is itself inside the store's second prefix (`docs/dev/tmp/`, per
  `STORE_PREFIXES`); case 1's store-identity check must compare against
  `docs/dev/project-management` ONLY (per the PRD's case 1 wording — "the
  store directory" singular, meaning the project-management keeper tree),
  not `docs/dev/tmp`, or every default-sink run would refuse itself. The
  PRD's own fixture (`docs/dev/tmp/gate-hl.log`) and the "default sink...
  goes through the same checks" line confirm `docs/dev/tmp` is checked for
  tracked/symlink/hardlink but is NOT itself store-forbidden ground.

## Test strategy outline

Fourteen tests in `skills/run-autopilot/cli/test_verify_log_refusal.py`,
against a fixture repo (one committed source file, a committed
`docs/dev/tmp/` ignore rule, a committed store state file carrying a marker
string) exactly as named under the PRD's Implementation section and
modeled on the nine carried-over tests shown on branch
`fast-track/00306-refuse-tracked-verify-log-v1-c1` (same fixture shape,
same `_git`/`_commit`/`_verify` helpers). New in this PRD beyond that
branch's nine:

- `test_cli_refuses_hardlinked_log` — `os.link` the committed store state
  file to a `docs/dev/tmp` sink, assert exit 2 and the marker string
  intact (the fenced reproduction in the Problem section).
- `test_default_sink_symlink_is_refused` / `test_default_sink_hardlink_is_refused`
  — plant the link/hardlink at `docs/dev/tmp/gate-<sha7>.log` (the `<sha7>`
  computed from the fixture's HEAD) and run `verify` WITHOUT `--log`.
- `test_git_dir_identity_holds_from_a_subdirectory_cwd` — cwd in a
  subdirectory, `--repo-root <top> --log .git/config`.
- `test_log_into_another_repos_store_is_refused` — a second fixture repo,
  `--log` pointed at its store file via a relative path that resolves
  there from the first repo's cwd.
- **New beyond the PRD's fourteen** (closing gaps the codex design review
  found): `test_parent_dir_symlink_swap_is_refused` — monkeypatch
  `log_sink_refusal.refuse` to return `None` (simulating a check that
  already passed), then swap `docs/dev/tmp` for a symlink to `.git`
  before calling `_open_log_sink` directly; assert the open raises rather
  than landing inside `.git` (pins case 4(b)'s `_open_log_sink`-side
  defense: the pinned parent directory descriptor, not a pathname
  re-walk, closes this race — a real concurrent attacker is
  non-deterministic to pin, so this test fixes the order deterministically
  instead). `test_nested_repo_store_is_refused` — create a second,
  nested git repo under the first fixture's ignored
  `docs/dev/tmp/other/`, commit a marker file into the nested repo's own
  store-shaped path, and assert `--log docs/dev/tmp/other/<nested store
  path>` exits 2 via case 4(b)'s toplevel-mismatch check (the file passes
  cases 1-3 and the first repo's own `git ls-files`, since it is only
  tracked by the nested repo).

Sixteen tests total. Base-commit red/skip state (Phase 0 acceptance):
fifteen tests fail (today's code has none of the six cases except the
bare store prefix-string check), `test_cli_refuses_case_variant_store_path`
may instead SKIP when the filesystem under test is case-sensitive, and
`test_untracked_tmp_log_still_records` passes unchanged (today's happy
path already works and this design does not touch it) — this is the
PRD's own stated acceptance shape (nine-of-fourteen plus the untouched
happy path), extended by the two added tests, which are also red at base
(there is no parent-descriptor pinning or nested-repo check at all
today).

`skills/run-autopilot/cli/test_verification_dirty.py` and
`test_verify_truth.py` are the regression suites for `_lock_and_check`/
`_dirty_result` and the verify CLI's truth-telling; Phase 1's acceptance
runs all three files together so the new `_refuse_verify_log_path` branch
in `_lock_and_check` is proven not to change any existing dirty-tree
behavior (`rg -c '^def test_' test_verification_dirty.py` pinning the
test count unchanged, per the PRD).

## Review log

Dispatch 1 (claude) found 2 blockers (call-site `.resolve()` ordering made
case 3's symlink walk unreachable; a duplicate hardcoded JSON print at the
`_run_verify` call site, wrong text for 5/6 cases and missing `"log":
null`) — both fixed by changing `_run_verify` to pass the UNRESOLVED
candidate path through to both the refusal check and `run_gate`, and by
making `_refuse_verify_log` the sole printer of stderr+JSON. No
non-blockers or questions raised.

dispatch 1 (claude): cardinal-sin 0, blocker 2, non-blocker 0, question 0

Dispatch 2 (codex) found 3 blockers (parent-directory symlink-swap race
not closed by leaf-only `O_EXCL`/`O_NOFOLLOW`; a nested git repository
inside this repo's working tree not excluded by the toplevel-containment
check; the JSON `error` text built from a shorter string than the
required stderr line), 2 non-blockers (a reuse-inventory claim that
contradicts the design's own correct `STORE_PREFIX`-only scoping for
case 1; the CHANGELOG deliverable not restated in this design's own
scope), and 3 questions (ancestor-walk wording ambiguous about checking
only the nearest existing ancestor vs. every existing ancestor; whether
the "no lock taken" guarantee is CLI-only or also claimed for the
library path; whether the fail-first acceptance's happy-path exemption
contradicts the PRD). All 3 blockers fixed: `_open_log_sink` now pins
the parent directory via no-follow `openat`-style traversal before
unlink/create; case 4 gained a second sub-check comparing the log path's
own containing repo's toplevel against `repo_root`'s; the stderr/JSON
text now share one constructed message string. Both non-blockers and all
3 questions resolved by clarifying prose (§ Reuse inventory, § Risks
"Next likely change 3", case 1's ancestor-walk wording, § Data flow's new
"Lock-scope clarification" paragraph); the happy-path question needed no
change — the design's acceptance text already matched the PRD.

dispatch 2 (codex): cardinal-sin 0, blocker 3, non-blocker 2, question 3

Dispatch 3 (codex outage — a `codex exec` run on the verification prompt
produced no output for ~20 minutes with the process still alive; killed
and degraded to a Claude fallback reviewer per the skill's codex-outage
rule) verified all three blockers' fixes against the full revised design:
the `_open_log_sink` openat-chain correctly re-checks `O_NOFOLLOW` on
every level including the mkdir-then-reopen path for a missing
intermediate directory (the one unguarded point is the toplevel's own
first `os.open`, which has no parent `dir_fd` to anchor to — an inherent
root-of-chain limit, not a gap in the fix); case 4(b)'s `git -C <parent
dir> rev-parse --show-toplevel` re-probe correctly does NOT fire for a
deep subdirectory with no nested `.git` (git's upward walk lands on the
same outer toplevel); the stderr/JSON text now share one message string
verbatim. No stale `_store_roots`/`STORE_PREFIXES` reuse claims remain.
Zero open findings.

dispatch 3 (claude-fallback): cardinal-sin 0, blocker 0, non-blocker 0, question 0
