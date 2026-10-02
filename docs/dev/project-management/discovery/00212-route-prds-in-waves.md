# Discovery: Route PRDs in waves

## Classification

Feature discovery for the autopilot plugin (run-autopilot), elicited 2026-09-21
from two measured drains: the sequential `autoclaude` loop on agent-skills
(0.5.4 validation batch) and the hand-run wave on claude-autopilot
(`dev/local/notes/backlog-finish-plan-2026-09-20.md`, report in
`backlog-finish-report-2026-09-20.md`). Depth: comprehensive, because the change
touches the loop's core assumption (one PRD, one `state.json`, one checkout).

## Problem

The loop drains a backlog one PRD at a time, and each PRD is itself a chain of
sessions (build, review cycle, rework resume, finalize). Measured 2026-09-20/21
on agent-skills with 0.5.4: 4.5 PRDs in 10.7 h and $527 (22 sessions; review
sessions were 74% of the spend). The same day, five hand-run lanes in worktrees
(one implementing subagent per lane, one fresh headless review session per PRD,
one integrator) delivered 11 PRDs of this repo's backlog in ~9 wall-hours for
~$1,200 including all reviews. Per PRD that is ~$110 and ~50 minutes of wall
against ~$117 and ~2.4 h through the loop, with the wave's cost dominated by
review sessions too. The wave did not make the work cheaper; it removed the
serial wall-clock and most of the per-session re-orientation (the loop paid a
full catchup or a brief plus state reads at every hand-off), and it let one
operator watch five lanes at once.

Nothing in the plugin can run that wave today: `cli/loop.py` assumes one
`dev/local/autopilot/state.json` in one checkout, `references/phase-build.md`
Phase 0 selects the lowest PRD only, and the assembly (rebase, conflict
resolution, integrator lines, release checks) has no owner but the operator.

## Requirements

### Must have

1. **Wave cutting by file ownership.** A wave is a set of PRDs whose named paths
   do not overlap; PRDs that share a path go into the same lane, in backlog
   order. The path sets come from `cli/lane.py`'s named-path extraction (PRD
   00204), plus the shared-file rule set of the 2026-09-20 plan: `CHANGELOG.md`
   and `dev/bin/release-checks` are append-only and never make two PRDs
   conflict.
2. **One lane, one worktree, one state.** Each lane gets `git worktree add
   ../<repo>-l<n> -b lane/<slug>` from the current default branch and its own
   `dev/local/autopilot/` (state, ledger, brief, markers) inside that worktree,
   so every existing phase, hook and cap runs unchanged per lane. The lane's
   PRDs run serially through the ordinary loop inside the worktree.
3. **Lane sessions are loop sessions.** A lane driver launches the same
   `claude -p` sessions the loop does today, with the same routing
   (`cli/routing.py`), the same hooks (cap, stand-down filter, leave-row guard)
   and the same per-PRD review roster in fresh sessions. No lens is thinned in
   a lane.
4. **Assembly session.** After every lane of a wave has closed its PRDs (done or
   parked), an opus session in the main checkout merges lanes in a fixed order
   (the plan's rule: lanes that touch the core skill files first), rebasing
   each onto the current head, resolving `CHANGELOG.md` and `release-checks`
   as both-added, applying every `Integrator:` trailer from lane commits, and
   running `bash dev/bin/release-checks` after each merge. A merge that leaves
   a non-trivial conflict (same-line edits outside the append-only files)
   stalls the lane with a new `site: "assembly_conflict"` and the operator
   finishes it.
5. **Assembly review.** One `review-work-completion` pass over the assembled
   diff (the merge range, not the per-PRD diffs) before the wave closes, with
   the standard roster; a CRITICAL or HIGH here creates a rework task in the
   main checkout's ordinary loop, never a silent fix.
6. **Ledger merge.** Each lane's `loop-metrics.jsonl`, `dispatch-metrics.jsonl`
   and deferred records are appended to the main batch's ledger at assembly
   with a `lane` field, so the batch report's per-PRD sections and Run
   conditions lines render as today, plus a `- Wave:` line naming the lane.
7. **Review-slot semaphore.** A wave never runs more than N review sessions at
   once (default 3), shared across lanes, so the five-hour window keeps
   headroom; the semaphore is a directory of slot files, the way the
   2026-09-20 run did it.
8. **Fence and guards per worktree.** The write-scope fence
   (`enforce_write_scope.py`) and the hooks resolve the autopilot dir by
   walking up from the session's cwd (they already do), so a lane session in
   `../repo-l2` sees only its own state; the stand-down peer filter keys on the
   repository basename, so `repo-l2` sessions must count as the same
   repository as `repo` (strip the `-l<n>` suffix, or key on the git common
   dir).

### Nice to have

- `autoclaude wave` as the operator entry (plan the wave, print the lane
  table, launch the lane drivers, assemble), with `autoclaude wave status`
  rendering all lanes on one screen (tracon per lane is out).
- A wave planner that proposes the cut and lets the operator edit it before
  launch (the 2026-09-20 plan was written by hand and that step was the
  valuable one).
- Lane-local `session_model`/effort overrides in the wave plan.

### Out of scope

- Parallelism inside one PRD (parallel tasks): the work skill's task graph is
  serial by design and its rework mode already parallelizes independent fixes.
- Cross-repo waves.
- Replacing the sequential loop: `autoclaude` stays the default; `wave` is a
  second entry that reuses the loop per lane.

## Constraints

- Every existing prose pin on the loop (`test_loop_prose.py`,
  `test_custody_prose*.py`, the phase files) keeps passing: the lane driver
  wraps `autopilot loop`, it does not fork it.
- The review-per-PRD rule (`~/.claude/AGENTS.md` § Workflow) is not thinned:
  every PRD in a lane gets its fresh-session roster, and the assembly diff gets
  one more.
- No new dependency; worktrees are plain git.
- The 500K cap and the 1M window are unchanged per session.

## Codebase Context

- `cli/loop.py`, `loop_decision.py`, `loop_act.py`, `loop_gates.py`: the
  session loop, one state file, `DEFAULT_LOOPS_DIR` registry with a
  one-loop-per-repo guard (`live_wrapper_pid`) that a wave must relax to
  one-loop-per-worktree.
- `cli/lane.py`: named-path extraction and the effort-lane classifier (PRD
  00204); the path sets are the wave planner's input.
- `references/phase-build.md` Phase 0: PRD selection (lowest in wip, then
  backlog); a lane needs "select from my lane's list only", which is a
  `dev/local/autopilot/lane.json` allowlist read at selection.
- `hooks/`: `guard_skill_after_leave.py`, `note_session_leave.py` (PRD 00211),
  the push guard; all resolve the autopilot dir from cwd.
- `dev/bin/release-checks`, `CHANGELOG.md`: the append-only shared files; the
  2026-09-20 assembly resolved every both-added conflict by keeping both and
  every same-line conflict by hand (`state-schema.md` rows, `records.py`
  comment, `schema.py` enums, one rewritten changelog bullet).
- `scratchpad/rebase-keep-both.sh`, `changelog_to_unreleased.py`,
  `review-slot.sh` from the 2026-09-20 session: throwaway versions of the
  assembly helpers and the semaphore.

## Approach

1. **Plan**: `autopilot wave plan` reads the backlog, extracts each PRD's path
   set (`lane.py`), builds lanes by connected components over shared paths
   (append-only files excluded), orders PRDs inside a lane by number, prints
   the lane table (the 2026-09-20 plan's table shape: lane, branch, PRDs, owned
   paths) and writes `dev/local/autopilot/wave.json`. The operator edits it or
   accepts it.
2. **Launch**: for each lane, `git worktree add`, copy the lane's PRDs into the
   worktree's `dev/local/prds/backlog/`, write `dev/local/autopilot/lane.json`
   there, and start `autopilot loop` in that worktree with the wave's slot
   semaphore path in the environment. The registry guard keys on the worktree
   path.
3. **Drain**: each lane runs the ordinary loop to "backlog drained" (or park).
4. **Assemble**: the assembly session merges lanes in the plan's order with the
   keep-both rule, applies `Integrator:` trailers, runs release-checks after
   each merge, runs the assembly review, merges ledgers, moves the PRDs to the
   main `done/`, removes worktrees and lane branches.
5. **Release**: the ordinary `dev/bin/release`.

## Success Criteria

- A five-lane wave over a synthetic backlog (fixture PRDs with disjoint paths)
  drains in one `wave` run with every PRD reviewed by the standard roster and
  the assembly review, and the batch report renders one section per PRD plus
  the wave line.
- Wall-clock per PRD under 1 h on a real backlog of small PRDs (0.5.4 loop:
  2.2 h mean), at the same or lower $/PRD.
- Zero lost sessions, zero cross-lane state writes (a lane never touches
  another worktree's `dev/local`).

## Risks

- **Assembly conflicts outside the append-only files**: measured on 2026-09-20
  as six same-line conflicts across 88 commits; the stall-and-hand-over rule
  keeps them safe but each costs operator time. Mitigation: the planner treats
  `references/state-schema.md`, `SKILL.md` and `cli/records.py` as shared
  files that force PRDs into one lane.
- **Rate limits**: five lanes x (build + review) can exhaust the five-hour
  window; the semaphore bounds reviews, not builds. Mitigation: a lane-count
  cap tied to the window's `allowed_warning` (PRD 00199's yield already reads
  it).
- **Two loops in one repo**: the registry guard was built to prevent exactly
  this; relaxing it per worktree must keep the same-checkout duplicate guard.

## Open Questions

1. Lane cutting: classifier path sets alone, or the operator names lanes (as on
   2026-09-20) with the classifier only checking disjointness? The hand-cut
   plan was better than any path-set component would have been (it split by
   skill ownership, not by file).
2. Assembly review: one pass over the whole merge range (cheap, one session) or
   the full roster with two cycles (the rule's letter)? The merged diff was
   already reviewed per PRD; the assembly adds conflict resolutions and
   integrator lines only.
3. Where does a lane's parked PRD go: the lane worktree's `hold/` (lost when
   the worktree is removed) or the main checkout's (needs a move at assembly)?
4. Does a wave need its own batch id, or is it one batch with a `wave` field?
