# autoclaude inefficiencies - two live loops (measured 2026-09-13 13:40 CEST)

## Conclusions (2026-09-13 evening, after a full day of watching both loops)

1. Unit economics. One opus task costs ~200 tool calls, 60-80 minutes and $50-70; Ivan's
   implementation is 5-10 minutes of that. Sessions cost $50-140 each and cost is context x calls,
   not output (9K output tokens in a $52 session).
2. Where the money goes, ranked: (a) the test-authoring loop, Tess x3-5 plus Devon x2 per task,
   40-70 minutes before Ivan writes a line, and Devon broke the tests in every round today, so the
   loop is a fixed tax rather than a filter; (b) orientation, ~100 calls per session across ~40
   sessions per batch; (c) lost work, rotations and wall-cap kills that redo committed tests or
   code (tasks 10, 12, 13 today; two 3-hour review sessions on claude-autopilot); (d) the design
   step spending a whole session (249 calls, 338K) before planning; (e) rework volume, one
   review turning 32 findings into 10 opus rework tasks, more than the PRD had.
3. Review is the strong and cheap part: $28-40 per cycle, and it catches real defects (invalid
   YAML frontmatter, a null-cost crash). Its output is where cost explodes, and at the cap it
   still defers unresolved Highs (8 on 00186), so the assurance is partial even at full price.
4. Backlog dynamics. agent-skills batch: 12 PRDs done, 26 in backlog, 21 parked in hold.
   claude-autopilot: 8 done, 15 in backlog, every one of them meta-work on autopilot itself. The
   loop files more PRDs than it drains (review deferrals, stalls, self-improvement) and the meta
   share is far above the 30% ceiling.
5. Verdict. The full pipeline earns its cost on cross-cutting, algorithmic or security-sensitive
   changes. For prose edits, one-file fixes and test scaffolding, which were most of today's
   tasks, it is a 5-10x tax over a solo session followed by one review pass.
6. Levers, by yield: (1) route by risk lane so most PRDs never enter the full loop, est. 50-70%
   of batch spend; (2) thin the per-task pipeline without touching the review roster, Devon only
   on contract or algorithmic tasks, headroom handoffs, the session brief (PRDs 00196-00202),
   est. 30% per opus task; (3) cap meta-work to the highest-yield PRDs and run the loop on product
   repos with $/task per lane as the metric. Decision taken 2026-09-13: start with lever 1.

Loops: agent-skills (PRD 00051, build phase, task 10 of 14) and claude-autopilot (PRD 00186, review
phase cycle 1 rework, task 10 of 16). Both run plugin cache autopilot 0.5.1.
Sources: each repo's `dev/local/autopilot/{loop-metrics,dispatch-metrics}.jsonl`, `.turn-counts.json`,
and the transcripts `ee920ac5` (agent-skills, died at the turn tripwire) and `8f7c779f`
(claude-autopilot, killed by the 3 h review wall cap).

## Headline numbers

| metric | agent-skills 00051 | claude-autopilot 00186 |
|---|---|---|
| spend so far | $450, 14 sessions, 13.8 h, 9/14 tasks | $239 + one unrecorded 3 h session, 11 sessions, 9.8 h, 9/16 tasks |
| orientation before first dispatch | 99 calls, 13K -> 159K context | 100 calls, 13K -> 181K context |
| one opus task, full pipeline | task 9: 205 calls, 67 min, 11 dispatches | task 7: ~170 calls, 80 min, 9 dispatches |
| Tess+Devon before Ivan runs | 5 dispatches, 40 min | 5 dispatches, 50-70 min |
| sessions at the 300-call tripwire | 7 of 103 (17 more at 200-299) | 3 of 59 (10 more at 200-299) |
| cost driver | $52 per session for 9K output tokens; cache reads 13K -> 356K | same shape; 8f7c779f reached 448K |

## Findings, ordered by impact on cost and lost work

### 1. HIGH - the context cap hook is inert during review-phase rework builds
`autopilot_context_cap_hook.py:680` returns unless `state.phase == "build"`. Cycle-1 rework runs
`/work` inside the review session (phase stays `review`), so no soft cap, hard cap, or turn tripwire
applies. Session 8f7c779f: review done in 26 min, then rework tasks 7 and 8 ran unguarded to 448K
context and 427 calls until `_AUTOPILOT_SESSION_MAX_REVIEW=10800` killed it mid-Ivan. Cost of that
session is unrecorded (`cost_usd: null`), Ivan's task-8 work was lost, and the next session redid it.
Fix: gate the hook on `phase in {"build","review"}` when `rework_task_ids` is non-empty, or have the
review phase hand off to a fresh build session for rework instead of running `/work` inline.
Quality impact: none. Only bounds cost and prevents wall-cap kills.

### 2. HIGH - the running plugin lags the repo's own efficiency fixes
Both loops run cache 0.5.1 (2026-09-05). `[Unreleased]` in claude-autopilot already holds: Devon at
one strengthen round (max 2 Devon + 4 Tess per task, PRD 00179), dispatch rows closed at handoffs,
Bob retry on refusal, review effort routing (xhigh cycle 1, high after). Live sessions today still run
two Devon rounds (task 10 in agent-skills: Devon, Tess "strengthened 7 holes", Devon round 2).
Fix: release 0.5.2 and relaunch both loops at the next task boundary. Zero code needed.

### 3. HIGH - TURN_TRIPWIRE=300 clips healthy opus sessions; the second clip parks the PRD
Hook line 90 says the tripwire sits "deliberately above the healthy-session norm". Measured norm:
~100 calls orientation + ~200 per opus task. One opus task fits per session; the second dies mid-flight
(ee920ac5: task 9 done at call 303, task 10 Tess done, Devon running, tripwire -> rotation).
`cap_rotations` already names task 10 once in agent-skills; a second fire -> `oversized_task` stall
-> PRD parked at 9/14. Live session 74133160 must finish task 10 within its remaining budget.
Fix options: count only orchestrator-originated calls (exclude Monitor/TaskStop/telemetry, ~25% of
calls); or hand off at step 6.5 when calls used > 120 (a fresh session per opus task costs ~$8 of
orientation, a rotation costs a lost task plus orientation); or raise to 600 for `opus` tasks.

### 4. HIGH - soft-cap check at the task boundary raced the marker by 14 s
ee920ac5: step 6.5 read `.handoff-requested` at 00:26:24Z with context 319.7K (absent), claimed task
10 at 00:26:40Z at 321.4K; the hook wrote the marker in between. Fix: step 6.5 reads the live usage
total (the hook already parses it; expose it as `statectl usage`) and hands off when
`usage + est_context_peak_of_next_task > SOFT_CAP`.

Second shape, seen 2026-09-14 17:32 CEST (00190 session 1, e45acedb, Sonnet, 337K): the
handoff procedure ran `rm .handoff-requested` at 15:32:43Z; the hook fired on that Bash
call's own PostToolUse, usage still above 320K, no task in progress, and rewrote the marker
as `unknown` (7 bytes). Session 2 (82039fed) inherited it and handed off after one task at
309K, below the soft cap. One task per session is the steady state under 0.5.2 until 00191
(clear the marker at the resume edge) or 00200 (no SOFT_CAP) lands.

### 5. MEDIUM - rotation and wall-cap kills lose uncommitted subagent output
Tess's 603-line test file (agent-skills task 10) and Ivan's task-8 edit (claude-autopilot) both sat
uncommitted when their sessions died. Today's sessions handled it well (reused the tests; discarded
a 3-line Ivan edit) but spent ~15 calls each deciding. Fix: commit Tess output at 2.9 before Devon
runs (Devon is read-only on tests); on rotation, stage allowlisted files as a WIP commit.

### 6. MEDIUM - ~100 calls of orientation per session
Both transcripts: 6-11 single-key `jq` reads of state.json, `Read` of 4-6 skill reference files
(12K + 11K + 26K cache creation), a full `/git-ferry:catchup` because `catchup_head_sha` is stale
from the loop's own commits, and in 8f7c779f a 20-call hunt for the `autoclaude` binary
("Find autopilot executable", "List local bin", "Search bash plugin..."). ~$8-10 and 5 min per session.
Fix: one `statectl resume-brief` printing every field the build/review gates read; treat catchup as
fresh when every commit since `catchup_head_sha` is a loop task commit (ancestor of `work_start_sha`
chain); pin the CLI path in the contract card.

### 7. MEDIUM - Tess writes oversized test files, then Ivan spends 19 min splitting them
8f7c779f task 7: style gate failed on file size after Ivan's implementation; an extra Ivan dispatch
("splits the oversized test file", 19 min) plus a second style-gate run. Tess's prompt does not carry
the 800-line file limit. Fix: put the per-task style limits in `tess-prompt.md` and run the style gate
on the test commit at 2.9, before Ivan.

### 8. MEDIUM - consensus under-counted by path-format mismatch
00186 review-1 says so itself: Alice cites `/Users/.../SKILL.md (lines 166-171)`, Bob cites
`skills/fast-track/SKILL.md:166`; `files_match` in `consolidate_findings.py:150` compares segment
tails, and the `(lines a-b)` suffix survives `_TRAILING_LINENO_RE`, so four real [2/4] agreements
rendered as [1/4]. Fix: strip a trailing ` (lines N-M)` / `:N-M` in `normalize_file`, and have the
reviewer prompts demand repo-relative `path:line`. Quality impact: positive (consensus drives task
priority).
Third shape, 00191 review-1 (2026-09-14 21:30 CEST): five cross-reviewer pairs merged by hand,
"the script kept them apart because Bob's `File:` carries `:line` suffixes or the file was
`N/A`". Bob writes `N/A (skills/x.py:77, skills/y.py:91)` when a finding spans files; 00198's
regex never sees a path there. 00198 should also make the Bob prompt forbid `N/A` and require
the first file as the `File:` value, or teach `normalize_file` to take the first path inside
the parentheses.

### 9. LOW - stale `.handoff-requested` / `.cap-fired` markers survive across sessions
agent-skills still carries both from Sep 8. Each resuming session spends 3-6 calls discovering and
removing them (8f7c779f: "Find where the handoff marker is written", "Remove the stale handoff
marker", "Record the stale-marker decision"). Fix: the loop wrapper clears both at launch.

### 10. LOW - per-dispatch bookkeeping is 4-5 orchestrator calls
render, Agent, Monitor(15 min), TaskStop, telemetry close, plus a probe pair when a check-in fires.
~55 of task 9's 205 calls. Cheap individually, but they count toward finding 3.

### 11. INFO - review lens roster is efficient; rework volume is the cost
00186 cycle 1: 4 reviewers in parallel, 26 min end to end, 32 findings, 10 rework tasks at opus
(24 findings covered, 8 carried). The review itself is not the problem; the 10 opus rework tasks at
~70 min and ~$45 each are. Two levers that keep quality: route S-sized rework tasks (13, 14, 15) to
`sonnet` tier (no Devon), and let the classifier override the PRD's `default_model: opus` floor for
rework tasks whose finding is mechanical (YAML frontmatter, null guard).

## Actions taken 2026-09-13 (user decision: draft PRDs, release 0.5.2, keep monitoring)

- Discovery `claude-autopilot/dev/local/discovery/00193-cut-loop-overhead-without-thinning-review.md`
  (2026-09-07) already plans three PRDs covering findings 3, 4 and 6 (usage-headroom soft cap,
  after-task-done marker placement, session brief). Those PRDs are not yet created.
- New PRDs in claude-autopilot backlog: 00196 (findings 1, 3-turn-form, 5), 00197 (finding 7),
  00198 (finding 8). Finding 9 is PRD 00191. Finding 11 stays a suggestion here.
- Release 0.5.2: `dev/bin/release-checks` is red only on the four `test_fast_track_commit.py`
  pins that rework task 11 committed red by design; the release runs in the window after task
  11's fix commit while Pat reviews (tree clean, no subagent writing). Note: 0.5.2 ships the
  fast-track skill mid-rework (tasks 12-16 pending), which the loops do not use.

## First 0.5.2 session observation (claude-autopilot, cycle-2 review, ~19:00 CEST)

- LOW: the 0.5.2 `record_dispatch.py handoff` verb closed 67 never-closed rows from the whole
  batch (Sep 5-8 render-only rows, rows from killed sessions) as `outcome: lost, detail: "open at
  review/resume handoff"`, elapsed null. Correct by its contract (start without end), but the
  batch report will show 67 lost dispatches attributed to today's handoff. One-time per upgraded
  batch; a `lost` row could carry the id's queued_at session instead of the closing handoff. The 3
  ids with two end rows (`05ab58ae`, `5405c491`, `8492e78c`) predate the upgrade: 0.5.1 sessions
  closed a row as killed at a rotation and again as ok after resume.

## Finding 12 (19:30 CEST, claude-autopilot PRD 00187 build session)

HIGH: the design step runs inside the build session and consumed 249 tool calls and a 338K context
peak in 34 minutes (design doc, three review dispatches, ~35 design edits) before planning started.
The soft-cap hook wrote `.handoff-requested` with task `unknown` (no task in progress); the
300-call tripwire will fire during planning with the same `unknown` id, and `_fire_breach`
(hook :558) treats two consecutive breaches with one id as a livelock, so two long design or
planning phases in a row park a PRD as `oversized_task "unknown"`. agent-skills already carries
one `unknown` rotation entry from today. Recorded in PRD 00200 as the no-task rule plus a
headroom check at the design->plan and plan->work gate edges.
Recurred 2026-09-14 23:05 CEST on 00192 (`catchup: force`, `design: run`, opus, 7 tasks): the
build session wrote the 48KB design doc and the task plan, then the hard cap rotated it with
`task_id: "unknown"` before task 1 was claimed (`.cap-fired` + `.handoff-requested` both on
disk, `cap_rotations` = 1). Artifacts survived, so the relaunch resumes at task 1; a second
`unknown` rotation in the same PRD would park it as oversized.
Again 2026-09-15 02:10 CEST on 00194 (`catchup: skip`, `design: run`, opus, 4 tasks): 52 min
and $38.50 to write the 42KB design doc and the plan, soft cap at 331K during design, hard cap
right after task 1 was claimed (`cap_rotations` task_id "1", no Tess row, clean tree, nothing
lost). Every `design: run` opus PRD in this batch now burns one full session before its first
task; 00200's gate-edge headroom check is the fix, and until it lands `design: run` PRDs
should expect one rotation each.

## Finding 13 (21:15 CEST): the five-hour window drained under three loops

The account's five-hour window hit its limit at 20:19 ("You've hit your session limit, resets
9:10pm"). The agent-skills review session died mid-review (Bob and Carl rows lost, $14.75 spent,
the whole cycle re-runs) and the claude-autopilot build session died mid-Devon ($20.18). Both
relaunches failed instantly with the limit banner; both wrappers waited until the reset and
relaunched at 21:11, 50 minutes idle. A third loop (ovcaq, PRD 00004, 17/18 tasks) started at
20:30 on the same account, plus this monitoring session and the operator's own sessions. No loop
knows the others exist; PRD 00199's yield-to-the-oldest-loop rule is the designed fix, and until
it ships three loops will keep draining one window early. Seven-day window at 28%.

## Finding 14 (2026-09-14 10:15 CEST): false stand-down across repos

The agent-skills build session for the PRD after 00051 stood down one minute after launch:
"peer session claude-autopilot-c7 (busy, started ~1m ago) appears to own this batch; state.json
and contract-card.md both mtime ~60s old". The peer was the claude-autopilot loop's own review
session in another repo, and the 60-second-old writes were the agent-skills finalize session's
per-PRD reset. The wrapper consumed the marker and stamped `paused-by-operator`; the batch sat
idle until the operator noticed. Second false stand-down class after the 2026-09-02 one (PRD
00172). Fix folded into PRD 00199: the peer filter requires the ListAgents name to start with
this repo's directory basename, and writer evidence is a dirty tracked tree or a state write
later than the batch's last `leave` row, never a bare mtime.
Recurred 2026-09-14 22:33 CEST: agent-skills 00052 task-2 session stood down for
"claude-autopilot-52 (interactive, busy, started 3m ago)", the claude-autopilot loop's own
00192 build session, citing commit df71f88 (the agent-skills loop's own test-split commit 4 min
earlier) as peer evidence. Wrapper stamped `paused-by-operator`; batch idle until relaunched.
Two false stand-downs in one day; 00199's basename filter is the fix.

## Finding 15 (2026-09-14 19:39 CEST): a background Pat dispatch ended the build session

00191 build session 7606384b (Sonnet, 465K at the time) launched Pat's per-task review as a
`run_in_background` Bash call of `sonnet-run.sh` at 17:39:07Z, then ended its turn with
"Waiting for completion." and no Monitor call. Headless mode does not keep a session alive
for a pending background Bash: the parent exited at 17:39:13Z, the harness wrote `[killed]`
into the task's output file, Pat's own session (4857e2ac) died with no assistant turn and a
0-byte review file, and the wrapper relaunched (`signal=continue`, task 1 still in_progress,
no attempt row, no handoff row; the open `pat` dispatch row will read `lost` at the next
handoff). The relaunch re-oriented and re-dispatched Pat at 17:45Z: about 6 minutes and one
session start lost, no code lost. The same session's six Agent-tool dispatches (async agents)
resumed correctly, and 00190's Pat runs were foreground Bash calls that just blocked. Only
the "background Bash, then end the turn" shape dies.

Fix (prose pin, one line in `skills/work/references/per-task-review.md` or the sonnet
dispatch step, plus a prose test): in loop mode dispatch `sonnet-run.sh` as a foreground Bash
call with `timeout` (it blocks like the Agent tool does), never with `run_in_background`;
if a run must be backgrounded, the next call is `Monitor` on its output file, never a bare
end of turn. Candidate home: PRD 00199 (loop guard rails) or a small PRD of its own.
Recurred 2026-09-14 22:33 CEST in agent-skills (00052 task 2, 98-minute session, $21.82): same
`run_in_background` `sonnet-run.sh` Pat dispatch, same "Waiting for Pat's per-task review to
complete." end of turn, session exited, and the relaunch then hit finding 14's false stand-down,
so the batch went from "Pat running" to "paused" in under a minute with nobody at fault but the
prose. Three sessions lost to this pair in one evening; both fixes are one-line prose pins.

## Finding 16 (2026-09-15 03:40 CEST): Devon's round is dead weight on prose-pin tasks

Four prose tasks today (skill markdown edits pinned by substring tests) ran the full
Tess -> Devon -> Tess -> Devon chain and every round ended "exhausted, flagged" on the same
ceiling, that a substring pin cannot see negation, inversion or past-tense narration:
00191 T1 (Devon 164s + 248s, Tess retry 225s), 00192 T6 (424s + 313s, 47s; "hollow mixin"),
00194 T1 (140s + 124s, 204s; "negation-blind substring pins (known ceiling)"), 00194 T2
(175s + 416s, 840s; "past-tense narration passes bound pins; round exhausted"). About 55
minutes of Opus session time bought zero kept strengthenings; Devon's own verdict names the
ceiling each time. Fix: the step-2.9 gate skips Devon when every test file in the task is a
prose test (name matches `test_*_prose.py` or every assertion reads a `.md`), recording
`devon: skipped:prose` in the attempt row; or the adversarial prompt returns "ceiling" as a
first-attempt verdict and the orchestrator stops there. Candidate home: a small PRD beside
00197 (both are Tess-prompt economics).

## PRDs from discovery 00193 (created 2026-09-13 ~18:30 CEST)

- 00199 loop guard rails: probe-count outage budget, `allowed_warning` yield to the oldest loop,
  rejected never enters overage, ask-first stand-down. The discovery's caffeinate item is already
  met by the `autoclaude` shell function (`caffeinate -is`), so it is stated as a premise, not a task.
- 00200 usage-headroom handoff (replaces `SOFT_CAP`), marker read only at step 6.5 after task-done,
  `session_model` frontmatter key decoupled from `default_model`. Coordinates with 00196.
- 00201 session brief: `statectl write-brief` renders `dev/local/autopilot/session-brief.md` at
  every gate transition; the launch prompt names it; Phase 0 opens with it.
- Batch order that avoids file collisions: 00192 -> 00199; 00191 -> 00196 -> 00200; 00201, 00197,
  00198 anywhere.

## Release 0.5.2 (done 2026-09-13 ~18:00 CEST)

Local release in the loop's clean window at 16:48 (gate green: 146 fast-track tests, all
runner suites); commits `47bbf43` (claude-autopilot) and `6ebef97` (claude-plugins) pushed by the
operator over SSH; tag `v0.5.2`; `claude plugin update` installed 0.5.2 beside 0.5.1. Running
sessions keep 0.5.1 until they end; every fresh loop session from now on runs 0.5.2 (one-round
Devon cap, handoff closes open dispatch rows, review effort routing). Neither batch pins
`autopilot` in `plugin_versions`, so the loop's drift gate does not halt.

## Fresh evidence, afternoon of 2026-09-13

- claude-autopilot review session (started 13:19) hit the 10800 s wall cap again at 16:19,
  $138.53 recorded, killed mid style-fix dispatch on task 14 ("tree clean, nothing landed").
  Finding 1 reproduced live; the relaunch resumed correctly.
- agent-skills: two more tripwire rotations. One entry names `task_id: "unknown"` (fired between
  task 11's completion and task 12's claim, no task in progress). The other names task 12: the
  tripwire fired during Pat with task 12's tests and implementation already committed
  (`70229cd`, `dbf3487`), reset it to `pending`, and the session ended at $59. The next session
  re-attempts a task that is already implemented; a second fire on 12 parks the PRD. Per-session
  costs today: $64, $70, $59 for one opus task each.
- Pipeline per opus task on 0.5.1 is stable at Tess x3 + Devon x2 + Ivan + Pat; every Devon
  round 2 today still broke the tests, so the 0.5.2 one-round cap loses no assurance.

## Live status at 13:40 CEST
- agent-skills 74133160: task 10 in Devon round 2 (reused the orphaned tests, no Tess rerun).
- claude-autopilot 0c3401f9: discarded the dead session's 3-line Ivan edit, loaded the rework
  contract card, entering `/work` on task 10.
Watches armed on both: turns crossing 150/200/250, dispatch rows, commits, state deltas, markers.
