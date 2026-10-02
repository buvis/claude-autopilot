---
catchup: skip
design: skip
default_model: sonnet
model_tier_rationale: same move PRD 00171 made for sonnet-run.sh, three named lines; a wrong pipeline stage goes red on the pinned exit-code case, and the PASS-line count pin guards the test rewrites
---

# Route the codex prompt through stdin

Source: discovery `dev/local/discovery/00177-cut-review-and-test-loop-overhead.md` (reviewed 2026-09-05). Twin of PRD 00171, which moved `sonnet-run.sh` to stdin on 2026-09-02.

## Overview

### Problem Statement

`skills/use-codex/scripts/codex-run.sh` hands the prompt to codex as one positional argv string on all three codex paths: the plain `run_cmd codex exec ... "$PROMPT" < /dev/null` (line 304), the JSON path `"$@" --json --output-last-message "$OUTPUT_FILE" "$PROMPT" < /dev/null` (line 244), and `codex exec resume <id> ...` through that same JSON path (line 328). Two consequences: a prompt whose first byte is `-` (a ledger bullet, a diff hunk) is parsed as an option, and the prompt is bounded by the platform's argv limit (128 KiB per argument on Linux, 1 MiB total on macOS), which is what makes PRD 00178's inlined retry prompt a size question at all. `codex exec --help` and `codex exec resume --help` both document `-`: "If `-` is used, instructions are read from stdin."

### Target Users

Every `use-codex` dispatch in the autopilot loop (Bob's review, the codex implementor rung, design review) and the operator running `codex-run.sh -f` by hand.

### Success Metrics

- A prompt file whose first line is `- [ ] item` reaches codex byte for byte on the plain, JSON and resume paths.
- The child never inherits the wrapper's stdin (the PRD 00040 hang class stays closed).
- `bash dev/bin/release-checks` stays green with the argv pins rewritten to the new shape.

## Functional Decomposition

### Capability: Prompt delivery

#### Feature: Codex reads the prompt on stdin
- **Description**: every codex dispatch path feeds the prompt on the child's stdin with the literal `-` positional, so no prompt byte is parsed as an option and no argv cap applies.
- **Inputs**: `-f FILE` or a positional prompt; the two codex dispatch lines named above (244, which the resume argv at 328 also feeds, and 304).
- **Outputs**: `codex exec [flags] -` and `codex exec resume <id> [flags] -` with `printf '%s' "$PROMPT" |` in front of the child (exactly the shape `sonnet-run.sh` uses since PRD 00171) and the `< /dev/null` redirect removed on those three lines only. The copilot fallback keeps `-p "$PROMPT" < /dev/null`. The `Prompt required` guard stays.
- **Behavior**: the wrapper's exit code stays codex's own on every path; the JSON path's `codex_exit=$?` after the `| while` loop must still read codex's status once `printf` is the first pipeline stage (the pinned case `fresh JSON path: codex-run.sh exit code equals codex's non-zero exit code` goes red otherwise). `references/dispatch-contract.md` § Child Stdin Policy's second documented exception names `codex-run.sh`'s `codex exec` paths beside `sonnet-run.sh`.

#### Feature: The argv pins follow
- **Description**: `test_codex_run.sh` asserts the stdin shape instead of the positional one.
- **Inputs**: `skills/use-codex/scripts/test_codex_run.sh`, run by `dev/bin/release-checks`.
- **Outputs**: the three cases named `codex child stdin is /dev/null` (no-flag, `--emit-thread-id`, `--resume-thread`) become `codex child stdin is exactly the prompt, never the wrapper's stdin` (the stub's captured stdin equals the prompt bytes and does not contain `SENTINEL_STDIN_DATA`); `no-flag argv is exactly: codex exec --skip-git-repo-check --sandbox read-only <PROMPT>` becomes `... --sandbox read-only -`; the `--resume-thread: argv starts with 'exec resume <uuid>'` case also asserts the argv ends with `-`; one new case feeds a prompt file whose first line is `- [ ] item` and asserts the stub receives it verbatim on stdin.
- **Behavior**: every other case keeps its exit-code and argv assertions; only the prompt's location moves. Premise: `rg -c 'PASS "' skills/use-codex/scripts/test_codex_run.sh` prints 39 before the change (measured 2026-09-05) and must print 40 after (one new case, none dropped); a different count means a case was lost, so stop and report.

## Structural Decomposition

### Repository Structure

```
skills/use-codex/scripts/codex-run.sh                  # Maps to: codex reads the prompt on stdin
skills/use-codex/scripts/test_codex_run.sh             # Maps to: the argv pins follow
skills/use-codex/references/dispatch-contract.md       # Maps to: child stdin policy exception
CHANGELOG.md
```

### Module: codex-runner
- **Maps to capability**: Prompt delivery
- **Responsibility**: the two codex dispatch lines in `codex-run.sh`, their pins, and the dispatch-contract sentence.
- **Exports**: none new (the CLI surface of `codex-run.sh` is unchanged).

## Dependency Graph

### Foundation Layer (Phase 0)
No dependencies - built first.

- **codex-runner**: the stdin dispatch and its pins.

## Implementation Phases

### Phase 0: Fix and pins
**Goal**: a leading-dash prompt runs on every codex path; the runner guard pins the stdin shape.

**Tasks**:
- [ ] Move the two codex dispatch lines in `codex-run.sh` (the JSON path at 244, which the resume argv at 328 also feeds, and the plain path at 304) to `printf '%s' "$PROMPT" |` plus the `-` positional, reword the comment above `run_codex_json_path` (line 216) to say the prompt is piped to the child's stdin with `-` without quoting the argv, and leave the copilot line alone; rewrite the three stdin cases, the no-flag argv pin and the resume argv pin in `test_codex_run.sh` as named above; add the leading-dash case, watched failing against the old script first; add `codex-run.sh` to the second exception in `dispatch-contract.md` § Child Stdin Policy; CHANGELOG `**use-codex**` under Fixed (no deps) - Acceptance: `bash skills/use-codex/scripts/test_codex_run.sh` green including the new case; `rg -c 'PASS "' skills/use-codex/scripts/test_codex_run.sh` prints 40; `rg -c '"\$PROMPT" < /dev/null' skills/use-codex/scripts/codex-run.sh` prints 1 (the copilot `-p "$PROMPT"` line; today it prints 4); `rg -c "printf '%s' \"\\\$PROMPT\" \|" skills/use-codex/scripts/codex-run.sh` prints 2 (today 0); `bash dev/bin/release-checks` green.

**Exit Criteria**: release checks green.

## Test Strategy

### Critical Scenarios
- **Happy path**: `-f` with a file starting with `- [ ] item` reaches the stub codex on stdin unchanged on the plain, JSON and resume paths → Expected: captured stdin equals the file bytes, argv ends with `-`.
- **Edge case**: `--resume-thread <uuid>` → Expected: argv starts with `exec resume <uuid>`, ends with `-`, carries `-c sandbox_mode=read-only`, and the prompt is on stdin.
- **Error case**: an empty prompt file → Expected: exit 1 with `Prompt required` and codex never invoked (existing case stays green).

## Risks

- **Pipeline exit status**: `printf` as the first pipeline stage changes which stage `$?` and `PIPESTATUS[0]` name on the JSON path; the pinned exit-code case catches a wrong read.
- **`gemini-run.sh` keeps the positional `-p <PROMPT>` shape**: out of scope here, as PRD 00171 noted; Carl's prompt is short and never inlined.

## Post-completion notes (2026-09-07)

Ended at the rework cap in cycle 2 (batch 202609061630) with nine findings open; walked 2026-09-07 in the
config-audit closure walkthrough (`~/.claude/dev/local/audit-results/2026-09-05.md`). The ledger's decision
fields get backfilled at batch end.

- The `rg -c 'PASS "'` gate above (40) is a pinned suite count of the kind create-prd now forbids: the build
  split 24 cases into `test_codex_run_resume.sh` and the count reads 21 with all 45 cases alive. The split
  copied 239 scaffold lines and defined `child_stdin_is_prompt` twice; the unreadable-prompt case passes
  against the pre-fix script and is a no-op for root; two new cases duplicate existing ones; the leading-dash
  prompt is checked on the plain path only. All seven rows: PRD 00190 (shared helper, bound cases, three
  paths).
- Commit bb08599's whitespace guard rejects blank prompts by `-f` and positionally while the CHANGELOG says
  `-f` only: keep the guard, correct the line (in PRD 00190).
- The stdin delivery itself (the reason for this PRD) was reviewed clean in both cycles and ships in 0.5.2.
