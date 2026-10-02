Read /Users/bob/git/src/github.com/buvis/claude-autopilot/dev/local/tmp/review-context-00176-01.md for review context, and /Users/bob/git/src/github.com/buvis/claude-autopilot/dev/local/tmp/review-diff-00176-01.diff for the full diff.

Read (no pack available this cycle) and treat its full content as prepended context: similar code, reuse precedent, findings precedent, and task prose for this diff's changed symbols.

Use this review checklist:
# Review Dimensions

Detailed checklist for reviewing completed work.

## Plan Compliance

- [ ] Implementation matches task description
- [ ] All acceptance criteria met
- [ ] No scope creep (extra features not requested)
- [ ] No missing pieces from original task

## PRD Coverage

- [ ] All "must have" requirements addressed
- [ ] Success metrics achievable with implementation
- [ ] No PRD sections left unimplemented
- [ ] Dependencies correctly handled

## Simplification

Hunt actively for simplification — do not just tick boxes. The diff under
review is fresh; this is the cheapest moment to cut complexity before it sets.
For every added or changed file, ask "what would make this simpler to read
without changing what it does?" and flag concrete opportunities.

- [ ] **Reduce complexity** — no needless indirection, dead branches, or
      abstractions built for a single caller; nesting <= 4 levels; functions
      under 50 lines
- [ ] **Eliminate redundancy** — no logic duplicated within the diff or against
      existing code; no helper that reimplements a stdlib or existing utility
- [ ] **Improve naming** — names state intent; no opaque abbreviations;
      action-named functions start with a verb
- [ ] **Follow project standards** — conventions from CLAUDE.md / AGENTS.md and
      the surrounding code; no style drift
- [ ] **No dead code** — no commented-out blocks, unused imports, variables, or
      speculatively-added parameters
- [ ] **Appropriate error handling** — explicit, never silently swallowed

**How to flag a simplification:** give the file:line, the current shape, and
the simpler replacement. Flag concrete behavior-preserving simplifications at
🟡 Medium so the decision gate routes them into the rework loop. Do not inflate
them to 🟠 High; that floods the rework loop and can trip the scope alarm.

**Balance — do not over-simplify:** never propose a change that trades clarity
for brevity, drops error handling, collapses a deliberate boundary, or removes
a documented invariant. Simpler means easier to read and maintain, not shorter
at any cost. If a "simplification" would change behavior, it is out of scope —
do not flag it.

## Testing

- [ ] Unit tests for new logic
- [ ] Edge cases covered
- [ ] Error paths tested
- [ ] Integration tests if crossing boundaries
- [ ] Tests actually run and pass
- [ ] No tautological test — every new or changed test fails against the
      pre-change code (the context's fail-first replay block), and no assert
      is constant, self-comparing, or an either-or hedge (the shapes block)

## Security

- [ ] No hardcoded secrets
- [ ] Input validation at boundaries
- [ ] No SQL/command injection risks
- [ ] Auth/authz correctly applied
- [ ] Sensitive data not logged

## Documentation

- [ ] Public APIs documented
- [ ] Complex logic has comments
- [ ] README updated if needed
- [ ] Breaking changes noted


In addition, work through the numbered rubric:
# Review-Work-Completion Rubric

This rubric defines binary pass/fail criteria for consensus review of completed work. Each rule is numbered and stable for tracking coverage. Reviewers must answer "R{n}: pass|fail" for every rule in their prompt.

## Rules

### Tests

R1: Tests cover every new behavior introduced by the diff.
R2: Tests bind to intent, not just observable behavior; no new or changed test is tautological (passes against the pre-change code, or cannot fail as written).
R3: No skipped or xfail tests mask failures.

### Integration

R4: Changed components integrate with existing callers.

### Security

R6: No hardcoded secrets in the codebase.
R7: All user input is validated and sanitized.
R8: No injection-unsafe queries or commands.

### Domain

R9: Implementation matches PRD feature behavior exactly.
R10: Error handling is explicit and not swallowed.
R11: No debug statements, TODOs, or placeholder markers remain.

### Code Quality

R12: Function sizes respect the 50-line limit.
R13: File sizes respect the 800-line limit.

Review the completed work against PRD requirements. Explore the codebase as needed.

OUTPUT FORMAT IS MANDATORY. Follow exactly:

Each agent outputs issues in this exact format:

```
[{AGENT_NAME}] {emoji} {description} | File: {path or "N/A"} | Task: {id or "general"}
```

**Severity emojis:** 🔴 Critical, 🟠 High, 🟡 Medium, ⚪ Low

**Rules:**
- One issue per line
- Use "N/A" for file if issue is architectural/cross-cutting
- Use "general" for task if issue spans multiple tasks or is a PRD gap
- If zero issues found: `[{AGENT_NAME}] ✅ No issues found`

**Examples:**
```
[ALICE] 🔴 SQL injection in query builder | File: src/db/query.ts | Task: 3
[BOB] 🟠 Missing error handling strategy | File: N/A | Task: general
[CARL] 🟡 PRD section 2.3 not implemented | File: N/A | Task: 5
```


PER-RULE VERDICTS ARE MANDATORY. For every rule in the numbered rubric, emit one line:
R{n}: pass   or   R{n}: fail
(one rule per line, no other text on the line, no rationale).

## Sandbox Constraints

You run in a restricted sandbox. You CANNOT execute code, tests, linters, or package managers.

Perform STATIC analysis only:
- Read code for logical correctness, patterns, naming, structure
- Check for missing imports, dead code, type mismatches
- Review against PRD requirements by reading, not executing
- Trace data flow and control flow by reading source

If a criterion requires runtime verification (e.g. "tests pass", "linter clean"), output:
[BOB] ⚪ Cannot statically verify: {criterion description} | File: N/A | Task: {id}

Do NOT attempt to run commands. Do NOT report failures from blocked execution.

## Two lenses, applied to every changed file

Treat (no pack available this cycle) as findings precedent already recorded for this diff's changed symbols. Weigh it when applying both lenses and the rubric verdicts rather than re-litigating known prior findings.

### 1. Doubt lens (correctness)
Surface residual findings a confident reviewer would wave past:
- spec gaps: PRD says X, code does Y (wrong field names, enum values,
  thresholds, artifact kind);
- missing or incomplete features the PRD requires;
- edge cases, error paths, and failure modes left unhandled;
- tests that cannot fail: they assert the implementation rather than the intent,
  or still pass against the pre-change code (the caller's mechanical test checks
  list every one it found; each is behavior left unpinned).

### 2. De-slop lens (quality)
Flag slop introduced by the changes (do not propose broad refactors):
- over-abstraction / single-caller indirection with no current testability or
  architectural need;
- dead code, code kept in comments, unreachable branches;
- defensive guards for states that cannot occur;
- restating docstrings, "robust" error messages with no context, premature
  configuration, framework-verification tests;
- speculative generality (parameters, hooks, or layers nothing uses yet).
Bias: aggressive on newly-created files (slop concentrates there), conservative
on lightly-touched files (do not destabilize existing behavior).


## Rubric verdicts (REQUIRED — emit verbatim, one per line)

Apply the doubt-review rubric. A rule you cannot evaluate is `fail`; never omit
a line.
- D1: every residual finding is in exactly one of FIX/VERIFY/KNOWN.
- D2: all FIX items are genuinely fixable now (bounded, in-scope, actionable).
- D3: all VERIFY items name the exact check needed (not vague).
- D4: all KNOWN items carry a written out-of-scope justification.
- D5: input finding count equals FIX + VERIFY + KNOWN counts.

Emit exactly:

```
D1: pass|fail
D2: pass|fail
D3: pass|fail
D4: pass|fail
D5: pass|fail
```

Do not modify any files. This is a review only — produce findings and the
rubric verdict lines. No commits.

# Doubt-Review Rubric

This rubric applies binary pass/fail rules to the output of Phase 8 doubt-review. For each residual finding, the reviewer must categorize it as FIX, VERIFY, or KNOWN. The rubric ensures consistent categorization and that no finding is silently dropped.

Rule ids use the `D` prefix (PRD 00108). The three review rubrics once shared a
single id namespace, which made a bare rule id ambiguous across consensus, blind
and doubt — a latent misroute now that rubric ids live inside agent files. The
consensus set keeps the `R` prefix, blind took `B`, doubt took `D`. Ids are
stable within a set: the prefix changed, no rule was renumbered.

## Rules

### Full Categorization

D1: Every residual finding is placed in exactly one of FIX/VERIFY/KNOWN.

### FIX Validity

D2: All items in FIX bucket are genuinely fixable now (bounded scope, in-scope, actionable).

### VERIFY Validity

D3: All items in VERIFY bucket name the exact check needed to resolve them (not vague "look into X").

### KNOWN Validity

D4: All items in KNOWN bucket carry a written justification explaining why they are out-of-scope.

### Count Conservation

D5: Input finding count equals the sum of FIX + VERIFY + KNOWN counts.


Retain the mandatory [BOB] issue-line contract. For D1-D5, identify exactly one FIX, VERIFY, or KNOWN bucket for each residual finding within its description, preserving one finding per issue line. This does not replace the R verdicts: emit both the current R set and D1-D5.

## Inlined context

# Review Context

## Completed Tasks

# Completed tasks

Standalone manual review: no state.json or canonical task store exists. The two checked PRD tasks and commit scope supply the table below; they do not substitute for independent verification.

| Task | Description | Commit |
|---|---|---|
| 1 | Guard target read_bytes calls and stat in _verdict_for; map OSError to syntax_error and cover directory targets with fail-first tests. Shared commit with task 2. | ece9ac34053a17e9629e9af50355e7c84dc32fe2 |
| 2 | Guard write_bytes and replace in _repair_known, clean partial temp files, preserve later rows; add regression tests and Fixed changelog entry. Shared commit with task 1. | ece9ac34053a17e9629e9af50355e7c84dc32fe2 |

## Code Changes

### Changed Files
_Diff scope: full PRD review, explicit authorized base 9336ab507525e13a685957a41b338561e74032fd (the gather script's --since selects this base; this is cycle 1)._

```
 CHANGELOG.md                                       |   1 +
 skills/use-codex/scripts/codex_hook_doctor.py      |  31 ++-
 .../scripts/test_codex_hook_doctor_parse_errors.py | 263 ++++++++++++++++++++-
 3 files changed, 285 insertions(+), 10 deletions(-)
```

### Diff Content
Full diff available at: /Users/bob/git/src/github.com/buvis/claude-autopilot/dev/local/tmp/review-diff-00176-01.diff

(361 lines)

## PRD Requirements

---
catchup: skip
design: skip
default_model: sonnet
model_tier_rationale: guards at named call sites with the verdict pinned; additive fail-first tests
---

# Guard the target reads in the doctor

Source: PRD 00173's review cycle 1 — Blake's residual-unguarded-operations finding and Eve's first KNOWN item, both against `dev/local/reviews/00173-guard-the-canonical-read-in-the-doctor-verdict-v1-review-1.md`. Filed 2026-09-05. This is the next layer of the onion PRD 00169 → 00173 has been peeling: 00169 guarded the import scan, 00173 guarded the canonical reads, and the target-side reads are what remain.

## Overview

### Problem Statement

`skills/use-codex/scripts/codex_hook_doctor.py` still aborts the whole run with exit 2 and no TSV rows when a **target** (rather than a canonical) cannot be read. Three unguarded paths remain, all confirmed by reading, one confirmed live:

1. `_verdict_for` compiles the target with `compile(target.read_bytes(), ...)`. `read_bytes()` raises `OSError` when the target is a directory or is unreadable. `check` collects targets from `hooks_dir.glob("*.py")`, and **glob matches directories**, so a directory literally named `something.py` under `hooks/` aborts the run. Confirmed live during the 00173 review: `error: [Errno 21] Is a directory: .../hooks/x.py`, exit 2.
2. `_verdict_for`'s staleness comparison reads the target a second time (`canonical_bytes != target.read_bytes()`). Same exposure, and it is a second read of a file that may have changed since the first.
3. `_repair_known`'s write path (`tmp_path.write_bytes(canonical_bytes)` then `os.replace(tmp_path, target)`) is unguarded. A read-only hooks directory, a full disk, or a permission change between check and write raises `OSError` out of `repair`: exit 2, and any targets not yet processed get no row at all.

`_verdict_for` also calls `target.stat()` right after `target.exists()`. That is a check-then-act window: a target removed between the two calls raises `OSError` from `stat()`.

The batch codex health probe reads this exit code. Exit 2 means "the doctor itself could not run", so one broken file on the host currently masks the verdict of every other hook.

### Target Users

The operator running `repair` against a damaged plugin cache, and the batch codex health probe reading the doctor's exit code.

### Success Metrics

- A target that is a directory, or unreadable, yields one row for that target and the run exits 1 or 3, never 2.
- A repair whose write fails yields `unrepairable` for that target, still processes every remaining target, and never exits 2.
- A target deleted between `exists()` and `stat()` is verdicted, not raised.
- Every existing verdict string and `_report`'s counting stay unchanged; `skills/use-codex/SKILL.md`'s exit-code list needs no edit.

## Functional Decomposition

### Capability: Doctor verdicts

#### Feature: An unreadable target verdicts itself
- **Description**: a target that exists but cannot be read verdicts that one target instead of aborting the run.
- **Inputs**: a target whose `read_bytes()` or `stat()` raises `OSError` — a directory, a permission-denied file, or one removed mid-run.
- **Outputs**: a `syntax_error` verdict for that target with the `OSError` text in the detail; exit 1 or 3 through `_report`'s existing counting.
- **Behavior**: guard both `target.read_bytes()` calls and the `stat()` in `_verdict_for`, mapping `OSError` to `syntax_error` with the `OSError` text as the detail. No new verdict string: `syntax_error` already carries a detail and gates the rung off, which is the safe direction for a hook that cannot be read.

#### Feature: A failed write costs one row, not the run
- **Description**: an `OSError` from the repair write is reported for that target and does not stop the remaining targets.
- **Inputs**: a hooks directory that is read-only, full, or whose permissions changed after the check.
- **Outputs**: `unrepairable` for that target with the `OSError` in the detail; every other target still processed.
- **Behavior**: guard `tmp_path.write_bytes(...)` and `os.replace(...)` in `_repair_known`, and remove the temp file if it was created before the failure, so a failed repair leaves no `.tmp` litter beside the hook.

## Structural Decomposition

### Repository Structure

```
skills/use-codex/scripts/codex_hook_doctor.py                  # Maps to: both features
skills/use-codex/scripts/test_codex_hook_doctor_parse_errors.py  # Maps to: regression tests (the other three doctor test modules are at 772/789/795 against the 800-line limit)
CHANGELOG.md
```

### Module: hook-doctor
- **Maps to capability**: Doctor verdicts
- **Responsibility**: the guarded target reads and the guarded repair write.
- **Exports**: none new (`_verdict_for` and `_repair_known` keep their signatures)

## Dependency Graph

### Foundation Layer (Phase 0)
No dependencies.

- **hook-doctor**: the guarded target reads and write.

## Implementation Phases

### Phase 0: Guard the target paths
**Goal**: no host file can abort the doctor with exit 2.

**Tasks**:
- [x] Guard both `target.read_bytes()` calls and the `stat()` in `_verdict_for`, mapping `OSError` to `syntax_error` with the `OSError` text as the detail; one fail-first test using a directory named `*.py` under `hooks/` asserting `check` never exits 2 (no deps) - Acceptance: `uv run --no-project --with pytest python -m pytest -q skills/use-codex/scripts` green with the new test present, and the test fails against the pre-change module.
- [x] Guard `tmp_path.write_bytes` and `os.replace` in `_repair_known`, cleaning up a partial `.tmp`; one fail-first test with a read-only hooks directory asserting the other targets still get rows (depends on task 1); CHANGELOG `**use-codex**` under Fixed - Acceptance: suite green; `bash dev/bin/release-checks` green.

**Exit Criteria**: suite green; `bash dev/bin/release-checks` green.

## Test Strategy

### Critical Scenarios
- **Happy path**: a readable stale target with a readable canonical → Expected: `repaired`, unchanged from today.
- **Edge case**: a directory named `x.py` under `hooks/` → Expected: one row for it, exit 1 or 3, never 2, and every other target still verdicted.
- **Error case**: a read-only hooks directory during repair → Expected: `unrepairable` for the target that could not be written, rows for all others, no leftover `.tmp` file, never exit 2.

## Risks

- A test that makes a directory read-only must restore its mode in teardown, or it leaves an undeletable `tmp_path` behind and poisons later runs. Use a fixture with explicit cleanup; skip the case when running as root, where mode bits do not deny.
- Mapping target `OSError` onto `syntax_error` widens what that verdict means; the detail column carries the `OSError` text, and the code comment records why no new verdict was added (a new string would touch `_report`'s counting and `SKILL.md`'s exit-code list).

## Architecture context

# Project Capsule: claude-autopilot

Generated: 2026-09-01

## Key Invariants

- This repo IS the `autopilot@buvis-plugins` skill pack's source. An autopilot
  batch drained *in this repo* executes the **marketplace-cached** install
  (`~/.claude/plugins/cache/buvis-plugins/autopilot/<version>`), not the
  checkout — nothing a PRD changes here is live until `dev/bin/release` +
  `/plugin update`. See memory `project-batch-runs-installed-cache`.
- Bob (codex reviewer) needs his prompt fully inlined (header + context + diff
  + PRD text in one file) — path references are unreadable in his sandbox. See
  memory `project-bob-codex-needs-inlined-prompt`.
- `enforce_prd_location.py` keeps `dev/local/prds/` lifecycle dirs canonical;
  a repo-root `backlog/`/`wip/`/`hold/`/`done/` reference is blocked.

## Architecture Decisions

- Ten skills drive a PRD lifecycle: catchup → design → plan-tasks → work →
  review-rework loop (consensus/blind/doubt lenses every cycle) → done.
- Fourteen agents: one implementor (`ivan`), thirteen reviewers across four
  lenses (consensus: alice/bob/carl; blind: blake; doubt: eve; dimensions:
  rita/cora/grace/toby/mallory/trent/victor/pat).
  bob (codex) and carl (gemini) dispatch to external CLIs; both refuse to
  recurse when already inside a CLI agent (`AUTOPILOT_DISPATCH_DEPTH` /
  host markers) — see README "Recursion guard".
- PRD 00164 (this batch's selection) added VERIFY-finding routing: a
  doubt-lens finding with an exact named check gets queued to
  `dev/local/reviews/{prd-stem}-checks-{cycle}.json` instead of becoming a
  task; `work` step 7 runs the queue inside its one mandatory verification
  pass and writes `dev/local/autopilot/last-verification.json`; the review's
  `Tests:` line reuses that record when its `sha` matches the reviewed HEAD.
  This collapses the "full suite runs up to 3x per cycle" duplication.

## Component Boundaries

- `skills/run-autopilot/cli/` is the sole `state.json` mutator surface
  (`statectl.py` + the `autopilot` subcommand CLI); skills invoke it rather
  than hand-editing state.
- `skills/work/references/final-verification.md` owns the verification
  procedure (suite run, queued checks, the recorded-result write); the
  review skill only *reads* `last-verification.json`, never writes it.

## Active Work

### Batch 202609011951
- [x] 00164-close-verify-findings-through-the-final-gate-v1 (0 cycles this
      batch — retroactive finalize; the work was already implemented, tested,
      changelogged and released as v0.3.0 in a prior session, the PRD file
      just never moved out of wip/)
- [x] 00161-doctor-codex-host-hooks-v1 (2 cycles)
- [x] 00160-route-opus-on-task-local-risk-v1 (2 cycles)
- [x] 00171-route-sonnet-prompt-through-stdin-v1 (1 cycle)
- [ ] 00173-guard-the-canonical-read-in-the-doctor-verdict-v1 (backlog)
- [ ] 00174-align-qwen-routing-with-single-file-trust-v1 (backlog)

Observations: PRD numbering here continues independently of the `~/.claude`
repo's sequence (same numbers across the two repos are not a collision).

## GitHub State

- 0 open issues, 0 open PRs.
- Only `origin`/`origin/master` active (both current, no stale branches).
- No tagged GitHub releases; CHANGELOG.md tracks versions instead (latest:
  0.3.0, 2026-09-01).
- No workflow runs found (no CI configured, or none has run).

## Project Health

CI: none configured/observed. Backlog has 3 PRDs (00160, 00161, 00168)
untouched. Working tree is clean on `master`.

## Project Memories

- `project-batch-runs-installed-cache`: batches here run the installed cache,
  need a release to take effect, must not write to `~/.claude`.
- `project-bob-codex-needs-inlined-prompt`: Bob's codex sandbox needs an
  inlined prompt, not path references.

## Verification independently run this cycle

Full suite: `mise exec -- uv run --no-project --with pytest --with rich --with textual python -m pytest -q skills` exited 0: 2608 passed, 1 skipped, 4 warnings, 459 subtests passed in 79.14s. The one skip is outside this diff. Release checks are pending independent verification.

## Mechanical facts (computed, do not re-count)

Function line counts from `ast`. Cite these for countable claims; a
finding that contradicts this block is discarded at the review gate.

- `CHANGELOG.md` — skipped (non-python)
- `skills/use-codex/scripts/codex_hook_doctor.py`
  - `_iter_commands` — line 31, 8 lines
  - `_resolve_target` — line 41, 6 lines
  - `_verdict_for` — line 49, 43 lines
  - `_load_hooks` — line 94, 5 lines
  - `check` — line 101, 29 lines
  - `_missing_common_import_names` — line 132, 39 lines
  - `_repair_unknown` — line 173, 9 lines
  - `_repair_known` — line 184, 53 lines
  - `_repair_target` — line 239, 38 lines
  - `_remove_orphaned_empty` — line 279, 20 lines
  - `repair` — line 301, 37 lines
  - `_default_config` — line 340, 5 lines
  - `_default_aegis_root` — line 347, 4 lines
  - `_default_autopilot_root` — line 353, 2 lines
  - `_build_parser` — line 357, 13 lines
  - `_resolve_roots` — line 372, 13 lines
  - `_run_subcommand` — line 387, 21 lines
  - `_report` — line 410, 21 lines
  - `main` — line 433, 20 lines
- `skills/use-codex/scripts/test_codex_hook_doctor_parse_errors.py`
  - `test_bare_value_error_from_parse_marks_sibling_and_canonical_unreadable` — line 48, 23 lines
  - `test_bare_value_error_from_parse_marks_sibling_and_canonical_unreadable.fake_parse` — line 60, 4 lines
  - `test_check_directory_target_reports_error_and_remaining_rows` — line 73, 32 lines
  - `test_target_deleted_between_exists_and_stat_is_verdicted` — line 107, 21 lines
  - `test_target_deleted_between_exists_and_stat_is_verdicted.disappearing_exists` — line 116, 5 lines
  - `test_staleness_uses_the_target_bytes_that_compiled` — line 130, 24 lines
  - `test_staleness_uses_the_target_bytes_that_compiled.disappearing_read` — line 142, 5 lines
  - `unreadable_target` — line 157, 11 lines
  - `test_unreadable_target_is_verdicted` — line 170, 10 lines
  - `repair_targets` — line 183, 19 lines
  - `readonly_hooks` — line 205, 12 lines
  - `test_readonly_repair_reports_all_targets_without_tmp_litter` — line 219, 19 lines
  - `test_failed_repair_cleans_tmp_and_repairs_next_target` — line 241, 40 lines
  - `test_failed_repair_cleans_tmp_and_repairs_next_target.partial_write` — line 254, 5 lines
  - `test_failed_repair_cleans_tmp_and_repairs_next_target.failed_replace` — line 260, 4 lines
  - `test_cleanup_failure_is_reported_without_losing_remaining_rows` — line 283, 38 lines
  - `test_cleanup_failure_is_reported_without_losing_remaining_rows.failed_replace` — line 294, 4 lines
  - `test_cleanup_failure_is_reported_without_losing_remaining_rows.failed_unlink` — line 299, 4 lines

## Tautological test shapes (computed, do not re-judge)

Each `[MECH]` line is a test whose shape cannot fail as written. Raise
it; step 6 adds any line the table lacks. `mech-check` is the finder.


Checked 8 test function(s) in 1 test file(s).

## Fail-first replay (computed, do not re-judge)

Touched tests from HEAD, run against the pre-change code at `9336ab507525`
(HEAD's test files overlaid on a base worktree). A test that passes there
does not pin this change. A behavior-preserving refactor's tests pass by
design, so weigh the PRD's intent before raising one. `mech-check` is the finder.


Replay: 8 touched test(s) ran, 8 failed against base, 0 passed; 0 test file(s) could not be collected at base (their tests fail there). Command: mise exec -- uv run --no-project --with pytest python -m pytest


## Inlined diff

diff --git a/CHANGELOG.md b/CHANGELOG.md
index d7b784d..4910a5e 100644
--- a/CHANGELOG.md
+++ b/CHANGELOG.md
@@ -15,6 +15,7 @@ and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0
 
 ### Fixed
 
+- **use-codex**: report unreadable hook targets and failed repairs per target, continue processing remaining hooks, and clean up temporary files after failed writes.
 - **use-gemini**: restore Carl's Copilot lane with a served Gemini Flash pin,
   distinguish permanent model/client-tier rejection (exit 4) from runtime
   failures, try native Gemini for rejected default prompt runs, and keep
diff --git a/skills/use-codex/scripts/codex_hook_doctor.py b/skills/use-codex/scripts/codex_hook_doctor.py
index b25a705..f67336a 100644
--- a/skills/use-codex/scripts/codex_hook_doctor.py
+++ b/skills/use-codex/scripts/codex_hook_doctor.py
@@ -51,10 +51,16 @@ def _verdict_for(
     aegis_root: Path,
     autopilot_root: Path,
 ) -> tuple[str, str]:
-    if not target.exists():
-        return "missing", ""
-    if target.stat().st_size == 0:
-        return "empty", ""
+    try:
+        if not target.exists():
+            return "missing", ""
+        if target.stat().st_size == 0:
+            return "empty", ""
+        target_bytes = target.read_bytes()
+    except OSError as exc:
+        # Unreadable hooks gate the rung off just like invalid Python;
+        # reuse syntax_error so report counting and exit codes stay unchanged.
+        return "syntax_error", str(exc)
 
     # Syntax outranks staleness: a hook that cannot compile fails on every
     # tool call, and `stale` exits 3 (rung stays on) while `syntax_error`
@@ -65,7 +71,7 @@ def _verdict_for(
     # cookie the way the interpreter would. ValueError covers a null byte on
     # 3.10 (SyntaxError from 3.11) and is UnicodeDecodeError's base.
     try:
-        compile(target.read_bytes(), str(target), "exec")
+        compile(target_bytes, str(target), "exec")
     except (SyntaxError, ValueError) as exc:
         return "syntax_error", str(exc)
 
@@ -78,7 +84,8 @@ def _verdict_for(
             canonical_bytes = canonical.read_bytes()
         except OSError:
             return "no_canonical", ""
-        if canonical_bytes != target.read_bytes():
+        # Compare the bytes that compiled, without another target read/race.
+        if canonical_bytes != target_bytes:
             return "stale", ""
 
     return "ok", ""
@@ -216,8 +223,16 @@ def _repair_known(
         return ("would-repair", target_str, str(canonical))
 
     tmp_path = target.with_name(target.name + ".tmp")
-    tmp_path.write_bytes(canonical_bytes)
-    os.replace(tmp_path, target)
+    try:
+        tmp_path.write_bytes(canonical_bytes)
+        os.replace(tmp_path, target)
+    except OSError as exc:
+        detail = str(exc)
+        try:
+            tmp_path.unlink(missing_ok=True)
+        except OSError as cleanup_exc:
+            detail += f"; temp cleanup failed: {cleanup_exc}"
+        return ("unrepairable", target_str, detail)
     return ("repaired", target_str, str(canonical))
 
 
diff --git a/skills/use-codex/scripts/test_codex_hook_doctor_parse_errors.py b/skills/use-codex/scripts/test_codex_hook_doctor_parse_errors.py
index 2da82fa..cfb62a2 100644
--- a/skills/use-codex/scripts/test_codex_hook_doctor_parse_errors.py
+++ b/skills/use-codex/scripts/test_codex_hook_doctor_parse_errors.py
@@ -1,4 +1,4 @@
-"""Interpreter-independent pins for the parse-error branches of
+"""Target I/O regressions (PRD 00176) and interpreter-independent pins for
 `_missing_common_import_names` (PRD 00173, added by review cycle 1).
 
 The CLI-level null-byte test in test_codex_hook_doctor_extra.py discriminates
@@ -25,11 +25,20 @@ the project's 800-line file limit.
 from __future__ import annotations
 
 import ast
+import errno
+import os
+from collections.abc import Iterator
 from pathlib import Path
 from typing import Any
 
 import pytest
-from test_codex_hook_doctor import codex_hook_doctor
+from test_codex_hook_doctor import (
+    _fake_roots,
+    _run_cli,
+    _write_config,
+    codex_hook_doctor,
+)
+from test_codex_hook_doctor_repair import _run_repair_cli
 
 _UNREADABLE = "unreadable (cannot verify _common imports)"
 # Stands in for bytes the interpreter refuses; the stub keys off this exact text.
@@ -59,3 +68,253 @@ def test_bare_value_error_from_parse_marks_sibling_and_canonical_unreadable(
         f"bad_sibling.py: {_UNREADABLE}",
         f"_common.py: {_UNREADABLE}",
     ]
+
+
+def test_check_directory_target_reports_error_and_remaining_rows(
+    tmp_path: Path,
+) -> None:
+    hooks_dir = tmp_path / "hooks"
+    hooks_dir.mkdir()
+    bad = hooks_dir / "a_directory.py"
+    bad.mkdir()
+    good = hooks_dir / "z_good.py"
+    good.write_text("X = 1\n", encoding="utf-8")
+    config = tmp_path / "hooks.json"
+    _write_config(config, {})  # Both targets must be discovered by glob.
+    aegis_root, autopilot_root = _fake_roots(tmp_path)
+
+    proc = _run_cli(
+        [
+            "--config",
+            str(config),
+            "--aegis-root",
+            str(aegis_root),
+            "--autopilot-root",
+            str(autopilot_root),
+        ]
+    )
+
+    assert proc.returncode == 1, proc.stderr
+    rows = [line.split("\t") for line in proc.stdout.splitlines()]
+    assert rows[0][:2] == ["syntax_error", str(bad)]
+    assert "Is a directory" in rows[0][2]
+    assert rows[1] == ["ok", str(good), ""]
+    assert rows[2] == ["summary", "1 ok, 0 stale, 1 broken"]
+    assert len(rows) == 3
+    assert proc.stderr == ""
+
+
+def test_target_deleted_between_exists_and_stat_is_verdicted(
+    tmp_path: Path,
+    monkeypatch: pytest.MonkeyPatch,
+) -> None:
+    target = tmp_path / "gone.py"
+    target.write_text("X = 1\n", encoding="utf-8")
+    aegis_root, autopilot_root = _fake_roots(tmp_path)
+    real_exists = Path.exists
+
+    def disappearing_exists(path: Path) -> bool:
+        exists = real_exists(path)
+        if path == target and exists:
+            path.unlink()
+        return exists
+
+    monkeypatch.setattr(Path, "exists", disappearing_exists)
+    verdict, detail = codex_hook_doctor._verdict_for(target, aegis_root, autopilot_root)
+
+    assert verdict == "syntax_error"
+    assert "No such file or directory" in detail
+    assert str(target) in detail
+
+
+def test_staleness_uses_the_target_bytes_that_compiled(
+    tmp_path: Path,
+    monkeypatch: pytest.MonkeyPatch,
+) -> None:
+    target = tmp_path / "protect_config.py"
+    target.write_bytes(b"X = 1\n")
+    aegis_root, autopilot_root = _fake_roots(tmp_path)
+    (aegis_root / "hooks").mkdir()
+    canonical = aegis_root / "hooks" / target.name
+    canonical.write_bytes(b"X = 1\n")
+    real_read = Path.read_bytes
+
+    def disappearing_read(path: Path) -> bytes:
+        data = real_read(path)
+        if path == target:
+            path.unlink()
+        return data
+
+    monkeypatch.setattr(Path, "read_bytes", disappearing_read)
+
+    assert codex_hook_doctor._verdict_for(target, aegis_root, autopilot_root) == (
+        "ok",
+        "",
+    )
+
+
+@pytest.fixture
+def unreadable_target(tmp_path: Path) -> Iterator[Path]:
+    if os.geteuid() == 0:
+        pytest.skip("root bypasses file permission bits")
+    target = tmp_path / "unreadable.py"
+    target.write_text("X = 1\n", encoding="utf-8")
+    mode = target.stat().st_mode
+    target.chmod(0)
+    try:
+        yield target
+    finally:
+        target.chmod(mode)
+
+
+def test_unreadable_target_is_verdicted(unreadable_target: Path) -> None:
+    verdict, detail = codex_hook_doctor._verdict_for(
+        unreadable_target,
+        unreadable_target.parent,
+        unreadable_target.parent,
+    )
+
+    assert verdict == "syntax_error"
+    assert "Permission denied" in detail
+    assert str(unreadable_target) in detail
+
+
+@pytest.fixture
+def repair_targets(tmp_path: Path) -> tuple[Path, list[str]]:
+    hooks_dir = tmp_path / "hooks"
+    hooks_dir.mkdir()
+    aegis_root, autopilot_root = _fake_roots(tmp_path)
+    (aegis_root / "hooks").mkdir()
+    names = ["protect_config.py", "validate_commit_msg.py"]
+    for name in names:
+        (hooks_dir / name).write_bytes(b"X = 1\n")
+        (aegis_root / "hooks" / name).write_bytes(b"X = 2\n")
+    config = tmp_path / "hooks.json"
+    _write_config(config, {"PreToolUse": [f"python3 hooks/{name}" for name in names]})
+    return hooks_dir, [
+        "--config",
+        str(config),
+        "--aegis-root",
+        str(aegis_root),
+        "--autopilot-root",
+        str(autopilot_root),
+    ]
+
+
+@pytest.fixture
+def readonly_hooks(
+    repair_targets: tuple[Path, list[str]],
+) -> Iterator[tuple[Path, list[str]]]:
+    if os.geteuid() == 0:
+        pytest.skip("root bypasses directory permission bits")
+    hooks_dir, _ = repair_targets
+    mode = hooks_dir.stat().st_mode
+    hooks_dir.chmod(0o555)
+    try:
+        yield repair_targets
+    finally:
+        hooks_dir.chmod(mode)
+
+
+def test_readonly_repair_reports_all_targets_without_tmp_litter(
+    readonly_hooks: tuple[Path, list[str]],
+) -> None:
+    hooks_dir, args = readonly_hooks
+
+    proc = _run_repair_cli(args)
+
+    assert proc.returncode == 3, proc.stderr
+    rows = [line.split("\t") for line in proc.stdout.splitlines()]
+    assert rows[0][:2] == ["unrepairable", str(hooks_dir / "protect_config.py")]
+    assert "Permission denied" in rows[0][2]
+    assert rows[1][:2] == ["unrepairable", str(hooks_dir / "validate_commit_msg.py")]
+    assert "Permission denied" in rows[1][2]
+    assert rows[2] == ["summary", "0 ok, 2 stale, 0 broken"]
+    assert len(rows) == 3
+    assert list(hooks_dir.glob("*.tmp")) == []
+    assert (hooks_dir / "protect_config.py").read_bytes() == b"X = 1\n"
+    assert (hooks_dir / "validate_commit_msg.py").read_bytes() == b"X = 1\n"
+    assert proc.stderr == ""
+
+
+@pytest.mark.parametrize("failure", ["partial_write", "replace"])
+def test_failed_repair_cleans_tmp_and_repairs_next_target(
+    repair_targets: tuple[Path, list[str]],
+    monkeypatch: pytest.MonkeyPatch,
+    capsys: pytest.CaptureFixture[str],
+    failure: str,
+) -> None:
+    hooks_dir, args = repair_targets
+    target = hooks_dir / "protect_config.py"
+    temp = target.with_name(target.name + ".tmp")
+    real_write = Path.write_bytes
+    real_replace = os.replace
+    error = OSError(errno.ENOSPC, "No space left on device", str(temp))
+
+    def partial_write(path: Path, data: bytes) -> int:
+        if path == temp:
+            real_write(path, data[:1])
+            raise error
+        return real_write(path, data)
+
+    def failed_replace(src: Path, dst: Path) -> None:
+        if dst == target:
+            raise error
+        real_replace(src, dst)
+
+    if failure == "partial_write":
+        monkeypatch.setattr(Path, "write_bytes", partial_write)
+    else:
+        monkeypatch.setattr(codex_hook_doctor.os, "replace", failed_replace)
+
+    assert codex_hook_doctor.main(["repair", *args]) == 3
+    output = capsys.readouterr()
+    rows = [line.split("\t") for line in output.out.splitlines()]
+    assert rows[0] == ["unrepairable", str(target), str(error)]
+    assert rows[1][:2] == ["repaired", str(hooks_dir / "validate_commit_msg.py")]
+    assert rows[2] == ["summary", "1 ok, 1 stale, 0 broken"]
+    assert len(rows) == 3
+    assert list(hooks_dir.glob("*.tmp")) == []
+    assert target.read_bytes() == b"X = 1\n"
+    assert (hooks_dir / "validate_commit_msg.py").read_bytes() == b"X = 2\n"
+    assert output.err == ""
+
+
+def test_cleanup_failure_is_reported_without_losing_remaining_rows(
+    repair_targets: tuple[Path, list[str]],
+    monkeypatch: pytest.MonkeyPatch,
+    capsys: pytest.CaptureFixture[str],
+) -> None:
+    hooks_dir, args = repair_targets
+    target = hooks_dir / "protect_config.py"
+    temp = target.with_name(target.name + ".tmp")
+    real_replace = os.replace
+    real_unlink = Path.unlink
+
+    def failed_replace(src: Path, dst: Path) -> None:
+        if dst == target:
+            raise PermissionError(errno.EACCES, "replace denied", str(target))
+        real_replace(src, dst)
+
+    def failed_unlink(path: Path, missing_ok: bool = False) -> None:
+        if path == temp:
+            raise PermissionError(errno.EACCES, "cleanup denied", str(temp))
+        real_unlink(path, missing_ok=missing_ok)
+
+    monkeypatch.setattr(codex_hook_doctor.os, "replace", failed_replace)
+    monkeypatch.setattr(Path, "unlink", failed_unlink)
+
+    assert codex_hook_doctor.main(["repair", *args]) == 3
+    output = capsys.readouterr()
+    rows = [line.split("\t") for line in output.out.splitlines()]
+    assert rows[0][:2] == ["unrepairable", str(target)]
+    assert "replace denied" in rows[0][2]
+    assert "temp cleanup failed:" in rows[0][2]
+    assert "cleanup denied" in rows[0][2]
+    assert rows[1][:2] == ["repaired", str(hooks_dir / "validate_commit_msg.py")]
+    assert rows[2] == ["summary", "1 ok, 1 stale, 0 broken"]
+    assert len(rows) == 3
+    assert target.read_bytes() == b"X = 1\n"
+    assert (hooks_dir / "validate_commit_msg.py").read_bytes() == b"X = 2\n"
+    assert temp.read_bytes() == b"X = 2\n"
+    assert output.err == ""


## Full current implementation (for static reading only)

```python
#!/usr/bin/env python3
"""Doctor for a codex hooks.json — verdicts every referenced hook target.

Usage:
    codex_hook_doctor.py check --config PATH --aegis-root PATH --autopilot-root PATH
"""

from __future__ import annotations

import argparse
import ast
import json
import os
import shlex
import sys
from pathlib import Path

# basename -> (root the canonical source resolves against, relative path
# under that root)
KNOWN_HOOKS: dict[str, tuple[str, str]] = {
    "validate_commit_msg.py": ("aegis", "hooks/validate_commit_msg.py"),
    "_common.py": ("aegis", "hooks/_common.py"),
    "protect_config.py": ("aegis", "hooks/protect_config.py"),
    "block_devlocal_redirects.py": ("aegis", "hooks/block_devlocal_redirects.py"),
    "block-suppression-markers.py": ("aegis", "hooks/block_suppression_markers.py"),
    "gateguard-fact-force.py": ("aegis", "hooks/gateguard_fact_force.py"),
    "enforce_prd_location.py": ("autopilot", "hooks/enforce_prd_location.py"),
}


def _iter_commands(hooks: dict) -> list[str]:
    commands: list[str] = []
    for entries in hooks.values():
        for entry in entries:
            for hook in entry.get("hooks", []):
                if hook.get("type") == "command":
                    commands.append(hook["command"])
    return commands


def _resolve_target(command: str, config_dir: Path) -> Path:
    tokens = shlex.split(command)
    path = Path(tokens[-1])
    if not path.is_absolute():
        path = config_dir / path
    return Path(os.path.normpath(path))


def _verdict_for(
    target: Path,
    aegis_root: Path,
    autopilot_root: Path,
) -> tuple[str, str]:
    try:
        if not target.exists():
            return "missing", ""
        if target.stat().st_size == 0:
            return "empty", ""
        target_bytes = target.read_bytes()
    except OSError as exc:
        # Unreadable hooks gate the rung off just like invalid Python;
        # reuse syntax_error so report counting and exit codes stay unchanged.
        return "syntax_error", str(exc)

    # Syntax outranks staleness: a hook that cannot compile fails on every
    # tool call, and `stale` exits 3 (rung stays on) while `syntax_error`
    # exits 1 (rung gates off). Checking drift first would report the
    # harmless verdict for the harmful state. `compile()` writes no bytecode
    # (`check` is contractually read-only, and a batch runs it against the
    # real ~/.codex) and, handed the raw bytes, honours a PEP 263 coding
    # cookie the way the interpreter would. ValueError covers a null byte on
    # 3.10 (SyntaxError from 3.11) and is UnicodeDecodeError's base.
    try:
        compile(target_bytes, str(target), "exec")
    except (SyntaxError, ValueError) as exc:
        return "syntax_error", str(exc)

    known = KNOWN_HOOKS.get(target.name)
    if known is not None:
        root_name, canonical_rel = known
        root = aegis_root if root_name == "aegis" else autopilot_root
        canonical = root / canonical_rel
        try:
            canonical_bytes = canonical.read_bytes()
        except OSError:
            return "no_canonical", ""
        # Compare the bytes that compiled, without another target read/race.
        if canonical_bytes != target_bytes:
            return "stale", ""

    return "ok", ""


def _load_hooks(config: Path) -> dict:
    hooks = json.loads(config.read_text(encoding="utf-8"))["hooks"]
    if not isinstance(hooks, dict):
        raise TypeError("hooks must be an object")
    return hooks


def check(
    *,
    config: Path,
    aegis_root: Path,
    autopilot_root: Path,
) -> list[tuple[str, str, str]]:
    hooks = _load_hooks(config)
    config_dir = config.parent

    targets: list[Path] = []
    seen: set[Path] = set()
    for command in _iter_commands(hooks):
        target = _resolve_target(command, config_dir)
        if target not in seen:
            seen.add(target)
            targets.append(target)

    hooks_dir = config_dir / "hooks"
    if hooks_dir.is_dir():
        for path in sorted(hooks_dir.glob("*.py")):
            if path not in seen:
                seen.add(path)
                targets.append(path)

    results: list[tuple[str, str, str]] = []
    for target in targets:
        verdict, detail = _verdict_for(target, aegis_root, autopilot_root)
        results.append((verdict, str(target), detail))
    return results


def _missing_common_import_names(hooks_dir: Path, canonical: Path) -> list[str]:
    imported: set[str] = set()
    unparseable: list[str] = []
    for py_file in sorted(hooks_dir.glob("*.py")):
        if py_file.name == "_common.py":
            continue
        try:
            tree = ast.parse(py_file.read_text(encoding="utf-8"))
        except SyntaxError:
            unparseable.append(
                f"{py_file.name}: SyntaxError (cannot verify _common imports)",
            )
            continue
        except (ValueError, OSError):
            unparseable.append(
                f"{py_file.name}: unreadable (cannot verify _common imports)",
            )
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module == "_common":
                imported.update(alias.name for alias in node.names)

    try:
        canonical_tree = ast.parse(canonical.read_text(encoding="utf-8"))
    except SyntaxError:
        unparseable.append(
            f"{canonical.name}: SyntaxError (cannot verify _common imports)",
        )
        return sorted(imported) + unparseable
    except (ValueError, OSError):
        unparseable.append(
            f"{canonical.name}: unreadable (cannot verify _common imports)",
        )
        return sorted(imported) + unparseable

    defined = {
        node.name for node in canonical_tree.body if isinstance(node, ast.FunctionDef)
    }
    return sorted(imported - defined) + unparseable


def _repair_unknown(
    verdict: str,
    target_str: str,
    detail: str,
) -> tuple[str, str, str] | None:
    if verdict in ("missing", "empty", "syntax_error"):
        why = detail or f"no canonical source for unknown hook ({verdict})"
        return ("unrepairable", target_str, why)
    return None


def _repair_known(
    verdict: str,
    target_str: str,
    known: tuple[str, str],
    *,
    hooks_dir: Path,
    aegis_root: Path,
    autopilot_root: Path,
    dry_run: bool,
) -> tuple[str, str, str] | None:
    if verdict not in ("missing", "empty", "stale", "no_canonical", "syntax_error"):
        return None

    target = Path(target_str)
    if target.is_symlink():
        return ("skipped", target_str, "symlink")

    root_name, canonical_rel = known
    root = aegis_root if root_name == "aegis" else autopilot_root
    canonical = root / canonical_rel
    try:
        canonical_bytes = canonical.read_bytes()
    except OSError:
        return ("unrepairable", target_str, f"no canonical source ({canonical})")

    if target.name == "_common.py":
        missing = _missing_common_import_names(hooks_dir, canonical)
        if missing:
            why = ", ".join(missing)
            # Sole entry = the canonical's own marker: no sibling is to blame,
            # so the prefix would lie. Matching the marker's "<name>: " shape is
            # safe — a Python identifier can hold neither ':' nor '.'.
            if not (len(missing) == 1 and missing[0].startswith(f"{canonical.name}: ")):
                why = (
                    "sibling imports names not defined in canonical _common.py: " + why
                )
            return ("unrepairable", target_str, why)

    if dry_run:
        return ("would-repair", target_str, str(canonical))

    tmp_path = target.with_name(target.name + ".tmp")
    try:
        tmp_path.write_bytes(canonical_bytes)
        os.replace(tmp_path, target)
    except OSError as exc:
        detail = str(exc)
        try:
            tmp_path.unlink(missing_ok=True)
        except OSError as cleanup_exc:
            detail += f"; temp cleanup failed: {cleanup_exc}"
        return ("unrepairable", target_str, detail)
    return ("repaired", target_str, str(canonical))


def _repair_target(
    verdict: str,
    target_str: str,
    detail: str,
    *,
    tests_dir: Path,
    registered: set[Path],
    hooks_dir: Path,
    aegis_root: Path,
    autopilot_root: Path,
    dry_run: bool,
) -> tuple[str, str, str] | None:
    target = Path(target_str)
    try:
        target.relative_to(tests_dir)
        return None
    except ValueError:
        pass

    known = KNOWN_HOOKS.get(target.name)
    # _common.py is never named by a command, so it is always "unregistered".
    # Excluding it here keeps its repair path; the placeholder scan exempts it
    # too, so without this it would be neither repaired nor removed.
    if verdict == "empty" and target not in registered and target.name != "_common.py":
        return None  # zero-byte + unregistered -> handled by the placeholder scan below

    if known is None:
        return _repair_unknown(verdict, target_str, detail)

    return _repair_known(
        verdict,
        target_str,
        known,
        hooks_dir=hooks_dir,
        aegis_root=aegis_root,
        autopilot_root=autopilot_root,
        dry_run=dry_run,
    )


def _remove_orphaned_empty(
    hooks_dir: Path,
    registered: set[Path],
    dry_run: bool,
) -> list[tuple[str, str, str]]:
    out: list[tuple[str, str, str]] = []
    if not hooks_dir.is_dir():
        return out
    for path in sorted(hooks_dir.glob("*.py")):
        if (
            path.stat().st_size == 0
            and path not in registered
            and path.name != "_common.py"
        ):
            if dry_run:
                out.append(("would-remove", str(path), ""))
            else:
                path.unlink()
                out.append(("removed", str(path), ""))
    return out


def repair(
    *,
    config: Path,
    aegis_root: Path,
    autopilot_root: Path,
    dry_run: bool = False,
) -> list[tuple[str, str, str]]:
    results = check(config=config, aegis_root=aegis_root, autopilot_root=autopilot_root)
    config_dir = config.parent
    hooks_dir = config_dir / "hooks"
    tests_dir = hooks_dir / "tests"

    hooks = _load_hooks(config)
    registered = {_resolve_target(c, config_dir) for c in _iter_commands(hooks)}

    out: list[tuple[str, str, str]] = []
    for verdict, target_str, detail in results:
        result = _repair_target(
            verdict,
            target_str,
            detail,
            tests_dir=tests_dir,
            registered=registered,
            hooks_dir=hooks_dir,
            aegis_root=aegis_root,
            autopilot_root=autopilot_root,
            dry_run=dry_run,
        )
        if result is not None:
            out.append(result)

    cleanup_hooks = _load_hooks(config)
    cleanup_registered = {
        _resolve_target(c, config_dir) for c in _iter_commands(cleanup_hooks)
    }
    out.extend(_remove_orphaned_empty(hooks_dir, cleanup_registered, dry_run))
    return out


def _default_config() -> Path:
    codex_home = os.environ.get("CODEX_HOME")
    if codex_home:
        return Path(codex_home) / "hooks.json"
    return Path.home() / ".codex" / "hooks.json"


def _default_aegis_root() -> Path:
    manifest = Path.home() / ".claude" / "plugins" / "installed_plugins.json"
    data = json.loads(manifest.read_text(encoding="utf-8"))
    return Path(data["plugins"]["aegis@buvis-plugins"][0]["installPath"])


def _default_autopilot_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="subcommand", required=True)
    check_parser = subparsers.add_parser("check")
    check_parser.add_argument("--config", type=Path)
    check_parser.add_argument("--aegis-root", type=Path)
    check_parser.add_argument("--autopilot-root", type=Path)
    repair_parser = subparsers.add_parser("repair")
    repair_parser.add_argument("--config", type=Path)
    repair_parser.add_argument("--aegis-root", type=Path)
    repair_parser.add_argument("--autopilot-root", type=Path)
    repair_parser.add_argument("--dry-run", action="store_true")
    return parser


def _resolve_roots(args: argparse.Namespace) -> tuple[Path, Path, Path]:
    config = args.config if args.config is not None else _default_config()
    if not config.exists():
        raise OSError(f"config not found: {config}")
    aegis_root = (
        args.aegis_root if args.aegis_root is not None else _default_aegis_root()
    )
    autopilot_root = (
        args.autopilot_root
        if args.autopilot_root is not None
        else _default_autopilot_root()
    )
    return config, aegis_root, autopilot_root


def _run_subcommand(
    args: argparse.Namespace,
    config: Path,
    aegis_root: Path,
    autopilot_root: Path,
) -> tuple[list[tuple[str, str, str]], list[tuple[str, str, str]]]:
    if args.subcommand == "repair":
        results = repair(
            config=config,
            aegis_root=aegis_root,
            autopilot_root=autopilot_root,
            dry_run=args.dry_run,
        )
        # Exit code reflects the post-repair state (identical to the
        # pre-repair state when --dry-run is set).
        verdicts = check(
            config=config, aegis_root=aegis_root, autopilot_root=autopilot_root
        )
        return results, verdicts
    results = check(config=config, aegis_root=aegis_root, autopilot_root=autopilot_root)
    return results, results


def _report(
    results: list[tuple[str, str, str]],
    verdicts: list[tuple[str, str, str]],
) -> int:
    ok = sum(1 for verdict, _, _ in verdicts if verdict == "ok")
    stale = sum(1 for verdict, _, _ in verdicts if verdict in ("stale", "no_canonical"))
    broken = sum(
        1
        for verdict, _, _ in verdicts
        if verdict in ("missing", "empty", "syntax_error")
    )

    for verdict, target, detail in results:
        print(f"{verdict}\t{target}\t{detail}")
    print(f"summary\t{ok} ok, {stale} stale, {broken} broken")

    if broken:
        return 1
    if stale:
        return 3
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    try:
        config, aegis_root, autopilot_root = _resolve_roots(args)
        results, verdicts = _run_subcommand(args, config, aegis_root, autopilot_root)
    except (
        OSError,
        json.JSONDecodeError,
        KeyError,
        TypeError,
        IndexError,
        ValueError,
        AttributeError,
    ) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    return _report(results, verdicts)


if __name__ == "__main__":
    sys.exit(main())

```

## Full current changed test file

```python
"""Target I/O regressions (PRD 00176) and interpreter-independent pins for
`_missing_common_import_names` (PRD 00173, added by review cycle 1).

The CLI-level null-byte test in test_codex_hook_doctor_extra.py discriminates
only on Python 3.10: from 3.11 a null byte raises SyntaxError, which the
pre-existing branch already caught, so that test stays green with or without
the `(ValueError, OSError)` widening this PRD added. Measured on this host —
`ast.parse("\\x00")` and `compile(b"\\x00", ...)` both raise ValueError on
3.10.20 and SyntaxError on 3.11.15, 3.12.13 and 3.13.13.

Faking the raise removes the interpreter from the equation: revert the widening
to `(UnicodeDecodeError, OSError)` and the bare ValueError escapes
`_missing_common_import_names`, failing this test on every Python.

`codex_hook_doctor` does a plain `import ast`, so `codex_hook_doctor.ast` is
the one shared module object — patching its `parse` wholesale would also break
pytest's own traceback rendering, which parses source to place carets. The
stub therefore raises only for this module's poison source and delegates every
other call to the real parser.

Lives in its own module because test_codex_hook_doctor_extra.py sits at 782 of
the project's 800-line file limit.
"""

from __future__ import annotations

import ast
import errno
import os
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from test_codex_hook_doctor import (
    _fake_roots,
    _run_cli,
    _write_config,
    codex_hook_doctor,
)
from test_codex_hook_doctor_repair import _run_repair_cli

_UNREADABLE = "unreadable (cannot verify _common imports)"
# Stands in for bytes the interpreter refuses; the stub keys off this exact text.
_POISON = "# parse of this source raises ValueError\n"


def test_bare_value_error_from_parse_marks_sibling_and_canonical_unreadable(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    hooks_dir = tmp_path / "hooks"
    hooks_dir.mkdir()
    (hooks_dir / "bad_sibling.py").write_text(_POISON, encoding="utf-8")
    canonical = tmp_path / "_common.py"
    canonical.write_text(_POISON, encoding="utf-8")

    real_parse = ast.parse

    def fake_parse(source: Any, *args: Any, **kwargs: Any) -> ast.AST:
        if source == _POISON:
            raise ValueError("source code string cannot contain null bytes")
        return real_parse(source, *args, **kwargs)

    monkeypatch.setattr(codex_hook_doctor.ast, "parse", fake_parse)

    assert codex_hook_doctor._missing_common_import_names(hooks_dir, canonical) == [
        f"bad_sibling.py: {_UNREADABLE}",
        f"_common.py: {_UNREADABLE}",
    ]


def test_check_directory_target_reports_error_and_remaining_rows(
    tmp_path: Path,
) -> None:
    hooks_dir = tmp_path / "hooks"
    hooks_dir.mkdir()
    bad = hooks_dir / "a_directory.py"
    bad.mkdir()
    good = hooks_dir / "z_good.py"
    good.write_text("X = 1\n", encoding="utf-8")
    config = tmp_path / "hooks.json"
    _write_config(config, {})  # Both targets must be discovered by glob.
    aegis_root, autopilot_root = _fake_roots(tmp_path)

    proc = _run_cli(
        [
            "--config",
            str(config),
            "--aegis-root",
            str(aegis_root),
            "--autopilot-root",
            str(autopilot_root),
        ]
    )

    assert proc.returncode == 1, proc.stderr
    rows = [line.split("\t") for line in proc.stdout.splitlines()]
    assert rows[0][:2] == ["syntax_error", str(bad)]
    assert "Is a directory" in rows[0][2]
    assert rows[1] == ["ok", str(good), ""]
    assert rows[2] == ["summary", "1 ok, 0 stale, 1 broken"]
    assert len(rows) == 3
    assert proc.stderr == ""


def test_target_deleted_between_exists_and_stat_is_verdicted(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    target = tmp_path / "gone.py"
    target.write_text("X = 1\n", encoding="utf-8")
    aegis_root, autopilot_root = _fake_roots(tmp_path)
    real_exists = Path.exists

    def disappearing_exists(path: Path) -> bool:
        exists = real_exists(path)
        if path == target and exists:
            path.unlink()
        return exists

    monkeypatch.setattr(Path, "exists", disappearing_exists)
    verdict, detail = codex_hook_doctor._verdict_for(target, aegis_root, autopilot_root)

    assert verdict == "syntax_error"
    assert "No such file or directory" in detail
    assert str(target) in detail


def test_staleness_uses_the_target_bytes_that_compiled(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    target = tmp_path / "protect_config.py"
    target.write_bytes(b"X = 1\n")
    aegis_root, autopilot_root = _fake_roots(tmp_path)
    (aegis_root / "hooks").mkdir()
    canonical = aegis_root / "hooks" / target.name
    canonical.write_bytes(b"X = 1\n")
    real_read = Path.read_bytes

    def disappearing_read(path: Path) -> bytes:
        data = real_read(path)
        if path == target:
            path.unlink()
        return data

    monkeypatch.setattr(Path, "read_bytes", disappearing_read)

    assert codex_hook_doctor._verdict_for(target, aegis_root, autopilot_root) == (
        "ok",
        "",
    )


@pytest.fixture
def unreadable_target(tmp_path: Path) -> Iterator[Path]:
    if os.geteuid() == 0:
        pytest.skip("root bypasses file permission bits")
    target = tmp_path / "unreadable.py"
    target.write_text("X = 1\n", encoding="utf-8")
    mode = target.stat().st_mode
    target.chmod(0)
    try:
        yield target
    finally:
        target.chmod(mode)


def test_unreadable_target_is_verdicted(unreadable_target: Path) -> None:
    verdict, detail = codex_hook_doctor._verdict_for(
        unreadable_target,
        unreadable_target.parent,
        unreadable_target.parent,
    )

    assert verdict == "syntax_error"
    assert "Permission denied" in detail
    assert str(unreadable_target) in detail


@pytest.fixture
def repair_targets(tmp_path: Path) -> tuple[Path, list[str]]:
    hooks_dir = tmp_path / "hooks"
    hooks_dir.mkdir()
    aegis_root, autopilot_root = _fake_roots(tmp_path)
    (aegis_root / "hooks").mkdir()
    names = ["protect_config.py", "validate_commit_msg.py"]
    for name in names:
        (hooks_dir / name).write_bytes(b"X = 1\n")
        (aegis_root / "hooks" / name).write_bytes(b"X = 2\n")
    config = tmp_path / "hooks.json"
    _write_config(config, {"PreToolUse": [f"python3 hooks/{name}" for name in names]})
    return hooks_dir, [
        "--config",
        str(config),
        "--aegis-root",
        str(aegis_root),
        "--autopilot-root",
        str(autopilot_root),
    ]


@pytest.fixture
def readonly_hooks(
    repair_targets: tuple[Path, list[str]],
) -> Iterator[tuple[Path, list[str]]]:
    if os.geteuid() == 0:
        pytest.skip("root bypasses directory permission bits")
    hooks_dir, _ = repair_targets
    mode = hooks_dir.stat().st_mode
    hooks_dir.chmod(0o555)
    try:
        yield repair_targets
    finally:
        hooks_dir.chmod(mode)


def test_readonly_repair_reports_all_targets_without_tmp_litter(
    readonly_hooks: tuple[Path, list[str]],
) -> None:
    hooks_dir, args = readonly_hooks

    proc = _run_repair_cli(args)

    assert proc.returncode == 3, proc.stderr
    rows = [line.split("\t") for line in proc.stdout.splitlines()]
    assert rows[0][:2] == ["unrepairable", str(hooks_dir / "protect_config.py")]
    assert "Permission denied" in rows[0][2]
    assert rows[1][:2] == ["unrepairable", str(hooks_dir / "validate_commit_msg.py")]
    assert "Permission denied" in rows[1][2]
    assert rows[2] == ["summary", "0 ok, 2 stale, 0 broken"]
    assert len(rows) == 3
    assert list(hooks_dir.glob("*.tmp")) == []
    assert (hooks_dir / "protect_config.py").read_bytes() == b"X = 1\n"
    assert (hooks_dir / "validate_commit_msg.py").read_bytes() == b"X = 1\n"
    assert proc.stderr == ""


@pytest.mark.parametrize("failure", ["partial_write", "replace"])
def test_failed_repair_cleans_tmp_and_repairs_next_target(
    repair_targets: tuple[Path, list[str]],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    failure: str,
) -> None:
    hooks_dir, args = repair_targets
    target = hooks_dir / "protect_config.py"
    temp = target.with_name(target.name + ".tmp")
    real_write = Path.write_bytes
    real_replace = os.replace
    error = OSError(errno.ENOSPC, "No space left on device", str(temp))

    def partial_write(path: Path, data: bytes) -> int:
        if path == temp:
            real_write(path, data[:1])
            raise error
        return real_write(path, data)

    def failed_replace(src: Path, dst: Path) -> None:
        if dst == target:
            raise error
        real_replace(src, dst)

    if failure == "partial_write":
        monkeypatch.setattr(Path, "write_bytes", partial_write)
    else:
        monkeypatch.setattr(codex_hook_doctor.os, "replace", failed_replace)

    assert codex_hook_doctor.main(["repair", *args]) == 3
    output = capsys.readouterr()
    rows = [line.split("\t") for line in output.out.splitlines()]
    assert rows[0] == ["unrepairable", str(target), str(error)]
    assert rows[1][:2] == ["repaired", str(hooks_dir / "validate_commit_msg.py")]
    assert rows[2] == ["summary", "1 ok, 1 stale, 0 broken"]
    assert len(rows) == 3
    assert list(hooks_dir.glob("*.tmp")) == []
    assert target.read_bytes() == b"X = 1\n"
    assert (hooks_dir / "validate_commit_msg.py").read_bytes() == b"X = 2\n"
    assert output.err == ""


def test_cleanup_failure_is_reported_without_losing_remaining_rows(
    repair_targets: tuple[Path, list[str]],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    hooks_dir, args = repair_targets
    target = hooks_dir / "protect_config.py"
    temp = target.with_name(target.name + ".tmp")
    real_replace = os.replace
    real_unlink = Path.unlink

    def failed_replace(src: Path, dst: Path) -> None:
        if dst == target:
            raise PermissionError(errno.EACCES, "replace denied", str(target))
        real_replace(src, dst)

    def failed_unlink(path: Path, missing_ok: bool = False) -> None:
        if path == temp:
            raise PermissionError(errno.EACCES, "cleanup denied", str(temp))
        real_unlink(path, missing_ok=missing_ok)

    monkeypatch.setattr(codex_hook_doctor.os, "replace", failed_replace)
    monkeypatch.setattr(Path, "unlink", failed_unlink)

    assert codex_hook_doctor.main(["repair", *args]) == 3
    output = capsys.readouterr()
    rows = [line.split("\t") for line in output.out.splitlines()]
    assert rows[0][:2] == ["unrepairable", str(target)]
    assert "replace denied" in rows[0][2]
    assert "temp cleanup failed:" in rows[0][2]
    assert "cleanup denied" in rows[0][2]
    assert rows[1][:2] == ["repaired", str(hooks_dir / "validate_commit_msg.py")]
    assert rows[2] == ["summary", "1 ok, 1 stale, 0 broken"]
    assert len(rows) == 3
    assert target.read_bytes() == b"X = 1\n"
    assert (hooks_dir / "validate_commit_msg.py").read_bytes() == b"X = 2\n"
    assert temp.read_bytes() == b"X = 2\n"
    assert output.err == ""

```

All review inputs are inlined because this static lane must not run commands. No edits, commits, branch changes, or autopilot invocation.
