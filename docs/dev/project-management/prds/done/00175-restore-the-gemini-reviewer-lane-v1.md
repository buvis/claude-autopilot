---
catchup: skip
design: skip
---

# Restore the gemini reviewer lane

Source: PRD 00173's review cycle 1 (`dev/local/reviews/00173-guard-the-canonical-read-in-the-doctor-verdict-v1-review-1.md`, Carl's section). Filed 2026-09-05.

## Overview

### Problem Statement

Carl, the panel's frontend and design specialist, cannot run on this host. Both backends `gemini-run.sh` supports fail, and neither failure is transient:

1. **copilot** (the preferred backend): `DEFAULT_COPILOT_MODEL="gemini-3.1-pro-preview"` at `skills/use-gemini/scripts/gemini-run.sh:73` is no longer served. Live: `Error: Model "gemini-3.1-pro-preview" from --model flag is not available.`, exit 1.
2. **native gemini** (the fallback, forced with `GEMINI_BACKEND=gemini`): `IneligibleTierError: This client is no longer supported for Gemini Code Assist for individuals`, `reasonCode: UNSUPPORTED_CLIENT`, `tierId: free-tier`, pointing at the Antigravity suite. Exit 1.

So `review-work-completion` silently degrades from five lenses to four on every cycle, and the only trace is one line in each review file. `references/agent-invocation.md` treats a non-zero `gemini-run.sh` as graceful degradation, which is right for a quota trip and wrong for a permanently dead pin.

The pack's own gate cannot catch it. `skills/use-gemini/scripts/test_gemini_run.sh` stubs the backend binary and asserts argv construction only, so `dev/bin/release-checks` prints `PASS: plain -f argv is exactly: --model gemini-3.1-pro-preview --allow-all-tools --deny-tool=write -p <PROMPT>` while that exact model is unavailable. A green suite certifies a dead configuration.

### Target Users

Anyone running `/autopilot:review-work-completion` or `/autopilot:run-autopilot`, who currently loses a reviewer without being told it is permanent.

### Success Metrics

- `gemini-run.sh -f <prompt> -o <out>` exits 0 and writes reviewer output on at least one backend on this host.
- A backend that rejects the pinned model, or refuses the client's tier, exits with a code distinct from a generic runtime failure, and the caller can tell "permanently unavailable" from "failed this once".
- The model pin has exactly one definition, and a documented command reports whether the backend still serves it.
- Once a cycle records the reserved exit code, every later cycle and PRD in the same batch skips Carl without a dispatch or retry, and each later review file says so in one line (added 2026-09-05 from discovery 00177).

## Functional Decomposition

### Capability: Gemini backend selection

#### Feature: A served model
- **Description**: the copilot default model names something copilot actually serves.
- **Inputs**: the backend's own model listing.
- **Outputs**: `DEFAULT_COPILOT_MODEL` set to a served id; `test_gemini_run.sh`'s argv assertion updated to match.
- **Behavior**: probe the installed copilot for its served models, pick the closest equivalent to Gemini 3.1 Pro, and repoint the single constant. If copilot serves no Gemini model at all, decide and record whether Carl moves to a different backend or is retired from the roster.

#### Feature: Unavailability is a distinct exit code
- **Description**: an unavailable model or ineligible tier is reported as its own failure class, not folded into "the CLI exited non-zero".
- **Inputs**: backend stderr matching the model-unavailable and ineligible-tier shapes.
- **Outputs**: a reserved exit code (mirroring `codex-run.sh`'s exit 3 for "unavailable"), with the reason on stderr.
- **Behavior**: `gemini-run.sh` classifies these two stderr shapes before propagating the child's exit code. `review-work-completion` step 1/5 records the reviewer as permanently unavailable rather than a one-off skip.

#### Feature: The pin's staleness is detectable
- **Description**: an operator can check the pin without reading a review file.
- **Inputs**: none beyond an installed backend CLI.
- **Outputs**: a documented command reporting whether the pinned model is served.
- **Behavior**: add a probe subcommand or documented one-liner to `skills/use-gemini/SKILL.md`. It must NOT run inside `dev/bin/release-checks` — that suite is hermetic and stubs its binaries, and a network call there would make releases fail on an offline machine.

### Capability: A dead lane stays off for the batch

#### Feature: A permanently unavailable Carl is skipped for the rest of the batch
- **Description**: after one cycle records the reserved exit code, no later cycle or PRD in the same batch dispatches or retries Carl.
- **Inputs**: the reserved exit code from `gemini-run.sh` in any cycle's step 5.
- **Outputs**: `state.batch.unavailable_reviewers: ["carl"]`, written once when the code fires (merge into `state.json` with sibling fields untouched, the way step 5 stamps `review_lenses`); `state.batch` survives the per-PRD reset (`cli/records.py` `PER_PRD_RESET_FIELDS` preserves `batch` in full) and dies with the batch, so a repaired Carl returns on the next batch. Step 1's optional-Carl check reads the field before probing any binary and, when `carl` is listed, skips him with no dispatch, no retry and no `ui` key in `state.review_lenses`. Every later review file carries the line `carl: skipped (permanently unavailable since cycle {n} of {prd})` and its `reviewers:` field omits him. `skills/run-autopilot/references/state-schema.md` documents the field.
- **Behavior**: on a standalone run with no `state.json` the field cannot exist, so the check falls through to today's binary probe. `check_review_file.py` needs no change: `reviewers:` already omits lanes that did not run.

## Structural Decomposition

### Repository Structure

```
skills/use-gemini/scripts/gemini-run.sh        # Maps to: all three features
skills/use-gemini/scripts/test_gemini_run.sh   # Maps to: argv pin, new exit-code cases
skills/use-gemini/SKILL.md                     # Maps to: the probe command, exit codes
skills/review-work-completion/SKILL.md         # Maps to: the batch-scoped skip (step 1, steps 5/6)
skills/run-autopilot/references/state-schema.md            # Maps to: batch.unavailable_reviewers
skills/review-work-completion/scripts/test_carl_skip_prose.py  # Maps to: pins the field and the skip line
CHANGELOG.md
```

### Module: gemini-runner
- **Maps to capability**: Gemini backend selection
- **Responsibility**: model pin, backend fallback, failure classification.
- **Exports**: none new; the script's flags stay as they are.

### Module: review-roster
- **Maps to capability**: A dead lane stays off for the batch
- **Responsibility**: the step-1 read of `state.batch.unavailable_reviewers`, the one-time write when the reserved code fires, the review-file skip line, and the schema entry.
- **Exports**: none (skill prose plus a prose contract test).

## Dependency Graph

### Foundation Layer (Phase 0)
No dependencies.

- **gemini-runner**: the pin and the exit-code classification.

### Core Layer (Phase 2)
- **review-roster**: Depends on [gemini-runner] (it reads the reserved exit code Phase 0 defines).

## Implementation Phases

### Phase 0: Repoint the pin and classify unavailability
**Goal**: Carl runs again, and a dead backend says so distinctly.

**Tasks**:
- [x] Probe the installed copilot for served models, repoint `DEFAULT_COPILOT_MODEL`, and update the argv assertion in `test_gemini_run.sh` to the new id (no deps) - Acceptance: `bash skills/use-gemini/scripts/test_gemini_run.sh` green, and a real `gemini-run.sh -f <prompt> -o <out>` exits 0 writing non-empty output.
- [x] Classify model-unavailable and ineligible-tier stderr as a reserved exit code, with stub-driven cases in `test_gemini_run.sh` (depends on task 1) - Acceptance: `bash dev/bin/release-checks` green with the two new cases present.

### Phase 1: Make the pin auditable
**Goal**: nobody learns the pin is dead from a review file again.

**Tasks**:
- [x] Document a probe command in `skills/use-gemini/SKILL.md`, listing the new exit code alongside the existing ones; CHANGELOG `**use-gemini**` under Fixed (depends on Phase 0) - Acceptance: the doc names the probe and every exit code the script can return.

**Exit Criteria**: `bash dev/bin/release-checks` green; a live Carl dispatch produces reviewer output.

### Phase 2: Keep a dead Carl off for the batch
**Goal**: one reserved exit code silences Carl until the batch ends, instead of a dispatch and a retry every cycle.

**Tasks**:
- [x] In `skills/review-work-completion/SKILL.md`: step 1's optional-Carl paragraph reads `state.batch.unavailable_reviewers` first and skips Carl when `carl` is listed (no dispatch, no retry, no `ui` lens key); step 5 writes the field once when `gemini-run.sh` returns the reserved code (merge into `state.json`, sibling fields untouched, as step 5 does for `review_lenses`); step 6 writes the review-file line `carl: skipped (permanently unavailable since cycle {n} of {prd})` on every later cycle and leaves him out of `reviewers:`; document `batch.unavailable_reviewers` in `skills/run-autopilot/references/state-schema.md`; add `skills/review-work-completion/scripts/test_carl_skip_prose.py` (pattern of `test_codex_resume_contract.py`) asserting `unavailable_reviewers` appears in SKILL.md step 1 and in `state-schema.md`, and the literal `carl: skipped (permanently unavailable` appears in SKILL.md; CHANGELOG `**review-work-completion**` under Added (depends on Phase 0) - Acceptance: `uv run --no-project --with pytest python -m pytest -q skills/review-work-completion/scripts/test_carl_skip_prose.py` green; `rg -c 'unavailable_reviewers' skills/run-autopilot/references/state-schema.md` prints at least 1; `rg -c 'carl: skipped \(permanently unavailable' skills/review-work-completion/SKILL.md` prints at least 1; `bash dev/bin/release-checks` green.

**Exit Criteria**: a cycle after one that recorded the reserved code writes the skip line and dispatches no `gemini-run.sh`.

## Test Strategy

### Critical Scenarios
- **Happy path**: `gemini-run.sh -f prompt -o out` on the repointed model → Expected: exit 0, `out` holds the backend's text.
- **Edge case**: backend reports the model unavailable → Expected: the reserved exit code, reason on stderr, no partial output file.
- **Edge case**: cycle 1 of PRD A records the reserved exit code, then cycle 2 and PRD B's cycle 1 run in the same batch → Expected: no `gemini-run.sh` call, both later review files carry the skip line, `reviewers:` omits carl.
- **Error case**: backend reports an ineligible tier → Expected: the same reserved exit code, and the fallback backend is still attempted first.

## Risks

- The replacement model may behave differently enough to change Carl's review quality; the argv pin makes the swap visible in one place, and the review file records which model ran.
- A probe that calls the network must stay out of `release-checks`, or releases break offline. This is why Phase 1 is documentation plus an opt-in command, not a suite leg.
- A batch-scoped skip outlives a mid-batch repair of the pin; the field dies with the batch, and an operator can delete it from `state.json` at a session boundary to bring Carl back sooner.
