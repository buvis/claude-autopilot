---
prd: dev/local/prds/wip/00208-hand-off-between-the-rework-design-and-the-first-fix-v1.md
review: 1
date: 2026-09-21
head_sha: 99da1aeac0bd173daf2715e88b925b00a2be84e9
codex_thread_id: 01a0c2cb-4af1-71d2-ac36-78449d830eb4
reviewers: alice,blake,bob,carl
agents:
  alice: available
  blake: available
  bob: available
  carl: available
---

# Review: 00208-hand-off-between-the-rework-design-and-the-first-fix-v1

Diff range: `b78bc1165d44e05dc2a9faa7cc8dfa114a9c14a7..99da1aeac0bd173daf2715e88b925b00a2be84e9`

codex_rung_guard: not fired

Run mode: standalone (`/autopilot:review-work-completion` in worktree `claude-autopilot-r4`, no `dev/local/autopilot/state.json`; `_AUTOPILOT_LOOP=1` and `CLAUDE_UNATTENDED=1` were set, so the Watcher ran and no approval below is guessed). No task store: tasks reconstructed from the two branch commits (T1 `33fbf4d`, T2 `99da1ae`).
Consensus engine: legacy (PRD frontmatter carries no `consensus_engine`). Doubt reviewer: codex (no `doubt_reviewer`); Eve not active.
Pack: failed (`engram pack` exit 1 twice: "not inside a registered repo; register it in ~/.config/gita/repos.csv" - the worktree is not gita-registered). Reviewers received `(no pack available this cycle)`.
Diff note: `gather-context.sh`'s default `git diff master` was inverted here (master has advanced with 00207/00209-00211 and carries rebased copies of these two commits as `5d7496e`/`7c4482d`), so the diff was regenerated with `--since <merge-base b78bc11>`; the 4-file, +53/-3 diff matches `git diff b78bc11..HEAD` (Carl confirmed byte-equal).
Mechanical checks: no tautological test shapes (13 checked); fail-first replay 2 touched tests, 2 failed against base, 0 passed. No `[MECH]` lines to absorb.
Carl backend: copilot / gemini-3.8-flash (41 AI credits, 4m33s).

## Review Summary

Reviewed: 2 completed tasks (T1, T2)
PRDs checked: 00208

### Agent Status
- Alice: ✅ Available
- Blake: ✅ Available
- Bob: ✅ Available (codex, thread captured)
- Carl: ✅ Available (copilot / gemini-3.8-flash)

## Consolidated Findings

`consolidate_findings.py`, 4 agent pairs, no ledger (cycle 1).

| Consensus | Severity | Issue | File | Task | Found By |
|-----------|----------|-------|------|------|----------|
| [1/4] | 🟠 | FIX: The resumed loop session still satisfies `$_AUTOPILOT_LOOP` and reaches the same hand-off branch again, causing endless hand-offs instead of invoking `/autopilot:work`; make the Phase 4 resume path dispatch work directly or otherwise distinguish it from the task-creation session | skills/run-autopilot/references/phase-review.md:272 | 1 | BOB |
| [1/4] | 🟠 | FIX: The new path says to follow the canonical Session handoff procedure while forbidding `phase-done`, but that procedure mandates `phase-done --outcome rework`, which increments the cycle and clears `rework_task_ids`; explicitly invoke only the contract-card, brief, leave-row, banner, and turn-end steps | skills/run-autopilot/references/phase-review.md:272 | 1 | BOB |
| [1/4] | 🟡 | FIX: The prose tests do not pin contract-card → brief → leave-row → banner ordering, unchanged phase/cycle state, or the resumed-session dispatch bypass, allowing both control-flow defects above to pass | skills/run-autopilot/cli/test_design_rework_prose.py:592 | 1 | BOB |
| [1/4] | ⚪ | Missing PEP8 double blank line before the new `test_phase_4_skip_is_the_rework_handoff_entry` function (every other top-level test def in the file has two blank lines before it; this one has one) | skills/run-autopilot/cli/test_design_rework_prose.py:620 | T2 | ALICE |
| [1/4] | ⚪ | VERIFY: Cannot statically verify: run `uv run --no-project --with pytest python -m pytest -q skills/run-autopilot/cli/test_design_rework_prose.py skills/run-autopilot/cli/test_custody_prose.py` and `bash dev/bin/release-checks` to confirm the required suites pass | N/A | general | BOB |

### Minority (<=50%)
- [1/4] 🟠 Resumed session may re-enter the hand-off branch | skills/run-autopilot/references/phase-review.md:272 | Found by: Bob
- [1/4] 🟠 "Follow the Session handoff procedure" vs "no phase-done" ambiguity | skills/run-autopilot/references/phase-review.md:272 | Found by: Bob
- [1/4] 🟡 Tests do not pin artifact ordering / unchanged state / resume bypass | skills/run-autopilot/cli/test_design_rework_prose.py:592 | Found by: Bob
- [1/4] ⚪ PEP8 blank line before `test_phase_4_skip_is_the_rework_handoff_entry` | skills/run-autopilot/cli/test_design_rework_prose.py:620 | Found by: Alice
- [1/4] ⚪ VERIFY suites pass | N/A | Found by: Bob - **already run this cycle by the orchestrator: 37 passed (the three named suites), `bash dev/bin/release-checks` green.** Not queued (standalone run has no queue file); resolved by the evidence in `Tests:` below.

## Follow-up Tasks Created

None. Standalone run: no `state.json`, so no `task-add`. Findings are reported here and to the user; the decision packets below await the operator.

## Decision packets (unattended: nothing approved, nothing applied)

Agenda: 3 findings need a call (2 HIGH, 1 MEDIUM), plus 1 LOW batch. The VERIFY item is closed by evidence above.

### 1 of 3 - 🟠 HIGH - The resumed session may hand off again instead of running the fixes

**What.** The new loop-mode paragraph at `phase-review.md:272` says "hand off here" whenever `$_AUTOPILOT_LOOP` is set, right after the rework ids are merged. The Phase 4 skip (`phase-review.md:22`) sends the next session to "resume at Phase 6 Dispatch rework". A resumed session that follows that pointer literally arrives at the same paragraph with `$_AUTOPILOT_LOOP` still set and every id already merged, and the paragraph tells it to hand off again. Found by Bob (doubt lens).

**Evidence.** The hand-off branch has no condition other than `$_AUTOPILOT_LOOP`; the "next session ... invokes `/autopilot:work` from there" sentence lives inside the branch as a description, not as an instruction the resumed session reads first. The skip paragraph does say "Before invoking `/autopilot:work` there", which is the intended reading. Confidence: **suspected** (prose ambiguity, not reproduced; a run-time loop would show as repeated `leave` rows with `--site review` and no `[D{cycle}]` task attempts).

**If unchanged.** Worst case: an infinite hand-off loop in loop mode, each iteration costing one review-session launch plus brief; the wrapper's session-count or wall-clock cap is the only stop. Likelihood: moderate. PRD 00211's history (a session ignored "end the turn" prose) says prose-only fences do fail. Compounds per rework cycle.

**Options.**
- **(Recommended) Add one guard sentence to the skip paragraph and the hand-off branch** - e.g. in the Phase 4 skip: "The resumed session does NOT hand off again: it invokes `/autopilot:work` directly." and in the branch: "(a session that arrived through Phase 4's skip skips this hand-off)". Pin both with a substring test. Benefit: closes the ambiguity where it is read. Drawback: still prose; the 00211 lesson says prose can be ignored. Effort S. Could break: nothing (prose + one test).
- **Make the resume path skip Phase 6 entirely** - the skip paragraph invokes `/autopilot:work` itself and never enters "Dispatch rework". Benefit: the resumed session never sees the hand-off branch. Drawback: the Tail-sweep and completed-id filtering sentences already live in the skip paragraph, so this moves more of Phase 6's logic there; touches the 00196 pins. Effort M (guess). Could break: `test_design_rework_prose.py` ordering pins for the skip paragraph.
- **Hook fence** - a PreToolUse hook denies a second `record_dispatch.py handoff --site review --edge leave` from a session whose `rework_task_ids` are all still `pending` and whose cycle review file exists. Benefit: the prose cannot loop. Drawback: new hook + tests for a prose-only PRD; overlaps the 00211 guard pair. Effort L. Could break: legitimate review-site hand-offs (cap rotation) if the predicate is wrong.
- **Accept / defer** - record here, revisit if a loop ever shows in `dispatch-metrics.jsonl`.

### 2 of 3 - 🟠 HIGH - "Follow the Session handoff procedure" while forbidding its step 1

**What.** The same paragraph says "follow the Session handoff procedure (core `SKILL.md`: brief, `leave` row ...) ... no `phase-done`, the cycle is not over". Core `SKILL.md`'s procedure is three steps and step 1 is `phase-done --outcome <outcome>`; at the review site that outcome is `rework`, which increments `state.cycle` and clears `rework_task_ids`. A session that follows the procedure as written runs step 1 first. Found by Bob.

**Evidence.** `skills/run-autopilot/SKILL.md` § Session handoff procedure, step 1: "Apply the transition with one `autopilot phase-done --outcome <outcome>` call". The paragraph does list the steps it wants (card, brief, leave row, banner) and does say "no `phase-done`". Confidence: **suspected** - the intent is stated, the contradiction is in the word "follow".

**If unchanged.** A session that runs `phase-done --outcome rework` at this point clears `rework_task_ids`, so the next session's skip does not fire, the cycle counter is one ahead, and the gate re-reviews instead of resuming - the exact failure the PRD's Risks section names. Likelihood: low-moderate. Stable, not compounding.

**Options.**
- **(Recommended) Reword to "run steps 2 and 3 of the Session handoff procedure only (brief, `leave` row, banner, end turn); step 1 (`phase-done`) is skipped"** and pin `steps 2 and 3` / `step 1` in the existing test. Benefit: removes the word that carries the contradiction. Drawback: couples the paragraph to the procedure's step numbering. Effort S. Could break: nothing beyond the one test.
- **Add a fourth site row to the handoff table** (`review-rework-queued`, outcome `none`, "commits nothing") so the procedure itself knows a no-transition hand-off. Benefit: the table stays the single source. Drawback: `cli/transitions.py` and `phase-done` would need a no-op outcome or the row must say "no call"; more surface for a prose PRD. Effort M. Could break: transitions tests.
- **Accept / defer** - the paragraph already says "no `phase-done`"; treat Bob's reading as over-literal.

### 3 of 3 - 🟡 MEDIUM - Tests pin strings, not the contract

**What.** `test_loop_mode_hands_off_after_task_add_before_work` (`test_design_rework_prose.py:592`) pins the loop-mode sentence, the banner, `END TURN`, the interactive sentence and two absences. It does not pin card → brief → leave-row → banner order, "state.phase ... left at review", "state.cycle unchanged", or that the resumed session dispatches without handing off. Found by Bob.

**Evidence.** The test's `_assert_in_order` tuple (diff lines 35-40) and `_assert_present` tuple (line 46). Confidence: **confirmed** (read the test).

**If unchanged.** A later prose edit can reorder the artifacts or drop the "no phase-done" clause without a red test. Stable.

**Options.**
- **(Recommended) Extend the order tuple** with `contract card`, `brief`, `leave`, `rework designed, handing off`, and add `state.cycle` unchanged` / `left at `review`` to `_assert_present`; plus whichever sentence 1-of-3 and 2-of-3 add. Benefit: the pins match the PRD's Outputs bullet. Drawback: brittle to wording. Effort S. Could break: nothing.
- **Fold into the fixes for 1 and 2** - only pin the new guard sentences. Benefit: smaller diff. Drawback: ordering stays unpinned. Effort S.
- **Accept / defer** - the PRD's acceptance criteria named exactly the pins that exist.

### LOW batch (one multiSelect when the operator returns)
- ⚪ Add the missing second blank line before `test_phase_4_skip_is_the_rework_handoff_entry` (`test_design_rework_prose.py:620`) - recommended fix: insert one blank line. Effort S.

## Alice

[ALICE] ⚪ Missing PEP8 double blank line before the new `test_phase_4_skip_is_the_rework_handoff_entry` function (every other top-level test def in the file has two blank lines before it; this one has one) | File: skills/run-autopilot/cli/test_design_rework_prose.py:620 | Task: T2
[ALICE] ✅ No other issues found

Verification notes: ran the two named suites (27 passed) and `test_custody_prose_schema.py` (10 passed); replay block confirms both new tests fail at base; file and function sizes under limits; the `cli/routing.rework_resume` citation at `phase-review.md:272` does not resolve in this pre-rebase worktree but exists on master (00207 landed there) - not raised as a finding.

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

Blind verification: located both amended paragraphs (`phase-review.md:22`, `:272`), the schema row (`state-schema.md:205`), the CHANGELOG entry and the two pinning tests; ran the PRD's suites (27 + 10 passed); `git diff --stat b78bc11 99da1ae` touches only the four expected files. B9-B14 pass vacuously (prose-only PRD). Did not run `release-checks` (the orchestrator did; green).

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

Codex, exit 0, first run (no retry). Thread `01a0c2cb-4af1-71d2-ac36-78449d830eb4`.

[BOB] 🟠 FIX: The resumed loop session still satisfies `$_AUTOPILOT_LOOP` and reaches the same hand-off branch again, causing endless hand-offs instead of invoking `/autopilot:work`; make the Phase 4 resume path dispatch work directly or otherwise distinguish it from the task-creation session | File: skills/run-autopilot/references/phase-review.md:272 | Task: 1
[BOB] 🟠 FIX: The new path says to follow the canonical Session handoff procedure while forbidding `phase-done`, but that procedure mandates `phase-done --outcome rework`, which increments the cycle and clears `rework_task_ids`; explicitly invoke only the contract-card, brief, leave-row, banner, and turn-end steps | File: skills/run-autopilot/references/phase-review.md:272 | Task: 1
[BOB] 🟡 FIX: The prose tests do not pin contract-card → brief → leave-row → banner ordering, unchanged phase/cycle state, or the resumed-session dispatch bypass, allowing both control-flow defects above to pass | File: skills/run-autopilot/cli/test_design_rework_prose.py:592 | Task: 1
[BOB] ⚪ VERIFY: Cannot statically verify: run `uv run --no-project --with pytest python -m pytest -q skills/run-autopilot/cli/test_design_rework_prose.py skills/run-autopilot/cli/test_custody_prose.py` and `bash dev/bin/release-checks` to confirm the required suites pass | File: N/A | Task: general

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

Backend copilot / gemini-3.8-flash, exit 0. Ran the PRD suites, `release-checks`, ruff and `check_style_limits.py`; confirmed the review diff equals `git diff b78bc11..HEAD`.

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

Verdict: 5 findings
Tests: 3630 passed, 0 failed, 1 skipped (suite run this cycle: `uv run --no-project --with pytest --with rich --with textual python -m pytest -q --ignore=dev/local` at 99da1ae; the PRD's three named suites 37 passed; `bash dev/bin/release-checks` green)
