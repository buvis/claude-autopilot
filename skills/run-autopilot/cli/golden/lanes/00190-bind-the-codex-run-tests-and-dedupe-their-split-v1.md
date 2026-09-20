---
catchup: skip
design: skip
default_model: sonnet
model_tier_rationale: test scaffolding and one CHANGELOG line, every case named by the review that raised it
rework_cap: 3
---

# Bind the codex-run tests and dedupe their split

Source: PRD 00180 hit the rework cap in cycle 2 with nine findings open (batch 202609061630 deferred ledger, `dev/local/reviews/00180-route-codex-prompt-through-stdin-v1-review-2.md`); walked 2026-09-07 in the config-audit closure walkthrough (`~/.claude/dev/local/audit-results/2026-09-05.md`). Filed with PRD 00182's release-checks gap, which touches the same gate.

## Overview

### Problem Statement

The 00180 build moved 24 of `test_codex_run.sh`'s cases into a new `test_codex_run_resume.sh` that the PRD never named, copying 239 byte-identical lines of scaffolding and defining `child_stdin_is_prompt` twice instead of the single shared-helper extraction the cycle-1 task asked for (483 and 524 lines today; the PRD's `rg -c 'PASS "'` gate reads 21 where it required 40, with all 45 cases alive). Three of four reviewers found the unreadable-prompt case at `test_codex_run.sh:392` passes against the pre-fix script, so the new cat-failure guard and its stderr message have no tripwire, and the same case turns into a no-op PASS for any user that can read a chmod-000 file (root in CI). Two new cases duplicate existing ones (the fresh-JSON marker case at `:454` re-invokes codex although the JSON-path case already captures argv; the trailing-newline case at `:434` repeats the leading-dash file case's byte compare), and the leading-dash prompt is verified on the plain path only, not the JSON and resume paths the PRD's test strategy named. Separately, commit bb08599's whitespace guard at `codex-run.sh:154` sits outside the `PROMPT_FILE` block, so a whitespace-only positional prompt is rejected too, while the CHANGELOG line describes the rejection as `-f` only; the operator decided to keep the guard and correct the line. And `dev/bin/release-checks` never runs `skills/work/scripts/test_record_dispatch.py`, which made PRD 00182's exit criterion a vacuous gate.

### Target Users

The operator releasing the plugin, whose release gate must run every test that guards a shipped behaviour; the next PRD that edits `codex-run.sh`, which must not have to fix two copies of one scaffold.

### Success Metrics

- `child_stdin_is_prompt` and the shared scaffolding are defined once, in a file both test scripts source; an anchored literal-definition search (`rg -n '^child_stdin_is_prompt\(\) \{' skills/use-codex/scripts/*.sh`) returns one definition in the helper, and source assertions verify both harnesses load it.
- The unreadable-prompt case fails against `codex-run.sh` at `bb08599~1` (checked once in a scratch worktree) and asserts the guard's stderr text; it is skipped, not passed, when the test runs as root.
- The leading-dash prompt case runs on the plain, JSON and resume paths; the two duplicate cases are folded into the cases they repeat.
- `CHANGELOG.md` says a whitespace-only prompt is rejected as `Prompt required` whether it arrives by `-f` or positionally.
- `bash dev/bin/release-checks` runs `test_record_dispatch.py` and passes.

## Functional Decomposition

### Capability: One scaffold for the codex-run tests
#### Feature: Shared helper file
- **Description**: `skills/use-codex/scripts/codex_run_test_lib.sh` holds the stub codex, `child_stdin_is_prompt`, the PASS/FAIL counters and every other block the two scripts currently duplicate; both scripts source it.
- **Inputs**: the 239 duplicated lines.
- **Outputs**: two scripts under 400 lines each and one helper file; `bash test_codex_run.sh` and `bash test_codex_run_resume.sh` keep their exit codes and PASS line shapes.
- **Behavior**: preserve all baseline cases and assertions except the two named duplicate executions, whose distinct assertions remain in their host cases. Their old labels become combined host labels. Replace the root unreadable-file no-op PASS with SKIP, and replace the single leading-dash label with plain/json/resume labels. These are the complete allowed label-count exceptions; compare the case/assertion inventory, not an unchanged PASS total.
- **Premise**: both scripts currently duplicate setup and define `child_stdin_is_prompt`; before moving or deleting blocks, inventory the execution-time cases, assertions and duplicated text. Recheck these observations and the two named duplicates; skip/report any task whose premise changed, never delete a different case to satisfy an old count.

### Capability: Cases that bind the guard
#### Feature: The unreadable-prompt case pins the cat-failure guard
- **Description**: the case asserts exit 1 and the guard's stderr message, and skips itself when `id -u` is 0.
- **Inputs**: a prompt file with mode 000.
- **Outputs**: FAIL against the pre-guard script, PASS against the current one, SKIP as root.
- **Behavior**: assert exit 1 and exact stderr `ERROR: failed to read prompt file: <path>`. Replay the revised harness and shared helper against the old runner at `bb08599~1` in a disposable scratch repo/worktree; do not run the old harness unchanged. Use a PATH shim for `id -u` to exercise SKIP without sudo.
#### Feature: Leading-dash prompt on every path
- **Description**: the leading-dash case runs on the plain, JSON and resume paths.
- **Inputs**: the existing leading-dash prompt file, including its trailing newlines.
- **Outputs**: three named PASS results: plain, json and resume.
- **Behavior**: assert captured stdin equals the file bytes and argv ends with `-` on each.

### Capability: The record straight
#### Feature: CHANGELOG line and release gate
- **Description**: the `**use-codex**` line under `[Unreleased]` about the whitespace guard names both prompt forms; `dev/bin/release-checks` gains a `[checks] record_dispatch` block that runs `skills/work/scripts/test_record_dispatch.py` the way the registry block runs its test.
- **Inputs**: the current whitespace guard and release-checks registrations.
- **Outputs**: an accurate Unreleased entry and a gate that runs the dispatch tests.
- **Behavior**: recheck that the guard applies to both prompt forms and the dispatch test remains absent before editing; skip/report a changed premise. Preserve unrelated changelog entries and checks.

## Structural Decomposition

### Repository Structure
```
skills/use-codex/scripts/codex_run_test_lib.sh      # Maps to: shared helper file (new)
skills/use-codex/scripts/test_codex_run.sh          # Maps to: bound cases, folded duplicates
skills/use-codex/scripts/test_codex_run_resume.sh   # Maps to: sources the helper
dev/bin/release-checks                              # Maps to: record_dispatch block
CHANGELOG.md                                        # Maps to: corrected whitespace line
```

### Module: codex-run tests
- **Maps to capability**: One scaffold for the codex-run tests; Cases that bind the guard
- **Responsibility**: `codex_run_test_lib.sh`, `test_codex_run.sh` and `test_codex_run_resume.sh` under `skills/use-codex/scripts/`; share setup and pin the runner's contract through the stub codex
- **Exports**: none (bash tests)

### Module: release gate
- **Maps to capability**: The record straight
- **Responsibility**: `dev/bin/release-checks` and `CHANGELOG.md`; register shipped tests and describe behavior
- **Exports**: none

## Dependency Graph

### Foundation Layer (Phase 0)
- **codex-run tests**: no dependencies; helper extraction is built first.

### Core Layer (Phase 1)
- **codex-run tests**: bound cases depend on their Phase 0 helper extraction.

### Integration Layer (Phase 2)
- **release gate**: Depends on [codex-run tests] for integrated verification.

## Implementation Phases

### Phase 0: One scaffold
**Goal**: Share scaffolding while retaining every distinct assertion.

**Tasks**:
- [ ] Extract `codex_run_test_lib.sh` and source it from both scripts; fold the fresh-JSON marker check into the JSON-path case and the trailing-newline check into the leading-dash file case (no deps) - Acceptance: recheck and record the Feature's duplication/case premises before edits; skip/report changed premises. `bash skills/use-codex/scripts/test_codex_run.sh` and `bash skills/use-codex/scripts/test_codex_run_resume.sh` exit 0; the anchored definition search returns one helper definition and both scripts source it; preserve the baseline case/assertion inventory with the explicit label exceptions in Shared helper file.

**Exit Criteria**: Both revised harnesses pass from one helper; the baseline assertion inventory is accounted for.

### Phase 1: Cases that bind
**Goal**: Make the unreadable and leading-dash regressions fail when the runner contract breaks.

**Tasks**:
- [ ] Rewrite the unreadable-prompt case to assert exit 1 and the guard's stderr text, skipping as root, and run the leading-dash case on the JSON and resume paths (depends on: Phase 0) - Acceptance: recheck that the current runner still contains the cat-failure guard and the old revision lacks it; skip/report if superseded. The revised harness and helper replayed against the runner from `bb08599~1` in a disposable scratch repo/worktree FAIL the unreadable-prompt case on a non-root run; against the current runner it PASSes; assert the exact error above, and exercise the root branch by faking `id -u` through a PATH shim; the leading-dash case prints three PASS lines naming plain, json and resume.

**Exit Criteria**: The revised regression fails against the pre-guard runner; current runner and all three leading-dash paths pass; the simulated root branch emits SKIP.

### Phase 2: The record
**Goal**: Make the shipped release gate and changelog match behavior.

**Tasks**:
- [ ] Correct the CHANGELOG whitespace line and add the `record_dispatch` block to `dev/bin/release-checks` (depends on: Phase 1) - Acceptance: recheck the whitespace-guard and missing-registration premises, skip/report a changed premise. The whitespace subject under Unreleased explicitly names both `-f` and positional input, preserving unrelated entries; `rg -c 'test_record_dispatch.py' dev/bin/release-checks` prints 1; `bash dev/bin/release-checks` green.

**Exit Criteria**: Targeted Unreleased assertions and release-checks pass.

## Test Strategy

### Critical Scenarios
- **Happy path**: both scripts green from one helper; release-checks runs the dispatch ledger tests.
- **Edge case**: root runs the suite → the unreadable-prompt case reports SKIP, never a vacuous PASS.
- **Error case**: the guard is removed from `codex-run.sh` → the unreadable-prompt case FAILs.

## Risks
- **Sourcing changes `$0`-relative paths**: the helper resolves paths from `BASH_SOURCE[0]`, and both scripts keep their own `cd`.
- **A folded case loses a distinct assertion**: each fold retains the distinct checks in the host case, with only location/helper adaptation as needed; the combined PASS label names both checks. Preserve the case/assertion inventory captured before edits.
