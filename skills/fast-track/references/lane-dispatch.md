# Lane Dispatch

> **Paths in this pack.** This pack's root is `${CLAUDE_PLUGIN_ROOT}`. That line
> is substituted when the skill loads and never inside a reference like this
> one, so swap the real directory in by hand when you meet the placeholder
> here. Never hand the literal placeholder to a shell: it expands to the empty
> string and the path silently becomes `/...`.

One block per lane: render the prompt, open the ledger row, send the dispatch.
Run them from an attended session. With `_AUTOPILOT_LOOP` set the lane refuses
the run, because two reviewers live in background Bash and a headless turn
kills it.

Ten kinds reach the ledger: `fast-track:tess`, `fast-track:ivan`,
`fast-track:fanout`, `fast-track:alice`, `fast-track:blake`, `fast-track:eve`,
`fast-track:bob`, `fast-track:carl`, `fast-track:victor` and
`fast-track:delta`.

## Tess: the test author

Runs only when the card's `## Tests` section is empty. It reads the card alone.

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/skills/work/scripts/render_prompt.py ${CLAUDE_PLUGIN_ROOT}/skills/work/references/tess-prompt.md \
  --out dev/local/tmp/fast-track-<item>-tests.txt \
  --set TASK_SUBJECT=<item> \
  --set-cmd TASK_DESCRIPTION="cat dev/local/tmp/fast-track-<item>-goal.txt dev/local/tmp/fast-track-<item>-files.txt" \
  --set-file TASK_ACCEPTANCE_CRITERIA=dev/local/tmp/fast-track-<item>-constraints.txt \
  --set-file SAMPLE_TEST_FILE=<the card's sample_test> \
  --set-cmd PUBLIC_INTERFACES="cat $(printf '%q ' <each Files entry that exists today>)" \
  --set TEST_FRAMEWORK=<the card's framework> \
  --require-file <each Files entry that exists today>
```

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/skills/work/scripts/record_dispatch.py start --kind fast-track:tess --task <item> --prompt-file dev/local/tmp/fast-track-<item>-tests.txt
```

```text
Agent tool:
  subagent_type: general-purpose
  model: <the card's model>
  prompt: the contents of dev/local/tmp/fast-track-<item>-tests.txt
```

## Ivan: the implementor

Ivan receives the failing tests, the card's `## Files` allowlist, the card's
constraints followed by the repo's `AGENTS.md` (its `CLAUDE.md` when it has no
`AGENTS.md`, `/dev/null` when it has neither), and nothing from the driver's
own reading of the fix.

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/skills/work/scripts/render_prompt.py ${CLAUDE_PLUGIN_ROOT}/agents/ivan.md \
  --out dev/local/tmp/fast-track-<item>-ivan.txt \
  --set-cmd FAILING_TESTS="cat $(printf '%q ' <the test files>)" \
  --set-cmd ARCHITECTURE_CONTEXT="cat dev/local/tmp/fast-track-<item>-constraints.txt $(printf '%q ' <absolute path of the repo's AGENTS.md>)" \
  --set-file FILE_PATHS=dev/local/tmp/fast-track-<item>-files.txt \
  --set RETRY_INSTRUCTION="" \
  --require-file <each Files entry that exists today> \
  --require-parent <each Files entry the card creates>
```

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/skills/work/scripts/record_dispatch.py start --kind fast-track:ivan --task <item> --prompt-file dev/local/tmp/fast-track-<item>-ivan.txt
```

```text
Task tool:
  subagent_type: autopilot:ivan
  model: <the card's model>
  prompt: the contents of dev/local/tmp/fast-track-<item>-ivan.txt
```

A rework opens a second `fast-track:ivan` row for a fresh implementor, at most
once per item. Its render takes the same shape with
`--out dev/local/tmp/fast-track-<item>-rework.txt` and
`--set-file FAILING_TESTS=dev/local/tmp/fast-track-<item>-findings.txt`, the
confirmed findings standing in for the test files as the spec.

## The roster: five lenses in one message

Three Task calls and two background Bash commands go out together, in one
message, so every lens reads the same change and the roster costs one turn.
Open the five rows first, one Bash call each, then send them.

The implementation-aware lanes (consensus, codex, gemini) share one render
shape, with `agents/alice.md`, `agents/bob.md` and `agents/carl.md` as the
persona.

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/skills/work/scripts/render_prompt.py ${CLAUDE_PLUGIN_ROOT}/agents/<persona>.md \
  --out dev/local/tmp/fast-track-<item>-<lane>.txt \
  --set CONTEXT_FILE=<absolute path of the context file> \
  --set DIFF_FILE=<absolute path of the staged diff> \
  --set PACK_FILE="(no pack available this cycle)" \
  --set-file REVIEW_CHECKLIST=${CLAUDE_PLUGIN_ROOT}/skills/review-work-completion/references/review-dimensions.md \
  --set-file RUBRIC=${CLAUDE_PLUGIN_ROOT}/skills/review-work-completion/references/rubric.md \
  --set-file OUTPUT_FORMAT=dev/local/tmp/fast-track-output-format.md
```

### Consensus: fanout, or alice

The consensus lens has two backends and one row. Open
`fast-track:fanout` when `~/.claude/workflows/review-fanout.workflow.js` sits
on disk.

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/skills/work/scripts/record_dispatch.py start --kind fast-track:fanout --task <item> --prompt-file dev/local/tmp/fast-track-<item>-consensus.txt
```

```text
Workflow tool:
  scriptPath: <absolute path of ~/.claude/workflows/review-fanout.workflow.js>
  args: diff, diff_bytes, diff_path, rubric_text, prd_text, changed_files, head_sha, date, cycle, agent_name, personas
```

With that file absent, the `autopilot:alice` subagent carries the lens, under
`fast-track:alice`, and the report names the backend that ran.

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/skills/work/scripts/record_dispatch.py start --kind fast-track:alice --task <item> --prompt-file dev/local/tmp/fast-track-<item>-consensus.txt
```

```text
Task tool:
  subagent_type: autopilot:alice
  prompt: the contents of dev/local/tmp/fast-track-<item>-consensus.txt
```

### Blake: the blind lens

Blake receives the card and never the diff. He locates the code himself and
judges it against what the card asks for, so his render call names no diff at
all: `--set-file PRD=<absolute path of the staged card>`, `--set-file
RUBRIC=${CLAUDE_PLUGIN_ROOT}/skills/review-blindly/references/rubric.md` and
the same `--set-file OUTPUT_FORMAT=`. An unfilled placeholder exits 1, so all
three go in.

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/skills/work/scripts/record_dispatch.py start --kind fast-track:blake --task <item> --prompt-file dev/local/tmp/fast-track-<item>-blake.txt
```

```text
Task tool:
  subagent_type: autopilot:blake
  prompt: the contents of dev/local/tmp/fast-track-<item>-blake.txt
```

### Eve: the doubt lens

`agents/eve.md` renders with `--set PACK_FINDINGS="(no pack available this
cycle)"`. Append six run inputs to the rendered file: the card, the diff range
`<base-sha>..HEAD`, the changed-file list, the findings precedent, the
mechanical test checks, and the `## Agent Output Format` block from
`${CLAUDE_PLUGIN_ROOT}/skills/review-work-completion/references/output-formats.md`.
That sixth input buys the consolidator its input: each FIX item comes back as
an `[EVE] {emoji} {description} | File: {path}` line as well.

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/skills/work/scripts/record_dispatch.py start --kind fast-track:eve --task <item> --prompt-file dev/local/tmp/fast-track-<item>-eve.txt
```

```text
Task tool:
  subagent_type: autopilot:eve
  prompt: the contents of dev/local/tmp/fast-track-<item>-eve.txt
```

### Bob: codex

Bob runs as a direct background Bash command, never inside a subagent: a
subagent cannot hold a background job, and one that shells out to a CLI hangs
until the item stalls. Pass absolute paths.

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/skills/work/scripts/record_dispatch.py start --kind fast-track:bob --task <item> --prompt-file dev/local/tmp/fast-track-<item>-codex.txt
```

```text
Bash tool:
  run_in_background: true
  command: ${CLAUDE_PLUGIN_ROOT}/skills/use-codex/scripts/codex-run.sh -f <absolute path of fast-track-<item>-codex.txt> -o <absolute path of codex-output-<item>.txt>
```

Exit 3 means codex itself is unavailable. Hand the same rendered prompt to a
`general-purpose` Task subagent then, and save its return as this lane's
output.

### Carl: gemini

Carl runs only when `gemini-run.sh` and its backend CLI (`copilot`, or native
`gemini`) resolved in the preconditions. Same shape as Bob: background Bash,
never inside a subagent, absolute paths.

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/skills/work/scripts/record_dispatch.py start --kind fast-track:carl --task <item> --prompt-file dev/local/tmp/fast-track-<item>-gemini.txt
```

```text
Bash tool:
  run_in_background: true
  command: ${CLAUDE_PLUGIN_ROOT}/skills/use-gemini/scripts/gemini-run.sh -f <absolute path of fast-track-<item>-gemini.txt> -o <absolute path of gemini-output-<item>.txt>
```

## Victor: adversarial verification

One dispatch per CRITICAL or HIGH row that earns verification.

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/skills/work/scripts/render_prompt.py ${CLAUDE_PLUGIN_ROOT}/agents/victor.md \
  --out dev/local/tmp/fast-track-<item>-verify-<n>.txt \
  --set-file FINDING_TITLE=dev/local/tmp/fast-track-<item>-finding-<n>-title.txt \
  --set FINDING_SEVERITY=<CRITICAL or HIGH> \
  --set FINDING_FILE=<the path the finding names> \
  --set-file FINDING_EVIDENCE=dev/local/tmp/fast-track-<item>-finding-<n>-evidence.txt \
  --set-file FINDING_PROOF=dev/local/tmp/fast-track-<item>-finding-<n>-proof.txt
```

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/skills/work/scripts/record_dispatch.py start --kind fast-track:victor --task <item> --prompt-file dev/local/tmp/fast-track-<item>-verify-<n>.txt
```

```text
Task tool:
  subagent_type: general-purpose
  model: sonnet
  prompt: the contents of dev/local/tmp/fast-track-<item>-verify-<n>.txt
```

`refuted: false` confirms the finding, and it costs a rework. Uncertainty
refutes: only a shown broken path confirms.

## Delta: the review after a rework

One dispatch, `autopilot:eve` over `<rework-base-sha>..HEAD`, and no other
lane. Her prompt is her persona render with the incremental-review line, the
confirmed findings, the range, its changed-file list and the card appended as
run inputs.

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/skills/work/scripts/render_prompt.py ${CLAUDE_PLUGIN_ROOT}/agents/eve.md \
  --out dev/local/tmp/fast-track-<item>-delta.txt \
  --set PACK_FINDINGS="(no pack available this cycle)"
```

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/skills/work/scripts/record_dispatch.py start --kind fast-track:delta --task <item> --prompt-file dev/local/tmp/fast-track-<item>-delta.txt
```

```text
Task tool:
  subagent_type: autopilot:eve
  prompt: the contents of dev/local/tmp/fast-track-<item>-delta.txt
```

## Close every row

Each dispatch closes the row it opened, with the id the `start` call printed.

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/skills/work/scripts/record_dispatch.py end <id> --outcome ok
```

`--outcome` takes `ok`, `timeout`, `killed`, `error` or `lost`, and `--detail`
carries the reason: `--outcome error --detail "exit <n>"` for a CLI lane that
exited non-zero.

## The item row

After the exit rule, one row closes the item itself.

```text
scripts/record_item.py --item <item> --card <path> --model <m> --started <ts> --outcome committed|branched|stopped --rework 0|1 --findings <json> --confirmed <n> [--cost <usd>]
```

The script sits at
`${CLAUDE_PLUGIN_ROOT}/skills/fast-track/scripts/record_item.py`. Pass `--cost`
when a measured USD figure exists; an absent `--cost` records unmeasured, which
is a different fact from free.
