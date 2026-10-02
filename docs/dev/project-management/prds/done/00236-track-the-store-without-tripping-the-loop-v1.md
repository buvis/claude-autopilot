---
catchup: skip
design: run
default_model: opus
model_tier_rationale: cross-cutting (about 16 clean-tree sites across run-autopilot, work, fast-track and the wave verbs) plus an invented commit contract at every handoff; a missed site either pauses every batch or commits a peer's work
---

# Track the store without tripping the loop

Source: operator decision 2026-09-30 ("this can be committed to public")
plus `docs/dev/project-management/notes/autoclaude-observation-2026-09-28.md`
O1. Grounded at `f550a2e` (v0.6.0).

## Overview

### Problem Statement

`rules/working-documents.md` says `docs/dev/project-management/` is tracked
and never gitignored, and v0.6.0 moved the store there. It is still
untracked: `/docs/` sits in `.git/info/exclude` in this repo and in
claude-plugins. The loop cannot live with a tracked store:

- **It rewrites the store every session without committing it**:
  `autopilot/state.json`, the metrics and ledger jsonl files, review files,
  PRD moves between `backlog/`, `wip/`, `done/` and `hold/`, and
  `meta/project-capsule.md`.
- **The stand-down procedure** (`skills/run-autopilot/SKILL.md` § Session
  Loop) stops a session when `git status --porcelain` "lists a tracked path
  this session did not edit". The next session sees the previous one's writes
  as exactly that, and pauses the batch.
- **About 16 other sites require a clean tree or read porcelain**, among them
  `work/references/task-boundary-handoff.md`, `work/references/rework-mode.md`,
  `work/references/gate-failure.md`, `fast-track/SKILL.md`, `cli/pause.py`
  and the `wave_launch`/`wave_assemble`/`wave_review` refusals. Each would
  refuse or stall on store churn.

A foreign writer in the checkout cost an 11-hour pause on 2026-09-28. A
tracked store without this PRD would cost a pause on every session.

### Target Users

The unattended loop, and the operator who wants the store's PRDs, designs and
reviews published with the repo.

### Success Metrics

- `uv run --no-project --with pytest python -m pytest -q skills/run-autopilot/cli/test_store_tree.py skills/run-autopilot/scripts/test_store_tree_prose.py`
  green; every existing suite green.
- `bash dev/bin/release-checks` green.
- Post-release signal: a batch run with the store tracked records no
  `stood_down_condition: dirty_tree` caused by a store path, and `git status
  --porcelain` is empty after every session's leave row.

## Functional Decomposition

### Capability: The store is never another writer's dirt

#### Feature: One predicate for "dirty"
- **Description**: every clean-tree check asks one function, which ignores
  the store.
- **Inputs**: repo root; `git status --porcelain -z` output.
- **Outputs**: `cli/store_tree.py` `foreign_dirty(repo) -> list[str]`, the
  porcelain paths outside `docs/dev/project-management/` and `docs/dev/tmp/`;
  and the CLI verb `autopilot dirty` printing one path per line, exit 0 when
  there are none and 1 when there are some.
- **Behavior**: paths are compared on the repo-relative, normalized path. A
  rename entry counts when either side is outside the store (guess). Every
  prose site that says "tree clean" or runs `git status --porcelain` for a
  gate is rewritten to run `autopilot dirty`. The design doc lists every site
  found by `rg -n -i "clean tree|tree clean|tree is clean|porcelain|dirty
  tree|dirty_tree"` over `skills/` and `hooks/`. Python sites (`pause.py` and
  the wave modules) import `foreign_dirty` instead of parsing porcelain
  themselves.

#### Feature: Volatile control files stay ignored
- **Description**: files that change on every tool call or exist only while
  a session runs are never tracked.
- **Inputs**: the Retention list in `SKILL.md`.
- **Outputs**: a `docs/dev/project-management/.gitignore` shipped by the
  pack's `mkdir` step (Phase 0 lifecycle directories), listing:
  `autopilot/state.json`, `autopilot/state.json.bak`, `autopilot/*.lock`,
  `autopilot/.turn-counts.json`, `autopilot/.handoff-requested`,
  `autopilot/.cap-fired`, `autopilot/.session-left`, `autopilot/lanes/`,
  `autopilot/wave-slots/`, `autopilot/last-session.log`,
  `autopilot/wrapper.log`, `autopilot/pause-requested`,
  `autopilot/paused-by-operator`, `autopilot/park-requested`,
  `autopilot/session-brief.md`, `autopilot/contract-card.md`,
  `autopilot/replan-context.md`, `autopilot/last-verification.json`.
- **Behavior**: the `SKILL.md` § Retention Disposable bullet names this file
  as the list's machine form. A test keeps the two in step.
- **Writer (operator decision 2026-10-02, after the `tooling_conflict`
  stall)**: the file is written by code, never by the Write or Edit tool.
  `hooks/enforce_prd_location.py` rejects a top-level store file outside its
  keeper list for editor tools only, and that refusal stays as is.
  `cli/store_tree.py` exports `STORE_GITIGNORE` (the pattern list above, in
  order, one per line) and `ensure_store_gitignore(store_dir) -> bool`, which
  writes `<store>/.gitignore` when it is missing or its content differs, and
  returns whether it wrote. The Phase 0 lifecycle-directories step calls it
  through a new verb `autopilot ensure-store` (run as its own Bash call right
  after the `mkdir -p`). The task that ships it also runs the verb once in
  this repo so the file exists before the parity test runs. Acceptance adds
  `test_store_tree.py::test_ensure_store_gitignore_writes_the_pattern_list`
  and `::test_ensure_store_gitignore_is_idempotent`, and the existing
  `test_store_gitignore_matches_the_disposable_list` compares `STORE_GITIGNORE`
  against the Disposable bullet.

### Capability: Each session commits its own store changes

#### Feature: Commit the store at the leave row
- **Description**: the session that wrote store files commits them before it
  leaves, so the next session starts clean.
- **Inputs**: the session handoff procedure, and the task-boundary and cap
  rotation handoffs.
- **Outputs**: one commit per handoff that has store changes: `git add -A --
  docs/dev/project-management` then `git commit -m "chore(autopilot): record
  <site> state for <prd stem>"` (guess on the wording; the design doc fixes
  it), with no push.
- **Behavior**: `SKILL.md` § Session handoff procedure gains a step between
  the brief and the leave row: run `autopilot record-store --site <site>
  --prd <state.prd>`, which stages only the store and commits when anything
  is staged (exit 0 either way; a commit failure prints one stderr line and
  never fails the handoff). The task-boundary handoff, the cap-rotation
  commit (`wip - rotated mid-task`) and the drained exit call the same verb.
  It never stages a path outside the store. A dirty path outside the store is
  left for `autopilot dirty` to report.

## Structural Decomposition

### Repository Structure

```
skills/run-autopilot/cli/
├── store_tree.py            # Maps to: One predicate for "dirty"; Commit the store at the leave row
├── __main__.py              # Maps to: `dirty` and `record-store` subparsers (thin)
├── pause.py, wave_launch.py, wave_assemble.py, wave_review.py   # Maps to: import foreign_dirty
└── test_store_tree.py       # Maps to: Test Strategy
skills/run-autopilot/scripts/
├── test_store_tree_prose.py # Maps to: every prose site
└── autopilot_context_cap_hook.py   # Maps to: the rotation handoff's record-store step
skills/run-autopilot/SKILL.md                                    # stand-down, handoff, Retention, Phase 0 mkdir
skills/run-autopilot/references/phase-build.md                    # Phase 0 lifecycle step
skills/work/references/task-boundary-handoff.md                   # steps 3e and 3h
skills/fast-track/SKILL.md                                       # the per-item foreign-dirt report
dev/bin/release-checks
CHANGELOG.md
```

### Module: store_tree
- **Maps to capability**: both
- **Responsibility**: the only code that knows where the store starts and
  what counts as foreign dirt.
- **Exports**:
  - `STORE_PREFIXES` - `("docs/dev/project-management/", "docs/dev/tmp/")`.
  - `foreign_dirty(repo, run_git=...) -> list[str]`.
  - `record_store(repo, site, prd, run_git=...) -> str | None` - the commit
    sha, or None when nothing was staged.

## Dependency Graph

### Foundation Layer (Phase 0)
No dependencies - built first.

- **store_tree**: pure over an injected `run_git`.

### Core Layer (Phase 1)
- **`dirty` and `record-store` verbs; Python call sites**: Depends on
  [store_tree].

### Integration Layer (Phase 2)
- **prose sites, the store .gitignore, prose tests, CHANGELOG**: Depends on
  [the verbs].

## Implementation Phases

### Phase 0: Foundation
**Goal**: the predicate and the recorder exist.

**Tasks**:
- [ ] Write `cli/store_tree.py` (no deps) - Acceptance:
  `test_store_tree.py::test_store_paths_are_never_foreign`,
  `::test_a_path_outside_the_store_is_foreign`,
  `::test_a_rename_out_of_the_store_is_foreign`,
  `::test_record_store_stages_only_the_store`,
  `::test_record_store_returns_none_when_nothing_changed`,
  `::test_record_store_survives_a_commit_failure` green.

**Exit Criteria**: `test_store_tree.py` green.

### Phase 1: Core
**Goal**: callable, and the Python sites use it.

**Tasks**:
- [ ] Add the `dirty` and `record-store` subparsers; switch `pause.py` and
  the wave modules to `foreign_dirty` (depends on: Phase 0) - Acceptance:
  `test_store_tree.py::test_cli_dirty_exits_one_on_foreign_paths`,
  `::test_cli_record_store_commits_with_the_site_and_prd` green; every
  existing `test_wave*.py` and `test_pause*.py` green (the refusals now
  ignore store churn and still refuse on a foreign path).

**Exit Criteria**: all cli suites green.

### Phase 2: Integration
**Goal**: every gate uses it, and the store can be tracked.

**Tasks**:
- [ ] Rewrite every prose site the design doc lists to `autopilot dirty`,
  add the `record-store` step to the handoff procedure, the task-boundary
  and rotation handoffs and the drained exit, ship the store `.gitignore`
  from the Phase 0 `mkdir` step, add `test_store_tree_prose.py` to
  `release-checks`, and the CHANGELOG `### Changed` `**run-autopilot**`
  entry (depends on: Phase 1) - Acceptance:
  `test_store_tree_prose.py::test_no_gate_parses_porcelain_by_hand` (no file
  under `skills/` outside `cli/store_tree.py` and tests contains `status
  --porcelain` as a gate instruction),
  `::test_stand_down_names_autopilot_dirty`,
  `::test_handoff_procedure_records_the_store_before_the_leave_row`,
  `::test_store_gitignore_matches_the_disposable_list` green; `bash
  dev/bin/release-checks` green.

**Exit Criteria**: `release-checks` green.

## Test Strategy

### Critical Scenarios
- **Happy path**: session A moves a PRD to `wip/`, writes reviews and metrics,
  runs `record-store` and leaves. Session B starts with `autopilot dirty` empty
  and no stand-down.
- **Edge case**: a peer edits `skills/work/SKILL.md` while the store has
  churn → `autopilot dirty` prints only the skill path, and the stand-down
  still fires.
- **Error case**: `git commit` fails (hook denial, locked index) →
  `record-store` prints one stderr line, the handoff completes, and the next
  session's `autopilot dirty` still ignores the leftover store changes.

## Risks

- **Commit noise**: one `chore(autopilot)` commit per handoff, about 15 per
  PRD. They are local until the operator pushes, and phase-done's "commit
  history is left as-is" rule already leaves squashing to the operator.
- **A secret lands in a review file and gets committed**: the store now
  becomes public on push. The release step already runs before any push; the
  first public commit of the store is preceded by a manual secret scan
  (operator task, outside this PRD's code).
