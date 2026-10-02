---
catchup: force
design: run
default_model: opus
model_tier_rationale: behaviour-preserving split of the loop core; reviewed seams, test inventory and goldens define equivalence
rework_cap: 3
---

# Split cli/loop.py and test_loop.py under the file cap

Source: PRD 00181 review, Alice R13, and the config-audit closure walkthrough (`~/.claude/dev/local/audit-results/2026-09-05.md`). The 800-line standing file cap was deferred because the loop split exceeded that PRD's scope.

## Overview

### Problem Statement
`skills/run-autopilot/cli/loop.py` and `test_loop.py` exceed the 800-line cap (1384 and 1440 at backlog review). They combine session spawning/metrics, the decision table, usage-limit waits, registry/markers and drained-path work. Earlier backlog PRDs add convergence metrics (00188) and lifecycle cleanup (00191); the split must retain their completed behavior and tests. Those changes may move the baseline, so capture it at execution time.

### Target Users
Future loop implementors and reviewers, who need each responsibility and its tests to fit in one readable module.

### Success Metrics
- At final completion, loop.py, test_loop.py and every sibling implementation/test module extracted by this PRD are under 800 lines.
- After every seam commit, the CLI suite passes and every file under cli/golden is byte-identical to the execution-time baseline.
- The collected test/case inventory and distinct assertions are preserved, with a mapping from old to new test locations.
- `bash dev/bin/release-checks` passes; the existing fixture loop build/review integration retains its state transitions.

### Non-Goals
- Behavior changes, renamed verbs/options, altered review lenses or context caps.
- Applying the cap to unrelated existing CLI files, including oversized __main__.py or test_state.py.
- Reshaping routing.py, records.py or state.py.

## Functional Decomposition

### Capability: Modules by responsibility
#### Feature: Reviewed seams with equivalent behavior
- **Description**: consume the Phase 1.5 reviewed design, which selects responsibility seams and exact sibling filenames before task planning.
- **Inputs**: execution-time loop.py, test_loop.py, import consumers and collected test inventory.
- **Outputs**: smaller sibling modules; loop.py keeps main() and the top-level loop, plus compatibility re-exports.
- **Behavior**: move responsibilities and their tests without changing behavior. Candidates are session spawning/metrics, decision/control flow, markers/registry and drained-path work. Necessary import, namespace, monkeypatch-target and fixture-location adaptations are allowed when equivalent; preserve distinct assertions. Lower-level seams do not import loop.py. Public names remain importable from loop.

## Structural Decomposition

### Repository Structure
```
skills/run-autopilot/cli/
├── loop.py                 # Maps to: loop driver
├── loop_*.py               # NEW: exact extracted names fixed in reviewed design
├── test_loop.py            # Maps to: equivalence verification
├── test_loop_*.py          # NEW: tests following the extracted seams
└── golden/                 # READ ONLY: baseline equivalence artifacts
```
The wildcard rows declare outputs, not a choice left to the work session. Phase 1.5 must produce the exact module/function/test map before plan-tasks creates Locations.

### Module: loop driver
- **Maps to capability**: Modules by responsibility
- **Responsibility**: loop.py retains the top-level loop and compatibility exports.
- **Exports**: every existing public name remains importable from loop.

### Module: extracted seams
- **Maps to capability**: Modules by responsibility
- **Responsibility**: the new loop-prefixed siblings named in the reviewed design; one responsibility per module.
- **Exports**: existing moved functions with equivalent contracts, re-exported by loop where needed.

### Module: equivalence verification
- **Maps to capability**: Modules by responsibility
- **Responsibility**: test_loop.py, newly extracted test siblings and read-only golden artifacts; preserve every baseline test and assertion.
- **Exports**: pytest tests and the old-to-new location inventory in the design document.

## Dependency Graph

### Foundation Layer (Phase 0)
- **equivalence verification**: capture the baseline and verify the reviewed design's exact map; no new implementation dependencies.

### Core Layer (Phase 1)
- **extracted seams**: follow the acyclic dependency order already approved by Phase 1.5.
- **loop driver**: depends on [extracted seams]; lower seams never import the driver.

### Integration Layer (Phase 2)
- **equivalence verification**: depends on [extracted seams, loop driver] for final size and release checks.

## Implementation Phases

### Phase 0: Baseline and reviewed map
**Goal**: bind moves to the reviewed design and execution-time behavior.
**Tasks**:
- [ ] Verify the existing Phase 1.5 design names each new module, moved function, test location and re-export; capture collection inventory and golden hashes (no deps). Premise: loop.py and test_loop.py still own the responsibilities above; recheck after earlier PRDs, skip/report a superseded split premise. Acceptance: the reviewed map is exact and acyclic, every baseline test has a destination, and CLI tests pass before moves; this task consumes the reviewed design rather than launching a second design cycle.
**Exit Criteria**: baseline inventory and reviewed move map are complete.

### Phase 1: Moves
**Goal**: extract one responsibility at a time with behavior intact.
**Tasks**:
- [ ] Move each seam with its tests, one commit per seam, preserving loop re-exports (depends on: Phase 0). Acceptance: after each commit, `uv run --no-project --with pytest --with rich --with textual python -m pytest -q skills/run-autopilot/cli` passes, the collected test/case inventory maps completely to the baseline, distinct assertions remain, and golden hashes are unchanged. Intermediate source files may still exceed 800 lines.
**Exit Criteria**: all reviewed seams are extracted and the CLI suite/goldens remain equivalent.

### Phase 2: Integration
**Goal**: verify the final split meets its bounded size target.
**Tasks**:
- [ ] Check final sizes, public imports, test inventory and fixture loop integration; run release-checks (depends on: Phase 1). Acceptance: loop.py, test_loop.py and the exact new siblings listed in the design are each under 800 lines; wrapper/CLI public imports still resolve; the existing build/review fixture has unchanged transitions; every baseline golden remains byte-identical; `bash dev/bin/release-checks` passes.
**Exit Criteria**: all Success Metrics hold; unrelated oversized CLI modules do not fail this PRD's size criterion.

## Test Strategy

### Critical Scenarios
- **Happy path**: all seams move, all baseline cases/assertions remain, goldens stay unchanged.
- **Edge case**: a wrapper or CLI import references a moved name → the re-export resolves it.
- **Error case**: a moved test loses parametrization or fixture behavior → inventory/equivalence checks fail even if the aggregate test count happens to match.

## Risks
- **Circular imports**: reviewed dependency order and one-way driver re-exports.
- **Moving monkeypatch targets changes behavior**: explicitly adapt namespace references, retaining the original assertions and fixture loop proof.
