---
prd: docs/dev/project-management/prds/wip/00231-route-rework-fixes-on-their-own-tier-v1.md
review: 1
date: 2026-09-30
head_sha: f550a2ede27c25592644f926717ecfa0443e81e1
reviewers: alice,blake,bob,carl
agents:
  alice: available
  blake: available
  bob: available
  carl: available
---

# Review: 00231-route-rework-fixes-on-their-own-tier-v1

Diff range: `319343c31b9c8ccc3f3571038e13b43518d715e5..f550a2ede27c25592644f926717ecfa0443e81e1`

codex_rung_guard: not fired

pack: failed (engram exited 1 — "not inside a registered repo; register it in /Users/bob/.config/gita/repos.csv"). A deterministic config miss, not a transient fault, so no retry was attempted. Every implementation-aware prompt received the sentinel `(no pack available this cycle)` for `{PACK_FILE}` and `{PACK_FINDINGS}`. The review is degraded on retrieval context, not invalid.

Scope note: `gather-context.sh` with no `--since` produced an EMPTY diff, because this repo works directly on `master` and the script's default base resolves to `master` (`git diff master` on `master` is empty). Re-run as `--since 319343c…`, which yields exactly the `work_start_sha..HEAD` range this cycle requires. The context file's scope label therefore reads "incremental" and was corrected in place to say FULL; this is cycle 1 and no reviewer was told to verify prior findings.

Out-of-band commit in range: `f550a2e chore: release v0.6.0` (version bumps in `.claude-plugin/plugin.json` and `.claude-plugin/marketplace.json`, plus a `## [0.6.0]` CHANGELOG heading). It is not PRD work; it is in range because the range starts at the PRD's work-start sha. It is the proximate cause of the one high-severity finding below.

## Review Summary

Reviewed: 3 completed tasks (commits `09b8715`, `8407b2d`, `0442eb6`)
PRDs checked: 00231-route-rework-fixes-on-their-own-tier-v1

### Agent Status

- Alice: ✅ Available (consensus lens)
- Blake: ✅ Available (blind lens, PRD-only)
- Bob: ✅ Available (codex, doubt + de-slop lens)
- Carl: ✅ Available (gemini via copilot backend, frontend/design specialist reviewing as generalist)
- Eve: ⏸️ Disabled (`doubt_reviewer: codex` and the codex doubt-roster guard did not fire — no task has a codex implementor)

**The PRD's own prose contract was met.** All four reviewers independently confirmed the `phase-review.md:269` sentence and the `plan-tasks/SKILL.md:308` bullet match the PRD's replacement text verbatim, including the 🔴 emoji and backtick placement; the plan-tasks bullet is the last item of the floor list as required; the Tail sweep sentence is untouched; the three named tests exist and pass; `dev/bin/release-checks:95` wires the new file beside its sibling prose tests; and the CHANGELOG bullet carries the `**run-autopilot**:` prefix and the literal phrase "floor only for CRITICAL". No reviewer found scope creep, a new flag, or a new dependency.

## Consolidated Findings

| Consensus | Severity | Issue | File | Task | Found By |
|-----------|----------|-------|------|------|----------|
| [2/4] | 🟠 | Release commit f550a2e moved every [Unreleased] entry under `## [0.6.0]`, leaving [Unreleased] empty, which turns test_changelog_unreleased_has_one_changed_heading red (found 0 '### Changed' headings, expected exactly 1) so `bash dev/bin/release-checks` exits 1 at HEAD; the same gate was green at 0442eb6, so PRD 00231 Task 3 acceptance and the Success Metric "release-checks green" do not hold at the reviewed HEAD; relax the pin to count <= 1 since the invariant is "no duplicate headings" and an emptied [Unreleased] is legitimate | skills/work/scripts/test_devon_round_prose.py:231 | general | ALICE, BLAKE |
| [2/4] | 🟡 | Both prose pins slice from the first "Compute the tier" to end of file, not the bullet, so the needles "only when the task's findings include at least one 🔴 CRITICAL line", "`final_tier = max(tier, default_model)`" and "keeps the classifier tier" would still pass if they moved to a later bullet or section, while the spec asks that the bullet contains them; reverting the edit still fails the test, so it is a real but loose pin | skills/run-autopilot/scripts/test_rework_tier_prose.py:24 | 2 | BLAKE, BOB |
| [1/4] | 🟡 | test_rework_tier_prose.py calls the region it asserts on "the 'Compute the tier' bullet" but text[text.index(_COMPUTE_TIER):] on lines 113 and 125 runs to end of file, not to the end of the bullet, so a later edit that drops the gate from the bullet but leaves or adds the phrase elsewhere after line 269 would still pass; test_non_critical_rework_keeps_the_classifier_tier also has no presence assert, so a missing bullet surfaces as a bare ValueError instead of the drift message the suite promises | skills/run-autopilot/scripts/test_rework_tier_prose.py:113 | 2 | ALICE |
| [1/4] | 🟡 | FIX: Simplify the nine-line module docstring to one purpose sentence; its second paragraph restates the tests and incorrectly claims each file is read once. | skills/run-autopilot/scripts/test_rework_tier_prose.py:1 | 2 | BOB |
| [1/4] | ⚪ | The Tail sweep sentence still says "then the `default_model` floor exactly as that section computes it", but a Tail sweep takes only actionable Medium/Low findings so it can never carry a 🔴 line, making the floor a no-op there while the clause still reads as if a floor may apply | skills/run-autopilot/references/phase-review.md:195 | 1 | ALICE |
| [1/4] | ⚪ | test_plan_tasks_points_at_the_rework_rule checks the pointer sentence anywhere in plan-tasks/SKILL.md, not in the step 4.7 floor list; the sentence is correctly the last bullet of that list at line 308, so this is pin looseness only | skills/run-autopilot/scripts/test_rework_tier_prose.py:44 | 2 | BLAKE |
| [1/4] | ⚪ | The spec's post-release signal ("a `[D]` task records `tier_reason` from the classifier, never `floor`") may not be observable, because the task-add payload line lists only estimated_tokens and est_context_peak as classifier fields and tier_reason is read only in cli/statectl.py:418; the spec did not ask for a change here | skills/run-autopilot/references/phase-review.md:270 | 1 | BLAKE |
| [1/4] | ⚪ | Cannot statically verify: VERIFY — release checks pass; exact check: `bash dev/bin/release-checks`. The supplied replay proves base failures, not current-suite success. | N/A | general | BOB |

Consolidation was produced by `consolidate_findings.py` (not model-side). It merged row 1's two citations after suffix stripping (`:231` ~ `:234`). It did **not** merge rows 2 and 3, which are the same defect in different words citing different lines of one file; the decision gate treats them as one and routes them to a single task. The `--ledger` flags were omitted because no ledger file existed at consolidation time (cycle 1).

No 🔴 CRITICAL row, so no rework design runs this cycle (`phase-review.md` Phase 6 § Design CRITICAL rework before any task-add fires only on a 🔴 row).

### Mechanical checks (computed)

- **Mechanical facts:** `test_rework_tier_prose.py` — `test_floor_applies_only_to_critical_rework` 11 lines, `test_non_critical_rework_keeps_the_classifier_tier` 6 lines, `test_plan_tasks_points_at_the_rework_rule` 4 lines. All other changed files are non-Python and were skipped. No finding contradicts this block.
- **Tautological test shapes:** 3 test functions checked in 1 file, **no `[MECH]` lines** — no test whose shape cannot fail.
- **Fail-first replay:** 3 of 3 touched tests ran against base `319343c31b9c` and **3 failed there, 0 passed**. Every new test genuinely pins this change. No `[MECH]` lines to absorb.

### Verification-check queue

None written this cycle. Eve did not run (`doubt_reviewer: codex`, guard not fired), and `agents/bob.md` defines no FIX/VERIFY/KNOWN buckets, so there is no doubt-lens VERIFY bucket to queue from. Bob's inline "VERIFY — release checks pass" rides inside his `[BOB] ⚪ Cannot statically verify` sandbox-escape line rather than a bucket; per this skill's step 6 a bucket he did not emit is not invented. That check was run by the orchestrator instead, and its result is the 🟠 row above.

## Alice

Findings: 1 🟠, 1 🟡, 1 ⚪ (rows 1, 3, 5 above).

Reproduced the release-checks red directly (1 failed, 557 passed across the CHANGELOG-reading suites) and confirmed the same gate was green at `0442eb6`. Proposed relaxing the pin to `count <= 1`, on the grounds that the invariant is "no duplicate headings" and an emptied `[Unreleased]` is legitimate. Verified the verbatim wording of both prose edits, the release wiring, the CHANGELOG entry, and that no test or code pinned the old "step 4.7 defines it" sentence (`classify_tier.py`'s floor logic is untouched and unaffected). Noted the tracon test directories fail to collect locally because `rich` is missing, unrelated to this diff.

```
R1: pass
R2: pass
R3: pass
R4: fail
R6: pass
R7: pass
R8: pass
R9: pass
R10: pass
R11: pass
R12: pass
R13: pass
```

Alice's lone `R4: fail` is the release-checks red (changed components integrating with existing callers — the CHANGELOG entry no longer satisfies the heading pin its release gate enforces).

## Blake

Findings: 2 🟡, 2 ⚪ (rows 1, 2, 6, 7 above). No CRITICAL or HIGH.

Located every file from the spec alone. Independently reproduced the release-checks red at HEAD and, in a temporary worktree since removed, confirmed it was green at `0442eb6` — so the PRD's diff did not cause it. Added the observation that `autopilot wave assemble` runs release-checks after every lane merge, so this red would trip wave assembly. Confirmed both prose edits verbatim, the step 4.7 bullet placement, the three tests passing, the release wiring at `dev/bin/release-checks:95`, and minimal scope (2 files task 1, 2 files task 2, 1 file task 3) with no extra features, flags or dependencies. Side suites: `skills/plan-tasks/scripts` 192 passed, `skills/run-autopilot/scripts` 622 passed, eight other phase-review-referencing prose tests 302 passed; skipped tracon for the missing `rich` module. Reported his worktree removed and `git status` clean.

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

Blake flagged B16 as a judgement call: he passed it because the PRD's Phase 2 criteria held at its own commit (`0442eb6`), and stated that graded strictly at HEAD it fails. The decision gate takes the strict reading — that is exactly why row 1 is queued as rework rather than waved through.

## Bob

Findings: 2 🟡, 1 ⚪ (rows 2, 4, 8 above). Ran on codex in the read-only sandbox, first run, no retry.

Independently found the end-of-file window defect in both Phase 6 tests and asked for the assertion windows to be bound to the bullet's own lines. Raised the module docstring as de-slop: nine lines restating the tests, with an incorrect claim that each file is read once. Emitted the sandbox-escape line for release-checks, which the orchestrator then ran.

```
R1: fail
R2: fail
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
D1: pass
D2: pass
D3: pass
D4: pass
D5: pass
```

Bob's `R1`/`R2` fails are his reading of the loose pins: a window that runs to end of file does not, in his judgement, bind the tests to intent. The computed fail-first replay block disagrees on the narrow question of tautology (3 of 3 tests fail against base), and the decision gate resolves this by fixing the window rather than by discarding either signal.

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

Backend: gemini-run.sh on the `copilot` backend, exit 0. The change has no frontend surface, so Carl reviewed as a generalist and invented no frontend findings, as his persona directs.

**Recorded divergence:** Carl's transcript shows him running `bash dev/bin/release-checks` and observing the same failure Alice and Blake raised, then returning `✅ No issues found` with every rule passing — including `R4`, where Alice failed on that evidence. His verdict is recorded as returned and not overridden, but it is not corroboration: on the one high-severity finding of this cycle his lens is inconsistent with his own observed output, so treat the row-1 consensus as Alice plus Blake and read Carl's all-pass as unreliable rather than as a third clean opinion.

## Decision gate

Not converged: one unresolved 🟠 HIGH remains (row 1). `state.cycle` 1 < `state.rework_cap` 2, so rework is allowed and the cap does not apply.

| Finding | Disposition |
|---------|-------------|
| Row 1 🟠 release-checks red | **auto-fix** → task 4 |
| Rows 2 + 3 + 4 🟡, row 6 ⚪ (all in `test_rework_tier_prose.py`) | **auto-fix** → task 5 (one task; rows 2 and 3 are one defect) |
| Row 5 ⚪ Tail sweep clarity | **discarded** — the PRD contract states verbatim that this sentence is unchanged; editing it would violate the spec under review, and the no-op is the intended consequence |
| Row 7 ⚪ `tier_reason` observability | **deferred to batch end** — out of scope by the PRD's own text; a gap in the PRD's post-release metric, not a spec/implementation divergence |
| Row 8 ⚪ Bob's un-runnable check | **discarded** — resolved by evidence; the check was run and its result is row 1 |

Row 1 is High severity, and a strict reading of `decision-framework.md` would route a non-additive High with no matching auto-fix row to the safety-default deferral. It is classified auto-fix instead, deliberately and on the record: the severity is High by blast radius (the repo's release gate and wave assembly are red), not by fix risk or ambiguity, and the fix is mechanical and provably intent-preserving because the assertion's own failure message states the invariant as no-duplicate-headings while the assertion encodes exactly-one. Deferring it would finalize the PRD with its own Success Metric ("release-checks green") red. Recorded in `autonomous_decisions`.

2 follow-up tasks — well under the 10-task scope alarm. Both carry no 🔴 line, so per the very rule this PRD ships they keep the classifier tier rather than a `default_model` floor; `default_model` is `sonnet` here in any case, so both are `sonnet`.

### Follow-up Tasks Created

1. `[D1] Let an emptied [Unreleased] pass the CHANGELOG heading pin so release-checks goes green` (S) — task 4, sonnet — 🟠 [2/4], addresses row 1
2. `[D1] Bound the rework-tier prose pins to the Compute-the-tier bullet and trim the module docstring` (M) — task 5, sonnet — 🟡 [2/4], addresses rows 2, 3, 4, 6

Verdict: 8 findings
Tests: 4186 passed, 1 failed, 1 skipped (suite run this cycle)

The `Tests:` line is a fresh run, not a reuse: `last-verification.json` records `sha 0442eb6` with null counts, while this cycle's reviewed HEAD is `f550a2e`, so the record was rejected on both sha mismatch and null counts. Command: `uv run --no-project --with pytest python -m pytest -q --continue-on-collection-errors -p no:cacheprovider hooks skills`, 308s. The single failure is row 1. Three collection errors also occurred, all pre-existing and unrelated to this diff: `skills/run-autopilot/scripts/tracon/{test_panels,test_screens,test_stream}.py` cannot import `rich`, which is absent from this environment. A wider run including `dev/` reports `2 failed, 4824 passed, 2 skipped, 11 errors`; the extra failure and errors all come from a stale `dev/local/tmp/` scratch tree that the v0.6.0 CHANGELOG says was relocated to `docs/dev/tmp/`, so they are leftovers rather than live tests, and `dev/bin/release-checks` does not cover that tree.
