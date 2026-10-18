# Discovery: Files over the 800-line cap

## Classification
Depth: light | Date: 2026-10-18 | Status: pre-elicitation (triage of recurring deferred findings, no questions asked yet)

## Problem
The repo's own style rule caps a file at 800 lines, and every review cycle
raises the files that break it, defers the finding as pre-existing, and
moves on. Deferred rows naming the cap in batch 202610161547 alone: nine,
across 00320, 00321, 00322, 00324 and 00326. Files named, with the sizes the
reviews recorded:

| File | Lines |
|---|---|
| `skills/run-autopilot/cli/__main__.py` | about 2030 |
| `skills/run-autopilot/scripts/tracon/test_discovery.py` | 1703 |
| `skills/run-autopilot/cli/review_stage.py` | 874 |
| `skills/run-autopilot/cli/test_review_stage.py` | 805 |
| `skills/run-autopilot/cli/test_routing.py` | 804 |
| `hooks/guard_phase_delegation.py` | 800 (at the limit) |
| `skills/run-autopilot/cli/test_state.py` | over (excluded by 00192) |

PRD 00192 split `loop.py` and its tests under the cap and deliberately
excluded `__main__.py` and `test_state.py`; nothing since has owned them, so
each new PRD that touches them re-pays the finding and the project capsule
carries the pair as "standing debt". Two of the files (`__main__.py`,
`review_stage.py`) are the verbs the loop runs most.

## Requirements (candidate, to be elicited)

### Must have
- F1: a decision per file: split (with the seams named: `__main__.py` by
  verb family, `review_stage.py` by stage, the test files by the module they
  test) or an explicit, dated exemption in the style rule's own text so
  reviewers stop raising it.
- F2: the review-close gate stops deferring the cap finding for an exempted
  file and keeps raising it for the rest.

### Nice to have
- A gate check that fails a PRD only when its own diff pushes a file over
  the cap, never for a pre-existing overflow.

### Out of scope
- Raising the cap globally.

## Constraints
- A split of `__main__.py` moves argparse wiring; every verb has prose and
  tests naming `cli/__main__.py` as the entry point, which must keep
  working (`python3 .../cli/__main__.py <verb>`).

## Codebase Context
- PRD 00192 (done) as the precedent for a split under the loop.
- `rules/coding-style.md` (the 800 max), `skills/review-work-completion`
  rubric R13.

## Approach (candidate)
Elicit the per-file decision first; a split PRD per file after that, each
card-sized.

## Success Criteria (candidate)
- No deferred row of the next batch names the 800-line cap for an exempted
  or split file.

## Risks
- Splitting `__main__.py` under a running loop changes the file every loop
  session imports; schedule it as the first PRD of a batch.

## Open Questions
- Is the cap a hard rule for generated or table-like test files
  (`test_discovery.py` is mostly fixtures)?

## Discovery Log

### Inferred (not asked)
- The deferred ledger rows naming the cap carry `disposition: discovery
  00364`.
