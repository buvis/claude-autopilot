---
catchup: skip
design: skip
default_model: opus
model_tier_rationale: Phase 0 recovers the writer's field vocabulary from the batch transcripts, a judgment task with no exact expression to transcribe
---

# Make batch report decisions and implementor mix render

## Overview

### Problem Statement
Four of the eight PRD sections rendered in the week to 2026-09-05 (agent-skills 00019, 00024, 00026 in batch 202609040601 and 00015 in 202609050909) show an Autonomous Decisions table whose rows carry only the cycle number (00026 also carries severities), while 00033, 00161 and 00171 rendered full rows. The 00015 decision audit log (`dev/local/reviews/00015-corrupt-queue-reads-as-drained-v1-audit.md`) rendered 13 headers with no body at all. Every agent-skills section says `no implementor data` although `ledger/attempts.jsonl` holds 93 rows for that repo and 13 for this one, and two sections say `Cycles: ?`. Three mechanisms: `statectl append` accepts any dict for `autonomous_decisions` (`cli/schema.py:58` types the array, not its entries), so an entry that lacks the keys `render_report._autonomous_row` reads (`issue|question`, `severity`, `action`, `reason|resolution`) draws a blank row because `cycle` alone satisfies `is_autonomous_row`; `_implementor_mix` (`render_report.py:382`) reads only `state.tasks[].attempts[]`, which is empty at the time the section renders, and never looks at the ledger `complete-prd` just wrote; and `Cycles:` reads only `state.cycle`. The review phase docs (`references/phase-review.md:118,141`) say "record it in autonomous_decisions" without naming the keys.

### Target Users
The operator reading `dev/local/autopilot/reports/*-report.md` and `*-audit.md` at batch end; `audit-qwen` and the routing tuner, which read the implementor mix.

### Success Metrics
- `uv run --no-project --with pytest python -m pytest -q skills/run-autopilot/cli` passes with the new tests named below.
- `python3 skills/run-autopilot/cli/statectl.py <state> append autonomous_decisions '{"cycle": 1}'` exits 1 with `rejected:` naming the missing key.
- A section rendered from a state whose `tasks` is empty but whose ledger holds attempts for the PRD shows the Implementor table, not `no implementor data`.

## Functional Decomposition

### Capability: Decision entries validated at the write boundary
A decision that the report cannot render is refused when it is appended, with the missing key named, instead of drawing a blank row at batch end.

#### Feature: Entry contract
- **Description**: one definition of an `autonomous_decisions` entry, in `references/state-schema.md` § autonomous_decisions and enforced by `cli/schema.py`.
- **Inputs**: the appended value.
- **Outputs**: accepted, or `SchemaError("autonomous_decisions entry missing <key>")`.
- **Behavior**: an entry is a dict with `cycle` (int), one non-empty string among `issue` or `question`, `severity` in `{"critical", "high", "medium", "low", "n/a"}`, one non-empty string among `action` or `disposition`, and one non-empty string among `reason` or `resolution`. An entry whose `type` is `assumed-ambiguity` instead needs non-empty `question` and `assumption`. Extra keys (`file`, `consensus`, `research`, `type`) stay allowed. `validate_changed` applies the contract to entries that were added; existing entries in a state being read are never re-validated, so an old state loads.

#### Feature: Writer vocabulary recovered
- **Description**: the Phase 0 investigation that finds what the review phase actually appended this week.
- **Inputs**: the batch 202609040601 and 202609050909 loop transcripts under `~/.claude/projects/-Users-bob-git-src-github-com-buvis-agent-skills/` (session ids in `dev/local/autopilot/.turn-counts.json` of that repo) and the `statectl.py ... append autonomous_decisions` tool calls in them.
- **Outputs**: `dev/local/tmp/00183-decision-shapes.md` listing each distinct key set observed, with one verbatim example per set.
- **Behavior**: the observed key sets become the alias table below and the fixtures for the tests. If the transcripts show entries appended with the documented keys, the investigation records that and the alias table stays empty.

#### Feature: Renderer aliases
- **Description**: `_autonomous_row` reads `disposition` as `action` (the vocabulary the review ledger already uses: `dev/local/reviews/00015-...-ledger.json` entries carry `cycle`, `disposition`, `severity`, `issue`, `file`, `reason`) plus any alias the investigation found, and `is_autonomous_row` requires issue or question text, so a cycle-only entry no longer draws a row.
- **Inputs**: one entry.
- **Outputs**: the five cells, or no row.
- **Behavior**: `statectl.complete-prd` counts with the same predicate, so the count and the table keep agreeing (state-schema.md § batch.completed_prds).

### Capability: Implementor mix and cycles from durable sources
The report section reads the ledger the close step just wrote, and the cycle count from the batch record when the state no longer carries it.

#### Feature: Ledger-backed implementor mix
- **Description**: `_implementor_mix(state, ledger_rows)` where `ledger_rows` are the `attempt` objects from `dev/local/autopilot/ledger/attempts.jsonl` whose `prd` and `batch_id` match the section.
- **Inputs**: state, ledger rows.
- **Outputs**: the Implementor table from the union of state attempts and ledger attempts, deduplicated by (`task_id`, `attempt.attempt`); `no implementor data` only when both are empty.
- **Behavior**: `prd_section` loads the rows; a missing or unreadable ledger is an empty list and one stderr line, never a failed render.

#### Feature: Cycles fallback
- **Description**: `- Cycles:` reads `state.cycle`, then the `batch.completed_prds` record for the section's filename, then `?`.
- **Inputs**: state.
- **Outputs**: an int or `?`.
- **Behavior**: unchanged when `state.cycle` is present.

## Structural Decomposition

### Repository Structure

```
skills/run-autopilot/cli/
├── schema.py                                # Maps to: Entry contract
├── render_report.py                         # Maps to: Renderer aliases, Ledger-backed implementor mix, Cycles fallback
├── statectl.py                              # Maps to: complete-prd count parity (predicate reuse)
├── test_schema.py                           # Maps to: contract tests
├── test_render_autonomous_blank_rows.py     # Maps to: alias and cycle-only tests
├── test_render.py                           # Maps to: implementor mix and cycles tests
└── golden/expected/report-section.md        # Maps to: layout golden (unchanged unless layout moves)
skills/run-autopilot/references/
├── state-schema.md                          # Maps to: the single entry definition
├── batch-report-format.md                   # Maps to: implementor mix source note
└── phase-review.md                          # Maps to: append instruction carrying the exact JSON shape
skills/run-autopilot/scripts/
└── test_review_prompt_contracts.py          # Maps to: prose pin on the append instruction
dev/local/tmp/00183-decision-shapes.md       # Maps to: Writer vocabulary recovered (scratch, not shipped)
CHANGELOG.md
```

### Module: schema
- **Maps to capability**: Decision entries validated at the write boundary
- **Responsibility**: refuse an entry the report cannot render, naming the missing key
- **Exports**:
  - `validate_changed(before, after)` - now checks added `autonomous_decisions` entries
  - `DECISION_SEVERITIES` - the accepted severity set

### Module: render_report
- **Maps to capability**: Implementor mix and cycles from durable sources
- **Responsibility**: render a PRD section from state plus the attempt ledger
- **Exports**:
  - `_autonomous_row(d)`, `is_autonomous_row(entry)` - alias-aware
  - `_implementor_mix(state, ledger_rows)` - ledger-backed
  - `prd_section(...)` - loads the ledger rows for its PRD

## Dependency Graph

### Foundation Layer (Phase 0)
No dependencies - built first.

- **investigation**: the observed key sets (scratch file).
- **schema**: the entry contract.

### Core Layer (Phase 1)
- **render_report**: Depends on [investigation] for the alias table; [schema] for the predicate the count shares.

### Integration Layer (Phase 2)
- **docs and prose pins**: Depends on [schema, render_report].

## Implementation Phases

### Phase 0: Foundation
**Goal**: know what was written; refuse what cannot render.

**Tasks**:
- [ ] Recover the decision shapes appended in batches 202609040601 and 202609050909 into `dev/local/tmp/00183-decision-shapes.md` (no deps) - Acceptance: the file exists and lists at least one key set with a verbatim example, or states that only documented keys were observed; `rg -c '^## ' dev/local/tmp/00183-decision-shapes.md` is at least 1.
- [ ] Add the entry contract to `cli/schema.py` and document it in `references/state-schema.md` (no deps) - Acceptance: `test_appended_decision_missing_issue_is_rejected`, `test_appended_decision_with_disposition_is_accepted`, `test_assumed_ambiguity_entry_needs_question_and_assumption`, and `test_existing_entries_are_not_revalidated_on_load` pass in `cli/test_schema.py`; `python3 skills/run-autopilot/cli/statectl.py <tmp state> append autonomous_decisions '{"cycle": 1}'` exits 1 with `rejected: autonomous_decisions entry missing issue`.

**Exit Criteria**: `python -m pytest -q skills/run-autopilot/cli/test_schema.py` passes.

### Phase 1: Core
**Goal**: the section renders what the ledgers hold.

**Tasks**:
- [ ] Add the alias table and the text requirement to `_autonomous_row` and `is_autonomous_row` (depends on: Phase 0) - Acceptance: premise `rg -c 'def test_' skills/run-autopilot/cli/test_render_autonomous_blank_rows.py` is recorded before the edit and the count after is greater; `test_cycle_only_entry_draws_no_row` and `test_disposition_renders_as_action` pass; `test_complete_prd_count_matches_rendered_rows` in `scripts/test_statectl_complete_prd.py` passes.
- [ ] Make `_implementor_mix` ledger-backed and have `prd_section` load `ledger/attempts.jsonl` rows for its PRD (depends on: Phase 0) - Acceptance: `test_implementor_mix_reads_ledger_when_state_tasks_empty` (state with `tasks: []`, ledger with two `claude` and one `qwen` attempt for the PRD → table rows `claude 2`, `qwen 1`), `test_implementor_mix_dedups_state_and_ledger` (same attempt in both → counted once), and `test_missing_ledger_renders_no_implementor_data` pass in `cli/test_render.py`; `cli/golden/expected/report-section.md` is byte-identical before and after (`git diff --exit-code` on it).
- [ ] Add the `Cycles:` fallback (depends on: Phase 0) - Acceptance: `test_cycles_falls_back_to_completed_prd_record` passes.

**Exit Criteria**: `python -m pytest -q skills/run-autopilot/cli` passes.

### Phase 2: Integration
**Goal**: the writer instruction carries the shape the schema enforces.

**Tasks**:
- [ ] Give the append instruction in `references/phase-review.md` (lines 118 and 141) the exact JSON shape `{"cycle": <state.cycle>, "issue": "...", "severity": "...", "action": "...", "reason": "..."}` and add `test_phase_review_append_names_the_decision_keys` to `scripts/test_review_prompt_contracts.py` (depends on: Phase 1) - Acceptance: the new test passes and `rg -c '"issue"' skills/run-autopilot/references/phase-review.md` is at least 2.
- [ ] Note the ledger source in `references/batch-report-format.md` § Implementor Mix and add a `### Fixed` CHANGELOG entry under `[Unreleased]` (depends on: Phase 1) - Acceptance: `rg -n 'attempts.jsonl' skills/run-autopilot/references/batch-report-format.md` returns one hit; `rg -n 'implementor mix' CHANGELOG.md` returns one hit under `[Unreleased]`.

**Exit Criteria**: `bash dev/bin/release-checks` passes.

## Test Strategy

### Critical Scenarios
- **Happy path**: a documented entry appended → accepted, rendered with all five cells; the count in `batch.completed_prds` equals the rendered rows.
- **Edge case**: an entry using `disposition` → accepted and rendered under Action; a `type: assumed-ambiguity` entry → lands in Assumptions Made, not the decisions table.
- **Error case**: `{"cycle": 1}` appended → exit 1 naming `issue`; the state file is untouched (byte-identical before and after).

## Risks
- **Rejecting appends can stall a review session** that keeps retrying a wrong shape: the error names the key and the phase-review instruction now carries the shape, so the retry is one call, not a loop. The 45-minute wall-clock cap remains the backstop.
- **Old states with stub entries** stay as they are; only new appends are validated, so a resumed batch does not fail to load.
- **Golden drift**: the section layout does not change; the golden file is pinned byte-identical in Phase 1.
