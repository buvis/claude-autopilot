---
catchup: skip
design: skip
default_model: sonnet
model_tier_rationale: the grouping rule is given in full below (keys, merge order, cap, tie-breaks) and every branch has a named test; the classifier lifts the code task if it reads it as algorithmic risk
---

# Bound rework batches by file

Source: `docs/dev/project-management/notes/review-time-analysis-2026-09-30.md`
R4 and § Follow-ups. Grounded at v0.7.0.

## Overview

### Problem Statement

Every rework task pays the per-task pipeline's fixed cost: prompt renders,
Tess, the red-check, Ivan, the style gate, Pat and the verification record.
That came to 10-118 minutes per task across 00215-00223.

The only cap on how many tasks a review produces is the Tail sweep's "Split
rule" (`references/phase-review.md` § Tail sweep: more than 10 findings
split into 2-4 tasks). Phase 6's decision-gate `[D{cycle}]` follow-ups have
none, so the orchestrator picks the task count by judgment. 00223 cycle 1
turned 35 findings into ten `[D1]` tasks (its review file § Follow-up Tasks
Created). Tasks 4 and 5 were both prose edits to `phase-build.md`'s "Enter in
one call" section. Task 7 was a one-line `release-checks` wiring for the
tests that task 8 then strengthened. 00223's rework ran 9 hours.

### Target Users

The review gate's Phase 6 and Tail sweep in unattended batches.

### Success Metrics

- `uv run --no-project --with pytest python -m pytest -q skills/run-autopilot/cli/test_rework_groups.py skills/run-autopilot/scripts/test_rework_groups_prose.py`
  green; every existing `test_*prose*.py` under `skills/run-autopilot/` green.
- `bash dev/bin/release-checks` green.
- Post-release signal: no review cycle creates more than 4 non-CRITICAL
  `[D{cycle}]` tasks.

## Functional Decomposition

### Capability: Code decides how findings become tasks

#### Feature: `autopilot group-rework`
- **Description**: groups the findings the decision gate chose to fix into
  at most 4 non-CRITICAL tasks, by file.
- **Inputs**: `--findings <path>`, a JSON array of objects `{"severity":
  "🔴"|"🟠"|"🟡"|"⚪", "file": "<path>[:<line>]" | "general", "text": str,
  "consensus": str}`, the same fields the consolidated table carries.
- **Outputs**: one JSON array on stdout, one object per task:
  `{"name_hint": "<key>", "critical": bool, "findings": [<input objects,
  order kept>]}`. Exit 0; exit 2 with one stderr line on unreadable or
  malformed input.
- **Behavior**, in order:
  1. **CRITICAL stays separate.** Every 🔴 finding is its own group with
     `critical: true`. These are not capped (they carry the rework design,
     PRD 00194).
  2. **Key by file.** For each other finding, the key is `file` with any
     trailing `:<digits>` (and `:<digits>-<digits>`) removed; `general`
     stays `general`.
  3. **Prose in one group.** Every finding whose key ends in `.md` goes into
     a single group keyed `prose`.
  4. **One group per remaining key**, plus `general` when present.
  5. **Cap at 4.** While the non-critical group count exceeds 4: if a
     `general` group exists, merge it into the smallest other non-prose group
     (fewest findings, then lexically first key). Otherwise merge the pair of
     non-prose groups whose keys share the longest common path-directory
     prefix, breaking ties by the smallest combined finding count, then
     lexically. The merged group's key is the shared directory with a
     trailing `/`, or `mixed` when they share none. If only `prose` and one
     other group remain above the cap, merge `prose` into that group.
  6. **Order**: critical groups first, then by the highest severity in the
     group (🟠 > 🟡 > ⚪), then by finding count descending, then by key.

#### Feature: Phase 6 and the Tail sweep use it
- **Description**: the prose stops leaving the task count to judgment.
- **Inputs**: none.
- **Outputs**: prose.
- **Behavior**:
  - In `references/phase-review.md` § Phase 6, before the bullet
    "**CRITICAL D-tasks carry the rework design (PRD 00194).**", insert the
    bullet: "**Group first.** Write the findings this gate chose to fix
    (excluding `[C{cycle}]` re-queues) to `docs/dev/tmp/<prd-stem>-rework-<cycle>-findings.json`
    with the Write tool, run `autopilot group-rework --findings <that
    path>`, and create exactly one `[D{cycle}]` task per printed group, named
    from its `name_hint`. Its `### Findings (verbatim)` block holds that
    group's findings. Never split or merge groups by hand: the command caps
    non-CRITICAL tasks at 4 (measured: 00223's ten hand-made tasks took
    9 hours of rework)."
  - § Tail sweep's "**Split rule:**" sentence becomes "**Split rule:** run
    `autopilot group-rework` over the swept findings and create one task per
    group (it caps at 4, the same bound as before)."

## Structural Decomposition

### Repository Structure

```
skills/run-autopilot/cli/
├── rework_groups.py               # Maps to: autopilot group-rework (pure grouping)
├── __main__.py                    # Maps to: the group-rework subparser (thin)
└── test_rework_groups.py          # Maps to: Test Strategy
skills/run-autopilot/references/phase-review.md      # Phase 6 bullet, Tail sweep split rule
skills/run-autopilot/scripts/test_rework_groups_prose.py
dev/bin/release-checks
CHANGELOG.md
```

### Module: rework_groups
- **Maps to capability**: Code decides how findings become tasks
- **Responsibility**: the grouping rule above, pure over its input list.
- **Exports**:
  - `NON_CRITICAL_CAP = 4`.
  - `group(findings: list[dict]) -> list[dict]`.
  - `file_key(file: str) -> str`.

## Dependency Graph

### Foundation Layer (Phase 0)
No dependencies - built first.

- **rework_groups**: pure.

### Core Layer (Phase 1)
- **`group-rework` subparser**: Depends on [rework_groups].

### Integration Layer (Phase 2)
- **phase-review prose, the prose test, release-checks, CHANGELOG**:
  Depends on [`group-rework` subparser].

## Implementation Phases

### Phase 0: Foundation
**Goal**: the rule exists and every branch is pinned.

**Tasks**:
- [ ] Write `cli/rework_groups.py` (no deps) - Acceptance:
  `test_rework_groups.py::test_critical_findings_stay_separate_and_uncapped`,
  `::test_line_suffixes_share_one_file_key` (`a.py:10`, `a.py:20-30` and
  `a.py` land in one group),
  `::test_markdown_findings_share_one_prose_group`,
  `::test_general_merges_into_the_smallest_group_first`,
  `::test_closest_directories_merge_until_four_remain`,
  `::test_the_00223_cycle_one_set_yields_at_most_four_non_critical_tasks`
  (a fixture of 00223's 35 consolidated rows, file and severity transcribed
  from `docs/dev/project-management/reviews/00223-enter-the-build-gate-in-one-cli-call-v1-review-1.md`),
  `::test_order_is_critical_then_severity_then_size`,
  `::test_four_or_fewer_groups_pass_through_unmerged` green.

**Exit Criteria**: `test_rework_groups.py` green; the module under 200
lines.

### Phase 1: Core
**Goal**: callable.

**Tasks**:
- [ ] Add the `group-rework` subparser (depends on: Phase 0) - Acceptance:
  `test_rework_groups.py::test_cli_prints_one_json_array`,
  `::test_cli_malformed_input_exits_two` green; every existing `test_cli*.py`
  green.

**Exit Criteria**: the CLI tests green.

### Phase 2: Integration
**Goal**: Phase 6 and the Tail sweep use it.

**Tasks**:
- [ ] Insert the Phase 6 "Group first" bullet and rewrite the Tail sweep
  split rule exactly as above, add `test_rework_groups_prose.py` to
  `release-checks`, and add a `CHANGELOG.md` `[Unreleased]` `### Changed`
  `**run-autopilot**` line saying review rework now caps at 4 non-CRITICAL
  tasks, grouped by file (depends on: Phase 1) - Acceptance:
  `test_rework_groups_prose.py::test_phase_6_groups_before_creating_d_tasks`
  (the bullet precedes "CRITICAL D-tasks carry the rework design" and
  contains "autopilot group-rework" and "Never split or merge groups by
  hand"), `::test_tail_sweep_split_rule_uses_the_command` green; `bash
  dev/bin/release-checks` green.

**Exit Criteria**: `release-checks` green.

## Test Strategy

### Critical Scenarios
- **Happy path**: 35 findings across 9 files and 3 markdown files → no more
  than 4 non-CRITICAL groups, one of them `prose`, with every input finding
  in exactly one group.
- **Edge case**: 3 findings in 3 files → 3 groups, unmerged; a 🔴 among 20
  findings → its own group plus at most 4 others.
- **Error case**: `--findings` names a missing file or a JSON object instead
  of an array → exit 2 with one stderr line, nothing on stdout.

## Risks

- **A merged task grows too large for one implementor**: `/autopilot:work`'s
  existing task-splitting and prompt-budget rules still apply per task, and a
  split there is a measured exception rather than the default.
- **Unrelated fixes share a task**: the merge prefers files in the same
  directory, and the verbatim findings block keeps each finding's own words,
  so Pat's closure check still runs per finding.
