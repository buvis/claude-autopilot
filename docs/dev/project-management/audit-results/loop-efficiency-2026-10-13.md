# Loop deep dive, batch 202610111300 (measured 2026-10-13 evening, loop live on 00283 build; throughput re-measured 2026-10-14 after the loop exit)

Filed 2026-10-14. The loop exited 2026-10-14 03:16 with "Backlog drained. 8 PRDs completed" (00271, 00276, 00278, 00279, 00282, 00283, 00284, 00285; 00277 held) and ran agoge unattended (`agoge-2026-10-14.md`, 30 packets, 0 CRITICAL, 0 HIGH, 13 MEDIUM, 17 LOW, walkthrough pending). Every number below was measured this session; "confirmed" means reproduced or read in the artifact, "suspected" means inferred.

## Throughput (loop-metrics.jsonl)

| batch | sessions | PRDs | wall h | session h | $ | session h/PRD | $/PRD |
|---|---|---|---|---|---|---|---|
| 202609252154 | 109 | 11 | 155 | 83.2 | 2110 | 7.6 | 192 |
| 202610031511 | 62 | 10 | 41 | 31.8 | 879 | 3.2 | 88 |
| 202610111300 (final) | 62 | 8 done (00277 held) | 62 | 34.5 | 1062 | 4.3 | 133 |

This batch by phase (final): build 30 sessions, $556, 19.4 h (8 opus); review 22 sessions, $480, 14.4 h (15 opus); done/paused/untagged 10 sessions, $26. Per PRD: 00271 $288 / 8.3 h, 00283 $270 / 4.2 h, 00282 $121 / 6.7 h, 00276 $114 / 4.1 h, 00277 (held) $73 / 3.0 h, 00278 $69 / 2.5 h, 00279 $52 / 1.7 h, 00285 $48 / 2.5 h, 00284 $29 / 1.5 h. Decisions at the 2026-10-13 measurement: 112 autonomous, 0 escalated. Outcomes: 00285, 00279 and 00284 (solo lane: alice, blake, eve) converged in 1 cycle; 00283 converged in 2; 00271, 00276, 00278, 00282 ended `cap_deferred` after 2.

## Quality findings, ranked

### Q1. `autopilot verify --log <tracked file>` overwrites committed source (confirmed live, release blocker)

Probe against HEAD's CLI copy in a scratch repo: `verify --gate-command "printf 'PASS 1 FAIL 0 SKIP 0\n'" --log src/app.py` on a clean tree. Result: exit 3, `dirty: true, recorded: false`, and `src/app.py` now holds `PASS 1 FAIL 0 SKIP 0` instead of its source line (`git diff` shows the replacement). Origin: 00276's cycle-1 rework removed the tracked-log refusal that the design doc and tasks 5 and 7 required, and changed the tests to require the overwrite; cycle-2 raised it as HIGH (Bob 1/3); the rework cap deferred it (stubs 00295, 00296). `_lock_and_check` runs the dirty check before `_run_locked_gate` opens the log `wb` (verification.py:541-568), so the damage lands first and the refusal comes after. Fix: refuse a `--log` that resolves to a tracked path or into the store, before opening it; restore the byte-preservation tests.

### Q2. The rework cap is the quality valve, and it ships rework-introduced regressions (confirmed)

Deferred ledger `autopilot/deferred/202610111300-deferred.json`: 99 records, 57 `cap-overflow` (9 HIGH), 22 `deferred_decision` (5 HIGH). Four of six PRDs closed `cap_deferred`. Cycle 2 keeps finding real bugs but can fix nothing, so what it finds ships:
- 00276: the refusal removal above.
- 00271: "the rework for prior R12 introduced a false-allow" (negation anywhere in the five words before the verb, across clauses), plus task scoping keyed by (sentence, id) that refuses an ordinary prompt.
- 00282: `prd_spend_since` crashes on a non-UTF-8 ledger (only OSError caught; contradicts the CHANGELOG promise that a telemetry failure never fails a dispatch); `_invalidate_loop_entry` silently ignores a second write failure and leaves a stale replay for the child.
- 00282: the 00277 rule implemented out of scope (commit 3218842, 17 historical reviews now refused, fixture edited, no CHANGELOG line). User decision 2026-10-13: keep, decide 00277 at batch end.
Product fix: a HIGH raised in the final cycle that names a rework commit as its cause parks the PRD (or gets one regression-only fix round) instead of deferring.

### Q3. Guard v2 ships with known false refusals (confirmed in the ledger, not re-run)

Replay corpus of 1172 dispatches (800 per-task): 7 per-task refusals, 1 correct (the pinned deny id), 6 legitimate dispatches refused because a phase name sits inside a quoted run (backtick, double quote, paren opening before the name). Plus the two rework regressions in Q2. `hooks/hooks.json` wires the guard; CHANGELOG lines 28, 41, 42 claim it with no caveat. In the loop a false refusal costs a denied Agent call and a rephrase turn; the session brief already recorded one such denial during 00271's own build.

### Q4. Reviewer roster is thinner than the review files suggest

Carl: 16 dispatches this batch, 0 ok, 4.6 h lane time (copilot auth; the native gemini retry stalls with no output). Bob: 20 dispatches, 15 ok; the first run was refused `lack-of-input` in 5 of 8 cycles (9 KB prompt), the inlined retry (134-705 KB) then passed. 00282 cycle 1 paid 63 min for the refused run and 63 min for the retry. Every finding count in the review files is Alice + Blake + Bob; no Gemini view since 00270.

### Q5. Test mass

Batch diff (skills, hooks, dev): product +2,771/-855, tests +9,672/-1,138, 359 new test functions, 31 new test files. Tree: 35.5K product lines, 107K test lines (3:1); 16 files over the 800-line maximum (11 tests, `cli/__main__.py` 1863, `review_stage.py` 843). Largest batch additions: `test_loop_budget.py` 716, `test_guard_phase_delegation_structure.py` 644, `test_loop_decision_table.py` 626, `test_records_park_wrapper_died.py` 515, `test_replay_delegation_guard.py` 492. The suite is why a gate takes 5 min and the fail-first replay hits its 600 s timeout.

## Efficiency findings, ranked

### E1. Sessions fight their own tooling: 437 errored tool calls of 6,851 (6.4%) across 55 sessions

Transcript census (`~/.claude/projects/.../*.jsonl` since 2026-10-11):
| cause | calls |
|---|---|
| aegis blocks `head` / `tail` / `cat` | 64 / 24 / 13 |
| redirect into `docs/dev/project-management/` blocked | 30 |
| `autopilot` CLI usage error (wrong verb or flags) | 10 |
| `autonomous_decisions` entry rejected (missing issue / severity) | 6 / 5 |
| `ls .handoff-requested` / `rm .cap-fired` on an absent marker | 7 / 6 |
| redirect-source block (echo into a source file) | 7 |
| `ScheduleWakeup` without a prompt | 5 |
| `json-path key not found: work_start_sha` | 5 |
| `check_style_limits.py` called without `--diff` | 4 |
| `gh not authenticated` | 4 |
Both skill bodies already say never to call `head`/`tail`/`cat` (work/SKILL.md:125, run-autopilot/SKILL.md:302); the model does it about twice per session anyway. Roughly 2-3% of all calls are a wasted turn; cost guess $40-80 of $763. Fixes: a `--` list of marker files tested with `test -e` in one statectl verb; a `decision` statectl verb that takes the fields as flags so the shape cannot be wrong; keep the prose, it is not working.

### E2. Bob's short first run is pure waste (Q4): 5 refused first runs, 1.3 h of lane time plus the session waiting. Inline on the first dispatch (memory `bob-codex-needs-inlined-prompt` already says so; the installed skill still sends the short prompt first, retry-policy.md:23).

### E3. Carl never latches (Q4): exit 1 is not the exit-4 "permanent" shape, so every cycle re-dispatches twice. 4.6 h this batch. Latch after two identical auth failures (PRD draft `reviewer-lane-resilience`). Outside the checkout, decided 2026-10-13: the gh-agent PAT is org-owned and must stay so (a personal-owned fine-grained token cannot push to buvis repos), and "Copilot Requests" exists only on personal-owned tokens, so Copilot gets a second PAT (personal owner, no repos, Copilot Requests read-only) at `~/.config/gh-agent/copilot-token`, exported by `~/bin/run-agent` as `COPILOT_GITHUB_TOKEN` (read before `GH_TOKEN`, ignored by gh). Applied 2026-10-13 22:48 (buvis commit f2ab2f8a); verified in the sandbox: copilot answered `ok` with `GH_CONFIG_DIR` set to gh-agent. Effective at the next `autoclaude` launch.

### E4. Dispatch telemetry is a floor, not a measure: this batch `pat` 29 of 42 rows lost, `tess` 30 of 60, `ivan` 24 of 55 (row never closed at a handoff). Subagent time cannot be read from the ledger. Close the row from the dispatch site, not from the model.

### E5. Review dispatch ids named by date (`review-20261013-c1`, `review-20261013-0630`, `review-20261013c2`) in three cycles, so per-PRD lane attribution breaks for 00276 c2 and 00282 c1. The skill says `review-{id}` (SKILL.md:173); the id should come from state, not the model.

### E6. Carried from the 16:30 pass: 21 HIGH stubs in hold (5 moot now that the gate is green: 00297, 00298, 00299, 00302, 00303; pairs 00288/00293, 00295/00296 repeat one issue); lane and replay timeouts leave gemini and pytest children (two gemini orphans 10 h idle, pytest 28178, foreign ovcaq 14557 at 0.75 core); fail-first replay timed out in 2 of 7 cycles; the gate ran twice in one 00282 session (no `verify` verb in 0.9.0); relaunch gaps small (30 pairs, 26 min). At loop exit (2026-10-14): three gemini orphan pairs (30835/30852, 74168/74203, 79557/79608) and both pytest orphans (14557 foreign, 28178) still alive; `pgrep -f "autopilot.*loop"` matches the gemini prompts, so check `pgrep -lf autoclaude` for a live loop instead.

## Decisions (2026-10-13)

- Q2 last bullet: user chose "keep 3218842, decide 00277 at batch end". At loop exit: walk 00277 with the 17 `_ACCEPTED_FLIPS` paths as evidence, add the CHANGELOG Fixed entry, note the edited `fixtures/00256-review-1.md` in the assumptions ledger, move 00277 per the option picked.

## PRDs filed (2026-10-14, after the loop exit)

Five PRDs on the create-prd templates, grounding gate green at draft time, moved into `prds/backlog/` on 2026-10-14 in drain order: 00306 `refuse-tracked-verify-log` (Q1, sonnet), 00307 `guard-citations-and-replay-contract` (Q3 + stubs 00286-00294, opus), 00308 `reviewer-lane-resilience` (Q4/E2-E5, opus), 00309 `loop-friction-verbs` (E1/E4, sonnet), 00310 `park-cap-regressions` (Q2, opus; changes the review contract, so last). User said "go" (2026-10-13 evening). Not drafted: stub dedupe (needs a human to judge "same issue"), aegis's head/tail/cat blocking (other repo), git-ferry's `gh not authenticated` under the sandbox (other repo), the test-mass question (a judgment, not a spec).

## Overlap with agoge-2026-10-14.md (read before the walkthrough)

- Packets 7, 8, 18 (`verify --log` into a case-variant store path, into `.git/`, a FIFO): same code path as 00306; the natural home is one `--log` identity rule in 00306 (refuse tracked, symlink, outside toplevel, inside the store or git dir by `samefile`, non-regular or executable existing target) rather than a sixth PRD.
- Packet 9 (killing `verify` leaves the gate running): the "timeouts leak children" class that 00308 fixes for replay and gemini; a `killpg` in `run_gate` fits 00308's scope.
- Packet 15 (`agoge:` prefix exemption untested): guard work adjacent to 00307.
- Packets 4, 5, 6 (findings sweep lead shapes): all depend on the 00277 decision; take it at packet 4 (the user chose on 2026-10-13 to keep 3218842 and decide 00277 at batch end).
- Packet 30 (stub 00280 stale, merged into 00278): part of the stub triage; `git mv` to `done/` with a note.
- Packet 1 (`pgrep -P` without `-a` hides the live loop from its own tree on macOS): hits 0.9.0 today; explains why `live_wrapper_pid` returned None from inside the loop.

## Batch-end agenda (proposed order, revised 2026-10-14)

1. Agoge walkthrough (`/run-agoge --resume docs/dev/project-management/audit-results/agoge-2026-10-14.md`, 30 packets); fold packets 7/8/18 into 00306 and 9 into 00308 when accepted; decide 00277 at packet 4. 2. Stub triage in `hold/` (20 stubs 00286-00305: 5 moot now that the gate is green, 00297/00298/00299/00302/00303; pairs 00288/00293 and 00295/00296 repeat one issue; 00280 to done per packet 30). 3. `/review-prd-backlog` over 00306-00310 plus whatever the walkthrough adds. 4. Launch the next batch (00306 and 00307 are release blockers: `verify --log` overwrites source, the guard ships 6 false refusals). 5. Release, `/plugin update autopilot@buvis-plugins`, `/run-agoge` on the release.
