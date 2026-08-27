# Per-Task Review Mechanics (step 5.7)

Moved verbatim out of `SKILL.md` step 5.7 (PRD 00119-v2; situational: consulted
once the tier gate says a task IS reviewed). SKILL.md keeps the tier-gate table,
the `pat.md` render block and the MEDIUM-retry rule; this file owns the runner
dispatch and the result-handling ladder. **Read it before the first step-5.7
dispatch of a batch.**

## Why the lane is tier-gated

A `haiku`-tier task commits after per-task test verification (step 5.5) with **no** review dispatch and proceeds straight to step 6 — it relies on per-task test verification plus the mandated PRD-level review lenses (consensus, blind, doubt — every review cycle reviews every task's diff regardless of tier). The reviewer is a fixed-model helper-script lane (Sonnet via `use-sonnet`) — reviewer capability is deliberately independent of the task's implementor tier. (Why tier-gated: `references/design-rationale.md` § tier-gated pipeline.)

## Test-only diffs

Before anything below, SKILL.md step 5.7 applies `test_only_gate` (from
`skills/work/scripts/work_routing.py`) to
`git diff --name-only <task_base_sha>..HEAD`. When every changed path is test or
fixture code and the task is **not** in rework mode, the whole step is skipped:
no render, no dispatch, `review: "skipped:test-only"` on the attempt record and
in the phase report. Every tier takes the skip, `fable` included.

A rework task keeps its reviewer even on a test-only diff — its CLOSURE verdicts
are what end the review cycle, so skipping him would leave nothing to close on.
One production path anywhere in the diff runs this file in full.

## Recorded verification

Pat is dispatched with no tools, so he cannot run the tests himself. Before the
render, write `dev/local/tmp/review-task-<id>-verification.txt` with the **Write
tool** (never a shell redirect — command output carries quotes and newlines):
the exact command(s) step 5.5 ran, each exit code, and the runner's own summary
line (for example `12 passed in 0.4s`). When step 5.5 could not run, write the
attempt's literal `verification: skipped:<cause>` value instead. That file is
what `--set-file VERIFICATION_RESULT=` reads, and it is the only test evidence
Pat has.

## Dispatch

Dispatch via the sonnet runner (helper-script dispatch — the **Subagent Watchdog** applies), after SKILL.md step 5.7's render call has written the prompt file:

```bash
bash ${CLAUDE_PLUGIN_ROOT}/skills/use-sonnet/scripts/sonnet-run.sh -t "" -f dev/local/tmp/review-task-<id>-prompt.md -o dev/local/tmp/review-task-<id>.md
```

`-t ""` grants the child no tools at all: Pat judges the diff, the task text and
the recorded verification, and nothing else. No `-a`/`-y` either — the reviewer
needs no write access, and a read-only dispatch must never run with bypassed
permissions.

## Result handling

**Validate the reply first.** Every read of the output file, including each
re-run inside the ladder below, goes through the parser:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/skills/work/scripts/parse_review.py dev/local/tmp/review-task-<id>.md
```

- **Exit 0** — the JSON on stdout (`no_findings`, `findings`, `closures`) is what
  the ladder below reads. Do not re-parse the raw text by hand.
- **Exit 1** — the reply broke the reporting contract. Re-render `pat.md` with
  every flag identical except `--set CONTRACT_CORRECTION=` set to exactly this
  text, then dispatch **once** more:

  > Your previous reply did not follow the reporting contract. Reply again with only lines of the form `SEVERITY | file:line | issue | fix` (CRITICAL/HIGH/MEDIUM/LOW), CLOSURE lines where the description carries a findings block, or the single line `NO FINDINGS`. No other text.

  A second exit 1 records `review: "failed:invalid_output"` on the attempt
  record and in the phase report (fail loud), then proceeds to step 6. The
  mandatory PRD-level review catches what Pat missed. There is no third
  dispatch.
- **Exit 2** — the output file is missing or empty. That is the runner-failure
  row at the bottom of this list, not a contract failure.

Then handle the parsed result:

- **`CLOSURE | resolved|unresolved | ...` verdicts** (rework tasks only — the persona emits one per finding when the task description carries a `### Findings (verbatim)` block, per PRD 00095). A `resolved` verdict needs nothing. **Treat every `unresolved` verdict as a HIGH finding** and run it through the same loop as the row below: verify it against the code first, then dispatch Ivan with the confirmed gap. This exists because "the diff looks fine" and "the reported defect is gone" are different questions, and the review that answered only the first let a task ship with `_run_status` still swallowing `FileNotFoundError` while its review read "fixed inline". Step 5.5 already covers findings that produced a test; these verdicts are what closes the ones that did not.
- **CRITICAL or HIGH findings** — treat like a failed verification: verify each finding against the code first and discard wrong ones (the reviewer can be wrong), then re-render `ivan.md` using the full retry command shape in `references/gate-failure.md` § Retry render, writing the confirmed findings to the `FAILING_TESTS` scratch file and passing `--set RETRY_INSTRUCTION="Apply ONLY the specific fixes listed below. Do not refactor surrounding code or address unrelated issues you notice."`. The code-quality rules block is already permanent in `ivan.md` — do not re-include it. Re-commit (step 5), re-verify (step 5.5), re-review. Max 3 review cycles, then proceed with warning.
- **MEDIUM outside this task's files, LOW only, or `NO FINDINGS`** - note them in the task output, proceed to step 6.
- **Runner unavailable, exit nonzero, or output file missing/empty** — retry ONCE. On the second failure: record `review: failed:<cause>` in the task's attempt entry and the phase report (fail loud), then proceed to step 6 — the reviewer lane never blocks the batch; the PRD-level review lenses catch what it missed.

The MEDIUM-inside-this-task's-files row stays in `SKILL.md` step 5.7: it is the
one branch a passing review still has to stamp on the attempt record.
