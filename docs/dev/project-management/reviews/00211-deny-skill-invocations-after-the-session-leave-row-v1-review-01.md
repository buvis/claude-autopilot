---
prd: dev/local/prds/wip/00211-deny-skill-invocations-after-the-session-leave-row-v1.md
review: 1
date: 2026-09-21
head_sha: 4d49be8f6e9c7c76c517fd8c37e9e2030bbf5eec
codex_thread_id: 01a0c2d6-ed3e-7103-bf51-8c8c68b0b912
reviewers: alice,blake,bob,carl
agents:
  alice: available
  blake: available
  bob: available
  carl: available
---

# Review: 00211-deny-skill-invocations-after-the-session-leave-row-v1

Diff range: `b78bc11..4d49be8` (full review: merge-base with master to HEAD of `review/00211`; local `master` already carries these commits merged, so the branch base, not `master`, is the diff base)

codex_rung_guard: not fired

Mode: standalone (no `dev/local/autopilot/state.json`; worktree `claude-autopilot-r5`). No autopilot tasks; the task table was derived from the three branch commits (T1 4ff1142, T2 3ee544b, T3 4d49be8 rework from an earlier review pass whose file is not in this worktree). Unattended (`CLAUDE_UNATTENDED=1`): findings are written as decision packets below and NOT walked; no tasks created (standalone runs never write autopilot state).
consensus_engine: legacy (PRD frontmatter carries no `consensus_engine`)
doubt_reviewer: codex (PRD frontmatter carries no `doubt_reviewer`; Eve not active)
pack: failed (`engram pack` exit 1: worktree not registered in `~/.config/gita/repos.csv`; deterministic, no retry; `(no pack available this cycle)` substituted)
ledger: none (cycle 1)
Carl backend: copilot, model gemini-3.8-flash (gemini-run.sh stderr)
Consolidation: `consolidate_findings.py` (script), then two paraphrase pairs the script left split were merged by hand (marked "merged model-side" below): Bob+Carl on `tool_failed` (lines :44/:40 of the same file) and Bob+Carl on `test_both_registrations_point_at_pack_relative_files_that_exist`. The three `[MECH]` lines were absorbed into matching rows.

## Review Summary

Reviewed: 3 completed tasks (from commits)
PRDs checked: 00211

### Agent Status
- Alice: ✅ Available (Task subagent, sonnet)
- Blake: ✅ Available (Task subagent, sonnet, PRD-only)
- Bob: ✅ Available (codex, first run, no retry)
- Carl: ✅ Available (copilot/gemini-3.8-flash)

## Consolidated Findings

| # | Consensus | Severity | Issue | File | Found By | Orchestrator check |
|---|-----------|----------|-------|------|----------|--------------------|
| 1 | [2/4] | 🟠 | `tool_failed` ignores a non-zero exit status, so a failed leave command could write `.session-left`; PRD says "no `is_error: true` or non-zero exit" (merged model-side) | hooks/note_session_leave.py:40 | Bob, Carl | **Refuted.** Claude Code hooks reference: PostToolUse "runs immediately after a tool completes successfully"; a Bash command that exits non-zero fires `PostToolUseFailure` instead (payload `error: "Exit code N..."`). A failed leave command never reaches this hook, so the `is_error`/`interrupted` check is belt-and-braces, not a gap. |
| 2 | [2/4]+mech | 🟡 | `test_catchup_after_leave_is_denied_too` passes against the pre-change tree: a missing script makes python exit 2 too, and the test asserts only `returncode == 2` | hooks/test_guard_skill_after_leave.py:121 | Bob, Carl, mech-check | **Confirmed** (replay block: passes at b78bc11). Alice's claim that it fails at base is wrong; the mechanical fact wins. |
| 3 | [2/4]+mech | 🟡 | `test_both_registrations_point_at_pack_relative_files_that_exist` passes against the pre-change tree: it iterates whatever Bash/Skill commands exist and never asserts the two new ones are among them (merged model-side) | hooks/test_hook_registration.py:44 | Bob, Carl, mech-check | **Confirmed** (replay block). The other three tests in the file do pin the registration, so the gap is one vacuous test, not an unpinned change. |
| 4 | [2/4]+mech | 🟡 | `test_hooks_json_is_valid` has no assertion; it only proves parsing does not raise | skills/run-autopilot/scripts/test_review_coverage_hook_registration.py:59 | Bob, Carl, mech-check | **Confirmed shape, out of scope**: the function predates this PRD; the diff adds two rows to `_EXPECTED_REGISTRATIONS` and does not touch it. |
| 5 | [1/4] | 🟡 | A marker naming this session but with a missing or non-string `at` is denied as "an earlier call", against the PRD's "malformed marker → pass" | hooks/guard_skill_after_leave.py:54 | Bob | **Suspected, cannot occur**: `note_session_leave.py` is the only writer and always sets `at`. A same-session marker with no `at` still means the session left, so denying is the safer reading; the PRD wording is ambiguous here. |
| 6 | [1/4] | 🟡 | No test covers the PRD Test Strategy's "autopilot dir missing → pass" case for either hook | hooks/test_guard_skill_after_leave.py:157 | Bob | **Confirmed**: no test runs either hook against a `tmp_path` without `dev/local/autopilot`. |
| 7 | [1/4] | 🟡 | `test_each_guard_hook_has_a_short_timeout` asserts `timeout <= 5` with default 0, so an absent or zero timeout passes; the PRD pins `timeout 5` | hooks/test_hook_registration.py:65 | Bob | **Confirmed** by reading the assert. |
| 8 | [1/4] | ⚪ | VERIFY: cannot statically verify the acceptance suite and release gate pass | N/A | Bob | **Closed this cycle**: both commands ran green (see `Tests:` line). |

## Findings walkthrough (decision packets; unattended, awaiting the user)

Agenda: 8 findings; 0 CRITICAL, 1 HIGH (refuted), 6 MEDIUM, 1 LOW (closed).

### 1 of 8 - 🟠 HIGH (refuted) - `tool_failed` and non-zero exits
What: `hooks/note_session_leave.py` decides whether the leave-row command failed by looking at `is_error` and `interrupted` in the hook payload. Bob and Carl read the PRD's "or non-zero exit" and flagged that no exit code is checked. Found by the consensus lens (2 of 4 reviewers).
Evidence: confirmed against the Claude Code hooks reference: PostToolUse fires only after a tool completes successfully; a non-zero Bash exit routes to `PostToolUseFailure`, whose payload carries `error: "Exit code N"`. The Bash `tool_response` has no exit-code field to read.
If unchanged: nothing degrades; a failed leave command never reaches this hook. Stable.
Options:
- **(Recommended) Dismiss and ledger it** with the event-contract reason. Benefit: no code churn. Drawback: the PRD sentence still reads as if the hook checks an exit code; a future reader may re-raise. Effort S. Breaks nothing.
- Add a one-line docstring note in `note_session_leave.py` naming `PostToolUseFailure` as the reason no exit code is read. Benefit: closes the re-raise loop at the source. Drawback: a comment for a case that cannot happen. Effort S. Breaks nothing.
- Register the same script under `PostToolUseFailure` too and treat `error` starting with `Exit code` as failed. Benefit: literal PRD wording. Drawback: dead registration, one more hook per failed Bash call. Effort M. Could add noise on every failed command.
- Accept or defer.

### 2 of 8 - 🟡 MEDIUM - catchup deny test cannot tell "denied" from "script missing"
What: `test_catchup_after_leave_is_denied_too` asserts only exit 2. Python exits 2 when the script file does not exist, so the test also passes on a tree without the guard. Found by the fail-first replay (mechanical) and by Bob and Carl.
Evidence: confirmed; replay at `b78bc11` reports it passing (15 of 17 touched tests fail there, this is one of the 2 that pass).
If unchanged: the guard for `git-ferry:catchup` is unpinned; a regression (say, dropping the exact-match tuple) still leaves this test green. Stable, low blast radius.
Options:
- **(Recommended) Assert the reason**: add `assert "git-ferry:catchup" in result.stderr` (mirrors the run-autopilot test above it). Benefit: two-line fix, test now fails at base. Drawback: none of note. Effort S. Breaks nothing.
- Parametrize the deny test over both skills and delete this one. Benefit: one test, both skills. Drawback: loses the PRD-named test function name. Effort S.
- Accept (the end-to-end test also covers deny, but only for `autopilot:*`).

### 3 of 8 - 🟡 MEDIUM - registration existence test is vacuous
What: `test_both_registrations_point_at_pack_relative_files_that_exist` loops over every Bash PostToolUse and Skill PreToolUse command and checks each file exists. On a tree without the new entries it loops over the old ones and passes. Found by the replay, Bob and Carl.
Evidence: confirmed by the replay at `b78bc11`.
If unchanged: harmless; the three sibling tests in the same file pin the two registrations. Stable.
Options:
- **(Recommended) Restrict it to the two new hooks**: collect the two commands by name and assert both were found and both files exist. Benefit: the test then fails at base. Drawback: slightly longer test. Effort S. Breaks nothing.
- Delete it; the pack-wide `test_registered_commands_point_at_files_that_exist` already covers file existence. Benefit: less duplication. Drawback: the PRD-named file loses a check. Effort S.
- Accept.

### 4 of 8 - 🟡 MEDIUM - pre-existing assertion-less `test_hooks_json_is_valid`
What: the pack-wide registration test has a test that only parses `hooks.json`. Not written by this PRD; the diff adds two dict rows to that file.
Evidence: confirmed shape; `git diff b78bc11..HEAD` on that file is the two rows only.
If unchanged: unchanged from before this PRD. Stable.
Options:
- **(Recommended) Defer** to a hygiene pass or the next PRD touching that file (out of scope here per the surgical-changes rule). Benefit: keeps this diff scoped. Drawback: the smell stays one more release. Effort S.
- Fix in this rework: `assert isinstance(data["hooks"], dict)`. Benefit: one line. Drawback: touches code the PRD did not ask for. Effort S.
- Accept.

### 5 of 8 - 🟡 MEDIUM - same-session marker without `at` denies
What: `left_at` returns the string "an earlier call" when the marker names this session but has no `at`, so the guard denies. Bob reads the PRD's "malformed marker → pass" as covering this.
Evidence: suspected; the only writer always sets `at`, so this state is unreachable in practice.
If unchanged: nothing; and if it ever happened, denying a post-leave skill call is the intended behavior anyway. Stable.
Options:
- **(Recommended) Accept**: the marker names the session, so it left; missing `at` is cosmetic. Benefit: no change. Drawback: literal PRD wording not matched. Effort none.
- Return `None` when `at` is missing (fail open). Benefit: literal PRD. Drawback: a corrupted marker lets the exact failure the PRD exists to stop through. Effort S.
- Tighten the PRD sentence instead ("malformed = not a JSON object naming a session"). Benefit: spec matches the safer code. Drawback: a doc edit in a done PRD. Effort S.

### 6 of 8 - 🟡 MEDIUM - no test for "autopilot dir missing → pass"
What: the PRD Test Strategy lists "autopilot dir missing → pass" as an error case; neither hook has a test running it against a `tmp_path` with no `dev/local/autopilot`.
Evidence: confirmed by reading `hooks/test_guard_skill_after_leave.py`.
If unchanged: the `find_autopilot_dir is None` branch of both hooks is unpinned. Stable.
Options:
- **(Recommended) Add two tests** (`test_leave_row_without_autopilot_dir_writes_nothing`, `test_guard_without_autopilot_dir_passes`) using a bare `tmp_path`. Benefit: closes the PRD's own list. Drawback: none. Effort S. Breaks nothing.
- One combined test. Benefit: shorter. Drawback: two behaviors in one name. Effort S.
- Accept.

### 7 of 8 - 🟡 MEDIUM - timeout test accepts absent timeout
What: `assert hooks[0].get("timeout", 0) <= 5` passes when `timeout` is missing (default 0). The PRD says timeout 5.
Evidence: confirmed by reading the assert.
If unchanged: a dropped `timeout` key in `hooks.json` would go unnoticed (the harness default is 60s). Stable.
Options:
- **(Recommended) `assert hooks[0].get("timeout") == 5`**. Benefit: pins the PRD value. Drawback: brittle if someone later lowers it to 3 on purpose. Effort S.
- `assert 0 < hooks[0]["timeout"] <= 5`. Benefit: allows lowering. Drawback: not the literal PRD value. Effort S.
- Accept.

### 8 of 8 - ⚪ LOW - closed
Bob's VERIFY item: both named commands ran green this cycle (`Tests:` line). No decision needed.

## Alice

[ALICE] ✅ No issues found

Ran `hooks/test_guard_skill_after_leave.py hooks/test_hook_registration.py` (16 passed), `test_loop_prose.py` + `test_review_coverage_hook_registration.py` (13 passed), and `bash dev/bin/release-checks` (green). Checked `_walk_up`/`_common` signatures, hooks.json shape, mechanical line counts, no TODO/debug markers, SKILL.md/design-rationale/CHANGELOG consistency. Orchestrator note: her statement that `test_catchup_after_leave_is_denied_too` fails at base contradicts the replay block, which measured it passing; the mechanical fact stands (finding 2).

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

Located and verified both hooks, the registration, both test files, the SKILL.md handoff sentence and Retention entry, the design-rationale section, the CHANGELOG entry, `test_loop_prose.py::test_handoff_names_the_skill_guard`, and the release-checks block. Ran the acceptance files plus `test_loop_prose.py`: 24 passed.

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

Codex, first run, no retry. Thread `01a0c2d6-ed3e-7103-bf51-8c8c68b0b912`.

[BOB] 🟠 FIX: `tool_failed` ignores non-zero exit status, so a failed leave command can incorrectly write `.session-left`; handle the response exit-code field and add a regression test | File: hooks/note_session_leave.py:44 | Task: 1
[BOB] 🟡 FIX: A structurally malformed marker with the current session but missing/non-string `at` is denied as "an earlier call," contrary to the fail-open requirement; return `None` instead | File: hooks/guard_skill_after_leave.py:54 | Task: 1
[BOB] 🟡 FIX: `test_catchup_after_leave_is_denied_too` passes against the pre-change tree because Python's missing-script error also exits 2; assert the guard-specific stderr reason and skill name | File: hooks/test_guard_skill_after_leave.py:121 | Task: 1
[BOB] 🟡 FIX: No test covers the PRD's missing-autopilot-directory pass-through case; add subprocess cases showing both hooks exit 0 without a directory | File: hooks/test_guard_skill_after_leave.py:157 | Task: 1
[BOB] 🟡 FIX: This registration test passes against the pre-change tree and duplicates the pack-wide file-existence test; remove it or restrict it to the two newly registered hooks | File: hooks/test_hook_registration.py:44 | Task: general
[BOB] 🟡 FIX: The timeout assertion accepts an absent or zero timeout, so it does not pin the required value of 5; replace it with equality to 5 | File: hooks/test_hook_registration.py:65 | Task: 3
[BOB] 🟡 FIX: `test_hooks_json_is_valid` has no assertion and only proves parsing does not raise; assert the parsed manifest's expected structure | File: skills/run-autopilot/scripts/test_review_coverage_hook_registration.py:59 | Task: general
[BOB] ⚪ VERIFY: Cannot statically verify that the acceptance suite and release gate pass; run `uv run --no-project --with pytest python -m pytest -q hooks/test_guard_skill_after_leave.py hooks/test_hook_registration.py` and `bash dev/bin/release-checks` | File: N/A | Task: general

R1: fail
R2: fail
R3: pass
R4: pass
R6: pass
R7: pass
R8: pass
R9: fail
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

copilot backend, model gemini-3.8-flash. Ran the acceptance files, `test_loop_prose.py` and `bash dev/bin/release-checks` (green after clearing the nested-dispatch env vars).

[CARL] 🟡 test_catchup_after_leave_is_denied_too passes against pre-change code because python exits 2 on missing file and the test only asserts returncode == 2 without checking stderr | File: hooks/test_guard_skill_after_leave.py:121 | Task: T1
[CARL] 🟡 test_both_registrations_point_at_pack_relative_files_that_exist passes against pre-change code because it iterates over command lists without asserting they are non-empty | File: hooks/test_hook_registration.py:44 | Task: T3
[CARL] 🟡 test_hooks_json_is_valid has no assertion: it only proves the code does not raise | File: skills/run-autopilot/scripts/test_review_coverage_hook_registration.py:59 | Task: general
[CARL] 🟡 tool_failed ignores non-zero exit codes in tool_response, checking only is_error and interrupted despite PRD requiring check for non-zero exit | File: hooks/note_session_leave.py:40 | Task: T1

R1: pass
R2: fail
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

## Mechanical checks (step 3 blocks, absorbed above)

- Tautological shapes: 1 line (`test_hooks_json_is_valid`, pre-existing) → finding 4.
- Fail-first replay at `b78bc11`: 17 touched tests ran, 15 failed at base, 2 passed (`test_catchup_after_leave_is_denied_too` → finding 2; `test_both_registrations_point_at_pack_relative_files_that_exist` → finding 3).
- Function line counts: max 30 (`test_every_handoff_site_writes_the_brief`, pre-existing); new hooks max 25. No R12/R13 breach.

## Follow-up Tasks Created

None: standalone run (no `state.json`), so no `task-add`. Findings 2, 3, 6, 7 are the recommended rework set (all S); 1 refuted, 5 accept, 4 defer, 8 closed.

Verdict: 8 findings
Tests: 1039 passed, 0 failed, 0 skipped (suite run this cycle: `bash dev/bin/release-checks` at 4d49be8, all 16 pytest blocks green plus 106 bash contract checks passed; the PRD's acceptance command `pytest -q hooks/test_guard_skill_after_leave.py hooks/test_hook_registration.py` plus `test_loop_prose.py` and `test_review_coverage_hook_registration.py`: 29 passed)
