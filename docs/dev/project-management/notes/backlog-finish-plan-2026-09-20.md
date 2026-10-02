# Finish the claude-autopilot backlog in parallel worktrees, then validate (2026-09-20)

## Where we are (measured 2026-09-20 12:35 CEST)

- Weekly cap hit 2026-09-15 04:07 CEST at 100% after about 40 loop-hours; it reset today at
  11:00 CEST. No loop is running. `master` is 102 commits ahead of `origin/master`.
- Two loops spent about $2,765 in two days (claude-autopilot $1,773, agent-skills $992); the
  week before, about $2,255 in three days. The weekly cap is roughly $2,500-3,000 of
  API-equivalent spend and the loop eats it in two days.
- Delivered but NOT released: 00186-00192 and 00194 T1-T2. The installed plugin is still
  0.5.2, so none of it is running.
- Remaining: 00194 T3-T4 (two mechanical tasks), 00195-00202 (8 fix PRDs, 1,490 lines),
  00204-00206 (3 lane PRDs, 1,362 lines, Opus).
- Loop cost per PRD on 0.5.2: $68 / 1.8 h (00190, Sonnet), $135 / 3.5 h (00191), $182 / 3.2 h
  (00192, Opus with design), $109 for half of 00194. A loop drain of the 11 remaining PRDs is
  $1,400-1,900 and 30-40 hours, one full weekly cap, with nothing left to validate.
- Why: the loop's own pathologies (inefficiencies note, findings 1-16) are exactly what the
  backlog fixes. Paying the loop to fix the loop is the slow path.
- A first hand patch (findings 14, 15, 16, PRD 00197, the two `unknown` rules of 00200) is
  parked in `git stash` (stash@{0}, "loop-blockers hand patch"). It is green except
  `test_work_skill_body_stays_under_the_500_line_ceiling` (SKILL.md 502 lines): the new
  step-2.8 sentence has to move to a reference. Lane agents cherry-pick from it.

## Principle

Implement the backlog attended and in parallel: one git worktree per non-conflicting lane,
one implementing agent per lane, the same review roster per PRD in a fresh headless session,
one integrator (me) merging in a fixed order. The loop runs nowhere until validation.

## Lanes (wave 1, all in parallel)

Lanes are cut by shared files, so no two lanes edit the same file. Inside a lane the PRDs
run serially in the order given.

| Lane | Branch | PRDs (in order) | Files owned | Est. wall / cost |
|------|--------|-----------------|-------------|------------------|
| L1 cap-hook | `lane/cap-hook` | 00200, 00196, then 00194 T3-T4 | `skills/run-autopilot/scripts/autopilot_context_cap_hook.py` + its tests, `tracon/model.py` mirror, `skills/run-autopilot/references/{phase-build,phase-review,recovery,state-schema}.md`, `cli/frontmatter.py` (`session_model`), `skills/plan-tasks` step 4.7 text, work `SKILL.md` step 6.5 only | 2.5 h / $60 |
| L2 work-skill | `lane/work-skill` | 00197, 00202, findings 15 and 16 | `skills/work/SKILL.md` steps 2.8-2.95 (and the reference it spills into to stay under 500 lines), `references/{tess-prompt,tess-retry-prompt,adversarial-test-prompt,per-task-review}.md`, `skills/work/scripts/test_*_prose.py` | 1.5 h / $40 |
| L3 loop-cli | `lane/loop-cli` | 00199, 00201, finding 14 | `skills/run-autopilot/cli/{loop,loop_decision,loop_act,loop_gates,pause,brief,statectl}.py` + tests, run-autopilot `SKILL.md` § Session Loop and stand-down, `cli/golden/` | 2.5 h / $60 |
| L4 review | `lane/review` | 00198, 00195 | `skills/review-work-completion/scripts/consolidate_findings.py` + tests + fixtures, `agents/{alice,blake,carl}.md`, `references/agent-invocation.md`, finalize/hold-stub prose in `phase-done` references and `cli/records.py` | 1.5 h / $40 |
| L5 lanes | `lane/effort-lanes` | 00204, 00205, 00206 | `cli/lane.py` + tests, run-autopilot `SKILL.md` Phase 0 routing, `skills/fast-track/*`, `plan-tasks` lane frontmatter | 4 h / $120 |

Shared-file rules for every lane:

- `CHANGELOG.md`: append entries at the END of the right `[Unreleased]` subsection only. The
  integrator resolves the resulting both-added conflicts by keeping both.
- `dev/bin/release-checks`: append one `echo "[checks] <lane>"` block at the END of the file.
- Never touch `dev/local/` (worktrees do not carry it), `state.json`, or another lane's files.
  If a PRD needs a line in another lane's file, write it in the commit message and the
  integrator applies it at merge.
- Every PRD's named tests green, plus the full suite of every file touched. Bug fixes show the
  regression test failing once against the pre-change code (rules/testing.md).
- Conventional commits, one per task, `(00XXX Tn)` suffix as the loop does.

## Worktree mechanics

```bash
git -C ~/git/src/github.com/buvis/claude-autopilot worktree add ../claude-autopilot-l1 -b lane/cap-hook
# same for l2..l5
```

Each lane gets one implementing agent (Agent tool, `isolation: worktree`, or a plain
`claude` in the worktree if you prefer to watch it). The agent's prompt carries the absolute
paths of its PRDs under the main checkout's `dev/local/prds/backlog/`, the stash hunks it may
reuse (`git stash show -p stash@{0}` in the main checkout), the file-ownership list above, and
the stop rule: green tests, committed, then report.

## Review per PRD (fresh session, full roster, in the lane's worktree)

The workflow rule wants `/autopilot:review-work-completion` in a fresh session, all lenses.
A worktree has no `dev/local`, so it takes the standalone path: copy the one PRD under review
to `<worktree>/dev/local/prds/wip/` (one at a time; two wip PRDs trip the ambiguous-target
guard), then run

```bash
CLAUDE_UNATTENDED=1 claude -p --permission-mode auto --model 'claude-opus-5[1m]' "/autopilot:review-work-completion"
```

in the worktree. Unattended mode writes the findings file and stops. The lane agent fixes every
CRITICAL and HIGH, re-runs the review once (cap 2, like the loop), and Medium/Low go to a
`### Deferred` list in the PRD before it moves to `done/`. About $15-40 per review; run at most
three reviews at once so the five-hour window keeps headroom.

## Integration order and release

1. Merge L3, then L1, then L2, then L4 into `master` (rebase each onto the current master
   first; L3 before L1 because both touch run-autopilot `SKILL.md`, L2 before L4 because L2
   owns the work skill). Resolve CHANGELOG and release-checks by keeping both.
2. `bash dev/bin/release-checks` on master, then `dev/bin/release patch` -> 0.5.3 (your SSH,
   two pushes: repo tag and claude-plugins marketplace bump; origin is 102 commits behind).
3. Move 00194-00202 to `dev/local/prds/done/`, archive `dev/local/autopilot/state.json`
   (`statectl complete-prd` for 00194, then the loop's own archive step) so no stale batch
   state survives into the next `autoclaude` here.
4. L5 rebases onto the 0.5.3 master, runs its three reviews, merges, release 0.5.4.

## Validation (day 2, one loop only)

`autoclaude` in agent-skills on 0.5.4: 00052 plus 00053-00057. Measure against the 0.5.2
baseline from 09-13/14: $/PRD, wall hours/PRD, sessions/PRD, rotations/PRD, review cycles,
sessions lost to stand-down or death. Bar: under $60 and under 1.5 h per small PRD, zero lost
sessions. ddb has no `dev/local/prds/` yet; it needs `/elicit-requirements` before it can be a
target, so it follows the agent-skills numbers.

## Budget and timeline

- Wave 1: five agents in parallel, 3-4 h wall, about $320 implementation + $250 reviews +
  $100 fixes = about $700, versus $1,700 through the loop.
- Release 0.5.3 tonight; L5 and 0.5.4 tomorrow morning; validation batch tomorrow.
- Weekly reserve after wave 1: about $2,000 of the cap, enough for the agent-skills batch and
  a second look at ddb.

## Unresolved questions

1. Run L5 (the lane PRDs, the biggest and most conflict-prone) in wave 1 beside the four fix
   lanes, or start it only after 0.5.3 is out?
2. Implementers: Agent-tool subagents from this session (I watch all five), or five `claude`
   sessions you open in the worktrees yourself?
3. 00194 T3-T4: hand-finish inside L1 and close its loop state with `statectl complete-prd`
   (recommended), or let `autoclaude` finish it first and pause the loop at its finalize?
