# Design: 00322-kill-the-gate-on-every-signal-v1

## Architecture fit

All four leaks sit in the `run-autopilot` CLI's process layer, not its
state/orchestration layer: `verification.py` (the gate spawn/drain/reap under
`fcntl.flock`) and the replay runner used by `review-work-completion`'s
mechanical checks (`replay_tests_against_base.py`, driven by
`review_stage.py`'s `_append_mech_blocks`/`_run_script`). Neither touches
`state.json`; the fix is confined to signal handling around two `Popen`
call sites and one lock-wait/gate-timeout split. No new module, no new
layer — the existing `_SigtermGuard`/`_deferred_sigterm` contextmanager
pattern in `verification.py` already proves the shape (defer before the
gate starts, raise once it has); this PRD widens it to three signals and
duplicates the same shape once more in the replay runner, which has no
guard today.

## Module placement

- Edit `skills/run-autopilot/cli/verification.py`: rename/generalize
  `_SigtermGuard` → `_SignalGuard`, `_deferred_sigterm` → `_deferred_signals`;
  delete `_child_from_exception` and `_POPEN_TYPE`; `_spawn_gate` assigns
  `proc` inside the guarded region, unchanged structurally; `run_gate`,
  `_gate_under_lock`, `_acquire_lock`, `_lock_timeout_result`,
  `_timed_out_result`, `_head_moved_result`, `_dirty_result` gain
  `waited_s`; new module constant `GATE_LOCK_TIMEOUT_S`.
- Edit `skills/run-autopilot/cli/__main__.py`: `_run_verify` catches the
  guard's exception type and prints the one-line JSON instead of a
  traceback.
- Edit `skills/review-work-completion/scripts/replay_tests_against_base.py`:
  add `_SignalRaised` + `_raise_on_signal`; `_run_in_worktree` wraps the
  `communicate()` call and adds one `except` branch.
- Edit `skills/run-autopilot/cli/review_stage.py`: `_run_script` is
  rewritten from `subprocess.run(timeout=...)` to a manual
  `Popen`/`communicate` with a SIGTERM-then-grace-then-SIGKILL escalation
  (new constants `SCRIPT_TIMEOUT_S`, `SCRIPT_GRACE_S`); the one caller in
  `_append_mech_blocks` that invokes `REPLAY_SCRIPT` passes `--timeout 480`
  to the replay subprocess.
- No new files. Tests land in the three existing files the PRD names
  (`test_verify_truth.py`, `test_replay_timeout_kill.py`,
  `test_review_stage.py`).

## Interfaces & contracts

### `verification.py`

```python
GATE_LOCK_TIMEOUT_S = 600  # seconds the lock wait gets, separate from the gate's own timeout

class _SignalGuard:
    def __init__(self) -> None:
        self.gate_started: bool = False
        self.pending_signum: int | None = None
        # True from the moment a signal has triggered (or is triggering)
        # cleanup, through _kill_gate's killpg+wait. A signal arriving
        # while this is True is recorded, never re-raised — a second
        # SIGTERM landing inside _kill_gate must not interrupt the kill
        # or the reap, or the gate's process group can survive the first
        # signal's own cleanup and the flock release never runs.
        self.cleaning: bool = False

    def handle(self, signum: int, frame) -> None:
        """Before the gate starts, or while `cleaning` is True: record
        `pending_signum` (first one wins) and return. Once started and
        not cleaning: set `cleaning = True` and raise `_signal_error(signum)`
        directly — the one and only transition into cleanup."""

    def raise_if_pending(self) -> None:
        """If a signal arrived during spawn (`pending_signum` set) and
        cleanup has not already started: set `cleaning = True` and raise
        `_signal_error(self.pending_signum)`. No-op otherwise."""


def _signal_error(signum: int) -> RuntimeError:
    """RuntimeError("verify: <SIGNAME> during gate") — SIGNAME via
    `signal.Signals(signum).name`."""


@contextmanager
def _deferred_signals(signums: tuple[int, ...]):
    """Installs `_SignalGuard.handle` for every signum in `signums`,
    restoring each previous handler on exit. A no-op off the main thread
    (signal.signal cannot install there). Yields the guard."""
```

`_deferred_sigterm` is deleted; every caller becomes
`_deferred_signals((signal.SIGTERM, signal.SIGINT, signal.SIGHUP))`.
`_child_from_exception` and `_POPEN_TYPE` are deleted outright — no
replacement symbol, since `proc` is always a real `Popen` once this fix
lands (see Data flow).

```python
def _spawn_gate(command, cwd, deadline, log_file, lock_fd) -> tuple[int | None, bytes, bool]:
    """Unchanged signature and return shape. Body: `with _deferred_signals(
    (signal.SIGTERM, signal.SIGINT, signal.SIGHUP)) as guard:` wraps the
    same try/except as today, with one added line:
    `except BaseException: guard.cleaning = True; _kill_gate(proc); raise`
    — `proc` is always a real Popen or None at that point, never recovered
    from a traceback. Setting `guard.cleaning = True` before `_kill_gate`
    closes the dispatch-2 finding that a second signal landing inside
    `_kill_gate`'s killpg+wait could otherwise re-enter the handler and
    raise again mid-cleanup, interrupting the kill or the reap and
    breaking the gate-death/flock-release guarantee; with `cleaning` set,
    a second signal during cleanup is recorded (and dropped once cleanup
    finishes and the `with` block exits) rather than re-raised."""
```

```python
def run_gate(
    command: str,
    cwd: Path,
    sha: str,
    cycle: int | None,
    timeout: float = GATE_TIMEOUT_S,
    log_path: Path | None = None,
    lock_timeout: float = GATE_LOCK_TIMEOUT_S,
) -> dict:
    """New keyword `lock_timeout`. The lock wait is bounded by
    `lock_timeout`, independent of `timeout`; once the lock is acquired,
    the gate's own `deadline = time.monotonic() + timeout` is computed
    fresh (not inherited from the lock-wait budget), so a late waiter
    still gets the full `timeout` for its gate. Every returned dict gains
    `waited_s: float` — seconds spent in `_acquire_lock`, including the
    `_lock_timeout_result()` shape."""
```

```python
def _acquire_lock(lock_fd: int, deadline: float) -> bool:
    """Unchanged body; `deadline` is now the lock-wait deadline
    (`wait_start + lock_timeout`), computed in `run_gate`, never the
    combined lock+gate deadline."""


def _gate_under_lock(
    command: str, cwd: Path, sha: str, cycle: int | None,
    timeout: float, log_path: Path | None, lock_fd: int,
    lock_deadline: float, wait_start: float,
) -> dict:
    """New params `lock_deadline`/`wait_start` replace the single
    `deadline` this function took before. `waited_s = time.monotonic() -
    wait_start`, computed once right after `_acquire_lock` returns (success
    or failure) and attached to whichever result this function returns.
    On success, computes `gate_deadline = time.monotonic() + timeout`
    before calling `_lock_and_check`/`_run_locked_gate` (the pre-spawn
    dirty/HEAD checks now run inside the gate's own budget, not the
    lock-wait budget — a one-cycle shift in semantics the PRD's `waited_s`
    requirement makes necessary and no test pins the old boundary)."""
```

Every result builder gains a `waited_s: float` parameter and field:
`_timed_out_result(waited_s)`, `_lock_timeout_result(waited_s)`,
`_head_moved_result(waited_s)`, `_dirty_result(dirty_paths, waited_s)`.
`_record_gate`'s returned dict (used by `_run_locked_gate`) does not take
`waited_s` itself — `_gate_under_lock` attaches it to that dict after the
call returns, same as for the refusal/head-moved shapes, so every exit
path sets the field exactly once, in `_gate_under_lock`.

### `__main__.py`

```python
def _run_verify(args) -> int:
    """Wraps the existing `verification.run_gate(...)` call in
    `try: ... except RuntimeError as exc:` — matching `_signal_error`'s
    message shape (`str(exc).startswith("verify: ")`) — and on that
    branch prints `json.dumps({"error": str(exc), "exit": 2, "log": str(log_path) if log_path.exists() else None})`
    and returns 2. No traceback. The existing `except OSError` branch
    (log-sink open failures) is unchanged and stays a separate branch —
    a `RuntimeError` from the signal guard and an `OSError` from the log
    sink are distinguishable causes with the same exit code."""
```

### `replay_tests_against_base.py`

**Two-phase guard, same shape as `verification._SignalGuard`** — the
dispatch-2 review correctly rejected a bare "raise immediately" handler
here: a signal landing while `Popen()` is still mid-syscall (before `proc`
is bound) or while the kill-and-reap cleanup is running would otherwise
either escape uncaught (default disposition, no `finally` chance) or
re-enter the handler and interrupt the cleanup itself.

```python
class _SignalRaised(Exception):
    def __init__(self, signum: int) -> None:
        super().__init__(signum)
        self.signum = signum


class _ReplaySignalGuard:
    def __init__(self) -> None:
        self.spawned: bool = False   # True once `proc` is bound
        self.pending_signum: int | None = None
        self.cleaning: bool = False  # True while kill+communicate cleanup runs

    def handle(self, signum: int, frame) -> None:
        """Before spawn, or while cleaning: record `pending_signum` and
        return. Once spawned and not cleaning: set `cleaning = True` and
        raise `_SignalRaised(signum)`."""

    def raise_if_pending(self) -> None:
        """Mirrors `_SignalGuard.raise_if_pending` — raises the recorded
        signal, once, if one arrived before `spawned` was set."""


@contextmanager
def _raise_on_signal(signums: tuple[int, ...]):
    """Installs `_ReplaySignalGuard.handle` for every signum in `signums`,
    restoring the previous handlers on exit. Wraps the Popen call itself,
    not just `communicate()` — a signal cannot leak a child by arriving
    before the guard is up, only by arriving before this contextmanager is
    entered (the same irreducible gap `_deferred_signals` has: the
    function's own entry, before any handler exists at all; nothing
    upstream of `replay()` sends a signal in that single-statement
    window). Yields the guard."""
```

`_run_in_worktree`'s Popen/communicate block moves inside the guard, and
every cleanup branch sets `guard.cleaning = True` as its first line —
sequentially, before the synchronous killpg+communicate it guards, so a
second signal arriving during that narrow window is recorded and dropped
(the `with` block exits right after the branch's `return`), never
re-raised into the middle of the kill:

```python
    proc = None
    try:
        with _raise_on_signal((signal.SIGTERM, signal.SIGHUP)) as guard:
            try:
                proc = subprocess.Popen(argv, cwd=worktree, stdout=subprocess.PIPE,
                                         stderr=subprocess.PIPE, text=True, start_new_session=True)
                guard.spawned = True
                guard.raise_if_pending()
                stdout, stderr = proc.communicate(timeout=timeout)
            except subprocess.TimeoutExpired:
                guard.cleaning = True
                try:
                    os.killpg(proc.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                proc.communicate()
                return "", f"runner did not complete: timed out after {timeout} seconds"
            except _SignalRaised as exc:
                guard.cleaning = True
                if proc is not None:
                    try:
                        os.killpg(proc.pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                    proc.communicate()
                return "", f"runner did not complete: killed by {signal.Signals(exc.signum).name}"
    except OSError as exc:
        return "", f"runner did not complete: {exc}"
```

**Dispatch-3 fix:** `guard.spawned = True` and `guard.raise_if_pending()`
must sit *inside* the same `try` the `except _SignalRaised` branch
covers, not between that `try` and the outer `with` — dispatch 3 (codex)
correctly caught that the previous draft placed them outside the inner
`try`, so a signal `raise_if_pending()` itself raised would propagate
straight past the `_SignalRaised` handler (which only wrapped
`communicate()`) to the outer `except OSError`, which does not match it,
leaking the runner exactly as before. With the fix, every statement from
`Popen()` through `communicate()` — including the `spawned` transition
and the pending-signal check — runs under the one `try` whose
`except _SignalRaised` does the kill; `proc` is guarded with `if proc is
not None` because a signal that arrives and is deferred *before* `Popen()`
assigns `proc` (then raised by `raise_if_pending()` the instant `spawned`
flips true) cannot reach this branch with `proc` unset — the guard
replays the exact "defer then raise once spawned" contract `_SignalGuard`
uses for the gate, now actually wired to cover the right statements. (The
pre-existing `except OSError` stays outside the `with`, unchanged in
behavior — an `OSError` from `Popen()` itself means no child exists to
kill, matching today's code exactly.) The function's existing `finally:`
(worktree remove + `shutil.rmtree`) is untouched and still runs on every
path, including the new `_SignalRaised` branch.

### `review_stage.py`

```python
SCRIPT_TIMEOUT_S = 540  # seconds; below the Bash tool's 600s ceiling that
                        # bounds `_append_mech_blocks`'s whole caller
SCRIPT_GRACE_S = 30     # seconds given to a SIGTERM'd helper to run its
                        # own cleanup (replay's worktree removal) before
                        # the outer caller escalates to SIGKILL

def _run_script(script: Path, args: list[str], cwd: Path, timeout: float = SCRIPT_TIMEOUT_S) -> str:
    """Rewritten off `subprocess.run(timeout=...)` — dispatch 2 (codex)
    correctly flagged that `subprocess.run`'s own timeout handling calls
    `proc.kill()` (SIGKILL) directly on expiry, which gives a signalled
    helper no chance to run its own `finally`-based cleanup (the replay
    script's worktree removal). Instead, `_run_script` now `Popen`s the
    helper itself with `start_new_session=True` and does a two-stage
    shutdown on expiry: `communicate(timeout=timeout)`; on
    `TimeoutExpired`, `os.killpg(proc.pid, signal.SIGTERM)` (the replay
    script's own `_raise_on_signal` guard, see below, catches this and
    cleans up its worktree before exiting) followed by one more
    `communicate(timeout=SCRIPT_GRACE_S)`; if the child is STILL alive
    after that grace period, `os.killpg(proc.pid, signal.SIGKILL)` as the
    absolute last resort. Returns
    `f"_{script.name} failed (timeout after {int(timeout)}s)_"` on the
    timeout path (whether the child exited gracefully inside the grace
    window or had to be force-killed — the caller's context block gets
    the same message either way) and the existing non-zero-exit message
    otherwise; callers that just append the string need no change."""
```

For `MECH_SCRIPT`/`TAUT_SCRIPT` (no subprocess of their own), the SIGTERM
in the escalation path reaches a plain Python process with no custom
handler — Python's default disposition terminates it immediately, same
end state `subprocess.run`'s SIGKILL would have produced, so the two-stage
shutdown is a no-op cost for those two call sites and a correctness fix
only for `REPLAY_SCRIPT`, which does install a handler (below).

**In scope by PRD text, not a byproduct:** the PRD's own Requirements
line reads "`_run_script` times every helper script out at
`SCRIPT_TIMEOUT_S` and names the timeout in its block" — `_run_script` is
the one shared call site for `MECH_SCRIPT`, `TAUT_SCRIPT` and
`REPLAY_SCRIPT` (`_append_mech_blocks`, `review_stage.py:221-246`), so
bounding `compute_mech_facts.py` and `detect_tautological_tests.py` at
540s alongside the replay runner is the PRD's named scope, not an
unscoped widening. All three already run well under 540s in the existing
test corpus; a script that cannot is a pre-existing problem this PRD
surfaces rather than causes.

`_append_mech_blocks`'s replay call gains `--timeout 480`:

```python
    replay_args = ["--base", base, "--cmd", replay_cmd, "--timeout", "480"]
```

(`REPLAY_SCRIPT`'s own `--timeout` argparse default stays `600.0` for
direct/manual invocations; only this caller pins it to 480.) The 60s gap
between the replay's internal `--timeout 480` and the outer
`SCRIPT_TIMEOUT_S` 540 is the margin for the replay script's own
post-kill cleanup (`finally:` worktree-remove + `shutil.rmtree`) to run
to completion *before* `_run_script`'s outer `subprocess.run(timeout=540)`
would otherwise SIGKILL the whole replay process and re-leak the
worktree this PRD exists to stop leaking. 60s is generous for a
`git worktree remove --force` plus an `rmtree` of a tmp dir holding one
overlay's worth of files (no evidence any measured run needs more); if a
future measurement finds it tight, widen `SCRIPT_TIMEOUT_S` rather than
narrowing `--timeout 480`. This margin is now a secondary safety net
rather than the only protection — `_run_script`'s SIGTERM-then-grace-then-
SIGKILL escalation (above) means the replay script gets a real chance to
clean up even if the margin is ever exceeded.

## Data flow

**Gate spawn (signal path).** `run_gate` → `_gate_under_lock` (lock-wait
budget) → `_run_locked_gate` → `_spawn_gate`. Inside `_spawn_gate`,
`_deferred_signals` installs one handler for SIGTERM/SIGINT/SIGHUP before
`Popen()` runs. While the handler is installed and `gate_started` is
False, any of the three signals only sets `pending_signum` — Python never
converts SIGINT to `KeyboardInterrupt` while a handler is installed for
it, so `Popen()` always returns normally (this is the mechanism that
closes race 1: `Popen()` itself can no longer raise, so `proc` is always
bound from its return value, never recovered from a traceback). Once
`Popen()` returns, `proc` is assigned, `guard.gate_started = True`, then
`guard.raise_if_pending()` turns a signal that arrived during the Popen
call into the same `RuntimeError` a later signal would raise directly.
From that point on, the handler raises immediately on any of the three
signals, unwinding into the `except BaseException: _kill_gate(proc); raise`
that already exists — `proc` is real, so `_kill_gate` never sees a `None`
with a live child or a `TypeError`. `run_gate`'s own `finally` releases
the flock regardless of how `_spawn_gate` exits.

**Lock-wait budget (separate from the gate budget).** `run_gate` records
`wait_start` before calling `_acquire_lock(lock_fd, wait_start +
lock_timeout)`. On success, `waited_s = time.monotonic() - wait_start` and
a *fresh* `gate_deadline = time.monotonic() + timeout` are computed —
the gate's own budget starts counting only once the lock is actually
held, so a waiter that waited 580s of a 600s lock budget still gets its
full `timeout` (e.g. 1800s) for the gate itself, not `timeout - 580`.
`waited_s` rides on every returned dict, attached once in
`_gate_under_lock` regardless of which branch returns.

**Replay signal path.** `review_stage._append_mech_blocks` →
`replay_tests_against_base.replay` → `_run_in_worktree`. The guard goes up
before `Popen()` runs, exactly like the gate's: a SIGTERM/SIGHUP arriving
before `guard.spawned` is set only records `pending_signum` (same
mechanism that closes race 1 for the gate), so `Popen()` always returns
normally and `proc` is always bound before any raise. Once spawned,
`guard.raise_if_pending()` turns a deferred signal into `_SignalRaised`
immediately; from then on the handler raises on any further signal unless
`guard.cleaning` is set. A SIGTERM/SIGHUP delivered to the whole process
group (the orphan sweep's `SIGHUP`, or a session-level SIGTERM, or
`_run_script`'s own escalation below) raises `_SignalRaised` out of
`proc.communicate()`; the `except` branch sets `guard.cleaning = True`
first, then kills the runner's own process group with SIGKILL (the runner
was started with `start_new_session=True`, so it has its own group
distinct from the caller's) and returns a skip reason instead of
propagating — a second signal landing during that kill is recorded and
dropped, not re-raised. The function's `finally` then removes the
worktree and temp dir exactly as it does for the `TimeoutExpired` and
`OSError` paths today.

**Helper-script timeout.** `review_stage._run_script` now bounds every
helper subprocess (`compute_mech_facts.py`, `detect_tautological_tests.py`,
`replay_tests_against_base.py`) at `SCRIPT_TIMEOUT_S` (540s) via its own
manual `Popen`/`communicate`, not `subprocess.run`'s built-in timeout: on
expiry it sends SIGTERM to the helper's process group first, waits up to
`SCRIPT_GRACE_S` (30s) more, and only SIGKILLs if the helper is still
alive after that — giving `replay_tests_against_base.py`'s own guard a
real chance to run its `finally` (worktree removal) before anything is
force-killed. `compute_mech_facts.py`/`detect_tautological_tests.py` have
no signal handler of their own, so the SIGTERM simply terminates them
immediately on that path, same end state as before. Either way the
timeout is reported as a string in the context file instead of hanging
the review stage.

## Reuse inventory

- `_deferred_sigterm`/`_SigtermGuard` (`verification.py:538-578`) — the
  defer-then-raise shape this design generalizes in place; no new pattern
  introduced, same contextmanager shape widened to a signal tuple.
- `start_new_session=True` + `os.killpg(proc.pid, signal.SIGKILL)` — already
  used by both `_kill_gate` (`verification.py:640-654`) and the replay
  runner's existing `TimeoutExpired` branch
  (`replay_tests_against_base.py:132-137`); the new `_SignalRaised` branch
  reuses the exact same two-line kill idiom rather than inventing another.
- `subprocess.run(..., timeout=...)` — already the pattern `use-codex`'s
  `codex-run.sh` wrapper and `run_pack`'s `ENGRAM_TIMEOUT_S` use elsewhere
  in this pack; `_run_script`'s new `timeout=` kwarg matches `run_pack`'s
  existing `except subprocess.TimeoutExpired` shape
  (`review_stage.py:297-298`) rather than a new idiom.
- Greps tried confirming no existing generalized "defer N signals" helper
  exists anywhere else in the pack: `rg -n "deferred_sig|SignalGuard|signal.signal" skills/`
  (only this file's `_deferred_sigterm`/`_SigtermGuard` and
  `signal.signal` calls inside `_deferred_sigterm` and test monkeypatches
  — nothing to reuse beyond what this design widens); `rg -n "killpg.*SIGKILL" skills/`
  (the two call sites already reused above, no third).

## Alternatives considered

1. **Smallest-diff: only fix SIGINT-during-spawn, leave SIGHUP unhandled.**
   Would close race 1 alone (the measured 68/1500 leak) by adding SIGINT
   to the existing `_deferred_sigterm`'s signal set without renaming it.
   Rejected: the PRD's requirement line is explicit that SIGINT, SIGTERM
   *or* SIGHUP must all be covered, and the loop's orphan sweep already
   sends SIGHUP in production (`cli/loop.py:281`) — leaving it unhandled
   ships a known-reachable gap the PRD names by number (race 2, measured
   on a live sweep). Not taken.
2. **Chosen: one generalized `_deferred_signals` guard, same lock-split
   and replay-signal treatment as specified.** Matches the PRD's
   `## Solution` section symbol-for-symbol; the extra size over option 1
   buys coverage of a signal autopilot's own loop sends routinely, not a
   hypothetical.
3. **Separate guard classes per signal set (one for the gate, a different
   one for the replay runner) instead of one shared `_SignalGuard` concept
   reused as two near-identical implementations (`_SignalGuard` /
   `_SignalRaised`).** Rejected: the two call sites have different shapes
   already (the gate defers-then-raises across a `gate_started` boundary,
   because the lock and record-deletion steps around it must never be
   interrupted mid-write; the replay runner has no such pre-spawn critical
   section, so a bare raise-on-signal contextmanager is correct there and
   simpler). Sharing one class across both would force the replay runner
   to carry a `gate_started`-shaped flag it never needs. Two small,
   purpose-fit primitives beat one over-general one.

## Risks & edge cases

- **Off-main-thread callers.** `_deferred_signals` and `_raise_on_signal`
  are both no-ops off the main thread (matching today's
  `_deferred_sigterm` behavior) — any future caller that runs `run_gate`
  or `replay()` from a worker thread gets no signal protection at all,
  silently. Not a regression (today's code already has this gap), but
  worth flagging for whoever next touches thread-pooled verification.
- **Additive lock-wait + gate budgets are the intended tradeoff, not an
  open question.** A late lock-acquirer gets the gate's *full* `timeout`
  rather than a reduced one (see Data flow), making the two budgets
  additive up to `GATE_LOCK_TIMEOUT_S + GATE_TIMEOUT_S` (600s + 1800s =
  2400s worst case) instead of one shared ceiling. This is the PRD's own
  acceptance line verbatim ("a waiter that acquires the lock after N
  seconds still gets the full `timeout` for its gate"), not a judgment
  call this design introduces — `GATE_TIMEOUT_S` (1800s) is already well
  under the loop's multi-hour session wall-clock cap on its own, so 2400s
  worst case stays inside today's margin.
- **`waited_s` reaches stdout with no extra wiring.** `__main__._report_verify`
  (`cli/__main__.py:1067-1081`) already does `print(json.dumps({**result,
  "sha": head, "log": printed_log}))` — it spreads the whole `run_gate`
  result dict, so the new `waited_s` key is on stdout automatically; no
  change to `_report_verify` itself is needed.
- **`lock_timeout` default change is observable.** Any caller that passed
  a single `timeout` expecting it to cover the lock wait too (none exist
  in this repo today — confirmed by reading every `run_gate(` call site)
  now gets up to `GATE_LOCK_TIMEOUT_S` (600s) of *additional* wall time
  before the gate's own `timeout` even starts counting. For the loop's
  session wall-clock cap this is still safely inside today's margins
  (`GATE_TIMEOUT_S` 1800s + 600s lock wait is still well under the
  session's multi-hour cap), but a future PRD that tightens per-call
  budgets should account for the two being additive, not nested.
- **Next likely changes:** (1) a per-signal counter/metric so a repeatedly
  swept verify shows up in telemetry rather than only in the Tests line;
  (2) extending the same `_deferred_signals` treatment to `codex-run.sh`'s
  own background dispatch, which today has no signal guard of its own
  and could leak a codex process the same way `_spawn_gate` used to leak
  gates.

## Test strategy outline

- `test_verify_truth.py`: replace
  `test_sigint_during_popen_leaves_the_gate_running` with
  `test_sigint_during_spawn_kills_the_gate` (same `popen_then_sigint`
  fixture shape, but now asserts the gate group is dead and `run_gate`
  raised the signal `RuntimeError`, not that it leaked); add
  `test_sigint_storm_leaks_no_gate` (100 trials, random delay before the
  interrupt, asserting zero surviving gate pids across all trials, bounded
  to run under 20s total); add `test_sighup_kills_the_gate_group_and_frees_the_lock`
  (SIGHUP delivered mid-gate via `send_signal`, assert group dead and a
  non-blocking flock on the lock path succeeds within 1s afterward); add
  `test_signal_exit_prints_one_json_line` (drives `cli verify` as a
  subprocess, sends SIGTERM mid-gate, asserts exactly one JSON line on
  stdout shaped `{"error": "verify: SIGTERM during gate", "exit": 2, ...}`
  and no traceback on stderr); add `test_late_waiter_gate_gets_full_timeout`
  (hold the lock 3s, call `run_gate` with `timeout=2, lock_timeout=4`,
  assert `timed_out is False` once the holder releases); add
  `test_result_reports_waited_s` (assert `waited_s` present and
  approximately correct on a reused-lock-wait case, e.g. lock held ~1s).
- `test_replay_timeout_kill.py`: add
  `test_group_sigterm_kills_runner_and_removes_worktree` (spawn `replay()`
  in a subprocess or thread-free harness against a slow pytest command,
  SIGTERM the process group, assert `git worktree list` has exactly the
  original entry and no `replay-*` temp dir under the system tmp root
  survives).
- `test_review_stage.py`: add `test_run_script_times_out_and_says_so`
  (call `_run_script(..., timeout=0.1)` **explicitly** — dispatch 2
  correctly caught that monkeypatching the module-level `SCRIPT_TIMEOUT_S`
  constant has no effect on a default already bound into the function
  signature at def-time, so the test must pass `timeout=` as an argument,
  not patch the constant — point it at a helper that sleeps past it,
  assert the returned string matches `_<name> failed (timeout after
  0s)_`-shaped text, no exception propagates, and the helper process is
  actually gone afterward).
- `test_verify_truth.py`: add two more lifecycle-boundary cases dispatch 2
  named as missing — `test_sigterm_during_cleanup_does_not_leak` (send a
  second SIGTERM into `_kill_gate`'s own killpg/wait window via a
  monkeypatched `_kill_gate` that signals itself before returning; assert
  the gate group is still fully dead and the flock still frees within 1s)
  and `test_sighup_before_spawn_kills_the_gate` (SIGHUP delivered while
  `gate_started` is still False, mirroring `test_sigterm_pending_before_gate_started_kills_the_gate`'s
  existing shape for the third signal). Full exhaustive parametrization
  over all three signals at all four boundaries (before/during/after
  spawn, during cleanup) is not added — the existing suite plus these two
  already exercises every boundary at least once per signal class
  (SIGINT: before+during spawn; SIGTERM: before-spawn, mid-gate,
  mid-cleanup; SIGHUP: before-spawn, mid-gate) and a fully crossed matrix
  multiplies run time for marginal additional confidence given the three
  signals share one handler.
- `test_replay_timeout_kill.py`: add
  `test_sigterm_during_popen_kills_the_runner` (mirrors
  `test_sigint_during_spawn_kills_the_gate`'s monkeypatched-Popen shape:
  SIGTERM arrives while `subprocess.Popen` is still executing inside
  `_run_in_worktree`, before `guard.spawned` is set; assert the runner
  group still ends up dead and the worktree still gets removed).
- `test_review_stage.py`: add `test_run_script_sigterms_before_sigkill`
  (point `_run_script` at a helper that traps SIGTERM, writes a marker
  file, and exits 0 within the grace window; assert the returned string
  still reports the timeout, the marker file exists — proving the helper
  got a real SIGTERM and ran its own cleanup rather than being SIGKILLed
  outright — and no SIGKILL was needed).

## Review log

Dispatch 1 (claude) findings:
- non-blocker: pre-spawn dirty/HEAD-moved checks shift from the lock-wait budget to the gate budget; the design already names this shift. Not fixed further; adding a dedicated test for it is a `plan-tasks` call, not a design change.
- question: is `waited_s` additive to the gate's own timeout acceptable? Resolved above (Risks & edge cases) — yes, it is the PRD's own acceptance criterion, not an open question.
- question: does `waited_s` reach the CLI's stdout? Resolved above — yes, via the existing `{**result, ...}` spread in `_report_verify`, no code change needed.
- non-blocker: 60s margin between replay's internal `--timeout 480` and the outer `SCRIPT_TIMEOUT_S` 540 for worktree cleanup. Resolved above — kept as designed, with the reasoning spelled out and a path to widen if ever measured tight.
- blocker (resolved by citation, not a design change): `_run_script`'s 540s timeout applying to all three helper scripts, not just the replay runner, is the PRD's own stated requirement (`## Requirements` → "`_run_script` times every helper script out at `SCRIPT_TIMEOUT_S`"), not an unscoped widening. Cited inline above.

dispatch 1 (claude): cardinal-sin 0, blocker 1, non-blocker 2, question 2

Dispatch 2 (codex) findings:
- blocker: replay's `_raise_on_signal` was installed only around `communicate()`, after `Popen()` already returned and before `guard.spawned` existed — a signal during the Popen syscall or in the gap before entering the guard could escape uncaught. Fixed: `_ReplaySignalGuard` now mirrors `_SignalGuard`'s defer-before-spawn/raise-after-spawn shape, and the guard wraps the Popen call itself, not just `communicate()`.
- blocker: both guards (`_SignalGuard` and the new `_ReplaySignalGuard`) could have a second signal land inside their own kill-and-reap cleanup and re-raise, interrupting the kill. Fixed: both guards gained a `cleaning` flag, set to `True` as the first line of every cleanup branch, so a second signal during cleanup is recorded and dropped, never re-raised.
- blocker: `_run_script`'s plan to lean on `subprocess.run(timeout=...)` would SIGKILL a timed-out helper outright, giving the replay script's own cleanup no chance to run even after the guard fixes above — recreating the exact leak this PRD exists to close. Fixed: `_run_script` rewritten around a manual `Popen` + SIGTERM + `SCRIPT_GRACE_S` (30s) grace window + SIGKILL-as-last-resort escalation, so a timed-out replay gets a real chance to clean up via its own signal guard.
- non-blocker: the originally sketched test monkeypatched `SCRIPT_TIMEOUT_S` after the function's default was already bound at def-time, which would not have taken effect. Fixed in the test strategy: pass `timeout=` explicitly instead of patching the module constant.
- non-blocker: the original test list didn't exercise every signal at every lifecycle boundary (before/during spawn, during cleanup) for all three signals. Added three more tests (`test_sigterm_during_cleanup_does_not_leak`, `test_sighup_before_spawn_kills_the_gate`, `test_sigterm_during_popen_kills_the_runner`) plus one proving the new grace-then-kill escalation actually sends SIGTERM first (`test_run_script_sigterms_before_sigkill`); a fully crossed matrix was not added (see the test strategy's own note on why).

dispatch 2 (codex): cardinal-sin 0, blocker 3, non-blocker 2, question 0

Dispatch 3 (codex, verification) findings:
- blocker: `guard.spawned = True` and `guard.raise_if_pending()` sat outside the inner `try` whose `except _SignalRaised` does the kill, so a signal raised by `raise_if_pending()` itself would propagate past that handler to the outer `except OSError` (a non-match) and leak the runner — dispatch 2's first blocker was not actually closed by the prior edit. Fixed: moved `spawned = True`/`raise_if_pending()`/`communicate()` all inside the one inner `try` the `_SignalRaised` branch covers, with `proc is not None` guarding the kill (shown inline above).

dispatch 3 (codex): cardinal-sin 0, blocker 1, non-blocker 0, question 0

Dispatch ceiling (3/3) reached with dispatch 3's blocker fixed inline above and no new findings beyond it; no cardinal sins or blockers remain open. Per the skill's 3-dispatch ceiling, this is the final review pass — the fix is applied, not re-verified by a 4th dispatch.
