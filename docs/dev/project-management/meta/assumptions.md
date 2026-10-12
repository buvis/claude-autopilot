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

## 6: Exempt agoge personas and quote the match in a per-type deny message

Ivan:

- Took the quoted span literal from the guard's actual stderr (28 characters,
  `_quote`'s start-10/start+20 window) rather than the dispatch's "first 30
  characters" description, since the task said to derive it by running the
  guard.
- Each case sends only `prompt` and no `description` key, since every case is
  defined by the one shared prompt and `description` was not mentioned.
- Parametrize ids left to pytest's automatic naming; the missing-`subagent_type`
  case reports as `subagent_type3`. No `ids=` was requested.
- Appended the new module as the last entry of the `[checks] hook registration`
  block, after `_replay.py`, matching the siblings' order of addition.
- Added the module to no other gate block, and did not touch `CHANGELOG.md`
  (test-only change, which the changelog rule exempts).

Orchestrator:

- Task 6's production code had already landed with task 5. Rather than re-do
  it, the orchestrator probed all eight dispatch cases against the tree, found
  every verdict and message already exact, and scoped the task to the pin
  module plus the registration line, with `hooks/guard_phase_delegation.py`
  kept out of Ivan's write allowlist. If that probe was wrong, the pins would
  have failed; they passed first try.
- Devon was skipped: a test-only task runs no Tess dispatch, so there were no
  fresh tests for him to attack.
- The shared test prompt had to be moved into
  `docs/dev/tmp/task6-shared-prompt.txt` because the installed delegation
  guard denied the orchestrator's own Ivan dispatch for quoting it as data - a
  live false positive of exactly the shape this PRD addresses.

## 7: Bound the guard's cost per megabyte of prompt

Test author (initial):

- Printed-figure precision is `:.4f`; the recipe pinned the line shape but not
  the precision.
- Imported the predicate in its own isort block and relied on pytest's
  implicit `sys.path` entry for the test's own directory.
- Put the two timing helpers at module level, matching the file's existing
  helper style, rather than nesting them in the test.
- Read "assert each is under 0.3" as a strict `<` against a named constant,
  crafted checked first.

Test author (strengthening round):

- Chose "Review the ledger writer and report what you find." as the
  no-phase-mention prompt, and `general-purpose` as the persona for the three
  prompt-varying cases; the brief fixed neither.
- Read "hundreds of KB" as about 295 KB (`"Hold on. " * 32768`).
- Extracted the quoted span out of the already-pinned `Matched: "..."` wording
  rather than asserting a literal, so the case cannot pass on a clamp.
- Reworded the module docstring's "all four tests" phrase, which had become
  untrue; flagged in case docstrings count as frozen.

Implementor:

- Kept `_fold_run`'s loop body byte-identical to the old loop rather than
  rewriting it, so the equivalence criterion is "each surrounding stage is the
  identity on ASCII".
- Treated the one-process alternating base-vs-patched comparison as the
  authoritative before/after, because the machine's load average sat between
  4.9 and 6.5 throughout and two separately timed pytest runs would not have
  been comparable.
- Rejected two faster routes on safety grounds, both recorded: a literal
  substring prefilter before each phase-name pattern (not
  equivalence-preserving, because `re.IGNORECASE` does full Unicode case
  folding where `str.lower` does not, so U+017F and U+212A could become false
  negatives - the silent-allow failure mode), and merging the clause and
  sentence boundary passes (`\s-\s` can consume a newline the sentence scan
  must report).
- Counted importing the test module and calling its timing function with a
  swapped predicate as running the test rather than reading it, so he never
  saw the acceptance criteria or the string construction.

Orchestrator:

- The red-check came back GREEN, so the task's premise ("fails at base") does
  not hold on an idle machine. Resolved by the simplest safe assumption:
  implement the optimization anyway, because the task's stated goal is
  headroom against the 5 s hook timeout, and leave the contracted 0.3 bound
  untouched with the variance deferred for a human decision. Not implementing
  would have left the task's own test one load spike away from red.
- Restored the `sorted(spans)` call the slop-pruning pass had removed, after
  the per-task reviewer independently derived the concrete failure (an
  out-of-order span is clamped to the cursor, hits the `end <= start` skip and
  is left UNMASKED, with no error, on a fail-open hook). This also re-aligns
  the shipped bytes with the implementor's 50,000-case equivalence proof,
  which was run with the sort in place.
- Devon's prompt pointed at file paths rather than inlining the test module,
  because inlining it would have put this PRD's own trigger strings into a
  dispatch prompt and tripped the installed guard again.
