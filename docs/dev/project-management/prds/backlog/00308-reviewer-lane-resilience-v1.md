---
catchup: run
design: run
default_model: opus
model_tier_rationale: a deadline that must kill a process group is a timing path; the rest is transcription
---

# Reviewer lane resilience: inline Bob first, latch Carl on auth failure, kill on timeout

Source: `docs/dev/project-management/audit-results/loop-efficiency-2026-10-13.md` (Q4, E2-E5).

## Overview

### Problem Statement
Four lane defects cost batch 202610111300 about six hours of review-lane time and left orphan processes.

Bob's first dispatch sends a 9 KB prompt that references files; in 5 of 8 cycles codex refused it as lack-of-input and only the inlined retry (134-705 KB) dispatched with `codex-run.sh` passed (`skills/review-work-completion/references/retry-policy.md:21-27`); 00282 cycle 1 paid 63 minutes for the refusal. PRD 00180 routes the codex prompt through stdin, so the argv limit the policy still cites at line 54 no longer applies.

Carl's copilot backend fails with `Error: Authentication failed` on every cycle under the sandbox; `permanently_unavailable` (`skills/use-gemini/scripts/gemini-run.sh:199-201`) matches only model and tier rejections, so the run exits 1 and the latch on `state.batch.unavailable_reviewers` (`skills/review-work-completion/SKILL.md:288-294`) never fires; every cycle re-dispatches him twice: 16 dispatches, 0 ok, 4.6 h.

When exit 4 does fire, the native fallback `run_gemini` (`skills/use-gemini/scripts/gemini-run.sh:318-331`) has no deadline; on 00282 cycle 2 it stalled 53 minutes with no output.

The fail-first replay's `_run_in_worktree` (`skills/review-work-completion/scripts/replay_tests_against_base.py:98-136`) runs pytest with a plain `subprocess.run` timeout, which kills the runner but not its process group, so a timed-out replay leaves a pytest grandchild running on a deleted worktree; two such orphans and two gemini orphans sat idle for 10 h.

Retry rows are opened by hand with a typed task id beside the `dispatch_rows` ids (`skills/review-work-completion/SKILL.md:262`); three cycles named them by date (`review-20261013-c1`), so per-PRD lane attribution broke.

### Target Users
The unattended review session and the operator reading `dispatch-metrics.jsonl`.

### Success Metrics
- Bob: at most one codex dispatch per cycle when the output is well-formed (`dispatch-metrics.jsonl` rows per `review-<id>` task, kind `bob`).
- Carl: after one auth failure in a batch, zero further `carl` rows in that batch.
- Zero `gemini` or `pytest` processes reparented to launchd after a lane or replay timeout (`pgrep -P 1 -lf "gemini|pytest"` empty).
- Every retry row carries the same `task` as the row it retries.

## Functional Decomposition

### Capability: CLI reviewer dispatch
Bob and Carl run as background Bash lanes; this capability decides what they get and when they stop.

#### Feature: Bob inlined on the first run
- **Description**: the first Bob dispatch of a cycle uses the inlined prompt shape.
- **Inputs**: the review context, the diff, the pack file, the persona body; the shape at `skills/review-work-completion/references/retry-policy.md:25-54`, dispatched with `codex-run.sh`.
- **Outputs**: `docs/dev/tmp/bob-prompt-{id}.md` built as the inlined shape; the lack-of-input retry rule is deleted.
- **Behavior**: SKILL.md step 5 builds the first prompt with the head block, context, mid block, diff and the two persona edits exactly as the inlined-retry section specifies today; the lack-of-input section is removed; the one-retry budget stays for the format and verdict retries. The review file's Bob section no longer carries `after one retry (inlined)`.

#### Feature: Auth failure is permanent for the batch
- **Description**: a copilot authentication failure exits 4 like a tier rejection.
- **Inputs**: the backend's stderr.
- **Outputs**: exit 4 and the stderr line `ERROR: copilot permanently unavailable (authentication failed).`
- **Behavior**: `permanently_unavailable` also matches `Authentication failed` and `Copilot Requests permission`; the SKILL.md latch is unchanged and now fires.

#### Feature: Bounded native fallback
- **Description**: the native gemini fallback ends after a deadline.
- **Inputs**: `GEMINI_FALLBACK_TIMEOUT` seconds, default 900 (guess).
- **Outputs**: exit 4 with `ERROR: gemini fallback produced no output within <n>s.` when the deadline passes.
- **Behavior**: the fallback runs in its own process group; on the deadline the group is killed, partial output is not published, and the latch applies (exit 4). An auth-failure exit 4 skips the fallback entirely: the fallback exists for a rejected model, not a missing credential.

#### Feature: Retry rows inherit their task
- **Description**: `record_dispatch.py retry <id>` opens the retry row.
- **Inputs**: the id of the row being retried.
- **Outputs**: a new `start` row with the same `kind` and `task`, `detail: "retry of <id>"`, and the new id on stdout.
- **Behavior**: the retry case beside the `dispatch_rows` ids (`skills/review-work-completion/SKILL.md:262`) calls the verb instead of typing the task; `_open_row` (`skills/run-autopilot/cli/review_stage.py:654-689`) is unchanged.

### Capability: Timeout hygiene
A timeout kills what it started.

#### Feature: Replay kills its process group
- **Description**: a timed-out fail-first replay leaves no pytest behind.
- **Inputs**: the `--timeout` flag parsed beside `replay` (`skills/review-work-completion/scripts/replay_tests_against_base.py:195-206`).
- **Outputs**: the existing `runner did not complete` skip reason.
- **Behavior**: `_run_in_worktree` spawns with `start_new_session=True`, waits with `communicate(timeout=...)`, and on `TimeoutExpired` calls `os.killpg(proc.pid, SIGKILL)` before returning; the worktree removal in the `finally` block (`:133-135`) is unchanged.

## Structural Decomposition

### Repository Structure

```
skills/
├── review-work-completion/
│   ├── SKILL.md                                  # Maps to: Bob inlined on the first run, Retry rows inherit their task
│   ├── references/retry-policy.md                # Maps to: Bob inlined on the first run
│   ├── scripts/replay_tests_against_base.py      # Maps to: Replay kills its process group
│   ├── scripts/test_replay_timeout_kill.py       # Maps to: Replay kills its process group
│   └── scripts/test_bob_inlined_first_prose.py   # Maps to: Bob inlined on the first run
├── use-gemini/scripts/
│   ├── gemini-run.sh                             # Maps to: Auth failure is permanent, Bounded native fallback
│   └── test_gemini_run_unavailable.py            # Maps to: Auth failure is permanent, Bounded native fallback
└── work/scripts/
    ├── record_dispatch.py                        # Maps to: Retry rows inherit their task
    └── test_record_dispatch.py                   # Maps to: Retry rows inherit their task
```

### Module: bob-dispatch
- **Maps to capability**: CLI reviewer dispatch
- **Responsibility**: the first Bob prompt is the inlined shape; no lack-of-input retry
- **Exports**: none (prose)
- New symbols: `test_bob_inlined_first_prose.py`, `test_first_bob_prompt_is_the_inlined_shape`, `test_no_lack_of_input_retry_remains`, `test_retry_case_uses_the_retry_verb`

### Module: gemini-runner
- **Maps to capability**: CLI reviewer dispatch
- **Responsibility**: classify auth failure as permanent; bound the fallback; never fall back on a missing credential
- **Exports**: `permanently_unavailable()` (extended), `run_cmd()` (unchanged)
- New symbols: `GEMINI_FALLBACK_TIMEOUT`, `test_gemini_run_unavailable.py`, `test_auth_failure_exits_4_without_fallback`, `test_tier_rejection_still_falls_back`, `test_fallback_with_no_output_exits_4_at_the_deadline`, `test_fallback_leaves_no_child_running`

### Module: dispatch-retry
- **Maps to capability**: CLI reviewer dispatch
- **Responsibility**: a retry row copies kind and task from its original
- **Exports**: `start_row()` (unchanged), new `retry` verb
- New symbols: `retry_row`, `test_retry_row_copies_kind_and_task`, `test_retry_of_unknown_id_exits_1`

### Module: replay-kill
- **Maps to capability**: Timeout hygiene
- **Responsibility**: a replay timeout kills the runner's process group
- **Exports**: `replay()` (unchanged)
- New symbols: `test_replay_timeout_kill.py`, `test_timeout_kills_the_runner_process_group`

## Dependency Graph

### Foundation Layer (Phase 0)
No dependencies - built first.

- **replay-kill**: the process-group kill, self-contained
- **gemini-runner**: the classifier and the bounded fallback, self-contained

### Core Layer (Phase 1)
- **dispatch-retry**: Depends on [] (touches `record_dispatch.py`; a sibling PRD adds artifact-backed closure to `_handoff` in the same file, different function)

### Integration Layer (Phase 2)
- **bob-dispatch**: Depends on [dispatch-retry] (its retry case names the new verb)

## Implementation Phases

### Phase 0: Foundation
**Goal**: timeouts and auth failures end cleanly.

**Tasks**:
- [ ] Write `skills/review-work-completion/scripts/test_replay_timeout_kill.py` (`test_timeout_kills_the_runner_process_group`: a fake runner script that spawns `sleep 300` as a grandchild and never prints; after `_run_in_worktree` returns the skip reason, no process in the runner's group is alive) then make `_run_in_worktree` spawn with `start_new_session=True` and kill the group on `TimeoutExpired` (no deps) - Acceptance: the test is red before the change and `uv run --no-project --with pytest python -m pytest -q skills/review-work-completion/scripts/test_replay_timeout_kill.py skills/review-work-completion/scripts/test_replay_tests_against_base.py` passes after it; the new file is named in a `[checks]` block of `dev/bin/release-checks`.
- [ ] Write `skills/use-gemini/scripts/test_gemini_run_unavailable.py` (fake `copilot` and `gemini` binaries on PATH: `test_auth_failure_exits_4_without_fallback`, `test_tier_rejection_still_falls_back`, `test_fallback_with_no_output_exits_4_at_the_deadline` with `GEMINI_FALLBACK_TIMEOUT=2`, `test_fallback_leaves_no_child_running`) then extend `permanently_unavailable` and bound the fallback in `gemini-run.sh` (no deps) - Acceptance: the four tests are red before the change and `uv run --no-project --with pytest python -m pytest -q skills/use-gemini/scripts/test_gemini_run_unavailable.py` passes after it; the file is named in `dev/bin/release-checks`.

**Exit Criteria**: both test files green and registered.

### Phase 1: Core
**Goal**: retry rows are opened by code.

**Tasks**:
- [ ] Add the `retry <id>` verb to `skills/work/scripts/record_dispatch.py` (`retry_row(autopilot_dir, original_id) -> str`) and `test_retry_row_copies_kind_and_task` plus `test_retry_of_unknown_id_exits_1` to `skills/work/scripts/test_record_dispatch.py` (depends on: Phase 0) - Acceptance: `uv run --no-project --with pytest python -m pytest -q skills/work/scripts/test_record_dispatch.py` passes with both new tests.

**Exit Criteria**: `python3 skills/work/scripts/record_dispatch.py retry <id>` prints a new id whose row carries the original's `kind` and `task`.

### Phase 2: Integration
**Goal**: the review skill uses the new shapes.

**Tasks**:
- [ ] Rewrite `skills/review-work-completion/references/retry-policy.md` (delete the lack-of-input section; retitle the inlined-retry section to the inlined prompt and make it the first-run shape; drop the sentence at line 54 that cites PRD 00180 as pending), update step 5's Bob dispatch and the `after one retry (inlined)` wording in `skills/review-work-completion/SKILL.md` (line 430 today), point the retry case at line 262 to `record_dispatch.py retry <id>`, write `skills/review-work-completion/scripts/test_bob_inlined_first_prose.py` (`test_first_bob_prompt_is_the_inlined_shape`, `test_no_lack_of_input_retry_remains`, `test_retry_case_uses_the_retry_verb`), register it, and add two CHANGELOG `[Unreleased]` entries (**review-work-completion** Changed for Bob and the retry verb; **use-gemini** Fixed for the auth latch and the bounded fallback) (depends on: Phase 1) - Acceptance: `uv run --no-project --with pytest python -m pytest -q skills/review-work-completion/scripts/test_bob_inlined_first_prose.py skills/review-work-completion/scripts/test_retry_policy_prose.py` passes (the retry-policy prose test updated, not deleted); `rg -c 'lack-of-input' skills/review-work-completion/SKILL.md skills/review-work-completion/references/retry-policy.md` prints 0 for both.

**Exit Criteria**: `bash dev/bin/release-checks` passes.

## Test Strategy

### Critical Scenarios
- **Happy path**: Bob's first run returns findings and verdict lines → Expected: one `bob` row per cycle, outcome `ok`.
- **Edge case**: copilot answers `Authentication failed` → Expected: exit 4, no fallback, `carl` latched in `state.batch.unavailable_reviewers`.
- **Error case**: the replay runner hangs → Expected: skip reason `runner did not complete`, no pytest left in the group.

## Risks

- **A 700 KB first prompt costs more codex input per cycle**: it is the prompt that succeeds today anyway; the refused 9 KB run is pure overhead.
- **Latching on auth hides a transient token outage for the whole batch**: the operator clears the latch as the paragraph on `state.batch.unavailable_reviewers` documents (`skills/review-work-completion/SKILL.md:288-297`); a batch-long wrong latch costs less than two dead dispatches per cycle.
