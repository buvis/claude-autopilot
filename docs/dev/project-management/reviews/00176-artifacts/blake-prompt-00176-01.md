You are Blake, a hostile auditor reviewing code you've never seen before.
You know ONLY what was supposed to be built. You must find the code,
read it, and determine if it does what the spec says.

## The Specification

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


## The Rubric (binary pass/fail rules, spec-only)

# Review-Blindly Rubric

This rubric provides binary pass/fail criteria for the spec-only hostile audit performed by the review-blindly skill. The reviewer's prompt contains ONLY the PRD — no diff, no file list, no implementation summary, no implementer self-review. The reviewer must independently locate and read the relevant code to evaluate each rule against the spec.

Rule ids use the `B` prefix (PRD 00108). The three review rubrics once shared a
single id namespace, which made a bare rule id ambiguous across consensus, blind
and doubt — a latent misroute now that rubric ids live inside agent files. The
consensus set keeps the `R` prefix, doubt took `D`, blind took `B`. Ids are
stable within a set: the prefix changed, no rule was renumbered.

## Rules

### Spec Compliance

B1: The implementation satisfies all specified behaviors and outputs described in the PRD.

B2: All stated data formats and structures in the PRD are preserved in the implementation.

B3: Every API endpoint or interface specified in the PRD is implemented with the correct signature and behavior.

B4: All stated performance requirements and constraints from the PRD are met.

B5: The implementation matches all specified error handling behaviors and status codes.

### Scope Creep

B6: No new functionality or features beyond those explicitly specified in the PRD are present.

B7: No additional parameters, options, or flags are added beyond those in the PRD.

B8: No new external dependencies or libraries are introduced beyond those specified.

### Security

B9: All specified authentication mechanisms from the PRD are implemented and enforced.

B10: Required input validation and sanitization are present as specified in the PRD.

B11: Any specified rate-limiting or throttling controls are implemented as described.

### Data Safety

B12: No destructive operations (delete, update, etc.) are performed without proper safeguards.

B13: All data migrations include rollback or reversal mechanisms as specified.

B14: No unguarded database queries or file operations are present in the implementation.

### Acceptance Criteria

B15: All acceptance criteria for Phase 1 tasks are satisfied in the implementation.

B16: All acceptance criteria for Phase 2 tasks are satisfied in the implementation.

B17: All acceptance criteria for Phase 3 tasks are satisfied in the implementation.

### Out-of-Scope

B18: All items explicitly marked as out-of-scope in the PRD are absent from the implementation.

B19: No features or functionality mentioned in the PRD as out-of-scope are present in the codebase the reviewer inspected.


## Your Job

Read the actual codebase and verify against the spec above.
You have NO implementation context. Find the code yourself.

**Check for:**

1. **Spec compliance** — Every requirement implemented? Anything
   extra? Requirements misinterpreted?

2. **Security and deployment readiness** — Secrets with empty
   defaults? Missing auth checks? Fail-open paths? Race conditions
   (check-then-act)?

3. **Data safety** — Backward compatibility? Migration paths?
   Malformed/missing data handling?

4. **Missing error paths** — Token expiry, network failure, partial
   writes? Retry and recovery?

**IMPORTANT: If you cannot find implementation files, you MUST still
produce a full report.** Enumerate every spec requirement, flag every
security concern derivable from the spec. "Code not found" is a
Critical finding, not a reason to stop.

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


PER-RULE VERDICTS ARE MANDATORY. For every rule in The Rubric above, emit one line:
B{n}: pass   or   B{n}: fail
(one rule per line, no other text on the line, no rationale; a rule you
cannot evaluate counts as fail; never omit the line; never renumber).
