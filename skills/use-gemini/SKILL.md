---
name: use-gemini
description: Use when running Google Gemini via the native Gemini CLI for code analysis, refactoring, or editing. Triggers on "run gemini", "gemini analyze", "ask gemini".
compatibility: "Host-independent dispatch recipe requiring the named external model CLI and the bundled helper scripts."
---

# Gemini Skill Guide

Gemini runs through the helper script `scripts/gemini-run.sh`, which maps a
stable flag interface onto two backends and resolves the mise-managed binary.

> **Backend:** The helper prefers the GitHub Copilot CLI and falls back to the
> native `gemini` CLI when copilot is absent, or when its default prompt run
> reports a permanently unavailable model. Force a backend with
> `GEMINI_BACKEND=copilot` or `GEMINI_BACKEND=gemini`. Both CLIs are
> mise-managed and may not be on PATH; the helper resolves them via `mise which`.

## Dependencies

- Files read from other skill dirs:
  `${CLAUDE_PLUGIN_ROOT}/skills/use-codex/references/dispatch-contract.md` - mandatory,
  applies verbatim (see below)
- CLIs: `copilot` (preferred) or the native `gemini` CLI; `mise which` for
  resolution of either

## Dispatch Contract (shared)

Background dispatch and waiting (TaskOutput-only waiting), following up, error handling, and the always-use-`-f` prompt rule are defined once in `${CLAUDE_PLUGIN_ROOT}/skills/use-codex/references/dispatch-contract.md`. Read it before dispatching; it applies verbatim to this skill.

Gemini-specific delta: if the helper reports no backend CLI found, or the Copilot monthly quota is exhausted, report that and stop - do not silently fall back to another tool. For a quota error you may offer `GEMINI_BACKEND=gemini` (native CLI) as an alternative.

Permanent rejection is different: the helper tries native Gemini once for an
unforced prompt run with no `-m`. Explicit backends, model overrides, interactive
and resumed sessions never switch CLIs after rejection. Exit 4 means permanently
unavailable after any eligible fallback; report the stderr reason without
retrying the same configuration. If fallback fails transiently, its runtime
exit code is returned instead; stderr retains both backend reasons.

## Model Selection

- **Copilot backend (default):** spends Copilot AI credits per call (multiplier
  set by the model; not exposed headlessly - check the interactive `/model`
  picker). `DEFAULT_COPILOT_MODEL` in `scripts/gemini-run.sh` is the single
  production pin; `--help` prints its current value. The 2026-09-05 picker
  offered Gemini Flash successors but rejected the former Pro Preview pin;
  Carl stays on Gemini using the newest offered Flash model. Per policy,
  Gemini-via-Copilot is allowed because Claude does not
  provide Gemini.
- **Native gemini backend** (`GEMINI_BACKEND=gemini`): bills your Google/Gemini
  API account, no Copilot multiplier.
  With no `-m`, the CLI picks its own default.

Pass `-m MODEL` only when the user asks for a specific model.

### Check the pin (opt-in, live)

Run `mise exec -- copilot`, then `/model` to inspect the installed backend's
authenticated model picker. A listing alone does not prove inference works.
Use this probe to check the runner's actual pin without duplicating it:

```bash
prompt_file=$(mktemp)
printf '%s\n' 'Reply with exactly GEMINI_PIN_OK. Do not use tools.' > "$prompt_file"
GEMINI_BACKEND=copilot bash ${CLAUDE_PLUGIN_ROOT}/skills/use-gemini/scripts/gemini-run.sh -s -f "$prompt_file"
probe_status=$?
rm -f "$prompt_file"
printf 'Gemini pin probe exit: %s\n' "$probe_status"
```

Exit 0 plus `GEMINI_PIN_OK` confirms that the pinned model served the probe;
exit 4 reports permanent rejection. Other failures leave availability
unverified. Forcing copilot prevents a native fallback from hiding a stale pin.
This command uses the network, existing login, and Copilot credits. Never add
it to `dev/bin/release-checks`; that suite remains hermetic with stub binaries.

### Exit codes and output

| Code | Meaning |
| --- | --- |
| 0 | Backend succeeded (or `--help` printed); verify review output is non-empty. |
| 1 | Usage, setup, temporary/output file error, or ordinary backend failure with code 1, 3, or 4. |
| 3 | Nested dispatch refused; no backend ran. |
| 4 | Model unavailable or client tier ineligible after any eligible fallback. |
| Other non-zero | Backend/tool status propagated, including signal exits such as 130 or 143; a runtime failure, not classified permanent rejection. |

Child codes 3 and 4 without a recognized stderr rejection map to 1 to keep the
reserved codes unambiguous. Original backend errors and backend/model selection
are on stderr; record them in the review file. `-o` saves stdout after
classification and also streams stdout to the terminal. On exit 4 it creates
no partial output file and leaves any existing destination untouched; never
reuse that old file as this run's review. Ordinary failed runs retain partial
stdout for salvage. Diagnostics stay on stderr, outside the review text.

## Running a Task

1. Select the permission mode required for the task; default to no special flags (interactive approval) unless edits are necessary.
2. Assemble the command with appropriate options:
   - `-m, --model MODEL` to override the CLI default model
   - `-f, --file FILE` to read the prompt from a file (preferred - avoids shell escaping)
   - `-i, --interactive` for interactive mode with an initial prompt
   - `-a, --allow-tools` to auto-approve edit tools (`--approval-mode auto_edit`)
   - `-y, --yolo` to auto-approve all tools (`--approval-mode yolo`)
   - `-d, --dir DIR` to include an extra directory in the workspace (repeatable)
   - `-s, --silent` accepted for compatibility (headless `-p` output is already clean)
3. When continuing a previous session, use `-c` (most recent) or `-r [ID]` (`latest` or an index).
4. Run the command, capture output, and summarize the outcome for the user.
5. **After Gemini completes**, inform the user: "You can resume this session with `gemini-run.sh -c`."

### Quick Reference

| Use case | Key flags |
| --- | --- |
| Read-only analysis | `-f prompt.txt` |
| Interactive with initial prompt | `-i "prompt"` |
| Auto-approve edit tools | `-a -f prompt.txt` |
| Full auto (all tools) | `-y -f prompt.txt` |
| Include extra directory | `-d <DIR> -f prompt.txt` |
| Resume recent session | `-c` |
| Resume specific session | `-r <ID>` |

Gotcha: in repos where `dev/local` is a symlink outside the workspace (buvis convention: `-> ~/.local/tmp/claude-dev`), gemini cannot read through it - pass `-d ~/.local/tmp/claude-dev` so those files resolve (verified fix).

## Helper Script

```bash
# Write prompt to temp file (see the shared dispatch contract), then run
bash ${CLAUDE_PLUGIN_ROOT}/skills/use-gemini/scripts/gemini-run.sh -f /tmp/gemini-prompt.txt

# With auto-approve edit tools
bash ${CLAUDE_PLUGIN_ROOT}/skills/use-gemini/scripts/gemini-run.sh -a -f /tmp/gemini-prompt.txt

# Full permissions (all tools)
bash ${CLAUDE_PLUGIN_ROOT}/skills/use-gemini/scripts/gemini-run.sh -y -f /tmp/gemini-prompt.txt

# Resume most recent session
bash ${CLAUDE_PLUGIN_ROOT}/skills/use-gemini/scripts/gemini-run.sh -c
```

Run `${CLAUDE_PLUGIN_ROOT}/skills/use-gemini/scripts/gemini-run.sh --help` for all options.
