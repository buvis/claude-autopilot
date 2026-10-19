## Architecture fit

`skills/review-work-completion/scripts/consolidate_findings.py` is a standalone,
dependency-free CLI/library module (PRD 00095/00198) that the review-completion
skill shells out to after every reviewer dispatch. It owns exactly one
responsibility: deciding whether two reviewer-reported findings describe the
same defect. This PRD stays entirely inside that module and its test file;
nothing else in the repo calls `match()` except `split_ledger_dismissed`
(same file), so the fix has no ripple outside this pair of files.

## Module placement

- Edit `skills/review-work-completion/scripts/consolidate_findings.py`:
  - `match()` (line 251) — tighten the numeric fallback.
  - The module header comment (line 24-33) — describe the rule as shipped,
    with the measured values, matching the existing header-comment convention
    already used for `MERGE_THRESHOLD` and `OVERLAP_THRESHOLD`.
  - One new module constant beside `OVERLAP_MIN_RATIO` (line 75).
- Edit `skills/review-work-completion/scripts/test_consolidate_findings.py`:
  - Add the two new fixture tests beside `test_distinct_defects_in_one_file_do_not_match`
    (line 146), in the "matching" section (before the "numeric-signature
    matching" section at line 508, since both fixtures below exercise the
    numeric fallback alongside Jaccard/overlap — keeping them with the other
    `match()`-level tests mirrors how `test_same_wording_in_different_files_does_not_match`
    sits beside the Jaccard tests already).
- Edit `CHANGELOG.md`: one `[Unreleased]` → `### Fixed` bullet under
  **review-work-completion**.

No new files.

## Interfaces & contracts

```python
# consolidate_findings.py, beside OVERLAP_MIN_RATIO (after line 75)

# The numeric fallback's floor on *digit length*, not count: measured against
# the pinned 00122 fixture (shared citation numbers 763/822/800, all >= 3
# digits) versus the 00070 regression fixture (shared day-count numbers 0-45,
# all 1-2 digits). A line count or line number that two reviewers independently
# cite is reliably >= 100 in this codebase's review corpus; a day count, retry
# count, or other small test-data value recurs across unrelated findings and
# carries no defect identity. Tokens shorter than this floor are dropped before
# the two-distinct-tokens count below.
NUMERIC_SIGNATURE_MIN_DIGITS = 3
```

```python
def match(finding_a: Finding, finding_b: Finding) -> bool:
    """Do these two findings describe the same defect?"""
    if not files_match(finding_a.file, finding_b.file):
        return False
    tokens_a, tokens_b = tokens(finding_a.desc), tokens(finding_b.desc)
    if jaccard(tokens_a, tokens_b) >= MERGE_THRESHOLD:
        return True
    if overlap(tokens_a, tokens_b) >= OVERLAP_THRESHOLD:
        return True
    shared_nums = {
        t
        for t in numeric_tokens(finding_a.desc) & numeric_tokens(finding_b.desc)
        if len(t) >= NUMERIC_SIGNATURE_MIN_DIGITS
    }
    return len(shared_nums) >= 2
```

`numeric_tokens()` itself (line 229) is unchanged — it still returns every
all-digit token, docstring and all. The filter lives in `match()`, the one
caller that uses the fallback as a merge *signal*; a future caller that wants
raw numeric tokens (there is none today) is not forced through the floor.

No other symbol's signature changes. `OVERLAP_MIN_RATIO`, `MERGE_THRESHOLD`,
`OVERLAP_THRESHOLD`, `OVERLAP_MIN_TOKENS` are untouched — this PRD's bug is
isolated to the numeric path.

**Module header comment** (replaces the existing final sentence of the
docstring block that currently ends "... Merging is transitive inside a file
group. `match()` is importable; the ledger filter reuses it."): insert, before
that sentence, a short paragraph naming the digit-length floor and the two
measured fixture bands (00122's 3-digit citation numbers vs. 00070's 1-2-digit
day counts), in the same style as the existing `MERGE_THRESHOLD`/
`OVERLAP_THRESHOLD` paragraphs above `SEVERITY_ORDER`.

## Data flow

Unchanged. `main()` parses reviewer output lines into `Finding` objects,
`consolidate()` clusters them pairwise via `match()` (single-linkage,
transitive), `_fold()` collapses each cluster into one row, `render()` prints
the table. This PRD only narrows one of `match()`'s three merge signals; every
other step in the pipeline is untouched.

## Reuse inventory

- `numeric_tokens()` (`consolidate_findings.py:229`) — reused as-is; the fix
  filters its output in `match()` rather than duplicating token extraction.
- `tokens()` / `jaccard()` / `overlap()` (`consolidate_findings.py:225,234,240`)
  — reused as-is; no change to the Jaccard or overlap paths.
- Nothing found to reuse for "distinguish a citation-weight number from a
  test-data number" beyond what's in this file — greps tried: `rg -n "digit|isdigit" skills/review-work-completion/scripts/consolidate_findings.py`,
  `rg -n "line.?number|citation" skills/review-work-completion/scripts/*.py`,
  `rg -rn "MIN_DIGITS|digit.*len" skills/`. No existing helper classifies a
  numeric token by magnitude anywhere in the repo; this is new, narrowly-scoped
  logic.

## Alternatives considered

1. **Chosen: digit-length floor (`len(token) >= 3`) on the numeric fallback.**
   One `set`-comprehension line, reuses every existing helper, and the
   measured fixtures show a clean separation: the pinned 00122 fixture's
   shared citation numbers are 3 digits (763, 822, 800); the 00070 regression
   fixture's shared day-count numbers are 1-2 digits (0, 1, 2, 3, 29, 31, 35,
   40, 45). No fixture in the suite sits on the boundary.

2. **Restrict the fallback to tokens that also appear as a line-citation
   suffix (`:N` or inside a `File:` cell) in either description.** Rejected:
   measured against the pinned 00122 fixture, the shared tokens 822 and 800
   appear only in *prose* ("grew from 763 to **822** lines... the **800**-line
   file cap"), never in a `File:` cell suffix (Bob's citation is
   `cli/test_render.py:821` — 821, not 822). This candidate breaks the fixture
   it was meant to preserve; it was the smaller-diff idea on paper but fails
   its own contract when measured.

3. **Require the numeric fallback to also clear a lower Jaccard floor
   (e.g. `jaccard >= 0.14`).** Rejected: measured against the two 00070 lines,
   Alice-vs-Blake(a) scores jaccard 0.055 (would correctly stay separate) but
   Alice-vs-Blake(b) scores jaccard 0.237 — *above* any floor low enough to
   keep the pinned 00122 fixture's weakest pair (jaccard 0.139) working. No
   single Jaccard floor separates the regression fixture from the pinned one;
   this is not a usable band, unlike `MERGE_THRESHOLD`/`OVERLAP_THRESHOLD`'s
   existing bands.

The chosen option is also the smallest diff of the three real candidates (1
line in `match()`, 1 new constant) and the only one that passes every pinned
fixture plus both new ones when measured by hand against the exact reviewer
text (verified above; the implementation task re-verifies via
`uv run --no-project --with pytest python -m pytest`).

## Risks & edge cases

- **A real cross-reviewer citation uses a 2-digit line number** (a file under
  100 lines). The digit-length floor would then miss a true numeric-signature
  merge. Accepted: Jaccard/overlap still catch most such pairs (as they do for
  00122's Alice-Bob pair, overlap 0.5, independent of the numeric path); the
  numeric fallback is explicitly a fallback, not the primary signal, and
  under-merging (the pre-PRD-00095 status quo) is the safer failure direction
  per the module's own stated design principle (line 51-52).
- **A future PRD widens `numeric_tokens()` to normalize something like
  `800-line`→`800`** (it already does, via `_WORD_RE`). No change needed here;
  the filter composes with whatever `numeric_tokens()` already extracts.
- **Next likely changes after this PRD:** (1) a reviewer cites a 3-digit
  number that is itself a generic test value (e.g. a timeout of `500`ms)
  shared across two unrelated findings on one file — the same false-positive
  shape this PRD closes, one digit class up. The fix does not box this in:
  the constant is named and commented precisely so a future PRD can raise the
  floor or add a stopword-style list of "common round numbers" without
  touching the call site. (2) the numeric fallback might eventually need the
  same transitivity audit `consolidate()`'s docstring already describes for
  Jaccard/overlap — out of scope here, each fixture in this PRD is a 2-3-line
  pairwise case, not a transitive-bridge case.
- **`split_ledger_dismissed` (line 393) reuses `match()` to decide whether a
  reviewer's finding matches a settled ledger entry.** Narrowing the numeric
  fallback can make a previously-dismissed finding reappear, if the ledger
  entry and the finding matched only via two small shared digit tokens. This
  is the correct direction for this PRD (the whole point is that the numeric
  fallback was over-matching), but it is a real behavior change beyond the
  consolidation table, so the implementer should grep the ledger JSON fixtures
  in the test suite for any dismissal that depends on a now-filtered digit
  pair before shipping, and the CHANGELOG entry should mention the ledger
  filter alongside the consensus table.

## Test strategy outline

- Two new fixture tests in `test_consolidate_findings.py`, each asserting row
  counts via `main()`'s stdout (same pattern as
  `test_three_real_00122_findings_merge_via_shared_numeric_signature`):
  - `test_review_00070_approvals_stay_apart_from_the_finding`: 3 reviewer
    lines in → 3 rows out (no merges).
  - `test_review_00088_substring_finding_stays_apart_from_the_dedup_finding`:
    3 reviewer lines in → 2 rows out, one `[1/3]` row found by ALICE alone,
    one `[2/3]` row found by BLAKE and BOB. (Measured ahead of the task: this
    pair already merges correctly under the current, unfixed `match()` —
    Blake/Bob score jaccard 0.268 and overlap 0.6, both already over
    threshold, and Alice shares no numeric tokens with either. The fixture is
    still required by the PRD as a non-regression pin: it proves the digit-
    length floor does not disturb a pairing that was never broken.)
- No existing test needs its expected values changed: the digit-length floor
  is additive (a strict subset of what the current fallback accepts), and
  every pinned numeric-signature fixture (`test_three_real_00122_...`,
  `test_same_file_findings_sharing_only_one_number_stay_separate`,
  `test_different_file_findings_sharing_two_numbers_stay_separate`,
  `test_numeric_tokens_extracts_only_all_digit_tokens`) already uses 3-digit
  numbers or stays below the 2-token count regardless of digit length.
- Full module suite: `uv run --no-project --with pytest python -m pytest -q skills/review-work-completion/scripts/test_consolidate_findings.py`
  must pass in full, including the threshold-band tests the header comments
  reference.
- Add a boundary-pinning unit test directly on `match()` (or on
  `shared_nums`'s construction) beside `test_numeric_tokens_extracts_only_all_digit_tokens`
  (line 796): two same-file findings sharing exactly two 2-digit tokens stay
  unmatched, two sharing exactly two 3-digit tokens (and nothing else) match,
  and two sharing one 3-digit plus one 2-digit token stay unmatched. This
  pins the floor itself, independent of the 00070/00088 fixtures, so a future
  edit that silently drops back to "any digit length" fails here even if it
  happens to still pass the narrative fixtures.

## Review log

- [question] New 00070/00088 fixture token sets are sourced from a sibling
  repo's review files, not present in this repo. No design change — the
  implementation task re-verifies the exact row counts against the real
  reviewer lines via pytest, as already stated in Test strategy outline.
- [non-blocker] Cardinal-sin taxonomy is structurally inapplicable to this
  30-line, dependency-free, stateless text-matching fix (no persistence,
  auth, secrets, schema, or production write path). No action.
- Dispatch 1 raised a third finding (blocker: "Risks section's overlap 0.5
  figure for the 00122 Alice-Bob pair contradicts the pinned test's
  docstring") that does not survive verification: re-run against the actual
  module (`cf.overlap(cf.tokens(alice122), cf.tokens(bob122))`) returns
  `0.5`, confirming the design doc's figure is correct — Alice and Bob's
  00122 findings already merge via the overlap signal alone, independent of
  the numeric fallback this PRD touches; the pinned test's docstring
  (which only speaks to the Jaccard signal) is not contradicted by a
  second, independently-true signal. No doc change.
- dispatch 1 (claude): cardinal-sin 0, blocker 0, non-blocker 1, question 1
- Dispatch 2 (codex): its own sandbox blocked both its shell tools
  (`sandbox_apply: Operation not permitted`, the known codex-under-codex
  nesting limit) before it could independently re-run the source checks, so
  it reviewed the supplied design text only. It raised one question (own
  verification blocked — noted, not a design defect) and three non-blockers:
  a missing boundary-pinning test for the digit-length floor (added to Test
  strategy outline above), the `split_ledger_dismissed` ripple (added to
  Risks & edge cases above), and a reconfirmation that no cardinal sin
  applies. No cardinal sins or blockers raised; dispatch 3 (conditional
  codex verification) is not required.
- dispatch 2 (codex): cardinal-sin 0, blocker 0, non-blocker 3, question 1
