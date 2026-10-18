# Discovery: The drain's QA run leaves no trace until it ends

## Classification
Depth: light | Date: 2026-10-18 | Status: pre-elicitation (written from the drain of batch 202610161547, no questions asked yet)

## Problem
When a batch drains, the driver runs one agoge pass (`claude -p
--permission-mode auto "/run-agoge <repo> --authorized autoclaude-drain"`)
with stdout into `reports/<batch>-agoge.log` under a wall-clock cap. On
2026-10-17 the run spent 17 minutes on recon (the agoge profile was one whole
batch stale), dispatched its lanes at 21:08 and was killed at 21:48 by the
3600 s cap. The log is 0 bytes: plain `-p` prints only the final message, so
an hour of claude time and six subagent dispatches left nothing, and the
operator learned of it from the wrapper log line `agoge: run failed (rc 143)`
twelve hours later. The 2026-10-03 batch's log is 0 bytes too. The runs that
finished took 29 to 45 minutes. PRD 00351 raises the default cap to 7200 s;
it does not change what a killed or hung run leaves behind.

## Requirements (candidate, to be elicited)

### Must have
- F1: the QA run streams: the driver launches it with `--output-format
  stream-json --verbose` and renders events into the log as they arrive (the
  loop already has a renderer for its own sessions), so a killed run leaves
  its recon, its dispatches and its partial findings on disk.
- F2: the driver's final line names what the log holds (`agoge: killed at
  cap after <n> min, log has <k> lines`) and the batch report carries the
  same line, so a drained batch without QA is visible in the report.
- F3: agoge writes its packets incrementally (each lane's result as it
  returns) instead of at the end, so a cap kill keeps the lanes that
  finished.

### Nice to have
- The cap scales with the work: a stale profile (recon needed) adds its
  measured recon time to the cap instead of eating the margin.

### Out of scope
- What agoge checks (its own skill); the cap default (PRD 00351).

## Constraints
- The renderer must not change the log's consumers: the operator reads it,
  and `reports/<batch>-agoge.log` is referenced by the wrapper line.
- F3 is an agoge change (plugin `agoge`), F1 and F2 are autopilot changes.

## Codebase Context
- `skills/run-autopilot/cli/loop_act.py` `_run_agoge_process` and
  `run_agoge` (the Popen with stdout into the log, the `Watchdog` cap).
- `skills/run-autopilot/scripts/render_stream.py` (the loop's stream-json
  renderer for sessions).
- `reports/202610161547-agoge.log` (0 bytes), `202610031511-agoge.log` (0
  bytes), `202610141430-agoge.log` (3 KB, a finished run).

## Approach (candidate)
Reuse the session renderer for the QA process; one flag and one pipe.

## Success Criteria (candidate)
- A QA run killed at the cap leaves a log with the recon and dispatch lines
  and a final `killed at cap` line, and the batch report names it.

## Risks
- Stream rendering doubles the log size; acceptable against an empty file.

## Open Questions
- Should a killed QA run be retried once with a larger cap, or left to the
  operator's `/run-agoge`?
- Does agoge need an incremental packet writer, or is the streamed log
  enough for the walkthrough?

## Discovery Log

### Inferred (not asked)
- Timeline from the agoge session's transcript (e743caa7, 2026-10-17
  20:48-21:48 CEST) and the driver's wrapper log.
