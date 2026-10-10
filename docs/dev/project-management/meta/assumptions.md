# Assumption ledger — PRD 00269 (sweep every findings token)

## 1: gate: fence-aware scan, section bounds, unconsumed-token refusal, no-section rule, exit routing

Test author (Tess):
- Made up the 00268 payload: a table with header `| ID | Consensus | Sev | Description | Location |` and rows `| F1 | [3/3] | ... |`. Neither header nor rows match today's parser.
- The contract gives no detail text for a second live findings heading, so that test only checks: tag `malformed`, a non-empty detail other than the no-section text, and exit 2.
- An HTML comment line like `<!-- | R3 | [1/3] | ... | -->` counts as a token line because it holds `[1/3]`, even though it starts with `<!--`, not `|`.
- A fence opened with `~~~~` does not close on a later `~~~` line (fewer characters) and does close on `~~~~~`, per "at least as many".
- The exit code is checked by calling `gate._findings_exit(text, path)` directly, not through a subprocess.
- A Python 3 with pytest installed must be on PATH; ran via `uv run --no-project --with pytest` since the mise python here has none.

Test author (Tess), strengthening round:
- The weak-point-6 batch that names R3 asserts only "not ok, exit 2" — the PRD does not say whether the unread-token refusal or the unbacked-row mismatch is checked first.
- The rows for weak points 2, 3 and 4 sit under `## Alice`, not inside the findings section, because inside the section the table parser would read a commented or indented ref row as a data row (giving `uncovered`) rather than leaving it unread.
- Read "the same row" in weak point 3 as the row from the one-line comment test.
- Did not change `test_gate.py::test_a_missing_section_with_findings_rows_exits_2`; the "names 2 rows" check for a mixed batch went into the shapes-file test instead.

Implementor (Ivan):
- Extracted `_table_header` from `_table_keys` with no change in behavior, reading "reuse `_table_keys` unchanged" as unchanged behavior, not a ban on extracting a shared helper.
- The sweep runs before the `unreadable-table` check, so a table with an unrecognised header reports the unread-line detail instead of the `unreadable-table` text; both exit 2 and the existing tests accept either.
- Named the new `_FINDINGS_PROBLEMS` key `repeated-section`; the tests only require its detail to be non-empty, not the no-section text, and exit 2.
- Fence openers/closers were first implemented requiring column-0 alignment (no indentation) — corrected in the review retry to use the stripped line per the contract's own wording, after a confirmed MEDIUM finding.
- The no-section-with-rows detail counts every findings row, whatever its classification, as the strengthened test pins.

Implementor (Ivan), MEDIUM-finding retry:
- Where the dispatch allowlist (gate.py only) and the review's suggested fix (add two tests) conflicted, followed the allowlist and left the test file untouched; the orchestrator added the two regression tests directly instead.
- Changed the `_unfenced` docstring sentence describing the closer rule so it does not contradict the corrected code — the only change outside the two lines the finding named.
