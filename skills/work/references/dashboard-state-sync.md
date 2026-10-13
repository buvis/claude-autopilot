# Dashboard State Sync

The dashboard (tracon; `render_stream.py` fallback) reads `docs/dev/project-management/autopilot/state.json` directly, so `state.tasks[].status` must stay accurate — set at task start (step 2) and task end (step 6) — with `tasks_completed` matching it. The pidash sync hooks are retired (PRD 00063); nothing else maintains these.

Apply every such change with `statectl`, never the editing tools — the sole-writer rule in `run-autopilot` SKILL.md § State Management, which also documents the one human fallback. **Use the compound task verbs for the lifecycle transitions**, not a sequence of field writes:

| Transition | Call |
|---|---|
| task start | `statectl.py <state.json> task-start <task-id>` |
| task end | `statectl.py <state.json> task-done <task-id> <attempt-json-file>` |

`task-done` lands status, the appended attempt record, and a **recomputed** `tasks_completed` in one locked atomic write. Both verbs resolve the task by `tasks[].id`, not array position.

**Do not set `tasks_completed` alongside a task-lifecycle transition** — `task-done` derives it, and setting it too is what let the count and the statuses drift apart. This bans the per-task write only: the Phase 3 bulk snapshot (`run-autopilot/references/phase-build.md`) still writes `tasks_total`/`tasks_completed` in the same write that establishes the whole `tasks` array, which is the one legitimate hand-set and has no compound verb.

The generic `set|append|del <json-path>` forms remain for everything that is not a task-lifecycle transition.
