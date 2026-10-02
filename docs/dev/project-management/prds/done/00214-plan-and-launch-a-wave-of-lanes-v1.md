---
catchup: skip
design: run
default_model: opus
model_tier_rationale: the lane cut is an invented predicate over path sets, the launcher spawns detached loop drivers with the registry's own-pid tag, and the semaphore interleaves with the loop's spawn; three escalator rows hit
rework_cap: 2
---

# Plan and launch a wave of lanes

Source: `dev/local/discovery/00212-route-prds-in-waves.md` must-haves 1, 2, 3
and 8, open question 1 (2026-09-21). Grounded at `8885300` (0.5.5). First of
four: 00215 assembles a launched wave, 00216 reviews the assembly and adds the
one-shot `wave run`, 00217 adds the review-slot semaphore (must-have 7) whose
two variables this PRD already passes to every lane. The `autoclaude wave`
shell alias lives in the dotfiles, outside this repo, and follows the release.

## Overview

### Problem Statement

The loop drains one PRD at a time in one checkout: `cli/loop.py` anchors on the
autopilot dir above its cwd, `autopilot select` picks the lowest PRD from that
checkout's `wip/` then `backlog/`, and nothing cuts a backlog into lanes or runs
two loops side by side. The hand-run wave of 2026-09-20 (five worktrees, one
implementing agent per lane, a fresh-session review per PRD, one integrator)
delivered 11 PRDs in ~9 wall-hours against ~2.4 h per PRD through the loop at
the same $/PRD; its cut, worktree mechanics and review semaphore were all done
by hand (`dev/local/notes/backlog-finish-plan-2026-09-20.md`). This PRD makes
the plugin cut a wave and run one ordinary `autopilot loop` per lane, each in
its own worktree, with nothing in the loop, the hooks or the review roster
thinned.

Open question 1 of the discovery is decided here: the planner proposes the cut
from path sets, the operator edits `wave.json` before launch, and launch
validates disjointness.

### Target Users

The operator draining a backlog of independent PRDs on one machine.

### Success Metrics

- `uv run --no-project --with pytest python -m pytest -q skills/run-autopilot/cli/test_wave.py skills/run-autopilot/cli/test_wave_launch.py`
  green.
- `bash dev/bin/release-checks` green (the two files form a new
  `echo "[checks] waves"` block appended at the end of the file).
- Post-release signal: a three-lane wave over a real backlog runs three loops
  whose `~/.claude/autopilot-loops/*.json` entries name three distinct roots,
  and the main `backlog/` holds only the held-back PRDs while they run.

## Functional Decomposition

### Capability: Wave planning
Cut a backlog into lanes whose named paths do not overlap.

#### Feature: Cut lanes by named paths
- **Description**: `autopilot wave plan [--max-lanes N]` proposes the lanes and
  writes `dev/local/autopilot/wave.json`.
- **Inputs**: every `dev/local/prds/backlog/*.md`; `cli/lane.named_paths(text)`;
  `--max-lanes` (default 3).
- **Outputs**: `wave.json` (shape below) and the lane table on stdout: lane,
  branch, PRDs in order, owned paths; then the held-back list.
- **Behavior**: a PRD's path set is `named_paths(text)` minus
  `WAVE_APPEND_ONLY = ("CHANGELOG.md", "dev/bin/release-checks")`. Two PRDs
  share a lane when a path of one equals a path of the other, when one path is
  a directory prefix of the other (`b.startswith(a + "/")`, either way round;
  `named_paths` never returns a trailing-slash directory, so this fires for a
  `- **Location**:` path written without one, e.g. `skills/x` against
  `skills/x/y.py`), or when both name a path in
  `WAVE_FORCE_SHARED = ("skills/run-autopilot/SKILL.md", "skills/run-autopilot/references/state-schema.md", "skills/run-autopilot/cli/records.py")`
  (the 2026-09-20 same-line conflict sources: every PRD naming one of them
  joins one lane). Connected components over that relation, then greedy packing
  into at most N lanes: largest component first into the lane with the fewest
  PRDs. A PRD with no named paths is held back (`held_back: [{"prd", "reason":
  "no named paths"}]`) and stays in `backlog/` for the sequential loop. Inside
  a lane PRDs keep sequence order. Lane order (`order` 1..n, the assembly
  order) puts lanes owning a `WAVE_FORCE_SHARED`, `skills/run-autopilot/cli/`
  or `skills/run-autopilot/references/` path first, more such paths first,
  ties by lowest PRD number. `name` = `l<order>`, `branch` =
  `wave/<id>/l<order>`, `worktree` = `<repo parent>/<repo basename>-l<order>`,
  `id` = `yyyymmddHHMM`. `plan` exits 1 when a `wave.json` whose `status` is
  neither `done` nor `aborted` exists. Between `plan` and `launch` the operator
  edits `wave.json` freely (move PRDs, merge lanes, reorder).

  `wave.json`: `{"id", "status": "planned", "repo", "base_branch": null,
  "base_sha": null, "review_slots": 3, "created_at", "lanes": [{"name",
  "order", "branch", "worktree", "prds": [...], "paths": [...], "status":
  "planned", "pid": null, "started_at": null}], "held_back": [...]}`.

#### Feature: Validate the cut at launch
- **Description**: `launch` re-derives every lane's path union from the PRDs'
  current text and refuses overlapping lanes.
- **Inputs**: `wave.json`, the PRD texts.
- **Outputs**: exit 1 naming the two lanes and the path, or silence.
- **Behavior**: the sharing rule above, applied pairwise across lanes; a PRD
  listed in `wave.json` but absent from `backlog/` is also a refusal. Nothing
  is created before validation passes.

### Capability: Lane launch
One worktree, one autopilot dir, one ordinary loop per lane.

#### Feature: Launch the lanes
- **Description**: `autopilot wave launch` creates the worktrees, moves each
  lane's PRDs into its worktree and starts one detached `autopilot loop` per
  lane.
- **Inputs**: a validated `wave.json`; the main checkout's HEAD.
- **Outputs**: per lane a worktree at `base_sha` on its branch, populated
  `dev/local/`, a running loop; `wave.json` updated (`base_branch`,
  `base_sha`, per-lane `pid`, `started_at`, `status: "running"`, wave `status:
  "running"`).
- **Behavior**: preconditions: `git status --porcelain` empty in the main
  checkout, no live loop on the main root (`loop_gates.live_wrapper_pid`),
  wave `status == "planned"`. Per lane in order: `git worktree add <worktree>
  -b <branch> <base_sha>`; `mkdir -p <worktree>/dev/local/prds/{backlog,wip,done,hold}`
  and `<worktree>/dev/local/autopilot`; `mv` each PRD from the main `backlog/`
  into the worktree's `backlog/` (the worktree's `autopilot select` then sees
  only its lane, and the main backlog no longer lists them); copy
  `dev/local/meta/` when present (the capsule, so Phase 1 can delta-refresh);
  spawn
  `["bash", "-c", "export _AUTOPILOT_LOOP=$$; exec python3 \"$0\" loop", <cli/__main__.py>]`
  with `cwd=<worktree>`, stdin devnull, stdout and stderr appended to
  `<worktree>/dev/local/autopilot/wrapper.log`, `start_new_session=True`, env
  = the inherited environment minus `_AUTOPILOT_LOOP` plus
  `_AUTOPILOT_REVIEW_SLOTS_DIR=<main autopilot dir>/wave-slots`,
  `_AUTOPILOT_REVIEW_SLOTS=<wave.review_slots>` (read by the loop once 00217
  lands, ignored before), `_AUTOPILOT_TRACON_CHILD=1`. The exec'd driver's exec-time environment carries `_AUTOPILOT_LOOP=<its own
  pid>`, which is what `loop_gates._pid_tagged` reads, so each lane registers
  as a live loop, and `live_wrapper_pid` keys on the resolved worktree root, so
  no relaxation of the per-repo guard is needed (sourced from
  `cli/loop_gates.py`; a test pins it). `launch` returns after spawning; the
  loops are detached from the caller.

  Two rules that need no change, stated so no one "fixes" them: the stand-down
  procedure counts only busy interactive sessions named for `basename "$PWD"`
  (core `SKILL.md` § Session Loop), and a lane's cwd basename is
  `<repo>-l<n>`, so lane sessions see neither the operator's main-checkout
  session nor each other as peers; the write fence anchors on the nearest
  `dev/local/autopilot` above cwd (`~/.claude/hooks/enforce_write_scope.py`
  `_repo_root`), so a lane session writes only its own worktree.

#### Feature: Status and abort
- **Description**: `autopilot wave status` renders the lanes; `autopilot wave
  abort` stops them and returns the PRDs.
- **Inputs**: `wave.json`, each worktree's `dev/local/autopilot/state.json`,
  `loop-metrics.jsonl` and lifecycle dirs.
- **Outputs**: a table (lane, pid alive, `state.prd`, `phase`/`next_phase`,
  PRD counts per dir, last row's `phase_end`/`signal`, derived status); on
  abort the PRDs back in the main checkout.
- **Behavior**: derived lane status: `running` (pid alive per
  `loop_gates._pid_alive`), `drained` (pid dead and state `next_phase == ""`),
  `unfinished` (pid dead otherwise). `abort`: SIGTERM each live lane's process
  group (`os.killpg`), wait up to 60 s, SIGKILL what remains; move the
  worktree's `done/*` to main `done/`, `hold/*` to main `hold/`, `wip/*` and
  `backlog/*` to main `backlog/`; a lane whose branch has no commit past
  `base_sha` gets `git worktree remove --force` and `git branch -D`, any other
  is kept and its `git worktree list` line printed; remove `wave-slots/`; wave
  `status: "aborted"`. Idempotent on rerun.

## Structural Decomposition

### Repository Structure

```
skills/run-autopilot/cli/
├── wave.py                 # Maps to: Wave planning (pure cut, wave.json I/O, plan)
├── wave_launch.py          # Maps to: Lane launch (launch, status, abort)
├── wave_cli.py             # Maps to: `autopilot wave <verb>` argparse + dispatch
├── __main__.py             # Maps to: one `_SUBCOMMANDS` row ("wave")
├── test_wave.py            # Maps to: Test Strategy (cut rules)
└── test_wave_launch.py     # Maps to: Test Strategy (tmp git repos)
skills/run-autopilot/references/waves.md   # Maps to: operator runbook
skills/run-autopilot/SKILL.md               # Maps to: pointer + Retention rows
skills/run-autopilot/references/state-schema.md  # Maps to: § Marker files rows
dev/bin/release-checks                      # Maps to: `[checks] waves` block
CHANGELOG.md
```

### Module: wave
- **Maps to capability**: Wave planning
- **Responsibility**: the cut and the `wave.json` file.
- **Exports**: `WAVE_APPEND_ONLY`, `WAVE_FORCE_SHARED`, `shares(a, b) -> bool`,
  `cut(prds: dict[str, str], max_lanes: int) -> tuple[list[Lane], list[dict]]`
  (pure), `load(path)`, `save(path, wave)`, `plan(repo, max_lanes) -> int`.

### Module: wave_launch
- **Maps to capability**: Lane launch
- **Responsibility**: worktrees, PRD moves, loop processes, status, abort.
- **Exports**: `validate(wave, prds) -> list[str]`, `launch(repo, wave, *,
  spawn_fn, run_git) -> int`, `status(repo, wave) -> str`, `abort(repo, wave,
  *, kill_fn, run_git) -> int`, `lane_status(lane) -> str`.

### Module: wave_cli
- **Maps to capability**: both
- **Responsibility**: `autopilot wave plan|launch|status|abort` parsing and
  exit codes; 00215 and 00216 add `assemble`, `review`, `land`, `run` here.
- **Exports**: `add(subparsers)`, `run(args) -> int`.

## Dependency Graph

### Foundation Layer (Phase 0)
No dependencies - built first.

- **wave**: the cut and the file (uses `cli/lane.named_paths`, existing).

### Core Layer (Phase 1)
- **wave_launch**: Depends on [wave].
- **wave_cli**: Depends on [wave, wave_launch].

### Integration Layer (Phase 2)
- **prose, registration, changelog**: Depends on [wave_cli].

## Implementation Phases

### Phase 0: Foundation
**Goal**: the cut is decidable from PRD text alone; the semaphore works.

**Tasks**:
- [ ] Add `cli/wave.py` with `test_wave.py` (no deps) - Acceptance:
  `test_cut_joins_prds_that_share_a_path`,
  `test_cut_treats_a_directory_prefix_as_shared`,
  `test_append_only_files_never_join_lanes`,
  `test_force_shared_paths_pull_prds_into_one_lane`,
  `test_cut_packs_components_into_max_lanes`,
  `test_prd_without_named_paths_is_held_back`,
  `test_lane_order_puts_core_lanes_first`, `test_plan_refuses_a_live_wave`,
  `test_wave_json_round_trips` green; `cut` is pure (no disk).

**Exit Criteria**: the file green; `cut` under 50 lines.

### Phase 1: Core
**Goal**: a wave launches and can be watched and aborted.

**Tasks**:
- [ ] Add `cli/wave_launch.py` (`validate`, `launch`, `lane_status`) and
  `cli/wave_cli.py` with the `plan` and `launch` verbs, register `"wave"` in
  `_SUBCOMMANDS` (depends on: Phase 0) - Acceptance: `test_wave_launch.py`
  (real `git init` repos in `tmp_path`, a stub `python3` target recording its
  argv and environment): `test_launch_adds_a_worktree_per_lane_at_base_sha`,
  `test_launch_moves_lane_prds_out_of_the_main_backlog`,
  `test_launch_copies_meta_when_present`,
  `test_launch_refuses_overlapping_lanes`, `test_launch_refuses_a_dirty_tree`,
  `test_launch_spawns_the_loop_with_its_own_pid_tag` (the stub asserts
  `_AUTOPILOT_LOOP == str(os.getpid())`),
  `test_launch_env_carries_the_slot_dir_and_count`,
  `test_lane_roots_are_distinct_registry_roots` (`live_wrapper_pid` on
  `<repo>` and `<repo>-l1` never confuses the two) green.
- [ ] Add `status` and `abort` to `cli/wave_launch.py` and their verbs to
  `wave_cli.py` (depends on: task 1) - Acceptance:
  `test_status_derives_drained_from_a_dead_pid_and_empty_next_phase`,
  `test_abort_returns_prds_and_removes_clean_worktrees`,
  `test_abort_keeps_a_worktree_with_commits`,
  `test_abort_on_a_planned_wave_is_a_noop` (a planned, never launched wave:
  `abort` marks it `aborted` and the backlog is byte-for-byte as it was)
  green.

**Exit Criteria**: both tasks green in `tmp_path` repos; nothing in this PRD
runs `wave plan` or `abort` against this repo's live backlog inside the batch
session (a stray planned `wave.json` in the live autopilot dir would refuse
the first real `wave plan`).

### Phase 2: Integration
**Goal**: the operator can run a wave from the docs alone.

**Tasks**:
- [ ] Write `references/waves.md` (plan, edit, launch, status, abort; what a
  lane worktree holds; assembly and review deferred to 00215/00216; two
  operator notes: `WAVE_FORCE_SHARED` names this repo's three files and is a
  no-op in any other repo, and a main-checkout loop started after `launch`
  matches lane sessions as stand-down peers by basename prefix and pays one
  SendMessage plus up to 120 s per Phase 0, never a stand-down, because lanes
  own disjoint PRDs), add the pointer to core `SKILL.md` § Operator runbook
  and § Reference Files, add `dev/local/autopilot/wave.json` and
  `wave-slots/` to § Retention (disposable at wave end) and to
  `state-schema.md` § Marker files, append the `[checks] waves` block to
  `dev/bin/release-checks`, and a CHANGELOG `### Added` entry under
  `**run-autopilot**` (depends on: Phase 1) - Acceptance: a new
  `test_wave.py::test_docs_name_the_wave_files` pins `wave.json` and
  `wave-slots/` in the Retention list and `references/waves.md` in
  § Reference Files; `release-checks` green; `cli/test_loop_prose.py` and
  `cli/test_custody_prose*.py` stay green.

**Exit Criteria**: suites green; `release-checks` green.

## Test Strategy

### Critical Scenarios
- **Happy path**: five backlog PRDs with disjoint paths, `--max-lanes 3` →
  three lanes, every PRD placed, `launch` creates three worktrees at
  `base_sha`, three loop processes with distinct pid tags, the main backlog
  empty → Expected: `status` shows three `running` lanes.
- **Edge case**: two PRDs both name `state-schema.md` → one lane, ordered
  first; a PRD's Location line names `skills/x` (no trailing slash) and
  another names `skills/x/y.py` → one lane; a
  wave edited by hand into an overlap → `launch` refuses before creating
  anything → Expected: exact lane/path named on stderr.
- **Error case**: a lane loop dies (pid gone, `next_phase` non-empty) →
  `status` says `unfinished`; `abort` returns its PRDs to `backlog/` and keeps
  the worktree because it has commits → Expected: nothing lost, path printed.

## Risks

- **Catchup per lane**: each lane's first session runs Phase 1; the copied
  capsule makes it a delta refresh only when Phase 1's freshness check holds
  (`batch.catchup_completed_at` is per batch, and a lane batch is new), so a
  full catchup (~180K tokens) per lane is the likely cost. Accepted for v1;
  measured by the post-release signal in 00216's summary report.
- **Five-hour window**: N lanes multiply the spend; the existing window yield
  (`loop_gates._oldest_live_loop_pid`, PRD 00199) already makes younger loops
  yield to the oldest on an `allowed_warning`, `--max-lanes` defaults to 3, and
  00217 bounds the review sessions, the expensive ones.
- **A loop is still one PRD per checkout**: nothing here changes selection,
  hooks, caps or the roster; the lane is the ordinary loop in a worktree.
