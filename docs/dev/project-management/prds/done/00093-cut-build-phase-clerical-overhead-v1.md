---
catchup: force
---

# Cut Build-Phase Clerical Overhead

## Overview

### Problem Statement

The autopilot build phase spends most of its wall clock on bookkeeping rather
than work. Measured on the engram batch `202608012229` (build 23:19-04:50,
5h31m, 9 tasks, 6 sessions): task 4 took 21 minutes, of which 6m32s was code
generation and 2m52s was review - **55% of the task was the orchestrator talking
to itself**. Across the 5 measured build sessions there were **21 Agent
dispatches against 558 clerical tool calls** (353 Bash, 114 Read, 50 TaskCreate,
41 TaskUpdate).

The clerical work is deterministic: rebuilding a task list that is already stored
durably, generating prompt text that is 90% fixed scaffolding, writing single
state fields one shell call at a time, and re-probing a backend that has not
changed. `rules/ai-app-design.md` says code answers when code can answer; here a
reasoning model is doing a build script's job.

It also compounds. Sessions end at `SOFT_CAP = 320_000`
(`autopilot_context_cap_hook.py`), so clerical turns shorten sessions, which
multiplies the per-session startup cost. Sessions held 1-2 tasks each.

Full evidence:
`dev/local/audit-results/2026-08-02-autopilot-build-phase-analysis.md`.

### Target Users

The solo developer running `autoclaude` unattended, who wants a PRD to finish in
fewer hours without weakening the tests-first, gated, reviewed build pipeline
that produces the code.

### Success Metrics

All headlessly checkable:

- TaskList hydration issues **at most 2 assistant turns** regardless of task
  count (today: one turn per task, measured 10 + ~7 across every build session).
- **At most 2 `statectl` invocations per completed task** (today: 68 across 9
  tasks = 7.5 per task).
- **Zero inline prompt bodies** for the test-writer, implementor and per-task
  reviewer dispatches - each is rendered from a template file by a script.
- **`work/SKILL.md` body lands at or under 500 lines** once the prompt bodies
  move out (audit 2026-08-02 finding L6: 806 lines, ~15.6K tokens per
  invocation x 141 invocations/30d; the template extraction above is the
  mechanism, this metric makes the slimming binding rather than incidental).
- The qwen preflight probe runs **at most once per batch**, plus once after any
  failed qwen dispatch (today: once per qwen-routed task).
- The contract card is written in **one call** (today: 3 attempts fighting shell
  quoting, measured 59s at the end of session 6).
- Median build wall clock per task **below the 21-minute engram baseline** on the
  next batch. Secondary - it varies with PRD size.

## Functional Decomposition

### Capability: Session Bootstrap

Restoring per-session state that the harness does not persist.

#### Feature: Batched TaskList hydration

- **Description**: Issue the hydration's `TaskCreate` and `TaskUpdate` calls as
  one parallel batch instead of one call per turn.
- **Inputs**: `state.tasks[]` from `dev/local/autopilot/state.json`.
- **Outputs**: A populated TaskList with ids aligned 1:1 to `state.tasks[].id`.
- **Behavior**: The hydration sub-step (`run-autopilot/SKILL.md` § Hydrate
  TaskList from state.tasks) keeps its current semantics - declared order,
  metadata pass-through, `TaskCreate` id alignment, status restore - and gains
  one explicit instruction: emit every `TaskCreate` in a single message, then
  every non-`pending` `TaskUpdate` in a single message. Order within the batch
  still determines id assignment. Premise: that sub-step currently issues them
  sequentially, one per turn; re-check before editing and skip if already
  batched.

### Capability: Dispatch Prompt Assembly

Producing the prompt text handed to each subagent.

#### Feature: Implementor persona

- **Description**: Give Ivan a single persona file with named placeholders, the
  way Pat and Tess already have one.
- **Inputs**: Task subject, description and acceptance criteria; the
  code-quality rules block; the abort-instruction line; the tool-gate notice;
  the Assumptions footer instruction.
- **Outputs**: `~/.claude/agents/ivan.md` carrying every fixed block, plus its
  placeholder rows in `review-work-completion/references/agent-registry.md`.
- **Behavior**: Follows the registry convention exactly - single-brace
  `{PLACEHOLDER}` names, frontmatter stripped by the consuming skill,
  placeholders documented in the registry table. Ivan is the last dispatch in
  the build pipeline still assembled inline from several sources
  (`references/code-quality-principles.md` plus three verbatim instruction
  lines scattered through `work/SKILL.md`); Pat became a persona in commit
  `840f69a72` and Tess has had `work/references/test-author-prompt.md`
  throughout. **Premise**: `~/.claude/agents/` contains no `ivan.md` and
  `work/SKILL.md` step 3 still assembles his prompt from parts; re-check both
  before building, and skip if a persona already exists.

#### Feature: Scripted placeholder substitution

- **Description**: Substitute a persona's placeholders with a script instead of
  having the model re-emit the whole assembled prompt through `Write`.
- **Inputs**: A persona path plus a mapping of placeholder name to a literal
  value, a file whose contents fill the slot, or a command whose stdout fills it.
- **Outputs**: A rendered prompt file at the caller's chosen path, and its byte
  size on stdout so the Subagent Dispatch Budget check needs no separate
  measurement call.
- **Behavior**: Strips the persona's frontmatter and fills the `{PLACEHOLDER}`
  names defined in `agent-registry.md` - it serves that existing convention and
  must not introduce a second placeholder syntax. This is where the wall clock
  actually goes: templates alone do not help while the model still generates the
  full prompt text into a file, measured at 43s, 43s and 57s for three
  consecutive implementor prompts, one of which was written, deleted and written
  again. Applies to Pat, Tess and Ivan alike (Devon's step-2.85 prompt stays inline
  by choice - opus-tier only and rare). A missing placeholder is an error
  that names it, never a prompt containing a literal `{SLOT}`.

### Capability: State Transitions

Writing task lifecycle changes to `state.json`.

#### Feature: Compound task-transition verbs

- **Description**: Add `task-start` and `task-done` verbs to `statectl.py` so one
  invocation lands every field effect of a task transition.
- **Inputs**: `task-start <id>`; `task-done <id> <attempt-json-file>` (positional, as shipped).
- **Outputs**: Updated `state.json`; exit 0 on success, non-zero with a message
  on an unknown id or malformed attempt JSON.
- **Behavior**: `task-start` sets `tasks[i].status = "in_progress"`. `task-done`
  sets `tasks[i].status = "completed"`, appends the attempt record to
  `tasks[i].attempts`, and recomputes `tasks_completed` from the task array
  rather than accepting a caller-supplied count. Both resolve `i` by matching
  `tasks[].id`, removing the `tasks[N]` index-path errors seen in the transcripts
  (`cannot descend key '3' into non-object`). Both run inside the single
  `flock`-guarded read-modify-write that `mutate()` already provides, which also
  closes the non-transactional window `run-autopilot/references/phase-review.md`
  flags at its "After /work returns" step. Premise: `statectl.py` supports only
  `get|set|append|del` today; re-check before editing.
- **Scope note**: This is a narrow down-payment on PRD 00089's schema-validated
  write boundary, not a substitute. 00089 should absorb these verbs when it runs.

#### Feature: Contract card written from a file

- **Description**: Accept the contract card body from a file path so shell
  quoting cannot fail the write.
- **Inputs**: `set-contract-card <path>` (positional, as shipped).
- **Outputs**: `state.contract_card` set to the file's contents as a JSON string.
- **Behavior**: Reads the file, sets the field through the existing locked
  mutation path. The caller writes the card with the Write tool - already the
  house rule for prose - and passes the path. Premise: the card is set today via
  `statectl set contract_card '<inline string>'`, which failed three consecutive
  times on quoting at the end of build session 6.

### Capability: Routing Probes

Deciding whether an implementor backend is usable.

#### Feature: Batch-scoped qwen preflight

- **Description**: Cache the qwen preflight verdict per batch instead of probing
  before every qwen-routed task.
- **Inputs**: `state.batch.id`, the existing four-check probe from
  `work/references/qwen-integration.md`.
- **Outputs**: A `state.qwen_preflight` slice carrying the verdict, the detail,
  and the `batch_id` it was taken under.
- **Behavior**: Applies the batch-scope idiom `work/SKILL.md` already uses for
  the codex rung probe: compare the effective batch id
  `(state.batch.id // "no-batch")` to the stored `batch_id`; mismatch or absent
  means re-probe and overwrite, match means reuse. `(guess)` the staleness
  mitigation: additionally re-probe once after any qwen dispatch that fails its
  step-5.5 gate or times out, so a backend dying mid-batch is caught rather than
  masked by a cached `healthy`. The per-task memory-pressure gate
  (`check_memory_pressure.py`, routing table row 4) stays per-task - host memory
  genuinely changes between tasks. Premise: `work/SKILL.md` runs this probe per
  task today while the codex probe is already batch-scoped; re-check both.

### Capability: Gate Applicability

Running only the gates that can produce a signal.

#### Feature: Red-check skipped for new modules

- **Description**: Record the red check as inapplicable, without running pytest
  twice, when the task creates a module that does not yet exist.
- **Inputs**: The test file's import target; the working tree.
- **Outputs**: `attempts[-1].red_check = "n/a:new_module"`.
- **Behavior**: Before the red check, resolve the module path the committed tests
  import. If it does not exist on disk, the tests can only fail with
  `ImportError`, which cannot distinguish missing behavior from a missing file -
  so record `n/a:new_module` and skip both pytest invocations. Otherwise run the
  red check unchanged. Premise: `state.json` for the engram batch records
  `red_check: "skipped:import_not_built"` on 7 of 9 build tasks while still
  paying two Bash calls each.

## Structural Decomposition

### Repository Structure

```
~/.claude/
├── agents/
│   └── ivan.md                           # Maps to: Implementor persona
├── skills/
│   ├── review-work-completion/
│   │   └── references/agent-registry.md  # Maps to: Implementor persona
│   │                                     #          (placeholder rows only)
│   ├── run-autopilot/
│   │   ├── SKILL.md                      # Maps to: Batched TaskList hydration
│   │   └── scripts/
│   │       ├── statectl.py               # DONE 9b3d575a
│   │       └── test_statectl.py          # DONE 9b3d575a
│   └── work/
│       ├── SKILL.md                      # Maps to: Scripted placeholder substitution,
│       │                                 #          Batch-scoped qwen preflight,
│       │                                 #          Red-check skipped for new modules
│       └── scripts/
│           ├── render_prompt.py          # Maps to: Scripted placeholder substitution
│           └── test_render_prompt.py     # New suite
```

### Module: statectl

- **Maps to capability**: State Transitions
- **Responsibility**: The single locked writer for `state.json` field effects.
- **Status**: **Shipped in commit `9b3d575a`** ahead of this PRD, with 10 new
  tests. Listed here because the PRD's Success Metrics still measure it.
- **Exports**:
  - `task-start <id>` - mark a task in progress
  - `task-done <id> <attempt-json-file>` - status, attempt append and count
    recompute in one locked write
  - `set-contract-card <file>` - set the card without shell quoting

### Module: render_prompt

- **Maps to capability**: Dispatch Prompt Assembly
- **Responsibility**: Strip a persona's frontmatter, substitute its
  `{PLACEHOLDER}` names, write the result, report its size.
- **Exports**:
  - `render_prompt.py <persona> --out <path> [--set|--set-file|--set-cmd k=v]`

### Module: ivan persona

- **Maps to capability**: Dispatch Prompt Assembly
- **Responsibility**: Hold every fixed block of the implementor prompt, so the
  last inline-assembled dispatch in the build pipeline stops being rebuilt from
  parts on each task.
- **Exports**: `~/.claude/agents/ivan.md`, with its placeholder rows added to
  `review-work-completion/references/agent-registry.md`.

### Module: work skill prose

- **Maps to capability**: Dispatch Prompt Assembly, Routing Probes, Gate
  Applicability
- **Responsibility**: The build-phase procedure the orchestrator follows.
- **Exports**: steps 2.7, 3, 5.5, 5.7 rewritten to call the script and the cached
  probe.

### Module: run-autopilot skill prose

- **Maps to capability**: Session Bootstrap
- **Responsibility**: The shared hydration sub-step.
- **Exports**: § Hydrate TaskList from state.tasks, batched.

## Dependency Graph

### Foundation Layer (Phase 0)

No dependencies - built first.

- **statectl**: provides the compound verbs every later state write uses.
- **render_prompt**: provides substitution; independent of statectl.
- **prompt templates**: content only; pairs with render_prompt.

### Core Layer (Phase 1)

- **work skill prose**: Depends on [render_prompt, prompt templates, statectl]
- **run-autopilot skill prose**: Depends on [] - the hydration batching is a
  prose-only change with no script dependency.

### Integration Layer (Phase 2)

- **verification**: Depends on [work skill prose, run-autopilot skill prose] -
  proves the call counts actually dropped in a real build.

## Implementation Phases

**Phase −1 runs before Phase 0 and may close this PRD instead of building it.** It is specified
in "Premise refresh required before this leaves hold/" near the end of this file — re-measure one
real build batch against the statectl task verbs, rewrite the Problem Statement's numbers, and
re-derive the Success Metrics. If the overhead has already fallen, say so and close the PRD.
Unparked to `backlog/` on 2026-08-18 on that condition; if no build batch with statectl telemetry
has run yet, record that and park again rather than measuring a batch that does not exist.
**Unparked again 2026-08-23: a qualifying batch now exists.** Batch `202608180438` drained 11
PRDs / 62 tasks (00123-00133) entirely under statectl (2026-08-18 to 2026-08-21); the earlier
premise-park predates those PRDs running. Measure that batch in Phase −1.

Tasks marked `[x]` **DONE** are already shipped - plan-tasks must not plan them; they
stay listed so the Success Metrics keep their measurement surface.

### Phase 0: Foundation

**Goal**: The scripts and templates the prose will call exist and are tested.

**Tasks**:

- [x] **DONE (commit `9b3d575a`, ahead of this PRD).** Added `task-start`, `task-done`
      and `set-contract-card` to `statectl.py`, id-matched and inside the existing lock;
      10 new tests cover a successful `task-done` (status, appended attempt, recomputed
      count), id-not-position resolution, an unknown id, malformed and missing attempt
      files, and a contract card containing quotes, newlines and `$`. 26 statectl tests
      green; the 101 `cli/` tests, 48 fablectl, 23 cap-rotation, 6 golden-contract and
      6 halt-guarantee tests all still pass against the changed `mutate` signature.
- [ ] Build `render_prompt.py` with `--set`, `--set-file` and `--set-cmd`, stripping
      persona frontmatter and printing the rendered byte size (no deps) - Acceptance:
      `test_render_prompt.py` covers each source kind, an unfilled placeholder (non-zero
      exit naming it), a substituted value that itself contains a `{NAME}` sequence, and
      a persona whose frontmatter fails to parse; tests green.
- [ ] Write `~/.claude/agents/ivan.md` from the blocks `work/SKILL.md` step 3 assembles
      inline, and add its rows to `agent-registry.md` (no deps) - Acceptance: the persona
      carries the code-quality rules, the abort-instruction line, the tool-gate notice and
      the Assumptions footer verbatim; every placeholder it uses appears in the registry
      table; rendering it with representative values reproduces the fixed sections of
      today's prompt. Re-check the premise: skip if `ivan.md` already exists.

**Exit Criteria**: `test_render_prompt.py` green; `ivan.md` exists with registry rows;
rendering each of Pat, Tess and Ivan produces prompts whose fixed sections match today's.

### Phase 1: Core

**Goal**: The build phase calls the new machinery instead of doing the work inline.

**Tasks**:

- [ ] Rewrite `work/SKILL.md` steps 2.7, 3 and 5.7 to render prompts via
      `render_prompt.py` (depends on: Phase 0) - Acceptance: no step instructs the
      orchestrator to emit a prompt body itself; each dispatch step names its persona and
      its placeholder mapping; the Subagent Dispatch Budget check reads the script's
      reported size instead of a separate measurement call.
- [x] **DONE (commit `9b3d575a`).** Replaced the per-task state writes in `work/SKILL.md`
      step 6 with `task-start` / `task-done`, updated § Dashboard State Sync, and split
      `work/references/attempt-logging.md` so the abort and escalate-away paths keep the
      generic `append` (the task does not become `completed` there, so status and count
      must not move). The contract card now loads from a file in `work/SKILL.md`,
      `run-autopilot/SKILL.md` § Contract card and `review-work-completion/SKILL.md`.
- [ ] Batch-scope the qwen preflight into `state.qwen_preflight` with re-probe on
      dispatch failure (no deps) - Acceptance: the probe section carries the same batch-id
      compare/reuse wording as the codex rung probe; a documented re-probe trigger exists
      for a failed qwen dispatch.
- [ ] Make the red check skip new-module tasks in one resolution step (no deps) -
      Acceptance: the step resolves the import target before running pytest and records
      `n/a:new_module` without invoking pytest when it is absent.
- [x] **DONE (commit `9b3d575a`).** Batched the hydration calls in
      `run-autopilot/SKILL.md`: one message for all `TaskCreate`, one for all status
      `TaskUpdate`, with the declared-order and id-alignment guarantees restated.

**Exit Criteria**: `python3 ~/.claude/skills/run-autopilot/scripts/test_golden_contracts.py`
and the run-autopilot suite pass; no build-phase step in either skill authors a prompt
body or writes a task field individually.

### Phase 2: Integration

**Goal**: Prove the counts dropped against the recorded baseline.

**Tasks**:

- [ ] Add a `check_build_overhead.py` script that reads a session transcript and reports
      `TaskCreate` turns, `statectl` calls per completed task, and prompt-authoring
      `Write` calls (depends on: Phase 1) - Acceptance: run against the recorded engram
      baseline session `4bddd2d6-0c28-4a2d-aa41-bbf06873027d` (transcript:
      `~/.claude/projects/-Users-bob-git-src-github-com-buvis-engram/4bddd2d6-0c28-4a2d-aa41-bbf06873027d.jsonl`)
      it reports 10 TaskCreate turns and >= 7 statectl calls per task; its own unit tests pass.

**Exit Criteria**: The script reproduces the documented baseline numbers, so the next
real build can be compared against them without re-deriving the method.

## Test Strategy

### Critical Scenarios

- **Happy path**: `task-done 4 a.json` on a 10-task state → task 4 is
  `completed`, its attempt is appended, `tasks_completed` reflects the array, and the
  file is valid JSON with a `.bak` written.
- **Happy path**: rendering the reviewer template with a diff supplied by `--set-cmd`
  produces a prompt containing both the diff and the verbatim simplification mandate.
- **Edge case**: a contract card containing `'`, `"`, `$(`, and a newline round-trips
  through `set-contract-card --file` unchanged.
- **Edge case**: `task-done` on a state whose `tasks[]` ids are not array positions
  resolves by id, not index.
- **Edge case**: a template placeholder left unfilled exits non-zero and names it,
  rather than emitting a prompt containing a literal `{SLOT}`.
- **Error case**: `task-done` with malformed attempt JSON exits non-zero and leaves
  `state.json` byte-identical.
- **Error case**: a batch id absent from `state.batch` degrades to `"no-batch"` and
  re-probes rather than raising.

## Risks

- **The compound verbs collide with PRD 00089**: 00089 (parked in `hold/`) owns the
  schema-validated write boundary and would re-implement this surface. *Mitigation*: keep
  the verbs deliberately narrow - two transitions and one field setter, no schema layer -
  and record in 00089 that it absorbs them.
- **A cached qwen preflight masks a backend that died mid-batch**: the probe exists to
  stop a sick backend hanging a dispatch. *Mitigation*: the re-probe-on-failure trigger,
  plus the step-5.5 gate and the capability breaker, which already catch a qwen dispatch
  that produces bad work.
- **Templating strips context the prompts were carrying implicitly**: an inline prompt can
  absorb task-specific nuance a persona cannot. *Mitigation*: Phase 0 requires the
  rendered output's fixed sections to match today's text, and the per-task review plus the
  step-5.5 gate would surface a weaker implementor prompt as failing tasks.
- **This PRD went partly stale within a day of being written**: `840f69a72` turned Pat
  into a registry persona and `9b3d575a` shipped the state and hydration work, both after
  the analysis was measured. *Mitigation*: every remaining task carries a premise re-check
  and a skip-if-already-done instruction, and the shipped items are marked rather than
  deleted so the Success Metrics still have something to measure. Re-read the registry
  conventions before building - `agent-registry.md` is the authority on placeholder
  syntax, not this PRD.
- **Batched `TaskCreate` breaks id alignment**: ids are assigned sequentially and must
  match `state.tasks[].id`. *Mitigation*: the sub-step keeps its declared-order rule, and
  the acceptance criterion re-states the alignment guarantee; a mismatch is visible
  immediately because `/work` dispatches by id.
- **Measured on one PRD only**: every number here comes from the engram batch; no other
  repo has a `loop-metrics.jsonl`. *Mitigation*: Phase 2 ships the measurement script so
  the second data point is cheap.

## Premise refresh required before this leaves hold/ — 2026-08-17

**Do not build this as written.** Two of its premises rotted after it was parked, and the
operator's decision on 2026-08-17 was to keep it parked until they are re-measured:

1. **The baseline counts a retired mechanism.** The Problem Statement's headline figures — 50
   `TaskCreate` and 41 `TaskUpdate` calls among 558 clerical tool calls — count tools that PRD
   00120 removed. The clerical mix after the statectl migration is unknown, so the 55%
   orchestrator-overhead claim is unverified at HEAD, not wrong-but-close.
2. **Its measurement tool is being retired.** `check_build_overhead.py` derives
   `completed_tasks` from `TaskUpdate` calls and now reports a perfect `0.00` off a dead
   counter (agoge finding 27, accepted for retirement in the 2026-08-17 walkthrough). Whatever
   re-measures this has to count `statectl task-add` / `task-set-status … completed` instead.

**Phase −1, to run before anything else:** re-measure one real build batch against the
statectl task verbs, write the new numbers into the Problem Statement, and re-derive the
Success Metrics from them. If the overhead has already fallen — plausible, since 00120 replaced
per-field shell calls with statectl verbs and 00089 shipped the validated write boundary this
PRD's compound verbs were going to collide with — then say so and close the PRD instead of
building it.

Also stale as a result: the "Batched `TaskCreate` breaks id alignment" risk below describes a
tool that no longer exists.

## Carried in from PRD 00120's review — 2026-08-17

Two deferred items from PRD 00120 land here because this PRD owns the overhead
metric they concern. Source:
`dev/local/autopilot/deferred/202608162223-deferred.json`.

- **This PRD's own overhead metric now reads a perfect score from a dead
  counter.** `work/scripts/check_build_overhead.py:60` derives `completed_tasks`
  solely from `TaskUpdate` calls, which can no longer occur — PRD 00120 retired the
  task tools. The script does not fail; it reports 0 completed tasks and a
  statectl-calls-per-task ratio of `0.00`, which reads as the ideal outcome. Retire
  the counter or re-baseline it on `statectl task-set-status` calls before any
  number it prints is quoted again. Found by Alice, Bob and Blake (3/4).
- **PRD 00120's Phase-1 acceptance bullet and its Success Metric set different
  bars for the same sweep**, and the discrepancy is this script's fault: the literal
  bullet (`rg` sweep over `skills/work/` = 0 hits) returns 60+ hits, all inside
  `check_build_overhead.py` and its test, while the Success Metric (instruction text
  = 0) is satisfied. Correct 00120's wording when the counter is retired here.
  Found by Blake (blind lens).

Also stale in this PRD as a result: the "Batched `TaskCreate` breaks id alignment"
risk above describes a tool that no longer exists. Re-state it against the statectl
task verbs when this PRD is next picked up.
