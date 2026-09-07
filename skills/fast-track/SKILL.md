---
name: fast-track
description: Use when one small, test-specified item should run end to end without the autopilot loop: fresh implementor, five review lenses in one message, one rework, then commit or park. Triggers on "fast-track this card", "run the fast-track lane".
compatibility: "Requires Bob personal Claude/autoclaude environment or equivalent host adapters for sub-agents, background CLI reviewers, and the dispatch ledger."
---

> **Paths in this pack.** This pack's root is `${CLAUDE_PLUGIN_ROOT}` - that line
> is substituted when this skill loads, so what you just read is the real
> directory. Never hand the literal placeholder to a shell: it expands to the
> empty string and the path silently becomes `/...`.

# Fast-Track One Card

One spec card in, one reviewed change out. Start the lane in an attended
session:

```text
/autopilot:fast-track <card.md> --push
```

`--push` pushes the working branch after a clean commit exit; leave it off to
keep the commits local. Work down the sections in order: each one names the next
thing to do, and the section that stops the item says so.

## Preconditions

- **Attended session.** Check `_AUTOPILOT_LOOP` first: a set value means a
  headless loop session, and the lane refuses the run there. Headless
  `claude -p` kills background Bash about five seconds after the turn ends, and
  two of the five review lenses live in background Bash.
- **A worktree you know.** Run `git status --porcelain` and account for every
  dirty path. The lane stages the card's files and leaves foreign paths
  untouched.
- **Reviewer CLIs.** `${CLAUDE_PLUGIN_ROOT}/skills/use-codex/scripts/codex-run.sh`
  is executable. The gemini lane is optional: drop it when
  `${CLAUDE_PLUGIN_ROOT}/skills/use-gemini/scripts/gemini-run.sh` or its backend
  CLI (`copilot`, or native `gemini`) is absent, and say which in the report.
- **Staging.** `dev/local/tmp/` exists; create it when it does not. Every path a
  prompt names is absolute, because a subagent misresolves a relative
  `dev/local/` path as `~/dev/local/`.

## The card

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/skills/fast-track/scripts/card.py <card.md>
```

Exit 0 prints the parsed card as JSON. Hold `item` (the slug every ledger row
carries), `model` (the tier the implementor runs on), `suite`, `framework` and
`sample_test`.

Exit 2 prints `card.py: <field>: <message>` on stderr and the lane stops there:
fix that field and parse again. The parser refuses a card that misses one of the
seven `## ` sections (`Goal`, `Tests`, `Files`, `Constraints`, `Docs`, `Gates`,
`Transport impact`), carries an unknown `model` or `suite`, chains a gate line
with `&&`, `;` or `|`, lists more than 12 files, or runs a goal past 40 lines.
The last two say the same thing: `card too large for the lane; write a PRD`.

Stage the card's prose now, with the Write tool, so nothing crosses the shell as
an argument later: the goal to `dev/local/tmp/fast-track-<item>-goal.txt`, the
`## Tests` notes to `dev/local/tmp/fast-track-<item>-spec.txt`, the constraints
to `dev/local/tmp/fast-track-<item>-constraints.txt`, and the whole card to
`dev/local/tmp/fast-track-<item>-card.md`.

## Tests

A card whose `## Tests` section names test files ships its own spec: read those
files and go to Implement. An empty section means the card's `framework` and
`sample_test` drive one test-author dispatch.

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/skills/work/scripts/render_prompt.py ${CLAUDE_PLUGIN_ROOT}/skills/work/references/tess-prompt.md \
  --out dev/local/tmp/fast-track-<item>-tests.txt \
  --set-file TASK_SUBJECT=dev/local/tmp/fast-track-<item>-goal.txt \
  --set-file TASK_DESCRIPTION=dev/local/tmp/fast-track-<item>-spec.txt \
  --set-file TASK_ACCEPTANCE_CRITERIA=dev/local/tmp/fast-track-<item>-constraints.txt \
  --set-file SAMPLE_TEST_FILE=<the card's sample_test> \
  --set-cmd PUBLIC_INTERFACES="cat $(printf '%q ' <the card's Files entries>)" \
  --set TEST_FRAMEWORK=<the card's framework> \
  --require-file <each Files entry that exists today>
```

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/skills/work/scripts/record_dispatch.py start --kind fast-track:tests --task <item> --prompt-file dev/local/tmp/fast-track-<item>-tests.txt
```

Both calls print the prompt's byte count; the start call prints the dispatch id
under it. Hold that id for the `end` call.

```
Agent tool:
  subagent_type: general-purpose
  model: <the card's model>
  prompt: the contents of dev/local/tmp/fast-track-<item>-tests.txt
```

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/skills/work/scripts/record_dispatch.py end <id> --outcome ok
```

Commit the tests on their own, then run them once at the card's scope and watch
them fail. Red is the point: a test that passes before the implementation exists
pins nothing.

```bash
git add <the test files>
```

```bash
git commit -m "test(<scope>): add tests for <item>"
```

## Implement

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/skills/work/scripts/render_prompt.py ${CLAUDE_PLUGIN_ROOT}/agents/ivan.md \
  --out dev/local/tmp/fast-track-<item>-ivan.txt \
  --set-cmd FAILING_TESTS="cat $(printf '%q ' <the test files>)" \
  --set-file ARCHITECTURE_CONTEXT=dev/local/tmp/fast-track-<item>-constraints.txt \
  --set-file FILE_PATHS=dev/local/tmp/fast-track-<item>-files.txt \
  --set RETRY_INSTRUCTION="" \
  --require-file <each Files entry that exists today> \
  --require-parent <each Files entry the card creates>
```

`FILE_PATHS` is the card's `## Files` list, one absolute path per line, and it
is the whole allowlist. The implementor receives the failing tests, that
allowlist and the card's constraints. It receives no acceptance criteria and
nothing from your own reading of the fix.

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/skills/work/scripts/record_dispatch.py start --kind fast-track:ivan --task <item> --prompt-file dev/local/tmp/fast-track-<item>-ivan.txt
```

```
Agent tool:
  subagent_type: autopilot:ivan
  model: <the card's model>
  prompt: the contents of dev/local/tmp/fast-track-<item>-ivan.txt
```

Close the row, stage the paths from the `FILES_TOUCHED:` footer, and commit.
Any other dirty path is foreign: leave it unstaged and name it in the report.

```bash
git add <each path the footer names>
```

```bash
git commit -m "<type>(<scope>): <description>"
```

## Gates

Run the card's `## Gates` lines in the order the card lists them, one Bash call
each. The parser already refused a chained gate line, so each one runs on its
own. `suite: per-item` points the test gate at this item's test files;
`suite: batch` runs the repo suite once, at the last gate.

A gate that exits non-zero stops the lane here. Write the failing command and
its output to `dev/local/tmp/fast-track-<item>-retry.txt`, re-render the
Implement block with `--set-file RETRY_INSTRUCTION=` pointed at that file,
dispatch a fresh `autopilot:ivan` once, and run the gates again from the top. A
gate still red after that dispatch sends the item to the exit rule with outcome
`stopped`.

## Roster

Five lenses, zero shared context. Every prompt is rendered from the card, the
diff and a persona file, so nothing the driver believes about the change reaches
a reviewer.

Stage the review inputs first. Run `git diff <base-sha>..HEAD` and save its
output to `dev/local/tmp/fast-track-<item>.diff` with the Write tool, then copy
the `## Agent Output Format` section of
`${CLAUDE_PLUGIN_ROOT}/skills/review-work-completion/references/output-formats.md`
to `dev/local/tmp/fast-track-output-format.md`.

- **Consensus.** `review-fanout.workflow.js` when that file is on disk,
  otherwise the `autopilot:alice` subagent. Inputs: the staged card, the staged
  diff and the consensus rubric.
- **Blind.** `autopilot:blake` receives the card and never the diff. Knowing the
  card alone is the whole lens: he locates the code himself and judges it
  against what the card asks for.
- **Doubt.** `autopilot:eve` runs the doubt lens on the card, the diff range and
  the changed-file list, and returns FIX / VERIFY / KNOWN plus her five `D{n}`
  verdict lines.
- **Codex.** `codex-run.sh` carries the consensus prompt to codex.
- **Gemini.** `gemini-run.sh`, when its backend resolved in the preconditions.

Render each prompt from its persona. The implementation-aware lanes (consensus,
codex, gemini) take one shape:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/skills/work/scripts/render_prompt.py ${CLAUDE_PLUGIN_ROOT}/agents/<persona>.md \
  --out dev/local/tmp/fast-track-<item>-<lane>.txt \
  --set CONTEXT_FILE=<absolute path of the staged card> \
  --set DIFF_FILE=<absolute path of the staged diff> \
  --set PACK_FILE="(no pack available this cycle)" \
  --set-file REVIEW_CHECKLIST=${CLAUDE_PLUGIN_ROOT}/skills/review-work-completion/references/review-dimensions.md \
  --set-file RUBRIC=${CLAUDE_PLUGIN_ROOT}/skills/review-work-completion/references/rubric.md \
  --set-file OUTPUT_FORMAT=dev/local/tmp/fast-track-output-format.md
```

- `agents/alice.md` for the consensus lane, `agents/bob.md` for codex,
  `agents/carl.md` for gemini.
- `agents/blake.md` takes `--set-file PRD=<absolute path of the staged card>`,
  `--set-file RUBRIC=${CLAUDE_PLUGIN_ROOT}/skills/review-blindly/references/rubric.md`
  and the same `--set-file OUTPUT_FORMAT=`; his render call names no diff at all.
  An unfilled placeholder exits 1, so every one of the three is passed.
- `agents/eve.md` takes `--set PACK_FINDINGS="(no pack available this cycle)"`;
  append the card, the range `<base-sha>..HEAD` and the changed-file list to the
  rendered file as her run inputs.

Open one row per lane, one Bash call each:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/skills/work/scripts/record_dispatch.py start --kind fast-track:consensus --task <item> --prompt-file dev/local/tmp/fast-track-<item>-consensus.txt
python3 ${CLAUDE_PLUGIN_ROOT}/skills/work/scripts/record_dispatch.py start --kind fast-track:blind --task <item> --prompt-file dev/local/tmp/fast-track-<item>-blake.txt
python3 ${CLAUDE_PLUGIN_ROOT}/skills/work/scripts/record_dispatch.py start --kind fast-track:doubt --task <item> --prompt-file dev/local/tmp/fast-track-<item>-eve.txt
python3 ${CLAUDE_PLUGIN_ROOT}/skills/work/scripts/record_dispatch.py start --kind fast-track:codex --task <item> --prompt-file dev/local/tmp/fast-track-<item>-codex.txt
python3 ${CLAUDE_PLUGIN_ROOT}/skills/work/scripts/record_dispatch.py start --kind fast-track:gemini --task <item> --prompt-file dev/local/tmp/fast-track-<item>-gemini.txt
```

Send all five lanes in one message: three Task calls and two background Bash
calls, dispatched together, so the roster costs one turn and every lens reads
the same change.

```
Task tool:
  subagent_type: autopilot:alice
  prompt: the contents of dev/local/tmp/fast-track-<item>-consensus.txt
```

```
Task tool:
  subagent_type: autopilot:blake
  prompt: the contents of dev/local/tmp/fast-track-<item>-blake.txt
```

```
Task tool:
  subagent_type: autopilot:eve
  prompt: the contents of dev/local/tmp/fast-track-<item>-eve.txt
```

```
Bash tool:
  run_in_background: true
  command: ${CLAUDE_PLUGIN_ROOT}/skills/use-codex/scripts/codex-run.sh -f <absolute path of fast-track-<item>-codex.txt> -o <absolute path of fast-track-<item>-codex-out.txt>
```

```
Bash tool:
  run_in_background: true
  command: ${CLAUDE_PLUGIN_ROOT}/skills/use-gemini/scripts/gemini-run.sh -f <absolute path of fast-track-<item>-gemini.txt> -o <absolute path of fast-track-<item>-gemini-out.txt>
```

Codex and gemini run as background Bash, never inside a subagent: a subagent
cannot hold a background job, and one that shells out to a CLI hangs until the
whole item stalls.

On the workflow backend the consensus lane is a `Workflow` tool call in that
same message, with the host-local script:

```
Workflow tool:
  scriptPath: <absolute path of ~/.claude/workflows/review-fanout.workflow.js>
  args: diff, diff_bytes, diff_path, rubric_text, prd_text, changed_files, head_sha, date, cycle, agent_name, personas
```

`personas` maps `rita`, `cora`, `grace`, `toby`, `mallory`, `trent` and `victor`
to the bodies of `${CLAUDE_PLUGIN_ROOT}/agents/<name>.md` with the frontmatter
stripped; a blank body throws `INVALID_ARGS`. A missing workflow file means the
`autopilot:alice` Task call above, and one line in the report.

The harness re-invokes you when a background command finishes. Read
`fast-track-<item>-codex-out.txt` and `fast-track-<item>-gemini-out.txt` then,
and close every row: `--outcome ok`, or `--outcome error --detail "exit <n>"`
for a CLI lane that exited non-zero. A lens that reported nothing is a missing
lens in the report, never a pass. One retry per lane, then it counts as failed.

## Verify

Every CRITICAL and HIGH finding earns one adversarial verification before it
costs a rework. `verify_targets` in
`${CLAUDE_PLUGIN_ROOT}/skills/fast-track/scripts/fast_track_plan.py` is the
rule: rows raised by the consensus workflow skip this step, because its own
verifier already tested them, and a MEDIUM or a LOW neither reworks nor blocks
the exit.

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
python3 ${CLAUDE_PLUGIN_ROOT}/skills/work/scripts/record_dispatch.py start --kind fast-track:verify --task <item> --prompt-file dev/local/tmp/fast-track-<item>-verify-<n>.txt
```

```
Task tool:
  subagent_type: autopilot:victor
  prompt: the contents of dev/local/tmp/fast-track-<item>-verify-<n>.txt
```

Uncertainty refutes; only a shown broken path confirms. Record each refuted
finding in the report and drop it. What survives is the confirmed set.

## Rework

Rework runs at most once: dispatch a fresh `autopilot:ivan` with the confirmed
findings, the card and the same allowlist, then run the card's gates again from
the top.

Write the confirmed findings to `dev/local/tmp/fast-track-<item>-findings.txt`
and render the Implement block with `--set-file RETRY_INSTRUCTION=` pointed at
that file. The fresh implementor reads the findings and the tests, so it argues
with neither.

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/skills/work/scripts/record_dispatch.py start --kind fast-track:rework --task <item> --prompt-file dev/local/tmp/fast-track-<item>-rework.txt
```

A confirmed finding still standing after the delta review goes to the exit rule.
The lane opens no second round.

## Delta

The rework commit gets its own review, scoped to what changed:

```bash
git diff <rework-base-sha>..HEAD
```

Re-dispatch the lanes that raised the confirmed findings, in one message, each
prompt carrying this line above its inputs:

> This is an incremental review of the rework since the previous cycle. For each
> prior finding listed below, verify it is now resolved in the code, then review
> the scoped diff for any regression the rework introduced.

The blind lane keeps its card-only prompt here too. One row per re-dispatched
lane:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/skills/work/scripts/record_dispatch.py start --kind fast-track:delta --task <item> --prompt-file dev/local/tmp/fast-track-<item>-delta-<lane>.txt
```

Findings the delta review confirms join the surviving set. The exit rule reads
that set.

## Exit rule

`exit_action` in `fast_track_plan.py` is the rule: any surviving CRITICAL or
HIGH parks the item on a branch, and everything else commits.

**Clean.** The commits stay on the working branch. With `--push`, push it now.

**Blocked.** A confirmed CRITICAL or HIGH never stays on the working branch.
Park the commits, then put the working branch back where the item started:

```bash
git branch fast-track/<item>
```

```bash
git reset --keep <base-sha>
```

`git branch` leaves the commits reachable under `fast-track/<item>`, and
`git reset --keep <base-sha>` rewinds the working branch and refuses outright
rather than clobber a foreign change in the tree. A parked item never pushes.
Name the branch and the surviving findings in the report.

## Ledgers

Every dispatch opens a row before it goes out and closes it when it returns, so
the item's cost is measurable per lane:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/skills/work/scripts/record_dispatch.py end <id> --outcome ok
```

`--outcome` takes `ok`, `timeout`, `killed`, `error` or `lost`, and `--detail`
carries the reason. The kinds this lane opens are `fast-track:tests`,
`fast-track:ivan`, `fast-track:consensus`, `fast-track:blind`,
`fast-track:doubt`, `fast-track:codex`, `fast-track:gemini`,
`fast-track:verify`, `fast-track:rework` and `fast-track:delta`.

One more row closes the item itself, after the exit rule:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/skills/fast-track/scripts/record_item.py --item <item> --card <card.md> --model <model> --started <epoch seconds of the first dispatch> --outcome committed --rework 0 --findings <JSON array of the raised findings> --confirmed <n>
```

`--outcome` is `committed`, `branched` or `stopped`. Pass `--cost` when a
measured USD figure exists; an absent `--cost` records unmeasured, which is not
the same fact as free. The row lands in
`dev/local/autopilot/loop-metrics.jsonl` and its `ledger/` mirror.

## Report

Close with one screen:

- the item, its card path and the outcome (`committed`, `branched` or
  `stopped`), plus the branch name when the item is parked;
- each gate command with its exit code;
- findings raised per lens, findings confirmed, findings refuted, and the rework
  round when one ran;
- every lane that did not report, and why: a missing gemini backend, a missing
  workflow file, a lens that failed its one retry.

An item stopped by a red gate or a surviving CRITICAL says so in the first line.
A lens that never reported is reported as missing, and the ledger file
`dev/local/autopilot/loop-metrics.jsonl` is where the numbers came from.
