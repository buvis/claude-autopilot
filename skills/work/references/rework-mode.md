# Rework Mode (step 1.5)

Moved verbatim out of `SKILL.md` step 1.5 (PRD 00119-v2; situational: read only
when `state.rework_task_ids` is a non-empty array). SKILL.md keeps the two-mode
filter table; the lifecycle, attempt-field and abort semantics live here.
**Read this file before the first task of a rework pass.**

**In rework mode, each task's status is set to `in_progress` at start** via `task-start` (overwriting whatever the prior status was — `pending` after Phase 6's reset, or `completed` on a defensive re-entry) and to `completed` at end — same lifecycle as a default-mode pass, so the dashboard reflects rework progress. `task-start` does not recompute `tasks_completed`, so reopening a previously-`completed` task leaves the count transiently stale until that task's next `task-done` recomputes it — accepted, not a bug to fix.

**In rework mode, the Attempt logging entry** (see `SKILL.md` § Attempt logging) sets `review_cycle` to the current `state.cycle` value (not null), `model` to the escalated tier read from `state.tasks[i].model` (set by `/run-autopilot` Phase 6), and `outcome` to `"completed"` or `"aborted"` as normal. It also **copies `state.tasks[i].escalation_reason` and `state.tasks[i].escalated_from` onto the entry when present** — Phase 6 sets them (`escalation_reason: "review_flag"`, `escalated_from: <prev_tier>`) on the review-flag escalation path, and this copy is how `review_flag` actually reaches `attempts[]` (the PRD metric "every escalation records reason in attempts[]" depends on it). Absent (a non-escalated rework re-dispatch) → omit both.

**`/work` does NOT modify `rework_task_ids` itself.** Clearing is `/run-autopilot` Phase 6's responsibility, after this `/work` invocation returns. **If `/work` aborts mid-rework** (context overrun, Subagent Dispatch Budget overrun, unrecoverable error), `rework_task_ids` survives in state — this is correct recovery behavior: the next `/run-autopilot` session resumes with the same rework batch and re-attempts the listed tasks at their already-escalated tier. Phase 6's clear runs only on the successful `/work` return.

Cross-reference: `run-autopilot/references/state-schema.md` `rework_task_ids` row; `run-autopilot/references/phase-review.md` Phase 6 (rework) tier-escalation rule.

## Micro lane (PRD 00148)

Below a certain size the per-task ceremony costs more than the edit: a two-finding prose trim measured ~15 min and ~100K subagent tokens for a -25 net-line change. This lane spends none of that. It is a rework-only shortcut — a default-mode task has no findings block to size and no tests yet.

**Eligibility.** Read the task's `### Findings (verbatim)` block, collect one severity and one file path per line, and call `micro_lane_eligible(severities, files, in_rework=True)` from `scripts/work_routing.py`: at most two findings, at most two distinct files (the `:line` suffix is stripped), none CRITICAL, block parsed at all. Then run `git status --porcelain` and require every named file to be clean at claim time — the lane's escape hatch is `git checkout --`, which would destroy a live edit of the user's. Either check failing means the normal lane, unchanged.

**What it skips.** Steps 2.7, 2.8, 2.85, 2.9 and 2.95: no Tess, no Devon, no test commit, no red check. The orchestrator makes the change itself with the **Edit tool only** — no subagent, no `sed`, no shell rewrite.

**The overrun ceiling.** The 2/2 bound is a guess about the diff, made before the diff exists. This is the measurement that settles it. Before staging, over the working tree:

```bash
git diff --shortstat HEAD -- <files>
```

Compute `net_lines = insertions - deletions` and `file_count` (the step-5.6 formula). `net_lines >= 30` OR `file_count > 2` is an **overrun**: the task was not micro after all. Run `git checkout -- <files>`, stamp `micro_lane: "overrun"` on the attempt, and continue at step 2.7 as a normal task — the full pipeline then runs from a clean tree, having lost only the edit.

**Below the ceiling.** Step 5 stages and commits the edited files as usual, tripwire included. Step 5.5 runs the task's `Verify:` command, or the project's narrowest test command covering the touched modules when the task carries none. Step 5.6 records `self_deslop: "skipped:trivial"` without dispatching. Step 5.7 runs Pat unchanged, with `BASE_SHA` = the parent of the lane commit; its retry rows also edit through the orchestrator rather than re-rendering Ivan.

**The attempt record** carries `implementor: "orchestrator"`, `red_check: "n/a:micro-lane"`, and `review_cycle` as rework mode already sets it above. Two subagent dispatches are skipped and one reviewer is not — a lane that skipped Pat as well would be a lane with no check at all.
