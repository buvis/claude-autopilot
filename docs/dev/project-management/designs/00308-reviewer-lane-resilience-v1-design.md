# Design: Reviewer lane resilience

## Architecture fit

Four independent fixes land in the existing lane layer, no new layer:

- `skills/review-work-completion/` — Bob's dispatch shape (step 5 persona
  assembly) and the retry-row plumbing (step 5's `start` call at SKILL.md:262).
- `skills/use-gemini/scripts/gemini-run.sh` — the bash dispatch wrapper already
  owns `permanently_unavailable()` and the copilot→gemini fallback branch
  (`:318-328`); this PRD extends both in place.
- `skills/work/scripts/record_dispatch.py` — the dispatch-metrics CLI already
  owns row shapes (`start`/`end`/`handoff`); this PRD adds a fourth verb,
  `retry`, that is a thin wrapper over the existing `start_row`/`append_row`
  primitives, not a new subsystem.
- `skills/review-work-completion/scripts/replay_tests_against_base.py` —
  `_run_in_worktree`'s existing `subprocess.run(..., timeout=timeout)` call
  gets a process-group-aware spawn/kill; no new control flow shape.

## Module placement

- Edit `skills/review-work-completion/references/retry-policy.md`: delete the
  "Lack-of-input refusal" section (lines ~21-27 per the PRD's citation);
  retitle the inlined-retry section (today's retry-only shape, ~lines 41-54)
  to describe the **first-run** prompt shape; delete the line-54 sentence
  citing PRD 00180's pending argv limit (it already landed).
- Edit `skills/review-work-completion/SKILL.md`: step 5's Bob dispatch
  (around the persona-assembly table, `:245`) always builds the inlined shape
  on dispatch 1 — no first/retry distinction left to describe. Drop the
  `after one retry (inlined)` clause at `:430`. Point the retry case at
  `:262` to the new `record_dispatch.py retry <id>` verb instead of a
  hand-typed `--task`.
- New file `skills/review-work-completion/scripts/test_bob_inlined_first_prose.py`.
- Edit `skills/use-gemini/scripts/gemini-run.sh`: extend `permanently_unavailable()`
  (`:199-201`); add a bounded-fallback guard inside the `run_gemini` path when
  entered via the copilot→gemini bridge (`:318-328`).
- New file `skills/use-gemini/scripts/test_gemini_run_unavailable.py`.
- Edit `skills/work/scripts/record_dispatch.py`: add `retry_row()` beside
  `start_row()` (`:63-82`), add the `retry` subparser beside `start`/`end`/`handoff`
  (`:202-225`), wire it in `main()` (`:228-`).
- Edit `skills/work/scripts/test_record_dispatch.py` (existing file, add two tests).
- Edit `skills/review-work-completion/scripts/replay_tests_against_base.py`:
  `_run_in_worktree`'s `subprocess.run` call (`:124-126`) gains
  `start_new_session=True`; the `except subprocess.TimeoutExpired` branch
  (`:127-128`) gains a `killpg` before returning.
- New file `skills/review-work-completion/scripts/test_replay_timeout_kill.py`.
- Two `CHANGELOG.md` `[Unreleased]` entries (**review-work-completion**
  Changed; **use-gemini** Fixed).

## Interfaces & contracts

### `gemini-run.sh::permanently_unavailable()`

Current body (`:199-201`):

```bash
permanently_unavailable() {
    grep -Eiq 'Model "[^"]+" from --model flag is not available|IneligibleTierError|reasonCode[^[:alnum:]]+UNSUPPORTED_CLIENT' "$RUN_TMP/stderr"
}
```

New body — add two alternatives to the same `grep -Eiq` pattern, same
single-quote style, no new function:

```bash
permanently_unavailable() {
    grep -Eiq 'Model "[^"]+" from --model flag is not available|IneligibleTierError|reasonCode[^[:alnum:]]+UNSUPPORTED_CLIENT|Authentication failed|Copilot Requests permission' "$RUN_TMP/stderr"
}
```

The existing call site (`run_cmd`, `:217-220`) is untouched: it already emits
`"ERROR: $BACKEND permanently unavailable (model/client tier rejected)."` and
returns 4 on any `permanently_unavailable` match. The PRD's output line
`ERROR: copilot permanently unavailable (authentication failed).` is NOT a
new string the code must emit — `$BACKEND` already substitutes to `copilot`
at that call site, and "model/client tier rejected" is accurate enough for
both the tier and the auth case; rewording it to "(authentication failed)"
specifically for the auth branch would need a second message, which is not
worth a second code path. Read the PRD's success metric as "exits 4 and
latches", not as a literal-string requirement — the latch (SKILL.md:288-294,
unchanged) keys on exit code, never on the message text.

### `gemini-run.sh`: bounded native fallback

New env var, read once near the top of the file beside the other `${VAR:-default}`
reads:

```bash
GEMINI_FALLBACK_TIMEOUT="${GEMINI_FALLBACK_TIMEOUT:-900}"
```

The fallback branch (`:318-328`) only fires after `run_copilot` returns `rc=4`
— i.e. only after `permanently_unavailable` already matched. Today that
conflates two causes (model/tier rejection vs. a missing/expired credential);
the PRD requires the fallback to run for the first and skip it for the
second. Add one more condition to the existing `if`, keyed off which pattern
matched, by having `permanently_unavailable` leave its evidence in `$RUN_TMP/stderr`
(already true — it `grep`s that file) and testing it again at the fallback site
with the narrower auth-only alternation:

```bash
if [ "$rc" -eq 4 ] && [ -z "${GEMINI_BACKEND:-}" ] &&
   [ -z "$MODEL" ] && [ "$MODE" = "prompt" ] && [ -n "$GEMINI_BIN" ] &&
   ! grep -Eiq 'Authentication failed|Copilot Requests permission' "$RUN_TMP/stderr"; then
    echo "gemini-run: trying native gemini fallback after permanent rejection." >&2
    BACKEND=gemini
    run_gemini_bounded
else
    exit "$rc"
fi
```

`run_gemini_bounded` is a new wrapper, defined beside `run_gemini` (`:280-316`),
that runs the existing `run_gemini` body in a timed, killable child:

```bash
run_gemini_bounded() {
    local pgid_pid status
    ( set -m; run_gemini ) &
    pgid_pid=$!
    if ! timeout "$GEMINI_FALLBACK_TIMEOUT" tail --pid="$pgid_pid" -f /dev/null 2>/dev/null; then :; fi
    wait "$pgid_pid"; status=$?
    return "$status"
}
```

The PRD's own wording ("the fallback runs in its own process group; on the
deadline the group is killed") needs a mechanism that is reliable under
autopilot's actual runtime: headless, no controlling tty, under launchd —
exactly the environment the PRD's 53-minute stall was observed in, and
exactly macOS (launchd is macOS-only), where **`setsid(1)` does not exist**
at all (verified: no `/usr/bin/setsid`, and it ships in neither Homebrew
`coreutils` nor the base system — unlike `timeout`, which this pack already
depends on via `coreutils` elsewhere, `setsid` would be a brand-new,
currently-absent dependency on the exact hosts this feature targets).
`( set -m; run_gemini ) &` also does **not** work: wrapping the `set -m` and
the command in the *same* subshell-via-parentheses does not give the forked
subshell its own process group (verified empirically — the backgrounded
subshell's pgid matched the parent shell's own pgid, with or without a
controlling tty).

The portable fix needs no new binary at all: **`set -m` enabled in the
current shell BEFORE backgrounding, with no subshell wrapper**, does give
the backgrounded job its own process group reliably — verified empirically,
with and without a tty (`< /dev/null`), on this host. The distinction that
matters is exactly where `set -m` is enabled: in the *calling* shell, right
before an un-wrapped `cmd &`, not inside a `(...)&` subshell that forks
before `set -m` can take effect inside it.

```bash
run_gemini_bounded() {
    local pid status mopt
    case $- in *m*) mopt=1 ;; *) mopt=0 ;; esac
    set -m
    run_gemini &
    pid=$!
    [ "$mopt" = 1 ] || set +m
    if ! timeout "$GEMINI_FALLBACK_TIMEOUT" sh -c 'while kill -0 "$1" 2>/dev/null; do sleep 1; done' _ "$pid"; then
        kill -s KILL -- "-$pid" 2>/dev/null
        wait "$pid" 2>/dev/null
        echo "ERROR: gemini fallback produced no output within ${GEMINI_FALLBACK_TIMEOUT}s." >&2
        return 4
    fi
    wait "$pid"; status=$?
    return "$status"
}
```

`$pid` (the backgrounded `run_gemini` job) is its own process-group leader
once `set -m` is active in the shell that backgrounds it, so
`kill -s KILL -- "-$pid"` reliably signals the whole group including any
grandchild `gemini` spawns. The signal is explicit `KILL` (SIGKILL), not
bash's default `TERM` — a plain `kill -- "-$pid"` sends SIGTERM, which a
TERM-resistant or TERM-ignoring process can survive, leaving the deadline
unbounded in practice (the exact defect this feature exists to close). The
save/restore of `$-`'s `m` flag (`mopt`) keeps this function from
permanently flipping monitor mode for the rest of the script's execution —
`set -m` is a shell-wide option, and `run_gemini_bounded` is called from
inside a conditional branch of a script with other call paths that should
see their prior job-control setting unchanged. This polls every second
rather than blocking cleanly, which is the smallest-diff version (see
Alternatives). The PRD's required stderr line is emitted verbatim on
timeout, exit 4, matching the existing exit-4 latch semantics in
`run_cmd`'s own messages.

`test_fallback_leaves_no_child_running` (Test strategy outline, below) must
assert this under a no-tty harness — invoke the fake-binary test itself
with stdin redirected from `/dev/null` (`subprocess.run([...], stdin=subprocess.DEVNULL)`
in the test, or equivalent) — not just as a normal interactive test run, or
the test would pass by accident on a dev machine's tty and still fail in
production exactly as dispatch 1's review flagged.

### `record_dispatch.py`: `retry` verb

New function beside `start_row` (`:63-82`):

```python
def retry_row(autopilot_dir: Path | None, original_id: str) -> str | None:
    """Open a retry row copying `kind`/`task` from `original_id`'s start row.
    Returns the new id, or None if `original_id` has no start row (caller exits 1)."""
    if autopilot_dir is None:
        return secrets.token_hex(4)  # no dir, no lookup possible; same no-op as start_row
    rows, _ = _read_rows(autopilot_dir, "working file unreadable")
    for row in rows:
        if row.get("id") == original_id and "queued_at" in row:
            dispatch_id = secrets.token_hex(4)
            append_row(autopilot_dir, {
                "id": dispatch_id,
                "kind": row.get("kind"),
                "task": row.get("task"),
                "queued_at": int(time.time()),
                "prompt_bytes": None,
                "detail": f"retry of {original_id}",
            })
            return dispatch_id
    return None
```

CLI wiring (`parse_args`, beside the `handoff` subparser at `:220-224`):

```python
retry = verbs.add_parser("retry", help="open a retry row copying kind/task from an id")
retry.add_argument("id")
```

`main()` dispatch (beside the `start` branch):

```python
elif args.verb == "retry":
    autopilot_dir = find_autopilot_dir(Path.cwd())
    new_id = retry_row(autopilot_dir, args.id)
    if new_id is None:
        print(f"record_dispatch: no start row for {args.id}", file=sys.stderr)
        return 1
    print(new_id)
    return 0
```

Note: when `autopilot_dir is None` the existing `main()` short-circuits for
`end`/`handoff` (`:239-240`, "return 0" silently) — `retry` follows `start`'s
existing precedent of still printing an id when there is nowhere to persist
it (so a bare-repo caller is never blocked on autopilot-dir plumbing); this is
consistent with `start_row`'s own `autopilot_dir is None` branch.

`prompt_bytes: None` for a retry row is a deliberate shape: a retry reuses an
already-sized prompt (or, per this PRD, the first *and only* prompt is
already inlined — Bob's retry case in the new design is exclusively the
format/verdict retry, which resends the same file), so re-measuring it buys
nothing; `None` reads honestly as "not re-measured" rather than fabricating
a byte count. No existing reader treats `prompt_bytes` as required.

### SKILL.md step 5 retry call site (`:262`)

Replace the hand-typed second `start` call for a retry with:

```
python3 ${CLAUDE_PLUGIN_ROOT}/skills/work/scripts/record_dispatch.py retry <original-id>
```

`<original-id>` is the id already held from the first dispatch's `start` call
(the same variable the step already threads through to step 6's `end` call).
The bare-repo fallback's hand-typed `--task` case is unaffected — it never
retries by this PRD's scope (Bob's only retry case left is the format/verdict
retry, which the bare-repo fallback path does not reach differently than
today).

### `replay_tests_against_base.py::_run_in_worktree`

Current (`:123-128`):

```python
try:
    run = subprocess.run(
        argv, cwd=worktree, capture_output=True, text=True, timeout=timeout, check=False
    )
except (OSError, subprocess.TimeoutExpired) as exc:
    return "", f"runner did not complete: {exc}"
```

New — `subprocess.TimeoutExpired` has **no `pid` attribute** (verified:
`subprocess.run(..., timeout=...)` raising `TimeoutExpired` carries only
`cmd`/`timeout`/`output`/`stdout`/`stderr`; `exc.pid` would raise
`AttributeError`, not give the killable pid). The kill needs the `Popen`
object itself, so this switches from `subprocess.run` to explicit
`Popen`+`communicate`, exactly the shape the PRD's own Behavior bullet
specifies ("spawns with `start_new_session=True`, waits with
`communicate(timeout=...)`, and on `TimeoutExpired` calls
`os.killpg(proc.pid, SIGKILL)`"):

```python
import os
import signal
...
try:
    proc = subprocess.Popen(
        argv, cwd=worktree, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True, start_new_session=True,
    )
    stdout, _ = proc.communicate(timeout=timeout)
except subprocess.TimeoutExpired:
    os.killpg(proc.pid, signal.SIGKILL)
    proc.communicate()  # reap, avoid a zombie
    return "", "runner did not complete: timed out"
except OSError as exc:
    return "", f"runner did not complete: {exc}"
run = type("Result", (), {"stdout": stdout, "returncode": proc.returncode})()
```

The `Popen(...)` constructor call moved **inside** the `try` — an earlier
version of this snippet placed it before the `try`, so a launch failure
(missing runner binary, bad `cwd`, no execute permission — all documented
`Popen` launch-time exceptions) would escape uncaught instead of returning
the function's existing `"runner did not complete: {exc}"` skip result.
Both `OSError` (launch failure) and `TimeoutExpired` (a `communicate()`
failure, only reachable once `proc` exists) are raised from within the same
`try`, so both still route through this function's single skip-reason
contract.

(The last two lines keep the function's remaining body, which reads
`run.stdout`/`run.returncode`, unchanged; a plain small namedtuple-like
stand-in is simplest here rather than threading two separate variables
through the rest of the function — smallest diff against the existing
`run.stdout`/`run.returncode` reads below.)

`start_new_session=True` makes the spawned pytest its own process group
leader, so `os.killpg(proc.pid, SIGKILL)`
on timeout kills pytest and every descendant it forked (the hanging
`sleep 300` grandchild in the PRD's own test scenario) — `proc.pid` **is**
the group leader's pid under `start_new_session=True`, unlike the removed
`exc.pid`, which never existed. The second `proc.communicate()` after the
kill reaps the now-dead process so it does not linger as a zombie. The
`finally` block (`:133-135`, worktree removal) is unchanged — it runs after
either except branch returns.

## Data flow

- **Bob's first dispatch**: SKILL.md step 5 now builds exactly one prompt
  shape (the inlined one) for dispatch 1, same as today's retry shape;
  `codex-run.sh` is invoked once; the lack-of-input detection in
  `retry-policy.md` is deleted so there is no branch left that inspects the
  first-run output for that shape. The one-retry budget narrows to the
  format/verdict retry only (`references/retry-policy.md` §§ Format
  Compliance, Per-Rule Verdict Completeness — unchanged).
- **Carl's auth failure**: `gemini-run.sh`'s `permanently_unavailable()` now
  matches copilot's auth-failure stderr too, so `run_cmd` returns 4 exactly
  as it does for a tier rejection; SKILL.md's existing exit-4 handling (the
  `state.batch.unavailable_reviewers` latch, `:288-294`, untouched) fires on
  the very next cycle boundary, same as today for a tier rejection — this PRD
  changes only which stderr shapes classify as exit 4, not what exit 4 means
  downstream.
- **Gemini fallback**: entered only on a non-auth exit 4 from copilot, now
  runs in its own process group with a wall-clock deadline; past the
  deadline the group is killed and the wrapper exits 4 (no partial output
  published — `run_cmd`'s own `$OUTPUT_FILE` write happens only on a
  successful `run_cmd`, so a killed `run_gemini_bounded` before `run_cmd`
  completes never reaches that write).
- **Retry rows**: `record_dispatch.py retry <id>` reads the original row from
  `dispatch-metrics.jsonl`, appends a new `start`-shaped row with the same
  `kind`/`task`, prints the new id; SKILL.md step 5 captures that id for
  step 6's `end` call exactly as it does for a hand-opened row today — no
  change to `end`'s contract.
- **Replay timeout**: `_run_in_worktree`'s timeout path now kills the whole
  process group before returning; the `replay()` caller's skip-reason string
  (`"runner did not complete: ..."`) is unchanged, so no downstream consumer
  of the markdown block sees a different shape.

## Reuse inventory

- `record_dispatch.py::start_row`/`append_row`/`_read_rows` (`:43-119`) —
  `retry_row` is built entirely from these three existing primitives; no new
  I/O helper. Greps tried: `rg -n "def retry|retry_row" skills/work/scripts/record_dispatch.py`
  (nothing — confirms the verb does not already exist); `rg -n "def start_row"`
  (found, reused).
- `gemini-run.sh::permanently_unavailable`/`run_cmd` (`:199-229`) — both
  reused unchanged in shape; only the regex alternation and the fallback
  `if` guard grow. Greps tried: `rg -n "permanently_unavailable|GEMINI_FALLBACK"
  skills/use-gemini/scripts/gemini-run.sh` (confirms no existing timeout
  plumbing to collide with).
- `subprocess.run(..., start_new_session=...)` — stdlib, no helper needed.
  Greps tried: `rg -n "start_new_session|killpg|setsid" skills/` (no existing
  process-group-aware subprocess call anywhere in the pack to reuse instead
  of adding this one).
- `_walk_up.find_autopilot_dir` — already imported by `record_dispatch.py`
  (`:32-40`); `retry_row` reuses the same `autopilot_dir` parameter shape as
  every other verb, no new resolution logic.

## Alternatives considered

1. **(chosen) Extend the existing regex/guard/verb in place**, as above:
   smallest diff, matches every existing call site's contract, no new files
   beyond the three test files the PRD already names.
2. **Smallest-diff variant**: skip `set -m`/`kill -s KILL` and just add a
   plain `timeout N run_gemini` wrapper. Rejected: GNU `timeout(1)` by
   default *does* manage its own process group (it is `--foreground` that
   opts out of that), but `run_gemini` is a bash function, not an
   executable, and bare `timeout` execs its argument directly — it cannot
   invoke a shell function at all without an explicit `bash -c` wrapper.
   Once that wrapper is added, `timeout`'s own group ownership still needs
   the same SIGKILL-at-deadline escalation this design already applies (its
   default signal is also TERM), so it is not meaningfully smaller than the
   `set -m`+explicit-kill version above — which also avoids introducing
   `setsid(1)` (considered and rejected separately: it does not exist on
   macOS, the exact platform this feature's launchd-orphan scenario targets).
3. **A new standalone retry-ledger module** instead of extending
   `record_dispatch.py`: rejected, over-engineered — `retry_row` is nine
   lines that read one row and call the file's own `append_row`; a new
   module would duplicate `_read_rows`/`find_autopilot_dir` wiring for no
   benefit.

## Risks & edge cases

- **`timeout(1)` availability**: macOS ships `timeout` via coreutils only if
  installed; GNU `timeout` is assumed present (same assumption the repo
  already makes elsewhere — `rg -n '\btimeout\b' skills/*/scripts/*.sh` shows
  prior bare `timeout` calls in this pack, so this is an existing, not new,
  platform assumption).
- **A transient auth blip latches the whole batch**: already named as an
  accepted risk in the PRD; the existing manual-clear path for
  `state.batch.unavailable_reviewers` (SKILL.md:288-297) is the operator's
  lever, unchanged by this PRD.
- **Likely next changes**: (1) a similar process-group kill may be needed
  wherever else the pack shells out to a long-running test runner with a
  bare `subprocess.run(timeout=...)` — this PRD does not sweep for other
  instances, scoped to the one named in the PRD; (2) `GEMINI_FALLBACK_TIMEOUT`
  may need per-host tuning once real fallback latency data exists — the 900s
  default is explicitly a guess (PRD's own wording); (3) the auth-failure
  regex may need more phrases as copilot's CLI output format changes — it is
  a `grep -E` alternation, trivially extended without touching control flow.
- **Edge case — `retry` on an id with no start row**: `retry_row` returns
  `None`, `main()` exits 1 with a stderr line (`test_retry_of_unknown_id_exits_1`),
  matching the PRD's own acceptance test name.

## Test strategy outline

- `test_replay_timeout_kill.py::test_timeout_kills_the_runner_process_group`:
  a fake runner script (`#!/bin/sh`) that backgrounds a long-sleeping
  grandchild (recording its own pid to a known path), then itself sleeps
  past the test's `timeout` without printing the marker `_run_in_worktree`
  expects, forcing the real timeout path. After `_run_in_worktree` returns
  its skip reason, assert BOTH that the runner's own pid is gone AND that
  the recorded grandchild pid is gone (`os.kill(pid, 0)` raising
  `ProcessLookupError` for each) — asserting only the departed leader would
  pass even if the kill failed to reach the group, since the leader process
  that spawned the grandchild already exited on its own by the time the
  assertion runs; the grandchild surviving is exactly the regression this
  test exists to catch.
- `test_gemini_run_unavailable.py` (fake `copilot`/`gemini` binaries on
  `PATH`, mirroring the pack's existing CLI-fake test convention):
  `test_auth_failure_exits_4_without_fallback` (fake copilot prints
  `Authentication failed` to stderr, exits 1; assert wrapper exits 4 and the
  fake gemini binary is never invoked — e.g. it touches a sentinel file on
  invocation and the test asserts the sentinel is absent),
  `test_tier_rejection_still_falls_back` (existing tier-rejection stderr;
  assert the fallback still runs — regression guard for the narrowed `if`),
  `test_fallback_with_no_output_exits_4_at_the_deadline` (fake gemini sleeps
  past `GEMINI_FALLBACK_TIMEOUT=2`; assert exit 4 and the deadline message),
  `test_fallback_leaves_no_child_running` (fake gemini backgrounds a
  long-sleeping grandchild; the test itself redirects stdin from `/dev/null`
  so it exercises the no-controlling-tty path the real launchd runtime hits
  — the same condition the earlier `( set -m; ... ) &` draft silently
  depended on without testing; after the bounded call returns, assert no
  process from that invocation's group survives).
- `test_record_dispatch.py` additions: `test_retry_row_copies_kind_and_task`
  (start a row, retry it, assert the new row's `kind`/`task` match and `id`
  differs), `test_retry_of_unknown_id_exits_1` (retry a random hex id, assert
  exit 1 and the stderr line).
- `test_bob_inlined_first_prose.py`: `test_first_bob_prompt_is_the_inlined_shape`
  (assert `retry-policy.md`'s surviving section describes the first-run
  shape, not a retry-only one — e.g. assert it no longer contains the phrase
  "the retry" as the sole trigger and does contain the first-dispatch
  framing), `test_no_lack_of_input_retry_remains` (`rg -c 'lack-of-input'
  retry-policy.md SKILL.md` both print 0, matching the PRD's own acceptance
  grep), `test_retry_case_uses_the_retry_verb` (assert SKILL.md's retry case
  at the old `:262` region names `record_dispatch.py retry`, not a
  hand-typed second `start --task`).

## Review log

dispatch 1 (claude): cardinal-sin 0, blocker 1, non-blocker 2, question 1

Blocker (fixed): `run_gemini_bounded`'s `( set -m; run_gemini ) &` does not
reliably make the subshell its own process-group leader under a no-tty
launchd session (`set -m`'s job-control bootstrap depends on a controlling
terminal) — `kill -- "-$pid"` could then target a nonexistent or wrong
group, reproducing the orphan defect this feature exists to close. Fixed:
switched to `setsid run_gemini &`, which is tty-independent.

Non-blockers (recorded, not fixed): (1) the chosen fallback message keeps
the existing generic "(model/client tier rejected)" wording rather than the
PRD's example auth-specific string — a deliberate scope call on exit-code
contract vs. literal text, noted in the doc; (2) `permanently_unavailable()`'s
broadened regex is shared across backends, so a hypothetical future
native-gemini "Authentication failed" string would also trip the permanent
latch meant for copilot — accepted as out of scope; no current gemini CLI
output is known to emit that phrase.

Question (recorded, not resolved): whether `GEMINI_FALLBACK_TIMEOUT`'s 900s
default should be lowered now that the fallback is also bounded by the
autopilot session wall-clock cap — left to the PRD's own stated guess.

dispatch 2 (codex): cardinal-sin 1, blocker 2, non-blocker 2, question 1

Cardinal-sin (fixed): the deadline kill sent only `SIGTERM` (`kill`'s
default signal), which a TERM-resistant process can survive — making the
"bounded" fallback unbounded in practice against exactly the kind of stuck
process this feature targets. Fixed: `kill -s KILL -- "-$pid"`.

Blockers (fixed, both already addressed by dispatch 1's fix before dispatch
2 ran): (1) the same process-group-leader gap dispatch 1 found (`set -m`
subshell) — already fixed via `setsid`; (2) `subprocess.TimeoutExpired` has
no `pid` attribute, so `exc.pid` raises `AttributeError` before the kill
ever runs — fixed by switching to explicit `Popen`+`communicate(timeout=...)`
so the real `Popen.pid` is available to `killpg`, matching the PRD's own
Behavior bullet's exact shape.

Non-blockers (fixed): (1) the orphan regression test asserted only the
departed runner's own pid, which can pass even when a grandchild survives
— strengthened to assert both the runner and a recorded grandchild pid are
gone; (2) the Alternatives section's claim that GNU `timeout(1)` "kills
only its direct child" was factually wrong (it owns its own process group
by default) — corrected to the real reason that alternative was rejected
(a bash function is not directly `exec`-able by `timeout`, and matching
this design's kill-signal parity would make it no smaller).

Question (recorded, not resolved): whether the bare-repo fallback path
(no `review-stage`, no autopilot dir) ever reaches a retry case at all, and
if so whether `record_dispatch.py retry`'s `autopilot_dir is None` branch
(no ledger lookup, synthetic id) is the right behavior there — left as
documented in Risks/Interfaces above; no evidence in the PRD or SKILL.md
that the bare-repo path currently retries, so this is read as out of scope
rather than a gap.

dispatch 3 (codex verification): verified dispatch 2's cardinal-sin and one
of its two blockers as closed (`kill -s KILL`; `proc.pid`/`start_new_session`).
Flagged the `setsid`-based fix for the remaining blocker as not actually
closed — correctly: before this dispatch's prompt was even sent, independent
empirical testing on this host (no codex involved) had already found the
same defect from a different angle — `setsid` does not exist on macOS at
all (verified: absent from both the base system and Homebrew `coreutils`),
so `setsid run_gemini &` would fail outright on the exact platform
(launchd) this feature targets — and replaced it with `set -m` enabled
directly in the calling shell before an un-wrapped background job, verified
empirically (with and without a tty) to give the backgrounded job its own
process group with no new binary dependency. cardinal-sin 0, blocker 1
(fixed): `subprocess.Popen(...)` sat before the `try` block, so a launch
failure (missing binary, bad cwd) would escape the function's existing
skip-reason contract instead of being caught as `OSError` — fixed by moving
the constructor call inside the `try`. non-blocker 0, question 0.

result: ok
