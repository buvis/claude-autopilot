# Batch waste log - 2026-09-06

Two loops watched from one session: claude-autopilot (driver 55029, batch
started 00:01, PRDs 00178/00179/00180, plugin 0.5.1) and agent-skills (driver
54220, batch 202609050909 resumed 23:59, PRD 00016 with 34 queued). Entries are
observations with the evidence line; "worth optimizing" items carry a proposal.

## Observations

- **Phase 0 cold start: 4.5 min before `state.json` existed** (claude-autopilot,
  session start 00:01:15, state written 00:05:49). Fresh batch: plugin-pin
  reads, PRD selection, frontmatter parse, catchup skip. Measure the same gap
  on the second and third PRD (batch cache warm) before judging.
- **Hook-blocked `cat` on the first tool call** (00:01:22, `prefer_tools.py`
  blocked bash `cat` of `state.json`; the session then used Read). Every block
  is one wasted model turn. The per-session `hook_blocks` counter in the watch
  reports how often this recurs; the last-session.log of the agent-skills batch
  is the larger sample.
- **Hand-built PRDs versus the loop** (same day, same repo): 00175 by Codex
  14:35-21:03 (6.5 h, four cleared-context review cycles, live Gemini probes);
  00176 by Codex 21:40-23:56 (2.3 h, four review cycles for a two-guard fix,
  three commits plus one fix-up). Compare with 00178-00180 wall-clock and cost
  from loop-metrics when they land; the hand path spent most of its time in
  reviews, the same shape 00177's discovery measured (~20 min per cycle).
- **Release ran on the wrong branch** (22:23): the shared checkout had been
  switched to `fix/00176-doctor-target-io` by the Codex session; undoing cost
  ~20 min (tag delete, marketplace revert, revert on the branch, re-release
  from a worktree). Worth optimizing: `release-plugin` should refuse unless
  `git branch --show-current` is the default branch, and the shim could offer
  `--worktree` to release from a throwaway checkout of master.
- **Two loops on one machine share one usage budget.** Both drivers launch
  `claude-sonnet-5[1m] --effort xhigh` sessions; 00177's discovery recorded a
  usage-limit idle of 11:43-13:34 on a single batch. Watch loop-metrics
  `signal` and wall_secs for sleep-until-reset rows on either side.
- **Stale batch state needed a hand archive** (`202609011951` state.json plus a
  `paused-by-operator` marker from 09:11 sat until 21:39). By design (resume
  keeps state), but a paused batch whose PRDs were then finished by hand had
  nothing left to resume; tracon showed it as paused all day.

- **Stale `.handoff-requested` marker in agent-skills** (1 byte, dated
  2026-09-05 16:05, still present at 00:10 while 00016 runs at task 1/4). If
  the step-6.5 task-boundary check honours it, the next boundary hands off a
  session that had plenty of context left: one extra relaunch (~1-2 min of
  Phase 0 plus a cold context). Verify: a loop-metrics row for 00016 with
  `phase_launched: build`, short wall_secs, right after the task-2 commit.
  Worth optimizing if confirmed: the loop should clear the marker at session
  launch, or stamp it with the session id it belongs to.
- **00178 planning wrote tasks one at a time** (`tasks_total` went 1 → 2 → 3
  → 4 between 00:10:28 and 00:12:13, one `task-add` per ~35 s). Four tasks
  match the PRD, so no collapse; the 105 s of serial statectl round-trips is
  ceremony, small but per PRD.

## Per-session rows (appended as they land)

| repo | prd | phase launched → end | wall s | cost $ | tool calls | bash calls | hook blocks |
|------|-----|----------------------|--------|--------|------------|------------|-------------|
| claude-autopilot | 00178 | (bootstrap) → build | 1007 | 3.52 | 23* | 16* | 0* |
| claude-autopilot | 00178 | build → build (stood down, signal paused) | 133 | 0.50 | 13 turns | - | - |
| agent-skills | 00016 | build → review | 3203 | 13.21 | 205 | 125 | 0 |
| agent-skills | 00016 | review c1 → review c2 | 2427 | 19.81 | 256 | 152 | 12 |
| agent-skills | 00016 | (row with null metrics; session produced no cost record) | ? | 0 | 149 | 90 | 18 |
| agent-skills | 00016 | review → done | 1154 | 10.27 | 7 | 6 | 0 |
| agent-skills | 00016 | done → build (next PRD) | 244 | 1.07 | 33 | 29 | 8 |
| agent-skills | 00017 | build → build (handoff 1) | 3884 | 37.23 | 326 | 192 | 14 |
| agent-skills | 00017 | build → build (handoff 2) | 5381 | 47.91 | 385 | 215 | 6 |
| agent-skills | 00017 | build → build (handoff 3) | 4843 | 37.32 | 422 | 240 | 4 |
| agent-skills | 00017 | build → review | 619 | 5.12 | 69 | 49 | 6 |
| agent-skills | 00017 | review c1 → review c2 | 5644 | 47.77 | 473 | 283 | 24 |
| claude-autopilot | 00178 | build → build (task 1, cut by the usage limit) | 2069 | 9.45 | 184 | 114 | 8 |
| claude-autopilot | 00178 | build → build (dead relaunch at the limit) | 11 | 0 | 0 | 0 | 0 |
| agent-skills | 00017 | review c2 (a reviewer subagent killed by the limit) | 4041 | 9.21 | 163 | 116 | 16 |
| agent-skills | 00017 | review c2 (dead relaunch at the limit) | 7 | 0 | 0 | 0 | 0 |
| claude-autopilot | 00178 | build → build (task 2, after the reset) | 509 | 1.80 | 57 | 46 | 6 |
| agent-skills | 00017 | (null placeholder row before the done hop; counters belong to the review session) | - | 0 | 168 | 113 | 20 |
| claude-autopilot | 00178 | build → build (task 3) | 2361 | 5.23 | 107 | 75 | 6 |
| agent-skills | 00017 | review c2 → done (rework 7/7, converged) | 4346 | 41.51 | 232 | 120 | 0 |
| claude-autopilot | 00178 | build → review (task 4, at opus) | 1432 | 17.85 | 202 | 143 | 4 |

00178 build phase total: 5 sessions, ~1h50m of session time, $34.33, four
tasks (three at sonnet $1.80-9.45, the last promoted to opus at $17.85).

| claude-autopilot | 00178 | review c1 → review c2 (rework 3 tasks, cut by the lid close at 11:40) | 6264 | 13.32 | 181 | 121 | 20 |
| claude-autopilot | 00178 | review (died: machine asleep, 7802 s wall-clock counted) | 7802 | 0 | - | - | - |
| claude-autopilot | 00178 | review c2 (after the 19:42 restart; one more rework task) | 808 | 11.75 | ? | ? | ? |
| claude-autopilot | 00178 | (third null-metrics row) | ? | 0 | ? | ? | ? |
| claude-autopilot | 00178 | review c2 → done | 2386 | 27.38 | 131 | 92 | 8 |

| claude-autopilot | 00178→00179 | done → build (reset + select) | 202 | 1.67 | 51 | 42 | 6 |
| claude-autopilot | 00179 | build → review (plan + both tasks in one session, no handoff) | 1239 | 9.64 | 204 | 136 | 6 |
| agent-skills | 00020 | review c1 → review c2 (one rework task) | 2594 | 26.09 | 166 | 104 | 6 |
| agent-skills | 00020 | review c2 → done (one more rework task, then converged) | 1374 | 19.27 | 89 | 55 | 0 |

**00020 closed at 21:12**: 6 rows, 5.4 h session wall-clock (2.2 h of it the
dead sleeping session), $62.27, two review cycles, two rework tasks, for a
three-task PRD. The null row sat between `review→review` and `review→done`
in the ledger but was written at 21:00, before cycle 2's rework ran, so it is
a placeholder opened at the launch of the session that later records the done
hop, not a converge marker.

| claude-autopilot | 00179 | review c1 → done (one rework task inside the cycle, converged) | 1484 | 20.42 | 101 | 57 | 0 |

| claude-autopilot | 00179→00180 | done → build | 125 | 0.97 | 30 | 24 | 6 |
| claude-autopilot | 00180 | build → review (one task, one handoff request, sonnet) | 1620 | 9.43 | 195 | 133 | 14 |
| agent-skills | 00020→00021 | done → build | 105 | 0.93 | 28 | 23 | 0 |
| agent-skills | 00021 | build → build (plan + task 1, handoff) | 845 | 6.20 | 135 | 87 | 6 |
| agent-skills | 00021 | build → review (tasks 2-4) | 954 | 6.80 | 161 | 115 | 8 |
| agent-skills | 00021 | review c1 → done (one rework task, converged) | 1245 | 20.05 | 58 | 39 | 0 |

| agent-skills | 00021→00022 | done → build | 146 | 1.27 | 37 | 31 | 4 |
| agent-skills | 00022 | build → review (plan + four tasks in one session) | 1226 | 10.34 | 246 | 158 | 8 |
| agent-skills | 00022 | review c1 → done (no rework) | 943 | 12.28 | 127* | 79* | 8* |

| claude-autopilot | 00180 | review c1 → review (one rework task; 30 hook blocks, the day's worst) | 3190 | 26.90 | 388 | 237 | 30 |
| claude-autopilot | 00180 | review (rework close-out, handoff to c2) | 273 | 3.25 | 51 | 45 | 4 |
| claude-autopilot | 00180 | review c2 → done | 1261 | 15.36 | 182* | 123* | 16* |

| agent-skills | 00022→00030 | done → build | 89 | 0.96 | 31 | 25 | 4 |
| agent-skills | 00030 | build → build (plan + task 1, handoff) | 1188 | 7.31 | 161 | 104 | 6 |
| agent-skills | 00030 | build → review (tasks 2-3) | 1359 | 4.78 | 103 | 72 | 10 |
| agent-skills | 00030 | review c1 → review c2 (three rework tasks) | 1903 | 41.36 | 320 | 208 | 16 |
| agent-skills | 00030 | review c2 → done (one more rework task) | 1734 | 21.61 | 110 | 65 | 0 |
| claude-autopilot | 00180→00181 | done → build | 169 | 1.30 | 44 | 37 | 6 |
| claude-autopilot | 00181 | build → build (plan + task 1, handoff) | 1133 | 6.14 | 159 | 104 | 10 |
| claude-autopilot | 00181 | build → review (tasks 2-4) | 2499 | 14.78 | 70 | 48 | 4 |

| claude-autopilot | 00181 | review c1 → done (one rework task, converged) | 2280 | 29.42 | 302* | 187* | 16* |
| agent-skills | 00030→00032 | done → build | 102 | 1.07 | 25 | 22 | 4 |
| agent-skills | 00032 | build → review (plan + three tasks in one session) | 1330 | 10.89 | 222 | 158 | 12 |

| agent-skills | 00032 | review c1 → done (no rework) | 1054 | 11.16 | 139* | 83* | 8* |
| claude-autopilot | 00181→00182 | done → build | 120 | 1.17 | 32 | 26 | 4 |

| claude-autopilot | 00182 | build → build (planned 4 tasks, handed off with 0 done) | 1353 | 8.73 | 194 | 132 | 10 |

**Handoff between the commit and the state write** (00182, 01:18): the
session spent 22 min and $8.73 on Phase 0, planning and task 1, committed
task 1's feat/test/style commits (HEAD `bc49cf9`), then wrote
`.handoff-requested` and exited with `state.json` still saying task 1
`in_progress`, 0/4. The next session (01:24) found the mismatch, messaged this
session to rule out a peer collision, and had to mark task 1 done itself
before starting task 2. Two costs: a Phase 0 re-entry, and a reconciliation
turn that depends on a human-readable git log. The task-boundary handoff
should run after the `task-done` state write, never between the commit and
it.

| agent-skills | 00032→00034 | done → build | 161 | 1.17 | 33 | 29 | 6 |
| agent-skills | 00034 | build → review (plan + two tasks) | 1496 | 9.95 | 201 | 134 | 12 |
| agent-skills | 00034 | review c1 → done (one rework task) | 1264 | 19.55 | 227* | 159* | 18* |

| agent-skills | 00034→00036 | done → build | 140 | 1.07 | 30 | 24 | 4 |
| agent-skills | 00036 | build → review (plan + four tasks in one session) | 1628 | 11.39 | 276 | 175 | 4 |
| agent-skills | 00036 | review c1 → review c2 (three rework tasks) | 1585 | 24.29 | 299 | 185 | 18 |
| agent-skills | 00036 | review c2 → done (no further rework) | 828 | 9.92 | 158* | 98* | 18* |
| claude-autopilot | 00182 | build → build (tasks 2-3, handoff) | 2925 | 15.04 | 335 | 213 | 14 |
| claude-autopilot | 00182 | build → build (3 min, handed off again) | 177 | 0.84 | 36 | 31 | 8 |
| claude-autopilot | 00182 | build → review (task 4) | 493 | 3.19 | 89 | 62 | 6 |

| claude-autopilot | 00182 | review c1 → review c2 (three rework tasks) | 3916 | 45.13 | 430 | 274 | 26 |
| claude-autopilot | 00182 | review c2 → done (one more rework task) | 1850 | 22.60 | 272* | 164* | 24* |
| agent-skills | 00036→00038 | done → build | 98 | 1.05 | 19 | 18 | 4 |
| agent-skills | 00038 | build → build (plan + task 1, handoff) | 782 | 5.81 | 156 | 105 | 10 |
| agent-skills | 00038 | build → review (tasks 2-3) | 949 | 7.08 | 166 | 109 | 8 |

| agent-skills | 00038 | review c1 → review c2 (one rework task) | 1129 | 17.49 | 217 | 143 | 16 |
| agent-skills | 00038 | review c2 → done (one more rework task) | 1035 | 14.56 | 181* | 111* | 12* |

| claude-autopilot | 00182→00183 | done → build | 117 | 1.15 | 25 | 20 | 2 |
| claude-autopilot | 00183 | build → build (plan 7 tasks + task 1; cut by out_of_credits, Ivan killed) | 1938 | 11.94 | 155 | 91 | 6 |
| claude-autopilot | 00183 | build → build (dead relaunch, credits out) | 4 | 0 | 0 | 0 | 0 |
| claude-autopilot | 00183 | build → build (task 2 redone from scratch at opus, handoff) | 3385 | 39.76 | 319 | 182 | 8 |

| agent-skills | 00038→00044 | done → build | 155 | 0.82 | 31 | 26 | 10 |
| agent-skills | 00044 | build → build (76 min at opus: planning 9 tasks, 0 done, handoff) | 4588 | 41.83 | 436 | 241 | 14 |

**A CI-dependent task stalls by construction in loop mode** (00044,
agent-skills, 10:46). Task 8's premise needed the `windows-latest` job to
run on GitHub, but loop mode defers `git push`, so `origin/master` was 91
commits behind local `master` and the premise check failed. The session ran
the sanctioned stall (`autopilot stall --site premise`), which parks the PRD
in `hold/` and clears its tasks; tasks 1-7 stay committed locally. Sunk cost
at the stall: about $150 across five build sessions at opus. The gate should
refuse, or the loop should push before, any acceptance that reads remote CI;
otherwise every such PRD burns its whole build before stalling on the last
task.

**Pre-work alone cost $41.83** (00044, agent-skills, 04:55-06:11). The
PRD's frontmatter asks for it: `catchup: force`, `design: run`,
`default_model: opus` (verified in the PRD). The session ran full catchup,
wrote a 45 KB design doc (`designs/00044-...-design.md`, 05:47), planned
nine tasks, completed none and handed off. That is the most expensive
zero-task session of the run, and all of it was requested by the PRD author
rather than chosen by the loop; a gate that questions `design: run` on a CI
fix would have flagged it.

| claude-autopilot | 00183 | build → build (task 3 only, 65 min at opus, handoff) | 3923 | 45.84 | 414 | 231 | 6 |

| claude-autopilot | 00183 | build → build (task 4) | 1383 | 15.07 | 181 | 124 | 4 |
| claude-autopilot | 00183 | build → build (task 5, handoff) | 2018 | 29.87 | 282 | 162 | 4 |
| claude-autopilot | 00183 | build → review (tasks 6-7) | 2065 | 29.86 | 294 | 173 | 6 |
| claude-autopilot | 00183 | review c1 (five rework tasks; cut by the 09:05 limit) | 2995 | 44.91 | 394 | 254 | 38 |
| claude-autopilot | 00183 | review c1 (dead relaunch, credits out) | 4 | 0 | 0 | 0 | 0 |
| claude-autopilot | 00183 | review c1 rework (five tasks) → review c2 | 5550 | 76.98 | 607 | 358 | 6 |

| claude-autopilot | 00183 | review c2 → done (one more rework task) | 5110 | 74.29 | 613* | 414* | 34* |

| claude-autopilot | 00183→00184 | done → build | 231 | 1.65 | 36 | 25 | 6 |
| claude-autopilot | 00184 | build → build (plan + tasks 1-2, handoff) | 1361 | 8.83 | 207 | 135 | 10 |
| claude-autopilot | 00184 | build → build (task 3, handoff) | 412 | 3.67 | 80 | 49 | 4 |
| claude-autopilot | 00184 | build → review (task 4) | 509 | 4.15 | 84 | 48 | 0 |
| claude-autopilot | 00184 | review c1 → done (one rework task) | 1295 | 16.96 | 193* | 115* | 2* |

| claude-autopilot | 00184→00185 | done → build | 93 | 0.97 | 23 | 21 | 2 |
| claude-autopilot | 00185 | build → build (plan + task 1; cut by the 14:44 limit) | 1754 | 15.03 | 262 | 157 | 10 |
| claude-autopilot | 00185 | build → build (dead relaunch, then a 27 s resume) | 4+27 | 0.28 | 6 | 5 | 0 |
| claude-autopilot | 00185 | build → build (task 2, handoff) | 1067 | 6.92 | 177 | 122 | 6 |
| claude-autopilot | 00185 | build → review (task 3) | 467 | 3.09 | 77 | 56 | 6 |
| claude-autopilot | 00185 | review c1 → done (one rework task) | 2314 | 26.30 | 316* | 191* | 24* |

**00185 closed at 15:56** (claude-autopilot, ungated, sonnet): three tasks,
$51.62 (build $25.32 including the $15.03 session the limit killed, review
$26.30), ~1h35m, one cycle. This repo's backlog is now empty: batch
202609061630 drained eight PRDs (00178-00185) for about $750 recorded.

**00184 closed at 13:54** (claude-autopilot, ungated, sonnet): four tasks,
$33.61 (build $16.65, review $16.96), ~1h, one cycle. Same four-task shape
as 00183's first four tasks at one tenth of the cost: the difference is the
opus pin and the review yield.

**00183 closed at 12:50** (claude-autopilot, ungated, `default_model: opus`):
seven tasks plus six rework tasks, $383.59 recorded (build $187.50, review
$196.09), ~7.4 h of session time, two cycles. The most expensive PRD of the
run; its two review sessions alone ($77 and $74) cost more than any whole
PRD except 00017. It renders batch-report sections.

**00183 at cycle 2 (11:23)**: seven tasks plus five rework tasks, $309.30
recorded so far (build $187.50 at opus, review $121.89), ~6h of session time,
the most expensive PRD of the run before its second cycle has even run. The
review-rework session alone was 92 minutes and $76.98 with 607 tool calls.

**00183 at 05:47**: three of seven tasks in 2h35m of session time and $98.69,
all at opus (the PRD pins `default_model: opus` in its frontmatter, written
by the Codex session that filed it; the routing honours the pin for the
orchestrator session as well as the task floor; it is the largest of the
ungated five). Task 2 cost $39.76 (first attempt died with the credits at
04:15, second started over) and task 3 cost $45.84 on its own: one task per
session, each session paying Phase 0 again. At this rate the PRD's build
alone lands near $250 before review.

| agent-skills | 00044 | build → build (task 1, then tasks 2-7 across four opus sessions) | 888+2126+3874+3291 | 9.54+30.39+28.74+32.60 | - | - | - |
| agent-skills | 00044 | stalled at task 8 (premise: CI needs a push), parked | - | - | - | - | - |
| agent-skills | 00044→00047 | done → build | 155* | 0.82* | - | - | - |
| agent-skills | 00047 | build → build (plan + task 1, handoff) | 1099 | 8.17 | 163 | 102 | 8 |
| agent-skills | 00047 | build → review (task 2) | 1065 | 6.71 | 163 | 121 | 8 |
| agent-skills | 00047 | review c1 → done (one rework task) | 1168 | 15.51 | 192* | 126* | 12* |

| agent-skills | 00047→00051 | done → build | 103 | 1.05 | 28 | 23 | 4 |
| agent-skills | 00051 | build → build (79 min at opus: catchup, design doc, 14-task plan, 0 done) | 4749 | 54.75 | 369 | 176 | 6 |

**Pre-work again, larger** (00051, agent-skills, 11:45-13:04): `design:
run`, `default_model: opus` (verified in the PRD), 14 planned tasks against a
15-task loop ceiling, $54.75 before any task. With 00044's $41.83 that is
two zero-task opus sessions in one morning, both author-pinned.

**00047 closed at 11:42** (agent-skills): two tasks, $30.39, ~55 min, one
cycle, sonnet build. **00044 parked** at ~$143 recorded for 7 of 9 tasks.

**00038 closed at 04:13** (agent-skills): three tasks, $44.94, ~1h05m, two
review cycles, two rework tasks. Agent-skills since the 19:42 restart: eight
PRDs closed (00020, 00021, 00022, 00030, 00032, 00034, 00036, 00038) for
$339.36 recorded, average $42.

**00182 closed at 03:54** (claude-autopilot, ungated): four tasks, $95.53
(build $27.80 over four sessions and three handoffs, review $67.73 over two
cycles and four rework tasks), ~3h30m of session time. The second most
expensive PRD of the run after 00017, and the review alone cost more than
00179 and 00180 together.

**00036 closed at 03:07** (agent-skills): four tasks, $46.67, ~1h07m, two
review cycles, three rework tasks. **00182 build** (claude-autopilot): four
sessions and three handoffs for four tasks, $27.80, ~1h20m; review cycle 1
raised three rework tasks at 02:39.

**00034 closed at 01:58** (agent-skills): two tasks, $30.67, ~48 min, one
review cycle, one rework task. Agent-skills batch since the 19:42 restart:
00020, 00021, 00022, 00030, 00032, 00034 closed, $247.75 recorded for six
PRDs (00030's $76 is the outlier; the other five average $34).

**00032 closed at 01:09** (agent-skills): three tasks, $23.12, ~40 min, one
review cycle, no rework. The two no-rework PRDs today (00022, 00032) both
came in at $22-23 and 36-40 min: that is the floor of the pipeline's
ceremony for a small PRD, roughly half build and half review.

**00181 closed at 00:53** (claude-autopilot, ungated PRD): four tasks,
$51.64 (build $20.92, review $29.42), ~1h40m of session time, one review
cycle, one rework task. (*counters span the null placeholder and the
session.)

**00030 closed at 00:27 on the 7th** (agent-skills): three tasks, $76.02,
~1h43m of session time, two review cycles, four rework tasks. Review $62.97
versus build $12.09: the widest review-to-build ratio of the day.

**00180 closed at 23:12**: one task, $55.91 (build $9.43, review $46.48),
~1h35m of session time, two review cycles, one rework task. The review
phase was five times the build for a two-line runner change plus test pins,
and the cycle-1 session logged 30 hook-blocked calls.

**Batch 202609061630 (claude-autopilot) drained the three gated PRDs**:
00178 $91.08, 00179 $30.06, 00180 $55.91 = $177.05 recorded, plus the hops.
Review phases: $52.45 + $20.42 + $46.48 = $119.35, two thirds of the total.

**00022 closed at 22:43** (agent-skills): four tasks, $22.62, ~36 min of
session time, one review cycle with zero rework, the cheapest PRD of the day.
(*counters attributed to the null placeholder row that preceded it.)

**00021 closed at 22:04** (agent-skills): four tasks, $33.05, ~50 min of
session time, one review cycle. **Evening pattern on both repos**: with the
machine awake and no usage-limit sleep, PRDs of 1-4 prose or small-code tasks
close in 45-60 min for $30-35: build at sonnet $9-13, review at opus $20 that
finds one rework item and converges. The review session is two thirds of the
cost even in the good cases.

**00179 closed at 21:24**: 3 real rows (plus the done→build hop before it and
a null placeholder), ~45 min of session time, $30.06 (build $9.64, review
$20.42), one review cycle, one rework task. Same PRD shape as 00178 at a
third of the cost: no handoff, no opus build promotion, review converged in
one cycle. The review session still costs twice the build even here.

**00179 build in one session**: 20.6 min and $9.64 for planning plus two
prose tasks at sonnet, no context-pressure handoff. The whole build cost less
than 00178's single opus task. Same shape of PRD (prose edits plus one prose
test); the difference is the absence of handoffs and the opus promotion.

**00178 closed at 20:35**: 13 loop-metrics rows, 6.9 h of session wall-clock
(2.2 h of it the dead sleeping session), $91.08 recorded, two review cycles,
four rework tasks. The review phase cost $52.45 against $34.33 for the build,
and the PRD was prose-only (a persona section, two policy sections, ledger
sentences, one prose test). Calendar time 00:01-20:35 with about 16 h of that
idle (stand-down pause, usage limit, lid-close sleep).

00017 closed at 11:13: 2 review cycles, 3 rework tasks, recorded cost $235.84
over ~8h50m wall-clock (00:00-11:13 including the 55-min limit sleep), plus
two unrecorded sessions. For comparison the hand-built 00176 (Codex, four
review cycles) closed in 2h20m.
*partial: watch restarted at 00:12, session ran 00:01-00:18. Phase 0 + plan-tasks (4 tasks) for a prose-only PRD with catchup and design skipped.

Running totals at 07:50: 00016 ≈ 1h57m and $44.36 plus one unrecorded
session; 00017 ≈ 5h40m and $175.35 with review cycle 2 still open (a
four-task bug-fix PRD, "malformed memory half-written").

## Overnight observations (00:20-07:50)

- **Blocked tool calls: 92 across ten agent-skills sessions** (0, 12, 18, 0,
  8, 14, 6, 4, 6, 24 per session). Each is one wasted model round trip: the
  harness's auto-mode note tells sessions to read with `cat`/`head` and search
  with `grep`/`find`, and aegis `prefer_tools.py` blocks exactly those. Review
  sessions, which fan out to subagents, are the worst (12 and 24). Backlog PRD
  00184 (tool discipline in every bash-bearing loop prompt) targets this; the
  count above is its baseline.
- **Context-pressure handoffs dominate the build phase.** 00017's four tasks
  took three build sessions of 65-90 min ($37-48 each at opus), each ending on a
  `.handoff-requested` marker (02:33, 04:34, 05:58). Every handoff re-enters
  Phase 0 and reloads context (the done→build hop measured 244 s, $1.07, 33
  tool calls with nothing to build). Discovery 00177 scoped this out; the
  numbers say it is the largest single line after review cycles.
- **Opus on every 00017 build session.** Corrected: 00017's frontmatter pins
  `default_model: opus` (and `rework_cap: 5`, `catchup: force`), so the
  routing launched every build session at opus by author request: $122 of
  build before the first review for a small fix PRD. The pin is meant as the
  per-task floor; it also sets the orchestrator session model, which is the
  expensive half.
- **Review cycle 1 on 00017: 94 min, $47.77, two rework tasks** (4/6 → 6/6
  inside the review session), then cycle 2 opened at 07:47. Review sessions
  are the most expensive per hour in both batches.
- **Null-metrics rows are systematic, not lost sessions** (corrected 21:05).
  Every PRD in both ledgers shows the same sequence: `review→review`, then a
  row with null phase, signal and cost, then `review→done`. 00002 through
  00017 on agent-skills and 00178 here all follow it, so the null row is a
  placeholder the loop writes when a review converges, immediately followed by
  the real done-hop row; the tool calls my watch attributed to it belong to the
  surrounding session. Cost is not undercounted. It is still ledger litter:
  every consumer of `loop-metrics.jsonl` has to skip these rows, and the
  `wall_secs` gap they hide is the converge-to-done hand-off.
- **Stale `.handoff-requested` hypothesis not confirmed**: the marker was
  consumed at 00:10 and the session ran on for 53 more minutes, so the
  step-6.5 check ignores a marker it did not write. Later markers were real.
- **Shared five-hour budget at 91% by 08:53** (`rate_limit_event`
  `allowed_warning`, utilization 0.91, reset ~10:00) with both loops running:
  agent-skills in 00017's second review cycle at opus, claude-autopilot in
  00178's build. Expect one or both loops to sleep until the reset; the idle
  time is pure waste that a per-machine scheduler (run one batch at a time, or
  let the loop check utilization before launching an opus review session)
  would avoid.
- **Lid closed at 11:40:42 on battery; both batches were dead by 15:11 and
  idle until 19:32.** `pmset -g log`: "Entering Sleep state due to 'Clamshell
  Sleep' Using Batt (Charge:80%)" at 11:40:42, then only dark wakes of 2 s
  every 16-21 min. Both loops froze mid-session (00178 review cycle 1 had just
  started rework task 5 at 11:39; 00020 was in build). On the 13:01:10 wake
  both sessions flushed "API Error: Can't reach the API server (ENOTFOUND)"
  and exited; both loops relaunched at once, the new sessions burned 10 API
  retries in 72 s across dark wakes (last write 14:24:03), and the loops'
  connectivity poll, which counts wall-clock, saw its 1800 s budget elapse
  while the machine slept and declared "session died (API unreachable for
  1800s)" at 15:11:12, exiting instead of waiting. Cost: two dead relaunches,
  the cut-short rework turn, and ~8 h of batch idle (11:40-19:32) on both
  repos. Worth optimizing: (a) the poll should measure with a monotonic clock
  or reset on a detected sleep gap, and keep waiting rather than dying when
  the outage is local (ENOTFOUND, not a 5xx); (b) `autoclaude` could hold a
  `caffeinate -i` while a batch runs, or refuse to start on battery without
  `_AUTOPILOT_ALLOW_BATTERY=1`, since a closed lid ends every unattended run.
- **Second ungated refill** (seen 2026-09-07 16:00): 00186-00189 filed from
  the ddb refactor assessment on the 6th at 10:43-10:48 and 00190-00192 from
  the config-audit walkthrough on the 7th at 10:12-10:15, while this repo's
  loop was draining. Five of the seven pin `default_model: opus`; 00192 adds
  `design: force` and `rework_cap: 3` to a file split. The loop picked 00186
  (23 KB, opus) the minute 00185 closed. Same gap as the first refill, now
  with the opus pins the assessment flagged as the largest build-cost lever.
  00186 planned to 6 tasks by 16:07; `.handoff-requested` appeared at 16:33
  with 0 of 6 tasks closed, so the opus session crossed the 320K soft cap on
  planning plus one task's TDD round. It hands off after task 1: six tasks
  will cost six sessions plus orientation each (knob 3 and knob 4 evidence).
  Session 1 closed 16:44: $33.97, 46 min, 378 tool calls, planning plus task
  1 of 6 at opus. Session 2: task 2 closed 17:22, marker at 17:24, two
  minutes after the boundary check, so task 3 runs past the soft cap (third
  instance of the late-marker pattern today). Outcome, same as agent-skills
  at 16:31: the hard cap fired mid-task 3 during Pat's review dispatch (the
  reviewer session was killed mid-run, ledger row closed `killed`, review to
  be re-run from a fresh uuid). Session 2 closed 17:57 at $45.81, 71 min,
  442 tool calls: task 2 complete, task 3 committed through the style gate,
  `cap_rotations` gained task 3. Two hard-cap rotations in one afternoon,
  both on the task after a late marker; each costs a killed reviewer
  dispatch plus a re-orientation, on top of the marker's own handoff.
  Session 3 closed task 3 at 17:59, two minutes in, with the 17:24 marker
  still on disk, so it hands off again at once: the stale-marker double
  handoff (00191) reproduced on this repo too. That session: $5.22, 6 min,
  66 tool calls. Both stale-marker sessions today ($11.50 and $5.22) bought
  one Pat review and one task-done each; the orientation share is most of it.
  Task 4: $11.03 cut by the window, then $52.90 and 107 min for the redo
  session, which closed the task at 21:38 and ended on a third hard-cap
  rotation (`cap_rotations` now lists tasks 3 and 4). One opus task, about
  $64. 00186 so far: 4 of 6 tasks, about $150. Task 5: $42.19, 62 min, 379
  tool calls, closed 22:39. 00186: 5 of 6, about $190 before review. Task 6
  closed 22:47 in a 5-min session; build→review transition at 22:49 with
  `.handoff-requested` still on disk across the edge, the exact 00191 case.
  Watching whether the review session honours the stale marker. Review
  cycle 1 (22:49-23:14) added 10 rework tasks to the 6 built. The marker
  was cleared at 23:16 without a handoff (no session row), so the stale
  marker did not bite at the review edge this time. Rework task 1 of 10
  closed at 00:36 Sep 8, 80 minutes at opus; at that pace the rework alone
  is 10+ hours and $300-400, more than the build.
- **Review-phase session killed at the 3-hour wall** (00186, 22:50-01:50
  Sep 8, wrapper.log: "session exceeded the 10800s wall-clock cap;
  SIGTERM"): `_AUTOPILOT_SESSION_MAX_REVIEW` is 10800 s. The session ran
  review cycle 1 (25 min), rework task 1 (80 min), then 74 minutes on rework
  task 2 with only its tests committed (`32a2e51` at 01:48, two minutes
  before the kill). The loop relaunched at 01:50. wrapper.log also shows one
  earlier "memory pressure (level 2); waiting" hold before a launch (before
  11:25 Sep 7, duration not recorded). The metrics row records cost 0 and no output tokens, so the
  real cost (3 h at opus, 771 tool calls, 22 hook blocks; likely $80-120) is
  missing from every total. The relaunched session closed rework task 2 at
  01:59, nine minutes in, so the work lost to the kill was small; the
  hidden cost is the missing metrics row, not redone work. Third distinct killer of in-flight work
  today after the usage window and the hard cap; unlike those two, this one
  has no soft warning and no rotation card, and it also hides its own cost.
- **Sixth usage-window exhaustion** (agent-skills, 13:41-14:56 Sep 7, window
  reset 14:50 CEST): the opus build session on 00051 task 2 hit the limit
  mid-Devon-round (the "Running Mutation B" subagent died with the limit
  error), closed at $42.62 with 0 output tokens recorded, and the 14:56
  session redid task 2 from the test stage (its contract card lists Tess,
  Ivan, Pat and de-slop all in that session; closed 15:45 at `154c9b5`).
  Second instance of the killed-in-flight pattern. The redo session has not
  closed its metrics row yet, so its cost is unknown.
- **Seventh usage-window exhaustion** (both loops, 18:26-19:50 Sep 7, reset
  19:50 CEST): the window that opened at 14:50 lasted 3.6 h with both loops
  at opus. Both in-flight sessions died with a killed subagent: 00186 task 4
  session at $11.03 and 32 min, 00051 task 5 session at $18.01 and 48 min,
  both with 0 output tokens recorded. 84 idle minutes, about $29 of cut
  sessions. agent-skills closed task 5 at 20:41 in the resumed session.
  Since 14:50 the joint pattern is roughly 3.5 h running, 1.5 h waiting.
- **Handoff marker lands after the boundary check** (agent-skills 00051):
  task 2's task-done at 15:45:32, `.handoff-requested` at 15:48:33; the
  session had passed step 6.5 already and is into task 3 at 16:04 with the
  marker still present. It is honoured only when task 3 closes, so a whole
  opus task runs past the soft cap. Direct evidence for the headroom rule in
  discovery 00193, PRD 2. Outcome: the hard cap fired at 16:31, 43 minutes
  after the soft marker, mid-task 3 (Pat review not yet run). The session
  closed at $55 and 102 minutes (task 2 redo plus task 3 up to step 5.65).
  The cap rotation is the designed path: task 3 reset to `pending`,
  `cap_rotations` gained an entry, and the contract card tells the next
  session to resume at step 5.7 with the three task-3 commits (`86da70d`,
  `95d7b01`, `38d4bda`) kept. Whether the 16:34 session honours that card or
  re-dispatches Tess is the thing to watch; a redo would be ~$20 of waste.
  Outcome: the card was honoured. Task 3 closed 16:47 after 13 minutes (Pat
  review and task-done only). But the 15:48 `.handoff-requested` marker
  survived the cap rotation, so this fresh session hands off after one
  13-minute task: another orientation round bought by a stale marker. This is
  the 00191 case, one PRD ahead of its fix. That session closed at $11.50
  for 14 minutes and 120 tool calls: Pat's review, the task-done write, and
  a handoff, at opus. Task 3 total: about $30 across the cap-cut session's
  share plus this one. Next session (16:48): soft marker at 17:33 with task
  4 still open, so on this PRD every opus task is one session and each
  crosses the soft cap on its own. Task 4 session closed 17:48: $43.36, 60
  min, 342 tool calls, 12 hook blocks. Task 5: $18.01 cut by the window plus
  $28.80 for the 50-min redo session that closed it at 20:41. 00051 so far:
  5 of 14 tasks, about $300 including design; a straight-line projection is
  $650-750 for the build alone. Task 6: $47.35, 91 min, 410 tool calls,
  closed 22:11. Task 7: $42.26, 83 min, closed 23:34. 00051: 7 of 14,
  about $390; the per-task rate has settled at $42-47 and 60-90 min. Task
  8: $55.09, 99 min, closed 01:13 Sep 8. 00051: 8 of 14, about $445. Task
  9 closed 02:25; marker at 02:27, two minutes after the boundary (fourth
  late-marker instance), so task 10 runs past the soft cap.
- **state.json is an orientation tax** (agent-skills): 121 KB, of which
  `tasks` is 110 KB (14 entries, 3.4-13.4 KB each before any attempt is
  logged: plan-tasks stores the full task text in state). run-autopilot
  SKILL.md line 61 has every session read state.json at entry; a full read is
  roughly 27K tokens per session. Whether each session reads all of it was
  not measured. Input for the session brief in discovery 00193, PRD 3.
- **Contract card reinjected into the wrong session**: this monitoring
  session, compacting at about 16:00 inside the claude-autopilot checkout,
  was handed the loop's contract card ("step: build gate / Phase 2 for
  00186") by the SessionStart:compact hook
  `~/.claude/hooks/reinject_contract_card.py`. The hook keys on the
  checkout's `contract-card.md`, not on the session that wrote it. Harmless
  here; an interactive session in a checkout with a live loop is told it is
  mid-build after every compaction. The fix is a ~/.claude hook change, not
  this pack.
- **Post-gate PRDs drain ungated.** The backlog gate approved 00176-00180 at
  20:53 on the 5th; between 22:52 and 00:10 four PRDs were filed by the Codex
  00176 session (00181-00184) and one by the loop's own routing proposal
  (00185). At 23:17 the loop selected 00181 without any gate having read it.
  Either the gate needs to run per batch start inside the loop (a cheap
  compliance-and-grounding pass) or the loop should refuse PRDs newer than the
  last gate report in `dev/local/audit-results/`.
- **Fourth (09:05) and fifth (14:44) exhaustions, credits still out.** Each
  time both loops hard-stopped mid-session and slept to the reset: at 09:05
  the 00044 build session ($28.74) and the 00183 review session ($44.91)
  lost their in-flight subagents; at 14:44 the 00051 build session ($42.62,
  a Devon mutation run killed) and the 00185 build session ($15.03) did the
  same, each followed by a 2-4 s dead relaunch. Running tally of sessions
  cut by the limit: seven, about $185 of session cost with the work of their
  last subagent lost.
- **Third exhaustion at 04:13 on the 7th, and the overage ran dry.** Minutes
  into overage the events flipped to `overageStatus: rejected,
  overageDisabledReason: out_of_credits`: both loops hard-stopped, the 00183
  build session died at $11.94 with an Ivan subagent terminated mid-task
  ("Agent terminated early due to an API error"), each loop burned a dead
  relaunch (4 s and 6 s), and both slept to the 04:50 reset. Two loops
  exhaust the five-hour window roughly every four hours of joint running, and
  overnight they also consumed the whole overage allowance. From here every
  window end is a hard stop plus lost in-flight subagent work.
- **Second window exhaustion at ~22:50, this time on overage.** The
  `rate_limit_event` flipped to `status: rejected` with `overageStatus:
  allowed` and `isUsingOverage: true` (in the morning it was
  `org_level_disabled`), so both loops kept running on paid overage until the
  23:50 reset instead of sleeping. Two loops on one account turn a soft limit
  into a bill; the loop reads these events and could pause itself at
  `allowed_warning` when overage is enabled, or the operator can decide per
  batch with a `_AUTOPILOT_NO_OVERAGE=1` guard.
- **The limit landed at ~09:05 on both loops.** Each running session ended on a
  synthetic API-error message, each loop relaunched once into an immediate
  rejection (11 s and 7 s, $0), then slept to the 10:00 reset: about 55 min
  idle on both batches. On agent-skills the review-cycle-2 session lost a
  reviewer subagent mid-review ("Agent terminated early due to an API error"),
  so that lens re-runs after the reset. A loop that reads
  `rate_limit_event.utilization` before launching a session could have parked
  one batch at 90% and let the other finish its cycle.
- **00178 also handed off after task 1** (`.handoff-requested` at 08:51, ten
  minutes after the task-1 commit), so the context-pressure handoff is not an
  agent-skills quirk: a prose-only PRD on sonnet hits it too.
- **Stand-down false positive halted the claude-autopilot batch for 8 h (00:20-08:19).**
  Session 1 (00:01-00:18, $3.52) mistook its own headless pid for a foreign
  session, spent four minutes investigating and ended on a question no one
  could answer; session 2 (00:18-00:20, $0.50) read `_AUTOPILOT_LOOP`
  correctly but the stand-down rule fired on "busy interactive peer in this
  repo" (this monitoring session, mid-turn) plus a commit six minutes old.
  During a batch `state.json` is always fresh, so the rule reduces to "any
  active Claude session in the repo pauses the loop", and a pause is permanent
  until a human relaunches. The relaunch decision was answered at ~00:50 and
  not executed until 08:19 (this session dropped it under the notification
  stream). Worth optimizing: (a) the rule should require the peer to be a
  writer (recent commit authored from that session, or an owner marker), not
  merely present; (b) a stand-down should retry after a cool-off instead of
  stopping the loop; (c) a session that finds `_AUTOPILOT_LOOP` set must never
  reach `AskUserQuestion`.
