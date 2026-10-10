---
design: run
default_model: opus
model_tier_rationale: changes what counts as dirt, who may write the record and when reuse is safe; a wrong turn certifies a red tree as green or silently drops the gate in every other repo
---

# The gate record can lie or go missing

## Overview

### Problem Statement

The agoge run of 2026-10-10 (`docs/dev/project-management/audit-results/agoge-2026-10-10.md`,
packets 1, 2, 3, 10, 14, 15, 16, 19; decisions in its `## Minutes`, walked with the
operator) shows that `last-verification.json` can still certify a tree no gate
passed, and that in other repos the gate never runs at all:

- **1 (HIGH, regression since 0.9.0):** `verification._dirty_outside_store` treats only
  `docs/dev/project-management/` as the store, while `store_tree.STORE_PREFIXES` also
  names `docs/dev/tmp/`. In a repo that does not gitignore `docs/dev/tmp/`, the
  review's own staged prompts and gate log make the tree dirty: `review-stage`
  prints `Tests: (gate skipped: working tree dirty outside the store)` and exits 0,
  and `verify` refuses every run. Every other repo on the next release loses its gate.
- **2 (HIGH):** `run_gate` opens `--log` before the gate runs. `--log docs/dev/project-management/autopilot/last-verification.json`
  lets the gate's own stdout become the record; `review-stage` then reuses it as green.
- **3 (HIGH):** files marked `--skip-worktree` or `--assume-unchanged` are invisible to
  `git status`, so a gate run over edits to them records green for HEAD, and the
  record is reused after the edit is gone.
- **10 (MEDIUM, mocked):** `verify` exits 0 when the gate exits 0 but printed no
  summary, though `recorded` is false.
- **14 (LOW):** a relative `verify --log` resolves against the process cwd, not `--repo-root`.
- **15 (LOW):** two concurrent `verify` runs interleave one log and race on the record.
- **16 (LOW):** a tracked product symlink that points into the store lets a store-only
  edit change product behaviour while the record is still reused.
- **19 (LOW):** dirt that arrives mid-run (loupe's end-of-turn reflow) discards a
  finished 216 s run, and the JSON does not say which paths were dirty.

If unchanged: other repos ship red suites behind a review that exits 0, and one
documented flag makes a red suite read green.

### Target Users

The autopilot loop and its operator in every repo that installs the pack: build
sessions running `autopilot verify`, review sessions running `review-stage`.

### Success Metrics

- In a repo with no `docs/dev/tmp/` ignore rule and `GIT_CONFIG_GLOBAL=/dev/null`,
  `verify` gives `recorded: true` and review-stage's Tests line carries counts.
- No `verify --log` value can make the gate's output become the record.
- A skip-worktree or assume-unchanged edit outside the store blocks the record.
- `verify` exits non-zero whenever it wrote no record.

## Functional Decomposition

### Capability: One definition of dirt

#### Feature: Scratch is not dirt (packet 1)
- **Description**: `_dirty_outside_store` ignores every prefix in `store_tree.STORE_PREFIXES` and the run's own `log_path`.
- **Behavior**: replace the single `STORE_PREFIX` test in `_dirty_outside_store` with `store_tree.STORE_PREFIXES` (each joined to `--show-prefix`); `run_gate` passes its `log_path` (repo-relative, when inside the repo) as an extra excluded path. The committed-diff check in `_ancestor_and_clean` keeps its current store prefix (scratch is never committed).

#### Feature: Hidden-flag edits are dirt (packet 3)
- **Description**: also dirty when `git ls-files -v` shows an `S` tag (skip-worktree) or a lowercase tag (assume-unchanged) on a path outside the store prefixes.
- **Behavior**: one extra git call inside `_dirty_outside_store`; a git failure counts as dirty, as today. Files hidden through `.git/info/exclude` or other ignore rules stay out of scope: the operator accepted that route; the docstring names it.

#### Feature: Name the dirt (packet 19)
- **Description**: `run_gate`'s result gains `dirty_paths: list[str]` (the outside-store paths that made it dirty, empty when clean), and `verify` prints it.

### Capability: The verb cannot forge or lose the record

#### Feature: Log path is checked (packets 2, 14)
- **Description**: `verify` resolves a relative `--log` against `--repo-root`, then exits 2 (`autopilot: verify: --log ... resolves inside the store`) when the resolved path is under `docs/dev/project-management/`.
- **Behavior**: check runs in `_run_verify` before `run_gate`, so nothing is opened or truncated on refusal.

#### Feature: Invalidate at start (packet 2)
- **Description**: `run_gate` removes `last-verification.json` before spawning the gate (after the pre-spawn dirty check passes), so a failed, timed-out or unparsed run never leaves an older green record behind.
- **Risk accepted**: an aborted run costs the previous good record (one rerun, ~220 s).

#### Feature: Honest exit code (packet 10)
- **Description**: `verify` exits 3 when the gate exited 0, did not time out, and `recorded` is false. Exit 0 now means "green and recorded". Document 3 in the `__main__.py` docstring and `skills/work/references/final-verification.md` § Recorded verification result.

#### Feature: One run at a time (packet 15)
- **Description**: `run_gate` holds an exclusive `fcntl.flock` on `docs/dev/tmp/gate.lock` (under `cwd`) from before the pre-spawn dirty check until after the record write, covering the log and the record. The wait is bounded by the gate timeout; on expiry the second caller returns the timed-out result and writes nothing.

### Capability: Reuse sees through symlinks

#### Feature: Store targets of product symlinks are product (packet 16)
- **Description**: in `reuse_verdict`, a changed store path counts as product when any tracked symlink outside the store (`git ls-files -s`, mode `120000`) resolves to it; the verdict is then `stale`.

## Structural Decomposition

### Repository Structure

```
CHANGELOG.md                                   # [Unreleased] Fixed lines
skills/run-autopilot/cli/
├── __main__.py                                # verify: log path checks, exit 3, dirty_paths
├── verification.py                            # dirt prefixes, ls-files -v, invalidate, flock, symlink reuse
├── store_tree.py                              # read only: STORE_PREFIXES
├── test_verification.py                       # tests: symlink reuse, invalidate, flock
├── test_verification_dirty.py                 # tests: scratch, hidden flags, dirty_paths
└── test_cli_review_verbs.py                   # tests: verify log refusal, relative log, exit 3
skills/work/references/
└── final-verification.md                      # exit 3, log rule
```

### Module: verification
- **Responsibility**: decide dirt, run the gate once under a lock, write or invalidate the only record, decide reuse.
- **Exports**: `run_gate(...)` result gains `dirty_paths`; signature unchanged.

### Module: cli verify verb
- **Responsibility**: validate `--log`, map results to exit 0/1/2/3.

## Dependency Graph

### Foundation Layer (Phase 0)
- **verification**: dirt prefixes, hidden flags, dirty_paths, invalidate, flock, symlink reuse.

### Core Layer (Phase 1)
- **cli verify verb**: depends on [verification].

### Integration Layer (Phase 2)
- **prose, CHANGELOG**: depend on [cli verify verb].

## Implementation Phases

### Phase 0: Foundation
**Goal**: the record is honest and the gate runs in any repo.

**Tasks**:
- [ ] verification: `_dirty_outside_store` uses `STORE_PREFIXES` and accepts an excluded `log_path`; `run_gate` passes its own (no deps) - Acceptance: in `test_verification_dirty.py`, `test_gate_runs_in_a_repo_that_does_not_ignore_docs_dev_tmp` (fixture: no `.gitignore`, `GIT_CONFIG_GLOBAL=/dev/null`, staged `docs/dev/tmp/alice-prompt-1.md`) gives `recorded: True`, and `test_own_log_outside_tmp_is_not_dirt` passes; both fail at base.
- [ ] verification: skip-worktree and assume-unchanged entries outside the store count as dirt; docstring names the ignored-file route as accepted (no deps) - Acceptance: `test_skip_worktree_edit_blocks_record` and `test_assume_unchanged_edit_blocks_record` pass and fail at base.
- [ ] verification: `dirty_paths` in the result (no deps) - Acceptance: `test_dirty_result_lists_the_dirty_paths` passes and fails at base.
- [ ] verification: remove the record before spawn; flock `docs/dev/tmp/gate.lock` around the run (no deps) - Acceptance: in `test_verification.py`, `test_failed_run_leaves_no_older_green_record` and `test_concurrent_runs_serialize_on_the_gate_lock` pass and fail at base.
- [ ] verification: product symlink into the store makes reuse stale (no deps) - Acceptance: `test_store_edit_behind_a_product_symlink_is_stale` passes and fails at base; `test_store_only_change_below_toplevel_is_reused` still passes.

**Exit Criteria**: `uv run --no-project --with pytest python -m pytest -q skills/run-autopilot/cli/test_verification.py skills/run-autopilot/cli/test_verification_dirty.py` exits 0.

### Phase 1: Core
**Tasks**:
- [ ] cli: relative `--log` joins `--repo-root`; a store-resolving `--log` exits 2 before anything is opened; exit 3 when green but unrecorded; print `dirty_paths` (depends on: Phase 0) - Acceptance: in `test_cli_review_verbs.py`, `rejects_log_path_resolving_to_record` (record bytes unchanged), `test_relative_log_resolves_against_repo_root` and `test_verify_exits_3_when_green_but_unrecorded` pass and fail at base.

**Exit Criteria**: `uv run --no-project --with pytest python -m pytest -q skills/run-autopilot/cli/test_cli_review_verbs.py` exits 0.

### Phase 2: Integration
**Tasks**:
- [ ] prose: `final-verification.md` documents exit 3, the store-path refusal and `dirty_paths` (depends on: Phase 1) - Acceptance: `rg -n "exit 3|exits 3" skills/work/references/final-verification.md` hits.
- [ ] CHANGELOG: `[Unreleased] ### Fixed` lines for the gate in other repos, `--log` refusal, hidden-flag edits, exit 3, concurrent runs, symlink reuse (depends on: all above) - Acceptance: `rg -n "docs/dev/tmp" CHANGELOG.md` hits inside `[Unreleased]`.

**Exit Criteria**: `bash dev/bin/release-checks` exits 0 with `FAIL 0` on its summary line.

## Test Strategy

### Critical Scenarios

Reproductions from the report, verbatim:

```
1: Fixture with no `.gitignore` and `GIT_CONFIG_GLOBAL=/dev/null`: HEAD `review-stage` exit 0,
   `Tests: (gate skipped: working tree dirty outside the store)`. Its only dirt was
   `?? docs/dev/tmp/alice-prompt-1.md ... ?? docs/dev/tmp/gate-1.log`. The same fixture on 0.9.0
   gives `Tests: 5 passed ... (suite run this cycle)`.
2: `forge.sh` prints a record JSON (`"failed":0`, `"passed":9`, HEAD sha, `"command":"forge.sh"`)
   and runs `exit 1`. `verify --gate-command "bash forge.sh" --log
   docs/dev/project-management/autopilot/last-verification.json` gives exit 1, `recorded: false`,
   and the file now holds the forged JSON. `review-stage --gate-command "bash forge.sh"` then
   gives `"verdict": "reused"`, `Tests: 9 passed, 0 failed`.
3: HEAD fails its gate (`PASS 0 FAIL 1`). `update-index --skip-worktree app.py` plus a local fix
   leaves status `''`. `verify` then gives exit 0, `recorded: true`. After restoring the file,
   the gate fails again, and `review-stage` gives `reused`, `Tests: 1 passed, 0 failed`.
10: `verify --gate-command "bash gate.sh"` (body `true`) gives exit 0
   `{"passed": null, ..., "recorded": false}`.
14: `verify --repo-root <fx> --log docs/dev/tmp/rel.log`, run from another cwd, gives
   `"log": "docs/dev/tmp/rel.log"`: the file is under cwd, not under the repo.
15: Run B reports exit 0, `passed: 5, recorded: true`. Run A reports exit 1, `failed: 2,
   recorded: true`. The record on disk holds A's red result, and the log bytes interleave.
16: `settings.json -> docs/dev/project-management/settings.json`: editing the store target, and
   then committing it, both give `reused`.
19: `verify` took 216.4 s and returned `{"passed": 3001, ..., "recorded": false, "dirty": true}`.
```

## Risks

- **Scratch edits go unseen** (packet 1): product files placed under `docs/dev/tmp/` no longer block a record; that tree is scratch by rule.
- **Users with skip-worktree files** now get a refusal they must clear (packet 3). The ignored-file route stays open, documented.
- **Invalidate at start** costs the previous good record when a run aborts early.
- **The lock** makes a second run wait up to the gate timeout; a hung gate blocks the next until it expires.
- **Exit 3** is a new code: prose that treats any non-zero exit as red must not mistake it for a failing suite.
- Source: `docs/dev/project-management/audit-results/agoge-2026-10-10.md` (2026-10-10).
