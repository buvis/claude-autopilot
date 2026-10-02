# autoclaude observation, 2026-09-27 21:10 to 2026-09-28 21:50

Observed live from an interactive session, with `autoclaude` (plain renderer)
on plugin 0.5.6 in this repo. The run covered PRD 00215 (task 3 onward,
through the review and done gates) and PRD 00216 (tasks 1-4). Sources are the
render log (`scratchpad/loop.log`, 4.9K lines), `loop-metrics.jsonl`, and the
00215 cycle-1 review file. Prior findings V1..V47 live in
`validation-batch-202609252154-2026-09-26.md`, and the tags below point there.

## Timeline (loop-metrics)

| Start | End | PRD | Gate | Model / effort | Min | $ |
|---|---|---|---|---|---|---|
| 27 21:12 | 22:10 | 00215 | build (task 3) | opus xhigh | 58 | 34.39 |
| 22:10 | 23:28 | 00215 | build (task 4) -> review | opus xhigh | 78 | 30.62 |
| 23:28 | 00:15 | 00215 | review c1 | opus xhigh | 46 | 24.54 |
| 00:15 | 01:52 | 00215 | review c1 | opus xhigh | 96 | 56.26 |
| 01:52 | 04:14 | 00215 | rework (5 tasks) | sonnet xhigh | 142 | 24.18 |
| 04:14 | 04:43 | 00215 | rework | sonnet xhigh | 28 | 9.71 |
| 04:43 | 05:15 | 00215 | rework | sonnet xhigh | 31 | 8.86 |
| 05:15 | 05:48 | 00215 | review c2 -> done | opus high | 33 | 17.23 |
| 05:48 | 05:51 | 00215 | done | sonnet medium | 3 | 1.51 |
| 05:51 | 10:27 | 00216 | build tasks 1-4 (4 sessions) | sonnet xhigh | 274 | 82.21 |
| 10:27 | 21:50 | - | **paused (dirty_tree_foreign)** | - | 683 | 0 |

- 00215 from task 3: 8h36m and $207.
- 00216 tasks 1-4: 4h34m and $82.
- 11h23m of wall time went idle on one pause.
- Session relaunch gaps were under a minute every time.

## Findings, ranked by wall time at stake

### O1. Foreign writers in the loop's checkout: 11h+ idle, plus a tax on every session (new)

What happened: two interactive sessions (me, and another writer doing the
`dev/local` -> `docs/dev/project-management` migration) wrote into the same
checkout while the loop ran.

- Session 1 spent 5.5 min (21:12-21:18) on forensics over my commit c26156f:
  mtimes, git dates, ListAgents, SendMessage, a 2-min wait.
- Every later session start pinged me, because the stand-down check treats
  any busy interactive `claude-autopilot-*` session as a possible peer. That
  was 4 pings, each waiting up to 2 min.
- The review had to rebuild its diff to exclude the 177-file commit (863 KB
  down to 114 KB). The mechanical replay still emitted 20 `[MECH]` lines,
  every one against the foreign commit.
- The other writer's in-flight edits touched 00216 task 5's two files, and the
  loop correctly paused at 10:27. Nobody attended until 21:50.

Levers:
- **Operational:** never edit the loop's checkout while it runs. Do side work
  in a worktree, or run the loop itself in one (`autopilot wave` already makes
  lane worktrees). This costs nothing and would have saved all 11h.
- **Pause notification reach:** the pause fired `notify.py`, but 11h passed.
  A push that reaches the phone (ntfy) for `paused` would bound this.
- **Cheaper peer check:** skip the ping when the busy peer has not written in
  the last N minutes. `git status` clean plus no mtimes newer than the leave
  row is already strong evidence.

### O2. Test gaps named by Devon but never closed turn into a review rework cycle (V2 variant)

What happened: in task 3, Devon round 2 (10 min) came back BROKEN with 7 named
test gaps. The contract says "flag and proceed", so Ivan got the gaps as traps
but the tests stayed weak.

Evidence from review cycle 1:
- 5 of the 23 High/Medium findings are those same gaps, marked "Gap N
  CONFIRMED".
- The review says gap 5 is "precisely why H1 was never caught".
- Cycle 1 plus rework plus cycle 2 took 6h16m and $140, against 2h16m for the
  whole task-3/4 build.

Lever: when round 2 is BROKEN, spend one targeted Tess pass (about 5-10 min)
on the named gaps before Ivan, instead of carrying them to review. It won't
remove H2-H5 (a missing error path, id validation, a docs contradiction, a
dropped field), so rework likely still happens. It would shrink the rework
from 5 tasks and stop test-shaped findings from recurring in cycle 2. The
saving is a guess: roughly 1-2h per affected PRD.

### O3. Every session re-derives gate bookkeeping on the model at xhigh (V10/V29 family, still open)

What happened in session 1:
- 8 min passed before `/autopilot:work`.
- Of that, 2.5 min was about 15 separate model calls for deterministic steps:
  mkdir, marker clear, park handler (exit 3 "nothing to do"), custody list,
  select, batch show, frontmatter, handoff row, catchup skip, design reuse,
  the empty-review-log awk, the contract card write and load.
- The rest was reading the brief, state and dispatch telemetry.
- All of it ran on opus or sonnet at `--effort xhigh`.

Lever:
- One `autopilot resume` CLI verb that runs the whole Phase 0 plus artifact
  skips and prints the next action and the card. The skill already says
  "if code can answer, code answers".
- Launch the orchestrator at medium effort. Subagents do the heavy work, and
  xhigh thinking on 15 bookkeeping calls is pure latency.
- Estimate: 3-6 min per session across about 15 sessions, so 45-90 min per
  2-PRD run. That's a guess from one measured session.

### O4. Gates fire after the implementor instead of inside it (new)

What happened:
- Task 3's style gate failed after Ivan's commit (`assemble` was 58 lines,
  the limit is 50). That took a separate Ivan dispatch and gate rerun, about
  6 min (21:54-22:00).
- 00216 task 4: Pat found 8 MEDIUM contract deviations, and an Ivan retry
  ran 10:01 to past 10:13.
- Pat's prompt rendered at 54.8K, over the 50K budget, which forced a
  trim-and-re-render pass. His reply broke the parse contract again, so a
  correction dispatch ran (V4 still live).

Lever:
- Ivan runs `check_style_limits.py` on his own diff before handing back. It
  is a cheap script, and he already runs pytest and ruff.
- Pat's CLOSURE-line fix from V4.
- Size Pat's inputs before rendering (the acceptance file duplicated the
  adversary list).

### O5. Tool-call friction, pure waste (V8/V29, still open)

Counts over the whole log:
- 83 aegis `prefer_tools` blocks (`cat`/`tail`/`head`/`find`), each a wasted
  round trip. The skill's own Shell Command Rules forbid these, and subagents
  (Devon, Ivan) hit them most.
- 72 loupe reflow mentions: subagents leave magic-trailing-comma reflow, and
  the orchestrator inspects and discards it each time.
- Other friction: `python3 -m pytest` without pytest (then hunting for `uv`),
  ruff run with an all-rules config (CPY001/TC003 noise), and gateguard
  fact-forcing blocks on first edits.
- 55 hits across these signals, 54 subagent dispatches in total.

Lever:
- Put the Shell Command Rules and the exact test command
  (`uv run --with pytest ...`) into every subagent prompt header.
- Exempt this repo from loupe's end-of-turn pass, or accept its style once
  (V8).
- Estimate: 10-20 min per run. That's a guess.

### O6. The global rules and the installed plugin disagreed on paths during the run (transient)

`~/.claude/rules/working-documents.md` already said
`docs/dev/project-management/` while the 0.5.6 cache used `dev/local/`.
Sessions probed the new path first (one failed `ls` per session) and a brief
carried stale paths into Ivan's contract. This goes away once a release
carries the migration. Until then, keep the rules and the cache in step.

## What did not cost time

- Session relaunch: under 1 min every time.
- The memory-pressure gate: about 1 min at start.
- A headless session ending its turn while Devon or Ivan ran in the
  background: the process stayed alive and resumed on the handback.
- The V44 lane deadlock did not recur.

## Suggested order

1. O1 operational rule, today: the loop gets its own worktree or an unshared
   checkout. Free.
2. O2: one targeted Tess pass on a BROKEN round 2. Small skill change.
3. O3: an `autopilot resume` verb plus a medium-effort orchestrator. The
   biggest recurring saving.
4. O4 and O5: prompt-header and self-check changes. Small.
