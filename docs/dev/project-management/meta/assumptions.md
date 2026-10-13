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

## 2: gate: severity-content and marker-variant flag in _unread_token

Tess (test author):

- A severity word between pipes counts in any case (`Critical`, `critical`, `High`, `medium`, `LOW`) - `gate`'s own `_split_severity_cell` reads the word case-insensitively, so the committed test expects the same.
- An emoji refuses only a row-shaped line (a pipe, blockquote, or html table tag present), not "anywhere on the line" - every emoji fixture carries a pipe, a `<td>`, tabs or a column gap.
- A consensus-marker variant alone (no severity) still refuses, per the design's "a marker variant is a signal by itself" framing.

Ivan (implementor, repair dispatch):

- The design doc's original Contract code was unbuildable as written: it could not reach the pipe-less-table shape, required severity for a marker-variant-alone case the committed tests forbid, and flipped 20 real review baselines by gating an emoji-bullet arm on "pipe or blockquote marker at line start" rather than "a literal pipe or html tag anywhere" - reported as a blocker rather than guessed through, then resolved as a REPAIR (corrected Contract) by the orchestrator.
- Even the corrected Contract, applied word for word, still flipped 13 real baselines (an emoji+pipe reviewer lens bullet with no severity word, and a mid-line consensus variant in two real files) - narrowed further in-session (require a severity word adjacent to the emoji; anchor the consensus-variant match to the line's leading marker) before any baseline stayed green.
- Per-task review (Pat) found two real MEDIUM gaps in that narrowing (a wordless emoji+`Found by:` row stayed unflagged; the consensus-variant anchor missed ordinal/nested/emphasis-wrapped markers) - fixed in one retry, confirmed resolved on re-review, with no new baseline flips.
