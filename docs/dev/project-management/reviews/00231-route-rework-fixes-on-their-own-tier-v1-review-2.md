---
prd: docs/dev/project-management/prds/wip/00231-route-rework-fixes-on-their-own-tier-v1.md
review: 2
date: 2026-09-30
head_sha: 388f09a815abd5056e2a0ae0015007b9f204c267
codex_thread_id: 01a0f41f-d0ae-79a2-8425-5547c3fc2050
reviewers: alice,blake,bob,carl
agents:
  alice: available
  blake: available
  bob: available
  carl: available
---

# Review: 00231-route-rework-fixes-on-their-own-tier-v1

Diff range: `f550a2ede27c25592644f926717ecfa0443e81e1..388f09a815abd5056e2a0ae0015007b9f204c267`

codex_rung_guard: not fired

pack: failed (engram exited 1 — "not inside a registered repo; register it in /Users/bob/.config/gita/repos.csv"). The same deterministic config miss as cycle 1, not a transient fault, so no retry was attempted. Every implementation-aware prompt received the sentinel `(no pack available this cycle)` for `{PACK_FILE}` and `{PACK_FINDINGS}`. The review is degraded on retrieval context, not invalid.

Scope: **incremental**, `--since f550a2e…` as the cycle-1 `head_sha` prescribes. The scoped diff is exactly the two rework commits — `990b43f` (task 4) and `388f09a` (task 5) — touching two files, 22 insertions and 13 deletions. Bob ran fresh with no `--resume-thread`: the cycle-1 review file stamped no `codex_thread_id`. This cycle's id is stamped above, so cycle 3 (if there were one) could resume him.

## Review Summary

Reviewed: 2 rework tasks (commits `990b43f`, `388f09a`); tasks 1-3 were reviewed in full in cycle 1.
PRDs checked: 00231-route-rework-fixes-on-their-own-tier-v1

### Agent Status

- Alice: ✅ Available (consensus lens)
- Blake: ✅ Available (blind lens, PRD-only)
- Bob: ✅ Available (codex, doubt + de-slop lens, first run, no retry)
- Carl: ✅ Available (gemini via copilot backend, reviewing as generalist)
- Eve: ⏸️ Disabled (`doubt_reviewer: codex` and the codex doubt-roster guard did not fire — no task has a codex implementor)

**Cycle 1's high-severity finding is resolved, and every cycle-1 finding routed to rework is closed.** `bash dev/bin/release-checks` now **exits 0** — run by the orchestrator in the foreground at this HEAD, exit code captured explicitly (`release-checks exit=0`). That was the one 🟠 blocking cycle 1, and it was also the PRD's own second Success Metric. All four reviewers independently confirmed the prose contract still holds verbatim after the rework: the `phase-review.md:269` sentence, the untouched Tail sweep sentence, the `plan-tasks/SKILL.md:308` bullet as the last item of the step 4.7 floor list, the three PRD-named test names unchanged, and the three needles unchanged. No reviewer found scope creep, a new flag, or a new dependency.

## Consolidated Findings

| Consensus | Severity | Issue | File | Task | Found By |
|-----------|----------|-------|------|------|----------|
| [1/4] | 🟡 | FIX: `_compute_tier_bullet` stops at the named task-add item, not the bullet boundary. Moving any needle into a new sibling bullet before task-add still passes. Stop at the next structural bullet boundary. | skills/run-autopilot/scripts/test_rework_tier_prose.py:25 | 5 | BOB |
| [1/4] | 🟡 | FIX: `floor_list` includes paragraphs between “This guarantees:” and the qwen heading. Moving the pointer out of the list into a standalone paragraph there still passes. Assert membership in the contiguous Markdown floor list. | skills/run-autopilot/scripts/test_rework_tier_prose.py:52 | 5 | BOB |
| [1/4] | ⚪ | The bullet-end marker `_NEXT_BULLET` and the plan-tasks slice markers ("This guarantees:", "**`qwen_eligible` computation**") are located with bare `str.index`, so if the sibling bullet or heading is reworded the test dies with a bare ValueError instead of the drift message the suite promises. The presence assert covers only the start marker. Optional hardening: assert each marker is present with a drift-naming message. | skills/run-autopilot/scripts/test_rework_tier_prose.py:25 | 5 | ALICE |

Consolidation was produced by `consolidate_findings.py` (not model-side), with `--ledger` and `--ledger-dismiss BLAKE` against the 3-entry cycle-1 ledger. It printed no `### Auto-dismissed (ledger)` section: Blake raised nothing this cycle, so the dismissal filter had nothing to match. No reviewer re-raised a settled decision.

All three rows are one theme — the rework's new slice windows and their markers are bounded by *text* rather than by Markdown structure — and all three are in the one file task 5 created. **No 🔴 CRITICAL row and no 🟠 HIGH row**, so no rework design runs and no rework cycle is needed; the three rows are the Medium/Low tail and are swept below.

### Verification of each cycle-1 finding

| Cycle-1 finding | Status at this HEAD | Evidence |
|---|---|---|
| 🟠 [2/4] `test_changelog_unreleased_has_one_changed_heading` red on an emptied `[Unreleased]` | **resolved** | `test_devon_round_prose.py:234` now asserts `count <= 1` with an "at most one" message; `bash dev/bin/release-checks` exits 0 (orchestrator run, exit code captured). Alice and Carl each re-ran the file green. |
| 🟡 [2/4] both pins sliced to end of file | **resolved** | `_compute_tier_bullet` ends the slice at `` `task-add <task-json-file>` with a payload ``, which sits at `phase-review.md:270`, directly after the Compute-the-tier bullet at 269. Both bullet-scoped tests use the helper. (Bob's new row 1 narrows, not reopens, this: the window is now the bullet, but bounded textually.) |
| 🟡 [1/4] missing bullet raised a bare `ValueError`, not the drift message | **resolved** | the helper asserts the start marker with a drift-naming message and both tests route through it. (Alice's new ⚪ row extends this to the *end* markers, which still use bare `str.index`.) |
| 🟡 [1/4] nine-line module docstring restating the tests | **resolved** | now a three-line purpose statement at `test_rework_tier_prose.py:1`; the false "each file is read once" claim is gone. |
| ⚪ [1/4] plan-tasks pin matched anywhere in the file | **resolved** | the test slices `plan-tasks/SKILL.md` from "This guarantees:" (line 302) to the `qwen_eligible` heading (line 310); the pointer sentence is at 308. "This guarantees:" occurs once in the file. (Bob's new row 2 narrows this the same way row 1 narrows the bullet pin.) |
| ⚪ ×3 settled (Tail sweep wording, `tier_reason` metric, Bob's unrunnable check) | **not re-raised** | all three fed to Alice, Bob and Carl as settled decisions; none returned. |

### Mechanical checks (computed)

- **Mechanical facts:** `test_rework_tier_prose.py` — `_compute_tier_bullet` 6 lines, `test_floor_applies_only_to_critical_rework` 9, `test_non_critical_rework_keeps_the_classifier_tier` 5, `test_plan_tasks_points_at_the_rework_rule` 9. `test_devon_round_prose.py` — 13 functions, largest 24 lines, `test_changelog_unreleased_has_one_changed_heading` 8. Every function is far under the 50-line limit and both files under 800 lines. No finding contradicts this block.
- **Tautological test shapes:** 15 test functions checked across 2 files, **no `[MECH]` lines** — no test whose shape cannot fail.
- **Fail-first replay:** **skipped**, reported verbatim as `replay: skipped (no non-test change; a backfill's tests pass against base by design)`. This cycle's diff changes only test files, so there is no production change for a replay to pin. That is a legitimate skip, not a gap: in this prose-pin repo the *prose* is the production surface and it was reviewed in full in cycle 1, where 3 of 3 touched tests failed against base. No `[MECH]` lines to absorb.

### Verification-check queue

None written this cycle, and none carried forward. No `00231-…-checks-1.json` exists (cycle 1 wrote none), so the carry-forward read found nothing — an absent queue file is never an error. Eve did not run, and `agents/bob.md` defines no FIX/VERIFY/KNOWN buckets, so there is no doubt-lens VERIFY bucket to queue from. Bob's two findings this cycle are ordinary `[BOB] 🟡 FIX:` issue lines, not bucket items.

## Alice

Findings: 1 ⚪ (row 3 above).

Verified all five cycle-1 rework findings resolved, each with the file and line of the fix. Confirmed `_compute_tier_bullet`'s end marker resolves to `phase-review.md:270`, adjacent to the bullet at 269, so the window is the bullet today. Confirmed the three PRD-named test names and the three needles are unchanged, and that "This guarantees:" occurs exactly once in `plan-tasks/SKILL.md`. Ran the two touched test files: 15 passed. Her one new row is explicitly labelled optional hardening: the *end* markers are located with bare `str.index`, so a reworded sibling bullet or heading kills the test with a `ValueError` rather than the drift message the suite advertises — the same class of defect cycle 1 raised about the start marker, one step out. She also noted the diff re-wraps the `_PHASE_REVIEW` assignment as unrelated formatting churn, and judged it trivial. She ran `release-checks` but could not see its exit code and said so rather than claiming a pass.

```
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

```
[BLAKE] ✅ No issues found
```

Located every file from the spec alone, with no diff and no review history. Confirmed the `phase-review.md:269` sentence verbatim including the 🔴 emoji, the backtick placement and the measured-data clause, with the re-parse/warn/pass-through/not-persisted tail intact; the Tail sweep sentence at 195 unchanged; the pointer sentence as the last item of the step 4.7 floor list at `plan-tasks/SKILL.md:308`; the three named tests present, bullet-scoped and green (3 passed); `dev/bin/release-checks:95` wiring the new file beside its siblings; and the CHANGELOG bullet's `**run-autopilot**` prefix with grep count 1. He independently resolved the cycle-1 CHANGELOG question the other way round from a blind position: the entry now sits under `## [0.6.0]` rather than `[Unreleased]` because release commit `f550a2e` rolled it in after it was added, which he judged correct rather than a defect. He reported not running the two prose suites separately and said release-checks covers them as far as he saw it run.

```
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

B16 — the Phase 2 acceptance criteria that Blake flagged as a judgement call in cycle 1 and passed only at `0442eb6` — now passes on the strict reading too: `release-checks` exits 0 at this HEAD. The finding that forced that caveat is gone.

## Bob

Findings: 2 🟡 (rows 1 and 2 above). Ran on codex in the read-only sandbox, first run, no retry, no resume thread.

Both rows are the same narrowing: the rework bounded each window with a *text* marker, and Bob asks for a *structural* Markdown boundary instead. For the bullet pin, a new sibling bullet inserted before the `task-add` item would sit inside the window. For the plan-tasks pin, the "This guarantees:" → `qwen_eligible` span includes the paragraphs between them, not only the contiguous floor list. He emitted no `⚪ Cannot statically verify` line this cycle — the settled-decisions block told him `release-checks` had already been run — so the sandbox-escape row from cycle 1 did not recur.

```
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
R12: pass
R13: pass
```

Bob's `R1`/`R2`/`R9` fails are his reading of the two remaining pin-looseness rows: in his judgement a textually-bounded window does not yet bind the tests to intent, so the behaviour is not pinned exactly as specified. The computed blocks disagree on the narrow question of tautology (no tautological shapes; cycle 1's replay showed 3 of 3 tests failing against base), and the decision gate resolves the disagreement by sweeping the two rows rather than discarding either signal. His three fails are not blocking: per-rule verdicts are not the convergence test, which is severity-based, and he tagged both findings 🟡 himself.

```
D1: pass
D2: pass
D3: pass
D4: pass
D5: pass
```

## Carl

```
[CARL] ✅ No issues found
```

```
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

Backend: `gemini-run.sh` on the `copilot` backend, exit 0, non-empty reviewer text. The change has no frontend surface, so Carl reviewed as a generalist and invented no frontend findings, as his persona directs. He ran the two touched test files green and read the new test file, `test_devon_round_prose.py:225-245`, `dev/bin/release-checks` and the sibling `test_review_resume_prose.py:20-40` for the pattern the rework was told to follow.

**Recorded observation (not a finding against this diff).** Carl's first `bash dev/bin/release-checks` run failed with `SUMMARY: 6 passed, 20 failed` in the `[checks] runner recursion guard` section, every failure reading `refusing nested dispatch (depth=1)`. He diagnosed it himself — he runs *inside* a nested CLI dispatch, so `AUTOPILOT_DISPATCH_DEPTH`, `COPILOT_CLI` and `_AUTOPILOT_LOOP` are set in his environment and the guard under test refuses — and re-ran as `env -u AUTOPILOT_DISPATCH_DEPTH -u COPILOT_CLI -u _AUTOPILOT_LOOP bash dev/bin/release-checks`, which passed. Unlike cycle 1, Carl's all-pass verdict here is consistent with his own observed output. The environment sensitivity is real but pre-existing and out of scope for this PRD; it is deferred to batch end below rather than dropped.

## Decision gate

**Converged.** No unresolved 🔴 CRITICAL and no unresolved 🟠 HIGH remains: cycle 1's single 🟠 is fixed and independently verified (`release-checks exit=0`), and this cycle raised nothing above 🟡. Medium and Low findings never block convergence — they are swept, not dropped.

The cap is therefore irrelevant. `state.cycle` is 2 and `state.rework_cap` is 2, so had an unresolved CRITICAL/HIGH survived this cycle the cap-out path would have fired; it did not, and a converged cycle at the cap goes to the finalize hand-off, not to a cap-pause. No third review cycle runs.

| Finding | Disposition |
|---------|-------------|
| Row 1 🟡 bullet window bounded by text, not structure | **auto-fix** → Tail sweep task |
| Row 2 🟡 floor-list window includes intervening paragraphs | **auto-fix** → Tail sweep task |
| Row 3 ⚪ end markers use bare `str.index`, so drift dies as `ValueError` | **auto-fix** → Tail sweep task |
| Carl's nested-dispatch `release-checks` sensitivity | **deferred to batch end** — out of scope for a prose PRD; pre-existing behaviour of the recursion-guard tests, reproduced only from inside a nested CLI dispatch, and `release-checks` exits 0 in a normal shell |

All three actionable rows are Medium/Low, share one file and one theme, and total well under the 10-finding split threshold, so they become **one** `[D2] Tail sweep` task. Per the very rule this PRD ships, that task carries no 🔴 line and so keeps its classifier tier rather than taking the PRD's `default_model` floor — `sonnet` either way here, since `default_model` is `sonnet`.

3 follow-up findings, 1 task — well under the 10-task scope alarm.

### Follow-up Tasks Created

1. `[D2] Tail sweep: bound the rework-tier pin windows and their markers structurally` (S) — sonnet — 🟡 [1/4] ×2 + ⚪ [1/4], addresses rows 1, 2, 3

Verdict: 3 findings
Tests: 4187 passed, 0 failed, 1 skipped (suite run this cycle)

The `Tests:` line is a fresh run, not a reuse: `last-verification.json` records this cycle's reviewed HEAD (`388f09a`) but with all three counts `null`, so the record was rejected on null counts and the suite was run. Command: `uv run --no-project --with pytest python -m pytest -q --continue-on-collection-errors -p no:cacheprovider hooks skills`, 288.86s, plus 1049 subtests passed. **The run exited 1, not 0** — from 3 collection errors, not from any test failure: `skills/run-autopilot/scripts/tracon/{test_panels,test_screens,test_stream}.py` cannot import `rich`, confirmed by re-running one of them directly (`ModuleNotFoundError: No module named 'rich'`). That module is absent from this environment, the same three errors cycle 1 recorded, and `dev/bin/release-checks` — which exits 0 — does not cover that tree. Zero tests failed.
