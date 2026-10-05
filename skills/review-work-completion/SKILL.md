---
name: review-work-completion
description: Use after all tasks are completed to validate implementation against PRD requirements via multi-agent consensus review; for a spec-only blind lens use review-blindly. Triggers on "review work", "check completed work", "are we done".
compatibility: "Requires Bob personal Claude/autoclaude environment or equivalent host adapters for sub-agents, state, and review handoffs."
---

> **Paths in this pack.** This pack's root is `${CLAUDE_PLUGIN_ROOT}` - that line
> is substituted when this skill loads, so what you just read is the real
> directory. Files under `references/` are read at runtime and are **not**
> substituted: when one shows `${CLAUDE_PLUGIN_ROOT}/...`, swap in the root above
> before running anything. Never pass the literal placeholder to a shell - it
> expands to the empty string and the path silently becomes `/...`.

> Claude reviewer effort: Alice and Blake use their named agent definitions
> with `effort: high`. If rendering their persona into a generic prompt, dispatch
> it through `autopilot:worker-opus` (high effort), passing the source-selected
> reviewer model explicitly. External Claude reviewers pass `--effort high`.
> Preserve all lenses, isolation, rubrics, and the independent provider voice.

# Review Work Completion

## What This Does

Validates completed implementation work against PRD requirements using independent AI reviewers (tools may change in the future). Each reviewer analyzes the code changes and PRD criteria separately, then findings are consolidated by consensus - issues flagged by multiple reviewers get higher priority. Under autopilot, the decision gate in `run-autopilot/references/phase-review.md` turns the findings into follow-up tasks.

**Why multiple reviewers:** Different models catch different issues. Consensus scoring surfaces real problems while filtering noise from single-model false positives.

> **Note for anyone reviewing/auditing this skill:** See `references/design-rationale.md` for settled design decisions
> before suggesting changes. This doesn't apply to skill users, as it doesn't add any useful information
> to perform the skill.

## Dependencies

Step 1 (Validate prerequisites) owns the reviewer-CLI checks and their
degradation rules - see it, this list does not repeat them. What step 1 does
not name:

- Personal skills: `use-codex` (hard - `scripts/codex-run.sh`, STOP if missing)
- The agent registry `${CLAUDE_PLUGIN_ROOT}/agents/` (hard - every reviewer prompt is
  assembled from it; conventions and the roster in
  `references/agent-registry.md`). A missing or unparseable roster file is a
  failed reviewer, never a fallback prompt.
- Files read from other skill dirs:
  - `${CLAUDE_PLUGIN_ROOT}/skills/review-blindly/references/rubric.md` - inlined into
    Blake's blind prompt at its `{RUBRIC}` placeholder
- CLIs: `python3`, `git`
- Optional (graceful degradation, detailed in step 1): `use-gemini`

## Reviewers

Every review cycle runs all lenses (PRD 00015) — consensus, blind, and doubt
are prompt disciplines carried by the roster, not separate phases:

- **Alice** → Claude subagent (direct, not nested CLI); implementation-aware consensus lens. Her leg runs on the engine the PRD's `consensus_engine` flag selects (step 1): the legacy single subagent by default, or the `review-fanout` workflow — dimension fan-out, dedup, adversarial verification — when the flag opts in
- **Blake** → Claude subagent, **blind lens**: PRD-only prompt — no diff, no file list, no review history, no design doc (persona: `agents/blake.md`)
- **Bob** → Codex, **doubt lens**: carries the doubt rubric (D1-D5) and the de-slop lens every cycle; when codex is unavailable, a Claude subagent runs the same prompt so the lens never silently drops
- **Carl** → Gemini (frontend & design specialist; skipped when the Gemini CLI is unavailable)
- **Eve** → Claude Fable 5 Task subagent, opt-in fifth lens: joins the batch when the resolved doubt reviewer says so (step 1), running the same doubt prompt as Bob (see `references/agent-invocation.md` "Eve (Fable 5)"); absent otherwise

## Workflow

### 1. Validate prerequisites

Check these exist:

1. `${CLAUDE_PLUGIN_ROOT}/skills/use-codex/scripts/codex-run.sh` - executable
2. `docs/dev/project-management/prds/wip/` contains at least one `.txt` or `.md` file

(Alice is a native Claude subagent - no CLI prerequisite.)

**Ambiguous-target guard (standalone runs).** This skill reviews **one** PRD's work per run. When NO autopilot state names the PRD — `docs/dev/project-management/autopilot/state.json` is absent or carries no `prd` field (a manual/standalone `/autopilot:review-work-completion`) — AND `docs/dev/project-management/prds/wip/` holds **2+** PRDs, the target is ambiguous. Do NOT merge them into one review:

- **Interactive:** name every wip PRD and ask which to review via `AskUserQuestion`; scope the run to the chosen one (its path is the "review-target PRD" step 3 reads).
- **Unattended (`CLAUDE_UNATTENDED` set, or otherwise no human to ask):** STOP and report the ambiguity, naming all wip PRDs — never guess which one (`rules/communication.md` unattended rule).

Under autopilot, `state.prd` names the PRD, so this guard does not apply — review that PRD's work. A single wip PRD is unambiguous and passes straight through.

**Optional - Carl (Gemini), batch check first:** read
`state.batch.unavailable_reviewers` before probing any binary. Missing field
means `[]`. When it contains `carl`, Carl is inactive for this cycle: no dispatch,
no retry, and no `ui` key in `state.review_lenses` when step 3 replaces the lens
roster. Retain `state.batch.unavailable_reviewer_details.carl` as the skip origin
for step 6 and omit Carl from `reviewers:`. This applies to every later cycle
and PRD in the same batch. On a standalone run with no `state.json`, do not
create state; fall through to the binary check below.

**Carl binary check (only when not batch-skipped):** check `${CLAUDE_PLUGIN_ROOT}/skills/use-gemini/scripts/gemini-run.sh` is executable AND a backend CLI resolves - `copilot` (preferred; pin owned by the helper) OR native `gemini` (`mise which`/`command -v` succeeds for either). If both pass, Carl is active; binary presence alone does not establish model availability. If neither CLI resolves, skip Carl and record `Carl: unavailable (no backend CLI)` in the final review file. Do not run a live probe here; the opt-in operator probe lives in `use-gemini/SKILL.md`. Step 5 classifies dispatch results: exit 4 records `Carl: permanently unavailable` with the stderr reason; a quota or other runtime failure records a one-off failure. Carl on copilot spends Copilot AI credits.

Create if missing: `docs/dev/tmp/`, `docs/dev/project-management/reviews/`

**Path convention:** All `docs/dev/project-management/` paths in this skill are relative to the project root. When passing file paths to subagents or external scripts, always use absolute paths (e.g. `$PWD/docs/dev/tmp/...`) so they resolve correctly regardless of the subagent's working directory.

**Resolve the consensus engine.** Alice's leg runs on one of three engines. Read `state.consensus_engine` from `docs/dev/project-management/autopilot/state.json` (autopilot parses the PRD frontmatter once, at Phase 0); on a standalone run with no state file, read `consensus_engine` straight from the wip PRD's frontmatter.

| value | Alice's leg |
|-------|-------------|
| `legacy` (default — also every absent or invalid value) | Today's single Task subagent. No Workflow call, nothing else changes. |
| `workflow` | The `review-fanout` workflow **is** Alice's leg (step 5). |
| `shadow` | Both. Legacy Alice gates the cycle; the workflow runs beside her, non-gating, and its result is recorded as an observation (step 8). |

An invalid value falls back to `legacy` with one logged warning line (same rule as `rework_cap` / `doubt_reviewer`). Hold the resolved value as `CONSENSUS_ENGINE` for steps 5 and 8.

**Resolve the doubt reviewer.** Read `state.doubt_reviewer` from `docs/dev/project-management/autopilot/state.json`; on a standalone run with no state file, read `doubt_reviewer` straight from the wip PRD's frontmatter. An invalid value falls back to `codex` with one logged warning line. Hold the resolved value for the later roster and consolidation steps. Eve joins the batch when the resolved value is `fable`.

**Codex doubt-roster guard.** After resolving `doubt_reviewer`, when `docs/dev/project-management/autopilot/state.json` exists and `any(state.tasks[]?.attempts[]?.implementor == "codex")` is true, force the resolved value to `fable` — the doubt leg must not be codex alone. This adds **Eve** as the fifth lens alongside Bob; Bob/codex still runs, so the guard adds a voice rather than removing one. This override is in-memory only: do NOT write `state.doubt_reviewer` or invoke `statectl` for it. The stored field keeps whatever Phase 0 parsed, and Phase 0 remains its single writer. Count the codex-implemented tasks for step 6's review-file record.

`/autopilot:work` writes `attempts[].implementor` into the same `state.json` via `statectl`, whether invoked directly or under autopilot, so the guard fires on this path too whenever the file exists. The real gap: `state.json` exists only from `/autopilot:run-autopilot`'s Phase 0 (which creates it) until batch end (which deletes or archives it), so a PRD that never ran under autopilot, or whose batch has already closed, leaves the guard with no attempts record to consult.

**If CLI/script check fails, STOP and report:**

```text
Cannot proceed: {missing prerequisite}
```

### 2. Check task status

Read `state.tasks` from `docs/dev/project-management/autopilot/state.json` (walk up from cwd to find the autopilot dir) — it is the canonical, complete task store, so nothing needs hydrating first. The gates below read each entry's `status`; an empty `state.tasks`, or an absent state file (a standalone run has none), is "no tasks exist".

**If no tasks exist:** proceed without task context, noting the absence in the review file.

**If ANY task is `in_progress`:** STOP and report:

```text
Cannot review: {N} task(s) still in progress
- Task {id}: {subject}
```

**If ALL tasks are `pending`:** STOP and report:

```text
Cannot review: no completed tasks found. Complete tasks first.
```

### 3. Gather context

Read the **review-target PRD** from `docs/dev/project-management/prds/wip/` — `state.prd`'s PRD under autopilot, the PRD step 1's ambiguous-target guard resolved on a standalone multi-PRD run, else the single wip PRD. Extract success criteria, acceptance criteria, required features. (Only when the target is genuinely one PRD and wip legitimately holds several — an autopilot batch mid-flight — read the others for cross-PRD context, but scope the review to the target.)

**Determine review scope (full vs incremental).** List existing review files for this PRD with Bash `ls` (the native `Glob` tool is absent in this build): `docs/dev/project-management/reviews/<prd-name>-review-*.md` (PRD filename without the `.md` extension).

- **No prior review file** → cycle 1, a **full review**. When `state.work_start_sha` is set in `docs/dev/project-management/autopilot/state.json` (running under autopilot), pass `--since <state.work_start_sha>` to `review-stage` — the PRD's whole work range, the same value `COVERAGE_DIFF_RANGE` uses below. Without it, the `gather-context.sh` run inside `review-stage` diffs against the detected base branch, which is empty (and refused with exit 3) for a repo worked on directly on that branch. Without `state.work_start_sha` (an interactive, non-autopilot run), omit `--since`.
- **A prior review file exists** → this is a rework cycle, an **incremental review**. Read the highest-numbered prior file's `head_sha` frontmatter field.
  - `head_sha` present → pass `--since <head_sha>` to `review-stage`. The diff then covers only the rework commits since that cycle, not the whole PRD branch — the prior cycle already reviewed the full diff. Also read that file's consolidated findings; step 4 hands them to the reviewers to verify.
  - `head_sha` absent (file predates this field) → fall back to a full review (omit `--since`).
  - Also read that same prior file's `codex_thread_id` frontmatter field (stamped in step 8 of the prior cycle). Present → step 5 adds `--resume-thread <codex_thread_id>` to Bob's launch so codex resumes his prior session instead of re-reviewing from zero. Absent (pre-change file, or Bob was skipped / thread-id capture failed last cycle) → Bob runs a fresh review, no resume flag.

Capture the current HEAD now — `git rev-parse HEAD` — and hold it; step 8 stamps it into this cycle's review file as `head_sha`.

Also capture the diff range for the review scope (recorded in the review file; the doubt lens reviews this range). For an **incremental review** the diff range is `<prior-cycle-head-sha>` (the same SHA passed to `review-stage --since`). For a **full review**: when running under autopilot and `state.work_start_sha` is set in `docs/dev/project-management/autopilot/state.json`, use `<work_start_sha>..HEAD` (the PRD's whole work range — this is the scope the doubt lens reviews); otherwise compute it via `git merge-base HEAD origin/HEAD` (fallback: `git merge-base HEAD master`, then `git merge-base HEAD develop`). Store this as `COVERAGE_DIFF_RANGE`.

**Stage the cycle with one call (PRD 00249).** From the project root, run:

```bash
autopilot review-stage --cycle-id {id} --state docs/dev/project-management/autopilot/state.json --gate-command "<project gate command>" --roster <personas> [--since <sha>] [--replay-cmd "<per-file pytest invocation>"] [--settled-ledger <path>] [--prior-findings <path>]
```

- `{id}`: one id for the whole cycle (a timestamp or UUID; letters, digits, `.`, `_`, `-` only). Every `docs/dev/tmp/review-*-{id}.*` file, every prompt and every `-o` output path in step 5 shares it.
- `--gate-command`: the project's full test-gate command (this pack: `dev/bin/release-checks`). `review-stage` reuses `last-verification.json` when it still certifies HEAD, else runs this command once.
- `--roster`: comma-separated persona names of the reviewers step 1 made active: `alice,blake,bob`, plus `carl` when Carl is active and `eve` when the resolved doubt reviewer is `fable`. Always pass it: without it the CLI derives the roster from `state.review_lenses`, which knows neither Carl's batch skip nor his binary check.
- `--since`: per the scope rules above; omit it for a full review with no `state.work_start_sha`.
- `--replay-cmd`: the project's per-file pytest invocation (`python3 -m pytest`, unless the project runs one test file another way; this pack: `uv run --no-project --with pytest python -m pytest`). Omitting it skips the fail-first replay.
- `--settled-ledger`, `--prior-findings`: pass the ledger path and the prior-findings path you already loaded straight to this call; `review-stage` builds the ledger/incremental block itself for every consensus/doubt-lens persona that is supposed to see it. Blake's blind-lens prompt deliberately stays history-free: his branch never reads the ledger or the incremental block, by design.

**Standalone runs (no `state.json`).** Drop `--state` and pass what it would have supplied: `--tasks-json <file>` (a JSON array of `state.tasks`-shaped objects — `id`, `name`, `status`, `description`, plus `commit` and `companions` for a folded task — or `[]` when step 2 found no tasks; write it to `docs/dev/tmp/review-tasks-{id}.json` with the Write tool), `--prd <absolute path of the review-target PRD>`, and `--design-doc docs/dev/project-management/designs/<prd-stem>-design.md` when that file exists (`<prd-stem>` = the wip PRD filename minus `.md`). Under `--state`, `review-stage` reads `state.prd`, `state.tasks` and `state.design_doc` itself and refuses those three flags.

**What the call does** (`skills/run-autopilot/cli/review_stage.py`; it runs the existing scripts unchanged):

- Writes `docs/dev/tmp/review-tasks-{id}.md`, **one row per task — never merged**: a task folded into another's commit keeps its own row with the shared commit and companion task ids, so the cycle-N task→commit table stays unambiguous.
- Writes `docs/dev/tmp/review-prd-{id}.md`: the PRD, plus the design doc's full text under `## Design Doc` when one exists, so reviewers can tell "implemented as designed" from drift. The PRD remains the requirements authority. Blind review and doubt review must stay PRD-only (a blind reviewer tests requirements without design bias), so the design doc belongs on neither surface.
- Runs `gather-context.sh` with your `--since`, which writes the context and diff files to `docs/dev/tmp/`.
- Appends to the context file the mechanical-facts block (`compute_mech_facts.py`, PRD 00095: per-function line counts from `ast`, so a reviewer citing it cannot get a line count wrong, and step 6's gate discards any finding that contradicts it), then the two mechanical test checks: `detect_tautological_tests.py` (test functions whose shape cannot fail) and, with `--replay-cmd`, `replay_tests_against_base.py` (changed tests that PASS against the pre-change code, so they do not pin this change). Every `[MECH]` line in those two blocks is a finding step 6 absorbs, and they are Eve's fifth run input (step 4).
- Builds this cycle's engram context pack at `docs/dev/tmp/engram-pack-{id}.md` and appends its "Findings precedent" section, then the test-gate `Tests:` line.
- Renders every roster prompt (step 4).
- With `--state` only: REPLACES `state.review_lenses` with one `"running"` key per active lens (tracon renders these as the review phase's sub-steps; step 6 flips them to `"done"`/`"failed"`), and opens one dispatch row per CLI reviewer on the roster (`record_dispatch.py start --kind bob|carl --task review-{id}`).

**Read its summary.** It prints one JSON line on stdout. Hold these keys:

- `context_file`, `diff_file`, `prd_file`, `tasks_file`: the staged inputs (`diff_file` is `null` when no diff was written).
- `prompts`: `{persona: prompt path}`. A `null` value means that reviewer failed (step 4).
- `dispatch_rows`: `{"bob": id, "carl": id}` for step 6's `end` calls; `null` where no row was opened.
- `pack`: `"ok"` or `"failed (<reason>)"`. A failure is non-fatal and never blocks the cycle: the prompts already carry `(no pack available this cycle)` for `{PACK_FILE}` and `{PACK_FINDINGS}`; note the failure in the review file. A review without the pack is degraded, not invalid. Blake never receives a pack, by design.
- `gate.tests_line`: this cycle's computed counts. Step 6 still composes the `Tests:` line; when this run parsed counts it wrote `last-verification.json` at HEAD, so step 6 reuses that record instead of running the suite again.
- `errors`: every best-effort failure (lens stamp, dispatch row). Name each one in the review file.

Pass every staged path to subagents and CLIs as an absolute path (resolve a relative one against the project root): subagents misresolve relative `docs/dev/project-management/` paths as `~/docs/dev/project-management/`.

**A non-zero exit stages nothing to review.** Read its stderr. Exit 3 is `gather-context.sh` refusing an empty diff (no base branch, or nothing since `--since`): a review of nothing must never converge, so fix the range (e.g. pass `state.work_start_sha`) and re-run once, else STOP and report. Exit 1 or 2 is a usage or input problem (a bad `--cycle-id`, a standalone flag beside `--state`, an unreadable state or tasks file): fix it and re-run once, else STOP and report.

**Read the settled-decisions ledger (PRD 00095).** Read `docs/dev/project-management/reviews/<prd-stem>-ledger.json` (`<prd-stem>` = the review-target PRD's filename minus `.md`; absent on cycle 1, which is normal). When it exists and parses, hold its entries for step 4 — they become the "Settled decisions — do not re-raise" section of the implementation-aware prompts — and hold the path for step 6's `--ledger` flag. A malformed ledger is logged and skipped, never fatal.

**Bare-repo homes (e.g. `~/.buvis`: `git --git-dir=~/.buvis --work-tree=~`) — the fallback path.** `gather-context.sh` assumes a normal checkout, so `review-stage` fails here — do not fight it. Stage the cycle by hand instead; `review-stage` stays primary for normal repos.

1. Generate the diff with `git --git-dir=<bare-dir> --work-tree=<tree> diff <COVERAGE_DIFF_RANGE>` (the range captured above), and write it plus the tasks, PRD and context files to `/tmp/` with the Write tool (tasks one row per task, as above).
2. Append the mechanical blocks to that context file, passing the changed-file list you built: `python3 ${CLAUDE_PLUGIN_ROOT}/skills/review-work-completion/scripts/compute_mech_facts.py <changed file>...`, then `python3 ${CLAUDE_PLUGIN_ROOT}/skills/review-work-completion/scripts/detect_tautological_tests.py <changed file>...`. Both need only readable paths and always exit 0. The fail-first replay is skipped: there is no worktree to add.
3. Run `git rev-parse --show-toplevel` from the project root with no extra flags. The pack resolves `repo_root` the same way, and here it exits non-zero, so `engram pack` is never attempted: substitute `(no pack available this cycle)` for `{PACK_FILE}` and `{PACK_FINDINGS}` and write `pack: skipped (no git worktree)` in the review file — a skip, not a failure, and no retry.
4. Render the prompts per step 4's fallback, and under autopilot open the roster and dispatch rows per step 5's fallback.

### 4. Prepare agent prompts

The `review-stage` call in step 3 already rendered one prompt per roster
persona to `docs/dev/tmp/{agent}-prompt-{id}.md`; their absolute paths are its
summary's `prompts`. Do not author prompt files: the settled decisions and the
incremental addendum below are `review-stage` flags, not hand edits (only the
bare-repo fallback appends them by hand).

**Every prompt is assembled from the agent registry.** `review-stage` reads the
persona's file under `${CLAUDE_PLUGIN_ROOT}/agents/`, strips its frontmatter,
and substitutes its placeholders through `work/scripts/render_prompt.py` — the
substitution table and the conventions live in `references/agent-registry.md`.
There is no fallback prompt: a persona whose prompt is `null` in `prompts` is a
failed reviewer, handled by `references/retry-policy.md`.

**Fail-closed preflight.** Before rendering, `review-stage` verifies every
roster persona's file exists and its frontmatter carries non-empty `name`,
`description` and `tools`. A persona that fails it, or whose render fails
`render_prompt.py`'s placeholder check, never gets a prompt file written.

**Settled decisions — do not re-raise (PRD 00095).** When step 3 loaded ledger
entries, pass `--settled-ledger <path>` on the step-3 `review-stage` call; it
renders the settled-decisions section into **Alice's, Bob's, Carl's and Eve's**
prompts itself (Blake excluded), one line per entry (`disposition`, `severity`,
`issue`, `file`, `reason`), under the heading
`## Settled decisions — do not re-raise`:

> These calls were already made in an earlier cycle of this same review, with
> the reasons given. Do not re-raise them. Raise a NEW finding only if you can
> show the settled reason no longer holds.

**Blake never receives it.** His prompt is PRD-only by design, and a blind lens
fed the review's own history is no longer blind. His re-raises are absorbed
mechanically instead, by step 6's `--ledger-dismiss BLAKE`.

**Filesystem notes — Blake only (PRD 00141).** `review-stage` runs one check
on the project root: `test -L docs/dev/project-management` succeeds, OR the root's basename starts with `.`.
When either holds, it adds a `## Filesystem notes` block to Blake's run inputs
carrying the project root, the `docs/dev/project-management` realpath, and the sentence telling
him `rg --files` reaches neither. Paths only — no diff, no file list, no
review history, so the blind lens stays blind. The verbatim block lives in
`references/agent-invocation.md` § Blake: Filesystem notes.

Per persona (the table `review-stage` applies):

| Persona | Source | Substitutions |
|---------|--------|---------------|
| Alice | `agents/alice.md` | `{CONTEXT_FILE}`, `{DIFF_FILE}`, `{PACK_FILE}`, `{REVIEW_CHECKLIST}`, `{RUBRIC}`, `{OUTPUT_FORMAT}` |
| Bob | `agents/bob.md` (carries the sandbox appendix) **plus** the "Two lenses" and "Rubric verdicts" sections of `agents/eve.md` appended | same as Alice (including `{PACK_FILE}`), plus `{PACK_FINDINGS}` |
| Carl | `agents/carl.md` (carries the frontend & design appendix) | same as Alice |
| Blake | `agents/blake.md` | `{PRD}` and `{RUBRIC}` (from `review-blindly/references/rubric.md`) **only** — no context file, no diff file, no incremental addendum; blind every cycle. Run inputs gain the `## Filesystem notes` block when this project's trigger holds (above) |
| Eve | `agents/eve.md` | `{PACK_FINDINGS}`; the PRD, diff range, changed-file list, the pack's Findings-precedent section and step 3's two mechanical test-check blocks are appended as her five run inputs (see `references/agent-invocation.md`) |

**For an incremental review** (step 3 found a prior cycle): pass `--prior-findings <path>` on the same call; it adds the addendum to Alice's, Bob's, Carl's and Eve's prompts — the prior cycle's consolidated findings, plus this instruction. Blake is blind every cycle and never gets it.

> This is an **incremental review** of the rework done since the previous review cycle — the diff is scoped to changes since then. Two jobs: (1) for each prior finding listed below, verify it is now resolved in the code; (2) review the scoped diff for any regression the rework introduced. You need not re-review unchanged code; the previous cycle already reviewed the full implementation.

**Bare-repo fallback (step 3's carve-out).** With no `review-stage` run, run the same fail-closed preflight yourself, then render each active persona with `python3 ${CLAUDE_PLUGIN_ROOT}/skills/work/scripts/render_prompt.py <persona file> --out <absolute prompt path> --set-file <PLACEHOLDER>=<value file>` per the table above, the paths pointing at the `/tmp` inputs. For Bob, the persona file is a `/tmp` copy of `agents/bob.md` with the two `agents/eve.md` sections appended; Eve's run inputs and Blake's Filesystem notes go after the render. A non-zero exit fails that reviewer. Then make the same two appends (settled decisions, incremental addendum) by hand: with no `review-stage` run there are no flags, so on this path they remain hand edits.

### 5. Run agent review

**Use the staged prompts.** Each reviewer runs on its prompt path from step 3's summary `prompts` (absolute). A reviewer whose prompt is `null` is not dispatched; it counts as failed per `references/retry-policy.md`. Under autopilot, `review-stage` already stamped `state.review_lenses`.

**Launch ALL active reviewers in a SINGLE message so they run concurrently.** Alice, Blake, and Eve (when active) are Task subagent calls (native Claude tools), dispatched as `autopilot:alice`, `autopilot:blake`, `autopilot:eve` - the bare persona name is not a registered agent type and fails the dispatch outright (`references/agent-registry.md` § Dispatch mechanism). Every one of those Agent calls, and the Watcher below, carries `run_in_background: true` - never `false`, never omitted: an Agent dispatched with `run_in_background: false` makes the harness hold the background Bash calls in the same message until that Agent returns, while the Watcher only returns once those Bash lanes have written their outputs, so one `false` idles the cycle for the Watcher's whole 30-run budget (~50 min, seen twice on 2026-09-26). Bob and Carl are parallel **background Bash** commands (`run_in_background: true`) - never wrap a CLI reviewer (codex/gemini) in a subagent, it hangs and strands the whole cycle (see `references/agent-invocation.md`). Put the Task calls, the Watcher (below, if `$_AUTOPILOT_LOOP` is set), and the background Bash calls in the one message - if any CLI reviewer is in the dispatch, the Watcher goes in the same message or nothing holds the session open to see it finish.

**Ledger each CLI reviewer dispatch.** Under autopilot, `review-stage` already opened one dispatch row per CLI reviewer; hold its `dispatch_rows` ids for step 6's `end` call. Open a row by hand with `python3 ${CLAUDE_PLUGIN_ROOT}/skills/work/scripts/record_dispatch.py start --kind bob --task review-{id} --prompt-file <absolute prompt path>` (`--kind carl` for Carl), and hold the printed id, in three cases: a dispatched CLI reviewer whose `dispatch_rows` id is `null` (the failure is in `errors`), a retry (`references/retry-policy.md`), which opens a second `start` row under the same `--task`, and the bare-repo fallback.

**Bare-repo fallback (step 3's carve-out), autopilot runs.** With no `review-stage` run, also REPLACE `state.review_lenses` yourself (merge into state.json, do NOT replace sibling fields) with one key per active lens set to `"running"`: `consensus` (Alice), `blind` (Blake), `doubt` (Bob), plus `ui` (Carl) and `fable` (Eve) only when active. tracon renders these as the review phase's sub-steps; step 6 flips them to `"done"`/`"failed"`.

**Eve unavailable (codex doubt-roster guard active).** When Eve's dispatch fails after her one-retry budget (`references/agent-invocation.md` for the retry/unavailability semantics), dispatch a Claude Task subagent with Bob's exact assembled doubt prompt as a substitute for her, so a non-codex doubt voice still exists, and use its output as Eve's. Step 6 records which of the three `codex_rung_guard` outcomes resulted.

**Watcher (headless keep-alive — dispatch only when `$_AUTOPILOT_LOOP` is set).** Headless `claude -p` kills background Bash tasks ~5s after the final result; only a live subagent holds the session open (2026-07-12 loop death: every Claude subagent reviewer finished first, the CLI exited at turn end and killed codex mid-review, the loop halted). So in the SAME dispatch message, launch one extra Task subagent named Watcher (general-purpose, `run_in_background: true`) whose entire prompt is:

> Run `python3 ${CLAUDE_PLUGIN_ROOT}/skills/review-work-completion/scripts/await_reviewer_outputs.py --budget 100 <absolute -o output path of each CLI reviewer dispatched>` as a foreground Bash call. If the last stdout line is `WAITING`, run the same command again — up to 30 times total. Return the script's final output verbatim (`DONE`, or `WAITING` plus the pending files after 30 runs). Do nothing else: no reading the output files, no review commentary.

The Watcher is scaffolding, not a reviewer: its return is never saved, consolidated, or counted by the retry policy. Once every reviewer has either produced output (including a Bob fallback's) or reached a terminal failure/unavailability result, `TaskStop` the Watcher if it is still running, then proceed to step 6. A rejected Carl deliberately publishes no output file; classify his process exit and do not wait for that missing file. A `WAITING` return after 30 runs (~50 min) means a still-running CLI reviewer stalled — treat that reviewer as failed per `references/retry-policy.md`. When the Watcher is skipped, the Stop hook `hooks/guard_stop_on_live_lanes.py` (PRD 00213) holds the session open while either background lane (codex or gemini) is alive and names the `-o` files to await.

**Do not Write or Edit ANY reviewer output (Alice's and Blake's included) until ALL reviewers have reported.** The CLIs self-write via `-o`; subagent-returned text is saved only in step 6, after every reviewer has completed - even if a subagent returns first.

**Bob fallback (the doubt lens never drops).** If `codex-run.sh` exits non-zero with exit 3 (codex unavailable), dispatch a Claude Task subagent with Bob's exact assembled prompt (doubt lens + rubric included) and use its output as Bob's. On exit 4 (codex ran but failed, e.g. quota), FIRST check the wrapper's `codex-review-last.jsonl` sidecar: exit 4 has a documented false-positive mode (quota markers matched in codex's own command args or gateguard noise) where codex actually finished — if the sidecar holds a complete review (findings plus all `D{n}:` verdict lines), salvage it as Bob's output and skip the fallback entirely. Only when no complete review is salvageable dispatch the Claude fallback; only if that also fails does Bob count as a failed reviewer per `references/retry-policy.md`. When dispatching the Claude fallback, replace the persona's read-only-shell reading instruction with the equivalent `Read`-tool instruction, so the subagent is told to open `{CONTEXT_FILE}`, `{DIFF_FILE}` and `{PACK_FILE}` with the tool it actually has.

**Carl availability.** Apply `references/agent-invocation.md`'s Carl exit-code
contract before retry policy. Exit 4 is permanent configuration unavailability,
not a one-off skip: record `Carl: permanently unavailable` and the backend/model
and stderr reason in the review file and user summary; do not retry unchanged
configuration or consolidate a pre-existing output file. Exit 3 is a dispatch
guard refusal. Other non-zero results are runtime failures (including quota),
recorded with their code and reason. Continue with the remaining reviewers.
On success, record the selected backend/model from the runner's stderr, including
any fallback, and require non-empty reviewer text before counting Carl as run.

**Latch Carl for the batch (autopilot only).** On exit 4 and when `state.json`
exists, append `carl` once to `state.batch.unavailable_reviewers` (default `[]`)
and set `state.batch.unavailable_reviewer_details.carl` to
`{"cycle": state.cycle, "prd": state.prd}`. Merge both into `state.json` in one
write, sibling fields untouched (including other batch fields and reviewer
entries); never overwrite the first failure's origin on subsequent cycles.
Do not latch exit 3, quota, transient failures, or a successful native fallback.
Standalone reviews create no state. The latch survives per-PRD reset because
`cli/records.py` preserves `batch` in full, and expires with the batch. A new
batch tries Carl again; an operator can remove his list entry and detail at a
session boundary after repair to re-enable him within this batch.

**Alice on the workflow engine** (`CONSENSUS_ENGINE` is `workflow` or `shadow`; skip this whole block on `legacy`). The workflow call goes in the SAME single dispatch message as the other reviewers — it is a foreground tool call whose inner agents are live subagents, so it holds a headless session open exactly as a Task subagent does. The Watcher rule above is unchanged: it exists for the background-Bash CLI reviewers.

```
Workflow({
  scriptPath: "<absolute path to review-fanout.workflow.js>",
  args: { ... }
})
```

Invoke by absolute `scriptPath`, never by `name` — the named-workflow registry resolves `.claude/workflows/` relative to the project root, and when the project root *is* the config directory that path is ambiguous.

`review-fanout.workflow.js` is **not shipped with this pack**: it is a host-local workflow file, conventionally `~/.claude/workflows/review-fanout.workflow.js`. If it is absent, the `workflow` and `shadow` engines are unavailable — fall back to `legacy`, which is the default and needs no such file, and log one warning line.

Build `args` from the context already gathered in step 3:

| arg | value |
|-----|-------|
| `diff` | The diff file's text, **truncated by you to at most 400000 bytes** (`MAX_DIFF_BYTES`). The payload crosses the tool boundary as JSON, so the cap is the caller's job. |
| `diff_bytes` | The diff file's **real** byte size before truncation (`wc -c`). |
| `diff_path` | Absolute path to the full diff file. Mandatory whenever `diff_bytes` exceeds 400000; the dimension agents are told to read it. |
| `rubric_text` | `${CLAUDE_PLUGIN_ROOT}/skills/review-work-completion/references/rubric.md`, verbatim — the consensus `R{n}` set (the workflow's verdict-line schema expects exactly these rules). Alice's `R{n}: pass\|fail` verdict lines are generated from it, and `references/retry-policy.md` fails a reviewer that omits them. The blind and doubt sets carry their own `B`/`D` prefixes since PRD 00108, so there is no longer a same-name collision to guard against. |
| `prd_text`, `prd_path`, `changed_files`, `context_path` | From step 3's gathered context. |
| `pack_path` | Absolute path to this cycle's engram context pack (`engram-pack-{id}.md`, produced by the pack step in step 3). Optional; when set, it puts the pack in front of every dimension persona, not just Alice's own top-level judgment. |
| `head_sha`, `date`, `cycle`, `agent_name` | `head_sha` from step 3; `date` as `YYYY-MM-DD` (the sandbox cannot call `Date()`); `cycle` = this review cycle; `agent_name` = `ALICE`. |
| `tests_line` | Omit on the live path — test counts do not exist until step 6. Shadow runs substitute it at step 8. |
| `personas` | **Required** (PRD 00109). An object mapping each of `rita`, `cora`, `grace`, `toby`, `mallory`, `trent`, `victor` to the body of `${CLAUDE_PLUGIN_ROOT}/agents/<name>.md` with its frontmatter stripped. The workflow carries no prompt text of its own; a missing or blank body is an `INVALID_ARGS` throw, never a weaker review. Read all seven regardless of whether the security dimension arms — the workflow decides that itself. |

**Why the bodies travel as args rather than `agentType`.** The workflow could name a persona and let the harness supply it as the subagent's system prompt, but that splits the prompt into system + user and can only ever emit persona-then-inputs. Victor's prompt interleaves the finding's fields *between* persona text, so that split reorders his bytes and breaks the parity the goldens pin. Passing bodies keeps every lane byte-identical to its pre-registry prompt. The cost: the `tools` pins in those seven files do not apply on this path. Both facts are recorded in `references/agent-registry.md` § Dispatch mechanism.

On return, write the result's `agent_output` verbatim to `docs/dev/tmp/alice-output-{id}.txt`. Step 6 consolidates it unchanged: it already speaks the `[ALICE] {emoji} … | File: … | Task: …` line format, carries the twelve `R{n}` verdict lines, and ends with the engine's `stats_line`.

Three failure classes, three different answers — **only the last one may fall back to legacy**:

1. **`INVALID_ARGS` throw** (empty diff, missing `rubric_text`, an over-cap diff with no `diff_path`). A caller bug or a review with nothing valid to review — it must NOT degrade to legacy Alice, which would paper over it. Repairable (e.g. `rubric_text` was not passed) → repair and re-invoke once. An **empty diff STOPS the review**: a review of nothing must never reach `Verdict: converged`.
2. **`incomplete: true` in the return value** (a dimension agent or a verifier died). Re-invoke once with `resumeFromRunId: <runId>` — completed dimensions replay from cache, only the dead ones re-run. Still `incomplete` → its 🔴 `review incomplete` lines stand (a partial review cannot converge) and Alice counts as a degraded reviewer per `references/retry-policy.md`.
3. **Engine unavailable** (the `Workflow` tool is absent or the harness refuses the call). This — and only this — falls back to legacy Alice for the cycle, loudly, with the fallback noted in the review file.

On `shadow`, legacy Alice still runs and still gates; the workflow's output is never written to `alice-output-{id}.txt` and never consolidated. Step 8 records it.

Active reviewers: Alice, Blake, Bob, Carl, plus Eve when the resolved doubt-reviewer rule in step 1 activates her. Include Carl only if the optional Gemini check in step 1 passed; otherwise run the remaining reviewers. Use one `{id}` for the cycle so the `-o` output paths here match the consolidation paths in step 6.

Read these before proceeding:

- `references/agent-invocation.md` - invocation commands for each agent
- `references/retry-policy.md` - retry and format compliance rules

### 6. Consolidate findings

**Report the batch skip.** When step 1 batch-skipped Carl, write this line in
the review file's top matter, using the first failure's `cycle` and `prd` from
`state.batch.unavailable_reviewer_details.carl`, not this cycle's values:

`carl: skipped (permanently unavailable since cycle {n} of {prd})`

Write it on every later cycle, including cycle 1 of later PRDs in the batch;
omit Carl from `reviewers:` and the consolidation inputs. He has no `ui` lens
key this cycle. A manually populated legacy list without origin still suppresses
dispatch: use `unknown` for each missing origin value rather than inventing one.
The cycle that first receives exit 4 records the failure per step 5 instead.

**Close out the lens roster (autopilot runs).** When `state.review_lenses` was stamped (by `review-stage` in step 3, or by hand on the bare-repo fallback), set each lens to `"done"`, or `"failed"` for a reviewer that failed per `references/retry-policy.md` (a lens rescued by a fallback — e.g. Bob's Claude fallback — is `"done"`). Skip on standalone runs.

Save each subagent reviewer's returned text to `docs/dev/tmp/` — **Alice** to `alice-output-{id}.txt`, **Blake** to `blake-output-{id}.txt`, **Eve** (when she ran) or her Claude substitute (when it ran instead) to `eve-output-{id}.txt`, and Bob's Claude fallback (when it ran) to `bob-output-{id}.txt`. Bob's and Carl's CLI outputs are already on disk - their `-o` flag wrote them straight to `bob-output-{id}.txt` / `carl-output-{id}.txt` in step 5.

**Close the CLI reviewer dispatch rows.** A `start` row closes when its dispatch reaches a terminal state — the background command exited — not when an output file is read: a terminal failure may publish no `-o` file at all (Carl's exit 4 publishes none), and an unclosed row makes the ledger under-report dispatches. The call is `python3 ${CLAUDE_PLUGIN_ROOT}/skills/work/scripts/record_dispatch.py end <id> <flags>`, taking the `<flags>` of the first row below that matches:

| Terminal state | `<flags>` |
|---|---|
| the output holds a usable review, first run | `--outcome ok` |
| the output holds a usable review, produced by the retry | `--outcome ok --detail retry` |
| the retry itself failed | `--outcome error --detail "retry: exit <n>"` or `--outcome error --detail "retry: lack-of-input"` |
| non-zero exit, nothing usable published | `--outcome error --detail "exit <n>"` |
| exit 0 but the refusal shape (`references/retry-policy.md` § Lack-of-input refusal) | `--outcome error --detail "lack-of-input"` |
| exit 0 but the output is unusable — malformed issue lines, or incomplete per-rule verdicts (`references/retry-policy.md` §§ Format Compliance, Per-Rule Verdict Completeness) | `--outcome error --detail "format-invalid"` |

The rows are mutually exclusive. `--detail` is a single field, so a failed retry encodes both facts in it as `retry: <the failure>` rather than losing one of them. Bob's Claude fallback (a Task subagent, not a CLI dispatch) gets no ledger row.

Then run:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/skills/review-work-completion/scripts/consolidate_findings.py \
  ALICE:$PWD/docs/dev/tmp/alice-output-{id}.txt \
  BLAKE:$PWD/docs/dev/tmp/blake-output-{id}.txt \
  BOB:$PWD/docs/dev/tmp/bob-output-{id}.txt \
  CARL:$PWD/docs/dev/tmp/carl-output-{id}.txt \
  --ledger $PWD/docs/dev/project-management/reviews/<prd-stem>-ledger.json --ledger-dismiss BLAKE
```

**Drop the two `--ledger` flags when no ledger file exists** (cycle 1). With them, Blake findings matching a settled entry are excluded from the table and from task creation, and listed instead under a trailing `### Auto-dismissed (ledger)` section naming the reason each matched — copy that section into the review file, so a wrong dismissal is visible rather than silent. The filter is **Blake-only**: an implementation-aware reviewer re-raising despite the step-4 prompt feed is signal, not noise, and stays in the table.

Pass only agents that produced output (omit the `CARL:` pair when Carl was skipped; append an `EVE:` pair when Eve or her Claude substitute ran). The script computes consensus dynamically from the number of agent pairs provided, and **merges paraphrases**: two reviewers describing one defect in different words land in one row with the higher consensus, provided they name the same file (PRD 00095; the bash predecessor matched on exact strings, so real 3/4 agreement always read [1/4]).

**If `consolidate_findings.py` exits nonzero, or warden denies it:** do not skip consolidation (that would silently drop every finding). Read the deny/error reason from the tool result; a fixable invocation problem (a passed path that does not exist for a reviewer that did run) → fix and retry ONCE. Otherwise **fall back to model-side consolidation**: read each reviewer's `*-output-{id}.txt`, group the findings that name the same issue at the same `File:` across reviewers, set each finding's consensus to the count of distinct reviewers that flagged it, and sort by consensus then severity — the same shape the script emits. **Note in the review file that consolidation was model-side** (fail loud — a hand-rolled consolidation must not read as the script's). The `Verdict:`/`Tests:` composition below applies unchanged to the model-side result.

**Carry the previous cycle's failed checks forward.** Do this **before** composing the `Verdict:` line below — the count has to include what this adds, or a cycle whose only findings are carried-forward ones writes `Verdict: converged` over a non-empty table. Read the previous cycle's queue file (`<prd-stem>-checks-<state.cycle - 1>.json`; absent on cycle 1, and absent is never an error). **Every entry whose `result.exit` is anything but the integer `0` becomes a finding in this cycle's consolidated table** — a non-zero code, `"timeout"`, `"refused"`, or a missing `result` on an entry an earlier cycle queued: each means the check did not pass, and a refused or unrun one is exactly the case the decision gate created no task for. Severity from what the check proves, `Found by: verify-check`, the entry's `command` and its exit in the text. This is the mechanism behind "a failed check comes back through the normal path": without it a red check is written to a file nothing reads, and the cycle converges over it. Skip on standalone (non-autopilot) runs, which have no `state.cycle` to count back from.

**Absorb the mechanical test checks.** Also before composing the `Verdict:` line: every `[MECH]` line in the context file's two test-check blocks (step 3) is a finding. When a consolidated row already names the same test file and test, append `mech-check` to its finders; otherwise add the line as its own row — its own severity, consensus `[1/N]`, `Found by: mech-check`. A replay row states a computed fact (the test passes against the pre-change code); whether that is a defect depends on the PRD, since a behavior-preserving refactor's tests pass by design, so it stays 🟡 and the decision gate may ledger-dismiss it with that reason. It is never dropped silently — that silence is the failure these blocks exist to end.

**Compose the `Verdict:` line.** Zero consolidated findings → `Verdict: converged`; otherwise `Verdict: N findings` (the consolidated count, including any findings the carry-forward above just added and the mechanical test checks absorbed). Step 8 writes it into the review file.

**Write the verification-check queue.** After composing the `Verdict:` line, collect the **VERIFY** bucket of every doubt lens that emitted one — today that is **Eve, or whichever lane produced the doubt output in her place** (her Claude substitute). `agents/bob.md` mandates the `[BOB]` issue-line format plus `R{n}` verdicts and defines no FIX/VERIFY/KNOWN buckets, so `source: "bob"` applies only if his persona later gains one; do not invent buckets he did not emit. Write the entries whose text names an exact runnable command to `docs/dev/project-management/reviews/<prd-stem>-checks-<state.cycle>.json` with the **Write tool** (read the existing array, append, write back). Shape, the `source` values and the not-queued rule: `references/output-formats.md` § Verification-check queue. A VERIFY item that names no exact command is **not** queued — it stays an ordinary finding and is classified as today, because rubric rule D3 already fails a vague one. Skip this entirely on standalone (non-autopilot) runs, which have no `state.cycle` and no work phase to run the checks.

**Compose the `Tests:` line.** **Check docs-only first:** when the reviewed diff touches no code, the line is `Tests: none (docs-only)` — a first-class value, not a sentinel, and the one form that takes **no** suffix, because `cli/gate.py`'s `TESTS_RE` allows none there. Nothing below applies. That test comes before the record, because a docs-only diff in this pack still has a matching record from the work phase's own suite run, and reading the record first would silently replace the sentinel with counts. Otherwise write `Tests: N passed, M failed, K skipped`, and read `docs/dev/project-management/autopilot/last-verification.json` first (`work/references/final-verification.md` § Recorded verification result): when its `sha` equals this cycle's reviewed HEAD **and** its three counts are non-null, compose the line from the record and **run no suite** — that record is the work phase's own mandatory run at this same HEAD. Otherwise (file absent, empty `commands`, `sha` mismatch, or null counts) run the project's test suite once in the FOREGROUND, exactly as before. **Name which path produced the counts**, as a parenthesised suffix on the `Tests:` line itself — `Tests: N passed, M failed, K skipped (reused from last-verification.json at <sha>)` or `... (suite run this cycle)`. The gate's pattern admits any suffix after the counts (`cli/gate.py` `TESTS_RE`), so this cannot fail `check_review_file.py`. Fail loud: a reused count must never read as a fresh run, and a stale record must never be reused.

**Record the Codex doubt-roster guard.** Emit the fired rule in the cycle's review file as `codex_rung_guard: fired (N codex-implemented task(s))`, using the count from step 1, or emit `codex_rung_guard: not fired` when the predicate is false. When the guard fired, the fired form has three possible outcomes: Eve produced usable output → the plain fired form as above, with no suffix; Eve failed after her retry budget and the Claude-subagent fallback (step 5) recovered a non-codex doubt voice in her place → append `; eve unavailable, doubt lens fell back to claude`; neither Eve nor that fallback produced output → the constraint is NOT met, so append `; constraint UNMET` instead. The line must never report plain `fired` when the constraint did not hold. Consolidation owns this line; `run-autopilot` must not write it.

**Record the doubt-rubric verdicts (autopilot runs).** When `docs/dev/project-management/autopilot/state.json` exists, parse the five `D{n}: pass|fail` lines from Bob's output (or his Claude fallback's) and REPLACE `state.doubts_rubric_verdicts` with the five entries `{"rule_id": "D{n}", "verdict": "pass"|"fail"}`; when Eve also ran, read her raw `D{n}:` lines too and write one entry per rule per reviewer with `source` tags (`"codex"` / `"fable"`). Verdicts are re-recorded every cycle; the final cycle's are the durable ones (the batch report renders them). Skip this entirely on standalone (non-autopilot) runs.

Outputs consolidated issues sorted by consensus then severity. See `references/output-formats.md` for output format details.

### 7. Follow-up tasks (removed, PRD 00249)

This skill creates no tasks. Under autopilot, the decision gate in `run-autopilot/references/phase-review.md` classifies this cycle's consolidated findings and then makes one `autopilot review-close --batch-id decision-gate` call, which creates every task the cycle needs (🔴 rework and 🟠/🟡 follow-ups alike). The findings JSON that call takes must account for every row this cycle's consolidated table carries: every consolidated row gets one JSON row with its `ref` and a `classification`, `discard` included, or `review-close` refuses the batch for the row missing a disposition. On a standalone run, report the findings in the review file's consolidated table (step 8) and directly to the user, and say plainly that they were reported, not written as tasks; never fabricate the autopilot state no `/autopilot:run-autopilot` build phase wrote.

### 8. Save review file

Create at `docs/dev/project-management/reviews/`.

See `references/output-formats.md` for filename convention, frontmatter, and content format.

Stamp the `head_sha` frontmatter field with the HEAD sha captured in step 3 — the next rework cycle reads it to scope its diff via `--since`.

Stamp the `codex_thread_id` frontmatter field with the thread id from `docs/dev/tmp/bob-thread-{id}.txt` when that file exists and is non-empty AND Bob produced output this cycle — the next rework cycle reads it (step 3) to resume Bob's codex session via `--resume-thread`; omit the field otherwise (Bob was skipped, or thread-id capture failed).

Stamp the `reviewers:` frontmatter field with the comma-separated lowercase names of every reviewer that actually ran (e.g. `reviewers: alice,blake,bob,carl`) — `check_review_file.py` reads it to verify each section.

**Stamp `consensus_run_id`** with the `runId` the Workflow tool returned, whenever the engine ran (`workflow` or `shadow`) — same pattern as `codex_thread_id`, and the forensic handle for that cycle's run. It is deliberately not written to `state.json`: `resumeFromRunId` is same-session only, so a stored id would outlive its own usefulness.

**Shadow runs (`CONSENSUS_ENGINE == "shadow"`).** The workflow's `review_markdown` carries the literal token `{{TESTS_LINE}}` (step 5 passed no `tests_line`). Substitute the `Tests:` line composed in step 6 for that token — a file still carrying the token cannot pass `check_review_file.py` — then write the result to `docs/dev/tmp/<prd-base>-consensus-shadow-{cycle}.md`. **Never** to `docs/dev/project-management/reviews/`: step 3's `-review-*.md` glob finds the prior cycle there, and a shadow file in that directory would be mistaken for one. Gate the shadow file with `check_review_file.py --reviewers alice`, then record in the real review file, under Alice's section, the engine's `stats_line` and any verdict divergence from legacy Alice — as an observation, never as a finding. The shadow never gates.

Include all findings even if zero issues. Give each reviewer that ran a `## <Name>` section (their findings, or a one-line all-clear; Bob's keeps his `D{n}:` verdict lines, and records `after one retry (inlined)` whenever the inlined retry was dispatched, whether or not it produced them), and end the file with the `Verdict:` and `Tests:` lines composed in step 6.

Place the `codex_rung_guard:` line composed in step 6 in the top matter: directly after the `Diff range:` block, before the body sections.

**Gate the saved file (PRD 00016).** Run the shape check and fix the file if it fails — do not report a completed review over a failing gate:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/skills/review-work-completion/scripts/check_review_file.py --review-file $PWD/docs/dev/project-management/reviews/<review-file> --require-codex-guard
```

**Write the contract card** at this cycle transition (run-autopilot § Contract card): the current step, the active invariants, and the next gate (rework at cycle N+1, or converge → done), so a session compacted mid-review re-anchors to where the cycle stands. Write the body to `docs/dev/project-management/autopilot/contract-card.md` with the **Write tool**, then (autopilot only) load it with `statectl.py <state.json> set-contract-card docs/dev/project-management/autopilot/contract-card.md` — never as an inline shell argument, which fails on the card's own quotes and newlines. Then write the session brief — `python3 ${CLAUDE_PLUGIN_ROOT}/skills/run-autopilot/scripts/statectl.py <state.json> write-brief docs/dev/project-management/autopilot/session-brief.md` — so the next session orients from one page (PRD 00201); a failed write is one stderr line, never a phase failure.
