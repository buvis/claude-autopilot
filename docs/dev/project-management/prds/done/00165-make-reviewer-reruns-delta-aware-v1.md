# Make reviewer reruns delta-aware

## Overview

### Problem Statement

Every per-task reviewer re-run re-reads the entire task diff. `skills/work/SKILL.md`
step 5.7 renders Pat's prompt with `--set-cmd DIFF="git diff BASE_SHA..HEAD_SHA"`
where `BASE_SHA` is the parent of the task's test commit, and
`skills/work/references/per-task-review.md:28` closes the loop on a finding with
"Re-commit (step 5), re-verify (step 5.5), re-review". The base never moves, so
cycle 2 ships cycle 1's diff plus the fix, and cycle 3 ships all of it again.

Measured: a task-19 Pat prompt of about 369 KB, dispatched twice, the second run
re-reading thousands of unchanged mechanical test moves to check a small feedback
patch (batch feedback 2026-08-27).

The pack already solves this for one reviewer. Bob's codex lane passes
`--resume-thread` so he "verifies fixes against his own cycle-1 critique instead
of re-reviewing from zero"
(`skills/review-work-completion/references/agent-invocation.md:38-45`). Pat has
no equivalent, because `sonnet-run.sh` supports `-r/--resume` only in an
interactive mode that drops `--print` and takes no prompt file
(`skills/use-sonnet/scripts/sonnet-run.sh:110-111,152-156`), and it never emits a
session id.

`claude` itself supports both halves: `--session-id <uuid>` fixes the id of a new
session and `-r/--resume <id>` resumes one, both usable with `--print`.

### Target Users

The autopilot work phase, on any task whose per-task review raises a finding —
the second and third dispatch are the ones this cuts.

### Success Metrics

- A Pat re-run's prompt carries only the delta diff and the prior findings, not
  the full task diff. Target: a re-run prompt under 10% of the first dispatch's
  byte count on a task whose fix touches one file.
- The first dispatch's byte count and argv are unchanged from today.
- Coverage is preserved: the re-run judges within the same conversation that
  produced the findings, so the earlier diff is still in the reviewer's context.
- A resume that fails degrades to today's full-diff dispatch with a loud note,
  never to a skipped review.

## Functional Decomposition

### Capability: Resumable sonnet runner

Give `sonnet-run.sh` the two flags the delta lane needs.

#### Feature: Fixed session id on dispatch
- **Description**: `-S, --session-id UUID` passes `--session-id UUID` through to
  `claude` in print mode.
- **Inputs**: a UUID string.
- **Outputs**: the pair `--session-id <uuid>` in the child argv, in `--print`
  mode.
- **Behavior**: Absent `-S`, the argv is byte-identical to today (the exact-argv
  lock in `test_sonnet_run.sh` stays green). `-S` with no value is a usage error
  on stderr, exit non-zero, no dispatch. A malformed UUID is passed through
  unchanged — `claude` owns that validation, and duplicating it here would drift.

#### Feature: Print-mode resume
- **Description**: `-R, --resume-print ID` dispatches `claude --print --resume ID`
  with the prompt from `-f`.
- **Inputs**: a session id, plus the existing `-f` prompt file and `-o` output
  file.
- **Outputs**: the child argv `claude --print --model ... --resume <id> ... <prompt>`,
  with stdin guarded by `< /dev/null` exactly as the existing print path does.
- **Behavior**: A separate flag from the existing interactive `-r/--resume`,
  which is left untouched — `-r` sets `MODE=resume` and deliberately runs without
  `--print`, and overloading it would change an existing interactive contract.
  `-R` and `-r` together is a usage error. A resume whose session no longer
  exists exits non-zero, which the caller treats as a runner failure.

### Capability: Delta re-review

Send the reviewer what changed, not what he already read.

#### Feature: Per-task reviewer session id
- **Description**: Each task's first Pat dispatch fixes a session id the re-runs
  resume.
- **Inputs**: `uuidgen` run once per task at step 5.7.
- **Outputs**: `<pat_session_id>` held in-session for the task's review cycles.
- **Behavior**: The first dispatch passes `-S <pat_session_id>` and is otherwise
  unchanged — same prompt, same full diff, same render. The id is task-scoped and
  is not persisted: a re-run only ever happens inside the same task in the same
  session, and a session that dies takes the task's review cycle with it.

#### Feature: Delta re-run prompt
- **Description**: A second template carrying only what changed.
- **Inputs**: `<last_reviewed_sha>` (HEAD at the previous Pat dispatch), the
  confirmed findings sent to the fixer, and current HEAD.
- **Outputs**: `dev/local/tmp/review-task-<id>-rerun-<n>.md`, rendered from
  `skills/work/references/pat-rerun-prompt.md`.
- **Behavior**: The template holds three placeholders — `{PRIOR_FINDINGS}` (the
  findings the fixer was asked to address, verbatim, one per line),
  `{DELTA_DIFF}` (`git diff <last_reviewed_sha>..HEAD`) and
  `{UNCHANGED_NOTE}` (the literal sentence naming the earlier range as already
  reviewed in this same conversation) — plus a fixed instruction: judge whether
  each prior finding is resolved by the delta, and report new findings only from
  the delta. The reporting contract is unchanged, so the existing result ladder
  and any output parser consume it without modification. `<last_reviewed_sha>`
  advances to the HEAD of each dispatch, so cycle 3's delta is cycle 2's fix
  alone.

#### Feature: Resume-failure fallback
- **Description**: A failed resume never costs the review.
- **Inputs**: the runner's exit code and output file.
- **Outputs**: one full-diff dispatch, and `review` on the attempt record gaining
  a `resume_failed` note.
- **Behavior**: A non-zero exit or an empty output file from a `-R` dispatch
  re-dispatches once with today's full-diff prompt and no `-R`, and the phase
  report names the fallback (fail loud). This consumes the same single retry the
  existing runner-failure row grants — it does not add a dispatch budget.

## Structural Decomposition

### Repository Structure

```
skills/use-sonnet/scripts/
├── sonnet-run.sh                          # Maps to: Resumable sonnet runner
└── test_sonnet_run.sh                     # Flag tests
skills/work/
├── SKILL.md                               # Maps to: Per-task reviewer session id
└── references/
    ├── pat-rerun-prompt.md                # Maps to: Delta re-run prompt
    └── per-task-review.md                 # Maps to: Delta re-review, Resume-failure fallback
```

### Module: sonnet-runner
- **Maps to capability**: Resumable sonnet runner
- **Responsibility**: the two new flags and their argv shapes; nothing else in
  the script changes.
- **Exports**: CLI flags `-S, --session-id UUID` and `-R, --resume-print ID`

### Module: pat-rerun-template
- **Maps to capability**: Delta re-review
- **Responsibility**: the re-run prompt body and its three placeholders.
- **Exports**: `references/pat-rerun-prompt.md` (rendered by `render_prompt.py`)

### Module: work-prose
- **Maps to capability**: Delta re-review
- **Responsibility**: step 5.7's session-id capture; the re-run dispatch,
  `<last_reviewed_sha>` bookkeeping and the fallback row in
  `references/per-task-review.md`.
- **Exports**: none (prose)

## Dependency Graph

### Foundation Layer (Phase 0)
No dependencies - built first.

- **sonnet-runner**: the flags every later step dispatches through.
- **pat-rerun-template**: the prompt body; nothing runs it yet.

### Core Layer (Phase 1)
- **work-prose**: Depends on [sonnet-runner, pat-rerun-template] - it names both
  flags and every placeholder.

### Integration Layer (Phase 2)
No integration module - Phase 2 is documentation and pins.

## Implementation Phases

### Phase 0: Foundation
**Goal**: The runner can fix and resume a session in print mode; the template exists.

**Tasks**:
- [x] Add `-S, --session-id UUID` and `-R, --resume-print ID` to
      `skills/use-sonnet/scripts/sonnet-run.sh` (both apply to the `--print`
      dispatch path only; `-R` with `-r` is a usage error) and cases to
      `test_sonnet_run.sh`: `-S <uuid>` yields the argv pair `--session-id`
      `<uuid>`; `-R <id>` yields `--print` and `--resume` `<id>`; `-S` with no
      value exits non-zero with no claude invocation; `-R` with no value exits
      non-zero; `-R` plus `-r` exits non-zero; absent both, the argv is
      byte-identical to the existing exact-argv lock (no deps) - Acceptance:
      `bash skills/use-sonnet/scripts/test_sonnet_run.sh` prints `0 failed`.
- [x] Write `skills/work/references/pat-rerun-prompt.md` with the placeholders
      `{PRIOR_FINDINGS}`, `{DELTA_DIFF}` and `{UNCHANGED_NOTE}`, the judge-the
      -delta instruction, and a pointer stating the reporting contract is
      `agents/pat.md`'s and unchanged (no deps) - Acceptance:
      `rg -n "PRIOR_FINDINGS|DELTA_DIFF|UNCHANGED_NOTE" skills/work/references/pat-rerun-prompt.md`
      hits all three; `python3 skills/work/scripts/render_prompt.py skills/work/references/pat-rerun-prompt.md --out /dev/null`
      exits 1 naming the first unfilled placeholder.

**Exit Criteria**: `sonnet-run.sh -S <uuid> -f x -o y` and `-R <id> -f x -o y` produce the documented argv.

### Phase 1: Core
**Goal**: Pat's re-runs carry the delta.

**Tasks**:
- [x] Edit `skills/work/SKILL.md` step 5.7: generate `<pat_session_id>` with
      `uuidgen` before the first dispatch of a task, hold `<last_reviewed_sha>` =
      the HEAD of each dispatch, and point at
      `references/per-task-review.md` for the re-run procedure. The first
      dispatch's render block is unchanged apart from the `-S` flag on the runner
      command (depends on: Phase 0) - Acceptance:
      `rg -n "pat_session_id|last_reviewed_sha" skills/work/SKILL.md` hits both;
      `uv run --no-project --with pytest python -m pytest -q skills/work/scripts/test_dispatch_prose.py`
      green, its SKILL.md line-ceiling test included.
- [x] Rewrite `## Dispatch` and extend `## Result handling` in
      `skills/work/references/per-task-review.md`: the first dispatch adds
      `-S "<pat_session_id>"`; every re-run renders `pat-rerun-prompt.md` and
      dispatches with `-R "<pat_session_id>"`; add a `## Resume failure` row
      giving the single full-diff fallback dispatch and the `resume_failed`
      report note (depends on: Phase 1 task 1) - Acceptance:
      `rg -n '\-S "|\-R "|resume_failed' skills/work/references/per-task-review.md`
      hits all three.

**Exit Criteria**: A task whose review raises one HIGH dispatches a re-run whose prompt contains only the fix's diff.

### Phase 2: Integration
**Goal**: The behavior is documented and pinned.

**Tasks**:
- [x] Enumerate the `resume_failed` note in the `review` field semantics of
      `skills/work/references/attempt-logging.md`; add prose pins to
      `skills/work/scripts/test_dispatch_prose.py` (SKILL.md names
      `pat_session_id`; `per-task-review.md` names `-R` and `resume_failed`;
      `pat-rerun-prompt.md` names all three placeholders); add the CHANGELOG
      entries (`feat` commit: `**use-sonnet**` under Added for `-S`/`-R`;
      `**work**` under Changed for delta-aware per-task review re-runs) (depends
      on: Phase 1) - Acceptance:
      `rg -n "resume_failed" skills/work/references/attempt-logging.md` hits;
      `uv run --no-project --with pytest python -m pytest -q skills/work/scripts/test_dispatch_prose.py`
      green; `rg -n "^- \*\*(work|use-sonnet)\*\*" CHANGELOG.md` hits under
      `[Unreleased]`.

**Exit Criteria**: The prose suite pins every new flag and placeholder.

## Test Strategy

### Critical Scenarios
- **Happy path**: task 19's review raises one HIGH; the fix touches one file; the
  re-run prompt carries that file's diff plus one prior-finding line, and Pat
  answers from the resumed conversation.
- **Edge case**: three review cycles → each delta is the previous cycle's fix
  alone, never the accumulated range.
- **Edge case**: `NO FINDINGS` on the first dispatch → no re-run, no resume, and
  the lane is byte-identical to today.
- **Error case**: the session id no longer resolves → `-R` exits non-zero, one
  full-diff dispatch follows, and the phase report names the fallback.

## Risks

- **A resumed reviewer trusts a stale memory of the code.** The delta prompt
  states the range already reviewed and asks for a verdict on each prior finding
  against the new diff; the PRD-level lenses re-review the whole change every
  cycle regardless, so a missed regression in the earlier range is caught there.
- **Session persistence is not guaranteed.** `--no-session-persistence` is never
  passed by this lane, and the fallback converts any resume failure into today's
  behavior at the cost of one dispatch.
- **PRD 00159 also edits step 5.7 and `per-task-review.md`.** It adds `-t ""`,
  `{VERIFICATION_RESULT}` and the output parser; this PRD adds `-S`/`-R` and the
  re-run template. They touch the same files but different lines. Land 00159
  first; this PRD's edits then compose (the re-run dispatch also carries
  `-t ""`).
- **`uuidgen` availability.** It ships with macOS and util-linux; if a host
  lacks it, `python3 -c "import uuid,sys;sys.stdout.write(str(uuid.uuid4()))"` is
  the documented substitute, and a failure to produce an id simply means no `-S`
  is passed and the lane behaves exactly as today.
