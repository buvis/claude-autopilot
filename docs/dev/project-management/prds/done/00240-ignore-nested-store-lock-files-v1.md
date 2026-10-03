---
catchup: skip
design: skip
default_model: sonnet
model_tier_rationale: one pattern changed in two places that a parity test already binds, plus one real-git test; exact text given
---

# Ignore nested store lock files

Source: `docs/dev/project-management/notes/review-time-analysis-2026-09-30.md`
§ Follow-ups ("nested lock files"). Grounded at v0.7.0.

## Overview

### Problem Statement

`cli/store_tree.STORE_GITIGNORE` lists `autopilot/*.lock`. Git matches that
pattern one directory deep only, so the flock files beside the deferred
records (`autopilot/deferred/<batch>-deferred.json.lock`) are not ignored.
Committing the store on 2026-10-03 would have published four empty lock files.
claude-autopilot works around it with a root `.gitignore` line
(`docs/dev/project-management/**/*.lock`). Every other repo that tracks its
store commits the locks.

### Target Users

Every repo whose store `.gitignore` is written by `autopilot ensure-store`.

### Success Metrics

- `uv run --no-project --with pytest python -m pytest -q skills/run-autopilot/cli -k "store_gitignore or nested_lock"`
  green; the existing Retention parity test green.
- `bash dev/bin/release-checks` green.

## Functional Decomposition

### Capability: Every store lock file is ignored

#### Feature: A recursive lock pattern
- **Description**: one pattern covers lock files at any depth under
  `autopilot/`.
- **Inputs**: none.
- **Outputs**: `STORE_GITIGNORE` line 3 reads `autopilot/**/*.lock` (was
  `autopilot/*.lock`). In `skills/run-autopilot/SKILL.md` § Retention, the
  Disposable entry `` `docs/dev/project-management/autopilot/*.lock` `` reads
  `` `docs/dev/project-management/autopilot/**/*.lock` (the flock files beside
  `state.json` and beside each `deferred/*.json`) ``.
- **Behavior**: `ensure-store` rewrites an existing store `.gitignore`
  whenever it differs, so every repo picks the change up at its next Phase 0.
  In claude-autopilot, the root `.gitignore` line
  `docs/dev/project-management/**/*.lock` is removed in the same task, since
  the store's own file now covers it.

## Structural Decomposition

### Repository Structure

```
skills/run-autopilot/cli/store_tree.py           # Maps to: A recursive lock pattern
skills/run-autopilot/cli/test_store_tree_*.py    # Maps to: Test Strategy (the file holding the ensure-store tests)
skills/run-autopilot/SKILL.md                    # Retention Disposable entry
.gitignore                                       # drop the workaround line
CHANGELOG.md
```

### Module: store_tree
- **Maps to capability**: Every store lock file is ignored
- **Responsibility**: the store's ignore list.
- **Exports**: `STORE_GITIGNORE` (one line changed).

## Dependency Graph

### Foundation Layer (Phase 0)
No dependencies - built first.

- **store_tree pattern and the SKILL.md entry**: one change in two bound
  places.

### Core Layer (Phase 1)
- **the real-git test**: Depends on [store_tree pattern].

### Integration Layer (Phase 2)
- **root .gitignore cleanup and CHANGELOG**: Depends on [the real-git test].

## Implementation Phases

### Phase 0: Foundation
**Goal**: the pattern is recursive.

**Tasks**:
- [ ] Change `autopilot/*.lock` to `autopilot/**/*.lock` in `STORE_GITIGNORE`
  and in the SKILL.md Retention entry, with the parenthetical above (no deps) -
  Acceptance: `rg -c "autopilot/\*\*/\*\.lock" skills/run-autopilot/cli/store_tree.py skills/run-autopilot/SKILL.md`
  prints 1 per file; the existing `test_store_gitignore_matches_the_disposable_list`
  green.

**Exit Criteria**: the parity test green.

### Phase 1: Core
**Goal**: proven against real git.

**Tasks**:
- [ ] Add `test_nested_lock_files_are_ignored` beside the ensure-store tests:
  in a `tmp_path` git repo, run `ensure_store_gitignore(store)`, create
  `autopilot/state.json.lock` and `autopilot/deferred/b-deferred.json.lock`
  and `autopilot/deferred/b-deferred.json`, and assert `git status
  --porcelain --untracked-files=all` lists the `.json` file and neither lock
  (depends on: Phase 0) - Acceptance: the test is green, and red against
  `autopilot/*.lock` (fail-first recorded in the attempt entry).

**Exit Criteria**: the new test green.

### Phase 2: Integration
**Goal**: shipped.

**Tasks**:
- [ ] Remove `docs/dev/project-management/**/*.lock` from the repo root
  `.gitignore`, run `autopilot ensure-store` once in this repo so the store's
  file carries the new pattern, and add a `CHANGELOG.md` `[Unreleased]`
  `### Fixed` `**run-autopilot**` line: nested store lock files such as
  `deferred/*.json.lock` are now ignored (depends on: Phase 1) - Acceptance:
  `git status --porcelain` empty after the run; `git check-ignore -q
  docs/dev/project-management/autopilot/deferred/x.json.lock` exits 0; `bash
  dev/bin/release-checks` green.

**Exit Criteria**: `release-checks` green.

## Test Strategy

### Critical Scenarios
- **Happy path**: a deferred record's lock file is never listed by `git
  status`.
- **Edge case**: an existing store `.gitignore` with the old pattern is
  rewritten by `ensure-store` (it differs from `STORE_GITIGNORE`).
- **Error case**: a `.json` beside the lock is still listed, so the pattern
  did not swallow real records.

## Risks

- **Lock files already committed in another repo**: `.gitignore` does not
  untrack them. They are empty flock targets, so leaving them is harmless,
  and `git rm --cached` can remove them where they appear.
