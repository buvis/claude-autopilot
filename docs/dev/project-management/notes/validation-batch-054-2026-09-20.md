# 0.5.4 validation batch (agent-skills, 00052 + 00053-00057)

Monitored read-only from session claude-autopilot-15 (this checkout). Loop launched by
the operator with `autoclaude` in agent-skills; batch 202609050909 resumes at 00052 build,
task 2 of 3. Every PRD carries `consensus_engine: shadow` (00110 evidence), so the review
sessions' Alice leg costs ~6.5x the legacy one; the eval subtracts nothing, it notes it.

Baseline: `scratchpad/eval_batch.py` over the ledger with cutoff 1789418064 (last 0.5.2
session end, 2026-09-15 04:07 CEST). Small 0.5.2 PRDs: $23-76, 0.6-1.7 h, 3-7 sessions.
Bar (plan): under $60 and under 1.5 h per small PRD, zero lost sessions.

## Watch list (the four fixes under test)

1. Stand-down: never for a `claude-autopilot-*` peer (this session is one). Any `paused`
   row with `stood_down` set is a finding.
2. Pat: no session ends with a backgrounded `sonnet-run.sh`; no `pat` dispatch row `lost`.
3. Headroom hand-off: no `.handoff-requested` written with no task in progress; no session
   handing off after its first task.
4. Devon: prose-pin tasks record `devon: skipped:prose`; no Devon round on `*_prose.py`.

Plus: rotation wip commits (`chore(<scope>): wip - rotated mid-task`) on any rotation, the
session brief written at every hand-off and read first, review sessions rotating back to
the review gate, lane classification lines in the report (`- Lane:`), stub minting at
batch end.

## Session log

(one line per session as the loop runs: time, prd, phase, signal, wall, $, notes)
- 21:20 CEST loop launched (wrapper.log fresh). Session 1: 00052 build, sonnet xhigh, lane
  full/full (0.5.4 frontmatter verb ran), consensus_engine shadow, resumes task 2 of 3.
  Phase 0 ran ListAgents with this claude-autopilot-15 session live and did NOT stand down
  (fix 1 holding). No session-brief.md yet (none written before 0.5.4; expected from the
  first hand-off on). A stale 1-byte `.handoff-requested` from 2026-09-14 sits in the dir;
  watching whether /work step 2 clears it.
- 21:50 session 1 still on task 2 (30 min): ~100 tool calls, one Agent dispatch ("Fix
  report.py CRITICAL findings (task 2 retry)"), only the `resume` handoff row in
  dispatch-metrics so far (no `start` row for that Agent dispatch; check at session end
  whether the retry path skips record_dispatch). The stale `.handoff-requested` is still
  there; the session's log mentions the marker only in read prose, so step 2 did not clear
  it. Watch: if step 6.5 after task 2 reads it and hands off with task 3 pending, that is
  the 00191 edge-clear not covering a pre-0.5.4 marker (1 byte = legacy empty = current
  phase = matches, so it WOULD hand off).
- 22:11 task 2 completed (attempt: sonnet, lean pipeline, self_deslop committed 072c78e,
  style_gate fixed:df71f88, split_hygiene "failed: ... verified false positive, no change
  applied"). **Finding V1 (confirmed):** step 6.5 read the stale 1-byte
  `.handoff-requested` from 2026-09-14 (legacy-empty = current phase = match) and is
  handing off with task 3 pending: banner "2 tasks done, 1 pending — headroom rule fired"
  although no headroom rule fired this session. Cost: one extra session start (~5-10 min,
  ~$5). Cause: the marker predates 0.5.4, so no edge-clear ever ran on it, and neither
  Phase 0 nor /work step 2 clears a marker older than the session. Fix candidate: Phase 0
  (or the `_walk_up.py --clear-cap` call) removes any `.handoff-requested`/`.cap-fired`
  whose mtime precedes the session start; one-line rule plus a test. Also: no
  record_dispatch rows for the task-2 Agent dispatch (retry path), the `pat` row and
  `devon` field are absent for this task; check whether the retry path bypasses the
  telemetry. Watching the hand-off itself: brief write, leave row after next_phase.
- 22:27 **Session 1 row:** 00052 build, continue, 3090 s (51 min), $13.32, no stand-down,
  lane full/full. Hand-off artifacts all correct (fixes 00199/00201 holding): brief written
  20:11:27Z (lane line `full (classified full, security_path)`, Where, card, Read next),
  `leave` row at :37 after the brief; session 2 launched with `Read
  dev/local/autopilot/session-brief.md first.` in its prompt, read the brief, did not
  stand down, resumed task 3 (in_progress). One extra session from V1 (~5 min, ~$3-4).
- **Finding V2 (efficiency, confirmed):** session 2's context went 80K -> 267K in 66 calls
  before task 3 started: `catchup: force` in 00052's frontmatter re-runs the full
  `git-ferry:catchup` at EVERY Phase 0 entry, including a task-boundary resume inside the
  same PRD, right after reading the brief that already says where things stand. The
  headroom rule then fired at task-start 3 (marker `{"task_id": "3", ...}` at 20:16Z:
  233K left < task 2's recorded cost), which is harmless here (task 3 is the last task,
  step 6.5 skips on no pending tasks) but would cost a session on a 4-task PRD. Fix
  candidate: `catchup: force` means once per PRD entry, never on a same-PRD resume (the
  capsule freshness check already covers the rest); worth a small PRD, ~180K tokens and
  ~5 min per resume.
- 22:49 task 3 done (Ivan docs, Pat clean, commit 7b54ffc, suite 3334 passed); `phase-done
  --outcome tasks_done` -> review, card + brief + `leave` row written in the right order.
  **Finding V3 (HIGH, confirmed):** in the SAME assistant message as the hand-off banner
  ("handing off to fresh session for reviews"), the model called `Skill
  autopilot:run-autopilot` again instead of ending the turn (log line 655, msg
  011CfFL4r2Fb77rjxgwYaVaF), wrote a `resume` row for review 24 s after its own `leave`
  row, and is now running the whole review cycle inside the build session
  (ab9785a9): Alice and Blake as subagents, Bob and Carl as background Bash, no Watcher
  dispatched, the model keeping its turn alive with probe work while it waits. Context is
  at 503K (cache_read) and the cap hook is unguarded by design in `review` with no
  `rework_task_ids` (00196's guard covers rework sessions only), so nothing bounds this
  session until Phase 6 queues rework, at which point the hard cap (503K > 500K) rotates it
  back to the review gate. The loop sees one mega-session, no build row. Likely cause: the
  core SKILL.md "Run all phases in sequence without stopping ... Completing a sub-skill
  invocation is NOT a stopping point" outweighs the hand-off's "end the turn" for a
  sonnet orchestrator. Fix candidates: (a) prose: the Session handoff procedure ends with
  "the banner is the last output of this session; never invoke a skill after it" and the
  Execution Model paragraph carves out the loop-mode hand-off explicitly, pinned; (b)
  mechanical: a PreToolUse hook denying `Skill` calls to autopilot:* when `_AUTOPILOT_LOOP`
  is set and this session already wrote a `leave` row (dispatch-metrics, same session's
  wall clock), exit 2 with the reason. (b) is the one that holds under any prose.
- V3b (design note): the cap hook's "review without rework is unguarded" rule assumes a
  fresh review session; a build session that rolls into review carries its whole build
  context unbounded. Guarding `review` always (with the 00196 return-to-review-gate
  rotation) would close it.
- 23:07 mega-session still alive (pid 97230), context 615K. 00052 review-1 written
  (23:05Z): all four reviewers reported (Bob first run OK, Carl on copilot), Verdict 18
  findings, at least one 4/4 consensus row; Phase 5/6 next. **Finding V4 (blocks 00110,
  confirmed):** `consensus_engine: shadow` did NOT run the workflow leg: the `Workflow`
  tool refused `scriptPath ~/.claude/workflows/review-fanout.workflow.js` ("must be a
  script path this tool returned, or a file you can already read (the working directory
  or a directory you have added)"), the skill fell back to legacy Alice and stamped no
  `consensus_run_id`. So the 00110 evidence path is dead on this harness build for any
  repo outside ~/.claude: stamping `shadow` banks nothing and costs nothing. Fix
  candidates: review-work-completion step 5 passes the workflow inline (`script` = the
  file's text, or `scriptPath` under the repo after copying it into `dev/local/tmp/`), or
  the loop adds `--add-dir ~/.claude/workflows`. Until then, unstamp 00053-00057 is
  optional (harmless), and 00110's premise note needs this recorded.
- 23:23 mega-session still alive; its context was auto-compacted by the harness somewhere
  after 615K (now 155K cache-read), which is why it survived. Phase 5 classified 18
  findings: 1 CRITICAL (render() accepts unknown attempt_dir / non-VALID attempts /
  bad verdicts, 4/4 consensus) deferred-to-batch-end for the audit trail, 3 HIGH + 12
  MEDIUM auto-fix, 2 discarded; settled-decisions ledger written. Phase 6 is running the
  00194 rework design in-session (`design-solution --rework`, dispatch 1 of 3 running),
  the first live exercise of 00194. Side note: the orchestrator paused to resolve the
  step-7-vs-Phase-6 task-creation overlap with a subagent (the 00194 review's deferred
  Medium 1, now a measured cost). The shadow leg was retried by hand (read the diff,
  called Workflow inline) and refused again on the scriptPath (V4 confirmed twice).
  Still no `.cap-fired`; the hook stays unguarded until `rework_task_ids` lands.
- 23:44 **Session 2 row (the mega-session):** build launched, continue, 4497 s (75 min),
  $27.25; it ended mid-rework-design after dispatch 1 ("Waiting for dispatch 1's result"
  was its last text: an Agent dispatch awaited by ending the turn, the finding-15 shape
  for subagents; the loop read state_touched and continued, no death). Session 3 launched
  at 23:27Z as a proper review session on opus xhigh (+ sonnet fallback), read the brief,
  skipped Phases 4-5 by artifact (review-1 on disk), found the rework design doc
  interrupted (no terminal `result:` line) and re-invoked `design-solution --rework`
  exactly as 00194's artifact rule says; codex unavailable -> Claude fallback for
  dispatch 2; the doc now ends `result: ok` (23:43Z) with the Source review line matching.
  00194's resume path works. Cost of V3 so far: the review ran in an over-cap session
  and the rework design was done twice (~15 min, ~$8). 00052 running total: $40.6, 2.1 h,
  3 sessions, rework not yet dispatched.
- 00:05 session 3 (opus review) created three [D1] rework tasks (4: opus, the CRITICAL
  validation; 5 and 6: sonnet, the medium tail and the C6 test) and is running task 4
  in-session (Tess + one gate retry so far). Cap hook re-armed on `rework_task_ids` and
  the headroom rule fired at task-start 4: the review session was already at 464K
  (review context + three design-review dispatches), so the marker
  `{"phase": "review", "task_id": "4"}` will hand off after task 4 with 5 and 6 pending;
  that is the intended lossless path (00196 + 00200), each remaining rework task costing
  its own session. Task-bound stamping works (task 2: 80K -> 446K, calls 1 -> 124; the
  00200 pairs are `usage_at_start`/`usage_at_done`). **Finding V5 (efficiency):** a
  review session enters rework with ~460K of context because the review consolidation
  and the rework design's three dispatch packages all live in the orchestrator; either
  hand off between the rework design and the first fix task (fresh session, brief carries
  the design path) or keep the design prompt packages out of the orchestrator's context.
- 00:31 **Session 3 row:** review launched, continue, 3364 s (56 min), $60.17 (opus xhigh).
  Task 4 did NOT finish: the hard cap fired mid-task (Tess + Devon rounds on top of 464K)
  and the hook ROTATED: `cap_rotations: [{task 4, cycle 1, phase review}]`, next_phase
  review (00196), and the session committed `beb18bd chore(use-qwen): wip - rotated
  mid-task` after the two test commits (00202 live: nothing lost). Session 4 (opus,
  00:23Z) read the brief, resumed the rework dispatch at task 4 and picked up at Devon
  round 2 from the wip commit's body (00202 resume) rather than re-dispatching Tess.
  Fixes 00196 + 00200 + 00202 all exercised on the same rotation and held. 00052 running
  total: $100.7, 3.0 h, 4 sessions; opus review sessions are the cost driver ($60 for one
  rework task that then rotated). The bar (under $60/1.5 h) is already missed for 00052;
  it is not a small PRD (task 2 needed 7 CRITICAL fixes, 18 review findings), so the bar
  applies to 00053-00057.
- 00:57 **Session 4 row:** review launched, continue, 1790 s (30 min), $20.40 (opus).
  Task 4 completed (Devon round 2 resumed from the wip commit, Ivan, deslop, Pat twice:
  the first Pat prompt was 61 KB over the 50 KB budget and was killed after 18 s, the
  trimmed 49 KB retry passed), then a clean task-boundary hand-off with tasks 5, 6
  pending and `rework_task_ids` trimmed to ["5","6"] (00196's drop-completed rule).
  Session 5 (opus, 00:53Z) resumed at task 5 (Tess dispatched). Dispatch telemetry is
  intact (my earlier query used the wrong keys): tess/devon/ivan/deslop/pat rows all
  present; Pat rows are foreground (fix 2 holding: no `lost` Pat since launch, the 7
  `lost` closures are pre-launch rows closed at the first hand-off per 00182).
  **Finding V6 (efficiency):** every rework session runs on opus xhigh because the review
  phase routes opus, even when the remaining rework tasks are sonnet-tier (5 and 6) and
  Phases 4-5 are already done; a resume that lands directly in "Dispatch rework" could
  take the tasks' own tier (or `session_model`). Sessions 3-5 are the bulk of 00052's
  cost. 00052 running total: $121, 3.5 h, 5 sessions, 2 rework tasks left + cycle 2.
- 01:29 session 5 (opus) still running: task 5 completed (Tess, Ivan x2, Pat foreground),
  task 6 in progress (Ivan, Pat running). No Devon on 5/6: sonnet tier-gate, as designed.
  Next: Phase 6 exit -> `phase-done --outcome rework` -> hand-off -> cycle-2 review session.
- 02:00 **Session 5 row:** review launched, continue, 2707 s (45 min), $38.31 (opus).
  Tasks 5 and 6 completed, `phase-done --outcome rework` -> cycle 2, `rework_task_ids`
  cleared. Session 6 launched as the cycle-2 review on opus **high** (the 00185 rerun
  effort rule visible in the argv), reviewing now; no review-2 file yet. 00052 running
  total: $159.5, 4.3 h, 6 sessions (0.5.2 baseline for a review-heavy PRD of this size,
  00017: $228 / 8.0 h / 9 sessions).
- 02:31 **Session 6 row:** review (cycle 2, opus high), continue, 2144 s (36 min), $53.12.
  Review-2: 10 findings, 0 CRITICAL / 0 HIGH -> Medium/Low tail sweep queued as one
  `[D2] Tail sweep` task (7, sonnet), `rework_task_ids: ["7"]`; session 7 (opus high,
  02:05Z) is running it with a headroom marker already armed at task-start (the review
  session enters rework near the cap again, V5). Bob: codex hit its usage limit
  (resets 06:11), the doubt lens ran as the Claude fallback (lens kept, 00178 path).
  **V4 update:** the opus session worked around the Workflow scriptPath refusal by
  copying `~/.claude/workflows/review-fanout.workflow.js` into `dev/local/tmp/` and the
  shadow leg RAN: `consensus_run_id: wf_bc133a2a-4a5`, stats_line `dimensions 5, raw 11,
  unique 11`, workflow APPROVE vs legacy converge (no gating divergence, 10 more
  advisories, 4 overlapping Bob). That is the fix for the skill: copy the workflow into
  the repo's `dev/local/tmp/` before calling the Workflow tool. **V4b:** the 00110 gate
  greps the literal `no verdict divergence`, but the skill only says "record any verdict
  divergence" with no pinned wording; this file says "Divergence from legacy Alice: none
  at the gating level" and would NOT count. Pin the phrase in the skill (or key the gate
  on the stats_line plus `Divergence from legacy Alice: none`).
- 07:33 (the 03:03 wakeup fired 4.5 h late; catch-up from the ledger). **00052 closed:**
  session 7 (review, 23 min, $9.98) ran the tail sweep and converged; finalize session
  (sonnet, 4 min, $1.95) moved it to done, wrote the audit, minted THREE hold stubs
  (00081-00083: `vet` undocumented shapes flag, `vetting.json` nine keys, render accepts
  unknown attempt; 00195 live, `batch.minted_stubs` = 3), and the report section carries
  `- Lane: full (classified full, security_path)` (00204 live). 00052 total: 8 sessions,
  5.4 h, $225, 2 cycles, 0 lost sessions, 1 rotation (recovered). Observation V7: the
  `review_converged` row's per-cycle severity counts read all zero for both cycles
  (verdict 18 and 10) - the 00188 parser missed this file's table shape; the batch
  report's Run conditions line under-reports severities.
- **00053 closed** (opus design PRD, 6 tasks): build 2 sessions (34 + 65 min, $39.3),
  review-1 11 findings (opus, 36 min, $67.0), tail sweep (7 min, $3.2), finalize (4 min,
  $1.9): 5 sessions, 2.4 h, $111, 1 cycle. Lane `full (unparsed)`: the classifier could
  not parse the PRD's named paths (no Repository Structure block?); harmless (design:
  run routes full anyway) but the reason should read `design`.
- **00054 closed** (sonnet, 2 tasks): build 27 min $10.7, review-1 6 findings (opus, 29
  min, $40.3), finalize 3 min $1.7: 3 sessions, 1.0 h, $53, 1 cycle. Lane `full
  (unparsed)` again.
- **00055 in flight:** build 2 sessions (30 + 13 min, $21.2; the second is a headroom
  hand-off after the first task, V1/V2 shape again?), review-1 5 findings (opus, 36 min,
  $52.3), cycle 2 running now (session 15, opus high). 
- Shadow leg (V4 workaround) ran on every cycle since 00052-2: stats_lines banked below
  for 00110 - 00052-2 `dimensions 5, raw 11, unique 11`; 00053-1 `dimensions 4, raw 12,
  unique 11`; 00054-1 `dimensions 4, raw 5, unique 4`; 00055-1 `dimensions 4, raw 8,
  unique 8, confirmed 2`. Two cycles show raw > unique (dedup collapse). None writes the
  literal `no verdict divergence` (V4b), so the pinned gate still counts 0.
- Interim bar check (small PRDs): 00054 $53 / 1.0 h (under both), 00053 $111 / 2.4 h
  (over, but it is an opus design PRD), 00055 already $73 / 1.3 h with cycle 2 open.
  The opus review session is the cost floor: $40-67 per cycle-1 review alone, so no PRD
  that takes a full review can come in under $60 total. Zero stand-downs, zero deaths,
  zero parks so far.
- 08:05 **00055 closed** (sonnet, 2 tasks): build 30 + 13 min ($21.2), review-1 5
  findings ($52.3, 36 min), cycle-2 review ($19.2, 14 min), finalize ($1.3, 2 min):
  5 sessions, 1.6 h, $94, 2 cycles. **00056 in flight:** build 23 min $9.7 (one session,
  no hand-off), review-1 running (session 20, opus xhigh, since ~07:40). 00057 remains.
- 08:40 operator paused the loop (`paused-by-operator`); 00056 converged at review
  (6 findings, 0 C/H, shadow ran: `dimensions 5, raw 5, unique 5`) and sits at
  `phase: done` awaiting its finalize session; 00057 not started. Monitoring ends here.

## Eval (batch 202609050909, ledger as of 2026-09-21 08:40 CEST)

Bar: under $60 and under 1.5 h per small PRD, zero lost sessions.

### 0.5.2 baseline (batch 202609050909, before cutoff)

| prd | sessions | wall h | $ | review sessions | stood down | died | park |
|---|---|---|---|---|---|---|---|
| 00015-corrupt-queue-reads-as-drained-v1. | 8 | 4.7 | 120 | 4 | 0 | 0 | 0 |
| 00016-queue-lands-in-wrong-repo-v1.md | 7 | 2.8 | 61 | 2 | 0 | 0 | 0 |
| 00017-malformed-memory-half-written-v1.m | 9 | 8.0 | 228 | 4 | 0 | 0 | 0 |
| 00020-changelog-skill-presence-check-v1. | 6 | 5.4 | 63 | 2 | 0 | 1 | 0 |
| 00021-risks-tile-fake-zero-v1.md | 4 | 0.9 | 34 | 1 | 0 | 0 | 0 |
| 00022-node-ci-and-install-docs-v1.md | 3 | 0.6 | 24 | 1 | 0 | 0 | 0 |
| 00030-survey-prunes-skip-dirs-deep-v1.md | 5 | 1.7 | 76 | 2 | 0 | 0 | 0 |
| 00032-sweep-validates-out-late-v1.md | 3 | 0.7 | 23 | 1 | 0 | 0 | 0 |
| 00034-timeout-leaks-prompt-to-disk-v1.md | 3 | 0.8 | 31 | 1 | 0 | 0 | 0 |
| 00036-create-skill-scripts-help-and-unio | 4 | 1.1 | 47 | 2 | 0 | 0 | 0 |
| 00038-braid-docs-flags-and-backup-paths- | 7 | 1.1 | 47 | 2 | 0 | 0 | 0 |
| 00044-windows-ci-junction-claim-v1.md | 7 | 5.4 | 182 | 0 | 0 | 0 | 0 |
| 00047-check-links-repeated-stats-v1.md | 4 | 1.0 | 31 | 1 | 0 | 0 | 0 |
| 00051-qwen-eval-harness-core-v1.md | 33 | 32.5 | 1421 | 11 | 0 | 1 | 0 |
| 00052-qwen-eval-harness-report-v1.md | 2 | 1.6 | 22 | 0 | 0 | 0 | 0 |
| **mean/PRD** | 7.0 | 4.6 | 161 | | | | |

### 0.5.4 validation (after cutoff)

| prd | sessions | wall h | $ | review sessions | stood down | died | park |
|---|---|---|---|---|---|---|---|
| 00052-qwen-eval-harness-report-v1.md | 8 | 5.4 | 225 | 5 | 0 | 0 | 0 |
| 00053-split-oversized-brief-suites-v1.md | 5 | 2.4 | 111 | 2 | 0 | 0 | 0 |
| 00054-non-json-metadata-kills-collect-v1 | 3 | 1.0 | 53 | 1 | 0 | 0 | 0 |
| 00055-bad-metrics-ts-aborts-run-v1.md | 5 | 1.6 | 94 | 2 | 0 | 0 | 0 |
| 00056-ci-failure-fakes-no-ci-v1.md | 2 | 0.9 | 44 | 1 | 0 | 0 | 0 |
| **mean/PRD** | 4.6 | 2.2 | 105 | | | | |

Verdict: **zero lost sessions** (no stand-down, no death, no park; one hard-cap
rotation recovered with the wip commit) - that half of the bar holds and all four
fixes under test held on their first live exercise. The cost half does not:
of the four small PRDs only 00054 came in under $60 / 1.5 h; 00055 ($94, 1.6 h) and
00056 ($44 build+review so far, finalize pending) sit above or at the line, and the
cause is structural, not a regression: every PRD pays one opus review session of
$40-67, and every rework cycle adds an opus rework-resume session. Against the
0.5.2 mean ($161 / 4.6 h / 7.0 sessions per PRD, inflated by 00051) the 0.5.4 run
reads $105 / 2.2 h / 4.6 sessions per PRD; on comparable small PRDs (0.5.2:
$23-76, 0.6-1.7 h) it is roughly even, with the shadow Alice leg (~6.5x on that
lens) and the review-session floor absorbing the savings the hand-off fixes made.

Findings V1-V7 are filed as PRDs 00207-00211 in this repo (V4b and V7 recorded on
00110 and here, not yet PRDs); the wave idea from the lanes is a discovery doc.

## Addendum 2026-09-21 (reviews of the fix PRDs 00207-00211)

- **Finding V8 (HIGH class, confirmed):** the 00211 review session (opus, headless,
  `_AUTOPILOT_LOOP=1`) dispatched Alice and Blake as subagents and Bob and Carl as
  background Bash but never dispatched the Watcher subagent, then ended its turn with
  "Waiting on Bob and Carl."; the harness killed both CLI reviewers and no review file
  was written ($6.50, 7 minutes lost). The 00209 and 00210 sessions of the same batch did
  dispatch the Watcher. Same class as V3 (prose the orchestrator can skip): the fix for
  finding 15 covered Pat's dispatch only. Candidate mechanical fix: the three
  `*-run.sh` helpers refuse `run_in_background` shapes under `_AUTOPILOT_LOOP` unless a
  Watcher marker exists, or the review skill runs Bob and Carl through one foreground
  `await_reviewer_outputs.py` call instead of two background jobs plus a Watcher.

- **Finding V9 (latent, found 2026-09-21 while grounding the wave PRDs):** the
  review skill's step 3 says a cycle-1 full review runs `gather-context.sh` without
  `--since`, and the script diffs against the detected base branch. The loop commits on
  `master`, so on master that diff is empty. The 00054 cycle-1 context file shows the
  orchestrator noticing this and passing `--since <work_start_sha>` on its own
  (`review-context-00054-c1-202609210335.md` line 137: "this repo commits directly on
  master, so the script's branch-base diff would be empty"). A literal orchestrator
  reviews an empty diff. Fix candidate: under autopilot state, step 3 passes `--since
  <state.work_start_sha>` for the full review too (the same range the scope line already
  uses), and `gather-context.sh` labels it `full review (work range)`.

## Status 2026-09-21: v0.5.5 (tag 8885300, local, pushes pending)

Shipped: V1 -> 00210, V2 -> 00209, V3/V3b -> 00211, V5 -> 00208, V6 -> 00207. All five
reviewed in fresh sessions (converged; deferred M/L on each PRD in `prds/done/`; review
files in `dev/local/reviews/002XX-*-review-0N.md`). 3667 passed, 1 skipped at the tag.

V8 -> PRD 00213 (`prds/backlog/`, written 2026-09-21: lane markers from the two wrappers
plus a Stop hook that holds the session while a lane is alive). Open, no PRD yet: V4
(document the workflow copy into `dev/local/tmp`), V4b (pin the "no verdict divergence"
phrase or re-key the 00110 gate), V7 (`review_converged` severity counts read zero), V9
(cycle-1 review diff on master depends on the orchestrator adding `--since`). Wave routing:
`dev/local/discovery/00212-route-prds-in-waves.md` -> PRDs 00214 (plan + launch), 00215
(assemble), 00216 (assembly review + `wave run`), 00217 (review-slot semaphore), written
2026-09-21 via create-prd; open questions 1-4 decided in their Problem Statements. The
agent-skills loop is paused at
00056 done / 00057 pending; resume it on 0.5.5 after `/plugin update autopilot@buvis-plugins`.

