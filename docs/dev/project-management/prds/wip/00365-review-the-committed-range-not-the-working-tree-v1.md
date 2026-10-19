---
design: skip
default_model: sonnet
model_tier_rationale: three one-token edits in one script with the exact text given, one bash harness with its assertions given, one docstring line
---

# Review the committed range, not the working tree

Source: batch 202610100952 in the agent-skills repo, 2026-10-18. A formatter pass on two glean files sat uncommitted in the loop's checkout from 12:16 on. It was not part of any PRD, yet six of the nine reviews that day carried it (00031, 00045, 00048, 00070, 00086, 00088), three or four reviewers flagged it each time, consolidation discarded it with a git-log check each time, it produced eight batch-end deferred rows and two hold stubs, and the 00086 review wrote in its scope note that "the staged diff was built from the working tree". The review prose names the range as `work_start_sha..HEAD` (`skills/review-work-completion/SKILL.md:140`); the script does not produce that range.

## Problem

`skills/review-work-completion/scripts/gather-context.sh` resolves `DIFF_BASE` (the merge-base with the base branch, or the `--since` ref) and then calls git with that one ref: the emptiness probe at `skills/review-work-completion/scripts/gather-context.sh:120` (`git -C "$PROJECT_ROOT" diff --quiet "$DIFF_BASE"`), the changed-files block at `skills/review-work-completion/scripts/gather-context.sh:161` (`--stat`) and the diff file at `skills/review-work-completion/scripts/gather-context.sh:165`. With one ref, git compares that commit with the working tree, so every uncommitted or untracked-then-staged edit in the checkout is reviewed as if the PRD made it. The gate-reuse docstring records the dependence: its line `skills/run-autopilot/cli/verification.py:127` says the diff is against the working tree, not just `HEAD`. `review_stage` runs the script for every cycle through `GATHER_SCRIPT` (`skills/run-autopilot/cli/review_stage.py:32`), so every lane that stages a review through `review-stage` inherits the behavior.

## Solution

The three calls compare `DIFF_BASE` with `HEAD`: each `"$DIFF_BASE"` token on those three lines becomes `"$DIFF_BASE" HEAD`, before the path arguments (`git diff [options] <commit> <commit> [--] [<path>...]`). Nothing else in the script changes: the base resolution, the `--since` override, the empty-diff refusal (exit 3) and the review-paths scoping keep their text. The docstring line at `skills/run-autopilot/cli/verification.py:127` becomes `since the gate ran against the working tree, which must match what was reviewed`, so the clean-tree requirement of gate reuse keeps its reason. A third bash harness, `skills/review-work-completion/scripts/test_gather_context_committed_range.sh`, written in the shape of `skills/review-work-completion/scripts/test_gather_context_paths.sh` (its own `PASS`/`FAIL` helpers, `SCRIPT` resolved from the script's directory, a `setup_repo` that commits `base.py` on master and `a.py`, `b.py` on a feature branch), runs three scenarios:

1. On the feature branch, append a line to `base.py` without committing and create an untracked `scratch.py`; run the script; the diff file names `a.py` and `b.py` and does not name `base.py` or `scratch.py`; print `PASS: uncommitted edits stay out of the diff`.
2. Same tree, run the script with `--since <sha of the init commit>`; the diff file names `a.py` and `b.py` and does not name `base.py`; print `PASS: --since diffs the committed range`.
3. Check out master, append a line to `base.py` without committing, run the script; it exits 3 and prints the `empty diff` refusal on stderr; print `PASS: dirt alone never makes a review`.

`dev/bin/release-checks` registers the harness with `run_gather_harness` right after the `[checks] gather-context id` block (`dev/bin/release-checks:334`), as `echo "[checks] gather-context committed range"` followed by `run_gather_harness bash skills/review-work-completion/scripts/test_gather_context_committed_range.sh`.

## Requirements

### Must have
- The three git calls at lines 120, 161 and 165 of `skills/review-work-completion/scripts/gather-context.sh` compare `DIFF_BASE` with `HEAD`; no other line of the script changes.
- The harness `skills/review-work-completion/scripts/test_gather_context_committed_range.sh` with the three scenarios above, registered in `dev/bin/release-checks`.
- The docstring line at `skills/run-autopilot/cli/verification.py:127` reworded as given; the clean-tree check itself is unchanged.
- A CHANGELOG `[Unreleased]` Fixed entry under **review-work-completion**: the review diff is the committed range `base..HEAD`, so uncommitted edits in the loop's checkout are no longer reviewed, deferred and minted as stubs under every PRD of the batch.

### Nice to have
- None.

## Implementation

### Module: gather-context
- **Location**: `skills/review-work-completion/scripts/gather-context.sh`
- **Responsibility**: stage the review context and diff for one cycle
- **Exports**: none (a bash script)

### Module: committed-range-harness
- **Location**: `skills/review-work-completion/scripts/test_gather_context_committed_range.sh`
- **Responsibility**: pin that the diff never contains uncommitted work and that dirt alone is refused
- **Exports**: none
- New symbols: `test_gather_context_committed_range.sh`

### Module: release-checks
- **Location**: `dev/bin/release-checks`
- **Responsibility**: run the new harness in the gate
- **Exports**: none

### Module: verification-docstring
- **Location**: `skills/run-autopilot/cli/verification.py`
- **Responsibility**: state the true reason gate reuse needs a clean tree
- **Exports**: none (a docstring line)

### Dependencies
- gather-context: No dependencies (foundation)
- committed-range-harness: Depends on [gather-context]
- release-checks: Depends on [committed-range-harness]
- verification-docstring: No dependencies (foundation)

## Tasks

### Phase 0: Foundation
- [ ] Write `skills/review-work-completion/scripts/test_gather_context_committed_range.sh` with the three scenarios. Premise: `rg -c '"\$DIFF_BASE" HEAD' skills/review-work-completion/scripts/gather-context.sh` prints 0 before the edit; a different count means the script already changed and the task stops and reports. - Acceptance: `bash skills/review-work-completion/scripts/test_gather_context_committed_range.sh` exits 1 with a `FAIL:` line for scenario 1 against the current script.

### Phase 1: Core
- [ ] Edit the three git calls, reword the docstring line, register the harness, add the CHANGELOG entry (depends on: Phase 0) - Acceptance: `bash skills/review-work-completion/scripts/test_gather_context_committed_range.sh` exits 0 and prints three `PASS:` lines; `rg -c '"\$DIFF_BASE" HEAD' skills/review-work-completion/scripts/gather-context.sh` prints 3; `bash skills/review-work-completion/scripts/test_gather_context_paths.sh` and `bash skills/review-work-completion/scripts/test_gather_context_id.sh` both exit 0; `rg -c "gather-context committed range" dev/bin/release-checks` prints 1; `rg -n "review-work-completion.*committed range" CHANGELOG.md` prints one line under `[Unreleased]`.

## Success Criteria

- The three harnesses pass and `uv run --no-project --with pytest python -m pytest -q skills/run-autopilot/cli/test_verification.py` passes unchanged.
- Post-release signal: a batch run with one uncommitted edit in the checkout produces no review row, deferred row or hold stub about that edit.
