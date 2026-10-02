---
prd: dev/local/prds/wip/00191-clear-the-handoff-marker-at-phase-edges-v1.md
review: 1
date: 2026-09-14
head_sha: 6ca3cbda721e91f6c9c6de35ba1c27f8f9bf2b4f
codex_thread_id: 01a0a15a-6a04-72f3-a429-1a00028e4957
reviewers: alice,blake,bob,carl
agents:
  alice: available
  blake: available
  bob: available
  carl: available
---

# Review: 00191-clear-the-handoff-marker-at-phase-edges-v1

Diff range: `68c624db35b914c9b985eb8b718f8f17a8f243b8..6ca3cbda721e91f6c9c6de35ba1c27f8f9bf2b4f`

codex_rung_guard: not fired

pack: failed (`engram pack` exited 1 twice — "not inside a registered repo; register it in /Users/bob/.config/gita/repos.csv", the same deterministic error every cycle of this batch has recorded). `{PACK_FILE}` and `{PACK_FINDINGS}` were substituted with the literal `(no pack available this cycle)` in every prompt that takes them. Degraded, not invalid.

scope note: cycle 1, full review of the PRD's whole work range (13 commits, 10 files, +1168/-100). `gather-context.sh` was run with `--since 68c624db…` (`state.work_start_sha`) because its default base is `master` and the batch works on `master`, so the bare form yields an empty diff; the context file's scope label was corrected by hand to say "full review". Blake stayed blind: PRD and rubric only, no filesystem-notes block (`dev/local` is a real directory — `readlink` exits 1 — and the root has no dot prefix). No design doc (`design: skip`). The three computed blocks were appended to the context file: mechanical facts (every touched Python function counted), tautological shapes (115 test functions in 3 files, none flagged), fail-first replay (one `[MECH]` 🟡 line, absorbed below and refuted — see Mechanical checks).

bob note: codex ran this cycle (exit 0, first dispatch, thread `01a0a15a-…` captured for the next cycle's `--resume-thread`). No lack-of-input shape, all twelve `R` lines, five `D` lines and the FIX/VERIFY/KNOWN buckets present, so no retry was spent. Bob's `File:` values carry `:line` suffixes and are kept as he wrote them.

carl note: gemini-run backend=copilot model=gemini-3.8-flash, exit 0, non-empty output. **Independence caveat:** Carl's transcript shows he read `dev/local/tmp/bob-output-00191-c1.txt` before emitting his findings (Bob finished first; the CLI runners share `dev/local/tmp`), and his six 🟡 lines paraphrase Bob's. Every `Bob, Carl` row below is counted as ONE independent voice at the decision gate. He did run the suites and `release-checks` himself and reproduced the numeric-marker bug independently.

verification queue: none written this cycle. Bob emitted nine FIX items, one VERIFY item and one KNOWN item. The VERIFY item (replay discrepancy) is **not queued: command shape** — it needs a base worktree plus a test-file overlay, not one project verification command — and Alice performed exactly that check (see Mechanical checks). Eve did not run (`doubt_reviewer: codex`, no codex-implemented task in `state.tasks`).

## Review Summary

Reviewed: 4 completed tasks
PRDs checked: 00191-clear-the-handoff-marker-at-phase-edges-v1

### Agent Status

- Alice: ✅ Available (Claude subagent, sonnet; ran the PRD's integrated pytest set (1184 passed, 666 subtests) and `release-checks` (exit 0), rebuilt the fail-first replay in a base worktree, traced every `transitions.apply`/`reset_prd_fields`/`do_stall` caller, reproduced `_marker_task_id('7') == ''`; 3 🟡; R1, R9, R13 fail)
- Blake: ✅ Available (Claude subagent, sonnet, blind/PRD-only; located all ten files, confirmed `transitions.TRANSITIONS` matches the PRD matrix, ran the three suites (115 passed), the full cli package (1088 passed) and `release-checks` (exit 0), `git diff --stat` shows exactly the PRD's ten files; 1 ⚪; all nineteen B rules pass)
- Bob: ✅ Available (codex, exit 0, static analysis; doubt + de-slop lens; 11 issue lines: 9 🟡, 2 ⚪; R1/R2/R4/R7/R9/R12/R13 fail, D1-D5 pass)
- Carl: ✅ Available (gemini-run backend=copilot model=gemini-3.8-flash, exit 0; ran the suites, `release-checks`, `check_style_limits.py --diff` and his own base replay; 6 🟡, 1 ⚪; R1/R2/R7/R9/R12/R13 fail; independence caveat above)

## Consolidated Findings

12 findings: 17 rows from `consolidate_findings.py`, with five cross-reviewer paraphrase pairs merged by the orchestrator (the script kept them apart because Bob's `File:` carries `:line` suffixes or the file was `N/A`): numeric-legacy rows 3+5 → `[3/4]`; 800-line rows 2+12 → `[3/4]`; prose-test-gap rows 8+14 → `[2/4]`; timestamp rows 10+13 → `[2/4]`; inherited-size rows 16+17 → `[2/4]`. Plus the one `[MECH]` replay line absorbed as its own row and Bob's ⚪ "cannot statically verify" on the same tests folded into it. No 🔴 Critical, no 🟠 High; 10 🟡 Medium (one discarded), 2 ⚪ Low.

| Consensus | Severity | Issue | File | Task | Found By |
|-----------|----------|-------|------|------|----------|
| [3/4] | 🟡 Medium | `_marker_task_id` misparses a purely-numeric legacy plain-text marker (e.g. `"7"`) as JSON — `json.loads("7")` succeeds as an int, is not a dict, so the function returns `""` instead of `"7"`; a legacy marker already naming the current numeric task id is rewritten instead of left as a no-op (PRD: "Legacy non-empty plain task IDs have the same deduplication rule"). Task ids are integer strings in production. Only the non-numeric `"task-x"` case is tested. / Bob: Numeric legacy marker `1` parses as a JSON number and is overwritten for active task `1` / Carl | skills/run-autopilot/scripts/autopilot_context_cap_hook.py:443-460 | 1 | Alice, Bob, Carl |
| [3/4] | 🟡 Medium | Stale-marker stderr note omits the PRD's literal word "removed" (`...from phase {marker phase}, expected {state.phase}` vs the spec's `...from phase <p> removed`); behavior (removal + note) is correct, wording differs; the test pins only the prefix (Blake rated ⚪, Bob and Carl 🟡) | skills/work/references/task-boundary-handoff.md:30 | 3 | Blake, Bob, Carl |
| [3/4] | 🟡 Medium | This diff grows `skills/work/scripts/test_dispatch_prose.py` from 756 to 998 lines, newly crossing the project's 800-line file cap for a file that was compliant before the change / Bob also names the hook suite at 1210 (already over at base, see the Low row) | skills/work/scripts/test_dispatch_prose.py | 3 | Alice, Bob, Carl |
| [2/4] | 🟡 Medium | Consumer validation requires field presence but never string types; malformed values such as `session: null` can reach the handoff branch. The "typed fields" test checks names only. | skills/work/references/task-boundary-handoff.md:26 | 3 | Bob, Carl |
| [2/4] | 🟡 Medium | Prose tests do not pin the reference procedure's `next_phase` assignment, telemetry `--phase`, or malformed-marker removal; those instructions can regress while the assertions remain satisfied. / Carl | skills/work/scripts/test_dispatch_prose.py:840 | 3 | Bob, Carl |
| [2/4] | 🟡 Medium | Timestamp tests normalize non-UTC offsets and invent UTC for naive timestamps, allowing violations of the UTC output contract to pass (`_parse_iso_utc`) / Carl | skills/run-autopilot/scripts/test_autopilot_context_cap_hook.py:34 | 1 | Bob, Carl |
| [1/4] | 🟡 Medium | `task-boundary-handoff.md`'s `leave` handoff row now writes `--phase <marker phase>` but still hardcodes `--site build` unconditionally, so a review-phase task-boundary handoff — the exact scenario this PRD adds — is mislabeled as a `build` site in the telemetry ledger (`subagent-dispatch.md:236`: `site` is the gate that writes the row); no test covers `--site` | skills/work/references/task-boundary-handoff.md:40 | 3 | Alice |
| [1/4] | 🟡 Medium | Park cleanup uses the supplied autopilot directory rather than the state file's directory; differing `--state` and `--autopilot-dir` locations leave the required markers untouched | skills/run-autopilot/cli/records.py:541 | 2 | Bob |
| [1/4] | 🟡 Medium | Lifecycle coverage omits marker assertions for ordinary resume, interrupted-stall reconciliation and commit-write failure; cleanup-error tests also never require the failed path on stderr | skills/run-autopilot/cli/test_handoff.py:191 | 2 | Bob |
| [1/4] | 🟡 Medium | The new cleanup helper repeats its absence/error-handling contract in both module and function docstrings; retain that explanation once and shorten the duplicate | skills/run-autopilot/cli/handoff.py:29 | 2 | Bob |
| [1/5] | 🟡 Medium | [MECH] 12 touched test(s) pass against the pre-change code: test_dangling_symlink_at_autopilot_path_is_noop, test_handoff_marker_empty_or_malformed_is_replaced_with_json, test_handoff_marker_legacy_plain_same_task_not_rewritten, test_handoff_marker_task_whose_id_prefixes_the_marked_one_is_overwritten, test_missing_or_unreadable_state_writes_no_handoff_marker, test_no_autopilot_ancestor_is_noop +6 more / Bob ⚪: Cannot statically verify the replay classifications for the prefix-ID and malformed-marker tests **(discarded — refuted, reason below)** | skills/run-autopilot/scripts/test_autopilot_context_cap_hook.py | general | mech-check, Bob |
| [2/4] | ⚪ Low | Inherited size violations remain: `record_defer` 54 lines, `do_park` 61, `_bump_and_check_tripwire` 62 (50-line rule); `cli/__main__.py` 1099 lines and the hook test suite 958 → 1210 lines (800-line rule, both already over at base) **(deferred by design, reason below)** | skills/run-autopilot/cli/records.py, skills/run-autopilot/cli/__main__.py, skills/run-autopilot/scripts/test_autopilot_context_cap_hook.py | general | Bob, Carl |

### Decision gate (Phase 5)

Cycle 1 of cap 3. **No unresolved 🔴/🟠 → converged**, pending the constraint gate (`autopilot gate --require-codex-guard --assert-constraint-met`, run after this file is saved). The Medium/Low tail is swept, not dropped: one `[D1]` task (9 findings ≤ 10, no split) dispatched through `/autopilot:work` in rework mode, then the PRD finalizes without another review cycle. Every decision is in `state.autonomous_decisions` (11 entries) or `state.deferred_decisions` (1 entry); the discard and the deferral are in `00191-clear-the-handoff-marker-at-phase-edges-v1-ledger.json`, the deferral mirrored into the batch deferred JSON. No settled deferrals from a prior cycle (cycle 1), no scope alarm (1 follow-up task), no recurring issue, no verification queue.

- **Swept (9 findings → task 5 `[D1]`, tier opus):**
  - Numeric legacy marker: confirmed by reading `_marker_task_id` (json.loads on a bare digit string yields an int, the `isinstance(payload, dict)` branch returns `""`) and by Alice's direct call. Fix: a non-object JSON value is legacy text; add a numeric-id no-op test.
  - Stale note: the PRD's literal is `autopilot: stale handoff marker from phase <p> removed`; the procedure prints `..., expected {state.phase}`. Fix the prose to the PRD literal and pin the full string.
  - 800-line cap: orchestrator re-ran `check_style_limits.py --diff` → exit 1, `FILE | skills/work/scripts/test_dispatch_prose.py | 998 lines`, so task 3's `style_gate: clean` record was wrong. `release-checks` does not enumerate this file, so splitting the task-boundary block into `test_task_boundary_handoff_prose.py` has no gate impact.
  - Typed fields: step 3b names presence and a non-empty `task_id` only; the PRD says "invalid field shapes" are malformed. Prose plus pin.
  - Test gap + `--site`: orchestrator read `test_dispatch_prose.py` 770-998 — no test names `next_phase`, `--phase` or `--site`. Fix `--site build` → `--site <marker phase>` (on the match path the marker's phase is the gate running `/autopilot:work`) and pin all three plus the malformed-path removal.
  - UTC helper: one-assertion strictness fix.
  - Cleanup dir: `park --autopilot-dir` can differ from `state_path.parent`; the PRD says the state file's directory. One-token fix plus a differing-dir test.
  - Lifecycle coverage: `test_a_marker_that_cannot_be_removed_does_not_fail_the_command` asserts no Traceback but not the reported path (commit f792aa9's fix is unpinned); add it, plus a same-phase-resume preserve test and a commit-write-failure preserve test.
  - Docstring duplication: trim.
- **Discarded (1, ledger `discarded`):** the `[MECH]` replay row. Alice checked out base `68c624db35b9` in a worktree, overlaid HEAD's hook test file and ran pytest -v: `test_handoff_marker_empty_or_malformed_is_replaced_with_json` and `test_handoff_marker_task_whose_id_prefixes_the_marked_one_is_overwritten` **FAIL at base** (`12 failed, 48 passed`); the other listed passers pin guards the PRD says to PRESERVE (unreadable-state, review-phase, dangling-symlink, no-ancestor, legacy same-task no-op) and pass at base by design. `replay_tests_against_base.py` mis-scored the subTest-carrying methods. Bob's VERIFY item on the same discrepancy is answered by that run and was not queued (command shape).
- **Deferred by design (1, `deferred_decisions` + ledger `settled-deferral` + batch deferred JSON; batch-end review may overrule):** the inherited size violations. All three functions and both files were over their limits at base `68c624d`; the surgical-changes rule keeps adjacent code untouched and the PRD names none of them. Bob filed it under KNOWN himself. Noted honestly: the hook test suite grew ~250 lines while already over the cap; a hygiene PRD is the right home for the splits.

## Follow-up Tasks Created

One `[D1]` task at tier `opus` (cross-cutting: hook code, cli, prose, a test-file split and exact PRD literals; the PRD's `default_model: sonnet` floor leaves it), covering 9 of the 12 findings; `state.rework_task_ids = ["5"]`.

1. Task 5 — `[D1]` Sweep cycle-1 findings: numeric legacy marker dedup, PRD-literal stale note, split the prose test file under 800 lines, typed-field validation, pin next_phase/--phase/--site, strict UTC stamp, clear markers beside state.json, lifecycle coverage, trim handoff.py docstring (M) - 🟡 Medium - 9 findings

### Tail sweep result (same session, after `/autopilot:work`)

Task 5 completed at opus (pipeline full): tests 44542d6 (red-check 12 failed / 77 passed), implementation 54b7706 (`fix(run-autopilot): …`, with a CHANGELOG Fixed entry); Pat: 9 `CLOSURE | resolved`, `NO FINDINGS`; step 7: integrated pytest set `1197 passed, 672 subtests`, `release-checks` exit 0. `wc -l` 756 / 476. Devon broke the tests in both rounds (round cap 1 exhausted) — weakness flagged in `dev/local/tmp/00191-rework-cycle-1-phase-report.md`; the landed implementation takes none of the exploited shortcuts. No verify-escapes (no queue) and no sweep-escapes (Pat raised no C/H). Converged at cycle 1; the PRD finalizes without another review cycle.

## Alice

Consensus lens, Claude subagent (sonnet). Ran the integrated pytest set and `release-checks`, rebuilt the fail-first replay in a disposable worktree (removed afterwards), traced every lifecycle caller, reproduced the numeric-marker bug with a direct call, `wc -l` before/after on every touched file, `rg` for TODO/skip markers (none). 3 🟡; R1, R9, R13 fail on her own findings.

```
[ALICE] 🟡 `_marker_task_id` misparses a purely-numeric legacy plain-text marker (e.g. `"7"`) as JSON — `json.loads("7")` succeeds as an int, is not a dict, so the function returns `""` instead of `"7"`. This breaks the PRD's "Legacy non-empty plain task IDs have the same deduplication rule": a legacy marker already naming the current numeric task id will be rewritten instead of left as a no-op. Task ids in this codebase are sequential integer strings (`cli/statectl.py:281`, `task_id = str(highest_id + 1)`), so this is the realistic production format, not an edge case — but the only same-task legacy-dedup test uses the non-numeric `"task-x"`, so it's untested. Self-healing after one extra write (subsequent fires read valid JSON), so it does not cause data loss or wrong-phase routing. | File: skills/run-autopilot/scripts/autopilot_context_cap_hook.py:443-460 | Task: 1
[ALICE] 🟡 `task-boundary-handoff.md`'s `leave` handoff row now writes `--phase <marker phase>` (correctly varies with the current phase) but still hardcodes `--site build` unconditionally, so a review-phase task-boundary handoff — the exact scenario this PRD adds — is mislabeled as a `build` site in the `record_dispatch.py` telemetry ledger. `record_dispatch.py`'s `SITES = ("build", "review", "done")` and its own docs (`subagent-dispatch.md:236`) treat `site` as tied to where the handoff actually occurs; no test in `test_dispatch_prose.py` covers `--site`/telemetry for this file (`rg record_dispatch`/`rg -- --site` return no hits there). Best-effort/non-gating, so this is a data-quality gap rather than a functional bug. | File: skills/work/references/task-boundary-handoff.md:40 | Task: 3
[ALICE] 🟡 This diff grows `skills/work/scripts/test_dispatch_prose.py` from 756 to 998 lines, newly crossing the project's 800-line file cap (`~/.claude/rules/coding-style.md`) for a file that was compliant before the change. | File: skills/work/scripts/test_dispatch_prose.py | Task: 3

R1: fail
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
R13: fail
```

Evidence: integrated pytest set → exit 0, `1184 passed, 6 warnings, 666 subtests passed in 36.52s`; `bash dev/bin/release-checks` → exit 0, every `[checks]` section green; `git worktree add /tmp/review-00191-base 68c624db35b9` + overlay of HEAD's two test files + `pytest -v` → all 7 new hook behavior tests and all 10 new prose tests fail at base (`12 failed, 48 passed` in the hook file; `10 failed, 33 deselected` for the prose tests); `rg -n "reset_prd_fields\(|transitions\.apply\("` → the only 3 call sites, all wired; `python3 -c "... hook._marker_task_id('7') ..."` → `''`; `wc -l` cross-checked against `git show 68c624db…:<path>`.

## Blake

Blind lens, Claude subagent (sonnet), PRD and rubric only. Located all ten files, confirmed `transitions.py` is pure and its table matches the PRD matrix, ran the three suites (115 passed, 13 subtests), the full cli package (1088 passed, 657 subtests) and `release-checks` (exit 0), `git diff --stat` over the PRD's commit range touches exactly the ten named files. 1 ⚪; all nineteen B rules pass.

```
[BLAKE] ⚪ Stale-marker stderr note omits the PRD's literal word "removed" (`...from phase {marker phase}, expected {state.phase}` vs the spec's `...from phase <p> removed`); behavior (removal + note) is correct, wording differs | File: skills/work/references/task-boundary-handoff.md | Task: 5

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

Doubt + de-slop lens, codex (static-only sandbox), first dispatch, no retry. 11 issue lines (9 🟡, 2 ⚪), nine FIX items, one VERIFY item (not queued: command shape; answered by Alice's replay), one KNOWN item. R1/R2/R4/R7/R9/R12/R13 fail on his own findings; D1-D5 pass. The orchestrator confirmed the numeric-marker, stale-note, 800-line, typed-field, test-gap, cleanup-dir and stderr-path findings by reading the cited lines; the timestamp and docstring items by reading the helper and `handoff.py`.

```
[BOB] 🟡 Numeric legacy marker `1` parses as a JSON number and is overwritten for active task `1`, violating same-task deduplication. | File: skills/run-autopilot/scripts/autopilot_context_cap_hook.py:454 | Task: 1
[BOB] 🟡 Consumer validation requires field presence but never string types; malformed values such as `session: null` can reach the handoff branch. The "typed fields" test checks names only. | File: skills/work/references/task-boundary-handoff.md:26 | Task: 3
[BOB] 🟡 Park cleanup uses the supplied autopilot directory rather than the state file's directory; differing `--state` and `--autopilot-dir` locations leave the required markers untouched. | File: skills/run-autopilot/cli/records.py:541 | Task: 2
[BOB] 🟡 Stale-marker diagnostic substitutes "expected …" for the PRD-required "removed"; the test checks only the prefix. | File: skills/work/references/task-boundary-handoff.md:30 | Task: 3
[BOB] 🟡 Prose tests do not pin the reference procedure's `next_phase` assignment, telemetry `--phase`, or malformed-marker removal; those instructions can regress while the assertions remain satisfied. | File: skills/work/scripts/test_dispatch_prose.py:840 | Task: 3
[BOB] 🟡 Lifecycle coverage omits marker assertions for ordinary resume, interrupted-stall reconciliation and commit-write failure; cleanup-error tests also never require the failed path on stderr. | File: skills/run-autopilot/cli/test_handoff.py:191 | Task: 2
[BOB] 🟡 Timestamp tests normalize non-UTC offsets and invent UTC for naive timestamps, allowing violations of the UTC output contract to pass. | File: skills/run-autopilot/scripts/test_autopilot_context_cap_hook.py:34 | Task: 1
[BOB] 🟡 The new cleanup helper repeats its absence/error-handling contract in both module and function docstrings; retain that explanation once and shorten the duplicate. | File: skills/run-autopilot/cli/handoff.py:29 | Task: 2
[BOB] 🟡 Added tests take the prose suite to 998 lines and grow the hook suite to 1210, exceeding the 800-line limit; split cohesive suites while preserving discovery. | File: N/A | Task: general
[BOB] ⚪ Cannot statically verify: replay classifications for the prefix-ID and malformed-marker tests, which report passing at base despite containing JSON-contract assertions inside subtests. | File: N/A | Task: 1
[BOB] ⚪ Inherited size violations remain: supplied AST facts report `record_defer` at 54 lines, `do_park` at 61 and `_bump_and_check_tripwire` at 62; the lightly touched CLI entrypoint is also 1099 lines. | File: N/A | Task: general

R1: fail
R2: fail
R3: pass
R4: fail
R6: pass
R7: fail
R8: pass
R9: fail
R10: pass
R11: pass
R12: fail
R13: fail

FIX:
- Numeric legacy deduplication — skills/run-autopilot/scripts/autopilot_context_cap_hook.py:454 — Check exact legacy text equality before JSON decoding; add numeric-ID regressions.
- Typed consumer validation — skills/work/references/task-boundary-handoff.md:26 — Require an object with four string fields and non-empty task identity; pin invalid-type rejection.
- Cleanup directory — skills/run-autopilot/cli/records.py:541 — Derive cleanup location from `state_path.parent`; test differing CLI directory arguments.
- Stale diagnostic — skills/work/references/task-boundary-handoff.md:30 — Use `autopilot: stale handoff marker from phase <p> removed` and assert the complete message.
- Consumer regression coverage — skills/work/scripts/test_dispatch_prose.py:840 — Assert matching-phase assignment and telemetry in the handoff branch, plus both-marker removal in the malformed branch.
- Lifecycle acceptance coverage — skills/run-autopilot/cli/test_handoff.py:191 — Seed markers around resume and reconciliation, inject commit-write failure, and assert the full failed cleanup path on stderr.
- UTC assertion — skills/run-autopilot/scripts/test_autopilot_context_cap_hook.py:34 — Assert the parsed timestamp already has a zero UTC offset before normalization.
- Repeated documentation — skills/run-autopilot/cli/handoff.py:29 — Keep the invariant explanation in the module docstring and replace the duplicate with one sentence.
- Oversized test suites — skills/work/scripts/test_dispatch_prose.py:770; skills/run-autopilot/scripts/test_autopilot_context_cap_hook.py:557 — Extract cohesive suites into modules below 800 lines and retain them in integrated checks.

VERIFY:
- Replay discrepancy — In a base `68c624db35b9` checkout with HEAD's hook test file overlaid, run `python3 skills/run-autopilot/scripts/test_autopilot_context_cap_hook.py ContextCapHookTests.test_handoff_marker_task_whose_id_prefixes_the_marked_one_is_overwritten ContextCapHookTests.test_handoff_marker_empty_or_malformed_is_replaced_with_json` and inspect unittest's subtest failures. (not queued: command shape)

KNOWN:
- Inherited size violations — The three oversized function bodies are unchanged, and restructuring the lightly touched CLI entrypoint would broaden this marker-lifecycle fix.

D1: pass
D2: pass
D3: pass
D4: pass
D5: pass
```

## Carl

Consensus lens, gemini-run backend=copilot model=gemini-3.8-flash, exit 0, no retry. Read the context, the diff, the base `_request_handoff`, `records.py`, the CHANGELOG, `check_style_limits.py` and `replay_tests_against_base.py`; ran the integrated pytest set, `release-checks` (also with the inherited dispatch markers unset), `check_style_limits.py --diff` (flags the 998-line file) and his own replay of the two disputed tests at base. **He also read `bob-output-00191-c1.txt` before writing his findings** (independence caveat in the top matter). No frontend surface, reviewed as a generalist. 6 🟡, 1 ⚪; R1/R2/R7/R9/R12/R13 fail.

```
[CARL] 🟡 Numeric legacy marker (e.g. '1') parses as JSON integer and returns empty string in _marker_task_id, breaking same-task deduplication for numeric task IDs | File: skills/run-autopilot/scripts/autopilot_context_cap_hook.py | Task: 1
[CARL] 🟡 Stale marker stderr diagnostic in task-boundary-handoff.md specifies ', expected {state.phase}' instead of the PRD-required 'removed' | File: skills/work/references/task-boundary-handoff.md | Task: 3
[CARL] 🟡 Task-boundary handoff procedure requires 4 fields for JSON markers but does not validate field types (e.g. non-null string phase), allowing non-string values to reach next_phase assignment | File: skills/work/references/task-boundary-handoff.md | Task: 3
[CARL] 🟡 Test helper _parse_iso_utc normalizes naive datetimes and non-UTC offsets to UTC, masking potential violations of the UTC ISO-8601 requirement | File: skills/run-autopilot/scripts/test_autopilot_context_cap_hook.py | Task: 1
[CARL] 🟡 Test file test_dispatch_prose.py expanded to 998 lines, exceeding the 800-line file limit | File: skills/work/scripts/test_dispatch_prose.py | Task: 3
[CARL] 🟡 Test coverage for task-boundary-handoff.md does not verify next_phase assignment, telemetry phase parameter, or marker cleanup on malformed payloads | File: skills/work/scripts/test_dispatch_prose.py | Task: 3
[CARL] ⚪ Inherited function length violations in touched files (record_defer at 54 lines, do_park at 61 lines in records.py; _bump_and_check_tripwire at 62 lines in hook) exceed the 50-line limit | File: skills/run-autopilot/cli/records.py | Task: general

R1: fail
R2: fail
R3: pass
R4: pass
R6: pass
R7: fail
R8: pass
R9: fail
R10: pass
R11: pass
R12: fail
R13: fail
```

## Mechanical checks

- Mechanical facts: every touched Python function counted from `ast` (block appended to the context file). Over 50 lines and pre-existing at base: `record_defer` 54, `do_park` 61, `_bump_and_check_tripwire` 62; every function this PRD added or changed is under 50 (`clear_markers` 14, `_marker_task_id` 18, `_request_handoff` 35, `_run_phase_done` 40, `do_stall` 46).
- Tautological shapes: none (115 test functions in 3 files checked).
- Fail-first replay: `27 touched test(s) ran, 15 failed against base, 12 passed; 1 test file(s) could not be collected at base` (test_handoff.py: `cli.handoff` does not exist there). The `[MECH]` 🟡 row was absorbed and then **discarded as refuted** by Alice's direct replay (the two named JSON-contract tests FAIL at base; the rest are preserved guards) — ledger entry `discarded`. Carl's independent replay of the same two tests agrees.
- Style gate: `python3 skills/work/scripts/check_style_limits.py --diff dev/local/tmp/review-diff-00191-c1.diff <touched files>` → exit 1, `FILE | skills/work/scripts/test_dispatch_prose.py | 998 lines` (orchestrator-run; task 3's attempt record says `style_gate: clean`, which was wrong).

Verdict: 12 findings

Tests: 1184 passed, 0 failed, 0 skipped (suite run this cycle: the PRD's integrated pytest set at 6ca3cbda, exit 0, 666 subtests; `last-verification.json` matched the sha but carried null counts)
