---
consensus_engine: shadow
design: skip
eligibility: "test $(grep -l 'no verdict divergence' $(grep -l '^consensus_run_id:' dev/local/reviews/*.md 2>/dev/null | grep -v /00110-) /dev/null 2>/dev/null | wc -l) -ge 3"
---

# Flip Consensus Engine Default to Workflow

> Renumbered 00095 → 00110 on 2026-08-01 (backlog tail resequence; mapping in memory `project_backlog_renumber_2026_08`).
>
> **Unpark when (added 2026-08-23):** >= 3 consecutive clean shadow cycles exist, >= 1
> showing raw > unique. Evidence is accruing: `consensus_engine: shadow` was stamped on
> 00134/00135/00136 on 2026-08-23, so their drains bank cycles. Check PROMPTLY after that
> batch: shadow renders live in `dev/local/tmp/` (7-day GC, purged on drain) and per-PRD
> review files die with their PRDs - copy each batch's stats_line into
> `dev/local/reviews/00110-flip-evidence.md` (this PRD's own satellite, durable while it
> lives), then move this file to `backlog/`. Once PRD 00137's premise gate ships, move to
> `backlog/` immediately regardless: the stamped `premise:` line (inert until then,
> fixture-verified by 00137 Phase 2) self-serves this check at every drain.
>
> **Premise rewritten 2026-08-25 (backlog review, operator decision).** The 2026-08-23
> line (`rg -l consensus-shadow dev/local/reviews dev/local/tmp | wc -l >= 3`) exited 0
> already: it counted this PRD's own evidence satellite, a GC'd `dev/local/tmp` scratch
> file, and two 00136 review files, i.e. any mention of the word, not clean cycles. The
> new line counts review files whose frontmatter carries `consensus_run_id` (a shadow
> actually ran) and whose Alice section records `no verdict divergence`, excluding
> `00110-*` satellites. It is a DRAFT: 00137 Phase 2 pins the exact command with
> fail-first fixtures in both directions and may tighten it (consecutiveness,
> raw > unique). Today it matches 2 files (00136 cycles 1 and 2), so it exits 1.
>
> **Cost evidence added 2026-08-26** (from the hand-driven 00136 cycle 1, recorded in
> `dev/local/reviews/00110-flip-evidence.md` § Addendum): the shadow ran 6 agents,
> 771K subagent tokens, 5.5 min, against legacy Alice's 118K; of its 20 advisories 4
> duplicated gating lenses, 3 were new, 2 were adopted. A ~6.5x token multiplier for
> about one adopted LOW/MEDIUM finding per cycle. When this PRD un-parks, the flip
> decision has a third option besides `legacy`/`workflow`: arm the workflow only on
> cycle 1 of PRDs whose review diff exceeds a size threshold (500 lines proposed,
> where five dimension lanes have room to disagree), never on incremental cycles.
>
> **Command pinned 2026-08-26 (PRD 00137 Phase 2).** The draft piped `rg -l` into
> `xargs rg -l`, and an empty pipe left the second `rg` with no path argument, so it
> searched cwd and matched this very PRD's own body (which quotes the phrase). The
> pinned line uses two `grep -l` passes with `/dev/null` as a second operand, which
> keeps `grep` in multi-file mode and never matches, so an empty first pass counts 0
> instead of scanning the tree. Proven both directions by
> `cli/test_eligibility.py::Hold00110FixtureTests` (empty reviews dir -> exit 1; three
> synthetic stamped-and-converged reviews -> exit 0; 00110's own satellite and any
> unstamped or diverged review excluded). The string lives in that test as
> `HOLD_00110_COMMAND` because this file is gitignored; keep the two in step.
>
> **Re-keyed 2026-08-26 (backlog review of the plugin repo, operator decision):**
> `premise:` -> `eligibility:`, the frontmatter key PRD 00137 settled on (distinct from
> the task-level `Premise:` line, whose failure stalls; this key skips). The command is
> unchanged and still the draft 00137 Phase 2 pins. In this repo it matches 0 files (the
> 00136 reviews stayed in `~/.claude`) and still exits 1. This PRD's body still maps
> `~/.claude/` and names `create-prd` / `review-prd-backlog`, which are not part of the
> plugin - re-ground it before un-parking.

## Overview

### Problem Statement

The `review-fanout` workflow is wired as a tri-state behind Alice's consensus
leg (`consensus_engine: legacy | shadow | workflow`) but the default is still
`legacy` - the single-subagent path whose measured record is 13/14 PRDs
hitting rework cap 3 without converging (~$13/task). Shadow mode records
non-gating observations per cycle (stats_line + verdict divergence under
Alice's section of the review file; render in
`dev/local/tmp/<prd-base>-consensus-shadow-{cycle}.md`) but nothing evaluates
them, and the legacy + shadow branches carry permanent doc and dispatch
weight. Source: discovery 00092, must-have 1 (track A); supersedes the
remaining intent of PRD 00104 (ex-00057) (in `backlog/` as of 2026-08-01).

### Target Users

The autopilot review phase and every standalone `/review-work-completion`
run.

### Success Metrics

- Evidence of 3 consecutive clean shadow cycles audited and recorded before
  any flip (definition below); at least one cycle's stats shows dedup
  collapsing (raw > unique).
- Default engine is `workflow`; the legacy single-subagent Alice leg and the
  shadow branch are gone from the dispatch table.
- PRD 00104 (ex-00057) moved to `done/`.

## Functional Decomposition

### Capability: Flip Evidence Gate
Prove the workflow engine is safe to promote, or stop.

#### Feature: Clean-cycle audit
- **Description**: Premise-gated audit of banked shadow cycles.
- **Inputs**: Alice-section shadow observations in `dev/local/reviews/`
  review files (correlated by `consensus_run_id`), surviving shadow renders
  in `dev/local/tmp/`, `check_review_file.py`.
- **Outputs**: `dev/local/reviews/00110-flip-evidence.md` listing each
  audited cycle with verdicts, stats, and clean/dirty call.
- **Behavior**: A cycle is clean iff the engine completed end-to-end
  (stats_line recorded), zero findings-parse failures noted, the rendered
  shadow file passed `check_review_file.py --reviewers alice` (presence of
  the gated observation; re-run the gate on renders that still exist), and
  the shadow verdict matched or was stricter than legacy Alice's on the same
  diff (stricter = CHANGES_REQUESTED where legacy approved). Premise: ≥3
  consecutive clean cycles exist in the recorded evidence, and ≥1 audited
  cycle shows raw > unique. Execution-time re-check: if the evidence is
  missing, ambiguous, or shows any dirty cycle inside the last three, write
  the evidence file with the shortfall and stop - park and report, never
  flip.

### Capability: Default Flip and Legacy Retirement
Make the workflow the engine; delete the paths it replaces.

#### Feature: Default flip
- **Description**: `consensus_engine` defaults to `workflow` everywhere it is
  parsed or documented.
- **Inputs**: `run-autopilot/references/phase-build.md` (frontmatter table,
  fallback warning line, semantics), `run-autopilot/cli/schema.py` +
  `records.py`, `references/state-schema.md`,
  `review-work-completion/SKILL.md` step 1, `create-prd/SKILL.md` and
  `review-prd-backlog/SKILL.md` frontmatter docs,
  `scripts/golden/prd-frontmatter.md` + `test_golden_contracts.py`.
- **Outputs**: Updated parsers, docs, goldens, tests.
- **Behavior**: The flag stays parsed for back-compat; `workflow` is the
  default and the only dispatchable engine. `legacy` and `shadow` become
  invalid values: one logged warning, then `workflow` (the standard
  invalid-value fallback). Existing PRDs carrying `consensus_engine: shadow`
  (00108/00109 (ex-00093/00094), by then done) need no migration.

#### Feature: Legacy and shadow retirement
- **Description**: Remove the legacy Alice subagent dispatch and all shadow
  bookkeeping.
- **Inputs**: `review-work-completion/SKILL.md` (tri-state table, step 5
  legacy dispatch, step 8 shadow observation recording, shadow-render
  instructions), `references/agent-invocation.md`, `references/
  output-formats.md`, `references/review-coverage-format.md`, contract
  tests referencing legacy/shadow branches, `alice.md` parity tests bound to
  the legacy assembly (00109, ex-00094).
- **Outputs**: Workflow-only dispatch text; pruned references and tests.
- **Behavior**: The workflow IS Alice's leg unconditionally; her section in
  the review file comes from the engine's renderer with `{{TESTS_LINE}}`
  substitution as already specified for workflow mode. `alice.md` stays in
  the registry as the consensus-lead identity; its legacy-assembly parity
  test retires with the path it tested. `consensus_run_id` stamping in
  review-file frontmatter is unchanged. Premise for every deletion: the
  branch being removed still matches its recon'd shape (tri-state at step 1,
  shadow at steps 5/8); a moved or already-removed branch is skipped and
  reported.

#### Feature: 00104 (ex-00057) closure
- **Description**: The port-consensus-workflow PRD reaches done.
- **Inputs**: `00104-port-consensus-review-fanout-to-native-workflow-v1.md`,
  wherever it sits under `dev/local/prds/` at execution.
- **Outputs**: Same file under `done/`.
- **Behavior**: `mv` to `done/` keeping the prefix. Premise: 00104 (ex-00057) has not
  yet reached `done/` at execution; if it is already there (a human moved it
  or it drained on its own - it sits in `backlog/` as of 2026-08-01), skip
  and report.

## Structural Decomposition

### Repository Structure

```
~/.claude/
├── skills/review-work-completion/   # Maps to: Legacy and shadow retirement
│   ├── SKILL.md                     # step 1 table, steps 5/8 surgery
│   ├── references/                  # invocation, output-formats, coverage
│   └── scripts/                     # contract tests updated
├── skills/run-autopilot/            # Maps to: Default flip
│   ├── references/phase-build.md, references/state-schema.md
│   ├── cli/schema.py, cli/records.py, cli/test_*.py
│   └── scripts/golden/, scripts/test_golden_contracts.py
├── skills/create-prd/SKILL.md       # Maps to: Default flip (frontmatter doc)
├── skills/review-prd-backlog/SKILL.md
└── dev/local/                       # Maps to: Flip Evidence Gate, 00104 (ex-00057)
    ├── reviews/00110-flip-evidence.md
    └── prds/** → done/ (00104)
```

### Module: evidence-audit
- **Maps to capability**: Flip Evidence Gate
- **Responsibility**: Audit shadow observations, write the evidence file,
  enforce the premise.
- **Exports**: `dev/local/reviews/00110-flip-evidence.md`.

### Module: engine-default
- **Maps to capability**: Default Flip and Legacy Retirement
- **Responsibility**: Parser/docs/golden default change + invalid-value
  handling.
- **Exports**: Updated `schema.py`, `records.py`, docs, goldens.

### Module: dispatch-retirement
- **Maps to capability**: Default Flip and Legacy Retirement
- **Responsibility**: Remove legacy Alice + shadow branches and their tests;
  workflow-only step text.
- **Exports**: Updated `review-work-completion` SKILL + references + tests.

## Dependency Graph

### Foundation Layer (Phase 0)
No dependencies - built first.

- **evidence-audit**: Reads only recorded shadow evidence; gates everything
  downstream.

### Core Layer (Phase 1)
- **engine-default**: Depends on [evidence-audit].
- **dispatch-retirement**: Depends on [evidence-audit].

### Integration Layer (Phase 2)
- **Suite sweep + 00104 (ex-00057) closure**: Depends on [engine-default,
  dispatch-retirement].

## Implementation Phases

### Phase 0: Evidence gate
**Goal**: The flip is justified by recorded cycles, or the PRD stops.

**Tasks**:
- [ ] Audit shadow cycles and write
  `dev/local/reviews/00110-flip-evidence.md` (no deps) - Acceptance: file
  exists listing ≥3 consecutive clean cycles per the clean-cycle definition
  and ≥1 cycle with raw > unique; on shortfall the file records it and the
  PRD parks (premise failure, never force).

**Exit Criteria**: Evidence file written; premise holds or PRD parked.

### Phase 1: Flip and retire
**Goal**: Workflow-only engine, default flipped.

**Tasks**:
- [ ] Flip default + invalid-value handling in parsers, docs, goldens
  (depends on: Phase 0) - Acceptance: `uv run pytest
  skills/run-autopilot/cli/ skills/run-autopilot/scripts/` green; golden
  frontmatter fixture shows `workflow` default semantics.
- [ ] Remove legacy dispatch + shadow branches from review-work-completion
  and its references; update its contract tests (depends on: Phase 0) -
  Acceptance: `rg -i 'shadow' skills/review-work-completion` returns no
  dispatch-semantics matches; `uv run pytest
  skills/review-work-completion/scripts/` green.

**Exit Criteria**: Default flipped, legacy/shadow branches gone, suites green.

### Phase 2: Sweep and closure
**Goal**: Nothing dangling; 00104 (ex-00057) done.

**Tasks**:
- [ ] Repo-wide sweep for stale `legacy`/`shadow` engine references incl.
  create-prd + review-prd-backlog docs (depends on: Phase 1) - Acceptance:
  `rg 'consensus_engine'` across skills/ + workflows/ shows only
  workflow-default text; node + python suites green.
- [ ] Move 00104 (ex-00057) to done (depends on: Phase 1) - Acceptance: file exists in
  `done/`, absent from every other lifecycle dir (premise re-checked first).

**Exit Criteria**: Sweep clean, 00104 (ex-00057) closed.

## Test Strategy

### Critical Scenarios
- **Happy path**: PRD without the flag → engine resolves `workflow`; review
  file renders via the engine with substituted `Tests:` line and passes
  `check_review_file.py`.
- **Edge case**: PRD with `consensus_engine: legacy` → one warning,
  `workflow` used; nothing dispatches the retired path.
- **Error case**: Evidence shows a dirty cycle inside the last three →
  evidence file records the shortfall, PRD parks, no flip edits applied.

## Risks

- **Evidence perishes** (shadow renders live in `dev/local/tmp/`, 7-day GC;
  review files are PRD satellites): this PRD drains in the same batch as
  00108/00109 (ex-00093/00094), immediately after them; the audit also accepts the review
  files' recorded observations alone when renders are gone.
- **Workflow-only engine has no escape hatch**: accepted; the evidence gate
  is the proof bar, and `git revert` restores the tri-state wholesale.
- **Live work-tree HEAD moves mid-review** (known failure class): scope
  review diffs to this PRD's commits; re-verify the default at HEAD before
  declaring convergence.

## Premise status

- **2026-08-14: premise failed for the hand-run queue; parked by operator
  decision.** The evidence gate needs 3 clean shadow cycles, which only
  accrue from full autopilot review runs; the fast-track queue is hand-run
  and produced zero. Operator chose (fast-track v5 item 19): keep the gate
  as written, stay in `hold/`, and let the first real batch supply the
  cycles - the same batch already owed for 00094/00095's
  `cycles_to_converge` measurement doubles as the source. Rejected:
  redefining the gate to count interactive runs (weaker evidence than the
  autopilot conditions the flip must survive) and flipping on 00109's
  byte-parity goldens alone (prompt parity cannot show runtime differences).
  Un-park when `dev/local/reviews/` or the shadow ledger shows 3 post-batch
  shadow cycles.
- **2026-09-02: re-checked at the end of the 00159-00168 drain; still 0 cycles,
  still parked (operator decision).** `rg -l "^consensus_run_id:"
  dev/local/reviews` matches nothing: 00160 and 00161, the two PRDs autopilot
  drained on 2026-09-01/02, carried no `consensus_engine` and ran legacy. The
  host workflow file the shadow engine needs exists
  (`~/.claude/workflows/review-fanout.workflow.js`, 2026-08-03). Hand-run
  fast-track sessions dispatch Alice as a plain subagent and record no run id,
  so they can never feed this gate. The only way evidence accrues: stamp
  `consensus_engine: shadow` on PRDs that will run through autopilot. 00169 was
  chosen for a hand-run fast track instead, so it banks nothing here. Before
  un-parking, re-ground the body (it maps `~/.claude/`, names `create-prd` and
  `review-prd-backlog`, which this plugin does not ship) and weigh the
  size-threshold arming the 2026-08-26 cost evidence supports.
- **2026-09-20: re-checked after the 0.5.3/0.5.4 lane drain; still 0 cycles, still
  parked.** The eleven PRDs (00194-00206) were reviewed through standalone
  `review-work-completion` sessions in lane worktrees, none stamped `shadow`, so no
  `consensus_run_id` landed. Operator decision: stamp `consensus_engine: shadow` on the
  agent-skills validation batch (00052-00057; 00052 was already past Phase 0, so its
  `state.consensus_engine` was set to `shadow` by hand). Each of those review cycles
  banks a shadow observation in agent-skills' `dev/local/reviews/`; the eligibility
  command above reads THIS repo's reviews, so copy the stats_lines into
  `dev/local/reviews/00110-flip-evidence.md` here after that batch (the note of
  2026-08-23 applies), then re-run the gate. Cost caveat: the shadow multiplies Alice's
  tokens ~6.5x per cycle, so the validation batch's $/PRD reads high against the 0.5.2
  baseline; subtract the shadow cost from the comparison.
- **2026-09-20 23:07: the shadow stamp banks nothing on this harness build.** agent-skills
  00052 cycle 1 (0.5.4, `consensus_engine: shadow`) fell back to legacy Alice: the
  `Workflow` tool refuses `scriptPath ~/.claude/workflows/review-fanout.workflow.js`
  from a repo that is not `~/.claude` ("must be a script path this tool returned, or a
  file you can already read"). No `consensus_run_id` was stamped. Before this PRD can
  accrue evidence anywhere but `~/.claude`, review-work-completion step 5 must pass the
  workflow inline (`script`) or from a path under the repo, or the loop must launch with
  `--add-dir ~/.claude/workflows`; see
  `dev/local/notes/validation-batch-054-2026-09-20.md` finding V4.
- **2026-09-21 02:31 update:** the 00052 cycle-2 session copied the workflow into the
  repo's `dev/local/tmp/` and the shadow leg ran (`consensus_run_id: wf_bc133a2a-4a5`,
  `dimensions 5, raw 11, unique 11`, APPROVE, no gating divergence). Two follow-ups before
  evidence can count: (1) make that copy the skill's documented step 5 procedure; (2) the
  gate greps `no verdict divergence` but the skill pins no wording (this file wrote
  "Divergence from legacy Alice: none at the gating level"), so pin the phrase in
  review-work-completion or re-key the gate. First banked cycle in substance: agent-skills
  00052 cycle 2 (raw == unique, so no dedup collapse yet).

