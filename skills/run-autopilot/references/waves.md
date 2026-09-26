# Waves (parallel lanes over one backlog)

A wave runs several autopilot loops at once, one per **lane**: a slice of the PRD
backlog whose PRDs name no overlapping paths. `dev/local/autopilot/wave.json` is
the whole control surface - `cli/wave.py` plans it, `cli/wave_launch.py` launches,
reports and aborts it, and nothing else reads or writes it (its shape:
`references/state-schema.md` § Marker files). It is disposable at wave end,
together with `wave-slots/` (`SKILL.md` § Retention).

Run every verb from the main checkout. All of them but `status` hold an exclusive
lock on the sibling `wave.json.lock` for their whole body and reload `wave.json`
under it, so two operators cannot interleave.

## `autopilot wave plan [--max-lanes N]`

Cuts `dev/local/prds/backlog/*.md` into at most N lanes (default 3) and writes the
cut as a `planned` wave. Two PRDs share a lane when they name the same path, when
one names a directory the other names a file under, or when both name a
force-shared file (operator note 1 below). `CHANGELOG.md` and
`dev/bin/release-checks` never join two lanes: every PRD appends to them, so they
are dropped before the comparison. A PRD that names no paths at all is **held
back** - recorded under `held_back` as `no named paths`, left in the main backlog
for the sequential loop, never given to a lane.

Groups are packed largest first, one per lane while lanes remain, then onto the
lane holding the fewest PRDs. Lanes are numbered core-touching first (most core
paths first, where core means a force-shared file or anything under
`skills/run-autopilot/cli/` or `skills/run-autopilot/references/`), so the lane
most entangled with the pack's core is `l1`. Lane `l<n>` gets branch
`wave/<wave id>/l<n>` and worktree `<repo>-l<n>` beside the repo. The plan is
printed, one block per lane plus the held-back list.

It refuses with exit 1 and writes nothing when `wave.json` is unreadable or not
valid JSON, when it is structurally invalid, when the wave it holds is still live
(any status but `done` or `aborted` - abort that one first), or when `--max-lanes`
is below 1.

`wave.json` is a supported hand-edit surface between `plan` and `launch`: move a
PRD to another lane, drop a lane, fix a path. `launch` re-checks the whole file
before it creates anything.

## `autopilot wave launch`

The wave's one destructive step. Every check runs before anything is created, and
each refusal is exit 1 with the reason on stderr:

- `wave.json` is structurally invalid (malformed or missing fields, two lanes
  sharing an order/name/branch/worktree, a PRD in two lanes, a worktree or branch
  off the canonical name for its order, a wave planned for another repo).
- the main checkout's tree is dirty (commit or stash first).
- a loop is already running on the main root - the refusal names its pid.
- the wave is not `planned` any more.
- the plan has drifted from the backlog as it stands NOW: a lane's PRD has left
  `backlog/`, a PRD now names no paths, or two lanes would share a path. The
  re-derivation is the point of the hand-edit surface above.

Then it stamps `base_sha` and `base_branch` from the main checkout's HEAD, marks
the wave `running`, and walks the lanes in order. `wave.json` is saved once the
lane's worktree exists and again once its loop is up, so a later lane's failure
still leaves an accurate record of the earlier ones.

## `autopilot wave status`

Read-only: no lock, and neither `wave.json` nor any lane is touched. Prints a
header row and one row per lane - `lane`, `pid`, `prd`, `phase`, `next_phase`, the
four lifecycle counts (`backlog`, `wip`, `done`, `hold`), `phase_end`, `signal`,
`status`, `abort_error`. The PRD, phase and counts are read from the lane's own
`state.json`, PRD folders and `ledger/loop-metrics.jsonl`; the pid, status and
`abort_error` come from `wave.json`, so they survive a worktree that is gone.

Liveness beats the stored status: a live pid reads `running`, and a dead one is
told apart by the lane's own `state.json` - `drained` when its `next_phase` is
empty (the lane finished its PRDs), `unfinished` otherwise (the loop died with
work left). An empty cell prints `-`.

## `autopilot wave abort`

Stops the wave and gives the PRDs back. It refuses to touch a structurally
invalid `wave.json` (exit 1). Otherwise, per lane in order:

1. SIGTERM the lane's process group (`pid` IS the group id - the loop was spawned
   as its own session leader), wait up to 60 s, then SIGKILL and wait 10 s more. A
   group that outlives SIGKILL keeps its pid and `running` status and its files
   are left alone: it is still running.
2. Move every PRD the lane still holds - `backlog/`, `wip/`, `done/`, `hold/` -
   back into the main checkout's matching folder.
3. `git worktree remove --force` and `git branch -D` the lane's own worktree and
   branch.

Steps 2 and 3 are skipped, and the lane keeps its PRDs, when the worktree is not
this wave's to remove or holds work: this wave never recorded creating it, git no
longer has it checked out on the lane branch, the branch carries commits past
`base_sha`, or the worktree has uncommitted changes. The reason is printed - those
PRDs are the only record of what the lane was doing.

`wave-slots/` is removed only once every lane finished, because a lane that
survived its kill still reads it. The wave ends `aborted` (exit 0) or
`abort_failed` (exit 1) with each failure recorded in the lane's `abort_error`,
where `wave status` shows it. A wave left `abort_failed` is still live, so
`wave plan` refuses to replace it until the abort is retried.

## What a lane worktree holds

`<repo>-l<n>`, beside the main checkout, is a full autopilot workspace of its own:

- its own git checkout, created at the wave's `base_sha`, on its own branch
  `wave/<wave id>/l<n>`.
- its own `dev/local/prds/` lifecycle dirs (`backlog/`, `wip/`, `done/`, `hold/`),
  holding that lane's PRDs and nothing else. `launch` MOVES them out of the main
  checkout's `backlog/`, so exactly one checkout owns a PRD at any moment.
- a copy of `dev/local/meta/` (the project capsule and its siblings), so the lane
  starts catchup from the same curated memory.
- its own detached autopilot loop: spawned with the lane worktree as cwd, in its
  own session (so it survives the launching shell), logging to the lane's
  `dev/local/autopilot/wrapper.log`, registered as the incumbent loop for that
  root. The lane's `state.json`, reviews, designs and ledgers all stay inside the
  lane.

## Deferred: assembly and review slots

Not part of this release:

- **Assembly** - merging the lane branches back into the base branch - is PRD
  00215. Today a wave's output is N branches, each with its lane's commits; you
  merge them yourself, or `wave abort` keeps any branch that carries commits
  rather than deleting it.
- **The review-slot semaphore** is PRD 00216. `launch` already points every lane
  at one shared directory (`_AUTOPILOT_REVIEW_SLOTS_DIR` =
  `dev/local/autopilot/wave-slots` in the main checkout) and passes the wave's
  `review_slots` count, but nothing throttles concurrent review launches yet.

## Operator notes

**1. `WAVE_FORCE_SHARED` is this repo's own list.** The three paths it names -
`skills/run-autopilot/SKILL.md`, `skills/run-autopilot/references/state-schema.md`
and `skills/run-autopilot/cli/records.py` - are the files two PRDs edit at once
often enough that the cut refuses to split them across lanes: any two PRDs that
each touch one of the three are pulled into a single lane. In any other repo those
paths do not exist, so the constant is a no-op and the cut falls back to plain path
overlap.

**2. Do not start a main-checkout loop after `launch`.** A loop started in the main
checkout matches lane sessions as stand-down peers only by `basename "$PWD"` prefix
(a lane's cwd is `<repo>-l<n>`, which starts with the repo's basename), so its
Phase 0 pays one `SendMessage` plus a wait of up to 120 s for every lane session.
It never actually stands down: the lanes own PRDs disjoint from the main
checkout's, and the stand-down needs a peer that claims this session's PRD. The
cost is pure - one hand-off delay per lane, every session - so drain the wave
first, or keep the main checkout's backlog empty while it runs.
