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
    raw = env.get(DEADLINE_ENV)
    if raw is None:
        return None
    try:
        deadline = int(raw)
    except ValueError:
        return None
    return deadline - now


# Why the rotation signal is the primary filter and a magnitude test alone is
# wrong: a task that ran 70 min before rotating, waited 5 min for the relaunch
# and took 15 min more spans 6000s, which is under any credible ceiling yet is
# still dead time. Acting on it hands off at the FIRST fire of the next
# session, so that session does one task and leaves - multiplying the
# orientation cost this PRD exists to cut.
# And why only the MEASURED task's rotation counts: `cap_rotations` is per-PRD
# and is cleared at PRD completion, so "any rotation in this PRD" would switch
# the time term off for the whole remainder of every PRD that ever rotated -
# precisely the long PRDs the term exists for.
def trusted_last_wall(state: dict[str, Any]) -> int | None:
    """The last completed task's wall in seconds, or None when none can be
    trusted as one session's own work (which drops the time term).

    An unusable span - missing or non-int stamps, a boolean stamp, or a
    negative difference - is skipped, not a stop signal: the scan keeps
    walking back for an earlier completed task's span, the same rule
    `last_task_wall` already follows (PRD 00243). Two reasons DO stop the
    scan outright, never falling through to an earlier task's span. (1) The
    task ROTATED: `record_task_bounds` stamps `started_at` once and never
    replaces it (a PRD contract), so a task cut mid-flight and finished later
    carries every idle second between. Its id appears in
    `state["cap_rotations"]` as a `task_id`, so this is answerable exactly
    rather than by guessing from the magnitude. (2) The span exceeds
    `MAX_CREDIBLE_WALL_SECS` - the backstop for what state does not record (a
    watchdog kill, an operator pause).
    """
    tasks = state.get("tasks")
    if not isinstance(tasks, list):
        return None
    for task in reversed(tasks):
        if not isinstance(task, dict) or task.get("status") != "completed":
            continue
        started = task.get("started_at")
        done = task.get("done_at")
        if (
            isinstance(started, bool)
            or isinstance(done, bool)
            or not isinstance(started, int)
            or not isinstance(done, int)
        ):
            continue
        span = done - started
        if span < 0:
            continue
        if span > MAX_CREDIBLE_WALL_SECS:
            return None
        rotations = state.get("cap_rotations")
        if not isinstance(rotations, list):
            rotations = []
        task_id = task.get("id")
        if task_id is not None and any(
            isinstance(entry, dict) and entry.get("task_id") == task_id
            for entry in rotations
        ):
            return None
        return span
    return None


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
    if total is not None and usage_cap - total < last_usage * margin:
        return True
    if count is not None and turn_tripwire - count < last_calls * margin:
        return True
    return (
        secs_left is not None
        and last_wall is not None
        and secs_left < last_wall * margin
    )
