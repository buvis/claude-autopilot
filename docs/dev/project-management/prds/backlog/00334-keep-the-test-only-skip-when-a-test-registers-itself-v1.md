---
design: skip
default_model: sonnet
model_tier_rationale: one tuple constant, one predicate line and one prose sentence with their exact text, additive tests beside the existing test-path cases
---

# Keep the test-only skip when a test registers itself

Source: batch 202610161547, PRD 00320 task 1 (2026-10-16, session cdf17745): a tests-first task whose diff was `skills/run-autopilot/cli/test_verify_log_refusal.py` plus `dev/bin/release-checks`.

## Problem

`/autopilot:work` already skips self-deslop and the Pat review for a test-only task: step 5.7 (`skills/work/SKILL.md:418`) applies `test_only_gate` (`skills/work/scripts/work_routing.py:252-263`) to `git diff --name-only <task_base_sha>..HEAD`, and `test_only_diff` (`skills/work/scripts/work_routing.py:247-249`) is true only when every path satisfies `is_test_path` (`skills/work/scripts/work_routing.py:233-244`).

But this repository requires every new test file to be registered in a `[checks]` block of `dev/bin/release-checks`, and the PRD template's Phase 0 task does exactly that (00320's did), so a tests-first task's diff is one test file plus one production path and both skips are lost. Measured on 00320 task 1: the test file landed at 14:21:42Z; a self-deslop dispatch, a Pat dispatch with three MEDIUM findings, an implementor retry and a Pat re-run followed, and the attempt record closed at 14:30:39Z. Nine of the task's fifteen minutes, two sonnet-run calls and two worker dispatches went into reviewing a file the next task existed to make pass; `test_only_gate`'s own prose (`skills/work/references/per-task-review.md:13-24`) names that as the case the skip exists for.

## Solution

Treat the release gate's registration file as test infrastructure in the predicate. `work_routing.py` gains `_TEST_INFRA_PATHS = ("dev/bin/release-checks",)` beside the `_TEST_DIR_SEGMENTS` and `_TEST_BASENAME_GLOBS` tuples, and `is_test_path` returns True for an exact match before the segment and basename checks. `test_only_diff` and `test_only_gate` are unchanged. One sentence in `per-task-review.md` § Test-only diffs names the rule. The release gate's own structure stays guarded by `skills/run-autopilot/cli/test_release_checks_counts.py`, and the PRD-level review lenses see the registration like every other diff.

## Requirements

### Must have
- `is_test_path("dev/bin/release-checks")` is True; `is_test_path("dev/bin/release")` and `is_test_path("skills/run-autopilot/cli/release_checks.py")` stay False.
- `test_only_gate(["skills/run-autopilot/cli/test_x.py", "dev/bin/release-checks"], in_rework=False)` returns both skip stamps.
- `skills/work/references/per-task-review.md` § Test-only diffs gains the sentence: `dev/bin/release-checks` counts as test code here: a tests-first task registers its new file in a `[checks]` block, and that edit alone must not buy the file a review the implementation task repeats.`
- Fail-first tests in `skills/work/scripts/test_work_routing.py` (registered under `[checks] work scripts remainder`, `dev/bin/release-checks:510`).
- A CHANGELOG `[Unreleased]` Fixed entry under **work**.

### Nice to have
- None.

## Implementation

### Module: test-infra-path
- **Location**: `skills/work/scripts/work_routing.py` (`is_test_path`)
- **Responsibility**: the release gate's registration file is test infrastructure for the test-only skips
- **Exports**: `is_test_path()`, `test_only_diff()`, `test_only_gate()` (unchanged signatures)
- New symbols: `_TEST_INFRA_PATHS`

### Module: test-infra-path-tests
- **Location**: `skills/work/scripts/test_work_routing.py`, `skills/work/references/per-task-review.md`
- **Responsibility**: pin the new path and its near misses
- **Exports**: none
- New symbols: `test_release_checks_registration_is_a_test_path`, `test_release_checks_near_misses_stay_production`, `test_a_test_with_its_registration_still_skips_both_lanes`

### Dependencies
- test-infra-path-tests: No dependencies (foundation)
- test-infra-path: Depends on [test-infra-path-tests]

## Tasks

### Phase 0: Foundation
- [ ] Add three tests beside `test_directory_segments_and_basename_patterns_are_test_paths` (`skills/work/scripts/test_work_routing.py:1097`): `test_release_checks_registration_is_a_test_path` asserts `work_routing.is_test_path("dev/bin/release-checks") is True`; `test_release_checks_near_misses_stay_production` asserts False for `dev/bin/release` and `skills/run-autopilot/cli/release_checks.py`; `test_a_test_with_its_registration_still_skips_both_lanes` asserts `work_routing.test_only_gate(["skills/run-autopilot/cli/test_x.py", "dev/bin/release-checks"], in_rework=False) == {"self_deslop": "skipped:test-only", "review": "skipped:test-only"}` - Acceptance: `uv run --no-project --with pytest python -m pytest -q skills/work/scripts/test_work_routing.py -k "release_checks or its_registration"` reports two tests failing and `test_release_checks_near_misses_stay_production` passing at the task's base commit.

### Phase 1: Core
- [ ] In `skills/work/scripts/work_routing.py` add `_TEST_INFRA_PATHS = ("dev/bin/release-checks",)` beside the test-path tuples and make `is_test_path` begin with `if path in _TEST_INFRA_PATHS: return True`; add the sentence from Requirements to `skills/work/references/per-task-review.md` § Test-only diffs after its first paragraph (depends on: Phase 0) - Acceptance: `uv run --no-project --with pytest python -m pytest -q skills/work/scripts/test_work_routing.py skills/work/scripts/test_work_routing_attempt_outcome.py skills/work/scripts/test_work_routing_ladder_fence.py` passes; `rg -c 'counts as test code here' skills/work/references/per-task-review.md` prints 1.
- [ ] Add the CHANGELOG `[Unreleased]` Fixed entry `**work**: a tests-first task that registers its file in dev/bin/release-checks keeps the test-only skip of self-deslop and the per-task review` (depends on: Phase 1) - Acceptance: `rg -c 'keeps the test-only skip' CHANGELOG.md` prints 1.

## Success Criteria

- The next tests-first task whose diff is one test file plus `dev/bin/release-checks` records `review: skipped:test-only` and `self_deslop: skipped:test-only` in its attempt record.
- `test_work_routing.py` is green.
