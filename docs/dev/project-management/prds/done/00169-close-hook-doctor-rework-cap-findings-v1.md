---
catchup: skip
design: skip
---

# Close the hook doctor rework-cap findings

Source: PRD 00161's review cycle 2 hit the rework cap with eight findings unresolved (`dev/local/autopilot/deferred/202609011951-deferred.json`, `dev/local/reviews/00161-doctor-codex-host-hooks-v1-review-2.md`). Two are confirmed HIGH defects in `skills/use-codex/scripts/codex_hook_doctor.py`; the rest are one medium correctness gap, one misdocumented exit code, and four test-quality items. Filed 2026-09-02 by the operator walkthrough.

## Overview

### Problem Statement

`codex_hook_doctor.py` gates the codex rung on every batch. Two of its verdicts are wrong in ways that either leave a broken host unrepaired or gate the rung off on a healthy one:

1. `_repair_known` (line 171) accepts only `missing`, `empty`, `stale`, `no_canonical`. A KNOWN hook that fails to compile verdicts `syntax_error`, so `repair` returns `None` for it: no TSV row, no rewrite from canonical, and the rung stays gated on the exact state `check` was tightened to catch. `_repair_unknown` (line 155) does report `syntax_error`, so only the repairable case is silent. Introduced by cycle 1's verdict-ordering fix.
2. `_verdict_for` (line 66) runs `compile(target.read_text(encoding="utf-8"), ...)`. A valid hook carrying a PEP 263 coding cookie in another encoding raises `UnicodeDecodeError` before compiling and is verdicted `syntax_error` (exit 1, rung gated off). The PRD 00161 contract is "fails to compile", which `compile()` on bytes honours.

Alongside: `_missing_common_import_names` (line 139) catches only `SyntaxError` on the canonical `_common.py` read, so a non-UTF-8 or unreadable canonical aborts the whole `repair` run with exit 2 and no TSV output for any target; the sibling loop a few lines up already handles both. Exit 2 is documented as "config unreadable" (`state-schema.md:198`, `codex-implementor.md:78`) but `main` returns 2 for every resolution failure: malformed event entries, `shlex` tokenization, a manifest without the aegis entry, target I/O. The state then records a config problem for a manifest problem.

### Target Users

The operator, whose `~/.codex/hooks.json` the doctor repairs, and the batch codex health probe, which trusts the doctor's exit code to decide whether codex may implement.

### Success Metrics

- A known hook with a syntax error gets a `repaired` row (canonical present) or an `unrepairable` row (canonical absent) and the rung comes back on after repair.
- A hook with a valid non-UTF-8 coding cookie verdicts `ok`; a hook with a real syntax error still verdicts `syntax_error`.
- A non-UTF-8 or unreadable canonical `_common.py` makes that one target `unrepairable`; every other target still gets its row and its repair.
- `hook_doctor` on doctor exit 2 records a value that is true for every exit-2 cause.

## Functional Decomposition

### Capability: Doctor verdicts
Both HIGHs and the canonical-read gap, in `codex_hook_doctor.py`.

#### Feature: Known syntax-broken hooks are repaired
- **Inputs**: a target whose basename is in `KNOWN_HOOKS` and whose verdict is `syntax_error`.
- **Outputs**: `("repaired", target, canonical)` when the canonical exists, `("would-repair", ...)` under `--dry-run`, `("unrepairable", target, "no canonical source (...)")` otherwise.
- **Behavior**: add `"syntax_error"` to the verdict tuple in `_repair_known`. The symlink skip, the `_common.py` import scan and the tmp-then-`os.replace` write apply unchanged.

#### Feature: Compile honours the coding cookie
- **Inputs**: any target that exists and is non-empty.
- **Outputs**: `syntax_error` only when `compile()` rejects the bytes.
- **Behavior**: `compile(target.read_bytes(), str(target), "exec")`. Catch `(SyntaxError, ValueError)`: `compile()` on bytes raises `SyntaxError` for an unknown or mis-declared encoding and `ValueError` for null bytes on 3.10 and 3.11. Drop `UnicodeDecodeError` from the tuple only if no path can raise it anymore; keep the read-only property (no bytecode written).

#### Feature: Canonical read failures degrade per target
- **Inputs**: a canonical `_common.py` that is non-UTF-8 or unreadable.
- **Outputs**: the `_common.py` target verdicts `unrepairable` with `"<name>: unreadable (cannot verify _common imports)"`; siblings unaffected.
- **Behavior**: the canonical read at line 139 catches `(UnicodeDecodeError, OSError)` the way the sibling loop at line 129 does, appends the same unreadable marker and returns. No exit 2 from this path.

### Capability: Exit 2 telemetry
One literal and two documents.

#### Feature: Exit 2 means the doctor could not run
- **Inputs**: doctor exit 2 in the batch codex health probe.
- **Outputs**: `codex_probe.hook_doctor: "doctor error: <config path>"`, `detail: "hook_doctor: <the doctor's stderr error line>"` (unchanged).
- **Behavior**: replace the `"config unreadable: <config path>"` literal in `work/references/codex-implementor.md` § Codex batch health probe and the `codex_probe` row of `run-autopilot/references/state-schema.md`, and state the cause list: config missing, unreadable, not JSON or without a `hooks` object; a malformed event entry; a command that does not tokenize; a manifest without `aegis@buvis-plugins`; a target I/O failure. The stderr line names which. The two prose pins in `test_codex_hook_doctor_extra.py` (lines 446 and 519) follow the literal. Readers ignore `hook_doctor` content beyond display, so no state migration.

### Capability: Test quality
Four cap-overflow items, all in `skills/use-codex/scripts/`.

- **Sibling refusal test binds to intent**: `test_repair_tolerates_a_non_utf8_sibling_py_file_while_scanning_common_py_imports` (`test_codex_hook_doctor_repair.py:646`) asserts exit 1, an `unrepairable` `_common.py` row and byte-identical `_common.py` before and after; today any non-error exit passes.
- **`_snapshot` proves bytes, not sizes**: `test_codex_hook_doctor.py:68` records `sha256(read_bytes())` for files (directories stay `-1`) so a same-size rewrite fails the read-only proofs.
- **`_load_hooks(config)`**: `repair` parses `hooks.json` with the identical expression at lines 278 and 297; one helper, both call sites keep their own call so the deliberate re-read before cleanup stays.
- **Stale `py_compile` commentary**: the comments at `test_codex_hook_doctor_extra.py:207` and `:281` and `test_codex_hook_doctor.py:149` describe `py_compile`'s multi-line message; the implementation uses `compile()` and its one-line `str(exc)`. Replace with the actual contract in one sentence each.

## Structural Decomposition

### Repository Structure

```
skills/use-codex/scripts/
├── codex_hook_doctor.py                     # Maps to: Doctor verdicts, _load_hooks
├── test_codex_hook_doctor.py                # Maps to: _snapshot, compile contract comment
├── test_codex_hook_doctor_extra.py          # Maps to: exit-2 prose pins, stale comments
└── test_codex_hook_doctor_repair.py         # Maps to: syntax_error repair, canonical read, sibling refusal
skills/work/references/codex-implementor.md  # Maps to: Exit 2 telemetry
skills/run-autopilot/references/state-schema.md
CHANGELOG.md
```

## Dependency Graph

### Foundation Layer (Phase 0)
- **doctor-verdicts**: `codex_hook_doctor.py` and its regression tests. No dependencies.

### Core Layer (Phase 1)
- **exit-2-telemetry**: prose, schema row, the two pins. Depends on nothing in code; sequenced after Phase 0 so one suite run covers both.

### Integration Layer (Phase 2)
- **test-quality**: the four test items and the changelog. Depends on [doctor-verdicts] (the sibling test asserts the new unreadable path).

## Implementation Phases

### Phase 0: Doctor verdicts
**Goal**: the two HIGHs and the canonical-read gap are fixed with fail-first regression tests.

**Tasks**:
- [ ] In `codex_hook_doctor.py`: add `"syntax_error"` to `_repair_known`'s verdict tuple; compile `target.read_bytes()` in `_verdict_for` with the except tuple widened per the feature; catch `(UnicodeDecodeError, OSError)` on the canonical read in `_missing_common_import_names`. Tests in `test_codex_hook_doctor_repair.py`, each watched failing against the old code first: a known hook with `def (:` and a canonical present → `repaired` row and the file matches canonical; same with the canonical absent → `unrepairable`; under `--dry-run` → `would-repair`. In `test_codex_hook_doctor.py`: a hook `# -*- coding: latin-1 -*-\nX = "\xe9"\n` written as latin-1 bytes → `ok`; the same bytes without the cookie → `syntax_error`; a hook containing a null byte → `syntax_error`. In `test_codex_hook_doctor_repair.py`: a latin-1 canonical `_common.py` → `_common.py` row `unrepairable` with the unreadable marker, a stale sibling in the same run still `repaired`, exit 1 (no deps) - Acceptance: `uv run --no-project --with pytest python -m pytest -q skills/use-codex/scripts` green; `rg -n 'read_text\(encoding="utf-8"\), str\(target\)' skills/use-codex/scripts/codex_hook_doctor.py` has no hit.

**Exit Criteria**: suite green; `python3 skills/use-codex/scripts/codex_hook_doctor.py check --config <fixture>` on a latin-1 hook exits 0.

### Phase 1: Exit 2 telemetry
**Goal**: the exit-2 value is true for every exit-2 cause.

**Tasks**:
- [ ] Replace `"config unreadable: <config path>"` with `"doctor error: <config path>"` in `skills/work/references/codex-implementor.md` § Codex batch health probe and in the `codex_probe` row of `skills/run-autopilot/references/state-schema.md`; state the cause list in both; update the two pins at `test_codex_hook_doctor_extra.py:446` and `:519` (depends on: Phase 0) - Acceptance: `rg -n "config unreadable" skills` has no hit; `rg -n "doctor error: <config path>" skills/work/references/codex-implementor.md skills/run-autopilot/references/state-schema.md` hits both; `uv run --no-project --with pytest python -m pytest -q skills/use-codex/scripts` green.

**Exit Criteria**: pins green.

### Phase 2: Test quality and release
**Goal**: the four test items land and the change is changelogged.

**Tasks**:
- [ ] Tighten `test_repair_tolerates_a_non_utf8_sibling_py_file_while_scanning_common_py_imports` (exit 1, `unrepairable` `_common.py` row, `_common.py` bytes unchanged); make `_snapshot` hash file bytes; extract `_load_hooks(config)` in `codex_hook_doctor.py` with both call sites kept; replace the three `py_compile` comments with the `compile()` one-line contract; add the CHANGELOG entry (`fix(use-codex)`: `**use-codex**` under Fixed: the hook doctor repairs a known hook that fails to compile, accepts hooks with a non-UTF-8 coding cookie, reports an unreadable canonical `_common.py` as unrepairable instead of aborting, and records `doctor error:` on exit 2) (depends on: Phase 1) - Acceptance: `rg -n "py_compile" skills/use-codex/scripts` has no hit; `rg -n "^- \*\*use-codex\*\*" CHANGELOG.md` hits under `[Unreleased]`; `uv run --no-project --with pytest --with rich --with textual python -m pytest -q skills/use-codex/scripts skills/work/scripts skills/run-autopilot` green; `bash dev/bin/release-checks` green.

**Exit Criteria**: full suite and release checks green.

## Test Strategy

### Critical Scenarios
- **Happy path**: known hook with a syntax error, canonical present → `repaired`, post-repair `check` exits 0.
- **Edge case**: latin-1 hook with a coding cookie → `ok`; without the cookie → `syntax_error`.
- **Edge case**: latin-1 canonical `_common.py` → only `_common.py` unrepairable, siblings repaired, exit 1 not 2.
- **Error case**: manifest without the aegis entry → exit 2, stderr `error: 'aegis@buvis-plugins'`, and the documented `hook_doctor` value is `doctor error: <config path>`.

## Risks

- **Widening `_repair_known` rewrites a hook the operator edited by hand**: only hooks in `KNOWN_HOOKS` qualify, and a hand-edited known hook that still compiles verdicts `stale`, which was already repaired. A known hook that does not compile has no working state to preserve.
- **Bytes `compile()` behaviour differs across 3.10-3.13**: the null-byte case raises `ValueError` on 3.10/3.11 and `SyntaxError` on 3.12+; the except tuple names both, the test asserts the verdict, not the exception.
- **A reader of `hook_doctor` matches the old literal**: `rg "config unreadable"` across `skills/` is part of Phase 1's acceptance; no script parses the value today.
