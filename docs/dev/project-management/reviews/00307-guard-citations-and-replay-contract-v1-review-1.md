---
prd: docs/dev/project-management/prds/wip/00307-guard-citations-and-replay-contract-v1.md
review: 1
date: 2026-10-15
head_sha: f7e282223f55f8a891a5733f61f6715f21b06d93
codex_thread_id: 0199e1a3-c80e-7c21-b37e-2cb6a3ad0a9f
reviewers: alice,blake,bob,carl
agents:
  alice: available
  blake: available
  bob: available
  carl: available
dispatch_rows:
  bob: 0d0705de
  carl: 9bed4133
---

# Review: 00307-guard-citations-and-replay-contract-v1

Diff range: `82b0cd561b7edb38ec8063cf402ba9941cd75302..f7e282223f55f8a891a5733f61f6715f21b06d93`

codex_rung_guard: not fired

## Review Summary

Reviewed: 3 completed tasks
PRDs checked: 00307-guard-citations-and-replay-contract-v1

### Agent Status

- Alice: ✅ Available (consensus lens, legacy engine)
- Blake: ✅ Available (blind lens, PRD-only)
- Bob: ✅ Available (doubt lens, codex) — after one retry (inlined). The first
  run refused for lack of readable input (`sandbox_apply: Operation not
  permitted`, all R-verdicts failed on unavailable evidence); the one-retry
  budget was spent on the inlined retry prompt
  (`docs/dev/tmp/bob-prompt-20261015-0416-retry.md`, 172 KB), which produced a
  full review. (format warning) his issue lines carried a markdown `- ` list
  prefix the consolidator does not parse; they were mechanically normalized to
  the pinned shape before consolidation, with no text changed.
- Carl: ✅ Available (gemini backend: copilot)

Degradations this cycle: the engram context pack failed to build
(`engram pack exit 1: sqlite3.OperationalError: attempt to write a readonly
database`), so every prompt carried `(no pack available this cycle)`. The
review is degraded in precedent, not in lens coverage.

## Consolidated Findings

| Ref | Consensus | Severity | Issue | File | Task | Found By |
|-----|-----------|----------|-------|------|------|----------|
| R1 | [3/4] | 🔴 | PRD must-have unmet: two of the six stub-00294 ids are still refused and the replay still exits 1. I ran `python3 dev/bin/replay_delegation_guard.py` and got `per-task 755 refused 3` and exit 1, where the PRD requires `refused 1` and exit 0. The refused ids are toolu_011UqbqFtUDPuSeCiLLgMvEg (span "`Run the work phase for PRD 0") and toolu_013ePUKbLDE7DLnbnGmgszzR (span "parse and plan-tasks) looks fo"). The cause is that `_cited` bounds the close search and the opener search by sentence (`_SENTENCE_BOUNDARY` includes "."). In the first payload the backtick run is `Run the work phase for PRD 00300.` and its close sits after the period. In the second, "(cli/frontmatter.parse and plan-tasks)" has a "." inside `frontmatter.parse`, so the "(" falls before `sentence_start`. Task 3's own assumption note records this and defers it ("flagged for the PRD-level review"). The CHANGELOG entry therefore claims a fix that does not hold on the real corpus. | hooks/guard_phase_delegation.py:539 | 2 | ALICE, BLAKE, CARL |
| R2 | [3/4] | 🔴 | `test_six_corpus_dispatches_are_allowed` passes on invented prompts, so it cannot catch the two real failures above. The PRD says to copy the six prompts verbatim, but `_CORPUS` uses made-up sentences that contain only the span text. The assumptions ledger admits this for cases c2 and c3. For case 1 the real span is "e-invokes `/autopilot:work`, w", with the close right after the name, but the test uses "`/autopilot:work, which then ... next task`", a different shape. Cases 5 and 6 omit the "." and the period-then-close shape of the real payloads. The test is green while the real replay is red. It should be rebuilt on payload shapes that match the corpus: a "." inside the parenthesised run, and a sentence-ending period inside the backtick run. | hooks/test_guard_phase_delegation_citations.py:67 | 1 | ALICE, BLAKE, CARL |
| R3 | [2/4] | 🟡 | The PRD requires bisecting `sentences`, but the sentence lookup still uses `next(...)`; the new bisect only locates the verb's clause. Despite the conflicting implementation sketch, this must-have remains unmet. Replace the sentence scan with bisect and make the test distinguish those two lookups. | hooks/guard_phase_delegation.py:529 | 2 | BOB, CARL |
| R4 | [1/4] | 🔴 | The replay does not exit 0 and does not read `per-task <n> refused 1`. I ran `python3 dev/bin/replay_delegation_guard.py` on the local corpus. It exited 1 with `per-task 755 refused 3`. Two of the three are non-pinned refusals: toolu_011UqbqFtUDPuSeCiLLgMvEg (autopilot:worker-opus, span "`Run the work phase for PRD 0") and toolu_013ePUKbLDE7DLnbnGmgszzR (general-purpose, span "parse and plan-tasks) looks fo"). This fails the Phase 2 acceptance and the first Success Criterion. | dev/bin/replay_delegation_guard.py | 3 | BLAKE |
| R5 | [1/4] | 🟠 | The `_cited` rule is not the rule the spec states, and it still misses real shapes. The spec says an unmatched opener earlier in the same clause, closing later in the clause beyond the span end. The code uses the sentence for the close and for asymmetric openers, but a sentence or clause boundary inside the quoted run still defeats it (the two failures above). Read literally, the spec's clause-bounded rule would fail the same two ids, so the spec and its own success criterion conflict. The implementer did not reconcile this or record it. | hooks/guard_phase_delegation.py:539 | 2 | BLAKE |
| R6 | [1/4] | 🟠 | Balanced quotes can hide an unquoted order: `The log says "ready, done" then run plan-tasks for PRD 00300 and print "ok".` Clause-local parity misreads the quote after `done` as an opener. Track delimiter pairing consistently across clause boundaries and add this denial regression. | hooks/guard_phase_delegation.py:567 | 2 | BOB |
| R7 | [1/4] | 🟠 | Citation checking remains quadratic for repeated anchored citations in one sentence, such as repeated `"run plan-tasks for PRD 00300"`. Every candidate passes anchoring, rescans prefixes/suffixes, and continues. Precompute wrapper positions/state once and add a scaling regression covering anchored citations. | hooks/guard_phase_delegation.py:561 | 2 | BOB |
| R8 | [1/4] | 🟠 | The supplied live-replay record still reports exit 1 for required allowed IDs `toolu_011UqbqFtUDPuSeCiLLgMvEg` and `toolu_013ePUKbLDE7DLnbnGmgszzR`. Run `python3 dev/bin/replay_delegation_guard.py` on the reviewed revision against that corpus; require exit 0, no non-pinned refusals, preserved pinned denials, and reconcile the required `refused 1` count with deduplication. | docs/dev/project-management/meta/assumptions.md:27 | general | BOB |
| R9 | [1/4] | 🟡 | `_cited` departs from the pinned contract and widens the false-allow surface. The contract bounds the close search at `clause_end` and the asymmetric opener search at `clause_start`. The code uses `sentence_end` and `sentence_start` (call site at hooks/guard_phase_delegation.py:631), and adds two more departures: a six-argument signature, and `'` left out of the wrapper set. Any "(" earlier in the sentence with a ")" later now excuses a real order across clause boundaries. The departures are recorded only in meta/assumptions.md. If the fix for the first finding keeps sentence-wide scope, the contract and design doc need amending, and the real-order-inside-parens trade-off needs a pinned test (for example, a real order after "(a, b)" that is not cited). | hooks/guard_phase_delegation.py:539 | 2 | ALICE |
| R10 | [1/4] | 🟡 | `_cited` is computed and consumed inside `_field_delegation` (guard_phase_delegation.py:631) rather than in `_candidates`. The spec says "`_cited` computed in `_candidates`, consumed by `_field_delegation`". This is a minor structural deviation. | hooks/guard_phase_delegation.py:397 | 2 | BLAKE |
| R11 | [1/4] | 🟡 | The citation rule makes any quote or bracket before the name a bypass of the guard. A prompt such as `"note: /autopilot:work for PRD 00300, every task"` is now allowed. This is inherent in the spec, but the PRD does not mention the fail-open surface. | hooks/guard_phase_delegation.py:539 | 2 | BLAKE |
| R12 | [1/4] | 🟡 | Single-quoted citations are excluded despite the explicit contract: `The log reads 'run plan-tasks for PRD 00300' verbatim.` remains refused. Restore single-quote support, distinguish word-internal apostrophes, and add coverage. | hooks/guard_phase_delegation.py:561 | 2 | BOB |
| R13 | [1/4] | 🟡 | The first corpus fixture moves the closing backtick from immediately after `/autopilot:work` to the sentence tail, changing the supplied regression shape. Restore the exact span for `toolu_015DM18ubZLJZbA65ozvuw8c` and cover that tightly wrapped narrative without weakening standalone-label denial. | hooks/test_guard_phase_delegation_citations.py:69 | 1 | BOB |
| R14 | [1/4] | 🟡 | Reconstructing wrapper tuple on every _cited call adds unnecessary overhead; hoist to module-level constant | hooks/guard_phase_delegation.py:550 | 2 | CARL |
| R15 | [1/4] | 🟡 | 1 touched test(s) pass against the pre-change code: test_allow_corpus_ignores_scratch_dispatch_files | hooks/test_guard_phase_delegation.py | general | mech-check |
| R16 | [1/4] | 🟡 | 13 touched test(s) pass against the pre-change code: test_wrapper_closing_right_after_the_name_still_counts, test_already_closed_aside_before_the_name_is_not_a_citation, test_negation_inside_the_verb_clause_still_excuses +7 more | hooks/test_guard_phase_delegation_citations.py | general | mech-check |
| R17 | [1/4] | ⚪ | `test_ordered_to_follow_uses_bisect` asserts on `inspect.getsource` strings. That is brittle, but the PRD specifies it. The behavioural twin `test_negation_in_previous_clause_does_not_excuse_follow` does bind the intent. | hooks/test_guard_phase_delegation_citations.py:119 | 1 | ALICE |
| R18 | [1/4] | ⚪ | The scratch test (hooks/test_guard_phase_delegation.py:98) monkeypatches FIXTURES to a tmp_path that holds copies of the committed fixtures. It can fail and asserts the committed list, so it is acceptable. | hooks/test_guard_phase_delegation.py:98 | 1 | BLAKE |

Rows R15 and R16 are the mechanical fail-first replay block absorbed per SKILL
step 6. R16 is not merely mechanical noise here: it is the same defect R2
describes, measured independently — the new citation tests pass against the
pre-change code, so they do not pin this change.

### Orchestrator verification (not a lens)

Before dispatching the reviewers I ran `python3 dev/bin/replay_delegation_guard.py`
myself and got `per-task 755 refused 3`, exit 1. I also read
`hooks/guard_phase_delegation.py:529` directly and confirmed
`sentence_end = next((s for s in sentences if s >= end), len(text))` — the linear
scan the PRD must-have requires replaced by `bisect_left`. R1/R4 and R3 are
therefore confirmed facts, not reviewer claims. Blake's "verified as met" bullet
asserting `_ordered_to_follow` uses `bisect_left` is correct only for the clause
lookup at :534 and wrong for the sentence lookup at :529.

## Alice

[ALICE] 🟠 PRD must-have unmet: two of the six stub-00294 ids are still refused and the replay still exits 1 (`per-task 755 refused 3`, exit 1; PRD requires `refused 1` and exit 0). Cause: `_cited` bounds the close search and the opener search by sentence (`_SENTENCE_BOUNDARY` includes "."). | File: hooks/guard_phase_delegation.py:539 | Task: 2
[ALICE] 🟠 `test_six_corpus_dispatches_are_allowed` passes on invented prompts, so it cannot catch the two real failures. The PRD says to copy the six prompts verbatim; `_CORPUS` uses made-up sentences containing only the span text. | File: hooks/test_guard_phase_delegation_citations.py:67 | Task: 1
[ALICE] 🟡 `_cited` departs from the pinned contract and widens the false-allow surface (sentence-scoped instead of clause-scoped; six-argument signature; `'` dropped from the wrapper set). | File: hooks/guard_phase_delegation.py:539 | Task: 2
[ALICE] ⚪ `test_ordered_to_follow_uses_bisect` asserts on `inspect.getsource` strings — brittle, but the PRD specifies it. | File: hooks/test_guard_phase_delegation_citations.py:119 | Task: 1

Alice ran the citations, dispatch and replay test files: 65 passed. The replay corpus run is the check that fails.

R1: fail
R2: fail
R3: pass
R4: pass
R6: pass
R7: pass
R8: pass
R9: fail
R10: pass
R11: pass
R12: pass
R13: pass

## Blake

[BLAKE] 🔴 The replay does not exit 0 and does not read `per-task <n> refused 1`; it exited 1 with `per-task 755 refused 3`, two of them non-pinned. Fails the Phase 2 acceptance and the first Success Criterion. | File: dev/bin/replay_delegation_guard.py | Task: 3
[BLAKE] 🔴 Two of the six stub-00294 ids that must be allowed are still refused on their real recorded prompts; both exit 2 when replayed through the guard. | File: hooks/guard_phase_delegation.py:539 | Task: 2
[BLAKE] 🔴 `test_six_corpus_dispatches_are_allowed` does not use the six prompts verbatim; synthetic prompts with no inner "." pass while the real prompts fail. No test uses the real tool-use ids. | File: hooks/test_guard_phase_delegation_citations.py:67 | Task: 1
[BLAKE] 🟠 The `_cited` rule is not the rule the spec states, and it still misses real shapes; the spec and its own success criterion conflict, unreconciled. | File: hooks/guard_phase_delegation.py:539 | Task: 2
[BLAKE] 🟡 `_cited` is computed and consumed inside `_field_delegation` rather than in `_candidates`, against the spec. | File: hooks/guard_phase_delegation.py:397 | Task: 2
[BLAKE] 🟡 The citation rule makes any quote or bracket before the name a bypass of the guard; the PRD does not mention this fail-open surface. | File: hooks/guard_phase_delegation.py:539 | Task: 2
[BLAKE] ⚪ `_AGOGE_PREFIX` is kept for the replay's `bucket()`; a pinned id refused in the agoge or reviewer bucket is also exempted, broader than "per-task". Acceptable but unpinned by a test. | File: dev/bin/replay_delegation_guard.py:168 | Task: 3
[BLAKE] ⚪ The scratch test monkeypatches FIXTURES to a tmp_path holding copies of the committed fixtures. It can fail and asserts the committed list, so it is acceptable. | File: hooks/test_guard_phase_delegation.py:98 | Task: 1

Blake verified as met: the `_AGOGE_PERSONAS` roster replaces the prefix test; the
fold comment names the cross-script lookalike; the replay script exempts a
refused pinned id; `dev/bin/release-checks:145` registers the new test file once;
the CHANGELOG entry sits under `[Unreleased]` Fixed and contains "quoted
citation"; 680 tests across the guard and replay suites pass. His further claim
that `_ordered_to_follow` uses `bisect_left` is correct for the clause lookup
only — see Orchestrator verification above.

B1: fail
B2: pass
B3: pass
B4: pass
B5: pass
B6: pass
B7: pass
B8: pass
B9: pass
B10: pass
B11: pass
B12: pass
B13: pass
B14: pass
B15: pass
B16: fail
B17: pass
B18: pass
B19: pass

## Bob

Bob ran after one retry (inlined).

FIX:
[BOB] 🟠 Balanced quotes can hide an unquoted order: `The log says "ready, done" then run plan-tasks for PRD 00300 and print "ok".` Clause-local parity misreads the quote after `done` as an opener. | File: hooks/guard_phase_delegation.py:567 | Task: 2
[BOB] 🟠 Citation checking remains quadratic for repeated anchored citations in one sentence. Precompute wrapper positions/state once and add a scaling regression. | File: hooks/guard_phase_delegation.py:561 | Task: 2
[BOB] 🟡 Single-quoted citations are excluded despite the explicit contract. Restore single-quote support, distinguish word-internal apostrophes, add coverage. | File: hooks/guard_phase_delegation.py:561 | Task: 2
[BOB] 🟡 The first corpus fixture moves the closing backtick from immediately after `/autopilot:work` to the sentence tail, changing the supplied regression shape. | File: hooks/test_guard_phase_delegation_citations.py:69 | Task: 1
[BOB] 🟡 The PRD requires bisecting `sentences`, but the sentence lookup still uses `next(...)`; the new bisect only locates the verb's clause. This must-have remains unmet. | File: hooks/guard_phase_delegation.py:529 | Task: 2

VERIFY:
[BOB] 🟠 The supplied live-replay record still reports exit 1 for required allowed IDs `toolu_011UqbqFtUDPuSeCiLLgMvEg` and `toolu_013ePUKbLDE7DLnbnGmgszzR`. Run `python3 dev/bin/replay_delegation_guard.py`; require exit 0, no non-pinned refusals, preserved pinned denials. | File: docs/dev/project-management/meta/assumptions.md:27 | Task: general

KNOWN:
- (none)

R1: fail
R2: fail
R3: pass
R4: pass
R6: pass
R7: pass
R8: pass
R9: fail
R10: pass
R11: pass
R12: pass
R13: pass

D1: pass
D2: pass
D3: pass
D4: pass
D5: pass

## Carl

Backend: copilot (gemini runner).

[CARL] 🔴 Corpus replay exits 1 with refused 3: toolu_011UqbqFtUDPuSeCiLLgMvEg and toolu_013ePUKbLDE7DLnbnGmgszzR still refused due to sentence-boundary truncation on periods | File: hooks/guard_phase_delegation.py:633 | Task: 2
[CARL] 🟠 test_six_corpus_dispatches_are_allowed uses sanitized prompts lacking transcript periods, masking sentence-boundary truncation on real citations | File: hooks/test_guard_phase_delegation_citations.py:89 | Task: 1
[CARL] 🟡 _ordered_to_follow uses linear next() scan on sentences instead of bisect_left, violating PRD Must-Have requirement | File: hooks/guard_phase_delegation.py:524 | Task: 2
[CARL] 🟡 Reconstructing wrapper tuple on every _cited call adds unnecessary overhead; hoist to module-level constant | File: hooks/guard_phase_delegation.py:550 | Task: 2

R1: fail
R2: pass
R3: pass
R4: fail
R6: pass
R7: pass
R8: pass
R9: fail
R10: pass
R11: pass
R12: pass
R13: pass

Verdict: 18 findings
Tests: 6715 passed, 0 failed, 34 skipped (suite run this cycle)
