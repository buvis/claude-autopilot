---
prd: dev/local/prds/wip/00209-run-a-forced-catchup-once-per-prd-entry-v1.md
review: 2
date: 2026-09-21
head_sha: ca4a8210fb43467e27ba5aa5104dd58203e3b0ca
codex_thread_id: 01a0c2bd-974f-7fa2-b349-821cabb2556f
reviewers: alice,blake,bob,carl
agents:
  alice: available
  blake: available
  bob: available
  carl: available
  eve: disabled
---

# Review: 00209-run-a-forced-catchup-once-per-prd-entry-v1

Diff range: `1c51b2d3e5258cd7410b15cf86f94da6af0521b7..ca4a8210fb43467e27ba5aa5104dd58203e3b0ca` (incremental: rework commit `ca4a821` since cycle 1's `head_sha`)

codex_rung_guard: not fired

Run mode: standalone (`dev/local/autopilot/state.json` absent; worktree `claude-autopilot-r2`, branch `review/00209`; `_AUTOPILOT_LOOP=1` and `CLAUDE_UNATTENDED=1` set, so the Watcher ran and the decision packets are written, not asked). No task store, no verification-check queue, no `task-add`: findings are reported here, not written as tasks.
Consensus engine: legacy (no `consensus_engine` in PRD frontmatter). Doubt reviewer: codex (default; Eve not dispatched). Bob resumed his cycle-1 thread (`--resume-thread`), single run, no retry.
Pack: failed (`engram pack` exits 1: worktree not registered in gita; same cause as cycle 1, no retry could change it). Prompts carried `(no pack available this cycle)`.
Ledger: none. Filesystem notes for the blind lens: not triggered (`dev/local` is a real directory, root basename has no leading dot).
Consolidation: `consolidate_findings.py`, four agent pairs. Mechanical checks: 0 tautological shapes in 27 tests; fail-first replay 2 ran, 1 failed against base, 1 reported passing (absorbed below, refuted by a manual replay).
Reviewed: 1 rework task (R1, commit `ca4a821`) answering the cycle-1 findings; five files, 58 insertions, 25 deletions.

## Agent Status

- Alice: ✅ Available (Task subagent)
- Blake: ✅ Available (Task subagent, PRD-only)
- Bob: ✅ Available (codex, exit 0, thread resumed and re-emitted)
- Carl: ✅ Available (gemini-run backend=copilot model=gemini-3.8-flash, exit 0)
- Eve: ⏸️ Disabled (doubt_reviewer resolves to codex; codex guard not fired)

## Prior findings (cycle 1) — status

| # | Sev | Cycle-1 finding | Status |
|---|-----|-----------------|--------|
| 1 | 🟠 | non-list `state.tasks` crashes `resume_target` | resolved: `_build_resume_target` isinstance guard (`resume.py:96`) + `NonListTasksTests` (Alice, Carl confirmed; Bob raised no re-finding) |
| 2 | 🟠 | encoded resume contract bypasses the cache check | resolved by prose: `phase-build.md:60` says the line adjudicates handlers only and every build entry still runs § Batch cache check; pinned at `test_custody_prose.py:385-396` (Alice, Carl confirmed) |
| 3 | 🟡 [2/4] | `state-schema.md:169` old `force` semantics | resolved: row carries the spent-once nuance (Alice confirmed) |
| 4 | 🟡 | prose test pins loose tokens | resolved: pin binds the OR predicate, the exact banner, the non-list sentence, the new resume-target sentence (Alice confirmed) |
| 5 | 🟡 | condition 1 dense | not taken (PRD dictates content); no reviewer re-raised |
| 6 | ⚪ | suites / release-checks | re-verified this cycle: full suite below; Blake and Carl each ran `bash dev/bin/release-checks` green |
| 7 | ⚪ | post-release metric | still post-release by definition (Bob re-raised as ⚪, row below) |

## Consolidated Findings

| Consensus | Severity | Issue | File | Task | Found By |
|-----------|----------|-------|------|------|----------|
| [1/4] | 🟡 | `_build_resume_target` still documents "tasks exist → /work," contradicting the new invariant that every build entry first runs the Batch cache check; describe its return as the post-Phase-1 resume point | skills/run-autopilot/cli/resume.py:92 | R1 | BOB |
| [1/4] | 🟡 | The new regression-test class appears after `unittest.main()`, so direct execution exits before defining it and silently omits the test | skills/run-autopilot/cli/test_resume.py:119 | R1 | BOB |
| [1/4] | 🟡 | `selection` names an abort-handler section, obscuring what the assertion covers; rename it `abort_handler` or `resume_contract` | skills/run-autopilot/cli/test_custody_prose.py:385 | R1 | BOB |
| [1/4] | 🟡 | 1 touched test passes against the pre-change code: `test_build_with_a_non_list_tasks_reads_as_no_tasks` | skills/run-autopilot/cli/test_resume.py | general | mech-check |
| [1/4] | ⚪ | Cannot statically verify: post-release forced-resume logging and first-task usage metric | N/A | T1 | BOB |

### Orchestrator grounding (facts checked after consolidation, not new findings)

- 🟡 test class after `unittest.main()`: confirmed. `PYTHONPATH=skills/run-autopilot python cli/test_resume.py` runs 11 tests (`OK`); the 12th, `NonListTasksTests`, is defined after the `__main__` guard at `test_resume.py:119` and is never loaded on direct execution. Under pytest (the project's runner, `dev/bin/release-checks`, and this cycle's suite) it IS collected and passes, so the gap is the direct-execution path only.
- 🟡 mech-check replay row: refuted. A manual replay of the same overlay (HEAD's `test_resume.py` on a `1c51b2d` worktree, pytest 9.1.1) reports `4 failed, 1 passed`: every `subTest` case fails at base (`AttributeError: 'str' object has no attribute 'get'`; `TypeError: 'int' object is not iterable`). pytest 9 reports those as `SUBFAILED` while the parent id reports `passed`, and `replay_tests_against_base.py` reads the parent line. The test is fail-first; the false positive is a script bug outside this PRD (follow-up below).
- 🟡 `_build_resume_target` docstring: confirmed as written (`resume.py:93-94` reads "tasks exist -> /work (or the review gate when all are done), else catchup then planning"). The string contract is unchanged and the prose at `phase-build.md:60` already states the ordering; this is a comment-accuracy nit.
- 🟡 `selection` name: style, single reviewer; the variable holds the `_section(...)` slice, consistent with the file's other `_section` uses.
- ⚪ post-release metric: not verifiable before release by construction; same as cycle 1.

## Alice

[ALICE] ✅ No issues found

R1: pass, R2: pass, R3: pass, R4: pass, R6: pass, R7: pass, R8: pass, R9: pass, R10: pass, R11: pass, R12: pass, R13: pass

Notes: all four taken cycle-1 findings verified resolved with file:line evidence (see the prior-findings table); the fail-first replay false positive recognised from the orchestrator note; ran `test_custody_prose.py` + `test_resume.py` (27 passed, 9 subtests), `test_autopilot_resume.py` + `test_review_resume_prose.py` (39 passed), and the full `skills/run-autopilot/cli/` directory (1296 passed, 0 failed). `_build_resume_target` is 18 lines, matching the mechanical block.

## Blake

[BLAKE] ✅ No issues found

B1-B19: all pass (B3, B4, B9-B14, B16, B17 vacuous: the PRD specifies none of those surfaces). Located `phase-build.md:181` and `:143`, `test_custody_prose.py:364`, `CHANGELOG.md:8-12`; ran the PRD's named target (19 passed) and `bash dev/bin/release-checks` (green).

## Bob

[BOB] 🟡 `_build_resume_target` still documents "tasks exist → /work," contradicting the new invariant that every build entry first runs the Batch cache check; describe its return as the post-Phase-1 resume point | File: skills/run-autopilot/cli/resume.py:92 | Task: R1
[BOB] 🟡 The new regression-test class appears after `unittest.main()`, so direct execution exits before defining it and silently omits the test | File: skills/run-autopilot/cli/test_resume.py:119 | Task: R1
[BOB] 🟡 `selection` names an abort-handler section, obscuring what the assertion covers; rename it `abort_handler` or `resume_contract` | File: skills/run-autopilot/cli/test_custody_prose.py:385 | Task: R1
[BOB] ⚪ Cannot statically verify: post-release forced-resume logging and first-task usage metric | File: N/A | Task: T1

FIX: 3 items (the three 🟡 above). VERIFY: 1 item (the post-release resume metric: run a released `catchup: force` PRD through a task-boundary resume, confirm delta/skipped is logged and the first task's `usage_at_start` is under 150K). KNOWN: (none).

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

D1: pass
D2: pass
D3: pass
D4: pass
D5: pass

Dispatch: single run resuming thread `01a0c2bd-974f-7fa2-b349-821cabb2556f`, no retry, thread id re-emitted for cycle 3.

## Carl

[CARL] ✅ No issues found

R1-R13 (R5 absent from the rubric): all pass. Backend copilot / gemini-3.8-flash. Read the context and diff, ran `test_custody_prose.py` + `test_resume.py`, the handoff-placement prose test, and `bash dev/bin/release-checks` (re-run with the nested-dispatch env vars unset after the first attempt hit the dispatch guard), read `resume.py`, `test_resume.py`, `test_custody_prose.py`, `phase-build.md`, and diffed against `1c51b2d`. No frontend surface; reviewed as a generalist.

## Follow-up Tasks Created

None: standalone run, no `state.json`, so no `task-add`. The findings above are reported for the operator's decision (packets below).

## Decision packets (unattended: written, not asked)

Agenda: 5 findings; 0 CRITICAL, 0 HIGH, 4 MEDIUM (all single-reviewer; one refuted by evidence), 1 LOW (post-release by definition). All four cycle-1 taken findings are resolved; no reviewer found a regression in the rework.

**1 of 2, 🟡 MEDIUM, `NonListTasksTests` sits after the `__main__` guard.** What: the class added in `test_resume.py:119-131` comes after `if __name__ == "__main__": unittest.main()`, so running the file directly loads 11 of 12 tests. Found by Bob (doubt lens). Evidence: confirmed, `PYTHONPATH=skills/run-autopilot python cli/test_resume.py` → `Ran 11 tests`; under pytest (the project's runner and `release-checks`) the class is collected and passes. If unchanged: no CI gap, only a direct-execution one; stable, does not compound. Options: (a) Recommended: move the class above the `__main__` block (S; reason against: one more commit on a PRD whose functional work is done). (b) Drop the `__main__` block, the file is only ever run through pytest (S; breaks the file's own docstring convention shared with sibling tests). (c) Accept or defer.

**2 of 2, 🟡 MEDIUM bundle (single reviewer, Bob; style).** (i) `_build_resume_target` docstring says "tasks exist -> /work" without the "after Phase 1's cache decision" qualifier the prose now carries: recommended: one-line docstring edit (S), or accept (the prose at `phase-build.md:60` is authoritative). (ii) `selection` variable name in `test_custody_prose.py:385`: recommended: accept (it names a `_section` slice like the file's other pins), or rename to `abort_handler` (S). The mech-check replay row is refuted by the manual replay (4/4 subtests fail at base) and needs no decision on this PRD; its cause is a `replay_tests_against_base.py` bug (parent-line parse under pytest 9 `SUBFAILED` reporting) worth a follow-up PRD in this pack. The ⚪ post-release metric is resolved by definition.

Verdict: 5 findings
Tests: 3599 passed, 0 failed, 32 skipped (suite run this cycle)
