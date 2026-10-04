---
catchup: skip
design: skip
default_model: sonnet
model_tier_rationale: four small fixes with exact targets (a module move, two table rows, one fail-loud guard plus one pathspec prefix); each has a named failing test
---

# Tidy the enter verb and the review diff plumbing

Source: attended triage on 2026-10-03, checked against HEAD. Ledger trail:

- 00234 `d799b85ccee1` (batch `202609252154`)
- 00235 `f9c890a6856c` (batch `202609252154`)
- 00237 `b11361de7d00` (batch `202609252154`)
- 00238 `9f75f53ae7f7` (batch `202610021244`)

## Overview

### Problem Statement

Four small defects survive from the 00223 and 00236 reviews:

- **00234:** `cli/enter.py` is 427 lines, against 00223's exit criterion of
  under 400.
- **00235:** `references/phase-build.md`'s enter stop table routes `fs_error`
  only to the `mkdir -p` block and `park_halt` only to exit-code row 5. But
  `fs_error` also fires when `--prds` is too shallow and when the design doc
  can't be read, and `park_halt` also fires on an unmapped park exit code.
- **00237:** `review-work-completion/scripts/gather-context.sh` diffs against
  the detected base branch on a full review. In a repo that works directly on
  master, that diff is empty at a clean HEAD, so cycle-1 reviewers get
  nothing to review. The 00216 review worked around it with `--since
  <work_start_sha>`, but nothing documents that.
- **00238:** `cli/lane_check.diff_signal` excludes the store with the
  unprefixed `STORE_EXCLUDE_PATHSPECS` and `cwd=repo_root`. In a
  bare-repo-backed project (`~/.claude`, where the store sits at
  `.claude/docs/dev/project-management` under a `$HOME` work tree) that
  misses the store, so store commits read as production paths and every
  solo-lane PRD escalates to the full lane. `foreign_dirty` and
  `record_store` already derive the prefix with `store_tree._store_prefix`.

### Target Users

Every build session (`enter`), every review cycle (`gather-context.sh`), and
lane routing in bare-repo projects.

### Success Metrics

- `uv run --no-project --with pytest python -m pytest -q skills/run-autopilot/cli -k "enter or lane_check"`
  and `bash skills/review-work-completion/scripts/test_gather_context_id.sh`
  green.
- `wc -l skills/run-autopilot/cli/enter.py` under 400; `bash
  dev/bin/release-checks` green.

## Functional Decomposition

### Capability: enter is within its limits and documents its stops

#### Feature: Move enter's side-effect helpers out
- **Description**: `enter.py` drops under 400 lines with no behavior change.
- **Outputs**: new `cli/enter_io.py` holding `_git_head_sha`,
  `_record_resume_row` and `_review_log_has_dispatch_line` (renamed without
  the leading underscore). `enter.py` imports them.
- **Behavior**: every existing enter test passes unchanged except
  monkeypatch targets, which move to `cli.enter_io`.

#### Feature: Stop rows name every owner
- **Description**: the two stop-table rows say how `detail` picks the owning
  section.
- **Outputs**: in `phase-build.md` § Enter in one call:
  - The `fs_error` row reads "§ Ensure lifecycle directories exist when
    `detail` names the `mkdir`; the `--prds` flag when `detail` names a
    shallow path; the design-gate invariant's non-zero branch when `detail`
    names the design doc".
  - The `park_halt` row reads "§ Handle park request: exit-code row 5 when
    `detail` says systemic halt, otherwise the row matching the exit code
    `detail` names".

### Capability: Review diffs are never silently empty

#### Feature: A full review diffs from the PRD's start
- **Description**: `gather-context.sh` refuses an empty full-review diff,
  and the review skill always passes the PRD's start.
- **Outputs**:
  - When the resolved diff is empty and no `--since` was given, the script
    prints `gather-context: empty diff against <base>; pass --since
    <work_start_sha> for a full review` on stderr and exits 3.
  - `review-work-completion/SKILL.md`'s full-review gather step passes
    `--since <state.work_start_sha>`.

### Capability: Lane routing ignores the store in every layout

#### Feature: Prefix the store exclusion
- **Description**: `diff_signal` excludes the store wherever it sits.
- **Outputs**: `lane_check.diff_signal` builds its exclusion as
  `":(exclude,top)" + store_tree._store_prefix(repo_root, store_dir) +
  root.removesuffix("/")` for each `STORE_PREFIXES` root. `store_dir` is the
  resolved autopilot dir's parent, the same argument `foreign_dirty` gets.
- **Behavior**: the flat layout is unchanged.

## Structural Decomposition

### Repository Structure

```
skills/run-autopilot/cli/
├── enter.py, enter_io.py                    # Maps to: Move enter's side-effect helpers out
├── lane_check.py                            # Maps to: Prefix the store exclusion
└── test_enter*.py, test_lane_check*.py      # moved patch targets; new tests
skills/run-autopilot/references/phase-build.md            # Stop rows name every owner
skills/review-work-completion/scripts/gather-context.sh   # empty-diff refusal
skills/review-work-completion/scripts/test_gather_context_id.sh
skills/review-work-completion/SKILL.md                    # --since on full review
CHANGELOG.md
```

### Module: enter_io
- **Maps to capability**: enter is within its limits
- **Responsibility**: the verb's git, telemetry and review-log reads.
- **Exports**: `git_head_sha`, `record_resume_row`,
  `review_log_has_dispatch_line`.

## Dependency Graph

### Foundation Layer (Phase 0)
No dependencies - built first.

- **enter_io split; lane_check prefix; gather-context guard**: independent.

### Core Layer (Phase 1)
- **stop rows and the SKILL.md `--since` line**: Depends on [the Phase 0
  code they describe].

### Integration Layer (Phase 2)
- **CHANGELOG**: Depends on [Phase 1].

## Implementation Phases

### Phase 0: Foundation
**Goal**: the three code fixes.

**Tasks**:
- [ ] Move the three helpers to `cli/enter_io.py` (no deps) - Acceptance:
  `wc -l skills/run-autopilot/cli/enter.py` under 400; every `test_enter*.py`
  green.
- [ ] Prefix the store exclusion in `lane_check.diff_signal` (no deps) -
  Acceptance: `test_lane_check.py::test_bare_repo_store_commits_are_not_production_paths`
  (a `--git-dir`/`--work-tree` fixture with the store under `.claude/`) green
  and red before the change; the flat-layout lane tests green.
- [ ] Refuse an empty full-review diff in `gather-context.sh` (no deps) -
  Acceptance: a new scenario in `test_gather_context_id.sh` (clean master,
  no `--since` → exit 3 and the message; with `--since <sha>` → a non-empty
  diff) passes.

**Exit Criteria**: all three green.

### Phase 1: Core
**Goal**: the prose matches the code.

**Tasks**:
- [ ] Rewrite the `fs_error` and `park_halt` rows and add `--since
  <state.work_start_sha>` to the full-review gather step (depends on:
  Phase 0) - Acceptance: `test_enter_prose.py::test_fs_error_row_names_every_owner`
  and `::test_park_halt_row_routes_by_exit_code` green; `rg -c "\-\-since
  <state.work_start_sha>" skills/review-work-completion/SKILL.md` prints at
  least 1.

**Exit Criteria**: prose tests green.

### Phase 2: Integration
**Goal**: shipped.

**Tasks**:
- [ ] `CHANGELOG.md` `[Unreleased]` `### Fixed` lines for
  `**review-work-completion**` (empty full-review diff refused) and
  `**run-autopilot**` (lane routing ignores the store in bare-repo projects)
  (depends on: Phase 1) - Acceptance: `bash dev/bin/release-checks` green.

**Exit Criteria**: `release-checks` green.

## Test Strategy

### Critical Scenarios
- **Happy path**: a full review on master with `--since <work_start_sha>`
  gets the PRD's whole diff.
- **Edge case**: `~/.claude`-style bare repo → a solo PRD with only store
  commits stays solo.
- **Error case**: a full review without `--since` at a clean HEAD → exit 3,
  never an empty review.

## Risks

- **Exit 3 breaks an existing caller**: the only callers are the review
  skill's own steps, and an incremental review already passes `--since`.
