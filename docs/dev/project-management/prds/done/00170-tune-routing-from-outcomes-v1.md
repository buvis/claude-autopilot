# Tune routing from recorded outcomes

> Rehomed 2026-09-02 from `~/.claude` PRD 00113 (held four times there; its
> rule surfaces moved into this pack on 2026-08-25 and plugin PRD 00160 replaced
> the thresholds it meant to tune). Decisions carried over: apply-mode is
> **propose-only**; quality reversion stays manual, code never pulls a
> kill-switch (discovery Q3). Source:
> `~/.claude/dev/local/discovery/00065-deepen-model-escalation.md`, requirement 11.

## Overview

### Problem Statement

Routing rules are hand-set: the mechanical (haiku) row in
`skills/plan-tasks/scripts/classify_tier.py` (`_MECHANICAL_MAX_FILES = 2`,
`_MECHANICAL_MAX_LINES = 50`, nine phrases), the repair budget in
`skills/run-autopilot/references/model-ladder.md` § Per-rung budgets, and the
codex rung's on/off switch. The pack now records what happens to every task:
`dev/local/autopilot/ledger/attempts.jsonl` holds one row per attempt with the
verbatim attempt object, including the PRD 00065 escalation stamps
(`escalation_reason`, `escalated_from`, `repair_used`, `cause`). Nothing feeds
those outcomes back into the rules.

Two gaps block it. The ledger row copies `task_model` and `qwen_eligible` but
not `tasks[].tier_reason` (PRD 00160) or the plan-time
`tasks[].qwen_excluded_reason`, so an escalation cannot be traced to the rule
that set the tier. And the store is small: 11 rows from one PRD and zero
escalations on 2026-09-02, so any tuner must say HOLD honestly rather than
guess.

### Target Users

The operator deciding whether a routing rule should move; the batches that
inherit the tuned rule.

### Success Metrics

- Every ledger row written after this PRD carries `task_tier_reason` and
  `task_qwen_excluded_reason` (`null` when the task has none).
- `tune_routing.py` derives every proposal deterministically from the ledger
  with a per-signal minimum-sample floor of 12 rows; below the floor it emits
  HOLD with the count still needed, never a guessed number. The same ledger and
  `--date` produce byte-identical output on two runs.
- The tuner writes a proposal file (and a patch file when a proposal targets a
  source line); it never edits a rule surface and never sets a kill-switch.
- One real run lands in `dev/local/audit-results/`; HOLD on every signal is an
  acceptable, recorded outcome.

## Functional Decomposition

### Capability: Attributable ledger rows

Every attempt row names the plan-time rule that set its tier.

#### Feature: Plan-time routing fields in the ledger row
- **Description**: `append_attempt_rows` copies two more task fields into each row.
- **Inputs**: `state.tasks[i].tier_reason`, `state.tasks[i].qwen_excluded_reason` at `complete-prd`.
- **Outputs**: row keys `task_tier_reason` (string or `null`) and
  `task_qwen_excluded_reason` (string or `null`), beside the existing
  `batch_id, prd, task_id, task_name, task_model, qwen_eligible, recorded_at, attempt`.
- **Behavior**: absent task fields (legacy plans) write `null`; every other key and
  the append procedure are byte-identical to today. Existing readers
  (`audit-qwen`'s `read_attempt_ledger`) load rows as dicts and ignore extra keys.

### Capability: Outcome analysis

Read the ledger, find the rules it contradicts.

#### Feature: Signal extraction
- **Description**: deterministic aggregation of ledger rows into three signals plus one report-only table.
- **Inputs**: `--ledger PATH` (default: `dev/local/autopilot/ledger/attempts.jsonl`
  under the autopilot dir resolved with the existing `_walk_up.py` pattern);
  rows deduped on `(batch_id, prd, task_id, attempt.attempt)` per
  `state-schema.md` § Attempt ledger.
- **Outputs**: per signal, `PROPOSE` or `HOLD` with `n`, the rate, the PRDs
  behind it and, on HOLD, `needed: <12 - n> more rows`.
- **Behavior**: floors and rates are module constants at the top of the script,
  cited in the output. Signals:
  - **S1 mechanical row**: rows with `task_tier_reason == "mechanical"` and
    `attempt.attempt == 1` (one row per task: `task_tier_reason` is copied from
    the task, so an escalated task's later rows would count twice); rate =
    share with `attempt.outcome == "escalated"`. Rate >= 0.5 over >= 12 rows ->
    PROPOSE halving `_MECHANICAL_MAX_LINES` (integer division). Rows without
    `task_tier_reason` are counted as `unattributed` and never feed S1.
  - **S2 repair budget**: rows with `attempt.repair_used == true`; rate = share
    with `attempt.outcome == "completed"`. Rate < 0.5 over >= 12 rows -> PROPOSE
    removing the Repair row from § Per-rung budgets (prose proposal, no patch).
  - **S3 codex rung**: rows with `attempt.implementor == "codex"`; rates = share
    with `attempt.cause == "codex_no_edit"`, and share of the next row for the
    same `(batch_id, prd, task_id)` carrying `attempt.escalated_from == "codex"`.
    Either rate >= 0.5 over >= 12 rows -> PROPOSE the operator set
    `_WORK_CODEX_RUNG=off` for the next batch (prose; the switch is never set by code).
  - **Report-only**: escalation count by `task_tier_reason` value
    (`contract`, `algorithmic_risk`, `floor`, `test_port`, `packaging`,
    `default`, `mechanical`, `unattributed`). No proposal is ever derived from
    `contract`, `algorithmic_risk` or `floor` rows (opus and operator floors are
    out of tuning scope). The qwen fence is out of scope too: `audit-qwen`
    owns the WIDEN/NARROW/HOLD fence verdict from the same ledger, and the
    proposal file only names the newest `dev/local/audit-results/audit-qwen-*.md` (link-ok:
    glob over another skill's reports) when one exists.
  - A row missing `attempt` (object), `task_model` or `attempt.outcome` is
    `UNPARSED` with the field named; when zero rows parse the whole run is
    `UNPARSED`, never a HOLD with silent zeros.

### Capability: Proposal emission

Evidence becomes a file the operator accepts with one command.

#### Feature: Proposal and patch files
- **Description**: one markdown proposal per run, plus a unified diff when a proposal targets a source line.
- **Inputs**: the signal results; `--date YYYY-MM-DD` (default: today, UTC);
  `--classifier PATH` (default `skills/plan-tasks/scripts/classify_tier.py`
  relative to the repo root); `--out-dir` (default `dev/local/audit-results/`).
- **Outputs**: `<out-dir>/routing-proposal-<date>.md` with sections `Sources`
  (ledger path, rows, deduped rows, PRDs, `recorded_at` range, UNPARSED count),
  one section per signal, the report-only table, and a `Revert` line per
  PROPOSE; `<out-dir>/routing-proposal-<date>.patch` only when S1 proposes,
  holding `difflib.unified_diff` of the classifier with the one constant line
  replaced, applicable with `git apply`.
- **Behavior**: stdlib only; the classifier is read, never written; if the
  literal `_MECHANICAL_MAX_LINES = <int>` is not found the S1 section reads
  `UNPARSED: _MECHANICAL_MAX_LINES` and no patch is written. The `Revert` line
  states `git revert` of the accepting commit and notes that `_PLAN_TASKS_FLOOR`
  is read by no script, so it does not guard the constant.

## Structural Decomposition

### Repository Structure

```
skills/run-autopilot/
├── cli/
│   └── statectl.py                     # Maps to: Plan-time routing fields (append_attempt_rows)
├── scripts/
│   ├── test_statectl_ledger.py         # two new row-field cases
│   ├── tune_routing.py                 # NEW - Maps to: Signal extraction, Proposal and patch files
│   └── test_tune_routing.py            # NEW - fixture-driven
└── references/
    ├── state-schema.md                 # § Attempt ledger: row shape + example gain the two keys
    └── model-ladder.md                 # § Kill-switches: _PLAN_TASKS_FLOOR is read by no script; § Tuning pointer
CHANGELOG.md
```

### Module: ledger-row
- **Maps to capability**: Attributable ledger rows
- **Responsibility**: the two extra keys in `append_attempt_rows`; nothing else in `statectl.py` changes.
- **Exports**: row keys `task_tier_reason`, `task_qwen_excluded_reason`

### Module: tune-routing
- **Maps to capability**: Outcome analysis, Proposal emission
- **Responsibility**: read and dedupe the ledger, compute S1-S3 and the report table, write the proposal and optional patch. No state.json access, no git, no network, no writes outside `--out-dir`.
- **Exports**:
  - CLI `tune_routing.py [--ledger PATH] [--classifier PATH] [--out-dir DIR] [--date YYYY-MM-DD]`, exit 0 on PROPOSE or HOLD, exit 1 on a fully UNPARSED run or an unwritable out-dir
  - `load_rows(path) -> tuple[list[dict], list[str]]` (rows, unparsed reasons)
  - `signals(rows) -> dict[str, dict]` keyed `S1`, `S2`, `S3`, `report`
  - `render(signals, sources, date, classifier_text) -> tuple[str, str | None]` (markdown, patch or None)

### Module: routing-prose
- **Maps to capability**: Proposal emission
- **Responsibility**: the schema rows for the two keys, the kill-switch honesty line, and the pointer from the ladder to the tuner.
- **Exports**: none (prose)

## Dependency Graph

### Foundation Layer (Phase 0)
No dependencies - built first.

- **ledger-row**: rows become attributable.

### Core Layer (Phase 1)
- **tune-routing**: Depends on [ledger-row] - S1 reads `task_tier_reason`.

### Integration Layer (Phase 2)
- **routing-prose**: Depends on [tune-routing, ledger-row] - documents both.

## Implementation Phases

### Phase 0: Foundation
**Goal**: New ledger rows name their tier rule.

**Tasks**:
- [ ] Add `task_tier_reason` and `task_qwen_excluded_reason` to the row dict in
      `append_attempt_rows` (`skills/run-autopilot/cli/statectl.py`), read with
      `task.get(...)` so absent fields write `null`. Premise: the row dict there
      holds exactly `batch_id, prd, task_id, task_name, task_model, qwen_eligible,
      recorded_at, attempt`. Add two cases to
      `skills/run-autopilot/scripts/test_statectl_ledger.py`: a task with both
      fields set writes both values; a legacy task without them writes `null`
      for both and every other key is unchanged (no deps) - Acceptance:
      `uv run --no-project --with pytest python -m pytest -q skills/run-autopilot/scripts/test_statectl_ledger.py skills/run-autopilot/scripts/test_statectl_complete_prd.py`
      green with both new cases present.

**Exit Criteria**: A `complete-prd` on a 00160-era plan appends rows carrying both keys.

### Phase 1: Core
**Goal**: The tuner turns a ledger into a proposal, or an honest HOLD.

**Tasks**:
- [ ] Write `skills/run-autopilot/scripts/tune_routing.py` (stdlib only) with
      `load_rows`, `signals`, `render` and the CLI above; floors and rates as
      module constants `MIN_ROWS = 12`, `S1_ESCALATION_RATE = 0.5`,
      `S2_COMPLETED_RATE = 0.5`, `S3_FAILURE_RATE = 0.5` (depends on: Phase 0) -
      Acceptance: `python3 skills/run-autopilot/scripts/tune_routing.py --ledger /nonexistent --out-dir <tmp> --date 2026-01-01`
      exits 1 and writes nothing.
- [ ] Write `skills/run-autopilot/scripts/test_tune_routing.py` with fixture
      ledgers covering: 12 first-attempt mechanical rows with 7 `outcome:
      "escalated"` (plus those 7 tasks' second-attempt rows, which S1 ignores)
      -> S1 PROPOSE, a `.patch` whose only changed line is
      `_MECHANICAL_MAX_LINES = 50` -> `_MECHANICAL_MAX_LINES = 25`; 11 such
      first-attempt rows -> S1 HOLD with
      `needed: 1 more rows` and no patch; 12 `repair_used` rows with 5 completed
      -> S2 PROPOSE; 12 codex rows with 6 `codex_no_edit` -> S3 PROPOSE naming
      `_WORK_CODEX_RUNG=off`; rows with `task_tier_reason` in `contract`,
      `algorithmic_risk`, `floor` never change any signal and appear only in the
      report table; a duplicated row (same `batch_id, prd, task_id,
      attempt.attempt`) counts once; a row missing `attempt.outcome` ->
      `UNPARSED: attempt.outcome` while the other rows still count; a classifier
      file without the constant literal -> `UNPARSED: _MECHANICAL_MAX_LINES` and
      no patch; two runs on the same inputs and `--date` -> byte-identical files
      (depends on: Phase 1 task 1) - Acceptance:
      `uv run --no-project --with pytest python -m pytest -q skills/run-autopilot/scripts/test_tune_routing.py`
      green with all nine cases present.

**Exit Criteria**: Extraction and rendering proven on fixtures; scope guard and determinism pinned.

### Phase 2: Integration
**Goal**: One real cycle, auditable end to end.

**Tasks**:
- [ ] Document the two row keys in `skills/run-autopilot/references/state-schema.md`
      § Attempt ledger (row shape sentence and the JSON example); add to
      `skills/run-autopilot/references/model-ladder.md` § Kill-switches the
      sentence that `_PLAN_TASKS_FLOOR` is read by no script and does not guard
      `classify_tier.py` constants, and a `## Tuning` pointer naming
      `tune_routing.py` and the proposal path; add the CHANGELOG entry (`feat`
      commit, `**run-autopilot**` under Added: "attempt ledger rows carry
      task_tier_reason and task_qwen_excluded_reason; tune_routing.py proposes
      routing changes from the ledger"); then run the tuner once against this
      repo's real ledger and report the proposal path and its per-signal lines
      (the proposal lives under gitignored `dev/local/`, so it is a run
      artifact, never staged). Premise: `dev/local/autopilot/ledger/attempts.jsonl`
      exists with at least one row; if it does not, record STARVED in the task
      report and skip the run (depends on: Phase 1) - Acceptance:
      `rg -n "task_tier_reason" skills/run-autopilot/references/state-schema.md`
      hits; `rg -n "tune_routing" skills/run-autopilot/references/model-ladder.md CHANGELOG.md`
      hits in both; `rg -n "read by no script" skills/run-autopilot/references/model-ladder.md` hits;
      `python3 skills/run-autopilot/scripts/tune_routing.py` exits 0 and
      `dev/local/audit-results/routing-proposal-<today>.md` exists with a
      `Sources` section whose row count matches `wc -l` of the ledger minus
      duplicates and one `PROPOSE` or `HOLD` line per signal;
      `git status --porcelain skills/` empty after the run.

**Exit Criteria**: A proposal file exists for the real ledger; every rule surface is untouched.

## Test Strategy

### Critical Scenarios
- **Happy path**: 12 first-attempt mechanical rows, 7 escalated -> S1 PROPOSE
  with a one-line patch the operator applies with `git apply`.
- **Edge case**: every signal below its floor -> three HOLD lines with the
  counts needed; no patch file.
- **Edge case**: `contract`, `algorithmic_risk` and `floor` rows in the ledger ->
  report table only, no signal moves.
- **Error case**: ledger row missing `attempt.outcome`, or a classifier without
  the constant literal -> `UNPARSED` naming the field or literal; no
  partial-parse proposal.

## Risks

- **Goodhart**: the tuner reads escalation, completion and no-edit rates only;
  cost share is never an input (discovery Q2).
- **Auto-apply footgun**: propose-only by decision; the only file the tuner
  writes outside `--out-dir` is none. Reversion is `git revert` of the
  accepting commit, stated on every proposal.
- **Source schema drift**: readers pin the field names above; drift renders
  `UNPARSED` naming the field.
- **Rule surface drift**: the S1 patch is produced from the live classifier
  text at run time, so a moved constant yields `UNPARSED`, not a stale diff.
- **Starvation**: with 11 rows today every signal HOLDs; that is the designed
  first outcome, and the floors make the next move a matter of batches, not
  guesses.
