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

`- PRDs by lane: solo N, fast-track N, full N; escalated N` renders under
`- PRDs skipped:` (PRD 00204), counted from the batch's `completed_prds`
records by `lane_effective` (the lane that ran); a record carrying
`lane_escalated` counts under its escalated-to lane and under `escalated`.
Records without a `lane_effective` (bare strings, pre-lane dicts) append
`; unclassified N`, only when N > 0.

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
- **Implementor Mix** — `state.tasks[]` attempts (PRD 00019) unioned with
  this PRD's rows from `dev/local/autopilot/ledger/attempts.jsonl` and
  deduplicated on task-and-attempt (the state copy wins), because
  `complete-prd` drains the state attempts into the ledger before this
  renders: attempt counts per implementor, qwen preflight outcomes, the
  exclusion line (`state.tasks` only), the codex probe line (PRD 00077)
  and the capability breaker line (PRD 00065).
  Reading note: the exclusion line is two populations sharing one line —
  plan-time buckets partition the plan-time-ineligible tasks, while the
  dispatch-time `files`, `memory_pressure`, and `memory_probe_failed` reroutes
  are deduplicated by task within each bucket; runtime `files` may also occur
  on an empty write set in an already ineligible plan, so read these as two
  lists, not one partition. The codex
  probe line appends `; hooks: <hook_doctor>` whenever `codex_probe.hook_doctor`
  is present and not `"ok"` — a stale hook copy (`hooks: stale: <basenames>`)
  or the doctor-first sub-probe's own summary line when it found something
  broken; the suffix is omitted when `hook_doctor` is absent or `"ok"`.
- **Run conditions** — one line under `- Tasks:` rendering the PRD's
  `review_converged` row from `loop-metrics.jsonl` (cap, per-cycle roster
  and severity counts, build models, attempt tiers, task counts;
  `state-schema.md` § Convergence rows); `no review_converged row` when the
  batch's metrics file holds none for this PRD, so an emission gap is loud
  rather than blank. `- Tasks:` falls back to the row's counts when the
  closing record is absent or reads `0/0`.
- **Lane** — one line under `- Run conditions:`,
  `- Lane: <lane_effective> (classified <lane>, <lane_reason>)` (PRD 00204),
  read from the state while Phase 0 has not overwritten the fields, else
  from the closing `completed_prds` record; a record carrying
  `lane_escalated` (`{"from": <lane>, "signal": <slug>}`) ends the line with
  `, escalated from <lane>: <signal>`. When neither carries `lane` the line
  reads `- Lane: unclassified`, loud rather than blank.

Absent fields never fail the render: empty arrays omit their section,
`no implementor data` renders only when state and ledger are both empty,
and a `codex_probe` from another batch renders `codex probe: not run`.
