---
design: run
default_model: sonnet
model_tier_rationale: one prose rule replaced by an existing coded verdict, plus a narrower normalize_command; both have tests to bind to
---

# Two reuse rules disagree, and commands that run differently share a record

## Overview

### Problem Statement

The agoge run of 2026-10-10 (`docs/dev/project-management/audit-results/agoge-2026-10-10.md`,
packets 8 and 9; decisions in its `## Minutes`) shows that the review's `Tests:`
line is decided by a weaker rule than the one in code, and that the coded rule
joins commands that do not run the same way:

- **8 (MEDIUM):** `skills/review-work-completion/SKILL.md:402` reuses the record when
  `sha` equals HEAD and the counts are non-null, else runs `verify`. `review-stage`
  uses `verification.reuse_verdict` (ancestor plus store-only diff, matching command,
  `failed == 0`, clean tree). In both 00270 cycles `review-stage` said `reused`, yet
  the session ran `verify` anyway (221.7 s and 219.1 s) because loop store commits
  moved HEAD. The prose rule also reuses a subset command over a dirty tree, where
  the code says `stale`.
- **9 (MEDIUM):** `verification.normalize_command` strips one leading `bash `/`sh ` and
  one `./`, so `bash X`, `sh X`, `./X` and `X` share one record although they differ
  in shell, exec bit and PATH lookup. CHANGELOG line 41 says only "different
  whitespace", and `skills/work/references/final-verification.md` documents the stored
  command as "as run" while it stores the stripped form.

If unchanged: about 220 s wasted per review cycle, a `Tests:` line that can show
a subset run over a dirty tree, and gate commands that cannot run reading green.

### Target Users

Review sessions composing the `Tests:` line, and the operator reading it.

### Success Metrics

- Step 6 composes `Tests:` from `review-stage`'s `gate.tests_line` and has no
  sha/counts rule of its own.
- A record made by `bash X` is `stale` for `sh X`, `./X` and `X`.
- CHANGELOG and `final-verification.md` describe the stored command truthfully.

## Functional Decomposition

### Capability: One reuse rule

#### Feature: Step 6 takes review-stage's line (packet 8)
- **Description**: `review-work-completion/SKILL.md` step 6 composes the `Tests:` line from step 3's `gate.tests_line` (which `review-stage` already derived through `reuse_verdict` or a fresh run). It runs `autopilot verify` only when `gate.tests_line` is absent (review-stage ran without `--gate-command`). The paragraph's "`sha` equals this cycle's reviewed HEAD **and** its three counts are non-null" rule is removed. The docs-only check and the `(reused ...)` / `(suite run this cycle)` suffix rule stay.

### Capability: Exact commands

#### Feature: Whitespace-only normalization (packet 9)
- **Description**: `normalize_command` collapses whitespace only; it no longer strips `bash `/`sh ` or `./`. `_write_record` stores the raw command as run.
- **Prose**: CHANGELOG line 41 and `final-verification.md`'s "as run" text match the new behaviour.

## Structural Decomposition

### Repository Structure

```
CHANGELOG.md                                     # line 41 corrected; [Unreleased] Changed line
dev/bin/
└── release-checks                               # registers the new prose test
skills/review-work-completion/
├── SKILL.md                                     # step 6 Tests: line from gate.tests_line
└── scripts/                                     # NEW prose test for the step 6 rule
skills/run-autopilot/cli/
├── verification.py                              # normalize_command, _write_record
└── test_verification.py                         # tests: shell spellings are distinct
skills/work/references/
└── final-verification.md                        # stored command is the raw command
```

## Dependency Graph

### Foundation Layer (Phase 0)
- **verification**: normalize_command.
- **review SKILL step 6**: independent.

### Integration Layer (Phase 1)
- **final-verification.md, CHANGELOG**: depend on [verification].

## Implementation Phases

### Phase 0: Foundation
**Tasks**:
- [ ] verification: whitespace-only `normalize_command`; raw command stored. Premise: PRD 00270's `test_reuse_matches_a_command_spelled_with_bash_dot_slash_and_extra_spaces` asserts the old stripping; re-check with `rg -n "bash_dot_slash" skills/run-autopilot/cli/test_verification.py`, and change only that test's expectation to `stale` for the `bash ./` spelling while keeping its extra-spaces case `reused`; report the change (no deps) - Acceptance: in `test_verification.py`, `sh_and_bash_records_do_not_cross_reuse` and `dot_slash_and_bare_records_do_not_cross_reuse` pass and fail at base; `test_reuse_is_stale_when_the_gate_command_differs` still passes.
- [ ] review SKILL step 6: compose from `gate.tests_line`, drop the sha/counts rule; add `skills/review-work-completion/scripts/test_tests_line_source_prose.py` and register it in `dev/bin/release-checks` (no deps) - Acceptance: `test_step_6_composes_from_gate_tests_line` and `test_step_6_has_no_sha_counts_reuse_rule` pass and fail at base.

**Exit Criteria**: `uv run --no-project --with pytest python -m pytest -q skills/run-autopilot/cli/test_verification.py skills/review-work-completion/scripts/test_tests_line_source_prose.py` exits 0.

### Phase 1: Integration
**Tasks**:
- [ ] prose: `final-verification.md` stored command is "the command exactly as run, whitespace collapsed"; CHANGELOG line 41 corrected, plus an `[Unreleased] ### Changed` line that `bash X`/`sh X`/`./X`/`X` no longer share a record (depends on: Phase 0) - Acceptance: `rg -n "different whitespace" CHANGELOG.md` still hits only where it is true, and `rg -n "sh X|\./X" CHANGELOG.md` hits inside `[Unreleased]`.

**Exit Criteria**: `bash dev/bin/release-checks` exits 0 with `FAIL 0` on its summary line.

## Test Strategy

### Critical Scenarios

Reproductions from the report, verbatim:

```
8: Peggy (batch transcripts): 00270-c1 review-stage `"verdict": "reused"` at `1d02d5b`, then the
   session ran `verify` anyway (221.7 s). `1d02d5b..07fa37c` holds only store commits. Same in
   c2: 219.1 s. Wendy (fixture): a subset command recorded green, plus a dirty product edit. The
   SKILL rule gives `True` (reuse) while `reuse_verdict` gives `stale`.
9: Non-executable `gate.sh`: `verify "bash ./gate.sh"` records green. `review-stage "./gate.sh"`
   and `"gate.sh"` give `reused`, while running them directly gives exit 126 and 127.
   `sh shdep.sh` recorded green is reused for `bash shdep.sh`, which fails in a clean clone
   (`failed: 1`).
```

## Risks

- **Prose-only enforcement** (packet 8): step 6 still relies on the model following the SKILL text; the new prose test pins the wording.
- **Spelling drift reruns** (packet 9): `bash dev/bin/release-checks` vs `dev/bin/release-checks` now forces a full rerun (~220 s), the cost PRD 00270 packet 10 removed. Accepted by the operator.
- Source: `docs/dev/project-management/audit-results/agoge-2026-10-10.md` (2026-10-10).
