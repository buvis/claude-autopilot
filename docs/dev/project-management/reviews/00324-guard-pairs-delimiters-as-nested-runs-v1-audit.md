# Decision Audit Log: 00324-guard-pairs-delimiters-as-nested-runs-v1

PRD: `00324-guard-pairs-delimiters-as-nested-runs-v1.md`
Started: 2026-10-17T08:16:12Z
Completed: 2026-10-17T08:16:12Z
Autonomous: 18  |  Deferred: 13  |  Doubts: 0

### [autonomous] 2026-10-17T08:16:12Z

**Decision**: `_quoted_runs` is 55 lines, over the 50-line limit (mechanical facts block). Split the token walk that builds `pairs` (lines 356-385) from the span merge walk that builds `runs` (lines 386-402) into two helpers. The behavior stays the same.

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-10-17T08:16:12Z

**Decision**: CJK terminators only end the citation window when whitespace or a closer follows, but CJK text is normally written without spaces. `Hi (all。Run plan-tasks for PRD 00300 for every task。Thanks)` with a real `)` is still allowed (I ran it), while the same text with a space after each `。` is denied. Shape (3) is closed only for the PRD's spaced payload. Fix: let `。！？` end the sentence unconditionally, since they have no dotted-identifier ambiguity, e.g. an extra branch `[。！？]` outside the `(?=\s|...)` lookahead.

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-10-17T08:16:12Z

**Decision**: The nested-run rule is not applied to asymmetric openers in `_cited`. Its first loop looks for the nearest `(`, `[`, `“` and so on before the name using raw mark positions, ignoring the run map. A bracket opener that sits inside an already-closed quote or backtick run therefore still pairs with a later unrelated closer and hides the order. This is the same shape as payload (1), where the spec requires an opener inside a closed run to close only inside it.

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-10-17T08:16:12Z

**Decision**: Several new behaviors have no test. (a) `then` and `but` are untested although the test name and PRD title say "and/then/but"; only `and` is exercised. (b) `！` and `？` are untested; only `。` is. (c) `;` and `=` emoticons are untested; only `:(` and `:)` are. (d) A single backtick inside a doubled-backtick span (the length-pairing rule) and a bracket or quote opener deferred while another class is open have no test. (e) The nested-bracket chain and innermost-pair selection in the merge walk have no test. Add one parametrized case each.

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-10-17T08:16:12Z

**Decision**: The diff carries unrelated formatter reflow that no task asked for. Examples: the `_is_per_task_persona` expression, `text[end : end + 1]` slice spacing in `_candidates`, `_is_scoped`, `_quote` and `_field_delegation`, the exploded `_strongly_anchored` and `_weakly_anchored` signatures, the `main()` print calls, and removal of seven re-exported imports (`_MASKED_IN_SPAN`, `_PHASE_BARE`, `_PHASE_CONCEPT`, `_PHASE_SKILL`, `_WRAP`, `_WRAP_CLOSE`, `_WRAP_OPEN`). Revert these hunks so every changed line traces to the PRD.

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-10-17T08:16:12Z

**Decision**: `_find_skill_md_paths` was rewritten (last-token `rsplit`) although neither the task contract nor the design names it. It is equivalent, and it is what makes the dense budget pass. Record in the PRD or ledger that the budget was met this way instead of by the specified `_FOLLOW` once-per-field collection.

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-10-17T08:16:12Z

**Decision**: The spec's new symbol `_nested_runs` does not exist. The pairing was folded into `_quoted_runs`, which keeps its old name and gains an inline stack-less state machine (one quote slot, one backtick slot, a bracket stack). The stated interface (New symbols: `_nested_runs`) is not met.

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-10-17T08:16:12Z

**Decision**: CJK boundary coverage is masked by the emoticon fix: removing all three new terminators still leaves this fixture denied. Add cases with an ordinary closing `)` and parameterize `。`, `！`, `？`.

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-10-17T08:16:12Z

**Decision**: The `and_then_but` test exercises only `and`; existing `then` controls contain commas that already stop negation. Parameterize the new payloads over all three conjunctions without commas.

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-10-17T08:16:12Z

**Decision**: The design and PRD call the new function `_nested_runs` ("New symbols: `_nested_runs`"), but the code keeps the name `_quoted_runs` while it now pairs brackets, backticks and quotes. The name misleads. Rename it, or note the deviation in the PRD.

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-10-17T08:16:12Z

**Decision**: The CHANGELOG entry names the five closed shapes and says the scan stays linear, but it does not mention the doubled-backtick citation fix or the `·` terminator.

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-10-17T08:16:12Z

**Decision**: Cannot statically verify: acceptance suites, recorded replay, and timing limits (BOB VERIFY)

**Choice**: routed to verification

**Rationale**: queued as python3 dev/bin/replay_delegation_guard.py in 00324-guard-pairs-delimiters-as-nested-runs-v1-checks-1.json; runs in the work phase step-7 verification pass

### [autonomous] 2026-10-17T08:16:12Z

**Decision**: state.work_start_sha was unset at review entry, so the review diff range was undefined

**Choice**: set work_start_sha to 1228d38bfd0cbc61223001f545373e4f47de71e8

**Rationale**: parent of task 1 commit 447343f5, the PRD first work commit; the build gate never captured the field

### [autonomous] 2026-10-17T08:16:12Z

**Decision**: consolidate_findings.py silently dropped all four BOB findings because his output used bullet-prefixed issue lines (- [BOB] ...)

**Choice**: stripped the leading bullets from bob-output (text otherwise verbatim) and re-ran consolidation

**Rationale**: the parser matches only bare [AGENT] lines; without the fix the doubt lens contributed nothing to the table

### [autonomous] 2026-10-17T08:16:12Z

**Decision**: R10: reviewer could not tell which five tests failed in the staged gate run

**Choice**: discarded

**Rationale**: contradicts computed facts: dev/bin/release-checks re-run twice at HEAD 0ef4eb05, exit 0, 0 failed both times; hooks/ suite 974 passed. The staged run's five failures did not reproduce.

### [autonomous] 2026-10-17T08:16:12Z

**Decision**: R3: `·` is not a sentence end in `_CITE_SENTENCE_BOUNDARY` (Blake, blind)

**Choice**: excluded as a settled deferral

**Rationale**: cycle-1 R13 and the design doc both record the deliberate decision not to add `·`; a settled deferral does not block convergence and is not re-argued.

### [autonomous] 2026-10-17T08:16:12Z

**Decision**: Bob (codex) refused the first dispatch for lack of input (sandbox-exec: sandbox_apply: Operation not permitted)

**Choice**: re-dispatched once with the inlined retry prompt

**Rationale**: documented lack-of-input refusal shape; the inlined retry produced a usable doubt review, so the doubt lens did not drop.

### [autonomous] 2026-10-17T08:16:12Z

**Decision**: Both blocking HIGHs (R1 bracket-in-bracket, R4 unspaced ！/？) were re-measured by the orchestrator against HEAD before being treated as blocking

**Choice**: confirmed, then deferred as cap-overflow

**Rationale**: single- and multi-voice HIGHs are verified before they gate; both reproduce exactly as reported.

### [deferred] 2026-10-17T08:16:12Z

**Decision**: `_FOLLOW` matches are not collected once per field and looked up by bisect, as the spec requires. The budget is met anyway (0.14 to 0.25 s/MB against the 0.3 bound), but the specified design is absent.

**Rationale**: deferred by review-close

### [deferred] 2026-10-17T08:16:12Z

**Decision**: The supplied fail-first replay reports that `test_backtick_exclusion_in_cite_boundary_can_fail` passes against base, contradicting Phase 0's eight-red requirement. Retained as an existing-invariant regression test.

**Rationale**: deferred by review-close

### [deferred] 2026-10-17T08:16:12Z

**Decision**: `·` is not added to `_CITE_SENTENCE_BOUNDARY`, although the PRD Solution and Problem sections name it. The task contract and design deliberately drop it.

**Rationale**: deferred by review-close

### [deferred] 2026-10-17T08:16:12Z

**Decision**: `_NEGATION_REACH_END` newly denies coordinated negated lists such as `Never run work and plan-tasks for PRD 00300 for every task.`, which the 5-word window previously allowed. This is the safe direction for a guard.

**Rationale**: deferred by review-close

### [deferred] 2026-10-17T08:16:12Z

**Decision**: `test_backtick_exclusion_in_cite_boundary_can_fail` passes against the pre-change code (the replay [MECH] line), so it is not red-first. That is intended: it mutates the shipped pattern and asserts the verdict flips.

**Rationale**: deferred by review-close

### [deferred] 2026-10-17T08:16:12Z

**Decision**: Bracket-in-bracket bypass: an asymmetric opener inside a closed or mismatched bracket run still pairs with a later closer, so `Note [see (x] then run plan-tasks for PRD 00300 for every task (done).` and `Note (see [x) ... [done].` are still allowed (orchestrator-confirmed against HEAD). The quote/backtick/curly-quote variants are fixed. hooks/guard_phase_delegation.py:435

**Rationale**: rework cap reached with this finding unresolved

### [deferred] 2026-10-17T08:16:12Z

**Decision**: Unspaced fullwidth `！` and `？` still do not end the citation window end to end: normalization folds them to ASCII before the new unconditional CJK branch runs, so `Hi (all！Run plan-tasks for PRD 00300 for every task！Thanks)` is allowed while the `。` variant is denied (orchestrator-confirmed against HEAD). hooks/test_guard_phase_delegation_citations.py:727

**Rationale**: rework cap reached with this finding unresolved

### [deferred] 2026-10-17T08:16:12Z

**Decision**: `@lru_cache(maxsize=4)` on `_nested_run_pairs` is hidden module-level state retaining up to four field-sized strings; `_boundaries` should compute the pairs once and pass them in. hooks/guard_phase_delegation.py:353

**Rationale**: rework cap reached with this finding unresolved

### [deferred] 2026-10-17T08:16:12Z

**Decision**: The bracket-literal fix has one test (a single `(` inside a `"` run); the backtick-run, curly-quote and bracket-in-bracket shapes are untested. hooks/test_guard_phase_delegation_citations.py:138

**Rationale**: rework cap reached with this finding unresolved

### [deferred] 2026-10-17T08:16:12Z

**Decision**: Same LRU-cache simplification as R2, raised independently by the doubt lens. hooks/guard_phase_delegation.py:353

**Rationale**: rework cap reached with this finding unresolved

### [deferred] 2026-10-17T08:16:12Z

**Decision**: Mechanical replay: 3 touched tests in hooks/test_guard_phase_delegation_citations.py pass against the pre-change code, so they do not pin this cycle's rework.

**Rationale**: rework cap reached with this finding unresolved

### [deferred] 2026-10-17T08:16:12Z

**Decision**: Mechanical replay: 8 touched tests in hooks/test_guard_phase_delegation_structure.py pass against the pre-change code, so they do not pin this cycle's rework.

**Rationale**: rework cap reached with this finding unresolved

### [deferred] 2026-10-17T08:16:12Z

**Decision**: hooks/guard_phase_delegation.py is now exactly 800 lines, at the file-size limit; the next change to it should split it.

**Rationale**: rework cap reached with this finding unresolved
