"""Task usage and call record for the context-cap hook (PRD 00200).

The hook stamps four ints on each `state.tasks[]` entry: `usage_at_start`
and `calls_at_start` on the first PostToolUse after the task turns
in_progress, `usage_at_done` and `calls_at_done` on the first after it turns
completed. The headroom rule then reads the most recently completed task's
cost from them. Split out of `autopilot_context_cap_hook.py` to keep that
file under the 800-line limit; imported as a sibling module, like `_walk_up`.

Stdlib only. Pure: nothing here touches disk; the hook owns the locked
state write.
"""

from __future__ import annotations

import sys
from typing import Any

START_FIELDS = ("usage_at_start", "calls_at_start")
DONE_FIELDS = ("usage_at_done", "calls_at_done")
BOUND_FIELDS = ("usage_at_start", "usage_at_done", "calls_at_start", "calls_at_done")


def int_field(task: dict[str, Any], key: str) -> int | None:
    value = task.get(key)
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return value


def _warn_non_int(task: dict[str, Any], keys: list[str]) -> None:
    print(
        f"autopilot_context_cap_hook: tasks[{task.get('id')!r}] {', '.join(keys)} "
        "not an int; treating as absent",
        file=sys.stderr,
    )


def record_pair(
    task: dict[str, Any],
    fields: tuple[str, str],
    values: tuple[int, int | None],
    warn: bool,
) -> bool:
    """Write the missing half of one usage/calls pair onto `task`.

    A field already holding an int is never rewritten, with one exception:
    a START value above the current one was stamped by an earlier session
    (a rotated or died task keeps its first stamp; within a session the
    context total and the call count only grow), so it is replaced. A field
    holding a non-int (a string, a bool, null) is treated as absent, named
    on ONE stderr line per task (when `warn`), and overwritten. A None value
    (the session count when stdin carried no session id) writes nothing for
    that field. Returns whether the task changed.
    """
    bad = [key for key in fields if key in task and int_field(task, key) is None]
    if bad and warn:
        _warn_non_int(task, bad)
    changed = False
    for key, value in zip(fields, values):
        if value is None:
            continue
        present = int_field(task, key)
        if present is not None and (fields is not START_FIELDS or present <= value):
            continue
        task[key] = value
        changed = True
    return changed


def record_task_bounds(
    state: dict[str, Any],
    task_id: str,
    total: int,
    count: int | None,
    warn: bool = True,
) -> tuple[bool, str | None]:
    """Stamp the record onto `state.tasks`; return `(changed, done_task)`.

    `done_task` is the id of the task whose done pair was stamped on THIS
    fire and that carries a start pair - the task that just crossed its
    boundary with a measured cost - else None. Mutates `state` in place, so
    the caller can decide on the hook's initial read whether a locked write
    is needed at all, then re-apply the same mutation on the transaction's
    fresh read (with `warn=False`, so a non-int field is named once).
    """
    tasks = state.get("tasks")
    if not isinstance(tasks, list):
        return False, None
    changed = False
    done_task: str | None = None
    for task in tasks:
        if not isinstance(task, dict):
            continue
        status = task.get("status")
        if status == "in_progress" and task.get("id") == task_id:
            changed |= record_pair(task, START_FIELDS, (total, count), warn)
        elif status == "completed" and record_pair(
            task, DONE_FIELDS, (total, count), warn
        ):
            changed = True
            has_start = all(int_field(task, key) is not None for key in START_FIELDS)
            if has_start and isinstance(task.get("id"), str):
                done_task = task["id"]
    return changed, done_task


def last_task_cost(
    state: dict[str, Any], estimates: tuple[int, int]
) -> tuple[int, int]:
    """The (usage, calls) the most recently completed task cost, from its
    recorded bounds, or `estimates` when there is no completed task or its
    record is unusable.

    "Most recent" is the last completed entry in `state.tasks` order (tasks
    complete in plan order and rework tasks are appended). Its record is
    usable only when all four bounds are ints and neither difference is
    negative: a start stamped in an earlier session can exceed this
    session's done value, and a negative cost must never lower the bar. A
    non-int bound is named on one stderr line, like the record's own.
    """
    tasks = state.get("tasks")
    if not isinstance(tasks, list):
        return estimates
    for task in reversed(tasks):
        if not isinstance(task, dict) or task.get("status") != "completed":
            continue
        bad = [
            key for key in BOUND_FIELDS if key in task and int_field(task, key) is None
        ]
        if bad:
            _warn_non_int(task, bad)
        bounds = [int_field(task, key) for key in BOUND_FIELDS]
        if any(value is None for value in bounds):
            break
        usage = bounds[1] - bounds[0]
        calls = bounds[3] - bounds[2]
        if usage < 0 or calls < 0:
            break
        return usage, calls
    return estimates
