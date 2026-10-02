---
design: skip
---

# Check split hygiene in touched test files

## Overview

### Problem Statement

The self-deslop pass finds waste in test files and is forbidden to remove it.
`skills/work/references/self-deslop-prompt.md:80-81` states: "**Do not modify
tests.** If a test reads as weak, that is the per-task reviewer's call (step
5.7), not yours." The template also contradicts itself — step 2 (line 62) asks
the agent to evaluate "each line, block, helper, comment, docstring, **or test**
added in the diff" for removal, and the rule then forbids acting on the answer.

Measured (batch feedback 2026-08-27): a fresh de-slop pass noticed unused test
constants and shadowed assignments left behind by a mechanical file split, could
not touch them, and Pat then reported the same items — which fed the next review
cycle.

The ban is correct and stays. An agent deciding by judgment which test bindings
are dead is exactly the path to a silently weakened test. What is missing is a
mechanical answer to a mechanical question.

### Target Users

The autopilot work phase, on any task that splits or moves test code. The
operator sees the same hygiene finding travel through de-slop, Pat, and the
PRD-level lenses today.

### Success Metrics

- A test module carrying a module-level constant no other name in the file
  references is flagged before the per-task review runs, with file and line.
- Zero assertions, test functions or fixtures are ever flagged: the checker
  reports bindings, never behavior.
- A test file with no dead bindings exits 0 and dispatches nothing.
- The de-slop ban is unchanged: `self-deslop-prompt.md` still forbids modifying
  tests, and its self-contradicting step-2 wording is corrected to match.

## Functional Decomposition

### Capability: Mechanical split-hygiene check

Answer "is this binding read anywhere in this file" with `ast`, not judgment.

#### Feature: Unused module-level binding rule
- **Description**: Report a module-level name that nothing in the file loads.
- **Inputs**: one or more Python test file paths.
- **Outputs**: lines of the form `UNUSED | <path>:<line> | <name> | module-level binding never read in this file`.
- **Behavior**: Parse with `ast`. Collect module-level `Assign`/`AnnAssign`
  targets that are plain `Name` nodes, plus `Import`/`ImportFrom` bound names.
  Collect every `Name` in `Load` context and every `Attribute`/`arg`/decorator
  identifier anywhere in the module. A collected binding with no load is
  reported. **Never reported**: any name starting with `_`, `__all__` and names
  listed in it, names bound inside a function or class body, `conftest.py`
  bindings of any kind (pytest resolves fixtures by name across files, so a
  same-file load proves nothing there), and any name that appears as a string
  literal anywhere in the file (a `getattr`, `parametrize` id, or `monkeypatch`
  target).

#### Feature: Shadowed assignment rule
- **Description**: Report a local name assigned twice with no load between.
- **Inputs**: the same files.
- **Outputs**: lines of the form `SHADOWED | <path>:<line> | <name> | reassigned before the previous value is read`.
- **Behavior**: Per function body, walk statements in source order tracking, for
  each plain `Name` target, the line of its last unread assignment. A new
  assignment to a name whose previous assignment was never loaded reports the
  **previous** line. Augmented assignment (`x += 1`) counts as a load. `with`,
  `for`, `except ... as` and comprehension targets are bindings but are not
  reported — their rebinding is the construct's own semantics. Any function
  containing a `global`, `nonlocal`, `exec`, `eval`, `locals()` or `del` on the
  tracked name is skipped whole.

#### Feature: Exit contract
- **Description**: The same three-way contract the style gate uses.
- **Inputs**: the file list.
- **Outputs**: exit 0 (clean), 1 (violations printed to stdout), 2 (could not
  run — a syntax error, an unreadable file, or a non-Python path).
- **Behavior**: Mirrors `check_style_limits.py` so the caller's outcome ladder is
  the same shape. A file that fails to parse is a **skip**, and any skip forces
  exit 2 with the not-inspected list on stderr — never a silent pass.

### Capability: Task-boundary invocation

Run it where the style gate runs.

#### Feature: Call site and stamp
- **Description**: The checker runs on the test files this task touched, beside
  the style gate.
- **Inputs**: the task's committed and untracked `.py` paths, filtered to test
  paths.
- **Outputs**: `split_hygiene: "clean" | "fixed:<sha>" | "failed:<detail>" | "skipped:no-tests"`
  on the attempt record and in the phase report.
- **Behavior**: Runs immediately after the style-limit gate at the task
  boundary, over the test-file subset of the same candidate list. Violations
  route to the same single fix dispatch the style gate uses, with
  `RETRY_INSTRUCTION="Delete only the listed unused or shadowed bindings. Do not change any assertion, test function, fixture or parametrization. Do not add code."`
  Test files the task touched are already inside the task's own file list, so no
  allowlist widening is needed. Re-run after the fix; still failing →
  `failed:<violations>` and proceed (fail loud, never blocking).
- **Premise**: a task-boundary gate call site exists (PRD 00163's step 5.65).
  Re-check with `rg -n "5\.65" skills/work/SKILL.md`; if absent, this PRD adds
  the checker and its tests and wires the call into step 7 alongside the existing
  step-7.0 gate instead, changing nothing else.

## Structural Decomposition

### Repository Structure

```
skills/work/
├── scripts/
│   ├── check_split_hygiene.py          # Maps to: Mechanical split-hygiene check
│   └── test_check_split_hygiene.py     # Rule tests
├── SKILL.md                            # Maps to: Call site and stamp
└── references/
    ├── style-gate.md                   # The shared task-boundary procedure
    ├── self-deslop-prompt.md           # Step-2 wording correction
    └── attempt-logging.md              # The split_hygiene field
```

### Module: split-hygiene
- **Maps to capability**: Mechanical split-hygiene check
- **Responsibility**: parse test files and report dead or shadowed bindings; no
  writes, no git, no network.
- **Exports**:
  - `unused_bindings(tree, path) -> list[str]` - the UNUSED lines
  - `shadowed_assignments(tree, path) -> list[str]` - the SHADOWED lines
  - CLI `check_split_hygiene.py FILE [FILE ...]`

### Module: work-prose
- **Maps to capability**: Task-boundary invocation
- **Responsibility**: the call site, the outcome stamp, the corrected de-slop
  wording, the schema entry and the CHANGELOG.
- **Exports**: none (prose)

## Dependency Graph

### Foundation Layer (Phase 0)
No dependencies - built first.

- **split-hygiene**: the checker and its tests.

### Core Layer (Phase 1)
- **work-prose**: Depends on [split-hygiene] - it names the script, its flags and
  its exit codes.

### Integration Layer (Phase 2)
No integration module - this PRD ships one script and its prose.

## Implementation Phases

### Phase 0: Foundation
**Goal**: The checker answers both rules correctly on fixtures.

**Tasks**:
- [ ] Write `skills/work/scripts/check_split_hygiene.py` (stdlib `ast` only)
      implementing both rules, every exclusion listed above, and the 0/1/2 exit
      contract with a `skipped` list forcing exit 2 (no deps) - Acceptance:
      `python3 skills/work/scripts/check_split_hygiene.py /dev/null` exits 2;
      `python3 -c "import ast,sys;sys.path.insert(0,'skills/work/scripts');import check_split_hygiene"`
      exits 0.
- [ ] Write `skills/work/scripts/test_check_split_hygiene.py` covering: a
      module-level `EXPECTED = 3` no test reads is UNUSED; the same constant read
      in one assertion is clean; a `_HELPER` binding is never reported; a name
      only referenced inside a `parametrize` string literal is never reported; a
      `conftest.py` binding is never reported; an import bound and unused is
      UNUSED; `x = 1` then `x = 2` with no read between is SHADOWED naming the
      first line; `x = 1; assert x; x = 2` is clean; `x += 1` counts as a read; a
      `for x in ...` rebinding is never reported; a function using `global x` is
      skipped whole; a file with a syntax error yields exit 2 with the file named
      on stderr (no deps) - Acceptance:
      `uv run --no-project --with pytest python -m pytest -q skills/work/scripts/test_check_split_hygiene.py`
      green with all twelve cases present.

**Exit Criteria**: Both rules pass their fixtures and the checker never reports an assertion or test function.

### Phase 1: Core
**Goal**: The check runs at the task boundary and its verdict is recorded.

**Tasks**:
- [ ] Verify the premise (`rg -n "5\.65" skills/work/SKILL.md`) and wire the
      call accordingly: present → add a `## Split hygiene` section to
      `skills/work/references/style-gate.md` (test-path subset of the candidate
      list, the invocation, the outcome ladder, the verbatim
      `RETRY_INSTRUCTION`) and one line in step 5.65 pointing at it; absent →
      add the same section to `skills/work/references/final-verification.md` and
      one line in step 7 after the style gate. Either way record
      `split_hygiene:` on the attempt via step 6's `task-done` payload, never as
      a separate indexed write (depends on: Phase 0) - Acceptance:
      `rg -n "check_split_hygiene.py" skills/work/` hits a reference file and
      `skills/work/SKILL.md`;
      `uv run --no-project --with pytest python -m pytest -q skills/work/scripts/test_dispatch_prose.py`
      green, its SKILL.md line-ceiling test included.
- [ ] Correct the self-contradiction in
      `skills/work/references/self-deslop-prompt.md`: step 2 of the prompt
      template drops "or test" from its removal-candidate list, and a sentence
      after the "Do not modify tests" rule states that test-file hygiene is
      handled mechanically by `check_split_hygiene.py` at the task boundary. The
      ban itself is unchanged (depends on: Phase 1 task 1) - Acceptance:
      `rg -n "docstring, or test" skills/work/references/self-deslop-prompt.md`
      has no hit;
      `rg -n "Do not modify tests" skills/work/references/self-deslop-prompt.md`
      still hits;
      `rg -n "check_split_hygiene" skills/work/references/self-deslop-prompt.md`
      hits.
- [ ] Enumerate `split_hygiene` and its four values in
      `skills/work/references/attempt-logging.md` and in the `tasks[].attempts`
      signature in `skills/run-autopilot/references/state-schema.md`; add prose
      pins to `test_dispatch_prose.py`; add the CHANGELOG entry (`feat` commit:
      `**work**` under Added, "mechanical split-hygiene check on test files a
      task touched") (depends on: Phase 1 task 2) - Acceptance:
      `rg -n "split_hygiene" skills/work/references/attempt-logging.md skills/run-autopilot/references/state-schema.md`
      hits in both;
      `uv run --no-project --with pytest python -m pytest -q skills/work/scripts/test_dispatch_prose.py`
      green; `rg -n "split-hygiene" CHANGELOG.md` hits under `[Unreleased]`.

**Exit Criteria**: A task that splits a test module and leaves a dead constant behind gets one deletion-only fix dispatch before its per-task review.

## Test Strategy

### Critical Scenarios
- **Happy path**: a split leaves `EXPECTED_ROWS = 12` unread in the new module →
  one UNUSED line, one deletion-only fix dispatch, re-run clean,
  `split_hygiene: "fixed:<sha>"`.
- **Edge case**: a task touching no test files → `skipped:no-tests`, no
  invocation.
- **Edge case**: a fixture whose name is only referenced as a test-function
  argument → never reported (arg identifiers are collected as loads).
- **Error case**: an unparseable test file → exit 2,
  `split_hygiene: "failed:<stderr>"`, no fix dispatch, the task completes.

## Risks

- **Deleting a binding another file needs.** The rules only ever consider names
  bound at module level in a test file, `conftest.py` is excluded wholesale, and
  a name appearing in any string literal in the file is excluded. A cross-file
  import of a test module's constant is rare and would still be caught by the
  suite, which runs before the task completes.
- **A false SHADOWED on a deliberate rebinding.** Loop, `with` and `except`
  targets are excluded, `global`/`nonlocal`/`del`/`locals()` functions are
  skipped whole, and the fix is deletion-only with the suite as the backstop.
- **Rule creep toward judging tests.** The checker reports bindings, never
  assertions; the fix instruction forbids touching assertions, fixtures and
  parametrization; and the de-slop ban on modifying tests is untouched.
