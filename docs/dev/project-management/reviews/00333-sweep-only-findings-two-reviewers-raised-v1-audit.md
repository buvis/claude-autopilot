# Decision Audit Log: 00333-sweep-only-findings-two-reviewers-raised-v1

PRD: `00333-sweep-only-findings-two-reviewers-raised-v1.md`
Started: 2026-10-17T15:06:08Z
Completed: 2026-10-17T15:06:08Z
Autonomous: 6  |  Deferred: 0  |  Doubts: 0

### [autonomous] 2026-10-17T15:06:08Z

**Decision**: test_review_close.py _finding() default found_by was ["bob"] (one entry, already single-voice), colliding with PRD 00333 task 2 new single-voice refusal: 10 pre-existing tests built from this default (TAIL_MED, DEFER_ROW, plain _finding() callers) expect applied:True or a non-single-voice refusal, outside task 2 own file allowlist.

**Choice**: Bumped the shared _finding() default found_by to two entries (["alice", "bob"]) since that is what a typical multi-reviewer finding looks like; tests that specifically need a single-voice row already override found_by explicitly. Verified 99 passed across the full named test list after the fix.

### [autonomous] 2026-10-17T15:06:08Z

**Decision**: 11 single-voice [1/4] Medium/Low rows (R6-R16) plus the settled fixture-bump row R5 of review cycle 1

**Choice**: discarded to the settled-decisions ledger, no task created

**Rationale**: the landed single-voice rule in phase-review.md Classification: a Medium or Low raised by one reviewer is recorded in the ledger instead of becoming a task; R5 was already settled as this PRD build decision. R1-R4 (two or more voices) go to the tail sweep.

### [autonomous] 2026-10-17T15:06:08Z

**Decision**: The prose edits are not verbatim as the PRD contract requires. Backticks are stripped in the Classification paragraph (`[1/N]`, `discard`, `disposition: "discarded"`, `single-voice`). The Select sentence reads "as discarded" without backticks and uses `->` where the PRD has `→`. The mapping row is `| Single-voice Medium or Low | "discard" |` without backticks, unlike every sibling row, which writes `"discard"` in backticks. The prose test then pins the stripped form, so the PRD's exact text is not asserted.

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-10-17T15:06:08Z

**Decision**: The new refusal tests miss the negative and ordering cases. Nothing pins that a multi-voice `fix` row, a single-voice 🟠/🔴 `fix` row, a single-voice non-`fix` row (for example `discard`) or a row with no `found_by` is handled correctly at the decision gate. Dropping the severity or classification condition in `_single_voice_refusal` would still pass the whole suite, because the shared `_finding` default was raised to two finders. The tail-sweep order (after `tail_sweep_above_medium`, before `tail_sweep_duplicates_deferral`) is unpinned too: `tail_sweep_single_voice` is absent from `test_a_tail_sweep_tripping_two_refusals_reports_the_earlier_kind` and `test_cli_exits_2_on_every_tail_sweep_refusal`. Add parametrize cases.

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-10-17T15:06:08Z

**Decision**: `_tail_sweep_refusal` is still 55 lines (mechanical facts), over the 50-line limit. It was already about 56 before this diff and the docstring trim shaved a few lines, but it was touched again. Extracting the carry, gate and empty checks would bring it under the limit.

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-10-17T15:06:08Z

**Decision**: The `found_by` guard counts `len(row.get("found_by") or [])`. A string value ("CARL" has length 4) or a duplicated list (["CARL", "CARL"]) passes as multi-voice. The PRD's stated aim is that a hand-built batch cannot bypass the rule. Require a list and count distinct entries, `len(set(...))`.

**Choice**: auto-fixed

**Rationale**: fixed by review-close
