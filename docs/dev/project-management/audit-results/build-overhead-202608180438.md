# Build-phase overhead baseline: batch 202608180438

Measured 2026-08-26 (PRD 00093-v2) with `skills/work/scripts/check_build_overhead.py`
at commit `0419fcf`, over the author-machine transcripts of the `~/.claude` project
(`~/.claude/projects/-Users-bob--claude/`). Read-only; the filter script is
`dev/local/tmp/00093-batch-sessions.py`.

**Selection rule.** A transcript counts as a build session of this batch when all
three hold:

1. it is a top-level `*.jsonl` of the project directory (so `subagents/` is out) and
   mentions `202608180438`;
2. its first `user` entry is the headless launch (`<command-name>/run-autopilot</command-name>`);
3. its first timestamp falls inside the batch window taken from
   `~/.claude/dev/local/autopilot/loop-metrics.jsonl` (min `ts_start` .. max `ts_end`
   of the batch's rows), and it issues at least one `statectl ... task-start` or
   `task-done` call - the fingerprint of a build session.

129 transcripts mention the batch id; 70 pass all three tests. 32 launch-marked
transcripts carry no task verb (catchup, plan, review, done sessions) and 5 fall
outside the batch window (later sessions that merely read the batch report).

**Sanity check.** `loop-metrics.jsonl` holds 119 rows for this batch, 66 of them with
`phase_launched == "build"`. The 70 selected transcripts sit 4 above that, as expected:
relaunches and resumed sessions produce a transcript without always producing a
matching `phase_launched == "build"` row.

**Confidence.** Per-session counts are exact (they come from the transcript's own
tool_use blocks). The PRD column is a heuristic: each session is attributed to the
batch PRD (per loop-metrics) whose filename it names most often, so a session that
discusses a neighbouring PRD at length could be misfiled. 15 of the batch's 18 PRDs
have at least one build session here; 00110, 00136 and 00140 have none that pass the
filter.

**Reading the numbers.** `statectl/task` is `statectl calls / distinct completed task
ids` for that session alone. `n/a` means the session issued task verbs but completed
no task in its own window (a session that started a task and handed off, or a cap-out).
Those sessions still contribute their statectl calls to the totals row, which is why
the total ratio (9.47) is higher than most per-session ratios.

| Session | PRD | Tasks completed | statectl calls | statectl/task | Prompt Writes | Agent dispatches |
|---|---|---:|---:|---:|---:|---:|
| 1de2e7f4 | 00029-cartographer-evaluate-phase-4-6-reactivation-v1 | 1 | 8 | 8.00 | 0 | 0 |
| 6130e78c | 00029-cartographer-evaluate-phase-4-6-reactivation-v1 | 0 | 24 | n/a | 0 | 2 |
| a206512b | 00029-cartographer-evaluate-phase-4-6-reactivation-v1 | 1 | 22 | 22.00 | 0 | 2 |
| a8c3c978 | 00029-cartographer-evaluate-phase-4-6-reactivation-v1 | 1 | 11 | 11.00 | 1 | 0 |
| be0169e2 | 00029-cartographer-evaluate-phase-4-6-reactivation-v1 | 3 | 24 | 8.00 | 0 | 7 |
| cc92b9e3 | 00029-cartographer-evaluate-phase-4-6-reactivation-v1 | 2 | 13 | 6.50 | 0 | 6 |
| ef479756 | 00029-cartographer-evaluate-phase-4-6-reactivation-v1 | 0 | 18 | n/a | 0 | 0 |
| 16ad7841 | 00121-close-agoge-gate-review-highs-v1 | 0 | 4 | n/a | 0 | 0 |
| 369910b4 | 00121-close-agoge-gate-review-highs-v1 | 1 | 4 | 4.00 | 0 | 2 |
| 6f6970f9 | 00121-close-agoge-gate-review-highs-v1 | 0 | 3 | n/a | 1 | 1 |
| b727b712 | 00121-close-agoge-gate-review-highs-v1 | 1 | 7 | 7.00 | 1 | 1 |
| febafb47 | 00121-close-agoge-gate-review-highs-v1 | 4 | 13 | 3.25 | 0 | 0 |
| 38afdc2d | 00122-make-batch-reports-tell-the-truth-v1 | 0 | 1 | n/a | 0 | 2 |
| 6578534a | 00122-make-batch-reports-tell-the-truth-v1 | 1 | 16 | 16.00 | 1 | 1 |
| d5695e4b | 00122-make-batch-reports-tell-the-truth-v1 | 3 | 24 | 8.00 | 1 | 16 |
| 4ca04cec | 00123-sweep-task-tool-retirement-leftovers-v1 | 1 | 2 | 2.00 | 0 | 2 |
| fc8ebfe7 | 00123-sweep-task-tool-retirement-leftovers-v1 | 1 | 13 | 13.00 | 0 | 5 |
| 11c5aa77 | 00124-key-svelte-each-blocks-by-index-v1 | 2 | 6 | 3.00 | 4 | 3 |
| 4b02f46a | 00124-key-svelte-each-blocks-by-index-v1 | 0 | 14 | n/a | 0 | 1 |
| 631597f2 | 00124-key-svelte-each-blocks-by-index-v1 | 2 | 16 | 8.00 | 0 | 10 |
| 7c6f31bd | 00124-key-svelte-each-blocks-by-index-v1 | 1 | 13 | 13.00 | 0 | 5 |
| 0114b085 | 00125-debrief-build-states-non-facts-v1 | 1 | 2 | 2.00 | 0 | 0 |
| 043f1c54 | 00125-debrief-build-states-non-facts-v1 | 0 | 1 | n/a | 0 | 0 |
| 3d7061e6 | 00125-debrief-build-states-non-facts-v1 | 0 | 1 | n/a | 0 | 1 |
| 4b4aab25 | 00125-debrief-build-states-non-facts-v1 | 2 | 16 | 8.00 | 2 | 7 |
| 5644edf7 | 00125-debrief-build-states-non-facts-v1 | 0 | 15 | n/a | 0 | 3 |
| 635f655b | 00125-debrief-build-states-non-facts-v1 | 1 | 3 | 3.00 | 1 | 3 |
| 6e9e98de | 00125-debrief-build-states-non-facts-v1 | 1 | 2 | 2.00 | 0 | 2 |
| e5ffad98 | 00125-debrief-build-states-non-facts-v1 | 1 | 18 | 18.00 | 2 | 8 |
| 108b7e17 | 00126-portfolio-brief-hides-its-failures-v1 | 5 | 22 | 4.40 | 0 | 18 |
| 4f54930c | 00126-portfolio-brief-hides-its-failures-v1 | 1 | 12 | 12.00 | 0 | 6 |
| 58101b8a | 00126-portfolio-brief-hides-its-failures-v1 | 4 | 9 | 2.25 | 0 | 4 |
| 5eba7b93 | 00126-portfolio-brief-hides-its-failures-v1 | 3 | 24 | 8.00 | 0 | 6 |
| fef35e9b | 00126-portfolio-brief-hides-its-failures-v1 | 0 | 4 | n/a | 0 | 1 |
| 4e1b7bb6 | 00127-loop-registry-lies-about-liveness-v1 | 1 | 17 | 17.00 | 0 | 8 |
| 98ff3e32 | 00127-loop-registry-lies-about-liveness-v1 | 1 | 15 | 15.00 | 0 | 6 |
| a39aba84 | 00127-loop-registry-lies-about-liveness-v1 | 1 | 8 | 8.00 | 2 | 1 |
| dd488f78 | 00127-loop-registry-lies-about-liveness-v1 | 1 | 18 | 18.00 | 2 | 4 |
| 1f6c33bf | 00128-discarded-reviews-and-lost-alerts-v1 | 2 | 14 | 7.00 | 0 | 7 |
| a668b800 | 00128-discarded-reviews-and-lost-alerts-v1 | 0 | 10 | n/a | 0 | 2 |
| cbdbb873 | 00128-discarded-reviews-and-lost-alerts-v1 | 1 | 11 | 11.00 | 0 | 3 |
| f0b101b8 | 00128-discarded-reviews-and-lost-alerts-v1 | 2 | 4 | 2.00 | 0 | 3 |
| 102b06bb | 00129-autoclaude-suite-stubs-do-not-intercept-v1 | 0 | 20 | n/a | 2 | 6 |
| 25fcdcd8 | 00129-autoclaude-suite-stubs-do-not-intercept-v1 | 1 | 11 | 11.00 | 0 | 5 |
| 29a1403c | 00129-autoclaude-suite-stubs-do-not-intercept-v1 | 1 | 14 | 14.00 | 1 | 6 |
| bcd93b9c | 00129-autoclaude-suite-stubs-do-not-intercept-v1 | 1 | 11 | 11.00 | 0 | 0 |
| 0120e1f1 | 00130-hook-gates-fail-open-silently-v1 | 0 | 20 | n/a | 0 | 2 |
| 18fa0005 | 00130-hook-gates-fail-open-silently-v1 | 1 | 13 | 13.00 | 0 | 10 |
| b20480a1 | 00130-hook-gates-fail-open-silently-v1 | 2 | 7 | 3.50 | 1 | 3 |
| 714dbe00 | 00131-metrics-files-corrupt-and-mislead-v1 | 2 | 17 | 8.50 | 0 | 6 |
| 8fee85c4 | 00131-metrics-files-corrupt-and-mislead-v1 | 0 | 3 | n/a | 0 | 2 |
| 99c147bf | 00131-metrics-files-corrupt-and-mislead-v1 | 1 | 3 | 3.00 | 1 | 0 |
| f9ab79bc | 00131-metrics-files-corrupt-and-mislead-v1 | 1 | 17 | 17.00 | 0 | 5 |
| 3d322f0c | 00132-autopilot-writers-and-clis-tell-truth-v1 | 2 | 11 | 5.50 | 0 | 3 |
| 52748e68 | 00132-autopilot-writers-and-clis-tell-truth-v1 | 1 | 14 | 14.00 | 1 | 7 |
| 675431a3 | 00132-autopilot-writers-and-clis-tell-truth-v1 | 0 | 1 | n/a | 0 | 1 |
| 72974022 | 00132-autopilot-writers-and-clis-tell-truth-v1 | 0 | 4 | n/a | 1 | 4 |
| 7f12a6e8 | 00132-autopilot-writers-and-clis-tell-truth-v1 | 2 | 5 | 2.50 | 0 | 3 |
| aca2320c | 00132-autopilot-writers-and-clis-tell-truth-v1 | 0 | 2 | n/a | 1 | 1 |
| be8f2d12 | 00132-autopilot-writers-and-clis-tell-truth-v1 | 1 | 5 | 5.00 | 0 | 2 |
| c7f7ed21 | 00132-autopilot-writers-and-clis-tell-truth-v1 | 1 | 5 | 5.00 | 1 | 1 |
| d6e62443 | 00132-autopilot-writers-and-clis-tell-truth-v1 | 1 | 23 | 23.00 | 0 | 2 |
| 63b02230 | 00133-cut-hook-and-suite-overhead-v1 | 1 | 2 | 2.00 | 0 | 1 |
| 86783201 | 00133-cut-hook-and-suite-overhead-v1 | 0 | 4 | n/a | 1 | 1 |
| 8d91a2b3 | 00133-cut-hook-and-suite-overhead-v1 | 1 | 11 | 11.00 | 0 | 8 |
| 9377b1d4 | 00133-cut-hook-and-suite-overhead-v1 | 0 | 14 | n/a | 1 | 1 |
| dacba250 | 00133-cut-hook-and-suite-overhead-v1 | 3 | 18 | 6.00 | 0 | 13 |
| fd5d5788 | 00133-cut-hook-and-suite-overhead-v1 | 3 | 7 | 2.33 | 0 | 5 |
| 0e7917e6 | 00134-digest-github-repo-without-browser-v1 | 1 | 19 | 19.00 | 2 | 2 |
| c0755c31 | 00134-digest-github-repo-without-browser-v1 | 1 | 4 | 4.00 | 1 | 1 |
| **total (70 sessions)** | **15 PRDs** | **81** | **767** | **9.47** | **32** | **260** |

## What the baseline says

- **9.47 statectl calls per completed task** across the batch. No target is set here;
  this is the number the next tuning decision reads.
- **3.2 Agent dispatches per completed task** (260 / 81) - the build phase spends more
  calls on subagent dispatch than on state bookkeeping per task in many sessions.
- **32 prompt-authoring Writes** for 81 tasks (0.40 per task): rendered dispatch
  (`render_prompt.py`) already keeps hand-written prompt files rare.
- 19 of the 70 build sessions completed no task of their own. That is the batch's
  handoff cost, not idle work: a session that starts a task and hands off at the
  context cap still pays its statectl calls.
- The v1 PRD's headline figures (TaskList hydration turns, "7.5 statectl calls per
  task") were substring counts over a single transcript and are superseded by this
  table.
