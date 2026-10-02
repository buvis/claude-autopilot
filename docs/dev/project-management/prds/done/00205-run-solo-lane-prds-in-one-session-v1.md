---
catchup: run
design: skip
default_model: opus
model_tier_rationale: a Python port of securityTriggered with an equivalence obligation, a new state transition the review-coverage hook keys on, and code-decided escalation checks over a live git range; a wrong turn here lets an unreviewed production change close as done
rework_cap: 3
---

# Run solo-lane PRDs in one session

Source: `dev/local/discovery/00203-route-prds-by-effort-lane.md` (PRD B of
three; elicited 2026-09-13). Grounded 2026-09-14 at HEAD `70b606e`. Lands
after 00204 (the classifier, `state.lane`, step 5.5) and 00201 (owns the
Phase 0 opening sentence in `phase-build.md` and `cli/brief.py`). Independent
of 00206. Releases the `solo` lane: `lane.RELEASED_LANES` gains `solo`, so a
PRD that names no production path builds in one session, takes one
zero-context review pass, and closes without the review-rework loop.

## Overview

### Problem Statement

A prose, docs or test-only PRD pays the full pipeline: a Tess and Devon round
that broke the tests in every round measured, an Ivan dispatch for an edit
the orchestrator could make itself, and a review surface with every lens and
its rework cycles (`dev/local/notes/autoclaude-inefficiencies-2026-09-13.md:5-14`).
The pack already lets the orchestrator edit directly for small rework tasks
(`skills/work/references/rework-mode.md:16`, the micro lane) and already has
a single-pass consensus rule in fast-track (`skills/fast-track/SKILL.md:251-253`).
Nothing composes the two into a lane a PRD can take, and nothing escalates a
mis-routed PRD back into the full review with its commits kept. After 00204
the classifier records `solo` for such PRDs and still runs them full.

### Target Users

The loop operator paying per session, and a solo-classified PRD whose whole
build fits one session.

### Success Metrics

- `uv run --no-project --with pytest --with rich --with textual python -m pytest -q skills/run-autopilot`
  green with every test named under Implementation Phases present.
- `bash dev/bin/release-checks` green.
- Post-release signals, not judged in-session: a batch report whose solo PRD
  section reads `- Lane: solo (classified solo, no_production_code)` with one
  build session and no review session in its Loop Metrics table, and no
  `- Run conditions: no review_converged row` on any lane-routed PRD.

## Functional Decomposition

### Capability: Solo runbook
`references/lane-solo.md`, the procedure Phase 0 step 5.5 follows when
`state.lane_effective == "solo"`.

#### Feature: Build in session
- **Description**: the session mirrors the PRD's task lines, edits directly,
  commits per task and runs the suite once.
- **Inputs**: the PRD in `dev/local/prds/wip/`, `state.json`.
- **Outputs**: one conventional commit per task, `state.tasks` with attempt
  records, `dev/local/autopilot/last-verification.json`.
- **Behavior**, in this order and pinned by prose tests: (1) mirror every
  `- [ ]` line of the PRD into `state.tasks` with `task-add` (payload
  `{"name": <the task text>}`, no `model` key, so `tasks[i].model` is
  legacy-absent; `skills/plan-tasks/SKILL.md:72-75` is the payload contract),
  so tracon and the task counts stay live; (2) capture `work_start_sha` and
  `repo_root` (and `git_dir` for a bare-repo root) per the Phase 3
  invariants (`SKILL.md:252-256`, `phase-build.md:217-219`); (3) per task:
  `task-start`; implement with the Read, Edit and Write tools, no subagent,
  no shell rewrite (the micro lane generalized); where the task names a test,
  write it first and watch it fail once; run the acceptance commands the
  task names, each as its own Bash call; stage exactly the PRD's named paths
  the task touched plus `CHANGELOG.md` when the change earns an entry;
  commit in conventional form; `task-done` with the attempt record
  `{"attempt": 1, "model": <state.session_model or "sonnet">, "outcome": "completed", "review_cycle": null, "cause": null, "implementor": "orchestrator", "preflight_outcome": null, "pipeline": "solo"}`
  (`orchestrator` is the existing no-dispatch value,
  `references/state-schema.md` `tasks[].attempts` row; `solo` joins the
  `pipeline` vocabulary); (4) run the repo suite once under
  `skills/work/references/final-verification.md` and write
  `last-verification.json` per its § Recorded verification result. The soft
  marker `.handoff-requested` is not read: a solo PRD fits one session by
  construction and the hard cap of `autopilot_context_cap_hook.py` is the
  backstop (the session is `phase: "build"` with a task in progress, so the
  cap and tripwire apply unchanged and a rotation resumes by artifact at the
  first non-completed task).

#### Feature: Escalation checks
- **Description**: `autopilot lane-check` decides, in code, whether the
  finished build may take the single review pass or must join the full
  review gate.
- **Inputs**: `--state <path>`; `state.work_start_sha`, `state.repo_root`,
  `state.git_dir`, `state.lane`; the diff `work_start_sha..HEAD` read through
  `custody.git_argv(repo_root, git_dir)` (`cli/custody.py:126-131`) with
  `diff --name-only` and `diff`; or `--signal <slug>` for a signal the
  session determined from the review table or the suite.
- **Outputs**: exit 0 and `lane: ok` when no signal fires; exit 3 and
  `lane: escalate <signal>` after one transaction writing
  `lane_effective: "full"` and
  `lane_escalated: {"from": <state.lane>, "signal": <slug>}`; exit 2 with the
  reason on stderr when the state is unreadable or `work_start_sha` is
  unset.
- **Behavior**: without `--signal`, two checks in order: `unnamed_path` when
  any changed path is `lane.is_hook_path` or `lane.is_production_path` (a
  solo PRD named none, so any is unnamed); `security_diff` when
  `lane.security_triggered(diff, changed_files)` fires. A git command that
  fails escalates with `check_failed` rather than passing: the check fails
  toward the expensive lane (the `_AUTOPILOT_AGOGE_AUTHORIZED` principle,
  `SKILL.md:130`). `--signal` accepts `critical_finding`, `high_unresolved`,
  `suite_red` and records that slug. `lane.security_triggered(diff, changed_files) -> bool`
  is the Python port of `securityTriggered`
  (`~/.claude/workflows/review-fanout.workflow.js:156-178`): a changed path
  that is `securityish` fires; a `---`/`+++` pair is a header and skipped
  only as a pair; every other `+` or `-` line is tested with `securityish`.
  The verb is registered in `_SUBCOMMANDS` (`cli/__main__.py:874-891`).

#### Feature: One review pass
- **Description**: after `lane-check` passes, one zero-context review of the
  whole range under fast-track's consensus rule.
- **Inputs**: the PRD, `git diff work_start_sha..HEAD`, the changed-file
  list, the review-work-completion rubric and
  `references/output-formats.md` § Agent Output Format.
- **Outputs**: `dev/local/reviews/<prd-stem>-review-1.md` in the shape
  `cli/gate.py` checks (`:64-75`;
  `review-work-completion/references/review-coverage-format.md:9-25`).
- **Behavior**: the consensus rule verbatim
  (`skills/fast-track/SKILL.md:251-253`): the `review-fanout` workflow when
  `~/.claude/workflows/review-fanout.workflow.js` is on disk, else the
  `autopilot:alice` subagent; `consolidate_findings.py alice:<output>`
  (`review-work-completion/scripts/consolidate_findings.py:353-359`) or the
  workflow's own table builds the findings table. The file carries
  `head_sha: <HEAD>`, `reviewers: alice` with one `## Alice` section (or
  `reviewers: fanout` with one `## Fanout` section holding the workflow's
  consolidated table), the table, `Verdict: converged` when no row survives
  or `Verdict: N findings` (N = surviving rows of any severity),
  `Tests: N passed, M failed, K skipped (reused from last-verification.json at <sha>)`
  composed as `review-work-completion/SKILL.md:404` composes it, or
  `Tests: none (docs-only)` when every changed path is a doc, and
  `codex_rung_guard: not fired` (no codex-implemented task exists in this
  lane).

#### Feature: Findings disposition
- **Description**: what the session does with each severity.
- **Inputs**: the consolidated table.
- **Outputs**: at most one fix commit and one delta dispatch; or an
  escalation.
- **Behavior**: a CRITICAL escalates with `critical_finding`, no fix
  attempted. A HIGH or MEDIUM inside the PRD's named paths gets one
  in-session fix, the narrow checks the affected task named, and one delta
  dispatch of the same reviewer over `<fix-base>..HEAD` (fast-track's Delta
  shape, `SKILL.md:508-540`); a HIGH still confirmed after the delta
  escalates with `high_unresolved`; a suite that is red after the fix
  escalates with `suite_red`. A HIGH outside the PRD's named paths escalates
  with `high_unresolved` without a fix; a MEDIUM outside them and every LOW
  are recorded in the file, never reworked. On any escalation after the pass
  ran, the table is written to `dev/local/reviews/<prd-stem>-solo-pass.md`
  (a durable trail whose name never matches the gate's `-review-*` glob,
  `scripts/review_coverage_hook.py:44-57`, or the convergence reader's
  `-review-<n>`), never to `-review-1.md`, so the full lane's cycle 1 finds
  no file and runs.

#### Feature: Escalate or close
- **Description**: two exits, both through `autopilot phase-done`.
- **Inputs**: the `lane-check` result.
- **Outputs**: the next session's phase.
- **Behavior**: escalation = `autopilot phase-done --outcome tasks_done`
  (`cli/transitions.py:88`) and the Session handoff procedure
  (`SKILL.md:180-196`, build → review row), so the full review gate takes
  the finished build with every lens and its rework cycles; no commit is
  lost. Close = `autopilot phase-done --outcome lane_reviewed`, a new row
  `("build", "lane_reviewed"): _converged` in `TRANSITIONS`
  (`transitions.py:87-97`), whose effect is `_converged`'s (`:54-69`):
  `phase`/`next_phase: "done"` and `"review"` appended once to
  `phases_completed`, so `review_coverage_hook.gate_blocks`
  (`scripts/review_coverage_hook.py:99-146`, gated on `"review" in
  phases_completed` at `:85-96`) checks the solo review file with
  `--require-codex-guard` exactly as it checks a full-lane cycle; the done
  session then finalizes as today (`references/phase-done.md:10-62`).
  `OUTCOMES` (`transitions.py:99`) derives the new choice for the
  `phase-done` parser by itself.

### Capability: Lane composition
The neighbours learn the lane exists.

#### Feature: Convergence row for lane-routed PRDs
- **Description**: `loop._append_metrics` (`cli/loop.py:893-934`, or the
  sibling module PRD 00192 extracted it to; 00192 lands first) emits PRD
  00188's `review_converged` row on a build-launched session ending in
  `done` when `state.lane_effective` is `solo` or `fast-track`.
- **Inputs**: `decision["phase_end"]`, `phase_launched`, the state 00188's
  branch already re-reads.
- **Outputs**: the same row shape, `cycles[]` read from `-review-1.md`.
- **Behavior**: the emission condition becomes
  `phase_end == "done" and (phase_launched == "review" or lane_effective in ("solo", "fast-track"))`;
  a full-lane build session ending in `done` (a drained batch) still writes
  none.

#### Feature: Brief line
- **Description**: the 00201 session brief's `Where` section gains
  `- lane: <lane_effective> (classified <lane>, <lane_reason>)` after the
  `- phase:` line, `none` when the state has no lane.
- **Inputs**: `state.json`.
- **Outputs**: `cli/brief.py` `render_brief` output; the golden
  `cli/golden/expected/session-brief-build.md` changes.
- **Behavior**: one line; nothing else in the brief moves.

#### Feature: Step 5.5 solo branch and docs
- **Description**: `references/phase-build.md` § 5.5 replaces its shadow
  sentence with `solo: read references/lane-solo.md and follow it; Phases 1
  to 3 do not run for this PRD` and keeps the `running full` banner for an
  unreleased lane; `lane.RELEASED_LANES` becomes `frozenset({"full", "solo"})`.
- **Inputs**: none.
- **Outputs**: prose, and `references/state-schema.md` rows for
  `lane_escalated` (beside `lane_effective`) and `lane_reviewed` (in the
  Session handoff table of `SKILL.md:188-194` and the `phases_completed` row
  `:172`), a note beside the promotion signals (`:440`) that a solo session
  runs at 00200's `session_model` and that `default_model` is inert in solo,
  and a `lane=<lane_effective>` term in the `detail` the Phase 0 park
  handler writes for a `wrapper_died` park (`references/recovery.md:47-50`),
  so a solo PRD parked by the died-retry (`SKILL.md:164`) carries its lane.
- **Behavior**: `records.PER_PRD_RESET_FIELDS` (`records.py:69-92`) gains
  `lane_escalated`: it is per-PRD work product, not re-derived at Phase 0
  (the reset that would otherwise leak it into the next PRD's report line).

## Structural Decomposition

### Repository Structure

```
skills/run-autopilot/
├── cli/
│   ├── lane.py                      # Maps to: security_triggered, RELEASED_LANES
│   ├── __main__.py                  # Maps to: the lane-check verb
│   ├── transitions.py               # Maps to: lane_reviewed
│   ├── records.py                   # Maps to: lane_escalated reset
│   ├── loop.py                      # Maps to: convergence row for lane-routed PRDs (or the 00192 sibling holding _append_metrics)
│   ├── brief.py                     # Maps to: brief line
│   ├── test_lane.py, test_lane_cli.py, test_transitions.py, test_loop.py, test_brief.py
│   └── golden/expected/session-brief-build.md
├── scripts/
│   ├── test_lane_prose.py           # solo runbook pins
│   └── test_review_coverage_hook.py # the gate accepts the solo file
├── references/
│   ├── lane-solo.md                 # Maps to: Solo runbook (new)
│   ├── phase-build.md               # step 5.5 solo branch; park detail
│   ├── recovery.md
│   └── state-schema.md
└── SKILL.md                         # handoff table row
CHANGELOG.md
```

### Module: lane-solo runbook
- **Maps to capability**: Solo runbook
- **Responsibility**: the in-session build, the review pass, the disposition
  and the two exits, in order
- **Exports**: none (prose pinned by `test_lane_prose.py`)

### Module: lane + lane-check verb
- **Maps to capability**: Solo runbook (escalation checks)
- **Responsibility**: the security port and the code-decided escalation
- **Exports**: `lane.security_triggered(diff, changed_files)`,
  `lane.RELEASED_LANES`; the `lane-check` subcommand

### Module: transitions + records
- **Maps to capability**: Solo runbook (escalate or close)
- **Responsibility**: the `lane_reviewed` row; the `lane_escalated` reset
- **Exports**: `TRANSITIONS[("build", "lane_reviewed")]`, `OUTCOMES`

### Module: loop + brief + prose
- **Maps to capability**: Lane composition
- **Responsibility**: the convergence row, the brief line, the docs
- **Exports**: `_append_metrics(...)` unchanged signature;
  `render_brief(state, now)` unchanged signature

## Dependency Graph

### Foundation Layer (Phase 0)
No dependencies - built first.

- **lane (security port, RELEASED_LANES)**: pure additions to 00204's module.
- **transitions + records**: one row, one reset entry.

### Core Layer (Phase 1)
- **lane-check verb**: Depends on [lane, custody.git_argv].
- **loop + brief**: Depends on [transitions] (the build-to-done exit it
  observes exists only with `lane_reviewed`).

### Integration Layer (Phase 2)
- **lane-solo runbook + prose**: Depends on [lane-check verb, transitions,
  loop + brief].

## Implementation Phases

### Phase 0: Foundation
**Goal**: the port, the transition and the reset exist.

**Tasks**:
- [ ] `lane.security_triggered` and `RELEASED_LANES = frozenset({"full", "solo"})`
  (no deps) - Premise: 00204's `cli/lane.py` exports `securityish` and
  `RELEASED_LANES`; re-check with
  `rg -n '^def securityish|^RELEASED_LANES' skills/run-autopilot/cli/lane.py`
  (two hits) and skip with a report on a mismatch - Acceptance:
  `uv run --no-project --with pytest python -m pytest -q skills/run-autopilot/cli/test_lane.py -k "security_triggered or released"`
  passes with `test_security_triggered_fires_on_a_securityish_changed_path`
  (`auth/login.py`), `test_security_triggered_fires_on_an_added_or_removed_line`
  (`+token = ...` and `-password = ...`),
  `test_security_triggered_skips_a_header_pair_but_scans_a_lone_dash_line`
  (`--- a/x` followed by `+++ b/x` is skipped; a removed `--secret-flag`
  line without a `+++` partner fires),
  `test_security_triggered_is_quiet_on_a_docs_diff`, and
  `test_reviewed_backlog_classifies_as_agreed` still passes with `solo`
  released (`effective("solo", None)` now returns `solo`);
  `test_effective_forces_full_when_off_or_unreleased` still passes
  unchanged (00204 pins its unreleased case with `RELEASED_LANES`
  monkeypatched, not with a lane name).
- [ ] `("build", "lane_reviewed"): _converged` in `TRANSITIONS` and
  `lane_escalated` in `PER_PRD_RESET_FIELDS` (no deps) - Premise:
  `transitions.py:87-97` holds exactly six rows; re-check with
  `rg -c '^    \("' skills/run-autopilot/cli/transitions.py` printing 6 and
  skip with a report otherwise - Acceptance: `cli/test_transitions.py`
  gains `LaneReviewedTests` with `test_lane_reviewed_appends_the_review_marker`
  (from `phase: "build"`, `phases_completed: []` → `phase`/`next_phase`
  `done` and `["review"]`) and `test_lane_reviewed_appends_the_marker_once`
  (a second apply after a crash keeps one marker); `TableTests` still
  passes with `lane_reviewed` in `OUTCOMES`;
  `cli/test_records.py::test_lane_escalated_is_reset_per_prd`.

**Exit Criteria**: `pytest -q skills/run-autopilot/cli/test_lane.py skills/run-autopilot/cli/test_transitions.py skills/run-autopilot/cli/test_records.py`
green.

### Phase 1: Core
**Goal**: the verb decides; the ledgers and the brief see the lane.

**Tasks**:
- [ ] The `lane-check` verb (depends on: Phase 0) - Premise:
  `custody.git_argv(repo_root, git_dir)` exists at `cli/custody.py:126`;
  re-check with `rg -n '^def git_argv' skills/run-autopilot/cli/custody.py`
  and skip with a report otherwise - Acceptance: `cli/test_lane_cli.py`
  (subprocess over this checkout's `cli/__main__.py` and a temp git repo
  initialised with `git init`, one commit, `work_start_sha` set to it)
  passes with `test_lane_check_escalates_on_a_production_path` (a second
  commit adding `pkg/mod.py` → exit 3, stdout `lane: escalate unnamed_path`,
  `state.lane_effective == "full"`,
  `state.lane_escalated == {"from": "solo", "signal": "unnamed_path"}`),
  `test_lane_check_escalates_on_a_security_diff` (a docs-only commit adding
  a line `password: hunter2` to `notes.md` → `security_diff`),
  `test_lane_check_passes_a_docs_only_diff` (exit 0, `lane: ok`, state
  untouched), `test_lane_check_records_an_explicit_signal`
  (`--signal critical_finding` → exit 3 and the fields),
  `test_lane_check_escalates_when_git_fails` (`repo_root` pointing at a
  non-repo → `check_failed`), `test_lane_check_refuses_without_work_start_sha`
  (exit 2, stderr names the field) and
  `test_lane_check_rejects_an_unknown_signal` (argparse exit 2).
- [ ] Convergence row on the lane-routed build-to-done exit; the brief line
  (depends on: Phase 0) - Premise: 00188's branch in `_append_metrics` (in
  `cli/loop.py` or the sibling 00192 extracted it to) tests
  `phase_launched == "review"` and 00201's `render_brief` prints the
  `- phase:` line; re-check with
  `rg -n 'phase_launched == "review"' skills/run-autopilot/cli/loop*.py` and
  `rg -n '^- phase:' skills/run-autopilot/cli/golden/expected/session-brief-build.md`
  (one hit each) and skip with a report on a mismatch - Acceptance:
  `cli/test_loop.py::test_build_exit_to_done_writes_the_convergence_row_for_a_solo_lane`
  (a build step writing `next_phase: "done"`, `lane_effective: "solo"`,
  `cycle: 1` and a fixture `-review-1.md` → one event row whose
  `cycles[0].reviewers == ["alice"]`),
  `::test_build_exit_to_done_writes_no_convergence_row_for_the_full_lane`,
  and 00188's three convergence tests unchanged;
  `cli/test_brief.py::test_renders_the_documented_shape` against the updated
  golden and `::test_lane_line_renders_none_without_a_lane`.

**Exit Criteria**: `pytest -q skills/run-autopilot/cli` green.

### Phase 2: Integration
**Goal**: the runbook exists, is pinned, and the gate accepts what it writes.

**Tasks**:
- [ ] Write `references/lane-solo.md` (the five features of the Solo runbook
  capability, in order: mirror, implement, suite, escalation checks, review,
  disposition, close), the step 5.5 solo branch, the `SKILL.md` handoff-table
  row for `lane_reviewed`, the `state-schema.md` rows and note, the
  `recovery.md`/`phase-build.md` park-detail term, and the prose pins
  (depends on: Phase 1) - Premise: 00204's step 5.5 holds the sentence
  `acted on by nothing`; re-check with
  `rg -n 'acted on by nothing' skills/run-autopilot/references/phase-build.md`
  (one hit) and skip with a report otherwise - Acceptance:
  `uv run --no-project --with pytest python -m pytest -q skills/run-autopilot/scripts/test_lane_prose.py`
  passes with `test_solo_runbook_orders_mirror_implement_suite_check_review_close`
  (the six section headings in that order),
  `test_solo_runbook_names_six_signals_and_their_outcomes` (`unnamed_path`,
  `security_diff`, `check_failed`, `critical_finding`, `high_unresolved`,
  `suite_red`; `--outcome tasks_done` beside them; `--outcome lane_reviewed`
  in the close), `test_solo_runbook_never_reads_the_handoff_marker`
  (`.handoff-requested` appears only in a sentence saying it is not read),
  `test_solo_review_file_shape_is_gate_shaped` (`head_sha`, `reviewers:`,
  `Verdict:`, `Tests:`, `codex_rung_guard: not fired`, `-solo-pass.md`),
  `test_solo_attempt_record_uses_orchestrator_and_solo_pipeline`,
  `test_step_5_5_solo_branch_names_the_runbook` (the `acted on by nothing`
  sentence is gone; `lane-solo.md` is named);
  `scripts/test_review_coverage_hook.py::test_gate_accepts_a_solo_lane_review_file`
  (phase `done`, `phases_completed: ["review"]`, a `-review-1.md` with
  `reviewers: alice` and the five lines → no block) and
  `::test_gate_blocks_a_solo_close_without_a_review_file`;
  `rg -c 'lane_reviewed' skills/run-autopilot/SKILL.md skills/run-autopilot/references/state-schema.md`
  prints 1 or more for each;
  `rg -c 'lane=' skills/run-autopilot/references/recovery.md skills/run-autopilot/references/phase-build.md`
  prints 1 or more for each.
- [ ] A subprocess proof and the CHANGELOG (depends on: the runbook task) -
  Acceptance: `cli/test_lane_cli.py::test_phase_done_lane_reviewed_from_build`
  runs this checkout's `cli/__main__.py phase-done --outcome lane_reviewed`
  over a temp state with `phase: "build"` and asserts `phases_completed`
  carries `review` and `next_phase` is `done`; CHANGELOG `### Added` under
  `**run-autopilot**` names the solo lane, `lane-check`, `lane_reviewed`
  and that the lane is now live for solo-classified PRDs
  (`rg -c 'lane-check' CHANGELOG.md` prints 1 or more);
  `bash dev/bin/release-checks` passes.

**Exit Criteria**: `bash dev/bin/release-checks` green.

## Test Strategy

### Critical Scenarios
- **Happy path**: a three-doc PRD builds in one session, `lane-check` says
  `ok`, Alice converges, `-review-1.md` passes the gate, `lane_reviewed`
  closes it, the report shows one build session and `Lane: solo`.
- **Edge case**: the session touches a `.py` the PRD never named →
  `unnamed_path` → `tasks_done` → the full review gate reviews the finished
  build; no commit lost.
- **Edge case**: Alice raises one HIGH inside the PRD's paths → one fix, one
  delta; the HIGH survives → `high_unresolved`; the table lands in
  `-solo-pass.md`, cycle 1 of the full lane finds no `-review-1.md`.
- **Error case**: `git diff` fails (bad `repo_root`) → `check_failed`, never
  `ok`.

## Risks

- **The session's own reading shapes its code**: the zero-context pass and
  the six code-decided or table-decided signals are the counterweight; a
  CRITICAL escalates without a fix attempt.
- **A HIGH fixed in solo is verified by one delta only**: a surviving HIGH
  escalates to the full review; a LOW is never reworked.
- **The solo file name collides with the full lane's cycle 1**: prevented by
  construction; an escalated pass writes `-solo-pass.md`.
- **00206 closes with `lane_reviewed` too**: it lands after this PRD by
  sequence; the row is shared, not duplicated.

### Deferred

- [High, closed at integration 2026-09-20 after the rebase onto 00201: `render_brief` prints the lane line, golden and `test_lane_line_renders_none_without_a_lane` pin it] Brief line (`- lane:` in the session brief's Where section) not built (Blake, both cycles) - the PRD's own premise rule ("skip with a report on a mismatch") fired: `cli/brief.py` and `cli/golden/expected/session-brief-build.md` (PRD 00201) do not exist on this branch; the report and the exact integrator instruction are in commit 099814c's body; the integrator adds the line after 00201 lands
- [Low] `review_failed` is a fourth session signal beyond the PRD's three (Blake) - added at the review's own recommendation (cycle 1 packet 2 option A) so a failed sole review pass escalates instead of converging on an empty table; the PRD's Escalation-checks feature line should be amended to name it
- [Low] `test_solo_runbook_names_six_signals_and_their_outcomes` pins seven signals (Blake) - the PRD names the test by name, so it keeps its name and carries a comment
- [Low] the runbook's review-format check is a second, prose-side reading of `consolidate_findings.py`'s `_LINE_RE` (review 2 packet 3, option A's stated drawback) - option B (the consolidator warning on an unparseable `[AGENT]` line) would fix the full lane's silent drop too and is a follow-up outside this PRD's paths
- [Low] Bob's VERIFY on the release checks after rework - `bash dev/bin/release-checks` green at the final HEAD (see the report)
- [Low] `cli/__main__.py` is 1,181 lines, over the 800-line file ceiling (Carl, Bob KNOWN) - 1,125 before this branch; pre-existing debt, the registry split is its own PRD

Review 3 (post-rebase onto the 0.5.3 master, 2026-09-20, 8 findings, 0 CRITICAL / 0 HIGH): `_append_metrics` back at 50 lines after the rebase and the empty-string `lane_effective` fallback fixed at integration; deferred:
- [Medium] `lane-solo.md:162` row-count check rejects valid duplicate or paraphrased Alice findings that `consolidate()` merged, and names no mismatch action - validate parsed findings before merging and route parse failures through the retry/`review_failed` path (Bob)
- [Medium] `lane-solo.md:28` mirroring by name membership collapses identical checkbox labels in different PRD phases into one task - match occurrence counts per name (Bob)

