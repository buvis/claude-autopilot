# Discovery: Card gates miss the consumers of a changed predicate

## Classification
Depth: light | Date: 2026-10-18 | Status: pre-elicitation (written from the 00334 fast-track item, no questions asked yet)

## Problem
A fast-track card's gates are the backticked test commands of the PRD's own
acceptance lines. PRD 00334 asked for `is_test_path` in
`skills/work/scripts/work_routing.py` to return True for
`dev/bin/release-checks`, and its acceptance named only the `work_routing`
test files. Tess and Ivan implemented exactly that, both gates passed, and
the roster found that `skills/run-autopilot/cli/lane.py` loads `is_test_path`
from that file by path for `is_production_path`, and
`skills/plan-tasks/scripts/classify_tier.py` does the same: a
release-checks-only PRD would route to the solo lane and
`test_lane.py::test_production_path_excludes_tests_docs_and_packaging` went
red. Three lenses raised it (R1 `[3/4]`), Blake added R9 ("the PRD's gates
omit the dependent lane and classify_tier suites"), a rework replaced the
design (`_TEST_INFRA_PATHS` filtered inside `test_only_diff`, `is_test_path`
strict again) and the done PRD now describes a design that did not ship.
Cost: one rework round and a delta review, about 10 min and $4; without the
roster, a red batch suite 20 minutes later.

Two things are true at once: the author should have checked the consumers
(now a recorded authoring rule), and the lane had the information to catch
it before review and did not use it.

## Requirements (candidate, to be elicited)

### Must have
- F1: `cards_from_prd.py` adds, to a card's gates, the test file of every
  module that imports or path-loads a file in the card's `## Files`
  allowlist (an `rg` for the module stem across `skills/`, test files
  excluded, each hit's sibling `test_<name>*.py` appended as a gate), and
  prints which gates it added and why.
- F2: the card's `## Constraints` names the consumers found, so Tess and Ivan
  see them.

### Nice to have
- The same consumer list in the PRD grounding gate's output
  (`ground_prd.py`, in the agent-skills repo), so the author sees it before
  the PRD is saved.

### Out of scope
- Running the whole suite before review (15 to 25 min per card).

## Constraints
- Consumer discovery is textual (`rg` for the stem); a false positive adds a
  harmless gate, a false negative is today's behaviour.
- The gate list must stay bounded: cap added gates at a small number and
  prefer the directory form (`pytest -q skills/x/scripts`) when a module has
  many consumers.

## Codebase Context
- `skills/fast-track/scripts/cards_from_prd.py` `_gates` and
  `_GATE_PREFIXES` (PRD 00347 added the release-script drop there).
- `skills/run-autopilot/cli/lane.py:82-84` (`_load_by_path` of
  `work_routing.py`), `skills/plan-tasks/scripts/classify_tier.py:19-28`.
- `reviews/00334-*-review-1.md` rows R1, R4, R5, R9 and the item report
  under `docs/dev/tmp/00334-*-fast-track-review.md`.

## Approach (candidate)
Deterministic gate augmentation in the card parser.

## Success Criteria (candidate)
- Rendering the 00334 PRD into cards yields a gate that runs `test_lane.py`
  and the classify_tier tests, and the parser prints the two consumers.
- A PRD whose files have no consumers renders unchanged.

## Risks
- With consumer tests in the gate, 00334's first draft would have stalled
  (Tess's own test contradicted `test_lane.py`) instead of self-healing in
  review. A stall is the honest outcome for a PRD with a design error, but it
  costs an operator round trip where the roster today costs $4. The
  elicitation has to decide which is wanted.

## Open Questions
- Stall on a consumer-test failure, or let Ivan rewrite Tess's test when the
  two contradict (the fast-track rule today forbids Ivan touching tests)?
- Should the added gates run before Tess (to inform her) or only after Ivan?

## Discovery Log

### Inferred (not asked)
- Consumer list from `rg -n "is_test_path|test_only_diff" skills/ --glob
  '*.py' --glob '!test_*'` on 2026-10-17.
