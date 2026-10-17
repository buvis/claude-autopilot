---
catchup: run
design: skip
default_model: sonnet
model_tier_rationale: an exact character-class rule replacing a list; the replay baseline over the real reviews decides every flip
---

# The findings sweep reads a severity-emoji row behind any lead, by character class

Source: `docs/dev/project-management/audit-results/agoge-2026-10-15.md` packets 8 (MEDIUM) and 19 (LOW).

## Problem

PRD 00277 v2's rule, `_is_emoji_row` (`skills/run-autopilot/cli/gate.py:244-250`), strips a fixed lead set with `_strip_lead` (`skills/run-autopilot/cli/gate.py:218-241`): the marks in `_LEAD_MARKS` (`skills/run-autopilot/cli/gate.py:208`), ordinals matching `_ORDINAL_LEAD_RE` (`skills/run-autopilot/cli/gate.py:214`), category Zs and Cf code points and emphasis, then asks whether the first remaining character is a severity emoji. Leads outside the list hide the row: `⁃`, `∙`, `·`, `●`, `▪`, `→`, `a)`, `(1)`, `- [ ]`, `###`, U+FE0F, U+2800, U+3164, a one-line HTML comment, a one-line `<details>` element, `~~`, inline code and a link. Measured on a fixture review holding one covered row and a hidden line `<lead>🔴 CRITICAL: marker finding deletes the store`: `gate --findings` exits 0 for every lead above and `review-close --batch-id decision-gate` applies with `tasks_created: []` for `- [ ] `, `### `, U+2043 and U+2800, while the control `- 🔴 …` exits 2 (packet 8). A lead census over the real reviews found none of these leads, so widening the rule flips no baseline row. Separately, HEAD refuses `docs/dev/project-management/reviews/00311-verify-reports-what-the-gate-did-v1-review-2.md` line 24 for a prose `R1's [4/4]`, the only pass-to-refuse flip outside the replay baseline across 122 real reviews; the refusal is by design (the token belongs in a fence), but `_unread_token` (`skills/run-autopilot/cli/gate.py:521-566`) blames "a [m/n] token or table row the findings parser did not read", which sends the session hunting for a table row that does not exist (packet 19).

## Solution

Replace the lead list with a class rule. `_is_emoji_row` is true when, after consuming ordinal leads (the existing `_ORDINAL_LEAD_RE` extended to `[a-z][.)]`, `\(\d+\)` and `\([a-z]\)`) and checkbox tokens (`[ ]`, `[x]`, `[X]`), the line's first severity emoji occurs before its first character of Unicode category L or N, with every character of categories P, S, Z, C and M before it ignored; `_strip_lead` stays for the refusal detail only. A line whose first L or N character precedes its first severity emoji is prose, as today. `_unread_token` names a prose progress token precisely: when the unread line holds a `[m/n]` token and no pipe, the detail reads `line N: a [m/n] progress token in prose: [m/n] - fence it or reword (output-formats.md)`, the new `_PROSE_TOKEN_DETAIL`. `_ACCEPTED_FLIPS` (`skills/run-autopilot/cli/test_gate_findings_real_fixtures.py:179`) is re-baselined under the 00277 v2 join rule (a path joins only when the gate's named line starts with a severity emoji after lead normalisation; any other new flip fails the task), and the 00311 review-2 file joins the replay corpus.

## Requirements

### Must have
- One parametrised test row per lead listed in the Problem (eighteen cases) is refused with the `_EMOJI_ROW_DETAIL` wording; the control `- 🔴` and the bare `🔴` rows keep refusing.
- The prose exemptions stay: `test_bold_prose_mentioning_an_emoji_is_read`, `test_blockquote_prose_mentioning_an_emoji_is_read`, `test_ordinal_year_prose_is_read` and `test_severity_split_line_is_read` stay green, and a decorative line with a letter before its emoji is read as prose.
- The real-fixture replay flips nothing new under the join rule, and the 00311 review-2 file is in the corpus.
- The prose-token refusal uses `_PROSE_TOKEN_DETAIL` and names the token.
- CHANGELOG `[Unreleased]` Fixed entry under **run-autopilot**.

### Nice to have
- None.

## Implementation

### Module: sweep-lead-class
- **Location**: `skills/run-autopilot/cli/gate.py` (`_is_emoji_row`, `_strip_lead`, `_ORDINAL_LEAD_RE`, `_unread_token`)
- **Responsibility**: the class rule and the two refusal details
- **Exports**: `run_gate()` (unchanged)
- New symbols: `_PROSE_TOKEN_DETAIL`, `_CHECKBOX_RE`

### Module: sweep-lead-tests
- **Location**: `skills/run-autopilot/cli/test_gate_findings_unread_shapes.py`, `skills/run-autopilot/cli/test_gate_findings_real_fixtures.py`
- **Responsibility**: pin every lead, the prose exemptions, the token detail and the replay baseline
- **Exports**: none
- New symbols: `test_an_emoji_row_behind_any_non_alphanumeric_lead_is_a_row`, `test_a_decorative_emoji_after_a_letter_is_prose`, `test_prose_progress_token_error_names_token`

### Dependencies
- sweep-lead-tests: No dependencies (foundation)
- sweep-lead-class: Depends on [sweep-lead-tests]

## Tasks

### Phase 0: Foundation
- [ ] Add `test_an_emoji_row_behind_any_non_alphanumeric_lead_is_a_row` (parametrised over the eighteen leads, each asserting exit 2 and the `_EMOJI_ROW_DETAIL` wording through `gate --findings` on the fixture review), `test_a_decorative_emoji_after_a_letter_is_prose` and `test_prose_progress_token_error_names_token` to `skills/run-autopilot/cli/test_gate_findings_unread_shapes.py`, and add `docs/dev/project-management/reviews/00311-verify-reports-what-the-gate-did-v1-review-2.md` to the replay corpus of `skills/run-autopilot/cli/test_gate_findings_real_fixtures.py` - Acceptance: `uv run --no-project --with pytest python -m pytest -q skills/run-autopilot/cli/test_gate_findings_unread_shapes.py skills/run-autopilot/cli/test_gate_findings_real_fixtures.py` reports the eighteen lead cases and the token test failing at the task's base commit and no existing test failing.

### Phase 1: Core
- [ ] Implement the class rule in `_is_emoji_row`, extend `_ORDINAL_LEAD_RE`, add `_CHECKBOX_RE` and `_PROSE_TOKEN_DETAIL` to `skills/run-autopilot/cli/gate.py`, and re-baseline `_ACCEPTED_FLIPS` under the join rule (depends on: Phase 0) - Acceptance: the Phase 0 command passes every test; `uv run --no-project --with pytest python -m pytest -q skills/run-autopilot/cli/test_gate_findings_shapes.py skills/run-autopilot/cli/test_gate_findings_table.py skills/run-autopilot/cli/test_gate_findings_classification.py` passes.
- [ ] Add the CHANGELOG `[Unreleased]` Fixed entry `**run-autopilot**: the review gate reads a severity-emoji row behind any non-alphanumeric lead (unlisted bullets, checkboxes, headings, invisible marks, inline wrappers), and a prose \`[m/n]\` token is refused with a message that names the token instead of a table row` (depends on: Phase 1 rule) - Acceptance: `rg -n 'non-alphanumeric lead' CHANGELOG.md` prints one hit under `[Unreleased]`.

## Success Criteria

- The packet 8 fixture exits 2 through `gate --findings` for every lead in the list, and `review-close --batch-id decision-gate` refuses it with `findings_malformed`.
- The 00311 review-2 file is refused with a detail that contains `[4/4]` and `fence it`.
- `test_gate_findings_real_fixtures.py` is green with no new entry in `_ACCEPTED_FLIPS` beyond those the join rule admits.
