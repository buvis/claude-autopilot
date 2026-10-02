Drain the claude-autopilot backlog in parallel worktrees (wave 1), then release 0.5.3 and 0.5.4.

Plan of record: `dev/local/notes/backlog-finish-plan-2026-09-20.md` (read it first, whole file).
Decisions already taken, do not re-open: five lanes in parallel now, L5 merges last; you
implement through Agent-tool subagents with worktree isolation and integrate yourself;
00194 T3-T4 is hand-finished inside L1; no `autoclaude` runs in this repo this week. The loop
runs only for the validation batch in agent-skills, after 0.5.4.

## Context you need

- The measured pathologies each PRD fixes: `dev/local/notes/autoclaude-inefficiencies-2026-09-13.md`
  (findings 1-16; 14, 15, 16 have no PRD and land as part of L3, L2, L2).
- PRDs: `dev/local/prds/backlog/00195-*.md` through `00202-*.md`, `00204-*.md` through
  `00206-*.md`; `dev/local/prds/wip/00194-*.md` (T1-T2 committed, T3-T4 open; state.json
  names it, tasks 3 in_progress, 4 pending).
- A first hand patch is parked as `git stash` stash@{0} ("loop-blockers hand patch"): rule 12
  in the Tess prompts, the step-2.8 style gate sentence, the Devon prose-skip paragraph, the
  foreground-Pat paragraph, the stand-down basename filter, the two `unknown` rules in the cap
  hook (`_handle_below_cap`, `_fire_breach`) with two tests in `test_autopilot_cap_rotation.py`,
  two new prose test files, CHANGELOG lines and a release-checks block. It is green except
  `test_work_skill_body_stays_under_the_500_line_ceiling` (work SKILL.md at 502 lines): the
  step-2.8 sentence must live in a reference with a read-first pointer. Hand each lane its
  hunks with `git stash show -p stash@{0} -- <paths>`; do not `stash pop` on master.
- `master` is 102 commits ahead of `origin/master`; the release pushes need the user's SSH
  agent (1Password prompt). If the session cannot reach it, do the local release steps and
  ask the user to push.

## Lanes

Create one worktree per lane from the current master, one implementing subagent per lane
(Agent tool, `isolation: "worktree"` or a plain `git worktree add ../claude-autopilot-l<n> -b lane/<name>`),
model opus. Give each agent: its PRD paths (absolute, under this checkout's `dev/local`, which
the worktree does not carry), its file-ownership list, its stash hunks, the shared-file rules,
and the stop rule (every PRD's named tests green, the full suite of every touched file green,
one conventional commit per task with the `(00XXX Tn)` suffix, then report the commit list).

| Lane | Branch | PRDs in order | Owns |
|------|--------|---------------|------|
| L1 cap-hook | lane/cap-hook | 00200, 00196, then 00194 T3-T4 | `skills/run-autopilot/scripts/autopilot_context_cap_hook.py` and its tests, `tracon/model.py` cap mirror, `skills/run-autopilot/references/{phase-build,phase-review,recovery,state-schema}.md`, `cli/frontmatter.py` (`session_model`), plan-tasks step 4.7 text, work `SKILL.md` step 6.5 only |
| L2 work-skill | lane/work-skill | 00197, 00202, findings 15 and 16 | work `SKILL.md` steps 2.8-2.95 (spill mechanics to a reference to stay under 500 lines), `skills/work/references/{tess-prompt,tess-retry-prompt,adversarial-test-prompt,per-task-review}.md`, `skills/work/scripts/test_*_prose.py` |
| L3 loop-cli | lane/loop-cli | 00199, 00201, finding 14 | `skills/run-autopilot/cli/{loop,loop_decision,loop_act,loop_gates,pause,brief,statectl}.py` and tests, run-autopilot `SKILL.md` § Session Loop and stand-down, `cli/golden/` |
| L4 review | lane/review | 00198, 00195 | `skills/review-work-completion/scripts/consolidate_findings.py` and tests and fixtures (durable copies in `dev/local/notes/00198-fixture-reviewer-outputs-00186/`), `agents/{alice,blake,carl}.md`, `references/agent-invocation.md`, finalize hold-stub prose in `phase-done.md` and `cli/records.py` |
| L5 effort-lanes | lane/effort-lanes | 00204, 00205, 00206 | `cli/lane.py` and tests, run-autopilot `SKILL.md` Phase 0 routing, `skills/fast-track/*`, plan-tasks lane frontmatter |

Shared-file rules for every lane (put them in every agent prompt verbatim):

- `CHANGELOG.md`: append at the END of the right `[Unreleased]` subsection only.
- `dev/bin/release-checks`: append one `echo "[checks] <lane>"` block at the END.
- Never touch `dev/local/`, `state.json`, or a file another lane owns; a needed line in
  another lane's file goes into the commit message for the integrator.
- Bug fixes show the regression test failing once against the pre-change code.
- Tool discipline: `cat`/`head`/`tail`/`grep`/`find` are hook-blocked, use Read and `rg`; one
  command per Bash call, no pipes or `&&`; new files trip a fact-forcing gate (name the caller,
  prove no duplicate with `rg --files`, then retry); `wip` is not a commit type.

## Review per PRD

Workflow rule: `/autopilot:review-work-completion` in a fresh session, every lens, never from
the implementing session. In the lane's worktree, copy ONE PRD to
`<worktree>/dev/local/prds/wip/` (two trip the ambiguous-target guard; no `state.json` there,
so it takes the standalone path), then run

```bash
CLAUDE_UNATTENDED=1 claude -p --permission-mode auto --model 'claude-opus-5[1m]' "/autopilot:review-work-completion"
```

Unattended mode writes `dev/local/reviews/<prd>-review-1.md` in the worktree and stops. The
lane agent fixes every CRITICAL and HIGH, one re-review (cap 2), Medium and Low go under a
`### Deferred` heading appended to the PRD. At most three reviews running at once; read the
`rate_limit_event` lines in the session output and stop launching at 70% of the seven-day
window.

## Integration and release

1. Merge order: L3, L1, L2, L4 (rebase each onto the current master first; CHANGELOG and
   release-checks conflicts are both-added, keep both). Run `bash dev/bin/release-checks` on
   master after each merge.
2. `dev/bin/release patch` -> 0.5.3 (runs release-checks, stamps CHANGELOG, bumps
   `.claude-plugin/plugin.json` and the claude-plugins marketplace, tags, pushes both repos).
3. Move 00194-00202 to `dev/local/prds/done/`; close the loop state with
   `python3 skills/run-autopilot/scripts/statectl.py dev/local/autopilot/state.json complete-prd`
   for 00194 (read `statectl.py --help` first) and archive `state.json` the way the loop's
   drained-backlog step does, so no stale batch survives.
4. L5 rebases onto the 0.5.3 master, runs its three reviews, merges; `dev/bin/release patch`
   -> 0.5.4. Move 00204-00206 to `done/`.
5. Remove the worktrees and lane branches once merged.

## Resume rule (this prompt is re-runnable)

On start, before cutting anything: `git worktree list`, `git branch --list 'lane/*'`,
`git tag --list 'v0.5.*'`, and `ls dev/local/prds/done/ | rg '^00(19|20)'`. A lane branch that
exists is resumed by a new agent in its worktree from its last commit; a merged lane is
skipped; an existing tag means that release is done. Never redo a step whose artifact exists.

## Report

End with the standard handoff block: per lane the commits, review verdicts and deferrals; the
two release versions with tags; what is not done and what closes it. Then the single next
action: `autoclaude` in agent-skills on 0.5.4 for the validation batch (00052 plus
00053-00057), measured against the 0.5.2 baseline in the plan.
