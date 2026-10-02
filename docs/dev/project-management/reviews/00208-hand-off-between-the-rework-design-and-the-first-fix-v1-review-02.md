---
prd: dev/local/prds/wip/00208-hand-off-between-the-rework-design-and-the-first-fix-v1.md
review: 2
date: 2026-09-21
head_sha: d77431ba98fa141f7ee4d1f50c133291e30b38c6
codex_thread_id: 01a0c2cb-4af1-71d2-ac36-78449d830eb4
reviewers: alice,blake,bob,carl
agents:
  alice: available
  blake: available
  bob: available
  carl: available
---

# Review: 00208-hand-off-between-the-rework-design-and-the-first-fix-v1 (cycle 2, incremental)

Diff range: `99da1aeac0bd173daf2715e88b925b00a2be84e9..d77431ba98fa141f7ee4d1f50c133291e30b38c6` (incremental: `--since 99da1ae`, the cycle-1 `head_sha`; one rework commit `d77431b`, 2 files, +17/-6)

codex_rung_guard: not fired

Run mode: standalone (`/autopilot:review-work-completion` in worktree `claude-autopilot-r4`, no `dev/local/autopilot/state.json`; `_AUTOPILOT_LOOP=1` and `CLAUDE_UNATTENDED=1` were set, so the Watcher ran and no approval below is guessed). No task store: the rework is commit `d77431b` (cycle-1 findings 1-3 plus the LOW batch, all applied by the operator's rework session).
Consensus engine: legacy (PRD frontmatter carries no `consensus_engine`). Doubt reviewer: codex (no `doubt_reviewer`); Eve not active. Bob resumed his cycle-1 thread (`--resume-thread`, same id re-emitted).
Pack: failed (`engram pack` exit 1 twice: "not inside a registered repo; register it in ~/.config/gita/repos.csv" - the worktree is not gita-registered). Reviewers received `(no pack available this cycle)`.
Ledger: none (cycle 1 wrote no `-ledger.json`), so no `--ledger` flags and no auto-dismissal.
Mechanical checks: no tautological test shapes (13 checked); fail-first replay 2 touched tests, 2 failed against base `99da1ae`, 0 passed. No `[MECH]` lines to absorb.
Carl backend: copilot / gemini-3.8-flash.

## Review Summary

Reviewed: rework commit `d77431b` against the 4 cycle-1 findings (all verified resolved by Alice; Blake and Carl clean on the full PRD)
PRDs checked: 00208

### Agent Status
- Alice: ✅ Available
- Blake: ✅ Available
- Bob: ✅ Available (codex, thread resumed)
- Carl: ✅ Available (copilot / gemini-3.8-flash)

### Cycle-1 findings: resolution
| # | Cycle-1 finding | Status |
|---|-----------------|--------|
| 1 | 🟠 Resumed session may hand off again | resolved (`phase-review.md:22` "does not hand off again"; `:272` "never hands off again: the hand-off belongs to the task-creating session only") - confirmed by Alice, pins in `test_design_rework_prose.py:599-631` |
| 2 | 🟠 "Follow the Session handoff procedure" vs no `phase-done` | resolved (`:272` "steps 2 and 3 ... only: step 1 (`phase-done`) is skipped on purpose") - confirmed by Alice |
| 3 | 🟡 Tests pin strings, not the contract | resolved (order tuple carries the five steps, presence tuple pins unchanged phase/cycle and the task-creating-session clause) - confirmed by Alice |
| 4 | ⚪ PEP8 blank line | resolved (`test_design_rework_prose.py:640`) - confirmed by Alice |

## Consolidated Findings

`consolidate_findings.py`, 4 agent pairs, no ledger.

| Consensus | Severity | Issue | File | Task | Found By |
|-----------|----------|-------|------|------|----------|
| [1/4] | 🟠 | FIX: The new first-session guard requires that the session "created the tasks above," but Phase 6 also supports C-only rework batches whose existing tasks are merely requeued; in that valid loop-mode path no branch invokes `/autopilot:work`. Guard on rework being queued in the current session - or on not entering through the Phase 4 skip - and pin the C-only case | skills/run-autopilot/references/phase-review.md:272 | 1 | BOB |

### Minority (<=50%)
- [1/4] 🟠 C-only rework batch matches neither loop-mode branch | skills/run-autopilot/references/phase-review.md:272 | Found by: Bob

## Follow-up Tasks Created

None. Standalone run: no `state.json`, so no `task-add`. The finding is reported here and to the user; the decision packet below awaits the operator.

## Decision packets (unattended: nothing approved, nothing applied)

Agenda: 1 finding needs a call (1 HIGH as filed; the orchestrator reads it as MEDIUM, see Evidence). No LOW batch.

### 1 of 1 - 🟠 HIGH (filed) - A C-only rework cycle fits neither loop-mode sentence

**What.** The rework scoped the loop-mode hand-off to "the session that ran Phases 4-5 **and created the tasks above**" (`phase-review.md:272`), and the resume case to "a session that entered this section through that Phase 4 skip". Phase 6 builds the rework batch from two sources (`:263-270`): source 1 is the review-flagged `[C{cycle}]` tasks, existing tasks whose ids step 4 already appended to `rework_task_ids` with an escalated tier (no `task-add`); source 2 is the decision-gate `[D{cycle}]` tasks created here. A cycle whose batch is C-tasks only has a first session that ran Phases 4-5 but created nothing, so a literal reader finds no loop-mode sentence that applies and may fall through to neither hand-off nor `/autopilot:work`. Found by Bob (doubt lens, resumed thread).

**Evidence.** `phase-review.md:265`: "`state.rework_task_ids` already contains their IDs (appended in step 4 above)" - source 1 creates no task. The guard clause `and created the tasks above` is pinned verbatim by `test_design_rework_prose.py:602` (`"in the session that ran Phases 4-5 and created the tasks above: hand off here"`), so a reword touches that pin. Confidence: **suspected** - a prose reading, not reproduced; in practice "the session that ran Phases 4-5" is the discriminator and "created the tasks above" is a descriptor, and the interactive sentence is unaffected. The orchestrator rates the realistic impact MEDIUM: the failure needs a literal reader on a C-only cycle, the same class cycle 1 fixed, and the cost is one confused session, not a loop.

**If unchanged.** A loop-mode C-only cycle's first session might invoke `/autopilot:work` in-session (the pre-00208 behavior, a bloated session that may rotate) or stall asking which branch applies. Likelihood: low. Stable, not compounding.

**Options.**
- **(Recommended) Reword the discriminator to "queued"** - `in the session that ran Phases 4-5 and queued the rework above (source 1's re-flagged `[C{cycle}]` ids, source 2's `[D{cycle}]` tasks, or both)`, and update the `:602` pin plus one presence pin naming `[C{cycle}]`. Benefit: both sources named, the discriminator is the session role, not `task-add`. Drawback: still prose, and the sentence grows again. Effort S. Could break: the one existing pin (must be updated in the same commit).
- **Drop the clause** - keep `in the session that ran Phases 4-5: hand off here`, delete `and created the tasks above`; the skip-entered sentence already covers the other case. Benefit: shortest; the two sentences become exhaustive by construction. Drawback: loses the hint of why that session holds the bloat. Effort S. Could break: the `:602` pin (update it).
- **Pin the C-only case with a test only** - add a presence pin that the paragraph names both sources (fails today), forcing the wording fix through the test. Benefit: the contract is stated in the test first. Drawback: same edit as above plus a test, no real saving. Effort S.
- **Accept / defer** - treat "created" as loose for "queued"; C-only cycles without any D-task are rare under the decision gate. Record here, revisit if a loop session ever stalls at this paragraph.

## Alice

Cycle-1 findings 1-4 verified resolved in `d77431b` (see resolution table above); ran the PRD's two named suites (27 passed); file sizes under limits; no regression in the scoped diff.

[ALICE] ✅ No issues found

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

## Blake

[BLAKE] ✅ No issues found

Blind verification (PRD-only, no diff, no prior-cycle history): located both amended paragraphs (`phase-review.md:22`, `:272`), the schema row (`state-schema.md:205`), the CHANGELOG entry and the two pinning tests; ran the PRD's two named suites (27 passed). Did not run `release-checks` or `test_custody_prose_schema.py` by name (the orchestrator did: release-checks green, full suite below).

B1: pass
B2: pass
B3: pass
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
B15: pass
B16: pass
B17: pass
B18: pass
B19: pass

## Bob

Codex, exit 0, first run (no retry), resumed thread `01a0c2cb-4af1-71d2-ac36-78449d830eb4`. His cycle-1 findings are not re-raised; one new finding on the reworded guard.

[BOB] 🟠 FIX: The new first-session guard requires that the session "created the tasks above," but Phase 6 also supports C-only rework batches whose existing tasks are merely requeued; in that valid loop-mode path no branch invokes `/autopilot:work`. Guard on rework being queued in the current session - or on not entering through the Phase 4 skip - and pin the C-only case | File: skills/run-autopilot/references/phase-review.md:272 | Task: 1

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

Backend copilot / gemini-3.8-flash, exit 0. Read the context, diff and test file; ran the PRD suites and `release-checks` (also once with the parent dispatch env vars unset).

[CARL] ✅ No issues found

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

Verdict: 1 findings
Tests: 3630 passed, 0 failed, 1 skipped (suite run this cycle: `uv run --no-project --with pytest --with rich --with textual python -m pytest -q --ignore=dev/local` at d77431b; `bash dev/bin/release-checks` green)
