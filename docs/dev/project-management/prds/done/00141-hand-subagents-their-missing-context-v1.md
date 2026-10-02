---
catchup: skip
design: skip
---

# Hand the blind reviewer and the test author the context they cannot see

Merges the two 2026-08-25 drafts `00141-tell-blind-reviewer-about-symlinked-layouts-v1` and `00142-hand-tess-the-hook-harness-contract-v1` (backlog review decision, same day, while this PRD lived in `~/.claude`). Source: `~/.claude/dev/local/discovery/00148-autopilot-fast-track-learnings.md` § 3 and § 5. Backlog review 2026-08-26 (`dev/local/audit-results/backlog-review-2026-08-26.md`): the hook harness contract itself describes `~/.claude/hooks` (a dispatcher, 25 handlers, 20 suites), not this plugin's one-hook `hooks/`, so writing it moved to `~/.claude`'s PRD `00146-close-autopilot-extraction-chores-v1`; this PRD keeps the repo-agnostic `/work` convention that hands Tess such a contract wherever one exists.

## Problem

Two subagents are deliberately kept ignorant of the implementation and both were tripped by facts that are not implementation. Blake (blind lens) reported `~/.claude/dev/local/tmp/00136-smoke-autopilot/last-session.log` "does not exist on disk"; it existed (31 KB). He swept with `rg --files`, which neither descends into the `~/.claude` dot-directory nor follows the `dev/local` symlink - the same blindness behind the 00136 incident. The refuted 🟡 cost a verification round. Tess (test author) was briefed to drive a "marker checked before stdin" test through `_common.capture_main`; that helper installs its own `sys.stdin`, so the test would have passed against the old code too. Only the orchestrator reading `hooks/_common.py` before dispatch caught it. `/work` has no standing way to hand Tess a project's test-harness contract without handing her the code.

A third subagent is kept ignorant of something it needs by a blanket rule. `agents/ivan.md` line 8 says "Do NOT modify test files" outright, while the allowlist under `## Files you may read and modify` already bounds every dispatch. PRD 00122's wave-2 rework (2026-08-25) had two test-only tasks (split a test module under the 800-line cap; rename golden fixtures); Ivan could run neither, so the orchestrator hand-built a general-purpose implementor for each and recorded the deviation (`~/.claude/dev/local/meta/assumptions.md` ## 4, ## 5). `/work` step 2.7 already skips Tess for "test-only, docs-only, or config-only tasks", but step 3 never says what fills `FAILING_TESTS` when there are no failing tests, so each orchestrator improvises.

## Solution

Two run-input additions plus one persona clause. (1) `review-work-completion` step 4 prepends a `## Filesystem notes` block to Blake's run inputs when the project's `dev/local` is a symlink or the project root is a dot-directory: the realpath and the instruction to `ls`/Read it directly. (2) `/work` step 2.7 adds a project's test-harness contract to `PUBLIC_INTERFACES` whenever one exists beside a file the task touches: the convention is `<dir>/tests/HARNESS_CONTRACT.md` for a Contract path `<dir>/<file>`; absent means nothing is added (today's behavior). The `~/.claude/hooks/tests/HARNESS_CONTRACT.md` that motivated it is written by the `~/.claude` chores PRD. (3) Ivan's test-file ban yields to the allowlist, and `/work` step 3 says how a test-only or docs-only task fills `FAILING_TESTS`: with the task's own verification checks.

## Requirements

### Must have
- `skills/review-work-completion/SKILL.md` step 4, Blake's row: when the trigger holds, prepend `## Filesystem notes` to Blake's run inputs with the project root, the `dev/local` realpath, and the sentence "`rg --files` does not descend into dot-directories or follow this symlink; list or Read the realpath directly." The trigger is one deterministic check run from the project root: `test -L dev/local` succeeds, OR the project root's basename starts with `.`. No diff, no file list beyond those two paths, no review history. `references/agent-invocation.md` documents the block and trigger. `agents/blake.md` untouched.
- `skills/work/SKILL.md` step 2.7: for each path in the task's Contract file list, when `<its directory>/tests/HARNESS_CONTRACT.md` exists, the `PUBLIC_INTERFACES` `--set-cmd` includes that file (once per distinct file); when none exists nothing is added. `references/test-author-prompt.md` records the same rule. Tess still never receives the module under test. Keep the SKILL.md addition to two lines (PRD 00119 holds the file under 500).
- `agents/ivan.md` line 8: "Do NOT modify test files." becomes "Do NOT modify test files unless your allowlist below names them (a test-only task lists them on purpose)." Nothing else in the persona changes; rule 4 ("the failing tests are the spec ... do not weaken them") stays verbatim.
- `skills/work/SKILL.md` step 3 gains one paragraph, at most three lines, headed "Test-only, docs-only and config-only tasks (Tess skipped at 2.7):" - `FAILING_TESTS` is filled with the task's `Verify:` line and `Acceptance criteria` bullets written to `dev/local/tmp/ivan-<task-id>-checks.txt` and passed with `--set-file`; `FILE_PATHS` lists the test, doc or config files the task touches; step 2.95 is skipped and the attempt record's `red_check` is `n/a:test-only-task`, `n/a:docs-only-task` or `n/a:config-only-task`. `references/attempt-logging.md` (`:25`, `:56`) today enumerates only `skipped:<cause> | n/a:new_module | null`; add the three values there. Pat's step-5.7 review still runs for test-only tasks; the docs-only and config-only skip there is unchanged.
- `skills/work/scripts/test_dispatch_prose.py` gains one test: step 3 names `ivan-<task-id>-checks.txt` and the three `n/a:` values, `references/attempt-logging.md` lists them, and `agents/ivan.md` contains "unless your allowlist below names them".
- Two prose-contract tests pin the new sentences: one in `skills/review-work-completion/scripts/test_agent_registry.py` (SKILL.md step 4 names `## Filesystem notes`, the `test -L dev/local` check and the dot-directory trigger) and one in `skills/work/scripts/test_dispatch_prose.py` (step 2.7 and `test-author-prompt.md` both name `tests/HARNESS_CONTRACT.md`).

### Nice to have
- The cycle's review file records under Agent Status whether the Blake block was injected.

## Implementation

### Module: blake-run-inputs
- **Location**: `skills/review-work-completion/SKILL.md` (step 4), `skills/review-work-completion/references/agent-invocation.md`, `skills/review-work-completion/scripts/test_agent_registry.py`
- **Responsibility**: the trigger, the block text, and its prose pin.
- **Exports**: none (prose) + one test function

### Module: tess-run-inputs
- **Location**: `skills/work/SKILL.md` (step 2.7), `skills/work/references/test-author-prompt.md`, `skills/work/scripts/test_dispatch_prose.py`
- **Responsibility**: the harness-contract convention and its prose pin.
- **Exports**: none (prose) + one test function

### Module: ivan-test-only-lane
- **Location**: `agents/ivan.md` (line 8), `skills/work/SKILL.md` (step 3), `skills/work/references/attempt-logging.md` (`:25`, `:56`), `skills/work/scripts/test_dispatch_prose.py`
- **Responsibility**: the allowlist clause, the `FAILING_TESTS`-from-checks rule for test-only/docs-only/config-only tasks, the documented `red_check` values, and their prose pin.
- **Exports**: none (prose) + one test function

### Dependencies
- blake-run-inputs: No dependencies (foundation)
- tess-run-inputs: No dependencies (foundation)
- ivan-test-only-lane: No dependencies (foundation)

## Tasks

### Phase 0: Foundation
- [ ] Blake's `## Filesystem notes` block: SKILL.md step 4 + agent-invocation.md + the registry prose test - `rg -n "Filesystem notes" skills/review-work-completion/SKILL.md skills/review-work-completion/references/agent-invocation.md` hits both; `uv run --with pytest pytest skills/review-work-completion/scripts/test_agent_registry.py -q` green and the new test fails with the heading removed (spot-check once, restore); `agents/blake.md` byte-identical to HEAD.
- [ ] Ivan's allowlist clause, the step-3 test-only paragraph, the attempt-logging.md values and the prose pin - `rg -n "unless your allowlist below names them" agents/ivan.md` hits line 8; `rg -n "ivan-<task-id>-checks.txt" skills/work/SKILL.md` hits step 3; `rg -n "n/a:test-only-task" skills/work/references/attempt-logging.md` hits; `uv run --with pytest pytest skills/work/scripts/test_dispatch_prose.py skills/work/scripts/test_render_prompt.py -q` green; `skills/work/SKILL.md` gains at most three lines for this task.

### Phase 1: Core
- [ ] Wire the harness-contract convention into `/work` step 2.7 and the test-author reference, with the prose pin (depends on: Phase 0) - `rg -n "tests/HARNESS_CONTRACT.md" skills/work/SKILL.md skills/work/references/test-author-prompt.md` hits both; `uv run --with pytest pytest skills/work/scripts/test_dispatch_prose.py -q` green; `skills/work/SKILL.md` gains at most two lines for this task.

## Success Criteria

In-session (judged by the reviewers):
- The three prose pins are green and each goes red when its sentence is removed (spot-checked once during the task, then restored).
- `agents/blake.md` is byte-identical to HEAD; `skills/work/SKILL.md` grew by at most five lines in total.

Post-release signals (not judged in-session; the batch runs the installed plugin cache, and this repo's `dev/local` is a plain directory, so the Blake trigger cannot fire here until the pack is released and run in a symlinked project such as `~/.claude`):
- The next review of a PRD in `~/.claude` shows the `## Filesystem notes` block in `dev/local/tmp/blake-prompt-<id>.md`, and Blake files zero refuted "file does not exist" findings on `dev/local` files in the next three cycles.
- The next Tess dispatch for a task under `~/.claude/hooks/` carries the `capture_main` sentence in `dev/local/tmp/dispatch-tess-<id>.txt` (needs `~/.claude`'s chores PRD to have written the contract).
- The next test-only rework task is implemented by an `ivan.md` render (its `dev/local/tmp/dispatch-ivan-<id>.txt` exists) with no "purpose-built implementor" deviation in `dev/local/meta/assumptions.md`.
