# Rework design: 00256 cycle 1 CRITICAL

Source review: docs/dev/project-management/reviews/00256-finish-the-review-verbs-before-release-v1-review-1.md (head_sha b4c071ddd8a0b48fa5a1ac3439145f4e4a06ae56)

The one 🔴 row this design closes, verbatim from the cycle-1 consolidated table:

> [2/4] 🔴 The findings cross-check only parses the bullet shape `- [m/n] <sev> issue | file | Found by:` (gate.py:102, gate.py:217). Every saved review file in this repo uses the pipe table `| Consensus | Severity | Issue | File | Task | Found By |`. phase-review.md:267 and phase-review.md:195 also tell the orchestrator to copy chosen findings from that table. On a real file `_reviewed_keys` returns an empty set (section present, zero rows), so every fix/defer row reports "mismatch". `close()` therefore refuses with exit 2 on essentially every real decision-gate and tail-sweep batch, which stops the review loop. No test uses a table-shaped review file, so the suite does not catch it. Blake independently raised the related one-direction gap (a findings JSON that drops a table row still passes). Fix: parse the pipe table too (Severity, Issue, File columns), or pin the review-file writer to the bullet shape and update the phase-review.md and design-solution/SKILL.md:69 wording. Add a test fed from a real review file. | skills/run-autopilot/cli/gate.py:102 | 5 | ALICE, BLAKE

## Architecture fit

Prior fix: none - there was no prior rework fix.

The work range for the PRD is `540edd9e98dce6319c2946b21f5c4890658b454a..b4c071ddd8a0b48fa5a1ac3439145f4e4a06ae56`, 28 files, +2211/-179. The CRITICAL was *introduced* by that range: task 5 added `_reviewed_keys`, `_finding_key`, `_split_severity_cell` and `_cross_check_findings` to `cli/gate.py`, and wired the cross-check into `review_close.close()` as a mandatory refusal. Nothing before this PRD parsed findings rows at all, so the defect ships with the feature.

The layer is the review-close verb's input parsing: `cli/gate.py` owns review-file shape checks and now findings parsing; `cli/review_close.py` consumes the verdict. The fix stays inside `gate.py`'s parsing helpers. No new module, no new CLI surface, no state-schema change.

The reason this is CRITICAL rather than High: `close()` calls the cross-check unconditionally and maps `mismatch` to exit 2, so with real review files every decision-gate batch and every tail-sweep batch refuses. That is the review loop's only path to applying its own findings.

## Module placement

Edits to existing files only. No new files.

- `skills/run-autopilot/cli/gate.py` - two module constants beside the existing `_FINDING_ROW_RE`; a new `_table_keys` helper; `_reviewed_keys` gains the table rows; `_finding_key` gains escape and tag normalization; `_cross_check_findings` swaps its set-membership test for a `_backed` call.
- `skills/run-autopilot/cli/convergence.py` - drops its own `CONSENSUS_ROW_RE` and imports `TABLE_DATA_ROW_RE` from `gate`, so one pattern defines what a findings row is.
- `skills/review-work-completion/scripts/consolidate_findings.py` - emits the leading `Ref` column (`R1`, `R2`, … in row order).
- `skills/review-work-completion/references/output-formats.md` - documents the `Ref` column in both findings-table shapes.
- `skills/run-autopilot/references/phase-review.md` - its "copy the chosen findings" instructions say to carry the row's `Ref` into the findings JSON's `"ref"` field.
- `skills/run-autopilot/cli/test_gate.py` - new tests, including one fed from a real saved review file plus its real findings JSON.
- `skills/run-autopilot/cli/test_convergence.py` - only if the import change needs it; `test_severity_counts_come_from_table_rows_only` must stay green unchanged.

`cli/review_close.py` is **not** edited: its call into `_cross_check_findings` is already correct, and the settled decision (state.autonomous_decisions[1]) that `malformed` surfaces while only `mismatch` refuses stays exactly as it is.

## Interfaces & contracts

Closes: the 🔴 row quoted above.

**The dependency arrow does not change: `gate.py` imports nothing from the package.** `convergence.py:21` already does `from cli.gate import FRONTMATTER_REVIEWERS_RE, VERDICT_RE`, so `gate.py` importing `convergence` would close an import cycle. Measured on a scratch copy: `import cli.gate` then raises `ImportError: cannot import name 'FRONTMATTER_REVIEWERS_RE' from partially initialized module 'cli.gate'`, and `review_close.py:25` imports `gate` first, so that is the live path; `python3 cli/gate.py` also dies, breaking the direct-run contract `gate.py`'s own docstring states at line 7.

So the single definition lives in `gate.py` and `convergence.py` imports it, exactly like the two regexes it already takes from there. Two new module-level constants in `cli/gate.py`, beside `_FINDING_ROW_RE`:

```python
# `| [2/3] | 🟠 | wrong default | src/b.py:10 | 4 | alice, bob |` and the
# Ref-bearing form `| R2 | [2/3] | 🟠 | ... |`. The optional leading cell is
# mandatory in this pattern, not optional in spirit: without it the Ref column
# rule 7 introduces would make every row in every existing review file stop
# matching, which also silently zeroes convergence.read_cycle's severity counts.
TABLE_DATA_ROW_RE = re.compile(r"^\|(?:\s*R\d+\s*\|)?\s*\[\d+/\d+\]\s*\|", re.MULTILINE)
# `| Consensus | Severity | Issue | File | Task | Found By |`
_TABLE_HEADER_RE = re.compile(r"^\|(.+)\|\s*$", re.MULTILINE)
```

`TABLE_DATA_ROW_RE` is public (no leading underscore) because `convergence.py` consumes it: replace that module's `CONSENSUS_ROW_RE = re.compile(r"^\| \[\d+/\d+\] \|")` with `from cli.gate import TABLE_DATA_ROW_RE, FRONTMATTER_REVIEWERS_RE, VERDICT_RE` and use it at `convergence.py:70`. The pattern deliberately relaxes that module's exact single spaces to `\s*`, which is a strict widening: every row it matched before still matches. `test_convergence.py:366` (`test_severity_counts_come_from_table_rows_only`) must stay green, and a test asserting `cli.gate` imports cleanly as the FIRST package import belongs with this change.

One new helper, placed directly above `_reviewed_keys`:

```python
class Row(NamedTuple):
    ref: str       # "R4", or "" for a bullet row / a table with no Ref column
    severity: str
    file: str
    issue: str     # normalized per rule 6


def _table_keys(section: str) -> tuple[list[Row], str | None]:
    """Rows of the pipe-table form of the consolidated-findings section.

    The header row names the columns, so both the documented 5-column shape
    (Consensus, Severity, Issue, File, Found By) and the 6-column shape this
    repo's `consolidate_findings.py` emits (… Issue, File, Task, Found By)
    are read without guessing positions. An issue cell may itself contain an
    unescaped `|` — `consolidate_findings.py` does not escape it — so the
    Issue and File cells are split from the RIGHT out of the span between the
    Severity column and the first column after File, exactly as the bullet
    branch already does.
    """
```

Its behaviour, pinned:

1. **Cells, for every row:** split only — `line.strip().strip("|").split("|")` — and **do not strip the fragments here**. Strip each cell only after rule 5 has decided which fragments belong to which column. Stripping first and rejoining later deletes the space that followed an embedded pipe: replayed on the real 🔴 row, `issue \| file` becomes `issue \|file`, which no later escape collapse restores, so a verbatim-copied ref-less finding would mismatch. One split expression serves the header row and every data row, so the two can never be divided differently.
2. The first `_TABLE_HEADER_RE` row having a cell equal to `severity` AND a cell equal to `issue` (stripped, lowercased) is the **header**. Equality, not containment, in this rule and in rule 4 — one predicate, so a header cannot be selected here and rejected there. Rows before the header are ignored; a section with no such header contributes no keys, which is today's behaviour for a non-table section and leaves the bullet branch to run.
3. Data rows are exactly the lines `TABLE_DATA_ROW_RE` matches. That also makes the separator row, the header row and any prose line a non-row without a second pattern.
4. Column indices come from the header: `sev_i`, `issue_i`, `file_i` are the positions of the cells equal to `severity`, `issue` and `file`. A header missing any of the three contributes no keys.
5. For each data row, with the unstripped `cells` from rule 1 and `n = len(header_cells)`: when `len(cells) == n`, take the three cells by index and `.strip()` each. Otherwise the issue cell absorbed one or more `|`: take `cells[:issue_i]` from the left, take the `n - 1 - file_i` trailing cells from the right, and **rejoin the remaining pieces with `"|"`, then strip only the rejoined result** — that span is Issue..File, so its LAST `|`-separated piece is the file and everything before it, rejoined, is the issue. Rejoining before stripping is what restores a `\|` that the split cut in half, whitespace intact, before rule 6 collapses the escape. (Worked, for the 6-column header: `sev_i=1, issue_i=2, file_i=3`, trailing `= 6-1-3 = 2` cells, Task and Found By. With a Ref column the header is 7 wide and every index shifts by one, which is exactly why rule 4 reads the indices off the header instead of hard-coding them. For the 5-column documented header: trailing `= 5-1-3 = 1`, Found By.)
6. **`_finding_key` owns escape normalization, for BOTH sides.** It gains one step: collapse `\|` to `|` in the file and issue before keying. Collapsing only on the review-file side would guarantee a mismatch on exactly the rows whose text quotes a table — including the 🔴 row itself, which carries six `\|` sequences, and which `phase-review.md:267` tells the orchestrator to copy "straight from the finding's row".
7. **Rows carry a reference, and the reference is what the cross-check matches.** Comparing issue TEXT across the two sides cannot be made to work, and this is measured twice, not argued: with the parser fixed and text matching alone, 16 of 18 applied rows key as absent on the real pair on disk; with paraphrase tolerance added (tag stripping, containment, a 60-character prefix), 4 of 18 still fail — backticks and curly quotes differ between the review cell and the JSON — while the same looseness accepts an empty issue and two different findings that share 60 characters. Both directions were run against `reviews/00256-...-review-1.md` and `docs/dev/tmp/00256-...-rework-1-findings.json`. So the text comparison is replaced by an exact token:
   - The consolidated table gains a leading **`Ref`** column: `R1`, `R2`, … in row order. `skills/review-work-completion/scripts/consolidate_findings.py` emits it; the review-file format in `references/output-formats.md` documents it; `phase-review.md`'s "copy the chosen findings" instructions say to carry the row's `Ref` into the findings JSON's `"ref"` field.
   - A chosen row carrying `"ref"` is **backed** when a review row has that exact ref AND that row's `(severity, file)` equals the chosen row's. Issue text is not compared at all. `R4` is three characters with no paraphrase room, which is the whole point.
   - A chosen row with **no** `"ref"` falls back to today's rule unchanged: exact `(severity, file, normalized issue)`, where normalization is the existing `_finding_key` plus rule 6's escape collapse. Legacy review files (no `Ref` column) and legacy callers therefore behave exactly as they do now, so this is additive.
   - An empty normalized issue never backs anything, and a `"ref"` the review file does not contain is a `mismatch` naming the ref. There is no containment, no prefix threshold, and no similarity score anywhere in this check — the earlier draft had all three and each was shown to admit a false match.

8. **A findings table that cannot be read is its own result, carried to the caller.** `_reviewed_keys` returns a two-tuple `(rows, problem)`: `rows` is a list of `(severity, file, normalized issue)` triples plus a parallel ref map, and `problem` is `None`, `"no-section"`, or `"unreadable-table"`. `_cross_check_findings` maps `"no-section"` to today's `malformed, "no '## Consolidated Findings' section in the review file"` and `"unreadable-table"` to `malformed, "found a findings table whose rows do not match | [m/n] | ..."`. The two must not collapse into one `None`: that was the earlier draft's bug, and it would have promised a table-specific diagnostic the code could not produce. `malformed` still does not refuse (the settled decision), so neither case can newly block a batch.

9. **Types, stated once so the caller and the helper cannot disagree.** `_table_keys(section) -> tuple[list[Row], str | None]` and `_reviewed_keys(text) -> tuple[list[Row], str | None]`, where `Row` is a `NamedTuple` of `(ref, severity, file, issue)` — `ref` is `""` for a bullet row or a table without the column. No function in this change returns a `set`, and none returns a bare `None`. The earlier draft declared `set` and then concatenated with a list, which raises `TypeError` on the valid path.

`_reviewed_keys` keeps its bullet loop, adds the table rows, and returns the pair rule 9 declares:

```python
def _reviewed_keys(text: str) -> tuple[list[Row], str | None]:
    heading = _FINDINGS_HEADING_RE.search(text)
    if heading is None:
        return [], "no-section"
    section = text[heading.end() :]
    following = _NEXT_H2_RE.search(section)
    if following is not None:
        section = section[: following.start()]
    rows = []
    for row in _FINDING_ROW_RE.findall(section):
        # From the right: the row always ends `| {file} | Found by: {agents}`,
        # so an issue text carrying a pipe cannot shift the file cell.
        cells = [c.strip() for c in row.rsplit("|", 2)]
        severity, issue = _split_severity_cell(cells[0])
        key = _finding_key(severity, cells[1] if len(cells) > 1 else "", issue)
        rows.append(Row("", *key))
    table, problem = _table_keys(section)
    return rows + table, problem
```

`_cross_check_findings` keeps its loop and its three return tags; two things change inside it. It unpacks the pair and maps `problem` per rule 8 (both values give `malformed`, with their own reason strings), and its per-row test becomes `if not _backed(row, reviewed)`, where `_backed` applies rule 7: a `"ref"`-carrying chosen row matches by ref plus `(severity, file)`, a ref-less one by the exact `(severity, file, normalized issue)` triple. The `mismatch` message names the ref when one was given.

**Still out of scope, deliberately:** the one-direction semantics (a review row the batch is not applying is fine). Blake raised the other direction as a 🟠 with its own cycle-1 handling, and reversing it here would break the tail-sweep subset case `test_partial_batch_is_not_a_mismatch` pins.

## Data flow

`review_close.close()` reads the saved review file's text and the chosen-findings JSON → `gate._cross_check_findings(text, rows)` → `_reviewed_keys(text)` builds the key set from the `## Consolidated Findings` section (bullet rows **and** table rows after this fix) → each chosen row is keyed by `_finding_key` and looked up → `ok` applies the batch, `mismatch` refuses with exit 2, `malformed` is surfaced without refusing. The same `_reviewed_keys` serves `autopilot gate --findings`, so the CLI and the close path cannot disagree.

## Reuse inventory

- `gate._split_severity_cell` (`cli/gate.py:193`) — already normalizes `🟠`, `high`, `🟠 High wrong default`. Used as-is for the table's Severity cell; emoji-only cells are exactly what this repo's tables carry.
- `gate._finding_key` (`cli/gate.py:206`) — the one key function for both sides of the check. Reused unchanged, which is what guarantees bullet and table rows key identically.
- `gate._FINDINGS_HEADING_RE` / `_NEXT_H2_RE` (`cli/gate.py:99-100`) — section scoping already exists; `_table_keys` receives the already-scoped section text and does no scoping of its own.
- `review_close._nested_pairs` (`cli/review_close.py:72`) — frontmatter parsing, deliberately NOT reused: it reads indented `name: value` pairs, not markdown tables. Named here so a reviewer does not read its absence as an oversight.
- **`convergence.CONSENSUS_ROW_RE` (`cli/convergence.py:26`) — found by the sweep and reused as the data-row detector.** It already reads this same `## Consolidated Findings` table, to count severities per cycle. The first draft of this design asserted no table parser existed; the sweep refuted that, and the design changed rather than the claim. Reusing it also keeps one definition of "what counts as a findings row" in the package.
- `convergence.SEVERITY_MARKS` (`cli/convergence.py:25`) — the same four emoji `gate._SEVERITY_EMOJI` carries. NOT merged here: `gate` maps emoji to severity words for keying and `convergence` maps them to count buckets, and folding them is a refactor across two modules that this CRITICAL fix should not carry. Flagged as a duplicate worth one follow-up, not fixed in this cycle.
- `test_migration_map.parse_pipe_table` (`cli/test_migration_map.py:62`) — a general pipe-table reader, test-only, in a test module. NOT imported: production code importing a test helper inverts the dependency. Its existence is why the new helper is deliberately small.
- `custody_prose_testutil._cells` (`cli/custody_prose_testutil.py:228`) — `re.split(r"(?<!\\)\|", row)`, a row splitter that already keeps an escaped `\|` inside its cell, and it lives in a non-`test_*` module. The closest prior art, and missed by the first sweep pass (the dispatch-1 reviewer found it). NOT a drop-in: it does not handle the UNESCAPED pipe, which is the case that matters here, because `consolidate_findings.py:428` emits the issue text raw. Its negative-lookbehind split is worth copying as the escape-aware half if the implementor prefers it to rule 1 plus rule 5's rejoin; the observable contract is the same either way.
- Sweep commands actually run: `rg -n 'rsplit\("\|"|split\("\|"|startswith\("\|"\)' skills/` (15 hits, `gate.py:231` the only production one besides the test helpers), `rg -n 'def .*table' skills/run-autopilot/cli/` (hits in `render_report.py`, `render_metrics.py`, `wave_assemble.py`, `test_migration_map.py`), and `rg -c 'Consolidated Findings' skills/run-autopilot/cli/gate.py` → 3, which proves the pattern matches.

## Alternatives considered

1. **Smallest diff — pin the writer to the bullet shape instead.** Change `consolidate_findings.py` to emit bullet rows and update `references/output-formats.md`, `phase-review.md:195/267` and `design-solution/SKILL.md:69`. Diff is smaller in `gate.py` and adds no parser. Rejected: every review file already on disk stays unparseable, so the cross-check still refuses on any resumed or parked PRD, and the pipe table is the documented `## Consolidated Findings Table` form that three prose files tell the orchestrator to copy from. It trades a code fix for a documentation migration plus a data migration.
2. **Chosen — read both shapes.** `_reviewed_keys` returns the union of bullet keys and table keys. Larger than option 1 by roughly 25 lines plus tests. What the extra size buys: existing review files parse, both documented shapes stay legal, and no prose file has to change, so the fix cannot be half-applied across the pack.
3. **Normalize the review file before checking** — run the section through a converter that rewrites tables to bullets, then keep one parser. Rejected: a second representation of the same rows, and the converter needs the identical column logic anyway, so it is option 2 with an extra hop and a lossy intermediate.

## Risks & edge cases

- **An issue cell containing `|`.** Real: the 🔴 row's own text quotes `| file | Found by:`. Handled by rule 4 (split the trailing columns from the right). This is the single most likely way a naive fix regresses, and the test below pins it.
- **The 5-column vs 6-column table.** `references/output-formats.md:90` documents 5 columns; `consolidate_findings.py` emits 6 (it adds Task). Header-driven indices cover both; positional indices would silently read Task as Found By.
- **A row whose Severity cell is empty.** `_split_severity_cell` returns `("", rest)`, so the key carries an empty severity and will not match a chosen row that names one. That is today's behaviour for bullet rows and is left alone: a severity-less table row is a malformed review file, and failing to match is the safe direction.
- **Escaped pipes, on both sides.** A review file written by this skill escapes `\|` inside cells; `consolidate_findings.py` does not; and the chosen-findings JSON carries whatever the orchestrator copied, which for a quoted table row is the escaped form (and in JSON must itself be written `\\|`). Rule 6 therefore collapses the escape inside `_finding_key`, so review cell and chosen row are normalized by one function. Collapsing on the review side alone was the first draft's bug: it would have mismatched on exactly the 🔴 row that motivated the fix, which carries six `\|` sequences.
- **The `Ref` column has to reach the orchestrator, or the check stays strict and refuses.** The failure mode is benign but loud: a findings JSON written without `"ref"` falls back to exact text matching and a paraphrased row refuses with `mismatch`, exactly as today. That is the safe direction (it never applies a row the review did not record), but it means the prose change in `phase-review.md` is load-bearing, not cosmetic. The alternative — loosening the text comparison — was measured to admit an empty issue and two different 60-character-sharing findings, so it is rejected on evidence.
- **Row refs are positional, so a review file edited after its findings JSON was written can shift them.** In the loop that cannot happen: the review file is saved once and the JSON is derived from it in the same step. For a hand-edited review file the ref either resolves to the right row or does not exist, and a missing ref is a `mismatch` naming it. Content-hash refs would remove even that, at the cost of an unreadable token a human cannot copy; `R4` was chosen because a human and an LLM both copy it correctly.
- Likely next changes this design should not box in: (a) reversing or optioning the cross-check direction for Blake's 🟠 — unaffected, that lives in `_cross_check_findings`, which this fix does not touch; (b) a shared findings-row parser used by `consolidate_findings.py` too — `_table_keys` takes section text and returns keys, so lifting it later needs no call-site change; (c) more severity emoji in `_SEVERITY_EMOJI` — the fix adds no second severity table.

## Test strategy outline

In `skills/run-autopilot/cli/test_gate.py`, all fed through the existing `FindingsCrossCheckTests` helpers where they fit:

- `test_cross_check_reads_a_pipe_table_review_file` — a 6-column table, chosen findings copied from it, expect `ok`. Fails today (`mismatch`).
- `test_cross_check_reads_a_real_saved_review_file` — feed the real `reviews/00256-finish-the-review-verbs-before-release-v1-review-1.md` (copied into the test fixtures, so the test does not read the live store) and assert all 22 table rows parse. This is the parser half of the 🔴, and it is the test the finding says no fixture provided.
- `test_cross_check_refuses_the_real_paraphrased_findings_json_without_refs` — the same real review file against the real `docs/dev/tmp/00256-...-rework-1-findings.json` (also copied into fixtures), whose issue text was re-worded by the orchestrator: expect `mismatch`, **by design**. This is the honest expectation, measured twice: text matching cannot back those rows, and the design's answer is the `Ref` column, not a looser comparison. The test exists so that nobody "fixes" this case later by loosening the check.
- `test_cross_check_backs_the_same_real_pair_once_refs_are_carried` — the same two fixtures with a `Ref` column added to the review table and `"ref"` added to each JSON row: `ok`. The pair of tests above and this one together are the regression guard; a single test fed a verbatim-copied row passes by construction and proves nothing.
- `test_cross_check_matches_by_ref_regardless_of_issue_wording` — same ref, issue text re-worded (backticks removed, a sentence added, a `FIX: ` prefix), still `ok`.
- `test_cross_check_refuses_a_ref_the_review_file_does_not_contain` — and the message names the ref.
- `test_cross_check_refuses_a_ref_whose_severity_or_file_disagrees` — the ref alone is not enough.
- `test_cross_check_still_refuses_a_different_finding_about_the_same_file` — rule 7 must not become a rubber stamp: two genuinely different ref-less issues on one file at one severity, only one in the review, still `mismatch`.
- `test_cross_check_refuses_an_empty_issue_with_no_ref` — the empty string backs nothing.
- `test_a_ref_less_chosen_row_still_matches_exactly_as_before` — the legacy path, against a review file with no `Ref` column.
- `test_gate_imports_cleanly_as_the_first_package_import` — `import cli.gate` in a fresh interpreter, guarding the circular-import regression.
- `test_a_findings_table_whose_rows_do_not_match_is_malformed` — rule 8, and it must exit 1, not 2.
- `test_table_row_issue_containing_a_pipe_keys_correctly` — issue text carrying ` | ` still yields the right file and issue.
- `test_cross_check_reads_the_five_column_documented_table` — the `output-formats.md` shape (no Task column).
- `test_table_and_bullet_rows_key_identically` — the same finding written both ways produces one key, asserted by set equality.
- `test_escaped_pipe_in_a_table_cell_keys_like_an_unescaped_one`.
- `test_table_row_absent_from_the_findings_json_is_still_not_a_mismatch` — the one-direction semantics survive (guards against over-fixing into Blake's 🟠).
- Existing tests stay green, in particular `test_partial_batch_is_not_a_mismatch`, `test_malformed_findings_section_exits_1_not_2` and `test_empty_findings_against_a_missing_section_is_malformed`.

Run from the repo root: `uv run --no-project --with pytest python -m pytest skills/run-autopilot/cli/test_gate.py skills/run-autopilot/cli/test_review_close.py`.

## Review log

Non-blockers and questions recorded, not fixed:

- non-blocker (dispatch 1): the reuse sweep's first pass missed `cli/custody_prose_testutil.py:228`'s escape-aware row splitter. Now named in `## Reuse inventory`; recorded because the sweep method, not the design, is what was weak.
- question (dispatch 1): whether rule 7's 60-character prefix is the right threshold. Left as the design's one tunable; the implementor may change it with a test that justifies the new value.
- non-blocker (dispatch 1): `_NEXT_H2_RE` (`^##\s`) does not stop the findings section at `### Discarded this cycle`, so that subsection's rows (if it ever carries table rows) widen the accepted key set. Harmless under the one-direction check; worth a follow-up if the check ever becomes bidirectional.

Fixed in the doc after dispatch 1 (all three were blockers, each measured by the reviewer):

- `from . import convergence` closed an import cycle (`convergence.py:21` already imports from `gate`) and broke `python3 cli/gate.py`. The arrow is now the other way: `gate` defines `TABLE_DATA_ROW_RE`, `convergence` imports it.
- A correct parser alone did not close the CRITICAL: on the real review-file/findings-JSON pair, 22 rows parsed and 16 of 18 applied rows still keyed as absent, because orchestrators paraphrase. Rule 7 now defines paraphrase-tolerant backing, with `(severity, file)` still exact.
- Escape collapsing on the review side only would have mismatched the 🔴 row itself. Rule 6 moves it into `_finding_key`, normalizing both sides.

dispatch 1 (claude): cardinal-sin 0, blocker 3, non-blocker 2, question 2

Fixed in the doc after dispatch 2 (four blockers, codex, each replayed against the real files):

- Rule 7's paraphrase tolerance still left 4 of 18 real rows unbacked (backticks and curly quotes differ between the review cell and the JSON), while simultaneously accepting an empty issue and two different findings sharing 60 characters. Text comparison is therefore gone: the table gains a `Ref` column and the cross-check matches `ref` plus `(severity, file)` exactly, with the old exact-text rule kept only as the ref-less legacy path. This also enlarges the change into three prose/script files, which `## Module placement` now lists.
- Rule 8's malformed-table diagnostic could not survive a single `None` return shared with the missing-section case. `_reviewed_keys` now returns `(rows, problem)` with `problem` in `{None, "no-section", "unreadable-table"}`, and `_cross_check_findings` maps each to its own reason string.
- `_table_keys` was declared as returning a `set` and then concatenated with a list. Rule 9 now states every signature once: both helpers return `(list[Row], str | None)`, `Row` is a `NamedTuple`, nothing returns a `set` or a bare `None`.
- The real-pair test was specified in a way that could only pass by construction. It is now three tests: the parser recovers all 22 real rows; the real paraphrased JSON refuses **by design**; the same pair with refs carried is `ok`.

dispatch 2 (codex): cardinal-sin 0, blocker 4, non-blocker 0, question 0

Fixed in the doc after dispatch 3 (two blockers, codex):

- `TABLE_DATA_ROW_RE` required the consensus cell immediately after the opening pipe, so the `Ref` column rule 7 introduces would have made every row of every existing review file stop matching — and, through the shared detector, silently zeroed `convergence.read_cycle`'s severity counts. The pattern now accepts an optional leading `R\d+` cell.
- Rule 1 stripped each split fragment before rule 5 rejoined them, which deleted the space following an embedded pipe (`issue \| file` → `issue \|file`) and would have broken the ref-less exact-match path the compatibility guarantee rests on. Rule 1 now splits without stripping; rule 5 strips only the reconstructed cell.

**These two fixes were verified by direct measurement rather than by a fourth reviewer dispatch** (the ceiling is three). Replaying rules 1-5 and the new detector as written: both real review files yield 22 rows each; the 🔴 row's file cell is recovered exactly as `skills/run-autopilot/cli/gate.py:102` and its issue text keeps the space after the embedded pipe; a `Ref`-bearing table parses with every index shifted by one; and the separator and header rows are correctly not data rows. Script: `/tmp/verify-00256-rework-design.py`.

dispatch 3 (codex): cardinal-sin 0, blocker 2, non-blocker 0, question 0
result: ok
