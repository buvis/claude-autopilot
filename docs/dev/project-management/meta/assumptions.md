# Assumption ledger

Per-plan. Replaced at the first completed task of a full-plan pass.

Plan: PRD 00277 (catch critical rows in every shape v2), batch 202610141430.

## 1: Phase 0 - pin the lead-normalised emoji rule and prose exemptions

Tess (test author):

- Prose tests also assert `_unread_token(text) is None` and `findings_verdict == ("ok", None)`, not just `_is_emoji_row(...) is False`.
- The fence tests assert that the row survives `gate._unfenced(...)`, plus the verdict tag ("malformed" when the fence does not hide the row, "ok" for the closed ```python control).
- Added an extra prose test (`test_an_emoji_past_the_first_character_after_the_lead_is_prose`) to carry the old mid-line/trailing templates, as the task described.

Devon (adversarial validator):

- One exploit run that passes everything counts as proof for all seven listed weak points; weak points were read off the one passing wrong implementation rather than independently re-run per point.

Tess (strengthen, after Devon):

- A doubled bullet ("-- 🔴") must be prose, not a double-stripped lead.
- The red test run after strengthening is expected (gate.py has no implementation yet).
- (Orchestrator correction, not Tess's own: her weak-point-7 test as dispatched incorrectly expected `- [1/3] 🔴 crash` to get the emoji wording; corrected post-hoc to the generic wording, since `_strip_lead` stops at `[` before reaching the emoji — the emoji only wins precedence when it is the line's own first remaining character.)

## 4: [D1] skills/run-autopilot/cli/gate.py (rework cycle 1)

Note: the cycle-1 assumption above that `-- 🔴` must be prose is reversed by
this task — the review found it was in neither the PRD nor the design.

Tess (test author):

- Used CRIT for every nested-lead case; the four-emoji sweep stays with the existing test.
- Spelled the doubled-dash row as `-- 🔴 x` rather than the removed bare `-- 🔴`.
- Asserted `.startswith(CRIT)` for "first character is the severity emoji" (each severity emoji is a single code point).
- Placed the new tests immediately after the existing `_strip_lead` test; the brief did not specify placement.

Tess (strengthen, after Devon):

- `_SEVERITY_EMOJI` is exactly {🔴, 🟠, 🟡, ⚪}, so ✅/🟣/🧩 are valid non-severity emoji for weak point 5.
- The leading-pipe case `| 🔴 crash | src/a.py:3 |` is pinned only through `_is_emoji_row is False`; whether it is unread via the pipe/severity-word rule is not asserted.
- Merging `test_non_letter_junk_before_the_emoji_is_not_a_lead` into the prose test is an acceptable way to stay under 800 lines.

Ivan (implementor):

- The frozenset replacement keeps the identical character set (including the fullwidth dash `－`); equivalent to the regex for 1-char inputs.
- The `_strip_lead` docstring rewrite is Ivan's own wording; the task said only that the old sentences are false.
