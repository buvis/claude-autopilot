# Design: Cut Build-Phase Clerical Overhead

PRD: `dev/local/prds/wip/00093-cut-build-phase-clerical-overhead-v1.md`

Two of six features are already shipped (commit `9b3d575a7`): the `statectl`
compound verbs (`task-start`/`task-done`/`set-contract-card`) and the batched
`TaskList` hydration in `run-autopilot/SKILL.md`. This design covers the four
remaining: the implementor persona + scripted substitution, the batch-scoped
qwen preflight, and the red-check module-existence skip, plus the Phase 2
measurement script.

## Architecture fit

`~/.claude` has no application layers in the usual sense — it is a set of
Claude Code skills (prose procedures) plus small stdlib Python scripts they
shell out to. This work lands entirely inside that pattern:

- `work/scripts/` already holds two such scripts (`check_memory_pressure.py`,
  `diagnose_task.py`), each a single-purpose stdlib CLI with an argparse
  front end, a paired `test_*.py`, and a small integer/string exit-code
  contract. `render_prompt.py` and `check_build_overhead.py` are new members
  of the same family, not a new layer.
- `~/.claude/agents/*.md` is the existing flat persona-file convention
  (`agent-registry.md`), already home to 13 registered personas including
  Pat, the per-task reviewer `work/SKILL.md` dispatches today. `ivan.md`
  joins that set as a 14th file — no new mechanism, no new directory.
- `work/SKILL.md` and `run-autopilot/SKILL.md` are prose procedures the
  orchestrator (a Claude session running `/run-autopilot` → `/work`) follows
  turn by turn. Every change here is a prose edit to those procedures,
  replacing "assemble this prompt inline" with "call this script", or
  "probe every task" with "probe once per batch, cached in `state.json`".

## Module placement

**New files:**

| Path | Purpose |
|---|---|
| `work/scripts/render_prompt.py` | Strip a persona's frontmatter, substitute `{PLACEHOLDER}` tokens, write the result, print its byte size. |
| `work/scripts/test_render_prompt.py` | Unit tests for the above. |
| `agents/ivan.md` | The implementor persona — every fixed block of today's inline step-3 prompt. |
| `work/references/tess-prompt.md` | Tess's dispatch prompt extracted from `test-author-prompt.md`'s "Prompt Template" fenced block, reshaped to registry-style single-brace placeholders so `render_prompt.py` can consume it. See "Tess template split" below. |
| `work/scripts/check_build_overhead.py` | Reads a session transcript (`.jsonl`), reports `TaskCreate` turn count, `statectl` calls per completed task, and prompt-authoring `Write` call count. |
| `work/scripts/test_check_build_overhead.py` | Unit tests, plus a golden-number assertion against the engram baseline transcript named in the PRD. |

**Edited files:**

| Path | Change |
|---|---|
| `work/SKILL.md` | Step 2.7 (Tess dispatch), step 3 (Ivan dispatch), step 5.7 (Pat dispatch) rewritten to call `render_prompt.py` instead of assembling prompts inline. Step 3's qwen preflight paragraph rewritten to the batch-scoped cache. Step 2.95 (red check) gains the module-existence pre-check. |
| `work/references/test-author-prompt.md` | "Prompt Template" section replaced with a pointer to the new `tess-prompt.md` (single source of truth); "Context Selection" and "Retry Prompt" sections untouched — the 2.8 retry path is out of this PRD's named scope (see Risks). |
| `review-work-completion/references/agent-registry.md` | Six new rows in the placeholder table: three for Ivan (`{FAILING_TESTS}`, `{ARCHITECTURE_CONTEXT}`, `{FILE_PATHS}`), plus `{RETRY_INSTRUCTION}` (also Ivan — see step 3/5.5/7 data flow below), and three for Tess (`{SAMPLE_TEST_FILE}`, `{PUBLIC_INTERFACES}`, `{TEST_FRAMEWORK}` — `{TASK_SUBJECT}`/`{TASK_DESCRIPTION}`/`{TASK_ACCEPTANCE_CRITERIA}` already have rows, reused verbatim). Ivan is **not** added to "## The roster" — that table is reviewer-lane dispatch, and Ivan is an implementor, not a reviewer. |
| `run-autopilot/references/state-schema.md` | New `qwen_preflight` field row, mirroring the existing `codex_probe` row's shape and prose. |

**Already shipped, no further edit:** `run-autopilot/scripts/statectl.py` (compound verbs), `run-autopilot/SKILL.md` § Hydrate TaskList (batched hydration).

## Interfaces & contracts

### `render_prompt.py`

```
python3 render_prompt.py <persona> --out <path>
    [--set KEY=VALUE ...] [--set-file KEY=PATH ...] [--set-cmd KEY=CMD ...]
```

- `<persona>`: path to any file. If its first line is exactly `---`, everything
  up to and including the next line that is exactly `---` is stripped
  (YAML frontmatter, as on every `agents/*.md` file). A file with no leading
  `---` line is used as-is (this is what lets `tess-prompt.md` skip
  frontmatter entirely — it is never dispatched as a native agent type).
- `--set KEY=VALUE`: literal substitution value. Repeatable.
- `--set-file KEY=PATH`: value is the full contents of `PATH` (read as UTF-8
  text). Repeatable. `PATH` missing or unreadable is a **fatal error**:
  print `render_prompt: --set-file path not found for {KEY}: <path>` to
  stderr and exit 4.
- `--set-cmd KEY=CMD`: value is the stdout of `CMD`, run via
  `subprocess.run(CMD, shell=True, capture_output=True, text=True)`, with a
  trailing newline stripped. Repeatable. A non-zero returncode is a **fatal
  error**: print `render_prompt: --set-cmd failed for {KEY}: <cmd>
  (exit <n>): <stderr, one line>` and exit 4 — empty stdout is never
  silently substituted as if it were a valid empty value. **Trust
  boundary**: `CMD` runs through a shell inside this script's own process —
  never pass caller input that did not originate from the orchestrating
  skill itself (the same trust level the skill already extends to its own
  Bash tool calls). This is what lets a caller do `--set-cmd
  FAILING_TESTS="cat test_a.py test_b.py"` to concatenate multiple
  already-committed files into one placeholder without a separate
  Write-tool scratch step — `cat` inside a script's own subprocess is not
  the orchestrator's Bash tool call, so the `prefer_tools.py` hook (which
  gates the agent's own tool use, not subprocesses a script spawns) does not
  see it. **Every path interpolated into a `CMD` string must be
  `shlex.quote()`-d by the caller before composing the flag value** — a raw
  concatenation breaks on any path containing a space (plausible on macOS),
  splitting `cat`'s argument list. This is the orchestrating skill's
  responsibility (the string arrives at this script already assembled);
  `render_prompt.py` itself does no path discovery, so it cannot quote what
  it never sees as separate tokens.
- Placeholder scan: after frontmatter stripping, find every `{[A-Z_][A-Z0-9_]*}`
  token in the body via regex, and de-duplicate to the distinct set of names
  found (a token appearing twice in the body is one required key, not two).
  Build the substitution map from `--set` / `--set-file` / `--set-cmd`
  (last-write-wins if a key repeats across flag kinds; `--set-file`/`--set-cmd`
  failures above abort before the map is considered complete). **Validate
  before substituting**: compute `missing = found_names - map.keys()`; if
  non-empty, print `render_prompt: missing placeholder: {NAME}` (first name,
  sorted, for a deterministic message) to stderr and exit 1 — never emit a
  prompt containing a literal `{NAME}`, and never attempt substitution when
  any placeholder is unfilled. A `--set*` key with no matching token in the
  body is silently unused (not an error — callers may share one flag set
  across persona variants).
- Substitution is single-pass and runs only after the validation above
  passes, so the lookup inside it can never raise: build the output by
  scanning the body once and replacing each matched `{NAME}` token with its
  value from the map (e.g. `re.sub(r'\{[A-Z_][A-Z0-9_]*\}', lambda m:
  values[m.group(0)[1:-1]], body)` — safe here specifically because the
  validation step already guarantees every match has a map entry). A
  substituted value that itself contains a literal `{NAME}`-shaped sequence
  is inserted as-is and never re-scanned — `re.sub`'s replacement function
  output is not fed back through the pattern.
- Output: write the substituted body to `--out`. If `--out`'s parent
  directory does not exist, that is a **fatal error**: print `render_prompt:
  output directory does not exist: <dir>` to stderr and exit 5 — this
  script never creates directories (same convention as every other
  `dev/local/tmp/` scratch write in this codebase, where the caller is
  responsible for `mkdir -p` once per session, not per call). Print the byte
  count of the written file to stdout, and nothing else on success.
- Exit codes: `0` success. `1` unfilled placeholder. `2` persona file does
  not exist or is not readable. `3` persona opens with a `---` line but
  never closes it (malformed frontmatter — unterminated block). `4` a
  `--set-file` path does not exist/is not readable, or a `--set-cmd`
  subprocess exited non-zero. `5` `--out`'s parent directory does not exist.

### `agents/ivan.md`

Frontmatter: `name: ivan`, `description` (≤120 chars, e.g. "Implementor.
Makes failing tests pass against a fixed file allowlist. Read-only on test
files, no visibility into acceptance criteria."), `tools: Read, Edit, Write,
Bash` (Ivan is the only registry persona with edit access — the "No registry
reviewer may carry Edit or Write" rule in `agent-registry.md` § Tool sets
governs *reviewers*; Ivan is the implementor, exactly like Devon and Tess
already have write access as non-registry Agent-tool dispatches).

Body (every line below is **fixed text baked into the file**, per the PRD's
own "Outputs: `ivan.md` carrying every fixed block" — only the three
placeholders vary per dispatch):

```
You are Ivan, the implementor. Make all failing tests pass. Tests ARE the
spec. Do NOT modify test files. Do NOT read the task's acceptance criteria —
none are provided to you on purpose.

## Failing tests

{FAILING_TESTS}

## Architecture context

{ARCHITECTURE_CONTEXT}

## Files you may read and modify

{FILE_PATHS}

Read only the files listed above. If a file or symbol you need is not
listed, stop and report it as a blocker — do not run broad `rg` sweeps to
discover scope.

{RETRY_INSTRUCTION}

### Code quality rules (mandatory)

<verbatim copy of code-quality-principles.md's "Prompt Snippet" section,
between its BEGIN/END markers>

Abort and report if you read more than 100K of total input. Return the
partial result and an abort_reason: context_overrun field.

Read every file before your first Edit to it. Never call bash `head`,
`tail`, `cat`, `grep`, or `find` - a hook blocks them. Use the Read tool
(offset/limit), `rg`, or `rg --files` instead.

End your report with `ASSUMPTIONS:` - one line per assumption you made
where the task, tests, or listed files were silent (guessed interface, data
shape, resolved ambiguity, unstated behavior). Write `ASSUMPTIONS: none` if
you made none.

Also end your report with `FILES_TOUCHED:` - one line per file you created
or modified, path relative to the repo root. Write `FILES_TOUCHED: none` if
you changed no files.
```

This is byte-equivalent to what step 3 assembles today (per-task-varying
content aside) — the design's Phase 0 acceptance criterion ("rendering it
with representative values reproduces the fixed sections of today's prompt")
is a direct text diff between this body and the current inline assembly at
`work/SKILL.md` §3, `references/code-quality-principles.md`, and
`references/subagent-dispatch.md`.

### `agent-registry.md` new placeholder rows

| Placeholder | Substituted with |
|---|---|
| `{FAILING_TESTS}` | Failing test file paths and their content (Ivan). |
| `{ARCHITECTURE_CONTEXT}` | AGENTS.md/interface/relevant-module context Ivan needs to implement against (Ivan). |
| `{FILE_PATHS}` | The exact file paths Ivan may read and modify for this task (Ivan). |
| `{RETRY_INSTRUCTION}` | Empty string on the initial dispatch (step 3); a retry-specific one-line instruction on a re-dispatch (step 5.5's SURGICAL line or step 7's regression-fix line — see Data flow) (Ivan). |
| `{SAMPLE_TEST_FILE}` | One representative existing test file, for style/convention (Tess). |
| `{PUBLIC_INTERFACES}` | Type definitions / function signatures / module exports the new tests will call (Tess). |
| `{TEST_FRAMEWORK}` | The project's test framework name (pytest/jest/vitest/etc.) (Tess). |

### `check_build_overhead.py`

```
python3 check_build_overhead.py <transcript.jsonl>
```

- `<transcript.jsonl>`: positional, path to a Claude Code session transcript
  (the same `.jsonl` shape `~/.claude/projects/<hash>/<session-id>.jsonl`
  already uses — one JSON object per line, each a transcript event with a
  `type` field; `"assistant"` events carry a `message.content[]` array whose
  entries may be `{"type": "tool_use", "name": ..., "input": {...}}`).
- Behavior: stream the file line by line (never load it whole — these files
  run tens of MB). For each `tool_use` content block, classify:
  - `name == "TaskCreate"` → count the **assistant turn** it appears in
    (dedupe by the enclosing transcript line's turn, not by call — a batched
    hydration turn issuing ten `TaskCreate` calls in one message counts as
    ONE `TaskCreate` turn, which is exactly the metric the batched-hydration
    feature (already shipped) is judged against).
  - `name == "Bash"` and `input.command` starts with `python3` and contains
    `statectl.py` → increment the `statectl` call counter.
  - `name == "Write"` and `input.file_path` matches `*/dev/local/tmp/*prompt*`
    or `*/dev/local/tmp/dispatch-*` → increment the prompt-authoring `Write`
    counter (this pattern is what a pre-`render_prompt.py` session's inline
    prompt assembly looks like; post-migration sessions should report near
    zero here).
  - Track `TaskUpdate` calls with `status: "completed"` to derive the
    completed-task count, for the `statectl calls per completed task` ratio.
- Output (stdout, plain text, one line per metric — no JSON, this is a
  human-read report, not a machine-consumed one):
  ```
  TaskCreate turns: <n>
  statectl calls: <n>
  statectl calls per completed task: <float, 2 decimal places>
  prompt-authoring Write calls: <n>
  completed tasks: <n>
  ```
- Exit codes: `0` success (report printed, regardless of the numbers found —
  this is a report tool, not a pass/fail gate). `1` transcript file does not
  exist or is not readable. `2` file exists but contains zero parseable
  JSON lines (empty or wrong format entirely — distinguishes "nothing to
  report" from "wrong input").

### `state.qwen_preflight`

Mirrors `state.codex_probe`'s existing shape and batch-scope idiom exactly
(`state-schema.md` line 183), minus the `backend`/`model`/`note` fields that
don't apply to a single local backend:

```json
"qwen_preflight": {
  "batch_id": "<state.batch.id, or \"no-batch\">",
  "verdict": "healthy" | "pi_missing" | "endpoint_unreachable" | "model_id_missing" | "completion_failed",
  "detail": "<the failing check's own detail string, or null on healthy>",
  "checked_at": "<ISO 8601>"
}
```

`verdict` reuses the four existing `preflight_outcome` vocabulary strings
directly — no separate `"unhealthy"` wrapper — so the routing table's
existing `verdict == "healthy" ? proceed : fallback` branch and the attempt
log's `preflight_outcome` field read the same string with no translation.

## Data flow

**Ivan dispatch (step 3), per task:**

1. Orchestrator has already read the failing test files (step 2.95) and the
   architecture context (step 2.5) into its own context — this does not
   change.
2. Render: one Bash call — every interpolated path is `shlex.quote()`-d by
   the orchestrator before it lands inside a `--set-cmd` value, since that
   value crosses into a nested shell (`subprocess.run(..., shell=True)`
   inside `render_prompt.py`):
   ```bash
   python3 ~/.claude/skills/work/scripts/render_prompt.py ~/.claude/agents/ivan.md \
     --out dev/local/tmp/dispatch-ivan-<task-id>.txt \
     --set-cmd FAILING_TESTS="cat $(printf '%q ' <test_file_1> [test_file_2 ...])" \
     --set-file ARCHITECTURE_CONTEXT=<a single existing file, e.g. AGENTS.md, when one file covers it> \
     --set FILE_PATHS="<newline-separated list from the task's Contract section>" \
     --set RETRY_INSTRUCTION=""
   ```
   (`printf '%q '` is bash's own shell-quoting builtin — the orchestrator
   composes this command as a Bash tool call already running under bash, so
   it is the natural quoting mechanism at that call site; a Python-side
   caller would use `shlex.quote()` per path instead. Either way, the rule
   is: quote before interpolating, never concatenate raw paths.) When
   architecture context spans more than one file, use the same
   `--set-cmd ARCHITECTURE_CONTEXT="cat $(printf '%q ' <file_1> <file_2>)"`
   shape. `RETRY_INSTRUCTION` is the literal empty string on this, the
   initial dispatch. The stdout integer from this call **is** the Subagent
   Dispatch Budget measurement — no separate `wc -c`.
3. If the printed size exceeds 50 000, trim per the existing one-pass rule in
   `references/subagent-dispatch.md`, then re-render (still one call).
4. Dispatch the Agent tool with the file at `dev/local/tmp/dispatch-ivan-<task-id>.txt`
   as the prompt source, watchdog per the existing Subagent Watchdog section
   — unchanged.

**Steps 5.5 and 7 DO need a small prose edit each — verified, not assumed.**
Both currently carry their own inline "re-include the fixed block" text:
step 5.5 (`work/SKILL.md:455`) — *"Retry prompts... must re-include the
code-quality rules block from `references/code-quality-principles.md`, plus
an explicit SURGICAL instruction: 'Fix only what the failing test output
points to...'"* — and step 7 (`work/SKILL.md:711`) — *"Include the
code-quality rules block from `references/code-quality-principles.md` and
add: 'Fix only the regression identified below...'"*. Both become dead
instructions once `ivan.md` bakes the code-quality block in permanently (a
render call can no longer omit it), so both edit to: drop the
"re-include the code-quality rules block" sentence entirely, and route the
retry-specific line through the new `{RETRY_INSTRUCTION}` placeholder
instead of prose the model re-types:
- Step 5.5's retry: `--set RETRY_INSTRUCTION="Fix only what the failing
  test output points to. Do not refactor passing code, adjust unrelated
  files, or change style."` (verbatim, the exact text `work/SKILL.md:455`
  already specifies today), plus `--set-cmd FAILING_TESTS="cat $(printf
  '%q ' <test files>)"` updated with the failure output appended (a small
  scratch file the orchestrator writes once per retry, `--set-file
  FAILING_TESTS=dev/local/tmp/ivan-retry-tests-<task-id>-<n>.md`, combining
  the original failing tests plus the new failure output — this is real
  per-retry content assembly, not eliminated by templating, same as the
  PRD's own framing that templating removes *fixed*-block authoring, not
  task-varying content gathering).
- Step 7's regression fix: `--set RETRY_INSTRUCTION="Fix only the
  regression identified below. Do not touch unrelated files or refactor
  adjacent code."` (verbatim, `work/SKILL.md:711`'s exact text), with
  `FAILING_TESTS` filled from the step-7 failure output the same way.

This is a smaller edit than steps 2.7/3/5.7's full inline-assembly removal
(one sentence deleted, one flag added, per site) but it is a real edit —
the design's earlier draft claimed zero prose change here and that claim
did not survive checking the actual file content, corrected here.

**Tess dispatch (step 2.7):** identical shape, against `tess-prompt.md`
instead of `ivan.md`, with placeholders `{TASK_SUBJECT}`,
`{TASK_DESCRIPTION}`, `{TASK_ACCEPTANCE_CRITERIA}`, `{SAMPLE_TEST_FILE}`,
`{PUBLIC_INTERFACES}`, `{TEST_FRAMEWORK}` (first three reuse Pat's existing
names verbatim for consistency — same task-identity data, same names).

**Pat dispatch (step 5.7):** replace the inline "strip its frontmatter and
substitute..." paragraph with one `render_prompt.py ~/.claude/agents/pat.md
--out dev/local/tmp/review-task-<id>-prompt.md --set TASK_SUBJECT=... --set
TASK_DESCRIPTION=... --set TASK_ACCEPTANCE_CRITERIA=... --set-cmd
DIFF="git diff BASE_SHA..HEAD_SHA" --set-file
SIMPLIFICATION_MANDATE=references/simplification-mandate.md` call. Pat's
persona and placeholder table are unchanged — only the assembly mechanism
moves from "the model reads pat.md, mentally substitutes, and writes the
result" to "the script does it".

**Qwen preflight (step 3 routing, row 5):**

1. Before consulting row 5 (the four-check probe), compute the effective
   batch id and compare against `state.qwen_preflight.batch_id` — identical
   compare/reuse wording to `codex_probe`.
2. Mismatch or absent → run the existing four-check probe
   (`qwen-run.sh --preflight --approved-only`) once, write the verdict to
   `state.qwen_preflight` via `statectl set qwen_preflight <json>`, then
   proceed using that verdict.
3. Match → reuse the cached verdict, skip the probe entirely.
4. **Re-probe trigger — scoped to backend-health signals, not task-outcome
   signals.** A qwen-routed task's step-5.5 gate failing on its own is NOT a
   re-probe trigger: qwen is the weakest routing tier, and ordinary
   task-difficulty failures on a perfectly healthy backend are expected and
   already handled by the one-shot-to-Sonnet escalation
   (`qwen-integration.md` § One-shot attempt budget) — treating every such
   failure as a health signal would degrade the cache toward "probe before
   every task," reintroducing the exact overhead this feature removes. Only
   two signals invalidate the cache: (a) the Subagent Watchdog judges the
   qwen dispatch itself hung/lost (an infra symptom, not a test-quality
   one), or (b) the qwen helper script's own exit reports an infra-shaped
   failure at dispatch time — the same `"pi_missing"` /
   `"endpoint_unreachable"` / `"model_id_missing"` / `"completion_failed"`
   vocabulary the four-check probe already uses, surfaced when
   `qwen-run.sh` (not the preflight probe) fails at the real dispatch despite
   a cached `"healthy"` verdict (the backend died mid-batch, after the cache
   was written). On either trigger, run `statectl del qwen_preflight`
   immediately — this makes the next qwen-eligible task's batch-scope check
   see "absent" and re-probe, reusing the existing mismatch-or-absent path
   with no new conditional branch.
5. The per-task memory-pressure gate (routing row 4) is untouched — it stays
   a per-task host-memory check, run independently of this cache.
6. **Concurrency assumption, stated explicitly:** `/work`'s task loop is
   serial — one task claimed, dispatched, and completed before the next is
   claimed (`SKILL.md`'s own "CRITICAL: One Task at a Time" invariant, which
   `render_prompt.py`'s per-task-id scratch filenames throughout this design
   already assume). The delete-then-reprobe sequence above is therefore
   never racing a sibling qwen dispatch within one `/work` session. It is
   not proven safe across two *concurrent* `/work` sessions on the same
   batch (autopilot does not run those today — "one loop per repo" in
   `run-autopilot/SKILL.md` — so this is a documented assumption, not a
   gap this PRD needs to close).

**Red check (step 2.95):**

1. Before running the existing narrowest-scope pytest command, identify the
   **target module** — not every import in the test file, only the one
   under test — using the task's own `Contract` section (already present
   on every plan-tasks task: the exact file path(s) the task implements,
   per `plan-tasks`' own contract convention). The target module is the
   test file's import whose resolved filesystem path matches one of those
   Contract paths. This sidesteps import-parsing ambiguity entirely: the
   task plan already names the file being built, so the check is "does the
   Contract's own target path exist on disk yet," not "guess which import
   line is the interesting one" — `pytest`, stdlib, and fixture imports
   never appear in a task's Contract and are never candidates.
2. If that Contract-named path does not exist on disk: write
   `red_check = "n/a:new_module"` to the attempt entry, skip the pytest
   invocation for this step entirely, and proceed straight to step 3 (still
   "expected red" semantically — a module that doesn't exist cannot pass).
3. Otherwise (the Contract path already exists — this is an edit to an
   existing module, not a new one): run the red check exactly as today,
   unchanged.
4. **Edge case — a task's Contract names multiple files, some new, some
   existing** (e.g. a new module plus an edit to an existing caller): the
   check applies per Contract path the test file imports; if ANY named
   target is missing, treat it as the new-module case (skip pytest) —
   partial existence still guarantees an `ImportError` on the missing half,
   so the check gains nothing by running.

## Reuse inventory

- **`agent-registry.md`'s placeholder/frontmatter convention** — followed
  exactly for `ivan.md`; no new convention introduced. Searches: `rg -n
  "PLACEHOLDER" review-work-completion/references/agent-registry.md`, read
  in full.
- **`agents/pat.md`** — the concrete frontmatter+body shape `ivan.md`
  mirrors. Read in full.
- **`state.codex_probe` / `codex-implementor.md` § Codex batch health
  probe** — the exact batch-scope compare/reuse idiom `qwen_preflight`
  copies verbatim (down to the `(state.batch.id // "no-batch")` fallback
  expression). Searches: `rg -rn codex_probe skills/` (see catchup note —
  the field is `codex_probe`, confirmed by direct read of
  `state-schema.md:183` and `codex-implementor.md:9-28`).
- **`work/scripts/check_memory_pressure.py`** — the stdlib argparse-CLI
  shape (`parse_args`, single `main(argv)`, integer exit codes, no
  dependencies) that `render_prompt.py` and `check_build_overhead.py`
  follow. Read in full.
- **`qwen-integration.md` § Preflight** — the existing four-check probe and
  its `preflight_outcome` vocabulary, reused unchanged as the verdict
  strings for `state.qwen_preflight.verdict`. Nothing here is rewritten,
  only cached.
- **`test-author-prompt.md`** — searched for an existing registry-shaped
  Tess template before deciding to extract one; none exists (it uses dotted
  `{task.subject}` placeholders and carries no frontmatter), confirming the
  PRD's own claim needs the qualification recorded in Risks.
- Searches tried with no hit: `rg -n "def render_prompt\|render.prompt\|substitute.*placeholder" skills/` (nothing — no existing prompt-templating script anywhere in the repo, confirming `render_prompt.py` is genuinely new); `rg -rn "qwen_preflight" skills/` (nothing — confirms the field does not yet exist).

## Alternatives considered

1. **One combined `{TASK_CONTEXT}` placeholder for Ivan** instead of three
   separate ones (`FAILING_TESTS`/`ARCHITECTURE_CONTEXT`/`FILE_PATHS`). This
   is the smallest-diff version — one `--set-file` call instead of three
   flags. Rejected: the PRD's own "Ivan receives" list names these as three
   conceptually distinct inputs, and keeping them separate means a bad
   dispatch is debuggable by section (which of the three was wrong) rather
   than requiring the orchestrator to re-derive which part of one blob was
   off. The extra flags cost nothing at render time — `render_prompt.py`'s
   signature already supports repeatable `--set*` flags for exactly this.
2. **Register Tess as a full native persona** (`agents/tess.md`, in the
   roster, dispatched by `subagent_type: tess`) instead of the lighter
   `tess-prompt.md` reference-file extraction this design uses. This is the
   larger option: it would need a `tools:` pin, a registry-table row, and
   (per `agent-registry.md`'s own write-then-dispatch-window note) careful
   sequencing so the new type is announced before first use. Not chosen —
   nothing in the PRD's Structural Decomposition lists a new `agents/tess.md`
   file, and Tess today is dispatched as a plain Agent-tool call with an
   assembled prompt, not by name — turning her into a registry lane is a
   bigger, independently-reviewable change than "stop authoring her prompt
   by hand," which is all this PRD asks for.
3. **A generic `dev/local/tmp/` scratch-file Write step before every render
   call**, always writing `FAILING_TESTS`/`ARCHITECTURE_CONTEXT` to files
   even when their source is a single already-existing file. Rejected in
   favor of `--set-file` (existing file) / `--set-cmd "cat ..."`
   (concatenation) so the orchestrator never re-writes content that already
   exists on disk — this is the actual mechanism that removes the measured
   43s/43s/57s prompt-authoring cost, not merely templating the fixed
   sections.

## Risks & edge cases

- **PRD/reality drift on Tess.** The PRD states "Tess has had
  `work/references/test-author-prompt.md` throughout" as evidence she
  already follows the registry convention. She does not — that file uses
  dotted `{task.subject}`-style placeholders with no frontmatter, and lives
  outside `agents/`. This design treats that as the PRD's own
  premise-drift (explicitly anticipated in its Risks section: "re-read the
  registry conventions before building - `agent-registry.md` is the
  authority... not this PRD") and extracts a minimal, registry-shaped
  `tess-prompt.md` rather than leaving step 2.7 un-migrated — otherwise the
  PRD's own Success Metric ("Zero inline prompt bodies for the test-writer,
  implementor and per-task reviewer dispatches") is unreachable for one of
  its three named surfaces.
- **Step 2.8's retry prompt stays inline.** The quality-gate retry variant
  (`test-author-prompt.md` § Retry Prompt) is smaller and not named in the
  PRD's Phase 1 task list (which names step "2.7", not "2.8"). Left
  unconverted — flagged here as a natural next-PRD candidate rather than
  silently swept in.
- **Steps 5.5 and 7 need a small edit each, verified against the actual file
  (`work/SKILL.md:455` and `:711`), not the zero-edit claim an earlier draft
  of this design made without checking.** See Data flow above for the exact
  sentence removed and the `{RETRY_INSTRUCTION}` flag added at each site.
  This means the PRD's literal "steps 2.7, 3 and 5.7" task-list wording
  under-counts the edit surface by two steps; the Success Metric ("Zero
  inline prompt bodies for the test-writer, implementor and per-task
  reviewer dispatches") is the authoritative scope, and it is unreachable
  with 5.5/7 left as-is.
- **`--set-cmd`'s `shell=True`** is a real command-injection surface if ever
  fed untrusted content, independent of the quoting fix above (which
  prevents a *correctness* bug — arguments splitting on spaces — not an
  injection). It is only ever called by the orchestrating skill with
  strings it composes itself (file paths, git refs) — same trust model as
  every other Bash-tool call the skill already makes. Documented in the
  Interfaces section rather than defended against, per the "validate at
  real system boundaries only" rule — there is no boundary here, the caller
  and the callee are the same trust domain.
- **Likely next changes after this PRD:** (1) PRD 00089's schema-validated
  write boundary will eventually absorb `task-start`/`task-done` from
  `statectl.py` — already noted as a scope boundary in the PRD itself, this
  design adds nothing to that surface. (2) A future PRD may want the qwen
  batch-scope idiom and the codex batch-scope idiom collapsed into one
  shared helper now that three near-identical copies exist
  (`qwen_breaker`, `codex_probe`, `qwen_preflight`) — this design
  deliberately keeps the third copy literal rather than introducing a
  shared abstraction for three call sites, per the ladder's own "no
  abstraction for a single caller" instinct extended to "three, so far
  none identical enough to be sure the fourth would fit."
- **A `red_check = "n/a:new_module"` false-negative**: if a task's Contract
  section is stale or wrong (names a path that doesn't match what the test
  file actually imports), the skip could fire on a module that in fact
  exists under a different path. Mitigation: this is bounded, not
  unbounded — a wrong Contract path is already a planning-time defect
  `/plan-tasks` is responsible for getting right (every task's Contract is
  copied byte-for-byte from the design doc's `## Interfaces & contracts`,
  per that skill's own contract), and the false-negative's blast radius is
  "one wasted pytest skip," not silent data loss: step 3's dispatch still
  runs, and if the module truly exists, Ivan's own work either passes step
  5.5's real gate or fails it — nothing downstream trusts `red_check` as a
  correctness signal, only as a wall-clock optimization record.

## Test strategy outline

- `test_render_prompt.py`: one test per source kind (`--set`, `--set-file`,
  `--set-cmd`), an unfilled-placeholder case (asserts exit 1 and the name in
  stderr), a substituted value containing a literal `{NAME}`-shaped sequence
  (asserts it is not re-substituted), a persona with no frontmatter (body
  used as-is), a persona whose frontmatter never closes (asserts exit 3), a
  missing persona file (asserts exit 2), a missing `--set-file` path and a
  non-zero `--set-cmd` (both assert exit 4, distinct stderr messages), a
  missing `--out` parent directory (asserts exit 5), and a byte-size stdout
  assertion against a known-length rendered file.
- `test_check_build_overhead.py`: runs against the engram baseline
  transcript named in the PRD (`4bddd2d6-...jsonl`) and asserts the exact
  reported `TaskCreate` turn count (10) and per-task `statectl` call count
  (>= 7) the PRD's own Phase 2 acceptance criterion names, plus a missing-file
  case (exit 1) and an empty/unparseable-file case (exit 2).
- Ivan/Tess/Pat rendering: a fixture persona rendered with representative
  values, diffed against a captured snapshot of today's inline-assembled
  prompt (fixed sections only — task-varying content differs by
  construction) — proves Phase 0's "reproduces the fixed sections" claim
  mechanically rather than by inspection.
- `qwen_preflight` batch-scope: unit test mirroring
  `test_work_routing.py`'s existing `codex_probe`-batch-scope tests
  (mismatch → re-probe, match → reuse, absent → re-probe), plus two tests
  for the re-probe triggers (Watchdog-hung/lost → `qwen_preflight` deleted;
  dispatch-time infra failure → deleted) and one negative test (an ordinary
  step-5.5 gate failure on a healthy backend does NOT delete the cache — the
  finding this design was corrected for).
- Red-check module resolution: task Contract names one new-module path
  (skip pytest, `n/a:new_module`), one existing-module path (run pytest
  unchanged), and a mixed Contract (one new + one existing path) — asserts
  the skip fires because at least one target is missing.

## Review log

dispatch 1 (claude): cardinal-sin 0, blocker 7, non-blocker 0, question 1

Dispatch 1 findings (all 7 blockers fixed above): missing
`check_build_overhead.py` contract → added; `render_prompt.py` error
handling incomplete and its own worked substitution example would raise an
uncaught `KeyError` → validate-before-substitute added plus exit codes 4/5;
`agent-registry.md` scope missed 3 Tess-only placeholders → added (plus the
new `{RETRY_INSTRUCTION}` row); `qwen_preflight` re-probe trigger conflated
ordinary task-difficulty failure with backend health → narrowed to
Watchdog-hung/lost and dispatch-time infra failure only; "steps 5.5/7 need
no prose change" was an uncited claim → verified against the actual file
(`work/SKILL.md:455`, `:711`) and found false, corrected with the specific
edit each site needs; `--set-cmd` example concatenated paths with no
quoting → `printf '%q '`/`shlex.quote()` requirement added; red-check
import-resolution heuristic was underspecified for the realistic
multi-import case → replaced with a Contract-path-based resolution that
sidesteps import parsing entirely. Question (concurrency model for
`qwen_preflight` deletion) was answered inline in Data flow (item 6) rather
than left as an open question, since the answer was a one-sentence
documented assumption already implied by `/work`'s existing serial-task
invariant.
