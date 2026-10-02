---
catchup: skip
design: run
default_model: opus
model_tier_rationale: the root cause of the parallel failures is unknown (diagnosis before any fix), and the fix may touch fixtures shared by every wave test file
---

# Run the test suites in parallel

Source: `dev/local/notes/review-time-analysis-2026-09-30.md` R2 (parallel
half). The narrow-run half is PRD 00232.

## Overview

### Problem Statement

The full `skills/run-autopilot/cli` suite takes about 4 min serially, and it
is the tail of every gate: step 7's full run, `dev/bin/release-checks`, the
review cycle's test line. Measured 2026-09-30 at `d000753`:
`uv run --with pytest --with pytest-xdist pytest -n auto cli` finished in
87 s against about 240 s serial.

Two parallel runs each failed 7-8 tests, a different set each time and all
from the wave family (`test_wave_launch*.py`, `test_wave_assemble*.py`,
`test_wave_review*.py`, `test_wave_cli_refusals.py`). All of them passed
serially (`10 passed in 7.44s`). The wave tests share something between
workers. The fixtures use `tmp_path` and `monkeypatch.chdir`, so the shared
state is elsewhere. Candidates, unverified (guess): wave ids minted from the
wall-clock minute colliding across workers, a worktree or branch path derived
outside `tmp_path`, a git lock or global config, or a `~/.claude` path read
through `Path.home()`.

### Target Users

Every gate that runs the full suite: `/autopilot:work` step 7, the review
cycle, `dev/bin/release-checks`.

### Success Metrics

- `uv run --no-project --with pytest --with pytest-xdist python -m pytest -q -n auto skills/run-autopilot/cli`
  green on three consecutive runs.
- `bash dev/bin/release-checks` green, and its run-autopilot `cli` block
  passes `-n auto`.
- The same `cli` block finishes in under half its serial time on this host
  (measured before and after in the design doc).

## Functional Decomposition

### Capability: The wave tests are worker-safe

#### Feature: Find the shared state
- **Description**: identify what two workers share.
- **Inputs**: the wave test files and their fixtures
  (`test_wave_launch.py::_repo`, `_planned`, and the helpers the other wave
  files import from it).
- **Outputs**: a `## Root cause` section in the design doc naming the shared
  resource with a reproducing command (two tests that fail together under
  `-n 2` and pass alone).
- **Behavior**: the design step runs the family under `-n auto` with
  `-p no:randomly --dist loadfile` and without, and bisects to the smallest
  failing pair. Fixing anything before this section exists is out of order.

#### Feature: Isolate it
- **Description**: remove the sharing at its source.
- **Inputs**: the root cause.
- **Outputs**: fixture or production changes that give each test its own
  copy of the resource (a per-test id, `HOME`, git config or path under
  `tmp_path`).
- **Behavior**: prefer isolating the fixture over serializing tests. An
  `xdist_group` marker plus `--dist loadgroup` is the fallback only when the
  resource is genuinely global (for example the real `~/.claude`), and the
  design doc says why.

### Capability: The gates run in parallel

#### Feature: release-checks passes `-n auto`
- **Description**: the release gate's pytest calls use parallel workers.
- **Inputs**: `dev/bin/release-checks`.
- **Outputs**: `--with pytest-xdist` and `-n auto` on each `python -m pytest`
  line whose suite is proven worker-safe by three consecutive green runs.
  Suites not proven stay serial, and a comment names them.
- **Behavior**: `skills/work/references/final-verification.md`'s Python
  suite line (`pytest`) gains "with `-n auto` when the project's tests are
  worker-safe (its release gate already passes it)".

## Structural Decomposition

### Repository Structure

```
skills/run-autopilot/cli/test_wave_launch.py      # Maps to: Isolate it (shared fixtures)
skills/run-autopilot/cli/test_wave_*.py           # Maps to: Isolate it (as the root cause requires)
skills/run-autopilot/cli/test_parallel_safety.py  # Maps to: Test Strategy (the reproducing pair)
dev/bin/release-checks                            # Maps to: release-checks passes -n auto
skills/work/references/final-verification.md      # the -n auto sentence
CHANGELOG.md
```

### Module: wave test fixtures
- **Maps to capability**: The wave tests are worker-safe
- **Responsibility**: every wave test gets resources no other worker can
  reach.
- **Exports**: the fixtures the wave test files already import (names
  unchanged).

## Dependency Graph

### Foundation Layer (Phase 0)
No dependencies - built first.

- **root cause**: the design doc section and its reproducing pair.

### Core Layer (Phase 1)
- **fixture isolation**: Depends on [root cause].

### Integration Layer (Phase 2)
- **release-checks and final-verification prose, CHANGELOG**: Depends on
  [fixture isolation].

## Implementation Phases

### Phase 0: Foundation
**Goal**: the sharing is named and reproducible.

**Tasks**:
- [ ] Add `test_parallel_safety.py` holding the reproducing pair from the
  design doc's `## Root cause` as a test that runs the pair under `-n 2` via
  `pytest.main` in a subprocess and asserts both pass (no deps) - Acceptance:
  `test_parallel_safety.py::test_the_wave_pair_passes_under_two_workers`
  fails at the base commit (fail-first recorded in the task's attempt entry).

**Exit Criteria**: the new test is red for the documented reason.

### Phase 1: Core
**Goal**: the wave family is worker-safe.

**Tasks**:
- [ ] Isolate the shared resource in the fixtures (depends on: Phase 0) -
  Acceptance: `test_parallel_safety.py::test_the_wave_pair_passes_under_two_workers`
  green; `uv run --no-project --with pytest --with pytest-xdist python -m
  pytest -q -n auto skills/run-autopilot/cli` green on three consecutive
  runs; the serial run of the same directory green.

**Exit Criteria**: three consecutive green parallel runs.

### Phase 2: Integration
**Goal**: the gates use it.

**Tasks**:
- [ ] Pass `--with pytest-xdist` and `-n auto` in `dev/bin/release-checks`
  for the proven suites, add the final-verification sentence, CHANGELOG
  `### Changed` `**run-autopilot**` line (depends on: Phase 1) - Acceptance:
  `bash dev/bin/release-checks` green twice in a row; `rg -c "\-n auto"
  dev/bin/release-checks` prints at least 1.

**Exit Criteria**: `release-checks` green twice.

## Test Strategy

### Critical Scenarios
- **Happy path**: `-n auto` over `cli/` green three times, under half the
  serial time.
- **Edge case**: a suite that stays flaky under workers stays serial in
  `release-checks`, and the comment names it.
- **Error case**: the reproducing pair regresses (someone reintroduces the
  shared resource) and `test_parallel_safety.py` fails naming the pair.

## Risks

- **A flaky parallel gate is worse than a slow one**: nothing goes parallel
  without three consecutive green runs, and the serial run stays the
  fallback per suite.
- **The shared resource is production state, not a fixture**: if the root
  cause is in `cli/wave*.py` (for example ids from the wall-clock minute),
  the fix is a production change. The design doc says so and the task tier
  stays opus.
