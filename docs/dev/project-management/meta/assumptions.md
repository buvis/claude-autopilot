# Assumptions ledger — PRD 00307-guard-citations-and-replay-contract-v1

## 1: Write pinned citation/negation/agoge tests and register the new test file

- The dispatch's example "Note (an aside) then also run plan-tasks for cleanup)" returns None today because nothing anchors it, and a `_cited` fix can only allow more, so a non-None assertion on it could never pass. Used "Note (an aside) then also run plan-tasks for PRD 00300 cleanup)" instead: same closed-aside-then-stray-`)` shape, flagged today.
- The test is named `test_already_closed_aside_before_the_name_is_not_a_citation`; the dispatch gave no name.
- The c2 example sentence ("always reads ...") does not contain the required span "d reports `design-solution: <p", so used "The subagent then prints and reports `design-solution: <prd-stem>` followed by the doc path."
- The c3 sentence is invented: 'Write a test that checks self.assertIn("design-solution: <prd-stem>", report) for the exit line.' It contains the required span.
- The agoge prompt is "Run /autopilot:work for PRD 00300, every task."
- The citation-test prompts ("The report line reads `run plan-tasks for PRD 00300` verbatim." and its quote and paren variants) are invented; the dispatch gave none.
- In the allow-corpus test, a scratch file means any file outside `allowed/*.txt`.
