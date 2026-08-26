# Rework Mode (step 1.5)

Moved verbatim out of `SKILL.md` step 1.5 (PRD 00119-v2; situational: read only
when `state.rework_task_ids` is a non-empty array). SKILL.md keeps the two-mode
filter table; the lifecycle, attempt-field and abort semantics live here.
**Read this file before the first task of a rework pass.**

**In rework mode, each task's status is set to `in_progress` at start** via `task-start` (overwriting whatever the prior status was — `pending` after Phase 6's reset, or `completed` on a defensive re-entry) and to `completed` at end — same lifecycle as a default-mode pass, so the dashboard reflects rework progress. `task-start` does not recompute `tasks_completed`, so reopening a previously-`completed` task leaves the count transiently stale until that task's next `task-done` recomputes it — accepted, not a bug to fix.

**In rework mode, the Attempt logging entry** (see `SKILL.md` § Attempt logging) sets `review_cycle` to the current `state.cycle` value (not null), `model` to the escalated tier read from `state.tasks[i].model` (set by `/run-autopilot` Phase 6), and `outcome` to `"completed"` or `"aborted"` as normal. It also **copies `state.tasks[i].escalation_reason` and `state.tasks[i].escalated_from` onto the entry when present** — Phase 6 sets them (`escalation_reason: "review_flag"`, `escalated_from: <prev_tier>`) on the review-flag escalation path, and this copy is how `review_flag` actually reaches `attempts[]` (the PRD metric "every escalation records reason in attempts[]" depends on it). Absent (a non-escalated rework re-dispatch) → omit both.

**`/work` does NOT modify `rework_task_ids` itself.** Clearing is `/run-autopilot` Phase 6's responsibility, after this `/work` invocation returns. **If `/work` aborts mid-rework** (context overrun, Subagent Dispatch Budget overrun, unrecoverable error), `rework_task_ids` survives in state — this is correct recovery behavior: the next `/run-autopilot` session resumes with the same rework batch and re-attempts the listed tasks at their already-escalated tier. Phase 6's clear runs only on the successful `/work` return.

Cross-reference: `run-autopilot/references/state-schema.md` `rework_task_ids` row; `run-autopilot/references/phase-review.md` Phase 6 (rework) tier-escalation rule.
