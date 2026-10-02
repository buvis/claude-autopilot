---
prd: dev/local/prds/wip/00214-plan-and-launch-a-wave-of-lanes-v1.md
review: 1
date: 2026-09-26
head_sha: b8b6b17cb989385cf34baaca4957b282b0690aaf
codex_thread_id: 01a0dc90-8e96-7e00-ad58-d201618f8a35
reviewers: alice,blake,bob,carl
agents:
  alice: available
  blake: available
  bob: available
  carl: available
---

# Review: 00214-plan-and-launch-a-wave-of-lanes-v1

Diff range: `14da0ce87c9a5a8d4c1fcca4b35691c250b92e67..b8b6b17cb989385cf34baaca4957b282b0690aaf`

codex_rung_guard: not fired

pack: failed (engram: "not inside a registered repo; register it in /Users/bob/.config/gita/repos.csv"; retried once, same result). `{PACK_FILE}` and `{PACK_FINDINGS}` were substituted with `(no pack available this cycle)` for every reviewer that takes them. The review is degraded on retrieval context, not invalid.

## Review Summary

Reviewed: 4 completed tasks
PRDs checked: 00214-plan-and-launch-a-wave-of-lanes-v1

### Agent Status

- Alice: ✅ Available (Claude subagent, consensus lens; ran the wave suite and the prose suites herself)
- Blake: ✅ Available (Claude subagent, blind/PRD-only lens; ran the wave suite and full `release-checks` himself)
- Bob: ✅ Available (codex, `gpt-5.1-codex-max`-class read-only sandbox; consensus + doubt/de-slop lens, `D1`-`D5` emitted)
- Carl: ✅ Available (gemini via copilot backend, `model=gemini-3.8-flash`, recorded from the runner's stderr)

### Cycle mechanics worth recording

Three deviations from the happy path, all recorded rather than smoothed over:

1. **`gather-context.sh`'s full-review base resolution produced an EMPTY diff on the first run.** The script resolves its full-review base from `origin/HEAD` → `master`, and this PRD's work sits on `master` itself (35 commits ahead of `origin/master`, unpushed), so `git diff master` compared the branch to itself. The re-run passed `--since <work_start_sha>`, which produced the correct 3698-line diff over the PRD's whole work range. The context file's `_Diff scope:_` line was corrected by hand to say FULL review, so no reviewer read it as an incremental rework pass. **This is a latent defect in this repo's own pack** (`skills/review-work-completion/scripts/gather-context.sh`), not a finding about PRD 00214 — it silently produces a zero-line diff for any PRD built directly on the default branch. It is not carried into the findings table below (out of this PRD's scope); it is recorded here and surfaced to the operator.
2. **The Watcher's 30-run budget expired on reviewers that were alive, not stalled.** After ~54 minutes both CLI reviewers were still pending. Direct evidence (`pgrep`: codex pid 80229 and copilot pid 80853 both alive; Bob's event log still growing with `item.completed` rows) showed progress, so a second Watcher was dispatched instead of declaring the reviewers failed per the literal 30-run rule. Both then completed with exit 0 and usable output on the second Watcher's 5th run. Declaring them failed would have discarded two live reviews and left the cycle with two lenses.
3. **`consolidate_findings.py` over-merged two rows** and said so on stderr. Its suffix-stripping citation match folded four distinct `wave_launch.py` findings into one row (`FIX-03` + `FIX-04` + `KNOWN-01` + Carl's `wip/` finding) and three more into another (Alice's `status()` finding + Blake's two signature findings). The table below **splits those back out by hand**, keeping the script's output as the base. Consolidation was otherwise the script's, unmodified.

## Consolidated Findings

Consensus is over N=4 reviewers. Rows marked **(split)** were separated by hand from an over-merged script row (see mechanics note 3); their consensus is restated from the source outputs.

### Verified against the design contract

Every 🔴/🟠 row below was checked by the decision gate against `dev/local/designs/00214-plan-and-launch-a-wave-of-lanes-v1-design.md` before classification, because Bob raised all of them alone while Alice and Blake — both of whom ran the suites — found nothing above 🟡. Four survived that check, four were dismissed as design-conformant. Each verdict is stated on its row.

| Consensus | Severity | Issue | File | Task | Found By | Gate verdict |
|-----------|----------|-------|------|------|----------|--------------|
| [1/4] | 🔴 Critical | `_structural_errors`' `pid` check is `v is None or _is_int(v)` with no positivity bound, so a hand-edited or corrupted `"pid": 0` reaches `os.killpg(0, SIGTERM)` in `_kill_lane`, which signals the **caller's own process group** — under a wave that is the operator's shell or the autopilot loop itself. `order` and `review_slots` are both bounded `> 0` in the same table; `pid` is the one destructive field that is not | skills/run-autopilot/cli/wave.py:289 | 3 | BOB | **CONFIRMED** — the design doc's own Step 0 rationale names a hand-edited `pid` as the exact hazard `_structural_errors` exists to close (design:408-417). This field is the gap it missed. |
| [2/4] **(split)** | 🟠 High | `_return_prds` moves each lane folder into the **matching** main folder, so a lane's `wip/*` lands in main `wip/`. The PRD requires `wip/*` **and** `backlog/*` to return to main `backlog/`. A PRD left in main `wip/` is re-selected by `autopilot select` as already-in-progress, against a `state.json` that holds no task record for it | skills/run-autopilot/cli/wave_launch.py:440 | 3 | BOB, CARL | **CONFIRMED** — the design doc says "matching repo-root lifecycle dir" (design:476), deviating from the PRD with no stated reason for this clause. The PRD is the requirements authority. |
| [1/4] | 🟠 High | `_kill_lane` probes `_pgid_alive(pgid)` then calls `kill_fn(pgid, SIGTERM)`; a group that exits between the two raises `ProcessLookupError`. `_abort_lane`'s `try` wraps only `_clean_up_lane`, so the exception leaves `abort()` uncaught — no `save`, and every later lane unprocessed. The group is being asked to die, so losing the race is the ordinary case, not the exotic one | skills/run-autopilot/cli/wave_launch.py:392 | 3 | BOB | **CONFIRMED** — the design has the same gap: Step 1 wraps nothing, and Step 2's try/except is scoped to "EVERY git/filesystem call in this step" (design:431-494). It breaks abort's own per-lane-isolation promise. |
| [1/4] | 🟠 High | `base_sha` is absent from `_TOP_CHECKS`, but `_keep_reason` indexes `wave['base_sha']` after the lane has already been killed. A hand-edit that drops the key raises an uncaught `KeyError` (not `OSError`/`CalledProcessError`) mid-abort, after the signal and before any cleanup | skills/run-autopilot/cli/wave.py:274 | 3 | BOB | **CONFIRMED** — the design's Step 0 lists `base_sha` among the hand-edited fields abort must not trust (design:411). |
| [2/4] | 🟡 Medium | `waves.md` attributes the review-slot semaphore to PRD 00216; the PRD's own header assigns `wave run` to 00216 and the semaphore to 00217 | skills/run-autopilot/references/waves.md:127 | 4 | ALICE, BOB | CONFIRMED (documentation) |
| [1/4] | 🟡 Medium | `waves.md` documents abort as returning PRDs to matching folders — correct against the code, wrong against the PRD. Coupled to the `wip/` → `backlog/` row above: fixing one without the other leaves the doc lying | skills/run-autopilot/references/waves.md:73 | 4 | CARL | CONFIRMED (coupled) |
| [1/4] | 🟡 Medium | No test pins that every git call `abort()` makes runs with the correct cwd (repo, except the two lane-worktree calls), the way `test_launch_runs_every_git_call_in_the_repo` pins it for `launch()`. Coverage is incidental, so a `cwd=` regression on e.g. the dirty check passes silently — both candidate cwds are valid git repos | skills/run-autopilot/cli/test_wave_launch_abort.py | 3 | ALICE | CONFIRMED (this was one of the four findings task 3 deliberately deferred to this review) |
| [1/4] | 🟡 Medium | `_run_wave` validates a caller-supplied `--state` with a bare `assert`: a non-canonical path raises an uncaught `AssertionError`, or under `python -O` silently derives the wrong repo root. `main()` has no top-level handler, so this and `abort`'s unwrapped `git worktree list --porcelain` (unlike `launch`'s, which `wave_cli.run` catches) surface as raw tracebacks rather than exit 1 with a message | skills/run-autopilot/cli/__main__.py:1153 | 2 | ALICE | CONFIRMED |
| [1/4] | 🟡 Medium | No test covers the PRD-required refusal when a live loop already owns the main checkout (`loop_gates.live_wrapper_pid`). `test_lane_roots_are_distinct_registry_roots` covers registry distinctness, not the refusal | skills/run-autopilot/cli/test_wave_launch.py:412 | 2 | BOB | CONFIRMED (coverage gap on a PRD-named precondition) |
| [1/4] | 🟡 Medium | `abort`'s `wave-slots/` removal is suppressed by ANY `failed`, including a cleanup failure with every process group dead. The build's own recorded override was narrower — keep the directory only when a lane SURVIVED its kill, because a live lane still reads it | skills/run-autopilot/cli/wave_launch.py:526 | 3 | BOB | CONFIRMED — a genuine over-broadening of the build's own deliberate deviation from the design's unconditional `rmtree`. |
| [1/4] | 🟡 Medium | `_clean_up_lane` prints one synthesized `keeping <path>: <reason>` line; the design specifies the worktree's own `git worktree list` line plus, when dirty, one added note — two distinct outputs. Task 3's per-task reviewer raised this once already and it was not fixed | skills/run-autopilot/cli/wave_launch.py:464 | 3 | BOB | CONFIRMED (design:487-489; a repeat of task 3's Pat finding 2) |
| [1/4] | ⚪ Low | `status()` keys "worktree present" off `Path.exists()` rather than git's worktree registry, so a stray directory at a lane's worktree path has its `state.json`, metrics and PRD counts rendered as the lane's | skills/run-autopilot/cli/wave_launch.py:319 | 3 | ALICE | Design-accepted (`status(repo, wave) -> str` has no `run_git`); worth a documented caveat |
| [1/4] **(split)** | ⚪ Low | `launch`/`abort` take a `wave_path: Path` and reload under lock; the PRD's Exports table specifies `launch(repo, wave, ...)` / `abort(repo, wave, ...)` over an already-loaded dict | skills/run-autopilot/cli/wave_launch.py:228 | general | BLAKE | Design-conformant — the reload-under-lock shape is the design's own concurrency fix |
| [1/4] **(split)** | ⚪ Low | `validate()` takes a leading `repo` parameter absent from the PRD's `validate(wave, prds) -> list[str]` | skills/run-autopilot/cli/wave_launch.py:96 | general | BLAKE | Design-conformant (design:299) |
| [1/4] | ⚪ Low | `plan` takes `(repo, wave_path, max_lanes)`; the PRD's Exports table says `plan(repo, max_lanes) -> int` | skills/run-autopilot/cli/wave.py:225 | general | BLAKE | Design-conformant |
| [1/4] | ⚪ Low | The PRD's file tree names two test files; the implementation ships four | skills/run-autopilot/cli/test_wave_launch_abort.py | general | BLAKE | Settled — recorded autonomous decision: task 3's mandated split under the 800-line style gate, and `release-checks` runs all four |

### Dismissed by the gate (design-conformant or factually wrong)

Each is written to the settled-decisions ledger so it is not re-argued next cycle.

| Severity | Issue | File | Found By | Why dismissed |
|----------|-------|------|----------|---------------|
| 🟠 High | FIX-03: abort skips returning PRDs whenever the worktree has commits or uncommitted work | skills/run-autopilot/cli/wave_launch.py:461 | BOB | **Settled deferral.** The design doc states this explicitly and gives the reason: "keep the worktree AND its `dev/local/prds/` files exactly where they are - do NOT move anything back ... an in-progress PRD's only complete record is that worktree's own branch/working tree; the main checkout's `state.json` has no matching task record for it" (design:481-486). Deliberate, reviewed, justified. Note: Carl was merged onto this row by the script but his finding was the `wip/` one above, so its real consensus is 1/4, not 2/4. |
| 🟠 High | FIX-02: abort trusts any process group reusing the stored pid, without the `_AUTOPILOT_LOOP` ownership tag | skills/run-autopilot/cli/wave_launch.py:389 | BOB | **Settled deferral.** The design rules on this directly: `pid == pgid` from creation "permanently, independent of whether that leader later exits - no separate lookup is needed or correct here" (design:431-436). Its genuine residue — that nothing bounds the pid at all — is the CRITICAL row above, which is where it gets fixed. |
| 🟡 Medium | FIX-08: non-core lanes retain packing order instead of a lowest-PRD tie-break | skills/run-autopilot/cli/wave.py:136 | BOB | **Design-conformant.** `_order_lanes`' contract scopes the tie-break to the core-path lanes and says "remaining lanes keep packing order" (design:134). Bob read the PRD's tie-break clause as global. |
| 🟡 Medium | FIX-09: `cut()` does not validate `max_lanes >= 1` | skills/run-autopilot/cli/wave.py:74 | BOB | **Design-conformant.** The contract places the bound at `plan()`, before `cut` is called at all, and `test_plan_refuses_max_lanes_below_one_before_cutting` pins it there. |
| 🟡 Medium | FIX-12: delete `test_plan_refuses_an_abort_failed_wave_like_a_planned_one` and `test_run_still_plans_a_wave_after_the_new_verbs` as duplicate coverage | skills/run-autopilot/cli/test_wave_launch_abort.py:561 | BOB | **Rejected.** Both pin distinct behaviour (the `abort_failed` status refusing like `planned`; `plan` still reachable after the new verbs were added). Deleting regression tests to reduce apparent duplication trades a real guard for tidiness. |
| 🟡 Medium | Redundant `return` in `_pgid_alive`'s exception handler | skills/run-autopilot/cli/wave_launch.py:370 | CARL | **Discarded — factually wrong.** `except OSError: return True` is load-bearing: it converts EPERM ("the group exists, we may not signal it") into alive. Removing it would let that `OSError` propagate. The trailing `return True` is the no-exception path. |
| ⚪ Low | KNOWN-01: a main-root loop can start after `launch`'s point-in-time preflight and race the PRD moves | skills/run-autopilot/cli/wave_launch.py:148 | BOB | **Out of scope, as Bob himself classified it.** Enforcement needs a loop-side reservation outside PRD 00214; the runbook documents the operator constraint. |

### Not queued for verification

- `VERIFY-01` (BOB): "run the four pytest files followed by `bash dev/bin/release-checks`" — **not queued: command shape.** It is two chained commands, which the queue forbids. It is also already answered by evidence this cycle: Alice ran the four wave suites (141 passed) and the prose suites (34 passed); Blake ran the wave suites and the whole of `release-checks` green end to end; Carl ran both as well; and the gate's own suite run below is 2080 passed / 0 failed. No `checks-1.json` was written this cycle.

## Alice

Consensus lens, implementation-aware. Read `wave.py`, `wave_launch.py`, `wave_cli.py`, `__main__.py`'s wave wiring, `waves.md`, `state-schema.md`, `SKILL.md` and `release-checks` in full, plus all four test files including the two with no prior per-task review. Ran the wave suite (141 passed) and `test_loop_prose.py`/`test_custody_prose*.py` (34 passed).

Reports the implementation tracks the design doc almost line-for-line: `cut`'s union-find + greedy pack, `_order_lanes`' core-first tie-break, `_structural_errors`' three-part shape/duplicate/canonical split, `validate`'s re-derivation, `launch`'s save-before-loop / save-per-lane sequencing, and `abort`'s two-signal ownership check, SIGTERM/SIGKILL escalation and `abort_failed` status.

She worked the four findings task 3 deferred to this review and cleared two of them with evidence: the second-newest `_last_metrics` line is correct and pinned by `test_status_derives_drained_from_a_dead_pid_and_empty_next_phase`; the PRD-return-before-worktree-removal order in `_clean_up_lane` is the safe one and existing tests would fail if reversed. The other two she confirmed as real and they are in the table (the abort git-cwd test gap, and `status()`'s `Path.exists()` keying).

Findings: 3 × 🟡, 1 × ⚪. Nothing at 🟠 or 🔴.

`R1: pass` `R2: pass` `R3: pass` `R4: pass` `R6: pass` `R7: pass` `R8: pass` `R9: pass` `R10: pass` `R11: pass` `R12: pass` `R13: pass`

## Blake

Blind lens — prompt carried the PRD and the `B` rubric only: no diff, no changed-file list, no implementation summary, no review history. No filesystem-notes block (the trigger does not hold: `dev/local` is a real directory and the project root does not start with `.`).

Found the code himself, ran the full wave suite (141 passed) and then the whole of `dev/bin/release-checks` end to end, every block green including `[checks] waves` and the prose suites the PRD's exit criteria require to stay green. Cross-checked every named acceptance-criteria test from Phase 0, Phase 1 tasks 1-2 and Phase 2 against the functions actually present — all present, all passing.

He independently confirmed the PRD's deferred items are genuinely absent: `wave_cli.add` registers only `plan|launch|status|abort` (no `assemble`/`review`/`land`/`run`), and the two review-slot env vars are written by `launch` and read nowhere else in the codebase — which is exactly what `waves.md` claims and what the build flagged as unverified. **That closes note 6 of the build's hand-off**: the "nothing throttles it yet" half of the doc is now verified against the consumer side, by a reviewer who had no idea it was in question.

Findings: 4 × ⚪, all PRD-Exports-table vs. concrete-signature mismatches and the two extra test files. No Critical, High or Medium.

All nineteen blind verdicts pass: `B1`-`B19` `pass`.

## Bob

Doubt + de-slop lens on codex, read-only sandbox, plus the consensus `R` rubric. Ran first-try (no retry; the `codex-review-last.jsonl` salvage path was not needed). His first shell read was blocked by this host's aegis fact-forcing gate, which he recovered from on his own — the blocked `cat` cost him time but not the review.

He is the only reviewer who raised anything above 🟡, and he raised a lot of it: 1 × 🔴, 6 × 🟠, 4 × 🟡, 3 × ⚪ across 14 FIX items, 1 VERIFY and 1 KNOWN. The gate confirmed four of the seven 🔴/🟠 against the design contract and dismissed three; every dismissal is in the table above with its reason and in the ledger. His CRITICAL is the best finding of the cycle: nobody else noticed that `pid` is the one destructive, hand-editable field `_structural_errors` does not bound, and `os.killpg(0, ...)` hits the caller's own process group.

Buckets as emitted: `FIX (14)`, `VERIFY (1)`, `KNOWN (1)`.

`R1: fail` `R2: fail` `R3: pass` `R4: pass` `R6: pass` `R7: fail` `R8: pass` `R9: fail` `R10: fail` `R11: pass` `R12: pass` `R13: pass`

`D1: pass` `D2: pass` `D3: pass` `D4: pass` `D5: pass`

On his `R` failures: `R1`/`R2` rest on the coverage gaps in the table (the abort git-cwd invariant, the live-loop refusal) — the gate accepts those as real but reads them as Medium, not as the diff's tests failing to cover new behaviour wholesale; `R7`/`R10` rest on his pid/`base_sha`/`ProcessLookupError` findings, which the gate confirmed; `R9` rests on the `wip/` → `backlog/` deviation, also confirmed. Alice, Blake and Carl passed the rules Bob failed, except `R9`, where Carl agrees with him.

## Carl

Gemini lens via the copilot backend, `model=gemini-3.8-flash` (recorded from the runner's stderr; no native fallback). Read `wave.py`, `wave_launch.py`, `wave_cli.py`, `__main__.py`'s wave wiring, `waves.md`, `state-schema.md`, `SKILL.md`, `CHANGELOG.md`, `release-checks`, `selection.py` and parts of three test files. Ran the wave suites and `release-checks` (twice — once after unsetting the copilot recursion flags) and the prose suites.

No frontend surface here, and he correctly did not invent one; he reviewed as a generalist.

His value this cycle was independent corroboration of the `wip/` → `backlog/` deviation, which turns Bob's lone 🟠 into a 2/4 row, plus noticing that `waves.md` documents the wrong behaviour in the same place. His third finding (`_pgid_alive`'s handler) is wrong and is discarded with reason.

Findings: 1 × 🟠, 2 × 🟡.

`R1: pass` `R2: pass` `R3: pass` `R4: pass` `R6: pass` `R7: pass` `R8: pass` `R9: fail` `R10: pass` `R11: pass` `R12: pass` `R13: pass`

Verdict: 16 findings
Tests: 2080 passed, 0 failed, 1 skipped (suite run this cycle)
