---
design: skip
default_model: sonnet
model_tier_rationale: two small code changes with their exact behavior given, prose rewrites given verbatim, additive tests with their assertions given
---

# Stamp the build start in code and name the closed PRD in the done commit

Source: batch 202610100952 in the agent-skills repo, 2026-10-18. The 00088 review session found `state.work_start_sha` empty at the review gate ("the build session never captured it"), reconstructed the range from the parent of the first work commit and recorded the guess as an autonomous decision; a wrong guess there reviews the wrong range. The same day the done gate that closed 00087 committed as `chore(autopilot): record done state for 00088-document-the-eval-harness-contract-v1.md` (agent-skills commit 1dd9899), because the gate had already selected 00088 when it recorded the store, so the batch's git history attributes every close to the next PRD.

## Problem

The start sha is a prose duty. `skills/run-autopilot/SKILL.md:279` tells the build session to run `git rev-parse HEAD` and write `state.work_start_sha` once per PRD, `skills/run-autopilot/SKILL.md:281` names the empty-tree sentinel for an unborn branch, and `skills/run-autopilot/references/phase-build.md:378` repeats the duty; the field is declared in `skills/run-autopilot/cli/schema.py:61`, read by `lane-check` (`skills/run-autopilot/cli/__main__.py:775`), by `diff_signal` (`skills/run-autopilot/cli/lane_check.py:54`) and by the custody capture (`skills/run-autopilot/cli/records.py:270`), and written by no verb. `_select` in `skills/run-autopilot/cli/enter.py:184` is the one place every fresh selection passes: it moves the PRD from `backlog` into wip (`skills/run-autopilot/cli/enter.py:216`) and returns without recording where the work starts.

The done commit's subject comes from `record_store` (`skills/run-autopilot/cli/store_tree.py:156`), whose `message` line (`skills/run-autopilot/cli/store_tree.py:162`) names the PRD the caller passed, and the leave step tells every site to pass `state.prd` (`skills/run-autopilot/SKILL.md:201`); at the done site that is the next PRD.

## Solution

`_select` stamps the start: right after the verified move into wip, when the loaded state's `work_start_sha` is empty, it runs `git rev-parse HEAD` in the state's `repo_root` (with `--git-dir` from the state's `git_dir` when that field is set) and writes the sha through `_mutate` (`skills/run-autopilot/cli/enter.py:76`) under the site `work_start_sha`; when the command fails it writes the empty-tree sentinel `4b825dc642cb6eb9a060e54bf8d69288fbee4904` and appends `work_start_sha: unborn HEAD, empty-tree sentinel stamped` to `out["detail"]`. The two wip-resume returns, the one guarded by `prd_arg` (`skills/run-autopilot/cli/enter.py:194`) and the one guarded by `source` (`skills/run-autopilot/cli/enter.py:214`), are untouched, so a resume never re-stamps. The paragraph at `skills/run-autopilot/SKILL.md:279` becomes: `**work_start_sha is stamped by autopilot enter.** The verb writes git rev-parse HEAD into state.work_start_sha when it moves a PRD into wip/, and the empty-tree sentinel 4b825dc642cb6eb9a060e54bf8d69288fbee4904 when HEAD is unborn; a resume keeps the value. Before dispatching /autopilot:work, read the field: an empty value is a verb defect, so STOP and report it instead of guessing a range.` (symbols in backticks), the paragraph at `skills/run-autopilot/SKILL.md:281` is deleted, and `skills/run-autopilot/references/phase-build.md:378` becomes `**Check work_start_sha** per core SKILL.md § "Phase 3 invariants": autopilot enter stamped it at selection; an empty value stops the session.`

`_run_record_store` (`skills/run-autopilot/cli/__main__.py:1861`) resolves the PRD it names: for `--site done` it reads the state file and uses the `filename` of the last entry of `batch.completed_prds` when that list is non-empty, else the `--prd` it was given; the other sites keep `--prd`. The leave step (`skills/run-autopilot/SKILL.md:201`) keeps `state.prd` as the value for build and review and omits the flag at the done site, where the verb names the PRD it just closed.

## Requirements

### Must have
- The stamp in `_select` as above, the sentinel on failure, no re-stamp on resume.
- The done-site resolution in `_run_record_store` as above.
- The three prose edits, verbatim apart from backticks.
- Tests in `skills/run-autopilot/cli/test_enter.py`: `test_enter_stamps_work_start_sha_on_a_fresh_selection` (a backlog PRD, a repo with one commit: the state's `work_start_sha` equals `git rev-parse HEAD` after `enter`), `test_enter_keeps_work_start_sha_on_a_wip_resume` (a wip PRD and a pre-set value `abc123`: unchanged after `enter`), `test_enter_stamps_the_empty_tree_sentinel_when_rev_parse_fails` (an empty repo: the sentinel, and `detail` names it). A test in `skills/run-autopilot/cli/test_store_tree_record_store.py`: `test_done_site_names_the_prd_just_closed` (a state whose `prd` is `00002-next-v1.md` and whose `batch.completed_prds` ends with `00001-closed-v1.md`: the commit subject reads `chore(autopilot): record done state for 00001-closed-v1.md`). A prose test in `skills/run-autopilot/cli/test_enter_prose.py`: `test_skill_says_enter_stamps_the_start_sha` asserts the skill contains `stamped by autopilot enter` and no longer contains `write it to state.work_start_sha before dispatching`.
- A CHANGELOG `[Unreleased]` Fixed entry under **run-autopilot**: `autopilot enter` stamps `work_start_sha` when it selects a PRD, so a build session can no longer leave the review range undefined; the done-gate store commit names the PRD it closed, not the one selected next.

### Nice to have
- None.

## Implementation

### Module: enter-stamp
- **Location**: `skills/run-autopilot/cli/enter.py`
- **Responsibility**: record where a PRD's work range starts, once, at selection
- **Exports**: `enter()` (unchanged signature)

### Module: record-store-site
- **Location**: `skills/run-autopilot/cli/__main__.py`
- **Responsibility**: name the right PRD in a store commit
- **Exports**: none (the `record-store` verb keeps its flags)

### Module: loop-prose
- **Location**: `skills/run-autopilot/SKILL.md`, `skills/run-autopilot/references/phase-build.md`
- **Responsibility**: describe the verb's duty and the session's check
- **Exports**: none

### Module: tests
- **Location**: `skills/run-autopilot/cli/test_enter.py`, `skills/run-autopilot/cli/test_store_tree_record_store.py`, `skills/run-autopilot/cli/test_enter_prose.py`
- **Responsibility**: pin the stamp, the resume, the sentinel, the done subject and the prose
- **Exports**: none
- New symbols: `test_enter_stamps_work_start_sha_on_a_fresh_selection`, `test_enter_keeps_work_start_sha_on_a_wip_resume`, `test_enter_stamps_the_empty_tree_sentinel_when_rev_parse_fails`, `test_done_site_names_the_prd_just_closed`, `test_skill_says_enter_stamps_the_start_sha`

### Dependencies
- enter-stamp: No dependencies (foundation)
- record-store-site: No dependencies (foundation)
- loop-prose: Depends on [enter-stamp, record-store-site]
- tests: Depends on [enter-stamp, record-store-site, loop-prose]

## Tasks

### Phase 0: Foundation
- [ ] Add the five tests. Premise: `rg -c "work_start_sha" skills/run-autopilot/cli/enter.py` prints 0 before the edit; a different count means the stamp already landed and the task stops and reports. - Acceptance: `uv run --no-project --with pytest python -m pytest -q skills/run-autopilot/cli/test_enter.py skills/run-autopilot/cli/test_store_tree_record_store.py skills/run-autopilot/cli/test_enter_prose.py -k "work_start_sha or empty_tree or prd_just_closed or stamps_the_start"` fails all five against the current code and prose.

### Phase 1: Core
- [ ] Implement the stamp and the done-site resolution, make the three prose edits, add the CHANGELOG entry (depends on: Phase 0) - Acceptance: `uv run --no-project --with pytest python -m pytest -q skills/run-autopilot/cli/test_enter.py skills/run-autopilot/cli/test_store_tree_record_store.py skills/run-autopilot/cli/test_enter_prose.py` passes; `rg -c "stamped by autopilot enter" skills/run-autopilot/SKILL.md` prints 1; `rg -c "empty-tree sentinel" skills/run-autopilot/SKILL.md` prints 1; `rg -n "run-autopilot.*stamps.*work_start_sha" CHANGELOG.md` prints one line under `[Unreleased]`.

## Success Criteria

- The three test modules pass in full and the existing `enter` tests pass unchanged.
- Post-release signal: no review session of the next batch records a reconstructed `work_start_sha`, and every `record done state for` commit names the PRD moved to `done/` in that same commit.
