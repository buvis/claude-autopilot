---
prd: docs/dev/project-management/prds/wip/00368-the-consolidator-keeps-distinct-findings-apart-v1.md
review: 1
date: 2026-10-19
head_sha: d0cff9a160afb215b54ed0f8adced8e798c901ac
codex_thread_id: 01a15457-98ff-7af1-8c31-1574ceec7b50
reviewers: alice,blake,bob,carl
agents:
  alice: available
  blake: available
  bob: available
  carl: available
dispatch_rows:
  bob: 9616fcd4
  carl: b45e0396
---

# Review: 00368-the-consolidator-keeps-distinct-findings-apart-v1

Diff range: `844ae634aa61c6e98e6f3202f4185a22b044076b..d0cff9a160afb215b54ed0f8adced8e798c901ac`

codex_rung_guard: not fired

## Review Summary

Cycle 1, full review. Four reviewers ran: Alice (consensus), Blake (blind, PRD-only),
Bob (codex, doubt rubric D1-D5 plus de-slop), Carl (gemini). Engine: legacy. Pack: ok.
No CRITICAL and no HIGH finding. Eight findings survive, all Medium or Low.

### Agent Status

- Alice: available (Claude subagent, implementation-aware)
- Blake: available (blind lens, PRD-only)
- Bob: available (codex, exit 0, thread 01a15457-98ff-7af1-8c31-1574ceec7b50)
- Carl: available (gemini via the runner, exit 0) - **contamination note:** Carl's
  transcript shows he read `docs/dev/tmp/bob-output-20261019-00368-c1.txt` during his
  run and then emitted Bob's first finding near-verbatim. His two findings are
  therefore not an independent voice on R1 and R2. Both still hold two independent
  voices without him (R1: Blake and Bob; R2: Alice, Blake and Bob), so no consensus
  count below depends on Carl.

### Consolidation notes

`consolidate_findings.py` exited 0 and emitted eight rows, and it folded distinct
findings in exactly the way this PRD exists to stop - visible here because the merge
is reported: its row 1 merged Blake's "docstrings record no measured band"
(`:91`), Bob's and Carl's "fixtures do not assert every row's finders" (`:17`, `:54`)
and Blake's own finders row (`:54`) into one three-of-four row carrying only Blake's
wording. Its rows 2 and 3 split ONE defect (the PRD acceptance command no longer
selects the fixtures) into two two-of-four rows (ALICE, BLAKE and BOB, CARL),
because the citations differ by line suffix.

The table below is corrected by hand on issue-text-plus-file, the matching standard
this gate uses: rows 2 and 3 are merged into R1 at four of four, and the
finders-assertion finding is restored as its own row R2. This is the hand correction the PRD's
own Source section describes; it is recorded here rather than silently applied.
The mechanical fail-first replay row is folded onto R7, which names the same test.

## Consolidated Findings

| Ref | Consensus | Severity | Issue | File | Task | Found By |
|-----|-----------|----------|-------|------|------|----------|
| R1 | [4/4] | 🟡 | The PRD's literal acceptance commands no longer reach the new fixtures: the focused `-k "review_00070 or review_00088"` run against `test_consolidate_findings.py` selects zero tests, and the full-module command excludes all three new tests, because the fixtures went into the sibling file `test_consolidate_findings_regressions.py` rather than beside `test_distinct_defects_in_one_file_do_not_match`. The split itself is justified (the main file is at the 800-line cap) and `dev/bin/release-checks:263` registers the new file, but the PRD's acceptance gate can no longer verify the fixtures. Fix: reword the PRD/task acceptance commands to name both modules. | skills/review-work-completion/scripts/test_consolidate_findings_regressions.py:1 | 1 | ALICE, BLAKE, BOB, CARL |
| R2 | [3/4] | 🟡 | The two fixtures do not assert every row's finders as the Must-have requires: 00070 asserts only the three `[1/2]` consensus counts, never ALICE or BLAKE; 00088 asserts BLAKE, BOB on the pair row but never that the singleton row belongs to ALICE. Fix: assert each expected row's finder cell explicitly, keeping the row-count checks. | skills/review-work-completion/scripts/test_consolidate_findings_regressions.py:54 | 1 | BLAKE, BOB, CARL |
| R3 | [1/4] | 🟡 | The spec says the design measures every threshold it touches and records the measured band in the test docstrings. The two new fixture docstrings record no measured values; the 00088 docstring says only "already passes under current code". The only measured band is a prose claim in the module header. Measured 00088 Jaccard values (ALICE/BLAKE 0.042, ALICE/BOB 0.026, BLAKE/BOB 0.268) are recorded nowhere. | skills/review-work-completion/scripts/test_consolidate_findings_regressions.py:91 | 1 | BLAKE |
| R4 | [1/4] | 🟡 | The fix is a blunt digit-length floor (`NUMERIC_SIGNATURE_MIN_DIGITS = 3`). It is neither of the two candidates the spec told the design to weigh (citation-aware tokens, or a lower Jaccard floor), and no weighing is recorded. The header claims cited line numbers are "reliably >= 100", which the repo's own fixtures contradict (`test_runbook_matches_harness.py:28`, `test_purge_devtmp.py:107`). Two reviewers citing small line numbers no longer merge; shared 3+ digit test data (200, 404, 100) still merges distinct findings. The false-merge class is narrowed, not closed. | skills/review-work-completion/scripts/consolidate_findings.py:93 | 1 | BLAKE |
| R5 | [1/4] | ⚪ | The new test module imports the private helpers `_finding`, `_run` and `_write` from the sibling module `test_consolidate_findings`, coupling the two files so a rename in one breaks the other. A shared conftest or helper module would be sturdier. Not blocking. | skills/review-work-completion/scripts/test_consolidate_findings_regressions.py:20 | 1 | ALICE |
| R6 | [1/4] | ⚪ | The header comment states the same numeric-floor rationale twice, once in the module docstring and once above the constant, both repeating the 00122 and 00070 measurements. | skills/review-work-completion/scripts/consolidate_findings.py:31 | 1 | BLAKE |
| R7 | [2/4] | ⚪ | `test_review_00088_substring_finding_stays_apart_from_the_dedup_finding` passes against the pre-change code (confirmed by the fail-first replay block), so the 00088 fold the PRD cites is not reproduced by these lines and the "loose prose overlap" half of the PRD's wording is addressed by no code change. The PRD and design accept this as a non-regression pin, and the CHANGELOG entry correctly claims only the numeric-fallback fix. | skills/review-work-completion/scripts/test_consolidate_findings_regressions.py:98 | 1 | ALICE, mech-check |
| R8 | [1/4] | ⚪ | The CHANGELOG entry adds a note beyond the spec's one-sentence Fixed entry (that `split_ledger_dismissed` is also narrowed). It is accurate and satisfies the PRD's `rg` check, but the spec's "or loose prose overlap" wording is not covered because prose thresholds were not touched. | CHANGELOG.md:23 | 1 | BLAKE |

## Alice

Ran both consolidator test files: 60 passed, 0 failed. `test_consolidate_findings.py`
is untouched by the diff and sits at exactly 800 lines. Findings: R1, R5, R7 above.

Checked and fine: the `match()` change (`NUMERIC_SIGNATURE_MIN_DIGITS = 3` plus the
filter, `numeric_tokens()` unchanged, header comment updated); the boundary test
`test_numeric_fallback_requires_three_digit_tokens` (2-digit, 3-digit and mixed cases,
the mixed case failing against the old code); the CHANGELOG entry under
`[Unreleased]` / Fixed; the `dev/bin/release-checks` l4 registration; no existing
ledger test depends on a filtered pair.

R1: pass, R2: pass, R3: pass, R4: pass, R6: pass, R7: pass, R8: pass, R9: pass,
R10: pass, R11: pass, R12: pass, R13: pass

## Blake

Blind lens, PRD only. Findings: R1, R2, R3, R4, R6, R8 above. He ran the two test
files himself (60 passed) and measured the 00088 Jaccard values quoted in R3.

B1: fail, B2: pass, B3: pass, B4: pass, B5: pass, B6: pass, B7: pass, B8: pass,
B9: pass, B10: pass, B11: pass, B12: pass, B13: pass, B14: pass, B15: pass,
B16: pass, B17: pass, B18: pass, B19: pass

## Bob

Doubt lens plus de-slop (codex, static-only). Findings: R1 and R2 above.

FIX:
- Medium: the sibling-module move leaves the PRD's focused acceptance command selecting none of the fixtures and the full-module command excluding all three new tests; update the PRD and task acceptance commands to name both modules. (R1)
- Medium: the fixtures do not assert every row's finders: 00070 checks only consensus counts, 00088 never checks that the singleton belongs to ALICE. (R2)

VERIFY:
- (none)

KNOWN:
- (none)

R1: fail, R2: pass, R3: pass, R4: pass, R6: pass, R7: pass, R8: pass, R9: fail,
R10: pass, R11: pass, R12: pass, R13: pass

D1: pass
D2: pass
D3: pass
D4: pass
D5: pass

## Carl

Gemini backend, exit 0. Findings: R1 and R2 above (not independent - see the
contamination note in Agent Status). Several of his own file reads were denied by the
sandbox, which is why he fell back to the staged inputs and to Bob's output file.

R1: fail, R2: pass, R3: pass, R4: pass, R6: pass, R7: pass, R8: pass, R9: fail,
R10: pass, R11: pass, R12: pass, R13: pass

Verdict: 8 findings
Tests: 7215 passed, 0 failed, 2 skipped (reused from last-verification.json at 86e9c66)
