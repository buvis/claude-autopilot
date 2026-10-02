# Enforce style limits at the task boundary

## Overview

### Problem Statement

The style-limit gate runs once, after every task in the phase is done
(`skills/work/SKILL.md` step 7.0, base `state.work_start_sha..HEAD`). Twelve
tasks of oversize therefore accumulate before anything measures them, and the
repair lands as one mechanical 15-file, ~5K-line split with none of the context
that produced it (batch feedback 2026-08-27).

The repair is also boxed in. Step 7.0's fix dispatch re-renders `ivan.md` through
`references/gate-failure.md:136-144`, which re-passes `FILE_PATHS` **exactly as
the step-3 dispatch did** — the task's own Contract paths. `agents/ivan.md:24`
says: "Read only the files listed above. If a file or symbol you need is not
listed, stop and report it as a blocker." Splitting an 800-line file requires
new sibling modules that are by construction absent from that list, so the fixer
can only report a blocker or cram the split into files that are already too big.

### Target Users

The autopilot loop draining a multi-task PRD, and the operator who otherwise
receives one giant mechanical-split commit at the end of a build phase.

### Success Metrics

- The gate runs once per non-haiku task, with the task's own diff as its base —
  measured by a per-task `style_gate:` value on every attempt record.
- A phase whose tasks each stay under the limits performs zero style-fix
  dispatches, exactly as today.
- A style-fix dispatch can create new modules: a task whose only violation is an
  850-line file resolves without an Ivan blocker report.
- `skills/work/scripts/test_dispatch_prose.py` stays green, its SKILL.md
  line-ceiling test included.

## Functional Decomposition

### Capability: Task-scoped style gate

Move the measurement to where the context still exists.

#### Feature: Per-task gate invocation
- **Description**: The style-limit gate runs at the end of each task instead of
  at the end of the phase.
- **Inputs**: `<task_base_sha>` (the HEAD captured immediately after step 2's
  `task-start`) and current HEAD.
- **Outputs**: `dev/local/tmp/task-diff-<task-id>.txt`, the candidate `.py`
  list, and a `style_gate` value on that task's attempt record.
- **Behavior**: A new step 5.65 runs between step 5.6 (self-deslop) and step 5.7
  (per-task review), so the reviewer reads an already-conforming diff. The diff
  is built exactly as PRD 00162 specifies (committed range plus a
  `--no-index` block per untracked `.py` file). Same tier gate as step 5.7:
  `haiku` tasks skip it. Docs-only and config-only tasks with no `.py` change
  record `style_gate: clean` without running the script.
- **Premise**: `skills/work/SKILL.md` step 2 captures `<task_base_sha>` (added
  by PRD 00159). Re-check at execution time with
  `rg -n "task_base_sha" skills/work/SKILL.md`; if absent, this PRD's Phase 0
  adds the capture line itself, and if present that task is already satisfied.

#### Feature: Per-task style_gate stamp
- **Description**: Each attempt record carries its own gate verdict.
- **Inputs**: the gate's exit code and output.
- **Outputs**: `style_gate: "clean" | "fixed:<sha>" | "failed:<detail>" | "skipped:tier"`
  on `state.tasks[i].attempts[]`, and the same value in the phase report, one
  line per task.
- **Behavior**: The existing step-7.0 outcome ladder is reused verbatim (exit 0
  clean; exit 1 → one fix dispatch, commit, re-run, `fixed:<sha>` or
  `failed:<violations>`; exit 2 → `failed:<stderr>` with no fix dispatch). The
  value is carried in-session into step 6's `task-done` payload, never written
  as a separate indexed state mutation — the same rule `self_deslop` follows.
  `skipped:tier` is the haiku row.

#### Feature: Step 7.0 removal
- **Description**: The phase-end gate is deleted, not kept as a second run.
- **Inputs**: none.
- **Outputs**: `skills/work/SKILL.md` step 7 with no 7.0 sub-step; the phase
  report line becomes the per-task list.
- **Behavior**: A file only crosses 800 lines on the task that pushes it over,
  and the file-limit arithmetic (`n - ins + dels <= file_limit`) already
  identifies exactly that crossing, so the per-task run catches every case the
  phase run did. Keeping both would double the dispatches this PRD exists to
  cut.

### Capability: Sibling-file allowlist for style fixes

Let a split create the modules a split needs.

#### Feature: Directory entries in the fix dispatch allowlist
- **Description**: The style-fix `FILE_PATHS` carries the violating files plus
  the directories they live in.
- **Inputs**: the violation lines (each names a file path).
- **Outputs**: `dev/local/tmp/ivan-<task-id>-style-files.txt` — one absolute
  path per violating file, then one absolute directory path per distinct parent
  directory of those files, each directory line suffixed
  ` (new modules may be created here)`.
- **Behavior**: This list is used **only** by the style-fix dispatch. Every
  other Ivan dispatch keeps passing `dev/local/tmp/ivan-<task-id>-files.txt`
  unchanged. Directories are the parents of violating files only — never the
  repo root, never a parent walked upward.

#### Feature: Creation permission in the retry instruction
- **Description**: The permission is stated in `RETRY_INSTRUCTION`, not by
  editing the persona.
- **Inputs**: the directory list.
- **Outputs**: the rendered fix prompt.
- **Behavior**: `--set RETRY_INSTRUCTION="Fix only the listed style-limit violations. You may create new modules in the directories marked above and update imports in the listed files to use them. Do not change behavior, do not touch other code, and do not modify tests."`
  `agents/ivan.md` is untouched: `{RETRY_INSTRUCTION}` is already free text, and
  a persona edit would reach every dispatch rather than this one.

## Structural Decomposition

### Repository Structure

```
skills/work/
├── SKILL.md                              # Maps to: Per-task gate invocation, Step 7.0 removal
├── references/
│   ├── style-gate.md                     # New: the gate procedure and outcome ladder
│   ├── gate-failure.md                   # Maps to: Creation permission (style-fix render row)
│   └── attempt-logging.md                # Maps to: Per-task style_gate stamp
└── scripts/
    └── test_dispatch_prose.py            # Prose pins
skills/run-autopilot/references/
└── state-schema.md                       # Maps to: Per-task style_gate stamp
```

### Module: style-gate-procedure
- **Maps to capability**: Task-scoped style gate
- **Responsibility**: own the gate's diff construction, invocation and outcome
  ladder in one situational reference, so SKILL.md carries only the call and the
  tier gate (the same split PRD 00119-v2 applied to the other steps).
- **Exports**: none (prose)

### Module: work-prose
- **Maps to capability**: Task-scoped style gate, Sibling-file allowlist
- **Responsibility**: SKILL.md step 2 (`<task_base_sha>` premise), the new step
  5.65, the deletion of step 7.0, the phase-report line; `gate-failure.md`'s
  style-fix render row.
- **Exports**: none (prose)

### Module: schema-and-changelog
- **Maps to capability**: Per-task style_gate stamp
- **Responsibility**: enumerate the new attempt field and its values; CHANGELOG.
- **Exports**: none (prose)

## Dependency Graph

### Foundation Layer (Phase 0)
No dependencies - built first.

- **style-gate-procedure**: the reference file the call site points at.

### Core Layer (Phase 1)
- **work-prose**: Depends on [style-gate-procedure] - it names the file and its
  sections.

### Integration Layer (Phase 2)
- **schema-and-changelog**: Depends on [work-prose] - it documents the field the
  new step writes.

## Implementation Phases

### Phase 0: Foundation
**Goal**: The gate procedure exists as a reference, with the base SHA available.

**Tasks**:
- [ ] Verify the premise and satisfy it if unmet: if
      `rg -n "task_base_sha" skills/work/SKILL.md` has no hit, add to step 2,
      immediately after the `task-start` call, a `git rev-parse HEAD` whose
      output is held in-session as `<task_base_sha>`; if it hits, change nothing
      (no deps) - Acceptance: `rg -n "task_base_sha" skills/work/SKILL.md` hits.
- [ ] Write `skills/work/references/style-gate.md` with sections `## Diff
      construction` (committed range plus one
      `git diff --no-index -- /dev/null <path>` block per untracked `.py` file;
      `--no-index` exits 1 on differences, only exit ≥2 is a failure),
      `## Invocation` (the `check_style_limits.py --diff ... <files>` command
      with absolute paths), `## Outcome ladder` (exit 0/1/2 rows carried over
      verbatim from today's step 7.0) and `## Fix dispatch` (the style-files
      list shape and the verbatim `RETRY_INSTRUCTION`) (no deps) - Acceptance:
      `rg -n "^## (Diff construction|Invocation|Outcome ladder|Fix dispatch)$" skills/work/references/style-gate.md`
      hits all four.

**Exit Criteria**: The procedure is readable standalone; nothing calls it yet.

### Phase 1: Core
**Goal**: The gate runs per task and step 7.0 is gone.

**Tasks**:
- [ ] Edit `skills/work/SKILL.md`: add step 5.65 between 5.6 and 5.7 — the tier
      table (`haiku` → skip, record `style_gate: "skipped:tier"`; every other
      tier including `fable` → run), the base (`<task_base_sha>`), a pointer to
      read `references/style-gate.md` before the first run of a batch, and the
      in-session carry of the value into step 6's `task-done` payload. Delete
      step 7.0 entirely and change step 7's reporting line from the single
      `style_gate:` value to one line per task (depends on: Phase 0) -
      Acceptance: `rg -n "5\.65" skills/work/SKILL.md` hits;
      `rg -n "7\.0|Style-limit gate" skills/work/SKILL.md` has no hit;
      `uv run --no-project --with pytest python -m pytest -q skills/work/scripts/test_dispatch_prose.py`
      green, its SKILL.md line-ceiling test included.
- [ ] Add a `## Style-fix render` section to
      `skills/work/references/gate-failure.md` giving the full render command
      for the style-fix dispatch: identical to `## Retry render` except
      `--set-file FILE_PATHS=dev/local/tmp/ivan-<task-id>-style-files.txt` and
      the verbatim creation-permission `RETRY_INSTRUCTION`; state that this list
      is used by no other dispatch (depends on: Phase 1 task 1) - Acceptance:
      `rg -n "style-files|new modules may be created here" skills/work/references/gate-failure.md`
      hits both.

**Exit Criteria**: A task ending with an 850-line file dispatches one fixer that may create a sibling module.

### Phase 2: Integration
**Goal**: The new field is documented and pinned.

**Tasks**:
- [ ] Add `style_gate` to the attempt schema in
      `skills/work/references/attempt-logging.md` (the JSON block and a field
      -semantics bullet listing `"clean"`, `"fixed:<sha>"`, `"failed:<detail>"`,
      `"skipped:tier"`, absent on legacy attempts) and to the
      `tasks[].attempts` signature in
      `skills/run-autopilot/references/state-schema.md` (depends on: Phase 1) -
      Acceptance:
      `rg -n "style_gate" skills/work/references/attempt-logging.md skills/run-autopilot/references/state-schema.md`
      hits in both files.
- [ ] Add prose pins to `skills/work/scripts/test_dispatch_prose.py` (SKILL.md
      names step `5.65` and `skipped:tier`; SKILL.md no longer names step `7.0`;
      `style-gate.md` names `--no-index`; `gate-failure.md` names
      `style-files`), and the CHANGELOG entries (`feat` commit: `**work**` under
      Changed for the per-task gate and the removed phase-end gate; under Added
      for the sibling-module allowlist) (depends on: Phase 2 task 1) -
      Acceptance:
      `uv run --no-project --with pytest python -m pytest -q skills/work/scripts/test_dispatch_prose.py`
      green; `rg -n "^- \*\*work\*\*" CHANGELOG.md` hits under `[Unreleased]`.

**Exit Criteria**: The prose suite pins every new string and the schema documents the field.

## Test Strategy

### Critical Scenarios
- **Happy path**: a `sonnet` task commits a 900-line module → step 5.65 exits 1,
  one fix dispatch splits it into two siblings, the re-run is clean, the attempt
  records `style_gate: "fixed:<sha>"`, and step 5.7 reviews the split diff.
- **Edge case**: a `haiku` task → no gate run, `style_gate: "skipped:tier"`.
- **Edge case**: a docs-only task → no `.py` in the diff, `style_gate: "clean"`,
  no script invocation.
- **Error case**: the gate exits 2 (a candidate it could not place, per PRD
  00162) → `style_gate: "failed:<stderr>"`, no fix dispatch, the task completes.

## Risks

- **A per-task gate multiplies dispatches on a phase that was previously fixed
  once.** It only dispatches when a task's own diff introduces a violation, and
  the phase-end run it replaces dispatched a fixer over the accumulated diff of
  every task at once — strictly more work, later, with less context.
- **Directory entries in `FILE_PATHS` widen Ivan's scope.** They are the parent
  directories of violating files only, they reach one dispatch kind, and the
  retry instruction restricts the change to the listed violations. The step-5
  staging rule is unchanged: only files in `FILES_TOUCHED:` are committed, and
  anything else stays foreign and is named in the phase report.
- **The `<task_base_sha>` premise may be unmet if PRD 00159 has not landed.**
  Phase 0 re-checks it at execution time and adds the capture itself; the check
  is a grep, so it is decidable headlessly.
- **Cross-task accumulation could slip through.** It cannot: the file-limit test
  fires on the task whose insertions carried the file past 800, which is the
  task that must own the split.
