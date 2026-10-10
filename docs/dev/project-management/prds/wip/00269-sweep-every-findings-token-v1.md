---
design: run
default_model: opus
model_tier_rationale: invents the token-sweep predicate and the refusal wording both review verbs share; a wrong rule either stalls the loop on honest files or lets a CRITICAL leave the gate with no task
---

# Sweep every findings token

## Overview

### Problem Statement

The second agoge run of 2026-10-07 (`docs/dev/project-management/audit-results/agoge-2026-10-07-2.md`, packets 1-3, all HIGH, all confirmed by running the code) shows that a 🔴 review row still leaves the decision gate with no task and no refusal. PRD 00265 patched shapes one at a time; these shapes got past it:

1. **Heading typo or no heading (packet 1).** `## Consolidated findings`, `### Consolidated Findings`, `## Consolidated Findings (cycle 2)`, or no heading at all: `gate --findings` exits 1, but `review-close` applies the batch (`"findings_cross_check": "malformed"`, no task). A file whose only CRITICAL sits under `## Alice` with findings `[]` also applies. The loop runs only `review-close` at the decision gate, so the gate refusal never fires.
2. **Second heading, or `## ` in a code fence (packet 2).** The section is sliced from the first findings heading to the next `## ` line, fenced or not. Rows after a second findings heading, or after a fenced `## example`, are never read.
3. **Rows the parser skips (packet 3).** A row above the table header, a `* [2/2] 🔴 ...` bullet, and a one-line `<!-- ... -->` row are ignored.
4. **Unrecognised header (hold stub 00268, R4).** `| Ref | Cons | Sev | Issue | Files |` with a 🔴 row gives `gate` exit 0.

Operator decision (minutes of that report, settled): fix the class, not the shapes. Any `[m/n]` token or pipe-table row the findings parser did not consume makes the file unreadable (exit 2) in both verbs. `CHANGELOG.md` line 14 ("`review-close` now refuses exactly what `autopilot gate` refuses ... every refusal exits 2") is false today and is rewritten to the true claim.

Folded in from the same minutes (all settled):

- **Packet 13**: a review file with no `Verdict:` line makes `review-close` exit 1; it gets a `refused` kind and exits 2.
- **Packet 14**: the `docs/dev/tmp` escape refusal in `review_stage._tmp_escape_refusal` exits 1; PRD 00266 required 2, and the 00266 review minutes claim it was fixed in rework when it was not.
- **Packet 15**: the `ref-required` message gives no hint that a 0.9.0-era review file has no Ref column.
- **Packets 16 and 17**: the `carry_unmatched` text hides which condition failed; the `review-stage` path refusal does not name the field, the raw value or the resolved path.
- **Packet 18**: `_carry_unmatched` refuses a correctly stamped task named `[D1] ...`. The `not name.startswith("[D")` condition was an operator-session slip in the 00265 design fix and is removed.
- **Packet 19**: `gather-context.sh --since <blob sha>` passes `cat-file -e`, the diff fails, and `|| echo '_No diff available_'` turns that into exit 0 with an empty diff.

### Target Users

The autopilot decision gate and tail sweep (every `autopilot gate --findings` and `autopilot review-close` call), `autopilot review-stage`, and the operator reading their refusals.

### Success Metrics

- Every payload in the problem statement exits 2 from both verbs and leaves `state.json` byte-identical.
- The real fixture `skills/run-autopilot/cli/fixtures/00256-review-1.md` still reads clean: `python3 -m pytest skills/run-autopilot/cli/test_gate_findings_real_fixtures.py` passes unchanged.
- `bash dev/bin/release-checks` exits 0 (last phase only).

## Functional Decomposition

### Capability: Token sweep

One rule, in `gate.py`, behind `findings_verdict`, so `gate --findings` and `review-close` (both batch ids) cannot disagree. It runs only when findings are cross-checked; `gate` without `--findings` is unchanged.

#### Feature: Fence-aware line scan
- **Description**: classify every line of the review file as quoted or live.
- **Inputs**: the review file text.
- **Outputs**: per-line quoted flag.
- **Behavior**: a line whose stripped text starts with three or more backticks or tildes opens a fence; the fence closes on a later line that starts with the same character, at least as many times. Lines from the opener to the closer, both included, are quoted. A fence that never closes quotes nothing (every line after the opener stays live), so an unclosed fence cannot hide a row. HTML comments do not quote. A quoted line is never a token, a row, a findings heading or a section end.

#### Feature: Section bounds
- **Description**: find the one findings section.
- **Inputs**: the live lines.
- **Outputs**: the section's line range, or a refusal.
- **Behavior**: the heading stays the exact `^##\s+Consolidated Findings\s*$`, matched on live lines only. A second live findings heading makes the file unreadable. The section ends at the next live `^##\s` line. A fenced `## example` inside the section no longer ends it.

#### Feature: Unconsumed-token refusal
- **Description**: every live token must have been read by the parser.
- **Inputs**: the live lines, and the line numbers the parser consumed (the bullet rows `_FINDING_ROW_RE` read, plus the recognised table's header, separator and data rows).
- **Outputs**: `("malformed", detail)` where detail is `line <n>: a [m/n] token or table row the findings parser did not read: <line stripped, cut to 120 chars>`, naming the first such line.
- **Behavior**: a live line is a token line when it contains `\[\d+/\d+\]` anywhere, or when its stripped text starts with `|`. Any token line not consumed refuses: a row above the header, a `*` or `+` bullet, a one-line `<!-- ... -->` row, a second table, every line under an unrecognised header (00268), and any token outside the section (for example under `## Alice` or `## Follow-up Tasks Created`).

#### Feature: No-section rule
- **Description**: the legacy "surfaced, never refused" path survives only for a truly empty legacy file.
- **Behavior**: with no live findings heading, the verdict is `("malformed", _FINDINGS_PROBLEMS["no-section"])` only when the file has zero token lines AND the findings JSON is empty. A token line gives the unconsumed-token detail above. No token line but a non-empty findings JSON gives `no '## Consolidated Findings' section, yet the findings JSON names <k> rows: the findings heading is missing or misspelled`.

#### Feature: Fail-closed exit routing
- **Description**: route on the one detail that may pass, not on the ones that refuse.
- **Behavior**: `gate._findings_exit` returns 1 only when the detail equals `_FINDINGS_PROBLEMS["no-section"]`; every other `malformed` detail returns 2. `review_close._findings_refusal` refuses `findings_malformed` for every `malformed` detail except that one, which keeps today's legacy apply with `findings_cross_check: "malformed"` (nothing to apply, since the findings JSON is empty).

### Capability: Honest refusals

#### Feature: No-Verdict refusal exits 2 (packet 13)
- **Description**: a review file with no `Verdict:` line is a refusal, not a plain "not applied".
- **Inputs**: the review file text.
- **Outputs**: the refusal dict below; CLI exit 2.
- **Behavior**: `review_close.close` checks `gate.VERDICT_RE` before the shape gate; a file with no Verdict line returns `{"applied": False, "refused": "no_verdict", "reason": <gate.check's no-verdict text>}`, so the CLI exits 2. Other shape gaps and `already applied` keep exit 1.

#### Feature: Staging escape exits 2 (packet 14)
- **Description**: the `docs/dev/tmp` escape refusal matches the sibling `prd` refusal and the record.
- **Inputs**: the repo root and its `docs/dev/tmp` path.
- **Outputs**: `{"ok": False, "error": ..., "exit": 2}`; the corrected review file.
- **Behavior**: `_tmp_escape_refusal` returns `"exit": 2`; `review-stage` exits 2. The 00266 review file gets a dated correction under Bob and Carl: `> **Correction (2026-10-10, PRD 00269):** the staging-refusal exit code (1 vs 2) was not fixed in the 00266 rework; PRD 00269 fixes it.`

#### Feature: Version-skew hint (packet 15)
- **Description**: the `ref-required` refusal says why an old review file has no Ref column.
- **Inputs**: none new.
- **Outputs**: the longer message.
- **Behavior**: `_FINDINGS_PROBLEMS["ref-required"]` ends with `; review files from autopilot 0.9.0 or earlier have no Ref column; finish or restart the batch on one version`. Both verbs show it.

#### Feature: Path refusal names the field (packet 17)
- **Description**: the `review-stage --state` path refusal says what failed.
- **Inputs**: the state's `prd` and `design_doc`, the wip dir, the repo root.
- **Outputs**: one stderr line per failing field.
- **Behavior**: `_stage_inputs_from_state` prints one line per failing field: ``autopilot: review-stage: `prd` '<raw>' resolves to <resolved>, outside <wip>/ (<state>)`` or ``autopilot: review-stage: `design_doc` '<raw>' resolves to <resolved>, outside the repo <repo_root> (<state>)``. Exit stays 2.

### Capability: Carry match

#### Feature: No name test (packet 18)
- **Description**: a carry task is known by its stamps, never by its name.
- **Inputs**: the carry row, `state.cycle`, `state.tasks`, `state.rework_task_ids`.
- **Outputs**: matched or unmatched.
- **Behavior**: drop `not str(t.get("name", "")).startswith("[D")` from `_carry_unmatched`. A task backs a carry row when, in this order: (1) its `carry_refs` hold the row's ref, (2) `carry_cycle == cycle`, (3) its id is in `rework_task_ids`, (4) `escalation_reason` is `review_flag` or `fable_rescue`, (5) `status != "completed"`.

#### Feature: Closest task named (packet 16)
- **Description**: the `carry_unmatched` reason names the task nearest to a match and its first failing condition.
- **Inputs**: as above.
- **Outputs**: the `reason` string of the `carry_unmatched` refusal.
- **Behavior**: the `carry_unmatched` reason is one of: `carry row ref (none): a carry row needs a ref to match a re-queued task`; `carry row ref <R>: no task lists <R> in carry_refs`; or `carry row ref <R>: closest task <id> "<name>" fails <field>: <why>`. Closest = among tasks listing the ref, the one passing the longest run of conditions 2-5 in order; ties go to the first in `state.tasks`. `<field>: <why>` is `carry_cycle: <value> is not <cycle>`, `rework_task_ids: <id> is not listed`, `escalation_reason: <value> is not review_flag or fable_rescue`, or `status: completed`.

### Capability: Loud diff gathering (packet 19)

#### Feature: Commit-only `--since`, no swallowed diff
- **Description**: a wrong `--since` or a failing diff can no longer hand reviewers an empty diff with exit 0.
- **Inputs**: `--since <ref>`, the review-paths marker.
- **Outputs**: the context and diff files, or a non-zero exit.
- **Behavior**: `gather-context.sh` accepts `--since` only when `git rev-parse --verify --quiet "$SINCE_REF^{commit}"` succeeds; otherwise it keeps today's warning (`--since ref <ref> does not resolve; using the branch base`) and falls back. Both `git diff` calls in the context block drop `2>/dev/null || echo "_No diff available_"`: a failing diff exits with git's code, git's stderr intact, and prints no file paths on stdout.

## Structural Decomposition

### Repository Structure

No new files. No new test module, so `dev/bin/release-checks` and `cli/test_release_checks_counts.py` stay untouched. Every file any task touches:

```
CHANGELOG.md                                                          # line 14 fix + new [Unreleased] lines
docs/dev/project-management/reviews/
└── 00266-bind-gate-reuse-to-the-command-and-renames-v1-review-1.md   # Correction lines (packet 14)
skills/run-autopilot/cli/
├── gate.py                                   # Token sweep, no-section rule, exit routing, ref-required hint
├── review_close.py                           # findings_malformed routing, no_verdict, carry match + message
├── __main__.py                               # review-stage path refusal text, gate/review-close help
├── review_stage.py                           # _tmp_escape_refusal exit 2
├── test_gate.py                              # repoint one exit-1 test
├── test_gate_findings_shapes.py              # sweep tests (gate side), exit table case, ref-required hint
├── test_main_review_close_validation.py      # both-verb sweep tests, no_verdict, ref-required hint
├── test_review_close.py                      # repoint the legacy test, _carry_reason helper
├── test_review_close_carry.py                # carry match and message tests
└── test_review_stage_paths.py                # exit 2 and path-message tests
skills/run-autopilot/references/
└── phase-review.md                           # carry rule prose drops the [D name test
skills/review-work-completion/
├── references/
│   └── output-formats.md                     # fence example rows outside the table
└── scripts/
    ├── gather-context.sh                     # ^{commit} check, loud diff failure
    ├── test_gather_context_id.sh             # two new PASS cases
    └── test_review_verbs_prose.py            # help, prose and CHANGELOG pins
```

File-size limit (800 lines): `test_review_close.py` is at 764, so new review-close tests go in `test_main_review_close_validation.py` and `test_review_close_carry.py`; `test_gate_findings_table.py` (781) is not touched. `gate.py` (654) must stay at or under 800.

### Module: gate
- **Maps to capability**: Token sweep; Version-skew hint
- **Responsibility**: read the review file and judge a findings JSON against it, fail-closed
- **Exports**: `findings_verdict(text, findings, require_coverage=True)` (unchanged signature, new sweep inside); `_FINDINGS_PROBLEMS` gains the no-section-with-findings text

### Module: review_close
- **Maps to capability**: Fail-closed exit routing; Honest refusals; Carry match
- **Responsibility**: apply a classified review batch, or refuse it before any lock
- **Exports**: `close()` unchanged signature; new `refused` kind `no_verdict`

### Module: cli entry and review_stage
- **Maps to capability**: Honest refusals
- **Responsibility**: `review-stage` refusal text and exit codes; `gate`/`review-close` help
- **Exports**: none new

### Module: gather-context
- **Maps to capability**: Loud diff gathering
- **Responsibility**: stage the diff a review reads
- **Exports**: none new

### Module: prose and records
- **Maps to capability**: all
- **Responsibility**: CHANGELOG, phase-review carry rule, output-formats writer guidance, 00266 review correction
- **Exports**: none

## Dependency Graph

### Foundation Layer (Phase 0)
No dependencies - built first.

- **gate**: the sweep and the routing every other change reads

### Core Layer (Phase 1)
- **review_close**: Depends on [gate]
- **cli entry and review_stage**: no code dependency; placed here to keep Phase 2 for prose
- **gather-context**: no dependency

### Integration Layer (Phase 2)
- **prose and records**: Depends on [gate, review_close, cli entry and review_stage, gather-context] (states final behaviour)

## Implementation Phases

Every named test below must fail at the base commit and pass after its task. Paths are relative to `skills/run-autopilot/cli/` unless given in full.

### Phase 0: Foundation
**Goal**: one fail-closed sweep in `gate.py`.

**Tasks**:
- [ ] gate: fence-aware scan, section bounds, unconsumed-token refusal, no-section rule, `_findings_exit` routes 1 only for the no-section detail (no deps) - Acceptance: in `test_gate_findings_shapes.py`, `test_heading_typo_with_a_ref_table_is_unreadable` (parametrized over `## Consolidated findings`, `### Consolidated Findings`, `## Consolidated Findings (cycle 2)` and no heading; tag `malformed`, detail not the no-section text, gate exit 2), `test_a_critical_row_only_under_a_reviewer_heading_is_unreadable` (findings `[]`), `test_a_second_findings_heading_is_unreadable`, `test_a_fenced_h2_line_does_not_end_the_findings_section`, `test_a_fenced_example_row_and_heading_are_not_findings`, `test_an_unclosed_fence_quotes_nothing`, `test_a_row_above_the_table_header_is_unreadable`, `test_a_star_or_plus_bullet_row_is_unreadable`, `test_a_one_line_html_comment_row_is_unreadable`, `test_a_row_under_an_unrecognised_header_is_unreadable` (the 00268 payload, findings `[]`), `test_unreadable_detail_names_the_line_number_and_text`, `test_no_section_no_tokens_and_no_findings_keeps_the_exit_1_shape_gap` pass. Existing-test edits (premise, re-check before editing: `rg -c "malformed, no section at all" test_gate_findings_shapes.py` is 1 and `rg -c "def test_malformed_findings_section_exits_1_not_2" test_gate.py` is 1; if either differs, stop and report): in `test_each_findings_verdict_exits_by_its_own_tag` the no-section case takes findings `[]` (exit 1) and a new case `malformed, no section but findings rows` expects exit 2; `test_malformed_findings_section_exits_1_not_2` becomes `test_a_missing_section_with_findings_rows_exits_2`. `python3 -m pytest skills/run-autopilot/cli/test_gate.py skills/run-autopilot/cli/test_gate_findings_shapes.py skills/run-autopilot/cli/test_gate_findings_real_fixtures.py skills/run-autopilot/cli/test_gate_findings_table.py skills/run-autopilot/cli/test_gate_findings_classification.py` passes.
- [ ] gate: version-skew hint on `ref-required` (no deps) - Acceptance: `test_gate_findings_shapes.py::test_ref_required_message_names_the_0_9_0_version_skew` passes (asserts the exact appended clause in gate stderr).

**Exit Criteria**: the gate-side tests above pass.

### Phase 1: Core
**Goal**: `review-close` refuses what the sweep refuses; honest refusals; carry fixes.

**Tasks**:
- [ ] review_close: refuse every `malformed` detail but no-section (depends on: Phase 0) - Acceptance: in `test_main_review_close_validation.py`, `test_both_verbs_refuse_every_sweep_payload` (parametrized over the Phase 0 payloads; `gate --findings` exit 2, `review-close` exit 2 with `findings_malformed`, `state.json` bytes unchanged) and `test_a_missing_section_with_findings_rows_is_refused` pass. Existing-test edit (premise: `rg -c "def test_a_missing_findings_section_still_applies_as_legacy_malformed" test_review_close.py` is 1, else stop and report): it becomes `test_a_missing_section_with_no_tokens_and_no_findings_still_applies_as_legacy`, run with findings `[]`, still asserting `applied` and `findings_cross_check == "malformed"`. `test_review_close.py::test_a_no_section_verdict_applies_however_long_its_wording_is` passes unchanged.
- [ ] review_close: `refused: "no_verdict"` (depends on: Phase 0) - Acceptance: `test_main_review_close_validation.py::test_cli_exits_2_when_the_review_file_has_no_verdict_line` passes.
- [ ] review_close: ref-required hint reaches the operator (depends on: Phase 0) - Acceptance: `test_main_review_close_validation.py::test_ref_required_refusal_names_the_0_9_0_version_skew` passes.
- [ ] review_close: drop the `[D` name test, then the closest-task message (depends on: Phase 0) - Acceptance: in `test_review_close_carry.py`, `test_a_requeued_d_task_with_correct_stamps_backs_a_carry` (heidi's task `[D1] src/d.py`, `carry_refs ["R2"]`, `carry_cycle 2`, `fable_rescue`, applied), `test_a_fresh_d_task_with_no_escalation_reason_is_refused`, `test_a_completed_carry_task_is_still_refused` and `test_carry_refusal_names_the_closest_task_and_its_first_failing_condition` (parametrized: no `escalation_reason`, no `carry_cycle`, id not in `rework_task_ids`, `completed`, no task lists the ref, ref-less row) pass. Existing-test edits (premise: `rg -c "_carry_reason\(" test_review_close.py` is 3 and in `test_review_close_carry.py` is 4; `rg -c "D-named-task-is-not-a-carry-requeue" test_review_close_carry.py` is 1; if any differs, stop and report): `_carry_reason` builds the new message and its 6 call sites pass the closest-task details; the `[D2] src/b.py` parametrize row expects `False` and is renamed `D-named-requeued-task-backs-a-carry`. `python3 -m pytest skills/run-autopilot/cli/test_review_close.py skills/run-autopilot/cli/test_review_close_carry.py skills/run-autopilot/cli/test_review_close_apply.py skills/run-autopilot/cli/test_review_close_lowsev.py skills/run-autopilot/cli/test_review_close_tail_sweep.py skills/run-autopilot/cli/test_main_review_close_validation.py` passes.
- [ ] review_stage: escape exits 2 (no deps) - Acceptance: `test_review_stage_paths.py::test_a_symlinked_tmp_outside_the_repo_exits_2` passes (asserts `stage()`'s `"exit"` is 2 and the CLI returns 2).
- [ ] cli entry: path refusal names field, raw value and resolved path (no deps) - Acceptance: `test_review_stage_paths.py::test_path_refusal_names_the_field_the_raw_value_and_the_resolved_path` passes (parametrized over `prd: ../outside.md` and `design_doc: ../design.md`; stderr holds the field, the raw value and the resolved absolute path; exit 2).
- [ ] gather-context: `^{commit}` check and loud diff failure (no deps) - Acceptance: `bash skills/review-work-completion/scripts/test_gather_context_id.sh` prints `PASS: blob --since falls back to the branch base` (a blob sha: exit 0, warning names it, scope line reads `full review`) and `PASS: a failing diff exits non-zero` (a valid `--since` plus a `review-paths` marker holding `:(nosuchmagic)x`: non-zero exit, git's error on stderr, no paths on stdout), and every existing case in that harness still passes.

**Exit Criteria**: the Phase 1 test commands above pass.

### Phase 2: Integration
**Goal**: prose and records state the final behaviour.

**Tasks**:
- [ ] help text: `__main__.py` `gate` and `review-close` help and the `gate.py` module docstring name the sweep (`a [m/n] token or table row the findings parser did not read`), the no-Verdict exit 2, and say `no matching re-queued task` instead of `` no matching `[C]`-prefixed `` (depends on: Phase 1) - Acceptance: `skills/review-work-completion/scripts/test_review_verbs_prose.py::test_help_names_the_token_sweep_and_no_verdict_refusals` passes; existing-test edit (premise: `rg -c 'no matching \`\[C\]\`-prefixed' test_review_verbs_prose.py` is 1, else stop and report): that pin in `test_gate_help_describes_the_two_way_check` reads `no matching re-queued task`.
- [ ] phase-review.md: in the "Build `chosen_findings`" bullet of Dispatch rework, delete the clause "and its name not starting with `[D`" from the carry rule (depends on: Phase 1) - Acceptance: `test_review_verbs_prose.py::test_carry_rule_prose_has_no_d_name_test` passes.
- [ ] output-formats.md: under the Ref paragraph, add `A [m/n] token or a pipe-table row anywhere outside the Consolidated Findings table makes gate --findings and review-close refuse the file (exit 2); quote an example row inside a code fence.` (depends on: Phase 1) - Acceptance: `test_review_verbs_prose.py::test_output_formats_tells_writers_to_fence_example_rows` passes.
- [ ] CHANGELOG `[Unreleased]`: replace line 14's "refuses exactly what `autopilot gate` refuses ... every refusal exits 2" with the true claim (review-close refuses, exit 2, every findings file `gate --findings` refuses with exit 2; the one gap is a file with no findings section, no `[m/n]` token, no table row and an empty findings JSON, which gate reports as a shape gap, exit 1, and review-close applies with nothing to apply; a file with no Verdict line exits 2; other shape gaps and `already applied` exit 1), and add `### Fixed` lines for the sweep, the `docs/dev/tmp` exit 2, the version hint, the carry message and `[D` fix, the path message and `gather-context.sh` (depends on: Phase 1) - Acceptance: `test_review_verbs_prose.py::test_changelog_states_what_review_close_refuses_truthfully` passes (asserts `refuses exactly what` is absent from `[Unreleased]` and the new claim is present) and `test_carry_creates_nothing_prose` still passes.
- [ ] 00266 review correction lines under `## Bob` and `## Carl` (depends on: Phase 1) - Acceptance: `rg -c "Correction \(2026-10-10, PRD 00269\)" docs/dev/project-management/reviews/00266-bind-gate-reuse-to-the-command-and-renames-v1-review-1.md` prints 2, and its `Verdict:` and `Tests:` lines are unchanged (`git diff` shows only added lines).

**Exit Criteria**: `bash dev/bin/release-checks` exits 0.

## Test Strategy

### Critical Scenarios
- **Happy path**: the real `00256-review-1.md` fixture and a Ref table with every row covered -> exit 0 from both verbs.
- **Happy path**: an example row inside a closed code fence in `## Alice` -> not a finding, exit 0.
- **Edge case**: no findings section, no token, findings `[]` -> gate exit 1, review-close applies nothing and reports `malformed`.
- **Edge case**: a `[D1]` task with correct carry stamps -> the carry row is accepted.
- **Error case**: each packet 1-3 and 00268 payload -> exit 2 from both verbs, `state.json` unchanged.
- **Error case**: an unclosed fence before a 🔴 row -> exit 2.
- **Error case**: `--since <blob sha>` -> falls back to the branch base with a warning; a failing diff -> non-zero exit.

## Risks

- **False refusals on honest files**: a reviewer section or a `## Follow-up Tasks Created` line that writes `🟠 [4/4]` now refuses (real file `00223-...-review-1.md` does this). Accepted by the operator (packet 3 option 1 drawback). The detail names the line number and text, so one edit (fence it or drop the brackets) fixes it, and `output-formats.md` tells writers to fence examples.
- **Second tables inside the section** (for example `00186-...-review-1.md` "Full script output") now refuse: intended, a second table is an unread row set.
- **Edits to existing tests** can weaken coverage silently: each one carries an `rg -c` premise and a stop-and-report rule.
- **Exit-code change for callers**: no-section with findings rows moves from gate exit 1 to 2, and no-Verdict moves from review-close exit 1 to 2. Both are unreleased paths; `phase-review.md` treats any non-zero other than `already applied` as a sub-skill failure, so no prose branch changes.
