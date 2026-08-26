---
name: work
description: Use when executing already-planned tasks one at a time, dispatching the implementor and committing after each. Triggers on "work on tasks", "implement tasks", "start working", "execute the plan", "do the work".
compatibility: "Requires Bob personal Claude/autoclaude environment or equivalent host adapters for sub-agents, state, and review handoffs."
---

> **Paths in this pack.** This pack's root is `${CLAUDE_PLUGIN_ROOT}` - that line
> is substituted when this skill loads, so what you just read is the real
> directory. Files under `references/` are read at runtime and are **not**
> substituted: when one shows `${CLAUDE_PLUGIN_ROOT}/...`, swap in the root above
> before running anything. Never pass the literal placeholder to a shell - it
> expands to the empty string and the path silently becomes `/...`.

# Work Through Tasks

Implement pending tasks one-by-one, committing after each completion.

## Dependencies

- Personal skills: `run-autopilot` - this skill is a phase inside that loop and
  shares its state contract, `dev/local/autopilot/state.json` (see run-autopilot's
  state-schema and phase-review references).
- Files read from other skill dirs:
  - `${CLAUDE_PLUGIN_ROOT}/skills/run-autopilot/scripts/statectl.py` - the sole `state.json`
    mutator; `/work` invokes it to append attempt entries and sync task status
    (never the Edit/Write tools)
  - `${CLAUDE_PLUGIN_ROOT}/skills/run-autopilot/scripts/_walk_up.py` - run at every task
    start and at the handoff check
  - `${CLAUDE_PLUGIN_ROOT}/skills/run-autopilot/prompts/de-sloppify.md` - its
    `## What to remove` section is inlined into the step-5.6 deslop dispatch
  - `${CLAUDE_PLUGIN_ROOT}/skills/review-work-completion/scripts/compute_mech_facts.py` - imported
    by path from `scripts/check_style_limits.py` (step 7.0 style-limit gate) for the per-function line spans
- CLIs: `git`, `python3`
- Optional (explicit fallback exists): `use-gemini` skill (UI tasks), `use-qwen`
  skill, `use-codex` skill (an unhealthy or absent codex falls back to Claude at
  the task's tier), `use-sonnet` skill (its `scripts/sonnet-run.sh` drives the
  step-5.7 reviewer lane)

## CRITICAL: Never Ask the User to Run Commands

This skill runs inside an **automated autopilot loop**. The user is not watching. Do not ask the user to run tests, commands, or do anything manually. The only valid reasons to surface output to the user are:

1. A genuinely irreversible action that requires explicit confirmation (e.g. force-pushing a shared branch).
2. More than two consecutive failed attempts at the same automated step with no remaining fallback.

**When test verification is blocked** (e.g. all cargo processes were backgrounded and the build lock was contended): if the code compiles cleanly and the logic change is correct by inspection, commit and proceed — and record `verification: skipped:<cause>` in the task's attempt entry and the phase report (fail loud; a skipped check must never read as a passed one). The full-suite verification run at the end of the phase will catch regressions. Do not stop and ask the user to run anything.

**When cargo commands get backgrounded by the session**: the Bash tool may background long-running commands regardless of the `run_in_background` flag. Wait for background completions via Monitor (up to 20 minutes for full test suites). Never launch a second cargo command while one is still running — they contend on the build lock and jam the shell. If a Monitor times out, read the output file directly; if the file is empty the build lock was still held, wait longer before retrying.

## CRITICAL: One Task at a Time

**STOP.** Before dispatching ANY Agent or helper-script call, verify you are sending it EXACTLY ONE task. Batching tasks into one Agent call leaves `state.tasks` (and every dashboard reading state.json) stale for the entire duration and collapses per-task attempt logging.

**The loop runs in YOUR session (the main session), not inside a subagent:**

```
for each pending task:
    a. task-start <id>
    b. Tess writes tests (from requirements only)
    c. test quality gate (main session)
    d. Devon tries to break tests (adversarial validation)
    e. commit tests
    f. Ivan implements against failing tests
    g. verify THIS task's tests pass (retry Ivan if needed)
    h. commit implementation
    i. task-done <id> <attempt-file>

after all tasks complete:
    j. run full verification suite ONCE (see step 7 below)
```

The loop steps above are lettered on purpose — they are a conceptual
sequence, distinct from the numbered section headers (`### 1`…`### 7`)
that the rest of this skill cross-references. "step 7" always means the
section, never a loop step.

**Per-task verification runs only the tests Tess wrote in step 2.7, not the full project suite.** The full suite runs once at the end (why: `references/design-rationale.md` § narrow verification).

If you find yourself writing an Agent prompt that mentions multiple tasks, STOP — you are about to violate this rule.

See **Subagent Dispatch Budget and Watchdog** below — every Agent dispatch must satisfy both.

## Subagent Dispatch Budget and Watchdog

**Budget:** every prompt passed to the Agent tool (Tess, Ivan, or Devon) must be **≤ 50 000 bytes**, with the abort-instruction line prepended. Measure before every dispatch; trim the lowest-priority context once, and if still oversized abort the task with cause `subagent_prompt_overrun`.

**Watchdog:** every Agent dispatch must be wrapped in a watchdog: dispatch with `run_in_background: true`, wait with a `Monitor` timer (15-minute CHECK-IN — on expiry probe for progress and extend, 45-minute hard cap; kill only on two no-progress probes or the cap), and after any `TaskStop` inspect the tree before re-dispatching — a killed agent usually died at its verification tail with complete work on disk, which you verify independently and accept, never redo. Genuinely dead agents route to the **Result lost / hung** row of step 4's table (→ the infrastructure-failure circuit breaker, step 4.2). A foreground `Agent` call that hangs blocks this session indefinitely — never dispatch one unwatched.

See `references/subagent-dispatch.md` for the measurement procedure, the verbatim abort-instruction line, the abort-handoff steps, helper-script (`use-codex`/`use-gemini`/`use-qwen`) handling, and the three distinct deadlines (15 min / 10 min × 2 / 20 min, by mechanism). Read it before your first Agent dispatch in a session. Elsewhere in this file, "must satisfy the **Subagent Dispatch Budget**" and "**Subagent Watchdog**" mean exactly this section — the numbers are not restated at call sites.

## Per-task model dispatch

Before any Agent call for a task, read the task's `model` field in its `state.tasks` entry (`state.tasks[i].model`) and pass it as the Agent tool's `model` parameter.

Applies to **every** Agent call this skill dispatches, including follow-up dispatches inside compound steps: Tess and her quality-gate/adversarial-round re-dispatches (steps 2.7-2.85), Devon (2.85), and Ivan and every Ivan re-dispatch (3, 5.5, 5.7 fix, 7 regression fix). (The step-5.7 reviewer is a fixed-model helper-script dispatch via `use-sonnet`, not an Agent call — the `model` parameter does not apply to it.) If you add a new Agent call to this skill, pass `model` from `state.tasks[i].model` — no exceptions.

**Qwen one-shot-per-task budget carve-out (step 5.5 only).** When the failing attempt's implementor was qwen (helper-script `use-qwen`, NOT an Agent dispatch — qwen never used `state.tasks[i].model`), every step-5.5 re-dispatch for that task targets **Claude Sonnet** regardless of `state.tasks[i].model` — never qwen again for that task. This is the one-shot-per-task qwen attempt budget — one qwen dispatch per task, never a per-PRD or per-batch cap — the ladder's `qwen -> sonnet` capability edge (`run-autopilot/references/model-ladder.md` § Capability ladders and § Per-rung budgets; why: `references/design-rationale.md` § one shot): qwen gets exactly 1 dispatch per task, a qwen gate failure escalates to Sonnet immediately with zero qwen retries for that task, and step 5.5's Claude-rung budget then runs entirely on Claude Sonnet — see step 5.5 below for the full diagnose/repair/escalate flow this now drives. Applies unchanged under `_AUTOPILOT_ESCALATION=legacy` (model-ladder.md § Kill-switches). All non-step-5.5 Agent calls continue to obey `state.tasks[i].model` with no exceptions.

Accepted values: `"haiku"`, `"sonnet"`, `"opus"`. A fourth value, `"fable"`, is the human-gated rescue rung above `opus` (`run-autopilot/references/model-ladder.md` § Rungs).

**A task carrying `state.tasks[i].model: "fable"` overrides the step-3 Deterministic routing table outright** — set only by the Fable rescue gate (`run-autopilot/references/recovery.md` § Rework escalation exhausted): never qwen, never Gemini, always a Claude Agent dispatch at `model: "fable"`, whatever the rows of that table would pick. `fable` is never a session model and is never selected autonomously — a human-approved rescue is the only writer of this value (`run-autopilot/references/model-ladder.md` § Fable rescue). It runs at the same depth as `opus`: Devon at step 2.85, the step-5.7 per-task review, and `pipeline: "full"`.

**Legacy plans** (created before `state.tasks[i].model` existed) have no model field. Omit the `model` parameter — subagents inherit the session model. This preserves the legacy behavior bit-for-bit.

The **Subagent Dispatch Budget** applies regardless of tier. Haiku doesn't earn a smaller cap; opus doesn't earn a larger one.

## Assumptions footer

Every Tess and Ivan dispatch prompt - initial and retry, regardless of mechanism (Agent, `use-gemini`, `use-qwen`, `use-codex`) - must end with this instruction verbatim:

> End your report with `ASSUMPTIONS:` - one line per assumption you made where the task, tests, or listed files were silent (guessed interface, data shape, resolved ambiguity, unstated behavior). Write `ASSUMPTIONS: none` if you made none.

**Ivan** dispatch prompts (initial and retry, all mechanisms) must additionally end with this instruction verbatim:

> Also end your report with `FILES_TOUCHED:` - one line per file you created or modified, path relative to the repo root. Write `FILES_TOUCHED: none` if you changed no files.

Step 5 stages exactly the reported paths - an unreported file stays uncommitted and is surfaced by step 5's foreign-path rule, so an implementor that omits the footer fails loudly, not silently.

Collect the returned lines: step 6 appends non-`none` entries to `dev/local/meta/assumptions.md` under a `## <task-id>: <task subject>` heading (Write/Edit tool, never shell redirects). On the first completed task of a full-plan pass, replace the file instead of appending - the ledger is per-plan. Step 7's phase report includes the ledger so the user and the review phase can examine what the implementors guessed in a 30-second read.

## Dispatch prologue

Every Tess and Ivan dispatch prompt - initial and retry, regardless of mechanism (Agent, `use-gemini`, `use-qwen`, `use-codex`) - must also contain this line verbatim (transcript mining 2026-07-14: ~150 hook-blocked coreutils calls and ~60 Edit-before-Read failures across 90 sampled loop sessions):

> Read every file before your first Edit to it. Never call bash `head`, `tail`, `cat`, `grep`, or `find` - a hook blocks them. Use the Read tool (offset/limit), `rg`, or `rg --files` instead.

## Passing values to render_prompt.py

Every render call in this skill (Tess 2.7, Ivan 3 / 5.5 / 7, Pat 5.7) picks a flag by where the value comes from, not by convenience:

| Value | Flag |
|---|---|
| Task-authored prose — subject, description, acceptance criteria, Contract file paths, findings blocks | `--set-file`, from a scratch file written with the **Write tool** |
| A file that already exists on disk | `--set-file <path>` |
| Several existing files concatenated | `--set-cmd "cat $(printf '%q ' <paths>)"` |
| A fixed string this skill composes itself, containing no task text | `--set` |

**Task-authored prose must never be passed with `--set`.** A `--set KEY=VALUE` word is expanded by the shell before `render_prompt.py` ever sees it, and task text in this repo routinely contains backticks and `$( )` — bash executes the command substitution and strips it, so the subagent silently receives a corrupted prompt, and the substituted command runs. Writing the prose to a scratch file and passing the path removes the shell from the path entirely; it costs one Write call, which the render call was already saving.

The `--set-cmd` quoting rule is separate and still applies: any path interpolated into a `--set-cmd` value crosses into a nested shell (`subprocess.run(..., shell=True)`), so quote it with `printf '%q '` or `shlex.quote()` before composing the flag.

**Dispatch-target preflight (mandatory).** Every file path written into dispatch prose (descriptions, contracts, `FILE_PATHS` lists) is spelled **absolute** — never repo-relative. And every target file the task touches is passed to the render as a flag: `--require-file /abs/path` for a file the subagent edits (must exist), `--require-parent /abs/path` for a file it creates (parent directory must exist). The render exits 7 when a path is relative or does not resolve — that is a **blocked dispatch**: never dispatch, never "fix" the path by guessing; treat it exactly like a failed `Premise:` check (step 2, interactive: stop and report; loop mode: the loop-mode stall path). Why: a subagent handed the unanchored path `debrief-meeting/app/smoke.test.js` went hunting for it, and `rg` sweeps can't see into dot-directories — the only visible match was a suffix-matching copy in a synced directory outside the repo, which it edited and an external daemon pushed (2026-08-18, batch 202608180438).

## Attempt logging

At every task exit — success in step 6, abort in step 4 (timeout / context exceeded / error after debug), or via the Subagent Dispatch Budget overrun path — append one entry to `state.tasks[i].attempts[]`. Each entry carries:

- **`implementor`** — `"claude"`, `"gemini"`, `"qwen"`, or `"codex"`, reflecting what actually dispatched, NOT what the step-3 routing table initially picked (a qwen pick that fell back to Claude on preflight failure records `"claude"`).
- **`preflight_outcome`** — from the step-3 preflight probe. Always written explicitly — never omit the key. Qwen-eligible attempts record one of `"healthy"`, `"pi_missing"`, `"endpoint_unreachable"`, `"model_id_missing"`, `"completion_failed"`; non-qwen-eligible attempts record the literal JSON `null`. A pressure-gated attempt (row 4 fired, the probe never ran) also records the literal JSON `null` — the same carve-out already granted to a breaker-skipped attempt (row 3).
- **`qwen_excluded_reason`** — `"memory_pressure"` (row 4 fired, `check_memory_pressure.py` exited 1) or `"memory_probe_failed"` (row 4 fired, exited 2); key omitted when row 4 did not fire. Attempt-scoped RUNTIME field — distinct from the plan-time `state.tasks[i].qwen_excluded_reason` (`"ui"`/`"tier"`/`"files"`/`"contract"`) that `/plan-tasks` writes; `/work` never rewrites planner metadata. Absent on every attempt written before PRD 00075 — readers treat absence as "no pressure exclusion", never an error.
- **`pipeline`** — the tier-gated depth this attempt ran, keyed on `state.tasks[i].model`: `haiku` → `"minimal"` (Tess + Ivan), `sonnet` → `"lean"` (+ step-5.7 reviewer), `opus` → `"full"` (+ Devon at step 2.85); absent/legacy is treated as `sonnet` → `"lean"`. `fable` → `"full"` as well — the rescue rung runs the deepest pipeline, like `opus`. Written at every task exit; a Phase-6 escalation to `opus` records `"full"`.

See `references/attempt-logging.md` for the full entry schema, field semantics, and the atomic write procedure.

## Implementor Selection

The **deterministic routing table in step 3** is the single source of truth for picking each task's implementor (Gemini / local qwen / codex / Claude at tier). Do not route from memory or from this section.

**Gemini-first tasks** — the UI definition the routing table references. A task is UI/visual when it involves: color palettes/theming/contrast, layouts (page structure, spacing, visual hierarchy), UI components (buttons, forms, cards), typography, animations/transitions, responsive design, or any user-facing surface (web pages, GUI, dashboards).

For visual tasks, Gemini can also challenge the spec before implementation — see `references/gemini-integration.md` § Design Authority (trust its feedback on visual matters).

Codex (`use-codex`) is an implementor rung — activated by PRD 00077, sitting between qwen and the Claude tiers, gated by the fences and toggle declared in `run-autopilot/references/model-ladder.md` § Codex rung. It also still serves in the review path — see `references/codex-integration.md`.

## Dashboard State Sync

The dashboard (tracon; `render_stream.py` fallback) reads `dev/local/autopilot/state.json` directly, so `state.tasks[].status` must stay accurate — set at task start (step 2) and task end (step 6) — with `tasks_completed` matching it. The pidash sync hooks are retired (PRD 00063); nothing else maintains these.

Apply every such change with `statectl`, never the editing tools — the sole-writer rule in `run-autopilot` SKILL.md § State Management, which also documents the one human fallback. **Use the compound task verbs for the lifecycle transitions**, not a sequence of field writes:

| Transition | Call |
|---|---|
| task start | `statectl.py <state.json> task-start <task-id>` |
| task end | `statectl.py <state.json> task-done <task-id> <attempt-json-file>` |

`task-done` lands status, the appended attempt record, and a **recomputed** `tasks_completed` in one locked atomic write. Both verbs resolve the task by `tasks[].id`, not array position.

**Do not set `tasks_completed` alongside a task-lifecycle transition** — `task-done` derives it, and setting it too is what let the count and the statuses drift apart. This bans the per-task write only: the Phase 3 bulk snapshot (`run-autopilot/references/phase-build.md`) still writes `tasks_total`/`tasks_completed` in the same write that establishes the whole `tasks` array, which is the one legitimate hand-set and has no compound verb.

The generic `set|append|del <json-path>` forms remain for everything that is not a task-lifecycle transition.

## Workflow

### 1. Get pending tasks

Read `state.tasks` from `dev/local/autopilot/state.json` — it is the canonical,
complete task store, so nothing needs hydrating first. Filter for:

- `status == "pending"`
- **Unblocked**: `blocked_by` is absent, empty, or every id in it resolves to a
  `tasks[]` entry with `status == "completed"` (ids are stored as strings, so
  compare `str(id) == entry.id`)

### 1.5. Rework-mode task filter

Read `state.rework_task_ids` from `dev/local/autopilot/state.json` (walk up from cwd to find the autopilot dir, same pattern as the cap-marker reset in step 2). Two modes:

| `rework_task_ids` | Mode | Iteration source |
|-------------------|------|------------------|
| absent or `[]` | **default (full-plan)** | The pending-and-unblocked subset from step 1's `state.tasks` pending scan, in that scan's order. This is the Phase 3 first-pass behavior. |
| non-empty array | **rework mode** | The listed task IDs read directly from `state.rework_task_ids`, in array order — **bypass step 1's status filter entirely**. Each id's entry is read directly from `state.tasks[i]` (matched by id) regardless of current status (`pending` after Phase 6's reset, or `completed` if Phase 6's reset hasn't fired yet). Tasks NOT in the list are skipped entirely — no Tess/Ivan/Devon dispatch, no commits. |

**In rework mode, read `references/rework-mode.md` before the first task** — it carries the `in_progress`/`completed` lifecycle, the `review_cycle` / `escalation_reason` / `escalated_from` attempt fields, and the abort semantics (`rework_task_ids` survives an aborted pass; only Phase 6 clears it).

### 2. Claim and start task

For the first available task:

1. **Claim the task** with the single compound verb (see Dashboard State Sync) — `task-start` sets `status: in_progress` in the state file, so this call IS the claim:
   ```bash
   python3 ${CLAUDE_PLUGIN_ROOT}/skills/run-autopilot/scripts/statectl.py <state.json> task-start <task-id>
   ```
2. **Reset the per-task context-cap marker** so the autopilot PostToolUse hook fires once for THIS task, not once per Work phase. The hook also self-clears when the in-progress task id in `state.json` differs from the id stored in the marker file, but the explicit clear here is a belt-and-braces backstop in case state.json's task-id snapshot lags the actual task switch. Run the shared walk-up helper in `--clear-cap` mode — it resolves symlinks, walks up to the autopilot dir, and removes `<autopilot_dir>/.cap-fired` internally:
   ```bash
   python3 ${CLAUDE_PLUGIN_ROOT}/skills/run-autopilot/scripts/_walk_up.py --clear-cap
   ```
   No-op when no ancestor has the dir or the marker is already absent (first task of the phase); always exits 0. Use exactly this single-command form — no `d=$(...)` shell variable, so the permission matcher can resolve it.

### 2.5. Load project context

Before dispatching the implementor, load relevant context into the prompt:

- AGENTS.md / agent_docs/ architecture docs
- Active PRD from `dev/local/prds/wip/`
- Key module interfaces relevant to the task

1M context makes this practical — richer prompts produce better first-pass results.

**Ambiguity check (Think Before Coding):** Re-read the task description. If scope, data shape, target surface, or success criteria are unclear, stop and ask the user rather than picking silently. See `references/code-quality-principles.md` §1 and `references/code-quality-examples.md` §1 for what counts as a hidden assumption worth surfacing.

**Premise check:** If the task description carries a `Premise:` line, verify each stated fact against the current tree (`ls`, `rg`, `git ls-files` as fits) BEFORE dispatching any implementor — cheap read-only probes only, never a mutation. If any fact no longer holds, do not dispatch. Interactively: stop and report which fact failed; the task stays in_progress for the user or the decision gate. In loop mode (post-00017): a failed premise is never assumed through — it takes the loop-mode stall path (`run-autopilot/references/recovery.md` "Loop-mode stall procedure"), unlike ambiguities, which 00017 resolves by simplest safe assumption. If a probe command itself errors, treat the premise as unverified and surface it as a blocker — never proceed on an unknown. Tasks without a `Premise:` line skip this check entirely (zero behavior change for legacy plans).

### 2.7. Write tests first (Tess - test author)

Dispatch a separate agent to write tests from requirements only. This agent must NOT receive implementation hints or architecture deep-dives - only what a user of the API would know.

**Tess runs as:** Claude Code subagent (Agent tool), not a helper-script implementor (`use-gemini`, `use-qwen`, `use-codex`). It's a focused task that benefits from direct file access for reading test patterns.

**Skip for:** test-only, docs-only, or config-only tasks.

Render: one Bash call. **Task-authored prose never crosses the shell** — write it to a scratch file with the Write tool and pass `--set-file`; see § Passing values to render_prompt.py. Every interpolated path is `shlex.quote()`-d (or bash's `printf '%q '`) before it lands inside a `--set-cmd` value:
```bash
python3 ${CLAUDE_PLUGIN_ROOT}/skills/work/scripts/render_prompt.py ${CLAUDE_PLUGIN_ROOT}/skills/work/references/tess-prompt.md \
  --out dev/local/tmp/dispatch-tess-<task-id>.txt \
  --set-file TASK_SUBJECT=dev/local/tmp/tess-<task-id>-subject.txt \
  --set-file TASK_DESCRIPTION=<scratch file: task description plus the exact file paths and symbol names to test> \
  --set-file TASK_ACCEPTANCE_CRITERIA=dev/local/tmp/tess-<task-id>-acceptance.txt \
  --set-file SAMPLE_TEST_FILE=<one representative existing test file> \
  --set-cmd PUBLIC_INTERFACES="cat $(printf '%q ' <interface files>)" \
  --set TEST_FRAMEWORK="<pytest/jest/vitest/etc>" \
  --require-file <each absolute path to an existing file the task touches, one flag per path> \
  --require-parent <each absolute path to a file the task creates, one flag per path>
```
**Read `references/test-author-prompt.md` § Context Selection before the first Tess dispatch of a batch** — it lists exactly what Tess receives and what she must not, and what `tess-prompt.md` already bakes in (read-only scope, dispatch prologue, Assumptions footer), so nothing is added to the prompt by hand. Dispatch the Agent tool with the file at `dev/local/tmp/dispatch-tess-<task-id>.txt` as the prompt source; the render call's stdout integer **is** the Subagent Dispatch Budget measurement.

Tess prompts must satisfy the **Subagent Dispatch Budget**.

### 2.8. Test quality gate (main session)

Before committing Tess's tests, review them in the main session against the four-check rubric in `references/test-author-prompt.md` § Quality gate (behavior names, real assertions, edge cases, no tautologies); **read that section before running the gate.** If any check fails, dispatch Tess again with specific feedback about what's weak, rendered from `tess-retry-prompt.md` — never author the retry by hand. Max 2 quality gate retries.

**Total Tess budget:** max 5 dispatches across the entire test authoring phase (quality gate + adversarial rounds combined). If exhausted, flag weakness in task output and proceed. Don't block the pipeline forever.

### 2.85. Adversarial validation (Devon - devil's advocate)

**Tier gate — Devon runs on the deepest rungs only, `opus` and `fable`.** Read the task's `model` field (`state.tasks[i].model`):

| `state.tasks[i].model` | Devon (step 2.85) |
|-----------------------|-------------------|
| `opus` | dispatch Devon (below) |
| `fable` | dispatch Devon (below) — the rescue rung runs the deepest pipeline, like `opus` |
| anything else — `haiku`, `sonnet`, absent/legacy or unknown (both treated as `sonnet`) | skip Devon, proceed to step 2.9 |

The step-2.8 test quality gate is **unchanged** and runs for every tier — only this Agent dispatch is conditional. A Devon dispatch obeys the **Per-task model dispatch** rule (passes `model: opus`, or `model: fable` on a rescued task). Escalation interplay is automatic: when the review gate escalates a review-flagged task to `opus`, the rework attempt regains Devon with no extra mechanism. (Why tier-gated: `references/design-rationale.md` § tier-gated pipeline.)

See `references/adversarial-test-prompt.md` § Procedure for how Devon runs, and the file's prompt template section for what it receives. Devon prompts must satisfy the **Subagent Dispatch Budget**.

### 2.9. Commit tests

```bash
git add <test_files>
```
```bash
git commit -m "test(<scope>): add tests for <feature>"
```

Tests are committed separately before implementation, making the TDD boundary auditable in git history.

**Capture this task's test-commit SHA** immediately — step 5.5's ESCALATE reset resets to exactly this commit (never a prior task's):
```bash
git rev-parse HEAD
```
Hold the returned SHA in-session as `<test_commit_sha>` for this task; step 5.5's ESCALATE path reads it.

### 2.95. Red-check — watch the tests fail

Run the newly committed tests once, before any Ivan dispatch, at the narrowest scope (the same commands step 5.5 uses). Red is the point: a failure proves the tests bind behavior that does not exist yet (rules/testing.md fail-first). Implicitly skipped when step 2.7 was skipped (no new tests).

**Read `references/red-check.md` before the first red-check of a batch** — it resolves the target module from the task's `Contract` section and carries the outcome ladder (expected red -> step 3; accidentally green -> back to Tess; cannot run -> `red_check: skipped:<cause>`, fail loud). One verdict stays here: when an **imported** Contract-named target path does not exist on disk yet, skip the invocation entirely and write `red_check = "n/a:new_module"` to the attempt entry.
### 3. Implement against tests (Ivan - implementor)

Ivan's job: make the failing tests pass. Tests ARE the spec.

**Ivan receives:** failing test file paths and their content, architecture context (AGENTS.md, interfaces, relevant modules), and existing code patterns to follow. **Ivan does NOT receive:** the task's acceptance criteria prose (tests replace this) or permission to modify test files.

Render: one Bash call. **Task-authored prose never crosses the shell** — write it to a scratch file with the Write tool and pass `--set-file`; see § Passing values to render_prompt.py. Every interpolated path is `shlex.quote()`-d (or bash's `printf '%q '`) before it lands inside a `--set-cmd` value:
```bash
python3 ${CLAUDE_PLUGIN_ROOT}/skills/work/scripts/render_prompt.py ${CLAUDE_PLUGIN_ROOT}/agents/ivan.md \
  --out dev/local/tmp/dispatch-ivan-<task-id>.txt \
  --set-cmd FAILING_TESTS="cat $(printf '%q ' <test_file_1> [test_file_2 ...])" \
  --set-file ARCHITECTURE_CONTEXT=<a single existing file, e.g. AGENTS.md, when one file covers it> \
  --set-file FILE_PATHS=dev/local/tmp/ivan-<task-id>-files.txt \
  --set RETRY_INSTRUCTION="" \
  --require-file <each absolute FILE_PATHS entry that exists today, one flag per path> \
  --require-parent <each absolute FILE_PATHS entry the task creates, one flag per path>
```
`FILE_PATHS` is the newline-separated list from the task's Contract section, written to that scratch file — a Contract path can contain a space or a shell metacharacter, so it is never passed as a `--set` word. Every entry is absolute and every entry appears in a `--require-file`/`--require-parent` flag (§ Passing values to render_prompt.py, Dispatch-target preflight).
When architecture context spans more than one file, use the same `--set-cmd ARCHITECTURE_CONTEXT="cat $(printf '%q ' <file_1> <file_2>)"` shape. `RETRY_INSTRUCTION` is the literal empty string on this, the initial dispatch. The stdout integer from this call **is** the Subagent Dispatch Budget measurement — no separate `wc -c`. If the printed size exceeds 50 000, trim per the existing one-pass rule in `references/subagent-dispatch.md`, then re-render (still one call). Dispatch the Agent tool with the file at `dev/local/tmp/dispatch-ivan-<task-id>.txt` as the prompt source, watchdog per the existing Subagent Watchdog section — unchanged. `ivan.md` bakes in the code-quality rules block, the abort-instruction line, the read-only-scope note, the dispatch prologue, and the Assumptions/FILES_TOUCHED footers permanently — nothing further needs adding to the prompt by hand.

**If the task description is ambiguous** (multiple interpretations, unclear scope, unstated format/fields/location), stop before dispatching Ivan and surface the ambiguity to the user. See Example 1 in `references/code-quality-examples.md`. Do not dispatch with guessed-at requirements.

**Deterministic routing table.** Pick the implementor by reading the claimed task's tier (`state.tasks[i].model`) and qwen-eligibility flag (`state.tasks[i].qwen_eligible`), then cross-referencing against the "Gemini-first tasks" UI definition in **Implementor Selection** above. No re-judging here — `qwen_eligible` is computed upstream by `/plan-tasks` and already encodes backend (not UI) + `haiku`/`sonnet` tier + `<=3`-files + no public-contract edit (exported API signature, schema, wire format, hook registration shape); ineligible tasks carry `state.tasks[i].qwen_excluded_reason` (`ui`/`tier`/`files`/`contract`) for the batch-report telemetry. If the field is absent (legacy plans), treat it as `false`.

Apply the rows in this order — the first match wins (in practice `qwen_eligible == true` already excludes UI and `opus`, so the order resolves any apparent overlap deterministically):

| # | Task class | Implementor | Reference |
|---|------------|-------------|-----------|
| 1 | UI / visual task (per "Gemini-first tasks") | Gemini if available, else Claude at `state.tasks[i].model` | `references/gemini-integration.md` |
| 2 | Backend `opus` tier | Claude Opus (Agent dispatch) | — |
| 3 | Backend, `qwen_eligible == true`, `_AUTOPILOT_ESCALATION != "legacy"`, qwen capability breaker tripped (`qwen_breaker.tripped == true`, after the batch-scope check below) | Claude at the task's ORIGINAL tier (`haiku` → Haiku, `sonnet` → Sonnet) — **skip the preflight probe**, stamp the eventual attempt `breaker_skipped:true` | qwen capability breaker (below) |
| 4 | Backend, `qwen_eligible == true`, row 3 did not fire, and `python3 ${CLAUDE_PLUGIN_ROOT}/skills/work/scripts/check_memory_pressure.py --max-level <ladder § Memory gate value>` exits non-zero | Claude at the task's ORIGINAL tier (`haiku` → Haiku, `sonnet` → Sonnet) — **skip the preflight probe**; stamp the attempt `preflight_outcome: null` and `qwen_excluded_reason: "memory_pressure"` (exit 1) or `"memory_probe_failed"` (exit 2) | `scripts/check_memory_pressure.py` |
| 5 | Backend, `qwen_eligible == true`, row 3 did not fire, row 4 did not fire, healthy qwen infra | Local qwen via `use-qwen` helper | `references/qwen-integration.md` |
| 6 | Backend, `qwen_eligible == true`, row 3 did not fire, row 4 did not fire, **unhealthy** qwen infra | Claude at the task's original tier (`haiku` → Haiku, `sonnet` → Sonnet) | `references/qwen-integration.md` (Preflight) |
| 7 | Backend, `qwen_eligible == false` (or absent) | Claude at the task's tier (e.g. a `>=4`-file `sonnet` task → Claude Sonnet) | — |

**Codex rung interception.** After the table above yields its verdict, dispatch **codex** instead of the Claude implementor the table named when all six fences hold (verdict is "Claude at the task's tier"/"ORIGINAL tier", `codex_eligible(task)`, `_WORK_CODEX_RUNG != "off"`, `_AUTOPILOT_ESCALATION != "legacy"`, a `"healthy"` batch probe, and a terminal attempt that was not itself codex). **Read `references/codex-implementor.md` § Codex rung interception before the first codex dispatch of a batch** — it states each fence exactly and why fence 4 is not optional.

`scripts/work_routing.py` is a decision model of the table and this interception, tested in isolation by `scripts/test_work_routing.py`; it is kept in sync with this prose by review, not by a test that flips red when the prose changes. The one exception is the `codex_eligible` fence itself: `test_work_routing.py` extracts it live from `model-ladder.md` § Codex rung, so editing a clause's field or value, adding or removing a clause, or changing the `OR` that joins them, all flip a test red (see `test_codex_eligible_agrees_with_every_clause_extracted_from_the_real_ladder` and `test_extractor_raises_when_the_fence_joins_clauses_with_a_non_or_combinator`). A cosmetic reword of the fence's own opening line (e.g. renaming the pseudocode parameter) does not — the extractor's fence-selection match is deliberately loose there. The guard binds the fence to `_codex_eligible`, not the reverse: widening `_codex_eligible` to a value no clause and no candidate in `_CODEX_ELIGIBLE_CANDIDATES` names is not caught, so an edit there still needs review.

The memory-pressure gate (row 4) runs only when the table would otherwise reach qwen (now row 5) — it never runs for UI, `opus`, `qwen_eligible == false`, or breaker-skipped tasks.

**`fable` overrides this table outright.** A task carrying `state.tasks[i].model: "fable"` — set only by the Fable rescue gate (`run-autopilot/references/recovery.md` § Rework escalation exhausted) — never routes to qwen and never to Gemini: dispatch a Claude Agent at `model: "fable"`, whatever the rows above would pick. `fable` is never a session model and is never selected autonomously, so the human rescue gate is the only way in (`run-autopilot/references/model-ladder.md` § Fable rescue).

qwen never sees `opus`-tier or UI tasks — `state.tasks[i].qwen_eligible` is already `false` for those upstream.

**qwen capability breaker (routing-time consult, row 3).** Guarded by `_AUTOPILOT_ESCALATION != "legacy"` (`model-ladder.md` § Kill-switches) — under `legacy` the breaker is fully off, row 3 never fires, and rows 5-6 behave exactly as today's rows 3-4. The memory-pressure gate (row 4) is a deliberate always-on exception to that kill-switch: it carries no `_AUTOPILOT_ESCALATION` guard (unlike the breaker) and keeps firing under `legacy` — a host-safety mechanism, not a quality mechanism, so the kill-switch that restores old routing semantics must not also switch off OOM protection.

**Read `references/qwen-integration.md` § Batch-scoped preflight before the first qwen dispatch of a batch** — it carries the breaker's batch-scope reset and row-3 consult, and the `state.qwen_preflight` cache procedure (probe once per batch, reuse the verdict, and the two backend-health signals that force a re-probe). One rule lives here too, because a passing run never opens that reference: a qwen gate pass resets `qwen_gate_failures_consecutive` to 0, so the breaker trips only on two CONSECUTIVE qwen gate failures.

**Re-evaluate the routing table for EVERY claimed task — no session-level memory.** The table is per-task, and so is the qwen one-shot-per-task budget: exactly one qwen dispatch per task (success OR failure) — a qwen attempt on task A never excludes qwen for task B. There is no per-PRD or per-batch qwen cap; every eligible task is routed independently. Do not generalize a fallback ("qwen was slow on the last task, route the rest to Claude") — that decision belongs to the table and the preflight, not to session memory (observed failure: `references/design-rationale.md` § no session memory). Self-check before each Ivan dispatch: if `state.tasks[i].qwen_eligible == true` and you are about to dispatch Claude, the attempt log MUST carry a non-`"healthy"` `preflight_outcome` justifying the fallback — if it would read `null` or `"healthy"`, you skipped the table; run it now. **Exception:** the qwen capability breaker (row 3 above) and the memory-pressure gate (row 4 above) are the two deliberate, state-tracked overrides — the breaker reroutes off `qwen_breaker.tripped` (durable, batch-scoped state) and the pressure gate reroutes off `check_memory_pressure.py`'s exit code (host memory state); neither is ad-hoc session judgment. The self-check above only applies when rows 3 and 4 did not fire (a breaker-skipped or pressure-gated attempt's `null` `preflight_outcome` is expected, not a skipped table).

**An escalated tier belongs to its task and dies with it (PRD 00111).** When a task escalates — in-loop at step 5.5, or by review flag through `/run-autopilot` Phase 6 — the higher tier is written to that task's `model` field in `state.tasks[i]`, and nowhere else. Every other task still enters at the tier `/plan-tasks` classified for it: a task escalated to `opus` is followed by an unrelated `haiku` task dispatching at `haiku`, in the same PRD and the same session. Do not carry a tier sideways ("the last task needed opus, so this PRD runs at opus") — that is the same session-memory mistake the routing rule above forbids, priced one rung higher. Nothing escalation-related survives into the next PRD either: `autopilot reset-prd` drops `tasks` (the per-task tiers), `rework_task_ids`, `cap_rotations` and `stall_reason`, and zeroes `replan_count` (`run-autopilot/cli/records.py` `PER_PRD_RESET_FIELDS`). Session-model decay is the separate, matching rule in `run-autopilot/references/model-ladder.md` § Decay.

**Gemini availability check.** "Gemini if available" means the `use-gemini` helper resolves AND can run a no-op probe. Concretely: `${CLAUDE_PLUGIN_ROOT}/skills/use-gemini/scripts/gemini-run.sh` is executable AND `mise which gemini` (or `command -v gemini`) exits 0. If either fails, fall back to Claude at `state.tasks[i].model` for that UI task. Treat a runtime helper-script failure (non-zero exit, no output) the same way: record the failure and re-dispatch the task to Claude at the task's tier. Cross-reference: `references/gemini-integration.md`.

`use-qwen`, `use-gemini`, and `use-codex` are Bash helper-script dispatches; Claude implementor passes are Agent dispatches at the task's tier. All three must satisfy the **Subagent Dispatch Budget** and the **Subagent Watchdog**.

**Codex implementor mechanics.** The HOW of the codex rung — batch health probe, dispatch checklist, TOOL-GATE NOTICE — lives in `references/codex-implementor.md`; **read it in full before the first codex probe or dispatch of a batch**. Two invariants worth repeating at the call site: never `-y` (the `-a` grant covers this rung only), and on any codex timeout `TaskStop` + verify-gone BEFORE dispatching the Claude fallback.

### 4. Handle result

| Result | Action |
|--------|--------|
| Success | Continue to step 5. |
| Timeout | Append attempt-log entry (`outcome: "aborted"`, `cause: "timeout"`). Split task per `references/task-splitting.md`, mark original as blocked. |
| Context exceeded | Append attempt-log entry (`outcome: "aborted"`, `cause: "context_overrun"`). Split task per `references/task-splitting.md`, mark original as blocked. |
| Error | Invoke `debug-stuck-agent` (step 4.5). On unrecoverable error, append attempt-log entry (`outcome: "aborted"`, `cause: "error"`). Report to user. |
| Result lost / hung | The Agent result is empty, is `[Tool result missing due to internal error]`, or the Subagent Watchdog killed a hung agent. This is an infrastructure failure, not real work — apply the **infrastructure-failure circuit breaker** (step 4.2). |

**Codex carve-out.** A codex dispatch's timeout, missing/empty `-o` output, and a watchdog-killed hang are all arm 1 (Infra) per `model-ladder.md` § Codex rung — never the generic Timeout / Result-lost-hung rows above, never split-task, never the 4.2 breaker. On timeout, apply the kill-before-fallback rule from the codex dispatch checklist (`references/codex-implementor.md` § Codex dispatch): `TaskStop` the codex background task and verify it is gone BEFORE dispatching the Claude fallback — an orphaned `--sandbox workspace-write` codex keeps write access to the very files the fallback implementor is about to edit, so its late writes either get swept into the fallback's commit or land as unexplained foreign paths. Fall back to Claude at the task's tier, no escalation stamp. The `codex_no_edit` / `codex_no_edit_probe_exit` flags latched during dispatch (step 3) are likewise not resolved here — they are consumed by step 5.5's classification (arm 2), per the same ladder section.

### 4.2. Infrastructure-failure circuit breaker

A lost/empty Agent result or a watchdog-killed hang is an infrastructure failure, not a content failure. Do **not** silently re-dispatch in a loop — two back-to-back infrastructure failures on the same task once caused a multi-hour stall (`references/design-rationale.md` § circuit breaker).

Re-dispatch the **same** task at most **once** — that cap is separate from the test-failure retry cap (step 5.5) and the review-cycle cap (step 5.7). **Read `references/gate-failure.md` § Infrastructure-failure circuit breaker before re-dispatching**: it carries the working-tree check and the second-failure stop (attempt entry `cause: "subagent_infra_failure"`, `state.stall_reason`, escalate, never advance).

### 4.5. Debug on error

If the tool returned an error, invoke the `debug-stuck-agent` skill to diagnose the root cause before reporting to the user (`references/gate-failure.md` § Debug on error). If debugging resolves the issue, continue to step 5. If not, report to user and keep task in_progress.

### 5. Commit changes

Stage exactly this task's files, then commit in a separate Bash call. **Never `git add -A` or `git add .`** — the worktree is live (the user edits files during dispatches), and a bulk add sweeps foreign uncommitted work into the task commit (memory: feedback_subagents_vs_live_worktree).

1. Build the stage list: the paths from Ivan's `FILES_TOUCHED:` footer (see **Assumptions footer**), plus any build-generated files this task's changes legitimately produced (lockfiles, snapshots, generated bindings) — identified from `git status --porcelain` output, never guessed.
2. Fallback when the footer is absent or `none` while the tree is dirty (legacy retry prompts, malformed report): stage the intersection of dirty paths with the exact files the plan task names; treat every other dirty path as foreign.

```bash
git add <path> [<path> ...]
```
```bash
git commit -m "<type>(<scope>): <description>"
```

Any other dirty path is **foreign**: leave it unstaged and untouched, and name it in the phase report (fail loud) — the same never-commit-foreign-work rule the step-5.5 ESCALATE reset guard enforces.

Never chain these with `&&` in a single Bash call. Commit message rules: conventional commit format, one line, no period, reference the task ID if available.

Before committing a `feat`/`fix` (or breaking) change, verify CHANGELOG.md is staged in the same commit per rules/changelog.md — repos with a declared no-changelog exception (e.g. the buvis home repo) skip this check.

**If a commit (or its `git add`) is rejected** — `aegis`'s `validate_commit_msg.py` blocks a non-conventional message (boilerplate trailer, HEREDOC, bad format — `rules/development-workflow.md`), or warden denies the `git add`/`git commit` command: read the deny reason from the blocked tool result (aegis names the format violation; warden's reason usually names the preferred command form), fix the message or the command accordingly, and **retry the commit ONCE**. Still rejected after the one repair → ESCALATE: append an attempt-log entry (`outcome: "aborted"`, `cause: "commit_rejected"`), then report to the user (interactive) or take the loop-mode stall path (`run-autopilot/references/recovery.md`, `site: "sub_skill_fail"`, `detail` = the deny reason) — never leave the task's work uncommitted-and-unrecorded, and never reach for `--no-verify` to bypass the hook. This branch applies to every commit this skill makes (step 2.9 tests, step 5 implementation, the step-5.5/5.7 re-commits, the step-5.6 deslop commit).

### 5.5. Verify THIS task's tests pass

Run **only** the specific tests Tess wrote in step 2.7. Do NOT run the full project test suite, smoke tests, integration tests, or lint here — those run once at the end of the phase (step 7).

- Target the narrowest scope that covers the new tests:
  - Rust: run `cargo check -p <crate>` first — a compile failure IS the gate failure (skip the test run, go straight to the retry path with the compiler output); then `cargo test -p <crate> --test <test_file>` or `cargo test -p <crate> <module::test_name>`
  - Python: `pytest path/to/test_file.py::test_name`
  - JS/TS: `vitest run path/to/test_file` or `jest path/to/test_file`
- Never dispatch Tess to weaken tests.
- **Retry prompts** (feedback retry, repair re-dispatch, escalation dispatch, step 5.7's confirmed findings, step 7's regression fix) re-render `ivan.md` in full from `references/gate-failure.md` § Retry render — only `FAILING_TESTS` and `RETRY_INSTRUCTION` change, and a missing placeholder exits 1.

**Do not run here:** `cargo test --workspace`, `cargo clippy --workspace`, `./tests/smoke.sh`, `./tests/integration.sh`, `cargo test-full`, or any equivalent full-suite command. These are batched into step 7.

**Gate-failure handling.** Read `_AUTOPILOT_ESCALATION` (env var; `model-ladder.md` § Kill-switches).

**`_AUTOPILOT_ESCALATION == "legacy"`** — no diagnosis, repair, escalation, attribution stamping or qwen capability breaker: re-dispatch Ivan with the failure output, max 2 implementation retries, then escalate to the user. The branch is stated in full in `references/gate-failure.md` § Legacy escalation branch.

**Any other value / absent — diagnose→repair/escalate flow (default):** see `references/gate-failure.md` for the full flow. Read it before the first gate failure of a batch.

### 5.6. Self-deslop pre-commit pass

After step 5.5's tests pass and BEFORE the per-task code review at step 5.7, dispatch a fresh subagent to prune slop from the implementor's diff. The per-task review then runs against the leaner diff, which means review-rework cycles add defensive fixes on top of a smaller base. Best-effort: this step never blocks the task and never triggers retries.

**Skip rule.** Measure the implementor's most recent commit:

```bash
git diff --shortstat HEAD~1..HEAD
```
```bash
git diff-tree --no-commit-id --name-only -r HEAD
```

Compute `net_lines = insertions - deletions` (from `--shortstat`) and `file_count` (lines from `diff-tree`). If `net_lines < 30` OR `file_count < 2`, skip the dispatch — the cleanup overhead exceeds the slop budget for trivially small changes. Record `self_deslop: "skipped:trivial"` on the latest attempt (see "Outcome logging" below) and proceed directly to step 5.7.

**Read `references/self-deslop-prompt.md` § Procedure before the first step-5.6 dispatch of a batch** — it carries the dispatch contract (a **fresh** Agent call at `state.tasks[i].model`, **Subagent Dispatch Budget** + **Subagent Watchdog**), the placeholder substitutions, and the outcome table that maps each subagent result to its `self_deslop` value. `{{task_description}}` comes from `tasks[i].description`, falling back to the name-only body when `description` is absent.

**Outcome logging.** Hold the result in-session and write it as the `self_deslop` field of the attempt record step 6 builds — do NOT write it here as a separate indexed state mutation. On a first attempt `tasks[i].attempts` is still empty at this point (step 6 is what appends the entry), so a `tasks[i].attempts[-1].self_deslop` write fails outright: `statectl` exits 1 with `json-path index out of range: [-1]`, reproduced against a scratch state. Carrying the value into step 6's payload also keeps the whole task transition in the one `task-done` write.

**Do not retry self-deslop on failure** — best-effort means single attempt only.

### 5.7. Per-task code review

**Tier gate — per-task review is skipped only on haiku.** Read the task's `model` field (`state.tasks[i].model`):

| `state.tasks[i].model` | Per-task review (step 5.7) |
|-----------------------|----------------------------|
| `haiku` | skip per-task review |
| `fable` | review (below) — the rescue rung is reviewed like `opus` |
| anything else — `opus`, `sonnet`, absent/legacy or unknown (both treated as `sonnet`) | review (below) |

Dispatch the reviewer after commit and verification — a native lane, no plugin dependency:

1. Get SHAs: `BASE_SHA` = the parent of this task's test commit (`<test_commit_sha>` from step 2.9), `HEAD_SHA` = current HEAD (includes the step-5.6 deslop commit when one landed).
2. Render the review prompt with one Bash call, every interpolated path `shlex.quote()`-d (or bash's `printf '%q '`) before it lands inside a `--set-cmd` value:
   ```bash
   python3 ${CLAUDE_PLUGIN_ROOT}/skills/work/scripts/render_prompt.py ${CLAUDE_PLUGIN_ROOT}/agents/pat.md \
     --out dev/local/tmp/review-task-<id>-prompt.md \
     --set-file TASK_SUBJECT=dev/local/tmp/review-task-<id>-subject.txt \
     --set-file TASK_DESCRIPTION=dev/local/tmp/review-task-<id>-description.txt \
     --set-file TASK_ACCEPTANCE_CRITERIA=dev/local/tmp/review-task-<id>-acceptance.txt \
     --set-cmd DIFF="git diff BASE_SHA..HEAD_SHA" \
     --set-file SIMPLIFICATION_MANDATE=${CLAUDE_PLUGIN_ROOT}/skills/work/references/simplification-mandate.md
   ```
   The **Pat persona** (`${CLAUDE_PLUGIN_ROOT}/agents/pat.md`) already carries the read-only statement and the reporting contract — one finding per line as `SEVERITY | file:line | issue | fix` (severities CRITICAL/HIGH/MEDIUM/LOW), or the literal line `NO FINDINGS` — so do not restate them here. Conventions and the placeholder table: `review-work-completion/references/agent-registry.md`. If `pat.md` is missing or its frontmatter does not parse, treat it as a runner failure (step 4's retry-once branch) — never fall back to a hand-written prompt. The stdout integer from the render call **is** the Subagent Dispatch Budget measurement — no separate `wc -c`.
3. **Read `references/per-task-review.md` before the first step-5.7 dispatch of a batch** — it carries the `sonnet-run.sh` dispatch command (never `-a`/`-y`), the result-handling ladder (CLOSURE verdicts, CRITICAL/HIGH, the 3-cycle cap, a runner failure recorded as `review: failed:<cause>`), and why the lane is tier-gated. One row stays here, because a passing review still has to stamp it:
   - **MEDIUM inside this task's files** (the finding's file path, before its `:line` suffix, names a file in Ivan's `FILES_TOUCHED:` footer for this task) - ONE retry through the CRITICAL/HIGH row's procedure above, with two differences: the loop ends after a single Pat re-run (no third dispatch, whatever it returns), and step 6 appends `medium-retry:fixed` to the attempt record's `review` string when that re-run no longer lists the finding, `medium-retry:unfixed` otherwise. Why: a MEDIUM Pat already located costs one Ivan dispatch here and a four-reviewer cycle plus a rework task later (PRD 00140).

Skip for documentation-only or configuration-only tasks.

### 6. Mark complete and sync

1. **Build the attempt record** per the "Attempt logging" section: `outcome: "completed"`, `model` from `state.tasks[i].model`, `pipeline` from `state.tasks[i].model` (`haiku` → `"minimal"`, `sonnet`/absent/legacy → `"lean"`, `opus` → `"full"`) plus `fable` → `"full"` (the rescue rung runs the deepest pipeline, like `opus`), `cause: null`, `review_cycle: null` on a Phase-3 first pass or the current `state.cycle` on a rework pass. When `state.tasks[i].escalation_reason` / `state.tasks[i].escalated_from` are present (set by `/run-autopilot` Phase 6 for a review-flag escalation), **copy both onto the entry** so `escalation_reason: "review_flag"` reaches `attempts[]`; absent → omit both.
2. **Land the whole transition in ONE `statectl` call.** Write the record from point 1 to `dev/local/tmp/attempt-task-<id>.json` with the **Write tool** (never a shell redirect — an attempt record carries quotes and newlines), then:

   ```bash
   python3 ${CLAUDE_PLUGIN_ROOT}/skills/run-autopilot/scripts/statectl.py <state.json> task-done <task-id> dev/local/tmp/attempt-task-<id>.json
   ```

   `task-done` sets `tasks[i].status = "completed"`, appends the record to `tasks[i].attempts`, and **recomputes `tasks_completed` from the task array** — all three inside one locked atomic write. Do NOT set `status`, append the attempt, or set `tasks_completed` separately here; the count is derived and is not passed in. The task is resolved by matching `tasks[].id`, so the `tasks[N]` index form is not used here (rework appends `[D{cycle}]` follow-ups, after which array position stops matching id).

   The matching call at task start (step 2) is `statectl <state.json> task-start <task-id>`.
3. **Append `ASSUMPTIONS:` lines** from this task's Tess and Ivan reports (any entry beyond `none`) to `dev/local/meta/assumptions.md` per the **Assumptions footer** section
4. Proceed to step 6.5 (task-boundary handoff check) — it routes to the next task, a clean handoff, or final verification.

### 6.5. Task-boundary handoff check

After step 6, decide whether to finish the remaining tasks in this session or hand them to a fresh one.

**If no pending tasks remain**, skip this step — proceed to step 7. Final verification runs in whichever session finishes the last task. Otherwise resolve the autopilot dir with `python3 ${CLAUDE_PLUGIN_ROOT}/skills/run-autopilot/scripts/_walk_up.py --bash` and read `<dir>/.handoff-requested`: **absent** → return to step 1 for the next task, no handoff. **Present** → **read `references/task-boundary-handoff.md` and follow its procedure** (clean-tree check, marker removal, banner, contract card, `next_phase: "build"`, STOP). Do NOT return to step 1 and do NOT run step 7 on that path.

### 7. Final verification (once per work phase)

After all tasks in the phase are marked completed, run the project's full verification suite **once**. This is the single point where the full suite runs — per-task verification (step 5.5) only ran the new tests in isolation, so this step is mandatory and must not be skipped.

#### 7.0. Style-limit gate

Before the suite, measure what this phase's diff introduced. Base = `state.work_start_sha` (`statectl get work_start_sha`; captured once per PRD before the first `/work` pass, so it survives task-boundary handoffs and a first task that wrote no tests); every git invocation below runs with the repo's own `--git-dir`/`--work-tree` flags in a bare-repo home. Write the diff with `git diff <base>..HEAD --output=dev/local/tmp/phase-diff.txt` and list the changed Python files with `git diff --name-only --diff-filter=d <base>..HEAD -- '*.py'` (deleted files excluded: the script reads every path it is given). No `.py` file changed: skip the script and record `style_gate: clean`. Otherwise run `python3 ${CLAUDE_PLUGIN_ROOT}/skills/work/scripts/check_style_limits.py --diff dev/local/tmp/phase-diff.txt <those files as absolute paths>`; exit 0: record `style_gate: clean`. Exit 1: write the violation lines to the `FAILING_TESTS` scratch file and dispatch Ivan once with the full retry command shape from step 5.5 and `--set RETRY_INSTRUCTION="Fix only the listed style-limit violations; do not touch other code"`, commit per step 5, re-run the gate: clean -> `style_gate: fixed:<sha of the fix commit>`; still exit 1 -> `style_gate: failed:<the violation lines, joined by "; ">` and proceed to the suite anyway (fail loud, never silent). Exit 2 (or any other non-0/1 exit): the gate could not run at all, so there are no violation lines to hand a fix agent — record `style_gate: failed:<the script's stderr message>`, do NOT dispatch Ivan, and proceed to the suite anyway (fail loud, never silent, same as the still-failing exit-1 case). Function spans come from `review-work-completion/scripts/compute_mech_facts.py`, reused by import (see `## Dependencies`).

**What to run** (project-dependent — use the commands documented in `AGENTS.md` / `CLAUDE.md` / project README):

- Full workspace tests — Rust: `cargo nextest run --workspace` when nextest is installed (probe once with `cargo nextest --version`; on any nextest infra error fall back to `cargo test --workspace` — doc-tests are NOT run by nextest, so add `cargo test --workspace --doc` when the project has doc-tests); otherwise `cargo test --workspace`. Other stacks: `pytest`, `npm test`
- Lint (e.g., `cargo clippy --workspace`, `ruff check`, `eslint .`)
- Smoke tests if the project defines them (e.g., `./tests/smoke.sh`)
- Integration / e2e tests if the project defines them (e.g., `./tests/integration.sh`, `cargo test -p <crate>-e2e`)
- Any project-specific "definition of done" checks

**When the repo documents no verification commands** (no test/lint/build commands in `AGENTS.md`/`CLAUDE.md`/README): do NOT silently skip verification. Detect the stack from its manifest and improvise the standard suite — `Cargo.toml` → `cargo test --workspace` (+ `cargo clippy --workspace`); `pyproject.toml`/`setup.py` → `pytest` (+ `ruff check` if configured); `package.json` → `npm test` (only if a `test` script exists). Run the improvised set, and **state the exact improvised command set in the phase report** (fail loud — an improvised suite must not read as the project's own documented one). If no stack manifest is detectable and nothing runs, record `verification: none (no suite found)` in the phase report and surface it as a gap for the review phase — never report the phase green on an unverified tree.

Run each as a separate Bash call. Do not chain with `&&`.

**Handling failures at this step:**

1. Identify which task(s) introduced the regression. The failing test output usually points at a specific module; cross-reference against the task commits.
2. Re-open the offending task via `task-start <task-id>`.
3. Dispatch Ivan with the failure output to fix it: re-render `ivan.md` using the **full** retry command shape from step 5.5 (every placeholder filled, explicit `--out`), with `FAILING_TESTS` filled from the step-7 failure output and `--set RETRY_INSTRUCTION="Fix only the regression identified below. Do not touch unrelated files or refactor adjacent code."`. The code-quality rules block is already permanent in `ivan.md`. Do NOT relax the failing test.
4. After the fix commits, re-run **only** the previously failing commands from step 7 (not the whole suite again) to confirm the fix.
5. Mark the task completed and re-sync.
6. Repeat until the full suite is green.

Max 3 fix cycles at this step before escalating to the user — regressions clustering here usually indicate a design issue that needs human input.

Only stop the work phase once step 7's test suite is fully green — a recorded `style_gate: failed:<violations>` from step 7.0 is a sanctioned way for the phase to complete, not a reason to keep looping or stall; the suite itself still has to pass.

When reporting the phase result, include the `style_gate: <value>` line from step 7.0 and the contents of `dev/local/meta/assumptions.md` (if present) - the assumption ledger is input to the review phase and the user's 30-second examine pass.

## Reference Files

- `references/test-author-prompt.md` - Tess context-selection rules; points at the two templates below
- `references/tess-prompt.md` - Tess initial dispatch template (rendered by `render_prompt.py`)
- `references/tess-retry-prompt.md` - Tess quality-gate retry template (rendered by `render_prompt.py`)
- `references/adversarial-test-prompt.md` - Adversarial validator (Devon) prompt template
- `references/codex-integration.md` - Codex review-only usage
- `references/codex-implementor.md` - Codex rung mechanics: batch health probe, dispatch checklist, TOOL-GATE NOTICE (read before any codex probe/dispatch)
- `references/gemini-integration.md` - Gemini prompt templates, patterns, and the Design Authority section
- `references/qwen-integration.md` - qwen dispatch + four-check preflight protocol
- `references/code-quality-principles.md` - Think/Simplicity/Surgical/Goal-driven rules to inject into Ivan prompts
- `references/code-quality-examples.md` - Before/after examples of the anti-patterns those rules prevent
- `references/subagent-dispatch.md` - Dispatch Budget + Watchdog: how to safely make an Agent call
- `references/task-splitting.md` - Splitting a timed-out or oversized task, plus the parallel-rework cap
- `references/attempt-logging.md` - `state.tasks[].attempts[]` entry schema and write procedure
- `references/gate-failure.md` - Step 5.5 diagnose→repair/escalate flow (read before the first gate failure of a batch)
- `references/self-deslop-prompt.md` - Step 5.6 prompt template (placeholders + `{{slop_catalog}}` substitution)
- `references/simplification-mandate.md` - Step 5.7 reviewer-prompt appendix (append verbatim)
- `references/design-rationale.md` - incident history behind the rules (non-normative)
