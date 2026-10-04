---
catchup: skip
design: skip
default_model: sonnet
model_tier_rationale: transcription only - exact regex and exact prose replacements given, additive tests that fail at base
---

# Finish the rework-grouping fixes from 00241

## Problem

PRD 00241 capped out with two HIGH findings left open, minted as hold stubs
00246 (ledger key `d6ef37d5f2ff`) and 00247 (ledger key `92b585072b81`), batch
`202610031511`. Both were re-checked against HEAD on 2026-10-04 and are still
real:

- `skills/run-autopilot/references/phase-review.md` § Tail sweep says "one
  normal `/autopilot:work` task fixes it" (line 191) and "Build ONE
  `[D{cycle}]` task" (line 195), while the Split rule two lines below (line
  197) creates one task per `group-rework` group. A reader who stops at step 2
  builds one task.
- `skills/run-autopilot/cli/rework_groups.py:26` `_LINE_SUFFIX` strips `:N`,
  `:N-M`, ` (lines N-M)` and `#LN`, but not ` (line 3)`, ` (lines 18-22, 423)`
  or `#L12-L20`, which the canonical
  `consolidate_findings._TRAILING_LINENO_RE` strips. Each such citation
  becomes its own group key and burns a cap slot.

## Solution

Copy the canonical regex into `rework_groups.py` and make the Tail sweep prose
agree with its own Split rule. Both stubs leave `prds/hold/` in the same
change.

## Requirements

### Must have
- `file_key` strips every citation shape `_TRAILING_LINENO_RE` strips.
- Tail sweep prose names one task per group everywhere.
- Hold stubs 00246 and 00247 are removed from `docs/dev/project-management/prds/hold/`.

### Nice to have
- None.

## Implementation

### Module: rework_groups
- **Location**: `skills/run-autopilot/cli/rework_groups.py`
- **Responsibility**: group rework findings by file
- **Exports**: `file_key()` (unchanged signature)

### Module: phase-review prose
- **Location**: `skills/run-autopilot/references/phase-review.md`
- **Responsibility**: Tail sweep procedure text
- **Exports**: none

### Dependencies
- rework_groups: No dependencies (foundation)
- phase-review prose: No dependencies (foundation)

## Tasks

### Phase 0: Foundation
- [ ] rework_groups: replace line 26 with exactly
  `_LINE_SUFFIX = re.compile(r"(?:\s*\(lines?\s+\d[\d,\s-]*\)|:\d+(?:-\d+)?|#L\d+(?:-L?\d+)?)$")`
  and update the `file_key` docstring to list the added shapes; add tests
  `test_file_key_strips_singular_line_citation` (`"a/b.py (line 3)"` ->
  `"a/b.py"`), `test_file_key_strips_comma_line_list`
  (`"a/b.py (lines 18-22, 423)"` -> `"a/b.py"`) and
  `test_file_key_strips_anchor_range` (`"a/b.py#L12-L20"` -> `"a/b.py"`) to
  `skills/run-autopilot/cli/test_rework_groups.py` - Acceptance:
  `python3 -m pytest skills/run-autopilot/cli/test_rework_groups.py` passes,
  and the three new tests fail against the old regex.
- [ ] phase-review prose: in `skills/run-autopilot/references/phase-review.md`
  § Tail sweep, replace "one normal `/autopilot:work` task fixes it" with
  "the `/autopilot:work` tasks the Split rule below creates fix it, one per
  group", and replace "Build ONE `[D{cycle}]` task, named" with "Build one
  `[D{cycle}]` task per `group-rework` group (Split rule below), each named";
  add `test_tail_sweep_prose_never_says_one_task` to
  `skills/run-autopilot/scripts/test_review_resume_prose.py` asserting the
  Tail sweep section contains neither "Build ONE" nor "one normal" - Acceptance:
  `python3 -m pytest skills/run-autopilot/scripts/test_review_resume_prose.py` passes.

### Phase 1: Core
- [ ] triage: delete `docs/dev/project-management/prds/hold/00246-triage-tail-sweep-step-2-still-reads-build-one-v1.md`
  and `docs/dev/project-management/prds/hold/00247-triage-line-suffix-still-misses-three-citation-v1.md`
  (depends on: Phase 0). Premise: both files still exist and still name ledger
  keys `d6ef37d5f2ff` and `92b585072b81`; re-check at execution, and if either
  is gone or names another key, skip that file and report - Acceptance:
  `test ! -e` on both paths.

## Success Criteria

- `test_file_key_strips_singular_line_citation`,
  `test_file_key_strips_comma_line_list`, `test_file_key_strips_anchor_range`
  and `test_tail_sweep_prose_never_says_one_task` pass.
- `bash dev/bin/release-checks` exits 0.
