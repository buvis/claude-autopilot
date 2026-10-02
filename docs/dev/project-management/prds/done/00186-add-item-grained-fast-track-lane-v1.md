---
catchup: skip
design: skip
default_model: opus
model_tier_rationale: invents the spec-card contract and a driver that interleaves background CLI reviewers with subagents and a branch-or-reset exit rule that touches master
---

# Add an item-grained fast-track lane

## Overview

### Problem Statement
The loop pays per-PRD phases for every change: catchup, design, plan, then Tess/Devon/Ivan/deslop/Pat per task, then review cycles in fresh sessions (`skills/run-autopilot/references/phase-build.md:132-245`, `skills/work/SKILL.md:211-444`). On ddb batch 202607161128 the eight done PRDs cost $1,540 over 202,669 s, a mean of 7.0 h and $192 per PRD; 00167 alone ran 28 sessions, 40,058 s and $345.26 with review at $211.32 (`/Users/bob/git/src/github.com/doogat/ddb/dev/local/autopilot/reports/202607161128-report.md:301-305`). Review was 39-41% of the $2,028 batch and 0 of 4 August PRDs converged at `rework_cap` 2 (`/Users/bob/git/src/github.com/doogat/ddb/dev/local/audit-results/refactor-assessment-2026-09-06.md:16,63-65`); ~95 of 1,245 h were active (88% idle, `:15,50`); a task cost ~42 min and ~$18-19 (`:55`). The 00168 cap-out left a CRITICAL live on master for 25 commits (`:67`; `/Users/bob/git/src/github.com/doogat/ddb/dev/local/autopilot/deferred/202607161128-deferred.json:115-119`). The operator asked for "a fast track implementation plan that will avoid autopilot/autoclaude loops because these are terribly slow ... the key is using subagents with different models and zero context from driving session (so they are not biased)". The assessment's own plan needs it: step 5 runs 00175-00178 attended "PLUS `review-blindly` and `review-with-doubt` per PRD as the oracle" (`:159`) and rejects a plain attended sprint because it "forgoes the review lenses that found 4 CRITICALs in 00167 cycle 1" (`:163`).

What the neighbours already cover. Discovery 00148 § 6 became the rework-only micro lane (orchestrator edits, Pat kept; `skills/work/references/rework-mode.md:16-34`) and § 7 became `autopilot review-once`, one headless review SESSION for a PRD already in `wip/` with `state.json` (`dev/local/prds/done/00149-add-review-once-session-to-autopilot-cli-v1.md:18`, `skills/run-autopilot/cli/__main__.py:71-81`, `skills/run-autopilot/SKILL.md:153`). Discoveries 00157 and 00177 cut dispatches inside the loop and keep every lens (`dev/local/discovery/00177-cut-review-and-test-loop-overhead.md:57-62`). 00110 (hold) decides the workflow engine's default. None lets an operator run one PRD-less item through the full roster. This PRD adds only that delta: the spec card as the unit, a driver skill in the attended session, the whole roster at zero context, one rework, and an exit rule that never leaves a confirmed CRITICAL/HIGH on master.

### Target Users
The operator driving an attended sprint (ddb step 5) who wants the review without the loop; the reviewers, who get a card and a diff and nothing from the driver's head.

### Success Metrics
- `uv run --no-project --with pytest python -m pytest -q skills/fast-track/scripts` passes with every test named in the phases below; zero skips.
- From a fixture ledger, `count_item_dispatches` reports for a clean item exactly one `start` row each of `fast-track:ivan`, `fast-track:fanout`, `fast-track:blake`, `fast-track:eve`, `fast-track:bob`, `fast-track:carl` and none of `fast-track:victor`/`fast-track:delta`; for an item with one confirmed HIGH from Blake exactly 2 `fast-track:ivan`, 1 `fast-track:victor`, 1 `fast-track:delta`.
- `exit_action` returns `branch` whenever a CRITICAL or HIGH survives the delta review, and the SKILL.md prose that acts on it is pinned by `test_fast_track_prose.py`.
- `bash dev/bin/release-checks` runs the fast-track suite and passes.

## Functional Decomposition

### Capability: Spec card
The unit of work: one Markdown file the operator writes, the only thing every dispatch is assembled from.

#### Feature: Card format
- **Description**: `scripts/card.py` `load_card(path) -> Card` parses frontmatter `item` (slug: `[a-z0-9-]+`), `model` (`sonnet`|`opus`, Ivan's and Tess's tier), `suite` (`batch`|`per-item`, when the full suite runs), `changelog` (`none` or the one-line entry), plus `framework` and `sample_test` (required only when `## Tests` is empty); body sections `## Goal`, `## Tests` (`path::test_name` per line), `## Files` (absolute-or-repo-relative allowlist, one per line), `## Constraints`, `## Docs`, `## Gates` (one command per line, no `&&`/`;`/`|`), `## Transport impact` (one line).
- **Inputs**: the card path, anywhere under `dev/local/tmp/` or `dev/local/plans/` (both operator-owned, GC'd per `rules/working-documents.md`).
- **Outputs**: a `Card` dataclass, or exit 2 naming the missing section or bad value.
- **Behavior**: never guesses: an absent section is an error, not a default; a gate line with a chain character is refused with the same rule `output-formats.md:200-213` applies to queued checks.

#### Feature: Tests are the spec
- **Description**: when `## Tests` is empty, a fresh Tess writes them from the card alone.
- **Inputs**: `skills/work/references/tess-prompt.md` rendered with `TASK_SUBJECT` = `item`, `TASK_DESCRIPTION` = `## Goal` + `## Files`, `TASK_ACCEPTANCE_CRITERIA` = `## Constraints`, `SAMPLE_TEST_FILE` = `sample_test`, `PUBLIC_INTERFACES` = the `## Files` contents, `TEST_FRAMEWORK` = `framework` (the render shape at `skills/work/SKILL.md:221-230`), flags `--dispatch-kind fast-track:tess --dispatch-task <item>`.
- **Outputs**: test files at the paths Tess reports, committed as `test(<item>): add tests for <goal>` after a red check.
- **Behavior**: the first `## Gates` line is the red-check command (`skills/work/SKILL.md:271-275`); green before Ivan stops the item with `stopped: tests-green-before-implementation`. Tess never receives the driver's reasoning, only the card fields above.

### Capability: Driver
The lane itself: one skill invoked in the operator's session, no `state.json`, no phases.

#### Feature: Invocation and preconditions
- **Description**: `/autopilot:fast-track <card.md> [<card.md> ...] [--push]`, items processed in argument order.
- **Inputs**: the card paths; `git rev-parse HEAD` held as `<base>` per item; `git status --porcelain`.
- **Outputs**: one report per item at `dev/local/tmp/<item>-fast-track-review.md` (consolidated table, per-lane sections, victor verdicts, exit line) and the ledger rows below.
- **Behavior**: refuses when `$_AUTOPILOT_LOOP` is set (headless sessions kill background Bash, `references/agent-invocation.md:27`; this lane is attended by design) or when a dirty path lies inside the card's `## Files` (the foreign-WIP rule, `skills/work/SKILL.md:353,366`).

#### Feature: Implement and gate
- **Description**: a fresh `autopilot:ivan` at the card's `model` makes the tests pass inside the allowlist.
- **Inputs**: `agents/ivan.md` rendered as at `skills/work/SKILL.md:289-296` with `FAILING_TESTS` = the test files, `ARCHITECTURE_CONTEXT` = `## Constraints` + `AGENTS.md`, `FILE_PATHS` = `## Files`, `RETRY_INSTRUCTION` empty, `--dispatch-kind fast-track:ivan --dispatch-task <item>`, every path `--require-file`/`--require-parent`.
- **Outputs**: one commit of exactly `FILES_TOUCHED` (plus `CHANGELOG.md` when `changelog` is not `none`), message `<type>(<item>): <goal>`.
- **Behavior**: then every `## Gates` line runs in the foreground, one Bash call each, in order; a non-zero exit stops the item with `stopped: gate <n>` and no reviewer is dispatched. No deslop, no style gate, no Pat, no Devon (decision 4).

#### Feature: Exit rule
- **Description**: `fast_track_plan.exit_action(confirmed: list[Finding]) -> "commit" | "branch"`.
- **Inputs**: the confirmed findings after the delta review (or after the roster when nothing was confirmed).
- **Outputs**: `commit` leaves the item's commits on the current branch; `branch` runs `git branch fast-track/<item> HEAD` then `git reset --keep <base>` and reports the branch name and the surviving findings.
- **Behavior**: `branch` whenever any confirmed CRITICAL or HIGH remains; `--keep` refuses rather than clobbers a foreign change, and a refusal stops with the paths named, never `--hard`. With `--push`, `git push` runs once after the last item's `suite: batch` run is green, never per item.

### Capability: Zero-context roster
Every lens the review skill runs (`skills/review-work-completion/SKILL.md:45-52`), each dispatched fresh from the card and the diff, all in one message.

#### Feature: Lanes
- **Description**: the roster, dispatched together like step 5 of the review skill (`skills/review-work-completion/SKILL.md:264`; every `SKILL.md:` cite in this capability is that file): Task subagents plus background Bash, never a CLI inside a subagent.
- **Inputs**: `<base>..HEAD` diff written to `dev/local/tmp/<item>-fast-track.diff`; a context file holding the card verbatim, the changed-file list and `compute_mech_facts.py` output (`SKILL.md:168-174`); the card body as `{PRD}`.
- **Outputs**: `dev/local/tmp/<lane>-output-<item>.txt` per lane, consolidated by `consolidate_findings.py` exactly as `SKILL.md:365-371` (no `--ledger`; there is no ledger).
- **Behavior**: consensus = the `review-fanout` workflow (`Workflow` by absolute `scriptPath`, args as `SKILL.md:315-325`, `prd_text` = the card, `agent_name` = `ALICE`, kind `fast-track:fanout`) when `~/.claude/workflows/review-fanout.workflow.js` exists (`README.md:100-104`), else `autopilot:alice` (`agents/alice.md:5`, sonnet) as kind `fast-track:alice`; blind = `autopilot:blake` (sonnet, `agents/blake.md:5`) with `{PRD}` = the card and the blind rubric only, never the diff, plus the filesystem-notes block when its trigger holds (`agent-invocation.md:80-90`); doubt = `autopilot:eve` (fable, `agents/eve.md:5`) with her five run inputs (`agent-invocation.md:104-123`) and a sixth, the `{OUTPUT_FORMAT}` block (`output-formats.md:16-30`), so each FIX item is also an `[EVE] {emoji} ... | File: ...` line the consolidator can read; Bob = `codex-run.sh -f <prompt> -o <out>` as background Bash (`agent-invocation.md:35`, persona `agents/bob.md` + Eve's two sections per `SKILL.md:245`); Carl = `gemini-run.sh -f <prompt> -o <out>` as background Bash (`agent-invocation.md:55`) when the step-1 binary check passes (`SKILL.md:81`), else `carl: skipped (no backend CLI)` in the report. Bob's exit-3 Claude fallback and the one-retry budget apply unchanged (`SKILL.md:276`, `references/retry-policy.md:7,19`). No Watcher: the attended session is re-invoked when a background command ends.

#### Feature: Verify, rework, delta
- **Description**: adversarial verification, one fresh rework, one delta review.
- **Inputs**: every CRITICAL/HIGH row of the consolidated table raised by a non-workflow lane (the workflow already ran victor on its own findings, `~/.claude/workflows/review-fanout.workflow.js:7,460-471`).
- **Outputs**: one `fast-track:victor` dispatch per such row: `agents/victor.md` rendered through `render_prompt.py` with `FINDING_TITLE/SEVERITY/FILE/EVIDENCE/PROOF` (`agent-registry.md:72`), dispatched as a `general-purpose` Task with the rendered body as its prompt, the same shape the workflow uses (`review-fanout.workflow.js:460-471`), at `model: sonnet` (guess); `refuted: false` confirms. Confirmed rows plus the workflow's own confirmed rows are the rework spec.
- **Behavior**: rework = a second fresh `autopilot:ivan` at the card's `model` with `FAILING_TESTS` = the confirmed findings written to `dev/local/tmp/<item>-ivan-checks.txt` (the shape `skills/work/SKILL.md:285` already uses), same allowlist, commit `fix(<item>): address confirmed findings`, gates again; then one `fast-track:delta` dispatch, `autopilot:eve` on `<rework-base>..HEAD` with the confirmed list and the incremental instruction from `skills/review-work-completion/SKILL.md:258`; each confirmed finding she reports unresolved survives. MEDIUM/LOW never rework and never block; they are listed in the report. Zero confirmed rows means zero victor, zero rework, zero delta.

#### Feature: Ledgers
- **Description**: every dispatch is a ledger row; every item is a metrics row.
- **Inputs**: `skills/work/scripts/record_dispatch.py start --kind fast-track:<lane> --task <item> --prompt-file <prompt>` before each dispatch and `end <id> --outcome ...` after (`record_dispatch.py:7-9`; the kind is free-form, `record_dispatch.py:123-128`); background Bash lanes open their row before launch and close it when the output file is read.
- **Outputs**: `scripts/record_item.py --item <item> --card <path> --model <m> --started <ts> --outcome committed|branched|stopped --rework 0|1 --findings <json> --confirmed <n> [--cost <usd>]` appends `{"ts_start","ts_end","wall_secs","prd": <card basename>,"batch":"fast-track","phase_launched":"fast-track","phase_end":"fast-track","signal": <outcome>,"model","cost_usd","findings","confirmed","rework","outcome"}` to `dev/local/autopilot/loop-metrics.jsonl` and `ledger/loop-metrics.jsonl` (the row shape at `skills/run-autopilot/cli/loop.py:893-903`, as written in `/Users/bob/git/src/github.com/doogat/ddb/dev/local/autopilot/loop-metrics.jsonl:2`).
- **Behavior**: `cost_usd` is `null` unless `--cost` is passed (an attended session has no `last-session.log` to read, `loop.py:904`); never a guessed number. `render_metrics` groups by `phase_launched` (`cli/render_metrics.py:75`) so the row renders as its own line and `matching_rows` (`:61`) keeps it out of PRD sections. Both scripts exit 0 on a failed write, printing one stderr line (`record_dispatch.py:44-60`).

## Structural Decomposition

### Repository Structure

```
skills/fast-track/
├── SKILL.md                              # Maps to: Driver (invocation, gates, exit rule, lane order)
├── references/
│   ├── spec-card.md                      # Maps to: Spec card (format, one worked example)
│   └── lane-dispatch.md                  # Maps to: Zero-context roster (per-lane command lines)
└── scripts/
    ├── card.py                           # Maps to: Card format
    ├── fast_track_plan.py                # Maps to: Lanes, Verify/rework/delta, Exit rule (pure functions)
    ├── record_item.py                    # Maps to: Ledgers
    ├── test_card.py
    ├── test_fast_track_plan.py
    ├── test_record_item.py
    └── test_fast_track_prose.py          # Maps to: SKILL.md and reference pins
README.md, CHANGELOG.md, dev/bin/release-checks
```

### Module: card
- **Maps to capability**: Spec card
- **Responsibility**: parse and validate one card; no I/O beyond reading it.
- **Exports**:
  - `load_card(path) -> Card` - dataclass with the frontmatter keys and the seven sections
  - `CardError` - carries the field name; the CLI wrapper exits 2

### Module: plan
- **Maps to capability**: Zero-context roster, Driver
- **Responsibility**: the deterministic decisions the driver must not make from memory (`rules/ai-app-design.md`).
- **Exports**:
  - `plan_lanes(tests_present, workflow_available, carl_available) -> list[str]` - the ordered dispatch kinds before findings exist
  - `verify_targets(rows) -> list[Finding]` - CRITICAL/HIGH rows from non-workflow lanes
  - `exit_action(confirmed) -> "commit" | "branch"`
  - `count_item_dispatches(ledger_path, item) -> Counter` - `start` rows by kind for `task == item`

### Module: record-item
- **Maps to capability**: Ledgers
- **Responsibility**: the per-item metrics row, both files, best-effort.
- **Exports**:
  - `append_item_row(autopilot_dir, row)` - reuses `record_dispatch.append_row` by path import

### Module: skill prose
- **Maps to capability**: Driver, Zero-context roster
- **Responsibility**: the procedure the operator's session follows; every command line copyable.
- **Exports**: `SKILL.md`, `references/spec-card.md`, `references/lane-dispatch.md`

## Dependency Graph

### Foundation Layer (Phase 0)
No dependencies - built first.

- **card**: the card contract and its errors.
- **plan**: lane order, verify targets, exit rule, ledger counts.
- **record-item**: the metrics row.

### Core Layer (Phase 1)
- **skill prose**: Depends on [card, plan, record-item] - every command it names must exist.

### Integration Layer (Phase 2)
- **README, CHANGELOG, release-checks**: Depends on [skill prose].

## Implementation Phases

### Phase 0: Foundation
**Goal**: the deterministic parts exist and are pinned before any prose names them.

**Tasks**:
- [ ] Write `scripts/card.py` and `scripts/test_card.py` (no deps) - Acceptance: `test_missing_section_names_the_field`, `test_unknown_model_exits_two`, `test_chained_gate_line_is_refused`, `test_empty_tests_section_requires_framework_and_sample` pass; `python3 skills/fast-track/scripts/card.py <fixture>` prints the parsed card as JSON.
- [ ] Write `scripts/fast_track_plan.py` and `scripts/test_fast_track_plan.py` with fixture ledgers under `scripts/fixtures/` (no deps) - Acceptance: `test_clean_item_dispatches_one_ivan_and_the_roster_and_no_rework`, `test_one_confirmed_high_dispatches_two_ivans_one_victor_and_one_delta`, `test_surviving_critical_leaves_master_untouched` (`exit_action == "branch"`), `test_workflow_absent_dispatches_legacy_alice`, `test_carl_skipped_when_no_backend`, `test_workflow_findings_are_not_re_verified` pass.
- [ ] Write `scripts/record_item.py` and `scripts/test_record_item.py` (no deps) - Acceptance: `test_item_row_lands_in_both_ledgers_with_phase_fast_track`, `test_cost_is_null_unless_passed`, `test_failed_write_exits_zero_and_says_so` pass.

**Exit Criteria**: `python -m pytest -q skills/fast-track/scripts` passes.

### Phase 1: Core
**Goal**: the lane is followable from one skill file.

**Tasks**:
- [ ] Write `skills/fast-track/SKILL.md` (frontmatter `name: fast-track`, trigger-led description; sections: Preconditions, Card, Tests, Implement, Gates, Roster, Verify, Rework, Delta, Exit, Ledgers, Report) and `scripts/test_fast_track_prose.py` in the style of `skills/work/scripts/test_dispatch_telemetry_prose.py:1-11` (depends on: Phase 0) - Acceptance: `test_skill_names_the_invocation_form` (`/autopilot:fast-track <card.md>`), `test_every_lens_is_dispatched_in_one_message` (`autopilot:blake`, `autopilot:eve`, `codex-run.sh`, `gemini-run.sh`, `review-fanout.workflow.js`, `autopilot:alice`), `test_cli_reviewers_run_as_background_bash_never_inside_a_subagent` (`run_in_background: true` and `never inside a subagent`), `test_blake_receives_the_card_never_the_diff`, `test_ivan_is_fresh_on_rework_and_capped_at_one_rework`, `test_exit_rule_branches_and_resets_with_keep` (`fast-track/<item>` and `git reset --keep`), `test_headless_sessions_are_refused` (`_AUTOPILOT_LOOP`), `test_every_dispatch_opens_a_ledger_row` (`record_dispatch.py start --kind fast-track:` count >= 8), `test_no_per_task_ceremony` (none of `Devon`, `deslop`, `Pat`, `plan-tasks`, `design-solution` in the body) pass.
- [ ] Write `references/spec-card.md` (the format, one full example card, the empty-`## Tests` rule) and `references/lane-dispatch.md` (one command block per lane, victor's render, Eve's sixth input, the record_item call) (depends on: task 1 of this phase) - Acceptance: `test_reference_card_example_loads` (`load_card` on the example extracted from the reference) and `test_lane_reference_names_every_kind` (the eight `fast-track:` kinds) pass.

**Exit Criteria**: `python -m pytest -q skills/fast-track/scripts` passes with the prose pins.

### Phase 2: Integration
**Goal**: the pack knows the skill exists and the release gate runs its suite.

**Tasks**:
- [ ] Add the `fast-track` row to the README skills table and bump the count. Premise: `README.md:13` reads `Ten skills:` and the table at `:15-24` has no `fast-track` row; re-check with `rg -n 'Ten skills|fast-track' README.md`, skip and report if either fails (depends on: Phase 1) - Acceptance: `rg -c 'fast-track' README.md` reports at least 1 and `rg -n 'Ten skills' README.md` prints nothing.
- [ ] Add a `[checks] fast-track lane` block to `dev/bin/release-checks` running `uv run --no-project --with pytest python -m pytest -q skills/fast-track/scripts`. Premise: the file still has exactly three `echo "[checks] ...` lines at `:11,16,20`; re-check with `rg -c '^echo "\[checks\]' dev/bin/release-checks` = 3, skip and report otherwise (depends on: Phase 1) - Acceptance: `rg -n 'fast-track' dev/bin/release-checks` prints one line; `bash dev/bin/release-checks` exits 0.
- [ ] Add one `### Added` line `**fast-track**: ...` under `[Unreleased]` in `CHANGELOG.md`. Premise: `CHANGELOG.md:8` reads `## [Unreleased]`, `:10` reads `### Added` and `:20` reads `## [0.5.1] - 2026-09-05`; re-check with `rg -n '^## \[Unreleased\]|^### Added|^## \[0.5.1\]' CHANGELOG.md`, skip and report if any line moved (depends on: Phase 1) - Acceptance: `rg -n '^\- \*\*fast-track\*\*' CHANGELOG.md` prints one line above the `## [0.5.1]` heading.

**Exit Criteria**: `bash dev/bin/release-checks` passes.

## Test Strategy

### Critical Scenarios
- **Happy path**: card with tests present, workflow file present, Gemini resolves; Ivan passes, gates green, roster returns no CRITICAL/HIGH → Expected: `plan_lanes` yields ivan + fanout + blake + eve + bob + carl, `exit_action([]) == "commit"`, one `phase_launched: "fast-track"` row with `rework: 0`, the commits stay on the branch.
- **Edge case**: Blake alone raises one HIGH; victor confirms; the fresh Ivan reworks; the delta review reports it resolved → Expected: 2 ivan, 1 victor, 1 delta, `outcome: committed`, `rework: 1`. Workflow file absent → `fast-track:alice` replaces `fast-track:fanout`, roster count unchanged.
- **Error case**: a CRITICAL survives the delta review → Expected: `exit_action == "branch"`, `fast-track/<item>` holds the commits, `HEAD == <base>` on the current branch, the report names the finding; a gate fails after Ivan → no reviewer dispatched, `outcome: stopped`, commits left in place and reported as unreviewed.

## Risks

- **The driver leaks its own context into a prompt**: every prompt is rendered from the card, the diff and persona files by `render_prompt.py` or the workflow; `test_fast_track_prose.py` pins the rule `no session context` and the prose never lets the operator paste findings by hand.
- **`git reset --keep` refuses on an overlap with foreign work**: the item's commits stay on the current branch, the report says `branch: refused (<paths>)` and the item ends `stopped: reset-refused`; nothing is force-reset.
- **A card asks for too much**: a `## Files` list over 12 entries or a `## Goal` over 40 lines is refused by `load_card` with `card too large for the lane; write a PRD` (the assessment's plan-time size gate, `/Users/bob/git/src/github.com/doogat/ddb/dev/local/audit-results/refactor-assessment-2026-09-06.md:157`), so the lane never replaces the loop for large PRDs (decision 7).
- **Bob refuses to read again**: the retry-policy amendment and Claude fallback are reused unchanged; a failed Bob after his one retry is reported as a failed lane, the item is not converged and takes the `branch` exit when any CRITICAL/HIGH is confirmed elsewhere, `commit` otherwise, with `bob: failed` in the report.
