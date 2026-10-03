---
prd: 00242-harden-the-wave-verbs-v1.md
cycle: 1
date: 2026-10-03
head_sha: 11b281506a80903d7941f28e70295c563886b4db
codex_thread_id: 01a1038c-2e11-7791-ba2a-31554e5facc8
reviewers: alice,blake,bob,carl
---

# Review cycle 1 — 00242-harden-the-wave-verbs-v1

Diff range: `b48069ed29823e2c44bd05dfcfbad42d94a89ada..11b281506a80903d7941f28e70295c563886b4db`
Scope: full review (cycle 1, no prior cycle). Base is `state.work_start_sha`.

pack: failed (engram: "not inside a registered repo; register it in
/Users/bob/.config/gita/repos.csv"). Alice, Bob and Carl ran without the
context pack and Eve's `{PACK_FINDINGS}` input was the
`(no pack available this cycle)` sentinel. Degraded, not invalid.

codex_rung_guard: not fired

Lens roster: consensus (Alice), blind (Blake), doubt (Bob), ui (Carl). Eve is
not active this cycle — `doubt_reviewer` resolved to `codex` and the codex
doubt-roster guard did not fire (0 of 9 attempts across the 7 build tasks used
`implementor: "codex"`; all ran `claude`).

Carl backend: `gemini-run: backend=copilot model=gemini-3.8-flash` (exit 0,
non-empty reviewer text).

Consolidation: `consolidate_findings.py` with four agent pairs. No ledger file
existed at consolidation time (cycle 1), so `--ledger`/`--ledger-dismiss` were
not passed and no Blake finding was auto-dismissed. The script merged six rows
whose citations matched only after suffix stripping (adjacent line numbers in
the same function); those merges are reflected in the table's `Found By`
column.

## Consolidated Findings

21 rows: the 17 the script emitted, plus 4 rows absorbed from the context
file's fail-first replay block (`mech-check`). One `[MECH]` line matched an
existing row (Bob's retry-test finding) and contributed `mech-check` to its
finders rather than a new row.

| Consensus | Severity | Issue | File | Task | Found By |
|-----------|----------|-------|------|------|----------|
| [2/4] | 🟠 | 00226 spec deviation with a recovery hole. The spec says a hand-reviewed stub in prds/done/ "sets the status to `converged` (saved)" and then continues into the normal land path. `land` only checks for the stub and falls through without ever setting or saving `converged`. `_land_converged` runs `_land_migrate`, which moves the stub out of the worktree's prds/done/ into the main checkout's prds/done/. If anything then fails before the final `done` save (for example `_cycle_count` or `_append_summary_line`), wave.json is still `review_failed` and the stub is no longer in the worktree. A retry then returns 4 and appends a misleading review_failed line to the report even though the fast-forward already happened. The wave cannot land without hand-editing wave.json, which is the problem 00226 set out to remove. `test_hand_reviewed_stub_in_done_lands` never asserts the saved `converged` status. | skills/run-autopilot/cli/wave_review.py:543 | 00226 | BLAKE, BOB |
| [3/4] | 🟡 | `_drain_lane` now persists `worktree_removed=True` before `branch -D` (wave_assemble.py:528-531), but the early return at wave_assemble.py:519 skips the whole function once that flag is set. A crash between the second save and `branch -D`, or a `branch -D` that raises (e.g. a git lock), is therefore never retried on rerun, and the lane branch `wave/<id>/lN` leaks silently. Before the change an unsaved flag made the rerun retry it. The new docstring and the design comment claim the opposite ("the git calls check what is actually still there"). No test crashes between the two saves; `test_crash_after_save_before_remove_reruns_clean` only pins the first save. Fix: let the rerun path still run the `branch --list` / `-D` step when status is assembled, or set the flag only after `branch -D`; then add a test that crashes after the second save | skills/run-autopilot/cli/wave_assemble.py:519 | 4 | ALICE, BLAKE, BOB |
| [3/4] | 🟡 | PRD 00225 Risks promise that "the commit message and the wave report name every PRD moved to hold/". Only the commit body names them (wave_review.py:252-259); no report or summary line is written, and the design doc flagged this as an explicit planner task that no task picked up. The fix also has an unaddressed side effect. The hold commit sits on the assembly branch, and `land` fast-forwards master onto that branch (wave_review.py:392, 460-465). Per the design's own data-flow note, master's backlog PRDs end up in `hold/`. Held-back PRDs that waves.md:22 documents as "left in the main backlog" would land in `hold/`. Lane-completed PRDs that `migrate_lane` already put in `done/` would also appear in `hold/`. This is suspected from the design text and code reading, not confirmed by an end-to-end land run. Add the report line (or surface the names in `land`'s summary) and document the behaviour in waves.md's `wave review` section | skills/run-autopilot/cli/wave_review.py:235 | 5 | ALICE, BLAKE, BOB |
| [2/4] | 🟡 | PRD 00226 asks `_land_review_failed` to set the wave status to `converged` (saved) and continue. The code instead inlines the stub check in `land` (wave_review.py:543-548) and never writes `converged`; `_land_review_failed` is unchanged (still `(repo, wave)`, wave_review.py:501). The context's Task 6 description (a `wave_path` parameter, an `int \| None` return, a locked save) does not match the diff. The user-visible docs state behaviour that does not exist: waves.md:192 says `land` "sets the wave's status to `converged`". After a hand-reviewed `land` that returns 5 or raises, wave.json still reads `review_failed`. Either implement the saved `converged` transition or correct waves.md and the PRD wording | skills/run-autopilot/references/waves.md:192 | 6 | ALICE, BLAKE |
| [2/4] | 🟡 | The PRD's named acceptance test `test_wave_review.py::test_store_churn_in_the_assembly_worktree_does_not_refuse` does not exist in any file. The test landed as `test_wave_review_cleanup.py::test_store_only_churn_in_the_assembly_worktree_does_not_refuse` (different name and file). `test_seeded_backlog_prds_are_held_before_the_nested_loop` also moved to the new file. Behaviour is covered, but acceptance by test id fails. Rename the first test, or record the deviation in the PRD | skills/run-autopilot/cli/test_wave_review_cleanup.py:33 | 5 | ALICE, BLAKE |
| [2/4] | 🟡 | `_hold_backlog` has two partial-failure gaps. (1) A retry after a failed `git commit` finds an empty backlog and returns at the no-op guard (wave_review.py:241-242). The move then stays renamed on disk and staged in the index but uncommitted, which contradicts the docstring's claim that retry is safe. The retry test only fails a later `cycle` step, not a git step. (2) `Path.rename` silently overwrites an existing `hold/<name>`. Both are narrow | skills/run-autopilot/cli/wave_review.py:241 | 5 | ALICE, BOB |
| [2/4] | 🟡 | FIX: The retry test passes against pre-change code because unchanged HEAD also means nothing was committed initially. Assert the first attempt actually committed the backlog-to-hold move before checking retry idempotency. | skills/run-autopilot/cli/test_wave_review_cleanup.py:194 | 5 | BOB, mech-check |
| [1/4] | 🟡 | Simplification: `land` is exactly 50 lines (mechanical block), the checklist's "under 50" ceiling. It reached that because the hand-review check was inlined (wave_review.py:543-550) and the `status != "done"` rewrite at :552 touches it too. Extracting a 3-line `_hand_reviewed(wave) -> bool` helper (stub exists in the worktree's `prds/done/`) would bring `land` back under the limit and name the intent, with no behaviour change | skills/run-autopilot/cli/wave_review.py:515 | 6 | ALICE |
| [1/4] | 🟡 | [MECH] 1 touched test(s) pass against the pre-change code: test_every_wave_test_file_is_listed | skills/run-autopilot/cli/test_wave_docs.py | general | mech-check |
| [1/4] | 🟡 | [MECH] 1 touched test(s) pass against the pre-change code: test_seeded_backlog_prds_are_held_before_the_nested_loop | skills/run-autopilot/cli/test_wave_review_cleanup.py | general | mech-check |
| [1/4] | 🟡 | [MECH] 1 touched test(s) pass against the pre-change code: test_assemble_lets_a_non_os_error_propagate | skills/run-autopilot/cli/test_wave_cli_refusals.py | general | mech-check |
| [1/4] | 🟡 | [MECH] 1 touched test(s) pass against the pre-change code: test_review_failed_without_hand_review_still_exits_four | skills/run-autopilot/cli/test_wave_review_land.py | general | mech-check |
| [1/4] | 🟡 | [MECH] 2 touched test(s) pass against the pre-change code: test_one_slot_is_never_handed_to_two_holders, test_a_reclaim_never_steals_a_claim_that_went_live_first | skills/run-autopilot/cli/test_wave_slots.py | general | mech-check |
| [2/4] | ⚪ | `release` can now raise, and it creates files it did not before. `_slot_lock` does `mkdir(parents=True)` plus `open(..., "a")` (wave_slots.py:50-51), which is not in the design. `_remove`'s docstring (wave_slots.py:30-35) says `release` runs in a `finally:` where a raise would replace the in-flight error, yet an OSError from the lock open now escapes from `Loop._launch`'s `finally` (loop.py:441). A release of a missing slot, which the docstring calls a no-op, also recreates `wave-slots/` and `<n>.lock` after `land` or `abort` has removed the dir. The module docstring (wave_slots.py:1-10) does not mention the `.lock` sidecars. Consider catching OSError in `release` (report on stderr, as `_remove` does) and skipping the mkdir | skills/run-autopilot/cli/wave_slots.py:50 | 3 | ALICE, BLAKE |
| [2/4] | ⚪ | A crash window remains before the new first save in `_drain_lane`. `migrate_lane` moves the lane's PRDs out of its worktree via `_route_prds` and appends the jsonl rows before the first `save` (wave_assemble.py:521-524). `held_prds` and `migrated_at` are therefore still in memory only. A crash there loses the non-roster PRD names the PRD wants kept and duplicates ledger rows on rerun. This is pre-existing and outside the PRD's literal git-teardown scope; saving `held_prds` before `migrate_lane` would close it | skills/run-autopilot/cli/wave_assemble.py:523 | 4 | ALICE, BLAKE |
| [2/4] | ⚪ | Same mistake elsewhere: the OSError catch was added only to the `assemble` verb. `wave run` chains `wave_assemble.assemble` directly (wave_run.py:141) under `_GUARDED_ERRORS`, which omits OSError (wave_cli.py:37-42). A removed-worktree OSError still tracebacks through `wave run`, `wave review` and `wave land` | skills/run-autopilot/cli/wave_cli.py:37 | 4 | ALICE, BLAKE |
| [1/4] | ⚪ | The 00227 race test uses threads, not the "three processes" the PRD names. flock is per open file description, so mutual exclusion is still exercised. Cross-process behaviour through real `acquire` callers is not covered. | skills/run-autopilot/cli/test_wave_slots.py:573 | 00227 | BLAKE |
| [1/4] | ⚪ | `release(slot, owner_pid)` now has a required second argument, while the PRD says exports are "unchanged". The ownership check needs the pid, and the only production caller (loop.py:441) passes the same `loop_pid` used for `acquire`, so nothing breaks. It is still a signature change. | skills/run-autopilot/cli/wave_slots.py:176 | 00227 | BLAKE |
| [1/4] | ⚪ | `_land_cleanup` now exempts all store paths via `foreign_dirty`, as the spec requires. It then runs `worktree remove --force`, which silently discards any uncommitted store files in the assembly worktree that `migrate_lane` does not copy (designs, plans, meta). The old gate refused on those. This is spec-directed, not a bug. | skills/run-autopilot/cli/wave_review.py:430 | 00225 | BLAKE |
| [1/4] | ⚪ | `_hold_backlog` renames backlog PRDs over any same-named file already in `hold/`, with no collision check. A same-name collision would overwrite silently (recoverable from git history only when the store is tracked). | skills/run-autopilot/cli/wave_review.py:244 | 00225 | BLAKE |
| [1/4] | ⚪ | `release-checks` also gained `test_wave_cli_refusals.py`, beyond the single file the PRD names. This is needed for the new parity test and for the PRD's own 00222 acceptance test, so it is minor and justified. | dev/bin/release-checks:159 | 00221 | BLAKE |
| [1/4] | ⚪ | Cannot statically verify: tests pass at reviewed HEAD (VERIFY: run `bash dev/bin/release-checks` and `uv run --no-project --with pytest --with pytest-xdist python -m pytest -q -n 4 skills/run-autopilot/cli -k "wave or review_once"`). Recorded verification reports 2247 passing tests. | N/A | general | BOB |

## Orchestrator verification of the 🟠

The one finding that decides convergence was checked against the code rather
than accepted on two reviewers' agreement:

- **Confirmed.** `wave_review.py:501` reads
  `def _land_review_failed(repo: Path, wave: dict) -> int:` — the design's
  `wave_path` parameter and `int | None` return were never added, and the body
  returns `4` unconditionally. `land` at `:542-550` inlines the stub check and
  falls through with `status` still `"review_failed"`. Nothing writes
  `converged`. `waves.md:190-193` states the opposite.
- **The recovery hole is real but narrower than described.** Inside
  `_land_converged`, `_land_merge` (`:465`) and `_land_migrate` (`:466`) run,
  then `_cycle_count` (`:468`) and `_append_summary_line` (`:469`), and only
  then the locked save of `status = "done"` (`:475-479`). A failure in
  `_cycle_count` or `_append_summary_line` leaves master fast-forwarded and the
  stub moved out of the worktree while `wave.json` still reads `review_failed`;
  the retry finds no stub and returns 4 permanently.
- **One reviewer claim is REFUTED.** Alice's and Blake's "after a `land` that
  returns 5" variant does not hold: `_land_converged` compares `repo_head`
  against `base_sha`/`assembly_tip` at `:460-463` and returns `None` **before**
  any mutation, so the refusal path moves nothing. The rework task records this
  so no recovery code is added for a path that does not need it.

## Alice

9 findings (0 critical, 0 high, 5 medium, 4 low). Full text in the table above.
Alice ran implementation-aware with the context file, the full diff and the
three computed blocks; no pack.

R1: fail
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
R13: pass

## Blake

13 findings (0 critical, 1 high, 3 medium, 9 low). Blind lens: PRD only, no
diff, no file list, no design doc, no review history. He located the code
himself and independently ran both verification commands.

Blake's own verification run:

- `python -m pytest -q -n 4 skills/run-autopilot/cli -k "wave or review_once"` gave 435 passed.
- `bash dev/bin/release-checks` completed with no failures; its waves block ran 420 tests, including the summary tests.
- Confirmed against the code: 00221 gating, 00239 guard, 00227 per-slot flock in `_claim`, `_discard` and `release` with an ownership check, and 00222 persist-before-teardown ordering with the `OSError` catch for assemble.
- Confirmed against the code: the 00225 `foreign_dirty` swap in `_land_cleanup` and `_hold_backlog` committing the move to `hold/` before the nested loop, plus the CHANGELOG line.

B1: fail
B2: pass
B3: fail
B4: pass
B5: pass
B6: pass
B7: pass
B8: pass
B9: pass
B10: pass
B11: pass
B12: pass
B13: pass
B14: pass
B15: fail
B16: pass
B17: pass
B18: pass
B19: pass

> Orchestrator note on B14, recorded as disagreement rather than as an edit to
> Blake's output: he voted `B14: pass` ("No unguarded database queries or file
> operations") while also raising an unguarded `Path.rename` in
> `_hold_backlog` that silently overwrites an existing `hold/<name>`. That is
> the operation B14 tests for, so the gate reads his verdict as inconsistent
> with his own finding. His line stands as emitted — a reviewer's recorded
> output is not rewritten here — and the routing is unaffected, because that
> finding is already queued for rework under task 11.

## Bob

6 findings (0 critical, 1 high, 4 medium, 1 low), doubt + de-slop lens, codex
static-only sandbox. Bob ran on the default roster (codex), carrying the two
doubt lenses and the D1-D5 rubric appended to his consensus persona.

R1: fail
R2: fail
R3: pass
R4: fail
R6: pass
R7: pass
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

## Carl

`[CARL] ✅ No issues found` — all twelve `R{n}` verdicts pass. Carl ran as a
generalist (the change has no frontend surface) on `backend=copilot
model=gemini-3.8-flash`, exit 0, with real tool activity in his transcript
(diff reads, a `release-checks` read, a debug/TODO marker sweep, a `wave_slots`
search). His clean verdict stands as recorded, and it is the minority view: the
other three lenses each found the 00226 gap or its consequences.

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
R13: pass

## Verification-check queue

Empty for this cycle, and no `00242-harden-the-wave-verbs-v1-checks-1.json`
was written. Eve is not active (see the lens roster above), and Bob's assembled
persona carries the two doubt lenses and the D-rubric but not the
FIX/VERIFY/KNOWN bucket section, so no doubt-lens VERIFY bucket existed to
collect. Bob's `⚪ Cannot statically verify` line names two exact commands;
both were run inside this cycle (the orchestrator's `release-checks` run below,
and Blake's `-k` run above), so it is recorded as discarded-on-evidence in the
ledger rather than queued.

## Decision gate (Phase 5)

Cap check: `state.cycle` 1, `state.rework_cap` 2. One unresolved 🟠 HIGH
remains, so the cycle did **not** converge; `1 < 2`, so rework is allowed and
the cap does not fire.

Safety checks: 5 follow-up tasks created, under the 10-task scope alarm. No
prior cycle to compare issue counts against. No issue is a reappearance. All
four reviewers produced parseable output — no transient degradation beyond the
pack failure recorded above.

Dispositions, covering all 21 rows:

**Auto-fix — 5 `[D1]` tasks queued** (ids 8-12, all `sonnet`; no 🔴 row, so no
rework design pass and no `default_model` opus floor):

| Task | Rows it closes |
|------|----------------|
| 8 — Save converged on the hand-review land route (00226) | the 🟠, the waves.md:192 mismatch, the `land` 50-line simplification |
| 9 — Retry the branch delete on rerun and widen the OSError guard (00222) | the [3/4] `_drain_lane` branch leak, the `wave run` OSError gap, Blake's branch-leak row |
| 10 — Restore the PRD's acceptance test ids and make them fail-first (00221, 00225) | the test-id deviation, the retry-test base-pass, `test_every_wave_test_file_is_listed`, `test_seeded_backlog_prds_are_held_before_the_nested_loop` |
| 11 — Make `_hold_backlog` safe under partial failure (00225) | the uncommitted-move retry gap, Bob's same finding, the silent `hold/` overwrite |
| 12 — Keep `release` non-raising under the slot lock (00227) | the `_slot_lock` unguarded mkdir/open in a `finally:`, Blake's same finding |

**Deferred to batch end — 3** (recorded via `autopilot defer` into
`202610031511-deferred.json`, in `state.deferred_decisions`, and in the ledger):

- 00225 report-naming promise + the suspected `hold/`-on-master side effect — requirements ambiguity between the PRD's Outputs and its Risks; the design doc already flagged the report half as an unclaimed planner task, and the land-routing half is explicitly unconfirmed.
- The pre-existing `_drain_lane` crash window before the first save — both raising reviewers call it pre-existing and matching the PRD's literal wording.
- `_land_cleanup` + `--force` discarding uncommitted non-migrated store files — spec-directed, labelled "not a bug" by the reviewer who raised it.

**Discarded with a verified reason — 7** (all in the ledger with their
reasoning): threads vs "three processes" (flock is per open file description),
`release`'s signature change (design-decided, documented, caller updated), the
extra gated test file (required by the PRD's own 00222 acceptance test), Bob's
cannot-statically-verify line (answered in-cycle), and three `mech-check`
replay rows whose tests legitimately pass at base (`test_assemble_lets_a_non_os_error_propagate`
is the complement guard, `test_review_failed_without_hand_review_still_exits_four`
is the documented else-branch regression guard, and the two `test_wave_slots.py`
tests pre-date this PRD).

Next: rework the 5 queued tasks, then review cycle 2.

Verdict: 21 findings
Tests: 2247 passed, 0 failed, 0 skipped (suite run this cycle)
