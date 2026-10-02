---
prd: dev/local/prds/wip/00207-route-rework-resume-sessions-on-task-tier-v1.md
review: 2
date: 2026-09-21
head_sha: 64d0ce30b3222528e83e34dacf5f3515b2a91b8f
codex_thread_id: 01a0c2bd-fbce-7802-b03a-705ca48ebce7
reviewers: alice,blake,bob,carl
agents:
  alice: available
  blake: available
  bob: available
  carl: available
---

# Review: 00207-route-rework-resume-sessions-on-task-tier-v1

Diff range: `012df973bc807e30e0fa0f7713db0061ca36cd7c..64d0ce30b3222528e83e34dacf5f3515b2a91b8f`
(incremental review, cycle 2: the one rework commit `64d0ce3` since cycle 1's HEAD; `gather-context.sh --since 012df97`)

codex_rung_guard: not fired

Run mode: standalone (`dev/local/autopilot/state.json` absent), invoked under `_AUTOPILOT_LOOP=1` / `CLAUDE_UNATTENDED=1`. No task context (no state); tasks reconstructed from the PRD phases and the three branch commits. No follow-up tasks were created (no autopilot state to write them into); findings are reported here.
consensus_engine: legacy (no frontmatter value). doubt_reviewer: codex (no frontmatter value); Eve not active.
pack: failed (`engram pack` exit 1 twice: `not inside a registered repo; register it in ~/.config/gita/repos.csv`, the worktree is unregistered). Prompts carried `(no pack available this cycle)`.
ledger: none (no `-ledger.json` was written after cycle 1; cycle-1 decisions were unattended packets, so nothing was settled and no Blake finding was auto-dismissed).
Bob resumed his cycle-1 codex thread (`--resume-thread`), no retry; the thread id sidecar re-emitted the same id.

## Review Summary

Reviewed: 2 build tasks (T1 `8ba444c`, T2 `012df97`, reviewed in cycle 1) plus the rework commit R1 `64d0ce3` (this cycle's scope)
PRDs checked: 00207-route-rework-resume-sessions-on-task-tier-v1

### Agent Status
- Alice: ✅ Available (Task subagent `autopilot:alice`)
- Blake: ✅ Available (Task subagent `autopilot:blake`, PRD-only; no filesystem-notes trigger)
- Bob: ✅ Available (codex, exit 0, resumed thread `01a0c2bd-fbce-7802-b03a-705ca48ebce7`, no retry)
- Carl: ✅ Available (backend=copilot model=gemini-3.8-flash, exit 0; output carries the copilot tool trace above the findings, findings and all twelve R verdicts present)
- Eve: ⏸️ Disabled (doubt_reviewer=codex, guard not fired)

### Prior findings: resolution status (all four reviewers agree unless noted)

| Cycle-1 packet | Status | Evidence |
|---|---|---|
| 1 `rework_resume -> bool` (HIGH, 4/4) | **resolved** | `routing.py:279` `def rework_resume(autopilot_dir: Path) -> bool: return bool(_rework_tasks(autopilot_dir))` |
| 2 drop the `or` hedge | **not resolved** | `test_routing_rework.py:99-101` still `"## Review sessions" in ladder or "**Review sessions (PRD 00207).**" in ladder`, only reformatted; the commit message claims it was dropped |
| 3 pin the opus case / add fable case | **not resolved** | no new assertion; six touched tests all pass at base (replay) |
| 4 split test_routing.py | **partially** | rework tests moved to `test_routing_rework.py` (104 lines); `test_routing.py` is 803 lines, still over 800 (Carl counts it resolved: the PRD's own lines are gone) |
| 5 module docstring | **resolved** | `routing.py:27-34` names the rework-resume route |
| 6 SKILL.md "or fable" | **resolved** | `SKILL.md:44` |
| 7 cycle from loaded snapshot + fable/padded tests | **partially** | double read removed (`routing.py:271-273`); a missing or non-int `cycle` still defaults to 1 (Bob: contrary to "malformed state → fresh review"); no padded-filename or malformed-cycle test |
| 8 inline `_rework_model` | **resolved** | `_review_model` `routing.py:285`, 17 lines |

## Consolidated Findings

Script output (`consolidate_findings.py`, 4 agent pairs, no ledger) had 9 rows; it merged Alice/Bob's packet-3 rows after suffix stripping (`:62 ~ :59 ~ :50`) but did NOT merge the three `or`-hedge paraphrases at `test_routing_rework.py:99` (Alice, Bob, Carl). The table below merges those three by hand into one [3/4] row and says so. Mechanical test checks absorbed: the shapes `[MECH]` line joined the `:99` row; the fail-first replay `[MECH]` line (6 of 6 touched tests pass at base) joined the packet-3 row.

| Consensus | Severity | Issue | File | Task | Found By |
|-----------|----------|-------|------|------|----------|
| [3/4] | 🟡 | `rework_resume` is imported in `test_routing_rework.py:13` but never called by any test; the new boolean API is unpinned (only `route()` is exercised) and the import is dead | skills/run-autopilot/cli/test_routing_rework.py:13 | R1 | ALICE, BOB, CARL |
| [3/4] | 🟡 | `test_docs_name_the_rework_resume_rule` still hedges its heading assertion with `or`; only `**Review sessions (PRD 00207).**` exists in the ladder, the other branch is dead. The rework commit message claims packet 2 was taken; the assert was only reformatted (hand-merged from three paraphrases) | skills/run-autopilot/cli/test_routing_rework.py:99 | T2 | ALICE, BOB, CARL, mech-check |
| [2/4] | 🟡 | Packets 3 and 7 (tests) not taken: no fable-tier case, no `-review-01.md` padded-filename case, no stderr assertion on the opus case, no malformed-cycle case; all six touched tests pass unmodified against the pre-rework code (replay) | skills/run-autopilot/cli/test_routing_rework.py:62 | R1 | ALICE, BOB, mech-check |
| [2/4] | 🟡 | `test_routing.py` is 803 lines after the split, still over the 800-line ceiling (802 before this PRD, 890 after T1) | skills/run-autopilot/cli/test_routing.py:1 | general | ALICE, BOB |
| [1/4] | 🟡 | A missing or non-int `cycle` still resolves to 1 in `_rework_tasks`, so a malformed state with pending rework ids and a stale `-review-1.md` classifies as a resume; the PRD says malformed state is a fresh review | skills/run-autopilot/cli/routing.py:271 | R1 | BOB |
| [1/4] | 🟡 | The PRD's Success Metric names `pytest -q skills/run-autopilot/cli/test_routing.py` and Phase 0/1 acceptance names `test_routing.py::...`; the four cases and the docs test now live in `test_routing_rework.py`, so the PRD text no longer matches where the tests are (traceability, not behavior) | skills/run-autopilot/cli/test_routing_rework.py | general | BLAKE |
| [1/4] | ⚪ | Cannot statically verify: full CLI suite and release checks pass at HEAD (Bob, two lines) | N/A | general | BOB |

Bob's ⚪ items are closed by this cycle's own runs: `skills/run-autopilot/cli` suite 1300 passed, `bash dev/bin/release-checks` green (every section passed, exit 0). Alice and Carl also ran the two routing files (72 passed) and Blake ran each (66 + 6 passed).

Rubric fails this cycle: R1 and R2 fail from Alice, Bob and Carl (no new pin in the rework; the six touched tests pass at base); R11 fail from Alice (unused import); R13 fail from Alice and Bob (803 lines); R7 and R9 fail from Bob (malformed `cycle` accepted as a resume). Blake fails B15 only (Phase 0 acceptance names `test_routing.py`).

## Decision packets (unattended run: written, not asked)

Agenda: 5 decisions after merging duplicates. 0 CRITICAL, 0 HIGH, 5 MEDIUM (the last two bundled). The PRD's `rework_cap` is 2, so this is the last rework cycle before the loop parks the PRD; every fix below is S.

### 1 of 5 - 🟡 MEDIUM - the `or` hedge is still there, and the commit says it is not (Alice, Bob, Carl, mech-check)

**What.** `test_routing_rework.py:99-101` asserts `"## Review sessions" in ladder or "**Review sessions (PRD 00207).**" in ladder`. Only the second string exists. The cycle-1 rework commit message says "the docs pin no longer hedges with or"; the diff shows the assert reformatted over three lines and otherwise unchanged. Found by three reviewers and `detect_tautological_tests.py` a second time.
**Evidence.** Confirmed: the diff hunk at `test_routing_rework.py:327-329` and the shapes block `[MECH]` line.
**If unchanged.** Same as cycle 1: a heading rename passes silently. Stable. Plus a commit message that misstates what landed.
**Options.**
- **(Recommended) Pin the one real string.** Replace the three-line assert with `assert "**Review sessions (PRD 00207).**" in ladder`. Effort S. Could break: nothing. Reason against: none; it is a one-line cut that was already agreed in cycle 1.
- **Pin the heading form** and turn the ladder paragraph into `## Review sessions`. Effort S, but a docs restructure for a test.
- **Accept and ledger** as "the `rework resume` phrase assertion pins the substance". Drawback: mech-check re-raises it every cycle until a ledger exists.

### 2 of 5 - 🟡 MEDIUM - `rework_resume` imported, never called; the bool API has no test (Alice, Bob, Carl)

**What.** The new module imports `rework_resume` (`test_routing_rework.py:13`) but every test goes through `route()`. The cycle-1 HIGH was "return a bool"; the fix landed but nothing asserts `rework_resume(ap_dir) is True` / `is False`, and the import is dead (Alice fails R11 on it).
**Evidence.** Confirmed: `rg 'rework_resume\(' skills/run-autopilot/cli/test_routing_rework.py` finds only the import line.
**Options.**
- **(Recommended) Use the import.** Add `assert rework_resume(ap_dir) is True` to the sonnet case and `assert rework_resume(ap_dir) is False` to the missing-file and all-completed cases (three one-line additions). Pins the PRD's stated output type and makes the import live. Effort S. Could break: nothing. Reason against: the assertions duplicate what `route().model` already implies.
- **Drop the import.** One-line deletion; the bool contract stays unpinned. Effort S.
- **Accept.**

### 3 of 5 - 🟡 MEDIUM - no new test pins the rework: fable, padded filename, opus stderr, malformed cycle (Alice, Bob, mech-check)

**What.** Cycle-1 packets 3 and 7 asked for a `fable` task case, a `-review-01.md` case, a stderr assertion on the opus case, and (after this rework's own `cycle` parsing) a malformed-cycle case. None landed. The replay shows all six touched tests passing at the pre-rework base, which is expected for a test move but also means the cycle-2 diff added zero pins for the `cycle` parsing it introduced at `routing.py:271-273`.
**Evidence.** Confirmed by the replay block (6/6 pass at `012df97`) and the diff (no new test function).
**If unchanged.** The `fable` branch of `_review_model` and the padded-filename branch of `_cycle_review_file` stay unpinned; a regression in either is caught by nothing. Stable.
**Options.**
- **(Recommended) Add three cases to `test_routing_rework.py`.** `test_rework_resume_with_fable_task_routes_opus` (one `model: fable` task → OPUS, asserts the stderr line), `test_rework_resume_padded_review_filename_counts` (`_rework_box` gains `padded: bool` writing `-review-01.md` → SONNET), `test_rework_resume_with_non_int_cycle_is_a_fresh_review` (`cycle: "1"` → OPUS if packet 4 below is taken, else pins the current default-to-1 behavior). Effort S. Could break: nothing. Reason against: the file grows ~30 lines; fine at 104.
- **Add only the fable case.** The one branch with real routing consequence. Effort S.
- **Accept: cycle-1 tests cover the PRD's four named cases.**

### 4 of 5 - 🟡 MEDIUM - malformed `cycle` still counts as cycle 1 (Bob; Alice and Carl call the reread fix resolved)

**What.** `_rework_tasks` now parses `cycle` from the loaded snapshot (good: one read) but mirrors `review_cycle`'s "non-int → 1" default. Bob reads the PRD's "missing or malformed state → false (fresh review)" as forbidding that: a state with `cycle: "abc"`, pending rework ids and a stale `-review-1.md` routes Sonnet. Alice and Carl accepted the mirror as the documented behavior (the docstring at `routing.py:266-267` says so explicitly).
**Evidence.** Confirmed by reading `routing.py:271-273`; the scenario needs a malformed `cycle` next to a well-formed `rework_task_ids`, which Phase 0 and `phase-done` never write. Suspected impact only.
**Options.**
- **(Recommended) Accept as documented, ledger the reason.** `review_cycle` itself treats the same input as 1 for the effort rule; two readers of one field should not disagree. Effort none. Reason against: it leaves Bob's reading of the PRD sentence unanswered in code.
- **Return `[]` on a non-int `cycle`.** Two-line change plus the test from packet 3. Benefit: matches the PRD sentence literally. Drawback: the effort rule (`review_cycle`) still reads that state as cycle 1, so the launch becomes "Opus xhigh on a malformed state" — consistent with fail-expensive. Effort S.
- **Accept without ledger.**

### 5 of 5 - 🟡 MEDIUM bundle (one line each)

- `test_routing.py` still 803 lines (Alice, Bob). Recommended: move `_ap_dir_with_cycle` and the nine `test_review_cycle_*` cases (`test_routing.py:561-637`, ~75 lines) to `test_routing_rework.py` or a `test_routing_review.py`, both review-routing (S). Or accept: 3 lines over a pre-existing overrun, ledger it.
- PRD text names `test_routing.py` for the four cases and the docs test; they live in `test_routing_rework.py` (Blake, B15). Recommended: amend the PRD's Success Metric and the two acceptance lines to `test_routing_rework.py` when the PRD moves to `done/` (S). Or accept: the PRD is a record, the commit message states the move.

## Alice

[ALICE] 🟡 test_docs_name_the_rework_resume_rule still hedges with `or` (only "**Review sessions (PRD 00207).**" exists in model-ladder.md, the other branch is dead) — commit message claims packet 2 ("drop the `or` hedge") but the assert is untouched apart from reformatting | File: skills/run-autopilot/cli/test_routing_rework.py:99 | Task: general
[ALICE] ⚪ `rework_resume` imported in test_routing_rework.py:13 but never called directly by any test — only exercised indirectly through `route()`; dead import plus an untested public API (boolean return never asserted) | File: skills/run-autopilot/cli/test_routing_rework.py:13 | Task: general
[ALICE] 🟡 test_routing.py is still 803 lines, over the 800-line ceiling (was 802 before this PRD, 890 after cycle-1, now 803 after this rework moved content out) — the rework reduced it but did not bring it back under the cap | File: skills/run-autopilot/cli/test_routing.py:1 | Task: general
[ALICE] 🟡 Packet 3/8 not taken: no fable-tier test, no padded-filename (`-review-01.md`) test, no stderr assertion on the opus-routing case, no malformed-state fallback test — all six touched tests in test_routing_rework.py still pass unmodified against pre-change code per the fail-first replay | File: skills/run-autopilot/cli/test_routing_rework.py:62 | Task: general

Prior 1 resolved; 2 partially (803 lines); 3 not resolved; 4 resolved; 5 not resolved; 6 resolved; 7 resolved; 8 not resolved; 9 resolved. Ran the two routing files: 72 passed.

R1: fail, R2: fail, R3: pass, R4: pass, R6: pass, R7: pass, R8: pass, R9: pass, R10: pass, R11: fail, R12: pass, R13: fail

## Blake

[BLAKE] 🟡 PRD's literal Success-Metric command (`pytest -q skills/run-autopilot/cli/test_routing.py`) no longer demonstrates the four new rework-resume cases or the docs test: they were moved to a new file `cli/test_routing_rework.py` in the review-fixup commit to stay under the 800-line file ceiling, documented in the commit message but not reflected in the PRD text. Functionality is fully covered when running the whole cli/ suite, so this is a documentation/traceability gap, not a behavioral bug. | File: skills/run-autopilot/cli/test_routing_rework.py | Task: 0

Everything else checked out against the PRD (detection rule incl. both filename spellings, tier rule incl. fable and the no-`model` default, effort and cap untouched, env override, no latch, stderr line verbatim, docs and CHANGELOG present; `test_routing.py` 66 passed, `test_routing_rework.py` 6 passed).

B1-B14: pass, B15: fail, B16-B19: pass

## Bob

[BOB] 🟡 Documentation test still hedges its heading assertion with `or`; packet 2 was not taken | File: skills/run-autopilot/cli/test_routing_rework.py:99 | Task: T2
[BOB] 🟡 `rework_resume` is imported but never exercised, leaving the new boolean API unpinned and the import unused | File: skills/run-autopilot/cli/test_routing_rework.py:13 | Task: T1
[BOB] 🟡 Packet 3 was not taken: the opus case lacks a diagnostic assertion, no fable case exists, and the existing stderr assertion is not exact | File: skills/run-autopilot/cli/test_routing_rework.py:59 | Task: T1
[BOB] 🟡 Missing or non-integer `cycle` still defaults to 1 and can classify malformed state as a resume, contrary to the PRD | File: skills/run-autopilot/cli/routing.py:271 | Task: T1
[BOB] 🟡 Packet 7 coverage remains incomplete: no padded-filename or malformed-cycle test exists | File: skills/run-autopilot/cli/test_routing_rework.py:50 | Task: T1
[BOB] 🟡 The split leaves `test_routing.py` at 803 lines, still above the 800-line ceiling | File: skills/run-autopilot/cli/test_routing.py:1 | Task: general
[BOB] ⚪ Cannot statically verify: full CLI test suite passes at HEAD | File: N/A | Task: general
[BOB] ⚪ Cannot statically verify: release checks pass at HEAD | File: N/A | Task: general

Prior 1 resolved; 2 partially; 3 not resolved; 4 resolved; 5 not resolved; 6 partially (reread removed, malformed cycle accepted); 7 resolved; 8 not resolved; 9 resolved.

R1: fail
R2: fail
R3: pass
R4: pass
R6: pass
R7: fail
R8: pass
R9: fail
R10: pass
R11: pass
R12: pass
R13: fail

FIX: 6 items (the hedge; the bool API test; the opus/fable pins; the malformed-cycle rule; the padded/malformed-cycle tests; the oversized module). VERIFY: run `uv run --no-project --with pytest python -m pytest -q skills/run-autopilot/cli` (done this cycle: 1300 passed); run `bash dev/bin/release-checks` (done this cycle: green). KNOWN: (none).

D1: pass
D2: pass
D3: pass
D4: pass
D5: pass

## Carl

backend=copilot model=gemini-3.8-flash

[CARL] 🟡 test_docs_name_the_rework_resume_rule hedges with or: either outcome satisfies it | File: skills/run-autopilot/cli/test_routing_rework.py:99 | Task: general
[CARL] 🟡 Unused import rework_resume; public boolean API lacks direct test coverage | File: skills/run-autopilot/cli/test_routing_rework.py:13 | Task: T1

Prior 1 resolved; 2 resolved (tests moved); 3 not resolved; 4 resolved; 5 not resolved; 6 partially; 7 resolved; 8 not resolved; 9 resolved.

R1: fail, R2: fail, R3: pass, R4: pass, R6: pass, R7: pass, R8: pass, R9: pass, R10: pass, R11: pass, R12: pass, R13: pass

## Follow-up Tasks Created

None: standalone run, no `state.json` to write tasks into. The 5 decision packets above are the work list; every one is S effort. Verification-check queue not written (standalone, no `state.cycle`).

Verdict: 7 findings
Tests: 1300 passed, 0 failed, 0 skipped (suite run this cycle: `uv run --no-project --with pytest python -m pytest -q skills/run-autopilot/cli`, 660 subtests passed, 7 warnings all pre-existing pytest tmp-dir and legacy-schema warnings; `bash dev/bin/release-checks` also green, exit 0)
