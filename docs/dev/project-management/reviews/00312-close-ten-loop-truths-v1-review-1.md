---
prd: docs/dev/project-management/prds/wip/00312-close-ten-loop-truths-v1.md
review: 1
date: 2026-10-15
head_sha: 257141c190cec297376f033d1086bcc73478c002
codex_thread_id: 01a14053-5c68-77e2-a1b2-0a925b51a0fb
reviewers: alice,blake,bob,carl
agents:
  alice: available
  blake: available
  bob: available
  carl: available
dispatch_rows:
  bob: aa72c141
  carl: 9757e5cc
---

# Review: 00312-close-ten-loop-truths-v1

Diff range: `57fb258a2ef2612dcf1b53aab81e03a9da4a8fa4..257141c190cec297376f033d1086bcc73478c002`

codex_rung_guard: not fired

## Review Summary

Reviewed: 5 completed tasks
PRDs checked: 00312-close-ten-loop-truths-v1.md

### Agent Status

- Alice: ✅ Available (consensus lens, engine `legacy`)
- Blake: ✅ Available (blind lens, PRD-only)
- Bob: ✅ Available (doubt lens + de-slop, codex) — after one retry (inlined)
- Carl: ✅ Available (backend=copilot model=gemini-3.8-flash)
- Eve: ⏸️ Disabled: resolved doubt reviewer is `codex` and no task was
  implemented by codex, so the codex doubt-roster guard did not fire

### Degradations recorded this cycle

- **Engram context pack failed**: `engram pack exit 1: sqlite3.OperationalError:
  attempt to write a readonly database`. Every prompt carried the
  `(no pack available this cycle)` sentinel for `{PACK_FILE}` and
  `{PACK_FINDINGS}`. This review is degraded in reuse/findings precedent, not
  invalid. Known sandbox limitation of loop-mode runs under `run-agent`.
- **Bob's first run was a lack-of-input refusal**: codex's own sandbox denied
  read access (`sandbox_apply: Operation not permitted`), so he emitted
  `[BOB] ⚪ Cannot statically verify` with every `R{n}` failed. The refusal shape
  matched all three conditions in `references/retry-policy.md` § Lack-of-input
  refusal, so his single retry was spent on the inlined retry prompt
  (`docs/dev/tmp/bob-prompt-20261015-1800-retry.md`, 178 KB: review context and
  the full diff inlined verbatim). The retry produced a real review. The
  first-run refusal is retained at
  `docs/dev/tmp/bob-output-20261015-1800-firstrun-refusal.txt`.
- **Bob format warning**: his retry output bulleted every issue line
  (`- [BOB] 🟡 …`) inside the FIX/KNOWN sections, which
  `consolidate_findings.py` does not parse, so his first consolidation dropped
  all nine of his findings. His one-retry budget was already spent, so per
  `references/retry-policy.md` § Format Compliance step 2 his lines were parsed
  as far as they could be: the bullet prefix was stripped mechanically to
  `docs/dev/tmp/bob-output-20261015-1800-normalized.txt` (9 lines de-bulleted,
  no other edit) and consolidation re-run against that file. Bob's findings
  below carry `(format warning)`.
- **Working tree at review entry**: this session found 8 `skills/run-autopilot/cli/*.py`
  files modified with pure end-of-turn formatter reflow (line wrapping,
  `datetime.timezone.utc` → `datetime.UTC`, `__all__` sort, one behaviour-preserving
  SIM114 if/elif merge) and no PRD work. It was discarded with `git checkout`
  before the review was staged, so the reviewed tree is clean at HEAD.

## Consolidated Findings

22 findings: 0 🔴 critical, 0 🟠 high, 14 🟡 medium, 8 ⚪ low.

| Ref | Consensus | Severity | Issue | File | Task | Found By |
|-----|-----------|----------|-------|------|------|----------|
| R1 | [2/4] | 🟡 | The PRD contract says `_AUTOPILOT_LOOP_ENTRY_STALE` is never set after a successful write or a successful invalidation, but no test covers it. Removing either `env.pop` (loop.py:580 and loop.py:611) leaves every test green. A stale marker from one launch could then leak into the next successful launch and disable replay. Add a test with a failure followed by a success, asserting the variable is absent on the second child. | skills/run-autopilot/cli/test_loop_act.py:757 | 1 | ALICE, BOB |
| R2 | [2/4] | ⚪ | The first new CHANGELOG entry says the "catchup guard" now finds Darwin ancestor processes, but the catchup guard is the `merge-base --is-ancestor` change and has nothing to do with `pgrep`. Its own entry is the next line, so this is a wording slip | CHANGELOG.md:87 | general | BLAKE, BOB |
| R3 | [1/4] | 🟡 | The usage-limit wait print and notify are copied from `_act_continue` into `_budget_bound`, so two sites must now stay in step. Extract one helper (for example `_announce_limit_wait(decision)`) and call it from both. | skills/run-autopilot/cli/loop_decision.py:563 | 3 | ALICE |
| R4 | [1/4] | 🟡 | `_decision_fields` assigns `fields["limit_wait"]` in two branches, and the `elif` line is over 100 characters. Merge them into one condition, `limit_wait is not None and (effective_signal(decision) == "continue" or (decision["signal"] == "park" and decision.get("park_site") == "budget"))`. | skills/run-autopilot/cli/loop.py:136 | 3 | ALICE |
| R5 | [1/4] | 🟡 | `_record_entry` repeats the "invalidate, else set `_AUTOPILOT_LOOP_ENTRY_STALE`" pair in two except branches. The pop is also written twice, at the top of `_record_entry` and in the `_pre_enter` early return. Pop once at the top of `_pre_enter`, and have `_invalidate_loop_entry` or a small helper own the marking. | skills/run-autopilot/cli/loop.py:580 | 3 | ALICE |
| R6 | [1/4] | 🟡 | `test_budget_park_row_carries_limit_wait` and `test_instant_exit_limit_row_carries_limit_wait` call `_decision_fields` directly. The PRD and task text ask for the metrics row from the scripted loop. The negative case is also untested: a non-budget park must carry no `limit_wait`. | skills/run-autopilot/cli/test_loop_metrics.py:55 | 1 | ALICE |
| R7 | [1/4] | 🟡 | The doc-contract test accepts invalid argv containing the expected flag substrings. Removing `[--state]` or adding obsolete positionals still passes. Validate the invocation's required, optional, and positional arguments against the parser. (format warning) | skills/run-autopilot/cli/test_doc_contract.py:102 | 1 | BOB |
| R8 | [1/4] | 🟡 | Both wait-metrics tests inspect `_decision_fields` directly, although the PRD requires reading emitted metrics rows. Exercise the scripted loop and assert `limit_wait` in `metrics_rows` for both paths. (format warning) | skills/run-autopilot/cli/test_loop_metrics.py:55 | 1 | BOB |
| R9 | [1/4] | 🟡 | The grandchild can query before the parent writes its registry entry; the result file can also become visible before writing finishes. Synchronize registry readiness and result completion to prevent intermittent failures. (format warning) | skills/run-autopilot/cli/test_enter_loop_only.py:378 | 1 | BOB |
| R10 | [1/4] | 🟡 | The budget branch duplicates `_act_continue`'s wait announcement and notification. Extract one shared announcement method, retaining each caller's existing sleep ordering. (format warning) | skills/run-autopilot/cli/loop_decision.py:564 | 3 | BOB |
| R11 | [1/4] | 🟡 | The drained row repeats its existing absent-state condition, while its test checks a phrase anywhere in the document. Consolidate the row into conditional init followed by phase-done, and scope the assertion to that row. (format warning) | skills/run-autopilot/SKILL.md:315 | 4 | BOB |
| R12 | [1/4] | 🟡 | The supplied mechanical check identifies an either-or assertion in `test_wrapper_alive_script_requires_root_arg` that cannot reject the unwanted outcome. This assertion is unchanged and outside the PRD's seventeen regression tests. (format warning) | skills/run-autopilot/scripts/tracon/test_discovery.py:1665 | general | BOB |
| R13 | [1/4] | 🟡 | test_wrapper_alive_script_requires_root_arg hedges with or: either outcome satisfies it | skills/run-autopilot/scripts/tracon/test_discovery.py:1665 | general | CARL, mech-check |
| R14 | [1/4] | ⚪ | `test_loop_gates.py` carries unrelated reformatting: wrapped dict literals, parameter lists exploded one per line and an `assert (...)` wrap, in tests the PRD does not touch. This looks like an end-of-turn reflow. Revert it so the diff traces only to the PRD. | skills/run-autopilot/cli/test_loop_gates.py:277 | 1 | ALICE |
| R15 | [1/4] | ⚪ | `_invalidate_loop_entry` now returns False on a failed write but prints nothing. The operator sees the first failure and not why the entry stays replayable. One stderr line would make the new stale-marker path visible. | skills/run-autopilot/cli/loop.py:652 | 3 | ALICE |
| R16 | [1/4] | ⚪ | `mech-check` flagged `test_wrapper_alive_script_requires_root_arg` for hedging with `or`, so either outcome passes. The test is pre-existing but sits in a file this diff touches. | skills/run-autopilot/scripts/tracon/test_discovery.py:1665 | general | ALICE |
| R17 | [1/4] | ⚪ | The diff grows files already far over the 800-line limit: `__main__.py` is 1967 lines (+5) and `test_discovery.py` is 1667 (+20). `test_loop_gates.py` was split to stay under the limit, but these two were not. | skills/run-autopilot/cli/__main__.py:1967 | general | ALICE |
| R18 | [1/4] | ⚪ | In `_replay_loop_entry` the `_AUTOPILOT_LOOP_ENTRY_STALE` check comes after the `loop_entry` delete. If the state file stays unwritable, the child's `autopilot enter` returns 2 at the delete and never reaches the "run the entry for real" path. This only matters under persistent write failure and the PRD does not specify the order | skills/run-autopilot/cli/__main__.py:396 | loop-messages | BLAKE |
| R19 | [1/4] | ⚪ | `test_state_schema_cli_rows_match_the_parsers` only checks that the required flags appear in the two rows. It does not assert the old positional forms (`<state.json>`, `<review-file>`) are gone, and it ignores the optional `--state`. A row that keeps the old text and adds the flags would still pass | skills/run-autopilot/cli/test_doc_contract.py:67 | entry-hygiene | BLAKE |
| R20 | [1/4] | ⚪ | Existing size violations remain: `_select_report_block` is 55 lines, and its containing file exceeds 800 lines. These predate this diff; restructuring unchanged code is outside this PRD. (format warning) | skills/run-autopilot/cli/__main__.py:1508 | general | BOB |
| R21 | [1/4] | 🟡 | 9 touched test(s) pass against the pre-change code: test_loop_entry_then_skill_entry_writes_one_resume_row, test_stale_loop_entry_is_dropped, test_manual_prd_arg_skips_the_replay_even_with_a_matching_entry, test_pre_enter_failure_invalidates_a_stale_same_prd_entry, test_pre_enter_write_failure_invalidates_a_stale_same_prd_entry, test_pre_enter_runs_only_for_a_build_or_a_park_marker +3 more | skills/run-autopilot/cli/test_loop_gates.py | general | mech-check |
| R22 | [1/4] | 🟡 | 15 touched test(s) pass against the pre-change code: test_duplicate_loop_guard_refuses_a_second_loop, test_registry_entry_written_and_removed_at_teardown, test_registry_entry_carries_the_tracon_contract_shape, test_own_stale_registry_entry_is_overwritten_not_refused, test_registry_write_failure_runs_unregistered_loud, test_loops_dir_is_propagated_to_session_children +9 more | skills/run-autopilot/cli/test_loop_gates_registry.py | general | mech-check |

Rows R21 and R22 are the fail-first replay block's `[MECH]` lines, absorbed as
their own rows (no consolidated row named the same test files). Row R13
absorbed the tautological-shapes block's single `[MECH]` line by appending
`mech-check` to its finders.

## Alice

Nine findings, all 🟡 Medium or ⚪ Low, concentrated on de-duplication of the
new wait-announcement and stale-marker paths, and on tests that assert through
`_decision_fields` rather than the emitted metrics row the PRD names.

```
[ALICE] 🟡 The usage-limit wait print and notify are copied from `_act_continue` into `_budget_bound`, so two sites must now stay in step. Extract one helper (for example `_announce_limit_wait(decision)`) and call it from both. | File: skills/run-autopilot/cli/loop_decision.py:563 | Task: 3
[ALICE] 🟡 `_decision_fields` assigns `fields["limit_wait"]` in two branches, and the `elif` line is over 100 characters. Merge them into one condition. | File: skills/run-autopilot/cli/loop.py:136 | Task: 3
[ALICE] 🟡 `_record_entry` repeats the "invalidate, else set `_AUTOPILOT_LOOP_ENTRY_STALE`" pair in two except branches. The pop is also written twice. | File: skills/run-autopilot/cli/loop.py:580 | Task: 3
[ALICE] 🟡 The PRD contract says `_AUTOPILOT_LOOP_ENTRY_STALE` is never set after a successful write or a successful invalidation, but no test covers it. | File: skills/run-autopilot/cli/test_loop_act.py:757 | Task: 1
[ALICE] 🟡 `test_budget_park_row_carries_limit_wait` and `test_instant_exit_limit_row_carries_limit_wait` call `_decision_fields` directly. The negative case is also untested. | File: skills/run-autopilot/cli/test_loop_metrics.py:55 | Task: 1
[ALICE] ⚪ `test_loop_gates.py` carries unrelated reformatting in tests the PRD does not touch. | File: skills/run-autopilot/cli/test_loop_gates.py:277 | Task: 1
[ALICE] ⚪ `_invalidate_loop_entry` now returns False on a failed write but prints nothing. | File: skills/run-autopilot/cli/loop.py:652 | Task: 3
[ALICE] ⚪ `mech-check` flagged `test_wrapper_alive_script_requires_root_arg` for hedging with `or`. | File: skills/run-autopilot/scripts/tracon/test_discovery.py:1665 | Task: general
[ALICE] ⚪ The diff grows files already far over the 800-line limit: `__main__.py` is 1967 lines (+5) and `test_discovery.py` is 1667 (+20). | File: skills/run-autopilot/cli/__main__.py:1967 | Task: general
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
R13: fail
```

## Blake

Blind lens, PRD-only. Three ⚪ Low findings, and every blind rubric rule passes.
He confirms every Must-have item is implemented, all 17 named tests exist, and
both acceptance pytest commands pass (184 passed for the cli files plus
`test_loop_gates_registry.py`; 91 passed for `test_discovery.py`). He states
plainly what he did not run: the PRD's fail-first check at the base commit, and
the Phase 1 `rg` acceptance greps beyond `is-ancestor`.

```
[BLAKE] ⚪ In `_replay_loop_entry` the `_AUTOPILOT_LOOP_ENTRY_STALE` check comes after the `loop_entry` delete. | File: skills/run-autopilot/cli/__main__.py:396 | Task: loop-messages
[BLAKE] ⚪ `test_state_schema_cli_rows_match_the_parsers` only checks that the required flags appear in the two rows. | File: skills/run-autopilot/cli/test_doc_contract.py:67 | Task: entry-hygiene
[BLAKE] ⚪ The first new CHANGELOG entry says the "catchup guard" now finds Darwin ancestor processes, but that is the `pgrep` change, not the catchup guard. | File: CHANGELOG.md:87 | Task: general
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

Doubt lens plus de-slop, codex, **after one retry (inlined)**. Nine findings,
seven in FIX and two in KNOWN (both explicitly out of this PRD's scope). His
VERIFY bucket is empty, so no verification-check queue file was written for
this cycle. Issue lines carried a bullet prefix his budget could not be spent
re-formatting; see the format warning above.

```
FIX:
[BOB] 🟡 The doc-contract test accepts invalid argv containing the expected flag substrings. | File: skills/run-autopilot/cli/test_doc_contract.py:102 | Task: 1
[BOB] 🟡 Both wait-metrics tests inspect `_decision_fields` directly, although the PRD requires reading emitted metrics rows. | File: skills/run-autopilot/cli/test_loop_metrics.py:55 | Task: 1
[BOB] 🟡 Stale-marker coverage tests failure only; required clearance after successful recording or invalidation remains untested. | File: skills/run-autopilot/cli/test_loop_act.py:90 | Task: 1
[BOB] 🟡 The grandchild can query before the parent writes its registry entry; the result file can also become visible before writing finishes. | File: skills/run-autopilot/cli/test_enter_loop_only.py:378 | Task: 1
[BOB] 🟡 The budget branch duplicates `_act_continue`'s wait announcement and notification. | File: skills/run-autopilot/cli/loop_decision.py:564 | Task: 3
[BOB] 🟡 The drained row repeats its existing absent-state condition, while its test checks a phrase anywhere in the document. | File: skills/run-autopilot/SKILL.md:315 | Task: 4
[BOB] ⚪ The changelog reverses the ancestry relationship: the guard rejects a base that is no longer an ancestor of HEAD. Replace "descendant" with "ancestor." | File: CHANGELOG.md:88 | Task: 5

VERIFY:
- (none)

KNOWN:
[BOB] 🟡 The supplied mechanical check identifies an either-or assertion in `test_wrapper_alive_script_requires_root_arg` that cannot reject the unwanted outcome. Unchanged and outside the PRD's seventeen regression tests. | File: skills/run-autopilot/scripts/tracon/test_discovery.py:1665 | Task: general
[BOB] ⚪ Existing size violations remain: `_select_report_block` is 55 lines, and its containing file exceeds 800 lines. These predate this diff. | File: skills/run-autopilot/cli/__main__.py:1508 | Task: general

R1: fail
R2: fail
R3: pass
R4: pass
R6: pass
R7: pass
R8: pass
R9: fail
R10: pass
R11: pass
R12: fail
R13: fail

D1: pass
D2: pass
D3: pass
D4: pass
D5: pass
```

## Carl

Frontend & design specialist running as generalist here (this PRD has no UI
surface). Ran on `backend=copilot model=gemini-3.8-flash`. One 🟡 finding,
every consensus rubric rule passes.

```
[CARL] 🟡 test_wrapper_alive_script_requires_root_arg hedges with or: either outcome satisfies it | File: skills/run-autopilot/scripts/tracon/test_discovery.py:1665 | Task: general
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

Verdict: 22 findings
Tests: 6918 passed, 0 failed, 34 skipped (suite run this cycle)
