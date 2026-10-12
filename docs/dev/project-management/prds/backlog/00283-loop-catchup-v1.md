---
default_model: sonnet
model_tier_rationale: exact predicates and shapes given (committer string, probe verdicts, skip list); every criterion is a named test; the classifier can still raise a task
---

# Loop catchup: delta after loop-only commits, batch-scoped probes

## Overview

### Problem Statement
Every PRD carrying `catchup: force` re-runs full catchup (`/git-ferry:catchup`,
about 50K tokens and 60-95 s), even when the only commits since the last full
catchup are the loop's own. Inside each full catchup two steps always fail in
loop sessions: `gh` (GitHub state) and `engram` (repo not registered). Each
failure costs extra calls, because the catchup skill says to read a failed
script and run its commands by hand. Source: discovery
`docs/dev/project-management/discovery/00281-loop-efficiency.md` (F5, F6).

### Target Users
The operator running `autoclaude` batches whose PRDs carry `catchup: force`.

### Success Metrics
- `test_force_is_delta_when_all_commits_are_loop_commits` and `test_force_is_full_when_one_commit_is_not` pass.
- `test_probe_records_unauthenticated_then_reuses_within_batch` and `test_new_batch_reprobes` pass (gh and engram).
- `uv run pytest skills/run-autopilot` is green at the end of the last phase.

## Functional Decomposition

### Capability: Loop commit identity
Mark every commit a loop session or the loop itself makes.

#### Feature: Loop committer name
- **Description**: The loop stamps its commits' committer name with `autopilot-loop/<batch.id>`.
- **Inputs**: `state.batch.id` at launch (fallback `no-batch`).
- **Outputs**: `GIT_COMMITTER_NAME=autopilot-loop/<batch.id>` in the launched session's env and in the loop process's own `os.environ` (its store commits).
- **Behavior**: Set in `Loop._launch` before spawning, from state read at that moment. The author stays the user's own identity; only the committer name changes. The loop process makes only loop commits, so setting `os.environ` there is safe: `# ponytail: process-wide env, the loop process commits nothing else`. A human commit outside the loop keeps the user's committer name.

### Capability: Catchup decision
Choose full or delta catchup in code.

#### Feature: Force with loop-only commits (F5)
- **Description**: `catchup: force` gives full catchup unless every commit since `batch.catchup_head_sha` has committer name `autopilot-loop/<batch.id>`; then delta.
- **Inputs**: `state.catchup_mode`, `state.tasks`, `state.batch.catchup_head_sha`, `state.batch.id`, the project root.
- **Outputs**: `_catchup` returns `"delta"` or `"full"`.
- **Behavior**: In `enter._catchup`, the `mode == "force"` first-entry branch (tasks empty) now returns `delta` when `catchup_head_sha` is present and `loop_only(root, sha, f"autopilot-loop/{batch_id}")` is True. Otherwise it returns `full`. Freshness (`catchup_completed_at`) is not consulted for force, per discovery Q4. `loop_only` runs `git -C <root> log --format=%cn <sha>..HEAD`. It returns True when every line equals the name, including an empty range. It returns False on any git failure or an unknown sha, so a fault means full catchup. The `run` mode and the tasks-present `force` path are unchanged.

### Capability: Batch-scoped catchup probes
Learn once per batch which catchup steps cannot work here.

#### Feature: Catchup probe verb (F6)
- **Description**: `autopilot catchup-probe` probes `gh` and `engram` once per batch inside the session and prints the steps to skip.
- **Inputs**: `state.batch.id` (fallback `no-batch`), `state.catchup_probe`.
- **Outputs**: `state.catchup_probe = {"batch_id": <id>, "gh": "ok"|"unauthenticated"|"absent", "engram": "ok"|"unregistered"|"absent", "checked_at": <ISO UTC>}`. Stdout gets one JSON line: `{"skip": [...]}`, where `skip` holds `"github-state"` when gh is not `ok` and `"engram"` when engram is not `ok`.
- **Behavior**: When `catchup_probe.batch_id == batch.id`, it reuses the stored verdicts and runs neither binary (the `codex_probe` lazy-reset idiom, `skills/work/references/codex-implementor.md:40-80`). Otherwise it probes, in the project root. For `gh`: not on PATH gives `absent`; `gh auth status` exit 0 gives `ok`; any other exit gives `unauthenticated`. For `engram`: not on PATH gives `absent`; `engram status --scope repo` with stderr containing `not inside a registered repo` gives `unregistered`; any other result gives `ok` (a nonzero exit for stale rows still means registered). A probe timeout of 15 s counts as a failure. The probe runs in the session, not the loop, because the session's sandbox is where `gh` fails: `gh auth status` in a sandboxed shell fails on `~/.config/gh/hosts.yml` while the same call works outside it. In `references/phase-build.md` Phase 1, the full-catchup path runs `autopilot catchup-probe` first. It then invokes `/git-ferry:catchup` with each skipped step named: do not run `github-state.sh` or the gh commands, and do not run any `engram` command. It writes one gap line per skipped step in the capsule. The probe adds `catchup_probe` to the batch-scoped fields that `records.py` does not reset.

## Structural Decomposition

### Repository Structure

```
skills/run-autopilot/
├── cli/
│   ├── loop.py            # Maps to: Loop committer name
│   ├── enter.py           # Maps to: Force with loop-only commits
│   ├── enter_io.py        # Maps to: Force with loop-only commits (git log)
│   ├── catchup_probe.py   # Maps to: Catchup probe verb (new)
│   └── __main__.py        # Maps to: Catchup probe verb (subcommand)
└── references/
    ├── phase-build.md     # Maps to: Catchup probe verb (Phase 1 prose)
    └── state-schema.md    # catchup_probe row
```

### Module: loop committer
- **Maps to capability**: Loop commit identity
- **Responsibility**: Set the committer name before each launch.
- **Exports**: `loop_committer(batch_id)` - returns `f"autopilot-loop/{batch_id or 'no-batch'}"`; used by `Loop._launch` and `enter._catchup`.
- New symbols: `loop_committer`

### Module: enter catchup
- **Maps to capability**: Catchup decision
- **Responsibility**: The force branch of `_catchup`.
- **Exports**: `enter_io.commits_all_loop(root, sha, name)`, injected into `enter()` as the new keyword `loop_only` (default `enter_io.commits_all_loop`), like `git_head`.
- New symbols: `commits_all_loop`, `loop_only`, `enter_io.commits_all_loop`, `test_force_is_delta_when_all_commits_are_loop_commits`, `test_force_is_full_when_one_commit_is_not`, `test_force_is_full_on_git_failure`

### Module: catchup_probe
- **Maps to capability**: Batch-scoped catchup probes
- **Responsibility**: Probe, cache per batch, print the skip list.
- **Exports**: `probe(state_path, *, run=subprocess.run, which=shutil.which, now=...)` - returns the skip list and writes `catchup_probe` through `statectl.mutate`; `main` wiring as `catchup-probe --state <path>`.
- New symbols: `catchup_probe.py`, `probe`, `catchup-probe`, `catchup_probe`, `state.catchup_probe`, `unauthenticated`, `test_probe_records_unauthenticated_then_reuses_within_batch`, `test_new_batch_reprobes`, `test_engram_unregistered_from_stderr`

## Dependency Graph

### Foundation Layer (Phase 0)
No dependencies - built first.

- **loop committer**: the name and its env stamp.
- **catchup_probe**: standalone verb.

### Core Layer (Phase 1)
- **enter catchup**: Depends on [loop committer]

### Integration Layer (Phase 2)
- **phase-build prose, state-schema**: Depends on [enter catchup, catchup_probe]

## Implementation Phases

### Phase 0: Foundation
**Goal**: The committer stamp and the probe verb.

**Tasks**:
- [ ] `loop_committer` in `cli/loop.py`; `Loop._launch` sets `GIT_COMMITTER_NAME` in `self.env` and `os.environ` from `state.batch.id` (no deps) - Acceptance: `uv run pytest skills/run-autopilot/cli/test_loop.py -k committer` passes. The scripted spawn sees `GIT_COMMITTER_NAME == "autopilot-loop/<id>"` in its `env`; a commit made in a temp repo with that env shows it under `git log --format=%cn`.
- [ ] `cli/catchup_probe.py` and the `catchup-probe` subcommand (no deps) - Acceptance: `uv run pytest skills/run-autopilot/cli/test_catchup_probe.py` passes, including `test_probe_records_unauthenticated_then_reuses_within_batch` (stub `gh` exits 1: the first call records `unauthenticated` and the second call in the same batch does not run `gh`), `test_new_batch_reprobes`, and the same three for engram (`test_engram_unregistered_from_stderr`).

**Exit Criteria**: both filters pass.

### Phase 1: Core
**Goal**: `_catchup` returns delta after loop-only commits.

**Tasks**:
- [ ] `enter_io.commits_all_loop`, the `loop_only` keyword on `enter()`, and the force branch in `_catchup` (depends on: Phase 0) - Acceptance: `uv run pytest skills/run-autopilot/cli/test_enter_decisions.py -k "force"` passes, including `test_force_is_delta_when_all_commits_are_loop_commits`, `test_force_is_full_when_one_commit_is_not`, `test_force_is_full_on_git_failure`, and the existing force tests unchanged. Premise: the existing `force` tests in `test_enter_decisions.py` expect `full` for a first entry with no `catchup_head_sha`; re-check with `rg -n "force" skills/run-autopilot/cli/test_enter_decisions.py` before editing. If any expects `full` with a head sha whose range is loop-only, stop and report rather than rewriting it.

**Exit Criteria**: the filter passes.

### Phase 2: Integration
**Goal**: The session uses the probe and the docs match.

**Tasks**:
- [ ] `references/phase-build.md` Phase 1: condition 1 states the loop-commit rule for `force`, and the full-catchup path runs `autopilot catchup-probe` and passes the skip list to `/git-ferry:catchup` with the gap lines; `references/state-schema.md` gets a `catchup_probe` row; CHANGELOG `[Unreleased]` Changed and Added entries (depends on: Phase 1) - Acceptance: `rg -n "catchup-probe" skills/run-autopilot/references/phase-build.md` hits; `rg -n "catchup_probe" skills/run-autopilot/references/state-schema.md` hits; `uv run pytest skills/run-autopilot/cli/test_enter_prose.py skills/run-autopilot/cli/test_doc_contract.py` passes.

**Exit Criteria**: `uv run pytest skills/run-autopilot` is green.

## Test Strategy

### Critical Scenarios
- **Happy path**: temp repo, `catchup_head_sha` = A, two commits after A with committer `autopilot-loop/B1`, `batch.id` B1, `catchup_mode: force`, no tasks → Expected: `delta`.
- **Edge case**: one of those commits made with the default committer → Expected: `full`.
- **Edge case**: same commits but `batch.id` B2 → Expected: `full` (another batch's loop).
- **Error case**: `catchup_head_sha` not in the repo → Expected: `full`.
- **Happy path**: probe with stub `gh` exit 0 and stub `engram` exit 0 → Expected: `{"skip": []}`, verdicts `ok`.
- **Edge case**: `gh` not on PATH → Expected: `absent`, `github-state` in skip.

## Risks

- **Human commit misread as a loop commit**: only if a human sets the loop's committer name by hand. Message prefixes are never used.
- **Committer name visible in history**: `git log --format=fuller` and GitHub's "committed by" line show `autopilot-loop/<id>`. The user accepted this (2026-10-12).
- **Session ignores the skip instruction**: the cost falls back to today's, never worse. The probe still stops the repeat probing.
- **Probe verdict goes stale mid-batch** (someone runs `gh auth login`): the next batch re-probes. Fixing gh mid-batch needs `statectl del catchup_probe`.
