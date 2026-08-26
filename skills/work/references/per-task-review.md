# Per-Task Review Mechanics (step 5.7)

Moved verbatim out of `SKILL.md` step 5.7 (PRD 00119-v2; situational: consulted
once the tier gate says a task IS reviewed). SKILL.md keeps the tier-gate table,
the `pat.md` render block and the MEDIUM-retry rule; this file owns the runner
dispatch and the result-handling ladder. **Read it before the first step-5.7
dispatch of a batch.**

## Why the lane is tier-gated

A `haiku`-tier task commits after per-task test verification (step 5.5) with **no** review dispatch and proceeds straight to step 6 — it relies on per-task test verification plus the mandated PRD-level review lenses (consensus, blind, doubt — every review cycle reviews every task's diff regardless of tier). The reviewer is a fixed-model helper-script lane (Sonnet via `use-sonnet`) — reviewer capability is deliberately independent of the task's implementor tier. (Why tier-gated: `references/design-rationale.md` § tier-gated pipeline.)

## Dispatch

Dispatch via the sonnet runner (helper-script dispatch — the **Subagent Watchdog** applies), after SKILL.md step 5.7's render call has written the prompt file:

```bash
bash ${CLAUDE_PLUGIN_ROOT}/skills/use-sonnet/scripts/sonnet-run.sh -f dev/local/tmp/review-task-<id>-prompt.md -o dev/local/tmp/review-task-<id>.md
```

No `-a`/`-y` — the reviewer needs no write access, and a read-only dispatch must never run with bypassed permissions.

## Result handling

Read the output file and handle the result:

- **`CLOSURE | resolved|unresolved | ...` verdicts** (rework tasks only — the persona emits one per finding when the task description carries a `### Findings (verbatim)` block, per PRD 00095). A `resolved` verdict needs nothing. **Treat every `unresolved` verdict as a HIGH finding** and run it through the same loop as the row below: verify it against the code first, then dispatch Ivan with the confirmed gap. This exists because "the diff looks fine" and "the reported defect is gone" are different questions, and the review that answered only the first let a task ship with `_run_status` still swallowing `FileNotFoundError` while its review read "fixed inline". Step 5.5 already covers findings that produced a test; these verdicts are what closes the ones that did not.
- **CRITICAL or HIGH findings** — treat like a failed verification: verify each finding against the code first and discard wrong ones (the reviewer can be wrong), then re-render `ivan.md` using the full retry command shape in `references/gate-failure.md` § Retry render, writing the confirmed findings to the `FAILING_TESTS` scratch file and passing `--set RETRY_INSTRUCTION="Apply ONLY the specific fixes listed below. Do not refactor surrounding code or address unrelated issues you notice."`. The code-quality rules block is already permanent in `ivan.md` — do not re-include it. Re-commit (step 5), re-verify (step 5.5), re-review. Max 3 review cycles, then proceed with warning.
- **MEDIUM outside this task's files, LOW only, or `NO FINDINGS`** - note them in the task output, proceed to step 6.
- **Runner unavailable, exit nonzero, or output file missing/empty** — retry ONCE. On the second failure: record `review: failed:<cause>` in the task's attempt entry and the phase report (fail loud), then proceed to step 6 — the reviewer lane never blocks the batch; the PRD-level review lenses catch what it missed.

The MEDIUM-inside-this-task's-files row stays in `SKILL.md` step 5.7: it is the
one branch a passing review still has to stamp on the attempt record.
