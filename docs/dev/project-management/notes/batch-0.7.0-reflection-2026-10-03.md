# Batch reflection: first run on 0.7.0 (2026-10-03, 00240 onward)

Written at 20:40 with 00242 at task 3 of 7. Sources:
- `loop-metrics.jsonl` (sessions since 15:11)
- `scratchpad/loop.log` from line 31983, where this batch starts
- `scratchpad/batch_signals.py` and `blocks_by_actor.py`

The comparison baseline is the 0.5.6 batch of 09-27..30 (log lines 1-21424).

## What 0.7.0 fixed (measured)

| Lever | Before (0.5.6) | Now (0.7.0) |
|---|---|---|
| Session orientation, launch → planning | ~8 min (09-27 session 1) | ~45 s (15:11:11 → 15:11:58, `autopilot enter`) |
| Subagent full-suite runs | Tess/Ivan/Devon ran the 4-min suite repeatedly (part of 72 runs) | 0 by subagents; ~9 by the orchestrator, all gate runs |
| `release-checks` wall time | ~4 min | ~2 min (parallel, 4 workers) |
| Rework fix tier | opus-floor fixes 71-118 min each (00223) | 00241's rework session ran on sonnet, $13 |
| Pat per-task review | correction retries common | 12 s, no retries seen |
| PRD wall time, build → done | 00215: 8h36m; 00223: ~15h | 00240: 51 min; 00241: 3h24m |

The two PRDs aren't the same size, so the last row is a signal, not proof.

## What still costs time

### B1. A build orchestrator delegated the whole work phase to a subagent (new, off contract)
- **What happened:** on 00242 (7 opus-tier tasks) the sonnet/medium build
  session wrote "I'll delegate the entire Phase 3 work execution to an agent"
  and dispatched `Agent · Execute work phase …`. That agent dispatched Tess as
  a sub-subagent. The harness then forced it to hand back mid-task ("the
  harness forced an immediate handback"), and the orchestrator dispatched a
  second "Resume" agent.
- **Rule broken:** `work/SKILL.md` forbids this ("If you find yourself
  writing an Agent prompt that mentions multiple tasks, STOP"). Planning and
  design were also delegated, to "Plan" and "Design" agents.
- **Risks:** the context-cap hook, the task-boundary handoff and the dispatch
  telemetry all assume the session itself runs `/autopilot:work`. A nested
  agent can't hand off a session, and its context isn't the one the cap hook
  measures.
- **Damage this time:** none. The next session (20:17) ran `/work` correctly.
- **Lever:** a PreToolUse guard in loop mode that denies an `Agent` call
  whose prompt invokes or paraphrases `/autopilot:work`, `/autopilot:plan-tasks`
  or `/autopilot:design-solution` (the skill must run in the session), plus
  one prose line in `phase-build.md` Phase 2/3.
- **Watch:** whether medium effort makes this more likely. It is the first
  time it was seen, and the first batch at medium build effort.

### B2. PRD acceptance criteria force per-task `release-checks` runs (authoring)
- **What happens:** most per-task full runs now come from the orchestrator
  meeting task acceptance lines like "`bash dev/bin/release-checks` green". I
  wrote those into 00230-00244 myself.
- **Cost:** about 2 min each; several per PRD, on top of step 7's single
  final run.
- **Lever:** in create-prd (the agent-skills repo), task Acceptance names the
  task's own tests; `release-checks` appears only in the last phase's exit
  criteria.

### B3. The orchestrator still trips aegis's coreutils block
- **Count:** 41 blocks in 5.4 active hours, 27 of them by the orchestrator
  (`cat … | jq`, `rg … | head`). Each costs a round trip.
- **Lever:** the loop's launch prompt already carries one CLI sentence. Add
  one more: "Never call `cat`/`head`/`tail`/`grep`/`find`; use Read, `rg`,
  and `jq <file>`."

### B4. gateguard's fact-forcing gate fires on first edits in unattended runs
- **Count:** 28 in 5.4 h, spread across Ivan, Tess, Devon and the
  orchestrator. Each forces a "present facts" turn before the edit proceeds.
- **Lever:** aegis already has backlog PRD 00003 ("exempt autopilot loop from
  style hooks"). Schedule it in aegis.

### B5. Two review cycles per PRD remain the norm (observation)
00240 converged in one cycle; 00241 needed two. Each review still mints
triage stubs: 00245-00247 so far. No lever proposed, since review depth is a
standing rule.

## Suggested follow-ups

1. **B1:** a small autopilot PRD (a loop-mode `Agent` guard plus prose).
   High value, because it protects every other contract.
2. **B3:** a one-line change to the launch prompt (autopilot).
3. **B2:** a create-prd rule edit in agent-skills.
4. **B4:** schedule aegis 00003.
