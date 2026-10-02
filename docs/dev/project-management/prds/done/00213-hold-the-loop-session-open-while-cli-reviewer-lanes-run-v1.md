---
catchup: skip
design: skip
default_model: opus
model_tier_rationale: a Stop hook that can hold every loop session hostage if it misjudges liveness, plus two bash wrappers where a second EXIT trap silently replaces the first; the contracts are written out below, the risk is in the edges
rework_cap: 2
---

# Hold the loop session open while CLI reviewer lanes run

Source: `dev/local/notes/validation-batch-054-2026-09-20.md` finding V8
(2026-09-21). Grounded at `8885300` (0.5.5). Same class as 00211 (prose the
orchestrator can skip, replaced by a hook); independent of 00207-00210.

## Overview

### Problem Statement

`review-work-completion` step 5 and `fast-track` § Preconditions run Bob
(`codex-run.sh`) and Carl (`gemini-run.sh`) as background Bash and tell a loop
session to dispatch a Watcher subagent in the same message, because headless
`claude -p` kills background Bash about five seconds after the turn ends. The
Watcher is a sentence. On the 00211 review (opus, `_AUTOPILOT_LOOP=1`) the
session dispatched Alice and Blake, started Bob and Carl in the background,
never dispatched the Watcher, and ended its turn with "Waiting on Bob and
Carl."; both CLI reviewers died, no review file was written, $6.50 and seven
minutes were lost and the review had to be relaunched. The 00209 and 00210
sessions of the same batch did dispatch it. The keep-alive must be a mechanism
the session cannot skip: a Stop hook that refuses the turn's end while a CLI
lane started by this loop session is still alive, exactly as
`review_coverage_hook.py` already refuses it at an incomplete review file.

### Target Users

Headless loop sessions (`_AUTOPILOT_LOOP` set): the review-rework loop and the
fast-track lane. Interactive sessions and standalone wrapper runs are untouched.

### Success Metrics

- `uv run --no-project --with pytest python -m pytest -q hooks/test_guard_stop_on_live_lanes.py hooks/test_hook_registration.py`
  green.
- `bash skills/use-codex/scripts/test_codex_run.sh` and
  `bash skills/use-gemini/scripts/test_gemini_run.sh` green with the new lane
  cases.
- `bash dev/bin/release-checks` green (the new test joins the
  `[checks] hook registration` block).
- Post-release signal: no loop review session ends with a live `codex-run.sh`
  or `gemini-run.sh` child (no `codex-event:` stream cut mid-review in
  `last-session.log`), and every `.lane-guard-blocks` count seen in a session
  log is followed by a written review file.

## Functional Decomposition

### Capability: Lane keep-alive guard

#### Feature: Mark a live CLI lane
- **Description**: `codex-run.sh` and `gemini-run.sh` leave a marker for the
  life of the process when they run inside a loop session.
- **Inputs**: `$_AUTOPILOT_LOOP`; the wrapper's own pid (`$$`); `OUTPUT_FILE`
  (`-o`); the autopilot dir found from cwd by
  `python3 "$(dirname "$0")/../../run-autopilot/scripts/_walk_up.py" --bash`.
- **Outputs**: `dev/local/autopilot/lanes/<pid>`, two lines: the kind (`codex`
  or `gemini`) and the absolute `-o` path (an empty second line when no `-o`).
- **Behavior**: written after argument parsing and prompt validation, before
  any backend runs, only when `_AUTOPILOT_LOOP` is set and the walk-up finds a
  dir (`mkdir -p .../lanes`). Removed by the wrapper's `EXIT` trap.
  `gemini-run.sh` already owns `trap 'rm -rf "$RUN_TMP"' EXIT`; the removal
  joins that trap in one statement, because a second `trap ... EXIT` replaces
  the first and `RUN_TMP` would leak. Observation only: a failed walk-up,
  `mkdir` or write leaves the marker variable empty and the run proceeds
  unchanged; the wrapper's exit code never changes. `sonnet-run.sh` is out of
  scope: it is foreground-blocking by design and never dispatched in the
  background.

#### Feature: Refuse the stop while a lane is alive
- **Description**: a Stop hook, `hooks/guard_stop_on_live_lanes.py`, blocks the
  turn's end while a marked lane is still running and names what to await.
- **Inputs**: hook stdin JSON (`cwd`); `_AUTOPILOT_LOOP`;
  `dev/local/autopilot/lanes/*` located via `_walk_up.find_autopilot_dir`.
- **Outputs**: exit 2 with the reason on stderr, or exit 0; the counter
  `dev/local/autopilot/.lane-guard-blocks`.
- **Behavior**: not in the loop, no autopilot dir, or no `lanes/` dir: exit 0.
  A marker whose name is not an integer is ignored. A marker whose pid is dead
  (`os.kill(pid, 0)` raises `ProcessLookupError`; `PermissionError` counts as
  alive) is unlinked and ignored. A live marker older than
  `LANE_MAX_AGE_SECS = 3600` (mtime) is not held: one stderr line
  `autopilot: lane <kind> (pid N) has run <m> min, past the 60 min ceiling; not holding the session for it`
  (the retry policy already treats a stalled reviewer as failed). With no
  live lane left the counter is removed and the hook exits 0. With live lanes
  the counter is incremented; past `BLOCK_CAP = 40` the hook writes
  `... giving up after 40 blocked exits to preserve session liveness`, removes
  the counter and exits 0 (the same valve shape as `review_coverage_hook.py`).
  Otherwise it exits 2 with:
  `autopilot: <n> CLI reviewer lane(s) still running: codex (pid N) -> <output>; gemini (pid M) -> <output>. Headless claude kills them when this turn ends. Run python3 <abs path>/skills/review-work-completion/scripts/await_reviewer_outputs.py --budget 100 <outputs> in the foreground; while its last line is WAITING run it again; on DONE continue the review. Do not end the turn before then.`
  The awaiter path is resolved from the hook's own `__file__`, never a
  placeholder. A lane with an empty `-o` line is listed as `(no -o file)` and
  left out of the awaiter arguments. Every internal failure is exit 0.

#### Feature: The prose names the backstop
- **Description**: the two places that dispatch the Watcher say the hook holds
  the session when the Watcher is skipped; the retention list knows the dir.
- **Inputs**: `skills/review-work-completion/SKILL.md` step 5 (the Watcher
  paragraph ending "treat that reviewer as failed per
  `references/retry-policy.md`"), `skills/fast-track/SKILL.md` § Preconditions
  (the `_AUTOPILOT_LOOP` bullet), `skills/run-autopilot/SKILL.md` § Retention.
- **Outputs**: one sentence each; a `### Retention` disposable entry
  `dev/local/autopilot/lanes/` (one marker per live CLI reviewer lane, removed
  when the lane exits); a design-rationale section.
- **Behavior**: the Watcher stays as written (it is still the normal path);
  the sentence says `hooks/guard_stop_on_live_lanes.py` (PRD 00213) holds the
  session open while either background lane is alive and names the files to
  await. The fast-track sentence must not use any form of "refuse":
  `test_fast_track_prose.py::test_headless_sessions_dispatch_the_watcher`
  rejects `refus*` in that bullet.

## Structural Decomposition

### Repository Structure

```
hooks/
├── guard_stop_on_live_lanes.py         # Maps to: Refuse the stop while a lane is alive
├── test_guard_stop_on_live_lanes.py    # Maps to: Test Strategy (hook + docs pins)
├── test_hook_registration.py           # Maps to: the Stop registration pin (00211 file, one test added)
└── hooks.json                          # Maps to: Stop registration
skills/use-codex/scripts/
├── codex-run.sh                        # Maps to: Mark a live CLI lane
├── codex_run_test_lib.sh               # Maps to: stub records the lanes dir (env-gated)
└── test_codex_run.sh                   # Maps to: lane cases
skills/use-gemini/scripts/
├── gemini-run.sh                       # Maps to: Mark a live CLI lane (trap merge)
└── test_gemini_run.sh                  # Maps to: lane cases
skills/run-autopilot/scripts/test_review_coverage_hook_registration.py  # Maps to: pack-wide table row
skills/review-work-completion/SKILL.md                                  # Maps to: backstop sentence
skills/review-work-completion/references/design-rationale.md            # Maps to: incident section
skills/fast-track/SKILL.md                                              # Maps to: backstop sentence
skills/run-autopilot/SKILL.md                                           # Maps to: Retention entry
dev/bin/release-checks                                                  # Maps to: hook registration block
CHANGELOG.md
```

### Module: lane marker (bash, both wrappers)
- **Maps to capability**: Lane keep-alive guard
- **Responsibility**: mark the wrapper's pid for its lifetime under the loop.
- **Exports**: the marker file contract above.

### Module: hooks/guard_stop_on_live_lanes.py
- **Maps to capability**: Lane keep-alive guard
- **Responsibility**: decide, from the markers alone, whether the turn may end.
- **Exports**: `live_lanes(autopilot_dir) -> list[Lane]` (pure: reads, unlinks
  dead markers, applies the age ceiling), `reason(lanes, awaiter) -> str`,
  `main()`.

## Dependency Graph

### Foundation Layer (Phase 0)
- **lane marker**: no dependencies (`_walk_up.py --bash` exists).

### Core Layer (Phase 1)
- **guard_stop_on_live_lanes.py**: depends on the marker contract.

### Integration Layer (Phase 2)
- **prose, registration checks, changelog**: depend on both.

## Implementation Phases

### Phase 0: Mark the lanes
**Goal**: a loop-session wrapper run is visible as a marker for its lifetime.

**Tasks**:
- [ ] Add the marker block to `codex-run.sh` (after prompt validation, before
  `run_cmd`) with its own `trap` (the script has none today), and to
  `gemini-run.sh` merged into the existing `RUN_TMP` trap; the stub in
  `codex_run_test_lib.sh` and the copilot/gemini stubs in `test_gemini_run.sh`
  gain one env-gated line that lists the lanes dir and copies the marker while
  the stub runs (no deps) - Acceptance: in `test_codex_run.sh` and
  `test_gemini_run.sh`, with `_AUTOPILOT_LOOP=1` and cwd inside a temp repo
  holding `dev/local/autopilot`, exactly one marker exists during the run,
  its first line is the kind and its second the `-o` path, and the lanes dir
  is empty after the run; without `_AUTOPILOT_LOOP` no marker is written;
  with the loop set but no autopilot dir above cwd the run exits 0 and creates
  nothing; gemini only: with `TMPDIR` pointed at an empty temp dir, that dir
  is empty after the run (the merged trap still removes `RUN_TMP`). Existing
  cases stay green.

### Phase 1: The Stop hook
**Goal**: the turn cannot end while a marked lane is alive.

**Tasks**:
- [ ] Add `hooks/guard_stop_on_live_lanes.py` with
  `hooks/test_guard_stop_on_live_lanes.py` (depends on: Phase 0) -
  Acceptance: subprocess tests with a stdin payload and a `tmp_path` repo:
  `test_live_lanes_block_the_stop_with_the_files_to_await` (two `sleep`
  children, markers named by their pids; exit 2; stderr names both `-o`
  paths, `await_reviewer_outputs.py`, `--budget 100`; children killed in
  `finally`), `test_dead_lane_marker_is_ignored_and_removed`,
  `test_lane_past_the_age_ceiling_does_not_hold_the_session` (`os.utime`
  the marker 3700 s back; exit 0; stderr says `past the 60 min ceiling`),
  `test_outside_the_loop_never_blocks`, `test_no_autopilot_dir_passes`,
  `test_no_lanes_dir_passes`, `test_non_pid_marker_names_are_ignored`,
  `test_lane_without_an_output_file_is_named_but_not_awaited`,
  `test_block_cap_gives_up_loud` (counter at 40 → exit 0, `giving up`,
  counter removed), `test_blocks_count_up_and_reset_when_lanes_finish`. The
  deny tests assert the reason text, never exit code alone (00211 review).
- [ ] Register the hook on `Stop` in `hooks/hooks.json` (timeout 5, after
  `review_coverage_hook.py`; the Stop block carries no `matcher`), add the
  `"guard_stop_on_live_lanes.py": "Stop"` row to `_EXPECTED_REGISTRATIONS`,
  add `test_guard_stop_on_live_lanes_runs_on_stop` to
  `hooks/test_hook_registration.py` (its existence and timeout tests cover the
  third hook too; docstring names 00213 beside 00211), list the new test in
  the `[checks] hook registration` block of `dev/bin/release-checks`
  (depends on: task 1) - Acceptance: both registration files green;
  `release-checks` green.

### Phase 2: Prose and changelog
**Goal**: the Watcher paragraphs name the backstop; the dir is retained
correctly.

**Tasks**:
- [ ] Add the sentence to `review-work-completion/SKILL.md` step 5 and to the
  fast-track `_AUTOPILOT_LOOP` bullet (no `refus*`), the Retention entry, the
  design-rationale section
  `## The keep-alive is a hook, not a sentence (PRD 00213)` (the V8 numbers
  above), and a CHANGELOG `### Added` entry under `**hooks**` (depends on:
  Phase 1) - Acceptance:
  `hooks/test_guard_stop_on_live_lanes.py::test_docs_name_the_guard` pins
  `guard_stop_on_live_lanes.py` in the review SKILL.md step 5 Watcher
  paragraph and in the fast-track Preconditions section, and
  `dev/local/autopilot/lanes/` in the run-autopilot Retention list;
  `test_fast_track_prose.py`, `test_carl_skip_prose.py`,
  `test_retry_policy_prose.py` and `cli/test_loop_prose.py` stay green.

**Exit Criteria**: suites green; `release-checks` green.

## Test Strategy

### Critical Scenarios
- **Happy path**: loop session, Bob and Carl started with `-o` files, no
  Watcher; the model ends the turn → exit 2 with both files named; the model
  runs the awaiter; lanes exit, markers vanish → the next stop passes and the
  counter is gone.
- **Edge case**: a marker left by a killed session (dead pid) → pass, marker
  removed; a lane past 60 min → pass with the stderr note; a marker named
  `README` → ignored; a wrapper started without `-o` → named, not awaited.
- **Error case**: the wrapper cannot write the marker (no autopilot dir, or
  `lanes/` unwritable) → the reviewer runs exactly as before; the hook hits a
  malformed marker or an unreadable dir → exit 0; 40 blocked exits → gives up
  loud and lets the session end.

## Risks

- **A held session that never ends**: bounded twice, by the 60 min age
  ceiling (a compliant session awaits and the lanes finish or stall) and by
  `BLOCK_CAP` (a session that ignores the reason burns at most 40 turns).
  Accepted.
- **Pid reuse inside 60 min**: a recycled pid would hold the session until the
  ceiling; `ponytail:` comment names it, the ceiling bounds it. Accepted.
- **Both Stop hooks exit 2 on one stop**: the model sees both reasons; the
  coverage hook's own valve is untouched. Accepted.
- **Two loop sessions in one checkout**: the markers are per autopilot dir,
  so a second session would hold for the first's lanes; the loop runs one
  session per checkout and my hand reviews run in separate worktrees. Accepted.

Follow-up (not this PRD): once the hook has held for a whole batch, retire the
Watcher dispatch prose (review step 5, fast-track Preconditions,
`test_fast_track_prose.py::test_headless_sessions_dispatch_the_watcher`, the
`⟨Watcher⟩` rendering in `test_render_stream.py`).
