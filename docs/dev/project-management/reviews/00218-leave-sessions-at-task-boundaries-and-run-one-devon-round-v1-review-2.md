---
prd: dev/local/prds/wip/00218-leave-sessions-at-task-boundaries-and-run-one-devon-round-v1.md
review: 2
date: 2026-09-29
head_sha: 2a64f20e0c88647e1791bcc107801c6c3ce176a2
codex_thread_id: 01a0ee15-2166-7531-b39a-5f4f9102cb10
reviewers: alice,blake,bob,carl
agents:
  alice: available
  blake: available
  bob: available
  carl: available
---

# Review: 00218-leave-sessions-at-task-boundaries-and-run-one-devon-round-v1

Diff range: `e5a8479cb07bb3d9d62fbdb873aa4dab3b271c5e..2a64f20e0c88647e1791bcc107801c6c3ce176a2`

codex_rung_guard: not fired

## Run conditions

- Lenses: consensus (Alice, legacy engine), blind (Blake), doubt + de-slop (Bob via codex), UI/generalist (Carl via gemini-run.sh). Eve not active: the codex doubt-roster guard did not fire, because no `state.tasks[].attempts[].implementor` is `codex`.
- Carl backend: `backend=copilot model=gemini-3.8-flash` (from `gemini-run.sh` stderr). Exit 0, non-empty review text.
- Bob: exit 0, first run, no inlined retry. Cycle 1's `--emit-thread-id` wrote an EMPTY sidecar so there was no thread to resume; Bob therefore ran **fresh** this cycle rather than resuming his cycle-1 session. This cycle's sidecar is non-empty and is stamped above, so cycle 3 (if there were one) could resume.
- Consolidation: `consolidate_findings.py` (script, not model-side), with `--ledger` and `--ledger-dismiss BLAKE` (the cycle-1 ledger exists). It merged citations that matched only after suffix stripping on row 1 — see the caveat under the table.
- pack: FAILED, same deterministic config gap as cycle 1. `engram pack` exited 1 with `not inside a registered repo; register it in /Users/bob/.config/gita/repos.csv`. Not retried (a config gap, not transient). Every prompt taking `{PACK_FILE}` / `{PACK_FINDINGS}` received the sentinel `(no pack available this cycle)`. The review is degraded by the missing retrieval context, not invalid.
- Diff scope: INCREMENTAL, `--since e5a8479` (the cycle-1 `head_sha`). 20 files, 1412 insertions, 211 deletions, over the cycle-1 rework batch (tasks 8-14).
- Verification-check queue: NOT written this cycle. Eve did not run, and `agents/bob.md` defines no FIX/VERIFY/KNOWN buckets (`source: "bob"` is reserved), so no doubt lens emitted a VERIFY bucket to queue. Bob's two `Cannot statically verify` lines were discharged directly by the two runs recorded under `Tests:` below.
- Carry-forward: nothing. Cycle 1 wrote no `-checks-1.json`, so no previous cycle's failed checks exist to carry.
- Follow-up tasks: **none created**, deliberately. See "Follow-up Tasks Created" below.

## Consolidated Findings

| Consensus | Severity | Issue | File | Task | Found By |
|-----------|----------|-------|------|------|----------|
| [4/4] | 🟠 | `trusted_last_wall` stops at the first completed task whose stamps are missing, non-int or negative and returns None, instead of scanning back. Its tests pin that shape (`test_stamps_that_are_not_both_ints_give_no_span`, `test_a_negative_span_gives_nothing`). The PRD wording, the design doc ("finds the last completed entry whose stamps are both ints") and task 11's widening of `last_task_wall` all say scan back. Since the hook never calls `last_task_wall`, task 11's fix has no runtime effect. Any completed task that was never seen in progress now drops the time term for the next fire. This is conservative, and the rotated-task and over-ceiling stops are deliberate, but the unstamped case is undocumented as a deviation. Either skip unstamped or negative entries and stop only on rotated or over-ceiling ones, or record the deviation. The design's `test_trusted_last_wall_agrees_with_last_task_wall` pin is also missing (`rg` finds no such test), so the two walks can silently disagree. | skills/run-autopilot/scripts/_cap_headroom.py:61 | 14 | ALICE, BLAKE, BOB, CARL |
| [2/4] | 🟠 | R13 regression: the rework grew this test file from 782 to 923 lines, and the project's own style gate (`check_style_limits.py`, "files the diff pushed over 800") flags it. The earlier split existed to stay under 800. Move the new `TaskBoundsWallTests` additions into a sibling file such as `test_cap_task_record_wall.py`, and add it to `dev/bin/release-checks`. | skills/run-autopilot/scripts/test_autopilot_cap_headroom.py:735 | 11 | ALICE, CARL |
| [1/4] | 🟡 | `record_task_bounds` withholds `done_at` when the task has no `started_at`. The PRD says `now` is passed as the third value of each pair. This is defensible (a lone `done_at` gives no usable span) but it is an undocumented deviation from the contract. Note that `MAX_CREDIBLE_WALL_SECS` and this guard are extra behavior beyond the PRD. | skills/run-autopilot/scripts/_cap_task_record.py:111 | general | BLAKE |
| [1/4] | 🟡 | FIX: Adding `started_at` to `START_FIELDS` lets `record_pair` replace an existing timestamp when it exceeds `now`, breaking the write-once contract. Limit the stale-start replacement rule to usage and calls. | skills/run-autopilot/scripts/_cap_task_record.py:65 | 11 | BOB |
| [1/4] | 🟡 | FIX: A correction retry requires another Tess dispatch, but the four-dispatch budget allocates only one adversarial strengthen dispatch. The new prose still permits an unanswered weak point when that budget is spent. Reconcile the budget and retry rule; the test's check for the word "correction" does not pin dispatch counts. | skills/work/SKILL.md:243 | 13 | BOB |
| [1/4] | 🟡 | FIX: The expanded module introduction still repeats the assertions and test mechanics. Replace it with a short purpose statement, as requested in cycle 1. | skills/work/scripts/test_devon_round_prose.py:1 | 13 | BOB |
| [1/4] | 🟡 | 3 touched test(s) pass against the pre-change code: test_all_unstamped_tasks_print_none_stamped, test_empty_task_list_prints_none_stamped, test_missing_tasks_key_prints_none_stamped | skills/run-autopilot/cli/test_render_report.py | general | mech-check |
| [1/4] | 🟡 | 1 touched test(s) pass against the pre-change code: test_idle_guard_waits_for_an_active_session_past_the_cap | skills/run-autopilot/cli/test_watchdog.py | general | mech-check |
| [1/4] | 🟡 | 2 touched test(s) pass against the pre-change code: test_bound_fields_excludes_the_stamps_so_last_task_cost_ignores_them, test_done_at_survives_a_second_session | skills/run-autopilot/scripts/test_autopilot_cap_headroom.py | general | mech-check |
| [1/4] | 🟡 | 13 touched test(s) pass against the pre-change code: test_calls_margin_boundary_pins_the_exact_multiplier, test_calls_margin_fires_below_the_margined_threshold, test_time_term_boundary_pins_strict_less_than, test_time_term_is_false_when_plenty_of_time_remains, test_a_cheaper_last_task_keeps_working_under_the_same_deadline, test_a_malformed_cap_rotations_never_matches +7 more | skills/run-autopilot/scripts/test_autopilot_cap_headroom_margin.py | general | mech-check |
| [1/4] | 🟡 | 1 touched test(s) pass against the pre-change code: test_tess_answers_each_weak_point | skills/work/scripts/test_devon_round_prose.py | general | mech-check |
| [1/4] | ⚪ | `record_pair`'s annotation says `values: tuple[int, int \| None, int]`, but `record_task_bounds` passes `done_now`, which is `int \| None`, in the third slot. The code handles it (`None` is skipped). Only the type is wrong. | skills/run-autopilot/scripts/_cap_task_record.py:43 | 11 | ALICE |
| [1/4] | ⚪ | The PRD says step 2.8's Tess budget line is unchanged. The implementation rewrote it to say the strengthen "also covers Devon's one weak-point correction retry". This resolves a real tension in the spec (a correction retry versus a fixed budget of 4), but it edits a line the spec said to leave alone. | skills/work/SKILL.md:243 | general | BLAKE |
| [1/4] | ⚪ | The PRD's quoted step 2.9 replacement text contains "no second Devon dispatch". Its own acceptance test forbids that phrase in `### 2.9`. The implementer reworded to "Devon never dispatched again", which is the right way to resolve the spec's self-contradiction. | skills/work/SKILL.md:267 | general | BLAKE |
| [1/4] | ⚪ | Cannot statically verify: targeted suites pass and release checks pass; VERIFY: run the PRD Success Metrics pytest command and `bash dev/bin/release-checks`. | N/A | general | BOB |

**Consolidation caveat (read before treating row 1 as one defect).** `consolidate_findings.py` merged six citations in `_cap_headroom.py` (lines 61, 76, 79, 81, 648, 649) onto row 1 and kept Alice's first-seen wording. That row is really **three distinct defects**, all four reviewers between them:

1. **No `isinstance(task, dict)` guard** (`_cap_headroom.py:77`) — Alice, Blake. A non-dict entry in `state.tasks` raises `AttributeError` inside a PostToolUse hook that has no `except Exception` around it.
2. **Booleans satisfy `isinstance(..., int)`** (`_cap_headroom.py:81`) — Bob, Carl. `bool` subclasses `int`, so `started_at: True` / `done_at: True` yields a 0-second "span" instead of being rejected. `int_field` in `_cap_task_record.py` does the bool exclusion; this reader does not.
3. **No scan-back, and a `last_task_wall` that nothing calls** (`_cap_headroom.py:82,85,94`) — Alice, Bob, and Blake's separate 🟠 on the rotation/ceiling deviation from the PRD's `last_task_wall(state)`.

## Orchestrator verification of the two 🟠

Neither HIGH is taken on the reviewers' word. Verified directly at `2a64f20`:

**Row 1** — read `skills/run-autopilot/scripts/_cap_headroom.py:73-96`:

```python
    for task in reversed(tasks):
        if task.get("status") != "completed":      # no isinstance(task, dict) guard
            continue
        started = task.get("started_at")
        done = task.get("done_at")
        if not isinstance(started, int) or not isinstance(done, int):
            return None                            # bools pass; and no scan-back
```

All three sub-claims CONFIRMED by reading. `last_task_wall` is confirmed unreferenced by the hook path, so task 11's scan-back widening is dead for the runtime rule.

**Row 2** — run at `2a64f20`:

```
$ wc -l skills/run-autopilot/scripts/test_autopilot_cap_headroom.py
923
$ python3 skills/work/scripts/check_style_limits.py --diff dev/local/tmp/review-diff-00218-c2.diff skills/run-autopilot/scripts/test_autopilot_cap_headroom.py
FILE | skills/run-autopilot/scripts/test_autopilot_cap_headroom.py | 923 lines
(exit 1)
```

CONFIRMED. The rework pushed the file 123 lines over the project's own 800-line limit, and the gate that says so is the repo's own.

## Orchestrator verification of the cycle-1 🔴 (closed)

The cycle-1 CRITICAL (the time term never wired into the hook) is CLOSED, and the closure is pinned. Verified by checking HEAD's test file out over a base worktree at `e5a8479` and running it there:

```
$ uv run --no-project --with pytest python -m pytest -q skills/run-autopilot/scripts/test_autopilot_cap_headroom_margin.py -rA --tb=no
FAILED TimeTermHookTests::test_time_term_hands_off_when_the_deadline_is_near
FAILED TimeTermHookTests::test_deadline_already_past_hands_off
FAILED TimeTermHookTests::test_an_honest_long_wall_still_fires_the_time_term
FAILED TimeTermHookTests::test_a_rotation_of_another_task_still_fires_the_time_term
FAILED DeadlineSeamTests::test_deadline_env_name_matches_the_runner
9 failed, 15 passed, 4 subtests passed
```

Every positive end-to-end pin fails against the pre-change code, so the new tests genuinely pin the wiring rather than the predicate alone. That is what makes the thirteen `[MECH]` replay entries for this file benign: the ones that pass at base are the **inert/negative** assertions (`..._is_inert_without_a_deadline`, `..._does_not_fire_the_time_term`, `test_a_cheaper_last_task_keeps_working...`) plus the `HeadroomMarginTests` pure-predicate tests, which already existed at base.

## Alice

Alice (consensus, legacy engine) raised 4 findings: 1 🟠, 2 🟡, 1 ⚪, and verified the whole cycle-1 list closed except the two she raises. She ran 242 tests / 52 subtests green across the eight targeted suites, including the two that were red in cycle 1 (`test_render.py::GoldenRenderTests::test_report_section_matches_golden` and `test_routing.py::test_metrics_append_with_effort_still_never_raises`). She did not run `dev/bin/release-checks`; the orchestrator did (see `Tests:`).

Rubric verdicts:

```
R1: pass
R2: pass
R3: pass
R4: pass
R6: pass
R7: pass
R8: pass
R9: fail
R10: pass
R11: pass
R12: pass
R13: fail
```

## Blake

Blake (blind, PRD-only; no diff, no file list, no review history) raised 5 findings: 1 🟠, 2 🟡, 2 ⚪. His 🟠 is reached from the spec alone: the PRD says the hook reads `last_task_wall(state)`, and the implementation substitutes `trusted_last_wall`, whose rotation and 10800 s stops invert the PRD's own edge case ("a rotated task's wall spans both sessions and the next session hands off **earlier, never later**"). He confirmed as implemented-per-spec: the three-field stamps and write-once `started_at`, `HEADROOM_MARGIN = 1.25` and the None-drops-a-term rule, the whole watchdog idle/ceiling surface with `watchdog.py` at 199 lines, `idle_secs_for` defaulting to 1200, the deadline export, `activity_path`/`cap_reason`/`killed_by`, the runbook sentence, the budgets and the `Task wall-clock:` block, and the entire Devon prose set. Two of his findings were auto-dismissed against the ledger by `--ledger-dismiss BLAKE`: none matched, so nothing was dropped (no `### Auto-dismissed (ledger)` section was emitted).

Rubric verdicts:

```
B1: fail
B2: pass
B3: pass
B4: pass
B5: pass
B6: fail
B7: pass
B8: pass
B9: pass
B10: pass
B11: pass
B12: pass
B13: pass
B14: pass
B15: pass
B16: pass
B17: pass
B18: pass
B19: pass
```

Both B15 and B16 (the Phase 1 and Phase 2 acceptance rules that failed in cycle 1) now pass. B1 and B6 fail on the `trusted_last_wall` substitution and on `MAX_CREDIBLE_WALL_SECS` plus the `done_at` guard as behavior beyond the PRD.

## Bob

Bob (doubt + de-slop lens via codex, static-only sandbox) raised 7 findings: 5 🟡, 2 ⚪. First run, no inlined retry. He ran fresh rather than resuming (cycle 1's thread sidecar was empty). His two ⚪ are the sandbox's declared runtime limit, discharged by the orchestrator's two runs below.

Rubric verdicts:

```
R1: fail
R2: fail
R3: pass
R4: fail
R6: pass
R7: fail
R8: pass
R9: fail
R10: pass
R11: pass
R12: pass
R13: pass
D1: pass
D2: pass
D3: pass
D4: pass
D5: pass
```

Bob's `R13: pass` and Alice's/Carl's `R13: fail` disagree. The orchestrator's own `check_style_limits.py` run above settles it: **fail**. Bob's static sandbox did not run the gate.

## Carl

Carl (`backend=copilot model=gemini-3.8-flash`) raised 2 findings, both 🟡: the 923-line file and the bool-passes-`isinstance` hole. No frontend surface in this diff, so he reviewed as a generalist. His first `bash dev/bin/release-checks` run reported 20 failures; that was an artefact of his own sandbox exporting `AUTOPILOT_DISPATCH_DEPTH` / `COPILOT_CLI` (every failure line reads `refusing nested dispatch (depth=1)`). He re-ran under `env -u ...` and the orchestrator's own clean run confirms green — not a finding.

Rubric verdicts:

```
R1: pass
R2: pass
R3: pass
R4: pass
R6: pass
R7: pass
R8: pass
R9: pass
R10: pass
R11: pass
R12: pass
R13: fail
```

## Mechanical checks

- **Tautological test shapes**: clean. 125 test functions checked across 6 changed test files; no `[MECH]` line.
- **Fail-first replay**: 43 touched tests ran against `e5a8479`; 23 failed there (correctly pinning the change), 20 passed, 1 test file could not be collected at base. All five `[MECH]` lines are absorbed as their own rows in the table above; each is a benign expected-pass, verified in "Orchestrator verification of the cycle-1 🔴" above and in the ledger reasons.
- **Mechanical facts** (`ast` line counts) were appended to the context file and reached every implementation-aware prompt. No finding contradicts that block, so nothing was discarded under the computed-facts rule.

## Follow-up Tasks Created

**None, deliberately.** `state.cycle` is 2 and the PRD's `rework_cap` is 2, so Phase 5's cap check routes this cycle to the loop-mode cap-out, which defers and finalizes without a rework pass. Creating `[D2]` tasks here would leave pending tasks that nothing dispatches, breaking the `tasks_completed == tasks_total` accounting the done gate reads. Every unresolved finding gets a `cap-overflow` record in `state.deferred_decisions` instead, which is the durable home; the discarded ones get a ledger entry with the verified reason.

Verdict: 15 findings
Tests: 3721 passed, 0 failed, 1 skipped (suite run this cycle)

`last-verification.json` was NOT reused: its `sha` matches this HEAD but all three counts are null (its only recorded command is `bash dev/bin/release-checks`, which does not report a total). The counts above come from a fresh foreground run this cycle:

```
$ uv run --no-project --with pytest python -m pytest -q skills/ --ignore=skills/run-autopilot/scripts/tracon
3721 passed, 1 skipped, 7 warnings, 856 subtests passed in 282.25s (0:04:42)
```

Both of cycle 1's red tests are green. `skills/run-autopilot/scripts/tracon` stays excluded because its three test modules fail to import for want of the `rich` package — a pre-existing environment gap unrelated to this diff.

`bash dev/bin/release-checks` was also run in the foreground this cycle and is green end to end (every block passed; the recursion-guard, codex-resume, gemini and sonnet wrapper blocks report `26 passed, 0 failed`, `25 passed, 0 failed`, `38 passed, 0 failed` and `27 passed, 0 failed`). That discharges Bob's second `Cannot statically verify` line.
