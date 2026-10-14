# Backlog review - claude-autopilot - 2026-10-14

Verdict: GO

Run under the standing authorization (`~/.claude/AGENTS.md` § Autonomy, 2026-10-14): findings were adjudicated by the agent and applied in one pass; no per-finding walkthrough. Mechanical gates: `check_links.py` 0 findings under `prds/backlog` or `prds/wip` (492 elsewhere, all in `designs/` and old audit results); `ground_prd.py` over the nine PRDs `{"blocking": 0, "unverified": 0}` before and after the apply pass. Law loaded from `~/.agents/skills/create-prd/SKILL.md` and all three `assets/` templates; budget and tier rules from the installed `autopilot:plan-tasks` 0.9.0 steps 4-4.7. Lens D ran inline with `rg` (every citation in the nine PRDs was re-read against HEAD today while the PRDs were written or folded); no subagent fan-out.

## Map
| # | PRD | template | lines | subsystems | depends on | verdict |
|---|---|---|---|---|---|---|
| 00277 v2 | catch-critical-rows-in-every-shape | minimal | 70 | cli/gate.py, two gate test files, CHANGELOG | none (supersedes its own v1) | FIX -> READY |
| 00306 | refuse-tracked-verify-log | minimal | 66 | cli/__main__.py `_refuse_verify_log`, cli/verification.py `_lock_and_check` | none | READY |
| 00307 | guard-citations-and-replay-contract | minimal | 84 | hooks/guard_phase_delegation.py, dev/bin replay script | none | READY |
| 00308 | reviewer-lane-resilience | standard | 169 | review-work-completion prose, use-gemini runner, work/record_dispatch.py, replay script | none | READY |
| 00309 | loop-friction-verbs | minimal | 98 | cli markers verb, scripts/statectl.py, work/record_dispatch.py, cli/brief.py, three prose sites | none (sibling of 00308 in record_dispatch.py, different functions) | FIX -> READY |
| 00310 | park-cap-regressions | minimal | 75 | new cli/cap_check.py, phase-review prose, recovery and state-schema docs | none | READY |
| 00311 | verify-reports-what-the-gate-did | minimal | 80 | cli/__main__.py `_run_verify`, cli/verification.py runner, cli/review_stage.py, work/references/final-verification.md | 00306 lands first (same functions) | FIX -> READY |
| 00312 | close-ten-loop-truths | minimal | 97 | loop_gates, procinfo, tracon/discovery, enter_io, loop_decision, loop_act, loop, selection, __main__ `_run_init`, render_metrics, SKILL.md, state-schema.md | none | FIX -> READY |
| 00313 | release-gate-runs-what-it-claims | minimal | 77 | dev/bin/release-checks, dev/bin/release, cli/wave_launch.py, CHANGELOG | none | READY |

Hygiene: nine `NNNNN-{slug}-v{n}.md` files, numbers unique across backlog, wip (empty), hold (empty), done and discovery (max discovery 00281). The gitignored dotfile `backlog/.migration-placeholder` (1 byte, 2026-09-28) is not selectable: `selectable()` keeps only `.md` names with a sequence prefix.

## Findings
### Blocking
- [00277 v2] B executability: the re-baseline step said a newly flipping review file is "accepted into the list with a one-line reason or treated as a defect", a judgment left to the implementer -> fails as: rework thrash (reviewer and implementer disagree on each flip until the cap). Fix: a code-decided join rule in the Solution, the Must-have bullet and the Phase 2 task: a path joins `_ACCEPTED_FLIPS` only when the gate's named line starts with a severity emoji after lead normalisation; any other new flip fails the task. Applied.

### Non-blocking
- [00312] F sizing: Phase 1 was one task across twelve files; plan-tasks would split it at file boundaries into twelve tasks each paying the 55K overhead and a per-task review. Fix: four Phase 1 tasks by module (registry-children and catchup-guard; loop-messages; entry-hygiene; CHANGELOG) with their own acceptance commands. Applied.
- [00312] C coherence: `test_prd_spend_since_survives_a_non_utf8_ledger` was placed in `test_enter_budget.py`, which covers `enter`'s `prd_budget_since`; `prd_spend_since` is covered by `test_loop_budget.py` (9 hits). Fix: moved. Applied.
- [00309] D grounding: `render_brief` moved from line 161 to 164 when 00284 edited `brief.py`. Fix: citation updated. Applied.
- [00311] E cross-invalidation: 00306 drains first and edits `_refuse_verify_log` and `_lock_and_check`, shifting every line number 00311 cites. Fix: one sentence under Source naming the HEAD and stating that symbols anchor. Applied.
- [00306, 00311, 00312] F: three PRDs add to `skills/run-autopilot/cli/__main__.py` (1863 lines, past the 800-line ceiling); reviewers may raise the file-size rule on each. 00309 and 00310 put their new verbs in their own modules; 00311 and 00312 change existing functions only. No PRD edit; a split of `__main__.py` is a separate PRD if the reviewers keep raising it.
- [00313] B: the Phase 2 timing task runs the full gate twice (about 11 minutes). Deliberate: the measurement is the deliverable. No edit.
- [00308] A: one `(guess)` marker in a contract (`GEMINI_FALLBACK_TIMEOUT` default 900 s); plan-tasks freezes it as written. Acceptable. No edit.
- [all] A: `model_tier_rationale` is not in this gate's recognized-field list but is in create-prd's (ignored by both parsers). No edit.

### Questions
- None. Every contract a test author needs is stated with its exact expression; the one deferred judgment (00277 v2 flips) is now code-decided.

## Reshapes
- None. 00312 was pre-split in place (tasks, not PRDs); its ten edits are one subsystem (the loop driver) and one session.

## Gaps
- Test mass: 107K test lines against 35.5K product lines and a 5.5-minute gate (deep dive Q5). 00313 cuts 131 s; nothing addresses the suite's size. Recommend `/assess-evolution` after this batch, not a PRD invented here.
- Other repos: `allocate_prd_number.py` in the agoge pack scans `dev/local/prds/` and cannot claim numbers in this repo's `docs/dev/project-management/` store; aegis blocks `head`/`tail`/`cat` that loop sessions keep calling; git-ferry's catchup script fails `gh not authenticated` under the sandbox. Each belongs to its own repo.
- Carl: the credential fix is outside the checkout (`~/bin/run-agent`); 00308 latches the failure mode but no PRD can prove the lane is back until the next launch's first review file shows `carl: available`.

## End state after this batch
`autopilot verify` refuses every unsafe sink and reports red, lock contention and a moved HEAD truthfully, and a killed run leaves no second gate behind. The findings sweep reads rows the way a reader does (emoji first after any lead) and no longer refuses bold prose; the delegation guard stops refusing quoted citations and only the seven agoge personas are exempt. Bob is dispatched once, Carl latches on an auth failure, timeouts kill their process groups, retry rows keep their task. Sessions get `markers`, `decide` and `get --default` verbs instead of shell guesses, and dispatch rows close from artifacts. A rework-introduced HIGH at the cap parks the PRD instead of shipping. The loop sees itself from inside its own tree, catchup never reuses a capsule across a reset, every wait and park says why, and the release gate runs the Textual suite and refuses a skip pile. Still half-finished: the test suite's size, `__main__.py`'s length, and the pack-side number allocator.

## Frontmatter tuning
| PRD | suggestion | why |
|---|---|---|
| 00312 | keep `default_model: sonnet`, `design: skip` | every edit carries its exact expression; the new `_AUTOPILOT_LOOP_ENTRY_STALE` contract is spelled out, and the classifier can still raise the loop-messages task through `contract_edit` |
| 00313 | keep `sonnet`, `design: skip` | a flag, a constant with a parameter, a ceiling and a reorder |
| 00277 v2, 00307, 00308, 00310, 00311 | keep `opus`, `design: run` | invented predicates, timing paths and trust boundaries |
| 00306, 00309 | keep `sonnet` | exact expressions, named fail-first tests |

## Decisions applied
- 00277 v2: join rule written into Solution, Must have and the Phase 2 task (Blocking, applied).
- 00312: Phase 1 split into four module tasks; non-UTF-8 ledger test moved to `test_loop_budget.py` (applied).
- 00309: `brief.py` citation 161 -> 164 (applied).
- 00311: HEAD and symbol-anchor sentence under Source (applied).
- Lens A re-run on the four touched PRDs: headings unchanged, every task line keeps its `Acceptance:` clause; `ground_prd.py` after the pass: `{"blocking": 0, "unverified": 0}`.

Final verdict: GO. Drain order 00277, 00306, 00307, 00308, 00309, 00310, 00311, 00312, 00313. 00306 and 00307 are release blockers (destructive `verify --log`, six false guard refusals); the release waits for the batch.
