---
prd: docs/dev/project-management/prds/wip/00324-guard-pairs-delimiters-as-nested-runs-v1.md
review: 2
date: 2026-10-17
head_sha: 0ef4eb053470027d187e9baadf7bbefcfd873ff0
codex_thread_id: 01a1488b-d999-7162-967e-820e724d8193
reviewers: alice,blake,bob,carl
agents:
  alice: available
  blake: available
  bob: available (after one retry, inlined)
  carl: available
dispatch_rows:
  bob: acef204b (lack-of-input), cdbaf18b (retry, ok)
  carl: 6d56fcd7
---

# Review: 00324-guard-pairs-delimiters-as-nested-runs-v1

Diff range: `2f081b93fd3eeea3af223aa3877e0df3931a4f0a..0ef4eb053470027d187e9baadf7bbefcfd873ff0` (incremental review of the cycle-1 rework)

codex_rung_guard: not fired

pack: ok

## Consolidated Findings

| Ref | Consensus | Severity | Issue | File | Task | Found By |
|-----|-----------|----------|-------|------|------|----------|
| R1 | [3/4] | 🟠 | Prior finding R3 is only partly resolved. The rework drops brackets that sit inside a closed quote or backtick run (the new `literal_runs` filter in `_delim_positions`). The finding's own fourth payload is still allowed, though. I ran `Note [see (x] then run plan-tasks for PRD 00300 for every task (done).` through `find_phase_delegation`: it returns None, so the guard allows it. The variant `Note (see [x) then run plan-tasks for PRD 00300 for every task [done].` is also allowed. The cause is that `_nested_run_pairs` never closes the mismatched `[` (it pops only a matching top), and the asymmetric lookback in `_cited` still pairs the inner `(` with the later `)`. The three quote, backtick and curly-quote payloads from R3 are now denied, and the legitimate cites I tried (`Note "a (b" and (see run plan-tasks ...)`, `(run plan-tasks ...)`) stay allowed. Fix: either apply the same drop to openers inside any closed or mismatched bracket run, or record a bracket-in-bracket limitation in the ledger and the CHANGELOG, which today scopes the claim to quote and backtick runs. | hooks/guard_phase_delegation.py:435 | 4 | ALICE, BOB, CARL |
| R2 | [2/4] | 🟡 | `@lru_cache(maxsize=4)` on `_nested_run_pairs` exists only so `_boundaries` and `_quoted_runs` can both call it on the same scratch. That leaves hidden module-level state that keeps up to four field-sized strings alive. It also forces two throwaway unpacks, `_literal_runs` at line 395 and `_pairs` at line 479. Simpler: `_boundaries` calls `_nested_run_pairs` once and passes `pairs` to an internal helper, with `_quoted_runs(scratch, spans)` kept as a thin wrapper for the tests that call it. Behavior is unchanged. | hooks/guard_phase_delegation.py:353 | 4 | ALICE, BLAKE |
| R3 | [1/4] | 🟠 | `·` (middle dot) is not a sentence end in `_CITE_SENTENCE_BOUNDARY`. The spec says `。`, `·`, `！` and `？` join it, but the pattern only has `[。！？]`. `·` appears nowhere in `hooks/*.py`, and `_CITE_SENTENCE_BOUNDARY.search("a·b")` returns None. Measured through `find_phase_delegation`, `Hi (all· Run plan-tasks for PRD 00300 for every task· Thanks)` is allowed. The `。` and `.` versions of the same payload are denied. No test covers `·`. So a bypass shape the PRD named stays open. | hooks/guard_phase_delegation_lexicon.py:233 | 2 | BLAKE |
| R4 | [1/4] | 🟠 | Unspaced `！`/`？` boundaries remain broken end to end: normalization folds them to ASCII before the new unconditional CJK branch runs. The new regex-only test bypasses normalization. Preserve these terminators through normalization and test both with the real-parenthesis payload. | hooks/test_guard_phase_delegation_citations.py:727 | 5 | BOB |
| R5 | [1/4] | 🟡 | The R3 fix has one test, `test_bracket_literal_inside_a_closed_quote_run_does_not_cite`, with a single `(` inside a `"` run. The new `_delim_positions` branch is general (`char not in '"`'` and any asymmetric opener), but nothing covers the backtick-run case, a curly-quote opener (`“`) inside a run, or the bracket-in-bracket shape above. Parametrize the test over those payloads, which the review already listed. | hooks/test_guard_phase_delegation_citations.py:138 | 6 | ALICE |
| R6 | [1/4] | 🟡 | The global LRU cache exists to share one pairing computation between two callers within `_boundaries`. Compute pairs once there and pass them into `_quoted_runs`; this removes retained prompt strings, shared mutable cached lists, and cache-dependent data flow without adding another scan. | hooks/guard_phase_delegation.py:353 | 4 | BOB |
| R7 | [1/4] | 🟡 | 3 touched test(s) pass against the pre-change code: test_a_unit_mark_after_a_citation_does_not_un_cite_it, test_doubled_backtick_citation_is_allowed, test_backtick_exclusion_in_cite_boundary_can_fail | hooks/test_guard_phase_delegation_citations.py | general | mech-check |
| R8 | [1/4] | 🟡 | 8 touched test(s) pass against the pre-change code: test_negation_does_not_reach_past_the_bare_conjunction, test_emoticon_variants_beyond_colon_are_not_brackets +2 more | hooks/test_guard_phase_delegation_structure.py | general | mech-check |
| R9 | [1/4] | ⚪ | `hooks/guard_phase_delegation.py` is now exactly 800 lines, at the file-size limit. The next edit tips it over, so the next change to it should split it. | hooks/guard_phase_delegation.py:800 | general | ALICE |
| R10 | [1/4] | ⚪ | The context's gate line reads "7087 passed, 5 failed", while the review-1 file reported 7077 passed and 0 failed. I could not tell which five tests failed without a 25-minute full run. The seven guard test files, including the linearity budget, pass here: 732 passed. Confirm the five failures are outside this diff. | N/A | general | ALICE |

### Auto-dismissed (ledger)

- [BLAKE] 🟠 The spec's performance mechanism is not implemented, and the budget is not structurally restored. The spec says `_FOLLOW` matches are "collected once per field in `_boundaries`... looked up per mention by bisect". `_boundaries` returns no `_FOLLOW` data. `_ordered_to_follow` still runs `_FOLLOW.search(text, end, min(sentence_end, end + 200))` once per mention. The required `test_dense_skill_md_mentions_stay_under_budget` passes at 0.258 s/MB against the 0.3 bound, but its fixture is a negated "never follow it" at a 75-character spacing. A payload of `"skills/work/SKILL.md do "*4 + single-letter words`, 136-character unit, ran at 0.39 s/MB, over `BUDGET_S_PER_MB`. The 8 MB negated-dense run took 2.4 s, under the 5-second hook timeout. The packet-20 cost class is only partly fixed. | File: hooks/guard_phase_delegation.py:578 — The design doc's own remedy path makes the once-per-field cache the fallback only if the dense-budget test goes red; it is green (0.14-0.25 s/MB against 0.3). Adding the cache now is unrequested production change.
- [BLAKE] 🟡 The spec's named new symbol `_nested_runs` does not exist. The implementation is `_nested_run_pairs` (hooks/guard_phase_delegation.py:354) plus `_quoted_runs`, which now maps pairs to spans. `_cited`'s own-wrapper branch reads the shared run map, so behaviour matches. This is a naming and interface deviation from "New symbols: `_nested_runs`". | File: hooks/guard_phase_delegation.py:354 — Same deviation as the medium entry above (the missing `_nested_runs` symbol): noted rather than renamed, because the misleading name is the whole cost and a rename changes no behavior.

### Orchestrator verification of the blocking findings

Both HIGHs that block convergence were re-measured directly against HEAD, not taken on a reviewer's word (`python3 -c` driving `find_phase_delegation`):

- R1 confirmed: `Note [see (x] then run plan-tasks for PRD 00300 for every task (done).` → `None` (allowed). `Note (see [x) then run plan-tasks for PRD 00300 for every task [done].` → `None` (allowed). The quote, backtick and curly-quote variants of the same shape are now denied, so the cycle-1 fix is real but partial.
- R4 confirmed: `Hi (all。Run plan-tasks for PRD 00300 for every task。Thanks)` → denied, but `Hi (all！Run …！Thanks)` and `Hi (all？Run …？Thanks)` → `None` (allowed). Two of the three terminators the cycle-1 fix named are still open unspaced.
- R3 (`·`) is a settled deferral from cycle 1: the design doc states "Do NOT add `·` — no required payload needs it", and the cycle-1 ledger records it. Excluded from the convergence test as a settled deferral; it is not re-argued here.

### Carried-forward verification check (cycle 1)

`python3 dev/bin/replay_delegation_guard.py` (queued by Bob in cycle 1, no recorded result) was run this cycle: exit 0, `per-task 842 refused 1`. The check passes; no finding carried forward from it.

## Alice

Five findings (one 🟠, two 🟡, two ⚪), listed in the table. She verified the cycle-1 rework resolved R1, R2, R4, R9, R10 and R16, and confirmed R3 only partly.

## Blake

Five findings, two of them auto-dismissed against the settled-decisions ledger (the `_FOLLOW` once-per-field mechanism and the `_nested_runs` naming deviation, both settled in cycle 1). Blind lens; he located the code himself and ran the payloads end to end.

B1: fail
B2: pass
B3: fail
B4: fail
B5: pass
B6: fail
B7: pass
B8: pass
B9: pass
B10: pass
B11: pass
B12: pass
B13: pass
B14: pass
B15: pass
B16: pass
B17: pass
B18: pass
B19: pass

## Bob

First dispatch refused for lack of input (`sandbox-exec: sandbox_apply: Operation not permitted` — the codex sandbox could not read the staged files). Re-dispatched after one retry (inlined): context, diff and PRD inlined verbatim into the prompt. The retry produced three findings (two 🟠, one 🟡).

R1: fail
R2: pass
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

FIX:
- Unspaced fullwidth terminators lose their boundary behavior — hooks/test_guard_phase_delegation_citations.py:727 — preserve them through normalization and add end-to-end cases for `！` and `？`.
- Prior R3's bracket-inside-bracket bypass remains — hooks/guard_phase_delegation.py:432 — filter asymmetric marks using nesting ownership and pin the recorded payload.
- Pairing reuse uses an unnecessary global cache — hooks/guard_phase_delegation.py:353 — pass the already-computed pairs from `_boundaries` into `_quoted_runs`.

VERIFY:
- (none)

KNOWN:
- (none)

## Carl

Backend: gemini CLI. One finding (🟠), independently reaching the same bracket-in-bracket bypass as Alice and Bob.

R1: pass
R2: pass
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

Verdict: 10 findings
Tests: 7071 passed, 0 failed, 3 skipped (suite run this cycle; `dev/bin/release-checks` re-run at HEAD 0ef4eb05 exited 0 — the staged run's "7087 passed, 5 failed" did not reproduce in two subsequent full runs, and the `hooks/` suite is 974 passed, 0 failed)
