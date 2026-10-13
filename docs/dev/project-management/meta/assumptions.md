# Assumption ledger

Per-plan. Replaced at the first completed task of a full-plan pass.

Plan: PRD 00279 (run one exact reuse rule), batch 202610111300.

## 2: review SKILL step 6: Tests: line sourced from gate.tests_line

Tess (test author):

- Interpreted "the next line that starts with ** and ends with .**" as the bold *heading phrase* pattern (`**<text ending in period>**` at the start of a line), not a requirement that the entire line end in `.**` -- bold-heading paragraphs in SKILL.md continue with ordinary text after the heading phrase on the same line.

Ivan (implementor):

- Exact prose wording for the rewritten step-6 paragraph and lines 181/324 was at my discretion (prose, not code); preserved as much of the original sentence structure as possible while swapping the reuse-rule source.
- `test_tests_line_source_prose.py` already existed on disk (Tess's prior test-authoring dispatch); registered its path in `dev/bin/release-checks` without creating or modifying the test file itself.

## 3: prose: correct the stored-command description and CHANGELOG line 44

Ivan (implementor):

- Resolved the task's "Verify" line (run `dev/bin/release-checks`) as superseded by the dispatch's own standing rule against running the full suite inside a per-task dispatch, since this is a docs-only task with no failing tests named; left the full gate for the orchestrator's step 7.
- Placed the new CHANGELOG bullet as the last entry in `[Unreleased] ### Changed`, immediately before the `## [0.9.0]` heading, since no specific position was mandated beyond "alongside the other `### Changed` entries."
