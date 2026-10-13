# Assumption ledger

Per-plan. Replaced at the first completed task of a full-plan pass.

Plan: PRD 00277 (catch critical rows in every shape), batch 202610111300.

## 1: gate: CommonMark fence rule in _unfenced

Tess (test author):

- Both the opener and the closer carry the same indent, and the row between them has no indent, so the row's own indentation is never what makes it live.
- Used the existing `_ALICE_ROW` (`[1/3]`, CRIT) instead of a 🟡 example row - the task gave that only as an "e.g." and pointed to the pattern of `test_an_unclosed_fence_quotes_nothing`.
- "Column 4" follows CommonMark tab stops: a tab moves to the next multiple of 4, so `" \t"` and `"  \t"` both reach column 4.
- The 3-space boundary control re-indents both the opener and the closer to 3 spaces, including the "unindented opener, 4-space closer" case, where the original opener had no indent.
- A pipe ref row in the Alice section with no fence counts as an unread token line, matching existing tests that refuse pipe rows outside the table.

Ivan (implementor):

- A closer's run being "at least as long" as the opener's, with the same character, is the same check as `closer.group(1).startswith(run)` - the regex captures a run of a single character only, so this holds.
