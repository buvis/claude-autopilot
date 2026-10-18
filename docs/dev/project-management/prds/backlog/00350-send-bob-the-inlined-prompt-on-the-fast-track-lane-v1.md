---
design: skip
default_model: sonnet
model_tier_rationale: prose only, every sentence given verbatim, two additive prose tests, no code
---

# Send Bob the inlined prompt on the fast-track lane

Source: batch 202610161547, 2026-10-17. On every fast-track item whose codex output was read (00323, 00325, 00331, 00332, 00334, 00347) Bob's lane came back `Review remains unperformed: the sandbox failed to initialize every file reader`, on the first dispatch and on the one retry alike, so each of those cards was reviewed by four lenses and paid two failed codex runs (about 9 minutes of wall per card, Bob's dispatch rows closed with the error outcome). The mechanism is the operator's seatbelt: the loop runs under `run-agent`, codex applies its own `--sandbox read-only` with a nested `sandbox-exec`, and the outer profile refuses it (`sandbox-exec: sandbox_apply: Operation not permitted`, exit 71 when probed from inside `run-agent`), so every shell command codex issues fails, and his persona names the shell as his only file reader (`agents/bob.md:28`). The user's codex hook `gateguard-fact-force.py` denies his first command once more, but codex retries past that; the 00334 item report blamed that hook, which is a misreading.

## Problem

The fast-track lane renders Bob with `--set CONTEXT_FILE=<absolute path of the context file>` and `--set DIFF_FILE=<absolute path of the staged diff>` (`skills/fast-track/references/lane-dispatch.md:91-100`, `skills/fast-track/SKILL.md:288-297`), so his prompt opens with `Read {CONTEXT_FILE} for review context, and {DIFF_FILE} for the full diff.` (`agents/bob.md:7`) and ends with the instruction to open them with a shell read (`agents/bob.md:28`).
The full lane stopped sending that shape: `skills/review-work-completion/SKILL.md:260` builds the inlined prompt of `skills/review-work-completion/references/retry-policy.md:21-48` (head block, review context verbatim, mid block, diff verbatim inside a diff fence, persona with two edits) before every dispatch, and `skills/review-work-completion/references/agent-invocation.md:47` says no non-inlined first run is left.
The fast-track lane kept the path shape, and its one retry (`skills/fast-track/SKILL.md:398`) resends the same file, so the retry is spent on a run that cannot succeed.

## Solution

The lane keeps the render and Eve's appended sections, then rebuilds Bob's file in the full lane's inlined shape before the row opens. `skills/fast-track/references/lane-dispatch.md` § Bob: codex (`skills/fast-track/references/lane-dispatch.md:170-191`) gains this paragraph after the sentence `Pass absolute paths.`:

`Bob's file is the inlined shape of ${CLAUDE_PLUGIN_ROOT}/skills/review-work-completion/references/retry-policy.md § Inlined prompt (Bob's first dispatch): its head block (the one that says INLINED BELOW as text), with (no pack available this cycle) as the context pack line, the repo root, and the card's gate commands with their results as the test-results lines; the context file verbatim; its mid block with the item's <base-sha>..HEAD range; the staged diff verbatim inside a diff fence; then the render above with that section's two persona edits. Write it over docs/dev/tmp/fast-track-<item>-codex.txt before the row opens; the row, the command and the output path do not change. Codex's own sandbox cannot start inside the operator's seatbelt, so a path he must cat is a lane lost on the first run and on the retry alike; the inlined file is what he reads.`

In `skills/fast-track/SKILL.md` the roster bullet at line 282 becomes `- **Codex.** codex-run.sh carries the consensus prompt to codex in the inlined shape of review-work-completion/references/retry-policy.md § Inlined prompt (Bob's first dispatch), never a prompt he must open with cat (references/lane-dispatch.md § Bob: codex).` with `codex-run.sh`, the reference path and `cat` in backticks, and the bullet at lines 301-306 gains the final sentence `Then rebuild that file in the inlined shape (references/lane-dispatch.md § Bob: codex).` with the reference path in backticks.

## Requirements

### Must have
- The lane-dispatch paragraph and the two SKILL.md sentences above, verbatim apart from the backticks named.
- Fail-first tests in `skills/fast-track/scripts/test_fast_track_prose.py` (registered by the `[checks] fast-track lane` block, `dev/bin/release-checks:186-187`), beside `test_lane_reference_names_every_kind` (`skills/fast-track/scripts/test_fast_track_prose.py:777-798`):
  - `test_bob_receives_the_inlined_prompt_never_a_path` reads the lane reference through `LANE_DISPATCH_MD` (`skills/fast-track/scripts/fast_track_reference_testutil.py:33`), slices the text from `### Bob: codex` to `### Carl: gemini`, and asserts it contains `INLINED BELOW as text`, `retry-policy.md` and `fast-track-<item>-codex.txt`.
  - `test_skill_sends_codex_the_inlined_shape` reads the skill through `document` (`skills/fast-track/scripts/fast_track_prose_testutil.py:346`) and asserts it contains `Inlined prompt (Bob's first dispatch)` and that the sentence carrying it also carries `codex-run.sh`.
- A CHANGELOG `[Unreleased]` Fixed entry under **fast-track**: Bob's codex lane receives the inlined prompt (context and diff in the text), so a seatbelt that blocks codex's own sandbox no longer loses the lens on every card.

### Nice to have
- None.

## Implementation

### Module: lane-dispatch-prose
- **Location**: `skills/fast-track/references/lane-dispatch.md` (§ Bob: codex)
- **Responsibility**: say how Bob's file is built before his row opens
- **Exports**: none

### Module: skill-prose
- **Location**: `skills/fast-track/SKILL.md` (roster bullets)
- **Responsibility**: name the inlined shape where the roster is described
- **Exports**: none

### Module: prose-tests
- **Location**: `skills/fast-track/scripts/test_fast_track_prose.py`
- **Responsibility**: pin the paragraph and the bullet
- **Exports**: none
- New symbols: `test_bob_receives_the_inlined_prompt_never_a_path`, `test_skill_sends_codex_the_inlined_shape`

### Dependencies
- lane-dispatch-prose: No dependencies (foundation)
- skill-prose: No dependencies (foundation)
- prose-tests: Depends on [lane-dispatch-prose, skill-prose]

## Tasks

### Phase 0: Foundation
- [ ] Add the two tests to `skills/fast-track/scripts/test_fast_track_prose.py`. Premise: `rg -c "INLINED BELOW as text" skills/fast-track/references/lane-dispatch.md` prints 0 before the edit; a different count means the reference already changed and the task stops and reports. - Acceptance: `uv run --no-project --with pytest python -m pytest -q skills/fast-track/scripts/test_fast_track_prose.py -k "inlined"` fails both new tests against the current prose.

### Phase 1: Core
- [ ] Add the lane-dispatch paragraph, the two SKILL.md sentences and the CHANGELOG entry (depends on: Phase 0) - Acceptance: `uv run --no-project --with pytest python -m pytest -q skills/fast-track/scripts/test_fast_track_prose.py` passes; `rg -c "INLINED BELOW as text" skills/fast-track/references/lane-dispatch.md` prints 1; `rg -c "Inlined prompt \(Bob's first dispatch\)" skills/fast-track/SKILL.md` prints 1; `rg -n "fast-track.*inlined prompt" CHANGELOG.md` prints one line under `[Unreleased]`.

## Success Criteria

- Both new tests pass and `test_lane_reference_names_every_kind` still passes.
- Post-release signal: the next fast-track item's `codex-output-<item>.txt` carries FIX, VERIFY and KNOWN sections with at least one real `[BOB]` line, and its `fast-track:bob` dispatch row closes `ok` on the first run.
