---
catchup: skip
design: skip
eligibility: grep -q "def is_test_path" skills/work/scripts/work_routing.py
---

# Route opus on task-local risk

Source: `dev/local/discovery/00157-autopilot-efficiency-policies.md`, PRD 2 of 3 (must-haves 9-13, Q6-Q8). Depends on PRD 00159's `is_test_path` predicate; the `eligibility:` gate above keeps this PRD in `backlog/` until that lands, so a drain never plans it against a tree that lacks the symbol.

Amended 2026-09-02 after review cycle 2 (rework cap, 4/4 finding): the classifier tests live in five `test_classify_tier_*.py` modules plus `_classify_tier_test_support.py` (the single file outgrew the 800-line cap), and the CLI also rejects a negative `--lines`. Acceptance lines below name the split modules.

## Overview

### Problem Statement

`/autopilot:plan-tasks` step 4.7 Rule 1 promotes a task to `opus` when the PRD or task text contains any of `design`, `architect`, `introduce`, `novel algorithm`, `concurrency`, `migrate`, `refactor across`, or when `files_touched > 8`, or when `estimated_tokens > 120000`. The PRD-wide scan means one word in a PRD body promotes every task in it; the generic words match ordinary prose ("introduce a flag"); size is a proxy that has nothing to do with the risk `opus` is meant to buy. The recent 12-task run paid Opus, Devon and the full pipeline for test ports and packaging edits this way. The explicit `default_model: opus` floor is the operator's tool and must stay; the automatic promotions are the waste.

### Target Users

The operator, who wants `opus` spent only where a wrong implementation is expensive, and the `/autopilot:plan-tasks` session, which must classify each task deterministically with no one to ask.

### Success Metrics

- The tier decision is code (`classify_tier.py`) with tests; the only model judgments are two per-task boolean facts with written evidence rules.
- Under automatic routing a pure test-port or packaging task persists `model: "sonnet"` even when a manifest is externally consumed; a task persists `model: "opus"` only with `tier_reason` `contract`, `algorithmic_risk` or `floor`.
- `default_model: opus` still raises every task to `opus` (`cli/routing.py`'s session-model signal reads the same key and is untouched).
- Post-release signal: the next batch's `state.tasks[]` carry `tier_reason` on every task, and no task classified `opus` has a reason outside those three values.

## Functional Decomposition

### Capability: Tier classifier
One pure function, one CLI, exact precedence.

#### Feature: Sonnet-pinned classes
- **Description**: Test ports and packaging work are fixed at `sonnet` under automatic routing.
- **Inputs**: the task's file slice (repo-relative paths).
- **Outputs**: `("sonnet", "test_port")` or `("sonnet", "packaging")`.
- **Behavior**: `is_test_path` is imported by path from `skills/work/scripts/work_routing.py` (PRD 00159; `Path(__file__).resolve().parents[2] / "work" / "scripts" / "work_routing.py"` via `importlib`), the one predicate planning and execution share. `is_packaging_path(path)` is true when the basename is one of `plugin.json`, `marketplace.json`, `package.json`, `package-lock.json`, `pnpm-lock.yaml`, `yarn.lock`, `pyproject.toml`, `uv.lock`, `poetry.lock`, `setup.py`, `setup.cfg`, `MANIFEST.in`, `Pipfile`, `Pipfile.lock`, `Cargo.toml`, `Cargo.lock`, `go.mod`, `go.sum`, `mise.toml`, `.mise.toml`, `.tool-versions`, matches `requirements*.txt`, or a directory segment is `.claude-plugin`. A non-empty slice whose every path is a test path is `test_port`; a non-empty slice whose every path is a test or packaging path is `packaging`. These two rules come first: an externally consumed manifest is still packaging, and a test file that mentions concurrency is still a test.

#### Feature: Task-local opus signals
- **Description**: `opus` is assigned from two per-task facts, never from PRD-wide text, file count or token count.
- **Inputs**: `contract_edit: bool`, `algorithmic_risk: bool`, judged by the planner per task under the evidence rules in the planner prose capability.
- **Outputs**: `("opus", "contract")` or `("opus", "algorithmic_risk")`.
- **Behavior**: Evaluated after the sonnet-pinned classes, before the mechanical rule. Neither `files_touched > 8` nor `estimated_tokens > 120000` nor any keyword promotes any more; the 4.6 context-budget split still bounds size.

#### Feature: Mechanical rule, default and floor
- **Description**: Rule 2 (`haiku`) is unchanged; Rule 3 defaults to `sonnet`; the PRD frontmatter floor applies last.
- **Inputs**: `text` (task title plus description), `lines_changed`, the file slice, `default_model`.
- **Outputs**: `("haiku", "mechanical")`, `("sonnet", "default")`, or the floored tier with `tier_reason: "floor"`.
- **Behavior**: `haiku` when `len(files) <= 2` and `lines_changed <= 50` and the lowercased text contains one of exactly `add log`, `rename`, `add test for`, `port`, `mirror`, `inline`, `extract constant`, `update import`, `bump version` (the risk facts are already false here by precedence, which replaces the old "no Rule 1 keywords" clause). Otherwise `sonnet`. Then `final = max(tier, default_model)` over `haiku < sonnet < opus` when `default_model` is one of the three; when the floor raised the tier, `tier_reason` becomes `floor`. An invalid or absent `default_model` leaves the tier as classified; an invalid value prints one warning line to stderr. `_PLAN_TASKS_FLOOR` stays a prose-only, inert knob exactly as documented today; the script does not read it.

#### Feature: Classifier CLI
- **Description**: `skills/plan-tasks/scripts/classify_tier.py`, stdlib, Python 3.10+.
- **Inputs**: `--files-file <path>` (newline-separated slice), `--text-file <path>`, `--lines <int>`, optional `--contract-edit`, `--algorithmic-risk`, `--default-model <haiku|sonnet|opus>`.
- **Outputs**: stdout JSON `{"model": "<tier>", "tier_reason": "<reason>"}`; exit 0; exit 1 on a missing flag, an unreadable file or a negative `--lines` with the cause on stderr.
- **Behavior**: `classify(files, text, lines_changed, contract_edit, algorithmic_risk, default_model) -> dict` is the pure core; the CLI only reads the two files and prints. Task-authored prose crosses as files, never as shell words (the `--set-file` rule from `/autopilot:work`).

### Capability: Planner prose
Step 4.7 runs the script; the facts have evidence rules; step 4.6's exemption follows.

#### Feature: Evidence rules for the two facts
- **Description**: Step 4.7 states when the planner may assert each fact.
- **Inputs**: the task's own `Contract`, `Location`, `Details` and file slice.
- **Outputs**: the two flags passed to the CLI.
- **Behavior**: `contract_edit` is true only when the task itself changes an exported API signature, a persisted schema, a wire format or a hook registration shape, the same definition the `qwen_excluded_reason: contract` clause already uses; calling or documenting a contract does not count. `algorithmic_risk` is true only when the task's own Details name a new algorithm it implements (not one it calls), shared mutable state across threads, processes or async tasks, or a transform of persisted data (a migration). Words in the PRD body, the PRD title or the task name alone never qualify, and neither do `design`, `architect`, `introduce`, `refactor across`, file count or `estimated_tokens`. The facts are judged once per task before step 4.6 and reused in 4.7. Because a contract task now classifies `opus`, `qwen_excluded_reason: contract` becomes unreachable on new plans (`tier` is recorded first); readers keep accepting it on old plans, and the codex fence is unaffected (opus is never intercepted).

#### Feature: Step 4.6 risk exemption
- **Description**: The eligibility split skips tasks that will classify `opus`.
- **Inputs**: the two facts.
- **Outputs**: the task kept whole.
- **Behavior**: Replaces the "opus-signal exemption" text scan: a task with either fact true is not split for eligibility (opus is never qwen-eligible); the context-budget trigger is unaffected.

#### Feature: `tier_reason` persisted
- **Description**: Every task records why it got its tier.
- **Inputs**: the CLI output.
- **Outputs**: top-level `tier_reason` in the `task-add` payload, one of `test_port`, `packaging`, `contract`, `algorithmic_risk`, `mechanical`, `default`, `floor`.
- **Behavior**: `statectl task-add` persists any top-level key and `cli/schema.py` validates only `description` and `blocked_by`, so no state code changes; `state-schema.md` documents the field, absent on legacy plans.

## Structural Decomposition

### Repository Structure

```
skills/plan-tasks/
├── SKILL.md                              # Maps to: Planner prose (steps 4.6, 4.7)
├── scripts/
│   ├── classify_tier.py                  # Maps to: Tier classifier
│   ├── _classify_tier_test_support.py    # Maps to: Tier classifier (shared test bootstrap)
│   ├── test_classify_tier_cli.py         # Maps to: Tier classifier (tests, one theme per module)
│   ├── test_classify_tier_default_floor.py
│   ├── test_classify_tier_mechanical.py
│   ├── test_classify_tier_risk_flags.py
│   ├── test_classify_tier_sonnet_paths.py
│   └── test_plan_tasks_prose.py          # Maps to: Planner prose (pins)
└── references/design-rationale.md        # Maps to: Planner prose (why the keyword triggers went)
skills/run-autopilot/references/state-schema.md   # Maps to: tier_reason persisted
CHANGELOG.md
```

### Module: tier-classifier
- **Maps to capability**: Tier classifier
- **Responsibility**: the precedence, the packaging predicate, the CLI; imports `is_test_path` rather than restating it.
- **Exports**: `classify(...)`, `is_packaging_path(path)`, CLI `classify_tier.py`

### Module: planner-prose
- **Maps to capability**: Planner prose
- **Responsibility**: step 4.7 rewritten around the script and the evidence rules (the `_PLAN_TASKS_FLOOR` paragraph kept), step 4.6's exemption, the worked examples, a design-rationale entry, the prose pins.
- **Exports**: none (prose)

### Module: schema-and-changelog
- **Maps to capability**: `tier_reason` persisted
- **Responsibility**: the `tasks[].tier_reason` row; the `tasks[].model` row names `classify_tier.py`; the CHANGELOG entry.
- **Exports**: none (prose)

## Dependency Graph

### Foundation Layer (Phase 0)
No dependencies inside this PRD - built first.

- **tier-classifier**: the decision core. Depends on PRD 00159's `is_test_path` (guarded by the `eligibility:` gate and the task Premise).

### Core Layer (Phase 1)
- **planner-prose**: Depends on [tier-classifier] (names its CLI and reasons).

### Integration Layer (Phase 2)
- **schema-and-changelog**: Depends on [tier-classifier, planner-prose].

## Implementation Phases

### Phase 0: Foundation
**Goal**: The classifier exists, imports the shared predicate, and is pinned by tests.

**Tasks**:
- [x] Add `skills/plan-tasks/scripts/classify_tier.py` and the `test_classify_tier_*.py` modules. Premise: `skills/work/scripts/work_routing.py` defines `is_test_path` (PRD 00159 landed). Tests: a slice of `tests/test_x.py` with text "port the concurrency tests" → `sonnet`/`test_port`; `plugin.json` plus `.claude-plugin/marketplace.json` with `contract_edit` → `sonnet`/`packaging`; `cli/schema.py` with `contract_edit` → `opus`/`contract`; `cli/loop.py` with `algorithmic_risk` → `opus`/`algorithmic_risk`; one file, 10 lines, "rename foo to bar" → `haiku`/`mechanical`; three files, no flags, text "design and migrate the cache layer" → `sonnet`/`default`; nine files, no flags → `sonnet`/`default`; `default_model=opus` on the test-port fixture → `opus`/`floor`; `default_model=haiku` on the default fixture → `sonnet`/`default`; `default_model=fable` → ignored with a stderr warning; an empty slice with no flags → `sonnet`/`default`; the CLI round-trips the JSON shape and exits 1 on a missing `--files-file` (no deps) - Acceptance: `uv run --no-project --with pytest python -m pytest -q skills/plan-tasks/scripts/test_classify_tier_*.py` green; `rg -n "def is_test_path" skills/plan-tasks/scripts/classify_tier.py` has no hit (imported, not copied).

**Exit Criteria**: Suite green; `python3 skills/plan-tasks/scripts/classify_tier.py --help` exits 0.

### Phase 1: Core
**Goal**: `/autopilot:plan-tasks` classifies through the script.

**Tasks**:
- [x] Rewrite `skills/plan-tasks/SKILL.md` step 4.7 (the rules table replaced by: judge the two facts under the evidence rules, write the slice and the text to `dev/local/tmp/plan-<n>-files.txt` and `dev/local/tmp/plan-<n>-text.txt`, run `python3 ${CLAUDE_PLUGIN_ROOT}/skills/plan-tasks/scripts/classify_tier.py --files-file ... --text-file ... --lines <n> [--contract-edit] [--algorithmic-risk] [--default-model <floor>]`, persist `model` and `tier_reason`; keep the `_PLAN_TASKS_FLOOR` paragraph, the frontmatter-override paragraph and the `qwen_eligible` computation, noting that `contract` is now unreachable on new plans), rewrite the step 4.6 "Opus-signal exemption" as the risk exemption, update the three worked examples, and add a `## Rule 1 keyword triggers retired (PRD 00160)` entry to `references/design-rationale.md`. Add `skills/plan-tasks/scripts/test_plan_tasks_prose.py` pinning: step 4.7 names `classify_tier.py`, `tier_reason`, `contract_edit` and `algorithmic_risk`; SKILL.md no longer contains `files_touched > 8` or `estimated_tokens > 120000` as triggers; step 4.6 no longer contains `signal list` (depends on: Phase 0) - Acceptance: `uv run --no-project --with pytest python -m pytest -q skills/plan-tasks/scripts/test_plan_tasks_prose.py` green; `rg -n "refactor across" skills/plan-tasks/SKILL.md` hits only inside the evidence rules' "does not count" sentence.

**Exit Criteria**: Prose pins green; `rg -n "_PLAN_TASKS_FLOOR" skills/plan-tasks/SKILL.md` still hits.

### Phase 2: Integration
**Goal**: The new field is documented and the change is released.

**Tasks**:
- [x] Add the `tasks[].tier_reason` row to `skills/run-autopilot/references/state-schema.md` (the seven values; absent on plans created before this PRD), name `classify_tier.py` in the `tasks[].model` row, and add the CHANGELOG line (`feat(plan-tasks)`: `**plan-tasks**` under Changed: opus is assigned per task on a public-contract edit or concrete algorithmic risk, PRD-wide keywords, file count and token count no longer promote, test ports and packaging pin to Sonnet, and every task records `tier_reason`) (depends on: Phase 1) - Acceptance: `rg -n "tier_reason" skills/run-autopilot/references/state-schema.md` hits; `rg -n "^- \*\*plan-tasks\*\*" CHANGELOG.md` hits under `[Unreleased]`; `uv run --no-project --with pytest --with rich --with textual python -m pytest -q skills/plan-tasks/scripts skills/work/scripts skills/run-autopilot` green.

**Exit Criteria**: Full suite green; `bash dev/bin/release-checks` green.

## Test Strategy

### Critical Scenarios
- **Happy path**: a test-port task in a PRD whose body says "design a concurrent migration" → `sonnet`/`test_port`; the same PRD's `cli/schema.py` task with `contract_edit` → `opus`/`contract`.
- **Edge case**: `default_model: opus` on the test-port task → `opus`/`floor`; a nine-file backend task with neither fact → `sonnet`/`default` and, having no risk fact, still enters the 4.6 eligibility split.
- **Edge case**: a packaging slice (`pyproject.toml`, `uv.lock`) with `contract_edit` asserted → `sonnet`/`packaging` (the pin outranks the fact; only the floor can raise it).
- **Error case**: `--default-model fable` → one stderr warning, tier unchanged, exit 0; a missing `--files-file` → exit 1.

## Risks

- **Under-routing risky work**: the two facts keep `opus` reachable for exactly the work the discovery names, the floor stays unconditional, and the review-flag escalation ladder (`haiku -> sonnet -> opus`) still lifts a task that fails review.
- **The planner over-asserts a fact from PRD-wide text**: the evidence rules say "the task's own" three times and list the words that do not count; the prose pin fails if the exclusion sentence is dropped.
- **Telemetry shift**: `qwen_excluded_reason: contract` stops appearing on new plans; the Implementor Mix render still renders old values, and `tier_reason: contract` carries the count forward.
