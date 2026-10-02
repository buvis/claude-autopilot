# Close VERIFY findings through the final gate

## Overview

### Problem Statement

The full test suite runs up to three times per review cycle, for one cycle's
worth of evidence:

1. The tail sweep turns actionable Medium/Low findings into one `[D{cycle}]`
   task and dispatches `/autopilot:work`
   (`skills/run-autopilot/references/phase-review.md:180-184`).
2. That work pass runs its own mandatory step-7 full suite
   (`skills/work/SKILL.md:459`: "this step is mandatory and must not be
   skipped").
3. Composing the review file's `Tests:` line runs the suite again
   (`skills/review-work-completion/SKILL.md:329`: "run the project's test suite
   once in the FOREGROUND (or reuse the counts from a suite run already
   performed this cycle; do not run it twice)"). The reuse clause is prose with
   no mechanism behind it, so the reuse depends on the orchestrator remembering.

The root cause of the first duplication is that a **VERIFY** finding has no home
except a task. The doubt lens defines VERIFY as a finding that "needs a specific
named check to resolve" (`agents/eve.md:51`), but Phase 5 Classification
(`phase-review.md:100-127`) has no VERIFY row: the finding is auto-fixed,
researched, deferred or paused like any other, and an auto-fixable one becomes
an implementation task whose only content is "run this check". In the measured
batch that produced task 20, which ran the verification matrix, after which the
work skill correctly ran the same mandatory matrix again — 754 tests passing
twice for one answer.

### Target Users

The autopilot review loop, and the operator paying for a full suite run three
times per cycle on a large repo.

### Success Metrics

- A cycle whose findings are all VERIFY creates zero tasks and runs the suite
  once.
- Every VERIFY finding's named check appears in the phase report with its exact
  command and exit code — the evidence is preserved, only the execution is
  deduplicated.
- The review file's `Tests:` line is produced from a recorded run when one
  exists at the reviewed HEAD, and the reuse is decidable from a file rather
  than from memory.
- No lens is removed, skipped or narrowed: Alice, Blake, Bob, Carl and Eve run
  exactly as today, and the doubt rubric D1-D5 still requires every residual
  finding to land in exactly one of FIX/VERIFY/KNOWN.

## Functional Decomposition

### Capability: VERIFY routing

Give a "run this check" finding a destination that is not an implementation
task.

#### Feature: Verification-check queue
- **Description**: A per-cycle file holding the named checks the review wants
  run.
- **Inputs**: the VERIFY bucket of each doubt-lens reviewer's output
  (`agents/eve.md:61`, and Bob's identical contract).
- **Outputs**: `dev/local/reviews/{prd-stem}-checks-{cycle}.json` — a JSON array
  of `{"cycle": int, "finding": "<the finding text, verbatim>", "command": "<the exact check>", "source": "bob"|"eve"}`.
- **Behavior**: Written by the review skill's consolidation alongside the
  existing ledger write, using the Write tool (read, append, write back). A
  VERIFY finding whose text does not yield an exact runnable command is **not**
  queued — it stays a normal finding and follows today's classification, because
  rubric rule D3 already requires VERIFY items to name the exact check and a
  vague one is a rubric failure, not a queue entry.

#### Feature: Phase 5 VERIFY row
- **Description**: Classification gains one row that routes queued checks away
  from task creation.
- **Inputs**: the queue file for the current cycle.
- **Outputs**: no `task-add` call for those findings.
- **Behavior**: A finding present in the cycle's queue file is neither auto-fix
  nor research-then-decide nor defer: it is recorded in `autonomous_decisions`
  as routed-to-verification and excluded from both the follow-up task count and
  the tail-sweep selection. **A VERIFY finding never blocks convergence and
  never suppresses one**: convergence still requires no unresolved CRITICAL or
  HIGH, and a queued check that fails becomes a new finding in the next cycle
  through the normal path.

#### Feature: Queued checks run inside the final gate
- **Description**: The work phase's one mandatory verification run also runs the
  queued checks.
- **Inputs**: the queue file, if present, for the current `state.cycle`.
- **Outputs**: one report line per check —
  `verify_check: <command> -> exit <n>` — in the phase report, and the same
  lines appended to `dev/local/reviews/{prd-stem}-checks-{cycle}.json` as a
  `result` field on each entry.
- **Behavior**: `skills/work/SKILL.md` step 7 reads the queue after the suite
  commands and runs each queued command as its own Bash call. A non-zero exit is
  **not** a phase failure — it is evidence, reported and carried into the next
  review cycle as an open finding. Absent queue file: nothing runs and nothing
  is reported, so a first-pass build phase is unchanged.

### Capability: Suite-run reuse

Replace the prose reuse clause with a record.

#### Feature: Recorded verification result
- **Description**: The work phase writes what it ran, so the review can read it
  instead of re-running.
- **Inputs**: step 7's suite commands and their results.
- **Outputs**: `dev/local/autopilot/last-verification.json` —
  `{"sha": "<HEAD at the time of the run>", "cycle": <state.cycle or null>, "commands": [{"command": ..., "exit": ...}], "passed": int, "failed": int, "skipped": int}`,
  written with the Write tool.
- **Behavior**: Written at the end of step 7, replacing any prior content. The
  counts come from the runner's own summary line; a suite whose output carries
  no parseable counts records `null` for the three and the review falls back to
  running it. A phase that ran no suite writes the file with an empty `commands`
  array, which the reader treats the same as absent.

#### Feature: Review reads the record
- **Description**: The `Tests:` line is composed from the record when it matches
  the reviewed HEAD.
- **Inputs**: `last-verification.json` and the review's `head_sha`.
- **Outputs**: the `Tests: N passed, M failed, K skipped` line.
- **Behavior**: `skills/review-work-completion/SKILL.md` step 6 reads the file;
  if its `sha` equals the cycle's reviewed HEAD and its counts are non-null, the
  line is composed from it and **no suite runs**. Otherwise the suite runs in the
  foreground exactly as today, and the review file notes which of the two paths
  produced the line (fail loud — a stale reuse must never read as a fresh run).
  The `Tests: none (docs-only)` value is unchanged.

## Structural Decomposition

### Repository Structure

```
skills/run-autopilot/references/
└── phase-review.md                    # Maps to: Phase 5 VERIFY row
skills/review-work-completion/
├── SKILL.md                           # Maps to: Verification-check queue, Review reads the record
└── references/output-formats.md       # Queue file and Tests-line provenance
skills/work/
├── SKILL.md                           # Maps to: Queued checks, Recorded verification result
└── references/final-verification.md   # The procedure for both
```

### Module: verify-queue
- **Maps to capability**: VERIFY routing
- **Responsibility**: define the queue file's shape, its writer (review
  consolidation) and its reader (work step 7).
- **Exports**: none (prose + a JSON file contract)

### Module: review-prose
- **Maps to capability**: VERIFY routing, Suite-run reuse
- **Responsibility**: consolidation writes the queue; step 6 reads the
  verification record; Phase 5 gains the VERIFY row.
- **Exports**: none (prose)

### Module: work-prose
- **Maps to capability**: VERIFY routing, Suite-run reuse
- **Responsibility**: step 7 runs queued checks and writes the record.
- **Exports**: none (prose)

## Dependency Graph

### Foundation Layer (Phase 0)
No dependencies - built first.

- **verify-queue**: the two file contracts every other module reads or writes.

### Core Layer (Phase 1)
- **work-prose**: Depends on [verify-queue] - it reads the queue and writes the
  record.

### Integration Layer (Phase 2)
- **review-prose**: Depends on [verify-queue, work-prose] - it writes the queue
  the work phase reads and reads the record the work phase writes.

## Implementation Phases

### Phase 0: Foundation
**Goal**: Both file contracts are written down before anything reads them.

**Tasks**:
- [ ] Add a `## Verification-check queue` section to
      `skills/review-work-completion/references/output-formats.md` giving the
      queue filename pattern, the entry shape (with `result` as the optional
      field the work phase adds), the "no exact command means not queued" rule
      and the reader-tolerance rule (absent file = no checks, never an error)
      (no deps) - Acceptance:
      `rg -n "checks-\{cycle\}|Verification-check queue" skills/review-work-completion/references/output-formats.md`
      hits both.
- [ ] Add a `## Recorded verification result` section to
      `skills/work/references/final-verification.md` giving
      `last-verification.json`'s shape, its single writer (step 7), its single
      reader (review step 6), the null-counts fallback and the empty-commands
      case (no deps) - Acceptance:
      `rg -n "last-verification.json" skills/work/references/final-verification.md`
      hits.

**Exit Criteria**: Both contracts are readable standalone; nothing reads or writes them yet.

### Phase 1: Core
**Goal**: The work phase runs queued checks and records what it ran.

**Tasks**:
- [ ] Add a `## Queued verification checks` section to
      `skills/work/references/final-verification.md`: read
      `dev/local/reviews/{prd-stem}-checks-{cycle}.json` after the suite
      commands, run each `command` as its own Bash call, append its `result`,
      and emit one `verify_check: <command> -> exit <n>` report line per entry;
      a non-zero exit is evidence, not a phase failure (depends on: Phase 0) -
      Acceptance: `rg -n "verify_check" skills/work/references/final-verification.md`
      hits.
- [ ] Edit `skills/work/SKILL.md` step 7 to point at both new sections and to
      state that step 7 writes `last-verification.json` before reporting
      (depends on: Phase 1 task 1) - Acceptance:
      `rg -n "last-verification.json|verify_check" skills/work/SKILL.md` hits
      both;
      `uv run --no-project --with pytest python -m pytest -q skills/work/scripts/test_dispatch_prose.py`
      green, its SKILL.md line-ceiling test included.

**Exit Criteria**: A work phase with a queue file present runs each queued check exactly once and reports its exit code.

### Phase 2: Integration
**Goal**: The review writes the queue and stops re-running the suite.

**Tasks**:
- [ ] Edit `skills/review-work-completion/SKILL.md` step 6: write the queue file
      from the doubt lenses' VERIFY buckets alongside the existing ledger write,
      and compose the `Tests:` line from `last-verification.json` when its `sha`
      matches the reviewed HEAD and its counts are non-null, otherwise run the
      suite as today and note in the review file which path produced the line
      (depends on: Phase 1) - Acceptance:
      `rg -n "checks-|last-verification.json" skills/review-work-completion/SKILL.md`
      hits both;
      `uv run --no-project --with pytest python -m pytest -q skills/run-autopilot/scripts/test_review_prompt_contracts.py`
      green.
- [ ] Add the VERIFY row to Phase 5 Classification in
      `skills/run-autopilot/references/phase-review.md`: a finding present in the
      cycle's queue file is recorded in `autonomous_decisions` as routed to
      verification, creates no task, and is excluded from the follow-up count
      and from the tail sweep's selection; state explicitly that this changes
      neither the convergence test nor any lens (depends on: Phase 2 task 1) -
      Acceptance:
      `rg -n "routed to verification|checks-" skills/run-autopilot/references/phase-review.md`
      hits;
      `uv run --no-project --with pytest python -m pytest -q skills/run-autopilot/scripts/test_autopilot_lifecycle.py`
      green.
- [ ] Add the CHANGELOG entries (`feat` commit: `**review-work-completion**`
      under Changed for the verification-check queue and the reused `Tests:`
      counts; `**work**` under Added for queued-check execution and the recorded
      verification result) (depends on: Phase 2 task 2) - Acceptance:
      `rg -n "^- \*\*(work|review-work-completion)\*\*" CHANGELOG.md` hits under
      `[Unreleased]`.

**Exit Criteria**: A cycle whose only findings are VERIFY items creates zero tasks and runs the suite once.

## Test Strategy

### Critical Scenarios
- **Happy path**: cycle 1 yields two VERIFY findings with exact commands → both
  queued, zero tasks created, the rework work phase runs the suite once plus the
  two commands, and the phase report carries two `verify_check:` lines.
- **Edge case**: a VERIFY finding whose text names no exact command → not
  queued, classified as today, and rubric rule D3 records the fail.
- **Edge case**: a queued check exits non-zero → reported, phase still
  completes, and the failure reaches the next cycle as an open finding.
- **Error case**: `last-verification.json` carries a `sha` older than the
  reviewed HEAD → the review runs the suite itself and says so in the review
  file.

## Risks

- **A check that never runs.** The queue is read by the one mandatory step every
  work phase performs, and an absent queue file is an ordinary no-op; the risk
  case is a review cycle that queues checks and then converges without a rework
  pass, so the Phase 5 VERIFY row must record the routing in
  `autonomous_decisions` — the record is what makes an unrun check visible in
  the batch report rather than silently dropped.
- **A stale reuse reports green over changed code.** The reuse is gated on an
  exact `sha` match against the reviewed HEAD, and the review file names which
  path produced the counts.
- **Perceived thinning of the review.** Nothing is removed: every lens runs
  every cycle, the doubt rubric is untouched, and a VERIFY finding's named check
  still runs with its exit code recorded. Only the duplicate execution is
  removed.
