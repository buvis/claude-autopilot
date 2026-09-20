# Solo lane runbook

The procedure Phase 0 step 5.5 (`references/phase-build.md`) follows when
`state.lane_effective == "solo"`: a PRD that names no production path (docs,
prose, tests, config) builds in this one session, takes one zero-context
review pass, and closes without the review-rework loop. Phases 1 to 3 do not
run for this PRD. Every decision that could let an unreviewed production
change close as done is made by code (`autopilot lane-check`) or read off the
review table, never by this session's judgment of its own work. Six steps, in
this order; the section that stops the lane says so.

The session runs at `session_model` (default sonnet) or a promotion signal
(`references/state-schema.md` § Build-Session Model Promotion Signals);
`default_model` is inert in solo, which dispatches no implementor.

## 1. Mirror

Capture `work_start_sha` and `repo_root` (and `git_dir` for a bare-repo
root) first, on every entry, exactly per the Phase 3 invariants (core
`SKILL.md` § Phase 3 invariants; `references/phase-build.md` § Phase 3):
once per PRD, only when unset, with the empty-tree sentinel when
`git rev-parse HEAD` fails. A re-entry (a context-cap rotation, a died-retry
relaunch) that finds them set leaves them alone; one that finds them unset
captures them now, before any task runs.

Then mirror the PRD's task lines idempotently: `task-add` does not
deduplicate, so a re-entry must not double the task list. Mirror every
`- [ ]` line of the PRD whose text is not already the `name` of a task in
`state.tasks`, one `task-add` per such line, so tracon and the task counts
stay live; a first entry mirrors them all, a re-entry after a crash between
two `task-add` calls mirrors only the lines still missing, and a re-entry
with a complete mirror mirrors nothing and goes to step 2 at the first task
whose `status` is not `completed`.

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/skills/run-autopilot/scripts/statectl.py dev/local/autopilot/state.json task-add <task-json-file>
```

Write each `<task-json-file>` with the Write tool as `{"name": "<the task
text>"}` and nothing else: no `model` key, so `tasks[i].model` is
legacy-absent (`skills/plan-tasks/SKILL.md` step 4 is the payload contract).
Capture the printed id per task.

## 2. Implement

Per task, in order:

1. `python3 ${CLAUDE_PLUGIN_ROOT}/skills/run-autopilot/scripts/statectl.py dev/local/autopilot/state.json task-start <id>`.
2. Implement the task yourself with the Read, Edit and Write tools: no
   subagent, no Ivan or Tess dispatch, no shell rewrite (`sed`, heredocs).
   This is the micro lane of `work/references/rework-mode.md` generalized to
   a whole PRD.
3. Where the task names a test, write the test first and watch it fail once
   (one Bash call per test command) before the change that makes it pass.
4. Run the acceptance commands the task names, each as its own Bash call,
   and paste their result into the task's commit body when they are the
   proof.
5. Stage exactly the PRD's named paths the task touched, plus `CHANGELOG.md`
   when the change earns an entry (`rules/changelog.md`), and commit in
   conventional form (`<type>(<scope>): <subject> (<prd number> T<n>)`).
   A dirty path the PRD never named is foreign: leave it unstaged and name
   it in the report.
6. `task-done` with the attempt record written to a file with the Write
   tool:

   ```json
   {"attempt": 1, "model": "<state.session_model or \"sonnet\">", "outcome": "completed", "review_cycle": null, "cause": null, "implementor": "orchestrator", "preflight_outcome": null, "pipeline": "solo"}
   ```

   `orchestrator` is the existing no-dispatch value
   (`references/state-schema.md` `tasks[].attempts` row); `solo` joins the
   `pipeline` vocabulary.

   ```bash
   python3 ${CLAUDE_PLUGIN_ROOT}/skills/run-autopilot/scripts/statectl.py dev/local/autopilot/state.json task-done <id> <attempt-json-file>
   ```

The soft handoff marker `.handoff-requested` is not read by this runbook: a
solo PRD fits one session by construction, and the hard cap of
`autopilot_context_cap_hook.py` is the backstop. The session is
`phase: "build"` with a task in progress, so the cap and its tripwire apply
unchanged, and a rotation resumes by artifact at the first non-completed
task (Phase 0 finds `state.lane_effective == "solo"` and re-enters here).

## 3. Suite

After the last task, run the repo suite once under
`${CLAUDE_PLUGIN_ROOT}/skills/work/references/final-verification.md` and
write `dev/local/autopilot/last-verification.json` per its § Recorded
verification result (`sha`, the commands, the three counts). A red suite
here is fixed in-session as its own task-shaped commit before step 4; a suite
that stays red is the `suite_red` signal below.

## 4. Escalation checks

Code decides whether the finished build may take the single review pass:

```bash
autopilot lane-check --state dev/local/autopilot/state.json
```

It reads `state.work_start_sha`, `state.repo_root`, `state.git_dir` and
`state.lane`, runs `git diff --name-only <work_start_sha>..HEAD` and
`git diff <work_start_sha>..HEAD` through `custody.git_argv`, and checks in
order:

- `unnamed_path` — any changed path is a hook path (`lane.is_hook_path`) or
  a production path (`lane.is_production_path`). A solo PRD named none, so
  any is unnamed.
- `security_diff` — `lane.security_triggered(diff, changed_files)` fires on
  a security-ish changed path or an added or removed line (the Python port
  of `review-fanout.workflow.js`'s `securityTriggered`).
- `check_failed` — a git command failed. The check fails toward the
  expensive lane, never toward `ok` (the `_AUTOPILOT_AGOGE_AUTHORIZED`
  principle, core `SKILL.md`).

Exit 0 prints `lane: ok` and step 5 runs. Exit 3 prints
`lane: escalate <signal>` after one transaction writing
`lane_effective: "full"` and `lane_escalated: {"from": <state.lane>, "signal": <slug>}`;
go straight to step 6's escalation exit. Exit 2 (state unreadable or
`work_start_sha` unset, reason on stderr) is a lane bug: fix the state per the
Phase 3 invariants and re-run the check; never skip it.

`autopilot lane-check --state <path> --signal <slug>` records a signal the
session determined from the review table or the suite instead of the diff:
`critical_finding`, `high_unresolved`, `suite_red` or `review_failed`
(step 5). It writes the same two fields and exits 3.

The check runs again, without `--signal`, after every commit step 5's
disposition lands: a fix commit moves HEAD, and a fix that touches a
production path or adds a security-ish line must escalate exactly as the
build would have.

## 5. Review

One zero-context review of the whole range, under fast-track's consensus
rule verbatim (`skills/fast-track/SKILL.md` § Roster): the `review-fanout`
workflow when `~/.claude/workflows/review-fanout.workflow.js` is on disk,
else the `autopilot:alice` subagent. Inputs: the PRD, `git diff
<work_start_sha>..HEAD` (saved with the Write tool to
`dev/local/tmp/<prd-stem>-solo.diff`), the changed-file list, the
review-work-completion rubric
(`${CLAUDE_PLUGIN_ROOT}/skills/review-work-completion/references/rubric.md`)
and `references/output-formats.md` § Agent Output Format. Render Alice's
prompt from `${CLAUDE_PLUGIN_ROOT}/agents/alice.md` the way fast-track
renders its consensus lane; on the workflow backend the `Workflow` tool call
takes the same args fast-track passes. Save the returned text to
`dev/local/tmp/solo-output-<prd-stem>.txt`.

The review must have happened before its table means anything:
`consolidate_findings.py` reads a missing, empty or malformed output file
as `No issues found`, so check the saved text first. Alice's output holds at
least one `[ALICE]` line and all twelve `R{n}: pass|fail` verdict lines (the
workflow backend: its consolidated table with a `Verdict:` line), and every
`[ALICE]` line is either the exact all-clear `[ALICE] ✅ No issues found`
or a finding line carrying `| File:` and `| Task:` (the consolidator's own
`_LINE_RE`; a line it cannot parse is dropped without a word, which is how
`[ALICE] 🟠 broken check` would converge a PRD). When the text fails any of
that, dispatch the same reviewer once more; when the retry fails it too, the
sole review failed and the PRD escalates with `--signal review_failed`
(step 4), never converges on an empty table. Only then build the table, and
check that its row count equals the number of finding lines (the all-clear
line counts zero):

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/skills/review-work-completion/scripts/consolidate_findings.py alice:$PWD/dev/local/tmp/solo-output-<prd-stem>.txt
```

(the workflow's own consolidated table stands in for it on that backend).
Save the table to `dev/local/tmp/<prd-stem>-solo-table.md` with the Write
tool and run the disposition below over it. The review file itself is
written in step 6, after the disposition, so an escalated pass never leaves
a `-review-1.md` behind for the full lane's cycle 1 to mistake for its own.

The review file, `dev/local/reviews/<prd-stem>-review-1.md`, written with
the Write tool in the shape `cli/gate.py` checks
(`review-work-completion/references/review-coverage-format.md`):

```
---
head_sha: <git rev-parse HEAD>
reviewers: alice
---

## Alice

<the consolidated table, or the one-line all-clear>

Verdict: converged
Tests: N passed, M failed, K skipped (reused from last-verification.json at <sha>)
codex_rung_guard: not fired
```

`reviewers: fanout` with one `## Fanout` section holding the workflow's
consolidated table on the workflow backend. `Verdict: converged` when no
row survives, else `Verdict: N findings` (N = surviving rows of any
severity). The `Tests:` line is composed as `review-work-completion`
composes it (its step "Compose the `Tests:` line"): from
`last-verification.json` when its `sha` is HEAD, or `Tests: none (docs-only)`
when every changed path is a doc. `codex_rung_guard: not fired` always: no
codex-implemented task exists in this lane.

### Disposition

What the session does with each severity in the table, in this order:

- A CRITICAL escalates with `--signal critical_finding`; no fix is
  attempted.
- A HIGH or MEDIUM inside the PRD's named paths gets one in-session fix
  (Read, Edit, Write; one commit `fix(<scope>): ... (<prd number> review)`),
  the narrow checks the affected task named, and one delta dispatch of the
  same reviewer over `<fix-base>..HEAD` in fast-track's Delta shape
  (`skills/fast-track/SKILL.md` § Delta: capture `<fix-base>` as
  `git rev-parse HEAD` before the fix, then one Alice dispatch over that
  range with the confirmed findings listed). After the fix commit, run
  `autopilot lane-check` again without `--signal` (step 4): the fix moved
  HEAD. A HIGH still confirmed after the delta escalates with
  `--signal high_unresolved`; a suite that is red after the fix escalates
  with `--signal suite_red`. After the delta, rewrite the saved table so it
  reflects the delta's outcome: rows the delta confirmed fixed are removed,
  rows it raised on the fix are added; that updated table is what step 6
  writes.
- A HIGH outside the PRD's named paths escalates with
  `--signal high_unresolved` without a fix.
- A MEDIUM outside the PRD's named paths, and every LOW, is recorded in the
  file and never reworked.

On any escalation after the pass ran, write the table to
`dev/local/reviews/<prd-stem>-solo-pass.md` (a durable trail whose name
never matches the gate's `-review-*` glob in
`scripts/review_coverage_hook.py`, nor the convergence reader's
`-review-<n>`), never to `-review-1.md`, so the full lane's cycle 1 finds
no file and runs. `-review-1.md` is written only on the close exit of
step 6.

## 6. Close

Two exits, both through `autopilot phase-done`:

- **Escalation** (`lane-check` exited 3, in step 4 or through `--signal`):
  `autopilot phase-done --outcome tasks_done`, then the Session handoff
  procedure (core `SKILL.md` § Session Loop, build → review row). The full
  review gate takes the finished build with every lens and its rework
  cycles; no commit is lost. The report's `Lane:` line reads
  `full (classified solo, <reason>), escalated from solo: <signal>`.
- **Close** (`lane: ok` from the last `lane-check` and no escalating
  finding): first write `dev/local/reviews/<prd-stem>-review-1.md` from the
  saved table (updated with the delta's outcome when a fix ran) in the shape
  step 5 gives, then
  `autopilot phase-done --outcome lane_reviewed`, the `("build",
  "lane_reviewed")` row of `cli/transitions.py`, whose effect is
  convergence's: `phase`/`next_phase: "done"` and `"review"` appended once
  to `phases_completed`, so `review_coverage_hook.gate_blocks` checks the
  solo review file with `--require-codex-guard` exactly as it checks a
  full-lane cycle. Then the Session handoff procedure; the done session
  finalizes as today (`references/phase-done.md`).

Print, before ending the turn:

```
── AUTOPILOT ── PRD: {prd-name} ── solo lane: {reviewed|escalated <signal>} ──
```
