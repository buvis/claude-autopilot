---
catchup: skip
design: skip
default_model: sonnet
model_tier_rationale: transcription - one parameter, one comparison and one git flag, each pinned by a named test that fails at base
---

# Bind gate reuse to the command and to renames

## Problem

The 2026-10-06 agoge run (`docs/dev/project-management/audit-results/agoge-2026-10-06.md`,
findings 6 and 9, MEDIUM, confirmed; both live in v0.9.0):

- **#6:** `verification.reuse_verdict` (`skills/run-autopilot/cli/verification.py:93`)
  never compares the requested gate command with the one recorded in
  `last-verification.json`. A committed record from command `true` made
  `review-stage --gate-command "<a real gate>"` report `verdict: reused`,
  `Tests: 4242 passed`, and the requested gate never ran.
- **#9:** `_ancestor_and_clean` (`verification.py:74-80`) lists changed paths
  with `git log --name-only`, which names a committed rename by its new path
  only. A product file moved into the store tree reads as a store-only change,
  so a stale green record is reused.

Operator decision (2026-10-06): apply the recommended fixes.

## Solution

`reuse_verdict` takes the requested command and returns `stale` unless the
record's `commands[0].command` equals it; the `git log` call gains
`--no-renames`.

## Requirements

### Must have
- A record whose command differs from the requested one is `stale`.
- A committed rename from a product path into the store is `stale`.

### Nice to have
- None.

## Implementation

### Module: verification
- **Location**: `skills/run-autopilot/cli/verification.py`
- **Responsibility**: decide gate reuse
- **Exports**: `reuse_verdict(record, repo_root, head_sha, gate_command)` (new required parameter)

### Module: review_stage
- **Location**: `skills/run-autopilot/cli/review_stage.py`
- **Responsibility**: pass `--gate-command` through to `reuse_verdict` (call at line 351)
- **Exports**: none new

### Dependencies
- verification: No dependencies (foundation)
- review_stage: Depends on [verification]

## Tasks

### Phase 0: Foundation
- [ ] verification: add a `gate_command: str` parameter to `reuse_verdict`; return `("stale", ...)` when `record["commands"][0]["command"] != gate_command`; add `"--no-renames"` to the `git log` call in `_ancestor_and_clean` - Acceptance: `test_reuse_is_stale_when_the_gate_command_differs` and `test_committed_rename_into_the_store_is_stale` pass in `skills/run-autopilot/cli/test_verification.py`, and both fail at base.

### Phase 1: Core
- [ ] review_stage: pass the `--gate-command` value to `reuse_verdict` (depends on: Phase 0) - Acceptance: `test_stage_runs_the_gate_when_the_recorded_command_differs` passes in `skills/run-autopilot/cli/test_review_stage.py`.

## Success Criteria

- `test_reuse_is_stale_when_the_gate_command_differs`, `test_committed_rename_into_the_store_is_stale` and `test_stage_runs_the_gate_when_the_recorded_command_differs` pass.
- `bash dev/bin/release-checks` exits 0.
