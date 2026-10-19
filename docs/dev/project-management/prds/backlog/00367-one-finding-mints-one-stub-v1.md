---
design: skip
default_model: opus
model_tier_rationale: the fold rule for rows without a file is a similarity predicate the implementer must calibrate against the fixtures; the rest is transcription
---

# One finding mints one stub

Source: batch 202610100952 in the agent-skills repo, 2026-10-18. The 00086 gate recorded one HIGH finding (uncommitted drift in two glean files, raised by three of four reviewers) twice: once as review-close's deferral (type `repo-hygiene`) and once as the gate's own decision (type `deferred_decision`), with different wording and no `file` on either. `mint-stubs` at the done gate minted hold stubs 00091 and 00092 for the pair, same title, same source PRD. Earlier in the batch, 00075 capped out with two unresolved HIGHs that minted 00084 and 00085; the operator folded both into a hand-written PRD (00087) without quoting their keys, so the next finalize minted the same two findings again as 00089 and 00090, and a reviewer deleted them by hand.

## Problem

`skills/run-autopilot/cli/triage.py:14` states the ownership rule: a row is owned when its `ledger_key` (`skills/run-autopilot/cli/triage.py:132`, sha1 over `render_report._normalize` of the issue text) appears in the first twenty lines of any PRD, and "identical normalized text folds to one key". Two rows of one finding rarely share text: `_add_decisions` in `skills/run-autopilot/cli/review_close.py:286` writes the defer row with the consolidated wording and the `file` cell, while the gate's own record (the `deferred_decision` twin, written through `autopilot defer` or `statectl`) carries the orchestrator's summary. `mint_stubs` (`skills/run-autopilot/cli/triage.py:350`) keeps a `seen` set of keys and nothing else, so the twins mint two files. The stub's own text (`skills/run-autopilot/cli/triage.py:74`, `_STUB_TEMPLATE`) asks for "a triage decision for ledger key X" but never tells the human that a PRD absorbing the stub must quote that key, which is why 00087 did not.

## Solution

`mint_stubs` folds qualifying, unowned rows of one PRD into groups before allocating, and mints one stub per group:

- `fold_key(row)` returns `(prd, severity word, file without a trailing line suffix)` when the row's `file` is a non-empty string; rows with equal keys are one group.
- A row with no `file` joins the group of an earlier row of the same `prd` and severity word when `similar(a, b)` holds: the Jaccard index of the `[a-z0-9_]+` token sets of the two normalized issue texts is at least `0.25`, the consolidator's `MERGE_THRESHOLD` (`skills/review-work-completion/scripts/consolidate_findings.py:53`); otherwise it opens its own group. The implementer measures the two 00086 rows below and the 00075 cap-overflow pairs in the agent-skills deferred ledger `deferred/202610100952-deferred.json` and records the measured values in the test docstring; a threshold that folds the 00086 twins and keeps the two 00075 findings apart is the contract, and `0.25` is the starting value, not a fixed one.
- The group's stub carries every member's key: the frontmatter keeps `ledger_key: <first key>` and adds `ledger_keys: <key1>, <key2>` (comma-space separated, first key first) when the group has more than one row, and the Problem section carries each row's provenance and text in group order. `_prd_heads` ownership (`skills/run-autopilot/cli/triage.py:182`) already treats a quoted key in the first twenty lines as ownership, so every member row reads as owned after the mint, and a rerun mints nothing.
- The stub's Solution paragraph gains the sentence: `A PRD that absorbs this stub quotes its ledger_key line (every key when there are several) in its first 20 lines, or the next finalize mints the finding again.`

The two 00086 rows, verbatim, are the first fixture:

- `{"type": "repo-hygiene", "issue": "Uncommitted working-tree drift in skills/glean/scripts/glean.py and test_glean.py (formatter-style reformat, ~146 lines) predates PRD 00086 and belongs to no commit; three reviewers raised it against the staged diff. It also pushes cmd_scan to 54 lines, over the 50-line limit. Decide its fate: commit it as a separate formatter change, or revert it.", "severity": "high", "consensus": "3/4", "reason": "not this PRD's work (in no commit of 184d2cf..HEAD); committing or reverting another session's uncommitted work is an operator decision, not autopilot rework", "prd": "00086-use-qwen-budgets-survive-load-v1.md"}`
- `{"cycle": 1, "type": "deferred_decision", "issue": "Uncommitted working-tree drift in skills/glean/scripts/glean.py and test_glean.py (formatter-style reformat, ~146 lines); also pushes cmd_scan to 54 lines, over the 50-line limit", "severity": "high", "consensus": "3/4", "action": "deferred to batch end", "reason": "not this PRD's work (in no commit of 184d2cf..HEAD); committing or reverting another session's uncommitted work is an operator decision, not autopilot rework", "prd": "00086-use-qwen-budgets-survive-load-v1.md"}`

## Requirements

### Must have
- `fold_key` and `similar` in `skills/run-autopilot/cli/triage.py`, used by `mint_stubs` as above; `mint_stubs` keeps its signature and return shape (`minted` lists one basename per group; `skipped` counts every row that produced no file, folded members included).
- `render_stub` renders `ledger_keys:` only for a group of two or more, and lists every member's provenance and text.
- The stub sentence above in `_STUB_TEMPLATE`.
- Tests in `skills/run-autopilot/cli/test_triage.py`: `test_two_rows_of_one_finding_mint_one_stub_with_both_keys` (the 00086 pair above; one file minted, both keys in its first twenty lines, a rerun mints nothing), `test_rows_with_one_severity_and_file_mint_one_stub` (two high rows that cite one file at two different lines, with unrelated wording), `test_distinct_findings_of_one_prd_mint_two_stubs` (two high rows, no file, texts sharing fewer tokens than the threshold), `test_a_prd_quoting_any_listed_key_owns_the_group` (a backlog PRD quoting only the second key; the group is skipped). A prose test in `skills/run-autopilot/cli/test_triage_prose.py` pins the new stub sentence.
- A CHANGELOG `[Unreleased]` Fixed entry under **run-autopilot**: `mint-stubs` folds the rows of one finding into one hold stub carrying every ledger key, so a gate decision and its review-close twin no longer mint two stubs, and the stub tells a PRD author to quote the key.

### Nice to have
- `render_report._merge_deferral_sinks` (`skills/run-autopilot/cli/render_report.py:228`) folding the report's Deferred table by the same rule.

## Implementation

### Module: triage-fold
- **Location**: `skills/run-autopilot/cli/triage.py`
- **Responsibility**: group the rows of one finding and mint one stub per group
- **Exports**: `mint_stubs()` (unchanged signature), `fold_key()`, `similar()`
- New symbols: `fold_key`, `similar`

### Module: triage-tests
- **Location**: `skills/run-autopilot/cli/test_triage.py`, `skills/run-autopilot/cli/test_triage_prose.py`
- **Responsibility**: pin the fold, the multi-key ownership and the stub sentence
- **Exports**: none
- New symbols: `test_two_rows_of_one_finding_mint_one_stub_with_both_keys`, `test_rows_with_one_severity_and_file_mint_one_stub`, `test_distinct_findings_of_one_prd_mint_two_stubs`, `test_a_prd_quoting_any_listed_key_owns_the_group`

### Dependencies
- triage-fold: No dependencies (foundation)
- triage-tests: Depends on [triage-fold]

## Tasks

### Phase 0: Foundation
- [ ] Add the four tests and the prose test. Premise: `rg -c "def fold_key" skills/run-autopilot/cli/triage.py` prints 0 before the edit; a different count means the fold already landed and the task stops and reports. - Acceptance: `uv run --no-project --with pytest python -m pytest -q skills/run-autopilot/cli/test_triage.py -k "one_finding or one_severity_and_file or distinct_findings or any_listed_key"` fails all four against the current code.

### Phase 1: Core
- [ ] Implement `fold_key`, `similar`, the grouping in `mint_stubs`, the `ledger_keys:` line and the stub sentence; add the CHANGELOG entry (depends on: Phase 0) - Acceptance: `uv run --no-project --with pytest python -m pytest -q skills/run-autopilot/cli/test_triage.py skills/run-autopilot/cli/test_triage_prose.py` passes; `rg -c "ledger_keys:" skills/run-autopilot/cli/triage.py` prints at least 1; `rg -n "run-autopilot.*mint-stubs.*folds" CHANGELOG.md` prints one line under `[Unreleased]`.

## Success Criteria

- The new tests pass and every existing test in `skills/run-autopilot/cli/test_triage.py` passes unchanged.
- Post-release signal: a finalize over a deferred ledger holding a gate decision and its review-close twin mints one stub, and `wave status` or the batch report never shows two stubs with one title for one source PRD.
