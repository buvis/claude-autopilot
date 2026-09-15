---
name: design-solution
description: Use when turning a PRD into a reviewed design doc (the HOW) before planning tasks - architecture fit, exact interfaces, reuse, alternatives, then an autonomous adversarial review. Triggers on "design solution", "design this PRD".
argument-hint: "<prd-path> [--rework <review-file>]"
---

# Design Solution

Turn a PRD (the WHAT) into a reviewed implementation design doc (the HOW): module
placement, exact interfaces, data flow, reuse of existing code, and alternatives
weighed - then critique the draft with an autonomous adversarial reviewer before
handing it to `/autopilot:plan-tasks`.

This skill runs **unattended** inside the autopilot build gate. It never asks the
user anything. It is **state-agnostic**: it prints the design doc path on success
and, when unresolved cardinal sins or blockers remain, ends with an explicit
FAILED report naming them (a model-followed skill has no exit code - the report
is the observable signal the caller checks); the caller records the path.

It **never edits the PRD**. The design refines the PRD; acceptance criteria stay
PRD-owned.

## Dependencies

- Own files: `references/cardinal-sins.md` (the severity taxonomy, inlined into
  every reviewer prompt). It ships with this pack; `review-design-doc` keeps its
  own copy for its own use, so edit the two together when the taxonomy changes.
- Pack skills (files read at runtime): `use-codex` (`scripts/codex-run.sh`)
- CLI: `codex` (review dispatch). Unavailable: fall back to the Claude subagent
  reviewer documented in the review step
- Optional: `~/.claude/rules-library/rationalizations.md` (host-local; supplies
  the synonym sets for the reuse sweep). Absent: run the sweep with your own
  verb/noun synonyms and say so in the sweep's summary line.
- Optional: cartographer atlas `~/.local/share/agents/cartographer/projects/<hash>/atlas.md`
  (skipped silently when absent)

## Inputs

- **PRD path** (argument). If omitted, auto-select the single PRD in
  `dev/local/prds/wip/`. Error and stop if `wip/` holds zero or 2+ PRDs
  ("ambiguous - pass the PRD path explicitly").
- **Rework mode** (`--rework <review-file>`): design one review cycle's
  CRITICAL fixes instead of the PRD's first implementation - see
  `## Rework mode`.
- **Architecture context**, loaded when present (skip silently if absent):
  - the cartographer atlas for this repo
    (`~/.local/share/agents/cartographer/projects/<hash>/atlas.md`)
  - `dev/local/meta/project-capsule.md`
  - `AGENTS.md` / `agent_docs/`

## Output

`dev/local/designs/<prd-stem>-design.md`, where `<prd-stem>` is the PRD filename
minus its `.md` extension. Create `dev/local/designs/` if missing - it is a
durable artifact dir, like `dev/local/reviews/`.

In rework mode the output is `dev/local/designs/<prd-stem>-rework-<cycle>-design.md`,
where `<cycle>` is the review file's `review:` frontmatter value.

## Rework mode

`/autopilot:design-solution <prd-path> --rework <review-file>` designs one
review cycle's CRITICAL fixes (PRD 00194). `/autopilot:run-autopilot` Phase 6
invokes it once per cycle, before any fix task is created. Steps 1-5 run as
in default mode except where a bullet below says otherwise.

- **Inputs** (step 1): the PRD, plus from `<review-file>`: `<cycle>` = its
  `review:` frontmatter value, and the CRITICAL rows = every
  `## Consolidated Findings` table row whose Severity cell is `🔴 Critical`.
  `<work_start_sha>` = the left side of the `Diff range:` line in the cycle-1
  review file beside it, `<prd-stem>-review-1.md` (or `-review-01.md`) - under
  autopilot that range is `work_start_sha..HEAD`, so no flag carries it. Run
  `git diff --stat <work_start_sha>..HEAD` for the PRD's whole work range, and
  on cycle 2 or later also `git diff --stat` over `<review-file>`'s own
  `Diff range:` (the prior cycle's rework commits, the range the prior fix
  changed); a `Diff range:` holding a single SHA `X` is read as
  `X..<head_sha>`, `<head_sha>` being `<review-file>`'s frontmatter value. A
  review file with no `🔴 Critical` row, or no cycle-1 review file with a
  `Diff range:` line, is a usage error: print
  `design-solution: --rework needs a 🔴 Critical row and a cycle-1 Diff range` and
  stop without writing a doc.
- **Output**: `dev/local/designs/<prd-stem>-rework-<cycle>-design.md` with the
  same nine sections, same headings, same order as step 3, preceded by one
  source line directly under the H1 title, exactly
  `Source review: <review-file> (head_sha <head_sha>)` - the review file path
  as given and its frontmatter `head_sha`. Phase 6 compares that line before
  reusing a doc, so a design reviewed for one cycle's findings never supplies
  the contract for another's. An existing file at that path is overwritten.
- **`## Architecture fit` opens with a `Prior fix:` paragraph** -
  what the prior fix changed and why it regressed, quoting the CRITICAL rows'
  evidence and the files the prior-cycle `git diff --stat` names, and saying
  whether each CRITICAL was introduced by that fix or only exposed by it. On
  cycle 1 it reads exactly `Prior fix: none - there was no prior rework fix.`
- **`## Interfaces & contracts` is the sole contract source** for the cycle's
  CRITICAL fix tasks: Phase 6 copies it verbatim into each CRITICAL
  `[D{cycle}]` task's `### Contract` block, so name every symbol exactly, and
  open each entry with the 🔴 row it closes (`Closes: <row text>`) so a task
  owner is readable from the shared block.
- **Review** (step 4): the same three-dispatch procedure, the same 3-dispatch ceiling,
  prompt package, minimum-engagement check and Claude fallback, unchanged. The
  prompt additionally carries the CRITICAL rows verbatim so a reviewer judges
  the fix design against the finding it must close.
- **Terminal result line** (step 5): after the exit report is decided, append
  its `result:` value as the last line of `## Review log`, unindented - exactly
  `result: ok` or `result: failed (open cardinal sins/blockers)`. The Review log
  is the ninth section, so this is the doc's last non-empty line; Phase 6 reads
  it as the pass gate. Default mode writes no such line.
- **Exit report**: the first line is `design-solution: <prd-stem> (rework cycle <n>)`
  and `doc:` names the rework path; the remaining lines are unchanged. Open
  cardinal sins or blockers after dispatch 3 end the report with
  `result: failed (open cardinal sins/blockers)` exactly as step 5 describes;
  the caller routes the failure.

## Workflow

### 1. Resolve the PRD and load context

Resolve the PRD path per Inputs. Read the PRD in full. Load the architecture
context files that exist. Identify the capabilities and features the PRD asks for
- these drive the reuse sweep and the interface design.

### 2. Reuse sweep (before designing any new code)

Search the codebase (Bash `rg`; the native Grep tool is absent in this build,
see rules/tools.md) for existing helpers and patterns that already do what the PRD
needs, per the synonym sets in `~/.claude/rules-library/rationalizations.md` (when present)
("Synonyms-to-grep"). For each capability:

- Search **both** the verb and the noun synonyms (e.g. `format` / `render` /
  `serialize` AND `date` / `timestamp`).
- If a search returns nothing, re-run it with a term you know is present to prove
  the pattern works before concluding the helper is absent.

Record findings in `## Reuse inventory`: one entry per existing helper as
**(path + how to use it)**, or, when nothing exists, an explicit
`nothing found, greps tried: ...` line naming the searches you ran.

### 3. Write the design doc

Write `dev/local/designs/<prd-stem>-design.md` with **exactly these nine
sections, these headings, in this order**:

1. `## Architecture fit` - the target layers/modules this work lands in, drawn
   from the atlas / capsule.
2. `## Module placement` - which changes are new files vs edits to existing
   files, with paths.
3. `## Interfaces & contracts` - the exact signatures, types, enum values, field
   names, file/hook kinds, and thresholds. Write these **verbatim-ready**:
   `/autopilot:plan-tasks` copies them byte-for-byte into task `Contract` sections, so name
   every symbol exactly.
4. `## Data flow` - how data moves through the changed components.
5. `## Reuse inventory` - from step 2.
6. `## Alternatives considered` - 2-3 design options, the chosen one, and why.
   One option must be the smallest-diff version of the idea; if the chosen
   design is larger, say what the extra size buys.
7. `## Risks & edge cases` - include the 2-3 likely next changes after this
   PRD and anything in this design that boxes them in.
8. `## Test strategy outline`.
9. `## Review log` - start empty; the review loop (step 4) fills it.

Keep `## Interfaces & contracts` precise enough that a planner who never reads the
PRD could copy a contract verbatim and be correct.

### 4. Autonomous adversarial review (up to 3 dispatches)

Critique the draft with reviewers, then fix what they find. The review runs a
**cross-model** loop: dispatch 1 is a fresh Claude subagent, dispatch 2 is a
**mandatory codex** reviewer (a rival model catches the echo-chamber defects the
authoring model cannot see in itself), and dispatch 3 is a conditional codex
verification pass. Ceiling: **3 dispatches**.

**Each dispatch** sends the reviewer ONE self-contained prompt containing:

- the current draft design doc, and
- a short summary of the PRD (the problem + the capabilities), and
- the **severity taxonomy**:
  - the cardinal-sins list, inlined by reading
    `${CLAUDE_PLUGIN_ROOT}/skills/design-solution/references/cardinal-sins.md` at dispatch
    time (read it and paste its content into the prompt - do **not** copy the
    list into this skill file; that file is this skill's source of truth), plus
  - three-line definitions of the other severities:
    - **Blocking** - a defect that makes the design wrong or unbuildable as
      written; must be fixed before planning.
    - **Non-blocking** - a real concern that does not block planning; record it,
      do not fix it now.
    - **Question** - an ambiguity a competent reader could misread; record it, do
      not fix it now.
  - the calibration rule: **not everything is a blocker** - overflagging dilutes
    signal.

The reviewer returns findings only; it **never edits files**. Each finding has
the shape:

```
{severity: cardinal-sin|blocker|non-blocker|question, title, evidence, suggested_fix}
```

**Dispatch sequence:**

1. **Dispatch 1 - Claude** (fresh subagent). Fix every cardinal sin and blocker
   in the doc.
2. **Dispatch 2 - codex** (mandatory, cross-model). It **always runs,
   even when dispatch 1 found zero blockers** - that clean-dispatch-1 case is
   exactly where a second, rival-model opinion matters most. Fix every cardinal
   sin and blocker.
   Run codex as a **direct background Bash command** (never a Task subagent - a
   subagent that shells out to a CLI hangs), absolute paths:
   ```
   Bash tool (run_in_background: true):
     ${CLAUDE_PLUGIN_ROOT}/skills/use-codex/scripts/codex-run.sh -f "{codex_prompt_file_abs}" -o "{abs_repo_path}/dev/local/tmp/design-codex-output-{id}.txt"
   ```
   codex is **read-only** by default (no `-a`/`-y` -> `--sandbox read-only`) and
   never edits files; the prompt is self-contained (the same package the Claude
   reviewer gets), so no `-d`. When the background command completes, read the
   `-o` output file for codex's findings.
3. **Dispatch 3 - codex verification** (conditional). Runs **only if dispatch 2
   found cardinal sins or blockers**; a fresh codex call is acceptable. Open
   cardinal sins/blockers remaining after it terminate the review non-zero (step 5).

**Claude fallback on codex outage.** If codex is unavailable - `codex-run.sh`
missing/non-executable, it exits non-zero, the timed wait ceiling trips, or its
output is unparseable as findings - degrade that dispatch to a fresh Claude
reviewer subagent (identical prompt). Append, loudly, `dispatch <n>: codex
unavailable, Claude fallback` before its summary line, and use the reviewer token
`claude-fallback` in that line. **Never PAUSE on a codex outage** - the review
completes unattended either way (mirrors Phase 8's codex-with-Claude fallback).
The fallback rule applies to every codex dispatch (2 and 3).

**After each dispatch:**

- Fix **every** cardinal sin and blocker by editing the design doc, then proceed
  to the next dispatch (up to the 3-dispatch ceiling).
- Append every non-blocker and question to `## Review log` (do **not** fix them).
- Append a one-line summary of the dispatch to `## Review log`, in this **exact
  pinned format** (one line per dispatch, so the run-autopilot Phase 1.5 execution
  gate can match it with a single fixed pattern):
  ```
  dispatch <n> (<claude|codex|claude-fallback>): cardinal-sin <c>, blocker <b>, non-blocker <nb>, question <q>
  ```
  `<n>` is the dispatch number; `<c>/<b>/<nb>/<q>` are per-severity integer
  counts; the reviewer identity token is exactly one of `claude`, `codex`,
  `claude-fallback` (dispatch 1 -> `claude`; dispatch 2 -> `codex` or
  `claude-fallback`; dispatch 3 -> `codex` or `claude-fallback`). A dispatch
  marked WEAK by the minimum-engagement check below appends ` weak` to the end
  of this line (after `question <q>`) — the Phase 1.5 gate pattern still matches,
  it is not `$`-anchored.

**Minimum-engagement check (mirrors review-with-doubt's "fewer than 3 doubts = look harder").** A rubber-stamp review is worse than none — it reads as coverage that never happened. After a substantive dispatch (1, 2, or a dispatch-3 that ran), test it for engagement: it is **under-engaged** when it returns **fewer than 3 total findings** OR **not one finding anchors to a specific design-doc section or `file:symbol`** (real design review cites where — e.g. "`## Interfaces & contracts` declares `foo(x: int)` but the PRD says `str`"). On under-engagement, **re-dispatch that same reviewer ONCE** with a sharper prompt: name the specific sections/interfaces/modules it must inspect and require every finding — and every "checked, correct" note — to cite a doc section or `file:symbol`. This engagement re-run is a per-dispatch quality retry (capped at one per dispatch); it does **not** consume the 3-dispatch cross-model ceiling, so the mandatory codex dispatch still runs. If the re-run **still** shows no section-anchored evidence (it could not show it engaged), mark that dispatch **WEAK**: append ` weak` to its `## Review log` line and list it in the exit report. WEAK is advisory — it flags low confidence, it does not by itself fail the review. A thorough zero-blocker review that cites the sections it verified is NOT weak; engagement, not raw finding count, is the test after the re-run.

Bound each codex dispatch with a concrete deadline, not an open-ended wait.
After the `run_in_background: true` launch the harness re-invokes you with a
`<task-notification>` carrying the codex `-o` output path the moment it
finishes — `Read` that file for the findings (background Bash tasks return
their output path in the tool result and notify on completion; the old
blocking-wait tool is deprecated). If no completion notification has arrived within the ~10-min×2
deadline for helper-script Bash dispatches (`work/references/subagent-dispatch.md`),
treat the dispatch as a codex outage and take the Claude fallback above. A hung
reviewer must never block an unattended run (the autopilot session wall-clock
cap is the backstop).

### 5. Terminate

- **All cardinal sins and blockers resolved** (or none found): print the design
  doc path and the exit report, exit 0.
- **A cardinal sin or blocker is still open after dispatch 3**: print the design
  doc path, list every open cardinal-sin / blocker finding, print the exit
  report, and **exit non-zero**. The caller (autopilot) treats this as a
  sub-skill failure and PAUSEs; a manual run surfaces the open findings to the
  user.

## Exit report (always printed)

```
design-solution: <prd-stem>
  doc: dev/local/designs/<prd-stem>-design.md
  reviewer dispatches: <n>/3
  findings: cardinal-sin <c>, blocker <b>, non-blocker <nb>, question <q>
  open cardinal sins/blockers: <none, or a list>
  weak dispatches: <none, or a list of dispatch numbers flagged by the minimum-engagement check>
  result: ok | failed (open cardinal sins/blockers)
```

The exit report always lists the iteration count (reviewer dispatches) and the
per-severity finding counts.

In rework mode the first line reads `design-solution: <prd-stem> (rework cycle <n>)`.

## Notes

- One reviewer dispatch per loop iteration; never two in flight at once.
- The skill writes only the design doc (and creates `dev/local/designs/`). It
  never edits the PRD, the task list, or autopilot state.
- Downstream blind review and doubt review stay PRD-only by design; this design
  doc feeds `/autopilot:plan-tasks` and the work-completion review, not the spec-only
  surfaces.
