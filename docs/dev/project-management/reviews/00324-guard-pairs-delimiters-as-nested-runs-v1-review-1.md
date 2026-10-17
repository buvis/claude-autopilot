---
prd: docs/dev/project-management/prds/wip/00324-guard-pairs-delimiters-as-nested-runs-v1.md
review: 1
date: 2026-10-17
head_sha: 2f081b93fd3eeea3af223aa3877e0df3931a4f0a
codex_thread_id: 01a1488b-d999-7162-967e-820e724d8193
reviewers: alice,blake,bob,carl
agents:
  alice: available
  blake: available
  bob: available
  carl: available
dispatch_rows:
  bob: 31aeb52c
  carl: 7ebd7ad2
---

# Review: 00324-guard-pairs-delimiters-as-nested-runs-v1

Diff range: `1228d38bfd0cbc61223001f545373e4f47de71e8..2f081b93fd3eeea3af223aa3877e0df3931a4f0a`

codex_rung_guard: not fired

Notes on this cycle:

- `state.work_start_sha` was absent at review entry (the build gate never captured it). It was set to `1228d38b` — the parent of task 1's commit `447343f5` — so the diff range spans this PRD's whole work range.
- Bob's output used bullet-prefixed issue lines (`- [BOB] …`), which `consolidate_findings.py` does not parse; his four findings were silently dropped on the first run. The bullets were stripped (text otherwise verbatim) and consolidation re-run, so all four appear below.
- `consolidate_findings.py` merged Blake's ⚪ `_negated` over-reach note (`hooks/guard_phase_delegation.py:639`) into R3 by suffix-stripped citation match. The note is retained here in Blake's section; it is informational (fails closed).
- The mechanical fail-first `[MECH]` line (`test_backtick_exclusion_in_cite_boundary_can_fail` passes against base) is the same fact as R15/R11; `mech-check` is appended as a finder to R15.
- pack: ok. No settled-decisions ledger exists yet (cycle 1), so no `--ledger` filtering ran.

## Consolidated Findings

| Ref | Consensus | Severity | Issue | File | Task | Found By |
|-----|-----------|----------|-------|------|------|----------|
| R1 | [3/4] | 🟡 | `_quoted_runs` is 55 lines, over the 50-line limit (mechanical facts block). Split the token walk that builds `pairs` (lines 356-385) from the span merge walk that builds `runs` (lines 386-402) into two helpers. The behavior stays the same. | hooks/guard_phase_delegation.py:348 | 2 | ALICE, BOB, CARL |
| R2 | [2/4] | 🟠 | CJK terminators only end the citation window when whitespace or a closer follows, but CJK text is normally written without spaces. `Hi (all。Run plan-tasks for PRD 00300 for every task。Thanks)` with a real `)` is still allowed (I ran it), while the same text with a space after each `。` is denied. Shape (3) is closed only for the PRD's spaced payload. Fix: let `。！？` end the sentence unconditionally, since they have no dotted-identifier ambiguity, e.g. an extra branch `[。！？]` outside the `(?=\s|...)` lookahead. | hooks/guard_phase_delegation_lexicon.py:230 | 2 | ALICE, BLAKE |
| R3 | [1/4] | 🟠 | The nested-run rule is not applied to asymmetric openers in `_cited`. Its first loop looks for the nearest `(`, `[`, `“` and so on before the name using raw mark positions, ignoring the run map. A bracket opener that sits inside an already-closed quote or backtick run therefore still pairs with a later unrelated closer and hides the order. This is the same shape as payload (1), where the spec requires an opener inside a closed run to close only inside it. All of these are allowed: `Note "see (x" then run plan-tasks for PRD 00300 for every task, report (done).`, the same with a backtick run, `Note "see “x" then run plan-tasks … report ”done”.`, and `Note [see (x] then run plan-tasks for PRD 00300 for every task (done).`. | hooks/guard_phase_delegation.py:612 | 2 | BLAKE |
| R4 | [1/4] | 🟡 | Several new behaviors have no test. (a) `then` and `but` are untested although the test name and PRD title say "and/then/but"; only `and` is exercised. (b) `！` and `？` are untested; only `。` is. (c) `;` and `=` emoticons are untested; only `:(` and `:)` are. (d) A single backtick inside a doubled-backtick span (the length-pairing rule) and a bracket or quote opener deferred while another class is open have no test. (e) The nested-bracket chain and innermost-pair selection in the merge walk have no test. Add one parametrized case each. | hooks/test_guard_phase_delegation_structure.py:555 | 1 | ALICE |
| R5 | [1/4] | 🟡 | The diff carries unrelated formatter reflow that no task asked for. Examples: the `_is_per_task_persona` expression, `text[end : end + 1]` slice spacing in `_candidates`, `_is_scoped`, `_quote` and `_field_delegation`, the exploded `_strongly_anchored` and `_weakly_anchored` signatures, the `main()` print calls, and removal of seven re-exported imports (`_MASKED_IN_SPAN`, `_PHASE_BARE`, `_PHASE_CONCEPT`, `_PHASE_SKILL`, `_WRAP`, `_WRAP_CLOSE`, `_WRAP_OPEN`). This is the loupe end-of-turn pass the project memory says to check out and never commit. Revert these hunks so every changed line traces to the PRD. | hooks/guard_phase_delegation.py:148 | 2 | ALICE |
| R6 | [1/4] | 🟡 | `_find_skill_md_paths` was rewritten (last-token `rsplit`) although neither the task contract nor the design names it. I judge it equivalent, because `_SKILL_MD_PATH` has no whitespace and is `$`-anchored, and it is what makes the dense budget pass. But the design says "measure first, make no further production change" and the PRD asks for `_FOLLOW` matches to be collected once per field. Record in the PRD or ledger that the budget was met this way instead. | hooks/guard_phase_delegation.py:162 | 2 | ALICE |
| R7 | [1/4] | 🟡 | `_FOLLOW` matches are not collected once per field and looked up by bisect, as the spec requires. `_ordered_to_follow` still calls `_FOLLOW.search(text, end, min(sentence_end, end + 200))` for each `SKILL.md` mention, and `_boundaries` returns no `_FOLLOW` match list. The budget is met anyway (0.14 to 0.25 s/MB against the 0.3 bound), but the 0.25 s/MB case leaves little headroom and the specified design is absent. | hooks/guard_phase_delegation.py:562 | 2 | BLAKE |
| R8 | [1/4] | 🟡 | The spec's new symbol `_nested_runs` does not exist. The pairing was folded into `_quoted_runs`, which keeps its old name and gains an inline stack-less state machine (one quote slot, one backtick slot, a bracket stack). `rg _nested_runs hooks` finds nothing outside the spec. The stated interface (New symbols: `_nested_runs`) is not met, and the "one scan with a stack of open delimiters" is only partly met. | hooks/guard_phase_delegation.py:348 | 2 | BLAKE |
| R9 | [1/4] | 🟡 | CJK boundary coverage is masked by the emoticon fix: removing all three new terminators still leaves this fixture denied. Add cases with an ordinary closing `)` and parameterize `。`, `！`, `？`. | hooks/test_guard_phase_delegation_citations.py:698 | 1 | BOB |
| R10 | [1/4] | 🟡 | The `and_then_but` test exercises only `and`; existing `then` controls contain commas that already stop negation. Parameterize the new payloads over all three conjunctions without commas. | hooks/test_guard_phase_delegation_structure.py:560 | 1 | BOB |
| R11 | [1/4] | 🟡 | The supplied fail-first replay reports that `test_backtick_exclusion_in_cite_boundary_can_fail` passes against base, contradicting Phase 0's eight-red requirement. Retained as an existing-invariant regression test: making unchanged correct behavior fail is outside a behavior-preserving review fix. | hooks/test_guard_phase_delegation_citations.py:721 | 1 | BOB |
| R12 | [1/4] | ⚪ | The design and PRD call the new function `_nested_runs` ("New symbols: `_nested_runs`"), but the code keeps the name `_quoted_runs` while it now pairs brackets, backticks and quotes. The name misleads, though callers and `test_citation_checking_reads_the_run_map_once_per_candidate` stay consistent. Rename it, or note the deviation in the PRD. | hooks/guard_phase_delegation.py:348 | 2 | ALICE |
| R13 | [1/4] | ⚪ | `·` is not added to `_CITE_SENTENCE_BOUNDARY`, although the PRD Solution and Problem sections name it. The task contract and design deliberately drop it, so this is a recorded deviation and not a defect. | hooks/guard_phase_delegation_lexicon.py:230 | 2 | ALICE |
| R14 | [1/4] | ⚪ | `_NEGATION_REACH_END` newly denies coordinated negated lists such as `Never run work and plan-tasks for PRD 00300 for every task.`, which the 5-word window previously allowed. This is the safe direction for a guard. The design's Risks section does not list it. | hooks/guard_phase_delegation.py:638 | 2 | ALICE |
| R15 | [2/4] | ⚪ | `test_backtick_exclusion_in_cite_boundary_can_fail` passes against the pre-change code (the replay [MECH] line), so it is not red-first. That is intended: it mutates the shipped pattern and asserts the verdict flips. It would fail if the exclusion were deleted, because of its `broken_pattern != original_pattern` assertion. Task 1's "eight tests fail at base" acceptance therefore holds for seven only. | hooks/test_guard_phase_delegation_citations.py:1255 | 1 | ALICE, mech-check |
| R16 | [1/4] | ⚪ | The CHANGELOG entry names the five closed shapes and says the scan stays linear, but it does not mention the doubled-backtick citation fix or the `·` terminator. The PRD asked it to name the five shapes and the restored linear budget, so the doubled-backtick omission is minor. | CHANGELOG.md:46 | 3 | BLAKE |
| R17 | [1/4] | ⚪ | Cannot statically verify: acceptance suites, recorded replay, and timing limits. Run both Task 2 pytest commands and `python3 dev/bin/replay_delegation_guard.py`; confirm per-task `refused 1`, then measure the dense fixture at 1 MB against `BUDGET_S_PER_MB` and at 8 MB against five seconds. | N/A | 2 | BOB |

## Alice

Consensus lens, implementation-aware. Verification she ran: the five guard pytest files, 646 passed; `dev/bin/replay_delegation_guard.py` → `per-task 842 refused 1`; all five PRD payloads and their controls give the expected verdicts.

Findings: R1, R4, R5, R6, R12, R13, R14, R15 (see the table).

R1: fail
R2: pass
R3: pass
R4: pass
R6: pass
R7: pass
R8: pass
R9: pass
R10: pass
R11: pass
R12: fail
R13: pass

## Blake

Blind lens (PRD only, no diff). Checks he ran: all 717 tests in the seven named guard test files pass; `python3 dev/bin/replay_delegation_guard.py` exits 0 with `per-task 842 refused 1`; payloads (1)-(5) are all denied and their controls keep their results; a 1 MB dense `SKILL.md` payload ran in 0.14-0.25 s and an 8 MB payload in 1.0-2.0 s (under the 5 s hook timeout); the CHANGELOG `[Unreleased]` entry exists under **hooks**.

Findings: R2, R3, R7, R8, R16 (see the table), plus the informational note folded into R3 by the consolidator: ⚪ `_negated` cuts the negation window at every `and`, `then` and `but`, not only at the candidate's verb, so `Do not run the work phase for PRD 1 and plan-tasks for PRD 2` denies `plan-tasks` — fails closed and matches the spec's wording (hooks/guard_phase_delegation.py:639).

B1: fail
B2: pass
B3: fail
B4: pass
B5: pass
B6: pass
B7: pass
B8: pass
B9: pass
B10: fail
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

Doubt lens + de-slop (codex, static-only sandbox). FIX: R9, R10, R1. VERIFY: R17 (queued to `00324-guard-pairs-delimiters-as-nested-runs-v1-checks-1.json`). KNOWN: R11.

R1: fail
R2: fail
R3: pass
R4: pass
R6: pass
R7: pass
R8: pass
R9: pass
R10: pass
R11: pass
R12: fail
R13: pass

D1: pass
D2: pass
D3: pass
D4: pass
D5: pass

## Carl

Gemini (copilot backend). Ran the three touched test files and `dev/bin/replay_delegation_guard.py`. One finding: R1.

R1: pass
R2: pass
R3: pass
R4: pass
R6: pass
R7: pass
R8: pass
R9: pass
R10: pass
R11: pass
R12: fail
R13: pass

Verdict: 17 findings
Tests: 7077 passed, 0 failed, 3 skipped (suite run this cycle)
