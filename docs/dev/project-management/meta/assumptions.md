# Assumption ledger — PRD 00265 (close the critical-row escapes)

## 1: gate: fail-closed findings-table parse plus the Ref-column fixture migration

Test author (Tess):
- `R1 | R3` ("two refs in one cell") is written as raw unescaped text, so the row carries one cell too many; an escaped `R1 \| R3` single-cell variant is not tested.
- "An EMPTY findings section" means a section with no findings rows at all, not a table header with zero data rows (the latter is `unreadable-table` today).
- The migrated shared fixtures use refs `R1`, `R2`, `R3` in table order and drop the `### Full Consensus (n/n)` subsection headings, so each section holds one contiguous table.
- `known_classification` returns `False` (not raises) for non-strings and for wrong-case strings such as `"FIX"`.
- `_cross_check_findings`'s third parameter is positional-or-keyword; the alias test calls it both ways.
- A `discard` row may be a bare `{"ref": ..., "classification": "discard"}` when it goes straight to `_cross_check_findings`, but needs the full severity/file/issue/found_by fields when it passes through the CLI's `_is_chosen_finding` gate.
- Header-name matching case and padding (`| ref |`, `|  Ref  |`) are unpinned by the requirements, so neither was asserted.
- Ghost `verify` and `discard` rows stay exempt from the cross-check; only `fix`, `defer`, `carry` were asserted.
- A findings row carrying only `ref` + `classification` is checked on its ref alone (severity/file only when present).
- A bullet-shaped row inside a Ref-bearing table section parses as a row with an empty ref.
- `gate._findings_exit` takes the findings file, not a verdict tuple, so requirement 10's mapping is asserted through the `gate --findings` CLI, one run per verdict tag.

Implementor (Ivan):
- "One new problem value in `_reviewed_keys`'s vocabulary: `ref-required`" was read as "add the message under that key to `_FINDINGS_PROBLEMS`", not "let `_reviewed_keys` return it" — three tests assert `_reviewed_keys` returns `err is None` for a ref-less section.
- A findings row with an empty or missing `"ref"` is skipped by the duplicate-classification check; otherwise the 18 ref-less rows of the real 00256 fixture would collide with each other.
- The duplicate-classification check runs before the ref-required check, per the design's numbered order; no test exercises a section that would hit both.
- Conflict detection reports the FIRST ref whose classification disagrees with its first-seen value, naming those two classifications in first-seen then conflicting order.
- Missing `classification` is compared as `None` in that check, so a ref carrying one row with a classification and one without is reported as a conflict. No test covers that pair.
- The style limit counts a function from its `def` line through its last body line inclusive.
- `_ref_conflict_verdict` / `_unbacked_verdict` naming and placement were free choices; extracting the two helpers the prompt named as examples would have reached only 52 lines.
- The comment above `TABLE_HEADER_5` documented only that binding, so it was removed with it; the design doc's prose reference to `TABLE_HEADER_5` was left alone (docs outside the allowlist).
