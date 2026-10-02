---
catchup: run
design: skip
default_model: opus
model_tier_rationale: a mechanical card renderer with twelve derivation rules and a refusal contract that every produced card must satisfy, plus the one precondition change that lets fast-track's background reviewers survive a headless turn; the roster, verify, rework and exit sections must stay byte-identical
---

# Render fast-track cards from a PRD and run the lane in the loop

Source: `dev/local/discovery/00203-route-prds-by-effort-lane.md` (PRD C of
three; elicited 2026-09-13). Grounded 2026-09-14 at HEAD `70b606e`. Lands
after 00204 (the classifier and `lane.plan_cards`) and 00205 (the
`lane_reviewed` transition this lane closes with). Releases the `fast-track`
lane: `lane.RELEASED_LANES` gains `fast-track`, so a card-sized PRD runs the
existing fast-track lane per card inside an autoclaude batch.

## Overview

### Problem Statement

Fast-track (PRD 00186) runs a spec card through five review lenses without
the loop's phases, but it refuses a headless session outright
(`skills/fast-track/SKILL.md:27-31`, pinned by
`scripts/test_fast_track_prose.py:438`), because two lenses live in
background Bash, which `claude -p` kills about five seconds after the turn
ends. The review phase already solves that with a Watcher subagent
(`skills/review-work-completion/SKILL.md:270-274`, run-autopilot
`SKILL.md:174`). And nothing produces a card from a PRD: the lane takes
hand-written cards only. After 00204 the classifier records `fast-track` for
card-sized PRDs and still runs them full; the measured cost sits in
unattended batches, so a lane that only runs attended never fires where it
pays.

### Target Users

The loop operator paying per session, and a card-sized PRD (at most two
cards of at most 12 paths each) that the full loop over-serves.

### Success Metrics

- `uv run --no-project --with pytest python -m pytest -q skills/fast-track/scripts`
  green with every test named under Implementation Phases present and every
  other pin of `test_fast_track_prose.py` unchanged.
- `uv run --no-project --with pytest --with rich --with textual python -m pytest -q skills/run-autopilot`
  green.
- `bash dev/bin/release-checks` green.
- Post-release signal, not judged in-session: the first headless fast-track
  item is the proof; its report names any lane that failed its one retry, as
  fast-track already does.

## Functional Decomposition

### Capability: Cards from a PRD
A script renders what `lane.plan_cards` planned; it decides nothing about
the split.

#### Feature: Render
- **Description**: `skills/fast-track/scripts/cards_from_prd.py <prd> --out <dir>`
  writes one card per `CardPlan` and prints one card path per line.
- **Inputs**: the PRD path; `--out`; the cwd is the repo root (every path
  resolves from it); `lane.py` and `frontmatter.py` loaded by path from
  `Path(__file__).resolve().parents[2] / "run-autopilot" / "cli"` (the
  `classify_tier._load_is_test_path` idiom,
  `skills/plan-tasks/scripts/classify_tier.py:19-28`; both modules have no
  package imports).
- **Outputs**: `<dir>/<item>.md` per card, exit 0; or exit 2 with
  `cards_from_prd.py: <field>: <message>` on stderr (the `card.py:177-181`
  idiom) and no card left in `<dir>`.
- **Behavior**: `plan = lane.plan_cards(text)`; empty → exit 2, field
  `cards`. Cards are numbered from 1 in plan order; every card is rendered,
  written, then loaded back through `card.load_card` (`card.py:121-169`);
  the first `CardError` removes every written card and exits 2 with its
  field. Fields:
  - `item` = `<prd-stem>-c<n>`, lowercased with `_` replaced by `-` so it
    matches `card.py:18`.
  - `model` = the PRD's `default_model` (from `frontmatter.declared`) when
    it is `sonnet` or `opus`, else `sonnet`.
  - `suite` = `per-item` on every card but the last, `batch` on the last.
  - `changelog` = the text of the first task item naming `CHANGELOG.md`,
    else `none` (amended at integration, 2026-09-20: the card gate rejects an
    empty field).
  - `framework` and `sample_test`: only when `## Tests` is empty;
    `framework` = `pytest` when the PRD text names a `test_*.py`, else
    `bash` when it names a `test_*.sh`, else exit 2 `framework`;
    `sample_test` = the first path in the PRD text matching
    `\S+/test_[\w-]+\.(py|sh)`, in order of appearance, that exists on disk;
    none → exit 2 `sample_test`.
  - `## Goal` = the plan's `goal_lines` verbatim.
  - `## Tests` = the `path::test_name` ids in the card's task items whose
    `path` exists on disk, one per line; an id for a file the PRD is about
    to create never lands here, because fast-track reads a non-empty
    `## Tests` as the shipped spec (`SKILL.md:103-105`).
  - `## Files` = the plan's files. Each entry: contains `*` → exit 2
    `files` (a belt-and-braces check; `plan_cards` already refused it); has
    no `/` → must exist at the repo root; otherwise its parent directory
    must exist (a new file in an existing directory is what
    `--require-parent` admits, `SKILL.md:166`). A violation exits 2
    `files: <entry> does not resolve from the repo root`.
  - `## Constraints` = a `Tests to write: <ids>` line naming every
    `path::test_name` id whose file is not on disk (omitted when there is
    none; this section is what Tess reads as acceptance criteria,
    `SKILL.md:112`), then the text of the PRD's `## Constraints`,
    `### Non-Goals`/`## Non-Goals` or `## Risks` section, the first that
    exists; `none` when neither the line nor a section exists.
  - `## Docs` = `CHANGELOG.md` when a task item names it, else `none`.
  - `## Gates` = the backticked commands beginning `uv run `,
    `python -m pytest`, `pytest` or `bash ` found in the card's task items,
    in the `**Exit Criteria**` line of its phase (every phase for a
    whole-PRD card), and in the PRD's `## Success Criteria` section, in
    that order, deduplicated; a command holding `&&`, `;` or `|` is dropped
    with one stderr note; none left → exit 2 `gates`.
  - `## Transport impact` = `none`.

### Capability: The fast-track lane in the loop
`references/lane-fast-track.md`, the procedure Phase 0 step 5.5 follows when
`state.lane_effective == "fast-track"`.

#### Feature: Runbook
- **Description**: render, mirror, run the cards, consolidate, close or
  stall.
- **Inputs**: the PRD in `dev/local/prds/wip/`, `state.json`.
- **Outputs**: per-card commits on the working branch;
  `dev/local/reviews/<prd-stem>-review-1.md`; or a stall.
- **Behavior**, in this order and pinned by prose tests: (1)
  `mkdir -p dev/local/autopilot dev/local/tmp` (fast-track's staging
  precondition, `SKILL.md:40-46`), then
  `python3 ${CLAUDE_PLUGIN_ROOT}/skills/fast-track/scripts/cards_from_prd.py dev/local/prds/wip/<state.prd> --out dev/local/tmp/<prd-stem>-cards`;
  exit 2 writes `lane_effective: "full"` and `lane_reason: "uncardable"`
  with `statectl set` and continues to Phase 1 (the PRD takes the full
  loop, `state.lane` still `fast-track` so the report reads
  `Lane: full (classified fast-track, uncardable)`); (2) mirror one
  `state.tasks` entry per card (`task-add` with `{"name": <item>}`); (3)
  capture `work_start_sha` and `repo_root` per the Phase 3 invariants
  (`SKILL.md:252-256`); (4) for each card in order, `task-start`, then
  invoke `/autopilot:fast-track <card path>` through the Skill tool, one
  run per card, with no `--push` (the loop defers pushes, run-autopilot
  `SKILL.md:213`); the skill runs § Card to § Exit as written and prints
  its own report (invoking it is what resolves the `${CLAUDE_PLUGIN_ROOT}`
  references in its body; never `Read` `skills/fast-track/SKILL.md` as a
  file to follow it by hand); `task-done` on `commit`; (5) after the last
  card, consolidate every card's table into
  `dev/local/reviews/<prd-stem>-review-1.md` in the gate's shape
  (`review-coverage-format.md:9-25`): `head_sha: <HEAD>`, `reviewers:` the
  union of the lenses that ran across the cards (`alice` or `fanout`,
  `blake`, `eve`, `bob`, `carl`), one `## <Name>` section per reviewer
  holding each card's rows from that lens (or its one-line all-clear),
  `Verdict: converged` when no row survived any card else
  `Verdict: N findings`, `Tests: N passed, M failed, K skipped (fast-track batch suite)`
  from the last card's `suite: batch` run, and `codex_rung_guard: not fired`;
  (6) `autopilot phase-done --outcome lane_reviewed` and the Session
  handoff procedure (`SKILL.md:180-196`). A card whose exit rule prints
  `branch` (`SKILL.md:559-574`) stops the runbook:
  `autopilot stall --prd <state.prd> --site fast_track_blocked --detail "fast-track/<item>: <surviving findings>"`
  (the Loop-mode stall procedure, `references/recovery.md:5-37`), leaving
  every earlier card's commits on the working branch, since each passed its
  roster; `fast_track_blocked` joins the site slugs in `recovery.md:39-70`
  and `state-schema.md:436`.

#### Feature: Watcher in loop mode
- **Description**: fast-track's one precondition change: a headless session
  is no longer refused; the roster message carries the Watcher.
- **Inputs**: `_AUTOPILOT_LOOP`.
- **Outputs**: `SKILL.md` § Preconditions and § Roster.
- **Behavior**: the `Attended session` bullet (`SKILL.md:27-30`) becomes
  `Loop session`: when `_AUTOPILOT_LOOP` is set, dispatch the Watcher
  subagent (general-purpose) in the SAME message as the roster, with the
  exact prompt `skills/review-work-completion/SKILL.md:272` gives it,
  against the codex and gemini `-o` output paths of this item, and
  `TaskStop` it once every lane has reported; § Roster gains one sentence
  pointing at that bullet. Premise, stated as such in the task: § Roster
  (`:222-395`), § Verify, § Rework, § Delta and § Exit (`:397-585`) are
  byte-identical before and after, the way 00187 and 00194 state their
  review-roster sentence. `test_headless_sessions_are_refused`
  (`test_fast_track_prose.py:438`) becomes
  `test_headless_sessions_dispatch_the_watcher`.

#### Feature: Step 5.5 fast-track branch and docs
- **Description**: `references/phase-build.md` § 5.5 gains
  `fast-track: read references/lane-fast-track.md and follow it; Phases 1
  to 3 do not run for this PRD unless the runbook falls back to full`;
  `lane.RELEASED_LANES` becomes `frozenset({"full", "solo", "fast-track"})`.
- **Inputs**: none.
- **Outputs**: prose; `state-schema.md` names `fast-track` as a live lane
  and the `fast_track_blocked` site; CHANGELOG `### Changed` under
  `**fast-track**` (loop mode) and `### Added` under `**run-autopilot**`
  (the lane runbook and `cards_from_prd.py`).
- **Behavior**: `test_reviewed_backlog_classifies_as_agreed` still passes;
  `effective("fast-track", None)` returns `fast-track`.

## Structural Decomposition

### Repository Structure

```
skills/
├── fast-track/
│   ├── SKILL.md                             # Maps to: Watcher in loop mode
│   └── scripts/
│       ├── cards_from_prd.py                # Maps to: Render (new)
│       ├── test_cards_from_prd.py           # new
│       ├── test_fast_track_prose.py         # renamed pin
│       └── fixtures/lanes/                  # new: the repaired 00188 and the synthetic 25-path PRD (raw copies are read from 00204's cli/golden/lanes/)
└── run-autopilot/
    ├── cli/lane.py                          # Maps to: RELEASED_LANES
    ├── cli/test_lane.py
    ├── scripts/test_lane_prose.py           # fast-track runbook pins
    └── references/
        ├── lane-fast-track.md               # Maps to: Runbook (new)
        ├── phase-build.md                   # step 5.5 fast-track branch
        ├── recovery.md                      # fast_track_blocked
        └── state-schema.md
CHANGELOG.md
```

### Module: cards_from_prd
- **Maps to capability**: Cards from a PRD
- **Responsibility**: render each `CardPlan` into a card `card.load_card`
  accepts, or refuse naming the field
- **Exports**: `render_cards(prd_path, out_dir, root) -> list[Path]`,
  `main(argv)`

### Module: fast-track SKILL prose
- **Maps to capability**: The fast-track lane in the loop (Watcher)
- **Responsibility**: the one precondition and the roster sentence
- **Exports**: none (pinned by `test_fast_track_prose.py`)

### Module: lane-fast-track runbook + lane
- **Maps to capability**: The fast-track lane in the loop (Runbook, step 5.5)
- **Responsibility**: the loop-side procedure; the lane release
- **Exports**: `lane.RELEASED_LANES`; prose pinned by `test_lane_prose.py`

## Dependency Graph

### Foundation Layer (Phase 0)
No dependencies - built first.

- **cards_from_prd**: reads 00204's `lane.plan_cards` and `frontmatter.declared`
  by path; writes files only under `--out`.

### Core Layer (Phase 1)
- **fast-track SKILL prose (Watcher)**: no code dependency; sequenced after
  the renderer so the lane has cards to run.

### Integration Layer (Phase 2)
- **lane-fast-track runbook + lane release**: Depends on [cards_from_prd,
  fast-track SKILL prose, 00205's `lane_reviewed`].

## Implementation Phases

### Phase 0: Foundation
**Goal**: a PRD becomes cards, or says which field stopped it.

**Tasks**:
- [ ] Write `cards_from_prd.py` and `test_cards_from_prd.py`. The raw
  00188, 00189 and 00201 are read by path from 00204's frozen copies under
  `skills/run-autopilot/cli/golden/lanes/` (one frozen copy per PRD in the
  plugin); two fixtures of this PRD's own live under `scripts/fixtures/lanes/`:
  a repaired 00188 whose seven non-repo-relative paths (`cli/__main__.py`,
  `cli/test_loop.py`, `cli/test_render.py`, `cli/golden/metrics-render.jsonl`,
  `cli/golden/expected/report-section.md`, and the bare `state-schema.md`,
  `batch-report-format.md`) are rewritten under `skills/run-autopilot/`,
  and a synthetic 25-path PRD (no deps) -
  Premise: 00204's `lane.py` exports `plan_cards` and `CardPlan` with
  `task_items`, and 00204's `cli/golden/lanes/` holds the 15 frozen PRDs;
  re-check with
  `rg -n '^def plan_cards|task_items' skills/run-autopilot/cli/lane.py`
  (two or more hits) and `rg --files skills/run-autopilot/cli/golden/lanes`
  (15 hits) and skip with a report otherwise - Acceptance:
  `uv run --no-project --with pytest python -m pytest -q skills/fast-track/scripts/test_cards_from_prd.py`
  passes with `test_repaired_00188_renders_two_cards_load_card_accepts`
  (both cards load; `render_report.py` is in both `## Files`; the second
  card's `suite` is `batch`, the first `per-item`; the first `## Gates`
  line of card 1 is its `uv run ... test_convergence.py` command),
  `test_raw_00188_is_refused_on_a_relative_path` (exit 2, stderr names
  `files` and `cli/test_loop.py`, `--out` is empty afterwards),
  `test_raw_00189_renders_one_card_load_card_accepts` (its 11 `**Location**:`
  paths are all repo-relative, so one card with 11 files, `suite: batch`,
  `## Tests` empty, `framework: pytest`, `sample_test` =
  `skills/run-autopilot/cli/test_policy.py`),
  `test_00201_renders_one_card_with_tests_to_write` (`## Tests` empty,
  `framework: pytest`, `sample_test` an existing `skills/run-autopilot/...`
  test path, `## Constraints` opens with `Tests to write:` naming
  `test_brief.py::test_renders_the_documented_shape`),
  `test_twenty_five_paths_exit_two_naming_cards`,
  `test_item_slugs_match_card_py`, `test_gates_drop_chained_commands_loud`,
  `test_glob_file_entry_is_refused`, `test_model_follows_default_model_else_sonnet`,
  and `test_changelog_field_is_the_task_that_names_it`.

**Exit Criteria**: `pytest -q skills/fast-track/scripts/test_cards_from_prd.py`
green.

### Phase 1: Core
**Goal**: fast-track survives a headless turn.

**Tasks**:
- [ ] Replace the `Attended session` precondition with the `Loop session`
  bullet, add the § Roster sentence, rename the prose pin (depends on: Phase
  0) - Premise: `SKILL.md:27` reads `- **Attended session.**` and
  `test_fast_track_prose.py:438` defines `test_headless_sessions_are_refused`;
  re-check with `rg -n 'Attended session|def test_headless_sessions_are_refused' skills/fast-track/SKILL.md skills/fast-track/scripts/test_fast_track_prose.py`
  (one hit each) and skip with a report otherwise. Byte-identity premise:
  before editing, the § Roster through § Exit text (`sed -n '222,585p'
  skills/fast-track/SKILL.md` today) is saved with the Write tool to
  `dev/local/tmp/00206-roster-before.txt` (a shell redirect into
  `dev/local/` is blocked by aegis `block_devlocal_redirects.py`); after
  editing, the same sections (found by their headings, since line numbers
  move) diff empty against it - Acceptance:
  `uv run --no-project --with pytest python -m pytest -q skills/fast-track/scripts/test_fast_track_prose.py`
  passes with `test_headless_sessions_dispatch_the_watcher` (the
  preconditions name `_AUTOPILOT_LOOP`, `Watcher`,
  `await_reviewer_outputs.py` and `TaskStop`; `refuses` no longer appears
  in that bullet) and every other test in the file unchanged;
  `rg -c 'Watcher' skills/fast-track/SKILL.md` prints 2 or more.

**Exit Criteria**: `pytest -q skills/fast-track/scripts` green.

### Phase 2: Integration
**Goal**: the loop runs the lane and closes or stalls it.

**Tasks**:
- [ ] Write `references/lane-fast-track.md` (the Runbook feature, in order),
  the step 5.5 fast-track branch, `RELEASED_LANES` with `fast-track`, the
  `fast_track_blocked` slug in `recovery.md` and `state-schema.md`, and the
  prose pins (depends on: Phase 1, and 00205's `lane_reviewed`) - Premise:
  `transitions.py` holds `("build", "lane_reviewed")` and step 5.5 holds
  the `solo:` branch; re-check with
  `rg -n 'lane_reviewed' skills/run-autopilot/cli/transitions.py` and
  `rg -n 'lane-solo.md' skills/run-autopilot/references/phase-build.md`
  (one hit each) and skip with a report otherwise - Acceptance:
  `uv run --no-project --with pytest python -m pytest -q skills/run-autopilot/scripts/test_lane_prose.py`
  passes with `test_fast_track_runbook_orders_render_mirror_run_consolidate_close`,
  `test_fast_track_runbook_falls_back_to_full_on_uncardable`
  (`lane_effective`, `full`, `uncardable`, `Phase 1` in one sentence),
  `test_fast_track_runbook_stalls_a_branched_card`
  (`fast_track_blocked`, `autopilot stall`, `fast-track/<item>`),
  `test_fast_track_runbook_never_pushes` (`--push` appears only in a
  sentence saying it is not passed),
  `test_fast_track_review_file_names_the_lanes_that_ran`, and
  `test_step_5_5_fast_track_branch_names_the_runbook`;
  `cli/test_lane.py::test_effective_forces_full_when_off_or_unreleased`
  still passes unchanged (00204 pins its unreleased case with
  `RELEASED_LANES` monkeypatched, not with a lane name) and
  `test_reviewed_backlog_classifies_as_agreed` still passes; `rg -c 'fast_track_blocked' skills/run-autopilot/references/recovery.md skills/run-autopilot/references/state-schema.md`
  prints 1 or more for each.
- [ ] CHANGELOG entries (depends on: all) - Acceptance:
  `rg -n 'fast-track' CHANGELOG.md` shows one `**fast-track**` line under
  `### Changed` naming loop mode and the Watcher, and one
  `**run-autopilot**` line under `### Added` naming the lane runbook and
  `cards_from_prd.py`, both under `[Unreleased]`;
  `bash dev/bin/release-checks` passes.

**Exit Criteria**: `bash dev/bin/release-checks` green.

## Test Strategy

### Critical Scenarios
- **Happy path**: the repaired 00188 renders two cards; card 1 commits, card
  2 commits, the batch suite runs once, `-review-1.md` names the lanes that
  ran, `lane_reviewed` closes the PRD.
- **Edge case**: a PRD names `cli/test_loop.py` relative to a skill
  directory → exit 2 `files`, `lane_effective: full`, the full loop runs it,
  the report reads `classified fast-track, uncardable`.
- **Edge case**: card 1 commits and card 2 parks on a confirmed HIGH → stall
  `fast_track_blocked`; card 1's commits stay; the PRD sits in `hold/` with
  the branch name in its detail.
- **Error case**: a task quotes `pytest -q x | head` → dropped with a stderr
  note; when it was the only gate, exit 2 `gates`.

## Risks

- **Fast-track headless has never run**: the Watcher is the review phase's
  proven mechanism; the first batch is the proof; `_AUTOPILOT_LANES=off`
  forces full for a whole batch.
- **Two cards, two rosters, on a 16-path PRD**: bounded by the ceiling; the
  `--by-lane` metrics table (a follow-up) settles whether two cards beat the
  loop.
- **Path hygiene in hand-written PRDs**: a relative or bare path refuses the
  card and the PRD runs full, which is the safe direction; the `Lane:` line
  shows how often, and create-prd can tighten its path convention.
- **The prose diff of a 650-line skill file**: the byte-identity premise is
  checked by heading-bounded diff, not by line numbers.

### Deferred

- [Medium, spec amendment] the PRD's Render feature line ("`changelog` = the text of the first task item naming `CHANGELOG.md`, else empty") must read "else `none`" (Alice, Bob, Carl, review 2 packet 2) - the renderer emits the literal `none`, the value fast-track § Card skips the CHANGELOG edit on; an empty value would ask the implementor for an empty entry; amend the real PRD line before it moves to `done/`
- [Medium] `cards_from_prd._phase_bodies` re-implements `lane._phases`' heading walk (Bob, Carl, Alice; both cycles) - accepted per the review's own alternative: `lane._phases` returns task items, not raw bodies, so no drop-in call exists; a shared `lane.phase_bodies` is a follow-up
- [Low] Bob's VERIFY on suites and release checks - answered in both reviews and re-run after every fix (final: 2268 passed, 807 subtests; release-checks green)
- [Low] `fast_track_multicard_testutil._ELSEWHERE` still says the preconditions "refuse to run" under the loop (a message string in a test helper, untouched by the PRD) - one-line wording follow-up
- [Low] the first review-1 session died waiting on Bob and Carl (`dev/local/tmp/review-session-00206-1-died.jsonl`): it dispatched the CLI reviewers without a Watcher because `_AUTOPILOT_LOOP` was unset; the second attempt (and both later cycles) dispatched one anyway - the review-work-completion skill's Watcher rule could key on `CLAUDE_UNATTENDED` as well as `_AUTOPILOT_LOOP`
