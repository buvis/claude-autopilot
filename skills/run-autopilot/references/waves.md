# Waves (parallel lanes over one backlog)

A wave runs several autopilot loops at once, one per **lane**: a slice of the PRD
backlog whose PRDs name no overlapping paths. `docs/dev/project-management/autopilot/wave.json` is
the whole control surface - `cli/wave.py` plans it, `cli/wave_launch.py` launches,
reports and aborts it, and nothing else reads or writes it (its shape:
`references/state-schema.md` § Marker files). It is disposable at wave end,
together with `wave-slots/` (`SKILL.md` § Retention).

Run every verb from the main checkout. All of them but `status` hold an exclusive
lock on the sibling `wave.json.lock` for their whole body and reload `wave.json`
under it, so two operators cannot interleave.

## `autopilot wave plan [--max-lanes N]`

Cuts `docs/dev/project-management/prds/backlog/*.md` into at most N lanes (default 3) and writes the
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
   are left alone: it is still running. A group that exited between the liveness
   probe and the signal counts as killed - no escalation, no grace window spent -
   while a signal that could not be delivered at all (EPERM) leaves the lane
   running too, with the reason in its `abort_error`.
2. Move every PRD the lane still holds back into the main checkout: lane
   `backlog/` and lane `wip/` both land in the main `backlog/`, lane `done/` in
   `done/`, lane `hold/` in `hold/`. An in-flight PRD comes home to the backlog
   because a PRD sitting in the main `wip/` is re-selected as
   already-in-progress against a `state.json` that holds no task record for it.
   The folder a PRD sits in is the only thing that decides where it lands.
3. `git worktree remove --force` and `git branch -D` the lane's own worktree and
   branch.

Steps 2 and 3 are skipped, and the lane keeps its PRDs, when the worktree is not
this wave's to remove or holds work: this wave never recorded creating it, git no
longer has it checked out on the lane branch, the branch carries commits past
`base_sha`, or the worktree has uncommitted changes. Those PRDs are the only
record of what the lane was doing, so abort says where they are: for a worktree
git still has, it prints git's own `worktree list` line for it, branch and HEAD
sha included. A kept worktree git does not list gets one `autopilot:` line
carrying the path and the reason `git does not list it as a worktree`. A worktree
holding uncommitted changes gets a second line on top of its listing, the note
`autopilot: <n> uncommitted change(s), inspect before reusing this worktree`.

`wave-slots/` is kept only while a lane's process group survived its kill, because
that loop still reads it; every other outcome removes it, a worktree cleanup
failure with every group dead included. The wave ends `aborted` (exit 0) or
`abort_failed` (exit 1) with each failure recorded in the lane's `abort_error`,
where `wave status` shows it. A wave left `abort_failed` is still live, so
`wave plan` refuses to replace it until the abort is retried.

## `autopilot wave assemble`

Merges every drained lane back into one assembly branch off `base_sha`, in
`order` - the order `wave plan` assigned each lane, not wave.json's list
order. A lane merges only when it is drained (its `state.json`'s
`next_phase` is empty); a lane that is still live (a signalable pid) makes
the whole verb refuse before anything is created, and an unfinished lane (a
dead pid whose `state.json` still names a pending phase) is skipped, not
merged - it is kept for a later run. Each merge lands on the shared assembly
worktree `<repo>-wave-<wave id>`, on branch `wave/<wave id>/assembly`, and
`dev/bin/release-checks` runs there after every merge.

A lane's merge is undone and the lane is kept, instead of aborting the whole
pass, when its rebase conflicts outside the append-only files
(`CHANGELOG.md`, `dev/bin/release-checks`) or when `release-checks` fails
against the merged tree; either way the lane's status becomes `conflict` or
`checks_failed` and a stall deferred record (`site: assembly_conflict`,
`references/recovery.md`) is appended, naming the conflicting paths or the
check's exit code and stderr tail. For a `conflict` lane, its own branch and
worktree are left exactly as the lane left them - the rebase itself was
aborted. For a `checks_failed` lane, the lane's branch is retained, but it
was already rebased onto the newer assembly base before the merge and the
checks ran - only the shared assembly branch rewinds.

Exit codes: `0` when every drained lane merged clean, `3` when at least one
lane was kept (a conflict, a checks failure, or one still unfinished) - the
wave ends `assembled_partial` rather than `assembled` - and `1` when the
verb refuses outright (a live lane, a structurally invalid `wave.json`). To
finish a kept lane, rebase it by hand inside its own worktree (`<repo>-l<n>`)
against the assembly branch, resolve the conflict or fix whatever failed the
checks, then rerun `autopilot wave assemble` - it re-merges every lane not
yet `assembled`, in the same order.

## What a lane worktree holds

`<repo>-l<n>`, beside the main checkout, is a full autopilot workspace of its own:

- its own git checkout, created at the wave's `base_sha`, on its own branch
  `wave/<wave id>/l<n>`.
- its own `docs/dev/project-management/prds/` lifecycle dirs (`backlog/`, `wip/`, `done/`, `hold/`),
  holding that lane's PRDs and nothing else. `launch` MOVES them out of the main
  checkout's `backlog/`, so exactly one checkout owns a PRD at any moment.
- a copy of `docs/dev/project-management/meta/` (the project capsule and its siblings), so the lane
  starts catchup from the same curated memory.
- its own detached autopilot loop: spawned with the lane worktree as cwd, in its
  own session (so it survives the launching shell), logging to the lane's
  `docs/dev/project-management/autopilot/wrapper.log`, registered as the incumbent loop for that
  root. The lane's `state.json`, reviews, designs and ledgers all stay inside the
  lane.

## Review and land

### `autopilot wave review`

Runs one review cycle over the wave's assembly worktree (`<repo>-wave-<wave
id>`, on branch `wave/<wave id>/assembly`): seeds a nested autopilot loop
there, spawns it and blocks until it converges or fails, then reloads
`wave.json` fresh under lock and returns `"converged"` or `"review_failed"` -
it persists that outcome to `wave.json`'s `status` field itself, so a caller
never saves after calling it. Raises `ValueError` when the wave's state does
not meet the precondition for a review pass, propagated rather than caught,
like every other precondition check in this pack.

**Scope note.** The review runs only over the paths the wave's assembled
lanes actually touched: `review_paths(wave)` writes that scoped list to
`docs/dev/project-management/autopilot/review-paths`, one repo-relative path
per line, and the nested loop's `gather-context.sh` filters on it instead of
gathering the whole repo.

### `autopilot wave land`

Fast-forwards the main checkout onto the wave's assembly branch once review
has converged, then migrates and cleans up. Reloads `wave.json` fresh under
its own lock - a `wave` dict passed to it is used only to match the call
signature. Returns `4` when the wave's status is `review_failed` (no git
write). An operator who hand-reviewed a `review_failed` assembly and moved
its stub PRD to the assembly worktree's `prds/done/` can rerun `land`: it
finds the stub there, sets the wave's status to `converged`, and lands
normally instead of returning `4` again. Returns `5` when it is `converged`
but the main branch has moved since the wave was planned (no git write -
land refuses rather than force anything). Returns `0` once landed. Raises
`ValueError` if the status is neither `converged` nor `review_failed`.

## wave run

`autopilot wave run [--max-lanes N] [--review-slots N] [--yes]` chains every
step above into one call: `plan`, `launch`, a wait loop that reloads
`wave.json` and polls every 30s until every lane's pid reads dead (printing
the status table every 10 minutes of elapsed wall time), `assemble`,
`review`, and - only once review reports `converged` - `land`. A
`--review-slots` value other than 3 (the planned default) is written into
`wave.json` right after `plan`, before `launch` starts any lane.

The review spawn itself is wrapped in a `wave_slots.acquire`/`release` pair,
so at most `_AUTOPILOT_REVIEW_SLOTS` review sessions run at once (default
`3`), with the slot pool held under the directory named by
`_AUTOPILOT_REVIEW_SLOTS_DIR`.

It refuses before touching anything (exit `1`, a precondition refused) when
run with no controlling tty and without `--yes` - an unattended wave needs
the flag spelled out, same as any other one-shot destructive step. Past that
gate, `plan`'s and `launch`'s own exit-`1` refusals surface unchanged, and
nothing later in the chain runs.

SIGINT or SIGTERM during the wait loop kill every still-running lane's
process group directly - the same per-lane kill routine `wave abort` uses,
not `abort` end-to-end, so an interrupted wave keeps its PRDs where they sit
instead of handing them back - mark the wave `interrupted` in `wave.json`,
and exit `130`. A later `autopilot wave assemble` against that same
`wave.json` resumes from there exactly like any other assemble call; the
interrupt needs no special handling on the resume path.

Exit codes:

| Exit | Meaning |
|------|---------|
| `0` | the wave landed |
| `1` | a precondition refused - the `--yes` gate, or `plan`/`launch`'s own refusal |
| `3` | assemble kept a lane (a conflict, a checks failure, or one left unfinished) - the rest of the chain still ran to completion on what did merge |
| `4` | review failed |
| `5` | master moved between the confirmation gate and land |

The final code is the last non-zero code the chain produced, in the order
the steps ran: a kept lane (`3`) followed by a clean review and land still
reports `3`, but a kept lane whose review then fails reports `4` instead.

An `autoclaude wave` alias for `autopilot wave run` exists at the
operator-shell layer, outside this PRD's scope: a one-line dotfiles change,
`caffeinate -is python3 "$_skill/cli/__main__.py" wave run "$@"`.

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
