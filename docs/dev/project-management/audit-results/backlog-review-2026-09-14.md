# Backlog review - claude-autopilot - 2026-09-14

Verdict: GO (after the apply pass: 0 Blocking open, the Question resolved by an AGENTS.md
edit committed to buvis, 1 Non-blocking rejected by the user and left as is).

Scope: 17 PRDs in `dev/local/prds/backlog/` (00188-00192, 00194-00202, 00204-00206).
wip: 00187 (live loop, review phase, cycle-1 rework tasks 11-12 in flight while this
review ran). hold: 00110. Discovery: 00157, 00177, 00193, 00203. Plugin cache running
the batch: 0.5.2; nothing here is live until the next `dev/bin/release` + `/plugin update`.

Delta since the 2026-09-13 review (GO): 00187 moved to wip and its build landed
(custody core, push guard, Phase 0/phase-review/recovery/state-schema prose);
00204-00206 were created from discovery 00203. The 14 PRDs carried over were
re-grounded only on premise commands, named symbols and the files 00187 touched;
pure line-number drift is listed, not raised (the user rejected refreshes on 09-13).

Grounding ran inline with `rg` (six parallel grounding agents died on the account's
session rate limit, which the live loop shares). Measured at HEAD `1bb9b22`; the
tree moved four times during the review (00187 rework commits), so line numbers
below are as of that HEAD. Budget/tier questions consulted plan-tasks 0.5.2 steps 4-4.7.

## Map
| # | PRD | template | lines | subsystems | depends on | verdict |
|---|---|---|---|---|---|---|
| 00188 | record convergence cap and roster per PRD | minimal | 96 | cli/loop, render_metrics, render_report, phase-review | 00185 (done) | READY |
| 00189 | stall to split on plan expansion | minimal | 93 | cli/policy, frontmatter, check-plan, plan-tasks prose | 00188 | READY |
| 00190 | bind the codex-run tests and dedupe their split | standard | 127 | use-codex tests, release-checks | - | READY |
| 00191 | clear the handoff marker at phase edges | standard | 131 | cap hook, cli/handoff (new), work 6.5 | - | READY |
| 00192 | split cli/loop.py and its tests under the cap | standard | 110 | cli/loop.py, test_loop.py | 00188, 00191 | READY |
| 00194 | design CRITICAL rework before task dispatch | standard | 110 | design-solution, phase-review, recovery | 00187 (wip) | READY |
| 00195 | mint hold stubs for unowned deferred findings | standard | 122 | cli/triage (new), __main__, phase-done | 00187 (wip) | READY |
| 00196 | guard review-phase rework sessions | standard | 203 | cap hook, phase-review Phase 4 | 00191 | FIX (test name) |
| 00197 | carry style limits into the Tess prompt | minimal | 96 | tess-prompt, work SKILL 2.8 | - | READY |
| 00198 | normalize reviewer file citations | minimal | 110 | consolidate_findings, agents/*.md | - | READY |
| 00199 | loop guard rails for sleep, limits, stand-downs | standard | 286 | cli/loop, usage_limit, pause, SKILL.md | 00192 | READY |
| 00200 | usage/turn headroom handoff, session_model | standard | 309 | cap hook, frontmatter, routing, work 6.5 | 00191, 00196 | READY |
| 00201 | session brief at every gate transition | standard | 249 | cli/statectl, cli/brief (new), runner, phase-build/review | - | READY |
| 00202 | commit subagent output before a rotation | minimal | 110 | work SKILL 2.85/2.9, rotation text | 00196, 00200 | READY |
| 00204 | classify PRDs into effort lanes (shadow) | standard | 531 | cli/lane (new), frontmatter verb, schema, loop, statectl, render_report, phase-build 5.5 | 00188, 00189, 00198, 00200 | FIX |
| 00205 | run solo-lane PRDs in one session | standard | 436 | cli/lane, lane-check verb (new), transitions, records, loop, brief, lane-solo.md (new) | 00201, 00204 | FIX |
| 00206 | render fast-track cards, run the lane in the loop | standard | 365 | fast-track/cards_from_prd.py (new), fast-track SKILL, lane-fast-track.md (new) | 00204, 00205 | FIX |

Hygiene: filenames all `NNNNN-slug-v1.md`; sequence unique across backlog/wip/done/hold/discovery
(00193 and 00203 are discovery docs). `check_links.py`: 9 hits under backlog/wip, all forward
references to outputs the citing PRD creates (session-brief.md, test-diff-<id>.txt, the 00206
roster snapshot, the 00187 marker) - no citation findings. No stubs, `(guess)`, TBD or
attended-only markers anywhere in the backlog (control search proved the pattern). Drain order
by number satisfies every stated dependency; no renumbering needed.

Grounding results (premise commands run verbatim at HEAD): every skip-and-report `rg`
premise in 00188, 00189, 00190, 00191, 00196, 00197, 00198, 00199, 00200, 00201, 00202,
00204, 00205 and 00206 returns what its PRD expects today (counts and headings), with two
exceptions raised below (B1: 00204/00205 premises on `cli/loop.py` are invalidated by 00192
before they run; N1: 00196 names a test that does not exist under that name).

## Findings

### Blocking
- **B1** [00204, 00205] E cross-invalidation with 00192 (lands first): 00204 Feature "Session
  row fields" and Phase 1 task 2 premise-check `rg -n 'review_converged' skills/run-autopilot/cli/loop.py`;
  00205 Feature "Convergence row" and Phase 1 task 2 premise-check
  `rg -n 'phase_launched == "review"' skills/run-autopilot/cli/loop.py`. 00192 moves
  "session spawning/metrics" and "decision/control flow" (i.e. `_append_metrics`, `_decide`)
  into `loop_*.py` siblings and keeps only re-exports in `loop.py`, so both commands return
  0 hits at execution time -> fails as: stall (premise fails, task skipped, telemetry never
  lands; feature review then reworks). 00199 already handles the same hazard ("wherever
  00192 put it"). Fix: word both locations as "`cli/loop.py`, or the sibling 00192 extracted
  it to" and run the premises over `skills/run-autopilot/cli/loop*.py`.
- **B2** [00206] C/wrong-TDD lock-in: Phase 0 acceptance names
  `test_raw_00189_is_refused_on_a_relative_path` (`cli/test_policy.py`). 00189's named paths
  come only from its 11 `**Location**:` spans (00204's own test: "the frozen 00189 yields 11"),
  and all 11 are repo-relative (`skills/run-autopilot/cli/test_policy.py` etc.); `cli/test_policy.py`
  appears only in task text, which `named_paths` never reads. The raw 00189 therefore renders
  ONE card (`sample_test` = `skills/run-autopilot/cli/test_policy.py`) and the test as named can
  only pass by bending `named_paths` -> fails as: wrong-TDD lock-in. Fix: replace with
  `test_raw_00189_renders_one_card_load_card_accepts` (11 files, one card, `suite: batch`).
- **B3** [00205] E/rework thrash: releasing `solo` (`RELEASED_LANES = {"full", "solo"}`) breaks
  00204's `test_effective_forces_full_when_off_or_unreleased` whenever that test uses `solo` as
  its unreleased example; 00205 names no repoint (00206 does for `fast-track`) -> a red test the
  PRD did not predict. Fix: 00204 pins the unreleased case with `RELEASED_LANES` monkeypatched
  to `{"full"}` (survives every later release); 00205 Phase 0 task 1 adds "still passes".

### Non-blocking
- **N1** [00196] D: Phase 0 task 1 acceptance says `test_work_phase_is_noop` (:143) unchanged;
  the test at :143 is `test_noops_on_work_phase`. Vacuous "unchanged" clause. Fix the name.
- **N2** [00206] B: the byte-identity premise saves `sed -n '222,585p' skills/fast-track/SKILL.md`
  "to `dev/local/tmp/00206-roster-before.txt`"; the natural shell redirect into `dev/local/` is
  blocked by aegis `block_devlocal_redirects.py` (block, not a hang). Say "with the Write tool"
  or compare against `git show HEAD:skills/fast-track/SKILL.md` by heading.
- **N3** [00206] D: "three non-repo-relative paths" then lists five; 00188 has seven
  (`cli/__main__.py`, `cli/test_loop.py`, `cli/test_render.py`, `cli/golden/metrics-render.jsonl`,
  `cli/golden/expected/report-section.md`, `state-schema.md`, `batch-report-format.md`). The
  repaired fixture must fix all seven or `load_card` refuses; the count only misleads.
- **N4** [00204, 00206] G: fixture duplication. 00204 freezes 15 PRDs (~230KB) under
  `cli/golden/lanes/`; 00206 freezes raw 00188/00189/00201 again under
  `fast-track/scripts/fixtures/lanes/`. Read 00204's copies by path; keep only the repaired
  00188 and the synthetic 25-path PRD new.
- **N5** [00204] G/C: `named_paths` re-implements the tree-glyph walk that 00189 implements in
  `policy.prd_modules` (00204 says "the walk PRD 00189 gives" but lane.py imports nothing from
  policy). Two parsers of one grammar in one package; a reuse-lens reviewer will flag it.
  Option: 00189 exports `prd_tree_paths(text)`, 00204 builds `named_paths` source (1) on it.
- **N6** [00204] D line drift after 00187 task 4: `phase-build.md` premise ":88 reads `### Frontmatter parse (step 5)`, :132 reads `## Phase 1: Catchup`" is now :97/:141 (the
  rg command still finds both headings); `render_report.py` :509/:539/:580/:603 -> :524/:554/:595/:618; `__main__.py` :524/:541 -> :534/:551, `_SUBCOMMANDS` :874-891 -> :972; `records.py:98` -> :94-98. Only the phase-build premise states lines as the fact; reword to heading existence.
- **N7** [00205] D drift: `custody.git_argv` :126-131 -> :133-139 (premise `rg -n '^def git_argv'` holds); `_SUBCOMMANDS` -> :972; `state-schema.md:440` promotion signals moved.
- **N8** [00206] B: runbook step (4) "follow `skills/fast-track/SKILL.md` from § Card to § Exit as
  written" does not say whether the loop session invokes `/autopilot:fast-track <card>` (placeholders
  resolve) or Reads the file (the pack banner covers hand-substitution). State the invocation.
- **N9** [00204] F: 531 lines, 12 features, 6 tasks (2.6x the split threshold). Kept: the
  A/B/C packaging was decided in discovery 00203 Q9, and no task nears the 150K budget
  (largest, telemetry, ~126K peak, plan-tasks splits it at the file boundary). Suggest `rework_cap: 3`.
- **N10** [00204] wording: report-summary golden "its two records are bare strings" - one is a bare
  string, one a pre-lane dict; the `unclassified 2` count is right either way.
- **N11** [00201, surfaced by 00206's card model] C: the tree omits `scripts/test_statectl_new_task_verbs.py`,
  which Phase 1 edits. Harmless in the full lane (plan-tasks reads the tasks) and 00201 drains
  full before 00206 exists; but a fast-track card's allowlist IS the tree, so PRDs meant for the
  lane must list every file a task touches. A create-prd convention (agent-skills), see Gaps.

### Questions
- **Q1** [00205] H goal alignment: `~/.claude/AGENTS.md` Workflow rule: "every review cycle runs
  all lenses - consensus (Alice), blind/PRD-only (Blake), doubt+de-slop (Bob) - regardless of how
  small, simple, or well-specified the PRD looks". The solo lane closes a PRD on ONE zero-context
  Alice pass (no Blake, no Bob). Discovery 00203 (elicited with the user 2026-09-13) designs
  exactly that and scopes the all-lenses constraint to the full lane; the rule text does not.
  Nothing mechanical fights it (the coverage gate checks the file's own `reviewers:` list),
  but reviewers in 00205's own review may cite the rule. Needs the user's call: amend the rule
  (scope it to the full lane; lane routing is code-decided), widen the solo pass to Blake+Bob
  (keeps the rule, loses most of the saving), or HOLD 00205.

## Reshapes
- None proposed. 00204-00206 sizes (531/436/365) exceed create-prd's ~200-line rule but follow
  the discovery's user-decided packaging; per-task budgets stay under 150K.

## Gaps
- `lane:`, `session_model:` and `plan_expansion:` frontmatter keys are unknown to `create-prd`
  and to this gate's lens A (agent-skills repo); after the batch, future PRDs using them will be
  flagged as unrecognized fields here. Durable home: one chore PRD in agent-skills (00200 and
  00204 CHANGELOG entries record the follow-up).
- `autopilot render metrics --by-lane` (discovery 00203 nice-to-have): follow-up after the shadow batch.
- create-prd path convention for lane-routed PRDs (N11): every task-touched file in the tree,
  repo-relative, no globs - agent-skills.
- Q1's outcome needs a durable home: an AGENTS.md edit (buvis) or a 00205 edit.
- No strategic gap: the set follows discovery 00193, 00203 and the ddb assessment; `/assess-evolution` not needed.

## End state after this batch
The loop bounds every session (usage and turn headroom, guarded review-phase rework, no wall-cap
kills), yields the five-hour window between loops, survives a lid-close, pauses only for a writer
peer, and reads a rendered brief instead of re-deriving state. Cap-outs leave custody (00187, landing
now), get a reviewed rework design, and mint owners for deferred findings; plans that outgrow their
PRD stall to split; loop.py fits the file cap. On top of that, every PRD is classified into a lane in
shadow (00204), then the solo lane (00205) and the fast-track lane (00206) go live: prose/test-only
PRDs build in one session with one review pass, card-sized PRDs run the five-lens fast-track roster
per card inside the batch. Left half-finished: the handoff marker keeps legacy plain-text parsing
beside JSON (00191); rotation scars stay in git history (00202); `default_model: opus` PRDs already
filed lose the opus orchestrator until they add `session_model: opus` (00200); two tree-glyph
parsers coexist (N5) unless shared; the agent-skills side (create-prd, this gate) does not know
the three new frontmatter keys until a follow-up lands there.

## Frontmatter tuning
| PRD | suggestion | why |
|---|---|---|
| 00204 | `rework_cap: 3` | 12 features across 8 files; the 09-13 pattern for wide PRDs (00190-00192) |
| 00205 | `rework_cap: 3` | a security-regex port, a new transition and a git-reading verb |
| 00197, 00198 | `catchup: skip` | carried from 09-13 (not applied then); in-repo prose and fixture work |

## Decisions applied
- B1: applied - 00204 (Feature "Session row fields", tree row, Phase 1 task 2) and 00205
  (Feature "Convergence row", tree row, Phase 1 task 2) read "or the sibling 00192 extracted
  it to"; both premise commands run over `skills/run-autopilot/cli/loop*.py`.
- B2: applied - 00206's 00189 case is now `test_raw_00189_renders_one_card_load_card_accepts`
  (11 files, one card, `suite: batch`, `sample_test` = `skills/run-autopilot/cli/test_policy.py`).
- B3: applied - 00204's `test_effective_forces_full_when_off_or_unreleased` monkeypatches
  `lane.RELEASED_LANES` to `{"full"}` for the unreleased case; 00205 and 00206 say it still
  passes unchanged (00206's "updated so fast-track is released" reworded).
- Q1: applied - `~/.claude/AGENTS.md` Workflow rule gains the lane scope sentence (full lane and
  fast-track rosters; lane routing is code-decided; the solo one-pass review is the user's
  design). buvis commit `65451e08`, pushed.
- N1: applied - 00196 names `test_noops_on_work_phase`.
- N2: applied - 00206 saves the roster snapshot with the Write tool (aegis blocks the redirect).
- N3: applied - 00206 lists the seven non-repo-relative 00188 paths.
- N4: applied - 00206 reads the raw 00188/00189/00201 from 00204's `cli/golden/lanes/` by path
  (premise: 15 files there); its own fixtures are the repaired 00188 and the 25-path PRD.
- N5: rejected by the user - two tree-glyph parsers (policy.prd_modules, lane.named_paths) stay.
- N6: applied - 00204's phase-build premise states heading existence and order, no line numbers.
- N7, N10, N11: recorded only (line drift / wording / a create-prd convention gap).
- N8: applied - 00206 runbook step (4) invokes `/autopilot:fast-track <card path>` through the
  Skill tool per card, no `--push`, never Reads the SKILL.md to follow it by hand.
- N9: applied - `rework_cap: 3` on 00204 and 00205; `catchup: skip` on 00197 and 00198.
- Lens A re-run on 00196, 00197, 00198, 00204, 00205, 00206: every template heading present and
  in order; `#### Feature:` names unique; frontmatter fields recognized with valid values.
  Post-apply citation check: only declared outputs remain (00201 brief, 00197 per-task diff,
  00206 roster snapshot).
- Live-loop note: 00187 completed and the loop pulled 00188 into `wip/` while this review ran;
  no edit targeted 00188 or 00187. The report's HEAD stamp (`1bb9b22`) predates that move.

Final verdict: GO. Drain order by number: 00188 (wip), 00189, 00190, 00191, 00192, 00194,
00195, 00196, 00197, 00198, 00199, 00200, 00201, 00202, 00204, 00205, 00206. Nothing here
is live until `dev/bin/release` + `/plugin update` after the batch; the agent-skills
follow-ups (frontmatter keys `lane`, `session_model`, `plan_expansion`; the lane path
convention) are the Gaps above.
