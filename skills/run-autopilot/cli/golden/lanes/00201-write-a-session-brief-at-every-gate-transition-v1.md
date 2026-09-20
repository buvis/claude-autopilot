---
catchup: run
design: skip
default_model: sonnet
model_tier_rationale: the brief's shape is given verbatim below, the writer is a pure render of state.json plus the contract card, and every criterion is a named test; a wrong render breaks the fixture test rather than degrading silently
---

# Write a session brief at every gate transition

Source: `dev/local/discovery/00193-cut-loop-overhead-without-thinning-review.md`
(PRD 3 of three; elicited 2026-09-07). Re-grounded 2026-09-13. Independent of
PRDs 00199 and 00200.

## Overview

### Problem Statement

Every headless session re-derives where it is: transcript `ee920ac5`
(agent-skills, 2026-09-07) spent 99 tool calls before its first dispatch,
`8f7c779f` (claude-autopilot) 100, both reading state keys one `jq` at a
time, opening four to six skill reference files, and in one case hunting
for the `autoclaude` binary for 20 calls. At ~$8 and 5 minutes per session
across ~40 sessions per batch, the orientation alone cost more than several
of the PRDs it served. The contract card (`state.contract_card`) already
carries "current step, active invariants, next gate", but only the
`compact` SessionStart source re-injects it; a fresh loop session never sees
it.

### Target Users

Every headless `/autopilot:run-autopilot` session, and the operator paying
for its first hundred tool calls.

### Success Metrics

- A resumed session's first ten tool calls touch at most
  `dev/local/autopilot/session-brief.md`, `state.json` and the PRD, checked
  by `scripts/test_brief_orientation_prose.py` on the Phase 0 text and, post
  release, by `.turn-counts.json` deltas before the first dispatch row.
- `uv run --no-project --with pytest python -m pytest -q skills/run-autopilot`
  green with the new tests below.

## Functional Decomposition

### Capability: Brief rendering
Code renders the brief from state; the model never writes it by hand.

#### Feature: `statectl write-brief`
- **Description**: A new verb `write-brief <state.json> <out.md>` renders
  `dev/local/autopilot/session-brief.md` from `state.json` and the
  `contract_card` field.
- **Inputs**: `state.json` only.
- **Outputs**: the brief, exactly this shape:

```
# Session brief (written <ISO time> at <phase> -> <next_phase>)

## Where
- repo root: <repo_root>
- batch: <batch.id> (<len(batch.completed_prds)> PRDs done)
- prd: <prd>
- phase: <phase>, next_phase: <next_phase>, cycle: <cycle>
- tasks: <tasks_completed>/<tasks_total> done; pending: <ids>; rework: <rework_task_ids>
- stall_reason: <json or none>; pause_reason: <json or none>; cap_rotations: <n>

## Contract card
<contract_card verbatim, or "(none yet)">

## Read next
<one line per file from the table below for <next_phase>, "- `<path>` - <reason>">

## Do not re-read
- state.json keys listed above (already here)
- the reference files not listed under Read next
```

- **Behavior**: the `Read next` table is a constant in the verb:
  `build` -> `references/phase-build.md` ("the gate you are entering"),
  `work/SKILL.md` ("only when tasks are pending");
  `review` -> `references/phase-review.md`, `review-work-completion/SKILL.md`;
  `done` -> `references/phase-done.md`; `paused` -> `references/recovery.md`.
  Missing or malformed state fields render as `none`; the verb exits 0 on a
  readable state file and 2 (with the reason on stderr) otherwise.

### Capability: Brief at every gate transition
The brief is as fresh as the state it describes.

#### Feature: Written with the transition
- **Description**: The session handoff procedure (run-autopilot `SKILL.md`
  § Session handoff procedure) calls `write-brief` in the same step that sets
  `next_phase`, after `set-contract-card`; `/autopilot:work`'s task-boundary
  handoff and `/autopilot:review-work-completion`'s cycle transition do the
  same where they write their cards.
- **Inputs**: the three prose sites.
- **Outputs**: one `python3 ${CLAUDE_PLUGIN_ROOT}/skills/run-autopilot/scripts/statectl.py <state.json> write-brief dev/local/autopilot/session-brief.md`
  line at each site.
- **Behavior**: a failed write is one stderr line, never a phase failure.

### Capability: Brief-first orientation
The next session opens with the brief and skips what it answers.

#### Feature: Launch prompt names the brief
- **Description**: `runner.spawn` (runner.py:219, which already receives
  `autopilot_dir`) appends ` Read dev/local/autopilot/session-brief.md
  first.` to the prompt when `autopilot_dir / "session-brief.md"` exists;
  `DEFAULT_PROMPT` (:62) is unchanged.
- **Inputs**: `autopilot_dir`, the file's existence.
- **Outputs**: the argv's last element, via `build_argv(..., prompt=...)`
  (:158); `build_argv`'s signature does not change and neither `spawn` nor
  `subprocess.Popen` gains a `cwd`.
- **Behavior**: a missing brief leaves the prompt as today.

#### Feature: Phase 0 opens with the brief
- **Description**: `references/phase-build.md` § Phase 0 and
  `references/phase-review.md` gain, as their first step: `Read
  dev/local/autopilot/session-brief.md if it exists. Its Where section
  replaces the state reads below; open only the files its Read next section
  lists.`
- **Inputs**: the brief.
- **Outputs**: fewer orientation calls.
- **Behavior**: when the brief is absent, Phase 0 reads state through
  `statectl` as it does today (phase-build.md already carries no `jq`
  reads); nothing else changes on that path.

## Structural Decomposition

### Repository Structure

```
skills/run-autopilot/
├── cli/
│   ├── statectl.py                 # Maps to: write-brief verb
│   ├── brief.py                    # Maps to: render_brief() (new, <200 lines)
│   ├── test_brief.py               # new
│   ├── runner.py                   # Maps to: launch prompt names the brief
│   └── test_runner.py              # new case
├── scripts/
│   ├── statectl.py                 # shim, unchanged
│   └── test_brief_orientation_prose.py   # new prose pin
├── SKILL.md                        # Maps to: handoff procedure writes it
└── references/phase-build.md, phase-review.md   # Maps to: brief-first Phase 0
```

### Module: brief
- **Maps to capability**: Brief rendering
- **Responsibility**: render the fixed shape from a state dict
- **Exports**: `render_brief(state: dict, now: str) -> str`,
  `READ_NEXT: dict[str, list[tuple[str, str]]]`

### Module: statectl (verb)
- **Maps to capability**: Brief rendering
- **Responsibility**: read state, write the file, exit codes
- **Exports**: verb `write-brief`

### Module: runner
- **Maps to capability**: Brief-first orientation
- **Responsibility**: the launch argv
- **Exports**: `spawn(...)` (unchanged signature; prompt suffix decided
  inside), `build_argv(...)` (unchanged)

### Module: prose sites
- **Maps to capability**: Brief at every gate transition; Brief-first
- **Responsibility**: the call sites and the Phase 0 opening
- **Exports**: none (pinned by `test_brief_orientation_prose.py`)

## Dependency Graph

### Foundation Layer (Phase 0)
No dependencies - built first.

- **brief**: the renderer.

### Core Layer (Phase 1)
- **statectl (verb)**: Depends on [brief].
- **runner**: no dependency (reads a file path).

### Integration Layer (Phase 2)
- **prose sites**: Depends on [statectl verb, runner].

## Implementation Phases

### Phase 0: Foundation
**Goal**: a pure renderer with a fixture.

**Tasks**:
- [ ] `cli/brief.py` with `render_brief` and `READ_NEXT` (no deps) -
  Acceptance: `test_brief.py::test_renders_the_documented_shape` compares
  against a checked-in expected file `cli/golden/expected/session-brief-build.md`
  (the package's existing golden convention) rendered from
  `cli/golden/state-render.json`; `::test_missing_fields_render_as_none`;
  `::test_read_next_table_covers_every_phase` (build, review, done, paused).

**Exit Criteria**: `pytest -q skills/run-autopilot/cli/test_brief.py` green.

### Phase 1: Core
**Goal**: the verb and the launch line.

**Tasks**:
- [ ] `write-brief` verb (depends on: Phase 0) - Acceptance:
  `test_statectl_new_task_verbs.py::test_write_brief_writes_the_file_and_exits_zero`,
  `::test_write_brief_unreadable_state_exits_two`.
- [ ] `spawn` appends the brief sentence when `autopilot_dir / "session-brief.md"`
  exists (no deps) - Acceptance: `test_runner.py::test_prompt_names_the_brief_when_present`
  and `::test_prompt_is_unchanged_without_a_brief`, both asserting the argv
  `build_argv` receives.

**Exit Criteria**: `pytest -q skills/run-autopilot/cli skills/run-autopilot/scripts/test_statectl_new_task_verbs.py`
green (the verb's tests live under `scripts/`, not `cli/`).

### Phase 2: Integration
**Goal**: every transition writes it; every session reads it first.

**Tasks**:
- [ ] Add the `write-brief` line to the three handoff sites (depends on:
  Phase 1) - Acceptance: `test_brief_orientation_prose.py::test_every_handoff_site_writes_the_brief`
  finds a line matching `statectl\.py \S+ write-brief` (the three sites
  spell the statectl path differently: `${CLAUDE_PLUGIN_ROOT}/...` at
  run-autopilot SKILL.md:204, bare `statectl.py` at
  `task-boundary-handoff.md:26` and `review-work-completion/SKILL.md:461`)
  in run-autopilot `SKILL.md` § Session handoff procedure,
  `work/references/task-boundary-handoff.md` and
  `review-work-completion/SKILL.md`.
- [ ] Brief-first opening in `phase-build.md` § Phase 0 and `phase-review.md`
  (depends on: Phase 1) - Acceptance:
  `::test_phase_0_opens_with_the_brief` pins the sentence in both files.
- [ ] CHANGELOG `### Added` under `**run-autopilot**` (depends on: all) -
  Acceptance: `rg -c "session-brief" CHANGELOG.md` returns 1 or more.

**Exit Criteria**: `bash dev/bin/release-checks` green.

## Test Strategy

### Critical Scenarios
- **Happy path**: build-phase state with 3/7 tasks and a contract card ->
  brief matches the fixture byte for byte.
- **Edge case**: no `contract_card`, no `batch` -> `(none yet)` and `none`,
  exit 0.
- **Edge case**: `next_phase: "paused"` -> Read next lists `recovery.md` only.
- **Error case**: state.json unreadable -> exit 2, stderr names the file, no
  brief written.

## Risks

- **A stale brief misleads a session**: the header carries the write time
  and the phase edge; Phase 0 falls back to state reads when the brief's
  `phase` disagrees with `state.json`.
- **Host hook for a `startup` match**: out of this repo
  (`~/.claude/hooks/reinject_contract_card.py`, buvis dotfiles); the launch
  prompt sentence covers loop sessions without it.
