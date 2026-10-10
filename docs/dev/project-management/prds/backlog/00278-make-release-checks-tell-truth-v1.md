---
design: run
default_model: sonnet
model_tier_rationale: mostly wiring and prose; the three red tests and the scratch-replay split are local fixes with existing tests to bind to
---

# The release gate is not the full suite, and its claims are not enforced

## Overview

### Problem Statement

The agoge run of 2026-10-10 (`docs/dev/project-management/audit-results/agoge-2026-10-10.md`,
packets 6, 7, 12; decisions in its `## Minutes`) shows that the gate and the
changelog promise more than they check:

- **6 (HIGH):** CHANGELOG line 12 calls `autopilot verify` "the way to run the full
  suite", but `dev/bin/release-checks` names 133 of 262 tracked test files. The 113
  left out include `test_state.py`, `test_cli.py`, `test_loop.py` and
  `test_transitions.py`, and 3 of them fail at HEAD and at v0.9.0, so 0.9.0 shipped
  red outside its gate.
- **7 (HIGH):** CHANGELOG line 25 says the phase-delegation guard catches the missed
  phrasings "while ordinary prose about a phase stays allowed"; at HEAD it denies the
  ordinary question and allows four real delegation phrasings. PRD 00271 (held) says
  "the next release is blocked on this PRD", but nothing enforces that.
- **12 (MEDIUM):** `hooks/test_guard_phase_delegation.py:47-49` (`_allow_corpus`) builds
  its allow-test from gitignored `docs/dev/tmp/dispatch-*.txt` whenever any exist, so
  the live record counts 23 tests a clean clone cannot rebuild, and the 24 committed
  allowed fixtures never run in the live checkout.

If unchanged: regressions in state, loop and transitions code pass the gate, red
tests stay red across releases, and a routine release ships a false changelog
past a block that lives only in prose.

### Target Users

The operator cutting releases, and every loop session that trusts the gate's counts.

### Success Metrics

- `dev/bin/release-checks` runs every tracked `test_*.py`, and a test fails when a
  tracked test file is left out.
- The 3 currently red tests pass.
- `dev/bin/release` refuses to start while a `prds/hold/` or `prds/wip/` PRD contains
  "release is blocked".
- Gate counts for the hook block match between the live checkout and a clean clone.

## Functional Decomposition

### Capability: The gate is the full suite

#### Feature: Fix the 3 red tests (packet 6)
- `skills/run-autopilot/cli/test_doc_contract.py::test_every_registered_subcommand_has_an_autopilot_invocation_in_the_docs`: add the missing `autopilot group-rework` and `autopilot review-stage` invocations to the docs it scans (fix the docs, not the test).
- `skills/work/scripts/test_dispatch_prose.py` or `test_dispatch_telemetry_prose.py` (`test_work_skill_body_stays_under_the_500_line_ceiling`): bring `skills/work/SKILL.md` from 506 to 500 lines or fewer by moving text into a reference file.
- `test_step_6_5_writes_the_leave_row_before_the_stop` (`ValueError: substring not found`): find which prose moved and fix the prose or report why the test is wrong; do not quietly edit the test.

#### Feature: Gate every tracked test (packet 6)
- **Description**: `dev/bin/release-checks` runs every tracked `test_*.py` (and the existing bash harnesses), and a new test fails when `git ls-files '*test_*.py'` names a file the script does not run.
- **Constraint**: the 3 `tracon` tests that error on a missing `rich` need `--with rich` (or the equivalent) in their run line, not exclusion.
- **Cost**: gate time grows by 2,323 tests; measure and report the new wall time in the task report.

### Capability: Release claims are true

#### Feature: Honest guard line (packet 7)
- **Description**: rewrite CHANGELOG line 25 to the observed split: which phrasings the guard denies and which it still allows, pointing at PRD 00271 for the rest.

#### Feature: Enforced release block (packet 7)
- **Description**: `dev/bin/release` refuses (exit 1, naming the PRD) before `exec "$RELEASE"` when any `docs/dev/project-management/prds/hold/*.md` or `prds/wip/*.md` contains the phrase `release is blocked`.
- **Placement note**: the operator's chosen option named `release-checks`, but `release-checks` is also the review gate every loop cycle runs; a block there would fail every gate while 00271 sits in `hold/`. The check goes in the release shim, which only a release runs.

### Capability: Reproducible counts

#### Feature: Committed fixtures in the gate (packet 12)
- **Description**: `_allow_corpus` always returns the committed `fixtures/phase_delegation/allowed/*.txt`. The scratch replay moves to a separate test, `hooks/test_guard_phase_delegation_scratch_replay.py`, that skips with a stated reason when no scratch files exist and is not run by `release-checks`.

## Structural Decomposition

### Repository Structure

```
CHANGELOG.md                                          # line 25 rewritten
dev/bin/
├── release                                           # hold/wip "release is blocked" refusal
└── release-checks                                    # every tracked test_*.py
hooks/
├── test_guard_phase_delegation.py                    # committed fixtures only
└── test_guard_phase_delegation_scratch_replay.py     # NEW: scratch replay, outside the gate
skills/run-autopilot/cli/
├── test_doc_contract.py                              # read only: red test 1
└── test_release_checks_counts.py                     # NEW assertion: no tracked test left out
skills/run-autopilot/references/                      # docs gaining group-rework / review-stage invocations
skills/work/
├── SKILL.md                                          # trimmed to <= 500 lines
├── references/                                       # receives the moved text
└── scripts/
    ├── test_dispatch_prose.py                        # read only: red tests 2-3
    └── test_dispatch_telemetry_prose.py              # read only: red tests 2-3
```

## Dependency Graph

### Foundation Layer (Phase 0)
- **red tests**, **scratch split**, **CHANGELOG line 25**, **release shim**: independent.

### Core Layer (Phase 1)
- **gate every test**: depends on [red tests, scratch split].

## Implementation Phases

### Phase 0: Foundation
**Tasks**:
- [ ] fix red test 1: add the missing doc invocations (no deps) - Acceptance: `uv run --no-project --with pytest python -m pytest -q skills/run-autopilot/cli/test_doc_contract.py` exits 0.
- [ ] fix red test 2: trim `skills/work/SKILL.md` to <= 500 lines (no deps) - Acceptance: the 500-line ceiling test passes.
- [ ] fix red test 3: the leave-row ordering test passes, or the task report explains why the test is wrong (no deps) - Acceptance: `test_step_6_5_writes_the_leave_row_before_the_stop` passes.
- [ ] hooks: committed fixtures only in the gate; new scratch-replay test (no deps) - Acceptance: `test_allow_corpus_ignores_scratch_dispatch_files` (a scratch file present, corpus equals the committed fixtures) passes and fails at base.
- [ ] CHANGELOG line 25 rewritten to the observed split (no deps) - Acceptance: `rg -n "stays allowed" CHANGELOG.md` prints nothing while `rg -n "00271" CHANGELOG.md` hits inside `[Unreleased]`.
- [ ] release shim: refuse while a hold/wip PRD says "release is blocked" (no deps) - Acceptance: a test in `skills/run-autopilot/cli/test_release_checks_counts.py`, `test_release_refuses_while_a_held_prd_blocks_it`, runs `dev/bin/release` against a fixture store with such a PRD and a stub `claude-plugins` dir and sees exit 1 before the stub runs; fails at base.

**Exit Criteria**: each Acceptance command above exits 0.

### Phase 1: Core
**Tasks**:
- [ ] release-checks runs every tracked `test_*.py`; pin against omissions (depends on: Phase 0) - Acceptance: `test_every_tracked_test_file_is_gated` in `test_release_checks_counts.py` passes and fails at base; `bash dev/bin/release-checks` exits 0 with `FAIL 0`; the task report states the new wall time.

**Exit Criteria**: `bash dev/bin/release-checks` exits 0 with `FAIL 0` on its summary line.

## Test Strategy

### Critical Scenarios

Reproductions from the report, verbatim:

```
6: `pytest -n auto @ungated.txt` in a clone gives `3 failed, 2323 passed, 1 skipped, 3 errors`
   (the 3 errors are tracon tests missing `rich`, environment only). The failures:
   `test_every_registered_subcommand_has_an_autopilot_invocation_in_the_docs`
   (`['group-rework', 'review-stage'] != []`), `test_work_skill_body_stays_under_the_500_line_ceiling`
   (506 lines), and `test_step_6_5_writes_the_leave_row_before_the_stop`
   (`ValueError: substring not found`). The same 3 fail in a v0.9.0 worktree.
7: HEAD hook with `_AUTOPILOT_LOOP=1`: `'Do the work phase tests pass?'` exits 2 (deny), while
   `'Run your work phase for PRD 00300 now.'`, `'Kick off the work phase...'`,
   `'Run the work-phase...'` and `'/autopilot:work docs/...'` exit 0 (allow).
12: Live `gate-04d38af.log` gives `hook registration ... 251 passed`; the clone gives
   `228 passed`; every other block is equal.
```

## Risks

- **Gate time grows** with 2,323 more tests (today ~220 s per run, every cycle); flaky tests that were never gated may surface.
- **Text-match release block** is crude: a quoted "release is blocked" anywhere in a held PRD blocks releases.
- **Scratch replay leaves the gate**: real-prompt replay has caught guard false positives before; it now runs only on demand.
- Source: `docs/dev/project-management/audit-results/agoge-2026-10-10.md` (2026-10-10).
