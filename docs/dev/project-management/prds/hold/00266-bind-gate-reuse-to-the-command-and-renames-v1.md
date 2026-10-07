---
catchup: skip
design: skip
default_model: sonnet
model_tier_rationale: transcription - every check, flag and path rule is named exactly, each pinned by a named test that fails at base
---

# Harden gate reuse and review staging inputs

## Problem

The 2026-10-06 agoge run (`docs/dev/project-management/audit-results/agoge-2026-10-06.md`),
all confirmed, approved by the operator 2026-10-06 with the recommended fixes:

- **#6 (MEDIUM, live in 0.9.0):** `verification.reuse_verdict`
  (`skills/run-autopilot/cli/verification.py:93`) never compares the requested
  gate command with the recorded one. A committed record from command `true`
  made `review-stage --gate-command "<a real gate>"` report `verdict: reused`,
  `Tests: 4242 passed`, and the requested gate never ran.
- **#9 (MEDIUM):** `_ancestor_and_clean` (`verification.py:74-80`) uses
  `git log --name-only`, which names a committed rename by its new path only,
  so a product file moved into the store reads as store-only.
- **#16 (LOW):** with `--repo-root` below the git toplevel (`$HOME/.claude`
  under `$HOME`), `git log`/`status` paths are toplevel-relative while the
  store prefix is repo-root-relative, so every store change reads as product
  code and the record is never reused (fails safe, costs gate runs).
- **#18 (LOW):** a record whose `sha` is the string `HEAD` is reused forever.
- **#19 (LOW):** `gather-context.sh` diffs an interactive full review against
  the base branch tip instead of the merge-base, has no `main` candidate, and
  drops a bad `--since` silently; `review_stage._replay_base` uses the
  merge-base, so the two disagree.
- **#22 (LOW):** `review-stage` joins state `prd` onto `prds/wip/` without
  resolving it and reads `design_doc` as given, so `../` or an absolute path
  pulls any file into reviewer inputs.
- **#23 (LOW):** `review-stage` follows a symlinked `docs/dev/tmp` and writes
  prompts and diffs outside the repo.

## Solution

Bind reuse to the command, a full sha and both sides of a rename, measured
from the repo root; make `gather-context.sh` agree with `_replay_base`; keep
every staged input and output inside the repo.

## Requirements

### Must have
- A record whose command differs from the requested one, or whose sha is not 40 hex characters, is `stale`.
- A committed rename from a product path into the store is `stale`.
- From a repo root below the toplevel, a store-only change is `reused`.
- `gather-context.sh` diffs against `git merge-base <base> HEAD`, tries `main` after `master`, and warns on stderr when `--since` fails `cat-file -e`.
- `review-stage` refuses (exit 2) a resolved `prd` outside `prds/wip/`, a resolved `design_doc` outside the repo root, and a resolved staging dir outside the repo root.

### Nice to have
- None.

## Implementation

### Module: verification
- **Location**: `skills/run-autopilot/cli/verification.py`
- **Responsibility**: decide gate reuse
- **Exports**: `reuse_verdict(record, repo_root, head_sha, gate_command)` (new required parameter)

### Module: review_stage
- **Location**: `skills/run-autopilot/cli/review_stage.py`
- **Responsibility**: pass `--gate-command` to `reuse_verdict` (call at line 351); confine staged inputs and outputs to the repo
- **Exports**: none new

### Module: gather-context
- **Location**: `skills/review-work-completion/scripts/gather-context.sh`
- **Responsibility**: diff base for an interactive full review
- **Exports**: none

### Dependencies
- verification: No dependencies (foundation)
- review_stage: Depends on [verification]
- gather-context: No dependencies (foundation)

## Tasks

### Phase 0: Foundation
- [ ] verification: add `gate_command: str` to `reuse_verdict` and return `stale` when `record["commands"][0]["command"] != gate_command` (#6); add `"--no-renames"` to the `git log` call in `_ancestor_and_clean` (#9); require `re.fullmatch(r"[0-9a-f]{40}", sha)` (#18); run the `git log` and `git status` calls with `--relative` and `-- .` from `repo_root`, status with `-uall` (#16) - Acceptance: `test_reuse_is_stale_when_the_gate_command_differs`, `test_committed_rename_into_the_store_is_stale`, `test_symbolic_sha_record_is_stale`, `test_store_only_change_below_toplevel_is_reused` pass in `skills/run-autopilot/cli/test_verification.py`, each failing at base.
- [ ] gather-context: merge-base diff, `main` candidate, stderr warning on a bad `--since` (#19) - Acceptance: new cases in `skills/review-work-completion/scripts/test_gather_context_id.sh` pass (`advanced master is not shown as removed`, `main-only repo resolves a base`, `bad --since warns on stderr`).

### Phase 1: Core
- [ ] review_stage: pass `--gate-command` to `reuse_verdict`; resolve `prd`, `design_doc` and the staging dir and refuse each outside its root (#22, #23) (depends on: Phase 0) - Acceptance: `test_stage_runs_the_gate_when_the_recorded_command_differs`, `test_stage_refuses_a_prd_outside_wip`, `test_stage_refuses_a_design_doc_outside_the_repo`, `test_stage_refuses_a_symlinked_tmp_outside_the_repo` pass in `skills/run-autopilot/cli/test_review_stage.py`.

## Success Criteria

- Every test named above passes.
- `bash dev/bin/release-checks` exits 0.
