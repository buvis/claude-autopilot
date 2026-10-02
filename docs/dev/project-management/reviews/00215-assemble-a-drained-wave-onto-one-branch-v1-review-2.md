---
prd: dev/local/prds/wip/00215-assemble-a-drained-wave-onto-one-branch-v1.md
review: 2
date: 2026-09-28
head_sha: 5f0acd5ec83bd59227ee3245e4ed648ec3390a39
codex_thread_id: 01a0e4d9-901a-71f1-a75f-3fc61a326bf0
reviewers: alice,blake,bob,carl
agents:
  alice: available
  blake: available
  bob: available
  carl: available
---

# Review: 00215-assemble-a-drained-wave-onto-one-branch-v1

Diff range: `515989621530b24c5ad40f1d097ad13a727997e4..5f0acd5ec83bd59227ee3245e4ed648ec3390a39`
(incremental — cycle 1's `head_sha`..HEAD, 19 commits, 12 files, 70 KB. Cycle 1
reviewed the full PRD work range; this cycle reviews tasks 5-13, the cycle-1
rework batch.)

codex_rung_guard: not fired

pack: failed (engram exited 1: "not inside a registered repo; register it in `/Users/bob/.config/gita/repos.csv`"). Not retried — the same deterministic config precondition cycle 1 hit, not a transient error. `{PACK_FILE}` and `{PACK_FINDINGS}` were substituted with `(no pack available this cycle)` in every prompt that takes them. The review is degraded on retrieval context only, not invalid.

## Scope note (read before any finding)

Unlike cycle 1, this range is clean: all 19 commits are this PRD's own rework
commits and no foreign commit falls inside it, so the diff handed to the
implementation-aware lenses is the raw `--since` diff with no hand-rebuilt
segments.

One scope fact was stated to every implementation-aware lens: task 13's second
half corrected the **PRD's** own `## Module: wave_assemble` Exports line from
`migrate_lane(main, lane)` to `migrate_lane(main, wave_id, lane)`. That PRD
lives under `dev/local/`, which is gitignored in this repo by design, so the
edit is real on disk but invisible to `git diff`. No lens re-raised it.

## Deviation from the skill, recorded

Bob's assembled prompt carries `agents/bob.md` plus **three** sections of
`agents/eve.md` — "Two lenses", "Categorize every residual finding", and
"Rubric verdicts". `review-work-completion` SKILL.md step 4 names only the first
and third. The extra section gave Bob the FIX/VERIFY/KNOWN buckets, which he
emitted (cycle 1's Bob had none and his findings were prefixed `FIX —`). Effect
on this cycle: his VERIFY bucket is `(none)`, so no verification-check queue was
written and nothing downstream changed. Recorded because the assembly differed
from the skill's letter, not because it altered the outcome.

## Mechanical checks (computed, not reviewer judgment)

- **Function/file sizes:** largest changed function is `assemble` at 49 lines;
  `summary` 39, `keep_both` 7, `merge_lane` 33, `migrate_lane` 23, `_drain_lane`
  28, `_open_assembly` 24. All under 50; all files under 800. R12/R13 pass by
  computation and all four lenses agreed.
- **Tautological test shapes:** 76 test functions checked across 6 changed test
  files, **zero** shapes that cannot fail.
- **Fail-first replay:** 52 touched tests ran against the pre-change code at
  `5159896`; **20 failed there** (correct fail-first evidence) and 32 passed.
  Four `[MECH]` rows resulted and all four are absorbed into the table below as
  findings M1-M4 rather than dropped.

## Consolidated findings

10 findings: 2 🟠 High, 7 🟡 Medium, 1 ⚪ Low. No 🔴 Critical.

Consolidation ran via `consolidate_findings.py` with no `--ledger` flags (cycle
1 wrote no settled-decisions ledger, so none existed on entry). Two manual
adjustments to its output, both recorded:

1. It left the release-gate defect as **two rows** — Blake at
   `dev/bin/release-checks:107` and Bob at `dev/bin/release-checks:116` — because
   the paraphrases did not match even though the file did. They are one defect;
   merged here as H1 at consensus [2/4], the same hand-merge cycle 1 applied to
   its H2.
2. Bob's `_open_assembly` finding is **downgraded 🟠 → 🟡** by the decision gate.
   Reason in its row.

| Consensus | Severity | Issue | File | Task | Found By |
|-----------|----------|-------|------|------|----------|
| [2/4] | 🟠 | **H1** — `test_wave_assemble_summary.py` is absent from BOTH the `[checks] waves` block's pytest invocation (`dev/bin/release-checks:107-119`) and `test_wave_docs.py`'s `_WAVE_TEST_FILES` whitelist (`:41-53`). Task 10 split the summary tests out of `test_wave_assemble.py` (commit `7372327`) and registered the new file in neither list, so its 12 tests — including three Phase 0 acceptance tests the PRD names verbatim — never run in the repo's only CI gate, while `release-checks` still reports green. The test built to prevent exactly this hole, `test_the_release_gate_runs_every_wave_test_file`, passes because it asserts `named == set(_WAVE_TEST_FILES)` and the same commit updated neither side of that equality. | dev/bin/release-checks:107 | 10 | BLAKE, BOB |
| [1/4] | 🟠 | **H2** — Teardown is still crash-unsafe on the real pre-save crash. `_drain_lane` writes `lane["held_prds"]` (`:520`) and `_assemble_lane` writes `lane["status"]` in memory only; the single `save(wave_path, wave)` is at `:591`, AFTER the `git worktree remove` / `branch -D` at `:524-526`. A crash in that window loses `held_prds`, `status`, `batch_id` and `worktree_removed` together. Task 12's new test cannot catch it: it runs a full successful `assemble` first and then deletes ONLY `worktree_removed`, so it starts from a state that already persisted the other three. | skills/run-autopilot/cli/wave_assemble.py:519 | 12 | BOB |
| [1/4] | 🟡 | `_open_assembly` (`:549`) adopts any existing directory at the assembly path without verifying it is this repo's registered worktree on the expected branch. **Downgraded from 🟠 by the gate:** the path is wave-id-scoped (`{repo_parent}/{repo_name}-wave-{wave_id}`), so an unrelated worktree squatting there is improbable, and the realistic case (a stale plain directory) surfaces as a loud `git -C` failure, not as silent mutation of another branch. Real but narrower than reported. | skills/run-autopilot/cli/wave_assemble.py:549 | 12 | BOB |
| [1/4] | 🟡 | `CHANGELOG.md:12` still says a lane kept for a conflict **or** a checks failure has "its own branch and worktree left untouched" — the exact blanket claim task 13 corrected in `references/waves.md:133-137`, where a `conflict` lane's branch is untouched but a `checks_failed` lane's branch was already rebased. The changelog and the runbook now contradict each other inside the same task's scope. | CHANGELOG.md:12 | 13 | BOB |
| [1/4] | 🟡 | `_assemble_kept_region` (`test_wave_docs.py:196-212`) duplicates `_abort_keep_region` (`:118-133`): the two differ only in their heading and anchor constants, with an otherwise identical 10-line body. One parameterized anchored-region helper would replace both. | skills/run-autopilot/cli/test_wave_docs.py:196 | 13 | BOB |
| [1/4] | 🟡 | **M4** — 9 of the 14 touched tests in the split-out summary file pass against the pre-change code, among them `test_summary_opens_with_the_base_and_the_assembled_head` (cycle 1's gap 1) and `test_summary_tables_each_lane_with_its_branch_status_and_batch` (gap 3). Those two strengthenings therefore pin behavior that was already correct rather than failing on the swap/pluralisation defect their findings named; only a mutation-style test would prove them. | skills/run-autopilot/cli/test_wave_assemble_summary.py | 10 | mech-check |
| [1/4] | 🟡 | **M1** — 21 touched tests in `test_wave.py` pass against the pre-change code. | skills/run-autopilot/cli/test_wave.py | general | mech-check |
| [1/4] | 🟡 | **M2** — `test_docs_name_the_site_and_the_summary` passes against the pre-change code. | skills/run-autopilot/cli/test_wave_assemble.py | general | mech-check |
| [1/4] | 🟡 | **M3** — `test_wave_report_states_the_real_base_totals_and_lane_batches` passes against the pre-change code. | skills/run-autopilot/cli/test_wave_assemble_migrate.py | general | mech-check |
| [1/4] | ⚪ | `merge_lane` clears stale `conflict_paths` on a later clean rebase but never clears a stale `conflict_detail`, so a lane that succeeds on retry can still carry its previous failure's detail string in `wave.json`. Not one of cycle 1's 25 findings and not a regression from this rework; it sits in the function this rework touched for the sibling field. | skills/run-autopilot/cli/wave_assemble.py:220 | general | ALICE |

### Orchestrator verification of the HIGH findings

Both 🟠 were verified by direct source reading at this HEAD before being
accepted, and the downgraded row was verified too.

- **H1 — CONFIRMED, with runtime evidence.** `rg` over `dev/bin/release-checks`
  shows the `[checks] waves` block naming 11 wave test files, not including
  `test_wave_assemble_summary.py`; `test_wave_docs.py:41-53` shows the same
  11-entry whitelist. Running the file directly
  (`uv run --no-project --with pytest python -m pytest -q skills/run-autopilot/cli/test_wave_assemble_summary.py`)
  gives `12 passed in 0.01s`, so the tests exist and pass — they simply never
  run in the gate. This cycle's own full `release-checks` run counted 1327
  passed; those 12 are not among them.
- **H2 — CONFIRMED by tracing both branches of the rerun.** After the pre-save
  crash, `lane_status` (`wave_launch.py:257-267`) decides what happens next, and
  both of its outcomes are broken:
  - `lane["pid"]` set and dead → `lane_status` reads
    `<worktree>/docs/dev/project-management/autopilot/state.json`, which went
    with the removed worktree, so it returns `"unfinished"`. The merged lane is
    silently relabelled `unfinished`, lands in `kept`, the wave becomes
    `assembled_partial` and `assemble` returns 3 instead of 0 — while the lane's
    commits ARE on the assembly branch. `held_prds` is empty, so the rerun's
    report drops the lane's non-roster PRDs, re-opening cycle 1's H1 through this
    window; `migrate_lane:410` overwrites `lane["batch_id"]` with `None`, blanking
    the report's lane-batch column; and `worktree_removed` is never set, so every
    later rerun repeats all of it.
  - `lane["pid"]` None → `lane_status` returns the stale `"drained"`, so
    `_assemble_lane` calls `lane_files_and_notes`, which runs
    `subprocess.run(..., cwd=<removed worktree>, check=True)`. A missing `cwd`
    raises `FileNotFoundError`/`NotADirectoryError`, which `wave_cli.run` does not
    catch (it handles `CalledProcessError` and `WaveCorruptError` only) — a raw
    traceback out of `autopilot wave assemble`, the failure class task 6 removed
    for `wave.json`.
  No runtime reproduction was built for H2; the confirmation is source-level and
  the trace above is what it rests on.
- **Downgraded `_open_assembly` row — CONFIRMED but narrower.** `:549` is a bare
  `if not assembly.exists()`, so an existing path is adopted with no worktree or
  branch check, and `wave["assembly"]["branch"]` is then reported as the expected
  branch name whatever the worktree is really on. The wave-id in the path is what
  keeps this from being a HIGH.

### Where the lenses disagreed

Alice reported all five of cycle 1's HIGHs fixed and every Medium/Low resolved,
with 12/12 R-rules passing, having run 160 touched tests and a full
`release-checks`. Bob reported three HIGHs still open. On the two that survived
the gate, **Bob is right and Alice's pass was wrong**, verified above: she traced
`_drain_lane`'s crash-safety branches for the removal flag but not for the three
fields that share its unsaved window, and her green `release-checks` run is
precisely the false signal H1 describes — the gate is green because the missing
file is missing from both lists. Carl returned a clean review and also ran
`release-checks` green, reaching the same false signal. Blake, with no diff at
all, found H1 independently.

## Alice

Ran as a native Claude subagent on the `legacy` consensus engine
(`state.consensus_engine: legacy`), so no `review-fanout` workflow was invoked and
no `consensus_run_id` applies.

She verified each of cycle 1's five HIGHs against the current source with file
and line citations (`held_prds` at `wave_assemble.py:516-528` and its validator at
`wave.py:339-340`; the shared corrupt/absent handling at `wave_cli.py:38-40` and
`wave_assemble.py:569-571`; `_TOP_CHECKS["id"] = _is_basename` at `wave.py:298`;
the ledger mirror at `wave_assemble.py:495-498`; the `(lane, sha, text)` render at
`:117-123`), and reported every Medium/Low resolved and test-covered. She ran 160
tests over the six touched wave test files and a full `release-checks`, both green.
Her one finding is the ⚪ stale `conflict_detail` above, which she correctly framed
as out of this cycle's required scope.

Her pass on the teardown row ("independently resolved and test-covered") did not
hold: see "Where the lenses disagreed".

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

Blind lens — received the PRD and the B1-B19 rubric only: no diff, no
changed-file list, no design doc, no implementation summary, no review history.
He located the code himself. No `## Filesystem notes` block was added: this
project's root basename does not start with `.` and `dev/local` is not a symlink,
so the PRD 00141 trigger does not hold here.

He read `wave_assemble.py` end to end plus `wave_cli.py`, `wave.py`, the four
assemble test files, the four docs targets, `release-checks` and the CHANGELOG,
and ran two suites (56 passed over the five wave test files; 12 passed running the
summary file in isolation, deliberately, to prove it is not a stub).

His one finding is H1, reached from the spec side alone: the PRD's Phase 0
acceptance tests are named verbatim in a file the repo's only gate never runs. He
confirmed by `rg` with a working control that no other CI config references it.
He judged B3 a pass this cycle — cycle 1's `migrate_lane` signature mismatch is
closed, since the PRD's Exports line now names three parameters.

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

## Bob

Ran on codex, resuming cycle 1's thread `01a0e4d9-901a-71f1-a75f-3fc61a326bf0`
via `--resume-thread`, so he verified the fixes against his own cycle-1 critique
rather than re-reviewing from zero. First run, no retry needed, exit 0. The
`--emit-thread-id` sidecar rewrote the same id, so the resumed session kept its
identity and the frontmatter above carries it unchanged. Carried the doubt +
de-slop lens.

Bob was again the highest-yield lens: 5 findings, and **both surviving HIGHs are
his** (H1 shared with Blake, H2 his alone). H2 is the finding of the cycle — the
only lens to notice that task 12's crash-safety test starts from a state that
already saved the fields the real crash loses. His three remaining findings (the
CHANGELOG contradiction, the `_open_assembly` guard, the test-helper duplication)
are all real; the first is a documentation contradiction inside task 13's own
scope.

He emitted FIX/VERIFY/KNOWN buckets this cycle (see "Deviation from the skill"
above). VERIFY is `(none)`, so no verification-check queue was written.

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

Ran on the copilot backend with model `gemini-3.8-flash` via `gemini-run.sh`,
exit 0, non-empty output. Verdict: `[CARL] ✅ No issues found`, 12/12 R-rules pass.

He read the full diff in sections, computed function lengths from `ast` himself,
checked file line counts against the 800-line limit, searched for TODO/FIXME/debug
markers (none), and ran `release-checks` twice — once as dispatched and once with
`COPILOT_CLI`, `AUTOPILOT_DISPATCH_DEPTH` and `_AUTOPILOT_LOOP` unset to rule out a
nested-dispatch artifact. Both green.

His clean verdict rests on that green gate, which is the false signal H1 names: he
did not check whether the gate runs every wave test file. Counting him as a
completed reviewer is correct (exit 0, non-empty, all verdicts emitted); counting
his verdict as evidence that the gate is sound is not.

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

## Verification-check queue

**None written.** Bob's VERIFY bucket is `(none)` and Eve did not run (the codex
doubt-roster guard did not fire — zero task attempts carry
`implementor: "codex"`; the recorded implementors are `claude` and
`orchestrator`). No `00215-…-checks-2.json` exists. Cycle 1 wrote no
`checks-1.json` either, so nothing was carried forward into this cycle.

## Decision-gate outcome (recorded here, applied in Phase 5)

`state.cycle` is 2 and the PRD's `rework_cap` is 2, so **the cap is reached and
this cycle did not converge**: two unresolved 🟠 remain and convergence requires
no unresolved CRITICAL or HIGH. No 🔴 exists, so the loop-mode cap-out applies —
every unresolved finding is recorded in `state.deferred_decisions` as
`cap-overflow` and the PRD finalizes as converged-with-deferrals. Seven findings
are deferred (H1, H2, the downgraded `_open_assembly` row, the CHANGELOG
contradiction, the test-helper duplication, M4, and the ⚪ `conflict_detail`
row); M1-M3 are dismissed to the ledger as incidentally-touched pre-existing
tests.

**No follow-up tasks were created this cycle.** Creating them would leave
`state.tasks` holding pending entries the cap-out never dispatches, which would
put `tasks_completed` below `tasks_total` at the done gate. The findings' durable
home is `deferred_decisions` plus this file. `state.tasks` stays 13/13 completed.

**Two real HIGH defects ship unfixed.** H1 means 12 tests, three of them PRD-named
Phase 0 acceptance tests, do not run in `release-checks` — so the PRD's Success
Metric 2 is met only on its literal wording (`test_wave_assemble.py` is in the
block) and not on its intent. H2 means the PRD's idempotent-rerun contract has a
crash window that mislabels merged work as unfinished or aborts with a traceback.
Both are cheap to fix and both are deferred by the cap, not by a judgment that
they do not matter.

Verdict: 10 findings
Tests: 1327 passed, 0 failed, 0 skipped (suite run this cycle)
