---
prd: dev/local/prds/wip/00187-keep-cap-out-criticals-off-master-and-home-deferred-highs-v1.md
review: 2
date: 2026-09-14
head_sha: d67205b93f7f3df628f58415e64535af544e1375
codex_thread_id: 01a09e3d-b594-7103-a053-7618edc2a3a7
reviewers: alice,blake,bob,carl
agents:
  alice: available
  blake: available
  bob: available
  carl: available
---

# Review: 00187-keep-cap-out-criticals-off-master-and-home-deferred-highs-v1

Diff range: `1fda59631b9cc17ced374846d838185e5b79532d..d67205b93f7f3df628f58415e64535af544e1375`

codex_rung_guard: not fired

pack: failed (`engram pack` exits 1 deterministically here — "not inside a registered repo; register it in /Users/bob/.config/gita/repos.csv" — same as cycle 1; not retried). `{PACK_FILE}` and `{PACK_FINDINGS}` were substituted with the literal `(no pack available this cycle)`. Registering `claude-autopilot` in gita would restore the pack.

scope note: cycle 2, incremental review of the cycle-1 rework — 11 commits, 13 files, +1138/-334 since the cycle-1 `head_sha` (`gather-context.sh --since 1fda596…`). The review-cycle session that first ran this cycle (06:35–06:53) died with `state.json` untouched after staging every input and dispatching Bob and Carl; the loop relaunched. This session verified and reused that session's staging files (`dev/local/tmp/*-00187c2.*`: context, diff, mechanical blocks, PRD, task table, the four prompts — all built at this same HEAD), re-measured the replay correction below, re-dispatched Alice, Blake and Carl, and reused Bob's codex output (see the bob note). Blake stayed blind: PRD and rubric only, no filesystem-notes block (`dev/local` is a real directory; the root has no dot prefix).

bob note: codex is back within quota (the cycle-1 `usage_limit_exceeded` cleared). The prior session's dispatch (`codex-run.sh -f bob-prompt-00187c2.md -o bob-output-00187c2.txt --emit-thread-id …`, thread `01a09e3d-b594-7103-a053-7618edc2a3a7`, rollout 06:47–06:50) produced a complete review at this HEAD — three issue lines, FIX/VERIFY/KNOWN buckets, twelve `R` and five `D` verdict lines — so it was consolidated as-is rather than re-dispatched (same prompt, same diff, same HEAD; a re-run would spend credits for no new information). Its dispatch ledger row (`6704cf00`) was closed `ok` by this session. `codex_thread_id` is stamped from `bob-thread-00187c2.txt`.

carl note: backend `copilot`, model `gemini-3.8-flash`, exit 0, non-empty output (dispatch row `50dfc610`; the prior session's row `da6b56ca` was closed as an error — session died before exit). Carl ran the cli and hooks suites and `release-checks` (twice, once with the host dispatch markers unset). Fail loud: mid-review he also read `dev/local/tmp/bob-output-00187c2.txt` and the orchestrator's probe script `dev/local/tmp/00187-c2-guard-probe.py` and ran the probe, so his agreement on the wrapper-bypass row is corroborated (he executed the reproduction) but not independent of Bob's wording. The row is still real: the orchestrator reproduced it first (see the Decision gate).

verification queue: none written this cycle. Bob emitted three FIX items, `VERIFY: - (none)` and `KNOWN: - (none)`, so there is nothing to queue.

## Review Summary

Reviewed: 12 completed tasks (5 `[D1]` rework tasks 8–12 in this cycle's diff; original-plan tasks 1–7 reviewed in cycle 1)
PRDs checked: 00187-keep-cap-out-criticals-off-master-and-home-deferred-highs-v1

### Agent Status

- Alice: ✅ Available (Claude subagent, sonnet; verified all 12 reworked findings resolved, re-ran the hook suites (44 passed, 169 subtests) and the 8-suite custody block (121 passed, 86 subtests))
- Blake: ✅ Available (Claude subagent, sonnet, blind/PRD-only; ran custody + hook suites and the full `release-checks`, all green)
- Bob: ✅ Available (codex, thread `01a09e3d…`; output from the prior session's dispatch at this HEAD, reused)
- Carl: ✅ Available (gemini-run backend=copilot model=gemini-3.8-flash, exit 0)

## Consolidated Findings

10 findings: 4 rows from `consolidate_findings.py` (the `--ledger … --ledger-dismiss BLAKE` run; Blake raised nothing, so the auto-dismissed section is empty) plus the 6 `[MECH]` fail-first-replay lines absorbed as their own rows (`Found by: mech-check`; the tautological-shapes block was empty). No 🔴 Critical, no 🟠 High; **3 🟡 Medium from the reviewers**, 1 ⚪ Low, and 6 🟡 mechanical rows the decision gate discards with measured reasons below. All 12 cycle-1 reworked findings were confirmed resolved by Alice (each traced to its commit) and Carl; Blake passed all nineteen B rules with no finding.

| Consensus | Severity | Issue | File | Task | Found By |
|-----------|----------|-------|------|------|----------|
| [2/4] | 🟡 Medium | Wrapper bypass remains: `env -u git git push` unwraps to `git git push`; the parser sees subcommand `git`, and `exe != "git"` suppresses fallback, allowing a push from a guarded cwd. No test covers this collision. (Carl: same for `sudo -u git git push`) | hooks/guard_push_on_critical.py:254 | 10 | Bob, Carl |
| [1/4] | 🟡 Medium | Flag-free wrappers now cause false denials: `command echo 'git' 'push'` becomes uncertain solely because `wrapped=True`, contradicting the requirement to allow quoted echo arguments. | hooks/guard_push_on_critical.py:254 | 10 | Bob |
| [1/4] | 🟡 Medium | Redundant prose assertions: interactive-cell presence already guarantees row presence, and excluding `custody resolve` from the loop cell already excludes the full custody sentence. Remove the weaker duplicate checks. | skills/run-autopilot/cli/test_custody_prose_schema.py:284 | 8 | Bob |
| [1/4] | ⚪ Low | custody.marker_entry() is built twice with identical inputs in the do_stall step-4b path (once inside custody.record_critical, again in records._record_stall_custody right after) instead of threading the single built entry through; harmless since the builder is pure, but redundant | skills/run-autopilot/cli/records.py | 11 | Alice |
| [1/4] | 🟡 | Fail-first replay: 9 touched test(s) pass against the pre-change code: test_lone_ampersand_and_pipe_ampersand_split_segments, test_parentheses_are_separators_in_their_own_right, test_splits_at_unquoted_separators_and_keeps_quoted_ones, test_unterminated_quote_is_malformed, test_dollar_or_backtick_in_a_location_or_subcommand_marks_the_call_unresolved, test_resolves_the_git_call_and_its_global_options +3 more | hooks/test_guard_push_grammar.py | general | mech-check |
| [1/4] | 🟡 | Fail-first replay: 2 touched test(s) pass against the pre-change code: test_hidden_push_denies_only_when_the_payload_cwd_has_custody, test_bash_matcher_registers_the_guard_once_beside_enforce_prd_location | hooks/test_guard_push_on_critical.py | general | mech-check |
| [1/4] | 🟡 | Fail-first replay: 2 touched test(s) pass against the pre-change code: test_invents_no_default_for_a_missing_capture_key, test_returns_exactly_the_nine_keys_with_scalars_and_capture_as_given | skills/run-autopilot/cli/test_custody_entry.py | general | mech-check |
| [1/4] | 🟡 | Fail-first replay: 4 touched test(s) pass against the pre-change code: test_a_successful_stall_prints_nothing_to_stderr, test_load_marker_raises_custody_error_for_an_entry_without_a_string_op_id, test_rows_without_a_string_op_id_raise_custody_error_never_key_or_type_error, test_collapses_every_whitespace_run_in_the_detail_to_one_space | skills/run-autopilot/cli/test_custody_loud.py | general | mech-check |
| [1/4] | 🟡 | Fail-first replay: 1 touched test(s) pass against the pre-change code: test_pending_custody_handler_pauses_when_custody_state_is_unreadable | skills/run-autopilot/cli/test_custody_prose.py | general | mech-check |
| [1/4] | 🟡 | Fail-first replay: 1 touched test(s) pass against the pre-change code: test_unreadable_mirror_exits_9_with_the_custody_already_closed | skills/run-autopilot/cli/test_custody_resolve.py | general | mech-check |

### Auto-dismissed (ledger)

(none — Blake raised no finding this cycle)

### Decision gate (Phase 5)

No unresolved 🔴/🟠 → **converged at cycle 2** (`autopilot gate --assert-constraint-met` exit 0 recorded below). The Medium/Low tail is swept, not dropped: one `[D2]` task through the tail-sweep path, then the finalize hand-off. Every decision is in `state.autonomous_decisions`; the discards are appended to `00187-keep-cap-out-criticals-off-master-and-home-deferred-highs-v1-ledger.json`.

- **Swept (3 findings → 1 `[D2]` task, tier opus via the PRD's `default_model` floor):** the two guard findings and the redundant prose asserts. The orchestrator reproduced both guard findings before deciding (`dev/local/tmp/00187-c2-guard-probe.py`): `env -u git git push` and `sudo -u git git push` → `is_push_like False`, `parse_git_call` subcommand `'git'` → allowed (a false allow, the class the docstring promises never happens); `command echo 'git' 'push'` → `is_push_like True` → denied from a guarded cwd (a false deny on a PRD-listed pass case). One rule closes both: a wrapper that consumed any `-flag` makes the segment uncertain (its operand may have been the executable), while a flag-free wrapper classifies the executable it exposes normally. The prose-assert redundancy was confirmed by reading `test_custody_prose_schema.py:274-294` against `_PUSH_DENIAL_SENTENCE` (it contains `custody resolve`, so line 291 implies line 284; line 280 implies line 274).
- **Discarded (1 Low, reason in the ledger):** the second `marker_entry` build. `record_critical`'s signature is the design's verbatim contract (keyword-only inputs, `-> int | None`); threading the entry means changing that interface to save one pure five-key dict build. Not worth an interface change.
- **Discarded (6 mechanical rows, reasons in the ledger, measured this session):** the replay script reads pytest's `-rA` summary, and this pytest (native subtests) reports a `unittest.subTest` failure as a separate `SUBFAILED` line while the parent test still prints `PASSED`. Re-run in a base worktree at `1fda596` with HEAD's test files overlaid: **7 of the 19 flagged tests FAIL at base** (`test_flags_commands_that_could_run_a_push_the_parser_cannot_see`, `test_hidden_push_denies_only_when_the_payload_cwd_has_custody`, both `MarkerEntryBuilderTests` (AttributeError: no `marker_entry`), `test_load_marker_raises_custody_error_for_an_entry_without_a_string_op_id`, `test_rows_without_a_string_op_id_raise_custody_error_never_key_or_type_error`, `test_collapses_every_whitespace_run_in_the_detail_to_one_space` — pytest exit 1, SUBFAILED on the sudo/nice/env, quote-split, op_id and whitespace cases). The 12 that genuinely pass are structural: 8 grammar tests moved byte-for-byte into `test_guard_push_grammar.py` by task 10's style split plus the pre-existing registration test (a refactor split passes by design), `test_a_successful_stall_prints_nothing_to_stderr` (a preservation pin), `test_pending_custody_handler_pauses_when_custody_state_is_unreadable` (task 12 tightened a loose pin over unchanged, already-correct prose) and `test_unreadable_mirror_exits_9_with_the_custody_already_closed` (task 12 backfilled coverage of an existing branch). The subtest blind spot belongs to `replay_tests_against_base.py`, outside this PRD's diff.
- **Settled deferral, not re-raised:** `__main__.py` over the 800-line cap (Alice R13 fail, Bob R13 fail) — already in `state.deferred_decisions` from cycle 1.

## Follow-up Tasks Created

One `[D2]` tail-sweep task (opus; classifier default `sonnet` raised by the PRD's `default_model: opus` floor), covering the 3 swept findings; `state.rework_task_ids = ["13"]`. Phase 5 does not reopen after convergence: the sweep runs, then the PRD finalizes.

1. Task 13 — [D2] Tail sweep: close the wrapper-operand `git` bypass and the flag-free wrapper false deny in the push guard; drop the two redundant asserts in the Git-push-fails prose pin (S) - 🟡 Medium - 3 findings

Sweep result (same session): task 13 completed - tests e83033c (Tess + one Devon strengthen round; Devon's round cap left two structural table weaknesses flagged in `dev/local/meta/assumptions.md` § 13), fix e718214 (`_unwrap` reports a consumed `-` option as `hidden`; `is_push_like` returns True on it; flag-free wrappers are looked through). Pat: three CLOSURE resolved, NO FINDINGS. Final verification at e718214: `release-checks` exit 0; 1854 passed / 0 failed / 1 skipped across the four pytest directories (`dev/local/tmp/00187-rework-cycle-2-phase-report.md`). No verify-escapes (no checks-2 queue) and no sweep-escapes.

## Alice

Consensus lens, Claude subagent (sonnet). She traced every one of the 12 reworked findings to its commit and confirmed each resolved (SKILL.md cell move and the cell-index pins; the exit-9 stderr line; the `wrapped` flag and the quote-normalised push gate, hand-traced on `sudo -u NAME`, `nice -n 10`, `env -u VAR`, `sh -c 'git pu""sh'`; the single `marker_entry` builder and why `mock.patch.object` intercepts both call sites; the `_ranged_stall_record` rename; `MirrorStaleTests` and `_cleanup`'s write order; the exit-9-offset PAUSE pin; `_validate_mirror` gone; the eight-suite `release-checks` block, which she re-ran; string `op_id` validation; whitespace-collapsed `detail`). She found the `test_guard_push_grammar.py` split clean (no orphaned helpers) and accepted the orchestrator's replay correction. 1 ⚪ Low.

```
[ALICE] ⚪ custody.marker_entry() is built twice with identical inputs in the do_stall step-4b path (once inside custody.record_critical, again in records._record_stall_custody right after) instead of threading the single built entry through; harmless since the builder is pure, but redundant | File: skills/run-autopilot/cli/records.py | Task: 11

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
R13: fail
```

## Blake

Blind lens, Claude subagent (sonnet), PRD and rubric only. He located and read `custody.py`, `records.py`, `__main__.py`, `render_report.py`, the guard, `hooks.json`, the reference prose and the CHANGELOG; confirmed the `do_stall` step order, retry reuse of `op_id`/capture, the pre-reset migration with dedup, the guard's grammar and conservative fallback, the byte-identical roster sentence (via `git show`), no references to 00194/00195, and the best-effort `notify()`; ran the custody + hook suites and the full `release-checks` (green). He judged the marker entry's three extra keys (`branch`, `repo_root`, `git_dir`) licensed by the PRD's "reviewed design fixes internal argument shapes" clause. No finding.

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

Doubt + de-slop lens, codex (thread `01a09e3d-b594-7103-a053-7618edc2a3a7`, static read-only sandbox), output from the prior session's dispatch at this HEAD (see the bob note). 3 🟡 Medium, all three filed as FIX with concrete fixes; no VERIFY, no KNOWN. His R1/R7/R9 fails map to the untested wrapper-operand collision, the false allow it causes, and the `command echo 'git' 'push'` false deny against the PRD's pass list; R13 is the settled `__main__.py` deferral. Verbatim output:

```
[BOB] 🟡 Wrapper bypass remains: `env -u git git push` unwraps to `git git push`; the parser sees subcommand `git`, and `exe != "git"` suppresses fallback, allowing a push from a guarded cwd. No test covers this collision. | File: hooks/guard_push_on_critical.py:254 | Task: 10
[BOB] 🟡 Flag-free wrappers now cause false denials: `command echo 'git' 'push'` becomes uncertain solely because `wrapped=True`, contradicting the requirement to allow quoted echo arguments. | File: hooks/guard_push_on_critical.py:254 | Task: 10
[BOB] 🟡 Redundant prose assertions: interactive-cell presence already guarantees row presence, and excluding `custody resolve` from the loop cell already excludes the full custody sentence. Remove the weaker duplicate checks. | File: skills/run-autopilot/cli/test_custody_prose_schema.py:284 | Task: 8

FIX:

- Wrapper bypass — hooks/guard_push_on_critical.py:254 — Track unresolved wrapper options explicitly; retain uncertainty when an option operand equals `git`. Add guarded/clean fixtures for `env -u git git push`.
- Harmless wrapper denial — hooks/guard_push_on_critical.py:254 — Preserve normal executable classification after fully understood wrappers; add an allow fixture for `command echo 'git' 'push'`.
- Redundant prose checks — skills/run-autopilot/cli/test_custody_prose_schema.py:284 — Keep interactive-cell presence and loop-cell command exclusion; remove row-wide presence and full-sentence loop exclusion.

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
R13: fail

D1: pass
D2: pass
D3: pass
D4: pass
D5: pass
```

## Carl

Frontend & design specialist, generalist here (no UI surface). Backend `copilot`, model `gemini-3.8-flash`, exit 0. He read the context and the whole diff, checked the hook test split for overlap and lost lines (none), the exit-9 path in `custody.py`, the `release-checks` block, the prose pins; ran the cli and hooks suites and `release-checks` twice; searched the diff for debug markers, TODOs and stray prints (none). He confirmed all 12 reworked findings resolved and raised the wrapper-operand bypass (reproduced by running the orchestrator's probe — see the carl note). 1 🟡 Medium; R9 fail for it.

```
[CARL] 🟡 Wrapper bypass remains when option operand is git: sudo -u git git push and env -u git git push unwrap with exe="git" and subcommand="git", evading both the push check and wrapper fallback, allowing push from a guarded cwd | File: hooks/guard_push_on_critical.py | Task: 10

R1: pass
R2: pass
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
```

## Mechanical checks

- **Mechanical facts**: computed from `ast` over the 13 changed files (11 Python) and appended to the reviewer context; no reviewer contradicted the block.
- **Tautological test shapes**: 107 test functions checked in 7 files, **0 `[MECH]` findings**.
- **Fail-first replay**: 35 touched tests ran against `1fda596`; 16 failed at base, 19 reported passing across 6 `[MECH]` lines — absorbed as rows above and discarded at the gate after the orchestrator's own base-worktree re-run showed 7 of the 19 are `SUBFAILED` at base (the replay script's parent-`PASSED` blind spot) and the other 12 are refactor-move, preservation or backfill pins.

Verdict: 10 findings

Tests: 1854 passed, 0 failed, 1 skipped (reused from last-verification.json at d67205b93f7f3df628f58415e64535af544e1375)
