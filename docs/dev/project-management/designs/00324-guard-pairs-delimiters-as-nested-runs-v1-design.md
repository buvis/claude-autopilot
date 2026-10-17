# Design: 00324 — guard pairs delimiters as nested runs and binds a negation to its own verb

## Architecture fit

`hooks/guard_phase_delegation.py` is a PreToolUse hook predicate
(`find_phase_delegation()` / `is_phase_delegation()`) that denies an `Agent`
dispatch whose `prompt`/`description` orders a phase skill to run. It is pure
regex + bisect over precomputed boundary lists (`_boundaries()`), built once
per field and probed per candidate span. This PRD stays inside that same
two-pass shape (`_boundaries` builds once, `_field_delegation` probes per
candidate): no new pass over the field, no new data structure crossing
function boundaries beyond what `_boundaries()` already returns. The five
problem shapes are all citation/negation/boundary bugs in `_quoted_runs`,
`_cited`, `_negated`, and `_CITE_SENTENCE_BOUNDARY`; the sixth (linearity) is
a cache-once fix inside `_ordered_to_follow`'s caller path. No new module,
no new hook registration, no change to `find_phase_delegation`'s public
signature or `main()`.

## Module placement

- Edit `hooks/guard_phase_delegation.py`:
  - replace `_quoted_runs` with a new nested-run scanner `_nested_runs`
    (same call site in `_boundaries`, same return shape consumed by `_cited`
    and `runs.get((start, end), ())`).
  - edit `_cited` to route its own-wrapper branch through the same run map
    `_nested_runs` produces, instead of a live `marks.get(...)` bisect for
    the backtick/quote case.
  - edit `_negated` to stop its backward scan at `_NEGATION_REACH_END`.
  - edit `_boundaries` only if `_nested_runs`'s signature needs the full
    `scratch` + delimiter list (it already receives both; no signature
    change expected).
- Edit `hooks/guard_phase_delegation_lexicon.py`:
  - add `_NEGATION_REACH_END` (a compiled joiner pattern).
  - extend `_CITE_SENTENCE_BOUNDARY`'s trailing character class with `。`,
    `·`, `！`, `？`.
  - add an emoticon-exclusion check (a regex matching `[:;=][)(]`) applied
    inside `_delim_positions` itself, so excluded `(`/`)` positions never
    reach `marks` or `_nested_runs`'s bracket stack.
- New tests only (no new production files):
  `hooks/test_guard_phase_delegation_citations.py`,
  `hooks/test_guard_phase_delegation_structure.py`,
  `hooks/test_guard_phase_delegation_linearity.py` (all three already exist
  per the PRD's Module section; this PRD adds cases to them, it does not
  create them).
- `CHANGELOG.md`: one `[Unreleased]` Fixed entry under **hooks**.

## Interfaces & contracts

### `_nested_runs(scratch: str, spans: list[tuple[int, int, bool]]) -> dict[tuple[int, int], list[tuple[int, int]]]`

Replaces `_quoted_runs`. Same return type, **widened** consumer contract:
for each candidate span `(start, end, is_skill_md)` in `spans`, the dict
may map `(start, end)` to a list of `(open_at, close_at)` pairs where
`open_at <= start` (not `<`, unlike `_quoted_runs` — see the `_cited` note
below, which needs both the own-wrapper case `open_at == start` and the
strictly-enclosing case `open_at < start`) and `close_at >= end`. A run
is recorded whenever the span's own `start` falls at or after some open
marker that is still open when `end` is reached, regardless of whether
that marker sits exactly at `start` or strictly before it. Differences
from `_quoted_runs`:

- **One stack per delimiter class, not per delimiter character.** Three
  independent stacks: `"`-runs, backtick-runs (paired by *run length*, see
  below), and bracket-runs (the `_WRAP_PAIR` asymmetric set plus the
  additional literal pair `("(", ")")` scanned here rather than only in
  `_cited`'s single-opener lookback). A delimiter that opens while another
  kind's run is still open is pushed onto its own stack unchanged — nesting
  is implicit in having three independent stacks rather than one combined
  parity scan. This is what fixes shape (1): a backtick opened inside an
  already-open `"…"` run is on the backtick stack, which only pairs with
  the *next unconsumed backtick*, including one that lands after the
  `"…"` run's own close — i.e. it still can pair wrongly across the quote
  boundary **unless the backtick (and quote) open events are themselves
  deferred while the other kind's run is open — symmetrically, not only
  in the bracket case.** Concretely: `_nested_runs` first tokenizes
  backtick runs with one regex (a maximal run of consecutive backticks at
  a position is one token, its length recorded), then merges that token
  stream with the single-character `"`, `(`, `)` and `_WRAP_PAIR` matches
  into one position-ordered list `_order`, walked once left to right;
  three independent open-marker slots, each initialized to the explicit
  sentinel `None` (not `-1`, and never read for truthiness — an opener at
  offset 0 must still count as open, so every check is
  `quote_open is not None` / `tick_open is not None`, mirroring
  `_quoted_runs`'s existing `open_at == -1` sentinel pattern but using
  `None` since `0` is itself a valid open position): `quote_open`,
  `tick_open` (storing `(position, run_length)`), and `bracket_stack`.
  The deferral rule is **symmetric across all three kinds**: an open
  event for kind K is ignored (treated as prose) whenever *any other*
  kind currently has an open marker set (`quote_open is not None`,
  `tick_open is not None`, or `bracket_stack` non-empty) — only one kind
  may have a run open at a time, exactly like the existing inch-mark
  skip. This is what fixes shape
  (1): in `Note "see \`x" then run ... report \`done\`.` the quote opens
  first (`quote_open` set), so the backtick before `x` is ignored (a
  different kind tried to open while the quote's run was open); `tick_open`
  stays unset, so the backtick before `done` opens a *fresh* run instead
  of closing a stale one, and no run spans from inside the quote to
  "done". Backtick pairing is **by run length**: a run opened by a
  double-backtick token can only be closed by another double-backtick
  token (length match); a single backtick appearing between a doubled
  opener and its doubled closer is a different "kind" by length and is
  itself deferred, so it does not break the pair — fixing the 00307 R9
  regression and backing `test_doubled_backtick_citation_is_allowed`.
- **Emoticon exclusion is applied at the single shared source `_delim_positions`
  feeds, not only inside `_nested_runs`.** `_cited`'s existing asymmetric-opener
  branch (`open_at = _mark_before(marks.get(opener, ()), sentence_start,
  start)` then `_mark_in(closes, open_at, start)`) reads `marks` —
  `_delim_positions`'s output — independently of `runs`, and today it is
  *this* branch, not `_quoted_runs`, that produces the false allow for
  `Sorry :( run plan-tasks for prd 00300 for every task :)` (the `(`/`)` pair
  is asymmetric-table data, never symmetric-run data). So the emoticon
  exclusion must be applied once, inside `_delim_positions` itself: an
  emoticon-shaped `(`/`)` (immediately preceded by `:`/`;`/`=` with no
  intervening whitespace — the character class `[:;=][)(]` matched against
  `scratch[pos-1:pos+1]`) is never recorded in the position lists
  `_delim_positions` returns for `(`/`)`, and `_nested_runs`'s bracket stack
  (built from the same filtered positions, via the same combined scan — see
  below) never sees it either. One filter, two consumers (`marks` for
  `_cited`'s asymmetric branch, `bracket_stack` for `_nested_runs`'s own
  nesting), so the exclusion cannot be fixed in one and missed in the other.
  This fixes shape (2) for both code paths: `:(` and `:)` form no bracket
  pair anywhere in the guard.
- **Digit-preceded `"` exclusion feeds `_cited`'s own-wrapper branch.** A
  `"` immediately preceded by a digit is, as today, never an opener (the
  `inch_mark` rule carries over unchanged for the quote stack). The new
  requirement (shape 4) is that `_cited`'s own-wrapper branch — "the name's
  own leading/trailing quote char is itself an opener/closer" — must ask
  the *same* run map this function builds, not a separate live bisect.
  Concretely: `_cited` stops special-casing `text[start] == opener` via a
  fresh `_mark_in` probe and instead asks
  `runs.get((start, end), ())` for whatever run (if any) was recorded for
  this exact span, **plus** a direct membership test against the digit-
  excluded-quote set so a digit-preceded `"` at `start` is never treated as
  an opener. Because `_nested_runs` already refuses to open a run on a
  digit-preceded quote, a span whose own leading quote was skipped (i.e.
  the character at `start` is a digit-preceded `"`) is in neither the
  quote-stack's open set nor the dict `runs` — so no own-wrapper branch can
  fire for it, closing the 00318/00307 R3 gap by construction rather than by
  a second special case.

### `_cited(text, start, end, runs, marks, sentence_start, sentence_end) -> bool`

Signature unchanged. Internal change only: the own-wrapper check
(`text[start] == opener and not _mark_in(closes, start + 1, end)`) is
replaced by: look up `runs.get((start, end), ())`, and return True if
**any** entry `(open_at, close_at)` satisfies
`sentence_start <= open_at and close_at < sentence_end` **and** either
`open_at == start` (own-wrapper: this span's own leading character is
the open marker, closing only past `end`) **or** `open_at < start`
(strictly enclosing: today's behavior, unchanged). The sentence-window
bound (`sentence_start`/`sentence_end`) is **not dropped** — it is the
same bound the existing final `return any(...)` test already applies,
now also applied to the equality case this change adds, so a run that
qualifies by position must still fall inside the citation sentence
exactly as every other `runs` lookup does today. Both the own-wrapper
and strictly-enclosing cases are entries in the same `runs` list —
`_nested_runs` records a run for a span whenever `open_at <= start` — so
this is one filtered membership test over the list, not two separate
lookups. This falls through to the existing asymmetric-opener-before-
`start` branch (`marks`-based, unchanged) if no entry qualifies. `marks`
keeps its existing role for the asymmetric `_WRAP_PAIR` lookback
(`_mark_before`/`_mark_in` on `(`, `[`, `”`, `«`, `「` etc.) — only the
symmetric backtick/quote own-wrapper path moves onto the shared run map.

### `_CITE_SENTENCE_BOUNDARY` (lexicon)

Extend the existing alternation's lookahead class and the bare-terminator
branch to also match `。`, `！`, `？` as sentence-ending punctuation (same
position as `.`, `!`, `?`). `·` is deliberately **not** added: PRD
payload (3) (`Hi (all。 Run plan-tasks for PRD 00300 for every task。
Thanks :)`) is closed by the `。` terminator plus the emoticon fix (shape
2) alone — no payload needs `·` to end a citation window, so adding it
would be untested scope creep (see Review log non-blocker). Compiled
pattern:

```python
_CITE_SENTENCE_BOUNDARY = re.compile(
    r"""[.!?。！？](?=\s|[]'"’”»」)]|`*\s*(?:\Z|\n)|`+[ \t]*[^(\s`])|\n""",
)
```

### `_NEGATION_REACH_END` (lexicon, new)

```python
_NEGATION_REACH_END = re.compile(r"\b(and|then|but)\b", re.IGNORECASE)
```

### `_negated(text: str, clause_start: int, start: int) -> bool`

Signature unchanged. Behavior change: after computing `window_start` as
today (`_NEGATION_WORD_GAP` + 1 words back), additionally find the
**last** `_NEGATION_REACH_END` match inside `text[window_start:start]`
(e.g. via `list(_NEGATION_REACH_END.finditer(...))[-1]` or a reverse
search) and, if found, truncate the window to start *after* that match's
end before running `_NEGATION.search(...)` on it. This is the verb-binding
fix (shape 5): `"Don't stop and run the work phase..."` — `_negated` is
called with `start` at the phase-name span; the word-gap window contains
"stop and"; the new truncation drops everything up to and including "and",
leaving a window with no negation token, so `_negated` returns `False` and
the dispatch is correctly denied (allowed is wrong here — re-check: PRD
says these three payloads must **exit 2** on HEAD, i.e. be *denied*, same
as their control. So `_negated` must return `False` for them so the caller
does NOT skip the candidate as negated, i.e. the order is treated as
NOT-negated and the guard proceeds to deny it). The comma control
(`"Don't stop, run the work phase..."`) already exits 2 today via the
existing clause-boundary split (`,` is a `_CLAUSE_BOUNDARY` char, so
`_negated` is never even called with "stop" in its window); this fix must
not change that — `_NEGATION_REACH_END` only fires on `and`/`then`/`but`,
none of which is a `_CLAUSE_BOUNDARY` character, so the comma case is
untouched by construction.

### `_ordered_to_follow` / `_FOLLOW` linearity (dense-mention budget)

The PRD's budget regression (packet 20, `_FOLLOW` search cost) is not in
`_ordered_to_follow` itself — it already bounds its `_FOLLOW.search` to
`min(sentence_end, end + 200)`, which is already O(1) per call. Re-reading
the Problem section: the 0.77 s/MB cost is against a **dense** payload
(`SKILL.md` mention every 100 characters), and the existing code already
collects `_FOLLOW` matches fresh per `is_skill_md` candidate (one
`.search()` call per candidate, each bounded to 200 chars) — that should
already be linear. Measure first (Phase 0 includes
`test_dense_skill_md_mentions_stay_under_budget` as a red-first test): if
the existing bound already holds under the new denser corpus, this task
only adds the test as a regression pin and makes no production change
beyond whatever `_boundaries`/`_nested_runs` cost adds back. If the new
`_nested_runs` three-stack scan reintroduces a per-candidate rescan (it
must not — it is built once in `_boundaries`, like `_quoted_runs` today),
the budget test will catch it red and task 1 of Phase 1 is scoped to keep
`_nested_runs` a single linear pass exactly like the function it replaces.
No new "once per field" collection point beyond what `_boundaries` already
provides is being added by this PRD — the PRD's "collect `_FOLLOW` matches
once per field" sentence describes the existing design's invariant that
must be *preserved*, not a new cache to build, since `_ordered_to_follow`
is called at most once per `is_skill_md` candidate already.

## Data flow

`_field_delegation(text, per_task)` → `_candidates(text)` (unchanged) →
`_boundaries(text, spans)` → `_nested_runs(scratch, spans)` (new name,
same slot) + `_delim_positions(scratch)` (unchanged) → per-candidate loop
calls `_cited(...)` (reads `runs` from `_nested_runs` + `marks` from
`_delim_positions`, unchanged signature) and `_negated(...)` (unchanged
signature, new internal truncation) → `_ordered_to_follow` unchanged.
`_CITE_SENTENCE_BOUNDARY` is read only inside `_boundaries`'s
`cite_sentences` computation — its extended character class changes which
offsets land in that list, with no change to any consumer's code.

## Reuse inventory

- `_quoted_runs` (`hooks/guard_phase_delegation.py:329`) — the function
  being replaced; its docstring/pairing-rule comment block
  (lines 310-328) documents the invariants `_nested_runs` must preserve
  (disjoint increasing pairs per delimiter, inch-mark skip-then-stop rule)
  and is reused as the basis for the new comment, not rewritten from
  scratch.
- `_delim_positions` / `_mark_in` / `_mark_before`
  (`hooks/guard_phase_delegation.py:370-396`) — unchanged, reused as-is for
  the asymmetric `_WRAP_PAIR` lookback inside `_cited`.
- `_WRAP_SCAN_PAIRS`, `_WRAP_SCAN_CHARS`, `_SYMMETRIC_DELIMS`
  (`hooks/guard_phase_delegation_lexicon.py:33-54`) — the bracket/backtick/
  quote pair tables `_nested_runs` dispatches over; extended (an emoticon
  guard added to the `(`/`)` handling) rather than replaced.
- `_words_before` (referenced by `_negated`, defined elsewhere in the same
  file — not re-read in full here since its contract is unchanged) is
  reused unchanged by `_negated`'s existing word-gap computation; only the
  post-hoc truncation is new.
- Searched for an existing stack-based nested-delimiter matcher elsewhere
  in the repo: `rg -n "stack|nested" hooks/guard_phase_delegation.py
  hooks/guard_phase_delegation_lexicon.py` — nothing found, this is new
  logic. Searched for existing emoticon/CJK-terminator handling anywhere in
  the repo: `rg -n "emoticon|CJK|REACH_END" . -g '*.py'` — nothing found
  (control query against a known-present term in the same files confirmed
  `rg` itself is working), so both are new.

## Alternatives considered

1. **Smallest-diff: patch `_quoted_runs` in place** (add the emoticon
   guard and length-paired backticks to the existing per-delimiter
   independent-pairing loop, without restructuring it into a nested-run
   stack). This fixes shapes (2), (3), (4), (6) but **cannot** fix shape
   (1): `_quoted_runs` pairs each delimiter kind independently over the
   whole field with no cross-kind nesting awareness, so a backtick inside
   a closed `"…"` run still pairs with an unrelated later backtick — the
   bug is structural to independent per-kind scanning, not a missing
   guard. Rejected: fails the PRD's own payload (1).
2. **Full recursive-descent delimiter parser** (a general nested-bracket
   parser producing a tree, then flattening to the same dict shape). Correct
   and more general, but adds a second representation (tree + flattened
   map) and a much larger diff for a five-delimiter-kind problem that a
   three-stack linear scan already solves exactly. Rejected: over-built for
   the measured bypass set.
3. **Chosen: three independent stacks (quote/backtick/bracket) in one
   left-to-right scan, with a bracket-run masking rule for nested opens and
   an emoticon pre-filter.** Smallest change that still fixes shape (1):
   nesting is expressed as "an inner delimiter cannot pair while an outer
   run is open" via the masking rule, without building a general tree. The
   extra size over option 1 buys the one structural fix the PRD requires;
   the extra size over option 2 is avoided because three stacks, not a
   generic parser, is enough for exactly the five delimiter kinds in scope.

## Risks & edge cases

- **Four backticks** (`` ```` ``) as two adjacent doubled-backtick opens:
  the run-length pairing must treat a 4-run as either one 4-length pair or
  reject ambiguity by failing closed (deny), matching the existing
  "a skipped mark makes every later pairing a guess → stop" philosophy in
  the current `_quoted_runs` comment. Not in the PRD's required payloads;
  document as an accepted limitation in a code comment rather than adding
  unrequested handling.
- **A `(` immediately preceded by `:` that is genuinely prose**, e.g.
  "ratio: (3 to 1)" — the emoticon exclusion as specified (`[:;=][)(]`
  immediately adjacent, no word char between) will also suppress this
  real bracket. This is an accepted over-exclusion (a bracket run lost is
  the guard being slightly less able to recognize a quoted order inside
  parens after a colon, which only *removes* a citation exemption — it
  cannot cause a false allow, only a possible false deny on an edge case
  outside the PRD's payloads, which is the safe direction for a guard).
- **Likely next changes** this design should not box in: (a) a future
  CJK comma/semicolon as a clause boundary (not sentence boundary) — kept
  out of `_CITE_SENTENCE_BOUNDARY` and the unrelated `_CLAUSE_BOUNDARY` on
  purpose, since this PRD only touches citation *sentence* ends; (b) a
  future fourth delimiter stack (e.g. `«»` already exists as an asymmetric
  `_WRAP_PAIR` entry, not a new stack) if a sixth bypass shape surfaces —
  the three-stack dispatch loop is written as a dict-of-stacks keyed by
  delimiter kind rather than three hardcoded variables, so adding a fourth
  kind later is a one-line addition, not a rewrite (see Interfaces: the
  bracket stack already generalizes over all of `_WRAP_PAIR` plus the
  literal `(`/`)` pair, so curly quotes and guillemets get the nesting fix
  for free without being named in any payload).

## Test strategy outline

- Phase 0 (red-first): one test per new behavior in
  `hooks/test_guard_phase_delegation_citations.py` (backtick-inside-quote
  nesting, emoticon exclusion, CJK terminators, digit-preceded-quote
  own-wrapper exclusion, doubled-backtick allow, and the
  `test_backtick_exclusion_in_cite_boundary_can_fail` meta-test that
  swaps in a boundary pattern lacking the backtick class and asserts the
  guard's answer flips — this test imports and monkeypatches
  `_CITE_SENTENCE_BOUNDARY` or constructs the pattern inline and calls the
  guard function directly, it does not touch the shipped constant);
  three negation-reach-end payloads plus the comma control in
  `hooks/test_guard_phase_delegation_structure.py`; the dense-budget test
  in `hooks/test_guard_phase_delegation_linearity.py`. Each drives
  `find_phase_delegation` end to end with the literal payload text from
  the PRD's Problem section, asserting `is not None` (denied) or `is None`
  (allowed) per the PRD's exit-code table (exit 2 ⇒ `is not None`, exit 0
  ⇒ `is None`).
- Phase 1 acceptance: the full existing suite
  (`test_guard_phase_delegation.py`, `..._corpus.py`, `..._replay.py`,
  `..._scratch_replay.py`) plus the new Phase 0 tests, all green;
  `python3 dev/bin/replay_delegation_guard.py` exits 0, summary `refused 1`
  (the 00307-pinned corpus contract, unchanged by this PRD).
- No new test *files*; all additions land in the three files the PRD
  names, keeping the module boundary the same tests already define.

## Review log

- non-blocker (dispatch 1): the design drops `·` from the
  `_CITE_SENTENCE_BOUNDARY` extension the PRD's Solution text names,
  reasoning that no payload exercises it. Recorded, not fixed — none of
  the five required payloads need it, and adding an untested terminator
  would be unverifiable scope creep against the PRD's own acceptance
  criteria (which pin only the five payload groups + corpus + budget).
- question (dispatch 1): confirmed resolved by the backtick run-length
  tokenization rewrite above — backtick runs are now tokenized by one
  regex before merging into `_order`, so "run length" is explicit in the
  algorithm rather than implied by a single-character scan.
- dispatch 1 (claude): cardinal-sin 0, blocker 2, non-blocker 1, question 1
- non-blocker (dispatch 2): the linearity section doesn't name an explicit
  remedy path if the `_FOLLOW`-per-candidate cost measures over budget
  under the new code. Recorded, not fixed at design time — Phase 0's
  `test_dense_skill_md_mentions_stay_under_budget` is the gate; the
  Interfaces section already says task 1 of Phase 1 is scoped to keep
  `_nested_runs` linear if that test goes red, which is the concrete
  remedy path (adding a once-per-field `_FOLLOW` cache is the fallback if
  measurement shows the existing bound insufficient, not a step to take
  unconditionally).
- question (dispatch 2): resolved by the `None`-sentinel fix above — an
  opener at offset 0 is no longer missed.
- dispatch 2 (codex): cardinal-sin 0, blocker 1, non-blocker 1, question 1
- dispatch 3 (codex): confirmed both dispatch-2 findings fixed (the
  `open_at <= start` widening + `None`-sentinel fixes), traced payload
  (4) and a normal backtick own-wrapper citation to the correct exit
  codes, then found one new blocker: the revised `_cited` own-wrapper
  check dropped the sentence-window bound (`sentence_start`/
  `sentence_end`), which would let a run crossing a sentence boundary
  wrongly cite a name. Fixed above — the own-wrapper and strict-
  enclosure cases now both require the same sentence-window bound the
  existing final `runs.get(...)` test already applies.
- engagement re-run (dispatch 3, quality retry, does not consume the
  3-dispatch ceiling): the re-run prompt relied on codex re-reading repo
  files rather than inlined content, and its sandbox's local readers
  failed (`sandbox-exec: sandbox_apply: Operation not permitted`), so it
  returned no findings and no "checked-correct" confirmations — it could
  not show engagement. Marked WEAK per the minimum-engagement check;
  advisory only. The substantive dispatch-3 pass immediately prior (fully
  inlined, no file reads) DID engage: it traced two concrete payloads
  through the revised mechanism to specific exit codes and found a real
  defect (the sentence-window drop), which is itself section-anchored
  evidence of engagement even though the finding count was 1.
- dispatch 3 (codex): cardinal-sin 0, blocker 1, non-blocker 0, question 0 weak
