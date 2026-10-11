# Assumption ledger

Per-plan. Replaced at the first completed task of a full-plan pass.

Plan: PRD 00271 (guard v2 structural delegation check), batch 202610111300.

## 1: Normalize lookalike text before any guard matching

Tess (test author):

- A prompt with no phase-skill instruction at all ("Summarize the work you
  finished...", "Write the regression test...") is the safe shape for the
  required negative cases; the contract's "True iff the dispatch instructs a
  subagent to run a phase skill" covers it without touching the module's
  ambiguous compound-noun handling.
- The field join inside `is_phase_delegation` stays `f"{prompt}\n{description}"`
  (pre-existing), so a normalized `description` alone can still match a
  pattern; the description-only case depends on that join surviving the change.
  (NOTE: later superseded in part - the join still exists but each field is now
  normalized separately. The description-only case still passes.)
- "Strip `*`" removes asterisks with no replacement, so `"2**8 *args"` becomes
  `"28 args"`.
- A long-prompt case built by repeating a benign sentence 10 times is an
  acceptable stand-in for "a real dispatch prompt of hundreds of lines".
- U+05BE HEBREW PUNCTUATION MAQAF is a fair second out-of-range `Pd` pin
  alongside U+301C; both confirmed category `Pd` and NFKD-stable before use.
- "The plain ASCII letter it compatibility-folds to" for U+212B means capital
  `A` (U+212B -> NFKD -> `A` + U+030A, Mn dropped).
- The jamo-input case is within the "couple of concrete cases" allowance; it
  pins the NFKC step without recomputing the contract.
- A separate test function (not the `_LOOKALIKE_CASES` table) is the cleaner
  home for the NFKC pin, because the jamo-input case is not a fixed point and
  does not fit the table's `(raw, plain, id)` shape.

Ivan (implementor):

- `_normalize` is the single normalization entry point for the dispatch text,
  kept local to the module rather than promoted to `_common.py`.
- Category-based dropping (`Mn`/`Cf`) over an enumerated code-point table: the
  tests exercise 8 distinct invisibles and 3 mark forms and the docstring names
  the families, so the family rule is the spec rather than a lookup list.
- Deleted every asterisk unconditionally (not just paired emphasis markers),
  which the `2**8` and `*args` cases require.
- Appended the new test file at the end of the `[checks] hook registration`
  list rather than in alphabetical position; the existing list is not strictly
  alphabetical and the registration test only checks membership.
- `kept` is left unannotated as a local (the module annotates signatures, not
  locals), matching the surrounding style.
- (Superseded) the whole U+2010..U+2015 dash range was folded as "the same
  family" even though only part of it was tested. That assumption was WRONG
  against the contract, which says the `Pd` category; it left 15 `Pd` code
  points unfolded and a live guard bypass, and was fixed in the same task.

## 2: Freeze the real-dispatch replay fixture

Tess: skipped (test-and-fixture-only task, no separate test author).

Ivan (implementor):

- `source` label scheme: `00242-build-session` for the four deny records (the
  contract's own example, and all four do come from that one session) and the
  bare transcript session id (filename stem, no `.jsonl`) for the 13 allow
  records; the contract allowed either form.
- Record order in the file: deny group first, then allow, each in the
  contract's listing order (the contract specifies no order).
- `ensure_ascii=False` when serialising, so real prompt text stays readable in
  diffs; JSON decoding is byte-identical either way.
- Only the two named test functions were written; no extra schema/shape
  assertions beyond the pinned-deny-ids check the acceptance criteria name.
- The parametrized verdict test uses one pytest param per record (rather than a
  loop inside one test), so the 13 expected reds are individually visible; the
  criteria said "one subprocess run per record" without fixing the test shape.

Orchestrator:

- Pat's diff was trimmed once to fit the 50 KB dispatch budget (the untrimmed
  task diff is 255,886 bytes, 252 KB of it the fixture's verbatim prompt data).
  The fixture body was excluded from his diff and replaced by its `--stat` line
  plus the mechanical byte-identity evidence; he reviewed the two code files in
  full. Recorded because it means no model read the fixture's 252 KB end to
  end - its correctness rests on the mechanical re-harvest comparison, not on
  reading.
