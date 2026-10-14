---
design: skip
default_model: sonnet
model_tier_rationale: one prerequisite line, one CHANGELOG entry and one comment; no behaviour change
---

# The pack needs Python 3.11 and does not say so; the findings cross-check has an unstated ceiling

## Overview

### Problem Statement

The agoge run of 2026-10-10 (`docs/dev/project-management/audit-results/agoge-2026-10-10.md`,
packets 11 and 20; decisions in its `## Minutes`):

- **11 (MEDIUM):** `skills/run-autopilot/cli/__main__.py:256` imports `datetime.UTC`
  (Python 3.11+), so on 3.10 every verb fails with `ImportError: cannot import name
  'UTC' from 'datetime'`. v0.9.0 ran on 3.10. `skills/run-autopilot/SKILL.md:46` lists
  bare `python3`, and nothing names a minimum. The operator chose to **declare 3.11
  as the floor** instead of restoring 3.10 support, which makes hold stub 00272
  (`timezone.utc` fix) obsolete.
- **20 (LOW):** `gate._backed` scans every reviewed row per finding (N(N+1)/2 rows:
  0.30 s at 5,000 rows, 26 s at 50,000). Real reviews carry dozens. No ceiling is stated.

If unchanged: 3.10 users upgrade into a crash with no warning in the docs, and the
cross-check's limit is undocumented.

### Target Users

Operators installing the pack, and whoever later scales review files.

### Success Metrics

- `skills/run-autopilot/SKILL.md` names Python `>=3.11`.
- `[Unreleased] ### Changed` says the minimum Python is now 3.11.
- `gate._backed` carries a `ponytail:` ceiling comment naming the quadratic limit and the upgrade path.

## Functional Decomposition

### Capability: Stated contracts

#### Feature: Python floor (packet 11)
- `SKILL.md:46` reads `python3` (>= 3.11). CHANGELOG `[Unreleased] ### Changed`: `**run-autopilot**: the CLI now needs Python 3.11 or newer (it uses datetime.UTC); 3.10 is no longer supported`.

#### Feature: Ceiling comment (packet 20)
- A `# ponytail:` comment above `_backed`: quadratic in reviewed rows, fine at real sizes (dozens), index rows by ref and by (severity, file, issue) if reviews ever reach thousands.

## Structural Decomposition

### Repository Structure

```
CHANGELOG.md                         # [Unreleased] Changed: Python 3.11 floor
skills/run-autopilot/
├── SKILL.md                         # line 46: python3 (>= 3.11)
└── cli/
    └── gate.py                      # ponytail ceiling comment on _backed
```

## Dependency Graph

### Foundation Layer (Phase 0)
- All three edits are independent.

## Implementation Phases

### Phase 0: Foundation
**Tasks**:
- [ ] SKILL.md and CHANGELOG state the 3.11 floor (no deps) - Acceptance: `rg -n "3\.11" skills/run-autopilot/SKILL.md` hits on the CLIs prerequisite line, and `rg -n "Python 3\.11" CHANGELOG.md` hits inside `[Unreleased]`; docs-only, no behaviour to test.
- [ ] gate: ponytail ceiling comment on `_backed` (no deps) - Acceptance: `rg -n "ponytail:.*quadratic" skills/run-autopilot/cli/gate.py` prints one line while `rg -n "def _backed" skills/run-autopilot/cli/gate.py` hits (control); comment-only.

**Exit Criteria**: `bash dev/bin/release-checks` exits 0 with `FAIL 0` on its summary line.

## Test Strategy

### Critical Scenarios

Reproductions from the report, verbatim:

```
11: HEAD `uv run --python 3.10 python -m cli --help` gives `ImportError: cannot import name 'UTC'
    from 'datetime'`. A v0.9.0 worktree prints usage.
20: Rows scanned: 125,250 / 12,502,500 / 1,250,025,000 at 500 / 5,000 / 50,000 rows (N(N+1)/2).
    Wall time: 0.30 s at 5,000 rows, 26 s at 50,000.
```

No new test: both changes are documentation. A 3.10 import smoke test was offered and not chosen.

## Risks

- **Drops 3.10 users**: accepted by the operator (packet 11 option 2).
- Source: `docs/dev/project-management/audit-results/agoge-2026-10-10.md` (2026-10-10).

## Closed 2026-10-14

Merged into PRD 00278 at the backlog review of 2026-10-12 and left in `hold/` without a note. Its acceptance already holds at HEAD: `skills/run-autopilot/SKILL.md` names `python3 (>= 3.11)`, CHANGELOG line 21 states the floor, and the `ponytail:` quadratic comment sits above `_backed` in `skills/run-autopilot/cli/gate.py` (commit 6c91048). Moved to `done/` rather than deleted, so no finalize re-mints it (agoge-2026-10-14 packet 30).
