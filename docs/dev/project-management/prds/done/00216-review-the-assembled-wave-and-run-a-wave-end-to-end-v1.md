---
catchup: skip
design: run
default_model: sonnet
model_tier_rationale: sonnet floor by operator decision 2026-09-26 (the opus floor cost 109 min per task on 00214, 95 of them in test rounds); the planner still lifts the seeded review-phase state and the nested-loop outcome decision to opus per task through the contract escalator row
rework_cap: 2
---

# Review the assembled wave and run a wave end to end

Source: `dev/local/discovery/00212-route-prds-in-waves.md` must-have 5, open
question 2, the `autoclaude wave` nice-to-have (2026-09-21). Grounded at
`8885300` (0.5.5). Depends on 00214 (launch) and 00215 (assembly branch and
artifact migration). Last of three.

## Overview

### Problem Statement

An assembled wave is N reviewed PRDs plus whatever the assembly added: the
keep-both resolutions and the interactions between lanes that no per-PRD review
saw. The standing rule keeps every review cycle at the full roster, and
00212 asks for one more `review-work-completion` over the merge range whose
CRITICAL or HIGH findings become rework in the ordinary loop, never a silent
fix. Rather than a new review path, this PRD hands the assembled branch to the
loop itself: a stub PRD that describes the wave, a state file in the shape
`phase-done --outcome tasks_done` leaves, and `autopilot loop` in the assembly
worktree, so the review, the rework and the second cycle are the ones every
PRD already gets. It then lands the branch on master and adds the one-shot
`autopilot wave run` that chains plan, launch, wait, assemble, review and land.

Open question 2 is decided here: the full roster, through the ordinary loop,
with `rework_cap: 2`.

### Target Users

The operator, and the review-rework loop under `_AUTOPILOT_LOOP`.

### Success Metrics

- `uv run --no-project --with pytest python -m pytest -q skills/run-autopilot/cli/test_wave_review.py`
  green; `bash skills/review-work-completion/scripts/test_gather_context_paths.sh`
  green.
- `bash dev/bin/release-checks` green (`test_wave_review.py` and the bash test
  join the `[checks] waves` block).
- Post-release signal: a real wave's `reports/<wave id>-wave.md` ends with
  `## Assembly review: converged` and master's new head equals the assembly
  head; the wall-clock per PRD in that summary is under 1 h against the
  0.5.4 loop's 2.2 h mean, at the same or lower `cost_usd` per PRD.

## Functional Decomposition

### Capability: Assembly review
Review the assembled branch with the loop everyone else gets.

#### Feature: Review the assembly branch with the ordinary loop
- **Description**: `autopilot wave review` writes the stub PRD and the seeded
  state in the assembly worktree and runs `autopilot loop` there.
- **Inputs**: `wave.json` with `status` `assembled` or `assembled_partial`,
  its `assembly` block and each lane's `files` (00215); the assembly
  worktree; `dev/local/meta/` in the main checkout;
  `~/.claude/plugins/installed_plugins.json`.
- **Outputs**: `<assembly worktree>/dev/local/prds/wip/<wave id>-wave-assembly-v1.md`;
  `<assembly worktree>/dev/local/autopilot/state.json`;
  `<assembly worktree>/dev/local/autopilot/review-paths`; the loop's own
  artifacts (review files, ledgers, report); a review outcome `converged` or
  `review_failed` in `wave.json`.
- **Behavior**: preconditions: wave status `assembled`/`assembled_partial`,
  the assembly worktree present, main tree clean. The stub's frontmatter:
  `catchup: skip`, `design: skip`, `rework_cap: 2`, `default_model: sonnet`,
  `model_tier_rationale: fixes to conflict resolutions and lane interactions
  found by the assembly review`. Its body, in the create-prd template shape so
  `plan-tasks` can parse a rework: `# Wave <id> assembly`; `## Overview` with
  the merged lanes, their PRDs, `Diff range: <base_sha>..<head_sha>` and
  `Diff scope:` followed by the review paths (below), one per line;
  `## Functional Decomposition` / `### Capability: Assembly` /
  `#### Feature: Lane merges` (Description, Inputs, Outputs, Behavior naming
  each merged lane and its keep-both resolutions); `## Implementation Phases`
  / `### Phase 0: Assembly` with one `- [x] Merge lane <name> (<prds>) -
  Acceptance: release-checks green` per merged lane; `## Test Strategy`
  naming `bash dev/bin/release-checks` and every merged PRD's own named
  tests. Copy `dev/local/meta/` from the main checkout. Seed the state with
  `autopilot init --state <state> --prd <stub>`, then `statectl.py <state>
  set` for `work_start_sha "<base_sha>"`, `cycle 1`, `rework_cap 2` and
  `batch {"id": "<wave id>", "mode": "autopilot", "completed_prds": [],
  "plugin_versions": {"aegis@buvis-plugins": "<v>", "warden@buvis-plugins":
  "<v>"}}` read the way Phase 0 step 3 reads them, then `autopilot phase-done
  --state <state> --outcome tasks_done`: the same transition a build session
  runs at `tasks_done` (`cli/transitions._to_review` sets `phase` and
  `next_phase` to `review` and leaves `phases_completed` untouched, so the
  seed never writes that key), which also clears the hand-off markers. The
  review session therefore enters Phase 4 with the stub as `state.prd`,
  `tasks: []` (the review skill's "no tasks exist" branch) and the
  full-review range `<base_sha>..HEAD`; on the assembly branch `git diff
  <base branch>` is that same range whichever base the orchestrator takes.

  The range is narrowed to the interaction surface: `review` writes
  `<assembly worktree>/dev/local/autopilot/review-paths`, one repo-relative
  path per line, sorted: every path present in the `files` of two or more
  lanes, plus `WAVE_APPEND_ONLY`. `gather-context.sh` (review-work-completion)
  reads `$PROJECT_ROOT/dev/local/autopilot/review-paths` when it exists and
  is non-empty, appends `-- <its paths>` to both of its `git diff` commands
  and labels the scope `path-scoped review (<n> paths from
  dev/local/autopilot/review-paths)`; absent or empty, nothing changes. Every
  PRD already had its full-roster review inside its lane; the assembly review
  covers what those could not see, the keep-both resolutions and the files
  more than one lane touched, and it fits every reviewer (the 2026-09-20 wave
  was 12,367 inserted lines in 135 files, of which the six shared files held
  112). Spawn the loop in the assembly worktree with the 00214 launcher (no
  slot variables) and wait for it. Outcome: the stub in the worktree's
  `done/` → `converged`; the stub in `hold/`, or the loop exiting with the
  stub still in `wip/` → `review_failed`.

#### Feature: Land the wave
- **Description**: on `converged`, fast-forward master and fold the assembly
  worktree's artifacts into the main checkout; otherwise leave master alone.
- **Inputs**: the review outcome, `wave.json`, the assembly worktree.
- **Outputs**: master at the assembly head; the wave archived.
- **Behavior**: on `converged`: refuse with exit 5 when the main checkout's
  HEAD is not `base_sha` (master moved during the wave; the operator merges by
  hand), else `git merge --ff-only wave/<id>/assembly` in the main checkout;
  migrate the assembly worktree's artifacts exactly as 00215 migrates a lane
  (`"lane": "assembly"`), move the stub to the main `done/`, remove the
  assembly worktree and branch, delete `wave-slots/`, append `## Assembly
  review: converged (<n> cycle(s)), landed <sha>` to the summary, set
  `wave.json` status `done` and move it to `reports/<wave id>-wave.json`. On
  `review_failed`: master untouched, worktree and branch kept, status
  `review_failed`, the summary gains the review file path and where the stub
  sits; exit 4. `land` is its own verb (`autopilot wave land`) so an operator
  who reviewed by hand can still land.

### Capability: One-shot wave
Chain the verbs so a wave is one command.

#### Feature: Run a wave in one command
- **Description**: `autopilot wave run`: plan, confirm, launch, wait,
  assemble, review, land.
- **Inputs**: `--max-lanes N` (default 3), `--review-slots N` (default 3),
  `--yes`.
- **Outputs**: the wave's files and exit code.
- **Behavior**: `plan` and print the table; unless `--yes`, wait for Enter on
  a TTY (`sys.stdin.isatty()`; without a TTY and without `--yes` exit 1 with
  "pass --yes"); `launch`; poll every 30 s until every lane pid is dead,
  printing the `status` table every 10 min; `assemble`; `review`; `land`.
  Exit codes: 0 landed; 1 precondition; 3 a lane was kept (the run still
  reviews and lands what merged); 4 review failed; 5 master moved. SIGINT or
  SIGTERM forwards SIGTERM to every live lane group, writes status
  `interrupted` and exits 130; `wave assemble` resumes from there. The
  `autoclaude wave` alias is a one-line dotfiles change after release:
  `caffeinate -is python3 "$_skill/cli/__main__.py" wave run "$@"`.

## Structural Decomposition

### Repository Structure

```
skills/run-autopilot/cli/
├── wave_review.py          # Maps to: Assembly review (stub, state, review, land)
├── wave_run.py             # Maps to: One-shot wave
├── wave_cli.py             # Maps to: the `review`, `land`, `run` verbs (file from 00214)
├── test_wave_review.py     # Maps to: Test Strategy
skills/run-autopilot/references/waves.md   # Maps to: § Review and land, § wave run (file from 00214)
skills/run-autopilot/references/state-schema.md  # Maps to: § Marker files row `review-paths`
skills/run-autopilot/SKILL.md               # Maps to: Retention (`review-paths` disposable)
skills/review-work-completion/scripts/
├── gather-context.sh                       # Maps to: the `review-paths` filter
└── test_gather_context_paths.sh            # Maps to: Test Strategy (filter)
dev/bin/release-checks                      # Maps to: `[checks] waves` block
CHANGELOG.md
```

### Module: wave_review
- **Maps to capability**: Assembly review
- **Responsibility**: the stub, the review paths, the seeded state, the nested
  loop, the landing.
- **Exports**: `stub_text(wave) -> str` (pure), `review_paths(wave) ->
  list[str]` (pure), `seed_state(state_path, wave, plugins_json) -> None`,
  `review(repo, wave, *, spawn_fn) -> str` (the outcome), `land(repo, wave,
  *, run_git) -> int`.

### Module: wave_run
- **Maps to capability**: One-shot wave
- **Responsibility**: ordering, waiting, signals, exit codes.
- **Exports**: `run(repo, *, max_lanes, review_slots, yes, sleep_fn, clock)
  -> int`.

## Dependency Graph

### Foundation Layer (Phase 0)
No dependencies - built first.

- **stub_text, review_paths**: pure text over `wave.json`.

### Core Layer (Phase 1)
- **seed_state, review, land**: Depends on [stub_text, review_paths, 00214
  launcher, 00215 migration and lane `files`, `autopilot init`, `statectl`,
  `autopilot phase-done`].
- **gather-context.sh filter**: no dependencies inside this PRD (reads the
  marker file `review` writes).

### Integration Layer (Phase 2)
- **wave_run, verbs, prose, changelog**: Depends on [review, land].

## Implementation Phases

### Phase 0: Foundation
**Goal**: the stub is a PRD the loop can plan a rework from.

**Tasks**:
- [ ] Add `stub_text` and `review_paths` with their tests (no deps) -
  Acceptance: `test_stub_prd_names_every_merged_lane_and_the_range`,
  `test_stub_prd_carries_the_headings_plan_tasks_parses` (`#### Feature:`,
  `### Phase 0:`, `- [x]` items), `test_stub_frontmatter_is_the_five_pairs`
  (the five pairs above, parsed by `cli/frontmatter.parse` without a
  warning), `test_stub_prd_lists_the_diff_scope`,
  `test_review_paths_are_the_multi_lane_files_plus_append_only` (lanes l1 and
  l2 both list `cli/records.py`, l1 alone lists `cli/x.py`: the result is
  `CHANGELOG.md`, `cli/records.py`, `dev/bin/release-checks` and never
  `cli/x.py`; a kept lane's `files` count too) green.

**Exit Criteria**: `stub_text` and `review_paths` under 50 lines each.

### Phase 1: Core
**Goal**: the loop reviews the branch; master lands only on convergence.

**Tasks**:
- [ ] Add `seed_state` and `review` (depends on: Phase 0) - Acceptance:
  `test_seeded_state_is_the_tasks_done_shape` (`schema.validate` passes;
  `phase` and `next_phase` are `review`; `work_start_sha`, `cycle`,
  `rework_cap`, `batch.id`, `batch.plugin_versions` exact; `phases_completed`
  absent or empty; the seed's last write is `autopilot phase-done --outcome
  tasks_done`, pinned by an injected runner recording its argv),
  `test_review_writes_review_paths_in_the_assembly_worktree` (the file holds
  exactly `review_paths(wave)`, one per line),
  `test_review_copies_meta_and_spawns_the_loop_in_the_assembly_worktree`
  (injected `spawn_fn` records cwd and the absence of the slot variables),
  `test_review_outcome_reads_done_and_hold` (a fake loop that moves the stub),
  `test_review_refuses_before_assembly` green.
- [ ] Add the `review-paths` filter to `gather-context.sh` with
  `test_gather_context_paths.sh` (depends on: Phase 0) - Acceptance: in a
  `tmp_path` git repo with a `master` base and a branch touching `a.py` and
  `b.py`, with `dev/local/autopilot/review-paths` holding `a.py`, the diff
  file holds `a.py` hunks only and the context file's scope line reads
  `path-scoped review (1 paths from dev/local/autopilot/review-paths)`;
  without the marker both files appear and the scope line is as today; an
  empty marker behaves as absent; `test_gather_context_id.sh` stays green.
- [ ] Add `land` (depends on: Phase 0) - Acceptance:
  `test_land_fast_forwards_master_and_removes_the_worktree`,
  `test_land_migrates_the_assembly_artifacts_as_lane_assembly`,
  `test_land_refuses_when_master_moved`,
  `test_review_failed_keeps_master_untouched` green.

**Exit Criteria**: on a `tmp_path` wave with a fake loop that converges,
`review` then `land` leaves master at the assembly head and no worktree.

### Phase 2: Integration
**Goal**: one command, documented.

**Tasks**:
- [ ] Add `wave_run.py`, register `review`, `land` and `run` in
  `wave_cli.py`, add § Review and land and § `wave run` to
  `references/waves.md` (the exit codes, the interrupted resume, the alias
  line, the review scope and its `review-paths` file), add `review-paths` to
  `state-schema.md` § Marker files (writer `autopilot wave review`, reader
  `gather-context.sh`, removed with the assembly worktree) and to core
  `SKILL.md` § Retention (disposable), add `test_wave_review.py` and `bash
  skills/review-work-completion/scripts/test_gather_context_paths.sh` to the
  `[checks] waves` block, and a CHANGELOG `### Added` entry under
  `**run-autopilot**` (depends on: Phase 1)
  - Acceptance: `test_run_orders_plan_launch_wait_assemble_review_land`
  (injected fakes record the order), `test_run_without_tty_needs_yes`,
  `test_run_exit_code_follows_the_weakest_step`,
  `test_run_interrupt_terminates_lane_groups` (injected `kill_fn`),
  `test_docs_name_the_exit_codes` green; `release-checks` green.

**Exit Criteria**: suites green; `release-checks` green.

## Test Strategy

### Critical Scenarios
- **Happy path**: an assembled wave, a fake loop that writes a review file,
  moves the stub to `done/` and exits 0 → `converged`, master fast-forwarded,
  the summary ends with the converged line → Expected: exit 0, no worktree
  left.
- **Edge case**: the fake loop parks the stub (cap reached with a CRITICAL) →
  `review_failed`, master untouched, worktree kept, summary names the review
  file → Expected: exit 4; a later `wave land` after a hand review still
  lands.
- **Error case**: master moved during the wave → `land` exits 5 before any
  git write; `run` on a non-TTY without `--yes` exits 1 before planning.

## Risks

- **The seeded state drifts from what `phase-done` writes**: it cannot; the
  seed runs the same `phase-done --outcome tasks_done` transition a build
  session runs, and `test_seeded_state_is_the_tasks_done_shape` pins only the
  data fields the seed supplies itself.
- **The review session reads an empty diff**: the assembly branch's base is
  master, so `gather-context.sh`'s branch-base diff is the whole wave even
  when the orchestrator omits `--since`, narrowed by `review-paths` to the
  interaction surface; `work_start_sha` covers the other reading. Both are
  tested by inspection of the stub state, not by a live session.
- **The interaction surface misses a cross-lane symbol use inside a
  single-lane file**: accepted; that file had its full-roster review in its
  lane, and `release-checks` after each merge catches a broken import or
  test.
- **Two review cycles on a big merge range**: bounded by `rework_cap: 2`;
  what survives the cap is deferred and parked exactly as any PRD's is, and
  the wave then fails to land rather than landing unreviewed work.
