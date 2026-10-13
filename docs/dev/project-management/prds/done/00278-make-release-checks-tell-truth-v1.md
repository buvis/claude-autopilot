---
design: run
default_model: sonnet
model_tier_rationale: mostly wiring and prose; the three red tests and the scratch-replay split are local fixes with existing tests to bind to; 00280's two doc lines and one comment folded in (backlog review 2026-10-12)
---

# The release gate is not the full suite, and its claims are not enforced

## Overview

### Problem Statement

The agoge run of 2026-10-10 (`docs/dev/project-management/audit-results/agoge-2026-10-10.md`,
packets 6, 7, 11, 12, 20; decisions in its `## Minutes`) shows that the gate and the
changelog promise more than they check, and that two contracts go unstated:

- **6 (HIGH):** CHANGELOG line 12 calls `autopilot verify` "the way to run the full
  suite", but `dev/bin/release-checks` named 133 of the 262 tracked test files at the time of
  the report (254 are tracked today; the pin below counts at run time). The files left out
  include `test_state.py`, `test_cli.py`, `test_loop.py` and `test_transitions.py`, and 3 of
  them fail at HEAD and at v0.9.0, so 0.9.0 shipped red outside its gate.
- **7 (HIGH):** CHANGELOG line 28 says the phase-delegation guard catches the missed
  phrasings "while ordinary prose about a phase stays allowed"; at HEAD it denies the
  ordinary question and allows four real delegation phrasings. PRD 00271 (in `wip/`) says
  "the next release is blocked on this PRD", but nothing enforces that.
- **12 (MEDIUM):** `hooks/test_guard_phase_delegation.py:47-49` (`_allow_corpus`) builds
  its allow-test from gitignored `docs/dev/tmp/dispatch-*.txt` whenever any exist, so
  the live record counts 23 tests a clean clone cannot rebuild, and the 24 committed
  allowed fixtures never run in the live checkout.
- **11 (MEDIUM, from PRD 00280, merged 2026-10-12):** `skills/run-autopilot/cli/__main__.py:256`
  imports `datetime.UTC` (Python 3.11+), so on 3.10 every verb fails with `ImportError:
  cannot import name 'UTC' from 'datetime'`. v0.9.0 ran on 3.10. `skills/run-autopilot/SKILL.md:46`
  lists bare `python3`, and nothing names a minimum. The operator chose to declare 3.11 as
  the floor instead of restoring 3.10 support; hold stub 00272 was closed on that decision.
- **20 (LOW, from PRD 00280):** `gate._backed` scans every reviewed row per finding
  (N(N+1)/2 rows: 0.30 s at 5,000 rows, 26 s at 50,000). Real reviews carry dozens. No
  ceiling is stated.

If unchanged: regressions in state, loop and transitions code pass the gate, red
tests stay red across releases, a routine release ships a false changelog
past a block that lives only in prose, and 3.10 users upgrade into a crash with no
warning in the docs.

### Target Users

The operator cutting releases, operators installing the pack, and every loop session that
trusts the gate's counts.

### Success Metrics

- `dev/bin/release-checks` runs every tracked `test_*.py` except the ones its pin's
  `UNGATED` tuple names, and a test fails when a tracked test file is left out.
- The 3 currently red tests pass.
- `dev/bin/release` refuses to start while a `prds/hold/` or `prds/wip/` PRD contains
  "release is blocked".
- Gate counts for the hook block match between the live checkout and a clean clone.
- `skills/run-autopilot/SKILL.md` names Python `>=3.11`, and `[Unreleased] ### Changed` says
  the minimum Python is now 3.11.
- `gate._backed` carries a `ponytail:` ceiling comment naming the quadratic limit and the
  upgrade path.

## Functional Decomposition

### Capability: The gate is the full suite

#### Feature: Fix the 3 red tests (packet 6)
- `skills/run-autopilot/cli/test_doc_contract.py::test_every_registered_subcommand_has_an_autopilot_invocation_in_the_docs`: add the missing `autopilot group-rework` and `autopilot review-stage` invocations to the docs it scans (fix the docs, not the test).
- `skills/work/scripts/test_dispatch_prose.py` (`test_work_skill_body_stays_under_the_500_line_ceiling`): bring `skills/work/SKILL.md` from 505 to 500 lines or fewer by moving text into a reference file.
- `skills/work/scripts/test_dispatch_telemetry_prose.py::test_step_6_5_writes_the_leave_row_before_the_stop` (`ValueError: substring not found`): find which prose moved and fix the prose or report why the test is wrong; do not quietly edit the test.

#### Feature: Gate every tracked test (packet 6)
- **Description**: `dev/bin/release-checks` runs every tracked `test_*.py` (and the existing bash harnesses). Every existing `echo "[checks] <name>"` block and the paths it names stay as they are; the files the script does not name today are added to new or existing blocks. A new test, `test_every_tracked_test_file_is_gated`, compares `git ls-files '*test_*.py'` (run at test time) with the paths literally named in the script, minus an `UNGATED` tuple in the test that lists each intentionally ungated file with a one-line reason; any other difference fails naming the file. Today `UNGATED` holds one entry, `hooks/test_guard_phase_delegation_scratch_replay.py` (reads gitignored scratch input).
- **Constraint**: six prose tests parse the script by its exact `[checks]` lines and the commands between them (`test_release_checks_parallel_prose.py`, `test_wave_docs.py`, `test_triage_prose.py`, `test_enter_prose.py`, `test_design_rework_prose.py`, `test_custody_prose.py`; the script's own header lists them), so the script keeps its block shape; no loop over `git ls-files` replaces the literal lists. The 3 `tracon` tests that error on a missing `rich` need `--with rich` on their run line, not exclusion.
- **Cost**: gate time grows by the ungated files' tests (about 2,300 at the time of the report); measure and report the new wall time in the task report.

### Capability: Release claims are true

#### Feature: Honest guard line (packet 7)
- **Description**: rewrite the CHANGELOG `[Unreleased]` bullet that ends "while ordinary prose about a phase stays allowed" (line 28 today) to the observed split: which phrasings the guard denies and which it still allows, pointing at PRD 00271 for the rest.

#### Feature: Enforced release block (packet 7)
- **Description**: `dev/bin/release` refuses (exit 1, naming the PRD) before `exec "$RELEASE"` when any `docs/dev/project-management/prds/hold/*.md` or `prds/wip/*.md` contains the phrase `release is blocked`.
- **Placement note**: the operator's chosen option named `release-checks`, but `release-checks` is also the review gate every loop cycle runs; a block there would fail every gate while 00271 sits in `hold/` or `wip/`. The check goes in the release shim, which only a release runs.

### Capability: Reproducible counts

#### Feature: Committed fixtures in the gate (packet 12)
- **Description**: `_allow_corpus` always returns the committed `fixtures/phase_delegation/allowed/*.txt`. The scratch replay moves to a separate test, `hooks/test_guard_phase_delegation_scratch_replay.py`, that skips with a stated reason when no scratch files exist and is not run by `release-checks`: it is the one entry in the pin's `UNGATED` tuple.

### Capability: Stated contracts

#### Feature: Python floor (packet 11)
- **Description**: `skills/run-autopilot/SKILL.md:46` reads `python3` (>= 3.11). CHANGELOG `[Unreleased] ### Changed`: `**run-autopilot**: the CLI now needs Python 3.11 or newer (it uses datetime.UTC); 3.10 is no longer supported`.

#### Feature: Ceiling comment (packet 20)
- **Description**: a `# ponytail:` comment above `gate._backed`: quadratic in reviewed rows, fine at real sizes (dozens), index rows by ref and by (severity, file, issue) if reviews ever reach thousands.

## Structural Decomposition

### Repository Structure

```
CHANGELOG.md                                          # line 28 rewritten; [Unreleased] Changed: Python 3.11 floor
dev/bin/
├── release                                           # hold/wip "release is blocked" refusal
└── release-checks                                    # every tracked test_*.py, blocks kept
hooks/
├── test_guard_phase_delegation.py                    # committed fixtures only
└── test_guard_phase_delegation_scratch_replay.py     # NEW: scratch replay, outside the gate (UNGATED)
skills/run-autopilot/
├── SKILL.md                                          # line 46: python3 (>= 3.11)
├── cli/
│   ├── gate.py                                       # ponytail ceiling comment on _backed
│   ├── test_doc_contract.py                          # read only: red test 1
│   └── test_release_checks_counts.py                 # NEW assertions: pin and release refusal
└── references/                                       # docs gaining group-rework / review-stage invocations
skills/work/
├── SKILL.md                                          # trimmed to <= 500 lines
├── references/                                       # receives the moved text
└── scripts/
    ├── test_dispatch_prose.py                        # read only: red test 2
    └── test_dispatch_telemetry_prose.py              # read only: red test 3
```

### Module: release gate
- **Maps to capability**: The gate is the full suite; Release claims are true (the shim)
- **Responsibility**: run every tracked test file inside the existing `[checks]` blocks, pin that set, and refuse a release a held or in-flight PRD blocks.
- **Exports**: none (shell scripts); the pin's `UNGATED` tuple lives in `test_release_checks_counts.py`.
- New symbols: `UNGATED`, `test_every_tracked_test_file_is_gated`, `test_release_refuses_while_a_held_prd_blocks_it`

### Module: hooks guard tests
- **Maps to capability**: Reproducible counts
- **Responsibility**: `_allow_corpus` reads committed fixtures only; the scratch replay has its own file.
- **Exports**: `_allow_corpus` (unchanged name).
- New symbols: `test_guard_phase_delegation_scratch_replay.py`, `test_allow_corpus_ignores_scratch_dispatch_files`

### Module: release prose
- **Maps to capability**: Release claims are true; Stated contracts
- **Responsibility**: the CHANGELOG bullets, the SKILL.md prerequisite line, the `_backed` comment, the trimmed work skill and its reference file, the doc invocations red test 1 needs.
- **Exports**: none.

## Dependency Graph

### Foundation Layer (Phase 0)
- **red tests**, **scratch split**, **CHANGELOG line 28**, **release shim**, **stated contracts**: independent.

### Core Layer (Phase 1)
- **gate every test**: depends on [red tests, scratch split].

## Implementation Phases

### Phase 0: Foundation
**Tasks**:
- [ ] fix red test 1: add the missing doc invocations (no deps) - Acceptance: `uv run --no-project --with pytest python -m pytest -q skills/run-autopilot/cli/test_doc_contract.py` exits 0.
- [ ] fix red test 2: trim `skills/work/SKILL.md` to <= 500 lines (no deps) - Acceptance: the 500-line ceiling test passes.
- [ ] fix red test 3: the leave-row ordering test passes, or the task report explains why the test is wrong (no deps) - Acceptance: `test_step_6_5_writes_the_leave_row_before_the_stop` passes.
- [ ] hooks: committed fixtures only in the gate; new scratch-replay test (no deps) - Acceptance: `test_allow_corpus_ignores_scratch_dispatch_files` (a scratch file present, corpus equals the committed fixtures) passes and fails at base.
- [ ] CHANGELOG line 28 rewritten to the observed split (no deps) - Acceptance: `rg -n "stays allowed" CHANGELOG.md` prints nothing while `rg -n "00271" CHANGELOG.md` hits inside `[Unreleased]`.
- [ ] release shim: refuse while a hold/wip PRD says "release is blocked" (no deps) - Acceptance: a test in `skills/run-autopilot/cli/test_release_checks_counts.py`, `test_release_refuses_while_a_held_prd_blocks_it`, runs `dev/bin/release` against a fixture store with such a PRD and a stub `claude-plugins` dir and sees exit 1 before the stub runs; fails at base.
- [ ] SKILL.md and CHANGELOG state the 3.11 floor (no deps) - Acceptance: `rg -n "3\.11" skills/run-autopilot/SKILL.md` hits on the CLIs prerequisite line, and `rg -n "Python 3\.11" CHANGELOG.md` hits inside `[Unreleased]`; docs-only, no behaviour to test.
- [ ] gate: ponytail ceiling comment on `_backed` (no deps) - Acceptance: `rg -n "ponytail:.*quadratic" skills/run-autopilot/cli/gate.py` prints one line while `rg -n "def _backed" skills/run-autopilot/cli/gate.py` hits (control); comment-only.

**Exit Criteria**: each Acceptance command above exits 0.

### Phase 1: Core
**Tasks**:
- [ ] release-checks names every tracked `test_*.py` inside its existing `[checks]` blocks (new blocks for new groups, `--with rich` on the tracon block); the pin `test_every_tracked_test_file_is_gated` with its `UNGATED` tuple (depends on: Phase 0) - Acceptance: `test_every_tracked_test_file_is_gated` in `test_release_checks_counts.py` passes and fails at base; the six `[checks]`-parsing prose tests named in the Constraint still pass; `bash dev/bin/release-checks` exits 0 with `FAIL 0`; the task report states the new wall time.

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
11: HEAD `uv run --python 3.10 python -m cli --help` gives `ImportError: cannot import name 'UTC'
    from 'datetime'`. A v0.9.0 worktree prints usage.
12: Live `gate-04d38af.log` gives `hook registration ... 251 passed`; the clone gives
   `228 passed`; every other block is equal.
20: Rows scanned: 125,250 / 12,502,500 / 1,250,025,000 at 500 / 5,000 / 50,000 rows (N(N+1)/2).
    Wall time: 0.30 s at 5,000 rows, 26 s at 50,000.
```

Packets 11 and 20 need no new test: both changes are documentation. A 3.10 import smoke test was offered and not chosen.

## Risks

- **Gate time grows** with about 2,300 more tests (today ~220 s per run, every cycle); flaky tests that were never gated may surface.
- **Text-match release block** is crude: a quoted "release is blocked" anywhere in a held or in-flight PRD blocks releases.
- **Scratch replay leaves the gate**: real-prompt replay has caught guard false positives before; it now runs only on demand.
- **The pin is a standing obligation**: every later PRD that adds a `test_*.py` file must name it in `release-checks` (or in `UNGATED` with a reason) or the gate goes red; the pin's failure message names the file.
- **Drops 3.10 users**: accepted by the operator (packet 11 option 2).
- Source: `docs/dev/project-management/audit-results/agoge-2026-10-10.md` (2026-10-10); PRD 00280 merged here by the backlog review of 2026-10-12.
