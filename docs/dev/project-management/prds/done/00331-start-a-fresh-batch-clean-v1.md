---
design: skip
default_model: sonnet
model_tier_rationale: three transcription edits with their exact text (an unlink pair inside an existing branch, one stop-detail string, one extra existence test) plus additive tests in the existing enter and runner harnesses
---

# Start a fresh batch clean

Source: batch 202610161547's first session (2026-10-16 13:46Z, session cdf17745; its row in `docs/dev/project-management/autopilot/loop-metrics.jsonl` reads `wall_secs` 2740, `cost_usd` 23.07): 30 requests between launch and the PRD banner.

## Problem

A fresh batch starts with the previous batch's hand-off artifacts still beside `state.json`. The loop writes `session-brief.md` at every hand-off (`statectl.write_brief`, `skills/run-autopilot/cli/loop.py:633`), and `prompt_for` (`skills/run-autopilot/cli/runner.py:99-106`) appends `BRIEF_SUFFIX` to the launch prompt whenever that file exists.

At batch end `state.json` is archived and removed, but the brief and `contract-card.md` stay: `_prepare_tree` (`skills/run-autopilot/cli/enter.py:85-106`) bootstraps the skeleton state at lines 103-104 and unlinks only the `MARKERS` tuple of `handoff` (`skills/run-autopilot/cli/handoff.py:25`, the `.handoff-requested` and `.cap-fired` files). On 2026-10-16 the new batch's first session was therefore told to read a brief written for PRD 00313 at `done -> done` ("Read next: phase-done.md") while entering the build gate for 00320, beside a contract card saying "PRD 00312 CONVERGED, do NOT run another review cycle".

The same session then ran `autopilot init` three times. `_batch_report` (`skills/run-autopilot/cli/enter.py:227-239`) had stopped with `batch absent; initialize a batch first`, which reads as `autopilot init`; but `_run_init` (`skills/run-autopilot/cli/__main__.py:345-362`) refuses an existing state file with exit 7, and the `batch_init` row at `skills/run-autopilot/references/phase-build.md:47` means "mint `state.batch` via statectl, then run `enter` again". The session also tried `init --help`, a `python3 -c` import and a hook-blocked `| head` before it found the statectl route.

## Solution

Three one-line changes in the driver, all covered by existing test harnesses. `_prepare_tree` deletes `session-brief.md` and `contract-card.md` in the branch that creates the skeleton state (a fresh batch), so a resume with `state.json` present keeps both files. `prompt_for` appends the brief sentence only when `state.json` exists beside the brief, so the launch prompt of a fresh batch never points at a file `enter` is about to delete. `_batch_report`'s `batch_init` detail names the route: mint `state.batch` with statectl (phase-build.md Phase 0 step 3) and run `enter` again, never `autopilot init`. The exit-7 message of `_run_init` already names the path in the checkout (`skills/run-autopilot/cli/__main__.py:345-362`) and needs no change.

## Requirements

### Must have
- When `enter` creates the skeleton state (`state_path` absent), `docs/dev/project-management/autopilot/session-brief.md` and `docs/dev/project-management/autopilot/contract-card.md` are absent afterwards; when `state_path` exists, both files are byte-unchanged; `handoff.MARKERS` clearing is unchanged.
- `prompt_for` appends `BRIEF_SUFFIX` only when both `session-brief.md` and `state.json` exist in `autopilot_dir`; the CLI sentence logic is unchanged.
- The two existing runner tests that assert the brief sentence, `test_prompt_names_the_brief_when_present` (`skills/run-autopilot/cli/test_runner.py:216-229`) and `test_launch_prompt_forbids_blocked_coreutils` (`skills/run-autopilot/cli/test_runner.py:258-278`), write `state.json` into `ap` beside the brief; their assertions and the file's test count are otherwise unchanged.
- The `batch_init` stop detail is exactly `batch <absent|closed>; mint state.batch with statectl (phase-build.md Phase 0 step 3), then run enter again; never autopilot init`; `out["stop"]` and `out["batch"]` are unchanged.
- Fail-first tests in `skills/run-autopilot/cli/test_enter.py` (registered under `[checks] enter`, `dev/bin/release-checks:312`) and `skills/run-autopilot/cli/test_runner.py` (registered under `[checks] l3`, `dev/bin/release-checks:207`).
- A CHANGELOG `[Unreleased]` Fixed entry under **run-autopilot**.

### Nice to have
- None.

## Implementation

### Module: fresh-batch-bootstrap
- **Location**: `skills/run-autopilot/cli/enter.py` (`_prepare_tree`, `_batch_report`), `skills/run-autopilot/cli/runner.py` (`prompt_for`)
- **Responsibility**: a fresh batch's first session sees no stale brief or card, is not told to read one, and is told the statectl route
- **Exports**: `enter()`, `prompt_for()` (unchanged signatures)

### Module: fresh-batch-bootstrap-tests
- **Location**: `skills/run-autopilot/cli/test_enter.py`, `skills/run-autopilot/cli/test_runner.py`
- **Responsibility**: pin the three behaviors through the `Env` harness (`cli/enter_harness.py`) and the runner's prompt test
- **Exports**: none
- New symbols: `test_fresh_batch_bootstrap_removes_the_stale_brief_and_card`, `test_resume_keeps_the_brief_and_card`, `test_batch_init_detail_names_the_statectl_route`, `test_prompt_omits_the_brief_sentence_without_a_state_file`

### Dependencies
- fresh-batch-bootstrap-tests: No dependencies (foundation)
- fresh-batch-bootstrap: Depends on [fresh-batch-bootstrap-tests]

## Tasks

### Phase 0: Foundation
- [ ] Add three tests to `skills/run-autopilot/cli/test_enter.py` using its `env` fixture, and one to `skills/run-autopilot/cli/test_runner.py` beside the `BRIEF_SUFFIX` assertion at `skills/run-autopilot/cli/test_runner.py:278`. `test_fresh_batch_bootstrap_removes_the_stale_brief_and_card` writes `session-brief.md` and `contract-card.md` under `env.autopilot_dir`, writes no state, puts a wip PRD, runs `env.run()`, asserts both files are gone and the state file exists with `phase == "build"`. `test_resume_keeps_the_brief_and_card` writes both files and `_open_state()`, puts a wip PRD, runs, asserts both files still hold their bytes. `test_batch_init_detail_names_the_statectl_route` arranges the absent-batch case exactly as `test_absent_and_closed_batch_stop_batch_init` (`skills/run-autopilot/cli/test_enter.py:549`) does, runs, asserts `out["stop"] == "batch_init"` and `out["detail"] == "batch absent; mint state.batch with statectl (phase-build.md Phase 0 step 3), then run enter again; never autopilot init"`. `test_prompt_omits_the_brief_sentence_without_a_state_file` writes only `session-brief.md` into a temp `autopilot_dir` and asserts `prompt_for(autopilot_dir)` does not contain `BRIEF_SUFFIX`, then writes `state.json` and asserts it does - Acceptance: `uv run --no-project --with pytest python -m pytest -q skills/run-autopilot/cli/test_enter.py skills/run-autopilot/cli/test_runner.py -k "stale_brief or keeps_the_brief or statectl_route or without_a_state_file"` reports `test_resume_keeps_the_brief_and_card` passing and the other three failing at the task's base commit.

### Phase 1: Core
- [ ] In `skills/run-autopilot/cli/enter.py` `_prepare_tree`, inside the `if not state_path.exists():` branch after `state.init(...)`, add `for name in ("session-brief.md", "contract-card.md"): (autopilot_dir / name).unlink(missing_ok=True)`; in `_batch_report` replace the `_stop` detail with `f"batch {out['batch']}; mint state.batch with statectl (phase-build.md Phase 0 step 3), then run enter again; never autopilot init"`; in `skills/run-autopilot/cli/runner.py` `prompt_for` replace the brief test with `brief = BRIEF_SUFFIX if (autopilot_dir / BRIEF_NAME).is_file() and (autopilot_dir / "state.json").is_file() else ""`; in `skills/run-autopilot/cli/test_runner.py` add `(ap / "state.json").write_text("{}\n")` right after the `session-brief.md` write in `test_prompt_names_the_brief_when_present` (`skills/run-autopilot/cli/test_runner.py:216-229`) and in `test_launch_prompt_forbids_blocked_coreutils` (`skills/run-autopilot/cli/test_runner.py:258-278`). Premise, re-checked at execution: both tests write `session-brief.md` and no `state.json`; if either already writes `state.json`, skip that edit and report it (depends on: Phase 0) - Acceptance: `uv run --no-project --with pytest python -m pytest -q skills/run-autopilot/cli/test_enter.py skills/run-autopilot/cli/test_enter_prose.py skills/run-autopilot/cli/test_store_gitignore.py skills/run-autopilot/cli/test_runner.py` passes; `rg -c '^def test_' skills/run-autopilot/cli/test_runner.py` prints the task's base-commit count.
- [ ] Add the CHANGELOG `[Unreleased]` Fixed entry `**run-autopilot**: a fresh batch no longer starts from the previous batch's session brief and contract card, and the batch-absent stop names the statectl route instead of inviting autopilot init` (depends on: Phase 1 code) - Acceptance: `rg -c 'no longer starts from the previous batch' CHANGELOG.md` prints 1.

## Success Criteria

- The next fresh batch's first session reaches its `── AUTOPILOT ── PRD 1:` banner with no `Read` of `session-brief.md` and no `autopilot init` call in its transcript.
- `test_enter.py` and `test_runner.py` are green; `test_fresh_wip_prd_continues_with_null_stop` (`skills/run-autopilot/cli/test_enter.py:63`) still passes, so marker clearing is unchanged.
