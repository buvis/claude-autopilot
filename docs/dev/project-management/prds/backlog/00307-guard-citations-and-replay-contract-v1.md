---
catchup: run
design: run
default_model: opus
model_tier_rationale: a new anchoring rule inside a predicate pinned by 564 tests, plus a negation-window fix; both are invented expressions
---

# Make the delegation guard ignore quoted citations and fix the replay exit contract

Source: `docs/dev/project-management/audit-results/loop-efficiency-2026-10-13.md` (Q3); hold stubs 00286, 00287, 00288, 00289, 00290, 00291, 00293, 00294 (all from PRD 00271) and 00300 (from PRD 00278), closed into `done/` on 2026-10-14 against this PRD.

## Problem

PRD 00271's guard v2 ships with known false refusals. The recorded replay of 1172 dispatches (800 per-task) refuses 7 per-task dispatches: one is the pinned deny id and correct, six are legitimate dispatches whose phase name sits inside a quoted run, a backtick, double quote or parenthesis that opens before the name and closes after more text (the spans the guard quoted: `e-invokes \`/autopilot:work\`, w`, `.assertIn("design-solution: <p`, `(parse and plan-tasks) looks fo`). `_candidates` (`hooks/guard_phase_delegation.py:387-402`) treats a wrapper as neutral and consumes a close only when it sits immediately after the name, so a longer quoted run leaves the bare name weakly anchored by the punctuation after it.

Two more defects came from 00271's own rework. `_ordered_to_follow` (`hooks/guard_phase_delegation.py:505-527`) calls `_negated` with the span end as the floor instead of the verb's clause start, so a negation up to four words before the follow verb negates it even across a clause boundary (a false allow), and the same function finds the sentence end with a linear scan at line 511 while every other lookup is a bisect.

The replay script's contract exits 1 when any per-task record is refused, and the pinned deny id `toolu_01Ku4TbcQoeik6ZLf5XkkAuD` in `PINNED_DENY` (`dev/bin/replay_delegation_guard.py:35-42`) buckets per-task, so its correct refusal forces exit 1 (`:164-183`) and PRD 00271's success metric could never be met. The guard is wired in `hooks/hooks.json` and the CHANGELOG claims it without a caveat.

Two exemption findings from `docs/dev/project-management/audit-results/agoge-2026-10-14.md` (packets 15, 16) belong to the same hook. `_AGOGE_PREFIX` (`hooks/guard_phase_delegation.py:220`) exempts every `subagent_type` that starts with `agoge:`, so `agoge:` alone and `agoge:not-a-real-agent` pass a `/autopilot:work for PRD 00300, every task` prompt (confirmed: exit 0 for both, `general-purpose` exit 2); the reviewer exemption is pinned by `test_every_exempt_reviewer_lacks_the_skill_tool` (`hooks/test_guard_phase_delegation.py:405`), the agoge one by nothing. A Cyrillic or Greek o inside `/autopilot:wоrk` passes the guard because the fold, as its comment block in `hooks/guard_phase_delegation.py` documents, leaves letters unfolded (confirmed, exit 0); the harness would not resolve such a skill name, so this is accepted and only stated.

## Solution

Add one anchoring rule: a candidate is a citation, and never anchored, when an unmatched wrapper character from `_WRAP_OPEN` opens earlier in the same clause and its pair from `_WRAP_PAIR` (`hooks/guard_phase_delegation.py:62-71`) closes later in the clause beyond the span end; a wrapper that closes immediately after the name keeps today's handling (`:395-397`). `_ordered_to_follow` passes the follow verb's own clause start (from `_boundaries`, `:405-440`) to `_negated` and finds the sentence end with `bisect_left`. The replay script exempts a refused pinned id from the per-task-refusal clause: exit 1 only for a refused non-pinned per-task, agoge or reviewer record, or an allowed pinned id. The design doc for this PRD records the citation rule as an amendment to the 00271 predicate; the (sentence, id) task-scoping rule that stub 00292 contests is explicitly out of scope and stays as `_is_scoped` documents it (`:443-464`).

The agoge exemption becomes an enumerated roster: `_AGOGE_PERSONAS`, the seven `agoge:` agents (olivia, walter, heidi, judy, wendy, peggy, trudy), replaces the `_AGOGE_PREFIX` test at `hooks/guard_phase_delegation.py:584`, so any other `agoge:` spelling is not exempt. This is the packet's second option rather than its recommended cross-plugin test: the roster fails closed and reads no other plugin's files; a new agoge persona is refused until it is added here, which is the visible failure. The fold's comment block in `hooks/guard_phase_delegation.py` gains one sentence naming the cross-script lookalike (`/autopilot:wоrk`) as an accepted gap.

## Requirements

### Must have
- The six tool-use ids listed in hold stub 00294 are allowed by the guard; the four ids in `PINNED_DENY` (`dev/bin/replay_delegation_guard.py:35-42`) stay refused.
- A phase name wrapped on its own (`` `plan-tasks` ``) behaves as today; only a run that opens before the name and closes after other text is a citation.
- `_negated` is called with the clause start of the follow verb's clause; `hooks/test_guard_phase_delegation_structure.py` keeps passing.
- `_ordered_to_follow` uses `bisect_left` on `sentences`; `hooks/test_guard_phase_delegation_linearity.py` keeps passing.
- `python3 dev/bin/replay_delegation_guard.py` exits 0 on the local corpus with the pinned id refused.
- `test_allow_corpus_ignores_scratch_dispatch_files` (`hooks/test_guard_phase_delegation.py:98-110`) plants its scratch file in the directory `_allow_corpus` globs (monkeypatched) and asserts the committed fixture list, so it can fail (stub 00300: today it writes into `tmp_path`, which the glob never reads).
- `agoge:olivia`, `agoge:walter`, `agoge:heidi`, `agoge:judy`, `agoge:wendy`, `agoge:peggy` and `agoge:trudy` stay exempt; `agoge:` and `agoge:not-a-real-agent` are refused (exit 2) on a `/autopilot:work for PRD 00300, every task` prompt under `_AUTOPILOT_LOOP=1`.
- The fold's comment block in `hooks/guard_phase_delegation.py` names the cross-script lookalike as accepted.
- CHANGELOG `[Unreleased]` Fixed entry under **hooks** that names the false-refusal class closed and the agoge roster.

### Nice to have
- None.

## Implementation

### Module: guard-citations
- **Location**: `hooks/guard_phase_delegation.py` (`_candidates`, `_boundaries`, `_field_delegation`, `_ordered_to_follow`, `_negated`)
- **Responsibility**: a quoted citation of a phase name is not an order to run it; a negation counts only inside the verb's clause; only the seven agoge personas are exempt
- **Exports**: `find_phase_delegation()`, `is_phase_delegation()` (unchanged signatures)
- New symbols: `_cited`, `_AGOGE_PERSONAS`

### Module: replay-contract
- **Location**: `dev/bin/replay_delegation_guard.py`, `dev/bin/test_replay_delegation_guard.py`
- **Responsibility**: exit 1 only on a real regression, never on a pinned id's correct refusal
- **Exports**: `bucket()` (unchanged)
- New symbols: `test_refused_pinned_per_task_id_does_not_fail_the_replay`

### Module: guard-citation-tests
- **Location**: `hooks/test_guard_phase_delegation_citations.py`
- **Responsibility**: pin the six corpus shapes, the immediate-wrapper shape, the clause-bounded negation and the bisect lookup
- **Exports**: none
- New symbols: `test_guard_phase_delegation_citations.py`, `test_backtick_run_opening_before_the_name_is_a_citation`, `test_double_quote_run_is_a_citation`, `test_paren_aside_is_a_citation`, `test_wrapper_closing_right_after_the_name_still_counts`, `test_six_corpus_dispatches_are_allowed`, `test_negation_in_previous_clause_does_not_excuse_follow`, `test_negation_inside_the_verb_clause_still_excuses`, `test_ordered_to_follow_uses_bisect`, `test_each_agoge_persona_is_exempt`, `test_unknown_agoge_prefix_is_not_exempt`

### Dependencies
- guard-citation-tests: No dependencies (foundation)
- guard-citations: Depends on [guard-citation-tests]
- replay-contract: Depends on [guard-citations]

## Tasks

### Phase 0: Foundation
- [ ] Write `hooks/test_guard_phase_delegation_citations.py` with `test_backtick_run_opening_before_the_name_is_a_citation`, `test_double_quote_run_is_a_citation`, `test_paren_aside_is_a_citation`, `test_wrapper_closing_right_after_the_name_still_counts`, `test_six_corpus_dispatches_are_allowed` (the six prompts quoted in hold stub 00294, copied verbatim into the test), `test_negation_in_previous_clause_does_not_excuse_follow`, `test_negation_inside_the_verb_clause_still_excuses`, `test_ordered_to_follow_uses_bisect` (no linear scan: the function body contains `bisect_left` and no `next(`), `test_each_agoge_persona_is_exempt` (the seven names, exit 0) and `test_unknown_agoge_prefix_is_not_exempt` (`agoge:` and `agoge:not-a-real-agent`, exit 2); rewrite `test_allow_corpus_ignores_scratch_dispatch_files` in `hooks/test_guard_phase_delegation.py` to monkeypatch the corpus directory. Register the file in a `[checks]` block of `dev/bin/release-checks` - Acceptance: `uv run --no-project --with pytest python -m pytest -q hooks/test_guard_phase_delegation_citations.py` reports the citation, negation and unknown-agoge tests failing at the task's base commit; `rg -c 'test_guard_phase_delegation_citations.py' dev/bin/release-checks` prints 1.

### Phase 1: Core
- [ ] Implement the citation rule (`_cited` computed in `_candidates`, consumed by `_field_delegation`), the clause-bounded negation in `_ordered_to_follow`, the bisect lookup, the `_AGOGE_PERSONAS` roster in place of the prefix test, and the lookalike sentence in the comment block (depends on: Phase 0) - Acceptance: `uv run --no-project --with pytest python -m pytest -q hooks/test_guard_phase_delegation_citations.py hooks/test_guard_phase_delegation_structure.py hooks/test_guard_phase_delegation_linearity.py hooks/test_guard_phase_delegation_narrowing.py hooks/test_guard_phase_delegation_replay.py hooks/test_guard_phase_delegation.py` passes with no test removed (`rg -c '^def test_' hooks/test_guard_phase_delegation_structure.py` unchanged from the task's base commit).

### Phase 2: Integration
- [ ] Exempt a refused pinned id from the per-task-refusal clause in `dev/bin/replay_delegation_guard.py`, add `test_refused_pinned_per_task_id_does_not_fail_the_replay` to `dev/bin/test_replay_delegation_guard.py`, and add the CHANGELOG entry (depends on: Phase 1) - Acceptance: `uv run --no-project --with pytest python -m pytest -q dev/bin/test_replay_delegation_guard.py` passes; `python3 dev/bin/replay_delegation_guard.py` exits 0 and its per-task line reads `refused 1`; `rg -n 'quoted citation' CHANGELOG.md` prints one hit under `[Unreleased]`.

## Success Criteria

- `python3 dev/bin/replay_delegation_guard.py` exits 0 on the local corpus with `per-task <n> refused 1`.
- The six ids from stub 00294 are allowed and the four pinned ids refused, pinned by `test_six_corpus_dispatches_are_allowed` and `test_each_pinned_deny_id_fails_when_allowed`.
- Hold stubs 00286, 00287, 00288, 00289, 00290, 00291, 00293, 00294 and 00300 were closed against this PRD on 2026-10-14; this PRD's tests are their regression checks.
