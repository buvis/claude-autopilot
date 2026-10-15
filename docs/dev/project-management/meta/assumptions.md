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
