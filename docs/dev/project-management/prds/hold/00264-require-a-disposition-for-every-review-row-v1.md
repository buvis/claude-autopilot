---
catchup: skip
design: skip
default_model: sonnet
model_tier_rationale: transcription - the check, its result token and the tests are named exactly; classification values already exist
ledger_keys: 83449f8a9b37
---

# Require a disposition for every review row

## Problem

Hold stub 00260 (ledger key `83449f8a9b37`, batch `202610031511`, from PRD
00256 cycle 2, R2): `gate._cross_check_findings` (`skills/run-autopilot/cli/gate.py:386`)
checks one direction only. A `--findings` JSON row the review never recorded
is refused, but a review-table row the JSON leaves out passes silently. So an
orchestrator that drops an inconvenient HIGH while writing the JSON gets no
error from `autopilot gate --findings` or from `autopilot review-close`, which
runs the same check. Operator decision (2026-10-05): every consolidated row
must carry an explicit disposition in the JSON. Each JSON row already has a
`classification` in `fix | defer | verify | discard`
(`gate.py:141`, `review_close.py:286-287`), and every pipe-table row carries a
`Ref` (`R1`, `R2`, ...), so the missing piece is a coverage check.

## Solution

After the existing backed-row loop, refuse when a review-table row's `Ref` is
named by no JSON row. Bullet-shape rows carry no ref and stay exempt.

## Requirements

### Must have
- `_cross_check_findings` returns `("uncovered", "<message naming the first missing ref>")` when any review row with a non-empty ref is named by no JSON row's `ref`, regardless of that JSON row's classification.
- `autopilot gate --findings` exits 2 on `uncovered`, as on `mismatch`; `review-close` refuses and writes nothing, as on `mismatch`.
- `phase-review.md` and `review-work-completion/SKILL.md` say every consolidated row needs one JSON row with a `classification`, `discard` included.
- Hold stub 00260 leaves `prds/hold/`.

### Nice to have
- None.

## Implementation

### Module: gate
- **Location**: `skills/run-autopilot/cli/gate.py`
- **Responsibility**: review-file and findings checks
- **Exports**: `_cross_check_findings()` (new `uncovered` result)

### Module: review_close
- **Location**: `skills/run-autopilot/cli/review_close.py`
- **Responsibility**: apply a saved review
- **Exports**: `close()` (refuses on `uncovered`)

### Module: skill prose
- **Location**: `skills/run-autopilot/references/phase-review.md`, `skills/review-work-completion/SKILL.md`
- **Responsibility**: tell the orchestrator every row needs a disposition
- **Exports**: none

### Dependencies
- gate: No dependencies (foundation)
- review_close: Depends on [gate]
- skill prose: Depends on [gate]

## Tasks

### Phase 0: Foundation
- [ ] gate: after the backed-row loop in `_cross_check_findings`, compute `named = {str(r.get("ref", "")).strip() for r in findings}` and return `("uncovered", f"review row {ref} has no findings-JSON row; give it a classification (fix, defer, verify or discard)")` for the first reviewed row whose `ref` is non-empty and not in `named`; map `uncovered` to exit 2 wherever `mismatch` is mapped. Update the docstring ("both directions"). Tests in `skills/run-autopilot/cli/test_gate_findings_table.py`: `test_dropped_table_row_is_uncovered`, `test_discarded_row_counts_as_covered`, `test_bullet_rows_without_ref_need_no_coverage` - Acceptance: `python3 -m pytest skills/run-autopilot/cli/test_gate_findings_table.py` passes and the first test fails at base.

### Phase 1: Core
- [ ] review_close: treat `uncovered` exactly like `mismatch` (refuse, nothing written) (depends on: Phase 0) - Acceptance: `test_close_refuses_an_uncovered_review_row` passes in `skills/run-autopilot/cli/test_review_close.py`.
- [ ] skill prose: in `phase-review.md` (decision gate) and `review-work-completion/SKILL.md` (findings JSON step), state that every consolidated row gets one JSON row with its `ref` and a `classification`, `discard` included (depends on: Phase 0) - Acceptance: `test_findings_json_covers_every_row_prose` passes (new, in `skills/run-autopilot/cli/test_gate_findings_table.py`).
- [ ] triage: delete `docs/dev/project-management/prds/hold/00260-triage-r2-prd-test-strategy-says-a-findings-jso-v1.md` (depends on: Phase 0). Premise: the file exists and names ledger key `83449f8a9b37`; re-check at execution, skip and report if not - Acceptance: `test ! -e` on that path.

## Success Criteria

- `test_dropped_table_row_is_uncovered`, `test_discarded_row_counts_as_covered`, `test_bullet_rows_without_ref_need_no_coverage`, `test_close_refuses_an_uncovered_review_row` and `test_findings_json_covers_every_row_prose` pass.
- `bash dev/bin/release-checks` exits 0.
