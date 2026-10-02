---
prd: dev/local/prds/wip/00189-stall-to-split-on-plan-expansion-v1.md
review: 1
date: 2026-09-14
head_sha: a44f2e0347ca5fa0fbedfdb0f4bf664e10f62b7c
codex_thread_id: 01a0a00d-83e2-7801-8673-3b0c43f7dc55
reviewers: alice,blake,bob,carl
agents:
  alice: available
  blake: available
  bob: available
  carl: available
---

# Review: 00189-stall-to-split-on-plan-expansion-v1

Diff range: `184db706c61f0c6f649de98bd365cc6b63a5cce7..a44f2e0347ca5fa0fbedfdb0f4bf664e10f62b7c`

codex_rung_guard: not fired

pack: failed (`engram pack` exited 1 — "not inside a registered repo; register it in /Users/bob/.config/gita/repos.csv"; the same deterministic error the 00187 and 00188 cycles recorded, so no retry was spent). `{PACK_FILE}` and `{PACK_FINDINGS}` were substituted with the literal `(no pack available this cycle)` in every prompt that takes them. The review is degraded by the missing retrieval context, not invalid.

scope note: cycle 1, full review of the PRD's whole work range (13 commits, 14 files, +2146/-107). `gather-context.sh` was run with `--since 184db706…` (`state.work_start_sha`) because its default base is `master` and the batch works on `master`, so the bare form yields an empty diff (measured again this cycle: 0 lines); the context file's scope label was corrected by hand to say "full review". Blake stayed blind: PRD and rubric only, no filesystem-notes block (`dev/local` is a real directory and the root has no dot prefix). No design doc exists (`design: skip`).

bob note: codex ran this cycle (exit 0, first dispatch, thread `01a0a00d-…` captured for the next cycle's `--resume-thread`). No `Cannot statically verify` lines, no lack-of-input shape, all twelve `R` lines and five `D` lines present, so no retry was spent. Bob's `File:` values carry `:line` suffixes and are kept as he wrote them.

verification queue: none written this cycle. Bob emitted eight FIX items and explicit `VERIFY: - (none)` / `KNOWN: - (none)`, so there is nothing to queue; Eve did not run (`doubt_reviewer: codex`, no codex-implemented task).

## Review Summary

Reviewed: 5 completed tasks
PRDs checked: 00189-stall-to-split-on-plan-expansion-v1

### Agent Status

- Alice: ✅ Available (Claude subagent, sonnet; read the diff, the assumptions ledger and the code paths Devon left open; 1 🟡, 2 ⚪, all twelve R rules pass)
- Blake: ✅ Available (Claude subagent, sonnet, blind/PRD-only; ran the policy/CLI/frontmatter suites (66 passed), both prose suites (36), the doc-contract test, the full cli suite (1054 passed) and `release-checks`, all green; ✅ no issues, all nineteen B rules pass)
- Bob: ✅ Available (codex, exit 0, static analysis; doubt + de-slop lens; 8 issue lines: 2 🟠, 5 🟡, 1 ⚪; R1/R4/R7/R9/R10 fail, D1-D5 pass)
- Carl: ✅ Available (gemini-run backend=copilot model=gemini-3.8-flash, exit 0; ran the three touched suites and `release-checks` twice, once with the host dispatch markers unset; 1 🟡, 2 ⚪, all twelve R rules pass)

## Consolidated Findings

12 findings: 12 rows from `consolidate_findings.py` with three cross-reviewer paraphrases of one finding merged by the orchestrator (Alice's 🟡, Carl's 🟡 and Bob's ⚪ F8 on the misnamed `test_step_4_7_payloads_carry_files` — the script kept them apart because Bob's `File:` carries a `:559` suffix and the two Claude-side wordings fell below its merge threshold) into one `[3/4]` row, plus the fail-first replay's three `[MECH]` lines absorbed: the first joins that merged row as `mech-check`, the other two stand as their own rows and are discarded with a measured reason (Decision gate below). The tautological-shapes block was empty (99 tests checked). No 🔴 Critical; **two 🟠 High** (both Bob's, both confirmed by the orchestrator against `policy.py`); 8 🟡 Medium; 2 ⚪ Low.

Alice, Blake and Carl passed the implementation on every rubric rule; Blake found nothing. The doubt lens carried the weight again: Bob's eight issue lines are where both Highs and five of the eight Mediums come from.

| Consensus | Severity | Issue | File | Task | Found By |
|-----------|----------|-------|------|------|----------|
| [1/4] | 🟠 High | F1: Slash-separated file entries lose implicit directory ancestry. A tree containing `src/` and `└── auth/login.py` leaves `src` recursively covered, allowing unrelated `src/payments` and `src/orders` tasks through the drift gate. | skills/run-autopilot/cli/policy.py:126 | 2 | Bob |
| [1/4] | 🟠 High | F2: An absolute tree directory such as `/tmp/src/` hangs the ancestor loop: eventually `dirname("/") == "/"`, so parsing never terminates, even with the override set. | skills/run-autopilot/cli/policy.py:131 | 2 | Bob |
| [3/4] | 🟡 Medium | test_step_4_7_payloads_carry_files no longer asserts a `"files"` key exists in the payloads (that check moved to the sibling test_step_4_7_payload_files_are_real_repo_relative_paths during the function-cap split); the name now promises something the body doesn't check / Carl: misnamed after the function-cap split; add 'assert all("\"files\": [" in p for p in payloads)' / Bob F8: checks payload count and routing shape but never checks the `files` key; its passing against base is otherwise legitimate | skills/plan-tasks/scripts/test_plan_size_gate_prose.py | 4 | Alice, Carl, Bob, mech-check |
| [1/4] | 🟡 Medium | F3: Coverage compares unnormalized paths. `./src/auth/a.py` is falsely unlisted, while `src/auth/../payments/a.py` is falsely covered by the `src/auth` leaf. | skills/run-autopilot/cli/policy.py:152 | 2 | Bob |
| [1/4] | 🟡 Medium | F4: Task metadata lacks boundary validation. State loading permits non-dictionary task entries, which crash at `task.get`; a task with `files: [null]` instead disappears from the note with `unfiled=0`. | skills/run-autopilot/cli/policy.py:165 | 2 | Bob |
| [1/4] | 🟡 Medium | F5: Split-note directory creation and writing leave `OSError` uncaught. An existing regular file named `split-notes` produces a traceback and exit 1, outside step 5.5's documented error handling. | skills/run-autopilot/cli/__main__.py:435 | 3 | Bob |
| [1/4] | 🟡 Medium | F6: Stall verdicts return before emitting the required unfiled/skipped-drift diagnostic. For example, 16 unfiled tasks against a PRD without a tree print neither diagnostic on stderr. | skills/run-autopilot/cli/__main__.py:439 | 3 | Bob |
| [1/4] | 🟡 Medium | F7: `_mask_non_prose` duplicates the existing implementation in `test_plan_tasks_prose.py:55`, creating two copies of the same masking behavior to maintain. (deferred by design, reason below) | skills/plan-tasks/scripts/test_plan_size_gate_prose.py:65 | 4 | Bob |
| [2/4] | ⚪ Low | SKILL.md step 5.5 still reads "the gate is advice here, not a gate," a self-contradictory carry-over from the pre-PRD wording (Pat LOW, unresolved) | skills/plan-tasks/SKILL.md | 4 | Alice, Carl |
| [2/4] | ⚪ Low | _run_check_plan re-parses the PRD tree via policy.prd_modules(text) to derive drift_word instead of reading it off Verdict, duplicating work plan_expansion already did (Pat LOW, unresolved; deferred by design, reason below) | skills/run-autopilot/cli/__main__.py | 3 | Alice, Carl |
| [1/4] | 🟡 Medium | Fail-first replay: 1 touched test(s) pass against the pre-change code: test_production_parser_exposes_no_count_flag (discarded, reason below) | skills/run-autopilot/cli/test_check_plan_cli.py | general | mech-check |
| [1/4] | 🟡 Medium | Fail-first replay: 2 touched test(s) pass against the pre-change code: test_optional_markers_stay_absent_rather_than_false, test_plan_expansion_only_counts_inside_a_well_formed_block (discarded, reason below) | skills/run-autopilot/cli/test_frontmatter.py | general | mech-check |

### Decision gate (Phase 5)

Cycle 1 < rework cap 2, two 🟠 High unresolved → not converged → rework. Every decision is in `state.autonomous_decisions` (10 new entries) or `state.deferred_decisions` (2 new entries); the two by-design deferrals and the two discards are in `00189-stall-to-split-on-plan-expansion-v1-ledger.json`, and the F1 assumption plus both deferrals are mirrored into the batch deferred JSON. No settled deferrals from a prior cycle (cycle 1), no cap-overflow, no scope alarm (2 follow-up tasks), no recurring issue.

- **Auto-fix, reworked (8 findings → 2 `[D1]` tasks):**
  - F1 (High) is a requirements ambiguity resolved by the simplest safe assumption, recorded as `assumed-ambiguity`: the PRD says both "rebuild directory ancestry including parents implicit in slash-separated paths" and "a listed file is allowed individually without allowing its siblings"; the plan read the first as directory entries only (`_tree_entries` feeds only names ending in `/` into the ancestry loop, orchestrator-confirmed at `policy.py:110-134`), so `src/` + `└── auth/login.py` leaves `src` a leaf. Assumed reading, fail-closed: a file entry's implicit ancestors are grouping-only directories — they demote the explicit directory above them from leaf to grouping parent and grant nothing themselves. No existing fixture changes verdict; a false stall costs one human look, a false pass reproduces the $345 failure the gate exists for. Bounded additive change, so auto-fix rather than stall.
  - F2 (High) confirmed by reading: `while path and path != "."` with `posixpath.dirname("/") == "/"` never terminates on a tree line starting with `/`; it hangs `check-plan` even under the override because the note is built regardless. One-token guard plus a terminating test.
  - F3, F4, F5, F6 (Medium, mechanical guards, each confirmed against the cited lines; F4 also against `schema.py:96-97`, which lets non-dict task entries through), the merged misnamed-test Medium (the PRD names the test in its acceptance list, so it keeps its name and gains Carl's `"files": [` assertion, which also makes it fail at base), and the step 5.5 wording Low (four-word deletion; no prose pin covers the clause).
- **Deferred by design (2 findings, `deferred_decisions` + ledger `settled-deferral` + batch deferred JSON; batch-end review may overrule):** F7 — task 4's text mandated copying the private helpers into the new suite, not importing them; the re-parse Low — the PRD pins `Verdict`'s field list exactly, so tree presence cannot ride on the dataclass without a spec deviation, and task 3 prescribed `policy.prd_modules(text) is None`.
- **Discarded (2 replay rows, reasons in the ledger):** `test_production_parser_exposes_no_count_flag` is a pre-existing test moved unchanged in e1691bb (pins the absence of `--count`, already absent at base); `test_optional_markers_stay_absent_rather_than_false` and `test_plan_expansion_only_counts_inside_a_well_formed_block` are negative pins by design (the key is absent by default; a body mention does not opt in), and the positive pin `test_plan_expansion_recognized_only_at_allow` is among the 55 the replay reports failing at base.

## Follow-up Tasks Created

Two `[D1]` tasks at tier `opus` (classifier default `sonnet` raised by the PRD's `default_model: opus` floor), covering 8 of the 12 findings; `state.rework_task_ids = ["6", "7"]`.

1. Task 6 — Harden the Repository Structure parse and the coverage check in `cli/policy.py`: implicit ancestors of file entries are grouping-only, absolute tree paths terminate, task paths are normalized, malformed task entries count as unfiled (M) - 🟠 High - 4 findings (F1, F2, F3, F4)
2. Task 7 — `check-plan`: fail loud on a split-note write error and print the unfiled/drift diagnostic on a stall too; make `test_step_4_7_payloads_carry_files` assert the files key; drop the self-contradictory step 5.5 clause (S) - 🟡 Medium - 4 findings (F5, F6, the merged misnamed-test row, the wording Low)

## Alice

Consensus lens, Claude subagent (sonnet). She read the diff, the assumptions ledger and the code paths Devon left open, and judged the fail-first replay from the orchestrator's reading of its four rows. 1 🟡 Medium, 2 ⚪ Low, all twelve R rules pass.

```
[ALICE] 🟡 test_step_4_7_payloads_carry_files no longer asserts a `"files"` key exists in the payloads (that check moved to the sibling test_step_4_7_payload_files_are_real_repo_relative_paths during the function-cap split); the name now promises something the body doesn't check | File: skills/plan-tasks/scripts/test_plan_size_gate_prose.py | Task: 4
[ALICE] ⚪ SKILL.md step 5.5 still reads "the gate is advice here, not a gate," a self-contradictory carry-over from the pre-PRD wording (Pat LOW, unresolved) | File: skills/plan-tasks/SKILL.md | Task: 4
[ALICE] ⚪ _run_check_plan re-parses the PRD tree via policy.prd_modules(text) to derive drift_word instead of reading it off Verdict, duplicating work plan_expansion already did (Pat LOW, unresolved) | File: skills/run-autopilot/cli/__main__.py | Task: 3

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

Blind lens, Claude subagent (sonnet), PRD and rubric only. He located every module the PRD names, verified the constants, the frozen `Verdict` fields, the leaf/grouping/root-file tree semantics, the opt-in, the CLI exit contract (including the exit-1 usage error via the pre-existing `_ArgumentParser.error` override, which he judged consistent with the spec's "argparse usage error" and the CLI's own exit-code table), the SKILL.md steps, the reference docs and the CHANGELOG; ran the three touched suites (66 passed), both prose suites (36), the doc-contract test (1), the full cli suite (1054 passed, 653 subtests) and `release-checks` (exit 0). No scope creep, no new dependencies, no destructive operations. Commits map 1:1 onto the five tasks.

```
[BLAKE] ✅ No issues found

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
```

## Bob

Doubt + de-slop lens, codex (static-only sandbox), first dispatch, no retry. 8 issue lines (2 🟠, 5 🟡, 1 ⚪), eight FIX items, empty VERIFY and KNOWN buckets. R1, R4, R7, R9 and R10 fail on his own findings (F1/F2 for R4/R9, F3/F4 for R7, F5 for R10, the missing tests for R1); D1-D5 pass. The orchestrator confirmed F1, F2, F5 and F6 by reading the cited lines and F4 against `schema.py:96-97`; F7 is deferred by design (task 4 mandated the copy) and F8 is merged into the `[3/4]` misnamed-test row.

```
[BOB] 🟠 F1: Slash-separated file entries lose implicit directory ancestry. A tree containing `src/` and `└── auth/login.py` leaves `src` recursively covered, allowing unrelated `src/payments` and `src/orders` tasks through the drift gate. | File: skills/run-autopilot/cli/policy.py:126 | Task: 2
[BOB] 🟠 F2: An absolute tree directory such as `/tmp/src/` hangs the ancestor loop: eventually `dirname("/") == "/"`, so parsing never terminates, even with the override set. | File: skills/run-autopilot/cli/policy.py:131 | Task: 2
[BOB] 🟡 F3: Coverage compares unnormalized paths. `./src/auth/a.py` is falsely unlisted, while `src/auth/../payments/a.py` is falsely covered by the `src/auth` leaf. | File: skills/run-autopilot/cli/policy.py:152 | Task: 2
[BOB] 🟡 F4: Task metadata lacks boundary validation. State loading permits non-dictionary task entries, which crash at `task.get`; a task with `files: [null]` instead disappears from the note with `unfiled=0`. | File: skills/run-autopilot/cli/policy.py:165 | Task: 2
[BOB] 🟡 F5: Split-note directory creation and writing leave `OSError` uncaught. An existing regular file named `split-notes` produces a traceback and exit 1, outside step 5.5's documented error handling. | File: skills/run-autopilot/cli/__main__.py:435 | Task: 3
[BOB] 🟡 F6: Stall verdicts return before emitting the required unfiled/skipped-drift diagnostic. For example, 16 unfiled tasks against a PRD without a tree print neither diagnostic on stderr. | File: skills/run-autopilot/cli/__main__.py:439 | Task: 3
[BOB] 🟡 F7: `_mask_non_prose` duplicates the existing implementation in `test_plan_tasks_prose.py:55`, creating two copies of the same masking behavior to maintain. | File: skills/plan-tasks/scripts/test_plan_size_gate_prose.py:65 | Task: 4
[BOB] ⚪ F8: `test_step_4_7_payloads_carry_files` checks payload count and routing shape but never checks the `files` key; its name became misleading after the split. Its passing against base is otherwise legitimate. | File: skills/plan-tasks/scripts/test_plan_size_gate_prose.py:559 | Task: 4

FIX:
- F1 — skills/run-autopilot/cli/policy.py:126 — Collect implicit parent directories from file entries before continuing; add a slash-separated-file regression fixture.
- F2 — skills/run-autopilot/cli/policy.py:131 — Reject absolute tree paths explicitly and ensure ancestor traversal terminates at a fixed point.
- F3 — skills/run-autopilot/cli/policy.py:152 — Normalize tree and task paths consistently before comparison; reject paths escaping the repository.
- F4 — skills/run-autopilot/cli/policy.py:165 — Validate task objects and file-list elements before grouping; report malformed metadata with its task index through the CLI's input-error path.
- F5 — skills/run-autopilot/cli/__main__.py:435 — Catch note-write errors, name the failing path, return a documented error code, and pin the existing-file obstruction case.
- F6 — skills/run-autopilot/cli/__main__.py:439 — Emit applicable diagnostics after the two stall lines and before returning 3; add a stalled-plan diagnostic test.
- F7 — skills/plan-tasks/scripts/test_plan_size_gate_prose.py:65 — Extract the identical masking implementation into one shared test helper without changing behavior.
- F8 — skills/plan-tasks/scripts/test_plan_size_gate_prose.py:559 — Rename it to `test_step_4_7_payloads_have_the_expected_routing_pair`.
VERIFY:
- (none)
KNOWN:
- (none)

R1: fail
R2: pass
R3: pass
R4: fail
R6: pass
R7: fail
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
```

## Carl

Consensus lens, gemini-run backend=copilot model=gemini-3.8-flash, exit 0, no retry. Read the context, the diff, the assumptions ledger, `policy.py`, the CLI, the CHANGELOG, `release-checks` and the reference docs; ran the three touched suites and `release-checks` twice (once with the host dispatch markers unset) and checked the one skipped test's reason. No frontend surface, reviewed as a generalist. 1 🟡 Medium, 2 ⚪ Low, all twelve R rules pass.

```
[CARL] 🟡 test_step_4_7_payloads_carry_files is misnamed after the function-cap split; add 'assert all("\"files\": [" in p for p in payloads)' to assert files | File: skills/plan-tasks/scripts/test_plan_size_gate_prose.py | Task: 4
[CARL] ⚪ _run_check_plan re-parses PRD tree via policy.prd_modules(text) rather than carrying tree presence in Verdict | File: skills/run-autopilot/cli/__main__.py | Task: 3
[CARL] ⚪ Self-contradictory phrasing in step 5.5 interactive warning ('the gate is advice here, not a gate') | File: skills/plan-tasks/SKILL.md | Task: 4

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

- Tautological shapes: none (99 test functions in 5 files checked).
- Fail-first replay at `184db706`: 59 touched tests ran, 55 failed against base, 4 passed. Three `[MECH]` lines absorbed: `test_step_4_7_payloads_carry_files` joined the `[3/4]` row above as `mech-check` (its fix makes it fail at base); `test_production_parser_exposes_no_count_flag` (pre-existing, moved unchanged) and the two `test_frontmatter.py` negative pins discarded with reasons in the ledger.

Verdict: 12 findings

Tests: 1846 passed, 0 failed, 1 skipped (reused from last-verification.json at a44f2e0347ca5fa0fbedfdb0f4bf664e10f62b7c)
