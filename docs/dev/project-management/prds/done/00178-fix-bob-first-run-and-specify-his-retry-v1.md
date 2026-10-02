---
catchup: skip
design: skip
default_model: sonnet
model_tier_rationale: transcription only - the persona section, both retry-policy sections and the ledger sentences carry their exact text, and the prose test lists its assert strings
---

# Fix Bob's first run and specify his retry

Source: discovery `dev/local/discovery/00177-cut-review-and-test-loop-overhead.md` (reviewed 2026-09-05), measured on PRD 00015 in agent-skills, batch 202609050909. Sibling PRD 00180 moves the codex prompt to stdin, which removes the argv cap on the inlined retry prompt below.

## Overview

### Problem Statement

`agents/bob.md:7` tells codex to `Read {CONTEXT_FILE} ... and {DIFF_FILE}`, and `agents/bob.md:28-39` then says `You CANNOT execute code` and `Do NOT attempt to run commands`. Codex reads files only through shell commands, so whenever it takes the sandbox text literally it refuses to open its own inputs: on 2026-09-05 (`bob-output-00015-c1.txt`) the first run emitted one ⚪ `Cannot statically verify: source and PRD requirements ... which your instructions prohibit` line, `R1..R13: fail`, and `D1..D5: pass`. The driver then hand-built a 39 KB retry prompt with the context, diff and already-run test results inlined; `references/retry-policy.md:19` says only "an amended prompt file", so every cycle reinvents it (~3 min plus two opus driver rounds). And no ledger row records Bob or Carl, so nothing can count dispatches or retries.

### Target Users

Every review cycle under `/autopilot:review-work-completion` and `/autopilot:run-autopilot`, and the operator reading the batch ledger.

### Success Metrics

- A cycle with codex available writes exactly one `{"kind":"bob",...}` start row to `dev/local/autopilot/dispatch-metrics.jsonl`, and the first-run output holds at least one `R{n}: pass` line or one non-⚪ `[BOB]` line. Post-release signal, not judged in-session: the in-session checks are the prose test and the `rg` pins in Phases 0-2.
- `references/retry-policy.md` names the lack-of-input trigger and the inlined retry prompt; `test_retry_policy_prose.py` pins both and runs from `dev/bin/release-checks`.
- `bash dev/bin/release-checks` green.

## Functional Decomposition

### Capability: Bob reads his inputs
The persona stops forbidding the only way codex can read a file.

#### Feature: Persona permits read-only shell
- **Description**: `agents/bob.md` allows read-only shell commands for reading files while still forbidding tests, linters, package managers and writes.
- **Inputs**: `agents/bob.md` lines 26-39 (the `## Sandbox Constraints` section). Line 7 stays as is.
- **Outputs**: the section reads exactly:

  ```
  ## Sandbox Constraints

  You run in a read-only sandbox. Read files with read-only shell commands (`cat`, `sed -n`, `rg`, `ls`); that is how you open {CONTEXT_FILE}, {DIFF_FILE}, {PACK_FILE} and any source file. You CANNOT execute code, tests, linters, or package managers, and you cannot write.

  Perform STATIC analysis only:
  - Read code for logical correctness, patterns, naming, structure
  - Check for missing imports, dead code, type mismatches
  - Review against PRD requirements by reading, not executing
  - Trace data flow and control flow by reading source

  If a criterion requires runtime verification (e.g. "tests pass", "linter clean"), output:
  [BOB] ⚪ Cannot statically verify: {criterion description} | File: N/A | Task: {id}

  Do NOT run tests, linters, builds, or package managers. Do NOT report failures from blocked execution. Never report an inability to read a file you were told to read: read it with `cat`.
  ```
- **Behavior**: `test_agent_registry.py` keeps passing unchanged: the signature line `Perform STATIC analysis only` survives, `tools: Read` is untouched, and the body carries no personal path.

### Capability: The retry is specified
Nothing about the retry lives in a driver's head any more.

#### Feature: Lack-of-input refusal is a named retry trigger
- **Description**: `references/retry-policy.md` defines the one output shape that earns Bob a second dispatch on top of the existing triggers.
- **Inputs**: Bob's `-o` output file after the first run.
- **Outputs**: a new section `## Lack-of-input refusal (Bob)` after `## Retry Mechanism (CLI reviewers vs Alice)` that says: the output is a lack-of-input refusal when ALL THREE hold: `rg -c '^R[0-9]+: pass' <bob-output>` reports 0 (exit 1), `rg -c '^\[BOB\] (🔴|🟠|🟡|✅)' <bob-output>` reports 0 (exit 1), and `rg -c '^\[BOB\] ⚪ Cannot statically verify' <bob-output>` prints at least 1; on that shape send the one retry as the inlined retry prompt (next feature). Any other first-run shape is final: Bob is dispatched exactly once per cycle unless an existing trigger fires (non-zero `codex-run.sh` exit, malformed issue-line format, incomplete per-rule verdicts). The one-retry budget is unchanged; the lack-of-input retry and a format retry share it.
- **Behavior**: `references/agent-invocation.md` § Bob replaces `If codex-run.sh exits non-zero, treat Bob as a failed reviewer (graceful degradation per retry-policy.md); a single failed CLI reviewer does not block the cycle.` with `On a non-zero exit or a lack-of-input refusal, retry once per retry-policy.md § Lack-of-input refusal (Bob); only a failed retry makes Bob a failed reviewer, and a single failed CLI reviewer does not block the cycle.`

#### Feature: The inlined retry prompt is written down
- **Description**: `references/retry-policy.md` states how the retry prompt is assembled, so no cycle rebuilds it by hand.
- **Inputs**: `dev/local/tmp/review-context-{id}.md`, `dev/local/tmp/review-diff-{id}.diff`, the persona prompt `dev/local/tmp/bob-prompt-{id}.md`, and the cycle's already-run test results (the same facts step 6 writes to the review file's `Tests:` line).
- **Outputs**: a new section `## Inlined retry prompt (CLI reviewers)` giving the assembly order and the literal blocks. The file is `dev/local/tmp/bob-prompt-{id}-retry.md` (retained beside the first prompt, never `/tmp`), built as: head block, the review context verbatim, mid block, the diff verbatim inside a ```` ```diff ```` fence, then the persona prompt body with two edits. Dispatch it with the cycle-1 `codex-run.sh -f ... -o <same bob-output path>` command, without `--resume-thread`. Head block, verbatim:

  ```
  IMPORTANT: You run in a restricted sandbox and CANNOT read files or run commands. Everything you need is INLINED BELOW as text. Do not attempt to read any path, and do not report an inability to read files: the review context and the complete diff are both reproduced verbatim in this prompt.

  Context pack: {PACK_FILE contents, or the sentinel `(no pack available this cycle)`}

  Repo root (for path interpretation only): {absolute repo path}

  Test results for the reviewed revision (already run, do not ask for them):
  {the cycle's test results, one line per command}

  ================================================================================
  # REVIEW CONTEXT (inlined verbatim)
  ================================================================================
  ```

  Mid block, verbatim:

  ```
  ================================================================================
  # FULL DIFF (inlined verbatim), range {base}..{head}, path-scoped to this PRD
  ================================================================================
  ```

  The two persona edits: replace `Review the completed work against PRD requirements. Explore the codebase as needed.` with `Review the completed work against PRD requirements using ONLY the inlined text above.`; and append after the `OUTPUT FORMAT IS MANDATORY` block the line `Do NOT emit "Cannot statically verify" lines about reading files or test results: both are supplied above. Only mark a rule fail when the evidence above actually shows a failure.`
- **Behavior**: the retry keeps the same `{id}` and `-o` path as the first run (the retry policy already says so), and the review file's Bob section records `after one retry (inlined)` when it ran. Until PRD 00180 lands, the assembled file must stay under the host's argv limit (1 MiB total on macOS); the 2026-09-05 prompt was 39 KB.

### Capability: The ledger sees reviewers
Dispatch counts become the acceptance contract for the review phase too.

#### Feature: CLI reviewer dispatches are ledger rows
- **Description**: `review-work-completion` opens and closes a `record_dispatch.py` row for every Bob and Carl dispatch, retries included.
- **Inputs**: the assembled prompt file and the cycle `{id}` step 5 already uses for output paths.
- **Outputs**: in step 5, immediately before each CLI reviewer's background Bash: `python3 ${CLAUDE_PLUGIN_ROOT}/skills/work/scripts/record_dispatch.py start --kind bob --task review-{id} --prompt-file <absolute prompt path>` (and `--kind carl` for Carl); hold the printed id. In step 6, after the output file is read: `record_dispatch.py end <id> --outcome ok` for a usable output, `--outcome error --detail "exit <n>"` for a non-zero exit, `--outcome error --detail "lack-of-input"` for the refusal shape. A retry opens a second `start` row under the same `--task` and its `end` row carries `--detail retry`.
- **Behavior**: the `--kind` value is free text in `record_dispatch.py`, so no script change. On a standalone run with no `dev/local/autopilot/` the script prints an id and writes nothing (existing behavior), so the calls need no guard. Bob's Claude fallback (exit 3) is a Task subagent and gets no row.

## Structural Decomposition

### Repository Structure

```
agents/bob.md                                                       # Maps to: persona permits read-only shell
skills/review-work-completion/references/retry-policy.md            # Maps to: lack-of-input trigger, inlined retry prompt
skills/review-work-completion/references/agent-invocation.md        # Maps to: Bob section pointer
skills/review-work-completion/SKILL.md                              # Maps to: ledger rows (steps 5 and 6)
skills/review-work-completion/scripts/test_retry_policy_prose.py    # Maps to: prose pins (new)
dev/bin/release-checks                                              # Maps to: runs the new prose test
CHANGELOG.md
```

### Module: bob-persona
- **Maps to capability**: Bob reads his inputs
- **Responsibility**: the `## Sandbox Constraints` section of `agents/bob.md`.
- **Exports**: none (a persona file).

### Module: retry-policy
- **Maps to capability**: The retry is specified
- **Responsibility**: the two new sections in `retry-policy.md` and the one-sentence pointer in `agent-invocation.md`.
- **Exports**: none (skill prose).

### Module: review-ledger
- **Maps to capability**: The ledger sees reviewers
- **Responsibility**: the `record_dispatch.py start`/`end` sentences in `review-work-completion/SKILL.md` steps 5 and 6.
- **Exports**: none (skill prose; `record_dispatch.py` is unchanged).

### Module: prose-pins
- **Maps to capability**: The retry is specified; The ledger sees reviewers; Bob reads his inputs
- **Responsibility**: `test_retry_policy_prose.py`, mirroring `test_codex_resume_contract.py` (stdlib unittest, section-scoped substring asserts), wired into `dev/bin/release-checks`.
- **Exports**: none.

## Dependency Graph

### Foundation Layer (Phase 0)
No dependencies - built first.

- **bob-persona**: the wording change.

### Core Layer (Phase 1)
- **retry-policy**: Depends on [bob-persona] (its persona edits quote the persona's lines).
- **review-ledger**: Depends on [] (independent prose; sequenced here to keep the SKILL.md edits in one phase).

### Integration Layer (Phase 2)
- **prose-pins**: Depends on [bob-persona, retry-policy, review-ledger].

## Implementation Phases

### Phase 0: Foundation
**Goal**: the persona no longer forbids reading.

**Tasks**:
- [ ] Replace `agents/bob.md`'s `## Sandbox Constraints` section with the exact text above; CHANGELOG `**review-work-completion**` under Fixed: `Bob's persona permits read-only shell reads, so codex no longer refuses to open its own context and diff` (no deps) - Acceptance: `rg -c 'read-only shell commands' agents/bob.md` prints 1; `rg -c 'Do NOT attempt to run commands' agents/bob.md` exits 1; `uv run --no-project --with pytest python -m pytest -q skills/review-work-completion/scripts/test_agent_registry.py` green.

**Exit Criteria**: the persona's two conflicting lines are gone and the registry suite is green.

### Phase 1: Core
**Goal**: the retry and the ledger rows are written policy.

**Tasks**:
- [ ] Add `## Lack-of-input refusal (Bob)` and `## Inlined retry prompt (CLI reviewers)` to `retry-policy.md` with the three `rg -c` commands, the assembly order, the head and mid blocks verbatim and the two persona edits; replace the graceful-degradation sentence in `agent-invocation.md` § Bob with the pointer sentence above; CHANGELOG `**review-work-completion**` under Added (depends on: Phase 0) - Acceptance: `rg -c "rg -c '\^R\[0-9\]\+: pass'" skills/review-work-completion/references/retry-policy.md` prints 1; `rg -c 'INLINED BELOW as text' skills/review-work-completion/references/retry-policy.md` prints 1; `rg -c 'Lack-of-input refusal' skills/review-work-completion/references/agent-invocation.md` prints 1.
- [ ] Add the `record_dispatch.py start --kind bob|carl --task review-{id}` sentence to `review-work-completion/SKILL.md` step 5 (in the paragraph that launches the background Bash calls) and the `end` sentence with the three outcome forms to step 6, plus the `after one retry (inlined)` wording for the Bob section; CHANGELOG `**review-work-completion**` under Added (depends on: Phase 0) - Acceptance: `rg -c 'record_dispatch.py start --kind bob' skills/review-work-completion/SKILL.md` prints 1; `rg -c 'record_dispatch.py end' skills/review-work-completion/SKILL.md` prints at least 1; `rg -c -- '--kind carl' skills/review-work-completion/SKILL.md` prints 1.

**Exit Criteria**: a driver reading step 5, step 6 and `retry-policy.md` can run Bob's retry and record both dispatches without inventing anything.

### Phase 2: Integration
**Goal**: the prose cannot drift back silently.

**Tasks**:
- [ ] Write `skills/review-work-completion/scripts/test_retry_policy_prose.py` (stdlib unittest, the `_section` helper pattern of `test_codex_resume_contract.py`) asserting: `retry-policy.md` § `Lack-of-input refusal (Bob)` contains `rg -c '^R[0-9]+: pass'`, `(🔴|🟠|🟡|✅)` and `⚪ Cannot statically verify`; § `Inlined retry prompt (CLI reviewers)` contains `INLINED BELOW as text`, `bob-prompt-{id}-retry.md` and `using ONLY the inlined text above`; `SKILL.md` contains `record_dispatch.py start --kind bob` and `--kind carl`; `agent-invocation.md` § Bob contains `Lack-of-input refusal`; `agents/bob.md` contains `read-only shell commands` and not `Do NOT attempt to run commands`. Add a `[checks] retry policy prose` block to `dev/bin/release-checks` running it the way the registry block does (depends on: Phase 1) - Acceptance: `uv run --no-project --with pytest python -m pytest -q skills/review-work-completion/scripts/test_retry_policy_prose.py` green; `rg -c 'test_retry_policy_prose.py' dev/bin/release-checks` prints 1; `bash dev/bin/release-checks` green.

**Exit Criteria**: `bash dev/bin/release-checks` green with the new block present.

## Test Strategy

### Critical Scenarios
- **Happy path**: codex reads the context and diff with `cat` on the first run → Expected: at least one `R{n}: pass` line, one `bob` start row and one `end` row with `--outcome ok`.
- **Edge case**: Bob's first output is `R1..R13: fail` plus one ⚪ `Cannot statically verify: source` line → Expected: the two count commands report 0 and the ⚪ line is present, the driver sends the inlined retry, and the ledger holds two `bob` start rows with the second's end row marked `retry`.
- **Error case**: `codex-run.sh` exits 3 → Expected: the Claude fallback runs as today, the ledger holds one `bob` row ended `--outcome error --detail "exit 3"`, and no retry prompt is assembled.

## Risks

- **Codex still refuses despite the wording**: the inlined retry is now specified and its rows are in the ledger; `jq -c 'select(.detail=="retry")' dev/local/autopilot/ledger/dispatch-metrics.jsonl` counts retries per batch, and a count that stays above zero reopens the persona question.
- **Argv cap before PRD 00180 lands**: the inlined prompt travels as one argv string until then; on this macOS host the limit is 1 MiB total and the observed prompt was 39 KB, so it is a Linux-host concern only.

## Post-completion notes (2026-09-06)

Converged in review cycle 2 (batch 202609061630). The five deferred rows were walked on 2026-09-06 in the
config-audit closure walkthrough (`~/.claude/dev/local/audit-results/2026-09-05.md`); the ledger's decision
fields get backfilled at batch end.

- qwen dispatch hits `:8080` although the preflight resolved `llamacpp8002` (two aborted dispatches on task 3;
  `state.qwen_preflight` latched `endpoint_unreachable` for the batch): agent-skills use-qwen PRD 00078 makes
  the preflight probe the pi dispatch path and pins the dispatch.
- The python-first review id (commit fda6abd, not one of this PRD's tasks) had no test pinning the order:
  `test_step_5_7_mints_the_reviewer_id_with_python_before_uuidgen` added to
  `skills/work/scripts/test_dispatch_prose.py` (red on fda6abd~1, green after), committed with the 0.5.2
  release.
- Deeper pins on the retry-policy prose beyond the Phase 2 assertion list, the subTest rewrite of
  `test_retry_policy_prose.py`, and the numbered-gates reformat of `retry-policy.md`: accepted as the reviewers
  argued; the prose is the contract and the pins are this PRD's list.
