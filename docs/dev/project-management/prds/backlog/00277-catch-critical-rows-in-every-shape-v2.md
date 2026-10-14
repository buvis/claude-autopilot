---
catchup: run
design: run
default_model: opus
model_tier_rationale: the row rule is a trust boundary measured against 79 real reviews; a wrong rule either ships a CRITICAL untasked or refuses the loop's own review files
---

# A CRITICAL row with no ASCII bullet passes the gate, and bold prose that mentions an emoji is refused

Source: `docs/dev/project-management/audit-results/agoge-2026-10-14.md` (packets 4, 5, 6; all confirmed). Supersedes v1 of this PRD, held on 2026-10-13 with `docs/dev/project-management/reviews/00277-catch-critical-rows-in-every-shape-v1-blocking-escalation.md` (its Resolution section records the rule chosen here). The v1 features already shipped stay as they are: fences read off the raw line (`_FENCE_RE`, `skills/run-autopilot/cli/gate.py:206`), the fenced-header refusal (`_fenced_findings_header`, `skills/run-autopilot/cli/gate.py:495`), and the `repr` quoting in `_boundary_refusal_line` (`skills/run-autopilot/cli/__main__.py:1071-1082`).

## Problem

What v1 asked for, a severity emoji anywhere on an unconsumed line, flips 29 of 79 real reviews to `malformed` (escalation table), because the house review format uses the emoji in narrative. What shipped instead, from 00282's rework commit 3218842, is the first arm of `_is_unread_line` (`skills/run-autopilot/cli/gate.py:430-453`): a line is unread when `_BULLET_LEAD_RE` (`skills/run-autopilot/cli/gate.py:202`) matches its lead and `_SEVERITY_EMOJI_ANY_RE` (`skills/run-autopilot/cli/gate.py:155`) matches anywhere on it; 17 real reviews were accepted as flips in `_ACCEPTED_FLIPS` (`skills/run-autopilot/cli/test_gate_findings_real_fixtures.py:179-197`). Three confirmed defects remain:

- No-bullet rows pass (packet 4). A line reading `🔴 crash on empty input` followed by a source path and line, with no bullet, beside a covered table gives `gate` exit 0; the same row led by `•`, by an en dash, by a fullwidth `－`, by a zero-width space or by a no-break space gives `findings_verdict` `('ok', None)` and `review-close --batch-id decision-gate` `{"applied": true, "tasks_created": []}`. The control row led by `- ` is refused. CHANGELOG line 31 claims wordless rows are caught.
- Prose is refused (packet 5). `_BULLET_LEAD_RE` needs no whitespace after its marker, so `**Note.** The cycle carries no 🔴 finding`, `*Note:* ... 🔴`, `> ... 🔴` and `2026. ... 🔴` each exit 2, and `_unread_token` (`skills/run-autopilot/cli/gate.py:456-491`) answers `a [m/n] token or table row the findings parser did not read`, naming a token that is not there. Four of the 17 accepted flips are this shape (00188 review-2, 00207 review-01, 00244 review-1, 00256 review-2).
- Pseudo-fences hide rows (packet 6). `_FENCE_RE` opens on a backtick run whose info string itself contains a backtick and closes on a run with trailing text; CommonMark treats neither as a fence, so `_unfenced` (`skills/run-autopilot/cli/gate.py:399-427`) blanks a `- 🔴 crash on empty input` row with a file cell that a reader sees, and `review-close` applies with no task.

## Solution

Replace the bullet-lead arm with a lead-normalised emoji rule. Strip the line's lead: indent, ASCII bullets (`-`, `*`, `+`), blockquote `>`, ordinals (`\d+[.)]`), typographic bullets (`•`, `◦`, `‣`, `–`, `—`, `－`), emphasis markers (`*`, `_`), every Unicode Cf code point and every Zs space, in any combination; the line is a finding row when the first remaining character is a severity emoji. An emoji after other text is prose. The refusal names the matched emoji: `line N: a severity emoji row the findings parser did not read: 🔴 ...`. Fences follow CommonMark: a backtick opener's info string may not contain a backtick, and a closer is the run plus optional whitespace only (tilde openers keep their info string rule). The emoji tests in `skills/run-autopilot/cli/test_gate_findings_unread_shapes.py` (`test_a_severity_emoji_alone_makes_an_unread_line_a_finding` at line 57 and `test_every_severity_emoji_counts_wherever_it_sits_on_the_line` at line 90, which pins the mid-line and trailing positions) are the spec and are re-pinned to this rule deliberately. `_ACCEPTED_FLIPS` is re-baselined by running the replay guard under one code-decided rule: the four bold-lead reviews leave the list; a file that newly flips joins the list only when the line the gate names in its refusal detail starts, after lead normalisation, with a severity emoji (the rule doing what it says); a newly flipping file whose named line does not start with a severity emoji is a defect in the rule and the task fails until the rule is fixed. The task report lists every path that left or joined with the named line. CHANGELOG line 31 is reworded to describe the shipped rule and a Fixed entry names the no-bullet shapes, the bold-lead false refusal and the pseudo-fence.

## Requirements

### Must have
- Each lead shape from packet 4 (no lead, `•`, `–`, `－`, zero-width space, no-break space, and the ASCII bullets and ordinals already covered) followed by a severity emoji is `findings_malformed`; `- 🔴 x` and `1. 🔴 x` stay refused.
- `**Note.** The cycle carries no 🔴 finding`, `*Note:* ... 🔴`, `> The reviewer saw a 🔴 earlier`, `2026. ... 🔴` and `Severity split: 0 🔴 Critical, 2 🟠 High` are read as prose (exit 0).
- `**🔴 crash on empty input**` with a file cell and `> 🔴 crash` are rows (refused): emphasis and blockquote leads are stripped before the emoji is looked at.
- The refusal detail for an emoji row contains the emoji and reads `a severity emoji row the findings parser did not read`; the `[m/n]` wording stays for token and pipe rows.
- A backtick opener whose info string contains a backtick does not open a fence; a closing run followed by non-whitespace does not close one; the pseudo-fence review from packet 6 makes `review-close` refuse with `findings_malformed`, while a ```` ```python ```` block closed by a bare ```` ``` ```` still blanks.
- `skills/run-autopilot/cli/test_gate_findings_real_fixtures.py` passes with `_ACCEPTED_FLIPS` re-baselined; every path that joined the list has, in the gate's refusal detail, a named line that starts with a severity emoji after lead normalisation, and the task report quotes that line for each; a join whose named line does not start with a severity emoji is a rule defect, never an accepted flip.
- CHANGELOG line 31 describes the lead-normalised rule; `[Unreleased]` Fixed entry under **run-autopilot**.

### Nice to have
- None.

## Implementation

### Module: findings-sweep
- **Location**: `skills/run-autopilot/cli/gate.py` (`_is_unread_line`, `_unread_token`, `_unfenced`, `_fenced_findings_header`, the regex block at lines 149-206)
- **Responsibility**: read rows the way a reader sees them: by the emoji's position after the lead, and by CommonMark fences
- **Exports**: `findings_verdict()` (unchanged signature)
- New symbols: `_LEAD_RE`, `_strip_lead`, `_EMOJI_ROW_DETAIL`

### Module: sweep-tests
- **Location**: `skills/run-autopilot/cli/test_gate_findings_unread_shapes.py`, `skills/run-autopilot/cli/test_gate_findings_real_fixtures.py`
- **Responsibility**: pin the lead rule, the prose exemptions, the fence rule and the re-baselined replay
- **Exports**: none
- New symbols: `test_every_severity_emoji_counts_as_the_first_character_after_the_lead`, `test_bare_emoji_row_without_bullet_is_unread`, `test_typographic_bullet_emoji_row_is_unread`, `test_invisible_lead_emoji_row_is_unread`, `test_emphasis_wrapped_emoji_row_is_unread`, `test_bold_prose_mentioning_an_emoji_is_read`, `test_blockquote_prose_mentioning_an_emoji_is_read`, `test_ordinal_year_prose_is_read`, `test_severity_split_line_is_read`, `test_refusal_names_the_matched_emoji`, `test_backtick_in_info_string_is_not_a_fence`, `test_closer_with_trailing_text_does_not_close`

### Dependencies
- sweep-tests: No dependencies (foundation)
- findings-sweep: Depends on [sweep-tests]

## Tasks

### Phase 0: Foundation
- [ ] In `skills/run-autopilot/cli/test_gate_findings_unread_shapes.py`, re-pin `test_every_severity_emoji_counts_wherever_it_sits_on_the_line` to the lead rule (rename it `test_every_severity_emoji_counts_as_the_first_character_after_the_lead`; its mid-line and trailing templates move to the prose tests) and add `test_bare_emoji_row_without_bullet_is_unread`, `test_typographic_bullet_emoji_row_is_unread` (parametrized over `•`, `◦`, `‣`, `–`, `—`, `－`), `test_invisible_lead_emoji_row_is_unread` (zero-width space, no-break space), `test_emphasis_wrapped_emoji_row_is_unread`, `test_bold_prose_mentioning_an_emoji_is_read`, `test_blockquote_prose_mentioning_an_emoji_is_read`, `test_ordinal_year_prose_is_read`, `test_severity_split_line_is_read`, `test_refusal_names_the_matched_emoji`, `test_backtick_in_info_string_is_not_a_fence` and `test_closer_with_trailing_text_does_not_close` - Acceptance: `uv run --no-project --with pytest python -m pytest -q skills/run-autopilot/cli/test_gate_findings_unread_shapes.py` reports the eleven new tests and the re-pinned test failing at the task's base commit and every other test in the file passing.

### Phase 1: Core
- [ ] Implement `_LEAD_RE` and `_strip_lead`, replace the `_BULLET_LEAD_RE` arm of `_is_unread_line` with the first-character rule, name the emoji through `_EMOJI_ROW_DETAIL` in `_unread_token`, and apply the CommonMark opener and closer rules in `_unfenced` and `_fenced_findings_header` in `skills/run-autopilot/cli/gate.py` (depends on: Phase 0) - Acceptance: the Phase 0 command passes every test; `uv run --no-project --with pytest python -m pytest -q skills/run-autopilot/cli/test_gate_findings_shapes.py skills/run-autopilot/cli/test_gate.py` passes with no test deleted.

### Phase 2: Integration
- [ ] Re-baseline `_ACCEPTED_FLIPS` in `skills/run-autopilot/cli/test_gate_findings_real_fixtures.py` from a replay run under the join rule in the Solution (a path joins only when the gate's named line starts with a severity emoji after lead normalisation; any other new flip fails this task), quoting in the task report the named line of every path that left or joined; reword CHANGELOG line 31 and add the Fixed entry (depends on: Phase 1) - Acceptance: `uv run --no-project --with pytest python -m pytest -q skills/run-autopilot/cli/test_gate_findings_real_fixtures.py` passes; the four bold-lead paths named in the Problem section are absent from `_ACCEPTED_FLIPS`; every path present in `_ACCEPTED_FLIPS` carries a comment quoting its emoji-led line; `rg -n 'lead' CHANGELOG.md` prints a hit under `[Unreleased]`.

## Success Criteria

- The packet 4 probe (a bullet-less `🔴 crash on empty input` row with a file cell beside a covered table) gives `gate` exit 2 and `review-close` `findings_malformed`; the packet 5 probe (`**Note.** The cycle carries no 🔴 finding`) gives exit 0; the packet 6 pseudo-fence review is refused.
- The replay over the real review files passes with every flip named and accepted in `_ACCEPTED_FLIPS`, and the review files this loop writes in its own format are not among the new flips.
