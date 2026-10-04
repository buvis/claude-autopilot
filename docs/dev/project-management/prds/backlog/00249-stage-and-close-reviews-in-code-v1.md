---
catchup: skip
design: run
default_model: opus
model_tier_rationale: invents two CLI contracts (review-stage output, review-close input) that the review skill and phase-review prose consume
---

# Stage and close review cycles in code

## Overview

### Problem Statement

A review session spends about 60% of its time on orchestrator work that is
deterministic. Measured on batch `202610031511` (0.7.0), see
`docs/dev/project-management/notes/review-phase-waste-2026-10-04.md`:

| Session | Total | Before reviewers launch | Reviewers | After |
|---|---|---|---|---|
| 00244 c1 | 25.5 min | 9.0 min | 9.8 min | 7.2 min |
| 00242 c1 | 38.1 min | 15.5 min | 11.3 min | 11.1 min |

Before launch, the opus/xhigh orchestrator copies tasks from `state.json`
into `review-tasks-{id}.md`, copies and edits the PRD into
`review-prd-{id}.md`, runs `gather-context.sh` and the three mechanical
scripts one call at a time, reads nine reference files, writes each reviewer
prompt with the Write tool (26-73 s of generation each), stamps the lens
roster and opens dispatch rows. After the reviewers, it writes decision
arrays through `/tmp` JSON files and adds each rework or sweep task with its
own Write plus `task-add` pair. Two cycles per PRD is the norm, so this costs
roughly 30-45 minutes per PRD.

It also re-runs the full gate inside review: twice on 00244 c1 (the second
only to read counts it could not extract), because `last-verification.json`
is skipped whenever its `sha` lags HEAD, even when the only commits since are
store and handoff commits.

`autopilot enter` (0.7.0) cut session orientation from ~8 min to ~45 s by
moving the same kind of work into code. `skills/work/scripts/render_prompt.py`
already renders build persona prompts. This PRD does the same for review.

### Target Users

The autopilot review phase (loop and interactive) and standalone
`/autopilot:review-work-completion` runs.

### Success Metrics

- A review session launches its reviewers within 3 minutes of invoking the
  skill (from ~9-15 min), measured by `review-stage`'s own timing row.
- No reviewer prompt is written with the Write tool; every one comes from
  `review-stage`.
- Post-review bookkeeping is one `review-close` call.
- The reviewer roster, the number of cycles, the rework cap and every lens's
  prompt content are unchanged (prompt content pinned by golden tests).

## Functional Decomposition

### Capability: Review staging

Everything between "the skill starts" and "the reviewers launch", as one call.

#### Feature: Stage the review inputs
- **Description**: `autopilot review-stage` writes every input file a cycle needs.
- **Inputs**: `--state` (default store path), `--cycle-id`, optional `--since <sha>` for an incremental cycle.
- **Outputs**: `docs/dev/tmp/review-tasks-{id}.md`, `review-prd-{id}.md`, `review-context-{id}.md`, `review-diff-{id}.diff`, the engram pack when it succeeds; a JSON summary on stdout naming each path, the diff scope and the pack status.
- **Behavior**: tasks come from `state.tasks`, the PRD from `state.prd`'s wip path, context and diff from `gather-context.sh` (same flags as today), and the mechanical-facts, tautology and replay blocks are appended to the context file exactly as step 3 does now. An `engram pack` failure is recorded as `pack: failed (<reason>)` and never fails the stage, matching today's rule; a "not inside a registered repo" failure names `gita add` in the reason.

#### Feature: Render the roster prompts
- **Description**: renders every active reviewer's prompt from `agents/*.md`.
- **Inputs**: the staged files; the roster (`state.review_lenses`/doubt reviewer); the settled-decisions ledger; the prior cycle's consolidated findings for an incremental cycle.
- **Outputs**: `docs/dev/tmp/{agent}-prompt-{id}.md` per active agent, reported in the stdout summary.
- **Behavior**: applies the substitution table of `review-work-completion/SKILL.md` step 4 and `references/agent-registry.md` through `render_prompt.py`: Bob gets `eve.md`'s "Two lenses" and "Rubric verdicts" sections (and the FIX/VERIFY/KNOWN bucket section the 00241 reviews had to add by hand), Alice/Bob/Carl/Eve get the settled-decisions section, Blake gets only `{PRD}`, `{RUBRIC}` and, when the trigger holds, the Filesystem notes block. A missing or unparseable persona file fails closed for that reviewer exactly as the preflight does today.

#### Feature: Arm the roster
- **Description**: stamps `state.review_lenses` to `running` and opens the CLI dispatch rows.
- **Inputs**: the rendered roster.
- **Outputs**: state write; dispatch row ids in the stdout summary.
- **Behavior**: the same writes step 5 makes today, in the same order. The model still issues the reviewer dispatch message itself (Agent and background Bash calls in one message); the summary carries the exact commands.

### Capability: Review close-out

Everything after the review file is saved, as one call.

#### Feature: Close the cycle
- **Description**: `autopilot review-close --review-file <f>` applies the review's decisions to state.
- **Inputs**: the saved review file and a machine-readable findings block it carries (the design doc fixes the block's exact shape).
- **Outputs**: `autonomous_decisions`/`deferred_decisions` entries, rework or sweep tasks via the existing `task-add` and `group-rework` code, `rework_task_ids`, roster close-out (`done`/`failed`), `doubts_rubric_verdicts`, and the closed dispatch rows.
- **Behavior**: refuses (non-zero, nothing written) when the review file fails `autopilot gate --review-file` checks the cycle requires. Idempotent on re-run: a second call with the same file adds no task twice. Judgment stays with the model: which findings to fix, defer or route is decided in the review file, and this verb only applies it.

### Capability: Gate reuse

#### Feature: Reuse the last verification
- **Description**: review uses `last-verification.json` when nothing but store commits follow its `sha`.
- **Inputs**: `last-verification.json`, `git log <sha>..HEAD --name-only`.
- **Outputs**: a `reused` or `stale` verdict with the counts, in `review-stage`'s summary.
- **Behavior**: `reused` only when every path changed since `sha` is under `docs/dev/project-management/` and the record's counts are non-null; otherwise `stale`, and the skill runs the gate once.

#### Feature: One-line gate summary
- **Description**: a gate run prints a final `PASS n FAIL n SKIP n EXIT c` line.
- **Inputs**: the project's gate command.
- **Outputs**: that line on stdout, and the counts written to `last-verification.json`.
- **Behavior**: no second run is ever needed to read counts. Reviewer prompts carry the gate verdict, so reviewers are told not to re-run the full gate.

## Structural Decomposition

### Repository Structure

```
skills/run-autopilot/cli/
├── review_stage.py        # Maps to: Stage the review inputs, Render the roster prompts, Arm the roster
├── review_close.py        # Maps to: Close the cycle
├── verification.py        # Maps to: Reuse the last verification, One-line gate summary
├── __main__.py            # registers review-stage, review-close
├── test_review_stage.py
├── test_review_close.py
└── test_verification.py
skills/review-work-completion/
├── SKILL.md               # steps 3-6 call the verbs
└── references/agent-registry.md
skills/run-autopilot/references/phase-review.md   # decision gate calls review-close
```

### Module: review_stage
- **Maps to capability**: Review staging
- **Responsibility**: produce every pre-launch input and the dispatch plan
- **Exports**:
  - `stage(state_path, cycle_id, since) -> dict` - writes files, returns the summary
  - `render_roster(staged, roster) -> dict[str, Path]` - one prompt per active agent

### Module: review_close
- **Maps to capability**: Review close-out
- **Responsibility**: apply a saved review's decisions to state
- **Exports**:
  - `close(review_file, state_path) -> dict` - applies and returns what changed

### Module: verification
- **Maps to capability**: Gate reuse
- **Responsibility**: decide reuse; run the gate with a summary line
- **Exports**:
  - `reuse_verdict(record, repo) -> tuple[str, dict]`
  - `run_gate(command) -> dict`

## Dependency Graph

### Foundation Layer (Phase 0)
No dependencies - built first.

- **verification**: reuse verdict and gate summary

### Core Layer (Phase 1)
- **review_stage**: Depends on [verification]
- **review_close**: Depends on [] (reads state and the review file only)

### Integration Layer (Phase 2)
- **skill prose**: Depends on [review_stage, review_close]

## Implementation Phases

### Phase 0: Foundation
**Goal**: the gate never runs twice to read one result.

**Tasks**:
- [ ] verification: `reuse_verdict` and `run_gate` (no deps) - Acceptance: `test_reuse_when_only_store_paths_changed`, `test_stale_when_code_changed`, `test_stale_when_counts_null`, `test_run_gate_prints_one_summary_line` pass.

**Exit Criteria**: `python3 -m pytest skills/run-autopilot/cli/test_verification.py` passes.

### Phase 1: Core
**Goal**: staging and close-out are single verbs.

**Tasks**:
- [ ] review_stage: stage inputs and arm the roster (depends on: Phase 0) - Acceptance: `test_stage_writes_every_input_file`, `test_stage_survives_pack_failure`, `test_stage_stamps_roster_and_opens_cli_rows` pass.
- [ ] review_stage: render every roster prompt (depends on: previous task) - Acceptance: golden tests `test_render_matches_golden_{alice,bob,blake,carl,eve}` pass against fixtures built from today's skill table, and `test_blake_prompt_carries_no_diff_or_ledger` passes.
- [ ] review_close: apply decisions, tasks and verdicts (depends on: Phase 0) - Acceptance: `test_close_adds_one_task_per_group`, `test_close_is_idempotent`, `test_close_refuses_a_gate_failing_review_file`, `test_close_records_doubt_verdicts` pass.
- [ ] `__main__.py`: register both verbs (depends on: the two review tasks) - Acceptance: `test_cli_registers_review_stage_and_close` passes.

**Exit Criteria**: the three new test files pass.

### Phase 2: Integration
**Goal**: the skill uses the verbs.

**Tasks**:
- [ ] `review-work-completion/SKILL.md` steps 3-5: replace the hand-staging and Write-tool prompt instructions with one `autopilot review-stage` call and the dispatch message built from its summary; step 6 ends with `autopilot review-close`; keep the bare-repo carve-out as the fallback path (depends on: Phase 1) - Acceptance: a prose test `test_skill_stages_via_review_stage` asserts the step 4 text names `review-stage` and no longer says "use the **Write tool** ... to create" prompt files; existing `test_reviewer_dispatch_prose.py` and `test_agent_registry.py` pass.
- [ ] `phase-review.md` decision gate and Tail sweep: task creation goes through `review-close` (depends on: Phase 1) - Acceptance: `test_phase_review_closes_via_review_close` passes; `test_review_resume_prose.py` passes.

**Exit Criteria**: `bash dev/bin/release-checks` exits 0.

## Test Strategy

### Critical Scenarios
- **Happy path**: full cycle 1 on a fixture PRD → every input file and five prompts written, roster `running`, two CLI rows open, summary JSON lists them.
- **Edge case**: incremental cycle with `--since` → prompts carry the incremental addendum and prior findings; Blake's does not.
- **Edge case**: only store commits since `last-verification.json` → `reused`, no gate run.
- **Error case**: a persona file without frontmatter → that reviewer fails closed, the others still render.
- **Error case**: `review-close` on a review file missing its findings block → non-zero exit, state unchanged.

## Risks

- **Prompt drift breaks review quality silently**: golden tests pin each rendered prompt against today's hand-assembled shape (fixtures taken from `docs/dev/tmp/*-prompt-00244c1.md`), so a change in content is a red test, not a quieter review.
- **The findings block becomes a second source of truth beside the table**: the design step must make `review-close` read the block and `gate` check that the block and the table agree.
- **The installed cache runs old prose until release**: the batch keeps using today's path until 0.8.x ships; nothing here changes a running loop.
