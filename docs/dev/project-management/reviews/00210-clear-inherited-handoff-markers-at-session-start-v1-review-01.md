---
prd: dev/local/prds/wip/00210-clear-inherited-handoff-markers-at-session-start-v1.md
review: 1
date: 2026-09-21
head_sha: 8f093be99de1f04ff8b601e250258dab3180baaf
codex_thread_id: 01a0c2bd-274f-75d2-89a0-9b7dec22ee42
reviewers: alice,blake,bob,carl
agents:
  alice: available
  blake: available
  bob: available
  carl: available
---

# Review: 00210-clear-inherited-handoff-markers-at-session-start-v1

Diff range: `b78bc1165d44e05dc2a9faa7cc8dfa114a9c14a7..8f093be99de1f04ff8b601e250258dab3180baaf`
(full review, cycle 1; b78bc11 is the merge-base with master, passed to
`gather-context.sh --since` explicitly because master has moved ahead on
unrelated work and the script's default `git diff master` produced the wrong
diff - see Notes)

codex_rung_guard: not fired

pack: failed (`engram pack` exit 1: "not inside a registered repo; register it in ~/.config/gita/repos.csv" - this worktree is not gita-registered; not retried since the cause is configuration, `(no pack available this cycle)` substituted in every prompt)

## Review Summary

Reviewed: 2 completed tasks (T1 afc7d6a, T2 8f093be)
PRDs checked: 00210-clear-inherited-handoff-markers-at-session-start-v1
Run mode: standalone (no `dev/local/autopilot/state.json`; no task store, no
lens roster stamp, no checks queue, no `task-add`). Findings are reported
here, not written as tasks.
Consensus engine: legacy (PRD frontmatter carries no `consensus_engine`).
Doubt reviewer: codex (no `doubt_reviewer` in frontmatter; no state.json, so
the codex doubt-roster guard has no attempts record and does not fire; Eve
absent).

### Agent Status
- Alice: ✅ Available (Claude subagent, sonnet)
- Blake: ✅ Available (Claude subagent, sonnet; blind, PRD-only)
- Bob: ✅ Available (codex, thread 01a0c2bd-274f-75d2-89a0-9b7dec22ee42, exit 0, first run)
- Carl: ✅ Available (copilot backend, model gemini-3.8-flash, exit 0)

## Consolidated Findings

`consolidate_findings.py` ran (4 agent pairs); the mech-check replay row was
absorbed into Bob's row 4 (same file, same test).

| Consensus | Severity | Issue | File | Task | Found By |
|-----------|----------|-------|------|------|----------|
| [1/4] | 🟡 | FIX: Marker stat/unlink failures are silently swallowed, leaving stale markers with no diagnostic; retain exit 0 but report the failed removal | skills/run-autopilot/scripts/_walk_up.py:119 | 1 | BOB |
| [1/4] | 🟡 | FIX: Tests omit the required case where only `.cap-fired` exists, so they do not prove a missing first marker cannot prevent removal of the second | skills/run-autopilot/scripts/test_walk_up.py:103 | 1 | BOB |
| [1/4] | 🟡 | FIX: Stderr assertions do not require two distinct lines or the specified `written <timestamp>` shape, allowing malformed output to pass | skills/run-autopilot/scripts/test_walk_up.py:99 | 1 | BOB |
| [1/4] | 🟡 | FIX: `test_clear_cap_still_leaves_handoff_requested` passes against pre-change code; extend it to contrast `--clear-cap` with the new `--clear-markers` behavior | skills/run-autopilot/scripts/test_walk_up.py:113 | 1 | BOB, mech-check |
| [1/4] | 🟡 | FIX: The operational hot path embeds dated incident history despite the project convention that incidents belong in `design-rationale.md`; retain the invariant here and move the anecdote | skills/run-autopilot/references/phase-build.md:26 | 2 | BOB |
| [1/4] | ⚪ | Cannot statically verify: test suites pass; VERIFY with `uv run --no-project --with pytest python -m pytest -q skills/run-autopilot/scripts/test_walk_up.py skills/run-autopilot/cli/test_custody_prose.py` and `bash dev/bin/release-checks` | N/A | general | BOB |

### Orchestrator grounding (facts, not verdicts)

- Row 1: `except OSError: continue` at `_walk_up.py:119` is also the normal
  path for an absent marker (`stat()` raises `FileNotFoundError`), so a
  distinct diagnostic would need to separate "absent" from "present but
  unremovable". `_main_clear_cap` (line 87) swallows the same `OSError`; the
  PRD says "best-effort like `--clear-cap`". Suspected: a permission failure
  on a present marker is silent.
- Row 2: the PRD's Test Strategy lists "only `.cap-fired` present → removed"
  as an edge case; the acceptance list names four tests and none covers it.
  Confirmed gap against Test Strategy, not against the acceptance list.
- Row 3: `test_walk_up.py:99` asserts `count("cleared inherited") == 2` and
  both names present; the `written <ts>` shape is unasserted. Confirmed.
- Row 4: the replay block found the same test passes at base. Alice's note:
  it pins the deliberate back-compat requirement (`--clear-cap` keeps its
  single-marker behavior), so passing at base is by design. Confirmed fact,
  disputed as a defect.
- Row 5: `SKILL.md:335` describes `design-rationale.md` as "incident history
  behind the rules (non-normative)", so the convention Bob cites exists;
  `phase-build.md` already carries inline incident references elsewhere
  (e.g. line 191). Suspected style call.
- Row 6: resolved by this cycle's suite run (see `Tests:` below);
  `release-checks` includes both named files and was green.

### Minority (<=50%)
- [1/4] 🟡 Silent unlink failure, no diagnostic | skills/run-autopilot/scripts/_walk_up.py:119 | Found by: Bob
- [1/4] 🟡 No test for the only-`.cap-fired` edge case | skills/run-autopilot/scripts/test_walk_up.py:103 | Found by: Bob
- [1/4] 🟡 Stderr shape (`written <ts>`) unasserted | skills/run-autopilot/scripts/test_walk_up.py:99 | Found by: Bob
- [1/4] 🟡 Back-compat test passes at base | skills/run-autopilot/scripts/test_walk_up.py:113 | Found by: Bob, mech-check
- [1/4] 🟡 Incident anecdote in Phase 0 prose | skills/run-autopilot/references/phase-build.md:26 | Found by: Bob
- [1/4] ⚪ Cannot statically verify suites (resolved: run this cycle) | N/A | Found by: Bob

## Follow-up Tasks Created

None: standalone run, no autopilot state to write tasks into. The six
findings above are reported for the user's walkthrough.

## Alice

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

Notes: verified `INHERITED_MARKERS` (`_walk_up.py:50`) matches
`cli/handoff.py:25` `MARKERS` and `test_walk_up.py:123` pins it; ran the
three touched test files: 30 passed; the replay hit on
`test_clear_cap_still_leaves_handoff_requested` is a back-compat guard, not
a tautology; largest new function 18 lines.

## Blake

[BLAKE] ✅ No issues found

B1-B19: all pass (19 lines, verbatim in `dev/local/tmp/blake-output-00210c1.txt`).

Notes: found `--clear-markers` at `_walk_up.py:105`, the constant at line
50 with the `handoff.MARKERS` comment, all four required tests at
`test_walk_up.py:88-129`, the Phase 0 section at `phase-build.md:14-32`
before `### Handle park request`, no `--clear-cap` left in `phase-build.md`
(the `skills/work/SKILL.md:193-195` use is the preserved per-task reset),
CHANGELOG `### Fixed` entry present; ran the three test files: 30 passed.

## Bob

Backend: codex, exit 0, first run (no retry). Thread id captured.

[BOB] 🟡 FIX: Marker stat/unlink failures are silently swallowed, leaving stale markers with no diagnostic; retain exit 0 but report the failed removal | File: skills/run-autopilot/scripts/_walk_up.py:119 | Task: 1
[BOB] 🟡 FIX: Tests omit the required case where only `.cap-fired` exists, so they do not prove a missing first marker cannot prevent removal of the second | File: skills/run-autopilot/scripts/test_walk_up.py:103 | Task: 1
[BOB] 🟡 FIX: Stderr assertions do not require two distinct lines or the specified `written <timestamp>` shape, allowing malformed output to pass | File: skills/run-autopilot/scripts/test_walk_up.py:99 | Task: 1
[BOB] 🟡 FIX: `test_clear_cap_still_leaves_handoff_requested` passes against pre-change code; extend it to contrast `--clear-cap` with the new `--clear-markers` behavior | File: skills/run-autopilot/scripts/test_walk_up.py:113 | Task: 1
[BOB] 🟡 FIX: The operational hot path embeds dated incident history despite the project convention that incidents belong in `design-rationale.md`; retain the invariant here and move the anecdote | File: skills/run-autopilot/references/phase-build.md:26 | Task: 2
[BOB] ⚪ Cannot statically verify: test suites pass; VERIFY with `uv run --no-project --with pytest python -m pytest -q skills/run-autopilot/scripts/test_walk_up.py skills/run-autopilot/cli/test_custody_prose.py` and `bash dev/bin/release-checks` | File: N/A | Task: general

R1: fail
R2: fail
R3: pass
R4: pass
R6: pass
R7: pass
R8: pass
R9: pass
R10: fail
R11: pass
R12: pass
R13: pass
D1: pass
D2: pass
D3: pass
D4: pass
D5: pass

## Carl

Backend: copilot, model gemini-3.8-flash, exit 0. Ran the three touched
test files and `release-checks` himself (green).

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

## Mechanical checks

- Tautological shapes: checked 30 test functions in 3 files, none flagged.
- Fail-first replay against b78bc11: 6 touched tests ran, 5 failed at base,
  1 passed (`test_clear_cap_still_leaves_handoff_requested`, absorbed into
  Bob's row 4).

## Notes

- `gather-context.sh` diffs against the branch tip (`git diff master`), not
  the merge-base; with master ahead of this branch it produced an 18-file,
  653-deletion diff of unrelated work. Worked around by passing
  `--since <merge-base>`. Pre-existing script defect, outside this PRD;
  worth its own fix (use `git merge-base HEAD <base>`).
- Test line below is from `bash dev/bin/release-checks` run in this session
  at HEAD 8f093be (no `last-verification.json` existed): 1023 pytest passes
  across 16 suites plus 106 bash contract passes; 0 failed, 0 skipped.

Verdict: 6 findings
Tests: 1129 passed, 0 failed, 0 skipped (suite run this cycle: bash dev/bin/release-checks)
