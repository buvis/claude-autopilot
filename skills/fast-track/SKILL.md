---
name: fast-track
description: Use when one small, test-specified item should run end to end without the autopilot loop - fresh implementor, five review lenses in one message, one rework, then commit or park. Triggers on "fast-track this card", "run the fast-track lane".
compatibility: "Requires Bob personal Claude/autoclaude environment or equivalent host adapters for sub-agents, background CLI reviewers, and the dispatch ledger."
---

> **Paths in this pack.** This pack's root is `${CLAUDE_PLUGIN_ROOT}` - that line
> is substituted when this skill loads, so what you just read is the real
> directory. Never hand the literal placeholder to a shell: it expands to the
> empty string and the path silently becomes `/...`.

# Fast-Track One Card

Spec cards in, reviewed changes out. Start the lane in an attended session:

```text
/autopilot:fast-track <card.md> [<card.md> ...] [--push]
```

The lane runs the cards in the order the arguments give them. `--push` pushes
once, after the last item; leave it off to keep the commits local. Work down the
sections in order: each one names the next thing to do, and the section that
stops the item says so.

## Preconditions

- **Loop session.** Check `_AUTOPILOT_LOOP` first: a set value means a
  headless loop session, where `claude -p` kills background Bash about five
  seconds after the turn ends, and two of the five review lenses live in
  background Bash. When `_AUTOPILOT_LOOP` is set, dispatch the Watcher
  subagent (`general-purpose`) in the SAME message as the roster. When the
  Watcher is skipped, the Stop hook `hooks/guard_stop_on_live_lanes.py`
  (PRD 00213) holds the session open while either background lane is alive
  and names the `-o` files to await. The Watcher's prompt is the exact one
  `${CLAUDE_PLUGIN_ROOT}/skills/review-work-completion/SKILL.md` step 5
  gives it, quoted here verbatim (its placeholder is this item's two `-o`
  paths, the codex and the gemini output files):

  > Run `python3 ${CLAUDE_PLUGIN_ROOT}/skills/review-work-completion/scripts/await_reviewer_outputs.py --budget 100 <absolute -o output path of each CLI reviewer dispatched>` as a foreground Bash call. If the last stdout line is `WAITING`, run the same command again — up to 30 times total. Return the script's final output verbatim (`DONE`, or `WAITING` plus the pending files after 30 runs). Do nothing else: no reading the output files, no review commentary.

  The Watcher is scaffolding, not a reviewer: its return is never saved or
  consolidated, and once every lane has reported (or reached its terminal
  failure) `TaskStop` it if it is still running. A `WAITING` return after 30
  runs means a stalled CLI lane; count that lane as failed after its one
  retry, as the Roster says.
- **A worktree you know.** Run `git status --porcelain` and account for every
  dirty path. A dirty path inside the card's `## Files` stops the item before
  any dispatch: the lane cannot tell that work from the implementor's, and it
  refuses rather than commit somebody else's edit. The lane stages the card's
  files and leaves every other dirty path untouched.
- **Reviewer CLIs.** `${CLAUDE_PLUGIN_ROOT}/skills/use-codex/scripts/codex-run.sh`
  is executable. The gemini lane is optional: drop it when
  `${CLAUDE_PLUGIN_ROOT}/skills/use-gemini/scripts/gemini-run.sh` or its backend
  CLI (`copilot`, or native `gemini`) is absent, and say which in the report.
- **Staging and telemetry.** Create `dev/local/tmp/` and `dev/local/autopilot/`
  before the first dispatch: `mkdir -p dev/local/autopilot dev/local/tmp`. Both
  recorders find `dev/local/autopilot` by walking up from the cwd, and with no
  ancestor holding it they write nothing and exit 0, so a missing directory
  loses every ledger row of the item. Every path a prompt names is absolute,
  because a subagent misresolves a relative `dev/local/` path as
  `~/dev/local/`.

## Card

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

`${CLAUDE_PLUGIN_ROOT}/skills/fast-track/references/spec-card.md` holds the full
format: the frontmatter keys, the seven sections, one worked card and the
refusal table.

Stage the card's fields now, with the Write tool, so nothing crosses the shell
as an argument later: the goal to `dev/local/tmp/fast-track-<item>-goal.txt`,
the constraints to `dev/local/tmp/fast-track-<item>-constraints.txt`, the
`## Files` list, one absolute path per line, to
`dev/local/tmp/fast-track-<item>-files.txt`, and the whole card to
`dev/local/tmp/fast-track-<item>-card.md`.

Capture the item's starting commit before any commit of its own lands:

```bash
git rev-parse HEAD
```

Hold that as `<base-sha>`. The review range `<base-sha>..HEAD` and the blocked
exit's reset target both read it, and every item captures its own.

Print the lane plan before any dispatch. Each flag is `1` or `0`:
`--tests-present` when the card's `## Tests` section names test files,
`--workflow-available` when `~/.claude/workflows/review-fanout.workflow.js` is
on disk, `--carl-available` when the gemini backend resolved in the
preconditions.

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/skills/fast-track/scripts/fast_track_plan.py lanes --tests-present <1 or 0> --workflow-available <1 or 0> --carl-available <1 or 0>
```

It prints one `fast-track:<kind>` line per dispatch, in dispatch order. The
sections below open a row for exactly those kinds and dispatch no other lane:
Tests runs only when `fast-track:tess` is printed, the consensus slot takes the
backend it names, and gemini goes out only when `fast-track:carl` is on the
list.

## Tests

A card whose `## Tests` section names test files ships its own spec: read those
files and go to Implement. An empty section means the card's `framework` and
`sample_test` drive one test-author dispatch.

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

`TASK_DESCRIPTION` is the goal and the whole `## Files` list, so the author
reads the paths the card creates beside the ones that exist today.
`PUBLIC_INTERFACES` opens only the entries that exist: `cat` on a path the item
has not written yet exits non-zero and takes the render down with it.

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/skills/work/scripts/record_dispatch.py start --kind fast-track:tess --task <item> --prompt-file dev/local/tmp/fast-track-<item>-tests.txt
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

Run the card's first `## Gates` line over the new test files before you commit
them, and watch it come back red. A green suite stops the item with
`stopped: tests-green-before-implementation`. A test that passes before the
implementation exists pins nothing. Commit the tests on their own once that
first gate is red.

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
  --set-cmd ARCHITECTURE_CONTEXT="cat dev/local/tmp/fast-track-<item>-constraints.txt $(printf '%q ' <absolute path of the repo's AGENTS.md>)" \
  --set-file FILE_PATHS=dev/local/tmp/fast-track-<item>-files.txt \
  --set RETRY_INSTRUCTION="" \
  --require-file <each Files entry that exists today> \
  --require-parent <each Files entry the card creates>
```

`FILE_PATHS` is the card's `## Files` list, one absolute path per line, and it
is the whole allowlist. `ARCHITECTURE_CONTEXT` is the card's constraints
followed by the repo's `AGENTS.md`, the conventions no card repeats; a repo
without one hands over its `CLAUDE.md`, and a repo with neither hands over
`/dev/null`, so the `cat` still runs. The implementor receives the failing
tests, that allowlist and that context. It receives no acceptance criteria and
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

Read the card's `changelog` field. Write the entry into `CHANGELOG.md` under
the `## [Unreleased]` heading with the Edit tool when `changelog` is not
`none`, and add `CHANGELOG.md` to the paths the commit names, so the entry
lands in the same commit as the implementation. When `changelog` is `none`,
leave `CHANGELOG.md` untouched.

```bash
git add <each path the footer names>
```

```bash
git commit -m "<type>(<scope>): <description>" -- <each path the footer names>
```

The pathspec after `--` keeps the commit to those paths: every other index
entry stays where it is, staged and uncommitted.

## Gates

Run the card's `## Gates` lines in the order the card lists them, one Bash call
each. The parser already refused a chained gate line, so each one runs on its
own. `suite: per-item` points the test gate at this item's test files. The
repo-wide suite runs once, after the last item, for a card carrying
`suite: batch`; the Exit section is where that run happens.

A gate that exits non-zero stops the item with `stopped: gate <n>`, where `<n>`
is the gate's position in the card's list. No reviewer goes out over a gate the
item has not passed. Write the failing command and its output into the report,
close the open ledger row, and take the item to the exit rule with outcome
`stopped`.

## Roster

Five lenses, no session context. Every prompt is rendered from the card, the
diff and a persona file, so nothing the driver believes about the change reaches
a reviewer.

`${CLAUDE_PLUGIN_ROOT}/skills/fast-track/references/lane-dispatch.md` expands
every lane into its own copyable command block.

Stage the review inputs first. Run `git diff <base-sha>..HEAD` and save its
output to `dev/local/tmp/<item>-fast-track.diff` with the Write tool, then copy
the `## Agent Output Format` section of
`${CLAUDE_PLUGIN_ROOT}/skills/review-work-completion/references/output-formats.md`
to `dev/local/tmp/fast-track-output-format.md`.

Build the context file the implementation-aware lanes read. With the Write tool,
put the card verbatim into `dev/local/tmp/<item>-fast-track-context.md` and add
the changed-file list under a `### Changed Files` heading, then compute the
mechanical facts over those files:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/skills/review-work-completion/scripts/compute_mech_facts.py <each changed file>
```

It prints per-function line counts from `ast`, lists non-Python and unparseable
files as skipped, and always exits 0. Append its stdout to the context file with
the Write tool. A reviewer citing that block cannot get a line count wrong, and
a finding that contradicts it dies at the table instead of costing a rework.

- **Consensus.** `review-fanout.workflow.js` when that file is on disk,
  otherwise the `autopilot:alice` subagent. Inputs: the context file, the staged
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
  --set CONTEXT_FILE=<absolute path of the context file> \
  --set DIFF_FILE=<absolute path of the staged diff> \
  --set PACK_FILE="(no pack available this cycle)" \
  --set-file REVIEW_CHECKLIST=${CLAUDE_PLUGIN_ROOT}/skills/review-work-completion/references/review-dimensions.md \
  --set-file RUBRIC=${CLAUDE_PLUGIN_ROOT}/skills/review-work-completion/references/rubric.md \
  --set-file OUTPUT_FORMAT=dev/local/tmp/fast-track-output-format.md
```

- `agents/alice.md` for the consensus lane, `agents/bob.md` for codex,
  `agents/carl.md` for gemini.
- Bob's prompt is `agents/bob.md` plus Eve's doubt sections, composed the way
  review-work-completion composes it. With the Write tool, append the
  `## Two lenses` and `## Rubric verdicts` sections of
  `${CLAUDE_PLUGIN_ROOT}/agents/eve.md` to the `agents/bob.md` render,
  `dev/local/tmp/fast-track-<item>-codex.txt`, and replace `{PACK_FINDINGS}`
  inside them with `(no pack available this cycle)`.
- `agents/blake.md` takes `--set-file PRD=<absolute path of the staged card>`,
  `--set-file RUBRIC=${CLAUDE_PLUGIN_ROOT}/skills/review-blindly/references/rubric.md`
  and the same `--set-file OUTPUT_FORMAT=`; his render call names no diff at all.
  An unfilled placeholder exits 1, so every one of the three is passed. One
  check from the repo root decides his last run input: `test -L dev/local`
  succeeds, or the root's basename starts with a dot. When either holds, prepend
  a `## Filesystem notes` block to his run inputs, carrying the project root,
  the `dev/local` realpath, and the line that `rg --files` descends into neither
  and so cannot see those files. Two paths and that line, nothing about the
  change: without the block he sweeps a dot-directory with `rg --files` and
  reports real files as missing.
- `agents/eve.md` takes `--set PACK_FINDINGS="(no pack available this cycle)"`;
  append the card, the range `<base-sha>..HEAD` and the changed-file list to the
  rendered file as her run inputs.

Open one row per lane, one Bash call each:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/skills/work/scripts/record_dispatch.py start --kind fast-track:fanout --task <item> --prompt-file dev/local/tmp/fast-track-<item>-consensus.txt
python3 ${CLAUDE_PLUGIN_ROOT}/skills/work/scripts/record_dispatch.py start --kind fast-track:blake --task <item> --prompt-file dev/local/tmp/fast-track-<item>-blake.txt
python3 ${CLAUDE_PLUGIN_ROOT}/skills/work/scripts/record_dispatch.py start --kind fast-track:eve --task <item> --prompt-file dev/local/tmp/fast-track-<item>-eve.txt
python3 ${CLAUDE_PLUGIN_ROOT}/skills/work/scripts/record_dispatch.py start --kind fast-track:bob --task <item> --prompt-file dev/local/tmp/fast-track-<item>-codex.txt
python3 ${CLAUDE_PLUGIN_ROOT}/skills/work/scripts/record_dispatch.py start --kind fast-track:carl --task <item> --prompt-file dev/local/tmp/fast-track-<item>-gemini.txt
```

Send all five lanes in one message: three Task calls and two background Bash
calls, dispatched together, so the roster costs one turn and every lens reads
the same change. In a loop session the Watcher subagent of § Preconditions
(the `Loop session` bullet) goes into that same message: it is what keeps
the session open until the two background lanes finish.

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
  command: ${CLAUDE_PLUGIN_ROOT}/skills/use-codex/scripts/codex-run.sh -f <absolute path of fast-track-<item>-codex.txt> -o <absolute path of codex-output-<item>.txt>
```

```
Bash tool:
  run_in_background: true
  command: ${CLAUDE_PLUGIN_ROOT}/skills/use-gemini/scripts/gemini-run.sh -f <absolute path of fast-track-<item>-gemini.txt> -o <absolute path of gemini-output-<item>.txt>
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
`codex-output-<item>.txt` and `gemini-output-<item>.txt` then, and close every
row: `--outcome ok`, or `--outcome error --detail "exit <n>"` for a CLI lane
that exited non-zero. A lens that reported nothing is a missing lens in the
report, never a pass. One retry per lane, then it counts as failed.

Exit 3 from `codex-run.sh` means codex itself is unavailable, so a re-dispatch
of the same CLI buys nothing. Hand the rendered codex prompt to a
`general-purpose` Task subagent instead and save its return as the codex lane's
output, with the persona's read-only-shell reading instruction replaced by the
same instruction against the `Read` tool. That substitution spends no retry; the
one-retry budget covers every other failure.

Save each subagent lane's returned text once every lane has reported, to
`dev/local/tmp/consensus-output-<item>.txt`,
`dev/local/tmp/blind-output-<item>.txt` and
`dev/local/tmp/doubt-output-<item>.txt`; the CLI lanes write theirs through
`-o`. Then consolidate the roster into one table:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/skills/review-work-completion/scripts/consolidate_findings.py \
  CONSENSUS:$PWD/dev/local/tmp/consensus-output-<item>.txt \
  BLIND:$PWD/dev/local/tmp/blind-output-<item>.txt \
  DOUBT:$PWD/dev/local/tmp/doubt-output-<item>.txt \
  CODEX:$PWD/dev/local/tmp/codex-output-<item>.txt \
  GEMINI:$PWD/dev/local/tmp/gemini-output-<item>.txt
```

Pass only the lanes that reported. The script reads consensus off the number of
pairs it gets and merges two lanes describing one defect at the same file into
a single row. The call carries no `--ledger` flags: this lane keeps no
settled-decisions ledger, so there is nothing to dismiss against. On a non-zero
exit, fix the invocation and retry it once; if that also fails, group the
findings by file yourself and say in the report that the table is model-side.

## Verify

Every CRITICAL and HIGH finding earns one adversarial verification before it
costs a rework. Write the table's rows to
`dev/local/tmp/fast-track-<item>-raised.json` with the Write tool, as a JSON
array of objects with the keys `severity` (`CRITICAL`, `HIGH`, `MEDIUM` or
`LOW`), `title`, `file` and `lane` (the kind that opened the row for the lens
that raised it: `fast-track:fanout` for the consensus workflow,
`fast-track:alice` for the consensus subagent, `fast-track:blake`,
`fast-track:eve`, `fast-track:bob` or `fast-track:carl`). Then ask the rule
which rows earn it:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/skills/fast-track/scripts/fast_track_plan.py verify-targets dev/local/tmp/fast-track-<item>-raised.json
```

It prints those rows as a JSON array, in the order raised: rows the consensus
workflow raised skip this step, because its own verifier already tested them,
and a MEDIUM or a LOW neither reworks nor blocks the exit. It exits 2 on a file
that is anything but that array.

Number the printed rows from 1. For each one, write its
title to `dev/local/tmp/fast-track-<item>-finding-<n>-title.txt`, the evidence
the lane gave to `dev/local/tmp/fast-track-<item>-finding-<n>-evidence.txt` and
the proof it claimed to `dev/local/tmp/fast-track-<item>-finding-<n>-proof.txt`
with the Write tool, then render its prompt:

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

```
Task tool:
  subagent_type: general-purpose
  model: sonnet
  prompt: the contents of dev/local/tmp/fast-track-<item>-verify-<n>.txt
```

Uncertainty refutes; only a shown broken path confirms. Record each refuted
finding in the report and drop it. What survives is the confirmed set.

Zero confirmed rows means zero victor, zero rework and zero delta: skip Rework
and Delta and go straight to Exit. A clean item, one whose roster raised no
CRITICAL or HIGH, never reaches victor either and spends none of the three rows.

## Rework

Rework runs at most once: dispatch a fresh `autopilot:ivan` with the confirmed
findings, the card's constraints and the same allowlist, then run the card's
gates again from the top.

Capture the rework's starting commit before that dispatch:

```bash
git rev-parse HEAD
```

Hold that as `<rework-base-sha>`, so the delta range `<rework-base-sha>..HEAD`
is the rework commit and nothing else.

Write the confirmed findings to `dev/local/tmp/fast-track-<item>-findings.txt`
with the Write tool. That file is the rework's spec, as the test files are
round one's: the fresh implementor reads the findings with no memory of the
code they fault, so it argues with nobody.

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/skills/work/scripts/render_prompt.py ${CLAUDE_PLUGIN_ROOT}/agents/ivan.md \
  --out dev/local/tmp/fast-track-<item>-rework.txt \
  --set-file FAILING_TESTS=dev/local/tmp/fast-track-<item>-findings.txt \
  --set-cmd ARCHITECTURE_CONTEXT="cat dev/local/tmp/fast-track-<item>-constraints.txt $(printf '%q ' <absolute path of the repo's AGENTS.md>)" \
  --set-file FILE_PATHS=dev/local/tmp/fast-track-<item>-files.txt \
  --set RETRY_INSTRUCTION="Rework round. The suite is green; the failing tests above are the reviewers' confirmed findings. Address each one and keep the suite green." \
  --require-file <each Files entry that exists today> \
  --require-parent <each Files entry the card creates>
```

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/skills/work/scripts/record_dispatch.py start --kind fast-track:ivan --task <item> --prompt-file dev/local/tmp/fast-track-<item>-rework.txt
```

```
Agent tool:
  subagent_type: autopilot:ivan
  model: <the card's model>
  prompt: the contents of dev/local/tmp/fast-track-<item>-rework.txt
```

Close the row, stage the paths the `FILES_TOUCHED:` footer names, and commit
them as `fix(<item>): address confirmed findings`, scoped the same way.

```bash
git add <each path the footer names>
```

```bash
git commit -m "fix(<item>): address confirmed findings" -- <each path the footer names>
```

A confirmed finding still standing after the delta review goes to the exit rule.
The lane opens no second round.

## Delta

The rework commit gets one review, scoped to what changed: a single
`autopilot:eve` dispatch over `<rework-base-sha>..HEAD`. No other lane runs
again. Render her prompt from her persona, as in Roster:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/skills/work/scripts/render_prompt.py ${CLAUDE_PLUGIN_ROOT}/agents/eve.md \
  --out dev/local/tmp/fast-track-<item>-delta.txt \
  --set PACK_FINDINGS="(no pack available this cycle)"
```

Append her run inputs to that file with the Write tool: this line first, then
the confirmed findings one per line, then the range `<rework-base-sha>..HEAD`,
its changed-file list and the card.

> This is an incremental review of the rework since the previous cycle. For each
> prior finding listed below, verify it is now resolved in the code, then review
> the scoped diff for any regression the rework introduced.

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/skills/work/scripts/record_dispatch.py start --kind fast-track:delta --task <item> --prompt-file dev/local/tmp/fast-track-<item>-delta.txt
```

```
Task tool:
  subagent_type: autopilot:eve
  prompt: the contents of dev/local/tmp/fast-track-<item>-delta.txt
```

Close the row when she returns. Each confirmed finding she reports unresolved
survives, and any finding she raises on the rework diff joins the surviving
set. The exit rule reads that set.

## Exit

Write the surviving set to `dev/local/tmp/fast-track-<item>-surviving.json`
with the Write tool, in the shape of the raised file: the confirmed findings
still standing after Delta plus any she raised on the rework diff, or `[]` when
nothing survived. Then run the exit rule over it:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/skills/fast-track/scripts/fast_track_plan.py exit-action dev/local/tmp/fast-track-<item>-surviving.json
```

It prints `commit` or `branch`: any surviving CRITICAL or HIGH parks the item
on a branch, and everything else commits.

**Clean.** `commit`: the commits stay on the working branch, and the lane takes
the next card.

**Blocked.** `branch`: a confirmed CRITICAL or HIGH never stays on the working
branch, so park the commits under `fast-track/<item>`, then put the working
branch back where the item started:

```bash
git branch fast-track/<item> HEAD
```

```bash
git reset --keep <base-sha>
```

`git branch` leaves the commits reachable under `fast-track/<item>`, and
`git reset --keep <base-sha>` rewinds the working branch and refuses outright
rather than clobber a foreign change in the tree. A parked item never pushes.
Name the branch and the surviving findings in the report.

Both commands have a failure transition. A `git branch` that exits non-zero
stops the item there: write the command and its output into the report, close
the open ledger row, and end the item `stopped: branch-failed`. When
`git reset --keep <base-sha>` refuses, the item's commits stay on the current
branch, the report says `branch: refused (<paths>)` with the paths git named,
and the item ends `stopped: reset-refused`. Nothing is force-reset either way.

**End of the run.** After the last item, run the `suite: batch` suite once over
the whole repo. With `--push` the lane pushes once, after the last item, and
only over a green batch suite.

## Ledgers

Every dispatch opens a row before it goes out and closes it when it returns, so
the item's cost is measurable per lane:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/skills/work/scripts/record_dispatch.py end <id> --outcome ok
```

`--outcome` takes `ok`, `timeout`, `killed`, `error` or `lost`, and `--detail`
carries the reason. The kinds this lane opens are `fast-track:tess`,
`fast-track:ivan`, `fast-track:fanout`, `fast-track:alice`,
`fast-track:blake`, `fast-track:eve`, `fast-track:bob`, `fast-track:carl`,
`fast-track:victor` and `fast-track:delta`.

One more row closes the item itself, after the exit rule:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/skills/fast-track/scripts/record_item.py --item <item> --card <card.md> --model <model> --started <epoch seconds of the first dispatch> --outcome committed --rework 0 --findings <JSON array of the raised findings> --confirmed <n>
```

`--outcome` is `committed`, `branched` or `stopped`. Pass `--cost` when a
measured USD figure exists; an absent `--cost` records unmeasured, which is not
the same fact as free. The row lands in
`dev/local/autopilot/loop-metrics.jsonl` and its `ledger/` mirror.

Then count what the item spent, out of the rows the `start` calls above
appended:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/skills/fast-track/scripts/fast_track_plan.py count dev/local/autopilot/dispatch-metrics.jsonl <item>
```

It prints one `fast-track:<kind> <n>` line per kind the item opened, sorted by
kind, and exits 2 on a row it cannot parse. Copy those lines into the report as
printed; they are the item's cost per lane.

## Report

Write the item's report to `dev/local/tmp/<item>-fast-track-review.md` with the
Write tool before you say anything in chat. One file per item, holding in this
order:

- the consolidated table `consolidate_findings.py` printed, verbatim;
- one section per lane, carrying that lane's raised findings, or the reason it
  reported nothing;
- the verdict `autopilot:victor` returned on every CRITICAL and HIGH sent to
  Verify, confirmed or refuted, with the evidence that settled it;
- the exit line: the outcome (`committed`, `branched` or `stopped`), the branch
  name when the item is parked, and the findings that survived to put it there;
- for a card carrying `suite: batch`, the result of the repo-wide suite that
  runs once, after the last item: `batch suite: N passed, M failed, K skipped, exit <code>`,
  or `batch suite: not run` with the reason. A consumer of the report (the
  fast-track lane runbook of `/autopilot:run-autopilot`) reads this line and
  never infers green from its absence;
- the dispatch counts per kind, as `fast_track_plan.py count` printed them.

The file is where the numbers stay after the session ends; the chat summary is
a pointer to it.

Then close with one screen:

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
