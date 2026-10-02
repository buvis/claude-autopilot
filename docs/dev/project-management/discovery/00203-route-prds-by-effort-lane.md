# Discovery: Route PRDs by effort lane

## Classification
Depth: comprehensive | Date: 2026-09-13

Source: the operator's brief (2026-09-13), `dev/local/notes/autoclaude-inefficiencies-2026-09-13.md` § Conclusions, `dev/local/audit-results/backlog-review-2026-09-13.md` (the 15 reviewed PRDs 00187-00202 as the labelled sample), and discovery 00193 § Q5, which deferred exactly this. Grounded against HEAD `2c922c3`. Yields three sequenced PRDs, all after 00200: A (classifier, `lane:` key, Phase 0 routing in shadow, lane fields in the ledgers and report), B (the solo lane runbook, its review file and escalation), C (cards from a PRD and the fast-track lane in loop mode). Sequence numbers are re-scanned at create-prd time.

## Problem

One opus task in the full pipeline costs ~200 tool calls, 60-80 minutes and $50-70, of which Ivan's implementation is 5-10 minutes; Devon broke the tests in every round measured, orientation costs ~100 calls per session, the design step consumed a 249-call session before planning, and one review's 32 findings became 10 opus rework tasks (`dev/local/notes/autoclaude-inefficiencies-2026-09-13.md:5-14`). That pipeline earns its cost on cross-cutting, algorithmic or security-sensitive PRDs. For prose edits, one-file fixes and test scaffolding, most of what the two loops ran on 2026-09-13, it is a 5-10x tax over a solo session plus one review pass (`:22-24`). The decision taken that evening was to start with lever 1: route PRDs by risk lane so most never enter the full loop, estimated at 50-70% of batch spend (`:25-29`).

Today every PRD enters the same loop. Phase 0 parses seven frontmatter keys (`cli/frontmatter.py:38-56`) and none of them chooses a lane; `routing.route` (`cli/routing.py:212-256`) picks a model, an effort and a wall cap per phase, never a pipeline. The pack already has the middle lane, `fast-track` (PRD 00186), and a precedent for the cheapest one, the rework micro lane where the orchestrator edits directly (`skills/work/references/rework-mode.md:16`), but nothing decides which PRD takes which, and fast-track refuses to run inside the loop at all (`skills/fast-track/SKILL.md:27-31`). Without a classifier the three siblings from discovery 00193 (00199, 00200, 00201) thin the loop's overhead without changing how many PRDs pay it.

## Requirements

### Must have

PRD A, the classifier and its routing (`skills/run-autopilot/cli/`, Phase 0 prose, ledgers, report):

- A pure module `cli/lane.py`, stdlib only, `classify(text, declared) -> Verdict(lane, reason, paths, prod_paths, cards)` deciding from the PRD text plus the flat frontmatter pairs the caller already parsed (`declared`, from a new `frontmatter.declared(text)` that wraps `_block` and `_pairs`, so the block window is `frontmatter._HEAD_LINES` and nothing else), rules checked in order and the first match recorded as `reason` (the `classify_tier.py` shape, `skills/plan-tasks/scripts/classify_tier.py:113-135`):

  | # | rule | evidence read | lane | `reason` |
  |---|---|---|---|---|
  | 0 | `declared["lane"]` is one of `solo`, `fast-track`, `full` | the parsed frontmatter pairs | as written | `override` |
  | 1 | any named path is a hook: a `hooks/` directory segment, basename `hooks.json`, or basename `*_hook.py` | named paths | full | `hook` |
  | 2 | any named path trips the security regex (camel-split, lowercased, the `SECURITY_RE` of `review-fanout.workflow.js:41-42` ported verbatim) | named paths | full | `security_path` |
  | 3 | the PRD names no path at all | named paths | full | `unparsed` |
  | 4 | effective `design_mode` is `run` (declared `run`, or absent, which defaults to `run` per `frontmatter.py:40`) | frontmatter | full | `design` |
  | 5 | zero production paths: every named path is a test path (`work_routing.is_test_path`), a doc (`.md`, `.txt`, `.rst`), a packaging manifest (`classify_tier.is_packaging_path`) or `CHANGELOG.md` | named paths | solo | `no_production_code` |
  | 6 | cardable: `lane.plan_cards(text)` returns one or two cards (below) | named paths, phases, task items | fast-track | `card_sized` |
  | 7 | otherwise | | full | `uncardable` |

- `lane.plan_cards(text) -> list[CardPlan(phase, files, goal_lines)]` is the one owner of the card split; `Verdict.cards` is its length and PRD C's renderer imports it by path and only renders. It returns one whole-PRD card when the named paths fit 12 and the goal fits 40 lines, else one card per phase when the PRD has exactly two phases and each phase's card fits both limits (the `card.py` refusals, `skills/fast-track/SKILL.md:58-63`), else an empty list. Its terms: a phase is a `### Phase N:` heading under `## Tasks` or `## Implementation Phases` (never the `(Phase N)` suffix of a `## Dependency Graph` layer heading); a task item is its `- [ ]` line joined with its indented continuation lines into one line before any count; the goal is the Problem Statement (standard template) or `## Problem` (minimal template) followed by the card's joined task items; a phase card's files are the PRD-named paths that appear in the phase's joined task text, else every named path.
- `lane.RELEASED_LANES` names the lanes whose runbook has shipped: `{"full"}` in PRD A; B adds `solo`, C adds `fast-track`. `lane_effective` is `full` when `_AUTOPILOT_LANES=off` or the classified lane is not released, else the classified lane.

- Named paths come from the fenced block under `### Repository Structure` (tree glyphs rebuilt into full paths by the rules PRD 00189 gives `policy.prd_modules`; a line with no glyph is a root entry; comma-separated root lines split) and from `**Location**:` lines (backticked paths). A trailing `:N` or `:N-M` is stripped the way PRD 00198's `normalize_file` strips citations. Task lines are `policy.prd_task_lines` (00189). The two path predicates are imported by path exactly as `classify_tier._load_is_test_path` does (`classify_tier.py:19-28`), never copied.
- `default_model` never decides the lane; it keeps its documented meaning as the implementor tier floor and is honored inside the lanes that dispatch implementors (the card's `model` in fast-track, the task tier in full). In solo, which dispatches none, it is inert.
- The `autopilot frontmatter` verb (`cli/__main__.py:495-530`) runs `lane.classify` on the same text and pairs it already parses and writes `state.lane`, `state.lane_reason` and `state.lane_effective` in its one transaction, echoing all three; it is the one reader of `_AUTOPILOT_LANES` (through `env.get`, the wrapper's idiom). An invalid `lane:` value takes the classified lane and the verb prints one warning line naming the field, the disposition `frontmatter.py:14-17` gives every enum; an absent key is silent. `MALFORMED_WARNING` stays byte-identical (00189 pins it). The three fields are documented in `references/state-schema.md` § Field Descriptions beside `doubt_reviewer` (`:175`), re-derived per PRD at Phase 0 and therefore not in `records.PER_PRD_RESET_FIELDS` (`cli/records.py:91-96` keeps the frontmatter enums out on purpose).
- Phase 0 gains step 5.5 in `references/phase-build.md` after the frontmatter parse (`:88-130`): branch on `state.lane_effective`. When it differs from `state.lane` print `── AUTOPILOT ── lane: <lane> (<reason>), running full ──`; `full` continues to Phase 1. In PRD A every PRD takes that path (`RELEASED_LANES` is `{"full"}`); PRDs B and C each add their lane to `RELEASED_LANES` and their branch to step 5.5.
- Kill switch `_AUTOPILOT_LANES=off` in the loop environment forces `lane_effective: full` for every PRD (read by the verb, above).
- Ledgers: `loop._append_metrics` (`cli/loop.py:893-934`) adds `lane` and `lane_effective` to every session row, read from `state.json` at append time (each `null` when absent), inside its existing `try`; `statectl._completed_prd_record` (`cli/statectl.py:349-374`) adds `lane`, `lane_effective` and `lane_escalated` (the state dict copied verbatim, `null` when absent) to the `batch.completed_prds` entry.
- Report: `render_report.prd_section` (`cli/render_report.py:509`) prints `- Lane: <lane_effective> (classified <lane>, <reason>)` after `- Tasks:` (`:539`), with `, escalated from <lane>: <signal>` when the record carries it; `batch_summary` (`:580`) prints `- PRDs by lane: solo N, fast-track N, full N; escalated N` after `- PRDs skipped:` (`:603`). `references/batch-report-format.md` § What a completed-PRD section carries documents both. Goldens `cli/golden/expected/report-section.md` and `report-summary.md` change with them.
- Fixture: the 15 reviewed PRDs are frozen under `cli/golden/lanes/` and `cli/test_lane.py::test_reviewed_backlog_classifies_as_agreed` asserts the table in § Approach; rule-level tests cover each `reason`, the `design`-absent case, the hook basename forms, the line-suffix strip, the invalid and valid override, and the security regex on a path such as `auth/login.py`.
- CHANGELOG `### Added` under `**run-autopilot**`.

PRD B, the solo lane (`skills/run-autopilot/references/lane-solo.md`, `cli/transitions.py`, `cli/loop.py`, the review file):

- `references/lane-solo.md` is the runbook Phase 0 step 5.5 follows when `state.lane == "solo"` and lanes are on. Its procedure, in order: mirror the PRD's `- [ ]` task lines into `state.tasks` with `task-add` (`name` = the task text, no `model` key, so `state.tasks[i].model` is legacy-absent; `skills/plan-tasks/SKILL.md:72-75` is the payload contract) so tracon and the task counts stay live; capture `work_start_sha` and `repo_root` per the Phase 3 invariants (`SKILL.md:254-256`, `phase-build.md:217-219`); for each task `task-start`, implement directly with Read, Edit and Write (no subagent, the micro lane of `rework-mode.md:16` generalized), write the test first where the task names one and watch it fail, run the acceptance commands the task names, stage exactly the PRD's paths plus `CHANGELOG.md` when the change earns an entry, commit in conventional form, `task-done` with an attempt record `{implementor: "session", pipeline: "solo", model: <session model>, outcome: "completed"}`; then run the repo suite once under `work/references/final-verification.md` and write `last-verification.json`.
- Escalation checks, run in this order at the end of the build and before any review, each decided by code: (1) `git diff --name-only <work_start_sha>..HEAD` contains a hook path or any production path (a solo PRD named none, so any is unnamed); (2) `lane.security_triggered(diff, changed_files)`, the Python port of `securityTriggered` (`review-fanout.workflow.js:156-178`), fires on the added or removed lines or a changed path. On either: write `state.lane_effective = "full"` and `state.lane_escalated = {"from": "solo", "signal": "unnamed_path" | "security_diff"}`, then `autopilot phase-done --outcome tasks_done` (`transitions.py:88`) and the Session handoff procedure (`SKILL.md:180-196`), so the full review gate takes the finished build with every lens and its rework cycles; no commit is lost.
- The one review pass: fast-track's consensus rule verbatim (`skills/fast-track/SKILL.md:251-253`): the `review-fanout` workflow when `~/.claude/workflows/review-fanout.workflow.js` is on disk, else `autopilot:alice`; inputs are the PRD, the `work_start_sha..HEAD` diff and the changed-file list with the review-work-completion rubric and output format; `consolidate_findings.py` builds the table. The result is written as `dev/local/reviews/<prd-stem>-review-1.md` in the shape `cli/gate.py` checks (`:64-75`; `review-coverage-format.md:9-25`): frontmatter `head_sha`, `reviewers: alice` (or the fanout dimensions that ran), one non-empty section per reviewer, `Verdict: converged` or `Verdict: N findings`, a `Tests:` line composed from `last-verification.json`, and `codex_rung_guard: not fired`.
- Findings: a CRITICAL in the table escalates as above with signal `critical_finding`, no fix attempted. A HIGH or MEDIUM inside the PRD's paths gets one in-session fix, the narrow checks, and one delta dispatch of the same reviewer over `<fix-base>..HEAD` (the shape of fast-track's Delta); a HIGH surviving the delta escalates with signal `high_unresolved`; a suite that is red after the fix escalates with `suite_red`. LOW is recorded, never reworked.
- Close: `autopilot phase-done --outcome lane_reviewed`, a new row `("build", "lane_reviewed")` in `TRANSITIONS` (`transitions.py:87-97`) whose effect is `_converged`'s (`:54-69`): `phase`/`next_phase: "done"` and `"review"` appended to `phases_completed`, so `review_coverage_hook.gate_blocks` (`scripts/review_coverage_hook.py:99-146`, gated on `"review" in phases_completed` at `:85-96`) checks the solo review file with `--require-codex-guard` (`:60-82`) exactly as it checks a full-lane cycle. The done session then finalizes as today (Phase 9, `phase-done.md:10-62`).
- Budget: the solo session is `phase: "build"` with a task in progress, so `autopilot_context_cap_hook.py`'s hard cap and tripwire apply unchanged and a rotation resumes by artifact (tasks exist, work continues at the first non-completed task). The soft marker `.handoff-requested` is not read by the solo runbook: a solo PRD fits one session by construction, and the hard cap is the backstop. A solo PRD parked by the loop's died-retry (`SKILL.md:164`) lands in `hold/` with its lane in the stall detail.
- The PRD 00188 convergence row is emitted only on a review-launched session ending in `done`; B extends the emission in `_append_metrics` to a build-launched session ending in `done` when `state.lane_effective` is `solo` or `fast-track`, reading `cycles[]` from the lane's review-1 file, so the report's `- Run conditions:` line never reads `no review_converged row` for a lane-routed PRD.
- Session model: `routing.build_model` is untouched; the solo session runs at 00200's `session_model` (default sonnet) or a promotion signal; `default_model` is inert in solo and `session_model: opus` is the author's tool. Documented in `references/state-schema.md` beside the promotion signals (`:440`).
- Prose tests pin the runbook order (mirror, implement, suite, escalation checks, review, close), the five escalation signals and their `phase-done` outcomes, the review-file shape, and step 5.5's solo branch; `cli/test_transitions.py` pins `lane_reviewed`; a subprocess fixture runs this checkout's `cli/__main__.py phase-done --outcome lane_reviewed` and asserts `phases_completed` carries `review`.
- CHANGELOG `### Added` under `**run-autopilot**`.

PRD C, cards from a PRD and fast-track in the loop (`skills/fast-track/`, `references/lane-fast-track.md`):

- `skills/fast-track/scripts/cards_from_prd.py <prd> --out <dir>` renders one card per `CardPlan` that `lane.plan_cards` returns (imported by path, the `classify_tier._load_is_test_path` idiom; the split, the phase, task-item and goal terms live there, PRD A), and exits 2 with the failing field on stderr, the `card.py` idiom, when the plan is empty or a field below cannot be derived. Fields: `item` = `<prd-stem>-c<n>`; `model` = `default_model` when it is `sonnet` or `opus`, else `sonnet`; `suite` = `per-item` on every card but the last, `batch` on the last; `changelog` = the text of the task item that names `CHANGELOG.md`, else empty; `## Goal` = the plan's goal (Problem Statement or `## Problem`, then the card's joined task items), plus a `Tests to write:` line naming every acceptance test id whose file is not on disk; `## Tests` = only the `path::test_name` ids in the card's acceptance text whose file exists at render time (fast-track reads a non-empty `## Tests` as the shipped spec, `skills/fast-track/SKILL.md:103-105`, so an id for a file the PRD is about to create must not land there), and when none survives, `framework` = `pytest` when the PRD names a `test_*.py`, `bash` when it names a `test_*.sh`, with `sample_test` = the first existing named test file; `## Files` = the plan's files; `## Constraints` = the PRD's `Constraints`, `Non-Goals` or `Risks` section text; `## Docs` = `CHANGELOG.md` when a task names it, else `none`; `## Gates` = the `uv run`, `python -m pytest`, `pytest` and `bash` commands quoted in the card's task items and, for a phase card, its `**Exit Criteria**` line, one per line, none chained; `## Transport impact` = `none`. Every produced card must load through `card.load_card` (`test_cards_from_prd.py` proves it on the frozen 00198 and 00188 copies: one card and two cards, and that 00201's `test_brief.py::…` ids land under `Tests to write:` with an empty `## Tests`).
- `references/lane-fast-track.md` is the runbook Phase 0 step 5.5 follows when `state.lane == "fast-track"` and lanes are on: run `cards_from_prd.py` (exit 2 sets `lane_effective: "full"`, `lane_reason: "uncardable"`, and continues to Phase 1); mirror one `state.tasks` entry per card; capture `work_start_sha`; then follow `skills/fast-track/SKILL.md` for the cards in order, opening its ledger rows with `--task <item>`, and consolidate every card's table into `dev/local/reviews/<prd-stem>-review-1.md` in the gate's shape with `reviewers:` naming the lanes that ran; every card committed closes with `phase-done --outcome lane_reviewed`; a card that parks (fast-track's `branch` exit, `SKILL.md:559-574`) stalls the PRD with `autopilot stall --site fast_track_blocked --detail "fast-track/<item>: <surviving findings>"` (the Loop-mode stall procedure, `references/recovery.md:5`), leaving the committed cards on the working branch, since each passed its roster.
- Fast-track's precondition changes in one place: when `_AUTOPILOT_LOOP` is set, the lane dispatches the Watcher subagent in the same message as the roster, with the exact prompt `skills/review-work-completion/SKILL.md:270-274` gives it, against the codex and gemini `-o` paths, and `TaskStop`s it once every lane reported. `test_fast_track_prose.py::test_headless_sessions_are_refused` (`:438`) becomes `test_headless_sessions_dispatch_the_watcher`. The roster (`SKILL.md:224-395`), Verify, the one-rework cap, Delta and the exit rule are byte-identical, and the PRD states that as a premise the way 00187 and 00194 state the review-roster sentence.
- `_AUTOPILOT_AGOGE`-style caution applies: the first headless fast-track run is the proof; the report names any lane that failed its one retry as fast-track already does.
- CHANGELOG `### Changed` under `**fast-track**` (loop mode) and `### Added` under `**run-autopilot**` (the lane runbook).

### Nice to have

- `autopilot render metrics --by-lane`: one table `lane | PRDs | sessions | wall secs | cost USD | escalated` from the session rows' `lane` and the `completed_prds` records, the batch-to-batch tuning view.
- `review-prd-backlog` (agent-skills repo) suggests `lane:` in its frontmatter-tuning table the way it suggests `catchup: skip` today (`backlog-review-2026-09-13.md:82-87`), so an author sees the classifier's verdict before the batch runs.
- The `create-prd` skill (agent-skills repo) lists `lane:` in its frontmatter key table, the same follow-up 00200 records for `session_model`.

### Out of scope

- Any change to which lenses the full lane runs, how many cycles, or the review prompts; the classifier changes which PRDs enter the lane, never what it does.
- Redesigning fast-track's roster, verify, rework or exit rule; PRD C touches its entry precondition only.
- Tier routing inside a task (`classify_tier.py`) and the session-model decoupling (00200); the classifier reads their outputs and adds no signal to either.
- Routing by measured cost or wall-clock; no threshold in this discovery is a price.
- The eligibility gate (00137), plan expansion (00189) and hold parking: composed with, not changed.
- Keyword scanning of the PRD body for algorithmic or concurrency words: PRD 00160 retired exactly that trigger because one word in a PRD body promoted every task; the author's `design: run` and `lane:` carry that judgment.

## Constraints

- Every review lens keeps running every cycle inside the full lane.
- Three lanes only: solo, fast-track, full. The lane is decided from PRD features by code; an author `lane:` override wins; Phase 0 defaults on an invalid value the way it defaults every other key (the classified lane plus one warning line; silence on absence).
- Python 3.10+, stdlib only, under `skills/run-autopilot/cli/` for the classifier and transition, `skills/fast-track/scripts/` for the cards script; prose contract tests pin every SKILL.md and reference sentence the runbooks add; acceptance is headless-checkable; no wall-clock or cost criteria.
- Nothing is live until `dev/bin/release` and `/plugin update`; the batch running today uses the installed cache 0.5.2, so none of these PRDs can self-harm and post-release signals are not completion gates.
- PRD A lands after 00200 (owns `frontmatter.py` and `routing.py` edits), 00189 (owns the Repository Structure parse and `prd_task_lines`), 00188 (owns `_append_metrics`' convergence branch) and 00198 (owns the citation-suffix regex); B after A and 00201 (owns the Phase 0 opening sentence in `phase-build.md`); C after A. B and C are independent of each other.
- Every new env knob is `_AUTOPILOT_*`, read through `env.get`, with the default behaviour unchanged when unset, except that lanes are on by default once B or C ships.

## Codebase Context

- **Relevant code**:
  - `skills/plan-tasks/scripts/classify_tier.py:113-143`: the per-task tier classifier, first match wins, `tier_reason` names the rule, a floor applied last; `:19-28` imports `is_test_path` by path; `:82-90` `is_packaging_path`. `skills/plan-tasks/SKILL.md:244-267` step 4.7 and its evidence rules at `:252-253` (`contract_edit`, `algorithmic_risk` are per-task model judgments the lane classifier deliberately does not replicate at PRD level).
  - `skills/work/scripts/work_routing.py:233-244` `is_test_path` (closed list, unmatched is production), `:247-249` `test_only_diff`.
  - `skills/run-autopilot/cli/frontmatter.py:38-62` the seven keys, defaults and `MALFORMED_WARNING`; `:104-140` `parse`; `:27-29` why `default_model` is not recognized there. `cli/test_frontmatter.py` is the test shape (three dispositions, golden fixture `scripts/golden/prd-frontmatter.md`).
  - `skills/run-autopilot/cli/__main__.py:495-530` the `frontmatter` verb (parse at `:508`, one transaction at `:524`); `:827-835` `review-once`; `:874-891` the subcommand registry.
  - `skills/run-autopilot/cli/routing.py:68-82` `build_target` (peeks at the target PRD file before any state exists), `:85-106` `_frontmatter_pins_opus` (00200 renames it to `session_model`), `:170-194` `build_model`, `:212-256` `route`; the loop stays lane-agnostic because every lane runs as `phase: "build"`.
  - `skills/run-autopilot/cli/loop.py:893-934` `_append_metrics` (the session row: `prd`, `batch`, `phase_launched`, `phase_end`, `signal`, `model`, `effort`, `cost_usd`, `tokens_out`, written to `loop-metrics.jsonl` and its `ledger/` mirror); `:1255-1271` `_launch_phase`; `:1350-1380` `_run_loop`; `:1155-1169` the `review-once` phase guard.
  - `skills/run-autopilot/cli/render_metrics.py:71-98` `phase_table` groups by `phase_launched`, so lane-routed sessions render as `build` rows until a `lane` field exists; `:63-64` `matching_rows`.
  - `skills/run-autopilot/cli/render_report.py:509` `prd_section`, `:538-539` the `Cycles:` and `Tasks:` lines, `:547` Loop Metrics, `:580` `batch_summary`, `:600-603` the completed and skipped counts, `:71` `stalled_section`.
  - `skills/run-autopilot/cli/statectl.py:349-374` `_completed_prd_record`, `:430-451` `do_complete_prd` (drains attempts to `ledger/attempts.jsonl` first).
  - `skills/run-autopilot/cli/transitions.py:34-37` `_to_review`, `:54-69` `_converged`, `:87-97` `TRANSITIONS`; `cli/schema.py:42-44` the `phase` and `next_phase` enums (no change: solo and fast-track stay `build`).
  - `skills/run-autopilot/cli/records.py:67-99` `PER_PRD_RESET_FIELDS` and the deliberately-not-reset list; `:348-399` `do_stall`.
  - `skills/run-autopilot/cli/gate.py:64-75` the verdict, tests and `codex_rung_guard` regexes, `:168-207` `run_gate`; `skills/run-autopilot/scripts/review_coverage_hook.py:85-96` `_review_converged` (`"review" in phases_completed`), `:99-146` `gate_blocks`, `:160` loop-only; `skills/review-work-completion/references/review-coverage-format.md:9-25` the required shape.
  - `skills/run-autopilot/SKILL.md:59-72` gate dispatch, `:153-178` the session loop and its decision table, `:174` the Watcher rule, `:180-196` the handoff procedure and its site table, `:211-217` loop detection and the review-file gate, `:122` un-parking.
  - `skills/run-autopilot/references/phase-build.md:57-87` Phase 0 selection, `:70` the eligibility gate (skip, never park), `:88-130` the frontmatter step, `:160-181` design, `:183-209` planning and its stall, `:211-246` work and the build-to-review handoff. `references/phase-done.md:10-62` Phase 9. `references/recovery.md:5` the Loop-mode stall procedure, `:39-61` the site slugs. `references/state-schema.md:161-189` field rows, `:440-464` promotion signals, `:466-477` skip logic.
  - `skills/fast-track/SKILL.md:27-31` the attended-only precondition, `:48-63` the card parse and its two size refusals, `:85-99` the lane plan, `:224-262` the roster and the consensus rule at `:251-253`, `:344-346` CLI reviewers as background Bash, `:361-366` "the harness re-invokes you", `:542-585` the exit rule, `:587-622` ledgers (`record_item.py` writes `phase_launched: "fast-track"` rows). `references/spec-card.md:28-51` keys and sections. `scripts/test_fast_track_prose.py:438` `test_headless_sessions_are_refused`.
  - `skills/review-work-completion/SKILL.md:264-274` the single dispatch message and the Watcher prompt, `:302` the workflow engine in that same message.
  - `~/.claude/workflows/review-fanout.workflow.js:23-29` the five dimensions, `:41-42` `SECURITY_RE`, `:147-154` `securityish`, `:156-178` `securityTriggered`, `:475-477` arming. `agents/mallory.md:3`, `agents/alice.md` (sonnet, Read and Bash), `agents/pat.md` (prompt-only).
  - `skills/work/SKILL.md:211-444` the per-task pipeline the solo lane skips (Tess 2.7, quality gate 2.8, Devon 2.85, Ivan 3, deslop 5.6, style gate 5.65, Pat 5.7) and `:459-463` step 6.5; `skills/work/references/rework-mode.md:16` the micro lane.
  - `dev/bin/release-checks:34-35` the fast-track block; `README.md:13-25` the skills table; `CHANGELOG.md:8-12` `[Unreleased]`.
- **Conventions**: decisions are pure functions in `cli/` with `unittest` or pytest beside them and golden fixtures under `cli/golden/`; skill policy is prose pinned by `scripts/test_*_prose.py`; frontmatter keys parse at Phase 0 with silent defaults and one warning per invalid value; env knobs are `_AUTOPILOT_*`; lifecycle moves go through `autopilot stall`/`park`; every subagent dispatch opens a `record_dispatch.py` row; reviewers cite `path:line`; CLI proofs run this checkout's `cli/__main__.py` with the test interpreter over a temp state, never the installed cache.
- **Integration points**: `cli/lane.py` (new), `cli/__main__.py` `_run_frontmatter`, `references/phase-build.md` step 5.5, `references/lane-solo.md` and `references/lane-fast-track.md` (new), `cli/transitions.py` (`lane_reviewed`), `cli/loop.py` `_append_metrics` (`lane`, the convergence-row branch after 00188), `cli/statectl.py` `_completed_prd_record`, `cli/render_report.py` (`Lane:` line, `PRDs by lane:`), `references/state-schema.md`, `references/batch-report-format.md`, `skills/fast-track/SKILL.md` § Preconditions, `skills/fast-track/scripts/cards_from_prd.py` (new), `dev/bin/release-checks`, `CHANGELOG.md`.
- **Similar implementations**: `classify_tier.py` (first-match rules with a recorded reason, PRD 00160); the eligibility gate (PRD 00137: a frontmatter-declared, code-evaluated pick-time decision that skips rather than parks); `policy.plan_expansion` (PRD 00189: a PRD-text parse with an `allow` override and a stall site); `session_model` (PRD 00200: a frontmatter enum that changes routing, with the create-prd follow-up in agent-skills); the fast-track `record_item.py` row (`phase_launched: "fast-track"`, `cost_usd` null when unmeasured); the review micro lane (`rework-mode.md:16`, the orchestrator edits, Pat kept).

## Approach

Brief question to section: (1) the rules, the Must-have table for PRD A; (2) the solo lane, PRD B's runbook; (3) mis-routes, PRD B's escalation checks and signals; (4) composition, below; (5) measurement, the ledger and report items of PRD A plus the nice-to-have `--by-lane` table; (6) placements, the fixture table below and Q10 in the log.

- **Chosen**: a pure PRD-text classifier with seven ordered rules and an override, run inside the existing `autopilot frontmatter` verb so `state.lane` exists before Phase 1; every lane runs as `phase: "build"` so the loop, routing, the cap hook and resume stay lane-agnostic; the solo lane is one session that mirrors the PRD's task lines into `state.tasks`, edits directly, runs the suite, checks five code-decided escalation signals, takes one zero-context review pass through fast-track's consensus rule, writes a gate-shaped review file and closes with a new `lane_reviewed` transition that appends the `review` marker; the fast-track lane renders cards mechanically, runs the existing lane per card with the Watcher in loop mode, and stalls on a parked card; escalation continues into the full review gate with every commit kept; PRD A ships the classifier in shadow (recorded and rendered, not acted on) so one batch of data exists before B and C flip their lanes live.
- **Why**: it reuses every decision shape the pack already trusts (ordered rules with a recorded reason, frontmatter defaults, artifact-based resume, the stall procedure, the review-file gate, the Watcher), adds no phase enum, no routing branch and no new session type, and keeps the settled constraint intact: the full lane's roster and cycles are untouched, and the classifier only decides who enters.
- **Composition with the neighbours (brief question 4)**:
  - 00189 plan expansion: full lane only by construction; solo mirrors task lines without planning and fast-track cards carry their own 12-path bound, so `check-plan` never sees them. A fast-track PRD that stalls through `uncardable` takes the full lane, where 00189's gate then applies.
  - 00200 `session_model`: unchanged and lane-agnostic; every lane's session runs at `session_model` or a promotion signal. `default_model` floors card and task tiers, never the session and never the lane.
  - 00137 eligibility: runs at pick time, one step before the frontmatter verb; an unmet PRD is never classified. Skips and lanes render as separate summary lines.
  - hold parking: a died solo session parks through the loop's existing retry budget; a parked fast-track card stalls with site `fast_track_blocked`; an escalated solo PRD never parks, it joins the full review. Un-parking is the documented `mv` (`SKILL.md:122`) and re-classification happens at the next Phase 0.
  - 00188 convergence row: extended in B to build-to-done exits of lane-routed PRDs, so `- Run conditions:` renders the lane's roster and counts.
  - 00201 session brief: the brief's `Where` section gains `lane:` beside `phase:` (one line in `render_brief`, listed under B's prose edits).
- **Placements of the reviewed backlog (brief question 6, accepted as the fixture set)**:

  | PRD | lane | rule | cards |
  |---|---|---|---|
  | 00187 | full | hook (`hooks/guard_push_on_critical.py`) | |
  | 00188 | fast-track | card_sized (16 paths, two phases) | 2 |
  | 00189 | fast-track | card_sized (11 paths) | 1 |
  | 00190 | fast-track | card_sized (5 paths; the bash helper is not a recognized test path) | 1 |
  | 00191 | full | hook (`autopilot_context_cap_hook.py`) | |
  | 00192 | full | design | |
  | 00194 | full | design (prose-only otherwise) | |
  | 00195 | full | design | |
  | 00196 | full | hook | |
  | 00197 | solo | no_production_code | |
  | 00198 | fast-track | card_sized (3 paths) | 1 |
  | 00199 | full | design | |
  | 00200 | full | hook | |
  | 00201 | fast-track | card_sized (10 paths) | 1 |
  | 00202 | full | hook (a string-constant edit; `lane: fast-track` is the author's remedy) | |

  Nine full, five fast-track, one solo. This backlog is meta-work on the loop itself (five hook edits, seven design runs), so the yield here is the floor; product repos carry fewer of both.
- **Rejected alternatives**:
  - `default_model: opus` as a full-lane signal: 11 of 15 stay full on an opus-pinned backlog and the key's documented meaning is the tier floor.
  - Shape-only rules ignoring `design:`: 00192's loop split becomes a card.
  - A `solo` phase enum with its own routing row and resume entry: three more touch points for what a state field carries.
  - Keyword scans for algorithmic or concurrency work: retired by PRD 00160 for promoting every task on one word; the author's signals replace them.
  - The security regex over PRD prose: `session` fires on 3 of 15 titles here; paths only at PRD time, the diff at escalation and review time.
  - Solo with one Ivan or Tess-and-Ivan: prose PRDs have no failing tests to hand over and the dispatch ceremony the lane exists to cut returns.
  - Pat as the solo reviewer: prompt-only, per-task severity ladder, cannot judge PRD compliance, output does not fit the review-file gate.
  - Escalation by restart or by parking: throws away a working change, or hands the routing back to the operator.
  - Fast-track attended-only in the loop, or collapsed to full: the middle lane never fires where the cost was measured.
  - Model-written cards: an LLM step inside routing, non-reproducible.
  - One PRD, or two: five subsystems in one plan stalls at the task ceiling; two puts four subsystems in the first.

## Success Criteria

- `uv run --no-project --with pytest --with rich --with textual python -m pytest -q skills/run-autopilot` green with: `cli/test_lane.py::test_reviewed_backlog_classifies_as_agreed` over the frozen 15 (the table above, rule and card count per PRD), one test per rule slug, `test_design_absent_counts_as_run`, `test_line_suffix_is_stripped_before_kind`, `test_invalid_override_warns_and_classifies`, `test_security_regex_fires_on_a_path_not_on_prose`; `cli/test_frontmatter.py` unchanged and `MALFORMED_WARNING` byte-identical; a `frontmatter` verb subprocess fixture echoing `lane`, `lane_reason` and `lane_effective` (and `full` for every lane under `_AUTOPILOT_LANES=off`); `test_plan_cards_joins_wrapped_task_items_before_counting` and `test_plan_cards_ignores_dependency_graph_phase_suffixes`; `cli/test_transitions.py::test_lane_reviewed_appends_the_review_marker`; `cli/test_loop.py` rows carrying `lane` and `lane_effective` and the build-to-done convergence row for `lane_effective: solo`; `cli/test_render.py` goldens with the `Lane:` line and `PRDs by lane:` summary.
- `uv run --no-project --with pytest python -m pytest -q skills/fast-track/scripts` green with `test_cards_from_prd.py` producing one card from the frozen 00198 and two from 00188 that `card.load_card` accepts, exit 2 with the field name on a PRD with 25 paths, and `test_fast_track_prose.py::test_headless_sessions_dispatch_the_watcher` plus every other pin of that file unchanged.
- Prose pins: `scripts/test_lane_prose.py` finds step 5.5 in `phase-build.md` naming the three lanes and the shadow sentence (A), the solo runbook's order and its five signals with their outcomes (B), the fast-track runbook's `uncardable` fallback and `fast_track_blocked` stall (C); `test_doc_contract.py` still green.
- `bash dev/bin/release-checks` green with the lane tests registered.
- Post-release signals, not judged in-session: the next batch's report prints a `Lane:` line on every completed PRD and a `PRDs by lane:` summary; every session row carries `lane`; no `Run conditions: no review_converged row` on a lane-routed PRD; escalations render with their signal.

## Risks

- **A hook path routes a text-only edit to the full loop (00202)**: accepted; the `lane:` override is the remedy and the fixture documents it. Softening the hook rule would send cap-hook logic edits (00191, 00196, 00200) past the loop.
- **`design:` absent means full**: conservative by design (fail expensive, never fail dumb, the `routing.py` philosophy); create-prd writes the key explicitly, and the shadow batch shows how often it fires.
- **Path extraction misses a hand-written PRD**: `unparsed` routes to full; the shadow batch's `Lane:` lines show every such PRD before any lane goes live.
- **Fast-track headless has never run**: the Watcher is the review phase's proven mechanism, the first batch is the proof, and `_AUTOPILOT_LANES=off` forces full for a whole batch.
- **The solo session's own reading shapes its code**: the zero-context review pass and the five escalation signals are the counterweight; a CRITICAL escalates without a fix attempt.
- **A HIGH fixed in solo is verified by one delta only**: a HIGH surviving the delta escalates to the full review; a LOW is never reworked.
- **Two cards, two rosters, on a 16-path PRD**: bounded by the ceiling; a fast-track roster on a small diff is unmeasured, so the `--by-lane` table is what settles whether two cards beat the loop.
- **Shadow first delays the saving by one release**: one batch of `Lane:` lines is cheap insurance against a mis-tuned rule routing a hook edit to solo.
- **create-prd and review-prd-backlog live in agent-skills**: the `lane:` key is silently ignored there until that repo learns it; recorded as follow-ups, as 00200 did for `session_model`.

## Open Questions

- Should `_AUTOPILOT_LANES` accept a lane list (`solo`, `fast-track`) to disable one lane at a time, or stay a single `off` switch? Default: single switch.
- Should the solo runbook honor `.handoff-requested` at a task boundary, or keep the hard cap as its only rotation? Default: hard cap only; a solo PRD is expected to fit one session.
- Is `render metrics --by-lane` part of PRD A or a follow-up? Default: follow-up, after the first shadow batch shows the row fields are enough.
- Does the PRD-level `lane_reason` belong in the 00201 session brief, or only `lane`? Default: both, one line.

## Discovery Log

### Inferred: What triggers this need?
**Answer**: measured, not preventive. `dev/local/notes/autoclaude-inefficiencies-2026-09-13.md` § Conclusions: one opus task costs ~200 tool calls, 60-80 min and $50-70 with 5-10 min of implementation; Devon broke the tests in every round; ~100 orientation calls per session; the design step ate a 249-call session; one review's 32 findings became 10 opus rework tasks. The full pipeline earns its cost on cross-cutting, algorithmic or security-sensitive PRDs; for prose edits, one-file fixes and test scaffolding it is a 5-10x tax over a solo session plus one review pass. Decision 2026-09-13: route by risk lane first (lever 1, est. 50-70% of batch spend).

### Inferred: The PRD-time security signal
**Answer**: paths only. `SECURITY_RE` (`~/.claude/workflows/review-fanout.workflow.js:41`) over the 15 reviewed PRDs' named paths fires on none; over their H1 titles it fires on 00196, 00200 and 00201 because `session` is in the regex. So the classifier applies the regex to paths (the exact analogue of `securityTriggered`'s `changedFiles` loop, `:161-163`), never to prose; the added/removed-line half of the trigger runs where a diff exists: the full lane's fanout at review time, and the solo lane's escalation check over `work_start_sha..HEAD`.

### Inferred: fast-track refuses headless sessions
**Answer**: `skills/fast-track/SKILL.md:27-31` refuses a run when `_AUTOPILOT_LOOP` is set, and `test_fast_track_prose.py::test_headless_sessions_are_refused` pins it (PRD 00186 § Invocation and preconditions). Two review lanes (Bob, Carl) are background Bash, which a headless turn kills ~5 s after the final result. `review-work-completion` runs the same two lanes headless by dispatching a Watcher subagent that re-runs `await_reviewer_outputs.py` (run-autopilot `SKILL.md:174`). Whether the loop may drain fast-track PRDs is therefore a decision, asked below.

### Inferred: Mechanical features of the 15 reviewed PRDs (scan 2026-09-13, HEAD 2c922c3)
Paths come from the `### Repository Structure` block and `**Location**:` lines; kinds use `work_routing.is_test_path` and `classify_tier.is_packaging_path`; hook = `hooks/` segment, `hooks.json`, or `*_hook.py`.

| PRD | default_model | design | lines | task lines | paths | hook | prod | test | doc |
|---|---|---|---|---|---|---|---|---|---|
| 00187 | opus | run | 146 | 6 | 18 | 3 | 6 | 3 | 5 |
| 00188 | opus | skip | 96 | 5 | 16 | 0 | 7 | 4 | 4 |
| 00189 | opus | skip | 93 | 5 | 11 | 0 | 4 | 3 | 3 |
| 00190 | sonnet | skip | 127 | 3 | 5 | 0 | 2 | 2 | 0 |
| 00191 | sonnet | skip | 131 | 4 | 10 | 2 | 3 | 2 | 2 |
| 00192 | opus | run | 110 | 3 | 4 | 0 | 2 | 2 | 0 |
| 00194 | opus | run | 110 | 3 | 8 | 0 | 1 | 2 | 4 |
| 00195 | opus | run | 122 | 4 | 10 | 0 | 4 | 2 | 3 |
| 00196 | opus | run | 203 | 4 | 5 | 2 | 0 | 1 | 2 |
| 00197 | sonnet | skip | 96 | 3 | 3 | 0 | 0 | 0 | 3 |
| 00198 | sonnet | skip | 110 | 3 | 3 | 0 | 1 | 0 | 2 |
| 00199 | opus | run | 286 | 8 | 8 | 0 | 3 | 4 | 1 |
| 00200 | opus | run | 309 | 8 | 11 | 2 | 2 | 3 | 4 |
| 00201 | sonnet | skip | 249 | 6 | 10 | 0 | 4 | 3 | 3 |
| 00202 | sonnet | skip | 110 | 3 | 3 | 1 | 0 | 0 | 2 |

Notes: 00194's one prod path is `dev/bin/release-checks`; 00202's hook path is a string constant edit in `autopilot_context_cap_hook.py`; 00192's prod paths are `loop.py` and the declared wildcard `loop_*.py`.

### Q1: Which author signals in PRD frontmatter send a PRD to the full lane?
**Answer**: `design: run` only. `default_model` keeps its documented meaning, the implementor tier floor, honored inside every lane (the card's `model` field in fast-track, the task tier in full); it never decides the lane. 00188 and 00189 (opus, `design: skip`) therefore leave the loop for fast-track. Rejected: opus-or-design (11 of 15 stay full, no yield on an opus-pinned backlog); shape only (00192's loop split, which needs a reviewed seam map, would become a card).

### Q2: What shape qualifies a PRD for the solo lane?
**Answer**: zero production paths. A production path is any named path that is not a test path (`work_routing.is_test_path`), a doc (`.md`, `.txt`, `.rst`), a packaging manifest (`classify_tier.is_packaging_path`) or `CHANGELOG.md`. Solo covers prose, docs, tests and config; every code change, even one file, takes the roster through fast-track (00198's regex gets five lenses). Rejected: at most one prod path (00198 solo; a subtle one-file change reviewed by one lens); at most two (00190 and 00198 solo; two files is already a cross-file change).

### Q3: How large may a PRD be and still route to fast-track?
**Answer**: at most 2 cards of at most 12 paths each (the `card.py` limit is the unit). 00188 (16 paths) becomes two cards; 00189, 00190, 00198 and 00201 one each. A PRD whose named paths exceed 24, or whose mechanical split cannot produce valid cards, falls to full with reason `uncardable`. Rejected: one card only (00188 goes full though card-shaped); one card per task line with no ceiling (review spend scales with task count).

### Q4: How does fast-track run when the classifier picks it inside an autoclaude batch?
**Answer**: amend the precondition only. In loop mode the lane dispatches the Watcher subagent in the same message as the roster, re-running `review-work-completion/scripts/await_reviewer_outputs.py` against the codex and gemini output files until `DONE`, exactly as `review-work-completion` step 5 does; the roster, verify, one-rework cap, delta review and exit rule are untouched. `test_headless_sessions_are_refused` becomes the watched-in-loop pin. Rejected: attended only with loop skips (card-shaped PRDs pile up, the lever never fires unattended); collapse to full in loop mode (the measured cost is all in unattended batches).

### Q5: How are fast-track cards produced from a PRD?
**Answer**: a mechanical script, `cards_from_prd.py`, one card per phase (at most two): `item` = `<prd-stem>-c<n>`, `model` = `default_model` or `sonnet`, `suite` = `per-item`, `changelog` = the PRD's CHANGELOG task text or empty; Goal = the Problem Statement plus the phase's task lines (must fit 40 lines); Tests = the `path::test_name` ids in the phase's acceptance text whose file exists at render time, the rest named in the Goal as tests to write (empty Tests needs `framework` and `sample_test`, which the script takes from the PRD's named test files); Files = the paths of the modules the phase's tasks name, else every PRD path (must fit 12); Constraints = the PRD's Constraints or Non-Goals section; Docs = `CHANGELOG.md` when a task names it, else `none`; Gates = the pytest and bash commands quoted in the phase's acceptance; Transport impact = `none`. A field the script cannot derive exits 2 and the PRD takes the full lane with reason `uncardable`. Rejected: hybrid (a rewritten Goal drifts from the task line reviewers judge against); model-written cards (an LLM step inside routing, non-reproducible).

### Q6: Who implements a solo-lane PRD inside the session?
**Answer**: the session edits directly, no subagent, the micro lane of `work/references/rework-mode.md` generalized to a whole PRD. It reads the PRD, writes the change and its tests (red first where a test exists), stages exactly the PRD's paths plus `CHANGELOG.md` when the change earns an entry, and commits in conventional form. Rejected: one Ivan dispatch (prose PRDs have no failing tests to hand him; the dispatch ceremony returns); Tess then Ivan per task line (most of the per-task overhead returns).

### Q7: Which single review pass closes a solo-lane PRD?
**Answer**: fast-track's consensus rule, reused verbatim: the `review-fanout` workflow when `~/.claude/workflows/review-fanout.workflow.js` is on disk, else `autopilot:alice`; inputs are the PRD, the `work_start_sha..HEAD` diff and the changed-file list, with the review-work-completion rubric and output format. The result is consolidated and written as `dev/local/reviews/<prd-stem>-review-1.md` in the shape `cli/gate.py` checks, so the done hand-off passes the review-file gate and the trail stays durable. Rejected: Alice only (no security dimension, no verification); Pat over the whole diff (cannot judge PRD compliance, output does not fit the gate).

### Q8: When a solo build trips an escalation signal, what does the session do?
**Answer**: continue. Five signals, all decided by code over `work_start_sha..HEAD`: the diff touches a hook path or a production path the PRD never named; the security trigger fires on added or removed lines (`securityTriggered` ported to Python); the review pass raises a CRITICAL; a HIGH survives the lane's one delta review; the suite is still red after the lane's one fix. On any of them the session writes `state.lane_effective = "full"` and `state.lane_escalated = {"from": "solo", "signal": <slug>}`, then runs `autopilot phase-done --outcome tasks_done`, so the full review gate takes over the finished build with every lens and its rework cycles; no commit is lost and no new machinery is added. A fast-track item that parks keeps fast-track's own exit rule: the PRD stalls to `hold/` with site `fast_track_blocked` and the branch name in the detail. Rejected: restart from `work_start_sha` (throws away a working change); park every mis-route (the operator does the routing by hand).

### Q9: How should this discovery be packaged into PRDs?
**Answer**: three sequenced PRDs. A: classifier, `lane:` key, Phase 0 routing in shadow, lane fields in the session rows, the completed-PRD record and the report. B: the solo lane runbook, its review file, the `lane_reviewed` transition and escalation (depends on A). C: `cards_from_prd.py` and fast-track's loop-mode Watcher precondition (depends on A). B and C are independent. Rejected: two PRDs (the first spans four subsystems, the shape the 2026-09-13 backlog review reshaped in 00196); one PRD (five subsystems, stalls at the task ceiling and 00189's expansion gate).

### Q10: Do the 15 placements stand as the classifier's fixture set?
**Answer**: yes, all 15 as computed by the agreed rules (9 full, 5 fast-track, 1 solo; the table in § Approach). The two arguable cases stay as evidence of the override's purpose: 00202 goes full on a hook path for a string-constant edit, 00190 goes fast-track because its bash helper is not a recognized test path. Rejected: stamping `lane:` overrides on 00202 or 00190 now (nothing is live before release, and the batch running today uses the installed cache).

### Contradiction check
- `default_model` is "honored inside every lane" (Q1) but the solo lane dispatches no implementor (Q6): resolved, `default_model` is inert in solo and the session runs at 00200's `session_model`; `session_model: opus` is the author's tool.
- The solo review arms security through the fanout (Q7) while a security-tripping diff escalates (Q8): resolved by order, the escalation checks run at the end of the build before any review, so such a diff never gets the single-lens pass.
- "A production path the PRD never named" (Q8) against zero production paths (Q2): for a solo PRD the signal reduces to any production or hook path in the diff.
- The Watcher amendment (Q4) against the settled "do not redesign fast-track": scoped to the entry precondition; PRD C states the roster, verify, rework and exit sections as a byte-identical premise.
- Two cards (Q3) against one card per phase (Q5): one whole-PRD card when it fits, else one per phase for a two-phase PRD, else `uncardable`.
- Closing build-to-done directly would bypass `review_coverage_hook`, which gates on `"review" in phases_completed`: resolved, `lane_reviewed` appends the marker, so the hook checks the lane's review file with `--require-codex-guard` and the file carries `codex_rung_guard: not fired`.
- 00188's convergence row is emitted only on review-launched sessions: resolved, PRD B extends the emission to build-to-done exits of lane-routed PRDs.
