---
prd: dev/local/prds/wip/00215-assemble-a-drained-wave-onto-one-branch-v1.md
review: 1
date: 2026-09-28
head_sha: 515989621530b24c5ad40f1d097ad13a727997e4
codex_thread_id: 01a0e4d9-901a-71f1-a75f-3fc61a326bf0
reviewers: alice,blake,bob,carl
agents:
  alice: available
  blake: available
  bob: available
  carl: available
---

# Review: 00215-assemble-a-drained-wave-onto-one-branch-v1

Diff range: `206c914d70008dc287c8f13ed2bf1db030607b59..515989621530b24c5ad40f1d097ad13a727997e4`

codex_rung_guard: not fired

pack: failed (engram exited 1: "not inside a registered repo; register it in /Users/bob/.config/gita/repos.csv"). Not retried — a missing gita registry entry is a deterministic config precondition, not a transient error. `{PACK_FILE}` and `{PACK_FINDINGS}` were substituted with `(no pack available this cycle)` in every prompt that takes them. The review is degraded on retrieval context only, not invalid.

## Scope note (read before any finding)

The raw PRD work range above **spans a foreign commit**: `c26156f` ("refactor!: move working documents from dev/local to docs/dev/project-management", 177 files) was written by a different, concurrent interactive session in this same checkout and is **not** part of PRD 00215. The diff handed to every implementation-aware reviewer was rebuilt to exclude it, as two contiguous foreign-free segments whose union is exactly this PRD's own 16 commits:

- SEGMENT A: `206c914d..4d22f45` — task 1, task 2, task 3's first test commit
- SEGMENT B: `c26156f..5159896` — task 3's remaining commits, task 4

That cut the reviewer payload from 863 KB to 114 KB of in-scope change across 13 files. The unfiltered full-range diff was retained at `dev/local/tmp/review-diff-00215c1-fullrange.diff`.

A second, related fact was stated to every reviewer to prevent a class of false finding: this repo's own **runtime** state still lives under `dev/local/` while the skill **source text** now says `docs/dev/project-management/...`. Both are correct in their own layer; the mismatch is expected and was not to be raised.

Note also that the mechanical full-review path would have produced an **empty** diff here (`git diff master` while on master), which the skill forbids from reaching a verdict. `state.work_start_sha` was used as the diff base instead.

## Mechanical checks (computed, not reviewer judgment)

- **Function/file sizes:** `keep_both` 7 lines, `summary` 39, `assemble` 46, largest function `assemble` at 46. The PRD's Phase 0 exit criterion ("the two functions under 50 lines") holds. All files under 800 lines. R12/R13 pass by computation, and all four reviewers agreed.
- **Tautological test shapes:** 33 test functions checked across 4 test files, **zero** shapes that cannot fail.
- **Fail-first replay:** clean for this PRD. All three new test files (`test_wave_assemble.py`, `test_wave_assemble_migrate.py`, `test_wave_cli_assemble.py`) fail to collect against the base, because `cli/wave_assemble.py` does not exist there — correct fail-first evidence for a new module.
- **Mechanical findings absorbed into the table below: none.** The replay's raw run emitted 20 `[MECH]` lines, and **every one names a test file belonging to the foreign commit `c26156f`**, not to this PRD (the replay derives its touched-test set from the raw base diff, which spans that commit). They are recorded here rather than dropped silently, and are not findings against 00215: `hooks/test_guard_push_on_critical.py`, `hooks/test_guard_skill_after_leave.py`, `skills/fast-track/scripts/test_fast_track_renders.py`, `skills/run-autopilot/cli/test_cli.py`, `test_custody_prose_schema.py`, `test_lifecycle_cli.py`, `test_loop_review_once.py`, `test_routing.py`, `test_routing_rework.py`, `test_selection.py`, `test_wave_launch_refusals.py`, `skills/run-autopilot/scripts/test_autopilot_context_cap_hook.py`, `test_autopilot_lifecycle.py`, `test_autopilot_phase2_stall.py`, `test_review_coverage_hook.py`, `scripts/tracon/test_discovery.py`, `scripts/tracon/test_model.py`, `skills/work/scripts/test_check_build_overhead.py`, `test_dispatch_telemetry_prose.py`, `test_render_prompt_dispatch.py`.

## Consolidated findings

25 findings: 5 🟠 High, 18 🟡 Medium, 2 ⚪ Low. No 🔴 Critical.

Consolidation ran via `consolidate_findings.py` with no `--ledger` flags (cycle 1 has no settled-decisions ledger). It merged three rows on suffix-stripped citations, and it did **not** merge one pair that is in fact a single defect — see H2 below.

| Consensus | Severity | Issue | File | Task | Found By |
|-----------|----------|-------|------|------|----------|
| [3/4] | 🟡 | Gap 1 CONFIRMED, not fixed by the strengthening round: `test_summary_opens_with_the_base_and_the_assembled_head` was parametrized with two waves, but it only asserts each of the five header values (`id`, `base_branch`, `base_sha`, `branch`, `head_sha`) is present in the header and the other wave's values are absent — it never pins which value renders on which line. A `summary()` that swapped `base_sha` and `head_sha` between the "base" and "assembled head" lines within one render would still pass every assertion. | skills/run-autopilot/cli/test_wave_assemble.py:223 | 3 | ALICE, BOB, CARL |
| [3/4] | 🟡 | Gap 3 CONFIRMED, unaddressed: `test_summary_tables_each_lane_with_its_branch_status_and_batch` still gives every lane exactly one PRD, one path and one file (the strengthening round only made `paths`/`files` disjoint per lane, still singular). No test pins per-lane pluralisation (join separator, ordering) of the `prds`/`paths`/`files` table columns for a lane with more than one of any. | skills/run-autopilot/cli/test_wave_assemble.py:265 | 3 | ALICE, BOB, CARL |
| [2/4] | 🟠 | **H1** — `assemble()`'s rewritten wave report silently drops a lane's non-roster PRDs (e.g. a parked PRD that only ever lived in that lane's `hold/`, never in `lane["prds"]`) from the `## PRDs` section on any rerun after that lane's worktree is already removed. `_drain_lane` returns an empty set once `lane.get("worktree_removed")` is true (no re-scan), so `prd_names[lane["name"]] = set(lane["prds"]) \| held` falls back to just the roster; `_write_report` rebuilds the whole report from `prd_names` every call. Violates the PRD's "written last, rewritten on rerun" contract and its own `test_rerun_is_idempotent` Exit Criterion, for the exact operator workflow (finish a kept lane, rerun assemble) the PRD calls out as normal. | skills/run-autopilot/cli/wave_assemble.py:565 | 3 | ALICE, BOB |
| [2/4] | 🟠 | **H2** — `autopilot wave assemble` has no handling for a corrupt or absent `wave.json`. `wave_cli.py:32` dispatches the `assemble` branch and returns **before** the shared `except wave.WaveCorruptError` / `loaded is None` block (`wave_cli.py:40-54`) that `launch`/`status`/`abort` all get, and it catches only `subprocess.CalledProcessError`; `wave_assemble.py` never imports or catches `WaveCorruptError` either. A corrupt file therefore yields a raw traceback instead of the friendly exit-1 refusal every sibling verb prints, and an absent file yields `wave = None` and a `TypeError`. This is the design review's own unresolved non-blocker #1, shipped unfixed. | skills/run-autopilot/cli/wave_cli.py:32 | 4 | ALICE, BOB |
| [1/4] | 🟠 | **H3** — `wave["id"]` is interpolated into the assembly worktree path, the branch name, the report filename and the deferred filename without ever being validated as a safe basename. `wave.py`'s `_TOP_CHECKS["id"]` is `isinstance(v, str)` only, while the file already defines `_is_basename` and applies it to `prds`. A hand-edited or mistyped id containing `../` escapes the intended parent directory. | skills/run-autopilot/cli/wave_assemble.py:519 | general | BOB |
| [1/4] | 🟠 | **H4** — The wave report is added to core `SKILL.md`'s Retention **Durable** list (`SKILL.md:102`), but the very next bullet (`SKILL.md:103`) states that `purge-devlocal` exempts only `autopilot/ledger/**` and that `autopilot/reports/` falls through to the `stale-autopilot` rule and is trashed once its mtime passes the 14-day threshold. The durability claim is unenforceable where it was placed: it needs a real GC exemption or a `ledger/` location. | skills/run-autopilot/SKILL.md:102 | 4 | BOB |
| [1/4] | 🟠 | **H5** — Integrator-note lines omit the required lane name. The PRD specifies one line `- <lane> <sha>: <text>` per `integrator_notes` entry, but `summary()` flattens notes to `(sha, text)` and renders `- {sha}: {text}`, discarding which lane each note came from. Task 1's acceptance test `test_summary_lists_integrator_trailers` passes because it does not pin the lane name either. | skills/run-autopilot/cli/wave_assemble.py:110 | 1 | BOB |
| [1/4] | 🟡 | A crash/kill between `_open_assembly`'s `git worktree add` and the end of the per-lane loop (where `wave["assembly"]` is finally persisted) leaves the assembly worktree registered on disk with no record of it in `wave.json`. A subsequent `assemble()` re-evaluates `wave.get("assembly") and assembly.exists()` as false and retries `git worktree add` at the same path, which git refuses. Narrow and self-diagnosable, but a real gap in an otherwise careful rerun-safety story. | skills/run-autopilot/cli/wave_assemble.py:527 | 3 | ALICE |
| [1/4] | 🟡 | Gap 4 CONFIRMED: production code is correct (`_wave_rows` filters `row.get("wave") == wave_id`), but no test seeds a second wave's rows into the same `loop-metrics.jsonl` to prove the filter excludes them, so a regression that weakened it would go undetected. | skills/run-autopilot/cli/wave_assemble.py:438 | 3 | ALICE, BOB, CARL |
| [1/4] | 🟡 | Gap 5 CONFIRMED and demonstrably consequential: `test_rerun_is_idempotent` proves only "the second call changed nothing", not "the first call's output was itself complete and correct". Combined with Gap 3's single-PRD-per-lane fixtures, this is precisely why H1 was never caught — the idempotency check passes as long as both calls agree, even when both agree on an incomplete report. | skills/run-autopilot/cli/test_wave_assemble_migrate.py:400 | 3 | ALICE, CARL |
| [1/4] | 🟡 | Worktree removal, branch deletion, flag mutation and persistence are non-atomic; a failure after removal but before `worktree_removed` is saved leaves reruns operating on a missing worktree. | skills/run-autopilot/cli/wave_assemble.py:504 | 3 | BOB |
| [1/4] | 🟡 | `merge_lane` does not clear `conflict_paths` on `checks_failed`, so a conflict→checks-failure retry retains stale paths despite the contract requiring `None` for checks failures. | skills/run-autopilot/cli/wave_assemble.py:236 | 2 | BOB |
| [1/4] | 🟡 | The runbook says a checks-failed lane branch is unchanged, but the implementation rebases that branch and resets only the assembly branch; document it as retained but rebased. | skills/run-autopilot/references/waves.md:133 | 4 | BOB |
| [1/4] | 🟡 | Totals are pinned by only two datasets, allowing a special-cased incorrect wall-hours implementation to pass; add an independent summation/rounding case (Gap 2, raised at Medium by Bob and at Low by Alice). | skills/run-autopilot/cli/test_wave_assemble.py:348 | 3 | BOB, CARL |
| [1/4] | 🟡 | `summary()` reads `wave["prds"]` rather than `wave.get("prds", [])`, so a wave dict missing the transient key raises `KeyError`. Task 1's pinned contract named `wave.get("prds", [])` explicitly. | skills/run-autopilot/cli/wave_assemble.py:94 | 1 | CARL |
| [1/4] | 🟡 | `_totals()` uses `row.get("wall_secs", 0)`, which returns `None` for a row carrying an explicit `"wall_secs": null` and raises `TypeError` inside `sum()`. The function's own docstring says a row may carry no wall time. `row.get("wall_secs") or 0` is the fix. | skills/run-autopilot/cli/wave_assemble.py:52 | 1 | CARL |
| [1/4] | 🟡 | `_migrate_jsonl()` does not filter empty or whitespace-only lines when reading jsonl files, so a blank line raises a json decode error. | skills/run-autopilot/cli/wave_assemble.py:350 | 3 | CARL |
| [1/4] | 🟡 | `_open_assembly()`'s worktree guard could be simplified to `if not assembly.exists()` so interrupted runs do not fail attempting to recreate an existing worktree (the same root cause as the Medium above at :527). | skills/run-autopilot/cli/wave_assemble.py:526 | 3 | CARL |
| [1/4] | ⚪ | Gap 2 CONFIRMED but substantially mitigated: the totals test now runs two parametrized row sets (was one), which does catch an hours/cost/count mixup. Still exactly two hand-picked totals, so a formula subtly wrong for a third arbitrary row set is not ruled out. | skills/run-autopilot/cli/test_wave_assemble.py:348 | 3 | ALICE |
| [1/4] | ⚪ | `migrate_lane`'s actual signature is `migrate_lane(main, wave_id, lane)` (three params) but the PRD's Module Exports section specifies `migrate_lane(main, lane)` (two params). The extra `wave_id` is functionally necessary and fully covered by tests; it is a literal signature mismatch against the spec's stated export. | skills/run-autopilot/cli/wave_assemble.py:390 | general | BLAKE |

### Orchestrator verification of the HIGH findings

Every 🟠 was verified by direct source reading at this HEAD before being accepted, rather than taken on the reviewer's word:

- **H1** — confirmed at `wave_assemble.py:499-507` (`_drain_lane` returns `set()` when `worktree_removed`) and `:565` (`prd_names[lane["name"]] = set(lane["prds"]) | held`). `_lane_prd_names`'s own docstring says "including ones no lane ever listed", so the non-roster case is anticipated by the code itself, not hypothetical.
- **H2** — confirmed at `wave_cli.py:32-37` versus `:40-54`. The `assemble` branch returns before the shared corrupt/absent handling and catches only `CalledProcessError`.
- **H3** — confirmed at `wave.py:284` (`"id": lambda v: isinstance(v, str)`) against `wave.py:279` (`_is_basename` exists) and `wave.py:296` (`_is_basename` applied to `prds`). The validator has the exact helper and does not use it for `id`.
- **H4** — confirmed by reading `SKILL.md:102` and `:103` together. The Durable list and the Not-durable list now disagree about the same directory.
- **H5** — confirmed at `wave_assemble.py:110-116`. The comprehension binds `(note["sha"], note["text"])` and the render is `f"- {sha}: {text}"`; the lane is not carried through.

## Alice

Ran as a native Claude subagent on the `legacy` consensus engine (`state.consensus_engine: legacy`), so no `review-fanout` workflow was invoked and no `consensus_run_id` applies.

Found two previously-unflagged code bugs by direct reading (H1 and H2 above) plus one Medium rerun-safety gap, and adjudicated all five carried-forward test gaps: gaps 1, 3, 4, 5 confirmed at Medium, gap 2 confirmed but downgraded to Low given the strengthening round's added parametrization. She explicitly declined to raise the two gaps the brief identified as the contract's own mandated behaviour.

Also reported clean: no hardcoded secrets, no `shell=True` or injection risk (all subprocess calls use list args), no skipped/xfail tests, all functions under 50 lines and files under 800, the docs edits matching their pinning test, `wave.py`'s two-loop `_LANE_CHECKS`/`_LANE_OPTIONAL_CHECKS` split byte-for-byte as specified, `merge.conflictStyle=merge` forced on every git call (mooting the diff3-marker concern in the assumption ledger), and `kept` correctly including `unfinished` lanes.

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
R13: pass

## Blake

Blind lens — received the PRD and the B1-B19 rubric only: no diff, no changed-file list, no design doc, no implementation summary, no review history. He located the code himself.

He went beyond reading and actually ran the suites: the four new/changed wave test files (41 passed) and the rest of the `[checks] waves` block (190 passed), 231 tests total, confirming every test named in the PRD's Success Metrics and phase acceptance criteria is green.

His verdict on the implementation was that it closely tracks the spec, with one literal deviation: the `migrate_lane` signature mismatch (⚪ Low, in the table above), which is why B3 fails. He found no scope creep, no missing error paths, no unguarded destructive operations, and confirmed the out-of-scope items (00216's master-landing, 00217's review-slot semaphore, auto-applying `Integrator:` trailers) are correctly absent and documented as deferred.

Worth noting as a limit of the blind lens this cycle: Blake did not independently surface H1-H5. His pass was spec-compliance-shaped and his own test runs were green, which is exactly the blind spot the carried-forward weakness predicted — a green suite over underdetermined tests reads as compliance.

B1: pass
B2: pass
B3: fail
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

## Bob

Ran on codex (thread `01a0e4d9-901a-71f1-a75f-3fc61a326bf0`, captured for cycle 2's `--resume-thread`), first run, no retry needed, exit 0. Carried the doubt + de-slop lens.

Bob was the highest-yield lens this cycle: 12 findings, and **four of the five HIGHs are his alone** (H3, H4, H5 uniquely, and H1/H2 shared with Alice). H5 in particular is a direct PRD spec violation that every other lens missed, and H4 is a contradiction he found by reading the two adjacent Retention bullets against each other. He also independently confirmed four of the five carried-forward test gaps.

His findings are prefixed `FIX —` rather than emitted under `FIX:`/`VERIFY:`/`KNOWN:` section headers. That is consistent with his assembled prompt: `agents/bob.md` plus eve.md's "Two lenses" and "Rubric verdicts" sections carries no bucket definitions (SKILL.md step 6 states this explicitly), so no VERIFY bucket exists to harvest.

R1: fail
R2: fail
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

## Carl

Ran on the gemini backend via `gemini-run.sh`, exit 0, non-empty output. 9 findings, all 🟡 Medium.

Carl was told this change has no frontend surface (it is a Python CLI verb driving git plus a markdown renderer) and correctly reviewed as a generalist without inventing frontend findings.

His value this cycle was twofold: he independently confirmed **all five** carried-forward test gaps — the only lens to confirm the complete set — and he found four robustness defects by actually executing probe snippets rather than reading, including the `row.get("wall_secs", 0)` → `None` → `TypeError` path and the `wave["prds"]` `KeyError` path. Both of the latter are contract deviations, not just style nits: task 1's pinned contract named `wave.get("prds", [])` explicitly, and `_totals`'s own docstring says a row may carry no wall time.

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
R13: pass

## Verification-check queue

**None written.** No lens emitted a VERIFY bucket this cycle: Eve did not run (the codex doubt-roster guard did not fire — zero task attempts carry `implementor: "codex"`), and Bob's assembled prompt defines no FIX/VERIFY/KNOWN buckets, so `source: "bob"` does not apply. No `dev/local/reviews/00215-assemble-a-drained-wave-onto-one-branch-v1-checks-1.json` exists, and cycle 2 has nothing to carry forward.

Verdict: 25 findings
Tests: 1319 passed, 0 failed, 0 skipped (reused from last-verification.json at 515989621530b24c5ad40f1d097ad13a727997e4)
