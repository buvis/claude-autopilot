# Is the autopilot loop wasteful, or just thorough? Assessment 2026-09-07

Evidence: 18 PRDs across two repos, 2026-09-05 19:42 to 2026-09-07 07:20,
read from `loop-metrics.jsonl` (cost and wall-clock per session) plus a
per-session watch of tool calls and hook blocks
(`dev/local/notes/batch-waste-2026-09-06.md` holds the rows). Costs are the
API `cost_usd` the loop records; counters are from a bash watch and are
approximate; the opus attribution uses the session `model` field.

## Verdict

The loop is not flawed in what it checks. It is flawed in that it checks the
same way regardless of what it is checking, and it sits on infrastructure
that leaks as much as the checks cost. Roughly half of the money bought
assurance you asked for; the other half bought nothing:

| where the money went (16 closed + 2 open PRDs, $1,236 recorded) | $ | share |
|---|---|---|
| review sessions (all cycles, all lenses, at opus) | 661 | 53% |
| build sessions | 556 | 45% |
| of which: opus-promoted builds (00017, 00183, 00044, part of 00178) | 283 | 23% |
| of which: sonnet builds, 14 PRDs | 273 | 22% |
| done→build hops | 19 | 2% |

Inside those numbers, the parts that are not quality-bearing:

- **Re-orientation per session.** Every session starts with 25-50 tool calls
  reading state, references and the PRD before doing anything. 22
  context-pressure handoffs plus 18 hops means ~40 extra sessions; at 10-15
  min and $3-15 each that is $100-200 and 8-10 hours of session time.
- **Opus on whole builds.** 00017, 00183 and 00044 carry `default_model:
  opus` in their own frontmatter (verified), so their builds ran at opus by
  author request; `routing.build_model` honours the pin and launches the
  orchestrator session at opus too. Each task then costs $15-46 instead of
  $2-10 (00183: $113 for four tasks; 00017: $128 for four tasks). One flag
  drives two things: the per-task floor for subagents, which is what
  create-prd's escalator table is about, and the orchestrator session model,
  which is where the $40 sessions come from. The per-task classifier already
  escalates risky tasks on its own.
- **The second review cycle as confirmation.** Cycle 2 sessions cost $10-42
  (avg ~$22) and in 5 of 8 two-cycle PRDs found exactly one 🟡 whose fix then
  shipped unverified because the cap is 2. Cycle 1 finds the real problems
  (rework in 14 of 16 PRDs, Highs included); cycle 2 mostly confirms.
- **Environment.** Three usage-window exhaustions in 31 h of joint running,
  overage credits drained, one lid-close that killed both loops for 8 h, one
  false stand-down that parked a batch for 8 h, and an in-flight implementor
  killed at the limit and redone from scratch ($40). About 17 idle hours and
  ~$60 of dead or lost sessions. Zero quality value.
- **Hook-blocked tool calls.** 4-30 per session, ~10 average, ~800 over the
  run: each is a model round trip that returns "use Read instead". Reviewer
  subagents are the worst offenders (16-30 per review session).
- **Ceremony floor.** A PRD with no rework still costs $22-23 and 36-40 min
  (00022, 00032). Half of that is the review panel reading a diff of a few
  dozen lines.

So: thoroughness explains the review share and the per-task pipeline. The
uniformity (every PRD gets the full shape), the session architecture (one
task per session under context pressure, orientation paid every time) and
the environment handling explain the rest. A 2-line runner change (00180)
cost $56 and 1.8 h; a 4-task prose PRD (00178) cost $91 and 7 h of session
time. The hand-built comparison (Codex, 00176, four review cycles) closed a
similar fix in 2h20m because one context did all of it.

## Where the assurance really comes from

Worth protecting, in order: fail-first tests per task (cheap, catches real
regressions); the cycle-1 panel with the blind lens (finds the Highs: 00178's
review found a real High that the build missed); the per-task style and
tautology gates (mechanical, cheap). Worth questioning: Devon rounds at opus
(00179 already capped them), the full second panel, opus for build, design
docs for small fixes (00044: a 45 KB design doc and $42 before a single task).

## Knobs (ranked by savings per unit of quality risk)

1. **Environment guard rails, no knob needed.** Serialize loops on one
   account or pause a loop at `allowed_warning` when another is running;
   measure the connectivity poll with a monotonic clock and wait through
   local outages instead of dying; refuse to start on battery without an
   override, or hold `caffeinate -i`; make the stand-down rule require a
   writer (recent commit from that session), not a present peer, and retry
   after a cool-off. Saves the idle hours and the lost sessions. Risk: none.
2. **Hook-block elimination** (backlog 00184 already): reviewer and
   implementor prompts carry the tool discipline, or the aegis hook rewrites
   `cat X` into a Read instead of blocking. Saves ~800 round trips per two
   days. Risk: none.
3. **Handoff placement and budget.** Never hand off between the commit and
   the `task-done` write (00182 did, and the next session had to reconcile);
   let a session finish N tasks before yielding when headroom allows, instead
   of one task per session. Saves a Phase 0 re-entry per task on the affected
   PRDs. Risk: a longer session hits the context cap; the cap hook exists.
4. **Decouple the orchestrator model from the task floor.**
   `default_model: opus` should floor the subagent tiers (its documented
   meaning) without also launching the build orchestrator at opus; a separate
   `session_model:` key, default sonnet, covers the rare PRD whose
   orchestration itself needs opus. Plus gate hygiene: the backlog gate
   questions an opus pin against create-prd's escalator table (00183 is a
   report-rendering PRD; 00044 a CI fix). Saves most of the $283 opus build
   share. Risk: a hard task lands on sonnet; the task classifier and the
   escalation ladder already cover that path, and the pin still floors it.
5. **Scoped later cycles.** Cycle N>1 keeps every lens (your standing rule)
   but reviews the rework diff plus the findings ledger, with prompts that say
   so, instead of re-reading the whole PRD surface. Knob: `rework_scope:
   diff | full`, default `diff`. Saves roughly half of each cycle-2 session.
   Risk: a regression outside the rework diff goes unseen until the next
   PRD's review; the final verification suite still runs.
6. **Assurance tier per PRD** (needs your decision, it thins the review):
   `assurance: full | standard | light`. `light` = one review cycle, 🟡
   findings deferred to a batch-end sweep, no Devon, no design. The backlog
   gate proposes the tier from PRD shape (prose-only, single file, no
   contract change → light). Would have cut 00179/00180/00181 by 40-60%.
   Risk: the standing rule says never thin the review; this is the one knob
   that does, and only for PRDs the gate marks as low-risk.

## Recomposition of phases

- **Orientation brief.** Write a per-batch `session-brief.md` at Phase 0
  (repo root, state summary, the five references this phase needs, the
  contract card) and have every session read that one file first. The
  biggest architectural saving: turns 25-50 orientation calls into 5.
- **Fold the done→build hop into the finalize session**: the review→done
  session already knows the batch; selecting the next PRD there saves one
  session per PRD (~$1.2, 2-3 min, and one more Phase 0).
- **One task-close pass**: per-task review (Pat), self-deslop and the style
  gate are three dispatches at the end of every task; one sonnet pass with
  the three rubrics would do.
- **Design proportional to the PRD**: the gate sets `design: skip` unless the
  PRD declares more than one module or a contract change; 00044's $42 of
  pre-work was frontmatter-driven.
- **Cycle structure**: cycle 1 full panel on the full surface; cycle 2 full
  panel on the rework diff (knob 5); no cycle 3 (already the cap).

Estimated effect, flagged as estimates: knobs 1-4 and the orientation brief
take ~25-30% off build cost and most of the calendar idle; knob 5 takes
~30-40% off review; the tier knob adds another 15-25% on small PRDs. Together
roughly 35-45% of recorded cost and more than half of calendar time, with
the quality-bearing parts (fail-first tests, cycle-1 panel, blind lens, final
verification) untouched.

## What I would do first

1. Knob 1 (environment) and knob 2 (hooks, PRD 00184): zero quality risk,
   largest calendar win. 2. Knob 3 (handoff bug and budget). 3. The
   orientation brief. 4. Knob 4 (promotion scope). 5. Knob 5 (scoped cycles).
   6. Only then decide on the tier knob, with the cycle-2 yield data above.

## What not to touch

Cycle-1 lens breadth, the blind lens, fail-first tests, the mechanical gates.
They are where the findings come from and they are cheap relative to the
opus review hours around them.
