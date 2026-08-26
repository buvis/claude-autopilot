# Batch Report Format

File: `dev/local/autopilot/reports/{batch_id}-report.md`

Created at first PRD completion, appended after each subsequent PRD. Never
deleted by autopilot (the wrapper archives `state.json` beside it at drain).

**Filename invariant:** `{batch_id}` is always `state.batch.id` at append
time (pinned in core SKILL.md § "Phase 9 invariants"); the CLI builds the
filename from state and never globs `reports/*.md`.

## Rendering (mechanic — lives in the CLI)

`autopilot render report` (cli/render_report.py, PRD 00107) owns the layout;
`cli/golden/expected/report-section.md` pins it. Three forms:

- default — appends the completed-PRD section for `state.prd`, creating the
  file with its header on first write (Phase 9 step 7).
- `--summary` — appends the batch-end `## Batch Summary` block (PRD counts,
  cycle/decision sums, deferred count, duration from the batch's metrics
  rows), plus the Skipped surface below.
- `--stalled --site <site> --detail <detail>` — appends the short STALLED
  form instead of a full section (PRD 00017 loop-mode stall).

## What the batch summary carries about skips

`- PRDs skipped: N` renders directly under `- PRDs completed: N`, **always,
zero included**. That is the point of the line: a drain whose whole backlog
failed its eligibility checks must read as "0 done, N skipped", never as the
silent 0-done batch that has already been mistaken for a dead session once.

When N is non-zero, a `### Skipped` table follows the summary lines — one row
per skip, `PRD | Exit code | Command`, in the order they were recorded. Exit
code `-1` means the check never ran at all (timeout, or an unusable cwd);
`state.batch.skips[]` carries the `note` that says which, and the timestamp.
Skipped PRDs are still in `backlog/` — nothing was parked, and the next drain
re-evaluates each one.

## What a completed-PRD section carries

One `## {prd_filename}` section per PRD: completion stamp, cycles, task
counts, then only the subsections whose sources are non-empty:

- **Assumptions Made** — loop-mode `assumed-ambiguity` records from
  `state.autonomous_decisions` (question → assumption); the batch-end ntfy
  message carries the counts (`{n} done, {m} stalled, {k} deferred`).
- **Autonomous / Escalated Decisions, Deferred to Batch End** — the state
  decision arrays; a `deferred_decisions` entry with status
  `pending`/`deferred` lands in the batch-end table, anything resolved in
  Escalated.
- **Doubt Review Findings** — legacy `state.doubts`.
- **Doubt Rubric Verdicts** — `state.doubts_rubric_verdicts` (final cycle),
  one row per rule; on a dual-reviewer run (PRD 00038) both verdicts share
  the row, source-tagged (`pass (codex) / fail (fable)`).
- **Loop Metrics** — `loop-metrics.jsonl` rows matching this PRD and batch
  (PRD 00013/00018); missing file or no matching rows renders
  `no loop metrics (manual run)`, never a failure.
- **Implementor Mix** — `state.tasks[]` attempts (PRD 00019): attempt counts
  per implementor, qwen preflight outcomes, the exclusion line, the codex
  probe line (PRD 00077) and the capability breaker line (PRD 00065).
  Reading note: the exclusion line is two populations sharing one line —
  plan-time buckets partition the plan-time-ineligible tasks, while the
  dispatch-time memory reroutes (PRD 00075, deduplicated by task) come from
  the eligible population; read it as two lists, not one partition.

Absent fields never fail the render: empty arrays omit their section,
`state.tasks[]` missing/empty renders `no implementor data`, and a
`codex_probe` from another batch renders `codex probe: not run`.
