# Add A Premise Gate To The Autopilot Drain

> Source: hold-triage session 2026-08-23 (operator decision; `~/.claude` project memory
> `project_hold_triage_2026_08_23`). Class evidence: five premise-park bounces this
> month (00093 twice, 00110 twice, 00119), each burning a session to re-discover a
> fact a one-line shell check could answer, then evicting the PRD to `hold/` where a
> human must notice the evidence landed.
>
> **Key decided 2026-08-26 (backlog review, operator decision):** the frontmatter key is
> `eligibility:`, not `premise:`, so it cannot be read as the task-level `Premise:` line
> whose failure stalls a PRD (this gate skips). "Premise gate" stays the feature's name.
> `hold/00110`'s stamped line was re-keyed the same day; its command is still the draft
> Phase 2 pins. Also that day this PRD moved from `~/.claude` into the plugin repo, so
> the check runs from whatever project the drain serves, never from `~/.claude`, and the
> batch that builds it runs the installed plugin cache, so the end-to-end proof is a
> subprocess pick test plus a hand-run drain after release.

## Overview

### Problem Statement

Blocked-on-evidence PRDs have no machine-checkable eligibility. The drain picks
them, spends a session re-verifying prose premises (a cheap check still costs a
session; 00029's full evaluation cost a measured $53.63 on 2026-08-18), then parks
them to `hold/`, which autopilot never reads - so every unblock needs a human to
notice and `mv` the file back. `~/.claude/rules/ai-app-design.md`: deterministic
checks belong in code, not model sessions.

### Target Users

The solo operator (no more hold-triage sessions for evidence-shaped blocks) and
the autopilot drain (skips ineligible PRDs for pennies instead of sessions).

### Success Metrics

- A PRD may declare `eligibility:` in frontmatter: one shell command, run with cwd =
  the project root (the directory holding `dev/local/`, resolved from `--state` the
  way `cli/__main__.py` resolves `--prds`) with a hard timeout; exit 0 = eligible.
- A failing check SKIPS the PRD: it stays in `backlog/`, is never parked to
  `hold/`, gets no session, and the drain proceeds to the next candidate.
- Every skip is recorded (prd, command, exit code) in state and the batch report,
  so an all-skipped drain renders as "N skipped", never as a silent 0-done batch.
- A PRD without `eligibility:` behaves exactly as today (regression-tested).
- Evaluation never dispatches an agent or launches a session: wrapper-side
  subprocess or one in-session Bash call (design decides; constraints in Risks).
- Error or timeout of the command counts as unmet (skip) and is recorded -
  fail toward not-running, never toward park or crash.
- The one real fixture, `hold/00110`, carries a deterministic check (rewritten in
  Phase 2: the draft stamped 2026-08-25 counts review files whose frontmatter
  carries `consensus_run_id` and whose Alice section records `no verdict
  divergence`, excluding `00110-*`; it matches 0 files in this repo today - the
  00136 reviews it was drafted against stayed in `~/.claude` - so it exits 1) that
  exits non-zero against today's reality and zero under a synthetic met condition.
  A subprocess test over a temp project tree proves the pick: an unmet-check PRD
  with the lower number is skipped and a met-check PRD with the higher number is
  selected.
- All existing run-autopilot contract suites stay green.

### Non-Goals

- No change to `hold/` semantics: human parks and machine stalls stay as they are.
- No DSL: one shell command, exit code only.
- No retroactive stamping beyond the named hold PRD.
- Not a scheduler: checks are evaluated only when a drain considers the PRD.

## Functional Decomposition

### Capability: Eligibility check in code

#### Feature: eligibility frontmatter contract
- **Description**: parse `eligibility:` from PRD frontmatter at pick time; absent =
  eligible.
- **Behavior**: value is a single shell command string; documented convention:
  read-only checks only; cwd = the project root (above); default timeout 30s.
  Naming: `/work` already verifies a task-level `Premise:` line before dispatching
  an implementor (`work/SKILL.md:237`, copied verbatim by `/plan-tasks`
  `SKILL.md:125-132`), and its failure semantics are STALL, not skip - hence the
  distinct key; cross-link both in `phase-build.md:184`. Unknown frontmatter keys
  are silently ignored today (`cli/frontmatter.py:114-140`; recognized keys at
  `:38-56`), which is why 00110's stamped line is inert rather than an error.

#### Feature: skip-not-park pick loop
- **Description**: candidate iteration evaluates the check before any session or
  task planning; unmet -> log skip, continue in order; the PRD file is untouched.
- **Behavior**: skips recorded via statectl under `state.batch.skips[]`
  (batch-scoped, so `records.PER_PRD_RESET_FIELDS` does not wipe them; added to
  `schema._LIST_FIELDS`, `cli/schema.py:55-62`) and rendered in the batch
  report as a Skipped section (prd, exit code, command) plus a `PRDs skipped:
  N` line in `batch_summary` - `render_report.py` has no skipped surface today
  (`:5-15`), and `batch_summary` (`:383`) counts only completed PRDs, so
  the goldens `cli/golden/expected/report-section.md` /
  `report-summary.md` and `test_doc_contract.py` change with it.

### Capability: Real fixtures

#### Feature: eligibility line on the live hold PRD
- **Description**: rewrite the draft check stamped on 00110 into a
  deterministic check of its real unpark condition (at least 3 review files
  under `dev/local/reviews/` whose frontmatter carries `consensus_run_id` and
  whose Alice section records a converged shadow with no divergence, excluding
  00110's own satellites) - the 2026-08-23 line counted files containing a
  string, including 00110's own evidence file, and `dev/local/tmp` is GC'd.
  It is the complete fixture set: the cartographer pair (00029/00114) was
  cancelled 2026-08-23, and 00113 (`~/.claude`'s `hold/`) carries no check
  (rescoped 2026-08-23, held 2026-08-25 behind PRD 00143).
- **Behavior**: the fixture proven both ways in tests - non-zero against
  today's reality, zero under a synthetic met condition (fixture dir/file).

## Implementation Phases

### Phase 0: Locate the pick
Grounded 2026-08-25 and re-verified 2026-08-26; no task of its own - the facts ride
as the `Premise:` on Phase 1's task, and the design phase (Phase 1.5 runs; no
`design: skip`) writes the insertion-point note. Selection is the pure
`select(wip, backlog)` in `cli/selection.py:50-64`, called only by the
`autopilot select` verb (`cli/__main__.py:382-395`), invoked from
`references/phase-build.md:60`; `cli/loop.py` has no selection code. Anchoring
tests: `cli/test_selection.py` (incl. the signature assertion at `:98`),
`cli/test_lifecycle_cli.py::SelectTests` (`:79-131`), and the `migration_map.md`
rows `prd-selection-lowest-sequence` / `prd-selection-never-scans-hold`. Ordering
constraint: Phase 0 writes `state.prd` before the frontmatter call
(`phase-build.md:70, 86-88`), so the gate evaluates at pick time, before any
frontmatter machinery exists for the new PRD.

### Phase 1: Gate
**Tasks**:
- [ ] Implement `eligibility:` parse + evaluate + skip-not-park + statectl/report
  plumbing. Premise: selection is still `select()` in `cli/selection.py`, called
  only from `cli/__main__.py` `_run_select` and `phase-build.md` step 2;
  `cli/loop.py` still has no selection code; `cli/frontmatter.py` still ignores
  unknown keys - re-verify with `rg` before editing and stop and report if any
  moved. Acceptance: unit tests for met, unmet, error, timeout, absent; skip
  visible in a rendered report fixture; no-eligibility PRDs untouched
  (regression test).

### Phase 2: Fixtures and pick proof
**Tasks**:
- [ ] Rewrite 00110's `eligibility:` command as the deterministic fixture described
  in the Real fixtures capability, proven both directions (depends on: Phase 1).
  Acceptance: tests pin it; a subprocess test runs the checkout's
  `python3 skills/run-autopilot/cli/__main__.py select --prds <tmp>/dev/local/prds`
  over a temp project tree whose `backlog/` holds an unmet-check PRD with the
  lower number and a met-check PRD with the higher number (state at
  `<tmp>/dev/local/autopilot/state.json`): stdout `prd` names the met one,
  `state.batch.skips[]` holds exactly one entry naming the unmet one with its
  exit code, exit 0.

**Exit Criteria**: all Success Metrics green; 00110 stays in `hold/` with its
rewritten check until the gate finds it met (its header says so); 00113 is held
in `~/.claude` on its own terms (PRD 00143) and is not this PRD's concern.
Post-release signal (not judged in-session): the first released drain over a
backlog holding an unmet-check PRD renders it under Skipped instead of parking it.

## Test Strategy

Contract tests over pick behavior (skip-not-park is the regression surface);
the fixture check fails-first both directions; one subprocess pick test over a
temp tree; report rendering pinned by a golden that includes a Skipped section.

## Risks

- **Executable frontmatter**: the commands are PRD-authored and run
  unattended. Mitigations: read-only convention documented at the contract,
  hard timeout, failure = skip (never park or crash). If run in-session via the
  Bash tool, pipes break permission-prefix matching (`~/.claude/rules/tools.md`)
  and warden asks become denies unattended (WARDEN_UNATTENDED), which fails safe
  to skip; if run wrapper-side via subprocess, warden never sees it - the design
  must pick one and say which.
- **Frontmatter authority**: Phase 0 re-parses frontmatter and silently overrides
  state (`~/.claude` project memory `reference_prd_frontmatter_overrides_state`);
  handling must live on the frontmatter side of that boundary or be re-derived
  per session.
- **Silent-skip drift**: an all-skipped batch must render as skips, not reproduce
  the known "0 done / session died" false alarm (`~/.claude` project memory
  `project_autoclaude_drained_reports_died`).
- **No in-batch end-to-end proof**: the batch runs the installed plugin cache, not
  this checkout, so a live drain from inside a session cannot exercise the gate
  (and nesting a drain in a session is a hang risk). The subprocess pick test is
  the in-session proof; the real drain is a hand-run smoke after release.
