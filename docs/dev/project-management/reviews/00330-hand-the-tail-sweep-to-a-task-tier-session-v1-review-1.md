---
prd: docs/dev/project-management/prds/wip/00330-hand-the-tail-sweep-to-a-task-tier-session-v1.md
review: 1
date: 2026-10-17
head_sha: 0255e66eedc8adba7c258e1dca0fa76c042fe2b3
codex_thread_id: 01a149ba-337b-76d3-a2c4-ce2bec79b428
reviewers: alice,blake,bob,carl
agents:
  alice: available
  blake: available
  bob: available
  carl: available
dispatch_rows:
  bob: 30286551
  carl: 2ef46d3e
---

# Review: 00330-hand-the-tail-sweep-to-a-task-tier-session-v1

Diff range: `35d6479a87a4c92009b0a015d700c410a21d93d2..0255e66eedc8adba7c258e1dca0fa76c042fe2b3`

codex_rung_guard: not fired

pack: ok

## Review Summary

Reviewed: 2 completed tasks
PRDs checked: 00330-hand-the-tail-sweep-to-a-task-tier-session-v1.md

### Agent Status
- Alice: ✅ Available
- Blake: ✅ Available
- Bob: ✅ Available (after one retry (inlined); the first codex run refused for lack of input — its sandbox blocked every file read with `sandbox-exec: sandbox_apply: Operation not permitted`)
- Carl: ✅ Available (backend: gemini CLI)

## Consolidated Findings

| Ref | Consensus | Severity | Issue | File | Task | Found By |
|-----|-----------|----------|-------|------|------|----------|
| R1 | [1/4] | 🟡 | New tests leave the hand-off guards unpinned: removing the loop-only condition, unchanged-state requirement, or prohibition on repeated hand-offs still passes both tests. | skills/run-autopilot/scripts/test_review_resume_prose.py:78 | 1 | BOB |
| R2 | [1/4] | ⚪ | The new tests assert only substring presence (for example `END TURN`, `PRD 00208`) and never pin the loop-mode condition (`$_AUTOPILOT_LOOP`) or the `[D{cycle}]` task name. A later edit could drop the loop-mode gate and still pass. This is acceptable for prose pins, and the PRD specifies exactly these needles. | skills/run-autopilot/scripts/test_review_resume_prose.py:89 | 1 | ALICE |

### Minority (<=50%)
- [1/4] 🟡 New tests leave the hand-off guards unpinned | skills/run-autopilot/scripts/test_review_resume_prose.py:78 | Found by: BOB
- [1/4] ⚪ New tests assert only substring presence, not the loop-mode condition | skills/run-autopilot/scripts/test_review_resume_prose.py:89 | Found by: ALICE

No 🔴 CRITICAL and no 🟠 HIGH finding. The two rows are the same theme at two line anchors; the consolidator kept them apart because their `File:` anchors differ.

### Mechanical checks
- Tautological test shapes: 6 test functions checked in 1 file, no `[MECH]` line.
- Fail-first replay: 2 touched tests ran against the base at `35d6479a87a4`, 2 failed there, 0 passed — both new tests pin this change.

## Alice

[ALICE] ⚪ The new tests assert only substring presence (for example `END TURN`, `PRD 00208`) and never pin the loop-mode condition (`$_AUTOPILOT_LOOP`) or the `[D{cycle}]` task name. A later edit could drop the loop-mode gate and still pass. This is acceptable for prose pins, and the PRD specifies exactly these needles. | File: skills/run-autopilot/scripts/test_review_resume_prose.py:89 | Task: 1

- PRD match: step 3 and step 4 text matches the PRD's replacement text and the required exception sentence exactly.
- Preserved labels: `**3. Dispatch.**`, `**4. Finalize.**` and the `[D{cycle}] Tail sweep` name are unchanged.
- Phase 4 skip already resumes a Tail sweep task at step 3 and continues through step 4.
- The hand-off mirrors Phase 6's "Dispatch rework": both skip `phase-done` and leave `state.cycle` alone.
- CHANGELOG `[Unreleased]` Changed entry present.

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

- Step 3 carries the loop-mode hand-off in the order contract card, brief, `leave` row, banner, END TURN, with no `phase-done` and no state change.
- Step 4 keeps its three prohibitions and adds the exact exception sentence.
- Both new tests are present and the whole file's 6 tests pass.
- `rg -c 'tail sweep queued, handing off'` prints 1; the CHANGELOG entry is at CHANGELOG.md:24.
- No scope creep: prose, tests, CHANGELOG and loop-state files only.
- Not run by Blake: the three other acceptance test files, and the fail-first check at the base commit (both covered elsewhere in this cycle).

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

Ran after one retry (inlined). The first dispatch produced a lack-of-input refusal only (every rule `fail`, no review content); it is superseded by the retry below and is not consolidated.

[BOB] 🟡 New tests leave the hand-off guards unpinned: removing the loop-only condition, unchanged-state requirement, or prohibition on repeated hand-offs still passes both tests. | File: skills/run-autopilot/scripts/test_review_resume_prose.py:78 | Task: 1

FIX:
- Add assertions for the loop-only condition, unchanged phase/cycle fields, and resumed/interactive sessions executing work without another hand-off — skills/run-autopilot/scripts/test_review_resume_prose.py:78.

VERIFY:
- (none)

KNOWN:
- (none)

R1: fail
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

## Carl

[CARL] ✅ No issues found

Backend: native gemini CLI. Carl read the context, diff and pack, ran the four acceptance test files and both `rg -c` acceptance checks, and found nothing.

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

Verdict: 2 findings
Tests: 7143 passed, 0 failed, 3 skipped (suite run this cycle)
