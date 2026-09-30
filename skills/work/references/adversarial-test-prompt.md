# Adversarial Test Validator Prompt (Devon)

Devon tries to break Tess's tests by writing a wrong implementation that passes them. If it succeeds, the tests are too weak. Unlike a thought exercise, Devon must actually write the code and run the tests to prove its exploit works.

## Procedure

Dispatch Devon to try to write a **wrong** implementation that passes all of Tess's tests. Devon's goal is to exploit weak tests.

**Devon runs as:** Claude Code subagent (Agent tool) — it needs file write access and the project's test runner to execute its wrong implementation against the tests. **Devon receives only:** the test files from Tess, public interfaces/types (so its wrong implementation compiles), and test-runner access. No task description, no acceptance criteria, no architecture docs.

**Devon's job:** Write an implementation that is clearly wrong (hardcoded values, ignored edge cases, shortcut if/else chains), run the tests against it, and report which tests it broke through.

**Outcomes:**

| Devon result | Action |
|----------------|--------|
| Cannot break tests (tests catch all exploits) | Tests are strong. Proceed to 2.95 (the tests were committed at step 2.85, before Devon ran). |
| Breaks tests with wrong impl that passes | Send Devon's exploit back to Tess as a numbered weak-point list (see Feedback to Tess below). Commit the strengthened tests as `test(<scope>): strengthen <feature>` (this commit is now `<test_commit_sha>`), record `devon: exploit_fixed` and `devon_exploit: <Devon's one-line weak-point summary>`, `devon_weak_points: <count of Devon's list>` and `devon_in_contract: [<each "N. in-contract: ..." line Tess returned>]` in the task's attempt entry, proceed to 2.95. A weak point Tess neither strengthened nor marked in-contract goes back to Tess in the same strengthen dispatch's one correction retry; the orchestrator never dismisses one itself (V33). |

## Prompt Template

```
You are an adversarial test validator. Your job is to BREAK these tests by writing a wrong implementation that passes all of them.

Test files:
{test file contents}

Public interfaces/types (so your implementation compiles):
{type definitions, function signatures, module exports}

Test runner command: {the command that runs ONLY this task's test files, e.g. uv run --no-project --with pytest python -m pytest -q --tb=line <the task's test files>; never a whole test directory}

Your goal:
Write an implementation that makes ALL tests pass but is clearly WRONG. Strategies:
- Return hardcoded values that happen to match test expectations
- Ignore parameters and return constants
- Handle only the exact cases the tests check, fail on everything else
- Use if/else chains that match test inputs specifically
- Skip validation that tests don't verify

Process:
1. Read the tests carefully
2. Write a deliberately wrong implementation
3. Run the test suite against your wrong implementation
4. If tests pass: you broke them. Keep going: show every other weak point you can prove the same way, up to 8 in total, before reporting.
5. If tests fail: try a different exploit. After 3 failed attempts, report "Tests are robust."

Rules:
1. You MUST run the tests to verify your exploit actually works - no guessing
2. Your implementation MUST be obviously wrong (not just suboptimal)
3. Do NOT modify test files
4. For each exploit, explain which test is too weak and what assertion would prevent it
5. Clean up your wrong implementation before returning. Do NOT use `rm` — it is denied to subagents and will fail. Instead, use the Write tool to OVERWRITE every file you created with a single placeholder line (`# adversarial placeholder - overwritten by implementor`). The Write tool always works. Never ask for permission to delete; just overwrite and report the path.
6. Run only the test runner command above, once per exploit; never a
whole test directory.

Output format:
- If you CAN break the tests: show the wrong implementation and the passing test output, then a numbered `Weak points:` list, one line each: `N. <test name> - <what a wrong implementation gets away with> - <assertion that would prevent it>`
- If you CANNOT break the tests: say "Tests are robust" and explain why each shortcut you tried was caught

You receive NOTHING about what the code should actually do. You only see tests and types.
```

## Context Selection

| Include | Why |
|---------|-----|
| Test file contents | The thing Devon is trying to break |
| Public types/interfaces | So wrong implementation compiles |
| Test runner command (the task's test files only) | So Devon can verify exploits without a full-suite run per attempt |

| Exclude | Why |
|---------|-----|
| Task description | Devon shouldn't know what "correct" looks like |
| Acceptance criteria | Same - would leak the spec |
| Architecture docs | Not needed for adversarial validation |

## Feedback to Tess (when Devon succeeds)

When Devon finds an exploit, send this back to Tess:

```
Your tests can be passed by a wrong implementation:

{Devon's wrong implementation}

Test output (all passing):
{Devon's test run output}

Weak points:
{Devon's numbered weak-point list, verbatim}

Address every numbered weak point. Answer each in your reply as
`N. strengthened: <test name>` or `N. in-contract: <why the behavior is allowed>`.
Do not change tests that Devon could NOT break.
```
