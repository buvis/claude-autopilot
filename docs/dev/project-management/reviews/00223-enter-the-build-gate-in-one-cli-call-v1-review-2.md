---
prd: dev/local/prds/wip/00223-enter-the-build-gate-in-one-cli-call-v1.md
review: 2
date: 2026-09-30
head_sha: 319343c31b9c8ccc3f3571038e13b43518d715e5
reviewers: alice,blake,bob,carl
agents:
  alice: available
  blake: available
  bob: available
  carl: available
---

# Review: 00223-enter-the-build-gate-in-one-cli-call-v1

Diff range: `20b4b0205d11c2cd252e10abd9458dad5ea554d0..319343c31b9c8ccc3f3571038e13b43518d715e5`

codex_rung_guard: not fired

pack: failed (engram exited 1 twice: "not inside a registered repo; register it in /Users/bob/.config/gita/repos.csv"). Every prompt that takes `{PACK_FILE}` / `{PACK_FINDINGS}` received the sentinel `(no pack available this cycle)`. Same failure as cycle 1. The review is degraded on retrieval context, not invalid.

Scope note: this is an INCREMENTAL cycle-2 review. `gather-context.sh` ran with `--since 20b4b0205d11c2cd252e10abd9458dad5ea554d0` (cycle 1's `head_sha`), so the diff covers exactly the ten `[D1]` rework tasks (ids 4-13) and nothing from cycle 1's already-reviewed range. 39 commits, 15 files, 2643 insertions / 363 deletions.

carl: ran on backend `copilot`, model `gemini-3.8-flash`.

bob: ran fresh (no `codex_thread_id` — cycle 1's `--emit-thread-id` sidecar was empty, and this cycle's is empty again, so no id is stamped and cycle 3 would also run him fresh).

## Review Summary

Reviewed: 13 completed tasks (3 original-plan, 10 `[D1]` rework)
PRDs checked: 00223-enter-the-build-gate-in-one-cli-call-v1

### Agent Status

- Alice: ✅ Available (Claude subagent, consensus lens)
- Blake: ✅ Available (Claude subagent, blind/PRD-only lens)
- Bob: ✅ Available (codex, doubt + de-slop lens; exit 0, first run, no retry)
- Carl: ✅ Available (gemini via copilot, frontend/design specialist running as a generalist here)

## Consolidated Findings

18 findings. 0 🔴 Critical, 3 🟠 High, 9 🟡 Medium, 6 ⚪ Low.

Twelve rows came from `consolidate_findings.py`; six more were absorbed from the computed fail-first replay block (`Found by: mech-check`). Four Blake re-raises were auto-dismissed against the settled-decisions ledger (listed at the end).

`consolidate_findings.py` merged row 1's four citations after `:line` suffix stripping (`enter.py:1 ~ :414 ~ :2 ~ :138`) — all four reviewers independently measured the same file-size breach. Its severity is the highest any reviewer assigned (Blake 🟠; Alice, Bob and Carl each 🟡).

| Consensus | Severity | Issue | File | Task | Found By |
|-----------|----------|-------|------|------|----------|
| [4/4] | 🟠 | `enter.py` is 414 lines against the PRD's Phase 0 exit criterion "under 400 lines" (computed file-line-count table: OVER by 14). The cycle-2 rework added about 60 net lines. The 800-line project limit is fine. Move the three side-effect helpers (`_git_head_sha`, `_record_resume_row`, `_review_log_has_dispatch_line`) to a sibling module, or inline the single-caller `_prepare_tree` into `_bootstrap`, or trim 14 lines of restating docstring | skills/run-autopilot/cli/enter.py:1 | 4 | ALICE, BLAKE, BOB, CARL |
| [2/4] | 🟠 | Task 4 mapped two new failure causes onto existing stops, but the stop-table rows still name one owner each. `fs_error` now also carries "read design doc ... failed" (enter.py:358) and the shallow `--prds` no-grandparent case (enter.py:161), yet the row routes only to "§ Ensure lifecycle directories exist, the `mkdir -p` block could not run". `park_halt` now also carries "unmapped park exit code" (enter.py:188), but its row says only "exit-code table row 5 (systemic halt)". This is the wrong-owner class task 7 fixed, and the PRD's own stated risk. State in the rows that `detail` selects the owner, as the `deferred_io` row already does | skills/run-autopilot/references/phase-build.md:29 | 7 | ALICE, BOB |
| [1/4] | 🟠 | The `stop` vocabulary goes beyond the spec: `STOPS` adds `fs_error`, `stall_op_malformed`, `park_precondition_failed`, `prd_not_found` and `state_write_failed`, and the mapping of park exit 2 to a new stop is invented behaviour | skills/run-autopilot/cli/enter.py:29 | general | BLAKE |
| [2/4] | 🟡 | The frontmatter warnings are dropped when the frontmatter write fails. `_write_prd` calls `frontmatter.apply` without `on_warning`, so a `state_write_failed` stop returns `warnings: []` and the parse and lane warnings (for example `design: skpi`) vanish. The verb prints them before the write for exactly this reason, and the `_write_prd` docstring claims they travel on "halt or not". Pass `on_warning=out["warnings"].append` so a failed write keeps them. `test_a_halt_before_the_frontmatter_write_still_carries_an_empty_warnings_list` currently blesses the empty list | skills/run-autopilot/cli/enter.py:297 | 6 | ALICE, BOB |
| [1/4] | 🟡 | Two steps not in the spec's ordered chain: a `state.json` bootstrap via `state.init` when the file is missing, and a `stall_op` malformed precheck before park. The bootstrap creates state as a side effect | skills/run-autopilot/cli/enter.py:146 | general | BLAKE |
| [1/4] | 🟡 | Step 2 does not import the function behind `_walk_up.py --clear-markers`. It loops over `handoff.MARKERS` and unlinks inline, although `cli/handoff.py` already has `clear_markers` (used at `__main__.py:404`). Behaviour is the same, but it is a second implementation that can drift | skills/run-autopilot/cli/enter.py:148 | general | BLAKE |
| [1/4] | 🟡 | 6 touched tests pass against the pre-change code: `test_raising_resume_row_is_swallowed_to_stderr`, `test_prd_arg_absent_from_wip_and_backlog_stops_prd_not_found`, `test_park_halt_codes_map_to_their_stops` | skills/run-autopilot/cli/test_enter.py | general | mech-check |
| [1/4] | 🟡 | 8 touched tests pass against the pre-change code: `test_cli_prints_one_json_line_with_every_key`, `test_cli_moves_a_backlog_prd_into_wip`, `test_cli_unreadable_state_exits_two`, `test_cli_future_schema_exits_six` +2 more | skills/run-autopilot/cli/test_enter_cli.py | general | mech-check |
| [1/4] | 🟡 | 18 touched tests pass against the pre-change code: `test_the_enter_verb_prints_eleven_keys_on_stdout_when_the_prd_warns`, `test_the_enter_verb_still_prints_only_the_detail_line_on_an_early_halt`, `test_the_prds_override_selects_from_the_named_tree`, `test_a_stamp_that_is_not_a_past_utc_instant_degrades_to_full_catchup` +12 more | skills/run-autopilot/cli/test_enter_decisions.py | general | mech-check |
| [1/4] | 🟡 | 1 touched test passes against the pre-change code: `test_an_unexpected_error_from_a_step_is_not_reported_as_a_stop` | skills/run-autopilot/cli/test_enter_guards.py | general | mech-check |
| [1/4] | 🟡 | 2 touched tests pass against the pre-change code: `test_every_stop_value_has_a_row`, `test_enter_mirrors_the_design_gate_awk_regex` | skills/run-autopilot/cli/test_enter_prose.py | general | mech-check |
| [1/4] | 🟡 | 16 touched tests pass against the pre-change code: `test_a_skip_entry_carries_exactly_the_five_documented_keys`, `test_select_stamps_each_skip_with_a_clock_reading_not_the_prds_own_mtime`, `test_every_skip_is_appended_under_batch_and_never_at_the_top_level`, `test_the_eligibility_check_runs_where_the_prds_path_derivation_points`, `test_an_unreadable_prd_is_reported_before_the_state_file_is_read` +11 more | skills/run-autopilot/cli/test_shared_lift.py | general | mech-check |
| [1/4] | ⚪ | The `parked` paragraph says a non-null `parked` means "print the STALLED banner and continue selection". But `_park` also sets `parked` on exit 5 (enter.py:183) together with `stop: "park_halt"`, where the owning row says PAUSE banner and end the turn. Scope the sentence to `stop` null so the two instructions cannot collide | skills/run-autopilot/references/phase-build.md:51 | 8 | ALICE |
| [1/4] | ⚪ | `_run_frontmatter` reads the PRD twice (once discarded, once inside `apply`). It also changed one observable behaviour: parse and lane warnings used to reach stderr before the future-schema preflight exit 6, and now print only after it passes. The task required both verbs to be unchanged | skills/run-autopilot/cli/__main__.py:590 | 9 | ALICE |
| [1/4] | ⚪ | Every literal CLI expectation in `test_enter_cli.py` uses `_printed_line`'s `catchup: "full"` / `design: "skip"`; the fixtures differ only in `prd` and `source`. Task 11 asked for a delta-catchup reuse case and a full-catchup run case asserting different literal dicts. The delta/reuse literal exists only in-process (test_enter.py:144), so a canned CLI reply that ignores catchup and design still passes the subprocess lane | skills/run-autopilot/cli/test_enter_cli.py:41 | 11 | ALICE |
| [1/4] | ⚪ | Catchup `skip` mutates state (`catchup_mode` to `"skipped"`), which the spec does not list. `design_mode == "skipped"` (a resumed session after a skip) falls to the artifact check and can report `run`. Mirrors the prose but is a latent re-run risk | skills/run-autopilot/cli/enter.py:329 | general | BLAKE |
| [1/4] | ⚪ | In `_select`, `--prd` handling is check-then-act (`exists` then `shutil.move`). Mitigated by the post-move verification | skills/run-autopilot/cli/enter.py:235 | general | BLAKE |
| [1/4] | ⚪ | The spec names `test_cli_prints_one_json_line_with_every_key`, `test_cli_unreadable_state_exits_two` and `test_cli_future_schema_exits_six` in `test_enter.py`. They live in `test_enter_cli.py` and pass. The spec also names `test_enter_prose.py` alone in release-checks, and it lists those extra files too | skills/run-autopilot/cli/test_enter_cli.py:67 | general | BLAKE |

### Mechanical checks (computed)

- **Tautological test shapes**: 176 test functions checked across 8 test files, **no `[MECH]` findings**. No constant assert, self-comparison, `A or B` hedge, swallowed exception, `raises(Exception)`, or assertion-free test.
- **Fail-first replay against `20b4b0205d11`**: 139 touched tests ran, **88 failed against base, 51 passed**, 0 files uncollectable. The 51 passing tests produced the six `[MECH]` rows absorbed into the table above. Read them with the block's own caveat: the base here is cycle 1's HEAD, where `cli.enter` already existed and worked, so a rework cycle's *strengthened* pins and *coverage backfills* legitimately pass against it. `test_shared_lift.py`'s 16 are the clearest case — task 9 wrote them before the lift precisely to prove the refactor preserved behaviour, so passing at base is the property they assert. `test_enter_prose.py::test_every_stop_value_has_a_row` is the one worth keeping in view: it passes at base because it checks row *existence*, not routing *correctness*, which is exactly the gap High row 2 re-raises.
- **File line counts**: `enter.py` 414 (PRD limit 400 — over by 14); `__main__.py` 1198, down from 1289 at cycle 1 because task 9's lift moved code out, still over the 800 limit (settled deferral); `test_enter.py` 774, `test_enter_prose.py` 600, `test_enter_decisions.py` 614, `test_frontmatter.py` 465, `test_enter_guards.py` 437, `test_shared_lift.py` 425 — all under 800.
- **Function line counts** were taken from the computed `ast` facts block; no function in the diff exceeds the 50-line limit.
- **Carried-forward checks**: cycle 1's queue (`-checks-1.json`) holds one entry, `bash dev/bin/release-checks`, with `result.exit` 0. It passed, so it yields no cycle-2 finding.

## Alice

6 findings, above (3 🟡, 3 ⚪). She verified cycle 1's consolidated findings one by one and reports every one resolved in code, prose or tests except the residues she raised: the traceback guards (move, design read, skip write, `pause_reason` write, `catchup_mode` write, unmapped `do_park` code, shallow `--prds`), the `--prd` basename check, warnings on stderr with stdout still exactly eleven keys, the completed lift with orphan helpers deleted and the `selection.py` docstring corrected, the three stop-table rows, the restored obligations (STALLED banner, custody line, exit-code table, Active Work read), all five enter test files wired into release-checks, the anchored first-cell stop-table test, the awk drift guard, the real `_git_head_sha` tests, the plain `handoff.MARKERS` import, the `_park` branch collapse, the `batch_init` partial-batch prose, and the clear-markers forensics line.

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

11 findings, above, from the PRD alone (2 🟠, 3 🟡, 6 ⚪). Four were auto-dismissed against the ledger; a fifth (the `stop` vocabulary) is the same settled scope-creep discard re-raised at a different citation and is recorded as a cycle-2 settled deferral rather than a new defect.

Verification he ran: the enter, prose, cli, guards and decisions test files gave 180 passed; `bash dev/bin/release-checks` printed every stage green including `[checks] enter`, though he notes he did not observe its final exit status.

He confirmed as spec-matching: the 11 output keys with `warnings` popped to stderr, exit 2 for corrupt state and exit 6 for a future schema from the shared preflight, the step order, custody behaviour in and out of the loop, the batch absent/closed check, the lane stop after the frontmatter write, the catchup three-condition logic including the 00209 `force` rule, the design path and its section-scoped regex port, the prose section's position directly after the session-brief paragraph, the `SKILL.md` sentence, and the CHANGELOG entry.

Blake's B-rubric fails remain dominated by deviations the design doc explicitly approved and which he cannot see by construction.

B1: fail
B2: pass
B3: fail
B4: pass
B5: pass
B6: fail
B7: fail
B8: pass
B9: pass
B10: pass
B11: pass
B12: pass
B13: pass
B14: pass
B15: fail
B16: pass
B17: pass
B18: pass
B19: pass

## Bob

3 findings, above (1 🟠, 2 🟡), carrying the doubt + de-slop lens. Ran on codex, exit 0, first run, no retry.

R1: fail
R2: pass
R3: pass
R4: fail
R6: pass
R7: pass
R8: pass
R9: fail
R10: pass
R11: pass
R12: pass
R13: fail

FIX / VERIFY / KNOWN buckets:

```
FIX:
- Design-document read failure has the wrong `fs_error` route — skills/run-autopilot/references/phase-build.md:29 — add a `detail` branch directing it to the design gate's failure handler.
- Frontmatter warnings disappear on a failed write — skills/run-autopilot/cli/enter.py:297 — pass a warning collector to `frontmatter.apply` and retain those lines on the stop result.
- `enter.py` exceeds its PRD limit by 14 lines — skills/run-autopilot/cli/enter.py:2 — shorten restating docstrings to bring it below 400 lines.

VERIFY:
- (none)

KNOWN:
- `__main__.py` remains over 800 lines — pre-existing CLI registry debt explicitly deferred outside this PRD.
```

D1: pass
D2: pass
D3: pass
D4: pass
D5: pass

Bob's VERIFY bucket is empty, so **no verification-check queue was written for cycle 2** (no `-checks-2.json`). An absent queue file means no checks and is never an error.

## Carl

1 finding, above (🟡 — the same 414-line breach), on backend `copilot` / model `gemini-3.8-flash`. He named a concrete fix the others did not: inlining the single-caller `_prepare_tree` into `_bootstrap` brings the file under the limit.

He ran `env -u AUTOPILOT_DISPATCH_DEPTH -u COPILOT_CLI -u _AUTOPILOT_LOOP bash dev/bin/release-checks` (the nested-dispatch unset that cycle 1 established) and it completed green. His TODO/FIXME/breakpoint/pdb sweep over the diff returned no matches.

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

## Follow-up Tasks Created

**None — this is the cap cycle.** `state.cycle` is 2 and `rework_cap` is 2, so `cycle >= rework_cap`: the Phase 5 cap check routes this cycle to the loop-mode cap-out, which has no rework pass and no tail sweep. Creating `[D2]` tasks here would leave pending tasks at finalize and contradict the gate that just declined to dispatch them. Recorded as an autonomous decision rather than silently skipped.

The two unresolved 🟠 High findings are recorded as `cap-overflow` entries in `state.deferred_decisions` and surface at batch-end review. Every Medium and Low finding is recorded in the consolidated table above, which lives in `dev/local/reviews/` and is never deleted by cleanup.

## Settled decisions (ledger)

Ten entries now in `dev/local/reviews/00223-enter-the-build-gate-in-one-cli-call-v1-ledger.json` — the eight from cycle 1, plus two written this cycle:

1. **settled-deferral, high** — Blake's `stop`-vocabulary re-raise (enter.py:29). The same design-approved scope-creep discard as cycle 1, re-cited at a different file:line so the mechanical dismissal missed it. Its one new sub-claim, that mapping park exit 2 is invented, was checked and refuted: `_PARK_STOPS[2]` is `park_precondition_failed` (enter.py:62-66), one of the five design-approved values, and phase-build.md:35 documents its routing.
2. **discarded, medium** — the `test_shared_lift.py` replay row. Passing against the pre-change code is that file's purpose: task 9 wrote it before the lift to prove the refactor preserved behaviour, and the replay block's own caveat covers exactly this case.

### Auto-dismissed (ledger)

These four Blake findings matched a settled entry and were excluded from the table and from task creation:

- [BLAKE] 🟡 Extra CLI flag `--prds`. The spec's inputs are only `--state`, `--prd` and `_AUTOPILOT_LOOP`. | File: skills/run-autopilot/cli/__main__.py:296 — Design-approved, and the PRD itself says the design doc may rename but not drop keys. The design doc's `STOPS` tuple lists all five extra values, its step chain defines the state bootstrap, the stall_op precheck and the skipped write, and `_add_enter` declares `--prds` verbatim. selection.py and frontmatter.py are the two lifts the task mandates. Blake is PRD-only by construction and could not see any of it.
- [BLAKE] ⚪ `batch` is null on every stop before step 8, but the spec types it as `"open"|"absent"|"closed"` only. | File: skills/run-autopilot/cli/enter.py:49 — Design-approved with a written rationale: `batch` carries `|null` because four earlier steps can stop before step 9 evaluates it, and "absent" is a load-bearing checked condition that must not double as "this step never ran".
- [BLAKE] ⚪ `detail` for park exit 5 is a synthesized string. | File: skills/run-autopilot/cli/enter.py:175 — Design-approved: the captured text "carries nothing enter() doesn't already derive from the exit code and its own pre-call marker read, so it is discarded, not forwarded", and the contract spells out the synthetic detail for exit 5.
- [BLAKE] ⚪ `enter()`'s signature differs from the spec's `enter(state_path, prd_arg, in_loop, now)`. | File: skills/run-autopilot/cli/enter.py:366 — Design-approved. The design doc carries the exact signature the code implements, and the task description copied it verbatim as the contract.

Verdict: 18 findings
Tests: 1946 passed, 0 failed, 0 skipped (reused from last-verification.json at 319343c31b9c8ccc3f3571038e13b43518d715e5; the work phase's own mandatory run at this exact HEAD recorded `uv run --no-project --with pytest python -m pytest -q cli/` exit 0 and `bash dev/bin/release-checks` exit 0, so no suite was re-run this cycle)
