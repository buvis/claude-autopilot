# Discovery: Cut review and test-loop overhead

## Classification
Depth: standard | Date: 2026-09-05

Source: `agent-skills/dev/local/notes/autopilot-overhead-proposals-2026-09-05.md`, measured on PRD 00015
(batch 202609050909 in agent-skills): 95 min build and ~20 min per review cycle for ~50 production lines.
Yields three PRDs (00178 Bob's first run and retry; 00179 the Devon cap; 00180 codex prompt on stdin, split out by
create-prd's size rule) plus one task appended to backlog PRD 00175 (Carl).

## Problem

Two pipeline steps burn time without adding signal. In the review phase, Bob (codex) fails his first run
whenever codex reads his persona's "CANNOT execute code" line as "no shell", so he cannot open the context
and diff files the same persona tells him to read; the driver then hand-builds an inlined retry that no spec
describes, costing ~3 min plus two opus driver rounds per cycle. Carl (Gemini) is dead on both backends yet
is dispatched and retried every cycle because preflight only checks that a binary resolves. In the work
phase, the Tess/Devon adversarial loop runs up to two strengthen rounds after the first Devon pass; task 2
of PRD 00015 spent 20 min on Tess x3 / Devon x3 before the implementor ran, and still shipped a test gap
(a present, non-list `entries`) that codex found in one pass.

## Requirements

### Must have
- `agents/bob.md` permits read-only shell commands for reading files (cat, sed, rg) while still forbidding
  tests, linters, package managers and any write; the "Read {CONTEXT_FILE} ... {DIFF_FILE}" header stays.
- `references/retry-policy.md` names the CLI-reviewer retry amendment for Bob: the context and diff inlined
  as prompt text under the preamble recovered from the 2026-09-05 run (quoted in Codebase Context; it also
  carries the already-run test results), so no cycle rebuilds it by hand.
- `codex-run.sh` passes the prompt on stdin (`codex exec -` reads it; PRD 00171 made the same move for the
  sonnet helper), removing the argv cap; the `--resume-thread` path takes the same form.
- Bob is dispatched once per cycle unless `retry-policy.md`'s existing triggers fire (non-zero
  `codex-run.sh` exit, malformed issue-line format, incomplete per-rule verdicts) or the output is a
  lack-of-input refusal: every R line is `fail` and the only finding lines are ⚪ `Cannot statically verify`
  lines naming the source or diff. A first run of any other shape is final.
- `review-work-completion` records every CLI reviewer dispatch and retry as a dispatch-ledger row
  (`record_dispatch.py --kind bob` / `--kind carl`; the kind is free-form), so the Success Criteria and the
  batch report can count them.
- `skills/work/references/adversarial-test-prompt.md` outcome table caps the loop at one strengthen round:
  Devon, Tess strengthens, Devon re-checks, then "flag weakness, proceed". `skills/work/SKILL.md` step 2.8's
  total Tess budget shrinks to 4 dispatches (1 initial, 2 quality-gate retries, 1 strengthen).
- Per task, the dispatch ledger holds at most 2 `devon` rows and at most 4 `tess` rows, pinned by a prose
  contract test on the numbers in both files.
- PRD 00175 gains one task: once a cycle records Carl as permanently unavailable (its new exit code), every
  later cycle and PRD in the same batch skips his dispatch and retry, and the review file says so in one line.

### Nice to have
- None (the stdin move was promoted to Must have at review).

### Out of scope
- Removing or thinning any review lens; Alice, Blake and Bob run every cycle, Carl whenever he can.
- The driver's "waiting on Bob" polling turns and the Watcher subagent (not selected).
- PRD-text hygiene in create-prd (file names and file counts in acceptance criteria; lives in agent-skills).
- Per-task session handoffs from subagent-output context pressure.
- The usage-limit wait that idled batch 202609050909 from 11:43 to 13:34; infrastructure, not pipeline.

## Constraints
- Every review lens still runs every cycle; this cuts dead dispatches and redundant rounds, never a lens
  (same boundary as PRD 00157's discovery).
- Policy stays in skill prose pinned by contract tests under `skills/<skill>/scripts/test_*.py` and
  `dev/bin/release-checks`; no new runtime dependency.
- Acceptance is deterministic dispatch counts from the ledger, never wall-clock or cost.

## Codebase Context
- **Relevant code**:
  - `agents/bob.md:7` renders `Read {CONTEXT_FILE} for review context, and {DIFF_FILE} for the full diff.`;
    `agents/bob.md:26-30` says `You run in a restricted sandbox. You CANNOT execute code, tests, linters, or
    package managers. Perform STATIC analysis only.` Codex can only read files through shell, so the two
    lines conflict; the 202609040601 batch's Bob read them anyway, this run's refused
    (`bob-output-00015-c1.txt`: every R rule failed "for lack of input").
  - `skills/use-codex/scripts/codex-run.sh:142,244,304` passes the prompt as one argv string
    (`"$PROMPT"`); `codex exec --help` confirms `-` reads instructions from stdin. PRD 00171 moved the
    sonnet helper to stdin for the same reason.
  - The 2026-09-05 retry prompt (`/tmp/bob-prompt-00015-c1-retry.md`, 39 KB, assembled from
    `/tmp/bob-retry-{head,mid,tail}.md`; not retained under `dev/local/tmp/`) wrapped the persona body in
    this improvised preamble. Head, before the inlined context: `IMPORTANT: You run in a restricted sandbox
    and CANNOT read files or run commands. Everything you need is INLINED BELOW as text. Do not attempt to
    read any path, and do not report an inability to read files — the review context and the complete diff
    are both reproduced verbatim in this prompt.` then `Context pack: (no pack available this cycle)`,
    `Repo root (for path interpretation only): <abs path>`, and `Test results for the reviewed revision
    (already run, do not ask for them):` with the pytest and rg results pasted in, then
    `# REVIEW CONTEXT (inlined verbatim)`. Mid: `# FULL DIFF (inlined verbatim) — range <base>..<head>,
    path-scoped to this PRD` around a fenced diff. Tail, added to the persona body: `Review the completed
    work against PRD requirements using ONLY the inlined text above.`, `Do NOT emit "Cannot statically
    verify" lines about reading files or test results — both are supplied above.`, and on the verdict line
    `Judge each against the inlined diff and the supplied test results; only mark a rule fail when the
    evidence above actually shows a failure.`
  - `skills/review-work-completion/references/retry-policy.md:19`: CLI reviewers retry once by re-dispatching
    a fresh background Bash with "an amended prompt file". Nothing names what the amendment is.
  - `skills/review-work-completion/SKILL.md:72`: Carl is active when `gemini-run.sh` is executable AND
    `copilot` or `gemini` resolves on PATH; no auth or model probe. Backlog PRD 00175 repoints the pin,
    reserves a distinct exit code for "unavailable", and says step 1/5 records permanent unavailability,
    but does not say later cycles skip the dispatch.
  - `skills/work/references/adversarial-test-prompt.md:15-19`: Devon outcome table, "Max 2 Tess/Devon
    rounds", then "flag weakness, proceed". `skills/work/SKILL.md:238-242`: quality gate max 2 Tess retries,
    total Tess budget 5 dispatches. Devon runs only on `opus`/`fable` tasks (`SKILL.md:246-252`).
    Observed on task 2: tess 09:44, devon 09:47, tess 09:51, devon 09:55, tess 09:59, devon 10:03.
  - Autopilot 0.5.0 (released 2026-09-05) adds `detect_tautological_tests.py` to the step-2.8 gate, a
    mechanical check that covers part of what a second Devon round hunts.
  - Dispatch telemetry (`skills/work/scripts/record_dispatch.py`, `dev/local/autopilot/dispatch-metrics.jsonl`)
    records one row per Tess/Devon/Ivan/Pat dispatch with `kind` and `task`; PRD 00157's discovery chose
    dispatch counts as the acceptance contract. `review-work-completion` writes no rows today (no
    `record_dispatch` call under that skill), so Bob and Carl dispatches are countable only from review-file prose.
  - `skills/review-work-completion/scripts/test_agent_registry.py` pins persona text; it changes with bob.md.
- **Conventions**: workflow policy lives in skill prose pinned by prose contract tests; personas live in
  `agents/*.md`; CHANGELOG entries per `**skill**` scope.
- **Integration points**: `agents/bob.md`, `skills/review-work-completion/references/retry-policy.md` and
  `references/agent-invocation.md`, `skills/work/references/adversarial-test-prompt.md`,
  `skills/work/SKILL.md` steps 2.8 and 2.85, PRD 00175 (Carl), `test_agent_registry.py`.

## Success Criteria
- A review cycle with codex available records one `bob` dispatch and a first-run output containing R-rule
  verdicts (not "Cannot statically verify: source").
- `retry-policy.md` states the inlined-content retry and its preamble; a contract test greps both.
- A task at `opus` tier records at most 2 `devon` rows and at most 4 `tess` rows in the dispatch ledger; a
  contract test pins the numbers in `adversarial-test-prompt.md` and `SKILL.md` step 2.8.
- After 00175: a batch whose first cycle marks Carl unavailable records zero `carl` dispatches in later
  cycles, and each later review file carries the one-line skip note.
- `bash dev/bin/release-checks` green.

## Risks
- **Codex still refuses to read despite the wording**: the specified inlined retry covers it; count Bob
  retries per batch in the report and revisit if they stay above zero.
- **Weaker tests reach the implementor after one round**: Pat's per-task review, the 0.5.0 tautological
  check, and the cycle review remain; PRD 00015's real gap was found there, not by Devon's round two.
- **Prose caps drift silently**: pin every number with a contract test, as 00157's PRDs did.

## Open Questions
- None that block create-prd.

## Discovery Log

### Q1: Bob's persona tells codex to read two files, then forbids executing anything, so codex sometimes refuses to read them. Which fix?
**Answer**: Allow read-only shell in the persona (a one-line wording change; codex keeps reading files under
its read-only sandbox). Keep the inlined retry as the specified fallback. Rejected: inline-first (argv
prompt cap at the time; the stdin Must have removes the cap, the persona fix stays first) and a dual path.

### Q2: PRD 00175 repoints the Gemini pin and reserves an "unavailable" exit code, but later cycles still dispatch and retry Carl. Where should the skip live?
**Answer**: Add one task to PRD 00175: once a cycle records Carl as permanently unavailable, later cycles
and PRDs in the same batch skip his dispatch and retry outright. Rejected: a separate sequenced PRD, and
dropping it (the waste would return the next time any backend dies).

### Q3: Where should the Devon loop cap sit?
**Answer**: One round: Devon, Tess strengthens, Devon re-checks, then flag and proceed (at most 2 Devon and
1 strengthen-side Tess dispatch; Tess total 4). Rejected: strengthen without re-check (nothing proves the exploit
closed) and keeping two rounds while skipping Devon on rework tasks (task 2 was a first-pass task).

### Inferred: What is out of scope?
**Answer**: From the four proposals offered, the user selected only these two; driver polling and PRD-text
hygiene stay out, as does any lens removal.

### Inferred: How is success measured?
**Answer**: Deterministic dispatch counts from the ledger and prose contract tests, the shape PRD 00157's
discovery set; wall-clock and cost are reported, never gated.

### Inferred: When does this land?
**Answer**: Next claude-autopilot batch, alongside 00175, which the Carl task extends.
