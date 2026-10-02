# Backlog review - claude-autopilot - 2026-09-13

Verdict: GO (after the apply pass: 0 Blocking open, reshape applied; 5 Non-blocking line-reference refreshes rejected by the user and left as is).

Scope: 14 PRDs in `dev/local/prds/backlog/` (00187-00192, 00194-00201). wip: 00186 (in flight,
cycle 2). hold: 00110. Discovery: 00157, 00177, 00193. Plugin cache running the batch: 0.5.2
(released today); nothing here is live until the next `dev/bin/release` + `/plugin update`.
Lens D grounding ran as five parallel read-only agents against HEAD `2c922c3`; every claim
below cites their evidence. Budget and tier questions consulted plan-tasks 0.5.2 steps 4-4.7.

## Map
| # | PRD | template | lines | subsystems | depends on | verdict |
|---|---|---|---|---|---|---|
| 00187 | keep cap-out CRITICALs under custody | standard | 146 | cli/records, cli/custody (new), hooks/, phase-review, phase-build | - | READY |
| 00188 | record convergence cap and roster per PRD | minimal | 96 | cli/loop `_append_metrics`, render_metrics, render_report, phase-review | 00185 (done) | FIX (line refs) |
| 00189 | stall to split on plan expansion | minimal | 93 | cli/policy, frontmatter, check-plan, plan-tasks prose | 00188 (records planned) | FIX (stale text) |
| 00190 | bind the codex-run tests and dedupe their split | standard | 127 | use-codex tests, release-checks, CHANGELOG | - | READY (line refs drifted, non-blocking) |
| 00191 | clear the handoff marker at phase edges | standard | 131 | cap hook (marker JSON), cli/handoff (new), work 6.5 | - | READY |
| 00192 | split cli/loop.py and its tests under the cap | standard | 110 | cli/loop.py, test_loop.py | 00188, 00191 | READY (note) |
| 00194 | design CRITICAL rework before task dispatch | standard | 110 | design-solution, phase-review, recovery | 00187 | READY |
| 00195 | mint hold stubs for unowned deferred findings | standard | 122 | cli/triage (new), __main__, phase-done | 00187 | READY |
| 00196 | guard review-phase rework sessions (renamed, reshaped) | standard | 203 | cap hook, phase-review Phase 4 | 00191 | READY |
| 00197 | carry style limits into the Tess prompt | minimal | 96 | tess-prompt, work SKILL 2.8 | 00202 (same file, 00202 runs later) | READY |
| 00198 | normalize reviewer file citations | minimal | 105 | consolidate_findings, agents/*.md | - | READY |
| 00199 | loop guard rails for sleep, limits, stand-downs | standard | 286 | cli/loop, usage_limit, pause, run-autopilot SKILL | 00192 | READY |
| 00200 | usage and turn headroom handoff, session_model | standard | 292 | cap hook, frontmatter, routing, work 6.5 | 00191, 00196 | READY (absorbed turn headroom) |
| 00201 | session brief at every gate transition | standard | 249 | cli/statectl, cli/brief (new), runner, phase-build/review | - | READY |
| 00202 | commit subagent output before a rotation can lose it (new) | minimal | 110 | work SKILL 2.85/2.9, rotation envelope text | 00196, 00200 | READY |

Line counts over ~200 on 00196, 00199, 00200 and 00201 are the standard template's section overhead on 2-3 subsystem PRDs with 3 phases each; each task is small and none approaches the 150K per-task budget. Not a stall risk; noted, not reshaped further (the user accepted 00200's growth with the reshape).

Hygiene: filenames all `NNNNN-slug-v1.md`; sequence unique across backlog/wip/done/hold/discovery
(00193 is the discovery doc, no PRD claims it). Drain order by number satisfies every stated
dependency (00187 -> 00194/00195; 00191 -> 00196 -> 00200; 00192 -> 00199); no renumbering needed.

## Findings

### Blocking
- [00196, 00197, 00198] A/step 1 citation: all three cite `dev/local/tmp/00051-autoclaude-inefficiencies.md`, a file in the agent-skills repo's 7-day tmp dir; repo-relative it resolves to nothing -> fails as: stall (an implementor premise check trips on the dangling pointer). Fix: copy the report to `dev/local/notes/autoclaude-inefficiencies-2026-09-13.md` in this repo and cite that path.
- [00196] E collision with 00191: 00191 (lands first) pins "retain the build-only ... no-write guards" and a hook test for "review-phase no-write"; 00196 widens the guard to review-with-rework and never names that test -> fails as: rework thrash (red test the PRD did not predict). 00196 also re-specifies the step-6.5 `next_phase` preservation that 00191's "Step 6.5 honours only its own phase" already owns. Fix: 00196 Phase 0 names 00191's review-phase hook test as repointed to "review without rework"; drop 00196's task-boundary-handoff edit; keep the hook rotation `next_phase = phase` and the Phase 4 skip.
- [00199] B/D: the ask-first stand-down's writer test keys on a `Claude-Session:` commit trailer; `git log -200 --format=%B | rg Claude-Session:` returns 0 in this repo (aegis `validate_commit_msg.py` rejects trailers) -> the rule never fires and a silent writer peer never pauses the batch -> fails as: wrong-TDD lock-in (tests pin a dead predicate) and undoes 00172's protection. Fix: writer evidence = uncommitted changes to tracked files (`git status --porcelain` non-empty on tracked paths) OR `state.json`/contract-card mtime later than this batch's last `leave` handoff row in `dispatch-metrics.jsonl`. Decision walked.
- [00196] B: Success Metric 1 ("no review row with `cost_usd: null`") is unfalsifiable: the killed 10800 s row omits `cost_usd` entirely (loop-metrics.jsonl, 99 rows, zero nulls) -> fails as: rework thrash (a vacuous criterion). Fix: "no `phase_launched: review` row with `wall_secs >= 10800`".
- [00196] A/D: `_rotation_instructions(limit, phase)` changes a signature that `test_rotation_instructions_takes_only_limit_parameter` (test file :638) pins; the PRD names no repoint -> rework thrash. Fix: name it in Phase 0 acceptance.
- [00200] C/D: (a) "added to `records.PER_PRD_RESET_FIELDS`" contradicts "re-derived like `doubt_reviewer`" (records.py:95-96 keeps the frontmatter enums OUT of that list); (b) acceptance ids `file::test_x` but the hook test file is unittest-class based; (c) four signal-1 routing tests (test_routing.py:158, :166, :178, :254 parametrized grammar) need repointing and are unnamed; (d) `build_model` takes `(state_path, prds_dir, ledger_path, deferred_dir)`, not a PRD path; (e) `design-rationale.md` has no `default_model` mention while `model-ladder.md:303`, `state-schema.md:453` and `:464` do; (f) `SOFT_CAP` prose at hook :21/:28/:79/:166 and `task-boundary-handoff.md:7` uncovered; "frontmatter recognizes six keys" is seven -> fails as: wrong-TDD lock-in. Fix: edits as listed.
- [00201] D: `build_argv`/`spawn` have no `cwd` (runner.py:158, :219); `spawn` already receives `autopilot_dir` -> spec the brief check on `autopilot_dir / "session-brief.md"`; `test_statectl_new_task_verbs.py` lives in `scripts/`, so the Phase 1 exit criterion (`pytest -q skills/run-autopilot/cli`) never runs the verb's tests; fixture dir `cli/fixtures/` contradicts the `cli/golden/` convention; `test_doc_contract.py` covers only `autopilot` subcommands; phase-build.md has no `jq` reads to fold -> fails as: stall / rework thrash. Fix: edits as listed.
- [00198] B/D: the proposed regex cannot strip `(lines 18-22, 423)` (alice-output-00186c1.txt:5, a comma-separated multi-range), its `$` binds only the second alternative, and the fixed-point loop is stated as an aside; the Carl fixture holds zero findings (`[CARL] No issues found`), so `[2/4]` needs `total_agents=4` explicit -> fails as: wrong-TDD lock-in. Fix: regex `(?:\s*\(lines?\s+\d[\d,\s-]*\))|(?::\d+(?:-\d+)?)$` applied until the string stops changing (required), fixture case passes `--agents 4`.
- [00199] A/D: "§ Stand-down procedure" is not a heading; it is the bold run-in paragraph at SKILL.md:168 inside `## Session Loop` -> the prose test as specified pins nothing -> coverage/rework thrash. Also `_AUTOPILOT_NET_RETRIES_MAX` (3) wraps the poll, so the sleep burns 3 x 1800 s, and the loop-metrics row carries no `stood_down` today (two fields to add, not one). Fix: pin the paragraph, state the probe budget per retry, add both fields.

### Non-blocking
- [00188] D: 11 line references drifted (loop.py `_append_metrics` :880 -> :893, call sites :1188/:1254 -> :1197/:1368, `next_phase` read :730 -> :743, try :892-919 -> :906-931; render_report `- Tasks:` :441 -> :539; render_metrics :36-58 -> :38-60, :24 -> :26, :56 -> :58; test_loop :647 -> :683, :671 -> :707; test_render :60 -> :58, :93 -> :91). Every `rg` premise count still holds. Fix: refresh.
- [00189] D: "backlog 00179-00187" is stale (00180-00185 done, 00186 wip, 00179 absent); `schema.validate` is :161-200+, not :156-185. Fix: refresh.
- [00190] D: `:434` and `:454` are banner lines (cases run :433-453 and :453-460+); "239 byte-identical lines" measures 253. Fix: refresh; tasks already re-check premises.
- [00192] D: `test_loop_review_once.py` (189 lines) already occupies the `test_loop_*.py` wildcard row. Fix: name it in Non-Goals as untouched.
- [00194, 00195] D: "verify/register in release-checks" - no `cli/` test is in the gate today, so "verify" always resolves to "register". Wording only.
- [00200] D: "`/autopilot:work` reads the marker at other points" is not true of the prose (step 6.5 and its reference are the only readers); the placement feature reduces to one clarifying sentence. Keep, reword.
- [00188, 00189] A: minimal template carrying five modules and an extra "Post-release signals" section. Fit is borderline; the Dependencies section covers planning. No change.
- [00199] traceability: the discovery's caffeinate must-have is met by `autoclaude()` (`caffeinate -is`, development.plugin.bash:401); the PRD states it as a premise. Satisfied, not dropped.
- [00199] discovery open question (five-hour vs seven-day window): apply the discovery's stated default, `rateLimitType == "five_hour"` only.

### Questions
- None left open: the two 00193 open questions are resolved by their stated defaults (five-hour window; fixed 150K first-task estimate in 00200).

## Reshapes
- [00196 + 00200] F/E: 00196 is 276 lines over three subsystems and three concerns, and its turn-headroom capability edits the same hook function, task-start record and one-shot marker as 00200's usage-headroom. Proposal: move "Turn budget with a boundary form" (TURN_TRIPWIRE 450, `calls_at_start`, headroom rule) into 00200 as a third capability sharing one `headroom_exhausted(usage, calls)` predicate; split "Lossless rotation" (tests commit before Devon, `chore(<scope>): wip - rotated mid-task`, step-2 resume) into new PRD 00202; 00196 keeps the phase guard, phase-aware rotation and the Phase 4 skip.

## Gaps
- 00200's `session_model` key must reach the create-prd skill's frontmatter list (agent-skills repo); no PRD exists there. Durable home: a one-line PRD or chore in agent-skills.
- 00201's brief reaches non-loop sessions only through a `startup`-matched host hook (buvis dotfiles); out of this repo, noted in the PRD.
- 00196's `wip - rotated mid-task` commits are never squashed; accepted in its Risks.
- No strategic gap: the set follows discovery 00193 and the ddb assessment; `/assess-evolution` not needed for this batch.

## End state after this batch
The loop bounds every session (usage and turn headroom at task boundaries, a guarded review-phase
rework, a wall-cap that no longer fires), yields the five-hour window between loops, survives a
lid-close, pauses only for a writer peer, and reads a rendered brief instead of re-deriving state.
Cap-outs leave custody, get a reviewed rework design, and mint owners for deferred findings; plans
that outgrow their PRD stall to split; loop.py fits the file cap. Left half-finished: the handoff
marker keeps legacy plain-text parsing beside JSON (00191), rotation scars stay in git history
(00196/00202), and `default_model: opus` PRDs already filed silently lose the opus orchestrator
until they add `session_model: opus` (00200 release note).

## Frontmatter tuning
| PRD | suggestion | why |
|---|---|---|
| 00197 | `catchup: skip` | two prose lines and one gate call; no project context needed |
| 00198 | `catchup: skip` | regex plus persona sentence; fixture is in-repo |
| 00200 | keep `design: run` | two subsystems and a routing change |

## Decisions applied
- 00199 writer test: applied - dirty tracked path or state/card mtime later than the batch's last `leave` row; three `condition` values; five-hour window only; prose test pins the bold paragraph by its literal opening; probe budget per `_AUTOPILOT_NET_RETRIES_MAX` retry; paused row gains `stood_down` and `stood_down_condition`.
- 00196 reshape: applied - turn headroom moved into 00200 (one `_headroom_exhausted(total, count, ...)` predicate, `TURN_TRIPWIRE` 450 there); lossless rotation split to new 00202; 00196 renamed `00196-guard-review-phase-rework-sessions-v1.md` (203 lines) and keeps the phase guard, phase-aware rotation and Phase 4 skip.
- 00196 vs 00191: applied - 00196 names 00191's review-phase no-write case as repointed (premise re-check), drops its task-boundary-handoff edit, names `test_rotation_instructions_takes_only_limit_parameter` as rewritten; success metric now `wall_secs >= 10800`.
- Citations: applied - report copied to `dev/local/notes/autoclaude-inefficiencies-2026-09-13.md`; 00196, 00197, 00198 cite it. Post-apply citation check: only declared outputs remain (00187 custody marker, 00201 session brief, 00197 per-task diff).
- 00200 contract fixes: applied - reset-list clause dropped (re-derived like `doubt_reviewer`), class-qualified test methods, four signal-1 routing tests named including the parametrized grammar table, `build_model` inputs corrected, doc edits pointed at `model-ladder.md:303` and `state-schema.md:453/:464`, `SOFT_CAP` prose sites covered, "eighth key".
- 00201 contract fixes: applied - brief check on `autopilot_dir` inside `spawn` (no `cwd`), Phase 1 exit criterion includes `scripts/test_statectl_new_task_verbs.py`, expected file under `cli/golden/expected/`, `test_doc_contract.py` and `jq` clauses dropped, prose test matches any statectl path prefix.
- 00198 fixes: applied - anchored regex accepting comma-separated ranges, fixed-point loop stated as required, `test_comma_separated_ranges_are_one_suffix`, fixture case passes `total_agents=4`.
- Non-blocking line-reference refreshes (00188, 00189, 00190, 00192, 00200 wording): rejected by the user; left as is. Every `rg` premise count in those PRDs still holds, so no task stalls on them.
- Lens A re-run on 00196, 00197, 00198, 00199, 00200, 00201, 00202: every template heading present and in order; `#### Feature:` names unique; sequence 00196-00202 unique across backlog/wip/done/hold/discovery.

- Post-review addendum (19:30, live evidence from the 00187 build session): 00200 gains two sentences and one task - a breach with no in-progress task (`unknown`) never counts toward the livelock guard, and the build gate applies the headroom rule at the design->plan and plan->work edges. 00187's design step used 249 calls and 338K before planning; the hook wrote `.handoff-requested` with task `unknown`, and a second `unknown` breach would have parked the PRD as oversized. Lens A unchanged (task added under Phase 2).

Final verdict: GO. Drain order by number: 00187, 00188, 00189, 00190, 00191, 00192, 00194, 00195, 00196, 00197, 00198, 00199, 00200, 00201, 00202. Nothing here is live until `dev/bin/release` + `/plugin update` after the batch.
