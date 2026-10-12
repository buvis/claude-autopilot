---
prd: docs/dev/project-management/prds/wip/00271-guard-v2-structural-delegation-check-v1.md
review: 1
date: 2026-10-12
head_sha: 851c38619d72bfa08b3600436b2cfa2a9c1d4801
codex_thread_id: 01a131a4-57dc-7743-9e2f-1ef6f5b25a0e
reviewers: alice,blake,bob
agents:
  alice: available
  blake: available
  bob: available
  carl: unavailable
dispatch_rows:
  bob: 90f62d3d
  carl: 73fedfe7
---

# Review: 00271-guard-v2-structural-delegation-check-v1

Diff range: `b57e4254e453b7cbaff2d37915174fca39a07362..851c38619d72bfa08b3600436b2cfa2a9c1d4801`

codex_rung_guard: not fired

## Review Summary

Reviewed: 10 completed tasks
PRDs checked: 00271-guard-v2-structural-delegation-check-v1

### Agent Status

- Alice: ✅ Available (consensus lens, legacy engine)
- Blake: ✅ Available (blind lens, PRD-only)
- Bob: ✅ Available (doubt lens, codex) — after one retry (inlined). His first run refused with a lack-of-input shape (`sandbox-exec: sandbox_apply: Operation not permitted` on both reads); the inlined retry prompt carried the context and the full diff verbatim.
- Carl: ⚠️ Unavailable: gemini-run exit 1 on both the first run and the retry, backend `copilot` model `gemini-3.8-flash`, `Error: Authentication failed` (GitHub Copilot token invalid/expired). Not exit 4, so no batch-level latch was written.

pack: failed (engram pack exit 1: `sqlite3.OperationalError: attempt to write a readonly database`) — the review ran without the findings-precedent pack, which is degraded, not invalid.

Consolidation note (fail loud): `consolidate_findings.py` rejected Bob's issue lines on the first run because he emitted them as markdown bullets (`- [BOB] …`), which its `^\[` line regex drops. The bullets were stripped and the script re-run; the table below is the script's output with all three lenses parsed. The script's same-file merge then folded several distinct per-file findings into rows R1 and R2 (see its merge notes); the merged-away items are kept verbatim in the per-reviewer sections below and are carried into the decision gate separately.

## Consolidated Findings

| Ref | Consensus | Severity | Issue | File | Task | Found By |
|-----|-----------|----------|-------|------|------|----------|
| R1 | [3/3] | 🟠 | Live replay `python3 dev/bin/replay_delegation_guard.py` exits 1, so PRD success metric 2 and the Phase 2 exit criterion ("exits 0 on this machine") are unmet. Re-run this cycle: `per-task 803 refused 7`, `other 182 refused 7`, exit 1. The exit is structurally unreachable because pinned deny `toolu_01Ku4TbcQoeik6ZLf5XkkAuD` ("Resume work phase for PRD 00242, task 1 onward") matches the per-task description regex (`task 1`). It is correctly refused, but `main` then sets `failed = True` for any refused non-`other` bucket. Six more refused dispatches look like real false refusals. Under `general-purpose`, Tess/Devon prompts quote a backticked `design-solution: <phase...>` label, which ends its clause and hits the weak anchor (`toolu_013NAWvgMnP4WatpZDVyiNAa`, `toolu_01DAQSaS3uAph2VZnfn5NC9d`, `toolu_019nCz3WRsAZSwdaHb9itXiT`, `toolu_013ePUKbLDE7DLnbnGmgszzR`). `toolu_015DM18ubZLJZbA65ozvuw8c` (Tess, no subagent_type) is refused on a `/autopilot:work` span. This build's own task-6 `autopilot:worker-opus` Ivan dispatch (`toolu_011UqbqFtUDPuSeCiLLgMvEg`) is refused because it quotes a strongly anchored phase sentence as a test case. It is not scoped, because the prompt names several task ids and paths. The PRD says to fix the predicate, never the buckets or the deny-id list. Either the pinned-id refusal must be excluded from the per-task failure condition (spec conflict, needs an operator call) or the predicate must be narrowed. As shipped, the guard would refuse the build's own per-task dispatches. | dev/bin/replay_delegation_guard.py:148 | 9 | ALICE, BLAKE, BOB |
| R2 | [3/3] | 🟠 | `_PATH_TOKEN = \S*/\S+\.\w+` is quadratic, which breaks the PRD requirement "every regex runs in linear time" and the per-MB bound. `_is_scoped` runs `finditer` over the whole field once any phase candidate exists. A prompt `"Run the work phase for PRD 7. " + "a" * N` takes 0.29 s at N=20k, 0.98 s at 40k and 3.76 s at 80k, so the 5 s hook timeout is reached near 95 KB (a base64 blob or minified JSON would do it). Many candidates in one huge clause also scale quadratically (`'about the work phase and ' * 160000`: 4.5 s, and 0.375 s/MB at 1 MB, above the 0.3 budget). That path slices `text[end:clause_end]` per candidate (hooks/guard_phase_delegation.py:365) and lists every word in the clause per candidate (hooks/guard_phase_delegation.py:367 and :389). Replace the path regex with a linear token scan (split on whitespace, then test each token for `/` and a suffix) and bound the per-candidate clause slices. `test_guard_time_per_mb_stays_under_the_baseline` uses only prompts with zero candidates and spaces, so it cannot see this. Add a long-unbroken-token case and a many-mentions case. | hooks/guard_phase_delegation.py:166 | 5 | ALICE, BLAKE, BOB |
| R3 | [2/3] | 🟡 | `hooks/test_guard_phase_delegation_structure.py` is 804 lines, over the 800-line limit. Split off the normalization sweep (`test_normalize_*`, lines 224-330) into its own module, and register it in `dev/bin/release-checks`. | hooks/test_guard_phase_delegation_structure.py:804 | 5 | ALICE, BOB |
| R4 | [2/3] | ⚪ | CHANGELOG.md keeps the task-1 line "the phase-delegation guard normalizes lookalike text before matching..." beside the new guard line, which already says format characters and combining marks are stripped and every dash reads as `-`. The spec says to replace the 00267 guard line with the three lines, so this extra entry is redundant. The surrogate and leave-marker lines also sit at lines 17-18, away from the guard line at 28. Drop line 16 or fold it into line 28. | CHANGELOG.md:16 | 10 | ALICE, BLAKE |
| R5 | [1/3] | 🟠 | File scoping counts occurrences instead of distinct paths and accepts root-relative `prds/wip/00300.md` as an ordinary file. Thus a scoped-looking phase sentence naming one store path is allowed. Deduplicate paths and exclude both `prds/` and `/prds/` segments. | hooks/guard_phase_delegation.py:335 | 5 | BOB |
| R6 | [1/3] | 🟠 | `_negated` materializes every preceding word before slicing the last five; repeated negated, strongly anchored candidates in one clause therefore cause quadratic work. Precompute word positions once and use binary searches or implement the specified backward walk. | hooks/guard_phase_delegation.py:384 | 7 | BOB |
| R7 | [1/3] | 🟠 | The recorded live replay still refuses six legitimate per-task dispatches. The deferred evidence identifies quoted citations, including a strongly anchored worker test string; blanket quote exemptions would contradict the explicit design. Resolving these requires reconciling the settled quote policy with the zero-false-refusal success metric, outside a behavior-preserving fix. | docs/dev/project-management/autopilot/deferred/202610111300-deferred.json:58 | 9 | BOB |
| R8 | [1/3] | 🟡 | Fixed character slices silently narrow unbounded contracts: the 16-character skill-suffix probe misses longer whitespace, and 24-character task-range probes miss longer whitespace between range words. Match against the original string using positions and explicit boundaries instead of arbitrary character caps. | hooks/guard_phase_delegation.py:279 | 5 | BOB |
| R9 | [1/3] | 🟡 | The supplied fail-first result says the lone-surrogate denial test passes at base, so it does not demonstrate the targeted subprocess encoding failure. Add a strict-UTF-8 subprocess case asserting exit 2 and the lifecycle message, then confirm failure at base. | hooks/test_enforce_prd_location.py:150 | 3 | BOB |
| R10 | [1/3] | ⚪ | `_PHASE_BARE` has lookbehind `(?<![-/:\w])`, but the PRD says `(?<![-/\w])`. The extra `:` is harmless today because the `autopilot:` form covers the prefixed case, but it deviates from the spec. | hooks/guard_phase_delegation.py:98 | 5 | BLAKE |
| R11 | [1/3] | ⚪ | `_PRD_PATH_TAIL` (a path under `prds/` anchors on its own) is not in the PRD's anchor list. It is needed to satisfy the required deny of a prds/wip path sentence, so I treat it as a justified small addition, not scope creep. The PRD text itself does not produce that deny. | hooks/guard_phase_delegation.py:120 | 5 | BLAKE |
| R12 | [2/3] | 🟡 | Merged away by the consolidator, restored verbatim: the SKILL.md follow phrase ignores a negation sitting before the verb. `_ordered_to_follow` checks only the verb-object gap while `_negated` checks only before the path, so `Read skills/work/SKILL.md; you must never follow it` is denied. A false-deny path. | hooks/guard_phase_delegation.py:375 | 5 | BLAKE, BOB |
| R13 | [1/3] | 🟡 | Merged away by the consolidator, restored verbatim: the bare slash-command check uses `\b` after the skill name, not "first token is", so a longer hyphenated token beginning with the command name is always refused. The PRD says the first token must be the command. | hooks/guard_phase_delegation.py:148 | 5 | BLAKE |
| R14 | [1/3] | 🟠 | Merged away by the consolidator, restored verbatim: task scoping counts occurrences instead of distinct IDs and discards range matches before deciding scope. Repeating one task id incorrectly removes scope, and a mixed id-plus-range sentence incorrectly gains it. Collect distinct IDs and reject task-based scope if ANY occurrence has range adjacency. | hooks/guard_phase_delegation.py:335 | 5 | BOB |
| R15 | [2/3] | 🟠 | Merged away by the consolidator, restored verbatim: the replay treats every non-zero subprocess exit as a policy denial. A guard crashing with exit 1 satisfies the pinned-deny checks and can produce exit 0 for an all-`other` corpus. Test for exit 2 and report any other non-zero exit as an execution error with stderr. | dev/bin/replay_delegation_guard.py:108 | 9 | ALICE, BOB |
| M1 | [1/3] | 🟡 | 1 touched test(s) pass against the pre-change code: test_missing_guard_cannot_report_an_allowed_run | dev/bin/test_replay_delegation_guard.py | general | mech-check |
| M2 | [1/3] | 🟡 | 7 touched test(s) pass against the pre-change code: test_allows_non_lifecycle_write_whose_path_holds_a_lone_surrogate, test_allows_ordinary_source_and_lifecycle_prd_paths, test_blocks_bash_command_naming_a_repo_root_lifecycle_dir, test_blocks_file_in_store_root, test_blocks_multiedit_whose_later_edit_leaves_the_store, test_blocks_repo_root_backlog_write_whose_path_holds_a_lone_surrogate +1 more | hooks/test_enforce_prd_location.py | general | mech-check |
| M3 | [1/3] | 🟡 | 1 touched test(s) pass against the pre-change code: test_worker_dispatch_is_still_checked | hooks/test_guard_phase_delegation.py | general | mech-check |
| M4 | [1/3] | 🟡 | 8 touched test(s) pass against the pre-change code: test_agoge_lookalike_types_are_still_checked, test_a_dispatch_naming_no_phase_is_allowed, test_a_phase_mention_past_the_first_64_characters_is_denied +2 more | hooks/test_guard_phase_delegation_dispatch.py | general | mech-check |
| M5 | [1/3] | 🟡 | 20 touched test(s) pass against the pre-change code: test_ordinary_prose_with_a_widened_verb_near_phase_jargon_is_allowed +14 more | hooks/test_guard_phase_delegation_narrowing.py | general | mech-check |
| M6 | [1/3] | 🟡 | 45 touched test(s) pass against the pre-change code: test_lookalike_dashes_and_invisible_marks_are_normalized_and_denied, test_per_task_dispatch_without_a_phase_instruction_is_allowed, test_the_prompt_and_description_are_two_separate_fields, test_packet_three_phrasings_are_denied, test_the_same_verb_phrase_flips_on_the_anchor_alone +39 more | hooks/test_guard_phase_delegation_structure.py | general | mech-check |
| M7 | [1/3] | 🟡 | 6 touched test(s) pass against the pre-change code: test_leave_row_marks_the_session, test_other_bash_commands_write_nothing, test_leave_row_without_an_autopilot_dir_writes_nothing, test_guard_without_an_autopilot_dir_passes, test_non_autopilot_skill_passes, test_malformed_marker_passes | hooks/test_guard_skill_after_leave.py | general | mech-check |
| M8 | [1/3] | 🟡 | 24 touched test(s) pass against the pre-change code: test_every_stdin_hook_survives_bad_input +18 more | hooks/test_read_input.py | general | mech-check |

No tautological-test shapes were detected this cycle.

## Alice

Findings: R1, R2, R3, R4, R15 (see the table).

Notes from her run:
- The listed test suites pass: 734 passed in `hooks` and `dev/bin`, plus 664 passed in the nine task test modules. She did not reproduce the context's 9 failures and traced them outside this diff's tests.
- The fail-first "pass at base" flags for the lone-surrogate denial test are a replay artifact: pytest reports the parent test as passed while its subtests fail. Against the base hook (extracted to a scratch git repo) all 5 subtests fail with `0 != 2`.
- Function lengths all fit the 50-line limit. `hooks/guard_phase_delegation.py` is 519 lines.

R1: fail
R2: pass
R3: pass
R4: pass
R6: pass
R7: pass
R8: pass
R9: fail
R10: fail
R11: pass
R12: pass
R13: fail

## Blake

Findings: R1, R2, R4, R10, R11, R12, R13 (see the table).

Verified OK in his own words:
- 664 tests pass across the guard, structure, dispatch, replay, narrowing, read_input, replay CLI, `enforce_prd_location` and `guard_skill_after_leave` files.
- `release-checks` lists every new test file.
- `replay.jsonl` holds 17 records (4 deny, 13 allow) with the right keys.
- `enforce_prd_location.py:177` normalizes the path before `Path.resolve()`.
- Both leave-marker hooks `allow()` on a U+FFFD session id before any marker read or write.
- The `agoge:` prefix exemption and both deny messages match the spec text.
- `find_phase_delegation` is exported.

His measured quadratic case: a 1.05 MB prompt of a repeated `work/SKILL.md.` sentence took 15.8 s; 240 KB took 0.9 s and 480 KB took 3.4 s, crossing the 5 s hook timeout near 0.55 MB against the PRD's ~16 MB target, and a timeout fails open. Cause: `next((s for s in sentences if s >= end), ...)` rescanning the sentence list per candidate in `_ordered_to_follow`.

B1: fail
B2: pass
B3: pass
B4: fail
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
B15: fail
B16: fail
B17: pass
B18: pass
B19: pass

## Bob

Ran after one retry (inlined). Doubt + de-slop lens.

FIX: R1, R2, R3, R5, R6, R8, R9, R12, R14, R15 (see the table).

VERIFY: (none) — so no verification-check queue file was written this cycle.

KNOWN:
- 🟠 Task 9's required successful replay is impossible under the prescribed exit rules: pinned deny `toolu_01Ku4TbcQoeik6ZLf5XkkAuD` buckets as per-task, so either verdict fails. The deferred record confirms exit 1. Resolving it requires changing the settled replay contract, outside an implementation-only fix; completion remains unfulfilled. | File: dev/bin/replay_delegation_guard.py:156 | Task: 9
- 🟠 The recorded live replay still refuses six legitimate per-task dispatches (R7 above). Resolving these requires reconciling the settled quote policy with the zero-false-refusal success metric, outside a behavior-preserving fix. | File: docs/dev/project-management/autopilot/deferred/202610111300-deferred.json:58 | Task: 9

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
R13: fail

D1: pass
D2: pass
D3: pass
D4: pass
D5: pass

## Carl

Carl: unavailable (gemini-run exit 1 twice; backend `copilot`, model `gemini-3.8-flash`; `Error: Authentication failed` — GitHub Copilot token invalid, expired, or missing the `Copilot Requests` permission). Exit 1 is a runtime failure, not the exit-4 permanent-unavailability shape, so no `state.batch.unavailable_reviewers` latch was written and the next cycle will try him again.

Verdict: 23 findings
Tests: 3436 passed, 9 failed, 0 skipped (reused from last-verification.json at 851c38619d72bfa08b3600436b2cfa2a9c1d4801)
