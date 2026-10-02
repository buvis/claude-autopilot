---
prd: dev/local/prds/wip/00189-stall-to-split-on-plan-expansion-v1.md
review: 2
date: 2026-09-14
head_sha: 7f7713a846243855f72dcb7dd6be8c7b80b395a2
codex_thread_id: 01a0a00d-83e2-7801-8673-3b0c43f7dc55
reviewers: alice,blake,bob,carl
agents:
  alice: available
  blake: available
  bob: available
  carl: available
---

# Review: 00189-stall-to-split-on-plan-expansion-v1

Diff range: `a44f2e0347ca5fa0fbedfdb0f4bf664e10f62b7c..7f7713a846243855f72dcb7dd6be8c7b80b395a2`

codex_rung_guard: not fired

pack: failed (`engram pack` exited 1 — "not inside a registered repo; register it in /Users/bob/.config/gita/repos.csv"; the same deterministic error cycle 1 and the 00187/00188 cycles recorded, so no retry was spent). `{PACK_FILE}` and `{PACK_FINDINGS}` were substituted with the literal `(no pack available this cycle)` in every prompt that takes them. The review is degraded by the missing retrieval context, not invalid.

scope note: cycle 2, incremental review of the cycle-1 rework (`--since a44f2e03`, the cycle-1 `head_sha`): 4 commits, 7 files, +385/-25, tasks 6 and 7 (`[D1]` follow-ups at tier opus). Every implementation-aware prompt carried the cycle-1 consolidated table with each row's disposition, the incremental-review instruction, and the settled-decisions ledger (4 entries). Blake stayed blind: PRD and rubric only, no filesystem-notes block (`dev/local` is a real directory and the root has no dot prefix). No design doc exists (`design: skip`).

bob note: codex ran this cycle (exit 0, first dispatch, thread `01a0a00d-…` resumed via `--resume-thread` and re-emitted for the next cycle). No `Cannot statically verify` lines, no lack-of-input shape, all twelve `R` lines and five `D` lines present, so no retry was spent. He verified F1, F3-F6, F8 and the wording Low closed, F7 still deferred as settled, and raised F2 as only partially resolved plus one new Medium.

verification queue: none written this cycle. Bob emitted two FIX items and explicit `VERIFY: - (none)` / `KNOWN: - (none)`; Eve did not run (`doubt_reviewer: codex`, no codex-implemented task). No `00189-…-checks-1.json` exists, so there is nothing to carry forward.

## Review Summary

Reviewed: 7 completed tasks (tasks 6 and 7 in this cycle's diff; tasks 1-5 unchanged since cycle 1)
PRDs checked: 00189-stall-to-split-on-plan-expansion-v1

### Agent Status

- Alice: ✅ Available (Claude subagent, sonnet; traced every prior High/Medium through `policy.py:112-202` and `__main__.py:403-461`, hand-checked Devon's round-2 open weaknesses, re-ran the three touched suites (77 passed) and `test_doc_contract.py`; 3 ⚪, all twelve R rules pass)
- Blake: ✅ Available (Claude subagent, sonnet, blind/PRD-only; located every module, ran the suites and `release-checks`; 1 🟠, 1 🟡, six ✅ confirmations; B5 and B16 fail on his own two findings, the other seventeen B rules pass)
- Bob: ✅ Available (codex, exit 0, resumed thread, static analysis; doubt + de-slop lens; 2 issue lines: 1 🟠, 1 🟡; R1/R7/R9 fail on his F2, D1-D5 pass)
- Carl: ✅ Available (gemini-run backend=copilot model=gemini-3.8-flash, exit 0; ran the full suite (1861 passed) and `release-checks` twice; ✅ no issues, all twelve R rules pass)

## Consolidated Findings

10 findings: 7 rows from `consolidate_findings.py` (no paraphrase merges; the `--ledger-dismiss BLAKE` filter matched nothing, so no `### Auto-dismissed (ledger)` section) plus the fail-first replay's three `[MECH]` lines absorbed as their own rows (the tautological-shapes block was empty: 77 tests checked). No 🔴 Critical; **two 🟠 High** (one from Bob, orchestrator-confirmed by a computed fact; one from Blake, a requirements-ambiguity already decided at build time); 2 🟡 Medium from the reviewers plus 3 🟡 replay rows; 3 ⚪ Low.

Every reworked cycle-1 finding is closed: Alice, Bob and Carl each verified F1, F3, F4, F5, F6, the merged files-key Medium and the step 5.5 wording Low against the new code; Bob alone found a residue of F2.

| Consensus | Severity | Issue | File | Task | Found By |
|-----------|----------|-------|------|------|----------|
| [1/4] | 🟠 High | F2: A tree entry `//tmp/src/` still hangs parsing. `normpath` preserves two leading slashes, and `dirname("//") == "//"`; `_ancestors` never stops and now accumulates an unbounded list. | skills/run-autopilot/cli/policy.py:115 | 6 | Bob |
| [1/4] | 🟠 High | PRD Task 3 (check-plan) acceptance criteria specify `test_missing_prd_flag_is_a_usage_error (exit 2, stderr names --prd)`, but the implemented/tested behavior is exit 1 (the codebase's pre-existing `_ArgumentParser.error` override maps every usage error to 1, reserving 2 for state errors). The test in `test_check_plan_cli.py:340-348` explicitly asserts `returncode == 1` with a comment justifying the divergence from the PRD's literal text. This is a defensible engineering call (consistent with the codebase's own documented exit-code table) but it is a direct, undocumented-in-PRD deviation from an explicitly pinned acceptance value. (deferred as requirements ambiguity, reason below) | skills/run-autopilot/cli/test_check_plan_cli.py | 3 | Blake |
| [1/4] | 🟡 Medium | F9: `_bounded` reports a timeout but leaves the looping daemon thread running. A termination regression therefore continues consuming CPU and potentially memory throughout the remaining suite; daemon status only affects process shutdown. | skills/run-autopilot/cli/test_policy.py:117 | 6 | Bob |
| [1/4] | 🟡 Medium | PRD Task 3's literal acceptance command `uv run --no-project --with pytest python -m pytest -q skills/run-autopilot/cli/test_policy.py -k CheckPlanCli` collects zero tests (pytest exit 5) because `CheckPlanCliTests` was relocated to a new file `cli/test_check_plan_cli.py` (commit e1691bb, "under the file and function line caps"). The tests do exist and pass when run against the correct file/path, and CHANGELOG/docs are otherwise accurate, but anyone following the PRD's own acceptance instructions verbatim gets a false "no tests ran" result, and the PRD does not document this filename change anywhere (Requirements, Implementation, or CHANGELOG). (discarded, reason below) | skills/run-autopilot/cli/test_check_plan_cli.py | 3 | Blake |
| [1/4] | ⚪ Low | SKILL.md step 5.5's "Exit 2" bullet still reads only "state or PRD unreadable," but the fix in this diff makes an unwritable split note a third exit-2 cause (matches `__main__.py`'s updated docstring); the operator-facing prose doesn't mention it | skills/plan-tasks/SKILL.md | 7 | Alice |
| [1/4] | ⚪ Low | Carried Pat LOW, still open: `for item in files if isinstance(files, list) else []:` embeds the type guard in the loop iterable; hoisting to `files = files if isinstance(files, list) else []` reads cleaner | skills/run-autopilot/cli/policy.py:187 | 6 | Alice |
| [1/4] | ⚪ Low | Carried Pat LOW, still open: `test_unwritable_split_note_fails_loud` and `test_unwritable_split_note_file_fails_loud` are near-duplicates differing only in which call inside `_write_split_note` raises; kept separate by design (independent coverage of the two wrapped calls), no action needed (deferred by design, reason below) | skills/run-autopilot/cli/test_check_plan_cli.py | 7 | Alice |
| [1/4] | 🟡 Medium | Fail-first replay: 1 touched test(s) pass against the pre-change code: test_step_4_7_payloads_carry_files (discarded, reason below) | skills/plan-tasks/scripts/test_plan_size_gate_prose.py | general | mech-check |
| [1/4] | 🟡 Medium | Fail-first replay: 1 touched test(s) pass against the pre-change code: test_stall_writes_split_note_and_names_the_site (discarded, reason below) | skills/run-autopilot/cli/test_check_plan_cli.py | general | mech-check |
| [1/4] | 🟡 Medium | Fail-first replay: 3 touched test(s) pass against the pre-change code: test_junk_items_in_files_are_ignored_not_disqualifying, test_one_character_directory_is_still_a_leaf, test_root_slash_file_entry_does_not_grant_its_directory (discarded, reason below) | skills/run-autopilot/cli/test_policy.py | general | mech-check |

### Decision gate (Phase 5)

Not converged: one 🟠 High is unresolved (Bob's F2 residue), and `state.cycle` 2 >= `state.rework_cap` 2, so the cap check fires on the loop-mode branch: no CRITICAL, so no stall; every unresolved finding is deferred to batch end as a `cap-overflow` record in `state.deferred_decisions` (the only sink a cap-out writes), the `review_converged` metric row is appended with `outcome: "cap_deferred"`, and the PRD proceeds to the finalize hand-off as converged-with-deferrals. No third rework, no tail sweep (the cap-out paths have no work pass), no follow-up tasks created. The cap check precedes the Safety Checks table, so the "same issue reappearing after previous fix" row (F2) does not route to Protocol B this cycle; the deferral record names the residue and the one-line fix.

- **F2 residue (High, Bob, orchestrator-confirmed):** `posixpath.normpath("//tmp/src")` is `//tmp/src` and `posixpath.dirname("//")` is `//` (POSIX keeps exactly two leading slashes), so `_ancestors` loops forever on any tree entry starting with `//`, appending to `out` each pass. The cycle-1 fix bounded the walk at `/` only. Fix is one condition (`while path and posixpath.dirname(path) != path`, or add `"//"` to the stop set) plus a bounded test for `//tmp/src/` directory and file entries. **Cap-overflow deferral.**
- **F9 (Medium, Bob):** `_bounded` joins the daemon thread for 5 s and raises, but a spinning thread keeps running for the rest of the suite; the guard is correct only while the parse terminates. **Cap-overflow deferral** (would have been swept on convergence).
- **Exit-2 bullet (Low, Alice):** step 5.5's Exit 2 bullet names two causes; the rework added a third (unwritable split note) and documented it in the CLI docstring and CHANGELOG but not in the skill prose. **Cap-overflow deferral.**
- **Type-guard hoist (Low, Alice; Pat LOW carried from task 6):** style only. **Cap-overflow deferral.**
- **Exit 1 vs exit 2 (High, Blake) — deferred as a requirements ambiguity, settled:** the build phase already resolved this as an `assumed-ambiguity` (`state.autonomous_decisions[2]`): the PRD's normative Requirements text says only "argparse usage error without it"; the literal `exit 2` sits in the task acceptance line; the CLI's module docstring exit-code table reserves 2 for state errors and 1 for usage errors, and every other subcommand's usage error exits 1. Cycle-1 Blake judged the same reading consistent with the spec. Making one subcommand's usage error exit 2 would break the CLI's own table, so the deviation is recorded for the batch-end review to confirm or overrule (one assertion plus an `_ArgumentParser` special case, S) rather than reworked. Ledger `settled-deferral` so Blake's re-raise is absorbed next time.
- **Near-duplicate write-error tests (Low, Alice; Pat LOW carried from task 7) — deferred by design, settled:** task 7's brief kept them separate as independent coverage of the two wrapped calls (`mkdir` and `write_text`); Alice's own line says "no action needed". Recorded as `rejected-by-design` in `deferred_decisions`, the ledger and the batch deferred JSON, as cycle 1 did for F7.
- **Stale acceptance command (Medium, Blake) — discarded:** the PRD's Task 3 acceptance line names `test_policy.py -k CheckPlanCli`; `CheckPlanCliTests` moved to `test_check_plan_cli.py` in e1691bb to stay under the 800-line file cap (`rules/coding-style.md`), the move is recorded in the cycle-1 review's task table, and the tests exist and pass there (Blake and Alice both ran them). The PRD is the spec document, not an artifact this implementation edits, and a test-file relocation is not a user-visible change for the CHANGELOG. Ledger `discarded`.
- **Replay rows (3, Medium, mech-check) — discarded with measured reasons:** the replay base is the cycle-1 head `a44f2e03`, not the PRD's work start. `test_step_4_7_payloads_carry_files` gained an additive `"files": [` assertion that holds at a44f2e03 because the key was already present there; against the pre-PRD `SKILL.md` at 184db706 the key does not occur (`rg -c '"files": \['` on that revision's text finds 0 vs 2 now), so the pin fails where it must. `test_stall_writes_split_note_and_names_the_site` gained the complementary "exactly two stderr lines" pin (the negative half of F6: fully filed with a tree earns no third line), which held before the fix by construction. `test_root_slash_file_entry_does_not_grant_its_directory` was recorded at task time as a guard against over-correction (a glyph-less root file entry recorded no directory before the fix either); `test_one_character_directory_is_still_a_leaf` and `test_junk_items_in_files_are_ignored_not_disqualifying` are Tess-strengthen pins of behaviour Devon's round targeted (a one-character root, a junk item beside real paths) that the fix had to preserve. All five pin intended contract; none is a tautology.

## Follow-up Tasks Created

None. Cycle 2 reached the rework cap (`rework_cap: 2`) without converging, so no `[D2]` task is created and no rework is dispatched; the 4 unresolved findings above are `cap-overflow` records in `state.deferred_decisions` for the batch-end review, alongside the 2 settled deferrals. `state.rework_task_ids` stays `[]`.

## Alice

Consensus lens, Claude subagent (sonnet). She traced every prior High/Medium finding through the shipped code, hand-checked Devon's round-2 open weaknesses (E1-E5, the OSError and diagnostic-condition items), re-ran the three touched suites (77 passed) and `test_doc_contract.py` (1 passed). 3 ⚪ Low, all twelve R rules pass.

```
[ALICE] ⚪ SKILL.md step 5.5's "Exit 2" bullet still reads only "state or PRD unreadable," but the fix in this diff makes an unwritable split note a third exit-2 cause (matches `__main__.py`'s updated docstring); the operator-facing prose doesn't mention it | File: skills/plan-tasks/SKILL.md | Task: 7
[ALICE] ⚪ Carried Pat LOW, still open: `for item in files if isinstance(files, list) else []:` embeds the type guard in the loop iterable; hoisting to `files = files if isinstance(files, list) else []` reads cleaner | File: skills/run-autopilot/cli/policy.py:187 | Task: 6
[ALICE] ⚪ Carried Pat LOW, still open: `test_unwritable_split_note_fails_loud` and `test_unwritable_split_note_file_fails_loud` are near-duplicates differing only in which call inside `_write_split_note` raises; kept separate by design (independent coverage of the two wrapped calls), no action needed | File: skills/run-autopilot/cli/test_check_plan_cli.py | Task: 7

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
```

## Blake

Blind lens, Claude subagent (sonnet), PRD and rubric only. He located every module the PRD names, verified the policy (37 tests), the frontmatter opt-in and its per-PRD reset, the CLI contract (26 subprocess tests), the SKILL.md steps, the reference docs and the CHANGELOG, and ran `release-checks`. 1 🟠 (the exit-1 usage error against the acceptance line's `exit 2`), 1 🟡 (the acceptance command names the pre-split test file); B5 and B16 fail on those two, the other seventeen B rules pass. Six ✅ confirmation lines kept below as he wrote them.

```
[BLAKE] 🟠 PRD Task 3 (check-plan) acceptance criteria specify `test_missing_prd_flag_is_a_usage_error (exit 2, stderr names --prd)`, but the implemented/tested behavior is exit 1 (the codebase's pre-existing `_ArgumentParser.error` override maps every usage error to 1, reserving 2 for state errors). The test in `test_check_plan_cli.py:340-348` explicitly asserts `returncode == 1` with a comment justifying the divergence from the PRD's literal text. This is a defensible engineering call (consistent with the codebase's own documented exit-code table) but it is a direct, undocumented-in-PRD deviation from an explicitly pinned acceptance value. | File: skills/run-autopilot/cli/test_check_plan_cli.py | Task: 3
[BLAKE] 🟡 PRD Task 3's literal acceptance command `uv run --no-project --with pytest python -m pytest -q skills/run-autopilot/cli/test_policy.py -k CheckPlanCli` collects zero tests (pytest exit 5) because `CheckPlanCliTests` was relocated to a new file `cli/test_check_plan_cli.py` (commit e1691bb, "under the file and function line caps"). The tests do exist and pass when run against the correct file/path, and CHANGELOG/docs are otherwise accurate, but anyone following the PRD's own acceptance instructions verbatim gets a false "no tests ran" result, and the PRD does not document this filename change anywhere (Requirements, Implementation, or CHANGELOG). | File: skills/run-autopilot/cli/test_check_plan_cli.py | Task: 3
[BLAKE] ✅ Core plan_expansion policy (thresholds, Verdict shape, prd_task_lines, prd_modules tree parsing including grouping-only ancestors/leaf coverage/root-file handling, override, split-note rendering) matches the spec precisely and is pinned by 37 tests in test_policy.py, all passing | File: skills/run-autopilot/cli/policy.py | Task: general
[BLAKE] ✅ frontmatter.py's plan_expansion opt-in (exact "allow" match only, plan_expansion_override state field, byte-identical MALFORMED_WARNING) and its PER_PRD_RESET_FIELDS reset entry in records.py match spec and pass tests | File: skills/run-autopilot/cli/frontmatter.py | Task: general
[BLAKE] ✅ check-plan CLI (--prd required, --state/--ceiling unchanged, exit 0/3/2 contract, split-note write/error handling, stderr diagnostics for unfiled/skipped-drift on both pass and stall, override combined diagnostic) matches spec functionally and is exercised by 26 passing subprocess tests | File: skills/run-autopilot/cli/__main__.py | Task: general
[BLAKE] ✅ plan-tasks/SKILL.md step 4 persists `files`, step 4.7 payloads carry `files`, step 5.5 rewritten with the three numbered rules, site plan_expansion, override key and paired rework_cap:3 guidance; dev/bin/release-checks passes with the new "[checks] plan size gate" block (51 tests) | File: skills/plan-tasks/SKILL.md | Task: general
[BLAKE] ✅ references/recovery.md and references/state-schema.md document plan_expansion as the site with exactly one legacy oversized_plan mention; CHANGELOG.md carries the required plan-tasks (Added) and run-autopilot (Changed) entries under [Unreleased] | File: skills/run-autopilot/references/recovery.md | Task: general
[BLAKE] ✅ No scope creep detected: no new external dependencies, no schema.py edit (unknown key passes validate as documented), no extra CLI flags beyond --state/--prd/--ceiling, no automatic rework_cap mutation | File: N/A | Task: general

B1: pass
B2: pass
B3: pass
B4: pass
B5: fail
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
B16: fail
B17: pass
B18: pass
B19: pass
```

## Bob

Doubt + de-slop lens, codex (static-only sandbox), thread resumed from cycle 1, first dispatch, no retry. He verified F1, F3-F6, F8 and the wording Low closed and F7 still settled; 2 issue lines (1 🟠, 1 🟡), two FIX items, empty VERIFY and KNOWN buckets. R1, R7 and R9 fail on his F2 residue; D1-D5 pass. The orchestrator confirmed F2 by computing `posixpath.normpath("//tmp/src") == "//tmp/src"` and `posixpath.dirname("//") == "//"`.

```
Verified closed: F1, F3–F6, F8, and the wording Low. F7 remains deferred as settled. F2 is only partially resolved.

[BOB] 🟠 F2: A tree entry `//tmp/src/` still hangs parsing. `normpath` preserves two leading slashes, and `dirname("//") == "//"`; `_ancestors` never stops and now accumulates an unbounded list. | File: skills/run-autopilot/cli/policy.py:115 | Task: 6
[BOB] 🟡 F9: `_bounded` reports a timeout but leaves the looping daemon thread running. A termination regression therefore continues consuming CPU and potentially memory throughout the remaining suite; daemon status only affects process shutdown. | File: skills/run-autopilot/cli/test_policy.py:117 | Task: 6

FIX:
- F2 — skills/run-autopilot/cli/policy.py:115 — Stop ancestor traversal when the parent equals the current path; add bounded regression cases for double-leading-slash directory and file entries.
- F9 — skills/run-autopilot/cli/test_policy.py:117 — Run termination probes in an isolated process and terminate/join it on timeout, following the cleanup precedent in `test_state.py`.
VERIFY:
- (none)
KNOWN:
- (none)

R1: fail
R2: pass
R3: pass
R4: pass
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

## Carl

Consensus lens, gemini-run backend=copilot model=gemini-3.8-flash, exit 0, no retry. Read the context, the diff and the assumptions ledger, checked file line counts, ran the full suite (1861 passed) and `release-checks` twice (once with the host dispatch markers unset). No frontend surface, reviewed as a generalist. Verified every reworked finding closed; ✅ no issues, all twelve R rules pass.

```
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
```

## Mechanical checks

- Tautological shapes: none (77 test functions in 3 files checked).
- Fail-first replay at `a44f2e03` (the cycle-1 head): 17 touched tests ran, 12 failed against base, 5 passed. Three `[MECH]` lines absorbed as rows and discarded with the measured reasons in the Decision gate above.

Verdict: 10 findings

Tests: 1861 passed, 0 failed, 1 skipped (reused from last-verification.json at 7f7713a846243855f72dcb7dd6be8c7b80b395a2)
