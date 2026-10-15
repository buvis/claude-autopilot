# Rework design: 00307 guard citations and replay contract (cycle 1)

Source review: docs/dev/project-management/reviews/00307-guard-citations-and-replay-contract-v1-review-1.md (head_sha f7e282223f55f8a891a5733f61f6715f21b06d93)

## Architecture fit

Prior fix: none - there was no prior rework fix.

This is cycle 1 of PRD 00307's review loop, so every CRITICAL below was
introduced by the PRD's own first implementation (work range
`82b0cd561b7edb38ec8063cf402ba9941cd75302..f7e282223f55f8a891a5733f61f6715f21b06d93`,
78 changed lines in `hooks/guard_phase_delegation.py`, 143 new lines in
`hooks/test_guard_phase_delegation_citations.py`, 5 in
`dev/bin/replay_delegation_guard.py`), not exposed by an earlier rework.

The work lands entirely in the PreToolUse delegation guard
(`hooks/guard_phase_delegation.py`), its test suite, and the replay harness
that measures it against the recorded transcript corpus. No other layer is
touched: the guard is a leaf module read by `hooks/hooks.json` and by
`dev/bin/replay_delegation_guard.py`, and both consume it through
`find_phase_delegation()` / `is_phase_delegation()`, whose signatures do not
change.

The three CRITICAL rows this design closes:

- **R1 / R4** (one defect, two framings): the corpus replay exits 1 with
  `per-task 755 refused 3`, where the PRD requires exit 0 with `refused 1`.
  Two non-pinned ids are still refused - `toolu_011UqbqFtUDPuSeCiLLgMvEg` and
  `toolu_013ePUKbLDE7DLnbnGmgszzR`.
- **R2**: `test_six_corpus_dispatches_are_allowed` is built on invented
  prompts, so it is green while the real corpus is red. The mechanical
  fail-first replay confirms it independently (review row R16: 13 of the new
  citation tests pass against the pre-change code).

### Root cause (measured, not inferred)

`_SENTENCE_BOUNDARY` is `re.compile(r"[.!?\n]")` - a bare `.` with no
right-context condition (`hooks/guard_phase_delegation.py:222`). `_cited`
bounds its close search at `sentence_end` and its asymmetric-opener search at
`sentence_start` (`:560-572`). So any `.` between the wrapper and the phase
name truncates the window the citation rule needs:

- `toolu_011Uqb`: the payload reads ``Every case uses the one prompt `Run the
  work phase for PRD 00300.` (verbatim, including the period).`` The closing
  backtick sits *after* the `.`, so `text.find("`", end, sentence_end)` returns
  -1 and the run is never seen to close.
- `toolu_013ePU`: the payload reads `a downstream PRD parser
  (cli/frontmatter.parse and plan-tasks) looks for these exact markdown
  patterns.` The `.` inside the dotted identifier `frontmatter.parse` is a
  sentence boundary between the `(` and the name, so
  `text.rfind("(", sentence_start, start)` returns -1 and the opener is never
  seen.

Both are the same bug: a `.` that is not an English sentence terminator is
treated as one.

## Module placement

| Change | File | New or edit |
|---|---|---|
| `_CITE_SENTENCE_BOUNDARY` constant | `hooks/guard_phase_delegation.py` | new symbol in existing file |
| `_cite_sentences` returned by `_boundaries` | `hooks/guard_phase_delegation.py` | edit |
| `_cited` call site uses `_cite_sentences` | `hooks/guard_phase_delegation.py` (`_field_delegation`) | edit |
| `_WRAP_SCAN_PAIRS` module constant | `hooks/guard_phase_delegation.py` | new symbol in existing file |
| `_ordered_to_follow` sentence lookup via `bisect_left` | `hooks/guard_phase_delegation.py` | edit |
| Corpus test rebuilt on the real recorded payloads | `hooks/test_guard_phase_delegation_citations.py` | edit |
| Boundary regression tests | `hooks/test_guard_phase_delegation_citations.py` | edit (new test functions) |

No new file is created. No file is deleted.

## Interfaces & contracts

This section is the sole contract source for this cycle's CRITICAL fix tasks.
Copy it verbatim.

### 1. `_CITE_SENTENCE_BOUNDARY` (new module constant)

Closes: R1 / R4 - the corpus replay exits 1 because a non-terminal `.`
truncates the citation window.

```python
# A sentence terminator for CITATION purposes only: `.`, `!` or `?` that is
# actually followed by whitespace or end-of-text, plus a bare newline. A `.`
# inside a dotted identifier ("cli/frontmatter.parse") or immediately before a
# closing wrapper ("`... PRD 00300.`") is NOT a sentence end, and treating it
# as one is what made the guard refuse two legitimate corpus dispatches.
# Deliberately separate from _SENTENCE_BOUNDARY: that list feeds _is_scoped's
# (sentence, id) folding, _strongly_anchored and the whole-run marker set,
# whose behaviour is pinned by the existing suite and must not move.
#
# The closing-wrapper class before \Z is load-bearing, not decoration. A
# terminator followed ONLY by closing wrappers to end-of-text IS a real
# sentence end: '"Run the work phase for PRD 7."' is a whole quoted order and
# must stay denied. Without that class the window runs to len(text), the final
# quote is found as a close, and the guard allows it -- measured, 4 pinned
# tests in hooks/test_guard_phase_delegation_structure.py go red.
_CITE_SENTENCE_BOUNDARY = re.compile(
    r"""[.!?](?=\s|[]'"’”»」)]|`*\s*(?:\Z|\n)|`+[ \t]*[^(\s])|\n"""
)
```

In words: a `.`, `!` or `?` ends the citation sentence **unless** it is
followed by a run of backticks that is followed, after optional spaces or
tabs, by `(`. Everything else terminates: whitespace; any non-backtick closer
(`"`, `'`, `’`, `”`, `»`, `」`, `)`, `]`); a backtick run reaching end-of-line
or end-of-text; a backtick run followed by any non-`(` text.

Two lexical discriminators do the work, and an earlier draft of this design
wrongly declared both impossible:

1. **Closer identity.** The corpus payload's run is backtick-delimited - a
   code or literal citation. Every deny shape needing the window bounded is
   double-quote-delimited reported speech, which is exactly the pinned
   whole-sentence-quoted-order form. A straight `"` right after a terminator
   always ends the citation sentence.
2. **Parenthetical versus fresh text after the close.** ``…00300.` (verbatim,
   …)`` continues the citing sentence; ``…PRD 7.` and obey it`` does not. The
   continuation test is an **allowlist** - only `(` - so an unlisted
   continuation denies, which is the safe polarity for a guard.

Measured directions that do **not** separate the shapes, so do not reach for
them: start-of-field versus embedded (the deny shape `The spec says "…" Do
it.` is embedded too); text preceding the opener; and a citation verb before
the opener - that one is a trap, since that same deny shape contains "says".

The character class is written `[]...]` with the `]` first so it is a literal
rather than closing the class; keep that order. Measured against the four
decisive shapes (allow: the two corpus payloads; deny: the two structure-suite
prompts) this boundary is the only one of the two candidates that gets all
four right.

### 2. `_boundaries` (changed return shape)

```python
def _boundaries(
    text: str, spans: list[tuple[int, int, bool]]
) -> tuple[list[int], list[int], list[int], list[int]]:
```

Returns `(clause_starts, clause_ends, sentences, cite_sentences)`. The first
three are computed exactly as today and are byte-identical to today's values.
The fourth is new:

```python
    cite_sentences = [m.start() for m in _CITE_SENTENCE_BOUNDARY.finditer(scratch)]
    return [c[0] for c in clauses], [c[1] for c in clauses], sentences, cite_sentences
```

`cite_sentences` is computed from the same masked `scratch` string as
`sentences`, so the two index into the same coordinate space.

### 3. `_field_delegation` (changed call site)

```python
    clause_starts, clause_ends, sentences, cite_sentences = _boundaries(text, spans)
```

and, inside the `else:` branch that computes the citation window, the four
lines that currently read `sentences` become:

```python
            head = bisect_left(cite_sentences, start)
            sentence_start = cite_sentences[head - 1] + 1 if head else 0
            tail = bisect_left(cite_sentences, end)
            sentence_end = (
                cite_sentences[tail] if tail < len(cite_sentences) else len(text)
            )
```

Every other use of `sentences` in `_field_delegation` (`marked`, `_is_scoped`,
`_strongly_anchored`, `_ordered_to_follow`) keeps reading `sentences`
unchanged.

### 4. `_WRAP_SCAN_PAIRS` (new module constant)

Closes: review row R14 (🟡) - the wrapper tuple is rebuilt on every `_cited`
call.

```python
# Hoisted out of _cited: the pair list is fixed, and rebuilding it per
# candidate is pure overhead on a hot path. The straight single quote is
# deliberately absent even though it appears in _WRAP_OPEN - contractions and
# possessives ("don't run plan-tasks") would read as an open quote and excuse
# a real order. _WRAP_OPEN governs what the span matcher may absorb as the
# name's own wrapper; this tuple governs what may open a citation run around
# it, and the two are not the same question.
_WRAP_SCAN_PAIRS = (*_WRAP_PAIR.items(), ("`", "`"), ('"', '"'))
```

`_cited`'s loop header becomes `for opener, closer in _WRAP_SCAN_PAIRS:`. No
other line of `_cited` changes: its signature, its parity rule and its
asymmetric-opener rule all stay as they are. The fix is in the window it is
given, not in the rule it applies.

### 5. `_ordered_to_follow` (changed sentence lookup)

Closes: review row R3 (🟡, 2/4) - the PRD must-have "`_ordered_to_follow` uses
`bisect_left` on `sentences`" is unmet; the line is still a linear scan.

The line currently at `hooks/guard_phase_delegation.py:529`:

```python
    sentence_end = next((s for s in sentences if s >= end), len(text))
```

becomes:

```python
    sentence_index = bisect_left(sentences, end)
    sentence_end = (
        sentences[sentence_index] if sentence_index < len(sentences) else len(text)
    )
```

Named `sentence_index`, not `index`: three lines below, the existing
`index = bisect_left(clause_starts, verb_start)` is a different binary search,
and two of them sharing one name in a nine-line function invites a later edit
to reorder them into a bug.

`bisect_left(sentences, end)` returns the first index whose value is `>= end`,
which is exactly what the generator expression computed, so this is
behaviour-identical and `hooks/test_guard_phase_delegation_linearity.py` and
`hooks/test_guard_phase_delegation_structure.py` keep passing unchanged.

### 6. `_CORPUS` rebuilt on the real payloads

Closes: R2 - the corpus test uses invented prompts and cannot fail.

`test_six_corpus_dispatches_are_allowed` in
`hooks/test_guard_phase_delegation_citations.py` must drive the **six recorded
payloads, recovered verbatim by tool-use id**, not synthetic sentences built
around the quoted span.

**The single source is the transcript corpus, not stub 00294.** Hold stub
00294 (`docs/dev/project-management/prds/done/00294-triage-the-replay-found-six-legitimate-per-task-v1.md:18`)
quotes only the 30-character spans the guard reported; it reproduces no
prompt. Recover each payload from
`~/.claude/projects/-Users-bob-git-src-github-com-buvis-claude-autopilot/**/*.jsonl`
by its tool-use id, using the same extraction `dev/bin/replay_delegation_guard.py`
performs in `_dispatches`. **Reconstructing a prompt around a 30-character
span is forbidden** — that is precisely the R2 defect being fixed here. If a
payload cannot be recovered by its id, report it as a blocker; do not
synthesize one.

**Match the record, not the text.** A grep for the id hits far more than the
dispatch: measured, `toolu_011UqbqFtUDPuSeCiLLgMvEg` appears in 31 files under
that tree and `toolu_013ePUKbLDE7DLnbnGmgszzR` in 26 — original dispatch,
review transcripts, subagent logs, and `tool-results/*.txt` that merely discuss
the id, this PRD's own review sessions included. Landing on a reviewer quoting
the span is the R2 failure mode in a new hat. The payload is the `tool_input`
of the assistant record whose **own `id` field** equals the tool-use id and
whose `name` is `Agent`; a record that merely contains the id as text is not a
source. The recovered strings are inlined into `_RECORDED_CORPUS` as literals,
so the test has no runtime dependency on `~/.claude`.

**Only two of the six payloads still exist. Build the fixture from those two.**
Measured 2026-10-15, twice and independently, running exactly
`dev/bin/replay_delegation_guard.py:_dispatches`'s extraction over every
`*.jsonl` under `~/.claude/projects` (not just this repo's tree):

| id | `Agent` tool_use records | any tool_use records |
|---|---|---|
| `toolu_011UqbqFtUDPuSeCiLLgMvEg` | 1 | 1 |
| `toolu_013ePUKbLDE7DLnbnGmgszzR` | 1 | 1 |
| `toolu_015DM18ubZLJZbA65ozvuw8c` | **0** | 0 |
| `toolu_013NAWvgMnP4WatpZDVyiNAa` | **0** | 0 |
| `toolu_01DAQSaS3uAph2VZnfn5NC9d` | **0** | 0 |
| `toolu_019nCz3WRsAZSwdaHb9itXiT` | **0** | 0 |

The four zero-rows survive only as quoted text in later sessions, which is
exactly the contamination the record-matching rule above rejects. Why they are
gone was not determined - transcript rotation, a sidechain-only dispatch, or
ids mis-transcribed into stub 00294 at the time.

So the fixture target is **every payload recoverable by id**, not "six". Land
it with the two that exist. That costs nothing in rigour: those two are
precisely the ids that are red before the fix and green after, so the
fail-first property contract 6 exists to restore is fully preserved. Record
the four unrecoverable ids in the test file as a comment carrying this
measurement, so a later reader does not re-run the search. **The rule against
synthesis is unchanged and absolute** - do not invent a prompt for a missing
id.

The six ids, for the record:

| # | tool-use id | subagent_type | span the guard quoted |
|---|---|---|---|
| 1 | `toolu_015DM18ubZLJZbA65ozvuw8c` | (none) | ``e-invokes `/autopilot:work`, w`` |
| 2 | `toolu_013NAWvgMnP4WatpZDVyiNAa` | general-purpose | ``d reports `design-solution: <p`` |
| 3 | `toolu_01DAQSaS3uAph2VZnfn5NC9d` | general-purpose | `.assertIn("design-solution: <p` |
| 4 | `toolu_019nCz3WRsAZSwdaHb9itXiT` | general-purpose | ``ine reads `design-solution: <p`` |
| 5 | `toolu_013ePUKbLDE7DLnbnGmgszzR` | general-purpose | `parse and plan-tasks) looks fo` |
| 6 | `toolu_011UqbqFtUDPuSeCiLLgMvEg` | autopilot:worker-opus | ``​`Run the work phase for PRD 0`` |

Five of the six depend on `per_task` being false (the historical dispatch used
`general-purpose` or no type), so the test must preserve each payload's real
`subagent_type`, not just its prompt.

Name the fixture `_RECORDED_CORPUS`, carrying `(tool_use_id, tool_input)`
pairs — **not** `_CORPUS`: `hooks/test_guard_phase_delegation_structure.py:580`
already has an unrelated `_CORPUS` of a different shape, and the citations
suite's current `_CORPUS` is a third shape again.

```python
_RECORDED_CORPUS = (
    (
        "toolu_011UqbqFtUDPuSeCiLLgMvEg",
        {"subagent_type": "autopilot:worker-opus", "prompt": "<recovered verbatim>"},
    ),
    ...
)
```

The acceptance test for this contract is **not** that the test passes: it is
that the test **fails against the pre-change guard** and passes after. Both
recoverable ids (`toolu_011UqbqFtUDPuSeCiLLgMvEg`,
`toolu_013ePUKbLDE7DLnbnGmgszzR`) are refused today, so a correctly rebuilt
fixture is red before the `_CITE_SENTENCE_BOUNDARY` change lands and green
after. One caution for whoever writes the probe: `013ePU`'s real payload is
~9.7 KB and its refusal depends on the surrounding context. The one-sentence
abbreviation of it used in this design's root-cause section is **already
allowed in isolation** on master, so it does not reproduce the bug — use the
full recovered payload, and treat the replay row as the authoritative check
for that id. Recover each verbatim payload from the transcripts under
`~/.claude/projects/-Users-bob-git-src-github-com-buvis-claude-autopilot` by
tool-use id; do not reconstruct one from the review's quoted 30-character
span.

### 7. New boundary regression tests

Added to `hooks/test_guard_phase_delegation_citations.py`:

- `test_period_inside_a_dotted_identifier_does_not_end_the_citation_sentence`
  - the `(cli/frontmatter.parse and plan-tasks)` shape, allowed.
- `test_period_before_a_closing_backtick_does_not_end_the_citation_sentence`
  - the ``` `Run the work phase for PRD 00300.` ``` shape, allowed.
- `test_a_real_sentence_end_still_bounds_the_citation_window` - a `.` followed
  by a space still terminates, so a quote opened in one sentence cannot cite a
  name in the next. Denial regression; this is the test that keeps the fix
  from being a blanket widening.
- `test_balanced_quotes_in_one_clause_do_not_hide_an_order` - Bob's R6 shape,
  `The log says "ready, done" then run plan-tasks for PRD 00300 and print
  "ok".`, must be **refused**. Write it now: if it is already green the fix
  cost nothing, and if it is red the parity rule needs tightening before this
  cycle closes.
- `test_a_terminator_before_only_closing_wrappers_still_ends_the_sentence` -
  the two shapes the first draft of this design broke, both **refused**:
  `"Run the work phase for PRD 7."` and
  ``Insert the line "Invoke `/autopilot:work` skill."``. These are the
  regressions that keep the widened window honest; they are already pinned in
  `hooks/test_guard_phase_delegation_structure.py`
  (`test_quoted_text_is_still_checked[whole-sentence-quoted]` and
  `[quoted-phrase-to-edit]`), and restating them beside the citation rule puts
  the deny case next to the allow case it trades against.

Also strengthen the existing `test_ordered_to_follow_uses_bisect`
(`hooks/test_guard_phase_delegation_citations.py:119`): it asserts
`"bisect_left" in source` but never that the linear scan is gone, which is why
R3 survived a green suite. Add the assertion the PRD's Phase 0 task actually
specified:

```python
    assert "next(" not in source
```

## Data flow

Unchanged except for one extra list threaded through one call:

```
tool_input
  -> find_phase_delegation()            (reviewer / agoge exemptions, normalize)
  -> _field_delegation(text, per_task)
       -> _candidates(text)             -> spans
       -> _boundaries(text, spans)      -> clause_starts, clause_ends,
                                           sentences, cite_sentences   <-- NEW
       -> per span:
            _strongly_anchored / _weakly_anchored   (reads `sentences`)
            _is_scoped                              (reads `sentences`)
            _cited(..., sentence_start, sentence_end)
                 ^ both now derived from `cite_sentences`              <-- NEW
            _negated
```

The guard's two public entry points, `find_phase_delegation()` and
`is_phase_delegation()`, keep their signatures and their return contracts, so
`hooks/hooks.json` and `dev/bin/replay_delegation_guard.py` need no change.

## Reuse inventory

- `bisect_left` (`hooks/guard_phase_delegation.py:26`, already imported) - used
  for every other boundary lookup in this module (`:484`, `:499`, `:534`,
  `:598`, `:603`, `:609`, `:627`, `:629`). Contract 5 brings the one remaining
  linear scan onto it. Nothing new is imported.
- `_boundaries`'s existing masked-`scratch` construction (`:415-450`) - the new
  `cite_sentences` list reuses that same masked string, so the two boundary
  lists share one coordinate space for free. No second masking pass.
- `re` module-level compiled patterns - the file already compiles 20+ patterns
  at import; `_CITE_SENTENCE_BOUNDARY` follows that established shape rather
  than compiling per call.
- Greps run for an existing helper before designing the new constant:
  `rg -n 'def _' hooks/guard_phase_delegation.py` filtered for
  `sentence|boundar|wrap|cite|mask|word` returned only `_words_before`,
  `_boundaries`, `_is_scoped` and `_cited` - **nothing found** that already
  computes a wrap-aware or whitespace-anchored sentence boundary, so the
  constant is genuinely new. `rg -n '_SENTENCE_BOUNDARY|_WRAP_PAIR'` confirmed
  the single definition site and its three readers.
- `~/.claude/rules-library/rationalizations.md` was not consulted for synonym
  sets this round; the sweep used the verb/noun pairs above directly. Stated
  rather than silently skipped.

## Alternatives considered

**A. Narrow `_SENTENCE_BOUNDARY` itself** (smallest diff - one regex, no new
constant, no signature change). Rejected. `sentences` feeds `_is_scoped`'s
`(sentence, id)` folding, whose docstring explicitly leans on a path's own `.`
splitting `"a/b.py and a/b.py"` into two sentences (`:467-469`), plus
`_strongly_anchored` and the whole-run marker set. Changing it moves behaviour
under 564 pinned tests to fix a bug in one caller. The extra size of the chosen
design - one constant, one list, one widened return tuple - buys a guarantee
that the three other readers are byte-identical, which is the difference
between a fix and a second regression.

**B. Replace `_cited`'s heuristics with a real balanced-run scanner** -
precompute every wrapped run in the field once, then test enclosure. This is
the architecturally cleanest answer and would also retire Bob's R7 (quadratic
rescanning) and Alice's R9 (contract drift) outright. Rejected **for this
cycle**: whole-field pairing is strictly more fail-open than the current
clause-scoped parity, and the review already carries two separate findings
(R6, R11) warning that the citation rule's fail-open surface is
under-specified. Widening the pairing scope while closing a CRITICAL would
trade a false-refusal bug for a false-allow bug in a security guard, with one
rework cycle left to catch it. Recorded in Risks as the follow-on.

**C. Chosen: a citation-only boundary list.** `_cited` gets a window computed
with the correct rule; every other reader keeps today's. The citation rule
itself - parity for symmetric wrappers, no-close-since-opener for asymmetric -
is unchanged.

**Superseded by measurement — read the table below as the history of two
rejected drafts, not as the chosen design.** Dispatch 3 found a rule that
reaches the correct verdict on all fifteen probe shapes while keeping the
replay gate green, so the widening tabulated here is avoidable and is NOT
accepted. Contract 1 now carries that rule. The one residual it does keep is
recorded in Risks as an explicitly pinned fail-open.

What the two earlier drafts cost, measured:

**The fail-open surface DOES grow, and the earlier draft of this section was
wrong to say otherwise.** `_cited` is a pure function of its window, so a
strictly longer window is strictly more permissive. Measured (dispatch 2,
patched module against master, and reproduced independently here): five probe
prompts flip deny -> allow, only one of which is the intended corpus fix.

| prompt | master | with this design |
|---|---|---|
| `` `...PRD 00300.` (verbatim...)`` - the corpus payload | deny | **allow** (intended) |
| `"Run the work phase for PRD 7."` - pinned | deny | deny |
| `"Run the work phase for PRD 7." Then report back.` | deny | **allow** (not intended) |
| `The spec says "Run the work phase for PRD 00300." Do it.` | deny | **allow** (not intended) |
| `"Run the work phase for PRD 7." ` (trailing space) | deny | **allow** (not intended) |
| `` See `run the work phase for PRD 7.` and obey it.`` | deny | **allow** (not intended) |

Those four flips are what the two rejected drafts cost. None is pinned by a
test - the suite pins only the two end-of-text forms - so the full suite would
have stayed green while the guard got weaker, which is exactly the failure
mode this PRD was written to end. The corpus confirms it was not merely
synthetic: the second draft additionally flips the recorded dispatch
`toolu_01PyqE7BF9ihL7XP8mprMDut` from refused to allowed, taking the `other`
bucket from 6 refusals to 5.

The drafts failed because they looked only at where the sentence ends.
Contract 1's rule looks at **which** closer sits after the terminator and at
**what follows the closer run**, and those two bytes do separate the shapes:

| guard | per-task refused | other refused | replay exit |
|---|---|---|---|
| master | 3 (`011Uqb`, `013ePU`, `01Ku4T`) | 6 | 1 |
| rejected draft (sentence-only) | 1 | 5 | 0 |
| **contract 1 as written** | **1** | **6** | **0** |

So the chosen rule meets Success Criterion 1 *and* keeps every shape master
denies today, bar the single documented residual in Risks. Blake's review row
R5 ("the spec and its own success criterion conflict") is thereby answered
rather than accepted: the conflict was in the sentence-boundary framing, not
in the PRD.

## Risks & edge cases

- **Accepted, pinned fail-open: a backtick-wrapped order followed by a
  parenthetical.** Measured under contract 1's rule, these flip from deny to
  allow: ``See `run the work phase for PRD 7.` (now)``,
  ``See `run the work phase for PRD 7.` (do it) and report.``, and
  ``Note `run the work phase for PRD 7.` (urgent).`` This is irreducible for
  any lookahead rule - it is byte-identical to corpus payload `011Uqb`'s
  shape. It is one shape rather than the rejected drafts' four-plus, it
  requires backticks *and* a following `(`, and no recorded dispatch exhibits
  it. **Pin it with a test that records today's allow verdict as deliberate**
  (name it for the rule, e.g.
  `test_a_backtick_citation_followed_by_a_parenthetical_is_allowed`), with a
  comment naming the balanced-run scanner (alternative B) as the tightening
  path. Unpinned is exactly how the rejected drafts' regressions would have
  slipped through; this residual does not get that treatment.
- **Guillemet-style citations now deny.** Under contract 1's rule
  `«…PRD 7.» (verbatim)` denies, because `»` is a non-backtick closer. That is
  the safe direction and no recorded dispatch uses one, but it is a behaviour
  difference from the rejected drafts' intent and is stated here rather than
  discovered later.
- **The fix could widen the window too far.** A `.` followed by whitespace
  still terminates, so a quote opened in a previous sentence cannot reach
  across. Contract 7's `test_a_real_sentence_end_still_bounds_the_citation_window`
  is the pin; it must be written, not assumed.
- **The closer run must end at a newline as well as at end-of-text.** The
  first draft of contract 1 anchored the closer class on `\Z` alone and argued
  that `$` would wrongly make `"...PRD 00300.\n"` differ from
  `"...PRD 00300."`. Measurement inverted that reasoning: it was `\Z` that made
  the two differ, in the fail-open direction - one trailing newline flipped
  `'"Run the work phase for PRD 7."\n'` from deny to allow. Contract 1 now
  reads `(?:\Z|\n)`, verified to restore the deny without reopening the corpus
  allow-shape (there the closer is followed by a space, not `\Z`/`\n`). The
  standalone `|\n` alternative stays: it handles a bare newline with no
  terminator before it.
- **The defect reproduced itself during this very review.** Dispatch 3's
  prompt quoted probes A-H as test data and `hooks/guard_phase_delegation.py`
  refused the Agent call outright ("autopilot: run the phase skill ... with the
  Skill tool in THIS session"). The dispatch only went through after the
  payloads were moved into `docs/dev/tmp/00307-dispatch3-probes.md` and
  referenced by path. That is the false-refusal class this PRD exists to close,
  observed live on a reviewer dispatch rather than in the recorded corpus - and
  it is a seventh real-world instance beyond the six in stub 00294. Worth
  adding to the corpus when the rule is settled.
- **Recovering the six verbatim payloads is the task's real risk.** The review
  found the previous attempt invented them. If a payload cannot be recovered
  from the transcripts by its tool-use id, that is a blocker to report, not a
  licence to synthesize a prompt that contains the span.
- **Likely next changes after this PRD**, and whether this design boxes them
  in: (1) alternative B's balanced-run scanner - this design does not box it
  in, since `_cited`'s signature is untouched and `cite_sentences` would simply
  become unused; (2) tightening the symmetric-wrapper parity rule for R6 -
  independent of this change, same function, no conflict; (3) adding `'` to the
  citation wrapper set - deliberately refused here and documented in
  `_WRAP_SCAN_PAIRS`'s comment, so a future change has the reason in front of
  it rather than having to rediscover the contraction problem.
- **`_WRAP_OPEN` contains `'` while `_WRAP_SCAN_PAIRS` does not.** Bob read
  this as a contract violation (review row R12). It is deliberate and now
  carries its reason in the code; the two constants answer different questions.
  If a later cycle disagrees, the comment is the thing to argue with.

## Test strategy outline

1. **Fail-first is mandatory here** - the whole CRITICAL is that the previous
   tests could not fail. Rebuild `_CORPUS` from the real payloads, run it
   against the current guard, and confirm the two known ids are red *before*
   touching `_CITE_SENTENCE_BOUNDARY`.
2. Add the four boundary regressions of contract 7, two allow-shapes and two
   deny-shapes. The deny-shapes are what prove the fix is a correction and not
   a widening.
3. Apply contracts 1-3, re-run
   `uv run --no-project --with pytest python -m pytest -q hooks/test_guard_phase_delegation_citations.py`
   - the two corpus ids and the two new allow-shapes go green, the two
   deny-shapes stay green.
4. Apply contracts 4-5, then run the full guard suite with no test removed:
   `uv run --no-project --with pytest python -m pytest -q hooks/test_guard_phase_delegation_citations.py hooks/test_guard_phase_delegation_structure.py hooks/test_guard_phase_delegation_linearity.py hooks/test_guard_phase_delegation_narrowing.py hooks/test_guard_phase_delegation_replay.py hooks/test_guard_phase_delegation.py hooks/test_guard_phase_delegation_dispatch.py`.
5. **The acceptance gate for the cycle**: `python3 dev/bin/replay_delegation_guard.py`
   exits 0 with its per-task line reading `refused 1`. This is the PRD's own
   Success Criterion 1 and the queued verification check in
   `docs/dev/project-management/reviews/00307-guard-citations-and-replay-contract-v1-checks-1.json`.
   Treat `per-task ... refused 1` literally: if the four `PINNED_DENY` ids do
   not in fact dedupe to one group, report the discrepancy rather than
   loosening the check.
6. Full gate: `dev/bin/release-checks` green (baseline this cycle:
   `PASS 6715 FAIL 0 SKIP 34`).

## Review log

dispatch 1 (claude): cardinal-sin 0, blocker 2, non-blocker 3, question 1

Both blockers fixed in the doc:

- **B1** - contract 1's first regex `[.!?](?=\s|\Z)|\n` traded the CRITICAL
  false-refusal for a false-allow: a terminator followed only by closing
  wrappers to end-of-text did not fire, so `sentence_end` ran to `len(text)`
  and a whole-sentence-quoted order (`"Run the work phase for PRD 7."`) was
  read as a citation. Measured by the reviewer against a patched copy: 4 pinned
  tests in `hooks/test_guard_phase_delegation_structure.py` went red. Fixed by
  the closing-wrapper class now in contract 1; independently re-verified here
  against all four decisive shapes before accepting it.
- **B2** - contract 6 named hold stub 00294 as the verbatim source of the six
  prompts, but that file quotes only the 30-character spans. Confirmed at
  `docs/dev/project-management/prds/done/00294-triage-the-replay-found-six-legitimate-per-task-v1.md:18`.
  Contract 6 now names the transcript corpus as the sole source, lists all six
  ids with their `subagent_type`, and forbids reconstruction from the span.

Non-blockers and the question, recorded and deliberately not fixed:

- **NB1** (stale count) - the design quotes `per-task 755 refused 3` from the
  review; the reviewer measured `748 refused 3` the same day. The corpus
  denominator grows with every session, so the absolute figure drifts by
  design. The literal gate stays `exit 0` + `per-task ... refused 1`, which is
  denominator-free; the 755/748 figures are measurements, stamped by the
  session that took them, not acceptance text.
- **NB2** (two refusals outside the gate) - `other toolu_01F71bwTZ8FNSnRRt2rDxZiQ`
  and `other toolu_01XXaGFHXr8bcUMcQpBv5wpz` are refused for the same
  quoted-citation reason but sit in the `other` bucket, which
  `dev/bin/replay_delegation_guard.py:168` never fails on. Real, and outside
  this PRD's stated scope: its Must-haves name the six stub-00294 ids and the
  four pinned ids, not the `other` bucket. Worth a follow-up PRD rather than a
  scope widening in a rework cycle with one cap left.
- **NB3** (`_boundaries` docstring) - the docstring at
  `hooks/guard_phase_delegation.py:418-436` describes a 3-tuple. Cosmetic
  relative to the CRITICALs; the implementor updating the signature will see
  it directly above the line being changed.
- **Q1** (`_CORPUS` name collision across suites) - resolved while fixing B2
  rather than deferred: contract 6 now names the fixture `_RECORDED_CORPUS`
  and says why.

Verified correct by the reviewer and not changed: the root-cause analysis for
both payloads; that the four `PINNED_DENY` ids dedupe to one per-task group, so
`refused 1` is literally reachable; that `sentences` stays byte-identical for
its three other readers; that `_boundaries` has exactly one caller; that
contract 5's `bisect_left` swap is behaviour-identical; that contract 4 is a
pure hoist; and every line-number citation in the doc.

dispatch 2 (claude-fallback): cardinal-sin 0, blocker 2, non-blocker 2, question 1

Dispatch 2 ran as a Claude fallback: the codex dispatch returned its own
prompt plus hook noise and no findings (67 KB, zero `severity:` lines in the
body), which is a codex outage under the skill's fallback rule.

- **B3** - the dispatch-1 fix only held when the quoted order ended the
  prompt. Measured: append any text, or one trailing space, and four shapes
  that deny on master flip to allow. Not fixed by patching the boundary; the
  whole sentence-only framing was wrong, and dispatch 3 replaced it.
- **B4** - a single trailing newline defeated the closer class, and this
  design's own Risks bullet had argued for `\Z` on reasoning the measurement
  inverted. The bullet is rewritten and contract 1's rule covers the case.
- Non-blockers fixed in place: the false "the fail-open surface does not
  grow" claim (now a measured table), and contract 6's under-specified
  recovery procedure (now a record-matching rule, after measuring that the id
  appears as text in 25-31 files apiece). Question on `index` shadowing fixed
  by the `sentence_index` rename in contract 5.

dispatch 3 (claude): cardinal-sin 0, blocker 2, non-blocker 4, question 1

Dispatch 3 was asked to break the two-reviewer consensus that no boundary rule
could separate the shapes, and did, with measurements rather than argument.

- **B5** - the impossibility claim was false. A rule keying on closer identity
  and on what follows the closer run reaches the correct verdict on all 15
  probe shapes, keeps 445 guard tests green, holds the replay at exit 0
  `per-task 748 refused 1`, and - unlike both rejected drafts - keeps the
  recorded dispatch `toolu_01PyqE7BF9ihL7XP8mprMDut` refused. Contract 1 now
  carries that rule; contracts 2-5 were unaffected and are unchanged.
- **B6** - contract 6 was unbuildable: four of its six ids have no `tool_use`
  record anywhere under `~/.claude/projects`. **Independently re-measured here
  before accepting**, with the same result (2 recoverable, 4 at zero). The
  contract now targets the recoverable payloads and keeps the no-synthesis
  rule.
- Non-blockers: the probes file's abbreviated B string is already allowed in
  isolation and cannot discriminate (noted in contract 6); the residual
  backtick-plus-parenthetical fail-open is now an explicitly pinned Risks
  entry; the `(?:\Z|\n)` amendment and the contract 6 record-matching rule and
  contract 5 rename were each verified sound.
- Question (not decided, recorded): whether to narrow the `(`-continuation
  exemption with a citation-noun test. Deliberately not taken - the deny shape
  `The spec says "…" Do it.` proves a citation verb has no separating power,
  so it would be a second heuristic buying only part of one residual. The
  balanced-run scanner is the better follow-up.

Two claims I verified myself rather than taking on report, both confirmed:
contract 1's rule separates all seven decisive shapes at the boundary level,
and four of the six ids are genuinely unrecoverable.

Not verified by anyone: `dev/bin/release-checks` as a whole under contract 1's
rule. All seven guard suites are clean and the change is one regex, but the
full gate run belongs to the implementor (test strategy step 6).

result: ok
