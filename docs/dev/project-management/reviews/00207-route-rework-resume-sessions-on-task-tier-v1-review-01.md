---
prd: dev/local/prds/wip/00207-route-rework-resume-sessions-on-task-tier-v1.md
review: 1
date: 2026-09-21
head_sha: 012df973bc807e30e0fa0f7713db0061ca36cd7c
codex_thread_id: 01a0c2bd-fbce-7802-b03a-705ca48ebce7
reviewers: alice,blake,bob,carl
agents:
  alice: available
  blake: available
  bob: available
  carl: available
---

# Review: 00207-route-rework-resume-sessions-on-task-tier-v1

Diff range: `b78bc1165d44e05dc2a9faa7cc8dfa114a9c14a7..012df973bc807e30e0fa0f7713db0061ca36cd7c`
(full review, cycle 1; the PRD's merge-base with `master`, which has since taken 00207-00211. The branch's `routing.py`, `test_routing.py` and `model-ladder.md` are byte-identical to `master`'s.)

codex_rung_guard: not fired

Run mode: standalone (`dev/local/autopilot/state.json` absent), invoked under `_AUTOPILOT_LOOP=1` / `CLAUDE_UNATTENDED=1`. No task context (no state); the two tasks below were reconstructed from the PRD phases and the two branch commits. No follow-up tasks were created (no autopilot state to write them into); findings are reported here.
consensus_engine: legacy (no frontmatter value). doubt_reviewer: codex (no frontmatter value); Eve not active.
pack: failed (`engram pack` exit 1: `not inside a registered repo; register it in ~/.config/gita/repos.csv`, the worktree is unregistered; retry with `--diff` refused as mutually exclusive with `--cycle`). Prompts carried `(no pack available this cycle)`.
ledger: none (cycle 1).

## Review Summary

Reviewed: 2 completed tasks (T1 `8ba444c` routing + tests, T2 `012df97` docs + changelog)
PRDs checked: 00207-route-rework-resume-sessions-on-task-tier-v1

### Agent Status
- Alice: ✅ Available (Task subagent `autopilot:alice`)
- Blake: ✅ Available (Task subagent `autopilot:blake`, PRD-only; no filesystem-notes trigger)
- Bob: ✅ Available (codex, exit 0, thread `01a0c2bd-fbce-7802-b03a-705ca48ebce7`, no retry)
- Carl: ✅ Available (backend=copilot model=gemini-3.8-flash, exit 0; output carries the copilot tool trace above the findings, findings and all twelve R verdicts present)
- Eve: ⏸️ Disabled (doubt_reviewer=codex, guard not fired)

## Consolidated Findings

Script output (`consolidate_findings.py`, 4 agent pairs, no ledger). The script reported one suffix-stripped merge (`test_routing.py:1 ~ :707`). It did NOT merge three evident paraphrase groups; the decision packets below merge them by hand and say so.

| Consensus | Severity | Issue | File | Task | Found By |
|-----------|----------|-------|------|------|----------|
| [4/4] | 🟠 | `rework_resume` returns `list[dict]` (the pending tasks) but the PRD's Feature 1 "Outputs" spec names it `rework_resume(autopilot_dir) -> bool`; a predicate-named function returning a payload instead of a boolean is a naming/contract drift that a future caller could trip on | skills/run-autopilot/cli/routing.py:250 | T1 | ALICE, BLAKE, BOB, CARL |
| [2/4] | 🟡 | test_routing.py is 890 lines, over the 800-line file ceiling; it was already over (802) before this PRD, and this diff adds 88 more lines to the same file instead of splitting the rework-resume cases into their own test module | skills/run-autopilot/cli/test_routing.py:1 | T1 | ALICE, BOB |
| [2/4] | 🟡 | Four new tests pass against pre-change code, so the opus-task, missing-file, completed-list, and override cases are not fail-first pinned | skills/run-autopilot/cli/test_routing.py:751 | T1 | BOB, CARL, mech-check |
| [1/4] | 🟡 | Module docstring still says "Review stays on Opus on every cycle" after this diff makes that false for rework-resume launches; the doc-name task (T2) updated SKILL.md and model-ladder.md but left this stale claim in the same file the code change lives in | skills/run-autopilot/cli/routing.py:11 | T2 | ALICE |
| [1/4] | 🟡 | test_docs_name_the_rework_resume_rule hedges its heading assertion with `or` (either "## Review sessions" or "**Review sessions (PRD 00207).**" satisfies it) though only the second string is ever used in the file, making half the assertion dead weight | skills/run-autopilot/cli/test_routing.py:886 | T2 | ALICE, mech-check |
| [1/4] | 🟡 | Malformed state can be classified as a resume: an invalid/missing cycle defaults to 1, and string conversion can match id-less/invalid task IDs | skills/run-autopilot/cli/routing.py:223 | T1 | BOB |
| [1/4] | 🟡 | `_rework_model` is a trivial single-caller abstraction; inline its conditional into `_review_model` | skills/run-autopilot/cli/routing.py:270 | T1 | BOB |
| [1/4] | 🟡 | Tests omit the fable tier, padded review filename, boolean API, malformed-state model fallback, and exact stderr contract | skills/run-autopilot/cli/test_routing.py:739 | T1 | BOB |
| [1/4] | 🟡 | Documentation test hedges with `or` instead of pinning one required review-section structure | skills/run-autopilot/cli/test_routing.py:886 | T2 | BOB |
| [1/4] | 🟡 | Core skill prose incorrectly says only an opus task selects Opus, omitting the required fable case | skills/run-autopilot/SKILL.md:44 | T2 | BOB |
| [1/4] | 🟡 | test_docs_name_the_rework_resume_rule hedges with or: either outcome satisfies it | skills/run-autopilot/cli/test_routing.py:886 | general | CARL |
| [1/4] | 🟡 | Redundant state.json re-read in rework_resume: pass cycle from already-loaded state instead of calling review_cycle() | skills/run-autopilot/cli/routing.py:264 | T1 | CARL |
| [1/4] | ⚪ | Module documentation still claims every review stays on Opus | skills/run-autopilot/cli/routing.py:10 | T1 | BOB |
| [1/4] | ⚪ | Cannot statically verify: routing tests actually run and pass | N/A | T1 | BOB |

Mechanical test checks absorbed: the `or`-hedge `[MECH]` line joined the :886 row; the fail-first replay `[MECH]` line (4 of 6 touched tests pass at base) joined the :751 row. No new rows.

Bob's two ⚪ "Cannot statically verify" items (routing tests; release-checks) are closed by this cycle's own runs: `skills/run-autopilot/cli` suite 1300 passed, `bash dev/bin/release-checks` green (every section passed, exit 0).

## Decision packets (unattended run: written, not asked)

Agenda: 8 decisions after merging duplicates. 0 CRITICAL, 1 HIGH, 7 MEDIUM (two of them bundled as LOW-effort leftovers at the end).

### 1 of 8 - 🟠 HIGH - `rework_resume` returns a list, the PRD promised a bool

**What.** `cli/routing.py:250` defines `rework_resume(autopilot_dir) -> list[dict]` (the unfinished rework tasks). The PRD's Feature 1 "Outputs" line says `rework_resume(autopilot_dir) -> bool`. All four reviewers flagged it; Blake fails B3, Bob and Carl fail R9 on it. The routing *decision* is correct (empty list is falsy), only the exported signature drifts from the spec.
**Evidence.** Confirmed: diff line `def rework_resume(autopilot_dir: Path) -> list[dict]:`; `model-ladder.md` names `cli/routing.rework_resume` as the decider.
**If unchanged.** No runtime effect today (single caller `_review_model` uses the list). A future caller reading the PRD or the docstring name expects a bool and may compare `== True`. Stable, does not compound.
**Options.**
- **(Recommended) Return `bool`, keep the list private.** `rework_resume` becomes `return bool(_pending_rework(autopilot_dir))` and `_review_model` calls the private list helper. Benefit: matches the PRD and the predicate name. Drawback: one more tiny function in a module that already has five new ones. Effort S. Could break: nothing; tests call `route()`, not `rework_resume`. Strongest reason against: it adds code to satisfy a signature no caller needs.
- **Rename to say what it returns.** `unfinished_rework_tasks(autopilot_dir) -> list[dict]` and amend the PRD Outputs line + `model-ladder.md` reference + `test_docs...` assertion. Benefit: no extra function, honest name. Drawback: PRD edit after the fact; docs test pinning `cli/routing.rework_resume` must change. Effort S.
- **Accept the drift, ledger it.** Benefit: zero diff. Drawback: three reviewers keep failing the spec rule on every cycle; a spec/code mismatch stays on record.

### 2 of 8 - 🟡 MEDIUM - docs test hedges with `or` (Alice, Bob, Carl, mech-check: 3/4 + machine)

**What.** `test_routing.py:886` asserts `"## Review sessions" in ladder or "**Review sessions (PRD 00207).**" in ladder`. Only the second string exists; the first is dead weight and the assertion can pass on either shape. Found by three reviewers and `detect_tautological_tests.py`.
**Evidence.** Confirmed by the shapes block (`[MECH] 🟡 ... hedges with or`).
**If unchanged.** A future edit that renames the paragraph to a heading, or drops the PRD tag, still passes. Stable.
**Options.**
- **(Recommended) Pin the one real string.** Drop the `or` branch; assert `"**Review sessions (PRD 00207).**" in ladder`. Effort S. Could break: nothing. Reason against: none worth naming; it is a one-line cut.
- **Pin the heading form instead.** Turn the ladder paragraph into a `## Review sessions` heading and assert that. Benefit: the ladder gains a navigable section. Drawback: a docs restructure for a test. Effort S.
- **Accept.** The `rework resume` phrase assertion below it already pins the substance. Drawback: the hedge stays and the mech-check re-raises it every cycle.

### 3 of 8 - 🟡 MEDIUM - four new tests pass against the pre-change code (Bob, Carl, mech-check)

**What.** `test_rework_resume_with_one_opus_task_routes_opus`, `test_fresh_review_without_review_file_routes_opus`, `test_rework_resume_with_all_tasks_completed_routes_opus`, `test_rework_resume_env_model_override_still_wins` all assert `OPUS`, which the pre-change router already returned for every review launch. They guard the fresh-review path from regressing but do not pin the new detector. The sonnet case and the stderr line are pinned (2 of 6 fail at base).
**Evidence.** Confirmed by the fail-first replay (`4 passed` at `b78bc11`).
**If unchanged.** A bug that makes `rework_resume` always return empty (never resume) is caught only by the sonnet test; a bug in the opus branch of `_rework_model` (say, `fable` dropped) is caught by nothing. Stable.
**Options.**
- **(Recommended) Pin the opus-task case with the stderr line.** In `test_rework_resume_with_one_opus_task_routes_opus`, add `capsys` and assert `"rework resume, 2 task(s) left, routing" in err` plus the OPUS model name; add one `fable` task case the same way (also closes half of packet 7). Effort S. Could break: nothing. Reason against: the missing-file / all-completed / env-override tests are regression guards by design and stay base-passing; the replay will still list three.
- **Ledger-dismiss as by-design.** These three are fresh-review guards; record the reason so the mech-check line is auto-dismissed next cycle. Drawback: the opus branch stays unpinned.
- **Accept as is.**

### 4 of 8 - 🟡 MEDIUM - `test_routing.py` is over the 800-line ceiling (Alice, Bob; Alice fails R13)

**What.** 890 lines at HEAD, 802 before this PRD; the diff added 88 lines to a file already over. Alice and Bob flag it; Carl passes R13 (he judged the pre-existing overrun not this diff's).
**Evidence.** Confirmed: `wc -l` 890 / 802.
**If unchanged.** Style ceiling only. Compounds: every routing PRD appends here.
**Options.**
- **(Recommended) Move the new block to `cli/test_routing_review.py`.** The `_rework_box` helper and the five rework tests plus `test_docs_name_the_rework_resume_rule` are self-contained (they import `route`, `Route`, `OPUS`, `SONNET`). Effort S. Could break: the PRD's success metric names `test_routing.py` for the four cases; release-checks does not list either file, so nothing red. Reason against: the PRD text says the tests live in `test_routing.py`.
- **Split an older cohesive section instead** (the `build_model` signal tests, ~400 lines). Benefit: keeps the PRD's file name true. Drawback: touches code this PRD did not write. Effort M.
- **Accept: pre-existing overrun**, ledger it with that reason.

### 5 of 8 - 🟡 MEDIUM - stale module docstring in `routing.py` (Alice 🟡, Bob ⚪; merged)

**What.** `routing.py:11-12` still reads "Review stays on Opus on every cycle". The diff makes that false for rework resumes; T2 updated `SKILL.md` and the ladder but not the module that carries the code.
**Evidence.** Confirmed by reading `routing.py:11`.
**Options.**
- **(Recommended) One sentence.** "Review runs on Opus for a fresh review; a rework resume (PRD 00207) takes the queued tasks' tier." Effort S.
- **Delete the routing summary from the docstring** and point at `model-ladder.md` as the single source. Benefit: no second copy to drift. Drawback: the module loses its self-description. Effort S.
- **Accept.**

### 6 of 8 - 🟡 MEDIUM - `SKILL.md:44` omits `fable` (Bob)

**What.** The Execution Model sentence says "sonnet unless one is opus"; the code and the ladder say opus **or fable**.
**Evidence.** Confirmed by the diff (`SKILL.md` hunk vs `_rework_model`).
**Options.**
- **(Recommended) Add "or fable".** Effort S. Reason against: none.
- **Drop the tier detail from `SKILL.md`** and leave only the pointer to the ladder. Benefit: one place to keep true. Drawback: the sentence stops saying what the route does. Effort S.
- **Accept.**

### 7 of 8 - 🟡 MEDIUM - `rework_resume` re-reads `state.json` through `review_cycle()`; a missing `cycle` still resolves to 1 (Carl; Bob; merged with Bob's test-gap item on fable / padded filename)

**What.** `rework_resume` loads state once, then calls `review_cycle(autopilot_dir)`, which loads it again (`routing.py:264`). Bob adds: a state with no or an invalid `cycle` still reads as cycle 1, so a stale `-review-1.md` plus pending ids classifies as a resume even though the state is malformed, and the PRD says malformed state is a fresh review. Bob also notes no test covers the `fable` tier or the `-review-01.md` spelling.
**Evidence.** Confirmed (double load); the malformed-cycle path is suspected, not demonstrated with a real state file.
**If unchanged.** Two reads of a small file per launch: negligible. The malformed-cycle resume is unlikely (`cycle` is written by Phase 0 and `phase-done`), and the worse outcome is a sonnet orchestrator on a rework, not a lost lens.
**Options.**
- **(Recommended) Read `cycle` from the loaded snapshot and add two tests.** `_cycle_review_file(autopilot_dir, state.get("prd"), cycle)` with `cycle` parsed from the same dict (int, not bool, else fresh review); tests: one `fable` task → OPUS; review file spelled `-review-01.md` → resume. Effort S. Could break: `review_cycle`'s "bool is not int" rule must be mirrored, or an existing test class shifts. Reason against: it re-implements a sliver of `review_cycle`.
- **Keep the double read, only add the two tests.** Benefit: minimal code diff. Drawback: the malformed-cycle edge stays.
- **Accept.**

### 8 of 8 - 🟡 MEDIUM bundle (one line each)

- `_rework_model` is a six-line single-caller helper (Bob, `routing.py:270`). Recommended: inline into `_review_model` (S). Or keep it: it names the rule and keeps `_review_model` under 15 lines.
- Bob's ⚪ "cannot statically verify" items: closed by this cycle's runs (see above). No decision.

## Alice

[ALICE] 🟡 `rework_resume` returns `list[dict]` (the pending tasks) but the PRD's Feature 1 "Outputs" spec names it `rework_resume(autopilot_dir) -> bool`; a predicate-named function returning a payload instead of a boolean is a naming/contract drift that a future caller could trip on | File: skills/run-autopilot/cli/routing.py:250 | Task: T1
[ALICE] 🟡 Module docstring still says "Review stays on Opus on every cycle" after this diff makes that false for rework-resume launches; the doc-name task (T2) updated SKILL.md and model-ladder.md but left this stale claim in the same file the code change lives in | File: skills/run-autopilot/cli/routing.py:11 | Task: T2
[ALICE] 🟡 test_docs_name_the_rework_resume_rule hedges its heading assertion with `or` (either "## Review sessions" or "**Review sessions (PRD 00207).**" satisfies it) though only the second string is ever used in the file, making half the assertion dead weight | File: skills/run-autopilot/cli/test_routing.py:886 | Task: T2
[ALICE] 🟡 test_routing.py is 890 lines, over the 800-line file ceiling; it was already over (802) before this PRD, and this diff adds 88 more lines to the same file instead of splitting the rework-resume cases into their own test module | File: skills/run-autopilot/cli/test_routing.py:1 | Task: T1

R1: pass, R2: pass, R3: pass, R4: pass, R6: pass, R7: pass, R8: pass, R9: pass, R10: pass, R11: pass, R12: pass, R13: fail

## Blake

[BLAKE] 🟡 `rework_resume` returns `list[dict]` of pending tasks, not the `bool` the PRD's Outputs line specifies (`rework_resume(autopilot_dir) -> bool`); behavior is truthy-equivalent (empty list = false) and callers treat it that way, so the boolean *decision* is right, but the shipped interface signature does not match the spec's stated contract | File: skills/run-autopilot/cli/routing.py:250 | Task: 1

Everything else checked out against the PRD (truth table, tier rule, effort/cap untouched, stderr line verbatim, no latch, four named tests present, docs and CHANGELOG entries present, 72 passed in `test_routing.py`).

B1: pass, B2: pass, B3: fail, B4-B19: pass

## Bob

[BOB] 🟡 `rework_resume()` violates the required public API by returning task dictionaries instead of `bool` | File: skills/run-autopilot/cli/routing.py:250 | Task: T1
[BOB] 🟡 Malformed state can be classified as a resume: an invalid/missing cycle defaults to 1, and string conversion can match id-less/invalid task IDs | File: skills/run-autopilot/cli/routing.py:223 | Task: T1
[BOB] ⚪ Module documentation still claims every review stays on Opus | File: skills/run-autopilot/cli/routing.py:10 | Task: T1
[BOB] 🟡 `_rework_model` is a trivial single-caller abstraction; inline its conditional into `_review_model` | File: skills/run-autopilot/cli/routing.py:270 | Task: T1
[BOB] 🟡 Tests omit the fable tier, padded review filename, boolean API, malformed-state model fallback, and exact stderr contract | File: skills/run-autopilot/cli/test_routing.py:739 | Task: T1
[BOB] 🟡 Four new tests pass against pre-change code, so the opus-task, missing-file, completed-list, and override cases are not fail-first pinned | File: skills/run-autopilot/cli/test_routing.py:751 | Task: T1
[BOB] 🟡 Documentation test hedges with `or` instead of pinning one required review-section structure | File: skills/run-autopilot/cli/test_routing.py:886 | Task: T2
[BOB] 🟡 The 88-line addition grows an already oversized test file from 802 to 890 lines; extract a cohesive older section while retaining the mandated cases here | File: skills/run-autopilot/cli/test_routing.py:707 | Task: general
[BOB] 🟡 Core skill prose incorrectly says only an opus task selects Opus, omitting the required fable case | File: skills/run-autopilot/SKILL.md:44 | Task: T2
[BOB] ⚪ Cannot statically verify: routing tests actually run and pass | File: N/A | Task: T1
[BOB] ⚪ Cannot statically verify: release checks run and pass | File: N/A | Task: general

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

FIX: 9 items (the findings above minus the two ⚪ verify items). VERIFY: run `test_routing.py` (done this cycle: green); run `bash dev/bin/release-checks` (done this cycle: green). KNOWN: (none).

D1: pass
D2: pass
D3: pass
D4: pass
D5: pass

## Carl

backend=copilot model=gemini-3.8-flash

[CARL] 🟠 rework_resume returns list[dict] instead of bool specified by PRD contract | File: skills/run-autopilot/cli/routing.py:250 | Task: T1
[CARL] 🟡 test_docs_name_the_rework_resume_rule hedges with or: either outcome satisfies it | File: skills/run-autopilot/cli/test_routing.py:886 | Task: general
[CARL] 🟡 test_rework_resume_with_one_opus_task_routes_opus passes against pre-change code; does not assert rework-resume stderr announcement | File: skills/run-autopilot/cli/test_routing.py:751 | Task: T1
[CARL] 🟡 Redundant state.json re-read in rework_resume: pass cycle from already-loaded state instead of calling review_cycle() | File: skills/run-autopilot/cli/routing.py:264 | Task: T1

R1: pass, R2: fail, R3: pass, R4: pass, R6: pass, R7: pass, R8: pass, R9: fail, R10: pass, R11: pass, R12: pass, R13: pass

## Follow-up Tasks Created

None: standalone run, no `state.json` to write tasks into. The 8 decision packets above are the work list; every one is S effort.

Verdict: 14 findings
Tests: 1300 passed, 0 failed, 0 skipped (suite run this cycle: `uv run --no-project --with pytest python -m pytest -q skills/run-autopilot/cli`; `bash dev/bin/release-checks` also green, exit 0)
