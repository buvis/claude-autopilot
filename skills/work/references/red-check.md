# Red-Check Detail (step 2.95)

Moved verbatim out of `SKILL.md` step 2.95 (PRD 00119-v2). SKILL.md keeps the
run-it-once rule, the `n/a:new_module` verdict and the skip-when-2.7-skipped
rule; the target resolution and the outcome ladder live here. **Read this file
before the first red-check of a batch.**

## New-module pre-check

**New-module pre-check — skip the pytest invocation, don't just expect it to fail.** Before running the pytest command, identify the target module using the task's own `Contract` section (the exact file path(s) the task implements, per `plan-tasks`' own contract convention) — not every import in the test file, only the one under test. The target module is the test file's import whose resolved filesystem path matches one of those Contract paths; this sidesteps import-parsing ambiguity entirely, since the task plan already names the file being built.

**Only the Contract paths the test file actually imports are candidates.** A Contract routinely names files the new tests never import — an edited caller, a schema doc, a reference page — and a missing one of those does not imply an `ImportError`, so it must not suppress the run. Intersect first: take the Contract paths, keep those the test file imports, and judge existence on that set alone.

If any **imported** Contract-named target path does not yet exist on disk, skip the pytest invocation for this step entirely: write `red_check = "n/a:new_module"` to the attempt entry and proceed straight to step 3 (still "expected red" semantically — a module that doesn't exist cannot pass). A Contract naming multiple imported files, some new and some existing, still takes this branch if ANY of them is missing — partial existence still guarantees an `ImportError` on the missing half, so running pytest gains nothing.

**No Contract section, or no Contract path the tests import** (a legacy plan task, or a task whose Contract names only non-imported files): there is nothing to resolve, so do NOT skip. Run the check exactly as below — an unresolvable target is a reason to gather real evidence, never a reason to record `n/a:new_module` on a module that may well exist.

Otherwise (every imported Contract-named target already exists — this is an edit to an existing module, not a new one), run the check exactly as below.

## Outcomes

| Outcome | Action |
|---------|--------|
| ≥1 test fails | Expected red. Proceed to step 3. |
| All pass | Accidentally-green tests bind nothing. Send the run output back to Tess ("these tests pass with no implementation — strengthen them to fail against the current tree"); this consumes the **Total Tess budget** (step 2.8; on exhaustion flag and proceed per that step). Commit the strengthened tests (`test(<scope>): strengthen tests for <feature>`), re-capture `<test_commit_sha>` per step 2.9, and re-run this check. |
| Tests cannot run standalone (they import the not-yet-built feature, or the runner cannot execute them) | Record `red_check: skipped:<cause>` in the task's attempt entry and the phase report (fail loud; a skipped check must never read as a passed one), then proceed to step 3. |
