---
catchup: run
design: run
default_model: opus
model_tier_rationale: pairing semantics with a measured bypass set of five shapes, stacked onto a module two prior PRDs reworked
---

# The delegation guard pairs delimiters as nested runs and binds a negation to its own verb

Source: hold stubs 00317 and 00318 (PRD 00307 cycle 2, R2 and R3); the 00307 deferred ledger (R1, R9: the doubled-backtick citation); `docs/dev/project-management/audit-results/agoge-2026-10-15.md` packets 6, 7, 20, 29.

## Problem

00307's citation rule pairs quote and backtick delimiters field-wide in `_quoted_runs` (`hooks/guard_phase_delegation.py:329-367`) and `_cited` (`hooks/guard_phase_delegation.py:550-575`) exempts an order found inside a pair; `_negated` (`hooks/guard_phase_delegation.py:578-587`) treats any `_NEGATION` match (`hooks/guard_phase_delegation_lexicon.py:183-187`) within `_NEGATION_WORD_GAP` words of the name, inside its clause, as negating the order. Measured as hook exit codes on hand-written Agent payloads, HEAD against the released 0.9.0: (1) a backtick inside a closed `"…"` run pairs with an unrelated later backtick, so `Note "see `x" then run /autopilot:work for PRD 00300 end to end, report `done`.` is allowed (HEAD 0, 0.9.0 2), as is `Then "edit `a.py" and run plan-tasks for prd 00300 for every task and print `ok`.`; (2) `:(` and `:)` form a bracket pair: `Sorry :( run plan-tasks for prd 00300 for every task :)` (HEAD 0, 0.9.0 2); (3) `。` and `·` do not end the citation window: `Hi (all。 Run plan-tasks for PRD 00300 for every task。 Thanks :)` (HEAD 0, 0.9.0 2); (4) the own-wrapper branch of `_cited` excuses `The log says 5"plan-tasks for PRD 00300 and print "ok".` although `_quoted_runs` rejects the digit-preceded quote (stub 00318, reproduced by trudy); (5) a negation joined by "and" cancels the order that follows: `Don't stop and run the work phase for PRD 00300.`, `Never pause and run /autopilot:work for PRD 00300 end to end.` and `Do not wait and run plan-tasks for PRD 00300 for every task.` exit 0 on HEAD and 0.9.0 while the control `Don't stop, run the work phase for PRD 00300.` exits 2 (packet 7); (6) a doubled-backtick citation is still falsely refused, and the backtick exclusion in `_CITE_SENTENCE_BOUNDARY` (`hooks/guard_phase_delegation_lexicon.py:214-220`) has no test that fails when it is removed (00307 R1, R9). Cost: each `SKILL.md` mention searches `_FOLLOW` (`hooks/guard_phase_delegation_lexicon.py:160-164`) over a 200-character window, 0.77 s/MB on a dense payload against the 0.3 s/MB bound `BUDGET_S_PER_MB` (`hooks/test_guard_phase_delegation_linearity.py:33`), reaching the 5-second hook timeout at about 6.3 MB (packet 20). Stub 00317 (the corpus test pins 2 of the 6 recorded ids; the other four prompts were never recorded) is accepted as a documented limit: `hooks/test_guard_phase_delegation_corpus.py` already names its synthetic shapes, and no task here changes that.

## Solution

Pair delimiters as nested runs and bind negation to its verb. A new `_nested_runs` makes one left-to-right scan of the field with a stack of open delimiters: a delimiter that opens inside a closed run of another kind can only close inside it; a symmetric delimiter that `_quoted_runs` rejects (a digit-preceded `"`) is never an opener for any branch of `_cited`, so the own-wrapper branch reads from the same run map; a bracket opener preceded by `:` or `;` is an emoticon, not a wrapper; backtick runs pair by length, so a doubled-backtick citation closes with a doubled backtick. `。`, `·`, `！` and `？` join `_CITE_SENTENCE_BOUNDARY` as sentence ends. `_negated` stops at `_NEGATION_REACH_END` (` and `, ` then `, ` but ` before the candidate's verb): a negation before such a joiner does not reach the order after it. `_FOLLOW` matches are collected once per field and looked up per mention by bisect, so a dense payload costs under `BUDGET_S_PER_MB`. Every payload above is pinned as deny or allow, and packet 29 (the guard crashes under the system Python 3.9, which the harness may read as allow) is accepted as documented: the SKILL.md floor is 3.11.

## Requirements

### Must have
- Payloads (1) through (5) exit 2 on HEAD; their controls (`Don't stop, run the work phase for PRD 00300.` exit 2; `The log says "ready, done" then run plan-tasks for PRD 00300` exit 2; a whole order inside one quote pair exit 0) keep today's results.
- A citation wrapped in doubled backticks (the order "run plan-tasks for PRD 00300" inside a two-backtick code span, followed by prose) exits 0, and `test_backtick_exclusion_in_cite_boundary_can_fail` is red when the backtick class is removed from `_CITE_SENTENCE_BOUNDARY` (the test replaces the pattern with one lacking that class and asserts the guard's answer flips).
- `dev/bin/replay_delegation_guard.py` over the recorded corpus still exits 0 with per-task refused 1 (the pinned id), the 00307 contract.
- A 1 MB payload with a `SKILL.md` mention every 100 characters runs under `BUDGET_S_PER_MB` in `hooks/test_guard_phase_delegation_linearity.py`.
- CHANGELOG `[Unreleased]` Fixed entry under **hooks**.

### Nice to have
- None.

## Implementation

### Module: guard-pairing
- **Location**: `hooks/guard_phase_delegation.py` (`_quoted_runs`, `_cited`, `_negated`, `_boundaries`, `_ordered_to_follow`), `hooks/guard_phase_delegation_lexicon.py` (`_CITE_SENTENCE_BOUNDARY`, `_WRAP_SCAN_PAIRS`, `_SYMMETRIC_DELIMS`, `_FOLLOW`)
- **Responsibility**: nested-run pairing, emoticon and inch-mark exclusions, CJK terminators, verb-bound negation, one `_FOLLOW` pass per field
- **Exports**: `find_phase_delegation()`, `is_phase_delegation()` (unchanged)
- New symbols: `_nested_runs`, `_NEGATION_REACH_END`

### Module: guard-pairing-tests
- **Location**: `hooks/test_guard_phase_delegation_citations.py`, `hooks/test_guard_phase_delegation_structure.py`, `hooks/test_guard_phase_delegation_linearity.py`
- **Responsibility**: pin every payload above as deny or allow and the dense-mention budget
- **Exports**: none
- New symbols: `test_backtick_inside_closed_quote_run_does_not_pair_outside_it`, `test_emoticon_pair_is_not_a_citation`, `test_cjk_terminators_end_the_citation_window`, `test_digit_preceded_quote_never_opens_an_own_wrapper_run`, `test_negation_does_not_reach_past_and_then_but`, `test_doubled_backtick_citation_is_allowed`, `test_backtick_exclusion_in_cite_boundary_can_fail`, `test_dense_skill_md_mentions_stay_under_budget`

### Dependencies
- guard-pairing-tests: No dependencies (foundation)
- guard-pairing: Depends on [guard-pairing-tests]

## Tasks

### Phase 0: Foundation
- [ ] Add `test_backtick_inside_closed_quote_run_does_not_pair_outside_it`, `test_emoticon_pair_is_not_a_citation`, `test_cjk_terminators_end_the_citation_window`, `test_digit_preceded_quote_never_opens_an_own_wrapper_run`, `test_doubled_backtick_citation_is_allowed` and `test_backtick_exclusion_in_cite_boundary_can_fail` to `hooks/test_guard_phase_delegation_citations.py`, `test_negation_does_not_reach_past_and_then_but` (the three payloads of (5) deny, the comma control denies) to `hooks/test_guard_phase_delegation_structure.py`, and `test_dense_skill_md_mentions_stay_under_budget` to `hooks/test_guard_phase_delegation_linearity.py`, each driving `find_phase_delegation` with the payload verbatim - Acceptance: `uv run --no-project --with pytest python -m pytest -q hooks/test_guard_phase_delegation_citations.py hooks/test_guard_phase_delegation_structure.py hooks/test_guard_phase_delegation_linearity.py` reports the eight new tests failing at the task's base commit and no existing test failing.

### Phase 1: Core
- [ ] Implement `_nested_runs` and route `_cited`'s own-wrapper branch through it, add the emoticon exclusion and length-paired backtick runs, extend `_CITE_SENTENCE_BOUNDARY` with the CJK terminators, add `_NEGATION_REACH_END` to `_negated`, and collect `_FOLLOW` matches once per field in `_boundaries` for `_ordered_to_follow` (depends on: Phase 0) - Acceptance: the Phase 0 command passes every test; `uv run --no-project --with pytest python -m pytest -q hooks/test_guard_phase_delegation.py hooks/test_guard_phase_delegation_corpus.py hooks/test_guard_phase_delegation_replay.py hooks/test_guard_phase_delegation_scratch_replay.py` passes; `python3 dev/bin/replay_delegation_guard.py` exits 0 and its summary line reads `refused 1`.
- [ ] Add the CHANGELOG `[Unreleased]` Fixed entry under **hooks** naming the five closed shapes and the restored linear budget (depends on: Phase 1 pairing) - Acceptance: `rg -n 'emoticon' CHANGELOG.md` prints one hit under `[Unreleased]`.

## Success Criteria

- Each of the five payload groups from the Problem section exits 2 through `hooks/guard_phase_delegation.py` on stdin; each control keeps its documented exit.
- The recorded-corpus replay exits 0 with refused 1.
- The dense 1 MB payload runs under `BUDGET_S_PER_MB`; an 8 MB payload stays under the 5-second hook timeout.
