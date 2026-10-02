# Rework design: 00218-leave-sessions-at-task-boundaries-and-run-one-devon-round-v1 (cycle 1)

Source review: dev/local/reviews/00218-leave-sessions-at-task-boundaries-and-run-one-devon-round-v1-review-1.md (head_sha e5a8479cb07bb3d9d62fbdb873aa4dab3b271c5e)

## Architecture fit

Prior fix: none - there was no prior rework fix. This is cycle 1, so every
CRITICAL below was introduced by the PRD's own build pass (tasks 1-7,
`83165038..e5a8479`), not by an earlier rework.

The one 🔴 row lands entirely inside the context-cap hook's headroom rule, which
is the PostToolUse layer: `skills/run-autopilot/scripts/autopilot_context_cap_hook.py`
plus its pure sibling modules (`_cap_task_record`, `_cap_handoff_marker`,
`_cap_state_write`, `_cap_turn_counts`, `_walk_up`). Nothing in the CLI layer
(`cli/`) changes: `runner.spawn` already exports `_AUTOPILOT_SESSION_DEADLINE`
correctly (`cli/runner.py:293-303`, `_child_env_with_deadline`) and
`_cap_task_record.last_task_wall` already computes the wall correctly and is
tested. The defect is exactly the seam between the two: nothing reads either.

`git diff --stat 83165038f9dfd92ebf64ae94f38f61b946a17ee3..HEAD` over the PRD's
whole work range touches 24 files, 1066 insertions, 137 deletions. The two files
the 🔴 lives between are `skills/run-autopilot/scripts/autopilot_context_cap_hook.py`
(+31/-... ) and `skills/run-autopilot/cli/runner.py` (+69), both from task 4.

**The binding structural constraint.** `autopilot_context_cap_hook.py` is
**exactly 800 lines**, which is the project's file-size cap (rubric rule R13).
Task 4 already had to spend a style commit (`6bd1b69`, "trim the hook file to the
800-line cap") to land there. The file therefore cannot absorb even a single new
import line, and every candidate fix that adds lines to it is unbuildable as
written. This design's shape is dictated by that fact: it must **remove** more
from the hook than it adds. This is why the fix extracts rather than patches.

## Module placement

| Path | New or edit | What |
|---|---|---|
| `skills/run-autopilot/scripts/_cap_headroom.py` | **new file** | Three things: the pure headroom predicate parameterised by its caps (`headroom_exhausted`), the `_AUTOPILOT_SESSION_DEADLINE` parse (`secs_left_from_env`), and the rotation/ceiling trust filter on the last task's wall (`trusted_last_wall`). |
| `skills/run-autopilot/scripts/autopilot_context_cap_hook.py` | edit | Delete the predicate body; bind its caps with a `functools.partial` under the same private name; add one import line; wire the two time arguments at the one call site. Line 72 is untouched. Net effect must be a SHORTER file. |
| `skills/run-autopilot/scripts/test_autopilot_cap_headroom_margin.py` | edit | Replace the four vacuous predicate-only time-term tests with hook-level tests that control the env var and carry a stamped state; add the rotation/pause/honest-wall cases, the calls-term margin cases, and the file-size pin. |
| `skills/run-autopilot/scripts/test_cap_headroom_module.py` | **new file** | Unit tests for the new module's own surface: `secs_left_from_env`, `trusted_last_wall`, `headroom_exhausted`. |
| `dev/bin/release-checks` | edit | Add the new test file, so the 🔴's regression pins actually run at release (`## Test strategy outline` item 7). |

A new sibling `_cap_*` module is not a new abstraction: the hook already imports
five pure siblings (lines 66-74) for exactly this reason, so `_cap_headroom` is
the sixth instance of an established idiom (see `## Reuse inventory`). No
production behaviour outside the headroom rule changes.

## Interfaces & contracts

Closes: [4/4] 🔴 Time term is never wired into the hook. `_handle_below_cap` still calls `_headroom_exhausted(total, count, last_usage, last_calls)` with no `secs_left` or `last_wall`. The hook never reads `_AUTOPILOT_SESSION_DEADLINE` and never imports `last_task_wall` (only `last_task_cost, record_task_bounds` at line 72). The runner exports a deadline that nothing reads, and the stamps feed only the report, so the PRD's "session hands off before a task it cannot finish" does not exist at runtime. The tests call the predicate directly. `test_time_term_hands_off_when_the_deadline_is_near` and `test_malformed_deadline_drops_the_time_term` cannot fail if the wiring is missing, and no test drives the hook with a deadline. The hook file is exactly 800 lines, so the fix must move the deadline parse into a sibling module.

Also closes (folded into this task because the 🔴 fix must ship with the pin that
would have caught it):

Closes: [2/4] 🟠 The tests for the time term give false confidence. `test_time_term_hands_off_when_the_deadline_is_near`, `test_time_term_is_inert_without_a_deadline`, `test_time_term_is_inert_without_a_completed_task` and `test_malformed_deadline_drops_the_time_term` call `_headroom_exhausted(..., secs_left=..., last_wall=...)` directly. None runs the hook with the env var set and a stamped state, so the missing wiring passes. `test_malformed_deadline_drops_the_time_term` passes `secs_left=None` itself and asserts nothing about deadline parsing. No test exercises the hook end to end for the time term

Closes: [2/4] 🟡 The calls-term margin (`TURN_TRIPWIRE - count < last_calls * HEADROOM_MARGIN`) is unpinned. Dropping `* HEADROOM_MARGIN` on that term breaks no test. The docstring says "251 calls leave 199, under the margined 250-call threshold", but 199 < 200 also fires without the margin. Add a case such as `_headroom_exhausted(None, 220, 150_000, 200)` (True; 230 < 250) plus the exact boundary (count 200 is False).

### New module `skills/run-autopilot/scripts/_cap_headroom.py`

Stdlib only, and no `cli/` import. Pure: nothing here touches disk, and nothing
reads `os.environ` itself - the caller passes the mapping in, so tests need no
monkeypatching.

**The two filter functions below are given as signature + docstring contract, not
as finished code.** Their bodies are the implementor's, derived from those
docstrings. Only `headroom_exhausted`'s three term expressions are supplied
verbatim (in the block after this one) because they must stay byte-identical to
the ones being relocated. A `def` with only a docstring returns None, which for
`secs_left_from_env` would drop the time term always - that is, reproduce the 🔴.
Do not ship the skeleton as-is.

```python
"""Headroom rule for the context-cap hook (PRD 00200, PRD 00218).

Pure: the caller supplies the environment mapping and the clock. Split out of
`autopilot_context_cap_hook.py` to keep that file under the 800-line limit;
imported as a sibling module, like `_cap_task_record`.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

DEADLINE_ENV = "_AUTOPILOT_SESSION_DEADLINE"
# Backstop ceiling, NOT the primary filter. The primary signal is
# `state.cap_rotations`, which names every rotated task exactly (see
# `trusted_last_wall`); this ceiling only catches the spans state does not
# record - a watchdog kill or an operator pause (this project has recorded an
# 11h one). 10800 is `_AUTOPILOT_SESSION_MAX_REVIEW`, the LARGEST session
# wall-clock cap the pack ships (`cli/routing.py` spawns review/rework
# sessions with it; the headroom rule is live there because `_guarded_phase`
# admits `phase == "review"` with rework tasks queued). A span above the
# largest cap any session gets cannot be one session's work. Deliberately NOT
# 7200: a rework session may legitimately run a 2.5h task, and a 7200 ceiling
# would discard that genuine wall and leave the term unable to protect it.
# Above the ceiling the term is DROPPED, never clamped - clamping to the cap
# still fires immediately, because `secs_left ~= cap` at session start and
# `cap < cap * HEADROOM_MARGIN`.
# This tracks the DEFAULT of `_AUTOPILOT_SESSION_MAX_REVIEW`, which an operator
# can raise (`cli/routing.py`, `cli/loop_act.py` both read it with that
# default). Raise this constant with it, or the backstop starts discarding
# honest walls.
MAX_CREDIBLE_WALL_SECS = 10800


def secs_left_from_env(env: Mapping[str, str], now: int) -> int | None:
    """Seconds left before the session deadline, or None when there is no
    usable deadline. `env[DEADLINE_ENV]` is an epoch-second int written by
    `runner.spawn`; absent, empty, or non-int returns None, which drops the
    headroom rule's time term. A deadline already past returns a value <= 0
    (not None): a session out of time must still hand off."""


def trusted_last_wall(state: dict[str, Any]) -> int | None:
    """The last completed task's wall in seconds, or None when that span cannot
    be trusted as one session's own work (which drops the time term).

    ONE reverse walk over `state["tasks"]` finds the last `completed` entry
    whose `started_at`/`done_at` are both ints with a non-negative difference,
    and derives BOTH the span and that entry's `id` from that same entry. The
    pairing is the point: the rotation test below must be asked about the task
    the span actually came from, never about some other "last completed" task.

    Two reasons a span is not work. (1) The task ROTATED: `record_task_bounds`
    stamps `started_at` once and never replaces it (a PRD contract), so a task
    cut mid-flight and finished later carries every idle second between. Its id
    appears in `state["cap_rotations"]` as a `task_id`, so this is answerable
    exactly rather than by guessing from the magnitude. **Only that one id
    matters**: `cap_rotations` is per-PRD and is cleared at PRD completion, so
    "any rotation in this PRD" would switch the time term off for the whole
    remainder of every PRD that ever rotated - precisely the long PRDs the term
    exists for. (2) The span exceeds `MAX_CREDIBLE_WALL_SECS` - the backstop
    for what state does not record (a watchdog kill, an operator pause).

    Tolerate a malformed `cap_rotations`: not a list, entries that are not
    dicts, an entry `{}`, or a `task_id` of None must never raise and must
    never match. A None id on the measured task matches nothing.

    Reason (1) is why a magnitude test alone is wrong: a task that ran 70 min
    before rotating, waited 5 min for the relaunch and took 15 min more spans
    6000s, which is under any credible ceiling yet is still dead time. Acting
    on it hands off at the FIRST fire of the next session, so that session does
    one task and leaves - multiplying the orientation cost this PRD exists to
    cut.
    """


def headroom_exhausted(
    total: int | None,
    count: int | None,
    last_usage: int,
    last_calls: int,
    secs_left: float | None = None,
    last_wall: float | None = None,
    *,
    usage_cap: int,
    turn_tripwire: int,
    margin: float,
) -> bool:
    """True when the next task would not fit in the context left under
    `usage_cap`, the calls left under `turn_tripwire`, or the wall-clock
    seconds left before the session deadline, each judged by what the last
    task cost times `margin`. A None on either side of a term drops that
    term."""
```

`headroom_exhausted`'s three term expressions are byte-for-byte the ones the hook
carries today, with the module-level constants replaced by the keyword
parameters:

```python
    if total is not None and usage_cap - total < last_usage * margin:
        return True
    if count is not None and turn_tripwire - count < last_calls * margin:
        return True
    return (
        secs_left is not None
        and last_wall is not None
        and secs_left < last_wall * margin
    )
```

### Edits to `skills/run-autopilot/scripts/autopilot_context_cap_hook.py`

`USAGE_CAP`, `TURN_TRIPWIRE`, `HEADROOM_MARGIN`, `FIRST_TASK_USAGE_ESTIMATE` and
`FIRST_TASK_CALLS_ESTIMATE` **stay in this module, with their comment blocks
unchanged**. They are referenced by 15 other files (`cli/routing.py`,
`scripts/tracon/model.py` and its mirror test, `references/phase-build.md`,
`references/state-schema.md`, `scripts/README.md`, `work/scripts/test_handoff_placement_prose.py`
and five hook test files), and `~/.claude/AGENTS.md` names
`autopilot_context_cap_hook.USAGE_CAP` as the canonical location. Moving them is
out of scope for a rework fix.

1. **Line 72 is unchanged.** The hook does NOT import `last_task_wall`:
`trusted_last_wall` calls it inside `_cap_headroom`, so the hook only ever sees
the trusted value. Leave `from _cap_task_record import last_task_cost,
record_task_bounds` exactly as it is.

2. Add one import line, naming all three functions the hook calls:

```python
from _cap_headroom import headroom_exhausted, secs_left_from_env, trusted_last_wall
```

That is 82 characters - one line, within the style limit.

3. **Delete** the current `_headroom_exhausted` definition (lines 199-222
inclusive, 24 lines including its docstring) and replace it with a
`functools.partial` that binds this module's caps. `partial` **preserves every
existing call form** - the four-positional-argument calls at
`test_autopilot_cap_headroom.py:351-356`, the positional-plus-`secs_left=`/
`last_wall=` keyword calls in `test_autopilot_cap_headroom_margin.py`, and the
hook's own call - and no test monkeypatches `USAGE_CAP`, `TURN_TRIPWIRE` or
`HEADROOM_MARGIN` (`test_autopilot_cap_breach.py:41-47` only asserts their
values), so binding them at import time is safe:

```python
# `_cap_headroom.headroom_exhausted` bound to this hook's caps. A partial, not
# a def: the hook file is at its 800-line limit and this costs 6 lines instead
# of 20 while keeping the exact call signature every caller and test uses.
_headroom_exhausted = partial(
    headroom_exhausted,
    usage_cap=USAGE_CAP,
    turn_tripwire=TURN_TRIPWIRE,
    margin=HEADROOM_MARGIN,
)
```

`from functools import partial` goes on the existing stdlib import block (a new
line, counted below).

4. `_handle_below_cap` (currently lines 565-586): replace its last three lines
(584-586)

```python
    last_usage, last_calls = _last_task_cost(state)
    if _headroom_exhausted(total, count, last_usage, last_calls):
        request_handoff(autopilot_dir, task_id, session_id, _phase_of(state))
```

with these six (the one-line `if` would be 102 characters, so it wraps)

```python
    last_usage, last_calls = _last_task_cost(state)
    secs_left = secs_left_from_env(os.environ, int(time.time()))
    if _headroom_exhausted(
        total, count, last_usage, last_calls, secs_left, trusted_last_wall(state)
    ):
        request_handoff(autopilot_dir, task_id, session_id, _phase_of(state))
```

`os.environ` and `time` are already imported (lines 60, 62). `_last_task_cost`
stays exactly as it is - `test_autopilot_cap_headroom.py:145-173` pins it.
`trusted_last_wall` is what keeps a rotated or paused task's span from firing the
term at the first PostToolUse fire of every following session (see
`## Risks & edge cases`).

**Line-count contract (this is a hard acceptance criterion, not advice).** The
acceptance test is an **inequality, not a predicted number**: after the edit,

```
wc -l skills/run-autopilot/scripts/autopilot_context_cap_hook.py
```

must report **800 or fewer** - the same bound `skills/work/scripts/check_style_limits.py`
enforces (`file_limit = 800`, violated at `n > 800`), so exactly 800 is legal and
the implementor is not chasing a target. For orientation only, the expected
change is **-24** (the deleted `_headroom_exhausted` definition, lines 199-222
inclusive) **+9** (the `partial` block above, its three comment lines included)
**+1** (`from functools import partial`) **+1** (the `_cap_headroom` import)
**+3** (the call site: three lines become six) = **-10**, landing near 790. Treat
that as a sanity check on the diff, not as the criterion: if the real count is
different but still <= 800, that is fine. What is NOT fine is going over - and in
that case do not trim a policy comment block to fit and do not raise the cap;
take option 2 from `## Alternatives considered` instead.

### Test contracts

In `skills/run-autopilot/scripts/test_autopilot_cap_headroom_margin.py`, the four
tests named in the 🟠 row above are **replaced**, not supplemented. Each new test
drives `main()`/the hook end to end with `_AUTOPILOT_SESSION_DEADLINE` controlled
explicitly and a state whose last completed task carries `started_at`/`done_at`.

**Every new hook-level test MUST set or delete `_AUTOPILOT_SESSION_DEADLINE`
explicitly; none may rely on it being absent.** `test_autopilot_context_cap_hook.py:20-31`
builds the child env as `dict(os.environ)` plus two overrides and passes it to
`subprocess.run`, and autopilot's own test runs happen inside loop-spawned
sessions, which carry that variable (`cli/runner.py:297` exports it). So "absent"
is NOT the default state under a live loop: a test that omits the variable would
see the parent session's real deadline and flip as that session approaches its own
cap. The existing hook tests are immune only by accident - `_completed()`
(`test_autopilot_cap_headroom.py:42-52`) omits the two stamps, so
`last_task_wall` returns None - and the new tests add those stamps and lose that
immunity. The "no deadline" cases must therefore pop the key
(`os.environ.pop(DEADLINE_ENV, None)` inside a `mock.patch.dict`, or one shared
fixture helper that does it), not simply fail to set it.

**Helper placement**: `_run_with` / `_marker_written` are `HeadroomHandoffTests`
methods (`test_autopilot_cap_headroom.py:78-93`), not importable module helpers,
and `test_autopilot_cap_headroom_margin.py:12` imports only `_load_hook_module`.
Duplicate the ~20 lines of fixture into the margin file (its own stamped
`_completed()` included) rather than promoting the helpers - promoting them would
edit `test_autopilot_cap_headroom.py`, which is deliberately not in the
`## Module placement` table.

The tests:

- `test_time_term_hands_off_when_the_deadline_is_near` - deadline `now + 1000`,
  last completed task spanning 900 s, usage and calls both comfortable:
  `.handoff-requested` IS written. **This test must fail against the pre-fix
  code.** That is the whole point of the row it closes.
- `test_time_term_is_inert_without_a_deadline` - env var absent, same state: no
  marker.
- `test_malformed_deadline_drops_the_time_term` - `_AUTOPILOT_SESSION_DEADLINE`
  set to `abc`, and separately to the empty string: no marker, and the usage and
  call terms still fire when THEY are exhausted (assert both halves).
- `test_time_term_is_inert_without_a_completed_task` - deadline near, but no
  completed task carries both stamps: no marker.
- `test_deadline_already_past_hands_off` - deadline `now - 60`: marker written
  (a session out of time hands off rather than dropping the term).
- `test_a_rotated_task_wall_does_not_fire_the_time_term` - deadline `now + 7200`,
  last completed task spanning **6000 s** (under every credible ceiling) and
  **its own id** present in `state.cap_rotations`, usage and calls comfortable:
  **no marker**. 6000 s is chosen deliberately: 6000 * 1.25 = 7500 > 7200, so the
  term WOULD fire without the filter, and 6000 is inside the band a magnitude
  ceiling would miss. Write the deadline offset as the literal `7200`, not "a
  full cap": at the 10800 review cap this test is vacuous (7500 < 10800 passes
  with or without the filter).
- `test_a_rotation_of_another_task_still_fires_the_time_term` - deadline
  `now + 7200`, last completed task **un-rotated** with a **6540 s** span, and
  `state.cap_rotations` holding an entry for a DIFFERENT `task_id`: **marker
  written**. This is the test that separates the exact filter from
  `if state.get("cap_rotations"): return None`. Without it, that one-liner passes
  every other case here while switching the time term off for the entire
  remainder of any PRD that ever rotated - a green suite over a re-opened 🔴.
- `test_a_paused_task_wall_does_not_fire_the_time_term` - deadline `now + 7200`,
  last completed task spanning **40000 s** with NO `cap_rotations` entry
  (the operator-pause case state does not record): **no marker**. This is the
  ceiling's own pin.
- `test_an_honest_long_wall_still_fires_the_time_term` - last completed task
  spanning **6540 s** (the PRD's measured 109-minute opus task) with no
  `cap_rotations` entry, deadline `now + 7200`: **marker written** (6540 * 1.25 =
  8175 > 7200). Without this the two "no marker" tests above could be satisfied
  by disabling the term entirely.
- `test_a_malformed_cap_rotations_never_matches` - `cap_rotations` set in turn to
  a non-list, `[{}]` (the real degenerate shape, as in
  `cli/test_loop_decision.py:86`), `[{"task_id": None}]`, and an entry that is
  not a dict, against an un-rotated 6540 s span: **marker written** every time,
  and no exception. A malformed record must never be read as a rotation, and must
  never crash a PostToolUse hook.
- `test_deadline_env_name_matches_the_runner` - pin the reader/writer seam so a
  rename cannot silently disable the term again. **Mechanism**: the runner
  hardcodes the string inline (`cli/runner.py:297`) with no exported constant,
  and a test under `scripts/` cannot import `cli.runner` without path surgery -
  so use this repo's prose-pin idiom (as `skills/work/scripts/test_handoff_placement_prose.py`
  does): read `cli/runner.py` as text and assert `_cap_headroom.DEADLINE_ENV`
  appears in it. Do not add a `cli/` test file; none is in the placement table.

Calls-term margin pins, added in the same file:

- `test_calls_margin_fires_below_the_margined_threshold` -
  `_headroom_exhausted(None, 220, 150_000, 200)` is True (450 - 220 = 230, and
  230 < 200 * 1.25 = 250).
- `test_calls_margin_boundary_pins_the_exact_multiplier` -
  `_headroom_exhausted(None, 200, 150_000, 200)` is False (450 - 200 = 250, and
  250 < 250 is False).

The first of those two must fail if `* HEADROOM_MARGIN` is dropped from the calls
term, which is the property the row asks for.

New `skills/run-autopilot/scripts/test_cap_headroom_module.py` covers the new
module directly: `secs_left_from_env` on absent / empty / non-int / valid /
already-past input, and `headroom_exhausted` with explicit caps for each of the
three terms plus each None-drop.

## Data flow

```
cli/runner.spawn
  -> _child_env_with_deadline(env, cap_secs)
       writes _AUTOPILOT_SESSION_DEADLINE = ceil(now + cap_secs)   [already correct]
  -> claude -p child process
       PostToolUse fire
         -> autopilot_context_cap_hook.main
              -> _check_caps -> _handle_below_cap(state, task_id, total, count)
                   -> _last_task_cost(state)            -> (last_usage, last_calls)
                   -> secs_left_from_env(os.environ, now) -> secs_left      [NEW EDGE]
                   -> trusted_last_wall(state)          -> last_wall       [NEW EDGE]
                        -> last_task_wall(state)           the raw span
                        -> state.cap_rotations             drop it if rotated
                        -> MAX_CREDIBLE_WALL_SECS          drop it if paused
                   -> _headroom_exhausted(...)          -> bool
                        -> request_handoff(...)  writes .handoff-requested
```

The two edges marked NEW are the entire 🔴. Every other node already exists and
is tested. `_cap_task_record.record_task_bounds` continues to supply the
`started_at`/`done_at` stamps `last_task_wall` reads; `BOUND_FIELDS` is untouched,
so `last_task_cost` still ignores them.

## Reuse inventory

- **`_cap_task_record.last_task_wall(state)`** (`skills/run-autopilot/scripts/_cap_task_record.py:118-136`)
  - already written, already tested by `test_autopilot_cap_headroom.py:733-778`.
    It stays, unchanged, as the PRD-contracted export. **`trusted_last_wall` does
    NOT call it**, and that is deliberate, not an oversight: `last_task_wall`
    returns a bare `int | None` and never yields the id of the task it measured,
    so calling it would force a SECOND independent "find the last completed task"
    walk, and the rotation test would then be asked about whichever task that
    second walk found. **Cycle-1 task 11 is chartered to widen
    `last_task_wall`'s scan** (scan back past an unstamped or negative entry to
    the most recent valid one), which would desync the two walks outright: the
    span would come from an earlier task while the id came from the latest.
    `trusted_last_wall` therefore does one walk and derives both values from the
    same entry. **Pinned**: `test_trusted_last_wall_agrees_with_last_task_wall`
    asserts the two return the same number for an un-rotated, stamped, credible
    task, so if task 11's widening ever makes them disagree a test goes red
    instead of the filter silently reading the wrong task. Greps:
    `rg -n 'last_task_wall' skills/` - hits only `_cap_task_record.py` and tests,
    which is the finding itself.
- **`_headroom_exhausted`'s `secs_left`/`last_wall` parameters**
  (`autopilot_context_cap_hook.py:199-222`) - the predicate already accepts and
  correctly applies both. No predicate logic is written, only relocated verbatim
  with its caps parameterised.
- **`cli/runner.warn_secs_for` / `idle_secs_for`** (`cli/runner.py:96-120`) - the
  established env-int-with-fallback shape in this codebase: `raw = env.get(NAME)`,
  `if raw is None: return default`, `try: int(raw) except ValueError: return
  default`. `secs_left_from_env` follows that shape exactly rather than inventing
  one. It is NOT imported: importing `cli.runner` into a PostToolUse hook would
  pull `subprocess`, `threading` and the watchdog into every tool call, and its
  semantics differ (a default, not a None-drop). Greps tried:
  `rg -n -e 'def warn_secs_for' -e 'def idle_secs_for' -e 'def _child_env_with_deadline' skills/run-autopilot/cli/runner.py`,
  `rg -n 'deadline|secs_left|time_left|seconds_left' skills/run-autopilot/cli/ skills/run-autopilot/scripts/`.
- **The sibling-module idiom** - `_cap_handoff_marker`, `_cap_state_write`,
  `_cap_task_record`, `_cap_turn_counts`, `_walk_up` (hook lines 66-74). The hook
  already delegates to five pure siblings precisely to stay under 800 lines;
  `_cap_headroom` is the sixth of that kind, not a new pattern.
- **`state.cap_rotations`** (`references/state-schema.md`, written by
  `_append_rotation_to_state`, already read by `autopilot_context_cap_hook.py:345-354`
  via `_last_rotation_task`) - the exact record of which tasks rotated.
  `trusted_last_wall` reads it rather than inferring a rotation from the span's
  magnitude. Nothing new is recorded; the data is already in the `state` dict
  `_handle_below_cap` holds.
- **`_cap_task_record.int_field`** - a "parse or None" helper, but its contract is
  a task-record dict plus a key, not a raw env string. Not reusable here without
  widening its contract; `secs_left_from_env` does its own `int()`.
- **`cli/policy.py:49 TASK_WALL_BUDGET_SECS` and `cli/policy.py:61
  task_over_budget(task)`** - landed by this PRD's own build pass (commit
  `b60e5e0`). They read the same `started_at`/`done_at` stamps and compute
  `done - started` inline, so the repo now holds two wall computations for one
  concept. **Not shared, deliberately**: `cli/policy` lives behind the `cli/`
  package, and this design's own rule forbids a `cli/` import in a PostToolUse
  hook (it would pull the CLI's dependency graph into every tool call). Its
  largest value (2700) was also considered as the `MAX_CREDIBLE_WALL_SECS` source
  and rejected - 2700 would drop the PRD's own measured 109-minute task, which is
  a credible wall the term should act on. The duplication is named here rather
  than hidden; unifying it belongs to whoever moves the caps (option 2).
  The reuse sweep's own greps (`deadline|secs_left|time_left|seconds_left`) could
  not have surfaced it, which is why it is listed explicitly.
- **`cli/routing.py:63 _env_int(env, key, default)`** - the project-wide env-int
  parser, used at `routing.py:323/336/342/347` and `loop_act.py:262-263`. A first
  draft of this section claimed none existed; that was wrong, and wrong for the
  same reason the sweep first missed `cli/policy.py` - the control grep was scoped
  to one file instead of the tree. Not imported here for the same two reasons as
  `warn_secs_for`: it lives behind `cli/`, and its semantics are default-on-failure
  where the time term needs a None-drop. Greps tried (tree-scoped):
  `rg -n 'os.environ|getenv|environ.get' skills/run-autopilot/scripts/autopilot_context_cap_hook.py`
  (one hit, line 737, `_AUTOPILOT_LOOP`, a bare truthiness check - no int parse in
  the hook to extend) and `rg -n 'def _env_int|def .*_secs_for' skills/run-autopilot/`.

## Alternatives considered

1. **Patch the hook in place** (smallest diff: add the import and the parse
   function directly to `autopilot_context_cap_hook.py`). Rejected as
   **unbuildable**: the file is at exactly 800/800, so even the one required
   import line breaks rubric rule R13. The only way to make it fit is to trim a
   policy comment block, and those blocks are load-bearing history referenced
   from `AGENTS.md` and `references/phase-build.md`. Cost of rejecting it: one new
   file.

2. **Move the caps and the predicate wholesale into the new module** and have the
   hook re-export `USAGE_CAP`/`TURN_TRIPWIRE`/`HEADROOM_MARGIN`. Structurally
   tidier: no binding partial, and the hook drops ~50 lines instead of 12.
   **Its real cost is not the 15 files** - the first draft of this section said
   so and that was a straw man, since a re-export satisfies every one of them.
   Audited: only `scripts/tracon/test_model.py:586` reads it through the hook as
   an attribute (`model.USAGE_CAP == autopilot_context_cap_hook.USAGE_CAP`),
   which a re-export keeps resolving; the rest are a mirrored literal
   (`tracon/model.py:19-20`), a docstring mention (`cli/routing.py:20`), prose
   (`references/phase-build.md`, `references/state-schema.md`,
   `scripts/README.md`), a string literal in a prose pin
   (`work/scripts/test_handoff_placement_prose.py:55`), `tracon/panels.py:199`
   reading its own mirror, and hook tests reading `module.USAGE_CAP`. No test
   monkeypatches the constants.
   **The actual cost, re-decided against:** the three policy comment blocks
   (~25 lines of recorded incident history, including the 500K/`[1m]` coupling
   that `~/.claude/AGENTS.md` cites by module name) move to a private
   underscore-prefixed module, so the canonical definition site named in a
   user-global instructions file silently becomes a re-export. Rejected on that
   ground alone: a rework fix for one CRITICAL should not relocate a documented
   canonical constant. What the chosen option costs instead: a 6-line binding
   partial, and the hook left only 12 lines under its cap (see
   `## Risks & edge cases`). If a later change needs real room, this is the move.

3. **Chosen: extract the predicate (parameterised) plus the deadline parse into
   `_cap_headroom.py`, keep a signature-preserving wrapper in the hook.** Buys
   the one thing options 1 and 2 cannot both give: it fits under 800 without
   touching a widely-referenced constant, and it breaks no existing test, because
   the wrapper keeps `module._headroom_exhausted`'s current signature and the
   constants stay where 15 files expect them.

## Risks & edge cases

- **A wrapper that only forwards arguments reads as ceremony.** It is not: it is
  the seam that keeps the caps in the module 15 other files point at while the
  logic lives where it fits. If a later change moves the caps (option 2), the
  wrapper is the single line to delete. Named here so a reviewer does not read it
  as accidental indirection.
- **`secs_left` when the deadline has already passed.** `deadline - now` goes
  negative, and `negative < last_wall * 1.25` is True, so the session hands off
  at the next task boundary. That is correct and deliberate, and it is pinned by
  `test_deadline_already_past_hands_off`. The alternative (treating a past
  deadline as "no deadline") would silence the rule exactly when it matters most.
- **An interactive session has no deadline.** `runner.spawn` only sets the env
  var for loop-spawned children, so `secs_left_from_env` returns None and the
  time term is inert - the documented behaviour, pinned by
  `test_time_term_is_inert_without_a_deadline`.
- **A rotated or paused task's span is dead wall time, not work - and acting on
  it would make every following session do one task and leave.** This is the
  design's most serious edge case and the reason `trusted_last_wall` exists.
  `record_task_bounds` stamps `started_at` once and never replaces it
  (`_cap_task_record.py:102-106`, pinned by
  `test_autopilot_cap_headroom.py:712-731`), so a task cut mid-flight and finished
  in a later session carries a span covering every idle hour between - including
  the 11 h operator pause this project has recorded. `last_task_wall` returns that
  span verbatim. Once it exceeds `cap / HEADROOM_MARGIN` (5760 s at the default
  7200 s cap), the time term is True on the FIRST PostToolUse fire of the next
  session, because `_handle_below_cap` is reached with the in-progress task as the
  boundary task (`autopilot_context_cap_hook.py:693-694`). The marker is written
  at session start, that session does one task and hands off, and the per-session
  orientation cost the PRD exists to REDUCE gets multiplied instead.
  `trusted_last_wall` drops it. **A magnitude ceiling alone cannot do this job**:
  a task that ran 70 min before rotating, waited 5 min for the relaunch and took
  15 min more spans 6000 s, which is under any credible ceiling and still dead
  time - and the trigger threshold is only 5760 s at a 7200 s cap, so the whole
  band (5760, ceiling] would leak. So the primary filter is the exact signal:
  the task's id in `state.cap_rotations`. The ceiling stays only as the backstop
  for spans state does not record (a watchdog kill, an operator pause). Dropping
  rather than clamping is deliberate either way: clamping to the cap still fires
  at session start, since `secs_left ~= cap` there and `cap < cap * 1.25`.
- **A genuinely long task still hands the session off after one task, by
  design.** A real, un-rotated 109-minute task (the PRD's own measured opus task)
  gives `last_wall * 1.25 = 8175 s`, above a 7200 s cap, so the term fires at the
  first fire of the next session. That is correct - only one such task fits - and
  it is the PRD's stated Happy path, not the rotation defect above. The two are
  separated by the rotation signal, not by size, which is what lets a 6540 s
  honest wall be acted on while a 6000 s rotated one is dropped.
- **The term treats the SOFT cap as the deadline, not the watchdog ceiling.**
  `runner._child_env_with_deadline` exports `now + cap_secs` (`cli/runner.py:297`),
  while this PRD's own watchdog now tolerates up to `idle_secs` of silence or
  twice the cap before killing (`cli/watchdog.py`). So the term can fire while the
  session would in fact have survived longer. Deliberate: the point is to leave at
  a boundary rather than to run as close to a kill as possible.
- **The term only ever fires before the wrapper's fixed warning for tasks over
  ~12 minutes.** The wrapper already writes the same `.handoff-requested` marker
  `DEFAULT_WARN_SECS = 900` before the cap (`cli/runner.py:68`, via
  `on_warn=request_wrapper_handoff`; `cli/handoff_request.py` uses the hook's own
  writer). The new term fires first only when `last_wall * 1.25 > 900`, i.e.
  `last_wall > 720 s`. What it buys over the fixed warning is that it scales with
  the task instead of assuming 15 minutes is enough - which the PRD's problem
  statement measured as false (no opus-depth task in the batch finished inside
  15 minutes; task 5 took 109).
- **The time term is inert on a PRD's first task**, where the usage and calls
  terms have explicit `FIRST_TASK_USAGE_ESTIMATE` / `FIRST_TASK_CALLS_ESTIMATE`
  fallbacks (`autopilot_context_cap_hook.py:102-103`). There is no wall analogue,
  so `last_wall is None` drops the term. **Accepted, not fixed**: this is the
  PRD's own contract ("there is no first-task wall estimate, the wrapper's warning
  covers the first task"), and inventing an estimate here would exceed the spec.
  The consequence is real and named: the PRD's problem 3 stays open for a
  session's first task.
- **The margin now applies to the first-task estimates too.** With
  `FIRST_TASK_CALLS_ESTIMATE = 200` and `TURN_TRIPWIRE = 450`, the calls term
  fires at roughly 200 calls into a session's first task. Blake raised this as a
  behaviour change the PRD's Risks section only partly covers. It is pre-existing
  in the build pass, not introduced here, and the new calls-margin tests pin it
  rather than change it. Flagged, not fixed.
- **Likely next changes after this PRD**, and whether this design boxes them in:
  (1) cutting session orientation cost (PRD Risks names it explicitly) - touches
  `usage_at_start`, not the predicate; unaffected. (2) Moving the caps into a
  shared policy module so `cli/` and the hook stop mirroring them - option 2
  above, and this design makes it a one-line-wrapper deletion rather than harder.
  (3) A per-model rather than fixed `USAGE_CAP` - lands on the constants, which
  this design deliberately leaves in place. None is boxed in.
- **The new module must not import from `cli/`.** It runs on every PostToolUse
  fire; pulling `subprocess`/`threading` in would tax every tool call. Stdlib
  only, asserted by the new module's own test importing it in isolation.
- **A residual dead-time band (5760, 10800] stays open for session deaths, and
  that is accepted.** The rotation signal catches cap rotations exactly and the
  ceiling catches spans over 10800, but a task that ran 600 s, was SIGTERMed or
  hit the watchdog ceiling, then waited a 2 h pause and finished, spans ~7800 s
  with NO `cap_rotations` entry - so the term fires at the next session's first
  fire. Nothing in state records a session death, so no exact signal exists.
  The cost is bounded: that one session does one task and hands off, and the next
  honest span self-heals the reading. Named here so the next cycle's blind lens
  reads a known residual rather than an unhandled case.
- **The hook stays close to its cap.** The fix lands it near 790 of 800, so the
  next change to it faces the same squeeze. That is a real and accepted cost of
  rejecting option 2; it is why the design pins the file size in a test, so the
  next PRD hits a red test rather than a surprise. If a later change needs real
  room, option 2 is the move, and this design leaves it one partial-deletion away.
- **`trusted_last_wall` and `MAX_CREDIBLE_WALL_SECS` widen the PRD's literal
  contract**, which says `_handle_below_cap` takes `last_wall` straight from
  `last_task_wall(state)`. The filter sits between them. This is recorded as an
  autonomous decision in `state.autonomous_decisions` naming the constant, its
  value and the reason, so the next cycle's blind (PRD-only) lens reads it as a
  decided deviation rather than unspecified behaviour. The alternative the
  reviewer raised - re-stamping `started_at` on the stale-START branch so the
  wall self-heals like the cost does - was rejected because the PRD explicitly
  contracts the opposite ("`started_at` is written once and never replaced") and
  `test_started_at_survives_a_second_session` pins it; changing that is a spec
  change, not a rework fix.

## Test strategy outline

1. **Fail-first on the 🔴.** `test_time_term_hands_off_when_the_deadline_is_near`,
   rewritten to drive the hook, must be shown red against `e5a8479` before the
   wiring lands. A rewrite that passes against the pre-fix code has reproduced the
   exact defect the 🟠 row describes and is not acceptable.
2. **Unit level**, `test_cap_headroom_module.py`: `secs_left_from_env` over
   absent / empty / `abc` / valid / already-past (passing a plain dict, so no
   process environment is involved); `trusted_last_wall` over no tasks / an
   unstamped last completed task / a stamped un-rotated span / the same span with
   the task's id in `cap_rotations` / a span at `MAX_CREDIBLE_WALL_SECS` exactly /
   one second over / a malformed `cap_rotations` (not a list, entries not dicts -
   must not raise); `headroom_exhausted` with explicit caps for each of the three
   terms and each None-drop.
3. **Hook level**, `test_autopilot_cap_headroom_margin.py`: the nine time-term
   tests above, all driving the hook with the env var controlled explicitly and a
   stamped state.
4. **Regression**, unchanged and all green:
   `uv run --no-project --with pytest python -m pytest -q skills/run-autopilot/scripts/test_autopilot_cap_headroom.py skills/run-autopilot/scripts/test_autopilot_cap_headroom_margin.py skills/run-autopilot/scripts/test_autopilot_context_cap_hook.py skills/run-autopilot/scripts/test_autopilot_cap_breach.py skills/run-autopilot/scripts/test_cap_headroom_module.py`
   and `skills/run-autopilot/cli/test_runner.py` (the deadline export is
   untouched, so `test_spawn_exports_the_session_deadline` must stay green).
5. **Structural**: pin `autopilot_context_cap_hook.py` at **<= 800 lines** - the
   same bound `skills/work/scripts/check_style_limits.py` enforces (`file_limit =
   800`, violated at `n > 800`), so exactly 800 passes. Do NOT assert "strictly
   under": that would invent a stricter rule than the repo's own gate, and the
   file legitimately sits at 800 today. Put this pin in
   `test_autopilot_cap_headroom_margin.py`, not in the new module's unit-test
   file, so a failure reads as a file-size rule rather than a headroom bug.
6. **Purity**: assert `_cap_headroom` imports nothing from `cli` - read the
   module's source and assert it contains no `from cli` / `import cli`. Merely
   importing the module proves nothing. This is a `cli`-freedom check, not a
   stdlib-only proof; say so in the test name
   (`test_cap_headroom_does_not_import_cli`) rather than overclaiming.
7. **Release gate.** Neither `test_autopilot_cap_headroom_margin.py` nor the new
   `test_cap_headroom_module.py` is in `dev/bin/release-checks` (it runs
   `test_autopilot_cap_headroom.py`, `test_autopilot_cap_breach.py`,
   `test_autopilot_cap_rotation.py` and `test_autopilot_cap_review_phase.py`), so
   as written the 🔴's own regression tests would never run at release. Cycle-1
   task 12 adds the margin file by name, but it could not name a file that did not
   exist when it was written: **this task adds
   `skills/run-autopilot/scripts/test_cap_headroom_module.py` to
   `dev/bin/release-checks` itself.** One line; do not leave it to inference.

## Review log

- non-blocker (dispatch 1): Option 2's rejection was a straw man on blast radius; a re-export satisfies all 15 `USAGE_CAP` references. FIXED - `## Alternatives considered` now rejects option 2 on its real cost (relocating an `AGENTS.md`-canonical constant and its policy comment history), with the audit recorded.
- non-blocker (dispatch 1): Reuse inventory missed `cli/policy.py TASK_WALL_BUDGET_SECS` / `task_over_budget`, a second wall computation shipped by this same PRD. FIXED - row added, with why it is not shared and why 2700 is the wrong clamp source.
- non-blocker (dispatch 1): The runner's deadline export was called "already correct" without reconciling it with the watchdog tolerance and the 900s wrapper warning. FIXED - two Risks bullets added.
- non-blocker (dispatch 1): `DEADLINE_ENV` duplicates a literal the writer hardcodes, with nothing pinning reader and writer together. FIXED - `test_deadline_env_name_matches_the_runner` added to the test contract.
- non-blocker (dispatch 1): The new module's skeleton omitted `from __future__ import annotations` and the `Mapping` import, so it would raise NameError, and its return annotation was `float | None` where `deadline - now` on two ints is `int | None`. FIXED (treated as blocking in practice, because Phase 6 copies `## Interfaces & contracts` verbatim into the fix task).
- question (dispatch 1): Where the hook-level test helpers come from - `_run_with` / `_marker_written` are TestCase methods, not importable, and `_completed()` omits the new stamps. ANSWERED in `## Test contracts`: duplicate the fixture into the margin file rather than promoting helpers, which would edit a file outside the placement table.
- question (dispatch 1): The time term is inert on a PRD's first task where the usage and calls terms carry explicit estimates. ANSWERED in `## Risks & edge cases`: accepted, not fixed - it is the PRD's own contract, and the consequence is named. The "fifth instance" slip in the same finding is also corrected to sixth.
dispatch 1 (claude): cardinal-sin 0, blocker 3, non-blocker 5, question 2
dispatch 2: codex unavailable, Claude fallback
- The codex dispatch exited 0 but its captured output ends mid-investigation with no findings block at all (`rg 'severity:' dev/local/tmp/design-codex-output-00218-c1.txt` matches only the echoed prompt template). Output unparseable as findings, which this skill defines as a codex outage. Not re-dispatched on the identical prompt that just failed; degraded to a fresh Claude reviewer per the fallback rule.
- blocker (dispatch 2): The line-count arithmetic was wrong again - the `partial` block is 9 lines (3 comment + 6 code), not 6, and the call site is +2 not +4, and the Risks bullet still said 794. FIXED - the acceptance criterion is now the inequality `<= 800` (matching `check_style_limits.py`) with `wc -l` as the check, and the arithmetic is orientation only.
- blocker (dispatch 2): `usable_wall` was called at the new call site but never added to the import line, so the one new code path would raise NameError. FIXED - the single import line now names all three functions, and the composition moved inside `trusted_last_wall` so the hook's line 72 needs no change at all.
- blocker (dispatch 2): `MAX_CREDIBLE_WALL_SECS = 7200` left the whole (5760, 7200] band open - the exact band the rotated-span defect lives in, since the trigger threshold is `cap / 1.25` = 5760. A magnitude ceiling cannot separate a 6000s rotated span from a 6540s honest one. FIXED - the primary filter is now the exact signal `state.cap_rotations` (already read by the hook at :345-354), the ceiling is demoted to a documented backstop for pause/kill spans, and three tests pin the three cases (6000s rotated -> no marker, 40000s unrotated -> no marker, 6540s unrotated -> marker). The reviewer's alternative (re-stamp `started_at` so the wall self-heals) was REJECTED: the PRD explicitly contracts "`started_at` is written once and never replaced" and `test_started_at_survives_a_second_session` pins it, so that is a spec change, not a rework fix.
- non-blocker (dispatch 2): The ceiling's rationale named `_AUTOPILOT_SESSION_MAX` (7200) while review/rework sessions run at `_AUTOPILOT_SESSION_MAX_REVIEW` (10800) and the headroom rule is live there, so a legitimate 2.5h rework wall would have been discarded. FIXED - the ceiling is 10800, the largest cap the pack ships, and the comment names both caps and the phase-blindness.
- non-blocker (dispatch 2): "Nothing found for a project-wide env-int parser" was false - `cli/routing.py:63 _env_int` exists - and the control grep was scoped to one file. FIXED - the row now names it, says why it is still not imported, and records a tree-scoped control grep.
- non-blocker (dispatch 2): The file-size test was stricter than the repo's own gate (`check_style_limits.py` permits exactly 800) and sat in the new module's unit-test file. FIXED - `<= 800`, moved to the margin test file.
- non-blocker (dispatch 2): `trusted_last_wall` / `MAX_CREDIBLE_WALL_SECS` widen the PRD's literal contract with no recorded decision. FIXED - recorded in `state.autonomous_decisions` and named in Risks, so the blind lens reads a decided deviation rather than unspecified behaviour.
- non-blocker (dispatch 2): Three doc inconsistencies survived dispatch 1, one of them claimed as fixed (the "fifth instance" slip in `## Reuse inventory`, "replace its last two lines" above a three-line block, and the placement table naming only two of the new module's functions). FIXED - all three.
- question (dispatch 2): How the env-name pin reaches the runner's inline literal from `scripts/`. ANSWERED in `## Test contracts`: the repo's prose-pin idiom - read `cli/runner.py` as text and assert `DEADLINE_ENV` appears; no `cli/` test file is added.
- question (dispatch 2): Whether reconciling the unmargined, time-blind gate-edge prose in `references/phase-build.md` is in scope. ANSWERED: out of scope for THIS task and already owned by a separate cycle-1 follow-up (task 12, which carries that finding with its `test_handoff_placement_prose.py` pins).
dispatch 2 (claude-fallback): cardinal-sin 0, blocker 3, non-blocker 5, question 2
dispatch 3: codex unavailable, Claude fallback
- Dispatch 2's codex call had already demonstrated the outage on this same prompt (exit 0, output ends mid-investigation, no findings block). Re-dispatching the identical prompt that just failed, against a doc that had grown, would have burned the verification pass to reproduce a known failure. Degraded to a fresh Claude reviewer per the fallback rule and recorded here rather than silently.
- blocker (dispatch 3): `trusted_last_wall`'s rotation lookup was not bound to the task whose wall it filters - `last_task_wall` returns a bare int and never yields the measured task's id, so a second independent "last completed task" walk was implied, and cycle-1 task 11 is chartered to widen `last_task_wall`'s scan, which would desync the two outright (span from an earlier task, id from the latest). FIXED - `trusted_last_wall` now does ONE reverse walk and derives both the span and the id from the same entry; the docstring says the membership test is against that task's id; `## Reuse inventory` corrects the "it calls last_task_wall" claim, names task 11, and adds `test_trusted_last_wall_agrees_with_last_task_wall` so a future desync goes red instead of silent.
- blocker (dispatch 3): The three prescribed rotation tests all passed under `if state.get("cap_rotations"): return None`, and since `cap_rotations` is per-PRD and cleared only at PRD completion, that one-liner would switch the time term off for the whole remainder of every PRD that ever rotated - a green suite over a re-opened 🔴, the same "test that cannot fail" shape as the 🟠 being folded in. FIXED - added `test_a_rotation_of_another_task_still_fires_the_time_term` (entry for a DIFFERENT task_id, honest span, marker MUST be written) and `test_a_malformed_cap_rotations_never_matches` (non-list, `[{}]`, `task_id: None`, non-dict entry), and the docstring now states that only the measured task's id matters and why.
- blocker (dispatch 3): The new module's prescribed header used `Any` and `last_task_wall` without importing either, and its "Stdlib only" claim was becoming false - the same NameError class dispatch 1 and dispatch 2 each raised once, recurring because the header was not re-checked when `trusted_last_wall` was added. FIXED - `from typing import Any` added; `last_task_wall` is no longer referenced by the module at all (the blocker-1 fix removed the call); the purity wording is "Stdlib only, and no `cli/` import", which is now accurate.
- non-blocker (dispatch 3): The line-count arithmetic was wrong a third time - the replacement call site is six lines, not five (the one-line `if` would be 102 chars), so the change is -10 and lands near 790. FIXED in both places. It no longer blocks because the acceptance criterion is the inequality `<= 800`, which is the right shape and is left alone.
- non-blocker (dispatch 3): A dispatch-2 rename survived at one site - `## Risks & edge cases` still said `usable_wall`. FIXED.
- non-blocker (dispatch 3): The other half of a dispatch-2 "FIXED" item - the placement table's `_cap_headroom.py` row still named only two of the three functions (the fix had landed on the test-file row). FIXED - the row now names all three.
- non-blocker (dispatch 3): The residual dead-time band (5760, 10800] stays open for session deaths (SIGTERM or watchdog kill plus a pause), which state does not record. FIXED as documentation - a Risks line names the band and its bounded cost. No code change; no exact signal exists.
- non-blocker (dispatch 3): Every new pin landed in files `dev/bin/release-checks` does not run, so the 🔴's own regression test would never run at release. FIXED - `dev/bin/release-checks` is now in the placement table and `## Test strategy outline` item 7 makes adding the new test file this task's job rather than task 12's inference.
- non-blocker (dispatch 3): `MAX_CREDIBLE_WALL_SECS` hardcodes a value an operator can raise via `_AUTOPILOT_SESSION_MAX_REVIEW`. FIXED - the comment now says the constant tracks that default and must be raised with it.
- non-blocker (dispatch 3): "deadline a full cap away" was ambiguous, and at the 10800 review cap the rotated-span test is vacuous. FIXED - all three tests specify the literal `now + 7200`, with the arithmetic shown.
- non-blocker (dispatch 3): The claim that cycle-1 task 12 owns the `references/phase-build.md` gate-edge prose row was said not to match the review file. CHECKED, NOT A DEFECT - task 12's own payload (`dev/local/tmp/task-d1-05.json`) carries that finding verbatim as one of its four, alongside the release-checks row and the two node-id rows. The review file's one-line summary of task 12 names only two of its four themes, which is what read as a mismatch. No change; recorded so the next cycle does not re-raise it.
- question (dispatch 3): The two filter functions are given as docstring-only skeletons, so a verbatim copy would return None from both - which for `secs_left_from_env` reproduces the 🔴. ANSWERED - `## Interfaces & contracts` now states before the block that those two bodies are the implementor's, derived from the docstring contracts, and that only `headroom_exhausted`'s term expressions are supplied verbatim.
dispatch 3 (claude-fallback): cardinal-sin 0, blocker 3, non-blocker 7, question 1
result: ok
