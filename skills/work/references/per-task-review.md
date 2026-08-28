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
bash ${CLAUDE_PLUGIN_ROOT}/skills/use-sonnet/scripts/sonnet-run.sh -t "" -S "<pat_session_id>" -f dev/local/tmp/review-task-<id>-prompt.md -o dev/local/tmp/review-task-<id>.md
```

`-t ""` grants the child no tools at all: Pat judges the diff, the task text and
the recorded verification, and nothing else. No `-a`/`-y` either — the reviewer
needs no write access, and a read-only dispatch must never run with bypassed
permissions.

`-S "<pat_session_id>"` (step 5.7 item 1) fixes this conversation's id so a later
cycle can resume it. Everything else about the first dispatch is unchanged, and
when no id could be generated the flag is simply dropped.

## Delta re-runs

Every cycle after the first resumes the conversation that raised the findings
instead of starting over. Pat already read `<task_base_sha>..<last_reviewed_sha>`;
re-sending it is what made a second dispatch cost a whole task diff — a measured
369 KB prompt, sent twice, to check a one-file fix.

**Check the delta is non-empty first.** An empty `git diff <last_reviewed_sha>..HEAD`
means the fix never committed, and `render_prompt.py` exits 4 on a `--set-cmd`
that produces no output. Do not dispatch: there is nothing new to judge, the
previous cycle's findings stand, and the loop continues through the CRITICAL/HIGH
row below whose 3-cycle cap is what ends it.

For cycle `<n>` (2 or 3):

1. Write the findings you sent the fixer, verbatim, one per line, to
   `dev/local/tmp/review-task-<id>-prior-<n>.txt` with the **Write tool**. A
   finding line carries backticks and pipes, so it never crosses the shell as a
   `--set` word.
2. Render the re-run prompt:

   ```bash
   python3 ${CLAUDE_PLUGIN_ROOT}/skills/work/scripts/render_prompt.py ${CLAUDE_PLUGIN_ROOT}/skills/work/references/pat-rerun-prompt.md \
     --out dev/local/tmp/review-task-<id>-rerun-<n>.md \
     --set-file PRIOR_FINDINGS=dev/local/tmp/review-task-<id>-prior-<n>.txt \
     --set-cmd DELTA_DIFF="git diff <last_reviewed_sha>..HEAD" \
     --set UNCHANGED_NOTE="You already reviewed <task_base_sha>..<last_reviewed_sha> earlier in this conversation. That range is unchanged and is not repeated here."
   ```

3. Dispatch it with `-R` where the first dispatch had `-S`, same output file:

   ```bash
   bash ${CLAUDE_PLUGIN_ROOT}/skills/use-sonnet/scripts/sonnet-run.sh -t "" -R "<pat_session_id>" -f dev/local/tmp/review-task-<id>-rerun-<n>.md -o dev/local/tmp/review-task-<id>.md
   ```

4. Advance `<last_reviewed_sha>` to the HEAD this dispatch just read, so cycle
   3's delta is cycle 2's fix alone and never the accumulated range.

The reply goes through the same `parse_review.py` gate and the same ladder below:
the reporting contract is unchanged, so nothing downstream cares that the prompt
was a delta. A correction retry (exit 1) re-renders `pat.md`, not this template —
a reply that broke the line shape is not a resume problem.

**No `<pat_session_id>` means no delta lane at all.** When step 5.7 could not
generate an id, or § Resume failure dropped it, every cycle takes the full-diff
dispatch of § Dispatch with neither `-S` nor `-R` — exactly today's behavior.
Never dispatch `-R ""`.

## Resume failure

A `-R` dispatch that exits non-zero or leaves the output file empty (a session
that no longer resolves exits 1 with `No conversation found with session ID:`)
re-dispatches **once** with today's full-diff prompt: re-render `pat.md` exactly
as SKILL.md step 5.7 item 2 does, with `--set-cmd DIFF="git diff <task_base_sha>..HEAD"`,
and run the § Dispatch command above with neither `-S` nor `-R`. Record
`resume_failed` on the attempt record's `review` field (`references/attempt-logging.md`
§ `review` for the shape) and name the fallback in the phase report — a cheap
review that silently did not happen is worse than an expensive one that did.

Then **drop `<pat_session_id>`** and advance `<last_reviewed_sha>` to the HEAD
that fallback read. The session is gone; leaving the id in place would aim every
remaining cycle at a `-R` that is already known to fail, spending a doomed
dispatch each time.

That is the same single retry the runner-failure row below grants, not an extra
one: a second failure takes that row's `review: failed:<cause>` path.

## Result handling

**Validate the reply first.** Every read of the output file, including each
re-run inside the ladder below, goes through the parser:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/skills/work/scripts/parse_review.py dev/local/tmp/review-task-<id>.md
```

- **Exit 0** — the JSON on stdout (`no_findings`, `findings`, `closures`) is what
  the ladder below reads. Do not re-parse the raw text by hand.
- **Exit 1** — the reply broke the reporting contract. Write this text verbatim
  to `dev/local/tmp/review-task-<id>-correction.txt` with the **Write tool**,
  re-render `pat.md` with every flag identical except
  `--set-file CONTRACT_CORRECTION=dev/local/tmp/review-task-<id>-correction.txt`,
  then dispatch **once** more — with `-R "<pat_session_id>"`, never `-S`. The
  session already exists by then, and re-passing `-S` with the same id exits 1
  on `Error: Session ID <id> is already in use.` (verified live 2026-08-28),
  which would spend the whole correction retry on a runner failure. No id in
  hand → neither flag. A `-R` that fails here takes § Resume failure:

  > Your previous reply did not follow the reporting contract. Reply again with only lines of the form `SEVERITY | file:line | issue | fix` (CRITICAL/HIGH/MEDIUM/LOW), CLOSURE lines where the description carries a findings block, or the single line `NO FINDINGS`. No other text.

  **Never `--set` this one.** The text carries backticks; inside a double-quoted
  Bash word they are command substitution, so the correction would reach the
  reviewer with the line shapes it is teaching replaced by empty strings — on
  the single dispatch whose whole job is teaching the line shape. Same rule as
  the task-authored prose flags, and for the same reason.

  A second exit 1 records `review: "failed:invalid_output"` on the attempt
  record and in the phase report (fail loud), then proceeds to step 6. The
  mandatory PRD-level review catches what Pat missed. There is no third
  dispatch.
- **Exit 2** — the output file is missing or empty. That is the runner-failure
  row at the bottom of this list, not a contract failure.

Then handle the parsed result:

- **`CLOSURE | resolved|unresolved | ...` verdicts** (rework tasks only — the persona emits one per finding when the task description carries a `### Findings (verbatim)` block, per PRD 00095). A `resolved` verdict needs nothing. **Treat every `unresolved` verdict as a HIGH finding** and run it through the same loop as the row below: verify it against the code first, then dispatch Ivan with the confirmed gap. This exists because "the diff looks fine" and "the reported defect is gone" are different questions, and the review that answered only the first let a task ship with `_run_status` still swallowing `FileNotFoundError` while its review read "fixed inline". Step 5.5 already covers findings that produced a test; these verdicts are what closes the ones that did not.
- **CRITICAL or HIGH findings** — treat like a failed verification: verify each finding against the code first and discard wrong ones (the reviewer can be wrong), then re-render `ivan.md` using the full retry command shape in `references/gate-failure.md` § Retry render, writing the confirmed findings to the `FAILING_TESTS` scratch file and passing `--set RETRY_INSTRUCTION="Apply ONLY the specific fixes listed below. Do not refactor surrounding code or address unrelated issues you notice."`. The code-quality rules block is already permanent in `ivan.md` — do not re-include it. Re-commit (step 5), re-verify (step 5.5), re-review through § Delta re-runs. Max 3 review cycles, then proceed with warning.
- **MEDIUM outside this task's files, LOW only, or `NO FINDINGS`** - note them in the task output, proceed to step 6.
- **Runner unavailable, exit nonzero, or output file missing/empty** — retry ONCE. On the second failure: record `review: failed:<cause>` in the task's attempt entry and the phase report (fail loud), then proceed to step 6 — the reviewer lane never blocks the batch; the PRD-level review lenses catch what it missed.

The MEDIUM-inside-this-task's-files row stays in `SKILL.md` step 5.7: it is the
one branch a passing review still has to stamp on the attempt record.
