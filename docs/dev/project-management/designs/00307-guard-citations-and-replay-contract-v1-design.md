# Design: Make the delegation guard ignore quoted citations and fix the replay exit contract

## Architecture fit

`hooks/guard_phase_delegation.py` is a two-pass predicate (`_candidates` then
`_boundaries`/`_field_delegation`) wired as a PreToolUse hook on `Agent` calls
(`hooks/hooks.json`), gated on `_AUTOPILOT_LOOP`. This PRD adds a third
anchoring input — "is this candidate inside a longer quoted/wrapped run?" —
to the existing per-candidate anchoring decision in `_field_delegation`, fixes
a floor bug in the existing negation check (`_negated`/`_ordered_to_follow`),
and replaces one exemption set (`_AGOGE_PREFIX`) with an enumerated roster.
None of this changes the hook's wiring, its fail-open contract, or its
O(field) cost model — every new check reuses the existing boundary tables
(`_boundaries`'s `clauses`/`sentences`) rather than adding a new scan.

`dev/bin/replay_delegation_guard.py` is a standalone read-only corpus replay
(no hook wiring); its `main()` exit-code policy is adjusted, `bucket()` is
unchanged.

## Module placement

- Edit `hooks/guard_phase_delegation.py`:
  - new module-level set `_AGOGE_PERSONAS` (replaces `_AGOGE_PREFIX`'s use at
    the exemption check; `_AGOGE_PREFIX` itself stays defined and used by
    `dev/bin/replay_delegation_guard.py`'s `bucket()` import, so it is not
    deleted)
  - new function `_cited(text, start, end, clause_start, clause_end) -> bool`
  - `_field_delegation`: one new `if _cited(...): continue` guard per
    candidate, before the existing strong/weak-anchor branch
  - `_ordered_to_follow`: compute the follow verb's own clause start and pass
    it to `_negated` instead of `end`
  - one new sentence in the fold's comment block (near `_normalize`'s
    docstring, where the Cyrillic-lookalike gap is already documented)
- Edit `dev/bin/replay_delegation_guard.py`: `main()`'s per-task/reviewer/agoge
  refusal check stays; add the pinned-id carve-out described below
- New test files:
  - `hooks/test_guard_phase_delegation_citations.py` (new file, Phase 0)
  - `dev/bin/test_replay_delegation_guard.py` gains one new test function
    (existing file; confirm it exists before assuming "new")
- Edit `hooks/test_guard_phase_delegation.py`:
  `test_allow_corpus_ignores_scratch_dispatch_files` rewritten to monkeypatch
  the corpus directory instead of writing into `tmp_path`. Today's test
  (`:98-110`) writes a scratch file into `tmp_path` and is vacuously true:
  `_allow_corpus()` (`:35-36`) globs a hardcoded `FIXTURES / "allowed"` path
  that never sees `tmp_path`, so the test cannot fail regardless of what it
  writes. The rewrite makes `FIXTURES` (or whatever path `_allow_corpus`
  reads) patchable: add `monkeypatch.setattr(module, "FIXTURES", tmp_path)`
  (or the equivalent for however the path is held — a module-level `Path`
  constant is the simplest shape and needs no production code change,
  since `FIXTURES` already exists as a test-module constant, not a function
  parameter) so the test can write BOTH the committed fixture files and a
  scratch dispatch file into the patched directory and assert the scratch
  file is excluded from what `_allow_corpus()` returns.
- Edit `dev/bin/release-checks`: add
  `hooks/test_guard_phase_delegation_citations.py` to the `[checks]` block
  listing the sibling `test_guard_phase_delegation_*` files (line ~138-144)
- Edit `CHANGELOG.md`: one `[Unreleased]` **Fixed** entry under a `**hooks**:`
  bullet

## Interfaces & contracts

### `_AGOGE_PERSONAS` (replaces the prefix test at the exemption site)

```python
_AGOGE_PERSONAS = frozenset({
    "agoge:olivia", "agoge:walter", "agoge:heidi", "agoge:judy",
    "agoge:wendy", "agoge:peggy", "agoge:trudy",
})
```

In `find_phase_delegation`, the exemption line

```python
subagent_type in _READ_ONLY_REVIEWERS or subagent_type.startswith(_AGOGE_PREFIX)
```

becomes

```python
subagent_type in _READ_ONLY_REVIEWERS or subagent_type in _AGOGE_PERSONAS
```

`_AGOGE_PREFIX = "agoge:"` stays defined (unused by the hook after this
change, but `dev/bin/replay_delegation_guard.py` imports it for `bucket()`'s
own `subagent_type.startswith(_AGOGE_PREFIX)` branch, which classifies for
reporting only and is out of scope here — it keeps classifying anything
spelled `agoge:*` as the `"agoge"` bucket, exempt or not).

### `_cited`

```python
def _cited(
    text: str, start: int, end: int, clause_start: int, clause_end: int
) -> bool:
    """True iff an unmatched wrapper from _WRAP_PAIR opens before `start` and
    its matching close character occurs at or after `end`, STRICTLY beyond a
    close consumed immediately after the name (that shape is handled by the
    existing _candidates span-extension and must still anchor as today).
    Searched within [clause_start, clause_end) only — a wrapper opened in an
    earlier clause never cites this one.  '(' is checked in addition to the
    curly-quote/guillemet/corner-bracket/square-bracket members of
    _WRAP_PAIR; a plain straight quote/backtick pair is symmetric and already
    fully handled by _candidates's close-consumption (it only ever extends
    `end` by one character, so a straight-quote run spanning MORE than that
    one trailing character is what this function must still catch — see the
    worked example below)."""
```

Implementation sketch (not copied verbatim into the task — the task owner
writes the real body against the pinned tests, but the shape is fixed here):

- **Same two-part split as the symmetric branch above, for the same
  reason**: an asymmetric opener the match's own `_WRAP` group captured
  sits AT `start`, invisible to a backward scan over
  `text[clause_start:start]`. **Part 1**: when `text[start]` is itself an
  asymmetric opener (one of `_WRAP_PAIR`'s keys), treat `start` as `o`
  directly; if `_candidates` already consumed an adjacent `closer` into
  `end` for this pair (`text[end - 1]` equals this pair's `closer` via the
  same adjacent-close extension), this is the untouched label shape —
  fall through, not a citation via this check. Otherwise check whether
  `closer` occurs anywhere in `text[end:clause_end]`; if found, the
  candidate is a citation. **Part 2** (below) is the ordinary backward scan
  for an asymmetric opener that is NOT the match's own captured wrap — an
  unrelated earlier aside in the same clause, automatically disjoint from
  Part 1 for the same reason given in the symmetric branch.
- **Part 2**: walk `_WRAP_PAIR` items; for each `(opener, closer)` pair, find the last
  occurrence of `opener` in `text[clause_start:start]` (a scan backward from
  `start`, bounded by `clause_start` — same cost shape as `_words_before`).
  If found at `o`, **require that `o` is genuinely unclosed before `start`:
  confirm `closer` does NOT occur anywhere in `text[o:start]` after `o`**
  (an asymmetric pair has a distinct open/close character, so — unlike the
  symmetric branch's same-character parity count — this is a direct
  occurrence check, not a count: if `closer` already appears between the
  opener and `start`, that specific opener/closer pair already closed before
  the candidate and says nothing about whether `start` is wrapped; `_cited`
  must return `False` for this wrapper kind in that case, since the sketch
  does not walk further back to an even-earlier opener — a clause with two
  independent asymmetric-wrapped asides before a real, unwrapped delegation
  order is out of scope for the same reason the symmetric branch's stray-
  opener case is, per `## Risks & edge cases`). Only when `o` is confirmed
  unclosed before `start`, check `closer` in `text[end:clause_end]` (the
  first occurrence is enough — a citation is "wrapped", it does not need the
  tightest pair); if found, return `True`, UNLESS that `opener`/`closer`
  pair is exactly the one `_candidates` already consumed into `[start, end)`
  (i.e. `end - 1` already points at `closer` immediately after the match —
  detectable by checking whether `text[end - 1] == closer` *and* the found
  close index equals `end - 1`; in that case this specific pair already
  anchored via the existing immediate-close rule and must not ALSO be
  treated as a citation). **This mirrors the symmetric branch's parity
  guard exactly** (confirmed-unclosed-before-start, then confirmed-closed-
  at-or-after-end) — the two branches use different mechanics (count parity
  vs. a direct occurrence check) only because a symmetric character has no
  distinct open/close form and an asymmetric pair does.
- Backtick and straight-quote/double-quote citations (the six corpus
  dispatches) are **not** in `_WRAP_PAIR` (that dict only holds the
  asymmetric/curly pairs — see the module docstring at lines 71-74: "A regex
  backreference cannot express an asymmetric pair"). The symmetric wrappers
  (`` ` ``, `'`, `"`) are matched via `_WRAP_OPEN`/`_WRAP_CLOSE` character
  classes instead. So `_cited` needs its own small symmetric-wrapper check,
  in **two parts**, because a wrap character the match's own `_WRAP` group
  captured sits AT `start` itself — inside the matched span, not before it —
  and is therefore invisible to a plain backward scan over
  `text[clause_start:start]`. Treating that captured position correctly is
  not optional polish: three of the six corpus spans (the two backtick
  citations and the double-quote citation) all have their opening wrapper
  immediately adjacent to the name, so a scan that only looks strictly
  before `start` finds nothing for any of them and wrongly reports "not a
  citation" in every case.

  **Part 1 — the match's own captured wrap (`text[start]` is a wrap
  character).** When the candidate's own regex match captured a leading
  wrap — detectable directly as `text[start]` being one of `` ` ``, `'`,
  `"` — treat `start` itself as the opener position (not a backward scan
  target). Determine whether `_candidates` already consumed an immediately
  adjacent close into `end` for this exact pair (the existing extension:
  `hooks/guard_phase_delegation.py:395-397`, `if wrap and text[end:end+1] ==
  close: end += 1`). This is checkable directly: the adjacent-close case is
  exactly when extending the span by one more character from where the
  bare, un-extended match would have ended lands on this same character —
  equivalently, when `text[end - 1]` equals this wrap character AND no
  other explanation for that char's presence exists (for a single bare
  name match, the only way `end` can have been extended by `_candidates` at
  all is this exact rule, so `text[end - 1] == <the wrap character
  captured at start>` is sufficient to recognize "already consumed
  adjacent close" here). **If the adjacent close was consumed** (today's
  tight label, `` `plan-tasks` `` shape) — this is the untouched "wrapped on
  its own" case `## Requirements` pins: **not** a citation via this check
  (fall through to Part 2 / the existing anchor logic, unchanged). **If no
  adjacent close was consumed** (the wrap character at `start` has no
  partner immediately after the name), check whether that same character
  occurs again anywhere in `text[end:clause_end]`. If found, the candidate
  IS a citation — the wrap opens tight against the name but closes only
  after more text, exactly the PRD's stated common shape. This is what
  fixes the two backtick citations and the double-quote citation (in each,
  the opening wrapper sits immediately before the recognized name with no
  adjacent close, and the true close lands later in the sentence, past
  where the bare name match ends).

  **Part 2 — a wrap character that is NOT the match's own captured wrap**
  (an unrelated earlier quote in the same clause; this is the ordinary
  backward-scan case, parallel to the asymmetric branch). For each of
  `` ` ``, `'`, `"`, find the nearest occurrence of that character in
  `text[clause_start:start]` — note this scan can never find the
  match's-own captured wrap char, since that one sits AT `start`, not
  before it, so Part 1 and Part 2 are automatically disjoint and need no
  extra exclusion logic between them. Determine "genuinely unclosed before
  the candidate" by **parity, not by a bare "found one earlier" check**:
  count every occurrence of that character in `text[clause_start:start]`.
  An **odd** count means a dangling, unmatched opener of that kind is in
  effect at `start` — a bare "found at least one" test is not equivalent
  and is wrong (it would also fire for an EVEN count, i.e. a clause with
  zero or more already-CLOSED prior pairs, none of which wraps `start`).
  Only on an odd count, check whether that character occurs again anywhere
  in `text[end:clause_end]`: structurally, the NEXT occurrence of a
  symmetric wrap character after an odd-count position always closes the
  dangling interval (toggling parity back to even) — there is no ambiguity
  about which later occurrence "belongs" to the opener, because a symmetric
  character has no separate open/close identity; the string's occurrence
  sequence alone determines the open/closed state at every position. If
  found, the candidate is a citation via Part 2.

  `_cited` returns `True` for the symmetric branch when EITHER part finds a
  citation for any of the three characters (`` ` ``, `'`, `"`) — an `or`
  across parts and across characters, same as the branch-level `or` stated
  below.

  **Edge case, documented rather than specially handled**: a clause with a
  genuinely stray, never-closing wrap character before a real, correctly
  anchored delegation order (malformed prose or markdown, not a realistic
  corpus shape) reads every name after it as "inside" that dangling opener
  until the clause's next occurrence of the same character closes it —
  which could be a later, unrelated labelled name's own opening character.
  This is accepted as-is: it is a pre-existing property of treating a
  symmetric wrap character as toggling open/closed state (the only
  tractable rule for a character with no separate open/close form), it
  requires an adversarial, malformed input with no example anywhere in the
  565-record corpus this PRD was built against, and resolving it needs full
  per-character nesting tracking across the clause (Alternative 3, rejected
  below as disproportionate to a shape no real dispatch has ever hit).
- The paren-aside span (`parse and plan-tasks) looks fo`) is the `(`/`)`
  `_WRAP_PAIR` case: `(` opens 13 characters before `plan-tasks` (intervening
  words `parse and`), so it is NOT the match's own adjacent-wrap capture —
  `_candidates` only extends `end` by one when its own `wrap` group matched
  immediately before `start` (`hooks/guard_phase_delegation.py:395-397`),
  which did not happen here, so the trailing `)` is simply never consumed
  into the span at all; `end` points right after `plan-tasks`, before the
  `)`. **Resolution**:
  the "already consumed" exception in the first bullet applies only when the
  opener is *directly adjacent* to `start` too (a `(plan-tasks)` label, open
  immediately before, close immediately after) — that is the untouched
  "wrapped on its own" case `## Requirements` pins. When the opener is NOT
  adjacent to `start` (other words sit between the opener and the name, as
  here), the span is a citation regardless of whether `_candidates` already
  extended `end` by one for the close. So the adjacency test is on the
  OPENER side (is there a word gap between `(` and the name?), not on whether
  `_candidates` consumed the close.
- **Net rule, stated once for the task body (corrected — the opener's
  adjacency to `start` does NOT by itself decide citation-vs-label; the
  CLOSE's adjacency to `end` does):** a wrapper counts as a citation when
  its open character is in effect at or before `start` (either as the
  match's own captured `_WRAP` opener sitting AT `start` — Part 1 — or as
  an earlier, still-open occurrence found strictly before `start` — Part 2)
  **and** its matching close does NOT land immediately adjacent to `end`
  (i.e. `_candidates` did not already consume it via the existing
  adjacent-close extension), **and** that same close occurs somewhere in
  `[end, clause_end)` reached by scanning past where the bare match ended.
  The untouched "wrapped on its own" label shape (`` `plan-tasks` ``,
  `(plan-tasks)`) is exactly the case where open IS captured at `start`
  AND close IS adjacent to `end` — both conditions true, so citation is
  `False` and existing anchor logic decides as today. This rule covers all
  four corpus shapes (two backtick runs, one double-quote run, one paren
  aside) via Part 1 (the three tight-open, loose-close cases: two backtick,
  one double-quote) and Part 2 (the paren aside, whose open is not
  adjacent to the name at all).
- Costs: one bounded backward scan (`clause_start` to `start`) and one
  bounded forward scan (`end` to `clause_end`) per wrapper kind per
  candidate — same shape as the existing `_weakly_anchored` /
  `_strongly_anchored` bounded lookups, so no new unbounded scan is
  introduced.

### `_field_delegation` call site

```python
for start, end, is_skill_md in spans:
    ...
    if text[clause_end:clause_end + 1] == "?":
        continue
    if is_skill_md:
        if not _ordered_to_follow(text, end, sentences):
            continue
    else:
        if _cited(text, start, end, clause_start, clause_end):
            continue
        anchored = _strongly_anchored(...) or (
            not per_task and _weakly_anchored(...)
        )
        if not anchored or scoped:
            continue
    if _negated(text, clause_start, start):
        continue
    return _quote(text, start)
```

`_cited` runs only on the non-`is_skill_md` branch (a `SKILL.md` path span is
never quoted-citation-exempt by this PRD; `_ordered_to_follow` already gates
those via its own clause-scoped "order to follow" check).

### `_ordered_to_follow` clause-start fix

Current body (`hooks/guard_phase_delegation.py:505-515`):

```python
def _ordered_to_follow(text, end, sentences):
    sentence_end = next((s for s in sentences if s >= end), len(text))
    match = _FOLLOW.search(text, end, min(sentence_end, end + 200))
    if not match or _NEGATION.search(match.group(2)):
        return False
    return not _negated(text, end, match.start())
```

New: `_ordered_to_follow` must find the follow verb's own clause start (via
`_CLAUSE_BOUNDARY`, bisected against the `clause_starts`/`clause_ends` tables
`_boundaries` already built) and pass THAT as `_negated`'s floor, not `end`.
Since `_ordered_to_follow` does not currently receive `clause_starts` /
`clause_ends`, its signature grows:

```python
def _ordered_to_follow(
    text: str,
    end: int,
    sentences: list[int],
    clause_starts: list[int],
    clause_ends: list[int],
) -> bool:
    sentence_end = next((s for s in sentences if s >= end), len(text))
    match = _FOLLOW.search(text, end, min(sentence_end, end + 200))
    if not match or _NEGATION.search(match.group(2)):
        return False
    verb_start = match.start()
    index = bisect_left(clause_starts, verb_start)
    verb_clause_start = clause_ends[index - 1] if index else 0
    return not _negated(text, verb_clause_start, verb_start)
```

Its sole call site in `_field_delegation` (`if not _ordered_to_follow(text,
end, sentences): continue`) becomes `_ordered_to_follow(text, end, sentences,
clause_starts, clause_ends)` — `clause_starts`/`clause_ends` are already
local names in `_field_delegation` (from `_boundaries`'s return), so this is
a parameter-passing change only, no new computation at the call site.

Worked example from the deferred finding (00291): `"Read skills/work/SKILL.md,
do not stop, then follow it for every task."` — the SKILL.md path's clause
ends at the first `,` (before "do not stop"); "follow" sits in the NEXT
clause (after the second `,`). With the fix, `_negated`'s floor is that
second clause's start, so the "do not stop" negation word (which sits in the
PRIOR clause) is out of range and `_negated` returns `False` for "follow" —
the dispatch is correctly flagged as an ordered "follow" (guard denies, since
there is no negation in the follow clause itself). Today's bug used `end`
(the SKILL.md path's end, inside the FIRST clause) as `_negated`'s floor, so
`_words_before` walked back across the clause boundary into "do not stop"
and matched it, producing a false allow.

### Comment-block addition (lookalike gap)

In `_normalize`'s docstring block (or the nearby module-level comment that
already documents the Cyrillic "о" gap — grep `Cyrillic` in the file to find
the exact line), append one sentence:

> A cross-script homoglyph such as `/autopilot:wоrk` (Cyrillic о, U+043E)
> passes this guard unflagged: NFKD/NFKC fold compatibility and combining
> forms, never cross-script lookalikes, and the harness itself would not
> resolve such a spelling as a real skill name, so this is an accepted,
> documented gap rather than a defect.

### `dev/bin/replay_delegation_guard.py` exit contract

Current `main()` loop (lines 154-174): every refused dispatch outside bucket
`"other"` sets `failed = True`; a pinned id allowed sets `failed = True`. The
PRD requires: a **refused pinned id is correct and must not fail the run** —
only a refused non-pinned per-task/reviewer/agoge dispatch, or an ALLOWED
pinned id, fails it.

```python
for tool_input, ids in groups:
    name = bucket(tool_input, _READ_ONLY_REVIEWERS)
    try:
        refused = _refused(args.guard, tool_input)
    except GuardError as exc:
        print(f"replay: guard execution error: {exc}", file=sys.stderr)
        failed = True
        continue
    counts[name][0] += 1
    pinned = [tool_id for tool_id in ids if tool_id in PINNED_DENY]
    if refused:
        counts[name][1] += 1
        details.append(_detail(name, ids[0], tool_input))
        if name != "other" and not pinned:
            failed = True
    if pinned and not refused:
        print(
            f"replay: pinned deny id allowed: {' '.join(pinned)}",
            file=sys.stderr,
        )
        failed = True
```

Net change: the existing `failed = failed or name != "other"` line becomes
`if name != "other" and not pinned: failed = True`, computed from a `pinned`
list hoisted above the `if refused:` block (it is needed in both branches).
No other line changes. `bucket()` is untouched (per `## Module placement`).
Group dedup already guarantees a pinned id is never silently merged with a
non-pinned payload under a different key (the dedup key is the full
`tool_input` JSON, and `PINNED_DENY` matches by `tool_id`, which `_dedupe`
already preserves per-group as the `ids` list) — a pinned id sharing a
payload with other ids is already handled today (the existing per-group
`ids` list) and needs no new logic.

## Data flow

1. `_candidates` builds spans unchanged (pass 1, no clause/sentence lookup).
2. `_boundaries` builds `clause_starts`/`clause_ends`/`sentences` unchanged
   (pass 2 boundary tables, built once).
3. `_field_delegation`, per candidate: unchanged `clause_start`/`clause_end`
   lookup via `bisect_left` into those tables, then (new) `_cited` check
   before the existing anchor check, then (fixed) `_ordered_to_follow` with
   the clause tables threaded through for its own `_negated` call.
4. `find_phase_delegation`: unchanged, now resolves `_AGOGE_PERSONAS`
   membership instead of a prefix test at the one exemption line.
5. `dev/bin/replay_delegation_guard.py main()`: per dedup group, unchanged
   `bucket()`/`_refused()` calls; only the `failed` accumulation changes
   (pinned-and-refused is success, not failure).

## Reuse inventory

- `_words_before` (`hooks/guard_phase_delegation.py:363-384`): a lazy,
  nearest-first backward word walk bounded by a floor — the exact shape
  `_cited`'s backward wrapper scan reuses conceptually (bounded, O(1) amortized
  per candidate, never an unbounded rescan). `_cited` does not reuse this
  function directly (it scans characters, not words), but the cost-bounding
  pattern is copied from it and should be named as precedent in the task.
- `_boundaries`'s `clause_starts`/`clause_ends`/`sentences` tables
  (`hooks/guard_phase_delegation.py:405-440`): already computed once per
  field; both `_cited` and the fixed `_ordered_to_follow` consume these
  existing tables via `bisect_left`, adding no new per-field scan.
- `_WRAP_PAIR` (`:71-74`) and `_WRAP_OPEN`/`_WRAP_CLOSE` (`:62-63`): the exact
  wrapper-character sets `_cited` must search for; no new character class is
  needed.
- `bisect_left` (already imported from `bisect`, `:26`): reused by the fixed
  `_ordered_to_follow`.
- `dev/bin/release-checks`'s existing `[checks]` block
  (`hooks/test_guard_phase_delegation_*.py` list, lines 138-144 at the
  design's base commit): the new citation test file is registered by adding
  one line to this existing list, not a new block.
- Greps tried and confirmed nothing closer exists: `rg -n "quote|citation"
  hooks/guard_phase_delegation.py` (nothing — "citation" is a wholly new
  concept in this file); `rg -n "_WRAP_PAIR" hooks/` (only the one
  definition and its one use site in `_candidates`, confirming no existing
  "is this wrapped" helper to extend instead of adding `_cited`).

## Alternatives considered

1. **Chosen: one new `_cited` predicate + an opener/closer adjacency rule.**
   Smallest change that handles all four corpus wrapper shapes (backtick,
   double-quote, paren) with one rule (open-not-adjacent, close-anywhere-in-
   clause) instead of per-wrapper-kind special cases.
2. **Smallest-diff alternative: extend `_WEAK_ANCHOR_TAIL`'s existing
   close-wrap check to also require the OPEN wrap be adjacent, and drop weak
   anchoring whenever a same-kind wrapper character appears anywhere earlier
   in the clause.** Rejected: `_weakly_anchored` only runs when
   `not per_task`, but 4 of the 6 corpus dispatches are `general-purpose` (not
   per-task) while one (`toolu_011UqbqFtUDPuSeCiLLgMvEg`,
   `autopilot:worker-opus`) is strong-anchored, not weak-anchored (`"Run the
   work phase for PRD 0"` matches `_STRONG_ANCHOR_TAIL`'s `for ... PRD`
   pattern). A fix scoped to `_weakly_anchored` alone cannot close the
   strong-anchor corpus case, so the citation check must sit upstream of
   both anchor branches, as designed.
3. **Larger alternative: track wrapper nesting depth across the whole field
   in `_boundaries`'s single pass, annotating every character position with
   its "inside an unclosed wrapper" state, and have `_field_delegation` read
   that table directly instead of per-candidate scans.** Rejected: the
   nesting-depth table would need to run over the WHOLE field (an O(n)
   single pass, same order as the existing boundary build), which is not
   obviously cheaper than two bounded per-candidate scans (each bounded by
   the candidate's own clause, typically a few words), and it adds a new
   module-level data structure for a rule that only four of thousands of
   historical dispatches have ever tripped. The PRD's own framing ("a design
   decision, not an implementor rewrite... pinned verbatim by the design
   doc") asks for the narrowest predicate addition, not a new pass.

## Risks & edge cases

- **A wrapper opened in an EARLIER sentence, never closed, still open at the
  candidate**: `_cited`'s backward scan is bounded by `clause_start`, not
  `sentence_start`, so a dangling opener from a prior clause in the same
  sentence is invisible to it (by design — citation scope is the clause, per
  `## Interfaces & contracts`). This matches the PRD's stated scope (the six
  corpus spans are all single-clause) and keeps the cost bound tight; a
  cross-clause citation is out of scope and not asked for.
- **A wrapper that opens AND closes entirely before `start`** (an unrelated
  quoted/parenthesized run earlier in the clause, nothing to do with the
  candidate): **fixed in the contract**, not merely flagged here — the
  asymmetric `_WRAP_PAIR` bullet in `## Interfaces & contracts` now requires
  confirming no `closer` occurs between the found opener and `start` before
  treating it as a dangling opener (mirroring the symmetric branch's parity
  guard). A clause with TWO OR MORE independent already-closed asymmetric
  asides before an unwrapped candidate is still out of scope (the sketch
  checks only the nearest opener, it does not walk further back to an
  even-earlier one) — same accepted-risk shape as the symmetric branch's
  stray-opener case above, for the same reason (no adversarial corpus
  example, and full back-walking is the rejected Alternative 3 shape).
  `hooks/test_guard_phase_delegation_citations.py` must pin this exact
  shape (`"Note (an aside) then also run plan-tasks for cleanup)"` — the
  earlier `(an aside)` must NOT cause `plan-tasks` to be read as cited by
  the unrelated trailing `)`) as a required test case, not only the four
  shapes already listed in `## Test strategy outline`.
- **Next likely change #1**: a per-clause-kind citation allowlist (e.g. "only
  backtick/double-quote count, parens don't") if a future corpus run shows
  parens producing false negatives (a real paren-wrapped order being
  excused). This design's single open/close-adjacency rule treats all
  `_WRAP_PAIR` members plus backtick/quote identically; narrowing it later
  is a filter added inside `_cited`, not a reshape of its signature.
- **Next likely change #2**: the (sentence, id) task-scoping rule stub 00292
  contests is explicitly out of scope (per the PRD) and `_is_scoped` is
  untouched; a future PRD revisiting scoping must not assume this PRD
  touched it.
- **Next likely change #3**: a new `agoge:` persona added later must be
  added to `_AGOGE_PERSONAS` by hand (the roster fails closed, per the PRD's
  own framing) — this is the visible, intended failure mode, not a defect to
  fix here.

## Test strategy outline

- `hooks/test_guard_phase_delegation_citations.py` (new, Phase 0): one test
  per PRD-listed `New symbols` function name — backtick run, double-quote
  run, paren aside, wrapper-closing-right-after-the-name (today's handling,
  unchanged), a clause with an already-closed asymmetric aside before an
  unwrapped candidate (`"Note (an aside) then also run plan-tasks for
  cleanup)"` — must NOT be read as cited), the six corpus dispatches
  allowed, negation-in-previous-clause
  does NOT excuse follow, negation-inside-the-verb-clause STILL excuses,
  `_ordered_to_follow` uses `bisect_left` for its negation floor (asserted by
  reading the function's source via `inspect.getsource` and checking that
  `bisect_left` is present and that the specific line `_negated(text, end,
  match.start())` is absent — NOT a blanket "no `next(` anywhere in the
  function" check, since the unrelated `sentence_end = next((s for s in
  sentences if s >= end), len(text))` lookup is untouched by this fix and
  legitimately keeps its `next(` call), each agoge persona exempt, unknown
  `agoge:` prefix not exempt.
- `hooks/test_guard_phase_delegation.py`'s
  `test_allow_corpus_ignores_scratch_dispatch_files` rewritten to monkeypatch
  the corpus directory `_allow_corpus` globs, asserting the committed
  fixture list (per stub 00300 / PRD requirement line 36).
- `dev/bin/test_replay_delegation_guard.py`:
  `test_refused_pinned_per_task_id_does_not_fail_the_replay` — feed `main()`
  (or its core loop, whichever is more directly testable without a real
  subprocess — check the existing test file's fixture style first and match
  it) a dedup group whose only refused dispatch carries a `PINNED_DENY` id,
  and assert exit 0 with a `refused 1` per-task/bucket line, no "pinned deny
  id allowed" stderr line.
- Full existing suite run (task 1's acceptance criterion): all five sibling
  `test_guard_phase_delegation_*.py` files plus the new one, asserting equal
  `rg -c '^def test_' hooks/test_guard_phase_delegation_structure.py` before
  and after (no test silently dropped).
- Local corpus replay (task 2's acceptance criterion):
  `python3 dev/bin/replay_delegation_guard.py` exits 0 with no "pinned deny
  id allowed" stderr line and no refused dispatch outside the pinned ids
  (`PINNED_DENY` holds 4 ids, not 1 — do not hard-pin an exact refused count
  without first confirming, against the live corpus, how many of those 4
  dedupe into the replay's reported groups).

## Review log

dispatch 1 (claude): cardinal-sin 0, blocker 2, non-blocker 2, question 0
- Blocker: the symmetric-wrapper (backtick/quote) bullet in `_cited` lacked
  the "nearest-UNCLOSED-opener" guard and the adjacency exclusion the
  asymmetric branch already had, risking a legitimately labelled name near
  another wrapped name in the same clause being misflagged. Fixed: the
  symmetric bullet now states both guards explicitly as part of the
  contract.
- Blocker: the test-strategy line for `_ordered_to_follow`'s `bisect_left`
  check was a blanket "no `next(` anywhere in the function" assertion, which
  the design's own proposed body fails (the unrelated `sentence_end` lookup
  keeps its `next(`). Fixed: narrowed to asserting the specific old call
  site (`_negated(text, end, match.start())`) is gone.
- Non-blocker: the paren-aside worked example mischaracterized why
  `_candidates` does not extend `end` there. Fixed: corrected to state the
  real condition (the match's own adjacent-wrap capture never fired).
- Non-blocker: the replay acceptance line assumed all 4 `PINNED_DENY` ids
  collapse to one dedup group ("refused 1"), unverified. Fixed: reworded to
  a generic "no non-pinned refusal" criterion.
dispatch 2 (claude-fallback): codex unavailable (codex-run.sh ran under a
sandbox that denied every local read tool, `sandbox_apply: Operation not
permitted`; no findings were produced). Falling back to a fresh Claude
reviewer subagent for this dispatch.
cardinal-sin 0, blocker 1, non-blocker 0, question 1
- Blocker: the symmetric-wrapper `_cited` rule used a bare "found at least
  one earlier occurrence" existence check instead of parity, which could
  wrongly treat a name as a citation on an EVEN earlier count (zero or more
  already-closed prior pairs) with no actual dangling opener. Fixed: the
  rule now explicitly requires an ODD count of the character in
  `text[clause_start:start]` before treating the nearest occurrence as a
  genuinely dangling opener, and the forward check is justified
  structurally (a symmetric character's next occurrence always closes the
  currently-open interval, by parity toggle — no identity ambiguity). The
  one residual pathological shape (a stray, never-closing wrap character
  before a real order) is documented as an accepted edge case rather than
  specially handled, since it needs full per-character nesting tracking for
  a shape absent from the whole corpus this PRD is built against.
- Question: today's `test_allow_corpus_ignores_scratch_dispatch_files` is
  vacuously true (`_allow_corpus()` globs a hardcoded path, never
  `tmp_path`), and the design did not say what becomes patchable. Fixed:
  `## Module placement` now names the mechanism (`monkeypatch.setattr` on
  the test module's `FIXTURES` constant).
dispatch 3 (claude-fallback): codex unavailable again (same sandbox read
denial, `sandbox_apply: Operation not permitted`, zero findings produced).
Falling back to a fresh Claude reviewer subagent for this verification pass.
cardinal-sin 0, blocker 1, non-blocker 1, question 1
- Blocker: the symmetric branch's just-fixed parity guard was correct, but
  the ASYMMETRIC `_WRAP_PAIR` branch still had the identical
  already-closed-before-start false-positive bug that `## Risks & edge
  cases` had flagged as "must be guarded in the real implementation" without
  the fix ever being folded back into `## Interfaces & contracts`. Fixed:
  the asymmetric bullet now requires confirming no closer occurs between
  the found opener and `start` before treating it as dangling, mirroring
  the symmetric branch's guarantee; the Risks bullet is rewritten to say
  "fixed in the contract" instead of "must be guarded"; one new required
  test case (an already-closed aside before an unwrapped candidate) was
  added to both `## Risks & edge cases` and `## Test strategy outline`.
- Non-blocker: inconsistent phrasing between "six corpus dispatches" and
  "four corpus wrapper shapes" elsewhere in the doc — both are accurate (six
  dispatches map to four distinct wrapper shapes); left as-is, not worth a
  rewording pass.
- Question: whether the now-fixed asymmetric-branch risk bullet should be
  reclassified from "risk" to something else — resolved by rewriting it in
  place (see the Blocker fix above) rather than moving it, since it
  describes the SAME residual multi-opener accepted-risk shape the
  symmetric branch already documents, just for the asymmetric wrapper kind.
No further open cardinal sins or blockers after this dispatch.
result: ok
