# Retry Policy

## When to Retry

Retry on: missing CLI tool, runtime error, or malformed output format.

1. Retry ONCE — the total retry budget per agent is one retry, across all retry reasons (see "Format Compliance" and "Per-Rule Verdict Completeness" below: when both gates fail, the single retry asks for both fixes together)
2. Log: `[RETRY] {agent} attempt 1/1`
3. After the failed retry: mark agent unavailable, continue with others
4. If ALL agents fail: report failure

Consolidation uses partial results from available agents.

## Retry Mechanism (CLI reviewers vs Alice)

"Send one retry" below means different things by reviewer type:

- **Alice** (the native Claude Task Agent): message the running agent again in the same conversation, as written.
- **Bob (codex), Carl (gemini)** (the bg-Bash CLI reviewers, PRD 00034): these are one-shot `run_in_background` Bash processes that have already exited by the time their output file is read, so there is no in-conversation target. A retry means re-dispatching a FRESH `run_in_background` Bash call of the same `*-run.sh` with an amended prompt file, writing the same `dev/local/tmp/{agent}-output-{id}.txt` path. The one-retry budget is unchanged.

## Lack-of-input refusal (Bob)

the output is a lack-of-input refusal when ALL THREE hold: `rg -c '^R[0-9]+: pass' <bob-output>` reports 0 (exit 1), `rg -c '^\[BOB\] (🔴|🟠|🟡|✅)' <bob-output>` reports 0 (exit 1), and `rg -c '^\[BOB\] ⚪ Cannot statically verify' <bob-output>` prints at least 1; on that shape send the one retry as the inlined retry prompt. Any other first-run shape is final: Bob is dispatched exactly once per cycle unless an existing trigger fires (non-zero `codex-run.sh` exit, malformed issue-line format, incomplete per-rule verdicts). The one-retry budget is unchanged; the lack-of-input retry and a format retry share it.

## Inlined retry prompt (CLI reviewers)

the retry prompt file is `dev/local/tmp/bob-prompt-{id}-retry.md` (retained beside the first prompt, never `/tmp`), built as: head block, the review context verbatim, mid block, the diff verbatim inside a ```diff fence, then the persona prompt body with two edits. Dispatch it with the cycle-1 `codex-run.sh -f ... -o <same bob-output path>` command, without `--resume-thread`.

Head block, verbatim:
```
IMPORTANT: You run in a restricted sandbox and CANNOT read files or run commands. Everything you need is INLINED BELOW as text. Do not attempt to read any path, and do not report an inability to read files: the review context and the complete diff are both reproduced verbatim in this prompt.

Context pack: {PACK_FILE contents, or the sentinel `(no pack available this cycle)`}

Repo root (for path interpretation only): {absolute repo path}

Test results for the reviewed revision (already run, do not ask for them):
{the cycle's test results, one line per command}

================================================================================
# REVIEW CONTEXT (inlined verbatim)
================================================================================
```

Mid block, verbatim:
```
================================================================================
# FULL DIFF (inlined verbatim), range {base}..{head}, path-scoped to this PRD
================================================================================
```

The two persona edits: replace `Review the completed work against PRD requirements. Explore the codebase as needed.` with `Review the completed work against PRD requirements using ONLY the inlined text above.`; and append after the `OUTPUT FORMAT IS MANDATORY` block the line `Do NOT emit "Cannot statically verify" lines about reading files or test results: both are supplied above. Only mark a rule fail when the evidence above actually shows a failure.`

The retry keeps the same `{id}` and `-o` path as the first run. The review file's Bob section records `after one retry (inlined)` when it ran. Until PRD 00180 lands, the assembled file must stay under the host's argv limit (1 MiB total on macOS); the 2026-09-05 prompt was 39 KB.

## Format Compliance

If an agent's output doesn't match the required format:

1. Send one retry: "Your output format is incorrect. Reformat using exactly: `[{AGENT_NAME}] {emoji} {description} | File: {path or N/A} | Task: {id or general}` — one issue per line."
2. If still non-compliant after retry, parse what you can and note `(format warning)` next to that agent's findings in consolidation.

## Per-Rule Verdict Completeness

The reviewer prompt embeds a numbered rubric and mandates one `<id>: pass|fail` line per rule. **The id prefix names the rubric (PRD 00108):** `R{n}` for the consensus set (`references/rubric.md`), `B{n}` for the blind set (`review-blindly/references/rubric.md`), `D{n}` for the doubt set (`run-autopilot/references/doubt-review-rubric.md`). This policy is set-agnostic — read `<id>` below as whichever prefix the reviewer's own rubric uses. After parsing the agent's output:

1. For each expected rule ID `<id>`, look for a line matching the exact regex `^[RBD]\d+:\s+(pass|fail)\s*$` whose id is that rule's. A line is **incomplete** when it is absent for an expected rule ID, OR when a line for an expected rule ID exists but its value is anything other than the literal token `pass` or `fail` (e.g. `D5: ok`, `D5: maybe`, `D5: pass (some rationale)`, `D5: PASS`).
2. If any expected rule's line is incomplete, send one retry: "Your output is missing or malformed for the per-rule verdict on {missing/malformed rule IDs}. Emit one line per rule in this exact shape: `<id>: pass` or `<id>: fail` — lowercase token, no extra text, no rationale, no trailing punctuation. One rule per line. A rule you cannot evaluate counts as `fail` — never omit or fudge the line." (Quote the reviewer's own ids in the retry, never a foreign prefix.)
3. If still incomplete after retry, mark each unsatisfied rule as `fail` in the consolidated record and note `(verdict warning: missing/malformed <id>, ...)` next to that agent's findings in consolidation.
4. Combined with the issue-line retry above, the **total retry budget per agent is one retry**: the same retry can ask the agent to fix both the issue-line format and the missing/malformed verdicts together when both gates fail.
