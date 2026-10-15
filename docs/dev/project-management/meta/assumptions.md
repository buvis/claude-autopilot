# Assumptions ledger — PRD 00307-guard-citations-and-replay-contract-v1

## 1: Write pinned citation/negation/agoge tests and register the new test file

- The dispatch's example "Note (an aside) then also run plan-tasks for cleanup)" returns None today because nothing anchors it, and a `_cited` fix can only allow more, so a non-None assertion on it could never pass. Used "Note (an aside) then also run plan-tasks for PRD 00300 cleanup)" instead: same closed-aside-then-stray-`)` shape, flagged today.
- The test is named `test_already_closed_aside_before_the_name_is_not_a_citation`; the dispatch gave no name.
- The c2 example sentence ("always reads ...") does not contain the required span "d reports `design-solution: <p", so used "The subagent then prints and reports `design-solution: <prd-stem>` followed by the doc path."
- The c3 sentence is invented: 'Write a test that checks self.assertIn("design-solution: <prd-stem>", report) for the exit line.' It contains the required span.
- The agoge prompt is "Run /autopilot:work for PRD 00300, every task."
- The citation-test prompts ("The report line reads `run plan-tasks for PRD 00300` verbatim." and its quote and paren variants) are invented; the dispatch gave none.
- In the allow-corpus test, a scratch file means any file outside `allowed/*.txt`.

## 2: Implement the citation rule, clause-bounded negation, bisect lookup and agoge roster

- `_cited` is bounded by the enclosing sentence for closers, not the clause; plain clause bounds fail 7 of the pinned corpus/citation tests (backtick runs spanning a comma, `design-solution: <prd-stem>` across a colon, and the paren case whose `(` opens two commas before the name).
- Earlier symmetric openers (backtick, double quote) are still counted by parity from `clause_start` only — this is what keeps the quoted-aside bypass closed while the sentence-wide close window stays open.
- Earlier asymmetric openers (`(`, `[`, curly quotes) are searched from `sentence_start`, since they always open and the corpus paren case needs the reach.
- Straight single quote `'` is left out of the symmetric wrapper set to avoid false allows from contractions and possessives; no test needs it.
- `_cited` runs after the anchor and scope check, not before; same result (every branch ends in `continue`), but avoids a quadratic-cost ordering the linearity test caught.
- A close counts as taken into the span if the closer character appears anywhere in `text[start+1:end]`, which covers the optional " skill" suffix extending `end` past the consumed close.

## 3: Exempt a refused pinned id from the replay's exit contract and add the CHANGELOG entry

- The test exercises all four PINNED_DENY ids, not only PINNED_DENY[0], with distinct personas and descriptions per id so no persona-, prefix- or description-based shortcut can excuse the refusal.
- Weak point 7 (a mixed pinned+unpinned run) asserts both refusal lines plus exit 1 rather than a dedicated "unpinned-only" failure message, since the contract has no separate failure line for a refused unpinned dispatch.
- The CHANGELOG bullet's wording of what the citation rule does ("a phase named inside quotes or a citation is not an order to run it") is inferred from the prior task's contract, not re-derived from the hook code.
- The live-corpus replay run still exits 1 after this fix, from two non-pinned refusals (toolu_011UqbqFtUDPuSeCiLLgMvEg, toolu_013ePUKbLDE7DLnbnGmgszzR) unrelated to the pinned-exemption contract this task implements; flagged for the PRD-level review rather than silently loosening the acceptance check, per the task's own Verify instruction.
  - **Resolved in review cycle 1** (tasks 4 and 7). Both refusals came from the citation window being truncated by a period that is not a sentence end. Re-measured on the reviewed revision (23b99ef): `python3 dev/bin/replay_delegation_guard.py` exits **0** and prints `total 1183 / per-task 756 refused 1 / reviewer 168 refused 0 / agoge 49 refused 0 / other 210 refused 6`. No non-pinned refusal remains in the three gated buckets, and both previously-refused ids are now allowed (verified individually against the pre-change guard at 4eb6b53, where both are refused).

## Review cycle 1 rework (tasks 4-9)

- Contract item 2's 4-tuple `_boundaries` shipped literally; the test fixture's unpack was
  widened to match, rather than keeping a 3-tuple and building the masked scratch twice per
  field (the implementor's first resolution).
- Task 4: Pat's MEDIUM on the citation boundary's backtracking was real - `` `+[ \t]*[^(\s] ``
  gives one backtick back on a multi-backtick closer - and the trailing class now excludes the
  backtick. The matching multi-backtick CITATION test was dropped from task 4 rather than left
  red: it fails on `_cited`'s pairing, not on the boundary, and that was task 7's scope.
- Task 5: each recorded payload keeps its real `description` as well as its `subagent_type` and
  `prompt`; verified to change no verdict under either guard. The ~17 KB of literals pushed the
  citations file over the 800-line limit, so they live in `hooks/test_guard_phase_delegation_corpus.py`.
- Task 7: a digit-preceded `"` opens nothing but may still close a pending open (the literal
  "skip it when pairing" rule broke three pinned allows, whose closing quote follows a PRD
  number). Once a mark has been skipped, pairing stops and later marks form no run - a guard
  resolves the ambiguity by denying - while pairs completed before the skip stand.
- Task 7: the digit rule is the `"` pass only; no unit is written with a backtick, and skipping
  a backtick opener hands the opener role to its own closer.
- Task 7: the lexical layer moved to `hooks/guard_phase_delegation_lexicon.py` with every name
  re-imported, because eight test modules and `dev/bin/replay_delegation_guard.py` reach them
  as `guard_phase_delegation.<name>`.
- Task 9: `toolu_015DM18ubZLJZbA65ozvuw8c` has no recoverable payload, so its "exact span" was
  pinned as a SHAPE (a run closing at the sentence tail) with a standalone-label control,
  never as a reconstructed prompt.
- Tasks 6 and 8 carried no production diff: the replay acceptance gate and the record of it.

## Reconciling the required `refused 1` with the four pinned ids

The replay pins **four** deny ids (`replay_delegation_guard.py:PINNED_DENY`), yet the acceptance line reads `per-task ... refused 1`. The reason is bucketing, not deduplication: `bucket()` files each dispatch by persona, and of the four pinned ids only `toolu_01Ku4TbcQoeik6ZLf5XkkAuD` carries a per-task persona. The other three (`toolu_011eQouP7ZMWxba7b8ijXmiR`, `toolu_01WwjmFapBm8w3NYCwWddUbk`, `toolu_01S6V4tZDtrS3ePnXWtD9dT2`) dispatch as `general-purpose` and land in the ungated `other` bucket, which is where 3 of that bucket's 6 refusals come from. `_dedupe` does fold identical `tool_input` payloads into one group, so a count is of groups rather than records, but no pinned id is folded into another here.

## Accepted fail-open surface of the citation rule

Carried from review cycle 1 (BLAKE, task 7) and accepted as designed rather than fixed: a quoted or bracketed run that encloses a phase name excuses the order inside it, so `"note: /autopilot:work for PRD 00300, every task"` is allowed. That is the citation rule itself - the guard cannot tell a citation from an order dressed as one - and narrowing it is what refused the legitimate corpus dispatches this PRD exists to allow. The guard's protection against the shape being used deliberately is that the run must genuinely enclose the name within one citation sentence: a balanced quote earlier in the sentence, a terminator followed only by closing wrappers, a backtick behind a digit, and an ambiguous unit-mark pairing were each closed in cycle 1 and are pinned.
