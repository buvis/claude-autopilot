---
default_model: opus
model_tier_rationale: the merge rule that keeps the two fixtures apart without breaking the three pinned fixture suites is an algorithm the implementer must find and measure; design runs so the rule is reviewed before it is coded
---

# The consolidator keeps distinct findings apart

Source: two reviews of batch 202610100952 in the agent-skills repo, 2026-10-18. In the 00070 review, Blake's two approval lines (a LOW each, "harmless and additive", "extra coverage, not scope creep") folded into Alice's MEDIUM readability finding on the same test file, so R1 rendered as `[2/4] ALICE, BLAKE` and the orchestrator corrected the consensus by hand in the review file. In the 00088 review, Blake's and Bob's finding that the drift test uses bare substring matching folded onto Alice's finding that a subparsers lookup is duplicated, both in `skills/use-qwen/scripts/test_runbook_matches_harness.py`; the orchestrator restored the lost finding by hand as R18 and wrote that the surviving text "must not be the one nobody wrote down". A merge that hides a distinct defect changes which findings get swept, since a Medium raised by one reviewer is now ledgered while one raised by two is swept.

## Problem

`match` (`skills/review-work-completion/scripts/consolidate_findings.py:251`) merges two findings of one file when the token Jaccard reaches `MERGE_THRESHOLD` (`skills/review-work-completion/scripts/consolidate_findings.py:53`), when the overlap coefficient of a terse-versus-verbose pair reaches `OVERLAP_THRESHOLD` (`skills/review-work-completion/scripts/consolidate_findings.py:73`), or when `numeric_tokens` finds two all-digit tokens shared by the two descriptions (`skills/review-work-completion/scripts/consolidate_findings.py:260`). The numeric fallback was pinned for line-number signatures (`test_three_real_00122_findings_merge_via_shared_numeric_signature`, `skills/review-work-completion/scripts/test_consolidate_findings.py:511`), but it also fires on test data: Alice's 00070 finding names the day values 40, 2, 0, 45, 35, 31, 29 and 3, and Blake's approval lines name the same values, so each approval shares more than two digits with it. The 00088 pair is a prose match of the Jaccard or overlap kind; which one fired is for the implementer to measure. `parse_line` (`skills/review-work-completion/scripts/consolidate_findings.py:264`) and `consolidate` (`skills/review-work-completion/scripts/consolidate_findings.py:333`) then keep the first-seen wording, so the folded finding vanishes from the table.

## Solution

Two fixtures become the contract, in `skills/review-work-completion/scripts/test_consolidate_findings.py` beside `test_distinct_defects_in_one_file_do_not_match` (`skills/review-work-completion/scripts/test_consolidate_findings.py:146`), each built from the reviewers' lines verbatim:

Fixture 00070, three lines, must yield three rows (the cited files live in the agent-skills repo; they are test data here, not citations):

```text
[ALICE] 🟡 Simplification: test_empty_trash_ages_out_old_batches_only is 34 lines. It uses nested seed and present closures and a shared names dict that mutates across three seeding rounds. The PRD asked for a plain three-batch case (40, 2 and 0 days, expecting a return of 1). The extra boundary matrix (45/35/31/29/3 days) is behavior-preserving extra coverage, but it makes the test harder to read. Consider splitting the first three-batch case from the boundary sweep into two tests. | File: skills/purge-devtmp/scripts/test_purge_devtmp.py:126 | Task: 1
[BLAKE] ⚪ test_zero_day_retention_never_deletes_what_this_run_just_trashed goes beyond the spec's acceptance text. It adds a second scenario with a 40-day-old expired batch and asserts trash-batches-emptied=1. This is harmless and additive, and it pins that the retention pass still runs under zero days. | File: skills/purge-devtmp/scripts/test_purge_devtmp.py:107 | Task: 1
[BLAKE] ⚪ test_empty_trash_ages_out_old_batches_only uses a wider matrix than the spec's 40/2/0-day case: 45, 35, 31, 29 and 3 days, plus several retention values and a different keep. The spec's core assertions are present (40-day batch gone, 2-day and today's batches kept, return value 1). Fixing now at local noon avoids a flake near midnight. This is extra coverage, not scope creep. | File: skills/purge-devtmp/scripts/test_purge_devtmp.py:125 | Task: 1
```

Fixture 00088, three lines, must yield two rows, Alice alone and Blake with Bob:

```text
[ALICE] 🟡 Subparsers-action lookup is duplicated inside the file: _subparser (skills/use-qwen/scripts/test_runbook_matches_harness.py:28) and test_runbook_names_every_harness_subcommand (skills/use-qwen/scripts/test_runbook_matches_harness.py:37) each re-run next(action for action in parser._actions if action.choices is not None), and the two flag tests share an identical 5-line body. Simpler, behavior-preserving: add _subparsers_action() returning that action, call it from _subparser and from the subcommand test, and factor the flag loop into _long_flags(subparser) that yields every -- option except --help; each test then reads for flag in _long_flags(_subparser("vet")): assert flag in section, flag. | File: skills/use-qwen/scripts/test_runbook_matches_harness.py | Task: 1
[BLAKE] 🟡 Flag drift test uses bare substring matching, so two run flags are masked by longer ones: --shape is a substring of the documented --shapes and --bound of --gate-bound. Delete --bound SECONDS or --shape {description,tdd} from § 7 and the test still passes, defeating the stated goal that the contract "cannot drift silently". The PRD prescribed this assertion literally, so it is a spec defect faithfully implemented; a word-boundary check (rg-style --shape\b) would close it | File: skills/use-qwen/scripts/test_runbook_matches_harness.py:50 | Task: 1
[BOB] 🟡 Flag assertions use bare substring containment, so prefix-overlapping flags are never really pinned: --bound is satisfied by the documented --gate-bound and --shape by --shapes; drop either from § 7 and the drift test still passes | File: skills/use-qwen/scripts/test_runbook_matches_harness.py | Task: 1
```

The design step picks the rule that satisfies both fixtures while `test_paraphrases_of_one_defect_match`, `test_three_real_00122_findings_merge_via_shared_numeric_signature` and `test_review_00186_agreements_merge` keep passing, measures every threshold it touches against the fixture suites the way the module's header comments do, and records the measured band in the test docstrings. Two candidates the design must weigh: the numeric fallback counting only tokens that also appear as a line citation in a `File:` cell or a `:N` suffix of either description, and the numeric fallback requiring the pair to clear a lower Jaccard floor as well.

## Requirements

### Must have
- The two fixture tests, `test_review_00070_approvals_stay_apart_from_the_finding` and `test_review_00088_substring_finding_stays_apart_from_the_dedup_finding`, with the lines above, asserting the row counts and the finders of each row.
- `match` changed so both pass; `skills/review-work-completion/scripts/test_consolidate_findings.py` passes in full, including the pinned threshold-band tests.
- The module header comment (`skills/review-work-completion/scripts/consolidate_findings.py:24`) describes the rule as shipped, with the measured values.
- A CHANGELOG `[Unreleased]` Fixed entry under **review-work-completion**: two distinct findings on one file no longer merge on shared test-data numbers or loose prose overlap, so a reviewer's finding is never hidden under another reviewer's wording.

### Nice to have
- None.

## Implementation

### Module: consolidator
- **Location**: `skills/review-work-completion/scripts/consolidate_findings.py`
- **Responsibility**: merge the same defect across reviewers and nothing else
- **Exports**: `match()` (unchanged signature)

### Module: consolidator-fixtures
- **Location**: `skills/review-work-completion/scripts/test_consolidate_findings.py`
- **Responsibility**: pin the two real pairs that must stay apart
- **Exports**: none
- New symbols: `test_review_00070_approvals_stay_apart_from_the_finding`, `test_review_00088_substring_finding_stays_apart_from_the_dedup_finding`

### Dependencies
- consolidator: No dependencies (foundation)
- consolidator-fixtures: Depends on [consolidator]

## Tasks

### Phase 0: Foundation
- [ ] Add the two fixture tests. Premise: `rg -c "shared_nums\) >= 2" skills/review-work-completion/scripts/consolidate_findings.py` prints 1 before the edit; a different count means the rule already changed and the task stops and reports. - Acceptance: `uv run --no-project --with pytest python -m pytest -q skills/review-work-completion/scripts/test_consolidate_findings.py skills/review-work-completion/scripts/test_consolidate_findings_regressions.py -k "review_00070 or review_00088"` fails both against the current rule.

### Phase 1: Core
- [ ] Change `match` per the reviewed design, update the header comment and add the CHANGELOG entry (depends on: Phase 0) - Acceptance: `uv run --no-project --with pytest python -m pytest -q skills/review-work-completion/scripts/test_consolidate_findings.py skills/review-work-completion/scripts/test_consolidate_findings_regressions.py` passes; `rg -n "review-work-completion.*distinct findings" CHANGELOG.md` prints one line under `[Unreleased]`.

## Success Criteria

- The consolidator suite passes in full and the `[checks]` block that registers it (`dev/bin/release-checks:262`) is green.
- Post-release signal: a review file no longer needs a hand-written consolidation note restoring a folded finding.
