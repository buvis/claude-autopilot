# 00214-plan-and-launch-a-wave-of-lanes-v1 - rework cycle 1 design

Source review: dev/local/reviews/00214-plan-and-launch-a-wave-of-lanes-v1-review-1.md (head_sha b8b6b17cb989385cf34baaca4957b282b0690aaf)

## Architecture fit

Prior fix: none - there was no prior rework fix.

The cycle's one 🔴 Critical row:

> `_structural_errors`' `pid` check is `v is None or _is_int(v)` with no positivity
> bound, so a hand-edited or corrupted `"pid": 0` reaches `os.killpg(0, SIGTERM)` in
> `_kill_lane`, which signals the **caller's own process group** - under a wave that is
> the operator's shell or the autopilot loop itself. `order` and `review_slots` are both
> bounded `> 0` in the same table; `pid` is the one destructive field that is not.
> (`skills/run-autopilot/cli/wave.py:289`, found by bob, 1/4)

This lands entirely inside the wave module's own validation layer -
`cli/wave.py`'s `_LANE_CHECKS` table, read by `_collect_shape_errors`, reached
through `_structural_errors`. That function is the designed choke point, and it
has **three** verbs behind it, not two: `validate()` (launch's precondition,
`wave_launch.py:100` and `:138`), `abort()` (`wave_launch.py:512`), and `plan()`
via `_reject_existing_wave` (`wave.py:195`). All three run it before any signal or
filesystem action, precisely because `wave.json` is a supported hand-edit surface
between `plan` and `launch`. The original design doc states the intent at its
lines 408-417 - an earlier draft "trusted a hand-edited `pid`, `worktree`,
`branch`, or `base_sha` directly for destructive git calls and process signals".
`pid` is the one field in that sentence the shipped table does not actually bound.

The defect is therefore a missing row-level predicate, not a structural problem.
Nothing about the module layout, the lock discipline, or abort's two-signal
ownership check changes.

**Why a non-positive-or-1 `pid` is destructive, and what the bound must be.** One
platform fact decides this whole design: `os.killpg(pgid, sig)` is the libc
wrapper for `kill(-pgid, sig)`, on Darwin and under glibc alike. Verified on this
host (Darwin 25.5) rather than assumed: `python3 -c 'import os;
os.killpg(-os.getpid(), 0)'` **succeeds**, which is only possible if `killpg`
negates its argument - a real process-group lookup could never resolve a negative
pgid to the caller's own pid. Everything below follows from that one identity.

| `lane["pid"]` | what `os.killpg` actually does | consequence in `_kill_lane` |
|---|---|---|
| `4242` (a real lane pgid) | `kill(-4242, sig)` | signals that lane's group. Correct. |
| `0` | `kill(0, sig)` - POSIX: every process in the **caller's own** process group | `_pgid_alive(0)` returns True (the caller's group plainly exists), then `kill_fn(0, SIGTERM)` signals the group running `autopilot wave abort` itself. Default SIGTERM disposition terminates it **immediately**, so the 60 s grace and the SIGKILL never run - the abort dies mid-flight, leaving the wave half-cleaned (it saves per lane at `wave_launch.py:522`, and the final status write at `:533` never runs). The flock itself is released by the kernel when the fd closes (`wave.py:175`), so no stale lock survives. |
| `1` | `kill(-1, sig)` - POSIX **broadcast**: every process the caller has permission to signal | strictly worse than `0`. XNU excludes the calling process from the broadcast, so `abort` survives its own signal and proceeds to SIGKILL, while the operator's shell, editor, and every other autopilot loop on the machine take SIGTERM then SIGKILL. |
| negative, e.g. `-5` | `kill(5, sig)` - a plain **single-pid** kill | signals arbitrary pid 5, an unrelated process, with no group semantics at all. |
| `>= 2**31`, e.g. `99999999999999999999` | nothing - `os.killpg` raises `OverflowError: Python int too large to convert to C int` before any syscall | not a wrong signal but an uncaught **crash**: `OverflowError` is not an `OSError`, so `_pgid_alive`'s two excepts (`wave_launch.py:367-370`) do not catch it and `_abort_lane`'s `except (OSError, subprocess.CalledProcessError)` (`:490`) wraps only `_clean_up_lane`, not `_kill_lane` (`:482`). A raw traceback escapes `abort` after earlier lanes were already cleaned and saved, and every retry crashes at the same lane. JSON integers are arbitrary precision, so a hand edit reaches this trivially. |

So the bound is a **range**, `1 < v < 2**31` - not `> 0`, and not a bare `> 1`
either. Two separate mistakes are ruled out here:

- `> 0` would leave `1` accepted, and `1` is the single most destructive value of
  the set. `1` can never be a legitimate lane pgid: `launch` stores a freshly
  spawned session leader's `Popen.pid`, and pid 1 is `launchd`.
- `> 1` alone would leave the overflow row accepted, contradicting the claim that
  bounding the field makes the kill path sound. It is the same defect class as the
  🔴 - an unvalidated `pid` from a hand-editable file reaching `os.killpg` - so
  closing one and not the other in the same two-token edit would be arbitrary.
  `2**31` is the C `int` ceiling `os.killpg` converts to; every real pid on every
  supported platform is far below it (`kern.pid_max` is 99999 on Darwin).

All of these must be refused **before the signal**, which means refused by
`_structural_errors`, not defended against inside `_kill_lane`.

## Module placement

Edits to existing files only. No new files, no new module.

| Path | Change |
|------|--------|
| `skills/run-autopilot/cli/wave.py` | One `_LANE_CHECKS` row: bound `pid` to `None` or an int in `1 < v < 2**31`. |
| `skills/run-autopilot/cli/test_wave.py` | Four rows appended to the existing malformed-lane-field parametrize list. |
| `skills/run-autopilot/cli/test_wave_launch_abort.py` | One new test pinning that `abort()` validates **before** it signals anything. |

No `CHANGELOG.md` entry. The wave verbs are still under `[Unreleased]`
(`CHANGELOG.md` already describes `wave plan|launch|status|abort` there), so this
bound ships inside those existing bullets rather than as its own `### Fixed` line.
Stated explicitly so the changelog self-check neither stalls nor adds a stray
entry.

`cli/wave_launch.py` is deliberately **not** edited by this fix. `_kill_lane`
already reads `lane["pid"]` only after `abort()` has run `_structural_errors` and
returned 1 on any violation, so once the validator bounds the field to a real
pid range the kill path needs no second guard. Adding a redundant check inside
`_kill_lane` would put the same rule in two places and invite them to drift.

**One residual exposure is knowingly left open**, so the sentence above is not
read as more than it says: `status` reads `lane["pid"]` without running
`_structural_errors` (`wave_cli.py:54-55`, no lock, read-only) and reaches
`loop_gates._pid_alive`, which has the same two excepts, so a `pid` at or above
`2**31` in a wave.json that `status` is pointed at still raises `OverflowError`
there. `status` never signals - it probes with signal `0` - so this is a crash in
a read-only verb, not a wrong kill, and `status(repo, wave) -> str` is a frozen
signature with no validator seam. Out of scope for this 🔴; named here rather than
implied away.

## Interfaces & contracts

### 1. `_LANE_CHECKS["pid"]` - bound the field to None or a real pid range

Closes: 🔴 Critical - `_structural_errors`' `pid` check is `v is None or _is_int(v)` with no positivity bound, so a hand-edited or corrupted `"pid": 0` reaches `os.killpg(0, SIGTERM)` in `_kill_lane`, which signals the caller's own process group - under a wave that is the operator's shell or the autopilot loop itself. `order` and `review_slots` are both bounded `> 0` in the same table; `pid` is the one destructive field that is not. (`skills/run-autopilot/cli/wave.py:289`)

*Two corrections to that quoted row, so an implementor is not misled by it:*
`review_slots` lives in `_TOP_CHECKS` (`wave.py:279`), not in `_LANE_CHECKS` -
only `order` (`:283`) is in the same table as `pid` (`:289`). And the bound this
contract specifies is the range `1 < v < 2**31`, not the `> 0` the row's wording
implies: `pgid == 1` is a broadcast and is worse than the `0` the row names, and a
value at or above `2**31` crashes `os.killpg` with an uncaught `OverflowError`.
See `## Architecture fit`'s table for all four cases.

In `skills/run-autopilot/cli/wave.py`, the `_LANE_CHECKS` entry for `pid` becomes
exactly this - the comment is part of the contract, write both lines:

```python
    # A real pgid: 0 is the caller's own group, 1 is kill(-1)'s broadcast, and
    # 2**31 or more raises OverflowError out of os.killpg. abort() signals this.
    "pid": lambda v: v is None or (_is_int(v) and 1 < v < 2**31),
```

Replacing exactly:

```python
    "pid": lambda v: v is None or _is_int(v),
```

Contract of the changed predicate:

- `None` -> valid (a planned or fully-aborted lane has no pid). Unchanged.
- an `int` in `2 .. 2**31 - 1` -> valid. This is every real pid.
- `0` -> **invalid**. New. `killpg(0, sig)` signals the caller's own group.
- `1` -> **invalid**. New. `killpg(1, sig)` is `kill(-1, sig)`, a broadcast to
  every process the caller may signal. The worst value of the set.
- a negative `int` -> **invalid**. New. `killpg(-5, sig)` is `kill(5, sig)`, a
  plain single-pid kill of an unrelated process.
- an `int` `>= 2**31` -> **invalid**. New. `os.killpg` raises `OverflowError`,
  which is not an `OSError` and is caught nowhere on the abort path.
- `bool` (`True`/`False`) -> invalid, unchanged: `_is_int` already excludes
  `bool` via `not isinstance(value, bool)`, and that exclusion must survive this
  edit. `1 < True` is `False` so `True` would be refused by the range anyway, but
  `_is_int` is what refuses it *as a type error*; do not drop the conjunct.
- a `float` (e.g. `1.5`) or a `str` (e.g. `"4242"`) -> invalid, unchanged.

Write the chained comparison `1 < v < 2**31` rather than two `and`ed clauses; it
is the form the rest of this file would use and it reads as the range it is.

`_is_int` itself is **not** changed:

```python
def _is_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)
```

The violation message is produced by the existing `_collect_shape_errors` loop
and its wording is unchanged - a lane whose `pid` fails this predicate yields
`lane <name>: malformed field pid`, the same string every other malformed lane
field produces. No new message, no new error class, no signature change to
`_structural_errors`, `_collect_shape_errors`, `validate`, `abort`, or
`_kill_lane`.

**Reuse, not invention.** This is the predicate shape already used twice in this
file - `"review_slots": lambda v: _is_int(v) and v > 0` (`_TOP_CHECKS`) and
`"order": lambda v: _is_int(v) and v > 0` (`_LANE_CHECKS`) - wrapped in the
`v is None or (…)` form this field's nullability requires, with a range instead of
a floor because this value is passed to `os.killpg`. The parentheses are for the
reader, not the parser: `and` already binds tighter than `or`, so the unbracketed
form means the same thing. Write them anyway - the next reader should not have to
know Python's precedence table to audit a predicate that gates a kill.

### 2. Four parametrize rows pinning the new refusals

Closes: the same 🔴 row - a validator bound with no test is a bound the next de-slop pass deletes.

In `skills/run-autopilot/cli/test_wave.py`, append four rows to the existing
`("field", "value")` parametrize list feeding
`test_structural_errors_names_a_malformed_lane_field` (the list at `:603-633` that
already carries `("pid", "4242")`, `("pid", 1.5)`, `("pid", True)` at `:613-615`):

```python
        ("pid", 0),
        ("pid", 1),
        ("pid", -1),
        ("pid", 2**31),
```

One row per case in the contract's range, in the contract's own order.
`("pid", 1)` is the one a careless reading omits - it is the broadcast value - and
`("pid", 2**31)` is the one that pins the upper bound, without which `> 1` and the
range are indistinguishable to the suite. The `0` and `-1` rows mirror the
`("review_slots", 0)` / `("review_slots", -1)` pair already at `:583-584`, so the
two tables are tested to the same standard. No new test function, no new fixture,
no change to the existing test body or its assertion - the parametrize list is the
whole edit. `_wave()`'s lanes carry `pid: None` (`test_wave.py:53`), so each
`_set(..., "pid", <value>)` produces exactly one violation.

**Do not weaken the sibling cases.** `("pid", True)` must stay in the list. It is
the case that fails if someone "simplifies" the predicate to a bare comparison
with no `_is_int` conjunct.

### 3. One test binding the validator to the SIGNAL half of the kill path

Closes: the same 🔴 row - items 1 and 2 pin the bound, this pins that `abort()` applies it before it signals. Without it the 🔴 reopens on a refactor that reorders those two steps while every parametrize row stays green.

**What is already pinned, and what is not.** `test_wave_launch_abort.py:160`,
`test_abort_refuses_a_structurally_invalid_wave_before_touching_anything`, already
covers the *filesystem* half: it breaks `order`, then asserts `abort() == 1`,
`wave_path.read_bytes()` unchanged (`:182`), every worktree present (`:185`), every
branch present (`:186`) and every PRD still in the lane (`:188-189`). Do not
duplicate it. Two things leave the *signal* half unpinned: `_launched` clears every
lane's `pid` to `None` (`:96-99`), so `_kill_lane` returns at
`wave_launch.py:390` and no signal is ever attempted; and that test's
`order = None` would make a reordered `abort` die inside
`sorted(wave["lanes"], key=lambda each: each["order"])` (`wave_launch.py:520`) with
a `TypeError` *before* reaching the kill loop. A `pid` case leaves `order`
sortable, so it actually drives the loop. That is the gap this test closes.

In `skills/run-autopilot/cli/test_wave_launch_abort.py`, add one test alongside the
existing abort tests, following that file's conventions (`_launched`, a recording
`kill_fn`):

- Build a launched wave with `_launched`, then set one lane's `pid` to `0`, leaving
  every other field - `order` included - valid and sortable.
- Call `abort(repo, wave_path, kill_fn=<recorder>)`. **Pass no `run_git`.** The
  refusal branch returns at `wave_launch.py:517`, before the first git call at
  `:518`, so no injection is needed - which is exactly why the sibling test at
  `:160` passes none either. (A bare stub returning `None` would raise
  `AttributeError` on `.stdout` in `_worktree_branches` on the fail-first run, where
  `run_git` *is* reached.)
- **Assert the recorder was never called**, and assert `wave.json` on disk is
  byte-identical. **These two are the load-bearing assertions** - they are the only
  ones that fail against the pre-change code.
- Assert the return value is `1` as a secondary check only. Note in a comment that
  `== 1` also holds *before* the fix, for the opposite reason: `_pgid_alive(0)` is
  permanently True, so `_kill_lane` burns `_wait_for_exit(pgid, 60)` then
  `_wait_for_exit(pgid, 10)` (`wave_launch.py:393-397`) and returns
  `"process group 0 survived SIGKILL"`. An `== 1`-only test would pass pre-fix.
- **The fail-first run of this test takes about 70 seconds** for that same reason.
  Expect it, do not "fix" it by shortening the grace windows.

Name it for the rule it enforces, not the function it calls - e.g.
`test_abort_refuses_an_out_of_range_pid_without_signalling_anything`.

**Precision on the recorder:** it pins that no signal went through the injected
kill seam. `_pgid_alive` calls the real `os.killpg(pgid, 0)` directly
(`wave_launch.py:366`) and bypasses `kill_fn`, so the assertion is "no signal
through the kill seam", not "no `killpg` call in the process".

## Data flow

Unchanged in shape; one refusal moves earlier.

```
operator hand-edits wave.json  ──►  autopilot wave abort
                                      │
                                      ├─ locked(wave_path)
                                      ├─ load(wave_path)
                                      ├─ _structural_errors(repo, wave)
                                      │    └─ _collect_shape_errors
                                      │         └─ _LANE_CHECKS["pid"]  ◄── the fix
                                      │              pid outside 1 < v < 2**31
                                      │                       ──►  "lane l1: malformed field pid"
                                      │                             printed, return 1,
                                      │                             NO signal, NO git call,
                                      │                             wave.json untouched
                                      └─ (only a sound wave continues)
                                           └─ _abort_lane ──► _kill_lane
                                                └─ os.killpg(pgid, SIGTERM)   pgid is now
                                                                              a real pid
```

Before the fix every out-of-range `pid` fell through the validator and reached
`os.killpg`. After it, the existing refusal branch in `abort()` catches it -
prints every violation, prints `refusing to touch this wave.json`, returns 1. The
same guard covers `launch`, which calls `validate()` -> `_structural_errors` on
the same table, though `launch` never signals anything, and `plan`, which calls it
through `_reject_existing_wave` (`wave.py:195`).

`status` is the one verb that reads `lane["pid"]` without running
`_structural_errors` (`wave_cli.py` dispatches it lock-free and read-only), but it
reaches only `_pid_alive` with signal `0` - a liveness probe, never a kill - so an
unvalidated pid there misreports a row and destroys nothing. Left as is
deliberately: `status(repo, wave) -> str` is a frozen read-only signature.

## Reuse inventory

- `skills/run-autopilot/cli/wave.py:279` - `"review_slots": lambda v: _is_int(v) and v > 0`. The bounded-int predicate shape this fix needs, in the same file's sibling table (`_TOP_CHECKS`, not `_LANE_CHECKS`). **How to use:** copy the `_is_int(v) and v > N` shape into the `pid` row wrapped in the `v is None or (…)` form - but with `N = 1`, not `0`: `review_slots` only has to be a usable count, while `pid` is passed to `os.killpg`, where `1` is a broadcast.
- `skills/run-autopilot/cli/wave.py:283` - `"order": lambda v: _is_int(v) and v > 0`. Second instance of the same predicate, in the very table being edited. Confirms the shape is this module's convention rather than a one-off.
- `skills/run-autopilot/cli/wave.py:266` - `_is_int`. The bool-excluding int test, reused unchanged; no new helper is needed.
- `skills/run-autopilot/cli/test_wave.py:583-584` - `("review_slots", 0)` and `("review_slots", -1)` in the malformed-top-level-field parametrize list. **How to use:** the test edit mirrors these two rows into the malformed-lane-field list as `("pid", 0)` and `("pid", -1)`, plus the `("pid", 1)` row this field needs and `review_slots` does not.
- `skills/run-autopilot/cli/test_wave_launch_abort.py:160` - `test_abort_refuses_a_structurally_invalid_wave_before_touching_anything`. The existing validation-before-mutation test. **How to use:** copy its frozen-bytes (`:182`) and untouched-worktree/branch/PRD assertions (`:185-189`) into contract item 3's new test; the new test adds the `kill_fn` recorder and a sortable `order`, which is the only part that test cannot cover. Named here so a de-slop pass reads item 3 as the complement it is, not as a duplicate.
- `skills/run-autopilot/cli/loop_gates.py:26` - `_pid_alive`, and `:49` `_pid_tagged`. Inspected and deliberately **not** reused: the original design ruled that `pid == pgid` from creation makes a separate tag lookup "not needed or correct here" (design lines 431-436), and the cycle-1 gate settled the corresponding finding (FIX-02) on that ground. Named here so the next reader does not re-open it.
- Greps run for a shared validation helper outside this module: `rg -n 'def _is_int|_is_int\(v\)|> 0|positive' skills/run-autopilot/cli/wave.py skills/run-autopilot/cli/schema.py` (hits only the four `wave.py` lines above - `cli/schema.py`, the `state.json` validator, has no positive-int helper to borrow and validates a different file entirely), and `rg -n 'def _pid_alive|killpg|def live_wrapper_pid|_pid_tagged' skills/run-autopilot/cli/loop_gates.py` (hits the liveness convention above). `~/.claude/rules-library/rationalizations.md` was not consulted; the sweep used verb/noun synonyms chosen here (validate/check/bound × pid/pgid/int), and says so per the skill's absent-file rule.

## Alternatives considered

**A. Bound the field in `_LANE_CHECKS` (chosen, and the smallest diff).** One
lambda, three parametrize rows. Refuses at the designed choke point, so every
caller - `validate`, `abort`, and anything added later - inherits it for free.
The message, the error path and every signature stay as they are.

**B. Guard inside `_kill_lane`.** Add `if pgid is None or pgid <= 1 or not
_pgid_alive(pgid): return None` (or raise). Rejected: it puts the rule in the
kill path instead of the validation layer, so `launch`/`validate` still accept a
wave the abort path considers malformed, and the two rules can drift. It also
turns a *refusal to touch the file* into a *silent skip* of one lane, which is
exactly the class of quiet incomplete cleanup the `abort_failed` status was
introduced to stop. A malformed control file should refuse loudly before any
lane is touched, not be silently routed around per lane.

**C. Add a `pid` positivity check AND a `_kill_lane` guard (defence in depth).**
Rejected as over-engineering under this repo's own standards: `abort()` cannot
reach `_kill_lane` without `_structural_errors` returning empty, so the second
check is unreachable-by-construction code whose only effect is to make the
validator look optional. The 🔴 exists because one layer was missing a row, not
because one layer is the wrong number of layers.

Chosen A. It is the smallest version of the idea, so nothing extra needs
justifying.

## Risks & edge cases

- **Narrowing the bound back to `> 0` or `> 1`.** Both are mistakes this design already made and had corrected by review: the first draft wrote `> 0` (dispatch 1 caught that it still admits the broadcast value `1`), the second wrote `> 1` (dispatch 2 caught that it still admits the `OverflowError` range). The bound is the range `1 < v < 2**31`. An implementor who "corrects" it toward the 🔴 row's `> 0` wording reintroduces the worst case.
- **The bound now also refuses `wave plan`, not just `wave abort`.** `plan` validates an existing wave.json through `_reject_existing_wave` (`wave.py:195`), so after this fix a hand-edited out-of-range `pid` refuses `plan` too: the operator can neither abort the wave nor plan a new one until wave.json is hand-fixed. That is exactly the existing behaviour for every other malformed field, and the exit is to set the lane's `pid` to `null`. Accepted, and stated because the pre-fix behaviour was to silently accept and then signal.
- **`bool` regression.** A predicate written as a bare comparison with no `_is_int(v)` conjunct changes how `"pid": true` is refused (`True > 1` is `False`, so it would still fail, but as a value error rather than the type error the table means), and `("pid", True)` is the row that notices. Keep the conjunct.
- **A lane legitimately carrying `pid` of `0`, `1`, or negative.** Not reachable: `pid` is written only by `launch`'s `_spawn_lane`/`_launch_lane` from a real `Popen.pid` (a fresh session leader, so always well above 1), and cleared to `None` by `_abort_lane`. So no wave this code produces can trip the new bound; only a hand edit or file corruption can, which is the case the fix is for. No migration, no back-compat shim.
- **An already-running wave whose `wave.json` predates the fix.** Unaffected - its pids are real positive ints, so the stricter predicate accepts them unchanged. There is no stored-schema version to bump.
- **Same-table collision with this cycle's 🟠 findings.** The confirmed `base_sha`-not-validated HIGH edits `_TOP_CHECKS` in the same `wave.py` region, and the `wip/` -> `backlog/` and `ProcessLookupError` HIGHs edit `wave_launch.py`. The `base_sha` fix and this one touch adjacent dict literals in one file: they must land in the same task or in sequenced tasks, never as two parallel rework agents, or the second overwrites the first's hunk. **Planner note: group the `wave.py` validator fixes into one task.**
- **Likely next changes after this PRD, and whether this boxes them in.** (1) PRD 00215 assembles a launched wave and will add lane fields to `wave.json`; each new field needs its own `_LANE_CHECKS` row, and this fix makes the positive-int shape the obvious precedent to copy - it widens the pattern rather than narrowing it. (2) PRD 00217's review-slot semaphore reads `review_slots`, already bounded `> 0`; untouched. (3) A future `wave land` verb adds the wave-level `"done"` status the enum already accepts; untouched. Nothing here constrains any of the three.
- **Abort's refusal message gives the operator no printed way out - deliberately left alone.** The shipped message is `refusing to touch this wave.json` (`wave_launch.py:516`); the original design specified a second clause, "fix the listed fields by hand first" (original design:414-415), which the implementation dropped, while `plan`'s sibling refusal kept its equivalent (`wave.py:200-201`). This fix strictly increases how often an operator meets that message. **Decision: out of scope for this rework.** It is a message-text change on a path this 🔴 does not touch, it would edit `wave_launch.py` - the one file this fix deliberately leaves alone - and the per-violation lines printed above it already name the offending field. Recorded here so the next cycle can pick it up as its own item rather than rediscovering it.
- **What this fix does NOT close.** The cycle's three confirmed 🟠 findings are out of this doc's scope by the skill's own rule (the rework design covers 🔴 rows): abort returning `wip/*` to main `wip/` instead of main `backlog/`, the `ProcessLookupError` race between the liveness probe and the kill, and `base_sha` missing from `_TOP_CHECKS`. They are reworked as ordinary `[D1]` tasks without a `### Contract` block. Stated here so the contract above is not mistaken for the cycle's whole fix.

## Test strategy outline

- **The four new parametrize rows are the fail-first check.** `("pid", 0)`, `("pid", 1)`, `("pid", -1)` and `("pid", 2**31)` all fail against the pre-change predicate (it accepts any non-bool int), and pass after it. Run `test_structural_errors_names_a_malformed_lane_field` against the unedited `wave.py` once to watch all four fail, per the repo's bug-fix rule that the regression test fails once before the fix.
- **The sibling cases are the guard against a wrong fix.** `("pid", True)`, `("pid", 1.5)`, `("pid", "4242")` must all still fail validation, and `test_structural_errors_accepts_a_launched_lane` (which sets `pid=4242`) must still pass - that is the positive case proving the bound did not become "no pid allowed".
- **No new test file, no new test function in `test_wave.py`.** Four list rows. The existing parametrized test body already asserts the `lane <name>: malformed field <field>` message, so the new cases inherit the message assertion.
- **One new test in `test_wave_launch_abort.py`, pinning the SIGNAL half of the order.** The rows above pin the validator; they do not pin that `abort()` runs it *before* the kill loop. The filesystem half of that order is already pinned by `test_abort_refuses_a_structurally_invalid_wave_before_touching_anything` (`:160`), but its fixture clears every `pid` to `None` so no signal is ever attempted, and its `order = None` would make a reordered `abort` die in `sorted()` before the kill loop. The new test uses an out-of-range `pid` with a sortable `order` and a recording `kill_fn`, and its load-bearing assertions are *recorder never called* and *wave.json byte-identical*. Full specification in `## Interfaces & contracts` item 3, including why `== 1` alone would pass pre-fix and why the fail-first run takes ~70 s.
- **No changes to the existing kill-path tests.** The fix adds no behaviour to `_kill_lane`; `test_pgid_alive_probes_the_group_not_a_single_pid`, `test_abort_kills_a_group_whose_leader_has_already_exited` and `test_abort_leaves_a_lane_whose_group_outlived_sigkill_mid_loop` stay exactly as they are.
- **Verify:** `uv run --no-project --with pytest python -m pytest -q skills/run-autopilot/cli/test_wave.py` green, then `bash dev/bin/release-checks` green (its `[checks] waves` block runs all four wave suites).

## Review log

dispatch 1 (claude): cardinal-sin 0, blocker 1, non-blocker 2, question 2

**Blocker (fixed).** The draft bounded `pid` at `> 0`, which still admits `pid: 1`.
`os.killpg(pgid, sig)` is the libc wrapper for `kill(-pgid, sig)`, so `killpg(1, …)`
is `kill(-1, …)` - a broadcast to every process the operator may signal, a
strictly larger blast radius than the `pid: 0` the 🔴 named. Independently verified
before acting on it: `python3 -c 'import os; os.killpg(-os.getpid(), 0)'` succeeds
on this host, which is only possible if `killpg` negates its argument. Bound
changed to `> 1` throughout, a `("pid", 1)` parametrize row added, and
`## Architecture fit` now derives all four cases from that one identity.

**Non-blocker 1 (fixed, because it was the blocker's own evidence).** The draft's
signal mechanics were wrong in two places: it claimed `os.killpg(-1, …)` was the
broadcast (the sign is inverted - a negative pgid is a plain single-pid kill), and
that pgid `0` would reach the SIGKILL after a 60 s grace (it does not - the first
SIGTERM terminates the aborting process itself immediately). Both sentences were
the rationale the wrong bound rested on, so correcting them was part of fixing the
blocker rather than separate work. Replaced with the derivation table in
`## Architecture fit`.

**Non-blocker 2 (adopted, recorded as a deliberate deviation from the
fix-blockers-only rule).** `## Test strategy outline` had ruled out an
`abort()`-level test on the grounds it would "only re-test the validator". That
reason does not hold: such a test pins the ORDER of validation versus the kill
loop, which nothing currently asserts and which a refactor could silently invert
while every parametrize row stayed green. Adopted as contract item 3 rather than
merely logged, because it is the only test that binds the validator to the attack
path the 🔴 describes; leaving it as a logged non-blocker would have shipped the
fix with its central invariant untested. Cost: one test, in a file already in the
rework batch.

**Question 1 (answered in the doc).** The 🔴 row's own wording says `review_slots`
is bounded "in the same table" as `pid`; it is not - `review_slots` is in
`_TOP_CHECKS`, only `order` shares `_LANE_CHECKS` with `pid`. The quoted row is
reproduced verbatim as the skill requires, so the correction is annotated
immediately beneath it in `## Interfaces & contracts` §1 instead of altering the
quote.

**Question 2 (answered in the doc).** Whether `CHANGELOG.md` is in scope. It is
not: the wave verbs are still under `[Unreleased]`, so this bound ships inside the
existing bullets. Stated in `## Module placement` in one sentence so the repo's
blocking changelog self-check neither stalls the implementor nor produces a stray
entry.

Engagement: 5 findings, every one anchored to a doc section or `file:symbol`
(`wave.py:289`, `:279`, `:283`, `:266`, `test_wave.py:583-584`, `:613-615`,
`wave_launch.py:366`, `:392`, `:482`, `:512`, `:521`). Not under-engaged; no
engagement re-run needed.

dispatch 2: codex unavailable, Claude fallback
dispatch 2 (claude-fallback): cardinal-sin 0, blocker 0, non-blocker 5, question 1

**Why the fallback.** codex WAS dispatched (`codex exec`, `gpt-5.6-sol`, xhigh,
session `01a0dcb4-5a4f-74a2-a84b-dd3576924374`) and ran for over 30 minutes without
emitting findings, past the skill's ~10-min×2 deadline for helper-script Bash
dispatches. Its transcript shows it did real work first - it read the source, and
it probed both the predicate's truth table (`None`/`2` valid; `0`, `1`, `-1`,
`True`, `False`, `1.5`, `"4242"` invalid) and `os.killpg`'s overflow behaviour -
but it never reached a findings block. Per the skill's codex-outage rule the
dispatch degraded to a fresh Claude reviewer with the same package, and codex's two
probe results were handed to that reviewer as established facts rather than
discarded. The overflow probe is what produced non-blocker 5 below, so the codex
leg contributed its findings through the fallback even though it never reported.

**No blockers and no cardinal sins, so dispatch 3 did not run** (it is conditional
on dispatch 2 finding one of those). Five non-blockers and one question follow. The
skill says log non-blockers rather than fix them; **four were applied anyway and
one was answered**, each for a reason given below, because
`## Interfaces & contracts` is copied verbatim into the fix task and a wrong line
there is a defect in the deliverable, not a preference.

**Non-blocker 1 (applied).** `_structural_errors` has three callers, not the two
the doc claimed: `plan()` also validates, through `_reject_existing_wave`
(`wave.py:195`). Applied because the omission hid a real consequence - after this
fix an out-of-range `pid` refuses `wave plan` as well as `wave abort`, so the
operator can do neither until wave.json is hand-fixed. `## Architecture fit` and
`## Data flow` now name all three verbs, and `## Risks & edge cases` states the
consequence and the exit (`"pid": null`).

**Non-blocker 2 (applied).** The `pid: 0` table row claimed the abort "dies
mid-flight with the wave lock held". Wrong: `locked()` is an `fcntl.flock` inside a
`with open(...)` (`wave.py:175`), which the kernel releases when the fd closes. The
real residue is a half-cleaned wave - `abort` saves per lane (`:522`) and the final
status write (`:533`) never runs. Applied because this table is the doc's entire
derivation for the bound, and it is the second time a wrong mechanics claim has
been found in it.

**Non-blocker 3 (applied).** Contract item 3's justification was false.
`test_abort_refuses_a_structurally_invalid_wave_before_touching_anything` (`:160`)
already pins validation-before-mutation for the filesystem half. What is genuinely
unpinned is only the signal half, because that test's fixture clears every `pid` to
`None` and its `order = None` would make a reordered `abort` die in `sorted()`
first. Applied because the false premise would have read to a de-slop pass as a
duplicate test and got item 3 deleted. Item 3 now states what the existing test
covers, what it cannot, and why; the existing test is in `## Reuse inventory`.

**Non-blocker 4 (applied).** Contract item 3 was not writable as specified:
`run_git=<fake>` named no helper that exists (the refusal returns before the first
git call, so no injection is needed at all), and `assert ... == 1` passes *before*
the fix because `_pgid_alive(0)` never goes False - so an `== 1`-only test is
vacuous and its fail-first run burns ~70 s in the two grace windows. Applied
because this is the contract an implementor copies byte-for-byte; shipping it would
have cost a rework round. Item 3 now drops `run_git`, marks recorder-never-called
and byte-identical-wave.json as the load-bearing pair, and warns about the 70 s.

**Non-blocker 5 (applied, and it widened the bound).** `> 1` did not make the kill
path "sound with no second guard": the predicate accepted any `int >= 2`, JSON
integers are arbitrary precision, and `os.killpg(2**31, 0)` raises `OverflowError`,
which is not an `OSError` and is caught nowhere on the abort path - a raw traceback
out of `wave abort` after earlier lanes were already cleaned and saved. Applied
rather than logged because it is the *same defect class as the 🔴* (an unvalidated
`pid` from a hand-editable file reaching `os.killpg`), at the same edit site, in the
same test list: closing one and leaving the other would have been arbitrary. The
bound became the range `1 < v < 2**31` and a `("pid", 2**31)` row was added.
`status`'s equivalent exposure through `loop_gates._pid_alive` is a crash in a
read-only verb with no validator seam, and is named as knowingly out of scope in
`## Module placement`.

**Question (answered in the doc).** Abort's refusal prints
`refusing to touch this wave.json` but dropped the original design's second clause,
"fix the listed fields by hand first", which `plan`'s sibling refusal kept. Since
this fix increases how often an operator meets that message, the doc had to take a
position: **decided out of scope**, recorded in `## Risks & edge cases` with the
reason (it is a message-text change in `wave_launch.py`, the one file this fix
deliberately does not touch, and the per-violation lines above it already name the
offending field).

Engagement: 6 findings, every one anchored, with a separate anchored
"checked and correct" list covering the byte-exactness of contract items 1 and 2,
the absence of any route to `os.killpg` that skips the validator, and the fact that
no existing test breaks under the new bound. Not under-engaged.

result: ok
