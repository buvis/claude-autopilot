---
design: skip
---

# Fix style-gate blindness to new files

## Overview

### Problem Statement

The step-7.0 style-limit gate certifies files it never opened. Two independent
holes produce the same wrong answer, `style_gate: clean`:

1. **The enumeration cannot see uncommitted files.** `skills/work/SKILL.md`
   step 7.0 lists candidates with
   `git diff --name-only --diff-filter=d <base>..HEAD -- '*.py'`. A new module
   that exists on disk but is not in a commit is absent from that output, so it
   is never passed to the gate.
2. **The gate silently drops a file it cannot place in the diff.**
   `skills/work/scripts/check_style_limits.py:159-161` — `_resolve_diff_path`
   returns `None` when no `+++ b/` header matches, and the loop `continue`s. The
   path is not recorded in `skipped`, so the incomplete-gate exit-2 branch
   (lines 211-222) never fires and the run exits 0.

Measured cost (batch feedback 2026-08-27): eight oversized functions in new test
modules passed a clean gate, then surfaced in per-task review — costing another
commit, another de-slop pass, and another reviewer dispatch.

The `skipped` list and its exit-2 branch were built for exactly this failure
class. Untracked files fall outside them.

### Target Users

The autopilot loop itself, and the operator reading `style_gate:` in a phase
report. Today that line can read `clean` over a file the gate never opened.

### Success Metrics

- A phase whose only Python change is an uncommitted new module holding a
  60-line function exits 1 and prints a `FUNCTION | ... | 60 lines` line.
- A positional file with no `+++ b/` match in the diff exits 2 with the
  gate-incomplete stderr message, never 0.
- `skills/work/scripts/test_check_style_limits.py` and
  `test_check_style_limits_prd00136.py` stay green — no existing behavior on
  tracked, diff-present files changes.
- No new flag on `check_style_limits.py`: the untracked fix is entirely in how
  the caller builds the diff file.

## Functional Decomposition

### Capability: Untracked-file diff coverage

Make an uncommitted new Python file appear in the phase diff as a wholly added
file, using git itself rather than a new gate mode.

#### Feature: Untracked append to the phase diff
- **Description**: The step-7.0 diff file gains a full-add hunk for every
  untracked Python file in the worktree.
- **Inputs**: `git ls-files --others --exclude-standard -- '*.py'` run from the
  repo root (with the repo's own `--git-dir`/`--work-tree` flags in a bare-repo
  home, as step 7.0 already requires).
- **Outputs**: `dev/local/tmp/phase-diff.txt` — the committed-range diff
  followed by one `git diff --no-index -- /dev/null <path>` block per untracked
  path; the extended candidate list passed as positional arguments.
- **Behavior**: `git diff --no-index -- /dev/null <path>` emits
  `+++ b/<path>` and a single `@@ -0,0 +1,N @@` hunk covering the whole file
  (verified against git in this repo's environment), which is exactly the shape
  `touched_ranges` already parses — so every function in the file intersects a
  touched range and the file-limit arithmetic
  (`n - ins + dels <= file_limit`, line 186) reduces to `0 <= 800`, flagging any
  file over the limit. `--no-index` **exits 1 when it finds differences**, which
  is the normal case here and must not be read as a command failure; only exit
  ≥2 is an error. Zero untracked Python files appends nothing and changes the
  diff byte-for-byte.

#### Feature: Unresolvable candidate is a skip, not silence
- **Description**: A positional file the gate cannot locate in the diff is
  recorded as not-inspected instead of quietly passed over.
- **Inputs**: the positional path list and the parsed diff.
- **Outputs**: the path appended to `skipped`; the existing gate-incomplete
  stderr line and exit 2.
- **Behavior**: In `violations()`, the `diff_path is None` branch appends the
  path to `skipped` before `continue`. The ambiguous-tie branch inside
  `_resolve_diff_path` is unchanged (it already records a skip); only the
  no-match return path changes. The docstring's current defence — that no match
  means "the file is not in this diff, which is an ordinary answer" — is
  rewritten: every caller in this pack passes only files it derived from the
  diff, so a no-match is a caller/gate disagreement and must fail loud.

## Structural Decomposition

### Repository Structure

```
skills/work/
├── scripts/
│   ├── check_style_limits.py          # Maps to: Unresolvable candidate is a skip
│   └── test_check_style_limits.py     # Tests for both features
└── SKILL.md                           # Maps to: Untracked append to the phase diff
```

### Module: style-gate
- **Maps to capability**: Untracked-file diff coverage
- **Responsibility**: report only violations the diff introduced, and never
  report clean over a file it did not inspect.
- **Exports**:
  - `violations(diff_text, paths, function_limit, file_limit, skipped)` -
    unchanged signature; a no-match path now lands in `skipped`.

### Module: work-prose
- **Maps to capability**: Untracked-file diff coverage
- **Responsibility**: step 7.0's diff construction and candidate enumeration.
- **Exports**: none (prose)

## Dependency Graph

### Foundation Layer (Phase 0)
No dependencies - built first.

- **style-gate**: the `skipped` recording and its test.

### Core Layer (Phase 1)
- **work-prose**: Depends on [style-gate] - the prose describes the exit-2
  branch the gate now reaches.

### Integration Layer (Phase 2)
No integration module - this PRD ships two files.

## Implementation Phases

### Phase 0: Foundation
**Goal**: The gate refuses to certify a file it could not place in the diff.

**Tasks**:
- [ ] In `skills/work/scripts/check_style_limits.py`, append `path` to `skipped`
      in the `diff_path is None` branch of `violations()`, and rewrite the
      `_resolve_diff_path` docstring paragraph that calls no-match "an ordinary
      answer" to state the caller contract instead (no deps) - Acceptance:
      `uv run --no-project --with pytest python -m pytest -q skills/work/scripts/test_check_style_limits.py skills/work/scripts/test_check_style_limits_prd00136.py`
      green.
- [ ] Add tests to `test_check_style_limits.py`: a positional file absent from
      the diff exits 2 and names the file in stderr; a diff carrying a
      `--no-index` full-add block for a 900-line file yields a
      `FILE | ... | 900 lines` line and exit 1; a 60-line function inside such a
      block yields a `FUNCTION` line; a pure-deletion hunk on a present file
      still yields no violation and exit 0 (no deps) - Acceptance: the same
      pytest command green with the four new tests present.

**Exit Criteria**: `python3 skills/work/scripts/check_style_limits.py --diff <a diff naming only a.py> b.py` exits 2.

### Phase 1: Core
**Goal**: Step 7.0 builds a diff that contains the untracked files.

**Tasks**:
- [ ] Edit `skills/work/SKILL.md` step 7.0: after writing `phase-diff.txt` from
      the committed range, list untracked Python files with
      `git ls-files --others --exclude-standard -- '*.py'` and append a
      `git diff --no-index -- /dev/null <path>` block per path to the same file;
      state that `--no-index` exits 1 on differences and that only exit ≥2 is a
      failure; add those paths to the positional candidate list. Keep the
      no-`.py`-change short circuit (`style_gate: clean`) but base it on the
      combined list (depends on: Phase 0) - Acceptance:
      `rg -n "ls-files --others|--no-index" skills/work/SKILL.md` hits both;
      `uv run --no-project --with pytest python -m pytest -q skills/work/scripts/test_dispatch_prose.py`
      green, its SKILL.md line-ceiling test included.
- [ ] Add a prose pin to `skills/work/scripts/test_dispatch_prose.py` asserting
      step 7.0 names `ls-files --others` and `--no-index`, and add the CHANGELOG
      entry (`fix` commit: `**work**` under Fixed, "style-limit gate no longer
      reports clean over uncommitted or unmatched Python files") (depends on:
      Phase 1 task 1) - Acceptance: the prose test is green and
      `rg -n "style-limit gate" CHANGELOG.md` hits under `[Unreleased]`.

**Exit Criteria**: A worktree holding one uncommitted 60-line-function test module makes step 7.0 record a non-clean `style_gate`.

## Test Strategy

### Critical Scenarios
- **Happy path**: committed range plus one untracked `test_big.py` with a
  60-line function → exit 1, one `FUNCTION` line naming it.
- **Edge case**: no untracked Python files → the diff file and the exit code are
  byte-identical to today's.
- **Edge case**: an untracked file under 800 lines with no long function → exit
  0, `style_gate: clean`, and the clean verdict is now earned.
- **Error case**: a candidate path that matches no diff header → exit 2,
  `gate incomplete, 1 changed file(s) not inspected`, and step 7.0 records
  `style_gate: failed:<stderr>` and dispatches no fixer (its existing exit-2
  branch, unchanged).

## Risks

- **A previously-clean phase now exits 2 on a path-shape mismatch.** The
  trailing-segment matcher (`_match_depth`) already tolerates absolute vs
  repo-relative paths, and the exit-2 branch is non-blocking by design: step 7.0
  records `style_gate: failed:<stderr>`, skips the fixer, and runs the suite
  anyway. The failure is loud and costs no cycle.
- **`--no-index` on a large untracked file inflates the diff.** It is bounded by
  the file itself, the gate reads the file from disk regardless, and the diff
  file is not a dispatch prompt.
- **PRD 00163 relocates this gate to the task boundary.** Both changes here are
  in the gate script and in how a caller builds its diff, so they travel with
  the call site unchanged. Land this first; 00163 reuses it.
