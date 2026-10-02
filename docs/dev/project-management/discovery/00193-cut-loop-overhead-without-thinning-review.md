# Discovery: Cut loop overhead without thinning review

## Classification
Depth: standard | Date: 2026-09-07

Source: `dev/local/notes/autopilot-efficiency-assessment-2026-09-07.md`
(knobs 1-4 and the orientation brief) with the per-session evidence in
`dev/local/notes/batch-waste-2026-09-06.md`. Yields three sequenced PRDs:
(1) loop guard rails in `cli/loop.py`, (2) handoff budget, placement and the
orchestrator-model split in `work` and `cli/routing.py`, (3) the session
orientation brief in `run-autopilot`. The effort-lane classifier (solo
session / fast-track / full loop) is a separate comprehensive discovery.

Sequencing against the backlog as of 2026-09-07 16:00 (00186-00192 were
filed after this doc's evidence was gathered, none gated):
- PRD 1 (loop guard rails) lands after 00192 (`split cli/loop.py and
  test_loop.py under the file cap`): both edit `loop.py`, and 00192 moves the
  decision table into new modules, so PRD 1's locations are the post-split
  ones. create-prd re-grounds the line references at write time.
- PRD 2 (handoff budget and placement) lands after 00191 (`clear the
  handoff marker at phase edges`), which removes the marker at the
  build→review edge; PRD 2 keeps that and adds the headroom rule and the
  after-`task-done` ordering. Its `session_model` half is independent.
- 00186 (item-grained fast-track lane), 00188 (convergence cap and roster
  per PRD) and 00189 (stall to split on plan expansion) are inputs to the
  lane-classifier discovery, not to this one.

## Problem

Two batches (claude-autopilot 202609061630, agent-skills 202609050909)
drained 18 PRDs between 2026-09-05 19:42 and 2026-09-07 07:20 for $1,236 of
recorded API cost, 53% of it review sessions and 45% build. Roughly half of
the total bought no assurance: about 40 extra sessions from context-pressure
handoffs and done→build hops, each paying 25-50 orientation tool calls and a
Phase 0 re-entry; opus orchestrator sessions on the three PRDs whose authors
pinned `default_model: opus` ($283 of $556 build); about 17 idle hours from
three usage-window exhaustions, a lid-close sleep that the connectivity poll
counted as 1800 s of outage, and a stand-down that fired on a monitoring
session; and ~$60 of dead or lost sessions, including an implementor killed
mid-task when the overage ran out. None of these touch what the review
lenses check; they are the loop's own overhead, and every one recurs on
every batch.

## Requirements

### Must have

PRD 1, loop guard rails (`skills/run-autopilot/cli/loop.py` and siblings):

- The API-unreachable poll in `Loop._decide_no_progress` measures awake
  time (`time.monotonic()` or a probe count), never wall-clock, so a machine
  sleep cannot exhaust `_AUTOPILOT_NET_WAIT_MAX`; on wake the poll continues
  where it left off and the session relaunches when `_probe_api()` succeeds.
- The loop holds `caffeinate -i` (a child process for the loop's lifetime,
  skipped with one stderr line when `caffeinate` is absent) so idle sleep
  never starts during a batch; a closed lid still sleeps the machine and the
  loop resumes on wake.
- At a `rate_limit_event` with `status: allowed_warning` in the session
  stream, the loop lists `~/.claude/autopilot-loops/*.json` and, when it is
  not the live loop with the oldest `started_at`, waits until that event's
  `resetsAt` before launching its next session; `usage_limit.detect_from_log`
  gains the warning parse beside its rejected parse.
- A `rejected` event never enters overage: the loop sleeps to `resetsAt`
  regardless of `overageStatus`, with the existing `_AUTOPILOT_LIMIT_WAIT_MAX`
  bound.
- The stand-down rule (run-autopilot SKILL.md § Stand-down procedure) asks
  before pausing: Phase 0 messages the busy interactive peer (`SendMessage`,
  bounded wait of about two minutes) and pauses only when the peer claims the
  PRD or a commit in the last 15 minutes was authored from that peer's
  session; a peer that only reads never pauses a batch. `pause.py`'s
  `stand_down_reason` records which condition fired.
- Every new behaviour has a unit test with an injected clock and a fake
  registry (`loop.py` already takes `clock=` and `detect_limit_fn=`).

PRD 2, handoff budget, placement and the orchestrator model (`skills/work`,
`scripts/autopilot_context_cap_hook.py`, `cli/routing.py`):

- The context-cap hook requests a handoff only when the headroom below
  `USAGE_CAP` is smaller than the usage the last completed task consumed
  (usage at task start is recorded in state by the hook at `task-start`; the
  first task of a session uses a fixed estimate), instead of the flat
  `SOFT_CAP = 320_000`; the hard-cap rotation is unchanged.
- The work skill honours `.handoff-requested` only in step 6.5, after the
  `task-done` write has landed; a marker seen earlier is carried to 6.5,
  never acted on between the commit and the state write (00182 handed off
  with task 1 committed but `in_progress`, and the next session had to
  reconcile by reading git).
- `default_model:` keeps its documented meaning (the per-task tier floor
  read by plan-tasks) and stops driving `routing.build_model`; a new
  frontmatter key `session_model: sonnet | opus` (default sonnet, parsed by
  Phase 0 like the other six keys) sets the orchestrator session model. The
  other promotion signals (replan, stall, cap rotation, rescue ledger,
  deferred stall) still promote the session to opus.
- `loop-metrics.jsonl` rows record the session model they ran at (already
  present as `model`) so the change is measurable batch to batch.

PRD 3, session orientation brief (`skills/run-autopilot`):

- Every gate transition writes `dev/local/autopilot/session-brief.md`: repo
  root, batch id, current PRD and phase, the state summary (cycle, tasks
  done/total, pending rework ids), the contract card, and the list of the
  reference files the next phase needs, each with a one-line reason.
- Every headless session reads the brief first: the loop passes its path in
  the launch prompt, and `/autopilot:run-autopilot` Phase 0 opens with it,
  skipping the reference reads the brief already answers.
- Measured by the watch counters: the first ten tool calls of a resumed
  session touch at most the brief, `state.json` and the PRD.

### Nice to have

- Fold the done→build hop into the finalize session: the review→done
  session selects the next PRD itself, saving one session ($1-1.8, 2-3 min,
  one Phase 0) per PRD.
- The loop's stop line names the yield reason ("waiting for reset 10:00,
  loop 32044 holds the budget") so tracon shows why a batch is idle.

### Out of scope

- Any change to which lenses run, how many review cycles run, or the review
  prompts (the standing rule: every lens, every cycle).
- Hook-block reduction in prompts (backlog PRD 00184) and review-rerun
  effort (backlog PRD 00185).
- The effort-lane classifier and its solo lane (separate discovery).
- Phase recomposition beyond the brief and the optional hop fold (task-close
  pass merging Pat, deslop and the style gate; design proportional to PRD).
- The aegis `prefer_tools` hook itself (another repo).

## Constraints

- Every review lens keeps running every cycle; nothing here touches the
  review phase.
- Python only for hooks and loop code; no new dependencies; `caffeinate` is
  optional and detected with `shutil.which`.
- Existing `_AUTOPILOT_*` env knobs keep their meaning; new behaviour is
  additive and each has a kill-switch env var in the wrapper's idiom.
- The batch runs the installed plugin cache, so these PRDs cannot self-harm
  and take effect only after `dev/bin/release` + `/plugin update`.
- Acceptance is deterministic: unit tests with injected clocks and fake
  registries, prose contract tests under `skills/<skill>/scripts/test_*.py`,
  and ledger rows; never wall-clock or cost.

## Codebase Context

- **Relevant code**:
  - `skills/run-autopilot/cli/loop.py`: `_decide_no_progress` (l.765-858)
    is the branch-5 decision: stand-down via `pause.stand_down_reason`,
    limit via `usage_limit.detect_from_log` + `wait_decision` (bounded by
    `_AUTOPILOT_LIMIT_WAIT_MAX`, 21600), network outage via `_CONNECTION_FAIL`
    (l.72) with `deadline = self._clock() + net_max` (l.807) and `self._clock`
    defaulting to `time.time` (l.456, l.469); `_probe_api` (l.429); the
    loop registry under `~/.claude/autopilot-loops/<pid>.json` with `pid`,
    `root`, `ap_dir`, `started_at`.
  - `skills/run-autopilot/cli/usage_limit.py`: `_rejected_reset` (l.149)
    reads only `status == "rejected"`; `detect_from_log` (l.167) prefers the
    event over the prose banner; `wait_decision` (l.194).
  - `skills/run-autopilot/cli/pause.py`: `stand_down_reason` (l.20),
    `stamp_paused`, `clear_paused`; the marker is `pause-requested`.
  - `skills/run-autopilot/cli/routing.py`: `build_model` (l.168) returns
    OPUS on `_frontmatter_pins_opus` (l.83, `default_model: opus`), state
    signals (replan, stall, cap rotations), the rescue ledger key, or a
    deferred stall; `route` (l.195) applies `_AUTOPILOT_MODEL_BUILD` first.
  - `skills/run-autopilot/scripts/autopilot_context_cap_hook.py` (installed
    0.5.1): `USAGE_CAP = 500_000` (l.77), `SOFT_CAP = 320_000` (l.84),
    `_request_handoff` writes `.handoff-requested` one-shot per task
    (l.442), `_latest_usage_total` reads the transcript (l.193), state
    writes go through `_write_via_transaction` (l.322).
  - `skills/work/SKILL.md` step 6 (`task-done`, l.452-457) then step 6.5
    (l.459-463) and `references/task-boundary-handoff.md` (marker removal,
    contract card, `leave` handoff row, `next_phase: "build"`, STOP).
  - `skills/run-autopilot/SKILL.md`: § Resuming (l.106), § Stand-down
    procedure (l.166), § Contract card (l.196-207: `contract-card.md`
    written at gate transitions, loaded with `statectl set-contract-card`,
    re-injected after compaction by the host hook
    `~/.claude/hooks/reinject_contract_card.py`, matched to `compact` only;
    the brief needs a `startup` match for loop sessions, which lives in the
    host hooks, not this repo).
  - `skills/run-autopilot/cli/runner.py`: the child spawn; `LAUNCH_ENV` and
    (after PRD 00181) the host-marker scrub.
- **Conventions**: loop behaviour is code in `cli/` with pytest under
  `cli/test_*.py` and `scripts/test_*.py`; skill policy is prose pinned by
  contract tests; env knobs are `_AUTOPILOT_*` read through `self._int` /
  `env.get`; markers are files in `dev/local/autopilot/`; frontmatter keys are
  parsed by Phase 0 with silent defaults (`cli/frontmatter.py`).
- **Integration points**: `loop.py` (poll clock, caffeinate child, warning
  yield, overage rule), `usage_limit.py` (warning parse), `pause.py` (reason
  detail), SKILL.md § Stand-down (ask-first rule), the cap hook (headroom
  rule, task-start usage record), work SKILL.md step 6.5 and
  `task-boundary-handoff.md` (placement), `routing.py` + `frontmatter.py` +
  `references/state-schema.md` (`session_model`), run-autopilot SKILL.md and
  `phase-build.md` (session brief write and read), `records.py` per-PRD
  reset list if the brief path is stored in state.

## Success Criteria

- `uv run --no-project --with pytest python -m pytest -q skills/run-autopilot/cli`
  green with new tests: a poll that survives a simulated 2 h clock jump; a
  younger loop that yields at `allowed_warning` and an oldest loop that does
  not; a `rejected` event with `overageStatus: allowed` that still sleeps;
  `build_model` returning SONNET for a PRD that pins `default_model: opus`
  and OPUS for `session_model: opus`.
- A prose contract test pins the ask-first stand-down text, the step-6.5
  ordering sentence and the brief-first Phase 0 sentence.
- Cap-hook tests: no `.handoff-requested` while headroom exceeds the last
  task's usage; the marker appears once it does not.
- Post-release signals, not judged in-session: the next batch's
  `loop-metrics.jsonl` shows no `died` row with detail `API unreachable`
  across a sleep, no `paused` row whose `stood_down` reason names a reader,
  no session at opus for a PRD without `session_model: opus` or a promotion
  signal, and fewer `build→build` rows per PRD than tasks.

## Risks

- **A longer session hits the hard cap**: the headroom rule keeps taking
  tasks while they fit; the existing hard-cap rotation stays as the
  backstop, and the first-task estimate errs high.
- **caffeinate on battery**: a plugged-out laptop drains faster during a
  batch; the loop prints that it holds the assertion, and
  `_AUTOPILOT_NO_CAFFEINATE=1` disables it.
- **Peer that never answers**: the ask-first stand-down waits a bounded
  time, then continues unless a writer commit is present; a real collision
  with a silent writer still shows up as that commit.
- **Oldest-loop rule starves a newer batch**: the newer loop idles until
  the reset; the stop line and tracon say why.
- **`session_model` drift**: `default_model: opus` PRDs already in the
  backlog (00183 is in flight) silently lose the opus orchestrator; the
  release note says so and the gate flags pins.

## Open Questions

- Should the yield rule also apply at the seven-day window's warning, or
  only to the five-hour window? (Default: five-hour only; seven-day is a
  reporting signal.)
- Where should the first-task usage estimate come from: a constant, or the
  median of the previous PRD's tasks from the ledger?

## Discovery Log

### Inferred: What triggers this need?
**Answer**: measured, not preventive. 18 PRDs over 31 h on two repos cost
$1,236 recorded; about half bought no assurance: ~40 extra sessions from
context-pressure handoffs and hops (25-50 orientation tool calls each), opus
orchestrator sessions on author-pinned PRDs ($283 of $556 build), ~17 idle
hours from usage windows, a lid-close and a false stand-down, ~$60 of dead or
lost sessions, and ~800 hook-blocked tool calls.

### Q1: How should the five items be packaged?
**Answer**: Three sequenced PRDs, each inside one subsystem: (1) loop
environment guard rails in `cli/loop.py`; (2) handoff placement, soft-cap
budget and orchestrator-model decoupling in `work` and `cli/routing.py`; (3)
the session orientation brief in `run-autopilot`.

### Q2: What should the loop do about sleep and battery?
**Answer**: Monotonic poll plus caffeinate. The connectivity poll in
`loop.py` `_decide_no_progress` measures elapsed awake time (`time.monotonic`
or a probe count), so sleep no longer burns the `_AUTOPILOT_NET_WAIT_MAX`
budget; the loop holds `caffeinate -i` for its own lifetime so idle sleep
never starts during a batch; a closed lid still sleeps the machine and the
loop resumes on wake. Rejected: refusing to start on battery (the lid-close
case was on battery; unplugging mid-batch would still kill it).

### Q3: What should a loop do at `allowed_warning` or a `rejected` with overage available?
**Answer**: Yield if another loop is registered. At `allowed_warning`
(utilization >= 0.9 in the session's `rate_limit_event` stream) the loop
reads `~/.claude/autopilot-loops/*.json`; if it is not the oldest live loop
it waits until `resetsAt` before launching its next session. A `rejected`
event never enters overage: the loop sleeps to the reset regardless of
`overageStatus`. The oldest loop keeps the budget. Rejected: keeping today's
behaviour (the overage allowance was consumed overnight and a hard stop
followed).

### Q4: What should the stand-down rule become?
**Answer**: Ask the peer, pause only on a writer. Phase 0 sends the busy
interactive peer a message and continues unless the peer claims the PRD
within a bounded wait (about 2 min) or a commit in the last 15 min was
authored from that peer's session; a monitoring session never pauses a
batch. Rejected: a cool-off auto-resume (retries against a real collision
every half hour) and an owner marker file (interactive entry points rarely
write it).

### Q5: Where does the effort-lane classifier live?
**Answer**: A separate discovery at comprehensive depth (solo session /
fast-track / full loop, decided from PRD features with an author override).
This discovery stays the three no-risk PRDs.

### Q6: What should the handoff budget rule be?
**Answer**: Headroom rule plus placement fix. The context-cap hook
(`scripts/autopilot_context_cap_hook.py`, `SOFT_CAP = 320_000`,
`USAGE_CAP = 500_000`) requests a handoff only when the headroom left below
the hard cap is smaller than the usage the last completed task consumed
(measured from the transcript; a fixed estimate for the first task), and the
work skill honours the marker only after `task-done` has landed. Rejected:
raising the constant (wrong for both tiny and huge tasks) and placement
only (keeps one task per session).

### Q7: Decouple the orchestrator session model from the task floor?
**Answer**: Yes: add `session_model: sonnet | opus`, default sonnet;
`default_model:` keeps flooring the subagent tiers and stops driving
`routing.build_model`; the other promotion signals still promote the
session. Rejected: gate-only (ungated PRDs keep the multiplier) and keeping
today's coupling ($283 of $556 build spend from three pinned PRDs).

### Inferred: Success criteria, constraints, priority
**Answer**: deterministic checks (unit tests with injected clocks, prose
contract tests, ledger rows), as PRDs 00157 and 00177 set; every lens keeps
running; Python hooks, no new dependencies, additive env knobs; lands in the
next claude-autopilot batch after the current one drains.
