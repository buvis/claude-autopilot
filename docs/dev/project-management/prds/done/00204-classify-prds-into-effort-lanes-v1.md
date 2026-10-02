---
catchup: run
design: skip
default_model: opus
model_tier_rationale: an invented classifier (seven ordered rules, a PRD path extractor, a card-split predicate) whose Verdict and CardPlan shapes PRDs 00205 and 00206 consume; the rules are exact below but the extraction edge cases are judgment, not transcription
rework_cap: 3
---

# Classify PRDs into effort lanes

Source: `dev/local/discovery/00203-route-prds-by-effort-lane.md` (PRD A of
three; elicited 2026-09-13). Grounded 2026-09-14 at HEAD `70b606e`. Lands
after backlog PRDs 00200 (owns `frontmatter.py` and `routing.py`), 00189
(owns the Repository Structure walk in `policy.prd_modules`), 00188 (owns
`_append_metrics`' convergence branch) and 00198 (owns the citation-suffix
regex). This PRD ships the classifier in SHADOW: every PRD is classified,
recorded and rendered, and every PRD still runs the full loop. PRDs 00205
(solo lane) and 00206 (fast-track lane) each release one lane.

## Overview

### Problem Statement

Every PRD enters the same loop. One opus task in the full pipeline costs
~200 tool calls, 60-80 minutes and $50-70, of which the implementation is
5-10 minutes (`dev/local/notes/autoclaude-inefficiencies-2026-09-13.md:5-14`).
That pipeline earns its cost on cross-cutting, algorithmic or
security-sensitive PRDs; for prose edits, one-file fixes and test scaffolding
it is a 5-10x tax over a solo session plus one review pass (`:22-24`). Phase 0
parses seven frontmatter keys today (`cli/frontmatter.py:40-58`; 00189 and
00200 add one each) and none chooses a lane; `routing.route` (`cli/routing.py:212-256`) picks a model and an effort
per phase, never a pipeline. The pack has the middle lane (`fast-track`, PRD
00186) and a precedent for the cheapest one (the review micro lane,
`skills/work/references/rework-mode.md:16`), but nothing decides which PRD
takes which.

### Target Users

The loop operator paying per session, and the two follow-on PRDs that need
`state.lane` to exist before Phase 1.

### Success Metrics

- `uv run --no-project --with pytest --with rich --with textual python -m pytest -q skills/run-autopilot`
  green with every test named under Implementation Phases present.
- `cli/test_frontmatter.py` unchanged and `frontmatter.MALFORMED_WARNING`
  byte-identical (`rg -c 'consensus_engine=legacy"' skills/run-autopilot/cli/frontmatter.py`
  prints 1, as today).
- `bash dev/bin/release-checks` green with a new `[checks] effort lanes` block.
- Post-release signals, not judged in-session: the next batch's report prints
  a `- Lane:` line on every completed PRD and a `- PRDs by lane:` summary;
  every session row in `loop-metrics.jsonl` carries `lane`.

## Functional Decomposition

### Capability: Lane classification
A pure, stdlib-only module `cli/lane.py` that reads PRD text and the flat
frontmatter pairs and answers one question: which lane.

#### Feature: Named-path extraction
- **Description**: `named_paths(text) -> tuple[str, ...]` lists the
  repo-relative file paths a PRD names, in first-appearance order, deduplicated.
- **Inputs**: the PRD text.
- **Outputs**: the tuple; empty when the PRD names no path.
- **Behavior**: two sources, unioned in document order. (1) The first fenced
  code block after a `### Repository Structure` heading: per line, drop
  everything from the first ` #` on; a line with no glyph prefix is a root
  entry; a glyph line's depth is the count of 4-character columns (`├── `,
  `└── `, `│   `, `    `) before its name and it belongs to the nearest
  preceding directory entry at a lesser depth (the walk PRD 00189 gives
  `policy.prd_modules`); a name ending in `/` is a directory and is never a
  named path; a line holding `, ` splits into siblings, and a sibling without
  a `/` takes the directory of the item before it on that line
  (`references/phase-build.md, phase-review.md` yields two paths under
  `references/`). (2) Every backticked span on a line matching
  `^\s*-\s+\*\*Location\*\*:`. On every candidate from either source, strip a
  trailing `:N` or `:N-M` (`:\d+(?:-\d+)?$`, the form PRD 00198's
  `normalize_file` strips), then keep it only when it matches `^[\w./*-]+$`
  and contains `.` or `/` (so `_add_check_plan` and `render_brief()` are not
  paths, `dev/bin/release-checks` and `CHANGELOG.md` are). A glob such as
  `agents/*.md` is a named path (one entry) for classification; only
  `plan_cards` refuses it. On the frozen 00189 this yields 11 paths, on 00188
  16, on 00200 11, on 00201 10 (the discovery's counts).

#### Feature: Path kinds
- **Description**: `is_hook_path(path)`, `is_production_path(path)` and
  `securityish(text)` decide what a named path is.
- **Inputs**: one repo-relative path, or one string for `securityish`.
- **Outputs**: booleans.
- **Behavior**: hook = any directory segment equal to `hooks`, or basename
  `hooks.json`, or basename matching `*_hook.py`. Production = not
  `is_test_path` (loaded by path from `skills/work/scripts/work_routing.py`
  exactly as `classify_tier._load_is_test_path` does,
  `skills/plan-tasks/scripts/classify_tier.py:19-28`), not a doc (suffix
  `.md`, `.txt`, `.rst`), not `is_packaging_path` (loaded by path from
  `classify_tier.py`; its module-level `_load_is_test_path()` resolves
  through `__file__` and works under `spec_from_file_location`). Neither
  predicate is copied: `rg -c '_TEST_DIR_SEGMENTS|_PACKAGING_BASENAMES' skills/run-autopilot/cli/lane.py`
  prints 0. `SECURITY_RE` is the regex of
  `~/.claude/workflows/review-fanout.workflow.js:41-42` ported verbatim to
  `re` (Python supports its lookbehind and lookahead unchanged);
  `securityish` camel-splits (`re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", s)`),
  lowercases, then searches, the `:147-154` function.

#### Feature: Card plan
- **Description**: `plan_cards(text) -> list[CardPlan]` is the one owner of
  the card split; `CardPlan(phase, files, goal_lines, task_items)` is a frozen
  dataclass; PRD 00206's renderer imports it by path and only renders.
- **Inputs**: the PRD text.
- **Outputs**: one whole-PRD plan, two phase plans, or `[]` (uncardable).
- **Behavior**: terms first. A task item is a line matching `^- \[[ x]\] `
  joined with its following lines that start with two or more spaces into ONE
  line (single spaces), before any count. A phase is a `^### Phase \d+:`
  heading under `## Tasks` or `## Implementation Phases`, holding the task
  items up to the next `### ` or `## ` heading; the `(Phase N)` suffix of a
  `## Dependency Graph` layer heading never matches. The problem text is the
  body under `### Problem Statement` (standard template) or `## Problem`
  (minimal template), up to the next heading, stripped; the goal of a card is
  that text followed by one line per task item. `files` come from
  `named_paths`; any named path containing `*` makes the plan empty, because
  fast-track's allowlist is literal (`skills/fast-track/SKILL.md:116`,
  `:165-166` pass every `## Files` entry to `--require-file` or
  `--require-parent`). Then, in order: when every named path fits 12 and the
  whole-PRD goal fits 40 lines (`card.py:22-23`), one plan with
  `phase=None`, all named paths, every task item. Else, when there are
  exactly two phases, one plan per phase: its files are the named paths
  whose basename (with extension) occurs in that phase's joined task text,
  plus every named path whose basename occurs in no phase's task text (a
  file no task names must still be writable, so it goes to every card); its
  goal is the problem text plus its own items; both plans must fit both
  limits. Else `[]`. On the frozen 00188 the second card holds
  `render_report.py` (named by no task) and at most 12 files.

#### Feature: Classify
- **Description**: `classify(text, declared) -> Verdict` with
  `Verdict(lane, reason, paths, prod_paths, cards)`, a frozen dataclass.
- **Inputs**: the PRD text; `declared`, the flat frontmatter pairs from
  `frontmatter.declared(text)`.
- **Outputs**: `lane` in `solo | fast-track | full`; `reason` names the first
  rule that matched; `paths` and `prod_paths` are tuples; `cards` is
  `len(plan_cards(text))`.
- **Behavior**: rules checked in order, first match wins (the
  `classify_tier._tier_from_shape` shape, `classify_tier.py:113-135`):

  | # | rule | lane | `reason` |
  |---|---|---|---|
  | 0 | `declared.get("lane")` is `solo`, `fast-track` or `full` (any other value is treated as absent; the verb warns) | as written | `override` |
  | 1 | any named path is a hook | full | `hook` |
  | 2 | any named path is `securityish` | full | `security_path` |
  | 3 | no named path at all | full | `unparsed` |
  | 4 | `declared.get("design")` is not exactly `skip` (absent or invalid counts as `run`, `frontmatter.py:42`) | full | `design` |
  | 5 | no named path is a production path | solo | `no_production_code` |
  | 6 | `plan_cards(text)` is non-empty | fast-track | `card_sized` |
  | 7 | otherwise | full | `uncardable` |

  `default_model` never decides the lane. `effective(lane, lanes_env) -> str`
  returns `full` when `lanes_env == "off"` or `lane not in RELEASED_LANES`,
  else `lane`; `RELEASED_LANES = frozenset({"full"})` in this PRD.

### Capability: Phase 0 routing
The lane exists in state before Phase 1, written by the verb that already
parses the frontmatter.

#### Feature: `frontmatter.declared`
- **Description**: `declared(text) -> dict[str, str]` wraps `_block` and
  `_pairs` (`frontmatter.py:74-94`) so callers see the flat pairs under the
  same `_HEAD_LINES` window and nothing else.
- **Inputs**: the PRD text.
- **Outputs**: the pairs; `{}` on a malformed or absent block.
- **Behavior**: `parse` is unchanged in signature and result.

#### Feature: The `frontmatter` verb classifies
- **Description**: `_run_frontmatter` (`cli/__main__.py:501-542`) runs
  `lane.classify` on the text it already read and the pairs
  `frontmatter.declared` returns, and writes `lane`, `lane_reason` and
  `lane_effective` in its one transaction (`:524`), echoing them with the
  other fields (`:541`).
- **Inputs**: the PRD text; `os.environ.get("_AUTOPILOT_LANES")` (the CLI's
  env idiom, `cli/records.py:188`); this verb is the one reader of that knob.
- **Outputs**: the three state fields; one stderr line
  `autopilot: PRD frontmatter lane=<value!r> is not one of solo/fast-track/full; defaulting to <classified lane>`
  when `lane:` carries an invalid value (the enum disposition,
  `frontmatter.py:14-21`); silence when the key is absent.
- **Behavior**: `MALFORMED_WARNING` unchanged. `cli/schema.py` `_ENUMS`
  (`:42-49`) gains `"lane"` and `"lane_effective"`, each
  `{"solo", "fast-track", "full"}`; `lane_reason` is free text. The three
  fields are re-derived per PRD at Phase 0 and therefore NOT added to
  `records.PER_PRD_RESET_FIELDS` (`records.py:69-92`); the "NOT reset here"
  comment (`:98`) names them beside `doubt_reviewer`.

#### Feature: Step 5.5 in the build gate
- **Description**: `references/phase-build.md` gains `### 5.5. Route by lane`
  between the frontmatter parse (`:88-130`) and Phase 1 (`:132`).
- **Inputs**: `state.lane`, `state.lane_reason`, `state.lane_effective`.
- **Outputs**: prose.
- **Behavior**: the section reads, verbatim: `Read state.lane_effective,
  which step 5 wrote beside state.lane and state.lane_reason (cli/lane.py
  decides; three lanes: solo, fast-track, full). When it differs from
  state.lane, print` the banner
  `── AUTOPILOT ── lane: <lane> (<reason>), running full ──`
  `. full continues to Phase 1. Shadow: in this release lane.RELEASED_LANES
  holds full only, so every PRD continues to Phase 1; the lane is recorded
  in the session rows and the batch report and acted on by nothing.
  _AUTOPILOT_LANES=off in the loop environment forces full for every PRD.`
  (Backticks around the identifiers as the file's style has them.)

### Capability: Lane telemetry
The lane is measurable before any lane is live.

#### Feature: Session row fields
- **Description**: every `loop-metrics.jsonl` session row carries `lane` and
  `lane_effective`.
- **Inputs**: `state.json` as `loop._decide` already loads it (`cli/loop.py:739-744`,
  or the sibling module PRD 00192 extracted `_decide` to; 00192 lands first
  and moves the session/metrics and decision code out of `loop.py`).
- **Outputs**: two keys in the row `_append_metrics` builds (`:907-918`, or
  its 00192 sibling), `null` when the state lacks them.
- **Behavior**: `_decide` copies `state.get("lane")` and
  `state.get("lane_effective")` into `decision` (initialised to `None` in the
  dict at `:713-721`); `_append_metrics` writes both inside its existing
  `try`. PRD 00188's convergence branch in the same function is untouched.

#### Feature: Completed-PRD record fields
- **Description**: `statectl._completed_prd_record` (`cli/statectl.py:348-375`)
  adds `lane`, `lane_effective` and `lane_escalated`.
- **Inputs**: the closing state dict.
- **Outputs**: the three keys, copied verbatim, `null` when absent.
- **Behavior**: not added to `schema._COMPLETED_PRD_ENTRY_FIELDS` (`:69-76`),
  which rejects a present `null`; unknown entry fields pass.

#### Feature: Report lines
- **Description**: `render_report.prd_section` (`cli/render_report.py:509`)
  prints `- Lane: <lane_effective> (classified <lane>, <reason>)` after
  `- Tasks:` (`:539`); `batch_summary` (`:580`) prints
  `- PRDs by lane: solo N, fast-track N, full N; escalated N` after
  `- PRDs skipped:` (`:603`).
- **Inputs**: `state` (fields present until the next Phase 0 overwrites
  them) else the matching `completed_prds` record, the way `cycles` falls
  back (`:531-533`); the batch's records for the summary.
- **Outputs**: the two lines. With a record carrying `lane_escalated`
  (`{"from": ..., "signal": ...}`, written by PRD 00205) the section line
  ends `, escalated from <from>: <signal>`. When neither state nor record
  carries `lane`, the line is `- Lane: unclassified`. Records without
  `lane_effective` (bare strings, pre-lane dicts) count as
  `; unclassified N`, appended only when N > 0.
- **Behavior**: `cli/golden/state-render.json` gains
  `"lane": "full", "lane_reason": "design", "lane_effective": "full"`;
  `cli/golden/expected/report-section.md` gains the line after `- Tasks: 3/3`
  (line 6 today; PRD 00188 also inserts its `- Run conditions:` line there,
  so the `Lane:` line lands after `Run conditions` when that line exists);
  `report-summary.md` gains
  `- PRDs by lane: solo 0, fast-track 0, full 0; escalated 0; unclassified 2`
  after `- PRDs skipped: 0` (its two records are bare strings).

### Capability: Fixture and documentation
The reviewed backlog is the classifier's regression set.

#### Feature: Frozen backlog fixture
- **Description**: the 15 PRDs 00187-00202 (00193 is a discovery, not a PRD)
  are copied verbatim into `cli/golden/lanes/` and
  `cli/test_lane.py::test_reviewed_backlog_classifies_as_agreed` asserts the
  table below per file.
- **Inputs**: the files as they stand in `dev/local/prds/` at implementation
  time (`wip/`, `backlog/` or `done/`, wherever each is).
- **Outputs**: the copies and the test.
- **Behavior**: the expected table. The rules above are the contract and the
  table is their output on the frozen texts; a row the rules contradict on a
  frozen file is corrected to what the rules compute and the discrepancy is
  named in the task report, never the rule bent to the row.

  | PRD | lane | reason | cards |
  |---|---|---|---|
  | 00187 | full | hook | 0 |
  | 00188 | fast-track | card_sized | 2 |
  | 00189 | fast-track | card_sized | 1 |
  | 00190 | fast-track | card_sized | 1 |
  | 00191 | full | hook | 0 |
  | 00192 | full | design | 0 |
  | 00194 | full | design | 0 |
  | 00195 | full | design | 0 |
  | 00196 | full | hook | 0 |
  | 00197 | solo | no_production_code | 0 |
  | 00198 | full | uncardable | 0 |
  | 00199 | full | design | 0 |
  | 00200 | full | hook | 0 |
  | 00201 | fast-track | card_sized | 1 |
  | 00202 | full | hook | 0 |

  Ten full, four fast-track, one solo. The discovery placed 00198 in
  fast-track; it names `agents/*.md`, and a glob cannot be a fast-track
  allowlist entry, so it is `uncardable` here (its `lane: fast-track`
  override would be refused by PRD 00206's renderer for the same reason; the
  remedy is naming the fourteen files or running full).

#### Feature: Documentation
- **Description**: `references/state-schema.md` § Field Descriptions gains
  rows for `lane`, `lane_reason` and `lane_effective` beside `doubt_reviewer`
  (`:175`); `references/batch-report-format.md` § What a completed-PRD
  section carries (`:39`) documents the `Lane:` line and § What the batch
  summary carries (`:25`) the `PRDs by lane:` line; CHANGELOG `### Added`
  under `**run-autopilot**`.
- **Inputs**: none.
- **Outputs**: prose.
- **Behavior**: each row names the writer (the `frontmatter` verb), the
  values, the shadow rule and the `_AUTOPILOT_LANES=off` switch.

## Structural Decomposition

### Repository Structure

```
skills/run-autopilot/
├── cli/
│   ├── lane.py                      # Maps to: Lane classification (new, stdlib only)
│   ├── frontmatter.py               # Maps to: frontmatter.declared
│   ├── __main__.py                  # Maps to: the frontmatter verb classifies
│   ├── schema.py                    # Maps to: lane enums
│   ├── records.py                   # Maps to: the NOT-reset comment
│   ├── loop.py                      # Maps to: session row fields (or the 00192 sibling holding _decide/_append_metrics)
│   ├── statectl.py                  # Maps to: completed-PRD record fields
│   ├── render_report.py             # Maps to: report lines
│   ├── test_lane.py                 # new: classifier, card plan, fixture table
│   ├── test_lane_cli.py             # new: the verb as a subprocess
│   ├── test_loop.py, test_render.py, test_schema.py
│   └── golden/
│       ├── lanes/                   # new: the 15 frozen PRDs
│       ├── state-render.json
│       └── expected/report-section.md, report-summary.md
├── scripts/
│   ├── test_statectl_complete_prd.py
│   └── test_lane_prose.py           # new: step 5.5 pin
└── references/
    ├── phase-build.md               # Maps to: step 5.5
    ├── state-schema.md
    └── batch-report-format.md
dev/bin/release-checks               # [checks] effort lanes
CHANGELOG.md
```

### Module: lane
- **Maps to capability**: Lane classification
- **Responsibility**: the path extraction, the kinds, the card split and the
  seven rules; no disk, no state, no git
- **Exports**: `named_paths(text)`, `is_hook_path(path)`,
  `is_production_path(path)`, `SECURITY_RE`, `securityish(text)`,
  `CardPlan`, `plan_cards(text)`, `Verdict`, `classify(text, declared)`,
  `RELEASED_LANES`, `effective(lane, lanes_env)`

### Module: frontmatter + verb + schema
- **Maps to capability**: Phase 0 routing
- **Responsibility**: expose the pairs; write and validate the three fields
- **Exports**: `frontmatter.declared(text)`; the `frontmatter` subcommand
  (unchanged flags); `schema._ENUMS["lane"]`, `["lane_effective"]`

### Module: telemetry (loop, statectl, render_report)
- **Maps to capability**: Lane telemetry
- **Responsibility**: carry the fields into the session row, the record and
  the report
- **Exports**: `_append_metrics(...)` unchanged signature;
  `_completed_prd_record(data)`; `prd_section(...)` and `batch_summary(...)`
  unchanged signatures

### Module: fixture and prose
- **Maps to capability**: Fixture and documentation
- **Responsibility**: the frozen set, the pins, the docs
- **Exports**: none

## Dependency Graph

### Foundation Layer (Phase 0)
No dependencies - built first.

- **lane**: loads `is_test_path` and `is_packaging_path` by path; everything
  else is stdlib.
- **frontmatter.declared**: a two-line wrapper.

### Core Layer (Phase 1)
- **frontmatter verb + schema**: Depends on [lane, frontmatter.declared].
- **telemetry**: Depends on [frontmatter verb] (reads the fields it writes).

### Integration Layer (Phase 2)
- **fixture and prose**: Depends on [lane, telemetry].

## Implementation Phases

### Phase 0: Foundation
**Goal**: the classifier exists and reproduces the reviewed backlog.

**Tasks**:
- [ ] Write `cli/lane.py` with every export above, and `frontmatter.declared`
  (no deps) - Premise: `frontmatter.py:74` defines `_block` and `:85`
  `_pairs`, `_HEAD_LINES` is 22 (`:36`); re-check with
  `rg -n '^_HEAD_LINES|^def _block|^def _pairs' skills/run-autopilot/cli/frontmatter.py`
  (three hits) and skip with a report on a mismatch - Acceptance:
  `uv run --no-project --with pytest python -m pytest -q skills/run-autopilot/cli/test_lane.py`
  passes with `test_named_paths_rebuilds_tree_glyphs_and_splits_commas`
  (the frozen 00201 yields its 10 paths, `phase-review.md` under
  `references/`), `test_named_paths_reads_location_spans_and_skips_symbols`
  (the frozen 00189 yields 11, none named `_add_check_plan`),
  `test_line_suffix_is_stripped_before_kind` (`cli/__main__.py:756-782`
  becomes `cli/__main__.py`), `test_hook_basename_forms` (`hooks/x.py`,
  `hooks.json`, `foo_hook.py`; `hookshelf/x.py` is not a hook),
  `test_predicates_are_loaded_by_path_not_copied`
  (`lane.is_test_path.__module__ == "work_routing"`, and the `rg -c` above
  prints 0), `test_security_regex_fires_on_a_path_not_on_prose`
  (`auth/login.py` fires; a PRD titled `Session brief` whose paths are
  `cli/brief.py` classifies without `security_path`), `test_override_wins`,
  `test_invalid_override_is_ignored_by_classify`, one test per remaining
  reason slug (`hook`, `security_path`, `unparsed`, `design`,
  `no_production_code`, `card_sized`, `uncardable`),
  `test_design_absent_counts_as_run`,
  `test_plan_cards_joins_wrapped_task_items_before_counting`,
  `test_plan_cards_ignores_dependency_graph_phase_suffixes`,
  `test_plan_cards_gives_unnamed_files_to_every_card`,
  `test_plan_cards_refuses_a_glob_path`,
  `test_plan_cards_refuses_three_phases_over_twelve_paths`,
  `test_effective_forces_full_when_off_or_unreleased` (the switch case
  passes `lanes_env == "off"`; the unreleased case monkeypatches
  `lane.RELEASED_LANES` to `frozenset({"full"})` so the test stays true
  after PRDs 00205 and 00206 release lanes), and
  `test_declared_returns_pairs_or_empty` in `cli/test_frontmatter.py`'s
  style; `cli/test_frontmatter.py` passes unchanged.
- [ ] Freeze the 15 reviewed PRDs under `cli/golden/lanes/` and add
  `test_reviewed_backlog_classifies_as_agreed` (depends on: lane) -
  Premise: each of 00187-00202 except 00193 exists under `dev/local/prds/`;
  re-check with `rg --files dev/local/prds -g '00187-*' -g '00188-*' ... -g '00202-*'`
  (15 hits) and skip with a report naming any missing file - Acceptance:
  the test asserts `(lane, reason, cards)` for all 15 rows of the table
  above; `rg --files skills/run-autopilot/cli/golden/lanes` lists 15 files.

**Exit Criteria**: `pytest -q skills/run-autopilot/cli/test_lane.py` green.

### Phase 1: Core
**Goal**: the verb writes the lane; the ledgers and the report carry it.

**Tasks**:
- [ ] The `frontmatter` verb classifies and writes the three fields; schema
  enums; the `records.py:98` comment (depends on: Phase 0) - Premise:
  `_run_frontmatter` writes `fields` in one `state.transaction` at
  `__main__.py:524` and echoes at `:541`; re-check with
  `rg -n 'state.transaction\(|print\(json.dumps\(fields' skills/run-autopilot/cli/__main__.py`
  and skip with a report on a mismatch - Acceptance:
  `uv run --no-project --with pytest python -m pytest -q skills/run-autopilot/cli/test_lane_cli.py`
  passes, driving this checkout's `cli/__main__.py` with `sys.executable`
  over a temp state (the `test_render_cli.py:63-68` idiom) with
  `test_frontmatter_verb_echoes_lane_fields` (a solo-shaped PRD echoes
  `lane: solo`, `lane_reason: no_production_code`, `lane_effective: full`,
  and `state.json` carries all three),
  `test_frontmatter_verb_forces_full_under_lanes_off`
  (`_AUTOPILOT_LANES=off` in the subprocess env; `lane` still `solo`),
  `test_invalid_override_warns_and_classifies` (stderr holds the one line
  above, `lane` is the classified value),
  `test_absent_lane_key_is_silent` (stderr empty for a well-formed PRD),
  `test_malformed_warning_is_byte_identical` (a malformed block prints
  exactly `frontmatter.MALFORMED_WARNING` and writes `lane`); and
  `cli/test_schema.py::test_lane_enums_are_validated` rejects
  `lane: "fast"` and accepts the three values;
  `rg -n 'lane' skills/run-autopilot/cli/records.py` shows the comment line
  and no entry in `PER_PRD_RESET_FIELDS`.
- [ ] Session row, completed-PRD record and report lines, with the goldens
  (depends on: Phase 0) - Premise: `_append_metrics` builds its row in
  `cli/loop.py` or the sibling PRD 00192 extracted it to, and PRD 00188's
  branch is present; re-check with
  `rg -n 'review_converged' skills/run-autopilot/cli/loop*.py` (1 or more
  hits) and `rg -n '^- Tasks: 3/3' skills/run-autopilot/cli/golden/expected/report-section.md`
  (one hit) and skip with a report on a mismatch - Acceptance:
  `cli/test_loop.py::test_session_row_carries_lane_fields` (a step writing
  `lane`/`lane_effective` yields a row carrying both, in primary and
  mirror) and `::test_session_row_lane_is_null_without_state_fields`;
  `scripts/test_statectl_complete_prd.py::test_completed_prd_record_carries_lane_fields`
  (present values copied; absent renders `null`);
  `cli/test_render.py::test_report_section_matches_golden` against the
  updated golden, `::test_lane_line_reads_from_the_record_after_reset`,
  `::test_lane_line_names_the_escalation`,
  `::test_unclassified_lane_renders_loud`,
  `::test_batch_summary_counts_prds_by_lane` (two full, one solo, one
  escalated, one bare string); `test_metrics_line_lands_in_primary_and_ledger_mirror`
  and `test_one_metrics_line_per_session` still pass.

**Exit Criteria**: `pytest -q skills/run-autopilot/cli` green.

### Phase 2: Integration
**Goal**: the build gate and the docs say what the code does.

**Tasks**:
- [ ] Step 5.5 in `references/phase-build.md`, the three `state-schema.md`
  rows, the two `batch-report-format.md` bullets, and
  `scripts/test_lane_prose.py` (depends on: Phase 1) - Premise:
  `phase-build.md` holds the headings `### Frontmatter parse (step 5)` and,
  after it, `## Phase 1: Catchup` (their line numbers move as earlier PRDs
  land); re-check with
  `rg -n '^## Phase 1: Catchup|^### Frontmatter parse' skills/run-autopilot/references/phase-build.md`
  (two hits, the frontmatter one first) and skip with a report on a
  mismatch - Acceptance:
  `uv run --no-project --with pytest python -m pytest -q skills/run-autopilot/scripts/test_lane_prose.py`
  passes with `test_step_5_5_names_three_lanes_and_the_shadow_sentence`
  (the section holds `solo`, `fast-track`, `full`, `RELEASED_LANES`,
  `running full` and `_AUTOPILOT_LANES=off`);
  `rg -c 'lane_effective' skills/run-autopilot/references/state-schema.md skills/run-autopilot/references/batch-report-format.md`
  prints 1 or more for each; `cli/test_doc_contract.py` still passes.
- [ ] `[checks] effort lanes` block in `dev/bin/release-checks` running
  `skills/run-autopilot/cli/test_lane.py`, `cli/test_lane_cli.py` and
  `scripts/test_lane_prose.py`; CHANGELOG `### Added` under
  `**run-autopilot**` naming the shadow classification, the `lane:` key and
  the `_AUTOPILOT_LANES=off` switch, and recording that the `create-prd` and
  `review-prd-backlog` skills (agent-skills repo) need the key as a
  follow-up (depends on: all) - Acceptance:
  `rg -c 'effort lanes' dev/bin/release-checks` prints 1;
  `rg -c '_AUTOPILOT_LANES' CHANGELOG.md` prints 1 or more;
  `bash dev/bin/release-checks` passes.

**Exit Criteria**: `bash dev/bin/release-checks` green.

## Test Strategy

### Critical Scenarios
- **Happy path**: the frozen 00197 (three doc paths, `design: skip`)
  classifies `solo`/`no_production_code`; the verb writes
  `lane_effective: full` because `solo` is unreleased.
- **Edge case**: a PRD with `design:` absent and one production path
  classifies `full`/`design`, never `fast-track`.
- **Edge case**: a wrapped task item (`- [ ] Widen ...` plus two indented
  continuation lines) counts as one goal line.
- **Error case**: `lane: fast` in the frontmatter warns once and writes the
  classified lane; `state.json` never carries `fast`.

## Risks

- **A hook path routes a text-only edit to full (00202)**: accepted; the
  `lane:` override is the remedy and the fixture documents it. Softening the
  hook rule would send cap-hook logic edits (00191, 00196, 00200) past the
  loop.
- **`design:` absent means full**: conservative by design; create-prd writes
  the key explicitly, and the shadow batch shows how often it fires.
- **Path extraction misses a hand-written PRD**: `unparsed` routes to full;
  the shadow batch's `Lane:` lines show every such PRD before any lane goes
  live.
- **Three backlog PRDs edit `_append_metrics`, `phase-build.md` and
  `frontmatter.py`**: sequenced (00188, 00189, 00200 first); every task
  above re-checks its premise before editing.

### Deferred

- [Medium] `security_triggered` and its header helpers are dead code in this PRD (Blake, Bob, Carl) - written early for PRD 00205, whose `lane-check` verb calls it and whose tests pin it; it lands with that PRD on this branch
- [Medium] `lanes_line` crashes on a non-hashable `lane_effective` (`[]`/`{}`) in a hand-edited record (Bob) - the write path is schema-validated (`_ENUMS` holds the lane enum), so the value cannot arrive from `statectl`; accepted as a hand-edit-only risk
- [Medium] `test_lane_cli._run` has one caller (Bob) - PRD 00205's `lane-check` and `phase-done` proofs in the same file are its second and third callers
- [Low] `cards` corrected for 8 fixture rows, documented inline only (Blake) - the correction is recorded in the T1 commit message and this review; the PRD sanctions it
- [Low] `test_no_manual_range_flag_or_later_feature_leaks_into_the_skill_prose` passes against base (Alice, Bob) - expected: the exclusion guards fixture data that did not exist at base
- [Low] pre-existing size debt in `records.py` and `__main__.py` (Bob) - untouched functions, out of scope
- [Low] Bob's VERIFY on the suite and release checks - answered in the review (2022 passed, release-checks exit 0)
