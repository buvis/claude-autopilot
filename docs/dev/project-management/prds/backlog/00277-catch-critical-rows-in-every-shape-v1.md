---
design: run
default_model: opus
model_tier_rationale: widens the findings parser's trust boundary; a false negative ships a CRITICAL untasked, a false positive costs a review cycle on every real file that trips it
---

# A CRITICAL finding can leave a review with no task

## Overview

### Problem Statement

The agoge run of 2026-10-10 (`docs/dev/project-management/audit-results/agoge-2026-10-10.md`,
packets 4, 5, 17, 18; decisions in its `## Minutes`) shows that PRD 00269's
backstop still lets a 🔴 row pass the decision gate unread:

- **4 (HIGH):** `gate._unread_token` flags an unread line only when it carries the exact
  `[m/n]` token or starts with `|`. A 🔴 row as a bullet with no token, `[2 / 2]`,
  `［2/2］`, `(2/2)`, a blockquote table, a pipe-less table or an HTML `<table>` is
  ignored: `review-close --batch-id decision-gate` applies with `tasks_created: []`.
- **5 (HIGH):** `gate._unfenced` strips each line before matching a fence, so a
  tab- or 4-space-indented ```` ``` ```` opens a fake fence (CommonMark reads it as
  code text) and blanks the rows after it.
- **17 (LOW):** a real findings table inside a closed ```` ``` ```` or `~~~` fence is
  skipped by design and passes untasked.
- **18 (LOW):** `__main__._boundary_refusal_line` prints the raw `prd`/`design_doc`
  value, so `\n` and `\x1b[` in it forge extra log lines.

If unchanged: a model that writes its CRITICAL as a plain bullet, a natural shape,
ships it with no task, silently.

### Target Users

Review sessions running `gate --findings` and `review-close`, and the operator
who trusts that every 🔴 row became a task.

### Success Metrics

- Each of the 8 shapes from packet 4, and both indented-fence shapes from packet 5,
  makes `review-close` refuse (exit 2) instead of applying with no task.
- The 95 real past reviews walter replayed still pass `gate` exit for exit (a
  measured false-refusal count of 0, or each new refusal listed and accepted).
- A refusal line is always one line.

## Functional Decomposition

### Capability: The backstop reads by content

#### Feature: Severity-content flag (packet 4)
- **Description**: `_unread_token` also flags any unconsumed line that carries a severity emoji (🔴🟠🟡⚪) or a severity word (`CRITICAL`, `HIGH`, `MEDIUM`, `LOW`) next to a pipe, and any consensus-marker variant: spaced (`[2 / 2]`), full-width (`［2/2］`) or parenthesized (`(2/2)`).
- **Behavior**: the check runs on the unfenced text, after the existing token and pipe-row checks; the refusal message names the line number and text as today.

#### Feature: CommonMark fences (packet 5)
- **Description**: `_unfenced` matches openers and closers on the raw line with at most 3 leading spaces (`^ {0,3}(`{3,}|~{3,})`), never on the stripped line.
- **Constraint**: PRD 00269's indented-fence fix (`4ed526e`) and its tests must stay green; if one of them used 4+ spaces, report it rather than editing the test.

#### Feature: No real table in a fence (packet 17)
- **Description**: a closed fence whose body contains the findings table header (`Ref | ... | Severity | Issue | File`) is malformed, and the gate refuses it. Fenced example rows without that header stay allowed.
- **Prose**: `skills/review-work-completion/references/output-formats.md:101` adds that the header row itself must never be fenced.

### Capability: One-line refusals

#### Feature: repr() values (packet 18)
- **Description**: `_boundary_refusal_line` prints `raw` and `resolved` through `repr()`.

## Structural Decomposition

### Repository Structure

```
CHANGELOG.md                                         # [Unreleased] Fixed lines
skills/run-autopilot/cli/
├── gate.py                                          # _unread_token, _unfenced, fenced-header check
├── __main__.py                                      # _boundary_refusal_line
├── test_gate_findings_shapes.py                     # tests: 8 shapes, indented fences, fenced header
├── test_gate_findings_real_fixtures.py              # replay guard over real reviews
└── test_review_stage_paths.py                       # test: one-line refusal
skills/review-work-completion/references/
└── output-formats.md                                # line 101: never fence the header
```

### Module: gate
- **Responsibility**: read every findings row or refuse the file.
- **Exports**: unchanged.

## Dependency Graph

### Foundation Layer (Phase 0)
- **gate**: fences, then content flag, then fenced header.
- **cli refusal line**: independent.

### Integration Layer (Phase 1)
- **prose, CHANGELOG**: depend on [gate].

## Implementation Phases

### Phase 0: Foundation
**Tasks**:
- [ ] gate: CommonMark fence rule in `_unfenced` (no deps) - Acceptance: in `test_gate_findings_shapes.py`, `indented_fence_does_not_blank_rows` (parametrized: tab, 4 spaces) passes and fails at base; the `4ed526e` tests still pass.
- [ ] gate: severity-content and marker-variant flag in `_unread_token` (depends on: fence rule) - Acceptance: `critical_row_in_unparsed_shape_is_malformed`, parametrized over the 8 shapes of packet 4, passes and fails at base; `test_gate_findings_real_fixtures.py` passes with every real fixture, and any fixture that now refuses is listed in the task report rather than edited.
- [ ] gate: a fenced block with the findings table header is malformed (depends on: fence rule) - Acceptance: `fenced_findings_table_is_malformed` (backtick and tilde) passes and fails at base; `fenced_example_rows_without_header_still_pass` passes.
- [ ] cli: `repr()` in `_boundary_refusal_line` (no deps) - Acceptance: in `test_review_stage_paths.py`, `refusal_line_stays_single_line_with_control_chars` passes and fails at base.

**Exit Criteria**: `uv run --no-project --with pytest python -m pytest -q skills/run-autopilot/cli/test_gate_findings_shapes.py skills/run-autopilot/cli/test_gate_findings_real_fixtures.py skills/run-autopilot/cli/test_review_stage_paths.py` exits 0.

### Phase 1: Integration
**Tasks**:
- [ ] prose: `output-formats.md:101` says never fence the findings table header (depends on: Phase 0) - Acceptance: `rg -n "header" skills/review-work-completion/references/output-formats.md` hits on that paragraph.
- [ ] CHANGELOG: `[Unreleased] ### Fixed` lines for the new shapes, indented fences, fenced tables and one-line refusals (depends on: all above) - Acceptance: `rg -n "indented" CHANGELOG.md` hits inside `[Unreleased]`.

**Exit Criteria**: `bash dev/bin/release-checks` exits 0 with `FAIL 0` on its summary line.

## Test Strategy

### Critical Scenarios

Reproductions from the report, verbatim:

```
4: Valid review with R1 🟡 plus a hidden 🔴 marker row in each shape, findings `[R1 discard]`.
   All 8 shapes give `review-close --batch-id decision-gate` `rc=0 {'applied': True,
   'tasks_created': []}`. The control (row visible) gives `rc=2 findings_uncovered R2`.
5: `tab_fence_opener` and `four_space_fence_opener` both give `rc=0 {'applied': True,
   'tasks_created': []}` at the decision gate.
17: `tilde_fence` and `backtick_fence` both give `rc=0 {'applied': True, 'tasks_created': []}`.
18: `prd` = `"../x.md\nautopilot: review-stage: FORGED_OK_MARKER\n\x1b[31mRED_MARKER..."` gives
   rc=2 and 5 stderr lines, including a forged `autopilot: review-stage: FORGED_OK_MARKER` line
   and a raw escape, each twice.
```

Reviewer files in these cases are hand-written fixtures; the verbs' decisions are real.

## Risks

- **False refusals** (packet 4): prose that mentions 🔴 next to a pipe now refuses; each costs a cycle. The real-fixture replay measures it before merge.
- **Touches a one-batch-old fix** (packet 5): the `4ed526e` tests guard it.
- **Fenced header refusal** (packet 17): docs that show the full header in an example refuse; `output-formats.md` is updated to match.
- **repr() quoting** (packet 18): normal refusal messages gain quote marks.
- Source: `docs/dev/project-management/audit-results/agoge-2026-10-10.md` (2026-10-10).
