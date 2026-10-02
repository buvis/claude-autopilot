---
catchup: skip
design: skip
---

# Guard the canonical read in the doctor verdict

Source: three KNOWN items from PRD 00169's review cycle 1 (Eve, `dev/local/reviews/00169-review.md`), each judged out of 00169's scope because the PRD pinned its fix to one line. Filed 2026-09-02 by the 00169 session.

## Overview

### Problem Statement

`skills/use-codex/scripts/codex_hook_doctor.py` still has three paths where a broken file on the host or in the plugin cache aborts the whole run with exit 2 and no TSV rows, or reports a misleading detail:

1. `_verdict_for` reads the canonical with `canonical.read_bytes()` unguarded, after `canonical.exists()` passed. A canonical that is a directory or unreadable (permission denied) behind a known target that compiles raises `OSError` out of `check()`: exit 2, no rows. PRD 00169 guarded only the later read in `_missing_common_import_names`, so "an unreadable canonical makes that one target unrepairable" holds only for missing, empty or syntax-broken targets. Confirmed live: `error: [Errno 21] Is a directory: .../aegis/hooks/_common.py`, exit 2.
2. `_missing_common_import_names` catches `SyntaxError` and `(UnicodeDecodeError, OSError)` around `ast.parse`, but on Python 3.10 and 3.11 a null byte makes `ast.parse` raise a bare `ValueError`, which neither tuple catches: exit 2 from a sibling or canonical `_common.py` with a null byte. On 3.12 and later the same input raises `SyntaxError` and is caught. `UnicodeDecodeError` is a `ValueError` subclass, so widening the second tuple to `(ValueError, OSError)` is a superset.
3. The unrepairable detail for an unreadable or unparseable canonical reads `sibling imports names not defined in canonical _common.py: _common.py: unreadable (cannot verify _common imports)`. The prefix is false when the only entry is the canonical's own marker; the prefix predates 00169 (cycle 1 of PRD 00161 added the SyntaxError marker under it).

### Target Users

The operator running `repair` against a damaged plugin cache, and the batch codex health probe reading the doctor's exit code.

### Success Metrics

- A known target that compiles, whose canonical is a directory or unreadable, gets one row and the run exits 1 or 3, never 2.
- A null byte in a sibling or the canonical `_common.py` yields the unreadable marker on every supported Python, never exit 2.
- The detail for a canonical-only failure names the canonical failure without the sibling-imports prefix.

## Functional Decomposition

### Capability: Doctor verdicts

#### Feature: An unreadable canonical verdicts the target, not the run
- **Description**: a canonical that exists but cannot be read verdicts that one target `no_canonical` instead of aborting the run.
- **Inputs**: a known target whose canonical exists but `read_bytes()` raises `OSError`.
- **Outputs**: verdict `no_canonical` with an empty detail from `check` (exit 3 through `_report`'s existing count); from `repair`, `unrepairable` with detail `no canonical source (<path>)`.
- **Behavior**: catch `OSError` around the canonical read in `_verdict_for` and return `no_canonical`; in `_repair_known`, read the canonical once inside the same guard, placed before the `dry_run` branch, so `--dry-run` reports `unrepairable` (never `would-repair`) and the write path cannot raise where `check` did not. No new verdict string; `_report` and `use-codex/SKILL.md` are unchanged.

#### Feature: Null bytes degrade like undecodable bytes
- **Description**: a null byte in any `_common.py` read by `_missing_common_import_names` yields the unreadable marker on every supported Python.
- **Inputs**: a sibling or canonical `_common.py` whose bytes make `ast.parse` raise `ValueError` (3.10, 3.11) or `SyntaxError` (3.12 and later).
- **Outputs**: the `unreadable` or `SyntaxError` marker for that file; never exit 2.
- **Behavior**: widen the second except tuple in both `_missing_common_import_names` reads to `(ValueError, OSError)`; a test with a null-byte sibling asserts the unreadable-or-SyntaxError marker and no exit 2 (the branch taken depends on the interpreter, the verdict does not).

#### Feature: Canonical-only detail
- **Description**: a repair that fails only because the canonical is unreadable or unparseable says so without the sibling-imports prefix.
- **Inputs**: `_missing_common_import_names` returning exactly one entry, the canonical's own marker.
- **Outputs**: `unrepairable` with that marker as the whole detail.
- **Behavior**: when `_missing_common_import_names` returns only the canonical's own marker, `_repair_known` emits that marker as the detail without the `sibling imports names not defined` prefix; existing tests assert the marker with `in`, so they keep passing.

## Structural Decomposition

### Repository Structure

```
skills/use-codex/scripts/codex_hook_doctor.py          # Maps to: all three features
skills/use-codex/scripts/test_codex_hook_doctor_extra.py  # Maps to: regression tests (the repair test file is at the 800-line limit)
CHANGELOG.md
```

### Module: hook-doctor
- **Maps to capability**: Doctor verdicts
- **Responsibility**: the guarded canonical reads, the widened except tuples and the canonical-only detail in `codex_hook_doctor.py`; one fail-first test per feature in `test_codex_hook_doctor_extra.py`.
- **Exports**: none new (`_verdict_for`, `_missing_common_import_names`, `_repair_known` keep their signatures)

## Dependency Graph

### Foundation Layer (Phase 0)
No dependencies - built first.

- **hook-doctor**: the guarded reads.

## Implementation Phases

### Phase 0: Guard the reads
**Goal**: no host or cache file can abort the doctor with exit 2.

**Tasks**:
- [x] Guard `_verdict_for` and `_repair_known`'s canonical reads (verdict `no_canonical`; repair detail `no canonical source (<path>)`; the guard sits before the `dry_run` branch), widen the `ast.parse` except tuples, drop the sibling prefix for canonical-only failures; one fail-first test per feature in `test_codex_hook_doctor_extra.py`, the first using a directory as the canonical behind a compiling known target and asserting `check` exits 3 and `repair` exits 1 or 3, never 2; CHANGELOG `**use-codex**` under Fixed (no deps) - Acceptance: `uv run --no-project --with pytest python -m pytest -q skills/use-codex/scripts` green with the three new tests present.

**Exit Criteria**: suite green; `bash dev/bin/release-checks` green.

## Test Strategy

### Critical Scenarios
- **Happy path**: a stale known target with a readable canonical → Expected: `repaired`, unchanged from today.
- **Edge case**: the canonical is a directory behind a compiling known target → Expected: one `no_canonical` row, `check` exits 3, `repair` reports `unrepairable`, never exit 2.
- **Error case**: a null byte in a sibling `_common.py` → Expected: the unreadable or SyntaxError marker, never exit 2, on every supported Python.

## Risks

- Reusing `no_canonical` keeps `_report`'s counting, `use-codex/SKILL.md`'s exit-code list and the two prose pins untouched; the detail line carries the real cause.
- The test file for `repair` is at 795 lines; new tests go in `test_codex_hook_doctor_extra.py`.
