# Discovery: Batch health signals after a release

## Classification
Depth: light | Date: 2026-10-18 | Status: pre-elicitation (written from monitoring findings, no questions asked yet)

## Problem
After a release, nobody can tell from the ledgers whether the fixes hold. The
operator watched batch 202610161547 (00320-00348, 2026-10-16 15:46 to
2026-10-17 20:48 CEST, 67 sessions, $604) by reading more than twenty session
transcripts, because every defect below has a ledger footprint and no verb
renders it:

| Finding | Where it shows | Count in the batch |
|---|---|---|
| Orchestrator wrote production code outside the micro lane | `attempts.jsonl` stamps `implementor: orchestrator`, `review: skipped:orchestrator-direct`, invented values | 3 of 7 full-lane PRDs (00322 rework, 00324 task 2 and its rework with 67 edits, 00326 tasks 2-3) |
| Bob's codex lane never produced a review | `dispatch-metrics.jsonl` rows of kind `fast-track:bob` with outcome `error` | every fast-track card read (6 of 8) |
| Fast-track item rows with an invented start epoch | `loop-metrics.jsonl` rows with `batch: fast-track` and `ts_start` outside the batch window | 9 of 17 rows (wall up to 29,870,908 min) |
| A lane record the classifier cannot emit | state and report: `lane: fast-track` with `lane_reason: uncardable` (00333) | 1 of 18 |
| The drain's QA pass produced nothing | wrapper log `agoge: run failed (rc 143)`, 0-byte `reports/<batch>-agoge.log` | 1 of 1 (also the 2026-10-03 batch) |
| Review cycles forced by a single-voice HIGH | `*-review-N.md` rows `[1/4]` 🟠 | 6 of 8 HIGHs that reached a cap-out or a stub |

PRDs 00340, 00342, 00345, 00350 and 00351 fix the causes. Whether they hold
on the installed cache is unknown until someone reads the next batch's
transcripts again, which is the cost this discovery wants to remove. It is
also gate 1 of the public-release bar: a batch on the released version whose
ledgers show none of the rows above.

## Requirements (candidate, to be elicited)

### Must have
- F1: a read-only report over the existing ledgers for one batch, listing
  per PRD: attempts whose `implementor` is `orchestrator` outside the micro
  lane (net lines and files over the ceiling), reviewer lanes per kind with
  `ok`, `error` and missing counts, fast-track rows whose `ts_start` falls
  outside the batch window, `lane`/`lane_reason` pairs the classifier does
  not emit, the agoge outcome and log size, cap-outs with the number of
  single-voice HIGHs, deferred and minted-stub counts.
- F2: the drain session appends that report to the batch report and the
  operator can run it by hand on any past batch.

### Nice to have
- A comparison column against the previous batch, so a release shows its
  effect in one table.

### Out of scope
- Fixing any signal (each has its own PRD); blocking a release on the report
  (a later decision, see Open Questions).

## Constraints
- Reads only `docs/dev/project-management/autopilot/ledger/*.jsonl`, the
  batch's review files and `reports/<batch>-state-final.json`; no new ledger
  writer.
- Headless: the drain session runs it unattended.

## Codebase Context
- `skills/run-autopilot/cli/render_report.py` renders the batch report from
  the same sources (per-PRD loop metrics, implementor mix, deferred table).
- `skills/run-autopilot/cli/statectl.py` task stamps (PRD 00342 defines the
  closed grammar the report would count against).
- `skills/fast-track/scripts/record_item.py` writes the fast-track rows (PRD
  00326 bounds `--started`).
- `skills/run-autopilot/cli/loop_act.py` runs agoge and prints the rc line.
- `skills/work/scripts/record_dispatch.py` writes dispatch rows per kind.

## Approach (candidate)
A renderer beside `render_report.py`, fed by the ledgers, run at drain and by
hand. Code decides every row; no model judgment.

## Success Criteria (candidate)
- On the 202610161547 ledgers the report shows the counts in the table above.
- On a fixture batch with clean ledgers every row is zero.

## Risks
- Ledger shapes drift between releases; the report must say which fields it
  could not read instead of printing zero.

## Open Questions
- Which rows, if any, should block `dev/bin/release` the way a critical stub
  does today, and at what threshold?
- Does the report belong in the batch report, its own file under `reports/`,
  or both?
- Should the operator's "first batch after a release" be a named procedure
  with this report as its exit criterion?

## Discovery Log

### Inferred (not asked)
- Source of every count: the monitoring session of batch 202610161547
  (memory notes, review files `00320`-`00348`, `loop-metrics.jsonl`,
  the wrapper log of the driver launched 2026-10-17 09:44 CEST).
