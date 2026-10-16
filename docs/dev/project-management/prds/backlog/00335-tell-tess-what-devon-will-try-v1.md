---
design: skip
default_model: sonnet
model_tier_rationale: one numbered rule and one quality-gate check with their exact text, additive prose tests beside the existing rule pins; nothing is designed
---

# Tell Tess what Devon will try

Source: `docs/dev/project-management/autopilot/ledger/attempts.jsonl`, the 43 attempt records carrying `attempt.devon_exploit` (counted 2026-10-16), and 00322 task 1 (batch 202610161547, session a3aeb937: Tess, Devon, Tess again, three opus dispatches and about 22 minutes before the implementor started).

## Problem

`Devon` (work step 2.9, `skills/work/SKILL.md:248-256`, opus and fable tasks only) wins almost every time: of the Devon rounds recorded in `attempts.jsonl`, 46 ended `exploit_fixed` or `exploit:fixed`, one exhausted its rounds, and every `devon_exploit` text lists three to nine wrong implementations that passed Tess's whole first draft. The classes repeat. Of the 43 exploit texts: 22 shaped the implementation to the exact test input (exact-match of the fixture bytes, first-element or truncated handling, only the two tested tags), 20 hardcoded fixture values or filenames, 18 matched by substring, prefix or basename where identity was meant, 18 returned a constant or degenerate result (`return True`, `return {}`, allow-by-default, deny-everything), 10 swallowed an exception or failed open, 4 used a lookup table keyed on the fixture.

Tess is told to anticipate this only in the abstract: rule 6 of `skills/work/references/tess-prompt.md:25` says "For `EACH` test, ask yourself: What wrong implementation would still pass this?", and the step-2.8 quality gate `checklist` (`skills/work/references/test-author-prompt.md:63-68`) checks behavior names, real assertions, edge cases and tautologies, none of which fails a suite that a `hardcoded` fixture implementation passes. Devon's own prompt names the strategies (`skills/work/references/adversarial-test-prompt.md:35-36`), but Tess never sees it. So every opus task pays a Tess dispatch, a Devon dispatch and a Tess strengthening dispatch to arrive where the first draft could have started.

## Solution

Give Tess the six classes as a concrete rule with the assertion that defeats each, and make the step-2.8 gate check for those assertions before Devon runs. Rule 6a in `tess-prompt.md` lists, for every tested function: two distinct fixture values per asserted field (defeats hardcoding); a near-miss negative that shares a prefix, suffix or substring with a positive and must not match (defeats substring and basename matching); an input with more than one element and an empty input (defeats first-element and truncation shortcuts); both an accept and a reject case of the same shape for any guard or classifier (defeats constant returns); an error case asserting the exception or the failure signal surfaces (defeats swallowing and fail-open); and a dependency assertion, that a `cwd`, environment value or passed argument reached the call or changed a side effect (defeats dropped plumbing). The quality gate gains check 5, "Exploit classes covered?", citing rule 6a, so a draft lacking them is a Tess retry rather than a Devon round. Devon's round is unchanged; the measure of success is the share of his rounds that still find an exploit.

## Requirements

### Must have
- `skills/work/references/tess-prompt.md` gains rule `6a. DEVON-PROOF:` immediately after rule 6, one line, naming the six classes and their defeating assertions in the order above and ending `Devon will try exactly these; a draft that lacks one is sent back to you.`
- `skills/work/references/test-author-prompt.md` § Quality gate gains, after check 4: `5. **Exploit classes covered?** Every tested function has the six rule-6a assertions (two fixture values per asserted field, a near-miss negative, a multi-element and an empty input, an accept and a reject case of the same shape, a surfaced error, a dependency assertion); a missing one is a check-5 failure and names the class.`
- `skills/work/references/tess-retry-prompt.md` keeps its rule numbering; no other prose changes.
- Fail-first prose tests in `skills/work/scripts/test_tess_size_limits_prose.py` (registered under `[checks] loop blockers prose`, `dev/bin/release-checks:245`): `test_tess_prompt_names_devons_exploit_classes` and `test_quality_gate_checks_exploit_classes`.
- A CHANGELOG `[Unreleased]` Changed entry under **work**.

### Nice to have
- None.

## Implementation

### Module: tess-devon-proof-prose
- **Location**: `skills/work/references/tess-prompt.md` (rule 6a), `skills/work/references/test-author-prompt.md` (§ Quality gate check 5)
- **Responsibility**: the first test draft already closes the exploit classes Devon's rounds keep finding
- **Exports**: none (prose)

### Module: tess-devon-proof-tests
- **Location**: `skills/work/scripts/test_tess_size_limits_prose.py`
- **Responsibility**: pin rule 6a's six classes and the gate's check 5
- **Exports**: none
- New symbols: `test_tess_prompt_names_devons_exploit_classes`, `test_quality_gate_checks_exploit_classes`

### Dependencies
- tess-devon-proof-tests: No dependencies (foundation)
- tess-devon-proof-prose: Depends on [tess-devon-proof-tests]

## Tasks

### Phase 0: Foundation
- [ ] Add two tests to `skills/work/scripts/test_tess_size_limits_prose.py` using its `_rule` helper (`skills/work/scripts/test_tess_size_limits_prose.py:22`): `test_tess_prompt_names_devons_exploit_classes` reads rule `6a` of `tess-prompt.md` and asserts it contains `DEVON-PROOF`, `two distinct fixture values`, `near-miss negative`, `empty input`, `accept and a reject case`, `surfaced` and `dependency assertion`; `test_quality_gate_checks_exploit_classes` slices `test-author-prompt.md` from `## Quality gate (step 2.8)` to `### Style limits on the test files` and asserts it contains `5. **Exploit classes covered?**` and `rule-6a` - Acceptance: `uv run --no-project --with pytest python -m pytest -q skills/work/scripts/test_tess_size_limits_prose.py` reports the two new tests failing and the three existing tests passing at the task's base commit.

### Phase 1: Core
- [ ] Insert after rule 6 of `skills/work/references/tess-prompt.md` the line below, and after check 4 of `skills/work/references/test-author-prompt.md` § Quality gate the check-5 line from Requirements (depends on: Phase 0) - Acceptance: `uv run --no-project --with pytest python -m pytest -q skills/work/scripts/test_tess_size_limits_prose.py skills/work/scripts/test_devon_round_prose.py skills/work/scripts/test_dispatch_prose.py skills/work/scripts/test_step_order_prose.py` passes; `rg -c 'DEVON-PROOF' skills/work/references/tess-prompt.md` prints 1.

  ```
  6a. DEVON-PROOF: for every function you test, include all six: (1) two distinct fixture values per asserted field, so a hardcoded value fails; (2) a near-miss negative that shares a prefix, suffix or substring with a positive and must not match, so substring, prefix and basename matching fail; (3) an input with more than one element and an empty input, so first-element, last-element and truncation shortcuts fail; (4) for any guard, filter or classifier, an accept and a reject case of the same shape, so a constant return fails; (5) an error case that asserts the exception or failure signal is surfaced, so a swallowed error or fail-open passes nothing; (6) a dependency assertion that a cwd, environment value or passed argument reached the call or changed a side effect, so dropped plumbing fails. Devon will try exactly these; a draft that lacks one is sent back to you.
  ```

- [ ] Add the CHANGELOG `[Unreleased]` Changed entry `**work**: Tess's prompt names the six exploit classes Devon keeps finding, with the assertion that defeats each, and the step-2.8 quality gate checks for them before a Devon round` (depends on: Phase 1) - Acceptance: `rg -c 'six exploit classes Devon keeps finding' CHANGELOG.md` prints 1.

## Success Criteria

- Over the next batch, the share of Devon rounds recorded as `exploit_fixed` or `exploit:fixed` in `attempts.jsonl` falls below half (today 46 of 47).
- `test_tess_size_limits_prose.py` is green with five tests.
