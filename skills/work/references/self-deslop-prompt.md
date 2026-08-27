# Self-Deslop Prompt Template

This is the prompt template dispatched by `/autopilot:work` step 5.6 — the per-task
self-deslop pass that runs between test-pass verification (step 5.5) and the
per-task code review (step 5.7).

`/autopilot:work` step 5.6 substitutes the placeholders below before dispatching the
subagent. **`{{slop_catalog}}` is filled in at dispatch time** by reading the
current `${CLAUDE_PLUGIN_ROOT}/skills/run-autopilot/prompts/de-sloppify.md`, extracting the
`## What to remove` section verbatim, and inlining it here. The subagent
receives one self-contained prompt with no extra filesystem reads required.
This keeps `prompts/de-sloppify.md` as the single source of truth for slop
patterns: when it evolves, the next step-5.6 dispatch picks up the new catalog
with no edit to this template.

Placeholders:

- `{{task_subject}}` — `tasks[i].name`, read directly from `state.tasks` (no
  native tool field).
- `{{task_description}}` — `tasks[i].description` (full text), read directly
  from `state.tasks`; falls back to a name-only body when absent, and an
  empty-string `description` counts as absent.
- `{{task_acceptance_criteria}}` — a text-extraction of the `Acceptance
  criteria:` section from `tasks[i].description` (there is no native
  `acceptance_criteria` field), or the literal string `(none recorded)` when
  absent.
- `{{test_files}}` — comma-separated paths of the test files Tess wrote in
  step 2.7 and the implementor just made pass in step 5.5.
- `{{diff_files}}` — comma-separated paths of files touched in the implementor's
  most recent commit (`git diff-tree --no-commit-id --name-only -r HEAD`).
- `{{slop_catalog}}` — verbatim contents of `## What to remove` from
  `prompts/de-sloppify.md`.

---

## Prompt Template

```
A diff has been written to satisfy this task. The implementation passed its
tests. Your job: prune slop from the diff while keeping every test green.
This is best-effort cleanup, not a correctness rework — do not change
behavior, do not modify tests, do not refactor.

Task: {{task_subject}}

Description:
{{task_description}}

Acceptance criteria:
{{task_acceptance_criteria}}

Tests that the diff made pass (do NOT modify):
{{test_files}}

Files in the diff:
{{diff_files}}

Procedure:

1. Read the diff for each file in scope (`git diff HEAD~1..HEAD <file>` or
   equivalent in your environment).
2. For each line, block, helper, comment, docstring, or test added in the
   diff, ask:
     "Does this trace to a failing test, an acceptance criterion, or
     existing-behavior preservation?"
   If the answer is no, mark the construct for removal.
3. Apply removals one at a time. After each individual removal, re-run the
   tests listed above (the narrow set Tess wrote). If any test fails,
   restore that single removal and move on to the next candidate. Never
   delete the test that fails — the test is authoritative.
4. If no removal survived its test re-run, exit WITHOUT committing. Return
   the literal string "no slop found" so the caller can record a noop.
5. If at least one removal survived, commit with message:
     chore: prune slop from {{task_subject}}
   No CHANGELOG entry. No HEREDOC. No Co-Authored-By trailer. One commit
   only — do not split into multiple cleanup commits.

Rules:

- **Do not modify tests.** If a test reads as weak, that is the per-task
  reviewer's call (step 5.7), not yours. Leave it.
- **Do not change behavior.** Tests prove behavior; if you cannot satisfy
  the tests, the deletion is wrong. Restore.
- **Do not refactor.** This pass deletes; it does not move code around,
  rename symbols, or extract helpers. If a slop pattern would only resolve
  through restructuring, note it in the return message instead of acting.
- **Do not touch files outside the diff.** The cleanup is scoped to what
  the implementor just produced. Adjacent slop in untouched files is out
  of scope here — the post-session codex pass catches it separately.

Slop patterns to look for (catalog inlined from `prompts/de-sloppify.md`):

{{slop_catalog}}

Return one of:
  - "no slop found" — exited without commit, nothing to clean.
  - "committed {sha}" — committed `chore: prune slop from ...` at {sha},
    test suite green.
  - "errored: {short reason}" — dispatch problem; do not commit, just
    explain so the caller can record the failure.
```

---

## Test-only diffs

SKILL.md step 5.6 applies `test_only_diff` (from
`skills/work/scripts/work_routing.py`) to
`git diff --name-only <task_base_sha>..HEAD` **before** the 30-line/2-file rule.
When every changed path is test or fixture code, there is no dispatch: record
`self_deslop: "skipped:test-only"` and proceed to step 5.7. The stamp is
distinct from `"skipped:trivial"` so the two skips stay tellable apart in the
attempt data.

This skip applies in rework mode too, unlike step 5.7's — de-slopping a test
diff has nothing to close on, and the prompt below forbids touching tests
anyway. One production path anywhere in the diff runs the procedure below.

## Procedure

Moved verbatim out of `SKILL.md` step 5.6 (PRD 00119-v2). The skip rule, the
description-fallback rule and the outcome-logging rule stayed in the body; this
is everything the caller needs once the skip rule did NOT fire.

**Dispatch contract.** Otherwise, dispatch a **fresh** Agent call (NOT the implementor's session — fresh context breaks the "I built this" attachment; why: `references/design-rationale.md` § fresh dispatch) at `state.tasks[i].model`. Same tier as the implementor keeps cost proportional. The dispatch must satisfy the **Subagent Dispatch Budget** and the **Subagent Watchdog**.

**Prompt construction.** Build the subagent prompt from `references/self-deslop-prompt.md` by substituting:

- `{{task_subject}}` from `tasks[i].name`, `{{task_description}}` from `tasks[i].description` (full text, falling back to the name-only body when `description` is absent or an empty string), and `{{task_acceptance_criteria}}` from a **text-extraction** of the `Acceptance criteria:` section of that same `tasks[i].description` (falling back to the literal string `(none recorded)` when absent) — all read directly from the current task's `state.tasks` entry, already in hand from step 1's pending scan. The criteria are parsed out of the stored body; there is no `acceptance_criteria` field to read.
- `{{test_files}}` from the tests Tess wrote in step 2.7 (the same set step 5.5 just ran).
- `{{diff_files}}` from `git diff-tree --no-commit-id --name-only -r HEAD`.
- `{{slop_catalog}}` from the `## What to remove` section of `${CLAUDE_PLUGIN_ROOT}/skills/run-autopilot/prompts/de-sloppify.md` — read the file at dispatch time and inline the section verbatim. This keeps the deslop prompt as the single source of truth for slop patterns; when it grows entries, the next step-5.6 dispatch picks them up without a code change here.

| Subagent outcome | `self_deslop` value | Proceed to 5.7 against |
|------------------|---------------------|------------------------|
| Committed `chore: prune slop from ...` | `"committed:{sha}"` (full SHA from the new commit) | the pruned diff (HEAD now includes the cleanup commit) |
| Returned "no slop found", no commit | `"noop"` | the original implementor diff |
| Watchdog timeout (`TaskStop` fired) | `"timeout"` | the original implementor diff |
| Dispatch failed or subagent errored | `"errored:{short_cause}"` (e.g. `errored:dispatch_failed`, `errored:prompt_overrun`) | the original implementor diff |
| Skip rule fired | `"skipped:trivial"` (no dispatch occurred) | the original implementor diff |

In every non-committed outcome, the implementor's original commit stands and step 5.7 reviews it directly.

---

## Dispatch contract reminders

The `/autopilot:work` step 5.6 caller, NOT the subagent, is responsible for:

- The 30-net-lines / 2-files skip rule. The subagent only sees prompts for
  non-trivial diffs.
- The fresh-Agent-dispatch requirement (not the implementor's session).
- The 15-minute watchdog and `TaskStop` on timeout.
- Carrying the outcome into step 6's `task-done` payload as the attempt
  record's `self_deslop` field (never a separate indexed state write).

See `SKILL.md` step 5.6 for the full contract.
