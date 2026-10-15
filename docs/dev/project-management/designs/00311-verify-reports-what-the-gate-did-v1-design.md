# Design: Make `autopilot verify` report what the gate did

## Architecture fit

All six defects live in the existing `verify` verb's call chain:
`cli/__main__.py::_run_verify` (verb-level exit/JSON) ->
`cli/verification.py::run_gate` (locked spawn/drain/reap, record write) ->
consumed by `cli/review_stage.py::run_gate_line` (the human `Tests:` line) and
by `skills/work/references/final-verification.md` (the exit-code contract the
work phase reads). No new module: this PRD tightens the existing gate-runner
boundary (`## Component Boundaries` in the capsule: "`run_gate` owns the
verification procedure, review only reads the record").

## Module placement

- Edit `skills/run-autopilot/cli/verification.py`: `_write_record`,
  `_record_shape_ok`, `_run_locked_gate`, `run_gate`, `_timed_out_result`,
  `_dirty_result`. New private helpers `_lock_timeout_result`,
  `_head_moved_result`.
- Edit `skills/run-autopilot/cli/__main__.py`: `_run_verify`,
  `_refuse_verify_log` (exit-2 JSON line only; no logic change to the
  refusal test itself).
- Edit `skills/run-autopilot/cli/review_stage.py`: `run_gate_line`.
- Edit `skills/work/references/final-verification.md`: restate the exit
  table (lines 163-173).
- Edit `CHANGELOG.md`: reword the line-22 `writer`-reuse claim; add Fixed
  entries under `[Unreleased]` / **run-autopilot**.
- New file `skills/run-autopilot/cli/test_verify_truth.py` (Phase 0, listed
  in `dev/bin/release-checks`' `[checks]` block).
- Add `"writer": "run_gate"` to every hand-built record dict in
  `test_verification_log_sink.py`, `test_verification_dirty.py`,
  `test_verification_dirty_symlink.py`, `test_verification_hidden_flags.py`,
  `test_verification_dirty_paths.py`, `test_cli_review_verbs.py`.

## Interfaces & contracts

**`_write_record(cwd, command, sha, cycle, result)`** (unchanged signature) —
the written dict gains one key:

```python
record = {
    "sha": sha,
    "cycle": cycle,
    "writer": "run_gate",
    "commands": [{"command": normalize_command(command), "exit": result["exit"]}],
    "passed": result["passed"],
    "failed": result["failed"],
    "skipped": result["skipped"],
}
```

**`_record_shape_ok(record, gate_command) -> bool`** (unchanged signature) —
add one more required-match line, evaluated alongside the existing sha/counts/
commands/green checks (order inside the function is free; the full predicate
is a conjunction):

```python
if record.get("writer") != "run_gate":
    return False
```

**`run_gate(command, cwd, sha, cycle, timeout=GATE_TIMEOUT_S, log_path=None) -> dict`**
(unchanged signature). Every returned dict — `_timed_out_result()`,
`_dirty_result()`, the two new shapes below, and `_record_gate()`'s dict —
now carries two more keys, `False` everywhere except the one shape each
names:

```python
"lock_timeout": False,
"head_moved": False,
```

Shown explicitly for the normal green/parsed-result path too —
`_record_gate`'s returned `result` dict (`cli/verification.py:502-512`)
gains the same two keys, both `False`, alongside its existing
`"dirty": dirty, "dirty_paths": dirty_paths` lines:

```python
result = {
    "passed": int(found.group(1)) if found else None,
    "failed": int(found.group(2)) if found else None,
    "skipped": int(found.group(3)) if found else None,
    "exit": returncode,
    "raw_line": raw_line,
    "timed_out": False,
    "recorded": False,
    "dirty": dirty,
    "dirty_paths": dirty_paths,
    "lock_timeout": False,
    "head_moved": False,
}
```

New result-shape helpers, same field set as `_timed_out_result`/
`_dirty_result` plus the two above:

```python
def _lock_timeout_result() -> dict:
    """Returned when the flock was never acquired by the deadline. Per the
    PRD's exact rule, `timed_out` is True only for a gate killed at its
    deadline (a gate that spawned and ran); a lock timeout never spawns a
    gate, so `timed_out` stays False here -- `lock_timeout` is the field
    that names this cause. This also keeps `_run_verify`'s `spawned` check
    correct with no special-case exclusion: `exit is None and timed_out is
    False` already means "no gate ever ran" for this shape."""
    return {
        "passed": None, "failed": None, "skipped": None, "exit": None,
        "raw_line": None, "timed_out": False, "recorded": False,
        "dirty": False, "dirty_paths": [],
        "lock_timeout": True, "head_moved": False,
    }

def _head_moved_result() -> dict:
    """Returned when HEAD no longer equals `sha` once the lock is held.
    Not a `dirty` result: the tree can be clean while HEAD itself moved
    (e.g. a concurrent commit), which is a different cause than a dirty
    working tree and must print its own line."""
    return {
        "passed": None, "failed": None, "skipped": None, "exit": None,
        "raw_line": None, "timed_out": False, "recorded": False,
        "dirty": False, "dirty_paths": [],
        "lock_timeout": False, "head_moved": True,
    }
```

`run_gate` wiring (replaces the two current refusal call sites):

- `_acquire_lock(lock_fd, deadline)` returning `False` -> `return
  _lock_timeout_result()` (was `_timed_out_result()`).
- `_lock_and_check` currently folds "tree dirty" and "HEAD moved" into the
  same `_dirty_result(...)` call. Split it: `_lock_and_check` keeps
  returning `(extra_excluded, refusal_or_None)`, but the HEAD-mismatch
  branch's `refusal` becomes a sentinel object (module-level
  `_HEAD_MOVED = object()`) instead of `_dirty_result([])`; `run_gate`
  checks `refusal is _HEAD_MOVED` first and returns `_head_moved_result()`,
  else (dirty-tree refusal) returns `refusal` unchanged. `_lock_and_check`'s
  own dirty-tree branch is untouched — it still returns `_dirty_result(dirty_paths)`.

**`_run_locked_gate`** and **`run_gate`**'s process-spawn/kill path — the
lock-fd-passing and signal-handling contract (PRD requirement, no existing
code to reuse):

```python
proc = subprocess.Popen(
    command, shell=True, cwd=cwd,
    stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    start_new_session=True,
    pass_fds=(lock_fd,),
)
```

`run_gate` passes its own `lock_fd` into `_run_locked_gate(..., lock_fd=lock_fd)`
(new parameter), which passes it through to `Popen(pass_fds=...)` above —
this keeps the flock held by the gate's own process group after the Python
holder is killed, so a second `verify` waiting on `_acquire_lock` still
blocks until the orphaned gate's group actually exits (the fd closes on
exit, releasing the flock; a dangling `lock_fd` with no live holder is
harmless, `fcntl.flock` is advisory per-fd).

Around the existing `_drain_bounded`/`_reap` call in `_run_locked_gate`,
wrap in `try/except BaseException` (not just `OSError` as today) that kills
the gate's process group and re-raises:

```python
old_handler = signal.getsignal(signal.SIGTERM)
def _raise_on_sigterm(signum, frame):
    raise RuntimeError("verify: SIGTERM during gate")
signal.signal(signal.SIGTERM, _raise_on_sigterm)
try:
    ... existing Popen + drain + reap ...
except BaseException:
    try:
        os.killpg(proc.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    proc.wait()
    proc.stdout.close()
    proc.stderr.close()
    raise
finally:
    signal.signal(signal.SIGTERM, old_handler)
```

This replaces the current narrower `except OSError` block (the log-sink
write-error path): the new `except BaseException` block subsumes it — same
kill-reap-reraise body, now also triggered by the installed SIGTERM handler's
`RuntimeError` and by a `KeyboardInterrupt`/`SystemExit` from a SIGKILL
delivered to the Python process itself (SIGKILL cannot be handled, but if the
process is merely interrupted before SIGKILL lands, or receives SIGTERM, this
is the path that still reaps the gate). The handler install/restore brackets
the whole `Popen`-through-`_reap` region, inside `_run_locked_gate`'s existing
`try/finally` that closes `log_file`.

**`run_gate_line(repo_root, gate_command, cycle_id) -> dict`** (unchanged
signature) — two new branches before the existing `dirty`/`timed_out`/
`passed is None` chain, checked in this order (lock_timeout and head_moved
are mutually exclusive with dirty/timed_out by construction, since they are
now their own result shapes, not folded into `dirty`/`timed_out`):

```python
if result["lock_timeout"]:
    line = f"Tests: (gate skipped: another gate held the lock for {int(verification.GATE_TIMEOUT_S)}s)"
elif result["head_moved"]:
    line = "Tests: (gate skipped: HEAD moved during the lock wait)"
elif result["dirty"]:
    line = "Tests: (gate skipped: working tree dirty outside the store)"
... (existing timed_out / passed is None / else chain, unchanged) ...
```

The returned dict already carries `"log": str(log_path)`; add `"dirty_paths":
result["dirty_paths"]` to it unconditionally (today only `result["dirty"]`
is read, the paths are dropped) so a caller can always read which paths were
dirty, not only when the `dirty` line already names "the store" generically.

**`_run_verify(args) -> int`** (`cli/__main__.py`), new exit rule — read the
printed JSON's own fields, not the process returncode, to decide red vs green.
One final code block (no intermediate "simplify" version — this is the whole
function body change):

```python
summary_exit = None
if result.get("raw_line"):
    m = re.search(r"EXIT (\d+)", result["raw_line"])
    if m:
        summary_exit = int(m.group(1))
is_red = (result.get("failed") or 0) > 0 or (summary_exit not in (None, 0))
spawned = result["exit"] is not None or result["timed_out"]
printed_log = str(log_path) if spawned else None
print(json.dumps({**result, "sha": head, "log": printed_log}))
if result["lock_timeout"] or result["head_moved"] or result["timed_out"] or result["dirty"]:
    return 1
if is_red:
    return 1
return 0 if result["recorded"] else 3
```

`"log": null` iff no gate spawned (`exit is None and not timed_out`) — a
lock timeout has `exit is None` and (per the fix above) `timed_out is
False`, so it correctly falls into "no gate spawned" without any special
case. The `spawned`/`printed_log` pair above is the PRD's exact rule, and
the `log` decision is independent of `is_red`'s exit-code decision below it.

`is_red` reuses `result["raw_line"]` (already parsed by `_parse_summary` in
`verification.py`, already present on every non-timeout/non-refusal result
dict) rather than re-running `SUMMARY_RE` — same regex, single source
(`verification.SUMMARY_RE`), imported into `__main__.py` (already imports
`verification`).

Both stderr-only refusal sites in `_run_verify` additionally print the JSON
line on stdout before returning 2:

```python
# cannot resolve HEAD (both OSError and non-zero-returncode branches)
msg = f"cannot resolve HEAD in {repo_root}: {err_or_stderr}"
print(f"autopilot: verify: {msg}", file=sys.stderr)
print(json.dumps({"error": msg, "exit": 2}))
return 2

# _refuse_verify_log
if _refuse_verify_log(log_display, repo_root, log_path):
    print(json.dumps({"error": f"--log {log_display} resolves inside the store", "exit": 2}))
    return 2
```

`final-verification.md` exit table (replaces lines 163-173's prose):

```
autopilot verify exit codes:
  0 - gate ran green and the record was written
  1 - gate red (parsed FAIL > 0 or EXIT token non-zero, whatever the
      process exit), timed out, lock timeout, HEAD moved during the lock
      wait, or the tree was dirty before the gate could spawn
  2 - refusal (one JSON line with "error" and "exit": 2) - a tracked --log
      inside the store, or HEAD could not be resolved
  3 - the gate exited 0 and did not time out, but no summary line was
      parsed, or the tree dirtied mid-run (record not written)
```

CHANGELOG line 22 reworded (same bullet, corrected claim): "a hand-written
or pre-upgrade `last-verification.json` (missing the `writer: run_gate`
marker) is never reused — `autopilot verify` always reruns the gate for it."
New `[Unreleased]` / `### Fixed` entries, one per defect: the exit rule, the
writer marker, the orphaned-gate kill, and the lock-timeout/HEAD-moved
labels.

## Data flow

`_run_verify` resolves HEAD -> calls `run_gate` (holds the flock for the
whole wall-clock budget) -> `run_gate` returns one of five result shapes
(`_lock_timeout_result`, `_head_moved_result`, `_dirty_result`,
`_timed_out_result`, or `_record_gate`'s parsed-and-maybe-recorded dict) ->
`_run_verify` derives its exit code from the result's own fields (never the
subprocess returncode alone) and prints the JSON line (or the refusal JSON
on an early exit-2 path) -> `review_stage.run_gate_line` later reads
`last-verification.json` via `reuse_verdict` (gated by `_record_shape_ok`,
now including the `writer` check) or calls `run_gate` fresh, and turns the
result into one human `Tests:` line, picking among the five shapes in the
documented order.

## Reuse inventory

- `verification.SUMMARY_RE` (`cli/verification.py:37`) — reused directly in
  `__main__.py`'s new red/green check instead of re-deriving the pattern;
  `_run_verify` already imports the `verification` module.
- `_parse_summary`'s `raw_line` (`cli/verification.py:478-486`) is already
  threaded onto every result dict `_record_gate` returns — the new exit rule
  reads that existing field rather than adding a new one.
- `os.killpg(proc.pid, signal.SIGKILL)` / `ProcessLookupError` tolerance
  already exists twice in this file (`_reap`, the log-sink `except OSError`
  block) — the new `except BaseException` block reuses the identical
  kill-reap pattern rather than inventing a new one.
- Searched for an existing process-group/signal helper module to reuse
  instead of inlining the SIGTERM handler: `rg -n "signal.signal|SIGTERM"
  skills/` — only this file's two existing `SIGKILL` sites (above); no
  shared helper exists, nothing to reuse beyond the pattern itself.
- Searched for an existing "writer marker" / provenance-stamp convention
  elsewhere in the repo to reuse its key name: `rg -n '"writer"'
  skills/run-autopilot/cli/*.py` and `rg -n "writer_marker|record_writer"
  skills/` — nothing found; `"writer"` is a new, PRD-named field.

## Alternatives considered

1. **Smallest diff: patch only `_run_verify`'s exit derivation and the
   `writer` marker; leave the lock/signal/label work for a follow-up PRD.**
   Rejected as shipped scope (the PRD's Must-haves name all six defects
   together, and `final-verification.md`'s exit table would otherwise
   document labels the code cannot yet produce) — but if forced to cut, this
   is the slice to keep: it fixes the two defects agoge rated as currently
   misleading the work phase (silent false-green, stale-record reuse), at
   roughly a third of the diff.
2. **Wrap the gate's own `Popen` in a watchdog thread that polls the lock
   file's holder-pid instead of `pass_fds`.** Rejected: a pid-based watchdog
   is itself racy (pid reuse after the holder exits) and needs its own
   polling loop and thread lifecycle; `pass_fds` is zero extra code and the
   flock's kernel-enforced exclusivity needs no polling.
3. **Chosen: fix all six call-chain defects together, reusing the existing
   `_timed_out_result`/`_dirty_result` shape family for the two new result
   kinds and threading one more boolean pair through every shape.** Larger
   than option 1, but the extra size buys a single coherent exit-code
   contract that `final-verification.md` can state once and that the
   doubt-lens's six reproductions (Problem section) each flip in the same
   PRD, rather than leaving some labeled "red" generically while others gain
   named causes.

## Risks & edge cases

- **Edge case — `EXIT` token present but `failed == 0`** (a gate that prints
  `PASS 4 FAIL 0 SKIP 0 EXIT 1`, e.g. a suite that passed but the wrapper
  script itself hit an unrelated post-suite error): `is_red` still fires on
  the non-zero `EXIT` token alone, matching the PRD's "whatever the gate
  process exited" wording — this is intentional, not a bug to special-case.
- **Edge case — SIGKILL of the `verify` process itself.** SIGKILL cannot be
  handled; the installed SIGTERM handler and `BaseException` wrapper cannot
  run. The orphan-survival guarantee comes entirely from `pass_fds`: the
  gate's own process group keeps the flock via the inherited fd even though
  nothing in Python ever runs a kill. This is why the PRD's acceptance test
  (`test_sigkilled_verify_leaves_no_overlapping_gate`) asserts via the lock,
  not via a handler — document this plainly in the function docstring so a
  future reader does not "fix" the missing SIGKILL handler.
- **Likely next change 1**: a `--json-only` or machine-readable mode that
  suppresses the human stderr lines entirely for CI consumption — the new
  `{"error": ..., "exit": 2}` stdout line on refusals is a step toward that;
  this design does not remove the stderr duplication, so a future PRD can
  still choose either direction without this one boxing it in.
- **Likely next change 2**: review-stage's five-way `Tests:` line chain
  (`dirty` / `timed_out` / `lock_timeout` / `head_moved` / `passed is None` /
  green) is getting long; a follow-up could collapse it to a lookup table
  keyed by result shape. This design keeps the existing if/elif chain style
  (matches the file's current idiom) rather than introducing a table now,
  so that refactor stays a pure follow-up with no behavior change bundled
  in.
- **Risk**: the `except BaseException` block, if the kill-and-reraise itself
  raises (e.g. `proc.wait()` hangs), could leave `log_file` unclosed longer
  than intended. Mitigated by leaving it inside `_run_locked_gate`'s existing
  outer `try/finally` that closes `log_file` unconditionally — unchanged by
  this design, just confirmed still enclosing the new block.

## Test strategy outline

All six reproductions from the PRD's Problem section become the Phase 0
fixture file `test_verify_truth.py`, written and run red against the base
commit first (per the repo's standing fail-first contract for regression
tests): a fixture repo with a small scripted "gate" script per test
(inline shell one-liners via a temp executable, matching the existing
`test_verification_*.py` fixtures' style — `rg -n "def _repo\|tmp_path" skills/run-autopilot/cli/test_verification_dirty.py` for the pattern to follow). Phase 1 makes
the production code pass those tests plus the existing verification test
files (updated with the `writer` key so they do not regress). Phase 2 wires
the human-facing line and the doc/CHANGELOG text and pins it with a direct
`rg` count, matching the PRD's own acceptance commands verbatim (no new
test-running convention introduced).

## Review log

work-phase correction (post-dispatch-3, found by Ivan during task 1):
`_lock_timeout_result()` originally set `timed_out: True` (dispatch 3's own
fix assumed this and special-cased `spawned` to exclude `lock_timeout`).
Ivan, writing `test_verify_truth.py` from the PRD's Contract verbatim
(never the design), correctly built `test_lock_wait_expiry_reports_lock_timeout`
to assert `timed_out is False` -- the PRD's Solution paragraph states
"timed_out is True only for a gate killed at its deadline," and a lock
timeout never spawns a gate. The PRD is the authority on this point (task
Contracts are copied from the PRD verbatim precisely so a PRD/design
conflict surfaces here rather than silently). Fixed: `_lock_timeout_result`
now sets `timed_out: False`; the `spawned` check in `_run_verify` reverts
to its plain, unconditional form (`exit is None and not timed_out`) with
no special case, since a lock timeout's `exit` and `timed_out` already
read as "no gate ever spawned." All three review dispatches missed this
because none diffed the design's `_lock_timeout_result` prose against the
PRD's Solution-paragraph sentence word-for-word -- recorded here as a
design-review gap, not re-litigated.

dispatch 1 (claude): cardinal-sin 0, blocker 1, non-blocker 2, question 2
- Blocker (fixed): `## Interfaces & contracts` showed two contradictory
  versions of `_run_verify`'s body (a full exit-ladder block, then a
  "simplify the log decision" aside with a second, narrower snippet),
  leaving a planner unsure which to implement. Collapsed to one final code
  block carrying the `is_red` computation, the `spawned`/`printed_log`
  derivation, the print, and the full return ladder together.
- Question (recorded, not fixed): the design showed the `lock_timeout`/
  `head_moved` `False` defaults as literal dict lines for three of four
  result shapes but only asserted the fourth (`_record_gate`'s normal
  green-path dict) in prose — added the literal lines for that shape too
  (judged worth fixing inline since it is a one-line addition matching the
  other three shapes already shown, not a scope change).
- Non-blocker: the exit table's "pre-spawn dirt" (exit 1) vs "tree dirtied
  mid-run" (exit 3) distinction relies on an unstated invariant — mid-run
  dirtiness never sets `result["dirty"]=True` (that flag is reserved for
  `_lock_and_check`'s pre-spawn refusal only; `_record_gate`'s own `dirty`
  key, read by `run_gate_line` for its unrelated `Tests:` line, is a
  separate post-reap check that `_run_verify`'s ladder does not consult —
  `_run_verify` falls through to exit 3 via `recorded=False` instead).
  Recorded for the implementor's awareness; not changed in the design since
  the existing code already has this shape and the design does not alter it.
- Non-blocker: `pass_fds`-based lock survival across a `shell=True`
  intermediate `/bin/sh` is asserted but not walked through explicitly —
  the fd is inherited across `fork`+`exec` by default (no `O_CLOEXEC` is
  set, and `pass_fds` explicitly whitelists it through `close_fds=True`),
  so the intermediate shell and whatever it execs both hold it until the
  real gate process exits; left as a design note rather than a text change,
  since `## Risks & edge cases` already covers the SIGKILL case this
  mechanism exists for.
- Non-blocker: SIGTERM-during-exec timing granularity (signal landing
  between `signal.signal()` and `Popen()`, or during a C-level `wait()`)
  is not addressed; acceptable per Python's best-effort, line-boundary
  signal delivery — flagged for implementor awareness, not a design defect.

dispatch 2 (claude-fallback — codex's background run produced no parseable
findings, output cut off mid-sentence; degraded per the outage rule):
cardinal-sin 0, blocker 1, non-blocker 1, question 2
- Blocker: same duplicate/conflicting `log`-derivation snippet dispatch 1
  already flagged and this design already fixed (above) — confirms the
  fix, no further change needed.
- Non-blocker: flagged the same missing `_record_gate` literal-keys gap
  dispatch 1's question already prompted fixing — already resolved above.
- Question (recorded, not fixed): the early-return ladder in `_run_verify`
  (lock_timeout/head_moved/timed_out/dirty -> 1) makes `is_red`'s own check
  of those same conditions unreachable for those four shapes — correct but
  redundant control flow; worth a one-line comment at implementation time,
  not a design change.
- Question (recorded, not fixed): mutual exclusivity of the four boolean
  flags relies on code-review discipline, not a type system; the Phase 0
  test suite's per-shape assertions already cover this implicitly, no
  design change needed.

dispatch 3 (claude-fallback — both codex attempts produced no parseable
findings; this dispatch's first codex run was blocked by its own sandbox's
fact-forcing hook mid-run and cut off, degraded per the outage rule):
cardinal-sin 0, blocker 1, non-blocker 0, question 0
- Blocker (fixed): `_lock_timeout_result()` sets `exit=None, timed_out=True`.
  The `spawned` check (`result["exit"] is not None or result["timed_out"]`)
  therefore read `spawned=True` for a lock-timeout too, so `printed_log`
  named the *previous* run's log path even though no gate process ever
  spawned (the flock was never acquired) — silently reproducing the exact
  "pre-spawn refusal names a stale log" defect this PRD exists to fix.
  `_timed_out_result` (a gate that *did* spawn and ran to its deadline) is
  correctly `spawned=True` and must stay that way; only `lock_timeout` needs
  excluding. Fixed: `spawned = result["exit"] is not None or
  (result["timed_out"] and not result["lock_timeout"])`.
- No cardinal sins, no other blockers: the collapsed `_run_verify` block is
  confirmed internally consistent (one version, no contradiction — dispatch
  1/2's duplicate-snippet fix holds); the writer marker, pass_fds/SIGTERM
  kill-and-reraise, dirty_paths threading, exit-table wording and CHANGELOG
  rewording were all re-checked against the PRD's Must-haves and found
  consistent.

dispatch 2's codex attempt and dispatch 3's codex attempt both failed the
minimum-engagement check by producing no parseable output (the first cut off
mid-sentence after an opening acknowledgement, the second was blocked by its
own sandbox's fact-forcing hook partway through reading an unrelated skill
file) — both degraded to the Claude fallback per the codex-outage rule, not
marked WEAK (a WEAK mark is for an engaged-but-shallow review; these simply
never ran to completion, which is an outage, not weak engagement).

result: ok

