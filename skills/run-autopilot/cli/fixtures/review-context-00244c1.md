# Review Context

## Completed Tasks

_Trimmed for the render_roster golden tests: only the Diff scope line and the
mechanical blocks below feed a prompt (Eve's run inputs)._

## Code Changes

### Changed Files
_Diff scope: incremental review (changes since c704212975724ee445dca70ebf3fe6a983508fc8)_

## Mechanical facts (computed, do not re-count)

Function line counts from `ast`. Cite these for countable claims; a
finding that contradicts this block is discarded at the review gate.

- `skills/run-autopilot/cli/enter_io.py`
  - `git_head_sha` — line 31, 9 lines

## Tautological test shapes (computed, do not re-judge)

Each `[MECH]` line is a test whose shape cannot fail as written. Raise
it; step 6 adds any line the table lacks. `mech-check` is the finder.


Checked 91 test function(s) in 4 test file(s).

## Fail-first replay (computed, do not re-judge)

Touched tests from HEAD, run against the pre-change code at `c70421297572`
(HEAD's test files overlaid on a base worktree). A test that passes there
does not pin this change. A behavior-preserving refactor's tests pass by
design, so weigh the PRD's intent before raising one. `mech-check` is the finder.


Replay: 2 touched test(s) ran, 2 failed against base, 0 passed; 3 test file(s) could not be collected at base (their tests fail there). Command: uv run --no-project --with pytest python -m pytest

## Context Pack

Pack file: (no pack available this cycle)

### Findings precedent

(no pack available this cycle)

## Test gate

Tests: 12 passed, 0 failed, 0 skipped (suite run this cycle)
