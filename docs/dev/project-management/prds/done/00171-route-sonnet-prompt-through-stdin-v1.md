---
catchup: skip
design: skip
---

# Route the sonnet prompt through stdin

Source: reported 2026-09-02 by the agent-skills session working PRD 00010 there. agent-skills fixed its own copy in 13d68a8, mirroring df551fc for `qwen-run.sh`; the plugin twin here still has the bug. Filed by the 00169 session after reading the script; not reproduced live here.

## Overview

### Problem Statement

`skills/use-sonnet/scripts/sonnet-run.sh` line 232 hands the prompt to `claude --print` as the last positional argument, with stdin redirected from `/dev/null`. A prompt whose first character is `-` (a ledger line such as `- [ ] task`, a markdown bullet, a diff hunk) is parsed by `claude` as an option and rejected as unknown, so the dispatch fails before the model runs. `-f FILE` is the common caller (reviewer dispatches, per-task prompts) and prompt files routinely open with a bullet.

### Target Users

Every `use-sonnet` dispatch in the autopilot loop and the operator running `sonnet-run.sh -f` by hand.

### Success Metrics

- A prompt file whose first line is `- [ ] item` reaches the model byte for byte in prompt mode.
- The child never inherits the caller's stdin (the PRD 00040 hang class stays closed).
- `bash dev/bin/release-checks` stays green with the argv pins rewritten to the new shape.

## Functional Decomposition

### Capability: Prompt delivery

#### Feature: Prompt mode feeds the prompt on stdin
- **Description**: headless dispatch delivers the prompt on the child's stdin so no prompt byte is ever parsed as an option.
- **Inputs**: `-f FILE` or a positional prompt, `MODE=prompt`.
- **Outputs**: `claude --print --model MODEL [flags]` with the prompt on stdin and no positional prompt token.
- **Behavior**: replace `"$PROMPT" < /dev/null` with `printf '%s' "$PROMPT" |` in front of the `run_cmd` call, so the child's stdin is exactly the prompt bytes (no trailing newline added) and never the wrapper's stdin. `-S` and `-R` stay on this `--print` path. Interactive (`-i`), resume (`-r`) and continue (`-c`) keep the TTY and the positional prompt. Keep the explicit "Prompt required" guard so an empty prompt still fails before dispatch.

#### Feature: The argv pins follow
- **Description**: the runner guard's cases assert the new stdin shape instead of the old positional one.
- **Inputs**: `skills/use-sonnet/scripts/test_sonnet_run.sh`, run by `dev/bin/release-checks`.
- **Outputs**: the case `claude child stdin is /dev/null` becomes `claude child stdin is exactly the prompt, never the wrapper's stdin` (the stub's captured stdin equals the prompt bytes and does not contain `SENTINEL_STDIN_DATA`); the cases `plain -f argv is exactly: --print --model sonnet <PROMPT>`, `-t "": the prompt still reaches claude as its own argv token`, `-t Read: argv carries --tools=Read with the prompt intact`, and the `-S`/`-R` argv lines assert the prompt on the fake claude's stdin and no positional token; one new case feeds a prompt file starting with `- [ ] item` and asserts the fake receives it verbatim.
- **Behavior**: every case keeps its exit-code and argv assertions; only the prompt's location moves from argv to stdin.

## Structural Decomposition

### Repository Structure

```
skills/use-sonnet/scripts/sonnet-run.sh          # Maps to: prompt delivery
skills/use-sonnet/scripts/test_sonnet_run.sh     # Maps to: argv pins, leading-dash regression
CHANGELOG.md
```

### Module: sonnet-runner
- **Maps to capability**: Prompt delivery
- **Responsibility**: the prompt-mode dispatch line in `sonnet-run.sh` and its runner guard.
- **Exports**: none new (the CLI surface of `sonnet-run.sh` is unchanged)

## Dependency Graph

### Foundation Layer (Phase 0)
No dependencies - built first.

- **sonnet-runner**: the stdin dispatch and its pins.

## Implementation Phases

### Phase 0: Fix and pins
**Goal**: a leading-dash prompt runs; the runner guard pins the stdin shape.

**Tasks**:
- [ ] Change the prompt-mode dispatch line in `sonnet-run.sh`; rewrite the stdin and argv cases named above in `test_sonnet_run.sh`; add the leading-dash case, watched failing against the old script first; CHANGELOG `**use-sonnet**` under Fixed (no deps) - Acceptance: `bash skills/use-sonnet/scripts/test_sonnet_run.sh` green including the new case; `bash dev/bin/release-checks` green; `rg -n '"\$PROMPT" < /dev/null' skills/use-sonnet/scripts/sonnet-run.sh` has no hit.

**Exit Criteria**: release checks green.

## Test Strategy

### Critical Scenarios
- **Happy path**: `-f` with a file starting with `- [ ] item` reaches the fake claude on stdin unchanged.
- **Edge case**: `-t ""` (no tools) still dispatches with the prompt on stdin.
- **Error case**: an empty prompt file still exits 1 with "Prompt required" and never invokes claude.

## Risks

- `claude --print` reading stdin may treat a trailing newline differently from a positional prompt; the leading-dash case asserts byte equality so any trim shows up.
- `gemini-run.sh` carries the same positional shape (`-p <PROMPT>`); it is out of scope here and worth a separate check.
