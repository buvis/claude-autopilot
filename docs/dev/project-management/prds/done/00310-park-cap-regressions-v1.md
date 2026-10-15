---
catchup: run
design: run
default_model: opus
model_tier_rationale: invented predicate (which findings count as rework-introduced) and a new stall site that routes a PRD away from done
---

# Park a PRD at the rework cap when the last rework introduced a HIGH

Source: `docs/dev/project-management/audit-results/loop-efficiency-2026-10-13.md` (Q2); batch 202610111300 deferred ledger.

## Problem

With `rework_cap: 2` the second review cycle reviews the first cycle's rework but can fix nothing: every unresolved finding at the cap becomes a `cap-overflow` deferral (`skills/run-autopilot/references/phase-review.md:59`) and the PRD closes as `cap_deferred` (`skills/run-autopilot/cli/convergence.py:79-83`). In batch 202610111300 that ledger holds 57 cap-overflow records, 9 of them HIGH, and four of six PRDs closed this way. At least four of those HIGHs are regressions the cycle-1 rework itself introduced: 00276's rework removed the tracked-log refusal (verified destructive on HEAD), 00271's rework added a negation false-allow to the delegation guard, 00282's rework added a `UnicodeDecodeError` crash in `prd_spend_since` and a stale-replay path after a failed invalidation. Each shipped on master as a hold stub nobody reads until batch end.

Only a CRITICAL stalls the PRD today, through the `cap_critical` site (`skills/run-autopilot/references/phase-review.md:36`).

## Solution

Code decides whether a cap-time HIGH is a rework regression, and the cap-out branch stalls the PRD on that verdict exactly as it stalls on a CRITICAL. A new verb `autopilot cap-check --review-file <cycle N file> --previous <cycle N-1 file>` reads both files' `head_sha` frontmatter (`docs/dev/project-management/reviews/00282-loop-guards-v1-review-2.md:5` is the shape), takes the rework range `prev_head..head`, and classifies every consolidated row of severity high or critical: a row whose File cell carries a path and a line is a regression when `git blame -L line,line --porcelain <head> -- path` names a commit inside `git rev-list prev_head..head`; a row with a path and no line is a regression when the path appears in `git diff --name-only prev_head..head`; a row with no path is not a regression. The verb prints one JSON line per classified row and exits 1 when any regression row exists, 0 otherwise, 2 on unreadable input.

The cap-out prose routes exit 1 to the existing loop-mode stall procedure with the new site `cap_regression`: the same `records.do_stall` call as `cap_critical` (`skills/run-autopilot/cli/records.py:507-519`), which moves the PRD to `hold/` and lets `mint-stubs` run. Exit 0 keeps today's cap-overflow deferral. Nothing changes below the cap.

## Requirements

### Must have
- `cli/cap_check.py` with `classify_findings(repo_root, review_file, previous_review_file) -> list[dict]` (rows `{"ref", "severity", "file", "line", "regression", "commit"}`) and `rework_range(previous_head, head) -> tuple[str, str]`; the findings rows come from the same table parser `autopilot gate --findings` uses in `skills/run-autopilot/cli/gate.py`, never a second parser.
- The `cap-check` verb in `skills/run-autopilot/cli/__main__.py`: exit 1 when at least one row has `regression: true` and severity high or critical, 0 otherwise, 2 when a file, its `head_sha` line or a git call fails, with the reason on stderr.
- The cap-out branch at `skills/run-autopilot/references/phase-review.md:59` (the bullet that writes the `cap-overflow` records) runs `cap-check` first in loop mode; exit 1 -> stall with `site: "cap_regression"` and a `detail` listing the regression refs and their commits; exit 0 -> the existing cap-overflow deferral unchanged. `skills/run-autopilot/references/recovery.md` and `skills/run-autopilot/references/state-schema.md` list the `cap_regression` slug beside `cap_critical`.
- A cycle-1 cap (`rework_cap: 1`) or a missing previous review file classifies nothing (exit 0): there is no rework range.
- CHANGELOG `[Unreleased]` Added entry under **run-autopilot**.

### Nice to have
- `autopilot render report` prints `stalled: cap_regression` in the PRD's section the way it prints other stall sites.

## Implementation

### Module: cap-check
- **Location**: `skills/run-autopilot/cli/cap_check.py`, verb wiring in `skills/run-autopilot/cli/__main__.py`
- **Responsibility**: classify cap-time findings as rework-introduced or pre-existing from git, print the verdict, exit by it
- **Exports**: `classify_findings()`, `rework_range()`
- New symbols: `cap_check.py`, `classify_findings`, `rework_range`

### Module: cap-out-prose
- **Location**: `skills/run-autopilot/references/phase-review.md`, `skills/run-autopilot/references/recovery.md`, `skills/run-autopilot/references/state-schema.md`
- **Responsibility**: route the cap-out branch on the verb's exit code; document the `cap_regression` site
- **Exports**: none
- New symbols: `cap_regression`

### Module: cap-check-tests
- **Location**: `skills/run-autopilot/cli/test_cap_check.py`, `skills/run-autopilot/scripts/test_cap_regression_prose.py`
- **Responsibility**: pin the classification against a fixture repo and the prose routing
- **Exports**: none
- New symbols: `test_cap_check.py`, `test_cap_regression_prose.py`, `test_line_in_rework_commit_is_regression`, `test_line_outside_rework_range_is_not`, `test_file_without_line_added_by_rework_is_regression`, `test_medium_rows_are_not_classified`, `test_row_without_path_is_not_regression`, `test_exit_1_on_any_regression_and_0_otherwise`, `test_missing_previous_file_exits_0`, `test_unreadable_head_sha_exits_2`, `test_cap_out_runs_cap_check_before_deferring`, `test_exit_1_routes_to_cap_regression_stall`, `test_recovery_lists_cap_regression_slug`

### Dependencies
- cap-check-tests: No dependencies (foundation)
- cap-check: Depends on [cap-check-tests]
- cap-out-prose: Depends on [cap-check]

## Tasks

### Phase 0: Foundation
- [ ] Write `skills/run-autopilot/cli/test_cap_check.py` against a fixture repo: a base commit, then a rework commit that changes line 3 of file a.py and adds file b.py; two review files whose `head_sha` lines name the two commits and whose findings tables carry rows for a.py line 3 HIGH, a.py line 1 HIGH, b.py with no line HIGH, c.py line 1 MEDIUM, and a HIGH with no file. Tests: `test_line_in_rework_commit_is_regression`, `test_line_outside_rework_range_is_not`, `test_file_without_line_added_by_rework_is_regression`, `test_medium_rows_are_not_classified`, `test_row_without_path_is_not_regression`, `test_exit_1_on_any_regression_and_0_otherwise`, `test_missing_previous_file_exits_0`, `test_unreadable_head_sha_exits_2`. Register the file in a `[checks]` block of `dev/bin/release-checks` - Acceptance: `uv run --no-project --with pytest python -m pytest -q skills/run-autopilot/cli/test_cap_check.py` collects the eight tests and they fail on `ImportError` at the task's base commit; `rg -c 'test_cap_check.py' dev/bin/release-checks` prints 1.

### Phase 1: Core
- [ ] Implement `skills/run-autopilot/cli/cap_check.py` and the `cap-check` verb (depends on: Phase 0) - Acceptance: `uv run --no-project --with pytest python -m pytest -q skills/run-autopilot/cli/test_cap_check.py` passes all eight; `python3 skills/run-autopilot/cli/__main__.py cap-check --help` exits 0 and names `--review-file` and `--previous`.

### Phase 2: Integration
- [ ] Route the cap-out branch in `skills/run-autopilot/references/phase-review.md` (the loop-mode bullet that writes `cap-overflow` records) on `cap-check`, add the `cap_regression` slug to `skills/run-autopilot/references/recovery.md` and `skills/run-autopilot/references/state-schema.md` next to `cap_critical`, write `skills/run-autopilot/scripts/test_cap_regression_prose.py` (`test_cap_out_runs_cap_check_before_deferring`, `test_exit_1_routes_to_cap_regression_stall`, `test_recovery_lists_cap_regression_slug`), register it, and add the CHANGELOG entry (depends on: Phase 1) - Premise: `rg -c 'cap_critical' skills/run-autopilot/references/recovery.md` prints at least 1 at execution time; skip and report otherwise - Acceptance: `uv run --no-project --with pytest python -m pytest -q skills/run-autopilot/scripts/test_cap_regression_prose.py` passes; `rg -n 'cap_regression' CHANGELOG.md` prints one hit under `[Unreleased]`.

## Success Criteria

- Replaying the fixture of `test_cap_check.py` through the verb exits 1 and names the rework commit for the a.py line-3 row and the b.py row only.
- On the next batch, a PRD whose final cycle carries a rework-introduced HIGH lands in `prds/hold/` with a stall site of `cap_regression` instead of `prds/done/`, and its `review_converged` row is absent (the PRD never reached done).

## Closed 2026-10-15

Parked by its own rule at 13:28: the cycle-2 review session followed the checkout's `phase-review.md` (not the installed 0.9.0's), ran the checkout's `cap-check`, and stalled with `site: cap_regression` (R6 at `phase-review.md:59` introduced by 8b3a58f2, R7 at `cap_check.py:117` by b2d9a563). The code stays on master and is claimed on CHANGELOG line 19. The success criterion above held on the first try, on itself. The open HIGHs R5-R8, R1's `-z` half, and agoge-2026-10-15 packets 3, 4, 5, 23 and 27 go to PRD 00321 (v2), which also makes the stall record its rows in the ledger and mint a stub. Closed into `done/`.
