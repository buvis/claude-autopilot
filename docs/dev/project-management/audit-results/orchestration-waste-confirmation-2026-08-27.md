# Autopilot orchestration waste — confirmation against code

Date: 2026-08-27. Source: external feedback on a 12-task build batch.
Verdict: **7 of 7 confirmed**, 6 from code, 1 (the hang) from a mechanism gap
rather than the incident itself.

---

## 1. Style enforcement arrives at phase end, not task end — CONFIRMED

`skills/work/SKILL.md:461-463` (step 7.0) runs `check_style_limits.py` **after
all tasks complete**, against `state.work_start_sha..HEAD` — the whole phase
diff. Twelve tasks of oversize accumulate before anything measures them.

The repair is also boxed in. Step 7.0's fix dispatch re-renders `ivan.md` via
`references/gate-failure.md:136-144`, which re-passes `FILE_PATHS` **exactly as
the step-3 dispatch did** — the task's own Contract paths. `agents/ivan.md:24`:
"Read only the files listed above. If a file or symbol you need is not listed,
stop and report it as a blocker." A file split needs new sibling modules that
are by construction not on that list, so the fixer can only report a blocker or
cram the split into existing files.

## 2. The gate falsely passes on untracked files — CONFIRMED (correctness bug)

Two independent holes, either one sufficient:

- **The file list can't see them.** Step 7.0 enumerates with
  `git diff --name-only --diff-filter=d <base>..HEAD -- '*.py'`. An uncommitted
  new module is not in that output.
- **The gate silently drops them if passed anyway.**
  `check_style_limits.py:159-161`: `_resolve_diff_path` returns `None` for a
  file with no matching `+++ b/` header, and the loop does `continue`. The
  docstring at lines 118-119 calls no-match "an ordinary answer rather than a
  gate that failed to look" — true for an unrelated file, false for a brand-new
  one. It is not counted in `skipped`, so the run exits 0 and step 7.0 records
  `style_gate: clean`.

The `skipped` list and its exit-2 branch were built for exactly this class of
error (lines 147-153) — untracked new files just fall outside it.

## 3. Verification is deliberately duplicated — CONFIRMED (structurally, ×3)

Worse than reported. Three separate full-suite runs per rework cycle:

- `phase-review.md:180` — the tail sweep turns Medium/Low findings into ONE
  `[D{cycle}]` task, dispatched through normal `/autopilot:work`.
- `work/SKILL.md:459` — that work pass then runs its own mandatory step-7 full
  suite ("this step is mandatory and must not be skipped").
- `review-work-completion/SKILL.md:329` — composing the review file's `Tests:`
  line runs the suite again ("run the project's test suite once in the
  FOREGROUND (or reuse the counts from a suite run already performed this
  cycle)"). The reuse clause is the only thing standing between this and a
  third run, and it is prose, not a mechanism.

A doubt-lens **VERIFY** finding (`agents/eve.md:51`, "needs a specific named
check to resolve") has no path to the final-verification record. It enters
Phase 5 classification (`phase-review.md:100-127`) like any other finding and
comes out as a task.

## 4. Reviewer reruns resend the full unchanged diff — CONFIRMED

`work/SKILL.md:421-430`: Pat's `DIFF` placeholder is
`git diff BASE_SHA..HEAD_SHA` with `BASE_SHA` = the parent of the task's test
commit. `references/per-task-review.md:28` closes the loop: "Re-commit (step 5),
re-verify (step 5.5), re-review" — so cycle 2 re-renders the same base against a
later HEAD. The diff only grows; nothing is elided.

The fix already exists for one reviewer. `agent-invocation.md:38-45` gives Bob
(codex) `--resume-thread`, so he "verifies fixes against his own cycle-1
critique instead of re-reviewing from zero". Pat has no equivalent.

## 5. De-slop finds waste it is forbidden to remove — CONFIRMED

`references/self-deslop-prompt.md:80-81`: "**Do not modify tests.** If a test
reads as weak, that is the per-task reviewer's call (step 5.7), not yours."

The template contradicts itself: step 2 (line 62) tells the agent to evaluate
"each line, block, helper, comment, docstring, **or test** added in the diff"
for removal, and the rule then forbids acting on the answer. Whatever it finds
is dropped on the floor and re-found by Pat, then by the PRD-level lenses.

## 6. A verifier command hung 17m48s with no watchdog — CONFIRMED (as a gap)

The incident's session log is gone, so the specific command is unverifiable.
The gap is not: **the Subagent Watchdog covers dispatches, never plain Bash.**
`references/subagent-dispatch.md:60-88` scopes it to Agent dispatches
(15 min check-in / 45 min cap) and helper scripts (`TaskOutput` 10 min × 2).
Line 88 has one Bash carve-out — 20 min `Monitor` on backgrounded **cargo** —
and nothing else. A foreground `ruff`/`pytest`/inspection call has no deadline,
no no-output probe, and no kill path.

The "do not chain with `&&`" rule exists (`final-verification.md:19`,
`work/SKILL.md:366`) but is scoped to the step-7 suite and the commit pair — not
to inspection commands generally.

## 7. Wall-clock observability is inadequate — CONFIRMED

`references/attempt-logging.md:5-31` is the full attempt schema. It carries 24
fields. **Not one is a timestamp.** No queued, no start, no end, no prompt size,
no tool runtime, no timeout reason.

What does exist: `loop-metrics.jsonl` session rows (`wall_secs`, `cost_usd`, one
per session) and per-PRD `review_converged` rows (`phase-review.md:154-172`).
Neither can separate model work from quota waits, handoff latency, or a hung
tool. `subagent-dispatch.md:64` does say "Record the dispatch wall-clock time" —
in-session only, written nowhere.

---

## Overlap with the existing backlog

- **00159** (backlog) already makes Pat tool-less (`-t ""`), diff-only, and
  fed a recorded verification result; it also adds `<task_base_sha>` at step 2.
  It does **not** make reruns delta-aware — every cycle still ships the full
  diff. Finding 4's PRD depends on it and should land after.
- **00159** also reclassifies style/duplication findings as LOW (never retried
  in-task). That trims finding 5's churn at the task level; the findings still
  travel to the PRD review and the tail sweep.
- **00093** (hold) is build-phase clerical overhead — adjacent, no collision.
- **00160**, **00161** — no overlap.
