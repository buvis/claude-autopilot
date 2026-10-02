---
catchup: skip
design: skip
default_model: sonnet
model_tier_rationale: one script flag widened to a second marker, one Phase 0 sentence, tests with tmp_path fixtures; no design call
rework_cap: 2
---

# Clear inherited hand-off markers at session start

Source: `dev/local/notes/validation-batch-054-2026-09-20.md` finding V1
(2026-09-20). Grounded at `b78bc11` (0.5.4). Independent of 00207-00211.

## Overview

### Problem Statement

`.handoff-requested` is written by the context-cap hook for the session that
will consume it at `/autopilot:work` step 6.5. PRD 00191 clears both markers at
lifecycle edges (phase-done, stall, park), and Phase 0 runs `_walk_up.py
--clear-cap` after a rotation, which removes `.cap-fired` only. A marker left
by a session that neither reached an edge nor rotated (a wall-cap kill, a
crash, a plugin upgrade between sessions) survives into the next session.
Measured: a 1-byte `.handoff-requested` written 2026-09-14 by the 0.5.2 hook
sat through the 0.5.4 launch; step 6.5 read it as a legacy-empty marker (=
current phase, a match) and handed off after task 2 with task 3 pending, the
banner claiming "headroom rule fired". Cost: one session start (~5 min, ~$4).
A marker present when a session begins was, by construction, written by an
earlier session and describes a boundary that session never reached; it is
never this session's to act on.

### Target Users

The loop under `_AUTOPILOT_LOOP`; interactive resumes after a crash.

### Success Metrics

- `uv run --no-project --with pytest python -m pytest -q skills/run-autopilot/scripts/test_walk_up.py skills/run-autopilot/cli/test_custody_prose.py`
  green with the new cases.
- `bash dev/bin/release-checks` green.
- Post-release signal: no `.handoff-requested` in `dev/local/autopilot/` whose
  `at` predates the running session's start.

## Functional Decomposition

### Capability: Session-start marker clear

#### Feature: `--clear-markers` removes both markers
- **Description**: `_walk_up.py` gains `--clear-markers`, which removes
  `.handoff-requested` and `.cap-fired` beside the located autopilot dir;
  `--clear-cap` keeps its current single-marker behavior for back-compat.
- **Inputs**: cwd (walk-up), the two marker files.
- **Outputs**: exit 0 always; one stderr line per removed marker
  (`autopilot: cleared inherited <name> written <at|mtime>`), nothing when
  none was present.
- **Behavior**: best-effort like `--clear-cap`; reuses `cli/handoff.MARKERS`
  by name (the script must not import the package: it is a bare-binary
  helper, so the two names are repeated as a module constant with a comment
  naming `handoff.MARKERS` as the source of truth, and a test asserts the
  two tuples are equal).

#### Feature: Phase 0 clears unconditionally
- **Description**: `references/phase-build.md` § Phase 0 runs
  `--clear-markers` as its first Bash call after the lifecycle `mkdir`, in
  every mode, before the abort handlers read `state.json`.
- **Inputs**: none.
- **Outputs**: the amended § Ensure lifecycle directories exist (or a sibling
  sub-step) and the cap-rotation bullet, which now says the general clear
  already ran and drops its own `--clear-cap` call.
- **Behavior**: prose; the `work` skill's step 2 and 6.5 marker handling is
  unchanged (a marker written by THIS session's hook after Phase 0 is still
  consumed as today).

## Structural Decomposition

### Repository Structure

```
skills/run-autopilot/
├── scripts/_walk_up.py            # Maps to: --clear-markers
├── scripts/test_walk_up.py        # Maps to: Test Strategy
├── cli/handoff.py                 # Maps to: MARKERS parity test only (no change)
├── references/phase-build.md      # Maps to: Phase 0 clear
└── cli/test_custody_prose.py      # Maps to: the Phase 0 prose pin
```

### Module: _walk_up
- **Maps to capability**: Session-start marker clear
- **Responsibility**: locate the dir and unlink the inherited markers.
- **Exports**: `--clear-markers`, `INHERITED_MARKERS`.

## Dependency Graph

### Foundation Layer (Phase 0)
- **_walk_up**: no dependencies.

### Integration Layer (Phase 1)
- **phase-build prose**: depends on [_walk_up].

## Implementation Phases

### Phase 0: Script
**Goal**: one call clears both inherited markers.

**Tasks**:
- [ ] Add `--clear-markers` to `_walk_up.py` with `INHERITED_MARKERS` (no
  deps) - Acceptance: `test_walk_up.py` gains
  `test_clear_markers_removes_both_inherited_markers` (both files present →
  both gone, exit 0, two stderr lines), `test_clear_markers_is_a_noop_without_markers`
  (exit 0, empty stderr), `test_clear_cap_still_leaves_handoff_requested`
  (back-compat), `test_inherited_markers_match_handoff_markers`; the first is
  watched red against the pre-change code (unknown flag exits 2).

### Phase 1: Phase 0 prose
**Goal**: every session starts clean.

**Tasks**:
- [ ] Add the unconditional `--clear-markers` call to Phase 0 and simplify the
  cap-rotation bullet (depends on: Phase 0) - Acceptance:
  `test_custody_prose.py::test_phase_0_clears_inherited_markers_before_the_abort_handlers`
  pins `_walk_up.py --clear-markers` between the lifecycle `mkdir` sentence and
  `### Handle park request`, and asserts `--clear-cap` no longer appears in
  `phase-build.md`; `skills/work/scripts/test_handoff_placement_prose.py`
  (which pins `_walk_up.py --clear-cap` in the abort handler) is updated to the
  new flag in the same task; CHANGELOG `### Fixed` entry under
  `**run-autopilot**`.

**Exit Criteria**: suites green; release-checks green.

## Test Strategy

### Critical Scenarios
- **Happy path**: both markers present at session start → removed, logged.
- **Edge case**: only `.cap-fired` present → removed; `--clear-cap` on a dir
  with both → only `.cap-fired` removed.
- **Error case**: no autopilot dir above cwd → exit 0, nothing printed.

## Risks

- **A live marker written by this session's hook before Phase 0**: the hook
  fires on tool calls after the session's first read; Phase 0's clear is the
  session's first Bash call, so nothing this session wrote can precede it.
  Accepted.

### Deferred

Review 1 (2026-09-21, 6 findings, 0 CRITICAL / 0 HIGH, converged; three Mediums fixed
after the review, unreviewed: a failed unlink is now reported on stderr, the
lone-`.cap-fired` case and the two-line `written <timestamp>` shape are pinned):

- [Medium] `phase-build.md` § Clear inherited hand-off markers carries the dated incident in the hot path; move the anecdote to `design-rationale.md` and keep the invariant (Bob)
- [Medium] `test_clear_cap_still_leaves_handoff_requested` passes against the pre-change code - it pins back-compat by design; a contrast with `--clear-markers` in the same test would bind it (Bob, mech-check)
- [Low] Bob's VERIFY: `test_walk_up.py`, `test_custody_prose.py` and `release-checks` green at HEAD (answered)

