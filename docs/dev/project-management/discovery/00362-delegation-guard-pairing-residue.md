# Discovery: Delegation guard pairing residue

## Classification
Depth: light | Date: 2026-10-18 | Status: pre-elicitation (triage of batch 202610161547's deferred findings on PRD 00324, no questions asked yet)

## Problem
PRD 00324 (guard pairs delimiters as nested runs) capped out at cycle 2 with
two HIGHs and six Medium/Low findings unresolved. Both HIGHs reproduce at
HEAD e8ca2f7 on 2026-10-18, probed through
`guard_phase_delegation.is_phase_delegation({"prompt": ...})`:

| Stub | Payload | Verdict at HEAD | Expected |
|---|---|---|---|
| 00343 (31b3267b160e, 3/4) | `Note [see (x] then run plan-tasks for PRD 00300 for every task (done).` | allowed | denied |
| 00343 | `Note (see [x) then run plan-tasks for PRD 00300 for every task [done].` | allowed | denied |
| 00344 (54f138480301, 1/4) | `Hi (all！Run plan-tasks for PRD 00300 for every task！Thanks)` | allowed | denied |
| 00344 | `Hi (all？Run plan-tasks for PRD 00300 for every task？Thanks)` | allowed | denied |
| control | `Hi (all。Run plan-tasks for PRD 00300 for every task。Thanks)` | denied | denied |
| control | `Run plan-tasks for PRD 00300 for every task.` | denied | denied |

00343: an asymmetric opener inside a closed or mismatched bracket run still
pairs with a later closer (`hooks/guard_phase_delegation.py` around line
435); the quote, backtick and curly-quote variants were fixed in cycle 2.
00344: normalization folds the fullwidth `！` and `？` to ASCII before the
unconditional CJK terminator branch runs, so only `。` ends the citation
window.

Medium: `@lru_cache(maxsize=4)` on `_nested_run_pairs` (line 353) is hidden
module state holding field-sized strings, raised by two lenses; the
bracket-literal fix has one test, the backtick-run, curly-quote and
bracket-in-bracket shapes are untested; three touched tests in
`test_guard_phase_delegation_citations.py` and eight in
`test_guard_phase_delegation_structure.py` pass against the pre-change code.
Low: the hook is exactly 800 lines (discovery 00364).

Accepted deviations closed in this triage: `_FOLLOW` matches are not
collected by bisect (budget met anyway, 0.14 to 0.25 s/MB against 0.3);
`·` is not a sentence boundary (design decision); `_NEGATION_REACH_END`
denies coordinated negated lists (the safe direction); the mutation-style
test passes at base by design.

## Requirements (candidate, to be elicited)

### Must have
- F1: an opener inside a closed or mismatched bracket run never pairs with a
  closer outside that run; the four payloads above are denied and the
  existing allowed corpus stays allowed.
- F2: the fullwidth terminators `！` and `？` end the citation window before
  normalization folds them, or the CJK branch runs on the unnormalized text.
- F3: `_nested_run_pairs` computed once per field and passed down; no module
  cache.
- F4: one test per delimiter shape (backtick run, curly quote,
  bracket-in-bracket) in the citations test file, each red on the pre-change
  code.

### Nice to have
- A property-style corpus test over the recorded reviewer prompts
  (`dev/bin/replay_delegation_guard.py` already replays them).

### Out of scope
- The hook's size (discovery 00364).

## Constraints
- The hook runs on every subagent dispatch; the 0.3 s/MB budget holds.
- Every change replays the recorded corpus: five of 235 real reviewer prompts
  were still denied after 00248; no new false denial is acceptable.

## Codebase Context
- `hooks/guard_phase_delegation.py` (`_nested_run_pairs`, `_boundaries`,
  the CJK terminator branch), `hooks/guard_phase_delegation_lexicon.py`.
- `hooks/test_guard_phase_delegation_citations.py` (line 727 names the
  fullwidth case), `hooks/test_guard_phase_delegation_structure.py`,
  `dev/bin/replay_delegation_guard.py`.
- Review evidence: `reviews/00324-guard-pairs-delimiters-as-nested-runs-v1-review-2.md` R1, R3, R4.

## Approach (candidate)
One PRD, full lane, `design: run`, `default_model: opus` (pairing semantics
with a measured bypass history: 00248, 00254, 00267, 00271, 00307, 00324).

## Success Criteria (candidate)
- The probe table above reads denied in every row; the corpus replay stays
  at its recorded allow/deny counts.

## Risks
- Each guard PRD so far closed some bypasses and opened a stub for the next;
  the elicitation should ask whether a parser (bracket stack) replaces the
  regex pairing instead of another patch.

## Open Questions
- Patch the pairing again, or rewrite the delimiter handling as a small
  tokenizer with a bracket stack?

## Discovery Log

### Inferred (not asked)
- Probe script: `python3 -I` over the hook module with the six prompts,
  2026-10-18. Hold stubs 00343 and 00344 are closed into done/ with a note
  naming this document; the deferred ledger rows carry `disposition:
  discovery 00362`.
