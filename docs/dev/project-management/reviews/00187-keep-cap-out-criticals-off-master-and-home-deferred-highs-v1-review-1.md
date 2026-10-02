---
prd: dev/local/prds/wip/00187-keep-cap-out-criticals-off-master-and-home-deferred-highs-v1.md
review: 1
date: 2026-09-14
head_sha: 1fda59631b9cc17ced374846d838185e5b79532d
reviewers: alice,blake,bob,carl
agents:
  alice: available
  blake: available
  bob: available
  carl: available
---

# Review: 00187-keep-cap-out-criticals-off-master-and-home-deferred-highs-v1

Diff range: `2c922c38b30dcf78676e6f4f2a3482dd299cc288..1fda59631b9cc17ced374846d838185e5b79532d`

codex_rung_guard: not fired

pack: failed (`engram pack` exited 1 — "not inside a registered repo; register it in /Users/bob/.config/gita/repos.csv"; the registry lists 18 buvis repos and not this one, so the error is deterministic and no retry was spent). `{PACK_FILE}` and `{PACK_FINDINGS}` were substituted with the literal `(no pack available this cycle)` in every prompt that takes them. The review is degraded by the missing retrieval context, not invalid. Registering `claude-autopilot` in gita would restore the pack for later cycles.

scope note: cycle 1, full review of the PRD's whole work range (23 commits, 26 files, +5986/-143). `gather-context.sh` with no `--since` produced an empty diff again (its default diffs against `master`, and the batch works on `master`), so the run was redone with `--since 2c922c38…` (`state.work_start_sha`) and the scope label corrected by hand. Blake stayed blind: PRD and rubric only, no filesystem-notes block (`dev/local` is a real directory and the root has no dot prefix). Reviewers were told to run suites per directory (`dev/local/tmp/render-pin-check/` breaks root-level collection).

bob note: codex is out of quota — `codex-run.sh` exited 1 on the first dispatch and on the one retry, both with `codex_error_info: usage_limit_exceeded` ("try again at Sep 20th, 2026 11:10 AM"; the `~/.codex/sessions` rollout shows a `codex exec` from `~/.config/autocodex/driver.py` every five minutes all night, which is where the credits went). The wrapper mapped it to exit 1, not 4, so the retry policy's plain-exit retry ran once before the fallback. No sidecar output existed to salvage. Bob's exact assembled doubt prompt (issue lines, R rubric, FIX/VERIFY/KNOWN buckets, D rubric) ran on a Claude subagent (`autopilot:bob`, Read only), so the doubt + de-slop lens did not drop. No `codex_thread_id` is stamped: the thread ids captured belong to the two failed turns and resuming one would resume nothing. Every later cycle of this PRD, and every PRD in this batch until the reset, will take the same fallback.

verification queue: none written this cycle. Bob (fallback) emitted FIX and KNOWN buckets and an explicit `VERIFY: - (none)`, so there is nothing to queue.

## Review Summary

Reviewed: 7 completed tasks
PRDs checked: 00187-keep-cap-out-criticals-off-master-and-home-deferred-highs-v1

### Agent Status

- Alice: ✅ Available (Claude subagent, sonnet; ran the custody, hook, prose, render and records suites plus `bash dev/bin/release-checks` herself: 68 + 94 passed, exit 0)
- Blake: ✅ Available (Claude subagent, sonnet, blind/PRD-only; ran 99 custody + 44 hook tests and `release-checks`, all green)
- Bob: ✅ Available (Claude fallback subagent carrying the codex doubt + de-slop prompt; codex itself exit 1 ×2, `usage_limit_exceeded`)
- Carl: ✅ Available (gemini-run backend=copilot model=gemini-3.8-flash, exit 0, 12 KB output; ran the custody/hook/cli suites and `release-checks` twice, once with the host dispatch markers unset)

## Consolidated Findings

18 findings: 19 rows from `consolidate_findings.py` with the two `__main__.py`-over-800-lines rows (Alice and Bob, different wording, different path forms) merged into one `[2/4]` row, plus the fail-first replay's one `[MECH]` line absorbed into Bob's matching row (`mech-check` added as a finder). No 🔴 Critical; **one 🟠 High** (Bob, 1/4, confirmed by the orchestrator at `SKILL.md:297`); 5 🟡 Medium; 12 ⚪ Low. The script merged Alice's and Bob's `_stall_range` and PAUSE-pin rows across path forms; Bob's absolute `File:` paths are shown repo-relative below.

Alice and Carl passed the implementation on every rubric rule except Alice's R13 (`__main__.py` at 1008 lines, over the cap it already broke at 909). Blake passed all nineteen B rules and found one Low. The doubt lens carried the weight: Bob's 16 issue lines are where the one High and four of the five Mediums come from.

| Consensus | Severity | Issue | File | Task | Found By |
|-----------|----------|-------|------|------|----------|
| [1/4] | 🟠 High | SKILL.md "Git push fails" row puts the custody sentence in the LOOP-MODE cell, so an unattended session hitting the guard is told "resolve it with autopilot custody resolve" (needs a --choice it must invent); this contradicts phase-build.md § Handle pending custody ("neither asks nor runs custody resolve") and the PRD ("Loop mode only prints ... and continues", "no Git mutation from loop-mode resumption"); the Interactive cell carries no pointer at all | skills/run-autopilot/SKILL.md | 5 | Bob |
| [2/4] | 🟡 Medium | __main__.py is 1008 lines (was 909 pre-PRD; +99 from this diff), past the project's 800-line file cap; check_style_limits.py deliberately doesn't flag pre-existing overflow and defers it to review. Consider extracting the custody subcommand (_add_custody/_run_custody) into its own module. / __main__.py is 1009 lines, over the 800-line cap; it was already over before this PRD and the diff grew it by roughly 110 net lines (custody verb, _stall_range, render split) | skills/run-autopilot/cli/__main__.py | general | Alice, Bob |
| [1/4] | 🟡 Medium | record_critical swallows the failure reason: `except (OSError, ValueError, CustodyError): return 9` prints nothing, and do_stall/_run_stall add nothing, so a cap_critical exit 9 (seven distinct writes: migration record_defer, marker, journal, git config, hold read, hold write) reaches the operator with an empty stderr; recovery.md's `9` row then pauses with no diagnosable detail | skills/run-autopilot/cli/custody.py | 1 | Bob |
| [1/4] | 🟡 Medium | Guard docstring claims "Every limit errs toward a false deny, never a false allow", but `sudo -u NAME git push`, `nice -n 10 git push`, `env -u VAR git push` unwrap to exe `NAME`/`10`/`VAR` (not git, not in _PUSH_CAPABLE, no `$`), so parse_git_call is None and is_push_like is False: allowed from a guarded cwd | hooks/guard_push_on_critical.py | 2 | Bob |
| [1/4] | 🟡 Medium | _record_stall_custody rebuilds the same 9-key marker entry that custody.record_critical already builds internally (two places must agree on the entry shape the guard and resolve read) | skills/run-autopilot/cli/records.py | 1 | Bob |
| [1/4] | 🟡 Medium | _cleanup's `mirror stale, custody closed` exit-9 branch (state.transaction failing after the ledger record landed) is documented in the CLI exit table and state-schema.md but has no test; the assumptions ledger admits it | skills/run-autopilot/cli/test_custody_resolve.py | 3 | Bob |
| [2/4] | ⚪ Low | test_pending_custody_handler_pauses_when_custody_state_is_unreadable computes the exit-9 offset via _exit_code() but discards it, then asserts PAUSE/site: "sub_skill_fail" over the whole custody section rather than after that offset — looser than sibling tests in the same file (flagged by Pat in the work-phase ledger, deferred here) | skills/run-autopilot/cli/test_custody_prose.py | 4 | Alice, Bob |
| [2/4] | ⚪ Low | _stall_range returns the whole matched stall-record dict, not a range value; the name suggests a narrower return type (flagged by Pat in the work-phase ledger, deferred here) | skills/run-autopilot/cli/__main__.py | 6 | Alice, Bob |
| [1/4] | ⚪ Low | custody._validate_mirror is a single-caller one-line wrapper around schema.require (flagged by Pat in the work-phase ledger, deferred here) | skills/run-autopilot/cli/custody.py | 3 | Alice |
| [1/4] | ⚪ Low | Custody CLI test suites (test_custody.py, test_custody_prose.py, test_custody_prose_schema.py, test_custody_resolve.py, test_custody_stall.py, test_render_custody.py) are not invoked by dev/bin/release-checks; only hooks/test_guard_push_on_critical.py was registered there, so a future regression in cli/custody.py or its integration would not fail the release gate even though it passes standalone today. | dev/bin/release-checks | general | Blake |
| [1/4] | ⚪ Low | custody.pending() and _live_rows index `e["op_id"]` / `r["op_id"]`; load_marker only checks entries are dicts, so a marker entry or journal row without op_id raises KeyError (uncaught by _run_custody, traceback exit 1) instead of CustodyError exit 9 | skills/run-autopilot/cli/custody.py | 1 | Bob |
| [1/4] | ⚪ Low | stalled_section hardcodes "live on master" although the stall record carries `branch` (a trunk/topic-branch custody renders a wrong report line); the PRD and design text mandate this literal | skills/run-autopilot/cli/render_report.py | 6 | Bob |
| [1/4] | ⚪ Low | _refresh_block scans 20 head lines while frontmatter._HEAD_LINES is now 22: a block closing on line 21-22 parses before the refresh, then gets a second block prepended and its original keys drop out of frontmatter.parse (needs 19+ keys; design-specified bound) | skills/run-autopilot/cli/custody.py | 1 | Bob |
| [1/4] | ⚪ Low | Fail-first replay: 5 test_render_custody tests pass against base (range-less byte-identity pins) — the replay block rates the same fact 🟡 | skills/run-autopilot/cli/test_render_custody.py | 6 | Bob, mech-check |
| [1/4] | ⚪ Low | records and custody import each other (`from . import custody` / `from . import records`); works only because attributes are accessed lazily inside functions | skills/run-autopilot/cli/custody.py | 1 | Bob |
| [1/4] | ⚪ Low | Guard worst case exceeds its 10s hooks.json timeout: up to 8 candidate cwds each running resolve_toplevel (5s) plus marker_from_locator (5s) | hooks/guard_push_on_critical.py | 2 | Bob |
| [1/4] | ⚪ Low | refresh_hold_prd idempotency breaks when `detail` contains a newline: the prefix match replaces only the notice's first line, so a retry duplicates the tail | skills/run-autopilot/cli/custody.py | 1 | Bob |
| [1/4] | ⚪ Low | is_push_like tests `"push" in segment` on the raw quoted segment while decide normalises quotes, so `eval "git pu''sh"` / `sh -c 'git pu""sh'` pass the push-like check | hooks/guard_push_on_critical.py | 2 | Bob |

### Decision gate (Phase 5)

Cycle 1 < rework cap 2, one 🟠 High unresolved → not converged → rework. Every decision is in `state.autonomous_decisions` / `state.deferred_decisions`; the discards and the one settled deferral are in `00187-keep-cap-out-criticals-off-master-and-home-deferred-highs-v1-ledger.json`.

- **Auto-fix, reworked (12 findings → 5 `[D1]` tasks):** the High (verified at `SKILL.md:297`: the sentence sits only in the loop-mode cell; the fix adds/relocates prose, no interface change), the four code/test Mediums (the swallowed exit-9 reason, the wrapper false allow and the duplicated entry construction confirmed by reading `custody.py:309`, `guard_push_on_critical.py:189-192`, `records.py:434-440`), and the seven Lows with a mechanical or additive fix (`_stall_range` rename, PAUSE-pin offset, `_validate_mirror` inline, op_id validation, multi-line detail, `is_push_like` normalisation, custody suites in `release-checks`).
- **Deferred to batch end (1):** `__main__.py` over the 800-line cap — pre-existing overflow (909 at `work_start_sha`); the lines this PRD added are design-mandated, and removing only them leaves the file over the cap. Recorded via `autopilot defer` as `review-deferral` for PRD minting (the same treatment `loop.py` got under 00192). Medium, so it does not block convergence.
- **Discarded (5 Lows, reasons in the ledger):** the `live on master` literal (PRD-mandated), the `_refresh_block` 20-line bound (design-specified; needs 19+ frontmatter keys), the five range-less replay pins (preservation pins pass at base by construction; the four with-range tests fail at base), the records/custody circular import (design-placed, lazy access), and the guard's theoretical >10s worst case (documented limit). Each was Bob's own KNOWN item with a written justification.

## Follow-up Tasks Created

Five `[D1]` tasks at tier `opus` (classifier default `sonnet` raised by the PRD's `default_model: opus` floor), covering 12 of the 18 findings; `state.rework_task_ids = ["8", "9", "10", "11", "12"]`.

1. Task 8 — Move the custody push-denial sentence to the interactive cell of the Git-push-fails row; loop cell defers to the attended Phase 0 (S) - 🟠 High - 1 finding
2. Task 9 — custody.py fail-loud and validation: print the exit-9 reason, require op_id, normalise multi-line detail, inline `_validate_mirror` (M) - 🟡 Medium - 4 findings
3. Task 10 — Push guard: close the wrapper false-allow (`sudo -u` / `nice -n` / `env -u`), normalise the segment before the push-like check (M) - 🟡 Medium - 2 findings
4. Task 11 — One `custody.marker_entry` builder for records.py and custody.py; rename `_stall_range` (S) - 🟡 Medium - 2 findings
5. Task 12 — Pin the mirror-stale exit-9 branch, scope the PAUSE prose pin, run the custody CLI suites in `release-checks` (M) - 🟡 Medium - 3 findings

## Alice

Consensus lens, Claude subagent (sonnet). She ran the touched suites and `release-checks` herself (all green), traced the implementation against the design contract "almost line-for-line", and confirmed list-form argv throughout (no injection surface). 1 🟡 Medium, 3 ⚪ Low; the Lows are the three items Pat had parked in the assumptions ledger for this review, each confirmed by reading.

```
[ALICE] 🟡 __main__.py is 1008 lines (was 909 pre-PRD; +99 from this diff), past the project's 800-line file cap; check_style_limits.py deliberately doesn't flag pre-existing overflow and defers it to review. Consider extracting the custody subcommand (_add_custody/_run_custody) into its own module. | File: skills/run-autopilot/cli/__main__.py | Task: general
[ALICE] ⚪ test_pending_custody_handler_pauses_when_custody_state_is_unreadable computes the exit-9 offset via _exit_code() but discards it, then asserts PAUSE/site: "sub_skill_fail" over the whole custody section rather than after that offset — looser than sibling tests in the same file (flagged by Pat in the work-phase ledger, deferred here) | File: skills/run-autopilot/cli/test_custody_prose.py | Task: 4
[ALICE] ⚪ custody._validate_mirror is a single-caller one-line wrapper around schema.require (flagged by Pat in the work-phase ledger, deferred here) | File: skills/run-autopilot/cli/custody.py | Task: 3
[ALICE] ⚪ _stall_range returns the whole matched stall-record dict, not a range value; the name suggests a narrower return type (flagged by Pat in the work-phase ledger, deferred here) | File: skills/run-autopilot/cli/__main__.py | Task: 6

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

Blind lens, Claude subagent (sonnet), PRD and rubric only. He located the code himself, read `custody.py`, `records.py`, `__main__.py`, `render_report.py`, the guard and its tests, the reference prose, CHANGELOG and release-checks, and ran 99 custody + 44 hook tests and `release-checks` (green). He found no functional gap, no scope creep and no missing error path, and rates the implementation "unusually complete against this dense, precisely-worded PRD". 1 ⚪ Low.

```
[BLAKE] ⚪ Custody CLI test suites (test_custody.py, test_custody_prose.py, test_custody_prose_schema.py, test_custody_resolve.py, test_custody_stall.py, test_render_custody.py) are not invoked by dev/bin/release-checks; only hooks/test_guard_push_on_critical.py was registered there, so a future regression in cli/custody.py or its integration would not fail the release gate even though it passes standalone today. | File: dev/bin/release-checks | Task: general
[BLAKE] ✅ No other issues found - implementation matches PRD 00187 in full: retry-stable capture/marker/journal/locator, hold-PRD refresh, deferred-decision migration with dedup, command-aware push guard grammar (command/absolute/env-assignment/-C/-c/--git-dir/--work-tree/compound/echo/read-only cases), attended resolve (revert/branch-and-revert/accept) with exit 5/9 contracts, stalled-report custody line, reference docs, CHANGELOG, and release-checks all verified by reading code and running the actual test suites (99 custody + 44 hook tests + full bash dev/bin/release-checks, all green).

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

Doubt + de-slop lens. Codex unavailable (exit 1 twice, `usage_limit_exceeded`), so the exact assembled codex prompt ran on a Claude subagent (`autopilot:bob`, Read tool only, static analysis). 1 🟠 High, 5 🟡 Medium, 10 ⚪ Low; eight FIX items, no VERIFY item, eight KNOWN items each with a written justification (the KNOWN items are the five discards above plus `__main__.py`'s size, which the gate deferred rather than discarded, and two Lows the gate reworked anyway because the fix is one line: multi-line `detail` and the `is_push_like` raw-segment check). His R1/R9/R10/R13 fails map to the mirror-stale branch untested, the SKILL.md cell contradiction, the swallowed exit-9 reason, and the file cap.

```
[BOB] 🟠 SKILL.md "Git push fails" row puts the custody sentence in the LOOP-MODE cell, so an unattended session hitting the guard is told "resolve it with autopilot custody resolve" (needs a --choice it must invent); this contradicts phase-build.md § Handle pending custody ("neither asks nor runs custody resolve") and the PRD ("Loop mode only prints ... and continues", "no Git mutation from loop-mode resumption"); the Interactive cell carries no pointer at all | File: skills/run-autopilot/SKILL.md | Task: 5
[BOB] 🟡 record_critical swallows the failure reason: `except (OSError, ValueError, CustodyError): return 9` prints nothing, and do_stall/_run_stall add nothing, so a cap_critical exit 9 (seven distinct writes: migration record_defer, marker, journal, git config, hold read, hold write) reaches the operator with an empty stderr; recovery.md's `9` row then pauses with no diagnosable detail | File: skills/run-autopilot/cli/custody.py | Task: 1
[BOB] 🟡 Guard docstring claims "Every limit errs toward a false deny, never a false allow", but `sudo -u NAME git push`, `nice -n 10 git push`, `env -u VAR git push` unwrap to exe `NAME`/`10`/`VAR` (not git, not in _PUSH_CAPABLE, no `$`), so parse_git_call is None and is_push_like is False: allowed from a guarded cwd | File: hooks/guard_push_on_critical.py | Task: 2
[BOB] 🟡 _record_stall_custody rebuilds the same 9-key marker entry that custody.record_critical already builds internally (two places must agree on the entry shape the guard and resolve read) | File: skills/run-autopilot/cli/records.py | Task: 1
[BOB] 🟡 _cleanup's `mirror stale, custody closed` exit-9 branch (state.transaction failing after the ledger record landed) is documented in the CLI exit table and state-schema.md but has no test; the assumptions ledger admits it | File: skills/run-autopilot/cli/test_custody_resolve.py | Task: 3
[BOB] 🟡 __main__.py is 1009 lines, over the 800-line cap; it was already over before this PRD and the diff grew it by roughly 110 net lines (custody verb, _stall_range, render split) | File: skills/run-autopilot/cli/__main__.py | Task: general
[BOB] ⚪ _stall_range returns the whole stall record dict, not a range (name misleads; Pat flagged, not applied) | File: skills/run-autopilot/cli/__main__.py | Task: 6
[BOB] ⚪ custody.pending() and _live_rows index `e["op_id"]` / `r["op_id"]`; load_marker only checks entries are dicts, so a marker entry or journal row without op_id raises KeyError (uncaught by _run_custody, traceback exit 1) instead of CustodyError exit 9 | File: skills/run-autopilot/cli/custody.py | Task: 1
[BOB] ⚪ test_pending_custody_handler_pauses_when_custody_state_is_unreadable asserts PAUSE and `site: "sub_skill_fail"` anywhere in the custody section rather than after the exit-9 offset (the exit-5/STOP test slices correctly) | File: skills/run-autopilot/cli/test_custody_prose.py | Task: 4
[BOB] ⚪ stalled_section hardcodes "live on master" although the stall record carries `branch` (a trunk/topic-branch custody renders a wrong report line); the PRD and design text mandate this literal | File: skills/run-autopilot/cli/render_report.py | Task: 6
[BOB] ⚪ _refresh_block scans 20 head lines while frontmatter._HEAD_LINES is now 22: a block closing on line 21-22 parses before the refresh, then gets a second block prepended and its original keys drop out of frontmatter.parse (needs 19+ keys; design-specified bound) | File: skills/run-autopilot/cli/custody.py | Task: 1
[BOB] ⚪ Fail-first replay: 5 test_render_custody tests pass against base (range-less byte-identity pins) | File: skills/run-autopilot/cli/test_render_custody.py | Task: 6
[BOB] ⚪ records and custody import each other (`from . import custody` / `from . import records`); works only because attributes are accessed lazily inside functions | File: skills/run-autopilot/cli/custody.py | Task: 1
[BOB] ⚪ Guard worst case exceeds its 10s hooks.json timeout: up to 8 candidate cwds each running resolve_toplevel (5s) plus marker_from_locator (5s) | File: hooks/guard_push_on_critical.py | Task: 2
[BOB] ⚪ refresh_hold_prd idempotency breaks when `detail` contains a newline: the prefix match replaces only the notice's first line, so a retry duplicates the tail | File: skills/run-autopilot/cli/custody.py | Task: 1
[BOB] ⚪ is_push_like tests `"push" in segment` on the raw quoted segment while decide normalises quotes, so `eval "git pu''sh"` / `sh -c 'git pu""sh'` pass the push-like check | File: hooks/guard_push_on_critical.py | Task: 2

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
D1: pass
D2: pass
D3: pass
D4: pass
D5: pass
```

## Carl

Frontend & design specialist, generalist here (no UI surface). Backend `copilot`, model `gemini-3.8-flash`, exit 0, non-empty output (12 KB). He read the context and the diff, `custody.py` and the guard in full, checked file and function lengths himself, searched for debug markers and skips, probed `split_simple_commands` on `(cd /clean); git push` and the `rev-list --format=%B` shape, ran the custody/hook/cli suites and `release-checks` (twice, once with the host dispatch markers unset). All twelve rules pass; he read the pre-existing `__main__.py` overflow as out of this diff's scope.

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

- **Mechanical facts**: computed from `ast` over the 26 changed files (16 Python) and appended to the reviewer context. Every function in the diff is under 50 lines (largest: `record_defer` 54, pre-existing; `do_park` 61, pre-existing; the new `do_stall` is 48, `_resolve_locked` 43, `_cleanup` 41, `record_critical` 40, `split_simple_commands` 45). No reviewer contradicted the block, so nothing was discarded on that ground.
- **Tautological test shapes**: 162 test functions checked in 8 files, **0 `[MECH]` findings**.
- **Fail-first replay**: 9 touched tests ran against `2c922c3`; 4 failed at base (the with-range `test_render_custody` tests), 5 passed (the range-less preservation pins, discarded with reason above); 6 test files could not be collected at base (they import `custody`, which does not exist there — fail-first evidence, not a gap).

Verdict: 18 findings

Tests: 2206 passed, 0 failed, 1 skipped (reused from last-verification.json at 1fda59631b9cc17ced374846d838185e5b79532d)
